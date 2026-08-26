# Restricción dura: el detector de codo NO puede volver a las bifurcaciones

_Benjamín, 26-ago, con dos capturas: **«necesito que no tenga las bifurcaciones
del esqueleto al costado como en otras versiones; ya lo arreglaste, no lo vuelvas
a arruinar»**_

---

## Qué muestran las dos capturas

**La mala**: el esqueleto se bifurca y el target (la X blanca) queda puesto en una
**rama lateral corta**, mientras el camino real es la curva grande de la derecha.
El robot va a seguir una costilla del esqueleto, no la cinta.

**La buena**: una sola cadena limpia siguiendo la curva. Sin ramas al costado.

---

## Por qué esto no es un detalle

De `camino_principal.py:14-16`, medido sobre los videos:

```
frames con alguna bifurcación .......... 55,9 %
estrellas de 5+ extremos ................ 8,1 %   (máx 14 extremos, 36 bifurcaciones)
```

**Más de la mitad de los frames tienen bifurcaciones.** No es un caso raro: es el
caso normal. Y `H6b` ya demostró que **no son ruido de máscara** — persisten en
multiescala, son ramas reales del medial axis de una cinta con bordes imperfectos.

## Lo que hoy lo resuelve, y hay que respetar

`camino_principal.py:50` — la garantía, escrita por el propio archivo:

> «me quedo con **UNA** cadena raíz→hoja del esqueleto»

y los candidatos del target se **restringen a esa cadena**. Eso es CAMINO. MONO
le agrega el orden temporal para saber cuál extremo es "adelante".

Y el mismo archivo es honesto sobre el límite (línea 52):

> «**NO** garantiza que esa cadena sea la cinta semánticamente correcta»

O sea: elige heurísticamente una cadena larga y temporalmente consistente. Es lo
mejor que hay, y **funciona**. No hay que tocarlo.

---

## LA REGLA, para cualquier detector de codo

> **El detector trabaja sobre la CADENA que CAMINO ya eligió — nunca sobre el
> esqueleto crudo.**

En la práctica, en `vision_linea.py` eso es la lista `cad` que sale de
`_v2.reconstruct(prev, si, F)`: una secuencia **ordenada y sin bifurcaciones**.

### Lo que un detector NO puede hacer

| ❌ | por qué |
|---|---|
| recorrer el esqueleto crudo buscando extremos | vuelve a agarrar costillas: 56 % de los frames |
| ajustar rectas a "los puntos de la máscara" | la máscara en un codo tiene el centroide **fuera** de la cinta |
| tomar "la rama más larga" por su cuenta | eso es reimplementar CAMINO, peor y en paralelo |
| detectar el codo por conteo de extremos del esqueleto | 8,1 % de los frames son estrellas de 5+ extremos: dispararía todo el tiempo |

### Lo que sí

| ✅ | |
|---|---|
| recorrer **`cad`**, que ya viene ordenada y es única | |
| ajustar dos rectas **a tramos de `cad`** | cerca y lejos |
| medir el cambio de rumbo **a lo largo de `cad`** | y su concentración |
| si `cad` no existe en ese frame | **devolver `None`** — "no opino", como hace `vision_linea` |

---

## Cómo se verifica que no se rompió

Sobre los videos, comparando con el pipeline actual:

1. **la fracción de frames en que el target cae fuera de `cad` tiene que seguir
   siendo 0** — si el detector propone un vértice o un target propio, tiene que
   estar sobre la cadena
2. **el conteo de saltos del target no puede subir**
3. **y a ojo**: generar el mismo panel de la captura buena y mirar que no
   reaparezcan las ramas al costado

**Si un detector mejora la detección del codo pero devuelve las bifurcaciones, no
sirve.** El costo de seguir una costilla es perder la corrida entera; el beneficio
de detectar un codo antes es unas décimas.
