import argparse
import sys

parser = argparse.ArgumentParser(description="Convierte temperaturas de Celsius a Farenheit y viceversa.")

parser.add_argument("-t", "--to", help="a qué unidad se quiere convertir (celsius o farenheit).")
parser.add_argument("-v", "--value", type=float, help="el valor de la temperatura a convertir.")

args = parser.parse_args() # parse_args() analiza los argumentos pasados por línea de comandos y los asigna a args

# Para prevenir errores, verificar que ambos argumentos hayan sido proporcionados
if args.to is None or args.value is None:
    print("Uso: python temperatura.py -t <unidad> -v <valor>")
    sys.exit(1)

if args.to.lower() == "celsius":
    resultado = (args.value - 32) * 5.0/9.0
    print(f"{args.value}°F son {resultado:.2f}°C.")
elif args.to.lower() == "farenheit":
    resultado = (args.value * 9.0/5.0) + 32
    print(f"{args.value}°C son {resultado:.2f}°F.")
else:
    print("Unidad no reconocida. Use 'celsius' o 'farenheit'.")
    sys.exit(1)
