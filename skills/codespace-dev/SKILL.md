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

**Prefer `dev:APP:clean` variants** (e.g., `pnpm dev:dashboard:clean`) when available. These `rm -rf` the app's `.next` before starting, which avoids two recurring problems on codespaces:

1. **Stale Turbopack cache** causing extremely slow first-page compilations and repeated `Finished filesystem cache database compaction` log spam.
2. **`.next` corruption** from killed/orphaned dev servers, branch switches, or panics — symptoms range from "is another instance running?" lock errors to silent module-resolution failures.

Empirically, plain `next dev` runs on a codespace get into broken `.next` states often enough that `:clean` is worth the ~30-60s cold compile every start. Only fall back to `pnpm dev:APP` (no `:clean`) if no `:clean` variant exists, or to direct `pnpm with-env next dev` if turbo daemon itself is failing to initialise (see troubleshooting below).

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

#### Step 5b: Start port-forward watchdog (mandatory when forwarding)

The `gh codespace ports forward` tunnel dies silently — process disappears with no exit code, no log line, even when the codespace stays `Available`. Without a watchdog, the user hits "site unreachable" mid-test and you have to restart the forward manually. Always start the watchdog after any port forward.

Write the watchdog script once (idempotent — overwrites are fine):

```bash
cat > /tmp/codespace-port-watchdog.sh << 'WATCHDOG_EOF'
#!/usr/bin/env bash
# Watchdog: keeps `gh codespace ports forward` alive.
set -u
CODESPACE="${1:-}"
PORT="${2:-3000}"
LOG="/tmp/codespace-port-watchdog.log"
INTERVAL="${INTERVAL:-15}"

if [[ -z "$CODESPACE" ]]; then
  echo "usage: $0 <codespace-name> [port]" >&2
  exit 1
fi

echo "$(date '+%H:%M:%S') watchdog started for $CODESPACE port $PORT (interval ${INTERVAL}s)" >> "$LOG"

while true; do
  CODE=$(curl -s -m 3 -o /dev/null -w "%{http_code}" "http://localhost:${PORT}" || echo "000")
  if [[ ! "$CODE" =~ ^[23] ]]; then
    echo "$(date '+%H:%M:%S') localhost:${PORT} returned '$CODE' — restarting forward" >> "$LOG"
    pkill -f "gh codespace ports forward ${PORT}:${PORT}.*${CODESPACE}" 2>/dev/null
    sleep 1
    nohup gh codespace ports forward "${PORT}:${PORT}" -c "$CODESPACE" \
      > /tmp/codespace-port-forward.log 2>&1 &
  fi
  sleep "$INTERVAL"
done
WATCHDOG_EOF
chmod +x /tmp/codespace-port-watchdog.sh
```

Kill any prior watchdog for this codespace+port, then start a fresh one:

```bash
pkill -f "codespace-port-watchdog.sh.*CODESPACE_NAME.*PORT" 2>/dev/null
nohup /tmp/codespace-port-watchdog.sh CODESPACE_NAME PORT > /dev/null 2>&1 &
sleep 2 && tail -3 /tmp/codespace-port-watchdog.log
```

The watchdog probes `http://localhost:PORT` every 15s. If the response is non-2xx/3xx (or the curl times out), it kills the dead forward and starts a fresh one. Restarts are logged to `/tmp/codespace-port-watchdog.log`.

**Multiple ports:** start one watchdog per forwarded port (each watches its own `localhost:PORT`).

#### Step 6: Confirm

Output a summary:
```
Codespace dev server running:
- App: <app>
- Branch: <branch>
- URL: http://localhost:<port>
- Logs: ssh into codespace and `tail -f /tmp/<app>-dev.log`
- Port-forward watchdog: tail -f /tmp/codespace-port-watchdog.log
```

### Mode: stop

Kill everything — local port forwards, codespace dev servers.

```bash
# Local
pkill -f "codespace-port-watchdog.sh.*CODESPACE_NAME" 2>/dev/null || true
pkill -f "gh codespace ssh.*CODESPACE_NAME" 2>/dev/null || true
pkill -f "gh codespace ports forward.*CODESPACE_NAME" 2>/dev/null || true

# Codespace — kill all dev processes, ports, and lock files
gh codespace ssh -c CODESPACE_NAME -- bash -c \
  'ps aux | grep -E "next-server|turbo.*dev|pnpm.*dev" | grep -v grep | awk "{print \$2}" | xargs -r kill -9 2>/dev/null; \
   fuser -k 3000/tcp 3001/tcp 3002/tcp 2>/dev/null; \
   rm -f REPO_DIR/apps/*/.next/dev/lock; \
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
- Or run your team's secret-pull script on the codespace if a secrets manager (e.g. Infisical) is configured there. <!-- CUSTOMIZE: your equivalent of `pnpm run pull-secrets`. -->

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
- Fix attempt 3 (reliable): **Bypass turbo entirely** - run Next.js directly: `cd REPO_DIR/apps/APP && pnpm with-env next dev`. You lose turbo caching and internal-package auto-rebuild, but it always works.
- **Default is `pnpm dev:APP:clean` through turbo** — the daemon issue is intermittent, and the `.next` corruption you get from running plain `next dev` long-term is worse than the occasional daemon hiccup. Fall back to direct `pnpm with-env next dev` only when turbo daemon is actively broken on the current session.

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

**Escaping the slow codespace filesystem for `.next/dev` (experimental):**
- Symptoms: Repeated `Finished filesystem cache database compaction in 11-29s` lines in the dashboard dev log, making first-render and HMR painful. The slow-fs cost lands hardest on Turbopack's `.next/dev` cache directory.
- The temptation: symlink `.next/dev` into `/tmp` (tmpfs) — much faster than the overlay fs the codespace mounts at `/workspaces`.
- **DON'T use `ln -s` for this.** `ln -sfn /tmp/next-dev .next/dev` boots, but Sentry's instrumentation hook crashes at module evaluation: `Cannot find module 'require-in-the-middle-...'` with stack pointing at `/tmp/next-dev/server/chunks/..._sentry_node-core...`. Root cause: Node's `Module._resolveFilename` + Sentry's `require-in-the-middle` patching don't follow symlinks correctly when the instrumented module sits behind one. Reverting the symlink restores the baseline. **Also don't combine the symlink with flipping `turbopackFileSystemCacheForDev: false` in `next.config.ts` — both halves were originally flipped together; we now know the symlink alone is the broken half, but neither has been validated as a perf win yet.**
- **Bind-mount works** (verified empirically on a live codespace). Node can't tell a bind-mount from a real dir, so Sentry's resolver is happy:
  ```bash
  cd REPO_DIR/apps/APP
  [ -e .next/dev ] && [ ! -L .next/dev ] && mv .next/dev .next/dev.bak
  mkdir -p /tmp/next-dev .next/dev
  sudo mount --bind /tmp/next-dev .next/dev
  ```
  Verify: `mount | grep next/dev` shows the bind line, then `pnpm with-env next dev` boots in ~300ms with no Sentry crash. Keep `turbopackFileSystemCacheForDev: true` (default) — don't touch it.
- Caveats before wiring this in permanently:
  - Bind-mount needs `sudo` and doesn't survive a codespace rebuild — would need a `postStartCommand` hook in `.devcontainer/devcontainer.json` to persist.
  - **Perf win is unverified.** Bind-mount stops the Sentry crash, but we haven't measured cold/warm request time vs baseline or counted the `filesystem cache database compaction` lines after 5 min of activity. Run those measurements before recommending this to anyone.
- Revert: `sudo umount .next/dev && rmdir .next/dev && mv .next/dev.bak .next/dev`.

**Dashboard / dev server feels sluggish after long uptime (kill-and-restart heuristic):**
- Symptoms: HMR is slow, first-page renders take 10+ seconds, frequent `Finished filesystem cache database compaction` lines in the log, but the codespace itself is healthy (RAM free, low CPU load, `.next/dev` looks normal — not a symlink, not a mount). No obvious config or branch change explains it.
- Cause: long-running `next-server` drifts. In-memory caches, Turbopack workers, tokio runtime state, and stale daemon connections accumulate over hours of HMR cycles, especially across branch switches or many route changes.
- **Default fix when in doubt: kill the dev server(s) and restart.** Don't burn time diagnosing further — kill-and-restart often beats deep investigation here, and it's reversible / cheap.
  ```bash
  # Kill everything dev-related on the codespace, then start the app you actually need
  gh codespace ssh -c CODESPACE_NAME -- bash -c \
    'ps aux | grep -E "next-server|turbo.*dev|tsx.*agent|pnpm.*dev" | grep -v grep | awk "{print \$2}" | xargs -r kill -9 2>/dev/null; \
     fuser -k 3000/tcp 3001/tcp 3002/tcp 2>/dev/null; \
     rm -f REPO_DIR/apps/*/.next/dev/lock; \
     echo cleaned'
  # Then start fresh — see "Step 4: Start dev server" above
  ```
- Evidence: observed in practice during a QA session - a dev server that had been running ~6 hours felt sluggish to the user testing on a real device. Killing and restarting restored fast renders and dropped compaction-line frequency to a handful of lines per hour. No config change applied - the restart alone was the fix.
- Apply this BEFORE assuming you need a deeper tweak (bind-mount escape, daemon clean, etc.). If the slowness persists after a fresh restart, then dig in.

**File watching lag warnings on codespace:**
- `WARNING: lagged behind N processing file watching events` and `encountered filewatching error, flushing all globs` are normal on codespaces with large repos. Not actionable - just noise from the filesystem watcher struggling with the repo size.

**pnpm install needed after branch sync:**
- After pulling a new branch, always run `pnpm install --frozen-lockfile` before starting apps. Missing deps cause cryptic module-not-found errors during compile (e.g., `Can't resolve 'html-minifier-terser'`).

**Port forward dies silently:**
- The `nohup gh codespace ports forward` process can die without warning (e.g., after codespace restart or SSH reconnect, or unprompted while the codespace stays `Available`).
- Even when the OS process is alive, the tunnel itself can be dead — `curl http://localhost:PORT` returning empty is the canonical symptom.
- **Always start the watchdog (Step 5b)** — it probes `localhost:PORT` and auto-restarts the forward when it dies. Without the watchdog, the user will hit "site unreachable" mid-test.
- If the user reports the dashboard is unreachable: `tail /tmp/codespace-port-watchdog.log` to see if the watchdog is running and how many restarts have occurred. If the watchdog is dead, restart it (Step 5b).

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
12. **Always start the port-forward watchdog (Step 5b) after any forward** — the tunnel dies silently with no log line; the watchdog is the only thing that keeps the user's session usable across the typical 30+ minute idle/reconnect events
13. **Always kill the watchdog in stop mode** — leftover watchdogs will keep resurrecting forwards after the user thought they shut everything down
