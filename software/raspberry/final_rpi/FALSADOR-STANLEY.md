# Falsador — separar POSICIÓN de RUMBO (Stanley)

**Escrito ANTES de medir. 25-ago-2026. Rama `collab/nuevo-code`.**
Defecto 3.5.1 del traspaso, el único de los tres del cálculo de ángulos que
sigue abierto.

---

## El defecto, como está medido hoy

La ley de producción es un solo número:

```
steer = -90 · (x_target − CENTER) / (W/2)
```

`x_target` se corre por dos causas físicamente distintas —el robot está corrido
de la cinta (`e`, posición) y la cinta dobla adelante (`ψ`, rumbo)— y las dos
entran por la misma variable, con **una sola ganancia**, y la ley **nunca ve la
velocidad**. Medido en `posicion_vs_rumbo.py`:

```
steer = −1,011·e_lat  −0,758·ψ      R² = 0,82      47,8 % posición / 52,2 % rumbo
```

Stanley las separa: `δ = ψ + arctan(k·e / v)`. El término de posición **se
divide por la velocidad**; el de rumbo no.

---

## Hipótesis

**H-SEP** — `e` y `ψ` son dos grados de libertad materialmente distintos, y
colapsarlos en `x_target` con una sola ganancia **destruye información que la
ley podría usar**.

---

## Falsadores. En números, y escritos antes.

### F1 — colinealidad. Si se cumple, la hipótesis muere entera.
> Si `|corr(e, ψ)| ≥ 0,90` sobre los 10 autónomos, `e` y `ψ` son el mismo
> número con otra escala. No hay dos grados de libertad que separar. **MUERE.**

### F2 — suficiencia de `x_target`. Si se cumple, muere entera.
> Si `x_target` predice `ψ` con `R² ≥ 0,90`, entonces la ley actual ya "ve" el
> rumbo y no perdió nada al colapsar. **MUERE.**

### F3 — materialidad del cambio. Si se cumple, muere la POLÍTICA
### (el diagnóstico puede seguir en pie).
> Con las ganancias equiparadas en autoridad (misma desviación estándar de
> comando que la ley actual, sobre los mismos frames), si
> `p90(|δ_stanley − δ_actual|) < T` la separación es cosmética.
>
> **Banda preregistrada de T: 2 / 5 / 8 / 12 / 20 grados.**
> Sólo hay conclusión si el veredicto se sostiene en **toda** la banda
> (plateau). Un solo T que dé lindo no cuenta.

### F4 — sanidad del instrumento. Si se cumple, el instrumento está roto,
### no hay hallazgo.
> En los frames con la cinta **recta y el robot centrado** (`|e|` < p25 **y**
> `|ψ|` < p25 de sus propias distribuciones), la ley nueva debe pedir
> `p90(|δ_stanley|) ≤ p90(|δ_actual|)` en ese mismo subconjunto.
> Si ahí pide **más** giro que la ley vieja, el estimador está mal y se aborta
> antes de reportar nada.

### F5 — dependencia de la velocidad. Si se cumple, no implementé Stanley.
> Con `v` variando en su rango real (factor 0,55 → 1,00 de
> `vision_linea.velocidad`), el término de posición tiene que cambiar. Si
> `p90(|δ(v=0,55) − δ(v=1,00)|) < 1°` sobre los frames donde el factor de
> velocidad efectivamente baja, entonces la división por `v` no está haciendo
> nada y no es Stanley: es la ley vieja con otro nombre. **MUERE.**

---

## Controles positivos — no se pueden romper

Tomados de `gate.py`, con su motivo, y **sin agregar criterios nuevos**:

| control | qué exige | por qué |
|---|---|---|
| `hist_exito` f580-679 | 100/100 targets | ahí no perdió la línea |
| `lineal_positivo` f800-872 | 73/73 targets | ídem |
| `lineal` f800-872 | **máximo de steer ≥ +89** | en f824 el target queda en (2,95) con +87° y **la curva se completó**. Esa autoridad es necesaria |

> **La ley nueva NO puede bajar la autoridad máxima.** Separar posición de rumbo
> es repartir la autoridad entre dos términos, no recortarla. Si la ley nueva no
> llega a +89 en `lineal`, no se adopta. Regla 3 del traspaso, sin excepción.

**Nota sobre el conteo de targets:** el steer no realimenta al selector de
target, así que se *espera* que 100/100 y 73/73 sean invariantes al cambio de
ley. **Eso hay que verificarlo, no asumirlo.** Si cambian, hay una realimentación
que no está documentada y eso es el hallazgo, no la ley.

---

## Instrumentación — se verifica antes de creerle

Regla 4 del traspaso. La ley nueva se implementa como **módulo puro** que
consume el dict que la candidata ya devuelve (`start`, `target`, `path`, `skel`)
y **no toca la candidata**.

Prueba de fidelidad, obligatoria antes de cualquier A/B:
> En modo `actual`, el módulo tiene que reproducir **exactamente** el valor de
> `vision_linea._angulo_de(target[0])`, frame a frame, sobre los 10 autónomos.
> Criterio: **0 discrepancias**. Con una sola, se aborta.

---

## Lo que este experimento NO puede probar

**El replay es lazo abierto.** El video contiene el futuro que generó la ley
vieja manejando el robot. Un cambio en la ley de control cambia la trayectoria,
así que **ninguna métrica de este banco puede decir que Stanley maneja mejor.**

Lo que sí puede decir:
- si hay dos grados de libertad (F1, F2);
- si la ley nueva los separa de verdad (F3, F5);
- si el instrumento es sano (F4);
- si rompe algo que hoy anda (controles).

El veredicto "maneja mejor" es **prueba de robot**, y no se va a afirmar acá.

---

## Sensibilidad al campo visual

El HFOV **no está calibrado** y `d_eje` **no está medido**. `ψ` en grados
verdaderos depende del HFOV, así que todo se reporta para **45 / 60 / 75**,
igual que se hizo con SUELO. Si el veredicto cambia de signo dentro de esa banda,
no hay conclusión.

`d_eje` no entra: es un desplazamiento a lo largo de Z, y ni la tangente del
camino (`ψ`) ni el cross-track en la fila más baja (`e`) dependen de él. Eso es
una ventaja de Stanley sobre pure pursuit y es la razón por la que esta tarea
**no está bloqueada** por la medición pendiente de `d_eje`.
