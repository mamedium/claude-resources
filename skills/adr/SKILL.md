---
name: adr
description: Architecture Decision Records - capture decisions with context, alternatives, and consequences
allowed-tools: Read, Write, Glob
---

# Architecture Decision Records (ADR)

Capture architectural decisions with context, alternatives considered, and consequences.

## When to Activate
- Choosing between 2+ valid technical approaches
- Making infrastructure decisions (new service, database change, provider switch)
- Changing core patterns (state management, API design, auth flow)
- User explicitly says "ADR this", "document this decision", "log this decision"

## When NOT to Use
- Trivial choices (naming a variable, formatting)
- Decisions already documented elsewhere (Linear ticket has full context)
- Reversible decisions with low impact

## ADR Template

```markdown
# ADR-NNN: <Decision Title>

**Date**: YYYY-MM-DD
**Status**: proposed | accepted | deprecated | superseded by ADR-NNN
**Deciders**: <who was involved>

## Context
<2-5 sentences: What situation prompted this decision? What constraints exist?>

## Decision
<1-3 sentences: What was decided?>

## Alternatives Considered

### Option A: <name>
- **Pros**: ...
- **Cons**: ...
- **Why not**: <specific reason this was rejected>

### Option B: <name> (chosen)
- **Pros**: ...
- **Cons**: ...
- **Why chosen**: <specific reason>

### Option C: <name>
- **Pros**: ...
- **Cons**: ...
- **Why not**: <specific reason>

## Consequences

### Positive
- <what improves>

### Negative
- <what gets harder or worse>

### Risks
- <what could go wrong>

## Revisit When
<Under what conditions should this decision be reconsidered?>
```

## Storage Location
- Monorepo decisions: `docs/decisions/` in the project root
- Learning artifacts: `$OBSIDIAN_VAULT/03-work/<project>/<TICKET-ID>/learnings/decision-<topic>.md`
- Number ADRs sequentially (ADR-001, ADR-002, etc.)
- Maintain an index file: `docs/decisions/README.md`

## What Makes a Good ADR
- **Be specific**: "We chose tRPC over REST because..." not "We chose the best option"
- **Record the WHY**: The decision itself is obvious from the code; the reasoning is what gets lost
- **Include rejected alternatives**: Future developers need to know what was considered
- **State consequences honestly**: Every choice has trade-offs
- **Keep it short**: 1 page max. If longer, the decision is too big - split it

## Decision Detection Signals
- "Should we use X or Y?"
- "I'm torn between..."
- "The trade-off here is..."
- "We could do this several ways..."
- Multiple valid approaches discussed in conversation
