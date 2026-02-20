---
name: create-skill
description: Generate a new Claude Code skill from an MCP server repo or API. Clones the repo, learns the API surface, and scaffolds a complete skill with a Python CLI wrapper and SKILL.md. Use when the user wants to create a new skill based on an MCP server, API, or service.
argument-hint: <repo-url-or-service-name>
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, WebSearch, WebFetch
---

# Create Skill

Generate a new Claude Code skill by learning from an MCP server repo or API documentation, then scaffolding a complete skill with a Python CLI wrapper.

**Input**: `$ARGUMENTS`

---

## Step 1: Parse Input

`$ARGUMENTS` format: `<source> [skill-name]`

- **source**: A GitHub URL (MCP repo), npm package name, or API docs URL
- **skill-name** (optional): Override the auto-detected name

If only a name/URL is given, infer the skill name from the repo (e.g., `getsentry/sentry-mcp` -> `sentry`, `linear-mcp` -> `linear`).

### When `$ARGUMENTS` is empty - Conversation Inference

If no arguments are provided, **scan the current conversation history** for GitHub repo URLs or service names that were discussed. Look for:

1. URLs matching `https://github.com/...` shared by the user or fetched via tools
2. MCP server names, npm packages, or service names mentioned
3. Repos that were cloned, explored, or discussed

From the candidates found, **pick the most likely official one**:
- Prefer repos under the official org (e.g., `getsentry/sentry-mcp` over `random-user/sentry-mcp`)
- Prefer repos with "mcp" in the name
- Prefer repos that were the main topic of discussion

If a strong candidate is found, confirm with the user:
> "I found `<repo-url>` from our conversation. Create a skill from this?"

If no candidates found, ask the user what service/MCP they want to create a skill for.

---

## Step 2: Clone & Explore

### 2a: If GitHub URL

```bash
git clone <url> /tmp/skill-source-<name> 2>&1 | tail -5
```

### 2b: If npm package

```bash
mkdir -p /tmp/skill-source-<name> && cd /tmp/skill-source-<name> && npm pack <package> --pack-destination . && tar -xzf *.tgz 2>/dev/null
```

### 2c: If API docs URL

Fetch the documentation using WebFetch and extract the API surface.

---

## Step 3: Learn the API Surface

Launch an **Explore agent** (very thorough) against the cloned repo to extract:

1. **All API endpoints/tools** - HTTP method, URL path, parameters, response shape
2. **Authentication method** - API key, OAuth, bearer token, etc.
3. **Configuration** - env vars, hosts, required setup
4. **Tool categories** - group by domain (issues, events, users, etc.)
5. **Key data types** - important response schemas

The agent prompt should be:

```
Very thorough exploration of /tmp/skill-source-<name>.

Extract the complete API surface:
1. All API endpoints or MCP tools - for each: HTTP method, URL path, query params, request body, key response fields
2. Authentication method (API key, OAuth, bearer token)
3. Required environment variables and configuration
4. Tool/endpoint categories grouped by domain
5. Key data types and response schemas

For MCP servers, focus on:
- packages/*/src/tools/ or src/tools/ for tool definitions
- packages/*/src/api-client/ or src/api/ for HTTP client methods
- README.md for setup instructions and config examples

Give me a comprehensive, structured list of ALL API operations.
```

---

## Step 4: Design the CLI Commands

Based on the learned API surface, design CLI commands following these conventions:

### Naming Rules
- **List resources**: `<plural-noun>` (e.g., `issues`, `projects`, `teams`)
- **Get single resource**: `<noun>-get` (e.g., `issue-get`, `project-get`)
- **Create resource**: `create-<noun>` (e.g., `create-project`, `create-team`)
- **Update resource**: `<noun>-update` or `update-<noun>` (e.g., `issue-update`)
- **Delete resource**: `<noun>-delete` or `delete-<noun>` (e.g., `issue-delete`)
- **Special actions**: descriptive verb (e.g., `whoami`, `autofix`, `search`)

### Argument Rules
- First positional arg should be the most common scope (e.g., `org`, `workspace`)
- Second positional arg should be the resource identifier
- Filters and options as `--flags`
- Always include `--json` for raw output
- Always include `--limit` on list commands (default 25)

### Command Categories
Group into 3-6 categories:
- Auth & Discovery
- Core CRUD operations
- Search & Query
- Analysis / AI features (if applicable)
- Management / Admin

---

## Step 5: Generate the Python Script

Create `~/.claude/skills/<name>/scripts/<name>.py` following this template:

### Script Requirements
- **Pure Python stdlib only** - no pip dependencies (use `urllib.request`, `json`, `argparse`)
- **Auth via env var** - `<SERVICE>_AUTH_TOKEN` or `<SERVICE>_API_KEY`
- **Retry logic** - exponential backoff on 429 rate limits (up to 4 attempts)
- **Error handling** - print HTTP status + response body on failure
- **Output modes** - human-readable tables by default, `--json` for raw output
- **Clean table formatting** - aligned columns with truncation

### Script Structure

```python
#!/usr/bin/env python3
"""<Service> CLI - <description> via <Service> REST API."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# --- Helpers ----------------------------------------------------------------

def get_token():
    token = os.environ.get("<SERVICE>_AUTH_TOKEN")
    if not token:
        print("Error: <SERVICE>_AUTH_TOKEN not set", file=sys.stderr)
        print("Add to ~/.claude/settings.json:", file=sys.stderr)
        print('  {"env": {"<SERVICE>_AUTH_TOKEN": "..."}}', file=sys.stderr)
        sys.exit(1)
    return token

def api(method, path, body=None, params=None):
    """Make an API request with retry logic."""
    # ... (standard pattern with retry, error handling)

def fmt_json(data):
    print(json.dumps(data, indent=2))

def fmt_table(rows, columns):
    """Print aligned table."""
    # ... (standard pattern)

def truncate(s, n=80):
    s = str(s or "")
    return s[:n] + "..." if len(s) > n else s

# --- Commands ---------------------------------------------------------------
# One function per command: cmd_<name>(args)

# --- CLI Parser -------------------------------------------------------------
def build_parser():
    # argparse with subcommands

DISPATCH = { "command-name": cmd_function, ... }

def main():
    parser = build_parser()
    args = parser.parse_args()
    fn = DISPATCH.get(args.command)
    if fn: fn(args)
    else: parser.print_help()

if __name__ == "__main__":
    main()
```

### Validation
After generating, run:
```bash
python3 ~/.claude/skills/<name>/scripts/<name>.py --help
```

---

## Step 5b: Generate Source Metadata

Create `~/.claude/skills/<name>/source.json` to track where this skill was generated from:

```json
{
  "repo": "<github-url>",
  "created_from_commit": "<commit-sha>",
  "created_at": "<ISO-8601-date>",
  "skill_version": 1
}
```

Get the latest commit SHA:
```bash
git -C /tmp/skill-source-<name> rev-parse HEAD
```

This file is used by the **Upstream Sync** section (see below) to detect updates.

---

## Step 6: Generate the SKILL.md

Create `~/.claude/skills/<name>/SKILL.md` following this template:

```markdown
---
name: <name>
description: <one-line description>. Use when the user asks about <trigger phrases>.
argument-hint: <typical argument>
allowed-tools: Bash, Read, Edit, Write, Agent
---

# <Service> Integration

<One-line description of what this skill does.>

> Paths below use `{base}` as shorthand for this skill's base directory.

**Input**: `$ARGUMENTS`

---

## Quick Reference

\```bash
CMD="python3 {base}/scripts/<name>.py"
\```

### Natural Language Mappings

| User says | Command |
|-----------|---------|
| ... | ... |

---

## Commands

### <Category 1>
\```bash
$CMD <command> [args]
\```

### <Category 2>
...

---

## <Query Syntax / Special Features>
(If the service has its own query language, document it here)

---

## Common Workflows

### <Workflow 1>
1. Step with command
2. Step with command

---

## Global Flags

- `--json` - Raw JSON output
- `--limit N` - Number of results (default 25)

---

## Setup

### 1. Get API Token
<Instructions to get the token>

### 2. Configure
Add to `~/.claude/settings.json`:
\```json
{
  "env": {
    "<SERVICE>_AUTH_TOKEN": "..."
  }
}
\```

### 3. Verify
Run `/<name> <verify-command>` to confirm.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| ... | ... | ... |

---

## Upstream Sync (Auto-Update from Source Repo)

**IMPORTANT: This section MUST be included in every generated skill.**

This skill was generated from a source repo. On every skill invocation, **before executing the user's command**, launch a **background agent** to check for upstream updates.

### Source Reference

\```
Source repo: <github-url>
Generated from commit: <commit-sha>
Source metadata: {base}/source.json
\```

### On Every Skill Trigger

1. Read `{base}/source.json` to get the source repo URL and last known commit
2. Launch a **background Agent** (run_in_background: true) with this task:

\```
Check for upstream updates to the skill source repo.

1. Clone or fetch the repo:
   git clone --depth=50 <repo-url> /tmp/skill-sync-<name> 2>/dev/null || git -C /tmp/skill-sync-<name> fetch origin

2. Get the latest commit SHA:
   git -C /tmp/skill-sync-<name> rev-parse origin/main (or origin/master)

3. Compare with the stored commit SHA from {base}/source.json

4. If they differ, get the changelog:
   git -C /tmp/skill-sync-<name> log --oneline <stored-sha>..origin/main

5. For each changed file, check if it affects the API surface:
   - Tool definitions (new tools, changed parameters, removed tools)
   - API endpoints (new endpoints, changed paths, auth changes)
   - Breaking changes (removed features, renamed fields)
   - Bug fixes in API client logic

6. ANALYZE the changes and make a judgment:

   IF GOOD UPDATE (new tools, bug fixes, improved endpoints, non-breaking additions):
   - Update the Python script ({base}/scripts/<name>.py) to add new commands or fix issues
   - Update the SKILL.md to document new commands/features
   - Update {base}/source.json with the new commit SHA and date
   - Return a summary: "Updated <name> skill: <what changed>"

   IF BAD UPDATE (breaking changes that would break existing commands, removals without replacement, regressions):
   - Do NOT modify any skill files
   - Return a summary: "Skipped <name> update: <why it's bad> - <what the upstream change was>"

   IF NO CHANGES:
   - Return: "No upstream updates for <name>"
\```

3. **Continue executing the user's command immediately** - don't wait for the sync agent
4. When the background agent completes, **notify the user** with the result:
   - If updated: "Updated /<name> skill from upstream - <brief summary of changes>"
   - If skipped: "Upstream /<name> has changes but skipped - <reason>"
   - If no changes: say nothing (silent)

### Update Judgment Criteria

**GOOD (auto-apply):**
- New API endpoints/tools added (additive, non-breaking)
- Bug fixes in existing endpoint behavior
- New query parameters or fields added to existing tools
- Documentation improvements that reveal previously undocumented features
- Dependency updates that don't change the API

**BAD (skip and notify):**
- Existing endpoints removed or renamed
- Authentication method changed
- Required parameters changed in a way that breaks existing commands
- Response schema changed in a way that breaks table formatting
- The repo appears abandoned, forked, or taken over

## Upstream Sync (Auto-Update from Source Repo)

This skill was generated from: **<github-url>** (commit: `<sha>`)
Source metadata: `{base}/source.json`

### On Every Skill Trigger

**Before executing the user's command**, launch a **background Agent** to check for upstream updates:

1. Read `{base}/source.json` to get the source repo URL and last known commit SHA
2. Launch a background agent (run_in_background: true) to:
   - Shallow-clone or fetch the source repo to `/tmp/skill-sync-<name>`
   - Compare latest commit with stored SHA
   - If different: analyze the changelog for API surface changes
   - **If good update** (new tools, bug fixes, additive changes): auto-update the script and SKILL.md, update source.json, return summary
   - **If bad update** (breaking changes, removals, regressions): skip changes, return reason
   - **If no changes**: return silently
3. Continue executing the user's command immediately (don't wait)
4. When the background agent completes:
   - If updated: notify user "Updated /<name> skill from upstream - <summary>"
   - If skipped: notify user "Upstream /<name> has changes but skipped - <reason>"
   - If no changes: say nothing

## Self-Healing Protocol

When a command fails unexpectedly:
1. **Diagnose** - Read error output and check the script
2. **Propose** - Describe the fix
3. **Await approval** - Ask user before editing
4. **Apply** - Edit `{base}/scripts/<name>.py`
5. **Verify** - Re-run the failed command
\```

---

## Step 7: Report

Show the user:

```
## Skill Created: <name>

**Location**: ~/.claude/skills/<name>/
**Commands**: <count> commands across <count> categories
**Auth**: <env var name> (get token at <url>)

### Quick Setup
Add to `~/.claude/settings.json`:
{"env": {"<SERVICE>_AUTH_TOKEN": "..."}}

### Test
/<name> <verify-command>

### Commands
<brief grouped list>
```

---

## Quality Checklist

Before reporting success, verify:

- [ ] `python3 ~/.claude/skills/<name>/scripts/<name>.py --help` runs without errors
- [ ] SKILL.md has proper frontmatter (name, description, argument-hint, allowed-tools)
- [ ] SKILL.md uses `{base}` for paths (not hardcoded)
- [ ] Natural language mappings cover the most common user intents
- [ ] Setup section has clear token/auth instructions
- [ ] Troubleshooting section covers auth errors, 404s, rate limits
- [ ] Self-healing protocol is included
- [ ] All commands have `--json` flag
- [ ] List commands have `--limit` flag
- [ ] Script uses only stdlib (no pip packages)
- [ ] `source.json` exists with repo URL and commit SHA
- [ ] SKILL.md includes the **Upstream Sync** section with the correct repo URL
- [ ] allowed-tools includes `Agent` (needed for background sync agent)

---

## Error Handling

- **Clone fails**: Try alternative URL formats, ask user to verify
- **No API surface found**: Ask user for API docs URL as fallback
- **Too many endpoints**: Prioritize the most useful 15-20 commands, note omitted ones
- **Auth unclear**: Default to bearer token pattern, note in setup section
