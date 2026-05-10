# Análisis integral de comunicación RPi ↔ Teensy — 2026-05-10

> **Objetivo:** identificar todos los problemas de **eficiencia**, **desincronización** y **fail-safe** del canal serial entre la Raspberry Pi 4B y la Teensy 4.1, y proponer un plan de fixes priorizado para llegar al mundial RCJ 2026 con un protocolo robusto y rápido.
>
> **Audiencia:** mentores y alumnos del equipo IITA Salta. Coach: Gustavo Viollaz. Asignados de seguimiento: Enzo (`@enzzo19`) + Benjamin (`@benjaminvillagran`).
>
> Este documento complementa, **no reemplaza**, [`comunicacion-rpi-teensy.md`](comunicacion-rpi-teensy.md).

---

## 1. Resumen ejecutivo

El canal funciona pero **no es fail-safe**: si la Pi se cuelga el Teensy sigue moviendo el robot con el último comando; si el Teensy se resetea la Pi no se entera; un solo bit flip puede corromper un campo sin que ningún lado lo note. Hay además **ineficiencias claras** (`serialEvent5()` consume 1 byte por loop; `reset_input_buffer()` en RPi descarta comandos válidos) que penalizan la latencia de respuesta y producen pérdidas silenciosas de comandos.

**Recomendación táctica:** aplicar 6 fixes mínimos sin cambiar el protocolo (cubre 80% del riesgo) **antes** de considerar un protocolo v2 con length+CRC. Ver [§7 Plan de migración](#7-plan-de-migración-por-fases).

---

## 2. Arquitectura actual

```
┌──────────────────┐   UART 115200, 8-N-1   ┌──────────────────┐
│  Raspberry Pi 4B │ ─────────────────────► │   Teensy 4.1     │
│   /dev/serial0   │                        │   Serial5        │
│                  │ ◄─────────────────────  │                  │
│  pyserial 3.x    │   acks de 1 byte       │  Teensyduino     │
└──────────────────┘                        └──────────────────┘
       │                                              │
       └─ visión (YOLO+OpenCV)                        └─ motores, encoders, ToF, IMU,
          decisión alto nivel                            servos, sensor color
```

**Frame RPi → Teensy** (8 bytes, sin CRC, sin length):

```
[ 0xFF, speed,  0xFE, angle, 0xFD, green_state, 0xFC, silver_line ]
```

**Mensajes Teensy → RPi** (1 byte cada uno, sin frame):

| Byte | Significado |
|---|---|
| `0xF9` (249) | Fin de startUp → cambiar a `linea` |
| `0xF8` (248) | Suficientes pelotas → cambiar a `depositar` |
| `0xFF` (255) | Switch off → volver a `esperando` |

---

## 3. Métricas estimadas (con código actual)

> *Estimaciones de oficina; medirlas en banco con un analizador lógico es trabajo pendiente — ver §8.*

| Métrica | Valor estimado | Comentario |
|---|---|---|
| Bandwidth utilizado | ~2 % | 8 bytes × 30 fps = 240 B/s sobre 11 520 B/s teóricos |
| Latencia frame TX (8 B) | ~0,7 ms | a 115 200 baud |
| Frecuencia de RPi → Teensy | 25–40 frames/s | atado al FPS de visión |
| Frecuencia de Teensy → RPi | aperiódica | sólo en cambios de estado |
| Latencia visión → motor | 70–200 ms | dominada por inferencia YOLO + ciclo loop Teensy |
| Drain rate del parser Teensy | **1 byte por iteración del loop** | ver §4.1 — *éste es el problema #1* |

---

## 4. Problemas de eficiencia

### 4.1 [P1] `serialEvent5()` consume sólo 1 byte por llamada

**Archivo:** [`software/teensy/firmware/src/main.cpp:383-406`](../../software/teensy/firmware/src/main.cpp#L383-L406)

```cpp
void serialEvent5() {
    if (Serial5.available() > 0) {
        int data = Serial5.read();   // ← un solo byte por llamada
        // ... parser ...
    }
}
```

Si la RPi escribe los 8 bytes del frame en ráfaga (que es lo que hace `pyserial`), el Teensy necesita **8 iteraciones** del `loop()` para terminar de parsear el frame. Si una de esas iteraciones cae adentro de un `runTime` o `runDistance` (ver issue [#63](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/63)), el frame se queda atascado en el buffer hasta que termine la maniobra.

**Fix:**

```cpp
void serialEvent5() {
    while (Serial5.available() > 0) {     // drain completo
        int data = Serial5.read();
        // ... mismo parser de antes ...
    }
}
```

**Impacto:** latencia visión → motor baja en ~30–80 ms en el caso peor. Es **el cambio de mayor relación costo-beneficio** del documento.

### 4.2 [P1] `reset_input_buffer()` descarta comandos válidos

**Archivo:** [`software/raspberry/final_rpi/Main.py:568-572`](../../software/raspberry/final_rpi/Main.py#L568-L572)

```python
while estado == 'esperando':
    frame = vs.read()
    silver_line = False
    if ser.in_waiting > 0:
        data = ser.read()
        if data == b'\xf9':
            estado = 'linea'
        ser.reset_input_buffer()   # ← borra TODO lo demás
```

Si el Teensy mandó `0xF9` y a continuación cambia de estado y manda otro byte (e.g. `0xFF` por kill switch), ese segundo byte **se pierde** en el `reset_input_buffer()`.

**Fix:** quitar el `reset_input_buffer()` después del read. Si no matcheó, dejar el byte en el buffer (no lo había de todos modos — `ser.read()` ya lo consumió). Si matcheó, los bytes posteriores son válidos y deben respetarse.

```python
if ser.in_waiting > 0:
    data = ser.read()
    if data == b'\xf9':
        estado = 'linea'
    # NO reset_input_buffer
```

### 4.3 [P2] Frame fijo, no rate-limited por delta

**Archivo:** [`Main.py:664-669`](../../software/raspberry/final_rpi/Main.py#L664-L669) y `:523-524`

La RPi envía un frame en CADA iteración del loop de visión, aunque `speed`, `angle`, `green_state` no hayan cambiado. Es **30 fps × 8 bytes = 240 B/s** constantes — bandwidth no es problema, pero **CPU del parser Teensy sí**: un drain de 8 bytes cada 33 ms compite con loops críticos.

**Fix sugerido:**
- Mantener envío periódico **mínimo** de 10 Hz (heartbeat).
- Si todos los campos cambiaron <delta_threshold y no pasaron 100 ms del último, **omitir** el envío.
- Resultado: ~12 fps de envío en estado estable, full rate cuando hay cambio.

> **Cuidado:** si se hace el fix de `serialEvent5() while`, la mayor parte del problema desaparece. Este punto sólo vale el esfuerzo si vemos lag medible después de §4.1.

### 4.4 [P2] `runDistance` y `runTime` con `delay(10)` — polling lento del kill switch

**Archivo:** [`main.cpp:551, 575`](../../software/teensy/firmware/src/main.cpp#L551)

`delay(10)` adentro del while de movimiento limita el polling del switch + serial a 100 Hz. Para un cuerpo crítico de control, debería ser ≥500 Hz (= sin delay). Es deuda técnica enredada con [#59](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/59) y [#63](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/63), no vale issue separado.

---

## 5. Problemas de desincronización

### 5.1 [P1] Sin handshake/versión al iniciar — un reset del Teensy desincroniza el sistema

**Síntoma:** si el Teensy se cuelga y reinicia (o lo apagás y prendés con la Pi corriendo), arranca en `esperando` pero la Pi puede estar en `linea` mandando frames. La Pi nunca recibe `0xF9` (porque ya pasó), el Teensy ignora `green_state` (porque no entró en `linea`). **Resultado: robot inerte, sin diagnóstico.**

**Fix mínimo:**
- En `setup()` del Teensy, mandar `0xFA` (sync byte propio) durante 2 s (cada 100 ms).
- En la Pi, en CUALQUIER estado, si llega `0xFA` → reset estado a `esperando`.

**Fix completo:**
- Handshake de versión: ambos lados intercambian byte de versión al boot.
- Si versión de firmware ≠ versión esperada en RPi, prender LED rojo y abortar.

Esto **anula también el problema 5.4** (RPi no detecta reset del Teensy).

### 5.2 [P1] Sin sanity check de rangos en payload

**Archivo:** [`main.cpp:386-405`](../../software/teensy/firmware/src/main.cpp#L386-L405)

```cpp
else if (serial5state == 0)
    speed = (double)data / 100 * 100; // sin clamp
else if (serial5state == 1)
    steer = ((double)data - 90) / 90; // sin clamp
```

Si por bug de RPi llega `speed = 200`, el Teensy le pasa 200 a `steer()`, que clampa a 159 — pero ese clamp es invisible al sistema. Peor: si `angle` llega como 200, `steer = (200-90)/90 = 1.22`, fuera del rango esperado [-1, 1] que `steer()` también clampea silenciosamente.

**Fix:** clamp explícito + log si fuera de rango. Idealmente, descartar el frame:

```cpp
else if (serial5state == 0) {
    if (data < 0 || data > 100) { /* log + ignorar */ return; }
    speed = data;
}
```

### 5.3 [P1] Sin CRC ni checksum — bit flip silencioso

**Síntoma:** el cable USB-serial es robusto pero el rack de competencia tiene mucho ruido de motores DC y servos. Un bit flip en `green_state` (e.g. `7` → `5`) es **silencioso** — no hay detección.

**Fix mínimo:** XOR de los 4 bytes de payload, anexado como byte 9.

```
[0xFF, speed, 0xFE, angle, 0xFD, green, 0xFC, silver, CRC]
```

**Costo:** 1 byte extra (12 % overhead). Muy barato. Detectar bit flips simples cubre ~80 % de los casos.

**Fix completo:** CRC-8 polinomio 0x07. Detecta más errores. Tabla precomputada en flash para no afectar performance.

### 5.4 [P1] RPi no detecta si el Teensy se reinició

Cubierto por §5.1 con el handshake `0xFA`.

### 5.5 [P2] Colisión potencial entre sync bytes y payload

Hoy:
- `speed` ∈ [0, 100] → no toca [252, 255]. ✅
- `angle` ∈ [0, 180] (después de `+90`) → no toca [252, 255]. ✅
- `green_state` ∈ {0..17} → no toca [252, 255]. ✅
- `silver_line` ∈ {0, 1} → no toca [252, 255]. ✅

**No hay colisión hoy**, pero **no hay enforcement**. Si alguien agrega un nuevo `green_state = 254`, todo se rompe silenciosamente. Documentar como **contrato** en el código (assertion en debug, comment claro).

### 5.6 [P2] Buffer del Serial5 puede llenarse durante operaciones bloqueantes

**Archivo:** Teensyduino default = **1 KB** para Serial5. RPi envía 8 B × 30 fps = 240 B/s. En una operación bloqueante de 4 s (e.g. zona de rescate), llegan **960 B**. Marginal pero **cerca del límite**.

Tras el fix de §4.1, el buffer se drena casi instantáneo y deja de ser problema. Si después de eso aún se ve overrun, considerar:

```cpp
Serial5.addMemoryForRead(buffer, 4096); // 4 KB
```

---

## 6. Gaps de fail-safe

| # | Gap | Riesgo | Cubierto por |
|---|---|---|---|
| 6.1 | Pi se cuelga → Teensy sigue ejecutando último `speed`/`steer` | **Crítico** — robot se va de pista | Issue [#53](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/53) (heartbeat) |
| 6.2 | Teensy se resetea → Pi no se entera | Alto — robot inerte sin diagnóstico | §5.1 (handshake) |
| 6.3 | Cable serial se desconecta → ambos lados ignoran | **Crítico** | §6.1 + heartbeat bidireccional |
| 6.4 | Sensor I2C se cuelga (BNO055/APDS9960) → loop bloqueado | Alto — Pi no puede comandar parada de emergencia | Issues [#27](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/27) [#61](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/61) [#62](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/62) |
| 6.5 | RPi `ser` con `timeout=None` — `ser.read()` blocking infinito | Medio — sólo si alguien olvida el guard `in_waiting>0` | Nuevo issue (ver §9) |
| 6.6 | Sin contador / log de frames → imposible post-mortem | Medio — coaching ciego | Nuevo issue (ver §9) |
| 6.7 | Sin botón de "STOP de emergencia por software" desde RPi | Medio — sólo el switch físico para | Discusión: ver §7 fase 3 |

### 6.1 Heartbeat — propuesta concreta

Ya hay issue ([#53](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/53)) pero sin diseño. Propuesta:

**Lado Teensy:**
```cpp
elapsedMillis lastFrameMs;
const unsigned long FRAME_TIMEOUT_MS = 500;

void loop() {
    serialEvent5();  // drena
    if (lastFrameMs > FRAME_TIMEOUT_MS) {
        // No hay comando reciente → STOP seguro
        speed = 0;
        steer = 0;
        digitalWrite(LED_ROJO, HIGH);  // diagnóstico visual
    } else {
        digitalWrite(LED_ROJO, LOW);
    }
    // ... resto del loop ...
}

// dentro de serialEvent5(), cuando se completa un frame:
lastFrameMs = 0;
```

**Lado RPi (en main loop):**
```python
last_ack = time.monotonic()
TEENSY_TIMEOUT = 0.5   # 500 ms

# cada vez que recibe byte del Teensy:
last_ack = time.monotonic()

# cada N frames:
if time.monotonic() - last_ack > TEENSY_TIMEOUT:
    print("[ERROR] Teensy no responde — degradando a STOP")
    output = bytes([255, 0, 254, 90, 253, 0, 252, 0])  # speed=0, angle=center
    ser.write(output)
```

---

## 7. Plan de migración por fases

> **Filosofía:** primero los fixes que **no cambian el protocolo** y reducen 80 % del riesgo. Recién después considerar protocolo v2.

### Fase 1 — Fixes mínimos (≤1 semana, sin cambiar protocolo)

| # | Cambio | Issue | Esfuerzo | Riesgo |
|---|---|---|---|---|
| 1 | `serialEvent5()` en `while` (§4.1) | nuevo §9.1 | 15 min | Bajo |
| 2 | Quitar `reset_input_buffer()` post-read (§4.2) | nuevo §9.2 | 15 min | Bajo |
| 3 | Heartbeat Teensy → STOP a 500 ms (§6.1) | [#53](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/53) | 1 h | Medio |
| 4 | Handshake `0xFA` al boot del Teensy (§5.1) | nuevo §9.3 | 30 min | Bajo |
| 5 | Clamp + flush en RPi `_send_frame()` | [#66](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/66) | 30 min | Bajo |
| 6 | RPi `ser` con `timeout=0.05` (§6.5) | nuevo §9.4 | 5 min | Bajo |

**Estado esperado tras Fase 1:** robot **fail-safe** ante caída de Pi y reset de Teensy. Latencia más baja. Sin pérdida silenciosa de comandos.

### Fase 2 — Robustez (1-2 semanas)

| # | Cambio | Issue | Esfuerzo |
|---|---|---|---|
| 7 | Sanity check de rangos en parser Teensy (§5.2) | nuevo §9.5 | 30 min |
| 8 | Logging de frames RX/TX (§6.6) | nuevo §9.6 | 1 h |
| 9 | Drain `serialEvent5` en `runTime/runDistance/runAngle` | [#63](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/63) | 1 h |
| 10 | Documentar contrato de rangos en código (§5.5) | nuevo §9.7 | 30 min |

### Fase 3 — Protocolo v2 (post-mundial, opcional)

Solo si Fase 1 + 2 no son suficientes:

```
[ 0xAA, LEN, OPCODE, payload..., CRC8 ]
```

- `0xAA` sync único.
- `LEN` byte de longitud.
- `OPCODE` distingue tipo de mensaje (frame visión, ack, comando RPi→Teensy, etc.).
- `payload` variable.
- `CRC8` poly 0x07.

**Pros:** robusto, extensible, telemetría bidireccional rica.
**Cons:** rewrite del parser ambos lados. Riesgo de regresión. **No hacer antes del mundial.**

---

## 8. Mediciones pendientes (a medir en banco)

Antes de aplicar Fase 1 conviene **medir el baseline** para tener números:

| Medición | Cómo | Por qué |
|---|---|---|
| Frame rate RPi → Teensy real | `time.time()` antes/después de `ser.write` por 60 s | Validar 30 fps estimados |
| Latencia visión → motor | Toggle GPIO en Pi al detectar evento, GPIO en Teensy al actuar | Saber el caso peor real |
| Bytes pendientes en `Serial5.available()` durante `runTime` | `Serial.print(Serial5.available())` cada 100 ms | Confirmar §5.6 |
| Frames perdidos / corruptos | Contador en cada lado | Justificar (o no) Fase 3 |

---

## 9. Issues nuevos a abrir (cobertura de gaps)

Findings **no cubiertos** por issues existentes:

| ID | Título | Sección | Prioridad |
|---|---|---|---|
| §9.1 | `serialEvent5()` consume 1 byte por llamada — drain incompleto | §4.1 | P1 |
| §9.2 | `reset_input_buffer()` post-read descarta comandos en estado `esperando` | §4.2 | P1 |
| §9.3 | Sin handshake/versión al boot — reset del Teensy desincroniza el sistema | §5.1 | P1 |
| §9.4 | RPi `serial.Serial` sin `timeout` — riesgo de deadlock en `ser.read()` | §6.5 | P1 |
| §9.5 | Sin sanity check de rangos en parser Teensy | §5.2 | P2 |
| §9.6 | Sin logging de frames RX/TX para post-mortem | §6.6 | P2 |
| §9.7 | Documentar contrato de rangos del payload | §5.5 | P2 |

> CRC/Checksum se trata aparte porque toca protocolo (Fase 3).

---

## 10. Checklist pre-mundial (canonical)

Cuando se cierre Fase 1+2, marcar acá:

- [ ] Heartbeat Teensy verificado: desconectar Pi → motores paran en <600 ms.
- [ ] Reset Teensy verificado: apagar/prender Teensy con Pi corriendo → ambos vuelven a `esperando`.
- [ ] Latencia medida visión → motor < 100 ms (caso típico).
- [ ] Frame loss < 0.1 % en 5 minutos de operación continua (con telemetría).
- [ ] Sin warnings en `pio run` lado Teensy.
- [ ] Sin warnings de pyserial en `python -W all Main.py`.
- [ ] Tests automatizados de parser Teensy (`pio test`) corriendo en CI.
- [ ] `testing/TEST_LOG.md` con últimas 10 corridas en banco/pista.

---

## 11. Referencias cruzadas

- [`comunicacion-rpi-teensy.md`](comunicacion-rpi-teensy.md) — descripción base del protocolo.
- [`AUDIT-ACTION-PLAN.md`](../../AUDIT-ACTION-PLAN.md) — plan original.
- [`AI-INSTRUCTIONS.md`](../../AI-INSTRUCTIONS.md) — reglas del repo.
- Issues abiertos sobre comms: [#25](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/25), [#27](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/27), [#53](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/53), [#59](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/59), [#63](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/63), [#66](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/66).

---

*Autor: análisis dirigido por Gustavo Viollaz; auditoría asistida por Claude Code (Opus 4.7) con las skills `rcj-rescue-reviewer`, `teensy-firmware-auditor`, `rpi-vision-auditor` y `rpi-teensy-comms-auditor` definidas en `.claude/skills/`. Fecha: 2026-05-10.*
