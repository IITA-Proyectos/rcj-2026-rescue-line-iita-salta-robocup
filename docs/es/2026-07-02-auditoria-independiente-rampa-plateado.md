# Auditoría independiente — "no sube la rampa" / "no entra a rescate"

**Fecha:** 2026-07-02
**Rol:** auditoría independiente (arquitectura de sistemas + coach Rescue Line). Escepticismo por defecto.
**Método:** lectura línea por línea del código real; recálculo de cada número de cero; cada afirmación validada por hasta **4 métodos independientes** (traza estática, recálculo numérico/diferencial vs repo, semántica de plataforma/librería, y reconciliación con la conducta observada). El diagnóstico del 2-jul se trató como **hipótesis a testear, no como verdad**.
**Firmware auditado:** el que corrió hoy = `C:\Users\violl.DESKTOP-FD94JER\Downloads\main.cpp` (NO es el del repo; el repo tiene una versión más vieja). Visión: `software/raspberry/final_rpi/Main.py`.

> **Estándar de este documento:** lo que digo "VERIFICADO-EN-CÓDIGO" está probado contra las instrucciones reales. Lo que digo "NECESITA-BANCO" es hipótesis con evidencia pero sin confirmar físicamente, y va con la medición exacta que lo cierra. No se manda a los alumnos a cambiar nada que no esté en la primera categoría o precedido por su medición.

---

## 0) Correcciones (anti-adulación: incluye errores míos y del 2-jul)

La auditoría independiente **dio vuelta dos afirmaciones que yo mismo te había dado antes como fuertes**. Las corrijo explícitamente:

1. **"El steer queda congelado en la línea porque el case 7 no llama `serialEvent5()`."** → **FALSO.** En Teensy 4.x la librería `Wire` (I2C) llama `yield()` mientras espera cada transferencia (confirmado en fuente PJRC autoritativa). El loop de línea hace lecturas I2C **cada iteración** (`leer_tof()` → 2× VL53L0X, `ajustarVelocidadPorPendiente()` → BNO055, `get_color_fast()` → APDS9960), y cada una dispara `yield()` → que ejecuta `serialEvent5()`. **El serial SÍ se drena varias veces por vuelta; `steer`/`green_state`/`silver_line` están frescos.** Esto también refuta el ítem "serial no drenado en línea" del 2-jul. (Reconcilia con lo observado: por eso el robot sí siguió curvas y reaccionó a los verdes.)

2. **"El pitch se lee del eje equivocado (`.y` = roll)."** → **NO VERIFICABLE POR CÓDIGO; es una contradicción documentada.** Las fuentes autoritativas se contradicen: el datasheet Bosch + el orden de registros Euler dicen `.y = roll, .z = pitch`; pero los **ejemplos Adafruit vendorizados en el propio repo** (`test/sensors/BNO055_examples/webserial3d.cpp:112`, `bunny.cpp:100-104`) rotulan `.y = pitch, .z = roll`. Como además el eje efectivo depende del **montaje físico** del chip, esto **solo se resuelve midiendo** (ver P1, Paso 0). Retiro mi afirmación anterior de que `.y` era seguro que fuera roll.

Ambas correcciones son el motivo por el que esta auditoría valió la pena: dos "certezas" previas no sobrevivieron a la verificación independiente.

---

## 1) El hecho técnico que reordena TODO (VERIFICADO-EN-CÓDIGO)

**El firmware ya entrega PWM máximo (255) a la rueda cuando se frena. No hay "más fuerza" que darle por software.**

Cadena verificada de cero:
- Los motores usan **PID de velocidad, integral puro**: `drivebase.h:30` `_kp=0, _ki=22, _kd=0`. El "speed" de `robot.steer()` es **setpoint de RPM**, no PWM (`drivebase.cpp:113`, `drivebase.h:16 setSpeed(int dir, double rpm)`).
- Con kp=kd=0 la salida ES el integrador (`PID.cpp:64` `outputSum += ki*error`; `PID.cpp:85/91` `output = outputSum`), saturado a **[0, 255]** (`PID.cpp:22`).
- `ki` interno = `22 × 0.1 = 2.2` por ciclo de 100 ms (`PID.cpp:127`, `SampleTime=100`).
- **`PID::Reset()` no se llama nunca** (0 coincidencias en el firmware) → el integrador acumula libre.
- Si la rueda se frena en la rampa, `error ≈ 40 RPM` → `outputSum` sube ~`2.2×40 = 88`/ciclo → **satura a 255 en ~3 ciclos (~300 ms)**. `analogWrite(pin, 255 - _pwmVal)` (`drivebase.cpp:51`) = PWM efectivo máximo.

**Consecuencias que hay que grabarse:**
- Con setpoint 40 **o** 45, si la rueda no llega a la RPM pedida, el PWM al motor es el MISMO (255). **El "boost" 40→45 NO agrega tracción.**
- Si con PWM 255 el robot igual no trepa → la causa es **física** (par/tracción/peso/geometría/batería). **Ningún cambio de firmware lo resuelve.**
- Esto **refuta** como causa de P1 al "PID lento" (satura sub-segundo) y vuelve **irrelevantes** para trepar las causas "boost/pitch" (aunque sean ciertas en código).

---

# PROBLEMA 1 — No sube la rampa

## Causas raíz (ordenadas por probabilidad de ser el fallo de hoy)

### CAUSA A — Anti-atasco que retrocede/embiste en la rampa (candidata #1 de *software*)
**Mecanismo VERIFICADO-EN-CÓDIGO; que dispare en la rampa NECESITA-BANCO.**

Es el **único cambio de comportamiento nuevo** en el hot path de linetrack respecto del repo (differential: el repo NO tiene anti-atasco).
- Se llama **incondicionalmente** cada vuelta en el case 7: `main.cpp:2115-2120` (`if (chequearAtasco(...)) { recuperarAtasco(); break; }`).
- Dispara si `min(ΔfrontRight, ΔfrontLeft) < 15` pulsos/100 ms sostenido **3 s** (`UMBRAL_RUEDA=15` L1614, `STUCK_TIME_MS=3000` L1616). **No lee pitch/IMU**: trata la rampa igual que la loma de burro.
- Recálculo: 15 pulsos/100 ms = 150 pulsos/s ÷ 25 pulsos/cm = **6,0 cm/s**. Si la rueda más lenta trepa a <6 cm/s durante 3 s corridos → "atasco". *(El factor 25 pulsos/cm sale de `runDistance`; el `[CAL]` loguea pulsos crudos, así que la medición no depende de que ese factor sea exacto.)*
- El grace de 8 s se arma **una sola vez** al arrancar (`main.cpp:1850`) y **nunca se re-arma** → en la rampa (que está lejos del arranque) **ya expiró**.
- `recuperarAtasco()` (`main.cpp:1661-1671`): 150 ms de **reversa a vel 90** + **450 ms de avance a vel 100**.

**Corrección al 2-jul:** no "solo retrocede". Hace reversa corta **y luego embiste a full 450 ms**. En la rampa el efecto neto es un ciclo *"bajo un poco / embisto"* cada ~3 s, que puede **ayudar** (momentum) o **tirarlo fuera de la rampa** — cuál de las dos es física.

Por qué es candidata #1 de software: es 100% código (no depende del BNO), es lo único NUEVO en el hot path, y "no sube" es compatible con "cada 3 s retrocede".

### CAUSA B — Límite de par/tracción mecánico (candidata #1 global)
**NECESITA-BANCO. El código no la confirma ni la refuta, pero apunta a ella.**
Del punto 1: el firmware ya manda PWM 255 cuando la rueda se frena. Si con par máximo no trepa, **es mecánico** (peso, reparto sobre el eje motriz, goma, reducción, ángulo de ataque, tensión de batería). Es, por frecuencia física, la causa más común de "no sube la rampa" en Rescue Line.

### CAUSA C (RETIRADA) — "steer congelado en case 7"
**REFUTADA.** Ver §0.1: el serial se drena vía `yield()` de las lecturas I2C. El steer está fresco. **No** hace falta agregar `serialEvent5()` al case 7.

### CAUSA D — Detección de pendiente dudosa (real en código, pero irrelevante para trepar)
`main.cpp:1365` `pitch = event.orientation.y`; umbral `pitch > 3.9` de un solo signo, sin offset, sin histéresis; `velocidadBase` es código muerto (`1377-1385`). **Todo cierto**, pero por el punto 1 **corregirlo no agrega par** → no hace subir la rampa. Su único valor para P1 es como *gate* del anti-atasco (Solución A1), y para eso hay que saber cuál eje es el pitch (§0.2, NECESITA-BANCO).

### Descartado para P1 (no perder tiempo)
- **Boost 40→45 / `velocidadBase` muerto** (L1-C2/L2-2): cierto, pero cosmético (punto 1). Deuda, no fix.
- **Rueda interna en reversa con |steer|>0.7** (`drivebase.cpp:141-146`, `55−2·0.7·55 = −22` RPM): cierto, pero es el **mismo** comportamiento en llano que hoy funciona. Solo aplicaría si hay curva cerrada **sobre** la rampa (dato inexistente en código).
- **"steer torcido → rueda interna clavada → dispara anti-atasco":** refutado — `chequearAtasco` usa `labs(Δpulsos)` (`main.cpp:1642-1643`); una rueda en reversa tiene Δ alto, no cuenta como clavada.
- **"PID integral-puro deja bajo el par":** refutado — satura a 255 en ~300 ms.

## Solución (la más simple y confiable): MEDIR antes de tocar

**No cambiar una línea antes del Paso 0.** Hoy no está probado cuál de A/B es el mecanismo real, y B (mecánico) no se arregla con firmware. El firmware **ya tiene toda la telemetría** — la medición cuesta ~10 min y 1 línea de print temporal.

**Paso 0 — Medición discriminante (obligatoria, casi cero código):**
1. Agregar temporalmente en el case 7 (tras `main.cpp:2115`):
   `Serial.print("pitch="); Serial.print(pitch); Serial.print(" pwm="); Serial.print(fr.getPWM()); Serial.print(" set="); Serial.println(velocidadAjustada);`
   y para el eje del BNO, loguear también `event.orientation.x/y/z`.
2. Correr el robot subiendo la rampa real, en linetrack, con el grace ya expirado (condición de competencia), monitor serial abierto. Ya se imprimen `[CAL] frD/flD/min` (`1647-1649`) y `[ATASCO]` (`1663`).
3. **Leer el resultado:**
   - **Aparece `[ATASCO]` durante el trepado** → **CAUSA A**. Ir a A1/A2.
   - **NO aparece `[ATASCO]`, `pwm ≈ 255` y no sube** → **CAUSA B (mecánico)**. **No tocar firmware.**
   - Anotar qué eje (`x/y/z`) cambia al inclinar y con qué signo → resuelve §0.2 y habilita A1.

**Si el banco muestra `[ATASCO]` en la rampa:**
- **A1 (la más simple, si el pitch resultó usable) — gate por pitch en `chequearAtasco`** (inicio, `main.cpp:1619`), replicando la forma del gate de grace ya existente:
  ```cpp
  if (leer_pitch() > UMBRAL_RAMPA) { stuck_since = now; return false; }
  ```
  Usar el eje/umbral que confirmó el Paso 0. Deja el anti-atasco intacto para la loma en llano; solo lo silencia inclinado. Falla-seguro: si el eje está mal, no empeora (queda como hoy).
- **A2 (si el pitch no sirve) — desactivar el anti-atasco solo en case 7** vía flag nuevo en `priority_fix_flags.h` (default off) o comentando `main.cpp:2117-2120`. Devuelve el case 7 al comportamiento **del repo** (que trepaba-o-no sin retroceder). Costo: se pierde la recuperación anti-palos en toda la corrida.
- **A3 (parche, menos confiable) — subir `STUCK_TIME_MS`** (`1616`) de 3000 a > tiempo de coronar. Un literal; no distingue rampa de loma. Solo temporal.

**Si el banco muestra `pwm ≈ 255` sin trepar:** causa **mecánica**. Firmware no toca nada. Va a hardware (peso/goma/reparto/CG), documentado en `hardware/cambios_de_hardware.md`.

---

# PROBLEMA 2 — No entra a rescate / no detecta plateado

## Reconciliación con la conducta de hoy (leer primero)
**La corrida de hoy NO prueba P2.** La línea plateada marca la entrada a evacuación, que en Rescue Line está **después** de la rampa. Si el robot no subió la rampa, **es muy probable que nunca haya pisado la cinta plateada**. Entonces:
- Que hoy "no entrara a rescate" está **explicado por P1** (no llegó), no necesariamente por los bugs de plata.
- Los bugs de detección de plata están **VERIFICADOS-EN-CÓDIGO** (impedirían el ingreso aunque llegara), pero **su activación hoy es NO-CONCLUYENTE**.
- **Prioridad operativa:** primero P1. P2 se cierra en banco **en paralelo**, porque son bugs demostrados; no se valida en pista hasta que el robot llegue físicamente a la plata.

## Causas raíz verificadas

Hay **dos caminos independientes** a `action=2 → rutina="rescate"`: (A) sensor APDS local (`main.cpp:1974`), (B) `silver_line` por serial desde la RPi (`main.cpp:1970`). El gating posterior está **sano** (C0).

### C0 — El gating NO es la barrera (VERIFICADO-EN-CÓDIGO 100%)
`taskDone` es `true` al entrar a la línea y **nunca vuelve a `false`** (grep: no existe `taskDone=false`); `if(taskDone)` (`1940`) siempre corre. `case 2` (`2024`) hace `rutina="rescate"` sin condición extra. **Un solo detector alcanza.** La falla está 100% aguas arriba: **ningún detector dispara.** No buscar el bug en el gating.

### C1 — [Camino A / APDS, PRINCIPAL] El umbral de "Plateado" es inalcanzable con su propia calibración (VERIFICADO-EN-CÓDIGO)
- Ruta viva: `get_color_fast()` (`1886`) → `classify_color()` (`604`). Es el único clasificador vivo (`get_color_old`/`get_color_blocking_legacy` están muertas).
- Umbral (`main.cpp:625`): `if (c > 2220 && ratio_rc > 0.234f) → "Plateado"`.
- Referencia calibrada de plata (`main.cpp:536`): `{500,900,900,2300}` → **r/c = 500/2300 = 0,2174 < 0,234 ⇒ FALLA** (a c=2300 el umbral exige r ≥ 538; la plata mide 500). Cae en la rama **"Blanco"** (`629`: `c>1500 && ratio_rc≤0.235`).
- **Agravante — la tabla es físicamente incoherente:** el Blanco `{570,…,2685}` es **más brillante** que la plata (c 2685 > 2300) y su r/c=0,2123 es casi idéntico. Recalculé **todos los ejes**: r/c 0,212 vs 0,217; g/c 0,376 vs 0,391; r/g 0,564 vs 0,556; r/b idénticos. **Ningún eje de la tabla separa plata de blanco.**
- Consecuencia: `color_detected=="Plateado"` nunca es cierto → nunca `plateadoDetectado` (`1893`) → nunca `action=2` (`1974`) ni `Serial5.write(241)` (`1896`).
- **NUEVO:** el mismo `classify_color` roto lo usan también `detectarPlateado()` (`1294`) y `procesarColorEvacuacion()` (`1317`) → el bug afecta la detección de plata **también dentro de evacuación**, no solo el ingreso.

### C2 — [Camino B / serial] El plateado por visión nunca se emite (VERIFICADO-EN-CÓDIGO)
- **RPi: máscara en espacio de color equivocado.** `Main.py:793` `silver_mask = cv2.inRange(frame_resized, lower_silver_hsv, upper_silver_hsv)`. `frame_resized` es **BGR** (`770`, resize sin convertir); las cotas son HSV (`74-75`). Recálculo: la intersección de bandas para un gris neutro (B=G=R) es **vacía**; solo un azul navy oscuro matchea. **El plateado es matemáticamente imposible de detectar.** (El rojo, en cambio, sí usa `hsv_frame`, `789-790`.) → la RPi manda `silver_line=0` siempre.
- **Corrección a un ítem del 2-jul y de esta auditoría:** la sub-causa "la Teensy no drena `silver_line` en case 7" es **FALSA** (§0.1: se drena vía `yield()` de I2C). El camino B no muere por el serial de la Teensy; muere **en la RPi**, que nunca pone `silver_line=1`.

### C3 — Desync RPi/Teensy (real, pero NO es causa próxima)
La RPi flipea `estado='rescate'` local por su propia detección (`Main.py:890-891`) sin esperar el 241, y un disparo por camino B no reenvía 241. **Verificado**, pero es lo que pasa *después* de detectar plata. Con la detección rota, arreglar el desync no mueve la aguja. **Deuda, no fix de P2.**

## Solución (la más simple y confiable): MEDIR antes de tocar el umbral

**Principio: resolver UN camino confiablemente, no los dos a medias.** El camino A (APDS) es el más corto y autosuficiente (no depende de la RPi ni del serial). Es el fix primario.

**Paso A — Medición APDS (obligatoria, 0 cambios de lógica):**
1. `main.cpp:611` → `bool shouldPrint = true;` (el print ya está cableado). Flashear.
2. Con el sensor a **altura y velocidad reales de pista** e iluminación de competencia, loguear `R, G, B, C, r/c` sobre: (i) la cinta plateada real de evacuación, (ii) el blanco de la pista. ~20 muestras de cada una.
3. **Decisión:** ¿algún eje (c, r/c, g/c, …) separa las dos nubes con margen?
   - **Sí** → **Paso B**: reescribir SOLO la condición `main.cpp:625` con el corte en el punto medio medido. No tocar nada más de la cadena (está sana, C0).
   - **No** → el APDS no discrimina plata de blanco; ir al camino B (visión).
4. Revertir `shouldPrint=false` antes de competir.

**Por qué es obligatorio medir:** la tabla vigente da plata ≈ blanco en todos los ejes, y la referencia de plata es **sospechosa de stale** (una superficie especular debería dar C **más alto** que el blanco mate; la tabla dice lo contrario). **Bajar el 0,234 a ciegas puede meter falso rescate sobre blanco en plena pista — peor que hoy.** Recomendar un número sin banco es adivinar.

**Fix del camino B (redundancia, o primario si el APDS no separa) — `Main.py:793`, 1 palabra:**
```python
silver_mask = cv2.inRange(hsv_frame, lower_silver_hsv, upper_silver_hsv)
```
`hsv_frame` ya se computa (`785`), reusa la calibración HSV, queda coherente con el rojo. Elimina la imposibilidad matemática. **Pero** requiere recalibrar `lower/upper_silver_hsv` (`74-75`) sobre la cinta real con `calibration.py` bajo luz de competencia; sin eso, elimina el bug pero no garantiza detección. (No necesita tocar el serial de la Teensy: ya se drena.)

**Decisión de arquitectura:** elegir **una** fuente de verdad. Si el banco muestra que el APDS separa plata de blanco → APDS primario, camino B queda como deuda opcional. Si no separa → la visión es la fuente (fix RPi + recalibración). **No arreglar los dos a medias.**

---

## Qué se CONFIRMA / DESCARTA / es NUEVO respecto del 2-jul

**Confirmado (recalculado de cero):** anti-atasco sin gate por pitch metido en el hot path; grace de 8 s que ya expiró en la rampa; boost cosmético + `velocidadBase` muerto; umbral APDS incoherente (plata → "Blanco"); RPi `inRange` BGR con cotas HSV.

**Descartado / corregido:**
- **"Serial/steer congelado en línea"** → refutado (I2C hace `yield()` → drena serial). Vale para P1 (no era causa) y para P2 (el camino B no muere por el serial de la Teensy).
- **"PID lento deja bajo el par"** → refutado (satura a 255 en ~300 ms).
- **"Arreglar pitch/boost hace subir la rampa"** → descartado (PWM ya saturado).
- **"steer torcido dispara el anti-atasco"** → refutado (`labs`).
- **"Basta bajar el umbral 0,234 y anda"** → descartado como certeza: la tabla no separa plata de blanco en ningún eje; sin banco es adivinar y puede empeorar.
- **Eje `.y` = roll** → no verificable por código (fuentes contradictorias); NECESITA-BANCO.

**Nuevo:**
- **`PID::Reset()` nunca se llama** → integrador libre → PWM satura a 255 → reordena todo P1 (mecánico vs software).
- **El anti-atasco es código NUEVO** (differential vs repo): único cambio de comportamiento en el hot path.
- **`taskDone` nunca vuelve a `false`** → el gating no es la barrera (P2).
- **La topología** (plata después de la rampa) → la conducta de hoy no prueba P2.
- El mismo `classify_color` roto afecta también la detección de plata **en evacuación**.

---

## Orden de ejecución (mínimo riesgo sobre lo que hoy funciona)

1. **P1 primero** — bloqueó la corrida y es prerrequisito físico para testear P2.
2. **P1 · Paso 0** (medición en rampa; 1 print temporal). Sin riesgo. Discrimina A (anti-atasco) vs B (mecánico) de una sola vez.
3. **P1 · fix según banco:** A1 (gate por pitch) o A2 (flag anti-atasco off en case 7) si aparece `[ATASCO]`; **hardware** si `pwm≈255` sin trepar. Re-testear loma en llano antes de aceptar.
4. **P2 · Paso A** (medición APDS plata vs blanco; solo habilitar el print). En paralelo con P1. Sin riesgo.
5. **P2 · fix según banco:** reescribir el corte en `main.cpp:625` (toca solo la frontera Blanco/Plateado; no roza Negro/Verde/Rojo/motores/PID/comms), o pasar a visión (`Main.py:793` + recalibrar).
6. **No tocar:** gating (C0), cadena posterior a la clasificación, protocolo serial (C3), y todo subsistema validado. Nada de rediseños (histéresis/fusión/handshake) hasta que el banco demuestre que el fix mínimo no alcanza.

**Regla dura:** ningún cambio de umbral ni de firmware de control llega a los alumnos sin su medición de banco previa. El testing en hardware lo cierra el equipo humano.

---

## Apéndice — método y trazabilidad

- **Verificación:** 8 lentes de análisis independientes → cada claim validado por 4 métodos independientes (traza / numérico-diferencial / plataforma / conducta) → solo sobrevive lo confirmado por ≥2 métodos sin refutación. Dos claims fueron **refutados** por el propio proceso (el eje del BNO y el "PID lento"), y dos afirmaciones previas mías fueron corregidas (serial congelado; eje roll).
- **Hechos de plataforma confirmados en fuente autoritativa:** Teensy 4.x `Wire`/`WireIMXRT` llama `yield()` durante las esperas I2C (PJRC); Teensy ejecuta `serialEventN()` desde `yield()`; convención Euler del BNO055 **contradictoria** entre datasheet/registros y ejemplos Adafruit (por eso el eje es NECESITA-BANCO).
- **Números recalculados de cero:** r/c plata 500/2300 = 0,2174 (< 0,234); anti-atasco 15 pulsos/100 ms = 6,0 cm/s; PID satura 255 en ~3 ciclos de 100 ms; rueda interna a |steer|>0,7 → −22 RPM; boost (45−40)/40 = 12,5 %.
- **Archivos load-bearing:** `main.cpp` (clasificador 604-632, tabla 532-538, cadena línea 1882-1976, case 7 2113-2133, anti-atasco 1619-1671, ajuste pendiente 1373-1386, `leer_pitch` 1360-1367, `taskDone` 110/1276/1792, print 611); `drivebase.cpp`/`.h` (PID 30-31, setSpeed 39-53, steer 111-156); `PID.cpp` (Compute 50-102, límites 22); `Main.py` (silver 74-75/793, hsv_frame 785, silver→estado 890-891); `priority_fix_flags.h:13`.
