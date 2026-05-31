# Auditoría integral 2026-05-18 · doc-03 · ESTADO DEL VIDEO

> **Dominio:** Presentation Video oficial RCJ Rescue 2026 (sección 3 del paquete de documentación: TDP + Poster + **Video**).
> **Issues de referencia:** [#55 Armado de VIDEO](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/55) (owner @benjaminvillagran) · [#94 Sesión de fotos equipo+robot](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/94) (owner @gviollaz + @enzzo19 + @benjaminvillagran) · meta [#97](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/97) / [#98](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/98).
> **Auditoría previa que NO repito:** `docs/es/analisis-documentacion-rubricas-2026-05-10.md` §1.3, §2.3, §5 (V1–V5). Cito y agrego **lo nuevo del 18-05**: inspección técnica real del footage crudo con ffprobe + extracción de frames, que el análisis del 10-05 no había hecho (asumía "probablemente útil para sección 3").
> **Fecha de corte de datos:** 2026-05-31. Branch auditado: `feature/initialize-testing-log` (contenido espejado en `main`).
> **Framing:** todo finding es **TEMA A ANALIZAR** — riesgo-de-no-hacer / riesgo-de-hacer / tiempo / pregunta concreta. No es "bug a fixear".

---

## 0. Resumen ejecutivo

**Diagnóstico en una línea:** el video oficial **no existe** (0 archivos de video editado, 0 script, 0 subtítulos, 0 audio en inglés, 0 carpeta `docs/video/`), y **el único material crudo que hay — los 5 clips en `software/raspberry/Videos/` — es prácticamente inutilizable como footage de presentación**, porque son grabaciones POV de la cámara del propio robot (vista fisheye mirando el piso de la zona de evacuación), no tomas externas del robot en acción.

**Esto es lo NUEVO respecto del 10-05.** El análisis previo estimó esos 5 clips como "probablemente útiles para la sección 3 Robot In Action". La inspección técnica del 18-05 (ffprobe + frames) **desmiente ese supuesto**: ver §3. La consecuencia es que el costo real de producción del video es **más alto** de lo presupuestado, porque hay que **filmar footage externo nuevo casi desde cero**, no sólo "editar lo existente + ponerle voz".

**Puntaje estimado HOY: 0 / 24 pts (0 %).** Sin cambios respecto del 10-05. Nada se ejecutó en estas 3 semanas (ver §2).

**Potencial realista con plan de acción:** 18–22 / 24 pts. El video es **puntaje grande que NO toca el robot** → se puede producir durante el freeze de firmware del 20-05 sin riesgo técnico (esto es una ventaja estratégica, no un detalle).

**La acción de mayor retorno, y el cuello de botella de todo:** ejecutar [#94](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/94) — **la sesión de fotos Y filmación externa del robot**. Sin footage externo nuevo del robot ejecutando + del equipo, el video tiene techo de 3–4 pts por sección sin importar cuánto se edite. Depende del coach agendar un sábado. Es la pieza crítica del camino.

---

## 1. La rúbrica oficial Video 2026 (recordatorio operativo)

Documentos: [`Presentation_Video_Rubrics_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Presentation_Video_Rubrics_RCJ_Rescue_2026.pdf) · [`Presentation_Video_Guideline_RCJ_Rescue_2026.pdf`](https://rescue.rcj.cloud/rules/2026/Presentation_Video_Guideline_RCJ_Rescue_2026.pdf).

**Restricciones duras (descalifican o recortan si se incumplen):**

| Restricción | Valor | Estado hoy |
|---|---|---|
| Duración | 5–7 min (pasados 7 min sólo se evalúan los primeros 7) | ❌ no hay video |
| Idioma | **inglés obligatorio** (subtítulos EN opcionales o en idioma original) | ❌ todo el material es es / sin audio |
| Formato | `.mp4`, **≤ 500 MB** | ⚠️ a tener en cuenta en export |
| Uso | se proyecta en Incheon + posible web oficial RoboCup | — |

**4 secciones puntuadas (cada una 0 / 1-2 / 3-4 / 5-6 pts → total 24):**

| # | Sección | Tiempo sugerido | Qué separa 5-6 de 3-4 |
|---|---|---|---|
| 1 | **Team Introduction** | 1 min 30 s | Presenta al equipo **con fotos de ellos**; cómo se formó, roles, qué los inspiró |
| 2 | **Robot Introduction** | 1 min | Presenta al robot **usándolo EN CÁMARA** para mostrar hardware + innovaciones + class diagram |
| 3 | **Robot In Action** | 2 min 15 s | Robot en acción **mientras el equipo explica qué hace** (no footage mudo) |
| 4 | **Future Plans** | 0 min 45 s | Plan de futuro claro con metas concretas en RoboCup |

**Regla de oro de la rúbrica, repetida en 2 de 4 secciones:** *mostrar al robot HACIENDO / al robot EN PANTALLA*, no sólo describirlo con voz sobre diagramas. Esto es exactamente lo que el footage actual **no** permite (§3).

---

## 2. Qué existe hoy en el repo (estado al 2026-05-31)

### 2.1 Lo que NO existe (igual que el 10-05, nada se movió)

- ❌ **Video editado** — no hay `.mp4`/`.mov` de presentación en ninguna parte del árbol.
- ❌ **Carpeta `docs/video/`** — no existe (tampoco `docs/tdp/`, `docs/poster/`, `docs/files/`). Verificado: `ls` da "No such file or directory".
- ❌ **Script / guión** — no existe ningún archivo de guión. El único lugar del repo donde aparecen las palabras "voiceover / subtítulo / guión / script de video" es **el propio análisis del 10-05** (`docs/es/analisis-documentacion-rubricas-2026-05-10.md`), es decir el *plan*, no la *ejecución*.
- ❌ **Audio / voiceover en inglés** — inexistente. Además los clips crudos **no tienen pista de audio** (§3).
- ❌ **Subtítulos** (`.srt` / `.vtt`) — no existen.
- ❌ **Fotos del equipo / robot externas** — `git ls-files` filtrado por imágenes de robot/equipo/competencia devuelve **vacío**. Las únicas imágenes en el repo son renders CAD viejos en `hardware/mechanical/_legacy/CAD/Imagenes/` y 3 PNG de benchmarks de ML en `software/raspberry/imagenes/benchmarks/`. Ninguna sirve para video.
- ❌ **Class diagram del software** (insumo directo de la sección 2 del video) — issue [#41](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/41) sigue **OPEN**, sin diagrama formal en el repo. Sólo hay un Mermaid embebido en `analisis-arquitectura-robotica.md`.

### 2.2 Lo único que existe: 5 clips de footage crudo

`software/raspberry/Videos/` — commiteados **todos juntos en un solo commit** (`3ddc89d feat: migrate all content from legacy repository`). **No hubo ni un commit nuevo de video desde la migración legacy.** Son material viejo (nombres con fechas 2025-08, "diciembremuestr"), no grabaciones hechas para el video oficial.

| Archivo | Tamaño |
|---|---|
| `3rvideo.mp4` | 13.7 MB |
| `diciembremuestr.mp4` | 10.9 MB |
| `video_2025-08-23_23-40-37.avi` | 11.8 MB |
| `video_2025-08-24_00-00-18.mp4` | 11.5 MB |
| `xdsdsd.mp4` | 9.8 MB |

> Nota cruzada (no es de mi dominio pero impacta): estos videos están commiteados como blobs en Git, lo que el issue [#69](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/69) [P2] ya marca para migrar a Git LFS. No afecta el puntaje del video, pero si se agregan los clips finales del video oficial (que serán pesados) al repo sin LFS, el repo se infla. **Recomendación:** el video oficial final NO va al repo Git — va a Drive/YouTube y se linkea. Sólo el script y los subtítulos (texto) van al repo.

### 2.3 Estado de los issues de video (qué se movió desde 10-05)

| Issue | Título | Owner | Creado | Última actualización | Estado |
|---|---|---|---|---|---|
| #55 | Armado de VIDEO | @benjaminvillagran | 2026-04-29 | **2026-05-10** | OPEN, 3 comentarios (último = checklist V1-V5 del coach el 10-05) |
| #94 | Sesión de fotos equipo + robot | @gviollaz, @enzzo19, @benjaminvillagran | 2026-05-10 | 2026-05-10 | OPEN, **0 comentarios**, 0 ejecución |
| #41 | Diagrama de bloques/flujo SW (insumo sección 2) | @luciouriel2011 | — | — | OPEN |

**Lectura:** desde el 10-05 (hace 3 semanas) **nadie tocó los issues de video**. #94 nació muerto el mismo día del análisis y no tuvo un solo movimiento. La razón es legítima y está documentada en el propio plan del coach (issue [#106](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/106) §5 y [#107](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/107)): la W20 priorizó **quick-wins de confiabilidad/performance antes del freeze 2026-05-20**, y el video se etiquetó explícitamente como "puntaje grande pero NO toca el robot → se puede trabajar incluso durante el freeze". O sea: **la postergación fue una decisión, no un olvido** — pero la ventana de "durante el freeze" empieza el 20-05 y la deadline real se acerca (§5).

---

## 3. 🔴 HALLAZGO NUEVO (no estaba en el análisis del 10-05): el footage crudo NO sirve para footage de presentación

Esto es lo que aporta esta auditoría sobre la del 10-05. El análisis previo escribió: *"Material crudo (footage): 5 archivos … **Probablemente útil para sección 3 'Robot In Action'**"*. Inspeccioné los 5 archivos con `ffprobe` y extraje frames. **El supuesto no se sostiene.**

### 3.1 Datos técnicos (ffprobe)

| Archivo | Resolución | Aspect | FPS | Duración | **Audio** | Códec |
|---|---|---|---|---|---|---|
| `3rvideo.mp4` | 960×720 | ~4:3 | 30 | 119.8 s | **NINGUNO** | h264 |
| `diciembremuestr.mp4` | 962×720 | ~4:3 | 30 | 92.3 s | **NINGUNO** | h264 |
| `video_2025-08-23_…avi` | 640×480 | 4:3 | 20 | 142.6 s | **NINGUNO** | mpeg4 |
| `video_2025-08-24_…mp4` | 640×480 | 4:3 | 20 | 146.0 s | **NINGUNO** | mpeg4 |
| `xdsdsd.mp4` | 960×720 | ~4:3 | 30 | 86.8 s | **NINGUNO** | mpeg4 |

Total footage crudo: **~587 s (~9.8 min)**.

**Tres problemas técnicos duros:**
1. **Sin pista de audio en ninguno** (ffprobe sólo reporta `codec_type=video`). No es "footage al que hay que cambiarle el audio" — es footage **mudo**. El voiceover hay que crearlo 100% nuevo de todas formas.
2. **Baja resolución y 4:3.** El guideline pide horizontal 16:9, idealmente 1080p (issue #94 lo dice explícito). 640×480 y 960×720 a 4:3 se ven viejos proyectados en pantalla grande en Incheon. Reescalar a 1080p 16:9 mete pillarboxing/estiramiento.
3. **20 fps en dos clips** (los .avi/.mp4 de agosto) — se nota entrecortado.

### 3.2 El problema GRAVE: es POV de la cámara del robot, no tomas externas del robot

Extraje frames a los 3–10 s de 4 de los clips. **Los 4 muestran lo mismo:** vista en primera persona **desde la cámara onboard del robot** (lente fisheye, mirando hacia abajo el piso blanco de la zona de evacuación), con las **víctimas plateadas (bolas de telgopor con glitter)** y las paredes de la zona de rescate al fondo. Se ven el horizonte curvado por el fisheye, las paredes blancas/verdes/naranjas de la arena, y las bolas plateadas. **En ningún frame se ve el robot** — porque la cámara ES el robot.

Esto significa que el footage es **debug/calibración de visión** (el mismo stream 960×720 que consume el pipeline de OpenCV/YOLO en la RPi), capturado para tunear detección de víctimas, **no** material de presentación.

**Por qué esto rompe la rúbrica:**

| Sección | Qué pide la rúbrica para 5-6 | ¿Sirve el footage POV? |
|---|---|---|
| 2. Robot Introduction | Robot **en cámara** mostrando hardware/sensores/claw | ❌ No se ve el robot. Es lo contrario: el ojo del robot. |
| 3. Robot In Action | Robot **visiblemente** siguiendo línea, depositando víctimas, superando obstáculos | ❌ No se ve el robot ejecutando. Sólo se ve el piso/víctimas desde su POV. |

**Uso residual posible (no nulo, pero menor):** un par de segundos de POV pueden meterse como *inserto* ilustrativo ("así ve el robot la víctima → así la detecta", con overlay de la detección YOLO encima) dentro de la sección 3 o de Software innovations. Pero **NO puede ser el material principal** de ninguna sección, y por sí solo no levanta ninguna sección por encima de 3-4 pts.

**Conclusión del hallazgo:** el costo de producción real es mayor que el presupuestado el 10-05, porque la sección 3 ("Robot In Action") — la más larga (2:15) y la que el plan suponía "casi resuelta con lo existente, 4 h de edición" — en realidad requiere **filmar tomas externas nuevas del robot ejecutando en pista**, no editar lo viejo. Re-estimo tiempos en §5.

---

## 4. TEMAS A ANALIZAR — Video (actualizados al 18-05)

Mantengo la numeración V1–V5 del análisis del 10-05 para trazabilidad, y actualizo cada uno con el hallazgo nuevo.

### TEMA V1 — Producción del video (cross-cutting) · estado: **sin arrancar**

**Qué observamos.** Cero artefactos de producción (script, audio, subtítulos, timeline de edición). Decisión consciente de posponer al post-freeze (#106), legítima, pero la ventana ya casi se abre.

**Riesgo de NO hacer.** **MUY ALTO.** 24 pts en juego (16.7 % del total de documentación de 144). Y a diferencia del TDP, el video tiene un **piso de tiempo irreducible**: aunque tengas todo el material, editar + traducir + grabar voz + subtitular + exportar lleva días de calendario, no se hace la noche anterior.

**Riesgo de hacer.** **Mínimo / nulo sobre el robot.** No toca firmware ni visión. Es la tarea ideal para ejecutar *durante* el freeze de código (20-05 en adelante) sin riesgo técnico.

**Tiempo estimado (re-estimado al alza por §3).** **~15–18 h** (antes 12-15 h). El delta es por filmar footage externo nuevo de la sección 3 en lugar de reutilizar el viejo. Desglose en §5.

**Pregunta concreta para el equipo.** ¿Cuál es la **deadline real de subida del video** a la organización RCJ? Esto define si vamos relajados o contra reloj. (El mundial es 30-06 al 06-07; típicamente los docs se suben 2-4 semanas antes → deadline probable **principios/mediados de junio**. Hay que confirmarlo YA, porque define toda la planificación.)

### TEMA V2 — Sección 1: Team Introduction (1.5 min, max 6 pts) · estado: **bloqueado por #94**

**Qué observamos.** No hay fotos ni footage del equipo en el repo (`git ls-files` → vacío para fotos de equipo). Sin fotos, techo de 3-4 pts por rúbrica explícita ("introduces the team **with some pictures of them**").

**Qué falta.** Footage corto de cada uno de los 3 alumnos (Laureano, Lucio, Benjamin) + Enzo presentándose (5 s c/u) + foto grupal + narrativa de cómo se formó el equipo / qué los inspiró. Si existe foto de **competencia nacional 2025**, ESA suma (la rúbrica premia "competencias nacionales").

**Riesgo de NO hacer.** Medio-alto (3 pts perdidos sobre 6).

**Tiempo.** 1 h (filmar) + 1 h (editar), **dentro de la sesión #94**.

**Pregunta.** ¿Hay fotos/videos de la competencia nacional 2025 en algún Drive/WhatsApp/celular del equipo? Rescatarlas vale puntos.

### TEMA V3 — Sección 2: Robot Introduction (1 min, max 6 pts) · estado: **bloqueado por #94 + #41**

**Qué observamos.** Esta es la sección donde el hallazgo §3 pega más fuerte. **No hay una sola toma del robot visto desde afuera.** Y el class diagram que la rúbrica pide mostrar "rapidito" no existe (issue #41 OPEN).

**Qué falta.** (a) Footage del robot **encendido, frente a cámara**, con un alumno señalando y explicando sensores (BNO055, ToF VL53L0X, ultrasonido, cámara), claw de servos, PCB; (b) close-ups de esos componentes; (c) un class/architecture diagram presentable en pantalla 2-3 s.

**Riesgo de NO hacer.** Alto. Sin robot en cámara, techo 3-4 pts (la rúbrica lo dice: *"si sólo hay diagrams + voiceover, máximo 3-4"*).

**Riesgo de hacer.** Bajo.

**Tiempo.** 2 h filmar (sesión #94) + dependencia de #41 para el diagrama (que igual hay que hacer para el TDP T12, así que se comparte el costo).

**Pregunta.** ¿El class diagram lo saca Lucio en draw.io/tldraw esta semana (cierra #41 + sirve a TDP + sirve al video, triple uso)?

### TEMA V4 — Sección 3: Robot In Action (2.25 min, max 6 pts) · estado: **el footage existente NO alcanza** (cambio vs 10-05)

**Qué observamos.** **Aquí está el cambio principal de esta auditoría.** El plan del 10-05 daba esta sección como "4 h de edición sobre los 5 clips existentes". El hallazgo §3 muestra que esos clips son POV del robot, no tomas externas → **no muestran al robot ejecutando**. Para 5-6 pts hace falta el robot **visiblemente** siguiendo línea, reaccionando a verdes, entrando a la zona, depositando víctimas, superando rampa/obstáculo/seesaw — todo en tomas externas.

**Qué falta.** Filmar **footage externo nuevo** de corridas reales (cámara en trípode/gimbal apuntando a la pista) + voiceover en inglés explicando qué hace en cada tramo.

**Riesgo de NO hacer.** Alto (es la sección más larga, 2:15 → la que más pesa visualmente). Con sólo POV mudo, techo 2-3 pts.

**Riesgo de hacer.** Bajo (filmación + edición), pero **depende de que el robot esté corriendo bien** — lo que cruza con el objetivo de confiabilidad 8/10 (issue #114). Conviene filmar después de los quick-wins de confiabilidad de la W20, cuando el robot ande más estable, para tener tomas de corridas exitosas.

**Tiempo.** 2 h filmar corridas (idealmente aprovechando una sesión de banco/pista ya planificada, ej. el protocolo de banco de Benjamin en #117) + 4 h edición + se le puede intercalar 10-20 s de POV existente como inserto ilustrativo.

**Pregunta.** ¿Cuándo hay una sesión de pista con el robot andando bien que podamos grabar en paralelo? (No filmar una sesión aparte — filmar la que ya van a hacer.)

### TEMA V5 — Sección 4: Future Plans (0.75 min, max 6 pts) · estado: **fácil, material ya disponible**

**Qué observamos.** Es la sección más barata. El contenido sale directo de los issues abiertos: roadmap a confiabilidad 8/10 (#114), mejoras de visión/comms, plan post-mundial. Material textual ya existe.

**Qué falta.** Guionar 45 s + grabar voz + visual (puede ser slides simples + B-roll del equipo trabajando).

**Riesgo de NO hacer.** Medio (1-2 pts), pero es el quick-win de la sección.

**Tiempo.** 1 h.

**Pregunta.** ¿Las metas concretas para Incheon ya están escritas en #114? (Sí → copiar y resumir en inglés.)

---

## 5. Puntaje estimado HOY y plan de mayor retorno

### 5.1 Estimación de puntaje

| Sección | Max | **Hoy (31-05)** | Techo si se hace SIN footage externo nuevo (sólo POV + slides) | Potencial con sesión #94 ejecutada bien |
|---|---|---|---|---|
| 1. Team Introduction | 6 | **0** | 3-4 | 5-6 |
| 2. Robot Introduction | 6 | **0** | 2-3 | 5-6 |
| 3. Robot In Action | 6 | **0** | 2-3 | 5-6 |
| 4. Future Plans | 6 | **0** | 4-5 | 5-6 |
| **TOTAL** | **24** | **0 (0 %)** | **11-15 (46-63 %)** | **20-22 (83-92 %)** |

**Lectura clave:** el "techo sin footage externo" (11-15 pts) muestra **cuánto cuesta saltarse la sesión #94**: ~7-8 pts de diferencia. Esos 7-8 pts dependen casi enteramente de **2-4 h de filmación externa del robot + equipo**. Es el mejor ratio puntos/hora de todo el paquete de video.

> Coincide con el rango "20-22" que el análisis del 10-05 fijó como potencial — lo confirmo. Lo que cambió es el **camino**: ya no es "editar lo viejo", es "filmar nuevo". El destino es el mismo; la ruta es más cara.

### 5.2 Acciones por retorno (de mayor a menor ROI)

1. **🥇 CONFIRMAR LA DEADLINE REAL DE SUBIDA DEL VIDEO** (15 min, coach/Enzo). Es lo primero. Sin saber la fecha límite no se puede planificar nada. El video es el documento con **piso de tiempo de calendario irreducible** (no se improvisa). Buscar en el portal RCJ / forum la fecha de entrega de documentos 2026. **Bloquea todo lo demás.**

2. **🥇 EJECUTAR #94 — sesión combinada de fotos + filmación externa** (1 sábado, ~4-5 h, coach agenda). Es **el cuello de botella de las secciones 1, 2 y 3 a la vez**. Un solo sábado con el robot encendido + el equipo presente + cámara en trípode resuelve: footage del equipo (V2), robot en cámara + close-ups (V3), y corridas externas (V4). **Depende del coach** (es el único que puede juntar a los 4 + robot un sábado). Sin esto, el video tiene techo de ~13/24. **Esta es la recomendación #1 del informe.**

3. **🥈 Guionar el video en inglés** (~3 h, Benjamin + quien tenga mejor inglés). Script de 5-7 min, 4 secciones, conciso (el propio Enzo lo dijo en #55: "no fragmentos de 30 s sobre un tema, mencionar lo más relevante en palabras"). Se puede hacer **antes** de filmar (el script guía qué filmar). Si nadie tiene inglés fuerte → IA (ElevenLabs / Google TTS) para el voiceover, como ya sugirió el coach en #55.

4. **🥈 Cerrar #41 (class/architecture diagram)** (~3-4 h, Lucio, draw.io/tldraw). **Triple uso:** insumo de la sección 2 del video + criterio T12 del TDP + criterio Software del Poster. Máximo apalancamiento por hora.

5. **🥉 Editar + traducir + subtitular + exportar** (~5-6 h, Benjamin). Post-filmación. CapCut o DaVinci Resolve (gratis). Subtítulos en inglés. Export `.mp4` ≤ 500 MB. Verificar duración 5-7 min.

6. **🥉 Rescatar material histórico** (~1 h, equipo). Buscar en Drive/WhatsApp/celulares: fotos de competencia nacional 2025 (suman en V2) y cualquier toma externa del robot ya grabada. Puede reducir lo que hay que filmar nuevo.

### 5.3 Secuencia recomendada (todo post-freeze 20-05, sin tocar robot)

```
Día 0  → confirmar deadline (15 min)  [BLOQUEANTE]
Día 1  → guión EN (3 h) + #41 diagrama (4 h, en paralelo, Lucio)
Día 2  → SÁBADO sesión #94: filmar equipo + robot + corridas externas (4-5 h)  [CUELLO DE BOTELLA]
Día 3-4→ edición + voiceover EN + subtítulos (6 h)
Día 5  → export, verificar duración/peso/idioma, subir + linkear en repo (1 h)
```

Total: **~15-18 h de trabajo** distribuidas en ~5 días de calendario. **Crítico:** el "Día 2" (sesión #94) tiene que pasar lo antes posible porque es el único que requiere juntar a todos + robot un fin de semana, y todo lo demás depende de su output.

---

## 6. Riesgos y dependencias cruzadas

- **Dependencia dura con #94:** las secciones 1, 2 y 3 (18 de 24 pts) están **bloqueadas** por la sesión de fotos/filmación. Si #94 no se ejecuta, el video no pasa de ~13/24 por más esfuerzo de edición que se ponga. **Es el riesgo #1.**
- **Dependencia con #41:** la sección 2 quiere mostrar el class diagram; #41 está OPEN. Bajo riesgo porque #41 igual hay que hacerlo para el TDP.
- **Dependencia con confiabilidad (#114):** para tener buenas tomas de "Robot In Action" (sección 3) el robot tiene que **completar corridas**. Filmar después de los quick-wins de confiabilidad de la W20 da mejores tomas. Si se filma con el robot fallando, las tomas no sirven o muestran un robot poco confiable (mala imagen ante jueces).
- **Riesgo de calendario:** el video es el único documento con **piso de tiempo irreducible**. El TDP/Poster se pueden empujar hasta último momento; el video no (editar + traducir + voz + subtítulos + export es secuencial y lleva días). **Si la deadline está cerca y #94 no se agendó, el video es el documento en mayor riesgo de quedar incompleto o de baja calidad.**
- **Riesgo de formato (bajo, evitable):** exportar y olvidar verificar ≤ 7 min / ≤ 500 MB / idioma inglés. Checklist final de export obligatorio.
- **Git/LFS (#69):** no meter el `.mp4` final pesado al repo sin LFS. Subir a Drive/YouTube y linkear; al repo sólo el script (texto) y los `.srt`.

---

## 7. Verificación de fidelidad (lo que afirmo vs. lo que verifiqué)

| Afirmación | Cómo lo verifiqué | Resultado |
|---|---|---|
| "No existe video oficial" | `git ls-files` + búsqueda `.mp4/.mov/.avi` en todo el árbol | ✅ sólo los 5 clips crudos en `software/raspberry/Videos/` |
| "No hay carpeta docs/video/" | `ls -d docs/video docs/tdp docs/poster docs/files` | ✅ "No such file or directory" en las 4 |
| "Los 5 clips son POV del robot, sin audio" | `ffprobe` (sin stream de audio) + extracción de 4 frames | ✅ confirmado: fisheye POV mirando piso/víctimas, 0 audio |
| "Nada se movió desde 10-05" | `gh issue view 55/94 --json updatedAt` + `git log --since=2026-05-10` | ✅ #55 last update 10-05; #94 sin comentarios; 0 commits de video |
| "No hay fotos externas de equipo/robot" | `git ls-files` filtrado por jpg/png de robot/team/competencia | ✅ vacío (sólo CAD legacy + benchmarks ML) |
| "#41 class diagram sigue abierto" | `gh issue view 41 --json state` | ✅ OPEN |

---

## 8. Síntesis para el coach (1 párrafo)

El video está en **0/24 y no se movió desde el 10-05** — postergación consciente por el freeze, legítima, pero la ventana de trabajo (post-20-05) ya se abre. La novedad de esta auditoría es que **el material crudo que creíamos aprovechable no sirve**: son grabaciones POV de la cámara del robot (sin audio, 4:3, fisheye), no tomas del robot en acción, así que la sección 3 hay que **filmarla de nuevo en externo**, no editarla. El camino al potencial de 20-22/24 pasa **sí o sí por la sesión #94** (un sábado con robot + equipo + cámara en trípode), que resuelve 3 de las 4 secciones de golpe y depende de que vos la agendes. Antes que nada: **confirmar la deadline real de subida del video** — es el único documento con piso de tiempo irreducible y el de mayor riesgo de quedar corto si se arranca tarde.

---

*Auditoría doc-03 (Video) del paquete integral 2026-05-18. Dominio: estado del video vs. rúbrica oficial RCJ Rescue 2026. Asistido por Claude (Opus 4.8, 1M). Material fuente: rúbrica/guideline oficiales 2026 + issues #55/#94/#97/#98/#106/#41 + inspección técnica ffprobe de los 5 clips crudos + lectura del análisis previo `docs/es/analisis-documentacion-rubricas-2026-05-10.md`. Sólo lectura — no se modificó código ni `software/**` ni `hardware/**`. Filosofía: TEMAS A ANALIZAR (riesgo-no-hacer / riesgo-hacer / tiempo / pregunta), el equipo decide qué tomar.*
