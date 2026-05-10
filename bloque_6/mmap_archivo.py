import mmap
from pathlib import Path

# Abrir un archivo existente
datos_path = Path(__file__).with_name("datos.txt")

with open(datos_path, "r+b") as f:
    # Mapear todo el archivo a memoria
    mm = mmap.mmap(f.fileno(), 0)  # 0 = mapear todo el archivo

    # Leer como si fuera un archivo
    print(mm.readline())

    # Acceder como si fuera un array de bytes
    print(mm[0:10])

    # Modificar directamente
    mm[0:5] = b"HOLA!" # Representación binaria de "HOLA!"

    print(mm[0:10])

    # Los cambios se escriben al archivo
    mm.flush()
    mm.close()