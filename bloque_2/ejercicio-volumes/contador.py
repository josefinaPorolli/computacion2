import os
from datetime import datetime

ARCHIVO = '/datos/contador.txt'

def leer_contador():
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO) as f:
            return int(f.read().strip())
    return 0

def guardar_contador(n):
    os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
    with open(ARCHIVO, 'w') as f:
        f.write(str(n))

if __name__ == '__main__':
    n = leer_contador()
    n += 1
    guardar_contador(n)
    print(f"[{datetime.now().isoformat()}] Contador: {n}")
