---
name: mode-autopilot
description: Autonomous execution mode - works through all tasks without stopping, researches decisions with agent teams, enforces TDD, backs up before risky operations, and self-reviews at the end. Triggers on "autopilot", "go autopilot", "autopilot mode", "/autopilot", or when the user wants sustained autonomous implementation with minimal interruption. This is NOT the /loop skill - /loop is for recurring intervals, /autopilot is for autonomous task completion.
argument-hint: <task-description-or-plan-reference>
---

# Autopilot Mode

Sustained autonomous execution. Work through all tasks without stopping. Research decisions with agent teams. Write tests first. Back up before anything risky. Self-review when done.

**Input**: `$ARGUMENTS`

---

## Step 0: Initialise

1. **Parse input**: Read `$ARGUMENTS` to understand the goal. If it references a plan file, read it. If it references an issue-tracker ticket (e.g. `ENG-123`), fetch the details. <!-- CUSTOMIZE: point this at your tracker integration - a Linear/Jira/GitHub Issues skill or MCP server. -->

2. **Build the task list**: Break the goal into discrete, verifiable tasks using `TaskCreate`. Each task must have:
   - A clear definition of done
   - A test strategy (what test proves this works)
   - A scope tag: `primary` (original goal) or `discovered` (found during work)
   - A planned gate from "Confidence gates before acting" (e.g. `bug-fix`, `new-feature`). If a task has no gateable evidence path, surface it now, not mid-execution.

3. **Set the execution order**: primary tasks first, discovered tasks after. Dependencies determine ordering within each group.

4. **Announce the plan**: Show the user the task list before starting. Do NOT wait for confirmation - start immediately after showing it.

---

## Confidence gates before acting

The audit point is **task completion (Step 1e)**. Pre-action checks are guidance. **Confidence percentages are not gates** - gates require something verifiable a reviewer can re-check.

**How to use the table**: pick every domain row that applies to the task (a perf+UX fix needs both rows cleared). Within a row, "clear >=1" means one of the listed evidence types in that row.

| Domain | Gate (clear >=1 within the row) |
|---|---|
| **Bug fix** | A test that reproduces the originally reported symptom (not "what the code currently does"), fails before the fix, passes after, and asserts the expected behaviour from the bug report. Root cause named with `file:line`. **Untestable bugs** (UI render, native crash, race, third-party timing): reproduction steps + manual verification log + root cause at `file:line`. |
| **New feature** | Point to >=1 existing sibling in the codebase that mirrors the work. **First-of-kind**: cite an external convention (named section/URL) and state "no sibling; setting precedent". |
| **Performance** | Paired before+after numbers with explicit delta (benchmark, query plan, bundle size, profiler sample). **No infra available**: complexity analysis (O() before/after) + named hot path at `file:line`. A single profiler trace with no baseline does not clear. |
| **UX / UI** | Anchor against >=2 sibling components in the codebase OR a named section of a platform doc (e.g. `HIG > Layout > Touch Targets`, not bare "per HIG"). **First-of-kind**: cite the convention + "setting precedent". |
| **DX / tooling** | Capture the real command(s) run plus an output snippet showing success. **Destructive workflows** (db push, deploy, force-push): defer to Step 2; clear via dry-run output + docs section. |
| **Refactor / architecture** | Name the pattern, point to >=1 sibling refactor in the codebase. If decided between alternatives, state what would flip the rejected one to correct. **First-of-kind**: cite external convention + "setting precedent". |
| **Documentation** | The change matches the source of truth being documented (cite `file:line` or URL). Examples build/run if shown. |
| **Dependency change** | Changelog/release notes link, breaking-changes scanned, lockfile diff reviewed, install + smoke run captured. |
| **Schema / migration** | Migration runs forward + reverse against a non-prod DB; cite the run output. For multi-tenant apps: tenant-scoping preserved on every touched query. |
| **CI / infra** | Workflow runs end-to-end on a branch with output snippet. For IaC/IAM changes, name the permission boundary. |
| **Security / tenant isolation** | Every changed query scopes by the tenant/org identifier (cite `file:line`). <!-- CUSTOMIZE: name your tenant key, e.g. orgId, accountId, workspaceId. --> Auth checks server-side, not UI. Test covers a cross-tenant attempt and expects denial. |
| **API / contract change** | Old + new shape diffed, deprecation path stated, consumers grep'd, backwards-compat note in the PR. |

**Exemptions** (gates do not apply): typos, mechanical renames, dependency version bumps with no API change, CSS-only tweaks, comments/docs without behaviour shift, throwaway scripts, changes <10 lines with no behaviour change.

**If no gate clears after one genuine retry** (re-read code, check siblings, write a probe test, profile - this counts as 1 of the 3 attempts allowed per Guardrails):
1. Surface the evidence you DID gather inline.
2. Mark the task `blocked` with `gate not cleared: <which>` rather than `completed` with thin evidence. **Under context pressure (Step 4), prefer blocked over thin completion.**
3. Continue with the next task.

**Definitions** (operational, not vibes):
- *Sibling*: a file in the same package or component family doing structurally similar work.
- *Probe test*: a throwaway test isolating one unknown (does this function return null on empty input?), deleted after.
- *Documented platform convention*: a citable section name or URL, not a bare standard reference.

**Tiebreaker** when multiple options clear gates: (a) clears the most applicable rows, (b) safest to reverse, (c) closest match to cited siblings.

**Wiring**: Step 1b names the gate alongside the test. Step 1c research agents return a *gate forecast* (which gate the option would need + initial signal), not final clearance. Step 1e cites the cleared gate + evidence. Step 3 reviewers spot-verify the citations.

---

## Step 1: Execute Task Loop

For each task in the list:

### 1a. Start the task
- Mark task `in_progress` via `TaskUpdate`
- Read all relevant files before making changes

### 1b. TDD First (default)
- **RED**: Write a failing test that defines the expected behaviour
- **GREEN**: Write the minimum implementation to pass the test
- **REFACTOR**: Clean up while keeping tests green
- **Name the gate**: state which row from "Confidence gates before acting" this task targets (e.g. `bug-fix`, `new-feature`). For non-bug tasks the test is necessary but not sufficient - the row's evidence still needs to be gathered.
- **Skip TDD only when**: pure config changes, CSS-only work, documentation, or no testable interface exists. Note the skip reason in the task. Skipping TDD does not skip the gate.

### 1c. Handle decisions that need user input
When you hit a fork where multiple valid approaches exist:

1. **Do NOT stop and ask the user.** Instead, spawn 3 parallel agents (agent teams) to research the options:
   - Agent 1: Research Option A (the most obvious/conventional approach)
   - Agent 2: Research Option B (an alternative with different tradeoffs)
   - Agent 3: Research Option C (a creative or less conventional approach)

2. Each agent must return:
   - What the option does and how to implement it
   - Pros and cons (concrete, not generic)
   - Risks and unknowns
   - **Gate forecast**: which gate the option would need to clear at implementation time, with initial signal (e.g. sketch of repro test, sibling at `path:line`). Not final clearance.

3. **Pick the option whose forecast clears the most applicable gates** (see "Confidence gates before acting" + tiebreaker rules). If no option's forecast clears, pick the safest reversible one, surface the evidence gap, and proceed. Present all 3 to the user inline (brief, not verbose) with your choice highlighted:

   ```
   Decision: <what needed deciding>

   --> Option A (chosen): <one-liner> - clears <gate-name> via <evidence>; safest to reverse
       Option B: <one-liner> - <which gate failed / why not chosen>
       Option C: <one-liner> - <which gate failed / why not chosen>
   ```

4. Implement the chosen option immediately. Do not wait for user approval unless the decision is destructive (see Step 2).

### 1d. Handle discovered issues
When you find bugs, tech debt, missing tests, or improvements during implementation:
- Create a new task via `TaskCreate` tagged as `discovered`
- Set priority: `blocking` (must fix now, current task depends on it) or `deferred` (fix after primary tasks)
- If `blocking`: fix it immediately, then resume the original task
- If `deferred`: log it and continue

### 1e. Complete the task
- Run tests to verify the task is done
- **State which gate cleared and cite the evidence** (test path, sibling `file:line`, before/after numbers, command output). This is the audit point - vague citations don't count.
- If no gate cleared after one retry: mark `blocked` with `gate not cleared: <which>`, do not mark `completed`.
- Mark task `completed` via `TaskUpdate`
- Move to the next task

---

## Step 2: Risky Operations Protocol

Before executing anything destructive or hard-to-reverse (file deletion, DB changes, force-push, config overwrites, package removal):

**Independent of gates**: a risky op needs BOTH a Step 2 backup AND its Confidence gate cleared. Backups are not evidence; evidence is not a backup.

### 2a. Create a backup
- **Files**: copy to a temp location or ensure they're committed in git
- **Git state**: create a checkpoint commit or stash (`git stash push -m "autopilot-backup-<task>"`)
- **DB**: dump the relevant table or record the current state
- **Config**: copy the original file before modifying

### 2b. If backup is impossible and risk is high
- **STOP that specific implementation**. Do not proceed.
- Log why it was skipped in the task: "Skipped: high risk, no backup possible - <details>"
- Mark the task as `blocked` and move on to the next task
- The user can decide how to handle it later

### 2c. If something goes wrong after a risky operation
- Restore from the backup immediately
- Log what happened and why it failed
- Mark the task as `blocked` with the failure reason

---

## Step 3: Self-Review Pass

When all tasks (primary + discovered) are complete, run a review cycle:

1. **Spawn 2 parallel review agents**:
   - Agent 1 (Correctness): Re-read all changed files. Look for bugs, edge cases, missing error handling, broken tests, type errors. **Spot-verify gate citations**: open each cited `file:line`, re-run each cited test, re-check each cited number. Flag any faked or unverifiable gate as a review finding.
   - Agent 2 (Risk/Improvement): Check for security issues, performance concerns, and improvements that align with the original goal. **Verify the gate row chosen actually fits the task** (a perf change marked `bug-fix` is a finding).

2. **If issues found**: Create new tasks tagged `review-finding`, add them to the task list, and execute them (loop back to Step 1).

3. **If no issues found**: Move to Step 4.

4. **Cap review iterations at 2.** After 2 review passes, stop and report remaining concerns rather than looping indefinitely.

---

## Step 4: Context Budget Check

Monitor context usage throughout execution:

- **At 75% context**: Wrap up the current task, skip remaining `deferred` and `discovered` tasks, go directly to Step 5 (Summary).
- **At 85% context**: Stop immediately, go to Step 5.
- If context is healthy and all tasks are genuinely done, proceed to Step 5.

---

## Step 5: Session Summary

Present a structured summary:

```
## Autopilot Summary

### Completed Tasks
- [x] Task 1: <description> (TDD: yes/skipped) - Gate: <row> via <evidence>
- [x] Task 2: <description> (TDD: yes/skipped) - Gate: <row> via <evidence>

### Skipped / Blocked Tasks
- [ ] Task N: <description> - Reason: <why> (gate not cleared: <which>)

### Key Decisions Made
| Decision | Chosen | Gate cleared (evidence) | Alternatives Rejected |
|----------|--------|------------------------|----------------------|
| <what>   | Option A | <row> via <evidence> | B: <gate gap>, C: <gate gap> |

### Risky Operations
- <operation>: backup at <location>, result: success/rolled-back

### Review Findings
- <finding 1>: fixed / deferred
- <finding 2>: fixed / deferred

### Remaining Work
- <anything left for the user or next session>
```

---

## Guardrails

- **Respect CLAUDE.md rules**: all existing policies (destructive actions, git safety, formatting) still apply. Autopilot does not override them.
- **Out-of-scope tasks are deprioritised**: discovered items go after primary tasks. Skip them if context is tight.
- **Agent teams are capped**: max 3 parallel agents per decision point. Don't burn context on over-research.
- **No infinite loops**: max 2 review iterations. Max 3 attempts at any single task before marking it blocked.
- **TDD is the default**, not optional. Explicitly note when and why it's skipped.
- **Decisions are logged**: every non-trivial choice is recorded for the summary. The user should be able to audit every decision after the fact.
- **No fabricated confidence.** Stating "90% sure" or "high certainty" without a citation a reviewer can re-check is a faked gate. Use the row's evidence types or mark `blocked`.
