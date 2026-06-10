---
name: pr-comments-triage
description: Triage unresolved PR review comments across a stack or single PR - verify claims at source, push back on speculation, draft replies, wait for approval before fixing
allowed-tools: Read, Grep, Glob, Bash
---

# PR Comments Triage Skill

Pull unresolved review comments across a Graphite stack (or a single PR), analyse each comment critically - **defaulting to pushing back** - and draft a decision + reply per thread. Wait for user approval before writing code.

## When to use

Trigger phrases:
- "address the PR comments on this stack"
- "go through reviewer feedback on the stack"
- "triage stack comments"
- "/pr-comments-triage"

Works for:
- Single PR (pass the PR number)
- Entire Graphite stack (default when on a stacked branch)
- Mix of automated review bots (Codex, Copilot, CodeRabbit) and human reviewers

## Core posture

**The working code is the current source of truth. Default to arguing against reviewer claims until proven otherwise.**

- Reviewer bots generate plausible-sounding but often wrong critiques
- "Might break in X scenario" is not the same as "breaks in X scenario"
- A valid claim must be reproducible against the actual source, not just the diff
- Legitimate bugs get accepted; speculative concerns get pushed back on with evidence

**Exception (never argue):** security issues, destructive data operations, and any always-fix patterns documented in your repo's `CLAUDE.md` (e.g. tenant isolation / org-scoped queries in a multi-tenant app). These get fixed, not debated.

<!-- CUSTOMIZE: list your repo's non-negotiable review categories here so the skill auto-escalates them to Accept. -->

## Workflow

### Step 1 - Map the stack

```bash
gt log short          # Graphite stacks; skip if triaging a single PR
git branch --show-current
```

Collect the PR numbers for every branch in the stack (use `gh pr list --author "@me" --state open --json number,title,headRefName,url`).

### Step 2 - Pull unresolved review threads

For each PR, use the GraphQL `reviewThreads` query (not `gh pr view --comments` - it mixes resolved and unresolved):

```bash
for pr in <pr-numbers>; do
  gh api graphql -f query='
    query($prNumber: Int!) {
      repository(owner: "<owner>", name: "<repo>") {
        pullRequest(number: $prNumber) {
          title
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              isOutdated
              path
              line
              comments(first: 20) {
                nodes { author { login } body createdAt url }
              }
            }
          }
        }
      }
    }' -F prNumber=$pr --jq '{
      title: .data.repository.pullRequest.title,
      unresolved: [.data.repository.pullRequest.reviewThreads.nodes[]
        | select(.isResolved == false)
        | {id, path, line, isOutdated,
           comments: [.comments.nodes[] | {author: .author.login, body, url}]}]
    }'
done
```

Keep the thread IDs - you'll need them to resolve/reply via GraphQL.

### Step 3 - Verify at source (mandatory before drafting a decision)

**Never decide based on the reviewer's words alone.** For each thread:

1. Read the exact file + lines cited
2. If the claim references cross-file behaviour (e.g. "this handler is called by X which does Y"), read that caller too
3. Cross-check against your repo's `CLAUDE.md` anti-patterns - if it matches a documented always-fix pattern, it's almost certainly legit
4. Note line drift: reviewer bots cite lines from the PR diff, which may have shifted since. Search by symbol, not line number

Batch reads in parallel when possible - one turn can read 8+ files.

### Step 4 - Classify each thread

Apply these posture labels:

| Label | Meaning | Bias |
|---|---|---|
| **Accept** | Verified bug. Fix reduces risk and doesn't break current behaviour | Rare - only when source confirms |
| **Accept (small)** | Trivial improvement, low risk, costs nothing to apply | Prefer over arguing when the fix is <=5 lines |
| **Defer** | Real but out-of-scope for this PR. Track as follow-up | Use when legit but stack is already large |
| **Reject (speculative)** | Reviewer describes a scenario that can't actually occur in production | Default for "might happen if..." claims |
| **Reject (wrong)** | Claim is factually incorrect - the code does handle this | Use when source verification shows the reviewer misread |
| **Reject (intentional)** | Current behaviour is deliberate, often documented in a comment or PR description | Use when it's a design decision, not an oversight |
| **Ask (human input)** | Ambiguous business logic or design tradeoff; requires user decision | Use sparingly |

Security / always-fix claims: auto-escalate to **Accept** unless source clearly shows the protection is enforced elsewhere.

### Step 5 - Draft the decision matrix

Present as a table or per-PR list with this shape:

```
### PR #NNNN - <title>
**Thread 1** · `<path>:<line>` · <Badge> · <Reviewer>
- **Claim (summary)**: <one-line paraphrase of reviewer's point>
- **Verification**: <what I read, what I confirmed or disproved>
- **Decision**: <Accept / Reject / Defer> - <one-line rationale>
- **Reply draft**:
  > <proposed reply text that will be posted once approved>
```

Show the full matrix to the user. **Do not write code yet.**

### Step 6 - Wait for approval

Prompt: "Approve these decisions? Reply with the thread IDs to apply (or 'all') and I'll proceed with the code fixes. Threads you want to re-argue can be flagged and we'll revisit."

The user may:
- Approve all -> proceed to Step 7 for every Accept/Accept-small thread
- Approve a subset -> proceed only for those
- Overrule a rejection -> flip to Accept, apply the fix
- Overrule an accept -> flip to Reject, just post the reply

### Step 7 - Execute fixes (only after approval)

For each approved Accept:
1. Apply the minimal fix on the correct branch in the stack
2. Run your repo's lint + typecheck commands scoped to the affected package <!-- CUSTOMIZE: e.g. `pnpm lint:fix && pnpm typecheck` -->
3. Commit with a conventional commit message <!-- CUSTOMIZE: append your ticket-ID convention, e.g. `[ENG-123]` -->
4. Push / submit (`gt submit --no-interactive --draft` for Graphite stacks, `git push` otherwise)
5. Post the reply on the thread and resolve it via GraphQL:

```bash
gh api graphql -f query='
  mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) {
      comment { url }
    }
  }' -F threadId="$THREAD_ID" -F body="$REPLY_BODY"

gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread { isResolved }
    }
  }' -F threadId="$THREAD_ID"
```

For each approved Reject/Defer:
- Post the reply (rationale) but do NOT resolve - let the reviewer resolve or push back
- If reviewer doesn't push back within the agreed window, then resolve

> **Note on human reviewers:** bot threads are safe to reply to and resolve autonomously. For threads opened by humans, consider drafting the reply for the user to post themselves - tone and team norms matter more there.

## Reply-writing conventions

- Keep replies terse and direct. Max 3 sentences for a rejection, 1 sentence for an acceptance
- Cite source: `See <path>:<line>` or `Intentional per <doc section>`
- Never apologise for disagreeing; just state the reasoning
- For bot replies (Codex, Copilot, CodeRabbit): no need to be diplomatic - the bot doesn't read tone

### Templates

**Accept:**
> Good catch. Fixing in a follow-up commit - will apply the fix and add a regression test.

**Reject (speculative):**
> This scenario can't occur here because `<invariant>`. Specifically, `<code pointer>` guarantees `<X>` before this path runs. Closing as not applicable.

**Reject (wrong):**
> The dispatcher handles this at `<path>:<line>` - see the `<branch>` case. The default null fallback is reachable only for unknown kinds, which are schema-validated upstream.

**Defer:**
> Valid but out of scope for this PR (stack is already 8 PRs). Tracked as `<TICKET-ID>`. Resolving as intentional-for-later.

## Anti-patterns (things that bite in practice)

- **Accepting the P1/critical badge at face value.** Review bots slap high severity on everything vaguely "could break". Verify before trusting.
- **Using PR-diff line numbers as current line numbers.** Stack PRs rebase constantly - always search by symbol.
- **Fixing in the wrong branch.** A comment on the bottom PR of a stack must be fixed on that PR's branch, not on the current HEAD. Use `gt checkout <branch>` first.
- **Resolving the thread before the fix lands.** Resolve only after the commit is pushed and visible on the PR.
- **Addressing cosmetic nits on a large stack.** Drops velocity; defer to a single follow-up cleanup PR.

## Output format

When invoked, produce:
1. A one-line count of unresolved threads per PR (acts as a health check)
2. The full decision matrix (Step 5 format)
3. A closing prompt asking for approval

Do NOT:
- Auto-apply any code change
- Resolve any thread
- Post any reply

...until the user explicitly approves.
