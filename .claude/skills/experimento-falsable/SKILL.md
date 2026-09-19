---
name: experimento-falsable
description: Diseña y audita experimentos sobre datos del robot para que no se autoengañen — hipótesis con falsador escrito antes, umbrales preregistrados y plateau en vez de un número elegido a ojo, controles positivos que no se pueden romper, grupos de comparación equiparables, placebo desplazado en el tiempo, tasas base y razón de riesgo, eventos únicos en vez de "al menos uno", distribuciones zero-inflated que parecen bimodales, y separar diagnóstico confirmado de política adoptada. Usar antes de correr cualquier A/B, cuando un resultado dé sospechosamente lindo, cuando haya que elegir un umbral, cuando se vaya a reportar un porcentaje, o cuando una hipótesis "casi funciona".
---

# experimento-falsable

Sos responsable de que las mediciones sobre el robot **signifiquen lo que dicen
que significan**. Tu trabajo no es encontrar resultados: es evitar que se adopten
resultados falsos.

## Por qué existe esta skill

En dos días de trabajo sobre el seguidor de línea de IITA se cometieron **cuatro
errores estadísticos distintos**, todos de buena fe, todos detectados después de
publicarlos:

1. Grupo de control contaminado con los frames donde vivía el efecto.
2. La unidad de análisis equivocada (frame en vez de racha).
3. "Rachas con al menos una inversión" reportado como "porcentaje de las
   inversiones".
4. Confundir dos columnas de una tabla de métricas, y publicar un porcentaje
   sobre el denominador equivocado.

Y uno más, atajado a tiempo: un estimador de velocidad angular que daba **900
grados/s en un robot que gira a 39**, porque medía frame a frame algo que era
ruido.

Ninguno era falta de cuidado. Todos eran errores que un checklist ataja.

---

## 1. El falsador se escribe ANTES

Una hipótesis sin falsador escrito no es una hipótesis: es una preferencia.

Antes de correr nada, escribí:

- **qué predice** la hipótesis, en números;
- **qué resultado la mataría**, en números;
- **qué controles** tienen que seguir intactos.

Y guardalo en el commit o en el issue **antes** de ver el resultado.

> Si al ver el resultado te encontrás explicando por qué el falsador no aplica en
> este caso, la hipótesis ya cayó.

---

## 2. Umbrales: plateau, no un número

Cuando una conclusión depende de un umbral (`delta ≥ 15`, `salto > 24 px`), hay
que demostrar que **no depende de ese número en particular**.

**Preregistrá una banda** (por ejemplo 10/15/20/30/40), corré el análisis en
**todos**, y reportá la tabla completa. Sólo hay conclusión si el efecto se
sostiene en toda la banda.

```
umbr   RR contra placebo   % de eventos
  10        2,14x              21,4 %
  15        2,04x              17,3 %
  20        1,85x              16,3 %
  30        2,64x              14,0 %
  40        2,42x              10,7 %       <- hay plateau: 1,85 a 2,64
```

**Nunca elijas primero el umbral que mejor queda.** Si el efecto sólo aparece en
uno, no hay umbral defendible.

### Zero-inflated no es bimodal

Trampa concreta y cara. "El 84 % de los valores son exactamente 0, p90 = 3 y
p95 = 22" **no demuestra** que haya dos poblaciones ni un umbral natural. Puede
ser perfectamente una distribución con mucho cero y cola larga.

**Imprimí el histograma completo, con bins, no tres cuantiles.** Y aun con un
valle visible, mirá los **conteos**: un valle de 34 frames contra 45 y 61 es
ruido, no estructura.

---

## 3. Controles positivos: lo que no se puede romper

Definí de antemano dos o tres tramos donde el sistema **funciona hoy**, y exigí
que sigan intactos exactamente. En IITA:

```
lineal_positivo   73/73 targets, y conserva el giro extremo de +87 grados
hist_exito       100/100 targets
teacher trace     sin regresión
```

Un cambio que mejora la métrica principal y rompe un control positivo **no se
adopta**, sin discusión.

> Y guardá el motivo del control. `lineal_positivo` existe porque en ese tramo el
> target queda en el borde con steer +87° y **la curva se completó**. Sin esa
> nota, alguien va a proponer "limitar la magnitud del steer" y va a romper algo
> que andaba.

---

## 4. Los grupos de comparación tienen que ser equiparables

Error real: al comparar "frames con el efecto" contra "frames sin el efecto", el
segundo grupo incluía los frames **no aplicables** (pérdida de línea, otro modo
del algoritmo) — que son justo donde vivían los eventos que se querían explicar.
La razón de riesgo dio 0,54× y parecía refutar todo.

**Regla:** los dos grupos tienen que salir del **mismo conjunto elegible**.
Escribí explícitamente qué frames entran al denominador y por qué.

---

## 5. La unidad de análisis

Si el mecanismo dice "el error se acumula y **después** produce el evento", la
unidad no es el frame: es la **racha**.

Medido por frame daba 0,77× (sin efecto). Medido por racha, contra la variable
correcta, daba **3,09×**. Mismo dato, misma hipótesis, conclusión opuesta.

**Preguntá siempre: ¿cuál es la unidad que el mecanismo predice?** Y decidilo
antes de mirar.

---

## 6. Y la variable de salida correcta

Mismo caso: el efecto se medía contra "saltos de más de 24 px" y no aparecía.
Resultó que un limitador aguas abajo **convertía el salto en un barrido suave**,
así que el salto nunca se registraba — pero sí quedaba una **inversión de
signo**.

**Si hay un guard, un filtro o un limitador entre la causa y la métrica,
preguntá qué le hace a la señal.** Puede estar borrando exactamente lo que
buscás.

---

## 7. Placebo y tasa base

"El 77,6 % de las rachas termina en inversión" no dice nada solo. Hacen falta
dos referencias:

- **tasa base**: ¿cuál es la probabilidad del evento en una ventana cualquiera?
- **placebo**: la misma construcción de ventana, desplazada en el tiempo.

```
inversión en los 10 f DESPUÉS del final    77,6 %
inversión en los 10 f ANTES del inicio     19,0 %
PLACEBO: misma ventana 2 s antes           27,6 %
tasa base global                           25,1 %
```

El placebo en la base y el "antes" por debajo: el efecto es **específico del
final de la racha**, no de la región. Sin el placebo, cualquiera puede decir
"eso pasa porque son zonas de curva".

---

## 8. Eventos únicos, no "al menos uno"

**"58 rachas y el 77,6 % tiene al menos una inversión" NO es "el 77,6 % de las
inversiones".** Son cosas distintas y la segunda es la que la gente entiende.

Para atribuir correctamente:

1. Contá los **eventos únicos** en todo el dataset (y verificá que coincida con
   el número que reporta el banco oficial — si no coincide, algo está mal).
2. Uní las ventanas en un **conjunto**, así las superpuestas no cuentan dos
   veces.
3. Intersecá eventos con el conjunto.
4. Reportá `atribuidos / total`.

Y **verificá qué columna es cuál**. En IITA, `93,78 / 864 / 276 / 247 / 392` son
disponibilidad, frames sin autoridad, huecos, **saltos** e **inversiones**. Se
publicó un porcentaje sobre 247 creyendo que eran las inversiones. Eran los
saltos.

---

## 9. Instrumentar sin cambiar lo que se mide

Si para medir hay que espiar el interior de un algoritmo, **demostrá que el
espía no cambia el resultado**: corré N frames con y sin instrumentación y
compará la salida exacta. Si difiere, abortá.

Y si una etapa intermedia no se expone y hay que re-derivarla, **hacé que la
re-derivación se autoverifique**: aplicá también las etapas siguientes y exigí
que reproduzca exactamente la salida que el sistema sí expone. En IITA eso dio
**16.112 frames, 0 discrepancias**, y por eso las etapas intermedias del registro
visual son datos y no una reconstrucción plausible.

Reportá siempre el **overhead** de la instrumentación.

---

## 10. Sanidad física antes de publicar

Antes de reportar cualquier número con unidades, preguntá: **¿es físicamente
posible?**

Un estimador de velocidad angular daba p50 = 51 °/s y máximos de 900 °/s en un
robot cuyo techo era 39 °/s. Y el tramo que fallaba daba *menos* que el que salía
bien. Los dos síntomas gritaban "estimador roto", no "hallazgo".

**Dos chequeos baratos:**
- **orden de magnitud** contra algo ya medido;
- **coherencia interna**: si los controles se comportan al revés de lo esperado,
  sospechá del instrumento antes que de la teoría.

En ese caso la causa era medir frame a frame algo que sólo tiene sentido
integrado: la medición correcta usaba una ventana de 0,3 s, que además es lo que
significaba "sostenida".

---

## 11. Diagnóstico confirmado ≠ política adoptada

Son dos veredictos separados y hay que darlos por separado:

| | |
|---|---|
| **fenómeno** | ¿existe? ¿los controles están limpios? |
| **causa de X** | ¿predice X mejor que el azar, con placebo? |
| **política** | ¿la intervención mejora la métrica primaria sin romper nada? |

Un diagnóstico puede ser **fuerte** y su política **caer**. Pasó dos veces
seguidas en IITA (H9 y H10): el mecanismo estaba bien identificado, la
intervención empeoraba las cosas.

> **Y cuando la política cae, cae.** "Casi funciona" y "con otro umbral quizás"
> son cómo se pierden semanas. Anotá el límite conocido de la métrica si lo hay,
> pero no lo uses para revivir la política.

---

## 12. Cuando falla el gate, no falló la hipótesis

Distinción fina y cara. Si una política casi no dispara —8 intervenciones en
14.000 frames— y **no dispara en el caso que la motivó**, entonces el A/B **no
testeó la hipótesis**: testeó una condición de activación mal especificada.

Antes de declarar nada, **verificá que la intervención dispare en el caso
testigo**. Si no dispara, arreglá el gate y volvé a correr la banda completa de
umbrales preregistrados — y decí explícitamente que fue un error de
especificación, no un ajuste para ganar.

---

## Checklist antes de correr un A/B

- [ ] Hipótesis y falsador escritos, en números.
- [ ] Banda de umbrales preregistrada.
- [ ] Controles positivos definidos, con el motivo de cada uno.
- [ ] Métrica primaria elegida **antes**, y verificado que ningún filtro
      aguas abajo la borre.
- [ ] Unidad de análisis derivada del mecanismo.
- [ ] Denominador escrito explícitamente, y los dos grupos equiparables.
- [ ] Placebo y tasa base definidos.
- [ ] Instrumentación verificada contra la versión limpia.

## Checklist antes de publicar un número

- [ ] ¿Es físicamente posible?
- [ ] ¿Coincide con algún número ya conocido del banco oficial?
- [ ] ¿Los controles se comportan como deberían?
- [ ] ¿El denominador es el que el lector va a suponer?
- [ ] ¿"Al menos uno" o eventos únicos?
- [ ] ¿La conclusión sobrevive en toda la banda de umbrales?
- [ ] ¿Estoy separando diagnóstico de política?
