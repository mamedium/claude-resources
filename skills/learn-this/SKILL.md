---
name: learn-this
description: Reflect on the just-completed work, deep-think the key learnings, and capture them in the right place (project CLAUDE.md and/or auto-memory). Optionally promote recurring patterns into a reusable skill. Use when the user says "learn this", "/learn-this", "what's the takeaway", or "capture this lesson" after a review-pass / bug-fix / surprising-fix.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - AskUserQuestion
---

# /learn-this - Capture Session Learnings

This skill is NOT `/learn` (which generates TIL / post-mortem artifacts in a notes directory). `/learn-this` is for **distilling lessons from what just happened in the session and writing them into the right durable store** so the same mistake / blindspot doesn't recur.

Trigger when:
- A code review (human or bot) pushed back on something that wasn't obviously wrong
- A "surprising fix" worked - a workaround was no longer needed, a refactor revealed a cleaner shape
- Two or more independent findings in the same session shared a common root cause
- The user asks "what's the takeaway here" / "how do we not do this again"

## Step 1 - Deep-think the key learnings

Don't jump to writing. **Before touching any file**, mentally surface:

1. **What is the surface lesson?** The literal thing the reviewer said or the diff did.
2. **What is the deeper lesson?** Strip "use X instead of Y" to the principle underneath. ("Two passes -> one pass" -> "match operation to intent: filter is for keep/drop, not refinement").
3. **Was there a meta-pattern across multiple findings in this session?** If the session had 2+ separate fixes, look for the common root. Often it's "code that worked but wasn't shaped right" or "workaround that calcified".
4. **What was the cost of NOT learning this?** Concrete cost grounds the lesson: rebase conflicts, drift, performance, review churn.
5. **Who flagged it?** Name the reviewer and link the PR. Reviewer attribution helps future-you trust the lesson when it surfaces.

Output this thinking to the user as a short prose section before touching files. Don't bullet-point it to death - the synthesis is the value.

## Step 2 - Classify each learning

For every distinct lesson, pick exactly one home:

| Lesson type | Home | Example |
|---|---|---|
| **Project-specific gotcha** ("in this codebase, don't do X because Y") | Nearest relevant `CLAUDE.md` in the repo (root, `apps/<x>/CLAUDE.md`, `packages/<x>/CLAUDE.md`) | "DON'T hand-mirror workspace modules in test-mocks" -> `apps/mobile/CLAUDE.md` |
| **User preference / reviewer pattern** ("I / a regular reviewer cares about X") | `~/.claude/projects/<project>/memory/feedback_<slug>.md` + index in `MEMORY.md` | "Prefer single-pass filter over chained `.filter().filter()`" |
| **Project state / decision** ("we decided X because Y, valid until Z") | `~/.claude/projects/<project>/memory/project_<slug>.md` + index | "ENG-123 gates the mobile rollout - flag stays OFF until <date>" |
| **External reference pointer** ("Y info lives in Z system") | `~/.claude/projects/<project>/memory/reference_<slug>.md` + index | "Pipeline incidents are tracked in the issue tracker's INGEST project" |
| **Generalisable workflow** (same recipe will reapply 3+ times) | New skill at `~/.claude/skills/<slug>/SKILL.md` | "Run a stack rebase + restack child + force-push-with-lease" |

**Tiebreakers:**
- If a lesson is both project-specific AND a user preference, write to CLAUDE.md (more discoverable for any agent in the repo) and cross-link from memory.
- If the lesson is "this workaround can now go away", write it in CLAUDE.md as a DON'T-do entry, NOT as a project memory - project memories drift fast, anti-patterns in CLAUDE.md stay scoped to the file they're near.
- If unsure between feedback memory and CLAUDE.md, prefer CLAUDE.md when the lesson would apply to anyone on the team, prefer feedback memory when it's specifically about the user's preferences or a single reviewer's pattern.

## Step 3 - Apply updates

For each lesson with its picked home:

### CLAUDE.md updates
- Open the target CLAUDE.md
- Find the right section (`## Anti-Patterns`, `## Gotchas`, etc.)
- Lead with the rule in **bold** (DON'T / DO / ALWAYS), then explain the why, then the prevention pattern
- Reference the PR + ticket that caused the lesson - gives future readers a place to dig if they need context
- Keep entries under 4 lines - long entries get skimmed past

### Memory updates
- Create `<type>_<slug>.md` with proper frontmatter (`name`, `description`, `metadata.type`)
- Body structure for `feedback` / `project`: lead with the rule/fact, then `**Why:**`, then `**How to apply:**`
- Cross-link related memories via `[[name-slug]]`
- Add the one-line pointer to `MEMORY.md` (the index)
- Keep the description specific - generic descriptions don't help future relevance scoring

### Skill promotion (optional)
If the lesson is a generalisable workflow:
- Confirm with the user before creating - skill creation is heavier than a memory entry
- Use `~/.claude/skills/<slug>/SKILL.md` with frontmatter `name`, `description`, `allowed-tools`
- Body: when to trigger -> step-by-step workflow -> guardrails

## Step 4 - Confirm + show diffs

After writing, summarise to the user:
- Which lessons you identified (one line each)
- Where each went (file path + section)
- Any cross-links you set up
- If you promoted a skill, what triggers it

Ask explicitly if anything should move (sometimes a lesson lands in CLAUDE.md but the user prefers memory, or vice versa). Don't ask for confirmation BEFORE writing - show the work, then offer to relocate.

## Step 5 - Don't over-capture

A session can produce many small observations. Only capture the ones that meet ALL of:
- **Non-obvious** - would the next agent / future-you actually trip on this?
- **Surprising or contested** - was the right answer not the first one tried?
- **Durable** - will it still apply in 3 months, or is it ephemeral (current sprint state, in-flight bug)?

If a learning fails any of these, drop it. Memory bloat from "captured everything" is worse than missing one minor lesson.

## What NOT to capture

- Generic programming knowledge (the model already knows it)
- Pure restatements of the diff ("we changed X to Y" - that's the commit message, not a lesson)
- Internal debugging trace ("I tried A first, then B" - process notes, not learning)
- Anything in flight that hasn't actually settled
- Anything that duplicates an existing CLAUDE.md / memory entry - UPDATE instead

## Example invocations

- **"/learn-this"** - distill the last fix-pass into lessons + capture
- **"/learn-this - focus on what the reviewer's feedback taught me"** - narrow scope to a specific reviewer's feedback
- **"/learn-this and consider promoting to a skill"** - explicit ask to evaluate skill-worthiness

## Guardrails

- Never write `Co-Authored-By` lines into anything you capture
- Never delete an existing CLAUDE.md / memory entry - UPDATE it if outdated, ARCHIVE it if obsolete
- Always include a ticket / PR reference for project-specific lessons so context isn't lost
- If a lesson conflicts with an existing entry, surface the conflict to the user before deciding which wins
