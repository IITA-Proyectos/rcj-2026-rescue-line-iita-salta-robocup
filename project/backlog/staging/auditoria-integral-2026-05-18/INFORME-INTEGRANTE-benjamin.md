# Informe de desempeño — Benjamin Villagran (@benjaminvillagran)

> **Para:** Enzo Juarez (@enzzo19), coach del equipo · **De:** auditoría integral 2026-05-18 (rol coach senior)
> **Integrante:** Benjamin Villagran (@benjaminvillagran) — RPi/visión · hardware/electrónica · banco de pruebas
> **Repo:** `rcj-2026-rescue-line-iita-salta-robocup` · **Branch auditada:** `feature/initialize-testing-log` (post-merge PR #101 → `main`; contenido espejado en `main`)
> **Fecha:** 2026-05-31 · **Mundial:** RoboCup Junior Rescue Line, Incheon (Corea), 2026-06-30 → 07-06 (**30 días**)
> **Naturaleza:** este es un informe de *desempeño de persona* para uso de coaching, no una auditoría de bugs. Combina datos de actividad git/gh con la calidad técnica del subsistema. Los hallazgos críticos se enmarcan como **temas a decidir** (riesgo de no-corregir · riesgo de corregir · tiempo), nunca como "bug a fixear".

---

## 0. Síntesis para el coach (leer esto si no leés nada más)

Benjamin es **el contribuidor #2 del repo después de vos** y, por lejos, **la mejor pluma de ingeniería del equipo**. Su `cambios_de_hardware.md` (717 líneas) es el mejor documento del repositorio: cita reglamento 2026, evalúa opciones con pros/contras y anticipa modos de falla físicos. Su código de fiabilidad es competente, no cosmético. Tiene amplitud (toca los 4 subsistemas) y cadencia sostenida (feb→may, último commit 2026-05-24).

**Su problema no es el talento ni el esfuerzo. Es la disciplina de entrega.** Casi todo su trabajo P0/P1 de fiabilidad —y el TEST_LOG que la rúbrica del TDP más valora— está **varado en PR #129 (OPEN, +5707/−506, 39 archivos, 0 reviews)** y **no está en `main`**. Si hoy se flashea el robot desde `main`, no tiene esos fixes.

> **El riesgo más alto del equipo asociado a Benjamin no es que su código falle. Es que su buen código nunca llegue a `main` antes de Incheon.** Tu trabajo de coaching con él, a 30 días del mundial, es esencialmente **uno de proceso de entrega**, no de capacidad técnica.

| Eje | Calificación | Una línea |
|---|---|---|
| Capacidad técnica | **Alta** | Criterio de ingeniería más maduro del equipo. |
| Volumen / cadencia | **Alta** | #2 del repo, sostenido, reciente. |
| Documentación de hardware | **Sobresaliente** | `cambios_de_hardware.md` es lo mejor del repo. |
| Documentación de banco (testing) | **Mixta / incompleta** | Sabe hacerlo, pero n=1 y no mergeado. |
| Disciplina de proceso | **Débil (su talón de Aquiles)** | PRs gigantes, su mejor trabajo sin mergear. |

---

## 1. Resumen de actividad (datos duros, verificados)

### 1.1 Commits

| Métrica | Valor | Verificación |
|---|---|---|
| Commits únicos (todas las ramas, ambas identidades) | **28** | `git log --all --author=...` |
| Commits en `main` | **15** | — |
| Identidad primaria `benjaminvillagran <villagranbenjamin52@gmail.com>` | 23 | `git shortlog -sne --all` |
| Identidad secundaria `Benjamin Villagran <148703811+...>` | 4–5 | (merges + 3 commits) |
| Ranking del repo | **#2** | gviollaz 26+ · Benjamin 23 · resto del equipo ≤5 c/u |

> **Nota de higiene:** commitea bajo **dos identidades git** (cuenta web vs. cliente local). No afecta la atribución pero ensucia `git shortlog`. Se resuelve en 5 min unificando `user.email`. Confirmado además que **no existe ningún "Lautaro"** — ese es Laureano Monteros, persona distinta.

**Cadencia mensual** (sostenida y reciente, lo cual es bueno):

| Mes | Commits | Qué hizo |
|---|---|---|
| 2026-02 | 1 | Arranque (encoders atómicos) |
| 2026-03 | 12 | **Pico** — visión TFLite/NCNN, warmup, BOM, esquemático, drivebase pybricks |
| 2026-04 | 6 | Heartbeating, navegación de salida, ultrasonido bloqueante, doc hardware |
| 2026-05 | 9 | Timeouts, revert claw, sprint fiabilidad, TEST_LOG, TDP |

Último commit: **2026-05-24** (7 días antes de este informe). El detalle preocupante: ese push fue a la rama abierta PR #129, **no a `main`**.

### 1.2 "41.378 líneas" — cuidado, es engañoso

`git log --numstat` declara ~41.378 líneas agregadas, pero **~34.000 son PDF binario del PCB** (`ROBOCUP.SHEET.pdf` + `pcb-preview.pdf` versionados como texto en el commit `073b8a2`). Descontando binarios, **el aporte real de código/doc ronda 5.000–6.000 líneas** — sigue siendo el mayor del equipo después del coach, pero no hay que citarle "41k" a nadie: no es real.

### 1.3 Pull Requests

| PR | Estado | Reviews | Aprobación formal | Tamaño |
|---|---|---|---|---|
| #34 `fix(teensy): lectura atomica de encoders` | MERGED | 1 (COMMENTED) | 0 | +115/−41 |
| #35 `fix(vision): velocidad primera inferencia` | MERGED | 1 (COMMENTED) | 0 | +614/−53 |
| #43 `hardware(docs): esquemático/BOM/pines` | MERGED | 3 (COMMENTED) | 0 | +963/−2 |
| #50 `Mejora velocidad inferencia + balance blancos` | MERGED | **0** | 0 | +1946/−363 |
| **#129 `Bugs prioritarios`** | **OPEN** | **0** ✅verificado vía gh | **0** | **+5707/−506, 39 files** |

Dos señales de proceso, ambas verificadas:
- **PR #50 (+1946/−363) se mergeó con 0 reviews** → viola la Regla de Oro #1 del `CLAUDE.md` ("al menos un review"). El revisor habitual sos vos y nunca quedó un `APPROVED` formal trazable en GitHub (siempre `COMMENTED`); el merge se hace por acuerdo en clase.
- **PR #129 es materialmente irreviewable:** mezcla firmware + RPi + systemd + el TDP completo (**duplicado**: `TDP.md` y `docs/tdp/TDP-IITA-2026.md`, 458 líneas idénticas cada uno) + 14 assets PNG/SVG + TEST_LOG + un `image.png` suelto en la raíz. Nadie revisa eso con rigor a 30 días del mundial.

### 1.4 Issues

- **Abiertos/creados por él:** #51, #49, #40 (Documentación Electrónica), #38 (Clonar SD), #31 — buen uso de issues para encuadrar su propio trabajo. (#38 sigue OPEN.)
- **Asignados:** **30** confirmados vía gh (el resumen interno citaba ~50; el número trazable hoy es 30, igualmente **desproporcionado para un alumno**). Es el "dueño" de facto del cluster RPi/hardware/comms y de casi toda la serie de fiabilidad #57–#76.

### 1.5 Mensajes de commit

**Buenos.** 25/28 siguen Conventional Commits en español (`fix(teensy):`, `feat(vision):`, `hardware(docs):`) — cumple Regla de Oro #7 mejor que el promedio del equipo. Defectos menores: espacios sobrantes (`fix(comms) :`), un typo en cuerpo (`eliminanacion`), 2 mensajes no-convencionales.

---

## 2. Calidad del trabajo

### 2.1 Foco

Amplio, casi **demasiado** amplio: visión RPi + firmware Teensy + documentación de hardware + comms. Es una fortaleza (entiende el sistema completo, es el integrador natural) y a la vez un riesgo (se reparte entre 4 frentes y carga ~30 issues). La amplitud es genuina, no superficial: en cada subsistema hay trabajo de fondo, no solo retoques.

### 2.2 Tests documentados — el punto mixto

Este es **el foco de su dominio de banco de pruebas** y donde más matiz hay. El issue #93 marcó el TEST_LOG como el ítem de mayor impacto del TDP (~24 pts de la rúbrica).

- **En `main` (rama auditada): el TEST_LOG está VACÍO.** Verificado: las 4 categorías (`MECH`/`ELEC`/`SW`/`PERF`) dicen literalmente `(vacío — próximos tests acá)`. Solo está el ejemplo didáctico T-000. El esqueleto lo inicializó **el coach** (`c42e535`), no Benjamin.
- **En PR #129 (sin mergear): Benjamin SÍ lo llenó**, y con datos reales (verificado en `git show af270d2:testing/TEST_LOG.md`):
  - **T-001** `[MECH][ELEC][PERF]` — medición física: LiPo 12.6→12.5 V en 5 min reposo, ~1 h hasta 10.5 V, error `runDistance()` ~1–2 cm, `runAngle()` ±1°. Estrés 10 min `speed=60` + pickup marcado **PARTIAL** (campo "voltaje final no registrado").
  - **T-002** `[SW][PERF]` — desde el `systemd` real con `journalctl`: **line-following 91.33 FPS**, **rescate/depósito 22.25–22.40 FPS** (TFLite + anti-flash + AGCWD + tracker), transición Teensy→RPi confirmada, `frames_sent` 1→2204.

**Evaluación honesta de esos tests:**
- ✅ Son **tests reales con números reales**, no inventados. T-002 cita logs concretos.
- ⚠️ **n=1 por test.** La rúbrica de fiabilidad valora repetibilidad (X/10). Falta pickup X/10, deposit 5+5, matriz de confusión de color.
- ⚠️ Varios campos **"no registrado"** (iluminación; batería en T-002) → resta valor citable.
- ⚠️ El acompañante `TEST_LOG_AUTO.md` está **explícitamente marcado como AI-generado** (extracción de constantes del código, NO tests medidos). Es útil como inventario pero **no es banco de pruebas** y no debe presentarse como evidencia física.
- ✅ `MEDICIONES_PENDIENTES.md` es un **plan de sesión de banco impecable** (~45 min, 9 mediciones priorizadas, con dónde va cada una en el TDP). **Prueba que Benjamin sabe exactamente qué falta medir.**

> **Conclusión del dominio banco:** Benjamin **entiende perfectamente la disciplina de testing** (el plan y las 2 entradas lo demuestran). Pero la ejecución está **incompleta (n=1, campos faltantes) y —peor— no mergeada**. La afirmación de PR #129 "Closes #93" es **optimista**: el log existe con 2 tests parciales, no con la batería completa que el TDP necesita.

### 2.3 Convenciones

Cumple bien: Conventional Commits, idioma español (Regla #5), documentación de hardware en el archivo canónico (Regla #6). **Donde falla es en el flujo de PR** (Reglas #1 "review" y #3 "probar en banco antes de mergear, anotar en TEST_LOG"): mergeó sin review (#50) y revirtió en `main` sin anotar en banco.

### 2.4 Reincidencia de bugs / proceso

No hay reincidencia de *bugs de código* atribuibles a él (su código es correcto donde existe). La reincidencia es **de patrón de proceso**: PRs sobredimensionados (#50, #129), trabajo que no aterriza en `main`, archivos basura commiteados. Es un patrón, no un evento aislado.

---

## 3. FORTALEZAS concretas (verificadas, no halago)

1. **Documentación de hardware de nivel profesional.** `hardware/cambios_de_hardware.md` (717 líneas, **autoría 100% suya**, verificado por `git log` del archivo) documenta 4 mejoras con el formato exacto que pide la rúbrica del TDP: Problema → Opciones → Solución → Pros/Contras, **citando reglamento 2026**. Ejemplos concretos de su criterio:
   - **LED 12V + APDS9960 como sensor de reflectancia** (regla §3.9): justifica físicamente por qué bajar la ganancia de `AGAIN_4X` a `AGAIN_1X` y cómo distinguir blanco difuso de plateado especular por canal Clear + IR. Nivel de ingeniería genuino.
   - **Pin de conductividad para víctimas falsas** (§3.10/§3.10.3): y —notablemente— **anticipa el modo de falla del cable físico** (fatiga por flexión repetitiva de la garra) recomendando cable siliconado/jumper con alivio de tensión. Pensar el modo de falla mecánico antes de que ocurra es madurez de ingeniero, no de alumno.
   - **ESP32 para SuperTeam** y **finales de carrera**: descarta alternativas (HC-05/HC-06, pitch del BNO055) con análisis de trade-offs honesto.

2. **Honestidad técnica.** `docs/tdp/code-reliability-evidence-2026.md` tabula cada mecanismo de fiabilidad con archivo y línea, **separa explícitamente "mecanismos en código" de "mediciones físicas"**, y cierra con el caveat correcto: *"Physical testing must still validate the real-world effect of these safeguards."* No infla performance que no midió. Es el antídoto exacto al riesgo opuesto (afirmar sin medir).

3. **Código de fiabilidad competente.** El `runDistance()` con timeout no bloqueante + `serviceMotionBackgroundTasks()` resuelve **dos hallazgos de RESILIENCIA a la vez** (#60 timeout y #59 motion-no-actualiza-claw). El diseño con **feature flags por issue** (`priority_fix_flags.h`, default-off para el riesgoso #63) es ingeniería defensiva correcta. El `systemd/robot.service` con `Restart=always` ataca #108. Nada de esto es superficial.

4. **Sus mejoras de comms SÍ están en `main` y funcionan.** A diferencia del firmware, las mejoras de serial del lado RPi que escribió (commits `5bac4a5`/`86dca44`) **sí aterrizaron**: `send_frame()` con clamp a [0,255] + `ser.flush()` (cierra #66), `serial.Serial(..., timeout=0.05, write_timeout=0.05)` (cierra #73), telemetría TX `[TLM] frames_sent` (#75 parcial). Verificado en la auditoría COMMS+THREADING. Demuestra que **cuando el trabajo es acotado, lo lleva hasta producción** — el problema aparece cuando el PR crece.

5. **Volumen y amplitud reales.** #2 del repo, 4 subsistemas, cadencia sostenida. Es el motor de contenido del equipo después del coach.

---

## 4. DEBILIDADES / áreas de mejora concretas

> Enmarcadas como temas a decidir. La mayoría son de **proceso**, recuperables sin tocar el robot.

### 4.1 [PROCESO-P0] Su trabajo de fiabilidad no llega a `main`
**Hecho duro verificado:**
- `main.cpp` en `main`: **2 menciones** de timeout/flags; `priority_fix_flags.h` **no existe en el árbol** (borrado en `b10485e`).
- `main.cpp` en PR #129 (`af270d2`): **64 menciones** de timeout/flags. Ahí vive todo.

Si hoy se flashea el robot desde `main`, **no tiene** los timeouts de `runDistance`/`runAngle`, ni la validación de payload, ni el handshake de boot.
- **Riesgo de NO corregir:** el robot va a Incheon con los cuelgues que RESILIENCIA ya documentó (#57–#76). El esfuerzo de Benjamin es invisible en producción.
- **Riesgo de corregir:** mergear PR #129 tal cual mete 5707 líneas sin revisar → alto riesgo de romper algo validado (Regla #4).
- **Tiempo:** partir PR #129 en 4–5 PRs revisables = **6–10 h** (Benjamin + review).

### 4.2 [TEST-P0] El banco está vacío en `main`; los tests reales viven sin mergear, con n=1
Ver §2.2. El conocimiento está; la ejecución y el merge, no.
- **Riesgo de NO corregir:** el TDP pierde o entrega con n=1 la sección de evidencia de fiabilidad (~24 pts).
- **Riesgo de corregir:** ninguno técnico; es trabajo de banco. El cuello es de **calendario** (necesita el robot armado).
- **Tiempo:** **~45–60 min de banco** + 30 min de transcripción para pasar T-001/T-002 de n=1 a evidencia citable.

### 4.3 [PROCESO-P1] El revert de timeouts en `main` sin re-merge oportuno (2026-05-10)
Secuencia verificada en `main`: `5bac4a5` (18:06) mete timeouts → `cead75e` (19:26) los revierte (−181 líneas) por **error de integración de `claw.cpp` con los flags**. **Revertir algo que no compila está bien** (Regla #4). El problema **no es el revert**: es que el re-arreglo correcto tardó 10 días y terminó en una rama sin mergear (§4.1). Dato de causa-raíz nuevo que aporta esta auditoría: fue un fallo de integración, no un rechazo de diseño.

### 4.4 [PROCESO-P1] PRs sobredimensionados y merge sin review
PR #50 (0 reviews) y PR #129 (39 files, multi-dominio) son demasiado grandes para review real. El TDP aparece **duplicado** en PR #129. Es el reincidente del equipo en esto. Costo de corregir: cero — es un hábito.

### 4.5 [HYGIENE-P2] Basura y binarios en el repo
`image.png` suelto en la raíz (PR #129); modelos con nombres de descarga sin limpiar (`best_float32 (1).tflite` — el espacio y paréntesis son frágiles en CI); 34.000+ líneas de PDF versionadas como texto. Es exactamente el issue #69 (migrar a Git LFS), **asignado a él y abierto**.
- **Recomendación:** **NO tocar antes de Incheon** (mover a LFS reescribe historia y puede romper checkouts del equipo a días del mundial). Post-mundial, 1–2 h.

### 4.6 [HYGIENE-P2] Dos identidades git
Unificar `user.email`: 5 min.

### 4.7 Subsistema que toca pero NO depende de él (contexto para no malatribuir)
El **núcleo de threading de la RPi sigue roto** (#111 `infer_thread` sin try/except, #113 `camthreader` sin `Lock`) — pero **eso no es trabajo pendiente de Benjamin**: son hallazgos de la auditoría de concurrencia que nadie tomó aún. Conviene tenerlo presente para no exigirle a Benjamin lo que no se le asignó. Y un dato de hardware relevante a su dominio: las **3 representaciones del hardware no coinciden** (firmware BNO055 ↔ esquemático PDF con ESP32/LEDs propuestos ↔ PCB.json que sigue siendo el board Roboliga 2024 con MPU6050). El `cambios_de_hardware.md` de Benjamin es excelente pero **describe propuestas dibujadas como si existieran**; el firmware ya aplicó el remap de pines (BUZZER 35→31, LED_ROJO 34→30 — verificado en `main.cpp:31-32`) para una ESP32 que **nunca se montó**, dejando los pines 34/35 sin función y `Serial8` sin inicializar. Esto es coordinación de equipo, no falla individual de Benjamin, pero él es quien tiene el contexto para resolverlo.

---

## 5. Recomendaciones de coaching para Enzo

> El objetivo no es producir más: Benjamin ya produce de sobra y de calidad. El objetivo es **convertir su trabajo en producción mergeada y trazable** antes de Incheon. Casi todo es proceso.

### 5.1 Qué pedirle (concreto, priorizado, esta semana)

1. **[P0 · ~6–10 h] Partir PR #129 y mergear lo seguro a `main`.** Esta es la conversación más importante que vas a tener con él antes del mundial. Orden sugerido:
   - **PR-A:** firmware timeouts + `priority_fix_flags.h` + validación serial (cierra #57–#62, #74–#76). **Probar en banco antes de mergear** (Regla #3) y anotar en TEST_LOG.
   - **PR-B:** RPi recovery + `systemd` (#108, #65, #64).
   - **PR-C:** TEST_LOG con T-001/T-002 + `MEDICIONES_PENDIENTES` (referencia #93, **sin "Closes" hasta n≥5**).
   - **PR-D:** TDP (un solo `TDP.md`, eliminar el duplicado) + assets.
2. **[P0 · ~1 h banco] Completar la sesión de `MEDICIONES_PENDIENTES.md`** con repeticiones (pickup X/10 negra+plateada, deposit 5+5, runDistance/runAngle ×10, voltaje final de estrés, anti-flash con linterna). Registrar iluminación y batería que hoy faltan.
3. **[P1 · hábito] Regla dura de PR:** nada se mergea sin un `APPROVED` formal en GitHub; PRs < ~400 líneas y de un solo dominio. Benjamin es el reincidente — si arranca él, arrastra al equipo.

### 5.2 Cómo apoyarlo (estilo de coaching)

- **Validá explícitamente su capacidad técnica primero.** Es real y conviene que lo sepa: decile que `cambios_de_hardware.md` y su honestidad en `code-reliability-evidence` son lo mejor del repo. Esto le baja la guardia para la crítica de proceso, que es la que importa.
- **Reencuadrá "terminar" = "mergeado en `main` y probado en banco", no "lo escribí".** Para Benjamin el trabajo se siente hecho cuando lo codeó; el cambio mental es entender que **código en rama sin mergear = trabajo invisible** a 30 días de un mundial sin rollback. Es el hábito de mayor retorno que le podés enseñar este año.
- **Sentate con él a partir el PR #129 en vivo** (sesión de pair, 1–2 h). No es castigo: es enseñarle a dimensionar PRs. Que vea cómo un PR de 39 archivos se vuelve 4 PRs reviewables.
- **Hacelo el dueño del TEST_LOG del equipo.** Ya sabe la disciplina (su plan lo prueba). Darle ese rol formal aprovecha su fortaleza y le da una razón concreta para mergear seguido (cada test es una entrada).

### 5.3 Cómo hacerlo crecer

- **Re-balanceá su carga de issues (~30 asignados).** Es insostenible y es parte de por qué su trabajo no aterriza: está estirado. Pasale parte del cluster comms #70–#76 a Laureano/Lucio. Liberarlo lo hace **más** efectivo, no menos.
- **Dale ownership de un entregable del TDP de punta a punta** (p. ej. la sección Electronics): relevar el robot real, reconciliar las 3 representaciones de hardware, cerrar el BOM en `hardware/bom/`. Es trabajo de markdown de bajo riesgo (~10–15 h, sin tocar firmware) con altísimo retorno de puntaje, y juega exactamente a su fortaleza de documentación.
- **Mentoría de revisor:** ponelo a revisar PRs de Laureano y Lucio. Tiene el criterio para hacerlo y le enseña, desde el otro lado, por qué un PR chico es revisable y uno gigante no.

---

## 6. Veredicto

**Talento y esfuerzo: altos. Mejor documentador del equipo. Frenado por disciplina de entrega.**

Benjamin no necesita que le enseñes a hacer ingeniería —ya la hace mejor que nadie en el equipo—. Necesita que le enseñes a **cerrar el lazo**: del código a la rama, de la rama a `main`, de `main` al banco, del banco al TEST_LOG. A 30 días de Incheon, **la diferencia entre que su excelente trabajo llegue o no a la pista la define el proceso de merge, no su capacidad.** Si parte y mergea PR #129 y completa la sesión de banco, pasa de ser el integrante de mayor potencial latente a ser el de mayor impacto real del equipo.

---

*Informe generado para la auditoría integral 2026-05-18 — uso de coaching. Solo lectura: no se modificó código fuente, no se abrieron/cerraron/comentaron issues ni PRs. Todos los hallazgos críticos se presentan como temas a decidir (riesgo-no-fix · riesgo-fix · tiempo). Verificaciones cruzadas contra `main.cpp`, `testing/TEST_LOG.md`, `hardware/cambios_de_hardware.md`, `git log`/`git show af270d2`, y `gh pr/issue view` (solo lectura). Informes fuente en `project/backlog/staging/auditoria-integral-2026-05-18/`: `equipo-03-benjamin.md`, `hw-01-bom-planos-evolucion.md`, `hw-02-evaluacion-critica.md`, `comms-02-esp32.md`, `rpi-03-comms-threading.md`.*
