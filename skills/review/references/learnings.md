# Review Skill Learnings

Accumulated dismissal patterns from depth passes. When a pattern appears 3+ times, promote to the relevant domain's breadth prompt.

## Promoted Patterns

(None yet - patterns graduate here after 3+ occurrences)

---

## How to Use This File

After each review, record dismissed/downgraded findings here with the pattern that caused the false positive. When a pattern appears 3+ times across different reviews, promote it:

1. Add it to the relevant breadth agent's "known false positives" section
2. Move it from "Emerging" to "Promoted Patterns" above

### Entry Format

```
## YYYY-MM-DD - PR #NNN (description)

**X breadth -> Y confirmed, Z dismissed, W downgraded**

### Dismissed (Z)
- **Category:** Reason for dismissal (xN if repeated)

### Downgraded (W)
- **Category:** Original severity -> New severity - reason

### Patterns Emerging
- **Pattern name (Nth occurrence):** Description of the false positive pattern
```

### Common False Positive Patterns to Watch For

- **Structured output concerns:** When code uses schema-enforced structured output (e.g. `generateObject()`), prompt-level schema/structure concerns are usually false positives
- **Framework behaviour assumptions:** Breadth agents reasoning about SDK/framework behaviour from diff alone without reading source
- **Pre-existing issues on cleanup PRs:** Deletion/refactor PRs trigger findings in untouched files tangentially related to deleted code
- **Wrong-branch depth reads:** When reviewing external PRs (not current branch), depth agents may read the checked-out branch on disk instead of the PR branch
- **Severity inflation:** Breadth agents tend to mark findings as P1 when P2 is more appropriate. Depth pass should recalibrate.
