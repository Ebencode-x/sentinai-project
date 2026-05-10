# SentinAI — production image
# Multi-stage: builder installs deps, runtime runs as non-root
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target /build/deps


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/deps

# Create non-root user for security
RUN groupadd --gid 1001 sentinai && \
    useradd --uid 1001 --gid sentinai --shell /bin/bash --create-home sentinai

WORKDIR /app

# Copy installed deps from builder
COPY --from=builder /build/deps ./deps

# Copy only source code — no tests, no logs, no .env files
COPY src ./src

# Create logs directory owned by non-root user
RUN mkdir -p logs && chown -R sentinai:sentinai /app

USER sentinai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5).raise_for_status()"

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
