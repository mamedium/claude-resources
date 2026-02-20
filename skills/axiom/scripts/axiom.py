#!/usr/bin/env python3
"""Axiom CLI - Query observability data via Axiom REST API."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# --- Helpers ----------------------------------------------------------------

BASE_URL = "https://api.axiom.co"
INTERNAL_URL = "https://app.axiom.co"


def get_token():
    token = os.environ.get("AXIOM_AUTH_TOKEN")
    if not token:
        print("Error: AXIOM_AUTH_TOKEN not set", file=sys.stderr)
        print("Add to ~/.claude/settings.json:", file=sys.stderr)
        print('  {"env": {"AXIOM_AUTH_TOKEN": "your-xapt-token"}}', file=sys.stderr)
        sys.exit(1)
    return token


def get_org_id():
    org_id = os.environ.get("AXIOM_ORG_ID", "")
    return org_id


def api(method, path, body=None, params=None, base=None):
    """Make an API request with retry logic."""
    url = (base or BASE_URL) + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    org_id = get_org_id()
    if org_id:
        headers["x-axiom-org-id"] = org_id

    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                wait = 2 ** attempt
                print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            body_text = e.read().decode() if e.fp else ""
            print(f"HTTP {e.code}: {body_text}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"Connection error: {e.reason}", file=sys.stderr)
            sys.exit(1)
    return None


def fmt_json(data):
    print(json.dumps(data, indent=2))


def truncate(s, n=80):
    s = str(s or "")
    return s[:n] + "..." if len(s) > n else s


def fmt_table(rows, columns):
    """Print aligned table."""
    if not rows:
        print("No results.")
        return
    widths = {c: len(c) for c in columns}
    str_rows = []
    for row in rows:
        sr = {}
        for c in columns:
            val = str(row.get(c, ""))
            sr[c] = val
            widths[c] = max(widths[c], min(len(val), 80))
        str_rows.append(sr)
    header = "  ".join(c.ljust(widths[c])[:widths[c]] for c in columns)
    print(header)
    print("  ".join("-" * widths[c] for c in columns))
    for sr in str_rows:
        print("  ".join(sr[c].ljust(widths[c])[:widths[c]] for c in columns))


# --- Commands ---------------------------------------------------------------


def cmd_datasets(args):
    """List all datasets."""
    data = api("GET", "/v2/datasets")
    if args.json:
        fmt_json(data)
        return
    rows = [{"name": d["name"], "description": truncate(d.get("description", ""), 60),
             "kind": d.get("kind", "events")} for d in data]
    fmt_table(rows, ["name", "kind", "description"])


def cmd_dataset_fields(args):
    """List fields in a dataset."""
    data = api("GET", f"/v2/datasets/{urllib.parse.quote(args.dataset)}/fields")
    if args.json:
        fmt_json(data)
        return
    rows = [{"name": f["name"], "type": f.get("type", ""),
             "description": truncate(f.get("description", ""), 50)} for f in data]
    fmt_table(rows, ["name", "type", "description"])


def cmd_query(args):
    """Execute an APL query."""
    body = {"apl": args.apl, "maxBinAutoGroups": 15}
    if args.start:
        body["startTime"] = args.start
    if args.end:
        body["endTime"] = args.end
    data = api("POST", "/v1/datasets/_apl", body=body, params={"format": "tabular"})
    if args.json:
        fmt_json(data)
        return
    # Print status
    status = data.get("status", {})
    print(f"Rows matched: {status.get('rowsMatched', '?')}  "
          f"Elapsed: {status.get('elapsedTime', '?')}ms  "
          f"Blocks: {status.get('blocksExamined', '?')}")
    print()
    # Print tables
    for table in data.get("tables", []):
        fields = [f["name"] for f in table.get("fields", [])]
        columns = table.get("columns", [])
        if not columns or not fields:
            continue
        num_rows = len(columns[0]) if columns else 0
        rows = []
        for i in range(min(num_rows, args.limit)):
            row = {}
            for j, f in enumerate(fields):
                val = columns[j][i] if j < len(columns) else ""
                row[f] = truncate(str(val), 60)
            rows.append(row)
        display_fields = fields[:10]  # Cap columns for readability
        fmt_table(rows, display_fields)
        if num_rows > args.limit:
            print(f"\n... showing {args.limit} of {num_rows} rows")


def cmd_saved_queries(args):
    """List saved/starred APL queries."""
    data = api("GET", "/v2/apl-starred-queries", params={"limit": str(args.limit), "who": "all"})
    if args.json:
        fmt_json(data)
        return
    rows = [{"name": q.get("name", ""), "query": truncate(q.get("apl", ""), 60),
             "createdBy": q.get("createdBy", "")} for q in (data or [])]
    fmt_table(rows, ["name", "createdBy", "query"])


def cmd_monitors(args):
    """List all monitors and their statuses."""
    data = api("GET", "/v2/monitors")
    if args.json:
        fmt_json(data)
        return
    rows = []
    for m in data:
        rows.append({
            "id": m.get("id", ""),
            "name": truncate(m.get("name", ""), 40),
            "type": m.get("type", ""),
            "disabled": str(m.get("disabled", False)),
            "interval": str(m.get("intervalMinutes", "")) + "m",
        })
    fmt_table(rows, ["id", "name", "type", "disabled", "interval"])


def cmd_monitor_history(args):
    """Get recent check history for a monitor."""
    data = api("GET", "/api/internal/monitors/history",
               params={"monitorIds": args.monitor_id}, base=INTERNAL_URL)
    if args.json:
        fmt_json(data)
        return
    fields = data.get("fields", [])
    entries = data.get("data", {}).get(args.monitor_id, [])
    if not entries:
        print("No history found.")
        return
    for entry in entries[:args.limit]:
        row = dict(zip(fields, entry)) if fields else {}
        print(json.dumps(row))


def cmd_dashboards(args):
    """List all dashboards."""
    data = api("GET", "/v2/dashboards")
    if args.json:
        fmt_json(data)
        return
    rows = []
    for d in data:
        dash = d.get("dashboard", {})
        rows.append({
            "uid": d.get("uid", ""),
            "name": truncate(dash.get("name", ""), 40),
            "owner": dash.get("owner", ""),
            "updated": d.get("updatedAt", "")[:19],
        })
    fmt_table(rows, ["uid", "name", "owner", "updated"])


def cmd_dashboard_get(args):
    """Get a specific dashboard."""
    data = api("GET", f"/v2/dashboards/uid/{urllib.parse.quote(args.uid)}")
    if args.json:
        fmt_json(data)
        return
    dash = data.get("dashboard", {})
    print(f"Name:        {dash.get('name', '')}")
    print(f"UID:         {data.get('uid', '')}")
    print(f"Owner:       {dash.get('owner', '')}")
    print(f"Version:     {data.get('version', '')}")
    print(f"Updated:     {data.get('updatedAt', '')}")
    print(f"Updated By:  {data.get('updatedBy', '')}")
    print(f"Charts:      {len(dash.get('charts', []))}")
    print(f"Datasets:    {', '.join(dash.get('datasets', []))}")
    if dash.get("description"):
        print(f"Description: {dash['description']}")


def cmd_dashboard_export(args):
    """Export a dashboard as JSON."""
    data = api("GET", f"/v2/dashboards/uid/{urllib.parse.quote(args.uid)}")
    fmt_json(data)


def cmd_query_metrics(args):
    """Query metrics using MPL."""
    body = {"apl": args.mpl}
    if args.start:
        body["startTime"] = args.start
    if args.end:
        body["endTime"] = args.end
    data = api("POST", "/v1/query/_mpl", body=body, params={"format": "metrics-v1"})
    if args.json:
        fmt_json(data)
        return
    if not data:
        print("No results.")
        return
    for series in data[:args.limit]:
        tags = series.get("tags", {})
        tag_str = ", ".join(f"{k}={v}" for k, v in tags.items()) if tags else ""
        metric = series.get("metric", "")
        summary = series.get("summary")
        points = series.get("data", [])
        non_null = [p for p in points if p is not None]
        print(f"Metric: {metric}  Tags: [{tag_str}]  "
              f"Summary: {summary}  Points: {len(non_null)}")


def cmd_metrics(args):
    """List available metrics in a dataset."""
    params = {}
    if args.start:
        params["start"] = args.start
    if args.end:
        params["end"] = args.end
    ds = urllib.parse.quote(args.dataset)
    data = api("GET", f"/v1/query/metrics/info/datasets/{ds}/metrics", params=params)
    if args.json:
        fmt_json(data)
        return
    for m in (data or []):
        print(m)


def cmd_metric_tags(args):
    """List available tags in a metrics dataset."""
    params = {}
    if args.start:
        params["start"] = args.start
    if args.end:
        params["end"] = args.end
    ds = urllib.parse.quote(args.dataset)
    data = api("GET", f"/v1/query/metrics/info/datasets/{ds}/tags", params=params)
    if args.json:
        fmt_json(data)
        return
    for t in (data or []):
        print(t)


def cmd_metric_tag_values(args):
    """List values for a specific tag."""
    params = {}
    if args.start:
        params["start"] = args.start
    if args.end:
        params["end"] = args.end
    ds = urllib.parse.quote(args.dataset)
    tag = urllib.parse.quote(args.tag)
    data = api("GET", f"/v1/query/metrics/info/datasets/{ds}/tags/{tag}/values", params=params)
    if args.json:
        fmt_json(data)
        return
    for v in (data or []):
        print(v)


# --- CLI Parser -------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(prog="axiom", description="Axiom CLI - Query observability data")
    sub = p.add_subparsers(dest="command", help="Command")

    # datasets
    ds = sub.add_parser("datasets", help="List all datasets")
    ds.add_argument("--json", action="store_true", help="Raw JSON output")

    # dataset-fields
    df = sub.add_parser("dataset-fields", help="List fields in a dataset")
    df.add_argument("dataset", help="Dataset name")
    df.add_argument("--json", action="store_true")

    # query
    q = sub.add_parser("query", help="Execute an APL query")
    q.add_argument("apl", help="APL query string")
    q.add_argument("--start", help="Start time (RFC3339 or relative, e.g. now-1h)")
    q.add_argument("--end", help="End time (RFC3339 or relative)")
    q.add_argument("--limit", type=int, default=50, help="Max rows to display (default 50)")
    q.add_argument("--json", action="store_true")

    # saved-queries
    sq = sub.add_parser("saved-queries", help="List saved APL queries")
    sq.add_argument("--limit", type=int, default=25, help="Max results (default 25)")
    sq.add_argument("--json", action="store_true")

    # monitors
    mo = sub.add_parser("monitors", help="List monitors and statuses")
    mo.add_argument("--json", action="store_true")

    # monitor-history
    mh = sub.add_parser("monitor-history", help="Get monitor check history")
    mh.add_argument("monitor_id", help="Monitor ID")
    mh.add_argument("--limit", type=int, default=25)
    mh.add_argument("--json", action="store_true")

    # dashboards
    da = sub.add_parser("dashboards", help="List all dashboards")
    da.add_argument("--json", action="store_true")

    # dashboard-get
    dg = sub.add_parser("dashboard-get", help="Get dashboard details")
    dg.add_argument("uid", help="Dashboard UID")
    dg.add_argument("--json", action="store_true")

    # dashboard-export
    de = sub.add_parser("dashboard-export", help="Export dashboard as JSON")
    de.add_argument("uid", help="Dashboard UID")

    # query-metrics
    qm = sub.add_parser("query-metrics", help="Query metrics using MPL")
    qm.add_argument("mpl", help="MPL query string")
    qm.add_argument("--start", help="Start time")
    qm.add_argument("--end", help="End time")
    qm.add_argument("--limit", type=int, default=25)
    qm.add_argument("--json", action="store_true")

    # metrics
    me = sub.add_parser("metrics", help="List metrics in a dataset")
    me.add_argument("dataset", help="Metrics dataset name")
    me.add_argument("--start", help="Start time (RFC3339)")
    me.add_argument("--end", help="End time (RFC3339)")
    me.add_argument("--json", action="store_true")

    # metric-tags
    mt = sub.add_parser("metric-tags", help="List tags in a metrics dataset")
    mt.add_argument("dataset", help="Metrics dataset name")
    mt.add_argument("--start", help="Start time")
    mt.add_argument("--end", help="End time")
    mt.add_argument("--json", action="store_true")

    # metric-tag-values
    mv = sub.add_parser("metric-tag-values", help="List values for a metric tag")
    mv.add_argument("dataset", help="Metrics dataset name")
    mv.add_argument("tag", help="Tag name")
    mv.add_argument("--start", help="Start time")
    mv.add_argument("--end", help="End time")
    mv.add_argument("--json", action="store_true")

    return p


DISPATCH = {
    "datasets": cmd_datasets,
    "dataset-fields": cmd_dataset_fields,
    "query": cmd_query,
    "saved-queries": cmd_saved_queries,
    "monitors": cmd_monitors,
    "monitor-history": cmd_monitor_history,
    "dashboards": cmd_dashboards,
    "dashboard-get": cmd_dashboard_get,
    "dashboard-export": cmd_dashboard_export,
    "query-metrics": cmd_query_metrics,
    "metrics": cmd_metrics,
    "metric-tags": cmd_metric_tags,
    "metric-tag-values": cmd_metric_tag_values,
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
