# Commit Message Examples

This reference shows commit message patterns to ensure consistency.

## Feature Commits (`feat`)

```
feat(api): add webhook signature verification for incoming events [ENG-123]
feat(dashboard): implement user settings page with role management [ENG-456]
feat(agent): add retry logic with exponential backoff [ENG-789]
feat: booking confirmation email templates [ENG-101]
```

**Pattern:** `feat(scope): add/implement/enhance <thing> [TICKET-ID]`

## Fix Commits (`fix`)

```
fix(api): prevent duplicate webhook delivery on retry [ENG-234]
fix(agent): clear existing background audio before new playback [ENG-567]
fix(dashboard): resolve infinite re-render in settings form [ENG-890]
```

**Pattern:** `fix(scope): fix/correct/resolve <issue> [TICKET-ID]`

## Refactor Commits (`refactor`)

```
refactor(api): extract validation logic into shared middleware [ENG-345]
refactor(agent): streamline response handling for consistency [ENG-678]
refactor: remove legacy config and simplify service layer [ENG-901]
```

**Pattern:** `refactor(scope): update/streamline/enhance/improve <thing> [TICKET-ID]`

## Multiple Tickets

When changes relate to multiple tickets:
```
refactor(agent): improvements in data capture workflow [ENG-123][ENG-456]
```

## Scope Usage

| Scope | Example Files |
|-------|---------------|
| `api` | src/api/*.ts, src/routes/*.ts |
| `dashboard` | src/dashboard/*.tsx |
| `agent` | src/agent/*.py |
| `db` | src/db/*.ts, schema files |
| *(none)* | Multiple areas, general changes |

## Action Verbs (Imperative Mood)

**Use these:**
- add, implement, create
- fix, correct, resolve
- update, modify, change
- remove, delete, drop
- refactor, restructure, reorganize
- enhance, improve, optimize
- streamline, simplify

**NOT these:**
- added, implemented, created (past tense)
- adding, implementing (gerund)
- adds, implements (third person)

## Length Guidelines

- **Maximum:** 72 characters total
- **Ideal:** 50-60 characters
- **Minimum:** Be descriptive enough to understand the change

## Ticket Number Extraction

Branch: `eng-123-add-webhook-support`
Extract: `ENG-123`

Branch: `feature/eng-456-new-feature`
Extract: `ENG-456`

Branch: `dev` or `main`
Extract: Check commits or ask user
