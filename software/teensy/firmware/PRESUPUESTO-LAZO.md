# Presupuesto del lazo de línea — 25-ago-2026

**Pregunta de Benjamín:** *«necesitamos buscar en el main.cpp el menor delay
posible para que todo llegue datos actuales».*

Todo lo que sigue es **software puro**, sin tocar una sola conexión, y cada
número tiene su fuente citada. **Nada de esto está probado en banco.**

---

## Por qué esto importa, en una línea

El comando llega tarde. Medido en el robot: el lazo del Teensy corre a p50
30 ms, la Pi manda a 66–86 Hz y **el comando cambia a 8,6–20,6 Hz**. Y medido
del lado de visión, ejecutar un comando 2 frames viejo lo equivoca **21° en el
p90**; 4 frames, **36°**.

---

## Lo que hay hoy en el lazo, con `kFixLazoLineaSensoresBloqueantes = true`

```
while (rutina == "linea" && digitalRead(32) == 0)
{
    serialEvent5();
    ... watchdog ...
    DIAG_TICK();                    // no-op: MODO_DIAGNOSTICO = 0
    enviarTelemetria();
    color_detected = get_color_fast();
    leer_ultrasonido_frontal();     // <- el que domina
    ...
}
```

| llamada | qué hace | costo | fuente |
|---|---|---|---|
| `serialEvent5()` | drena el buffer, parsea 8 bytes | ~20 µs | no bloquea |
| `DIAG_TICK()` | nada | **0** | `MODO_DIAGNOSTICO = 0`, `main.cpp:174` |
| `enviarTelemetria()` | **2 lecturas I2C del BNO055** (`getEvent` + `getVector`) | ~1,8 ms **cada 100 ms** | `Telemetria telemetria(Serial8, 100)`, `main.cpp:330` |
| `get_color_fast()` | 1 lectura I2C (`colorDataReady`) | ~0,36 ms, hasta cada 2 ms | `APDS_COLOR_STATUS_POLL_MS = 2` |
| `leer_ultrasonido_frontal()` | `sonar[0].ping_cm()` | **8,58 ms** | ver abajo |

### El ultrasonido frontal es el 95 % del lazo, y el caso normal es el peor caso

De la librería **vendorizada en el propio repo**, `lib/NewPing/NewPing.h`:

```
US_ROUNDTRIP_CM  = 57 us/cm      (linea 163)
MAX_SENSOR_DELAY = 5800 us       (linea 172)
_maxEchoTime = MAX_DISTANCE * 57 + 28
```

Con `MAX_DISTANCE = 150` (`main.cpp:1230`):

```
150 * 57 + 28 = 8578 us = 8,58 ms          (y hasta 14,4 ms si el sensor tarda en arrancar)
```

**`ping_cm()` bloquea hasta el timeout cuando NO hay eco.** En seguimiento de
línea casi nunca hay una pared a menos de 150 cm adelante, así que **el caso
normal es el peor caso**: se pagan 8,6 ms por vuelta para que la única pregunta
del lazo —`front_distance < 12`— conteste siempre «no hay nada».

El sensor no es lento. El **timeout está puesto 12 veces más lejos de lo que el
lazo pregunta**.

### Y el bus I2C corre a 100 kHz

**No hay un solo `Wire.setClock()` en las 4.146 líneas de `main.cpp`.** El
default de `Wire.begin()` en Teensy 4.x es 100 kHz, y `Wire.setClock()` soporta
hasta 1 MHz en el 4.1. Todo lo que cuelga del bus paga ese factor 4 (o 10).

---

## Los cuatro cambios, todos por software y todos con flag

En `src/priority_fix_flags.h`.

### 1. `kFixPingFrontalCorto = true` — el más grande

`NewPing::ping_cm(unsigned int max_cm_distance = 0)` acepta la distancia **por
llamada** (`NewPing.h:223`), así que no hay que tocar el objeto ni el resto de
las rutinas. El lazo pregunta `< 12`; con 30 cm de techo sobra el doble:

```
8578 us  ->  1738 us          −6,84 ms por vuelta,  4,9x
```

**Cuidado que hay que tener:** `set_max_distance()` **persiste** en el objeto.
Evacuación usa `front_distance < 120`, así que `leer_ultrasonidos()` vuelve a
pedir el rango largo explícitamente. Ese es el único riesgo del cambio y está
cubierto.

### 2. `kFixPingFrontalPeriodico = true` — cada 40 ms, no cada vuelta

A 30 cm/s el robot avanza **1,2 cm en 40 ms**, un décimo del umbral de 12 cm.
Con el lazo a ~2 ms, el costo **medio** del ultrasonido pasa de 8578 µs a
**~87 µs**.

### 3. `kFixI2cRapido = false` — **apagado, y hay que medirlo antes**

`Wire.setClock(400000)` divide por 4 todo el I2C: la telemetría de ~1,8 ms a
~450 µs, el `colorDataReady()` de 360 a 90 µs, y los ToF.

**Va apagado porque es el único de los cuatro que puede ROMPER algo.** Los
pull-up internos del Teensy 4.1 son débiles y hay tres esclavos en el bus
(BNO055, APDS9960, dos VL53L0X). Si los módulos no traen pull-up suficiente, a
400 kHz los flancos no llegan y **el bus se cuelga**, que es peor que ser lento.

*Cómo encenderlo:* 10 minutos de banco leyendo los tres sensores seguidos, y que
ninguno devuelva basura ni se cuelgue. Si pasa, se enciende; si no, queda en 100.

### 4. `kFixTofPresupuesto = true` — 33 ms → 20 ms

El presupuesto por defecto del VL53L0X es **33 ms** y el mínimo admitido **20 ms**;
`setMeasurementTimingBudget()` no se había llamado nunca.

**No cambia el lazo de línea** —ahí los ToF ya no se leen— sino el **seguimiento
de pared**, que sí los relee.

---

## Lo que debería dar, y el falsador

| | hoy | con 1+2 | con 1+2+3 |
|---|---|---|---|
| ultrasonido, costo medio | 8578 µs | ~87 µs | ~87 µs |
| telemetría (cada 100 ms) | ~1800 µs | ~1800 µs | ~450 µs |
| color | ~360 µs | ~360 µs | ~90 µs |
| **p50 del período** | **~30 ms medido** | **< 3 ms esperado** | **< 1 ms esperado** |

**Falsador, escrito antes de probar:** el p50 del período de lazo tiene que
bajar de los 30 ms medidos a **menos de 5 ms**, y la frecuencia con que el
comando CAMBIA tiene que subir de 8,6–20,6 Hz a **más de 50 Hz**.

Si el período baja y la frecuencia de cambio del comando **no sube**, entonces
el cuello no era el lazo y está en el pipeline de cámara o en el serie — y eso
también es un resultado.

**Lo que este fix NO promete:** que el robot tome la curva. Reduce el retardo, y
el retardo cuesta 21–36° de comando equivocado. Cuánto de la falla explica eso
es lo que la corrida del sábado tiene que decir.

---

## Compilación

`pio run -e competencia_fix` → **SUCCESS**, 75.212 B de flash.
**Sin probar en banco**, como todo lo de `priority_fix_flags.h`.

---

## Fuentes

- Pololu, librería VL53L0X para Arduino — presupuesto por defecto 33 ms, mínimo
  20 ms, `setMeasurementTimingBudget()`:
  <https://github.com/pololu/vl53l0x-arduino>
- PJRC, librería Wire en Teensy — `Wire.begin()` default 100 kHz,
  `setClock()` hasta 1 MHz en el 4.1, aviso sobre pull-up internos débiles:
  <https://www.pjrc.com/teensy/td_libs_Wire.html> y
  <https://forum.pjrc.com/threads/57319-I2C-maximum-speed>
- NewPing — `US_ROUNDTRIP_CM`, `MAX_SENSOR_DELAY`, `_maxEchoTime` y la firma de
  `ping_cm(max_cm_distance)`: **la copia vendorizada en `lib/NewPing/`** de este
  mismo repo, contrastada con <https://github.com/livetronic/Arduino-NewPing>
