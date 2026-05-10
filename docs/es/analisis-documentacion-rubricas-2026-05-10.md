# Análisis de documentación (TDP + Poster + Video) vs Rúbricas Oficiales RCJ Rescue 2026

> **Pedido del coach @gviollaz:** revisar el TDP, Poster y Video del equipo IITA Salta, asegurar que se corresponda con la realidad técnica del robot, cruzar con las rúbricas oficiales 2026 y emitir un documento completo con qué modificar para asegurar la máxima puntuación.
>
> **Fecha:** 2026-05-10. **Asignados de seguimiento:** @enzzo19 + @benjaminvillagran + el coach. **Owners por documento:** TDP → @luciouriel2011; Poster → @Laumonteros; Video → @benjaminvillagran (según issues #46, #45, #55).
>
> **Forma del análisis:** mismo framing que los anteriores — todo finding es **TEMA A ANALIZAR** con riesgo / tiempo / pregunta concreta para el equipo.

---

## 0. Resumen ejecutivo

**Diagnóstico en una línea:** el equipo tiene **~80 % del contenido técnico** necesario para llegar a puntaje alto (gracias a los análisis del coach + Gemini + Claude que ya viven en `docs/es/`), pero **el 0 % del contenido está estructurado en los documentos oficiales** — TDP, Poster y Video todavía no existen como archivos en el repo.

**Estimación de puntaje actual vs. potencial:**

| Documento | Máximo | Actual estimado | Potencial con plan de acción |
|---|---|---|---|
| TDP | **102 pts** | ~6-12 pts (raw material en `docs/es/`, no estructurado) | **80-90 pts** |
| Poster | **18 pts** | 0 pts (no existe) | **16-18 pts** |
| Video | **24 pts** | 0 pts (sólo footage crudo en `software/raspberry/Videos/`) | **20-22 pts** |
| **Total** | **144 pts** | **~6-12 pts (4-8%)** | **~116-130 pts (81-90%)** |

**Acción inmediata más urgente:** descargar la **plantilla oficial TDP** desde [rescue.rcj.cloud/documents](https://rescue.rcj.cloud/documents) (`TDP_Template_Line_Maze.docx`) y volcar el contenido existente respetando ESA estructura. Sin la plantilla oficial, el criterio "Formatting" del TDP ya pierde puntos.

**Brecha conceptual más grande:** **`Reliability Tests and quality assurance`** aparece como criterio en 4 de las 5 grandes secciones del TDP. Si no documentamos tests sistemáticos en banco/pista, **perdemos ~24 pts (~24%) del TDP** automáticamente.

---

## 1. Las 3 rúbricas oficiales 2026 (resumen)

### 1.1 TDP (Technical Description Paper) — máximo 102 pts

**Documento:** [`Line&Maze_TDP_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Line&Maze_TDP_Rubrics_RCJ_Rescue_2026.pdf) · [Plantilla](https://rescue.rcj.cloud/rules/2026/TDP_Template_Line_Maze.docx)

Cada **Key Element** se puntúa 0, 1-2, 3-4 o **5-6 (excelente)**. Total = 17 elementos × 6 = 102 pts.

| Sección | Key Elements | Max sección |
|---|---|---|
| **Project Planning – from Design to Deployment** | Requirements definition · Overall Project Plan · Integration Plan / System Engineering | 18 |
| **Mechanical design and manufacturing** | Mechanical design structure and diagrams · Sub-module design and workability · Maker and/or innovative solutions · Reliability Tests and quality assurance | 24 |
| **Electronic design and manufacturing** | Electronic design structure and diagrams · Sub-module design and workability · Maker and/or innovative solutions · Reliability Tests and quality assurance | 24 |
| **Software** | Architecture design with diagrams (flowchart, UML, pseudocode) · Innovative solutions · Reliability Tests and quality assurance | 18 |
| **Performance Evaluation (competition challenges)** | Reliability Testing and Quality Assurance | 6 |
| **Document** | Contents, Conciseness and Clarity · Formatting | 12 |

**Lo que separa 5-6 puntos de 3-4:** "**innovative**" y "**clearly identifies**" en cada criterio. No alcanza con explicar — hay que mostrar **diagrams, pseudocode, test results, integration paths**.

**Nuevo en 2026 (vs 2025):** todos los criterios incluyen ahora "**Reliability Tests and quality assurance**" explícitamente. Si vienen de un TDP 2025, esa sección hay que crearla nueva.

### 1.2 Poster — máximo 18 pts

**Documento:** [`Line&Maze_Poster_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Line&Maze_Poster_Rubrics_RCJ_Rescue_2026.pdf)

| Key Element | 0 | 1-2 | 3-4 | **5-6** |
|---|---|---|---|---|
| **Team** | N/A | Nombre, liga, país, miembros con rol genérico | + fotos de los miembros + roles específicos | + **resultados notables y premios** + fotos del equipo en competencias nacionales |
| **Hardware Line** | N/A | Foto del robot + lista de sensores y motores SIN descripción | + descripción de cada sensor con la tarea asociada | + **soluciones innovadoras de hardware destacadas** con imagen/sketch propio + explicación |
| **Software Line** | N/A | Sólo lenguaje + intento confuso de explicación | + flowchart del main loop comprensible | + **algoritmos y métodos relevantes** explicados con pseudocódigo / flowchart / **resultados de tests** (outputs, gráficos) |

**Sugerencias específicas del comité para "innovative":**
- **Hardware Line:** chasis custom, mecanismo de captura de víctimas, cualquier solución innovadora.
- **Software Line:** estrategia de zona de evacuación, detección de víctimas, line following, cualquier algoritmo innovador.

### 1.3 Video (Presentation Video) — máximo 24 pts

**Documento:** [`Presentation_Video_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Presentation_Video_Rubrics_RCJ_Rescue_2026.pdf) · [Guideline](https://rescue.rcj.cloud/rules/2026/Presentation_Video_Guideline_RCJ_Rescue_2026.pdf)

**Restricciones generales:**
- **Duración:** 5-7 min (pasados los 7 min, sólo se evalúan los primeros 7).
- **Idioma:** **inglés** obligatorio. Subtítulos en inglés opcionales o en idioma original.
- **Formato:** `.mp4`, máximo 500 MB.
- **Uso:** se proyecta en la competencia internacional + posiblemente en la web oficial RoboCup.

| Sección | Tiempo sugerido | 5-6 (excelente) |
|---|---|---|
| **1. Team Introduction** | 1 min 30 s | Presenta al equipo claramente con fotos. Cómo se formó, primeros pasos, roles, qué los inspiró. |
| **2. Robot Introduction** | 1 min | Presenta al robot **usándolo en cámara** para mostrar hardware, innovaciones y class diagram del software. |
| **3. Robot In Action** | 2 min 15 s | Robot en acción **mientras el equipo da explicación de qué hace**, no sólo footage. |
| **4. Future Plans** | 0 min 45 s | Plan de futuro claro con metas concretas en RoboCup. |

**Lo que separa 5-6 puntos de 3-4:** **mostrar al robot HACIENDO**, no sólo describir. El equipo aparece o se escucha explicando mientras el robot ejecuta.

---

## 2. Estado actual de los documentos (al 2026-05-10)

### 2.1 TDP — Issue [#46](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/46)

- **Owner:** @luciouriel2011 (+ Enzo, Lautaro, Benjamin asignados).
- **Estado:** issue abierto desde hace meses. **No hay archivo TDP en el repo** (ni `.md`, ni `.docx`, ni `.pdf`).
- **Plan original (del coach en el issue):** archivo Markdown en `docs/`, formato basado en TDP Soccer 2025, cumplir 100 % rúbricas.

**Material crudo disponible** (~80 % del contenido técnico ya escrito):
- [`docs/es/analisis-arquitectura-robotica.md`](analisis-arquitectura-robotica.md) — by Gemini, con diagrama Mermaid del sistema.
- [`docs/es/analisis-integral-ingenieria.md`](analisis-integral-ingenieria.md) — by Claude, 700+ líneas. Cubre arquitectura, firmware, vision, comms.
- [`docs/es/analisis-estrategico-teensy-rescate.md`](analisis-estrategico-teensy-rescate.md)
- [`docs/es/analisis-profundo-raspberry-os-codigo.md`](analisis-profundo-raspberry-os-codigo.md)
- [`docs/es/analisis-raspberry-pi.md`](analisis-raspberry-pi.md)
- [`docs/es/analisis-teensy-codigo.md`](analisis-teensy-codigo.md)
- [`docs/es/comunicacion-rpi-teensy.md`](comunicacion-rpi-teensy.md)
- [`docs/es/librerias-firmware.md`](librerias-firmware.md)
- [`docs/es/yolo-raspberry.md`](yolo-raspberry.md)
- [`docs/es/referencia-equipos-top-rescue-line-2024-2025.md`](referencia-equipos-top-rescue-line-2024-2025.md)
- [`docs/es/analisis-integral-comunicacion-2026-05-10.md`](analisis-integral-comunicacion-2026-05-10.md) — nuevo
- [`docs/es/analisis-flexibilidad-tasks-2026-05-10.md`](analisis-flexibilidad-tasks-2026-05-10.md) — nuevo
- [`hardware/electronics/PCB_Main/`](../../hardware/electronics/PCB_Main) — diseño PCB (JSON + PDF preview)
- [`hardware/mechanical/_legacy/CAD/STLS/`](../../hardware/mechanical/_legacy/CAD/STLS) — STLs del robot

**Lo que falta ESTRUCTURALMENTE:**
1. ❌ El archivo TDP en sí (vacío hoy).
2. ❌ Plantilla oficial 2026 descargada del sitio `rescue.rcj.cloud`.
3. ❌ Sección **Project Planning** (requirements list, milestones, integration plan) — no existe.
4. ❌ Sección **Reliability Tests and quality assurance** específica — testing en `testing/` está vacío (.gitkeep solo).
5. ❌ **Idioma inglés** — todo el contenido raw está en español. Hay que traducir o redactar nuevo.
6. ❌ **BOM (Bill of Materials)** formal — hay archivos en `hardware/electronics/_legacy/ELECTRONICA/` pero no actualizado.
7. ❌ Diagramas formales (flowchart, UML, class diagram) — ahora hay sólo Mermaid embedded.

### 2.2 Poster — Issue [#45](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/45)

- **Owner:** @Laumonteros (sin assignee en GitHub al 2026-05-10).
- **Estado:** issue abierto. **No hay PDF de poster en `docs/files/poster/`** (la carpeta `docs/files/` no existe).
- **Plan original:** Canva compartido, PDF final en repo.

**Material crudo:**
- Foto del robot (asumimos que existen, no veo en repo).
- Fotos del equipo (asumimos que existen, no veo en repo).
- Nombre liga/país/miembros (en `CODEOWNERS`).
- **Premio nacional 2025** mencionado en `analisis-integral-ingenieria.md` — clave para criterio Team 5-6.

**Lo que falta:**
1. ❌ El poster en sí (no existe).
2. ❌ Fotos del equipo en formato adecuado (al menos pic en banco + en competencia 2025).
3. ❌ Pseudocode/flowchart **publicable** del main loop.
4. ❌ **Resultados de tests** (gráficos, outputs) — depende del gap de testing del TDP.

### 2.3 Video — Issue [#55](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/55)

- **Owner:** @benjaminvillagran.
- **Estado:** issue abierto. **No hay video oficial en el repo**.
- **Material crudo (footage):** 5 archivos en `software/raspberry/Videos/`:
  - `3rvideo.mp4`, `diciembremuestr.mp4`, `xdsdsd.mp4`, `video_2025-08-23_23-40-37.avi`, `video_2025-08-24_00-00-18.mp4`.
  - **Probablemente útil para sección 3 "Robot In Action"** del video oficial.

**Lo que falta:**
1. ❌ El video editado en sí (5-7 min, .mp4, ≤500 MB).
2. ❌ **Audio en inglés** o subtítulos en inglés.
3. ❌ Footage del **robot mostrando hardware** mientras alguien explica (sección 2).
4. ❌ Footage del **equipo presentándose** con fotos (sección 1).
5. ❌ Plan de **future plans** (sección 4).
6. ❌ Script.

### 2.4 Diagramas de bloques — Issue [#41](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/41)

- **Owner:** sin asignar formal, pidió Lucio en el issue.
- **Estado:** issue abierto. **No hay diagrams formales** en el repo.
- **Hay** un Mermaid embedido en `analisis-arquitectura-robotica.md` que es buen punto de partida.

Estos diagrams son **insumo directo** del TDP (criterios "Architecture design with diagrams", "Mechanical design diagrams", "Electronic design diagrams") y del Poster (criterio "Software Line - flowchart"). **Sin estos diagrams, no se pasa de 3-4 pts en esos criterios.**

---

## 3. TEMAS A ANALIZAR — TDP

> Por cada criterio del TDP, qué tenemos / qué falta / qué hacer / cuánto cuesta / cuánto se gana.

### 3.1 Project Planning (max 18 pts)

#### TEMA T1 — Requirements definition (max 6 pts)

**Qué observamos.** No hay un documento que liste los requirements del robot derivados de las reglas RCJ 2026 (e.g. "robot ≤ 250×250 mm", "debe pasar seesaw < 20°", "víctimas: 8 negras + 4 plateadas + 2 falsas").

**Qué falta.** Un capítulo del TDP con: lista numerada de requirements, justificación de cada uno contra reglas RCJ 2026, restricciones por hardware del equipo.

**Riesgo de NO cambiar.** Alto — sin esto, máximo 1-2 pts en este criterio (4 pts perdidos).

**Riesgo de cambiar.** Bajo — es escritura, no toca código.

**Tiempo estimado.** 2 h (lectura reglas + redacción + review entre los dos).

**Pregunta para el equipo.** ¿Tienen lista la edición 2026 de las reglas? Si no, primero descargar reglas y leerlas en grupo (1 h) antes de redactar requirements.

#### TEMA T2 — Overall Project Plan (max 6 pts)

**Qué observamos.** No hay calendario formal, milestones por miembro o gates de revisión. El issue tracker tiene tareas pero no hay roadmap consolidada.

**Qué falta.** Tabla con: Sprint / Milestone / Owner / Fecha objetivo / Status. Mínimo 4-6 milestones grandes (e.g. "M1: línea estable enero", "M2: zona rescate febrero", "M3: tunning marzo", "M4: TDP final mayo", "M5: video + poster junio").

**Riesgo de NO cambiar.** Alto — automáticamente 1-2 pts en este criterio. Refleja debilidad de gestión.

**Riesgo de cambiar.** Bajo — escritura + reconstrucción del histórico.

**Tiempo estimado.** 1.5 h (entrevista a Lautaro/Benjamin sobre cuándo se hizo cada cosa + redacción).

**Pregunta para el equipo.** ¿Quién tiene memoria histórica de las fechas?

#### TEMA T3 — Integration Plan / System Engineering (max 6 pts)

**Qué observamos.** El diagrama Mermaid en `analisis-arquitectura-robotica.md` es buen punto de partida. Falta cómo se conectan, qué comm protocols, qué requirements cubre cada sub-componente.

**Qué falta.** Diagrama formal (no sólo Mermaid) + tabla "componente → qué requirement cubre → cómo se conecta a otros".

**Riesgo de NO cambiar.** Medio — el Mermaid sólo da 3-4 pts. Para 5-6 hay que formalizarlo.

**Riesgo de cambiar.** Bajo — escritura.

**Tiempo estimado.** 2 h.

**Pregunta para el equipo.** ¿Usamos el Mermaid existente o re-dibujamos en draw.io / Figma para que se vea más prolijo?

### 3.2 Mechanical design (max 24 pts)

#### TEMA T4 — Mechanical design structure & diagrams (max 6 pts)

**Qué observamos.** STLs en `hardware/mechanical/_legacy/CAD/STLS/` + imágenes del robot en `_legacy/CAD/Imagenes/`. NO hay un documento explicando el diseño.

**Qué falta.** Capítulo con: imágenes ortogonales (front, top, side), explicación de cada parte mayor (chasis, claw, motor mounts), por qué se eligió (e.g. "chasis 4WD por tracción en rampa de 25°").

**Riesgo de NO cambiar.** Medio-Alto — sin esto, máximo 1-2 pts.

**Riesgo de cambiar.** Bajo.

**Tiempo estimado.** 2.5 h (Benjamin + Enzo, requiere fotos nuevas o las existentes en el legacy).

#### TEMA T5 — Mechanical sub-modules (max 6 pts)

Similar a T4 pero focalizado en sub-módulos: claw (5 servos), drivetrain, sensor mounts. Tiempo: 1.5 h.

#### TEMA T6 — Mechanical innovative solutions (max 6 pts)

**Qué observamos.** El robot **probablemente tiene innovaciones** (claw con 5 servos, sortLeft/sortRight, depositCenter — eso es no-trivial). Pero no están documentadas como tales.

**Qué falta.** Sección "Innovaciones mecánicas" listando 1-3 cosas que el equipo diseñó originales (vs. parts de kit). Con foto + sketch + explicación de ventaja competitiva.

**Riesgo de NO cambiar.** Medio — 3-4 pts máximo si no se destaca como innovador.

**Riesgo de cambiar.** Bajo.

**Tiempo estimado.** 1 h.

**Pregunta para el equipo.** ¿Cuál es nuestra "feature mecánica" más original?

#### TEMA T7 — Mechanical reliability tests (max 6 pts) ⚠️

**Qué observamos.** **Folder `testing/` está vacío (`.gitkeep` solo)**. No hay logs de tests sistemáticos, ni evidencia de QA.

**Qué falta.** Tests documentados: e.g. "10 corridas de zona de rescate, 8/10 exitosas, fallas: ...". Idealmente con tabla y gráfico.

**Riesgo de NO cambiar.** **MUY ALTO** — automáticamente 0 pts en este criterio. Y este patrón se repite en 4 de 5 secciones del TDP → ~24 pts perdidos en total.

**Riesgo de cambiar.** Bajo (es documentar tests que ya hicieron de forma informal) — pero requiere disciplina nueva (anotar tests futuros en `testing/TEST_LOG.md`).

**Tiempo estimado.** 4 h iniciales (reconstruir histórico de tests + crear template) + ~30 min/semana ongoing.

**Pregunta para el equipo.** ¿Tienen registro de cuántos tests corrieron? ¿Videos? ¿Whatsapp con resultados? Aunque sea reconstruir 5-10 tests recientes.

> **Este es el TEMA de mayor impacto del análisis** — fix sólo este y subimos ~24 pts.

### 3.3 Electronic design (max 24 pts)

Estructura idéntica a la mecánica. Mismo análisis.

#### TEMA T8 — Electronic design structure & diagrams (max 6 pts)

**Qué observamos.** PCB JSON existe en `hardware/electronics/PCB_Main/PCB.json`, hay PDF preview. Falta documento explicativo.

**Riesgo de NO cambiar.** Medio. **Tiempo:** 2 h.

#### TEMA T9 — Electronic sub-modules (max 6 pts)

Cobrar ~1.5 h.

#### TEMA T10 — Electronic innovative solutions (max 6 pts)

**Pregunta clave:** ¿el equipo diseñó una PCB propia o usa breakouts de stock? Por las reglas: "main controller + sensors + actuators integrados en PCB diseñada por el equipo" = 5-6 pts. Si usan breakouts = 3-4 pts máximo.

**Tiempo:** 1 h documentando.

#### TEMA T11 — Electronic reliability tests (max 6 pts) ⚠️

Mismo problema que T7. **Tiempo:** 1.5 h (logs de tests eléctricos: power tree, ruido, etc.).

### 3.4 Software (max 18 pts)

#### TEMA T12 — Software architecture diagrams (max 6 pts)

**Qué observamos.** Hay descripción en docs pero **no hay flowchart formal ni UML ni pseudocode** del main loop ni de las FSM.

**Qué falta.** Mínimo: flowchart del main loop Teensy + flowchart del Main.py + class diagram (si UML aplica) + pseudocode de los algoritmos críticos (line-track, victim detection).

**Riesgo de NO cambiar.** Alto — sin diagrams formales, máximo 1-2 pts.

**Riesgo de cambiar.** Bajo.

**Tiempo estimado.** 4 h (Lucio puede usar draw.io o tldraw + el material de los docs de Gemini/Claude).

> **Este es el segundo TEMA de mayor impacto** — fix sólo este y subimos ~6 pts del TDP + cierra el issue [#41](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/41).

#### TEMA T13 — Software innovative solutions (max 6 pts)

**Qué observamos.** Hay innovaciones reales (YOLOv8 a ONNX en RPi, FSM de rescate parcial, doble validación con sensor de color). Necesitan estar **destacadas**.

**Tiempo:** 1.5 h.

#### TEMA T14 — Software reliability tests (max 6 pts) ⚠️

Mismo patrón. **Tiempo:** 1.5 h.

### 3.5 Performance Evaluation (max 6 pts)

#### TEMA T15 — Performance reliability + insightful evaluation (max 6 pts)

**Qué observamos.** No hay sección de "qué problema tuvimos en competencia y cómo lo arreglamos".

**Qué falta.** 1-2 problemas reales encontrados en testing/competencia, qué módulo causó dificultad, cómo lo solucionaron.

**Riesgo de NO cambiar.** Medio — 1-2 pts.

**Tiempo estimado.** 1.5 h.

**Pregunta para el equipo.** ¿Cuál fue el bug más frustrante que solucionaron? ¿La carga del modelo YOLO en hot path (issue #24)? Tienen una historia ahí, hay que contarla.

### 3.6 Document quality (max 12 pts)

#### TEMA T16 — Contents, Conciseness and Clarity (max 6 pts)

Se evalúa al final. Tener todas las secciones cubiertas + conciso. Riesgo cero si las otras secciones están bien.

#### TEMA T17 — Formatting (max 6 pts) ⚠️

**Qué observamos.** **Si no se usa la plantilla oficial 2026**, puntaje automáticamente 1-2.

**Qué falta.** Descargar `TDP_Template_Line_Maze.docx` desde rescue.rcj.cloud y usarla como base.

**Riesgo de NO cambiar.** Alto — 4 pts perdidos por algo trivial.

**Tiempo:** 30 min descargar + adaptar formato.

> **Este TEMA cuesta 30 min y vale 4 pts. ROI altísimo.**

---

## 4. TEMAS A ANALIZAR — Poster

### TEMA P1 — Team section 5-6 pts (max 6 pts)

**Qué observamos.** No hay poster. Para 5-6 pts: nombre + liga + país + miembros con fotos + roles específicos + **resultados notables y premios**.

**Qué falta:** fotos del equipo + listing de premios (mundial Argentina 2025 mencionado en docs).

**Riesgo de NO cambiar.** Alto — 6 pts perdidos.

**Riesgo de cambiar.** Bajo — Canva.

**Tiempo:** 2 h (sesión de fotos del equipo + redacción).

**Pregunta clave:** ¿Tenemos fotos del equipo en competencia nacional 2025? Si sí, ESAS son las que van.

### TEMA P2 — Hardware Line section 5-6 pts (max 6 pts)

Para 5-6: foto del robot + lista de sensores con tareas + **soluciones innovadoras destacadas** con sketch propio.

**Tiempo:** 3 h (consolidar lo de TDP-T6 + render visual).

### TEMA P3 — Software Line section 5-6 pts (max 6 pts)

Para 5-6: lenguaje + **flowchart del main loop** + algoritmos innovadores con pseudocódigo / **resultados de tests** (gráficos, outputs).

**Riesgo cruzado:** depende de TEMA T12 (diagrams) y T7-T14 (tests). Si esos no están, este tampoco llega a 5-6.

**Tiempo:** 2 h (asumiendo T12 ya hecho).

---

## 5. TEMAS A ANALIZAR — Video

### TEMA V1 — Producción del video (cross-cutting)

**Restricciones duras:**
- 5-7 minutos.
- **Inglés con subtítulos**.
- .mp4 ≤ 500 MB.

**Tiempo total estimado de producción:** ~12-15 h distribuidas en:
- Script en español: 2 h.
- Traducción al inglés + subtítulos: 1 h.
- Filmación de equipo (sección 1) + sección 4 future plans: 2 h.
- Filmación del robot mostrando hardware (sección 2): 2 h.
- Edición usando footage existente para "Robot in Action" (sección 3): 4 h.
- Polish + export: 1 h.

### TEMA V2 — Sección 1 Team Introduction (1.5 min, max 6 pts)

Para 5-6: presentación clara + **fotos del equipo**.

**Material crudo:** asumimos fotos disponibles. Sin fotos = max 3-4 pts.

**Tiempo:** 1 h filmar/editar.

### TEMA V3 — Sección 2 Robot Introduction (1 min, max 6 pts)

Para 5-6: equipo presenta robot **usándolo en cámara** para mostrar hardware + innovaciones + class diagram.

**Material crudo necesario:** robot encendido + persona explicando + close-ups de sensores. NO usar diagrams sólos.

**Tiempo:** 2 h.

### TEMA V4 — Sección 3 Robot In Action (2.25 min, max 6 pts)

Para 5-6: robot en demo **mientras el equipo explica**. No sólo footage.

**Material crudo:** los 5 videos en `software/raspberry/Videos/` son útiles pero sin voiceover en inglés. Hay que regrabar audio sobre ellos o filmar nuevo.

**Tiempo:** 4 h.

### TEMA V5 — Sección 4 Future Plans (0.45 min, max 6 pts)

Para 5-6: plan claro y específico.

**Material:** se puede sintetizar de los issues abiertos del repo (todo lo que sale del análisis de comms y flexibilidad).

**Tiempo:** 1 h.

---

## 6. Plan de acción priorizado

### Fase 1 — Quick wins (esta semana, ~5-6 h)

Cosas de gran ROI con riesgo bajo:

1. **Descargar plantilla TDP oficial** + crear archivo `docs/tdp/TDP-IITA-2026.md` con la estructura. ⏱ **30 min**. → **+4 pts (Formatting)**.
2. **Inicializar `testing/TEST_LOG.md`** con template y reconstruir 5-10 tests recientes. ⏱ **2 h**. → **+10 pts** (parcial en 4 secciones de tests).
3. **Diagramas de bloques** (Lucio) en draw.io / tldraw — main loop Teensy + RPi + comms. ⏱ **3 h**. → **+6-12 pts** (TDP T12 + cierra issue #41).
4. **Lista de fotos requeridas** + asignar a alguien para colectar/sacar. ⏱ **30 min** prep, ~2 h ejecutar después. → **+6-12 pts** (Poster + Video).

**Subtotal Fase 1:** ~6-7 h, **~26-38 pts ganados** vs. estado base.

### Fase 2 — Cuerpo del TDP (próximas 2 semanas, ~20 h)

Documentar lo técnico que ya existe en formato rúbrica. Distribuir entre Lucio (TDP), Benjamin (electrónica + mecánica), Enzo (review + integration plan), Lautaro (firmware diagrams).

5. T1 Requirements (2 h)
6. T2 Project Plan (1.5 h)
7. T3 Integration Plan (2 h)
8. T4-T6 Mechanical (5 h)
9. T8-T10 Electronic (4.5 h)
10. T13 Software innovations (1.5 h)
11. T15 Performance evaluation (1.5 h)
12. T16-T17 Document polish (2 h)

### Fase 3 — Poster + Video (próximas 3 semanas, ~18 h)

13. P1-P3 Poster en Canva (~7 h).
14. V1-V5 Video script + filmación + edición + traducción (~12-15 h).

### Fase 4 — Tests sistemáticos ongoing

Mantener `testing/TEST_LOG.md` actualizado con cada ensayo. **30 min/semana** después del setup inicial.

---

## 7. Estimación de puntaje — antes vs. después de Fase 1+2+3

| Sección | Hoy estimado | Post-Fase 1 | Post-Fase 1+2 | Post-Fase 1+2+3 |
|---|---|---|---|---|
| TDP Project Planning (18) | 0-3 | 3 | 14-16 | 14-16 |
| TDP Mechanical (24) | 1-3 | 6 | 18-22 | 18-22 |
| TDP Electronic (24) | 1-3 | 6 | 18-22 | 18-22 |
| TDP Software (18) | 2-4 | 8-10 | 14-16 | 14-16 |
| TDP Performance (6) | 0 | 1 | 5-6 | 5-6 |
| TDP Document (12) | 1-2 | 5-6 | 9-11 | 9-11 |
| Poster (18) | 0 | 0 | 6-9 | 16-18 |
| Video (24) | 0 | 0 | 0 | 20-22 |
| **TOTAL (144)** | **5-15** | **29-32** | **84-102** | **114-133** |
| **% del máximo** | **3-10 %** | **20-22 %** | **58-71 %** | **79-92 %** |

> **Lectura:** la Fase 1 (sólo 6-7 h de trabajo bien dirigido) **multiplica el puntaje por ~3x**. Las fases 2-3 lo llevan a competitivo internacional.

---

## 8. Verificación de fidelidad técnica (¿la doc se corresponde con la realidad?)

Cruce entre los `docs/es/` existentes y el código actual del repo:

| Doc afirma… | Código dice… | ¿Coincide? |
|---|---|---|
| "FSM de rescate no bloqueante" (analisis-integral-ingenieria) | `actualizarRescate()` en `main.cpp:126-254` SÍ es FSM | ✅ |
| "Comparación strings por puntero (P1 bug)" (varios docs) | `drivebase.cpp:68` usa `strcmp(...)` correctamente | ❌ Doc desactualizado — fixeado |
| "Encoders sin volatile" | `drivebase.h:24` tiene `volatile long pulseCount;` | ❌ Doc desactualizado — fixeado |
| "Modelo YOLO se carga cada vez en rescate" | `Main.py:121-145` carga UNA vez con warmup | ❌ Doc desactualizado — fixeado |
| "delay() bloqueante en pinza" | `main.cpp:164,225,939-940,976-978,1152` sigue presente | ✅ Doc actual |
| "Sin heartbeat serial" | confirmed en main.cpp | ✅ Doc actual |

**Conclusión.** Hay docs **desactualizados** que dicen que ciertos bugs P0/P1 siguen ahí cuando ya se arreglaron. Riesgo: si el equipo copia ciegamente al TDP, queda mal por contradicciones con el código real.

**Recomendación.** Antes de armar el TDP, **revisar cada análisis técnico contra el código actual** y eliminar afirmaciones obsoletas. Tiempo estimado: 2 h (Enzo o el coach).

---

## 9. Issues nuevos sugeridos

Cubriendo los gaps cross-cutting que no encajan en los issues existentes:

| Tema | Cubre TEMAs | Owner sugerido |
|---|---|---|
| Inicializar `testing/TEST_LOG.md` con template + 5-10 tests recientes | T7, T11, T14, T15 | Benjamin + Enzo |
| Sesión de fotos del equipo (banco, competencia 2025, retratos) | P1, V2 | Coach + cualquiera |
| Validar fidelidad técnica de los análisis existentes en `docs/es/` antes del TDP | T16, defensa contra contradicciones | Enzo |
| Lista BOM (Bill of Materials) actualizada | T8, T17 | Benjamin |

Plus comentarios concretos en los **issues existentes** #46 (TDP), #45 (Poster), #55 (Video), #41 (Diagramas) con checklists alineados a esta doc.

---

## 10. Anexos — links oficiales

- **Reglas oficiales 2026:** [`RCJRescueLine2026-final.pdf`](https://junior.robocup.org/wp-content/uploads/2026/02/RCJRescueLine2026-final.pdf)
- **TDP Template:** [`TDP_Template_Line_Maze.docx`](https://rescue.rcj.cloud/rules/2026/TDP_Template_Line_Maze.docx)
- **Rúbrica TDP:** [`Line&Maze_TDP_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Line&Maze_TDP_Rubrics_RCJ_Rescue_2026.pdf)
- **Rúbrica Poster:** [`Line&Maze_Poster_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Line&Maze_Poster_Rubrics_RCJ_Rescue_2026.pdf)
- **Rúbrica Video:** [`Presentation_Video_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Presentation_Video_Rubrics_RCJ_Rescue_2026.pdf)
- **Guía de Video:** [`Presentation_Video_Guideline_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Presentation_Video_Guideline_RCJ_Rescue_2026.pdf)
- **Scoring Example:** [`ScoringExample.pdf`](https://rescue.rcj.cloud/rules/2026/ScoringExample.pdf)
- **BOM Template:** [`BOM_Template.xlsx`](https://rescue.rcj.cloud/rules/2026/BOM_Template.xlsx)
- **Judge Training Guide 2026:** [`RCJ_Rescue_Line_2026_Judge_training_guideline.pdf`](https://rescue.rcj.cloud/rules/2026/RCJ_Rescue_Line_2026_Judge_training_guideline.pdf)
- **Weighted Victims Build Guide:** [`Weighted_Victims_Definition_and_Build_Guide.pdf`](https://rescue.rcj.cloud/rules/2026/Weighted_Victims_Definition_and_Build_Guide.pdf)
- **Forum:** [Documents and Rubrics for 2026](https://junior.forum.robocup.org/t/documents-and-rubrics-for-2026/5268)

---

## 11. Recomendación final

**Mi recomendación honesta:** que Lucio, Lautaro, Benjamin y Enzo se sienten **una tarde entera** a ejecutar la Fase 1 completa (descargar plantilla, crear archivo TDP esqueleto, iniciar TEST_LOG, primer pase de diagrams). Eso solo lleva al equipo de ~10 % del puntaje a ~22 % en 6-7 horas — la curva de retorno más empinada de toda la campaña.

Después, distribuir la Fase 2 entre los 4 con deadlines semanales y revisión cruzada. Coach hace pase final.

**Lo más urgente que sí o sí depende del coach:** organizar la **sesión de fotos** (TEMA P1, V2) — sin fotos no se llega a 5-6 pts ni en Poster ni en Video. **2 horas de sábado en la escuela con buena luz.**

---

*Análisis dirigido por @gviollaz, asistido por Claude Code (Opus 4.7). Material fuente: rúbricas oficiales 2026 + lectura cruzada de los 12 docs de análisis técnico existentes en `docs/es/` + estado del código a 2026-05-10. Filosofía: TEMAS A ANALIZAR — el equipo decide qué tomar; el auditor presenta el material.*
