#!/usr/bin/env python3
"""
Ejecutor de comandos en paralelo.
Uso: python3 paralelo.py "cmd1" "cmd2" ...
"""
import os
import shlex
import sys
import time

def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} comando1 [comando2 ...]")
        sys.exit(1)

    comandos = sys.argv[1:]
    inicio = time.time() # para medir el tiempo total de ejecución

    # pid -> comando original
    procesos = {}

    # Lanzar todos los comandos sin esperar (paralelo)
    for comando in comandos:
        pid = os.fork() # por cada comando, hacer un fork para clonar el proceso

        if pid == 0:
            # Hijo: parsea y ejecuta el comando
            try:
                partes = shlex.split(comando) # partes es una lista: [comando, arg1, arg2, ...]
            except ValueError as e:
                print(f"Error parseando comando '{comando}': {e}", file=sys.stderr)
                os._exit(127)

            if not partes:
                print("Comando vacío", file=sys.stderr)
                os._exit(127)

            try:
                os.execvp(partes[0], partes) # execvp busca el comando en el PATH
            except OSError as e:
                print(f"Error ejecutando '{comando}': {e}", file=sys.stderr)
                os._exit(127)
        else:
            procesos[pid] = comando # Guardar el comando asociado al PID
            print(f"[{pid}] Iniciado: {comando}")

    exitosos = 0
    fallidos = 0

    # Esperar a todos; reportar en el orden real en que terminan
    while procesos: # mientras haya procesos activos
        pid, status = os.wait() # espera a que termine cualquier hijo; devuelve su PID y estado
        comando = procesos.pop(pid, "<desconocido>") # obtener el comando asociado al PID, o "<desconocido>" si no tenemos el PID registrado.
        if os.WIFEXITED(status):
            codigo = os.WEXITSTATUS(status) # código de salida del proceso hijo
        elif os.WIFSIGNALED(status): # el proceso fue terminado por una señal (ej: Ctrl+C)
            # Convención shell: 128 + número de señal
            codigo = 128 + os.WTERMSIG(status) # número de señal que causó la terminación
        else:
            codigo = 1 # código genérico para otros casos (ej: detenido, continuado)

        if codigo == 0:
            exitosos += 1
        else:
            fallidos += 1

        print(f"[{pid}] Terminado: {comando} (código: {codigo})")

    total = time.time() - inicio

    print("\nResumen:")
    print(f"- Comandos ejecutados: {len(comandos)}")
    print(f"- Exitosos: {exitosos}")
    print(f"- Fallidos: {fallidos}")
    print(f"- Tiempo total: {total:.2f}s")

if __name__ == "__main__":
    main()