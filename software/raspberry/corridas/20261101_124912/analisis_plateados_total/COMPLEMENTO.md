# Complemento (1-nov-2026): cuáles entraron y por qué

Se cruzaron las 8 aproximaciones de `INFORME.md` con `cuadros.csv` y el log `pista_doble_dato_20261101_124912.log`.
La Pi no graba mientras está en rescate, así que un hueco largo en el tiempo después de la aproximación (70–200 s)
quiere decir que entró. Un hueco corto (8–24 s) quiere decir que lo reubicaron.

| ID | Recuperación | Después | Hueco | Resultado |
|---|---|---|---|---|
| P01 | AMBIGUA → GAP (derecho) | `Llego 241` 2,1 s después del GS4 | 82 s | **entró** |
| P02 | AMBIGUA → CURVA +54 → parada (GS19) | — | 15 s | no |
| P03 | AMBIGUA → GAP | 241 a los 2,3 s | 201 s | **entró** |
| P04 | AMBIGUA → CURVA +50 → parada | — | 8 s | no |
| P05 | AMBIGUA → GAP | 241 a los 1,7 s | 70 s | **entró** |
| P06 | AMBIGUA → CURVA +66 → parada | — | 15 s | no |
| P07 | AMBIGUA → CURVA +65 → búsqueda −85 | — | 24 s | no |
| P08 | AMBIGUA → CURVA +54 → parada | — | 195 s | no (*) |

(*) El hueco de P08 es largo, pero en el registro no hay entrada a rescate con la cinta de por medio: hay que
mirarlo en el log antes de contarlo como entrada.

- **Las que van por GAP (derecho) cruzan la banda:** el sensor de color confirma (`Llego 241`) unos 2 s después
  del GS4 y entran.
- **Las que van por CURVA pivotean a la izquierda** y quedan mirando dentro de la zona (se ven las esquinas roja
  y verde de los depósitos). Adentro no hay cinta negra, así que la Pi manda la parada de seguridad
  (`perdida-failsafe-persistente`) y el robot se queda quieto en la entrada, antes de que el sensor confirme.
  Ver `entro_vs_no_entro.jpg`.
- **La dirección de la cinta antes de perderla no separa** las que entran de las que no: los últimos ángulos van
  de −82 a +63 en los dos grupos.
- **El sensor confirma tarde,** ~2 s después de perder la línea. Cualquier ayuda de la cámara tiene que actuar
  antes o sin esperarlo.

## Por qué decide CURVA (log de las 12:49)

- **Las que entraron:** el clasificador del final de línea (TERM-HARD) vio un final "tipo gap"
  (`GAP: 13–14 cuadros desde arriba`, `piso=True`) y la recuperación eligió `GAP_PREVIO`, es decir, derecho.
- **Las que no:** la cinta venía tocando el costado (`rama por el costado`, `punta en el costado`). Se eligió CURVA
  por "lateral previa + fragmento pequeño compatible", siempre a la **izquierda** (+50..+66), y el robot quedó
  mirando la pared de la zona.

## Detector de banda por cámara: dónde sirve y dónde no

Se midieron las 356 recuperaciones de las 11 corridas del 31-oct y el 1-nov. Además de las de las 12:49 aparecieron
entradas al plateado en 12:38 (4:02, 4:08), 11:47 (5:02, 14:22) y 13:54 (3:14): 13 en total.

- **"Banda gris con textura" en cualquier recuperación: no es confiable.** Se confunde con el piso visto de costado
  en las corridas de noche (31-oct), con la cresta de una rampa (12:49 0:53) y con una placa gris en una esquina
  (31-oct 21:36, 12 veces).
- **Restringida a las recuperaciones que deciden CURVA a la IZQUIERDA** (108), sí separa:
  - Con la banda vista al llegar (6 cuadros antes del GS4) y después del retroceso (hasta la decisión), las dos
    ≥ 1700: 8 de 8 del plateado y 0 de las 100 curvas a la izquierda que no son plateado.
  - El margen es chico: el plateado más bajo da 1912/1855, y lo que no es plateado más cerca da 1808/1619.
  - Puntaje: píxeles con S < 60, 110 < V < 225 y desvío local de V > 7 (5×5), filas 40–119 del cuadro de 160×120.
- **La entrada de 13:54 (3:14.75) curvó a la DERECHA:** esta regla no la cubriría.

## Solución (2-nov-2026): PLATEADO-ENTRADA-1

Está en el paquete `cambios/cresta_bajada_20261101` (`plateado_entrada.py` y `main.py`); ver su `RESULTADO.md`.
- **La regla:** si la recuperación decide CURVA a la izquierda y la banda da ≥ 1790 al llegar y después del
  retroceso, va derecho (GAP). Se apaga con `PLATEADO_RECTA=0`.
- **Separación:** las 8 del plateado dan como mínimo 1856 (el menor de los dos puntajes). De las 100 curvas a la
  izquierda que no son plateado, la más alta da 1730 (13:54 4:03, en crudo). Ver `cercanos_al_umbral.jpg`: las tres curvas más cercanas
  arriba y dos entradas abajo.
- **Los puntajes salen de los PNG crudos,** lo mismo que ve la Pi. El video comprimido no da lo mismo:
  - En la banda da menos que el crudo, hasta 173 en la mediana: borra la textura real.
  - En el piso blanco da más: mediana +61 en la llegada y +126 después del retroceso. Agrega textura propia.
  - 13:54 se midió primero sobre el video, porque su crudo no estaba en la PC: su curva más cercana al umbral dio
    1620/1808. El 7-nov se midió con el crudo que quedó en la Pi y dio **1730/1778**. La estimación de "1560–1670
    en crudo" estaba mal, y por eso el umbral pasó de 1740 a **1790**.
- **A la derecha no se puede:** 31-oct 21:03 (3:44) da 1927/1731 y no es plateado.
- **Sacar los bordes de la cinta negra del puntaje** empeora la separación: 0,97 en vez de 1,15.
- **Simulador por tramos:** en las 11 corridas (178 tramos, 118.186 cuadros) cambian solo las 8 entradas. Las
  herramientas están en `herramientas/`. Usan los scripts del simulador de `Downloads/SIMULADOR_PI_2026-10-17` con
  el `main.py` de cada variante.
