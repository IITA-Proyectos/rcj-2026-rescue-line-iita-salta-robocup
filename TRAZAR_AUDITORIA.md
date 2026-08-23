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
| `software/raspberry/final_rpi/trazar.py` | 523 | 21.785 | `69736c99b540538baa6f345f4c7c44feb3ed64c1cd7822dd36b2b6101a260e05` | sí, commit **`57e766c`** |
| `software/raspberry/final_rpi/resumen_traza.py` | 150 | 5771 | `5eb3e8684588b2d8600e3b9fd510d2d484f8b98f94f2b45a400c60b1af4171f7` | sí |

- Repositorio HEAD al congelar: **`57e766c8a394612b1410fe48f570048687830ddd`**
  (`feat(rpi): banco que traza las CINCO etapas de Nuevo Code, sin tocarlo`).
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
