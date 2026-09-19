# Cómo medir qué tan tarde reacciona el robot

**Pregunta de Benjamín, 25-ago:** *«¿entonces para saber qué tan tarde reacciona
el robot a la instrucción?»*

---

## La cadena, y qué eslabón mide cada campo

```
[1]  la cámara captura el frame
      │  edad del frame          cam_edad     (CSV de la Pi)   <- NUEVO, 25-ago
[2]  la Pi empieza a procesarlo
      │  proceso                 proc_ms      (CSV de la Pi)
[3]  la Pi manda los 8 bytes
      │  serie                   ~0,7 ms      8 bytes a 115200, calculado
[4]  la Teensy recibe la trama
      │  espera al lazo          dt           (registrador del Teensy)
[5]  la Teensy la ejecuta
      │  motores + inercia
[6]  el robot gira               gz           (registrador del Teensy)
```

**Clave de unión:** la columna `i` del CSV de la Pi es `frames_sent`, y `rxf`
del Teensy es su contador de tramas completas. Son el mismo número mientras no
se pierda una trama; si al final no coinciden, **la diferencia es exactamente
cuántas se perdieron**, y eso también es un dato.

---

## Lo que ya estaba medido, y lo que no

| eslabón | ¿medido? | valor conocido |
|---|---|---|
| [1]→[2] edad del frame | **NO, hasta hoy** | — |
| [2]→[3] procesamiento | sí | `proc_ms` |
| [3]→[4] serie | calculado | 8 bytes / 115200 = **0,7 ms** |
| [4]→[5] espera al lazo | sí | p50 **30 ms**, 2º modo en 65 (7.673 períodos) |
| [5]→[6] comando→giro | sí | **65–70 ms** de lag, por correlación `rot`↔`gz` |

El agujero era el **primero**, y es el que se acaba de tapar.

### Lo que se agregó hoy (Pi)

`camthreader.py` es el patrón «último frame disponible»: el hilo pisa
`self.frame` a la velocidad de la cámara y `read()` devuelve lo que haya. Eso
está bien —es lo que evita acumular latencia de cola— pero sin sello de tiempo
**el lazo no puede saber si procesó un frame nuevo o el mismo dos veces**.

`read_meta()` devuelve `(frame, seq, edad_ms)`. `read()` sigue igual y sin
cambios. Cuatro campos nuevos en el CSV:

| campo | qué dice |
|---|---|
| `cam_seq` | número de frame que la cámara entregó |
| `cam_edad` | ms ×10 desde que **ese** frame se capturó |
| `cam_rep` | acumulado: veces que se procesó **dos veces el mismo** frame |
| `cam_salt` | acumulado: frames que la cámara entregó y el lazo nunca vio |

`cam_rep` y `cam_salt` son los que más van a decir: si `cam_rep` sube rápido,
el lazo de visión corre más rápido que la cámara y la mitad de las decisiones
son aire. Si sube `cam_salt`, es al revés.

---

## El procedimiento, y no necesita nada nuevo

**Una sola corrida**, con las dos telemetrías encendidas:

```bash
TLM_VISION=/home/iita/corrida_retardo.csv VISION_LINEA=camino python3 Main.py
```

y el firmware compilado con `MODO_DIAGNOSTICO=1` (entorno `diagnostico_fix`),
que es el que graba `dt`, `rxf`, `rot` y `gz`.

Después, sobre los dos CSV unidos por `i == rxf`:

1. **Edad del frame:** distribución de `cam_edad`. Es el eslabón nuevo.
2. **Repetidos y salteados:** pendiente de `cam_rep` y `cam_salt` contra `i`.
3. **Período del lazo:** histograma de `dt`. Antes: p50 30 ms con un 2º modo en
   65. Si los fixes de `PRESUPUESTO-LAZO.md` funcionan, tiene que bajar de 5.
4. **Frecuencia con que el comando CAMBIA:** cuántas veces por segundo cambia
   `rxsteer`. Antes: 8,6–20,6 Hz. Tiene que subir de 50.
5. **Retardo comando→giro:** correlación cruzada `rot` contra `gz`, buscando el
   lag que la maximiza. Antes: 65–70 ms.

**El retardo total es la suma de [1] a [6]**, y con esos cinco números sale
entero — con la parte que le toca a cada eslabón, que es lo que permite decidir
dónde seguir.

---

## Los dos falsadores, escritos antes

**F-A (el del lazo, ya escrito en `PRESUPUESTO-LAZO.md`):** el p50 de `dt` tiene
que bajar de 30 ms a menos de 5, y la frecuencia de cambio del comando subir de
8,6–20,6 Hz a más de 50. **Si el período baja y la frecuencia de cambio no
sube**, el cuello no era el lazo del Teensy.

**F-B (el de la cámara):** si `cam_edad` da un p90 por encima de **30 ms**, o si
`cam_rep` crece más rápido que 1 de cada 4 frames, entonces una parte importante
del retardo es de la cámara y **ningún arreglo de firmware la va a tocar**.

Los dos falsadores pueden dar positivo a la vez. Los retardos se suman: no hay
un solo culpable, y la tabla dice cuánto pone cada uno.

---

## Lo que esto NO contesta

Cuánto retardo es **demasiado**. Que el robot reaccione 150 ms tarde es un
número, no un veredicto: si a 30 cm/s eso son 4,5 cm de avance a ciegas, si eso
alcanza para salirse de una curva de radio 5 cm depende de la geometría, y esa
cuenta necesita la escala física que hoy no está medida (`d_eje`).

Lo que sí queda cerrado: **saber dónde se va el tiempo**, que es lo que hoy no
se sabe.
