# INFORME EJECUTIVO PARA EL COACH

## Auditoría Integral del Proyecto — RCJ Rescue Line 2026 · IITA Salta

**De:** Gustavo Viollaz (Director) **· Para:** Enzo Juarez (Coach) **· Fecha:** 31-05-2026
**Mundial:** RoboCup Junior Rescue Line — Incheon, Corea — 30-jun a 06-jul-2026 (**~30 días**)
**Base:** auditoría de 26 agentes sobre el repo (24 análisis de subsistema + 3 informes por integrante), datos verificados a mano contra `origin/main` (`1841dcb`) el 31-05-2026.

---

### MENSAJE DEL DIRECTOR

> **Enzo: están perdiendo el foco.** Se está trabajando en cosas intrascendentes —agregar finales de carrera, sumar un módulo de comunicación ESP32, intentar hacer videos— **sin CONCRETAR lo importante**. Falta **TRABAJO PROFESIONAL**. Falta **DOCUMENTACIÓN**. Falta **CARGAR TODO EN EL REPOSITORIO**: lo que no está en `main` no existe. Tenemos talento y tenemos buen diagnóstico, pero el trabajo no se cierra, no se mergea y no se documenta. **Estamos a tiempo —pero tienen que CAMBIAR LA FORMA DE TRABAJO AHORA.** Esta semana, no la que viene.

---

### RESUMEN EJECUTIVO

**Diagnóstico en una línea:** el equipo identificó el blanco correcto y le apuntó bien, **pero la bala está atascada en la recámara (PR #129) y la maneja un solo tirador (Benjamin).** El riesgo #1 a Incheon **no es técnico: es de proceso —merge, bus-factor y documentación.**

**Semáforo por frente:**

| Frente | Estado |
|---|---|
| Análisis y diagnóstico de bugs | 🟢 Nivel mundial — saben qué está mal |
| Visión (features: TFLite, NCNN, anti-destello, 91 FPS medidos) | 🟢 Lo más maduro |
| **Cierre / merge a `main`** | 🔴 Todo el código real represado en PR #129 sin mergear |
| Firmware (control/rescate) | 🔴 PID saturado, velocidad mal en curva, rescate por FSM muerta |
| Comms / resiliencia / auto-recuperación 8-10 | 🔴 Sin heartbeat, sin handshake real, sin WDT → hoy es aspiracional |
| **TDP / Poster / Video** | 🔴 No existen: ~6-12/102 · 0/18 · 0/24 |
| Balance de personas | 🔴 Bus-factor = 1 (Benjamin escribió el 100% del código del último mes) |
| Hardware (diseño) | 🟢 Arquitectura correcta, alineada con campeones |
| Uso de IA (visión + herramienta de desarrollo) | 🟢 Maduro, transparente, premiable |

**Los 5 riesgos P0:**

1. **PR #129 no se mergea** → el robot que viaja tiene los bugs B1-B10 vivos. *Verificado: `drivebase.cpp:50` en `main` sigue con el PID saturado; `priority_fix_flags.h` no existe en `main`.*
2. **Bus-factor = 1.** Benjamin = 100% del código del último mes. Laureano no toca código desde el 14-mar; Lucio tiene 0 líneas vivas en visión siendo el dueño. No podrán debuggear en el pit.
3. **Documentación de jurado en cero** (~72 pts de presentación + reliability sin respaldo). El TEST_LOG en `main` está vacío.
4. **Comms sin red de seguridad** (sin heartbeat #53, el Teensy nunca emite el handshake 0xFA, sin WDT) → un cuelgue deja el robot inerte.
5. **El rescate corre por código fantasma:** la FSM no-bloqueante está 100% muerta; corre la vieja secuencia inline bloqueante. **El equipo tunea código que no se ejecuta.**

**Conclusión:** el talento y el criterio están a nivel mundial (lo prueban los issues #57-#128). Lo que falta no es saber qué hacer — es **cerrar: mergear, repartir y documentar en la rama que cuenta.** A 30 días, con las 3 palancas del anexo movidas esta semana, "podio + aprender" sigue siendo alcanzable.

<!-- PAGEBREAK -->

### INFORME GENERAL DEL PROYECTO

**Programas — Teensy (firmware).** Es el subsistema que más puntos gana o pierde en pista y el menos atendido las últimas semanas.
- **PID (B1/#121) — reinterpretado:** los motores son DFRobot FIT0441 con **PWM invertido** → el `255 - _pwmVal` es *correcto* a nivel HW. El problema real es el lazo (PID en modo DIRECT + `ki=22` dominante + `kp=0`) que **nunca regula y queda saturado a fondo**. *El fix naïve que se había propuesto EMPEORA el robot:* es rediseño de lazo, no un cambio de signo (`teensy-01-drivebase-pid.md`).
- **Navegación (B5/#122):** la velocidad sube a 55 en curva con lógica invertida → causa #1 de salidas de pista. `taskDone` nunca vuelve a `false` (solo anda tras un OFF→ON manual). Esquiva de obstáculo con `random()` sin semilla. La línea roja de fin de pista (`green_state==10`) se ignora: el robot no frena al terminar.
- **Rescate (P0 central):** existen **dos FSM de pinza contradictorias**; la no-bloqueante (`actualizarRescate()`, `claw.cpp`) está **100% muerta** y corre la vieja inline bloqueante (`main.cpp:1137-1186`). `ball_counter`/`veces_deposit` con init contradictorio → salida anticipada del cuarto (#123/B6). La salida final NO está implementada → el robot queda contra la pared.
- **Sensores:** el revert `cead75e` borró los timeouts (#59-#62) → sin timeout en `colorDataReady`, `while(1)` infinito ante fallo de init de BNO055/APDS9960.

**Programas — RPi (visión + decisión).** El más maduro, pero con un P0 binario sin confirmar:
- **#124/B7 (P0, 48h):** el parseo del tensor TFLite asume `[N,6]` con NMS embebido, pero `metadata.yaml` dice `end2end:false`. Si no trae NMS, el `infer_thread` (sin try/except, #111) **crashea → el rescate no funciona en absoluto.** **Hay que medir `out.shape` esta semana.**
- **#B2:** `silver_mask` en BGR con umbrales HSV → el único trigger de entrada a rescate está mal. **#B9:** rojo `H∈[1,7]` sin wrap. Causa raíz transversal: exposición/balance de blancos de la cámara sin fijar.
- La FSM 'depositar' ciega el YOLO a todas las víctimas → robot clavado en la zona verde.

**Comms + ESP32.** El protocolo quedó **desincronizado entre placas** por el revert: la RPi ya tiene el protocolo nuevo (0xFA, clamp, timeout) pero el Teensy **nunca emite 0xFA** → el fail-safe es ilusorio. El buffer de Serial5 es de **64 bytes** y desborda en ~0,27 s bajo maniobras. **El ESP32 NO está incorporado** (ni HW ni SW): solo es propuesta. Peor: el firmware **ya remapeó pines** (BUZZER 35→31, LED 34→30) para una ESP32 que nunca se montó → estado inconsistente. Hay **dos planes de SuperTeam incompatibles** (ESP32-Teensy vs BT-RPi) sin decidir.

**Hardware.** Arquitectura **acertada y alineada con campeones**, pero: (a) las **3 representaciones del hardware no coinciden** entre sí ni con el robot real (firmware con BNO055 ↔ esquemático con ESP32 ↔ PCB.json con MPU6050 → no se puede re-fabricar el board desde el repo); (b) `hardware/bom/` vacío, sin CAD/STL 2026; (c) **P0 de potencia:** la RPi se alimenta de un buck **sub-dimensionado** (reinicios que matan el 8-10 de auto-recuperación) y **no hay fusible** ni protección de LiPo.

**Documentación (puntaje HOY → potencial):** **TDP** ~6-12/102 → 71-89 (no existe como archivo; el draft de Lucio está en Google Drive fuera del repo). **Poster** 0/18 → 13-18 (bloqueado por acceso al Canva, #45). **Video** 0/24 → 20-22 (**los 5 clips crudos son POV de la cámara onboard, inservibles — hay que filmar de nuevo**, #94). El TEST_LOG en `main` está vacío.

**Novedad defendible:** la arquitectura NO es novedosa (es el "patrón campeón"). Lo defendible: el **pipeline anti-destello adaptativo** (implementado) y la **validación multimodal de víctima** (diseñada, no embarcada). **Riesgo: vender diseño como implementación** — el claim de "auto-recuperación 8-10" es hoy el más peligroso porque nada está mergeado.

**Estrategia — los 2 desvíos:** (1) el TDP se metió dentro del PR #129 y **bloquea la entrada de los fixes que sí corren en pista**; (2) **scope creep impropio a 30 días** (finales de carrera, ESP32/SuperTeam, Technical Challenges, refactors) — todo eso distrae con un solo programador. **Hay que recortar y cerrar.**

<!-- PAGEBREAK -->

### INTEGRANTE 1 — Laureano Monteros (@Laumonteros) · Firmware Teensy (owner)

**Actividad (datos duros, `git log`/`gh`):** 6 commits de contenido, **todos en marzo (07-14)**, **0 en abril-mayo** (~2,5 meses sin tocar `main` a 30 días del mundial). +534/−90 líneas. 2 PRs (#37, #39), ambos mergeados por el coach con **0 reviews formales**. **0 issues autorados.** **14 issues asignados OPEN** (sus #25/#27 originales + los 6 de CORRECTITUD). **0 entradas en TEST_LOG.** Commitea bajo 2 identidades git (unificar `user.email`).

**Calidad — lo bueno (mérito genuino, leído en `claw.cpp`/`claw.h`):** la **FSM no-bloqueante de la pinza** es el patrón correcto y ataca directo su propio issue #25; `begin()` separado del constructor con comentario sobre orden de init de globales → sofisticado para su nivel. **Mejor instinto de arquitectura de firmware del equipo.**

**Calidad — lo que falla:** su mejor commit (`ec8e6ab` "Timeout/Watchdogs") **NO es ancestro de `main`** (`git merge-base` lo confirma) → **su mejor trabajo está perdido.** Su FSM de pinza está **muerta** (corre la inline bloqueante). El bug B5/#122 vive en `main.cpp:1066` **porque es justo el código que él intentó borrar** → no es reincidencia, es trabajo no integrado. PR #37 marinó 7 semanas y declara `Closes #123` (que no existía) → **aceptó salida de IA sin verificar** (lo declaró honestamente, eso está bien). `variables_doc.md` ya quedó desactualizado.

**Fortalezas:** arquitectura de firmware · ataca los problemas correctos (resiliencia) · iniciativa de documentar · transparente con el uso de IA · dueño real de subsistema.

**Debilidades:** desconexión temporal (riesgo #1) · cero verificación en banco · acepta IA sin auditar · no hace follow-up de sus PRs hasta verlos en `main` · higiene de proceso floja.

**Recomendaciones para Enzo:** (1) **Reactivarlo con una victoria garantizada: #115 = recuperar SUS timeouts** (`git show ec8e6ab` existe) — máximo ROI técnico + psicológico. (2) Pedirle **una** entrada de TEST_LOG de la pinza (y descubrir juntos que su FSM no corre). (3) Triage guiado de sus 6 issues B*. (4) Enseñarle a **verificar la IA** (¿el issue del `Closes` existe? ¿la variable significa lo que creo? ¿lo probé en banco?). (5) Emparejarlo con Benjamin + check-ins semanales de 15 min para forzar continuidad.

**Veredicto:** *talento de arquitectura por encima del promedio del equipo, lastrado por disciplina e involucramiento muy por debajo de lo que exige un mundial.* Si se reconecta, es el firmware-lead que el equipo necesita.

<!-- PAGEBREAK -->

### INTEGRANTE 2 — Lucio Saucedo (@luciouriel2011) · RPi Visión (owner)

**Actividad (datos duros):** 5 commits no-merge (el menor de los 3 alumnos). 2 PRs: #36 (fix C++ punteros) **mergeado**; #42 (comentarios) **OPEN desde marzo, abandonado** tras feedback del coach del 29-abr. **0 issues autorados, 0 reviews. Última actividad 2026-04-25 → +1 mes de silencio** entrando a la recta final.

**Calidad — el hallazgo que define todo:** por `git blame` sobre la versión viva, **Lucio tiene 0 líneas en TODO el código de visión** (`Main.py`, `camthreader.py`, `calibration.py`, `AI/`) pese a ser el dueño. Sus dos aportes con sustancia cayeron **fuera de dominio**: el fix de firmware (`strcmp` por comparación de punteros, PR #36 — técnicamente impecable, agregó hasta el guard `!= NULL`) y un **TDP de 411 líneas** de buena calidad. Pero el TDP está **varado sin mergear** en la rama `documentation_and_diagrams`, en inglés sin review, con un error de hecho ("RPi 5" en vez de 4B). **Agravante de gobernanza (#46):** dice tener un draft "desarrollado en su mayoría" en **Google Drive** que el coach pidió **dos veces** (1-abr y 29-abr) sin respuesta.

**Lectura clave:** **el problema NO es de talento** —el fix de punteros y el TDP lo prueban— **es de aplicación fuera de dominio, falta de continuidad y entregables sin cerrar.**

**Fortalezas:** sabe programar y razona bugs de verdad · escribe documentación técnica de calidad (el TDP es hoy su mayor aporte potencial al puntaje) · respeta convenciones · trabaja sin romper.

**Debilidades:** desalineación rol↔realidad (bus-factor de visión = 1) · desconexión sostenida (+1 mes) · patrón de "no termina lo que empieza" (PR #42 y el TDP varados) · no participa del proceso de equipo (0 reviews) · sin hábito de banco.

**Recomendaciones para Enzo:** (1) **ROI máximo: rescatar el TDP** — pedirle el link del Drive (#46), cherry-pick de `TDP/` + imágenes a `main`, corregir "RPi 5"→"4B". Es el mayor salto de puntaje disponible y le devuelve ownership de algo que SÍ hizo bien. (2) **Bus-factor 2 en visión por pairing dirigido** (NO reasignación): hacerlo **dueño de la calibración de color en sede** (HSV plata + verde LAB, conecta con #B2/#B9) — tarea chica, medible, con commit + TEST_LOG. (3) Cerrar PR #42. (4) **La conversación 1:1** (deuda de equipo, no de código): entender por qué se desconectó y salir con 2-3 tareas con fecha.

**Veredicto:** *por debajo de lo esperado para el rol, pero no por incapacidad.* La materia prima es buena; falta engancharla al rol y al equipo antes de viajar — y las 3 acciones de mayor impacto son recuperables en pocas horas.

<!-- PAGEBREAK -->

### INTEGRANTE 3 — Benjamin Villagran (@benjaminvillagran) · RPi + Hardware + Banco

**Actividad (datos duros):** **28 commits** (todas las ramas), **#2 del repo después del coach**, cadencia sostenida feb→may (último 24-may). **El 100% del código del último mes es suyo.** Ojo: las "41k líneas" son engañosas (~34k son PDF binario del PCB); el aporte real ronda 5-6k líneas. ~30 issues asignados (**desproporcionado**). Mensajes de commit buenos (25/28 Conventional Commits).

**Calidad — fortalezas reales (verificadas, no halago):** `hardware/cambios_de_hardware.md` (717 líneas, 100% suyas) es **el mejor documento del repo** — cita reglamento 2026, evalúa opciones con pros/contras, anticipa modos de falla físicos (fatiga del cable de la garra). **Honestidad técnica:** en `code-reliability-evidence` separa explícitamente "mecanismos en código" de "mediciones físicas" y aclara *"physical testing must still validate…"*. Sus mejoras de comms del lado RPi (clamp #66, timeout serial #73, telemetría #75) **sí están en `main` y funcionan** → cuando el trabajo es acotado, lo lleva a producción.

**Calidad — el talón de Aquiles (PROCESO, no capacidad):** casi todo su trabajo P0/P1 de fiabilidad —y el TEST_LOG que la rúbrica más valora— está **varado en PR #129 (OPEN, +5707/−506, 39 archivos, 0 reviews).** `main.cpp` en `main` tiene 2 menciones de timeout; en #129 tiene 64. **Si hoy se flashea desde `main`, el robot no tiene esos fixes.** El TEST_LOG en `main` está **vacío**; los 2 tests reales (T-001 batería/odometría, T-002 **91.33 FPS** medidos) viven sin mergear y con **n=1**. PR #50 (+1946) se mergeó con 0 reviews. El PR #129 es **materialmente irreviewable** (multi-dominio + TDP duplicado + assets + `image.png` suelto).

**Fortalezas:** documentación de hardware profesional · honestidad técnica · código de fiabilidad competente (`priority_fix_flags.h` con feature-flags por issue) · volumen y amplitud reales (es el motor de contenido del equipo).

**Debilidades:** **su trabajo de fiabilidad no llega a `main`** (P0) · banco vacío en `main`, tests reales sin mergear y con n=1 · PRs sobredimensionados y merge sin review (reincidente) · sobrecarga de ~30 issues que lo estira · binarios/basura en el repo (#69).

**Recomendaciones para Enzo:** (1) **[P0] Partir #129** en PR-A firmware/timeouts → PR-B RPi/systemd → PR-C TEST_LOG → PR-D TDP, y **mergear lo seguro con banco**. (2) **[P0] Completar `MEDICIONES_PENDIENTES.md`** (~1h banco: pickup X/10, deposit 5+5, voltaje de estrés). (3) **Regla dura: nada se mergea sin `APPROVED`; PRs <400 líneas, un dominio.** (4) Validar su capacidad primero, luego enseñarle que *"terminar = mergeado y probado, no escrito"*. (5) Re-balancear su carga de issues (pasar comms #70-#76 a otros) y darle ownership del TDP §Electronics.

**Veredicto:** *talento y esfuerzo altos, mejor documentador del equipo, frenado por disciplina de entrega.* Si parte y mergea #129 y completa el banco, pasa de mayor potencial latente a **mayor impacto real** del equipo.

<!-- PAGEBREAK -->

### ANEXO — PRIORIDADES (qué hacer, en qué orden) · 1/2

**Régimen vigente (corregido al 31-05):** la ventana de push libre de firmware (Track A) **ya venció**; todo entra por review de Enzo. Docs/visión (Track B) push libre hasta 11-jun. **Freeze de código propuesto: 15-jun** (deja 15 días para banco + viaje).

#### LAS 3 COSAS QUE MÁS MUEVEN LA AGUJA (esta semana)

1. **DESBLOQUEAR Y MERGEAR EL CÓDIGO DE #129 (con banco).** Pedir a Benjamin que **parta #129 en dos**: PR-código (drivebase, main.cpp, Main.py, systemd, `priority_fix_flags.h`) → mergear **primero** con sesión de banco; PR-TDP → después. *Mientras #129 esté abierto, el robot que viaja tiene B1-B10 vivos.* **Meta: PR-código en `main` antes del 05-jun, con T-003 de validación.**
2. **ROMPER EL BUS-FACTOR.** Laureano y Lucio escribiendo **CÓDIGO** ya, con pairing. Laureano ejecuta #115 (recuperar SUS timeouts); Lucio toma #124/B7 + #110 y **trae su TDP del Drive al repo.** **Meta: ≥3 commits de código de cada uno mergeados antes del 10-jun.**
3. **AGENDAR LA SESIÓN DE FOTOS Y EXIGIR EL CANVA.** Única acción no delegable del coach, mayor ROI por hora en documentación: un sábado con robot + equipo + cámara desbloquea **Poster (18) + Video (18 de 24) + TDP §Mechanical.** Confirmar la **deadline real de subida del video** (único piso de calendario irreducible).

#### PLAN POR SEMANAS (responsables: B=Benjamin, L=Lucio, La=Laureano, E=Enzo, D=Director)

**Semana 0 — Destrabe (31-may → 07-jun):**
- [E+D] Review y **partir PR #129**; mergear PR-código + T-001/T-002 a `main`.
- [La] #115 → recuperar timeouts #60/#61/#112. [B] #72 → emisor 0xFA del Teensy (15 min). [B/La] #57 (signo rama pared) + init de `ball_counter`/`veces_deposit` + delay pinza plateada.
- [L] **#124/B7 → medir `out.shape` del TFLite** (define si el rescate funciona). Luego #110 + #111. **Traer el TDP del Drive (#46).**
- [E, no delegable] Exigir Canva (#45) + **agendar fotos (#94).** [D/E] Decidir SuperTeam (Ruta B BT-RPi ya, ESP32 como migración).
- [D/E] Etiquetar `post-incheon` el scope creep (#88/#81/#82/#83/#87/#84 + finales de carrera). [B] Git LFS (#69) antes de clonar en Corea.
- **Hito: SIMULACIÓN SuperTeam 1** (ver abajo).

**Semana 1 — Estabilizar y filmar (08-jun → 14-jun):**
- [La] #122/B5 + #125/B8 (validar en banco, T-XXX). [La/B] Activar la FSM de rescate o documentar por qué se queda con la inline + **implementar la salida del cuarto.** [B] #53 heartbeat + #27 WDT. [L] #B2 + #B9. [La] #121/B1 → **sesión de diseño del PID** (NO quick-win).
- [B/L sábado] **Sesión de fotos #94 + filmar tomas externas** del robot. [L+B] Ensamblar el cuerpo del TDP (objetivo ~40 pts). [La+B] #41 diagrama de software.
- **Hito: SIMULACIÓN SuperTeam 2** (ver abajo).

<!-- PAGEBREAK -->

### ANEXO — PRIORIDADES · 2/2

**Semana 2 — Documentar y endurecer (15-jun → 21-jun) · FREEZE DE CÓDIGO el 15:**
- [La/B] #126/B10 calibrar encoder. **[B] Hardware P0: buck ≥5A real para la RPi + fusible/PTC** (los reinicios matan el 8-10). [E] Régimen de banco: 2 sesiones fijas/semana, cada una ≥1 entrada en TEST_LOG.
- [L+B] **TDP cuerpo completo** (objetivo 71-89) con la sección de visión/IA y la declaración de uso de IA. [La/B] Maquetar **Poster** en Canva (13-18). [B] Editar **Video** con tomas nuevas + narración en inglés (20-22). [E/D] Pasar `cambios_de_hardware.md` de "propuesta" a "as-built" honesto.

**Semana 3 — Logística y ensayo (22-jun → 29-jun):**
- [Todos] Ensayos completos cronometrados (línea + rescate + recuperación), midiendo el 8-10 real. Pairing en el pit. [E/D] **Subir TDP, Poster, Video.** [B] Kit de pit (SD clonada #38, repo clonable offline, baterías, repuestos). Viaje a Incheon.

#### REGLAS DE TRABAJO NUEVAS (no negociables, desde hoy)

1. **Lo que no está en `main` no existe.** Nada de Google Drive ni ramas eternas. Cargar TODO al repo.
2. **Ningún merge sin un `APPROVED` formal.** PRs chicos (<400 líneas) y de un solo dominio.
3. **Ningún fix de firmware se mergea sin su entrada en TEST_LOG** (Regla de Oro #3, hoy incumplida por los 3).
4. **Cada alumno escribe CÓDIGO de SU subsistema cada semana** (check-in de 15 min). Se terminó el "aparezco, brillo una semana, desaparezco".
5. **Recortar el scope:** nada de finales de carrera, ESP32 ni Technical Challenges hasta after-Incheon. Foco en robot core + documentación.

#### LAS 2 SIMULACIONES SUPERTEAM (listas para asignar)

El SuperTeam Challenge es **independiente** (premio propio, no afecta el puntaje individual), premia **cooperación entre equipos de distinto idioma**, la tarea se anuncia **recién en Incheon**, canal 2.4 GHz con espectro **no garantizado** (hay que tolerar pérdida). Detalle completo en `superteam-00-dos-ejercicios.md`.

- **SIMULACIÓN 1 — "Lenguaje común sin radio" (~2h30, Semana 0/1):** acordar un protocolo de cooperación en ≤15 min **sin idioma común** (solo íconos) y ejecutar un handoff **sin radio** (percepción + tiempo + señales LED/buzzer). Cero riesgo, no depende de la decisión ESP32/BT. Produce el "protocolo de aplicación" que hoy no existe.
- **SIMULACIÓN 2 — "Handshake y degradación con canal real" (~3h, Semana 1):** primer canal inter-robot funcional (Bluetooth nativo de la RPi, sin abrir el robot) con handshake + barrera + **prueba de degradación** (cortar la radio → los robots NO se cuelgan). Crea `superteam.py`. **Regla dura: el canal SuperTeam NO toca el UART frágil Teensy↔RPi.**

---

*Informe sintetizado de la auditoría integral de 26 agentes (31-05-2026). Reportes de respaldo (24 archivos) en `project/backlog/staging/auditoria-integral-2026-05-18/`. Datos verificados a mano sobre `origin/main` (`1841dcb`): PID saturado vivo en `drivebase.cpp:50`; `priority_fix_flags.h` ausente en `main`; TEST_LOG vacío; PR #129 OPEN (+5707/−506, 39 files, 0 reviews); 73 issues y 8 PRs abiertos. Marco "temas a analizar" (riesgo-no-actuar / riesgo-actuar / tiempo), no "bugs a fixear".*
