#!/usr/bin/env python3
"""Graphite stack sizing analyser.

Discovers a Graphite stack via git config (`branch.<name>.parent`), computes
per-PR effective sizes, and reports green/soft/hard verdicts. Used by:

  1. The PreToolUse hook (~/.claude/scripts/hooks/gt-submit-sizing.js) which
     blocks `gt submit` on hard breach (this script's exit code 2).
  2. The /graphite restructure subcommand (interactive split workflow).

Subcommands:
  stack       Analyse the current stack and print verdict table
  snapshot    Back up the current stack (git bundle + graphite metadata)
  plan        Propose a split for any hard-breach PRs (path bucketing)
  override    Write a one-shot marker to bypass the next gt submit
  gc          Delete backup directories older than 30 days
  restore     (added later) restore a stack from a snapshot dir

Stdlib only. No pip dependencies.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# --- Tunables ---------------------------------------------------------------

SOFT_LINES, HARD_LINES = 600, 1200
SOFT_FILES, HARD_FILES = 18, 25
MECHANICAL_SOFT_LINES, MECHANICAL_HARD_LINES = 1800, 3500
MECHANICAL_SOFT_FILES, MECHANICAL_HARD_FILES = 40, 60
DELETION_WEIGHT = 0.3
DELETION_FLOOR_WEIGHT = 0.15
BACKUP_RETENTION_DAYS = 30

EXCLUDED_SEGMENTS = {
    "ios", "android", "node_modules", "__snapshots__",
    ".next", "dist", "build", ".turbo", ".expo",
}
EXCLUDED_FILENAMES = {
    "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "Cargo.lock",
}
EXCLUDED_SUFFIXES = (
    ".generated.ts", ".generated.js", ".snap", ".lock",
)

BACKUP_ROOT = Path.home() / ".claude" / "backups" / "graphite-stacks"
OVERRIDE_MARKER_DIR = Path("/tmp")
OVERRIDE_MARKER_PREFIX = "gt-sizing-override-"

# Exit codes (the hook depends on these)
EXIT_GREEN = 0
EXIT_SOFT = 1
EXIT_HARD = 2
EXIT_ERROR = 3

# --- Subprocess helpers -----------------------------------------------------


def run(cmd, check=True, capture=True, cwd=None):
    """Run a subprocess and return CompletedProcess. Raises on non-zero if check."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        cwd=cwd,
    )


def git(*args, check=True):
    """Run a git command, return stdout stripped."""
    res = run(["git", *args], check=check)
    return res.stdout.strip()


def gh_json(*args):
    """Run a gh command expecting JSON output. Returns parsed object or None."""
    try:
        res = run(["gh", *args], check=True)
        return json.loads(res.stdout) if res.stdout.strip() else None
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


# --- Exclusion logic --------------------------------------------------------


def is_excluded(path: str) -> bool:
    """Path-segment match (recursive). Handles nested apps/expo/ios/foo.swift."""
    parts = path.split("/")
    if any(seg in EXCLUDED_SEGMENTS for seg in parts):
        return True
    if parts and parts[-1] in EXCLUDED_FILENAMES:
        return True
    if path.endswith(EXCLUDED_SUFFIXES):
        return True
    return False


# --- Stack discovery --------------------------------------------------------


def git_common_dir() -> Path:
    """The shared .git dir, even when called from inside a worktree.
    Worktrees have their own .git/worktrees/<name>/ but Graphite stores its
    cache in the MAIN repo's .git/ — use --git-common-dir to find it."""
    return Path(git("rev-parse", "--git-common-dir"))


def graphite_cache_path() -> Path:
    """Path to the Graphite cache JSON in the shared git dir."""
    return git_common_dir() / ".graphite_cache_persist"


def graphite_repo_config_path() -> Path:
    return git_common_dir() / ".graphite_repo_config"


def load_graphite_cache() -> dict | None:
    """Load and parse .graphite_cache_persist. Returns None if missing."""
    path = graphite_cache_path()
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def get_trunk() -> str:
    """Discover the trunk branch.
    Priority: .graphite_repo_config (the source of truth Graphite uses) →
    fall back to dev/main heuristic."""
    # Graphite repo config stores the trunk under "trunk" key
    cfg_path = graphite_repo_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            trunk = cfg.get("trunk")
            if trunk:
                return trunk
        except (OSError, json.JSONDecodeError):
            pass
    # Fallback: check what dev/main exist locally
    for candidate in ("dev", "main", "master"):
        try:
            git("rev-parse", "--verify", f"refs/heads/{candidate}", check=True)
            return candidate
        except subprocess.CalledProcessError:
            continue
    return "main"


def get_current_branch() -> str:
    return git("symbolic-ref", "--short", "HEAD")


def get_parent_map() -> dict:
    """Return {child_branch: parent_branch} by parsing .graphite_cache_persist.

    Graphite stores stack metadata as a JSON file with structure:
        {"sha": "...", "branches": [[branch_name, {parentBranchName, children, ...}], ...]}

    The Feasibility review agent was wrong about git config — Graphite does
    NOT store parent relationships under branch.<name>.parent. It uses this
    cache file instead.
    """
    cache = load_graphite_cache()
    if not cache or "branches" not in cache:
        return {}
    parent_map = {}
    for entry in cache["branches"]:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        name, info = entry[0], entry[1]
        parent = info.get("parentBranchName")
        if parent:
            parent_map[name] = parent
    return parent_map


def walk_stack(current: str, trunk: str, parent_map: dict) -> list:
    """Walk parent chain from `current` up to `trunk`. Returns list ordered
    from oldest (closest to trunk) to newest (current). Includes current.
    Also walks descendants of `current` to include the full stack tip."""
    # Walk up
    ancestors = []
    cursor = current
    seen = set()
    while cursor and cursor != trunk and cursor not in seen:
        seen.add(cursor)
        if cursor != current:
            ancestors.append(cursor)
        parent = parent_map.get(cursor)
        if not parent:
            break
        cursor = parent
    ancestors.reverse()  # oldest first

    # Build child map and walk down from current to find descendants (linear only)
    child_map = {}
    for child, parent in parent_map.items():
        child_map.setdefault(parent, []).append(child)

    descendants = []
    cursor = current
    while True:
        children = child_map.get(cursor, [])
        if len(children) != 1:
            # 0 children = tip; >1 = forked stack, stop here for v1
            break
        cursor = children[0]
        if cursor in seen:
            break
        seen.add(cursor)
        descendants.append(cursor)

    return ancestors + [current] + descendants


# --- Branch metrics ---------------------------------------------------------


def get_branch_metrics(branch: str, parent: str) -> dict:
    """Return {pr_number, additions, deletions, files, body} for a branch.
    Uses gh pr list if a PR exists, else falls back to local git diff --numstat.
    """
    pr_data = gh_json(
        "pr", "list",
        "--head", branch,
        "--state", "open",
        "--json", "number,additions,deletions,files,body,title",
        "--limit", "1",
    )
    if pr_data and len(pr_data) > 0:
        pr = pr_data[0]
        return {
            "branch": branch,
            "pr_number": pr.get("number"),
            "title": pr.get("title", ""),
            "body": pr.get("body", "") or "",
            "files": [
                {
                    "path": f["path"],
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                }
                for f in pr.get("files", [])
            ],
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "source": "github",
        }

    # Local fallback: git diff --numstat parent...branch
    try:
        res = run(["git", "diff", "--numstat", f"{parent}...{branch}"], check=True)
        files = []
        total_add = 0
        total_del = 0
        for line in res.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            add = int(parts[0]) if parts[0].isdigit() else 0
            dele = int(parts[1]) if parts[1].isdigit() else 0
            path = parts[2]
            files.append({"path": path, "additions": add, "deletions": dele})
            total_add += add
            total_del += dele
        return {
            "branch": branch,
            "pr_number": None,
            "title": git("log", "-1", "--format=%s", branch, check=False),
            "body": "",
            "files": files,
            "additions": total_add,
            "deletions": total_del,
            "source": "local",
        }
    except subprocess.CalledProcessError:
        return {
            "branch": branch, "pr_number": None, "title": "", "body": "",
            "files": [], "additions": 0, "deletions": 0, "source": "error",
        }


def has_mechanical_marker(branch: str, parent: str, body: str) -> bool:
    """Check git commit trailer first, fall back to PR body."""
    try:
        res = run(
            ["git", "log", f"{parent}..{branch}", "--format=%B"],
            check=True,
        )
        commits_text = res.stdout
        if re.search(r"^Mechanical-Change:\s*true\s*$", commits_text, re.IGNORECASE | re.MULTILINE):
            return True
    except subprocess.CalledProcessError:
        pass
    if body and re.search(r"^mechanical:\s*true\s*$", body, re.IGNORECASE | re.MULTILINE):
        return True
    return False


# --- Sizing formula ---------------------------------------------------------


def compute_effective(metrics: dict) -> dict:
    """Apply exclusion + formula. Returns dict with effective_lines/files plus
    breakdown of excluded vs counted."""
    counted_files = []
    excluded_files = []
    total_add = 0
    total_del = 0
    for f in metrics["files"]:
        if is_excluded(f["path"]):
            excluded_files.append(f)
        else:
            counted_files.append(f)
            total_add += f["additions"]
            total_del += f["deletions"]
    raw_effective = total_add + (total_del * DELETION_WEIGHT)
    floor = total_del * DELETION_FLOOR_WEIGHT
    effective_lines = max(raw_effective, floor)
    return {
        "effective_lines": int(round(effective_lines)),
        "effective_files": len(counted_files),
        "counted_additions": total_add,
        "counted_deletions": total_del,
        "excluded_count": len(excluded_files),
    }


def verdict(eff_lines: int, eff_files: int, mechanical: bool) -> str:
    """Return 'green' / 'soft' / 'hard'."""
    if mechanical:
        if eff_lines > MECHANICAL_HARD_LINES or eff_files > MECHANICAL_HARD_FILES:
            return "hard"
        if eff_lines > MECHANICAL_SOFT_LINES or eff_files > MECHANICAL_SOFT_FILES:
            return "soft"
        return "green"
    if eff_lines > HARD_LINES or eff_files > HARD_FILES:
        return "hard"
    if eff_lines > SOFT_LINES or eff_files > SOFT_FILES:
        return "soft"
    return "green"


VERDICT_GLYPH = {"green": "✅", "soft": "⚠️", "hard": "🚨"}


# --- Override marker --------------------------------------------------------


def override_marker_path() -> Path:
    sha = git("rev-parse", "HEAD")
    return OVERRIDE_MARKER_DIR / f"{OVERRIDE_MARKER_PREFIX}{sha}"


def consume_override() -> str | None:
    """If a marker exists for HEAD, return reason and DELETE the marker (one-shot)."""
    path = override_marker_path()
    if path.exists():
        try:
            reason = path.read_text().strip()
        except OSError:
            reason = ""
        try:
            path.unlink()
        except OSError:
            pass
        return reason
    return None


# --- Subcommands ------------------------------------------------------------


def cmd_stack(args) -> int:
    """Analyse current stack, print verdict table, exit 0/1/2."""
    # Honour override marker (one-shot bypass for the next submit)
    if not args.no_override_check:
        reason = consume_override()
        if reason is not None:
            print(f"OVERRIDE consumed: {reason}", file=sys.stderr)
            print("Stack sizing check bypassed for this submit.", file=sys.stderr)
            return EXIT_GREEN

    trunk = get_trunk()
    current = get_current_branch()
    if current == trunk:
        print(f"On trunk ({trunk}) — no stack to analyse.", file=sys.stderr)
        return EXIT_GREEN

    parent_map = get_parent_map()
    if current not in parent_map:
        cache_path = graphite_cache_path()
        if not cache_path.exists():
            print(f"No Graphite cache at {cache_path} — this repo isn't initialised with `gt`.", file=sys.stderr)
        else:
            print(f"Branch '{current}' is not in the Graphite cache ({cache_path}).", file=sys.stderr)
            print("Run `gt track --parent <parent>` to track it, or this isn't part of a stack.", file=sys.stderr)
        return EXIT_GREEN

    branches = walk_stack(current, trunk, parent_map)
    if not branches:
        print("No stack discovered.", file=sys.stderr)
        return EXIT_GREEN

    # Build parent lookup including trunk for the bottom branch
    def parent_of(b):
        return parent_map.get(b, trunk)

    rows = []
    overall = "green"
    for branch in branches:
        parent = parent_of(branch)
        metrics = get_branch_metrics(branch, parent)
        eff = compute_effective(metrics)
        mechanical = has_mechanical_marker(branch, parent, metrics["body"])
        v = verdict(eff["effective_lines"], eff["effective_files"], mechanical)
        if v == "hard":
            overall = "hard"
        elif v == "soft" and overall == "green":
            overall = "soft"
        rows.append({
            "branch": branch,
            "metrics": metrics,
            "eff": eff,
            "mechanical": mechanical,
            "verdict": v,
        })

    # Print table
    print()
    print(f"Stack sizing report — trunk: {trunk}, branches: {len(branches)}")
    print()
    header = f"{'#':>3}  {'Branch':<40} {'PR':>6}  {'+adds':>6} {'-dels':>6} {'files':>5}  {'eff':>6} {'mech':>5}  Verdict"
    print(header)
    print("-" * len(header))
    for i, row in enumerate(rows, 1):
        m = row["metrics"]
        e = row["eff"]
        pr = f"#{m['pr_number']}" if m["pr_number"] else "(local)"
        mech = "yes" if row["mechanical"] else "no"
        glyph = VERDICT_GLYPH[row["verdict"]]
        branch_short = row["branch"][:40]
        print(
            f"{i:>3}  {branch_short:<40} {pr:>6}  "
            f"{m['additions']:>6} {m['deletions']:>6} {len(m['files']):>5}  "
            f"{e['effective_lines']:>6} {mech:>5}  {glyph} {row['verdict']}"
        )
    print()

    # Summary footer
    hard_count = sum(1 for r in rows if r["verdict"] == "hard")
    soft_count = sum(1 for r in rows if r["verdict"] == "soft")
    if hard_count:
        print(f"🚨 {hard_count} PR(s) breach the HARD limit ({HARD_LINES} eff lines / {HARD_FILES} files).", file=sys.stderr)
        print("   Run `/graphite restructure` to split, or use the override flow (see CLAUDE.md).", file=sys.stderr)
    elif soft_count:
        print(f"⚠️  {soft_count} PR(s) breach the SOFT limit ({SOFT_LINES} eff lines / {SOFT_FILES} files).", file=sys.stderr)
        print("   Consider splitting. Submit will not be blocked.", file=sys.stderr)
    else:
        print("✅ All PRs within size limits.", file=sys.stderr)

    return {"green": EXIT_GREEN, "soft": EXIT_SOFT, "hard": EXIT_HARD}[overall]


def cmd_snapshot(args) -> int:
    """Create a local backup of the current stack."""
    trunk = get_trunk()
    current = get_current_branch()
    parent_map = get_parent_map()
    branches = walk_stack(current, trunk, parent_map) if current != trunk else []

    if not branches:
        print("No stack to snapshot (on trunk or no parent config).", file=sys.stderr)
        return EXIT_ERROR

    ts = int(time.time())
    safe_branch = current.replace("/", "_")
    backup_dir = BACKUP_ROOT / f"{safe_branch}-{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. git bundle of all branches in the stack + trunk
    bundle_path = backup_dir / "stack.bundle"
    bundle_refs = [trunk] + branches
    try:
        run(["git", "bundle", "create", str(bundle_path), *bundle_refs], check=True)
    except subprocess.CalledProcessError as e:
        print(f"git bundle failed: {e.stderr}", file=sys.stderr)
        return EXIT_ERROR

    # 2. Capture branch.* git config (vscode/gitkraken merge-base hints, remotes, etc.)
    branch_config_path = backup_dir / "branch-config.txt"
    res = run(["git", "config", "--get-regexp", r"^branch\."], check=False)
    branch_config_path.write_text(res.stdout)

    # 3. Copy ALL Graphite metadata files from the shared git dir
    shared_git_dir = git_common_dir()
    for fname in (".graphite_cache_persist", ".graphite_metadata.db", ".graphite_pr_info", ".graphite_repo_config"):
        src = shared_git_dir / fname
        if src.exists():
            shutil.copy2(src, backup_dir / fname)

    # 4. Manifest
    manifest = {
        "current_branch": current,
        "trunk": trunk,
        "branches": branches,
        "branch_shas": {b: git("rev-parse", b) for b in branches},
        "timestamp": ts,
        "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # 5. Restore script (always include — task 7 will flesh out the actual restore subcommand)
    restore_sh = backup_dir / "restore.sh"
    restore_sh.write_text(f"""#!/usr/bin/env bash
# Restore script for stack snapshot taken at {manifest['iso_timestamp']}
# Generated by analyse.py snapshot
set -euo pipefail

BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)"

# Refuse if working tree is dirty
if ! git diff-index --quiet HEAD --; then
  echo "ERROR: working tree is dirty. Commit or stash before restoring." >&2
  exit 1
fi

# Create pre-restore safety refs
TS=$(date +%s)
{"".join(f'git update-ref refs/heads/{b}-pre-restore-$TS refs/heads/{b} 2>/dev/null || true{chr(10)}' for b in branches)}

# Unbundle and force-update each branch ref
git bundle unbundle "$BACKUP_DIR/stack.bundle"
{"".join(f'git update-ref refs/heads/{b} $(git rev-parse {manifest["branch_shas"][b]}){chr(10)}' for b in branches)}

# Replay branch config (parent relationships)
while IFS=' ' read -r key value; do
  [ -n "$key" ] && git config "$key" "$value"
done < "$BACKUP_DIR/branch-config.txt"

# Restore Graphite metadata files (to shared git dir, not worktree-specific)
GIT_COMMON_DIR=$(git rev-parse --git-common-dir)
for f in .graphite_cache_persist .graphite_metadata.db .graphite_pr_info .graphite_repo_config; do
  if [ -f "$BACKUP_DIR/$f" ]; then
    cp "$BACKUP_DIR/$f" "$GIT_COMMON_DIR/$f"
  fi
done

echo "Restored stack from $BACKUP_DIR"
echo "Pre-restore refs saved as <branch>-pre-restore-$TS"
""")
    restore_sh.chmod(0o755)

    print(f"Snapshot created: {backup_dir}", file=sys.stderr)
    print(f"  Branches: {len(branches)} ({', '.join(branches)})", file=sys.stderr)
    print(f"  Restore:  {restore_sh}", file=sys.stderr)
    return EXIT_GREEN


def cmd_plan(args) -> int:
    """Propose a split for any hard-breach PRs."""
    trunk = get_trunk()
    current = get_current_branch()
    parent_map = get_parent_map()
    if current == trunk or current not in parent_map:
        print("Not on a Graphite stack — nothing to plan.", file=sys.stderr)
        return EXIT_GREEN

    branches = walk_stack(current, trunk, parent_map)
    plans = []
    for branch in branches:
        parent = parent_map.get(branch, trunk)
        metrics = get_branch_metrics(branch, parent)
        eff = compute_effective(metrics)
        mechanical = has_mechanical_marker(branch, parent, metrics["body"])
        v = verdict(eff["effective_lines"], eff["effective_files"], mechanical)
        if v != "hard":
            continue
        plans.append(propose_split(branch, metrics))

    if not plans:
        print("No hard-breach PRs in the stack — nothing to split.", file=sys.stderr)
        return EXIT_GREEN

    for plan in plans:
        print(f"\n=== Split plan for {plan['branch']} ===")
        print(f"Current: {plan['original_lines']} eff lines, {plan['original_files']} files")
        print(f"Proposed: {len(plan['buckets'])} sub-PRs\n")
        for i, bucket in enumerate(plan["buckets"], 1):
            print(f"  {i}. {bucket['name']}")
            print(f"     {bucket['effective_lines']} eff lines, {len(bucket['files'])} files")
            print(f"     Suggested title: {bucket['suggested_title']}")
            for f in bucket["files"][:5]:
                print(f"       - {f}")
            if len(bucket["files"]) > 5:
                print(f"       ... and {len(bucket['files']) - 5} more")
            print()
    return EXIT_GREEN


def _bucket_files_by_depth(files: list, depth: int) -> dict:
    """Group files by their first `depth` path segments."""
    out = {}
    for f in files:
        parts = f["path"].split("/")
        key = "/".join(parts[:depth]) if len(parts) >= depth else "/".join(parts)
        out.setdefault(key, []).append(f)
    return out


def _bucket_effective(files: list) -> int:
    adds = sum(f["additions"] for f in files)
    dels = sum(f["deletions"] for f in files)
    return int(round(max(adds + dels * DELETION_WEIGHT, dels * DELETION_FLOOR_WEIGHT)))


def _find_useful_depth(files: list, start_depth: int, max_depth: int) -> int:
    """Find the smallest depth >= start_depth at which the files split into
    more than one bucket. Returns max_depth if no split is possible."""
    for d in range(start_depth, max_depth + 1):
        if len(_bucket_files_by_depth(files, d)) > 1:
            return d
    return max_depth


def _split_recursive(files: list, depth: int = 2, max_depth: int = 8) -> list:
    """Bucket files at the given depth. If any bucket is still > HARD_LINES,
    recursively subdivide that bucket at the next USEFUL depth (one that
    actually produces multiple sub-buckets). Stop at max_depth.

    Returns a flat list of {name, files, effective_lines} dicts.
    """
    # Skip past depths that don't produce a meaningful split
    useful_depth = _find_useful_depth(files, depth, max_depth)
    bucketed = _bucket_files_by_depth(files, useful_depth)
    out = []
    for key in sorted(bucketed.keys()):
        bucket_files = bucketed[key]
        eff = _bucket_effective(bucket_files)

        if eff > HARD_LINES and useful_depth < max_depth and len(bucket_files) > 1:
            # Try to subdivide this bucket at any deeper useful depth
            next_useful = _find_useful_depth(bucket_files, useful_depth + 1, max_depth)
            if next_useful > useful_depth:
                sub_buckets = _split_recursive(bucket_files, next_useful, max_depth)
                if len(sub_buckets) > 1:
                    out.extend(sub_buckets)
                    continue
        out.append({
            "name": key,
            "files": [f["path"] for f in bucket_files],
            "effective_lines": eff,
        })
    return out


def _longest_common_prefix(paths: list) -> str:
    """Longest common path-segment prefix of a list of file paths.
    e.g. ['apps/expo/src/app/(app)/home/index.tsx',
          'apps/expo/src/app/(app)/home/_layout.tsx']
         → 'apps/expo/src/app/(app)/home'"""
    if not paths:
        return ""
    split_paths = [p.split("/") for p in paths]
    common = []
    for segs in zip(*split_paths):
        if len(set(segs)) == 1:
            common.append(segs[0])
        else:
            break
    return "/".join(common)


def _short_label(path_prefix: str, max_segments: int = 2) -> str:
    """Take the last `max_segments` of a path prefix for a friendly label."""
    if not path_prefix:
        return "(root)"
    segs = path_prefix.split("/")
    return "/".join(segs[-max_segments:]) if len(segs) >= max_segments else path_prefix


def propose_split(branch: str, metrics: dict) -> dict:
    """Bucket files by path segments, recursively subdividing oversized buckets.
    Then merge tiny buckets and generate suggested titles."""
    counted_files = [f for f in metrics["files"] if not is_excluded(f["path"])]

    # Recursive bucketing — drills deeper when a bucket is still oversized
    bucket_list = _split_recursive(counted_files, depth=2)

    # Merge tiny buckets with adjacent neighbours (alphabetical)
    merge_threshold = SOFT_LINES // 2
    merged = []
    for bucket in bucket_list:
        if (merged
                and bucket["effective_lines"] < merge_threshold
                and merged[-1]["effective_lines"] + bucket["effective_lines"] < SOFT_LINES):
            merged[-1]["files"].extend(bucket["files"])
            merged[-1]["effective_lines"] += bucket["effective_lines"]
        else:
            merged.append(bucket)

    # Recompute display names from longest-common-prefix of each bucket's files
    for bucket in merged:
        prefix = _longest_common_prefix(bucket["files"])
        bucket["name"] = prefix or "(mixed)"

    # Generate suggested titles
    ticket_match = re.search(r"\[([A-Z]+-\d+)\]", metrics.get("title", ""))
    ticket = ticket_match.group(1) if ticket_match else "TICKET"
    n = len(merged)
    for i, bucket in enumerate(merged):
        suffix = chr(ord("a") + i)
        label = _short_label(bucket["name"])
        bucket["suggested_title"] = f"[{ticket}] {label} ({suffix}/{n})"

    eff_total = compute_effective(metrics)
    return {
        "branch": branch,
        "original_lines": eff_total["effective_lines"],
        "original_files": eff_total["effective_files"],
        "buckets": merged,
    }


def cmd_execute_split(args) -> int:
    """Execute a file-boundary split for the current branch.

    This wraps `gt split --by-file <pathspec>` per proposed bucket. It ONLY
    handles file-boundary splits — `gt split --by-commit` and `--by-hunk`
    are interactive and cannot be automated. For those, the script prints
    the exact command and exits non-zero so the caller knows to fall back
    to manual mode.

    Input: a JSON file describing the buckets, in the format produced by
    `analyse.py plan` (see propose_split). Format:
        {
          "branch": "<original-branch>",
          "buckets": [
            {"name": "...", "files": ["path1", "path2"], "suggested_title": "..."},
            ...
          ]
        }

    Safety:
      - Refuses if working tree is dirty
      - Refuses without --yes
      - Always takes a snapshot first (unless --skip-snapshot)
    """
    plan_path = Path(args.plan_file).expanduser().resolve()
    if not plan_path.is_file():
        print(f"ERROR: plan file does not exist: {plan_path}", file=sys.stderr)
        return EXIT_ERROR

    try:
        plan = json.loads(plan_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot parse plan file: {e}", file=sys.stderr)
        return EXIT_ERROR

    branch = plan.get("branch")
    buckets = plan.get("buckets", [])
    if not branch or not buckets:
        print("ERROR: plan file missing 'branch' or 'buckets'.", file=sys.stderr)
        return EXIT_ERROR

    if len(buckets) < 2:
        print(f"ERROR: plan has only {len(buckets)} bucket(s) — nothing to split.", file=sys.stderr)
        return EXIT_ERROR

    current = get_current_branch()
    if current != branch:
        print(f"ERROR: plan is for branch '{branch}' but current branch is '{current}'.", file=sys.stderr)
        print("Checkout the target branch first.", file=sys.stderr)
        return EXIT_ERROR

    # Refuse if dirty
    dirty_check = run(["git", "diff-index", "--quiet", "HEAD", "--"], check=False)
    if dirty_check.returncode != 0:
        print("ERROR: working tree is dirty. Commit or stash before splitting.", file=sys.stderr)
        return EXIT_ERROR

    print("=" * 60, file=sys.stderr)
    print(f"Split plan for: {branch}", file=sys.stderr)
    print(f"Buckets: {len(buckets)}", file=sys.stderr)
    for i, b in enumerate(buckets, 1):
        print(f"  {i}. {b.get('name', '?')}  ({len(b.get('files', []))} files)", file=sys.stderr)
        print(f"     Title: {b.get('suggested_title', '(none)')}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    if not args.yes:
        print("", file=sys.stderr)
        print("This will run `gt split --by-file <pathspec>` for each bucket above,", file=sys.stderr)
        print("then `gt restack --no-interactive`. The current branch will be replaced", file=sys.stderr)
        print("by N new branches in a stack.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Re-run with --yes to proceed.", file=sys.stderr)
        return EXIT_ERROR

    # Snapshot first unless explicitly skipped
    if not args.skip_snapshot:
        print("Taking pre-split snapshot ...", file=sys.stderr)
        snap_args = argparse.Namespace()
        snap_result = cmd_snapshot(snap_args)
        if snap_result != EXIT_GREEN:
            print("ERROR: snapshot failed. Aborting split.", file=sys.stderr)
            return EXIT_ERROR

    # Execute splits. `gt split --by-file <pathspec>` takes one pathspec at a time.
    # We need to think carefully about ordering: each split creates a new branch,
    # so subsequent splits operate on what's left.
    print("", file=sys.stderr)
    print(f"Executing {len(buckets)} splits ...", file=sys.stderr)
    for i, bucket in enumerate(buckets, 1):
        files = bucket.get("files", [])
        if not files:
            continue
        # Build a pathspec from the file list. Quote each file safely via separate args.
        cmd = ["gt", "split", "--by-file", "--no-interactive", *files]
        print(f"\n[{i}/{len(buckets)}] {bucket.get('name', '?')}", file=sys.stderr)
        print(f"  $ gt split --by-file --no-interactive {' '.join(files[:3])}{'...' if len(files) > 3 else ''}", file=sys.stderr)
        result = run(cmd, check=False, capture=False)
        if result.returncode != 0:
            print(f"\nERROR: gt split failed for bucket {i}. Aborting.", file=sys.stderr)
            print("Recovery: restore from the snapshot taken at the start of this run.", file=sys.stderr)
            return EXIT_ERROR

    print("\nRestacking ...", file=sys.stderr)
    result = run(["gt", "restack", "--no-interactive"], check=False, capture=False)
    if result.returncode != 0:
        print("WARNING: gt restack exited non-zero. Manual intervention may be needed.", file=sys.stderr)
        return EXIT_ERROR

    print(f"\n✅ Split complete. {len(buckets)} new branches created.", file=sys.stderr)
    print("Run `gt log` to see the new stack, then `gt submit --no-interactive --publish` to push.", file=sys.stderr)
    return EXIT_GREEN


def cmd_override(args) -> int:
    """Write a one-shot marker to bypass the next gt submit."""
    reason = args.reason.strip()
    if not reason:
        print("ERROR: override reason cannot be empty.", file=sys.stderr)
        return EXIT_ERROR
    path = override_marker_path()
    path.write_text(reason)
    print(f"Override marker written: {path}", file=sys.stderr)
    print(f"Reason: {reason}", file=sys.stderr)
    print("The next `gt submit` will bypass the sizing hook (one-shot).", file=sys.stderr)
    print(f"After submit, append the reason to each offending PR body via:", file=sys.stderr)
    print(f'  gh pr edit <n> --body-append "**Override reason**: {reason}"', file=sys.stderr)
    return EXIT_GREEN


def cmd_gc(args) -> int:
    """Delete backup directories older than BACKUP_RETENTION_DAYS."""
    if not BACKUP_ROOT.exists():
        print("No backups to GC.", file=sys.stderr)
        return EXIT_GREEN
    cutoff = time.time() - (BACKUP_RETENTION_DAYS * 86400)
    deleted = 0
    for entry in BACKUP_ROOT.iterdir():
        if not entry.is_dir():
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                if args.dry_run:
                    print(f"Would delete: {entry}", file=sys.stderr)
                else:
                    shutil.rmtree(entry)
                    print(f"Deleted: {entry}", file=sys.stderr)
                deleted += 1
        except OSError as e:
            print(f"Failed to process {entry}: {e}", file=sys.stderr)
    print(f"GC complete: {deleted} backup(s) {'would be ' if args.dry_run else ''}deleted (>{BACKUP_RETENTION_DAYS} days old).", file=sys.stderr)
    return EXIT_GREEN


def cmd_restore(args) -> int:
    """Restore a stack from a snapshot directory.

    Safety order:
      1. Validate the backup dir has the expected files
      2. Read manifest to know what we're restoring
      3. Refuse if working tree is dirty (commits would be lost)
      4. Refuse without --yes (force human-in-the-loop confirmation)
      5. Run the snapshot's restore.sh
      6. Verify branch SHAs match the manifest
    """
    backup_dir = Path(args.backup_dir).expanduser().resolve()
    if not backup_dir.is_dir():
        print(f"ERROR: backup directory does not exist: {backup_dir}", file=sys.stderr)
        return EXIT_ERROR

    manifest_path = backup_dir / "manifest.json"
    bundle_path = backup_dir / "stack.bundle"
    restore_sh = backup_dir / "restore.sh"
    for required in (manifest_path, bundle_path, restore_sh):
        if not required.exists():
            print(f"ERROR: missing {required.name} in backup directory.", file=sys.stderr)
            return EXIT_ERROR

    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read manifest.json: {e}", file=sys.stderr)
        return EXIT_ERROR

    # Show what we're about to do
    print("=" * 60, file=sys.stderr)
    print(f"Restore from: {backup_dir}", file=sys.stderr)
    print(f"Snapshot taken: {manifest.get('iso_timestamp', 'unknown')}", file=sys.stderr)
    print(f"Original branch: {manifest.get('current_branch', 'unknown')}", file=sys.stderr)
    print(f"Trunk: {manifest.get('trunk', 'unknown')}", file=sys.stderr)
    branches = manifest.get("branches", [])
    print(f"Branches to restore ({len(branches)}):", file=sys.stderr)
    for b in branches:
        sha = manifest.get("branch_shas", {}).get(b, "?")
        # Show whether the branch exists locally and whether SHA matches
        try:
            current_sha = git("rev-parse", b, check=True)
            status = "✓ matches" if current_sha == sha else f"⚠️  current: {current_sha[:8]}, target: {sha[:8]}"
        except subprocess.CalledProcessError:
            status = "○ does not exist locally (will be created)"
        print(f"  - {b}  {status}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Refuse if working tree is dirty
    dirty_check = run(["git", "diff-index", "--quiet", "HEAD", "--"], check=False)
    if dirty_check.returncode != 0:
        print("ERROR: working tree is dirty. Commit or stash before restoring.", file=sys.stderr)
        print("(restore would force-update branch refs, which could destroy uncommitted work)", file=sys.stderr)
        return EXIT_ERROR

    # Require explicit confirmation
    if not args.yes:
        print("", file=sys.stderr)
        print("This will FORCE-UPDATE the branch refs above to match the snapshot.", file=sys.stderr)
        print("Pre-restore safety refs (`<branch>-pre-restore-<ts>`) will be created first,", file=sys.stderr)
        print("so you can recover with `git reset --hard <safety-ref>` if needed.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Re-run with --yes to proceed:", file=sys.stderr)
        print(f"  python3 {sys.argv[0]} restore {backup_dir} --yes", file=sys.stderr)
        return EXIT_ERROR

    # Run the restore script
    print("Running restore.sh ...", file=sys.stderr)
    result = run(["bash", str(restore_sh)], check=False, capture=False)
    if result.returncode != 0:
        print(f"ERROR: restore.sh exited {result.returncode}", file=sys.stderr)
        return EXIT_ERROR

    # Verify branch SHAs match the manifest after restore
    print("", file=sys.stderr)
    print("Verifying restored state:", file=sys.stderr)
    mismatches = 0
    for b in branches:
        expected = manifest.get("branch_shas", {}).get(b)
        try:
            actual = git("rev-parse", b, check=True)
            if actual == expected:
                print(f"  ✓ {b}", file=sys.stderr)
            else:
                print(f"  ✗ {b}  expected {expected[:8]}, got {actual[:8]}", file=sys.stderr)
                mismatches += 1
        except subprocess.CalledProcessError:
            print(f"  ✗ {b}  branch missing after restore", file=sys.stderr)
            mismatches += 1

    if mismatches:
        print(f"\n⚠️  {mismatches} branch(es) did not restore cleanly.", file=sys.stderr)
        print("Recovery: pre-restore safety refs are at `<branch>-pre-restore-<unix-ts>`.", file=sys.stderr)
        return EXIT_ERROR

    print(f"\n✅ Restore complete. {len(branches)} branch(es) restored.", file=sys.stderr)
    print("Note: Graphite cache was also restored — `gt log` should show the original stack.", file=sys.stderr)
    return EXIT_GREEN


# --- Argparse setup ---------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="analyse.py",
        description="Graphite stack sizing analyser. See script docstring for full usage.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_stack = sub.add_parser("stack", help="Analyse the current stack and print verdict table")
    p_stack.add_argument("--no-override-check", action="store_true",
                         help="Skip the override marker check (for debugging)")
    p_stack.set_defaults(func=cmd_stack)

    p_snap = sub.add_parser("snapshot", help="Back up the current stack to ~/.claude/backups/graphite-stacks/")
    p_snap.set_defaults(func=cmd_snapshot)

    p_plan = sub.add_parser("plan", help="Propose a split for hard-breach PRs in the stack")
    p_plan.set_defaults(func=cmd_plan)

    p_over = sub.add_parser("override", help="Write a one-shot marker to bypass the next gt submit")
    p_over.add_argument("reason", help="Why this submit should bypass the sizing check")
    p_over.set_defaults(func=cmd_override)

    p_exec = sub.add_parser("execute-split", help="Execute a file-boundary split from a JSON plan file")
    p_exec.add_argument("plan_file", help="Path to a JSON plan file (see `plan` subcommand)")
    p_exec.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    p_exec.add_argument("--skip-snapshot", action="store_true", help="Don't take a pre-split snapshot (NOT recommended)")
    p_exec.set_defaults(func=cmd_execute_split)

    p_gc = sub.add_parser("gc", help=f"Delete backup directories older than {BACKUP_RETENTION_DAYS} days")
    p_gc.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    p_gc.set_defaults(func=cmd_gc)

    p_rest = sub.add_parser("restore", help="Restore a stack from a snapshot directory")
    p_rest.add_argument("backup_dir", help="Path to the snapshot directory (created by `snapshot`)")
    p_rest.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt and proceed with the restore")
    p_rest.set_defaults(func=cmd_restore)

    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()
