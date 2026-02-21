---
name: sync-to-main
description: Copy openspec/, .claude/skills/, and .claude/commands/ from the current worktree to the main worktree. Use when you've created or modified skills, commands, or openspec files in a worktree and want to sync them back to the main repo.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# Sync to Main Worktree Skill

Copies `openspec/`, `.claude/skills/`, and `.claude/commands/` directories from the current worktree back to the main worktree so that new skills, commands, specs, and changes are available in the main repo.

## What This Skill Does

1. **Detects current worktree** — Determines the current working directory and the main worktree path
2. **Identifies what to sync** — Lists files in `openspec/`, `.claude/skills/`, and `.claude/commands/` that differ from the main worktree
3. **Shows a preview** — Displays what will be copied (new, modified, and deleted files)
4. **Asks for confirmation** — Waits for user approval before copying
5. **Syncs the directories** — Copies the directories to the main worktree using rsync

## Execution Steps

### Step 1: Detect Worktree Layout

```bash
# Get the main worktree path
git worktree list | head -1 | awk '{print $1}'

# Current working directory
pwd
```

If the current directory IS the main worktree, inform the user and stop — nothing to sync.

### Step 2: Identify Changes

For each directory (`openspec/`, `.claude/skills/`, and `.claude/commands/`), compare the current worktree's version against the main worktree:

```bash
# Show differences between worktree and main for openspec/
diff -rq <CURRENT_WORKTREE>/openspec/ <MAIN_WORKTREE>/openspec/ 2>/dev/null || echo "openspec/ does not exist in one or both locations"

# Show differences for .claude/skills/
diff -rq <CURRENT_WORKTREE>/.claude/skills/ <MAIN_WORKTREE>/.claude/skills/ 2>/dev/null || echo ".claude/skills/ does not exist in one or both locations"

# Show differences for .claude/commands/
diff -rq <CURRENT_WORKTREE>/.claude/commands/ <MAIN_WORKTREE>/.claude/commands/ 2>/dev/null || echo ".claude/commands/ does not exist in one or both locations"
```

### Step 3: Show Preview

Present a clear summary to the user:

```
## Sync Preview

Source: /workspaces/monorepo-SAI-XXXX-workspace
Target: /workspaces/monorepo

### openspec/
- New: openspec/new-file.md
- Modified: openspec/existing-file.md

### .claude/skills/
- New: .claude/skills/new-skill/SKILL.md
- Modified: .claude/skills/existing-skill/SKILL.md

### .claude/commands/
- New: .claude/commands/new-command.md
- Modified: .claude/commands/existing-command.md

Ready to sync?
```

If there are no differences, inform the user that everything is already in sync and stop.

### Step 4: Ask for Confirmation

**CRITICAL: Always show the preview and wait for user approval before syncing.**

Ask: "Ready to sync these to the main worktree, or would you like to adjust?"

### Step 5: Sync Directories

After user approval, copy the directories:

```bash
# Sync openspec/ (if it exists in current worktree)
rsync -av --delete <CURRENT_WORKTREE>/openspec/ <MAIN_WORKTREE>/openspec/

# Sync .claude/skills/
rsync -av --delete <CURRENT_WORKTREE>/.claude/skills/ <MAIN_WORKTREE>/.claude/skills/

# Sync .claude/commands/
rsync -av --delete <CURRENT_WORKTREE>/.claude/commands/ <MAIN_WORKTREE>/.claude/commands/
```

**Flags explained:**
- `-a` — Archive mode (preserves permissions, timestamps, etc.)
- `-v` — Verbose output
- `--delete` — Remove files in target that don't exist in source (keeps directories in sync)

### Step 6: Confirm Result

```bash
# Verify the sync
diff -rq <CURRENT_WORKTREE>/openspec/ <MAIN_WORKTREE>/openspec/
diff -rq <CURRENT_WORKTREE>/.claude/skills/ <MAIN_WORKTREE>/.claude/skills/
diff -rq <CURRENT_WORKTREE>/.claude/commands/ <MAIN_WORKTREE>/.claude/commands/
```

Report success to the user.

## Important Notes

1. **Always show preview first** — Never sync without user approval
2. **Uses `--delete` flag** — Files removed in the worktree will also be removed from the main worktree's copy. This keeps them truly in sync.
3. **Does NOT commit anything** — Only copies files. The user must commit in the main worktree separately.
4. **Works from any worktree** — Automatically detects the main worktree path via `git worktree list`.
5. **Safe to run repeatedly** — If already in sync, reports no changes needed.
