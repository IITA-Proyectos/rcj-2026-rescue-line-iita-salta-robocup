# Auditoría Integral 2026-05-18 — Estrategia 02: ANÁLISIS HOLÍSTICO + NOVEDAD DEFENDIBLE

> **Dominio:** mirada de sistema completo (HW + firmware + visión + comms + resiliencia) con un único objetivo: **¿qué puede el equipo IITA Salta presentar legítimamente como aporte propio y diferencial ante el jurado y en el TDP?**
> **Pregunta que responde este informe:** de todo lo que hace este robot, **¿qué es genuinamente novedoso (o defendible como tal) y qué es estándar de la categoría?** Sé honesto: lo estándar se descarta explícitamente.
> **Alcance:** SOLO lectura. No se modificó código ni hardware. No se abrieron issues.
> **Checkout:** `feature/initialize-testing-log` (idéntico a `main` post-PR #101, HEAD `5a868ea`).
> **Autor:** auditoría holística, Claude Code (Opus 4.8, 1M), bajo supervisión de @gviollaz. Corrida 2026-05-31.
> **Marco de framing (memoria del coach):** esto NO es una lista de "features a vender". Cada ángulo de novedad lleva **por qué es defendible**, **qué tan honesto es el claim hoy**, y **el riesgo de sobre-venderlo** (un jurado técnico de mundial pregunta y desarma claims inflados en la mesa). Un ángulo de novedad mal sostenido **resta** credibilidad a todo el TDP.

---

## 0. Resumen ejecutivo

**Tesis central:** la arquitectura del robot (Teensy 4.1 + RPi 4B, BNO055, ToF+ultrasonido, YOLOv8, 4WD, OpenCV+PID) **no tiene nada de novedoso** — es exactamente el "patrón campeón" que el propio equipo documentó en `research/completed/2026-02-23-analisis-campeones-mundiales-rescue-line.md` y `docs/es/referencia-equipos-top-rescue-line-2024-2025.md` (Overengineering², Airborne, Danesh). Presentar la arquitectura como innovación sería un error: el jurado la ve en cada robot top y le baja la nota a "describe lo estándar" (3-4, no 5-6 en la rúbrica).

**Pero el equipo SÍ tiene novedad real, y está concentrada en un patrón claro:** las decisiones de ingeniería **derivadas de leer el reglamento 2026 línea por línea y resolver problemas específicos que ese reglamento introdujo** (regla 3.9 luces LED intermitentes; regla 3.10 víctimas falsas; regla 6.3 SuperTeam con equipos asignados en el momento). Ahí es donde el equipo hizo trabajo propio, original y defendible — no copiando a los campeones (que compitieron bajo reglas 2024/2025, **sin** esas reglas nuevas), sino resolviendo problemas que los campeones **todavía no enfrentaron**.

**Los 4 ángulos de novedad defendibles, ordenados por solidez del claim:**

| # | Ángulo | Qué tan novedoso | Qué tan honesto HOY | Dónde vive |
|---|--------|------------------|---------------------|------------|
| **N1** | **Pipeline de visión anti-destello adaptativo** (anti-flash + AGCWD + Zero-DCE conmutable), diseñado contra la regla 3.9 (LEDs intermitentes) | **Alto** — no aparece en ningún equipo de referencia; es respuesta directa a una regla 2026 | **Medio-alto** — el código está escrito y corre (`Main.py`), pero falta validación documentada del beneficio | `software/raspberry/final_rpi/Main.py:188-248` |
| **N2** | **Validación multi-modal de víctima** (visión YOLO + conductividad eléctrica + reflectancia C/IR del APDS9960), contra la regla 3.10 (víctimas falsas) | **Alto** — fusión sensorial de 3 principios físicos para una decisión que la mayoría resuelve solo con visión | **Medio** — la conductividad y el uso de reflectancia están **diseñados y argumentados** (`hardware/cambios_de_hardware.md`) pero **NO integrados al firmware todavía** | `hardware/cambios_de_hardware.md` (§ conductividad, § LED 12V) |
| **N3** | **Detección de salida de evacuación por reflectancia local** (APDS9960 + LED 12V dedicado en la Teensy, fuera del lazo de visión) contra la regla 3.9 | **Medio-alto** — mover una decisión de la cámara (que falla con el destello) a un sensor aislado con iluminación propia es ingeniería de robustez original | **Medio** — argumentado y prototipado en doc; el firmware actual aún detecta salida por `green_state` de la RPi | `hardware/cambios_de_hardware.md` (§ LED 12V) |
| **N4** | **Metodología de auditoría asistida por IA con framing de riesgo** (skills + "TEMAS A ANALIZAR") como proceso de aseguramiento de calidad | **Medio** — proceso de QA inusual para la categoría; encaja perfecto con la rúbrica 2026 que ahora exige "Reliability Tests & QA" en 4 secciones | **Alto como proceso** (existe y se usa), **bajo como resultado** (los tests reales no están cargados — ver `doc-01-tdp.md`) | `.claude/skills/` + `docs/es/` + esta auditoría |

**La frase honesta de cierre del resumen:** el diferencial del equipo **no es** que use IA o doble procesador (eso lo usan todos). Es que **leyó el reglamento 2026 como ingeniero y resolvió los 3 problemas nuevos que ese reglamento introdujo, con soluciones de fusión sensorial que los campeones de 2024/2025 no necesitaron tener.** Ese es el relato de novedad que se sostiene bajo preguntas. Todo lo demás es "buena ejecución del estándar", que se documenta pero no se vende como innovación.

> **Advertencia transversal (crítica).** N2 y N3 son hoy **propuestas de ingeniería documentadas, no features embarcadas**: el firmware (`main.cpp`) **no lee** el pin de conductividad, **no usa** el APDS9960 como reflectancia (sigue con `get_color()` por mínimos cuadrados sobre 3 colores hardcodeados), y **no hay** finales de carrera ni ESP32 conectados. Si esto entra al TDP como "el robot hace X" en vez de "diseñamos e implementamos X / planeamos X", un juez que pida ver el robot detecta la inconsistencia. La auditoría de hardware (`hw-02-evaluacion-critica.md`) y la de TDP (`doc-01-tdp.md`) ya marcan esta brecha doc↔realidad como el riesgo de credibilidad #1 del proyecto. **La novedad es real y defendible; el tiempo verbal con que se presenta es lo que la hace honesta o no.**

---

## 1. Metodología: cómo separé "novedoso" de "estándar"

Para no inflar claims, usé un criterio doble:

1. **Benchmark contra los equipos de referencia que el propio equipo investigó.** Si Overengineering² (campeón 2024) o Airborne (2025, docs públicas completas) ya lo hacen, **no es novedad** — es estándar de la categoría, por más bien hecho que esté. Fuentes: `research/completed/2026-02-23-...md` y `docs/es/referencia-equipos-top-rescue-line-2024-2025.md`.
2. **Benchmark contra el reglamento 2026.** Lo que es respuesta a una regla **nueva de 2026** (que los campeones de 2024/2025 no enfrentaron) es, por construcción, terreno donde el equipo no pudo copiar y tuvo que innovar. Fuentes: `hardware/cambios_de_hardware.md` (cita reglas 3.9, 3.10, 6.3) y `project/backlog/pendientes_generales.md` (resumen reglamento 2026).

Lo que cae en "lo hace todo equipo top" se descarta en §2. Lo que sobrevive ambos filtros es novedad defendible (§3).

---

## 2. Lo que NO es novedoso (descartado con honestidad)

> El jurado de un mundial vio cientos de robots. Presentar esto como "innovación" es el error clásico que delata a un equipo que no conoce el estado del arte. Se **documenta como buena ingeniería**, nunca como aporte propio.

| Elemento del robot | Por qué NO es novedad | Evidencia |
|---|---|---|
| **Arquitectura dual SBC + microcontrolador** (RPi 4B + Teensy 4.1) | Es *el* estándar de oro de la categoría. Overengineering², Airborne, Danesh, todos lo hacen. | `research/...campeones.md §2`; `hw-02 §1` lo llama "la correcta… coincide con el estándar de los top" |
| **IMU BNO055 con fusión interna** | Overengineering² usa exactamente BNO055; Airborne usa ICM-20948. Es el sensor de fusión que usan todos. | `referencia-...top.md §9.2` |
| **ToF (VL53L0X) + ultrasonido** | Airborne reporta 5× VL53L0X. La migración a ToF es "la tendencia ganadora 2025", no un invento. | `referencia-...top.md §9.3` |
| **YOLOv8 para víctimas/zonas** | Airborne usa YOLOv8; Overengineering² migró a IA. Visión-first con red neuronal es el patrón dominante 2024-2025. | `referencia-...top.md §11.2` |
| **Line-following por OpenCV + centro de masa + PID** | Enfoque clásico documentado como "Enfoque 1" estándar. | `referencia-...top.md §5.1` |
| **4WD skid-steer + control diferencial** | "Estándar de oro". | `hw-02 §2`; `referencia-...top.md §8` |
| **Pinza multi-servo que clasifica viva/muerta** | Airborne publica brazo de doble servo; clasificar viva/muerta es requisito reglamentario, no diferencial. La de 5 servos es *capaz*, pero "más servos" no es innovación (de hecho `hw-02 §4` la critica como sobre-actuada). | `referencia-...top.md §11.4`; `hw-02 §4` |
| **Protocolo serial binario propio** | Todo equipo dual tiene uno. Y el de este equipo es **más débil** que el estándar (sin CRC, sin heartbeat, desincronizado entre placas hoy — ver `comms-01 F-1/F-2`). Presentarlo como novedad sería contraproducente: invita a preguntas que exponen sus fallas. | `comms-01-protocolo-integral.md` |
| **Pipeline multihilo captura/inferencia/control** | Buena práctica (Overengineering² usa multiprocessing), pero estándar. Y el de este equipo tiene bugs de concurrencia abiertos (#111/#113, CT-01..CT-11). | `rpi-03-comms-threading.md` |
| **Sistema de resiliencia / auto-recuperación** | **OJO — esto es tentador presentar como novedad y NO se sostiene.** El heartbeat (#53), el handshake `0xFA` (#72), el watchdog, el CRC: están **mayormente sin implementar o medio-implementados** (`comms-01 §0`: "RPi nuevo, Teensy revertido, `0xFA` nunca se emite"). El objetivo del equipo es *auto-recuperación 8/10*, pero hoy el sistema es **frágil**, no resiliente. Vender resiliencia que no existe es el claim más peligroso de todos. | `comms-01 F-1/F-2`, `rpi-03 §0`, `teensy-04 §0` |

**Conclusión de §2:** la columna vertebral del robot es competente y madura, pero **no diferencial**. Si el TDP intenta innovar acá, pierde. La novedad está en otro lado.

---

## 3. Los ángulos de novedad DEFENDIBLES

### N1 — Pipeline de visión anti-destello adaptativo (contra la regla 3.9)

**En qué consiste.** El equipo construyó un pre-procesamiento de imagen de **tres capas conmutables** que se ejecuta antes de la inferencia YOLO y de la segmentación de color, diseñado específicamente para sobrevivir a la **iluminación hostil de la zona de evacuación 2026** (LEDs blancos intermitentes que la regla 3.9 permite montar en las paredes). El código real (`Main.py`):

1. **`anti_flash_preprocess()` (`Main.py:218-237`):** detecta píxeles "quemados" por un destello (V≥215 **y** saturación baja S≤60 = blanco puro de flash, no color real), construye una máscara suavizada con Gaussiana, y **comprime selectivamente** solo esas regiones (factor 0.45) en vez de aplastar todo el frame. Es decir: ataca el destello **donde está**, preservando el resto de la imagen. Esto es una idea propia y no trivial.
2. **`agcwd()` (`Main.py:188-206`):** corrección de gamma adaptativa ponderada por histograma (Adaptive Gamma Correction with Weighting Distribution), con un caso especial que **atenúa la corrección cuando la imagen ya está clara** (`mean_v > 120` → mezcla 0.3/0.7) para no sobre-exponer.
3. **Switch Zero-DCE / AGCWD (`Main.py:42-47, 239-248`):** un flag (`USE_ZERODCE`) que elige entre un realce por red neuronal (Zero-DCE INT8 en TFLite, para Pi 5, ~20 FPS) y el realce clásico AGCWD (para Pi 4B, ~35 FPS). En modo rescate, además, **aplica el realce caro solo 1 de cada 3 frames** (`DETECT_EVERY`) y el barato en los intermedios — una decisión de presupuesto de cómputo consciente.

**Por qué es novedoso / diferencial.**
- **Ningún equipo de referencia documenta esto.** Overengineering² y Airborne usan iluminación LED *propia* para **estabilizar** la escena (control de entrada), no un pipeline de software para **sobrevivir** a iluminación *adversa que no controlan*. Es un problema distinto: la regla 3.9 mete un destello que el robot **no puede apagar**, y la respuesta de software es original.
- **Es respuesta directa a una regla 2026** que los campeones 2024/2025 **no enfrentaron**. Por construcción, no pudieron copiarla de nadie.
- La combinación anti-flash dirigido + AGCWD + selector de realce por plataforma/frame-budget es un diseño que demuestra entendimiento real de procesamiento de imagen, no un `cv2.equalizeHist()` genérico.

**Qué tan honesto es el claim HOY.** **Medio-alto.** El código **está escrito y se ejecuta** en el path productivo (verificado en `Main.py`, no es código muerto: `enhance()` se llama en `infer_thread` L464 y el loop de línea usa las máscaras). Lo que falta es **evidencia documentada del beneficio**: no hay en `TEST_LOG.md` una comparación "detección con/sin anti-flash bajo destello". El claim defendible hoy es *"diseñamos e implementamos un pipeline adaptativo anti-destello"*, no *"que mejora la detección en X%"* (eso hay que medirlo). La auditoría de visión (`rpi-01 §0`) además advierte que la calibración de color subyacente es frágil (silver en BGR, rojo sin wrap), así que el anti-flash corre **sobre** una base que también hay que endurecer — eso no invalida la novedad del pipeline, pero conviene no presentarlo como "resuelto".

**Cómo expresarlo en el TDP / presentación (2-3 frases):**
> *"La regla 3.9 de 2026 permite LEDs blancos intermitentes en la zona de evacuación, un destello que el robot no puede controlar y que rompe tanto la detección por color como la inferencia YOLO. Diseñamos un pipeline de pre-procesamiento adaptativo de tres capas —detección y compresión selectiva de regiones sobre-expuestas (`anti_flash_preprocess`), corrección de gamma ponderada por histograma (AGCWD), y un realce conmutable entre red neuronal (Zero-DCE) y método clásico según la plataforma— que ataca el destello localmente preservando el resto de la imagen. A diferencia de los enfoques de referencia, que estabilizan la escena con iluminación propia, nuestro pipeline está pensado para sobrevivir a iluminación adversa que no controlamos."*

**Cómo blindar el claim antes de Incheon (alto ROI para el TDP):** grabar 10-20 frames con destello real (o simulado con una linterna), correr la detección con y sin `anti_flash_preprocess`, y meter la tabla comparativa en `TEST_LOG.md` + sección Software del TDP. Eso convierte N1 de "diseñamos" a "diseñamos y validamos" — que es la diferencia entre 3-4 y 5-6 en la rúbrica ("innovative solutions" + "Reliability Tests").

---

### N2 — Validación multi-modal de víctima: visión + conductividad + reflectancia (contra la regla 3.10)

**En qué consiste.** El equipo diseñó una estrategia de **fusión de tres principios físicos independientes** para decidir si una esfera plateada es una víctima viva real o una **víctima falsa** (que la regla 3.10 de 2026 permite colocar y penaliza evacuar):

1. **Visión (YOLO):** localiza y clasifica la esfera como `plateado` (cls 1) — pero la cámara **no puede** distinguir una falsa de una real (son visualmente idénticas).
2. **Conductividad eléctrica (pin 26, `INPUT_PULLUP` + 2 electrodos en la garra):** la regla 3.10.3 dice textualmente que *"living victims are electrically conductive"* y las muertas/falsas no. Al cerrar la garra, dos electrodos tocan la superficie: víctima real → cierra circuito → `LOW`; falsa → circuito abierto → `HIGH`. Confirmación física directa, inmune a todo lo óptico.
3. **Reflectancia óptica diferencial (APDS9960):** canal Clear (luminancia) + `readProximity()` (IR) para separar **blanco difuso** de **plateado especular** — el plateado rebota el IR concentrado como espejo, el blanco lo dispersa. (`cambios_de_hardware.md § LED 12V`, parte de reflectancia.)

La clave de diseño: la decisión final no descansa en un solo sensor engañable, sino en el **cruce de tres modalidades** que fallan de forma independiente. La conductividad es el árbitro definitivo que la regla misma habilita.

**Por qué es novedoso / diferencial.**
- **La mayoría de los equipos resuelve viva/muerta solo con visión** (color/reflexión), que es exactamente lo que la regla 3.10 ataca al introducir víctimas falsas visualmente idénticas. El equipo de referencia recomienda "híbrido: visión para localizar + conductividad para confirmar" (`referencia-...top.md §11.3`) como *best practice teórica* — pero **implementarla y atarla explícitamente a la regla 3.10.3 es trabajo propio**, y la fusión de **tres** modalidades (no dos) es más rica que el patrón de referencia.
- **Es respuesta directa a una regla 2026 nueva** (víctimas falsas, §3.10). Los campeones 2024/2025 no la enfrentaron.
- El razonamiento físico del documento (IR difuso vs especular, ganancia 1X para no saturar, `delta` de canales normalizados para descartar color cromático) demuestra entendimiento profundo del sensor, no un uso de catálogo.

**Qué tan honesto es el claim HOY.** **Medio — y acá hay que ser muy cuidadoso.** Esto está **diseñado y argumentado con calidad de ingeniería** en `hardware/cambios_de_hardware.md`, pero **NO está en el firmware**: `main.cpp` no define el pin 26 de conductividad, no lo lee, y `get_color()` sigue usando mínimos cuadrados sobre 3 colores RGB hardcodeados (no la lógica C/IR descrita). La auditoría de HW (`hw-02 §3.3`) confirma: *"el firmware no lee… sigue con `known_colors` hardcodeados"*. **El claim honesto es: "diseñamos un sistema de validación multi-modal de víctima y lo tenemos especificado a nivel de circuito y firmware; está en integración".** Presentarlo como "el robot rechaza víctimas falsas por conductividad" **hoy sería falso** y un juez que pida la demo lo detecta. Si el equipo lo **implementa** antes de Incheon (es barato: 1 pin + 2 cables + ~15 líneas, ver `cambios_de_hardware.md §4`), el claim pasa a ser honesto y es de los más fuertes del TDP.

**Cómo expresarlo en el TDP / presentación (2-3 frases):**
> *"La regla 3.10 de 2026 introduce víctimas falsas visualmente idénticas a las reales, que penalizan al robot que las evacúa. Como la cámara no puede distinguirlas, diseñamos una validación de tres modalidades físicas independientes: la visión YOLO localiza la esfera, un par de electrodos en la garra verifica la conductividad eléctrica que la propia regla 3.10.3 define como discriminador de víctima viva, y el canal IR del sensor APDS9960 separa la reflexión especular del plateado de la difusa del blanco. Ninguna decisión depende de un único sensor engañable: la conductividad actúa como árbitro físico definitivo."*

**Cómo blindar el claim:** **implementarlo** (no solo documentarlo) y registrar en `TEST_LOG.md` una tanda "10 víctimas reales + 5 falsas → tasa de rechazo correcto". Es el de mayor relación valor/esfuerzo de los cuatro para convertir diseño en novedad demostrable, y además resuelve un problema de puntaje real en pista.

---

### N3 — Detección de salida de evacuación por reflectancia local aislada (contra la regla 3.9)

**En qué consiste.** Un sub-caso de N1/N2 con entidad propia: el equipo decidió **mover la detección de la línea negra de salida de la cámara (RPi) a un sensor de color con iluminación propia en la Teensy** (`cambios_de_hardware.md §LED 12V`). La cámara, durante la evacuación, sufre el destello LED (regla 3.9) **y** está saturada procesando YOLO de víctimas — detectar la cinta negra de salida ahí da falsos positivos (sombra del robot, destello sobre piso blanco) y compite por cómputo. La solución: un **LED 12V dedicado** (vía el relé que ya existe) junto al APDS9960 montado abajo y **aislado de la luz ambiente**, que lee reflectancia constante y decide la salida **en la Teensy, con latencia cero, liberando la cámara**.

**Por qué es novedoso / diferencial.**
- Es una decisión de **arquitectura de percepción** original: reconocer que un sensor barato con iluminación controlada y aislada **gana** a una cámara potente bajo iluminación adversa, para una tarea binaria específica. Eso es criterio de ingeniería de sistema, no copia.
- Está **causalmente atado a la regla 3.9** y a un fallo *observado en pruebas reales* (el doc lista la tabla de falsos positivos por destello/sombra). Un TDP que narra "teníamos detección por cámara, falló por la regla 3.9, rediseñamos a sensor aislado" es exactamente el tipo de **evaluación crítica** que la rúbrica 2026 premia en "Performance Evaluation".

**Qué tan honesto es el claim HOY.** **Medio.** El **problema** está bien diagnosticado y el rediseño **argumentado y prototipado en código de ejemplo**, pero el firmware productivo todavía detecta salida vía `green_state` de la RPi (de hecho `teensy-04 R-FSM-10` reporta que la salida de evacuación **ni siquiera está completa**: el bloque `green_state==10` está comentado). El claim honesto es *"identificamos por qué la detección por cámara falla con la regla 3.9 y diseñamos una solución por reflectancia aislada"*. Si se implementa, sube a feature real.

**Cómo expresarlo en el TDP / presentación (2-3 frases):**
> *"Detectar la cinta negra de salida con la cámara falla bajo la regla 3.9 (destello LED): sombras y reflejos generan falsos positivos, y la RPi compite entre YOLO y detección de línea. Rediseñamos la detección de salida hacia un sensor de reflectancia (APDS9960) con un LED 12V dedicado, montado abajo y aislado de la luz ambiente, que decide en la Teensy con latencia cero y libera por completo la cámara para la detección de víctimas. Es un ejemplo de nuestra filosofía: para una decisión binaria crítica, un sensor simple con iluminación controlada supera a una cámara potente bajo iluminación adversa."*

**Nota de honestidad:** la auditoría de HW (`hw-02 §3.3`) matiza que el APDS9960 **no es el sensor ideal** para esto (rango IR corto, lectura lenta que bloquea el loop) y que la solución robusta v2 sería un TCRT5000/QTR. Conviene presentar N3 como "puente pragmático para Incheon con hardware ya montado", reconociendo el upgrade futuro — eso es **más** creíble, no menos.

---

### N4 — Metodología de aseguramiento de calidad asistida por IA con framing de riesgo

**En qué consiste.** El equipo (dirección Gustavo Viollaz + coach Enzo) montó un **proceso de auditoría sistemática del código asistido por IA**, materializado en cuatro *skills* versionadas en el repo (`.claude/skills/`: `rcj-rescue-reviewer` orquestador + auditores de firmware, visión y comms) que producen **findings priorizados (P0/P1/P2) con una convención propia**: cada hallazgo lleva *riesgo de NO arreglarlo* + *riesgo de SÍ arreglarlo* + *tiempo estimado* + *cómo validar en banco*, y se canaliza por issues con plantilla + `TEST_LOG.md`. Es un pipeline de QA reproducible, no una revisión ad-hoc.

**Por qué es novedoso / diferencial.**
- Es **inusual para la categoría** documentar un proceso de QA formal y asistido por IA. La rúbrica TDP 2026 **agregó "Reliability Tests and quality assurance" en 4 de las 6 secciones** (= 24 pts atados a tener QA documentado, ver `doc-01-tdp.md §1`). Un equipo que puede mostrar **un método de aseguramiento de calidad** (no solo "probamos y anduvo") ataca directo ese criterio nuevo.
- El framing "riesgo de tocar / riesgo de no tocar" es maduro: reconoce que en un robot validado en banco, **un fix puede romper más de lo que arregla** — criterio de ingeniería que pocos equipos junior explicitan.
- Se alinea con la regla 2026 de uso de IA: la IA **asiste el análisis**, no completa la tarea por el equipo (las decisiones y la validación son humanas), lo que lo mantiene del lado permitido del reglamento de herramientas.

**Qué tan honesto es el claim HOY.** **Alto como proceso, bajo como resultado.** El proceso **existe y se está usando** (estas mismas auditorías son la prueba; las skills están en el repo). Pero el **output que el jurado puntúa** —tests reales con resultados en `TEST_LOG.md`— **está vacío** (`doc-01-tdp.md §0`: el `TEST_LOG.md` se inicializó pero las 4 categorías no tienen datos, solo el ejemplo `T-000` marcado "no es real"). El claim honesto es *"tenemos una metodología de QA asistida por IA con framing de riesgo"*; **NO** *"validamos exhaustivamente el robot"* (eso es falso hoy). Además, presentar IA-en-el-proceso requiere cuidado: el reglamento exige **declarar** el uso de IA (el repo lo hace en `CONTRIBUTING.md` y los docs firman autoría IA — bien), y conviene enmarcarlo como *herramienta de coaching/QA del equipo humano*, no como "la IA programó el robot".

**Cómo expresarlo en el TDP / presentación (2-3 frases):**
> *"Adoptamos un proceso de aseguramiento de calidad asistido por IA: cuatro auditores especializados (firmware, visión, comunicación) versionados en el repositorio analizan el código y producen hallazgos priorizados, cada uno con su riesgo de corregir, riesgo de no corregir, esfuerzo y método de validación en banco. La IA asiste el análisis; las decisiones y la validación son del equipo. Esto nos permite documentar no solo qué probamos, sino el método con el que aseguramos confiabilidad rumbo al mundial."*

**Riesgo de sobre-venderlo (importante):** si el TDP presenta esto como gran innovación pero el `TEST_LOG.md` está vacío, el jurado ve la contradicción y **resta doble** (claim inflado + ausencia de evidencia). N4 solo es defendible si va acompañado de **tests reales cargados**. Es decir: N4 **depende** de ejecutar la Acción 2 de `doc-01-tdp.md` (cargar 5-10 tests reales). Sin eso, mejor mencionarlo al pasar que destacarlo.

---

## 4. Cómo combinar los 4 ángulos en un relato único (para el TDP y la presentación)

Los cuatro ángulos **no son features sueltas**: tienen un **hilo conductor** que es en sí mismo el mensaje de novedad más fuerte del equipo.

> **El relato:** *"No rediseñamos el robot estándar de Rescue Line —adoptamos la arquitectura probada por los campeones. Nuestro aporte está en haber leído el reglamento 2026 como ingenieros y resuelto los tres problemas nuevos que ese reglamento introduce y que los campeones de 2024/2025 no enfrentaron: el destello LED (3.9), las víctimas falsas (3.10) y la coordinación SuperTeam con equipos asignados en el momento (6.3). Para cada uno elegimos fusión de sensores y robustez por diseño en vez de confiar en un único sensor. Y aseguramos ese trabajo con un proceso de QA asistido por IA."*

Este relato es poderoso porque:
- Es **honesto** sobre lo estándar (no infla la arquitectura) → gana credibilidad técnica.
- Concentra la novedad donde es **genuina e incopiable** (reglas 2026) → defendible bajo preguntas.
- Demuestra **proceso de ingeniería** (leer reglas → identificar problema → diseñar solución → validar) → es justo lo que la rúbrica 2026 premia ("Requirements definition", "innovative solutions", "Performance Evaluation").

**Mención honorable que refuerza el relato (no es N5 por sí sola, pero suma):** el análisis comparativo **ESP32-BLE vs HC-05/HC-06** para el SuperTeam Challenge (`cambios_de_hardware.md §ESP32`) es una pieza de razonamiento de ingeniería **excelente**: argumenta que el broadcast BLE es la única opción viable porque los equipos se asignan en el momento (no se puede pre-compartir MAC address ni fijar roles maestro/esclavo). Es respuesta a la regla 6.3 y demuestra que el equipo piensa los problemas hasta el final. **Caveat idéntico a N2/N3: la ESP32 NO está conectada hoy** (es propuesta documentada), así que va como "diseño/plan", no como "implementado".

---

## 5. Riesgos transversales de la estrategia de novedad (lo que puede hundir los claims)

> Crítico. Estos son los modos de fallo de la *presentación*, independientes de la calidad técnica.

| # | Riesgo | Por qué importa | Mitigación |
|---|--------|-----------------|------------|
| **R1** | **Presentar diseño como implementación** (N2, N3, ESP32) | El robot real no lee conductividad, no usa reflectancia C/IR, no tiene ESP32 ni finales de carrera. Un juez que pida demo detecta la brecha. `hw-02` y `doc-01-tdp` ya la marcan como riesgo de credibilidad #1. | Usar el tiempo verbal correcto ("diseñamos / planeamos / está en integración") **o** implementar antes de Incheon (N2 es barato). Nunca "el robot hace X" si X no corre. |
| **R2** | **Vender resiliencia/auto-recuperación que no existe** | El heartbeat, handshake `0xFA`, CRC, watchdog están sin implementar o medio-implementados (`comms-01 §0`, `rpi-03 §0`). Es el claim más tentador y más falso. | NO presentar resiliencia como novedad. Si se menciona, como "trabajo en curso / plan", jamás como logro. |
| **R3** | **N4 sin tests reales cargados** | El `TEST_LOG.md` está vacío. Destacar "QA asistido por IA" con 0 tests documentados es contradicción visible. | Cargar 5-10 tests reales (Acción 2 de `doc-01-tdp`) antes de destacar N4. |
| **R4** | **Inconsistencia doc↔código en el propio TDP** | Varios docs de `docs/es/` afirman bugs ya corregidos o features aspiracionales (`power-tree` cita VNH5019/INA219 inexistentes). Si se copian al TDP, contradicen el robot. | Validar fidelidad técnica antes de volcar (issue #95, `doc-01-tdp §5 Acción 6`). |
| **R5** | **Atribuir a IA lo que debe ser del equipo** | El reglamento de herramientas (rules 2025 §14.1, sigue en 2026) penaliza herramientas no desarrolladas por el equipo que completen tareas. La IA debe enmarcarse como asistente de análisis/QA, con autoría declarada. | El repo ya declara uso de IA (`CONTRIBUTING.md`). Mantener el framing "IA asiste, equipo decide". |

---

## 6. Veredicto final (una línea por ángulo)

- **N1 (anti-destello adaptativo):** **el ángulo más sólido hoy** — está implementado y corriendo; solo falta medir el beneficio. Vendible ya como "diseñamos e implementamos", fuerte como "y validamos" tras 1 tanda de banco.
- **N2 (validación multi-modal de víctima):** **el de mayor potencial y mejor relación valor/esfuerzo** — implementar la conductividad (barato) lo convierte en el claim más fuerte del TDP y resuelve puntaje real. Hoy: diseño excelente, no embarcado.
- **N3 (salida por reflectancia aislada):** **buena historia de evaluación crítica** (regla 3.9 → fallo observado → rediseño). Hoy: diseño/prototipo, no productivo; preséntalo como puente pragmático, no como resuelto.
- **N4 (QA asistido por IA):** **proceso real, resultado pendiente** — solo destacarlo si se cargan tests reales; sin eso, mencionar al pasar.

**El mensaje en una frase para el coach:** la novedad defendible del equipo no es *tecnológica* (la tecnología es estándar) sino *de criterio de ingeniería aplicado al reglamento 2026* — y está mayormente **diseñada pero no implementada**. La acción de mayor retorno para el TDP no es inventar más novedad, sino **bajar 2-3 de estos diseños al firmware y medirlos**, convirtiendo "lo pensamos" en "lo hicimos y lo probamos". Esa es la diferencia entre un TDP que suena bien y uno que se sostiene cuando el jurado pregunta.

---

*Auditoría holística + novedad dirigida por @gviollaz, asistida por Claude Code (Opus 4.8, 1M). Solo lectura; sin cambios en `software/**` ni `hardware/**`; sin issues nuevos. Cruzada contra las auditorías hermanas del 2026-05-18 (`doc-01-tdp`, `rpi-01-vision`, `rpi-02-decision`, `rpi-03-comms-threading`, `teensy-04-rescate-fsm`, `comms-01-protocolo-integral`, `hw-02-evaluacion-critica`) y contra las referencias de equipos top (`research/...campeones`, `referencia-...top`) y el reglamento 2026 (`hardware/cambios_de_hardware.md`, `pendientes_generales.md`). Filosofía: TEMAS A ANALIZAR — cada ángulo con su riesgo de sobre-venderlo; el equipo decide qué destacar. La honestidad del claim es parte de la estrategia, no un detalle.*
