# Creá wc_simple.py (inspirado en el comando wc de Unix) que cuente las líneas de un archivo. El programa recibe el nombre del archivo como argumento

import sys

if(len(sys.argv) < 2):
    print("Uso: python3 wc_simple.py <nombre_archivo>")
    sys.exit(1)

archivo = sys.argv[1]
try:
    with open(archivo, 'r') as f: # r de "read"
        lineas = f.readlines() # readlines() devuelve una lista con cada línea del archivo como un elemento
        print(f"El archivo '{archivo}' tiene {len(lineas)} líneas.")
except FileNotFoundError:
    print(f"El archivo '{archivo}' no se encontró.")
    sys.exit(1)
except Exception as e: # para cualquier otra excepción
    print(f"Ocurrió un error: {e}")
    sys.exit(1)
