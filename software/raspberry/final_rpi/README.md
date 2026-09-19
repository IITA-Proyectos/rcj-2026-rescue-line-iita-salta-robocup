# Visión de línea — qué corre hoy, y cómo se llegó acá

---

## Lo primero, porque es lo que más se malentiende

> **Hoy el robot NO corre con el planner. Corre con el `atan2` de toda la vida.**

`Main.py:41-44` lo dice:

```
VISION_LINEA=camino python3 Main.py    candidata + CAMINO + MONO
VISION_LINEA=v1     python3 Main.py    POI sobre contorno
python3 Main.py                        visión vieja, sin cambios   ← el default
```

Sin la variable de entorno, `vision_linea.MODO` queda vacío y el módulo **no se
activa**. El ángulo sale de una línea sola, `Main.py:887`:

```python
angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90
```

El centroide de la mancha negra del ROI, y el `atan2` de sus componentes. **No hay
camino, no hay esqueleto, no hay lookahead.** Eso llega recién con `VISION_LINEA`.

**Por qué importa para todo lo demás:** todos los CSV del 22-ago, y por lo tanto
todos los números de `../../../analisis/`, son del **`atan2`**. Si se enciende el
planner, la distribución de ángulos cambia y hay que rehacer las cuentas. Por eso
la telemetría tiene la columna `ang_viejo` — con el planner encendido, **una sola
corrida da las dos leyes a la vez** y el A/B sale sin pasada extra.

---

## Cómo se llegó a esto

Vale la pena contarlo porque el método sirve más que el resultado.

Durante semanas se buscó el problema **en la percepción**: que la cámara no viera
bien, que el target cayera en la cinta equivocada, que el latigazo del ángulo
rompiera el seguimiento. Se probaron ROI adaptativo, poda del grafo, suavizado,
bird-eye, salida lateral, límites de pendiente. **Trece hipótesis, todas muertas**,
y la percepción resultó estar bien: el target cae en la cinta correcta el 50/50 de
la verdad de terreno, es estable el 99,8 % del tiempo y apunta bien el 97,3 %.

El giro vino de un comentario de Benjamín, y fue lo que destrabó todo: **que se
usaran las fórmulas, y que se probara.** No buscar más síntomas en el video —
escribir la física y ver si cierra.

Y cerró en cuatro renglones. `drivebase.cpp`, dentro de `DriveBase::steer()`:

```cpp
_rightspeed = _speed;                        // rueda externa
_leftspeed  = _speed * (1 - 2*rotation);     // rueda interna
```

De ahí sale, sin medir nada todavía, sólo despejando:

```
v_centro = vel · (1 − rot)
ω        = 2 · vel · rot / b_eff
R        = v_centro / ω = b_eff · (1 − rot) / (2 · rot)
```

**Dos cosas que ninguna cantidad de video iba a mostrar:**

1. **`R` no contiene `vel`.** Subir la velocidad sube el giro y el avance en la
   misma proporción: **el radio no se mueve.** Eso mató de una la idea de subir
   `LINE_PIVOT_SPEED`, que era la línea de trabajo principal.
2. **En `rot = 1` el centro del robot no avanza.** No es un efecto raro: es la
   definición del pivote. Y el robot se pasa ahí una parte grande del tiempo.

Lo mismo pasó del lado de visión: el planner no salió de mirar más frames, salió de
escribir qué era un camino sobre el esqueleto y qué significaba "adelante".

**Y después de la fórmula, medir.** Los CSV del Teensy tenían el giroscopio y los
encoders en la misma fila desde el 22-ago y nadie los había cruzado con el comando.
De ahí salieron los tres números que hoy sostienen todo:

| | valor | cómo |
|---|---|---|
| diámetro efectivo de rodadura | **6,88 cm** | la calibración de `runDistance()`, que ya estaba escrita en el TDP |
| ancho de vía efectivo `b_eff` | **20,9 cm** | `dv_encoder / gz_giroscopio` |
| factor de apertura | **1,15** | el robot no traza el radio que pide, **se abre** |

Ninguno salió de un sensor nuevo ni de una corrida nueva. Salieron de cruzar
columnas que ya estaban grabadas, una vez que la fórmula dijo **qué** cruzar.

### La parte incómoda, que también es método

En dos días **murieron cinco hipótesis**, la mayoría propias, porque cada una tenía
escrito **de antemano** qué resultado la mataba. Un factor de apertura de 1,7 que
resultó ser ruido de un solo tramo. Una firma de oscilación que era generalizar
desde 13 episodios elegidos. Un `steer = 0` que parecía la falla y resultó ser el
cruce de gap funcionando **bien**. Un radio de 4,9 cm citado como del reglamento que
**no está en el reglamento**.

Que se cayeran no fue el problema: fue el control de calidad funcionando. Lo que
hubiera sido caro es enterarse el sábado, con el robot en la pista.

---

## Los archivos

### Producción

| archivo | qué hace |
|---|---|
| `Main.py` | el lazo. Acá está el `atan2` y el protocolo a la Teensy |
| `camthreader.py` | captura de cámara en hilo |
| `calibration.py` | calibración de color |

### El pipeline nuevo — **apagado salvo que se pida**

| archivo | qué hace |
|---|---|
| `vision_linea.py` | el enchufe. Sin `VISION_LINEA` no importa nada pesado |
| `nuevo_code_v2.py` | el grafo del camino. **Acá vive `LOOKAHEAD = 70`** |
| `camino_principal.py` | elige la cadena principal del esqueleto |
| `continuidad.py` | el cap de continuidad entre frames |
| `ley_steer.py` | separa error de posición de error de rumbo |
| `telemetria_vision.py` | el registro de 49 columnas, con las 5 etapas del target |

### Análisis

Están en `../../../analisis/` del repo de Roboliga, con su README. Acá quedan los
que dependen de este pipeline, y **`simular_leyes.py`**, que corre las cinco
soluciones candidatas contra el drivebase **offline**, sin robot.

---

## Tres cosas para no tropezar

**El replay sobre video es lazo abierto.** Mide qué vio la cámara, **no** por dónde
pasó el robot. Para trayectoria, los CSV del Teensy.

**`LOOKAHEAD = 70` px no es una distancia del suelo.** Son píxeles geodésicos sobre
el esqueleto, con la cámara mirando casi horizontal. Y nadie lo barrió todavía —
ojo que **más lookahead es más amortiguación**, o sea **menos** reacción en curva
cerrada.

**Stanley es experimental y está apagado.** Pasa sus cinco falsadores y un gate
15/15, y cuesta 19 µs. Pero **no es el Stanley de Thrun**: es un controlador
inspirado en su estructura, y la demostración de convergencia **no aplica**.
