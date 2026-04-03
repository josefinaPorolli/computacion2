import argparse
import sys
import random

parser = argparse.ArgumentParser(description="Genera contraseñas aleatorias.")
parser.add_argument("-n", "--length", type=int, default=12, help="Longitud (default: 12)")
parser.add_argument("--no-symbols", action="store_true", help="Sin símbolos")
parser.add_argument("--no-numbers", action="store_true", help="Sin números")
parser.add_argument("--count", type=int, default=1, help="Cantidad a generar (default: 1)")

args = parser.parse_args()

if args.length < 4:
    print("La longitud mínima recomendada es de 4 caracteres.")
    sys.exit(1)

characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" # Siempre incluir letras mayúsculas y minúsculas
if not args.no_numbers: # Si no se ha especificado --no-numbers, incluir números
    characters += "0123456789"
if not args.no_symbols: # Si no se ha especificado --no-symbols, incluir símbolos especiales
    characters += "!@#$%&~?"

for _ in range(args.count): # Generar la cantidad de contraseñas solicitada
    password = ''.join(random.choice(characters) for _ in range(args.length)) # Generar una contraseña aleatoria de la longitud especificada usando los caracteres permitidos
    print(password)