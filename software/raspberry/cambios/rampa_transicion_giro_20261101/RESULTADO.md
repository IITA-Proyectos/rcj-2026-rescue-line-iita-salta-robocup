# RAMPA-TRANSICION-2: soltar la transición cuando la cinta dobla en la cresta

Corrida: `corridas/20261101_124912` (video `pista_doble_dato_20261101_124912.avi`, 20 fps, cuadro n = n/20 s).

## Qué pasó
- Las subidas de 18:30 y 18:45 son las únicas donde la cinta **dobla a la derecha arriba de la rampa**.
  En las demás (0:27, 0:37, 4:41, 4:51, 8:50, 8:59, 13:56, 14:06) la cinta sigue derecha.
- En las dos malas, la recta de subida armó `RAMPA-TRANSICION-1` (20 cuadros `rampa-recta`). Desde ahí,
  cada cuadro `rampa-linea` se reemplazó por `rampa-transicion-cerca` (recortado a ±15) o
  `rampa-transicion-sin-geometria` (0). El video muestra `viejo -18 / -20 / -59` (22312-22320) y
  `-22 / -44 / -78` (22603-22612): el ángulo de siempre sí giraba y la transición lo tapó.
- Después, sin cinta: `rampa-cresta-recto` (hasta 1,5 s) + `rampa-sin-recup` (1,5 s) = unos 3,5 s derecho.

## Cambio (solo `rampa_transicion.py`)
Con la transición armada, si la cinta toca **un solo** costado de la máscara (≥10 filas en las 3
columnas del borde) y la parte más baja de esa rama **baja 4 cuadros seguidos** (se acerca al robot),
la transición se desarma y vuelve el ángulo de siempre. El borde de la cresta de 8:59 toca los dos
costados o se aleja, así que no suelta.

## Replay sobre esta corrida (`verificar_giro.py`)
Máscara reconstruida desde el panel del video (no es exactamente `_m_lin`).
- Suelta en **22318** (5 cuadros antes de perder la cinta) y en **22607** (7 antes).
- 8:59 y 14:06 (subidas buenas con transición armada): **ningún cuadro cambia**.
- También cambia 22403 (un cuadro, ya pasado el giro) y desarma en 24156 sin cambiar nada.

## Sin probar
- No se probó en el robot ni con la máscara real (`_m_lin`). Son solo 2 casos positivos.
- Después de soltar, si la cinta se pierde igual, `cresta-recto` / `sin-recup` siguen mandando 0.
