# Multi-stage build for smaller final image
# Comment: "Multi-stage: Build in one container, run in another (smaller)"

# Stage 1: Builder
# Use official Python slim image for smaller base
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build dependencies
# - gcc, g++: For compiling C extensions
# - postgresql-client, libpq-dev: For PostgreSQL connection
# - gdal-bin: For PostGIS/geospatial operations
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*
    # Comment: "Clean up apt cache to reduce image size"

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
# --no-cache-dir reduces image size by not verifying downloaded packages
# --user installs to ~/.local which is easy to copy
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
# Start fresh with a slim image
FROM python:3.11-slim

# Install runtime dependencies only
# We don't need gcc/g++ here, just the libraries
RUN apt-get update && apt-get install -y \
    libpq5 \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
# Python installed packages usually live in site-packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code from host
COPY . .

# Create non-root user for security
# Comment: "Never run containers as root in production!"
# -m creates home dir, -u 1000 sets specific UID
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port 8000 for the API
EXPOSE 8000

# Health check
# Comment: "Docker monitors container health, restarts if unhealthy"
# simple check to see if API responds
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Start application
# gunicorn manages multiple worker processes for concurrency
# uvicorn.workers.UvicornWorker allows running async ASGI apps
CMD ["gunicorn", "api.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120"]
