# Guía de estudio del TP2

Este archivo es para estudiar el trabajo y prepararse para la corrección. El informe
formal es el `README.md`. Podés dejarlo en el repo o sacarlo antes de entregar.

> Recordatorio de la consigna: **"Si no podés explicar tu propio código, no aprueba"**.
> La idea es que, al terminar esta guía, puedas explicar cada decisión sin mirar.

---

## 1. La idea en 30 segundos

Un servidor HTTP recibe pedidos de trabajo. **No los hace en el momento**: los anota,
los pone en una fila y responde "anotado, tu número es el 7". Atrás hay N "empleados"
(workers) que van sacando trabajos de la fila y los hacen. El cliente pregunta después
"¿cómo va el 7?".

Lo interesante es que **todo corre en un solo thread**. Los empleados no son threads:
son corrutinas que, mientras esperan algo (la red, un timer, que llegue trabajo), le
ceden el thread a los demás. Eso funciona perfecto para esperar (I/O), pero no para
calcular (CPU): un empleado que se pone a calcular no le cede el thread a nadie. Por
eso el cálculo se manda a **otros procesos**.

---

## 2. Orden sugerido para leer el código

Leelo en este orden. Para cada archivo: primero el concepto, después qué mirar en el
código, y al final la idea para llevarse.

### Paso 1 — `app/modelos.py` (5 min)

**Concepto**: Pydantic valida los datos de entrada antes de que lleguen a tu código.

**Qué mirar**: `Estado` (los 5 estados), y `TareaNueva`, que es una *unión discriminada*:
Pydantic mira el campo `tipo` y según eso valida `parametros` con `ParamsDescargar`,
`ParamsHashear` o `ParamsEsperar`.

**Para llevarse**: si mandás `{"tipo":"hashear","parametros":{}}`, FastAPI responde
`422` solo. Nunca llega a `motor.py`.

### Paso 2 — `app/registro.py` (10 min)

**Concepto**: el estado de todo el sistema es un `dict` en memoria. **Sin lock.**

**Qué mirar**: la clase `Tarea` (un dataclass con todos los campos) y `Registro`, con
los métodos que hacen las transiciones: `crear`, `iniciar`, `terminar`. Fijate que
`terminar` no hace nada si la tarea ya estaba en un estado final.

**Para llevarse**: ningún método tiene `await`. Por eso no hace falta lock: en asyncio
solo se cambia de corrutina en un `await`, así que cada método corre entero sin que
nadie se meta en el medio.

### Paso 3 — `app/tareas/esperar.py` y `hashear.py` (15 min)

**Concepto**: la diferencia entre ceder el control y no cederlo.

**Qué mirar**:
- `esperar.py`: `await asyncio.sleep(...)`. El `await` suspende esta corrutina y el loop
  atiende a otros.
- `hashear.py`: la función `hash_iterado` es un `for` puro sin `await`. En modo
  `directo` se llama directamente (bloquea todo). En modo `proceso` se llama con
  `await loop.run_in_executor(ctx.pool_cpu, hash_iterado, h, n)`: corre en otro proceso.
- El `while hechas < total` que manda el trabajo **en bloques**. Entre bloque y bloque
  hay un `await`: ahí puede entrar una cancelación o un timeout.

**Para llevarse**: "si la función no tiene `await`, el loop está trabado mientras corre".

### Paso 4 — `app/tareas/descargar.py` (15 min)

**Concepto**: muchas esperas de red al mismo tiempo.

**Qué mirar**:
- `async with asyncio.TaskGroup() as grupo:` crea una tarea por URL. Al salir del
  bloque, todas terminaron. Si cancelan a la tarea madre, el TaskGroup cancela a las
  hijas **y las espera**.
- `async with sem:` → como mucho 20 descargas a la vez.
- `async with ctx.http.stream(...)` → la respuesta se cierra siempre, aunque haya
  cancelación.
- `except asyncio.CancelledError: raise` → **nunca** tragarse la cancelación.
- El modo `secuencial`: `[await una(u) for u in urls]`. Es el "for con await adentro".

**Para llevarse**: la medición 1 es exactamente la diferencia entre esas dos formas.

### Paso 5 — `app/motor.py` (30 min, el más importante)

**Concepto**: productor-consumidor con `asyncio.Queue`.

**Qué mirar, en este orden**:
1. `__init__`: la cola con `maxsize`, el dict `en_curso` (id → ejecución).
2. `encolar`: `put_nowait`. Si la cola está llena → excepción `ColaLlena` → 503.
3. `_worker`: el bucle infinito. `await cola.get()`, procesar, `task_done()` en `finally`.
4. `_procesar`: **el corazón**. Crea la ejecución como tarea hija, la espera, y según
   cómo termine pone el estado final. Leé despacio el `except asyncio.CancelledError`.
5. `_ejecutar`: `async with asyncio.timeout(t.timeout)`.
6. `cancelar`: los dos casos, pendiente y ejecutando.
7. `_worker_termino`: el supervisor que relanza workers muertos.
8. `apagar`: los 5 pasos del apagado ordenado.

**Para llevarse**: dibujá en un papel el worker, la ejecución hija y quién llama a
`.cancel()` sobre quién en cada caso (DELETE, timeout, apagado).

### Paso 6 — `app/main.py` (15 min)

**Concepto**: el `lifespan` crea todo al arrancar y lo libera al apagar.

**Qué mirar**:
- `ciclo_de_vida`: todo lo que está antes del `yield` es el arranque; lo que está en el
  `finally` es el apagado. Ahí se crea el `ProcessPoolExecutor` (una sola vez), el
  `httpx.AsyncClient` (uno solo) y el `Motor`.
- Los endpoints: son cortos porque delegan en el motor y el registro.
- `eventos` (WebSocket): las dos corrutinas `mandar` y `escuchar_cierre`, y por qué
  hicieron falta (el bug del apagado colgado, ver README).
- Al final, `if __name__ == '__main__':`, y por qué es obligatorio con `spawn`.

### Paso 7 — `app/persistencia.py` (5 min)

**Qué mirar**: escritura atómica (temporal + `os.replace`). En `main.py`, se llama con
`asyncio.to_thread` porque escribir a disco bloquea.

### Paso 8 — `tests/test_api.py` (10 min)

Cada test es una afirmación del README hecha código. Leé los nombres de los tests:
son la lista de cosas que el sistema garantiza.

---

## 3. Las preguntas de la corrección (de la consigna), con respuesta

### "Mostrame dónde tu código podría bloquear el event loop."

En `hashear.py`, el modo `directo`: llama a `hash_iterado` sin executor. Es a propósito,
para la medición 2, y está **deshabilitado por defecto**: `POST` responde `403` salvo que
el servidor arranque con `PERMITIR_MODO_DIRECTO=1` (el chequeo está en `crear_tarea`,
en `main.py`). Fuera de eso, revisé: no hay `time.sleep`, no uso `requests`, el
volcado JSON y el `pool.shutdown` van con `asyncio.to_thread`. Lo único que podría
pesar es `/estadisticas` con millones de tareas, porque recorre el dict entero (es O(n)).

### "¿Qué pasa si cancelo una tarea justo cuando está a mitad de una descarga?"

`DELETE` llama a `.cancel()` sobre la ejecución. Eso inyecta `CancelledError` en el
`await` donde está parada: probablemente leyendo un pedazo en `aiter_bytes()`. La
excepción sube: el `async with ctx.http.stream(...)` cierra la respuesta, el
`async with sem` libera el semáforo, y el `TaskGroup` cancela a las otras descargas y
espera a que terminen. Ninguna corrutina queda huérfana; hay un test que lo verifica.

### "¿Por qué tu pool de workers no necesita un `Lock`?"

Porque todos los workers son corrutinas del mismo thread, y una corrutina solo cede el
control en un `await`. Los métodos que modifican el estado (`Registro`) no tienen ningún
`await` adentro, así que se ejecutan enteros, sin interrupción. Con threads el SO puede
cortar en cualquier instrucción, y ahí sí haría falta un lock (clase 11). Y la cola ya
resuelve sola la coordinación entre productor y consumidores.

### "Si te mando 10.000 tareas de golpe, ¿qué se rompe primero?"

La cola, a propósito: tiene `maxsize=1000`. Después de llenarse, los POST reciben `503`
con `Retry-After`. Lo medí: de 3000 tareas, 1465 aceptadas y 1535 rechazadas (medición
3C). Si subo `COLA_MAX`, entran todas, y lo siguiente es el ritmo al que el event loop
procesa POSTs (un solo thread). Después, la memoria del registro, porque nunca borra.

### "¿Qué diferencia hay entre `asyncio.gather` y un `for` con `await` adentro?"

El `for` espera a que termine cada una antes de *empezar* la siguiente: tarda la suma.
`gather` (o `TaskGroup`) las lanza todas y después espera a todas: tarda lo que la más
lenta. Medición 1: 12,69 s contra 0,91 s. Además, `TaskGroup` (que es lo que uso) tiene
una ventaja sobre `gather`: si una falla, cancela a las demás en vez de dejarlas
huérfanas (clase 21).

### "¿Por qué `time.sleep()` en una corrutina es un bug y `asyncio.sleep()` no?"

`time.sleep` duerme el **thread**, y como el event loop es un solo thread, se duerme
todo el servidor. `asyncio.sleep` es una corrutina: suspende solo a la corrutina que la
llamó, le devuelve el control al loop, y el loop la despierta cuando pasa el tiempo.
Mientras, atiende a todos los demás. La medición 2 en modo `directo` es el mismo efecto.

### Otras que pueden caer

- **¿Por qué procesos y no threads para el hash?** El GIL. Medido: con threads el GET
  tarda 14 ms; con procesos, 3,5 ms. Y dos hashes en threads no corren en paralelo.
- **¿Por qué `asyncio.Queue` y no `queue.Queue`?** `queue.Queue.get()` bloquea el thread,
  que es el único que hay. `asyncio.Queue.get()` suspende la corrutina.
- **¿Qué pasa si un worker lanza una excepción?** Tres niveles: la tarea pasa a
  `fallida`; si el error es del worker, se loguea y sigue; si igual muere, el supervisor
  lo reemplaza.
- **¿Por qué el `task_done()` va en un `finally`?** Si una tarea falla y no se llama,
  la cuenta de la cola queda desbalanceada y un `join()` esperaría para siempre.
- **¿Qué hace `cancelling()`?** Dice si alguien pidió cancelar a la tarea *actual*. Lo
  uso para distinguir si cancelaron a la ejecución (DELETE: el worker sigue) o al
  worker (apagado: el worker termina).
- **¿Por qué `spawn` y la guarda `if __name__ == '__main__'`?** Con `spawn`, cada
  proceso del pool arranca un intérprete nuevo que re-importa el módulo principal.
  Sin la guarda, cada proceso hijo levantaría otro servidor.
- **¿Por qué el CMD del Dockerfile es una lista?** Forma exec: Python es el PID 1 y
  recibe el SIGTERM. Con la forma shell lo recibe `/bin/sh` y no lo reenvía.

---

## 4. Experimentos para hacer vos (para entender, no para entregar)

Hacé cada uno, mirá qué pasa, y deshacé el cambio.

1. **Romper el loop a mano**: en `esperar.py`, cambiá `await asyncio.sleep(...)` por
   `time.sleep(...)`. Mandá una tarea `esperar` de 5 s y, mientras, un `GET /tareas`.
2. **Tragarse la cancelación**: en `descargar.py`, sacá el `raise` del
   `except asyncio.CancelledError`. Cancelá una descarga en curso. ¿Qué estado queda?
3. **Olvidarse del `task_done`**: sacalo del `finally` de `_worker`. ¿Se nota algo?
   (Pista: acá no, porque no uso `cola.join()`. En `cola.py` de la clase 21 sí se nota.)
4. **Un solo worker**: `WORKERS=1` en el compose. Mandá tres `esperar` de 5 s. Mirá
   `espera_en_cola` de cada una.
5. **Cola chica**: `COLA_MAX=2`, `WORKERS=1`. Mandá 5 tareas rápido. ¿Cuáles dan 503?
6. **Medición 2 en tu máquina**: corré `medir_bloqueo.py`. Si tu máquina tiene más
   núcleos, probá `medir_techo.py --b 1 2 4 8 16` y fijate dónde se dobla la curva.
7. **WebSocket en vivo**: conectate a `/eventos` (con `websocat` o desde la consola del
   navegador: `new WebSocket('ws://localhost:8000/eventos').onmessage = e => console.log(e.data)`)
   y mandá tareas.

---

## 5. Checklist antes de entregar (03/11)

- [ ] `docker compose up --build` en tu máquina, y probar los `curl` del README.
- [ ] Probar `Ctrl+C` / `docker compose stop` y ver el `estado_*.json` en `volcados/`.
- [ ] Correr las tres mediciones **en tu máquina** y reemplazar los números del README
      con los tuyos (la consigna pide "números tuyos"). Los scripts imprimen tablas
      listas para copiar. Si cambian mucho, ajustá también la interpretación (por
      ejemplo, la 3B depende de cuántos núcleos tengas).
- [ ] Escribir la sección **7. Lo que aprendí** con tus palabras.
- [ ] Poner tu nombre y legajo arriba del README.
- [ ] Sacar del README, en "Limitaciones", el punto de "no pude probar docker compose".
- [ ] (Opcional) Crear `dudas.md` con lo que te haya quedado dando vueltas.
- [ ] Subir al repo público de GitHub y verificar que se clona y levanta "sin pasos extra".
- [ ] Repasar las preguntas de la sección 3 de esta guía en voz alta, sin mirar.

---

## 6. Glosario rápido

| Término | En una línea |
|--|--|
| Event loop | El bucle que decide qué corrutina corre ahora; duerme en `epoll` hasta que haya algo listo |
| Corrutina | Función `async def`; se puede pausar en cada `await` y retomar después |
| `await` | "Esperá esto, y mientras tanto dejá correr a otros" |
| Task | Una corrutina que el loop ejecuta por su cuenta (`create_task`); se puede cancelar |
| `CancelledError` | La excepción que aparece en el `await` de una tarea cancelada |
| I/O-bound | Pasa casi todo el tiempo esperando (red, disco, timers) → asyncio sirve |
| CPU-bound | Pasa casi todo el tiempo calculando → asyncio no sirve, hacen falta procesos |
| GIL | Lock del intérprete: un solo thread ejecuta bytecode Python a la vez |
| Executor | Pool de threads o procesos al que se le mandan funciones comunes |
| Backpressure | Frenar o rechazar al productor cuando el consumidor no da abasto (`maxsize`) |
| Lifespan | El código de arranque y apagado de una app FastAPI |