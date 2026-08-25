# Traspaso — 25-ago-2026, noche

**Rama `collab/nuevo-code` · `aef4c42` → `6b1d0b9` · 38 commits en un día**

Este documento **reemplaza** a `TRASPASO-2026-08-25.md` (el de la mañana) para
todo lo que respecta al diagnóstico. El de la mañana sigue valiendo como
inventario de lo que existe y de las trece hipótesis muertas; lo que cambió es
**dónde está el problema**.

---

## 0. Lo primero, y cambia el orden de todo

> **La curva más cerrada del reglamento no es físicamente posible a la velocidad
> a la que el robot iba.**

Medido con los CSV del propio robot (`software/teensy/firmware/corridas/`,
22-ago, seis corridas de pista, giroscopio del BNO055):

```
el robot avanza a           8,5 cm/s      (RPM del encoder, p50 = 25)
giro sostenido p90          54,8 °/s      (giroscopio, no correlación de fase)

curva más cerrada (R = 4,9 cm, RCJ 2.2.2: radio interno ≥ 40 mm)
    v_max admisible          4,7 cm/s
    el robot va a            8,5     →   82 % POR ENCIMA
    la curva EXIGE          99 °/s       y el robot da 55

curva suave (R = 15 cm, cuarto de círculo en un tile de 30)
    v_max admisible         14,3 cm/s
    el robot va a            8,5     →   OK, 59 % del límite
```

`v_max = ω_max · R`. Es el **punto 1** del checklist de
`seguimiento-de-trayectoria`, el que dice que suele cerrar el caso, y **nunca se
había calculado con datos del robot**.

**No es que el controlador elija mal: no existe una trayectoria que tome esa
curva a esa velocidad con ese giro.** Y la curva suave **sí** da — que es
exactamente coherente con *«se sale en las curvas cerradas»* y no en todas.

### Y es robusto al diámetro de rueda

Se barrió todo el rango plausible (44 a 85 mm). El robot queda entre **24 % y
137 % por encima** del límite en todos. Para que la curva fuera posible la rueda
tendría que medir **3,58 cm**. Con gomas o sin gomas, con el CAD o con el
encoder, el veredicto no se mueve.

### Las tres salidas, y hay que elegir una

| | qué | costo |
|---|---|---|
| **1** | **frenar en curva** hasta ≤ 4,7 cm/s | pierde tiempo de corrida |
| **2** | **subir el giro** — el techo **no** es físico: es `LINE_PIVOT_SPEED` × la ganancia. **Hay que barrer el parámetro** y confirmar que la respuesta se aplana antes de declarar un techo | issue #2 de Roboliga |
| **3** | **girar en el lugar** | determinista pero caro: ~2,3 s por cada 90° |

**Y una ironía que hay que decir:** la salida 1 es exactamente la anticipación de
curva que se refutó esta misma mañana. Su evidencia estadística no valía —el test
tenía el bug del *«al menos uno»*— pero **la razón física para frenar antes de
una curva cerrada apareció por otro lado, y esta vez con una desigualdad.**
Refutar el test no refutó el mecanismo.

---

## 1. Qué cambió respecto del traspaso de la mañana

| | mañana | noche |
|---|---|---|
| el problema | la percepción y la ley de steer | **la cinemática** |
| el retardo de 65-70 ms | «el hallazgo más grande» | **0,53 cm de avance. No es mucho** |
| la anticipación de curva | «84 % con ~1 s» | evidencia **refutada**, mecanismo **revivido por física** |
| el `atan2` | mezcla posición y rumbo | **sí traduce rumbo a comando**, y no explica la falla |
| dónde mirar | el video de replay | **los CSV del robot** |

---

## 2. El retardo, en centímetros

La pregunta era *«¿65-70 ms es mucho?»*. Con las RPM del encoder:

```
el robot avanza a     8,5 cm/s
en 70 ms avanza       0,53 cm    = un cuarto del ancho de la cinta
                                 = 7 % del arco de una curva de 90°
y gira                1,4°       = 2 % de los 90
```

**No, no es mucho.** Y las RPM son creíbles: la consigna y la medida coinciden
(16/16, 20/19, 20/20), con caída sólo en las dos corridas de pivote (43/32,
41/30) — justo donde el skid steer patina.

### Pero el diagnóstico del lazo se confirmó entero, con el sensor bueno

```
período del lazo    p50 35 ms, modo principal 30-35 (32,5 %)
                    SEGUNDO MODO en 60-70 ms (20,2 %)
lag comando→giro    13-14 muestras × 5 ms = 65-70 ms
el comando CAMBIA   8,8 a 20,6 veces por segundo
el robot OBEDECE    76-87 % en pista, 95-99 % en banco
```

Los tres números de la sección 3.1 del traspaso de la mañana salen **iguales**,
pero medidos contra el **giroscopio del BNO055** y no contra la correlación de
fase sobre el fondo (que es el estimador débil que se venía usando).

**Y el segundo modo en el doble exacto** es la firma de una espera enganchada a
un reloj de hardware — que es exactamente lo que los fixes de esta tarde atacan.

**Estas diez corridas son el baseline.** Son de *antes* de los fixes: el sábado
alcanza con volver a grabar y comparar.

---

## 3. Lo que se hizo hoy, por bloque

### 3.1 Separar posición de rumbo — `4f91eb0`, `8101c10`

`δ = ψ + arctan(k·e/v)`. Módulo puro (`ley_steer.py`), **apagado por defecto**:
`VISION_LINEA=camino LEY_STEER=stanley`.

Los cinco falsadores de `FALSADOR-STANLEY.md` sobreviven, gate **15/15** en la
banda HFOV 45/60/75 × arco 0,30–1,30. Cuesta **19 µs**, el 1,8 % de un paso.

**Un defecto grande que encontró Benjamín mirando el registro:** `e` se medía en
el `start` (un nodo del **esqueleto**) y no en la cinta. Sesgo p50 **14 px**,
p90 **35**, máx **152**, con el 58,5 % de los frames arriba de 10 px. Corregido
con `entrada` (centroide de la componente en sus 3 filas más bajas): el comando
cambia p90 **44,8°** y el 55,9 % de los frames se mueve más de 10°.

Y una **validación cruzada** que no se fue a buscar: el `atan2` correlaciona
**−0,642 con `entrada`** y sólo **−0,301 con `start`**. La ley que lleva años
andando ya estaba del lado correcto.

### 3.2 Telemetría — `01a64c0`, `08043d3`, `7642693`, `1eef449`

El CSV pasó de 18 a **48 columnas**, todas al final. Las **cinco** etapas del
target (`raw → cap → geo → bra → tg`), `ctrl_source` (quién manda), `vl_activa`,
y los cuatro campos de cámara (`cam_seq`, `cam_edad`, `cam_rep`, `cam_salt`) que
eran el único eslabón del retardo sin instrumentar.

El que más va a servir: **`ang_viejo`**, lo que la ley de hoy habría mandado en
ese mismo frame. El A/B de leyes sale de **una sola corrida real**.

### 3.3 Firmware — `a553a6b`

El ping frontal costaba **8,6 ms por vuelta** y el caso normal *era* el peor caso
(`ping_cm()` bloquea hasta el timeout cuando no hay eco). Y **no hay un solo
`Wire.setClock()`** en las 4.146 líneas: el I2C corre a 100 kHz.

Cuatro flags: `kFixPingFrontalCorto` ✅ (8578 → 1738 µs), `kFixPingFrontalPeriodico`
✅ (costo medio → 87 µs), `kFixI2cRapido` ❌ **apagado** (puede colgar el bus),
`kFixTofPresupuesto` ✅ (33 → 20 ms). Compila. **Sin banco.**

### 3.4 Serie — `55e8dea`

`ser.flush()` bloqueaba **5,6 % del tiempo** del lazo de visión sin que nadie
esperara esa garantía. Apagado, reversible con `SERIAL_FLUSH=1`.

**Pendiente y sin hacer:** subir el baud de 115200 a 460800 (−75 % de tiempo de
trama). Hay que cambiarlo en **los dos lados a la vez**.

### 3.5 V1 — `b6ef35a`

`RETR_LIST` → `RETR_EXTERNAL`. El contorno elegido **era un agujero de reflejo en
295 de 13.900 frames**. Ninguna métrica empeora; `saltos>24` baja de 928 a 910.

### 3.6 El registro visual — `7dd2a18`, `30a5e84`

`REGISTRO_COMPLETO.mp4`: los 10 autónomos seguidos, **13.900 frames, 6:56**, con
las cinco etapas, la `entrada`, el arco de `ψ`, y **un transportador** con las
dos leyes y la aguja que manda marcada con un punto. `indice_video.py` da los
minutos donde pasa algo.

---

## 4. Lo que murió hoy

| | por qué |
|---|---|
| **la anticipación de curva** (3.7 del traspaso de la mañana) | el test buscaba «al menos un `kappa > U` en 40 frames» **sin `break`**. Rehecho con precisión/tasa base/placebo: lift máx **1,47×** base y **1,26×** placebo, bajo el 1,5 preregistrado. Lo encontró ChatGPT |
| **«el `atan2` no ve el rumbo»** | con el robot centrado, `\|atan2\|` **crece monótonamente** con `\|ψ\|`: 26,7 → 65,6 |
| **«mezclar posición y rumbo causa la falla»** | no anticipa la pérdida de línea: RR **0,45–0,84×** (menor que 1), con control de sanidad a 5,4× |
| **«lo que cambia es *cuándo*»** | correlación cruzada: lag óptimo **0 o ±1 frame** en los tres pares. No hay desfase |
| **«el retardo explica la falla»** | en la falla el robot **dejó de obedecer** (corr 0,92 → 0,52), no obedeció tarde |

---

## 5. Errores míos de hoy, retractados

1. **El extractor cuantizaba la velocidad** a 1/100. Apareció como 1.098
   discrepancias de hasta 0,18°.
2. **`_RAZON` mapeaba estados** (HIGH/MEDIUM) cuando `reason` sale de `mode`
   (NEAR/AHEAD). Dejaba el 93 % de los frames en 0.
3. **`geo` no era el target geométrico**: ya venía con dos guards aplicados. Un
   log del sábado habría dicho «el planificador eligió esto» y era falso.
4. **Culpé mal a las 10 discrepancias de `con_planner`**: dije que era mi espía
   llamando dos veces; puse el espía y dieron las mismas 10.
5. **«d_eje no importa»** era demasiado fuerte: el cross-track canónico y el mío
   difieren en `d_eje·sin(ψ)`, y con ψ ~45° el factor es 0,71.
6. **«calibración sin tuning»** — es inicialización mirando el dataset.
7. **«las costillas no están, por construcción»** — falso: si una costilla es el
   nodo más lejano, la cadena *es* la costilla.
8. **«lo que cambia es cuándo»** — vago, y en el sentido temporal falso.
9. **`git add -A`** arrastró al commit `7642693` archivos que no eran míos
   (`leyes_*.csv`, `wf_slew.py`, `wf_suelo_camino.py`) y 60 MB de `.avi`. Los
   `.avi` salieron del seguimiento; **el blob sigue en la historia** y sacarlo
   es decisión de Benjamín.
10. **El test de telemetría** contaba 48 «desviaciones» que eran el límite exacto
    del `round()`. El test estaba mal, no el código.

---

## 6. El sábado, reordenado

El orden de la mañana ponía el fix del ToF primero. **Ya no.**

### Fase A — la cuenta, 0 minutos de robot

Confirmar el diámetro en Fusion y el valor actual de `LINE_PIVOT_SPEED`. Con eso
se cierra el número exacto de cuánto hay que frenar o cuánto subir el giro.

### Fase B — barrer `LINE_PIVOT_SPEED`, ~20 min

**Es la salida 2 y es la única que no cuesta tiempo de corrida.** El techo de
39 °/s nunca fue físico. Subir el parámetro y medir `gz` hasta que la respuesta
**se aplane**. Si llega a 99 °/s, la curva cerrada pasa a ser posible sin frenar.

Falsador: si `gz` **no sube** al subir el parámetro, ahí sí hay un techo físico
(motor, batería o tracción) y la única salida es frenar.

### Fase C — medir `d_eje`, ~20 min

`COMO_MEDIR_D_EJE.png` tiene los cuatro pasos. Desbloquea la escala, y con ella
saber si `LOOKAHEAD = 70` rompe la cota `ℓd ≤ 2R` — que con `d_eje ≥ 9,8 cm`
está **fuera sin importar nada más**.

### Fase D — el fix del lazo, ~30 min

Volver a grabar con `diagnostico_fix` y comparar contra el baseline del 22-ago.
Falsador: p50 de 35 ms → **< 5**, y la frecuencia de cambio del comando de
8,8–20,6 Hz → **> 50**. Si el período baja y la frecuencia **no** sube, el cuello
no era el lazo.

### Fase E — un cambio por fase, y en este orden

`VISION_LINEA=camino` **solo** (es el salto más grande: 12,2 % de frames con el
comando dado vuelta contra el `atan2`), después `LEY_STEER=stanley`, después
`VEL_ANTICIPADA=1`. **Nunca los tres juntos.**

---

## 7. Lo que sigue abierto

- **`LOOKAHEAD = 70` px** puede ser el bug, y se decide con `d_eje`.
- **El baud del serie**, 115200 → 460800. Los dos lados a la vez.
- **`kFixI2cRapido`**, apagado hasta que haya 10 minutos de banco.
- **El watchdog**: el tercer problema que señaló ChatGPT (bytes viejos drenados
  al volver de una maniobra bloqueante) sigue **sin arreglar**.
- **3.5.2, el lookahead no es una distancia física** — Stanley no lo arregla, lo
  esquiva.
- **3.5.3** — todavía **2,7 %** de frames con el camino apuntando hacia atrás.
- **`t_mono_ns`** en la telemetría, para cruzar con el Teensy sin ambigüedad.
- **Rampa y plateado**: `docs/estado.md` del repo de Roboliga dice que el 2 de
  julio el robot no subió las rampas y no detectó el plateado. **Esta sesión no
  lo tocó.**

---

## 8. Herramientas nuevas de hoy

| archivo | qué contesta |
|---|---|
| `factibilidad.py` | **¿la curva es posible a esa velocidad?** ← el hallazgo |
| `cuanto_es_el_retardo.py` | el retardo en cm y en grados |
| `retardo_real.py` | período, lag y obediencia, con los CSV del robot |
| `ley_steer.py` | la ley de Stanley y la geometría de suelo |
| `sep_pos_rumbo*.py` | los cinco falsadores de la separación |
| `curva_cerrada2.py` | la anticipación, rehecha con placebo |
| `tres_leyes.py` | `atan2` vs lineal vs Stanley |
| `porque_el_atan2.py` | por qué el `atan2` no explica la falla |
| `precursor_perdida.py` | el conflicto no anticipa la pérdida |
| `obedecio_el_robot.py` | en la falla dejó de obedecer |
| `anticipacion.py` | de dónde puede salir anticipación |
| `embudo.py` | dónde se pierde lo que la visión ve |
| `sesgo_start.py` | el defecto que encontró Benjamín |
| `para_que_d_eje.py` | qué está en juego al medirlo |
| `video_completo.py` · `indice_video.py` | el registro y dónde mirar |
| `que_mira_cada_ley.py` · `dibujar_medicion_eje.py` | las dos figuras |
| `PRESUPUESTO-LAZO.md` · `MEDIR-EL-RETARDO.md` | los dos documentos de método |

---

## 9. Las reglas, sin cambios

Las ocho del traspaso de la mañana siguen valiendo. Hoy se usaron todas y
**cinco hipótesis murieron por ellas**, cuatro de ellas mías.

Y una que esta sesión agregó, por las malas:

> **Antes de instrumentar, preguntá qué mide realmente el campo que vas a usar.**
> `dt` parecía el período del lazo y era el del registrador — un IntervalTimer de
> hardware a 200 Hz. El número correcto salía de otra columna.

---

## 10. Canal

Issue **#138** — dos comentarios hoy. La auditoría de ChatGPT del 25-ago está
respondida punto por punto: los cuatro hallazgos verificados en el código y
corregidos, y las cuatro correcciones de alcance aceptadas.
