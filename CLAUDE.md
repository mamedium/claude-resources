# claude-resources

Public collection of Claude Code skills. All content must be safe for public repos.

## Structure

- `skills/` — Claude Code skill definitions (SKILL.md files)
  - `adr/` — Architecture decision records
  - `axiom/` — Axiom observability queries
  - `browser-test/` — Local Playwright browser testing runner
  - `codespace-dev/` — Manage dev servers on GitHub Codespaces (config-driven via yaml)
  - `codex/` — Delegate to OpenAI Codex CLI as background tasks (vendored, MIT)
  - `continuous-learning-v2/` — Project-scoped instinct system (trigger-action patterns with confidence)
  - `create-skill/` — Scaffold new skills from MCP server repos or APIs
  - `exit/` — Session closing ritual (learning artifacts, continuation file, cleanup)
  - `focus/` — Cross-session focus tracker with bundled bash CLI
  - `generate-beads/` — Generate OpenSpec proposals and Beads issues from approved plans
  - `git-stage/` — Smart staging and conventional commits
  - `git-worktree/` — Git worktree setup with env files and deps
  - `graphite/` — Stacked PR management with Graphite CLI
  - `gsheets/` — Google Sheets read/write/format
  - `hotfix/` — Cherry-pick merged dev PRs to main
  - `langfuse/` — Langfuse LLM observability queries
  - `learn/` — Capture session learnings (diagrams, TILs, decision logs, post-mortems)
  - `learn-this/` — Distill lessons into CLAUDE.md, auto-memory, or new skills
  - `linear/` — Linear project management
  - `mac-health/` — macOS RAM and disk health inspector
  - `mode-autopilot/` — Sustained autonomous execution with evidence gates
  - `pr-comments-triage/` — Verify-first triage of PR review comments
  - `review/` — Two-pass monorepo-aware code review
  - `security-review/` — OWASP Top 10 checklist for full-stack apps
  - `sentry/` — Sentry error tracking and performance
  - `slack/` — Slack workspace interaction
  - `solve-ticket/` — End-to-end ticket pipeline (analyse, plan, review gates, build, draft PR)
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
