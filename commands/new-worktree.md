---
name: "New Worktree"
description: Create a new git worktree and branch from a Jira issue key, then copy config files
category: Workflow
tags: [worktree, jira, branch, setup]
---

Create a new git worktree with a branch named after a Jira issue key, then set it up with project config files.

**Input**: The argument after `/new-worktree` is a Jira issue key (e.g., `PROJ-123`) or a full Jira URL (e.g., `https://<cloud-id>.atlassian.net/browse/PROJ-123`).

**Steps**

1. **Parse the Jira issue key**

   - If it's a URL like `https://<site>.atlassian.net/browse/PROJ-123`, extract both the base URL and the issue key
   - If it's already a key like `PROJ-123`, use it directly
   - If no input provided, use **AskUserQuestion** to ask for the Jira ticket key or URL
   - If only a bare issue key was provided (no URL), resolve the Jira base URL automatically via MCP:
     ```
     getAccessibleAtlassianResources()  → extract the site URL (e.g., https://mycompany.atlassian.net)
     ```
     If multiple sites are returned, present them via **AskUserQuestion** and let the user pick.
     This requires the Jira MCP server to be connected. If the call fails, fall back to asking the user for their Jira base URL.

2. **Determine paths**

   - Branch name: `<ISSUE-KEY>` (e.g., `PROJ-123`)
   - Worktree path: Derive from main worktree. If main is `/workspaces/monorepo`, then path is `/workspaces/monorepo-<ISSUE-KEY>-workspace`

3. **Create the worktree**

   ```bash
   git fetch origin
   git worktree add -b <branch-name> <worktree-path> origin/dev
   ```

   If the branch already exists, ask the user whether to use the existing branch or pick a new name.
   If the worktree path already exists, warn the user and stop.

4. **Copy config files**

   Copy these from the main worktree to the new worktree, skipping any that don't exist:
   ```bash
   cp <source>/AGENTS.md <target>/ 2>/dev/null
   cp <source>/AGENT.md <target>/ 2>/dev/null
   cp <source>/CLAUDE.local.md <target>/ 2>/dev/null
   cp <source>/GEMINI.md <target>/ 2>/dev/null
   cp -r <source>/openspec <target>/ 2>/dev/null
   cp -r <source>/.claude/skills <target>/.claude/ 2>/dev/null
   cp -r <source>/.claude/commands <target>/.claude/ 2>/dev/null
   cp <source>/.claude/settings.local.json <target>/.claude/ 2>/dev/null
   ```

   Make sure the `<target>/.claude/` directory exists before copying:
   ```bash
   mkdir -p <target>/.claude
   ```

5. **Copy MCP server config**

   Copy the `mcpServers` from the source project's entry in `~/.claude.json` to the new worktree's project entry:

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

6. **Report the result**

   Summarize: branch name, worktree path, files copied, MCP servers copied.
   Suggest: `cd <worktree-path>`

**Guardrails**
- Always `git fetch origin` before creating
- Base branch is always `origin/dev`
- Do NOT push the branch
- Only fetch from Jira MCP to resolve the site base URL — do NOT fetch issue details
