import argparse
import sys
import re # Para usar expresiones regulares en la búsqueda

def main():
    parser = argparse.ArgumentParser(description="Buscar un patrón en archivos o stdin")
    parser.add_argument("pattern", help="Patrón a buscar")
    parser.add_argument("files", nargs="*", help="Archivos a buscar (si no se especifican, se lee de stdin)")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Búsqueda insensible a mayúsculas")
    parser.add_argument("-n", "--line-number", action="store_true", help="Mostrar número de línea")
    parser.add_argument("-c", "--count", action="store_true", help="Solo mostrar conteo de coincidencias")
    parser.add_argument("-v", "--invert", action="store_true", help="Mostrar líneas que NO coinciden")

    args = parser.parse_args()
    args.show_line_number = args.line_number or len(args.files) > 1

    if not args.files:
        # Leer de stdin
        lines = sys.stdin.read().splitlines()
        search_in_lines(lines, args)
    else:
        for filename in args.files:
            with open(filename, 'r') as f:
                lines = f.read().splitlines()
                search_in_lines(lines, args, filename)

def search_in_lines(lines, args, filename=None):
    pattern = args.pattern
    if args.ignore_case:
        pattern = pattern.lower()

    count = 0
    for i, line in enumerate(lines, start=1):
        line_to_check = line.lower() if args.ignore_case else line
        match = re.search(pattern, line_to_check) is not None

        if (match and not args.invert) or (not match and args.invert):
            count += 1
            if not args.count:
                if args.show_line_number:
                    prefix = f"{filename}:{i}:" if filename else f"{i}:"
                    print(f"{prefix} {line}")
                else:
                    print(line)

    if args.count:
        prefix = f"{filename}: " if filename else ""
        print(f"{prefix}{count} coincidencias")

if __name__ == "__main__":
    main()