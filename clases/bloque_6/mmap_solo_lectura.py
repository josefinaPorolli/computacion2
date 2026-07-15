#!/usr/bin/env python3
"""Mapear archivo en modo solo lectura."""
import mmap

# Asegurate de tener el archivo del ejercicio anterior (crear_mapear_archivo.py) creado antes de ejecutar este script
with open("/tmp/mmap_test.txt", "rb") as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) # solo lectura se especifica con access=mmap.ACCESS_READ

    # Esto funciona:
    print(f"Contenido: {mm[:40]}") # [:40] para leer los primeros 40 bytes, se puede usar cualquier rango o [:] para todo el contenido
    print(f"Tamaño: {mm.size()} bytes") # size devuelve el tamaño del mapeo, que es el tamaño del archivo en este caso

    # Esto lanza excepción:
    try:
        mm[0:4] = b"TEST" # Intentar modificar el contenido del mapeo en modo solo lectura debería lanzar una excepción TypeError
    except TypeError as e:
        print(f"Error al escribir: {e}")

    mm.close()