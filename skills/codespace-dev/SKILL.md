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
3. Ask for the repo directory inside the codespace (default: `/workspaces/repo`).
4. Ask for the default app and its port (default: `dashboard` on port `3000`).
5. Ask for any additional apps and their ports.
6. Write the config:

```bash
mkdir -p ~/.config/claude-resources
cat > ~/.config/claude-resources/codespace-dev.yaml << 'EOF'
codespace_name: <selected-codespace>
repo_dir: /workspaces/repo
default_app: dashboard
apps:
  dashboard: 3000
  admin: 3001
  functions: 3002
EOF
```

### Config format

```yaml
codespace_name: your-codespace-name-here
repo_dir: /workspaces/repo
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

**Codespace** — kill processes **only for the specific app** being started. Do NOT use broad patterns that kill all dev servers — this will SIGTERM other running apps.

```bash
# For dashboard/admin/forms (Next.js apps):
# Step A: Kill by process name
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'ps aux | grep -E "next-server|turbo.*dev.*-F APP" | grep -v grep | awk "{print \$2}" | xargs -r kill -9 2>/dev/null; echo ok'
# Step B: Kill anything holding the app's port (catches orphaned node child processes)
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'fuser -k PORT/tcp 2>/dev/null; echo ok'
# Step C: Remove the Next.js dev lock file (prevents "is another instance running?" errors)
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'rm -f REPO_DIR/apps/APP/.next/dev/lock; echo ok'

# For background-worker (tsx watch):
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'ps aux | grep -E "tsx.*agent|background-worker" | grep -v grep | awk "{print \$2}" | xargs -r kill -9 2>/dev/null; echo ok'

# For functions (SST/Hono):
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'ps aux | grep -E "sst.*dev|functions" | grep -v grep | awk "{print \$2}" | xargs -r kill -9 2>/dev/null; echo ok'
```

**Important:**
- Do NOT use `pkill -f pnpm` or similar broad patterns inside the codespace — this can kill the SSH session itself and SIGTERM other running apps. Always use `ps aux | grep ... | xargs kill` targeting **app-specific** processes.
- **Always use `kill -9` (SIGKILL)** not just `kill` (SIGTERM) — Next.js/node processes can ignore SIGTERM, leaving orphaned child processes that hold ports and lock files.
- **Always kill by port AND by name** — killing the parent process by name often leaves orphaned node workers still bound to the port. `fuser -k PORT/tcp` catches these.
- **Always remove `.next/dev/lock`** for Next.js apps — even after killing all processes, a stale lock file will prevent the next start.

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

Then pull on the codespace. **Note:** `git pull` via HTTPS may fail due to credential issues. If it fails, use the stdin pipe fallback to copy changed files directly.

**Important:** If the codespace was on a different branch, nuke `.next` after checkout to avoid Turbopack cache compaction loops:
```bash
gh codespace ssh -c CODESPACE_NAME -- "rm -rf REPO_DIR/apps/APP/.next"
```

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

First, check if the app has a root-level script (`pnpm dev:APP`). If not (e.g., `background-worker`), run `pnpm dev` directly from the app directory.

**Prefer `dev:APP:clean` variants** (e.g., `pnpm dev:dashboard:clean`) when available. These clear the Turbopack/Next.js cache before starting, which avoids stale cache issues that cause extremely slow first-page compilations on codespaces. Only fall back to `pnpm dev:APP` if no `:clean` variant exists.

**Important:** `nohup` via SSH loses the working directory (defaults to `$HOME`). Always use `bash -l -c "cd /path && nohup ... & disown"` pattern:

```bash
# If root-level script exists (e.g., dev:dashboard, dev:admin, dev:functions):
gh codespace ssh -c CODESPACE_NAME -- \
  'bash -l -c "cd REPO_DIR && nohup pnpm dev:APP > /tmp/APP-dev.log 2>&1 & disown; echo started"'

# If NO root-level script (e.g., background-worker):
gh codespace ssh -c CODESPACE_NAME -- \
  'bash -l -c "cd REPO_DIR/apps/APP && nohup pnpm dev > /tmp/APP-dev.log 2>&1 & disown; echo started"'
```

Wait 5-10 seconds, then verify it started:
```bash
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  "ps aux | grep -E 'next-server|turbo.*dev|tsx.*agent' | grep -v grep | head -5"
```

**Check logs** to confirm no errors (auth failures, missing env vars, etc.):
```bash
gh codespace ssh -c CODESPACE_NAME -- tail -20 /tmp/APP-dev.log
```

#### Step 5: Forward port

Forward the codespace port to localhost. **Must use `nohup`** — running with just `&` or via the Task tool's `run_in_background` causes the process to exit immediately:

```bash
nohup gh codespace ports forward PORT:PORT -c CODESPACE_NAME > /tmp/codespace-port-forward.log 2>&1 &
```

Verify the port forward is running:
```bash
ps aux | grep "gh codespace ports forward" | grep -v grep
```

Tell the user the app is available at `http://localhost:PORT`.

**Note:** Not all apps need port forwarding. Apps that connect to external services (e.g., a background worker connecting to a third-party API) don't expose a local HTTP server and don't need port forwarding.

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

# Codespace — kill all dev processes, ports, and lock files
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'ps aux | grep -E "next-server|turbo.*dev|pnpm.*dev" | grep -v grep | awk "{print \$2}" | xargs -r kill -9 2>/dev/null; \
   fuser -k 3000/tcp 3001/tcp 3002/tcp 2>/dev/null; \
   rm -f REPO_DIR/apps/dashboard/.next/dev/lock REPO_DIR/apps/admin/.next/dev/lock REPO_DIR/apps/forms/.next/dev/lock; \
   echo ok'
```

Verify nothing is left:
```bash
ps aux | grep -E "gh codespace.*(ssh|ports).*CODESPACE_NAME" | grep -v grep | head -5
```

**If user says "stop all"** — also stop the codespace machine itself after killing processes:
```bash
gh codespace stop -c CODESPACE_NAME
```
Verify with `gh codespace list` that status is `Shutdown` or `ShuttingDown`.

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

**Missing `.env.local` on codespace:**
- Apps that need env vars (e.g., background-worker needs API keys) will fail without `.env.local`.
- Copy from local: `cat /path/to/.env | gh codespace ssh -c CODESPACE_NAME -- "cat > REPO_DIR/.env.local"`
- Or run `pnpm script:run pull-secrets` on the codespace if Infisical is configured there.

**App not in config (`pnpm dev:APP` not found):**
- Not all apps have root-level scripts. Check `package.json` for available `dev:*` scripts.
- For apps without root scripts, run `pnpm dev` directly from the app directory (see Step 4).

**Starting one app kills another:**
- Caused by broad kill patterns in Step 2. Always scope kill commands to the specific app.
- After starting a new app, verify previously running apps are still alive.

**Orphaned processes after restart:**
- Old processes may linger after killing and restarting an app.
- Check with `ps aux | grep APP` and kill stale PIDs manually if needed.

**Next.js "is another instance running?" / port already in use on codespace:**
- This happens when `kill` (SIGTERM) is used instead of `kill -9` (SIGKILL) — Next.js child processes ignore SIGTERM and keep holding the port and lock file.
- Fix: `fuser -k PORT/tcp` to kill anything on the port, then `rm -f REPO_DIR/apps/APP/.next/dev/lock` to clear the lock.
- Prevention: Always use `kill -9` and the three-step cleanup (kill by name, kill by port, remove lock) in Step 2.

**Turbo daemon fails to initialize file watcher:**
- Symptoms: `WARNING: timed out waiting for file watching to become ready after 5s` then `Package change channel closed` and exit code 1
- Caused by: large monorepo on codespace filesystem exceeding inotify limits, stale daemon from previous session, or branch switches
- Fix attempt 1: `npx turbo daemon clean` then retry
- Fix attempt 2: `rm -rf ~/.turbo/daemon` then retry
- Fix attempt 3 (reliable): **Bypass turbo entirely** - run Next.js directly: `cd REPO_DIR/apps/APP && pnpm with-env next dev`. You lose turbo caching but it always works.
- When starting apps, prefer the direct `pnpm with-env next dev` approach on codespaces to avoid this class of issue entirely.

**Turbopack cache corruption (panics with `inner_of_uppers_lost_follower`):**
- Symptoms: Turbopack tokio-runtime-worker threads panic repeatedly, pages stuck compiling, high CPU
- Fix: Delete `.next` entirely: `rm -rf REPO_DIR/apps/APP/.next` then restart. Don't just remove the lock file.
- This happens more often on codespaces after branch switches or stale cache from previous sessions.
- First page load after cache nuke takes 30-60s (cold compile). Subsequent loads are fast.

**Turbopack cache compaction loop after branch switch:**
- Symptoms: Repeated "Finished filesystem cache database compaction" messages in logs, extremely slow or stuck compilation, pages never finish compiling
- Cause: Turbopack cache from the previous branch is incompatible with the new branch's code. The cache keeps trying to compact/reconcile instead of compiling.
- Fix: Same as above - nuke `.next` entirely: `rm -rf REPO_DIR/apps/APP/.next` then restart.
- Prevention: Always nuke `.next` after switching branches on the codespace. Add this to Step 3 (sync) when the branch changes.

**File watching lag warnings on codespace:**
- `WARNING: lagged behind N processing file watching events` and `encountered filewatching error, flushing all globs` are normal on codespaces with large repos. Not actionable - just noise from the filesystem watcher struggling with the repo size.

**pnpm install needed after branch sync:**
- After pulling a new branch, always run `pnpm install --frozen-lockfile` before starting apps. Missing deps cause cryptic module-not-found errors during compile (e.g., `Can't resolve 'html-minifier-terser'`).

**Port forward dies silently:**
- The `nohup gh codespace ports forward` process can die without warning (e.g., after codespace restart or SSH reconnect).
- Always verify port forward is alive before telling the user the app is ready: `ps aux | grep "gh codespace ports forward" | grep -v grep`
- If dead, restart it.

**Duplicate port forward processes cause connection failures:**
- If you restart port forwarding without killing the old process first, two instances compete on the same local port. This causes intermittent connection failures or hangs.
- Always `pkill -f "gh codespace ports forward"` before starting a new one. Never stack multiple forwards on the same port.

## Important Rules

1. **Always read config first** — never hardcode codespace names, ports, or paths
2. **Always push before pulling** — the codespace pulls from remote, not from local filesystem
3. **Never force push** — ask the user first if push is rejected
4. **Use `bash -l -c "cd /path && nohup ... & disown"`** — plain `nohup` via SSH loses the working directory
5. **Use `nohup` for port forwarding locally** — `&` alone or Task tool background mode causes early exit
6. **Scope kill commands to the specific app** — broad patterns kill other running apps
7. **Clean up before starting** — always kill existing processes first to avoid port conflicts
8. **Don't use broad pkill inside codespace** — it kills the SSH connection. Use `ps aux | grep | xargs kill` instead
9. **Verify after starting** — always check logs and process list to confirm the app is healthy, not just that it launched
10. **Handle apps not in config** — fall back to `pnpm dev` from the app directory if no root-level script exists
11. **Always re-forward ports after restarting an app** — restarting a dev server kills the port forward; always re-run `nohup gh codespace ports forward ...` after any restart
