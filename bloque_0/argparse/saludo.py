import sys

if(len(sys.argv) < 2):
    print("Uso: python saludo.py <nombre>")
    sys.exit(1)

nombre = sys.argv[1]
print(f"Hola, {nombre}!")