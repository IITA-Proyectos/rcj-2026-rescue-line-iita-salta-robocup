---
name: geometria-camara-suelo
description: Convierte lo que ve la cámara en distancias y ángulos del piso, con hardware fijo. Fila del horizonte y el modelo Z = k/(v − v_h), escala lateral, cuánto suelo vale un píxel según la fila, por qué el mapeo lineal columna→grados no es un ángulo y cuál es su error real, el bearing desde el EJE DE ROTACIÓN y no desde el centro óptico (d_eje), cómo medir d_eje con papel y regla, y cuándo la proyección al suelo vale la pena contra IPM completo. Usar cuando aparezca una constante en píxeles que se trate como distancia, cuando se llame "grados" a algo que no lo es, cuando haya que comparar dos leyes de steer, cuando la cámara mire casi horizontal, o antes de tocar LOOKAHEAD.
---

# geometria-camara-suelo

Sos experto en la geometría que conecta **columna y fila de imagen** con
**distancia y ángulo en el piso**, en un robot de RoboCupJunior Rescue Line con
la cámara **montada fija y sin posibilidad de moverla**.

## La regla que ordena todo

> **Un número en píxeles no es una distancia y un número escalado a ±90 no es un
> ángulo.** En el momento en que un píxel se compara con un umbral físico —una
> velocidad, un radio, un techo de grados por segundo— hay que convertirlo
> primero. Si no, se están sumando peras con metros.

---

## 1. El modelo de suelo plano

Cámara pinhole mirando un plano, sin roll. Con `v` = fila de imagen y `v_h` =
fila del horizonte:

```
distancia hacia adelante     Z(v) = k / (v − v_h)
escala lateral               s(v) ∝ (v − v_h)
ancho aparente de una cinta  w(v) = a · (v − v_h)
```

`v_h` y `a` salen de **una sola foto**: poné una cinta de ancho conocido a lo
largo del eje de avance, medí su ancho aparente en cada fila, ajustá la recta
`w = a·v + b`, y el horizonte es `v_h = −b/a`. En el robot de IITA ese ajuste dio
**R² entre 0,982 y 0,999 en 9 de 11 videos**, con `v_h` mediana **+9,0** sobre
una imagen de 120 filas.

### La tabla que hay que tener en la cabeza

Con `v_h = 9` en una imagen de 120 filas, normalizando `Z(119) = 1`:

| fila v | Z relativa | cuánto suelo vale 1 píxel de alto |
|---|---|---|
| 119 | 1,0× | 1× |
| 80 | 1,55× | 2,4× |
| 60 | 2,16× | 4,7× |
| 40 | 3,55× | 12,6× |
| 30 | 5,24× | **27×** |
| 20 | 10,0× | **101×** |
| 15 | 18,3× | **336×** |

**Con la cámara casi horizontal, el mismo píxel puede valer 300 veces más suelo
arriba que abajo.** Cualquier criterio "a N píxeles" es en realidad un criterio
con una escala física que varía dos órdenes de magnitud dentro del cuadro.

Ese es exactamente el motivo por el que ningún equipo top monta la cámara así
—el campeón mundial 2024 la monta a 10 cm mirando **directamente hacia abajo**,
con lo cual el plano del suelo queda fronto-paralelo y la imagen ya *es* una
vista cenital escalada. **Si el hardware no se puede tocar, hay que compensarlo
en software, no ignorarlo.**

---

## 2. El bearing depende SOLO de la columna (y por qué eso engaña)

Del modelo: `X ∝ (u − cx)/(v − v_h)` y `Z ∝ 1/(v − v_h)`. Dividiendo,

```
X / Z = c · (u − cx)
```

**El `(v − v_h)` se cancela: la tangente del bearing hacia el target, medida
desde el centro óptico, depende sólo de la columna.** La fila no entra.

De acá salen dos conclusiones que parecen contradecirse y no lo hacen:

- La **medición de dirección** es robusta: no se corrompe porque el target esté
  más cerca o más lejos.
- El **lookahead** sí importa igual, porque fija la ganancia del lazo
  (`2/ℓd²`), no la dirección. Ver `seguimiento-de-trayectoria`.

---

## 3. El bearing que le importa al robot no es el del centro óptico

Hay **tres** bearings distintos y usar el equivocado invalida cualquier
comparación de leyes de steer:

| desde dónde | fórmula | para qué sirve |
|---|---|---|
| centro óptico | `atan(c·(u − cx))` | es lo que la cámara mide |
| borde inferior de la imagen | `atan2(kx·X, kz·(Z_base − Z))` | es lo que devuelve un bird-eye |
| **eje de rotación del robot** | `atan2(X, Z + d_eje)` | **es el que hay que comandar** |

`d_eje` es la distancia entre el eje de rotación del robot y el punto del piso
que cae en la fila más baja de la imagen. **No está en ningún video ni en ningún
CSV.** Es un dato del montaje físico.

### Por qué no se puede sacar de la telemetría

Tentación clásica: correlacionar el `rot` comandado contra el `gz` medido del
giroscopio. **No sirve: el robot giró OBEDECIENDO a `rot`, así que `rot`
correlaciona con `gz` por construcción.** Es circular. Se necesita una medición
externa.

---

## 4. Cómo medir `d_eje` con papel y regla (~20 minutos)

El truco que lo vuelve una regresión lineal: si medís con regla la distancia `D`
desde el eje hasta el punto del piso que cae en la fila `v`, entonces

```
D(v) = k/(v − v_h) + d_eje
```

que es **una recta en `x = 1/(v − v_h)`**, y **la ordenada al origen es
`d_eje`**. Sale por mínimos cuadrados con residuos y R². No hace falta calibrar
la cámara ni desarmar nada.

### Paso 0 — el eje de rotación real, que no es el geométrico

Con 4 ruedas fijas el centro de rotación **se corre hacia el eje delantero y
depende de la superficie**. Se encuentra así, y es exacto para un cuerpo rígido:

1. Hoja de papel bajo el robot, pegada al piso.
2. Marcar en el papel **dos** puntos del chasis (plomada sobre el centro del
   paragolpes y sobre el centro trasero).
3. Pivotear en el lugar ~90°.
4. Marcar **los mismos dos** puntos en la nueva pose.
5. Unir cada punto con su nueva posición → dos segmentos. Trazar la
   **mediatriz** de cada uno. Se cruzan en el centro de rotación.
6. Repetir pivoteando al otro lado y promediar.

> Si los dos cruces difieren más de ~1 cm, **anotalo**: el centro de rotación no
> es estable, y eso es un hallazgo sobre el skid steer, no un error de medición.

### Pasos 1–3

1. Foto **longitudinal**: cinta a lo largo del eje de avance → da `a` y `v_h`.
2. **Travesaños**: cinta perpendicular a 3 o 4 distancias, medidas con regla
   desde el centro de rotación al borde **más cercano**. Elegí distancias
   repartidas entre la fila más baja y la mitad del cuadro; si las cuatro caen
   abajo, el ajuste no tiene palanca.
3. Ajustar la recta.

**Criterios de aceptación:** R² ≥ 0,98, `d_eje` > 0, n ≥ 3 travesaños. Con 2
puntos la recta pasa exacta y el R² no dice nada.

**Robustez:** con 2,5 mm de error de regla el ajuste recupera `d_eje` con menos
de 0,32 cm de error, y un `v_h` equivocado en 3 filas sólo lo corre 0,82 cm.

---

## 5. El mapeo lineal columna→grados: dos errores distintos

La ley típica es `steer = ±90 · (u − cx)/(W/2)`. Tiene **dos** problemas y
conviene no confundirlos, porque uno es chico y el otro es grande.

### (a) Error de forma — chico

El bearing verdadero es `θ(s) = arctan(s · tan(HFOV/2))` con `s ∈ [−1,1]`.
Comparado con el lineal **bien escalado**:

| HFOV | máxima desviación de forma |
|---|---|
| 50° | ±0,6° (2,5 %) |
| 60° | ±1,1° (3,7 %) |
| 70° | ±1,8° (5,2 %) |
| 90° | ±4,1° (9,1 %) |
| 120° | ±10,9° (18,2 %) |

**Contraintuitivo:** el error **no** es máximo en los bordes. El lineal coincide
en el centro y en el borde por construcción; el peor punto está a media imagen
(`s ≈ 0,5`), donde el lineal **subestima** el ángulo. Con HFOV ≤ 70° es
despreciable — **el arcotangente no es el problema principal**.

### (b) Error de escala — grande

`±90` en el borde de imagen **independientemente del HFOV**. Si la cámara tiene
60° de campo horizontal, el bearing real en el borde es 30° y estás comandando
90°: **3× de sobreganancia**. Con 90° de HFOV son 2×.

### Cuándo el lineal es válido

Como **ganancia proporcional sobre error de píxel**, sí, y es lo que usan los
equipos campeones. Es inválido en el momento en que:

- al número se lo llama "grados" y se lo compara con un techo físico;
- se lo mezcla con algo que sí es métrico (un lookahead en cm, un feedforward de
  velocidad angular).

> **Regla:** o es una ganancia a sintonizar y entonces no se llama grados, o es
> un ángulo físico y entonces hay que calibrar el HFOV. Las dos cosas a la vez,
> no.

---

## 6. ¿Proyectar al suelo o hacer IPM completo?

Con hardware fijo, esta es la decisión de diseño real.

| opción | qué cuesta | cuándo conviene |
|---|---|---|
| **nada** (todo en píxeles) | gratis | sólo si ningún criterio se compara con una magnitud física |
| **proyección de puntos** (`Z = k/(v−v_h)`, `X = c(u−cx)/(v−v_h)`) | dos divisiones por punto | **casi siempre.** Con calibrar `v_h`, `a` y `d_eje` alcanza |
| **IPM completo** (rectificar la imagen) | una `warpPerspective` por frame | sólo si el algoritmo necesita la **imagen** rectificada, no puntos |

**Por defecto: proyectar puntos, no la imagen.** Si el pipeline elige un target
y después lo convierte en un comando, sólo hace falta proyectar ese punto. En
IITA se probó bird-eye como arquitectura principal y quedó descartado; pero eso
**no** justifica seguir midiendo lookahead en píxeles: son dos cosas distintas.

Y ojo con la zona alta del cuadro: es donde la compresión es máxima **y** donde
la segmentación es peor (una cinta de 1–2 cm mide 1–2 px ahí). Un criterio que
manda el target a filas 20–40 está apostando la corrida al peor lugar de la
imagen.

---

## Checklist

1. ¿Está medido `v_h`? ¿Con qué R²?
2. ¿Alguna constante en píxeles se compara con algo físico?
3. ¿A qué fila cae típicamente el target, y cuánto suelo vale un píxel ahí?
4. ¿La ley de steer se llama "grados"? ¿Está calibrado el HFOV?
5. ¿Está medido `d_eje`? Si no, **cualquier comparación entre leyes de steer
   está usando un origen equivocado y no concluye nada.**
6. ¿Se intentó sacar geometría de la telemetría de comando? Es circular.
