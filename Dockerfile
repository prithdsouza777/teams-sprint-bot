# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime (clean slim image)
FROM python:3.13-slim

WORKDIR /app

# Copy only the virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application
COPY app/ ./app/

# Cloud Run uses PORT environment variable
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run with uvicorn - Cloud Run injects PORT
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
