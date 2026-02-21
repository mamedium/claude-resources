# claude-resources

Personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills and commands — version-controlled and symlinked into `~/.claude/`.

## Skills

| Skill | Trigger | What it does |
|-------|---------|-------------|
| **codespace-dev** | `/codespace-dev` | Start, stop, or sync dev servers on a GitHub Codespace. Reads config from a yaml file — no hardcoded values. |
| **daily** | `/daily` | Reviews your daily note, gathers Slack context, updates checkboxes, generates tomorrow's file, and optionally posts to Geekbot. |
| **generate-beads** | `/generate-beads` | Turns an approved Claude plan into OpenSpec proposals and Beads issues with full cross-referencing. |
| **pr-review-respond** | `/pr-review-respond` | Respond to bot review comments on the current PR, resolve threads, and trigger a new review. |
| **slack-chat-to-jira** | `/slack-chat-to-jira` | Convert Slack conversations into well-structured Jira tickets with codebase investigation. |
| **sync-to-main** | `/sync-to-main` | Copy skills, commands, and openspec files from a worktree back to the main repo. |

## Commands

| Command | Trigger | What it does |
|---------|---------|-------------|
| **new-worktree** | `/new-worktree` | Create a git worktree and branch from a Jira issue key. |
| **setup-worktree** | `/setup-worktree` | Copy project config files (AGENTS.md, CLAUDE.local.md, etc.) into a worktree. |
| **openspec/proposal** | `/openspec:proposal` | Create OpenSpec proposal documents. |
| **openspec/apply** | `/openspec:apply` | Apply OpenSpec changes to the codebase. |
| **openspec/archive** | `/openspec:archive` | Archive completed OpenSpec documents. |

## Quick Start

```bash
git clone git@github.com:dodycode/claude-resources.git
cd claude-resources
./setup.sh
```

The setup script will:

1. Show available skills and let you pick which to install
2. Create symlinks from `~/.claude/skills/{name}` to this repo
3. Symlink commands from `~/.claude/commands/` to this repo
4. For `codespace-dev`, auto-detect your codespace and write the config
5. For `daily`, prompt for Slack IDs and channel config

Then start a new Claude Code session — your skills and commands are ready to use.

## Uninstall

```bash
./uninstall.sh
```

Removes symlinks pointing to this repo and optionally cleans up `~/.config/claude-resources/`.

## Structure

```
skills/
├── codespace-dev/
│   └── SKILL.md          # config: ~/.config/claude-resources/codespace-dev.yaml
├── daily/
│   └── SKILL.md          # config: ~/.config/claude-resources/daily.yaml
├── generate-beads/
│   └── SKILL.md
├── pr-review-respond/
│   └── SKILL.md
├── slack-chat-to-jira/
│   ├── SKILL.md
│   └── TEMPLATES.md
└── sync-to-main/
    └── SKILL.md
commands/
├── new-worktree.md
├── setup-worktree.md
└── openspec/
    ├── proposal.md
    ├── apply.md
    └── archive.md
setup.sh                  # interactive installer
uninstall.sh              # cleanup
```
