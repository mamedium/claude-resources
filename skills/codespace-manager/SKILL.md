---
name: codespace-manager
description: Manage GitHub Codespaces remotely - create, start, list, forward ports, stop, delete, view, and rebuild codespaces using the gh CLI. Use this skill when the user wants to work with GitHub Codespaces from the terminal.
license: MIT
metadata:
  author: dodycode
  version: "1.0.0"
user_invocable: true
---

# GitHub Codespaces Manager

Manage GitHub Codespaces remotely via `gh codespace` (alias: `gh cs`) CLI commands.

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- Run `gh auth status` to verify authentication
- Codespaces must be enabled for the target repository

## When Invoked

When the user invokes `/codespace-manager`, follow this workflow:

1. **Verify prerequisites** - Check `gh auth status` silently
2. **Ask what they want to do** - Use AskUserQuestion with the operations below
3. **Execute** - Run the appropriate `gh` commands
4. **Report results** - Show the user what happened and next steps

## Operations

### Create a New Codespace

Create and optionally connect to a new codespace.

```bash
gh codespace create \
  -R OWNER/REPO \
  -b BRANCH \
  -m MACHINE_TYPE \
  --display-name "NAME" \
  --idle-timeout DURATION \
  --retention-period DURATION \
  -l LOCATION
```

**Workflow:**
1. Ask for the repository (`-R owner/repo`) - REQUIRED
2. Ask for branch (`-b`) - default: repo's default branch
3. List available machine types: `gh codespace create -R OWNER/REPO --show-machine-types` (non-interactive, just to display options)
4. Ask for machine type (`-m`) if user wants to choose
5. Optionally ask for display name, idle timeout, retention period
6. Create the codespace and capture the codespace name from output
7. Ask if they want to connect immediately via SSH

**Machine types** (common):
- `basicLinux32gb` - 2-core, 8GB RAM, 32GB storage
- `standardLinux32gb` - 4-core, 16GB RAM, 32GB storage
- `premiumLinux` - 8-core, 32GB RAM, 64GB storage
- `largePremiumLinux` - 16-core, 64GB RAM, 128GB storage

**Locations**: EastUs, SouthEastAsia, WestEurope, WestUs2

### Start a Codespace

Start a stopped codespace to make it active and available for later SSH connections. This uses the GitHub REST API since `gh codespace` has no built-in `start` subcommand.

```bash
# List available codespaces first
gh codespace list

# Start a stopped codespace via REST API
gh api -X POST /user/codespaces/CODESPACE_NAME/start
```

**Workflow:**
1. Run `gh codespace list --json name,state,repository,branch,machineDisplayName,lastUsedAt` to show available codespaces
2. Filter for stopped codespaces (state: `Shutdown`)
3. Ask user which codespace to start
4. Start it via `gh api -X POST /user/codespaces/{codespace_name}/start`
5. Confirm the codespace is now starting/available
6. Provide the user with a ready-to-use SSH command using the actual codespace name:
   ```
   gh codespace ssh -c <actual-codespace-name>
   ```

### List Codespaces

```bash
# List all codespaces
gh codespace list

# List with JSON output for parsing
gh codespace list --json name,state,repository,branch,machineDisplayName,lastUsedAt
```

Show results in a readable table format with: name, repo, branch, state, machine type, and last used.

### Forward Ports

Forward ports from a codespace to the local machine.

```bash
# Forward a single port
gh codespace ports forward REMOTE_PORT:LOCAL_PORT -c CODESPACE_NAME

# Forward multiple ports
gh codespace ports forward 8080:8080 3000:3000 -c CODESPACE_NAME

# List current port forwarding
gh codespace ports -c CODESPACE_NAME

# Change port visibility
gh codespace ports visibility REMOTE_PORT:public -c CODESPACE_NAME
```

**Workflow:**
1. List codespaces if no codespace specified
2. Ask which ports to forward (remote:local format)
3. Execute port forwarding (runs in background)
4. Inform user the forwarding is active and how to stop it

### Stop a Codespace

Gracefully stop a running codespace (preserves state, stops billing for compute).

```bash
gh codespace stop -c CODESPACE_NAME
```

**Workflow:**
1. List running codespaces: `gh codespace list --json name,state,repository | jq '.[] | select(.state=="Available")'`
2. Ask which to stop
3. Stop it
4. Confirm stopped

### Delete a Codespace

Permanently delete a codespace and all its data.

```bash
gh codespace delete -c CODESPACE_NAME

# Delete with confirmation skip
gh codespace delete -c CODESPACE_NAME --force
```

**Workflow:**
1. List codespaces
2. Ask which to delete
3. **ALWAYS confirm with the user before deleting** - this is destructive and irreversible
4. Delete it
5. Confirm deletion

### View Codespace Details

```bash
gh codespace view -c CODESPACE_NAME

# JSON output for full details
gh codespace view -c CODESPACE_NAME --json name,state,repository,branch,machineDisplayName,createdAt,lastUsedAt,retentionExpiresAt
```

### Rebuild a Codespace

Rebuild the container for a codespace (useful after devcontainer.json changes).

```bash
gh codespace rebuild -c CODESPACE_NAME

# Full rebuild (no cache)
gh codespace rebuild -c CODESPACE_NAME --full
```

**Workflow:**
1. Ask which codespace to rebuild
2. Ask if full rebuild (no cache) is desired
3. Warn that rebuild may take several minutes
4. Execute rebuild

## Error Handling

- **Not authenticated**: Run `gh auth login` and ensure codespaces scope
- **No access**: User may not have codespaces enabled for the repo
- **Machine type unavailable**: List available types with `--show-machine-types`
- **Codespace not found**: Re-list codespaces to verify name
- **Rate limited**: Wait and retry

## Interactive Command Warning

Commands like `gh codespace ssh` are interactive and take over the terminal. Always warn the user before running interactive commands. For non-interactive alternatives, prefer `--json` output flags where available.

## Tips for Users

- Codespaces auto-stop after the idle timeout (default 30 min)
- Stopped codespaces still incur storage costs
- Use `--retention-period` to auto-delete after shutdown
- Port forwarding requires the codespace to be running
- Use `gh codespace list --json` for scriptable output
