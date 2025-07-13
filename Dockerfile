# Working Simple HTTP Server
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
HEALTHCHECK NONE
EXPOSE 8001

# Start with FastMCP CLI for HTTP mode
CMD ["fastmcp", "run", "--transport", "http", "--host", "0.0.0.0", "--port", "8000", "mcp_server_main.py"]
