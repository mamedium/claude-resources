---
name: graphite
description: Manage stacked PRs with Graphite CLI (gt). Use when the user wants to create stacked branches, submit PRs, sync stacks, manage branch dependencies, or analyse/restructure oversized stack PRs. Triggers on "stack", "stacked PR", "graphite", "gt", "submit stack", "restructure stack", "split stack".
argument-hint: [status|create|submit|sync|restack|log|analyse|restructure]
---

# Graphite - Stacked PRs

Manage stacked PRs using the Graphite CLI (`gt`). This skill wraps `gt` commands for creating, submitting, and syncing branch stacks.

## 🚨 Draft-by-default rule (MANDATORY)

**Every `gt submit` MUST include `--draft` unless the user explicitly says "publish", "ready for review", or "not draft".**

Rationale: PRs should land in draft state by default so the user can review + polish the description/title before opening them for team review. Accidentally creating a non-draft PR pings reviewers prematurely and pollutes their queue.

### ⚠️ `--publish` and `--draft` are MUTUALLY EXCLUSIVE (gt >= late 2025)

Recent versions of Graphite reject `gt submit --publish --draft` with:
```
ERROR: Can't use both --publish and --draft flags in one command
```

**What this means**:
- `--draft` alone: pushes branches to GitHub AND creates draft PRs (supersedes `--publish`)
- `--publish` alone: pushes branches AND creates PRs as non-draft (ready for review)
- Passing both: hard error, nothing happens

**The old "always use --publish" guidance is DEAD.** `--draft` now handles the push + PR creation on its own. If you still try `--publish --draft`, `gt` blocks the command.

**Correct default**:
```bash
gt submit --no-interactive --draft
gt submit --no-interactive --stack --draft
```

**Only when the user explicitly says publish/ready**:
```bash
gt submit --no-interactive --publish
gt submit --no-interactive --publish --stack
```

**Only drop `--draft` if the user says one of**:
- "publish the PR" / "publish as ready"
- "mark as ready for review"
- "undraft the PR"
- "not draft" / "not as draft"

**If you accidentally submit without `--draft`** (or inherit a non-draft PR created before this rule was in place):
```bash
gh pr ready <pr-number> --undo   # converts to draft
```

**Verification before any `gt submit`**:
1. Confirm the command includes `--draft` (or the user explicitly approved otherwise)
2. After submit, run `gh pr view <num> --json isDraft` on newly created PRs to verify
3. If any are non-draft against the rule, immediately `gh pr ready --undo` them

## Prerequisites
- Graphite CLI installed: `npm install -g @withgraphite/graphite-cli`
- Authenticated: `gt auth --token <token>` (get token from https://app.graphite.dev/activate)
- Repo initialized: `gt init --trunk <trunk-branch>` (usually `dev` or `main`)

## Quick Reference

| User says | Command |
|-----------|---------|
| "show the stack" | `gt log` |
| "create a new branch" | `gt create <name> -m "commit message"` |
| "submit/push PRs" | `gt submit --no-interactive --draft` (draft by default — see top of file) |
| "submit as ready for review" | `gt submit --no-interactive --publish` (only when user explicitly says publish/ready) |
| "sync with trunk" | `gt sync --no-interactive` |
| "restack branches" | `gt restack --no-interactive` |
| "track existing branch" | `gt track --parent <parent> --no-interactive` |
| "switch to branch" | `gt checkout <branch>` |
| "move to parent/child" | `gt up` / `gt down` |
| "what branch am I on" | `gt branch info` |
| "analyse stack size" | `python3 ~/.claude/skills/graphite/scripts/analyse.py stack` |
| "restructure stack" / "split stack" | See [Stack Sizing & Restructure](#stack-sizing--restructure) below |
| "fold stack" / "collapse stack" | See [Fold Stack](#fold-stack) below |

**Heads-up**: a PreToolUse hook (`~/.claude/scripts/hooks/gt-submit-sizing.js`) intercepts every `gt submit` and runs the analyser. If a PR in the stack breaches the hard size limit, the submit is blocked. See the section below for thresholds, the mechanical-change escape hatch, and the override flow.

## Commands

### Viewing Stack

```bash
# Show full stack visualization (like git log but for stacks)
gt log

# Show just the current branch info
gt branch info

# List all tracked branches
gt branch list
```

### Creating Branches (Stacking)

```bash
# Create a new branch on top of current (with staged changes)
gt create <branch-name> -m "commit message" --no-interactive

# Create empty branch (no commit)
gt create <branch-name> --no-interactive

# Track an existing git branch into the stack
gt track --parent <parent-branch> --no-interactive
```

### Submitting PRs

```bash
# DEFAULT — draft-by-default rule applies (see top of file)
# `--draft` pushes AND creates draft PRs on its own; do NOT combine with --publish
gt submit --no-interactive --draft

# Submit just the current branch as a draft
gt submit --no-interactive --branch <branch> --draft

# Submit the whole stack as drafts
gt submit --no-interactive --stack --draft

# Submit with custom PR title and body (draft)
gt submit --no-interactive --draft --title "PR title" --body "PR body"

# Submit as ready for review (ONLY when user explicitly says publish/ready)
gt submit --no-interactive --publish
gt submit --no-interactive --publish --stack
```

**Important**: Always use `--no-interactive`. For the PR state flag:
- `--draft` (default): pushes branches AND creates draft PRs. Do NOT combine with `--publish` — gt rejects the combo with `ERROR: Can't use both --publish and --draft flags in one command`.
- `--publish`: pushes branches AND creates non-draft PRs. Use only when the user explicitly asks for ready-for-review.
- `--no-interactive`: prevents interactive prompts that block CLI.

### Syncing and Restacking

```bash
# Sync with remote trunk (fetch + rebase)
gt sync --no-interactive

# Restack all branches (rebase stack after changes)
gt restack --no-interactive

# After resolving merge conflicts during restack
gt continue
```

### Navigation

```bash
# Move up the stack (to child branch)
gt up

# Move down the stack (to parent branch)
gt down

# Move to the bottom of the stack
gt bottom

# Move to the top of the stack
gt top

# Checkout a specific branch
gt checkout <branch>
```

### Branch Management

```bash
# Rename current branch
gt branch rename <new-name>

# Delete current branch (untrack + delete)
gt branch delete --no-interactive

# Fold current branch into parent (squash)
gt fold --no-interactive

# Modify current branch's parent
gt branch reparent --on <new-parent> --no-interactive
```

### Amending and Committing

```bash
# Amend the current commit (add staged changes)
gt modify --no-interactive

# Create a new commit on the current branch
gt commit create -m "message"
```

## Workflow: Phase-Based Stacked PRs

For multi-phase feature work (like mobile app phases):

```bash
# 1. Start from trunk
gt sync --no-interactive

# 2. Create Phase 0 branch
gt create phase-0-foundation -m "feat: phase 0 foundation" --no-interactive

# 3. Work on Phase 0, commit as needed
git add . && gt modify --no-interactive
# or
gt commit create -m "feat: add shared components"

# 4. Create Phase 1 branch (stacks on Phase 0)
gt create phase-1-core -m "feat: phase 1 core workflow" --no-interactive

# 5. Work on Phase 1...

# 6. Submit entire stack as PRs (draft by default — see top of file)
gt submit --no-interactive --stack --draft
```

## Retroactive Branch Splitting

To split an existing branch into a stack:

```bash
# 1. Create branches at specific commits
git branch phase-0 <commit-hash>
git branch phase-1 <commit-hash>

# 2. Track them in order
git checkout phase-0
gt track --parent dev --no-interactive

git checkout phase-1
gt track --parent phase-0 --no-interactive

# 3. Delete the original branch
git branch -D original-branch

# 4. Submit (draft by default — see top of file)
gt submit --no-interactive --stack --draft
```

## PR Description Format

When submitting PRs, Graphite auto-generates descriptions from commit messages. To customize:

```bash
gt submit --no-interactive --draft \
  --title "feat(expo): Phase 0 - Foundation (ENG-262)" \
  --body "$(cat <<'BODY'
## Summary
Foundation layer for mobile field technician experience.

## Changes
- Restructured tab navigation to 5 tabs
- Added shared reusable components
- Extended theme with invoice/quote status colors

## Test plan
- Typecheck passes: `pnpm typecheck --filter expo-app`
- Biome passes: `npx biome check`
BODY
)"
```

## Trunk Configuration

This repo uses `dev` as trunk:
```bash
gt init --trunk dev
```

## Tips
- Always use `--no-interactive` to prevent blocking prompts
- Run `gt sync --no-interactive` before starting new work
- After force-push by Graphite, dependents auto-restack
- `gt log` is the best way to see your current stack state
- Use `gt continue` after resolving conflicts during restack

## Fold Stack

Collapse an entire stacked PR series into a single branch/PR. Useful when reviewers prefer one big PR over many small ones, or when the stack has grown unwieldy and individual PR review history is no longer worth preserving.

### Pre-fold checklist

1. **Sync & restack** - `gt sync --no-interactive` then `gt restack --no-interactive` (resolve any conflicts)
2. **Backup ALL branches in the stack** - local + remote, so every branch is recoverable:
   ```bash
   # For each branch in the stack (bottom to top):
   for branch in user/eng-XXX user/eng-XXX-part2 ...; do
     backup_name="backup/${branch#user/}"
     git branch -f "$backup_name" "$branch"
   done
   # Push all backups to remote in one go
   git push origin backup/eng-XXX backup/eng-XXX-part2 ... --force
   ```
3. **Verify stack state** - `gt log short` to confirm the branches you're about to fold

### Fold workflow

`gt fold` merges the current branch **down into its parent** (not upward). After folding, you land on the parent branch with the combined commits. Repeating from the top collapses the whole stack into the base branch.

```bash
# 1. Navigate to the top of the stack
gt top --no-interactive

# 2. Fold each branch into its parent (repeat until one branch above trunk)
# --close auto-closes the redundant PR on GitHub
# --keep (-k) keeps the current branch name instead of the parent's
gt fold --no-interactive --close
gt fold --no-interactive --close
# ... keep going until one branch remains above trunk

# 3. Squash all commits into one clean commit
# Include ALL ticket IDs from the folded stack in the message
gt squash -m "feat(scope): description [ENG-XXX][ENG-YYY][ENG-ZZZ]" --no-interactive

# 4. Submit the single PR
# NOTE: draft PRs skip CI in this repo. If you need CI to run, use --publish
# then convert to draft after CI passes: gh pr ready <num> --undo
gt submit --no-interactive --publish
```

### Scripted version (non-interactive loop)

```bash
gt top --no-interactive
while true; do
  parent=$(gt parent 2>/dev/null || echo "")
  if [[ "$parent" == "dev" ]] || [[ "$parent" == "main" ]] || [[ -z "$parent" ]]; then break; fi
  gt fold --no-interactive --close
done
gt squash --no-edit --no-interactive
# Use --publish so CI runs; convert to draft after if needed
gt submit --no-interactive --publish
```

### Flags

| Flag | Effect |
|------|--------|
| `--keep` (`-k`) | Keep the current branch's name instead of the parent's |
| `--close` (`-c`) | Close the associated PR on GitHub when folding |

### Gotchas

- **Branch name**: without `--keep`, folding always keeps the parent's name. After folding the whole stack you end up on the base branch (e.g. `user/eng-649`). Use `--keep` on the first fold if you want to preserve the tip branch name.
- **Draft PRs skip CI**: this repo's CI only runs on ready-for-review PRs. After fold + submit, use `--publish` to trigger CI, then `gh pr ready <num> --undo` to convert back to draft if needed.
- **Codex re-reviews**: folding triggers a new Codex review on the combined diff. Comments are likely repeats of already-triaged items from individual PRs - triage before acting.

### Tradeoffs

| Pros | Cons |
|------|------|
| Single CI run, no cascading type errors | Loses individual PR review history |
| Clean single commit on trunk | Large diff may be harder to review |
| No more restack/sync overhead | Graphite warns about sync pitfalls |
| Simpler merge queue | Can't land partial progress incrementally |

### Recovery

If the fold goes wrong, restore from the backups:
```bash
# Restore any individual branch
git checkout -B user/eng-XXX backup/eng-XXX
```

### Cleanup after merge

Once the folded PR is merged, delete all backup branches:
```bash
# Remote
git push origin --delete $(git branch -r | grep 'origin/backup/' | sed 's|origin/||')
# Local
git branch -D $(git branch | grep 'backup/')
```

## Stack Sizing & Restructure

Stack PRs are size-checked before every `gt submit` by a PreToolUse hook. The hook runs `analyse.py stack`, blocks on hard breach, and lets soft warnings through with a printed warning. See `~/.claude/CLAUDE.md` for the full sizing rule.

### Thresholds

| Level | Effective lines | Files | Action |
|---|---|---|---|
| ✅ Green | ≤ 400 | ≤ 15 | Submit |
| ⚠️ Soft | 401–700 | 16–20 | Hook warns, allows submit |
| 🚨 Hard | > 700 | > 20 | Hook blocks |

Effective lines = `additions_non_excluded + (deletions_non_excluded × 0.3)`, with a `× 0.15` floor for deletion-heavy PRs. Excluded paths: `node_modules`, `ios`, `android`, lockfiles, generated files, snapshots, build output.

### Mechanical-change escape hatch

For renames, codemods, icon swaps — anything where the diff is large but mechanical — add a commit trailer to any commit on the branch:

```
Mechanical-Change: true
```

The trailer survives restacks and is reviewable in `git log`. Thresholds become soft 1500 / hard 3000.

### Content integrity guardrail (verify-tree.py)

**Why this exists**: `gt track --parent` + `gt restack` + `gt split` can silently drop commits or mis-resolve conflicts, leaving a stack whose topology looks fine but whose content no longer matches the original. A reviewer may not notice until CI breaks or a missing feature is reported.

**How it works**: Every git commit points to a tree object (a hash of the entire worktree state). Two commits with different SHAs but identical content share the same tree SHA. So "content preserved" reduces to "stack tip tree SHA unchanged". `verify-tree.py` snapshots tree SHAs before the restructure and diffs them after.

**Mandatory in every restructure** (wired into the steps below):

1. **Before any mutation** — `python3 ~/.claude/skills/graphite/scripts/verify-tree.py snapshot`
   - Records tree SHAs for every branch in the stack
   - Tags HEAD as `backup/pre-restructure-<timestamp>` for rollback
   - Writes a `pending` marker — the gt-submit-sizing hook will BLOCK `gt submit` until verify passes
2. **After all restructure ops, before `gt submit`** — `python3 ~/.claude/skills/graphite/scripts/verify-tree.py verify`
   - Recomputes the tip tree SHA and compares to the recorded original
   - On match: prints `CONTENT PRESERVED`, flips the marker to `passed`, unblocks submit
   - On mismatch: prints `CONTENT DRIFT DETECTED` with a `git diff --stat`, writes `failed`, hook stays blocked
3. **Status check** — `python3 ~/.claude/skills/graphite/scripts/verify-tree.py status`
4. **Abort a restructure** — `python3 ~/.claude/skills/graphite/scripts/verify-tree.py clear` (removes the marker without verifying)

**Legitimate drift exceptions** (must be manually acknowledged):

- **Mechanical trailer commits** (`Mechanical-Change: true`) — they add real content, so the tip tree legitimately differs.
- **PR splits** — after `gt split`, the original tip and new tip will differ by construction. The correct check is "union of split branches' content == original branch's content", which is a manual inspection step. Do it by checking out each split branch and diffing files against the pre-split backup tag.

To acknowledge drift and unblock submit:
```bash
python3 ~/.claude/skills/graphite/scripts/verify-tree.py verify --accept-drift "<reason>"
```
The reason is written into the marker file for the audit trail.

**Hook integration**: `~/.claude/scripts/hooks/gt-submit-sizing.js` calls `verify-tree.py hook-check` before the size check. If the most recent snapshot (within 6 hours) is `pending` or `failed`, submit is blocked with a hard exit.

### Subcommands (analyse.py)

| Command | What it does |
|---|---|
| `analyse.py stack` | Walk the current stack via `.git/.graphite_cache_persist`, print verdict table, exit 0/1/2 (green/soft/hard). The hook calls this. |
| `analyse.py snapshot` | Back up the stack to `~/.claude/backups/graphite-stacks/<branch>-<ts>/`. Captures `git bundle` of all branches PLUS Graphite metadata files (`.graphite_cache_persist`, `.graphite_metadata.db`, `.graphite_pr_info`, `.graphite_repo_config`). Always run before any restructure. |
| `analyse.py plan` | For each hard-breach PR, propose a split by bucketing files by their first 2 path segments. Plain text output for review. |
| `analyse.py override "<reason>"` | Write a one-shot marker file at `/tmp/gt-sizing-override-<HEAD-sha>` so the next `gt submit` bypasses the hook. The marker is auto-consumed after one use. |
| `analyse.py gc` | Delete backup directories older than 30 days. |
| `analyse.py restore <backup-dir>` | (Stub — task 7.) Run the snapshot's `restore.sh` manually for now. |

### Restructure workflow

When the hook blocks a `gt submit` (or whenever a stack feels too big to review), follow these steps:

1. **Snapshot (bundle)** — `python3 ~/.claude/skills/graphite/scripts/analyse.py snapshot`. Always first. Captures `git bundle` + all four Graphite metadata files. The backup includes a `restore.sh` you can run if anything goes wrong.

2. **Snapshot (tree hashes)** — `python3 ~/.claude/skills/graphite/scripts/verify-tree.py snapshot`. Records tree SHAs for every branch and writes a `pending` marker. The gt-submit-sizing hook will now BLOCK `gt submit` until step 7 passes. See [Content integrity guardrail](#content-integrity-guardrail-verify-treepy) for the rationale.

3. **Analyse** — `python3 ~/.claude/skills/graphite/scripts/analyse.py stack`. Confirms which PRs breach the hard limit and which are soft.

4. **Plan** — `python3 ~/.claude/skills/graphite/scripts/analyse.py plan`. Proposes how to split each hard-breach PR by file path bucket. Output is plain text — read it, decide if the proposed boundaries make sense.

5. **Approve** — present the plan to the user via AskUserQuestion. Do NOT execute without explicit approval.

6. **Execute** — run `gt split --by-file <pathspec>` for each proposed split, then `gt restack --no-interactive`. **Important:** `gt split` is interactive by default; only `--by-file` is non-interactive. For commit/hunk splits, print the exact `gt split --by-commit` command and wait for the user to run it manually, then resume after.

7. **Verify content** — `python3 ~/.claude/skills/graphite/scripts/verify-tree.py verify`. If the stack was NOT split (e.g. pure reparent/restack), this should print `CONTENT PRESERVED` and unblock submit. If you DID split (tip tree legitimately changes), manually diff each split branch against the `backup/pre-restructure-<ts>` tag, then run `verify-tree.py verify --accept-drift "split <n> PRs: <summary>"` to acknowledge and unblock.

8. **On any failure** — print both recovery commands (`bash <backup-dir>/restore.sh` for the bundle snapshot, or `git reset --hard backup/pre-restructure-<ts>` for the tree-hash snapshot) and stop. Do not try to recover automatically.

### Override flow (genuine one-offs)

When a PR is genuinely a one-off that can't be sensibly split (rare):

1. User says: "submit anyway, reason: <reason>"
2. Run: `python3 ~/.claude/skills/graphite/scripts/analyse.py override "<reason>"` — this writes a one-shot marker file matching HEAD's SHA.
3. Run `gt submit --no-interactive --draft` (or `--publish` if the user explicitly said ready-for-review). The hook lets it through (the marker is consumed).
4. After submit, append the reason to each offending PR body for the paper trail:
   ```bash
   gh pr edit <n> --body-append "**Override reason**: <reason>"
   ```

The override is **per-commit** (tied to HEAD SHA), so it doesn't persist across new commits.

### Why this exists

Reviewers tap out at ~1000-line PRs. The historical ENG-649 stack produced two such PRs (#3330 at 1003 additions, #3332 at 1071) even after a manual restructure. The hook + restructure subcommand prevent that recurring without manual vigilance. See `~/.claude/plans/precious-foraging-church.md` for the design rationale.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "not tracked" error | Run `gt track --parent <parent> --no-interactive` |
| Conflicts during restack | Resolve conflicts, `git add`, then `gt continue` |
| Wrong parent | `gt branch reparent --on <correct-parent> --no-interactive` |
| Auth expired | `gt auth --token <token>` from https://app.graphite.dev/activate |
| Out of sync | `gt sync --no-interactive` then `gt restack --no-interactive` |
| Hook blocks `gt submit` on hard breach | Run `analyse.py plan`, then `/graphite restructure`, or use the override flow |
| Hook fails to find Graphite cache | Branch isn't Graphite-tracked (no entry in `.graphite_cache_persist`) — run `gt track --parent <parent>` |
| Hook blocks `gt submit` with "unresolved content-integrity state" | Run `verify-tree.py verify`. If drift is intentional: `verify --accept-drift "<reason>"`. If aborting the restructure: `verify-tree.py clear`. |
