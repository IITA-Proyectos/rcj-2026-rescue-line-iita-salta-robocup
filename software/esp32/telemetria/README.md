# Telemetría RescueBot — ESP32-MINI (AP WiFi + GUI)

Telemetría en vivo de **todos** los valores de control del Teensy, servida por la
ESP32-MINI como Access Point WiFi. Te conectás con el celular o la laptop y ves un
dashboard profesional con sensores, enlace con la Raspberry y máquina de estados —
sin cables, sin depender del monitor serie.

> **Es 100% no intrusiva.** No cambia el comportamiento del robot: el Teensy
> escribe una línea JSON por Serial8 a 10 Hz y, si el buffer TX no tiene lugar,
> **descarta el frame** (el control nunca se frena). Se activa/desactiva con una
> sola flag (`#define TELEMETRIA` en `main.cpp`).

---

## 1. Arquitectura

```
  ┌─────────────┐  Serial8 (UART 115200, 3.3V)   ┌──────────────┐   WiFi AP    ┌────────────┐
  │   TEENSY    │  TX8 pin35 ─────────────────►   │  ESP32-MINI  │  192.168.4.1 │  Celular / │
  │   4.1       │  RX8 pin34 ◄───(opcional)────   │  (la "C3")   │ ◄──────────► │  Laptop    │
  │ enviarTele- │  1 línea JSON/frame (~10 Hz)    │ "tubo tonto" │   HTTP/GUI   │ (navegador)│
  │ metria()    │                                 │ AP + WebSrv  │              │            │
  └─────────────┘                                 └──────────────┘              └────────────┘
```

- **Teensy** arma el JSON con todos los globals (`enviarTelemetria()` en
  [`main.cpp`](../../teensy/firmware/src/main.cpp)) y lo manda por Serial8.
- **ESP32** solo **reenvía**: lee la última línea completa y la publica en `/data`.
  No interpreta el esquema → cero duplicación.
- **Navegador** (GUI) consulta `/data` cada 100 ms y renderiza todo.

---

## 2. Cableado

Ya existe del ex-SuperTema. 3.3 V ambos lados, **sin level shifter**, GND común.

| Teensy 4.1        | ESP32-MINI          | Obligatorio |
|-------------------|---------------------|-------------|
| TX8 (pin **35**)  | `UART_RX_PIN` (GPIO4) | **Sí** (es el dato) |
| RX8 (pin **34**)  | `UART_TX_PIN` (GPIO5) | No (telemetría no lo usa) |
| GND               | GND                 | Sí |
| 5 V del regulador | 5V / VIN            | Sí |

Los pines GPIO de la ESP32 se definen en [`src/main.cpp`](src/main.cpp)
(`UART_RX_PIN` / `UART_TX_PIN`). Si tu módulo no es un ESP32-C3 Super Mini,
elegí dos GPIOs libres y actualizá esos defines.

---

## 3. Cómo se usa

1. **Flashear la ESP32** (ver §4).
2. Encender el robot (el Teensy ya manda telemetría con `TELEMETRIA 1`).
3. En el celular/laptop, conectarse al WiFi:
   - **SSID:** `RescueBot-Telemetria`
   - **Clave:** `rescate2026`
4. Abrir el navegador en **http://192.168.4.1/**

El dashboard muestra: enlace RPi (velocidad/steer/green_state/silver/contadores),
sensor de color APDS9960 (R/G/B/C + color detectado), 3 ultrasonidos (con radar),
2 ToF, IMU BNO055 (compás yaw + pitch + roll), 4 encoders, la máquina de estados
completa (rutina, action, rescateState, pelotas, depósitos, verdes, flags de
evacuación…), E/S digital (switch, finales de carrera, relay, buzzer, LED) y la garra.

### Herramientas de calibración/diagnóstico (en la misma GUI)

**🎨 Calibración de Color** — para actualizar los umbrales de `classify_color` sin
la terminal USB. Muestra en vivo R/G/B/C y los ratios R/C, R/G, R/B, B-G (los mismos
valores filtrados que usa el robot). Poné una superficie bajo el sensor **con el
robot en idle** (switch off), elegí qué es (`Plateado`/`Negro`/…) y tocá **«Capturar
muestra»**. Repetí con varias superficies y tocá **«Copiar todo (para IA)»**: copia
un texto listo para pegarle a una IA (con el prompt + todas las lecturas etiquetadas)
y pedirle cómo quedarían los umbrales. Es exactamente el flujo de calibración manual,
pero desde el celular.

**🟢 Diagnóstico de Verdes** — para el problema de los `green_state` (1/2/3). El Teensy
cuenta, por tipo: cuántos verdes **llegaron** de la RPi, cuántos **giró** (el re-chequeo
confirmó) y cuántos **mató el re-chequeo** (el `if(green_state==N)` después del
`runTime(...,800)` falló porque el verde ya se apagó/cambió). El log en vivo muestra
cada evento: `Verde IZQ → GIRÓ ✓` o `Verde IZQ → MATADO ✗ (re-check gs=0)`. Si ves
muchos «matados» con `gs=0`, el verde llega bien pero se pierde durante el avance de
800 ms → ahí está el bug a atacar.

> Podés ver la GUI **sin robot**: abrí [`gui/dashboard.html`](gui/dashboard.html)
> directo en un navegador. Entra en **modo demo** con datos sintéticos.

---

## 4. Build y flasheo

Requiere [PlatformIO](https://platformio.org/). Board por defecto: **ESP32-C3 Super Mini**.

```bash
cd software/esp32/telemetria
pio run                       # compila
pio run --target upload       # flashea (con la ESP32 conectada por USB)
pio device monitor            # logs (muestra la IP del AP)
```

Si tu módulo es otro, descomentá el `[env:...]` correspondiente en
[`platformio.ini`](platformio.ini) y compilá con `pio run -e <env>`.

### Editar la GUI

La GUI vive en [`gui/dashboard.html`](gui/dashboard.html) (autónoma, sin librerías
externas). Está **embebida** en el firmware en `src/web_ui.h`. Tras editar el HTML,
regenerá el header y recompilá:

```bash
python tools/gen_web_ui.py
pio run --target upload
```

---

## 5. Esquema de datos (una línea JSON por frame)

El Teensy emite algo así (10 Hz, terminado en `\n`):

```json
{"t":123456,
 "rpi":{"speed":45,"steer":-0.320,"green":1,"silver":0,"rxb":2691,"rxf":468,"st":3},
 "col":{"d":"Blanco","r":570,"g":1010,"b":1025,"c":2685,"ok":1},
 "us":{"f":60,"l":45,"r":12},
 "tof":{"l":520,"r":480},
 "imu":{"yaw":180.4,"pit":-2.1,"rol":0.5,"cen":180.0},
 "enc":{"fl":10598,"fr":10846,"bl":10101,"br":10730},
 "fsm":{"rut":"linea","act":7,"task":1,"up":1,"resc":0,"balls":1,"dep":0,"verd":1,
        "evi":0,"evs":0,"slatch":0,"pared":"left","lado":"derecha","ran":2},
 "io":{"sw":0,"fcl":0,"fcr":0,"rel":0,"buz":0,"led":1},
 "claw":{"busy":0},
 "grn":{"rx":[0,3,1,0],"act":[0,2,1,0],"kill":[0,1,0,0],"lt":1,"age":491,"lrc":0}}
```

En `grn`, los arrays están indexados por tipo de verde: `[_, izq(1), der(2), doble(3)]`
(el índice 0 no se usa). `rx`=recibidos, `act`=giró, `kill`=matado por re-chequeo;
`lt`=último verde recibido, `age`=ms desde ese último (−1 = nunca), `lrc`=green_state
en el último re-chequeo.

| Grupo | Clave | Significado | Fuente en `main.cpp` |
|---|---|---|---|
| `rpi` | `speed`,`steer` | velocidad/giro comandados por la RPi | `speed`, `steer` |
| | `green`,`silver` | estado de cámara / línea plateada | `green_state`, `silver_line` |
| | `rxb`,`rxf`,`st` | bytes/frames recibidos, estado del parser | `serial_bytes_rx`, `serial_frames_rx`, `serial5state` |
| `col` | `d`,`r`,`g`,`b`,`c`,`ok` | color detectado, RGBC filtrado, sensor OK | APDS9960 + `get_filtered_color()` |
| `us` | `f`,`l`,`r` | ultrasonidos frente/izq/der (cm) | `front/left/right_distance` |
| `tof` | `l`,`r` | ToF izq/der (mm) | `distance_left/right_tof` |
| `imu` | `yaw`,`pit`,`rol`,`cen` | BNO055 (grados) + ref `centrar` | lectura fresca del BNO |
| `enc` | `fl`,`fr`,`bl`,`br` | contadores de encoder | `fl/fr/bl/br.pulseCount` |
| `fsm` | (varias) | rutina, action, rescateState, contadores, flags | globals de estado |
| `io` | `sw`,`fcl`,`fcr`,`rel`,`buz`,`led` | entradas/salidas digitales | `digitalRead(...)` |
| `claw` | `busy` | garra ejecutando maniobra | `claw.busy()` |
| `grn` | `rx`,`act`,`kill` | verdes recibidos / girados / matados por re-chequeo, por tipo | contadores `g_rx/g_act/g_kill` |
| | `lt`,`age`,`lrc` | último verde, ms desde entonces, green_state en el re-chequeo | `telemGreenRx/Resultado` |

> **Agregar un valor nuevo:** sumá el campo en el `snprintf` de `enviarTelemetria()`
> (Teensy) y leélo en `render()` de `gui/dashboard.html` (JS). La ESP32 no se toca.

---

## 6. Garantías de no-intrusión

- **Nunca bloquea:** `Telemetria::enviar()` escribe solo si
  `Serial8.availableForWrite() >= len`; si no, descarta el frame y sigue.
- **Buffer TX ampliado** (`addMemoryForWrite`, ~1 KB) para que un frame completo
  entre sin esperar; a 115200 baud drena en ~42 ms, mucho antes del próximo (100 ms).
- **Rate-limited** a 10 Hz: cualquier cantidad de llamadas a `enviarTelemetria()`
  desde el loop es inofensiva (solo chequea un timer).
- **Apagable:** `#define TELEMETRIA 0` en `main.cpp` la saca por completo.
- **Serial8 compartido con SUPERTEAM:** no activar `TELEMETRIA` y `SUPERTEAM` a la vez.

---

*IITA Salta — RoboCup Junior Rescue Line 2026.*
