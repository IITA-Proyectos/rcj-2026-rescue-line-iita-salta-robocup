# Traspaso — diagnóstico de curvas cerradas, robot de rescate IITA

_19-ago-2026 · para retomar en otra conversación · reemplaza al traspaso del 17-ago_

**Lo que se juega el sábado:** ésta es la prueba fundamental. El equipo tiene el robot
**una vez por semana, los sábados, 3 horas y media**. No hay banco entre semana. La
competencia (Roboliga 2026, Rescate) es en noviembre.

---

## El problema

El robot **no toma las curvas cerradas** desde que se pasó de "2 fijas adelante + 2 omni
atrás" a **4 ruedas fijas de silicona**. En rectas anda. Benjamín observa además que no se
centra sobre la línea y que una rueda retrocede más lento al girar.

**Hay DOS hipótesis vivas y ninguna lectura de código las separa** — las dos aparecen
exactamente al sacar las omni:

1. **PID ciego al signo.** El encoder es de un solo canal (`attachInterrupt(..., CHANGE)`,
   540 flancos/vuelta) y el lazo compara **magnitudes**: `|consigna| − |medida|`. Cuando el
   chasis arrastra la rueda interna hacia adelante mientras se le pidió reversa, el encoder
   informa un número sano, el PID le **baja el PWM**, y el FIT0441 a PWM bajo hace **COAST**
   (medido en banco por el equipo el 2026-08-08). Se realimenta: menos par → gira menos →
   más arrastre → menos par.
2. **Techo de par.** La silicona tiene mucho rozamiento y las 4 fijas tienen que arrastrar
   de costado para girar. Si no alcanza el par, **ningún cambio de firmware lo arregla**.

Con las omni el bug (1) estaba latente: la rueda hacía lo que le decían, así que la ceguera
al signo era inofensiva. **No fue suerte: fue una precondición que el tren viejo no creaba.**

---

## Lo VERIFICADO (medido o leído del código, no supuesto)

### Firmware

- `Moto::setSpeed` tenía `if (_pwmVal < 10) _dir = !_dir;` → **invierte el pin de dirección
  en cada llamada** mientras el esfuerzo sea bajo, o sea a la frecuencia del `loop()`. Además
  ensucia `pulseCount`, que cuenta según `_dir`.
- **El salto de rama del `case 7`**, calculado con las constantes del propio archivo:

  | cámara | rama | rotation | rueda interna |
  |---|---|---|---|
  | 23,3° | curva | 0,350 | **+7,8 rpm** (adelante) |
  | 23,4° | curva dura | 0,800 | **−13,2 rpm** (REVERSA) |

  **Una décima de grado da vuelta la rueda interna.** Peor salto con 0,1° de cámara:
  **21,0 rpm**. Este salto **no existía antes del 15-ago**: el `case 7` commiteado pasaba
  `steer` como `rotation` en las dos ramas (continuo). Lo introdujo el parche de Codex.
- `steerAxleBias(front=0.55, rear=1.00)` le pide **−7,3 rpm a la delantera y −13,3 a la
  trasera del mismo lado**: 9,0 rpm de conflicto. En un chasis rígido eso no la hace girar
  más despacio — hace que su RPM medida supere a la pedida, y como el PID solo ve magnitudes,
  **le corta el PWM y el eje delantero queda sin par**.
- `ajustarVelocidadPorPendiente()`: el `else if (pitch > 25)` es **inalcanzable** (hay un
  `if (pitch > 3.9)` antes) y la función **ignora su propio `velocidadBase`**.
- `PID::Reset()` pone en cero el acumulador pero **no `_pwmVal`**, y `Compute()` solo corre
  cada `SampleTime`: pedir consigna 0 dejaba el motor andando hasta 20 ms con el esfuerzo
  viejo. (Arreglado.)

### Visión (medido reproduciendo el bloque exacto de `Main.py`)

- **Sesgo de −1,97°** con la línea perfectamente centrada, por `cam_x = width/2 - 1` (79,0
  cuando el centro real de 160 px es 79,5). El byte que sale es 88, no 90.
- **Ganancia 3:1**: −1,96 °/px pegado al centro, −0,70 °/px a ±40 px.
- **Se queda MUDA en media curva**: en la geometría de curva ya iniciada manda **1,28°**
  cuando tendría que gritar. No se invierte: se anula. La masa del tramo de donde venís
  cancela la del tramo hacia donde vas.
- **`atan2(0,0) − 90 = −90`**: con la máscara vacía el ángulo vale −90, y ese −90 fija
  `last_line_search_dir` → **la recuperación busca siempre hacia el mismo lado**.
- El `speed` que manda la RPi **no se usa** en linetrack: el `case 7` usa
  `ajustarVelocidadPorPendiente(45)` y después 26/22/20 fijos.
- **NO reproduje** el "11 % de inversiones de signo" que decía el traspaso viejo. Con
  geometría sintética limpia el signo sale bien en 19 de 20 casos. Queda como discrepancia.

### Lo que NO hay que hacer (probado y descartado)

- **El método de "dos bandas"** (centroide cerca vs lejos): lo probé y da **10/11 signos
  equivocados**. Mide hacia dónde va la cinta pero no cuán desviado está el robot: le da
  0,00° a una recta desplazada 30 px. Un seguidor necesita las dos cosas.
- **Bajar `SampleTime` del PID de 100 a 20 ms**: es un **no-op matemático**. `ki_interno =
  Ki·Ts` aplicado cada `Ts` → la ganancia integral por segundo es `Ki` sin importar `Ts`.

---

## AVISOS CRÍTICOS

### 1. Todo esto está sin commitear

```
UNTRACKED (no existen en ningún lado más que ese disco):
  software/teensy/firmware/tools/            <- las 9 herramientas y el protocolo
  software/raspberry/final_rpi/telemetria_vision.py
  software/teensy/firmware/git_commit.py
stash: 0   tags: 0   .pio está en .gitignore (los 9 .hex tampoco están versionados)
```

Un `git clean -fd` borra todo. **Commitear y taguear antes que cualquier otra cosa.**

### 2. `teensy_hid_device` NO es el robot que compitió

```
PID SampleTime en HEAD : 100     <- y NO está detrás de ningún #if
PID SampleTime hoy     : 20         => entra en TODOS los binarios
steerAxleBias en HEAD  : 0 ocurrencias
steerAxleBias hoy      : 3          => reconstruida del desensamblado, nunca commiteada
```

Es el código histórico + un `steerAxleBias` reconstruido a mano + un PID 5× más rápido.
El A/B entre entornos sigue siendo válido (la única diferencia es el flag), pero **no se
puede decir "así se comportaba antes"**.

### 3. `mainenviar.py` no existe en el repo

`Main.py` lo importa en la línea 2. La visión solo arranca porque la Raspberry tiene ese
archivo **fuera de git** — igual que el `.tflite` que carga. Y lo que corre en la Pi es un
archivo del Desktop, **no el del repo**: el enganche de telemetría de visión que se agregó
**no está en la máquina que corre**.

---

## Lo que se construyó (todo compila; NADA corrió en el robot)

### Nueve entornos de PlatformIO

| entorno | qué es |
|---|---|
| `teensy_hid_device` | competencia. Sin nada del diagnóstico adentro. Es el `default_envs` |
| `banco_barrido` | **el primero a subir.** Barrido automático de rotation y velocidad, sin pista ni visión |
| `banco_barrido_fix` | idem con los dos fixes encendidos |
| `diagnostico` | robot actual + registrador CSV **200 Hz** por USB |
| `diagnostico_full` | idem + telemetría WiFi 10 Hz **en paralelo** (redundancia) |
| `diagnostico_lazo` | + fix del lazo de motor solamente |
| `diagnostico_fix` | + fix del lazo **y** rotation continua |
| `diagnostico_suelto` | CSV por Serial8 (sin cable USB), con USB-TTL en pin 35 a 921600 |
| `competencia_fix` | el robot andando con los dos fixes, sin registrador |

### Los dos fixes (por defecto APAGADOS)

- **`FIX_LAZO_MOTOR`** — feedforward (`kS + kV·rpm`), anti-windup acotado al rango útil,
  **piso absoluto `MOTO_PWM_ANTICOAST = 45`** `[PROVISORIO: banco]`, reset del integrador al
  invertir, apagado inmediato con consigna 0, y sin el toggle del pin.
  Simulación de la aritmética exacta contra el lazo histórico:
  ```
  DENTRO de la curva:  historico cae de 53.8 a 0.0 -> COAST, rueda suelta
                       nuevo     cae de 28.8 a 17.5 -> sostiene el esfuerzo
  ```
- **`FIX_CURVA_CONTINUA`** — `rotation` como función continua de `steerCmd`, sin
  `steerAxleBias`:
  ```
  PEOR SALTO con 0,1 grado de camara:   historico 21.0 rpm  ->  continuo 0.2 rpm
  CONFLICTO ENTRE EJES:                 historico  9.0 rpm  ->  continuo 0.0 rpm
  ```

### Nueve herramientas en `software/teensy/firmware/tools/`

| archivo | qué hace |
|---|---|
| `registrar_diagnostico.py` | graba el CSV por USB. Lectura por bloques, `--nota`, contadores de curvas de visión vs giros programados **en vivo**, y criterio de **CORRIDA VALIDA** al cortar |
| `grabar_wifi.py` | graba por WiFi desde la ESP32, **sin cable**. Detecta frame congelado |
| `wifi_a_csv.py` | convierte el JSONL al mismo CSV. Emite `*_pmin`/`*_rmax` (envolventes) |
| `analizar_diagnostico.py` | causas **A/B/C/D/E/F/G/P/R** sobre una corrida. `--comparar`, `--eje` |
| `analizar_barrido.py` | **el veredicto firmware-vs-mecánica**. `--aire`, `--eje` |
| `analizar_conjunto.py` | cruza el CSV del Teensy con el de la visión |
| `probar_analizador.py` | **16 casos sintéticos de regresión (11 + 5 del barrido). Pasan** |
| `PROTOCOLO-DIAGNOSTICO.md` | el protocolo escrito |
| `telemetria_vision.py` (en `raspberry/final_rpi/`) | una línea por frame. **2 µs de costo**, nunca levanta excepción |

### El registro CSV — 45 columnas a 200 Hz

Muestreo por **`IntervalTimer` de hardware**, no colgado del `loop()`. Esto es crítico: el
`case 7` corre dentro de un `while (rutina == "linea")` **adentro de `loop()`** y no llama a
`serviceMotionBackgroundTasks()`, así que colgado del lazo **el registrador grababa CERO
muestras de las curvas**.

Columnas: el ángulo que llegó de la RPi (`rxsteer`) y su edad (`rxage`) · lo que decidió el
drivebase (`rot`, `ls`, `rs`, `ram`) · por rueda: `dir`, `set`, `rpm`, **`raw`** (flancos
crudos, la única medida de movimiento físico que no depende de `_dir`), `pwm`, `enc`, `tog` ·
el giro real (`gx`/`gy`/`gz`) · y la honestidad del muestreo (`dt`, `drop`).

---

## EL PLAN DEL SÁBADO (210 minutos)

Con una ventana por semana, **el costo de un error no es una hora: es una semana.** Por eso
los primeros 35 minutos se gastan en **saber qué se está arreglando**.

| minutos | qué | qué compra |
|---|---|---|
| **0-15** | armar, flashear `banco_barrido`, verificar que grabe | que la cadena de medición funcione **antes** de necesitarla |
| **15-35** | barrido en el piso + con ruedas al aire → `analizar_barrido.py` | **el veredicto: firmware o mecánica** |
| **35-60** | si es firmware: `banco_barrido_fix`, mismo barrido | la mejora **medida** |
| **60-140** | pista con `competencia_fix` + `diagnostico_full` | el robot andando, y grabado |
| **140-180** | iterar según los CSV | |
| **180-210** | dejar la config final, guardar archivos | no terminar sin saber qué quedó flasheado |

### El barrido decide porque las dos hipótesis predicen ÓRDENES OPUESTOS

- el giro **mejora** hacia `rotation = 1` → **PID ciego al signo**. En `rotation=1` la
  consigna de la interna es la velocidad completa y el lazo **no puede** colapsar.
- el giro **empeora** hacia `rotation = 1` → **techo de par**. `rotation=1` es el scrub
  máximo. **Es mecánico.**
- **en el aire obedece y en el piso se apaga** → el problema **depende de la carga**: la
  prueba directa de toda la hipótesis.

El robot pivotea dentro de **25 cm** (radio = `trocha·(1−r)/(2r)`), así que **alcanza un
cable USB corto**. No hace falta uno de 3 m — y sería contraproducente: tironea del chasis
justo en las curvas. Lo que importa es que esté **flojo**.

### El barrido va sobre la PISTA, no sobre el piso del taller

La hipótesis 2 es literalmente sobre el rozamiento de la silicona contra la superficie. El
cerámico del taller no es el MDF pintado de la pista. Entra en una baldosa limpia.

---

## Las causas y dónde se arregla cada una

| | qué significa | dónde |
|---|---|---|
| **[A]** | el PID le corta la corriente a la rueda interna | firmware — `FIX_LAZO_MOTOR` |
| **[B]** | las ruedas obedecen y el robot igual no gira | **mecánica**. Es **residual**: solo sobrevive si ni G, ni P, ni D lo explican |
| **[C]** | el pin de dirección oscilando | firmware, tres líneas |
| **[D]** | el control se congela en un movimiento bloqueante | firmware |
| **[E]** | el robot actúa sobre un comando viejo | comms |
| **[F]** | la visión nunca pidió el giro | percepción |
| **[G]** | el estimador de RPM miente (`rpm` vs `raw`) | reescribir `getSpeed()` |
| **[P]** | las cuatro ruedas cortas a la vez | **alimentación/driver**, no scrub. Discrimina por **simetría**: el scrub castiga a la interna, la tensión a las cuatro |
| **[R]** | flancos imposibles del encoder (>185 rpm) | **hardware**: capacitor / apantallado |
| **[!]** | hubo ruido antes del colapso → **[A] no concluyente** | resolver [R] primero |
| **[-]** | la curva la pidió un `runAngle`, no la visión | no cuenta |

---

## Lo que el diagnóstico NO puede ver

1. **El sentido real de giro.** Encoder de un canal: `raw` dice que la rueda se movió, no
   para dónde. "La están arrastrando" es una **inferencia fuerte**, no una medición.
2. **Tensión y corriente.** No hay sensor y **no tienen voltímetro**. [P] discrimina por
   simetría, que es inferencia. Un divisor resistivo a un ADC lo convertiría en medición.
3. **`getSpeed()` muta el filtro.** Escribe `_rpmlist[3]`, y ese valor entra al historial.
   Como se llama desde `setSpeed()`, el sesgo depende de **cuántas veces por vuelta** se
   llame — y con `pitch > PITCH_RAMPA` las traseras reciben dos extra. **Sin arreglar a
   propósito**: es el estimador del control y cambiarlo sin medir es lo que no hay que hacer.

---

## Lo que falta hacer y NO es código

- **Compilar los 9 entornos en la notebook que va a la sede** (`pio run`). Si nunca compiló
  un entorno, recompila el framework Teensy: 2-5 min **por entorno**.
- **Traer por SSH el `main.py` que realmente corre en la Pi** (está en el Desktop, no en el
  repo) y aplicarle ahí el enganche de `telemetria_vision.py`.
- **Una cuna** para el barrido al aire: dos tacos o una caja recortada, con el cable saliendo
  sin tensión. Antes de grabar, **girar las cuatro ruedas con el dedo**: una rozando la cuna
  simula exactamente el colapso que se busca.
- **Plan por si sale MECÁNICO**: las 2 omni viejas, destornillador y cinta de embalar en la
  caja. Es lo único que no se improvisa.
- **Baterías cargadas**: el barrido es lo más caro en corriente que hace el robot.

---

## Historial de auditorías

Tres auditorías adversariales con verificación independiente. Hallazgos que habrían
arruinado el sábado y ya están cerrados:

- El registrador **grababa cero muestras** durante el seguimiento de línea (`DIAG_TICK` no se
  alcanzaba). → `IntervalTimer`.
- El piso de esfuerzo del fix quedaba en **3,5 % de PWM** justo en la curva cerrada, por
  debajo del umbral del analizador: las dos corridas habrían dado **el mismo veredicto**. →
  piso absoluto.
- La comparación **piso vs aire** comparaba la guiñada del chasis — que en el aire es cero
  por física — y decía **siempre lo contrario**. → compara el colapso de la rueda interna.
- El selector de eje del giroscopio elegía **el eje que más vibra**. → media **con signo**
  (la rotación tiene continua, la vibración promedia 0).
- `MODO_BANCO` no salteaba `setup()`: si el BNO fallaba, `while(1)` **mudo**. → no fatal.
- Con la IMU muda el analizador sentenciaba **"el problema está en la VISIÓN"**. → se niega
  a dar veredicto.

---

## Reglas de la casa

- Verificar contra el **código**, no contra la documentación.
- **Compilar no es funcionar.** Lo que no corrió en el robot es hipótesis, y se dice así.
- Todo en **español rioplatense**.
- El jurado entrevista a los **alumnos**: lo simple y explicable vale más.
- **Poner a refutar las conclusiones importantes antes de darlas.** En esta sesión eso
  atrapó tres bugs en las propias herramientas de diagnóstico y una idea mía de visión que
  era peor que lo que había.

---

## Estado al cerrar

**9 entornos + ESP32 compilan · 9 herramientas parsean · 16/16 de regresión.**

**Nada corrió en el robot.** El sábado es la primera vez, y por eso el plan del día es
medir, no arreglar a ciegas.
