#!/usr/bin/env python3
"""Google Sheets CLI - Read, write, and manage Google Spreadsheets via Sheets API v4."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_URL = "https://www.googleapis.com/drive/v3/files"
TOKEN_PATH = os.path.expanduser("~/.config/google-docs-mcp/token.json")

# --- Auth -------------------------------------------------------------------


def _load_token_file():
    """Load token.json from google-docs-mcp config."""
    if not os.path.exists(TOKEN_PATH):
        return None
    with open(TOKEN_PATH) as f:
        return json.load(f)


def _refresh_access_token(token_data):
    """Refresh an expired OAuth2 access token."""
    refresh_token = token_data.get("refresh_token")
    client_id = os.environ.get("GOOGLE_CLIENT_ID") or token_data.get("client_id")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or token_data.get("client_secret")

    if not all([refresh_token, client_id, client_secret]):
        return None

    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            token_data["access_token"] = result["access_token"]
            token_data["expiry"] = int(time.time()) + result.get("expires_in", 3600)
            # Save updated token
            with open(TOKEN_PATH, "w") as f:
                json.dump(token_data, f, indent=2)
            return result["access_token"]
    except urllib.error.URLError as e:
        print(f"Error refreshing token: {e}", file=sys.stderr)
        return None


def get_token():
    """Get a valid access token, refreshing if needed."""
    # 1. Check env var (direct token)
    token = os.environ.get("GOOGLE_SHEETS_ACCESS_TOKEN")
    if token:
        return token

    # 2. Load from google-docs-mcp token.json
    token_data = _load_token_file()
    if not token_data:
        print("Error: No Google auth token found.", file=sys.stderr)
        print("Either:", file=sys.stderr)
        print("  1. Set GOOGLE_SHEETS_ACCESS_TOKEN env var", file=sys.stderr)
        print("  2. Run google-docs-mcp auth: npx -y @anthropic-ai/google-docs-mcp auth", file=sys.stderr)
        print(f"     Token file expected at: {TOKEN_PATH}", file=sys.stderr)
        sys.exit(1)

    access_token = token_data.get("access_token")
    expiry = token_data.get("expiry", 0)

    # Check if token is expired (with 60s buffer)
    if expiry and (isinstance(expiry, (int, float)) and expiry < time.time() + 60):
        refreshed = _refresh_access_token(token_data)
        if refreshed:
            return refreshed

    if access_token:
        return access_token

    # Try refresh anyway
    refreshed = _refresh_access_token(token_data)
    if refreshed:
        return refreshed

    print("Error: Could not obtain a valid access token.", file=sys.stderr)
    sys.exit(1)


# --- HTTP Helpers -----------------------------------------------------------


def api(method, url, body=None, params=None):
    """Make an authenticated API request with retry logic."""
    token = get_token()

    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params)

    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
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
            print(f"Network error: {e.reason}", file=sys.stderr)
            sys.exit(1)
    sys.exit(1)


def fmt_json(data):
    print(json.dumps(data, indent=2))


def fmt_table(rows, columns):
    """Print aligned table with headers."""
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
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    print(header)
    print("  ".join("-" * widths[col] for col in columns))

    # Rows
    for row in rows:
        line = "  ".join(truncate(str(row.get(col, "")), widths[col]).ljust(widths[col]) for col in columns)
        print(line)


def truncate(s, n=80):
    s = str(s or "")
    return s[: n - 3] + "..." if len(s) > n else s


# --- Commands ---------------------------------------------------------------


def cmd_list(args):
    """List Google Sheets in Drive."""
    params = {
        "q": "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        "fields": "files(id,name,modifiedTime,createdTime),nextPageToken",
        "pageSize": args.limit,
        "orderBy": "modifiedTime desc",
    }
    if hasattr(args, "page_token") and args.page_token:
        params["pageToken"] = args.page_token

    result = api("GET", DRIVE_URL, params=params)
    files = result.get("files", [])

    if args.json:
        fmt_json(result)
        return

    rows = [
        {"ID": f["id"], "Name": f.get("name", ""), "Modified": f.get("modifiedTime", "")[:10]}
        for f in files
    ]
    fmt_table(rows, ["ID", "Name", "Modified"])

    npt = result.get("nextPageToken")
    if npt:
        print(f"\nNext page: --page-token {npt}")


def cmd_search(args):
    """Search for spreadsheets by name."""
    q = f"mimeType='application/vnd.google-apps.spreadsheet' and trashed=false and name contains '{args.query}'"
    params = {
        "q": q,
        "fields": "files(id,name,modifiedTime),nextPageToken",
        "pageSize": args.limit,
        "orderBy": "modifiedTime desc",
    }

    result = api("GET", DRIVE_URL, params=params)
    files = result.get("files", [])

    if args.json:
        fmt_json(result)
        return

    rows = [
        {"ID": f["id"], "Name": f.get("name", ""), "Modified": f.get("modifiedTime", "")[:10]}
        for f in files
    ]
    fmt_table(rows, ["ID", "Name", "Modified"])


def cmd_create(args):
    """Create a new spreadsheet."""
    body = {"properties": {"title": args.title}}
    if args.sheets:
        body["sheets"] = [{"properties": {"title": t}} for t in args.sheets]

    result = api("POST", BASE_URL, body=body)

    if args.json:
        fmt_json(result)
        return

    sid = result.get("spreadsheetId", "")
    title = result.get("properties", {}).get("title", "")
    url = result.get("spreadsheetUrl", "")
    sheets = [s.get("properties", {}).get("title", "") for s in result.get("sheets", [])]
    print(f"Created: {title}")
    print(f"ID: {sid}")
    print(f"URL: {url}")
    print(f"Sheets: {', '.join(sheets)}")


def cmd_info(args):
    """Get spreadsheet metadata."""
    url = f"{BASE_URL}/{args.spreadsheet_id}"
    params = {"fields": "spreadsheetId,properties,sheets.properties,spreadsheetUrl"}
    result = api("GET", url, params=params)

    if args.json:
        fmt_json(result)
        return

    props = result.get("properties", {})
    print(f"Title: {props.get('title', '')}")
    print(f"ID: {result.get('spreadsheetId', '')}")
    print(f"URL: {result.get('spreadsheetUrl', '')}")
    print(f"Locale: {props.get('locale', '')}")
    print(f"Timezone: {props.get('timeZone', '')}")
    print(f"\nSheets:")
    for s in result.get("sheets", []):
        sp = s.get("properties", {})
        rows = sp.get("gridProperties", {}).get("rowCount", 0)
        cols = sp.get("gridProperties", {}).get("columnCount", 0)
        print(f"  - {sp.get('title', '')} (ID: {sp.get('sheetId', '')}, {rows}x{cols})")


def cmd_read(args):
    """Read data from a range."""
    url = f"{BASE_URL}/{args.spreadsheet_id}/values/{urllib.parse.quote(args.range)}"
    params = {}
    if args.render:
        params["valueRenderOption"] = args.render

    result = api("GET", url, params=params)
    values = result.get("values", [])

    if args.json:
        fmt_json(result)
        return

    if not values:
        print("(empty range)")
        return

    # Auto-detect if first row is headers
    if args.headers and len(values) > 1:
        headers = values[0]
        rows = [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in values[1:]]
        fmt_table(rows, headers)
    else:
        # Print as grid
        col_widths = []
        for row in values:
            for i, cell in enumerate(row):
                while len(col_widths) <= i:
                    col_widths.append(0)
                col_widths[i] = max(col_widths[i], min(len(str(cell)), 40))

        for row in values:
            cells = []
            for i, cell in enumerate(row):
                w = col_widths[i] if i < len(col_widths) else 10
                cells.append(truncate(str(cell), w).ljust(w))
            print("  ".join(cells))


def cmd_write(args):
    """Write data to a range."""
    # Parse values: accept JSON array or comma-separated rows
    try:
        values = json.loads(args.values)
    except json.JSONDecodeError:
        # Try row;col format: "a,b,c;d,e,f"
        values = [row.split(",") for row in args.values.split(";")]

    url = f"{BASE_URL}/{args.spreadsheet_id}/values/{urllib.parse.quote(args.range)}"
    params = {"valueInputOption": args.input_mode}
    body = {"values": values}

    result = api("PUT", url, body=body, params=params)

    if args.json:
        fmt_json(result)
        return

    print(f"Updated: {result.get('updatedRange', '')}")
    print(f"Cells: {result.get('updatedCells', 0)}, Rows: {result.get('updatedRows', 0)}, Cols: {result.get('updatedColumns', 0)}")


def cmd_append(args):
    """Append rows to a sheet."""
    try:
        values = json.loads(args.values)
    except json.JSONDecodeError:
        values = [row.split(",") for row in args.values.split(";")]

    url = f"{BASE_URL}/{args.spreadsheet_id}/values/{urllib.parse.quote(args.range)}:append"
    params = {"valueInputOption": args.input_mode, "insertDataOption": "INSERT_ROWS"}
    body = {"values": values}

    result = api("POST", url, body=body, params=params)

    if args.json:
        fmt_json(result)
        return

    updates = result.get("updates", {})
    print(f"Appended to: {updates.get('updatedRange', '')}")
    print(f"Rows: {updates.get('updatedRows', 0)}")


def cmd_clear(args):
    """Clear values from a range."""
    url = f"{BASE_URL}/{args.spreadsheet_id}/values/{urllib.parse.quote(args.range)}:clear"
    result = api("POST", url, body={})

    if args.json:
        fmt_json(result)
        return

    print(f"Cleared: {result.get('clearedRange', args.range)}")


def cmd_sheets(args):
    """List sheets in a spreadsheet."""
    url = f"{BASE_URL}/{args.spreadsheet_id}"
    params = {"fields": "sheets.properties"}
    result = api("GET", url, params=params)

    if args.json:
        fmt_json(result)
        return

    rows = []
    for s in result.get("sheets", []):
        sp = s.get("properties", {})
        gp = sp.get("gridProperties", {})
        rows.append({
            "ID": str(sp.get("sheetId", "")),
            "Title": sp.get("title", ""),
            "Rows": str(gp.get("rowCount", "")),
            "Cols": str(gp.get("columnCount", "")),
            "Frozen Rows": str(gp.get("frozenRowCount", 0)),
        })
    fmt_table(rows, ["ID", "Title", "Rows", "Cols", "Frozen Rows"])


def cmd_add_sheet(args):
    """Add a new sheet to a spreadsheet."""
    url = f"{BASE_URL}/{args.spreadsheet_id}:batchUpdate"
    body = {
        "requests": [{"addSheet": {"properties": {"title": args.title}}}]
    }
    result = api("POST", url, body=body)

    if args.json:
        fmt_json(result)
        return

    reply = result.get("replies", [{}])[0]
    props = reply.get("addSheet", {}).get("properties", {})
    print(f"Added sheet: {props.get('title', args.title)} (ID: {props.get('sheetId', '')})")


def cmd_delete_sheet(args):
    """Delete a sheet from a spreadsheet."""
    # First resolve sheet name to ID
    sheet_id = _resolve_sheet_id(args.spreadsheet_id, args.sheet_name)

    url = f"{BASE_URL}/{args.spreadsheet_id}:batchUpdate"
    body = {
        "requests": [{"deleteSheet": {"sheetId": sheet_id}}]
    }
    api("POST", url, body=body)
    print(f"Deleted sheet: {args.sheet_name}")


def cmd_rename_sheet(args):
    """Rename a sheet."""
    sheet_id = _resolve_sheet_id(args.spreadsheet_id, args.sheet_name)

    url = f"{BASE_URL}/{args.spreadsheet_id}:batchUpdate"
    body = {
        "requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "title": args.new_name},
                "fields": "title",
            }
        }]
    }
    api("POST", url, body=body)
    print(f"Renamed: {args.sheet_name} -> {args.new_name}")


def cmd_duplicate_sheet(args):
    """Duplicate a sheet."""
    sheet_id = _resolve_sheet_id(args.spreadsheet_id, args.sheet_name)

    url = f"{BASE_URL}/{args.spreadsheet_id}:batchUpdate"
    request = {"duplicateSheet": {"sourceSheetId": sheet_id}}
    if args.new_name:
        request["duplicateSheet"]["newSheetName"] = args.new_name
    body = {"requests": [request]}

    result = api("POST", url, body=body)

    if args.json:
        fmt_json(result)
        return

    reply = result.get("replies", [{}])[0]
    props = reply.get("duplicateSheet", {}).get("properties", {})
    print(f"Duplicated to: {props.get('title', '')} (ID: {props.get('sheetId', '')})")


def cmd_format(args):
    """Format cells in a range."""
    sheet_id, grid_range = _parse_range_to_grid(args.spreadsheet_id, args.range)

    cell_format = {}
    text_format = {}

    if args.bold is not None:
        text_format["bold"] = args.bold
    if args.italic is not None:
        text_format["italic"] = args.italic
    if args.font_size:
        text_format["fontSize"] = args.font_size
    if args.fg_color:
        text_format["foregroundColorStyle"] = {"rgbColor": _hex_to_rgb(args.fg_color)}
    if args.bg_color:
        cell_format["backgroundColor"] = _hex_to_rgb(args.bg_color)
    if args.align:
        cell_format["horizontalAlignment"] = args.align.upper()
    if args.number_format:
        parts = args.number_format.split(":", 1)
        nf = {"type": parts[0]}
        if len(parts) > 1:
            nf["pattern"] = parts[1]
        cell_format["numberFormat"] = nf
    if text_format:
        cell_format["textFormat"] = text_format

    if not cell_format:
        print("Error: No format options specified", file=sys.stderr)
        sys.exit(1)

    # Build fields mask
    fields = []
    if "backgroundColor" in cell_format:
        fields.append("userEnteredFormat.backgroundColor")
    if "horizontalAlignment" in cell_format:
        fields.append("userEnteredFormat.horizontalAlignment")
    if "numberFormat" in cell_format:
        fields.append("userEnteredFormat.numberFormat")
    if text_format:
        if "bold" in text_format:
            fields.append("userEnteredFormat.textFormat.bold")
        if "italic" in text_format:
            fields.append("userEnteredFormat.textFormat.italic")
        if "fontSize" in text_format:
            fields.append("userEnteredFormat.textFormat.fontSize")
        if "foregroundColorStyle" in text_format:
            fields.append("userEnteredFormat.textFormat.foregroundColorStyle")

    url = f"{BASE_URL}/{args.spreadsheet_id}:batchUpdate"
    body = {
        "requests": [{
            "repeatCell": {
                "range": grid_range,
                "cell": {"userEnteredFormat": cell_format},
                "fields": ",".join(fields),
            }
        }]
    }
    api("POST", url, body=body)

    if args.json:
        fmt_json({"status": "ok", "range": args.range, "format": cell_format})
        return
    print(f"Formatted: {args.range}")


def cmd_freeze(args):
    """Freeze rows and/or columns."""
    sheet_id = _resolve_sheet_id(args.spreadsheet_id, args.sheet_name) if args.sheet_name else 0

    props = {"sheetId": sheet_id}
    field_parts = []
    if args.rows is not None:
        props["gridProperties"] = props.get("gridProperties", {})
        props["gridProperties"]["frozenRowCount"] = args.rows
        field_parts.append("gridProperties.frozenRowCount")
    if args.cols is not None:
        props["gridProperties"] = props.get("gridProperties", {})
        props["gridProperties"]["frozenColumnCount"] = args.cols
        field_parts.append("gridProperties.frozenColumnCount")

    if not field_parts:
        print("Error: Specify --rows and/or --cols", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL}/{args.spreadsheet_id}:batchUpdate"
    body = {
        "requests": [{
            "updateSheetProperties": {
                "properties": props,
                "fields": ",".join(field_parts),
            }
        }]
    }
    api("POST", url, body=body)
    print(f"Frozen: {args.rows or 0} rows, {args.cols or 0} columns")


def cmd_batch_write(args):
    """Write to multiple ranges at once."""
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError:
        print("Error: --data must be valid JSON array of {range, values}", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL}/{args.spreadsheet_id}/values:batchUpdate"
    body = {
        "valueInputOption": args.input_mode,
        "data": data,
    }
    result = api("POST", url, body=body)

    if args.json:
        fmt_json(result)
        return

    print(f"Updated {result.get('totalUpdatedCells', 0)} cells across {result.get('totalUpdatedSheets', 0)} sheets")


def cmd_batch_read(args):
    """Read from multiple ranges at once."""
    url = f"{BASE_URL}/{args.spreadsheet_id}/values:batchGet"
    params = {"ranges": args.ranges}
    if args.render:
        params["valueRenderOption"] = args.render

    result = api("GET", url, params=params)

    if args.json:
        fmt_json(result)
        return

    for vr in result.get("valueRanges", []):
        print(f"\n--- {vr.get('range', '')} ---")
        for row in vr.get("values", []):
            print("  ".join(str(c) for c in row))


# --- Helpers ----------------------------------------------------------------


def _resolve_sheet_id(spreadsheet_id, sheet_name):
    """Resolve a sheet name to its numeric ID."""
    url = f"{BASE_URL}/{spreadsheet_id}"
    params = {"fields": "sheets.properties"}
    result = api("GET", url, params=params)

    for s in result.get("sheets", []):
        props = s.get("properties", {})
        if props.get("title", "").lower() == sheet_name.lower():
            return props["sheetId"]
        # Also match by ID string
        if str(props.get("sheetId", "")) == sheet_name:
            return props["sheetId"]

    print(f"Error: Sheet '{sheet_name}' not found", file=sys.stderr)
    sys.exit(1)


def _col_to_index(col_str):
    """Convert column letters to 0-based index. A=0, B=1, AA=26."""
    result = 0
    for ch in col_str.upper():
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def _parse_a1_range(a1):
    """Parse A1 notation into start/end row/col indices."""
    import re
    # Handle "Sheet1!A1:B2" -> strip sheet name
    if "!" in a1:
        a1 = a1.split("!", 1)[1]

    m = re.match(r"([A-Za-z]*)(\d*):?([A-Za-z]*)(\d*)", a1)
    if not m:
        return {}

    start_col, start_row, end_col, end_row = m.groups()
    result = {}
    if start_col:
        result["startColumnIndex"] = _col_to_index(start_col)
    if start_row:
        result["startRowIndex"] = int(start_row) - 1
    if end_col:
        result["endColumnIndex"] = _col_to_index(end_col) + 1
    if end_row:
        result["endRowIndex"] = int(end_row)
    return result


def _parse_range_to_grid(spreadsheet_id, range_str):
    """Parse a range string into a GridRange dict with sheetId."""
    sheet_name = None
    a1 = range_str
    if "!" in range_str:
        sheet_name, a1 = range_str.split("!", 1)
        # Strip quotes from sheet name
        sheet_name = sheet_name.strip("'\"")

    sheet_id = _resolve_sheet_id(spreadsheet_id, sheet_name) if sheet_name else 0
    grid = _parse_a1_range(a1)
    grid["sheetId"] = sheet_id
    return sheet_id, grid


def _hex_to_rgb(hex_color):
    """Convert hex color to Google API RGB format (0-1 floats)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return {
        "red": int(h[0:2], 16) / 255.0,
        "green": int(h[2:4], 16) / 255.0,
        "blue": int(h[4:6], 16) / 255.0,
    }


# --- CLI Parser -------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(
        prog="gsheets",
        description="Google Sheets CLI - manage spreadsheets via Sheets API v4",
    )
    sub = p.add_subparsers(dest="command", help="Command")

    # list
    ls = sub.add_parser("list", help="List spreadsheets in Drive")
    ls.add_argument("--limit", type=int, default=25, help="Max results (default 25)")
    ls.add_argument("--page-token", help="Pagination token")
    ls.add_argument("--json", action="store_true", help="Raw JSON output")

    # search
    se = sub.add_parser("search", help="Search spreadsheets by name")
    se.add_argument("query", help="Search query")
    se.add_argument("--limit", type=int, default=25)
    se.add_argument("--json", action="store_true")

    # create
    cr = sub.add_parser("create", help="Create a new spreadsheet")
    cr.add_argument("title", help="Spreadsheet title")
    cr.add_argument("--sheets", nargs="+", help="Sheet names to create")
    cr.add_argument("--json", action="store_true")

    # info
    inf = sub.add_parser("info", help="Get spreadsheet metadata")
    inf.add_argument("spreadsheet_id", help="Spreadsheet ID")
    inf.add_argument("--json", action="store_true")

    # read
    rd = sub.add_parser("read", help="Read data from a range")
    rd.add_argument("spreadsheet_id", help="Spreadsheet ID")
    rd.add_argument("range", help="A1 range (e.g. Sheet1!A1:D10)")
    rd.add_argument("--render", choices=["FORMATTED_VALUE", "UNFORMATTED_VALUE", "FORMULA"], help="Value render option")
    rd.add_argument("--headers", action="store_true", default=True, help="Treat first row as headers (default)")
    rd.add_argument("--no-headers", action="store_false", dest="headers")
    rd.add_argument("--json", action="store_true")

    # write
    wr = sub.add_parser("write", help="Write data to a range")
    wr.add_argument("spreadsheet_id", help="Spreadsheet ID")
    wr.add_argument("range", help="A1 range")
    wr.add_argument("values", help='JSON 2D array or semicolon/comma format: "a,b;c,d"')
    wr.add_argument("--input-mode", default="USER_ENTERED", choices=["RAW", "USER_ENTERED"])
    wr.add_argument("--json", action="store_true")

    # append
    ap = sub.add_parser("append", help="Append rows to a sheet")
    ap.add_argument("spreadsheet_id", help="Spreadsheet ID")
    ap.add_argument("range", help="A1 range (e.g. Sheet1!A:D)")
    ap.add_argument("values", help='JSON 2D array or semicolon/comma format')
    ap.add_argument("--input-mode", default="USER_ENTERED", choices=["RAW", "USER_ENTERED"])
    ap.add_argument("--json", action="store_true")

    # clear
    cl = sub.add_parser("clear", help="Clear values from a range")
    cl.add_argument("spreadsheet_id", help="Spreadsheet ID")
    cl.add_argument("range", help="A1 range")
    cl.add_argument("--json", action="store_true")

    # sheets
    sh = sub.add_parser("sheets", help="List sheets in a spreadsheet")
    sh.add_argument("spreadsheet_id", help="Spreadsheet ID")
    sh.add_argument("--json", action="store_true")

    # add-sheet
    ads = sub.add_parser("add-sheet", help="Add a new sheet")
    ads.add_argument("spreadsheet_id", help="Spreadsheet ID")
    ads.add_argument("title", help="Sheet title")
    ads.add_argument("--json", action="store_true")

    # delete-sheet
    ds = sub.add_parser("delete-sheet", help="Delete a sheet")
    ds.add_argument("spreadsheet_id", help="Spreadsheet ID")
    ds.add_argument("sheet_name", help="Sheet name or ID")
    ds.add_argument("--json", action="store_true")

    # rename-sheet
    rs = sub.add_parser("rename-sheet", help="Rename a sheet")
    rs.add_argument("spreadsheet_id", help="Spreadsheet ID")
    rs.add_argument("sheet_name", help="Current sheet name")
    rs.add_argument("new_name", help="New sheet name")
    rs.add_argument("--json", action="store_true")

    # duplicate-sheet
    dups = sub.add_parser("duplicate-sheet", help="Duplicate a sheet")
    dups.add_argument("spreadsheet_id", help="Spreadsheet ID")
    dups.add_argument("sheet_name", help="Sheet to duplicate")
    dups.add_argument("--new-name", help="Name for the copy")
    dups.add_argument("--json", action="store_true")

    # format
    fmt = sub.add_parser("format", help="Format cells")
    fmt.add_argument("spreadsheet_id", help="Spreadsheet ID")
    fmt.add_argument("range", help="A1 range")
    fmt.add_argument("--bold", type=_str_to_bool, help="Bold (true/false)")
    fmt.add_argument("--italic", type=_str_to_bool, help="Italic (true/false)")
    fmt.add_argument("--font-size", type=int, help="Font size")
    fmt.add_argument("--fg-color", help="Text color (hex, e.g. #FF0000)")
    fmt.add_argument("--bg-color", help="Background color (hex)")
    fmt.add_argument("--align", choices=["left", "center", "right"], help="Horizontal alignment")
    fmt.add_argument("--number-format", help="Number format TYPE:pattern (e.g. CURRENCY:$#,##0.00)")
    fmt.add_argument("--json", action="store_true")

    # freeze
    fr = sub.add_parser("freeze", help="Freeze rows/columns")
    fr.add_argument("spreadsheet_id", help="Spreadsheet ID")
    fr.add_argument("--sheet-name", help="Sheet name (default: first sheet)")
    fr.add_argument("--rows", type=int, help="Number of rows to freeze")
    fr.add_argument("--cols", type=int, help="Number of columns to freeze")
    fr.add_argument("--json", action="store_true")

    # batch-write
    bw = sub.add_parser("batch-write", help="Write to multiple ranges")
    bw.add_argument("spreadsheet_id", help="Spreadsheet ID")
    bw.add_argument("data", help='JSON array: [{"range": "A1:B2", "values": [[1,2],[3,4]]}]')
    bw.add_argument("--input-mode", default="USER_ENTERED", choices=["RAW", "USER_ENTERED"])
    bw.add_argument("--json", action="store_true")

    # batch-read
    br = sub.add_parser("batch-read", help="Read from multiple ranges")
    br.add_argument("spreadsheet_id", help="Spreadsheet ID")
    br.add_argument("ranges", nargs="+", help="A1 ranges to read")
    br.add_argument("--render", choices=["FORMATTED_VALUE", "UNFORMATTED_VALUE", "FORMULA"])
    br.add_argument("--json", action="store_true")

    return p


def _str_to_bool(v):
    if v.lower() in ("true", "1", "yes"):
        return True
    if v.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean expected, got '{v}'")


DISPATCH = {
    "list": cmd_list,
    "search": cmd_search,
    "create": cmd_create,
    "info": cmd_info,
    "read": cmd_read,
    "write": cmd_write,
    "append": cmd_append,
    "clear": cmd_clear,
    "sheets": cmd_sheets,
    "add-sheet": cmd_add_sheet,
    "delete-sheet": cmd_delete_sheet,
    "rename-sheet": cmd_rename_sheet,
    "duplicate-sheet": cmd_duplicate_sheet,
    "format": cmd_format,
    "freeze": cmd_freeze,
    "batch-write": cmd_batch_write,
    "batch-read": cmd_batch_read,
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
