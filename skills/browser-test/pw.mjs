#!/usr/bin/env node

// pw.mjs — Lightweight Playwright runner for Claude Code
//
// Single:  node pw.mjs navigate http://localhost:3000
// Multi:   node pw.mjs navigate URL -- snapshot -- ss home
// Batch:   node pw.mjs <<'CMDS'
//            navigate http://localhost:3000
//            snapshot
//            ss home
//          CMDS

import { readFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  console.error('playwright not installed. Run:\n  cd .claude/skills/browser-test && npm install');
  process.exit(1);
}

const SS_DIR = join(process.cwd(), '.playwright-mcp');
const rawArgs = process.argv.slice(2);

// Extract global flags
const headed = rawArgs.includes('--headed') || process.env.PW_HEADED === '1';
const args = rawArgs.filter(a => a !== '--headed');

// --- Command parsing ---

function getCommands() {
  if (args.length > 0) {
    const cmds = [];
    let cur = [];
    for (const a of args) {
      if (a === '--') {
        if (cur.length) cmds.push(cur);
        cur = [];
      } else {
        cur.push(a);
      }
    }
    if (cur.length) cmds.push(cur);
    return cmds;
  }
  // Batch: read from stdin (heredoc or pipe)
  const input = readFileSync(0, 'utf-8');
  return input
    .split('\n')
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('#'))
    .map(tokenize);
}

function tokenize(line) {
  const tokens = [];
  let cur = '', q = null;
  for (const c of line) {
    if (q) {
      if (c === q) q = null;
      else cur += c;
    } else if (c === '"' || c === "'") {
      q = c;
    } else if (c === ' ') {
      if (cur) { tokens.push(cur); cur = ''; }
    } else {
      cur += c;
    }
  }
  if (cur) tokens.push(cur);
  return tokens;
}

// No custom tree printer needed — page.locator(':root').ariaSnapshot() returns formatted text

// --- Command executor ---

async function exec(page, [action, ...rest], consoleMsgs) {
  switch (action) {
    case 'navigate':
    case 'goto': {
      await page.goto(rest[0], { waitUntil: 'domcontentloaded', timeout: 30000 });
      console.log(`[navigate] ${rest[0]} -> "${await page.title()}"`);
      break;
    }

    case 'snapshot':
    case 'snap': {
      console.log('[snapshot]');
      const snap = await page.locator(':root').ariaSnapshot();
      console.log(snap || '(empty)');
      break;
    }

    case 'screenshot':
    case 'ss': {
      const name = rest[0] || `ss-${Date.now()}`;
      const file = name.endsWith('.png') ? name : `${name}.png`;
      mkdirSync(SS_DIR, { recursive: true });
      const p = join(SS_DIR, file);
      const full = rest.includes('--full');
      await page.screenshot({ path: p, fullPage: full });
      console.log(`[screenshot] ${p}`);
      break;
    }

    case 'click': {
      await page.click(rest[0], { timeout: 5000 });
      console.log(`[click] ${rest[0]}`);
      break;
    }

    case 'dblclick': {
      await page.dblclick(rest[0], { timeout: 5000 });
      console.log(`[dblclick] ${rest[0]}`);
      break;
    }

    case 'fill': {
      const val = rest.slice(1).join(' ');
      await page.fill(rest[0], val, { timeout: 5000 });
      console.log(`[fill] ${rest[0]} = "${val}"`);
      break;
    }

    case 'type': {
      const val = rest.slice(1).join(' ');
      await page.locator(rest[0]).pressSequentially(val, { delay: 30 });
      console.log(`[type] ${rest[0]} "${val}"`);
      break;
    }

    case 'select': {
      await page.selectOption(rest[0], rest[1], { timeout: 5000 });
      console.log(`[select] ${rest[0]} = "${rest[1]}"`);
      break;
    }

    case 'press': {
      await page.keyboard.press(rest[0]);
      console.log(`[press] ${rest[0]}`);
      break;
    }

    case 'hover': {
      await page.hover(rest[0], { timeout: 5000 });
      console.log(`[hover] ${rest[0]}`);
      break;
    }

    case 'wait': {
      if (/^\d+$/.test(rest[0])) {
        await page.waitForTimeout(parseInt(rest[0]));
        console.log(`[wait] ${rest[0]}ms`);
      } else {
        const text = rest.join(' ');
        const waitTimeout = parseInt(process.env.PW_WAIT_TIMEOUT || '10000');
        await page.getByText(text, { exact: false }).first().waitFor({ timeout: waitTimeout });
        console.log(`[wait] found "${text}"`);
      }
      break;
    }

    case 'eval': {
      console.log('[eval]');
      const result = await page.evaluate(rest.join(' '));
      console.log(typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result));
      break;
    }

    case 'console': {
      console.log('[console]');
      if (!consoleMsgs.length) console.log('(no messages)');
      else consoleMsgs.forEach(m => console.log(`  [${m.type}] ${m.text}`));
      break;
    }

    case 'network': {
      console.log('[network]');
      const entries = await page.evaluate(() =>
        performance.getEntriesByType('resource').map(e => ({
          name: e.name,
          type: e.initiatorType,
          duration: Math.round(e.duration),
          size: e.transferSize,
        }))
      );
      if (!entries.length) console.log('(no requests)');
      else entries.forEach(e => console.log(`  ${e.type} ${e.name} ${e.duration}ms ${e.size}b`));
      break;
    }

    case 'resize': {
      await page.setViewportSize({ width: +rest[0], height: +rest[1] });
      console.log(`[resize] ${rest[0]}x${rest[1]}`);
      break;
    }

    case 'back': {
      await page.goBack({ waitUntil: 'domcontentloaded' });
      console.log(`[back] ${page.url()}`);
      break;
    }

    case 'forward': {
      await page.goForward({ waitUntil: 'domcontentloaded' });
      console.log(`[forward] ${page.url()}`);
      break;
    }

    case 'reload': {
      await page.reload({ waitUntil: 'domcontentloaded' });
      console.log(`[reload] ${page.url()}`);
      break;
    }

    case 'title': {
      console.log(`[title] ${await page.title()}`);
      break;
    }

    case 'url': {
      console.log(`[url] ${page.url()}`);
      break;
    }

    default:
      console.log(`[unknown] ${action}`);
  }
}

// --- Main ---

const userDataDir = process.env.PW_USER_DATA_DIR;
let browser, context, page;

const channel = process.env.PW_CHANNEL; // e.g. 'chrome' to use real Chrome

if (userDataDir) {
  mkdirSync(userDataDir, { recursive: true });
  context = await chromium.launchPersistentContext(userDataDir, {
    headless: !headed,
    slowMo: parseInt(process.env.PW_SLOW_MO || '0'),
    viewport: { width: 1280, height: 800 },
    ...(channel ? { channel } : {}),
  });
  page = context.pages()[0] || await context.newPage();
} else {
  browser = await chromium.launch({
    headless: !headed,
    slowMo: parseInt(process.env.PW_SLOW_MO || '0'),
    ...(channel ? { channel } : {}),
  });
  page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
}

const consoleMsgs = [];
page.on('console', msg => consoleMsgs.push({ type: msg.type(), text: msg.text() }));

try {
  for (const cmd of getCommands()) {
    try {
      await exec(page, cmd, consoleMsgs);
    } catch (e) {
      console.log(`[ERROR] ${cmd[0]}: ${e.message}`);
    }
  }
} finally {
  await (browser || context).close();
}
