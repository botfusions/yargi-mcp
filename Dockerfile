FROM python:3.11-slim
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy all source files
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Start the API
CMD ["uvicorn", "simple_api:app", "--host", "0.0.0.0", "--port", "8000"]