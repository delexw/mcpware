# Use Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy application files
COPY gateway_server.py .
COPY src/ ./src/

# The gateway runs in stdio mode
ENTRYPOINT ["python", "gateway_server.py"] 