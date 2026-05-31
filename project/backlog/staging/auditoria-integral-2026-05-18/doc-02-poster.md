# Auditoría integral 2026-05-18 · doc-02 · ESTADO DEL POSTER

> **Dominio:** Poster oficial RCJ Rescue Line 2026 — Issues [#45](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/45) (Armado de Poster) y [#94](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/94) (Sesión de fotos).
> **Auditor:** Claude Code (Opus 4.8) por encargo de @gviollaz.
> **Fecha:** 2026-05-31. **Mundial:** Incheon, Corea, 2026-06-30 → 07-06 (**a 30 días**).
> **Owner del poster:** @Laumonteros (Laureano Monteros). **Coordinación:** @enzzo19 + @benjaminvillagran.
> **Alcance:** SOLO lectura. Estado vs. rúbrica oficial Poster 2026, puntaje estimado hoy, acciones de mayor retorno.
> **Filosofía:** TEMAS A ANALIZAR — cada gap lleva riesgo-no-fix / riesgo-fix / tiempo. El equipo decide.

---

## 0. Resumen ejecutivo

**Diagnóstico en una línea:** el Poster **no existe** — no hay archivo, no hay carpeta `docs/files/poster/`, no hay PDF, no hay evidencia verificable de que el proyecto Canva siquiera se haya creado. El puntaje hoy es **0 / 18 pts**.

**Esto NO es un hallazgo nuevo** respecto de la auditoría de documentación del 2026-05-10 ([`docs/es/analisis-documentacion-rubricas-2026-05-10.md`](../../../../docs/es/analisis-documentacion-rubricas-2026-05-10.md) §2.2 y §4). Lo que **sí es nuevo** y empeora el cuadro:

1. **Pasaron 21 días desde ese análisis y el poster sigue en 0 pts.** No hubo ni un commit, ni un comentario de avance de @Laumonteros, ni se creó la carpeta. El gap no se está cerrando — está congelado.
2. **El owner está incomunicado en este frente.** En #45 hay **dos pedidos de acceso al Canva sin responder** (uno de @enzzo19, uno de @gviollaz pidiendo "un link solo de visualización"). No hay confirmación de que el Canva exista.
3. **Quedan 30 días al mundial.** La ventana para ejecutar las ~7 h del poster + las dependencias (fotos, diagramas, tests) se está cerrando, y el poster compite por tiempo con TDP (no existe), Video (no existe) y ~15 bugs P0/P1 de las auditorías técnicas.

**Puntaje estimado:**

| Momento | Puntaje Poster | % del máximo |
|---|---|---|
| **HOY (2026-05-31)** | **0 / 18** | **0 %** |
| Potencial con plan de acción completo | 16-18 / 18 | 89-100 % |
| Realista a 30 días, con priorización agresiva | 11-15 / 18 | 61-83 % |

**Las 3 acciones de mayor retorno (detalle en §6):**
1. **Crear el proyecto Canva HOY + compartir link de visualización en #45** (desbloquea todo, 30 min). Es el cuello de botella político, no técnico.
2. **Resolver #94 (sesión de fotos) este fin de semana** (2 h) — sin fotos del equipo no hay 5-6 en P1, sin foto del robot no hay 5-6 en P2. Es la dependencia física de mayor impacto.
3. **Cargar P1 (Team) completo** apenas haya fotos — es la sección de 6 pts más barata porque el material (premio nacional 2025, roles, país) ya existe.

---

## 1. La rúbrica oficial Poster 2026 (referencia)

**Documento oficial:** [`Line&Maze_Poster_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Line&Maze_Poster_Rubrics_RCJ_Rescue_2026.pdf)

El poster son **3 Key Elements**, cada uno puntuado 0 / 1-2 / 3-4 / **5-6 (excelente)**. Máximo = **3 × 6 = 18 pts**.

| Key Element | 1-2 (básico) | 3-4 (bueno) | **5-6 (excelente)** |
|---|---|---|---|
| **Team** | Nombre, liga, país, miembros con rol genérico | + fotos de los miembros + roles específicos | + **resultados notables y premios** + **fotos del equipo en competencias nacionales** |
| **Hardware Line** | Foto del robot + lista de sensores/motores SIN descripción | + descripción de cada sensor con la tarea asociada | + **soluciones innovadoras de hardware destacadas** con imagen/sketch propio + explicación |
| **Software Line** | Sólo lenguaje + intento confuso de explicación | + flowchart del main loop comprensible | + **algoritmos y métodos relevantes** explicados con pseudocódigo / flowchart / **resultados de tests** (outputs, gráficos) |

**Sugerencias del comité para "innovative":**
- **Hardware Line:** chasis custom, mecanismo de captura de víctimas, cualquier solución innovadora.
- **Software Line:** estrategia de zona de evacuación, detección de víctimas, line following, cualquier algoritmo innovador.

**Regla de lectura clave:** lo que separa **5-6 de 3-4** en los tres criterios es siempre lo *innovador destacado* + *evidencia propia* (sketch, pseudocódigo, resultados de test). Un poster prolijo pero genérico topea en 3-4 → **9-12/18**. Para pasar de ahí hay que mostrar lo que el equipo hizo de original.

> **Nota de verificación:** el desglose de la rúbrica no pude reconfirmarlo contra el PDF oficial en esta sesión (sin acceso de red al PDF). Lo tomo de [`docs/es/analisis-documentacion-rubricas-2026-05-10.md`](../../../../docs/es/analisis-documentacion-rubricas-2026-05-10.md) §1.2, que ya lo había transcrito. **Acción de control:** que un humano abra el PDF oficial y confirme los 18 pts y los 3 criterios antes de cerrar el poster (5 min).

---

## 2. Estado real verificado en el repo (2026-05-31)

Lo que sigue NO son supuestos — es lo que está (o no está) en el checkout actual de `feature/initialize-testing-log`.

### 2.1 Lo que NO existe

| Esperado (según #45 / análisis 05-10) | Estado verificado |
|---|---|
| Carpeta `docs/files/poster/` con el PDF | ❌ **No existe.** `docs/` sólo tiene `en/` y `es/`. No hay `docs/files/`. |
| Archivo del poster (`.pdf`, `.png`, fuente de diseño) | ❌ **No existe ningún archivo de poster** en todo el repo (`git ls-files` sin match de poster). |
| README de proceso del poster (Enzo lo pidió explícito en #45) | ❌ **No existe.** Ningún `.md` documenta el armado del poster. |
| Link al proyecto Canva compartido (pedido en #45 y en README) | ❌ **No publicado.** No está en #45, ni en ningún README. Dos pedidos de acceso quedaron sin responder. |
| Carpeta `journal/` con avances | ❌ Sólo `.gitkeep` (vacía). |

### 2.2 Estado de los issues

**Issue #45 — Armado de Poster** (autor @enzzo19, OPEN, 4 comentarios, **sin assignee formal en GitHub**):
- Enzo asignó a @Laumonteros el armado en Canva, con entrega del PDF en `docs/files/poster/archivo.pdf` mantenido actualizado.
- **Comentario 1 (Enzo):** "te mandé solicitud de acceso para ver el archivo y como va el avance".
- **Comentario 2 (Gustavo):** "te mandé solicitud de acceso nuevamente, puedes dejar aquí un link que sea solo de visualización (NO EDICIÓN) para que pueda ver los avances?"
- **Comentario 3 (Gustavo):** vuelco completo de la rúbrica Poster con checklist P1/P2/P3 (post PR #92).
- **Lectura:** dos pedidos de acceso sin respuesta = **señal fuerte de bloqueo**. O el Canva no se creó, o se creó privado y no se compartió. En cualquier caso, **no hay avance verificable y el coach no puede auditarlo**. Este es el problema #1 del poster, y es de **comunicación/ownership, no técnico**.

**Issue #94 — Sesión de fotos del equipo y robot** (autor @gviollaz, OPEN, **0 comentarios**, assignees: gviollaz, enzzo19, benjaminvillagran):
- Lista detallada de fotos requeridas para Poster (P1, P2) y Video. Bien especificado (foto grupal, retratos individuales, robot lateral/frontal/top, foto en competencia nacional 2025, renders de innovaciones).
- **0 comentarios = 0 avance.** No hay evidencia de que la sesión se haya hecho ni agendado.
- **Erratum a corregir:** la lista de #94 dice "Lautaro" en "_Foto individual de cada miembro (Enzo, Benjamin, Lautaro, Lucio)_". **No existe ningún Lautaro** — es Laureano Monteros (@Laumonteros). Hay que corregirlo cuando se ejecute la sesión para que no falte la foto del firmware-lead real. (Mismo error ya corregido en otros docs por los commits 5a868ea / 6ffba5d / 59960e6.)

**Issues relacionados que son dependencias del poster (todos OPEN, sin avance):**
- **#41 — Diagrama de bloques/flujo del software** (autor @enzzo19, etiquetado P0 en el título). Es la dependencia directa de **P3 (flowchart del main loop)**. No hay diagramas formales en el repo — sólo un Mermaid embebido en [`docs/es/analisis-arquitectura-robotica.md`](../../../../docs/es/analisis-arquitectura-robotica.md).
- **TEST_LOG** ([`testing/TEST_LOG.md`](../../../../testing/TEST_LOG.md)): **fue inicializado** (142 líneas, esta rama, commit c42e535) — buena noticia estructural — pero las 4 tablas de resultados (`[MECH]`, `[ELEC]`, `[SW]`, `[PERF]`) están **100 % vacías** ("_(vacío — próximos tests acá)_"). Es la dependencia de **P3 (resultados de tests)** y hoy no aporta nada citable.
- **#94 (fotos)**: dependencia de **P1 y P2**.

---

## 3. Activos que SÍ existen y sirven para el poster

No todo es desierto. Hay materia prima reutilizable que baja el costo de cada sección:

| Activo | Ubicación | Sirve para |
|---|---|---|
| **Premio: campeón nacional argentino 2025** | Confirmado en [`docs/es/analisis-integral-ingenieria.md:11`](../../../../docs/es/analisis-integral-ingenieria.md) y `:487` ("El equipo IITA Salta ganó el campeonato nacional argentino en 2025") | **P1 Team 5-6** — es exactamente el "resultado notable/premio" que separa 3-4 de 5-6. **Activo de oro, gratis.** |
| **PCB main propia** (no es kit) | [`hardware/electronics/PCB_Main/`](../../../../hardware/electronics/PCB_Main): `PCB.json` (580 KB), `ROBOCUP.SHEET.pdf`, `pcb-preview.pdf` | **P2 Hardware 5-6** — "PCB diseñada por el equipo" es innovación destacable con imagen propia (ya hay PDF preview). |
| **Diagrama Mermaid de arquitectura** | [`docs/es/analisis-arquitectura-robotica.md`](../../../../docs/es/analisis-arquitectura-robotica.md) | **P3 Software** — punto de partida del flowchart (hay que re-dibujarlo prolijo, pero el contenido está). |
| **Descripción de sensores con tarea** | [`docs/es/analisis-integral-ingenieria.md`](../../../../docs/es/analisis-integral-ingenieria.md), CLAUDE.md (stack table) | **P2 Hardware 3-4→5-6** — BNO055 (orientación/yaw), VL53L0X ToF, APDS9960 color, NewPing ultrasonido, encoders. Listado con tarea ya redactado. |
| **Innovaciones de hardware identificadas** | Claw 5 servos (depositCenter/sortLeft/sortRight), chasis 4WD para rampas, PCB propia | **P2 Hardware 5-6** — son las 1-3 innovaciones destacables. Falta sólo el sketch/foto. |
| **Innovaciones de software identificadas** | YOLOv8→ONNX en RPi 4B, FSM de rescate no-bloqueante, doble validación víctima (cámara + sensor color), protocolo serial binario propio | **P3 Software 5-6** — algoritmos relevantes a destacar con pseudocódigo. |
| **Stack/lenguajes** | CLAUDE.md: Python (OpenCV+YOLO) en RPi, C++ (PlatformIO) en Teensy, UART 115200 | **P3 Software 1-2 base** — ya redactado. |
| **Benchmarks RPi (gráficos)** | [`software/raspberry/imagenes/benchmarks/`](../../../../software/raspberry/imagenes/benchmarks): 3 PNG de latencia/IPS MobileNetV2 | **P3 Software 5-6** — son "resultados/gráficos" reutilizables si se contextualizan (¡ojo! son de MobileNetV2, no necesariamente del modelo final YOLO — verificar antes de publicarlos para no mentir en el poster). |
| **País / liga / miembros** | CODEOWNERS, CLAUDE.md | **P1 Team 1-2 base** — Argentina, Rescue Line, los 4 miembros + coach. |

**Conclusión de §3:** el contenido **textual** para llegar a 5-6 en los 3 criterios está ~70 % disponible. **Lo que falta es casi todo visual** (fotos, sketches, flowchart prolijo) + el acto de **maquetarlo en Canva**. Es trabajo de diseño y de sesión de fotos, no de investigación técnica.

---

## 4. Estimación de puntaje detallada por criterio

> Puntaje **HOY** = 0 en todo porque el poster no existe. Las columnas de la derecha proyectan qué se alcanza según cuánto se ejecute.

| Criterio (max 6 c/u) | HOY | Si sólo se maqueta lo que existe (sin fotos ni diagramas nuevos) | Con #94 (fotos) hecho | Con #94 + #41 (diagramas) + tests | Bloqueantes para el máximo |
|---|---|---|---|---|---|
| **P1 — Team** | **0** | 1-2 (texto sin fotos) | **5-6** | 5-6 | Fotos individuales + foto en nacional 2025. Premio ya disponible. |
| **P2 — Hardware Line** | **0** | 3-4 (lista de sensores + texto de innovaciones, sin foto del robot ni sketch) | 4-5 | **5-6** | Foto del robot (#94) + sketch/render de claw y chasis. PCB ya ilustrable. |
| **P3 — Software Line** | **0** | 1-2 (sólo lenguaje + texto) | 1-2 | **5-6** | Flowchart prolijo (#41) + pseudocódigo + resultados de tests reales (TEST_LOG vacío hoy). |
| **TOTAL / 18** | **0** | **5-8** | **10-13** | **16-18** | |

**Lecturas:**
- **El "piso barato" es 5-8/18**: con sólo volcar a Canva el material textual existente, sin sacar una sola foto, el poster ya deja de ser 0. P2 es el que más sube en este escenario (la lista de sensores + innovaciones ya está escrita).
- **El salto grande (a 10-13) lo da la sesión de fotos (#94)**, que es 2 h de un sábado y desbloquea P1 a tope y mejora P2.
- **El techo (16-18) depende de #41 (diagramas) y de tener ≥1 test real cargado**, que son las dependencias más caras y compartidas con el TDP. Por eso conviene atacarlas igual (sirven doble).
- **P3 es el criterio más difícil y el último en cerrar** — está acoplado a dos issues que hoy no avanzan (#41 sin diagramas formales, TEST_LOG vacío). Si a 2 semanas del mundial P3 sigue trabado, **aceptar 3-4 en P3** (flowchart comprensible aunque no innovador) y poner la energía en P1+P2 a 5-6 → eso ya da **13-14/18**, competitivo.

---

## 5. TEMAS A ANALIZAR — Poster

> Re-evaluación de los temas P1-P3 del análisis 05-10, **actualizada a 30 días del mundial** y con el estado real verificado. Cada uno: qué falta / riesgo-no-fix / riesgo-fix / tiempo / pregunta.

### TEMA P0 (NUEVO) — Desbloquear el ownership del poster ⚠️ EL MÁS URGENTE

**Qué observamos.** El poster no tiene avance verificable y @Laumonteros no respondió dos pedidos de acceso al Canva. No es un problema de rúbrica — es de **ejecución y comunicación**. Todos los demás temas P1-P3 dependen de que esto se destrabe.

**Riesgo de NO cambiar.** **MUY ALTO.** Si en 30 días el cuello de botella sigue siendo "no sabemos si Laureano arrancó", el poster llega a 0 o cerca de 0 al mundial → **−18 pts garantizados**. Es el riesgo más grande de todo el documento.

**Riesgo de cambiar.** Nulo.

**Tiempo.** 30 min (crear Canva compartido + pegar link de visualización en #45) + decisión de coach sobre ownership.

**Pregunta para el equipo (directa).** @Laumonteros: ¿el Canva existe? Si sí, pegá el link de **solo-visualización** en #45 hoy. Si no arrancaste o no tenés tiempo, **decilo ahora** para que Enzo reasigne — a 30 días no hay margen para silencio. ¿Querés que Benjamin o Lucio te ayuden con la maqueta mientras vos seguís con firmware?

---

### TEMA P1 — Team section (max 6)

**Qué falta.** Fotos individuales de los 4 + foto del equipo en competencia nacional 2025. El resto (nombre, liga Rescue Line, país Argentina, roles específicos, **premio nacional 2025**) **ya existe** en docs.

**Riesgo de NO cambiar.** Alto si falta el bloque de fotos/premio → topea en 1-2. Pero es la sección **más barata de llevar a 5-6** porque sólo le falta el componente visual.

**Riesgo de cambiar.** Bajo (maquetar + sesión de fotos).

**Tiempo.** 1 h de maqueta (asumiendo fotos ya tomadas vía #94).

**Pregunta clave.** ¿Hay fotos del equipo en la competencia nacional 2025 en algún Drive/WhatsApp/cámara? Si existen, **esas son las que van** y P1 llega a 6 casi sin esfuerzo. Si no existen, una foto grupal actual con el robot alcanza para 5.

---

### TEMA P2 — Hardware Line section (max 6)

**Qué falta.** (a) Foto del robot (lateral/frontal/top) — depende de #94. (b) Sketch/render propio de 1-3 innovaciones (claw 5 servos, chasis 4WD, PCB). La lista de sensores-con-tarea y el texto de innovaciones ya están redactados (§3).

**Riesgo de NO cambiar.** Medio. Sin foto del robot ni sketch propio, topea en 3-4 (lista + descripción). El sketch propio es lo que lo lleva a 5-6.

**Riesgo de cambiar.** Bajo. El render de claw/chasis puede salir de screenshots de Fusion 360 + edición; la PCB ya tiene PDF preview reutilizable.

**Tiempo.** 2 h (consolidar texto + capturar/editar renders + maquetar).

**Pregunta clave.** Confirmado que la PCB de `hardware/electronics/PCB_Main/` es de diseño propio (no kit) — entonces destacarla como innovación. ¿Cuál es la innovación de hardware #1 que el equipo quiere que el jurado recuerde? (la claw con sort/deposit es la candidata más fuerte).

---

### TEMA P3 — Software Line section (max 6) ⚠️ EL MÁS ACOPLADO

**Qué falta.** (a) **Flowchart prolijo del main loop** — depende de #41 (hoy sólo hay Mermaid). (b) Pseudocódigo de 1-2 algoritmos innovadores (line tracking, victim detection con doble validación, evac strategy). (c) **Resultados de tests** (gráficos/outputs) — depende de que TEST_LOG.md tenga datos reales (hoy vacío).

**Riesgo de NO cambiar.** **Alto** — es la sección que más fácil se queda en 1-2 (sólo lenguaje + texto). Y es la que más impresiona al jurado técnico cuando está bien.

**Riesgo de cambiar.** Bajo en esfuerzo de poster, pero **gateado por dos dependencias externas** (#41 + TEST_LOG) que hoy no avanzan.

**Tiempo.** 2 h de maqueta **asumiendo #41 ya hecho**. Si #41 no está, suma el costo de los diagramas (otra cosa, ~3-4 h, owner Lucio).

**Pregunta clave.** ¿Para cuándo Lucio puede tener el flowchart de #41? Eso destraba P3 **y** el criterio equivalente del TDP. Si #41 no llega a tiempo, ¿aceptamos un flowchart "comprensible pero simple" (3-4 pts) para no bloquear el poster?

**Cross-reference honesto:** este TEMA P3 es la cara visible de tres issues estancados (#41 diagramas, TEST_LOG vacío, y la disciplina de testing del TDP T7/T11/T14). **No se puede llevar P3 a 5-6 sin destrabar esos.** Si el equipo quiere maximizar retorno a 30 días, la decisión racional es: **P1+P2 a 5-6 (seguro), P3 a 3-4 (aceptable)** = 13-14/18, y subir P3 sólo si #41 y un test real llegan a tiempo.

---

## 6. Plan de acción priorizado por retorno (a 30 días)

> Ordenado por **retorno por hora**, con el mundial a 30 días. La regla es: primero lo que desbloquea, después lo barato-y-seguro, al final lo caro-y-acoplado.

### Acción 1 — Destrabar ownership (HOY, 30 min) → habilita los 18 pts

- @Laumonteros crea/comparte el Canva con link de **solo-visualización** pegado en #45. Si no puede sostener el frente, lo dice y Enzo reasigna o suma apoyo (Benjamin/Lucio en maqueta).
- **Sin esto, todo lo demás no arranca.** Es el TEMA P0.

### Acción 2 — Maquetar el "piso barato" con material existente (2 h) → +5-8 pts sobre 0

- Volcar a Canva, **sin esperar fotos**: nombre/liga/país/roles/premio 2025 (P1 texto), lista de sensores-con-tarea + texto de innovaciones HW (P2), lenguaje/stack (P3 texto).
- Deja placeholders marcados donde van fotos y diagramas. **El poster pasa de 0 a ~5-8 en una tarde.**

### Acción 3 — Resolver #94 sesión de fotos (2 h, un sábado) → P1 a 5-6, P2 a ~5

- Foto grupal + 4 retratos + robot lateral/frontal/top + (si existe) foto nacional 2025.
- **Corregir "Lautaro"→"Laureano"** en la lista de #94 antes de ejecutar.
- Es la dependencia física de mayor impacto: con esto P1 cierra y P2 sube.
- **Depende del coach** (organizar el sábado en el lab) — explicitado por el propio análisis 05-10 como "lo más urgente que sí o sí depende del coach".

### Acción 4 — Sketches/renders de innovaciones HW (1-2 h) → P2 a 5-6

- Screenshots de Fusion 360 de claw + chasis, editados. PCB ya tiene preview reutilizable.

### Acción 5 (acoplada/condicional) — Cerrar P3 a 5-6 (depende de #41 + 1 test real)

- Si Lucio entrega el flowchart de #41 y se carga **al menos un test real** en TEST_LOG (ej. "10 corridas zona rescate, 8/10"), P3 sube a 5-6.
- **Si no llegan a tiempo:** aceptar flowchart simple (3-4) y cerrar el poster en 13-14/18. **No bloquear la entrega del poster esperando P3 perfecto.**

**Resumen de retorno acumulado:**

| Después de… | Puntaje Poster esperado |
|---|---|
| Acción 1 (sola, sin maquetar) | 0 (pero desbloqueado) |
| Acción 1 + 2 | 5-8 / 18 |
| + Acción 3 (fotos) | 10-13 / 18 |
| + Acción 4 (sketches) | 12-15 / 18 |
| + Acción 5 (P3 completo) | **16-18 / 18** |

---

## 7. Riesgos y decisiones que el coach debe tomar

1. **Ownership de #45 (decisión política, urgente).** El silencio de @Laumonteros es el riesgo #1. Decidir esta semana: ¿se le da un ultimátum suave con deadline (ej. "Canva compartido para el martes") o se reasigna/co-asigna ya? A 30 días, "esperar a ver si responde" es la opción más cara.
2. **Sesión de fotos (#94) depende del coach.** Sin un sábado agendado, P1 y P2 no llegan a 5-6. Es la acción de mayor impacto que **no** puede delegar.
3. **Aceptar P3 imperfecto si #41 no llega.** Decisión a tomar ~2 semanas antes del mundial: ¿poster 13-14/18 entregado a tiempo, o jugar a 16-18 arriesgando que P3 trabe la entrega? Recomendación del auditor: **entregar 13-14 seguro** y subir sólo si las dependencias llegan solas.
4. **Verificar el PDF oficial de la rúbrica (5 min).** Confirmar que sigue siendo 3 criterios × 6 = 18 pts antes de cerrar (esta auditoría se basó en la transcripción del análisis 05-10, no pudo abrir el PDF).
5. **No publicar benchmarks ajenos como propios.** Los 3 PNG en `software/raspberry/imagenes/benchmarks/` son de MobileNetV2 — si se usan en P3 como "resultados de tests", contextualizar honestamente o no usarlos. Un jurado técnico que detecta un dato inflado castiga más que un dato faltante.

---

## 8. Relación con las auditorías previas (no se repite, se cita)

- **Auditoría documentación 2026-05-10** ([`docs/es/analisis-documentacion-rubricas-2026-05-10.md`](../../../../docs/es/analisis-documentacion-rubricas-2026-05-10.md)): ya estableció Poster = 0/18 hoy → 16-18 potencial, ~7 h. **Este doc confirma que en 21 días no se movió** y agrega: (a) el bloqueo de ownership (P0 nuevo), (b) la priorización a 30 días con escenario "piso barato 5-8", (c) la verificación física del repo, (d) el erratum "Lautaro" en #94.
- **Meta-issues #97 / #98** (plan de ejecución TDP+Poster+Video, autor @gviollaz, ambos OPEN, **0 comentarios cada uno**): el plan existe pero **nadie lo comentó ni lo empezó**. El poster es una de sus ramas y está igual de quieto.
- **Auditorías técnicas (RESILIENCIA #53-#119, CORRECTITUD #120-#128):** no tocan el poster directamente, pero **alimentan P3**: cada bug arreglado y testeado es un "resultado de test" citable. El gap de testing (TEST_LOG vacío) que esas auditorías señalan es el mismo que bloquea P3.

---

## 9. Conclusión

**El poster está en 0/18 y, a diferencia del TDP, el bloqueo principal NO es de contenido — es de ejecución y ownership.** El material textual para 5-6 en los tres criterios está ~70 % disponible en el repo (premio nacional 2025, lista de sensores, innovaciones HW/SW, PCB propia, Mermaid base). Lo que falta es: (1) que alguien efectivamente **maquete en Canva** — y hoy ni siquiera hay confirmación de que el proyecto exista —, (2) la **sesión de fotos (#94)**, parada hace 21 días, y (3) los diagramas/tests para rematar P3.

**El retorno por hora es altísimo en las primeras acciones y decreciente después:** 30 min destraban el ownership, 2 h llevan el poster de 0 a 5-8 con material que ya existe, otras 2 h de fotos lo llevan a 10-13. Llegar a 13-14/18 es perfectamente alcanzable a 30 días **si el ownership se destraba esta semana**. El techo de 16-18 depende de #41 y del testing, que el equipo debería atacar igual porque rinden doble (poster + TDP).

**La única acción que el coach no puede delegar y que define el resultado: agendar la sesión de fotos y exigir a @Laumonteros el link del Canva esta semana.** Sin esas dos, el poster llega a 0 al mundial por inacción, no por falta de capacidad técnica.

---

*Auditoría dirigida por @gviollaz, asistida por Claude Code (Opus 4.8). Fuente: rúbrica Poster 2026 (vía transcripción en `docs/es/analisis-documentacion-rubricas-2026-05-10.md`), estado real del repo en `feature/initialize-testing-log` al 2026-05-31, issues #45/#94/#41/#97/#98 leídos vía `gh`. Filosofía: TEMAS A ANALIZAR — el auditor presenta el material, el equipo decide.*
