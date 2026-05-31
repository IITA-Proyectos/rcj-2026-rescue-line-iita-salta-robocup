# comms-01 — Protocolo serial integral Teensy ↔ RPi (auditoría 2026-05-18)

> **Dominio:** protocolo de comunicación UART entre Raspberry Pi 4B (visión, `Main.py`) y Teensy 4.1 (control, `main.cpp`), **ambos lados**.
> **Alcance:** solo lectura. Documentar el protocolo **tal como está implementado en el checkout actual** (`feature/initialize-testing-log`, contenido idéntico a `main` post-PR #101) y evaluar framing, robustez, saturación, resincronización, heartbeat/handshake y contrato de rangos.
> **Relación con auditorías previas:** este informe **no repite** el [análisis 2026-05-10](../../../../docs/es/analisis-integral-comunicacion-2026-05-10.md) ni los issues #53/#63/#70/#72. Cita cada uno y **agrega análisis nuevo**: estado real del código vs lo que esos issues/doc describen, diagrama de secuencia, presupuesto de bytes/seg vs buffer real del Teensy, y un hallazgo de regresión introducido por el revert `cead75e`.
> **Convención de findings (memoria del coach):** cada finding lleva *riesgo de no arreglarlo* + *riesgo de arreglarlo* + *tiempo estimado*. No son "bugs a fixear" sino **temas a analizar** con el equipo.

---

## 0. TL;DR para el coach

1. **El protocolo está DESINCRONIZADO entre las dos placas en el repo, ahora mismo.** El lado RPi (`Main.py`, HEAD) ya tiene la versión nueva del protocolo (maneja `0xFA`/`0xF9`/`0xF8`/`0xFF`, clamp de bytes, `flush()`, `timeout`, drain del buffer con `while`). El lado Teensy (`main.cpp`, HEAD) fue **revertido** en `cead75e` a una versión vieja que **nunca manda `0xFA`**, sigue leyendo **1 byte por llamada** y sigue **descartando** bytes durante maniobras. Resultado: la RPi está esperando un handshake de boot que el firmware nunca emite, y tiene código de recuperación que jamás se dispara. **Esto es nuevo respecto del doc 2026-05-10** (que describía ambos lados "viejos"). Ver F-1.
2. **No hay heartbeat ni watchdog de RX en ninguno de los dos lados** (sigue abierto #53). Si la Pi se cuelga, el Teensy ejecuta el último `speed`/`steer` para siempre. Es el riesgo P0 de comms para Incheon. Ver F-2.
3. **El presupuesto de buffer está MUCHO más ajustado de lo que dice el doc 2026-05-10.** Ese doc asumió RX buffer de **1 KB**; el default real de Teensyduino para `Serial5` en Teensy 4.x es **64 bytes**. Con maniobras bloqueantes de varios segundos y 8 B × 30 fps entrando, el buffer **se desborda y se pierden frames enteros**, además de desalinear el framing. Ver F-3 y §6.
4. El framing es **stateful, sin length ni CRC, y con un parser frágil** ante pérdida del primer byte de sync; se resincroniza "de casualidad" cada frame nuevo, pero con corrupción puede mapear un payload al campo equivocado sin que nadie se entere. Ver F-4, F-5.

---

## 1. El protocolo real, tal como está implementado

### 1.1 Capa física

| Parámetro | RPi (`Main.py:67`) | Teensy (`main.cpp:753`) | Estado |
|---|---|---|---|
| Puerto | `/dev/serial0` | `Serial5` (pins 20/21) | OK |
| Baud | `115200` | `115200` | **Coinciden** ✅ |
| Formato | 8-N-1 (default pyserial) | 8-N-1 (default Teensyduino) | OK |
| `timeout` lectura | `0.05 s` (`SERIAL_TIMEOUT_S`) | n/a (lee con guard `available()>0`) | OK |
| `write_timeout` | `0.05 s` | n/a | OK |

> ⚠️ **Nota de toolchain:** el test `software/teensy/firmware/test/comms/serialReceive.cpp:21` abre `Serial5` a **57600**, no a 115200. Es solo un test de banco, pero si alguien lo flashea para "probar comms" va a ver basura y perder tiempo. Mencionar al equipo (Benjamin, banco de pruebas) — **no es bug de producción**.

### 1.2 Frame de datos — dirección RPi → Teensy

Definido en `Main.py:26-29` y construido en `send_frame()` (`Main.py:98-116`). **8 bytes, posicional, con sync byte intercalado antes de cada campo:**

```
índice:   0     1      2     3      4     5             6     7
byte:   0xFF  speed  0xFE  angle  0xFD  green_state  0xFC  silver_line
        SYNC         SYNC         SYNC               SYNC
```

| Sync byte | Constante RPi | Campo que precede | Rango contractual (RPi) | Cómo lo arma la RPi |
|---|---|---|---|---|
| `0xFF` (255) | `SYNC_SPEED` | `speed` | `[0,100]` | `clamp_byte(speed)` |
| `0xFE` (254) | `SYNC_ANGLE` | `angle` | `[0,180]` | `clamp_byte(angle + 90)` |
| `0xFD` (253) | `SYNC_GREEN_STATE` | `green_state` | `0..17` | `clamp_byte(green_state)` |
| `0xFC` (252) | `SYNC_SILVER_LINE` | `silver_line` | `{0,1}` | `clamp_byte(int(bool(...)))` |

- `speed`/`angle` se interpretan en el Teensy en `serialEvent5()` (`main.cpp:397-404`):
  - `speed = (double)data / 100 * 100;` → identidad, rango efectivo 0..255 (sin clamp).
  - `steer = ((double)data - 90) / 90;` → mapea byte 0..180 a `steer ∈ [-1, +1]` (con 90 = recto).
  - `green_state = data;` y `silver_line = data;` directos, sin validación.

> **Asimetría de clamp:** la RPi clampa a `[0,255]` con `clamp_byte` (no a los rangos contractuales `[0,100]`/`[0,180]`), y el Teensy **no clampa nada**. Es decir: el "contrato de rangos" está **documentado en `Main.py` pero no enforced en ninguno de los dos lados** en los límites reales (100/180). Coincide con lo que #72/doc §5.2 llaman "sin sanity check"; lo **nuevo** es que la RPi *parece* validar (`clamp_byte`) pero clampa al límite equivocado (255, no 100/180). Ver F-5.

### 1.3 Mensajes de control — dirección Teensy → RPi

**1 byte suelto cada uno, sin frame, sin sync, aperiódicos.** Emitidos con `Serial5.write(...)` en `main.cpp`:

| Byte | Constante RPi (`Main.py:31-34`) | Emite el Teensy en… | Significado | Efecto en RPi (`handle_control_byte`) |
|---|---|---|---|---|
| `0xFA` (250) | `TEENSY_BOOT` | **NUNCA** (ver F-1) | "Teensy reseteó" | `estado='esperando'` |
| `0xF9` (249) | `TEENSY_READY` | `main.cpp:862` (fin de `startUp`) | "Listo → arrancá línea" | si `esperando`→`linea` |
| `0xF8` (248) | `TEENSY_RESCATE_DONE` | `main.cpp:1191` (`ball_counter>=3`) | "Suficientes pelotas" | si `rescate`→`depositar` |
| `0xFF` (255) | `TEENSY_STOP` | `main.cpp:427,453,559,582,822` (switch off / kill) | "Stop / standby" | `estado='esperando'` |

**Hallazgos de framing en esta dirección (nuevos / ampliados):**

- **`0xFF` está sobrecargado en ambas direcciones.** Es `SYNC_SPEED` (RPi→Teensy) **y** `TEENSY_STOP` (Teensy→RPi). Como son enlaces físicos distintos (TX/RX separados) no colisionan en el cable, pero es el **mismo número mágico con dos semánticas opuestas**. Cualquiera que lea el código se confunde, y un loopback accidental (eco) auto-dispara `esperando`. Deuda de diseño, no falla activa.
- **`0xFA` (TEENSY_BOOT) = 250** y **`0xF9`=249, `0xF8`=248** caen dentro del rango que `green_state` podría alcanzar si alguien rompe el contrato (hoy `green_state` llega hasta 17, ok). Pero **no hay barrera**: estos bytes de control "uplink" comparten espacio numérico con sync bytes "downlink". Mismo problema que doc §5.5, **sin resolver**.
- En `runTime`/`runDistance`, cuando se detecta el switch apagado, el Teensy hace `Serial5.clear()` (limpia su RX) **y** `Serial5.write(255)` (avisa stop). Es la única secuencia de "limpieza" intencional del canal. Está bien pensada, pero `Serial5.clear()` también **descarta frames de control válidos** que la RPi pudiera estar mandando.

### 1.4 Quién parsea, y cuándo (clave para §5–6)

`serialEvent5()` (`main.cpp:383`) es el parser. Tiene **doble naturaleza**:

1. Es el **callback automático** del core Teensyduino (se llama solo entre iteraciones de `loop()` cuando hay datos en `Serial5`).
2. Se llama **manualmente** en `main.cpp:599, 1048, 1056, 1081, 1090, 1116, 1133, 1193` (y comentado en 950/965).

Esto importa muchísimo: durante el **line-tracking puro** (`case 7`, `main.cpp:1062-1077`) **no** se llama `serialEvent5()` dentro del `while`. El `while (rutina=="linea" && digitalRead(32)==0)` (`main.cpp:884-1128`) **no retorna a `loop()`**, así que el callback automático **tampoco corre**. La actualización de `speed`/`steer`/`green_state` depende de que la ejecución entre a un `case` que llame `serialEvent5()` o que el while termine. Ver F-6.

---

## 2. Diagrama de secuencia (estado real del checkout)

### 2.1 Arranque feliz (lo que SÍ funciona hoy)

```
RPi (Main.py)                         Teensy (main.cpp)
  | estado='esperando'                   | setup(): init sensores, Serial5.begin(115200)
  | (loop esperando, lee 1 byte)         | loop(): switch ON (digitalRead(32)==0) y !startUp
  |                                       |   runTime back/fwd 300ms, startUp=true
  |        <----- 0xF9 (249) ------------ |   Serial5.write(249)   [main.cpp:862]
  | handle_control_byte(0xF9)             |
  | estado: 'esperando'->'linea'          | entra while(rutina=="linea")
  |                                       |
  | --- 8B frame [FF,sp,FE,an,FD,gr,FC,si]-->  (buffer Serial5)
  |     (cada iteración de visión)        |   serialEvent5() parsea de a 1 byte
  |        <----- (nada periódico) ------ |   ejecuta robot.steer(speed,FWD,steer)
```

### 2.2 Transición a rescate y depósito

```
RPi                                    Teensy
  | detecta silver_line=True             |
  | send_frame(...,silver_line=1)        | serialEvent5(): silver_line=1
  | estado='rescate'  [Main.py:818-819]  |   case 2 -> rutina="rescate"
  | modo_rescate() (YOLO loop)           |   while(rutina=="rescate")
  | manda green_state 6/7/8/9 según clase|   recolecta/deposita (maniobras BLOQUEANTES)
  |                                       |   cuando ball_counter>=3:
  |        <----- 0xF8 (248) ------------ |   Serial5.write(248)  [main.cpp:1191]
  | estado: 'rescate'->'depositar'        |
```

### 2.3 El escenario ROTO: reset del Teensy con la Pi corriendo (F-1)

```
RPi                                    Teensy
  | estado='linea', mandando frames      | <RESET / brown-out / cuelgue+reboot>
  |                                       | setup() corre de nuevo...
  | --- 8B frame ----------------------->  |   ...pero startUp=false otra vez
  | (sigue en 'linea', nunca recibe nada) |   espera switch para mandar 0xF9
  | ESPERA 0xFA que NUNCA llega  <---X--- |   firmware NO emite 0xFA  [F-1]
  | robot inerte; RPi cree que todo va bien
```

> La RPi **tiene el manejador** `if data == TEENSY_BOOT: estado='esperando'` (`Main.py:156-159`), pero como el firmware nunca manda `0xFA`, esa rama es **código muerto**. Exactamente el síntoma que #72 quería evitar — pero hoy está **medio implementado** (RPi sí, Teensy no). Esto es **peor que no implementarlo en ningún lado**, porque da falsa sensación de cobertura.

---

## 3. Presupuesto de bytes/seg vs buffer (análisis nuevo)

### 3.1 Tasas

- Capacidad del enlace: 115200 baud / 10 bits por byte (8-N-1) = **11 520 B/s**.
- Frame = **8 B**. Frecuencia de envío RPi = FPS de visión.
  - Línea (`Main.py:711-832`): 1 frame por iteración. ~25-40 fps → **200–320 B/s**.
  - Rescate (`modo_rescate`, `Main.py:560-679`): 1 frame por item de `result_q`, atado a inferencia YOLO/centroid → estimado 8–20 fps → **64–160 B/s**.
- Uplink Teensy→RPi: aperiódico, despreciable (<10 B/s).

→ **Utilización del canal ≈ 2–3 %.** El ancho de banda **no** es el problema (coincide con doc §3). El problema es el **buffer del receptor durante bloqueos**, y acá el doc 2026-05-10 se equivocó en el número.

### 3.2 Buffer real del Teensy (corrección al doc §5.6)

El doc 2026-05-10 §5.6 afirma *"Teensyduino default = 1 KB para Serial5"*. **Eso es incorrecto.** El default de Teensyduino (`HardwareSerial`) para Teensy 4.x es **`SERIAL5_RX_BUFFER_SIZE = 64` bytes** de ring software (más un FIFO hardware chico). No hay `addMemoryForRead()` en `main.cpp` (verificado: 0 ocurrencias). Por lo tanto el buffer de recepción es **~64 bytes, no 1024**.

### 3.3 Tiempo hasta overflow durante una maniobra bloqueante

A 30 fps la RPi mete 8 B cada ~33 ms = **240 B/s = 1 byte cada ~4,2 ms**. Con buffer de 64 B y el parser **sin drenar** (porque estamos dentro de un `runTime`/`runDistance` que NO llama `serialEvent5()` — ver #63):

```
tiempo_a_overflow ≈ 64 B / 240 B/s ≈ 0,27 s
```

**El buffer se llena en ~270 ms.** Muchas maniobras del rescate son de **1–3 segundos bloqueantes** (`nonBlockingDelay(1000..1400)`, `runTime(0,FORWARD,0,3000)`, etc.). Durante esas ventanas:

1. El RX ring de 64 B se llena en ~0,27 s.
2. Los bytes siguientes **se descartan en hardware** (overrun).
3. Cuando termina la maniobra y `serialEvent5()` vuelve a correr, **arranca a parsear desde una posición arbitraria** del frame → el primer byte que lee puede ser un `angle` interpretado como `speed`, etc. → **desalineación de campos** hasta el próximo `0xFF`.

> Esto es **cualitativamente distinto** de lo que decía el doc ("960 B en 4 s, marginal, cerca del límite"). Con 64 B reales **no es marginal: es overflow garantizado en cualquier bloqueo >0,3 s**. Es el hallazgo cuantitativo nuevo más importante de comms. Ver F-3.

> ⚠️ Matiz importante: `nonBlockingDelay()` (`main.cpp:592-601`) **sí** llama `serialEvent5()` y drena, así que las maniobras del `while(rutina=="rescate")` que usan `nonBlockingDelay` están parcialmente cubiertas. Pero `runTime`/`runDistance`/`runAngle` **no** drenan (solo `Serial5.read()` y descartan — #63), y esas son las que rompen el budget. La mezcla de ambos patrones en el mismo flujo hace el comportamiento **impredecible** según por qué rama caiga el robot.

---

## 4. Evaluación por eje

### 4.1 Framing
- **Posicional con sync intercalado**, sin length, sin CRC, sin terminador. Robusto solo si el primer `0xFF` llega intacto y el stream no se desalinea.
- El sync intercalado (un sync byte por campo, no solo al inicio) es en realidad una **decisión defensiva buena**: permite re-anclar campo por campo. Pero el parser **no la aprovecha bien** (ver 4.4).

### 4.2 Robustez ante pérdida/corrupción
- **Pérdida de bytes** (overrun de buffer): el parser se desalinea y mapea payloads a campos equivocados hasta el próximo sync. Sin CRC, **no hay detección**.
- **Corrupción de 1 bit**: silenciosa. Un flip en `green_state` (7→5) o en `speed` cambia comportamiento sin alarma. El rack de competencia tiene ruido de motores DC + servos. Mismo riesgo que doc §5.3, **sin resolver**.
- **Caso especialmente feo**: si un payload se corrompe **a un valor de sync** (p.ej. `speed` byte se vuelve `0xFE`), el parser cree que empezó el campo `angle` y se desalinea medio frame. Como `speed∈[0,100]` hoy no alcanza 252-255, esto solo pasa por corrupción, pero **no hay defensa**.

### 4.3 Saturación bajo maniobras bloqueantes
- Cubierto en §3.3: **overflow en ~0,27 s** en `runTime`/`runDistance`/`runAngle`. Parcialmente mitigado solo donde se usa `nonBlockingDelay`. **El peor caso es real y frecuente en el rescate.**

### 4.4 Resincronización
- El único mecanismo de resync es **implícito**: el próximo `0xFF` re-arma `serial5state=0`. No hay timeout de frame, ni "si pasaron N ms sin sync, descartar parcial".
- **Falla concreta:** si el byte perdido es un **sync** (`0xFF`), el siguiente payload `speed` se interpreta como sea que esté `serial5state`. Como el parser es una cadena `if/else if`, un payload que **coincide numéricamente** con 252-255 se trata como sync aunque sea dato. Hoy el contrato de rangos lo evita por suerte, no por diseño.
- No hay **máquina de estados de frame completa** (esperar exactamente 8 bytes, validar las 4 marcas, recién entonces commitear). Se commitea **campo por campo a globales en vivo**, así que un frame a medio parsear ya movió el robot con datos viejos+nuevos mezclados.

### 4.5 Heartbeat / handshake
- **Heartbeat: inexistente en ambos lados.** Sigue 100% abierto #53. No hay `lastFrameMs` en el Teensy ni timeout de ACK en la RPi. Si la Pi muere, el robot sigue con el último `speed`/`steer`. **Riesgo P0 de comms.** Ver F-2.
- **Handshake de boot: medio implementado y por lo tanto roto.** RPi maneja `0xFA`; Teensy no lo emite (F-1). El handshake "real" que existe hoy es el `0xF9` post-`startUp`, que **solo funciona si la RPi estaba en `esperando` cuando el Teensy arranca**. Si el orden de boot es Teensy-primero o hay reset en caliente, se pierde.

### 4.6 Contrato de rangos
- Documentado en `Main.py:19-29` pero **no enforced**: la RPi clampa a 255 (no a 100/180) y el Teensy no clampa. Ver F-5. El contrato vive en un comentario, no en código ejecutable.

---

## 5. Findings (formato riesgo/riesgo/tiempo)

> Recordatorio: estos son **temas a analizar con el equipo**, no órdenes de cambio. La regla de oro del repo (CLAUDE.md #4) es no romper lo que los chicos ya validaron en banco.

### F-1 — [P0] El protocolo está desincronizado en el repo: RPi nuevo, Teensy revertido. `0xFA` nunca se emite.
- **Qué:** `Main.py` (HEAD) implementa el protocolo nuevo (control bytes 0xFA/0xF9/0xF8/0xFF, `clamp_byte`, `flush`, `timeout`, drain con `while`). `main.cpp` (HEAD) fue revertido en `cead75e` ("error de libreria claw.cpp", `-181 líneas`) a una versión que **no manda `0xFA`**, parsea **1 byte/llamada** y **descarta** bytes en maniobras. El manejador `TEENSY_BOOT` de la RPi (`Main.py:156-159`) es **código muerto**.
- **Evidencia:** `git show 5bac4a5:...main.cpp | grep 0xFA` → vacío (ni la versión "buena" lo tenía). `git show HEAD:...main.cpp` serialEvent5 sigue `if`. `Main.py` HEAD tiene `TEENSY_BOOT=b'\xfa'`.
- **Riesgo de NO analizarlo:** reset/brown-out del Teensy en pista (probable con motores DC y baterías al límite) → **robot inerte sin diagnóstico**, corrida perdida. La RPi *cree* que está cubierta. Exactamente el escenario de #72, hoy **parcialmente implementado = falsa seguridad**.
- **Riesgo de SÍ analizarlo/arreglarlo:** agregar el emit de `0xFA` en `setup()` del Teensy es de bajo riesgo, pero **tocar `setup()`/boot toca el arranque validado**; hay que reprobar la secuencia de encendido completa en banco. Riesgo medio-bajo.
- **Tiempo:** diagnóstico ya hecho. Implementar emit `0xFA` (cerrar #72 lado Teensy) + verificación en banco: **~1–2 h**.

### F-2 — [P0] Sin heartbeat / watchdog de RX. La Pi se cuelga y el robot no para.
- **Qué:** ni el Teensy degrada a STOP por ausencia de frames, ni la RPi detecta ausencia de uplink. Sigue abierto #53 (sin diseño implementado).
- **Evidencia:** 0 ocurrencias de `lastFrameMs`/`FRAME_TIMEOUT`/timeout-de-RX en `main.cpp`; en `Main.py` no hay watchdog de `last_ack`.
- **Riesgo de NO:** cuelgue de la Pi (OpenCV/cámara/USB) en cualquier momento → el Teensy repite el último `robot.steer(speed,FWD,steer)` indefinidamente → **robot se va de pista**. Riesgo de seguridad y de descalificación. Es **el** gap fail-safe de comms.
- **Riesgo de SÍ:** un timeout mal calibrado puede **frenar el robot por falsos negativos** en bloqueos legítimos (p.ej. inferencia lenta) → pérdida de tiempo en pista. Calibrar el umbral (≥500 ms, como propone doc §6.1) y probar exhaustivamente. Riesgo medio.
- **Tiempo:** diseño ya está en doc §6.1. Implementar ambos lados + calibrar en banco: **~3–4 h**.

### F-3 — [P1] Overflow de buffer en ~0,27 s durante `runTime`/`runDistance`/`runAngle`. (Corrige doc §5.6.)
- **Qué:** RX ring real del `Serial5` = **64 B**, no 1 KB. A 240 B/s y sin drenar dentro de las maniobras bloqueantes de movimiento, el buffer **desborda en ~270 ms** y desalinea el framing. Distinto y peor que lo estimado en el doc previo.
- **Evidencia:** `addMemoryForRead` ausente en `main.cpp`; `runTime`/`runDistance` solo hacen `Serial5.read()` y descartan (no `serialEvent5()`).
- **Riesgo de NO:** durante el rescate (maniobras de 1–3 s) se pierden frames y, al volver, el parser puede mapear campos cruzados → comandos espurios (`speed`/`steer` equivocados) justo en la fase de mayor puntaje. Errático e intermitente.
- **Riesgo de SÍ:** dos caminos: (a) drenar con `serialEvent5()` dentro de las maniobras (es #63 + #70) — riesgo medio porque `serialEvent5` puede pisar `speed`/`steer` globales en medio de una maniobra de valores fijos; (b) ampliar buffer con `addMemoryForRead(buf,512)` — riesgo bajo pero solo **pospone** el overflow (no lo elimina si la maniobra es larga). Idealmente ambos.
- **Tiempo:** (b) buffer grande: **~15 min**. (a) drain correcto: enredado con #63/#70, **~1–2 h** + banco.

### F-4 — [P1] Sin CRC/checksum ni length: corrupción y desalineación silenciosas.
- **Qué:** frame sin integridad ni longitud. Un bit flip o un overrun no se detectan. (Doc §5.3, sin resolver; lo agrego para cerrar el panorama integral, no para duplicar.)
- **Riesgo de NO:** en el ambiente ruidoso del rack, un `green_state` o `silver_line` corrupto dispara una rutina equivocada (girar 180°, entrar a rescate de más) sin alarma.
- **Riesgo de SÍ:** agregar 1 byte XOR/CRC8 obliga a **cambiar el parser de los dos lados** → riesgo de regresión en un sistema validado. Es cambio de protocolo (Fase 3 del doc). **No recomendado antes de Incheon** salvo que se vea corrupción medible.
- **Tiempo:** XOR simple ambos lados + banco: **~2–3 h**; CRC8 con tabla: **~4 h**. Mejor post-mundial.

### F-5 — [P2] Contrato de rangos no enforced; clamp de la RPi al límite equivocado.
- **Qué:** el contrato `[0,100]/[0,180]/0..17/{0,1}` está en comentario (`Main.py:19-29`) pero `clamp_byte` clampa a `[0,255]`, no a 100/180; el Teensy no clampa. Un `green_state=254` por bug rompería el framing.
- **Riesgo de NO:** un bug futuro de visión que mande un valor fuera de rango se traduce en sync byte falso → desalineación. Hoy no pasa, pero no hay red.
- **Riesgo de SÍ:** muy bajo (agregar `min/max` reales en `send_frame` + `if (data>100) return;` en el parser). Podría enmascarar un bug de visión si solo se clampa sin loguear.
- **Tiempo:** **~30 min** ambos lados.

### F-6 — [P2] Line-tracking puro no drena serial: la actualización de `speed`/`steer` depende de a qué `case` entre.
- **Qué:** el `while(rutina=="linea")` no retorna a `loop()`, y `case 7` (line-track) no llama `serialEvent5()`. El callback automático del core **no corre dentro de ese while**. Solo cases 5/6/12/14 parsean. Además `get_color()` (`main.cpp:336-339`) bloquea con `while(!colorDataReady()) delay(5)` cada iteración del while de línea.
- **Riesgo de NO:** latencia variable y a veces alta entre que la RPi manda un `angle`/`green_state` nuevo y el Teensy lo aplica, **en la fase de seguir línea** (la más frecuente). Sumado a F-3, explica "lag" reportable en banco.
- **Riesgo de SÍ:** meter `serialEvent5()` en `case 7` es barato, pero cambia el timing del lazo de control de línea ya tuneado por los chicos → puede requerir re-tuneo de velocidades/steer. Riesgo medio (regla de oro #4).
- **Tiempo:** **~30 min** + re-validación de seguimiento de línea en pista.

---

## 6. Oportunidades de mejora priorizadas (qué tocar primero rumbo a Incheon)

| Prio | Acción | Finding | Issue relacionado | Costo | Beneficio |
|---|---|---|---|---|---|
| 1 | **Re-sincronizar las dos placas**: emitir `0xFA` en `setup()` del Teensy (cerrar lado faltante de #72) **o** decidir explícitamente quitar el manejador de la RPi. No dejar el medio-implementado. | F-1 | #72 | ~1–2 h | Elimina el "robot inerte sin diagnóstico" y el código muerto. |
| 2 | **Heartbeat bidireccional con STOP fail-safe** (Teensy: `lastFrameMs>500ms`→stop+LED; RPi: timeout de uplink→manda frame de STOP). | F-2 | #53 | ~3–4 h | Cierra el gap de seguridad P0 de comms. |
| 3 | **Ampliar RX buffer** `Serial5.addMemoryForRead(buf,512)` (parche barato) **y** drenar con `serialEvent5()` dentro de `runTime`/`runDistance`/`runAngle`. | F-3 | #63, #70 | ~15 min + ~1–2 h | Mata el overflow de 0,27 s; baja latencia visión→motor 30–80 ms (estimado doc §4.1). |
| 4 | **Drenar serial en `case 7`** (line-track) o reestructurar el `while` para volver a `loop()`. | F-6 | (deuda, parte de #63) | ~30 min + pista | Latencia de línea consistente. |
| 5 | **Enforce contrato de rangos** con clamp real + log. | F-5 | doc §5.2 | ~30 min | Red de seguridad ante bugs de visión. |
| 6 | **(Post-mundial)** XOR/CRC8 + length. Solo si se mide corrupción. | F-4 | doc §5.3 / Fase 3 | ~2–4 h | Integridad real; alto riesgo de regresión, **no antes de Incheon**. |

**Secuencia recomendada para banco (Benjamin):** medir baseline primero (frames/s reales, `Serial5.available()` durante un `runTime(0,...,3000)`, frames perdidos) — son las mediciones pendientes del doc §8, **todavía sin hacer**. Sin ese baseline, el equipo no puede saber si F-3 ya los está mordiendo hoy.

---

## 7. Relación explícita con issues citados (qué agrega este informe)

- **#53 (heartbeat):** sigue **sin implementar en ningún lado**. Confirmo el gap y lo elevo a **P0 de comms** con el budget de §3 (un cuelgue de Pi deja `robot.steer(last_speed,...)` activo para siempre). Nuevo: el diseño de doc §6.1 sigue siendo válido y aplicable.
- **#63 (runTime/runDistance descartan bytes):** **sin arreglar** en HEAD (verificado líneas 418-422, 553-556, 576-579: solo `Serial5.read()` + `Serial.print`). Nuevo: lo conecto con el **overflow de 0,27 s** (§3.3) — el descarte no es solo "latencia", es **pérdida de frame + desalineación** por buffer de 64 B.
- **#70 (serialEvent5 lee 1 byte/llamada):** **sin arreglar** en HEAD (`serialEvent5` sigue `if`). Nuevo: cuantifico que con el `while` de línea sin drenar (F-6) el problema es peor de lo descrito, porque ni siquiera el callback automático corre durante line-track.
- **#72 (handshake de boot):** **medio implementado** — y eso es el hallazgo F-1, el más relevante. La RPi ya tiene el lado del handshake (no estaba así en el doc 2026-05-10); el Teensy fue revertido y nunca emite `0xFA`. El issue se puede cerrar **solo agregando el emit en el Teensy**, no hay que tocar la RPi.
- **Corrección al doc 2026-05-10 §5.6:** el RX buffer de `Serial5` es **64 B**, no 1 KB. Cambia la conclusión de "marginal" a "overflow garantizado en bloqueos >0,3 s".

---

## 8. Notas de método y límites

- Análisis **estático** sobre el checkout `feature/initialize-testing-log` (== `main` post-#101). No se ejecutó hardware. Todas las tasas (fps, latencias) son estimaciones de oficina salvo las exactas del enlace (11 520 B/s) y el frame (8 B).
- El tamaño de buffer (64 B) es el **default documentado** de Teensyduino para `Serial5` en Teensy 4.x; conviene **confirmarlo en banco** imprimiendo o forzando overflow, porque versiones del core pueden variar.
- No se tocó código fuente (regla del encargo). No se crearon issues ni se comentó en GitHub (solo lectura con `gh`).
- El test `serialReceive.cpp` a 57600 baud es de banco, no de producción; se menciona solo para evitar confusión del equipo.

---

*Autor: auditoría asistida por Claude Code (Opus 4.8, 1M) para Gustavo Viollaz. Dominio: protocolo serial integral RPi↔Teensy. Fecha: 2026-05-18. Complementa —no reemplaza— `docs/es/analisis-integral-comunicacion-2026-05-10.md` y los issues #53/#63/#70/#72.*
