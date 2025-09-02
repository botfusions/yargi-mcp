FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies with uv for better dependency management
RUN pip install --no-cache-dir uv

# Copy source files first for better caching
COPY . .

# Install dependencies
RUN uv pip install --system --no-cache-dir .[asgi,saas] || pip install --no-cache-dir -r requirements.txt

# Environment variables for TurkLawAI
ENV PYTHONUNBUFFERED=1
ENV ENABLE_AUTH=true
ENV HOST=0.0.0.0
ENV PORT=8000

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash turklawai
RUN chown -R turklawai:turklawai /app
USER turklawai

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start the TurkLawAI API server
CMD ["python", "turklawai_mcp_server.py"]
