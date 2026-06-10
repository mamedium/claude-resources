# 🧰 claude-resources

A collection of 30 reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for real dev workflows - code review, stacked PRs, observability, project management, and more.

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
| GitHub CLI (`gh`) | review, hotfix, team-debate, codespace-dev, solve-ticket, pr-comments-triage | `brew install gh` |
| Graphite CLI (`gt`) | graphite, pr-comments-triage (optional) | `brew install withgraphite/tap/graphite` |
| OpenAI Codex CLI | codex, solve-ticket (optional) | `npm i -g @openai/codex` + `OPENAI_API_KEY` |
| Node.js | browser-test | `brew install node` |
| pnpm | git-worktree | `npm i -g pnpm` |
| Python 3.9+ | axiom, sentry, langfuse, slack, gsheets, linear | Usually pre-installed on macOS |

Some skills also need **env vars** for API auth (noted per skill below).

---

## 📦 Skills

### 🔍 Code Quality

| Skill | Trigger | What it does |
|-------|---------|-------------|
| [solve-ticket](#-solve-ticket) | `/solve-ticket ENG-123` | End-to-end ticket pipeline: analyse, plan, review, build, review again |
| [review](#-review) | `/review 493` | Two-pass code review: breadth agents find issues, depth agents validate |
| [tdd-workflow](#-tdd-workflow) | `/tdd` | RED-GREEN-REFACTOR cycle with Vitest and pytest |
| [team-debate](#%EF%B8%8F-team-debate) | `/team-debate` | Multi-agent structured debate for PR reviews or design decisions |
| [adr](#-adr) | `/adr` | Capture architecture decisions with context and alternatives |
| [codex](#-codex) | `/codex review my changes` | Delegate coding, review, and deliberation to OpenAI Codex CLI as background tasks |
| [pr-comments-triage](#%EF%B8%8F-pr-comments-triage) | `/pr-comments-triage` | Triage PR review comments - verify at source, push back on speculation |
| [security-review](#-security-review) | `/security-review` | OWASP Top 10 checklist for full-stack apps - secrets, injection, auth, XSS, infra |

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
| [mode-autopilot](#%EF%B8%8F-mode-autopilot) | `/autopilot plan.md` | Sustained autonomous execution with TDD, evidence gates, backups, self-review |
| [continuous-learning-v2](#-continuous-learning-v2) | `/instinct-status` | Project-scoped instinct system - patterns build confidence, evolve into skills |

### 🧭 Workflow & Learning

| Skill | Trigger | What it does |
|-------|---------|-------------|
| [focus](#-focus) | `/focus ENG-123` | Cross-session focus tracker - what's active, paused, or blocked |
| [learn](#-learn) | `/learn` | Capture session learnings as diagrams, TILs, decision logs, post-mortems |
| [learn-this](#-learn-this) | `/learn-this` | Distill the takeaway from a fix or review and write it where it sticks |
| [exit](#-exit) | `/exit` | Session closing ritual - finalise learnings, save a resume file, clean up |

---

## 🔎 Skill Details

### 🎫 solve-ticket

> One ticket in, one draft PR out - with the root cause actually understood.

A fixed delivery pipeline: deep-dive analysis (parallel exploration agents classify bug vs feature and find the in-codebase pattern to mirror), a TDD-shaped plan, a second-model review gate on the plan, autonomous execution with a writer + reviewer agent team, a second review gate on the generated code, then a dev smoke test + QA test plan and a draft PR. Each stage gates the next; review feedback is triaged accept/reject, never applied blindly.

```bash
/solve-ticket ENG-123                  # drive a tracked ticket end-to-end
/solve-ticket "fix the flaky logout"   # or free-text, no ticket attached
```

**Requires:** `gh` · **Optional:** the `linear` + `git-worktree` skills, a second-model reviewer CLI (falls back to fresh-context reviewer agents)

---

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

### 🤖 codex

> A second brain with a different reasoning manifold - delegate to GPT-5.5 in the background.

Wraps the OpenAI Codex CLI for non-interactive use from Claude Code. Two modes: `think` (read-only deliberation, web search, ephemeral) and `run` (full-access implementation with persisted, resumable sessions), plus a diff-aware `review` command. Every task launches in the background so Claude keeps working while Codex churns; results are collected via TaskOutput with session IDs for follow-ups. Vendored from [tomc98/claude-code-codex-skill](https://github.com/tomc98/claude-code-codex-skill) (MIT).

```bash
/codex think is this auth design scalable?
/codex review my uncommitted changes for security issues
/codex implement rate limiting for the upload endpoint
```

**Requires:** OpenAI Codex CLI (`npm i -g @openai/codex`) + `OPENAI_API_KEY` or `CODEX_API_KEY`

---

### ⚖️ pr-comments-triage

> Review bots are confidently wrong. This skill makes them prove it.

Pulls every unresolved review thread across a Graphite stack (or single PR) via GraphQL, then verifies each claim against the actual source before deciding - defaulting to push-back on speculative "might break if..." critiques while auto-escalating security and always-fix patterns. Produces a decision matrix (Accept / Reject / Defer with evidence and a drafted reply per thread) and waits for your approval before touching code, replying, or resolving anything.

```bash
/pr-comments-triage            # triage the whole current stack
/pr-comments-triage 493        # triage a single PR
```

**Requires:** `gh` · **Optional:** `gt` (Graphite) for stack workflows

---

### 🔐 security-review

> The OWASP Top 10, turned into a merge-blocking checklist.

A 10-category security checklist (secrets, input validation, SQL injection, authz, XSS, CSRF, rate limiting, data exposure, dependencies, cloud infra) with good/bad code examples and CRITICAL/HIGH/MEDIUM severity gates. Written for TypeScript-first stacks with Python services, but every category maps to any stack - swap the example tools for yours. Note: shares its trigger name with Claude Code's built-in `/security-review` plugin command - this one is a proactive checklist rather than a branch-diff review; rename the folder if you want both.

```bash
/security-review               # run the checklist against current changes
```

**Requires:** None

---

### 🌳 graphite

> Stacked PRs without the pain.

Handles the full lifecycle with the Graphite CLI (`gt`): create stacks, submit with auto-generated PR descriptions, sync with trunk, restack after conflicts, and restructure oversized stacks (fold, split, reorder). Includes pre-fold backup workflows, a cleanup procedure for closed PRs that still clutter the Graphite web UI stack view, and gotcha docs from real-world usage.

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

### ✈️ mode-autopilot

> Point it at a goal, walk away, come back to an audited summary.

Turns Claude Code into a sustained autonomous executor: it builds a verifiable task list, works through every task without stopping, and never fakes confidence - each task must clear a domain-specific evidence gate (failing-then-passing repro test for bug fixes, before/after numbers for perf, sibling citations for features) or get marked blocked. Decision forks spawn 3 parallel research agents instead of interrupting you, risky operations require a backup first, and a capped two-pass self-review spot-verifies every gate citation before the final summary.

```bash
/autopilot implement the plan in ~/.claude/plans/auth-redesign.md
/autopilot fix the flaky session-refresh test and any related races
```

**Requires:** None

---

### 🧬 continuous-learning-v2

> Your agent's mistakes become its instincts.

Captures atomic "instincts" - trigger-action pairs learned from sessions (error fixes, user corrections, repeated patterns) - as YAML files under `~/.claude/instincts/`, scoped per-project or global. Each instinct carries a confidence score that rises when confirmed and falls when contradicted; high-confidence clusters get promoted into skills, commands, or rules. Ships the mechanism only - you grow your own instincts.

```bash
/instinct-status          # list instincts for this project + globals
/instinct-export          # share instincts as YAML
/evolve                   # cluster instincts into skill/command candidates
```

**Requires:** None

---

### 🎯 focus

> Your sessions are ephemeral. Your focus shouldn't be.

Maintains a tiny markdown tracker (`~/.claude/focus/active.md`) recording what you're actively working on across sessions - active, paused, blocked (and by what), last touched, next step. A bundled bash CLI handles all reads/writes so the file never gets mangled; the skill routes `/focus`, `/pause`, `/block`, `/unblock`, `/resume` and "what am I working on?" through it. Done entries auto-prune after 7 days.

```bash
/focus                                    # show everything in flight
/focus ENG-123 "write the failing test"   # switch active task + next step
/block ENG-123 ENG-200                    # mark blocked by another ticket
```

**Requires:** None · **Optional:** SessionStart/Stop hooks for automatic updates

---

### 📚 learn

> Every session produces learnings. Most evaporate. This one writes them down.

Analyzes the current conversation and generates the applicable learning artifacts - mermaid diagrams for architecture/flow changes, atomic TIL notes for new concepts, decision logs (options, tradeoffs, "what would flip the choice"), and bug post-mortems that name the bug class explicitly. Artifacts are plain markdown saved per-ticket to a configurable notes directory (Obsidian vault or plain folder) and indexed in a MOC file.

```bash
/learn                # generate all applicable artifacts for this session
/learn postmortem     # just the bug post-mortem
/learn decision       # just the decision log
```

**Requires:** None · **Customize:** notes directory path in SKILL.md

---

### 🧠 learn-this

> Don't just fix it - make sure the next session doesn't repeat it.

After a review pushback, surprising fix, or repeated mistake, this skill deep-thinks the lesson (surface vs underlying principle, meta-patterns across findings, cost of not learning it), then classifies each lesson into exactly one durable home: the nearest project `CLAUDE.md` for codebase gotchas, Claude Code auto-memory for preferences and project state, or promotion into a brand-new skill for recurring workflows. Includes tiebreaker rules and a strict "don't over-capture" filter so memory doesn't bloat.

```bash
/learn-this                                   # distill + capture the last fix-pass
/learn-this and consider promoting to a skill # evaluate skill-worthiness too
```

**Requires:** None

---

### 🚪 exit

> End every session on purpose, not by closing the terminal.

A closing ritual for Claude Code sessions: audits which learning artifacts exist vs should exist (and fills the gaps, pairing with `/learn`), runs any custom session-end rituals you configure (the CUSTOMIZE slot ships with a spaced-repetition flashcard example), and - the killer feature - writes a **continuation file** when work is unfinished: remaining tasks, key files, decisions made, and a copy-paste resume prompt so the next session picks up exactly where this one stopped. Ends with orphaned-process cleanup and a summary table.

```bash
/exit          # close the session properly
```

**Requires:** None · **Customize:** notes directory + optional rituals in SKILL.md

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
