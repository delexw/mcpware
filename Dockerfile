# Use Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gateway_server.py .
COPY src/ ./src/

# Run as non-root user
RUN useradd -m -u 1000 gateway && chown -R gateway:gateway /app
USER gateway

# Default command (stdio mode)
CMD ["python", "gateway_server.py"] 