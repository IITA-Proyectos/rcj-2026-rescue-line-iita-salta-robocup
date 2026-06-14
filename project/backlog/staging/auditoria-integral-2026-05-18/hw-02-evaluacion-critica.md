# HW-02 — Evaluación Crítica de las Decisiones de Hardware

> **Auditoría Integral 2026-05-18 · Dominio: Hardware del robot**
> **Tono:** ingeniero senior. Revisión de las *decisiones de diseño* (no de bugs de código).
> **Alcance:** SOLO lectura. No se modificó nada en `software/**` ni `hardware/**`.
> **Robot:** RoboCup Junior Rescue Line — Incheon, 2026-06-30 a 07-06.
> **Objetivo de equipo:** podio + auto-recuperación 8/10.

---

## 0. Resumen ejecutivo y metodología

Esta evaluación juzga **cada elección de hardware** del robot: la arquitectura dual (Teensy 4.1 + RPi 4B), motores/encoders, set de sensores (BNO055 / APDS9960 / VL53L0X / HC‑SR04), mecanismo de pinza, chasis/tracción y power tree/batería. Para cada bloque doy: si fue **buena decisión**, sus **puntos fuertes y débiles**, el **riesgo concreto en competencia** y las **oportunidades de mejora** para futuras versiones.

**Lo más importante que encontré antes de entrar en detalle:** hay una **brecha grave entre la documentación de hardware y el hardware real**. Los documentos "de ingeniería" firmados por *"Ai Gemini"* (`hardware/electronics/power-tree/README.md`, `hardware/electronics/datasheets/README.md`, `hardware/mechanics/traction-optimization/README.md`) describen un robot con **drivers VNH5019 (30 A), regulador XL4016 (8 A) y telemetría INA219** — **ninguno de los tres existe en el robot**. El PCB real (`hardware/electronics/PCB_Main/PCB.json`) y el BOM físico (`hardware/electronics/_legacy/ELECTRONICA/Archivo_EASY_EDA/BOM EASYEDA.csv`) muestran **drivers XH‑D‑5A / XH‑5A (5 A clase L298), reguladores MP1584 y footprint de IMU MPU6050**. El firmware (`software/teensy/firmware/`) **no lee ningún INA219 ni voltaje de batería**. Esto significa que un lector que confíe en `power-tree/README.md` está auditando un robot que no existe. **Trato la documentación como aspiracional y el código + PCB.json + BOM legacy como la fuente de verdad del hardware embarcado.**

> **Nota de método (regla del equipo "TEMAS A ANALIZAR"):** cada finding se presenta con *riesgo-de-NO-tocar*, *riesgo-de-tocar* y *tiempo estimado*. Nada acá es "un bug a fixear" — son decisiones de ingeniería con trade-offs, a discutir con los alumnos (Laureano firmware, Lucio visión, Benjamín hardware/banco) y el coach Enzo. Las auditorías previas RESILIENCIA (#53/#27/#57–#119) y CORRECTITUD (#120–#128, bugs #B1–#B10) **no se repiten**; se citan cuando un tema de hardware las toca.

**Mapa de pines reconstruido del firmware** (fuente: `main.cpp` y `drivebase.cpp`), porque no existe un pinout versionado y es la base de varios findings:

| Función | Pines | Fuente |
|---|---|---|
| Motor BL (pwm/dir/enc) | 29 / 28 / 27 | `main.cpp:40` |
| Motor FL | 7 / 6 / 5 | `main.cpp:41` |
| Motor BR | 36 / 37 / 38 | `main.cpp:42` |
| Motor FR | 4 / 3 / 2 | `main.cpp:43` |
| Encoders (ISR, solo 1 canal) | 27, 5, 38, 2 — `CHANGE` | `main.cpp:743–746` |
| Servos garra (sort/left/right/lift/deposit) | 23 / 14 / 15 / 22 / 12 | `main.cpp:20–24` |
| Ultrasonidos HC‑SR04 (trig/echo) | 8/9, 11/10, 39/33 | `main.cpp:259–261` |
| ToF VL53L0X izq/der | I2C Wire2 / Wire1, **ambos addr 0x30** | `main.cpp:780–784` |
| IMU BNO055 | I2C 0x28 (Wire por defecto) | `main.cpp:38` |
| APDS9960 color | I2C (Wire por defecto) | `main.cpp:317` |
| RELAY | **pin 0** (= RX1 hardware) | `main.cpp:30` |
| BUZZER / LED_ROJO / SWITCH | 31 / 30 / 32 | `main.cpp:31–33` |
| PWM motores | `analogWriteFrequency(pin, 50000)` = **50 kHz** | `drivebase.cpp:15` |

---

## 1. Arquitectura dual: Teensy 4.1 + Raspberry Pi 4B

### Veredicto: **BUENA decisión, y es la correcta.** Coincide con el estándar de los equipos top.

**Por qué es acertada.** Separar el tiempo real (control de motores, PID, lectura de encoders por ISR, I2C de sensores críticos) del cómputo pesado y no determinista (OpenCV + YOLO) es exactamente lo que hacen los campeones (`research/completed/2026-02-23-analisis-campeones-mundiales-rescue-line.md` y `docs/es/analisis-arquitectura-robotica.md` lo documentan: Overengineering², Data Cro). La Teensy 4.1 (Cortex‑M7 @600 MHz, FPU, abundante RAM, 3 I2C HW, 8 UART HW) está **sobrada** para esta carga y nunca va a ser el cuello de botella. La RPi 4B 8 GB da margen para el modelo de visión.

**Puntos fuertes:**
- Determinismo del lazo de control aislado de los frames perdidos / GC de Python.
- La Teensy "tonta y reactiva" simplifica la lógica de bajo nivel (aunque ver punto débil 2).
- Hardware barato de reponer y con comunidad enorme (PJRC, Adafruit).

**Puntos débiles / riesgos en competencia:**
1. **Enlace serial sin integridad.** El protocolo `[255,speed,254,angle,253,green,252,silver]` es posicional y sin checksum: un solo bit corrido por EMI de motores desincroniza **todos** los comandos siguientes. Ya está cubierto por la auditoría de COMUNICACIÓN (#120 y la familia RESILIENCIA #57–#119: heartbeat/timeouts). Lo reitero acá **solo como consecuencia de la arquitectura dual**: el bus UART es el punto único de falla de toda la coordinación, y físicamente corre al lado de los motores. → Mitigación de hardware, no de software: par trenzado RX/TX + GND dedicado, ferrita, y **separar el ruteo del cable serial del de potencia** (hoy no hay garantía de eso porque no existe doc de cableado).
2. **El reparto de inteligencia es frágil.** Toda la máquina de estados de rescate vive en la Teensy (`main.cpp` 1278 líneas, un `loop()` monolítico con `while` anidados bloqueantes). La RPi solo manda `green_state`. Esto es una decisión de *software* más que de *hardware*, pero condiciona el hardware: si mañana quieren más autonomía de decisión, la Teensy ya está al límite de complejidad de código manejable, no de cómputo.
3. **RELAY en pin 0 (= RX1).** `#define RELAY 0` (`main.cpp:30`) ocupa el pin del **UART1 por hardware**. Con la arquitectura dual usando Serial5 para la RPi, perdés gratis un UART HW que podría servir para la ESP32 del SuperTeam (que el doc propone meter en Serial8/pines 34‑35). Es una mala asignación de un recurso escaso. → *Riesgo de no tocar:* ninguno funcional hoy, pero te quedás sin UART para expansión. *Riesgo de tocar:* recablear el relay a otro pin digital libre + recompilar. *Tiempo:* 30 min + prueba de banco.

**Oportunidad de mejora (futuras versiones):** considerar **RP2040/Pico o Teensy 4.0** si el presupuesto aprieta (la 4.1 está sobredimensionada salvo que usen Ethernet/SD), y mover la decisión estratégica de rescate a la RPi dejando la Teensy como puro servo-loop. Pero **para Incheon NO tocar la arquitectura** — está validada y el tiempo es escaso.

---

## 2. Motores y encoders

### Veredicto: elección de motor **razonable**; la **cadena driver + encoder + PWM tiene tres decisiones cuestionables** que cuestan torque, precisión de odometría y robustez.

**Lo que hay (fuente de verdad).** BOM (`hardware/bom/.gitkeep` está vacío; el BOM real es `hardware/electronics/_legacy/.../Lista de materiales y link de compra.md` y el README de BOM): **4× DFRobot "Brushless DC Motor with Encoder 12V 159 RPM"** (product‑1364). Drivers reales según PCB.json/BOM EASYEDA: **XH‑D‑5A / XH‑5A** (módulos H‑bridge de 5 A, clase L298/“5A”). PWM a **50 kHz** (`drivebase.cpp:15`). PID por motor con **Kp=0, Ki=22, Kd=0** (`drivebase.h:30`) — control puramente integral.

**Puntos fuertes:**
- Motor con caja reductora metálica + encoder integrado y 12 V es la categoría correcta para Rescue Line (coincide con la recomendación de campeones: DC 12V con reductora metálica).
- 159 RPM es un buen compromiso velocidad/torque para línea + rampas de 25°.
- 4WD con control diferencial (`DriveBase::steer`) es el estándar de oro.

**Puntos débiles / riesgos en competencia:**

1. **PWM a 50 kHz sobre drivers clase 5A/L298 = decisión incorrecta.** Los módulos XH‑D‑5A (puente tipo L298 o MOSFET económico) **no conmutan limpio a 50 kHz**: el L298 tiene tiempos de subida/bajada que lo vuelven ineficiente arriba de ~5–10 kHz; a 50 kHz disipás en conmutación, perdés torque efectivo y calentás el driver. Es probable que el equipo haya subido la frecuencia para silenciar el chillido audible (típico a 1–2 kHz), pero el costo es térmico y de torque justo en rampa, que es donde más lo necesitás. → *Riesgo de no tocar:* driver caliente y torque mermado en la rampa de 25° (zona de pérdida de corrida). *Riesgo de tocar:* bajar a ~16–20 kHz (inaudible pero dentro de spec) puede reintroducir un leve silbido y obliga a re-tunear sensación de velocidad. *Tiempo:* 1 línea + 1 tarde de banco midiendo temperatura del driver y torque en rampa.

2. **Encoder leído como un solo canal (sin cuadratura) → la odometría no “ve” el sentido real.** Los ISR (`main.cpp:377–380`, `attachInterrupt(...CHANGE)`) cuentan flancos de **un solo pin** por motor. La dirección del conteo se infiere del `_dir` **comandado** (`drivebase.cpp:67–83`: el signo de `pulseCount` depende de `_dir`, no de una segunda señal en cuadratura). Consecuencia: si una rueda patina, se frena por obstáculo o **gira hacia atrás arrastrada** (back-drive en rampa), el firmware sigue sumando pulsos en el sentido que *creía* ir. `runDistance()` (`main.cpp:533`) confía 100% en esto. En una bajada con slip, la distancia recorrida real ≠ contada. Esto se conecta con el bug **#B10 (encoder sin calibrar)** de la auditoría de CORRECTITUD — pero el problema es más profundo que la calibración: **es topología de sensor**, no constante. → *Riesgo de no tocar:* `runDistance` deriva en rampas/slip, depósitos y maniobras a ciegas mal posicionados (justo lo que ataca el doc de finales de carrera). *Riesgo de tocar:* cablear el 2° canal del encoder (si el motor lo expone) + reescribir `updatePulse()` para cuadratura real = cambio no trivial en lazo crítico. *Tiempo:* medio día de firmware + verificación. **No recomendado antes de Incheon**; sí para v2.

3. **PID con Kp=0, Kd=0, solo Ki=22.** Un controlador puramente integral sobre velocidad de rueda es lento para responder a perturbaciones (golpe de rampa, lomo de burro) y propenso a windup. Funciona "lo suficiente" en línea recta a velocidad media, pero no es un lazo de velocidad robusto. Esto lo cubre la auditoría de CORRECTITUD en espíritu (#B1 PID invertido en `drivebase.cpp:50`, #B5 vel 55 en curva); acá lo marco como **decisión de tuning de hardware-control**: con encoders de un canal y este PID, el "traction control por fusión encoder+IMU" que sueña `traction-optimization/README.md` **no es implementable de forma confiable hoy**. *Tiempo de mejora:* fuera de alcance pre-mundial.

4. **Sin sensado de corriente ni protección de motor.** Los drivers XH‑D‑5A no exponen current-sense usable y el firmware no lo lee. Un motor trabado contra una pared (caso real en alineación de depósito, `main.cpp:1230–1267`) consume corriente de rotor bloqueado sin que nadie lo detecte → riesgo de quemar driver/motor o disparar protección térmica del módulo en plena corrida. → *Riesgo de no tocar:* humo en la pista. *Mitigación barata:* límite de tiempo en los `while` de empuje contra pared (también lo pide RESILIENCIA con timeouts; recordar que `cead75e` **revirtió** unos timeouts — revisar que estos `while` de rescate tengan corte).

**Oportunidad de mejora (v2):** drivers decentes (TB6612FNG para esta corriente, o DRV8871/BTS7960 si quieren margen) con PWM en spec; encoders en cuadratura reales; lazo PID completo (P+I, con anti-windup). El power-tree doc *menciona* VNH5019 — sería un buen driver, pero **hoy no está montado**: cerrar esa brecha doc↔realidad es parte del trabajo.

---

## 3. Set de sensores

### Veredicto: **el set es bueno y bien pensado**, con redundancia inteligente (ToF + ultrasonido) y la IMU correcta. Hay fragilidades de implementación I2C y de elección del sensor de color.

### 3.1 IMU — BNO055 → **excelente decisión**
- **Fuerte:** el BNO055 hace fusión sensorial **interna** (devuelve orientación absoluta por hardware), lo que descarga a la Teensy y da yaw estable para giros (`runAngle`) y pitch para rampas (`ajustarVelocidadPorPendiente`, `main.cpp:628`). Es literalmente el sensor que usan los campeones. Buen upgrade respecto del MPU6050 que figura en el footprint del PCB legacy (la doc de BOM lo justifica).
- **Débil / riesgo:** (a) es **sensible a EMI magnético de los motores**; el propio `power-tree/README.md` pide capacitores de 0.1 µF en motores para protegerlo — **no hay evidencia de que estén montados** y no hay forma de verificarlo desde el repo (asumo que NO, salvo confirmación de Benjamín). Un BNO055 cerca de motores ruidosos da yaw con deriva → giros de 90°/180° imprecisos (relacionado con #B4 *leer_yaw no asigna la global* y #B8 *runAngle180* de CORRECTITUD). (b) Está en el bus I2C `Wire` por defecto **compartido con el APDS9960** — si el color sensor cuelga el bus, te quedás sin IMU. (c) Depende de `event.orientation.x/y` (modo NDOF) que necesita calibración de arranque; no veo rutina de verificación de `calibration status` antes de competir.
- **Mejora:** montar los capacitores cerámicos ya, ubicar el BNO055 en el centro geométrico (lo pide `traction-optimization/README.md` punto 5.2), y agregar un check de `getCalibration()` en el arranque que no deje correr hasta tener sys/gyro calibrados. *Tiempo:* capacitores 1h de soldadura (P1, alto ROI); check de calibración 1h de firmware.

### 3.2 Distancia — 2× VL53L0X (ToF) + 3× HC‑SR04 (ultrasonido) → **buena redundancia, implementación I2C frágil**
- **Fuerte:** migrar a ToF láser para las paredes laterales (precisión mm, inmune a ruido acústico) y dejar ultrasonido para frente/laterales de obstáculo es exactamente la tendencia ganadora. Tener ambos da redundancia: el ToF para `avance_recto` de pared (`main.cpp:672`) y los HC‑SR04 para detección de obstáculo y navegación a ciegas en rescate.
- **Débil / riesgo CRÍTICO de implementación:** los **dos VL53L0X se configuran con la MISMA dirección 0x30** (`main.cpp:783‑784`) y solo no chocan porque están en **buses I2C físicos distintos** (Wire1/Wire2, `main.cpp:780‑781`). Esto *funciona* pero es **frágil y caro en pines**: gasta dos periféricos I2C HW para evitar el procedimiento estándar (XSHUT para re-direccionar en un solo bus). Si alguien recablea ambos al mismo bus "para simplificar", colisión inmediata y silenciosa. Además **no hay re-init en caliente**: si un ToF cuelga (cubierto por #B? RESILIENCIA y los timeouts de `setTimeout(500)`), `leer_tof()` devuelve basura sin recuperación. → *Riesgo de no tocar:* funciona si nadie toca el cableado; pero un ToF colgado en rescate = navegación a ciegas mal. *Mejora v2:* esquema XSHUT + direcciones únicas en un solo bus, liberando un I2C.
- **Débil — ultrasonido en zona de evacuación:** la estrategia de rescate (`main.cpp:1222‑1267`) navega "a ciegas" con los 3 HC‑SR04 contra las paredes. Los HC‑SR04 tienen cono ancho (~15°), zona muerta (~2 cm) y rebotan mal en esquinas/paredes oblicuas. Para alinear el depósito esto es marginal — y es **justamente** por qué el doc propone los **finales de carrera** (sección 4 de `cambios_de_hardware.md`). **Coincido fuertemente con esa mejora:** un microswitch da contacto físico binario, inmune a todo lo que confunde al ultrasonido. Es la mejora de hardware de mayor relación valor/esfuerzo de todo el documento para el objetivo "depósito consistente".

### 3.3 Color / línea de salida — APDS9960 → **el eslabón más débil del set; la solución propuesta es correcta pero el sensor es inadecuado para "plateado"**
- **Contexto:** el APDS9960 (`main.cpp:317`, `get_color()`) se usa hoy para clasificar Negro/Rojo/Verde por mínimos cuadrados sobre RGB+C contra 3 colores hardcodeados (`known_colors`, `main.cpp:324‑329`). El doc `cambios_de_hardware.md` (sección LED 12V) propone usarlo además como **sensor de reflectancia** (canal Clear + IR de proximidad) para detectar la línea negra de salida y diferenciar blanco/plateado, agregando un LED 12V por relé.
- **Fuerte:** la lógica del doc es **buena ingeniería** — aislar el sensor abajo, iluminación constante con LED, usar canal C como luminancia y `readProximity()` (IR especular vs difuso) para separar plateado de blanco, bajar la ganancia a 1X para no saturar. Mueve la detección de salida de la RPi (que sufre la linterna intermitente del reglamento 3.9) a la Teensy con cero latencia. **Apruebo el enfoque.**
- **Débil / riesgo:** (a) el APDS9960 **no es un sensor de reflectancia de línea**; su rango de proximidad IR es de pocos cm y su lectura de color es lenta (`while(!apds.colorDataReady()) delay(5)` en `get_color()` **bloquea el loop** hasta 5 ms+ por lectura — ya tocado por RESILIENCIA). Para detectar plateado/blanco de víctimas reglamentarias, su separabilidad es marginal y muy dependiente de distancia al piso y de la ganancia exacta. (b) Los `known_colors` están **hardcodeados a una iluminación** — bajo otra luz de cancha, la clasificación Negro/Verde/Rojo se degrada (esto enlaza con #B2 *silver_mask en BGR* y #B9 *rojo sin wrap* de visión: el sistema tiene **doble** detección de color frágil, una en RPi y otra en Teensy). (c) Depende de un **relé** (pin RELAY=0) que a su vez pisa el UART1 (ver §1).
- **Mejora prioritaria (alineada con el doc):** para el caso **línea negra de salida**, lo correcto sería un **sensor de reflectancia IR dedicado** (TCRT5000 o un array QTR como usan los campeones, `research/...campeones`) en vez de forzar el APDS9960. El LED 12V + APDS sirve como puente para Incheon, pero la solución robusta de v2 es QTR/TCRT. La **conductividad para víctimas plateadas falsas** (sección 5 del doc, pin 26 INPUT_PULLUP + 2 electrodos) es, en cambio, una idea **muy buena y barata** que ataca directo el reglamento 3.10.3 ("living victims are electrically conductive"): la apruebo, con la salvedad de fatiga de cable que el propio doc ya identifica bien (usar jumper multifilar/siliconado AWG28, alivio de tensión).

### 3.4 Cámara — USB Wide 140°
- **Fuerte:** FOV ancho ve ambos cuadrados verdes y la línea cerca. USB plug-and-play en la RPi.
- **Débil:** lente 140° introduce **distorsión de barril** fuerte en bordes → la línea recta se curva en el frame y las ROIs de verde se deforman (impacta visión, fuera de este dominio pero lo dejo señalado para el auditor de RPi). Sin shutter global, hay motion blur en movimiento rápido.

---

## 4. Mecanismo de pinza (claw, 5 servos)

### Veredicto: **mecanismo ambicioso y funcional, pero sobre-actuado y con servos sub-especificados para uso como contrapeso.**

**Lo que hay.** 5× DFRobot "2 kg·cm 300° Clutch Servo" (product‑2126) controlando: `lift`, `left`, `right` (mordaza), `sort` y `deposit` (`main.cpp:20‑25`, `claw.cpp`). Secuencias de recolección/depósito por FSM no bloqueante (`claw.cpp` `update()` y la máquina `RESCATE_*` en `main.cpp:86‑254`).

**Puntos fuertes:**
- **5 GDL** permiten recoger, **clasificar** víctima viva/muerta (sort left/right) y **depositar** en el triángulo correcto (deposit left/center/right) — cumple el reglamento de separar vivas/muertas. Es más capaz que muchas pinzas de un solo servo.
- La migración a FSM no bloqueante (`claw.update()`, máquina `RESCATE_*`) es la decisión de software correcta y ya está hecha (descarga el `delay()` que congelaba el PID — alineado con RESILIENCIA).
- Servo "clutch" (embrague) protege el tren de engranajes ante bloqueo, acertado para una pinza que choca contra el piso/víctimas.

**Puntos débiles / riesgos en competencia:**
1. **Torque 2 kg·cm es bajo** para los roles que se le piden. Si el equipo pretende además usar la garra como **contrapeso dinámico en rampa** (lo sugiere `traction-optimization/README.md` 2.1: "garra adelante-abajo en subida"), 2 kg·cm no mueve masa significativa de forma confiable. Y bajo carga (víctima + brazo extendido) el servo de `lift` trabaja cerca de su límite → jitter, calentamiento, y consumo que castiga el riel de 6 V (ver §6). → *Riesgo:* pinza que no levanta confiable a fin de batería. *Mejora:* servo de `lift` de mayor torque (≥10–15 kg·cm metal-gear) en v2.
2. **5 servos = 5 puntos de falla mecánicos** y mucho consumo concurrente. Las secuencias usan `delay(1000)`/`nonBlockingDelay(1000)` generosos (`main.cpp:1141‑1186`) — **gastan tiempo de corrida** (cada víctima son ~6–8 s de coreografía). Con bug **#B6 (salida anticipada del cuarto)** de CORRECTITUD ya señalado, la secuencia es además sensible a timing. → *Mejora:* reducir GDL si es posible (¿`sort` y `deposit` pueden fusionarse?), y recortar delays con verificación de posición.
3. **Sin realimentación de posición/cierre.** La garra cierra a ciegas (`close()` = ángulos fijos 210/85, `claw.cpp:66`). No sabe si **agarró** la víctima. El pin de conductividad propuesto (§3.3) ayuda a saber si es real, pero no si está bien sujeta. → riesgo de soltar víctima en el traslado.
4. **Cableado de servos hacia una garra que sube/baja** = fatiga (el doc lo reconoce para el cable de conductividad; aplica **igual** a los 5 cables de servo del brazo `lift`). No veo gestión de cadena de cables.

**Oportunidad de mejora (v2):** repensar si 5 servos son necesarios o si un diseño de 3 GDL con mejor torque y un mecanismo pasivo de clasificación logra lo mismo con menos masa, menos consumo y menos puntos de falla. Para Incheon: **no rediseñar**, sí poner un servo de lift más fuerte si el presupuesto/tiempo lo permite y validar consumo pico contra el regulador de servos.

---

## 5. Chasis y tracción

### Veredicto: **configuración de tracción inusual (2 omni + 2 fijas) que merece justificación; sin suspensión, lo cual es el mayor riesgo mecánico para rampas/lomos.**

**Lo que hay (BOM).** 2× **Omniwheel 58 mm** + 2× **ruedas fijas** (Pololu 1420). 4WD skid-steer por software (`DriveBase`). Chasis impreso en 3D (múltiples STL en `hardware/mechanical/_legacy/CAD/STLS/`: base, soportes de motor, carcasa RPi, cajón de servos, aletas, "obstruye pelotas"). CG con batería montada vía `agarra_bateria.stl`.

**Puntos fuertes:**
- 4WD da tracción; el chasis 3D es totalmente iterable (ventaja para v2).
- Las omni **podrían** dar corrección lateral en rampas transversales (si están bien ubicadas).

**Puntos débiles / riesgos en competencia:**
1. **Mezcla 2 omni + 2 fijas: decisión que no veo justificada y que es riesgosa.** Un skid-steer 4WD normalmente usa 4 ruedas iguales (todas con tracción/agarre). Mezclar 2 omni (que **patinan lateralmente por diseño**) con 2 fijas crea un comportamiento de giro asimétrico y **reduce el agarre efectivo**: las omni tienen menos µ longitudinal que una rueda de goma maciza, justo lo que necesitás en rampa de 25°. Si las omni están atrás, el tren trasero patina en subida; si están adelante, perdés dirección. El documento de tracción (`traction-optimization/README.md`) recomienda **lo contrario**: ruedas de silicona blanda (Shore 10‑20A) para máximo agarre. Hay **contradicción entre el doc y el BOM**. → *Riesgo de no tocar:* slip en rampa = no superar el 100% de pista (objetivo declarado P1 del doc). → *Mejora:* evaluar pasar a 4 ruedas iguales con neumático de silicona blanda; si las omni son para algo específico (estrategia de giro), **documentarlo**.
2. **Sin suspensión ni array flotante.** Los campeones montan los sensores de línea (y a veces los ejes) en **paralelogramo deformable / rocker** para mantener contacto en lomos de burro (`research/...campeones` 1.2; `traction-optimization/README.md` 3). Este robot es **chasis rígido**: en un lomo de burro o entrada de rampa, una rueda se levanta → pierde 25% de tracción y el control diferencial se vuelve errático (lo dice el propio doc). Para un robot **basado en cámara** (no en array de línea al ras), levantar una rueda además descuadra el frame. → *Riesgo:* pérdida de línea / vuelco en transiciones. *Mejora v2:* chasis con flex controlado (placa fina) o rocker pasivo; bajar el CG (batería lo más abajo posible — verificar `agarra_bateria.stl`).
3. **CG y vuelco en 25°.** No hay datos de masa ni de altura de CG en el repo (no hay TDP mecánico). Con RPi + 5 servos + garra pesada arriba, el CG es probablemente alto → riesgo de "caballito" en subida y vuelco frontal en bajada. El doc propone contrapeso activo con la garra, pero los servos de 2 kg·cm no alcanzan (§4). → *Supuesto:* asumo CG alto por falta de datos; **verificar con Benjamín** pesando el robot y midiendo el ángulo de vuelco estático en banco antes de viajar.
4. **Despeje (ground clearance) y la garra.** La garra baja al piso para recoger; si cuelga mucho, engancha en lomos/bordes. No hay cota de despeje documentada.

**Oportunidad de mejora (v2):** moldes de silicona para neumáticos (el doc ya investigó Dragon Skin/VytaFlex), suspensión pasiva, y un **CAD vivo** (hoy el único `.f3d` está en `_legacy` — `Rescue3D.f3d` — y los STL son de la versión anterior; **no hay CAD versionado de la versión actual de competencia**, lo cual es deuda de documentación seria para un robot iterable).

---

## 6. Power tree y batería

### Veredicto: **el diseño documentado es sólido en teoría pero NO es el que está montado; el power tree real (MP1584 + drivers 5A, sin telemetría) es marginal y es el riesgo de hardware #1 para "robot que no se reinicia".**

**Brecha doc ↔ realidad (crítico).**

| Componente | `power-tree/README.md` (doc "Ai Gemini") | Hardware REAL (PCB.json + BOM EASYEDA + código) |
|---|---|---|
| Driver motores | VNH5019, 30 A, current-sense | **XH‑D‑5A / XH‑5A (~5 A, sin sense)** |
| Regulador RPi | XL4016, 8 A, ajustar 5.1 V | **MP1584** (módulo 3 A nominal) |
| Regulador Teensy/sensores | XL4015, 5 A | **MP1584 5 V** |
| Regulador servos | LM2596, 6 V/3 A | **MP1584 6 V** |
| Telemetría batería | INA219 I2C, corte <9.9 V | **NO existe** (el firmware no lee corriente/voltaje) |
| Batería | "LiPo 3S 35C, >3000 mAh" (doc tracción dice 35C) | BOM dice **2200 mAh 30‑60C**; legacy decía **1500 mAh 80C** |

**Puntos fuertes (del diseño documentado, si se implementara):**
- La **filosofía es correcta**: star-ground único, separación de riel "sucio" (motores) y "limpio" (RPi/lógica), capacitores de filtrado en motores, cable ≥20 AWG a la RPi, regulador dedicado a la RPi para evitar el "rayo amarillo" de under-voltage. Todo esto es exactamente lo que separa a los equipos que terminan corridas de los que se reinician. **Como guía de construcción, el doc es bueno.**

**Puntos débiles / riesgos en competencia (del hardware REAL):**
1. **MP1584 para alimentar una RPi 4B = sub-dimensionado y peligroso.** El MP1584 es un módulo de **3 A nominales** (y se calienta mucho cerca de eso). Una RPi 4B pide picos de **>1.2 A a 5 V solo la placa**, y el oficial recomienda fuente de **3 A**; sumá picos de arranque de YOLO + cámara USB. El MP1584 va a estar **al límite o por encima**, lo que produce caídas de tensión → **under-voltage throttling o reinicio de la RPi en plena corrida**. Esto es probablemente la causa raíz de cuelgues si los hubo (cruza con RESILIENCIA #57–#119: crashes/recuperación). El doc lo sabe (por eso pide XL4016 8 A) — **pero el XL4016 no está montado.** → *Riesgo de no tocar:* RPi se reinicia en la peor corrida = corrida perdida + objetivo de auto-recuperación 8/10 comprometido. → *Mitigación prioritaria:* **montar realmente un buck de ≥5 A (XL4016/equivalente) para la RPi**, ajustado a 5.1 V, con 20 AWG. Es, en mi opinión, **la mejora de hardware más importante de todas para el objetivo del equipo.** *Tiempo:* 2‑3 h (comprar/montar/medir bajo carga con `vcgencmd get_throttled` en la RPi).
2. **Cero telemetría de batería.** El firmware **no lee INA219** (confirmado: `grep` sin resultados). No hay corte por bajo voltaje. Una LiPo 3S descargada por debajo de 3.3 V/celda se **daña permanentemente** y, peor, a batería baja el voltaje cae bajo carga → motores con menos torque + RPi con under-voltage **justo al final de la corrida**. → *Riesgo:* batería arruinada (costo) y degradación de performance no observada. → *Mejora:* o bien montar el INA219 que el doc pide y leerlo en la Teensy para buzzear/cortar a <9.9 V (cruza con la idea de heartbeat), o como mínimo un **alarma de LiPo** (buzzer de celda) de 2 USD enchufado al balance — solución de campo barata para Incheon. *Tiempo:* alarma 5 min; INA219 + firmware medio día.
3. **Capacitores de filtrado en motores: probablemente ausentes.** El doc los pide (0.1 µF polo-polo y polo-carcasa) explícitamente para proteger el BNO055 del EMI. No hay forma de confirmar desde el repo que estén montados. Si faltan, explica deriva de IMU en giros (§3.1). → *Mejora P1, altísimo ROI:* soldar los capacitores. *Tiempo:* 1 h.
4. **Batería 2200 mAh: justa en energía.** Para una corrida de Rescue Line con 4 motores + RPi (~5‑8 W) + 5 servos, 2200 mAh 3S (~24 Wh) alcanza para una corrida pero deja **poco margen** para tandas de prueba en boxes y para mantener voltaje alto al final. Los campeones usan **>3000 mAh** (el propio doc lo dice). El alto C-rating (30‑60C) es correcto para los picos de arranque de motor; el problema es la **capacidad**, no el C. → *Mejora:* batería de mayor capacidad (≥3000 mAh) y **tener 2‑3 baterías cargadas** rotando en competencia. *Tiempo:* compra.
5. **Sin fusible verificable.** El doc pide "Switch + Fusible 15 A"; el BOM EASYEDA solo muestra switches (DPDT 6‑pin, slide on/off), **no veo fusible**. Una LiPo 3S 30‑60C puede entregar **decenas de A** en cortocircuito → riesgo de incendio si hay un corto en la pista. → *Mejora P0 de seguridad:* fusible/PTC inline en el positivo de batería. *Tiempo:* 30 min.

**Oportunidad de mejora (v2):** implementar el power tree **tal como está documentado** (es bueno): buck dedicado de ≥5 A para RPi, INA219 con corte, star-ground real, capacitores. Y **reconciliar la documentación con la realidad** — hoy el `power-tree/README.md` es activamente engañoso para cualquiera que lo lea como spec.

---

## 7. Priorización para Incheon (acciones de hardware, no rediseños)

Ordenadas por relación valor/riesgo/tiempo. Todas son **temas a discutir** con riesgo-de-tocar incluido, no órdenes.

| # | Tema (hardware) | Riesgo de NO tocar | Riesgo de tocar | Tiempo | Prioridad |
|---|---|---|---|---|---|
| 1 | **Buck ≥5 A real para la RPi** (reemplazar MP1584) | RPi se reinicia en corrida; falla auto-recuperación | Recablear riel 5 V, ajustar 5.1 V | 2‑3 h | **P0** |
| 2 | **Fusible/PTC en + de batería** | Incendio ante corto de LiPo | Trivial | 30 min | **P0 seguridad** |
| 3 | **Alarma/corte de LiPo baja** (buzzer balance o INA219) | Batería arruinada; torque/voltaje caen al final | Alarma: nulo | 5 min–medio día | **P1** |
| 4 | **Capacitores de filtro en motores** | Deriva de IMU en giros (#B4/#B8) | Nulo | 1 h | **P1 (alto ROI)** |
| 5 | **Finales de carrera para depósito** (doc §4) | Depósito impreciso, víctimas mal soltadas | Desarmar + soporte 3D | 1 día | **P1** |
| 6 | **Bajar PWM motores a ~16‑20 kHz** | Driver caliente, torque mermado en rampa | Reintroduce leve silbido; re-tune | 1 línea + 1 banco | **P1/P2** |
| 7 | **Pin conductividad víctimas falsas** (doc §5) | Pierde tiempo con víctimas falsas | Cable a fatiga (mitigable) | medio día | **P2** |
| 8 | **Validar CG / ángulo de vuelco estático** en banco | Vuelco en 25° | Solo medición | 1 h | **P1 (medición)** |
| 9 | **Confirmar ruteo serial separado de potencia** | EMI desincroniza UART | Recableo si está mal | variable | **P1** |

**Para v2 (post-Incheon, robot iterable):** drivers en spec (TB6612/VNH5019) + encoders en cuadratura + PID completo; tracción de 4 ruedas iguales de silicona blanda + suspensión pasiva; sensor de reflectancia dedicado (QTR/TCRT) para línea; garra de menos GDL con más torque; CAD y pinout **versionados** de la versión real; e **implementar el power tree documentado**.

---

## 8. Supuestos e inferencias (marcados)

- **Asumo que los capacitores de filtro de motor y el INA219 NO están montados**, porque el firmware no los referencia y el BOM real no los lista. Confirmar con Benjamín (hardware/banco).
- **Asumo drivers XH‑D‑5A = clase L298/"5A"** por el designador del BOM EASYEDA; no hay datasheet en `hardware/electronics/datasheets/` (solo un README que describe componentes que no están montados).
- **Asumo CG alto** por composición (RPi+garra arriba) ante ausencia de datos de masa/CG en el repo (no hay TDP mecánico).
- **Asumo que el CAD de competencia actual no está versionado**: el único `.f3d` y los STL viven en `hardware/mechanical/_legacy/CAD/` y corresponden a una versión previa.
- La **batería real** es ambigua: BOM README dice 2200 mAh 30‑60C; el README de datasheets dice 35C; el legacy decía 1500 mAh 80C. Tomé 2200 mAh 3S como la más reciente. Confirmar cuál viaja a Incheon.
- No pude inspeccionar `PCB.json` completo (580 KB, supera el límite de lectura); extraje los IC por búsqueda dirigida (XH‑D‑5A ×22, MP1584 ×10, VL53L0X ×14, JSN/HC‑SR04, MPU6050 ×5). El `pcb-preview.pdf` y `ROBOCUP.SHEET.pdf` no se renderizaron en esta auditoría.

---

## 9. Conclusión

**Las decisiones de arquitectura son acertadas y maduras**: la dual Teensy 4.1 + RPi 4B, la IMU BNO055, la redundancia ToF + ultrasonido y la migración a visión con YOLO son exactamente lo que hacen los equipos top, y el equipo claramente investigó bien (los docs de campeones y tracción lo demuestran). **La debilidad no está en *qué* eligieron sino en la *implementación de potencia y mecánica* y en la brecha entre la documentación aspiracional y el hardware embarcado.**

Los tres riesgos de hardware que más pueden costar una corrida en Incheon son, en orden: **(1) la alimentación de la RPi por un MP1584 sub-dimensionado** (reinicios → mata el objetivo de auto-recuperación), **(2) la ausencia total de telemetría/protección de batería y fusible** (seguridad + degradación al final), y **(3) la tracción mixta omni+fija sin suspensión** (slip/vuelco en la rampa de 25°). Las mejoras del propio `cambios_de_hardware.md` (finales de carrera, conductividad, LED 12V) son **buena ingeniería y las apruebo**, pero **ninguna importa si la RPi se reinicia por falta de corriente**. La prioridad de hardware antes de viajar es **el riel de 5 V y la seguridad de la batería**, no las features nuevas.

Finalmente, una recomendación de proceso: **reconciliar la carpeta `hardware/` con la realidad**. Hoy un alumno (o un juez en el TDP) que lea `power-tree/README.md` cree que el robot tiene VNH5019 + XL4016 + INA219. No los tiene. Para un robot que va a un mundial y que el equipo quiere hacer iterable, **el pinout, el CAD actual y el power tree real deben estar versionados y ser verdaderos** — esa es la base sobre la que se construye la v2 con Virginia rumbo a 2027.
