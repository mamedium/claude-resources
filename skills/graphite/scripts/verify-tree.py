#!/usr/bin/env python3
"""
Tree-hash integrity guardrail for Graphite stack restructures.

Purpose
-------
A Graphite restructure (gt track/restack/split/reparent) can silently drop
commits or mis-resolve conflicts, leaving a stack whose topology looks fine
but whose content no longer matches the original. This script prevents that
by snapshotting git tree SHAs before the restructure and verifying them after.

Every git commit points to a tree object whose SHA is a hash of the entire
directory state. Two different commits with identical content share the same
tree SHA. So "content preserved" == "tip tree SHA unchanged".

Usage
-----
  verify-tree.py snapshot              # BEFORE any restructure
  verify-tree.py verify                # AFTER restructure, before gt submit
  verify-tree.py verify --backup <dir> # Explicit backup to verify against
  verify-tree.py status                # Show the most recent snapshot + verify state
  verify-tree.py clear                 # Clear the "pending" marker (if restructure aborted)

Exit codes
----------
  0  green  — snapshot written, or verify passed
  1  soft   — no recent snapshot to verify against (not an error)
  2  hard   — verify failed (tree drift detected) OR pending marker present

Marker file lifecycle
---------------------
Each snapshot directory contains `verify-status` with one of:
  pending  — snapshot taken, verify not yet run (blocks gt submit)
  passed   — verify succeeded
  failed   — verify detected drift (blocks gt submit)

The gt-submit-sizing hook reads the most recent snapshot's marker. If it is
`pending` or `failed`, the hook blocks the submit.

Known legitimate exceptions (manual override required)
------------------------------------------------------
- Mechanical trailer commits (`Mechanical-Change: true`) add real content.
- PR splits: tip tree will differ. Verify manually by checking that the union
  of split branches' content equals the original branch's content.

For these cases, after the restructure run:
  verify-tree.py verify --accept-drift "<reason>"
to mark the latest snapshot as passed with the reason recorded.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BACKUP_ROOT = Path.home() / ".claude" / "backups" / "graphite-stacks"

EXIT_GREEN = 0
EXIT_SOFT = 1
EXIT_HARD = 2

# Marker values
STATUS_PENDING = "pending"
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"

# Consider a snapshot "recent" (hook-relevant) if it's within this many seconds.
RECENT_WINDOW_SECONDS = 6 * 60 * 60  # 6 hours


def run(cmd, check=True):
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
    )


def git(*args):
    result = run(["git", *args], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_trunk() -> str:
    """Best-effort trunk detection. Matches analyse.py conventions."""
    # Try Graphite's trunk config first
    trunk = git("config", "--get", "branch.trunk")
    if trunk:
        return trunk
    # Fall back to common defaults
    for candidate in ("dev", "main", "master"):
        if git("rev-parse", "--verify", candidate) is not None:
            return candidate
    return "main"


def get_current_branch() -> str:
    branch = git("symbolic-ref", "--short", "HEAD")
    if branch is None:
        # Detached HEAD
        sha = git("rev-parse", "--short", "HEAD") or "detached"
        return f"(detached:{sha})"
    return branch


def get_parent_map() -> dict:
    """Return {branch_name: parent_branch_name} for every Graphite-tracked branch.

    Source priority:
      1. `.git/.graphite_metadata.db` (modern Graphite CLI — SQLite)
      2. `branch.<name>.parent` git config entries (legacy Graphite)
    """
    parents: dict = {}

    # Source 1: SQLite metadata (modern Graphite)
    git_dir = git("rev-parse", "--git-dir") or ".git"
    db_path = Path(git_dir) / ".graphite_metadata.db"
    if db_path.exists():
        try:
            import sqlite3
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                cur = con.execute(
                    "SELECT branch_name, parent_branch_name "
                    "FROM branch_metadata "
                    "WHERE parent_branch_name IS NOT NULL AND parent_branch_name != ''"
                )
                for branch_name, parent_branch_name in cur.fetchall():
                    parents[branch_name] = parent_branch_name
            finally:
                con.close()
            if parents:
                return parents
        except (sqlite3.Error, ImportError) as e:
            print(f"verify-tree: WARNING — could not read Graphite SQLite ({e}), "
                  f"falling back to git config.", file=sys.stderr)

    # Source 2: legacy git config entries
    result = run(["git", "config", "--get-regexp", r"^branch\..*\.parent$"], check=False)
    if result.returncode != 0:
        return parents
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        key, value = parts
        if key.startswith("branch.") and key.endswith(".parent"):
            branch_name = key[len("branch."):-len(".parent")]
            parents[branch_name] = value.strip()
    return parents


def walk_stack(tip: str, trunk: str, parent_map: dict) -> list:
    """Walk parent_map from tip down to trunk. Returns bottom→tip order."""
    chain = []
    seen = set()
    cur = tip
    while cur and cur != trunk:
        if cur in seen:
            # cycle guard
            break
        seen.add(cur)
        chain.append(cur)
        cur = parent_map.get(cur)
    chain.reverse()
    return chain


def tree_sha_for(ref: str):
    """Return the tree SHA for a ref, or None if the ref doesn't resolve."""
    return git("rev-parse", f"{ref}^{{tree}}")


def compute_diff_hash(parent_ref: str, branch_ref: str) -> str | None:
    """SHA256 the exact bytes of `git diff <parent>..<branch>`.

    No normalisation — exact byte comparison is the point. Returns None if
    either ref fails to resolve.
    """
    result = subprocess.run(
        ["git", "diff", f"{parent_ref}..{branch_ref}"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def compute_diff_stats(parent_ref: str, branch_ref: str) -> dict:
    """Parse `git diff --shortstat` into {files, insertions, deletions}."""
    stats = {"files": 0, "insertions": 0, "deletions": 0}
    result = run(
        ["git", "diff", "--shortstat", f"{parent_ref}..{branch_ref}"],
        check=False,
    )
    if result.returncode != 0:
        return stats
    line = result.stdout.strip()
    # e.g. " 6 files changed, 791 insertions(+), 19 deletions(-)"
    m_files = re.search(r"(\d+) files? changed", line)
    m_ins = re.search(r"(\d+) insertions?\(\+\)", line)
    m_del = re.search(r"(\d+) deletions?\(-\)", line)
    if m_files:
        stats["files"] = int(m_files.group(1))
    if m_ins:
        stats["insertions"] = int(m_ins.group(1))
    if m_del:
        stats["deletions"] = int(m_del.group(1))
    return stats


def compute_diff_file_set(parent_ref: str, branch_ref: str) -> set[str]:
    """Set of file paths touched by `git diff --name-only <parent>..<branch>`."""
    result = run(
        ["git", "diff", "--name-only", f"{parent_ref}..{branch_ref}"],
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {line for line in result.stdout.splitlines() if line.strip()}


def find_latest_snapshot() -> Path | None:
    """Return the most recent verify-tree snapshot dir, or None."""
    if not BACKUP_ROOT.exists():
        return None
    candidates = [
        d for d in BACKUP_ROOT.iterdir()
        if d.is_dir() and (d / "tree-hashes.txt").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def read_marker(backup_dir: Path) -> str | None:
    marker = backup_dir / "verify-status"
    if not marker.exists():
        return None
    return marker.read_text().strip().split()[0] if marker.read_text().strip() else None


def write_marker(backup_dir: Path, status: str, note: str = "") -> None:
    marker = backup_dir / "verify-status"
    line = status if not note else f"{status} {note}"
    marker.write_text(line + "\n")


def cmd_snapshot(args) -> int:
    trunk = get_trunk()
    parent_map = get_parent_map()

    # --tip overrides current branch so you can snapshot a full stack from
    # the bottom without checking out the real tip. No git working tree change.
    tip_override = getattr(args, "tip", None)
    if tip_override:
        # Verify the branch exists before we bother walking.
        if git("rev-parse", "--verify", tip_override) is None:
            print(f"verify-tree: --tip branch '{tip_override}' does not exist.",
                  file=sys.stderr)
            return EXIT_HARD
        # Warn if Graphite doesn't know about it — walk_stack will still try,
        # but the chain will just be [tip_override] which is probably not what
        # the user wanted.
        if tip_override not in parent_map:
            print(f"verify-tree: WARNING — '{tip_override}' has no Graphite "
                  f"parent registered. Snapshot will record just this one "
                  f"branch. Did you mean to run `gt track {tip_override}` first?",
                  file=sys.stderr)
        current = tip_override
    else:
        current = get_current_branch()

    if current == trunk or current.startswith("(detached"):
        print(f"verify-tree: cannot snapshot — on trunk or detached HEAD ({current}).",
              file=sys.stderr)
        return EXIT_SOFT

    branches = walk_stack(current, trunk, parent_map)
    if not branches:
        print(f"verify-tree: no stack to snapshot (branch {current} has no parent chain).",
              file=sys.stderr)
        return EXIT_SOFT

    ts = int(time.time())
    safe_branch = current.replace("/", "_").replace(" ", "_")
    backup_dir = BACKUP_ROOT / f"verify-{safe_branch}-{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Record tree SHAs for every branch in the stack.
    lines = []
    branch_trees = {}
    for b in branches:
        t = tree_sha_for(b)
        if t is None:
            print(f"verify-tree: WARNING — could not resolve tree for '{b}'.",
                  file=sys.stderr)
            continue
        branch_trees[b] = t
        lines.append(f"{b} {t}")
    (backup_dir / "tree-hashes.txt").write_text("\n".join(lines) + "\n")

    # Record per-branch PR diff signatures. For each branch, the parent is
    # the previous entry in the bottom→tip chain, or `trunk` for the first.
    branch_pr_diffs: dict = {}
    for idx, b in enumerate(branches):
        parent_branch = trunk if idx == 0 else branches[idx - 1]
        parent_sha = git("rev-parse", parent_branch)
        tip_sha = git("rev-parse", b)
        if parent_sha is None or tip_sha is None:
            print(f"verify-tree: WARNING — could not resolve PR diff base for "
                  f"'{b}' (parent={parent_branch}).", file=sys.stderr)
            continue
        diff_hash = compute_diff_hash(parent_sha, tip_sha)
        if diff_hash is None:
            print(f"verify-tree: WARNING — could not compute diff hash for "
                  f"'{b}'.", file=sys.stderr)
            continue
        branch_pr_diffs[b] = {
            "parent_branch_at_snapshot": parent_branch,
            "parent_at_snapshot": parent_sha,
            "tip_at_snapshot": tip_sha,
            "diff_hash": diff_hash,
            "diff_stats": compute_diff_stats(parent_sha, tip_sha),
        }

    # Stack tip == last branch in bottom→tip order.
    tip_branch = branches[-1]
    tip_tree = branch_trees.get(tip_branch)
    tip_commit = git("rev-parse", tip_branch)
    head_sha = git("rev-parse", "HEAD")

    manifest = {
        "kind": "verify-tree-snapshot",
        "version": 1,
        "timestamp": ts,
        "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
        "trunk": trunk,
        "current_branch": current,
        "tip_branch": tip_branch,
        "tip_tree_sha": tip_tree,
        "tip_commit_sha": tip_commit,
        "head_sha_at_snapshot": head_sha,
        "branches": branches,
        "branch_trees": branch_trees,
        "branch_pr_diffs": branch_pr_diffs,
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Tag HEAD for easy rollback reference. Non-fatal if tagging fails.
    tag_name = f"backup/pre-restructure-{ts}"
    tag_result = run(["git", "tag", tag_name, "HEAD"], check=False)
    if tag_result.returncode == 0:
        (backup_dir / "git-tag.txt").write_text(tag_name + "\n")
    else:
        print(f"verify-tree: WARNING — could not create tag {tag_name}: "
              f"{tag_result.stderr.strip()}", file=sys.stderr)

    # Mark as pending — hook will block submit until verify runs.
    write_marker(backup_dir, STATUS_PENDING)

    print(f"verify-tree: snapshot saved → {backup_dir}", file=sys.stderr)
    print(f"  tip branch:   {tip_branch}", file=sys.stderr)
    print(f"  tip tree SHA: {tip_tree}", file=sys.stderr)
    print(f"  branches:     {len(branches)}", file=sys.stderr)
    if tag_result.returncode == 0:
        print(f"  rollback tag: {tag_name}", file=sys.stderr)
    print("  status:       PENDING (gt submit will be blocked until verify passes)",
          file=sys.stderr)
    return EXIT_GREEN


def _load_manifest(backup_dir: Path) -> dict | None:
    mf = backup_dir / "manifest.json"
    if not mf.exists():
        return None
    try:
        return json.loads(mf.read_text())
    except json.JSONDecodeError:
        return None


def _verify_tip_tree(manifest: dict, backup_dir: Path) -> tuple[bool, str]:
    """Check the recorded tip tree SHA against current state.

    Returns (ok, failure_reason). On success, prints a success line.
    On failure, prints a detailed drift report. Does NOT write the marker.
    """
    original_tip_tree = manifest.get("tip_tree_sha")
    tip_branch = manifest.get("tip_branch")

    new_tip_tree = tree_sha_for(tip_branch)
    if new_tip_tree is None:
        print(f"verify-tree: FAIL — tip branch '{tip_branch}' no longer exists.",
              file=sys.stderr)
        return (False, "tip-missing")

    if new_tip_tree != original_tip_tree:
        print("verify-tree: ❌ TIP TREE DRIFT DETECTED", file=sys.stderr)
        print(f"  tip branch:       {tip_branch}", file=sys.stderr)
        print(f"  original tree:    {original_tip_tree}", file=sys.stderr)
        print(f"  current tree:     {new_tip_tree}", file=sys.stderr)
        print("", file=sys.stderr)
        print("  Diff (stat):", file=sys.stderr)
        diff_result = run(
            ["git", "diff", "--stat", original_tip_tree, new_tip_tree],
            check=False,
        )
        if diff_result.returncode == 0:
            for line in diff_result.stdout.splitlines():
                print(f"    {line}", file=sys.stderr)
        else:
            print(f"    (could not compute diff: {diff_result.stderr.strip()})",
                  file=sys.stderr)
        print(f"  Rollback tag: {manifest.get('head_sha_at_snapshot', '(none)')[:12]} "
              f"(see {backup_dir}/git-tag.txt)", file=sys.stderr)
        return (False, "tree-drift")

    print(f"verify-tree: ✅ tip tree preserved ({tip_branch})", file=sys.stderr)
    return (True, "")


def _verify_pr_content(manifest: dict) -> tuple[bool, str]:
    """Per-branch PR-diff preservation check.

    For each branch recorded in manifest['branch_pr_diffs'], re-compute the
    diff hash against its CURRENT parent and compare against the recorded
    hash. Prints a report per branch. Returns (ok, failure_reason).
    """
    branch_pr_diffs: dict = manifest.get("branch_pr_diffs") or {}
    if not branch_pr_diffs:
        print("verify-tree: ⚠️  no per-branch PR diffs recorded — snapshot "
              "pre-dates the pr-content feature. Skipping PR content check.",
              file=sys.stderr)
        return (True, "")

    trunk = manifest.get("trunk") or get_trunk()
    branches_order: list = manifest.get("branches") or list(branch_pr_diffs.keys())
    current_parent_map = get_parent_map()

    print("verify-tree: PR content check", file=sys.stderr)

    drifted: list = []
    preserved: list = []

    for idx, branch in enumerate(branches_order):
        record = branch_pr_diffs.get(branch)
        if record is None:
            continue

        # Resolve the branch's CURRENT parent.
        current_parent = current_parent_map.get(branch)
        if current_parent is None:
            # Fall back to the position-based chain from the manifest.
            current_parent = trunk if idx == 0 else branches_order[idx - 1]

        # Verify the branch and parent still resolve.
        if git("rev-parse", "--verify", branch) is None:
            print(f"  ⚠️  {branch}    branch no longer exists", file=sys.stderr)
            drifted.append(branch)
            continue
        if git("rev-parse", "--verify", current_parent) is None:
            print(f"  ⚠️  {branch}    parent '{current_parent}' no longer exists",
                  file=sys.stderr)
            drifted.append(branch)
            continue

        current_hash = compute_diff_hash(current_parent, branch)
        if current_hash is None:
            print(f"  ⚠️  {branch}    could not compute current diff hash",
                  file=sys.stderr)
            drifted.append(branch)
            continue

        recorded_hash = record.get("diff_hash")
        recorded_stats = record.get("diff_stats") or {}

        if current_hash == recorded_hash:
            stats_str = (f"{recorded_stats.get('files', 0)} files, "
                         f"{recorded_stats.get('insertions', 0)}+/"
                         f"{recorded_stats.get('deletions', 0)}-")
            print(f"  ✅ {branch}    PR diff unchanged ({stats_str})",
                  file=sys.stderr)
            preserved.append(branch)
            continue

        # Drift — compute file-level delta for the report.
        print(f"  ⚠️  {branch}    PR diff DRIFTED", file=sys.stderr)

        old_parent = record.get("parent_at_snapshot")
        old_tip = record.get("tip_at_snapshot")
        old_files: set = set()
        if old_parent and old_tip:
            old_files = compute_diff_file_set(old_parent, old_tip)
        new_files = compute_diff_file_set(current_parent, branch)

        added = sorted(new_files - old_files)
        removed = sorted(old_files - new_files)
        if added:
            print(f"      Files added in current: {', '.join(added[:5])}"
                  f"{' …' if len(added) > 5 else ''}", file=sys.stderr)
        if removed:
            print(f"      Files removed in current: {', '.join(removed[:5])}"
                  f"{' …' if len(removed) > 5 else ''}", file=sys.stderr)

        new_stats = compute_diff_stats(current_parent, branch)
        old_ins = recorded_stats.get("insertions", 0)
        old_del = recorded_stats.get("deletions", 0)
        new_ins = new_stats.get("insertions", 0)
        new_del = new_stats.get("deletions", 0)
        print(f"      Line delta: was +{old_ins}/-{old_del}, "
              f"now +{new_ins}/-{new_del}", file=sys.stderr)

        drifted.append(branch)

    print("", file=sys.stderr)
    if drifted:
        print(f"{len(drifted)} branch(es) drifted, "
              f"{len(preserved)} preserved", file=sys.stderr)
        print("Run `verify --pr-content --accept-drift \"<reason>\"` to "
              "accept intentional drift.", file=sys.stderr)
        return (False, "pr-content-drift")

    print(f"All {len(preserved)} branch(es) preserved", file=sys.stderr)
    return (True, "")


def cmd_verify(args) -> int:
    if args.backup:
        backup_dir = Path(args.backup).expanduser().resolve()
    else:
        backup_dir = find_latest_snapshot()
        if backup_dir is None:
            print("verify-tree: no snapshot found to verify against.", file=sys.stderr)
            return EXIT_SOFT

    manifest = _load_manifest(backup_dir)
    if manifest is None or manifest.get("kind") != "verify-tree-snapshot":
        print(f"verify-tree: {backup_dir} is not a valid verify-tree snapshot.",
              file=sys.stderr)
        return EXIT_HARD

    # Allow the user to manually accept drift (splits, mechanical changes).
    if args.accept_drift is not None:
        reason = args.accept_drift.strip()
        if not reason:
            print("verify-tree: --accept-drift requires a non-empty reason.",
                  file=sys.stderr)
            return EXIT_HARD
        write_marker(backup_dir, STATUS_PASSED, f"accepted-drift: {reason}")
        print(f"verify-tree: drift ACCEPTED for {backup_dir.name}", file=sys.stderr)
        print(f"  reason: {reason}", file=sys.stderr)
        return EXIT_GREEN

    # Decide which checks to run based on flags.
    # Default: run BOTH tip-tree and pr-content checks.
    # --tip-only: skip pr-content.
    # --pr-content: skip tip-tree (explicit pr-content-only mode).
    run_tip = not args.pr_content
    run_pr = not args.tip_only

    if args.tip_only and args.pr_content:
        print("verify-tree: --tip-only and --pr-content are mutually exclusive.",
              file=sys.stderr)
        return EXIT_HARD

    tip_ok = True
    pr_ok = True
    failure_reason = ""

    if run_tip:
        tip_ok, tip_reason = _verify_tip_tree(manifest, backup_dir)
        if not tip_ok:
            failure_reason = tip_reason

    if run_pr:
        pr_ok, pr_reason = _verify_pr_content(manifest)
        if not pr_ok and not failure_reason:
            failure_reason = pr_reason

    if tip_ok and pr_ok:
        print(f"verify-tree: ✅ CONTENT PRESERVED ({backup_dir.name})",
              file=sys.stderr)
        write_marker(backup_dir, STATUS_PASSED)
        return EXIT_GREEN

    print("", file=sys.stderr)
    print("  Investigate manually. If drift is intentional (split, mechanical),",
          file=sys.stderr)
    print("  re-run: verify-tree.py verify --accept-drift \"<reason>\"",
          file=sys.stderr)
    write_marker(backup_dir, STATUS_FAILED, failure_reason)
    return EXIT_HARD


def cmd_status(args) -> int:
    backup_dir = find_latest_snapshot()
    if backup_dir is None:
        print("verify-tree: no snapshots present.", file=sys.stderr)
        return EXIT_SOFT
    manifest = _load_manifest(backup_dir) or {}
    marker = read_marker(backup_dir) or "(no marker)"
    age = int(time.time() - backup_dir.stat().st_mtime)
    print(f"verify-tree: latest snapshot", file=sys.stderr)
    print(f"  dir:        {backup_dir}", file=sys.stderr)
    print(f"  age:        {age}s", file=sys.stderr)
    print(f"  tip branch: {manifest.get('tip_branch', '?')}", file=sys.stderr)
    print(f"  tip tree:   {manifest.get('tip_tree_sha', '?')}", file=sys.stderr)
    print(f"  status:     {marker}", file=sys.stderr)
    return EXIT_GREEN


def cmd_clear(args) -> int:
    backup_dir = find_latest_snapshot()
    if backup_dir is None:
        print("verify-tree: no snapshots to clear.", file=sys.stderr)
        return EXIT_SOFT
    marker = backup_dir / "verify-status"
    if marker.exists():
        marker.unlink()
        print(f"verify-tree: cleared marker in {backup_dir.name}", file=sys.stderr)
    return EXIT_GREEN


def check_for_blocking_marker() -> tuple[int, str]:
    """
    Used by the gt-submit-sizing hook.

    Returns (exit_code, message):
      0 — no recent snapshot OR latest is passed
      2 — latest snapshot (within RECENT_WINDOW_SECONDS) is pending or failed
    """
    backup_dir = find_latest_snapshot()
    if backup_dir is None:
        return (0, "")
    age = time.time() - backup_dir.stat().st_mtime
    if age > RECENT_WINDOW_SECONDS:
        return (0, "")
    marker = read_marker(backup_dir)
    if marker is None:
        return (0, "")
    if marker == STATUS_PASSED:
        return (0, "")
    return (2, f"{backup_dir} status={marker}")


def cmd_hook_check(args) -> int:
    """Hidden subcommand used by the hook to check for blocking markers."""
    code, msg = check_for_blocking_marker()
    if code != 0:
        print(f"verify-tree: BLOCKING — latest restructure snapshot is {msg}",
              file=sys.stderr)
        print("  Run: python3 ~/.claude/skills/graphite/scripts/verify-tree.py verify",
              file=sys.stderr)
        print("  Or if the drift is intentional: verify --accept-drift \"<reason>\"",
              file=sys.stderr)
        print("  Or if aborting the restructure: verify-tree.py clear",
              file=sys.stderr)
    return code


def main():
    parser = argparse.ArgumentParser(
        description="Tree-hash integrity guardrail for Graphite stack restructures",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_snap = sub.add_parser("snapshot", help="Record tree SHAs before a restructure")
    p_snap.add_argument("--tip", metavar="BRANCH",
                        help="Snapshot from an arbitrary branch's perspective "
                             "(walks its parent chain down to trunk) without "
                             "requiring checkout. Useful when sitting at the "
                             "bottom of a stack — pass the real tip to record "
                             "every branch in the chain.")
    p_snap.set_defaults(func=cmd_snapshot)

    p_ver = sub.add_parser(
        "verify",
        help="Verify tip tree SHA AND per-branch PR diffs match latest snapshot",
    )
    p_ver.add_argument("--backup", help="Explicit backup dir (default: latest)")
    p_ver.add_argument("--accept-drift", metavar="REASON",
                       help="Accept drift with a written reason (for splits / mechanical)")
    p_ver.add_argument("--tip-only", action="store_true",
                       help="Only verify the tip tree SHA (skip per-branch PR content check)")
    p_ver.add_argument("--pr-content", action="store_true",
                       help="Only verify per-branch PR diffs (skip tip tree check)")
    p_ver.set_defaults(func=cmd_verify)

    p_status = sub.add_parser("status", help="Show latest snapshot + verify state")
    p_status.set_defaults(func=cmd_status)

    p_clear = sub.add_parser("clear", help="Clear the latest snapshot's marker")
    p_clear.set_defaults(func=cmd_clear)

    p_hook = sub.add_parser("hook-check",
                            help="(internal) Used by gt-submit-sizing hook")
    p_hook.set_defaults(func=cmd_hook_check)

    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except subprocess.CalledProcessError as e:
        print(f"verify-tree: command failed: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(EXIT_HARD)
    except KeyboardInterrupt:
        print("\nverify-tree: interrupted.", file=sys.stderr)
        sys.exit(EXIT_HARD)


if __name__ == "__main__":
    main()
