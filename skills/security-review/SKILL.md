---
name: security-review
description: Security review checklist - OWASP Top 10 adapted for modern TypeScript/Python web stacks
allowed-tools: Read, Grep, Glob, Bash
---

# Security Review

Comprehensive security checklist for modern full-stack apps. The examples assume a TypeScript-first stack (Next.js / tRPC-style API layer, an ORM, a cloud provider) with some Python services - **adapt each item to your actual stack**; the categories apply everywhere.

<!-- CUSTOMIZE: replace the example tools below (Zod, Drizzle, NextAuth, Stripe, etc.) with your stack's equivalents. The checklist structure stays the same. -->

## When to Activate
- Implementing authentication or authorization
- Handling user input (forms, API endpoints, file uploads)
- Creating API endpoints
- Working with secrets or credentials
- Handling payment/billing integrations
- Processing sensitive data (PII, health data, financial)
- Creating webhook receivers
- Modifying cloud infrastructure (IAM, serverless functions, networking)

## Security Checklist

### 1. Secrets Management
- [ ] No hardcoded secrets (API keys, tokens, connection strings)
- [ ] Secrets via a secrets manager (e.g. Infisical, AWS Secrets Manager, Doppler) - not .env files in production
- [ ] Secrets validated at startup (fail fast if missing)
- [ ] .env and .env.local in .gitignore
- [ ] Different secrets per environment (dev/staging/prod)

### 2. Input Validation
- [ ] All API inputs validated with a schema library (e.g. Zod, Pydantic)
- [ ] File uploads: validate content-type, size limits, scan for malicious content
- [ ] URL parameters: validate format, prevent path traversal
- [ ] AI/LLM outputs: validate with a schema, prefer `.nullable()` over `.optional()` so missing fields fail loudly

```typescript
// GOOD: schema-validated API input (Zod example)
export const createItemInput = z.object({
  name: z.string().min(1).max(255),
  orgId: z.string().uuid(),
  email: z.string().email().optional(),
});
```

### 3. SQL Injection Prevention
- [ ] ALL queries through an ORM / query builder (parameterized by default)
- [ ] NEVER use raw SQL string concatenation
- [ ] If raw SQL is needed, use your ORM's tagged-template / parameter-binding escape hatch

```typescript
// GOOD: parameterized (Drizzle example - same idea in Prisma, Kysely, SQLAlchemy)
const users = await db.select().from(usersTable).where(eq(usersTable.orgId, orgId));

// BAD: string concatenation
const users = await db.execute(`SELECT * FROM users WHERE org_id = '${orgId}'`);
```

### 4. Authentication & Authorization
- [ ] Session validation on every protected route (e.g. NextAuth.js, Lucia, your auth middleware)
- [ ] API middleware enforces auth (protected procedures/routes by default, public as the exception)
- [ ] Multi-tenant apps: EVERY query filters by tenant/org ID - treat misses as critical
- [ ] Role checks before destructive operations
- [ ] API key validation for external endpoints
- [ ] Webhook signature verification (Stripe, Twilio, GitHub, etc.)

### 5. XSS Prevention
- [ ] React (and similar frameworks) auto-escape by default - avoid `dangerouslySetInnerHTML`
- [ ] If rendering user content as HTML, sanitize with DOMPurify or equivalent
- [ ] CSP headers configured (framework middleware or CDN)
- [ ] Embedded widgets: scoped CSS, no global style injection

### 6. CSRF Protection
- [ ] CSRF tokens on session-authenticated form posts
- [ ] Mutations via POST (not GET)
- [ ] SameSite=Lax (or Strict) on session cookies
- [ ] Custom headers on API requests from embedded widgets

### 7. Rate Limiting
- [ ] Gateway/edge throttling configured
- [ ] Application-level rate limiting on sensitive endpoints (auth, password reset)
- [ ] Webhook endpoints: validate source + rate limit
- [ ] Public/widget endpoints: per-origin rate limiting

### 8. Sensitive Data Exposure
- [ ] Error messages: generic to user, detailed to logs (error tracking / observability platform)
- [ ] API responses: never include internal IDs, stack traces, or DB errors
- [ ] Logging: sanitize PII before shipping logs to third parties
- [ ] Object storage uploads: encryption for sensitive files, never presign public URLs
- [ ] Caches (Redis etc.): TTL on sensitive cached data, don't cache PII

### 9. Dependency Security
- [ ] Audit clean (`pnpm audit` / `npm audit` / `pip-audit` - no critical/high vulnerabilities)
- [ ] Lock files committed
- [ ] No wildcard versions in package manifests
- [ ] Review new dependencies before adding

### 10. Infrastructure Security (cloud)
- [ ] Serverless functions / services: least-privilege IAM roles
- [ ] API gateway: auth on all routes (except deliberately public webhooks)
- [ ] CDN: verified headers between CDN and origin
- [ ] Queues: message validation, dead letter queue for failed messages
- [ ] Secrets: managed secret resources, not env vars in plain text
- [ ] Networking: private subnets for internal services

## Severity Levels
- **CRITICAL**: Blocks merge - secrets exposure, injection, auth bypass, data breach risk
- **HIGH**: Should fix before merge - missing validation, weak auth, unencrypted sensitive data
- **MEDIUM**: Track as follow-up - defense-in-depth gaps, minor exposure risks

## Quick Commands
```bash
pnpm audit                    # Check npm vulnerabilities
ruff check --select S .       # Python security rules (bandit-style)
grep -r "dangerouslySetInnerHTML" --include="*.tsx"  # XSS risk
grep -r "sql\`" --include="*.ts"  # Raw SQL usage
```
