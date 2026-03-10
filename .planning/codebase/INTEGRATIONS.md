# External Integrations

**Analysis Date:** 2025-02-25

## APIs & External Services

**ANAF API (e-Factura):**
- Service: Romanian ANAF (Agency for Fiscal Administration) API for e-factura management.
  - SDK/Client: `backend/src/services/anaf/AnafApiClient.ts` (custom implementation using `axios`).
  - Auth: OAuth2 implementation in `backend/src/services/auth/AnafOAuthService.ts`.
  - Config: `backend/src/config/anaf.ts`.
  - Env Vars: `ANAF_OAUTH_CLIENT_ID`, `ANAF_OAUTH_CLIENT_SECRET`, `ANAF_OAUTH_REDIRECT_URI`.

**Stripe:**
- Service: Payment processing and subscription management.
  - SDK/Client: `stripe` package, used in `backend/src/services/stripe/StripeService.ts`.
  - Webhooks: `backend/src/services/stripe/StripeWebhookHandler.ts` and `backend/src/routes/stripe.ts`.
  - Auth: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.

**Web Push:**
- Service: Browser-based push notifications.
  - SDK/Client: `web-push` package, used in `backend/src/services/notifications/PushNotificationService.ts`.
  - Auth: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`.

## Data Storage

**Databases:**
- PostgreSQL
  - Connection: `DATABASE_URL`.
  - Client: Prisma ORM, configured in `backend/prisma/schema.prisma` and `backend/src/config/database.ts`.

**File Storage:**
- Backblaze B2 (Primary Backup)
  - Service: `backblaze-b2` for long-term storage and durability of downloaded invoices.
  - Implementation: `backend/src/services/backup/B2Service.ts`.
  - Env Vars: `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_ID`.
- Local Filesystem (Primary Storage)
  - Path: `backend/src/services/storage/FileStorageService.ts` (defaults to `./storage/invoices`).

**Caching:**
- Redis
  - Service: Caching and task queuing via Bull.
  - Client: `ioredis` in `backend/src/config/redis.ts`.
  - Env Var: `REDIS_URL`.

## Authentication & Identity

**Auth Provider:**
- Custom (JWT-based)
  - Implementation: `backend/src/controllers/AuthController.ts` and `backend/src/services/auth/AuthService.ts`.
  - Multi-factor: 2FA/TOTP supported via `backend/src/routes/totp.ts` and `node-forge`.

## Monitoring & Observability

**Error Tracking:**
- None detected (uses Winston local/rotating logs).

**Logs:**
- Winston with daily rotation files.
- Implementation: `backend/src/utils/logger.ts`.
- Path: `./logs/` (configurable via `LOG_DIR`).

## CI/CD & Deployment

**Hosting:**
- Docker-based deployment (Vultr/DigitalOcean likely, as seen in `deploy.sh` and `AUTODEPLOY_SETUP.md`).
- Reverse Proxy: Nginx (`nginx-webhook.conf`).

**CI Pipeline:**
- Custom shell scripts for deployment: `deploy.sh`, `deploy-update.sh`, `setup-autodeploy.sh`.
- GitHub Webhooks for auto-deploy: `webhook-server.js`.

## Environment Configuration

**Required env vars:**
- `DATABASE_URL`, `REDIS_URL`, `STRIPE_SECRET_KEY`, `ANAF_OAUTH_CLIENT_ID`, `ANAF_OAUTH_CLIENT_SECRET`, `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_ID`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`.

**Secrets location:**
- Environment variables (managed via `.env` files and system-level environment).

## Webhooks & Callbacks

**Incoming:**
- `/api/stripe/webhook` - Stripe payment/subscription events.
- `/api/auth/anaf/callback` - OAuth2 callback from ANAF.
- `/webhook` - Auto-deployment webhook (on port 9000, managed by `webhook-server.js`).

**Outgoing:**
- ANAF API (upload/download/list).
- Backblaze B2 (backup storage).
- Stripe API (subscription/customer creation).
- Web Push servers (notifications).
- SMTP servers (email notifications via `nodemailer`).

---

*Integration audit: 2025-02-25*
