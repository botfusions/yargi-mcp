FROM python:3.11-slim
WORKDIR /app

RUN pip install fastapi uvicorn

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "asgi_app:app", "--host", "0.0.0.0", "--port", "8000"]