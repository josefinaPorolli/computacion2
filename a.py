#!/usr/bin/env python3
"""Servidor TCP mínimo."""
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
    # servidor.setsockopt(socket.SOL_SOCKET, 1)
    servidor.bind(('0.0.0.0', 8080))
    servidor.listen(5)
    print('Escuchando en 0.0.0.0:8080...')

    while True:
        conn, direccion = servidor.accept()
        with conn:
            print(f'Conexión desde {direccion}')
            datos = conn.recv(4096)
            print(f'Datos recibidos: {datos.decode("utf-8")}')
            if datos:
                conn.sendall(datos)      # eco