#!/usr/bin/env python3

import argparse
import pwd
import grp
import stat
from datetime import datetime
from pathlib import Path


def format_size(size_bytes: int, include_kb: bool) -> str:
	if include_kb:
		size_kb = size_bytes / 1024
		return f"{size_bytes} bytes ({size_kb:.2f} KB)"
	return f"{size_bytes} bytes"


def format_permissions(mode: int) -> str:
	symbolic = stat.filemode(mode)[1:]
	numeric = stat.S_IMODE(mode)
	return f"{symbolic} ({numeric:o})"


def format_time(timestamp: float) -> str:
	return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def get_file_type(path_obj: Path, mode: int) -> str:
	if stat.S_ISLNK(mode):
		target = path_obj.readlink()
		return f"enlace simbólico -> {target}"
	if stat.S_ISREG(mode):
		return "archivo regular"
	if stat.S_ISDIR(mode):
		return "directorio"
	if stat.S_ISCHR(mode):
		return "dispositivo de caracteres"
	if stat.S_ISBLK(mode):
		return "dispositivo de bloques"
	if stat.S_ISFIFO(mode):
		return "FIFO/pipe"
	if stat.S_ISSOCK(mode):
		return "socket"
	return "tipo desconocido"


def resolve_owner(uid: int) -> str:
	try:
		return pwd.getpwuid(uid).pw_name
	except KeyError:
		return "desconocido"


def resolve_group(gid: int) -> str:
	try:
		return grp.getgrgid(gid).gr_name
	except KeyError:
		return "desconocido"


def inspect_path(path: str) -> None:
	path_obj = Path(path)

	try:
		st = path_obj.lstat()
	except FileNotFoundError:
		print(f"Error: no existe '{path}'")
		return
	except PermissionError:
		print(f"Error: sin permisos para acceder a '{path}'")
		return
	except OSError as exc:
		print(f"Error al inspeccionar '{path}': {exc}")
		return

	file_type = get_file_type(path_obj, st.st_mode)
	owner = resolve_owner(st.st_uid)
	group = resolve_group(st.st_gid)

	print(f"Archivo: {path}")
	print(f"Tipo: {file_type}")

	include_kb = stat.S_ISREG(st.st_mode)
	print(f"Tamaño: {format_size(st.st_size, include_kb)}")

	print(f"Permisos: {format_permissions(st.st_mode)}")
	print(f"Propietario: {owner} (uid: {st.st_uid})")
	print(f"Grupo: {group} (gid: {st.st_gid})")
	print(f"Inodo: {st.st_ino}")
	print(f"Enlaces duros: {st.st_nlink}")
	print(f"Creación: {format_time(st.st_ctime)}")
	print(f"Última modificación: {format_time(st.st_mtime)}")
	print(f"Último acceso: {format_time(st.st_atime)}")

	if stat.S_ISDIR(st.st_mode):
		try:
			entries_count = sum(1 for _ in path_obj.iterdir())
			print(f"Contenido: {entries_count} elementos")
		except PermissionError:
			print("Contenido: sin permisos")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Inspecciona información de un archivo o directorio")
	parser.add_argument("ruta", help="Ruta al archivo o directorio a inspeccionar")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	inspect_path(args.ruta)


if __name__ == "__main__":
	main()
