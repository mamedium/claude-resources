---
name: exit
description: Session closing ritual. Finalises learning artifacts, writes a session continuation file for unfinished work, runs custom session-end rituals, and presents a session summary. Use when the user types /exit to end a session.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Bash
  - Grep
---

# Exit Skill - Session Closing Ritual

This skill runs when the user types `/exit` to close their session. It ensures no learnings or in-flight state are lost. Pairs with the `/learn` skill (same artifact types, same notes layout) but works standalone.

## Configuration

<!-- CUSTOMIZE: point NOTES_DIR at your notes location - an Obsidian vault folder, ~/notes, ~/.claude/notes, etc. Keep it identical to the /learn skill's config if you use both. -->

```
NOTES_DIR=~/notes
LEARNING_BASE=$NOTES_DIR/learnings
```

## Step 1: Determine Ticket ID and Output Path

### 1.1: Extract ticket ID

Try these sources in order:
1. **Git branch name** - pattern: `username/TICKET-ID-description` or `TICKET-ID-description` (e.g., `alice/ENG-123`, `ENG-123-fix-auth`)
2. **Recent commits** - check last 5 commit messages for ticket ID patterns (`ENG-###` or similar `XXX-###`)
3. **Use `_general`** if no ticket context (e.g., config-only sessions, dotfiles work)

```bash
git branch --show-current
git log --oneline -5
```

### 1.2: Set output path

```
OUTPUT_DIR=$LEARNING_BASE/<TICKET-ID>/
```

Create the directory if it doesn't exist:
```bash
mkdir -p "$OUTPUT_DIR"
```

## Step 2: Audit Existing Artifacts

Check what learning artifacts already exist for this session's ticket:

```bash
ls "$OUTPUT_DIR"/learnings/*.md 2>/dev/null
```

Categorize into:
- **Already created during session**: Files that were written earlier in this conversation
- **Missing but applicable**: Types that should have been created based on what happened in the session

## Step 3: Review Session Activity

Analyze the current conversation to determine what happened:

1. **Were decisions made between 2+ approaches?** - If yes and no `decision-*.md` exists, generate one
2. **Were architecture/flow/complex logic changes made?** - If yes and no `diagram-*.md` exists, generate one
3. **Were bugs investigated and fixed?** - If yes and no `postmortem-*.md` exists, generate one
4. **Were new concepts, patterns, or surprising behaviour encountered?** - If yes and no `til-*.md` exists, generate one
5. **Were existing artifacts scaffolded but not filled in?** - If yes, fill them in with real content now

### 3.1: Update existing artifacts

For artifacts that were scaffolded earlier in the session but not yet filled:
- Read each placeholder file
- Fill in the content sections with details from the session
- Remove any placeholder text

### 3.2: Generate missing artifacts

For applicable types that don't have a file yet, follow the artifact formats from the `/learn` skill (frontmatter with `type` / `ticket` / `date` / `topic`, then the type-specific content). Write to `$OUTPUT_DIR/learnings/<type>-<topic>.md`.

### 3.3: Update the learnings index

After writing artifacts, update `$LEARNING_BASE/MOC-Learnings.md` (create it on first run):
- Add new entries under the relevant topic section
- Format: `- [[artifact-filename]] - brief description (TICKET-ID)`
- If no matching topic section exists, create one

## Step 4: Custom Session-End Rituals

<!-- CUSTOMIZE: this is the slot for any personal end-of-session habit you want enforced every time. Delete this step if you have none.

Example ritual (what the original author used): generate spaced-repetition flashcards from language corrections given during the session. A per-turn hook flagged non-native English phrasing; at /exit, all corrections were collected into `$OUTPUT_DIR/anki-cards-<YYYY-MM-DD>.md` as a pipe-separated table (Front = the error, Back = correction + brief rule, Tag = category like grammar/word-choice/collocation), ready for Anki's text import. One card per correction, only real corrections from the session - never create an empty file.

Other ideas: append to a daily work log, update a time-tracking note, dump open browser tabs, journal one sentence about how the session went. -->

If a ritual is configured above, run it now. Otherwise skip.

## Step 5: Session Continuation File

Detect whether the session has **remaining tasks** that warrant resuming in a new session (e.g., user is about to run out of context, or explicitly says "let's continue in a new session").

### 5.1: Detect remaining tasks

Scan the current conversation for any of these signals:

1. **Unchecked TodoWrite items** - any task still in `pending` or `in_progress` state
2. **Explicitly deferred work** - phrases like "let's do that next session", "TODO:", "skip for now", "come back to this", "park it", "follow-up"
3. **Ticket acceptance criteria not yet implemented** - if an issue tracker is connected, fetch the ticket (from the ID detected in Step 1) and compare acceptance criteria against what was actually done this session
4. **Unresolved blockers** - failing tests, unresolved errors, unaddressed PR review comments, lint/type errors left open
5. **User explicitly asks to continue later** - e.g., "I need to start a new session", "context is almost full, let's wrap up", "save state so I can resume"

If **none** of these exist, **skip this step entirely** - do not create or update a continuation file.

### 5.2: Write/update the continuation file

Path: `$LEARNING_BASE/<TICKET-ID>/continuation.md` (sibling of `learnings/`, one file per ticket, **always overwrite** with the latest state).

```bash
mkdir -p "$LEARNING_BASE/<TICKET-ID>"
```

File format:

```markdown
---
type: session-continuation
ticket: <TICKET-ID>
updated: <YYYY-MM-DD HH:MM>
branch: <current-git-branch>
---

# Session Continuation - <TICKET-ID>

## Where We Left Off
<1-3 sentences: what was the last meaningful state of the work>

## Remaining Tasks
- [ ] <task 1 - from todos / deferred work / AC / blockers>
- [ ] <task 2>
- [ ] <task 3>

## Context You'll Need
- **Branch**: `<branch-name>`
- **Key files touched**: `<path:line>`, `<path:line>`
- **Decisions already made**: <brief recap or link to decision-*.md>
- **Blockers/gotchas**: <anything that bit us this session and might bite next session>

## Resume Prompt

Copy-paste this into a new Claude Code session to continue:

\`\`\`
Resume work on <TICKET-ID>. Read the continuation file first:

<absolute-path-to-continuation.md>

It contains remaining tasks, context, and where we left off. After reading it,
give me a 3-line status recap and wait for my go-ahead before making changes.
\`\`\`
```

### 5.3: Notes

- **Always overwrite** the file - it represents the *latest* state, not a history.
- The resume prompt must include the **absolute path** to the continuation file so the new session can `Read` it directly.
- Keep "Remaining Tasks" concrete and actionable - no vague items like "polish things".
- If a ticket's acceptance criteria was the source of a remaining task, prefix it with `[AC]` so future-you knows it's a hard requirement.

## Step 6: Process Cleanup

<!-- CUSTOMIZE: list any MCP servers or helper processes your sessions tend to orphan. Check with `ps aux | grep mcp` after a few sessions to find yours. -->

```bash
pkill -f "@playwright/mcp" 2>/dev/null || true
```

## Step 7: Session Summary

Present a final summary:

```
## Session Complete

**Ticket:** <TICKET-ID>
**Artifacts path:** learnings/<TICKET-ID>/

### Learning Artifacts
| Status | Type | File | Description |
|---|---|---|---|
| <created/updated/skipped> | Diagram | diagram-<topic>.md | <brief desc> |
| <created/updated/skipped> | TIL | til-<topic>.md | <brief desc> |
| <created/updated/skipped> | Decision | decision-<topic>.md | <brief desc> |
| <created/updated/skipped> | Post-mortem | postmortem-<topic>.md | <brief desc> |

### Rituals
<output of any custom session-end rituals, or "None configured">

### Session Continuation
<"N remaining tasks saved to `<absolute-path-to-continuation.md>` - paste the resume prompt from that file into a new session to pick up where you left off"> (or "No remaining tasks - session fully wrapped")

### Cleanup
Orphaned processes cleaned up.

---
Session closed. See you next time!
```

## Edge Cases

**Session had no code/problem-solving work:** If the session was purely conversational (e.g., discussing config, asking questions), skip learning artifacts entirely. Still run custom rituals and cleanup.

**Session was in a non-work repo (e.g., ~/.claude):** Use `_general` as the folder name instead of a ticket ID. Learning artifacts still apply if concepts were discussed.

**Multiple tickets in one session:** If the session clearly worked on multiple tickets, generate artifacts per ticket in their respective folders. Ask which ticket to associate ambiguous artifacts with.

**Artifacts were already fully generated during the session:** If `/learn` was already run and all artifacts are up to date, just confirm they're complete and move on to rituals + cleanup.
