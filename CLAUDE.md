# claude-resources

Public collection of Claude Code skills. All content must be safe for public repos.

## Structure

- `skills/` — Claude Code skill definitions (SKILL.md files)
  - `adr/` — Architecture decision records
  - `axiom/` — Axiom observability queries
  - `browser-test/` — Local Playwright browser testing runner
  - `codespace-dev/` — Manage dev servers on GitHub Codespaces (config-driven via yaml)
  - `create-skill/` — Scaffold new skills from MCP server repos or APIs
  - `generate-beads/` — Generate OpenSpec proposals and Beads issues from approved plans
  - `git-stage/` — Smart staging and conventional commits
  - `git-worktree/` — Git worktree setup with env files and deps
  - `graphite/` — Stacked PR management with Graphite CLI
  - `gsheets/` — Google Sheets read/write/format
  - `hotfix/` — Cherry-pick merged dev PRs to main
  - `langfuse/` — Langfuse LLM observability queries
  - `linear/` — Linear project management
  - `mac-health/` — macOS RAM and disk health inspector
  - `review/` — Two-pass monorepo-aware code review
  - `sentry/` — Sentry error tracking and performance
  - `slack/` — Slack workspace interaction
  - `stack-pr/` — Stacked PR workflows
  - `tdd-workflow/` — TDD RED-GREEN-REFACTOR cycle
  - `team-debate/` — Multi-agent structured debate
- `setup.sh` — Interactive installer: picks skills, creates symlinks to `~/.claude/skills/`
- `uninstall.sh` — Removes symlinks and optionally config

## How it works

Skills are symlinked from `~/.claude/skills/{name}` to this repo. Run `setup.sh` to install.

Config-driven skills (like `codespace-dev`) read from `~/.config/claude-resources/` instead of hardcoding values. If the config file is missing, the skill prompts the user for values and writes it.

## Public repo rules

- No hardcoded API keys, tokens, secrets, or credentials
- No personal identifiable information (emails, Slack IDs, real user IDs, org names)
- No company-specific code patterns, internal URLs, or project names
- Use `CXXXXXXXXXX`, `UXXXXXXXXXX`, `ENG-123`, `username`, `my-org` as placeholders in examples
- Mark customization points with `<!-- CUSTOMIZE: ... -->` comments
- `.gitignore` blocks `.tokens.json`, `context.md`, `.env`, `node_modules/`, `.pw-profile/`
