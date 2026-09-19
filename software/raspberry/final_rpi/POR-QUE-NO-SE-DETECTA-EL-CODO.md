# Por qué el codo no se detecta sobre el esqueleto — y qué hay que atacar

_26-ago-2026 · dos implementaciones independientes llegaron al mismo número_

---

## El resultado

| | eventos/min | límite del falsador |
|---|---|---|
| detector por concentración (mío) | **16,2** | 6 |
| detector por concentración local (workflow) | **17,0** | 6 |

**Los dos fallan, y por casi el mismo margen.** Cuando dos implementaciones
distintas del mismo principio llegan al mismo resultado, el problema no está en
ninguna de las dos.

---

## La causa raíz, medida

`nuevo_code_v2.py:395` ya lo decía: *«con la cámara casi horizontal la cinta
ocupa ~65 px de ancho»*. Medido sobre 4.823 muestras de tres videos:

| fila | ancho de la mancha | % del ancho de la imagen |
|---|---|---|
| **115** (cerca del robot) | **71 px** (p90: 102) | **44 %** |
| 105 | 65 px | 41 % |
| 95 | 58 px | 36 % |
| 85 | 50 px | 31 % |
| 75 | 43 px | 27 % |

> **El eje medial de una mancha de 71 px puede desviarse ±35 px sin que la cinta
> doble absolutamente nada.**

Ese ruido es **mucho mayor** que la señal que se quiere medir. Y es geométrico,
no de umbral: la cinta real mide 1–2 cm, pero vista casi de canto ocupa medio
cuadro, y su esqueleto serpentea dentro de esa mancha.

## Los dos números que lo demuestran

**1. La concentración no separa.** Sobre el codo real de `hist.avi` f1350–1365
contra tramos rectos de `lineal.avi`:

```
CODO real    concentración p50 = 0,576    rango 0,45 – 0,64
NO codo      concentración p50 = 0,544    rango 0,43 – 0,83
```

**6 % de diferencia, y los rangos se solapan casi por completo.** Apunta en el
sentido correcto y no discrimina nada.

**2. Y no es que el estimador esté mal formulado.** El detector del workflow, con
una normalización distinta (contraste local contra las propias patas en vez de
fracción del total), **sí separa sobre geometría limpia**: un hairpin que gira
37,5° en la ventana da razón 1,02 (rechazado) y un codo que gira 27,9° da 5,31
(aceptado). *Mismo giro, veredicto opuesto* — que es exactamente lo que se busca.

**Pero sobre el material real da 17 eventos/min igual.** Su propia prueba de
control: usar la peor de las dos patas en vez del promedio —que es lo correcto si
las patas de un codo son rectas— **empeora las dos cosas a la vez**.

---

## Qué hay que atacar, entonces

**La cadena, no el discriminador.** Tres caminos, en orden de lo que cuesta:

| | idea | por qué podría funcionar |
|---|---|---|
| **1** | medir el rumbo sobre los **BORDES** de la cinta, no sobre el eje medial | los bordes son dos curvas casi paralelas; su dirección es mucho menos ruidosa que el eje de una mancha gruesa |
| **2** | ajustar **rectas por tramos sobre la máscara** en vez de recorrer el esqueleto | usa todos los píxeles de la mancha, no una línea de un píxel de ancho |
| **3** | subresolución del esqueleto | el más barato, pero sólo ataca el ruido de discretización, no el de anchura — que es el grande |

**La (1) es la que más promete y no está probada.** El eje medial tiene ±35 px de
libertad; el borde de la cinta tiene la que le da el umbral de la máscara, que es
mucho menos.

---

## Y una pista que salió de mirar un frame

En `hist.avi` f322 → f324, en el instante del codo, **la cadena pasa de vertical a
horizontal**: la cinta deja de irse hacia adelante y cruza el cuadro de lado a
lado. Ahí los dos extremos de la cadena son geométricamente igual de válidos, y
el `raw` saltó al extremo opuesto de donde venía (+24,2° contra los −35,4° que se
mandaron; el cap de continuidad lo corrigió **por memoria**, no por percepción).

> **Cuando la cadena se vuelve horizontal y el `raw` salta al extremo opuesto, el
> robot está encima del vértice.**

Eso es una señal de **orientación de la cadena entera**, no de curvatura local —
o sea que **no la afecta el ruido del eje medial** de la misma forma. Es la
candidata más barata que queda.

**No está medida.** La vi en tres frames. Antes de creerle hace falta el falsador
y la tasa base, igual que todo lo demás.

---

## Lo que sigue faltando, y bloquea todo

**El dataset de codos etiquetados a mano.** El agente que lo iba a construir murió
por caída de conexión. Sin él, todo lo de arriba mide **tasa de disparo**, nunca
**precisión**: no se puede saber si esos 16–17 eventos por minuto son codos reales
o ruido.

Es el mismo P0 que marcó ChatGPT, y ya bloqueó dos intentos.
