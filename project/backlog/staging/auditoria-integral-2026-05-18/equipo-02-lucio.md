# Auditoría Integral 2026 — Desempeño de Lucio Saucedo (@luciouriel2011)

**Dominio asignado:** Raspberry Pi 4B — Visión (OpenCV + YOLO)
**Fecha del informe:** 2026-05-18 (corrida 2026-05-31)
**Repo:** `rcj-2026-rescue-line-iita-salta-robocup` · branch `feature/initialize-testing-log` (contenido = `main` post-PR #101)
**Metodología:** minería de `git log --all` (filtros `lucio`, `luciouriel`, `Saucedo`), `git blame` línea por línea sobre los archivos vivos, `gh pr/issue list`, lectura completa de cada commit autorado. Sólo lectura. Números 100% verificables, no inventados.

---

## 0. TL;DR (lectura honesta y cruda)

Lucio figura en la arquitectura del equipo como **el responsable de visión en la Raspberry Pi**. Los datos duros dicen otra cosa: **Lucio no escribió, en la práctica, código de visión que haya sobrevivido**. El pipeline de visión que hoy corre (`Main.py`, `camthreader.py`, `calibration.py`, los modelos YOLO/NCNN/TFLite y todos los scripts de `rescue_zone_test/`) fue migrado por Gustavo y desarrollado por **Benjamín Villagrán**. La contribución técnica más sólida de Lucio en todo el repo es un **fix de firmware en C++** (comparación de punteros en `drivebase.cpp`) — bueno, pero fuera de su dominio. El resto es: un pase de comentarios autogenerados (PR #42, sigue **abierto sin mergear** desde marzo), un TDP en inglés (deliverable real y valioso, pero **varado en una rama sin mergear** y con errores de hecho), y una línea en el README.

**Esto NO es necesariamente "Lucio no trabajó".** Es un **TEMA A ANALIZAR de rol y de proceso**: o el reparto de responsabilidades no refleja la realidad (Benjamín absorbió visión + hardware + banco), o Lucio trabajó offline/sin commitear, o se desconectó. A 6 semanas del mundial (Incheon, 2026-06-30), el "dueño de visión" con cero líneas vivas de visión es un **riesgo de bus-factor y de cobertura** que hay que mirar de frente. Su última actividad es del **2026-04-25** — más de un mes de silencio.

---

## 1. Inventario de commits (dato duro)

Total de commits autorados por Lucio en **todas las ramas**, excluyendo merges: **5**. (Con el merge `e0616e5` serían 6, pero un merge no es trabajo original.)

| # | Hash | Fecha | Mensaje | Naturaleza real |
|---|------|-------|---------|-----------------|
| 1 | `a8241e2` | 2026-03-07 | `fix(teensy): cambio de comparacion de punteros` | **Fix real de C++** (firmware, NO visión). Mergeado (PR #36). |
| 2 | `848f142` | 2026-03-14 | `Update README with Teensy loader download link` | 1 línea en README. Trivial pero sobrevive en `main`. |
| 3 | `e0616e5` | 2026-03-14 | `fix(firmware):solve conflicts` | **Merge commit** (2 padres). No es autoría original. |
| 4 | `795cc8e` | 2026-03-16 | `docs/comentarios en codigos` | Pase de comentarios (PR #42, **abierto sin mergear**). Sobreescrito en visión. |
| 5 | `19f6055` | 2026-03-23 | `docs(tdp): base de tdp` | Base del TDP + `consumo.md`. **Varado en rama sin mergear.** |
| 6 | `53657fb` | 2026-04-25 | `feat(docs): agregue mas imagenes al TDP` | 3 imágenes + edición menor del TDP. **Misma rama sin mergear.** |

**Contexto de volumen (commits no-merge, todas las ramas):**
gviollaz 27 · benjaminvillagran 23 · IITA-robotica 9 · "Gustavo Viollaz - IITA" 7 · Laureano 6 · **lucio 5** · Enzo 3 · "Benjamin Villagran" 3.

Lucio es el de **menor volumen entre los tres alumnos** (Laureano 6, Benjamín 23+3=26). El volumen por sí solo no condena — pero combinado con el *contenido* (abajo) sí pinta un patrón.

**GitHub:**
- **PRs autorados:** 2 → #36 (`comparacion_de_punteros_res`, **MERGED**), #42 (`documentation_and_diagrams`, **OPEN** desde 2026-03-16).
- **Issues abiertos:** **0**.
- **PRs de compañeros revisados por Lucio:** **0**. No participó del code-review del equipo.

---

## 2. El hallazgo central: cero líneas vivas de visión

Esto es lo más importante del informe. Hice `git blame` línea por línea sobre la versión **actual** de cada archivo de visión y conté autores:

| Archivo (versión actual) | benjaminvillagran | Gustavo Viollaz | **Lucio** |
|---|---:|---:|---:|
| `final_rpi/Main.py` | 537 | 312 | **0** |
| `final_rpi/camthreader.py` | 0 | 43 | **0** |
| `final_rpi/calibration.py` | 0 | 50 | **0** |
| `test/rescue_zone_test/rescatemodelonos.py` | 0 | 450 | **0** |
| `test/rescue_zone_test/tfmodelprueba.py` | 0 | 524 | **0** |
| `test/rescue_zone_test/warmup.py` | 485 | 0 | **0** |
| `test/annotator.py` | 0 | 49 | **0** |
| `test/prueba_send_serial.py` | 0 | 12 | **0** |

**Lucio tiene 0 líneas sobrevivientes en TODOS los archivos de visión.**

¿Por qué? Porque su único toque sobre visión fue el commit `795cc8e` ("comentarios en codigos"), y ese pase **agregó comentarios sin tocar la lógica**. Luego Benjamín reescribió `Main.py` por completo en una cadena de commits (`86dca44` "main con velocidad de inferencia mayor y autobalanceador de blancos", `6f82c5f`/`2894ded` heartbeating, `97fc5cd` latencia primera inferencia, `ec06758`, `d0246d5`), y `camthreader.py` también lo retocó Benjamín. Los comentarios de Lucio **murieron en el rebase de la realidad**.

La historia de autoría de `Main.py` lo deja explícito (commits que tocaron el archivo, más nuevos primero):
`d0246d5 Benjamín → ec06758 Benjamín → 5bac4a5 Benjamín → 430e01e Benjamín → 2894ded Benjamín → 6f82c5f Benjamín → ba25f4f Benjamín → 86dca44 Benjamín → 795cc8e **Lucio (solo comentarios)** → 97fc5cd Benjamín → 3ddc89d Gustavo (migración legacy)`.

Y el directorio de **modelos de IA** (`software/raspberry/AI/`, que es *literalmente* el corazón del dominio de visión de Lucio — entrenamiento YOLO, export NCNN/TFLite):
`430e01e Benjamín → 0311bf1 Benjamín (feat(vision): modelo con ncnn) → 64f7c0f Benjamín (feat(vision): integración TFLite + AGCWD/Zero-DCE) → 3ddc89d Gustavo`. **Cero Lucio.**

> **TEMA A ANALIZAR #L1 — Desalineación rol↔realidad en visión.**
> **Riesgo si NO se actúa:** el "dueño de visión" no conoce el código de visión en profundidad (no lo escribió). Si Benjamín falla/se enferma/se satura en Incheon, no hay redundancia humana sobre el subsistema más crítico para el puntaje (línea, víctimas, zonas). Bus-factor = 1 sobre visión.
> **Riesgo si se actúa (reasignar o forzar ownership real):** fricción social, posible desmotivación de Lucio, y costo de onboarding tardío a 6 semanas del mundial (el peor momento para mover responsabilidades).
> **Tiempo de mitigación mínima:** 4–6 h de pairing dirigido Benjamín→Lucio sobre `Main.py` + corrida del banco, repetido 2–3 veces antes de viajar. No para que Lucio "reescriba", sino para garantizar **dos personas capaces de debuggear visión en pista**.

---

## 3. Lo bueno: el fix de punteros (`a8241e2`, PR #36)

Hay que reconocerlo: **este es un buen fix y es técnicamente correcto.** En `drivebase.cpp`, el código comparaba el ID de motor así:

```cpp
if (this->id == "FL" || this->id == "BL" )   // ANTES: compara PUNTEROS, no strings
```

Lucio lo corrigió a:

```cpp
#include <string.h>
...
if (this->id != NULL && (strcmp(this->id, "FL") == 0 || strcmp(this->id, "BL") == 0))  // DESPUES: correcto
```

Esto es exactamente el bug clase "comparación de `const char*` con `==`" que marca el auditor de firmware Teensy: con `==` se compara la dirección del puntero, no el contenido; funciona "por casualidad" si el compilador deduplica literales, pero es undefined behavior y puede romper la cuenta de pulsos de encoder (que define el `_dir` y por ende la odometría → directamente ligado a **#B10 encoder sin calibrar** de la auditoría de correctitud). Además agregó el guard `!= NULL`. **Trabajo limpio.**

**El asterisco:** es el **único commit de Lucio que tocó lógica real**, y está **fuera de su dominio** (firmware = Laureano). Sugiere que Lucio *puede* programar y razonar bugs, pero su energía no fue a visión. Esto refuerza #L1: la capacidad existe, la aplicación al rol no.

---

## 4. El pase de comentarios (`795cc8e` / PR #42): bien intencionado, mal terminado, y sospechoso de IA

**Qué hizo:** PR #42 toca **32 archivos**, +2654/−1557 líneas, agregando comentarios a Main.py, calibration, camthreader, los scripts de test de visión y ~12 archivos de firmware Teensy.

**Problema 1 — Es casi-seguramente autogenerado.** El estilo es banners ASCII (`####...`) con secciones en inglés y comentarios línea-a-línea tipo *"# OpenCV: image processing, feature extraction, drawing and tracking."* sobre cada `import`. Las líneas de lógica subyacente **no cambian** — solo se anotan. Es el patrón típico de "pasar el archivo por un LLM y pedirle comentarios". No es malo per se (documentar está bien), pero **no es desarrollo** y no demuestra comprensión propia del código.

**Problema 2 — Las deleciones gigantes son engañosas.** El `--stat` muestra `-596` en `rescatemodelonos.py`, `-678` en `tfmodelprueba.py`, `-607` en `warmup.py`. Eso **no es código que Lucio escribió y borró**: es el efecto de reformatear/recomentar archivos que ya existían. No hay creación neta de funcionalidad.

**Problema 3 — Nunca se cerró.** El PR sigue **OPEN desde 2026-03-16** (>2.5 meses). Enzo (coach) comentó el 2026-04-29: *"este me sale que entra en conflictos, el estándar de comentarios que propones está bueno, solo faltaría agregarlo en las líneas adicionales después de agregar las últimas PR"*. **Lucio no respondió ni rebaseó.** Resultado: 2654 líneas de comentarios que (a) ya conflictúan con `main` y (b) nunca van a entrar como están. **Trabajo desperdiciado por falta de seguimiento.**

> **TEMA A ANALIZAR #L2 — PRs abandonados / falta de cierre.**
> **Riesgo si NO se actúa:** se normaliza dejar PRs colgados; el estándar de comentarios (que el coach valoró) se pierde; ruido de ramas muertas antes del freeze de competencia.
> **Riesgo si se actúa (cerrar/rehacer):** rebasear un PR de 32 archivos contra el `main` actual es trabajo no-trivial y de bajo valor a esta altura.
> **Tiempo:** decisión 10 min (cerrar PR #42 como "no se mergea, estándar adoptado a futuro") + opcional 2–3 h si se quiere portar el estándar de comentarios solo a los archivos de visión vivos. **Recomendación: cerrar y no reabrir antes del mundial.**

---

## 5. El TDP (`19f6055` + `53657fb`, rama `documentation_and_diagrams`): el aporte más valioso, pero varado

**Lo que sí construyó Lucio y tiene valor real:** el **Team Description Paper** (`TDP/TDP.md`, 411 líneas) más imágenes (`equipo.jpg`, `pcb.png`, `robotfull.jpg`, `deposit.jpg`, `Led_high/Low.jpg`, `batery.jpg`) y un `hardware/electronics/power-tree/consumo.md` (116 líneas de tabla de consumo).

El TDP es un **deliverable obligatorio y evaluado** en RoboCupJunior, así que esto cuenta. Y está **bien estructurado**: cubre las 15 secciones del rubro (Project Planning, Mechanical, Electronic, Sensors, Software Architecture, Vision and AI, Motion and Control, Rescue Strategy, Testing, Problems and Solutions, Innovation, Future Work, Conclusion, Acknowledgements). La prosa es competente y *no* suena a relleno: describe correctamente la arquitectura de dos computadoras, YOLO entrenado con **+2500 imágenes**, deposición selectiva, etc. Esto es trabajo de redacción técnica genuino y útil.

**Pero hay tres problemas serios:**

**(a) Está varado en una rama sin mergear.** `TDP/TDP.md` y `consumo.md` **NO existen en `main`** — viven sólo en `origin/documentation_and_diagrams` (la misma rama del PR #42). Verificado: `git ls-tree main | grep TDP` y `grep consumo` → vacío. Un deliverable de competencia que no está en la rama principal es un deliverable en riesgo de perderse.

**(b) Error de hecho que un juez puede penalizar.** El TDP dice **"Raspberry Pi 5"** en el Abstract y en la sección 7 ("The Raspberry Pi 5 uses Python, OpenCV, and YOLO..."). El hardware real del equipo es **Raspberry Pi 4B**. Un TDP que describe mal su propio hardware le resta credibilidad ante los jueces y contradice el resto de la documentación.

**(c) Está en inglés** mientras buena parte del repo/comentarios del equipo está en español. No es un error (el TDP de RoboCup *se entrega en inglés*), pero implica que **nadie más del equipo lo revisó técnicamente** (de ahí que el error "RPi 5" haya pasado). Sin review, los datos finos quedan sin verificar.

> **TEMA A ANALIZAR #L3 — TDP valioso pero sin mergear, sin review y con error de hardware.**
> **Riesgo si NO se actúa:** el equipo llega a Incheon sin TDP en `main`, o con un TDP que dice "RPi 5". Penalización de documentación / pérdida de puntos blandos. El TDP es de los pocos entregables 100% bajo control del equipo — perderlo por proceso sería evitable.
> **Riesgo si se actúa:** mergear `documentation_and_diagrams` arrastra también el pase de comentarios conflictivo (#L2) → hay que separar el TDP del resto antes de mergear (cherry-pick de `TDP/` y `consumo.md`).
> **Tiempo:** 1–2 h para cherry-pickear TDP+imágenes+consumo a una rama limpia y mergear a `main`; +1 h para que Benjamín/Laureano revisen los datos técnicos (corregir "RPi 5"→"RPi 4B", verificar sensores listados, consumo real). **Alta prioridad: es puntos de competencia casi gratis.**

---

## 6. Línea de tiempo de actividad (señal de desconexión)

Commits no-merge de Lucio, ordenados:

```
2026-03-07  fix(teensy) punteros        <- pico técnico
2026-03-14  README link
2026-03-16  comentarios (PR #42)
2026-03-23  base TDP
2026-04-25  +imágenes TDP               <- ULTIMA actividad
```

**Toda la actividad real de Lucio se concentra entre el 7 y el 23 de marzo** (una ventana de ~2 semanas), con una sola reaparición el 25 de abril para sumar imágenes. **Desde 2026-04-25 no hay ningún commit, PR, ni review de Lucio.** Estamos a 2026-05-31 → **más de un mes de silencio**, entrando en la recta final hacia el mundial (30-jun).

Compárese: Benjamín tiene commits de visión hasta el 20-24 de mayo (`ec06758`, `d0246d5`). El equipo está activo; Lucio no aparece en ese tramo.

> **TEMA A ANALIZAR #L4 — Desconexión sostenida (>1 mes) del miembro de visión.**
> **Riesgo si NO se actúa:** se llega a Incheon con un integrante desacoplado del estado real del robot. En pista, cada persona del equipo necesita poder operar/debuggear *algo*; un miembro que no tocó el código en 2 meses es peso muerto operativo (y un problema de equipo/moral, no solo técnico).
> **Riesgo si se actúa (confrontar / reasignar):** es una conversación de liderazgo delicada con un alumno; mal manejada desmotiva. Requiere al coach (Enzo) y al director (Gustavo), no es un "issue de GitHub".
> **Tiempo:** conversación 1:1 (30–45 min) + plan de reincorporación con tareas concretas y acotadas (ver §7). **No es deuda de código, es deuda de equipo.**

---

## 7. Síntesis honesta y recomendaciones

**Qué hizo Lucio, sin maquillaje:**
- 1 fix de firmware C++ real y correcto (punteros, PR #36 mergeado) — **fuera de su dominio**.
- 1 TDP completo y de buena calidad redaccional (varado sin mergear, con error "RPi 5").
- 1 `consumo.md` (varado sin mergear).
- 1 pase de comentarios autogenerados (PR #42 abierto, sobreescrito en visión, abandonado tras feedback del coach).
- 1 línea en README.
- **0 líneas vivas de código de visión** (su dominio asignado).
- **0 issues abiertos, 0 reviews de PRs de compañeros.**
- Activo ~2 semanas (marzo) + 1 día (25-abr). Silencio desde entonces.

**Lo que esto NO dice:** no dice que Lucio sea incapaz — el fix de punteros prueba que razona bugs y escribe C++ correcto. Tampoco dice con certeza *por qué* no trabajó en visión (puede haber trabajado offline sin commitear, puede haber un reparto informal donde Benjamín tomó visión, puede haber desmotivación). El git **no muestra intención, muestra resultado**. El resultado es: el dueño nominal de visión no tiene huella en visión.

**Lo que SÍ dice, y es accionable:**
1. **Cobertura/bus-factor de visión = 1 (Benjamín).** Inaceptable para el subsistema que más puntúa, a 6 semanas del mundial. → Pairing dirigido Benjamín→Lucio sobre `Main.py` + banco (#L1).
2. **El TDP es puntos casi gratis y está por perderse.** Cherry-pick a `main`, corregir "RPi 5"→"RPi 4B", review técnico (#L3). **La acción de mayor ROI sobre el trabajo de Lucio.**
3. **Cerrar PR #42** y no arrastrar conflictos (#L2).
4. **Conversación de reincorporación** liderada por Enzo/Gustavo con tareas acotadas y verificables, p.ej.: dueño de la **calibración de color en sede** (HSV plata + verde Lab, que se rompe con la luz de Incheon → liga con #B2 silver_mask en BGR y los tests de iluminación del TDP §10), y dueño del **banco de pruebas de visión** junto a Benjamín. Tareas chicas, medibles, con commit al final (#L4).

**Veredicto de desempeño (honesto):** **por debajo de lo esperado para el rol asignado.** No por incapacidad (el fix de punteros y el TDP demuestran competencia), sino por **aplicación fuera de dominio + falta de continuidad + entregables sin cerrar**. El mayor valor que dejó (el TDP) corre riesgo de perderse por un problema de proceso, no de talento. La prioridad del coach con Lucio no debería ser "que escriba más código", sino **(a) rescatar y mergear su TDP, (b) garantizar que sea la segunda persona capaz de operar visión en pista, y (c) reconectarlo con tareas concretas antes de viajar.**

---

## 8. Cruce con auditorías previas (no se repiten, se citan)

- **#B10 (encoder sin calibrar)** y **#B1 (PID invertido)**: el fix de punteros de Lucio (`a8241e2`) toca la cuenta de pulsos de encoder en `drivebase.cpp`, que alimenta la odometría → relacionado con la confiabilidad del encoder. Su fix *mejora* la corrección, no la empeora; pero la calibración numérica del encoder (#B10) sigue pendiente y NO es de Lucio.
- **#B2 (silver_mask en BGR)** y los **tests de iluminación** descritos en el TDP §10: el TDP de Lucio documenta el problema de sensibilidad a la luz como "Problem 1", lo cual es correcto y útil — pero la *solución* en código (AGCWD/Zero-DCE, autobalance de blancos) la implementó **Benjamín** (`64f7c0f`, `86dca44`), no Lucio. El TDP describe trabajo ajeno como propio del equipo (correcto a nivel equipo, pero refuerza que Lucio documenta visión sin haberla codeado).
- Las auditorías de **RESILIENCIA** (#53/#27/#57-#119) y **CORRECTITUD** (#120-#128) no atribuyen ningún hallazgo a código de Lucio, consistente con que no tiene código de visión vivo.

---

*Fin del informe. Todos los números provienen de `git log/blame --all` y `gh pr/issue list` sobre el checkout `feature/initialize-testing-log` al 2026-05-31. No se modificó código ni se ejecutaron acciones de escritura en GitHub.*
