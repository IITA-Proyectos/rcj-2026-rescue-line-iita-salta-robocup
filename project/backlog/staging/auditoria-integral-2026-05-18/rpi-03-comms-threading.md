# Auditoría integral 2026-05-18 — RPi · Módulo COMMS + THREADING

**Dominio:** Serial RPi→Teensy (`send_frame`, clamp, flush, parser de bytes de control) + concurrencia (hilos de cámara, inferencia, captura, monitor serial; colas `frame_q`/`result_q`; manejo de `WebcamVideoStream`).
**Archivos analizados (leídos completos):**
- `software/raspberry/final_rpi/Main.py` (849 líneas)
- `software/raspberry/final_rpi/camthreader.py` (43 líneas)
- `software/raspberry/final_rpi/calibration.py` (50 líneas, solo herramienta de calibración offline)

**Branch:** `feature/initialize-testing-log` (contenido también en `main` tras PR #101).
**Filosofía del informe:** cada hallazgo es un **TEMA A ANALIZAR**, no una orden de fix. Cada uno trae *riesgo-de-no-cambiar*, *riesgo-de-cambiar* y *estimación de tiempo realista* (incluye banco + pista + anotar `TEST_LOG.md`). El equipo decide **Tomar / Posponer / Descartar**.

> ⚠️ **Solo lectura.** Este informe no modifica código. No abre Issues. Cita los Issues existentes y agrega lo nuevo.

---

## 0. Resumen ejecutivo

El módulo comms+threading **mejoró sustancialmente** desde la auditoría de comms del 2026-05-10 (Issues #66–#77). El commit `5bac4a5`/`86dca44` ya incorporó al código real:

- `send_frame()` con **clamp a [0,255]** vía `clamp_byte()` y **`ser.flush()`** → **#66 quedó implementado** (verificado en `Main.py:94-116`).
- `serial.Serial(..., timeout=0.05, write_timeout=0.05)` → **#73 implementado** (verificado en `Main.py:67`).
- Telemetría TX `[TLM] frames_sent=...` cada 5 s → **#75 implementado parcialmente** (solo lado TX, falta RX).
- `read_frame_with_recovery()` con guard de `frame is None` + auto-restart del stream tras 30 frames vacíos → mitiga parte de **#65/#113**.
- Drenado de colas en el `finally` de `modo_rescate()` (comentado como "FIX ZOMBI") → mitiga parte de **#111 (R-V11)**.

**Pero el corazón de la concurrencia sigue roto.** Los tres agujeros CRÍTICOS de la auditoría de resiliencia siguen **abiertos y sin tocar en el código**:

- **#113 — `camthreader` sin `threading.Lock`**: confirmado, el `Lock` no existe (`camthreader.py` completo, 43 líneas, no importa `Lock`). Frame desgarrado/stale bajo carga.
- **#111 — `infer_thread()` sin `try/except`**: confirmado (`Main.py:452-503`). Una excepción de `interpreter.invoke()` mata el hilo en silencio y deadlockea el rescate.
- **#108 — sin auto-restart de proceso**: fuera de dominio comms estricto, pero amplifica TODO lo de abajo: cualquier excepción no capturada = Pi ciega permanente.

Y aparecen **hallazgos NUEVOS de esta pasada** que las auditorías previas no listaron, casi todos de **concurrencia sobre recursos compartidos** (`ser`, `vs`, `estado`) accedidos desde 3–4 hilos sin sincronización:

| ID | Hallazgo nuevo | Prioridad sugerida |
|---|---|---|
| **CT-01** | `ser` (objeto serial) escrito por main-loop y leído por `serial_monitor_local` **sin lock** → write/read concurrentes sobre el mismo fd | **P1** |
| **CT-02** | `ser.flush()` en `send_frame` es **bloqueante** y ahora hay `write_timeout=0.05`: si el buffer del kernel se llena, `write`/`flush` puede tirar `SerialTimeoutException` no capturada → mata el loop | **P1** |
| **CT-03** | `estado` (global) mutado desde `serial_monitor_local` (hilo) y desde main-loop **sin lock ni `volatile`-equivalente** → TOCTOU en transiciones de FSM | **P1** |
| **CT-04** | `restart_video_stream()` rebind del global `vs` **mientras `capture_thread` retiene la referencia vieja** → el hilo de captura sigue leyendo el stream muerto; el restart no lo alcanza | **P1** |
| **CT-05** | `frame_q.put(frame)` **bloqueante** con `MAX_QUEUE=2` (saturación) → si `infer_thread` se atrasa o muere, `capture_thread` se cuelga; combinado con #111 es el deadlock de 3 hilos | **P1** (refuerza #111) |
| **CT-06** | `infer_thread` usa `frame_q.get()` **sin timeout** y depende del sentinel `None`; si el sentinel se drena antes (carrera con el `finally`) el hilo queda colgado para siempre | **P2** (refuerza #111/R-V11) |
| **CT-07** | El `result_q.put(...)` en `infer_thread` es **bloqueante** con `MAX_QUEUE=2`: si `main_loop` sale por `stop_rescate` y deja de consumir, `infer_thread` se cuelga en el `put` antes de poder ver el sentinel | **P2** |
| **CT-08** | `WebcamVideoStream.read()` puede devolver el **primer frame `None`** (cámara aún no entregó frame en `__init__`) y `update()` no chequea `grabbed` antes de pisar `self.frame` | **P2** (refuerza #113) |
| **CT-09** | Hilos `capture`/`infer`/`serial_monitor` son `daemon=True` con `join(timeout=1)`: si no joinean a tiempo quedan **vivos en el próximo ciclo de rescate** compartiendo `interpreter`/`ser`/colas nuevas → corrupción cruzada | **P2** (refuerza #111/R-V11) |
| **CT-10** | No hay **heartbeat TX periódico garantizado**: en estado `esperando` la Pi no manda `speed=0`; depende 100% del lado Teensy (#53). El TX solo ocurre dentro de los loops de `linea`/`rescate` | **P1** (lado RPi de #53) |
| **CT-11** | `print()` de debug en hot-path serial/visión (`Main.py:798 print(area)` por contorno, telemetría, warnings) compite por el GIL y puede bloquear si stdout va a una tty lenta/llena | **P2** |

A continuación el detalle de cada uno.

---

## 1. Estado de los Issues previos (verificación sobre el código actual)

No repito el análisis de estos Issues; **confirmo o corrijo su estado** contra el checkout actual y agrego matices nuevos.

### 1.1 #66 — `ser.write()` sin clamp ni flush → **IMPLEMENTADO** (con caveat nuevo, ver CT-02)
`Main.py:94-116`. `clamp_byte()` existe y se aplica a los 4 payloads; `ser.flush()` está presente. **El bug original de #66 ya no aplica**: `clamp_byte(angle + 90)` nunca tira `ValueError` porque clampa a [0,255] antes de `bytes([...])`.
**Matiz nuevo:** el clamp es **silencioso**. Si `angle` viniera fuera de rango (p. ej. `-error_norm*90` con `error_norm` mal calculado), el clamp tapa el síntoma sin loguear. Para comms eso es aceptable (preferible a crashear), pero conviene un contador de clamps (relacionar con la telemetría de #75). **No es regresión, es deuda menor.**

### 1.2 #73 — serial sin timeout → **IMPLEMENTADO**
`Main.py:67`: `serial.Serial('/dev/serial0', 115200, timeout=SERIAL_TIMEOUT_S, write_timeout=SERIAL_TIMEOUT_S)` con `SERIAL_TIMEOUT_S = 0.05`. El read-timeout cierra el riesgo de cuelgue en `ser.read()`. **Pero** se agregó `write_timeout=0.05`, que introduce CT-02 (excepción de escritura ahora posible). El issue #73 pedía solo `timeout`; el `write_timeout` es un add-on no contemplado en su test plan.

### 1.3 #75 — sin telemetría RX/TX → **PARCIAL (solo TX)**
`Main.py:110-114`: cuenta `frames_sent` y emite `[TLM] frames_sent=... estado=...` cada 5 s. **Falta el lado RX** (cuántos bytes de control llegaron del Teensy, cuántos frames completó el Teensy). Sin RX no se puede diagnosticar el caso "la Pi manda pero el Teensy no recibe / no completa frame". Sigue siendo P2.

### 1.4 #113 — `camthreader` sin Lock → **ABIERTO, sin tocar (CRÍTICO)**
`camthreader.py` completo (43 líneas) **no importa `Lock` ni lo usa**. `update()` (L25-32) hace `(self.grabbed, self.frame) = self.stream.read()` y `read()` (L34-36) hace `return self.frame` sin sincronización. Confirmado al 100%. Ver detalle ampliado en CT-08 (hay además un sub-bug de `grabbed` no chequeado). **Este es, en mi opinión, el hallazgo de comms+threading de mayor relación impacto/esfuerzo del lote.**

### 1.5 #111 — `infer_thread` sin try/except → **ABIERTO, sin tocar (CRÍTICO)**
`Main.py:452-503`: el `while True` de `infer_thread` no tiene `try/except`. `interpreter.invoke()` (L479) puede tirar y matar el hilo. El `finally` de `modo_rescate` (L689-705) **sí** agregó el drenado de colas (mitiga R-V11 parcialmente) y `join(timeout=...)`, pero **no** agregó el respawn ni el `is_alive()` check que pedía #111. Ver CT-05/CT-06/CT-07/CT-09 que amplían la cadena de deadlock.

### 1.6 #53 — heartbeat bidireccional → lado RPi sigue débil (ver CT-10)
La telemetría TX de #75 **no es un heartbeat**: no garantiza envío periódico de `speed=0` cuando la Pi está en `esperando` o entre estados. Ver CT-10.

### 1.7 #108 — sin auto-restart de proceso → contexto amplificador
Fuera del dominio comms estricto, pero **toda** excepción no capturada de esta lista (CT-02, CT-03, frame corrupto de #113) termina en proceso muerto y Pi ciega porque no hay systemd. Lo cito como multiplicador de severidad, no lo re-analizo.

---

## 2. Hallazgos NUEVOS — detalle

### CT-01 · `ser` compartido entre main-loop y `serial_monitor_local` sin lock — **P1**

**Dónde:**
- Escritura: `send_frame()` → `ser.write(output); ser.flush()` (`Main.py:107-108`), llamado desde `main_loop()` (`Main.py:663`) y desde el loop de línea (`Main.py:814`).
- Lectura: `serial_monitor_local()` → `if ser.in_waiting > 0: data = ser.read()` (`Main.py:544-545`), corriendo en `t_serial_mon` (`Main.py:557`, `daemon=True`).

**Qué pasa:** durante `modo_rescate()` hay **dos hilos tocando el mismo `serial.Serial`**: `main_loop` (hilo principal) escribe; `serial_monitor_local` (hilo) lee. `pyserial` sobre un fd POSIX **no es thread-safe para operaciones concurrentes**. Aunque read y write van a endpoints distintos del mismo device, comparten estado interno de pyserial (flags, `in_waiting`, manejo de timeout) y el `flush()` del writer puede entrelazarse con el `read()` del reader. En la práctica el síntoma típico es **lectura de un byte de control a destiempo** o un `OSError`/`SerialException` esporádico bajo carga — que, sin `try/except` de último recurso (#108), mata el proceso.

**Riesgo de no cambiar:** medio-alto. Es un bug de concurrencia clásico, intermitente, que aparece **más bajo carga/calor** (justo en competencia). Difícil de reproducir en banco frío. `serial_monitor_local` **sí** tiene `try/except` interno (L553) que loguea y sigue, lo que reduce el riesgo de muerte, pero no elimina la corrupción de un byte de control leído mal (p. ej. interpretar un ACK como `0xFF` STOP → frena el robot a mitad de rescate).
**Riesgo de cambiar:** bajo-medio. Un `threading.Lock` sostenido microsegundos alrededor de `write+flush` y de `in_waiting+read` no afecta FPS. El riesgo es olvidar un sitio de acceso a `ser` (hay 3 writes y 3 reads en el archivo).
**Tiempo realista:** 1.5–2.5 h (agregar lock, envolver los 6 accesos, banco 30 min verificando que no baja FPS ni se pierden ACKs, anotar TEST_LOG).
**Relación:** complementa #70/#71/#73 (parser/buffer Teensy) y #53 (heartbeat).

---

### CT-02 · `ser.flush()` bloqueante + `write_timeout=0.05` → `SerialTimeoutException` no capturada — **P1**

**Dónde:** `send_frame()` `Main.py:107-108`:
```python
ser.write(output)
ser.flush()
```
con `ser = serial.Serial(..., write_timeout=SERIAL_TIMEOUT_S)` (`Main.py:67`, 0.05 s).

**Qué pasa:** `write_timeout` hace que, si el buffer de salida del kernel/UART no drena en 50 ms (Teensy lento leyendo, flow control, UART saturado por ACKs entrantes), `ser.write()` lance **`serial.SerialTimeoutException`**. Además, `pyserial`'s `flush()` **bloquea hasta que el OS termina de transmitir**. Estas 2 líneas están en el camino caliente que se ejecuta una vez por frame, tanto en `main_loop` de rescate (L663) como en el loop de línea (L814). **No hay `try/except` alrededor de `send_frame`** en ninguno de los dos call-sites.

Resultado: un único timeout de escritura **mata el loop de línea o el de rescate** → con #108 ausente, Pi ciega. Es exactamente la clase de excepción que la auditoría de resiliencia (#108) enumeró como path de muerte, pero **acá la causa es el `write_timeout` recién agregado** (no estaba en el código viejo, así que es un riesgo introducido por el fix de #73).

Nota fina: el frame son 8 bytes a 115200 baud ≈ 0.7 ms de transmisión real; en operación normal nunca se acerca a 50 ms. El riesgo se materializa solo si el Teensy deja de drenar (su `serialEvent5` consume 1 byte/llamada, ver #70) y el buffer se llena — escenario plausible si el Teensy está en un `while` bloqueante (#27/#63) o en `runAngle180` (#B8).

**Riesgo de no cambiar:** medio. Probabilidad baja en operación nominal, pero el modo de falla es total (proceso muerto) y **correlaciona con otros bugs ya conocidos del Teensy** (#70 drain incompleto, #63 descarta bytes en movimiento): si el Teensy se atasca, la Pi muere por simpatía.
**Riesgo de cambiar:** bajo. Opciones: (a) envolver `send_frame` en `try/except serial.SerialTimeoutException` que loguee y siga; (b) considerar quitar el `flush()` (con timeout de escritura, el write ya garantiza entrega o excepción; el `flush` redundante agrega bloqueo) — **pero** quitar flush cambia timing, requiere banco. La opción (a) es la segura.
**Tiempo realista:** 1–2 h (envolver ambos call-sites, simular Teensy lento desconectando TX, banco, TEST_LOG).
**Relación:** introducido al cerrar #73; amplificado por #70/#63/#27; mortal por ausencia de #108.

---

### CT-03 · `estado` global mutado desde hilo `serial_monitor_local` sin sincronización — **P1**

**Dónde:** `estado` es global (`Main.py:62`). Lo muta:
- `handle_control_byte()` (`Main.py:150-177`): `estado = 'esperando' | 'linea' | 'depositar' | ...` — llamado desde **el hilo** `serial_monitor_local` (L546) **y** desde el main-loop (L717, L828).
- `main_loop()` también escribe `estado = "depositar verde"` (`Main.py:634`).
- La FSM de nivel superior (`Main.py:711-845`) **lee** `estado` para decidir en qué `while` entrar.

**Qué pasa:** transición de estado **TOCTOU** (time-of-check-to-time-of-use). El hilo `serial_monitor_local` puede cambiar `estado` a `'esperando'`/`'depositar'` en cualquier instante mientras `main_loop` está a mitad de una iteración leyendo `estado` (p. ej. en los filtros de clase `if estado == "rescate"` de `infer_thread` L491-496, o en `choose_stable_target(..., estado)` L593). En CPython el GIL hace que la **asignación** de la referencia sea atómica (no hay frame desgarrado de string), así que no crashea; **pero la lógica sí se corrompe**: `infer_thread` puede filtrar detecciones con un `estado` y `main_loop` decidir target con otro, en el mismo frame. El acoplamiento `estado`↔`stop_rescate` (flag local) tampoco es atómico como par.

**Riesgo de no cambiar:** medio. No mata el proceso (GIL salva del crash), pero produce **comportamiento errático intermitente** en las transiciones rescate→depositar→depositar-verde, que son justo las que valen puntos (separar víctimas, depositar en zona correcta). Difícil de depurar porque depende del timing del byte de control.
**Riesgo de cambiar:** bajo-medio. Lo correcto es un `threading.Lock` para las transiciones, o mejor, **que solo el hilo principal mute `estado`** y que `serial_monitor_local` deposite la intención en una `queue`/flag y el main la aplique en un punto definido del loop. Refactor de FSM es delicado en víspera de mundial.
**Tiempo realista:** 2–4 h (diseño mínimo: mover la mutación de `estado` desde el hilo a una bandera consumida por el main; banco de las 3 transiciones; TEST_LOG). Si solo se pone un Lock: 1.5 h.
**Relación:** raíz compartida con #72 (handshake al boot resincroniza `estado`) y #71 (descarte de comandos). El `estado='esperando'` por `TEENSY_BOOT` (L157) es la pieza que #72 quiere robustecer.

---

### CT-04 · `restart_video_stream()` rebind del global `vs` mientras `capture_thread` retiene la referencia vieja — **P1**

**Dónde:**
- `restart_video_stream()` (`Main.py:119-129`): `global vs; vs.stop(); ...; vs = WebcamVideoStream(src=0).start()`.
- Lo llama `read_frame_with_recovery()` (`Main.py:143`) tras 30 frames None.
- **Pero** dentro de `modo_rescate()`, `capture_thread` (`Main.py:442-450`) llama `read_frame_with_recovery(none_count, "rescate-capture")` (L445), que internamente hace `frame = vs.read()` (L133) leyendo **el global `vs`**.

**Qué pasa:** dos problemas encadenados:
1. **Rebind del global desde un hilo daemon.** Si el `capture_thread` dispara el restart (porque la cámara entregó 30 None seguidos), `restart_video_stream()` reasigna el global `vs`. La referencia vieja queda con su propio hilo `update()` (lanzado en `WebcamVideoStream.start()`, `camthreader.py:20-23`) que **nunca se detiene de verdad**: `vs.stop()` setea `self.stopped=True` en el objeto viejo, OK, ese hilo muere; pero si el restart lo dispara el **loop de línea** (hilo principal) mientras un `capture_thread` de un rescate previo siguiera vivo (CT-09), habría dos productores.
2. **`read_frame_with_recovery` mezcla recuperación de dos contextos sobre el mismo global.** El `none_count` es local a cada llamador (línea vs capture), pero `vs` es uno solo. Si el de rescate reinicia `vs`, el contador de línea no se entera, y viceversa. Aceptable, pero frágil.

El riesgo principal real: **`vs.read()` puede correr concurrente con el rebind `vs = ...`**. En CPython la lectura del nombre global `vs` y la asignación son atómicas individualmente (no hay puntero a medio escribir), así que no segfaultea; el peor caso es que `capture_thread` lea un frame del stream **viejo justo antes de que muera**, o del nuevo antes de que esté listo (primer frame None, CT-08). No es catastrófico por sí solo, pero combinado con CT-08 (primer frame None del stream nuevo) puede disparar **otro** ciclo de "30 None → restart" en bucle si la cámara tarda en entregar.

**Riesgo de no cambiar:** medio. La auto-recuperación de cámara es valiosa (la cámara USB puede desconectarse), pero la implementación actual puede entrar en **loop de restart** si la cámara reaparece lento, gastando segundos de corrida. No mata el proceso.
**Riesgo de cambiar:** medio. Tocar la recuperación de cámara es delicado; mal hecho, se pierde la capacidad de recuperarse de un unplug real. Conviene: (a) que el restart lo haga **solo** el hilo dueño del stream en cada modo; (b) agregar un pequeño `time.sleep` + reintento de lectura tras el restart antes de volver a contar None; (c) loguear cada restart (hoy sí loguea, L142).
**Tiempo realista:** 2–3 h (banco con desconexión real de cámara USB, verificar recuperación en ≤2 s sin loop, TEST_LOG).
**Relación:** nuevo; toca la misma clase "recursos globales sin dueño claro" que CT-01/CT-03. Conecta con #108 (si la recuperación falla, sin systemd no hay red de seguridad).

---

### CT-05 · `frame_q.put(frame)` bloqueante con `MAX_QUEUE=2` → eslabón del deadlock de 3 hilos — **P1 (refuerza #111)**

**Dónde:** `frame_q = queue.Queue(MAX_QUEUE)` con `MAX_QUEUE=2` (`Main.py:316,432`). `capture_thread` hace `frame_q.put(frame)` **sin timeout ni `put_nowait`** (`Main.py:449`).

**Qué pasa:** `queue.Queue(2).put(x)` **bloquea** cuando la cola está llena. La cola se llena si `infer_thread` deja de consumir — y `infer_thread` deja de consumir si **muere** (exactamente el escenario de #111: `interpreter.invoke()` tira). Cadena confirmada leyendo el código:
1. `infer_thread` muere en `invoke()` (sin `try/except`, L479).
2. `capture_thread` llena `frame_q` (2 slots) y se **bloquea para siempre** en `frame_q.put` (L449).
3. `main_loop` saca `queue.Empty` de `result_q` cada 250 ms (L574) y **sigue enviando `speed=10, angle=90`** (búsqueda) indefinidamente (L658-663).

Esto **es** el deadlock que #111 describe, pero quiero remarcar que **el `put` bloqueante es la pieza que congela `capture_thread`** — no basta con poner `try/except` en `infer_thread` si querés que el sistema se auto-recupere; también hay que romper el bloqueo del productor (p. ej. `put` con timeout, o descartar el frame más viejo: patrón "drop-oldest" para visión en tiempo real).

**Riesgo de no cambiar:** alto (es CRÍTICO vía #111). Robot en búsqueda infinita dentro de la zona de evacuación = 0 víctimas depositadas en esa corrida.
**Riesgo de cambiar:** bajo. Patrón estándar: en `capture_thread`, si `frame_q` está llena, descartar el frame más viejo (`get_nowait` + `put_nowait`) en vez de bloquear. Mejora incluso el latency en operación normal.
**Tiempo realista:** 1–2 h, idealmente **junto con el fix de #111** (mismo banco: inyectar excepción en `invoke`, verificar que el sistema no se congela). 
**Relación:** **es parte de #111** — recomiendo tratarlos como un solo fix de "robustez del pipeline de rescate".

---

### CT-06 · `infer_thread` usa `frame_q.get()` sin timeout y depende del sentinel — **P2 (refuerza #111/R-V11)**

**Dónde:** `infer_thread` `Main.py:455`: `frame = frame_q.get()` (bloqueante, sin timeout). El protocolo de parada es: `capture_thread` pone `None` al salir (`Main.py:450`), `infer_thread` lo recibe y hace `result_q.put(None); break` (L457-458).

**Qué pasa:** si el sentinel `None` se pierde, `infer_thread` queda bloqueado en `get()` para siempre. ¿Cuándo se pierde? El `finally` de `modo_rescate` (L694-700) **drena `frame_q` con `get_nowait()`** para destrabar hilos — si ese drenado consume el `None` que `capture_thread` puso, antes de que `infer_thread` lo lea, `infer_thread` nunca ve el sentinel. El `join(timeout=1)` (L704) entonces **expira** y, como el hilo es daemon, **queda vivo** colgado en `get()`. Esto es exactamente R-V11 de #111 (thread zombie que corrompe `interpreter` en el próximo ciclo). El drenado actual mitiga el caso del `put` bloqueante (CT-05/CT-07) pero **abre** este otro al competir por el sentinel.

**Riesgo de no cambiar:** medio. No afecta la corrida actual (el rescate termina igual), pero deja un **hilo zombi** que en el **siguiente** rescate comparte el `interpreter` global y las colas nuevas → inferencia corrupta o crash en la 2ª víctima. Como en una corrida hay varias víctimas, es plausible que pase.
**Riesgo de cambiar:** bajo. `frame_q.get(timeout=X)` + chequear `stop_event` en el loop de `infer_thread`, y **no** depender solo del sentinel. O usar `stop_event.is_set()` como condición del `while`.
**Tiempo realista:** 1.5–2 h junto con #111 (mismo banco, mismo PR conceptual).
**Relación:** R-V11 explícito de #111. Recomiendo cerrarlo en el mismo fix que CT-05.

---

### CT-07 · `result_q.put(...)` bloqueante: `infer_thread` se cuelga si `main_loop` deja de consumir — **P2**

**Dónde:** `infer_thread` hace `result_q.put(('det', ...))` / `result_q.put(('no_det', ...))` (`Main.py:499,501`), `result_q = queue.Queue(MAX_QUEUE)` con `MAX_QUEUE=2` (L433). `put` sin timeout → bloqueante.

**Qué pasa:** `main_loop` sale del `while True` cuando `stop_rescate` se activa (L569-570, lo setea `serial_monitor_local` al recibir boot/stop, L549). En cuanto `main_loop` rompe, **deja de hacer `result_q.get()`**. Si `infer_thread` está justo por encolar resultados, llena `result_q` (2 slots) y se **bloquea en `result_q.put`** — **antes de poder llegar a la rama del sentinel** que lo haría terminar limpio. Otra vez el `finally` drena `result_q` (L698-700), lo que ayuda, pero hay una ventana de carrera entre "main_loop rompió" y "el finally drena": en esa ventana `infer_thread` puede quedar bloqueado y, si el drenado no lo libera a tiempo, el `join(timeout=1)` expira → zombi (igual que CT-06).

**Riesgo de no cambiar:** bajo-medio. Mismo desenlace que CT-06 (hilo zombi para el próximo rescate), distinta cola.
**Riesgo de cambiar:** bajo. `result_q.put(item, timeout=X)` o chequear `stop_event` antes de encolar.
**Tiempo realista:** incluido en el fix de #111/CT-05/CT-06 (1 h marginal).
**Relación:** mismo cluster #111/R-V11. **Recomendación fuerte: CT-05, CT-06, CT-07 + #111 son UN solo fix** ("hacer el pipeline de rescate a prueba de muerte de hilos"). Tratarlos sueltos es ineficiente y riesgoso (parches parciales que mueven el deadlock de lugar).

---

### CT-08 · Primer frame `None` y `grabbed` ignorado en `WebcamVideoStream` — **P2 (refuerza #113)**

**Dónde:** `camthreader.py`:
- `__init__` L15: `(self.grabbed, self.frame) = self.stream.read()` — el **primer** `read()` puede devolver `grabbed=False, frame=None` si la cámara no entregó frame todavía.
- `update()` L32: `(self.grabbed, self.frame) = self.stream.read()` — **pisa `self.frame` aunque `grabbed` sea False** (lectura fallida intermitente → `self.frame=None`).
- `read()` L34-36: `return self.frame` — puede devolver `None`.

**Qué pasa:** `read()` puede devolver `None` en dos momentos: (a) arranque, antes del primer frame válido; (b) cualquier lectura fallida intermitente de la cámara, porque `update()` no chequea `grabbed` antes de asignar. El guard `read_frame_with_recovery` (`Main.py:132-147`) **sí** maneja el `None` (cuenta, reintenta, reinicia), así que el crash directo está cubierto. **El sub-bug nuevo** es que `update()` sobrescribe un frame **bueno** anterior con `None` ante un solo `read()` fallido — perdés el último frame válido innecesariamente. Lo correcto (y lo que pide #113 punto 2) es: `grabbed, frame = read(); if grabbed: self.frame = frame`. Así un fallo transitorio conserva el último frame bueno.

**Riesgo de no cambiar:** bajo-medio. Aumenta la tasa de frames `None` espurios → más reintentos, más probabilidad de gatillar el restart de cámara (CT-04) sin necesidad. No corrompe (el `None` se filtra), pero degrada FPS efectivo y robustez.
**Riesgo de cambiar:** muy bajo. Es el mismo cambio de #113 punto 2; va **junto con el Lock de #113**.
**Tiempo realista:** 0.5–1 h, **dentro del fix de #113** (es 1 línea extra: el `if grabbed`).
**Relación:** **#113** (mismo archivo, mismo PR). El Lock (#113.1) + el guard de `grabbed` (#113.2 / CT-08) son el mismo fix de `camthreader.py`.

---

### CT-09 · Hilos daemon con `join(timeout)` corto → supervivencia entre ciclos de rescate — **P2 (refuerza R-V11)**

**Dónde:** `Main.py:684-705`. `tcap`, `tinf`, `t_serial_mon` son `daemon=True`. El `finally` hace `tcap.join(timeout=1)`, `tinf.join(timeout=1)`, `t_serial_mon.join(timeout=0.5)`.

**Qué pasa:** `join(timeout=1)` **no garantiza** que el hilo terminó; solo espera hasta 1 s. Si un hilo sigue bloqueado (CT-05/CT-06/CT-07) más de ese timeout, `join` retorna y `modo_rescate()` **sale dejando el hilo vivo**. Como `modo_rescate()` se vuelve a llamar en el `while estado == 'rescate'` (L720-721) en la próxima víctima, se crean **nuevos** `frame_q`/`result_q`/hilos, pero el `interpreter` y `ser` son **globales compartidos**. Un `infer_thread` zombi del ciclo anterior, si despierta, llama `interpreter.set_tensor/invoke` (L478-480) sobre el mismo intérprete que el nuevo `infer_thread` → **corrupción de tensores / crash**. Esto es R-V11 explícito.

**Riesgo de no cambiar:** medio. Depende de que un hilo se cuelgue (CT-05/06/07); si esos se arreglan, este riesgo casi desaparece. Por eso lo marco P2 condicionado.
**Riesgo de cambiar:** bajo. Verificar `is_alive()` tras el join y, si quedó vivo, **no** reentrar a `modo_rescate()` hasta que muera, o abortar el rescate de forma controlada. Idealmente, los hilos deben salir solos al setear `stop_event` (lo cual requiere arreglar los `put/get` bloqueantes primero).
**Tiempo realista:** incluido en el cluster #111 (0.5 h marginal para el `is_alive()` check).
**Relación:** R-V11 de #111. **Cluster #111.**

---

### CT-10 · No hay heartbeat TX periódico garantizado desde la RPi — **P1 (lado RPi de #53)**

**Dónde:** el TX (`send_frame`) ocurre **solo** dentro de los loops de `linea` (L814) y `rescate` (L663). En estado `esperando` (L713-718) la Pi **no transmite nada**: solo lee bytes de control y duerme 10 ms. Entre transiciones de estado (p. ej. `linea`→`rescate`→`modo_rescate` arranque) hay ventanas sin TX.

**Qué pasa:** #53 pide un "latido bidireccional" para que, si la Pi se cuelga, el robot frene. Hoy el lado RPi **no manda un keep-alive periódico independiente del estado**. Si la Pi entra a `esperando` (porque el Teensy mandó `TEENSY_STOP`/`TEENSY_BOOT`), la Pi calla; depende 100% de que el Teensy implemente su propio timeout (#53 lado Teensy). Si la Pi se **cuelga** dentro de un loop (no manda más frames), el Teensy debe detectarlo — pero eso es trabajo del lado Teensy (#53). Del lado RPi, lo que falta es: **mandar `speed=0` explícito al entrar a `esperando` y periódicamente mientras espera**, para que el último comando que reciba el Teensy sea "frená", no el último `speed=40` de línea.

Hoy, secuencia peligrosa: robot en línea a `speed=40` → Teensy manda `0xFF` (stop) → Pi pasa a `esperando` y **calla** → si el Teensy no procesó bien su propio stop, su último comando vigente sigue siendo `speed=40`. Un `send_frame(0,0,0,0)` al entrar a `esperando` cierra ese hueco desde el lado RPi.

**Riesgo de no cambiar:** medio-alto (seguridad). Es el lado RPi del riesgo CRÍTICO #53: robot que sigue a 40 tras un stop. Barato de mitigar desde la Pi.
**Riesgo de cambiar:** bajo. Agregar `send_frame(0,0,0,0)` en la entrada del `while estado=='esperando'` y cada N ms. Cuidado de no spamear ni pisar el handshake (#72).
**Tiempo realista:** 1.5–2.5 h (coordinar con el lado Teensy de #53/#72, banco, TEST_LOG).
**Relación:** **#53** (lado RPi), conecta con **#72** (handshake boot) y **#71** (no descartar comandos al boot).

---

### CT-11 · `print()` de debug en hot-path compite por GIL / puede bloquear en stdout — **P2**

**Dónde:** `Main.py:798`: `print(area)` **dentro del `for contour in silver_contours`** del loop de línea (se ejecuta por cada contorno, cada frame). También telemetría (L113), warnings de frame None (L139), prints de rescate (L641, L678). En `camthreader.py:13` hay un `print` de dimensiones en el `__init__` (una vez, OK).

**Qué pasa:** `print()` toma el GIL y, si stdout va a una **tty/pipe sin consumir** (p. ej. `nohup`, o un `journald` saturado), **bloquea** hasta que el buffer drene. En el camino caliente de visión (cada frame, y peor, por cada contorno de plata), esto introduce jitter de FPS y, en el peor caso, un micro-stall que retrasa `send_frame` → contribuye a CT-02 (buffer de escritura sin drenar). El `print(area)` por contorno (L798) es claramente un residuo de debug que quedó activo.

**Riesgo de no cambiar:** bajo (calidad/FPS). No mata, pero degrada throughput y ensucia logs; el `print(area)` por contorno es ruido puro en producción.
**Riesgo de cambiar:** muy bajo. Quitar `print(area)` (L798) y gating de los prints de debug detrás de un flag (`DEBUG_VIEW` ya existe, L13). 
**Tiempo realista:** 0.5–1 h (quitar/gate, verificar FPS, TEST_LOG).
**Relación:** higiene de hot-path; toca tangencialmente la telemetría de #75 (que sí queremos, pero ya está rate-limited a 5 s, OK).

---

## 3. Oportunidades (no-bugs) — deuda de diseño de comms+threading

Estas no son fallas activas; son mejoras de robustez/observabilidad que el equipo puede tomar o posponer.

- **OP-1 · Telemetría RX (cerrar #75 del todo).** Hoy solo hay TX (`frames_sent`). Agregar contador de bytes de control RX y de cada tipo (`boot/stop/ready/rescate_done`) daría visibilidad del lado Teensy. ~1.5 h. Relación: **#75**.
- **OP-2 · Centralizar TODO acceso a `ser` en una clase `SerialLink` con su propio `Lock`.** Resolvería CT-01, CT-02 (try/except adentro), CT-10 (heartbeat method) y parte de #70/#71/#72 de un saque, con un solo punto de cambio. Es el refactor "correcto" pero **delicado a 4 semanas del mundial**: recomiendo **posponer a post-Incheon** salvo que se haga con banco intensivo. ~6–10 h. Relación: #77 (roadmap comms fase 2).
- **OP-3 · `WebcamVideoStream` con `Lock` + `Condition` (frame nuevo señalizado).** Más allá del Lock de #113, un `Condition` permitiría que el consumidor espere "frame nuevo" en vez de pollear, eliminando frames duplicados/stale por diseño. ~3 h. Relación: **#113** (versión ampliada).
- **OP-4 · Reemplazar `daemon=True`+`join(timeout)` por shutdown determinista basado en `stop_event` que los hilos chequean en cada `get/put`.** Elimina la clase entera de zombis (CT-06/07/09). Va de la mano del cluster #111. ~incluido en #111.
- **OP-5 · Watchdog de hilos en `main_loop`** (`tinf.is_alive()`, `tcap.is_alive()` periódico) con respawn de la sesión de rescate. Es literalmente lo que pide #111 punto 2. ~incluido en #111.

---

## 4. Recomendación de agrupamiento (para no fragmentar el trabajo)

El error más caro sería abrir 11 fixes sueltos. Por dependencia técnica, **agrupar así**:

1. **FIX-CAM (`camthreader.py`)** → **#113 + CT-08**. Un solo archivo, un PR. Lock + guard de `grabbed`. **El de mejor ROI del lote.** ~2–3 h.
2. **FIX-PIPELINE-RESCATE** → **#111 + CT-05 + CT-06 + CT-07 + CT-09 (+ OP-4/OP-5)**. Hacer el pipeline de rescate a prueba de muerte de hilos: `try/except` en `infer_thread`, `put/get` no bloqueantes (drop-oldest), shutdown por `stop_event`, `is_alive()`+respawn. Un PR coherente. ~4–6 h. **CRÍTICO.**
3. **FIX-SERIAL-TX** → **CT-02 + CT-01 + CT-10**. `try/except` en `send_frame`, `Lock` para `ser`, heartbeat `speed=0` en `esperando`. Coordinar con lado Teensy (#53/#70/#72). ~3–4 h.
4. **FIX-FSM-ESTADO** → **CT-03**. Que solo el hilo principal mute `estado`. Coordinar con #72. ~2–4 h.
5. **FIX-CAM-RESTART** → **CT-04**. Recuperación de cámara con dueño claro + anti-loop. ~2–3 h.
6. **Higiene** → **CT-11 + OP-1** (telemetría RX). ~2 h.

**Bloqueante transversal:** sin **#108 (systemd auto-restart)**, *cualquier* excepción que se escape (CT-02, CT-03, frame corrupto de #113) sigue significando Pi-ciega-permanente. #108 es la red de seguridad que hace que todo lo demás sea "degradación" en vez de "muerte". **Priorizar #108 + FIX-CAM + FIX-PIPELINE-RESCATE** como el núcleo pre-Incheon del lado RPi.

---

## 5. Tabla de trazabilidad hallazgo → Issue existente

| Hallazgo | Issue(s) relacionado(s) | Estado en código actual |
|---|---|---|
| #66 clamp+flush | #66 | **Implementado** (`Main.py:94-116`) |
| serial timeout | #73 | **Implementado** (`Main.py:67`) |
| telemetría | #75 | **Parcial** (solo TX) |
| camthreader Lock | #113 | **Abierto, sin tocar** |
| infer_thread try/except | #111 | **Abierto, sin tocar** (drenado de colas sí agregado) |
| auto-restart proceso | #108 | Abierto (fuera de dominio, amplificador) |
| heartbeat | #53 | Lado RPi débil (CT-10) |
| CT-01 ser sin lock | nuevo (toca #70/#71/#73) | Nuevo |
| CT-02 flush+write_timeout | nuevo (introducido al cerrar #73; amplifica #108) | Nuevo |
| CT-03 estado sin sync | nuevo (toca #72) | Nuevo |
| CT-04 restart vs global | nuevo | Nuevo |
| CT-05/06/07/09 colas+zombis | **#111 (R-V11)** | Abierto |
| CT-08 grabbed/None | **#113** punto 2 | Abierto |
| CT-10 heartbeat TX RPi | **#53** lado RPi | Abierto |
| CT-11 print hot-path | nuevo | Nuevo |

---

*Informe de dominio COMMS+THREADING. Auditoría integral 2026-05-18. Solo lectura — no modifica código, no abre Issues. Para abrir findings nuevos usar la plantilla `audit-finding.yml` y verificar antes contra `AUDIT-ACTION-PLAN.md` y los Issues #53/#66/#70-#77/#108/#111/#113 ya existentes.*
