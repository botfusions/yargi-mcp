# Test HTTP Server - Fixed Syntax
FROM python:3.11-slim

WORKDIR /app

# Create test server script
RUN echo 'from http.server import HTTPServer, BaseHTTPRequestHandler\n\
class Handler(BaseHTTPRequestHandler):\n\
    def do_GET(self):\n\
        self.send_response(200)\n\
        self.end_headers()\n\
        self.wfile.write(b"Yargi MCP Test OK")\n\
\n\
print("Starting HTTP server on port 8001...")\n\
server = HTTPServer(("0.0.0.0", 8001), Handler)\n\
server.serve_forever()' > server.py

EXPOSE 8001
HEALTHCHECK NONE

CMD ["python", "server.py"]
