import argparse

parser = argparse.ArgumentParser(description="Suma números.")
parser.add_argument("numeros", nargs="+", type=float, help="Números a sumar")
args = parser.parse_args()
print(f"La suma es: {sum(args.numeros)}")