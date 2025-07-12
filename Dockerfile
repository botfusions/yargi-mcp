# yargi-mcp Clean Dockerfile (No Health Check)
FROM mcr.microsoft.com/playwright/python:v1.53.0-noble

# Runtime setup
WORKDIR /app

# Copy dependency manifests first for layer-cache
COPY pyproject.toml poetry.lock* requirements*.txt* ./

# Fast, deterministic install with uv
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir .[asgi,saas]

# Copy application source
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV ENABLE_AUTH=true
ENV PORT=8001

# Expose port
EXPOSE 8001

# Start the application
CMD ["uvicorn", "asgi_app:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
