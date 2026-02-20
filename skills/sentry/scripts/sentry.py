#!/usr/bin/env python3
"""Sentry CLI - error tracking and performance monitoring via Sentry REST API."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


# --- Helpers ----------------------------------------------------------------


def get_token():
    token = os.environ.get("SENTRY_AUTH_TOKEN")
    if not token:
        print("Error: SENTRY_AUTH_TOKEN not set", file=sys.stderr)
        print("Add to ~/.claude/settings.json:", file=sys.stderr)
        print('  {"env": {"SENTRY_AUTH_TOKEN": "sntrys_..."}}', file=sys.stderr)
        print(
            "\nGet token at: https://sentry.io/settings/account/api/auth-tokens/",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def get_host():
    return os.environ.get("SENTRY_HOST", "sentry.io")


def api(method, path, body=None, params=None):
    """Make a Sentry API request with retry logic."""
    token = get_token()
    host = get_host()
    base = f"https://{host}/api/0"
    url = f"{base}{path}"

    if params:
        # Handle repeated params like field[]=foo&field[]=bar
        parts = []
        for k, v in params.items():
            if isinstance(v, list):
                for item in v:
                    parts.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(item))}")
            elif v is not None:
                parts.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}")
        if parts:
            url += "?" + "&".join(parts)

    data = json.dumps(body).encode("utf-8") if body else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(2**attempt, 10)
                print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            print(f"HTTP {e.code}: {e.reason}", file=sys.stderr)
            if error_body:
                print(error_body, file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"Connection error: {e.reason}", file=sys.stderr)
            sys.exit(1)
    print("Max retries exceeded", file=sys.stderr)
    sys.exit(1)


def fmt_json(data):
    print(json.dumps(data, indent=2))


def fmt_table(rows, columns):
    """Print a simple aligned table."""
    if not rows:
        print("No results.")
        return
    widths = {c: len(c) for c in columns}
    for row in rows:
        for c in columns:
            val = str(row.get(c, ""))
            widths[c] = max(widths[c], min(len(val), 60))
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("-+-".join("-" * widths[c] for c in columns))
    for row in rows:
        line = " | ".join(str(row.get(c, "")).ljust(widths[c])[:60] for c in columns)
        print(line)


def truncate(s, n=80):
    s = str(s or "")
    return s[:n] + "..." if len(s) > n else s


# --- Commands: Auth & Discovery ---------------------------------------------


def cmd_whoami(args):
    data = api("GET", "/auth/")
    if args.json:
        fmt_json(data)
        return
    print(f"Name:  {data.get('name', 'N/A')}")
    print(f"Email: {data.get('email', 'N/A')}")
    print(f"ID:    {data.get('id', 'N/A')}")


def cmd_orgs(args):
    params = {"per_page": args.limit}
    if args.query:
        params["query"] = args.query
    data = api("GET", "/organizations/", params=params)
    if args.json:
        fmt_json(data)
        return
    rows = [{"slug": o["slug"], "name": o.get("name", ""), "id": o["id"]} for o in data]
    fmt_table(rows, ["slug", "name", "id"])


def cmd_teams(args):
    params = {"per_page": args.limit}
    if args.query:
        params["query"] = args.query
    data = api("GET", f"/organizations/{args.org}/teams/", params=params)
    if args.json:
        fmt_json(data)
        return
    rows = [{"slug": t["slug"], "name": t.get("name", ""), "id": t["id"]} for t in data]
    fmt_table(rows, ["slug", "name", "id"])


def cmd_projects(args):
    params = {"per_page": args.limit}
    if args.query:
        params["query"] = args.query
    data = api("GET", f"/organizations/{args.org}/projects/", params=params)
    if args.json:
        fmt_json(data)
        return
    rows = [
        {
            "slug": p["slug"],
            "name": p.get("name", ""),
            "platform": p.get("platform", ""),
            "id": p["id"],
        }
        for p in data
    ]
    fmt_table(rows, ["slug", "name", "platform", "id"])


def cmd_releases(args):
    params = {"per_page": args.limit}
    if args.query:
        params["query"] = args.query
    if args.project:
        path = f"/projects/{args.org}/{args.project}/releases/"
    else:
        path = f"/organizations/{args.org}/releases/"
    data = api("GET", path, params=params)
    if args.json:
        fmt_json(data)
        return
    rows = [
        {
            "version": truncate(r.get("version", ""), 40),
            "date": (r.get("dateCreated") or "")[:19],
            "projects": ",".join(p["slug"] for p in r.get("projects", [])),
        }
        for r in data
    ]
    fmt_table(rows, ["version", "date", "projects"])


# --- Commands: Issues -------------------------------------------------------


def cmd_issues(args):
    params = {
        "per_page": args.limit,
        "sort": args.sort or "date",
        "collapse": "unhandled",
    }
    if args.query:
        params["query"] = args.query
    if args.period:
        params["statsPeriod"] = args.period
    if args.project:
        path = f"/projects/{args.org}/{args.project}/issues/"
    else:
        path = f"/organizations/{args.org}/issues/"
    data = api("GET", path, params=params)
    if args.json:
        fmt_json(data)
        return
    rows = [
        {
            "id": i["id"],
            "shortId": i.get("shortId", ""),
            "title": truncate(i.get("title", ""), 60),
            "level": i.get("level", ""),
            "count": i.get("count", ""),
            "users": i.get("userCount", ""),
            "lastSeen": (i.get("lastSeen") or "")[:19],
            "status": i.get("status", ""),
        }
        for i in data
    ]
    fmt_table(rows, ["shortId", "title", "level", "count", "users", "lastSeen", "status"])


def cmd_issue_get(args):
    issue_id = args.issue_id
    data = api("GET", f"/organizations/{args.org}/issues/{issue_id}/")
    if args.json:
        fmt_json(data)
        return
    print(f"ID:        {data.get('shortId', data.get('id', 'N/A'))}")
    print(f"Title:     {data.get('title', 'N/A')}")
    print(f"Level:     {data.get('level', 'N/A')}")
    print(f"Status:    {data.get('status', 'N/A')}")
    print(f"Events:    {data.get('count', 'N/A')}")
    print(f"Users:     {data.get('userCount', 'N/A')}")
    print(f"First:     {data.get('firstSeen', 'N/A')}")
    print(f"Last:      {data.get('lastSeen', 'N/A')}")
    print(f"Platform:  {data.get('platform', 'N/A')}")
    print(f"Project:   {data.get('project', {}).get('slug', 'N/A')}")
    permalink = data.get("permalink", "")
    if permalink:
        print(f"Link:      {permalink}")
    assigned = data.get("assignedTo")
    if assigned:
        print(f"Assigned:  {assigned.get('name', 'N/A')} ({assigned.get('type', '')})")
    # Show latest event info
    metadata = data.get("metadata", {})
    if metadata.get("value"):
        print(f"\nMessage:   {metadata['value']}")
    if metadata.get("filename"):
        print(f"File:      {metadata['filename']}")
    if metadata.get("function"):
        print(f"Function:  {metadata['function']}")


def cmd_issue_events(args):
    params = {"per_page": args.limit, "full": "true"}
    if args.query:
        params["query"] = args.query
    if args.period:
        params["statsPeriod"] = args.period
    data = api(
        "GET", f"/organizations/{args.org}/issues/{args.issue_id}/events/", params=params
    )
    if args.json:
        fmt_json(data)
        return
    rows = [
        {
            "eventID": e.get("eventID", "")[:12],
            "title": truncate(e.get("title", ""), 50),
            "dateCreated": (e.get("dateCreated") or "")[:19],
            "user": (e.get("user") or {}).get("email", "N/A"),
        }
        for e in data
    ]
    fmt_table(rows, ["eventID", "title", "dateCreated", "user"])


def cmd_issue_latest_event(args):
    data = api(
        "GET", f"/organizations/{args.org}/issues/{args.issue_id}/events/latest/"
    )
    if args.json:
        fmt_json(data)
        return
    print(f"Event ID:  {data.get('eventID', 'N/A')}")
    print(f"Title:     {data.get('title', 'N/A')}")
    print(f"Date:      {data.get('dateCreated', 'N/A')}")
    print(f"Platform:  {data.get('platform', 'N/A')}")
    # Print tags
    tags = data.get("tags", [])
    if tags:
        print("\nTags:")
        for t in tags[:15]:
            print(f"  {t.get('key', '')}: {t.get('value', '')}")
    # Print exception info
    entries = data.get("entries", [])
    for entry in entries:
        if entry.get("type") == "exception":
            exc_data = entry.get("data", {})
            for exc in exc_data.get("values", []):
                print(f"\nException: {exc.get('type', 'Unknown')}")
                print(f"Value:     {exc.get('value', 'N/A')}")
                frames = (exc.get("stacktrace") or {}).get("frames", [])
                if frames:
                    print("Stack trace (most recent last):")
                    for f in frames[-10:]:
                        filename = f.get("filename") or f.get("absPath") or "?"
                        lineno = f.get("lineNo", "?")
                        func = f.get("function", "?")
                        print(f"  {filename}:{lineno} in {func}")
                        ctx_line = f.get("context_line")
                        if ctx_line:
                            print(f"    > {ctx_line.strip()}")


def cmd_issue_tags(args):
    data = api(
        "GET",
        f"/organizations/{args.org}/issues/{args.issue_id}/tags/{args.tag_key}/",
    )
    if args.json:
        fmt_json(data)
        return
    print(f"Tag: {data.get('key', args.tag_key)} (unique values: {data.get('uniqueValues', 'N/A')})")
    print(f"Total: {data.get('totalValues', 'N/A')}")
    top = data.get("topValues", [])
    if top:
        print("\nTop values:")
        rows = [
            {
                "value": truncate(v.get("value", ""), 60),
                "count": v.get("count", ""),
                "lastSeen": (v.get("lastSeen") or "")[:19],
            }
            for v in top
        ]
        fmt_table(rows, ["value", "count", "lastSeen"])


def cmd_issue_update(args):
    body = {}
    if args.status:
        body["status"] = args.status
    if args.assignee:
        body["assignedTo"] = args.assignee if args.assignee != "none" else ""
    if not body:
        print("Error: provide --status and/or --assignee", file=sys.stderr)
        sys.exit(1)
    data = api("PUT", f"/organizations/{args.org}/issues/{args.issue_id}/", body=body)
    if args.json:
        fmt_json(data)
        return
    print(f"Updated issue {data.get('shortId', args.issue_id)}")
    print(f"  Status:   {data.get('status', 'N/A')}")
    assigned = data.get("assignedTo")
    if assigned:
        print(f"  Assigned: {assigned.get('name', 'N/A')}")


# --- Commands: Events & Search ----------------------------------------------


def cmd_events(args):
    fields = args.fields or ["title", "event.type", "project", "timestamp"]
    params = {
        "per_page": args.limit,
        "field[]": fields,
    }
    if args.dataset:
        params["dataset"] = args.dataset
    if args.query:
        params["query"] = args.query
    if args.period:
        params["statsPeriod"] = args.period
    if args.sort:
        params["sort"] = args.sort
    data = api("GET", f"/organizations/{args.org}/events/", params=params)
    if args.json:
        fmt_json(data)
        return
    rows = data.get("data", [])
    if not rows:
        print("No events found.")
        return
    # Use field names as columns
    display_cols = [f for f in fields if not f.startswith("count") and not f.startswith("sum")]
    if not display_cols:
        display_cols = list(rows[0].keys())[:6]
    # For aggregate queries, show all returned fields
    if any(f.startswith("count") or f.startswith("sum") or f.startswith("avg") or f.startswith("p50") or f.startswith("p75") or f.startswith("p95") or f.startswith("p99") for f in fields):
        display_cols = list(rows[0].keys())[:8]
    table_rows = []
    for r in rows:
        table_rows.append({c: truncate(str(r.get(c, "")), 50) for c in display_cols})
    fmt_table(table_rows, display_cols)
    meta = data.get("meta", {})
    if meta:
        total = meta.get("total")
        if total is not None:
            print(f"\nTotal: {total}")


# --- Commands: Traces -------------------------------------------------------


def cmd_trace(args):
    meta = api(
        "GET",
        f"/organizations/{args.org}/trace-meta/{args.trace_id}/",
        params={"statsPeriod": args.period or "24h"},
    )
    if args.json:
        fmt_json(meta)
        return
    print(f"Trace:      {args.trace_id}")
    print(f"Projects:   {meta.get('projects', 'N/A')}")
    print(f"Transactions: {meta.get('transactions', 'N/A')}")
    print(f"Errors:     {meta.get('errors', 'N/A')}")
    spans = meta.get("spans", 0)
    print(f"Spans:      {spans}")
    perf = meta.get("performance_issues", 0)
    if perf:
        print(f"Perf Issues: {perf}")


# --- Commands: Autofix / Seer -----------------------------------------------


def cmd_autofix(args):
    # Check existing autofix state first
    existing = api(
        "GET", f"/organizations/{args.org}/issues/{args.issue_id}/autofix/"
    )
    runs = existing.get("autofix", {}).get("runs", [])

    if runs and not args.restart:
        latest = runs[0]
        status = latest.get("status", "unknown")
        print(f"Autofix status: {status}")

        if status == "COMPLETED":
            output = latest.get("output", {})
            causes = output.get("causes", [])
            if causes:
                for i, cause in enumerate(causes, 1):
                    print(f"\n--- Root Cause {i} ---")
                    print(f"Title: {cause.get('title', 'N/A')}")
                    print(f"Description: {cause.get('description', 'N/A')}")
            fixes = output.get("fixes", [])
            if fixes:
                print(f"\n--- Suggested Fixes ---")
                for fix in fixes:
                    print(f"  Title: {fix.get('title', 'N/A')}")
                    print(f"  Description: {fix.get('description', 'N/A')}")
            if not causes and not fixes:
                if args.json:
                    fmt_json(existing)
                else:
                    print("Completed but no causes/fixes found.")
                    print("Use --json for full output.")
            return

        if status in ("PROCESSING", "PENDING"):
            print("Analysis is still running. Check back in a few minutes.")
            print(f"Started: {latest.get('createdAt', 'N/A')}")
            return

        if args.json:
            fmt_json(existing)
        return

    # Start new analysis
    body = {}
    if args.instruction:
        body["instruction"] = args.instruction
    print(f"Starting autofix analysis for issue {args.issue_id}...")
    data = api(
        "POST", f"/organizations/{args.org}/issues/{args.issue_id}/autofix/", body=body
    )
    if args.json:
        fmt_json(data)
        return
    print("Autofix analysis started. This may take 2-5 minutes.")
    print("Run the same command again to check status.")


# --- Commands: Management ---------------------------------------------------


def cmd_create_team(args):
    data = api(
        "POST",
        f"/organizations/{args.org}/teams/",
        body={"name": args.name},
    )
    if args.json:
        fmt_json(data)
        return
    print(f"Created team: {data.get('slug', 'N/A')} (id: {data.get('id', 'N/A')})")


def cmd_create_project(args):
    data = api(
        "POST",
        f"/teams/{args.org}/{args.team}/projects/",
        body={"name": args.name, "platform": args.platform},
    )
    if args.json:
        fmt_json(data)
        return
    print(f"Created project: {data.get('slug', 'N/A')} (id: {data.get('id', 'N/A')})")
    keys = data.get("keys", [])
    if keys:
        dsn = keys[0].get("dsn", {})
        print(f"DSN (public): {dsn.get('public', 'N/A')}")


def cmd_update_project(args):
    body = {}
    if args.name:
        body["name"] = args.name
    if args.slug:
        body["slug"] = args.slug
    if args.platform:
        body["platform"] = args.platform
    if not body:
        print("Error: provide at least one of --name, --slug, --platform", file=sys.stderr)
        sys.exit(1)
    data = api("PUT", f"/projects/{args.org}/{args.project}/", body=body)
    if args.json:
        fmt_json(data)
        return
    print(f"Updated project: {data.get('slug', 'N/A')}")


def cmd_dsns(args):
    data = api("GET", f"/projects/{args.org}/{args.project}/keys/")
    if args.json:
        fmt_json(data)
        return
    rows = [
        {
            "name": k.get("name", ""),
            "dsn": k.get("dsn", {}).get("public", ""),
            "id": k.get("id", ""),
        }
        for k in data
    ]
    fmt_table(rows, ["name", "dsn", "id"])


def cmd_create_dsn(args):
    body = {}
    if args.name:
        body["name"] = args.name
    data = api("POST", f"/projects/{args.org}/{args.project}/keys/", body=body)
    if args.json:
        fmt_json(data)
        return
    dsn = data.get("dsn", {})
    print(f"Created DSN: {data.get('name', 'N/A')}")
    print(f"Public:  {dsn.get('public', 'N/A')}")


# --- CLI Parser -------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(description="Sentry CLI for Claude Code")
    p.add_argument("--json", action="store_true", help="Raw JSON output")
    sub = p.add_subparsers(dest="command", required=True)

    # whoami
    sub.add_parser("whoami", help="Identify authenticated user")

    # orgs
    sp = sub.add_parser("orgs", help="List organizations")
    sp.add_argument("--query", help="Filter by name")
    sp.add_argument("--limit", type=int, default=25)

    # teams
    sp = sub.add_parser("teams", help="List teams in an organization")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("--query", help="Filter by name")
    sp.add_argument("--limit", type=int, default=25)

    # projects
    sp = sub.add_parser("projects", help="List projects in an organization")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("--query", help="Filter by name")
    sp.add_argument("--limit", type=int, default=25)

    # releases
    sp = sub.add_parser("releases", help="List releases")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("--project", help="Filter by project slug")
    sp.add_argument("--query", help="Filter by version")
    sp.add_argument("--limit", type=int, default=25)

    # issues
    sp = sub.add_parser("issues", help="List/search issues")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("--project", help="Filter by project slug")
    sp.add_argument("--query", "-q", help="Sentry search query (e.g. 'is:unresolved level:error')")
    sp.add_argument("--sort", choices=["date", "new", "priority", "freq", "user"], default="date")
    sp.add_argument("--period", default="14d", help="Stats period (e.g. 24h, 7d, 14d, 30d)")
    sp.add_argument("--limit", type=int, default=25)

    # issue-get
    sp = sub.add_parser("issue-get", help="Get issue details")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("issue_id", help="Issue ID or short ID")

    # issue-events
    sp = sub.add_parser("issue-events", help="List events for an issue")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("issue_id", help="Issue ID")
    sp.add_argument("--query", "-q", help="Filter events")
    sp.add_argument("--period", help="Stats period")
    sp.add_argument("--limit", type=int, default=10)

    # issue-latest
    sp = sub.add_parser("issue-latest", help="Get latest event for an issue (includes stack trace)")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("issue_id", help="Issue ID")

    # issue-tags
    sp = sub.add_parser("issue-tags", help="Get tag distribution for an issue")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("issue_id", help="Issue ID")
    sp.add_argument("tag_key", help="Tag key (e.g. browser, os, url, environment, user)")

    # issue-update
    sp = sub.add_parser("issue-update", help="Update issue status/assignment")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("issue_id", help="Issue ID")
    sp.add_argument("--status", choices=["resolved", "unresolved", "ignored"])
    sp.add_argument("--assignee", help="Username or 'none' to unassign")

    # events
    sp = sub.add_parser("events", help="Search events (errors, spans, logs)")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("--query", "-q", help="Sentry search query")
    sp.add_argument("--dataset", choices=["errors", "spans", "logs"], default="errors")
    sp.add_argument("--fields", nargs="+", help="Fields to return (e.g. title count())")
    sp.add_argument("--sort", help="Sort field (prefix with - for desc)")
    sp.add_argument("--period", default="24h", help="Stats period (e.g. 1h, 24h, 7d)")
    sp.add_argument("--limit", type=int, default=25)

    # trace
    sp = sub.add_parser("trace", help="Get trace metadata")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("trace_id", help="Trace ID")
    sp.add_argument("--period", help="Stats period")

    # autofix
    sp = sub.add_parser("autofix", help="AI root cause analysis (Seer)")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("issue_id", help="Issue ID")
    sp.add_argument("--restart", action="store_true", help="Force restart analysis")
    sp.add_argument("--instruction", help="Additional context for analysis")

    # create-team
    sp = sub.add_parser("create-team", help="Create a new team")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("--name", required=True, help="Team name")

    # create-project
    sp = sub.add_parser("create-project", help="Create a new project")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("--team", required=True, help="Team slug")
    sp.add_argument("--name", required=True, help="Project name")
    sp.add_argument("--platform", default="python", help="Platform (e.g. python, javascript, node)")

    # update-project
    sp = sub.add_parser("update-project", help="Update project settings")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("project", help="Project slug")
    sp.add_argument("--name", help="New name")
    sp.add_argument("--slug", help="New slug")
    sp.add_argument("--platform", help="New platform")

    # dsns
    sp = sub.add_parser("dsns", help="List DSNs for a project")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("project", help="Project slug")

    # create-dsn
    sp = sub.add_parser("create-dsn", help="Create a new DSN")
    sp.add_argument("org", help="Organization slug")
    sp.add_argument("project", help="Project slug")
    sp.add_argument("--name", help="Key name")

    return p


DISPATCH = {
    "whoami": cmd_whoami,
    "orgs": cmd_orgs,
    "teams": cmd_teams,
    "projects": cmd_projects,
    "releases": cmd_releases,
    "issues": cmd_issues,
    "issue-get": cmd_issue_get,
    "issue-events": cmd_issue_events,
    "issue-latest": cmd_issue_latest_event,
    "issue-tags": cmd_issue_tags,
    "issue-update": cmd_issue_update,
    "events": cmd_events,
    "trace": cmd_trace,
    "autofix": cmd_autofix,
    "create-team": cmd_create_team,
    "create-project": cmd_create_project,
    "update-project": cmd_update_project,
    "dsns": cmd_dsns,
    "create-dsn": cmd_create_dsn,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    fn = DISPATCH.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
