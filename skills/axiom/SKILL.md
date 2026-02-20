---
name: axiom
description: Axiom observability - query datasets, APL queries, monitors, dashboards, metrics. Use when the user asks about logs, traces, observability data, APL queries, Axiom datasets, monitors, or dashboards.
argument-hint: query "['my-dataset'] | where status == 500 | take 10"
allowed-tools: Bash, Read, Edit, Write, Agent
---

# Axiom Integration

Query and explore Axiom observability data - datasets, APL queries, monitors, dashboards, and metrics.

> Paths below use `{base}` as shorthand for this skill's base directory.

**Input**: ``

---

## Quick Reference

```bash
CMD="python3 {base}/scripts/axiom.py"
```

### Natural Language Mappings

| User says | Command |
|-----------|---------|
| "list datasets", "what datasets do we have" | `$CMD datasets` |
| "show fields for X", "what's in dataset X" | `$CMD dataset-fields <dataset>` |
| "query X", "run this APL", "search logs" | `$CMD query "<apl>"` |
| "show saved queries" | `$CMD saved-queries` **(needs token upgrade)** |
| "check monitors", "any alerts firing" | `$CMD monitors` **(needs token upgrade)** |
| "monitor history for X" | `$CMD monitor-history <id>` **(needs token upgrade)** |
| "list dashboards" | `$CMD dashboards` **(needs token upgrade)** |
| "show dashboard X" | `$CMD dashboard-get <uid>` **(needs token upgrade)** |
| "export dashboard X" | `$CMD dashboard-export <uid>` **(needs token upgrade)** |
| "query metrics", "MPL query" | `$CMD query-metrics "<mpl>"` |
| "list metrics in X" | `$CMD metrics <dataset>` |
| "show metric tags" | `$CMD metric-tags <dataset>` |
| "tag values for X" | `$CMD metric-tag-values <dataset> <tag>` |

---

## Dataset Map

<!-- CUSTOMIZE: Map your Axiom datasets here so the skill knows which dataset to query. -->

| Dataset | Service | What it logs | When to query |
|---------|---------|-------------|---------------|
| `api-prod` | API server | HTTP request/response logs | Debugging API issues |
| `api-dev` | API server (dev) | HTTP request/response logs | Debugging dev API issues |
| `workers-prod` | Background workers | Job execution logs | Debugging background job issues |
| `workers-dev` | Background workers (dev) | Job execution logs | Debugging dev job issues |

### Dataset Selection Guide

| User is debugging... | Query this dataset |
|----------------------|--------------------|
| API errors / HTTP responses | `api-prod` or `api-dev` |
| Background jobs | `workers-prod` or `workers-dev` |
| Admin dashboard issues | `admin` |
| Public API issues | `openapi` |
| External/internal agent (TS) | `external-agent` / `internal-agent` |

---

## Commands

### Datasets & Querying

```bash
# List all datasets
$CMD datasets

# List fields in a dataset
$CMD dataset-fields <dataset>

# Execute an APL query
$CMD query "['my-dataset'] | where status == 500 | take 10"
$CMD query "['logs'] | summarize count() by bin(_time, 1h)" --start "now-24h"
$CMD query "['traces'] | where duration > 1000" --start "now-1h" --end "now" --limit 100

# List saved/starred queries
$CMD saved-queries --limit 50
```

### Monitors (needs token upgrade - ask user for `monitors:read` permission)

```bash
# List all monitors and statuses
$CMD monitors

# Get check history for a monitor
$CMD monitor-history <monitor-id> --limit 10
```

### Dashboards (needs token upgrade - ask user for `dashboards:read` permission)

```bash
# List all dashboards
$CMD dashboards

# Get dashboard details
$CMD dashboard-get <uid>

# Export dashboard as JSON (for backup/transfer)
$CMD dashboard-export <uid>
```

### Metrics (MPL)

```bash
# Query metrics using Metrics Processing Language
$CMD query-metrics "`metrics-ds`:`http.request.duration` | align to 5m using avg"

# List available metrics in a dataset
$CMD metrics <metrics-dataset> --start "2026-03-11T00:00:00Z" --end "2026-03-12T00:00:00Z"

# List tags (dimensions) for filtering
$CMD metric-tags <metrics-dataset>

# List values for a specific tag
$CMD metric-tag-values <metrics-dataset> <tag-name>
```

---

## APL Quick Reference (Axiom Processing Language)

APL is the query language for event datasets. Key operators:

```
# Basic query
['dataset'] | where field == "value" | take 10

# Aggregation
['dataset'] | summarize count() by status

# Time bucketing
['dataset'] | summarize count() by bin(_time, 1h)

# Multiple conditions
['dataset'] | where status >= 400 and method == "POST"

# String search
['dataset'] | where message contains "error"

# Top N
['dataset'] | summarize count() by path | top 10 by count_

# Percentiles
['dataset'] | summarize percentile(duration, 50), percentile(duration, 95), percentile(duration, 99)

# Project specific fields
['dataset'] | project _time, status, path, duration

# Extend with computed fields
['dataset'] | extend duration_ms = duration / 1000000
```

**Time formats:**
- Relative: `now-1h`, `now-30m`, `now-7d`
- Absolute: `2026-03-12T00:00:00Z` (RFC3339)

---

## Common Workflows

### Investigate errors in the last hour
1. `$CMD query "['logs'] | where level == 'error' | summarize count() by message | top 10 by count_" --start "now-1h"`
2. Drill into a specific error: `$CMD query "['logs'] | where message contains 'specific error' | take 20" --start "now-1h"`

### Check system health
1. `$CMD monitors` - Check for any firing monitors
2. `$CMD query "['logs'] | summarize count() by bin(_time, 5m), level" --start "now-1h"` - Error rate over time

### Explore a new dataset
1. `$CMD datasets` - Find the dataset name
2. `$CMD dataset-fields <name>` - See available fields
3. `$CMD query "['<name>'] | take 5"` - Sample some data
4. `$CMD query "['<name>'] | summarize count() by bin(_time, 1h)" --start "now-24h"` - Volume over time

---

## Global Flags

- `--json` - Raw JSON output (all commands)
- `--limit N` - Number of results (where applicable, default 25-50)
- `--start` - Start time for time-ranged queries
- `--end` - End time for time-ranged queries

---

## Setup

### 1. Get API Token
1. Go to [Axiom Settings](https://app.axiom.co/settings/api-tokens)
2. Create a Personal Token (starts with `xapt-`)
3. Grant it read access to datasets you need

### 2. Configure
Add to `~/.claude/settings.json`:
```json
{
  "env": {
    "AXIOM_AUTH_TOKEN": "xapt-your-token-here",
    "AXIOM_ORG_ID": "your-org-id"
  }
}
```

`AXIOM_ORG_ID` is optional but recommended if you belong to multiple orgs.

### 3. Verify
Run `/axiom datasets` to confirm you can list your datasets.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `AXIOM_AUTH_TOKEN not set` | Missing env var | Add token to `~/.claude/settings.json` env |
| `HTTP 401` | Invalid or expired token | Regenerate token at app.axiom.co |
| `HTTP 404` | Dataset or resource not found | Check dataset name with `datasets` command |
| `HTTP 429` | Rate limited | Script auto-retries with backoff (up to 4 attempts) |
| `HTTP 400` on query | Invalid APL syntax | Check APL syntax - dataset name needs `['quotes']` |

---

## Upstream Sync (Auto-Update from Source Repo)

This skill was generated from: **https://github.com/axiomhq/mcp** (commit: `7f139a16ccf3d8d6e708dee65ea774b08b66685f`)
Source metadata: `{base}/source.json`

### On Every Skill Trigger

**Before executing the user's command**, launch a **background Agent** to check for upstream updates:

1. Read `{base}/source.json` to get the source repo URL and last known commit SHA
2. Launch a background agent (run_in_background: true) to:
   - Shallow-clone or fetch the source repo to `/tmp/skill-sync-axiom`
   - Compare latest commit with stored SHA
   - If different: analyze the changelog for API surface changes
   - **If good update** (new tools, bug fixes, additive changes): auto-update the script and SKILL.md, update source.json, return summary
   - **If bad update** (breaking changes, removals, regressions): skip changes, return reason
   - **If no changes**: return silently
3. Continue executing the user's command immediately (don't wait)
4. When the background agent completes:
   - If updated: notify user "Updated /axiom skill from upstream - <summary>"
   - If skipped: notify user "Upstream /axiom has changes but skipped - <reason>"
   - If no changes: say nothing

## Self-Healing Protocol

When a command fails unexpectedly:
1. **Diagnose** - Read error output and check the script
2. **Propose** - Describe the fix
3. **Await approval** - Ask user before editing
4. **Apply** - Edit `{base}/scripts/axiom.py`
5. **Verify** - Re-run the failed command
