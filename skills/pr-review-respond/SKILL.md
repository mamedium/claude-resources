---
name: pr-review-respond
description: Respond to bot review comments on the current PR, resolve threads where fixes have been applied, and trigger a new Codex review. Use when the user wants to address PR review comments, resolve bot feedback, or request a fresh review.
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# PR Review Respond Skill

This skill finds bot review comments on the current branch's PR, replies to them with context about applied fixes, resolves addressed threads, and triggers a new `@codex review`.

## What This Skill Does

1. **Finds the PR** for the current branch
2. **Fetches all review comments** from bot reviewers
3. **Identifies unresolved threads** that have been addressed by recent commits
4. **Replies to each comment** explaining what was fixed and referencing the commit
5. **Resolves the thread** via the GraphQL API
6. **Posts `@codex review`** to trigger a fresh automated review

## Execution Steps

### Step 1: Identify the PR

```bash
# Get current branch
git branch --show-current

# Find PR for this branch
gh pr list --head <branch> --json number,title,url
```

If no PR is found, inform the user and stop.

### Step 2: Fetch Review Comments

```bash
# Get all review comments with file, line, body, and author
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --jq '.[] | {id: .id, node_id: .node_id, path: .path, line: (.line // .original_line), author: .user.login, body: .body, in_reply_to_id: .in_reply_to_id}'
```

Filter to **top-level comments only** (where `in_reply_to_id` is null) — these are the original review comments, not replies.

### Step 3: Get Unresolved Threads

```bash
# Use GraphQL to get thread IDs and resolution status
gh api graphql -f query='
query {
  repository(owner: "{owner}", name: "{repo}") {
    pullRequest(number: {pr_number}) {
      reviewThreads(first: 50) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes {
              body
              databaseId
            }
          }
        }
      }
    }
  }
}'
```

Match threads to comments by `databaseId` to find unresolved ones.

### Step 4: Analyze Each Unresolved Comment

For each unresolved bot comment:

1. **Read the referenced file** at the mentioned line to understand current state
2. **Check recent commits** to find if/how the issue was addressed:
   ```bash
   git log --oneline -10 -- <file_path>
   ```
3. **Compare the comment's concern** against the current code

Categorize each comment as:
- **Addressed** — The issue has been fixed in a recent commit
- **Not addressed** — The issue still exists and needs work
- **Invalid** — The comment doesn't apply (false positive, outdated, etc.)

### Step 5: Reply and Resolve Addressed Comments

For each **addressed** comment:

1. **Reply** with a concise explanation of what was fixed and the commit hash:
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies \
     -X POST -f body="Fixed in {commit_hash} — {brief explanation of what changed}."
   ```

2. **Resolve the thread**:
   ```bash
   gh api graphql -f query='
   mutation {
     resolveReviewThread(input: {threadId: "{thread_node_id}"}) {
       thread { isResolved }
     }
   }'
   ```

For **not addressed** comments:
- Report them to the user with the file path, line, and concern
- Do NOT resolve these threads

For **invalid** comments:
- Reply explaining why the concern doesn't apply
- Resolve the thread

### Step 6: Trigger New Review

```bash
gh pr comment {pr_number} --body "@codex review"
```

### Step 7: Report Summary

Output a summary to the user:

```
## PR Review Response Summary

**PR:** #<number> - <title>

### Addressed (resolved)
- **<file>:<line>** — <brief description of fix> (commit: <hash>)

### Needs Attention (not resolved)
- **<file>:<line>** — <description of remaining issue>

### Invalid (resolved)
- **<file>:<line>** — <why it doesn't apply>

---
Triggered `@codex review` for a fresh review.
```

## Important Notes

1. **Only resolve comments that are actually fixed** — Never resolve a thread where the underlying issue still exists
2. **Reference specific commits** — Always include the commit hash in replies so reviewers can verify
3. **Be concise in replies** — One or two sentences explaining the fix is sufficient
4. **Detect the repo owner/name dynamically** — Use `gh repo view --json owner,name`
5. **Handle bot detection broadly** — Look for `[bot]` suffix in author login, or common bot names like `chatgpt-codex-connector[bot]`, `github-actions[bot]`, etc.
6. **Skip already-resolved threads** — Don't reply to threads that are already resolved
