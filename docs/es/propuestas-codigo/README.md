# Índice de propuestas de código — RCJ Rescue Line 2026 (IITA Salta)

> **⚠️ ESTO ES CÓDIGO PROPUESTO, NO COMMITEADO AL ROBOT.**
> Todo lo que se enlaza desde acá es **código de ejemplo / borrador** que un coach técnico preparó para que el equipo lo **revise, adapte a su hardware real, pruebe en banco y recién después commitee**. Nada de esto está mergeado en `main` ni corre hoy en el robot. **Cada alumno hace su propio PR** de lo que le corresponde.

---

## Cómo se usa este índice

Este documento es el **mapa navegable** de todas las propuestas de código que se escribieron durante la auditoría integral del repo. Antes no había índice: los snippets estaban dispersos en archivos sueltos dentro de `project/backlog/staging/`. Acá los juntamos por **persona / subsistema**, con qué propone cada uno, qué issues cubre y el link directo al archivo fuente.

**Regla de oro (vale para TODOS los items):**

1. El código de las propuestas **no se pushea tal cual**. Es un punto de partida.
2. Quien tiene el robot/Pi en frente **lo adapta** a la realidad del hardware (rutas, pines, parámetros, versiones).
3. Se **prueba en banco** y el resultado se documenta en [`testing/TEST_LOG.md`](../../../testing/TEST_LOG.md) (regla de oro del repo: sin entrada en el TEST_LOG, no se mergea).
4. **Cada alumno abre su propio PR**, un issue por PR, en español, con `Closes #NNN`.

> **📅 Sobre las fechas de los documentos enlazados:** los `programa-*.md` y los reportes de auditoría fueron escritos el **2026-05-18**. Las fechas de sprint/gate que aparecen adentro (p. ej. "gate 26-may", "freeze 20-may", "push libre hasta 11-jun", "faltan 6 semanas") **están superadas**. El régimen de fases vigente y el estado real del proyecto al día de hoy viven en **[`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../ESTADO-ACTUAL-2026-05-31.md)** (y el informe director, en [`docs/es/2026-05-31-informe-coach-auditoria-integral.md`](../2026-05-31-informe-coach-auditoria-integral.md)). Tomá las propuestas de código como válidas (el código no caduca), pero **ignorá las fechas internas** y guiate por el estado del 31-may.

---

## ⚠️ Corrección importante antes de aplicar nada: el PID (#121 / B1)

Hay un "fix" que circuló como quick-win y **es incorrecto**. Que quede MUY claro antes de que alguien lo aplique:

- El supuesto fix de **cambiar el signo del PWM** (poner `analogWrite(_pwmVal)` en lugar de `analogWrite(255 - _pwmVal)`) **NO es correcto**.
- Los motores son **DFRobot FIT0441 con PWM invertido a nivel hardware**: `255 - _pwmVal` es lo correcto físicamente. Cambiarlo "para que el signo dé bien" rompe el control de motor.
- El problema real del PID **no es el signo**: es el **lazo** (modo `DIRECT` + `ki=22` dominante + `kp=0`) que queda **saturado**. Es un **rediseño de lazo de control**, no un quick-win de una línea.
- La fuente de verdad de este análisis es **[`teensy-01-drivebase-pid.md` → finding T-01](../../../project/backlog/staging/auditoria-integral-2026-05-18/teensy-01-drivebase-pid.md)**. Ese archivo ya lo explica bien — leerlo antes de tocar el PID.

**No apliquen el cambio de signo del PWM. Tratar el PID como rediseño, con banco.**

---

## 1. Laureano Monteros (`@Laumonteros`) — Firmware Teensy 4.1 (C++)

**Fuente primaria de código (snippets C++ COMPLETOS, listos para revisar y adaptar):**
👉 **[`programa-laureano-teensy-resiliencia.md`](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md)** (el más grande del lote, ~36 KB)

Propone resiliencia para el firmware: timeouts en loops bloqueantes, señalización visible de fallos, heartbeat/failsafe serial, watchdog de hardware, salud de sensores en runtime y arreglos de encoders. Está organizado en 3 sprints (los nombres "Sprint 1/2/3" y sus fechas internas están superados — ver banner de fechas arriba).

| Issue | Qué propone | Archivo fuente |
|-------|-------------|----------------|
| **#60** | Timeout en `runDistance()` para salir si el encoder no cuenta + nuevo archivo `priority_fix_flags.h` (feature flags de compilación) | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |
| **#61** | Timeout en `get_color()` (`while (!apds.colorDataReady())`) para no colgarse si el APDS9960 no responde | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |
| **#62** | Alerta **visible** (LED rojo + buzzer) en `setup()` si el BNO055 o el APDS fallan al iniciar | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |
| **#112** | Timeout + **dreno de Serial5** en `runAngle()` (este fix nunca existió antes; se escribe por primera vez) | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) · draft: [draft-issue-resi-runangle-timeout](../../../project/backlog/staging/draft-issue-resi-runangle-timeout.md) |
| **#53** | Heartbeat serial (byte `0xF0` cada ~200 ms) + failsafe `speed=0` si la RPi se cuelga | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |
| **#27** | Watchdog de hardware `WDT_T4` (WDOG1) + callback que para motores antes del reset | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |
| **#109** | Salud del BNO055 en runtime: detectar heading congelado + `resetear_bno()` con timeout | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) · draft: [draft-issue-resi-bno-runtime](../../../project/backlog/staging/draft-issue-resi-bno-runtime.md) |
| **#72** | Resync del protocolo serial post-reset (esperar el sync byte 255 antes de procesar datos) | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |
| **#67** | Encoders: init de `pulseCount`/`_dir`, lectura atómica (`noInterrupts()`), `_dir` a `volatile` | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |
| **#59** | Timeout de rescate: salir de la zona de evacuación si tarda demasiado (valor a tunear en banco) | [programa-laureano](../../../project/backlog/staging/programa-laureano-teensy-resiliencia.md) |

> **Nota Laureano:** empezá por `priority_fix_flags.h` (es prerequisito de #60/#61/#62/#112). Los flags arrancan en `true` en la propuesta, pero validás de a uno en banco. Un PR por issue, no todo junto.

### Reportes de auditoría que respaldan estos fixes (excerpts del código actual + análisis)

Estos son los informes de auditoría del firmware. Tienen **excerpts del código que hoy está en el robot** + el razonamiento del fix. Sirven para entender *por qué* se propone cada cambio.

| Reporte | Subsistema Teensy | Findings | Link |
|---------|-------------------|----------|------|
| **teensy-01** | Drivebase + PID (control de motores) | T-01 … T-11 (PID saturado #121/B1, SampleTime, `kp=0`/`ki=22`, calibración 25 pulsos/cm #126/B10, init encoders #67) | [teensy-01-drivebase-pid.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/teensy-01-drivebase-pid.md) |
| **teensy-02** | Sensores (BNO055 / APDS9960 / VL53L0X / NewPing) | S-01 … S-10 (revert de defensas en `cead75e`, #61/#62/#109/B4, ToF basura, color hardcodeado) | [teensy-02-sensores.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/teensy-02-sensores.md) |
| **teensy-03** | FSM de **línea** (navegación) | F-01 … F-11 (velocidad 55 en curva #122/B5, `runAngle(180)`, case 12 fall-through, esquiva sin seed, `taskDone`, cooldown verde #125/B8, #58) | [teensy-03-linea-fsm.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/teensy-03-linea-fsm.md) |
| **teensy-04** | FSM de **rescate** (claw / depósito) | R-FSM-01 … R-FSM-10 (#57 ramas -90, `ball_counter`/`veces_deposit` init, #123/B6, #125/B8, #120/B4, #112, #60) | [teensy-04-rescate-fsm.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/teensy-04-rescate-fsm.md) |
| **teensy-05** | Serial (lado C++ del protocolo) | 2.1 … 2.9 (handshake 0xFA a medias #72, `green_state` sticky re-dispara rescate, frames stale, desync #63/#70) | [teensy-05-serial-teensy.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/teensy-05-serial-teensy.md) |

> Los timeouts de #61/#62 también vivieron completos en git (commit `cead75e`, después revertido). Los reportes teensy-02/03/04 cruzan con `programa-laureano` — usá ambos.

---

## 2. Lucio Saucedo (`@luciouriel2011`) — Visión RPi 4B (Python / OpenCV / TFLite)

**Fuente primaria de código (snippets Python COMPLETOS + test scripts):**
👉 **[`programa-lucio-rpi-vision.md`](../../../project/backlog/staging/programa-lucio-rpi-vision.md)**

Propone arreglos de robustez para el pipeline de visión: guard headless, init defensivo contra crash, threading seguro en la cámara y manejo de errores en el hilo de inferencia. Todos son cambios chicos (< 20 líneas cada uno), se escriben sin el robot; el banco hace falta sólo para la validación final.

| Issue | Qué propone | Archivo fuente |
|-------|-------------|----------------|
| **#64** | Guard `HEADLESS` en `calibration.py` (los `cv2.imshow` crashean en la Pi sin pantalla) | [programa-lucio](../../../project/backlog/staging/programa-lucio-rpi-vision.md) |
| **#110** | Inicializar `cx_black = width // 2` para evitar crash 100% reproducible en zona verde sin línea negra | [programa-lucio](../../../project/backlog/staging/programa-lucio-rpi-vision.md) · draft: [draft-issue-resi-cx-black-crash](../../../project/backlog/staging/draft-issue-resi-cx-black-crash.md) |
| **#65 + #113** *(unificados)* | `threading.Lock` + None-check en `camthreader.py` — reescritura completa de `WebcamVideoStream` (evita frame desgarrado/stale y crash al desconectar cámara) | [programa-lucio](../../../project/backlog/staging/programa-lucio-rpi-vision.md) · draft: [draft-issue-resi-camthreader-lock](../../../project/backlog/staging/draft-issue-resi-camthreader-lock.md) |
| **#111** | `try/except` en `infer_thread()` para evitar el **deadlock silencioso** de la cola de rescate si la inferencia tira una excepción | [programa-lucio](../../../project/backlog/staging/programa-lucio-rpi-vision.md) · draft: [draft-issue-resi-infer-thread](../../../project/backlog/staging/draft-issue-resi-infer-thread.md) |

> **Nota Lucio:** #110 es el de mejor ratio impacto/riesgo (una línea, crash determinista). #65 y #113 se resuelven con el **mismo** `Lock` → un solo PR.

### Reportes de auditoría que respaldan estos fixes

| Reporte | Subsistema RPi | Findings | Link |
|---------|----------------|----------|------|
| **rpi-01** | Percepción / visión (la mayor densidad de Python del lote) | V18-01 … V18-12 (parse tensor TFLite #124/B7, `silver_mask` en BGR #B2, máscara roja sin wrap #B9, verde LAB #86, `camthreader` sin Lock #113) | [rpi-01-vision.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/rpi-01-vision.md) |
| **rpi-02** | FSM de decisión de alto nivel | D1 … D12 (decisión de verde con ROIs mezclados `cx_black` vs `greenCentroidX`; referencia #110, #120/B2/B3, #127, #123) | [rpi-02-decision.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/rpi-02-decision.md) |

> **Matiz importante sobre "clases YOLO invertidas" (#B3):** **NO** es cierto que las clases del modelo estén invertidas — **coinciden con `metadata.yaml`**. Lo que estaba cruzado eran los **nombres de sub-estados de depósito**, no las clases del modelo. El reporte **rpi-01 (finding V18-03)** ya tiene este matiz y es la fuente de verdad. No repitas "las clases YOLO están invertidas" sin esa aclaración.

---

## 3. Benjamin Villagran (`@benjaminvillagran`) — RPi 4B + Hardware + systemd

**Fuente primaria de código (mixta: systemd + Python + bash + protocolo de banco):**
👉 **[`programa-benjamin-rpi-hardware.md`](../../../project/backlog/staging/programa-benjamin-rpi-hardware.md)**

Rol dual: fixes propios de sistema/comms **+** el **gate de banco** (valida en hardware real los PRs de Lucio y Laureano). Propone auto-restart del proceso, pinneo de dependencias, TX serial defensivo y un protocolo de banco reusable con templates de TEST_LOG.

### 3.1 systemd / arranque

| Issue | Qué propone | Archivo fuente |
|-------|-------------|----------------|
| **#108** | Unit `robot.service` con `Restart=always` + `RestartSec=2` (auto-restart del proceso `Main.py` si crashea) | [programa-benjamin](../../../project/backlog/staging/programa-benjamin-rpi-hardware.md) · draft: [draft-issue-resi-systemd-rpi](../../../project/backlog/staging/draft-issue-resi-systemd-rpi.md) |

### 3.2 Python (Main.py)

| Issue | Qué propone | Archivo fuente |
|-------|-------------|----------------|
| **#108** | `__main__` guard + `try/except` de último recurso + handlers de señal con `_emergency_stop()` (manda `speed=0` al Teensy antes de morir) | [programa-benjamin](../../../project/backlog/staging/programa-benjamin-rpi-hardware.md) |
| **#66** | `send_frame_safe()`: clamp de rango (speed/angle) + captura de `SerialException`/`SerialTimeoutException` + contador de errores | [programa-benjamin](../../../project/backlog/staging/programa-benjamin-rpi-hardware.md) |

### 3.3 Config

| Issue | Qué propone | Archivo fuente |
|-------|-------------|----------------|
| **#68** | `requirements.txt` **pineado** (`==`) desde un `pip freeze` de la Pi de producción, para reproducir el entorno desde una SD limpia | [programa-benjamin](../../../project/backlog/staging/programa-benjamin-rpi-hardware.md) |

### 3.4 Protocolo de banco (gate de calidad reusable)

No es un fix de código: es el **procedimiento de validación en banco** que Benjamin usa para aprobar PRs de RPi/comms (de Lucio y de Laureano). Incluye equipamiento mínimo, flujo de sesión, **tests de inyección de fallas F1–F5** (desconexión de cámara, desconexión UART, `kill -9`, arranque sin cámara, arranque sin Teensy) y templates de entrada para `testing/TEST_LOG.md`.
👉 Sección "Protocolo de banco" en [programa-benjamin](../../../project/backlog/staging/programa-benjamin-rpi-hardware.md).

> **Nota Benjamin:** **ajustá las rutas de la unit systemd y los parámetros a la Pi real** antes de commitear (el `ExecStart`/`WorkingDirectory` dependen de dónde esté el clone). Ningún PR de visión/comms se mergea sin tu check en hardware.

### Reporte de auditoría relacionado

| Reporte | Subsistema | Findings | Link |
|---------|------------|----------|------|
| **rpi-03** | Comms + threading (lado RPi) | CT-01 … CT-11 (#113, #111, #66, #73, #53 lado RPi, #108) + agrupamiento sugerido (FIX-CAM, FIX-PIPELINE-RESCATE, FIX-SERIAL-TX) | [rpi-03-comms-threading.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/rpi-03-comms-threading.md) |

> rpi-03 cruza con `programa-lucio` (#113/#111) y con `programa-benjamin` (#66/#108).

---

## 4. Comms / protocolo serial (ambos lados) — referencia transversal

Estos reportes documentan el **protocolo serial completo** Teensy ↔ RPi. No son de una sola persona: tocan firmware (Laureano) y RPi (Lucio/Benjamin). Sirven como "cabecera" que une los lados C++ (teensy-05) y Python (rpi-03).

| Reporte | Contenido | Estado | Link |
|---------|-----------|--------|------|
| **comms-01** | Protocolo integral: tabla de frame `[255,speed,254,angle,253,green,252,silver]`, diagramas de secuencia, presupuesto de bytes/buffer 64 B + fixes **F-1 … F-6** (handshake 0xFA, heartbeat #53, overflow #63/#70, contrato de rangos) | Referencia del protocolo (más diagramas/prosa que código ejecutable) | [comms-01-protocolo-integral.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/comms-01-protocolo-integral.md) |
| **comms-02** | ESP32 / SuperTeam Challenge: estado del módulo. **El ESP32 no existe** (0 código, 0 footprint); hay 2 planes incompatibles (#84 BT-RPi con stub `superteam.py` inexistente vs ESP32–Teensy por Serial8). Único excerpt: los `#define BUZZER 31 / LED_ROJO 30` ya aplicados | **Entrada de ESTADO, no de snippet aplicable** — no hay código propuesto concreto todavía, sólo decisión de arquitectura pendiente | [comms-02-esp32.md](../../../project/backlog/staging/auditoria-integral-2026-05-18/comms-02-esp32.md) |

---

## 5. Coordinación / validación (Enzo, coach) — cómo se validan estas propuestas

👉 **[`programa-enzo-coordinacion-validacion.md`](../../../project/backlog/staging/programa-enzo-coordinacion-validacion.md)**

**No contiene snippets de código del robot.** Es el documento de coordinación/aprobación de Enzo: checklists de validación de PRs (firmware / Python RPi / systemd), criterios de gate por fase, y comandos `gh` de lectura. Útil como referencia de **cómo se aprueba** un PR antes de mergear, no como fuente de código.

> Las fechas de régimen que aparecen ahí (tracks/gates 26-may / 11-jun) son **históricas** → ver [`ESTADO-ACTUAL-2026-05-31.md`](../ESTADO-ACTUAL-2026-05-31.md).

---

## Resumen: dónde está cada cosa

| Si buscás… | Andá a… |
|------------|---------|
| Código C++ Teensy listo para adaptar | `programa-laureano-teensy-resiliencia.md` |
| Código Python RPi (visión) listo para adaptar | `programa-lucio-rpi-vision.md` |
| systemd + Python sistema + protocolo de banco | `programa-benjamin-rpi-hardware.md` |
| Por qué se propone cada fix (excerpts del código actual) | reportes `teensy-0X` / `rpi-0X` / `comms-0X` en `auditoria-integral-2026-05-18/` |
| Borradores de issue (intención + test plan) | `draft-issue-resi-*.md` |
| Cómo se valida/aprueba un PR | `programa-enzo-coordinacion-validacion.md` |
| Estado real del proyecto y régimen vigente HOY | [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../ESTADO-ACTUAL-2026-05-31.md) · [informe director](../2026-05-31-informe-coach-auditoria-integral.md) |

---

*Índice generado para que el equipo encuentre y valide las propuestas de código. Recordá: **código propuesto, no commiteado — cada alumno hace su propio PR, prueba en banco y registra en `testing/TEST_LOG.md`.***
