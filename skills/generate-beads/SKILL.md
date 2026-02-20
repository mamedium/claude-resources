---
name: generate-beads
description: Generate OpenSpec proposals and/or Beads issues from an approved Claude plan. Use after plan mode approval to scaffold work tracking artifacts.
argument-hint: [plan-file-path]
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

# Generate Beads Skill

Automates the flow from an approved Claude plan to OpenSpec proposals and Beads issues. Invoke via `/generate-beads` after plan mode approval.

**Rule**: Never create OpenSpec or Beads during plan mode — only after the plan is approved and exited.

## Workflow

Execute these steps in order:

### Step 1: Find the Plan File

If an argument was provided, use it as the plan file path.

Otherwise, use the Glob tool with pattern `.claude/plans/*.md` and pick the most recently modified file.

Read the plan content. If no plan file is found, report an error and stop:

```
Error: No plan file found in .claude/plans/
Provide a path: /generate-beads path/to/plan.md
```

### Step 2: Ask User for Mode

Use `AskUserQuestion` with these options:

| Option | Description |
|--------|-------------|
| **Both** (recommended) | Generate OpenSpec proposal + Beads issues |
| **OpenSpec only** | Generate proposal files only, no Beads |
| **Beads only** | Create issues directly from plan, skip OpenSpec |

### Step 3: Check Existing State

Before parsing or creating anything, check what already exists:

```bash
openspec list                  # Active changes — avoid conflicts
openspec list --specs          # Existing capabilities — prefer modifying over duplicating
```

Also read `openspec/project.md` for project conventions that should inform the generated artifacts.

If an existing capability matches what the plan is changing, note it — the spec delta in Step 5d should use `MODIFIED` instead of `ADDED`.

### Step 4: Parse the Plan

Extract from the plan content:

| Plan Section | Maps To |
|-------------|---------|
| Context/purpose/problem statement | proposal.md "Why" section |
| Implementation steps/sections | tasks.md numbered sections + proposal.md "What Changes" |
| Files to modify/create | proposal.md "Impact" section |
| Verification/testing steps | tasks.md final verification section |

> **Warning**: If the plan doesn't clearly have these sections (e.g., no explicit context/problem statement, or steps are inline rather than grouped), log a warning and extract what's available. Do not generate empty sections — omit them instead.

### Step 5: Derive Identifiers

**change-id**: Derive from plan title using verb-led kebab-case:
- "Plan: Add UI Automation Tests" → `add-ui-automation-tests`
- "Plan: Fix Login Validation Bug" → `fix-login-validation-bug`
- "Plan: Update Payment Flow" → `update-payment-flow`

**capability**: Derive noun-based from the primary domain:
- "UI Automation Tests" → `ui-automation-testing`
- "Payment Flow" → `payment-flow`
- "CRM Identifiers" → `crm-identifiers`

Check if `openspec/changes/<change-id>/` already exists. If so, ask user for an alternative name.

### Step 6: Create OpenSpec (if mode includes it)

Create the directory structure:

```bash
mkdir -p openspec/changes/<change-id>/specs/<capability>
```

**6a. `proposal.md`**

```markdown
# Change: <Title derived from plan>

**Original Plan**: `.claude/plans/<plan-file-name>.md`

## Why

<Extracted from plan context/problem statement>

## What Changes

<Bullet list derived from implementation steps>

## Impact

- Affected specs: `<capability>`
- Affected code:
  <List of files from plan>
```

**6b. `tasks.md`**

```markdown
**Original Plan**: `.claude/plans/<plan-file-name>.md`

## 1. <First logical group>

- [ ] 1.1 <First task>
- [ ] 1.2 <Second task>

## 2. <Second logical group>

- [ ] 2.1 <Task>

...

## N. Verification

- [ ] N.1 Run typecheck and lint for affected packages
- [ ] N.2 <Testing step from plan>
```

**6c. `design.md`** (only if plan has 3+ implementation sections, affects 2+ `apps/` or `internal/` directories, introduces an external dependency, or has security/migration complexity)

```markdown
# Design Documentation

**Original Plan**: `.claude/plans/<plan-file-name>.md`

## Context

<Background, constraints, stakeholders from plan>

## Goals / Non-Goals

- Goals: <What this change achieves>
- Non-Goals: <What is explicitly out of scope>

## Decisions

### 1. <Decision title>

**Decision**: <What was decided>

**Rationale**: <Why this approach>

**Alternative considered**: <Other option>
- **Rejected**: <Why>

## Risks / Trade-offs

- <Risk> → <Mitigation>

## Migration Plan

<Steps and rollback strategy, if applicable — omit section if not relevant>

## Open Questions

- <Any unresolved questions from the plan>
```

**6d. `specs/<capability>/spec.md`**

> **Skip for simple plans**: If the plan is a bug fix, single-file change, or has only 1 implementation section, skip spec.md generation entirely. Specs are for behavioral/capability changes, not minor fixes.

**Choose the correct delta operation** based on Step 3 findings:

- **ADDED** — New capability that doesn't exist in `openspec/specs/` yet
- **MODIFIED** — Changes behavior of an existing capability. MUST copy the full existing requirement text from `openspec/specs/<capability>/spec.md`, paste it under `## MODIFIED Requirements`, then edit to reflect changes. Partial deltas cause data loss at archive time.
- **REMOVED** — Removing an existing capability. Include `**Reason**` and `**Migration**`.

```markdown
## ADDED Requirements

### Requirement: <Requirement name>

<Description using SHALL/MUST wording>

#### Scenario: <Scenario name>

- **WHEN** <condition>
- **THEN** <expected behavior> SHALL <outcome>
- **AND** <additional expectation>
```

For MODIFIED requirements:
```markdown
## MODIFIED Requirements

### Requirement: <Existing requirement name — must match exactly>

<Full updated requirement text with SHALL/MUST wording>

#### Scenario: <Updated or new scenario>

- **WHEN** <condition>
- **THEN** <updated expected behavior>
```

**6e. Validate OpenSpec**

```bash
openspec validate <change-id> --strict --no-interactive
```

If validation fails, fix the errors and re-validate. Common fixes:
- Missing `proposal.md` → create it
- Scenario format → use exactly 4 hashtags (`####`)
- Missing ADDED/MODIFIED/REMOVED prefix → add it

### Step 7: Create Beads Issues (if mode includes it)

**Prefer Beads MCP tools** for all operations. Fall back to `bd` CLI only if MCP tools are unavailable (tool not found or connection errors).

**7a. Check for existing issues (idempotency)**

Before creating anything, check if issues already exist for this plan:

Using MCP tool: `list` with `status="open"` — scan for issues whose title or description references `openspec/changes/<change-id>/`.

If an epic already exists:
- Skip epic creation, reuse the existing epic ID
- Only create child issues that don't already exist (match by title)
- Report what was skipped vs. created

**7b. Create the epic**

Using MCP tool: `create` with parameters:
- `title`: `"<Plan title>"`
- `issue_type`: `"epic"`
- `description`: `"OpenSpec: openspec/changes/<change-id>/"`
- `priority`: `2`

Capture the epic ID from output (format: `bd-XXXX`).

**7c. Create child issues** (one per tasks.md section)

For each numbered section in tasks.md, use MCP tool: `create` with:
- `title`: `"<Section title>"`
- `description`: `"Epic: <epic-id>"`
- `priority`: `2`
- `deps`: `["<epic-id>"]`

The `deps` parameter automatically links the child to the epic. No separate dependency step needed.

Capture each child ID.

**7d. Error recovery**

If creation fails partway through (e.g., epic created but some children failed):
1. Use MCP tool: `list` with `status="open"` to see what was already created
2. Resume from where it stopped — don't recreate existing issues
3. Report partial state to the user with which issues succeeded and which failed

**7e. Fallback: `bd` CLI**

If MCP tools are unavailable (tool not found or connection errors), fall back to CLI:

```bash
# Epic
bd create "<Plan title>" --type epic --description "OpenSpec: openspec/changes/<change-id>/" --priority 2

# Child issues (--parent auto-links to epic)
bd create "<Section title>" --parent <epic-id> --priority 2
```

If `bd` CLI is also unavailable, output the commands for the user to run manually.

**7f. Flush to JSONL**

After all issues are created, run:

```bash
bd sync --flush-only
```

This ensures Beads data is persisted to JSONL files.

### Step 8: Cross-Reference Updates

After both OpenSpec and Beads are created, update the files with cross-references:

**8a. Update tasks.md** — add Beads issue IDs to section headers:

```markdown
## 1. Section Name (`bd-XXXX`)
```

**8b. Update proposal.md and tasks.md** — add Beads epic reference:

Add after the "Original Plan" line:

```markdown
**Beads Epic**: `<epic-id>`
```

**8c. Update design.md** (if created) — add same references at top.

### Step 9: Summary Output

Present the results:

```
## Generation Complete

### OpenSpec
- Path: openspec/changes/<change-id>/
- Files: proposal.md, tasks.md, [design.md], specs/<capability>/spec.md
- Validation: Passed

### Beads
- Epic: <epic-id> — "<Plan title>"
- Issues:
  - <child-id-1> — "<Section 1 title>"
  - <child-id-2> — "<Section 2 title>"
  ...

### Next Steps
Work on issues one at a time using the Beads workflow:
1. `bd update <first-child-id> --status in_progress`
2. Implement the changes
3. Run pre-checks, commit, then close the issue
```

## Critical Rules

1. **Never create during plan mode** — only after plan is approved and exited
2. **Check existing state first** — run `openspec list`, `openspec list --specs`, read `openspec/project.md` before generating
3. **Always validate OpenSpec** before creating Beads issues
4. **All three artifacts must cross-reference each other** (Plan ↔ OpenSpec ↔ Beads)
5. **Prefer Beads MCP tools**, fall back to `bd` CLI only if MCP is unavailable
6. **Use `deps` parameter** (MCP) or `--parent` flag (CLI) when creating child issues — no separate dependency step needed
7. **One issue per tasks.md section** — don't split sections into multiple issues
8. **Spec scenarios use exactly 4 hashtags** (`#### Scenario:`)
9. **Use SHALL/MUST wording** in spec requirements
10. **Choose correct delta operation** — use MODIFIED (with full text) for existing capabilities, ADDED for new ones
11. **change-id must be verb-led kebab-case** (e.g. `add-feature`, `fix-bug`, `update-flow`)
12. **Do not modify the original plan file** — it's a read-only input
13. **Check for duplicates** before creating Beads issues — never create duplicate epics or children
14. **Always flush** (`bd sync --flush-only`) after creating Beads issues
