# Los números del codo — medidos el 26-ago-2026

> ## ⚠️ CORREGIDO tras la auditoría de ChatGPT (26-ago)
>
> Este documento tenía **tres afirmaciones más fuertes que la evidencia**. Se
> corrigen abajo y se deja escrito qué decía antes:
>
> 1. **«avance por grado» → «RECORRIDO DE RUEDA por grado».** No es traslación
>    del centro: sale de encoders de **un solo canal** con el signo **inferido
>    del comando**, en un skid steer que patina. `recorrido de rueda / giro ≠
>    traslación del centro / giro`.
> 2. **Publicaba sólo la mediana (0,080).** La dispersión es enorme —
>    **el p90 es 6,9× el p25**— y esconderla fue parte del problema.
> 3. **Publicaba `7,3 cm/rad` y `0,080 cm/°` juntos, y no cierran** (0,080 cm/°
>    = 4,58 cm/rad). No era un error de aritmética: son dos estimadores sobre
>    poblaciones distintas, pero los presenté como si fueran lo mismo. Y el 7,3
>    era **el peor caso de las seis corridas**, no el típico.
>
> El script único y reproducible que lo resuelve es
> [`recorrido_por_grado.py`](recorrido_por_grado.py).

Salen de las 6 corridas de pista del 22-ago. **Son el presupuesto con el que
tiene que trabajar cualquier solución al codo.**

## El mecanismo, cuantificado

Benjamín: *"no gira en el lugar sino que avanza, y llega un punto donde le queda
casi nada de línea, y ya el atan2 no es que tira mal el ángulo sino que ya no
sabe cuál es el ángulo correcto"*.

| percentil | cm/grado | **en un codo de 90°** |
|---|---|---|
| p25 | 0,033 | 3,0 cm |
| **p50** | **0,080** | **7,2 cm** |
| p75 | 0,154 | 13,9 cm |
| p90 | 0,230 | 20,7 cm |

*(n = 17.430 muestras con `\|gz\| > 25 °/s`, seis corridas, lag 14 aplicado.)*

Y la distancia a la que mira la cámara es **~7–10 cm** — pero **ese número
tampoco está cerrado**: depende del HFOV, que
[no está calibrado](EL-HFOV-NO-ESTA-CALIBRADO.md).

**Lo que se puede afirmar hoy, y nada más que esto:** la escala del recorrido
inferido durante un codo es **comparable** a la escala aparente del horizonte
visual. O sea que el mecanismo que describió Benjamín es **plausible y
consistente con los datos** — pero para declararlo confirmado hacen falta las
dos cantidades medidas **en el mismo sistema de referencia**, y hoy ninguna de
las dos lo está.

Por corrida (p50 de cm por grado):

```
arbol_de_ramas          0,065  →  5,8 cm en 90°
gain18                  0,058  →  5,2
pivote35                0,094  →  8,5
pivote_con_histeresis   0,067  →  6,0
pivote_sin_histeresis   0,093  →  8,4
rampa_continua_pivote20 0,087  →  7,8
```

## El presupuesto de tiempo — cuánto tiene que aguantar sin ver

| girando a | 90° en |
|---|---|
| 42,6 °/s (p50 real) | **2,11 s** |
| 56,8 °/s (p75) | 1,58 s |
| 74,5 °/s (p90) | 1,21 s |
| 80 °/s (45 rpm, medido en banco) | 1,12 s |
| 127 °/s (70 rpm, medido en banco) | **0,71 s** |

**Entre 0,7 y 2,1 segundos.** Si la solución pasa por completar el giro a ciegas
con el BNO055, ese es el lapso que tiene que sostener.

> **CORREGIDO:** antes decía *"el BNO en modo fusión no deriva de forma
> apreciable en ese tiempo"*. **Eso no está demostrado para este robot.** El
> datasheet de Bosch dice que si el magnetómetro se detecta distorsionado la
> fusión puede ignorarlo y el heading **deriva**, y advierte sobre vibración
> prolongada. Y alrededor del BNO hay motores, corriente, acero y vibración.
>
> **Es medible y hay que medirlo**: marca física a 0°, girar, comparar Δψ del
> BNO contra Δψ real del piso, **con motores encendidos y en los dos sentidos**.
> Si repite bien, es un sensor excelente para cerrar la maniobra. Si no, se
> descarta antes de meterlo en producción.

## Lo que hace que sea viable

- el giro **no satura** en el rango medido: 1,69–1,86 °/s por rpm de 15 a 90 rpm,
  en dos binarios
- el PWM llega a **157 de 255** en el punto más exigido
- el motor libre da 495 rpm; en banco cargado llegó a 121; en pista corre a 30–43

> **CORREGIDO:** antes decía *"PWM 157/255 → sobra 38 %"*. **PWM no se convierte
> linealmente en giro bajo carga** — hay fricción, back-EMF, corriente, batería,
> saturación del lazo, scrub de cuatro ruedas y transitorio. Lo que está medido
> es que **el giro escala con la rpm hasta 90**, no que quede un 38 % de
> autoridad disponible. Para eso hace falta la curva `comando → ω` hasta
> encontrar la meseta, sobre la misma superficie.
>
> Y sobre *"a `rot = 1` subir la velocidad no tiene costo"*: **es cierto en el
> modelo** (`v_centro = vel·(1−rot) = 0`), pero este robot no es el diferencial
> ideal. A 70 rpm con `rot = 1` puede aparecer más scrub, más deriva del centro,
> más overshoot, más corriente y peor imagen durante el giro. **El experimento
> correcto no es "la máxima rpm posible" sino "la rpm de pivote que minimiza el
> tiempo sin aumentar la deriva ni el overshoot".**

## Lo que NO está medido

- **el ángulo y el radio de acuerdo de los codos de nuestra pista** — hace falta
  la cinta y el transportador
- **cuánto avanza el robot entre que empieza y termina un codo REAL**, marcado en
  el piso. Lo de arriba es por frame, no por codo completo
- **si el BNO derive o no en 2 s** con los motores andando (hierro y corriente
  cerca). Es medible en banco: girar 90° y comparar contra una marca en el piso
