---
name: slack
description: Slack workspace interaction - channels, messages, search, users, DMs, reactions. Use when the user asks about Slack messages, wants to search Slack, send messages, read channels, check threads, find users, or any Slack workspace interaction.
argument-hint: search "deploy issue" --limit 10
allowed-tools: Bash, Read, Edit, Write, Agent
---

# Slack Integration

Interact with Slack workspaces - read channels, search messages, send/schedule messages, manage reactions, and more.

> Paths below use `{base}` as shorthand for this skill's base directory.

**Input**: `$ARGUMENTS`

---

## Quick Reference

```bash
CMD="python3 {base}/scripts/slack.py"
```

### Natural Language Mappings

| User says | Command |
|-----------|---------|
| "who am I in slack" | `$CMD me` |
| "list slack channels" | `$CMD channels` |
| "find the #general channel" | `$CMD channels -q general` |
| "show channel info for CXXXXXXXXXX" | `$CMD channel-info CXXXXXXXXXX` |
| "read latest messages in #general" | `$CMD history CXXXXXXXXXX` |
| "read that thread" | `$CMD thread <channel> <thread_ts>` |
| "send a message to #general" | `$CMD send CXXXXXXXXXX "message here"` |
| "reply in thread" | `$CMD send <channel> "reply" --thread-ts <ts>` |
| "search slack for deploy" | `$CMD search "deploy"` |
| "search messages from username about API" | `$CMD search "from:username API"` |
| "list all users" | `$CMD users` |
| "find user alex" | `$CMD users -q alex` |
| "get info on user UXXXXXXXXXX" | `$CMD user-info UXXXXXXXXXX` |
| "add thumbsup reaction" | `$CMD react <channel> <ts> thumbsup` |
| "what reactions on this message" | `$CMD reactions <channel> <ts>` |
| "show pins in #general" | `$CMD pins CXXXXXXXXXX` |
| "list files" | `$CMD files` |
| "DM alex about the deploy" | `$CMD dm <user_id> "message"` |
| "who's in #general" | `$CMD members CXXXXXXXXXX` |
| "get permalink for message" | `$CMD permalink <channel> <ts>` |
| "list bookmarks in channel" | `$CMD bookmarks <channel>` |
| "show custom emoji" | `$CMD emoji` |
| "show my reminders" | `$CMD reminders` |
| "schedule message for 5pm" | `$CMD schedule <channel> "msg" <unix_ts>` |

---

## Commands

### Auth & Discovery

```bash
# Test auth / whoami
$CMD me

# List channels (filter with -q)
$CMD channels
$CMD channels -q engineering
$CMD channels --type public_channel

# Channel details
$CMD channel-info <channel_id>

# Channel members
$CMD members <channel_id>
$CMD members <channel_id> --resolve  # slower, resolves names

# List users (filter with -q)
$CMD users
$CMD users -q alex
$CMD users --include-bots
```

### Reading Messages

```bash
# Channel history
$CMD history <channel_id>
$CMD history <channel_id> --limit 50

# Thread replies
$CMD thread <channel_id> <thread_ts>

# Get message permalink
$CMD permalink <channel_id> <message_ts>
```

### Sending Messages

```bash
# Send to channel
$CMD send <channel_id> "Hello team"

# Reply in thread
$CMD send <channel_id> "Reply text" --thread-ts <ts>

# Update a message
$CMD update <channel_id> <ts> "Updated text"

# Schedule a message (unix timestamp)
$CMD schedule <channel_id> "Reminder" <post_at_unix>

# Direct message
$CMD dm <user_id> "Hey, quick question..."
$CMD dm <user_id>  # just open the DM channel
```

### Search

```bash
# Basic search
$CMD search "deploy issue"

# Search with Slack query syntax
$CMD search "from:username in:#tech after:2026-03-01"
$CMD search "has:link bug fix"

# Sort options
$CMD search "query" --sort score
$CMD search "query" --sort timestamp --sort-dir asc
```

### Reactions & Pins

```bash
# Add reaction
$CMD react <channel_id> <ts> thumbsup

# Get reactions on a message
$CMD reactions <channel_id> <ts>

# List pinned messages
$CMD pins <channel_id>
```

### Files & Bookmarks

```bash
# List files
$CMD files
$CMD files --channel <channel_id>
$CMD files --user <user_id>
$CMD files --type images

# Channel bookmarks
$CMD bookmarks <channel_id>
```

### Misc

```bash
# Custom emoji
$CMD emoji
$CMD emoji -q party

# Reminders
$CMD reminders
```

---

## Slack Search Query Syntax

Slack search supports operators:

| Operator | Example | Description |
|----------|---------|-------------|
| `from:` | `from:username` | Messages from a user |
| `in:` | `in:#tech` | Messages in a channel |
| `to:` | `to:me` | Direct messages to you |
| `has:` | `has:link`, `has:emoji` | Messages with attachments |
| `before:` | `before:2026-03-01` | Before a date |
| `after:` | `after:2026-03-01` | After a date |
| `during:` | `during:march` | During a time period |
| `on:` | `on:2026-03-12` | On a specific date |
| Quotes | `"exact phrase"` | Exact match |
| `-` | `-deploy` | Exclude term |

Combine: `from:username in:#tech after:2026-03-01 "API change"`

---

## Common Workflows

### Check what happened in a channel today
```bash
$CMD history <channel_id> --limit 50
```

### Find and read a specific thread
```bash
$CMD search "topic keywords in:#channel-name"
# Get the channel_id and thread_ts from results
$CMD thread <channel_id> <thread_ts>
```

### Find a user and DM them
```bash
$CMD users -q alex
# Get user_id from results
$CMD dm <user_id> "Hey, about that deploy..."
```

### Search for recent activity from someone
```bash
$CMD search "from:username after:2026-03-11"
```

---

## Global Flags

- `--json` - Raw JSON output (place before subcommand)
- `--limit N` - Number of results (on supported commands)

---

## Setup

### 1. Get a Slack Bot Token

You need a Slack bot token (`xoxb-...`) with these scopes:
- `channels:history`, `channels:read` - read public channels
- `groups:history`, `groups:read` - read private channels
- `chat:write` - send messages
- `search:read` - search messages
- `users:read`, `users:read.email` - read user info
- `reactions:read`, `reactions:write` - manage reactions
- `pins:read` - read pins
- `files:read` - list files
- `bookmarks:read` - read bookmarks
- `im:read`, `im:write`, `im:history` - DMs
- `mpim:read`, `mpim:history` - group DMs
- `reminders:read` - read reminders
- `emoji:read` - custom emoji

Or use a user token (`xoxp-...`) for search and broader access.

### 2. Configure

Add to `~/.claude/settings.json`:
```json
{
  "env": {
    "SLACK_BOT_TOKEN": "xoxb-your-token-here"
  }
}
```

### 3. Verify

```bash
python3 {base}/scripts/slack.py me
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `SLACK_BOT_TOKEN not set` | Missing env var | Add token to `~/.claude/settings.json` |
| `not_authed` | Invalid token | Check token is correct and not expired |
| `channel_not_found` | Bad channel ID | Use `channels` command to find correct ID |
| `missing_scope` | Token lacks permission | Add required OAuth scope to Slack app |
| `ratelimited` | Too many requests | Script auto-retries with backoff |
| `not_in_channel` | Bot not in channel | Invite bot to the channel first |
| `user_not_found` | Bad user ID | Use `users` command to find correct ID |

---

## Self-Healing Protocol

When a command fails unexpectedly:
1. **Diagnose** - Read error output and check the script
2. **Propose** - Describe the fix
3. **Await approval** - Ask user before editing
4. **Apply** - Edit `{base}/scripts/slack.py`
5. **Verify** - Re-run the failed command
