# claude-resources

Personal Claude Code skills and configuration, centralized with version control.

## Structure

- `skills/` — Claude Code skill definitions (SKILL.md files)
  - `codespace-dev/` — Manage dev servers on GitHub Codespaces (config-driven via yaml)
  - `daily/` — Daily note review, update, and next-day generation
  - `generate-beads/` — Generate OpenSpec proposals and Beads issues from approved plans
- `setup.sh` — Interactive installer: picks skills, creates symlinks to `~/.claude/skills/`
- `uninstall.sh` — Removes symlinks and optionally config

## How it works

Skills are symlinked from `~/.claude/skills/{name}` to this repo. Run `setup.sh` to install.

`codespace-dev` reads its configuration from `~/.config/claude-resources/codespace-dev.yaml` instead of hardcoding values. If the config file is missing, the skill prompts the user for values and writes it.
