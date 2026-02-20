#!/usr/bin/env python3
"""Linear CLI — issue tracking and project management via Linear GraphQL API."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_api_key():
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        print("Error: LINEAR_API_KEY not set", file=sys.stderr)
        print("Add to ~/.claude/settings.json:", file=sys.stderr)
        print('  {"env": {"LINEAR_API_KEY": "lin_api_..."}}', file=sys.stderr)
        sys.exit(1)
    return key


def graphql(query, variables=None):
    key = get_api_key()
    body = {"query": query}
    if variables:
        body["variables"] = variables
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": key,
    }
    for attempt in range(4):
        req = urllib.request.Request(
            "https://api.linear.app/graphql",
            data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if "errors" in result:
                    for err in result["errors"]:
                        print(f"GraphQL error: {err.get('message', err)}", file=sys.stderr)
                    if not result.get("data"):
                        sys.exit(1)
                return result.get("data", {})
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                if attempt < 3:
                    print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                print("Error: Rate limited after retries", file=sys.stderr)
                sys.exit(1)
            error_body = e.read().decode("utf-8")
            print(f"HTTP {e.code}: {error_body}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"Connection error: {e.reason}", file=sys.stderr)
            sys.exit(1)


def output(args, data, text_fn):
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        text_fn(data)


def priority_label(p):
    return {0: "None", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}.get(p, "?")


def fmt_issue_line(node):
    ident = node.get("identifier", "?")
    title = node.get("title", "")
    state = node.get("state", {}).get("name", "?") if node.get("state") else "?"
    assignee = node.get("assignee", {}).get("name", "Unassigned") if node.get("assignee") else "Unassigned"
    pri = priority_label(node.get("priority", 0))
    labels = ", ".join(l["name"] for l in node.get("labels", {}).get("nodes", [])) if node.get("labels") else ""
    label_str = f" [{labels}]" if labels else ""
    return f"{ident:<10} {pri:<8} {state:<15} {assignee:<20} {title}{label_str}"


# ─── Viewer ──────────────────────────────────────────────────────────────────

def cmd_me(args):
    data = graphql("{ viewer { id name email admin active } }")
    def fmt(d):
        v = d["viewer"]
        print(f"Logged in as: {v['name']}")
        print(f"  Email: {v['email']}")
        print(f"  ID: {v['id']}")
        print(f"  Admin: {v.get('admin', False)}")
    output(args, data, fmt)


# ─── Teams ───────────────────────────────────────────────────────────────────

def cmd_teams(args):
    data = graphql("""
        { teams { nodes { id name key description } } }
    """)
    def fmt(d):
        teams = d["teams"]["nodes"]
        if not teams:
            print("No teams found.")
            return
        print(f"{'Key':<8} {'Name':<25} ID")
        print("-" * 70)
        for t in teams:
            print(f"{t['key']:<8} {t['name']:<25} {t['id']}")
    output(args, data, fmt)


def cmd_team_states(args):
    data = graphql("""
        query($teamId: String!) {
            team(id: $teamId) {
                name key
                states { nodes { id name type position } }
            }
        }
    """, {"teamId": args.team})
    def fmt(d):
        team = d["team"]
        states = sorted(team["states"]["nodes"], key=lambda s: s["position"])
        print(f"Workflow states for {team['name']} ({team['key']}):\n")
        print(f"  {'Name':<20} {'Type':<12} ID")
        print(f"  {'-'*60}")
        for s in states:
            print(f"  {s['name']:<20} {s['type']:<12} {s['id']}")
    output(args, data, fmt)


def cmd_team_labels(args):
    data = graphql("""
        query($teamId: String!) {
            team(id: $teamId) {
                name key
                labels { nodes { id name color } }
            }
        }
    """, {"teamId": args.team})
    def fmt(d):
        team = d["team"]
        labels = team["labels"]["nodes"]
        print(f"Labels for {team['name']} ({team['key']}):\n")
        if not labels:
            print("  No labels.")
            return
        for l in labels:
            print(f"  {l['name']:<25} {l['color']:<10} {l['id']}")
    output(args, data, fmt)


def cmd_team_members(args):
    data = graphql("""
        query($teamId: String!) {
            team(id: $teamId) {
                name key
                members { nodes { id name email active } }
            }
        }
    """, {"teamId": args.team})
    def fmt(d):
        team = d["team"]
        members = team["members"]["nodes"]
        print(f"Members of {team['name']} ({team['key']}):\n")
        print(f"  {'Name':<25} {'Email':<35} {'Active':<8} ID")
        print(f"  {'-'*80}")
        for m in members:
            active = "Yes" if m.get("active") else "No"
            print(f"  {m['name']:<25} {m.get('email','?'):<35} {active:<8} {m['id']}")
    output(args, data, fmt)


# ─── Issues ──────────────────────────────────────────────────────────────────

ISSUE_FIELDS = """
    id identifier title description priority priorityLabel
    estimate dueDate url createdAt updatedAt
    state { id name type }
    assignee { id name email }
    creator { id name }
    team { id name key }
    project { id name }
    cycle { id name number }
    labels { nodes { id name color } }
    parent { id identifier title }
    children { nodes { id identifier title state { name } } }
"""

ISSUE_LIST_FIELDS = """
    id identifier title priority
    state { name type }
    assignee { name }
    labels { nodes { name } }
    createdAt updatedAt
"""


def cmd_issue_get(args):
    data = graphql(f"""
        query($id: String!) {{
            issue(id: $id) {{ {ISSUE_FIELDS}
                comments {{ nodes {{ id body user {{ name }} createdAt }} }}
            }}
        }}
    """, {"id": args.id})
    def fmt(d):
        i = d["issue"]
        print(f"{i['identifier']}: {i['title']}")
        print(f"  Status:   {i['state']['name']} ({i['state']['type']})")
        print(f"  Priority: {i.get('priorityLabel', 'None')}")
        assignee = i['assignee']['name'] if i.get('assignee') else 'Unassigned'
        print(f"  Assignee: {assignee}")
        creator = i['creator']['name'] if i.get('creator') else '?'
        print(f"  Creator:  {creator}")
        print(f"  Team:     {i['team']['name']} ({i['team']['key']})")
        if i.get('project'):
            print(f"  Project:  {i['project']['name']}")
        if i.get('cycle'):
            print(f"  Cycle:    {i['cycle']['name']} (#{i['cycle']['number']})")
        if i.get('estimate'):
            print(f"  Estimate: {i['estimate']}")
        if i.get('dueDate'):
            print(f"  Due:      {i['dueDate']}")
        labels = [l['name'] for l in i.get('labels', {}).get('nodes', [])]
        if labels:
            print(f"  Labels:   {', '.join(labels)}")
        if i.get('parent'):
            print(f"  Parent:   {i['parent']['identifier']} - {i['parent']['title']}")
        children = i.get('children', {}).get('nodes', [])
        if children:
            print(f"  Children: {len(children)}")
            for c in children:
                print(f"    {c['identifier']}: {c['title']} [{c['state']['name']}]")
        print(f"  URL:      {i['url']}")
        print(f"  Created:  {i['createdAt']}")
        print(f"  Updated:  {i['updatedAt']}")
        if i.get('description'):
            print(f"\n--- Description ---\n{i['description']}")
        comments = i.get('comments', {}).get('nodes', [])
        if comments:
            print(f"\n--- Comments ({len(comments)}) ---")
            for c in comments:
                author = c.get('user', {}).get('name', '?') if c.get('user') else '?'
                print(f"\n[{c['createdAt'][:16]}] {author}:")
                print(f"  {c['body']}")
    output(args, data, fmt)


def cmd_issue_list(args):
    filters = []
    if args.team:
        filters.append(f'team: {{ key: {{ eq: "{args.team}" }} }}')
    if args.state:
        filters.append(f'state: {{ name: {{ eqIgnoreCase: "{args.state}" }} }}')
    if args.assignee:
        filters.append(f'assignee: {{ name: {{ containsIgnoreCase: "{args.assignee}" }} }}')
    if args.label:
        filters.append(f'labels: {{ name: {{ eqIgnoreCase: "{args.label}" }} }}')
    if args.project:
        filters.append(f'project: {{ name: {{ containsIgnoreCase: "{args.project}" }} }}')
    if args.priority is not None:
        filters.append(f'priority: {{ eq: {args.priority} }}')

    filter_str = ", ".join(filters)
    filter_arg = f", filter: {{ {filter_str} }}" if filter_str else ""

    data = graphql(f"""
        query {{
            issues(first: {args.limit}, orderBy: updatedAt{filter_arg}) {{
                nodes {{ {ISSUE_LIST_FIELDS} }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
    """)
    def fmt(d):
        issues = d["issues"]["nodes"]
        if not issues:
            print("No issues found.")
            return
        print(f"{'ID':<10} {'Pri':<8} {'Status':<15} {'Assignee':<20} Title")
        print("-" * 90)
        for i in issues:
            print(fmt_issue_line(i))
        pi = d["issues"]["pageInfo"]
        if pi.get("hasNextPage"):
            print(f"\n(more results available)")
    output(args, data, fmt)


def cmd_issue_create(args):
    variables = {
        "teamId": args.team,
        "title": args.title,
    }
    optional_fields = []
    if args.description:
        optional_fields.append("$description: String")
        variables["description"] = args.description
    if args.priority is not None:
        optional_fields.append("$priority: Int")
        variables["priority"] = args.priority
    if args.assignee:
        optional_fields.append("$assigneeId: String")
        variables["assigneeId"] = args.assignee
    if args.state:
        optional_fields.append("$stateId: String")
        variables["stateId"] = args.state
    if args.project:
        optional_fields.append("$projectId: String")
        variables["projectId"] = args.project
    if args.estimate:
        optional_fields.append("$estimate: Int")
        variables["estimate"] = args.estimate
    if args.due:
        optional_fields.append("$dueDate: TimelessDate")
        variables["dueDate"] = args.due
    if args.parent:
        optional_fields.append("$parentId: String")
        variables["parentId"] = args.parent
    if args.label:
        optional_fields.append("$labelIds: [String!]")
        variables["labelIds"] = args.label

    var_defs = ", ".join(["$teamId: String!", "$title: String!"] + optional_fields)
    input_fields = ["teamId: $teamId", "title: $title"]
    for f in optional_fields:
        name = f.split(":")[0].strip().lstrip("$")
        input_fields.append(f"{name}: ${name}")

    data = graphql(f"""
        mutation({var_defs}) {{
            issueCreate(input: {{ {', '.join(input_fields)} }}) {{
                success
                issue {{ id identifier title url state {{ name }} }}
            }}
        }}
    """, variables)
    def fmt(d):
        r = d["issueCreate"]
        if r["success"]:
            i = r["issue"]
            print(f"Created: {i['identifier']} - {i['title']}")
            print(f"  State: {i['state']['name']}")
            print(f"  URL:   {i['url']}")
        else:
            print("Failed to create issue.", file=sys.stderr)
    output(args, data, fmt)


def cmd_issue_update(args):
    variables = {"id": args.id}
    input_parts = []

    if args.title:
        variables["title"] = args.title
        input_parts.append("title: $title")
    if args.description is not None:
        variables["description"] = args.description
        input_parts.append("description: $description")
    if args.priority is not None:
        variables["priority"] = args.priority
        input_parts.append("priority: $priority")
    if args.assignee:
        variables["assigneeId"] = args.assignee
        input_parts.append("assigneeId: $assigneeId")
    if args.state:
        variables["stateId"] = args.state
        input_parts.append("stateId: $stateId")
    if args.project:
        variables["projectId"] = args.project
        input_parts.append("projectId: $projectId")
    if args.estimate is not None:
        variables["estimate"] = args.estimate
        input_parts.append("estimate: $estimate")
    if args.due:
        variables["dueDate"] = args.due
        input_parts.append("dueDate: $dueDate")
    if args.label:
        variables["labelIds"] = args.label
        input_parts.append("labelIds: $labelIds")

    if not input_parts:
        print("Nothing to update. Use --title, --description, --priority, --assignee, --state, --project, --estimate, --due, or --label.", file=sys.stderr)
        sys.exit(1)

    # Build variable type definitions
    var_types = {"id": "String!"}
    type_map = {
        "title": "String", "description": "String", "priority": "Int",
        "assigneeId": "String", "stateId": "String", "projectId": "String",
        "estimate": "Int", "dueDate": "TimelessDate", "labelIds": "[String!]",
    }
    for part in input_parts:
        var_name = part.split(":")[0].strip()
        gql_var = var_name
        var_types[gql_var] = type_map.get(var_name, "String")

    var_defs = ", ".join(f"${k}: {v}" for k, v in var_types.items())

    data = graphql(f"""
        mutation({var_defs}) {{
            issueUpdate(id: $id, input: {{ {', '.join(input_parts)} }}) {{
                success
                issue {{ id identifier title state {{ name }} assignee {{ name }} }}
            }}
        }}
    """, variables)
    def fmt(d):
        r = d["issueUpdate"]
        if r["success"]:
            i = r["issue"]
            assignee = i['assignee']['name'] if i.get('assignee') else 'Unassigned'
            print(f"Updated: {i['identifier']} - {i['title']} [{i['state']['name']}] ({assignee})")
        else:
            print("Failed to update issue.", file=sys.stderr)
    output(args, data, fmt)


def cmd_issue_assign(args):
    data = graphql("""
        mutation($id: String!, $assigneeId: String) {
            issueUpdate(id: $id, input: { assigneeId: $assigneeId }) {
                success
                issue { identifier assignee { name } }
            }
        }
    """, {"id": args.id, "assigneeId": args.user if args.user != "none" else None})
    def fmt(d):
        r = d["issueUpdate"]
        if r["success"]:
            i = r["issue"]
            assignee = i['assignee']['name'] if i.get('assignee') else 'Unassigned'
            print(f"{i['identifier']} assigned to {assignee}")
    output(args, data, fmt)


def cmd_issue_move(args):
    data = graphql("""
        mutation($id: String!, $stateId: String!) {
            issueUpdate(id: $id, input: { stateId: $stateId }) {
                success
                issue { identifier title state { name type } }
            }
        }
    """, {"id": args.id, "stateId": args.state})
    def fmt(d):
        r = d["issueUpdate"]
        if r["success"]:
            i = r["issue"]
            print(f"{i['identifier']} -> {i['state']['name']}")
    output(args, data, fmt)


def cmd_issue_archive(args):
    data = graphql("""
        mutation($id: String!) {
            issueArchive(id: $id) { success }
        }
    """, {"id": args.id})
    def fmt(d):
        if d["issueArchive"]["success"]:
            print(f"Archived: {args.id}")
    output(args, data, fmt)


def cmd_issue_delete(args):
    data = graphql("""
        mutation($id: String!) {
            issueDelete(id: $id) { success }
        }
    """, {"id": args.id})
    def fmt(d):
        if d["issueDelete"]["success"]:
            print(f"Deleted: {args.id}")
    output(args, data, fmt)


def cmd_issue_search(args):
    data = graphql(f"""
        query($term: String!) {{
            searchIssues(term: $term, first: {args.limit}) {{
                nodes {{ {ISSUE_LIST_FIELDS} }}
            }}
        }}
    """, {"term": args.query})
    def fmt(d):
        issues = d["searchIssues"]["nodes"]
        if not issues:
            print("No issues found.")
            return
        print(f"{'ID':<10} {'Pri':<8} {'Status':<15} {'Assignee':<20} Title")
        print("-" * 90)
        for i in issues:
            print(fmt_issue_line(i))
    output(args, data, fmt)


# ─── Comments ────────────────────────────────────────────────────────────────

def cmd_comment_list(args):
    data = graphql(f"""
        query($id: String!) {{
            issue(id: $id) {{
                identifier title
                comments(first: {args.limit}) {{
                    nodes {{
                        id body
                        user {{ name }}
                        createdAt updatedAt
                    }}
                }}
            }}
        }}
    """, {"id": args.id})
    def fmt(d):
        i = d["issue"]
        comments = i["comments"]["nodes"]
        print(f"Comments on {i['identifier']}: {i['title']}\n")
        if not comments:
            print("  No comments.")
            return
        for c in comments:
            author = c.get("user", {}).get("name", "?") if c.get("user") else "?"
            print(f"[{c['createdAt'][:16]}] {author} (ID: {c['id']})")
            print(f"  {c['body']}\n")
    output(args, data, fmt)


def cmd_comment_add(args):
    data = graphql("""
        mutation($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
                comment { id body user { name } createdAt }
            }
        }
    """, {"issueId": args.id, "body": args.body})
    def fmt(d):
        r = d["commentCreate"]
        if r["success"]:
            c = r["comment"]
            print(f"Comment added (ID: {c['id']})")
    output(args, data, fmt)


def cmd_comment_delete(args):
    data = graphql("""
        mutation($id: String!) {
            commentDelete(id: $id) { success }
        }
    """, {"id": args.comment_id})
    def fmt(d):
        if d["commentDelete"]["success"]:
            print(f"Comment deleted: {args.comment_id}")
    output(args, data, fmt)


# ─── Labels ──────────────────────────────────────────────────────────────────

def cmd_label_add(args):
    data = graphql("""
        mutation($id: String!, $labelId: String!) {
            issueAddLabel(id: $id, labelId: $labelId) {
                success
                issue { identifier labels { nodes { name } } }
            }
        }
    """, {"id": args.id, "labelId": args.label})
    def fmt(d):
        r = d["issueAddLabel"]
        if r["success"]:
            i = r["issue"]
            labels = [l["name"] for l in i["labels"]["nodes"]]
            print(f"{i['identifier']} labels: {', '.join(labels)}")
    output(args, data, fmt)


def cmd_label_remove(args):
    data = graphql("""
        mutation($id: String!, $labelId: String!) {
            issueRemoveLabel(id: $id, labelId: $labelId) {
                success
                issue { identifier labels { nodes { name } } }
            }
        }
    """, {"id": args.id, "labelId": args.label})
    def fmt(d):
        r = d["issueRemoveLabel"]
        if r["success"]:
            i = r["issue"]
            labels = [l["name"] for l in i["labels"]["nodes"]]
            print(f"{i['identifier']} labels: {', '.join(labels) if labels else '(none)'}")
    output(args, data, fmt)


def cmd_label_create(args):
    variables = {"teamId": args.team, "name": args.name}
    if args.color:
        variables["color"] = args.color
    color_def = ", $color: String" if args.color else ""
    color_input = ", color: $color" if args.color else ""
    data = graphql(f"""
        mutation($teamId: String!, $name: String!{color_def}) {{
            issueLabelCreate(input: {{ teamId: $teamId, name: $name{color_input} }}) {{
                success
                issueLabel {{ id name color }}
            }}
        }}
    """, variables)
    def fmt(d):
        r = d["issueLabelCreate"]
        if r["success"]:
            l = r["issueLabel"]
            print(f"Created label: {l['name']} ({l['color']}) ID: {l['id']}")
    output(args, data, fmt)


# ─── Projects ────────────────────────────────────────────────────────────────

def cmd_project_list(args):
    data = graphql("""
        { projects(first: 50) {
            nodes {
                id name state description
                progress startDate targetDate
                lead { name }
                teams { nodes { key } }
            }
        } }
    """)
    def fmt(d):
        projects = d["projects"]["nodes"]
        if not projects:
            print("No projects found.")
            return
        print(f"{'Name':<40} {'State':<12} {'Lead':<20} {'Progress':<10} ID")
        print("-" * 110)
        for p in projects:
            lead = p['lead']['name'] if p.get('lead') else "?"
            progress = f"{int(p.get('progress', 0) * 100)}%" if p.get('progress') is not None else "?"
            teams = ",".join(t['key'] for t in p.get('teams', {}).get('nodes', []))
            name = p['name']
            if teams:
                name = f"{name} [{teams}]"
            print(f"{name:<40} {p.get('state','?'):<12} {lead:<20} {progress:<10} {p['id']}")
    output(args, data, fmt)


def cmd_project_get(args):
    data = graphql(f"""
        query($id: String!) {{
            project(id: $id) {{
                id name state description
                progress startDate targetDate url
                lead {{ name email }}
                teams {{ nodes {{ key name }} }}
                issues(first: 50) {{ nodes {{ {ISSUE_LIST_FIELDS} }} }}
            }}
        }}
    """, {"id": args.id})
    def fmt(d):
        p = d["project"]
        print(f"Project: {p['name']}")
        print(f"  State:    {p.get('state', '?')}")
        if p.get('lead'):
            print(f"  Lead:     {p['lead']['name']}")
        progress = f"{int(p.get('progress', 0) * 100)}%" if p.get('progress') is not None else "?"
        print(f"  Progress: {progress}")
        if p.get('startDate'):
            print(f"  Start:    {p['startDate']}")
        if p.get('targetDate'):
            print(f"  Target:   {p['targetDate']}")
        if p.get('url'):
            print(f"  URL:      {p['url']}")
        if p.get('description'):
            print(f"\n{p['description']}")
        issues = p.get('issues', {}).get('nodes', [])
        if issues:
            print(f"\n--- Issues ({len(issues)}) ---")
            print(f"{'ID':<10} {'Pri':<8} {'Status':<15} {'Assignee':<20} Title")
            print("-" * 90)
            for i in issues:
                print(fmt_issue_line(i))
    output(args, data, fmt)


def cmd_project_create(args):
    variables = {"name": args.name}
    extra_defs = ""
    extra_inputs = ""
    if args.description:
        variables["description"] = args.description
        extra_defs += ", $description: String"
        extra_inputs += ", description: $description"
    if args.team:
        variables["teamIds"] = [args.team]
        extra_defs += ", $teamIds: [String!]"
        extra_inputs += ", teamIds: $teamIds"
    data = graphql(f"""
        mutation($name: String!{extra_defs}) {{
            projectCreate(input: {{ name: $name{extra_inputs} }}) {{
                success
                project {{ id name state url }}
            }}
        }}
    """, variables)
    def fmt(d):
        r = d["projectCreate"]
        if r["success"]:
            p = r["project"]
            print(f"Created project: {p['name']}")
            print(f"  ID:  {p['id']}")
            if p.get('url'):
                print(f"  URL: {p['url']}")
    output(args, data, fmt)


def cmd_project_delete(args):
    data = graphql("""
        mutation($id: String!) {
            projectDelete(id: $id) { success }
        }
    """, {"id": args.id})
    def fmt(d):
        if d["projectDelete"]["success"]:
            print(f"Deleted project: {args.id}")
    output(args, data, fmt)


# ─── Cycles ──────────────────────────────────────────────────────────────────

def cmd_cycle_list(args):
    data = graphql("""
        query($teamId: String!) {
            team(id: $teamId) {
                name key
                cycles(first: 20, orderBy: createdAt) {
                    nodes {
                        id name number
                        startsAt endsAt
                        progress
                    }
                }
            }
        }
    """, {"teamId": args.team})
    def fmt(d):
        team = d["team"]
        cycles = team["cycles"]["nodes"]
        print(f"Cycles for {team['name']} ({team['key']}):\n")
        if not cycles:
            print("  No cycles.")
            return
        print(f"  {'#':<5} {'Name':<30} {'Start':<12} {'End':<12} Progress")
        print(f"  {'-'*75}")
        for c in cycles:
            start = c.get("startsAt", "")[:10] if c.get("startsAt") else "?"
            end = c.get("endsAt", "")[:10] if c.get("endsAt") else "?"
            prog = c.get("progress", 0)
            pct = f"{int(prog * 100)}%" if prog is not None else "?"
            name = c.get('name') or f"Cycle {c.get('number', '?')}"
            num = str(c.get('number', '?'))
            print(f"  {num:<5} {name:<30} {start:<12} {end:<12} {pct}")
    output(args, data, fmt)


# ─── Helpers: resolve by name ────────────────────────────────────────────────

def cmd_resolve(args):
    """Resolve a team key, state name, label name, or user name to their IDs."""
    entity = args.entity
    query_str = args.query

    if entity == "team":
        data = graphql('{ teams { nodes { id name key } } }')
        for t in data["teams"]["nodes"]:
            if query_str.lower() in (t["key"].lower(), t["name"].lower()):
                print(f"{t['key']}: {t['id']}")
                return
        print(f"No team matching '{query_str}'", file=sys.stderr)
        sys.exit(1)

    elif entity == "state":
        if not args.team:
            print("--team required for state resolution", file=sys.stderr)
            sys.exit(1)
        data = graphql("""
            query($teamId: String!) {
                team(id: $teamId) { states { nodes { id name type } } }
            }
        """, {"teamId": args.team})
        for s in data["team"]["states"]["nodes"]:
            if query_str.lower() in s["name"].lower():
                print(f"{s['name']} ({s['type']}): {s['id']}")
                return
        print(f"No state matching '{query_str}'", file=sys.stderr)
        sys.exit(1)

    elif entity == "label":
        data = graphql('{ issueLabels(first: 100) { nodes { id name color } } }')
        for l in data["issueLabels"]["nodes"]:
            if query_str.lower() in l["name"].lower():
                print(f"{l['name']}: {l['id']}")
                return
        print(f"No label matching '{query_str}'", file=sys.stderr)
        sys.exit(1)

    elif entity == "user":
        data = graphql('{ users(first: 50) { nodes { id name email active } } }')
        for u in data["users"]["nodes"]:
            if query_str.lower() in u["name"].lower() or query_str.lower() in u.get("email", "").lower():
                active = "active" if u.get("active") else "inactive"
                print(f"{u['name']} ({u.get('email','?')}, {active}): {u['id']}")
                return
        print(f"No user matching '{query_str}'", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Unknown entity: {entity}. Use: team, state, label, user", file=sys.stderr)
        sys.exit(1)


# ─── My Issues ───────────────────────────────────────────────────────────────

def cmd_my_issues(args):
    state_filter = ""
    if args.state:
        state_filter = f', filter: {{ state: {{ name: {{ eqIgnoreCase: "{args.state}" }} }} }}'
    data = graphql(f"""
        {{
            viewer {{
                assignedIssues(first: {args.limit}, orderBy: updatedAt{state_filter}) {{
                    nodes {{ {ISSUE_LIST_FIELDS} }}
                }}
            }}
        }}
    """)
    def fmt(d):
        issues = d["viewer"]["assignedIssues"]["nodes"]
        if not issues:
            print("No issues assigned to you.")
            return
        print(f"{'ID':<10} {'Pri':<8} {'Status':<15} {'Assignee':<20} Title")
        print("-" * 90)
        for i in issues:
            print(fmt_issue_line(i))
    output(args, data, fmt)


# ─── Raw GraphQL ─────────────────────────────────────────────────────────────

def cmd_raw(args):
    variables = None
    if args.variables:
        variables = json.loads(args.variables)
    data = graphql(args.query, variables)
    print(json.dumps(data, indent=2))


# ─── Setup (generate context.md) ─────────────────────────────────────────────

def cmd_setup(args):
    """Query the Linear API and generate context.md with workspace-specific IDs."""
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    context_path = os.path.join(skill_dir, "context.md")

    print("Querying Linear workspace...")

    # Split into smaller queries to stay under complexity limit
    base = graphql("""
        {
            viewer { id name email }
            organization { name urlKey }
            teams { nodes { id name key } }
            projects(first: 50) { nodes { id name state } }
        }
    """)

    viewer = base["viewer"]
    org = base.get("organization", {})
    teams = base["teams"]["nodes"]
    projects = base["projects"]["nodes"]

    # Fetch details per team (states, labels, members)
    for team in teams:
        detail = graphql("""
            query($id: String!) {
                team(id: $id) {
                    states { nodes { id name type position } }
                    labels { nodes { id name color } }
                    members { nodes { id name email active } }
                }
            }
        """, {"id": team["id"]})
        t = detail["team"]
        team["states"] = t["states"]
        team["labels"] = t["labels"]
        team["members"] = t["members"]

    lines = []
    lines.append("# Linear Workspace Context")
    lines.append("")
    lines.append("> Auto-generated by `linear.py setup`. Re-run to refresh.")
    lines.append("> This file is gitignored — it contains workspace-specific IDs.")
    lines.append("")

    # Organization
    lines.append(f"**Organization**: {org.get('name', '?')} ({org.get('urlKey', '?')})")
    lines.append("")

    # Current user
    lines.append("## Current User")
    lines.append("")
    lines.append(f"- **Name**: {viewer['name']}")
    lines.append(f"- **Email**: {viewer['email']}")
    lines.append(f"- **User ID**: `{viewer['id']}`")
    lines.append("")
    lines.append("**Default assignee**: When creating issues, always include "
                 f"`--assignee {viewer['id']}` unless the user explicitly says "
                 "to assign someone else or leave unassigned.")
    lines.append("")

    # Teams
    lines.append("## Teams")
    lines.append("")
    lines.append("| Key | Name | Team ID |")
    lines.append("|-----|------|---------|")
    for t in teams:
        lines.append(f"| {t['key']} | {t['name']} | `{t['id']}` |")
    lines.append("")

    # Per-team states, labels, members
    for t in teams:
        lines.append(f"### {t['name']} ({t['key']}) — Workflow States")
        lines.append("")
        lines.append("| State | Type | State ID |")
        lines.append("|-------|------|----------|")
        states = sorted(t["states"]["nodes"], key=lambda s: s["position"])
        for s in states:
            lines.append(f"| {s['name']} | {s['type']} | `{s['id']}` |")
        lines.append("")

        labels = t["labels"]["nodes"]
        if labels:
            lines.append(f"### {t['name']} ({t['key']}) — Labels")
            lines.append("")
            lines.append("| Name | Color | Label ID |")
            lines.append("|------|-------|----------|")
            for l in labels:
                lines.append(f"| {l['name']} | {l['color']} | `{l['id']}` |")
            lines.append("")

        members = [m for m in t["members"]["nodes"] if m.get("active")]
        if members:
            lines.append(f"### {t['name']} ({t['key']}) — Members")
            lines.append("")
            lines.append("| Name | Email | User ID |")
            lines.append("|------|-------|---------|")
            for m in members:
                lines.append(f"| {m['name']} | {m.get('email','?')} | `{m['id']}` |")
            lines.append("")

    # Projects
    if projects:
        lines.append("## Projects")
        lines.append("")
        lines.append("| Name | State | Project ID |")
        lines.append("|------|-------|------------|")
        for p in projects:
            lines.append(f"| {p['name']} | {p.get('state','?')} | `{p['id']}` |")
        lines.append("")

    content = "\n".join(lines)
    with open(context_path, "w") as f:
        f.write(content)
    print(f"Wrote {context_path}")
    print(f"  Organization: {org.get('name', '?')}")
    print(f"  Teams: {len(teams)}")
    print(f"  Projects: {len(projects)}")
    print(f"  Your ID: {viewer['id']}")


# ─── Parser ──────────────────────────────────────────────────────────────────

def main():
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--json", action="store_true", help="Output raw JSON")

    parser = argparse.ArgumentParser(description="Linear CLI", prog="linear", parents=[parent])
    subs = parser.add_subparsers(dest="command", required=True)
    _orig = subs.add_parser
    subs.add_parser = lambda *a, **kw: _orig(*a, parents=[parent], **{k: v for k, v in kw.items() if k != "parents"})

    # --- Viewer ---
    p = subs.add_parser("me", help="Show current user")
    p.set_defaults(func=cmd_me)

    p = subs.add_parser("my-issues", help="List issues assigned to me")
    p.add_argument("--state", help="Filter by state name")
    p.add_argument("--limit", type=int, default=25, help="Max results")
    p.set_defaults(func=cmd_my_issues)

    # --- Teams ---
    p = subs.add_parser("teams", help="List teams")
    p.set_defaults(func=cmd_teams)

    p = subs.add_parser("team-states", help="List workflow states for a team")
    p.add_argument("team", help="Team ID or key")
    p.set_defaults(func=cmd_team_states)

    p = subs.add_parser("team-labels", help="List labels for a team")
    p.add_argument("team", help="Team ID or key")
    p.set_defaults(func=cmd_team_labels)

    p = subs.add_parser("team-members", help="List team members")
    p.add_argument("team", help="Team ID or key")
    p.set_defaults(func=cmd_team_members)

    # --- Issues ---
    p = subs.add_parser("issue-get", help="Get issue details")
    p.add_argument("id", help="Issue ID or identifier (e.g. ENG-123)")
    p.set_defaults(func=cmd_issue_get)

    p = subs.add_parser("issue-list", help="List issues with filters")
    p.add_argument("--team", help="Team key (e.g. ENG)")
    p.add_argument("--state", help="State name (e.g. 'In Progress')")
    p.add_argument("--assignee", help="Assignee name (substring)")
    p.add_argument("--label", help="Label name")
    p.add_argument("--project", help="Project name (substring)")
    p.add_argument("--priority", type=int, choices=[0,1,2,3,4], help="Priority (1=Urgent, 4=Low)")
    p.add_argument("--limit", type=int, default=25, help="Max results")
    p.set_defaults(func=cmd_issue_list)

    p = subs.add_parser("issue-create", help="Create an issue")
    p.add_argument("team", help="Team ID")
    p.add_argument("--title", required=True, help="Issue title")
    p.add_argument("--description", help="Description (markdown)")
    p.add_argument("--priority", type=int, choices=[0,1,2,3,4], help="Priority (1=Urgent, 4=Low)")
    p.add_argument("--assignee", help="Assignee user ID")
    p.add_argument("--state", help="Initial state ID")
    p.add_argument("--project", help="Project ID")
    p.add_argument("--estimate", type=int, help="Point estimate")
    p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    p.add_argument("--parent", help="Parent issue ID")
    p.add_argument("--label", action="append", help="Label ID (repeat for multiple)")
    p.set_defaults(func=cmd_issue_create)

    p = subs.add_parser("issue-update", help="Update an issue")
    p.add_argument("id", help="Issue ID or identifier")
    p.add_argument("--title", help="New title")
    p.add_argument("--description", help="New description (markdown)")
    p.add_argument("--priority", type=int, choices=[0,1,2,3,4], help="Priority")
    p.add_argument("--assignee", help="Assignee user ID")
    p.add_argument("--state", help="State ID")
    p.add_argument("--project", help="Project ID")
    p.add_argument("--estimate", type=int, help="Point estimate")
    p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    p.add_argument("--label", action="append", help="Label ID (replaces all; repeat for multiple)")
    p.set_defaults(func=cmd_issue_update)

    p = subs.add_parser("issue-assign", help="Assign/unassign an issue")
    p.add_argument("id", help="Issue ID or identifier")
    p.add_argument("user", help="User ID (or 'none' to unassign)")
    p.set_defaults(func=cmd_issue_assign)

    p = subs.add_parser("issue-move", help="Move an issue to a new state")
    p.add_argument("id", help="Issue ID or identifier")
    p.add_argument("state", help="Target state ID")
    p.set_defaults(func=cmd_issue_move)

    p = subs.add_parser("issue-archive", help="Archive an issue")
    p.add_argument("id", help="Issue ID or identifier")
    p.set_defaults(func=cmd_issue_archive)

    p = subs.add_parser("issue-delete", help="Delete an issue")
    p.add_argument("id", help="Issue ID or identifier")
    p.set_defaults(func=cmd_issue_delete)

    p = subs.add_parser("issue-search", help="Full-text search issues")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=20, help="Max results")
    p.set_defaults(func=cmd_issue_search)

    # --- Comments ---
    p = subs.add_parser("comment-list", help="List comments on an issue")
    p.add_argument("id", help="Issue ID or identifier")
    p.add_argument("--limit", type=int, default=20, help="Max comments")
    p.set_defaults(func=cmd_comment_list)

    p = subs.add_parser("comment-add", help="Add a comment")
    p.add_argument("id", help="Issue ID or identifier")
    p.add_argument("body", help="Comment text (markdown)")
    p.set_defaults(func=cmd_comment_add)

    p = subs.add_parser("comment-delete", help="Delete a comment")
    p.add_argument("comment_id", help="Comment ID")
    p.set_defaults(func=cmd_comment_delete)

    # --- Labels ---
    p = subs.add_parser("label-add", help="Add a label to an issue")
    p.add_argument("id", help="Issue ID or identifier")
    p.add_argument("label", help="Label ID")
    p.set_defaults(func=cmd_label_add)

    p = subs.add_parser("label-remove", help="Remove a label from an issue")
    p.add_argument("id", help="Issue ID or identifier")
    p.add_argument("label", help="Label ID")
    p.set_defaults(func=cmd_label_remove)

    p = subs.add_parser("label-create", help="Create a new label")
    p.add_argument("team", help="Team ID")
    p.add_argument("--name", required=True, help="Label name")
    p.add_argument("--color", help="Color hex (e.g. #EB5757)")
    p.set_defaults(func=cmd_label_create)

    # --- Projects ---
    p = subs.add_parser("project-list", help="List projects")
    p.set_defaults(func=cmd_project_list)

    p = subs.add_parser("project-get", help="Get project details with issues")
    p.add_argument("id", help="Project ID")
    p.set_defaults(func=cmd_project_get)

    p = subs.add_parser("project-create", help="Create a project")
    p.add_argument("--name", required=True, help="Project name")
    p.add_argument("--description", help="Project description")
    p.add_argument("--team", help="Team ID to associate")
    p.set_defaults(func=cmd_project_create)

    p = subs.add_parser("project-delete", help="Delete a project")
    p.add_argument("id", help="Project ID")
    p.set_defaults(func=cmd_project_delete)

    # --- Cycles ---
    p = subs.add_parser("cycle-list", help="List cycles for a team")
    p.add_argument("team", help="Team ID")
    p.set_defaults(func=cmd_cycle_list)

    # --- Resolve ---
    p = subs.add_parser("resolve", help="Resolve name to ID (team, state, label, user)")
    p.add_argument("entity", choices=["team", "state", "label", "user"], help="Entity type")
    p.add_argument("query", help="Name to search for")
    p.add_argument("--team", help="Team ID (required for state)")
    p.set_defaults(func=cmd_resolve)

    # --- Raw ---
    p = subs.add_parser("raw", help="Execute raw GraphQL query")
    p.add_argument("query", help="GraphQL query string")
    p.add_argument("--variables", help="JSON variables")
    p.set_defaults(func=cmd_raw)

    # --- Setup ---
    p = subs.add_parser("setup", help="Generate context.md with workspace IDs")
    p.set_defaults(func=cmd_setup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
