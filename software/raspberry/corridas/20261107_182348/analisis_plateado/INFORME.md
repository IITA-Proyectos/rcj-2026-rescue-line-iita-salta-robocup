# Plateado, prueba del sábado 7-nov-2026 (18:41 a 18:59)

Grabación: `pista_prueba_182348.avi`, `.log` y `crudo_prueba_182348/1107_184121`, con 11.576 cuadros. El video y el
crudo coinciden cuadro por cuadro. Paquete instalado: CRESTA-BAJADA + PLATEADO, umbral 1790.

## Resumen

48 pasadas (una por reubicación); entraron 34 (`Llego 241`).

| | Pasadas | Entraron | La regla actuó |
|---|---|---|---|
| Entrada que da al salón (18:41–18:44) | 4 | 1 | 3 veces |
| Zona de evacuación de verdad (18:44–18:59) | 44 | 33 | ninguna |

## Donde actuó la regla: las 3 veces hizo lo correcto

Fueron las pasadas 2, 3 y 4, con curva a la izquierda y la banda en 3046–3361 al llegar y 2108–2323 después. Las
tres veces mandó derecho, y en las tres el robot fue derecho a la banda:
- **18:44:02:** entró a 1,43 s de la decisión.
- **18:43:36:** la grabación se corta a 1,33 s, justo antes del momento en que entró la otra. El log dice
  `cambiando estado` sin parada de la Teensy, o sea que apagaron la llave.
- **18:43:41:** se corta a 0,42 s, sin tiempo de llegar.

Ver `regla_actuo_*.jpg`.

## En la zona real no actuó: la banda se ve demasiado brillante

- **15 curvas a la izquierda en la entrada:** 7 entraron igual (el sensor llegó a ver el plateado) y 8 se
  frenaron mirando la pared (GS19). Es la falla de siempre.
- **Sus puntajes, el menor de llegada y post:** de 1124 a 1770, casi todos entre 1300 y 1500. Ninguno llega a
  1790. El que más cerca quedó fue 18:45:08, con 2016/1770.
- **Por qué:** el puntaje solo cuenta gris *con textura*, las vetas de la banda (110 < V < 225 y desvío local
  > 7). Con la luz de hoy esas vetas casi no se ven.
  - La banda queda gris lisa (azul en `por_que_la_banda_da_bajo.jpg`) o quemada (amarillo, V ≥ 225). En los dos
    casos no cuenta, y cuentan sobre todo sus bordes.
  - En los 6 cuadros de llegada, el gris con textura dio una mediana de ~1500 hoy contra ~2050 en las 8 entradas
    del 1-nov. Los píxeles quemados subieron de ~2300 a ~3200–5200.
  - (La primera versión de este informe decía que era solo por brillo: no es así.)
- **Bajar el umbral no sirve:** las curvas comunes de otros días llegan a 1730 (13:54 4:03) y 1564 (22:11
  5:28). Con 1300 actuaría en curvas comunes.

## Ir derecho en la zona sí funciona

De las recuperaciones de la zona que fueron derecho (palillo, GAP previo o AMBIGUA→GAP), entraron todas menos una:
la pasada de las 18:53:23, donde el GAP encontró cinta negra y siguió. El problema es solo detectar la banda con
esta luz.

## Falsos positivos

Ninguno: en las 48 pasadas la regla actuó solo en las 3 de la entrada. Hoy no hubo vueltas a la pista, así que no
se pudo mirar en curvas comunes.

## Herramientas

- `tiras_pasadas.py`: tira de cuadros del video alrededor de una decisión del log.
- `por_que_pixeles.py`: colorea cada píxel según la condición del puntaje que no cumple.
