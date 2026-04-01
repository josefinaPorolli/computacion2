import sys
    
numeros = sys.argv[1:]
suma = 0
for num in numeros:
    try:
        suma += float(num)
    except ValueError:
        print(f"'{num}' no es un número válido.")
        sys.exit(1)

print(f"La suma es: {suma}")