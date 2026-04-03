import argparse
import sys

parser = argparse.ArgumentParser(description="Convierte temperaturas de Celsius a Farenheit y viceversa.")

parser.add_argument("-t", "--to", required=True, choices=["celsius", "farenheit"], help="Unidad destino")
parser.add_argument("-v", "--value", required=True, type=float, help="Valor de temperatura")
args = parser.parse_args()

if args.to.lower() == "celsius":
    resultado = (args.value - 32) * 5.0/9.0
    print(f"{args.value}°F son {resultado:.2f}°C.")
elif args.to.lower() == "farenheit":
    resultado = (args.value * 9.0/5.0) + 32
    print(f"{args.value}°C son {resultado:.2f}°F.")
else:
    print("Unidad no reconocida. Use 'celsius' o 'farenheit'.")
    sys.exit(1)
