# Los números del codo — medidos el 26-ago-2026

Salen de las 6 corridas de pista del 22-ago. **Son el presupuesto con el que
tiene que trabajar cualquier solución al codo.**

## El mecanismo, cuantificado

Benjamín: *"no gira en el lugar sino que avanza, y llega un punto donde le queda
casi nada de línea, y ya el atan2 no es que tira mal el ángulo sino que ya no
sabe cuál es el ángulo correcto"*.

| | valor | qué significa |
|---|---|---|
| **avance por grado girado** | **0,080 cm/°** (p50) | |
| **→ en un codo de 90°** | **avanza 7,2 cm** | |
| distancia a la que mira la cámara | ~7–10 cm | **el robot consume TODA su distancia de mirada dentro del codo** |
| largo del robot | 15,7 cm | |

**Ese es el número que explica la falla.** Para cuando termina de girar 90°, el
punto que la cámara miraba al entrar al codo ya le quedó debajo o detrás.

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
con el BNO055, ese es el lapso que tiene que sostener — y el BNO en modo fusión
no deriva de forma apreciable en ese tiempo (no es integración pura del
giroscopio).

## Lo que hace que sea viable

- el giro **no satura**: 1,69–1,86 °/s por rpm de 15 a 90 rpm, en dos binarios
- el PWM llega a **157 de 255** en el punto más exigido → **sobra 38 %**
- el motor libre da 495 rpm; en banco cargado llegó a 121; en pista corre a 30–43

**El robot puede girar mucho más rápido de lo que gira.** Ir a 70 rpm en el codo
bajaría el tiempo a ciegas a 0,71 s, y a `rot = 1` subir la velocidad **sí** sube
el giro sin costo (porque con `rot = 1`, `v_centro = 0` y no hay avance que
compensar).

## Lo que NO está medido

- **el ángulo y el radio de acuerdo de los codos de nuestra pista** — hace falta
  la cinta y el transportador
- **cuánto avanza el robot entre que empieza y termina un codo REAL**, marcado en
  el piso. Lo de arriba es por frame, no por codo completo
- **si el BNO derive o no en 2 s** con los motores andando (hierro y corriente
  cerca). Es medible en banco: girar 90° y comparar contra una marca en el piso
