"""
procfs.py — Funciones para leer y parsear /proc directamente.

Este es el ÚNICO archivo del proyecto que toca /proc.
Todos los analizadores importan desde acá.

Reglas:
- Funciones puras: reciben un pid, devuelven un dict o None
- Si el proceso desaparece mientras leemos, devuelve None (no crashea)
- Sin lógica de negocio: solo parsing
"""

import os


# ---------------------------------------------------------------------------
# Funciones de listado
# ---------------------------------------------------------------------------

def listar_pids():
    """
    Devuelve la lista de PIDs activos leyendo /proc.
    Filtra solo las carpetas numéricas — esas son procesos.

    Ejemplo de retorno: [1, 2, 45, 1234, 5678]
    """
    pids = []
    try:
        for entrada in os.listdir('/proc'):
            if entrada.isdigit():
                pids.append(int(entrada))
    except PermissionError:
        pass
    return pids


# ---------------------------------------------------------------------------
# Lectura de /proc/<pid>/stat
# ---------------------------------------------------------------------------

def leer_stat(pid):
    """
    Lee y parsea /proc/<pid>/stat.

    Este archivo tiene todos los datos en una sola línea separada por espacios.
    El problema: el campo 2 (nombre del proceso) puede tener espacios y está
    entre paréntesis — hay que parsearlo con cuidado.

    Campos que nos interesan (indexados desde 1 como en la man page):
      1  = pid
      2  = nombre (comm) entre paréntesis
      3  = estado (R/S/D/T/Z/...)
      4  = ppid
      6  = session id (SID)
      7  = group id del proceso en foreground (PGID)
      10 = minor faults
      12 = minor faults de hijos
      11 = major faults
      13 = major faults de hijos
      14 = utime (tiempo en modo usuario, en jiffies)
      15 = stime (tiempo en modo kernel, en jiffies)
      18 = priority
      19 = nice
      20 = num_threads
      40 = rt_priority
      41 = policy de scheduling

    Retorna un dict con los campos parseados, o None si el proceso no existe.
    """
    try:
        with open(f'/proc/{pid}/stat') as f:
            contenido = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    # El nombre del proceso está entre paréntesis y puede tener espacios.
    # Buscamos el último ')' para separar correctamente.
    # Ejemplo: "123 (mi proceso) S 1 ..."
    inicio_nombre = contenido.index('(')
    fin_nombre    = contenido.rindex(')')

    nombre = contenido[inicio_nombre + 1 : fin_nombre]

    # El resto de los campos van después del ')' + espacio
    resto = contenido[fin_nombre + 2:].split()

    # Armamos el dict con los campos que nos importan.
    # Usamos índices del 'resto' (que empieza en el campo 3 de la man page).
    try:
        return {
            'pid':         int(pid),
            'nombre':      nombre,
            'estado':      resto[0],          # campo 3
            'ppid':        int(resto[1]),      # campo 4
            'sid':         int(resto[3]),      # campo 6
            'pgid':        int(resto[2]),      # campo 5 (pgrp)
            'minflt':      int(resto[7]),      # campo 10
            'majflt':      int(resto[9]),      # campo 12 (en realidad 11)
            'utime':       int(resto[11]),     # campo 14
            'stime':       int(resto[12]),     # campo 15
            'priority':    int(resto[15]),     # campo 18
            'nice':        int(resto[16]),     # campo 19
            'num_threads': int(resto[17]),     # campo 20
            'rt_priority': int(resto[37]),     # campo 40
            'policy':      int(resto[38]),     # campo 41
        }
    except (IndexError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Lectura de /proc/<pid>/status
# ---------------------------------------------------------------------------

def leer_status(pid):
    """
    Lee y parsea /proc/<pid>/status.

    Este archivo es más legible que stat: cada línea tiene formato
    "Clave:   valor". Complementa stat con datos de memoria y señales.

    Campos que extraemos:
      - Uid, Gid (real, efectivo, saved, filesystem)
      - VmSize, VmRSS, VmData, VmStk, VmExe, VmLib, VmHWM, VmSwap (memoria)
      - Threads
      - SigBlk, SigIgn, SigCgt, SigPnd, ShdPnd (máscaras de señales)
      - voluntary_ctxt_switches, nonvoluntary_ctxt_switches
      - Cpus_allowed_list

    Retorna un dict, o None si el proceso no existe.
    """
    try:
        with open(f'/proc/{pid}/status') as f:
            lineas = f.readlines()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    datos = {}
    for linea in lineas:
        if ':' not in linea:
            continue
        clave, _, valor = linea.partition(':')
        datos[clave.strip()] = valor.strip()

    # Campos de memoria: vienen como "8192 kB", nos quedamos con el número
    campos_memoria = ['VmSize', 'VmRSS', 'VmData', 'VmStk',
                      'VmExe', 'VmLib', 'VmHWM', 'VmSwap']
    for campo in campos_memoria:
        if campo in datos:
            try:
                # "8192 kB" → 8192
                datos[campo] = int(datos[campo].split()[0])
            except (ValueError, IndexError):
                datos[campo] = 0
        else:
            datos[campo] = 0

    # UIDs y GIDs: vienen como "1000 1000 1000 1000" (real efectivo saved fs)
    for campo in ('Uid', 'Gid'):
        if campo in datos:
            try:
                partes = datos[campo].split()
                datos[campo] = {
                    'real':      int(partes[0]),
                    'efectivo':  int(partes[1]),
                    'saved':     int(partes[2]),
                    'fs':        int(partes[3]),
                }
            except (ValueError, IndexError):
                datos[campo] = {'real': 0, 'efectivo': 0, 'saved': 0, 'fs': 0}

    # Threads: viene como string, lo convertimos a int
    if 'Threads' in datos:
        try:
            datos['Threads'] = int(datos['Threads'])
        except ValueError:
            datos['Threads'] = 0

    # Context switches
    for campo in ('voluntary_ctxt_switches', 'nonvoluntary_ctxt_switches'):
        if campo in datos:
            try:
                datos[campo] = int(datos[campo])
            except ValueError:
                datos[campo] = 0

    return datos


# ---------------------------------------------------------------------------
# Lectura de /proc/<pid>/cmdline
# ---------------------------------------------------------------------------

def leer_cmdline(pid):
    """
    Lee /proc/<pid>/cmdline — el comando completo con todos sus argumentos.

    A diferencia de 'nombre' en stat (que está truncado a 15 chars),
    cmdline tiene el comando completo. Los argumentos están separados
    por caracteres nulos (\x00) en vez de espacios.

    Si está vacío, el proceso es un proceso de kernel (entre corchetes).

    Retorna un string, o None si el proceso no existe.
    """
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            contenido = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    if not contenido:
        # Proceso de kernel: mostramos el nombre entre corchetes
        stat = leer_stat(pid)
        if stat:
            return f"[{stat['nombre']}]"
        return None

    # Reemplazamos los nulos por espacios para que sea legible
    return contenido.replace(b'\x00', b' ').decode('utf-8', errors='replace').strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pid_existe(pid):
    """Chequeo rápido: ¿existe este PID en /proc?"""
    return os.path.exists(f'/proc/{pid}')


def nombre_usuario(uid):
    """
    Convierte un UID numérico al nombre de usuario.
    Lee /etc/passwd directamente (sin usar pwd module para mantener
    la filosofía de leer archivos del sistema a mano).
    """
    try:
        with open('/etc/passwd') as f:
            for linea in f:
                partes = linea.split(':')
                if len(partes) >= 3 and int(partes[2]) == uid:
                    return partes[0]
    except (FileNotFoundError, ValueError):
        pass
    return str(uid)  # Si no encontramos el nombre, devolvemos el número