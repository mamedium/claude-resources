#!/usr/bin/env python3
"""Langfuse CLI - LLM observability and prompt management via Langfuse REST API."""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# --- Helpers ----------------------------------------------------------------

def get_auth():
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("LANGFUSE_SECRET_KEY")
    if not pub or not sec:
        print("Error: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set", file=sys.stderr)
        print("Add to ~/.claude/settings.json:", file=sys.stderr)
        print('  {"env": {"LANGFUSE_PUBLIC_KEY": "pk-...", "LANGFUSE_SECRET_KEY": "sk-..."}}', file=sys.stderr)
        sys.exit(1)
    return base64.b64encode(f"{pub}:{sec}".encode()).decode()


def get_base_url():
    return os.environ.get("LANGFUSE_BASEURL", "https://cloud.langfuse.com").rstrip("/")


def api(method, path, body=None, params=None):
    """Make an API request with retry logic."""
    base = get_base_url()
    url = f"{base}/api/public{path}"
    if params:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if qs:
            url += f"?{qs}"

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Basic {get_auth()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
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
            print(f"Request failed: {e.reason}", file=sys.stderr)
            sys.exit(1)
    print("Max retries exceeded", file=sys.stderr)
    sys.exit(1)


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
    for r in rows:
        sr = {}
        for c in columns:
            val = r.get(c, "")
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            sr[c] = str(val or "")
            widths[c] = max(widths[c], min(len(sr[c]), 80))
        str_rows.append(sr)
    header = "  ".join(c.ljust(widths[c])[:widths[c]] for c in columns)
    print(header)
    print("  ".join("-" * widths[c] for c in columns))
    for sr in str_rows:
        print("  ".join(sr[c].ljust(widths[c])[:widths[c]] for c in columns))


# --- Commands: Health & Projects --------------------------------------------

def cmd_health(args):
    data = api("GET", "/health")
    if args.json:
        fmt_json(data)
    else:
        status = data.get("status", "unknown")
        print(f"Status: {status}")


def cmd_projects(args):
    data = api("GET", "/projects", params={"page": args.page, "limit": args.limit})
    items = data.get("data", [])
    if args.json:
        fmt_json(data)
    else:
        fmt_table(items, ["id", "name", "createdAt"])


# --- Commands: Traces -------------------------------------------------------

def cmd_traces(args):
    params = {"limit": args.limit}
    if args.cursor:
        params["cursor"] = args.cursor
    if args.user_id:
        params["userId"] = args.user_id
    if args.session_id:
        params["sessionId"] = args.session_id
    if args.filter:
        params["filter"] = args.filter
    data = api("GET", "/v2/traces", params=params)
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "name", "userId", "sessionId", "timestamp", "tags"])
        meta = data.get("meta", {})
        if meta.get("nextCursor"):
            print(f"\nNext cursor: {meta['nextCursor']}")


def cmd_trace_get(args):
    data = api("GET", f"/traces/{args.trace_id}")
    if args.json:
        fmt_json(data)
    else:
        print(f"ID:        {data.get('id')}")
        print(f"Name:      {data.get('name')}")
        print(f"User:      {data.get('userId')}")
        print(f"Session:   {data.get('sessionId')}")
        print(f"Timestamp: {data.get('timestamp')}")
        print(f"Tags:      {data.get('tags', [])}")
        print(f"Metadata:  {json.dumps(data.get('metadata', {}), indent=2)}")
        inp = data.get("input")
        if inp:
            print(f"\nInput:\n{json.dumps(inp, indent=2)[:2000]}")
        out = data.get("output")
        if out:
            print(f"\nOutput:\n{json.dumps(out, indent=2)[:2000]}")
        obs = data.get("observations", [])
        if obs:
            print(f"\nObservations ({len(obs)}):")
            fmt_table(obs[:20], ["id", "name", "type", "level", "startTime"])


def cmd_trace_delete(args):
    api("DELETE", f"/traces/{args.trace_id}")
    print(f"Deleted trace {args.trace_id}")


def cmd_trace_bookmark(args):
    api("POST", f"/traces/{args.trace_id}/bookmark")
    print(f"Bookmarked trace {args.trace_id}")


def cmd_trace_unbookmark(args):
    api("DELETE", f"/traces/{args.trace_id}/bookmark")
    print(f"Removed bookmark from trace {args.trace_id}")


# --- Commands: Observations -------------------------------------------------

def cmd_observations(args):
    params = {"limit": args.limit}
    if args.cursor:
        params["cursor"] = args.cursor
    if args.name:
        params["name"] = args.name
    if args.type:
        params["type"] = args.type
    if args.trace_id:
        params["traceId"] = args.trace_id
    if args.level:
        params["level"] = args.level
    if args.user_id:
        params["userId"] = args.user_id
    if args.environment:
        params["environment"] = args.environment
    data = api("GET", "/v2/observations", params=params)
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "name", "type", "traceId", "level", "startTime"])
        meta = data.get("meta", {})
        if meta.get("nextCursor"):
            print(f"\nNext cursor: {meta['nextCursor']}")


def cmd_observation_get(args):
    data = api("GET", f"/observations/{args.observation_id}")
    if args.json:
        fmt_json(data)
    else:
        print(f"ID:        {data.get('id')}")
        print(f"Name:      {data.get('name')}")
        print(f"Type:      {data.get('type')}")
        print(f"Trace:     {data.get('traceId')}")
        print(f"Level:     {data.get('level')}")
        print(f"Model:     {data.get('model')}")
        print(f"Start:     {data.get('startTime')}")
        print(f"End:       {data.get('endTime')}")
        usage = data.get("usage", {})
        if usage:
            print(f"Usage:     {json.dumps(usage)}")
        inp = data.get("input")
        if inp:
            print(f"\nInput:\n{json.dumps(inp, indent=2)[:2000]}")
        out = data.get("output")
        if out:
            print(f"\nOutput:\n{json.dumps(out, indent=2)[:2000]}")


# --- Commands: Sessions -----------------------------------------------------

def cmd_sessions(args):
    params = {"page": args.page, "limit": args.limit}
    if args.user_id:
        params["userId"] = args.user_id
    data = api("GET", "/sessions", params=params)
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "createdAt", "projectId"])


def cmd_session_get(args):
    data = api("GET", f"/sessions/{args.session_id}")
    if args.json:
        fmt_json(data)
    else:
        print(f"ID:        {data.get('id')}")
        print(f"Created:   {data.get('createdAt')}")
        print(f"Project:   {data.get('projectId')}")
        traces = data.get("traces", [])
        if traces:
            print(f"\nTraces ({len(traces)}):")
            fmt_table(traces[:20], ["id", "name", "timestamp"])


# --- Commands: Scores -------------------------------------------------------

def cmd_scores(args):
    params = {"limit": args.limit}
    if args.cursor:
        params["cursor"] = args.cursor
    if args.filter:
        params["filter"] = args.filter
    data = api("GET", "/v2/scores", params=params)
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "name", "value", "traceId", "observationId", "source"])
        meta = data.get("meta", {})
        if meta.get("nextCursor"):
            print(f"\nNext cursor: {meta['nextCursor']}")


def cmd_score_create(args):
    body = {"name": args.name, "traceId": args.trace_id}
    if args.value is not None:
        body["value"] = args.value
    if args.string_value:
        body["stringValue"] = args.string_value
    if args.observation_id:
        body["observationId"] = args.observation_id
    if args.comment:
        body["comment"] = args.comment
    if args.data_type:
        body["dataType"] = args.data_type
    data = api("POST", "/v2/scores", body=body)
    if args.json:
        fmt_json(data)
    else:
        print(f"Created score: {data.get('id')}")


def cmd_score_delete(args):
    api("DELETE", f"/v2/scores/{args.score_id}")
    print(f"Deleted score {args.score_id}")


# --- Commands: Score Configs ------------------------------------------------

def cmd_score_configs(args):
    data = api("GET", "/score-configs", params={"page": args.page, "limit": args.limit})
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "name", "dataType", "isArchived", "createdAt"])


# --- Commands: Prompts ------------------------------------------------------

def cmd_prompts(args):
    params = {"page": args.page, "limit": args.limit}
    if args.name:
        params["name"] = args.name
    data = api("GET", "/prompts", params=params)
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["name", "version", "type", "labels", "tags", "createdAt"])


def cmd_prompt_get(args):
    path = f"/prompts/{urllib.parse.quote(args.prompt_name, safe='')}"
    params = {}
    if args.version is not None:
        params["version"] = args.version
    if args.label:
        params["label"] = args.label
    data = api("GET", path, params=params)
    if args.json:
        fmt_json(data)
    else:
        print(f"Name:    {data.get('name')}")
        print(f"Version: {data.get('version')}")
        print(f"Type:    {data.get('type')}")
        print(f"Labels:  {data.get('labels', [])}")
        print(f"Tags:    {data.get('tags', [])}")
        prompt = data.get("prompt")
        if isinstance(prompt, str):
            print(f"\nPrompt:\n{prompt}")
        elif isinstance(prompt, list):
            print(f"\nMessages:")
            for msg in prompt:
                role = msg.get("role", "?")
                content = msg.get("content", "")
                print(f"  [{role}] {truncate(content, 200)}")
        config = data.get("config")
        if config:
            print(f"\nConfig:\n{json.dumps(config, indent=2)}")


def cmd_prompt_create(args):
    body = {"name": args.name, "type": args.type}
    if args.type == "text":
        body["prompt"] = args.prompt_text or ""
    elif args.type == "chat":
        if args.messages:
            body["prompt"] = json.loads(args.messages)
        else:
            body["prompt"] = [{"role": "system", "content": args.prompt_text or ""}]
    if args.labels:
        body["labels"] = args.labels.split(",")
    if args.tags:
        body["tags"] = args.tags.split(",")
    if args.config:
        body["config"] = json.loads(args.config)
    if args.commit_message:
        body["commitMessage"] = args.commit_message
    data = api("POST", "/prompts", body=body)
    if args.json:
        fmt_json(data)
    else:
        print(f"Created prompt '{data.get('name')}' version {data.get('version')}")


# --- Commands: Datasets -----------------------------------------------------

def cmd_datasets(args):
    data = api("GET", "/v2/datasets", params={"page": args.page, "limit": args.limit})
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "name", "description", "createdAt"])


def cmd_dataset_get(args):
    data = api("GET", f"/v2/datasets/{urllib.parse.quote(args.dataset_name, safe='')}")
    if args.json:
        fmt_json(data)
    else:
        print(f"Name:        {data.get('name')}")
        print(f"ID:          {data.get('id')}")
        print(f"Description: {data.get('description')}")
        print(f"Created:     {data.get('createdAt')}")
        print(f"Metadata:    {json.dumps(data.get('metadata', {}))}")


def cmd_dataset_create(args):
    body = {"name": args.name}
    if args.description:
        body["description"] = args.description
    if args.metadata:
        body["metadata"] = json.loads(args.metadata)
    data = api("POST", "/v2/datasets", body=body)
    if args.json:
        fmt_json(data)
    else:
        print(f"Created dataset '{data.get('name')}' ({data.get('id')})")


def cmd_dataset_runs(args):
    name = urllib.parse.quote(args.dataset_name, safe="")
    data = api("GET", f"/datasets/{name}/runs", params={"page": args.page, "limit": args.limit})
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "name", "createdAt", "datasetId"])


def cmd_dataset_items(args):
    params = {"limit": args.limit, "page": args.page}
    if args.dataset_name:
        params["datasetName"] = args.dataset_name
    data = api("GET", "/dataset-items", params=params)
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "datasetId", "status", "createdAt"])


def cmd_dataset_item_create(args):
    body = {"datasetName": args.dataset_name, "input": json.loads(args.input)}
    if args.expected_output:
        body["expectedOutput"] = json.loads(args.expected_output)
    if args.metadata:
        body["metadata"] = json.loads(args.metadata)
    if args.source_trace_id:
        body["sourceTraceId"] = args.source_trace_id
    if args.source_observation_id:
        body["sourceObservationId"] = args.source_observation_id
    if args.id:
        body["id"] = args.id
    data = api("POST", "/dataset-items", body=body)
    if args.json:
        fmt_json(data)
    else:
        print(f"Created dataset item {data.get('id')}")


# --- Commands: Models -------------------------------------------------------

def cmd_models(args):
    data = api("GET", "/models", params={"page": args.page, "limit": args.limit})
    if args.json:
        fmt_json(data)
    else:
        items = data.get("data", [])
        fmt_table(items, ["id", "modelName", "matchPattern", "unit", "createdAt"])


def cmd_model_get(args):
    data = api("GET", f"/models/{args.model_id}")
    if args.json:
        fmt_json(data)
    else:
        print(f"ID:        {data.get('id')}")
        print(f"Name:      {data.get('modelName')}")
        print(f"Pattern:   {data.get('matchPattern')}")
        print(f"Unit:      {data.get('unit')}")
        print(f"Input $/u: {data.get('inputPrice')}")
        print(f"Out $/u:   {data.get('outputPrice')}")
        print(f"Total $/u: {data.get('totalPrice')}")


# --- Commands: Metrics ------------------------------------------------------

def cmd_metrics(args):
    params = {}
    if args.query:
        params["query"] = args.query
    data = api("GET", "/v2/metrics", params=params)
    if args.json:
        fmt_json(data)
    else:
        fmt_json(data)  # metrics are complex, always show JSON


# --- CLI Parser -------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="langfuse", description="Langfuse CLI")
    p.add_argument("--json", action="store_true", help="Raw JSON output")
    sub = p.add_subparsers(dest="command")

    # Health
    sub.add_parser("health", help="Check API health")

    # Projects
    sp = sub.add_parser("projects", help="List projects")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)

    # Traces
    sp = sub.add_parser("traces", help="List traces")
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--cursor", help="Pagination cursor")
    sp.add_argument("--user-id", help="Filter by user ID")
    sp.add_argument("--session-id", help="Filter by session ID")
    sp.add_argument("--filter", help="Filter JSON string")

    sp = sub.add_parser("trace-get", help="Get trace by ID")
    sp.add_argument("trace_id", help="Trace ID")

    sp = sub.add_parser("trace-delete", help="Delete a trace")
    sp.add_argument("trace_id", help="Trace ID")

    sp = sub.add_parser("trace-bookmark", help="Bookmark a trace")
    sp.add_argument("trace_id", help="Trace ID")

    sp = sub.add_parser("trace-unbookmark", help="Remove bookmark from trace")
    sp.add_argument("trace_id", help="Trace ID")

    # Observations
    sp = sub.add_parser("observations", help="List observations")
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--cursor", help="Pagination cursor")
    sp.add_argument("--name", help="Filter by name")
    sp.add_argument("--type", help="Filter by type (SPAN, GENERATION, EVENT)")
    sp.add_argument("--trace-id", help="Filter by trace ID")
    sp.add_argument("--level", help="Filter by level")
    sp.add_argument("--user-id", help="Filter by user ID")
    sp.add_argument("--environment", help="Filter by environment")

    sp = sub.add_parser("observation-get", help="Get observation by ID")
    sp.add_argument("observation_id", help="Observation ID")

    # Sessions
    sp = sub.add_parser("sessions", help="List sessions")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--user-id", help="Filter by user ID")

    sp = sub.add_parser("session-get", help="Get session by ID")
    sp.add_argument("session_id", help="Session ID")

    # Scores
    sp = sub.add_parser("scores", help="List scores")
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--cursor", help="Pagination cursor")
    sp.add_argument("--filter", help="Filter JSON string")

    sp = sub.add_parser("create-score", help="Create a score")
    sp.add_argument("--name", required=True, help="Score name")
    sp.add_argument("--trace-id", required=True, help="Trace ID")
    sp.add_argument("--value", type=float, help="Numeric value")
    sp.add_argument("--string-value", help="String value")
    sp.add_argument("--observation-id", help="Observation ID")
    sp.add_argument("--comment", help="Comment")
    sp.add_argument("--data-type", help="Data type (NUMERIC, BOOLEAN, CATEGORICAL)")

    sp = sub.add_parser("score-delete", help="Delete a score")
    sp.add_argument("score_id", help="Score ID")

    sp = sub.add_parser("score-configs", help="List score configurations")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)

    # Prompts
    sp = sub.add_parser("prompts", help="List prompts")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--name", help="Filter by name")

    sp = sub.add_parser("prompt-get", help="Get prompt by name")
    sp.add_argument("prompt_name", help="Prompt name")
    sp.add_argument("--version", type=int, help="Specific version")
    sp.add_argument("--label", help="Label (e.g. production)")

    sp = sub.add_parser("create-prompt", help="Create a prompt version")
    sp.add_argument("--name", required=True, help="Prompt name")
    sp.add_argument("--type", choices=["text", "chat"], default="text", help="Prompt type")
    sp.add_argument("--prompt-text", help="Prompt template text")
    sp.add_argument("--messages", help="Chat messages JSON array")
    sp.add_argument("--labels", help="Comma-separated labels")
    sp.add_argument("--tags", help="Comma-separated tags")
    sp.add_argument("--config", help="Config JSON")
    sp.add_argument("--commit-message", help="Commit message")

    # Datasets
    sp = sub.add_parser("datasets", help="List datasets")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)

    sp = sub.add_parser("dataset-get", help="Get dataset by name")
    sp.add_argument("dataset_name", help="Dataset name")

    sp = sub.add_parser("create-dataset", help="Create a dataset")
    sp.add_argument("--name", required=True, help="Dataset name")
    sp.add_argument("--description", help="Description")
    sp.add_argument("--metadata", help="Metadata JSON")

    sp = sub.add_parser("dataset-runs", help="List dataset runs")
    sp.add_argument("dataset_name", help="Dataset name")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)

    sp = sub.add_parser("dataset-items", help="List dataset items")
    sp.add_argument("--dataset-name", help="Filter by dataset name")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)

    sp = sub.add_parser("create-dataset-item", help="Create a dataset item")
    sp.add_argument("--dataset-name", required=True, help="Dataset name")
    sp.add_argument("--input", required=True, help="Input JSON")
    sp.add_argument("--expected-output", help="Expected output JSON")
    sp.add_argument("--metadata", help="Metadata JSON")
    sp.add_argument("--source-trace-id", help="Source trace ID")
    sp.add_argument("--source-observation-id", help="Source observation ID")
    sp.add_argument("--id", help="Custom item ID")

    # Models
    sp = sub.add_parser("models", help="List models")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=25)

    sp = sub.add_parser("model-get", help="Get model by ID")
    sp.add_argument("model_id", help="Model ID")

    # Metrics
    sp = sub.add_parser("metrics", help="Get metrics")
    sp.add_argument("--query", help="Query JSON string")

    return p


DISPATCH = {
    "health": cmd_health,
    "projects": cmd_projects,
    "traces": cmd_traces,
    "trace-get": cmd_trace_get,
    "trace-delete": cmd_trace_delete,
    "trace-bookmark": cmd_trace_bookmark,
    "trace-unbookmark": cmd_trace_unbookmark,
    "observations": cmd_observations,
    "observation-get": cmd_observation_get,
    "sessions": cmd_sessions,
    "session-get": cmd_session_get,
    "scores": cmd_scores,
    "create-score": cmd_score_create,
    "score-delete": cmd_score_delete,
    "score-configs": cmd_score_configs,
    "prompts": cmd_prompts,
    "prompt-get": cmd_prompt_get,
    "create-prompt": cmd_prompt_create,
    "datasets": cmd_datasets,
    "dataset-get": cmd_dataset_get,
    "create-dataset": cmd_dataset_create,
    "dataset-runs": cmd_dataset_runs,
    "dataset-items": cmd_dataset_items,
    "create-dataset-item": cmd_dataset_item_create,
    "models": cmd_models,
    "model-get": cmd_model_get,
    "metrics": cmd_metrics,
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
