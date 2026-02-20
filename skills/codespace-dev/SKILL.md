---
name: codespace-dev
description: Start, stop, or sync dev servers on a GitHub Codespace. Handles push/pull, port forwarding, and cleanup. Use when you need to run apps on the codespace for testing.
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# Codespace Dev Skill

Manage dev servers on a GitHub Codespace. Syncs code from local, starts dev servers remotely, and forwards ports for local browser testing.

## Configuration

This skill reads its config from `~/.config/claude-resources/codespace-dev.yaml`.

### On startup, ALWAYS read the config file first:

```bash
cat ~/.config/claude-resources/codespace-dev.yaml
```

If the file does not exist or is empty, run the interactive setup below and then continue.

### Interactive setup (only when config is missing)

1. Run `gh codespace list` to show available codespaces.
2. Ask the user which codespace to use (or auto-select if there's only one).
3. Ask for the repo directory inside the codespace (default: `/workspaces/monorepo`).
4. Ask for the default app and its port (default: `dashboard` on port `3000`).
5. Ask for any additional apps and their ports.
6. Write the config:

```bash
mkdir -p ~/.config/claude-resources
cat > ~/.config/claude-resources/codespace-dev.yaml << 'EOF'
codespace_name: <selected-codespace>
repo_dir: /workspaces/monorepo
default_app: dashboard
apps:
  dashboard: 3000
  admin: 3001
  functions: 3002
EOF
```

### Config format

```yaml
codespace_name: redesigned-space-engine-rpgwv9p74qv2xp9j
repo_dir: /workspaces/monorepo
default_app: dashboard
apps:
  dashboard: 3000
  admin: 3001
  functions: 3002
```

Use these values throughout the skill wherever you see `CODESPACE_NAME`, `REPO_DIR`, `APP`, or `PORT`.

If SSH to the codespace fails (exit 255), the codespace name may be stale. Run `gh codespace list` to get the current name, update the yaml config file, and retry.

## Commands

This skill supports four modes based on user intent. If the user just says `/codespace-dev`, default to **start**.

### Mode: start (default)

Full workflow to get a dev server running on the codespace.

#### Step 1: Determine what to run

Check the config for available apps. Ask the user what app to run if not obvious from context.

If the user already specified (e.g., `/codespace-dev dashboard`), skip asking.

#### Step 2: Kill existing processes

**Local** — kill any leftover SSH/port-forward processes to this codespace:
```bash
pkill -f "gh codespace ssh.*CODESPACE_NAME" 2>/dev/null || true
pkill -f "gh codespace ports forward.*CODESPACE_NAME" 2>/dev/null || true
```

**Codespace** — kill existing dev servers to free ports:
```bash
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'ps aux | grep -E "next-server|turbo.*dev|pnpm.*dev" | grep -v grep | awk "{print \$2}" | xargs -r kill 2>/dev/null; echo ok'
```

**Important:** Do NOT use `pkill -f pnpm` or similar broad patterns inside the codespace — this can kill the SSH session itself. Always use `ps aux | grep ... | xargs kill` targeting specific processes.

#### Step 3: Sync code to codespace

**Auto-commit uncommitted changes** before pushing. Check `git status` — if there are uncommitted changes, stage and commit them automatically with a brief conventional commit message. Do NOT ask the user for confirmation — just commit and move on.

```bash
# Get current branch
BRANCH=$(git branch --show-current)

# Auto-commit any uncommitted changes
git status -s
# If there are changes, stage and commit:
git add -A
git commit -m "wip: sync to codespace"

# Push to remote
git push origin $BRANCH
```

Then pull on the codespace. **Note:** `git pull` via HTTPS may fail due to credential issues. If it fails, use the stdin pipe fallback to copy changed files directly:

```bash
# Try git pull first
gh codespace ssh -c CODESPACE_NAME -- "cd REPO_DIR && git pull origin $BRANCH"

# If git pull fails (credential errors), fall back to piping files via stdin:
cat local/path/to/file.tsx | gh codespace ssh -c CODESPACE_NAME -- "cat > REPO_DIR/path/to/file.tsx"
```

If using `git pull` and it requires `pnpm install`:
```bash
gh codespace ssh -c CODESPACE_NAME -- "cd REPO_DIR && pnpm install --frozen-lockfile"
```

If `pnpm install` fails with lockfile issues, inform the user and suggest running without `--frozen-lockfile`.

#### Step 4: Start dev server

Run the dev server in the background so the SSH session can close:
```bash
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  "cd REPO_DIR && nohup pnpm dev:APP > /tmp/APP-dev.log 2>&1 &"
```

Wait 3-5 seconds, then verify it started:
```bash
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  "ps aux | grep -E 'next-server|turbo.*dev' | grep -v grep | head -5"
```

#### Step 5: Forward port

Forward the codespace port to localhost:
```bash
gh codespace ports forward PORT:PORT -c CODESPACE_NAME &
```

Run this in the background. Tell the user the app is available at `http://localhost:PORT`.

#### Step 6: Confirm

Output a summary:
```
Codespace dev server running:
- App: <app>
- Branch: <branch>
- URL: http://localhost:<port>
- Logs: ssh into codespace and `tail -f /tmp/<app>-dev.log`
```

### Mode: stop

Kill everything — local port forwards, codespace dev servers.

```bash
# Local
pkill -f "gh codespace ssh.*CODESPACE_NAME" 2>/dev/null || true
pkill -f "gh codespace ports forward.*CODESPACE_NAME" 2>/dev/null || true

# Codespace
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'ps aux | grep -E "next-server|turbo.*dev|pnpm.*dev" | grep -v grep | awk "{print \$2}" | xargs -r kill 2>/dev/null; echo ok'
```

Verify nothing is left:
```bash
ps aux | grep -E "gh codespace.*(ssh|ports).*CODESPACE_NAME" | grep -v grep | head -5
```

### Mode: sync

Push local changes and pull on codespace without restarting the server. Useful for hot-reload scenarios (Next.js will pick up changes automatically).

**Auto-commit uncommitted changes** before pushing — same as Step 3 in start mode.

```bash
BRANCH=$(git branch --show-current)

# Auto-commit any uncommitted changes
git status -s
# If there are changes:
git add -A
git commit -m "wip: sync to codespace"

git push origin $BRANCH

# Try git pull first, fall back to stdin pipe if credentials fail
gh codespace ssh -c CODESPACE_NAME -- "cd REPO_DIR && git pull origin $BRANCH"
# Fallback: pipe individual files via stdin (see Step 3 in start mode)
```

### Mode: logs

Tail the dev server logs from the codespace:

```bash
gh codespace ssh -c CODESPACE_NAME -- tail -50 /tmp/APP-dev.log
```

## Troubleshooting

**SSH connection fails (exit 255):**
- The codespace may be stopped. Run `gh codespace list` to check status.
- If stopped, tell the user to start it: `gh codespace start -c CODESPACE_NAME`
- If the codespace name changed, update `~/.config/claude-resources/codespace-dev.yaml` with the new name.

**Port already in use locally:**
- Check what's using it: `lsof -ti:PORT`
- Kill it or suggest an alternate local port: `gh codespace ports forward LOCAL_PORT:REMOTE_PORT`

**pnpm install fails:**
- May need `--no-frozen-lockfile` if lockfile diverged.
- Or run `pnpm install` locally first, commit lockfile, then sync.

## Important Rules

1. **Always read config first** — never hardcode codespace names, ports, or paths
2. **Always push before pulling** — the codespace pulls from remote, not from local filesystem
3. **Never force push** — ask the user first if push is rejected
4. **Background the dev server** — use `nohup ... &` so the SSH session can disconnect
5. **Clean up before starting** — always kill existing processes first to avoid port conflicts
6. **Don't use broad pkill inside codespace** — it kills the SSH connection. Use `ps aux | grep | xargs kill` instead
