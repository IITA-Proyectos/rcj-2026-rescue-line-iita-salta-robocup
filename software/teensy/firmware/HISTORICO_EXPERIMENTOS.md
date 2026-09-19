# Histórico del firmware Teensy: por qué anda así y qué se probó

Anotado el 17-sep-2026, al limpiar `src/main.cpp` a pedido del equipo. Los comentarios largos del código
(con fechas y mediciones) se sacaron del fuente y quedan resumidos acá.

**La versión que funciona** es la de las 19:00 del 16-sep: tomó los codos cerrados y los gaps en pista.

- En git: commit `8a8be2c` de la rama `limpieza/firmware-teensy-2026-09-17` (firmware) y `a6f1ed0` (paquete de la Pi
  que corre junto: `software/raspberry/paquetes/V6_6_BASE_COMPLETO_CODO_GAP_2026-09-15/`).
- Copias fuera de git: `Descargas/V6_6_BASE_COMPLETO_CODO_GAP_2026-09-15(.zip)` y `C:/Users/villa/fwbase_1900/` (fuentes +
  build `competencia` usada como referencia binaria para la limpieza).
- La Pi y la Teensy van juntas: la recuperación de línea (GS=4) necesita las dos, y `COMPLETAR_GIRO` en la Pi espera el
  aviso 0xED de la Teensy.

---

## 1. La configuración que funciona

Es la que se flasheaba desde el 30-ago con:

```
set PLATFORMIO_BUILD_FLAGS=-D LINE_STEER_GAIN=1.0 -D LINE_ROT_EXP=0.85
     -D LINE_PIVOTE_ENTRA=1.01 -D LINE_RECTA_FACTOR=0.8
     -D LINE_FRENO_DELANTERO=1 -D LINE_FRENO_STEER=0.70 -D LINE_FRENO_VEL=55
```

Desde el 6-sep esos valores son los predeterminados del código y se flashea con `pio run -t upload` a secas (verificado
comparando el `.elf` función por función). 30-ago, Benjamín: *"lo flasheo y funciona muy bien"*, primera configuración
que toma los codos desde el cambio a 4 ruedas fijas. 31-ago: funcionan los codos con la maniobra de recuperación.

### La cadena, de la cámara a las ruedas

```
angle (0..180, lo manda la Pi)
  -> steer    = (angle - 90) / 90                         -1 .. +1   (derecha negativa)
  -> steerCmd = constrain(steer * LINE_STEER_GAIN, -1, 1)
  -> rot      = |steerCmd| ^ LINE_ROT_EXP                 (rot = 1 si |steerCmd| >= 0,92)
  -> vel      = base + k^2 * (LINE_PIVOT_SPEED - base),   k = |steerCmd| / 0,92
  -> si |steerCmd| >= LINE_FRENO_STEER:  steer(LINE_FRENO_VEL, ±rot)
     si no:                              steer(vel * LINE_RECTA_FACTOR, ±rot)
  -> steer(): rueda de afuera = vel, rueda de adentro = vel * (1 - 2*rot)  (negativa = marcha atrás)
```

Base: 40 rpm en el llano (45 si el pitch pasa de 3,9°).

### Qué dice cada valor y la medición que lo justifica

| flag | valor | por qué |
|---|---|---|
| `LINE_STEER_GAIN` | 1.0 | Con 1,8 el cabeceo empeoró de −11,8° a −20,3° y la banda media de rotación cayó de 32 % a 22 % (satura antes). |
| `LINE_ROT_EXP` | 0.85 | Es LA palanca del radio. La distancia recorrida por grado girado vale `(1−rot)/(k·rot)` y **no depende de la velocidad** (22-ago, corridas a 29 y 37 rpm: 0,49 y 0,44 cm/°). En la curva de 90° que fallaba: con rot 0,30 el robot recorría 44 cm mientras giraba; con rot 0,87, 3,6 cm. La cámara ve 2-3 cm de piso. |
| `LINE_PIVOTE_ENTRA` | 1.01 | **Apaga el pivote pegajoso** (ver experimento 1). Medido sobre 43.137 muestras de pista del 26-ago: tiempo girando sin avanzar (rot ≥ 0,95) **29,7 % → 7,8 %**. Es la razón principal de que la configuración anda. |
| `LINE_RECTA_FACTOR` | 0.8 | Pedido de Benjamín (26-ago): "más lento normalmente y de ahí girar brusco". 36 rpm en recta. No cierra el radio: da tiempo de reacción (con el lazo de visión a ~50 fps y 60-70 ms de retraso comando→giro, el doble de frames por cm antes del codo). |
| `LINE_FRENO_DELANTERO` | 1 | No controla nada en el código (quedó de un experimento). Se quita. |
| `LINE_FRENO_STEER` | 0.70 | Desde `|steer| ≥ 0,70` se usa la velocidad fija de curva cerrada. En el umbral: `rot` es continuo (0,7384 → 0,7385) y la velocidad salta 36 → 55 rpm (+53 %). Si aparece un tirón entrando a una curva, empezar por acá. |
| `LINE_FRENO_VEL` | 55 | La que usaban con la tracción anterior (2 fijas + 2 omni): 40 de base y 55 en curva. Resume la configuración ganadora: **lento y suave en todos lados, rápido y comprometido solo en la curva cerrada, y nunca pivotando en el lugar**. |
| `LINE_PIVOT_SPEED` | 50 | Techo de la rampa cuadrática. 23-ago, tramos de más de 150 ms: 20 rpm dan 19,6 °/s, 35 dan 39,3 y 50 dan 39,2 (de 35 a 50 no se gana giro). Con `LINE_FRENO_STEER` 0,70 la rampa no llega a 50: queda en ~45. |

### Por qué la rampa de velocidad es cuadrática

22-ago, dos corridas a distinta velocidad, rendimiento de giro por zona:

| zona | lenta | rápida |
|---|---|---|
| rot 0,40-0,60 (avanza mientras gira) | 29 rpm: 0,744 / 0,824 | 37 rpm: 0,716 / 0,757 |
| rot 0,95-1,00 (gira en el lugar) | 20 rpm: 23,7 °/s | 35 rpm: 45,3 °/s |

En la zona intermedia rinde mejor más lento; en el giro en el lugar, más velocidad duplica el giro. Con `k²` la velocidad
queda baja a mitad de curva (40 en recta, 42 a mitad, 50 cerca del fondo): frena donde avanza y empuja donde gira.
`LINE_PIVOT_STEER = 0,92` fuerza `rot = 1` en el 4,6 % de las muestras (era 6,9 % con ganancia 1,35).

### Geometría medida del robot

| dato | valor | cómo |
|---|---|---|
| diámetro efectivo de rodadura | **68,8 mm** | 25 cuentas/cm con 540 ticks/vuelta (el TDP dice 60 mm y está mal); hub 62,654 mm + silicona A10 |
| ancho de vía efectivo `b_eff` | **20,9 cm** | 26-ago, `b = Δv_encoder / gz`: 21,35 / 21,38 / 21,28 cm en 3 corridas de pista (banco: 22,41 y 22,31). Mayor que el ancho real (17,7 cm) por el arrastre del skid-steer |
| apertura | **1,15** | el robot abre un 15 % respecto del radio pedido, constante en todo el rango (22-ago, banco con las 4 ruedas al piso) |
| retraso comando → giro | 60-70 ms | CSV de pista |
| radio pedido | `R = 20,9·(1−rot)/(2·rot)` cm | la velocidad no aparece: ir más lento no cierra la curva (26-ago, `freno_ctrl_1` con 55 en curva dio igual que la base) |

### Recuperación de línea (GS=4)

- Pi: GS=4 con antirrebote ("venía estable y la perdí, confirmado": 3 frames; 3 frames + 0,55 s para salir) y el rumbo de
  CAMINO+MONO en el byte `angle`.
- Teensy: retrocede 400 ms a 25 rpm (~3,6 cm), queda quieta 120 ms para que CAMINO mire desde la pose nueva, y pivota una
  sola vez `28 + 0,22·|rumbo|` grados acotado a [35, 58], a 35 rpm, con tope de 1,6 s. Los pivotes de 70-90° eran los
  que se iban de la pista (`K` bajó de 0,26 a 0,22 el 12-sep).
- `completo_auth_1` (12-sep): 10 de 11 recuperaciones bien; la única falla fue el codo de 0:36. Con ~43° pedidos la
  derecha giró 33-42° y la izquierda 45-48°.

### Lazo de velocidad de cada motor (`FIX_LAZO_MOTOR = 1`, desde el 6-sep)

- Feedforward `8 + 1,35·rpm` (el motor da 159 rpm a 12 V con ~215 de esfuerzo) + integrador acotado.
- Piso de esfuerzo: nunca menos de la mitad del feedforward, y nunca menos de 20. El FIT0441 a PWM bajo **suelta** la
  rueda (coast, medido en banco el 8-ago). El piso estuvo en 45 y era un error: 45 es más que el feedforward de toda
  la curva (8 + 1,35·27,4) y tapaba al lazo justo en las curvas.
- 11 corridas de pista (15-sep): en giro en el lugar las ruedas llegan al 76-82 % de lo pedido con esfuerzo mediano ~95
  de 255 y 0 % saturado.

### Otros valores medidos que quedan

- **Ping frontal:** `ping_cm()` bloquea hasta el timeout sin eco: con 30 cm de techo el timeout baja de 8578 µs a 1738 µs.
  El lazo de línea corría a 30 ms de período (p50 sobre 7673 vueltas) con la Pi mandando a 66-86 Hz: 3 de cada 4 tramas
  se descartaban; sacar las lecturas bloqueantes (ToF y ping largo) lo bajó a menos de 10 ms.
- **Watchdog de comunicación (400 ms + 300 ms sostenidos):** en una corrida grabada, 49 % de las muestras con más de 1 s
  sin trama nueva y una ventana de 17,1 s sobre el mismo comando. Durante una maniobra el comando llega con p50 1849 ms
  y máximo 4677 ms de atraso: por eso se exige que lo rancio se sostenga.

---

## 2. Experimentos retirados del código

### 1. Pivote con histéresis (`LINE_PIVOTE_ENTRA/_SALE/_CONFIRMA_MS/_MAX_MS`)
- Qué hacía: con `|steer|` alto giraba en el lugar (`rot = 1`) y no soltaba hasta quedar alineado.
- Sin histéresis picoteaba (22-ago): 3,6 entradas y salidas por segundo, episodios de 160 ms y 8° de mediana; solo 4 de
  76 episodios pasaban 45° (un codo pide 90°).
- Con histéresis tampoco alcanzaba: 284 episodios simulados sobre el `rxsteer` real dieron 210 ms y 6,0° reales de
  mediana, 1 % pasando 45°. **La cámara no mide rumbo**: se mueve 7 a 9,6° de imagen por grado real del robot, así que
  con 11° de giro el ángulo cruza el cero y la condición de salida se cumple antes de terminar la curva.
- Las rachas alineadas duran 50-75 ms: con `_CONFIRMA_MS` ≥ 300 no salía por alineación y giraba 2,5 s en el lugar
  (Lack of Progress). La tasa de giro satura en ~39 °/s: 90° cuestan 2,3 s.
- Apagarlo bajó el tiempo sin avanzar de 29,7 % a 7,8 %. Para revivirlo: `LINE_PIVOTE_ENTRA = 0.60` en el código viejo.

### 2. Freno real de la delantera interna (`LINE_FRENO_FACTOR`, `LINE_FRENO_ROT_MULT`, `steerFrenoDelantero`)
- Idea (26-ago, de la época de 2 fijas + 2 omni): frenar o invertir la rueda delantera interna para correr el centro de
  giro hacia adelante.
- `LINE_FRENO_FACTOR` valía `kFrenoComoSteer`, que reparte **igual que `steer()`**: nunca frenó nada. La rama solo aportaba
  el escalón 36 → 55 rpm (eso **se conserva**, ahora con `steer()` directo: mismo reparto).
- Con 4 ruedas fijas el centro de giro no se puede imponer por consigna (las dos ruedas de un lado tienen la misma
  posición lateral). Con la delantera interna en reversa el radio sería 3,48 cm contra 10,45 cm quieta: es el mayor
  desgaste de silicona de todo lo probado. 26-ago: 88 episodios de curva y ninguno pasó 55° netos.
- `LINE_FRENO_ROT_MULT` (1.0) nunca se barrió.

### 3. Lazo de motor histórico (`FIX_LAZO_MOTOR = 0`)
- Integrador puro con "toggle" del pin de dirección cuando el esfuerzo bajaba de 10.
- Defectos (6-sep): (a) el encoder no da sentido, y cuando el chasis arrastraba la rueda interna hacia adelante el lazo
  bajaba el PWM y la soltaba; (b) sin feedforward, el PWM salía solo de la medición; (c) el toggle invertía el pin en cada
  vuelta del loop y ensuciaba la cuenta de pulsos. Se reemplazó por el lazo nuevo (sección 1).

### 4. Extra de grados en la recuperación hacia la derecha (`RECUP_GIRO_DER_EXTRA_GRADOS`)
- Sumaba grados solo al pivote de recuperación a la derecha, por la asimetría medida en `completo_auth_1` (derecha 33-42°,
  izquierda 45-48° con ~43° pedidos).
- La versión del 12-sep lo sumaba a la izquierda por un error de signo; se corrigió y quedó en 0 (= `completo_auth_1`).
  Idea pendiente: probar 10° en banco.

### 5. Máquina de rescate no bloqueante (`RescateState`, `actualizarRescate`)
- Secuencias de garra por pasos (negra y plateada). Nunca arrancaba: las funciones que la disparaban se borraron el 6-sep.
  El rescate que corre es el de los green_state 6 (negra) y 7 (plateada) dentro de `rutina == "rescate"`.

### 6. Modo intersección con realineo por IMU (green_state 14, 15, 16 y 17 → `case 12`)
- Con GS 14 se realineaba con el rumbo guardado al arrancar (`centrar`) y esperaba hasta 5 s un GS 15/16/17 para girar.
  Ninguna versión de la Pi lo manda. Al sacarlo se elimina un riesgo: un byte corrupto de valor 14 dejaba el robot
  esperando 5 s.

### 7. Sensores ToF VL53L0X laterales
- Montados a los costados (buses Wire1 y Wire2), se inicializaban al arrancar pero nadie los leía desde que se sacó el
  seguimiento de pared. El equipo prefiere los ultrasonidos. La telemetría mandaba siempre 0 mm.

### 8. Leyes de reparto de `DriveBase` sin uso (`steerSuma`, `steerRadius`, `steerAxleBias`)
- `steerSuma`: reparto por suma y resta (la ley de Airborne 2025); el robot no pierde avance al girar (`R = b_eff/(2u)`).
- `steerRadius`: pedir un radio en cm con `rot = b_eff/(2R + b_eff)` (4,9 cm → rot 0,681; 15 cm → 0,411).
- `steerAxleBias`: escalar la consigna por eje para emular las omni traseras. Bajar la consigna de un eje no lo hace ir
  más despacio contra el piso: el lazo le baja el PWM hasta dejarlo sin par (con 0,55 el eje delantero quedaba sin fuerza).

### 9. Rampa (16-sep, no está en el código de las 19:00)
Todo guardado en `Descargas/TEENSY_RAMPA_2026-09-17/` y detallado en `Descargas/PENDIENTES_COMPETENCIA_13-NOV-2026.md`
(punto 10). Lo que quedó medido:
- **Trasera interna clavada** (CSV `rampa_mapa_1`): con pitch > 12 y giro > 40° el refuerzo de 80 rpm y `steer()` le dan
  dos sentidos por vuelta; queda a 2-5 rpm con esfuerzo 117-119 mientras la externa va a 35 rpm. Sacar el conflicto dejando
  que la interna vaya marcha atrás hizo que **no subiera** (cabeceo).
- **Quieto en la rampa:** mirando hacia arriba rueda para atrás; mirando hacia abajo desliza un poco; de costado desliza un
  poco y se queda (μ ≈ 0,43-0,50 a 23°: sobra entre 1 % y 18 % de agarre).
- **De costado** (`rampa_bajada_1`): girando lento hacia abajo logra 96 % del giro pedido, hacia arriba 76 %; girando en el
  lugar, 77 %. De frente, en curvas medias, 37-51 %.
- **Verde en rampa:** avanzar derecho y después girar en arco no desliza; girar en el lugar lo corre rampa abajo.
- **Bajada:** el lazo no frena (ruedas arrastradas a 24-52 rpm con esfuerzo mínimo); el freno por contracorriente frenó
  pero vibró.
- **Lección:** nada de rampa puede mirar el pitch instantáneo: los picos del IMU en las curvas del piso (hasta 1 s por
  debajo de −12°) cambiaron el giro en el piso.
