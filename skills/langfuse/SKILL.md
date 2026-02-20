---
name: langfuse
description: Langfuse LLM observability - traces, scores, prompts, datasets, metrics. Use when the user asks about Langfuse traces, LLM observability, prompt management, evaluation scores, datasets, or provides a Langfuse URL.
argument-hint: traces --limit 10
allowed-tools: Bash, Read, Edit, Write, Agent
---

# Langfuse Integration

Query and manage Langfuse LLM observability data - traces, observations, scores, prompts, datasets, and metrics.

> Paths below use `{base}` as shorthand for this skill's base directory.

**Input**: `$ARGS`

---

## Quick Reference

```bash
CMD="python3 {base}/scripts/langfuse.py"
```

### Natural Language Mappings

| User says | Command |
|-----------|---------|
| "show me recent traces" | `$CMD traces` |
| "get trace details" | `$CMD trace-get <id>` |
| "list observations for trace" | `$CMD observations --trace-id <id>` |
| "show me the scores" | `$CMD scores` |
| "create a score for this trace" | `$CMD create-score --name <n> --trace-id <id> --value <v>` |
| "list prompts" | `$CMD prompts` |
| "get prompt X" | `$CMD prompt-get <name>` |
| "create a text prompt" | `$CMD create-prompt --name <n> --prompt-text "..."` |
| "show datasets" | `$CMD datasets` |
| "list sessions" | `$CMD sessions` |
| "show models" | `$CMD models` |
| "get metrics" | `$CMD metrics --query '...'` |
| "check langfuse health" | `$CMD health` |
| "list projects" | `$CMD projects` |

---

## Commands

### Health & Projects
```bash
$CMD health                          # Check API health
$CMD projects [--limit N]            # List projects
```

### Traces
```bash
$CMD traces [--limit N] [--cursor C] [--user-id U] [--session-id S]
$CMD trace-get <trace-id>            # Full trace with observations
$CMD trace-bookmark <trace-id>       # Bookmark a trace
$CMD trace-unbookmark <trace-id>     # Remove bookmark
$CMD trace-delete <trace-id>         # Delete a trace
```

### Observations
```bash
$CMD observations [--limit N] [--cursor C] [--trace-id T] [--type SPAN|GENERATION|EVENT] [--name N] [--level L] [--environment E]
$CMD observation-get <observation-id>
```

### Sessions
```bash
$CMD sessions [--limit N] [--user-id U]
$CMD session-get <session-id>
```

### Scores
```bash
$CMD scores [--limit N] [--cursor C] [--filter F]
$CMD create-score --name <name> --trace-id <id> [--value 0.9] [--string-value "good"] [--observation-id O] [--comment "..."] [--data-type NUMERIC|BOOLEAN|CATEGORICAL]
$CMD score-delete <score-id>
$CMD score-configs [--limit N]       # List score configurations
```

### Prompts
```bash
$CMD prompts [--limit N] [--name N]
$CMD prompt-get <name> [--version V] [--label production]
$CMD create-prompt --name <n> --type text|chat [--prompt-text "..."] [--messages '[{"role":"system","content":"..."}]'] [--labels "production,staging"] [--tags "t1,t2"] [--config '{}'] [--commit-message "..."]
```

### Datasets
```bash
$CMD datasets [--limit N]
$CMD dataset-get <name>
$CMD create-dataset --name <n> [--description "..."] [--metadata '{}']
$CMD dataset-runs <name> [--limit N]
$CMD dataset-items [--dataset-name N] [--limit N]
$CMD create-dataset-item --dataset-name <n> --input '{"key":"val"}' [--expected-output '{}'] [--metadata '{}'] [--source-trace-id T]
```

### Models
```bash
$CMD models [--limit N]
$CMD model-get <model-id>
```

### Metrics
```bash
$CMD metrics [--query '{"view":"traces","dimensions":["name"],"metrics":["count"]}']
```

---

## Common Workflows

### Investigate a trace
1. `$CMD traces --limit 10` - find recent traces
2. `$CMD trace-get <id>` - view trace details with observations
3. `$CMD observations --trace-id <id>` - list all spans/generations
4. `$CMD observation-get <obs-id>` - inspect specific generation input/output

### Score traces for evaluation
1. `$CMD traces --user-id <uid>` - find traces to evaluate
2. `$CMD create-score --name accuracy --trace-id <id> --value 0.95`
3. `$CMD scores --limit 50` - review scores

### Manage prompts
1. `$CMD prompts` - list all prompts
2. `$CMD prompt-get my-prompt --label production` - get production version
3. `$CMD create-prompt --name my-prompt --type text --prompt-text "You are..." --labels "staging"`

### Build evaluation datasets
1. `$CMD create-dataset --name "qa-eval" --description "QA evaluation set"`
2. `$CMD create-dataset-item --dataset-name "qa-eval" --input '{"question":"..."}' --expected-output '{"answer":"..."}'`
3. `$CMD dataset-items --dataset-name "qa-eval"` - verify items

---

## Global Flags

- `--json` - Raw JSON output (place before subcommand)
- `--limit N` - Number of results (default 25)
- `--cursor C` - Cursor-based pagination (v2 endpoints)
- `--page N` - Page-based pagination (v1 endpoints)

---

## Setup

### 1. Get API Keys
Go to your Langfuse project settings > API Keys. You need:
- **Public Key** (starts with `pk-lf-`)
- **Secret Key** (starts with `sk-lf-`)

### 2. Configure
Add to `~/.claude/settings.json`:
```json
{
  "env": {
    "LANGFUSE_PUBLIC_KEY": "pk-lf-...",
    "LANGFUSE_SECRET_KEY": "sk-lf-...",
    "LANGFUSE_BASEURL": "https://cloud.langfuse.com"
  }
}
```

For EU cloud use `https://cloud.langfuse.com`, for US cloud use `https://us.cloud.langfuse.com`.

### 3. Verify
Run `/langfuse health` to confirm connection.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set` | Missing env vars | Add keys to `~/.claude/settings.json` |
| `HTTP 401` | Invalid credentials | Check public/secret key pair, ensure correct project |
| `HTTP 404` | Wrong base URL or invalid resource ID | Verify `LANGFUSE_BASEURL` matches your region |
| `HTTP 429` | Rate limited | Script auto-retries with backoff (up to 4 attempts) |
| `HTTP 403` | Insufficient permissions | Check API key scope in Langfuse project settings |

---

## Upstream Sync (Auto-Update from Source Repo)

This skill was generated from: **https://github.com/langfuse/mcp-server-langfuse** (commit: `a534b5a995d50c21ba45f14419246ef64d3ca6f4`)
Source metadata: `{base}/source.json`

### On Every Skill Trigger

**Before executing the user's command**, launch a **background Agent** to check for upstream updates:

1. Read `{base}/source.json` to get the source repo URL and last known commit SHA
2. Launch a background agent (run_in_background: true) to:
   - Shallow-clone or fetch the source repo to `/tmp/skill-sync-langfuse`
   - Compare latest commit with stored SHA
   - If different: analyze the changelog for API surface changes
   - **If good update** (new tools, bug fixes, additive changes): auto-update the script and SKILL.md, update source.json, return summary
   - **If bad update** (breaking changes, removals, regressions): skip changes, return reason
   - **If no changes**: return silently
3. Continue executing the user's command immediately (don't wait)
4. When the background agent completes:
   - If updated: notify user "Updated /langfuse skill from upstream - <summary>"
   - If skipped: notify user "Upstream /langfuse has changes but skipped - <reason>"
   - If no changes: say nothing

## Self-Healing Protocol

When a command fails unexpectedly:
1. **Diagnose** - Read error output and check the script
2. **Propose** - Describe the fix
3. **Await approval** - Ask user before editing
4. **Apply** - Edit `{base}/scripts/langfuse.py`
5. **Verify** - Re-run the failed command
