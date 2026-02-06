FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Cloud Run uses PORT environment variable
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run with uvicorn - Cloud Run injects PORT
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
