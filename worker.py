"""
MUNI84CR Railway worker — minimal HTTP health-check version for deployment debugging.
If this passes Railway's health check, the full pipeline will be added back.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

print("worker.py: STARTED", flush=True)

PORT = int(os.environ.get("PORT", 8080))

print(f"worker.py: binding to port {PORT}", flush=True)
print(f"worker.py: WORKER_MODE={os.environ.get('WORKER_MODE', 'NOT SET')}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok","service":"crawler-worker"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


print("worker.py: starting HTTPServer...", flush=True)
server = HTTPServer(("0.0.0.0", PORT), Handler)
print(f"worker.py: listening on port {PORT} — health check ready", flush=True)
server.serve_forever()
