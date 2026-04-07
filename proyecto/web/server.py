import redis
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Servidor HTTP simple
redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379, decode_responses=True)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            visitas = r.get('visitas') or 0
            response = {'visitas': int(visitas)}
        else:
            response = {'error': 'no encontrado'}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8000), Handler)
    print("Servidor en puerto 8000...")
    server.serve_forever()
