---
name: mac-health
description: Inspect macOS RAM pressure and disk usage. Reports memory hogs, orphaned MCP servers from prior Claude Code sessions, and disk-eating caches, then prints the exact shell commands to reclaim resources. Use when the user asks about RAM, memory pressure, slow Mac, orphaned processes, disk space, or "mac is full".
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# mac-health

Read-only macOS inspector. Reports RAM pressure and disk usage, then **prints copy-paste commands** the user can run themselves. The skill never kills processes or deletes files on its own.

## Setup

```
MAC="python3 {base}/scripts/mac_health.py"
```

Where `{base}` is this skill's directory.

## Usage

Two subcommands:

- `$MAC ram` — memory pressure snapshot, top 15 processes by RSS, orphaned MCP scan
- `$MAC storage` — `df -h` overview + sizes of system caches, Xcode DerivedData, package manager caches, Homebrew, Trash, Downloads >30d

Both subcommands are **read-only**. They run `ps`, `vm_stat`, `memory_pressure`, `sysctl`, `du`, `df`, `pgrep`, `find`, `xcrun simctl list`, `brew --cache` only. No `kill`, no `rm`, no `prune`, no `clean`.

## Workflow

1. Run the relevant subcommand via `Bash`:
   - User says "check RAM" / "my Mac is slow" / "orphaned MCPs?" → `$MAC ram`
   - User says "check storage" / "disk is full" / "what's eating space?" → `$MAC storage`
   - User says "full health check" → run both.
2. Summarise the report for the user in chat — call out anything above a reasonable threshold (e.g. top RSS process > 2 GB, any orphaned MCPs, any category > 1 GB).
3. Use `AskUserQuestion` to let them pick which printed command(s) they want to run:
   - Options should be the actual commands from the report (or "skip / I'll run them myself" / "list Downloads >30d individually" / similar).
   - Multi-select is fine.
4. For each command the user picks, **show the command again and ask explicit confirmation before executing**. Then run via `Bash`. Never batch-execute without per-command confirmation.
5. If the user says "just give me the list" or "I'll run them myself", stop at step 2 — do NOT run anything. Matches the CLAUDE.md policy of letting the user pull the trigger.

## Safety rules

- The script itself is read-only. It never calls `kill`, `rm`, `prune`, or any destructive action — verifiable by grepping `mac_health.py` for those strings.
- Hardcoded blocklists in `mac_health.py`:
  - `HARD_PROTECTED_ROOTS` — Obsidian vault, `~/.claude`, `~/Documents`, `~/Desktop`, `~/Library/Mobile Documents` (iCloud), `/System`, `/Library`, `/usr`, `/bin`, `/sbin`. Any suggested delete command targeting these roots is replaced with `(protected — skipped)`.
  - `BLOCKED_PROCESS_NAMES` — `launchd`, `kernel_task`, `WindowServer`, `loginwindow`, `bash`, `zsh`, `tmux`, `sshd`, `Finder`, etc. Plus PIDs < 500 and the current Claude Code process tree (walked via `ps -o ppid=`). These show `(protected)` instead of a `kill` suggestion.
- When Claude executes a command on behalf of the user (step 4 above), it must:
  - Show the exact command.
  - Get explicit yes-per-command confirmation in chat.
  - Never chain multiple destructive commands in a single `Bash` call.
  - Never run anything touching paths in `HARD_PROTECTED_ROOTS`, even if the user asks — refuse and explain.

## Notes on macOS quirks the script handles

- `ps -Ao pid,rss,comm -m` sorts by memory. `-r` on BSD sorts by CPU — do not use it for RSS ranking.
- `pgrep -Eaf '<pattern>'` needs `-E` for regex alternation on BSD. `pgrep -af 'a\|b'` silently matches nothing.
- `memory_pressure` can be chatty; the script parses only the "System-wide memory free percentage" line.
- `du` targets are explicit paths, never `du -x ~` — iCloud / Google Drive mounts under `~` make that hang or inflate.
