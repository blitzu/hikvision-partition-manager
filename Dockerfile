# Stage 1: builder — install all dependencies into /install
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml .
COPY app/ app/

RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: runtime — lean image with non-root user
FROM python:3.12-slim

# Create non-root user
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy full project source with correct ownership
# This includes alembic/ and alembic.ini which are required at runtime
# because lifespan runs migrations via asyncio.to_thread(_run_migrations)
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
