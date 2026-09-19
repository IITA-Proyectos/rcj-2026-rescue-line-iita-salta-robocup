# Corridas de visión del 2026-08-22 — qué se probó y qué dijo cada una

Primer día en que algo del diagnóstico de visión corrió en el robot. Seis corridas
grabadas, **6772 frames de pista**, todas medidas sobre las mismas cuatro métricas.

**Todavía no hay solución: el robot se sigue saliendo.** Este archivo existe para que
lo probado no se vuelva a probar, y para que lo medido no se vuelva a suponer.

---

## Las corridas

| archivo | qué corría |
|---|---|
| `con_planner.avi` | el planner manejando, primer intento (320×240, sin panel de máscara) |
| `con_planner2.avi` | el planner manejando, con panel de máscara |
| `roi_auto.avi` | el `atan2` de siempre + ROI adaptativo |
| `lineal.avi` | control lineal, `K_CERCA=40` |
| `lineal70.avi` | control lineal, `K_CERCA=70` |

## Lo que dieron

| control | cruces/s | tiempo a <10 px | desvío medio | línea perdida |
|---|---|---|---|---|
| **`atan2` (original)** | 1,88 | **42 %** | **20,0 px** | **17,9 %** |
| planner | **1,07** | 37 % | 19,4 px | 24,8 % |
| lineal `K=40` | 1,14 | 22 % | 26,1 px | 33,9 % |
| lineal `K=70` | 1,62 | 37 % | 21,1 px | 22,6 % |

**Cuatro leyes de control distintas y las cuatro caen en la misma banda.** Ninguna le
ganó al `atan2` original en las cuatro métricas a la vez. Cuando se cambia el
controlador de raíz cuatro veces y el resultado no se mueve, el límite no está en el
controlador.

---

## Lo que sí quedó demostrado

### 1. La ganancia del `atan2` está invertida

Medido sobre 3221 frames:

| desvío | ángulo medio | **ganancia** |
|---|---|---|
| 0 – 5 px | 19,3° | 1,04 °/px |
| 5 – 10 px | 26,9° | **1,74 °/px** |
| 30 – 45 px | 55,6° | 0,29 °/px |
| 45 – 80 px | 57,5° | **−0,61 °/px** |

A **un píxel** del centro ya corrige 1,45°; a 45 px no corrige más que a 30. Por eso
oscila cerca del centro **y** por eso, cuando se fue, no vuelve. Las dos cosas salen de
la misma fórmula. `CTRL=lineal` la reemplaza por dos términos de ganancia constante.

### 2. Al perder la línea, el robot endereza

```python
if np.sum(black_mask) < min_line_size:
    angle = 0            # <- seguir DERECHO
```

La línea no desaparece por casualidad: desaparece porque se fue por un costado. Justo
ahí el robot endereza y se va de la pista. **El `Main.py` del repo sí tiene rutina de
línea perdida (`last_line_search_dir`); el que corre en la Raspberry no la tiene.**
`RECUP=1` la restituye: sigue girando hacia donde estaba la línea, cada vez más fuerte.

### 3. El recorte fijo de la fila 60 tira un tercio del ROI

El salón termina en la fila 35-40; el recorte está en 60. Son **23 filas de pista**
(mediana) descartadas, y son las **más lejanas** — las únicas que sirven para anticipar.
`ROI=auto` recorta en el horizonte real: el ROI pasa de 60 a 83 filas.

### 4. El planner recorre el borde de la mancha, no un centro

Visible en el panel de máscara de `con_planner2.avi`: en `#570`, `#666`, `#761` y
`#1046` el trazo camina el contorno. En `#856`, donde la cinta se ve como un trapecio
que se aleja, va derecho por el medio y coincide con el centroide. **Cuando la cinta
tiene perspectiva los dos funcionan; cuando es una mancha, los dos fallan.**

Además cuesta **11 ms por frame** en la Pi (55 → 34 fps).

---

## Errores de medición cometidos y corregidos

Se documentan porque cada uno casi produce una decisión equivocada.

| lo que se afirmó | por qué era falso |
|---|---|
| "la imagen está quemada" | 0 % de frames con píxeles al tope. Es piso claro, no sobreexposición |
| "el 100 % de los frames sin línea tienen línea arriba del recorte" | era el **salón**, no pista. Se contó negro y se lo llamó línea |
| "el 55 % de los frames se comportan como mancha" | la métrica de perspectiva clasificaba 3 de 5 al revés. Se eliminó |
| "el robot ve 2,8 cm de piso" | medido en la fila más cercana, donde la perspectiva magnifica más. No es el campo visual |
| "la basura del horizonte explica que `CTRL=lineal` empeorara" | sólo afecta al 2,2 % de los frames. La causa era la ganancia baja |

**La lección, dos veces aprendida: validar contra casos reales de respuesta conocida, no
contra sintéticos ni contra promedios.** Los sintéticos pasaban con las métricas rotas.

---

## Cómo medir una corrida nueva

Las cuatro métricas salen del video con el panel izquierdo (el frame que el robot
procesó, escalado ×2 — se recupera exacto tomando un píxel de cada dos):

- **cruces/s** — cuántas veces por segundo la línea cruza el centro de la cámara
- **tiempo a <10 px** — qué fracción del tiempo está realmente centrado
- **desvío medio** — cuán lejos del centro está, en píxeles (la cinta mide ~36 px)
- **línea perdida** — fracción de frames sin cinta en el ROI

Comparar siempre contra `roi_auto.avi`, que es la línea de base del `atan2`.

---

## Lo que falta probar

```bash
ROI=auto RECUP=1 GRABAR=~/Desktop/a.avi python3 main.py
```

El cálculo de siempre, con 23 filas más de pista por delante y **sin enderezar cuando
pierde la línea**. Es la combinación que ataca directamente lo observado en pista —
*"la línea le queda muy al lado, el robot intenta girar hacia donde ve un poco, después
no ve nada y se sale"*— y ninguna de las seis corridas la probó.
