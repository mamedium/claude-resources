# claude-resources

Personal Claude Code skills, centralized with version control.

## Skills

| Skill | Description |
|-------|-------------|
| `codespace-dev` | Start, stop, or sync dev servers on a GitHub Codespace. Config-driven via yaml. |
| `daily` | Daily note review, update, and next-day generation with Slack integration. |
| `generate-beads` | Generate OpenSpec proposals and Beads issues from approved Claude plans. |

## Setup

```bash
./setup.sh
```

The script will:
1. List available skills
2. Let you pick which to install (default: all)
3. Create symlinks from `~/.claude/skills/{name}` to this repo
4. If `codespace-dev` is selected, prompt for config values and write `~/.config/claude-resources/codespace-dev.yaml`

## Uninstall

```bash
./uninstall.sh
```

Removes symlinks from `~/.claude/skills/` that point to this repo. Optionally removes the config directory.

## Structure

```
skills/
├── codespace-dev/
│   └── SKILL.md        # reads config from ~/.config/claude-resources/codespace-dev.yaml
├── daily/
│   └── SKILL.md
└── generate-beads/
    └── SKILL.md
setup.sh                # interactive installer
uninstall.sh            # cleanup
```
