"""
main.py temporal — prueba procfs.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from procfs import listar_pids, leer_stat, leer_status, leer_cmdline, nombre_usuario

def main():
    pid_propio = os.getpid()
    print(f"=== Probando procfs.py con PID propio: {pid_propio} ===\n")

    # 1. listar_pids
    pids = listar_pids()
    print(f"listar_pids(): {len(pids)} procesos encontrados")
    print(f"  Primeros 5: {sorted(pids)[:5]}\n")

    # 2. leer_stat
    stat = leer_stat(pid_propio)
    print(f"leer_stat({pid_propio}):")
    for k, v in stat.items():
        print(f"  {k}: {v}")
    print()

    # 3. leer_status
    status = leer_status(pid_propio)
    print(f"leer_status({pid_propio}) — algunos campos:")
    for k in ('VmRSS', 'VmSize', 'Threads', 'Uid', 'voluntary_ctxt_switches'):
        print(f"  {k}: {status.get(k)}")
    print()

    # 4. leer_cmdline
    cmd = leer_cmdline(pid_propio)
    print(f"leer_cmdline({pid_propio}): {cmd}\n")

    # 5. nombre_usuario
    uid = status['Uid']['real']
    print(f"nombre_usuario({uid}): {nombre_usuario(uid)}")

if __name__ == "__main__":
    main()