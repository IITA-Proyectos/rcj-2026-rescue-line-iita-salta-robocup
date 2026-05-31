# INFORME DEL DIRECTOR PARA ENZO — Auditoría Integral 2026-05-18

**De:** Gustavo Viollaz (Director) · **Para:** Enzo Juarez (Coach, @enzzo19)
**Proyecto:** RCJ Rescue Line — IITA Salta — RoboCup Junior, Incheon (Corea), 2026-06-30 → 07-06
**Fecha de corte de datos:** 2026-05-31 · **Rama analizada:** `feature/initialize-testing-log` (== `main` post-PR #101)
**Objetivo declarado del equipo:** podio + auto-recuperación 8/10.

> **Cómo leer este informe.** Esto es dirección, no código. Sintetiza las 24 auditorías de subsistema del 2026-05-18 (firmware, visión, comms, hardware, documentación, estrategia, equipo, SuperTeam) y las baja a un plan accionable. **No repite** las dos auditorías previas — RESILIENCIA (#53/#27/#57–#119) y CORRECTITUD (#120–#128, bugs B1–B10) — las cita y construye encima. Por convención IITA, cada tema accionable se presenta como **TEMA A ANALIZAR** con riesgo-de-no-tocar + riesgo-de-tocar + esfuerzo. La decisión es del coach; el auditor presenta el material. El tono es duro a propósito: faltan ~4 semanas y el diagnóstico tibio no sirve. Lo positivo también está, porque es real.

---

## 1. RESUMEN EJECUTIVO

### 1.1 Semáforo general

| Frente | Estado | Semáforo |
|---|---|---|
| **Análisis y diagnóstico de bugs** | Nivel mundial. El equipo sabe *exactamente* qué está mal. | 🟢 |
| **Visión (RPi)** — features | La más madura: TFLite, NCNN, anti-destello, 91 FPS medidos. | 🟢 |
| **Ejecución de cierre (merge a `main`)** | Todo el trabajo real está represado en PR #129 sin mergear. El robot que viaja tiene B1–B10 vivos. | 🔴 |
| **Firmware (Teensy)** — control/rescate | Estancado. PID saturado (B1), velocidad mal en curva (B5), salida anticipada del cuarto (B6), rescate por FSM muerta. Sin timeouts (revertidos en `cead75e`). | 🔴 |
| **Comms serial** | Sin heartbeat (#53), sin handshake real (Teensy nunca emite 0xFA), buffer de 64 B que desborda en ~0,27 s. Desincronizado entre placas tras el revert. | 🔴 |
| **Resiliencia / auto-recuperación** | El objetivo 8/10 hoy es aspiracional: WDT, heartbeat, handshake y auto-restart no están en `main`. | 🔴 |
| **TDP** | No existe como archivo. ~6–12/102 pts hoy. | 🔴 |
| **Poster** | No existe. 0/18 pts. Bloqueo de ownership (Canva). | 🔴 |
| **Video** | No existe. 0/24 pts. Clips crudos resultaron inservibles (POV onboard). | 🔴 |
| **Balance de personas** | Bus-factor = 1 (Benjamin). Los dueños nominales no escriben su subsistema. | 🔴 |
| **Hardware (diseño)** | Arquitectura correcta, alineada con campeones. | 🟢 |
| **Hardware (implementación de potencia + documentación)** | Tres representaciones que no coinciden; buck de la RPi sub-dimensionado; sin fusible. | 🟡 |
| **Novedad defendible para el jurado** | Hay 4 ángulos reales (anti-destello, validación multimodal). Riesgo: vender diseño como implementación. | 🟡 |
| **Uso de IA** | Maduro, transparente, declarado. Premiable. | 🟢 |

**Lectura de una línea:** el equipo **identificó el blanco correcto y le apuntó bien, pero la bala está atascada en la recámara (#129) y la maneja un solo tirador (Benjamin).** El riesgo número uno a Incheon **no es técnico — es de proceso de merge, de bus-factor y de documentación.**

### 1.2 T-semanas a Incheon

- **HOY (2026-05-31) → 2026-06-30:** quedan **~4,3 semanas** calendario al inicio del torneo.
- Descontando viaje + logística + jet-lag, quedan **~3 semanas hábiles de banco** reales.
- **Fechas de fase vigentes:** Track A (firmware/comms) push libre **≤ 2026-05-26** → ya cerró su ventana de push libre; ahora **gate de Enzo**. Track B (docs/visión) push libre **≤ 2026-06-11** → 11 días restantes. **Logística:** última semana.
- **Recomendación de calendario nueva:** declarar **feature-freeze de código el 2026-06-15** (deja 15 días para banco + viaje). Post-freeze, solo fixes P0 verificados en banco.

### 1.3 Los 5 riesgos mayores (priorizados)

| # | Riesgo | Prob. | Impacto | Sev. |
|---|---|---|---|---|
| **R-1** | **PR #129 no se mergea (o se mergea sin banco la última semana)** → el robot compite con B1 (PID saturado), B5 (velocidad en curva), B6 (salida anticipada), B8 (doble-verde), timeouts y systemd vivos solo dentro del PR. Verificado a mano: `drivebase.cpp:50` en `origin/main` sigue diciendo `analogWrite(_pwmPin, (int)(255 - _pwmVal))` con PID DIRECT, y `priority_fix_flags.h` **no existe en `main`**. | Alta | Muy alto | **P0** |
| **R-2** | **Bus-factor = 1.** 100% del código del último mes lo escribió Benjamin. Laureano (firmware, owner) no toca código desde el **14-mar**; Lucio (visión, owner) tiene **3 commits de código en toda la historia** y **0 líneas vivas** en visión. Si Benjamin falla, el proyecto se detiene; los otros dos no pueden asistir en el pit. | Media | Muy alto | **P0** |
| **R-3** | **Documentación de jurado en cero.** TDP no existe (~6–12/102), Poster 0/18, Video 0/24. A 30 días, **48 pts de presentación + ~24 pts de reliability del TDP** están sin respaldo. El TEST_LOG en `main` está **vacío** (confirmado: las 4 categorías dicen "(vacío)", solo el ejemplo T-000 marcado "no es real"). | Alta | Alto | **P0** |
| **R-4** | **Comms/resiliencia sin red de seguridad.** Sin heartbeat (#53), Teensy nunca emite el 0xFA del handshake (#72 medio implementado = peor que nada), sin WDT, sin timeouts (revertidos en `cead75e`). Un reset del Teensy o un cuelgue de la Pi en pista deja al robot inerte ejecutando el último comando para siempre. El objetivo "8/10 recuperación" hoy es **mentira técnica**. | Media-Alta | Alto | **P0/P1** |
| **R-5** | **Rescate corre por código fantasma.** La recolección real usa la vieja secuencia inline **bloqueante** (`main.cpp:1137-1186`); la FSM no bloqueante (`actualizarRescate()`, `claw.cpp`) está **100% muerta** (sus disparadores nunca se invocan). El equipo está tuneando código que no se ejecuta. Sumado a contadores `ball_counter`/`veces_deposit` con init contradictorio → salida anticipada del cuarto (causa raíz de #123/B6). | Alta | Alto | **P0/P1** |

**Si en los próximos 7 días se mueven R-1, R-2 y R-3, el objetivo "podio + 8/10" sigue siendo alcanzable. Si el 2026-06-10 #129 sigue abierto y los docs en cero, el riesgo de llegar con un robot no validado y sin presentación es muy alto.**

---

## 2. ESTADO POR FRENTE

### 2.1 PROGRAMAS — Teensy (firmware de control, navegación, rescate)

El firmware es el subsistema que **más puntos puede ganar o perder en pista** y es el menos atendido las últimas semanas. Cinco auditorías lo cubren (`teensy-01..05`). Bugs críticos consolidados:

**Control de motores / drivebase (`teensy-01-drivebase-pid.md`):**
- **Reinterpretación clave de B1/#121 (P0).** Los motores son **DFRobot FIT0441 brushless con PWM INVERTIDO** (255=parado, 0=máximo) y pulsos NO en cuadratura. Por eso el `255 - _pwmVal` es **correcto a nivel HW**. El problema real es el **acople de sentido**: PID en modo DIRECT + actuador de ganancia negativa + `ki=22` dominante + `kp=0` → el lazo **nunca regula y queda saturado arriba**. El robot anda "a fondo" porque está pegado en PWM máximo, no porque controle. **El fix naïve de #121 (`analogWrite(_pwmVal)`) probablemente EMPEORA** (invertiría el sentido global). Esto cambia la naturaleza del fix: no es un signo, es rediseñar el lazo.
- **Bombas latentes que se despiertan al arreglar el PID:** la histéresis `if(_pwmVal<10) _dir=!_dir` **invierte la dirección comandada** (T-06); el conteo de pulsos infiere el sentido del software `_dir`, no del HW, y se corrompe en frenadas/inversiones (T-05); `SampleTime=100ms` corre el lazo a 10 Hz aunque `setSpeed()` se llame a miles de Hz (T-02); `getSpeed()` arma mal la ventana de RPM y pisa `_rpmlist[3]` desde dos contextos (T-07).
- Confirmados **#B10/#126** (constante 25 pulsos/cm sin origen + ISR CHANGE x2) y **#67** (`pulseCount` sin init). La geometría de `steer()` es **CORRECTA** y NO debe tocarse. Los giros usan IMU, no encoders, lo que **acota** el impacto de los bugs de odometría a maniobras lineales de rescate.

**Navegación de línea (`teensy-03-linea-fsm.md`):**
- **#B5/#122 (P1, causa #1 de salidas de pista):** velocidad sube a 55 en curva con lógica invertida → la rueda interna se invierte a alta velocidad.
- **#B8/#125:** `runAngle(180)` siempre gira a la derecha sin mirar el signo del error, y nunca converge sin timeout.
- **Nuevos P0:** el guard `taskDone` arranca en `false` y **nunca vuelve a `false`** → el line-track solo funciona tras un OFF→ON manual del switch. La esquiva de obstáculo usa `random()` **sin `randomSeed()`** (secuencia idéntica en cada encendido, elige el lado a ciegas sin leer ToF/ultrasonidos) dentro de un `while` sin timeout.
- **Código muerto/inalcanzable:** `Main.py` solo emite green_state 0/1/2/3/10 en línea, nunca 14–17 → el `case 12` es inalcanzable. La línea roja de fin de pista (green_state==10) **se ignora**: el robot no frena al terminar. Anti-rebote de verde declarado pero muerto (`lastTurn`/`turnCooldown`) → giros dobles.

**Zona de evacuación / rescate (`teensy-04-rescate-fsm.md`):**
- **P0 nuevo y central:** existen **DOS máquinas de estado de pinza contradictorias**. `actualizarRescate()` (líneas 86-254, llamada en loop:807) está **100% MUERTA** porque `iniciarRecoleccionNegra/Plateada` nunca se invocan; igual `Claw::pickupLeft/Right`. La recolección real corre por la vieja secuencia **inline bloqueante** (`main.cpp:1137-1186`) — la misma que RESILIENCIA marcó por bloquear UART. **El equipo tunea código fantasma.**
- **P0 segundo eje (causa raíz de #123/B6):** `ball_counter` y `veces_deposit` tienen init global `=2` (`main.cpp:82-83`) que contradice su reset `=0` (solo en case 2). No se resetean en switch-off → un re-arranque por switch deja al robot depositando/saliendo con 0 víctimas.
- Confirmado **#57** (ambas ramas `-90` en main.cpp:1258 y 1263; el patrón correcto que discrimina por `pared==` ya existe 17 líneas arriba). Pinza plateada sin delay entre `lower()` y `sortLeft()`. **Salida final del cuarto NO implementada** (green_state==10 comentado con errores de compilación, `pelotita()` vacía) → el robot no completa la evacuación, queda contra la pared hasta switch-off.

**Sensores (`teensy-02-sensores.md`):** 10 hallazgos S-01..S-10. Central: **`cead75e` revirtió los fixes de sensores #59/#60/#61/#62** → firmware menos resiliente (sin timeout en `colorDataReady`, `while(1)` infinito ante fallo de init de BNO055/APDS9960 sin alerta visible).

**Serial lado Teensy (`teensy-05-serial-teensy.md`):**
- **P0 estructural:** `serialEvent5()` **NO funciona como callback** de Teensyduino porque `loop()` casi nunca retorna (vive en `while(rutina=="linea"/"rescate")` infinitos). La recepción depende de 9 llamadas manuales dispersas, atadas a sensores bloqueantes.
- **Mayor valor/riesgo:** el handshake 0xFA de #72 está implementado **solo en la RPi**; el Teensy **nunca escribe 0xFA**. El fail-safe de reset es **ilusorio**; solo falta el emisor (~15 min). #63/#70/#72 siguen abiertos.

> **Recomendación de los auditores (unánime):** **NO reescribir a FSM antes del mundial.** Atacar por bloques con quick-wins seguros primero (init de contadores, delay plateada, signo de #57, emisor 0xFA, borrar/activar la FSM muerta), y dejar el rediseño del PID y la salida final del cuarto a sesiones de diseño + banco con ruedas al aire.

### 2.2 PROGRAMAS — RPi (percepción + decisión + threading)

**Percepción (`rpi-01-vision.md`, 12 findings V18-01..12):**
- **V18-01 (P0, binario, NO confirmado):** el parseo del tensor TFLite asume formato `[N,6]` con NMS embebido, pero `metadata.yaml` dice `end2end:false`. Si el TFLite no trae NMS, el output es `[1,8,8400]` y el loop `for det in out` **crashea el infer_thread** (que además no tiene try/except, #111) → **rescate no funciona EN ABSOLUTO**. Hay que medir `out.shape` en 48 h. Es el #124/B7.
- **#B2 (P1):** `silver_mask` usa `frame_resized` (BGR) con umbrales medidos en HSV, mientras el rojo sí usa `hsv_frame`. Es el **único trigger de entrada a rescate**.
- **#B9 (P1):** rojo `H∈[1,7]` sin wrap → pierde el rojo en H≈170-179. Verde LAB con ventana angosta, frágil a iluminación.
- **MATIZA #B3:** las clases del modelo **NO están invertidas** (CLASS_NAMES coincide con metadata). Lo invertido son los **nombres de sub-estados de depósito** + hay duplicación de filtros (infer_thread vs select_target_from_list) → deuda de mantenibilidad con alto riesgo de regresión, no detección rota.
- Causa raíz transversal: **exposición/WB de cámara sin fijar** → inestabilidad de color. Reconoce lo ya resuelto en este branch (clamp_byte #66, timeout serial #73, recovery de None #65, guard HEADLESS #64).

**Decisión / FSM alto nivel (`rpi-02-decision.md`, D1-D12):**
- **D2 (P0 de puntaje):** la inversión de nombres de clase se propaga a **4 sitios de decisión**, bloqueado por #124/B7.
- **D4 (P0):** la FSM 'depositar' es un sub-estado frágil que **ciega el YOLO a todas las víctimas**, sin branch propio ni transición de retorno → robot clavado en la zona verde.
- **D1 (P1):** la decisión de verde mezcla ROIs incompatibles (franja 60-90 vs 90-120) → giros de intersección potencialmente invertidos. D1 y D4 tocan lógica calibrada a mano → sesión de diseño + banco, NO quick-win.
- **Quick-wins listos:** D5 (target sin ponderar score/cercanía), D7 (CentroidTracker sin max_distance), D8 (cy ignorado), D12 (print en hot-path).

**Comms + threading RPi (`rpi-03-comms-threading.md`):** detalle completo en el archivo; refuerza #110 (cx_black sin init), #111 (infer_thread sin try/except), #113 (camthreader sin Lock → frame desgarrado), #108 (sin auto-restart de Main.py).

### 2.3 COMMS + ESP32

**Protocolo serial (`comms-01-protocolo-integral.md`):**
- Protocolo real: downlink RPi→Teensy = frame posicional de 8 bytes `[0xFF,speed,0xFE,angle,0xFD,green,0xFC,silver]` **sin length/CRC**; uplink Teensy→RPi = bytes sueltos 0xF9/0xF8/0xFF aperiódicos.
- **Hallazgo central NUEVO — REGRESIÓN por `cead75e`:** el protocolo quedó **desincronizado entre placas**. La RPi (HEAD) ya tiene el protocolo nuevo (maneja 0xFA, clamp, flush, timeout, drain con while), pero el Teensy fue revertido a una versión que **nunca emite 0xFA**, lee 1 byte por llamada y descarta bytes en runTime/runDistance. Resultado: el manejador TEENSY_BOOT de la RPi es **código muerto** y un reset del Teensy en pista deja el robot inerte con falsa sensación de cobertura.
- **Corrección de dato del doc previo:** el RX buffer real de Serial5 es **64 bytes** (no 1 KB). Con 240 B/s y maniobras bloqueantes sin drenar, el buffer **desborda en ~0,27 s**, perdiendo frames y desalineando el framing.
- **#53 (heartbeat) sigue sin implementar en ambos lados** (P0): cuelgue de Pi deja `robot.steer` del último comando activo para siempre. #63/#70 siguen sin arreglar en HEAD.

**ESP32 / SuperTeam (`comms-02-esp32.md`):**
- El módulo ESP32 **NO está incorporado**: no existe ni como hardware ni como software. Solo aparece como propuesta (`hardware/cambios_de_hardware.md`, firmada por Benjamin 2026-04-28) y como issue #84 (con OTRA arquitectura: Bluetooth nativo RPi vía `bleak`, archivo `superteam.py` que no existe).
- **Hallazgo de mayor riesgo:** el firmware **YA aplicó el remapeo de pines** de la propuesta (BUZZER 35→31, LED_ROJO 34→30, commit 073b8a2) para hacerle lugar a una ESP32 **que nunca se montó**, dejando los pines 34/35 sin función y `Serial8` sin inicializar → **estado intermedio inconsistente**. Hay **dos planes de SuperTeam incompatibles sin coordinar** (ESP32-Teensy vs BT-RPi); decidir uno es prerrequisito de todo.

### 2.4 HARDWARE / BOM

**Documentación (`hw-01-bom-planos-evolucion.md`):** el repo tiene material valioso (BOM tabulado, esquemático 2026, power-tree, datasheets, `cambios_de_hardware.md` de 716 líneas con 4 mejoras argumentadas). **Problema estructural grave para un TDP de mundial:** las **tres representaciones del hardware NO coinciden** entre sí ni con el robot real:
1. Firmware/robot: IMU BNO055, relé en pin 0, sin ESP32/finales/conductividad.
2. Esquemático PDF 2026: dibuja BNO055 + ESP32 + 2×LED-12V + relé = estado **futuro propuesto**.
3. PCB editable (`PCB.json`): byte-equivalente al board Roboliga 2024, todavía con **MPU6050** → **no se puede re-fabricar el board real desde el repo**.
- `hardware/bom/` está vacío (solo `.gitkeep`); el BOM real vive escondido en `electronics/PCB_Main/README.md` e incompleto. **No existe ningún CAD/STL/STEP 2026.** Recuperable con ~10-15h de edición de markdown + relevamiento del robot, sin tocar firmware.

**Evaluación crítica (`hw-02-evaluacion-critica.md`):** la **arquitectura de diseño es acertada y alineada con campeones**; la debilidad está en la implementación de potencia/mecánica y en documentación engañosa. Los 3 riesgos que más pueden costar una corrida en Incheon:
- **P0:** alimentación de la RPi por un **MP1584 sub-dimensionado** (reinicios que matan el objetivo de auto-recuperación 8/10) → necesita buck ≥5A real.
- **P0:** ausencia total de **fusible** y de protección/telemetría de batería LiPo.
- **P1:** tracción mixta 2 omni + 2 fijas sin suspensión → slip/vuelco en rampa de 25°.

### 2.5 DOCUMENTACIÓN — puntajes estimados HOY

| Documento | Pts máx | **HOY** | Tras quick-wins | Con cuerpo completo | Estado |
|---|---:|---:|---:|---:|---|
| **TDP** | 102 | **~6–12** | ~26–37 (≈6h) | ~71–89 (≈26h) | No existe como archivo. `doc-01-tdp.md` |
| **Poster** | 18 | **0** | ~5–8 (≈2h con lo existente) | 13–14 realista / 16–18 con #41+testing | No existe. Bloqueo de ownership Canva. `doc-02-poster.md` |
| **Video** | 24 | **0** | — | 20–22 potencial | No existe. Clips crudos inservibles. `doc-03-video.md` |

**TDP (`doc-01-tdp.md`):** a 30 días, el TDP **sigue sin existir** (no hay .md/.docx/.pdf de TDP, no existe `docs/tdp/`). El único avance en 3 semanas fue inicializar `TEST_LOG.md` (#93 cerrado) pero **vacío de datos reales** → criterio Reliability Tests (~24 pts) vale 0. **Cerrar #93 sin datos crea métrica de avance engañosa.** El material crudo es rico (CAD ortográfico, esquemático, PCB.json, BOM, ~24 programas de test) pero nada está volcado en estructura de rúbrica. **Riesgo de gobernanza:** Lucio dice tener un draft de TDP "desarrollado en su mayoría" en Google Drive (issue #46) que Enzo pidió dos veces sin éxito → vive **fuera de control de versiones, invisible para jueces. Riesgo de fidelidad:** docs aspiracionales (ruedas de silicona, rocker-bogie, VNH5019/INA219 que no están en el BOM) que un juez detecta si entran como "as-built".

**Poster (`doc-02-poster.md`):** 0/18. El bloqueo principal es de **ownership y comunicación**, no de contenido: issue #45 (owner @Laumonteros) tiene dos pedidos de acceso al Canva sin responder. El material textual está al ~70% (premio nacional 2025 confirmado, PCB propia, lista de innovaciones, Mermaid de arquitectura). Falta lo visual (fotos del equipo y robot — issue #94, 21 días sin avance). **Única acción no delegable del coach: agendar la sesión de fotos y exigir el link del Canva.**

**Video (`doc-03-video.md`):** 0/24, sin cambios desde el 10-05 (postergación consciente por el freeze, legítima, pero la ventana ya se abre). **Aporte nuevo decisivo:** la inspección con ffprobe de los 5 clips crudos en `software/raspberry/Videos/` reveló que son **grabaciones POV de la cámara onboard** (fisheye mirando el piso, sin audio, 4:3 baja resolución) → **inservibles como material de presentación. En ningún frame se ve el robot.** Consecuencia: la sección 3 del video (la más larga, 2:15) que el plan daba como "editar lo viejo" en realidad requiere **FILMAR tomas externas nuevas**. El cuello de botella de 18 de 24 pts es ejecutar #94. **Lo más urgente: confirmar la deadline real de subida del video.**

### 2.6 NOVEDAD DEL EQUIPO (`estrategia-02-novedad.md`)

La **arquitectura del robot NO es novedosa** — es el "patrón campeón" que el propio equipo documentó (Overengineering², Airborne, Danesh). Presentarla como innovación **bajaría la nota**. La novedad real y defendible está en **decisiones derivadas de leer el reglamento 2026** y resolver los 3 problemas nuevos que los campeones 2024/2025 no enfrentaron:
- **N1 (el más sólido):** pipeline de visión anti-destello adaptativo (anti_flash + AGCWD + Zero-DCE conmutable, contra regla 3.9 de LEDs). **Implementado y corriendo** en `Main.py:188-248`; solo falta medir el beneficio.
- **N2 (mejor valor/esfuerzo):** validación multimodal de víctima (YOLO + conductividad + reflectancia C/IR del APDS9960, contra regla 3.10). HOY **diseñado en `cambios_de_hardware.md`, NO embarcado** en firmware.
- **N3:** detección de salida por reflectancia con LED 12V (contra 3.9). Diseño no productivo.
- **N4:** metodología de QA asistida por IA. Proceso real, resultado pendiente (TEST_LOG vacío).
- **Riesgo transversal #1:** presentar **diseño como implementación**. Vender resiliencia/auto-recuperación es el claim **más peligroso** porque heartbeat/handshake/CRC están sin implementar.

### 2.7 USO DE IA (`doc-04-uso-de-ia.md`)

- **IA de visión:** YOLOv8n (256×256, 4 clases) entrenado en Roboflow + Colab sobre **dataset propio** "Roboliga 2025" (2496→5108 imágenes), exportado a ONNX/NCNN/TFLite. El robot corre el TFLite FP32. Cada decisión (nano, 256, FP32 vs INT8, ONNX→TFLite) está justificada. **El ML de visión está premiado en la rúbrica.**
- **IA como herramienta:** uso maduro, transparente y declarado de Gemini, ChatGPT y Claude Code, con coautoría firmada en git y regla en CONTRIBUTING.md. **El código del robot lo escriben los alumnos; la IA audita/mentorea.**
- **Aceptabilidad RCJ:** ambos usos son defendibles. El riesgo no es usar IA sino: (a) no dejar por escrito la frontera "docs-IA vs código-de-alumnos", (b) no poder defenderlo en la entrevista del jurado, (c) volcar al TDP docs IA stale que contradicen el código. **Heads-up:** el repo NO tiene las reglas RCJ 2026 (solo 2023 + Roboliga 2025) — leer la letra 2026 antes de redactar la declaración de IA.

---

## 3. DESEMPEÑO DEL EQUIPO

**Balance de carga (datos duros, `git shortlog --no-merges origin/main`):** Benjamin ~14 commits / Laureano 7 (todos en marzo) / Lucio 5. **El 100% del código del último mes es de Benjamin.** Los dos dueños nominales de subsistema **no escriben su propio subsistema.** Esto es la bandera roja de dirección más grave del proyecto.

### 3.1 Laureano Monteros (@Laumonteros) — firmware Teensy (owner)
**Fortaleza:** talento de arquitectura por encima del promedio del equipo. Su FSM de pinza (`claw.cpp`) es no bloqueante y bien hecha; su mejor commit (`ec8e6ab`, Timeout/Watchdogs) es trabajo de nivel.
**Debilidad:** disciplina de proceso e involucramiento sostenido muy por debajo de lo que exige un mundial. **6 commits, todos en marzo, cero en abril-mayo.** Su mejor commit **NO es ancestro de `main` (trabajo perdido por merge-base)**; su FSM de pinza está **muerta**; sus propios bugs (B5/B8/#57) siguen sin atender; 14 issues asignados OPEN; 0 entradas en TEST_LOG.
**Qué pedirle:** ejecutar **en código** su issue de arranque #115 — recuperar SUS timeouts (#60/#61/#112) — que es a la vez la palanca de mayor impacto técnico y la más motivante. Luego validar en banco la decisión sobre #122/#125. **≥3 commits de código mergeados antes del 2026-06-10.**

### 3.2 Lucio Saucedo (@luciouriel2011) — RPi visión (owner)
**Fortaleza:** competencia probada — su fix de firmware (strcmp, PR #36 mergeado) y su TDP de 411 líneas (en `documentation_and_diagrams`) demuestran capacidad técnica y de redacción.
**Debilidad:** **0 líneas vivas en TODO el código de visión** (confirmado por git blame) pese a ser el dueño. Sus dos aportes con sustancia cayeron **fuera de dominio**. PR #42 abierto y abandonado desde marzo. Su draft de TDP está varado sin mergear, en inglés sin review, con error de hecho ("RPi 5" vs 4B). **Última actividad 2026-04-25 → +1 mes de silencio** entrando a la recta final.
**Qué pedirle:** **traer el draft de TDP de Google Drive al repo esta semana** (es la pieza de mayor valor parado) y tomar **#110 (cx_black, crash de 1 línea)** + #111 en código. El problema no es talento: es aplicación fuera de dominio y entregables sin cerrar.

### 3.3 Benjamin Villagran (@benjaminvillagran) — RPi + hardware + banco
**Fortaleza:** es el #2 del repo en volumen y el **mejor documentador**. Su trabajo P0/P1 (drivebase, main.cpp, Main.py, systemd, TDP, testeo honesto T-001/T-002) es la columna vertebral del último mes.
**Debilidad:** **disciplina de entrega** — su mejor trabajo está **varado sin mergear** en PR #129 (OPEN, 0 reviews, +5707/-506, 39 files, 7 días parado) a 30 días de Incheon. Es a la vez el productor único (bus-factor) y el mejor candidato para hacer pairing.
**Qué pedirle:** **partir #129 en dos** (PR-código mergeable ya + PR-TDP después) y hacer **pairing con Lucio y Laureano** para transferir conocimiento antes del pit. Separar lo que es suyo de lo que no (threading roto #111/#113 no es suyo; la desincronización de hardware es coordinación de equipo, no su falla).

---

## 4. ANÁLISIS ESTRATÉGICO CRÍTICO (`estrategia-01-critico.md`)

**¿Trabajan en lo correcto?** **SÍ en el "qué", con dos desvíos de prioridad.** Los issues #120–#128 (CORRECTITUD) atacan bugs que cuestan puntos en pista; los #57–#113 (RESILIENCIA) atacan lo que impide completar la corrida; el foco en systemd/auto-restart es la mejor relación puntos/esfuerzo del proyecto. **El problema no es talento ni criterio — es ejecución de cierre.**

**Desvío #1 — el TDP se comió el sprint final de código.** PR #129 **mezcla código crítico de robot con un TDP completo** (~20 diagramas, BOM, assets), cierra/refiere a ~35 issues a la vez → **imposible de revisar rápido y peligroso de mergear con confianza.** El TDP (que no corre en pista) está **bloqueando la entrada de los fixes que sí corren en pista.**

**Desvío #2 — scope creep impropio a 30 días.** Technical Challenges (#88), boot-mode (#81), Bluetooth SuperTeam (#84), refactors (#82/#83/#87) son legítimos para un equipo maduro, pero a 30 días con un solo programador **distraen**. El objetivo es "podio + 8/10 + aprender", no ganar challenges en el primer mundial. **Postergar a post-incheon.**

**Deuda de higiene:** 207 MB de binarios sin Git LFS (#69) → repo intransportable si hay que clonar limpio en el hotel de Corea; `AUDIT-ACTION-PLAN.md` obsoleto desde 23-feb (la fuente de verdad declarada está muerta, la verdad vive en los issues); 8 PRs abiertos colgando.

**Correcciones de rumbo (resumen — el detalle por semana va en la sección 5):**
1. **Desbloquear y partir #129 esta semana** (tarea #1 del proyecto).
2. **Romper el bus-factor:** reactivar a Laureano (firmware) y Lucio (visión) en CÓDIGO ya, con pairing.
3. **Convertir el TEST_LOG en hábito de banco** (regla de oro #3 del CLAUDE.md, literal: ningún fix se mergea sin su T-XXX).
4. **Recortar alcance:** etiquetar `post-incheon` todo lo que no sea core robot + TDP base.
5. **Fijar freeze (2026-06-15) y cadencia de merge ≤48h.**

**Lo que está BIEN (para no desmoralizar):** la calidad del análisis de bugs es de nivel mundial; el testeo que sí hicieron (T-001/T-002: FPS 91.33, curva de batería, error de odometría) es honesto y riguroso; la decisión de **NO tocar ciertos bugs** porque el comportamiento observado compensa es criterio de competencia correcto. El problema es 100% recuperable si se actúa esta semana.

---

## 5. PLAN DE TAREAS POR SEMANAS HASTA INCHEON

> **Régimen de fases vigente:** **Track A** (firmware/comms) push libre ya cerró (≤2026-05-26) → ahora **gate de Enzo** (todo entra por review). **Track B** (docs/visión) push libre **≤2026-06-11** → luego gate de Enzo. **Logística:** última semana. **Freeze de código propuesto: 2026-06-15.**
>
> Leyenda de responsables: **B**=Benjamin, **L**=Lucio, **La**=Laureano, **E**=Enzo (coach), **D**=Director.

### SEMANA 0 — "Destrabe" (2026-05-31 → 06-07) · LA SEMANA QUE MÁS MUEVE LA AGUJA

**Track A (firmware/comms — gate Enzo):**
- **[E+D, 48h] Review y PARTIR PR #129** en (a) PR-código (drivebase, main.cpp, Main.py, camthreader, systemd, `priority_fix_flags.h`, test/evacuation) → **mergear primero con sesión de banco**; (b) PR-TDP → después. **Mergea T-001/T-002 a `main`.** *(R-1)*
- **[La] #115 → recuperar timeouts #60/#61/#112** en código (runDistance/runAngle/colorDataReady). *(R-4)* Su mejor trabajo perdido vuelve a la vida.
- **[B, 15 min] #72 → emisor 0xFA en el boot del Teensy** (el handshake hoy es ilusorio; solo falta el emisor). *(R-4)*
- **[B/La quick-wins seguros de rescate] #57** (signo de la rama pared), **init de `ball_counter`/`veces_deposit`** y reset en switch-off (causa de #123/B6), **delay pinza plateada**. *(R-5)*

**Track B (docs/visión — push libre hasta 06-11):**
- **[L, P0 24-48h] #124/B7 → medir `out.shape` del TFLite** (binario: define si el rescate funciona o crashea). Luego **#110 (cx_black)** + **#111 (try/except en infer_thread)**.
- **[L] Traer el draft de TDP de Google Drive al repo** (issue #46) → PR a `docs/tdp/`. **Destraba ~30-40 pts de TDP.**
- **[E, no delegable] Exigir link del Canva (#45) y AGENDAR la sesión de fotos (#94)** para este o el próximo sábado. Bloquea Poster (18) + Video (18 de 24).
- **[D/E] Decidir SuperTeam: Ruta B (BT-RPi) ya, ESP32 como migración** → cierra el limbo de #84.

**Hito SuperTeam:** **SIMULACIÓN 1 (Ejercicio 1 — "Lenguaje común y coreografía sin radio")** en una sesión de taller de esta semana o la próxima. Detalle en §6. *(no afecta el puntaje individual; es upside de aprendizaje, bajo costo.)*

**Gobernanza:** **[D/E] etiquetar `post-incheon`** los issues #88/#81/#82/#83/#87 (scope creep). **[B] migrar binarios a Git LFS (#69)** antes de que alguien clone limpio en Corea.

**Métrica de salida de Semana 0:** PR-código de #129 mergeado a `main`; ≥1 commit de código de La y de L; draft TDP en el repo; fecha de fotos agendada; ≥2 entradas reales en TEST_LOG de `main`.

### SEMANA 1 — "Estabilizar y filmar" (2026-06-08 → 06-14)

**Track A (gate Enzo):**
- **[La] #122/B5 (velocidad 55 en curva) + #125/B8 (runAngle 180)** → validar en banco la decisión (tocar vs no tocar), documentar T-XXX. *(causa #1 de salidas de pista.)*
- **[La/B] Rescate:** activar la FSM no bloqueante hoy muerta **o** documentar por qué se queda con la inline, e implementar la **salida final del cuarto** (green_state==10, `pelotita()`). *(R-5)*
- **[B] #53 heartbeat serial** (ambos lados) + **#27 watchdogs (WDT)** → red de seguridad para el objetivo 8/10. *(R-4)*
- **[L] #B2 (silver_mask en HSV)** + **#B9 (rojo con wrap)** → el trigger de rescate confiable.
- **[La] #121/B1 → sesión de diseño del PID** (NO quick-win: rediseñar lazo, no cambiar signo). Ruedas al aire, midiendo RPM real.

**Track B (push libre hasta 06-11, luego gate):**
- **[B/L, sábado] Sesión de fotos #94** (robot + equipo + cámara en trípode) + **filmar tomas externas del robot ejecutando** (la sección 3 del video necesita footage nuevo, no los clips POV).
- **[L+B] Ensamblar el cuerpo del TDP** sobre el draft + material crudo (CAD, esquemático, PCB, BOM) en estructura de rúbrica. Objetivo: pasar de ~12 a ~40+ pts.
- **[La+B] #41 diagrama de bloques/flujo del software** (insumo de Poster P3 y Video sección 2).
- **[B] #96 BOM actualizado** + **#95 validar fidelidad de docs/es contra el código** (sacar lo aspiracional que un juez detecta).

**Hito SuperTeam:** **SIMULACIÓN 2 (Ejercicio 2 — "Handshake, handoff y degradación con canal real")** en una sesión de taller de esta semana. Crea `superteam.py`. Detalle en §6.

**Métrica de salida de Semana 1:** firmware estable en banco (sin salidas de pista en curva, rescate completa la evacuación, sin cuelgues); fotos y tomas de video tomadas; TDP ≥40 pts; ≥4 entradas en TEST_LOG.

### SEMANA 2 — "Documentar y endurecer" (2026-06-15 → 06-21) · **FREEZE DE CÓDIGO el 15**

**Track A (post-freeze: SOLO fixes P0 verificados en banco):**
- **[La/B] #126/B10 → calibrar la constante de encoder** (25 pulsos/cm) con medición real de distancia; corregir ISR CHANGE x2 si afecta. *(impacto acotado a maniobras lineales.)*
- **[B] Hardware P0:** confirmar/instalar **buck ≥5A real para la RPi** + **fusible/PTC** (los reinicios de la Pi matan el 8/10). *(`hw-02` P0.)*
- **[E] Régimen de banco:** 2 sesiones fijas/semana, cada una produce ≥1 T-XXX. Cerrar `MEDICIONES_PENDIENTES.md` (voltaje bajo carga, precisión de runAngle).

**Track B (gate Enzo — empuje fuerte de docs):**
- **[L+B] TDP cuerpo completo** → objetivo 71-89 pts. Incluir la sección de visión/IA (lista en `doc-04`) y la declaración de "AI tooling disclosure".
- **[La/B] Maquetar Poster en Canva** con fotos + flowchart → objetivo 13-18 pts.
- **[B] Editar Video** con tomas nuevas + narración en inglés + subtítulos → objetivo 20-22 pts. **Confirmar deadline de subida (irreducible).**
- **[E/D] Pasar `cambios_de_hardware.md` de "propuesta" a "as-built" honesto** (marcar qué está implementado y qué no, para que no contradiga el TDP).

**Métrica de salida de Semana 2:** robot congelado y validado en banco; TDP, Poster y Video en borrador avanzado listos para revisión final.

### SEMANA 3 — "Logística y ensayo" (2026-06-22 → 06-29)

- **[Todos] Ensayos completos de corrida** (línea + rescate + recuperación) cronometrados, midiendo el 8/10 real de auto-recuperación. Pairing en el pit: La y L deben poder debuggear su subsistema bajo presión.
- **[E/D] Subir TDP, Poster y Video** según deadlines oficiales. **Cerrar el repo:** LFS, PRs colgados, `AUDIT-ACTION-PLAN.md` actualizado o jubilado.
- **[B] Kit de pit:** SD clonada (#38), repo clonable offline, baterías cargadas, herramientas, piezas de repuesto.
- **[Todos] Checklist de hardware:** capacitores de filtro en motores, alarma de LiPo, finales de carrera (`hw-02` P1).
- **Viaje a Incheon.** En el venue: ventana SuperTeam (aplicar lo entrenado en las simulaciones 1 y 2).

### Mapa issue → semana → persona (referencia rápida)

| Issue | Qué es | Semana | Responsable |
|---|---|---|---|
| **PR #129** | Partir + mergear código | S0 | B + E (review) |
| **#100, #119** | Mergear (skill coach + fix nombre) | S0 | E/D |
| **#124/B7** | Medir out.shape TFLite | S0 | L |
| **#110, #111** | cx_black + try/except infer | S0 | L |
| **#72** | Emisor 0xFA Teensy | S0 | B |
| **#57** | Rescate: signo rama pared | S0 | B/La |
| **#112** (#60/#61) | Recuperar timeouts firmware | S0 | La |
| **#45, #94** | Canva + sesión de fotos | S0→S1 | E (no delegable) |
| **#122/B5, #125/B8** | Velocidad curva + runAngle180 | S1 | La |
| **#53, #27** | Heartbeat + WDT | S1 | B |
| **#B2, #B9** | silver_mask HSV + rojo wrap | S1 | L |
| **#121/B1** | Rediseño PID (diseño+banco) | S1 | La |
| **#41** | Diagrama de software | S1 | La/B |
| **#95, #96, #97, #98** | TDP/BOM/fidelidad/plan docs | S1–S2 | B/L |
| **#123/B6** | Salida anticipada cuarto (init contadores) | S0–S1 | La/B |
| **#126/B10** | Calibrar encoder | S2 | La/B |
| **#69** | Git LFS | S0 | B |
| **#88/#81/#82/#83/#87/#84** | Scope creep → `post-incheon` | S0 | D/E |

---

## 6. LAS 2 SIMULACIONES SUPERTEAM (para que Enzo las asigne)

> **Marco (reglamento §6.3):** el SuperTeam Challenge es **independiente** y **NO afecta el puntaje individual** — tiene premio propio y premia **cooperación entre equipos de distinto idioma nativo**. La tarea exacta se anuncia **recién en Incheon** y exige "cambios sustanciales de software". El canal está acotado a **2.4 GHz, ≤100 mW EIRP** (§1.3.1), con "spectrum availability not guaranteed" (la sala estará saturada → hay que tolerar pérdida). **Detalle completo de ambos ejercicios en `superteam-00-dos-ejercicios.md`.** Las dos sesiones son **secuenciales y acumulativas**; cada una cierra con una entrada en TEST_LOG.

### SIMULACIÓN 1 — "Lenguaje común y coreografía sin radio" (~2h30) — **Semana 0 o 1**
- **Objetivo:** que el equipo aprenda a **acordar un protocolo de cooperación en minutos, sin idioma común** (solo dibujos/gestos, ventana de 15 min cronometrada) y ejecutarlo **sin radio** (cooperación por percepción + tiempo + señales físicas LED/buzzer/cartel). Simula la ventana de colaboración de Incheon y produce el **protocolo de aplicación SuperTeam** que hoy no existe en ninguna forma.
- **Cuándo:** una tarde de taller, **Semana 0 o 1**. Cero radio = bajo riesgo, no depende de la decisión ESP32 vs BT.
- **Qué preparar:** dos robots (o robot + "robot humano" con caja/LED/cartel como fallback); pista con un **checkpoint de handoff** y zona de evacuación; **[B] verificar en banco que LED_ROJO y BUZZER encienden** en los pines remapeados 30/31 (sin confirmar — bonus de diagnóstico); papel y fibrón para la "tarjeta de protocolo" (**solo íconos, prohibido escribir palabras**); cronómetro; cámara.
- **Criterio de éxito:** handoff sin colisión en **2/2** corridas finales; tarjeta de protocolo solo con íconos e interpretada igual por ambos sub-equipos; acuerdo en ≤15 min; lista de **≥3 mensajes** "que necesitábamos por radio" (insumo directo de la Simulación 2).

### SIMULACIÓN 2 — "Handshake, handoff y degradación con canal real" (~3h) — **Semana 1**
- **Objetivo:** construir por primera vez un **canal inter-robot funcional mínimo** (Ruta B del issue #84: Bluetooth nativo de la RPi, **sin abrir el robot**) y **estresarlo** con la condición real de Incheon (espectro saturado, pérdida de paquetes). Implementa handshake + mensaje con contenido + barrera + **prueba de degradación** (cortar radio → los robots NO se cuelgan, siguen su pista individual). Materializa en radio la "tarjeta de protocolo" de la Simulación 1.
- **Cuándo:** una tarde de taller, **Semana 1** (después de la Simulación 1).
- **Qué preparar:** dos Raspberry Pi 4B (o Pi + **celular Android** con app BLE como fallback); crear `software/raspberry/final_rpi/superteam.py` (hoy inexistente); `bleak` instalado. **Regla dura:** el canal SuperTeam **NO toca el UART frágil Teensy↔RPi** (ese hot-path ya está al límite — #53/#63).
- **Criterio de éxito:** ping-pong `HELLO|ROJO`↔`HELLO|AZUL` funcionando; **1 mensaje con contenido** + **1 barrera** ejecutados; prueba de degradación pasada (radio apagada → ambos robots siguen sin colgarse). Deja documentada la migración a Ruta A (ESP32) y produce el primer entregable concreto de #84.

---

## 7. CIERRE DEL DIRECTOR — Las 3 cosas que Enzo tiene que hacer

Si Enzo solo puede hacer tres cosas esta semana, son estas — en este orden:

### 1. DESBLOQUEAR Y MERGEAR EL CÓDIGO DE #129 (con banco) — la tarea #1 del proyecto
Pedirle a Benjamin que **parta #129 en dos**: PR-código (drivebase, main.cpp, Main.py, systemd, `priority_fix_flags.h`) → mergear **primero** con una sesión de banco; PR-TDP → después. **Mientras #129 esté abierto, el robot que viaja a Incheon tiene B1–B10 vivos y el TEST_LOG de `main` vacío.** Verificado a mano: el PID saturado sigue en `main`. Métrica: PR-código en `main` **antes del 2026-06-05**, con T-003 documentando la corrida de validación.

### 2. ROMPER EL BUS-FACTOR — poner a Laureano y Lucio a escribir CÓDIGO ya, con pairing
Hoy el proyecto depende de una sola persona y los dos dueños nominales **no podrán asistir en el pit** porque no tocaron su propio subsistema. Exigir **commits de código** (no análisis): Laureano ejecuta #115 (recuperar SUS timeouts); Lucio toma #124/B7 + #110 y **trae su draft de TDP de Google Drive al repo**. Pairing Benjamin↔La/L. Métrica: ≥3 commits de código de cada uno mergeados antes del 2026-06-10.

### 3. AGENDAR LA SESIÓN DE FOTOS Y EXIGIR EL CANVA — destrabar 48+ pts de presentación
Esta es la **única acción no delegable del coach** y la de mayor ROI por hora en documentación: una sesión de un sábado con robot + equipo + cámara desbloquea **Poster (18 pts) + Video (18 de 24 pts) + TDP §Mechanical**. Exigir el link del Canva (#45, lleva 21 días bloqueado por ownership) y confirmar la **deadline real de subida del video** (único piso de calendario irreducible). Sin esto, el equipo llega a Incheon con un robot que (quizás) anda pero **invisible para los jueces** — y en Rescue Line la mitad del puntaje del TDP/Poster/Video es presentación, no robot.

---

> **El diagnóstico es duro pero la conclusión es optimista:** el talento y el criterio técnico de este equipo están a nivel mundial — los issues #57–#128 lo prueban. **Lo que falta no es saber qué hacer, es cerrar: mergear, repartir y documentar en la rama que cuenta.** A 30 días, con las tres palancas de arriba movidas esta semana, "podio + 8/10 + aprender" sigue siendo alcanzable.

---

*Auditorías sintetizadas (24 archivos en `project/backlog/staging/auditoria-integral-2026-05-18/`):* `teensy-01-drivebase-pid`, `teensy-02-sensores`, `teensy-03-linea-fsm`, `teensy-04-rescate-fsm`, `teensy-05-serial-teensy`, `rpi-01-vision`, `rpi-02-decision`, `rpi-03-comms-threading`, `comms-01-protocolo-integral`, `comms-02-esp32`, `hw-01-bom-planos-evolucion`, `hw-02-evaluacion-critica`, `doc-01-tdp`, `doc-02-poster`, `doc-03-video`, `doc-04-uso-de-ia`, `estrategia-01-critico`, `estrategia-02-novedad`, `superteam-00-dos-ejercicios`, `INFORME-INTEGRANTE-{laureano,lucio,benjamin}`, `equipo-0{1,2,3}`.
*Auditorías previas citadas (no repetidas):* RESILIENCIA (#53/#27/#57–#119), CORRECTITUD (#120–#128, bugs B1–B10).
*Datos duros verificados sobre el repo el 2026-05-31:* `origin/main` tip `1841dcb` (PR #101 mergeado); B1 vivo en `origin/main:software/teensy/firmware/lib/drivebase/drivebase.cpp:50`; `priority_fix_flags.h` ausente en `main`; TEST_LOG de `main` con las 4 categorías vacías; PR #129 OPEN (+5707/-506, 39f, 0 reviews); 73 issues abiertos; 8 PRs abiertos.
