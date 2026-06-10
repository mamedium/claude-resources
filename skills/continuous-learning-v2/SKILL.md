---
name: continuous-learning-v2
description: Project-scoped instinct system - observe patterns, build confidence, evolve into skills
allowed-tools: Read, Write, Glob, Grep, Bash
---

# Continuous Learning v2

Observe session patterns, extract reusable "instincts" (trigger-action pairs), and evolve them into skills, commands, or agent improvements over time.

## When to Activate
- End of session - review patterns worth capturing
- User says "learn this", "remember this pattern", "extract instincts"
- After resolving a non-trivial bug or implementing a complex feature
- When the same pattern appears for the 2nd+ time in a session

<!-- CUSTOMIZE: if you have a session-closing skill (e.g. /exit or /save-session), wire this skill to fire from it so instincts are captured automatically. -->

## Core Concept: Instincts

An instinct is an atomic learned behaviour:

```yaml
id: instinct-<hash>
trigger: "When [specific condition]"
action: "Then [specific response]"
confidence: 0.3-0.9
evidence:
  - "2026-04-02: Fixed React Native build by rebuilding dev client after adding native dep"
scope: project | global
project: my-app  # if project-scoped
created: 2026-04-02
updated: 2026-04-02
```

### Confidence Levels
- **0.3** (tentative): Seen once, might be coincidence
- **0.5** (probable): Seen twice or confirmed by user
- **0.7** (confident): Consistent pattern across multiple sessions
- **0.9** (near-certain): Well-established, never contradicted

### Confidence Changes
- Pattern confirmed: +0.1
- Pattern seen in new context: +0.1
- Pattern contradicted: -0.2
- User explicitly corrects: reset to 0.3 with new action

## Storage

```
~/.claude/instincts/
  global/                    # Cross-project instincts
    instinct-a1b2c3.yaml
  projects/
    my-app/                  # Project-scoped instincts
      instinct-d4e5f6.yaml
    side-project/
      instinct-g7h8i9.yaml
```

### Project Detection
1. Check git remote URL (hash it for privacy)
2. Fallback: use git toplevel directory name
3. If no git: use current working directory name

## Scope Decision Guide

| Pattern | Scope | Example |
|---------|-------|---------|
| Language idiom | global | "Always use Zod .nullable() for AI outputs" |
| Framework pattern | global | "React 19 useOptimistic needs fallback" |
| Project convention | project | "This project uses orgId for tenant isolation" |
| Team preference | project | "This team prefers small commits" |
| Universal principle | global | "Run tests before and after refactoring" |

## How to Capture Instincts

### During Session (lightweight)
When you notice a repeating pattern or learn something new:

1. Check if an instinct already exists: `ls ~/.claude/instincts/{global,projects/<project>}/`
2. If exists: update confidence (+0.1) and add evidence
3. If new: create with confidence 0.3 and one evidence entry

### At Session End (comprehensive)
Review the session for:
- Error resolution patterns (what broke, what fixed it)
- User corrections (explicit "no, do it this way")
- Successful approaches (what worked well)
- Repeated actions (same pattern 2+ times)

## Promotion Criteria

An instinct can be promoted when:
- **To global**: Seen in 2+ projects, average confidence >= 0.7
- **To skill**: 3+ related instincts form a coherent workflow
- **To rule**: Universal, high-confidence (0.9), always applicable

## Commands

- `/instinct-status` - List all instincts for current project + globals, sorted by confidence
- `/instinct-export` - Export instincts as YAML for sharing
- `/instinct-import <file>` - Import instincts from YAML file
- `/evolve` - Analyze instincts, suggest clustering into skills/commands

<!-- CUSTOMIZE: these sub-commands are conventions, not separate skill files. Invoke them as natural-language requests ("show instinct status") or scaffold them as thin slash commands that point back at this skill. -->

## Complementary Systems

If you also keep human-readable notes (TIL files, decision logs, a notes vault), treat the two layers as complementary:

- **Notes / artifacts** = human-readable knowledge for future reference
- **Instincts** = machine-readable patterns for agent behaviour

Both should fire at session end.

## Anti-Patterns
- Don't capture trivial patterns ("use semicolons in TypeScript")
- Don't capture one-time fixes (typos, config mistakes)
- Don't capture what's already in CLAUDE.md or project rules
- Don't over-capture: 5-10 instincts per project is ideal, not 50
