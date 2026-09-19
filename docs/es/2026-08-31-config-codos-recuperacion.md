# 31-ago-2026 — La configuracion con la que el robot TOMA LOS CODOS

**Benjamin, despues de probar en el robot: "con estos 2 codigos funcionaron los
codos por fin, con la maniobra de recuperacion".**

Es la primera vez que codo + recuperacion de linea perdida funcionan juntos.
Este documento existe para que la config **no viva solo en dos lineas de consola**:
al 30-ago los flags estaban unicamente en un `set` de PowerShell y
`src/main.cpp` estaba modificado y sin commitear.

Los dos archivos quedan congelados en el repo:

| lado | archivo |
|---|---|
| Raspberry | [`software/raspberry/EN_EL_ROBOT/main.py`](../../software/raspberry/EN_EL_ROBOT/main.py) |
| Teensy | [`software/teensy/firmware/src/main.cpp`](../../software/teensy/firmware/src/main.cpp) |

**Los dos van juntos.** El `main.py` manda `green_state = 4` (linea perdida
confirmada) y el rumbo de CAMINO; el firmware es el que retrocede y pivotea.
Flashear uno solo de los dos no reproduce el resultado.

---

## Como se lanza

### Raspberry

```bash
RECUP=1 RETROCEDER=1 RECUP_CAMINO=1 python3 -u main.py
```

### Teensy

```
set PLATFORMIO_BUILD_FLAGS=-D LINE_STEER_GAIN=1.0 -D LINE_ROT_EXP=0.85 -D LINE_PIVOTE_ENTRA=1.01 -D LINE_RECTA_FACTOR=0.8 -D LINE_FRENO_DELANTERO=1 -D LINE_FRENO_STEER=0.70 -D LINE_FRENO_VEL=55
pio run -e diagnostico_fix
```

`PLATFORMIO_BUILD_FLAGS` se **suma** a los `build_flags` de
`[env:diagnostico_fix]` (`MODO_DIAGNOSTICO=1`, `TELEMETRIA=0`,
`FIX_LAZO_MOTOR=1`, `FIX_CURVA_CONTINUA=1`). Los siete flags de arriba estan
declarados con `#ifndef` en `main.cpp` (lineas 90-297), asi que el `-D` pisa el
default. Para flashear, el mismo comando con `-t upload`.

---

## Que enciende cada palanca

### Del lado de la Pi

| variable | efecto |
|---|---|
| `RECUP=1` | arma la deteccion de linea perdida (`_solo_mi_linea` + error lateral) |
| `RETROCEDER=1` | al confirmar la perdida manda `green_state = 4` en vez de girar a ciegas |
| `RECUP_CAMINO=1` | levanta el shadow CAMINO+MONO como **sensor de rumbo** para el pivote dirigido |

Todo lo demas queda en su default: `PLANNER=0`, `CTRL=atan2`, `ROI=60`,
`ROI_ARRIBA=60`, `ROI_ABAJO=120` (sin recorte). O sea: **el seguimiento normal
es el de siempre**; lo que cambia es que la perdida de linea ahora tiene una
maniobra.

`RECUP_CAMINO` no toca el `angle` mientras la linea existe. CAMINO corre en
paralelo y solo guarda el ultimo `heading` confiable (HIGH/MEDIUM); ese numero
se usa unicamente cuando se dispara GS=4.

La perdida no se declara con un frame vacio. El antirrebote esta en
`main.py:44-53`: `RECUP_PERDIDA_FRAMES=3` para entrar, `RECUP_RECAPTURA_FRAMES=3`
y `RECUP_RECAPTURA_MIN_S=0.55` para salir, mas bloqueos por verde
(`RECUP_BLOQUEO_VERDE_S=3.0`, doble verde `6.0`). Todos son variables de
entorno: se pueden barrer sin editar el archivo.

### Del lado del firmware

Los siete flags son los mismos del 30-ago. Lo que agrega esta version es el
**pivote dirigido** dentro de GS=4 (`main.cpp:632-680`):

```
retroceso            RECUP_VEL=25 rpm durante RECUP_MS=400 ms
reanalisis           RECUP_REANALISIS_MS=120 ms quieto, para que CAMINO
                     vuelva a mirar desde la posicion nueva
rumbo aceptado       solo si llego hace menos de RECUP_REANALISIS_EDAD_MS=180 ms
                     y con |steer| >= RECUP_STEER_MIN=0.10
angulo del pivote    28 + 0.26 * |heading|, acotado a [35, 58] grados
                     (RECUP_GIRO_BASE_GRADOS / _CAMINO_K / _MIN / _MAX)
pivote               RECUP_PIVOTE_ROT=1.00, RECUP_GIRO_VEL=35
topes                RECUP_GIRO_MAX_MS=1600 por giro, RECUP_MAX_GIROS=3 por
                     episodio, RECUP_MAX_PASOS=20 retrocesos seguidos
```

El heading de CAMINO **no** se manda 1:1 a los grados de yaw: se escala. Esa es
la diferencia con los pivotes de 70-90 grados que se iban de la pista.

---

## Lo que estos flags NO hacen

`LINE_FRENO_DELANTERO=1` **no esta frenando la rueda delantera interna.**
`LINE_FRENO_FACTOR` no se pasa por linea de comandos, asi que queda en su
default `DriveBase::kFrenoComoSteer` (`main.cpp:251-252`), que es el **control
negativo**: la delantera interna recibe exactamente la misma consigna que en
`steer()`. La geometria del giro no cambia.

Lo que la rama del freno si hace con esta config es un **cambio de velocidad**:
arriba de `absSteer 0.70` usa `LINE_FRENO_VEL=55` en vez de `vel*0.8`. Eso es
lo que hay que tener en la cabeza antes de "mejorar el freno": el efecto medido
viene de ahi, no de la rueda.

El otro mecanismo, ya medido el 30-ago: `LINE_PIVOTE_ENTRA=1.01` **apaga el
pivote pegajoso**, porque `steerCmd` esta acotado a +-1.0 y nunca llega a 1.01.

---

## Dependencias que hay que tener al lado del `main.py`

`RECUP_CAMINO=1` hace `from camino_heading import CaminoHeading`, y ese modulo
carga por ruta absoluta, desde su propia carpeta:

```
camino_heading.py            <- el shadow
camino_principal_robot.py    <- instala CAMINO+MONO sobre v2
nuevo_code_v4.py             <- y encadena v3 -> v2
nuevo_code_v3.py
nuevo_code_v2.py
```

Los cinco quedan versionados en `software/raspberry/EN_EL_ROBOT/`. Si falta
alguno, `main.py` **no falla**: imprime
`[RECUP-CAMINO] no se pudo cargar (...)` y sigue, pero la recuperacion queda
**sin giro dirigido** — solo retrocede. Verificar siempre en el arranque que
diga `[RECUP-CAMINO] CAMINO+MONO shadow encendido` y que la linea `[PARCHE]`
cierre con `RECUP_CAMINO=1`.

---

## Verificacion hecha al commitear

- `pio run -e diagnostico_fix` con los siete flags: **SUCCESS** (6,4 s;
  FLASH 75 212 B, RAM1 variables 19 040 B).
- Los seis `.py` compilan (`python -m py_compile`).
- `CaminoHeading()` se instancia con los cinco archivos en `EN_EL_ROBOT/`
  (devuelve `estado='SIN_DATO'` antes del primer frame, que es lo esperado).
- Prueba en el robot: la reporta Benjamin — codos tomados con la maniobra de
  recuperacion. Ver `testing/TEST_LOG.md` T-009.

## Procedencia

Bundle `INTEGRACION_GAP_COLOR_RECOVERY_FINAL`, carpeta `BACKUP_CONGELADO/`
(`main.py`, `main_teensy.cpp`), copiados byte por byte. No es la version
`RASPBERRY/` + `TEENSY/` del mismo bundle: esa es posterior y **no es la que se
probo**. Diferencia del lado del firmware entre lo que habia sin commitear en
el worktree y lo congelado: `RECUP_GIRO_MAX_GRADOS` 60 -> **58**.
