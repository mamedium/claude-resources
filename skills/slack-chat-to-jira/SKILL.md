---
name: slack-chat-to-jira
description: Convert Slack conversations into well-structured Jira tickets. Investigates the codebase to validate bugs and enrich feature requests before creating tickets. Paste a Slack link to get started.
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
  - ToolSearch
  - mcp__claude_ai_Slack__slack_read_thread
  - mcp__claude_ai_Slack__slack_read_channel
  - mcp__claude_ai_Atlassian__getAccessibleAtlassianResources
  - mcp__claude_ai_Atlassian__getVisibleJiraProjects
  - mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql
  - mcp__claude_ai_Atlassian__atlassianUserInfo
  - mcp__claude_ai_Atlassian__createJiraIssue
  - mcp__claude_ai_Atlassian__editJiraIssue
  - mcp__claude_ai_Atlassian__getJiraIssue
  - mcp__claude_ai_Atlassian__getJiraProjectIssueTypesMetadata
  - mcp__claude_ai_Slack__slack_send_message
---

# Slack to Jira Skill

Convert Slack conversations into well-structured Jira tickets with QA-friendly descriptions and test cases.

**Prerequisites**: Both Slack and Jira MCP servers must be connected before using this skill. If either is missing, inform the user and stop.

**Input**: `/slack-chat-to-jira <slack-url> [PROJECT_KEY]`

## Step 1: Parse Slack URL & Resolve Project

Extract `channel_id` and `message_ts` from the provided URL.

**Supported URL formats:**
- Thread: `https://workspace.slack.com/archives/CXXXXXX/pXXXXXXXXXXXXXXXX`
- Thread with query: `https://workspace.slack.com/archives/CXXXXXX/pXXXXXXXXXXXXXXXX?thread_ts=XXXXXXXXXX.XXXXXX`
- Channel-only: `https://workspace.slack.com/archives/CXXXXXX`

**Parsing rules:**
1. Extract `channel_id` from the path segment after `/archives/`
2. Extract the message ID (starts with `p`) from the next path segment
3. Convert message ID to timestamp: remove `p` prefix, insert `.` before the last 6 digits
   - Example: `p1234567890123456` -> `1234567890.123456`
4. If `thread_ts` query param exists, use that as the thread timestamp

**Resolve cloud ID and project key:**

1. Fetch the cloud ID:
   ```
   getAccessibleAtlassianResources()  → extract cloudId
   ```

2. If a project key was passed as the second argument, use it directly. Otherwise, fetch the user's projects and let them choose:
   ```
   getVisibleJiraProjects(cloudId)  → list of projects
   ```
   Present the projects as options via **AskUserQuestion**, showing each project's key and name (e.g., "PROJ - My Project"). Let the user pick which project the ticket should be created in.

Store the resolved `cloudId` and `project_key` for use in later steps.

**Error handling:**
- If URL is missing or unparseable, show the expected formats and ask the user to provide a valid link
- If no argument was provided, ask the user for the Slack URL
- If `getVisibleJiraProjects` returns no projects, inform the user and stop

## Step 2: Read Slack Conversation

Use ToolSearch to load the Slack MCP tools, then read the conversation.

**Thread link (has message_ts):**
```
slack_read_thread(channel_id, message_ts)
```
- Paginate if needed, up to **300 messages max**
- If truncated, warn the user that not all messages were captured

**Channel-only link (no message_ts):**
```
slack_read_channel(channel_id)
```
- Read recent messages, then use **AskUserQuestion** to ask which topic/conversation the user wants to create a ticket for
- Once identified, focus on those relevant messages

**Error handling:**
- If the channel is private and inaccessible, suggest the user copy/paste the thread content directly and proceed with that text instead

## Step 3: Analyze & Determine Issue Type

Analyze the conversation content to determine whether this is a **BUG** or a **STORY**.

**BUG signals:**
- Words: "broken", "error", "crash", "not working", "bug", "issue", "fail", "500", "404"
- Stack traces, error messages, or logs
- Expected vs actual behavior descriptions
- Regression language ("used to work", "stopped working")

**STORY signals:**
- Words: "feature", "request", "add", "improve", "enhance", "new", "would be nice"
- New capability descriptions
- User workflow improvements
- Design or UX change requests

**If ambiguous**, use **AskUserQuestion** to ask the user whether this is a BUG or STORY.

### Acknowledge BUGs in Slack

If the issue is determined to be a **BUG**, immediately reply to the Slack thread to let the reporter know it's being looked at:
```
slack_send_message(channel_id, "Checking", thread_ts=message_ts)
```
Do this **before** continuing to the next steps. This gives the reporter quick feedback.

**Extract from conversation:**
- **Summary**: One-line description of the issue/feature
- **Requirements/Details**: Key points from the discussion
- **Affected area**: Which part of the system (dashboard, API, agent, etc.)
- **Severity hints**: How urgent/impactful (for bugs)
- **Participants**: Who reported it, who's involved
- **Original reporter**: The person who started the thread
- **Date**: When the conversation started

## Step 4: Investigate Codebase

Before drafting the ticket, search the codebase to validate the issue and understand what's involved. This ensures you write accurate tickets and can advise the user on whether a bug is real.

**Reports come from the CS team — they describe issues in user-facing terms** (e.g., "invoice page not loading", "customer can't see appointments"), not code paths. You need to translate their description into codebase searches.

**How to derive search terms from CS reports:**
- "invoice page" → search for `invoice` in `apps/dashboard/src`
- "can't send SMS" → search for `sms` or `sendSms` in `internal/`
- "appointment not showing" → search for `appointment` in routes/components
- "onboarding stuck" → search for `onboarding` in dashboard components
- Use the feature/entity name, not the symptom

**Use `Glob` and `Grep` to search. Keep it to 2-3 searches max.**

**For BUGs — validate the issue:**
- Find the relevant code area based on the feature described
- Check if the reported behavior matches what the code actually does
- Look for recent changes that might have caused a regression (`git log --oneline -10 -- <file>`)
- Form an opinion: Is this a real bug, expected behavior, or user error?
- Use your findings to give the user a confident recommendation during the Bug Validation Gate (Step 7)

**For STORYs — understand the current state:**
- Find existing related features (what already exists in this area?)
- Identify the relevant database tables, API routes, or components
- Check if something similar has already been built that could be extended
- Use this understanding to write more accurate requirements, acceptance criteria, and test cases in the ticket

### Bug Validation Gate (BUGs only)

After investigating the codebase, present your findings to the user:
- What the reported issue is
- What you found in the code (is it a real bug, expected behavior, user error, already fixed?)
- Your recommendation

Then use **AskUserQuestion** to ask the user:
1. **Confirmed bug — notify Slack**: Reply to the Slack thread confirming the issue and letting the reporter know it will be fixed, then continue to Step 5.
2. **Confirmed bug — skip Slack notification**: Continue to Step 5 without replying to Slack.
3. **Not a valid bug**: Ask the reason, reply to Slack explaining why, and stop the workflow.

**If the user confirms and wants Slack notified**, reply to the thread:
```
slack_send_message(channel_id, "Thanks for reporting this — looks like <brief description of the issue>. We'll get this fixed.", thread_ts=message_ts)
```

**If the user says it's not a valid bug:**
1. Use **AskUserQuestion** to ask the reason (e.g. user error, expected behavior, already fixed, won't fix, etc.)
2. Reply to the Slack thread explaining why, based on the user's reason:
   ```
   slack_send_message(channel_id, "Thanks for flagging this — <explanation>. Let us know if you run into anything else!", thread_ts=message_ts)
   ```
3. Stop the workflow — do not create a ticket.

## Step 5: Check for Duplicates

Search Jira for potential duplicate issues.

1. Using the `cloudId` and `project_key` resolved in Step 1, search for duplicates:
   ```
   searchJiraIssuesUsingJql(cloudId, 'project = <project_key> AND status != Done AND summary ~ "<key_terms>"')
   ```
   - Use 2-3 most distinctive words from the summary
   - Also try alternative phrasings if the first search returns nothing

3. If matches are found, collect their keys, summaries, and statuses to present in the preview.

## Step 6: Get Current User Info

Retrieve the current user's Atlassian account for assignment and reporter fields:
```
atlassianUserInfo()
```
Extract the `account_id` from the response.

## Step 6b: Resolve Active Sprint

After getting the current user info, find the project's active sprint so the ticket can be automatically added to it.

1. **Find an issue in the active sprint** using JQL:
   ```
   searchJiraIssuesUsingJql(cloudId, 'project = <project_key> AND sprint in openSprints()', maxResults=1)
   ```

2. **If results are returned**, take the first issue's key and fetch its sprint field:
   ```
   getJiraIssue(cloudId, issue_key, fields=["customfield_10020"])
   ```
   Extract the active sprint from the `customfield_10020` array — find the entry with `"state": "active"` and store its `id` and `name`.

3. **If no results are returned** (no issues in an active sprint), the project may not use sprints or has no active sprint. In this case, set `active_sprint = null` and skip sprint assignment later. Do NOT ask the user — just proceed without sprint assignment and note it in the preview.

Store the resolved `sprint_id` and `sprint_name` for use in Steps 7 and 8.

## Step 7: Present Preview (MANDATORY)

**You MUST show the complete ticket draft to the user before creating it.** Never skip this step.

Before building the preview, validate the issue type name against the project's configuration:
```
getJiraProjectIssueTypesMetadata(cloudId, "<project_key>")
```
Use the exact issue type name from the metadata (e.g., "Bug" not "BUG", "Story" not "STORY").

Present the preview using this format:

```
## Jira Ticket Preview

**Type**: Bug / Story
**Summary**: <one-line summary>
**Sprint**: <sprint_name> (or "No active sprint — ticket will be created in backlog")
**Assignee**: <current user name>
**Reporter**: <current user name>

### Description

<Full description using the appropriate template from TEMPLATES.md>

---

### Potential Duplicates
- <PROJECT_KEY>-XXXX: <summary> (Status: <status>)
- (or "No duplicates found")

---

Does this look good? You can ask me to edit any part before I create it.
```

### Approval

Wait for the user to **approve**, **request edits**, or **cancel**.
- If they approve, proceed to Step 8
- If they request edits, update the draft and show the preview again
- If they cancel, stop without creating anything

## Step 8: Create Jira Ticket

Once approved, create the ticket:

1. **Create the issue:**
   ```
   createJiraIssue(cloudId, "<project_key>", "<issue_type_name>", summary, description, assignee_account_id)
   ```

2. **Set reporter** (if not automatically set):
   ```
   editJiraIssue(cloudId, issue_key, { reporter: { accountId: current_user_account_id } })
   ```

3. **Assign to active sprint** (if `active_sprint` was resolved in Step 6b):
   ```
   editJiraIssue(cloudId, issue_key, { customfield_10020: sprint_id })
   ```
   - **Important**: Pass the sprint ID as a plain integer (e.g., `600`), NOT as an object (`{"id": 600}`) — the object format returns a Bad Request error
   - This can be combined with the reporter update into a single `editJiraIssue` call
   - If no active sprint was found, skip this step — the ticket stays in the backlog

5. **Reply to Slack thread with ticket link:**
   ```
   slack_send_message(channel_id, "Jira ticket created: <jira_base_url>/browse/<PROJECT_KEY>-XXXX", thread_ts=message_ts)
   ```
   This notifies the original reporter and thread participants that a ticket has been filed.

6. **Output the result to the user:**
   ```
   Jira ticket created: <jira_base_url>/browse/<PROJECT_KEY>-XXXX
   (Slack thread notified)
   ```

**Error handling:**
- If `createJiraIssue` fails, preserve the full draft description and show it to the user
- Report the error and suggest they can manually create the ticket with the drafted content
- If the issue type name doesn't match, try fetching `getJiraProjectIssueTypesMetadata` again and use the closest match

## Edge Cases

| Scenario | Action |
|----------|--------|
| Invalid/unparseable URL | Show expected formats, ask for valid link |
| Private channel (no access) | Suggest copy/paste, work with pasted content |
| Thread too long (>300 msgs) | Cap at 300, warn about truncation |
| Ambiguous BUG vs STORY | Ask user via AskUserQuestion |
| Duplicate found | Show in preview, let user decide to proceed or not |
| createJiraIssue fails | Preserve draft, report error, suggest manual creation |
| Issue type name mismatch | Validate with getJiraProjectIssueTypesMetadata first |
| No active sprint | Skip sprint assignment, ticket goes to backlog, note in preview |
| Sprint assignment fails | Log warning but don't fail — ticket is still created |

## Templates

Refer to `TEMPLATES.md` in this skill directory for the BUG and STORY description templates.
