# Auditoría integral 2026-05-18 — USO DE IA EN EL PROYECTO

**Dominio:** uso de Inteligencia Artificial en el proyecto, en sus **dos acepciones**:
1. **IA de VISIÓN** — el modelo de detección de objetos (YOLOv8 → ONNX/NCNN/TFLite) que corre en la Raspberry Pi durante el rescate: cómo se entrenó, se adaptó y se justifica.
2. **IA como HERRAMIENTA DE DESARROLLO** — cómo se usó IA generativa (Claude Code, Gemini, ChatGPT) para auditar, documentar y dirigir el proyecto.

Para AMBAS se evalúa además la **aceptabilidad ante el reglamento RCJ** y ante el jurado del mundial.

**Archivos leídos (lectura completa):**
- `software/raspberry/AI/best_ncnn_model/metadata.yaml`, `model.ncnn.param`, `model_ncnn.py`
- `software/raspberry/AI/` (árbol completo: modelos `.pt`/`.onnx`/`.tflite`, datasets `.zip`, tutorial PDF)
- `software/raspberry/final_rpi/Main.py` (850 líneas), `requirements.txt`, `README.md`
- `software/raspberry/test/rescue_zone_test/tflite-balance.py`, `warmup.py`
- `docs/es/yolo-raspberry.md`, `docs/es/analisis-arquitectura-robotica.md` (Gemini), `docs/es/informe-coaching-repo.md` (ChatGPT 5.2)
- `AI-INSTRUCTIONS.md`, `AUDIT-ACTION-PLAN.md`, `CONTRIBUTING.md`, `CLAUDE.md`
- `.claude/skills/{rcj-rescue-reviewer,rpi-vision-auditor,teensy-firmware-auditor,rpi-teensy-comms-auditor}/SKILL.md`
- Issues #49, #51 (visión/modelo); `git log --all` (trailers de coautoría IA); `gh pr list` (PRs #3, #15, #16, #20, #21, #56)
- `competition/rules/` (solo `RCJRescueLine2023Rules (2).pdf` + `Reglamento Roboliga 2025.docx`)

**Autor:** auditor de "Uso de IA" (SOLO lectura; no se tocó `software/**` ni `hardware/**`).
**Branch:** `feature/initialize-testing-log` (= `main`, post-PR #101).
**Fecha del corte:** 2026-05-18 (redactado 2026-05-31).

> **Marco de lectura (LEER ANTES).** Cada hallazgo se presenta como **TEMA A ANALIZAR**, no como "tarea obligatoria ni bug a fixear". Para cada uno: qué hay HOY, **riesgo de NO actuar**, **riesgo de actuar**, esfuerzo, y la acción de mayor retorno. La decisión final es del equipo.
>
> **No repite las auditorías previas.** La auditoría de percepción ([`rpi-01-vision.md`](rpi-01-vision.md)) ya cubre los **bugs de código** del pipeline de visión (NMS/formato de tensor V18-01 / #124-B7, `silver_mask` en BGR V18-02 / #B2, clases invertidas V18-03 / #B3, etc.). **Este documento NO los reaudita**: los cita donde corresponde y se enfoca en lo que es propio de su dominio — el **pipeline de entrenamiento**, la **justificación de la elección/adaptación del modelo**, una **sección lista para el TDP**, y la **aceptabilidad reglamentaria del uso de IA**. La auditoría de TDP ([`doc-01-tdp.md`](doc-01-tdp.md)) delega explícitamente en este informe el contenido profundo de "Software – Innovative solutions" (su criterio T13).

---

## 0. Resumen ejecutivo

**Dos diagnósticos en una línea cada uno:**

- **IA de visión:** el modelo es un **YOLOv8n entrenado en Roboflow + Google Colab sobre un dataset propio "Roboliga 2025"** (5.108 imágenes auto-anotadas por el equipo), técnicamente **sólido y 100% defendible ante el jurado** (trabajo original del equipo, no un modelo pre-entrenado de terceros). El problema **no es la legitimidad ni la metodología — es la trazabilidad y la consistencia documental**: no hay en el repo el script de entrenamiento, ni `data.yaml`, ni las métricas (mAP/precision/recall), ni el cuaderno de Colab; conviven **3 generaciones de modelo + 4 formatos** (`.pt`/`.onnx`/`.ncnn`/`.tflite`) sin un "modelo oficial" marcado; y la doc (`yolo-raspberry.md`) **se contradice con el código** (la doc dice "ONNX es el final"; el código corre TFLite). Eso es reconstruible en pocas horas y, bien volcado, vale puntos directos de TDP.

- **IA como herramienta de desarrollo:** el proyecto hace un uso **maduro, transparente y declarado** de IA generativa (Claude Code para auditorías y skills, Gemini y ChatGPT para análisis), con **coautoría firmada en commits**, una regla explícita en `CONTRIBUTING.md` de "declarar uso de IA en cada PR", y supervisión humana nombrada (@gviollaz). **Este es un patrón ejemplar y, salvo un matiz, defendible al 100%.** El único riesgo real es de **encuadre**: hay que tener clarísima la frontera entre "IA que nos ayudó a razonar/documentar/revisar" (totalmente legítimo) y "IA que escribió el código que corre en el robot" (el reglamento exige que el trabajo de ingeniería sea de los estudiantes). Hoy la evidencia muestra que **el código fuente del robot lo escribieron los alumnos** y la IA actuó como auditor/mentor — pero esa distinción tiene que quedar **escrita y honesta en el TDP**, no implícita.

**Aceptabilidad reglamentaria — veredicto corto:** ambos usos son **aceptables** bajo la filosofía RCJ, *siempre que se declaren con honestidad*. El uso de visión por ML está explícitamente premiado ("innovative solutions"). El uso de IA de desarrollo es legítimo como herramienta, igual que un IDE o Stack Overflow, **mientras los estudiantes puedan explicar cada línea ante una entrevista técnica** (el formato de RCJ incluye preguntas del jurado). **El riesgo no es usar IA; es no poder defender lo que la IA produjo.**

> **Heads-up reglamentario (TEMA crítico, ver §7).** El repo **no contiene las reglas RCJ Rescue Line 2026** (solo 2023 + Roboliga 2025). El texto 2026 sobre conducta, originalidad y entrevistas debe leerse del PDF oficial antes de redactar la declaración de IA del TDP. No asumir; verificar la letra.

---

# PARTE 1 — IA DE VISIÓN (el modelo que corre en el robot)

## 1.1 Qué hay exactamente en el repo (inventario forense)

### Modelos (3 generaciones, 4 formatos)

| Fecha (carpeta) | Archivo | Formato | Tamaño | Rol declarado | Estado real |
|---|---|---|---|---|---|
| 11-09 | `AI/11-09/roboliga - copia.pt` | PyTorch (pesos entrenables) | 6,25 MB | Primer modelo de rescate | Histórico |
| 11-09 | `AI/11-09/roboliga.onnx` | ONNX FP32 | 12,2 MB | Primeras pruebas | Histórico |
| 20-11 | `AI/20-11/depositoalto.onnx` | ONNX FP32 | 12,8 MB | Pruebas de zonas de depósito | Histórico |
| 23-11 | `AI/23-11/zonasdepositoalta.onnx` | ONNX FP32 | 12,1 MB | "Modelo usado en Main.py" (según doc) | **Stale**: ver abajo |
| — | `final_rpi/zonasdepositoalta.onnx` | ONNX FP32 | 12,1 MB | Copia junto al main | **Peso muerto** (el main NO lo carga) |
| 2026-03-22 | `AI/best_ncnn_model/` | NCNN (`.param`+`.bin`) | — | Export NCNN | El `.bin` **falta** en el repo (solo `.param`) |
| — | `AI/tfliteNMS_prueba/best_float32 (1).tflite` | TFLite FP32 | — | **Modelo que el robot realmente usa** | **Productivo** (Main.py lo carga) |
| — | `AI/tfliteNMS_prueba/bestflite.tflite` | TFLite | — | Variante de prueba | Histórico |
| — | `AI/tfliteNMS_prueba/dcenet_int8.tflite` | TFLite INT8 | — | Zero-DCE (mejora de imagen, **no es el detector**) | Opcional (apagado) |

**Hallazgo de inventario (V-IA-A, P2 de mantenibilidad):** hay **tres modelos distintos presentados como "el bueno"** según dónde se mire:
- La doc `yolo-raspberry.md` (líneas 87, 102, 160) dice que **`zonasdepositoalta.onnx`** es el modelo final y que "ONNX Runtime dio mejores FPS, por eso el modelo final se exporta a `.onnx`".
- El `metadata.yaml` apunta a un **export NCNN** (`best_ncnn_model`) fechado 2026-03-22, **posterior** a todo lo demás.
- El código real (`Main.py:261`, `tflite-balance.py:118`) carga **`best_float32 (1).tflite`** desde `/home/pi/Downloads/`.

El "modelo oficial" no está marcado en ningún lado y los tres caminos divergen. Esto es deuda de proceso, no un bug que cuelgue el robot — pero ante un juez, "¿cuál es su modelo?" debería tener **una** respuesta.

### Datasets (Roboflow, versionados)

Tres `.zip` exportados de **Roboflow** en formato YOLOv8, cuyos nombres cuentan la historia de la evolución:

| Archivo | Qué revela el nombre |
|---|---|
| `Roboliga 2025.v5-rescate.yolov8.zip` (11-09) | Versión 5 del proyecto Roboflow, foco "rescate" |
| `Roboliga 2025.v12-zonas-alta.yolov8.zip` (20-11) | Versión 12, se agregaron "zonas altas" (esquinas de evacuación) |
| `Roboliga 2025.v15-sinboxes-bajas.yolov8.zip` (23-11) | Versión 15, se removieron "boxes bajas" (zonas bajas) |

**Dato clave:** el proyecto Roboflow se llama **"Roboliga 2025"**, no "RCJ". Esto confirma el origen del modelo (ver §1.3): nació para la liga argentina **Roboliga** y se está **reutilizando/adaptando** para RCJ 2026. No es un problema —las zonas de evacuación de ambos reglamentos son muy parecidas— pero **debe declararse así en el TDP** (es transferencia de un dataset propio, lo cual es legítimo y hasta meritorio, pero presentarlo como "dataset hecho para RCJ" sería inexacto).

### Las 4 clases del modelo productivo

De `metadata.yaml` (autoridad: el export real del modelo):
```yaml
names:
  0: negro        # víctima muerta (esfera negra, no conductora)
  1: plateado     # víctima viva (esfera plateada, reflectiva, conductora)
  2: rojo_alto    # zona de evacuación roja (víctimas muertas) — esquina triangular
  3: verde_alto   # zona de evacuación verde (víctimas vivas) — esquina triangular
imgsz: [256, 256]
task: detect
stride: 32
version: 8.4.24   # Ultralytics
```

> **Evidencia de iteración real (no improvisación):** el script de prueba `warmup.py:187-203` revela una versión **anterior de 6 clases** (incluía `boxgreen`/`boxred` para intersecciones de línea) que después se **colapsó a las 4 clases** de rescate. Es decir, el equipo probó un modelo "todo en uno" (línea + rescate) y deliberadamente lo simplificó a "solo rescate", dejando la línea a visión clásica. Esa decisión de diseño es **contable como innovación/madurez** en el TDP.

### Arquitectura confirmada desde `model.ncnn.param`

Inspección del grafo NCNN (203 capas): entrada `in0` 1×3×256×256 → backbone con `Convolution`+`Swish (SiLU)` (firma inconfundible de YOLOv8) → cabeza de detección con `MemoryData anchor_points` (1344 anchors = grilla 256/8 + 256/16 + 256/32 al cuadrado, decode estándar de Ultralytics), `Slice`/`BinaryOp` de DFL (Distribution Focal Loss), y salida `Concat` tras `Sigmoid`. **Es un YOLOv8n (nano) detector de 4 clases a 256×256.** El sufijo "n" se infiere del tamaño (~6 MB en `.pt`, ~12 MB en ONNX FP32) y del presupuesto de cómputo de una Pi 4B CPU-only.

**Nota técnica relevante para el bug V18-01 de [`rpi-01-vision.md`](rpi-01-vision.md):** `metadata.yaml` dice `end2end: false`. Eso significa que el modelo **NO tiene NMS embebido**; la salida cruda son anchors decodificados sin supresión de duplicados. El código de `Main.py` (`for det in out: x1,y1,x2,y2,score,cls = det`) asume un tensor `[N,6]` ya post-procesado. **Si el TFLite productivo no incluye un `TFLite_Detection_PostProcess` o un export `nms=True`, la detección está rota o entrega duplicados.** Esto es exactamente el #124 (B7) y el V18-01 — no lo reaudito, pero **lo confirmo desde la metadata**: la ausencia de NMS no es hipótesis, está declarada en el `metadata.yaml`.

## 1.2 El pipeline de entrenamiento (reconstruido)

No hay script de training en el repo, pero el pipeline es **reconstruible con alta confianza** cruzando evidencias (`metadata.yaml`, `model_ncnn.py`, nombres de datasets, issues #49/#51, `requirements.txt`):

```
1. CAPTURA      → el equipo graba video/fotos de la pista de evacuación con la propia
                  cámara del robot (USB 2MP WIDE 140°), con pelotas negras/plateadas y
                  esquinas roja/verde, sobre paredes de varios colores.
                  Evidencia: issue #51 ("grabamos con pared naranja fluor, amarilla,
                  marrón claro, blanca..."), videos en software/raspberry/Videos/.

2. ANOTACIÓN    → Roboflow (Annotate). Bounding boxes manuales de las 4 clases.
                  Evidencia: issue #51 ("Roboflow → Annotate", "calidad de los bounding
                  boxes"); tutorial PDF en AI/ "Tutorial de como hacer y descargar un modelo".
                  Crecimiento del dataset: 2.496 → 5.108 imágenes (issue #51).

3. AUGMENT/SPLIT→ Roboflow genera versiones (v5, v12, v15) con augmentations y split
                  train/val/test, y exporta el .zip "YOLOv8".

4. ENTRENAMIENTO→ Google Colab, Ultralytics YOLOv8 (v8.4.24), 256×256, batch 1, FP32.
                  Evidencia DURA: model_ncnn.py:11-12 referencia rutas
                  "/content/runs/detect/train/weights/best_ncnn_model/..." → "/content/"
                  es el sistema de archivos de Colab; "runs/detect/train/weights/best.pt"
                  es la convención exacta de Ultralytics.

5. EXPORT       → del best.pt se exporta a múltiples runtimes para benchmarking en la Pi:
                  ONNX (FP32), NCNN, TFLite (FP32). Evidencia: coexistencia de los 4
                  formatos + el script model_ncnn.py de validación de inferencia NCNN.

6. SELECCIÓN    → se eligió TFLite FP32 para producción (ver §1.4), tras descartar INT8
                  por pérdida de precisión (yolo-raspberry.md:104-121).

7. INTEGRACIÓN  → el .tflite se copia a la Pi (/home/pi/Downloads/) y Main.py lo carga una
                  sola vez al arranque con warmup global (issue #49, Main.py:252-287).
```

**Lo que falta en el repo para que el pipeline sea reproducible (TEMA V-IA-B):** el `data.yaml`, el notebook de Colab (`.ipynb`), las métricas de validación (`results.csv`, curvas PR, matriz de confusión), los hiperparámetros (epochs, lr, augmentations) y la receta de export. Sin esto, **el entrenamiento no es reproducible ni auditable**, y el TDP no puede mostrar "evidencia de QA del modelo" (que la rúbrica 2026 premia en "Software – Reliability Tests").

## 1.3 Justificación de la elección y adaptación del modelo

Esta sección argumenta **por qué las decisiones tomadas son razonables** (para defenderlas ante el jurado) y dónde son discutibles.

**¿Por qué YOLOv8n y no visión clásica para el rescate?**
La línea sí se resuelve con visión clásica (máscaras HSV/LAB, centro de masa) — eficiente y suficiente. Pero las **víctimas y zonas** son objetos 3D con apariencia variable (esferas con brillo especular, esquinas triangulares vistas en perspectiva, sobre fondos de cualquier color). Un detector aprendido generaliza a esa variabilidad mucho mejor que umbrales de color fijos. **Decisión correcta y estándar** en equipos top de Rescue Line.

**¿Por qué "nano" (YOLOv8n)?**
Es el único tamaño que da FPS usable en una **Pi 4B sin acelerador** (CPU-only, confirmado en `yolo-raspberry.md:123-126`). Modelos s/m/l serían más precisos pero correrían a <1 FPS. **Trade-off bien resuelto.**

**¿Por qué 256×256 y no 640?**
640 es el default de YOLO pero a ~3 FPS en NCNN en una Pi 4 (benchmark citado en `yolo-raspberry.md:153`). 256 baja el cómputo ~6× y, para objetos grandes y cercanos como pelotas y esquinas, **256 es defendible**. Riesgo: objetos chicos o lejanos pueden perderse. **Aceptable dado que el robot se acerca antes de decidir** (usa `width_ratio` para "estoy cerca").

**¿Por qué FP32 y no INT8 (cuantización)?**
`yolo-raspberry.md:104-121` documenta que **se intentó INT8 y la precisión empeoró** con el set de calibración disponible, así que se priorizó robustez sobre FPS. **Esta es una decisión madura y bien argumentada** — es exactamente el tipo de trade-off consciente que el jurado valora. (Matiz: con un set de calibración representativo, INT8 podría recuperar FPS sin tanta pérdida; queda como "future work" honesto.)

**¿Por qué la migración de runtime ONNX → TFLite?**
Issue #49 (Benjamin): el overhead de la librería `ultralytics` en Python limitaba a ~3-7 FPS con ONNX; el intérprete **TFLite puro** (sin `ultralytics`) sube a ~14+ FPS con el mismo modelo. **Decisión correcta y medida** (hay tabla comparativa). **PERO genera la contradicción documental V-IA-A**: `yolo-raspberry.md` sigue afirmando "ONNX fue el mejor, por eso es el final" — esa doc quedó **stale** tras la migración de #49 y, si se copia al TDP, contradice el código que el juez puede ver.

**La adaptación clave para RCJ (issue #51) — y por qué es lo más fuerte del trabajo:**
El equipo detectó empíricamente que **con pared naranja fluorescente el robot confundía la pared con la zona roja** y no depositaba bien. La respuesta fue **ampliar el dataset con paredes de muchos colores** (blanca, marrón, naranja, amarillo, y pendientes azul/violeta/gris), citando correctamente que el reglamento permite **paredes de cualquier color excepto rojo/verde/negro/plateado**. Esto es **metodología de ML aplicada de manera ejemplar**: identificar un fallo de distribución (domain gap), no parchearlo en código sino **arreglarlo en los datos**, y validar. **Esta es la historia estrella para "Software – Innovative solutions" del TDP.**

## 1.4 Mejoras de imagen (no son el detector, pero son IA-adyacentes)

El pipeline incluye preprocesamiento que conviene declarar porque también es "IA/algorítmico avanzado":
- **AGCWD** (Adaptive Gamma Correction with Weighting Distribution, `Main.py:188`): realce de contraste adaptativo clásico, siempre activo.
- **Anti-flash** (`Main.py:218`): atenúa reflejos especulares de las pelotas plateadas (que son el peor enemigo de la detección). **Solución propia, no trivial, contable como innovación.**
- **Zero-DCE** (`dcenet_int8.tflite`): red neuronal de *low-light enhancement* (un **segundo modelo de IA**), opcional y **apagado por defecto** (`USE_ZERODCE=False`) porque en Pi 4B baja los FPS. Bien encapsulado tras un switch.

## 1.5 — SECCIÓN LISTA PARA EL TDP (Software → Perception / Machine Learning)

> Redactada para pegar (traducida al inglés) bajo "Software – Innovative solutions" y "Software – Reliability Tests". Es **as-built honesto**: describe lo que el robot hace, marca lo que es "future work", y no inventa métricas. **Reemplazar los `<...>` con los datos reales antes de publicar.**

---

### Victim & Zone Detection — Custom YOLOv8 Model

**Problem.** Inside the evacuation zone, the robot must distinguish silver (alive) and black (dead) victim balls, and locate the red (dead) and green (alive) high-walled deposit corners, against walls that may be **any colour except red/green/black/silver**. Classical colour thresholding fails here: balls have strong specular highlights and the background is unconstrained.

**Approach.** We trained a **custom single-stage object detector (YOLOv8-nano, Ultralytics 8.4.x)** with **4 classes** (`black_victim`, `silver_victim`, `red_zone`, `green_zone`). The model was **entirely built by our team** — we recorded our own footage with the robot's onboard camera, labelled it ourselves in Roboflow, and trained in Google Colab. No third-party pre-trained detection model was used; only the standard YOLOv8 architecture and COCO-pretrained backbone as a starting point for transfer learning.

**Dataset.** `<N>` images self-captured and hand-annotated, grown from 2 496 to **5 108 images** across project iterations. Critically, after observing in bench testing that a **fluorescent-orange wall was being misclassified as the red zone**, we expanded the dataset with walls of many colours (white, light brown, orange, yellow, …) to close the domain gap. Dataset versioning was managed in Roboflow (v5 → v15). *(This is the data-centric fix to a real failure mode — emphasise it.)*

**Model selection & on-device optimisation (Raspberry Pi 4B, CPU-only, no accelerator):**
- Input resolution **256×256** (vs. the 640 default) for ~6× less compute while keeping near/large objects detectable.
- Runtime migrated from **ONNX+Ultralytics (~3–7 FPS)** to a **pure TFLite interpreter (~14+ FPS)** after profiling identified the Python `ultralytics` wrapper as the bottleneck.
- Kept **FP32**: INT8 quantisation was attempted but **degraded accuracy** with our calibration set, so we prioritised reliability over frame rate. *(Honest trade-off.)*
- The model is **loaded once at startup with a warm-up inference**, never inside the rescue hot path, to avoid a multi-second freeze on zone entry.
- Pre-processing: **AGCWD** adaptive contrast + a **custom anti-flash filter** to tame the specular highlights on the silver balls; an optional **Zero-DCE** low-light enhancement network is available but disabled on the Pi 4B for performance.

**Threading.** Capture, inference and serial run in **separate threads** with bounded queues, so camera I/O and UART traffic never stall detection.

**Reliability tests (Software / Perception):** `<fill with REAL numbers from TEST_LOG.md>` — e.g. detection rate per class under stadium-like lighting, FPS measured on the Pi 4B, false-positive rate against coloured walls, and the orange-wall regression check from issue #51. *(Today these numbers do not exist in the repo — see §1.2; producing them is the single highest-value action for this section.)*

**AI tooling disclosure.** See the project-wide AI-usage statement (Part 2 / §6). The detection model and all robot source code were developed by the student team; generative-AI assistants were used for code review, documentation and project management, never to author the competition firmware.

---

> **Por qué esta sección importa:** la rúbrica 2026 da 5-6 pts (vs 3-4) solo si el TDP usa la palabra "innovative" **y lo respalda con evidencia**. Esta sección lo hace — pero **se cae si no se cargan los números reales** de los tests. El texto está; el dato no (ver [`doc-01-tdp.md`](doc-01-tdp.md) §4.4, criterio T14, hoy en 0 pts).

---

# PARTE 2 — IA COMO HERRAMIENTA DE DESARROLLO

## 2.1 Inventario de uso de IA generativa en el proyecto

El proyecto usó **al menos tres asistentes de IA distintos**, todos **declarados explícitamente** en el material:

| Herramienta | Qué produjo | Dónde / evidencia | Declaración |
|---|---|---|---|
| **Gemini** | `docs/es/analisis-arquitectura-robotica.md` (diagrama Mermaid del sistema); `AUDIT-ACTION-PLAN.md` (lista de bugs P0/P1/P2) | Nota de autoría al inicio del doc: *"generado por Ai Gemini a pedido de Gustavo Viollaz"*; AUDIT-ACTION-PLAN: *"detectados por IA Gemini bajo supervisión de Gustavo Viollaz"* | ✅ Nombrada |
| **ChatGPT 5.2 (GPT-5.2 Pro)** | `docs/es/informe-coaching-repo.md` (revisión técnica del repo); reporte consolidado (PR #21) | Header del doc: *"Creado por: AI ChatGPT 5.2 ... A pedido de: Gustavo Viollaz"* | ✅ Nombrada |
| **Claude Code (Opus 4.7 / 4.8)** | Las 4 skills de auditoría en `.claude/skills/`; `CLAUDE.md`; toda la tanda de auditorías de `project/backlog/staging/` (incluido este informe); plantillas | Trailers `Co-Authored-By: Claude Opus 4.7 (1M context)` en múltiples commits; headers de cada doc de staging *"Claude Code (Opus 4.8) bajo supervisión de @gviollaz"* | ✅ Nombrada + coautoría git |

**Y, crucialmente, lo que la IA NO produjo:** el **código fuente del robot**. Los PRs de software (#34 lectura atómica de encoders, #35/#50 visión, #36 punteros, #37/#39 firmware pinzas) son de **Benjamin, Lucio y Laureano**, vinculados a issues, con descripción técnica propia. El historial muestra que **los alumnos escriben el código y la IA lo audita/documenta** — exactamente la frontera correcta (ver §2.4).

## 2.2 El sistema de "vibe reviewing" — las 4 skills de Claude Code

El repo institucionaliza el uso de IA-auditor en `.claude/skills/`:

- **`rcj-rescue-reviewer`** (orquestador): decide qué subsistemas auditar, dispara los 3 auditores en paralelo, deduplica contra `AUDIT-ACTION-PLAN.md` e issues, y **abre Issues** (no toca código).
- **`teensy-firmware-auditor`**, **`rpi-vision-auditor`**, **`rpi-teensy-comms-auditor`**: auditores especializados por subsistema, con catálogos de bugs P0/P1/P2 y formato de salida estandarizado.

**Lo notable (y muy bien diseñado) de estas skills es su autocontención ética**, que es justamente lo que las hace defendibles:
- `rcj-rescue-reviewer` Anti-patterns: *"❌ Escribir el fix vos. **Vos auditás, los alumnos implementan**"*, *"❌ Mergear nada"*, *"❌ Abrir Issue por code smell sin impacto real"*.
- `rpi-vision-auditor` Reglas duras: *"No tocar modelos. Si el modelo es malo, el finding es 'evaluar reentrenamiento', no 'este modelo está mal'"*, *"Si dudás, bajá prioridad"*.
- `teensy-firmware-auditor`: *"No escribas el fix completo, mostrá el patrón. **Los alumnos aprenden implementándolo**"*.

> Este diseño convierte a la IA en **mentor socrático**, no en autor. Es el patrón **más defendible posible** ante un jurado: la IA no hace el trabajo de los chicos, los obliga a hacerlo mejor. **Esto, contado honestamente, es un punto a favor del equipo, no en contra.**

## 2.3 La práctica de declaración (lo que ya está bien hecho)

`CONTRIBUTING.md` (líneas 30, 90-93, 125-132) **exige declarar IA en cada PR**:
```
### Uso de IA (si hay)
- Herramienta: ChatGPT 4
- Se generó el algoritmo de filtrado y luego se ajustó manualmente.
```
y la sección final pide: *"Herramienta usada / Qué parte del código fue asistida / Si se revisó/modificó manualmente"*. `AI-INSTRUCTIONS.md:19` lo repite como regla del repo (*"Declarar uso de IA en los PRs"*).

**Esto es exactamente lo que un jurado de RCJ quiere ver.** La transparencia ya es política del repo, no un gesto aislado. **Fortaleza real — preservarla y citarla en el TDP.**

## 2.4 La frontera que hay que cuidar (el único riesgo serio)

**El riesgo NO es que se haya usado IA. Es de ENCUADRE y de DEFENDIBILIDAD.** Concretamente:

1. **La distinción "razonamiento/docs" vs "código del robot" debe ser explícita.** Hoy un observador externo ve docs de arquitectura firmados por Gemini/ChatGPT/Claude y podría *malinterpretar* que la IA diseñó el robot. La realidad (código de los alumnos, IA como auditor) **es defendible pero está implícita**. El TDP debe afirmarlo en una frase clara (ver §6).

2. **Defendibilidad en la entrevista.** RCJ incluye entrevistas técnicas del jurado. Si un alumno no puede explicar **por qué** el PID está sintonizado así, **por qué** se eligió TFLite, o **cómo** funciona el `CentroidTracker`, el uso de IA se vuelve un pasivo. **No porque esté prohibido, sino porque expone que el conocimiento no se internalizó.** La mitigación es de proceso: cada alumno debe poder defender su subsistema **sin la IA presente**. Las skills (que fuerzan "los alumnos implementan") ayudan, pero hay que **verificarlo** antes de Incheon.

3. **Docs de IA desactualizados que contradicen el código** (ya señalado por la auditoría de rúbricas, `docs/es/analisis-documentacion-rubricas-2026-05-10.md:488-495`, y por [`doc-01-tdp.md`](doc-01-tdp.md) §5 Acción 6). Ejemplos: `AUDIT-ACTION-PLAN.md` (Gemini) lista como P0 vigente *"YOLO se carga cada vez en rescate"* y *"encoders sin volatile"* — **ambos ya fixeados** (#34, #49). Si ese texto generado por IA se copia al TDP, **el robot real contradice el paper** → resta credibilidad. La IA generó análisis correctos *en su momento*; quedaron stale. **Hay que validar fidelidad antes de volcar.**

4. **Material aspiracional generado por IA presentado como as-built.** `hardware/mechanics/traction-optimization/README.md` (Gemini) describe ruedas de silicona moldeadas, suspensión rocker-bogie y ajuste activo de CG — que el robot **probablemente no tiene**. Como "future plans" es legítimo; como descripción actual, un juez lo detecta en la mesa. (Detalle en [`doc-01-tdp.md`](doc-01-tdp.md) §2.2 y `hw-02-evaluacion-critica.md`.)

---

# PARTE 3 — ACEPTABILIDAD REGLAMENTARIA (RCJ)

## §5. IA de visión ante el reglamento

**Veredicto: plenamente aceptable, y premiado.**
- RCJ Rescue Line **no prohíbe** el aprendizaje automático; al contrario, el TDP premia "innovative solutions" y la detección por ML de víctimas/zonas es de las innovaciones mejor vistas.
- El requisito implícito es de **autoría**: el modelo y los datos deben ser **trabajo del equipo**. Aquí se cumple sobradamente (dataset propio auto-anotado, entrenamiento propio en Colab). **No hay uso de modelos pre-entrenados de terceros para la tarea específica** (usar la arquitectura YOLOv8 y un backbone COCO como punto de partida de transfer learning es estándar y aceptado — eso es como usar una librería, no como copiar la solución).
- **Cómo declararlo honestamente en el TDP:** "modelo entrenado por el equipo sobre dataset propio; arquitectura YOLOv8 estándar; backbone pre-entrenado COCO como inicialización de transfer learning". Esa frase es precisa y defendible.
- **Lo que NO se debe hacer:** presentar el dataset "Roboliga 2025" como "creado para RCJ" (es reúso legítimo, decláralo como tal), ni mostrar métricas inventadas. Si no hay mAP medido, decir "evaluación cualitativa en banco" es preferible a un número falso.

## §6. IA de desarrollo ante el reglamento

**Veredicto: aceptable como herramienta, con la condición de defendibilidad.**

Marco mental correcto: **la IA generativa es una herramienta, equivalente a un IDE, un linter, Stack Overflow o un libro.** RCJ no prohíbe herramientas; evalúa si los **estudiantes** son los ingenieros y si **entienden** su robot. Patrones:

**Defendibles ante el jurado (lo que el equipo hace):**
- IA como **auditor/revisor** que abre issues y el alumno implementa (las 4 skills). ✅
- IA como **redactor asistido** de documentación que el equipo revisa y corrige. ✅
- IA como **tutor** que explica conceptos. ✅
- **Declaración explícita** de qué herramienta se usó y para qué (ya en CONTRIBUTING). ✅

**NO defendibles (lo que el equipo debe evitar / verificar que no ocurre):**
- IA que **escribe el firmware/visión** y el alumno solo lo pega sin entenderlo. ❌ (No hay evidencia de esto; los PRs de código son de alumnos — pero verificar defendibilidad en entrevista.)
- TDP **redactado íntegramente por IA** y presentado como propio sin revisión ni comprensión. ❌ (Riesgo latente: gran parte del material de `docs/` es generado por IA; el TDP final debe ser **reescrito y comprendido por el equipo**, no un copy-paste.)
- Métricas/diagramas **alucinados** por IA que no reflejan el robot real. ❌ (Riesgo concreto, ver §2.4 puntos 3-4.)

**Declaración de IA recomendada para el TDP (borrador, conservador y honesto) — pegar en una nota al pie o sección de metodología:**

> *"AI tooling disclosure. During development we used generative-AI assistants (Claude Code, Google Gemini, OpenAI ChatGPT) for **code review, documentation drafting, and project management** — for example, automated code audits that flagged issues for us to fix, and first drafts of analysis documents that we then reviewed and corrected. **All robot source code (Teensy firmware and Raspberry Pi vision) and the detection model were designed and implemented by the student team.** Generative AI was not used to author the competition code. Every team member can explain the subsystem they are responsible for."*

Ajustar a la **verdad literal** del equipo y a la **letra de las reglas 2026** (ver §7). Si alguna línea de código sí salió de IA, decirlo — la honestidad parcial es peor que la total.

## §7. TEMA crítico — verificar la letra de las reglas 2026

**El repo no tiene las reglas RCJ Rescue Line 2026.** `competition/rules/` solo contiene `RCJRescueLine2023Rules (2).pdf` y `Reglamento Roboliga 2025.docx`. Antes de redactar la declaración de IA del TDP **hay que leer el texto 2026 oficial** sobre:
- Código de conducta / originalidad del trabajo.
- Qué se considera "trabajo del equipo".
- Formato y peso de la **entrevista técnica** del jurado.
- Cualquier cláusula nueva sobre uso de herramientas externas o IA (varias ligas RoboCup la están agregando; verificar si Rescue Line 2026 la incluye).

- **Riesgo de NO actuar:** medio. La filosofía RCJ es estable y el uso actual es conservador, pero redactar la declaración "a ojo" sin la letra 2026 es evitable.
- **Riesgo de actuar:** nulo (leer un PDF).
- **Esfuerzo:** 30 min. Descargar `RCJRescueLine2026-final.pdf` a `competition/rules/`. (Acción ya recomendada por [`doc-01-tdp.md`](doc-01-tdp.md) §5 Acción 4 por otras razones — aprovechar.)

---

# PARTE 4 — TEMAS A ANALIZAR (consolidado, con riesgo/esfuerzo)

> Formato del equipo: cada tema lleva riesgo-si-NO / riesgo-si-SÍ / esfuerzo / acción.

| ID | Tema | Riesgo si NO se actúa | Riesgo si SÍ se actúa | Esfuerzo | Prioridad |
|---|---|---|---|---|---|
| **V-IA-A** | Doc `yolo-raspberry.md` stale (dice ONNX final; corre TFLite) + 3 "modelos oficiales" divergentes | Contradicción con el código visible al jurado → resta en TDP/Clarity | Bajo (solo actualizar doc + marcar EL modelo) | ~1 h | Media |
| **V-IA-B** | No hay `data.yaml`, notebook Colab, ni métricas (mAP/PR/confusión) del modelo en el repo | "Software – Reliability Tests" del modelo vale 0; entrenamiento no reproducible | Bajo (subir artefactos ya existentes en Drive/Colab) | ~2 h | **Alta** |
| **V-IA-C** | Confirmar NMS en el TFLite productivo (`end2end:false` en metadata) | Si falta NMS, la detección de víctimas está rota/duplicada (= #124/V18-01) | — (ya cubierto por rpi-01-vision; aquí solo se confirma desde metadata) | ver V18-01 | **Alta** (delegado) |
| **V-IA-D** | Limpiar pesos muertos: `final_rpi/zonasdepositoalta.onnx` no se usa; falta `model.ncnn.bin`; modelos en `/home/pi/Downloads/` fuera del repo | Confusión sobre qué modelo es el real; modelo productivo no versionado | Bajo (mover el `.tflite` productivo al repo o a LFS; borrar copia muerta) | ~1 h | Media |
| **IA-DEV-A** | Frontera "IA-docs vs código-de-alumnos" no afirmada explícitamente | Malinterpretación de autoría por el jurado | Nulo (una frase en el TDP — borrador en §6) | 15 min | **Alta** |
| **IA-DEV-B** | Verificar defendibilidad: cada alumno explica su subsistema sin IA | Uso de IA se vuelve pasivo en la entrevista | Medio (ensayo de entrevista) | 2-3 h | **Alta** |
| **IA-DEV-C** | Validar fidelidad de docs generados por IA antes de volcar al TDP (bugs ya fixeados, hardware aspiracional) | TDP contradice el robot real → pierde credibilidad | Medio (revisión técnica) | 2-3 h | **Alta** (ya en doc-01 §5 Acción 6) |
| **IA-DEV-D** | Falta el texto reglamentario 2026 en el repo para redactar la declaración de IA | Declaración redactada sin base normativa | Nulo (descargar PDF) | 30 min | Media |
| **IA-DEV-E** | El TDP final debe ser reescrito/comprendido por el equipo, no copy-paste de docs IA | "TDP escrito por IA" sin comprensión = no defendible | Alto (es escribir el TDP) | ver doc-01 | **Alta** |

---

## Cierre — el mensaje en una línea

El equipo usa IA de **dos** maneras y **ambas son defendibles**: un **modelo de visión propio** (dataset auto-anotado, entrenamiento propio, decisiones de ingeniería bien argumentadas) y un **sistema de auditoría asistida por IA** transparente y declarado, donde **los alumnos escriben el código y la IA los hace razonar mejor**. El riesgo no está en *haber usado* IA — está en **no dejar por escrito, con honestidad, dónde termina la ayuda de la IA y empieza el trabajo del equipo**, y en **no poder defender en la entrevista lo que se produjo**. Las dos acciones de mayor retorno son baratísimas: (1) subir al repo los artefactos de entrenamiento y las métricas reales del modelo (hoy invisibles, viven en Colab/Drive), y (2) escribir en el TDP la frase de §6 que afirma la autoría del equipo. Lo demás —limpiar modelos duplicados, actualizar la doc stale, ensayar la entrevista— es higiene que multiplica la credibilidad del paper sin tocar una línea del robot.

---

*Auditoría de "Uso de IA" dirigida por @gviollaz, asistida por Claude Code (Opus 4.8, 1M context). SOLO lectura — no se modificó `software/**` ni `hardware/**`. Fuentes: artefactos de `software/raspberry/AI/`, `Main.py`, issues #49/#51, `.claude/skills/`, `AUDIT-ACTION-PLAN.md`, `CONTRIBUTING.md`, historial git de coautoría IA, y reglas en `competition/rules/`. No repite la auditoría de percepción ([`rpi-01-vision.md`](rpi-01-vision.md)) ni la de TDP ([`doc-01-tdp.md`](doc-01-tdp.md)): las cita y agrega su dominio propio. Filosofía: TEMAS A ANALIZAR — el equipo decide; el auditor presenta material, riesgo y la frontera ética con honestidad conservadora.*
