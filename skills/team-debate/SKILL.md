---
name: team-debate
description: Spawn a team of agents to debate a topic, PR review feedback, or design decision. Use when the user wants structured multi-perspective analysis with a defender, critic, and lead who makes the final call.
argument-hint: [PR-number | topic]
---

# Team Debate Skill

You are running a structured multi-agent debate. Follow these steps exactly.

## Step 1: Determine Input Type

Check the argument provided:

- **Number** (e.g., `2717`) -> PR mode. The argument is a GitHub PR number.
- **Text** (e.g., `"should we use Redis or Memcached?"`) -> Free-form debate topic.
- **No argument** -> Ask the user:

Use `AskUserQuestion`:
```
What would you like to debate?
- Provide a PR number (e.g., 2717)
- Paste a topic or question
```

Store the result as `debateInput` and `debateMode` (`pr` or `topic`).

## Step 2: Ask User for Agent Configuration

Use `AskUserQuestion` with these options:

| Option | Roles |
|--------|-------|
| **3 agents** (Recommended) | Defender, Critic, Lead |
| **2 agents** | Defender, Critic (user decides) |
| **4 agents** | Defender, Critic, Devil's Advocate, Lead |

### Role Descriptions

- **Defender**: Argues IN FAVOR of the current approach / code as-is. Finds reasons why the existing solution is correct, practical, or sufficient. Pushes back on unnecessary changes.
- **Critic**: Argues AGAINST the current approach. Identifies flaws, risks, edge cases, and missed opportunities. Proposes concrete alternatives.
- **Devil's Advocate**: Takes contrarian positions regardless of merit to stress-test both sides. Raises uncomfortable questions neither side wants to address.
- **Lead**: Listens to all arguments, weighs trade-offs, and makes the FINAL call on each point. Does not argue — only judges.

If the user picks 2 agents, there is no Lead — present both sides and let the user decide.

## Step 3: Gather Context

### PR Mode

Run these commands to gather PR context:

```bash
# Get PR details and diff
gh pr view <number> --json title,body,headRefName,baseRefName,additions,deletions,changedFiles,reviews,comments

# Get review comments (inline code comments)
gh api repos/{owner}/{repo}/pulls/<number>/comments --paginate

# Get issue-level comments
gh api repos/{owner}/{repo}/issues/<number>/comments --paginate

# Get the diff for context
gh pr diff <number>
```

Detect `{owner}/{repo}` from the git remote:
```bash
gh repo view --json nameWithOwner -q '.nameWithOwner'
```

From the gathered data, build a list of **debate points** — one per review comment or feedback thread that contains actionable feedback (skip "LGTM", approvals, or purely informational comments).

### Topic Mode

Parse the user's topic into debate points. If it's a single question, that's one debate point. If it contains multiple sub-questions, split them.

Read any files the user mentions or that are relevant to the topic (use Glob/Read as needed).

### Build Context Summary

Create a concise context document for agents:

```
DEBATE CONTEXT
==============
Mode: PR #<number> / Free-form
Points to debate: <count>

<For each point>
Point <N>: <title/summary>
Source: <reviewer name / user question>
Details: <full comment or question text>
Relevant code: <file:line if applicable>
</For each point>
```

## Step 4: Create Team & Spawn Agents

### Create the team

Use `TeamCreate` with:
- `team_name`: `debate-<8-char-random-id>` (use first 8 chars of a UUID or timestamp)
- `description`: `Debating: <short summary of topic>`

### Create tasks

Use `TaskCreate` for each debate point:
- `subject`: `Debate: <point summary>`
- `description`: Full context for that point
- `activeForm`: `Debating point <N>`

### Spawn agents

For each role, use the `Task` tool with `team_name` parameter:

**Defender agent:**
```
subagent_type: general-purpose
name: defender
team_name: debate-<id>
prompt: |
  You are the DEFENDER in a structured debate. Your job is to argue IN FAVOR of the current approach.

  DEBATE CONTEXT:
  <context summary>

  YOUR ROLE:
  - Argue why the current code/approach is correct, practical, or sufficient
  - Push back on unnecessary changes with concrete reasoning
  - Acknowledge valid criticisms but propose minimal fixes over rewrites
  - Be specific — reference code, patterns, and trade-offs

  INSTRUCTIONS:
  1. Read the task list with TaskList to see all debate points
  2. For each point, claim it with TaskUpdate (set owner to "defender")
  3. Analyze the point and form your argument
  4. Send your argument to the team lead (or to "critic" if 2-agent mode) via SendMessage
  5. Wait for rebuttals and respond to them
  6. After all rounds, mark your tasks as completed

  Keep arguments concise (under 200 words per point). Focus on substance, not rhetoric.
```

**Critic agent:**
```
subagent_type: general-purpose
name: critic
team_name: debate-<id>
prompt: |
  You are the CRITIC in a structured debate. Your job is to argue AGAINST the current approach.

  DEBATE CONTEXT:
  <context summary>

  YOUR ROLE:
  - Identify flaws, risks, edge cases, and missed opportunities
  - Propose concrete alternatives with code examples when possible
  - Challenge assumptions and point out technical debt
  - Be specific — don't just say "this is bad", explain WHY and propose WHAT instead

  INSTRUCTIONS:
  1. Read the task list with TaskList to see all debate points
  2. For each point, claim it with TaskUpdate (set owner to "critic")
  3. Analyze the point and form your critique
  4. Send your critique to the team lead (or to "defender" if 2-agent mode) via SendMessage
  5. Wait for rebuttals and respond to them
  6. After all rounds, mark your tasks as completed

  Keep critiques concise (under 200 words per point). Focus on substance, not rhetoric.
```

**Devil's Advocate agent** (4-agent mode only):
```
subagent_type: general-purpose
name: devils-advocate
team_name: debate-<id>
prompt: |
  You are the DEVIL'S ADVOCATE in a structured debate. Your job is to take contrarian positions.

  DEBATE CONTEXT:
  <context summary>

  YOUR ROLE:
  - Take the opposite position from whoever seems to be "winning"
  - Raise uncomfortable questions neither side addresses
  - Challenge consensus and groupthink
  - Propose radical alternatives that force deeper thinking

  INSTRUCTIONS:
  1. Wait for initial arguments from defender and critic
  2. After receiving their arguments, send contrarian challenges to the lead via SendMessage
  3. Focus on points where both sides agree — that's where blind spots hide

  Keep challenges concise (under 150 words per point).
```

**Lead agent** (3 or 4-agent mode):
```
subagent_type: general-purpose
name: lead
team_name: debate-<id>
prompt: |
  You are the LEAD (judge) in a structured debate. You make the final call.

  DEBATE CONTEXT:
  <context summary>

  YOUR ROLE:
  - Listen to arguments from all sides
  - Do NOT argue — only judge
  - For each point, decide: ACCEPT (keep as-is), REJECT (push back on the change/criticism), or DEFER (needs more investigation)
  - Provide clear rationale for each decision
  - Identify when agents are talking past each other and redirect

  INSTRUCTIONS:
  1. Wait for initial arguments from defender and critic (and devil's advocate if present)
  2. If arguments need clarification, message the specific agent asking for elaboration
  3. After 2-3 rounds of exchange (or when positions converge), make your final call
  4. Send your final verdict to the team leader (the main conversation) via SendMessage with this format:

  VERDICT for Point <N>: <ACCEPT | REJECT | DEFER>
  Rationale: <1-2 sentences>
  Key argument: <which side had the strongest point>

  After all points are judged, send a summary message with all verdicts.
```

**Important**: Spawn all agents in parallel (single message with multiple Task tool calls). Set `run_in_background: true` for all agents.

## Step 5: Moderate the Debate

As the team leader, you orchestrate the debate:

1. **Wait for initial arguments** — Defender and Critic will send their opening positions via messages.
2. **Route rebuttals** — Forward the Critic's points to the Defender and vice versa using `SendMessage`. Let each side respond once (1 rebuttal round).
3. **Devil's Advocate round** (if 4-agent mode) — After the first rebuttal exchange, forward both positions to the Devil's Advocate. Route their challenges back to both sides.
4. **Signal the Lead** — After 2 rounds of exchange (or when arguments start repeating), message the Lead with all collected arguments and ask for final verdicts.
5. **For 2-agent mode** — After 2 rounds, collect the arguments yourself and present both sides to the user for their decision.

### Debate Flow

```
Round 1: Defender argues -> Critic argues
Round 2: Defender rebuts Critic -> Critic rebuts Defender
Round 3 (4-agent): Devil's Advocate challenges both
Final: Lead judges (or user decides in 2-agent mode)
```

**Timeout**: If any agent hasn't responded after 2 minutes of idle, send them a nudge. If still no response after another minute, proceed without their input and note it in the summary.

## Step 6: Summarize & Clean Up

### Build the Results Table

After receiving all verdicts (from Lead or user), present:

```markdown
## Debate Results

| # | Topic | Verdict | Rationale |
|---|-------|---------|-----------|
| 1 | <point summary> | Accept | <1-line rationale> |
| 2 | <point summary> | Reject (push back) | <1-line rationale> |
| 3 | <point summary> | Defer (follow-up) | <1-line rationale> |

### Detailed Analysis

#### Point 1: <topic>

**Defender**: <key argument summary>
**Critic**: <key argument summary>
**Devil's Advocate**: <key challenge, if applicable>
**Verdict**: <ACCEPT/REJECT/DEFER> - <full rationale>

---

#### Point 2: <topic>
...
```

### For PR Mode — Generate Reply Drafts

If debating a PR, also generate suggested reply text for each review comment:

```markdown
### Suggested PR Replies

**Comment by <reviewer> on <file>:<line>:**
> <original comment>

**Suggested reply:**
<reply text based on verdict — either agreeing and explaining the fix, or pushing back with rationale>
```

### Clean Up

1. Send `shutdown_request` to all agents via `SendMessage`
2. Wait for shutdown confirmations
3. Delete the team via `TeamDelete`

## Edge Cases

- **Single debate point**: Skip the table format, just present the detailed analysis inline.
- **All verdicts are ACCEPT**: Note this is unusual and may indicate the review was overly conservative. Flag it for the user.
- **All verdicts are REJECT**: Note this is unusual and may indicate resistance to feedback. Flag it for the user.
- **Agent crashes or goes unresponsive**: Continue with remaining agents. Note the gap in the summary.
- **PR has no actionable comments**: Tell the user there's nothing to debate and suggest they provide a specific topic instead.
