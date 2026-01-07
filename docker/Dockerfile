FROM python:3.12-slim as builder

WORKDIR /app

# Install uv
RUN pip install uv

# Copy and install dependencies
COPY pyproject.toml README.md ./
COPY src/ src/
RUN uv pip install --system .

FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source
COPY src/ src/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "reflex.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
