---
name: browser-test
description: Test pages in the browser, take screenshots, verify UI behavior, fill forms, click elements, and run browser automation using a local Playwright runner. Use when asked to "test this page", "take a screenshot", "check the UI", "verify the form works", "open the browser", or any browser-based testing or visual verification. Runs locally without MCP for token efficiency.
argument-hint: <url> [actions...]
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Write
  - Edit
---

# Browser Test

Local Playwright runner for browser automation, testing, and screenshots. Runs directly via Node.js — no MCP protocol overhead. Multiple browser actions execute in a single Bash call for maximum token efficiency.

## Setup (one-time)

```bash
cd ~/.claude/skills/browser-test && npm install
npx playwright install chromium
```

If the Playwright MCP plugin is already installed, browsers are already available — skip the second command.

## Runner: `pw.mjs`

Located at `~/.claude/skills/browser-test/pw.mjs`. Three invocation modes:

### Single command (args)
```bash
node ~/.claude/skills/browser-test/pw.mjs navigate http://localhost:3000
```

### Multi-command (args with `--` separator)
```bash
node ~/.claude/skills/browser-test/pw.mjs navigate http://localhost:3000 -- snapshot -- ss home
```

### Batch (heredoc — most token-efficient)
```bash
node ~/.claude/skills/browser-test/pw.mjs <<'CMDS'
navigate http://localhost:3000
wait 1000
snapshot
ss home
CMDS
```

### Environment / flags

| Flag/Env | Effect |
|----------|--------|
| `--headed` | Show browser window |
| `PW_HEADED=1` | Same as `--headed` |
| `PW_SLOW_MO=100` | Slow down actions by 100ms |

## Commands

### Navigation
| Command | Example | Description |
|---------|---------|-------------|
| `navigate <url>` | `navigate http://localhost:3000` | Go to URL |
| `back` | `back` | Go back in history |
| `forward` | `forward` | Go forward |
| `reload` | `reload` | Reload page |
| `title` | `title` | Print page title |
| `url` | `url` | Print current URL |

### Seeing the page
| Command | Example | Description |
|---------|---------|-------------|
| `snapshot` / `snap` | `snapshot` | Accessibility tree (text, token-efficient) |
| `screenshot` / `ss` | `ss login-page` | Screenshot to `.playwright-mcp/` |
| `ss <name> --full` | `ss full-page --full` | Full-page screenshot |

### Interaction
| Command | Example | Description |
|---------|---------|-------------|
| `click <selector>` | `click "text=Login"` | Click element |
| `dblclick <selector>` | `dblclick "#item"` | Double-click |
| `fill <selector> <value>` | `fill "#email" test@test.com` | Clear + fill input |
| `type <selector> <value>` | `type "#search" hello` | Type character by character |
| `select <selector> <value>` | `select "#country" US` | Select dropdown option |
| `press <key>` | `press Enter` | Press keyboard key |
| `hover <selector>` | `hover "text=Menu"` | Hover over element |
| `wait <text or ms>` | `wait 2000` / `wait "Welcome"` | Wait for timeout or text |

### Inspection
| Command | Example | Description |
|---------|---------|-------------|
| `eval <js>` | `eval document.title` | Run JavaScript, print result |
| `console` | `console` | Print captured console messages |
| `network` | `network` | Print network requests |
| `resize <w> <h>` | `resize 375 812` | Resize viewport |

### Selectors

Use Playwright selector syntax:

| Type | Example |
|------|---------|
| Text | `"text=Login"` |
| CSS | `"#email"`, `".btn-primary"` |
| Role | `'role=button[name="Submit"]'` |
| Test ID | `"data-testid=login-btn"` |
| Placeholder | `"[placeholder='Search...']"` |
| XPath | `"xpath=//button[@type='submit']"` |

## Workflows

### Quick Screenshot

One Bash call = navigate + wait + screenshot:

```bash
node ~/.claude/skills/browser-test/pw.mjs <<'CMDS'
navigate http://localhost:3000
wait 1000
ss dashboard-home
CMDS
```

Then read the screenshot:
```
Read .playwright-mcp/dashboard-home.png
```

### Responsive Testing

One Bash call = navigate + screenshot at every breakpoint:

```bash
node ~/.claude/skills/browser-test/pw.mjs <<'CMDS'
navigate http://localhost:3000/settings
wait 1000
# Mobile
resize 375 812
wait 500
ss settings-mobile
# Tablet
resize 768 1024
wait 500
ss settings-tablet
# Desktop
resize 1440 900
wait 500
ss settings-desktop
CMDS
```

### Form Testing

One Bash call = open form + fill + submit + verify:

```bash
node ~/.claude/skills/browser-test/pw.mjs <<'CMDS'
navigate http://localhost:3000/login
wait 1000
snapshot
fill "#email" test@example.com
fill "#password" password123
click "text=Sign in"
wait Welcome
snapshot
ss after-login
CMDS
```

### Multi-Step Flow

```bash
node ~/.claude/skills/browser-test/pw.mjs <<'CMDS'
navigate http://localhost:3000
wait 1000
click "text=Leads"
wait 1000
snapshot
ss leads-list
click "text=Add Lead"
wait 500
fill "#name" "John Doe"
fill "#email" "john@test.com"
click "text=Save"
wait "successfully"
snapshot
ss lead-created
CMDS
```

### Console & Network Debugging

```bash
node ~/.claude/skills/browser-test/pw.mjs <<'CMDS'
navigate http://localhost:3000/dashboard
wait 2000
console
network
CMDS
```

### JavaScript Evaluation

```bash
node ~/.claude/skills/browser-test/pw.mjs eval "document.querySelectorAll('.error').length"
node ~/.claude/skills/browser-test/pw.mjs eval "JSON.stringify(window.__NEXT_DATA__.props)"
```

## Token Efficiency

This approach saves tokens compared to MCP because:

| Approach | Tool calls | Round trips |
|----------|-----------|-------------|
| MCP (navigate + snapshot + screenshot) | 3 tool calls | 3 round trips |
| pw.mjs batch (same 3 actions) | 1 Bash call | 1 round trip |
| MCP (login flow: 8 steps) | 8+ tool calls | 8+ round trips |
| pw.mjs batch (same flow) | 1 Bash call | 1 round trip |

Each MCP tool call costs tokens for: the tool call message, the protocol wrapping, the response message, and Claude processing the response. Batching eliminates all of that overhead.

## Guidelines

### Snapshot for understanding, screenshot for visual

- Use `snapshot` (accessibility tree) to understand page structure and derive selectors. This is text-only and very token-efficient.
- Use `screenshot` for visual verification — then read the image with the Read tool.
- Prefer snapshot over screenshot when you just need to know what's on the page.

### Batch everything

Always prefer the heredoc batch mode. Never run multiple single-command Bash calls when you can batch them.

### Dev server check

Before testing local pages, verify the dev server is running:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "Dev server not running"
```

### Error handling

The runner continues on errors (prints `[ERROR]` and moves to next command). Check the output for errors after the batch completes. If a click fails, try:
1. A different selector (`text=` vs CSS vs role)
2. Adding a `wait` before the action
3. Taking a snapshot to see current page state

### Screenshot storage

All screenshots save to `.playwright-mcp/` in the project root. Use descriptive names:
- `{page}-{state}.png` — `login-form-empty.png`
- `{page}-{viewport}.png` — `settings-mobile.png`
- `{page}-{step}.png` — `checkout-step2.png`
