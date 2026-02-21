# Jira Description Templates

## BUG Template

Use this template when the issue type is Bug.

```
## Summary

<1-2 sentence summary of the bug>

## Steps to Reproduce

1. <Step 1>
2. <Step 2>
3. <Step 3>

## Expected Behavior

<What should happen>

## Actual Behavior

<What actually happens, include error messages if available>

## Environment

- **Affected Area**: <dashboard / API / agent / integrations / etc.>
- **Severity**: <Critical / Major / Minor / Trivial>
- **First Reported**: <date from Slack thread>
- **Reported By**: <original reporter from Slack>

## Test Cases

### TC1: Fix Verification
- **Precondition**: <setup needed>
- **Steps**: <steps to verify the fix>
- **Expected**: <correct behavior after fix>

### TC2: Regression Check
- **Precondition**: <setup needed>
- **Steps**: <steps to verify related functionality still works>
- **Expected**: <existing behavior is preserved>

### TC3: Edge Case
- **Precondition**: <setup needed>
- **Steps**: <steps for boundary/edge case>
- **Expected**: <correct handling of edge case>

---

*Source: [Slack thread](<slack_thread_url>)*
```

## STORY Template

Use this template when the issue type is Story.

```
## Summary

<1-2 sentence summary of the feature>

## User Story

As a <role>, I want to <action>, so that <benefit>.

## Requirements

- <Requirement 1>
- <Requirement 2>
- <Requirement 3>

## Acceptance Criteria

- [ ] <Criterion 1>
- [ ] <Criterion 2>
- [ ] <Criterion 3>

## Details

- **Affected Area**: <dashboard / API / agent / integrations / etc.>
- **Requested**: <date from Slack thread>
- **Requested By**: <original requester from Slack>

## Test Cases

### TC1: Happy Path
- **Precondition**: <setup needed>
- **Steps**: <steps for the main success scenario>
- **Expected**: <feature works as described>

### TC2: Validation & Error Handling
- **Precondition**: <setup needed>
- **Steps**: <steps with invalid input or error conditions>
- **Expected**: <proper validation messages or graceful error handling>

### TC3: Permissions & Access
- **Precondition**: <setup with different user roles>
- **Steps**: <steps to verify access control>
- **Expected**: <correct behavior per role/permission>

---

*Source: [Slack thread](<slack_thread_url>)*
```

## Template Notes

- Use **Markdown** formatting (##, ###, -, **bold**, [text](url)) — the Atlassian MCP tool converts Markdown to ADF automatically
- Do NOT use Jira wiki markup (h2., h3., *, #, [text|url]) — it will render as plain text
- Replace all `<placeholder>` values with actual content from the Slack conversation
- Test cases should be specific and actionable, not generic
- Include 3 test cases minimum for each template
- The Slack thread link should always be included at the bottom
- Severity for bugs: Critical (system down), Major (feature broken), Minor (cosmetic/workaround exists), Trivial (negligible impact)
