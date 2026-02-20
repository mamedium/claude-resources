---
name: gsheets
description: Google Sheets - read, write, format, and manage spreadsheets. Use when the user asks about spreadsheets, Google Sheets, cell data, sheet formatting, or wants to create/edit/read a Google Sheet.
argument-hint: read <spreadsheet-id> Sheet1!A1:D10
allowed-tools: Bash, Read, Edit, Write, Agent
---

# Google Sheets Integration

Read, write, format, and manage Google Spreadsheets via the Sheets API v4.

> Paths below use `{base}` as shorthand for this skill's base directory.

**Input**: `$ARGUMENTS`

---

## Quick Reference

```bash
CMD="python3 {base}/scripts/gsheets.py"
```

### Natural Language Mappings

| User says | Command |
|-----------|---------|
| "list my spreadsheets" | `$CMD list` |
| "find the budget spreadsheet" | `$CMD search "budget"` |
| "create a new spreadsheet called Q1 Report" | `$CMD create "Q1 Report"` |
| "show me the data in this sheet" | `$CMD read <id> Sheet1!A1:Z100` |
| "read cells A1 to D10" | `$CMD read <id> A1:D10` |
| "write these values to the sheet" | `$CMD write <id> A1:B2 '[["a","b"],["c","d"]]'` |
| "add a row to the sheet" | `$CMD append <id> Sheet1!A:Z '[["val1","val2"]]'` |
| "what sheets are in this spreadsheet?" | `$CMD sheets <id>` |
| "add a new tab called Summary" | `$CMD add-sheet <id> Summary` |
| "make the header row bold" | `$CMD format <id> 1:1 --bold true` |
| "freeze the top row" | `$CMD freeze <id> --rows 1` |
| "clear the data" | `$CMD clear <id> Sheet1!A1:Z1000` |
| "get spreadsheet info" | `$CMD info <id>` |
| "show me raw formulas" | `$CMD read <id> A1:D10 --render FORMULA` |

---

## Commands

### Discovery & Management

```bash
# List all spreadsheets (most recently modified first)
$CMD list [--limit 25] [--json]

# Search by name
$CMD search "query" [--limit 25] [--json]

# Create new spreadsheet
$CMD create "Title" [--sheets Tab1 Tab2] [--json]

# Get spreadsheet metadata
$CMD info <spreadsheet-id> [--json]
```

### Reading Data

```bash
# Read a range (first row treated as headers by default)
$CMD read <spreadsheet-id> "Sheet1!A1:D10" [--json]

# Read without header detection
$CMD read <spreadsheet-id> "A1:D10" --no-headers

# Read raw formulas instead of computed values
$CMD read <spreadsheet-id> "A1:D10" --render FORMULA

# Read unformatted values (numbers without currency/percent symbols)
$CMD read <spreadsheet-id> "A1:D10" --render UNFORMATTED_VALUE

# Read multiple ranges at once
$CMD batch-read <spreadsheet-id> "Sheet1!A1:B5" "Sheet2!A1:C3" [--json]
```

### Writing Data

```bash
# Write JSON 2D array
$CMD write <spreadsheet-id> "A1:B2" '[["Name","Score"],["Alice",95]]'

# Write with semicolon/comma shorthand
$CMD write <spreadsheet-id> "A1:B2" "Name,Score;Alice,95"

# Write raw values (no formula parsing)
$CMD write <spreadsheet-id> "A1" '[["=SUM(B:B)"]]' --input-mode RAW

# Append rows to end of sheet
$CMD append <spreadsheet-id> "Sheet1!A:D" '[["new","row","data","here"]]'

# Write to multiple ranges at once
$CMD batch-write <spreadsheet-id> '[{"range":"A1:B1","values":[["x","y"]]},{"range":"A2:B2","values":[["1","2"]]}]'

# Clear a range
$CMD clear <spreadsheet-id> "Sheet1!A1:Z1000"
```

### Sheet (Tab) Management

```bash
# List sheets in a spreadsheet
$CMD sheets <spreadsheet-id> [--json]

# Add a new sheet
$CMD add-sheet <spreadsheet-id> "New Tab Name"

# Delete a sheet
$CMD delete-sheet <spreadsheet-id> "Tab Name"

# Rename a sheet
$CMD rename-sheet <spreadsheet-id> "Old Name" "New Name"

# Duplicate a sheet
$CMD duplicate-sheet <spreadsheet-id> "Source Tab" [--new-name "Copy"]
```

### Formatting

```bash
# Bold a range
$CMD format <spreadsheet-id> "A1:D1" --bold true

# Set background color and alignment
$CMD format <spreadsheet-id> "A1:A10" --bg-color "#FFE0B2" --align center

# Set font size and text color
$CMD format <spreadsheet-id> "B2:B5" --font-size 14 --fg-color "#D32F2F"

# Apply number format (CURRENCY, PERCENT, DATE, NUMBER, etc.)
$CMD format <spreadsheet-id> "C2:C100" --number-format "CURRENCY:$#,##0.00"

# Freeze header row
$CMD freeze <spreadsheet-id> --rows 1

# Freeze first column and header
$CMD freeze <spreadsheet-id> --rows 1 --cols 1 --sheet-name "Data"
```

---

## A1 Range Notation

| Example | Meaning |
|---------|---------|
| `A1:D10` | Specific rectangle |
| `Sheet1!A1:D10` | Range on specific sheet |
| `A:D` | Entire columns A through D |
| `1:5` | Entire rows 1 through 5 |
| `A1` | Single cell |
| `'Sheet Name'!A1:B2` | Sheet with spaces (quote it) |

---

## Common Workflows

### Read a spreadsheet and summarize
1. `$CMD info <id>` to see sheet names
2. `$CMD read <id> "Sheet1!A1:Z100"` to read data
3. Analyze and present findings

### Create a report from data
1. `$CMD create "Report Title" --sheets "Summary" "Data"`
2. `$CMD write <id> "Data!A1" '<data>'`
3. `$CMD format <id> "Data!1:1" --bold true --bg-color "#1565C0" --fg-color "#FFFFFF"`
4. `$CMD freeze <id> --rows 1 --sheet-name "Data"`

### Update existing data
1. `$CMD read <id> "Sheet1!A1:D1"` to check headers
2. `$CMD append <id> "Sheet1!A:D" '<new rows>'`

---

## Global Flags

- `--json` - Raw JSON output (all commands)
- `--limit N` - Number of results for list/search (default 25)
- `--input-mode RAW|USER_ENTERED` - How values are parsed on write (default: USER_ENTERED)
- `--render FORMATTED_VALUE|UNFORMATTED_VALUE|FORMULA` - How values are returned on read

---

## Setup

### 1. Authenticate with Google

The easiest way is to use the google-docs-mcp auth flow:

```bash
npx -y @anthropic-ai/google-docs-mcp auth
```

This creates a token at `~/.config/google-docs-mcp/token.json` that the CLI reuses.

Alternatively, set `GOOGLE_SHEETS_ACCESS_TOKEN` directly (expires in 1h).

### 2. Google Cloud Setup

If setting up from scratch:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Enable **Google Sheets API** and **Google Drive API**
4. Create OAuth 2.0 credentials (Desktop app)
5. Run the auth command above with your credentials:

```bash
GOOGLE_CLIENT_ID="..." GOOGLE_CLIENT_SECRET="..." npx -y @anthropic-ai/google-docs-mcp auth
```

### 3. (Optional) Environment Variables

Add to `~/.claude/settings.json` if using direct token or custom OAuth:
```json
{
  "env": {
    "GOOGLE_CLIENT_ID": "your-client-id",
    "GOOGLE_CLIENT_SECRET": "your-client-secret"
  }
}
```

### 4. Verify

Run `/gsheets list` to confirm authentication works.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `No Google auth token found` | No token.json and no env var | Run `npx -y @anthropic-ai/google-docs-mcp auth` |
| `HTTP 401` | Token expired and refresh failed | Re-run auth command |
| `HTTP 403` | Missing API scope or spreadsheet permission | Check API is enabled; check sharing permissions |
| `HTTP 404` | Invalid spreadsheet ID | Verify the ID from the spreadsheet URL |
| `HTTP 429` | Rate limited | Auto-retries with backoff; reduce request frequency |
| `Sheet 'X' not found` | Typo in sheet name | Run `$CMD sheets <id>` to list available sheets |

---

## Upstream Sync (Auto-Update from Source Repo)

This skill was generated from: **https://github.com/a-bonus/google-docs-mcp** (commit: `b722383b22815c430a259e1932fec51991953df8`)
Source metadata: `{base}/source.json`

### On Every Skill Trigger

**Before executing the user's command**, launch a **background Agent** to check for upstream updates:

1. Read `{base}/source.json` to get the source repo URL and last known commit SHA
2. Launch a background agent (run_in_background: true) to:
   - Shallow-clone or fetch the source repo to `/tmp/skill-sync-gsheets`
   - Compare latest commit with stored SHA
   - If different: analyze the changelog for API surface changes
   - **If good update** (new tools, bug fixes, additive changes): auto-update the script and SKILL.md, update source.json, return summary
   - **If bad update** (breaking changes, removals, regressions): skip changes, return reason
   - **If no changes**: return silently
3. Continue executing the user's command immediately (don't wait)
4. When the background agent completes:
   - If updated: notify user "Updated /gsheets skill from upstream - <summary>"
   - If skipped: notify user "Upstream /gsheets has changes but skipped - <reason>"
   - If no changes: say nothing

## Self-Healing Protocol

When a command fails unexpectedly:
1. **Diagnose** - Read error output and check the script
2. **Propose** - Describe the fix
3. **Await approval** - Ask user before editing
4. **Apply** - Edit `{base}/scripts/gsheets.py`
5. **Verify** - Re-run the failed command
