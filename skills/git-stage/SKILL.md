---
name: git-stage
description: This skill should be used when the user wants to "stage changes", "prepare a commit", "commit this", or needs help crafting a commit message. Analyzes changes, excludes agent-generated files, stages, crafts a conventional commit message, and commits locally. Does not push or create PRs — use /ship for delivery.
---

# Git Stage Skill

Prepare and commit: analyze changes, exclude junk, stage, craft message, commit locally. **Never pushes — use `/ship` for delivery.**

## Workflow

### Step 1: Analyze Current State

```bash
git branch --show-current
git status
git diff --stat
git diff --cached --stat
```

### Step 2: Extract Ticket Number from Branch

Branch pattern: `SAI-XXXX-Description-Here` → extract `SAI-XXXX`

If no ticket in branch name:
1. Check recent commits for ticket reference
2. Ask the user
3. Proceed without only if user confirms (rare)

### Step 3: Identify Files to EXCLUDE

**NEVER stage:**
- `.claude/` directory contents
- `requested-agents.md`
- `*.generated.md`, `*_generated.md`
- Agent-generated markdown from current session

**DO stage:**
- All source code (`*.py`, `*.js`, `*.ts`, etc.)
- Config files (`*.json`, `*.yaml`, `*.toml`, etc.)
- `CLAUDE.md` only if user explicitly modified it
- Legitimate project docs (`README.md`, `CHANGELOG.md`, etc.)

### Step 4: Determine Commit Type and Scope

**Types:** `feat`, `fix`, `refactor`, `style`, `docs`, `test`, `chore`, `ci`, `build`, `revert`

**Scopes (agents repo):**

| Files Changed | Scope |
|---------------|-------|
| `src/agent/**` | `agent` |
| `src/agent/stage_tts/**` | `tts` |
| `src/agent/stage_stt/**` | `stt` |
| `src/agent/stage_llm/**` | `llm` |
| `src/database/**` | `database` |
| `src/evals/**` | `evals` |
| `src/utils/logging.py` | `logger` |
| `src/services/langfuse.py` | `metrics` |
| Multiple directories | Primary area or omit |

**Scopes (monorepo):** Infer from directory — `core`, `trigger`, `api`, `db`, `dashboard`, `functions`, `ui`, etc. Omit if changes span multiple areas.

**Disallowed scopes:** `release`, `merge`

### Step 5: Craft Commit Message

**Format:**
```
type(scope): lowercase description in imperative mood [SAI-XXXX]
```

**Rules:**
1. Lowercase type and description
2. Imperative mood: "add" not "added"
3. Under 72 characters total
4. Ticket in square brackets at end
5. No period at end
6. Be specific: "add customer phone validation" not "update code"

### Step 6: Stage Files

```bash
git add <file1> <file2> ...

# Or stage all then unstage excluded
git add .
git reset HEAD -- .claude/
git reset HEAD -- requested-agents.md
git reset HEAD -- "*.generated.md"
```

### Step 7: Verify + Present

```bash
git diff --cached --stat
git status
```

Present:
```
## Git Stage Summary

**Branch:** SAI-XXXX-description
**Ticket:** SAI-XXXX

### Staged Files:
- path/to/file.ts
- path/to/other.ts

### Excluded:
- .claude/agents/foo.md

### Proposed Commit Message:
feat(scope): description [SAI-XXXX]
```

### Step 8: Refine Gate

Use AskUserQuestion:

- **Commit** — commit with this message
- **Edit message** — change the commit message
- **Edit files** — add or remove staged files
- **Stage only** — leave staged without committing (rare)
- **Cancel** — unstage everything

### Step 9: Commit

On **Commit**:
```bash
git commit -m "$(cat <<'EOF'
type(scope): description [SAI-XXXX]
EOF
)"
```

Verify:
```bash
git log --oneline -1
```

Present:
```
Committed: feat(scope): description [SAI-XXXX]

Run /ship when ready to push + create PR.
```

On **Stage only**: skip commit, present staged summary, suggest `/ship` when ready.

## Edge Cases

**No ticket:** Ask user. Proceed without only if confirmed.
**Mixed changes:** Suggest splitting into multiple commits. Stage one ticket's files at a time.
**Only docs:** Verify legitimate (not agent-generated). Use `docs:` type.
**Merge conflicts:** Stop. Alert user to resolve first.

## PR Title Format (for reference)

PR titles follow the same format as commits (validated by CI):
```
type(scope): lowercase description [SAI-XXXX]
```
Pattern: `^(\w*)(?:\((.*)\))?: (.+?)(?:\s+\[SAI-\d+\])?$`
