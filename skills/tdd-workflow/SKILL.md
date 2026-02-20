---
name: tdd-workflow
description: Test-Driven Development workflow - RED-GREEN-REFACTOR cycle with Vitest and pytest
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# TDD Workflow

Test-first development enforcing the RED-GREEN-REFACTOR cycle.

## When to Activate
- Writing new features or functions
- Fixing bugs (write test that reproduces bug first)
- Refactoring existing code (ensure tests exist before changing)
- User says "TDD", "test first", "write tests"

## Core Principles
1. **Tests BEFORE code** - always write the failing test first
2. **Minimum 80% coverage** (100% for critical paths: auth, payments, data mutations)
3. **Three test types required**: unit, integration, E2E
4. **Git checkpoints**: commit after RED, GREEN, and REFACTOR stages

## TDD Cycle

### Step 1: Define User Journey
Map out what the feature should do from the user's perspective.

### Step 2: Write Test Cases (RED)
```bash
# TypeScript (Vitest)
pnpm vitest run path/to/test.test.ts

# Python (pytest)
pytest tests/test_feature.py -v
```

Write tests that FAIL because the implementation doesn't exist yet. Verify the test fails for the RIGHT reason (not a syntax error).

### Step 3: Run Tests - Verify RED
```bash
pnpm vitest run --reporter=verbose  # Should see FAIL
pytest -v                            # Should see FAILED
```
Commit: `test: add failing tests for <feature>`

### Step 4: Write Minimal Implementation (GREEN)
Write just enough code to make tests pass. No optimization, no edge cases yet.

### Step 5: Run Tests - Verify GREEN
```bash
pnpm vitest run  # Should see PASS
pytest            # Should see passed
```
Commit: `feat: implement <feature> (green)`

### Step 6: Refactor
Improve code quality while keeping tests green. Run tests after every change.
Commit: `refactor: clean up <feature>`

### Step 7: Verify Coverage
```bash
pnpm vitest run --coverage  # Check coverage report
pytest --cov=src --cov-report=term-missing
```

## Framework Patterns

### Vitest (TypeScript)
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('FeatureName', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should handle the happy path', () => {
    // Arrange
    const input = { /* ... */ };
    // Act
    const result = featureFunction(input);
    // Assert
    expect(result).toEqual(expected);
  });

  it('should handle error case', () => {
    expect(() => featureFunction(null)).toThrow();
  });
});
```

### pytest (Python)
```python
import pytest
from unittest.mock import AsyncMock, patch

class TestFeature:
    def test_happy_path(self):
        result = feature_function(valid_input)
        assert result == expected

    def test_error_case(self):
        with pytest.raises(ValueError):
            feature_function(invalid_input)

    @pytest.mark.asyncio
    async def test_async_handler(self):
        mock_ctx = AsyncMock()
        result = await async_handler(mock_ctx)
        assert result is not None
```

### tRPC Procedure Testing
```typescript
import { createCaller } from '~/server/trpc';

const caller = createCaller({ session: mockSession, db: testDb });
const result = await caller.feature.getById({ id: '123' });
expect(result).toMatchObject({ id: '123' });
```

### Playwright E2E
```typescript
import { test, expect } from '@playwright/test';

test('user can complete feature flow', async ({ page }) => {
  await page.goto('/feature');
  await page.getByTestId('input').fill('value');
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.getByText('Success')).toBeVisible();
});
```

## Edge Cases to Always Test
- null/undefined/empty string inputs
- Empty arrays and objects
- Boundary values (0, -1, MAX_SAFE_INTEGER)
- Error paths and rejection handling
- Race conditions in async code
- Large datasets (pagination boundaries)
- Special characters in strings
- Concurrent access patterns

## Anti-Patterns
- Testing implementation details (private methods, internal state)
- Tests that depend on execution order
- Mocking everything (use real DB in integration tests via Docker)
- Snapshot tests for business logic
- Tests without assertions
- Tests that pass when the feature is broken

## Quick Reference
| Command | Purpose |
|---------|---------|
| `pnpm vitest run` | Run all TS tests |
| `pnpm vitest run --watch` | Watch mode |
| `pnpm vitest run --coverage` | Coverage report |
| `pnpm vitest run --reporter=verbose` | Detailed output |
| `pytest -v` | Run all Python tests |
| `pytest --cov=src` | Python coverage |
| `pnpm test:e2e` | Playwright E2E |
