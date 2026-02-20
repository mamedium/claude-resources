# Hotfix PR Skill

Create a hotfix PR that cherry-picks a merged dev PR directly to main for immediate deployment.

## When to use

When the user says "hotfix", "create hotfix PR", "cherry-pick to main", or needs to fast-track a fix that's already merged to dev.

## Usage

```
/hotfix <PR-number>
```

If no PR number is given, ask the user which PR to hotfix, or default to the most recent merged PR on the current branch.

## Workflow

### Step 1: Identify the source PR

Get the merge commit SHA from the source PR:
```bash
gh pr view <PR-number> --json mergeCommit,title --jq '.mergeCommit.oid'
```

If the PR is not yet merged, warn the user and stop.

### Step 2: Create hotfix branch from main

```bash
git fetch origin main dev
git checkout -b hotfix/<branch-name> origin/main
```

Branch naming: `hotfix/<ticket-id>` (e.g., `hotfix/ENG-123`). Extract the ticket ID from the source PR title or branch name.

### Step 3: Cherry-pick the merge commit

```bash
git cherry-pick <merge-commit-sha> -m 1
```

The `-m 1` flag selects the first parent (main line) for merge commits.

If there are conflicts:
1. Show the conflicting files to the user
2. Ask how they want to resolve
3. After resolution: `git add -A && git cherry-pick --continue`

### Step 4: Push and create draft PR

```bash
git push origin hotfix/<branch-name>
```

Create a **draft** PR targeting `main`:
```bash
gh pr create --base main --draft --title "<same title as source PR>" --body "$(cat <<'EOF'
# Hotfix: <title>

Cherry-pick from #<source-PR-number> (merged to dev).

<copy summary and changes from source PR>
EOF
)"
```

### Step 5: Report

Output:
- Hotfix PR URL
- Source PR reference
- Remind user to mark ready for review when CI passes

## Important Rules

1. **Always create as draft** — never create ready PRs
2. **Always target main** — hotfix PRs bypass the dev → main release cycle
3. **Always reference the source PR** — include `Cherry-pick from #<number>` in the body
4. **Reuse the source PR title and description** — don't rewrite, keep consistency
5. **Use `-m 1` for cherry-pick** — merge commits need parent selection
6. **Handle conflicts gracefully** — show files and ask user, don't force resolve
