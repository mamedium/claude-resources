# 🧰 claude-resources

A collection of 20 reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for real dev workflows - code review, stacked PRs, observability, project management, and more.

> **What are skills?** Claude Code skills are reusable slash commands you install once and use in every session. Each skill is a prompt template that teaches Claude a specific workflow - no setup per session, no re-explaining, just `/review` and go. 🧠

## ⚡ Quick Start

**3 commands, then you're done:**

```bash
git clone git@github.com:mamedium/claude-resources.git
cd claude-resources
./setup.sh          # interactive menu - pick skills to install
```

Start a new Claude Code session. Your skills are ready as `/slash-commands`. 🎉

> **Just want one skill?** Skip the setup script:
> ```bash
> ln -s /path/to/claude-resources/skills/review ~/.claude/skills/review
> ```

### Prerequisites

Most skills only need Claude Code. Some need extra tools:

| Dependency | Skills that need it | Install |
|-----------|-------------------|---------|
| GitHub CLI (`gh`) | review, hotfix, team-debate, codespace-dev | `brew install gh` |
| Graphite CLI (`gt`) | graphite | `brew install withgraphite/tap/graphite` |
| Node.js | browser-test | `brew install node` |
| pnpm | git-worktree | `npm i -g pnpm` |
| Python 3.9+ | axiom, sentry, langfuse, slack, gsheets, linear | Usually pre-installed on macOS |

Some skills also need **env vars** for API auth (noted per skill below).

---

## 📦 Skills

### 🔍 Code Quality

| Skill | Trigger | What it does |
|-------|---------|-------------|
| [review](#-review) | `/review 493` | Two-pass code review: breadth agents find issues, depth agents validate |
| [tdd-workflow](#-tdd-workflow) | `/tdd` | RED-GREEN-REFACTOR cycle with Vitest and pytest |
| [team-debate](#%EF%B8%8F-team-debate) | `/team-debate` | Multi-agent structured debate for PR reviews or design decisions |
| [adr](#-adr) | `/adr` | Capture architecture decisions with context and alternatives |

### 🌳 Git Workflows

| Skill | Trigger | What it does |
|-------|---------|-------------|
| [graphite](#-graphite) | `/graphite submit` | Stacked PRs with Graphite CLI - create, submit, sync, restructure |
| [git-stage](#-git-stage) | `/git-stage` | Smart staging + conventional commit messages (no push) |
| [git-worktree](#-git-worktree) | `/git-worktree feature-x` | Create worktree with env files and deps installed |
| [stack-pr](#-stack-pr) | `/stack-pr status` | Branch stack management for stacked PR workflows |
| [hotfix](#-hotfix) | `/hotfix 234` | Cherry-pick a merged dev PR to main 🚑 |

### 📡 Observability & Debugging

| Skill | Trigger | What it does | Auth |
|-------|---------|-------------|------|
| [axiom](#-axiom) | `/axiom` | Query Axiom datasets with APL, monitors, dashboards | `AXIOM_AUTH_TOKEN` |
| [sentry](#-sentry) | `/sentry issues my-org` | Search and triage Sentry issues + performance | `SENTRY_AUTH_TOKEN` |
| [langfuse](#-langfuse) | `/langfuse traces` | LLM observability - traces, scores, prompts | `LANGFUSE_PUBLIC_KEY` + `SECRET_KEY` |
| [mac-health](#-mac-health) | `/mac-health ram` | macOS RAM pressure, disk usage, orphaned processes 🧹 | None |

### 📋 Project Management & Comms

| Skill | Trigger | What it does | Auth |
|-------|---------|-------------|------|
| [linear](#-linear) | `/linear my-issues` | Full Linear management - issues, projects, cycles, teams | `LINEAR_API_KEY` |
| [slack](#-slack) | `/slack search "deploy"` | Read channels, search, send messages, reactions | `SLACK_BOT_TOKEN` |
| [gsheets](#-gsheets) | `/gsheets read ID Sheet1!A1:D10` | Read, write, and format Google Sheets | Google auth token |

### 🖥️ Dev Environment

| Skill | Trigger | What it does |
|-------|---------|-------------|
| [codespace-dev](#%EF%B8%8F-codespace-dev) | `/codespace-dev` | Manage dev servers on Codespaces - sync, start, port-forward |
| [browser-test](#-browser-test) | `/browser-test url` | Local Playwright runner for screenshots and UI verification |

### 🏗️ Meta / Skill Creation

| Skill | Trigger | What it does |
|-------|---------|-------------|
| [create-skill](#%EF%B8%8F-create-skill) | `/create-skill repo-url` | Generate a new skill from any MCP server repo or API docs |
| [generate-beads](#-generate-beads) | `/generate-beads` | Generate OpenSpec proposals + Beads issues from a Claude plan |

---

## 🔎 Skill Details

### 🔍 review

> Two-pass code review that actually catches real bugs.

Spawns parallel **breadth agents** (each with a domain lens - API, database, React, security, etc.) to find issues, then spawns **depth agents** to independently validate each finding by reading the actual source code. Deduplicates, adjusts severity, and produces a structured report with P1/P2/P3 findings and concrete fix code.

```bash
/review 493                    # review PR #493
/review --staged               # review staged changes
/review --deep 493             # 🔬 deep mode: more agents + regression risk
/review 493 --post             # 📤 post results as PR comment
```

**Requires:** `gh`

---

### 🔴 tdd-workflow

> Write the test first. Then make it pass. Then make it pretty.

Enforces RED-GREEN-REFACTOR cycle. Supports Vitest and pytest.

```bash
/tdd
```

**Requires:** Vitest or pytest

---

### 🗣️ team-debate

> Get a second (and third, and fourth) opinion.

Spawns a team of AI agents to hold a structured debate. Each agent takes a role (defender, critic, devil's advocate) and a lead agent delivers final verdicts. Works with GitHub PRs or free-form topics.

```bash
/team-debate 2717              # debate PR review feedback
/team-debate Redis vs DynamoDB for session storage?
```

**Requires:** `gh` for PR mode

---

### 📝 adr

> Decisions are cheap. Forgetting why you made them is expensive.

Captures architectural decisions with context, alternatives considered, consequences, and revisit conditions. Stores in `docs/decisions/` with sequential numbering.

```bash
/adr
```

---

### 🌳 graphite

> Stacked PRs without the pain.

Handles the full lifecycle with the Graphite CLI (`gt`): create stacks, submit with auto-generated PR descriptions, sync with trunk, restack after conflicts, and restructure oversized stacks (fold, split, reorder). Includes pre-fold backup workflows and gotcha docs from real-world usage.

```bash
/graphite status               # 📊 show current stack state
/graphite submit               # 🚀 submit stack as PRs
/graphite sync                 # 🔄 sync with trunk and restack
/graphite restructure          # ✂️  fold/split an oversized stack
```

**Requires:** `gt` CLI

---

### 🔀 git-stage

> Commit messages that don't say "fix stuff".

Analyzes changes, excludes agent-generated files, stages relevant files, crafts a conventional commit message, and commits locally. Does not push or create PRs.

```bash
/git-stage
```

---

### 🌿 git-worktree

> Parallel branches without stashing your life away.

Creates a git worktree for parallel branch work. Copies `.env` files from the main worktree and installs dependencies.

```bash
/git-worktree feature-branch
```

**Requires:** pnpm

---

### 📚 stack-pr

> Branch stacks, managed.

Manages branch stacks for stacked PR workflows with explicit YAML stack definitions.

```bash
/stack-pr status
```

---

### 🚑 hotfix

> Production is down. Skip the queue.

Cherry-picks a merged dev PR to main for immediate deployment. Creates a hotfix branch, cherry-picks the merge commit, and opens a PR.

```bash
/hotfix 234
```

**Requires:** `gh`

---

### 📊 axiom

> Query your logs without leaving the terminal.

Query Axiom datasets using APL, check monitors, view dashboards, and explore metrics. Includes a customizable dataset map for quick lookups.

```bash
/axiom
```

**Requires:** `AXIOM_AUTH_TOKEN` env var

---

### 🐛 sentry

> Find the bug before the user finds you.

Search, analyze, triage, and manage Sentry issues. Supports issue queries, event inspection, release tracking, and performance trace analysis.

```bash
/sentry issues my-org
/sentry issue-get my-org ISSUE-123
```

**Requires:** `SENTRY_AUTH_TOKEN` env var

---

### 🔬 langfuse

> See what your LLM is actually doing.

Query Langfuse traces, scores, prompts, datasets, and metrics for LLM application monitoring.

```bash
/langfuse traces --limit 10
```

**Requires:** `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` env vars

---

### 🩺 mac-health

> Is it the code or is your Mac just dying?

Read-only macOS inspector. Reports memory hogs, orphaned MCP servers from prior Claude Code sessions, and disk-eating caches. Prints the exact shell commands to reclaim resources without executing them.

```bash
/mac-health ram
/mac-health storage
```

---

### 📐 linear

> Project management from your terminal.

Full Linear management: create/update issues, manage projects and cycles, query workflow states, add labels and comments, and fetch branch names for auto-linking.

```bash
/linear my-issues
/linear issue ENG-123
/linear create-issue "Fix login bug" --priority high
```

**Requires:** `LINEAR_API_KEY` env var

---

### 💬 slack

> Read Slack without opening Slack.

Read channels, search messages, send and reply to messages, manage reactions, list users, and interact with Slack workspaces.

```bash
/slack search "deploy issue"
/slack history CXXXXXXXXXX
/slack send CXXXXXXXXXX "message"
```

**Requires:** `SLACK_BOT_TOKEN` env var

---

### 📗 gsheets

> Spreadsheets, meet the command line.

Read, write, and format Google Sheets. Supports cell ranges, batch updates, sheet creation, and formatting.

```bash
/gsheets read SPREADSHEET_ID Sheet1!A1:D10
/gsheets write SPREADSHEET_ID Sheet1!A1 "value"
```

**Requires:** Google auth token

---

### 🖥️ codespace-dev

> Dev servers in the cloud, tested on localhost.

Manages dev servers running on a GitHub Codespace from your local machine. Config-driven via YAML (auto-generated on first run). Syncs code, starts the server via SSH, and forwards ports.

```bash
/codespace-dev                 # ▶️  start default app
/codespace-dev sync            # 🔄 push code without restarting
/codespace-dev stop            # ⏹️  kill all servers + port forwards
```

**Requires:** `gh`, active codespace

---

### 🎭 browser-test

> See what the user sees.

Browser testing, screenshots, form filling, and UI verification using a local Playwright instance. Runs without MCP for token efficiency.

```bash
/browser-test https://localhost:3000/login
```

**Requires:** Node.js

---

### 🏗️ create-skill

> Point it at any MCP server, get a working skill in minutes. 🪄

Scaffolds a new Claude Code skill from any MCP server repo or API documentation. Clones the repo, maps the API surface, and generates a complete `SKILL.md` + Python CLI wrapper.

```bash
/create-skill https://github.com/some-org/some-mcp-server
```

---

### 🧩 generate-beads

> From plan to tracked work in one command.

Takes an approved Claude plan and generates OpenSpec proposals (specs, tasks, design docs) and Beads issues (epic + children), all cross-referenced.

```bash
/generate-beads
/generate-beads .claude/plans/add-auth.md
```

**Requires:** OpenSpec CLI, Beads CLI or MCP

---

## ✨ Creating Your Own Skills

Use the included `/create-skill` to scaffold from any MCP server:

```bash
/create-skill https://github.com/some-org/some-mcp-server
```

Or create one manually - a skill is just a folder with a `SKILL.md`:

```
skills/my-skill/
├── SKILL.md              # required - prompt definition with frontmatter
└── scripts/              # optional - helper scripts the skill can call
    └── my_tool.py
```

**Minimal `SKILL.md`:**

```yaml
---
name: my-skill
description: What this skill does (shown in /skills list)
argument-hint: optional args hint
allowed-tools: Bash, Read, Edit, Write
---

# My Skill

Instructions for Claude go here. This is a prompt, not code.
Use `$ARGUMENTS` to reference what the user typed after the slash command.
```

Then symlink it:
```bash
ln -s /path/to/claude-resources/skills/my-skill ~/.claude/skills/my-skill
```

Or run `./setup.sh` to install everything at once.

---

## 🗑️ Uninstall

```bash
./uninstall.sh
```

Removes symlinks pointing to this repo and optionally cleans up `~/.config/claude-resources/`.

---

## 🤝 Contributing

Found a bug? Want to add a skill? PRs welcome.

**Rules for contributions:**
- No hardcoded credentials, API keys, or PII
- Use placeholders in examples: `CXXXXXXXXXX`, `ENG-123`, `my-org`, `username`
- Mark customization points with `<!-- CUSTOMIZE: ... -->` comments
- Test your skill in a fresh Claude Code session before submitting

---

Made with ☕ and [Claude Code](https://docs.anthropic.com/en/docs/claude-code).
