import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description="Procesar archivos JSON desde la terminal")
    parser.add_argument("json_file", help="Archivo JSON a procesar (usa - para stdin)")
    parser.add_argument("--keys", action="store_true", help="Listar claves del primer nivel")
    parser.add_argument("--get", metavar="KEY", help="Obtener valor usando notación con puntos")
    parser.add_argument("--pretty", action="store_true", help="Formatear JSON con indentación")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Modificar un valor usando notación con puntos")
    parser.add_argument("-o", "--output", help="Archivo de salida (default: stdout)")

    args = parser.parse_args()

    # Cargar JSON
    if args.json_file == "-": 
        data = json.load(sys.stdin) # Leer JSON desde stdin si se especifica "-"
    else:
        with open(args.json_file, 'r') as f: # Cargar JSON desde el archivo especificado
            data = json.load(f)

    # Listar claves del primer nivel
    if args.keys:
        for key in data.keys():
            print(key)
        return

    # Obtener valor con notación de puntos
    if args.get:
        value = get_value(data, args.get)
        print(json.dumps(value) if isinstance(value, (dict, list)) else value)
        return

    # Modificar valor con notación de puntos
    if args.set:
        set_value(data, args.set[0], args.set[1])

    # Formatear JSON si se pidió con --pretty
    output_data = json.dumps(data, indent=4) if args.pretty else json.dumps(data) # agrega indentación

    # Guardar o imprimir resultado
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_data)
        print(f"Guardado en {args.output}")
    else:
        print(output_data)

def get_value(data, path):
    keys = path.split('.') # Dividir el path en partes
    for key in keys:
        if isinstance(data, list): # Si el dato actual es una lista, convertimos la clave a entero para acceder al índice.
            key = int(key)  # Convertir a entero para índices de listas
        data = data[key]
    return data

def set_value(data, path, value):
    keys = path.split('.')
    # Navegar hasta el penúltimo nivel del diccionario para llegar al lugar donde se va a modificar el value. En caso de que se encadenen varias claves. Ejemplo: persona.nombre.origen_nombre 
    for key in keys[:-1]: 
        if isinstance(data, list):
            key = int(key)
        data = data[key]
    last_key = keys[-1] 
    if isinstance(data, list):
        last_key = int(last_key)
    data[last_key] = json.loads(value) if value.startswith(('{', '[', '"')) else value # Si el valor a setear es un JSON válido
if __name__ == "__main__":
    main()