---
name: solve-ticket
description: End-to-end ticket pipeline - deep-dive analysis, plan, second-model review of the plan, apply legit feedback, execute autonomously with TDD, then review the generated code. Use when the user wants a ticket driven from analysis to a draft PR with minimal hand-holding. Triggers on "/solve-ticket", "solve ENG-123", "run the pipeline on", "full-send this ticket".
argument-hint: <ticket-id-or-task-description>
---

# Solve Ticket

A fixed delivery pipeline for one ticket: **analyse -> plan -> review the plan -> apply -> build -> review the code**. Each stage gates the next. The goal is a clean draft PR with the root cause actually understood, not a plausible patch.

**Input**: `$ARGUMENTS` (a ticket ID like `ENG-123`, or a free-text task description)

> Throughout: feature branches only (never push to the default branch), draft PRs, TDD for non-trivial code, KISS over DRY, ask before destructive actions.

<!-- CUSTOMIZE: this pipeline assumes Linear for tickets (via the `linear` skill) and an optional second-model reviewer (e.g. an OpenAI Codex CLI skill). Swap in your own tracker/reviewer where noted. -->

---

## Step 0: Setup

1. **Resolve the ticket.** If `$ARGUMENTS` is a ticket ID, fetch it (e.g. via the `linear` skill, including attachments and relations). Read any linked thread or screenshot for the real-world symptom. If it's free text, work from that and note no ticket is attached.
2. **Branch / worktree.** Use the tracker's auto-generated branch name (e.g. Linear's `gitBranchName`) - never hand-construct it. If not already on that branch, set up a worktree via the `git-worktree` skill. Confirm with the user before creating it if disk is tight.
3. **Work log.** <!-- CUSTOMIZE: if you keep a daily work log, append an in-progress item for the ticket here. Otherwise skip. -->
4. **Ticket status.** If the ticket is in Backlog/Todo, note that it should move to In Progress (don't change it without the user's ok unless they've said to keep the tracker in sync).

State a one-line plan-of-attack before proceeding.

---

## Step 1: Deep-dive analysis

Goal: understand **why** the behaviour happens and **what the correct flow is**, before any code.

First classify the ticket: **bug** (existing behaviour is wrong) or **feature** (behaviour doesn't exist yet). This shapes the brief below.

1. **Fan out parallel exploration agents** (use `Explore` / general-purpose subagents - keep the main thread clean). Give each a narrow scope:
   - **Behaviour path** - where the broken/missing behaviour lives (which app/package, screen/page, component, route, handler). Locate it from the ticket - don't assume.
   - **Reference path** - if a sibling app or module already implements the same capability, find it: component, API call, data shape, entry point. That's the source-of-truth pattern to mirror. If no sibling implementation exists, find the closest in-codebase analogue instead and say so explicitly.
   - **Shared layer** - the routers, hooks, types, or packages involved. Confirm whether the capability exists and is just unwired in the target, vs missing entirely.
2. **Produce an analysis brief** (inline, concise):
   - **Bug**: root cause in one sentence. **Feature**: the gap in one sentence (what's missing and where it plugs in).
   - Current flow vs expected flow (a short before/after - ASCII diagram in a ```text``` fence, since Claude Code CLI doesn't render mermaid).
   - Reference pattern with `file:line` anchors.
   - Affected files + blast radius.
   - Open questions (only if a wrong guess would waste >5 min or touch unfamiliar business logic - otherwise pick the obvious option and note the assumption).

If the root cause (or the right insertion point, for features) is genuinely ambiguous after exploration, stop and ask. Otherwise continue.

---

## Step 2: Planning

Before writing the plan, explore the codebase across 8 categories: similar implementations, naming conventions, error handling, logging/observability, type definitions, test patterns, configuration, available dependencies. Trace the relevant code paths (happy, error, auth, data mutation, external services).

The plan MUST include:

- A **Patterns to Mirror** section with real code snippets + `file:line` refs (mirror the reference pattern from Step 1 - do not invent patterns).
- Step-by-step tasks where each step has a **validation command**.
- A saved plan file: `~/.claude/plans/<TICKET>-<slug>.md`. <!-- CUSTOMIZE: point this at your notes directory if you keep plans elsewhere. -->

Keep the plan tight and TDD-shaped: for each behaviour change, name the failing test first, then the minimum implementation.

---

## Step 3: Second-model review of the plan

Hand the saved plan plus the Step 1 analysis brief to an **independent reviewer** - ideally a different model (e.g. a Codex CLI skill in read-only mode), otherwise a fresh-context reviewer agent. Ask it specifically to attack:

- Wrong or shallow root cause.
- A simpler approach being missed (KISS / over-engineering).
- Missed edge cases, error paths, or platform gotchas.
- Whether the reference pattern is actually the right thing to mirror here.

A different model has independent signal - where it disagrees, that disagreement is worth taking seriously.

**Fallback**: if the second model is unavailable (CLI missing, auth or rate-limit errors), don't dead-end the pipeline. Substitute a fresh-context reviewer agent with the same attack list, and note the substitution in the final summary.

---

## Step 4: Apply legitimate feedback

Triage the reviewer's findings. For each: **accept** (fold into the plan) or **reject** (one-line reason). Don't apply feedback blindly - only what genuinely improves the plan. Update the saved plan file. Show the user a short accept/reject table before building.

> Cap: one review pass here. Don't loop the plan through review repeatedly - apply, then build.

---

## Step 5: Execute autonomously

Work through the finalised plan without stopping: <!-- CUSTOMIZE: if you have an autopilot-style execution skill, invoke it here with the plan file as input. -->

- Build a task list (TaskCreate) and execute in order.
- Enforce TDD (failing test -> minimum impl -> refactor).
- Spawn a **writer + reviewer** agent team for non-trivial changes (writer implements, reviewer critiques in fresh context).
- Back up before anything risky; never run destructive actions autonomously.
- Self-review at the end.

Break only on ambiguous business logic or a destructive action.

---

## Step 6: Second-model review of the generated code

Once execution reports done, run the independent reviewer over the actual diff against the base branch (e.g. `codex review --base <base>` if using a Codex skill - diff-aware and read-only). Focus it on:

- Correctness vs the plan's intent (did it solve the root cause, not just the symptom?).
- Bugs, regressions, missed error/edge cases.
- Reuse / simplification / dead code.
- Consistency with the mirrored reference pattern.

Triage the findings (accept/reject, same as Step 4) and apply the legit ones to the working tree. Cap at one apply pass; report any remaining low-confidence concerns instead of looping.

---

## Step 7: Test cases - dev smoke test + QA detail

Two distinct audiences, two destinations. Don't mix them.

### 7a. Dev smoke test (for the developer)

A **short smoke test** so the developer can sanity-check the key points of the code change before publishing the PR. NOT a full QA matrix - just "did the thing I changed actually work, and did I obviously break anything next to it".

- **Path**: `~/.claude/plans/<TICKET>-dev-smoke-test.md` <!-- CUSTOMIZE: point at your notes directory. -->
- **Contents** - derive strictly from the actual diff, key points only:
  - The **core flow the change fixes** - 1 happy-path check.
  - 1-3 **key-point checks** tied to specific changed files/behaviour (the things most likely to be wrong given what was edited).
  - 1-2 **adjacent regression** checks only if the diff touched shared code.
  - Each as a checkbox: `- [ ] <steps> -> <expected result>`.
- Keep it to ~5 checks, tickable in a couple of minutes. Print the file path in the summary.

### 7b. Detailed QA test cases (for QA, on the ticket)

**QA-skip check first.** If the change is *exclusively* test-only / CI-CD config / docs / non-shipped repo tooling, skip the test matrix entirely: draft a short comment instead stating why QA is skipped and tagging your QA owner. <!-- CUSTOMIZE: your team's QA-skip policy and who to tag. --> Otherwise:

The **full, detailed test matrix** goes on the ticket itself so QA picks it up there. **Draft it now, post it in Step 8** once the PR exists - the comment needs to say where to test (PR link / preview env / build), which isn't known yet. Post as a **comment** (non-destructive; don't overwrite the description).

- Comment header: `## QA Test Plan` + one line on what shipped and where to test.
- Detailed scenarios as checkboxes, grouped: **Happy paths**, **Edge / error cases** (empty input, offline, long input, permission denied, rapid interaction, backgrounding mid-flow), **Regression** (adjacent flows the change could plausibly break), **Cross-cutting** (platform specifics, theming, multi-org/tenant).

Surface both - the smoke-test file path AND the drafted QA plan (or QA-skip comment) destined for the ticket - in the final summary.

---

## Step 8: Wrap up

1. **Verify**: tests pass; for UI changes confirm behaviour in a browser or on-device. Plausible-looking-but-unverified code is not done.
2. **PR**: open as **draft** (mark ready only on explicit request) against your team's base branch. <!-- CUSTOMIZE: `gt submit` if you use Graphite (mind any stack-size limits), otherwise `gh pr create --draft`. --> Title format `type(scope): lowercase description [TICKET-ID]`. PR description: summary (why before what), tight change bullets, a before/after ASCII diagram if there's structural logic, manual test plan. No AI attribution.
3. **Post the Step 7b comment** on the ticket - the QA test plan (now including the PR link / where to test) or the QA-skip reason.
4. **Work log**: check off the in-progress item, detail proportional to scope.
5. **Ticket status**: note the status should move (e.g. -> In Review). Don't flip it without the user's ok unless told to keep the tracker in sync.
6. **Summary**: one tight table - root cause, what changed, files touched, test result, smoke-test file path, QA plan posted (Y/N, or QA-skip), PR link. Call out explicitly that the PR is draft and pending the dev smoke test before publish. No narration.

---

## Notes

- This is a **pipeline**, not a suggestion box - run the stages in order, each gating the next. The two review gates (plan + code) are the point; don't skip them.
- Respect context budget: at 75% wrap up the current stage and skip deferred work; at 85% surface remaining work. Delegate broad exploration to subagents to keep the main thread lean.
- If the same stage fails 3 times, stop and surface as blocked rather than looping.
