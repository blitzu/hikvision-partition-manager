# Architecture

**Analysis Date:** 2025-02-24

## Pattern Overview

**Overall:** N-Tier Architecture with decoupled Frontend (React) and Backend (Node.js/Express) communicating via REST API.

**Key Characteristics:**
- **Separation of Concerns:** Distinct separation between UI, API handling, and business logic (services).
- **Service-Oriented Backend:** Backend logic is encapsulated in specialized services (ANAF, Storage, Backup, Notifications).
- **Multi-tenant Isolation:** Data access is restricted by firm ownership and user associations.
- **Event-Driven Notifications:** Real-time updates via WebSockets and Web Push.

## Layers

**Frontend (Presentation):**
- Purpose: Provides the user interface for managing firms and invoices.
- Location: `frontend/src`
- Contains: React components, hooks, contexts, and API services.
- Depends on: Backend API, Material UI, React Router.
- Used by: End users.

**API Layer (Backend):**
- Purpose: Handles HTTP requests, authentication, and routing.
- Location: `backend/src/controllers`, `backend/src/routes`
- Contains: Express routes and controllers.
- Depends on: Backend Services, Middleware.
- Used by: Frontend application.

**Service Layer (Business Logic):**
- Purpose: Implements core business logic and external integrations.
- Location: `backend/src/services`
- Contains: Specialized classes for ANAF API, file storage, job scheduling, and notifications.
- Depends on: Prisma (Database), External APIs (ANAF, Stripe, B2).
- Used by: Backend Controllers and Schedulers.

**Data Access Layer:**
- Purpose: Manages database interactions and schema.
- Location: `backend/prisma`, `backend/src/config/database.ts`
- Contains: Prisma schema and client configuration.
- Depends on: PostgreSQL.
- Used by: Backend Services and Controllers.

## Data Flow

**Invoice Synchronization:**

1. **Trigger:** `DownloadScheduler` (`backend/src/services/scheduler/DownloadScheduler.ts`) runs on a cron schedule or is triggered manually via `DownloadController`.
2. **Fetch List:** `AnafApiClient` (`backend/src/services/anaf/AnafApiClient.ts`) queries the ANAF API for a list of available invoices for a given firm.
3. **Download & Process:** For new invoices, `DownloadWorker` downloads the ZIP file.
4. **Storage:** `FileStorageService` (`backend/src/services/storage/FileStorageService.ts`) saves the ZIP and extracts XML content to the local filesystem.
5. **Persistence:** Invoice metadata and file paths are saved to the database via Prisma.
6. **Notification:** `WebSocketServer` or `PushNotificationService` (`backend/src/services/notifications/`) notifies the user.
7. **Backup:** `BackupWorker` (`backend/src/services/backup/BackupWorker.ts`) uploads new files to Backblaze B2 for redundancy.

**State Management:**
- **Backend:** Stateless API with JWT-based authentication. Session state is managed in the database for tracking active logins.
- **Frontend:** React Context (`frontend/src/contexts/AuthContext.tsx`, `frontend/src/contexts/NotificationContext.tsx`) manages global application state like authentication and notifications.

## Key Abstractions

**Service Interface:**
- Purpose: Encapsulates complex logic for external integrations.
- Examples: `AnafApiClient.ts`, `StripeService.ts`, `B2Service.ts`.
- Pattern: Service Pattern.

**Tenant Isolation:**
- Purpose: Ensures users only access data they are authorized to see.
- Examples: `backend/src/utils/tenant.ts` (functions like `getUserFirmIds` and `checkFirmAccess`).
- Pattern: Middleware/Utility-based filtering.

## Entry Points

**Backend API:**
- Location: `backend/src/server.ts`
- Triggers: HTTP requests.
- Responsibilities: Server initialization, middleware registration, database connection, and service startup.

**Frontend App:**
- Location: `frontend/src/main.tsx`
- Triggers: Browser page load.
- Responsibilities: React root mounting, context providers initialization.

**Download Worker:**
- Location: `backend/src/services/scheduler/DownloadWorker.ts`
- Triggers: Triggered by `DownloadScheduler`.
- Responsibilities: Executing the multi-step process of downloading and storing invoices.

## Error Handling

**Strategy:** Centralized error handling using middleware.

**Patterns:**
- **Backend Middleware:** `backend/src/middleware/errorHandler.ts` catches all unhandled exceptions and returns structured JSON errors.
- **Frontend Boundary:** `frontend/src/components/ErrorBoundary.tsx` catches React rendering errors and displays a fallback UI.

## Cross-Cutting Concerns

**Logging:** Handled by a custom logger (`backend/src/utils/logger.ts`) using Winston, providing levels (debug, info, warn, error).
**Validation:** Request body and parameter validation using middleware (`backend/src/middleware/validation.ts`) and Zod (implied by typical TS patterns).
**Authentication:** JWT-based authentication enforced via `backend/src/middleware/auth.ts`.
**Audit:** Every API request is logged for auditing purposes via `backend/src/middleware/audit.ts`.

---

*Architecture analysis: 2025-02-24*
