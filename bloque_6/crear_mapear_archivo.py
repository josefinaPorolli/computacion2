#!/usr/bin/env python3
"""Crear un archivo, mapearlo y modificarlo con mmap."""
import mmap

# Crear archivo con contenido
with open("/tmp/mmap_test.txt", "wb") as f:
    f.write(b"Pizza, pasta, put it in a box\n")
    f.write(b"Bring it here and put it on my c***\n")
    f.write(b"The tortellini on my weenie\n")
    f.write(b"Pepperoni on the WAAALLS\n")
    f.write(b"Cheesy on my peenny and some sauce-a on my balls\n")

# Mapear el archivo
with open("/tmp/mmap_test.txt", "r+b") as f:
    mm = mmap.mmap(f.fileno(), 0) # Mapear todo el archivo (0 significa tamaño completo), fileno obtiene el descriptor del archivo

    # Leer todo el contenido
    print("=== Contenido completo ===")
    print(mm[:].decode()) # [:] para leer todo el contenido, decode para convertir bytes a string

    # Leer línea por línea
    print("=== Línea por línea ===")
    mm.seek(0) # seek para volver al inicio del archivo
    while True:
        linea = mm.readline()
        if not linea:
            break
        print(f"  {linea.decode().strip()}")

    # Buscar texto desde el inicio del mapeo
    pos = mm.find(b"c***", 0)
    print(f"\n'c***' encontrado en posición: {pos}")

    # Modificar una parte si se encontró
    if pos != -1:
        mm.seek(pos)
        mm.write(b"cock")  # Sobrescribir en mayúsculas
    else:
        print("No se encontró 'c***' en el archivo.")

    # Ver resultado
    mm.seek(0)
    print(f"\n=== Después de modificar ===")
    print(mm[:].decode())

    mm.close()