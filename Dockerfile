# Test HTTP Server
FROM python:3.11-slim

WORKDIR /app

EXPOSE 8001
HEALTHCHECK NONE

CMD ["python", "-c", "from http.server import HTTPServer, BaseHTTPRequestHandler; class Handler(BaseHTTPRequestHandler): def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'Yargi MCP Test OK'); HTTPServer(('0.0.0.0', 8001), Handler).serve_forever()"]
