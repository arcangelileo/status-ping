# ---------- build stage ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency spec first for layer caching
COPY pyproject.toml .

# Install dependencies into a virtual environment for clean copying
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir .

# ---------- runtime stage ----------
FROM python:3.11-slim

LABEL maintainer="StatusPing <hello@statusping.app>"
LABEL description="StatusPing — uptime monitoring and public status page platform"

WORKDIR /app

# Create non-root user
RUN groupadd -r statusping && useradd -r -g statusping -d /app -s /sbin/nologin statusping

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

# Copy entrypoint
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Create data directory for SQLite database
RUN mkdir -p /app/data && chown -R statusping:statusping /app

# Switch to non-root user
USER statusping

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
