# Auditoría Integral 2026-05-18 — Módulo COMMS-02: ESP32 / SuperTeam Challenge

> **Dominio:** rastro del módulo ESP32 que "se incorporó" al robot RCJ Rescue Line 2026.
> **Pregunta del coach:** ¿existe código? ¿qué hace? ¿cómo se conecta (pines, bus, protocolo)? ¿cuál es el propósito? Si no existe o está esbozado, decirlo con evidencia y enumerar qué falta para SuperTeam.
> **Modo:** sólo lectura. No se modificó código ni se tocó GitHub.
> **Checkout auditado:** rama `feature/initialize-testing-log` (HEAD `5a868ea`), contenido también presente en `main`.

---

## 0. Veredicto en una línea

**El módulo ESP32 NO existe como hardware ni como software. Existe ÚNICAMENTE como una propuesta escrita** (un capítulo del documento `hardware/cambios_de_hardware.md`) y un **stub conceptual no implementado** en el issue #84. **Cero líneas de código** (ni firmware Teensy, ni sketch ESP32/MicroPython, ni Python RPi). **Cero footprint en el PCB.** Lo único que SÍ se ejecutó del plan es un cambio de pines en el firmware que **liberó los pines 34/35 para un módulo que nunca se conectó** — dejando dos pines UART asignados a nada.

Para el SuperTeam Challenge de Incheon, hoy el robot **parte de cero**: no hay ningún canal inter-robot funcional, ni siquiera a nivel de andamiaje compilable.

---

## 1. Qué se buscó y cómo (trazabilidad)

Búsqueda exhaustiva en todo el repo. Términos: `esp32`, `esp-now`/`espnow`, `bluetooth`, `ble`, `wifi`/`wi-fi`, `hc-05`/`hc-06`, `micropython`, `Serial8`/`UART8`, `superteam`/`super team`, `inter-robot`, `nrf24`, `radio`, `zigbee`, `bleak`, `pybluez`, `broadcast`, `socket`.

Ámbitos cubiertos:
- `software/teensy/firmware/**` (src, libs, tests, `platformio.ini`, `variables_doc.md`)
- `software/raspberry/**` (`final_rpi/`, `test/`, `AI/`, `requirements.txt`)
- `hardware/**` (`cambios_de_hardware.md`, `electronics/PCB_Main/`, BOM, legacy)
- `docs/es/**` y `docs/en/**`
- `archive/**` (código legacy roboliga/rescue_line)
- `project/backlog/`, `AUDIT-ACTION-PLAN.md`, `CHANGELOG.md`, `README.md`
- Issue **#84** vía `gh issue view` (lectura)
- `git log` / `git log -L` / `git log -S` para fechar y atribuir cambios

**Resultado neto de la búsqueda en código fuente real:** `0` coincidencias verdaderas. Todas las apariciones de los términos en `software/**` fueron **falsos positivos por substring** (`varia**ble**`, `availa**ble**`, `Legacy MOSSE`, `enable`, etc.). No hay un solo identificador, `#include`, `begin()`, define o comentario que toque ESP32 / BLE / ESP-NOW / WiFi en el firmware ni en la RPi.

---

## 2. Dónde SÍ aparece el ESP32 (las únicas dos fuentes)

### 2.1 `hardware/cambios_de_hardware.md` — sección "ESP32 Super Mini — Implementación SuperTeam Challenge" (líneas 199–393)

- **Autoría y fecha:** commit `789cd7d` "Análisis de cambios en hardware", **Benjamin Villagran**, **2026-04-28**. Es el **único** commit que tocó este archivo. Presente en `main`.
- **Naturaleza:** es un documento de **análisis/propuesta de hardware**, no un registro de algo ya hecho. El texto es deliberativo ("Considero que la incorporación... es una de las soluciones prioritarias", "Aunque es necesario desarmar al robot..."). El propio CLAUDE.md (Regla de oro #6) define este archivo como bitácora de cambios físicos — pero acá se usó como propuesta pendiente de aprobación, no como cambio confirmado.

**Contenido técnico de la propuesta (lo que el equipo *quiere* hacer, no lo que está hecho):**

| Aspecto | Especificación propuesta (cita textual del doc) |
|---|---|
| Módulo | "**ESP32 Super Mini**" (línea 213) |
| Propósito | **Canal inter-robot para SuperTeam Challenge** — coordinar acciones entre dos robots de equipos distintos en tiempo real (líneas 207–209). NO es telemetría. |
| Conexión a Teensy | **UART** vía **Serial8 (pines 34/35)**: "Serial8 RX → pin 34 (antes: BUZZER) / Serial8 TX → pin 35 (antes: LED_ROJO)" (líneas 213–219, 250) |
| Rol de la ESP32 | "actúa como módulo **BLE** dedicado: recibe comandos de la Teensy por serial y los transmite al robot del otro equipo, y viceversa" (línea 221). Más abajo se habla de **BLE broadcast** tipo radio (líneas 366–390). |
| Firmware de la ESP32 | "**MicroPython** ya conocido por el equipo" (líneas 226, 271) — pero NO hay ningún `.py`/`main.py` de ESP32 en el repo. |
| Alimentación | VIN de la ESP32 → 5V del regulador existente; GND común (líneas 258–264) |
| Cambio de SW declarado | "**(2 líneas)**": mover `#define BUZZER 35→31` y `#define LED_ROJO 34→30` (líneas 230–242) |
| Cambio de HW declarado | Desoldar BUZZER del pin 35 → pin 31; desoldar LED_ROJO del pin 34 → pin 30; cablear pin 34 (RX8) y 35 (TX8) a la UART de la ESP32; diseñar soporte 3D (tabla líneas 246–251) |
| Esquemático | Sólo un `<img>` embebido apuntando a `user-attachments` de GitHub (línea 281). **No hay** un archivo de esquemático versionado con la ESP32 en `hardware/electronics/`. |
| Análisis comparativo | Descarta HC-05 (roles maestro/esclavo fijos, necesita MAC previa) y HC-06 (sólo esclavo) a favor de BLE broadcast (líneas 285–390). El razonamiento es sólido y bien argumentado. |

**Observación crítica de protocolo:** la propuesta es **internamente ambigua/contradictoria** sobre el protocolo de radio. Dice "BLE" y "BLE broadcast" indistintamente. BLE "broadcast" real (advertising no conectado) tiene payload de ~31 bytes por paquete y semántica muy distinta a un GATT conectado (que es lo que sugiere "recibe comandos... y los transmite"). El issue #84, además, asume BLE conectado con `peer_mac`. No hay un diseño de protocolo cerrado: ni framing, ni IDs de mensaje, ni tamaños, ni handshake, ni manejo de colisión en sala con múltiples equipos transmitiendo. Es una idea, no una especificación.

### 2.2 Issue #84 — "[TEMA] Stub Bluetooth para SuperTeam Challenge (canal inter-robot)"

- **Estado:** OPEN. Autor: @gviollaz. Asignados: @enzzo19, @benjaminvillagran. Labels: `subsystem/comms`, `type/feature`. 0 comentarios.
- **Naturaleza:** flag de auditoría previa (CORRECTITUD/RESILIENCIA) que **propone un stub**, explícitamente **no implementado** ("solo andamio para que el día del challenge sea integrar, no diseñar").
- **Enfoque del issue:** **divergente del doc de hardware.** El issue propone resolver SuperTeam **del lado de la RPi**, usando el **Bluetooth class 2 nativo de la Raspberry Pi 4B** con librería `bleak` (BLE asyncio) o `pybluez`, en un archivo nuevo `software/raspberry/final_rpi/superteam.py` con una clase `SuperTeamChannel(role, peer_mac)`. **No menciona ESP32 en absoluto.**
- **Estado del stub:** el archivo `software/raspberry/final_rpi/superteam.py` **NO existe** (confirmado: `final_rpi/` sólo contiene `Main.py`, `calibration.py`, `camthreader.py`, `zonasdepositoalta.onnx`). Los métodos del stub propuesto (`announce_state`, `wait_for_signal`) son cuerpos `pass` con `# TODO: implementar BLE`.

**Esto destapa el hallazgo más importante para la decisión (ver §5):** existen **DOS estrategias de SuperTeam incompatibles y sin coordinar** conviviendo en el repo:
1. **Doc de hardware (Benjamin):** ESP32 externa colgada de la Teensy por UART (Serial8), radio BLE/ESP-NOW desde la ESP32.
2. **Issue #84 (coach):** Bluetooth nativo de la RPi, sin hardware extra, `bleak`.

Ninguna de las dos está implementada. Decidir cuál se sigue es prerrequisito de cualquier trabajo.

---

## 3. Estado real del firmware: el cambio de pines SÍ se aplicó, el módulo NO

Este es el hallazgo más concreto y verificable, y el de mayor riesgo silencioso.

**Hecho:** el firmware en `main` ya tiene aplicado el "cambio de 2 líneas" de la propuesta:

```cpp
// software/teensy/firmware/src/main.cpp:31-32 (estado ACTUAL en HEAD)
#define BUZZER 31         // Definicion de PIN BUZZER
#define LED_ROJO 30       // Definicion de PIN LED_ROJO
```

**`git log -L 31,32:...main.cpp` confirma la transición:**
- Commit `3ddc89d` (migración del repo legacy): nacían como `BUZZER 35` / `LED_ROJO 34`.
- Commit **`073b8a2`** "hardware(docs): Esquematico mas legible, bom y actualizacion de pines en main.cpp": los cambia a `BUZZER 31` / `LED_ROJO 30`.

Es decir: **los pines 34 y 35 fueron liberados en el firmware específicamente para conectar la ESP32 por Serial8** — pero la ESP32 nunca se conectó.

**Qué NO está (verificado en `main.cpp` completo y en todo el firmware):**
- **No existe `Serial8.begin(...)`.** El único puerto serie inicializado en `setup()` es `Serial5.begin(115200)` (el enlace con la RPi). `Serial1` está comentado, `Serial`/USB comentado. **`Serial8` no aparece en ninguna parte del repo** (`git grep Serial8` → vacío).
- **No hay lectura/escritura de Serial8**, ni parser de mensajes inter-robot, ni máquina de estados de SuperTeam, ni `#include` de ninguna lib BLE/WiFi.
- Los pines **34 y 35 quedaron sin reasignar**: no se usan como GPIO, ni como UART, ni se declaran con `pinMode`. Están **flotantes/sin función** en el firmware.

**Implicancia (riesgo a presentar como TEMA, no como "bug"):** el equipo ejecutó el paso reversible y barato del plan (mover defines) pero no el costoso (desarmar, soldar, montar la ESP32, escribir el firmware de ambos lados). Quedó un estado intermedio:
- **Riesgo de NO tocar:** el robot funciona perfecto hoy (BUZZER y LED_ROJO responden en sus nuevos pines 31/30 si el cableado físico acompañó el cambio de define). PERO si el cableado físico **no** se movió, BUZZER/LED_ROJO no funcionan (el firmware escribe a 31/30 mientras el hardware sigue en 35/34). **Esto NO se puede verificar por código — requiere banco.** Es la primera cosa a chequear físicamente.
- **Riesgo de "completar" la ESP32:** desarmar el robot a < 5 semanas del mundial (Incheon 2026-06-30) para soldar y montar un módulo cuyo software no existe es alto riesgo de regresión sobre subsistemas validados (CLAUDE.md Regla de oro #4).
- **Tiempo:** verificar pines en banco: 15 min. Revertir defines a 35/34 si se decide NO poner ESP32: 2 min + 1 entrada en TEST_LOG.

---

## 4. Estado real del PCB y la BOM: sin rastro de ESP32

- **`hardware/electronics/PCB_Main/PCB.json`** (EasyEDA): las **únicas dos descripciones de componente** presentes en todo el archivo son `Ultrasonic Ranging Module HC-SR04` y `DIP Black Male Header VERT`. Búsqueda literal de `ESP`, `ESP32`, `WROOM`, `WROVER`, `ESP-NOW`: **0 coincidencias.** No hay footprint, ni módulo, ni header dedicado a una ESP32 en la placa.
- **`hardware/electronics/PCB_Main/README.md` (BOM):** lista cámara, BNO055, 2× VL53L0X, 3× HC-SR04, APDS9960, Raspberry Pi 4, Teensy 4.1, motores, servos, reguladores, batería. **No incluye ESP32 Super Mini.**
- El `ROBOCUP.SHEET.pdf` (esquemático) aparece en la búsqueda inicial sólo porque es un binario; el esquemático "con la ESP32" del doc es una imagen embebida en GitHub (`user-attachments`), **no un artefacto versionado**.

Conclusión: a nivel hardware versionado, la ESP32 **no fue incorporada**. Lo que existe es un render/boceto en una propuesta.

---

## 5. Qué falta para tener SuperTeam funcional (checklist accionable)

El robot está hoy en **~0% de implementación** de comunicación inter-robot. Antes de cualquier código hay una **decisión de arquitectura pendiente** porque hay dos planes incompatibles (§2.2). Presento las dos rutas con su costo, para que el equipo decida (filosofía TEMAS A ANALIZAR — el equipo decide, el coach asiste).

### Decisión 0 (bloqueante): ¿ESP32 externa o BT nativo de la RPi?

| Criterio | Ruta A — ESP32 Super Mini (doc HW) | Ruta B — Bluetooth nativo RPi (issue #84) |
|---|---|---|
| Hardware extra | Sí: módulo + soporte 3D + desarmar/soldar | **No** (BT class 2 ya está en la Pi 4B) |
| Firmware nuevo | Sí, en 2 lugares (Teensy Serial8 **y** sketch ESP32) | No toca Teensy; sólo Python en RPi |
| Riesgo de regresión pre-mundial | **Alto** (abrir el robot validado) | **Bajo** (módulo opcional por flag, no afecta flujo single-robot) |
| Quién entra en el hot-path serial | Suma tráfico al ya frágil enlace Teensy↔RPi | Aísla SuperTeam del enlace de control |
| Madurez en el repo | Sólo doc + pines liberados | Sólo stub conceptual (archivo inexistente) |

> Lectura del auditor: la **Ruta B (issue #84)** es la de menor riesgo a 5 semanas del mundial y la que el coach ya esbozó. La Ruta A es más elegante para robot-a-robot puro pero implica cirugía sobre un robot validado. **No es decisión del auditor** — es del equipo (#84 está asignado a @enzzo19 y @benjaminvillagran).

### Si se elige Ruta A (ESP32) — qué falta (todo):
1. **Confirmar/comprar** la ESP32 Super Mini y agregarla a la BOM (`PCB_Main/README.md`). (15 min doc + compra)
2. **Hardware:** desoldar BUZZER (pin 35→31) y LED_ROJO (pin 34→30) en la placa real, cablear pin 34/35 de la Teensy a la UART de la ESP32, alimentar VIN=5V/GND. Verificar que BUZZER/LED_ROJO siguen funcionando tras el remapeo. Diseñar e imprimir soporte 3D. (varias horas + banco)
3. **Firmware Teensy:** agregar `Serial8.begin(<baud>)` en `setup()`, definir framing de mensajes inter-robot, parser no bloqueante (cuidado: el firmware ya tiene problemas de lecturas bloqueantes y descarte de bytes — issues #60/#63/#70), e integrarlo con la FSM de rescate **sin** romper el heartbeat con la RPi (#53). (días)
4. **Firmware ESP32 (inexistente):** escribir el sketch MicroPython/C++ que hace de puente UART↔radio. Definir si es BLE GATT, BLE advertising/broadcast o ESP-NOW (la propuesta los mezcla). Manejar emparejamiento sin conocer al otro equipo de antemano, colisiones en sala, reconexión, timeouts. (días)
5. **Protocolo inter-robot cerrado:** IDs de mensaje, tamaños, handshake, qué se comunica ("llegué al checkpoint", "esperá"), y degradación si no hay par. (diseño)
6. **Banco con DOS robots/placas** y entrada en `testing/TEST_LOG.md`. (CLAUDE.md Regla #3)

### Si se elige Ruta B (BT RPi / issue #84) — qué falta:
1. **Crear `software/raspberry/final_rpi/superteam.py`** (hoy no existe) implementando `SuperTeamChannel` de verdad (los `pass`/TODO del stub).
2. **Elegir y pinnear** `bleak` (BLE, asyncio) o `pybluez` en `requirements.txt` (que además hoy no tiene pinning — issue #68).
3. **Integrar el flag opcional** en `Main.py` (`SUPERTEAM_ROLE` por env var) garantizando que **sin** el flag el robot se comporta idéntico (test explícito).
4. **Protocolo + framing + timeouts** (mismo diseño que Ruta A punto 5).
5. **Banco con dos Pi** (o Pi + smartphone como par) y entrada en `TEST_LOG.md`.
6. Estimación del propio issue #84: **~4 h** para el stub funcional ping-pong; el protocolo real del challenge es adicional.

### Transversal a ambas rutas (lo que hoy NO está y es imprescindible):
- **Diseño de protocolo de aplicación SuperTeam** — qué mensajes, cuándo, qué hace el robot al recibirlos. Hoy **no existe en ningún lado**, ni siquiera en prosa. Sin esto, ni la ESP32 ni el BT sirven.
- **Estrategia de coordinación con el equipo-par** antes del torneo (el reglamento asigna parejas en el momento; conviene acordar formato mínimo común). El doc lo identifica bien como el problema central.
- **Plan de degradación:** si el canal falla, el robot debe seguir corriendo su pista individual sin colgarse (esto enlaza con los watchdogs/heartbeat de #27/#53).

---

## 6. Cruce con auditorías previas (no se repiten, se citan)

- **Issue #84** (RESILIENCIA/flexibilidad) ya flagueó la ausencia de canal inter-robot del lado RPi y propuso el stub. **Sigue 100% válido y sin implementar.** Esta auditoría agrega: (a) existe una segunda propuesta divergente en `hardware/cambios_de_hardware.md` (ESP32 por Serial8) que el issue #84 no contempla, y (b) el firmware **ya liberó los pines 34/35** para esa ESP32, dejando un estado intermedio inconsistente.
- **Cadena RESILIENCIA #53/#27** (heartbeat / watchdogs): cualquier integración de SuperTeam por la Teensy (Ruta A) toca el mismo hot-path serial frágil. No sumar tráfico al enlace Teensy↔RPi sin antes cerrar el heartbeat.
- **CORRECTITUD #B*:** no hay solapamiento directo (ninguno de los 10 bugs toca ESP32/comms inter-robot). El protocolo `[255,speed,254,angle,253,green,252,silver]` es exclusivamente RPi→Teensy y no contempla un tercer interlocutor.

---

## 7. Resumen ejecutivo

1. **No hay módulo ESP32 incorporado.** Hay (a) una **propuesta de hardware** firmada por Benjamin Villagran el 2026-04-28 en `hardware/cambios_de_hardware.md`, y (b) un **stub no implementado** en el issue #84 (que además usa otra arquitectura: BT nativo de la RPi). **Cero código** en firmware o RPi; **cero footprint** en PCB; **cero entrada** en BOM.
2. **El propósito declarado es claro y correcto:** canal inter-robot para el **SuperTeam Challenge** (no telemetría). El reglamento 2026 §6.3 lo recomienda; la referencia de equipos top (§15) confirma 2.4 GHz / ≤100 mW EIRP.
3. **Conexión propuesta:** Teensy ↔ ESP32 por **UART (Serial8, pines 34/35)**; ESP32 hace de puente a **radio BLE/ESP-NOW** (la propuesta mezcla BLE GATT, BLE broadcast y ESP-NOW sin cerrar cuál).
4. **Hallazgo de mayor riesgo:** el firmware **ya aplicó** el remapeo de pines (BUZZER 35→31, LED_ROJO 34→30, commit `073b8a2`) para hacerle lugar a una ESP32 que nunca se montó. Pines 34/35 quedaron sin función y `Serial8` nunca se inicializa. **Verificar en banco** que BUZZER/LED_ROJO sigan funcionando tras el cambio de defines (no comprobable por código).
5. **Dos planes incompatibles sin coordinar** (ESP32-Teensy vs BT-RPi). **Decidir uno es prerrequisito** de todo trabajo.
6. **Para SuperTeam funcional falta esencialmente todo:** decisión de arquitectura, hardware (si Ruta A), firmware de ambos lados, **diseño de protocolo de aplicación** (hoy inexistente en cualquier forma), y validación en banco con dos robots. A < 5 semanas de Incheon, la **Ruta B (#84, BT-RPi, ~4 h de stub + protocolo)** es la de menor riesgo de regresión; la **Ruta A** implica cirugía sobre un robot validado.

---

*Auditoría COMMS-02 (ESP32 / SuperTeam) — Auditoría Integral 2026-05-18. Sólo lectura; sin commits ni cambios en GitHub. Filosofía TEMAS A ANALIZAR: cada hallazgo lleva riesgo-de-no-tocar + riesgo-de-tocar + tiempo. El equipo decide; el coach asiste; el auditor IA presenta el material.*
