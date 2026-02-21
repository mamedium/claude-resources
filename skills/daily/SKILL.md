---
name: daily
description: Daily note review, update, and next-day generation
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Bash
  - AskUserQuestion
  - mcp__claude_ai_Slack__slack_read_channel
  - mcp__claude_ai_Slack__slack_search_public_and_private
  - mcp__claude_ai_Slack__slack_search_public
  - mcp__claude_ai_Slack__slack_send_message
  - mcp__claude_ai_Slack__slack_read_thread
  - mcp__claude_ai_Slack__slack_read_user_profile
---

# Daily Note Review Skill

You are running the daily note review workflow. Follow these four phases exactly.

## Configuration

This skill reads its config from `~/.config/claude-resources/daily.yaml`.

### On startup, ALWAYS do these two things:

**1. Read the config file:**

```bash
cat ~/.config/claude-resources/daily.yaml
```

If the file does not exist, report an error and stop:

```
Error: Config file missing at ~/.config/claude-resources/daily.yaml
Run setup.sh from the claude-resources repo to configure, or create the file manually.
```

**2. Auto-detect Slack identity:**

Call `slack_read_user_profile` with NO arguments (defaults to current authenticated user) and `response_format: "concise"`.

- Extract the **User ID** (e.g. `U07MRTS7CCC`) and **Real Name** from the response.
- Use these as `USER_SLACK_ID` and `USER_NAME` throughout the skill.
- These auto-detected values **override** any `user_slack_id` or `user_name` in the config file.
- If the Slack call fails, fall back to the values in the config file. If those are also missing, report an error and stop.

### Config format

```yaml
# Geekbot
geekbot_dm_channel: DXXXXXXXXXX
geekbot_user_id: UXXXXXXXXXX

# Slack channels to monitor
channels:
  tech: CXXXXXXXXXX
  bugs: CXXXXXXXXXX
  reported_calls: CXXXXXXXXXX
  tech_dev: CXXXXXXXXXX
  team: CXXXXXXXXXX
  jira: CXXXXXXXXXX

# Daily note templates
chores_template:
  - Chore item 1
  - Chore item 2

personal_template:
  - Exercise
  - Read
  - Course
    - Sub-course 1
    - Sub-course 2
```

Note: `user_name` and `user_slack_id` are optional in the config — they are auto-detected from Slack MCP. If present, they serve as fallback values only.

Use these values throughout the skill wherever you see `USER_NAME`, `USER_SLACK_ID`, channel names, or template content.

---

## Phase 1: REVIEW — Find Latest Note & Gather Context

### Step 1.1: Find the latest daily note

1. Use Glob to list all files matching `00-daily/YYYY-MM-DD.md` (pattern: `00-daily/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md`).
2. Sort by filename (lexicographic = chronological for ISO dates). Pick the last one — that's the latest.
3. If no files exist, skip to Phase 3 and create a new file for today using the fresh template. Tell the user "No existing daily notes found — creating a fresh one for today."

### Step 1.2: Read and parse the latest daily note

1. Read the file.
2. Identify these sections by their `### ` headings: Chores, Work, Backlog, Personal, House Work, Journal, Long term buy.
3. For the **Work** and **Backlog** sections, collect all top-level unchecked items (`- [ ]` at the root indent level). An item may have indented subtasks below it — these belong to the parent.

### Step 1.2b: Gather Slack Context

Attempt to pull context from Slack. If any Slack call fails, set a flag `slackAvailable = false` and skip to the fallback in Step 1.3.

**Geekbot DM pull:**
1. Read the `geekbot_dm_channel` from config with `limit: 30`.
2. Find the most recent bot message (from `geekbot_user_id`) that contains "Daily Standup".
3. Parse the sequential Q&A that follows in the thread or channel:
   - The user message immediately after "What have you done since yesterday?" = **Done** list
   - The user message after "What will you do today?" = **Today** list
   - The user message after "Anything blocking your progress?" = **Blockers**
4. Store these as `geekbotDone`, `geekbotToday`, `geekbotBlockers`.
5. If no "Daily Standup" message is found in the last 30 messages, set `geekbotFound = false`.

**Channel search (be thorough — read channels AND search):**

Use BOTH approaches to avoid missing activity:

**A. Read full channel history for the day** using `slack_read_channel` with `oldest` set to start-of-day Unix timestamp. Read each channel listed in the `channels` config section.

**B. Search for the user's messages and mentions** across all channels:
   - `from:<@USER_SLACK_ID> on:{daily-note-date}` — messages the user sent today
   - `<@USER_SLACK_ID> on:{daily-note-date}` — messages mentioning/tagging the user today

**C. Read threads for full context:**
   - For any message in tech or bugs channels where the user participated (sent a message or was tagged), read the full thread using `slack_read_thread` to understand if work was completed, PR was approved, issue was resolved, etc.
   - Look for completion signals: "fixed", "deployed", "merged", "approved", PR links, Jira ticket transitions

**D. Search Jira activity:**
   - Search `USER_NAME` in the jira channel or in bot messages with `transitioned`, `created`, or `assigned` to detect ticket status changes

3. Extract meaningful work activities: PR submissions, bug investigations, technical discussions, code reviews, hotfixes, deployments.
4. Ignore casual messages (greetings, reactions, short acknowledgments).
5. Store as `slackActivities` — a list of `{ description, channel, confidence }`.

**Cross-reference with daily note items:**
- **Tier 1 (high confidence):** Match ticket IDs (e.g. `SAI-XXXX`) between daily note unchecked items and Slack messages/Geekbot Done list.
- **Tier 2 (medium confidence):** Keyword/semantic matching for items without ticket IDs.
- Categorize each unchecked item as: `completed` (evidence found), `still_open` (no evidence), or `new` (in Slack but not in daily note).

### Step 1.3: Work Item Review (Slack-Aware)

**If `slackAvailable = true` and at least one item has Slack evidence:**

Present a pre-filled summary to the user. Include items from BOTH Work and Backlog sections:

```
Based on your Slack activity:

COMPLETED (evidence found):
  [x] TICKET-123 Some task (Geekbot "Done")
  [x] Investigated some issue (#tech discussion)

STILL OPEN (no evidence):
  [ ] improve key points and summary generation
  [ ] Some other task

NEW ACTIVITY (not in daily note):
  + TICKET-456 Fix something (#tech PR)

Is this correct? Reply with adjustments or "yes" to confirm.
```

- If user says "yes" → accept as-is.
- If user provides corrections → apply them.
- NEW ACTIVITY items confirmed by user are added to the completed list.
- User can say "remove [item]" to delete items from the daily note entirely (won't carry over).
- User can provide progress updates on still-open items.

**Fallback — if `slackAvailable = false` or no Slack evidence found at all:**

Revert to original one-by-one Q&A:

For each **top-level unchecked item** in the Work and Backlog sections (skip checked `- [x]` items):

1. Ask the user: **"Did you finish: [task description]?"**
2. Wait for their response before asking the next question.
3. Record which items the user says are done vs. not done.
4. If a parent item is marked done, all its subtasks are also marked done.

If there are no unchecked Work items, tell the user "All work items already checked off!" and skip to the bulk prompt.

### Step 1.4: Bulk Prompt — Reflection, Journal, Planning & Blockers

**Ask all remaining questions in a SINGLE message** so the user can answer in one go:

```
Quick wrap-up:

1. Any wins today?
2. Anything you learned?
3. How was your day? Any thoughts for the journal? (or "skip")
4. What's on your plate for tomorrow?
5. Any blockers?
```

**Geekbot-aware adjustments:**
- If `geekbotFound = true` and `geekbotToday` exists, replace question 4 with:
  **"4. Your Geekbot standup lists these for today: {geekbotToday}. Still accurate, or adjust?"**
- If `geekbotFound = true` and `geekbotBlockers` is "none" or equivalent, replace question 5 with:
  **"5. Any blockers? (Geekbot had 'none' — same?)"**

Store all responses for use in Phase 2 and 3.

---

## Phase 2: UPDATE — Modify Current File

### Step 2.1: Update Work and Backlog item checkboxes

In the latest daily note file:
- Change `- [ ]` to `- [x]` for items the user confirmed as done (and their subtasks).
- Leave `- [ ]` for items the user said are not done.
- **Remove** items the user explicitly asked to remove (don't check them, delete the line entirely).

### Step 2.2: Fill journal section

If the user provided journal content (including wins/learnings/thoughts), replace the content under `### Journal` with the collected journal text. Combine wins, learnings, and thoughts naturally. Format as a simple list or prose — match the user's style.

If the user skipped journal, leave the section unchanged.

### Step 2.3: Journal archiving

Check the `### Journal` section content (after updating):

- If it contains real content (NOT just the placeholder "Write something about the day here..." and NOT empty):
  1. Create the directory `00-daily/journals/` if it doesn't exist (use `mkdir -p`).
  2. Write the journal content to `00-daily/journals/{date}.md` where `{date}` is the date from the latest daily note filename.
  3. Replace the journal section content in the daily note with: `![[journals/{date}]]`

- If the journal is empty or just the placeholder, do nothing.

### Step 2.4: Save the updated file

Write the updated content back to the same file path.

---

## Phase 3: GENERATE — Create Next Day's File

### Step 3.1: Calculate the new date

- Extract the date from the latest daily note filename.
- If that date equals today's date → new date = tomorrow (today + 1 day).
- If that date is before today → new date = today.
- Format as `YYYY-MM-DD`.

### Step 3.2: Build the Standup section

Use the Geekbot three-question format. **Follow these standup style rules:**

- **Done:** Focus on actual development work only
  - Do NOT include PR reviews/approvals (these are routine, not standup-worthy)
  - Do NOT include "created ticket" or "shared pricing" — only actual dev progress
  - Be careful about which day work was done. If something was investigated yesterday and you only followed up today, say "followed up" not "investigated"
  - For ongoing tasks, describe the dev progress (e.g., "done enabling feature X, need to implement in admin") not the admin work around it
- **Today:** List planned development tasks
- **Blockers:** Be specific and technical

```
### Standup
**Done:**
{list completed work items — dev work focus, preserve ticket IDs}

**Today:**
{items from the user's tomorrow planning response}

**Blockers:**
{user's blocker response, or "none" if they said none}
```

If no work items were completed, put "none" under Done.

### Step 3.3: Build sections with carry-over rules

Apply these rules for each section:

**Chores** — FRESH template (always reset):
Use the `chores_template` from the config file to generate the chores section with unchecked checkboxes.

**Work** — CARRY OVER unchecked items + append new plans:
1. Copy all unchecked (`- [ ]`) top-level Work items with their full subtask trees and any annotations (WIP, links, etc.). Preserve tab indentation exactly.
2. Do NOT carry over checked items, removed items, non-checkbox lines (prose, plain list items without checkboxes), or standalone text.
3. Append new items from the user's tomorrow planning as `- [ ] {item}`.

**Backlog** — CARRY OVER unchecked items:
1. Copy all unchecked (`- [ ]`) top-level Backlog items with their full subtask trees.
2. Do NOT carry over checked or removed items.
3. If the Backlog section becomes empty, still include the heading.

**Personal** — FRESH template (always reset):
Use the `personal_template` from the config file to generate the personal section with unchecked checkboxes. Preserve nested items with tab indentation.

**House Work** — CARRY OVER unchecked items:
1. Copy all unchecked top-level House Work items with their full subtask trees.
2. Preserve tab indentation exactly.
3. Skip fully-checked items (parent and all children checked).

**Journal** — FRESH placeholder:
```
### Journal
Write something about the day here...
```

**Long term buy** — CARRY OVER exactly:
1. Copy the entire Long term buy section content as-is to the new file.

### Step 3.4: Assemble and write the new file

Combine sections in this order:
1. Standup
2. Chores
3. Work
4. Backlog
5. Personal
6. House Work
7. Journal
8. Long term buy

Separate each section with a blank line after its content. Use tabs for indentation (never spaces). Write to `00-daily/{new-date}.md`.

### Step 3.5: Completion confirmation

Tell the user:
- Which file was updated (with the changes made)
- Which new file was created
- Whether the journal was archived (and where)
- Summary of items carried over to the new file
- How many items were auto-detected from Slack vs. manually adjusted (if Slack was used)

Then proceed to Phase 3.6 for outstanding issues, then Phase 4 for Geekbot.

### Step 3.6: Outstanding Issues Summary

Search for unresolved mentions — messages where someone tagged the user (via `USER_SLACK_ID`) but the user hasn't replied or given an update yet.

**How to detect:**
1. Search `<@USER_SLACK_ID>` in each monitored channel from the config with `after` set to 3 days ago (to catch recent but not ancient items).
2. For each message that mentions the user, check the thread replies (if any) or subsequent messages in the channel.
3. An issue is **outstanding** if:
   - The user was mentioned/tagged
   - The user has NOT replied in that thread or within a reasonable window after the message
   - The message asks a question, requests action, reports a bug, or assigns a task
4. An issue is **NOT outstanding** if:
   - The user already replied or acknowledged
   - Someone else resolved it
   - It's just an FYI/notification that doesn't need a response (e.g., PR approval notifications, Jira bot assignments)

**Present to user:**
```
OUTSTANDING ISSUES (need your attention):
  1. #channel-name — Someone reported an issue, tagged you for review (2 days ago)
  2. #channel-name — Someone asked about something, no reply yet (1 day ago)

No outstanding issues found. (if none)
```

If there are outstanding items, ask: **"Want to address any of these now, or just keep them noted?"**
- This is informational — don't block the workflow on it.

---

## Phase 4: GEEKBOT — Reply to Daily Standup

### Step 4.1: Check if Geekbot is waiting for a report

1. Read the `geekbot_dm_channel` from config with `limit: 5`.
2. Check the most recent message from the `geekbot_user_id`.
3. **Proceed only if** the most recent Geekbot message is from today AND contains "Daily Standup" or one of the standup questions ("What have you done", "What will you do today", "Anything blocking").
4. If the most recent Geekbot message already says "Good job!" or similar completion → standup already submitted. Tell user: **"Your Geekbot standup is already posted — no need to copy it manually."** Skip this phase.
5. If no Geekbot message from today → standup not triggered yet. Tell user: **"Geekbot hasn't asked for your standup yet today."** Skip this phase.

### Step 4.2: Determine current question state

Read the last few messages to figure out where in the Q&A flow Geekbot is:

- If last Geekbot message contains "What have you done" → needs **Done** reply
- If last Geekbot message contains "What will you do today" → needs **Today** reply
- If last Geekbot message contains "Anything blocking" → needs **Blockers** reply

### Step 4.3: Reply sequentially

Use the **Standup** section from the newly generated daily note file as the source.

**Reply flow (one message at a time):**

1. **Done reply:** Send the items under `**Done:**` from the standup section to the `geekbot_dm_channel`. Format as bullet points with `•` prefix (matching the user's usual Geekbot style). Wait ~3 seconds, then re-read the channel to get Geekbot's next question.

2. **Today reply:** Send the items under `**Today:**` from the standup section. Format as bullet points with `•` prefix. Wait ~3 seconds, then re-read the channel.

3. **Blockers reply:** Send the blockers text (usually "none"). Wait ~3 seconds, then re-read the channel.

4. **Verify completion:** Check that Geekbot responded with "Good job!" or similar. If so, tell the user: **"Geekbot standup submitted successfully!"**

**Important:**
- Always ask the user for confirmation before sending the first reply: **"Ready to submit this to Geekbot? [show the 3 answers]. Say 'yes' to send or adjust."**
- Send each reply as a separate message (not all at once) — Geekbot expects sequential answers.
- If at any point Geekbot doesn't respond with the next question within the re-read, stop and tell the user.

---

## Formatting Rules (apply everywhere)

- Section headings: `###` (H3 level)
- Indentation: **tabs only** (no spaces for nesting)
- Unchecked checkbox: `- [ ]`
- Checked checkbox: `- [x]`
- No trailing whitespace
- One blank line between sections
