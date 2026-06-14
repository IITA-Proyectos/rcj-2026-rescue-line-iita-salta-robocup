# Auditoría Integral 2026-05-18 — Módulo PERCEPCIÓN (RPi)

**Dominio:** Percepción / Visión por computadora en Raspberry Pi 4B
**Archivos auditados (lectura completa):**
- `software/raspberry/final_rpi/Main.py` (850 líneas)
- `software/raspberry/final_rpi/camthreader.py` (44 líneas)
- `software/raspberry/final_rpi/calibration.py` (50 líneas)
- Soporte: `software/raspberry/AI/best_ncnn_model/metadata.yaml`, `docs/es/yolo-raspberry.md`, `software/raspberry/test/rescue_zone_test/tflite-balance.py` (versión legacy del mismo pipeline)

**Auditor:** Claude Code (Opus 4.8) bajo supervisión de @gviollaz
**Alcance:** SOLO lectura. Cada finding lleva *riesgo-si-NO-se-fixea* / *riesgo-si-SÍ-se-fixea* / *tiempo estimado* / *cómo validar*, según la convención del equipo (un finding NUNCA se presenta como "bug a fixear" pelado).

> **Relación con auditorías previas.** Este informe NO repite las auditorías de RESILIENCIA (#108–#113, #65, #64) ni de CORRECTITUD (#120–#128). Las **cita** y agrega lo nuevo o lo que quedó sin confirmar. Donde el branch ya cambió algo respecto de la versión que vieron esas auditorías, lo señalo explícitamente.

---

## 0. Resumen ejecutivo

El pipeline de percepción tiene **dos caminos** muy distintos en madurez:

1. **Línea (visión clásica, `estado == 'linea'`, Main.py:724–845):** funcional y tuneado por los chicos durante meses. Los bugs acá son de **calibración de color** (espacios mal usados, rangos frágiles) que cuestan puntos pero no cuelgan el robot. El más grave es el **trigger de entrada a rescate** (`silver_line`), que decide cuándo el robot abandona la línea y entra a la zona de evacuación.

2. **Rescate (YOLO + tracking, `modo_rescate`, Main.py:290–705):** mucho más frágil. Tiene **un bug sistémico sin confirmar** (formato del tensor TFLite / NMS — #124) que, de ser real, invalida TODA la detección de víctimas y zonas, y una **lógica de estados de depósito con nombres invertidos** que es muy fácil de romper en una edición futura.

**Hallazgos de mayor prioridad para Incheon (T–6 semanas):**

| ID | Severidad | Qué | Estado vs. auditorías previas |
|---|---|---|---|
| **V18-01** | **P0** | Formato tensor TFLite / NMS sin verificar (`for det in out` asume `[N,6]` pero `end2end:false`) | Confirma y profundiza **#124 (B7)** |
| **V18-02** | **P1** | `silver_mask` se calcula sobre BGR con umbrales medidos en HSV → trigger de rescate poco confiable | Confirma **#B2**; agrego que es el ÚNICO disparador de entrada a zona |
| **V18-03** | **P1** | Lógica de depósito con clases/nombres de estado invertidos (`depositar verde` apunta a la zona ROJA) | Matiza **#B3**: el riesgo real es de **mantenibilidad/edición**, no un cuelgue actual |
| **V18-04** | **P1** | Máscara roja sin wrap de Hue (H∈[1,7]) → pierde la mitad del rojo | Confirma **#B9** |
| **V18-05** | **P1** | Verde en LAB con ventana muy angosta + dependiente de iluminación de estadio | Amplía **#86** y el "MEDIO" de `analisis-raspberry-pi.md` |
| **V18-06** | **P1** | `camthreader` sin `Lock` → frame stale/desgarrado alimenta decisiones | **Ya es #113 / TEMA V-A.** Agrego matiz de impacto en rescate |
| **V18-07** | **P2** | Sin confirmación multi-frame de `silver_line`/`red_line` → 1 frame de ruido cambia de estado | NUEVO |
| **V18-08** | **P2** | Exposición / balance de blancos de la cámara NO fijados → AGCWD pelea contra auto-exposure | NUEVO (complementa #86) |
| **V18-09** | **P2** | `calibration.py` muestra frames desincronizados (LAB del frame N, RGB del N+1) | **Ya es TEMA V-E** (#104). Lo reconfirmo con detalle |
| **V18-10** | **P2** | Umbrales de color **hardcodeados** sin protocolo de recalibración in-situ (Songdo/Incheon) | NUEVO — oportunidad de mayor impacto competitivo |
| **V18-11** | **P2** | ROIs hardcodeadas (`[:55]`, `[62:]`, `[75:]`, `[90:]`) acopladas a montaje físico de cámara | NUEVO |
| **V18-12** | **P2** | `CLASS_THRESH` de rescate cambió entre versiones sin registro (rojo 0.2→0.5) | NUEVO (deuda de proceso) |

> **Nota de divergencia importante:** la versión productiva (`Main.py` de este branch) ya **corrigió** varias cosas que la versión legacy `tflite-balance.py` tenía mal: ahora hay `send_frame()` con `clamp_byte` (#66), timeout en serial (#73), `read_frame_with_recovery` para `None` de cámara (#65), guard `HEADLESS`/`SHOW_DEBUG_WINDOWS` (#64) y telemetría TX (#75). **Eso es trabajo bien hecho de los chicos y hay que reconocerlo.** Lo que sigue son los huecos que quedan.

---

## 1. Metodología y mapa del pipeline

### 1.1 Camino de LÍNEA (`estado == 'linea'`, Main.py:724–845)

```
frame USB → rotate 180 → resize 160×120 (INTER_NEAREST)
  ├─ black_mask  = inRange(BGR, [0,0,0]..[90,90,90])   # línea negra; top [:55]=0
  ├─ green_mask  = inRange(LAB, [120,90,100]..[170,120,140])  # solo filas [90:]
  ├─ red_mask    = inRange(HSV, [1,147,159]..[7,205,216])     # top [:75]=0
  ├─ silver_mask = inRange(BGR(!), [79,16,46]..[168,28,79])   # top [:75]=0  ← BUG V18-02
  └─ ángulo por centro de masa ponderado (x_com·(1−y_com))
→ green_state (giros verdes / doble verde) + silver_line + red_line
→ send_frame(speed, angle, green_state, silver_line)
→ si silver_line: estado='rescate'
```

### 1.2 Camino de RESCATE (`modo_rescate`, Main.py:290–705)

```
3 hilos:
  capture_thread → rotate180 → frame_q (maxsize 2)
  infer_thread   → resize 256² → enhance(AGCWD+antiflash) cada DETECT_EVERY(=3)
                 → TFLite invoke → out = get_tensor(...)[0]
                 → for det in out: x1,y1,x2,y2,score,cls  ← ASUME [N,6] (BUG V18-01)
                 → filtros por estado → result_q
  serial_monitor_local → escucha 0xFF/0xF8
main_loop → CentroidTracker(max_lost=8) → choose_stable_target → P-control por error_x
          → green_state según clase + width_ratio (stop) → send_frame
```

El modelo es **YOLOv8 `imgsz=256`, 4 clases** (`metadata.yaml`): `0:negro 1:plateado 2:rojo_alto 3:verde_alto`, **`end2end:false`** (sin NMS embebido — clave para V18-01). Nota: el código carga un **TFLite** (`/home/pi/Downloads/best_float32 (1).tflite`), mientras que el repo versiona un **.onnx** (`zonasdepositoalta.onnx`) y `docs/es/yolo-raspberry.md` dice que el runtime elegido fue ONNX. Hay **divergencia entre lo documentado (ONNX) y lo que corre (TFLite)** — relevante para V18-01 porque el formato de salida depende de cómo se exportó ese TFLite puntual.

---

## 2. Hallazgos detallados

### V18-01 — [P0] Formato del tensor TFLite / NMS sin verificar (confirma y profundiza #124 / B7)

**Ubicación:** `Main.py:480-497` (idéntico patrón en `tflite-balance.py:340-357`).

```python
out = interpreter.get_tensor(output_details['index'])[0]
detections = []
for det in out:
    x1, y1, x2, y2, score, cls_raw = det      # ← asume fila = 6 valores (formato NMS/end2end)
    ...
    x1 *= IMGSZ; y1 *= IMGSZ; x2 *= IMGSZ; y2 *= IMGSZ
```

**Causa raíz.** El loop desempaqueta **6 valores por fila** `(x1,y1,x2,y2,score,cls)` y trata las coords como **normalizadas** (las multiplica por `IMGSZ`). Eso es el formato de un export **con NMS embebido** (`nms=True`, salida `[N,6]`). Pero `metadata.yaml` dice explícitamente **`end2end: false`**. El head crudo de YOLOv8 es **`[1, 4+nc, 8400]` = `[1, 8, 8400]`** (4 box + 4 clases, sin objectness), **transpuesto** respecto de lo que el loop espera.

**Qué pasa si el TFLite NO trae NMS (escenario probable dado `end2end:false`):**
- `out = get_tensor(...)[0]` → shape `(8, 8400)`.
- `for det in out` itera **8 filas** (no 8400 detecciones). Cada `det` tiene 8400 elementos → el unpacking `x1,y1,x2,y2,score,cls_raw = det` **lanza `ValueError: too many values to unpack`**.
- Con el `infer_thread` **sin `try/except`** (eso es **#111 / R-V04**), la excepción **mata el hilo en silencio**: `result_q` deja de llenarse, `main_loop` cae en `queue.Empty` cada 0.25 s para siempre → el robot **se queda quieto en la zona de rescate sin detectar nada**. Es un **cuelgue funcional total del rescate**, no solo "detección mala".

**Por qué quedó así (hipótesis).** El código probablemente funcionó en algún momento con un export `nms=True`, y al re-exportar el modelo (carpeta `tfliteNMS_prueba` sugiere que estuvieron probando ambos) quedó un `best_float32 (1).tflite` cuyo formato real nadie verificó. El `metadata.yaml` versionado es del **modelo NCNN/ONNX**, no necesariamente del TFLite que corre — por eso no se puede asumir nada.

**Riesgo si NO se fixea (verifica):** **P0 sistémico.** Si el TFLite no trae NMS, el rescate **nunca funciona** (mejor caso: crash de hilo silencioso; peor caso: si por casualidad no crashea, coords/clases basura → persigue fantasmas). Es el bug de **mayor impacto absoluto de todo el módulo** porque invalida la mitad del puntaje (víctimas + zonas).

**Riesgo si SÍ se fixea:** Bajo, pero **NO es trivial** (≠ "1 línea"). Hay que:
1. Imprimir `out.shape` real en el warmup (Main.py:286 ya hace `_ = interpreter.get_tensor(...)`; agregar `print(_.shape)`).
2. Según el shape:
   - Si es `(1, N, 6)` o `(N, 6)` → el código actual está OK, **solo hace falta el assert** para que no vuelva a romperse en silencio.
   - Si es `(1, 8, 8400)` → hay que **transponer** (`out.T` → `(8400, 8)`), **separar box+clases** (`box = out[:4]`, `cls_scores = out[4:]`), tomar `score = cls_scores.max(0)`, `cls = cls_scores.argmax(0)`, **convertir `cxcywh`→`xyxy`**, y **correr NMS** (`cv2.dnn.NMSBoxes`). Son ~25–40 líneas nuevas y cambia la semántica de coordenadas (el head crudo da box en **píxeles de 256**, no normalizado → ojo con el `*= IMGSZ`).
3. **Riesgo de regresión si se hace mal:** podrías romper un rescate que hoy funciona (si resulta que SÍ traía NMS). Por eso el paso 1 (medir) es obligatorio **antes** de tocar nada.

**Validación (10 min de diagnóstico + banco):**
```python
# En el warmup, después de interpreter.invoke():
o = interpreter.get_tensor(_output_details['index'])
print("OUT SHAPE:", o.shape, "DTYPE:", o.dtype, "min/max:", o.min(), o.max())
```
- Esperado si trae NMS: `(1, N, 6)` con coords en `[0,1]`.
- Esperado si NO trae NMS: `(1, 8, 8400)` con coords en `[0,256]`.
- En banco: poner una pelota plateada y una negra frente a la cámara, confirmar bbox dibujado encima del objeto real (no desplazado/escalado).
- Agregar `assert o.ndim==3 and o.shape[-1]==6, f"Formato inesperado {o.shape}"` para que un re-export futuro falle **ruidoso** y no en silencio.

**Cruce con otras auditorías:** este finding **depende de #111** (infer_thread sin try/except). Si se arregla #111 primero, el síntoma cambia de "cuelgue silencioso" a "excepción logueada" — lo que ayuda a diagnosticar, pero **no resuelve** la detección. Hay que hacer ambos.

---

### V18-02 — [P1] `silver_mask` calculada en BGR con umbrales HSV (confirma #B2)

**Ubicación:** `Main.py:72-73, 745, 750-751`.

```python
lower_silver_hsv = np.array([79, 16, 46])     # nombre dice HSV
upper_silver_hsv = np.array([168, 28, 79])
...
hsv_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2HSV)   # SÍ se calcula HSV
...
red_mask    = cv2.inRange(hsv_frame, lower_red, upper_red)    # rojo usa HSV ✔
silver_mask = cv2.inRange(frame_resized, lower_silver_hsv, upper_silver_hsv)  # plata usa BGR ✗
```

**Causa raíz.** El sufijo `_hsv` y los valores (S∈[16,28], V∈[46,79]) delatan que los umbrales se **midieron en HSV** (con `calibration.py`/`annotator.py`, que imprimen valores HSV). Pero `inRange` se aplica a **`frame_resized` (BGR)**, no a `hsv_frame`. El rojo, tres líneas arriba, **sí** usa `hsv_frame` correctamente — lo que confirma que la intención era HSV y esto es un descuido de copy-paste, no una decisión.

**Consecuencia concreta.** `inRange(BGR, [79,16,46], [168,28,79])` exige: **B∈[79,168], G∈[16,28], R∈[46,79]**. Eso es un color **azul-verdoso oscuro con G casi nulo** — **nada que ver con plateado** (que en BGR es ~`[180,180,180]`, gris claro con los 3 canales altos y G muy por encima de 28). Resultado: la máscara captura **píxeles equivocados** y la cinta plateada real **no entra** en el rango (su G≈180 ≫ 28).

**Por qué es P1 y no P2.** `silver_line` es el **único disparador** de entrada a la zona de rescate (`Main.py:818-819: if silver_line: estado='rescate'`). Si el umbral está roto:
- **Falso negativo** (lo más probable): el robot **pasa de largo la entrada** de la zona de evacuación → no rescata → pierde todo el puntaje de víctimas. Catastrófico en competencia.
- **Falso positivo** (si por casualidad algún reflejo cae en ese rango BGR raro): entra a rescate **en mitad de la pista** → se desorienta.

Que el robot haya "funcionado" en pruebas sugiere una de dos: (a) por casualidad el piso/cinta de su pista de prueba caía en ese rango BGR, o (b) los chicos bajaron el `area > 50` (Main.py:799) hasta que disparaba con cualquier cosa — lo que lo hace **aún más frágil** ante el piso nuevo de Incheon.

**Riesgo si NO se fixea:** alto en pista nueva. El trigger de rescate es impredecible bajo otra iluminación/piso.

**Riesgo si SÍ se fixea:** **medio**, por contraintuitivo que suene. Cambiar a `inRange(hsv_frame, ...)` es 1 palabra, **pero** si los chicos llevan meses tuneando el `area>50` y el comportamiento contra una máscara BGR rota, al pasar a HSV **cambia todo el balance** y hay que **recalibrar plata de cero** (rango HSV + umbral de área). No es flip-and-forget. Debe ir acompañado de una sesión de calibración (ver V18-10).

**Validación (banco, ~20 min):**
1. Con `calibration.py`/`annotator.py`, doble-click sobre la cinta plateada real → leer valores HSV reales (los `print` ya existen).
2. Setear `lower/upper_silver_hsv` a ese rango ±tolerancia.
3. Cambiar `silver_mask = cv2.inRange(hsv_frame, ...)`.
4. Mostrar `silver_mask` (debug ya disponible vía `debugHori`): la cinta debe iluminarse blanca y el resto negro, **sin** que el piso brillante dispare.
5. Pasar el robot por la entrada 10 veces → debe disparar `silver_line` 10/10 y **0** falsos en recta normal. Registrar en `TEST_LOG.md`.

---

### V18-03 — [P1] Lógica de depósito con clases y nombres de estado invertidos (matiza #B3)

**Ubicación:** `Main.py:312, 491-496, 505-518, 615-634`.

Acá hay que ser preciso porque **#B3 ("clases YOLO invertidas") como se enunció NO es exacto** — y el equipo merece el matiz correcto para no "arreglar" algo que está bien y romperlo.

**Lo que SÍ está bien:**
- `CLASS_NAMES = ['negro','plateado','rojo alto','verde_alto']` **coincide** con `metadata.yaml` (0=negro, 1=plateado, 2=rojo_alto, 3=verde_alto). No hay inversión de nombres respecto del modelo.
- En `'rescate'`, `select_target_from_list` toma `cls in (0,1)` = negro + plateado = **las dos pelotas**. Correcto (víctima viva plateada + muerta negra).

**Lo que está MAL / es trampa:**
1. **Filtros de `infer_thread` (491-496) contradicen a `select_target_from_list` (505-518).** Hay **dos lugares** que filtran por estado y **no son consistentes**:
   - `infer_thread` en `'depositar'` descarta `cls in (0,1,2)` → deja pasar **solo cls 3 (verde)**.
   - `select_target_from_list` en `'depositar'` toma `cls in (3,)` → verde. OK, coinciden acá.
   - Pero en `'depositar verde'`: `infer_thread` descarta `(0,1,3)` → deja **cls 2 (rojo)**; `select_target_from_list` toma `cls in (2,)` → rojo. **El sub-estado llamado "depositar VERDE" en realidad apunta a la zona ROJA.**
2. **Nombres invertidos = bomba de tiempo.** El estado `'depositar verde'` que persigue la zona **roja** (cls 2) es semánticamente al revés de su nombre. Hoy "funciona" porque los dos lugares están alineados por casualidad, pero **cualquiera que edite uno solo** (muy probable en las 6 semanas que quedan) rompe el depósito sin darse cuenta. Es exactamente el tipo de "fallo lógico aleatorio" que el equipo quiere evitar.
3. **`green_state` de depósito (491-494):** cls 2 (rojo)→`green_state=8`, cls 3 (verde)→`green_state=9`. El nombre de variable `ball_type="red_zone"/"green_zone"` está bien, pero como entra desde estados con nombres cruzados, es muy difícil de seguir.

**Lógica de negocio correcta (reglamento, `yolo-raspberry.md:33-41`):** víctima **viva = plateada** → va a la zona **VERDE**; víctima **muerta = negra** → va a la zona **ROJA**. El flujo del código (`depositar`→verde primero, luego `depositar verde`→rojo) **puede** ser correcto si la secuencia de pinza deposita primero las vivas y luego las muertas — **pero eso no se puede verificar desde la RPi**, depende del firmware Teensy y de `green_state` 6/7/8/9. Hay un **acoplamiento implícito RPi↔Teensy** no documentado.

**Riesgo si NO se fixea:** **bajo HOY** (funciona por alineación accidental), **pero alto ante cualquier edición**. Además, debugging confuso: nadie va a entender que "depositar verde" mira rojo.

**Riesgo si SÍ se fixea:** **bajo-medio**. El fix correcto es **mantenibilidad, no corrección funcional**:
- Renombrar estados a algo inequívoco (`'depositar_vivas'`/`'depositar_muertas'` o `'zona_verde'`/`'zona_roja'`).
- **Unificar el filtro en UN solo lugar** (eliminar la duplicación 491-496 vs 505-518). Mientras haya dos fuentes de verdad, el bug latente sigue.
- Agregar un comentario que explique el mapeo viva→verde / muerta→roja.
- **NO tocar** los números de `green_state` (6/7/8/9) sin coordinar con Teensy — ahí sí se rompe algo validado.

**Validación (banco):** correr la secuencia completa rescate→depositar con una pelota plateada y una negra; confirmar que va a la zona verde con la plateada y a la roja con la negra. Registrar el mapeo real observado en `TEST_LOG.md` (sirve también de documentación del contrato con Teensy).

> **Veredicto sobre #B3:** el finding original apunta a algo real (la lógica de depósito es confusa y frágil) pero la etiqueta "clases YOLO invertidas" es imprecisa: las **clases del modelo NO están invertidas**; lo que está invertido/cruzado son los **nombres de los sub-estados de depósito** y hay **duplicación de filtros**. Reclasificar como **deuda de mantenibilidad de alto riesgo de regresión**, no como "detección rota".

---

### V18-04 — [P1] Máscara roja sin wrap de Hue (confirma #B9)

**Ubicación:** `Main.py:74-75, 748-749`.

```python
lower_red = np.array([1, 147, 159])
upper_red = np.array([7, 205, 216])
red_mask  = cv2.inRange(hsv_frame, lower_red, upper_red)   # H ∈ [1,7] solamente
```

**Causa raíz.** En OpenCV el Hue va de 0–179 y el **rojo está partido en dos** alrededor de 0: el rojo "cálido" cae en H≈0–10 y el rojo "frío"/magenta en H≈170–179. Acá solo se cubre **H∈[1,7]** — una banda de **6 grados**. Todo rojo que caiga en H≈170–179 (muy común según el balance de blancos de la cámara y la temperatura de color del LED del estadio) **se pierde**.

**Dónde importa.** `red_mask` dispara `green_state=10` (Main.py:811-812) que, según el contrato, es la **línea roja de "fin de pista"/parada** (regla de la cinta roja que marca el final). Si no se detecta:
- **Falso negativo:** el robot **no para donde debe** → puede salirse o seguir buscando línea inexistente.
- Además H∈[1,7] con S∈[147,205] altísimo es **muy angosto**: cualquier rojo desaturado por reflejo se escapa.

**Riesgo si NO se fixea:** P1. La línea roja es un evento de baja frecuencia pero alto impacto (parada/fin). Frágil ante iluminación.

**Riesgo si SÍ se fixea:** bajo. Patrón estándar de doble banda:
```python
lower_red1=np.array([0,120,120]);   upper_red1=np.array([10,255,255])
lower_red2=np.array([170,120,120]); upper_red2=np.array([179,255,255])
red_mask = cv2.inRange(hsv,lower_red1,upper_red1) | cv2.inRange(hsv,lower_red2,upper_red2)
```
~3 líneas. **Pero** los valores exactos hay que recalibrarlos in-situ (V18-10); abrir el rango sin recalibrar el `area>25` (Main.py:807) puede generar falsos positivos con la cinta plateada o el verde mal balanceado.

**Validación:** apuntar a una cinta roja real bajo el LED del estadio (o simulado), leer H con `annotator.py`. Si cae en ~170–179, el bug es 100% activo. Mostrar `red_mask` con/sin la segunda banda. Registrar.

---

### V18-05 — [P1] Verde en LAB con ventana angosta y dependiente de iluminación (amplía #86)

**Ubicación:** `Main.py:70-71, 733, 742`.

```python
lower_green = np.array([120, 90, 100])    # LAB
upper_green = np.array([170, 120, 140])
lab = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)
green_mask[90:, :] = cv2.inRange(lab[90:, :, :], lower_green, upper_green)
```

**Análisis.** En LAB de 8 bits de OpenCV: L∈[0,255], a∈[0,255] (128=neutro, **<128 = verde**, >128 = rojo/magenta), b∈[0,255] (128=neutro, <128=azul, >128=amarillo). El verde de los cuadrados de pista (verde saturado) debería tener **a bien por debajo de 128**. Acá:
- **a∈[90,120]** → centrado en ~105, sí es lado verde, pero **se corta en 120** (apenas 8 unidades bajo el neutro) → solo capta verdes **muy** saturados; un verde apenas desaturado por reflejo (a≈122) **se escapa**.
- **L∈[120,170]** → excluye verdes **oscuros** (sombra) y **brillantes** (reflejo del LED). Ventana de luminancia angosta.
- **b∈[100,140]** → cruza el neutro 128, razonable.

El verde gobierna la **detección de giros (intersecciones verdes)** y el **doble verde** (giro de 180°, `green_state=3`) — eventos de **alto puntaje**. Una máscara angosta produce:
- **Falsos negativos:** pierde el marcador verde → no gira donde debe → se sale o sigue derecho. Pérdida directa de puntos.
- El umbral de área (`min_square_size*255`, y `1.35×` para doble verde, Main.py:759/778) está calibrado **contra esta máscara angosta**; al abrir el rango hay que recalibrar áreas.

**Riesgo si NO:** P1. Verde frágil ante el cambio de iluminación de Salta→Incheon (es el "MEDIO" de `analisis-raspberry-pi.md` aplicado a verde, y se conecta con #86 auto-exposure/CLAHE).

**Riesgo si SÍ:** medio. Ampliar la ventana LAB sin recalibrar puede meter ruido (el piso blanco bajo cierta luz puede acercarse al neutro). **Debe** hacerse con calibración in-situ y re-tuneo de áreas. No es un cambio "a ojo".

**Validación:** capturar el cuadrado verde real bajo varias iluminaciones, leer a/b con `calibration.py` (modo LAB ya existe, líneas 19-21/30). Definir rango que cubra el peor caso. Verificar `green_mask` + que `green_state` 1/2/3 siguen disparando bien (banco con cuadrados a izquierda, derecha y doble). Registrar.

---

### V18-06 — [P1] `camthreader` sin Lock: frame stale/desgarrado (ya es #113 / TEMA V-A)

**Ubicación:** `camthreader.py:25-36`.

```python
def update(self):
    while True:
        if self.stopped: return
        (self.grabbed, self.frame) = self.stream.read()   # escribe sin lock
def read(self):
    return self.frame                                      # lee sin lock
```

**Esto ya está cubierto por #113 / TEMA V-A — NO lo reabro.** Agrego solo el matiz que esas auditorías no resaltaron desde la óptica de percepción:

- En **rescate**, `read()` se llama dentro de `read_frame_with_recovery` desde `capture_thread`, que luego mete el frame en `frame_q` y de ahí va a la **inferencia YOLO**. Un frame **a medio escribir** (tearing) no es `None` (el guard de #65 no lo ve) → entra al modelo → **detección sobre imagen corrupta**, justo en el momento de tracking fino de la pelota cerca de la pinza. El `CentroidTracker` puede "saltar" de objeto por un frame basura.
- El fix de #113 (`threading.Lock` en `__init__`, adquirir en `update`/`read`, idealmente devolver **copia** `self.frame.copy()`) resuelve tanto línea como rescate. Solo subrayo que **el costo del `.copy()` en 160×120 es despreciable** y en 256² (rescate) también — no hay excusa de FPS para no hacerlo.

**Validación:** la de #113 (`print(id(frame))` 5 s → sin lock hay IDs repetidos/saltos; con lock+copy, frames consistentes).

---

### V18-07 — [P2] Sin confirmación multi-frame de `silver_line` / `red_line` (NUEVO)

**Ubicación:** `Main.py:794-819` (silver), `804-812` (red).

**Qué.** `silver_line` y `red_line` se evalúan **por frame** y disparan transición de estado **inmediata** (silver→`estado='rescate'`, red→`green_state=10`). Un **solo frame** con un reflejo del piso que supere `area>50` (plata) o `area>25` (rojo) **cambia el estado del robot**. No hay histéresis ni "N frames consecutivos".

**Por qué importa (especialmente con V18-02/V18-04 sin resolver).** El piso de un estadio mundial es brillante y heterogéneo. Combinado con las máscaras frágiles de plata (BGR roto) y rojo (sin wrap), basta **un frame de ruido** para:
- Entrar a rescate en mitad de la recta (falso `silver_line`) → desastre estratégico.
- Disparar `green_state=10` (parada) espurio.

**Riesgo si NO:** P2 hoy, sube a P1 si V18-02/04 quedan frágiles. Transiciones de estado por ruido de 1 frame.

**Riesgo si SÍ:** bajo. Contador de confirmación: `silver_count += 1 if silver_line else reset; entrar a rescate solo si silver_count >= 3`. ~5 líneas por señal. **Trade-off:** agrega ~3 frames (~75–150 ms) de latencia a la detección de entrada — aceptable para la cinta plateada de 25 cm (el robot la ve varios frames). Cuidado de no poner N tan alto que se pierda la cinta a velocidad alta.

**Validación:** pasar el robot por la entrada a velocidad de carrera; confirmar que dispara con N=3 sin perder la cinta, y que el ruido del piso (sin cinta) **nunca** llega a 3 consecutivos. Registrar.

---

### V18-08 — [P2] Exposición / balance de blancos de la cámara NO fijados (NUEVO, complementa #86)

**Ubicación:** `camthreader.py:9-13` (solo se setea W/H; FPS comentado). No se tocan `CAP_PROP_AUTO_EXPOSURE`, `CAP_PROP_EXPOSURE`, `CAP_PROP_AUTO_WB`, `CAP_PROP_WB_TEMPERATURE`, `CAP_PROP_GAIN`.

**Qué.** La cámara USB corre con **auto-exposición y auto-WB del driver UVC activos**. Eso significa que el hardware **cambia el brillo y el balance de color frame a frame** según lo que ve. Encima corre AGCWD (`agcwd`, Main.py:188) y anti-flash, que **vuelven a tocar** el brillo. Tres lazos de control de exposición peleando (auto-exposure HW + AGCWD + anti-flash).

**Consecuencias para percepción:**
- **Umbrales de color inestables:** todos los rangos BGR/HSV/LAB (negro, verde, plata, rojo) asumen una exposición/WB **fija**. Con auto-WB, el mismo objeto cambia de valores entre frames → la calibración hecha en banco **no se sostiene** en pista.
- **Reglamento 2026 (`yolo-raspberry.md:37`):** hay **LEDs blancos** en lo alto de las paredes de la zona. Con auto-exposure, entrar a la zona iluminada por LED hace que el driver **baje la exposición global** → el resto de la imagen se oscurece → negro/verde/plata se rompen. Esto es exactamente lo que motiva #86.

**Riesgo si NO:** P2, pero es **causa raíz de varios P1**. Mientras la cámara auto-ajuste, ninguna calibración de color (V18-02/04/05/10) es estable. Es el "cimiento" del castillo de naipes.

**Riesgo si SÍ:** **medio**, y hay que medirlo. Fijar exposición/WB (`CAP_PROP_AUTO_EXPOSURE=manual`, `CAP_PROP_EXPOSURE=<valor>`, `CAP_PROP_AUTO_WB=0`, `WB_TEMPERATURE` fijo) **estabiliza** la calibración, **pero**: (a) el soporte UVC de estas props **varía por cámara/driver** (la "USB 2MP WIDE 140°" puede ignorar algunas) → hay que verificar cuáles aplican; (b) si se fija una exposición y el estadio es más oscuro/claro de lo previsto, **no se auto-corrige** → hay que elegir el valor **en Songdo/Incheon** durante práctica. Es una mejora de robustez con costo de calibración in-situ.

**Validación (banco + Songdo):** probar `vs.stream.set(cv2.CAP_PROP_AUTO_EXPOSURE, ...)` y leer back con `get()` para confirmar que la cámara lo respeta. Con exposición fija, verificar que los valores HSV/LAB de un objeto **no varían** entre frames (hoy varían). Elegir exposición/WB en la práctica oficial. Registrar en `TEST_LOG.md` + en el "Manual de Calibración" que pide AUDIT-ACTION-PLAN.md §3.

---

### V18-09 — [P2] `calibration.py` muestra frames desincronizados (ya es TEMA V-E / #104)

**Ubicación:** `calibration.py:28-44`.

```python
while True:
    rgb_frame = vs.read()           # frame N (para LAB)
    lab_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2Lab)
    cv2.namedWindow('LAB'); cv2.setMouseCallback('LAB', labclick)   # namedWindow en loop
    rgb_frame = vs.read()           # frame N+1 (pisa el anterior; RGB/HSV de OTRO frame)
    hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)
```

**Esto ya es TEMA V-E (#104) — lo reconfirmo, no lo reabro.** Detalle adicional: hay **dos** `vs.read()` por iteración; el `lab_frame` se calcula del **primer** read y el `rgb_frame`/`hsv_frame` que se muestran son del **segundo**. El operador que doble-clickea para leer un valor LAB está mirando un frame **distinto** al RGB/HSV → **lee coordenadas de color de un objeto que en LAB estaba en otra posición**. Sobre objeto en movimiento, el valor leído es **incorrecto**. Como `calibration.py` es **la herramienta con la que se calibran TODOS los umbrales** (V18-02/04/05/10), un bug acá **contamina toda la calibración**.

**Riesgo si NO:** P2 directo sobre calidad de calibración pre-mundial (dominio de banco de Benjamin).
**Riesgo si SÍ:** muy bajo. Un solo `read()` por iteración, calcular LAB/HSV/RGB del **mismo** frame, sacar `namedWindow`/`setMouseCallback` fuera del `while`. ~4 líneas.
**Validación:** apuntar a objeto en movimiento lento; las 3 ventanas deben mostrar la **misma** escena; el valor leído coincide entre RGB y LAB. Registrar.

---

### V18-10 — [P2 / OPORTUNIDAD] Umbrales hardcodeados sin protocolo de recalibración in-situ (NUEVO — mayor impacto competitivo)

**Ubicación:** `Main.py:68-75` (todos los rangos de color son constantes globales hardcodeadas).

**Qué.** Negro, verde, plata y rojo están **fijos en el código**. Para recalibrar en Incheon hay que **editar `Main.py` a mano** y re-deployar. No hay archivo de calibración externo, ni modo de calibración rápido, ni los valores están versionados con la pista donde se midieron.

**Por qué es la oportunidad de mayor impacto.** El equipo lo sabe (es el "Manual de Calibración en <5 min" de AUDIT-ACTION-PLAN.md §3 y el "MEDIO sensibilidad a iluminación" del análisis de Gemini). En la práctica oficial de Songdo/Incheon **la iluminación y el piso serán distintos** a Salta. **Todos** los bugs de color de arriba (V18-02/04/05) se mitigan masivamente si existe un flujo de recalibración de 5 minutos. Es **prevención sistémica**, no un bug puntual.

**Propuesta (oportunidad, no urgencia):**
- Mover los 8 arrays de umbral a un `calibracion.json`/`.yaml` que `Main.py` cargue al arrancar.
- `calibration.py` que **escriba** ese archivo (hoy solo imprime valores a consola para copiar a mano).
- Versionar `calibracion_salta.json`, `calibracion_songdo.json`, etc., con fecha/iluminación.
- Checklist impreso de 5 min: cinta plateada, cuadrado verde, línea negra, cinta roja → click → guardar → reiniciar.

**Riesgo si NO:** llegás a Incheon con umbrales de Salta y los reescribís a mano bajo presión, con `calibration.py` desincronizado (V18-09). Alto riesgo de calibración apurada y mala.
**Riesgo si SÍ:** bajo técnicamente, **pero** es trabajo (~3–4 h) y toca el arranque de `Main.py` → hay que probar que carga bien y que un JSON faltante no crashea (fallback a defaults hardcodeados). **No hacer esto la semana del freeze sin banco.**
**Validación:** recalibrar la pista de Salta con el flujo nuevo en <5 min; confirmar que los umbrales cargados = los del JSON; correr una vuelta completa. Registrar el tiempo real de recalibración.

---

### V18-11 — [P2] ROIs hardcodeadas acopladas al montaje físico de la cámara (NUEVO)

**Ubicación:** `Main.py:736 (black [:55]), 742 (green [90:]), 746 (cut [62:]), 749 (red [:75]), 751 (silver [:75])`.

**Qué.** Las franjas de imagen donde se busca cada cosa son **constantes de píxel** atadas a 160×120: negro ignora arriba de y=55, verde solo y≥90, rojo/plata solo y≥75, etc. Estas líneas codifican el **horizonte** y la **geometría de montaje** de la cámara (ángulo, altura).

**Por qué importa.** Si la cámara se mueve (golpe, re-montaje, cambio de soporte impreso entre Salta e Incheon — habitual en viaje) o cambia el ángulo, **el horizonte real ya no coincide** con estas constantes. Resultado: el verde se busca donde ya no está el piso, o el negro incluye pared/horizonte. **Silenciosamente** degrada todo. No hay un solo lugar (`HORIZON_Y`) que documente "acá está el horizonte"; está esparcido en 5 magic numbers distintos y **además inconsistentes entre sí** (55 vs 62 vs 75 vs 90).

**Riesgo si NO:** P2. Frágil ante cualquier cambio físico de cámara; difícil de re-ajustar porque son 5 números dispersos sin nombre.
**Riesgo si SÍ:** bajo. Extraer a constantes nombradas (`ROI_HORIZON_Y`, `ROI_GREEN_Y`, `ROI_NEAR_Y`) arriba del loop, documentar qué representa cada una. **No cambia comportamiento**, solo legibilidad/ajustabilidad. Cuidado de no fusionar valores que a propósito son distintos.
**Validación:** revisión + una corrida que confirme comportamiento idéntico. Documentar en el manual de calibración cómo reajustar el horizonte si se mueve la cámara.

---

### V18-12 — [P2] `CLASS_THRESH` de rescate cambió entre versiones sin registro (NUEVO — deuda de proceso)

**Ubicación:** `Main.py:325-330` (productivo) vs `tflite-balance.py:186-191` (legacy).

**Qué.** Comparando las dos versiones del mismo código, los umbrales de confianza por clase **cambiaron sin dejar rastro**:

| Clase | legacy `tflite-balance.py` | productivo `Main.py` |
|---|---|---|
| 0 negro | 0.45 | 0.45 |
| 1 plateado | 0.45 | 0.45 |
| **2 rojo_alto** | **0.2** | **0.5** |
| 3 verde_alto | 0.6 | 0.6 |

Y `STOP_WIDTH_RATIO` 0.20→0.21, `STOP_WIDTH_RATIO_BOX` 0.93→0.98, `CENTER_TOLERANCE_PX` 10→8. **Ningún commit ni TEST_LOG explica por qué.** El de rojo (0.2→0.5) es grande: a 0.5 el modelo necesita **mucha** más confianza para aceptar la zona roja → si el modelo es flojo detectando rojo, ahora la **pierde**. A la inversa, 0.2 aceptaba casi cualquier cosa como roja.

**Por qué importa.** Estos números **son** la calibración del rescate y se tocaron a ojo sin medir. Sin saber con qué dataset/condición se eligió 0.5, no se puede saber si es correcto para Incheon. Es la **deuda de proceso** que AUDIT-ACTION-PLAN.md §3 ("Testing Matrix") busca eliminar.

**Riesgo si NO:** P2. No es un bug per se, pero significa que la calibración de rescate es **opaca**: si en Incheon falla la detección de zona roja, nadie sabrá si es el umbral 0.5, el modelo, o V18-01. Imposible de debuggear ordenadamente.
**Riesgo si SÍ (documentar/validar):** nulo en código. Solo hay que **medir** los umbrales con frames reales de zona y **registrar** el porqué en `TEST_LOG.md`. Idealmente, curva precisión/recall por clase con un puñado de imágenes etiquetadas.
**Validación:** con el modelo real y 10–20 frames de cada zona/pelota, barrer el umbral y elegir el que maximiza recall sin falsos. Anotar en TEST_LOG. **Bloqueado por V18-01** (si el tensor está mal parseado, los `score` no significan nada y este tuneo es inútil — arreglar V18-01 primero).

---

## 3. Cosas que están BIEN (para no romperlas)

Para respetar la regla de oro #4 ("no tocar lo que funciona"), dejo registro de lo que el branch hace bien y **no** hay que tocar:

- **`send_frame()` con `clamp_byte` + `flush()` (Main.py:94-116):** resuelve #66. Correcto. No revertir.
- **`read_frame_with_recovery` (132-147):** maneja `None` de cámara con reintentos + restart del stream (resuelve #65 y parte de R-V01/#108). Bien pensado.
- **Serial con `timeout`/`write_timeout` (67):** resuelve #73.
- **Guard `SHOW_DEBUG_WINDOWS` (12-14) en todos los `imshow`:** resuelve #64. El `cv2.waitKey` también quedó tras el guard.
- **`while ser.in_waiting` con `break` al detectar 0xFF (826-831):** drenado completo del buffer con salida temprana. Resuelve #70/#71 del lado RPi y el comentario lo documenta bien.
- **`handle_control_byte` centralizado (150-177):** una sola fuente de verdad para el parseo de bytes de control (mejor que el legacy que lo tenía inline y duplicado). Buen refactor.
- **Telemetría TX cada 5 s (112-114):** resuelve #75.
- **`infer_thread` AGCWD vectorizado parcial:** OJO, el LUT de `agcwd` **sigue** siendo list-comprehension (198-201) → eso es **TEMA V-D (#104), aún pendiente**, no resuelto.

---

## 4. Cruce con auditorías previas (qué NO repetir)

| Issue previo | Estado en este branch | Acción |
|---|---|---|
| #65 (vs.read None) | **Resuelto** (`read_frame_with_recovery`) | Cerrar si banco OK |
| #64 (imshow sin guard) | **Resuelto** (`SHOW_DEBUG_WINDOWS`) | Cerrar |
| #66 (write sin clamp) | **Resuelto** (`clamp_byte`) | Cerrar |
| #73 (serial sin timeout) | **Resuelto** (timeout=0.05) | Cerrar |
| #113 (camthreader sin Lock) | **Pendiente** | Ver V18-06; sigue abierto |
| #111 (infer_thread sin try/except) | **Pendiente** | **Bloquea diagnóstico de V18-01** |
| #110 (cx_black sin init) | **Pendiente** (Main.py:769-770: `cx_black` solo se asigna si `np.sum(black_mask[90:])`; si hay verde sin negro abajo, `cx_black` indefinido en 778/780) | Confirmo que **sigue vivo** |
| #124 (B7 NMS) | **Pendiente** | Es V18-01 (profundizado) |
| #86 (auto-exposure/CLAHE) | **Pendiente** | Conecta con V18-08/V18-10 |
| TEMA V-D (LUT Python) | **Pendiente** | Sigue en Main.py:198-201 |
| TEMA V-E (calibration desync) | **Pendiente** | Es V18-09 |
| TEMA V-F (`print(area)` hot path) | **Pendiente** | Sigue en Main.py:798 |

> **Confirmo que #110 sigue 100% vivo en este branch:** `cx_black` (Main.py:770) solo se inicializa dentro de `if np.sum(black_mask[90:, :]):`. Si hay un cuadrado verde abajo **sin** línea negra en las filas [90:] (caso real: marcador verde aislado), `cx_black` queda **sin definir** y se usa en las comparaciones de las líneas 778/780/630 → **`NameError` → crash del loop de línea**. Es el crash de 1 línea que Lucio tiene asignado (#110/#116). No es de mi dominio de "percepción de color" pero lo cruzo porque vive en el mismo bloque verde.

---

## 5. Priorización sugerida para el cluster de visión (T–6 semanas, freeze 2026-05-20)

**Orden recomendado (de mayor a menor ratio impacto/riesgo):**

1. **V18-01 (P0)** — medir `out.shape` HOY (10 min, cero riesgo el solo diagnóstico). Es el único que puede invalidar TODO el rescate. Hacer junto a #111 (try/except). **Antes que cualquier otra cosa de rescate.**
2. **V18-02 (P1)** — silver en HSV + recalibrar. Trigger de entrada a zona; sin esto el rescate puede ni empezar. Requiere banco.
3. **V18-08 (P2→habilitador)** — fijar exposición/WB **primero**, porque estabiliza la calibración de 02/04/05. Probar qué props respeta la cámara.
4. **V18-04 + V18-05 (P1)** — rojo con wrap + verde LAB ampliado, **recalibrados in-situ** (no a ojo). Van juntos con el manual de calibración.
5. **V18-06 (P1, =#113)** — Lock + copy en camthreader. Barato, beneficia línea y rescate.
6. **V18-03 (P1, mantenibilidad)** — unificar filtro de depósito + renombrar estados. Hacer **con cuidado** y banco (no tocar green_state 6/7/8/9).
7. **V18-09 (P2, =V-E) + V18-12 (P2)** — arreglar `calibration.py` (habilita buena calibración) y documentar `CLASS_THRESH`.
8. **V18-10 (P2, oportunidad)** — protocolo de recalibración por JSON. **Post-freeze / en Songdo**, no la semana del freeze.
9. **V18-07, V18-11 (P2)** — confirmación multi-frame y ROIs nombradas. Cuando haya aire.

**Regla de "hecho" transversal (CLAUDE.md):** PR vinculado a issue + 1 corrida de banco que lo valide + 1 línea en `testing/TEST_LOG.md`. Varios de estos fixes (V18-02/04/05/08/10) **no se pueden validar sin pista + iluminación representativa** → idealmente cerrar la calibración fina en la **práctica oficial de Songdo/Incheon**, dejando en Salta solo la **infraestructura** (HSV correcto, wrap de rojo, exposición fija, JSON de calibración) lista para recalibrar en 5 minutos.

---

## 6. Riesgo agregado para Incheon (síntesis honesta)

- El **camino de línea** llega en estado **competitivo pero frágil a la iluminación**. Con V18-02/04/05/08 resueltos + recalibración in-situ, debería ser sólido. Sin eso, hay riesgo real de perder marcadores verdes y de un trigger de rescate errático.
- El **camino de rescate** tiene un **riesgo P0 binario sin confirmar (V18-01)**: o el tensor está bien parseado y el rescate anda, o está mal y **el rescate no funciona en absoluto**. **Esto hay que medirlo en las próximas 48 h** — es el mayor riesgo individual de todo el módulo de percepción y condiciona el objetivo de "auto-recuperación 8/10" y el podio. Todo el tuneo de rescate (V18-03/12, thresholds, tracking) es **secundario hasta confirmar V18-01**.
- La **deuda de calibración** (umbrales hardcodeados + `calibration.py` roto + exposición auto) es la **causa raíz transversal**: invertir en V18-08 + V18-09 + V18-10 ahora **multiplica** el valor de cada fix de color individual y reduce el riesgo de "calibración apurada bajo presión" en Corea.

---

*Auditoría de percepción RPi — Claude Code (Opus 4.8) bajo supervisión de @gviollaz. Solo lectura; sin cambios en `software/**`. Findings con riesgo-NO / riesgo-SÍ / tiempo / validación según convención del equipo. Cruzado contra auditorías RESILIENCIA (#108–#113) y CORRECTITUD (#120–#128); no se reabren issues existentes.*
