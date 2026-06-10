---
name: focus
description: Manage a cross-session focus tracker (a small markdown file recording what you're actively working on). Use when the user types /focus, /pause, /block, /unblock, /resume, or asks "what am I working on", "what's in flight", "show me my focus", or wants to switch active task.
allowed-tools:
  - Read
  - Edit
  - Bash
---

# Focus Skill

Maintains a cross-session record of what the user is actively working on. Claude Code sessions are ephemeral; the tracker is not - it survives between sessions so any new session can answer "what am I working on?" instantly.

This skill is the **manual control** layer for switching the active task, marking blockers, and reviewing what's in flight.

<!-- CUSTOMIZE: the tracker pairs well with hooks (SessionStart to print the list, Stop to bump last_touched via `cli.sh touch <ticket>`, PostToolUse on `git worktree add` to auto-add entries). The CLI works fine standalone without any hooks. -->

## Tracker location

`~/.claude/focus/active.md` - plain markdown, one `## TICKET - title` section per task with `status` / `worktree` / `last_touched` / `next` / `blocked_by` fields.

<!-- CUSTOMIZE: override the data directory by exporting FOCUS_DIR before calling the CLI. -->

## CLI

All operations go through the bundled CLI at `~/.claude/skills/focus/scripts/cli.sh` (adjust the path if you installed the skill somewhere else). Examples:

```bash
cli.sh list                           # show all entries grouped by status
cli.sh show ENG-123                   # detail one ticket
cli.sh focus ENG-123 "fix login bug"  # set active + next step
cli.sh pause ENG-124                  # pause a task
cli.sh block ENG-125 ENG-200          # mark blocked by another ticket
cli.sh unblock ENG-125                # clear the blocker
cli.sh resume ENG-124                 # set active without auto-pausing others
cli.sh add ENG-999 "title here"       # add new entry
cli.sh done ENG-123                   # mark finished (pruned after 7 days)
cli.sh remove ENG-999                 # drop entry
```

## Sub-command routing

The user may invoke this skill via:

| User typed | Action |
|---|---|
| `/focus` (no args) | Run `cli.sh list`, render the output |
| `/focus <TICKET>` | Run `cli.sh focus <TICKET>` - make this the active task |
| `/focus <TICKET> <next step text>` | Same + capture the next-step note |
| `/pause` | Pause the current cwd's ticket (derive it from the git branch or directory name) |
| `/pause <TICKET>` | Pause that specific ticket |
| `/block <TICKET> <BLOCKER>` | Mark blocked by another ticket |
| `/unblock <TICKET>` | Clear the blocker |
| `/resume <TICKET>` | Resume without auto-pausing others |
| "what am I working on" / "show focus" | Run `cli.sh list` |

## When the user says "switch to X" or "let me work on X"

1. Run `cli.sh focus <TICKET>` to mark it active.
2. Check `cli.sh list` - if 3+ are active, ask if they want to pause the others.
3. If the ticket isn't in the tracker yet, run `cli.sh add <TICKET> "<title>"` first (fetch the title from the issue tracker if one is connected, otherwise ask).
4. Show the resulting list compactly.

## When the user says "I'm blocked on X"

1. Identify which ticket is blocked (cwd ticket if not specified).
2. Identify the blocker ticket ID. If unclear, ask once.
3. Run `cli.sh block <TICKET> <BLOCKER>`.
4. Suggest switching focus: "Switch to a different task while this is blocked?"

## When the user says "done" / "finished" / "PR merged"

1. Run `cli.sh done <TICKET>` - or `cli.sh remove <TICKET>` if they want it gone immediately.
2. `cli.sh prune` removes `done` entries older than 7 days (run it opportunistically, e.g. after a `list`).

## Soft enforcement

Never block the user. The tracker is a mirror, not a gate. If something feels off (e.g. trying to focus a blocked ticket without unblocking first), surface it as a one-line note, then proceed if they want.

## Don't

- Don't write directly to `active.md` - always go through `cli.sh`. The CLI handles the field updates correctly.
- Don't add entries without a real ticket/issue ID (or at least a stable slug) - the tracker is for tracked work, not loose ideas.
- Don't pause/resume without an explicit user request.
