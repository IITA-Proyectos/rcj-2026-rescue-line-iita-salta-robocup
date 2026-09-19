# TRAZAR — paquete de evidencia congelado para auditoría independiente

_IITA Salta · RoboCupJunior Rescue Line 2026 · rama `roboliga` · 2026-08-23_

Este archivo es **autosuficiente**. Quien audite no necesita esta conversación.
Todos los números publicados acá se pueden reproducir de dos maneras
independientes: corriendo `trazar.py` sobre los videos, o leyendo únicamente los
once `traza_*.csv`.

**Nada de V2/V3/V4 fue modificado.** `trazar.py` los envuelve.

---

## 1. Procedencia exacta del código

| archivo | líneas | bytes | SHA-256 | en git |
|---|---:|---:|---|---|
| `nuevo_code_v2.py` | 519 | 17.778 | `a6fbdb6e3d52592c3354da2cb26debd6a5e811d7136e1347b45a77b36b4cdd80` | **no** — vive en `~/Downloads` |
| `nuevo_code_v3.py` | 687 | 19.967 | `cd2c4df04a7a6da652a972e48c7441e4876884f8c387a89e37604698f5ab162e` | **no** — vive en `~/Downloads` |
| `nuevo_code_v4.py` | 427 | 12.830 | `2d974d5fc230bd73bc3d32157e672e85355e8dda79907b1644babb50cde68a1a` | **no** — vive en `~/Downloads` |
| `software/raspberry/final_rpi/trazar.py` | 523 | 21.785 | `6ca080bb3ae98513339ca2230d598b0dc945645bcce2ed54a085005ec8149510` | sí, commit **`e90401c`** | |
| `software/raspberry/final_rpi/groundtruth_v4.py` | 498 | 21049 | `674935f3f6bec541ca25c151ae841ec7449644160d2266261e3150138d868c5b` | sí, commit **`e90401c`** |
| `software/raspberry/final_rpi/resumen_traza.py` | 150 | 5771 | `5eb3e8684588b2d8600e3b9fd510d2d484f8b98f94f2b45a400c60b1af4171f7` | sí |

- Repositorio HEAD: **`e90401c`** (`feat(rpi): ground truth retrospectivo de
  video_4, y el contador del pre-roll`). El congelado original de la traza fue
  `57e766c8a394612b1410fe48f570048687830ddd`; **los once `traza_*.csv` no
  cambiaron**, porque el único cambio de `trazar.py` fue el contador de
  autovalidación de `--casos` (§13), que no toca ninguna columna del CSV.
- **Los tres `nuevo_code_*.py` NO están versionados.** Es una deuda: la única
  procedencia que existe hoy son los SHA-256 de arriba. Si alguien los edita, el
  paquete deja de ser reproducible sin aviso.
- Dependencia externa nueva: `scikit-image` (`nuevo_code_v2.py:23`,
  `from skimage.morphology import skeletonize`).

---

## 2. Comandos exactos usados

Desde `software/raspberry/final_rpi/`, con los once AVI en esa misma carpeta y
los `nuevo_code_*.py` en `~/Downloads`:

```bash
python trazar.py --todos
```

Ése es el único comando que generó los once `traza_*.csv` publicados. Los
cuatro casos de control se corren aparte y **sus CSV no entran en los
agregados**, porque serían frames contados dos veces:

```bash
python trazar.py --casos
```

Reconstrucción de todos los agregados leyendo sólo los CSV:

```bash
python resumen_traza.py
```

Si los `nuevo_code_*.py` están en otro lado:

```bash
python trazar.py --todos --code-dir /ruta/a/la/carpeta
```

---

## 3. FPS asignado a cada video, y por qué

**Los once AVI declaran 20,0 fps en su cabecera y diez de ellos mienten.** El
`VideoWriter` del grabador tiene 20,0 fijo (`parche_planner.py:294`), mientras
el lazo de visión corría a ~33,3. Es la regla de método 4 del
`HANDOFF_LINEA_2026-08-23_FINAL.md`, y ya hizo caer una auditoría previa que
leyó `cap.get(CAP_PROP_FPS)` y concluyó que toda la validación había corrido mal.

`trazar.py:88-95` asigna el fps **por nombre de archivo, nunca leyendo la
cabecera**:

| video | frames | fps asignado | formato de entrada |
|---|---:|---:|---|
| `hist.avi` | 2091 | 33,3 | panel 640×240 |
| `lineal.avi` | 1194 | 33,3 | panel 640×240 |
| `lineal70.avi` | 1215 | 33,3 | panel 640×240 |
| `como_esta.avi` | 1498 | 33,3 | panel 640×240 |
| `seguir.avi` | 1259 | 33,3 | panel 640×240 |
| `rumbo.avi` | 1068 | 33,3 | panel 640×240 |
| `a.avi` | 751 | 33,3 | panel 640×240 |
| `roi_auto.avi` | 3221 | 33,3 | panel 640×240 |
| `con_planner.avi` | 461 | 33,3 | panel 640×240 |
| `con_planner2.avi` | 1142 | 33,3 | panel 640×240 |
| **`video_4.avi`** | 642 | **20,0** | **crudo 640×480** |

`video_4.avi` es el único crudo y el único realmente a 20 fps.
`nuevo_code_v2.py:53-57` (`frame_pi`) discrimina por forma: panel 640×240 →
`frame[:, :320][1::2, 1::2]`; cualquier otra → `ROTATE_180` + `resize(160,120)`
`INTER_NEAREST`. El submuestreo **impar** está validado en 84,0 % de
coincidencia exacta al grado contra el `rxsteer` real de la Teensy.

> **Trampa conocida, no corregida:** el default de `--fps` es 33,3 en
> `nuevo_code_v3.py:674` y `nuevo_code_v4.py:416`, pero **20,0 en
> `nuevo_code_v2.py:512`**. El stack se contradice. `trazar.py` no usa esos
> defaults: resuelve por nombre.

---

## 4. Las cinco etapas

El `.md` de V4 habla de dos guards. **Son cinco limitadores en serie**, porque
dentro de V2 hay dos consecutivos que no salen de `step()`:

```
target_raw        nuevo_code_v2.py:305        punto geodésico a LOOKAHEAD=70 sobre la centerline
   ↓
target_cap        nuevo_code_v2.py:352-364    cap de continuidad 16 / 12 / 20 px según estado
   ↓
target_lowproj    nuevo_code_v2.py:366-372    en LOW, proyección hacia last_good_target
   ↓
target_branch     nuevo_code_v3.py:196-283    guard de rama: prohíbe inversión directa de signo
   ↓
target_final      nuevo_code_v4.py:53-120     guard espacial 24 / 30 px
```

**Consecuencia que conviene tener presente al leer el `.md` de V4:** lo que
`nuevo_code_v4.py:146,156` llama `target_geometric` es la **etapa 3**, o sea que
ya pasó por dos limitadores. No es el target geométrico crudo.

Correspondencia con las columnas del CSV:

| etapa | columnas | quién la produce |
|---|---|---|
| 1 `target_raw` | `raw_x`, `raw_y` | interceptando `path_target` |
| 2 `target_cap` | `cap_x`, `cap_y`, `cap_via`, `cap_jump_px` | **reproducida** (§5) |
| 3 `target_lowproj` | `lowproj_x`, `lowproj_y` | `r["target_geometric"]` |
| 4 `target_branch` | `branch_x`, `branch_y`, `branch_guard` | `r["target_branch"]` |
| 5 `target_final` | `final_x`, `final_y`, `spatial_guard` | `r["target"]` |

Cuánto movió cada capa: `movio_cap_px`, `movio_lowproj_px`, `movio_branch_px`,
`movio_spatial_px`.

Las etapas 3, 4 y 5 **ya estaban en memoria** (`nuevo_code_v4.py:156-158`); el
CSV de V4 (`nuevo_code_v4.py:268-279`) simplemente no las escribía. La etapa 1
se captura envolviendo el método, sin reescribirlo (`trazar.py:139-147`).

---

## 5. Cómo se reconstruye el cap de V2, y cómo se verifica

La etapa 2 es la única que **no** se puede observar: es una variable local de
`NuevoCodeV2.step`. `trazar.py:150-168` la reproduce como copia literal de
`nuevo_code_v2.py:352-364`:

```python
jump = hypot(raw - prev_target)
cap  = 16 si estado in (HIGH, MEDIUM)
       12 si estado in (LOW, LOW_FORWARD)
       20 en otro caso                      # SIN_CERCA
si jump <= cap:                     -> raw            ("bajo_cap")
si no:
    poss = puntos del esqueleto con dist(prev_target) <= cap
    si len(poss):                   -> el de poss más cercano a raw  ("capeado")
    si no:                          -> raw SIN LIMITAR ("FALLA_ABIERTA")
```

Reproducir código es peligroso, así que **el banco se autovalida y aborta si
falla**. La invariante es:

> En todo frame donde `low_proj` **no** disparó, la etapa 2 reproducida tiene
> que ser **idéntica** a lo que V2 realmente devolvió (etapa 3).

Es verificable **sólo con el CSV**, sin correr nada: en las filas cuyo `reason`
no contiene `low_proj`, `cap_x`/`cap_y` debe ser igual a `lowproj_x`/`lowproj_y`.

```python
import csv
n = i = 0
for r in csv.DictReader(open("traza_hist.csv", encoding="utf-8")):
    if r["cap_x"] == "" or r["lowproj_x"] == "" or "low_proj" in r["reason"]:
        continue
    n += 1
    i += (abs(float(r["cap_x"]) - float(r["lowproj_x"])) < 1e-6 and
          abs(float(r["cap_y"]) - float(r["lowproj_y"])) < 1e-6)
print(i, "/", n)
```

**Resultado medido:**

| video | frames comparables | idénticos | % |
|---|---:|---:|---:|
| `hist` | 1924 | 1924 | 100,0 |
| `lineal` | 1142 | 1142 | 100,0 |
| `lineal70` | 1194 | 1194 | 100,0 |
| `como_esta` | 1388 | 1388 | 100,0 |
| `seguir` | 1184 | 1184 | 100,0 |
| `rumbo` | 998 | 998 | 100,0 |
| `a` | 657 | 657 | 100,0 |
| `roi_auto` | 3079 | 3079 | 100,0 |
| `con_planner` | 461 | 461 | 100,0 |
| `con_planner2` | 1031 | 1031 | 100,0 |
| `video_4` | 610 | 610 | 100,0 |
| **TOTAL** | **13.668** | **13.668** | **100,0** |

Si esta tabla no diera 100,0 %, **nada del resto del paquete valdría**, y
`trazar.py` lo imprime como `*** LA AUTOVALIDACION FALLO EN: ...`.

---

## 6. `FALLA_ABIERTA` — definición

`nuevo_code_v2.py:361` es un `if len(poss):` **sin `else`**:

```python
if jump > cap:
    ys, xs = np.nonzero(sk)
    dp = sqrt((xs - prev_target[0])**2 + (ys - prev_target[1])**2)
    poss = np.where(dp <= cap)[0]
    if len(poss):                    # <-- si NO entra, no pasa nada
        ...  target = punto capeado
# y acá `target` sigue valiendo `raw`, sin ningún límite
```

Es decir: cuando el salto **supera** el cap y **además** no existe ningún píxel
del esqueleto actual a menos de `cap` px del `prev_target`, el limitador **no
limita**: deja pasar el target crudo entero. El caso que más necesitaba el
límite es exactamente el que no lo recibe.

`cap_via` == `FALLA_ABIERTA` marca esos frames. **411 de 14.542 (2,8 %).**

Los otros valores de `cap_via`: `sin_prev` (no hay target previo), `bajo_cap`
(el salto no llegó al límite), `capeado` (el límite actuó).

---

## 7. Evento pérdida → reacquisición — definición

Un evento se abre cuando un frame con `final_x` no vacío es seguido por uno o
más frames con `final_x` vacío, y se cierra en el primer frame posterior que
vuelve a tener `final_x`. Se descartan las rachas iniciales sin un target previo
(no hay contra qué comparar). Implementación: `trazar.py:399-427` y, sólo desde
el CSV, `resumen_traza.py:44-72`.

Por evento se registra:

- `largo` — cuántos frames consecutivos sin target;
- `ultima X` — el último target antes de perder;
- `nueva X` — el primer target después de recuperar;
- `salto` — distancia euclídea entre esas dos;
- `d steer` — cambio de `steer_request_deg` a través del hueco;
- `d rumbo` — cambio de `heading_deg`;
- estado antes y después, y el `spatial_guard` del frame de reenganche.

**Por qué esta definición y no otra.** `nuevo_code_v4.py:316-318` pone
`prev = None` en el frame sin target, así que el salto de reacquisición nunca
entra en `max_accepted_jump`. Y `nuevo_code_v4.py:81-83` acepta esa primera
evidencia **sin aplicar `max_step`**, porque `self.previous is None`. El único
salto que el limitador no limita es también el único que la métrica no mira.
Este evento existe para cubrir precisamente ese hueco.

> Consecuencia estructural, verificable en el código: `reset()` se llama en
> `nuevo_code_v4.py:75`, `:97` y `:108` — o sea **justo cuando el guard detecta
> un salto imposible**. El rechazo no evita el teletransporte: lo posterga un
> frame y después lo deja pasar sin límite.

**No incluido todavía:** `candidate persistence` (si la componente reaparecida
sobrevive N frames). Requiere mirar hacia adelante desde el reenganche y cambia
la estructura del evento. Queda pendiente y está declarado como pendiente.

---

## 8. Tabla por video

`cap2` / `lowp` / `brV3` / `spV4` = frames en que **esa capa movió el target**
más de 0,01 px. `FA` = `FALLA_ABIERTA`. `ev` = eventos de pérdida.
`>24` = eventos con salto mayor a 24 px, que es el límite que
`SpatialTargetGuard` declara y **no** aplica en la reacquisición.

| video | fps | frames | sin target | cap2 | lowp | brV3 | spV4 | FA | ev | >24 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `hist` | 33,3 | 2091 | 106 | 221 | 80 | 7 | 18 | 91 | 48 | 37 |
| `lineal` | 33,3 | 1194 | 72 | 125 | 0 | 7 | 5 | 35 | 27 | 24 |
| `lineal70` | 33,3 | 1215 | 46 | 132 | 3 | 11 | 18 | 53 | 33 | 31 |
| `como_esta` | 33,3 | 1498 | 119 | 103 | 3 | 1 | 5 | 22 | 16 | 15 |
| `seguir` | 33,3 | 1259 | 80 | 142 | 12 | 3 | 1 | 42 | 33 | 29 |
| `rumbo` | 33,3 | 1068 | 77 | 173 | 5 | 0 | 2 | 24 | 17 | 17 |
| `a` | 33,3 | 751 | 93 | 82 | 10 | 3 | 5 | 21 | 19 | 15 |
| `roi_auto` | 33,3 | 3221 | 152 | 346 | 28 | 7 | 8 | 93 | 61 | 57 |
| `con_planner` | 33,3 | 461 | 2 | 96 | 0 | 0 | 0 | 2 | 2 | 1 |
| `con_planner2` | 33,3 | 1142 | 120 | 84 | 0 | 4 | 4 | 26 | 21 | 20 |
| `video_4` | 20,0 | 642 | 32 | 37 | 0 | 0 | 0 | 2 | 1 | 1 |
| **TOTAL** | | **14.542** | **899** | **1541** | **141** | **43** | **66** | **411** | **278** | **247** |

**Lectura directa: el que limita es el cap de V2.** 1541 intervenciones contra
43 del branch guard de V3 y 66 del spatial guard de V4. Sobre los **cuatro casos
de control** medidos por separado, el branch guard de V3 no actuó **ni una vez**
y el spatial guard de V4 actuó **una sola vez, de 8,1 px, en 952 frames**.

Además, el cap de V2 (12/16/20 px) es **más estricto** que el de V4 (24/30 px),
así que V4 sólo puede actuar sobre frames donde el de V2 ya falló.

---

## 9. Las 278 reacquisiciones

| | |
|---|---|
| eventos totales | **278** |
| salto p50 / p90 / máx | **65,9 / 145,0 / 163,8 px** |
| eventos con salto > 24 px | **247 (88,8 %)** |
| \|Δ steer_request\| p50 / p90 / máx | **44° / 156° / 178°** |
| largo p50 / p90 / máx | **1 / 8 / 36 frames** |
| `spatial_guard` en el frame de reenganche | **`REACQ_ACCEPT` en los 278** |

Dos cosas que conviene no pasar por alto:

1. **Los 278 son `REACQ_ACCEPT`.** Ninguno pasó por límite alguno.
2. **El largo mediano es 1 frame.** No hace falta una pérdida larga: una sola
   pérdida basta para que la X cruce la imagen entera.

Los diez mayores. La imagen mide 160 px de ancho:

| video | frames | salto | última X | nueva X | Δ steer | guard |
|---|---:|---:|---|---|---:|---|
| `a` | 10 | 163,8 | (1,116) | (157,66) | −176° | `REACQ_ACCEPT` |
| `lineal` | 4 | 163,2 | (0,115) | (156,67) | −176° | `REACQ_ACCEPT` |
| `a` | 9 | 162,5 | (0,108) | (157,66) | −177° | `REACQ_ACCEPT` |
| `roi_auto` | 3 | 162,3 | (6,119) | (158,62) | −171° | `REACQ_ACCEPT` |
| `roi_auto` | 13 | 161,6 | (3,116) | (157,67) | −173° | `REACQ_ACCEPT` |
| `roi_auto` | 11 | 161,6 | (2,116) | (155,64) | −172° | `REACQ_ACCEPT` |
| `roi_auto` | 10 | 161,0 | (1,111) | (155,64) | −173° | `REACQ_ACCEPT` |
| `lineal` | 1 | 160,7 | (2,112) | (156,66) | −173° | `REACQ_ACCEPT` |
| `lineal` | 6 | 160,6 | (4,117) | (156,65) | −171° | `REACQ_ACCEPT` |
| **`video_4`** | **32** | **160,0** | **(154,115)** | **(2,65)** | **+171°** | `REACQ_ACCEPT` |

La última fila es el caso más importante del paquete: ocurre en el **teacher
trace**, el único material donde se conoce de antemano la respuesta correcta, y
cae entre los frames 522 y 556 — el mismo tramo que la sección 6 del handoff ya
había señalado como la maniobra que Benjamín completó bien moviendo el robot a
mano.

---

## 10. Columnas del CSV

`frame`, `t_s`, `state`, `mode`, `reason`, `raw_x`, `raw_y`, `cap_x`, `cap_y`,
`cap_via`, `cap_jump_px`, `lowproj_x`, `lowproj_y`, `branch_x`, `branch_y`,
`branch_guard`, `final_x`, `final_y`, `spatial_guard`, `movio_cap_px`,
`movio_lowproj_px`, `movio_branch_px`, `movio_spatial_px`, `euclidea_px`,
`geodesica_px`, `proyeccion_px`, `rama_id`, `solape_rama`, `edad_prev_target`,
`edad_last_good`, `heading_deg`, `steer_request_deg`, `bearing_real_deg`,
`atan2_viejo_deg`.

Definiciones que no son obvias:

- **`geodesica_px`** — distancia entre `prev_target` y `final` **a lo largo del
  esqueleto**, con el Dijkstra de `nuevo_code_v2.py:144`. Los dos puntos se
  proyectan al nodo más cercano del esqueleto actual; si la proyección supera
  6 px, la columna queda vacía porque el punto no está sobre esta centerline y
  la comparación no significaría nada. `proyeccion_px` guarda esa distancia de
  proyección, para poder auditar el descarte.
- **`rama_id`** — identidad de la componente elegida por solape IoU con la del
  frame anterior. Con IoU < 0,25 se emite un ID nuevo. `solape_rama` guarda el
  IoU crudo.
- **`edad_prev_target`** / **`edad_last_good`** — frames desde la última vez que
  esa memoria cambió de valor. `last_good_target` sólo se actualiza en
  HIGH/MEDIUM (`nuevo_code_v2.py:377-378`), así que en LOW puede envejecer
  bastante: medido en el tramo `hist` 1354-1490, p50 **13** frames y máx **26**
  (0,78 s a 33,3 fps).
- **`steer_request_deg`** — `−90·(final_x − 79,5)/80`, o sea lo que el stack
  llama «ángulo». **Usa sólo X.** Se llama así y no `angle` a propósito.
- **`bearing_real_deg`** — `atan2(−(final_x − 79,5), 119 − final_y)`, el ángulo
  geométrico real desde el robot hasta ese mismo punto. Está en el CSV para que
  la diferencia entre las dos columnas sea auditable frame a frame.

---

## 11. Límites de este paquete — leer antes de concluir

1. **Es replay de lazo abierto.** Los frames los generó la trayectoria física
   que realmente ocurrió con el controlador viejo. Nada de acá puede afirmar qué
   habría hecho el robot con otro control. Regla de método 7 del handoff.
2. **`off_path` no está en la tabla a propósito.** Da 0 en los 14.542 frames y
   **no puede dar otra cosa**: en `SPATIAL_LIMIT` el punto aceptado sale de
   `np.nonzero(skel)` (`nuevo_code_v4.py:94,116-117`) y en los demás caminos
   `nuevo_code_v3.py:275-281` ya rechazó todo lo que no estuviera sobre el
   esqueleto. Es una identidad, no una medición, y publicarla como evidencia
   sería engañoso.
3. **El riesgo de «cambio de rama invisible al guard euclídeo» se midió y es
   marginal.** Sobre 8.049 transiciones con target en los dos frames, sólo **36
   (0,45 %)** tienen ratio geodésica/euclídea ≥ 2 con euclídea ≤ 24 px; con
   ratio ≥ 5, dos casos (`lineal70` f480: 12,5 px euclídea contra 122,2
   geodésica; `seguir` f809: 19,3 contra 155,3). Se había marcado P1 y **baja a
   P2**. El primer test que se escribió —geodésica infinita— daba 0 en todo y
   era un test débil: el esqueleto es de una sola componente, así que el grafo
   casi siempre es conexo.
4. **Los `nuevo_code_*.py` no están versionados.** Sólo los SHA-256 de §1.
5. **`candidate persistence` no está implementado** (§7).
6. **Los cuatro casos de control no entran en los agregados** para no contar
   frames dos veces. Se corren con `--casos` y se reportan aparte.

---

## 12. Qué se pide auditar

1. Que la reproducción del cap de V2 (§5) sea fiel a `nuevo_code_v2.py:352-364`,
   y que la invariante de autovalidación sea la correcta y no una tautología.
2. Que la definición de evento (§7) no deje afuera ningún salto real.
3. Que la tabla de §8 se reconstruya con `resumen_traza.py` y dé lo mismo.
4. Contraejemplos: cualquier frame donde la traza diga algo distinto de lo que
   se ve en el video.


---

## 13. Corrección aplicada: el contador de autovalidación de `--casos`

La auditoría externa encontró que con `--casos`, `tz.paso()` se ejecuta antes de
`if i >= desde`, así que el contador de autovalidación acumulaba el pre-roll:
`hist_exito` decía `n = 100` y `629 frames` de autovalidación. **El pre-roll es
necesario** —sin él la memoria temporal llega muerta a `--desde`— pero el número
publicable es el del tramo. Corregido: ahora se informan los dos por separado.

```
hist_exito       EXITO      n=100   sin target 0 (0.0 %)
    autovalidacion etapa 2, SOLO EL TRAMO : 100.0 % de 100 frames  OK
    autovalidacion con el pre-roll 0..579: 100.0 % de 629 frames
```

El veredicto (`OK` / `MAL`) ahora se decide con el del tramo. Los once
`traza_*.csv` **no cambian**: el arreglo no toca ninguna columna.

---

## 14. Ground truth retrospectivo de `video_4` — resultado

`groundtruth_v4.py`, rango 490-600, 111 frames.

### Método

Ancla = **todo** frame donde una componente toca la fila 119: ahí el robot la
tiene debajo y, en un teacher trace, esa es la cinta correcta por construcción.
Se encontraron **103 anclas sobre 141 frames**. Desde cada una se propaga hacia
adelante y hacia atrás por solape (fracción de la componente más chica cubierta,
≥ 0,30, con 9 px de dilatación); cada frame se queda con la asignación de la
ancla más cercana. Un solo ancla no alcanza: la cinta desaparece 23 frames y
ninguna propagación en una sola dirección puede cruzar ese hueco.

El target de referencia se calcula con el **mismo `path_target` de
`nuevo_code_v2.py`** alimentado con la componente correcta. No se inventa una ley.

### Qué dice el ground truth

**La cinta correcta no está en el cuadro entre los frames 524 y 546** (23
frames). Está visible en 88 de 111 (79,3 %).

| tipo | frames | |
|---|---:|---|
| `T1_SELECCION` | **0** | V4 nunca siguió una componente equivocada |
| `T1_INVENTADO` | **0** | nunca dio target sin cinta visible |
| `T2_DISCONTINUIDAD` | **0** | |
| `T3_REACQUISICION` | **0** | |
| `T0_SIN_ORDEN` | **9** | frames 547-555: la cinta está a la vista y V4 no da target |
| `T4_CONVERSION` | **8** | frames 556-562 y 591 |

Error del target de V4 contra el de referencia, donde hay ground truth:
**p50 0,0 px · p90 11,6 px · máx 29,0 px** sobre 79 frames.

### Consecuencia para C-2

**El salto de 160 px del frame 556 NO es un error de percepción.** Solape con la
cinta correcta = 1,00, error del target = 1,0 px. La cinta desapareció de verdad
y volvió a entrar por el lado opuesto: el salto es del mundo, no del tracker.

El hueco de reacquisición (`nuevo_code_v4.py:81-83`) sigue siendo un riesgo
estructural sin instrumentar, pero **en el único caso con respuesta conocida no
produjo un error de percepción**. Eso cambia el orden de prioridad.

### El error que sí hubo, con su cadena causal completa

`prev_target` queda **congelado en (154,115) desde el frame 523 hasta el 556** —
33 frames — porque `nuevo_code_v2.py:320-322` y `:342-344` salen de PERDIDA sin
resetear la memoria. Y `nuevo_code_v2.py:340` rechaza una componente si
`distancia > 75` **y** `ymax < 70`:

| frame | área | `ymax` | dist. a `prev_target` | resultado |
|---:|---:|---:|---:|---|
| 550 | 596 | 65 | 81,0 | rechazada → PERDIDA |
| 553 | 622 | 67 | 111,7 | rechazada → PERDIDA |
| 554 | 710 | 68 | 109,0 | rechazada → PERDIDA |
| 555 | 771 | 68 | 107,0 | rechazada → PERDIDA |
| **556** | 908 | **70** | 103,7 | **aceptada** |

V4 tuvo la cinta correcta a la vista con 622 px de área desde el frame 553 y la
rechazó tres frames más **por dos filas de diferencia en `ymax`**. La distancia
nunca mejoró (103,7 > 75 igual en el 556): lo que destrabó fue que la cinta
creciera hasta cruzar `ymax >= 70`. La referencia contra la que se mide esa
distancia tiene 33 frames de antigüedad.

**Son 9 frames = 0,45 s a 20 fps de ceguera con la cinta a la vista**, y la causa
es la memoria congelada, no ninguno de los cinco limitadores.

### El otro error: la conversión

En 556-562 el target está bien (error 0,0 px) y `steer_request` pide **+87°**
mientras la dirección real hacia ese mismo punto es **+55°**. Sobre los 79
frames con ground truth: p50 3,9° · p90 17,3° · **máx 32,1°**. El error es chico
cuando el target está cerca del centro y grande cuando está lateral y lejos, que
es exactamente cuando el robot está en problemas.

Importa porque el firmware no es agnóstico: `main.cpp` recibe `angle+90` y el
`case 7` entra en pivote con `|angle| >= 40°`. Los dos valores pivotean, pero
con `rot` distinto.

### Archivos

- `groundtruth_video_4.csv` — 17 columnas, una fila por frame.
- `groundtruth_video_4.avi` — evidencia visual: verde = cinta correcta, cruz
  verde = target de referencia, X blanca = target de V4.

Los dos son derivados y están en `.gitignore`; se regeneran con:

```bash
python groundtruth_v4.py --avi
```


---

## 15. RETRACTACIÓN — el tramo de `video_4` usado en §14 no es físicamente válido

**Dato aportado por Benjamín el 2026-08-23, después de escribir §14:** en
`video_4.avi`, aproximadamente entre los frames **515 y 575**, el robot fue
**levantado del piso y reposicionado a mano**.

Con el robot en el aire la cámara no conserva su pose respecto del suelo, y la
premisa sobre la que se apoya todo el ground truth —*una componente que toca la
fila 119 es la cinta que el robot tiene debajo*— deja de ser cierta.

### Lo que se retira

| conclusión de §14 | estado |
|---|---|
| «9 frames = 0,45 s de ceguera con la cinta a la vista» (`T0_SIN_ORDEN`, f547-555) | **RETIRADA.** El robot estaba siendo reposicionado |
| «`steer_request` +87° contra bearing +55°» como evidencia P0 contra la conversión (f556-562) | **RETIRADA.** No se juzga una ley de conducción con el robot en las manos |
| «el salto de 160 px es del mundo, no del tracker» | **Cierto sólo en sentido óptico.** No fue un evento de conducción autónoma y no debe contarse como reacquisición |
| la cadena causal `prev_target` congelado → rechazo por `v2:340` | **el mecanismo existe en el código**, pero *ese* tramo no lo demuestra. Se remide aparte (§15.3) |

El tramo queda etiquetado en el código como `MANUAL_LIFT` en
`groundtruth_v4.py`, en la constante `TRAMOS_INVALIDOS`, y se excluye de todo
agregado.

### 15.1 No se pudo construir un detector de pose

Se intentó detectar la manipulación por imagen, para no depender de anotación
humana. **Falló, y el número queda publicado para que no se reintente sin datos
nuevos.** Tres señales sobre el frame 160×120, validadas contra el único tramo
etiquetado:

| señal | p50 fuera | p50 dentro | separación |
|---|---:|---:|---:|
| cambio global entre frames | 1,00 | 2,00 | 0,74 σ |
| desplazamiento por correlación de fase | 0,52 | 1,56 | 0,79 σ |
| fila donde termina el suelo (banda central) | 21,0 | 27,0 | **1,34 σ** |

Con la mejor de las tres y el umbral que cubre el 75 % del tramo etiquetado, se
marca además el **27,9 %** del resto del video. Inservible. Y en los diez
autónomos esa misma señal tiene entre 21 % y 35 % de frames fuera de rango, o
sea que no distingue «levantado» de «doblando».

**Conclusión de método: la validez física de un tramo es un input humano.** Se
anota, se versiona y no se infiere. La única etiqueta sólida disponible hoy es a
nivel de video, y no hay que medirla: se sabe cómo se grabó cada uno.

- **AUTÓNOMO** — los 10 paneles 640×240: la Pi corriendo, la Teensy moviendo.
- **MANUAL** — `video_4.avi`, con el sub-tramo 515-575 levantado.

### 15.2 `video_4` con el tramo excluido

Sobre los 50 frames físicamente válidos del rango 490-600:

| | |
|---|---|
| cinta correcta visible | **100 %** |
| `T0_SIN_ORDEN` / `T1` / `T2` / `T3` | **0** |
| `T4_CONVERSION` | **1** (frame 591) |
| error del target contra la referencia | **p50 0,0 px** · p90 11,5 · máx 29,0 |
| diferencia `steer_request` vs bearing | p50 2,3° · p90 10,3° · máx 23,7° |

**Cuando el robot está apoyado y la cámara en pose normal, NUEVO CODE engancha
la cinta correcta y el target coincide con la referencia.** Es el resultado más
favorable a V4 de todo el paquete, y aparece recién al sacar el tramo inválido.

### 15.3 La memoria congelada, remedida sólo en conducción autónoma

`memoria_perdida.py`, los 10 paneles, 13.900 frames, `video_4` excluido. Se
cuentan los frames en que la regla `nuevo_code_v2.py:340`
(`distancia > 75` **y** `ymax < 70`) descarta una componente de **≥ 200 px**, y
se calcula el contrafáctico con la misma regla contra la memoria reseteada al
centro de abajo.

| | |
|---|---|
| rachas de bloqueo | **20** |
| frames bloqueados | **127 de 13.900 (0,91 %)** |
| largo de la racha | p50 6 · p90 13 · **máx 22 frames (660 ms)** |
| edad de `prev_target` al bloquear | p50 8 · máx 28 frames |
| frames que pasarían con la memoria reseteada | **46 de 127 (36,2 %)** |

Los cuatro casos más largos:

| video | desde | largo | área máx | dist. a memoria vieja | dist. reseteada | salvables |
|---|---:|---:|---:|---:|---:|---:|
| `como_esta` | 146 | 22 (660 ms) | 881 | 100,8 | 67,4 | **15** |
| `a` | 511 | 18 (540 ms) | 1080 | 127,1 | 72,8 | **10** |
| `roi_auto` | 2507 | 12 (360 ms) | 812 | 79,7 | 80,6 | **0** |
| `a` | 414 | 10 (300 ms) | 1317 | 103,2 | 77,1 | 1 |

**El fenómeno es real y mucho más chico de lo que sugería el tramo inválido**:
0,91 % de los frames, unas 3 rachas por minuto. Y **el reset no es una bala de
plata**: en 4 de las 10 rachas más largas ninguno de los frames se salvaba,
porque la componente estaba genuinamente lejos también del centro.

Tampoco generaliza uniforme: `seguir`, `rumbo` y `con_planner` no tienen **ni
una** racha, y `hist` tiene una sola de 1 frame. Se concentra en `a`,
`roi_auto`, `como_esta` y `lineal`.

### 15.4 Estado del diagnóstico después de la corrección

| | antes | después |
|---|---|---|
| percepción / target | prometedor | **muy bueno**: 0,0 px de error mediano donde el robot está apoyado |
| reacquisición | «claramente rota» | **riesgo estructural en el código, sin contraejemplo físico limpio todavía** |
| memoria congelada | «0,45 s de ceguera» | **real pero chica**: 0,91 % de frames, máx 660 ms, 36 % salvable |
| `target_x` → steer | «claramente problemática» | **pendiente. NO condenada por `video_4`** |

### 15.5 Incertidumbre que queda abierta

Los diez son autónomos **por cómo se grabaron, no por una medición**. Si alguno
corresponde a la corrida marcada `2026-08-22_INVALIDA_ruedas_en_el_aire.csv`,
hay que sacarlo y volver a correr. Hoy no se puede saber: de 60 pares
video×CSV posibles sólo existe uno enganchado.
