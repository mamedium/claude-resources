# claude-resources

Personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills — version-controlled and symlinked into `~/.claude/skills/`.

## 📦 Skills

| Skill | Trigger | What it does |
|-------|---------|-------------|
| **codespace-dev** | `/codespace-dev` | Start, stop, or sync dev servers on a GitHub Codespace. Reads config from a yaml file — no hardcoded values. |
| **daily** | `/daily` | Reviews your daily note, gathers Slack context, updates checkboxes, generates tomorrow's file, and optionally posts to Geekbot. |
| **generate-beads** | `/generate-beads` | Turns an approved Claude plan into OpenSpec proposals and Beads issues with full cross-referencing. |

## 🚀 Quick Start

```bash
git clone git@github.com:mamedium/claude-resources.git
cd claude-resources
./setup.sh
```

The setup script will:

1. Show available skills and let you pick which to install
2. Create symlinks from `~/.claude/skills/{name}` → this repo
3. For `codespace-dev`, auto-detect your codespace and write the config

Then start a new Claude Code session — your skills are ready to use.

## 🗑️ Uninstall

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
│   └── SKILL.md
└── generate-beads/
    └── SKILL.md
setup.sh                  # interactive installer
uninstall.sh              # cleanup
```
