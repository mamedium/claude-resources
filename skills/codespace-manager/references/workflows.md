# Codespace Workflows - Quick Reference

## Quick Start: Create a Codespace

```bash
# 1. Create codespace
gh codespace create -R owner/repo -b main -m standardLinux32gb --display-name "my-feature"
```

## Quick Start: Start an Existing Codespace

```bash
# 1. Find your codespace
gh codespace list --json name,state,repository,branch -q '.[] | "\(.name)\t\(.state)\t\(.repository)\t\(.branch)"'

# 2. Start a stopped codespace (via REST API — no built-in start subcommand)
gh api -X POST /user/codespaces/CODESPACE_NAME/start

# 3. Connect later when ready
gh codespace ssh -c CODESPACE_NAME
```

## Development Session with Port Forwarding

```bash
# 1. Start codespace if stopped
gh api -X POST /user/codespaces/CODESPACE_NAME/start

# 2. Connect via SSH
gh codespace ssh -c CODESPACE_NAME

# 3. In another terminal, forward ports
gh codespace ports forward 3000:3000 8080:8080 -c CODESPACE_NAME

# 4. Access at localhost:3000 and localhost:8080
```

## Cleanup Workflow

```bash
# Stop all running codespaces
gh codespace list --json name,state -q '.[] | select(.state=="Available") | .name' | xargs -I{} gh codespace stop -c {}

# Delete old codespaces (interactive, one by one)
gh codespace delete -c CODESPACE_NAME
```

## JSON Output Fields

Available fields for `--json` flag on `list` and `view`:

- `name` - Codespace identifier
- `state` - Available, Shutdown, Starting, etc.
- `repository` - Owner/repo
- `branch` - Git branch
- `machineDisplayName` - Machine type description
- `createdAt` - Creation timestamp
- `lastUsedAt` - Last activity timestamp
- `retentionExpiresAt` - When auto-delete kicks in
- `owner` - GitHub username
- `gitStatus` - Commit info and dirty state

## Machine Type Selection

To see available machine types for a repo:
```bash
gh api repos/OWNER/REPO/codespaces/machines --jq '.machines[] | "\(.name)\t\(.display_name)\t\(.cpus) cores\t\(.memory_in_bytes/1073741824)GB RAM"'
```

## Troubleshooting

### "gh: command not found"
Install GitHub CLI: https://cli.github.com/

### "not logged in"
```bash
gh auth login
gh auth refresh -s codespace
```

### Codespace won't start
```bash
# Check logs
gh codespace logs -c CODESPACE_NAME

# Try rebuilding
gh codespace rebuild -c CODESPACE_NAME --full
```

### Port forwarding not working
- Ensure codespace is in "Available" (running) state
- Check if the service is actually running inside the codespace
- Try a different local port if the default is in use
