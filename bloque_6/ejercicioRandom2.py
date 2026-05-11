import os
import mmap
import struct

# Crear la región compartida ANTES del fork
mm = mmap.mmap(-1, 4, mmap.MAP_SHARED)  # -1 = anónimo, sin archivo
struct.pack_into('i', mm, 0, 0)  # escribir 0 como entero de 4 bytes

pid = os.fork()

if pid == 0:
    valor = struct.unpack_from('i', mm, 0)[0] # leer el valor entero desde el mapeo, devuelve una tupla, por eso [0] para obtener el valor
    print(f"Hijo antes: var={valor}, id={id(mm)}")
    struct.pack_into('i', mm, 0, valor + 1) # escribir el nuevo valor (valor + 1) en el mapeo, sobrescribiendo los 4 bytes a partir de la posición 0
    valor = struct.unpack_from('i', mm, 0)[0] # leer el valor actualizado para mostrarlo, aunque no es estrictamente necesario, sirve para verificar que se actualizó correctamente
    print(f"Hijo después: var={valor}, id={id(mm)}")
else:
    valor = struct.unpack_from('i', mm, 0)[0]
    print(f"Padre antes: var={valor}, id={id(mm)}")
    struct.pack_into('i', mm, 0, valor + 2)
    valor = struct.unpack_from('i', mm, 0)[0]
    print(f"Padre después: var={valor}, id={id(mm)}")