# Auditoría Integral 2026-05-18 — Teensy / Módulo SENSORES

**Subsistema:** Firmware Teensy 4.1 — sensores (BNO055 IMU, APDS9960 color, VL53L0X ToF, ultrasonido NewPing)
**Archivo principal:** `software/teensy/firmware/src/main.cpp`
**Branch analizado:** `feature/initialize-testing-log` (contenido = `main`, post-merge PR #101)
**Fecha:** 2026-05-18 / redactado 2026-05-31
**Auditor:** dominio SENSORES (lectura únicamente — NO se modificó código)
**Alcance:** init en `setup()`, lecturas en runtime (`leer_yaw`, `leer_pitch`, `get_color`, `leer_tof`, `leer_ultrasonidos`), manejo de fallo, salud de sensores.

> **Convención de findings (regla del coach):** cada finding lleva **risk-NO-fix** (qué pasa si se deja), **risk-fix** (qué se puede romper al tocarlo) y **tiempo estimado**. NO se presentan como "bugs a fixear" sino como TEMAS A ANALIZAR con trade-off explícito. La decisión final es del equipo.

---

## 0. Resumen ejecutivo

El módulo de sensores es **funcionalmente correcto en condiciones nominales** pero **frágil ante cualquier fallo de hardware en runtime** — precisamente el escenario que más se da en un mundial (golpes, conectores flojos, EMI de motores en rampa). El equipo YA tenía implementadas defensas (timeouts de color, init con alerta visible, timeout de `runDistance`, servicio de tareas de fondo durante movimiento) bajo un sistema de flags `priority_fix_flags.h`, pero **todo ese sistema fue revertido en bloque en el commit `cead75e` (2026-05-10, Benjamin)** con el mensaje engañoso `fix(teensy): error de libreria claw.cpp`. Hoy el firmware está **menos resiliente que hace 3 semanas**.

Los hallazgos se clasifican así:

| ID | Título | Prioridad | Estado en auditorías previas |
|---|---|---|---|
| **S-01** | Revert masivo de defensas de sensores en `cead75e` (#60/#61/#62 desimplementados) | **P0** | **NUEVO** (las previas no detectaron el revert) |
| **S-02** | `get_color()` cuelga el firmware sin timeout (sensor color) | **P1** | Ya en #61 (re-confirmado: revertido) |
| **S-03** | `while(1)` infinito en init de BNO055 sin alerta visible | **P1** | Ya en #62 (re-confirmado: revertido) |
| **S-04** | BNO055 sin detección de fallo en runtime → heading basura silencioso | **P0/P1** | Ya en #109 / R-T06 (se agrega análisis de `leer_yaw`) |
| **S-05** | `leer_yaw()` declara variable local que ensombrece la global → `avance_recto()` usa yaw=0 (#B4) | **P1** | Parcial en #109; **se precisa el scope real de #B4** |
| **S-06** | ToF devuelve `65535` (basura) en timeout y se propaga sin filtrar | **P1** | **NUEVO** (las previas cubren BNO, no VL53L0X) |
| **S-07** | `get_color()` no puede devolver "Plateado" — tabla de calibración sin entrada plateado (código muerto) | **P2** | **NUEVO** |
| **S-08** | Calibración de color hardcodeada y sin blanco/ambiente; 3 colores muy juntos | **P1/P2** | **NUEVO** (oportunidad) |
| **S-09** | Sin health-check unificado ni fusión sensorial (ToF+US redundantes sin cruzar) | **P2** | Oportunidad (complementa #27, #53, #109) |
| **S-10** | Lecturas ToF bloqueantes (`readRangeContinuousMillimeters` con timeout 500 ms) en hot loop | **P2** | **NUEVO** |

---

## 1. Inventario de sensores y su uso

| Sensor | Lib | Bus | Init (`setup`) | Lectura runtime | Consumidores |
|---|---|---|---|---|---|
| **BNO055** (IMU) | Adafruit_BNO055 | I2C `Wire` (0x28) | `bno.begin()` + `setExtCrystalUse(true)` (líneas 757-763) | `leer_yaw()` (610), `leer_pitch()` (617), inline en `runAngle()` (436-449) | giros, `avance_recto`, `centrar`, `angulo_rescate` |
| **APDS9960** (color) | Adafruit_APDS9960 | I2C `Wire` (default) | `apds.begin()` + `enableColor(true)` (766-774) | `get_color()` (331) | detección Negro/Verde/Rojo en rutina línea y rescate |
| **VL53L0X ×2** (ToF) | Pololu VL53L0X (lib local) | `Wire2` (left) / `Wire1` (right), ambos addr 0x30 | `init/setTimeout(500)/startContinuous` (777-794) | `leer_tof()` (284) | `avance_recto()` (no se usa en `loop` actual) |
| **Ultrasonido ×3** (frente/izq/der) | NewPing (lib local) | pines trig/echo | constructor estático (258-261) | `leer_ultrasonidos()` (269) | detección obstáculo (`front_distance<12`), elección de pared en rescate |

**Observación de arquitectura:** los cuatro sensores comparten el patrón "función `leer_X()` que escribe variables globales". Esto es razonable para un firmware reactivo, pero **ninguna** valida el retorno del driver ni marca un flag de salud. Cualquier fallo es silencioso.

---

## 2. Hallazgos detallados

### S-01 — [P0] Revert masivo de defensas de sensores en `cead75e` (#60/#61/#62 desimplementados)

**Evidencia dura (git):**
El commit `cead75ea389f517ec6f218993279f53d3a7546d0` (Benjamin Villagran, 2026-05-10 19:26, mensaje `fix(teensy): error de libreria claw.cpp`) **eliminó 181 líneas** que constituían el sistema completo de mitigaciones, incluyendo el header `priority_fix_flags.h` (que ya **no existe** en el repo — confirmado con `git ls-files`). Lo revertido relevante a sensores:

1. **`get_color()` timeout (issue #61)** — se borró:
   ```cpp
   if (fixIssue61Enabled() && (millis() - waitStart) > 50)
       return "Desconocido";
   ```
   y la guarda `if (!color_sensor_ok) return "Desconocido";`. Hoy el `while (!apds.colorDataReady()) delay(5);` (main.cpp:336-339) **quedó otra vez sin timeout**.

2. **Init con alerta visible (issue #62)** — se borraron `handleBnoInitFailure()`, `fatalSensorInitLoop()` (LED rojo + buzzer parpadeantes), `notifyOptionalSensorWarning()` y la bandera `color_sensor_ok`. Hoy el init volvió al `while (1) ;` mudo (main.cpp:760-761 y 665-666).

3. **`runDistance` timeout (issue #60)** y **`serviceMotionBackgroundTasks()` (issue #59)** — también revertidos. Impactan sensores indirectamente: durante `runTime/runAngle/runDistance` ya **no** se refresca `claw.update()` ni la máquina de rescate, y los giros por IMU pueden colgar sin escape.

**Por qué las auditorías previas no lo marcaron:** las auditorías de RESILIENCIA (#109 et al., commit `c42e535`) y CORRECTITUD (#120-#128) se hicieron sobre el estado **post-revert**, por lo que describen los síntomas (#61, #62, #109) como bugs presentes, pero **ninguna documentó que existió una solución y fue retirada**. Esto es relevante porque el código de fix YA está escrito y validado conceptualmente en `git show cead75e` — restaurarlo cuesta mucho menos que reescribirlo.

- **risk-NO-fix:** el robot conserva los tres modos de cuelgue/silencio (#60/#61/#62) en pleno mundial. Además, cada vez que alguien "arregla" #61 o #62 desde cero, está reinventando código que el equipo ya había escrito y probablemente probado — desperdicio de las pocas semanas que quedan.
- **risk-fix:** restaurar el sistema de flags reintroduce ~180 líneas y el header. Hay riesgo de que el revert original haya sido **intencional** porque algo de ese sistema rompía el banco (el mensaje miente sobre el motivo, así que NO sabemos la razón real). **Acción previa obligatoria:** hablar con Benjamin/Enzo para entender por qué se revirtió antes de restaurar nada. Puede que `serviceMotionBackgroundTasks()` (que llama `actualizarRescate()` dentro de `runTime`) generara reentrada — de hecho el revert también quitó el guard `rescateUpdateInProgress`, lo que sugiere que ahí había un problema de reentrada que el equipo no resolvió y prefirió tirar todo.
- **tiempo:** 30 min investigar el motivo del revert (preguntar al equipo + leer el diff completo) + 1-2 h restaurar selectivamente solo los timeouts de sensores (#61, #62) sin el resto. **No restaurar a ciegas.**

**Recomendación:** abrir el tema como meta-issue que enlace #59/#60/#61/#62, citando `cead75e` como el commit que los desimplementó, y decidir cuáles se restauran. El issue #115 ("empezá HOY por recuperar timeouts #60/#61", asignado a Laureano) ya apunta en esta dirección pero **no menciona que el código fuente del fix vive en `cead75e`** — agregarlo ahorra trabajo.

---

### S-02 — [P1] `get_color()` cuelga el firmware sin timeout

**Ya documentado en issue #61 (OPEN).** Re-confirmado tras el revert de S-01. No se reabre; se cita.

`main.cpp:336-339`:
```cpp
while (!apds.colorDataReady()) {
    delay(5);
}
```
`get_color()` se llama en el hot loop de la rutina línea (línea 887) y dentro de maniobras de obstáculo (951, 966). Si el APDS9960 pierde I2C, el robot queda **congelado** dentro del `while` con el switch encendido — no responde, no avanza, pierde la corrida.

- **risk-NO-fix:** un conector de color flojo (escenario común tras un choque) cuelga TODO el firmware. Es de los peores fallos: el robot queda inmóvil y el equipo no sabe por qué.
- **risk-fix:** el fix propuesto en #61 (timeout 50 ms → devolver "Desconocido") es de riesgo bajo; "Desconocido" cae en `action=7` (linetrack), comportamiento seguro. Único matiz: si el sensor está intermitente, devolverá "Desconocido" esporádicamente y se podría perder una detección de verde puntual — preferible a colgarse.
- **tiempo:** 15 min (el código exacto está en #61 y en `cead75e`).

---

### S-03 — [P1] `while(1)` infinito en init de BNO055 sin alerta visible

**Ya documentado en issue #62 (OPEN).** Re-confirmado tras el revert. Se cita.

`main.cpp:757-762` (setup) y `662-668` (`resetear_bno`):
```cpp
if (!bno.begin()) {
    Serial.print("No BNO055 detected ...");
    while (1) ;   // sin LED, sin buzzer
}
```
APDS9960 (766-774): el fallo de `apds.begin()` **ni se trata** — el código sigue como si todo estuviera bien, y luego `get_color()` se cuelga en el `while` de S-02.

- **risk-NO-fix:** si la IMU no inicializa (cable, dirección I2C, brown-out), el robot parece "muerto" salvo el LED de la Teensy. En la mesa de competencia, los alumnos pierden minutos creyendo que es el switch o la batería. El fallo de APDS pasa de "init mudo" a "cuelgue en runtime" sin pista.
- **risk-fix:** el fix de #62 (LED rojo + buzzer parpadeantes en el `while`) es de riesgo nulo (solo cambia la indicación). El modo degradado (seguir sin IMU) es refactor mayor — NO recomendado para esta ventana.
- **tiempo:** 20 min para la indicación visible (código en #62 y `cead75e`).

---

### S-04 — [P0/P1] BNO055 sin detección de fallo en runtime → heading basura silencioso

**Ya documentado en issue #109 / R-T06 (OPEN, severidad CRÍTICA).** Se cita y se agrega análisis específico de los lectores.

`leer_yaw()` (610-616), `leer_pitch()` (617-622) y el bloque inline de `runAngle()` (436-449) llaman `bno.getEvent(&event)` **sin chequear el `bool` de retorno**. Si la IMU pierde I2C en runtime, la lib Adafruit devuelve `0.0` o el último valor; el robot navega/gira con heading erróneo **sin saberlo**. `resetear_bno()` existe pero nunca se invoca automáticamente.

Esto es especialmente grave porque el heading alimenta **toda** la lógica de giros (`runAngle`), el centrado (`centrar`, líneas 828/1083), y `angulo_rescate` (998/1015/1036/1228) — un heading congelado en 0 hace que `calcularDiferenciaAngulo()` produzca giros arbitrarios.

- **risk-NO-fix:** falla silenciosa = la peor clase. El robot no se cuelga: hace lo incorrecto (gira de más/de menos, se va de la pista) y nadie entiende por qué. En rescate, un `angulo_rescate` basura arruina toda la secuencia de depósito.
- **risk-fix:** el fix de #109 (verificar retorno + flag `bno_ok` + detección de "heading congelado" >500 ms + degradar `runAngle` a giro por tiempo) es de complejidad media y toca el camino crítico de giros. Hay que probarlo bien en banco. La detección de "congelado" puede dar falso positivo si el robot está genuinamente quieto y derecho — debe condicionarse a "con motores girando".
- **tiempo:** 3-4 h (es el más caro del módulo). Plan ya detallado en #109, asignado a @Laumonteros @gviollaz, régimen Track A.

---

### S-05 — [P1] `leer_yaw()` declara variable local que ensombrece la global (#B4 — scope preciso)

**Relacionado con #B4 (mencionado en el contexto de auditoría como "leer_yaw no asigna global").** Aquí se **precisa el comportamiento real**, que es más sutil de lo que sugiere el título.

`main.cpp`:
```cpp
float yaw = 0;        // línea 608 — GLOBAL
float leer_yaw() {
    sensors_event_t event;
    bno.getEvent(&event);
    float yaw = event.orientation.x;   // línea 614 — LOCAL que ENSOMBRECE la global
    return yaw;                        // devuelve la local; la global queda en 0
}
```

**Análisis de impacto por consumidor (CRÍTICO entender bien esto):**
- Las llamadas que usan el **valor de retorno** funcionan correctamente: `centrar = leer_yaw()` (828), `angulo_rescate = leer_yaw()` (998/1015/1036), `calcularDiferenciaAngulo(leer_yaw(), …)` (1083/1228). En estos casos el bug es **inocuo** porque se consume el `return`.
- **El bug SÍ muerde en `avance_recto()`** (672-717): llama `leer_yaw();` (línea 674) **descartando el retorno**, y luego usa la **global** `yaw` en `calcularDiferenciaAngulo(yaw, TARGET_ANGLE)` (línea 678). Como `leer_yaw()` nunca asigna la global, `avance_recto()` **siempre corrige sobre yaw=0** → control de pared roto.

**Atenuante actual:** `avance_recto()` **no se invoca en el `loop()` vigente** (no aparece como call site activo; solo está definida). O sea: **el bug está latente, no activo hoy.** Pero es una trampa — en cuanto alguien reactive `avance_recto` (está pensada para seguir pared con ToF), fallará en silencio. `leer_pitch()` (617) sí asigna la global `pitch` correctamente, lo que hace la inconsistencia más confusa para quien lea el código.

- **risk-NO-fix:** hoy nada se rompe (función no usada). Pero es una mina: cualquiera que llame `avance_recto()` o que asuma "después de `leer_yaw()` la global `yaw` está fresca" obtiene 0. Dado que `leer_pitch()` sí actualiza su global, el patrón inconsistente induce a error.
- **risk-fix:** trivial y de bajo riesgo. Dos opciones: (a) quitar el `float` de la línea 614 para que asigne la global y además retornarla; (b) en `avance_recto` usar el retorno: `float yaw_actual = leer_yaw();`. La opción (a) es la más coherente con `leer_pitch()`. Verificar que ningún consumidor dependa de que la global quede en 0 (no se encontró ninguno).
- **tiempo:** 10 min + 10 min de banco si se reactiva `avance_recto`.

---

### S-06 — [P1] ToF devuelve `65535` (basura) en timeout y se propaga sin filtrar

**NUEVO.** Las auditorías previas cubren el fallo de BNO (#109) pero **no** el de los VL53L0X.

`leer_tof()` (284-288):
```cpp
distance_left_tof  = left_tof.readRangeContinuousMillimeters();
distance_right_tof = right_tof.readRangeContinuousMillimeters();
```
La lib (`lib/VL53L0X/VL53L0X.cpp:813-832`) en timeout hace `did_timeout = true; return 65535;`. Como los timeouts están en 500 ms (`setTimeout(500)`, líneas 789/793), si un ToF pierde I2C o no recibe eco, `leer_tof()` carga **65535** en las globales `int distance_left_tof / distance_right_tof`.

Quién lo consume: `avance_recto()` (línea 700) hace `TARGET_DISTANCE - distance_left_tof` → con 65535 el `distance_error` se va a ~-65465, `steer` satura a `MAX_STEER` y el robot vira a fondo contra la pared. Además **nadie llama `timeoutOccurred()`** en producción (solo `imprimir_tof()`, que ni se invoca), así que el flag de timeout de la lib se ignora por completo.

Atenuante: igual que S-05, `avance_recto()` y por ende `leer_tof()` **no están en el `loop()` activo** (`leer_tof()` se llama en 675 y 888; el 888 está en la rutina línea pero el resultado no se usa para decidir nada — es lectura "muerta"). Riesgo latente, pero el cableado de fallo ya está ahí.

- **risk-NO-fix:** si se reactiva el seguimiento de pared por ToF, un sensor que entra en timeout (500 ms es mucho — bloquea el loop además, ver S-10) manda 65535 y el robot se estrella contra la pared con steering saturado. Falla silenciosa + colisión.
- **risk-fix:** bajo. En `leer_tof()`, tras la lectura: si `>= 8190` (rango útil del VL53L0X ~2 m = 2000 mm; 65535 es claramente inválido) o si `timeoutOccurred()`, conservar el último valor válido o marcar `tof_ok=false`. Cuidado de no filtrar lecturas legítimamente grandes (pero el sensor satura ~1200-2000 mm, nunca 65535).
- **tiempo:** 30 min + banco al reactivar `avance_recto`. Además bajar `setTimeout` a ~30-50 ms para no bloquear (ver S-10).

---

### S-07 — [P2] `get_color()` nunca puede devolver "Plateado" — tabla de calibración sin entrada plateado (código muerto)

**NUEVO.**

La tabla de producción `known_colors[]` (main.cpp:324-329) tiene **solo 3 entradas**: "Rojo", "Negro", "Verde". **No hay "Plateado" ni "Blanco".** Sin embargo, el código compara contra "Plateado":
```cpp
if (color_detected == "Plateado") { ... }   // líneas 891, 894 (comentadas en producción)
```
Como `get_color()` elige el `known_colors[i].name` con menor error cuadrático, y "Plateado" no está en la tabla, **`color_detected` nunca puede valer "Plateado"**. El bloque de detección de plateado por sensor está comentado (891-898), y la detección real de silver llega por serial (`silver_line`, línea 930) desde la RPi. O sea: la detección de plateado por color en el Teensy es **código muerto + tabla incompleta**.

Comparar con el test `get_color_sensor.cpp` (test/sensors/color_sensor/), que **sí** tiene "Plateado" {16,22,25,77} y "Blanco" {25,35,49,131} — la calibración buena quedó en el test y la de producción quedó coja.

- **risk-NO-fix:** confusión y deuda. Si alguien intenta reactivar la detección de plateado por color (para no depender del serial), no funcionará y perderá tiempo. Además "Negro" {0,0,0,67} y "Verde" {3,7,7,19} están muy juntos en clear→ riesgo de confundir verde con negro en piso oscuro (ver S-08).
- **risk-fix:** bajo si solo se documenta/elimina el código muerto. Medio si se decide **agregar** "Plateado"/"Blanco" a producción y reactivar la rama — requiere recalibrar en pista (ver S-08) y validar que no rompa el conteo de verde.
- **tiempo:** 15 min documentar/limpiar; 1-2 h si se reincorpora plateado al sensor (incluye recalibración).

---

### S-08 — [P1/P2] Calibración de color hardcodeada, sin blanco/ambiente y con clases muy próximas

**NUEVO (oportunidad).**

Los valores `known_colors[]` están **hardcodeados** y son de una sesión de iluminación específica. No hay normalización por luz ambiente ni referencia de blanco. Con clasificador de mínimos cuadrados sobre R/G/B/C absolutos, **cualquier cambio de iluminación en Incheon** (focos del estadio, sombras del robot) desplaza todo y rompe la clasificación. Además:
- "Negro" {0,0,0,67} y "Verde" {3,7,7,19} tienen R/G/B casi idénticos; los distingue casi solo el canal C (clear) — frágil.
- No hay histéresis ni filtrado temporal: una lectura espuria cambia `color_detected` de inmediato (impacta `action`).

- **risk-NO-fix:** en pista nueva con luz distinta, la detección de verde/negro se degrada → giros de intersección errados, pérdida de puntaje. Es un riesgo clásico de RCJ que muerde en competencia, no en el lab.
- **risk-fix:** medio. Normalizar por clear (`r/c, g/c, b/c`) o calibrar in-situ con una rutina al arrancar mejora robustez, pero **cambia el espacio de comparación** y obliga a re-tomar todos los `known_colors`. Debe hacerse con tiempo de pista, no a último momento. Mínimo viable: agregar un umbral de "clear" para distinguir línea negra de piso blanco antes de discriminar color.
- **tiempo:** 2-4 h (incluye sesión de calibración con la iluminación objetivo). Idealmente se hace en Incheon durante práctica, no antes.

---

### S-09 — [P2] Sin health-check unificado ni fusión sensorial

**Oportunidad (complementa #27 watchdog, #53 heartbeat, #109 BNO).**

No existe ninguna función tipo `sensores_ok()` que verifique al arranque y periódicamente el estado de los 4 sensores y exponga un flag/LED por cada uno. Hoy:
- BNO: sin flag (S-04).
- APDS: tenía `color_sensor_ok` → revertido (S-01).
- ToF: sin flag, ignora `timeoutOccurred()` (S-06).
- Ultrasonido: `ping_cm()` devuelve 0 cuando no hay eco; el código trata 0 como "sin obstáculo" (línea 921 `front_distance != 0 && front_distance < 12`) — razonable, pero 0 también es el valor de "sensor muerto", indistinguible.

Además hay **redundancia desaprovechada**: frente tiene ultrasonido (`front_distance`) y los laterales tienen ToF **y** ultrasonido (izq/der). Nunca se cruzan. Un health-check podría usar la discrepancia ToF-vs-US lateral para detectar un sensor caído (fusión simple), y el ultrasonido frontal como respaldo si un ToF muere.

- **risk-NO-fix:** sin visibilidad de salud, los fallos de S-03/S-04/S-06 se descubren tarde (en plena corrida). No es un cuelgue nuevo, es falta de observabilidad.
- **risk-fix:** bajo-medio. Un `sensores_ok()` que solo lee flags y enciende LEDs es seguro. La fusión (cruce ToF/US) es más invasiva y puede introducir lógica que confunda si se calibra mal — dejar para después del mundial salvo que sobre tiempo.
- **tiempo:** 1 h para health-check + LEDs de diagnóstico; +2-3 h para fusión lateral (opcional, post-mundial).

---

### S-10 — [P2] Lecturas ToF bloqueantes con timeout de 500 ms en el hot loop

**NUEVO.**

`readRangeContinuousMillimeters()` (lib, 813-823) hace **busy-wait** hasta que `RESULT_INTERRUPT_STATUS` indique dato listo, con `setTimeout(500)`. En operación normal el dato llega rápido, pero si un ToF está intermitente, **cada `leer_tof()` puede bloquear hasta 500 ms × 2 sensores = 1 s** dentro del loop, congelando el seguimiento de línea y el procesamiento serial durante ese tiempo. En `avance_recto()` esto es doblemente malo (combina con S-06).

- **risk-NO-fix:** un ToF flojo no cuelga "para siempre" pero introduce stutters de hasta 1 s que el equipo podría confundir con un problema de motores o de comms. Degrada el control de línea de forma intermitente y difícil de diagnosticar.
- **risk-fix:** bajo. Bajar `setTimeout` a 30-50 ms (suficiente para la tasa de conversión del VL53L0X en continuo) limita el peor caso. Combinar con el filtro de 65535 de S-06.
- **tiempo:** 10 min (dos líneas: 789, 793) + verificación.

---

## 3. Tabla consolidada risk / tiempo

| ID | Prioridad | risk-NO-fix | risk-fix | Tiempo | Cita previa |
|---|---|---|---|---|---|
| S-01 | P0 | 3 modos de cuelgue/silencio activos; reinvención de código ya escrito | Reintroduce 180 líneas; el revert pudo ser intencional (motivo desconocido) | 0.5 h investig. + 1-2 h restaurar selectivo | NUEVO (vincula #59/#60/#61/#62, commit `cead75e`) |
| S-02 | P1 | Conector color flojo cuelga TODO el firmware | Bajo; "Desconocido"→linetrack seguro | 15 min | #61 (revertido) |
| S-03 | P1 | Robot "muerto" sin diagnóstico; APDS ni se trata | Nulo (solo indicación) | 20 min | #62 (revertido) |
| S-04 | P0/P1 | Heading basura silencioso → se va de pista / rescate roto | Medio; toca camino crítico de giros | 3-4 h | #109 / R-T06 |
| S-05 | P1 | Latente: `avance_recto` corrige sobre yaw=0 al reactivarse | Trivial | 10 min | #B4 (scope precisado) |
| S-06 | P1 | Latente: 65535 → steering saturado, choque contra pared | Bajo | 30 min | NUEVO |
| S-07 | P2 | Código muerto; "Plateado" inalcanzable por sensor | Bajo (documentar) / medio (reactivar) | 15 min – 2 h | NUEVO |
| S-08 | P1/P2 | Detección color se degrada con luz de Incheon | Medio; obliga recalibrar todo | 2-4 h | NUEVO |
| S-09 | P2 | Sin observabilidad de fallos de sensor | Bajo (health-check) / medio (fusión) | 1 h + 2-3 h opc. | complementa #27/#53/#109 |
| S-10 | P2 | Stutters de hasta 1 s con ToF intermitente | Bajo | 10 min | NUEVO |

---

## 4. Recomendación de secuencia (para discutir con el equipo)

1. **Primero, entender `cead75e` (S-01).** Antes de tocar nada, preguntar a Benjamin/Enzo **por qué** se revirtió el sistema de flags (el mensaje de commit no lo dice). De ahí sale si se restaura o se reescribe. El código del fix de #61/#62 ya existe en `git show cead75e` — esto debería ahorrarle trabajo a Laureano (que en #115 tiene asignado "recuperar #60/#61").
2. **Quick-wins de bajo riesgo (S-02, S-03, S-05, S-06, S-10):** ~1.5 h en total, todos de riesgo bajo/nulo, varios con el código ya escrito. Cierran cuelgues y minas latentes.
3. **S-04 (BNO runtime):** el más caro y más valioso. Ya tiene plan en #109. Hacer en banco con la prueba de desconexión de SDA en caliente.
4. **S-08 (calibración color):** idealmente **en Incheon**, con la iluminación real, durante práctica. No invertir tiempo en calibrar acá con luz distinta.
5. **S-07, S-09:** documentar/limpiar deuda; health-check si sobra tiempo; fusión sensorial → post-mundial.

> **Nota de método:** los findings S-02/S-03/S-04 NO se proponen como issues nuevos — ya existen (#61, #62, #109) y están abiertos. La acción es **vincularlos a `cead75e`** y registrar que el fix fue revertido. Solo S-01 (meta), S-06, S-07, S-08, S-10 ameritan issues nuevos. Cada uno con la plantilla `audit-finding.yml` y entrada en `testing/TEST_LOG.md` al validarse, según el workflow del repo.

---

*Auditoría de solo-lectura. No se modificó `software/**` ni `hardware/**`. No se crearon ni editaron issues/PRs.*
