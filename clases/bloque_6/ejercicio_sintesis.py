#!/usr/bin/env python3
"""
Banco con cuentas en memoria compartida.
Múltiples procesos realizan transferencias.
"""
from multiprocessing import Process, Array, Value
import random

NUM_CUENTAS = 5
SALDO_INICIAL = 1000
NUM_PROCESOS = 3
TRANSFERENCIAS_POR_PROCESO = 10000

def mostrar_saldos(cuentas, etiqueta):
    # construye una lista normal de python con los saldos actuales del array compartido
    saldos = [cuentas[i] for i in range(NUM_CUENTAS)]
    total = sum(saldos)
    print(f"[{etiqueta}] Saldos: {saldos} | Total: {total}")

def cajero(cuentas, cajero_id, num_transferencias):
    for _ in range(num_transferencias):
        # elegir cuenta origen al azar
        origen = random.randint(0, NUM_CUENTAS - 1)
        
        # elegir cuenta destino al azar, que sea distinta a origen
        destino = random.randint(0, NUM_CUENTAS - 1)
        while destino == origen:
            destino = random.randint(0, NUM_CUENTAS - 1)

        monto = random.randint(1, 50)

        if cuentas[origen] >= monto:
            # OJO: estas dos líneas no son atómicas
            # entre el -= y el += cualquier otro proceso puede meterse
            # ejemplo: P0 lee origen=1000, P1 lee origen=1000,
            # P0 resta 50 → 950, P1 resta 30 → 970 (sobreescribe el de P0)
            # el dinero desaparece
            cuentas[origen] -= monto   # restar de la cuenta origen
            cuentas[destino] += monto  # sumar a la cuenta destino
            with open("transfer_log.txt", "a", encoding="utf-8") as log_file:
                log_file.write(f"{origen}->{destino}:{monto}\n")

    print(f"[Cajero {cajero_id}] Completó {num_transferencias} transferencias")


# Array es como Value pero para múltiples valores
# 'i' = enteros, [SALDO_INICIAL] * NUM_CUENTAS = [1000, 1000, 1000, 1000, 1000]
# internamente usa MAP_SHARED igual que Value, todos los procesos ven el mismo array
cuentas = Array('i', [SALDO_INICIAL] * NUM_CUENTAS)

print(f"=== Banco con {NUM_CUENTAS} cuentas ===")
print(f"=== Saldo total esperado: {NUM_CUENTAS * SALDO_INICIAL} ===\n")

mostrar_saldos(cuentas, "INICIO")

# lanzar un proceso por cajero, cada uno recibe el array compartido
procesos = []
for i in range(NUM_PROCESOS):
    p = Process(target=cajero, args=(cuentas, i, TRANSFERENCIAS_POR_PROCESO))
    p.start()    # arranca el proceso y sigue sin esperar
    procesos.append(p)

# esperar a que todos los cajeros terminen antes de mostrar el resultado
for p in procesos:
    p.join()

mostrar_saldos(cuentas, "FINAL")

total_final = sum(cuentas[i] for i in range(NUM_CUENTAS))
total_esperado = NUM_CUENTAS * SALDO_INICIAL

# si se perdió plata, fue por la race condition entre el -= y el +=
if total_final != total_esperado:
    print(f"\n¡ERROR! Se perdieron ${total_esperado - total_final}")
    print("Esto es una race condition - se necesita sincronización")
else:
    print(f"\nTodo correcto (pero fue suerte - ejecutalo varias veces)")