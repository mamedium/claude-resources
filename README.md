# claude-resources

Personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills — version-controlled and symlinked into `~/.claude/skills/`.

## What is this?

Claude Code skills are reusable prompt definitions that teach Claude how to perform specific workflows. Instead of re-explaining a complex process every session, you define it once in a `SKILL.md` file and trigger it with a slash command like `/review` or `/codespace-dev`.

This repo is a centralized collection of those skills. You clone it once, run the setup script to symlink whichever skills you want, and they're available in every Claude Code session. Version-controlled, portable, and easy to share.

## Skills

### codespace-dev

**What it does** — Manages dev servers running on a GitHub Codespace from your local machine. Syncs your local code, starts the server remotely, and forwards ports so you can test in your local browser.

**Trigger** — `/codespace-dev [mode] [app]`

**How it works:**
1. Reads config from `~/.config/claude-resources/codespace-dev.yaml` (auto-generated on first run)
2. Kills any stale SSH/port-forward processes
3. Auto-commits and pushes local changes, then pulls on the codespace
4. Starts the dev server in the background via SSH
5. Forwards the port to localhost

Supports four modes: `start` (default), `stop`, `sync` (push code without restarting), and `logs`.

**Prerequisites:**
- GitHub CLI (`gh`) installed and authenticated
- An active GitHub Codespace
- SSH access to the codespace (`gh codespace ssh` must work)

**Example usage:**
```
/codespace-dev                    # start the default app
/codespace-dev dashboard          # start a specific app
/codespace-dev sync               # push code changes without restarting
/codespace-dev stop               # kill all dev servers and port forwards
```

---

### generate-beads

**What it does** — Takes an approved Claude plan file and generates structured tracking artifacts: OpenSpec proposals (specs, tasks, design docs) and Beads issues (epic + child issues), all cross-referenced.

**Trigger** — `/generate-beads [plan-file-path]`

**How it works:**
1. Finds the most recent plan in `.claude/plans/` (or uses the path you provide)
2. Asks whether you want OpenSpec only, Beads only, or both
3. Checks existing OpenSpec state to avoid duplicates or conflicts
4. Parses the plan into a proposal, task list, optional design doc, and capability spec
5. Validates the OpenSpec output
6. Creates a Beads epic and one child issue per task section
7. Cross-references everything (plan ↔ OpenSpec ↔ Beads)

**Prerequisites:**
- OpenSpec CLI (`openspec`) installed
- Beads MCP tools or `bd` CLI available
- An approved plan file in `.claude/plans/`

**Example usage:**
```
/generate-beads                              # auto-detect latest plan
/generate-beads .claude/plans/add-auth.md    # use a specific plan file
```

---

### team-debate

**What it does** — Spawns a team of AI agents to hold a structured debate about a PR review, design decision, or any topic. Each agent takes a different role (defender, critic, devil's advocate) and a lead agent makes the final call.

**Trigger** — `/team-debate [PR-number | topic]`

**How it works:**
1. Determines the input — a GitHub PR number or a free-form topic
2. Asks how many agents you want (2, 3, or 4)
3. For PRs: pulls the diff, review comments, and inline feedback via `gh`. For topics: parses your question into debate points
4. Creates a team and spawns agents in parallel, each with a defined role:
   - **Defender** — argues in favor of the current approach
   - **Critic** — identifies flaws and proposes alternatives
   - **Devil's Advocate** (4-agent mode) — takes contrarian positions to stress-test both sides
   - **Lead** (3+ agents) — judges arguments and delivers a final verdict per point
5. Moderates 2-3 rounds of exchange, then collects verdicts
6. Presents a results table with verdicts, rationale, and (for PRs) suggested reply drafts

**Prerequisites:**
- GitHub CLI (`gh`) for PR mode
- A git repo with a remote for PR context detection

**Example usage:**
```
/team-debate 2717                            # debate feedback on PR #2717
/team-debate should we use Redis or DynamoDB for session storage?
/team-debate                                 # interactive — asks what to debate
```

### adr

**What it does** — Captures architectural decisions with context, alternatives considered, and consequences. Writes ADR files to the Obsidian vault.

**Trigger** — `/adr`

---

### axiom

**What it does** — Queries Axiom observability data: datasets, APL queries, monitors, and dashboards.

**Trigger** — `/axiom`

**Prerequisites:** `AXIOM_AUTH_TOKEN` env var

---

### browser-test

**What it does** — Local Playwright runner for browser testing, screenshots, form filling, and UI verification without MCP overhead.

**Trigger** — `/browser-test <url>`

**Prerequisites:** Node.js

---

### create-skill

**What it does** — Generates a new Claude Code skill from an MCP server repo or API. Clones the repo, learns the API surface, and scaffolds a complete skill with SKILL.md and Python CLI wrapper.

**Trigger** — `/create-skill <repo-url>`

---

### git-stage

**What it does** — Analyzes changes, excludes agent-generated files, stages, crafts a conventional commit message, and commits locally. Does not push or create PRs.

**Trigger** — `/git-stage`

---

### git-worktree

**What it does** — Creates a git worktree with env files copied and dependencies installed.

**Trigger** — `/git-worktree <branch-name>`

**Prerequisites:** pnpm

---

### graphite

**What it does** — Manages stacked PRs with Graphite CLI. Handles create, submit, sync, status, and stack restructuring for oversized stacks.

**Trigger** — `/graphite [status|create|submit|sync]`

**Prerequisites:** `gt` CLI installed and authenticated

---

### gsheets

**What it does** — Read, write, and format Google Sheets via the Sheets API v4.

**Trigger** — `/gsheets read <spreadsheet-id> Sheet1!A1:D10`

**Prerequisites:** Google auth token

---

### hotfix

**What it does** — Cherry-picks a merged dev PR to main for immediate deployment.

**Trigger** — `/hotfix <PR-number>`

**Prerequisites:** GitHub CLI (`gh`)

---

### langfuse

**What it does** — Queries Langfuse LLM observability: traces, scores, prompts, datasets, and metrics.

**Trigger** — `/langfuse traces --limit 10`

**Prerequisites:** `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` env vars

---

### linear

**What it does** — Full Linear project management: issues, projects, cycles, labels, comments, teams, and workflow states.

**Trigger** — `/linear my-issues`

**Prerequisites:** `LINEAR_API_KEY` env var

---

### mac-health

**What it does** — Read-only macOS inspector for RAM pressure, memory hogs, orphaned MCP servers, and disk-eating caches. Prints reclaim commands without executing them.

**Trigger** — `/mac-health ram` or `/mac-health storage`

---

### review

**What it does** — Two-pass monorepo-aware code review. Breadth agents find issues in parallel, then depth agents validate findings to reduce false positives.

**Trigger** — `/review 493` or `/review --staged`

**Prerequisites:** GitHub CLI (`gh`)

---

### sentry

**What it does** — Search, analyze, triage, and manage Sentry issues and performance data.

**Trigger** — `/sentry issues ORG`

**Prerequisites:** `SENTRY_AUTH_TOKEN` env var

---

### slack

**What it does** — Read channels, search messages, send/reply, manage reactions, and interact with Slack workspaces.

**Trigger** — `/slack search "deploy"`

**Prerequisites:** `SLACK_BOT_TOKEN` env var

---

### stack-pr

**What it does** — Manages branch stacks for stacked PR workflows with explicit stack definitions.

**Trigger** — `/stack-pr status`

---

### tdd-workflow

**What it does** — Test-Driven Development workflow: RED-GREEN-REFACTOR cycle with Vitest and pytest.

**Trigger** — `/tdd`

**Prerequisites:** Vitest or pytest installed

---

## Quick Start

```bash
git clone git@github.com:mamedium/claude-resources.git
cd claude-resources
./setup.sh
```

The setup script will:

1. Show available skills and let you pick which ones to install
2. Create symlinks from `~/.claude/skills/{name}` to this repo
3. For `codespace-dev`, auto-detect your codespace and write the config file

After setup, start a new Claude Code session. Your installed skills are available as slash commands — type `/skill-name` to trigger them.

Some skills (like `codespace-dev`) require a config file in `~/.config/claude-resources/`. If the config is missing on first use, the skill will either prompt you to create it or tell you what's needed.

## Uninstall

```bash
./uninstall.sh
```

Removes symlinks pointing to this repo and optionally cleans up `~/.config/claude-resources/`.

## Structure

```
skills/
├── adr/                    # architecture decision records
├── axiom/                  # Axiom observability queries
├── browser-test/           # local Playwright runner
├── codespace-dev/          # GitHub Codespace dev servers
├── create-skill/           # scaffold new skills from APIs
├── generate-beads/         # OpenSpec + Beads from plans
├── git-stage/              # smart staging + commits
├── git-worktree/           # worktree setup
├── graphite/               # stacked PR management
├── gsheets/                # Google Sheets API
├── hotfix/                 # cherry-pick to main
├── langfuse/               # LLM observability
├── linear/                 # Linear project management
├── mac-health/             # macOS RAM + disk inspector
├── review/                 # two-pass code review
├── sentry/                 # error tracking
├── slack/                  # Slack workspace interaction
├── stack-pr/               # stacked PR workflows
├── tdd-workflow/           # TDD RED-GREEN-REFACTOR
└── team-debate/            # multi-agent debates
setup.sh                    # interactive installer
uninstall.sh                # cleanup
```
