# PLAYBOOK — Desafío Técnico (IITA Salta 2026)

> Objetivo: el día del desafío (2:30 hs, **sin IA**, regla oficial 6.2.6) ir
> directo a la línea exacta de `main.cpp` que hay que cambiar, sin buscar.
> Las funciones ya están escritas en [`toolkit_desafios.h`](toolkit_desafios.h):
> copiás el bloque que toca y conectás con 1 línea.

---

## 0. Qué dice el reglamento (sección 6.2) — para no asustarse

- Se hace **después** de las corridas. Las reglas **no se anuncian antes**.
- Te van a pedir **reprogramar comportamiento. SIN cambios de hardware** (6.2.4).
  → Todo se resuelve con los sensores que ya tenés.
- Vale **20% del puntaje final** (0.2), normalizado contra el mejor equipo (6.1.6/6.1.7).
  → No hace falta perfección: hay que entregar algo que ande, mejor que el promedio.
- **Sin ayuda externa ni remota** (6.2.6) → por eso esto se prepara ANTES.

**Conclusión:** un desafío = agarran un comportamiento que el reglamento ya define
y le cambian la regla. Por eso casi todo es **re-mapeo en la Teensy**, no visión.

---

## 0.5 LOS DESAFÍOS OFICIALES 2024 y 2025 (analizados con imágenes)

> Los 2 ejemplos del profe **NO son inventados: son un remix de los oficiales
> 2024 + 2025.** El desafío real del miércoles también va a ser un remix de estas
> mismas mecánicas. Por eso preparamos TODAS, no solo las del profe.

### Oficial 2024 — "Contar intersecciones + paridad" (= Desafío 2 del profe)
- Contar **TODAS las intersecciones/dead ends** del camino — **incluidas las que
  NO tienen verde**. (El profe lo simplificó a "contar verdes".)
- Al ver un **obstáculo**: alejarse un poco y **rotar 360° sobre el eje**:
  - cuenta **PAR** → 360° **horario**, después pasar por la **IZQUIERDA**.
  - cuenta **IMPAR** → 360° **antihorario**, después pasar por la **DERECHA**.
- Conteo **continuo** (no se reinicia tras cada obstáculo). **Sí** se reinicia tras un LoP.
- Puntos: intersección 10, **obstáculo bien resuelto = 100 (!)**, exit bonus 50.

### Oficial 2025 — "Terremoto, señales invertidas" (= Desafío 1 del profe)
- **Verde a la derecha → girar IZQUIERDA; verde a la izquierda → girar DERECHA.**
- **Dead end (doble verde) → seguir RECTO** (no girar 180).
- **Línea roja:** la meta son **DOS líneas rojas paralelas** (80 mm de separación).
  Durante el recorrido hay líneas rojas **simples** que **NO son la meta y NO se
  paran**. Parar en una roja simple >5s = **-5 puntos**.
- **Evacuación distinta:** solo importa la **víctima VIVA (plateada)**; las negras
  no suman. Salida de la zona por una **rampa** en una esquina; **una sola** zona
  segura **verde fuera** de la zona de evacuación, se llega siguiendo la línea.
- Puntos: intersección 20, gap 10, levantar víctima viva 45, rampa 40, depositar
  viva 30, exit bonus 50.

### 🔑 ROJO: lo hacés con el SENSOR DE COLOR (la cámara es mala para rojo/plateado)
El rojo y el plateado los detectás con el **sensor de color de abajo**, que anda
mucho mejor que la cámara. Para distinguir **roja simple vs doble** (lo que pide el
2025) el sensor detecta la **secuencia** rojo→blanco→rojo mientras avanzás → ver
**Bloque I** del toolkit (`evaluarRojoSensor()`).

> Nota: tu RPi además calcula simple/doble y manda `green_state` 10/11, pero como
> preferís el sensor, no dependemos de eso.

---

## 0.6 COBERTURA PARA EL 100% — universo de mecánicas

Cada cosa que los oficiales pueden pedir, y si ya está cubierta:

| Mecánica | Fuente | Bloque toolkit | Teensy/RPi | Estado |
|---|---|---|---|---|
| Invertir verdes izq/der | 2025 | B / P1 | Teensy | ✅ listo |
| Dead end → seguir recto | 2025 | F / P2 | Teensy | ✅ listo |
| Roja simple ignorar / doble parar | 2025 | **I** (sensor color) | Teensy | ✅ listo |
| Roja = giro fijo (variante profe) | profe | C | Teensy | ✅ listo |
| Contar **verdes** + paridad | profe | A | Teensy | ✅ listo |
| Paridad → lado de esquive | 2024 | D | Teensy | ✅ listo |
| Paridad → **rotar 360°** + lado | 2024 | **J** | Teensy | ✅ listo |
| Reset de cuenta tras LoP | 2024 | **K** | Teensy | ✅ listo |
| Invertir zonas de depósito | profe | E | Teensy | ✅ listo |
| Solo rescatar víctima viva | 2025 | **K** (flag) | Teensy | ✅ listo |
| Contar **TODAS** las intersecciones (sin verde) | 2024 | **A-2** + RPi | Teensy + RPi | 🟡 listo* |
| Flujo evac 2025 (solo viva + rampa + zona externa) | 2025 | **L** | Teensy + RPi | 🟡 listo** |
| Línea otro color / reversa / víctima falsa | hipot. | — | **RPi** | 🔴 difícil |

*Para contar intersecciones sin verde, ver sección **0.7**.

**Flujo evac 2025 → **Bloque L** del toolkit. Idea: NO hace falta estado nuevo; un
flag `llevando_victima` + reusar tu `accionNegro()` (salida por cinta negra) y tu
`gs9` (zona verde). Pendiente RPi: apuntar solo a plateada en el agarre y confirmar
que el YOLO vea la zona verde desde afuera (lo más riesgoso — probar en banco).

---

## 0.7 CONTAR INTERSECCIONES LISAS (T y cruces, SIN verde) — 2024

**Realidad de tu `Main.py` HOY:** solo "ves" la intersección cuando hay verde
(`green_mask` + chequeo de negro arriba del verde, línea ~822). Una T/cruce sin
verde cae en el `else` y queda en `green_state = 0`. **No la contás.**

**El sensor de color NO sirve** (ve un punto; en una T sigue viendo negro). **Solo
la cámara**, detectando la **línea negra horizontal** de la intersección — lo mismo
que ya hacés con el rojo (`row_sum`), pero sobre negro.

**Regalo en tu código:** ya calculás `cut_line` (negro filas 62+, líneas 784-786) y
**no lo usás**. Es justo lo que necesitás.

### Lado RPi — pegar en `Main.py` después del bloque de verde, antes de `send_frame`
```python
# (una vez, arriba con las globales)   prev_intersection = False

# Linea horizontal = una fila con MUCHO negro (mismo metodo que usas para el rojo)
black_row_sum = np.sum(cut_line, axis=1)          # cut_line ya existe (negro filas 62+)
BLACK_ROW_THRESHOLD = 96 * 255                     # ~60% de 160 px en negro — TUNEAR
is_intersection = bool(np.any(black_row_sum > BLACK_ROW_THRESHOLD))

# Mandar 12 SOLO en el flanco y SOLO si no hay verde (el verde ya se cuenta solo)
if is_intersection and green_state == 0 and not prev_intersection:
    green_state = 12
prev_intersection = is_intersection
```

### Lado Teensy — usar `actualizarContadorIntersecciones()` del **Bloque A-2**
Cuenta `{1,2,3,12}` (toda intersección/dead end = +1) con **cooldown** para que el
verde y el `12` de la misma intersección no se cuenten dos veces.
> Desafío dice "contar **verdes**" (profe) → Bloque A. Dice "contar **intersecciones**"
> (oficial 2024) → snippet RPi + Bloque A-2, y la paridad la sacás con `interPar()`.

---

## 0.8 UNIFICAR "SEGUIR LÍNEA + VER LA ZONA VERDE" en la RPi — 2025

**El problema:** tu YOLO (`infer_thread`) se crea/destruye DENTRO de `modo_rescate()`.
En el estado `"linea"` no corre. Por eso no podés "seguir la línea y ver el modelo
a la vez" — son dos pipelines distintos.

**OJO (lo que descarta la máscara como opción A):** el camino a la zona segura pasa
por intersecciones con **cuadrados verdes** (marcadores). Detectar la zona por
`green_mask` puede confundir un marcador con la zona. YOLO no tiene ese problema:
la zona es una **clase entrenada (3)**, distinta de los marcadores. → **Usar YOLO.**

### OPCIÓN A (recomendada) — YOLO siempre prendido (productor-consumidor)
1. Sacá `capture_thread` + `infer_thread` + las colas a **scope global**, arrancados
   UNA vez al inicio (no dentro de `modo_rescate`).
2. En el estado de línea, leé el último resultado **sin bloquear**:
```python
try:
    item = result_q.get_nowait()      # NO espera; agarra lo más fresco
    # si item trae detección class 3 (green_zone) y carrying_victim: green_state = 9
except queue.Empty:
    pass
```
**No te baja los FPS de línea:** el seguidor corre cada frame (nunca espera a YOLO);
YOLO corre en su hilo a su ritmo; TFLite libera el GIL en `invoke()` → se solapan en
cores distintos. Costo = contención de CPU (testear), no bloqueo. En depósito vas
lento, alcanza con pocos fps de YOLO.

### OPCIÓN B (plan B) — zona verde por área de `green_mask`
Solo si la Pi sufre FPS. Riesgo: confundir con marcadores → subir el umbral fuerte.
```python
ZONA_VERDE_FACTOR = 8     # la zona es MUCHO más grande que un marcador — TUNEAR
if carrying_victim and np.sum(green_mask) > ZONA_VERDE_FACTOR * min_square_size * 255:
    green_state = 9
```

**Coordinación con la Teensy (código serial nuevo `246`), igual en A o B:**
```
Teensy agarra plateada → busca rampa → accionNegro() ve cinta negra
    → rutina="linea" + manda 246 (en vez de 249)
RPi recibe 246 → carrying_victim = True (sigue en línea, pero mira la zona verde)
RPi ve la zona verde → green_state = 9
Teensy (llevando_victima && gs9) → deposita → manda 249 (línea normal a la meta)
```

---

## 0.9 YOLO para la zona verde + solo plateada — 2025

> ✅ **YA IMPLEMENTADO** en [`Main_challenge.py`](../../../../raspberry/final_rpi/Main_challenge.py)
> (copia de `Main.py`). Se eligió la **variante SINCRÓNICA** (no la de hilos global):
> corre YOLO **solo cuando cargás la víctima**, en el estado de línea, cada N frames.
> Razón: es más seguro (tu `modo_rescate` probado queda intacto) y **más rápido**
> (la versión "siempre prendida" infiere durante TODA la corrida y te baja los FPS
> del seguidor de línea por contención de CPU). Como en línea-cargando `modo_rescate`
> ya terminó, el interpreter está libre → sin conflicto de hilos.

Cambios aplicados (todos marcados `CHALLENGE 2025`):
- Código serial `246` (`TEENSY_LINEA_VICTIMA`) + flag `carrying_victim`.
- `handle_control_byte`: 246 → `estado='linea'` + `carrying_victim=True` (y reset en stop/boot).
- `select_target_from_list` (rescate): apunta SOLO a `SILVER_CLS` (víctima viva).
- `hay_zona_verde()`: inferencia sincrónica que devuelve True si ve la zona (cls 3).
- Estado de línea: si `carrying_victim`, corre `hay_zona_verde` cada `YOLO_LINEA_EVERY`
  frames → `green_state = 9` (la Teensy deposita, Bloque L).

**A confirmar en banco:** `SILVER_CLS` (0 vs 1 — tu código se contradice) y tunear
`YOLO_LINEA_EVERY`. La versión de hilos siempre-on queda abajo como alternativa.

> ⚠️ **Clases contradictorias en tu código:** línea 324 `CLASS_NAMES` dice 0=negro,
> 1=plateado; pero la línea 658 (la que YA te funciona) usa **0=silver, 1=black**.
> Funcionalmente **0 = plateada, 3 = verde**. Confirmalo viendo detecciones.

### A) "Solo plateada y verde" — tu mismo patrón (2 líneas)
En `infer_thread`, donde ya filtrás por `estado` (~505-513), agregá:
```python
SILVER_CLS, GREEN_CLS = 0, 3       # 0=plateada (CONFIRMAR), 3=verde
if cls_id not in (SILVER_CLS, GREEN_CLS):
    continue                        # descarta negra (cls 1) y rojo (cls 2)
```

### B) "Siempre prendido" — sacar los hilos de modo_rescate (1 vez, no se apagan)
Hoy `capture_thread`+`infer_thread` nacen/mueren dentro de `modo_rescate` (por eso
el "FIX ZOMBI", línea 729). Global:
1. Mové `frame_q, result_q, stop_event, capture_thread, infer_thread` a scope de
   módulo, después de armar el `interpreter` (~línea 300).
2. En `infer_thread`, cambiá `evac_mode` por `estado == 'evacuacion'` (ya es global).
3. Arrancá los hilos UNA vez, antes del `while True` de `main()`:
   ```python
   threading.Thread(target=capture_thread, daemon=True).start()
   threading.Thread(target=infer_thread,  daemon=True).start()
   ```
4. En `modo_rescate` borrá el arranque (719-721) y el teardown de hilos (725-740);
   ahora solo consume `result_q`. **Bonus: se acaba el problema de hilos zombi.**

### C) Verlo en el estado de línea (cuando cargás víctima), sin bloquear
En el `while estado == 'linea'`, antes de `send_frame`, agregá:
```python
try:
    item = result_q.get_nowait()
    if carrying_victim and item and item[0] == 'det':
        if any(d['cls'] == GREEN_CLS for d in item[2]):
            green_state = 9          # zona verde a la vista
except queue.Empty:
    pass
```

### Seguridad — NO rompe tu seguidor de línea
`vs.read()` tiene lock (camthreader) → `capture_thread` y el estado de línea leen
frames a la vez sin problema. La visión por CPU de la línea queda intacta.

---

## 1. MAPA DE PERILLAS — dónde vive cada comportamiento en `main.cpp`

Buscá el texto del "ancla" con Ctrl+F (los números de línea se mueven al editar).

| # | Comportamiento | Ancla (Ctrl+F) | Línea aprox. | Dificultad |
|---|---|---|---|---|
| P1 | Verde izq/der → giro | `case 6:` / `case 5:` | 1794 / 1802 | 🟢 |
| P2 | Doble verde → 180° | `if (green_state == 3)` (mapeo) | 1659 | 🟢 |
| P3 | Línea roja → parar | `if (color_detected == "Rojo")` | 1636 | 🟢 |
| P4 | Obstáculo → lado de esquive | `RanNumber = random(1, 3);` | 1688 | 🟢 |
| P5 | Detección de obstáculo | `front_distance != 0 && front_distance < 12` | 1663 | 🟢 |
| P6 | Mapeo verde → acción | `if (green_state == 1)` | 1651 | 🟢 |
| P7 | Seguidor de línea (velocidad) | `case 7: // linetrack` | 1810 | 🟢 |
| P8 | Depósito víctima viva (verde) | `if(green_state == 9)//verde` | 1958 | 🟡 |
| P9 | Depósito víctima muerta (rojo) | `if (green_state == 8)//rojo` | 1978 | 🟡 |
| P10 | Inicio rescate (ve plateado) | `color_detected == "Plateado"` | 1626 | 🟡 |
| C1 | Conteo de verdes (insertar) | `leer_ultrasonidos();` (en while linea) | 1624 | 🟡 |

---

## 2. RECETA — Desafío 1 del profe (3 cambios)

### 1.1 — Invertir verdes (izq gira der y viceversa)
**Perilla P1.** La forma más rápida: cambiar el signo del giro.
- `case 6:` (verde izq) → `runAngle(35, FORWARD, -60);`  **cambiá `-60` por `60`**
- `case 5:` (verde der) → `runAngle(25, FORWARD, 60);`   **cambiá `60` por `-60`**

(Alternativa con 1 sola perilla: usar `anguloVerde()` del Bloque B con `INVERTIR_VERDES true`.)

### 1.2 — Doble verde: pasar de largo / ignorar
**Perilla P2.** En el mapeo (línea ~1659). En tu código son 4 líneas; **el cambio
real es UN token**: en el cuerpo del `if (green_state == 3)` cambiás `action = 14;`
por `action = 7;` (14 = gira 180 → 7 = sigue recto). Nada más.

### 1.3 — Línea roja = giro 180°
**Perilla P3.** Reemplazá el bloque del rojo:
```cpp
if (color_detected == "Rojo") {
    runTime(0, FORWARD, 0, 10000);   // ANTES: parar
    break;
}
```
por (copiá `accionRojo_giro180()` del Bloque C):
```cpp
if (color_detected == "Rojo") {
    accionRojo_giro180();
    break;
}
```

---

## 3. RECETA — Desafío 2 del profe (contar + paridad)

**Paso 0:** copiá el **Bloque A** completo (contador) del toolkit a main.cpp, arriba de `loop()`.

### 2.1 — Contar verdes (izq, der y dobles)
**Perilla C1.** Dentro del `while (rutina == "linea" ...)`, después de `leer_ultrasonidos();`:
```cpp
actualizarContadorVerdes();
```
> Decidir con el árbitro si un **doble cuenta 2 o 1** → `#define DOBLE_CUENTA_COMO`.

### 2.2 — Esquivar par=izquierda / impar=derecha
**Perilla P4.** En `case 1`, reemplazá las dos líneas del random:
```cpp
RanNumber = random(3);
RanNumber = random(1, 3);
```
por (Bloque D):
```cpp
RanNumber = ladoEsquiveParidad();   // par->izq(1), impar->der(2)
```

### 2.3 — Invertir zonas de depósito si es impar
**Perillas P8/P9.** Copiá `trianguloEfectivo()` (Bloque E). Justo **antes** de
`if(green_state == 9)//verde`, agregá:
```cpp
int gs_dep = trianguloEfectivo(green_state, verdesImpar());
```
y cambiá las dos condiciones:
```cpp
if (gs_dep == 9) { ... }   // antes: if(green_state == 9)
if (gs_dep == 8) { ... }   // antes: if (green_state == 8)
```
> Ojo: NO toques los `green_state == 6/7` de recolección. Solo el 8/9 de depósito.

---

## 3.5 RECETA — Evacuación 2025: PURO (solo viva) vs HÍBRIDO

Dos escenarios de la zona de evacuación. Ambos reusan el **Bloque L** (Teensy) y
`Main_challenge.py` (RPi). La diferencia es qué flags prendés.

### Flags en `Main_challenge.py` (RPi)
| Flag | Puro 2025 | Híbrido | Normal |
|---|---|---|---|
| `AGARRAR_SOLO_PLATEADA` | `True` | `False` | `False` |
| `DEPOSITO_ADENTRO_EN_ROJO` | `False` | `True` | `False` |
| `DETECTAR_ZONA_VERDE_LINEA` | `True` | `True` | `True`* |

*En normal no molesta: solo actúa si la Teensy manda 246 (`carrying_victim`).

### PURO 2025 — solo la plateada, se deposita afuera
- **RPi:** `AGARRAR_SOLO_PLATEADA=True`. (La negra ni entra — 3 capas de filtro alineadas.)
- **Teensy:**
  - `rescate2025()` (Bloque L): agarra la plateada → `llevando_victima=true` → exit.
  - `depositarVivaYSeguir()` con **`claw.open()`** (la víctima va agarrada en la garra).
  - Al final de `depositarVivaYSeguir()`: `Serial5.write(249);` → apaga `carrying_victim` en la RPi.

### HÍBRIDO — negras al ROJO adentro, plateada al VERDE afuera
- **RPi:** `AGARRAR_SOLO_PLATEADA=False` + `DEPOSITO_ADENTRO_EN_ROJO=True`.
  - Agarra las 3. En `"depositar"` el filtro deja solo el ROJO (cls 2) → manda gs8.
- **Teensy:**
  - Colección normal de las 3. El bloque `ball_counter >= UMBRAL` manda **248**
    (umbral = base + 3 pelotas; hoy base = 2 → umbral 5).
  - En `green_state == 8` (rojo): depositás las negras (`depositLeft`) como siempre, y
    **al final** agregás: `llevando_victima=true; Serial5.write(247); rutina="evacuacion"; break;`
  - El bloque `green_state == 9` (verde adentro) **no se usa**.
  - `depositarVivaYSeguir()` con **`claw.depositRight()`** (la plateada está en compartimento,
    no en la garra) + `Serial5.write(249);` al final.

### El lazo del depósito afuera (igual en los dos)
```
Teensy en evac -> rampa -> accionNegro(): Serial5.write(llevando_victima ? 246 : 249)
RPi recibe 246 -> carrying_victim=True -> busca zona verde (cls 3, CERCA: ZONA_VERDE_MIN_ANCHO)
RPi ve la zona -> green_state = 9
Teensy (llevando_victima && green_state==9) -> depositarVivaYSeguir()
   -> deposita, llevando_victima=false, Serial5.write(249)
RPi recibe 249 -> carrying_victim=False (deja de buscar)
```

> Filtro de clases (RPi): la lista en `if cls_id in (...): continue` es lo que
> **IGNORÁS**; lo que queda afuera es lo único que dejás. Verde=3, Rojo=2, Plateada=0, Negra=1.

---

## 4. Variaciones probables (no son los ejemplos del profe, pero entran igual)

| Si te piden... | Perilla | Cómo |
|---|---|---|
| Siempre girar a un lado fijo en intersección | P6 | Forzá `action = 5;` (o 6) fijo |
| "Sin verde = girar, con verde = recto" | P6 | Invertí el mapeo |
| Ir más lento/rápido en toda la pista | P7 | `robot.steer(vel * FACTOR_VEL, ...)` (Bloque H) |
| Detectar obstáculo más lejos/cerca | P5 | Cambiá el `< 12` |
| Contar otra cosa (intersecciones, etc.) | — | `contarPorFlanco()` (Bloque G) |
| Hacer algo en la N-ésima vez | A+G | `if (mi_contador == N) {...}` |
| Línea de otro color / reversa / víctima falsa | RPi | **Difícil** — `Main.py`, recalibrar |

---

## 5. Workflow del día (build + flash)

**Ya tenés [`main_challenge.cpp`](main_challenge.cpp)** = tu `main.cpp` con todo el
toolkit de LÍNEA pre-integrado y gateado por flags (todas en "normal" por defecto).
El miércoles:
```bash
# 1. Copiá main_challenge.cpp -> src/main.cpp
# 2. Prendé SOLO las flags que pida el desafio (arriba del archivo):
#      Desafio 1: INVERTIR_VERDES=true, MODO_DOBLE_VERDE=1, MODO_ROJO=1
#      Desafio 2: CONTAR_VERDES=true, ESQUIVE_POR_PARIDAD=true, INVERTIR_DEPOSITO=true
# 3. Compilar y flashear:
cd software/teensy/firmware
pio run                    # compila — si falla, leé el error, NO flashees
pio run --target upload    # flashea la Teensy
```
> ⚠️ ANTES del miércoles: compilá `main_challenge.cpp` con TODO en false y hacé una
> corrida normal (confirmás que la base es fiel), después probá cada flag de a UNA.
> Acá no hay compilador → la validación es en banco. El evac 2025/híbrido NO está en
> flags: eso es receta 3.5 + Bloque L (se copia aparte).

## 6. Checklist antes de decir "listo"
- [ ] Compila sin errores (`pio run` verde).
- [ ] El robot enciende y los motores responden (no watchdog reset).
- [ ] Probado en banco el comportamiento pedido al menos 2 veces.
- [ ] Confirmaste con el árbitro las dudas (ej: doble = 1 o 2 verdes).
- [ ] Guardaste copia del archivo que funcionó.

> **Regla de oro del día:** si una perilla no anda y se te acaba el tiempo,
> volvé al comportamiento anterior (tenés el ancla) antes que entregar algo roto.
