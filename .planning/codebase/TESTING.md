# Testing Patterns

**Analysis Date:** 2025-03-05

## Test Framework

**Runner:**
- **Jest** 29.7.0 (Backend)
- Config: `backend/jest.config.js`
- Preset: `ts-jest`

**Assertion Library:**
- **Jest Expect** (built-in)

**Run Commands:**
```bash
# Backend
npm run test           # Run all tests
npm run test:watch     # Watch mode
```

## Test File Organization

**Location:**
- Separate directory: `backend/src/__tests__`
- Configuration `roots: ['<rootDir>/src']` in `jest.config.js`

**Naming:**
- Pattern: `*.test.ts` or `*.spec.ts` (e.g., `backend/src/__tests__/crypto.test.ts`, `backend/src/__tests__/anaf.config.test.ts`).

**Structure:**
```
backend/src/
  __tests__/
    setup.ts           # Global test setup
    *.test.ts          # Logic and utility tests
```

## Test Structure

**Suite Organization:**
```typescript
import { someFunction } from '../utils/someFile';

describe('Some Utility', () => {
  beforeAll(() => {
    // Setup logic (e.g., env vars)
  });

  describe('someFunction', () => {
    it('should perform correctly under standard conditions', () => {
      const result = someFunction('input');
      expect(result).toBe('expected output');
    });

    it('should handle edge cases properly', () => {
      expect(() => someFunction('')).toThrow('Invalid input');
    });
  });
});
```

**Patterns:**
- **Setup pattern:** `beforeAll()` or `beforeEach()` for initialization.
- **Teardown pattern:** `afterAll()` or `afterEach()` for cleanup.
- **Assertion pattern:** Use `expect(actual).toBe(expected)`, `toEqual()`, `toThrow()`, `toHaveLength()`.

## Mocking

**Framework:** **Jest** built-in mocking (`jest.fn()`, `jest.mock()`).

**Patterns:**
```typescript
// Example from setup.ts
const originalConsoleError = console.error;
beforeAll(() => {
  console.error = jest.fn(); // Mocking console.error to reduce noise
});

afterAll(() => {
  console.error = originalConsoleError; // Restore after all tests
});
```

**What to Mock:**
- Environment variables (`process.env`).
- Database clients (Prisma) in unit tests (via `jest.mock`).
- External APIs (ANAF, Stripe, etc.).
- Global objects like `console` or `window`.

**What NOT to Mock:**
- Internal pure logic and utilities (e.g., `crypto.ts`).
- Configuration files that don't depend on external services.

## Fixtures and Factories

**Test Data:**
- Manual construction of test data within `describe` or `it` blocks.
- Environment variable mocking in `backend/src/__tests__/setup.ts`.

**Location:**
- Injected in `setup.ts` or directly in the test files.

## Coverage

**Requirements:**
- Configured in `backend/jest.config.js`.
- Excludes: `.d.ts` files, tests, index files.

**View Coverage:**
```bash
npx jest --coverage
```
Coverage reports are generated in `backend/coverage/` as `text`, `lcov`, and `html`.

## Test Types

**Unit Tests:**
- Backend: Utilities (`crypto.ts`), Configuration logic (`anaf.ts`), Input validation.
- Scope: High, focusing on critical logic and security.

**Integration Tests:**
- Not extensively detected, but infrastructure exists for them (e.g., `setup.ts` with DB URL).

**E2E Tests:**
- Not currently present in the codebase.

## Common Patterns

**Async Testing:**
- Use `async/await` in test blocks.
- `jest.setTimeout(10000)` set in `setup.ts` to accommodate network-related or complex async operations.

**Error Testing:**
- Use `expect(() => functionThatThrows()).toThrow()` for synchronous calls.
- Use `await expect(asyncFunction()).rejects.toThrow()` for asynchronous calls.

---

*Testing analysis: 2025-03-05*
