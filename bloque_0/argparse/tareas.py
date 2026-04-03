"""Ejercicio: Tareas con subcomandos
    Subcomando add:
        Argumento posicional: descripción de la tarea
        --priority: prioridad (choices: baja, media, alta)
    Subcomando list:
        --pending: mostrar solo pendientes
        --done: mostrar solo completadas
        --priority NIVEL: filtrar por prioridad
    Subcomando done:
        Argumento posicional: ID de la tarea
    Subcomando remove:
        Argumento posicional: ID de la tarea
        Pedir confirmación antes de eliminar

Para los subcomandos, usás parser.add_subparsers(). Cada subcomando puede tener su propio conjunto de argumentos.

Las tareas deben persistir entre ejecuciones. Guardá en un archivo JSON en ~/.tareas.json. Usá pathlib.Path.home() para obtener el directorio home del usuario.
"""

import argparse
import json
import sys
from pathlib import Path


TASKS_FILE = Path.home() / ".tareas.json" # path del archivo de tareas

# Para leer el archivo de tareas
def load_tasks():
    # Si el archivo no existe, retornar una lista vacía
    if not TASKS_FILE.exists():
        return []

    with TASKS_FILE.open("r", encoding="utf-8") as file: # abre el archivo de tareas en modo lectura
        data = json.load(file) # carga el contenido del archivo JSON en la variable data

    return data if isinstance(data, list) else []

# Para guardar tareas con el subcomando add
def save_tasks(tasks):
    with TASKS_FILE.open("w", encoding="utf-8") as file:
        json.dump(tasks, file, indent=4, ensure_ascii=False)

# Para generar un nuevo ID de tarea único
def next_task_id(tasks):
    if not tasks:
        return 1

    return max(task["id"] for task in tasks) + 1

# para subcomando list. verifica si una tarea coincide con los filtros especificados
def matches_filters(task, args):
    # Si se especifica --pending, solo mostrar tareas que no estén marcadas como hechas
    if args.pending and task.get("done", False):
        return False
    # Si se especifica --done, solo mostrar tareas que estén marcadas como hechas
    if args.done and not task.get("done", False):
        return False
    # Si se especifica --priority, solo mostrar tareas que coincidan con esa prioridad
    if args.priority and task.get("priority") != args.priority:
        return False
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Gestor de tareas con subcomandos",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Argumentos por subcomando:\n"
            "  add DESCRIPTION [--priority {baja,media,alta}]\n"
            "  list [--pending] [--done] [--priority {baja,media,alta}]\n"
            "  done ID\n"
            "  remove ID [--confirm]\n"
            "\n"
            "Ayuda detallada: tareas.py <subcomando> --help"
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="subcomandos",
        metavar="{add,list,done,remove}",
    )

    # Subcomando add
    add_parser = subparsers.add_parser("add", help="Agregar una nueva tarea") # Crear subparser para el comando "add"
    add_parser.add_argument("description", help="Descripción de la tarea")
    add_parser.add_argument("--priority", choices=["baja", "media", "alta"], default="media", help="Prioridad de la tarea (default: media)")

    # Subcomando list
    list_parser = subparsers.add_parser("list", help="Listar tareas")
    list_parser.add_argument("--pending", action="store_true", help="Mostrar solo pendientes")
    list_parser.add_argument("--done", action="store_true", help="Mostrar solamente tareas completadas")
    list_parser.add_argument("--priority", choices=["baja", "media", "alta"], help="Filtrar por prioridad")

    # Subcomando done
    done_parser = subparsers.add_parser("done", help="Marcar una tarea como completada")
    done_parser.add_argument("id", help="ID de la tarea")

    # Subcomando remove
    rm_parser = subparsers.add_parser("remove", help="Eliminar una tarea")
    rm_parser.add_argument("id", help="ID de la tarea a eliminar")
    rm_parser.add_argument("--confirm", action="store_true", help="Confirmar eliminación")

    args = parser.parse_args()

    ###################################

    # SUBCOMANDO ADD
    if args.command == "add":
        tasks = load_tasks()
        new_task = {
            "id": next_task_id(tasks),
            "description": args.description,
            "priority": args.priority,
            "done": False,
        }
        tasks.append(new_task)
        save_tasks(tasks) # save_tasks() guarda la lista de tareas actualizada en el archivo JSON. Si el archivo no existe, lo crea.
        print(f"Tarea agregada: '{args.description}' con prioridad '{args.priority}'")

    # SUBCOMANDO LIST
    elif args.command == "list":
        if args.pending and args.done:
            print("No podés usar --pending y --done al mismo tiempo.")
            sys.exit(1)

        tasks = load_tasks()
        filtered_tasks = [task for task in tasks if matches_filters(task, args)]

        print("LISTA DE TAREAS")

        if not filtered_tasks:
            print("No hay tareas que coincidan con los filtros.")
        else:
            for task in filtered_tasks:
                status = "Completada" if task.get("done", False) else "Pendiente"
                print(f"{task['id']}: {task['description']} (Prioridad: {task['priority']}, Estado: {status})")
    elif args.command == "done":
        tasks = load_tasks()
        task_id = int(args.id)
        
        for task in tasks:
            if task["id"] == task_id:
                task["done"] = True
                save_tasks(tasks)
                print(f"Tarea con id {args.id} marcada como completada")
                break
        else:
            print(f"No existe una tarea con id {args.id}")
            sys.exit(1)

    # SUBCOMANDO REMOVE
    elif args.command == "remove":
        if not args.confirm:
            print(f"¿Estás seguro de que quieres eliminar la tarea con id {args.id}? Usa --confirm para confirmar.")
            sys.exit(1)
        
        tasks = load_tasks()
        task_id = int(args.id)
        filtered_tasks = [task for task in tasks if task["id"] != task_id]
        
        if len(filtered_tasks) == len(tasks):
            print(f"No existe una tarea con id {args.id}")
            sys.exit(1)
        
        save_tasks(filtered_tasks)
        print(f"Tarea con id {args.id} eliminada")
    else:
        print("Comando no reconocido. Usa --help para ver los comandos disponibles.")
        sys.exit(1)

if __name__ == "__main__":
    main()