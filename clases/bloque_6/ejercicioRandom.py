"""Caso de memoria no compartida"""
import os
import time

var = 0

pid = os.fork()

if pid == 0:
    print(f"Hijo: PID {os.getpid()}, var={var}, {id(var)}")
    var+=1 # al cambiarla, cambia la referencia a la variable, por lo que el padre y el hijo tienen variables distintas
    print(f"Hijo: PID {os.getpid()}, var={var}, {id(var)}")
else:
    print(f"Padre: PID {os.getpid()}, var={var}, {id(var)}")
    var+=2 # al cambiarla, cambia la referencia a la variable, por lo que el padre y el hijo tienen variables distintas
    print(f"Padre: PID {os.getpid()}, var={var}, {id(var)}")