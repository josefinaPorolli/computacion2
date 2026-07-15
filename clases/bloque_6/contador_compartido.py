#!/usr/bin/env python3
"""
Demostración de race condition con Value.
Ejecutalo varias veces y observá cómo cambia el resultado.
"""
from multiprocessing import Process, Value
import time

def incrementar(contador, n, nombre):
    """Incrementa el contador n veces."""
    print(f"[{nombre}] Iniciando {n} incrementos...")
    for _ in range(n):
        contador.value += 1
    print(f"[{nombre}] Terminado")

# Crear valor compartido
contador = Value('i', 0) #  Value internamente implementa un contador entero compartido entre procesos, 'i' indica que es un entero

# Lanzar 4 procesos que incrementan
N = 100000
procesos = []
for i in range(4):
    p = Process(target=incrementar, args=(contador, N, f"P{i}")) # cada proceso incrementará el contador N veces, con un nombre para identificarlo
    p.start() # start inicia el proceso, pero no espera a que termine, por eso se pueden ejecutar en paralelo
    procesos.append(p) # guardar referencia al proceso para luego hacer join

for p in procesos:
    p.join()

esperado = 4 * N
print(f"\nEsperado: {esperado}")
print(f"Obtenido: {contador.value}")
print(f"Diferencia: {esperado - contador.value} (incrementos perdidos)")