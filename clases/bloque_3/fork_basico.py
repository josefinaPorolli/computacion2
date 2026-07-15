#!/usr/bin/env python3
"""Mi primer fork."""
import os

print(f"Proceso original: PID={os.getpid()}")

pid = os.fork()

if pid == 0:
    print(f"Soy el HIJO: PID={os.getpid()}, PPID={os.getppid()}")
else:
    print(f"Soy el PADRE: PID={os.getpid()}, hijo={pid}")

print(f"Este mensaje lo imprime PID={os.getpid()}")