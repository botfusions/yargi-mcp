# Minimal yargi-mcp Dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1

# No health check at all
HEALTHCHECK NONE

# Simple start
EXPOSE 8001
CMD ["python", "mcp_server_main.py"]
