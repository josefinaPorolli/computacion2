import os

# Crear pipe
read_fd, write_fd = os.pipe()

print(f"Extremo de lectura: fd {read_fd}")
print(f"Extremo de escritura: fd {write_fd}")

# Escribir en un extremo
os.write(write_fd, b"Hola por el pipe!\n")

# Leer del otro extremo
datos = os.read(read_fd, 1024)
print(f"Leído: {datos.decode()}")

# Cerrar
os.close(read_fd)
os.close(write_fd)