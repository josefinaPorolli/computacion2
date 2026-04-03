import argparse

parser = argparse.ArgumentParser(description="Saluda a una persona.")
parser.add_argument("nombre", help="Nombre de la persona")
args = parser.parse_args()
print(f"Hola, {args.nombre}!")