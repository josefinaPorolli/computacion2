import redis
import os
import time

# Conexión a redis
redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379)

print(f"Conectando a Redis en {redis_host}...")

while True:
    visitas = r.incr('visitas') # Incrementea el contador
    print(f"Visitas: {visitas}")
    time.sleep(1) # Delay de 1 segundo
