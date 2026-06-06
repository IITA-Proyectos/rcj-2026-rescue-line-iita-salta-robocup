# Revisión de código — rama `Bugs-Prioritarios` (PR #129)

**Fecha:** 2026-06-05 · **Faltan 25 días** para Incheon (RCJ Rescue Line, 30-jun) · **Freeze de código: 2026-06-15 (10 días).**
**Auditado:** el código **LATEST** del equipo = rama `Bugs-Prioritarios` / PR #129 (tip `2976dca`), worktree `rcj-bugsprio-wt`. Son **2.336 líneas que ninguna auditoría previa miró** — es lo que va a Incheon si se mergea.

> ⚠️ **Esto es DISTINTO de las auditorías anteriores.** Las de resiliencia (2026-05-18), correctitud (2026-05-18) e integral (2026-05-31) fueron sobre `main` viejo (`c42e535`). Este documento es sobre el código NUEVO. Si un bug "ya estaba en el viejo" lo decimos, pero acá importa **qué corre hoy en el robot que compite**.

Equipo: **Laureano** (@Laumonteros, firmware Teensy) · **Lucio** (@luciouriel2011, visión RPi) · **Benjamin** (@benjaminvillagran, RPi + HW + banco).

---

## 1. Veredicto en 5 líneas

1. **El PR es una mejora neta real.** Cierra varios P0 que la auditoría previa marcaba abiertos: handshake 0xFA, timeouts de `runAngle`/`runDistance`/sensor color, Lock en cámara, autorestart systemd, recuperación global en Python. **Eso hay que protegerlo, no romperlo.**
2. **El miedo a "fixes muertos" es INFUNDADO.** El sistema de flags NO apaga nada (ver §3). La red de seguridad de resiliencia está **VIVA** en el firmware que se flashea.
3. **PERO hay bugs NUEVOS reales** en el código de evacuación/rescate (1 P0 + varios P1) que nadie había visto, porque ese código es nuevo.
4. **Dos huecos de seguridad quedaron abiertos a propósito o por descuido:** sin failsafe de RX en el Teensy (P0) y el flag #63 apagado desincroniza el serial tras cada maniobra (P1).
5. **Ningún cambio tiene corrida de banco documentada** (regla de oro #3 sin cumplir), y la evacuación nueva — que es la mitad del puntaje útil — es lo menos probado.

## 2. ¿Es seguro mergear PR #129?

**MERGEAR CON CONDICIONES — NO tal cual está.**

| Condición | Detalle |
|---|---|
| **Partir el PR en dos** | El diff toca 106 archivos (+5718 / −14137). El código real son ~6 archivos; el resto es docs/TDP y **borra 14.137 líneas de auditorías**. **No se puede revisar el código del robot enterrado entre 1205 líneas de markdown borrado.** Separar: PR-código (firmware + rpi) y PR-docs. |
| **Mergeable YA (bajo riesgo, mejora pura)** | `drivebase.cpp` (`pulseCount=0`), `camthreader.py` (Lock + daemon + `stream.release()` + `read()` con copy/None), `priority_fix_flags.h` + helpers de timeout/validación serial. |
| **Necesita BANCO antes del freeze** | Toda la rama `rutina=="evacuacion"` (main.cpp:1887-1956), los cambios de FSM de rescate, y `robot.service` (ruta a verificar en la Pi real). |
| **Arreglar antes de competir** | El P0 de RX failsafe, el P0 de path systemd, y el P1 de green_state sin resetear (ver §4). |

---

## 3. Estado de los fixes en el código nuevo

### ⭐ LO MÁS IMPORTANTE: el sistema de flags NO mata los fixes

Era el mayor temor y quedó **resuelto a favor**. En `priority_fix_flags.h:5` el master `kEnableAllPriorityFixes = false`, pero en `main.cpp:120-178` **cada helper usa OR, no AND**:

```cpp
bool fixIssue60Enabled() {
    return kEnableAllPriorityFixes || kFixIssue60RunDistanceTimeout;  // OR
}
```

Con el master en `false`, el `||` corta-circuita al **flag individual**. Como los individuales están en `true` (#57/#58/#59/#60/#61/#62/#67/#74/#75/#76/#112), **los fixes ESTÁN ACTIVOS**. El master no es un kill-switch: es un override "forzar-todo-on". **La red de seguridad existe en el binario que va a Incheon.** Único apagado: **#63** (`KeepSerialDuringMotions`, master false + individual false → muerto, ver §4 bug N-08).

> ⚠️ **Trampa semántica a futuro:** el naming engaña. Si alguien pusiera el master en `false` esperando "modo seguro sin fixes", se equivoca (los fixes siguen). Y poniéndolo `true` ya **no** podés apagar un fix individual. Debería llamarse `kForceEnableAllFixes`. **No tocar el master.** Para apagar un fix que en banco resulte contraproducente, bajá su flag individual.

### Tabla de fixes conocidos

| Bug | Estado | Evidencia (código nuevo) |
|---|---|---|
| **#67** init `pulseCount` motor | ✅ **CORREGIDO** | `drivebase.cpp:17` agrega `pulseCount = 0;` en el constructor `Moto`. Único cambio funcional del PR en drivebase. Aplicado siempre (sin gate). |
| **#72** handshake 0xFA | ✅ **CORREGIDO** | Teensy emite `Serial5.write(0xFA)` 20× en `setup()` (`main.cpp:1385-1389`). RPi lo consume como `TEENSY_BOOT` (`Main.py:33,163-166` → estado `'esperando'`). End-to-end OK. **Limitación:** es boot one-shot, **no** heartbeat (no detecta cuelgue en runtime). |
| **#58** case 12 fall-through a case 14 | ✅ **CORREGIDO** | `main.cpp:1695-1744`: `waitStart` + timeout 5000ms + `break` gateado por #58. Sin fall-through con #58=true. (Ver inconsistencia I-04: el break depende del flag, anti-patrón.) |
| **#60** `runDistance` sin timeout | ✅ **CORREGIDO** | `computeRunDistanceTimeoutMs` + break en ambas ramas FORWARD (1058) y BACKWARD (1092) + `stopOnExit`. |
| **#61 / #62** timeout color / init sensores | ✅ **CORREGIDO** | #61: `get_color_fresh` timeout 35ms, guards en legacy. #62: `handleBnoInitFailure`→`fatalSensorInitLoop` (LED/buzzer) en vez de `while(1)` mudo. |
| **#74** validar payloads serial | ✅ **CORREGIDO** | `serialPayloadOutOfRange()` (815-832) + `continue` en `serialEvent5` para speed/angle/green_state/silver fuera de rango. |
| **#75** telemetría serial | ✅ **CORREGIDO** | `maybePrintSerialTelemetry()` + contadores `serial_frames_rx`. **Solo observabilidad** (ver oportunidad y P0 N-01: el dato existe pero no alimenta ningún failsafe). |
| **#112** `runAngle` sin timeout | ✅ **CORREGIDO** | `computeRunAngleTimeoutMs` + break (`main.cpp:959-963`). Acota B8. |
| **B9** rojo HSV sin wrap | ✅ **CORREGIDO** | `Main.py:77-80` doble rango (`red1` H[0-7], `red2` H[170-179]) + `bitwise_or` sobre `hsv_frame`. Además fin-de-pista pasó a método robusto por bandas de filas (línea simple=10 / doble=11). |
| **B6** salida anticipada del cuarto | ✅ **CORREGIDO** (en `src/` real) | Se **eliminó** el `veces_deposit=2;` hardcodeado. Ahora arranca en 0 (reset en case 2, 1598) y sube solo en depósitos reales (1845/1867). **OJO:** sigue sin chequear pelotas y reintroduce riesgo por otra vía → ver N-04 (green_state) y N-05 (`==2` estricto). |
| **#57** rescate ambas ramas −90 | ⚠️ **CORREGIDO por reescritura, flag MUERTO** | El bloque viejo (ambas ramas −90) fue **borrado**. El rescate nuevo usa `runAngle(+45)`/`(−45)` por lado, correcto. **PERO `fixIssue57Enabled()` está definido y NUNCA se llama** (0 call sites) → flag huérfano engañoso. El bug desapareció; el flag miente. |
| **B8** `runAngle(180)` sin mirar signo | ⚠️ **PARCIAL** | `main.cpp:982-986`: para 180° sigue `robot.steer(speed,dir,1)` (siempre a derecha, ignora signo). **Acotado** por timeout #112 (ya no se cuelga), pero puede tomar el camino largo. |
| **B2** silver_mask BGR con umbrales HSV | ⚠️ **PARCIAL** | `Main.py:787` sigue `inRange(frame_resized, lower_silver_hsv, ...)` sobre **BGR** con umbrales nombrados HSV → máscara prácticamente ruido. **Mitigado** por el sensor APDS del Teensy que clasifica 'Plateado' (`get_color_fast`). Doble camino: el del sensor es robusto, el de visión sigue frágil. |
| **B1** PID `kp=0/ki=22` DIRECT | ❌ **NO CORREGIDO** (decisión válida) | `drivebase.h:30-31` idéntico al viejo. Integral puro agresivo. **NO es runaway:** `PID.cpp` tiene anti-windup (clamp `outputSum` 0-255). `255-_pwmVal` es **correcto** para el FIT0441 (PWM activo-bajo). Es el baseline tuneado, no una regresión. Ver oportunidad O-1. |
| **B4** `leer_yaw()` no asigna el global | ❌ **NO CORREGIDO** | `main.cpp:1181-1187`: declara `float yaw` LOCAL que tapa al global (1179). `avance_recto()` llama `leer_yaw()` como void y usa el global, que **queda en 0**. Idéntico al viejo. **Bloquea** la búsqueda por yaw en evacuación (ver O-3). |
| **B5** velocidad 55 en curva | ❌ **NO CORREGIDO** | `main.cpp:1682-1690` case 7: si `|steer|>0.7` → `robot.steer(55,...)`. Hardcodeado, idéntico al viejo. Ver O-1/O-2. |
| **B10** encoder 25 pulsos/cm | ❌ **NO CORREGIDO** (mitigado) | `main.cpp:1051` `encoder = 25*Distance` hardcodeado. **Field-calibrado** y documentado (`MEDICIONES_PENDIENTES.md`, validado vs 28.65 teórico, error medido 1-2cm). Acotado por timeout #60. Define la geometría del barrido de evacuación → recalibrar in-situ (O-4). |
| **#53** heartbeat serial continuo | ❌ **NO CORREGIDO** | Grep `heartbeat`/`0xFB` = 0. El 0xFA es boot one-shot. Sin detección de caída de enlace de ningún lado. **Raíz del P0 N-01.** |
| **#27** WDT hardware Teensy | ❌ **NO CORREGIDO** | Grep `WDT`/`watchdog` en `main.cpp` = 0. Si el firmware se cuelga en un `while` sin timeout (p.ej. case 1 esquiva, N-02), no hay reset automático. Ver O-resiliencia. |
| **taskDone** nunca vuelve a false | ❌ **NO CORREGIDO** | `main.cpp:80` init false; solo pasa a true en switch-off (1418). El `if(taskDone)` (1510) que envuelve TODA la FSM de acciones queda **permanentemente true** tras el primer toggle. Variable de "tarea en curso" ficticia. No protege re-entrar a una intersección ya procesada. |
| **FSM rescate no-bloqueante** | ❌ **CÓDIGO MUERTO** | `actualizarRescate()` + enum `RescateState` (257-431, ~175 líneas) se llama cada loop, pero `iniciarRescateNegra/Plateada` (los únicos que sacan de `IDLE`) **nunca se invocan** (0 call sites) → queda en `RESCATE_IDLE`. El rescate REAL es **inline-bloqueante** (1760-1886). Igual `Claw::pickupLeft/Right`. Tres niveles de "recolectar pelota" escritos, uno solo corre. |

---

## 4. Bugs NUEVOS detectados

> Estos son del código nuevo. No estaban en el viejo o se amplificaron con el uso intensivo en la evacuación nueva.

### P0 — riesgo de no completar la corrida

| # | Título | Archivo:línea | Qué pasa | Fix | Quién |
|---|---|---|---|---|---|
| **N-01** | **Sin failsafe de RX en el Teensy** | `main.cpp:1486-1490, 1765`; serialEvent5 `849-900` | El Teensy actúa sobre las globales `speed`/`steer` que setea la RPi. **NO hay chequeo de "hace cuánto que no recibo un frame".** Si la RPi se cuelga (cámara None, excepción de visión, cable suelto), el robot **sigue manejando con el último comando — típicamente avanzando — hasta que se baje el switch físico.** Se va de la mesa o choca a fondo. Es el agujero más grande de la red de seguridad. | `static unsigned long lastFrameMs` actualizado en serialEvent5 al completar frame (donde ya sube `serial_frames_rx`, 894). En `loop()` antes de actuar: `if (millis()-lastFrameMs > 400){ robot.steer(0,FORWARD,0); }`. **Gatearlo con un flag nuevo** para probarlo en banco antes del freeze (desenchufar TX de la RPi y ver que frena). ~1-2h. | **Laureano** |
| **N-02** | **systemd apunta a un archivo que no existe** | `systemd/robot.service:8-9` | `ExecStart=/usr/bin/python3 /home/iita/Desktop/main.py` (minúscula) pero el repo es `final_rpi/Main.py` (**M mayúscula**, otra carpeta). Linux es **case-sensitive**: si en la Pi el archivo es `Main.py`, systemd falla con "No such file" y con `Restart=always` **loopea cada 2s eternamente sin arrancar nunca el robot.** Agravado: `Main.py` hace `from camthreader import *` → ese archivo debe estar en el mismo cwd, y el modelo TFLite está hardcodeado en otra ruta (`/home/iita/Documentos/...`). 3 paths que no cierran. | Decidir UNA convención y alinear `ExecStart` + `WorkingDirectory` con la ruta real desplegada. **Probar en la Pi real:** `sudo systemctl start robot && systemctl status robot`, matar el proceso y ver que reinicia y **levanta este código**. Verificar `User=iita` en grupos `dialout` (serial) y `video` (cámara). Escribir un README de deploy. | **Benjamin** (con Lucio) |

### P1 — pérdida de puntaje o comportamiento errático

| # | Título | Archivo:línea | Qué pasa | Fix | Quién |
|---|---|---|---|---|---|
| **N-04** | **`green_state` nunca se resetea tras depositar/recolectar → re-disparo del mismo evento** | `main.cpp:1768,1794` (negra/plateada) y `1827,1847` (verde/rojo) | Los bloques de rescate ejecutan la acción pero **NUNCA resetean `green_state`** (solo la RPi lo cambia). El loop itera cada pocos ms; si la RPi no mandó valor nuevo, en la próxima vuelta `green_state` sigue 6/7/8/9 y **se re-ejecuta toda la secuencia** (180°+ir a pared+depositRight+runDistance 64cm, o recolección completa). **Doble/múltiple depósito de la misma esquina**, `veces_deposit++` por el mismo evento → la salida `==2` puede alcanzarse re-disparando UNA esquina. Pérdida de pelota/penalización. | Resetear `green_state=0` al final de cada bloque de acción de rescate (igual que en línea se hace `action=7`). El bloque de evacuación (1952) ya lo hace bien — copiar el patrón. Idealmente exigir frame nuevo de la RPi antes de repetir. Banco: un comando de esquina = exactamente un depósito. | **Laureano** |
| **N-05** | **`veces_deposit == 2` estricto: si se sobrepasa, el rescate no sale nunca** | `main.cpp:1870` | Con el bug N-04, `veces_deposit` puede saltar de 1 a 3. La **igualdad estricta** `==2` nunca se cumple → el robot queda atrapado en `while(rutina=='rescate')` depositando hasta apagar el switch. **No hay timeout global de rescate** (existe `tiemporescate=millis()` en 1660 pero **nunca se chequea**). | Usar `>= 2`. Y cablear un timeout global usando el `tiemporescate` ya declarado: tras N segundos forzar `rutina='evacuacion'`. Combinar con N-04. | **Laureano** |
| **N-06** | **`right_distance==0` (dropout del ultrasonido) dispara giro 90° en cada lectura nula** | `main.cpp:1906-1914` | `if (right_distance == 0 \|\| (right_distance-last_right_distance)>30)` → avanza + gira 90° derecha. `NewPing.ping_cm()` devuelve **0 cuando no hay eco** (muy común en pared inclinada/esquina). Cada lectura 0 → giro espurio. En el cuarto de evacuación = pierde la trayectoria de barrido. | Tratar `right_distance==0` como **lectura inválida** (no como "pared lejos"): ignorar/repetir o usar el último válido. Separar "abertura real" (salto sostenido en N lecturas válidas) del dropout. | **Laureano** |
| **N-07** | **`right_jump_counter` nunca se incrementa → rama de recuperación de evacuación MUERTA** | `main.cpp:1918` (lee `>=3`); decl `108`; reset `1417,1921` | `if (right_jump_counter >= 3)` dispara una recuperación, pero el contador **solo se declara y se resetea — NUNCA hay un `++`** en todo `main.cpp` (verificado por grep). La condición jamás se cumple, la rama no corre nunca. El wall-following queda sin el debounce que el contador pretendía. | Definir la intención: incrementar `right_jump_counter` donde se evalúa el salto de pared (1906) y resetear cuando se estabiliza; **o** borrar la rama 1918-1924 para no dar falsa sensación de cobertura. **Decidir UN solo barrido.** | **Laureano** |
| **N-08** | **#63 apagado: el control queda SORDO al serial durante TODO movimiento bloqueante** | flag `priority_fix_flags.h:13`; `main.cpp:913-924, 955-958, 1072-1082, 658-661` | `fixIssue63Enabled()=false`. En cada `runTime/runAngle/runDistance/get_color_fresh`, la rama que procesa serial es `if (... && fixIssue63Enabled()) serialEvent5();` y el **else hace `Serial5.read()` de UN byte y lo TIRA**. Durante maniobras de 1-3s, los bytes de la RPi se descartan de a uno y **desincronizan el parser de framing** (se comen sync bytes 252-255). Al volver al loop, `speed/steer/green_state` están viejos y el parser puede estar corrido. **Causa raíz del comportamiento errático al reanudar línea tras una intersección.** Expone además el `write_timeout` del lado RPi (ver N-12). | Poner `kFixIssue63KeepSerialDuringMotions=true` (los `runAngle/runTime` usan parámetros **locales**, no las globales, así que es **seguro**). Probar en banco que no rompa el timing de giros. Mínimo de bajo riesgo si preocupa: cambiar el else por un `while` que drene todo el buffer, o `Serial5.clear()` al salir de la maniobra. | **Laureano** |
| **N-09** | **`front_distance<12` pisa la acción de verde en la misma iteración** | `main.cpp:1515-1546` | Cadena de `if` **sin else**: green→action, luego `if(front_distance<12) action=1` (esquiva) pisa el verde. En una **T con doble verde** (giro 180), la pared del fondo suele estar a <12cm → hace **esquiva random en vez del 180**. Pierde la intersección de verde. | Reordenar con prioridad explícita con `else-if`: **rescate(plateado) > verde > obstáculo > linetrack**, o chequear `green_state==0` antes de dejar que `front_distance` dispare la esquiva. 30min + banco. | **Laureano** |
| **N-10** | **Posible doble-inversión de clases YOLO (víctima viva/muerta al revés)** | `Main.py:324` vs `654-655` | `CLASS_NAMES=['negro','plateado',...]` (cls0=negro, cls1=plateado). Pero `cls==0 → ball_type="silver"` y `cls==1 → "black"`. O sea **cls0 (nombre 'negro') se trata como SILVER** y viceversa. Doble inversión que **puede cancelarse o no** según el orden REAL de clases del `.tflite` entrenado (modelo NUEVO `best (2)_float32.tflite`, sin metadata verificado). Si está cruzado: clasifica viva/muerta al revés → deposita en zona equivocada → **pierde el multiplicador ×1.4.** | Verificar contra el `metadata.yaml` del modelo desplegado el índice real de plateado vs negro. Alinear `CLASS_NAMES` + mapeo `ball_type` (654-655) + green_state que espera el Teensy. **Banco:** pelota plateada real → confirmar que ejecuta la rama plateada (sortLeft) y deposita en zona de vivas. | **Lucio** |
| **N-11** | **NameError por `cx_black` sin asignar en el camino por DEFECTO del bloque verde** | `Main.py:806-824` (default OFF por `:15`) | `ENABLE_CX_BLACK_GUARD` defaultea a `'0'` → corre la rama ELSE (812-814): `cx_black` solo se asigna si hay negro en filas `[90:]`; si no, queda **sin definir** pero `valid_green_reference=True`. Si el ratio negro-sobre-verde supera 0.32 (816), líneas 822/824 leen `cx_black` → **NameError**. Escenario real: marca verde de T con la línea negra que no llega al borde inferior. La excepción sube al `except` global → `[FATAL]`, frena y resetea a `'esperando'` → **pierde la corrida en plena intersección.** Fix de 1 carácter. | Activar el guard por defecto: `Main.py:15` → `os.environ.get('ENABLE_CX_BLACK_GUARD','1')=='1'`. **O** inicializar `cx_black=None` antes del if/else y agregar `and cx_black is not None`. Validar con video de T donde la línea negra no llegue al borde inferior. | **Lucio** |
| **N-12** | **`send_frame` sin try/except: un `write_timeout` de 50ms tira el robot a 'esperando'** | `Main.py:101-119` (write 110-111; timeout `:70`) | El puerto abre con `write_timeout=0.05`. `ser.write()+flush()` **sin try/except**. Si el Teensy no drena su RX por 50ms (justo lo que pasa con **#63=false**, N-08), `write` lanza `SerialTimeoutException` → sube al `except` global → `[FATAL]` + `estado='esperando'` + sleep(1s). **Abandona el rescate/línea ante un hipo de escritura**, plausible en pista por #63. | Envolver `write/flush` en try/except; ante timeout, loguear y reintentar 1× tras `reset_output_buffer()` o devolver sin matar el estado. Subir `write_timeout` a ~0.2s. **Coordinar con N-08:** activar #63 ataca la causa raíz. | **Lucio** + Laureano (#63) |
| **N-13** | **`capture_thread` sin try/except + `frame_q.get()` sin timeout = zombi irrecuperable** | `Main.py:455-463` y `469` | El #111 blindó `infer_thread`, pero `capture_thread` **NO** tiene try/except: si `cv2.rotate` falla o cualquier excepción, el hilo de captura **muere callado**. `frame_q` deja de llenarse e `infer_thread` queda bloqueado para siempre en `frame_q.get()` (469, **sin timeout**). `main_loop` da `queue.Empty` indefinido → **robot congelado en rescate/evacuación sin watchdog que lo saque.** Pérdida total de la corrida. | Envolver `capture_thread` en try/except que ante fallo haga `stop_event.set()` + `frame_q.put(None)` (espejo de infer_thread). Y/o `frame_q.get(timeout=...)` con manejo de `Empty`. Banco: simular cámara colgada en rescate y confirmar salida en <2s. | **Lucio** |

### P2 — robustez / deuda

| # | Título | Archivo:línea | Qué pasa / Fix | Quién |
|---|---|---|---|---|
| **N-14** | Busy-loops de case 1 (esquiva) sin timeout NI serial | `main.cpp:1561-1570, 1576-1585` | El `while` de esquiva solo sale si `get_color_fast()=="Negro"`. Si nunca lee negro (sensor sucio, esquina sin negro) → **gira en círculo para siempre**. Además `serialEvent5()` está **comentado** dentro (1564,1579). NO recibió timeout en la tanda de fixes. **Fix:** agregar `if((millis()-t0)>3000) break` como #58/#112, y descomentar/llamar `serviceMotionBackgroundTasks()`. | **Laureano** |
| **N-15** | Bloques de depósito hacen retroceso a fin de carrera **sin timeout** | `main.cpp:1831-1837, 1851-1857` | `while(digitalRead(32)==0){ steer(15,BACKWARD); if(FCL==HIGH&&FCR==HIGH) break; }`. Si un FC no cierra (falla mecánica, esquina mal alineada, víctima trabada) → **retrocede contra la pared indefinidamente.** Patrón opuesto a los que ganaron timeout. **Fix:** `if(millis()-start>2500) break`. | **Laureano** |
| **N-16** | Esquiva con `random()` sin seed → secuencia idéntica cada corrida | `main.cpp:1555-1556` | Sin `randomSeed()` en setup (verificado). En Teensy `random()` sin seed da **siempre la misma secuencia** tras reset → esquiva siempre para el mismo lado. Predecible y no mira `left/right_distance` que ya lee. Ver O-esquiva. | **Laureano** |
| **N-17** | `runDistance` arranca con sacudida fija BACKWARD+FORWARD 20ms | `main.cpp:1048-1049` | `runTime(30,BACKWARD,0,20)`+`runTime(30,FORWARD,0,20)` antes de resetear encoders. Es un tirón anti-fricción pero mete ~40ms de movimiento **no medido** y ~0.5cm de retroceso no contabilizado **por cada avance**. En evacuación se llama muchas veces (1907,1913,1938,1949) → **deriva acumulada.** **Fix:** medir deriva tras 10 `runDistance`; reducir a 10ms o compensar. | **Laureano** |
| **N-18** | `computeRunDistanceTimeoutMs` puede abortar el avance a baja velocidad | `main.cpp:236-244` | Estima `max(8, speed*3/4)` cm/s + margen 3/2 + 500ms. A `speed=15-20` con carga (pelota, rampa) el robot va **más lento** → el timeout puede dispararse antes de llegar → break silencioso → **robot mal posicionado en evacuación.** **Fix:** factor 2× o +1000ms para velocidades <25; loguear cuando dispara para distinguir "llegué" de "me rendí". | **Laureano** |
| **N-19** | `accionNegro()` saca de evacuación al primer negro | `main.cpp:1143-1151` desde `1891` | `accionNegro()` hace `rutina='linea'`. En cuanto ve **cualquier** negro (el borde negro del cuarto, que siempre está) sale de evacuación. `get_color_fast()` es 1 muestra sin filtro → falso negro (sombra, borde) → **loop: entra evac → negro → línea → re-detecta plateado → rescate de nuevo.** **Fix:** confirmación multi-muestra antes de `accionNegro`, o no dejar que cambie `rutina` durante evacuación. Modelar evacuación como FSM explícita. | **Laureano** |
| **N-20** | Asimetría sospechosa depósito verde (64cm) vs rojo (0cm) | `main.cpp:1844` vs `1863` | Verde: `runDistance(30,FORWARD,4+60)` = 64cm. Rojo: `runAngle(45)+runTime(500)+runAngle(-45)`, **sin avance equivalente**. El `4+60` es número mágico. En el `evacuation.cpp` viejo **ambos** hacían `runDistance(...,40)` → el comportamiento cambió. Sin banco no se sabe si es mejora o regresión. **Fix:** documentar la geometría, reemplazar `4+60` por constante nombrada, validar ambas secuencias en banco. | **Laureano** |
| **N-21** | `salida final green_state==10` comentada y rota | `main.cpp:1879-1884` | Bloque comentado con error de sintaxis (`estado == "salida"` con `==` y variable inexistente) que **no compilaría** si se descomenta. La salida real del cuarto depende de `accionNegro` (N-19), frágil bajo el destello de la regla 3.9. **Fix:** borrar el bloque roto y definir/probar UNA condición de salida robusta. | **Laureano** |
| **N-22** | `print(area)` incondicional en el hot-loop de línea | `Main.py:842` | Dentro de `for contour in silver_contours:`, un `print(area)` sin guard, cada frame por cada contorno. Con `PYTHONUNBUFFERED=1` (systemd) es **I/O síncrono al journal** → recorta FPS y ensucia logs. **Fix:** borrar o gatear con `if SHOW_DEBUG_WINDOWS`. | **Lucio** |
| **N-23** | `record=True` fuerza `cv2.imshow` de debug | `Main.py:58, 896-897` | `record` pasó de False a **True**. Hoy gateado por `SHOW_DEBUG_WINDOWS` (headless OK), pero si alguien lanza `Main.py` desde sesión gráfica/VNC con `DISPLAY` → abre 4-5 ventanas a 30+ FPS robando CPU en plena corrida. Cambio de debug que no debe ir a competencia. **Fix:** `record=False`, o flag `COMPETITION=1` que apague todos los imshow. | **Lucio** |

---

## 5. Inconsistencias a corregir

> El hilo común es **código muerto que aparenta estar vivo** — el equipo puede estar tuneando fantasmas. Limpiar esto baja la superficie de bug a 10 días del freeze.

| # | Inconsistencia | Dónde |
|---|---|---|
| **I-01** | **`test/evacuation.cpp` (1205 líneas) es CÓDIGO MUERTO y peligroso.** Tiene su propio `setup()/loop()`. `platformio.ini` **no** define `build_src_filter` → PlatformIO compila **solo `src/`**. NO entra al binario. PERO: (a) es una **copia STALE** del main viejo (`get_color()` bloqueante, sin validación serial, sin timeouts, **sin** `priority_fix_flags.h`); (b) tiene el bug B6 que el `src` vivo ya **no** tiene (`veces_deposit=2;` hardcodeado en `:1113` justo antes del `if`); (c) si alguien lo sube a `src/` por error, **sube firmware sin NINGÚN fix.** Las "1205 líneas nuevas" del diff son en su mayoría este archivo muerto — el cambio real de lógica es mucho menor. | `test/evacuation.cpp:1-1205` vs `src/main.cpp:1887-1956` |
| **I-02** | **Flags y variables huérfanas que engañan.** `fixIssue57Enabled()` definido, **0 call sites** (el equipo cree que #57 está "aplicado por el flag" y el flag no controla nada). `#67` se aplica **sin** gate (`drivebase.cpp:17`) → el flag es decorativo. `evacuacion_straight` (decl 106, solo se resetea) y `alineado` (101, solo `=false`) son zombis. `lastTurn`/`turnCooldown=600` (52-53) declarados, **nunca usados** (anti-rebote de verde a medias). | `main.cpp:120-124, 101, 106, 52-53` |
| **I-03** | **`veces_deposit` y `ball_counter` inicializan en 2** (el valor "terminado"), no en 0. Funciona porque se resetean al entrar a rescate (1597-1598), pero **el reset de switch-off (1407-1418) NO los toca.** Si el operador apaga/reenciende el switch **durante** rescate (común en competencia), quedan en valor arbitrario → depósito/salida con conteo corrupto. | `main.cpp:103-104, 1407-1418, 1597-1598` |
| **I-04** | **Break de `case 12` depende del flag #58 para no caer por fall-through a `case 14`** (giro 180). Control de flujo de un `switch` acoplado a un feature flag = anti-patrón. Inofensivo hoy **solo** porque `green_state==14` nunca llega de la RPi (código inalcanzable). **Fix:** `break` incondicional, dejar el flag solo para el timeout. | `main.cpp:1740-1744` |
| **I-05** | **`case 12` / `green_state 14-17` es código inalcanzable.** La RPi en línea solo emite `green_state ∈ {0,1,2,3,10,11}` (verificado `Main.py:790-874`). El `case 12` (50+ líneas con su timeout #58) **nunca corre en competencia.** El #58 protege código muerto. **Fix:** confirmar con Lucio que fue feature abandonada y borrar. | `main.cpp:1536-1539, 1695-1744` |
| **I-06** | **Línea roja de fin por VISIÓN se descarta.** La RPi manda `green_state=10` (simple) / `11` (doble), pero el firmware en rutina línea **nunca lee 10/11** (el switch solo maneja 0/1/2/3/14). Solo corta si el APDS físico clasifica 'Rojo' (`color_detected=="Rojo"`, 1504). Se tira información que la RPi ya calcula. Ver O-fin-pista. | `main.cpp:1504-1508` vs `Main.py:871-874` |
| **I-07** | **Tres implementaciones de clasificación de color en el firmware vivo:** `get_color_fast`/`update_color_nonblocking` (la usada), `get_color_old` (676) y `get_color_blocking_legacy` (731), las dos últimas **0 call sites**. Encima los umbrales de 'Rojo' **difieren entre el `print` y el `return`** en la legacy. Confunde el mantenimiento de la calibración. | `main.cpp:676-729, 731-802` |
| **I-08** | **Doble trigger de entrada a rescate con criterios distintos:** visión (`Main.py:838` silver_mask BGR + área>50 → `silver_line=1`) y sensor color Teensy (`main.cpp:1494` `get_color_fast=='Plateado'`). Coexisten sin fuente de verdad clara. Si uno da falso positivo, la entrada a la zona es errática. | `Main.py:838` vs `main.cpp:1494` |
| **I-09** | **Doc duplicada en el mismo PR que dice deduplicar.** `variables_doc.md` se vació marcándose "Deprecated TDP Copy" apuntando a `../../../TDP.md`, pero el PR agrega `TDP.md` en la raíz **Y** `docs/tdp/TDP-IITA-2026.md` (mismo contenido, 458 líneas c/u). Se viola "una sola fuente de verdad" en el mismo PR. | `TDP.md` y `docs/tdp/TDP-IITA-2026.md` |
| **I-10** | **Contrato de rangos desactualizado.** El comentario dice `green_state: 0..20` (`Main.py:22-23`) pero el código usa hasta 11. Verificar que `SERIAL_MAX_GREEN_STATE` (#74) sea ≥ los valores reales o se rechazarán green_states válidos — y `serialPayloadOutOfRange` hace `continue` **sin** resetear `serial5state`, desincronizando el frame siguiente. `cut_line` (778,781) se calcula y nunca se usa. | `Main.py:22, 778` vs `main.cpp:881` |

---

## 6. Oportunidades de mejora competitivas (ojo de campeón)

> Priorizadas por impacto en PUNTAJE. El scoring 2026 multiplica TODO el campo por **×1.4 por cada víctima viva evacuada**. Un robot que termina la línea pero falla la evacuación deja más puntos sobre la mesa que cualquier optimización de velocidad.

### 🎯 PALANCA #1 — Blindar la EVACUACIÓN (máximo leverage)

Es la mitad del puntaje útil y hoy es lo más frágil. Tres agujeros encadenados que ningún campeón aceptaría:
- **(a) Cobertura del cuarto a merced del azar.** `avance_recto()`, `lado_pared()`, `pelotita()`, `esquinas_negro[]` están **definidas pero MUERTAS** (0 call sites). El robot solo reacciona a lo que ve la cámara, **sin barrido sistemático del perímetro ni memoria de qué víctimas ya recogió.** Pelota en esquina fuera de cuadro = no se recoge nunca.
- **(b) Depósito a 180° fijo** (`main.cpp:1830,1850`) que asume la zona siempre enfrente. En zona asimétrica (los jueces la arman así) **deposita al aire.**
- **(c) Salida final sin implementar robustamente** (N-21).

**Leverage realista en 10 días — NO rediseñar, pero SÍ:** (1) cablear `avance_recto()` como modo búsqueda cuando la cámara no ve pelota — **requiere antes arreglar B4** (`leer_yaw` no asigna el global yaw); (2) hacer **20 corridas de evacuación cronometradas** midiendo tasa de captura y de depósito-en-zona-correcta, y tunear timings **con datos, no a ojo**. *Impacto: ALTO. Una corrida de ~30 pts de línea pasa a 30×1.4×1.4≈59 pts.* → **Laureano + Lucio.**

### 🎯 PALANCA #2 — Calibración de color robusta para la luz de Incheon (consistencia)

Lo que mata corridas en un estadio nuevo no es la estrategia, es que los umbrales calibrados en **Salta** no matchean la luz de **Songdo**. Tres sistemas de color con umbrales hardcodeados que se van a desincronizar: (a) `Main.py` BGR/LAB/HSV fijos (71-80) + **silver_mask en BGR con umbrales HSV (B2)**; (b) APDS9960 en Teensy con `known_colors[]` y thresholds mágicos (`c>1700`, `R/C>0.240`); (c) `CLASS_THRESH` de YOLO.

**Acción en 10 días:** (1) **fijar exposición y balance de blancos de la cámara** — hoy el auto-exposure "bombea" cuando entra plateado/blanco brillante y arruina las máscaras (el `anti_flash` ataca el síntoma; la causa es el auto-exposure). Son ~2 líneas de `cv2.CAP_PROP`; (2) escribir un **checklist de recalibración para el pit** (10-20s antes de cada ronda); (3) cargar umbrales desde JSON editable sin recompilar. *Impacto: ALTO para CONSISTENCIA — bajar la varianza entre corridas vale más que subir el máximo.* → **Lucio + Benjamin.**

### 🎯 PALANCA #3 — Convertir la novedad ya escrita en evidencia medida para el TDP

El TDP pesa **12% del total** y la rúbrica 2026 agregó "Reliability Tests & QA". El equipo YA tiene el activo de novedad más fuerte **escrito y corriendo**: el pipeline **anti-destello** (respuesta directa a la regla 3.9 de LEDs intermitentes) y el diseño de **validación multimodal de víctima** (visión+conductividad+reflectancia, regla 3.10). Ningún equipo de referencia (Overengineering², Airborne, Danesh) documenta esto porque compitieron bajo reglas 2024/2025. **Es el relato incopiable.** Pero hoy es "diseñamos", no "medimos": el TEST_LOG está casi vacío y **la conductividad NO está embarcada** (pin 26 no se lee).

**Alto ROI en 10 días:** (1) **implementar la conductividad** — ~15 líneas + 1 pin + 2 cables (ya documentado) → convierte el claim en feature real que rechaza víctimas falsas (regla 3.10); (2) grabar 15-20 frames con destello (una linterna), correr detección con/sin `anti_flash`, meter la tabla en TEST_LOG → N1 pasa de "diseñamos" a "diseñamos y validamos" (la diferencia entre 3 y 6 en la rúbrica). **Cuidado de credibilidad:** presentar SOLO lo embarcado como "el robot hace"; lo demás como "en integración". Un juez de mundial desarma claims inflados. → **Benjamin + Lucio.**

### Otras oportunidades (orden de impacto)

- **O-1 — Sintonizar un Kp real en el PID** (hoy `kp=0/ki=22`, integral puro). Un Kp pequeño da respuesta inmediata al error y mejora consistencia rueda-a-rueda y trazado en curvas. *Riesgo medio (re-test de las 4 ruedas). Solo si se hace ANTES del 15-jun o no se toca.* → **Laureano.**
- **O-2 — Speed scheduling proporcional en línea** en vez de dos velocidades 25/55 (B5): frenado progresivo al entrar en curva, mínimo en el ápice. Menos overshoot (salirse de la línea) + más velocidad en recta. → **Laureano.**
- **O-3 — Recuperación de línea perdida** (line-search): al perder negro, hoy la RPi manda `angle=0` y el robot sigue recto a ciegas. Un barrido ±con la IMU buscando negro salva baldosas en gaps. *Requiere B4 arreglado.* → **Laureano + Lucio.**
- **O-esquiva — Esquiva por sensor en vez de `random()`** (N-16): el robot YA lee `left/right_distance`. Mínimo: `lado = (left_distance > right_distance) ? izq : der`. El random ciego falla ~50% cuando el espacio está del otro lado. → **Laureano.**
- **O-fin-pista — Cerrar fin de pista por visión** (I-06): aprovechar `green_state 10/11` que la RPi ya manda, redundante con el APDS. Parada confiable en la línea roja de fin. → **Laureano + Lucio.**
- **O-resiliencia — Failsafe bidireccional + WDT hardware.** Convertir el 0xFA en heartbeat periódico (cada ~200ms ambos lados) cierra N-01 **y** el caso inverso (Teensy colgado). Armar el **WDT_T4** del Teensy con `feed()` en loop + while largos: ataja TODOS los cuelgues, incluso los no previstos (case 1, N-14). *Práctica estándar de equipos top, costo bajo.* → **Laureano** (+ Lucio para el lado RPi).
- **O-presupuesto — Recortar delays de pinza sobre-dimensionados.** Cada pelota encadena ~8 `nonBlockingDelay` de 1000-1400ms ≈ **9-10s/pelota ×3 ≈ 30s** quieto. **Cronometrar la corrida completa**; si no alcanza para 3 pelotas+2 depósitos+salida, recortar delays (varios 1000ms pueden ser 600-700ms si el servo ya llegó) y **priorizar las 2 vivas** (valen el multiplicador) sobre la muerta. *Regla de oro: evacuar 2 vivas > intentar 3 y quedarse sin tiempo.* → **Laureano + Benjamin (banco con cronómetro).**

---

## 7. Reparto por persona (antes del freeze del 15-jun)

### 🔧 Laureano (@Laumonteros) — firmware Teensy
**Orden de prioridad:**
1. **N-01 — Failsafe de RX (P0).** Deadman `lastFrameMs` + freno si `>400ms` sin frame, gateado por flag nuevo. Banco: desenchufar TX de la RPi → debe frenar. *Es el agujero más grande.*
2. **N-04 + N-05 — Reset de `green_state` tras depositar + `>=2` + timeout global de rescate.** El re-disparo de depósitos es pérdida directa de puntaje. Banco: un comando de esquina = un depósito.
3. **N-08 — Activar #63** (`kFixIssue63KeepSerialDuringMotions=true`). Mata el comportamiento errático tras intersecciones y cierra N-12. Banco: medir que no rompa timing de giros.
4. **N-06 + N-07 — Filtrar `right_distance==0` + decidir el barrido (cablear o borrar `right_jump_counter`).** Wall-following de evacuación.
5. **N-09 — Reordenar prioridad** verde > obstáculo (else-if).
6. **N-14 + N-15 — Timeouts faltantes** (case 1 esquiva, while de fin de carrera del depósito).
7. **Limpieza (I-01, I-02): borrar `test/evacuation.cpp`, flag #57 huérfano, variables zombi.** *No mergear 1200 líneas muertas de la lógica más crítica.*
8. Si queda tiempo y se valida en banco: **O-1 (Kp), O-esquiva, O-fin-pista.**

### 👁️ Lucio (@luciouriel2011) — visión RPi
**Orden de prioridad:**
1. **N-10 — Verificar el orden REAL de clases del `.tflite`** contra el metadata. Si está cruzado, deposita víctimas en zona equivocada (pierde ×1.4). Banco con pelota plateada real.
2. **N-11 — Activar el guard de `cx_black`** (`ENABLE_CX_BLACK_GUARD` default `'1'`). Fix de 1 carácter que evita perder corridas por NameError en T.
3. **N-12 + N-13 — try/except en `send_frame` y `capture_thread`** + timeouts en colas. Evita abandonos de corrida por hipos de serial/cámara.
4. **B2 / PALANCA #2 — Decidir la fuente de verdad del plateado:** mover silver_mask a HSV real **o** confiar 100% en el APDS y borrar la rama de visión (no enviar `silver_line=1` espurios). Validar con la cinta plateada real.
5. **Cámara: fijar exposición + WB manuales** (causa raíz del bombeo de máscaras). ~2 líneas.
6. **N-22 + N-23 — Sacar `print(area)` del hot-loop y `record=False`** para competencia.
7. PALANCA #3 (medición visión): grabar frames con/sin destello para el TEST_LOG.

### 🔌 Benjamin (@benjaminvillagran) — RPi + HW + banco
**Orden de prioridad:**
1. **N-02 — Arreglar el path de `robot.service` (P0).** Alinear `ExecStart`/`WorkingDirectory` con la ruta y nombre reales en la Pi (case-sensitive). **Probar `systemctl start/status`, matar el proceso, ver que reinicia y levanta ESTE código.** Verificar `iita` en grupos `dialout`+`video`. Escribir README de deploy. *Si esto falla, el robot no arranca en la mesa.*
2. **Single source of truth de paths:** repo == lo que corre en la Pi. Sacar el hardcode del modelo TFLite a una env var. Confirmar que `Main.py` + `camthreader.py` + modelo estén en el cwd correcto.
3. **PALANCA #3 — Embarcar la conductividad** (pin 26, ~15 líneas + 2 cables): convierte el mejor relato de TDP en feature real (regla 3.10).
4. **Banco de evacuación (PALANCA #1):** correr y cronometrar las 20 corridas con Laureano, llenar `testing/TEST_LOG.md`. *Regla de oro #3: ningún fix de evacuación se mergea sin banco documentado.*
5. **O-presupuesto:** cronometrar la corrida completa de evacuación con Laureano.
6. Endurecer `robot.service`: `StartLimitBurst`, esperar `/dev/serial0` y cámara, `Environment=ENABLE_CX_BLACK_GUARD=1`.

---

## 8. Cierre del coach — las 3 cosas de mayor impacto en 25 días

Equipo: este PR es un salto real respecto del robot que auditamos en mayo. Cerraron P0 de resiliencia, el handshake, los timeouts, el threading de cámara. **Eso ya está ganado — no lo rompan en el apuro.** Usen los flags individuales como red: si un fix nuevo rompe algo en Incheon, se apaga **su** flag, no se revierte código.

Ahora, dónde ponemos las fichas en estos 25 días, en orden:

1. **TAPAR LOS DOS P0 ESTA SEMANA.** El robot que se va de la mesa cuando la RPi se cuelga (**N-01**) y el autostart que no encuentra su propio archivo (**N-02**) son la diferencia entre competir y mirar. Son de bajo riesgo y se prueban en banco en una tarde. No lleguen al freeze sin esto.

2. **BLINDAR LA EVACUACIÓN — es la mitad del puntaje.** El multiplicador ×1.4 por víctima viva vale más que cualquier optimización de velocidad. No rediseñen: arreglen **B4** (yaw), cableen un barrido mínimo (**PALANCA #1**), arreglen el re-disparo de depósitos (**N-04/N-05**), y hagan **20 corridas cronometradas** tuneando con datos. Hoy la evacuación está a merced del azar y es lo menos probado.

3. **CONSISTENCIA > MÁXIMO: calibración de color in-situ + medir para el TDP.** Lo que mata robots en un mundial es que andan en casa y fallan en la cancha por la luz. **Fijen exposición/WB** (2 líneas, causa raíz del bombeo) y lleguen con un **checklist de recalibración para el pit**. Y de paso, **embarquen la conductividad** y graben las pruebas de destello: convierten el relato de novedad más fuerte que tienen (12% del TDP) de "diseñamos" a "medimos".

**Disciplina final:** todo lo que se toque va a banco y al `TEST_LOG.md` antes de mergear (regla de oro #3). Partan el PR #129 en código y docs para poder mergear el código seguro YA. Y no toquen el PID ni el master flag a menos que tengan una corrida de banco que lo justifique.

A ganar experiencia en Incheon — y a llegar con el robot **consistente**, que es lo que separa el podio.

— El coach
