#!/usr/bin/env python3
"""Redirección manual de stdout."""
import os
import sys

print("Este mensaje va a la terminal")

# Guardar stdout original
stdout_original = os.dup(1) # dup devuelve un nuevo fd que apunta al mismo destino que el fd dado (1 = stdout)

# Abrir archivo destino
archivo = os.open("/tmp/salida.txt", os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)

# Redirigir stdout
os.dup2(archivo, 1) # dup2 redirige el fd dado (archivo) al fd especificado (1 = stdout), cerrando el destino si ya estaba abierto
os.close(archivo)

# Ahora stdout va al archivo
print("Este mensaje va al archivo")
print("Y este también")
sys.stdout.flush()

# Restaurar stdout original
os.dup2(stdout_original, 1) # dup2 redirige el fd dado (stdout_original) al fd especificado (1 = stdout), cerrando el destino si ya estaba abierto
os.close(stdout_original)

print("Volvimos a la terminal")
print(f"Revisá el contenido de /tmp/salida.txt")