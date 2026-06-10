---
name: learn
description: Generate learning artifacts (mermaid diagrams, TIL notes, decision logs, bug post-mortems) for the current session and save them to your notes directory. Use when finishing a session, or anytime mid-session to capture learnings. Triggers on "generate learnings", "what did I learn", "capture this", or explicitly via /learn.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Bash
  - Grep
  - AskUserQuestion
---

# Learn Skill - Session Learning Artifact Generator

Generate learning artifacts from the current Claude Code session and save them to the user's notes directory (an Obsidian vault, a plain folder of markdown, whatever they use).

## Configuration

<!-- CUSTOMIZE: point NOTES_DIR at your notes location - an Obsidian vault folder, ~/notes, ~/.claude/notes, etc. Artifacts are plain markdown; wikilinks render best in Obsidian but degrade gracefully anywhere. -->

```
NOTES_DIR=~/notes
LEARNING_BASE=$NOTES_DIR/learnings
```

## Step 0: Parse Arguments

Check for optional arguments:

| Command | Behaviour |
|---|---|
| `/learn` | Full run - generate all applicable artifacts |
| `/learn diagram` | Generate mermaid diagram only |
| `/learn til` | Generate TIL note only |
| `/learn decision` | Generate decision log only |
| `/learn postmortem` | Generate bug post-mortem only |
| `/learn all` | Same as full run |

Store as `artifactMode`.

## Step 1: Determine Ticket ID and Output Path

### 1.1: Extract ticket ID

Try these sources in order:
1. **Git branch name** - pattern: `username/TICKET-ID-description` or `TICKET-ID-description` (e.g., `alice/ENG-123`, `ENG-123-fix-auth`)
2. **Recent commits** - check last 5 commit messages for ticket ID patterns (`ENG-###` or similar `XXX-###`)
3. **Ask the user** - if no ticket found: "What's the ticket ID for this session? (or type a slug like 'auth-refactor')"

```bash
git branch --show-current
git log --oneline -5
```

A descriptive slug is a perfectly fine substitute if the user doesn't use an issue tracker.

### 1.2: Set output path

```
OUTPUT_DIR=$LEARNING_BASE/<TICKET-ID>/learnings/
```

Create the directory if it doesn't exist:
```bash
mkdir -p "$OUTPUT_DIR"
```

## Step 2: Analyze Session Context

Review the current conversation to identify what happened:

1. **Code changes made** - what files were modified, what was the goal?
2. **Bugs fixed** - any debugging or bug fixes?
3. **Decisions made** - were there 2+ approaches discussed? Was a choice made?
4. **New concepts encountered** - any patterns, tools, or techniques worth noting?
5. **Architecture/flow changes** - any structural changes that benefit from a diagram?

Categorize into applicable artifact types:
- `diagram` - if architecture, data flow, state machine, or complex logic was involved
- `til` - if new concepts, patterns, or surprising behaviour came up
- `decision` - if 2+ approaches were discussed and one was chosen
- `postmortem` - if a non-trivial bug was investigated and fixed

## Step 3: Generate Artifacts

### 3.1: Common frontmatter

Every artifact starts with:

```yaml
---
type: diagram | til | decision | postmortem
ticket: <TICKET-ID>
date: <YYYY-MM-DD>
topic: <short-topic-slug>
---
```

### 3.2: Generate each applicable artifact

For each applicable type (or only the requested type if `artifactMode` is specific):

#### Mermaid Diagram (`diagram-<topic>.md`)

- Write 1-2 sentences of context explaining what the diagram captures
- Generate the mermaid diagram (flowchart, sequence, state, ER - whichever fits best)
- Add 2-3 key takeaways - what should the reader notice?
- **Diagram types to consider:**
  - `flowchart TD` - for request flows, data pipelines, decision trees
  - `sequenceDiagram` - for API calls, service interactions, async flows
  - `stateDiagram-v2` - for state machines, lifecycle, status transitions
  - `erDiagram` - for data models, relationships
  - `classDiagram` - for component relationships, inheritance
  - `graph LR` - for architecture overviews, system context

#### TIL Note (`til-<topic>.md`)

- One concept per file - keep it atomic
- Include a concrete code example where possible
- Link to related concepts
- These should be genuinely useful for future reference, not just "I used X today"

#### Decision Log (`decision-<topic>.md`)

- Must include at least 2 options with pros/cons
- Each option labelled by what it optimizes for
- Clear statement of what was chosen and why
- Include "what would need to change" for the other option to become the right choice
- Document tradeoffs accepted

#### Bug Post-mortem (`postmortem-<topic>.md`)

- Name the bug class explicitly (race condition, stale closure, off-by-one, type coercion, etc.)
- Explain root cause at the concept level, not just "line X was wrong"
- Include prevention pattern
- Add a mermaid diagram if it helps illustrate the bug (timeline, before/after flow)

### 3.3: Write all artifacts

Write each artifact to `$OUTPUT_DIR/<filename>.md`.

If a file with the same name already exists, append a number: `til-closures-2.md`.

### 3.4: Update the learnings index

After writing artifacts, update `$LEARNING_BASE/MOC-Learnings.md` (create it on first run):
- Add new entries under the relevant topic section
- Format: `- [[artifact-filename]] - brief description (TICKET-ID)`
- If no matching topic section exists, create one

## Step 4: Summary

Present a summary of what was generated:

```
## Learning Artifacts Generated

**Ticket:** ENG-123
**Path:** learnings/ENG-123/learnings/

| Artifact | File | Description |
|---|---|---|
| Diagram | diagram-auth-flow.md | Authentication middleware request flow |
| TIL | til-stale-closures.md | React stale closure gotcha in useEffect |
| Decision | decision-auth-middleware.md | JWT vs session-based auth |
| Post-mortem | postmortem-race-condition.md | Race condition in concurrent API calls |

All artifacts saved to your notes directory.
```

## Step 5: Ask for Additions

After presenting the summary:

```
Anything to add or adjust? You can:
- **Add** - generate additional artifacts I missed
- **Edit** - modify any generated artifact
- **Done** - wrap up
```

## Edge Cases

**No code changes in session:** Still check for TIL and decision artifacts - conversations about architecture or debugging strategy still produce learnings even without code changes.

**Multiple tickets in one session:** Group artifacts by ticket. Create separate folders if needed. Ask user which ticket to associate ambiguous artifacts with.

**Session was just a chat/question:** If genuinely nothing learnable happened (e.g., "what time is it?"), skip gracefully: "No learning artifacts applicable for this session."
