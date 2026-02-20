---
name: sentry
description: Sentry error tracking and performance monitoring. Use when the user asks about errors, exceptions, issues, stack traces, performance, traces, releases, or provides a Sentry URL. Handles searching, analyzing, triaging, and managing Sentry resources.
argument-hint: <query, issue ID, or Sentry URL>
allowed-tools: Bash, Read, Edit, Write, Agent
---

# Sentry Integration

Investigate errors, analyze performance, search events, and manage Sentry projects via the Sentry REST API.

> Paths below use `{base}` as shorthand for this skill's base directory, which is provided automatically via the "Base directory for this skill" context injected at the top of the prompt when the skill loads.

**Input**: `$ARGUMENTS`

---

## Quick Reference

```bash
SEN="python3 {base}/scripts/sentry.py"
```

### Natural Language Mappings

| User says | Command |
|-----------|---------|
| "who am I" / "check auth" | `$SEN whoami` |
| "what orgs" / "list organizations" | `$SEN orgs` |
| "list projects" | `$SEN projects ORG` |
| "list teams" | `$SEN teams ORG` |
| "latest errors" / "what's broken" | `$SEN issues ORG --query "is:unresolved" --sort date` |
| "unresolved errors" | `$SEN issues ORG --query "is:unresolved level:error"` |
| "show issue X" / Sentry URL | `$SEN issue-get ORG ISSUE_ID` |
| "stack trace for issue X" | `$SEN issue-latest ORG ISSUE_ID` |
| "events for issue X" | `$SEN issue-events ORG ISSUE_ID` |
| "who's affected by issue X" | `$SEN issue-tags ORG ISSUE_ID user` |
| "what browsers" | `$SEN issue-tags ORG ISSUE_ID browser` |
| "resolve issue X" | `$SEN issue-update ORG ISSUE_ID --status resolved` |
| "ignore issue X" | `$SEN issue-update ORG ISSUE_ID --status ignored` |
| "how many errors today" | `$SEN events ORG --fields "count()" --period 24h` |
| "errors by project" | `$SEN events ORG --fields "project" "count()" --period 24h` |
| "analyze issue X" / "root cause" | `$SEN autofix ORG ISSUE_ID` |
| "show trace" | `$SEN trace ORG TRACE_ID` |
| "list releases" | `$SEN releases ORG` |
| "list DSNs" | `$SEN dsns ORG PROJECT` |

---

## Workflow

If `$ARGUMENTS` is provided, determine the user's intent and act immediately.

1. **If it's a Sentry URL**: Extract the org slug, issue ID, or project from the URL and call the appropriate command
2. **If it's a natural language query**: Map to the right command from the table above
3. **If it's an issue ID**: Fetch details with `issue-get`, then `issue-latest` for stack trace
4. **If no arguments**: Ask what the user wants to investigate

---

## Commands

```bash
SEN="python3 {base}/scripts/sentry.py"
```

### Auth & Discovery

```bash
$SEN whoami
$SEN orgs
$SEN orgs --query "my-org"
$SEN teams ORG
$SEN projects ORG
$SEN projects ORG --query "agents"
$SEN releases ORG
$SEN releases ORG --project PROJECT
```

### Issues

```bash
$SEN issues ORG                                           # All recent issues
$SEN issues ORG --query "is:unresolved"                   # Unresolved only
$SEN issues ORG --query "is:unresolved level:error"       # Unresolved errors
$SEN issues ORG --project PROJECT                         # Specific project
$SEN issues ORG --query "is:unresolved" --sort freq       # By frequency
$SEN issues ORG --period 24h                              # Last 24 hours
$SEN issue-get ORG ISSUE_ID                               # Full issue details
$SEN issue-latest ORG ISSUE_ID                            # Latest event + stack trace
$SEN issue-events ORG ISSUE_ID                            # Event history
$SEN issue-events ORG ISSUE_ID --query "environment:production"
$SEN issue-tags ORG ISSUE_ID browser                      # Browser distribution
$SEN issue-tags ORG ISSUE_ID os                           # OS distribution
$SEN issue-tags ORG ISSUE_ID url                          # Affected URLs
$SEN issue-tags ORG ISSUE_ID user                         # Affected users
$SEN issue-tags ORG ISSUE_ID environment                  # Environments
$SEN issue-update ORG ISSUE_ID --status resolved
$SEN issue-update ORG ISSUE_ID --status ignored
$SEN issue-update ORG ISSUE_ID --assignee "username"
$SEN issue-update ORG ISSUE_ID --assignee none
```

### Events & Search

```bash
$SEN events ORG --query "level:error" --period 24h
$SEN events ORG --fields "title" "count()" --period 7d
$SEN events ORG --fields "project" "count()" --period 24h
$SEN events ORG --dataset spans --fields "transaction" "avg(duration)" --period 1h
$SEN events ORG --dataset logs --query "message:timeout" --period 24h
```

### Traces

```bash
$SEN trace ORG TRACE_ID
$SEN trace ORG TRACE_ID --period 7d
```

### AI Analysis (Seer/Autofix)

```bash
$SEN autofix ORG ISSUE_ID                                 # Start or check status
$SEN autofix ORG ISSUE_ID --restart                       # Force new analysis
$SEN autofix ORG ISSUE_ID --instruction "Focus on the database connection"
```

**Note:** First-time analysis takes 2-5 minutes. Results are cached - subsequent calls return instantly.

### Project Management

```bash
$SEN create-team ORG --name "Backend"
$SEN create-project ORG --team TEAM_SLUG --name "my-service"
$SEN create-project ORG --team TEAM_SLUG --name "my-service" --platform node
$SEN update-project ORG PROJECT --name "new-name"
$SEN update-project ORG PROJECT --platform python
$SEN dsns ORG PROJECT
$SEN create-dsn ORG PROJECT --name "Production"
```

---

## Sentry Query Syntax

The `--query` parameter for `issues` and `events` uses Sentry's search syntax:

| Query | Meaning |
|-------|---------|
| `is:unresolved` | Open issues only |
| `is:resolved` | Resolved issues |
| `level:error` | Error-level events |
| `level:fatal` | Fatal-level events |
| `environment:production` | Production environment only |
| `platform:python` | Python platform |
| `assigned:me` | Assigned to you |
| `!has:assignee` | Unassigned issues |
| `firstSeen:-24h` | First seen in last 24h |
| `lastSeen:-1h` | Active in last hour |
| `times_seen:>100` | Seen more than 100 times |
| `message:timeout` | Contains "timeout" in message |

Combine with spaces: `is:unresolved level:error environment:production`

---

## Event Fields for Aggregation

Use with `events --fields`:

| Field | Description |
|-------|-------------|
| `count()` | Total event count |
| `count_unique(user)` | Unique users affected |
| `title` | Event title/message |
| `project` | Project name |
| `timestamp` | Event time |
| `event.type` | Event type (error, transaction) |
| `level` | Error level |
| `avg(duration)` | Average span duration (spans dataset) |
| `p50(duration)` | P50 latency |
| `p95(duration)` | P95 latency |
| `p99(duration)` | P99 latency |

---

## Common Workflows

### Investigate an Error
1. `$SEN issues ORG --query "is:unresolved" --sort date` - find recent issues
2. `$SEN issue-get ORG ISSUE_ID` - get context
3. `$SEN issue-latest ORG ISSUE_ID` - get stack trace
4. `$SEN issue-tags ORG ISSUE_ID user` - check affected users
5. `$SEN autofix ORG ISSUE_ID` - get AI root cause analysis

### Check Error Trends
1. `$SEN events ORG --fields "project" "count()" --period 24h` - errors by project
2. `$SEN issues ORG --query "is:unresolved firstSeen:-24h"` - new issues today

### Debug Performance
1. `$SEN trace ORG TRACE_ID` - trace overview
2. `$SEN events ORG --dataset spans --fields "transaction" "avg(duration)" "p95(duration)" --period 1h`

### Triage
1. `$SEN issues ORG --query "is:unresolved" --sort freq` - highest frequency issues
2. `$SEN issue-update ORG ISSUE_ID --status resolved` - resolve
3. `$SEN issue-update ORG ISSUE_ID --assignee "username"` - assign

---

## Parsing Sentry URLs

When the user provides a Sentry URL, extract the org and issue ID:

- `https://sentry.io/organizations/{org}/issues/{issue_id}/` -> `issue-get {org} {issue_id}`
- `https://{org}.sentry.io/issues/{issue_id}/` -> `issue-get {org} {issue_id}`

---

## Example Query Patterns

Common investigation queries (customize for your project):

```bash
# Connection/networking errors
$SEN issues ORG --query "is:unresolved connection" --project PROJECT

# External service failures
$SEN issues ORG --query "is:unresolved timeout OR retry" --project PROJECT

# Database errors
$SEN issues ORG --query "is:unresolved mysql OR redis OR postgres" --project PROJECT

# Auth/permission errors
$SEN issues ORG --query "is:unresolved unauthorized OR forbidden" --project PROJECT
```

---

## Global Flags

- `--json` - Raw JSON output (available on all commands)
- `--limit N` - Number of results (default 25, available on list commands)

---

## Setup

### 1. Get Sentry Auth Token

Go to https://sentry.io/settings/account/api/auth-tokens/ and create a token with scopes:
- `org:read`, `project:read`, `project:write`, `team:read`, `team:write`, `event:write`

### 2. Configure

Add to `~/.claude/settings.json`:

```json
{
  "env": {
    "SENTRY_AUTH_TOKEN": "sntrys_..."
  }
}
```

For self-hosted Sentry, also set:
```json
{
  "env": {
    "SENTRY_AUTH_TOKEN": "sntrys_...",
    "SENTRY_HOST": "sentry.example.com"
  }
}
```

### 3. Verify

Run `/sentry who am I` to confirm authentication.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `SENTRY_AUTH_TOKEN not set` | Missing env var | Add to `~/.claude/settings.json` env block |
| `HTTP 401: Unauthorized` | Invalid or expired token | Regenerate at sentry.io settings |
| `HTTP 403: Forbidden` | Missing token scopes | Ensure all required scopes are set |
| `HTTP 404: Not Found` | Wrong org/project slug or issue ID | Run `orgs` then `projects ORG` to verify |
| Rate limited | Too many requests | Auto-retries with backoff; if persistent, wait |
| Connection error | Network issue | Check internet connectivity |
| Autofix timeout | First-time analysis takes 2-5 min | Re-run command to check status |

---

## Upstream Sync (Auto-Update from Source Repo)

This skill was generated from: **https://github.com/getsentry/sentry-mcp** (commit: `9077fdab`)
Source metadata: `{base}/source.json`

### On Every Skill Trigger

**Before executing the user's command**, launch a **background Agent** to check for upstream updates:

1. Read `{base}/source.json` to get the source repo URL and last known commit SHA
2. Launch a background agent (run_in_background: true) to:
   - Shallow-clone or fetch the source repo to `/tmp/skill-sync-sentry`
   - Compare latest commit with stored SHA
   - If different: analyze the changelog for API surface changes
   - **If good update** (new tools, bug fixes, additive changes): auto-update the script and SKILL.md, update source.json, return summary
   - **If bad update** (breaking changes, removals, regressions): skip changes, return reason
   - **If no changes**: return silently
3. Continue executing the user's command immediately (don't wait)
4. When the background agent completes:
   - If updated: notify user "Updated /sentry skill from upstream - <summary>"
   - If skipped: notify user "Upstream /sentry has changes but skipped - <reason>"
   - If no changes: say nothing

### Update Judgment Criteria

**GOOD (auto-apply):**
- New API endpoints/tools added (additive, non-breaking)
- Bug fixes in existing endpoint behavior
- New query parameters or fields
- Documentation revealing undocumented features

**BAD (skip and notify):**
- Existing endpoints removed or renamed
- Authentication method changed
- Required parameters changed breaking existing commands
- Response schema changes breaking table formatting

---

## Self-Healing Protocol

When a Sentry command fails unexpectedly:

1. **Diagnose** - Read error output and check the script
2. **Propose** - Describe the fix: what's broken, why, what change is needed
3. **Await approval** - Ask user before editing
4. **Apply** - Edit `{base}/scripts/sentry.py` with minimal changes
5. **Verify** - Re-run the failed command
