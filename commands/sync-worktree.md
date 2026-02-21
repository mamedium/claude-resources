---
name: "Sync Worktree"
description: Sync config files and MCP servers between a git worktree and the main worktree (either direction)
category: Workflow
tags: [worktree, sync, config]
---

Sync project configuration files between a git worktree and the main worktree. Supports both directions: main-to-worktree (initial setup / refresh) and worktree-to-main (push changes back).

**Input**: The argument after `/sync-worktree` is the worktree path or name (optional).

**Steps**

1. **Detect worktree layout**

   ```bash
   git worktree list
   ```

   Identify the main worktree (first entry) and all other worktrees.
   If no worktrees exist besides the main one, tell the user and stop.

2. **Determine the target worktree**

   - If the user provided a path or name, match it against the worktree list.
   - If there's only one non-main worktree, use that automatically.
   - If there are multiple worktrees and no input was given, use **AskUserQuestion** to let the user pick which worktree to sync.
   - The "other" worktree is the one that is NOT the main worktree.

3. **Ask for sync direction**

   Use **AskUserQuestion** to ask:

   > Which direction should we sync?

   Options:
   - **Main to Worktree** — Copy config from main into the worktree (initial setup / refresh)
   - **Worktree to Main** — Copy changes from the worktree back to main

   Based on the answer, set SOURCE and TARGET accordingly:
   - Main to Worktree: SOURCE = main worktree, TARGET = other worktree
   - Worktree to Main: SOURCE = other worktree, TARGET = main worktree

4. **Identify changes**

   Compare all syncable files/directories between SOURCE and TARGET:

   **Files to sync:**
   - `AGENTS.md`
   - `AGENT.md`
   - `CLAUDE.local.md`
   - `GEMINI.md`
   - `openspec/` (recursive)
   - `.claude/skills/` (recursive)
   - `.claude/commands/` (recursive)
   - `.claude/settings.local.json`

   For each file/directory, check what differs:
   ```bash
   # For individual files
   diff <SOURCE>/AGENTS.md <TARGET>/AGENTS.md 2>/dev/null

   # For directories
   diff -rq <SOURCE>/openspec/ <TARGET>/openspec/ 2>/dev/null
   diff -rq <SOURCE>/.claude/skills/ <TARGET>/.claude/skills/ 2>/dev/null
   diff -rq <SOURCE>/.claude/commands/ <TARGET>/.claude/commands/ 2>/dev/null
   ```

   Also check MCP server config:
   ```bash
   jq --arg src "<SOURCE_PATH>" --arg tgt "<TARGET_PATH>" '
     { source: (.projects[$src].mcpServers // {}), target: (.projects[$tgt].mcpServers // {}) }
   ' ~/.claude.json
   ```

5. **Show preview**

   Present a clear summary:
   ```
   ## Sync Preview

   Direction: Main → Worktree  (or Worktree → Main)
   Source: /path/to/source
   Target: /path/to/target

   ### Files
   - New: AGENTS.md
   - Modified: openspec/some-file.md
   - Unchanged: CLAUDE.local.md (skipping)

   ### MCP Servers
   - Will copy 3 server configs

   Ready to sync?
   ```

   If there are no differences, inform the user that everything is already in sync and stop.

6. **Ask for confirmation**

   **CRITICAL: Always show the preview and wait for user approval before syncing.**

   Ask: "Ready to sync, or would you like to adjust?"

7. **Sync files**

   After user approval, copy files from SOURCE to TARGET:

   ```bash
   # Ensure .claude directory exists in target
   mkdir -p <TARGET>/.claude

   # Individual files (only copy if they exist in source)
   cp <SOURCE>/AGENTS.md <TARGET>/ 2>/dev/null
   cp <SOURCE>/AGENT.md <TARGET>/ 2>/dev/null
   cp <SOURCE>/CLAUDE.local.md <TARGET>/ 2>/dev/null
   cp <SOURCE>/GEMINI.md <TARGET>/ 2>/dev/null
   cp <SOURCE>/.claude/settings.local.json <TARGET>/.claude/ 2>/dev/null

   # Directories (use rsync with --delete to keep in sync)
   rsync -av --delete <SOURCE>/openspec/ <TARGET>/openspec/ 2>/dev/null
   rsync -av --delete <SOURCE>/.claude/skills/ <TARGET>/.claude/skills/ 2>/dev/null
   rsync -av --delete <SOURCE>/.claude/commands/ <TARGET>/.claude/commands/ 2>/dev/null
   ```

8. **Sync MCP server config**

   Copy the `mcpServers` from the source project's entry in `~/.claude.json` to the target project entry:

   ```bash
   SOURCE_PATH="<source-worktree-path>"
   TARGET_PATH="<target-worktree-path>"
   jq --arg src "$SOURCE_PATH" --arg tgt "$TARGET_PATH" '
     .projects[$tgt].mcpServers = (.projects[$src].mcpServers // {})
   ' ~/.claude.json > /tmp/claude.json.tmp && mv /tmp/claude.json.tmp ~/.claude.json
   ```

   If the source project entry has no `mcpServers` or it's empty, skip this step.

9. **Report results**

**Output**

Summarize:
- Sync direction
- Source and target paths
- Which files were copied
- Which MCP servers were copied
- Any files that were skipped (didn't exist in source)

**Guardrails**
- Never overwrite without showing the preview and getting confirmation
- If the target already has these files, mention they'll be overwritten before proceeding
- Do NOT create worktrees — this command only syncs config between existing ones
- Does NOT commit anything — only copies files. The user must commit separately.
- Uses `--delete` for directory syncs to keep directories truly in sync
