# Linear — Claude Code Skill

A Claude Code skill for managing Linear issues, projects, cycles, labels, and workflows via the GraphQL API. Auto-configures to your workspace on first use.

## Features

- ~30 commands: issues, comments, labels, projects, cycles, teams, search
- Auto-discovers your workspace (teams, states, labels, members) on first use
- Default assignee set to the authenticated user
- Full markdown support in descriptions and comments
- Server-side filtering and pagination
- Raw GraphQL escape hatch for anything not covered
- Self-healing: Claude can fix the script if the API changes
- Zero dependencies beyond Python 3 stdlib

## Installation

```bash
# Via skill-manager
claude skill-manager install <repo-url>

# Manual
git clone <repo-url> ~/.claude/skills/linear
```

## Setup

1. Create a [Linear API key](https://linear.app/settings/account/security) (Personal API key)

2. Add to `~/.claude/settings.json`:
   ```json
   {
     "env": {
       "LINEAR_API_KEY": "lin_api_..."
     }
   }
   ```

3. Start using it — Claude auto-runs `setup` on first use to generate your workspace context.

## How It Works

On first use, Claude reads `SKILL.md`, notices `context.md` doesn't exist, and runs:

```bash
python3 scripts/linear.py setup
```

This queries your Linear API and generates `context.md` with all your workspace-specific IDs (teams, workflow states, labels, members, projects). This file is gitignored and never leaves your machine.

## Commands

| Group | Commands |
|-------|----------|
| Viewer | `me`, `my-issues` |
| Teams | `teams`, `team-states`, `team-labels`, `team-members` |
| Issues | `issue-get`, `issue-list`, `issue-create`, `issue-update`, `issue-assign`, `issue-move`, `issue-search`, `issue-archive`, `issue-delete` |
| Comments | `comment-list`, `comment-add`, `comment-delete` |
| Labels | `label-add`, `label-remove`, `label-create` |
| Projects | `project-list`, `project-get`, `project-create`, `project-delete` |
| Cycles | `cycle-list` |
| Utility | `resolve`, `raw`, `setup` |

All commands support `--json` for raw JSON output.

## License

MIT
