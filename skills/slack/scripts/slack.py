#!/usr/bin/env python3
"""Slack CLI - interact with Slack workspaces via the Slack Web API."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# --- Helpers ----------------------------------------------------------------

BASE_URL = "https://slack.com/api"
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKENS_FILE = os.path.join(SKILL_DIR, ".tokens.json")


def _load_tokens():
    """Load tokens from local cache file."""
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as f:
            return json.load(f)
    return {}


def _save_tokens(access_token, refresh_token):
    """Persist tokens to local cache file."""
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "updated_at": datetime.now().isoformat(),
    }
    with open(TOKENS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def _refresh_token(refresh_tok):
    """Rotate tokens via tooling.tokens.rotate. Returns (new_access, new_refresh)."""
    url = f"{BASE_URL}/tooling.tokens.rotate"
    body = urllib.parse.urlencode({"refresh_token": refresh_tok}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                new_access = result["token"]
                new_refresh = result["refresh_token"]
                _save_tokens(new_access, new_refresh)
                print("Token refreshed successfully.", file=sys.stderr)
                return new_access, new_refresh
            else:
                print(f"Token refresh failed: {result.get('error')}", file=sys.stderr)
                return None, None
    except Exception as e:
        print(f"Token refresh error: {e}", file=sys.stderr)
        return None, None


def get_token():
    """Get access token. Priority: cached file > env var."""
    cached = _load_tokens()
    token = cached.get("access_token")
    if token:
        return token

    token = os.environ.get("SLACK_BOT_TOKEN") or os.environ.get("SLACK_TOKEN")
    if not token:
        print("Error: No Slack token found.", file=sys.stderr)
        print("Run the skill setup or add SLACK_BOT_TOKEN to ~/.claude/settings.json", file=sys.stderr)
        sys.exit(1)

    # Seed the cache from env var
    refresh = os.environ.get("SLACK_REFRESH_TOKEN", "")
    if refresh:
        _save_tokens(token, refresh)

    return token


def get_refresh_token():
    """Get refresh token from cache or env."""
    cached = _load_tokens()
    token = cached.get("refresh_token")
    if token:
        return token
    return os.environ.get("SLACK_REFRESH_TOKEN", "")


def _raw_api_call(method, endpoint, token, body=None, params=None):
    """Single API call attempt. Returns (result_dict, error_string_or_None)."""
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        if not result.get("ok"):
            return result, result.get("error", "unknown_error")
        return result, None


def api(method, endpoint, body=None, params=None):
    """Make a Slack Web API request with auto-refresh and retry logic."""
    token = get_token()

    for attempt in range(4):
        try:
            result, err = _raw_api_call(method, endpoint, token, body, params)

            if err in ("token_expired", "invalid_auth", "token_revoked"):
                refresh_tok = get_refresh_token()
                if refresh_tok:
                    print(f"Token expired. Refreshing...", file=sys.stderr)
                    new_access, _ = _refresh_token(refresh_tok)
                    if new_access:
                        token = new_access
                        continue
                print(f"Slack API error: {err} (refresh failed or no refresh token)", file=sys.stderr)
                sys.exit(1)

            if err:
                print(f"Slack API error: {err}", file=sys.stderr)
                if result.get("response_metadata", {}).get("messages"):
                    for msg in result["response_metadata"]["messages"]:
                        print(f"  {msg}", file=sys.stderr)
                sys.exit(1)

            return result

        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", 2 ** attempt))
                print(f"Rate limited. Retrying in {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue
            body_text = e.read().decode("utf-8", errors="replace")
            print(f"HTTP {e.code}: {body_text}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"Connection error: {e.reason}", file=sys.stderr)
            sys.exit(1)

    print("Max retries exceeded", file=sys.stderr)
    sys.exit(1)


def fmt_json(data):
    print(json.dumps(data, indent=2))


def fmt_table(rows, columns):
    """Print aligned table."""
    if not rows:
        print("(no results)")
        return

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], min(len(val), 80))

    # Header
    header = "  ".join(col.upper().ljust(widths[col]) for col in columns)
    print(header)
    print("  ".join("-" * widths[col] for col in columns))

    # Rows
    for row in rows:
        line = "  ".join(
            truncate(str(row.get(col, "")), widths[col]).ljust(widths[col])
            for col in columns
        )
        print(line)


def truncate(s, n=80):
    s = str(s or "")
    return s[: n - 3] + "..." if len(s) > n else s


def ts_to_dt(ts):
    """Convert Slack timestamp to readable datetime."""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return str(ts)


# --- Commands ---------------------------------------------------------------


def cmd_me(args):
    """Test auth and show current bot/user info."""
    result = api("POST", "auth.test")
    if args.json:
        fmt_json(result)
        return
    print(f"User:      {result.get('user', 'N/A')}")
    print(f"User ID:   {result.get('user_id', 'N/A')}")
    print(f"Team:      {result.get('team', 'N/A')}")
    print(f"Team ID:   {result.get('team_id', 'N/A')}")
    print(f"URL:       {result.get('url', 'N/A')}")


def cmd_channels(args):
    """List channels in the workspace."""
    params = {"limit": args.limit, "exclude_archived": "true"}
    if args.type:
        params["types"] = args.type
    else:
        params["types"] = "public_channel,private_channel"

    result = api("GET", "conversations.list", params=params)
    channels = result.get("channels", [])

    if args.query:
        q = args.query.lower()
        channels = [c for c in channels if q in (c.get("name", "") or "").lower()]

    if args.json:
        fmt_json(channels)
        return

    rows = []
    for ch in channels:
        rows.append(
            {
                "id": ch.get("id", ""),
                "name": f"#{ch.get('name', '')}",
                "members": ch.get("num_members", ""),
                "topic": truncate(
                    (ch.get("topic", {}) or {}).get("value", ""), 50
                ),
            }
        )
    fmt_table(rows, ["id", "name", "members", "topic"])


def cmd_channel_info(args):
    """Get detailed info about a channel."""
    result = api("GET", "conversations.info", params={"channel": args.channel})
    ch = result.get("channel", {})

    if args.json:
        fmt_json(ch)
        return

    print(f"Name:       #{ch.get('name', 'N/A')}")
    print(f"ID:         {ch.get('id', 'N/A')}")
    print(f"Created:    {ts_to_dt(ch.get('created', ''))}")
    print(f"Members:    {ch.get('num_members', 'N/A')}")
    print(f"Private:    {ch.get('is_private', False)}")
    print(f"Archived:   {ch.get('is_archived', False)}")
    topic = (ch.get("topic", {}) or {}).get("value", "")
    purpose = (ch.get("purpose", {}) or {}).get("value", "")
    if topic:
        print(f"Topic:      {topic}")
    if purpose:
        print(f"Purpose:    {purpose}")


def cmd_history(args):
    """Read messages from a channel."""
    params = {"channel": args.channel, "limit": args.limit}
    if args.oldest:
        params["oldest"] = args.oldest
    if args.latest:
        params["latest"] = args.latest

    result = api("GET", "conversations.history", params=params)
    messages = result.get("messages", [])

    if args.json:
        fmt_json(messages)
        return

    for msg in reversed(messages):
        ts = ts_to_dt(msg.get("ts", ""))
        user = msg.get("user", msg.get("bot_id", "bot"))
        text = msg.get("text", "")
        thread_ts = msg.get("thread_ts", "")
        reply_count = msg.get("reply_count", 0)

        thread_indicator = f" [{reply_count} replies]" if reply_count else ""
        print(f"[{ts}] <{user}>{thread_indicator}")
        print(f"  {text[:500]}")
        if thread_ts and thread_ts == msg.get("ts"):
            print(f"  thread_ts: {thread_ts}")
        print()


def cmd_thread(args):
    """Read thread replies."""
    params = {"channel": args.channel, "ts": args.ts, "limit": args.limit}

    result = api("GET", "conversations.replies", params=params)
    messages = result.get("messages", [])

    if args.json:
        fmt_json(messages)
        return

    for msg in messages:
        ts = ts_to_dt(msg.get("ts", ""))
        user = msg.get("user", msg.get("bot_id", "bot"))
        text = msg.get("text", "")
        print(f"[{ts}] <{user}>")
        print(f"  {text[:500]}")
        print()


def cmd_send(args):
    """Send a message to a channel."""
    body = {"channel": args.channel, "text": args.text}
    if args.thread_ts:
        body["thread_ts"] = args.thread_ts
    if args.unfurl_links is not None:
        body["unfurl_links"] = args.unfurl_links
    if args.unfurl_media is not None:
        body["unfurl_media"] = args.unfurl_media

    result = api("POST", "chat.postMessage", body=body)

    if args.json:
        fmt_json(result)
        return

    ts = result.get("ts", "")
    ch = result.get("channel", "")
    print(f"Message sent to {ch} (ts: {ts})")


def cmd_schedule(args):
    """Schedule a message."""
    body = {
        "channel": args.channel,
        "text": args.text,
        "post_at": args.post_at,
    }
    if args.thread_ts:
        body["thread_ts"] = args.thread_ts

    result = api("POST", "chat.scheduleMessage", body=body)

    if args.json:
        fmt_json(result)
        return

    msg_id = result.get("scheduled_message_id", "")
    print(f"Scheduled message ID: {msg_id}")
    print(f"Post at: {ts_to_dt(args.post_at)}")


def cmd_update(args):
    """Update a message."""
    body = {"channel": args.channel, "ts": args.ts, "text": args.text}

    result = api("POST", "chat.update", body=body)

    if args.json:
        fmt_json(result)
        return

    print(f"Message updated (ts: {result.get('ts', '')})")


def cmd_search(args):
    """Search messages."""
    params = {"query": args.query, "count": args.limit, "sort": args.sort or "timestamp"}
    if args.sort_dir:
        params["sort_dir"] = args.sort_dir

    result = api("GET", "search.messages", params=params)

    if args.json:
        fmt_json(result)
        return

    matches = result.get("messages", {}).get("matches", [])
    total = result.get("messages", {}).get("total", 0)
    print(f"Found {total} results (showing {len(matches)}):\n")

    for msg in matches:
        ts = ts_to_dt(msg.get("ts", ""))
        user = msg.get("user", msg.get("username", "unknown"))
        channel_name = msg.get("channel", {}).get("name", "unknown")
        channel_id = msg.get("channel", {}).get("id", "")
        text = truncate(msg.get("text", ""), 200)
        permalink = msg.get("permalink", "")

        print(f"[{ts}] #{channel_name} ({channel_id}) <{user}>")
        print(f"  {text}")
        if permalink:
            print(f"  {permalink}")
        print()


def cmd_users(args):
    """List or search users."""
    params = {"limit": args.limit}

    result = api("GET", "users.list", params=params)
    members = result.get("members", [])

    # Filter out bots and deleted unless requested
    if not args.include_bots:
        members = [m for m in members if not m.get("is_bot") and not m.get("deleted")]

    if args.query:
        q = args.query.lower()
        members = [
            m
            for m in members
            if q in (m.get("name", "") or "").lower()
            or q in (m.get("real_name", "") or "").lower()
            or q in (m.get("profile", {}).get("display_name", "") or "").lower()
        ]

    if args.json:
        fmt_json(members)
        return

    rows = []
    for m in members:
        rows.append(
            {
                "id": m.get("id", ""),
                "name": m.get("name", ""),
                "real_name": m.get("real_name", ""),
                "display": m.get("profile", {}).get("display_name", ""),
                "status": truncate(
                    m.get("profile", {}).get("status_text", ""), 30
                ),
            }
        )
    fmt_table(rows, ["id", "name", "real_name", "display", "status"])


def cmd_user_info(args):
    """Get info about a specific user."""
    result = api("GET", "users.info", params={"user": args.user})
    user = result.get("user", {})
    profile = user.get("profile", {})

    if args.json:
        fmt_json(user)
        return

    print(f"Name:       {user.get('real_name', 'N/A')}")
    print(f"ID:         {user.get('id', 'N/A')}")
    print(f"Username:   @{user.get('name', 'N/A')}")
    print(f"Display:    {profile.get('display_name', 'N/A')}")
    print(f"Email:      {profile.get('email', 'N/A')}")
    print(f"Title:      {profile.get('title', 'N/A')}")
    print(f"Phone:      {profile.get('phone', 'N/A')}")
    print(f"Status:     {profile.get('status_emoji', '')} {profile.get('status_text', '')}")
    print(f"Timezone:   {user.get('tz_label', 'N/A')}")
    print(f"Bot:        {user.get('is_bot', False)}")
    print(f"Admin:      {user.get('is_admin', False)}")


def cmd_react(args):
    """Add a reaction to a message."""
    body = {"channel": args.channel, "timestamp": args.ts, "name": args.emoji}

    result = api("POST", "reactions.add", body=body)

    if args.json:
        fmt_json(result)
        return

    print(f"Added :{args.emoji}: reaction")


def cmd_reactions(args):
    """Get reactions on a message."""
    params = {"channel": args.channel, "timestamp": args.ts, "full": "true"}

    result = api("GET", "reactions.get", params=params)

    if args.json:
        fmt_json(result)
        return

    msg = result.get("message", {})
    reactions_list = msg.get("reactions", [])
    if not reactions_list:
        print("No reactions on this message.")
        return

    for r in reactions_list:
        users = ", ".join(r.get("users", []))
        print(f"  :{r.get('name', '')}: ({r.get('count', 0)}) - {users}")


def cmd_pins(args):
    """List pins in a channel."""
    result = api("GET", "pins.list", params={"channel": args.channel})
    items = result.get("items", [])

    if args.json:
        fmt_json(items)
        return

    if not items:
        print("No pins in this channel.")
        return

    for item in items:
        msg = item.get("message", {})
        ts = ts_to_dt(msg.get("ts", ""))
        user = msg.get("user", "unknown")
        text = truncate(msg.get("text", ""), 100)
        print(f"[{ts}] <{user}>")
        print(f"  {text}")
        print()


def cmd_files(args):
    """List files."""
    params = {"count": args.limit}
    if args.channel:
        params["channel"] = args.channel
    if args.user:
        params["user"] = args.user
    if args.type:
        params["types"] = args.type

    result = api("GET", "files.list", params=params)
    files = result.get("files", [])

    if args.json:
        fmt_json(files)
        return

    rows = []
    for f in files:
        rows.append(
            {
                "id": f.get("id", ""),
                "name": truncate(f.get("name", ""), 40),
                "type": f.get("filetype", ""),
                "size": f"{f.get('size', 0) // 1024}KB",
                "created": ts_to_dt(f.get("created", "")),
                "user": f.get("user", ""),
            }
        )
    fmt_table(rows, ["id", "name", "type", "size", "created", "user"])


def cmd_dm(args):
    """Open a DM with a user and optionally send a message."""
    # Open DM channel
    result = api("POST", "conversations.open", body={"users": args.user})
    channel = result.get("channel", {})
    channel_id = channel.get("id", "")

    if not args.text:
        if args.json:
            fmt_json(channel)
            return
        print(f"DM channel: {channel_id}")
        return

    # Send message
    body = {"channel": channel_id, "text": args.text}
    result = api("POST", "chat.postMessage", body=body)

    if args.json:
        fmt_json(result)
        return

    print(f"DM sent to {args.user} in {channel_id} (ts: {result.get('ts', '')})")


def cmd_members(args):
    """List members of a channel."""
    params = {"channel": args.channel, "limit": args.limit}

    result = api("GET", "conversations.members", params=params)
    member_ids = result.get("members", [])

    if args.json:
        fmt_json(member_ids)
        return

    if args.resolve:
        # Resolve user IDs to names
        rows = []
        for uid in member_ids:
            try:
                u = api("GET", "users.info", params={"user": uid})
                user = u.get("user", {})
                rows.append(
                    {
                        "id": uid,
                        "name": user.get("name", ""),
                        "real_name": user.get("real_name", ""),
                    }
                )
            except SystemExit:
                rows.append({"id": uid, "name": "?", "real_name": "?"})
        fmt_table(rows, ["id", "name", "real_name"])
    else:
        for uid in member_ids:
            print(uid)


def cmd_permalink(args):
    """Get permalink for a message."""
    params = {"channel": args.channel, "message_ts": args.ts}
    result = api("GET", "chat.getPermalink", params=params)

    if args.json:
        fmt_json(result)
        return

    print(result.get("permalink", ""))


def cmd_bookmarks(args):
    """List bookmarks in a channel."""
    result = api("POST", "bookmarks.list", body={"channel_id": args.channel})
    bookmarks = result.get("bookmarks", [])

    if args.json:
        fmt_json(bookmarks)
        return

    if not bookmarks:
        print("No bookmarks in this channel.")
        return

    rows = []
    for b in bookmarks:
        rows.append(
            {
                "title": truncate(b.get("title", ""), 40),
                "type": b.get("type", ""),
                "link": truncate(b.get("link", ""), 60),
                "created": ts_to_dt(b.get("date_created", "")),
            }
        )
    fmt_table(rows, ["title", "type", "link", "created"])


def cmd_emoji(args):
    """List custom emoji."""
    result = api("GET", "emoji.list")
    emoji_map = result.get("emoji", {})

    if args.json:
        fmt_json(emoji_map)
        return

    if args.query:
        q = args.query.lower()
        emoji_map = {k: v for k, v in emoji_map.items() if q in k.lower()}

    for name, url in sorted(emoji_map.items()):
        if url.startswith("alias:"):
            print(f"  :{name}: -> {url}")
        else:
            print(f"  :{name}:")


def cmd_reminders(args):
    """List reminders."""
    result = api("GET", "reminders.list")
    reminders = result.get("reminders", [])

    if args.json:
        fmt_json(reminders)
        return

    rows = []
    for r in reminders:
        rows.append(
            {
                "id": r.get("id", ""),
                "text": truncate(r.get("text", ""), 50),
                "time": ts_to_dt(r.get("time", "")),
                "complete": r.get("complete_ts", 0) > 0,
            }
        )
    fmt_table(rows, ["id", "text", "time", "complete"])


# --- CLI Parser -------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Slack CLI - interact with Slack via the Web API"
    )
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # me
    sub.add_parser("me", help="Show current auth info")

    # channels
    p = sub.add_parser("channels", help="List channels")
    p.add_argument("-q", "--query", help="Filter by name")
    p.add_argument("--type", help="Channel types (public_channel,private_channel,mpim,im)")
    p.add_argument("--limit", type=int, default=100, help="Max results")

    # channel-info
    p = sub.add_parser("channel-info", help="Get channel details")
    p.add_argument("channel", help="Channel ID")

    # history
    p = sub.add_parser("history", help="Read channel messages")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("--limit", type=int, default=25, help="Max messages")
    p.add_argument("--oldest", help="Start timestamp")
    p.add_argument("--latest", help="End timestamp")

    # thread
    p = sub.add_parser("thread", help="Read thread replies")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("ts", help="Thread timestamp")
    p.add_argument("--limit", type=int, default=50, help="Max replies")

    # send
    p = sub.add_parser("send", help="Send a message")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("text", help="Message text")
    p.add_argument("--thread-ts", help="Reply in thread")
    p.add_argument("--unfurl-links", type=bool, default=None)
    p.add_argument("--unfurl-media", type=bool, default=None)

    # schedule
    p = sub.add_parser("schedule", help="Schedule a message")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("text", help="Message text")
    p.add_argument("post_at", help="Unix timestamp to post at")
    p.add_argument("--thread-ts", help="Reply in thread")

    # update
    p = sub.add_parser("update", help="Update a message")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("ts", help="Message timestamp")
    p.add_argument("text", help="New message text")

    # search
    p = sub.add_parser("search", help="Search messages")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=20, help="Max results")
    p.add_argument("--sort", choices=["timestamp", "score"], default="timestamp")
    p.add_argument("--sort-dir", choices=["asc", "desc"])

    # users
    p = sub.add_parser("users", help="List or search users")
    p.add_argument("-q", "--query", help="Filter by name")
    p.add_argument("--include-bots", action="store_true", help="Include bots")
    p.add_argument("--limit", type=int, default=200, help="Max results")

    # user-info
    p = sub.add_parser("user-info", help="Get user details")
    p.add_argument("user", help="User ID")

    # react
    p = sub.add_parser("react", help="Add a reaction")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("ts", help="Message timestamp")
    p.add_argument("emoji", help="Emoji name (without colons)")

    # reactions
    p = sub.add_parser("reactions", help="Get reactions on a message")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("ts", help="Message timestamp")

    # pins
    p = sub.add_parser("pins", help="List pins in a channel")
    p.add_argument("channel", help="Channel ID")

    # files
    p = sub.add_parser("files", help="List files")
    p.add_argument("--channel", help="Filter by channel")
    p.add_argument("--user", help="Filter by user")
    p.add_argument("--type", help="File types (images,pdfs,docs,etc)")
    p.add_argument("--limit", type=int, default=25, help="Max results")

    # dm
    p = sub.add_parser("dm", help="Open DM / send direct message")
    p.add_argument("user", help="User ID")
    p.add_argument("text", nargs="?", help="Message to send (omit to just open)")

    # members
    p = sub.add_parser("members", help="List channel members")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("--resolve", action="store_true", help="Resolve to names (slow)")
    p.add_argument("--limit", type=int, default=100, help="Max results")

    # permalink
    p = sub.add_parser("permalink", help="Get message permalink")
    p.add_argument("channel", help="Channel ID")
    p.add_argument("ts", help="Message timestamp")

    # bookmarks
    p = sub.add_parser("bookmarks", help="List channel bookmarks")
    p.add_argument("channel", help="Channel ID")

    # emoji
    p = sub.add_parser("emoji", help="List custom emoji")
    p.add_argument("-q", "--query", help="Filter by name")

    # reminders
    sub.add_parser("reminders", help="List reminders")

    return parser


DISPATCH = {
    "me": cmd_me,
    "channels": cmd_channels,
    "channel-info": cmd_channel_info,
    "history": cmd_history,
    "thread": cmd_thread,
    "send": cmd_send,
    "schedule": cmd_schedule,
    "update": cmd_update,
    "search": cmd_search,
    "users": cmd_users,
    "user-info": cmd_user_info,
    "react": cmd_react,
    "reactions": cmd_reactions,
    "pins": cmd_pins,
    "files": cmd_files,
    "dm": cmd_dm,
    "members": cmd_members,
    "permalink": cmd_permalink,
    "bookmarks": cmd_bookmarks,
    "emoji": cmd_emoji,
    "reminders": cmd_reminders,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    fn = DISPATCH.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
