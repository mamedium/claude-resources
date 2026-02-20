# Domain Pools

Conductor picks domains based on what changed. Only the holistic agent is always present.

<!-- CUSTOMIZE: Tailor these domains to your codebase's stack and conventions. -->

## Code Review Domains

Pick 2 (quick), 4 (full), or 5 (deep) from this pool:

### Stack-Specific Domains (prefer these when file paths match)

| Domain | Lens | Pick When |
|--------|------|-----------|
| API & Handlers | Correct auth middleware, input validation, operations layer separation (handlers should delegate, not inline business logic), context usage for tenant filtering | `src/api/**`, `*.handler.ts`, `*_router.ts` |
| Database & Schema | Lifecycle timestamps on tables, correct ID types, soft deletes, tenant isolation via orgId, proper indexing, enum patterns | `src/db/schema/**`, `*.schema.ts`, migration files |
| Background Jobs | Queue concurrency limits, retry strategies, typed payloads via Zod, error handlers that respect rate limit headers, database connection inside run function | `src/jobs/**`, `*.task.ts`, queue definitions |
| Webhook Security | Signature verification before processing, Zod validation on bodies, rate limiting, secret management via env/config (never hardcoded) | `src/webhooks/**`, webhook routes, middleware |
| React & Components | Named exports, arrow function components, hook dependency control (manual, not lint-blind), design system tokens over raw colors, file size limits, one component per file | `src/components/**`, `*.tsx` |
| Multi-tenant Safety | Every DB query filters by orgId, permission checks on every endpoint, role-based access, session context for tenant ID (never trust client) | Any handler with DB queries, any new endpoint |

### General Domains (always available)

| Domain | Lens | Pick When |
|--------|------|-----------|
| Holistic | Cross-file consistency, missing changes (tests, types, docs), package boundary violations, production safety, what's good | Always included |
| Types & Data | TypeScript strictness, Zod schema correctness, null/undefined handling, type exports aligned across packages | Any `.ts`/`.tsx` changes |
| Testing | Test coverage for new code paths, test quality (not just existence), mock correctness, edge case coverage | Any PR (check for missing tests) |
| Performance | N+1 queries, unnecessary re-renders, missing indexes, unbounded loops, memory leaks | Database queries, React components, data processing |
| Security | Auth bypass, injection vectors, secret exposure, CORS, rate limiting, input sanitization | Auth changes, API endpoints, user input handling |
| Regression Risk | Caller analysis, test coverage verification, implicit contract changes, rollback safety | Deep mode only |

## Domain Selection Rules

1. **Always include Holistic** - it catches cross-cutting concerns other domains miss
2. **Match by file path first** - if the diff touches `src/db/schema/`, include Database & Schema
3. **Include Types & Data for any TypeScript changes** - type issues are the most common false negatives
4. **Include Testing for any PR** - check if new code paths have tests, even if no test files changed
5. **Quick mode:** Holistic + 1 best-match domain (2 total)
6. **Full mode:** Holistic + 3 best-match domains (4 total)
7. **Deep mode:** Holistic + 3 domains + Regression Risk (5 total)
