# Auditoría DECISIÓN / FSM de alto nivel — `Main.py` (RPi)

> **Dominio:** máquina de estados de alto nivel de la Raspberry Pi y toda la toma de decisiones que vive en `software/raspberry/final_rpi/Main.py`:
> FSM `esperando → linea → rescate → depositar → depositar verde`, cálculo de ángulo/steer (línea y rescate), decisión de verde/intersección, `choose_stable_target` / `select_target_from_list`, `CentroidTracker`, y la lógica de búsqueda de víctimas.
>
> **Autor:** auditoría integral 2026-05-18 (Track B / visión-RPi, capa de decisión).
> **Commit auditado:** checkout actual de `feature/initialize-testing-log` (post-merge PR #101; idéntico a `main`). HEAD `5a868ea`.
> **Alcance:** SOLO LECTURA. No se modificó código. Los "fix" son propuestas con diff sugerido, no aplicadas.
> **Convención IITA:** cada finding lleva **riesgo de NO fixear**, **riesgo de fixear** y **tiempo estimado**. No son "bugs a fixear a ciegas": son TEMAS A ANALIZAR con el equipo. La decisión final es de Enzo (coach) y los alumnos, que llevan meses tuneando.

---

## 0. Cómo leer este informe (deduplicación con auditorías previas)

Hay dos auditorías previas que **NO se repiten** acá; se citan y se agrega lo nuevo:

- **RESILIENCIA** (issues #53, #27, #57–#119): heartbeat, WDT, timeouts revertidos en `cead75e`, crashes, auto-restart.
- **CORRECTITUD** (issues #120–#128): bugs B1–B10 + bugs medios + oportunidades.

Findings de la capa de DECISIÓN que **ya tienen issue** y que solo se referencian (con matiz nuevo donde corresponde):

| Ya filado | Issue | Qué cubre | Qué agrega ESTE informe |
| :-- | :-- | :-- | :-- |
| `cx_black` sin inicializar (crash) | **#110 (R-V08)** | El `UnboundLocalError` crudo y el fix de init + try/except. | La **decisión de verde es semánticamente incorrecta** aun con el init puesto (mezcla de ROIs distintos). Ver **D1**. |
| Mapeo clases YOLO invertido | **#120 / B3** | `cls==0→black`, `cls==1→silver` en L624-631. | La inversión **también** rompe `select_target_from_list` (L509) y los filtros de estado (L491-494). Ver **D2**. |
| `silver_mask` en BGR con rangos HSV | **#120 / B2** | L750 usa `frame_resized` en vez de `hsv_frame`. | Es la **condición de entrada a `rescate`** (L818-819): si no dispara, la FSM nunca sale de `linea`. Solo se referencia. |
| Verde LAB rango L restrictivo | **#127 / B-V03** | L70 rango muy angosto. | Afecta el gate `np.sum(green_mask)` (L759) de toda la decisión de verde. Solo se referencia. |
| `cls` por `round()` vs `argmax` | **#127 / B-V04** | L486. | Afecta qué objetivo elige la FSM de rescate. Solo se referencia. |
| Salida anticipada del cuarto | **#123 / B6** | Lado Teensy (`main.cpp:1222`). | Su **contraparte RPi** es la búsqueda ciega (ver **D3**): la RPi no aporta evidencia de "no hay más víctimas". |

Lo que sigue (**D1–D12**) es la auditoría propia de la capa de decisión. **D1, D2, D3, D4 son nuevos o agregan severidad nueva** sobre lo ya filado.

---

## 1. Mapa de la FSM tal como está hoy

Estados (variable global `estado`, string):

```
'esperando'  → loop L713-718. Solo lee serial. Sale a 'linea' cuando Teensy manda READY (0xF9) (handle_control_byte L165-169).
'rescate'    → loop L720-721. Llama modo_rescate() en bucle.
'linea'      → loop L724-845. Visión clásica OpenCV (negro/verde/rojo/plateado). Sale a 'rescate' si silver_line (L818-819).
'depositar'        → NO tiene loop propio en el while-True. Es un SUB-estado dentro de modo_rescate().
'depositar verde'  → idem, sub-estado dentro de modo_rescate().
```

Transiciones (todas las asignaciones a `estado`):

| Línea | Origen | Destino | Disparador |
| :-- | :-- | :-- | :-- |
| L158 | cualquiera | `esperando` | Teensy BOOT (0xFA) |
| L162 | cualquiera | `esperando` | Teensy STOP (0xFF) |
| L167 | `esperando` | `linea` | Teensy READY (0xF9) |
| L173 | `rescate` | `depositar` | Teensy RESCATE_DONE (0xF8) |
| L634 | `depositar` | `depositar verde` | YOLO ve zona verde (cls==3) y `close_enough` |
| L819 | `linea` | `rescate` | `silver_line==True` |

**Hallazgo estructural (ver D4):** `depositar` y `depositar verde` se alcanzan **mientras `modo_rescate()` sigue corriendo** (son sub-estados leídos por los filtros YOLO de L491-496 y `select_target_from_list` L505-518). Pero el `while estado == 'rescate'` (L720) ya **no se cumple** cuando `estado` pasó a `'depositar'`. La única razón por la que esto "funciona" hoy es que `modo_rescate()` **no chequea `estado` en su condición de bucle** — corre hasta que `stop_rescate` se active. Es una FSM con dos niveles implícitos y frágiles que conviene explicitar antes de Incheon.

---

## 2. FINDINGS — capa de decisión

### D1 · La decisión de verde mezcla ROIs incompatibles → giro de intersección errado [P1] 🆕 (sobre #110)

**Ubicación:** `Main.py:759-789` (bloque de decisión de verde dentro de `while estado == 'linea'`).

**Qué pasa.** El issue #110 (R-V08) ya cubre que `cx_black` (L770) puede quedar **sin inicializar** y crashear en L778/L780. Eso es correcto y hay que aplicarlo. Pero **aun con el init puesto**, la *decisión* que se construye con esas variables está mal armada porque combina centroides calculados sobre **regiones de imagen distintas**:

- `cx_black` (L770) = momento horizontal de `black_mask[90:, :]` → solo las filas **90 a 120** (tercio inferior), en coordenadas **absolutas del frame** (0..160).
- `greenCentroidX` (L765) = `(rightIndex + leftIndex) / 2` → calculado sobre `green_pixels = np.amax(green_mask, axis=0)` que recorre **todas** las columnas; `green_mask` solo está poblado en `[90:, :]` (L742), así que `leftIndex/rightIndex` son columnas absolutas del verde inferior. OK, coherente con `cx_black`.
- **Pero** `slicedBlackMaskAboveGreen = black_mask[60:90, left:right]` (L766) mide el negro en la franja **60-90** (por encima del verde), y el gate de "esto es una intersección con verde" (L772) usa esa franja. Es decir: la *detección* de la marca usa la franja 60-90, mientras que la *decisión de hacia dónde girar* (L780, `greenCentroidX < cx_black`) compara el centro del verde contra el negro de la franja **90-120**.

El resultado: el robot decide girar a izquierda/derecha comparando el verde con la línea negra **que tiene justo debajo de la cámara** (90-120), no con la línea por la que va a salir de la intersección (que está arriba, 60-90). En una `T` o cruce con dos marcas verdes, esto produce **giros invertidos intermitentes** según dónde caiga la basecaja de la línea inferior.

Además, el criterio de "doble verde → seguir derecho" (L778, `green_state=3`) exige `len(green_contours) > 1` **y** `cx_black > leftIndex and cx_black < rightIndex`. Como `cx_black` es la línea inferior (no la de salida), el robot puede ver dos verdes legítimos y **no** clasificarlos como doble-verde porque la base de la línea quedó fuera del `[left,right]` del verde superior.

**Por qué importa (Incheon).** El verde en RCJ Rescue Line vale puntos por cada intersección tomada bien y penaliza fuerte cada giro errado (se sale de pista → lack-of-progress → re-spawn). Un giro invertido intermitente es exactamente el tipo de error que cuesta podio.

**Fix sugerido (a validar en banco, NO aplicado):**
1. Aplicar primero el init de #110: `cx_black = width // 2` antes del bloque (L753 aprox).
2. Unificar el ROI de decisión: comparar `greenCentroidX` contra el centroide de la línea **en la misma franja** donde se evalúa la salida (60-90), o documentar explícitamente por qué se usa la base. Ejemplo mínimo: calcular `cx_black_salida` sobre `black_mask[60:90, :]` y usar ese para L780.
3. Loguear ambos centroides + `green_state` resultante para revisar en video.

- **Riesgo de NO fixear:** giros de intersección invertidos intermitentes → salidas de pista en cruces con verde. Pérdida directa de puntaje y de tiempo de corrida. Es el bug "silencioso" más caro de esta capa.
- **Riesgo de fixear:** ALTO de regresión. Los alumnos calibraron estos umbrales (0.32 en L772, 1.35 en L778) **a mano** contra su pista. Cambiar el ROIde `cx_black` cambia el punto de operación de TODA la lógica de verde. **No tocar sin una tarde de banco con pista de cruces reales y video lado a lado.** Si rompe lo validado, se revierte (regla de oro #4).
- **Tiempo:** fix 30–45 min; **validación 2–3 h en banco con pista de intersecciones** (lo caro es la validación, no el cambio).

---

### D2 · La inversión de clases YOLO (#120/B3) propaga a `select_target_from_list` y a los filtros de estado [P0] 🆕 (extiende #120)

**Ubicación:** `Main.py:491-497` (filtros por estado en `infer_thread`), `Main.py:505-518` (`select_target_from_list`), `Main.py:624-634` (mapeo `ball_type`).

**Qué pasa.** #120/B3 documenta que en L624-631 el mapeo está invertido: el código asume `cls==0→silver`, `cls==1→black`, pero por `CLASS_NAMES = ['negro','plateado','rojo alto','verde_alto']` (L312) la realidad es `cls==0→negro(muerta)`, `cls==1→plateado(viva)`. El issue lo trata como "la pinza no separa vivos/muertos (−75 pts)". **Es más amplio que eso**: la misma confusión 0↔1 está cableada en **tres lugares más** de la capa de decisión, y todos hay que arreglarlos **coherentemente y a la vez** o se introduce un bug peor:

1. **Filtro de estado en `rescate` (L491-492):** `if cls_id in (2,3): continue` → descarta rojo y verde durante rescate. OK (en rescate solo importan pelotas). Este está bien.
2. **Filtro de estado en `depositar` (L493-494):** `if cls_id in (0,1,2): continue` → en `depositar` descarta **negro, plateado y rojo**, deja pasar solo verde (cls 3). Coherente con depositar-en-zona-verde.
3. **`select_target_from_list` (L507-515):** en `rescate` toma `cls in (0,1)` (ambas pelotas) — acá **no** depende del signo, toma las dos. PERO el `ball_type` posterior (L624) sí asigna mal silver/black, y de ahí sale el `green_state` (6 vs 7, L629-630) que le dice a la Teensy **qué pinza/secuencia** ejecutar. Esa es la cadena que pierde los 75 pts.

**El matiz nuevo y peligroso:** si alguien "arregla" B3 tocando **solo** L624-631 (que es lo que sugiere el texto del issue), el `green_state` queda corregido pero `select_target_from_list` sigue devolviendo `targets[0]` sin distinguir clase (ver D5), y los thresholds por clase `CLASS_THRESH` (L325-330) siguen asignando 0.45 a ambas. Hay que verificar que el **mapeo único** (qué número es viva, qué número es muerta) esté en **una sola constante** y se use en los 4 puntos. Hoy está duplicado y desincronizado.

**Fix sugerido:** definir un único dict `BALL_LIVE_CLS = 1` / `BALL_DEAD_CLS = 0` (confirmado por `CLASS_NAMES`) y derivar de ahí L624-631, L491-496 y L507-515. **Confirmar el orden real de clases del `.tflite`** (depende de #124/B7: si el tensor sale transpuesto, el `argmax`/`round` de L486 ya da clases basura y este fix es prematuro).

- **Riesgo de NO fixear:** la pinza deposita la viva donde va la muerta y viceversa → −75 pts de rescate, que es la mitad del valor de la zona. Es P0 de puntaje.
- **Riesgo de fixear:** MEDIO. Si se corrige el signo pero el `.tflite` resultó tener otro orden de clases (B7 sin verificar), se "des-arregla". Por eso **B7 (#124) va PRIMERO**, luego B3, luego este D2 como verificación de que los 4 puntos quedaron coherentes.
- **Tiempo:** 20 min de código + 30 min de banco con 1 pelota viva y 1 muerta reales frente a la pinza. **Bloqueado por #124.**

---

### D3 · Búsqueda de víctimas "ciega": giro fijo 90°/derecha sin barrido ni memoria [P1] 🆕 (formaliza nota del doc de feb)

**Ubicación:** `Main.py:657-660` (rama `else` de "no hay target" en `main_loop` de rescate).

```python
else:
    speed       = 10
    angle       = 90
    green_state = 0
```

**Qué pasa.** Cuando `choose_stable_target` no devuelve nada (no hay pelota en el frame), el robot **gira siempre a la derecha a 90°** a velocidad 10, indefinidamente. El doc `analisis-raspberry-pi.md` (feb-2026) ya marcó esto como "ALTO: Lógica de Búsqueda de Objetos … girará sin sentido". **No hay issue abierto específico** para la versión de rescate (el #123/B6 es el lado Teensy de salida del cuarto). Lo formalizo acá.

Problemas concretos de esta búsqueda:

1. **Sesgo de mano fijo.** Siempre derecha. Si la víctima quedó a la izquierda del cono de visión inicial, el robot puede tardar una vuelta entera (o no encontrarla si entra en bucle límite con una pared).
2. **Sin barrido sistemático.** No hay patrón de cobertura del cuarto (espiral, zig-zag, o "girar N grados → avanzar → girar"). Gira en el lugar (avanza a 10 pero con angle=90 ≈ giro cerrado), así que cubre poca área nueva.
3. **Sin memoria de víctimas ya vistas/depositadas.** El `CentroidTracker` (L342-430) mantiene IDs **solo mientras el objeto está (o estuvo hace ≤8 frames) en cuadro** (`max_lost=8`). No hay memoria persistente de "ya deposité 2 pelotas, faltan N" ni de zonas barridas. La decisión de cuándo dejar de buscar la toma **solo la Teensy** (B6/#123, `veces_deposit`), y la RPi no le aporta ninguna evidencia visual de "el cuarto está vacío".
4. **`green_state=0` durante la búsqueda** → la Teensy no distingue "buscando" de "siguiendo línea normal". Es un comando ambiguo.

**Fix sugerido (incremental, validar en banco):**
- **Quick-win (P1, barato):** alternar el sentido de giro y meter una fase de avance. Máquina mínima de búsqueda con `time.monotonic()`: girar a un lado T1 ms → avanzar T2 ms → girar al otro lado → … Cubre más área sin barrido "real".
- **Mejora (oportunidad, ver #128 "barrido sistemático del cuarto 40-60 pts"):** patrón de barrido determinista referido a la pared de entrada (plateada) usando el yaw que ya reporta la IMU vía Teensy. Esto es la oportunidad de mayor puntaje de toda la capa de decisión.
- **Memoria:** contador de depósitos en la RPi sincronizado con los `green_state` 6/7/8/9 que ya emite, para decidir "ya hice 3, busco la zona de salida" en vez de delegar 100% a `veces_deposit` de la Teensy.

- **Riesgo de NO fixear:** en un cuarto donde la víctima no cae en el cono inicial, el robot puede no encontrarla → 0 pts de esa pelota, o consumir todo el tiempo de corrida girando. El objetivo del equipo (auto-recuperación 8/10) es incompatible con búsqueda ciega.
- **Riesgo de fixear:** BAJO-MEDIO para el quick-win (es lógica nueva aislada, no toca lo validado). ALTO si se mete barrido con IMU sin banco (depende de que el yaw de la Teensy funcione — ojo B4/#120 `leer_yaw()` no asigna la global; si eso no está arreglado, el barrido con IMU navega a ciegas).
- **Tiempo:** quick-win 1-2 h; barrido con IMU 1-2 días (oportunidad post-quick-wins, triage en #128). **El barrido con IMU está bloqueado por B4 (#120).**

---

### D4 · La FSM `depositar` / `depositar verde` es un sub-estado frágil sin retorno ni branch propio [P1] 🆕

**Ubicación:** `while True` principal (L711-845); `modo_rescate()` (L290-705); `serial_monitor_local` (L539-555); `handle_control_byte` (L150-177).

**Qué pasa.** Hay tres problemas de control de flujo encadenados:

**(a) No hay `while estado == 'depositar'` en el bucle principal.** Los únicos branches son `esperando` (L713), `rescate` (L720), `linea` (L724). `depositar` y `depositar verde` **solo existen como condición leída dentro de `modo_rescate()`** (L491-496, L507-518, L615). El sistema "funciona" únicamente porque:
- `estado` pasa a `'depositar'` (L173 en `handle_control_byte`) cuando llega RESCATE_DONE (0xF8) **estando en `rescate`**, y
- `modo_rescate()` **no** mira `estado` en su `while True` interno (L568) — corre hasta que `stop_rescate` se active.

Si por cualquier razón `modo_rescate()` retornara con `estado == 'depositar'` (hoy solo retorna por boot/stop que fuerzan `esperando`, L547-549 → L161-162), el `while True` exterior **no tiene ningún branch que matchee `'depositar'`** → cae al final del while y vuelve a empezar, evaluando `while estado=='esperando'`(falso), `=='rescate'`(falso), `=='linea'`(falso) → **busy-loop a 100% CPU sin enviar comandos al Teensy** hasta que llegue un byte de serial. Es un deadlock blando latente.

**(b) `serial_monitor_local` recibe RESCATE_DONE pero no actúa.** L551-552: cuando `handle_control_byte` devuelve `'depositar'`, el monitor **solo imprime** `"Llego 248 -> terminar rescate y cambiar a depositar"` y **no setea `stop_rescate`**. O sea: el cambio a `depositar` lo hace `handle_control_byte` (cambia la global `estado`), pero `modo_rescate` **no termina** — sigue en el mismo `main_loop`, ahora con los filtros YOLO en modo "depositar". Esto es probablemente intencional (depositar es una continuación de rescate, no un modo nuevo), pero el comentario y el nombre del estado sugieren lo contrario. **Es código que nadie entiende del todo** → riesgo de que un cambio futuro lo rompa.

**(c) `depositar` ciega el YOLO a TODAS las víctimas.** En cuanto `estado=='depositar'`, el filtro L493-494 descarta `cls in (0,1,2)` → **el robot deja de ver pelotas (vivas y muertas)**. Si la Teensy manda RESCATE_DONE **antes de tiempo** (falsa esquina, que es justo el escenario de B6/#123), la RPi entra en `depositar`, busca **solo zona verde** (`select_target_from_list` L510-512, cls 3), y **ya no puede re-detectar víctimas** porque las clases 0/1 están suprimidas. Resultado: si quedaban pelotas en el cuarto, la RPi es **ciega** a ellas hasta que el estado vuelva a `rescate`, cosa que **no ocurre** (no hay transición `depositar → rescate` en ningún lado). Esto es exactamente el bug "estado depositar que ciega el YOLO" del brief.

**(d) `depositar verde` no tiene retorno.** Tras depositar en verde (`green_state=9`, L633, `estado="depositar verde"` L634), `close_enough` usa `STOP_WIDTH_RATIO_BOX=0.98` (L321/616) → el robot se frena pegado a la zona, `is_stopped=True`, y **no hay ninguna transición de salida**. Queda enviando `speed=0/angle=0` mirando la pared verde hasta que la Teensy mande boot/stop. No vuelve a línea ni reanuda búsqueda.

**Fix sugerido (explicitar la FSM, validar en banco):**
1. Decidir y **documentar** si `depositar` es un sub-estado de rescate (entonces renombrar a algo como `rescate_subestado` o usar una variable separada `fase_rescate`) o un estado top-level (entonces agregar `while estado == 'depositar'` y mover la lógica). Hoy es ambiguo.
2. Si la Teensy puede mandar RESCATE_DONE en falso (B6), **NO** suprimir cls 0/1 en `depositar` de forma irreversible: o mantener detección de víctimas activa, o agregar una transición `depositar → rescate` cuando reaparezca una pelota con score alto.
3. Agregar transición de salida de `depositar verde` (volver a `linea` o a búsqueda) tras confirmar depósito (multi-frame), en vez de quedar frenado para siempre.
4. Blindar el `while True` exterior con un `else`/branch de seguridad para que ningún valor de `estado` deje el robot en busy-loop sin comandos.

- **Riesgo de NO fixear:** (c) y (d) son pérdidas de puntaje concretas (víctimas restantes no detectadas; robot que se queda clavado en la zona verde sin volver a operar). (a) es un deadlock blando latente que puede aparecer si se toca el flujo. En conjunto, esta es la **deuda estructural más importante** de la capa de decisión.
- **Riesgo de fixear:** ALTO. Tocar la FSM de rescate/depósito es tocar el corazón del comportamiento validado en banco. **No se hace en caliente.** Requiere rediseño consensuado con Enzo + Lucio + Benjamin y validación completa de una corrida de rescate end-to-end. Si rompe el flujo actual que (parcialmente) funciona, se revierte.
- **Tiempo:** análisis + rediseño 1 día; validación end-to-end de rescate 1 día. Candidato a **sesión de diseño dedicada**, no a quick-win.

---

### D5 · `select_target_from_list` devuelve `targets[0]` sin ponderar score, tamaño ni cercanía [P1]

**Ubicación:** `Main.py:505-518`.

```python
def select_target_from_list(boxes, estado):
    targets = []
    if estado == 'rescate':
        for d in boxes:
            if d['cls'] in (0, 1): targets.append(d)
    ...
    if not targets:
        return None
    return targets[0]   # <-- el primero de la lista, en orden de detección
```

**Qué pasa.** Cuando **no** hay `last_target` (primer frame de rescate, o tras perder el objetivo), `choose_stable_target` cae a `select_target_from_list` (L523-524), que devuelve **el primer elemento del array de detecciones** — un orden **arbitrario** que depende del orden en que el tensor TFLite escupe las cajas (post-`CentroidTracker`, el orden es el de `self.objects` dict, es decir orden de registro). No se elige la pelota **más cercana**, ni la de **mayor score**, ni la **más centrada**, ni la **más grande** (más cerca de la pinza). El robot persigue "la que tocó salir primera", que puede ser una pelota lejana o de bajo score mientras tiene una mejor pegada a la pinza.

Una vez fijado un `last_target`, `choose_stable_target` (L520-536) sí persigue por **cercanía al target anterior** (`math.hypot`), lo cual da continuidad — pero arrastra la mala elección inicial y, peor, **no re-evalúa** si apareció una pelota mucho mejor (más cerca/centrada). Si el primer target elegido fue malo, el tracking lo mantiene malo.

**Fix sugerido:** ordenar `targets` por un score compuesto antes de devolver: priorizar mayor `bbox_w` (proxy de cercanía/“lista para pinza”), luego menor `|error_x|` (centrada), luego mayor `score`. Ejemplo:
`targets.sort(key=lambda d: (-(d['xyxy'][2]-d['xyxy'][0]), abs(((d['xyxy'][0]+d['xyxy'][2])//2) - frame_w//2)))` y devolver `targets[0]`. Y en `choose_stable_target`, permitir "robar" el target si aparece otro con score compuesto sustancialmente mejor (histéresis para no oscilar).

- **Riesgo de NO fixear:** el robot persigue pelotas sub-óptimas → más tiempo por víctima, más maniobras, riesgo de empujar una pelota fuera o agotar el tiempo. Pérdida de eficiencia, no de corrección absoluta.
- **Riesgo de fixear:** BAJO-MEDIO. Es lógica de selección aislada; no toca umbrales de visión. El único riesgo es oscilación de target si no se mete histéresis (por eso la histéresis es parte del fix).
- **Tiempo:** 30-45 min código + 1 h banco con 2-3 pelotas en cuadro. Oportunidad de buen ROI.

---

### D6 · Steer en rescate es proporcional puro (P), sin término derivativo → sobre-oscila cerca de la pinza [P2] (oportunidad PD)

**Ubicación:** `Main.py:636-647` (rescate) y `Main.py:756` (línea).

**Qué pasa.** El cálculo de ángulo es **P puro** en ambos modos:
- Rescate: `angle = int(-error_norm * 90)` (L637, L645). `error_norm = error_x / (frame_w//2)` (L608).
- Línea: `angle = atan2(y_resultant, x_resultant)/pi*180 - 90` (L756) — centro de masa, también sin término temporal.

No hay derivativo. La variable global `last_angles = []` (L76) **está declarada pero nunca se usa** (confirmado: solo aparece en L76; ninguna escritura/lectura posterior) — evidencia de que en algún momento se pensó un filtro/derivada sobre el ángulo y quedó muerto. Con P puro, al acercarse a la pelota el `bbox` crece y el `error_x` se vuelve sensible (la pelota ocupa medio frame); el robot **sobre-oscila** izquierda-derecha justo cuando más precisión necesita para encarar la pinza.

**Fix sugerido (oportunidad, ver #128 "PID real + rampa"):** agregar término D sobre `error_norm`: guardar `prev_error`, `d_error = error_norm - prev_error`, `angle = int(-(Kp*error_norm + Kd*d_error)*90)`. Usar `last_angles` (ya existe) como buffer para suavizar. Empezar con `Kd` chico y tunear en banco. Idéntico para línea.

- **Riesgo de NO fixear:** oscilación al encarar la pelota → cierres de pinza fallidos, más reintentos. Degrada la métrica de captura, no la rompe. Es P2 (oportunidad).
- **Riesgo de fixear:** MEDIO. Un PD mal sintonizado **empeora** la estabilidad (un D muy alto amplifica ruido del centroide YOLO, que es ruidoso por naturaleza). **Requiere tuning en banco**, no se mete a ojo. Si no mejora medible, se revierte.
- **Tiempo:** 1 h código + 2-3 h tuning en banco. Vale la pena solo si hay tiempo de banco disponible antes de Incheon.

---

### D7 · `CentroidTracker`: asociación O(n²) por fuerza bruta sin umbral de distancia máxima [P2]

**Ubicación:** `Main.py:342-430`.

**Qué pasa.** El `CentroidTracker` asocia detecciones a objetos existentes ordenando **todos** los pares `(obj, det)` por distancia² y haciendo greedy (L404-410). Dos observaciones de decisión:

1. **Sin `max_distance`:** un objeto y una detección se asocian **por más lejos que estén** (L408-410 solo chequea que ni `i` ni `j` estén ya tomados, nunca compara contra un umbral). Si una pelota desaparece y aparece otra en la esquina opuesta del frame, el tracker **reusa el mismo ID** y `choose_stable_target` (que sigue por cercanía al último centroide) puede **saltar** de una pelota a otra creyendo que es la misma. Para 1-2 pelotas es tolerable; con varias o con detecciones fantasma (sin NMS, ver #124/B7) puede teletransportar el target.
2. **`max_lost=8` fijo** (L343/565): a ~7-10 FPS efectivos en rescate (DETECT_EVERY=3), 8 frames perdidos ≈ 1 s de "memoria". Razonable, pero acoplado al FPS real; si el FPS cae, la memoria temporal se acorta sin que nadie lo note.

**Fix sugerido:** agregar `MAX_ASSOC_DIST` (p.ej. 40 px en frame 160 de ancho escalado) y en el greedy descartar pares con `dist² > MAX_ASSOC_DIST²` (no asociar, registrar como objeto nuevo). Documentar que `max_lost` está en frames, no en tiempo.

- **Riesgo de NO fixear:** salto de identidad entre pelotas en escenas con 2+ víctimas o con detecciones espurias → el robot cambia de objetivo de golpe. Intermitente, depende de cuántas pelotas haya en cuadro. P2.
- **Riesgo de fixear:** BAJO. Es un umbral nuevo aislado. Único riesgo: poner `MAX_ASSOC_DIST` demasiado chico y fragmentar IDs de una pelota que se mueve rápido en cuadro (se mitiga calibrando contra video).
- **Tiempo:** 30 min código + 30 min banco. Depende un poco de #124/B7 (si hay NMS, hay menos fantasmas y esto urge menos).

---

### D8 · `cy` se calcula pero el centrado ignora el eje vertical; la pelota puede estar centrada en X y arriba del frame [P2]

**Ubicación:** `Main.py:603, 607-609`.

**Qué pasa.** En rescate se computa `cy = (y1+y2)//2` (L603) pero la decisión de "centrado" (L609, `centered = abs(error_x) < CENTER_TOLERANCE_PX`) y de "cerca" (`width_ratio`) **solo usan X y ancho**. `cy` solo se usa para dibujar el círculo de debug (L652). Una pelota puede estar perfectamente centrada en X y con buen `width_ratio` pero **alta en el frame** (lejos en perspectiva, o es un reflejo/falso positivo en el horizonte) y el robot la trata como "lista para pinza". Sin fusión con ToF (oportunidad ya en `analisis-raspberry-pi.md` punto 2 y AUDIT-ACTION-PLAN), el único criterio de "tengo la pelota" es el ancho del bbox, que es engañable por una pelota grande lejana o un falso positivo.

**Fix sugerido:** condicionar `close_enough` también a que `cy` esté en el tercio inferior del frame (la pelota debe estar "abajo", cerca de la pinza), no solo a `width_ratio`. Idealmente, confirmar con ToF de la Teensy antes de cerrar pinza (esto ya es oportunidad conocida; lo cito).

- **Riesgo de NO fixear:** cierres de pinza en falso sobre pelotas lejanas o falsos positivos altos en el frame. Desperdicia un ciclo de pinza. P2.
- **Riesgo de fixear:** BAJO. Agregar una condición sobre `cy` es local. Riesgo de rechazar capturas válidas si el umbral vertical es muy estricto (calibrar).
- **Tiempo:** 20 min + 30 min banco.

---

### D9 · `green_state` de rescate emite valores (6–9) en un canal que el contrato declara 0..17, pero línea emite 0,1,2,3,10 — sin enum compartido [P2]

**Ubicación:** contrato L16-29; emisión rescate L629-634; emisión línea L779-812.

**Qué pasa.** El campo `green_state` (3er payload del frame) es un **multiplexor de comandos** que mezcla semánticas:
- En `linea`: 0 (nada), 1 (verde izq), 2 (verde der), 3 (doble verde), 10 (rojo/fin) — L779-812.
- En `rescate`/`depositar`: 6 (depositar silver), 7 (depositar black), 8 (zona roja), 9 (zona verde) — L629-633.

El contrato (L21) dice `green_state: 0..17` pero **no hay un enum único** que documente qué significa cada número, y los dos productores (línea y rescate) viven en archivos lejanos del mismo file sin tabla común. El Teensy es quien interpreta estos números; un desajuste RPi↔Teensy en el significado de, p.ej., `7` (¿depositar negro? ¿otra cosa?) es un bug silencioso de protocolo que no se detecta hasta el banco. Este es el **acoplamiento de decisión más sutil** del sistema y no está auto-documentado.

**Fix sugerido:** definir un `Enum`/constantes con nombre (`GREEN_NONE=0, GREEN_LEFT=1, ... DEPOSIT_SILVER=6, ...`) compartido conceptualmente con el `switch`/`case` del Teensy (`main.cpp`), y una tabla en el comentario de contrato (L16-29). No cambia comportamiento, blinda contra desincronización futura.

- **Riesgo de NO fixear:** ninguno inmediato si hoy RPi y Teensy coinciden. El riesgo es a futuro: cualquier cambio de un lado sin el otro produce un comando mal interpretado, dificilísimo de debuggear en competencia. Deuda de mantenibilidad. P2.
- **Riesgo de fixear:** MUY BAJO (constantes con nombre, sin cambio de valores). Solo hay que verificar que los números actuales coinciden con el `case` del Teensy **antes** de renombrar.
- **Tiempo:** 1 h (incluye cotejar contra el `switch` del Teensy). Es la clase de limpieza que conviene hacer junto con el comms-auditor.

---

### D10 · `green_state` puede pisarse: rojo (10) sobrescribe la decisión de verde en el mismo frame [P2]

**Ubicación:** `Main.py:753-812`.

**Qué pasa.** En el loop de línea, `green_state` se calcula primero por verde (L759-789, puede quedar 1/2/3) y **después** se evalúa rojo: si `red_line` (L811), `green_state = 10` **pisa incondicionalmente** lo que haya decidido el verde. Si en un mismo frame hay marca verde **y** rojo (transición de fin de pista que arranca justo sobre una intersección, o falso positivo rojo por reflejo — ojo que el rango rojo además está sin wrap, B9/#120), el robot **ignora el verde** y manda "fin" (10). No hay prioridad explícita ni log de la colisión. Dado que el rango rojo (L74-75) es angosto y sin wrap (B9), un falso positivo rojo es plausible, y borraría una decisión de giro válida.

**Fix sugerido:** hacer la prioridad explícita y documentada (¿rojo siempre gana? probablemente sí, pero confirmarlo) y **loguear** cuando rojo pisa un `green_state` no-cero, para detectar falsos positivos en video. Idealmente, exigir rojo persistente N frames antes de emitir 10 (multi-frame, ya es oportunidad conocida para esquinas).

- **Riesgo de NO fixear:** un falso positivo rojo en una intersección con verde manda "fin de pista" en vez de tomar el giro → el robot frena/termina donde no debe, o pierde la intersección. Intermitente y dependiente de B9. P2 (sube a P1 si B9 no se arregla y el rojo dispara seguido).
- **Riesgo de fixear:** BAJO. Es reordenar/loguear, no cambiar umbrales. 
- **Tiempo:** 20 min + observación en video. Conviene hacerlo junto con B9 (#120).

---

### D11 · `red_line` solo arma `green_state=10` pero la transición de fin/retorno no está en esta capa [P2] (referencia cruzada)

**Ubicación:** `Main.py:803-812`.

**Qué pasa.** La RPi detecta rojo y emite `green_state=10`, pero **no cambia `estado`** ni hace nada más del lado RPi: delega 100% en la Teensy la interpretación de "fin de baldosa / retorno". Esto es coherente con el reparto de responsabilidades (Teensy = control), pero significa que **toda** la lógica de fin-de-pista vive del otro lado y la RPi no tiene forma de saber si la Teensy actuó. Combinado con B9 (#120, rojo sin wrap → puede no dispararse) y con la ausencia de heartbeat (#53), la RPi puede estar mandando 10 sin que la Teensy lo reciba/actúe y **no enterarse**. Lo dejo como referencia cruzada, no como finding independiente: el fix es B9 + heartbeat, ya filados.

- **Riesgo de NO fixear:** cubierto por B9/#120 y #53. Sin acción nueva acá.
- **Riesgo de fixear / Tiempo:** N/A (referencia).

---

### D12 · `print(area)` y `print(...)` en hot-path de decisión [P2] (deuda, roza performance)

**Ubicación:** `Main.py:798` (`print(area)` por cada contorno plateado **en cada frame** del loop de línea), L113 (telemetría, OK porque throttled), varios `print` en rescate.

**Qué pasa.** L798 imprime el área de **cada contorno plateado en cada frame** sin throttle. En la práctica, escribir a stdout (sobre todo si hay una terminal SSH escuchando) puede costar ms por frame y **bajar FPS**, lo que a su vez **acorta la memoria temporal del tracker** (D7) y empeora el steer. Es deuda menor pero está en el lazo de decisión. El doc profundo (`analisis-profundo-raspberry-os-codigo.md` §3.3) ya advierte que la GUI/IO mata FPS; este `print` es la versión “oculta” de eso.

**Fix sugerido:** quitar `print(area)` (L798) o ponerlo detrás de un flag de debug throttled.

- **Riesgo de NO fixear:** unos FPS menos y logs ruidosos. P2.
- **Riesgo de fixear:** NULO. Borrar una línea de debug.
- **Tiempo:** 2 min.

---

## 3. Tabla resumen de priorización (capa de decisión)

| ID | Finding | Prio | ¿Nuevo? | Bloqueado por | Riesgo de fixear | Tiempo (fix + banco) |
| :-- | :-- | :-: | :-- | :-- | :-- | :-- |
| D1 | Decisión de verde mezcla ROIs (giro errado) | P1 | 🆕 sobre #110 | aplicar init #110 | ALTO (regresión) | 0.5h + 2-3h |
| D2 | Inversión clases YOLO propaga a 4 sitios | P0 | 🆕 extiende #120/B3 | **#124/B7** | MEDIO | 20m + 30m |
| D3 | Búsqueda de víctimas ciega (giro 90° fijo) | P1 | 🆕 | barrido: **#120/B4** | BAJO (quick-win) / ALTO (IMU) | 1-2h / 1-2d |
| D4 | FSM depositar: sub-estado frágil, ciega YOLO, sin retorno | P1 | 🆕 | — | ALTO | 1d + 1d |
| D5 | `select_target_from_list` → `targets[0]` sin ponderar | P1 | sí | — | BAJO-MEDIO | 0.5h + 1h |
| D6 | Steer P puro, sin D (`last_angles` muerto) | P2 | sí (oport.) | — | MEDIO (tuning) | 1h + 2-3h |
| D7 | CentroidTracker sin `max_distance` | P2 | sí | suaviza con #124 | BAJO | 0.5h + 0.5h |
| D8 | `cy` ignorado en criterio de "cerca" | P2 | sí | ToF (oport.) | BAJO | 20m + 30m |
| D9 | `green_state` sin enum compartido (0..17) | P2 | sí | cotejar Teensy | MUY BAJO | 1h |
| D10 | Rojo (10) pisa decisión de verde | P2 | sí | junto con #120/B9 | BAJO | 20m |
| D11 | `green_state=10` delega todo al Teensy | P2 | ref. | #120/B9 + #53 | N/A | N/A |
| D12 | `print(area)` en hot-path | P2 | sí | — | NULO | 2m |

### Orden de ataque sugerido (sin romper lo validado)
1. **Primero lo barato y aislado, ya:** D12 (2m), D5 (selección de target — buen ROI, bajo riesgo), D7 (umbral tracker), D8 (`cy`). Todos son lógica nueva que no toca umbrales de visión calibrados.
2. **Después de #124/B7:** D2 (la inversión de clases coherente en los 4 sitios). **No antes**, o se des-arregla si el tensor sale transpuesto.
3. **Quick-win de D3** (alternar sentido de búsqueda) en cuanto haya 1-2h de banco. El barrido con IMU queda para después de B4 (#120).
4. **Sesión de diseño dedicada** para D4 (rediseño de la FSM depositar) y D1 (ROI de decisión de verde). Son los dos cambios de **alto riesgo de regresión** que tocan comportamiento validado: **no se hacen en caliente**, requieren banco con pista real y video lado a lado, y se revierten si rompen (regla de oro #4).
5. **Oportunidades de tuning:** D6 (PD) y el barrido sistemático (#128), solo si queda tiempo de banco antes de Incheon.

---

## 4. Notas de validación (cómo probar cada fix en banco)

> Toda validación va con entrada en `testing/TEST_LOG.md` (regla de oro #3). Métrica de éxito explícita por test.

- **D1 (verde):** pista con 3 intersecciones (izq, der, doble). Correr 10 pasadas por cada una, anotar % de giros correctos antes/después. Video lado a lado. **Éxito:** ≥9/10 correctos por tipo, sin regresión vs. baseline actual.
- **D2 (clases):** 1 pelota viva (plateada) + 1 muerta (negra) reales frente a la cámara. Verificar en log que `green_state` emitido es 6 para viva y 7 para muerta (o el mapeo que confirme el Teensy). **Éxito:** 10/10 correcto. **Pre-requisito:** imprimir `out.shape` (B7/#124) y confirmar orden de clases.
- **D3 (búsqueda):** colocar la víctima en 4 posiciones del cuarto fuera del cono inicial (frente, izq, der, atrás). **Éxito quick-win:** encuentra la víctima en ≤20 s en ≥3/4 posiciones (vs. baseline ciego que falla en izq/atrás).
- **D4 (FSM):** corrida de rescate end-to-end: entrar por plateado → buscar → depositar 2 vivas → confirmar que tras "depositar verde" el robot **vuelve a operar** (no queda clavado). Forzar un RESCATE_DONE falso (B6) y verificar que la RPi **sigue viendo** víctimas restantes (no se ciega). **Éxito:** no queda clavado; no pierde víctimas por ceguera.
- **D5 (selección):** 3 pelotas en cuadro a distintas distancias. **Éxito:** elige consistentemente la más cercana/centrada, sin oscilar de objetivo (verificar con IDs del tracker en video).
- **D6 (PD):** medir oscilación pico-a-pico del `angle` en los últimos 30 cm de aproximación, antes/después. **Éxito:** menor overshoot y ≥ tasa de captura. Si empeora con el ruido del centroide, revertir.
- **D7/D8/D10/D12:** verificación funcional + FPS antes/después (D12). Sin regresión.

---

## 5. Cierre

La capa de decisión de `Main.py` está **funcional pero estructuralmente frágil**. Lo más urgente de puntaje es **D2** (inversión de clases, P0, bloqueado por #124/B7) y lo más urgente de robustez de corrida es **D4** (la FSM `depositar` que ciega el YOLO y no tiene retorno) y **D1** (giros de intersección potencialmente invertidos). Estos tres son los que más mueven la aguja hacia el objetivo del equipo (podio + auto-recuperación 8/10), pero **D1 y D4 son justamente los de mayor riesgo de regresión**: tocan lógica que los alumnos calibraron a mano contra su pista, así que van a **sesión de diseño + banco**, no a quick-win.

Los quick-wins de bajo riesgo y buen retorno (D5, D7, D8, D12) se pueden hacer ya sin tocar nada validado. Las oportunidades de tuning (D6 PD, barrido sistemático) solo valen la pena si hay tiempo de banco antes de Incheon.

**Recordatorio de régimen:** nada de esto se mergea sin entrada en `testing/TEST_LOG.md`, y cualquier cambio que rompa un subsistema validado se revierte (regla de oro #4). El trabajo de Laureano, Lucio y Benjamin de meses de tuning manda sobre cualquier "suena mejor".
