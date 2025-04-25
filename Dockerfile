FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY mcp_server.py .

# Expose health check port
EXPOSE 14000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    MYSQL_HOST=localhost \
    MYSQL_PORT=3306 \
    MYSQL_USER=root \
    MYSQL_PASSWORD=password \
    MYSQL_DATABASE=test \
    ROW_LIMIT=1000 \
    QUERY_TIMEOUT=10000 \
    POOL_SIZE=10 \
    HEALTH_PORT=14000 \
    KEEP_ALIVE_INTERVAL=10 \
    TIMEOUT=300 \
    LOG_LEVEL=INFO

# Run the server
CMD ["python", "mcp_server.py"] 