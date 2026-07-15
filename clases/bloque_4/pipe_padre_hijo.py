#!/usr/bin/env python3
"""Comunicación básica por pipe."""
import os

# Crear pipe ANTES del fork
read_fd, write_fd = os.pipe()

pid = os.fork()

if pid == 0:
    # === HIJO: escribe al pipe ===
    os.close(read_fd)  # No necesita leer

    mensajes = [
        "Mensaje 1 del hijo",
        "Mensaje 2 del hijo",
        "Mensaje 3 del hijo",
        "FIN"
    ]

    for msg in mensajes:
        os.write(write_fd, (msg + "\n").encode())
        print(f"[HIJO] Envié: {msg}")

    os.close(write_fd)
    os._exit(0)

else:
    # === PADRE: lee del pipe ===
    os.close(write_fd)  # No necesita escribir

    print("[PADRE] Esperando mensajes del hijo...\n")

    # Leer todo lo que venga por el pipe
    buffer = b""
    while True:
        datos = os.read(read_fd, 1024)
        if not datos:  # EOF - el hijo cerró su extremo
            break
        buffer += datos

    # Procesar los mensajes
    mensajes = buffer.decode().strip().split("\n")
    for msg in mensajes:
        print(f"[PADRE] Recibí: {msg}")

    os.close(read_fd)
    os.wait() # wait por el hijo para evitar zombies
    print("\n[PADRE] Hijo terminó")