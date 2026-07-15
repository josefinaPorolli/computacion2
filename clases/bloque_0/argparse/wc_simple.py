import argparse

parser = argparse.ArgumentParser(description="Cuenta líneas de un archivo (inspirado en wc).")
parser.add_argument("archivo", help="Archivo a contar")
args = parser.parse_args()
archivo = args.archivo
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
