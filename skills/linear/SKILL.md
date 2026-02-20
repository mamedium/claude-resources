---
name: linear
description: Linear project management — issues, projects, cycles, labels, comments, teams, and workflow states. Use when the user wants to interact with Linear, manage issues, check project status, or track work.
allowed-tools: Bash, Read, Edit, Write
---

# Linear Integration

Full Linear workspace management via GraphQL API. ~30 commands across 8 groups.

> Paths below use `{base}` as shorthand for this skill's base directory, which is provided automatically via the "Base directory for this skill" context injected at the top of the prompt when the skill loads. Construct the full path from that value — do NOT rely on environment variables.

---

<!-- BEGIN WORKSPACE INIT -->
> **STOP — Run `/linear init` before doing anything else.**
>
> This block means the workspace context has not been embedded yet. The user's first Linear command each session should be `/linear init`. When invoked:
>
> 1. Check if `{base}/context.md` exists. If not, run: `python3 {base}/scripts/linear.py setup`
> 2. Read the contents of `{base}/context.md`.
> 3. Edit this SKILL.md file: replace everything from `<!-- BEGIN WORKSPACE INIT -->` to `<!-- END WORKSPACE INIT -->` (inclusive) with the contents of context.md.
>
> After the edit, the workspace context (teams, states, labels, members, projects) will be permanently embedded in this file. Future skill loads will see it directly with no initialization step.
>
> To refresh after workspace changes, re-run `/linear init` (which runs `python3 {base}/scripts/linear.py setup` and re-embeds the context).
<!-- END WORKSPACE INIT -->

## Usage

**Natural language mappings:**

| User says | Action |
|-----------|--------|
| "init" / first use | Read `{base}/context.md` and embed into SKILL.md (see WORKSPACE INIT block) |
| "create an issue" | `issue-create TEAM_ID --title "..." --assignee DEFAULT_USER_ID` |
| "what's assigned to me" | `my-issues` |
| "move to done" | `issue-move ID DONE_STATE_ID` |
| "show issue X" | `issue-get ENG-123` |
| "add a comment" | `comment-add ENG-123 "text"` |
| "list projects" | `project-list` |
| "search for bugs" | `issue-search "bug"` |
| "who am I" | `me` |
| "assign to someone" | `issue-assign ENG-123 USER_ID` |
| "unassign" | `issue-assign ENG-123 none` |
| "list team issues" | `issue-list --team TEAM_KEY` |
| "show workflow" | `team-states TEAM_ID` |
| "list labels" | `team-labels TEAM_ID` |
| "add a label" | `label-add ENG-123 LABEL_ID` |
| "list cycles" | `cycle-list TEAM_ID` |
| "delete the issue" | `issue-delete ENG-123` |
| "show team members" | `team-members TEAM_ID` |
| "create a project" | `project-create --name "..."` |
| "find state ID" | `resolve state "In Progress" --team TEAM_ID` |
| "find user ID" | `resolve user "name"` |

---

## Commands

```bash
LIN="python3 {base}/scripts/linear.py"
```

### Auth & Viewer

```bash
$LIN me
$LIN my-issues
$LIN my-issues --state "In Progress"
$LIN my-issues --limit 50
```

### Teams

```bash
$LIN teams
$LIN team-states TEAM_ID
$LIN team-labels TEAM_ID
$LIN team-members TEAM_ID
```

### Issues

```bash
$LIN issue-get ENG-123
$LIN issue-list --team ENG
$LIN issue-list --team ENG --state "In Progress"
$LIN issue-list --team ENG --assignee "name" --priority 2
$LIN issue-list --label "Bug" --limit 50
$LIN issue-create TEAM_ID --title "Fix login timeout"
$LIN issue-create TEAM_ID --title "Add dark mode" --description "Support dark theme" --priority 2
$LIN issue-create TEAM_ID --title "Sub-task" --parent PARENT_ID
$LIN issue-create TEAM_ID --title "Labeled" --label LABEL_ID --label LABEL_ID_2
$LIN issue-update ENG-123 --title "New title"
$LIN issue-update ENG-123 --description "Updated description" --priority 1
$LIN issue-update ENG-123 --state STATE_ID --assignee USER_ID
$LIN issue-update ENG-123 --due 2026-04-01 --estimate 3
$LIN issue-assign ENG-123 USER_ID
$LIN issue-assign ENG-123 none
$LIN issue-move ENG-123 STATE_ID
$LIN issue-search "login bug"
$LIN issue-archive ENG-123
$LIN issue-delete ENG-123
```

### Comments

```bash
$LIN comment-list ENG-123
$LIN comment-add ENG-123 "Fixed in PR #42"
$LIN comment-delete COMMENT_ID
```

### Labels

```bash
$LIN label-add ENG-123 LABEL_ID
$LIN label-remove ENG-123 LABEL_ID
$LIN label-create TEAM_ID --name "P0" --color "#EB5757"
```

### Projects

```bash
$LIN project-list
$LIN project-get PROJECT_ID
$LIN project-create --name "New Feature" --description "Ship new feature" --team TEAM_ID
$LIN project-delete PROJECT_ID
```

### Cycles

```bash
$LIN cycle-list TEAM_ID
```

### Resolve (name -> ID)

```bash
$LIN resolve team ENG
$LIN resolve state "In Progress" --team TEAM_ID
$LIN resolve label "Bug"
$LIN resolve user "name"
```

### Setup & Raw

```bash
$LIN setup
$LIN raw '{ viewer { id name } }'
$LIN raw 'query($id: String!) { issue(id: $id) { title } }' --variables '{"id": "ENG-123"}'
```

---

## Global Flags

- `--json` — Raw JSON output (available on all commands)

---

## Priority Values

| Value | Label |
|-------|-------|
| 0 | No Priority |
| 1 | Urgent |
| 2 | High |
| 3 | Medium |
| 4 | Low |

---

## Git Branch Workflow

When creating a git branch for a Linear issue, **always fetch the branch name from Linear** instead of guessing:

```bash
$LIN raw 'query { issue(id: "ENG-123") { branchName identifier } }'
```

Then use the returned `branchName` for `git checkout -b`. This ensures the branch name matches Linear's auto-linking format (e.g., `username/eng-335`).

**Never guess the branch prefix** - always query Linear for it.

---

## Important Notes

- **Default assignee**: Always use the default assignee from `context.md` when creating issues, unless the user says otherwise
- **Issue IDs**: Most commands accept both UUID (`18486b81-...`) and shorthand identifiers (`ENG-123`)
- **State/Label/User IDs**: Mutations require UUIDs. Look them up in `context.md` or use `resolve`
- **Descriptions**: Full markdown supported in issue descriptions and comments
- **Filtering**: `issue-list` supports server-side filtering by team, state, assignee, label, project, and priority
- **Pagination**: Default 25 results, use `--limit` to change (max 250)
- **Rate limits**: 5,000 requests/hr. Script auto-retries on 429s with exponential backoff
- **Raw queries**: Use `raw` command for anything not covered by built-in commands

---

## Setup

### 1. Get API Key

Go to Linear Settings > Account > Security & Access > "Personal API keys" > Create key

### 2. Configure

Add to `~/.claude/settings.json`:

```json
{
  "env": {
    "LINEAR_API_KEY": "lin_api_..."
  }
}
```

### 3. Generate Workspace Context (auto on first use)

```bash
python3 {base}/scripts/linear.py setup
```

This auto-generates `context.md` with all your workspace IDs. The contents are injected into SKILL.md automatically via dynamic content, so they're available instantly when the skill loads — no extra read step needed. Re-run anytime your workspace changes.

---

## Self-Healing Protocol

When a Linear command fails unexpectedly:

1. **Diagnose** — Read the error output, examine the script source, and check the GraphQL response
2. **Propose** — Describe the fix to the user: what's broken, why, and what change is needed
3. **Await approval** — Ask the user if they want the fix applied
4. **Apply** — Edit the broken file (script or SKILL.md) with minimal changes
5. **Verify** — Re-run the failed command to confirm the fix works

What can be self-healed:
- `scripts/linear.py` — broken commands, changed API schema, new fields
- `SKILL.md` — incorrect docs, missing commands

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| AUTHENTICATION_ERROR | Invalid or expired API key | Regenerate key in Linear settings, update LINEAR_API_KEY |
| GRAPHQL_VALIDATION_FAILED | Query references non-existent field | Check Linear API schema; self-heal the script |
| RATELIMITED | Too many requests | Script auto-retries; if persistent, wait and retry |
| "Entity not found" | Wrong issue ID | Verify the identifier exists: `issue-search "term"` |
| LINEAR_API_KEY not set | Missing env var | Add to ~/.claude/settings.json env block |
| Connection error | Network issue | Check internet connectivity |
