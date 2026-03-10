# Coding Conventions

**Analysis Date:** 2025-03-05

## Naming Patterns

**Files:**
- **Backend Controllers/Services/Classes:** `PascalCase.ts` (e.g., `src/controllers/AuthController.ts`, `src/services/scheduler/DownloadScheduler.ts`).
- **Backend Routes/Middleware/Utils/Config:** `camelCase.ts` (e.g., `src/routes/auth.ts`, `src/middleware/auth.ts`, `src/utils/logger.ts`, `src/config/database.ts`).
- **Frontend Components:** `PascalCase.tsx` (e.g., `src/components/ErrorBoundary.tsx`).
- **Frontend Pages:** `PascalCase.tsx` (e.g., `src/pages/DashboardPage.tsx`).
- **Frontend Hooks:** `camelCase.ts` (e.g., `src/hooks/usePushNotifications.ts`).
- **Frontend Services/Contexts:** `PascalCase.tsx` or `camelCase.ts` (e.g., `src/contexts/AuthContext.tsx`, `src/services/api.ts`).
- **Types/Interfaces:** Often co-located or in `types/` with `camelCase.types.ts` (e.g., `src/types/anaf.types.ts`).

**Functions:**
- Use `camelCase` for all functions (e.g., `startAnafAuth`, `getAuthStatus`, `encryptString`).
- Use descriptive names starting with verbs (e.g., `get`, `set`, `handle`, `create`).

**Variables:**
- Use `camelCase` for local variables and properties (e.g., `firmId`, `accessToken`, `prisma`).
- Use `UPPER_SNAKE_CASE` for constants (e.g., `STATE_TTL`, `DELEGATE_TOKEN_TTL`, `REQUIRED_ENV`).

**Types:**
- Use `PascalCase` for Interfaces, Types, and Classes (e.g., `AppError`, `PushNotificationsHook`, `Firm`).
- Prefix interfaces with `I` is NOT practiced; use direct names.

## Code Style

**Formatting:**
- **Backend:** `prettier` is used. Configuration is expected to follow defaults or be defined in `package.json`. Command: `npm run format`.
- **Frontend:** Formatting is handled via `eslint` or `vite` defaults.

**Linting:**
- **Backend:** `eslint` with `@typescript-eslint` plugin. Command: `npm run lint`.
- **Frontend:** `eslint` is used. Command: `npm run lint`.

## Import Organization

**Order (Backend):**
1. Built-in Node modules (`express`, `path`, `fs`, `crypto`).
2. Third-party libraries (`axios`, `dotenv`, `cors`).
3. Internal config (`../config/database`).
4. Services/Classes (`../services/scheduler/DownloadScheduler`).
5. Routes (`../routes/firms`).
6. Middleware (`../middleware/auth`).
7. Utils (`../utils/logger`).

**Order (Frontend):**
1. React core (`react`, `react-dom`).
2. Third-party libraries (`react-router-dom`, `@mui/material`, `axios`).
3. Layouts/Components.
4. Contexts/Hooks.
5. Services/API.
6. Assets/CSS.

## Error Handling

**Backend Patterns:**
- Use custom `AppError` class `backend/src/middleware/errorHandler.ts` for operational errors.
- Throw specialized errors like `NotFoundError`, `ValidationError`, `UnauthorizedError`.
- Use `next(error)` in Express controllers to pass errors to the global error handler.
- Global error handler `backend/src/middleware/errorHandler.ts` handles Prisma errors (e.g., P2002 for unique constraint violations).

**Frontend Patterns:**
- Use `ErrorBoundary` component `frontend/src/components/ErrorBoundary.tsx` to catch rendering errors.
- Global `window.onerror` and `window.onunhandledrejection` in `frontend/src/main.tsx` for uncaught errors and promise rejections.
- Use `axios` interceptors in `frontend/src/services/api.ts` for global 401 handling (redirect to login).

## Logging

**Framework:** `winston` for backend; `console` for frontend.

**Patterns (Backend):**
- Use `logger` from `backend/src/utils/logger.ts`.
- Use child loggers for specific modules (e.g., `authLogger`, `anafLogger`).
- Logs are rotated daily in `logs/` directory (`error-%DATE%.log`, `combined-%DATE%.log`).
- Logs include metadata (e.g., `firmId`, `service`).

**Patterns (Frontend):**
- Use `console.log` or `console.error` with specific prefixes for easy filtering (e.g., `[APP]`, `[SW]`, `[Push]`).

## Module Design

**Backend:**
- **Controllers:** Handle HTTP requests, call services, and return responses.
- **Services:** Contain business logic, interact with DB/External APIs.
- **Routes:** Define endpoints and attach middleware/controllers.
- **Route Factories:** Use functions like `createFirmRoutes(prisma)` to inject dependencies.

**Frontend:**
- **Hooks:** Encapsulate logic and side effects (e.g., `usePushNotifications`).
- **Contexts:** Handle global state (Auth, Notifications, Theme).
- **Components:** Functional components with Hooks.
- **Services:** Axios instance and API call wrappers.

---

*Convention analysis: 2025-03-05*
