---
name: "Setup Worktree"
description: Copy project config files (AGENTS.md, AGENT.md, CLAUDE.local.md, openspec/) into a git worktree
category: Workflow
tags: [worktree, setup, config]
---

Copy project configuration files into a git worktree so it has the same Claude Code and OpenSpec setup as the main tree.

**Input**: The argument after `/setup-worktree` is the worktree path or name (optional).

**Steps**

1. **List worktrees to find the target**
   ```bash
   git worktree list
   ```
   Identify the main worktree (current repo root) and any other worktrees.

2. **Determine the target worktree**

   - If the user provided a path or name, match it against the worktree list.
   - If there's only one non-main worktree, use that automatically.
   - If there are multiple worktrees and no input was given, use **AskUserQuestion** to let the user pick which worktree to copy into.
   - If no worktrees exist besides the main one, tell the user and stop.

3. **Determine the source (main worktree)**

   The source is the main worktree root (the one on the primary branch). Identify it from the `git worktree list` output.

4. **Copy the config files**

   Copy these files/folders from the source worktree to the target worktree root:
   - `AGENTS.md`
   - `AGENT.md`
   - `CLAUDE.local.md`
   - `GEMINI.md`
   - `openspec/` (recursive)
   - `.claude/skills/` (recursive)
   - `.claude/commands/` (recursive)
   - `.claude/settings.local.json`

   Only copy files that exist in the source. Skip any that don't exist without erroring.

   ```bash
   # Ensure .claude directory exists in target
   mkdir -p <target>/.claude

   # For each file (example):
   cp <source>/AGENTS.md <target>/ 2>/dev/null
   cp <source>/AGENT.md <target>/ 2>/dev/null
   cp <source>/CLAUDE.local.md <target>/ 2>/dev/null
   cp <source>/GEMINI.md <target>/ 2>/dev/null
   cp -r <source>/openspec <target>/ 2>/dev/null
   cp -r <source>/.claude/skills <target>/.claude/ 2>/dev/null
   cp -r <source>/.claude/commands <target>/.claude/ 2>/dev/null
   cp <source>/.claude/settings.local.json <target>/.claude/ 2>/dev/null
   ```

5. **Copy MCP server config**

   Copy the `mcpServers` from the source project's entry in `~/.claude.json` to the target worktree's project entry:

   - Read `~/.claude.json`
   - Find the source project entry under `projects["<source-worktree-path>"]`
   - Find or create the target project entry under `projects["<target-worktree-path>"]`
   - Copy `mcpServers` from source to target
   - Write the updated JSON back to `~/.claude.json`

   Use `jq` for the JSON manipulation:
   ```bash
   SOURCE_PATH="<source-worktree-path>"
   TARGET_PATH="<target-worktree-path>"
   jq --arg src "$SOURCE_PATH" --arg tgt "$TARGET_PATH" '
     .projects[$tgt].mcpServers = (.projects[$src].mcpServers // {})
   ' ~/.claude.json > /tmp/claude.json.tmp && mv /tmp/claude.json.tmp ~/.claude.json
   ```

   If the source project entry has no `mcpServers` or it's empty, skip this step.

6. **Report what was copied**

**Output**

Summarize:
- Source worktree path
- Target worktree path
- Which files were successfully copied
- Which MCP servers were copied
- Any files that were skipped (didn't exist in source)

**Guardrails**
- Never overwrite without telling the user what will be replaced
- If the target already has these files, mention they'll be overwritten before proceeding
- Do NOT create worktrees - this skill only copies config into existing ones
