#!/usr/bin/env python3
"""Función para ejecutar comandos."""
import os
import sys

def ejecutar(comando, args=None):
    """
    Ejecuta un comando y retorna su código de salida.

    Args:
        comando: nombre del programa a ejecutar
        args: lista de argumentos (sin incluir el comando)

    Returns:
        código de salida del comando
    """
    if args is None:
        args = []

    pid = os.fork()

    if pid == 0:
        # Proceso hijo
        try:
            os.execvp(comando, [comando] + args) # execvp busca el comando en el PATH
        except OSError as e:
            print(f"Error: {e}", file=sys.stderr)
            os._exit(127)
    else:
        # Proceso padre: esperar al hijo y obtener su código de salida
        _, status = os.wait()
        return os.WEXITSTATUS(status)

# Probar la función
if __name__ == "__main__":
    print("=== Ejecutando ls ===")
    codigo = ejecutar("ls", ["-la", "/tmp"])
    print(f"Código de salida: {codigo}\n")

    print("=== Ejecutando comando inexistente ===")
    codigo = ejecutar("comando_que_no_existe")
    print(f"Código de salida: {codigo}\n")

    print("=== Ejecutando echo ===")
    codigo = ejecutar("echo", ["Hola", "desde", "exec"])
    print(f"Código de salida: {codigo}")