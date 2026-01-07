# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tree \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY config.py .
COPY tools.py .
COPY server.py .
COPY whitelist.txt .

# Create logs directory
RUN mkdir -p /app/logs

# Expose MCP port (default 8080)
EXPOSE 8080

# Run the server
CMD ["python", "server.py"]
