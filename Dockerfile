# Yargi-MCP HTTP Mode
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1

# No health check
HEALTHCHECK NONE

# Expose port
EXPOSE 8001

# Start in HTTP mode instead of STDIO
CMD ["python", "-c", "import sys; sys.path.append('.'); from mcp_server_main import mcp; mcp.run(transport='http', host='0.0.0.0', port=8001)"]
