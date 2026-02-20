---
name: deep-review
description: This skill should be used when the user asks to "review this PR", "review my changes", "review this branch", "review this spec", or needs a code review. Provides two-pass review pattern with parallel breadth agents (find issues) then parallel depth agents (validate findings) for fewer false positives.
version: 3.0.0
---

# Review

Two-pass review: breadth agents find issues (high recall), depth agents validate them (high precision). Conductor synthesises into a consolidated report.

v3 adds: existing review integration, code-block fixes, model tiering, confidence scoring, and streamlined output.

Works on PRs, branches, staged changes, or specs.

## Workflow

### Step 0: Review Context

Before parsing arguments, determine the review context using AskUserQuestion:

```
Question: "What are we reviewing?"
Options:
1. "My local code" — reviewing own changes before creating a PR
2. "My PR" — reviewing own PR that's already open
3. "A teammate's PR" — reviewing someone else's PR
```

This context flows through the entire skill:

| Context | Can fix issues? | Branch checkout? | Post to PR? |
|---------|----------------|-----------------|-------------|
| My local code | Yes — fix directly | No — already on branch | No — no PR yet |
| My PR | Yes — fix directly | May need checkout | Yes — with `--post` |
| Teammate's PR | No — report only | Always checkout | Yes — with `--post` |

**Skip this step** if the context is unambiguous from the invocation:
- `/review` or `/review --staged` → always "My local code"
- `/review 493` with current branch matching PR branch → likely "My PR"
- Otherwise → ask

### Step 1: Detect Input + Extract Diff

Parse arguments to determine review mode:

```
/review 493              → PR mode:     gh pr diff 493
/review                  → Working tree: git diff
/review --staged         → Staged only:  git diff --cached
/review branch-name      → Branch mode:  git diff origin/dev HEAD
/review spec path.md     → Spec mode:    read file contents
/review --quick ...      → Quick mode:   3+3 agents instead of 5+5
/review --deep ...       → Deep mode:    6+6 agents, opus depth, regression risk
/review 493 --post       → PR mode + post as PR comment
/review 493 --post slack → PR mode + post to Slack channel
```

**Detection rules:**
- Digits only → PR number
- `--staged` flag → staged changes
- `--quick` flag → reduce agent count (combinable with any mode)
- `--deep` flag → increase agent count + opus depth + regression risk agent (combinable with any mode)
- `--post` flag → post output (to PR comment by default, or `slack` for Slack channel)
- Path ending in `.md` → spec review
- String with no path separators → branch name
- No args → working tree (staged + unstaged)

**Output default is console.** Posting to PR or Slack is an explicit action, not automatic. Don't be proactive with actions visible to others.

**CRITICAL for branch mode:** Use `git diff origin/dev HEAD` (direct comparison). NEVER use `git diff dev...HEAD` (triple-dot merge-base). The merge-base comparison includes changes from other PRs that landed on dev after the branch was cut, causing reviewers to flag code that isn't part of the change.

For PRs, `gh pr diff` handles the base comparison correctly.

**CRITICAL for PR mode: Ensure depth agents can read the PR code.**

Depth agents read actual files on disk, not the diff. If the PR branch isn't checked out locally, depth agents see the old code and produce false dismissals.

**Same-repo PR** (no `--repo` flag, or repo matches cwd):
```bash
# Save current branch, checkout PR branch
ORIGINAL_BRANCH=$(git branch --show-current)
gh pr checkout {PR_NUMBER}
# ... run review ...
# Restore after review
git checkout $ORIGINAL_BRANCH
```

**Cross-repo PR** (`--repo` flag, different repo):
```bash
# Clone/worktree to temp directory
REVIEW_DIR=$(mktemp -d)
gh pr checkout {PR_NUMBER} --repo {OWNER/REPO} --detach -b review-tmp || \
  git -C {REPO_PATH} worktree add $REVIEW_DIR review-tmp
# Tell agents: "The repo is at $REVIEW_DIR"
# ... run review ...
# Clean up
rm -rf $REVIEW_DIR  # or git worktree remove
```

If checkout fails (dirty working tree, etc.), warn the user and proceed with breadth-only confidence — note in the report that depth results may have false dismissals for new code.

### Step 2: Gather Existing Reviews (PR mode only)

**Skip this step** for non-PR modes (working tree, staged, branch, spec).

Before the breadth pass, fetch all existing review comments on the PR:

```bash
# Get all review comments (inline + top-level)
gh api repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/comments --jq '.[] | {user: .user.login, body: .body, path: .path, line: .line}'
gh api repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews --jq '.[] | select(.body != "") | {user: .user.login, state: .state, body: .body}'
```

Parse existing reviews into a structured format:

```
## Existing Review Comments

### From {reviewer_name} ({review_state}):
- [{file_path}:{line}] {comment_body_summary}

### From {bot_name}:
- [{file_path}:{line}] {finding_summary}
```

This context is injected into breadth agent prompts via `{EXISTING_REVIEWS}` placeholder. Agents must:
1. **Not duplicate** — if an existing review already covers the same issue at the same location, skip it
2. **Cross-reference** — if a finding extends or disagrees with an existing review, note it: "Extends @reviewer's finding on line X" or "Disagrees with @bot — see Evidence"
3. **Confirm agreement** — if an agent independently finds the same issue as an existing review, note: "Independently confirms @reviewer's finding"

### Step 3: Analyse Diff + Pick Domains

Analyse the diff to determine which domain lenses are most relevant.

| Mode | Breadth Agents | Depth Agents | Total |
|------|---------------|-------------|-------|
| Quick | 2 domain + 1 holistic | 2 batch + 1 holistic | 6 |
| Full | 4 domain + 1 holistic | 4 batch + 1 holistic | 10 |
| Deep | 5 domain + 1 holistic + 1 regression | 5 batch + 1 holistic + 1 regression | 14 |

Pick domains from the appropriate pool. See `references/domain-pools.md` for code review and spec review domain tables.

The holistic agent is always present. It looks for: missing changes, cross-file consistency, architectural concerns, production safety.

**Deep mode** adds a **Regression Risk** agent that traces call sites, checks test coverage, and identifies what existing behavior could break. See `references/domain-pools.md` for details.

### Step 4: Breadth Pass (Pass 1)

Spawn all breadth agents in parallel using the Task tool:
- `subagent_type: general-purpose`
- `mode: bypassPermissions`
- `model: sonnet` (all breadth agents use sonnet for speed)

Each agent receives the diff, the list of changed files, its domain focus, existing review context (if PR mode), and the finding output template. See `references/agent-prompts.md` for exact prompts.

**Diff as anchor, code as context.** Breadth agents get the diff to know what changed, but they CAN and SHOULD read source files for surrounding context. The prompt includes: "You may read source files for context, but only flag issues in the changed code."

This prevents the pattern where agents reason from the diff alone without verifying assumptions against the actual codebase (e.g., citing wrong provider behaviour, missing how a framework API works).

Instruction framing: "Find issues. Be thorough. Better to over-report than miss."

Each finding must use the **structured output format** — not prose. This enables mechanical dedup in the conductor step:

```
### Finding N
- **Severity:** P1 / P2 / P3
- **Location:** file/path:line_number
- **Category:** [env-validation | null-handling | type-safety | retry-logic | auth | prompt-quality | architecture | missing-change | ...]
- **Issue:** One sentence
- **Evidence:** Why this is a problem (reference specific code you read)
- **Suggested fix:** How to resolve it
- **Fix code:** (REQUIRED for P1/P2) Actual code snippet showing the fix
```

**Code-block fixes are required for P1 and P2 findings.** Agents must provide actual before/after code, not just prose descriptions. This makes findings immediately actionable — the reviewer can copy-paste the fix. P3 findings may use prose-only suggestions.

The `Location` + `Category` pair is the dedup key. Same file:line + same category from multiple agents = one finding with multi-agent agreement (higher confidence).

### Step 5: Conductor Synthesis

Collect structured findings from all breadth agents. This step stays with the conductor (not an agent) because the conductor has the full picture from all breadth results.

The structured output format makes this **mechanical, not judgmental**:

1. **Deduplicate** — group by `Location` + `Category` key. Same key from multiple agents = one finding with multi-agent agreement (higher confidence).
2. **Ghost check** — run `git diff origin/dev HEAD -- <file>` for any finding whose file isn't obviously in the diff. Auto-dismiss with "not in this change" if the file shows no changes.
3. **Check learnings** — read `references/learnings.md` for known false positive patterns. Pre-filter findings that match recurring dismissal patterns (e.g., "prompt structure concerns when Output.object() is used").
4. **Cross-reference existing reviews** — match findings against existing review comments from Step 2. Tag matches:
   - `[ALSO: @reviewer]` — same issue already flagged by a reviewer
   - `[EXTENDS: @reviewer]` — finding adds new information to existing review
   - `[NEW]` — not covered by any existing review (default)
5. **Assign confidence** based on agent agreement:
   - `HIGH` — 2+ agents found the same issue (same Location + Category)
   - `MEDIUM` — 1 agent found it, clear evidence provided
   - `LOW` — 1 agent, weak evidence or speculative
6. **Batch for depth** — distribute findings evenly across depth agents. Holistic findings get their own dedicated depth agent.

### Step 6: Depth Pass (Pass 2)

Spawn depth agents in parallel (same spawning pattern as breadth).

**Model tiering:**
- `model: opus` for holistic depth agent and regression risk depth agent (critical judgment calls)
- `model: sonnet` for domain batch depth agents (straightforward validation)
- `model: haiku` for all depth agents in quick mode

Each depth agent receives a batch of findings — NOT the diff. They must read the actual code at each location themselves, forcing genuine verification.

Instruction framing: "Read the actual code. Verify each finding. Be skeptical. Dismiss false positives ruthlessly."

For each finding, produce a verdict:
- **CONFIRMED** — keep or escalate severity, with evidence. Update fix code if the breadth agent's fix was incomplete or incorrect.
- **DOWNGRADED** — new severity with reasoning (e.g., "P1 → P3: only affects fallback path")
- **DISMISSED** — reason (e.g., "false positive: already handled at line X")

Depth holistic agent validates cross-cutting findings and checks for anything breadth missed entirely.

### Step 7: Consolidated Report

Synthesise validated findings into the final report. The conductor writes the Summary (top) sections itself — it has the diff, all breadth results, and all depth verdicts.

```
## Deep Review

### Summary

| Severity | Count |
|----------|-------|
| P1 — High | N |
| P2 — Medium | N |
| P3 — Low | N |

**P1 items should be fixed before merge.** P2 items are recommended. P3 can be follow-ups.

**Intent:** What is this change trying to achieve? One or two sentences on the goal — not what files changed, but what problem is being solved and why.

**Execution:** How well does it achieve that intent? Did the approach land cleanly, or are there structural concerns? Note any significant trade-offs or shortcuts.

**Code Quality & Patterns:** Does the code follow established codebase patterns? Call out any new patterns introduced, any patterns violated, and whether the code reads like it belongs in this codebase.

---

### P1 — High (fix before merge)

#### {Issue title}

**`file/path:line_number`**

{Detailed description of the problem with evidence from depth pass.}

**Fix:**

```{lang}
// before
{original code}

// after
{fixed code}
```

{Brief explanation of why this fix works.}

---

### P2 — Medium (should fix)

#### {Issue title}

**`file/path:line_number`**

{Description with evidence.}

**Fix:** {code block or concise instruction}

---

### P3 — Low (warnings)

| # | Finding | Location | Note |
|---|---------|----------|------|

---

### Already Flagged by Others (agreement)

| Item | Flagged by | Our assessment |
|------|-----------|----------------|
| {issue summary} | @reviewer on `file:line` | Agree / Disagree — {reason} |

### What's Good
- [positive observation from holistic agents]

---

**Stats:** X found → Y confirmed, Z dismissed, W downgraded
**Confidence:** {N} high-confidence, {N} medium, {N} low
**Recommendation:** [merge as-is | fix P1s then merge | needs discussion]
```

**Report rules:**
- Summary is written by the conductor, not agents
- Summary draws from: the diff (intent), breadth + depth results (execution, quality), file list (reading list)
- Severity table at the top (Tom-style) for quick scan
- P1/P2 findings include actual code fixes (before/after blocks)
- P3 findings in compact table format
- "Already Flagged" section cross-references existing reviews — shows agreement/disagreement
- Dismissed findings excluded (count noted in stats)
- Downgraded findings show original → final severity
- Stats show the funnel: total → confirmed / dismissed / downgraded
- Confidence stats show how many findings had multi-agent agreement

**Output target (default: console):**
- No `--post` flag → print to console (always)
- `--post` flag → also post as PR comment via `gh pr comment` (PR mode only)
- `--post slack` flag → also post to Slack via dev MCP CLI

Console output is always shown. `--post` adds a secondary destination.

### Step 8: Learning Loop

After the report, present the proposed learnings entry using AskUserQuestion:

```
AskUserQuestion:
  question: "Here's what I'd add to learnings from this review. Confirm, amend, or skip?"
  options:
    - "Looks good" — write as proposed
    - "Amend" — user provides corrections (via Other text)
    - "Skip" — don't write learnings for this review
```

Show the proposed learnings entry (dismissed patterns, downgraded patterns, emerging patterns) before asking.

Only write to `references/learnings.md` after user confirms or provides amendments.

**Promotion rule:** When a dismissal pattern appears 3+ times across different reviews, propose promoting it to the relevant domain's breadth prompt as a "Known false positive" instruction.

### Step 9: Fix Confirmed Issues (Own Code Only)

**Only runs when review context is "My local code" or "My PR" (from Step 0).**

If confirmed P1 or P2 findings exist, present using AskUserQuestion:

```
AskUserQuestion:
  question: "Want me to address the confirmed issues?"
  multiSelect: true
  options:
    - "Fix all P1s and P2s" — address everything
    - "Fix P1s only" — just the bugs
    - "Skip" — I'll handle it myself
```

**Fix approach by size:**
- **Small fixes** (< ~10 lines, mechanical, obvious): Fix directly using Edit tool. Show what changed.
- **Large fixes** (architectural, multi-file, judgment calls): Describe the proposed approach and let the user confirm before implementing.

After fixing, show a summary of what was changed and suggest re-running the review if the fixes were significant.

**Never offer to fix for teammate's PRs.** The report is the deliverable — leave fixes to the PR author.

## Anti-Patterns

**Ghost diffs:** Triple-dot comparison shows inherited code as changes. Always use direct comparison. The ghost check in Step 5 catches any that slip through.

**Severity inflation:** Breadth agents call everything P1. This is expected — the depth pass exists to recalibrate. Two-pass structure makes this a feature, not a bug.

**Diff-only reasoning:** Breadth agents reasoning from the diff alone without checking the actual codebase. The "diff as anchor, code as context" pattern prevents this — agents can and should read source files to verify their assumptions.

**Auto-posting:** Never post review output to PRs or Slack without explicit `--post` flag. Console is always the default.

**Wrong-branch depth reads:** When reviewing external PRs, depth agents read whatever branch is checked out on disk. If the PR branch isn't checked out, depth agents dismiss real findings because the new code "doesn't exist." Always checkout the PR branch before the depth pass (Step 1). If checkout fails, the conductor must override wrong-branch dismissals using breadth diff evidence.

**Prose-only P1/P2 fixes:** P1 and P2 findings MUST include actual code-block fixes. "Consider refactoring" is not actionable — show the exact code change. If the fix is too complex for a code block, break it into steps with code for each step.

**Duplicating existing reviews:** When reviewing PRs with existing comments, agents must check the existing review context and not re-report known issues. The "Already Flagged" section is for cross-referencing, not duplicating.

## References

- `references/domain-pools.md` — Code review and spec review domain tables with selection criteria
- `references/agent-prompts.md` — Exact prompt templates for breadth and depth agents
- `references/learnings.md` — Accumulated dismissal patterns and promoted false positive rules
