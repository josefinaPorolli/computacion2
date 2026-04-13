#!/usr/bin/env python3
import os

def cmd_cd(args):
    """Implementación del comando cd."""
    if not args:
        destino = os.environ.get("HOME", "/")
    else:
        destino = args[0]

    try:
        os.chdir(destino)
    except OSError as e:
        print(f"cd: {e}")

def main():

    # Comandos internos
    internos = {
        "cd": cmd_cd, # es fantástico pq le puedo poner el nombre que se me salga del
    }

    while True:
        try:
            linea = input("minish$ ")
        except EOFError:
            print("\nChau!")
            break

        if not linea.strip():
            continue

        if linea.strip() == "exit":
            break

        # Parsear comando y argumentos
        partes = linea.split()
        comando = partes[0]
        args = partes[1:]

        # ¿Es comando interno?
        if comando in internos:
            internos[comando](args)
            continue

        # Fork + exec
        pid = os.fork()

        if pid == 0:
            try:
                os.execvp(comando, [comando] + args)
            except OSError as e:
                print(f"minish: {comando}: {e}")
                os._exit(127)
        else:
            _, status = os.wait()
            # Opcional: mostrar código si no es 0
            codigo = os.WEXITSTATUS(status)
            if codigo != 0:
                print(f"[código {codigo}]")

if __name__ == "__main__":
    main()