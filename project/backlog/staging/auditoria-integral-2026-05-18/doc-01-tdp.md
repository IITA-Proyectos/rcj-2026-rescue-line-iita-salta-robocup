# Auditoría integral 2026-05-18 — Estado del TDP (Team Description Paper) vs rúbrica oficial RCJ Rescue Line 2026

**Dominio:** documentación de competencia — específicamente el **TDP**. Fuentes leídas: `docs/es/` (12+ docs de análisis técnico), `docs/es/analisis-documentacion-rubricas-2026-05-10.md` (auditoría previa de documentación), `testing/` (TEST_LOG + README), `hardware/electronics/**` y `hardware/mechanics|mechanical/**` (material crudo de las secciones Mechanical/Electronic), e issues **#46, #95, #96, #97, #98** (+ contexto de #41, #45, #55, #93, #94).
**Autor:** auditor de documentación / TDP (lectura solamente, sin tocar código ni `software/**` ni `hardware/**`).
**Branch analizada:** `feature/initialize-testing-log` (contenido también en `main`, post-PR #101).
**Fecha:** 2026-05-18 (redactado 2026-05-31).

> **Marco de lectura (LEER ANTES).** Cada hallazgo se presenta como **TEMA A ANALIZAR**, no como "tarea obligatoria". Para cada criterio de la rúbrica se da: qué hay en el repo HOY, con qué calidad, qué falta, **riesgo de NO actuar**, **riesgo de actuar**, esfuerzo estimado, y la acción de mayor retorno. La decisión final es del equipo.
>
> **Esta auditoría NO repite la del 2026-05-10** ([`docs/es/analisis-documentacion-rubricas-2026-05-10.md`](../../../../docs/es/analisis-documentacion-rubricas-2026-05-10.md)). La cita, mide qué cambió en las 3 semanas transcurridas, y corrige dos cosas que esa auditoría subestimó (el material crudo de hardware es más rico de lo que decía; el `testing/` ya no está vacío pero sigue sin datos reales).

---

## 0. Resumen ejecutivo

**Diagnóstico en una línea:** a 30 días del mundial (Incheon, 2026-06-30), **el TDP sigue sin existir como archivo en el repositorio**. No hay `.md`, `.docx` ni `.pdf` de TDP en ningún lado del checkout. El material técnico crudo es abundante y, en hardware, **mejor de lo que la auditoría previa reconoció** — pero **nada está volcado en la estructura de la rúbrica oficial**, que es lo único que los jueces puntúan.

**Qué cambió desde el 2026-05-10 (3 semanas):**

| Ítem | Estado 2026-05-10 | Estado HOY (2026-05-31) | ¿Mejoró el puntaje del TDP? |
|---|---|---|---|
| Archivo TDP en el repo | No existe | **Sigue sin existir** | No |
| `docs/tdp/` (carpeta) | No existe | **Sigue sin existir** | No |
| `testing/TEST_LOG.md` | Vacío (`.gitkeep`) | **Inicializado** (template + índice) — issue #93 **CERRADO** | Infraestructura sí; datos **no** (0 tests reales) |
| Plantilla oficial `TDP_Template_Line_Maze.docx` | No descargada | **Sigue sin descargarse / sin estar en repo** | No |
| Diagramas formales (#41) | No existen | **Siguen sin existir** (solo Mermaid embebido) | No |
| BOM formal (#96) | Solo legacy | Hay un BOM en `hardware/electronics/PCB_Main/README.md` (no es la plantilla oficial) | Parcial (raw, no en TDP) |
| Fidelidad técnica docs (#95) | Sin validar | **Sigue sin validar** (issue OPEN) | No (riesgo latente) |

**Lectura honesta:** en 3 semanas, **el único entregable de documentación que se movió fue inicializar el `TEST_LOG.md`** — y se inicializó **vacío de contenido real** (solo trae un ejemplo didáctico `T-000` que el propio archivo marca "ESTE NO ES UN TEST REAL — BORRAR"). El issue #93 se cerró como "infraestructura lista", pero el criterio de rúbrica que ese issue debía atacar (Reliability Tests, ~24 pts) **sigue valiendo ~0 pts** hasta que se carguen tests con resultados. Cerrar #93 sin datos crea una **falsa sensación de avance**.

**Estimación de puntaje HOY (TDP, sobre 102 pts de la rúbrica):**

> **~6–12 / 102 → ~6–12 %.** Prácticamente igual que el estimado de la auditoría previa (5–15). El piso no se movió porque no se ensambló TDP; lo único que mejoró es la *preparación* (infraestructura de testing, material crudo de hardware identificado), que no otorga puntos hasta materializarse en el documento.

**Las 3 acciones de mayor retorno (detalle en §5):**

1. **Crear el esqueleto del TDP HOY** (`docs/tdp/TDP-IITA-2026.md` con las 17 cabeceras de la rúbrica) y volcar links al material crudo existente. ~1 h. Desbloquea TODO lo demás y captura el criterio "Formatting" (+4 pts) en cuanto se use la plantilla oficial.
2. **Cargar 5–10 tests reales en `TEST_LOG.md`** (reconstruir de WhatsApp/videos/memoria). ~3–4 h. Es el único camino para que las 4 secciones de "Reliability Tests" (~24 pts) dejen de valer 0.
3. **Recuperar el draft que Lucio dice tener en Drive** (issue #46, comentario del 2026-03-23) y commitearlo al repo. Si ese draft existe y está "desarrollado en su mayoría", el punto de partida real podría ser mucho más alto que 6–12 % — **pero hoy es invisible para los jueces y para esta auditoría porque vive en Drive, no en el repo.** Enzo lo viene pidiendo desde abril sin éxito.

---

## 1. La rúbrica oficial TDP 2026 — secciones requeridas

Fuente: [`Line&Maze_TDP_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Line&Maze_TDP_Rubrics_RCJ_Rescue_2026.pdf) + plantilla [`TDP_Template_Line_Maze.docx`](https://rescue.rcj.cloud/rules/2026/TDP_Template_Line_Maze.docx), tal como las transcribió la auditoría del 2026-05-10.

El TDP se puntúa por **17 Key Elements**, cada uno en escala **0 / 1-2 / 3-4 / 5-6 (excelente)**. Total = **17 × 6 = 102 pts**.

| # | Sección | Key Elements | Máx sección |
|---|---|---|---|
| 1 | **Project Planning – from Design to Deployment** | Requirements definition · Overall Project Plan · Integration Plan / System Engineering | **18** |
| 2 | **Mechanical design and manufacturing** | Design structure & diagrams · Sub-module design & workability · Maker/innovative solutions · **Reliability Tests & QA** | **24** |
| 3 | **Electronic design and manufacturing** | Design structure & diagrams · Sub-module design & workability · Maker/innovative solutions · **Reliability Tests & QA** | **24** |
| 4 | **Software** | Architecture design with diagrams (flowchart, UML, pseudocode) · Innovative solutions · **Reliability Tests & QA** | **18** |
| 5 | **Performance Evaluation** | **Reliability Testing & QA** (evaluación crítica de las corridas) | **6** |
| 6 | **Document** | Contents, Conciseness & Clarity · Formatting | **12** |

**Lo que separa 5-6 de 3-4:** las palabras **"innovative"** y **"clearly identifies"**. No alcanza con describir — hay que mostrar **diagramas, pseudocódigo, resultados de tests, paths de integración**.

**Novedad 2026:** "**Reliability Tests and quality assurance**" aparece ahora explícito en **4 de las 6 secciones** (Mechanical, Electronic, Software, Performance) = **24 pts atados a tener tests documentados**. Es el patrón de mayor impacto de toda la rúbrica.

---

## 2. Inventario: qué hay HOY en el repo relevante al TDP

### 2.1 El TDP en sí — **NO EXISTE**

Verificado con búsqueda exhaustiva en el checkout (`feature/initialize-testing-log`, = `main`):

- No hay ningún archivo cuyo nombre contenga `tdp`, `poster` o `description paper` (ni `.md`, `.docx`, `.pdf`).
- No existe la carpeta `docs/tdp/` (solo `docs/es/` y `docs/en/`).
- `git log` desde 2026-05-09 muestra que el **único** trabajo de documentación que aterrizó fue: el propio análisis de rúbricas (`0142f33`), el triage de issues (`9d33eb7`), la inicialización de `testing/` (`c42e535`), y dos commits de corrección "Lautaro→Laureano". **Cero TDP, cero diagramas, cero BOM formal, cero poster, cero video.**

> ⚠️ **Heads-up importante (issue #46).** El 2026-03-23 **Lucio comentó en #46**: *"estuve viendo lo del tdp y creé una base de cómo hacerlo, lo desarrollé en la mayoría"*. Enzo respondió el 2026-04-01 y de nuevo el 2026-04-29 **pidiendo el link de Drive de ese archivo**, sin respuesta visible. **Conclusión:** existe (o existió) un draft de TDP **en Google Drive**, pero **no está en el repositorio**. Para todo efecto de puntaje y de esta auditoría, **el TDP del repo es cero**. Esto es un riesgo de gobernanza además de técnico: el entregable más importante vive fuera de control de versiones, sin review, sin trazabilidad, y sin que el coach pueda verlo.

### 2.2 Material crudo disponible (sí existe, NO está en formato rúbrica)

Acá la auditoría del 2026-05-10 **se quedó corta**: dijo "~80 % del contenido técnico ya escrito" pero subvaloró el material de hardware. Inventario real:

**Software / arquitectura (texto, calidad media-alta):**
- [`docs/es/analisis-integral-ingenieria.md`](../../../../docs/es/analisis-integral-ingenieria.md) — 700+ líneas (Claude). Arquitectura, firmware, visión, comms. **Confirma el campeonato nacional 2025** (línea 11) — dato clave para credibilidad del TDP y para el Poster.
- [`docs/es/analisis-arquitectura-robotica.md`](../../../../docs/es/analisis-arquitectura-robotica.md) — diagrama **Mermaid** del sistema (Gemini). Buen punto de partida para Integration Plan (T3) y Software architecture (T12), pero es Mermaid, no diagrama formal.
- `analisis-teensy-codigo.md`, `analisis-estrategico-teensy-rescate.md`, `analisis-profundo-raspberry-os-codigo.md`, `analisis-raspberry-pi.md`, `comunicacion-rpi-teensy.md`, `librerias-firmware.md`, `yolo-raspberry.md`, `referencia-equipos-top-rescue-line-2024-2025.md`, `analisis-integral-comunicacion-2026-05-10.md`.

**Mechanical (mejor de lo reportado):**
- **Imágenes ortográficas del robot YA existen**: `hardware/mechanical/_legacy/CAD/Imagenes/` tiene `front.png`, `back.png`, `left.png`, `right.png`, `superior.png`, `inferior.png`, `Rescuebot.png` + el **modelo editable `Rescue3D.f3d`**. Esto es material directo para el criterio "Mechanical design structure & diagrams" (T4), que la auditoría previa dio por inexistente.
- [`hardware/mechanics/traction-optimization/README.md`](../../../../hardware/mechanics/traction-optimization/README.md) — doc de tracción/rampas (Gemini). **Ojo de fidelidad:** describe técnicas *aspiracionales* (ruedas de silicona moldeadas, suspensión rocker-bogie, ajuste activo de CG con servos) que probablemente **el robot NO tiene**. Útil como "future plans", peligroso si se presenta como "as-built".

**Electronic (bastante más rico de lo reportado):**
- [`hardware/electronics/PCB_Main/README.md`](../../../../hardware/electronics/PCB_Main/README.md) — **es un BOM real** (titulado "BOM — Lista de Materiales"): componentes electrónicos, mecánicos y de potencia, con cantidad, proveedor y link de compra. **Esto cubre parcialmente el issue #96** (que dice que solo hay BOM legacy — ya está semi-desactualizado).
- `hardware/electronics/PCB_Main/`: **`PCB.json`** (diseño EasyEDA, 580 KB), **`pcb-preview.pdf`** y **`ROBOCUP.SHEET.pdf`** (esquemático). Material directo para "Electronic design structure & diagrams" (T8).
- [`hardware/electronics/power-tree/README.md`](../../../../hardware/electronics/power-tree/README.md) — power tree con diagrama Mermaid + best practices (star ground, filtrado de motores). **Fidelidad:** menciona `VNH5019` e `INA219` que **no están en el BOM de PCB_Main** (que no lista driver de motor explícito). Verificar antes de citar.
- [`hardware/electronics/datasheets/README.md`](../../../../hardware/electronics/datasheets/README.md) — parámetros de XL4016, VNH5019, etc.

**Tests / QA (infraestructura nueva, sin datos):**
- `testing/TEST_LOG.md` + `testing/README.md` — bitácora inicializada (issue #93). Índice por categoría (`[MECH]`/`[ELEC]`/`[SW]`/`[PERF]`) **mapeado explícitamente a los criterios de la rúbrica** — muy bien pensado. Pero las 4 tablas están **vacías** y la única entrada es el ejemplo `T-000` marcado "no es real".
- `software/teensy/firmware/test/` — **~24 programas de test de hardware** (sensores BNO055, color, ToF, ultrasonido, encoders; actuadores claw/motores; comms serial). **Esto es evidencia de metodología de QA** que puede citarse en T11/T14 ("tenemos suite de bring-up por subsistema"), aunque son *programas de prueba*, no *resultados de prueba*.

**Reglas de competencia:**
- `competition/rules/` solo tiene **reglas 2023** y el reglamento Roboliga 2025. **Las reglas RCJ Rescue Line 2026 NO están en el repo** — necesarias para redactar Requirements (T1) con citas. (Aunque `hardware/cambios_de_hardware.md` cita correctamente la regla 3.9 de 2026 sobre luces LED, así que alguien tiene acceso a las reglas 2026.)

---

## 3. Puntaje estimado HOY — desglose por sección

Criterio de puntuación: se evalúa **el contenido presente en el repo, en formato entregable**. El material crudo en `docs/es/` y `hardware/` otorga puntos **mínimos** porque (a) no está en la estructura de la rúbrica, (b) está en español (la rúbrica TDP no exige inglés tan estrictamente como el video, pero la presentación informal resta en "Formatting"/"Clarity"), y (c) mezcla "análisis con recomendaciones" en vez de "descripción as-built".

| Sección (máx) | Pts HOY | Razón |
|---|---|---|
| **1. Project Planning** (18) | **0–2** | No hay Requirements list, ni Project Plan con milestones, ni Integration Plan formal. Solo un Mermaid de arquitectura suelto. |
| **2. Mechanical** (24) | **2–3** | Existen imágenes ortográficas + F3D + doc de tracción, pero NO ensamblados en TDP, sin explicación de decisiones as-built, sin sub-módulos descritos como tales, **sin un solo test mecánico documentado** (Reliability = 0). |
| **3. Electronic** (24) | **2–3** | Hay BOM + esquemático + PCB + power-tree (mejor base que mecánica), pero idem: no en TDP, fidelidad sin validar, **Reliability eléctrica = 0**. |
| **4. Software** (18) | **1–3** | Mucho texto de arquitectura, pero **sin flowchart/UML/pseudocódigo formal** (criterio explícito), y **Reliability SW = 0**. |
| **5. Performance Evaluation** (6) | **0–1** | No hay sección de "qué falló en competencia/banco y cómo se resolvió" en formato evaluativo. |
| **6. Document** (12) | **1–2** | Sin plantilla oficial (Formatting ≈ 1-2). Contenido no consolidado (Clarity baja porque está disperso en 12 archivos). |
| **TOTAL (102)** | **~6–12** | **≈ 6–12 %** |

> **Comparación con la auditoría previa.** El 2026-05-10 estimó 5–15 / 102. Hoy estimo 6–12 / 102. **El rango no mejoró de forma significativa** porque el único delta real (TEST_LOG inicializado) no aporta puntos sin datos. La banda alta del estimado (12) asume que un juez benévolo reconozca el material crudo como "borrador avanzado disperso"; la banda baja (6) asume evaluación estricta del repo "tal cual se entregaría hoy".

---

## 4. TEMAS A ANALIZAR — por criterio (qué falta / riesgo / esfuerzo)

> Se mantiene la numeración **T1–T17** de la auditoría del 2026-05-10 para continuidad. Acá se **actualiza** el estado de cada uno al 2026-05-31 y se agrega el material crudo descubierto que esa auditoría no contempló.

### 4.1 Project Planning (18 pts)

| ID | Criterio | Estado hoy | Falta | Riesgo NO actuar | Esfuerzo |
|----|----------|-----------|-------|------------------|----------|
| **T1** | Requirements definition (6) | 0 | Lista numerada derivada de reglas 2026 (medidas robot, víctimas, rampas). Reglas 2026 **no están en el repo**. | Alto → máx 1-2 pts | 2 h (+1 h leer reglas) |
| **T2** | Overall Project Plan (6) | 0 | Tabla Sprint/Milestone/Owner/Fecha. El issue tracker tiene tareas pero no roadmap consolidada. | Alto | 1.5 h |
| **T3** | Integration Plan (6) | ~1 | Formalizar el Mermaid de `analisis-arquitectura-robotica.md` + tabla "componente → requirement que cubre". | Medio → el Mermaid da 3-4 si se ensambla | 2 h |

### 4.2 Mechanical (24 pts)

| ID | Criterio | Estado hoy | Falta | Riesgo NO actuar | Esfuerzo |
|----|----------|-----------|-------|------------------|----------|
| **T4** | Design structure & diagrams (6) | ~1 | **Las imágenes ortográficas YA existen** en `_legacy/CAD/Imagenes/`. Falta: moverlas/citarlas en el TDP + explicar decisiones as-built (por qué 4WD, por qué omniwheel). | Medio (la materia prima existe — es ensamblar) | 2 h (menos que las 2.5 h estimadas antes) |
| **T5** | Sub-modules & workability (6) | 0 | Describir claw (5 servos: sortLeft/sortRight/depositCenter), drivetrain, sensor mounts como sub-módulos. | Medio | 1.5 h |
| **T6** | Maker / innovative (6) | 0 | Destacar 1-3 innovaciones reales del equipo (claw 5 servos es no-trivial). **Pregunta abierta del 2026-05-10 sigue sin responder:** ¿cuál es la feature mecánica más original? | Medio → 3-4 si no se destaca como "innovative" | 1 h |
| **T7** | **Reliability Tests & QA** (6) ⚠️ | **0** | Tests mecánicos documentados con resultados. `TEST_LOG.md` listo pero **categoría `[MECH]` vacía**. | **MUY ALTO** (0 pts garantizado) | 1-2 h (cargar tests reales) |

### 4.3 Electronic (24 pts)

| ID | Criterio | Estado hoy | Falta | Riesgo NO actuar | Esfuerzo |
|----|----------|-----------|-------|------------------|----------|
| **T8** | Design structure & diagrams (6) | ~1 | **Esquemático (`ROBOCUP.SHEET.pdf`) + PCB (`PCB.json`/preview) YA existen.** Falta ensamblar + explicar en TDP. | Medio (materia prima existe) | 1.5-2 h |
| **T9** | Sub-modules & workability (6) | ~1 | Power tree ya documentado (`power-tree/README.md`). Falta wiring de sensores + comms como sub-módulo. | Medio | 1.5 h |
| **T10** | Maker / innovative (6) | 0 | Documentar que la **PCB main es de diseño propio** (si lo es → 5-6 pts; si son breakouts → 3-4). Hay `PCB.json` de EasyEDA propio, lo que sugiere diseño propio — **confirmarlo**. | Medio | 1 h |
| **T11** | **Reliability Tests & QA** (6) ⚠️ | **0** | Tests eléctricos (caída de tensión bajo carga, ruido, power tree real). Los ~24 test programs de firmware ayudan a argumentar metodología. Categoría `[ELEC]` vacía. | **MUY ALTO** | 1.5 h |

### 4.4 Software (18 pts)

| ID | Criterio | Estado hoy | Falta | Riesgo NO actuar | Esfuerzo |
|----|----------|-----------|-------|------------------|----------|
| **T12** | Architecture w/ diagrams (6) ⚠️ | ~1 | **Flowchart formal del main loop Teensy + flowchart Main.py + class diagram + pseudocódigo** de line-track y victim detection. Hoy solo Mermaid. **Bloqueado por #41 (OPEN).** | Alto → sin diagramas formales, máx 1-2 | 4 h |
| **T13** | Innovative solutions (6) | ~1 | Destacar YOLOv8→ONNX en RPi, FSM de rescate, doble validación con sensor de color. El texto existe, falta "venderlo" como innovación. | Medio | 1.5 h |
| **T14** | **Reliability Tests & QA** (6) ⚠️ | **0** | Tests de software (parser serial, FSM rescate, visión). Categoría `[SW]` vacía. | **MUY ALTO** | 1.5 h |

### 4.5 Performance Evaluation (6 pts)

| ID | Criterio | Estado hoy | Falta | Riesgo NO actuar | Esfuerzo |
|----|----------|-----------|-------|------------------|----------|
| **T15** | Insightful evaluation (6) | 0 | Narrar 1-2 problemas reales y su solución en formato evaluativo. **Hay historias listas:** el bug del LED 12V para el sensor de color (`hardware/cambios_de_hardware.md`, motivado por la regla 2026 de luces LED) es un caso de evaluación EXCELENTE. También la carga del YOLO en hot path (ya resuelta). | Medio | 1.5 h |

### 4.6 Document quality (12 pts)

| ID | Criterio | Estado hoy | Falta | Riesgo NO actuar | Esfuerzo |
|----|----------|-----------|-------|------------------|----------|
| **T16** | Contents, Conciseness, Clarity (6) | ~1 | Review final. Riesgo bajo si las otras secciones se completan. Hoy baja porque el contenido está disperso en 12 archivos. | Bajo (depende del resto) | 1 h |
| **T17** | Formatting (6) ⚠️ | ~1 | **Descargar `TDP_Template_Line_Maze.docx` y usarla.** Sin plantilla oficial → máx 1-2. | Alto → 4 pts perdidos por algo trivial | 30 min |

---

## 5. Acciones de mayor retorno (ROI ordenado)

> Ordenadas por **(pts ganables) / (horas)**. Las 4 primeras son "quick wins" de altísimo retorno.

### 🥇 Acción 1 — Crear el esqueleto del TDP en el repo (HOY, ~1 h)

Crear `docs/tdp/TDP-IITA-2026.md` con las **17 cabeceras de la rúbrica** (las 6 secciones de §1 de este informe). Bajo cada cabecera, pegar links al material crudo que ya cubre ese criterio (los identifiqué en §2.2). Commitear el esqueleto aunque esté incompleto.

- **Por qué primero:** desbloquea la colaboración (hoy nadie puede aportar porque no hay dónde), hace visible el avance real, y convierte "no existe" en "borrador con TODOs". **Sin esto, ninguna otra acción del TDP es posible.**
- **Riesgo de actuar:** nulo (es escritura, no toca código).
- **Gana:** habilita el +4 de Formatting (en cuanto se use la plantilla oficial) y ~2-3 pts de "borrador estructurado" reconocible.

### 🥈 Acción 2 — Cargar 5–10 tests reales en `TEST_LOG.md` (~3–4 h)

El `TEST_LOG.md` ya tiene template e índice mapeado a la rúbrica. Falta **el dato**. Reconstruir tests de WhatsApp/videos/memoria del equipo: al menos 2-3 por categoría (`[MECH]`, `[ELEC]`, `[SW]`, `[PERF]`).

- **Por qué:** es el **único** camino para que las 4 secciones de "Reliability Tests" (**~24 pts**) dejen de valer 0. Es el tema de mayor impacto absoluto de toda la rúbrica.
- **Riesgo de actuar:** bajo (documentar tests ya hechos informalmente), pero requiere disciplina nueva (anotar cada ensayo futuro).
- **Gana:** de 0 a ~10-16 pts repartidos en T7/T11/T14/T15 según cantidad y calidad.
- **Nota crítica:** el issue #93 se cerró con el log **vacío**. **Reabrir el espíritu de #93** o abrir un seguimiento "cargar tests reales", porque "infraestructura lista" ≠ "puntos ganados".

### 🥉 Acción 3 — Recuperar el draft de Drive de Lucio y commitearlo (~30 min + review)

Issue #46 sugiere que existe un draft "desarrollado en su mayoría" en Drive desde marzo.

- **Por qué:** si ese draft es bueno, **el punto de partida real es mucho mayor que 6-12 %** — pero hay que traerlo al repo para que cuente, se pueda revisar y se pueda iterar con la plantilla oficial.
- **Riesgo de NO actuar:** **muy alto** — es el entregable más importante del proyecto viviendo fuera de control de versiones, sin review del coach, a 30 días del mundial. Si Lucio se enferma o pierde acceso, se pierde.
- **Acción concreta:** Lucio sube el `.md`/`.docx` a `docs/tdp/` vía PR. Si está en Google Docs, exportar a Markdown.

### Acción 4 — Descargar la plantilla oficial + reglas 2026 al repo (~30 min)

`TDP_Template_Line_Maze.docx` y `RCJRescueLine2026-final.pdf` a `competition/rules/` y `docs/tdp/`.

- **Gana:** +4 pts de Formatting (T17) + habilita T1 Requirements con citas a reglas reales. **ROI altísimo: 30 min por 4 pts.**

### Acción 5 — Diagramas formales (#41) (~4 h, Lucio)

Flowchart main loop Teensy + flowchart Main.py + class diagram + integration diagram, en draw.io/tldraw (no Mermaid). El Mermaid existente es el borrador.

- **Gana:** desbloquea T12 (Software, +hasta 6) y T3 (Integration) y el Poster "Software Line". Cierra #41.

### Acción 6 — Validar fidelidad técnica antes de volcar (#95, ~2-3 h, Enzo o coach)

**Esto es crítico y la auditoría previa ya lo marcó, pero el issue sigue OPEN.** Dos riesgos concretos detectados en esta pasada:

1. **Docs de análisis desactualizados:** afirman bugs ya corregidos (encoders volatile, strcmp, YOLO loading). Si se copian al TDP, contradicen el código real que los jueces ven → resta en "Clarity" y "Performance".
2. **Docs de hardware aspiracionales:** `traction-optimization/README.md` describe ruedas de silicona moldeadas, rocker-bogie y ajuste activo de CG; `power-tree/README.md` cita VNH5019/INA219 **que no figuran en el BOM de `PCB_Main/README.md`**. Si esto entra al TDP como "as-built" y el robot real no lo tiene, es una **inconsistencia que un juez técnico detecta en la mesa**. Va como "future plans", no como descripción actual.

- **Riesgo de NO actuar:** medio-alto. Es la diferencia entre un TDP creíble y uno que se cae bajo preguntas.

---

## 6. Estimación de puntaje — hoy vs. potencial (recalibrada)

| Sección (máx) | HOY | Tras Acciones 1-4 (≈6 h) | Tras cuerpo completo TDP (≈+20 h) |
|---|---|---|---|
| Project Planning (18) | 0–2 | 3–5 | 12–16 |
| Mechanical (24) | 2–3 | 6–8 | 16–20 |
| Electronic (24) | 2–3 | 6–8 | 16–20 |
| Software (18) | 1–3 | 4–6 | 13–16 |
| Performance (6) | 0–1 | 1–2 | 5–6 |
| Document (12) | 1–2 | 6–8 | 9–11 |
| **TOTAL (102)** | **~6–12** | **~26–37** | **~71–89** |
| **% del máximo** | **6–12 %** | **25–36 %** | **70–87 %** |

> **Diferencia vs. la tabla del 2026-05-10:** la columna "post-quick-wins" sube un poco más rápido en Mechanical/Electronic porque **descubrí material crudo (imágenes CAD ortográficas, esquemático, PCB, BOM) que esa auditoría dio por inexistente**. El techo final es consistente (~80 % bien ejecutado). El piso de hoy es básicamente el mismo: **mientras el TDP no esté en el repo, el equipo está dejando ~90 pts sobre la mesa.**

---

## 7. Cierre — el mensaje en una línea

A 30 días de Incheon, **el cuello de botella del TDP no es falta de contenido técnico — es falta de ensamblaje en el repositorio.** El equipo tiene el material; lo que falta es (1) crear el archivo, (2) cargar tests reales, y (3) traer el draft de Lucio de Drive al repo. **Las primeras 6 horas de trabajo bien dirigido multiplican el puntaje por ~3-4x.** El único avance de las últimas 3 semanas —inicializar el `TEST_LOG.md`— fue necesario pero se quedó a mitad de camino: la infraestructura está, los datos no. **Cerrar issues por "infraestructura lista" sin datos genera una métrica de avance engañosa que conviene corregir en la próxima reunión de equipo.**

---

*Auditoría de documentación/TDP dirigida por @gviollaz, asistida por Claude Code. Fuentes: rúbricas oficiales RCJ Rescue 2026 + auditoría previa `analisis-documentacion-rubricas-2026-05-10.md` + estado del repo a 2026-05-31 (branch `feature/initialize-testing-log`) + issues #46/#95/#96/#97/#98. Filosofía: TEMAS A ANALIZAR — el equipo decide qué tomar; el auditor presenta el material y el riesgo.*
