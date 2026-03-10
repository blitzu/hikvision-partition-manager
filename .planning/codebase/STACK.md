# Technology Stack

**Analysis Date:** 2025-02-25

## Languages

**Primary:**
- TypeScript 5.7.2 - Used across both `backend/` and `frontend/` for type-safe development.

**Secondary:**
- JavaScript (ESM/CommonJS) - Used in some scripts and configuration files.
- SQL (via Prisma) - Used for database schema definitions and migrations in `backend/prisma/schema.prisma`.

## Runtime

**Environment:**
- Node.js >= 18.0.0 - Primary execution environment for the backend and build tools.
- Docker - Used for containerization of both backend and frontend. `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml`.

**Package Manager:**
- npm >= 9.0.0
- Lockfile: `backend/package-lock.json` and `frontend/package-lock.json` are present.

## Frameworks

**Core:**
- Express 4.21.2 - Backend web framework for REST API and middleware.
- React 18.3.1 - Frontend UI library.
- Vite 6.0.7 - Frontend build tool and development server.
- Prisma 5.22.0 - ORM for database access and schema management.

**Testing:**
- Jest 29.7.0 - Primary testing framework for the backend. `backend/jest.config.js`.
- ts-jest 29.2.5 - TypeScript preprocessor for Jest.

**Build/Dev:**
- TypeScript Compiler (tsc) - For compiling backend code.
- Vite - For bundling and serving the frontend.
- ts-node-dev - For rapid backend development with auto-reload.

## Key Dependencies

**Critical:**
- `axios` 1.7.9 - Used for all external API requests including ANAF API.
- `bull` 4.16.3 - Redis-based queue for background processing of invoice downloads.
- `ioredis` 5.4.1 - Redis client for caching and queue management.
- `stripe` 17.5.0 - Integration for subscription management and payments.
- `backblaze-b2` 1.7.0 - SDK for Backblaze B2 storage integration.
- `jsonwebtoken` 9.0.2 - Implementation of JWT for authentication.

**Infrastructure:**
- `winston` 3.17.0 - Logging framework with support for multiple transports and rotation.
- `helmet` 8.0.0 - Security middleware for Express.
- `express-rate-limit` 7.5.0 - Rate limiting for API protection.
- `web-push` 3.6.7 - Library for sending browser push notifications.
- `socket.io` 4.7.5 - Real-time communication between backend and frontend.

## Configuration

**Environment:**
- Configured via `.env` files using `dotenv`.
- Key configs: `DATABASE_URL`, `REDIS_URL`, `STRIPE_SECRET_KEY`, `ANAF_OAUTH_CLIENT_ID`, `B2_APPLICATION_KEY`.

**Build:**
- `backend/tsconfig.json` - Backend TypeScript configuration.
- `frontend/tsconfig.json` - Frontend TypeScript configuration.
- `frontend/vite.config.ts` - Vite build configuration.

## Platform Requirements

**Development:**
- Node.js 18+, Docker Desktop (optional), Redis (local or containerized), PostgreSQL (local or containerized).

**Production:**
- Linux (based on `deploy.sh` and `docker-compose.yml`), Docker, Nginx (for proxying and webhooks).

---

*Stack analysis: 2025-02-25*
