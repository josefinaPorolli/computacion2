import redis
import os
import time

redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379)

print(f"Conectando a Redis en {redis_host}...")

while True:
    visitas = r.incr('visitas')
    print(f"Visitas: {visitas}")
    time.sleep(2)
