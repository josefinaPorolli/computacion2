#!/usr/bin/env python3
"""Demostración de stdout vs stderr."""
import sys
import os

# Escribir a stdout
print("Mensaje normal a stdout") # print escribe a stdout por defecto
sys.stdout.write("Otro mensaje a stdout\n") # sys.stdout.write es otra forma de escribir a stdout, no agrega un salto de línea automático
os.write(1, b"Y otro mas directo al fd 1\n") # os.write permite escribir directamente a un file descriptor (1 = stdout), pero requiere bytes

# Escribir a stderr
print("Mensaje de error a stderr", file=sys.stderr) # print con el argumento file permite especificar otro destino, en este caso sys.stderr
sys.stderr.write("Otro error a stderr\n") # sys.stderr.write es otra forma de escribir a stderr, no agrega un salto de línea automático
os.write(2, b"Error directo al fd 2\n") # os.write permite escribir directamente a un file descriptor (2 = stderr), pero requiere bytes