---
name: git-worktree
description: This skill should be used when the user wants to "create a worktree", "work on another branch", "parallel branch", or needs to set up a git worktree with proper env files and dependencies.
argument-hint: <branch-name>
---

# Git Worktree Setup

Create or switch to a git worktree for branch: `$ARGUMENTS`

## Instructions

1. **Fetch latest from remote**
   ```bash
   git fetch --all --prune
   ```

2. **Determine branch and worktree path**
   - Branch name: `$ARGUMENTS`
   - Worktree path: `../<repo-name>-$ARGUMENTS` (sibling to current repo)

3. **Check if branch exists (local or remote)**
   ```bash
   git branch -a | grep -E "(^|\s)$ARGUMENTS$|remotes/origin/$ARGUMENTS$"
   ```

4. **Create the worktree**
   - If branch exists locally or remotely: `git worktree add <path> <branch>`
   - If branch doesn't exist: `git worktree add -b <branch> <path>`

5. **Copy environment files using the script**
   Run the copy-env script to copy .env and .env.local to the new worktree:
   ```bash
   scripts/copy-env.sh "<worktree-path>"
   ```
   Run this script from the skill's directory (Claude resolves the path automatically).

   IMPORTANT: You cannot read .env files directly. You MUST use this script.

6. **Install dependencies in the new worktree**
   ```bash
   cd <worktree-path> && pnpm install
   ```

7. **Report the result**
   - Confirm the worktree was created
   - Confirm env files were copied (check script output)
   - Confirm dependencies were installed
   - Provide the path to the new worktree

## Error Handling

- If the worktree already exists, inform the user and ask if they want to remove and recreate it
- If git fetch fails, check network connectivity
- If pnpm install fails, suggest running it manually
