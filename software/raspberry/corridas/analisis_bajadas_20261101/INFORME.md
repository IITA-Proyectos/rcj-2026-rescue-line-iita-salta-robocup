# Bajadas: los verdes de la bajada y la salida de 12:49 en 19:17

Análisis del 1-nov-2026 sobre las 11 corridas del 31-oct y el 1-nov (12 videos, 71 verdes vistos bajando).
Cada falla se confirmó mirando los cuadros. El giro real se midió con flujo óptico sobre el fondo; el método
está validado: mide 39° en la maniobra del verde en el piso, lo que pide `runAngle`. Los datos por verde están en
`verdes_bajada_rasgos.csv` y los scripts en `herramientas/`.

## Cómo es la bajada

- **Bajada normal**, en dos tramos con un plano en el medio:
  - **Tramo 1:** a mitad de la rampa hay un cruce con verde a la IZQUIERDA (G1).
  - **Tramo 2:** abajo hay un "+" sin verde y después una **rotonda** con dos verdes a la izquierda: uno en la
    entrada de abajo (G2) y otro en la salida del costado izquierdo del círculo (G2'). Entre los dos, el robot
    sigue el círculo, que dobla a la derecha. G2' llega ~2,6 s después de G2.
- **Rampa lateral derecha:** se baja después del giro a la derecha en el cruce de la cresta. Tiene curvas en S y
  abajo una esquina cerrada en zigzag.

## 1. Los verdes de la bajada

| Verde | Resultado | Cómo falla |
|---|---|---|
| G1 (tramo 1) | casi siempre bien: 1 falla en ~20 (12:49 15:05.50) | (B) |
| G2 + G2' (rotonda) | ~17 bien (8 de ellos en las 11:47, sin G2'), 12 mal | (A) ×7, (C) ×4, (B) ×1 |

**(A) No ve el verde de la salida de la rotonda.** 12:38 en 1:05.50, 1:17.25, 1:27.65, 1:33.15 y 1:40.05;
12:49 en 5:17.55; 11:47 en 1:04.00.
- Después de G2, las vueltas buenas y las malas son iguales. En todas, G2 se detecta en el mismo lugar: el cuadrado
  toca la fila 119, x = 12–25, y estaba a la vista 6–8 cuadros antes. La Teensy gira +40..+50° y a los +1,7 s la
  cinta está conectada (4000–6000 px) con la Pi mandando +34..+40. Comparadas cuadro a cuadro, 9:25.10 (buena) y
  5:17.55 (mala) de las 12:49 coinciden hasta +1,9 s.
- **En las buenas**, el cuadrado de la salida entra en la imagen (x 5 → 19, de 374 a 1586 px) y se detecta en
  +2,08 s. Se hace la segunda maniobra a la izquierda y el robot termina en ~+98°.
- **En las malas**, el cuadrado aparece pegado al borde izquierdo (x = 1–11), cortado y chico (150–240 px). No
  llega a detectarse. La Pi sigue el círculo hacia la derecha (0 → −63 → −86), el robot vuelve a ~0° y sale por
  donde no es.
- Es geometría: unos grados o centímetros de diferencia en cómo llega el robot a la salida dejan el cuadrado
  dentro o fuera de la imagen.

**(C) Ve la salida, gira, y la pierde por el costado.** 10:31 en 2:14.30; 11:11 en 1:26.00 y 9:46.95; 31-oct
21:36 en 4:49.40. Después de la maniobra de G2' la cinta de la salida dobla a la derecha y desaparece por el
costado. `bajada-sin-recup` lo manda derecho 31–77 cuadros (1–2,5 s) y se sale del tablero.

**(B) Después de la maniobra no ve la rama.** 12:49 en 15:05.50 (G1) y 13:54 en 1:15.00 (G2). A los +1,7 s no
hay cinta (0 px en 15:05.50). `bajada-sin-recup` lo manda derecho 62–86 cuadros y la cámara termina viendo
el piso de madera.

## 2. 12:49 en 19:17: rampa lateral derecha

- Es la bajada que viene después del verde de la cresta de 19:07.5, el que salió bien.
- Sigue bien las curvas en S de 19:10 a 19:17. Abajo hay una esquina cerrada en zigzag: gira ~52° a la derecha
  (19:17–19:18.75) y ~52° a la izquierda (hasta 19:20.50).
- En 19:20.50 pierde la cinta por la derecha (−83). Desde 19:20.65, `bajada-sin-recup` lo manda derecho 33 cuadros
  (1,75 s), con la cinta a la vista adelante pero suelta. Lo reubican en 19:24.10.
- En 13:54 (5:04–5:09) la misma rampa también falló, más arriba:
  - En la curva a la derecha la Pi alterna −73, −21, −71, −87 y el robot no llega a girar lo suficiente.
  - En 5:06.85 la cinta sale por la derecha y `bajada-sin-recup` lo manda derecho 2,1 s sin ver nada.
  - Lo reubican en 5:09.60.
- **Las dos pasadas por esta rampa fallaron.**

## Qué tienen en común

- **(B), (C) y la rampa lateral (8 fallas):** los ceros salen todos de `bajada-sin-recup`. Es
  `BAJADA_SIN_RECUP=1` con `BAJADA_POST_S=4`: hasta 4 s después de terminar la bajada, sin cinta conectada,
  derecho. Se pensó para el borde de la 2.ª bajada, donde la cinta se esconde bajo la trompa. Pero abajo de esa
  bajada está la rotonda, y la rampa lateral tiene curvas: ahí "derecho" lo saca de la pista.
  - Es la misma familia que el verde de la cresta (`rampa-cresta-recto`/`rampa-sin-recup`): una regla de rampa que
    supone que la cinta sigue derecho.
- **No alcanza con mirar por dónde se perdió la cinta** para separar los "derecho" buenos de los malos. Los
  episodios cortos por un costado casi siempre caen durante la maniobra de la Teensy, que en ese momento ignora a
  la Pi, y salen bien. De los largos (≥1,5 s), 6 de 8 terminan mal.
- **(A) es otra cosa:** el verde de la salida de la rotonda queda en el borde de la imagen.

## Confirmado con el equipo (1-nov)

- Si no lo reubicaron, salió bien: las 8 pasadas de las 11:47 sin segundo verde son buenas.
- Lo que falla es el **segundo cuadrado verde de la rotonda** (G2', la salida izquierda).
- 19:17 de las 12:49 falló por `bajada-sin-recup`: ahí tenía que recuperar la línea. `bajada-sin-recup` arrancó
  en 19:20.65, 2,6 s después de que la Teensy dijo LLANO, dentro de la ventana `BAJADA_POST_S=4`. En 13:54
  (5:06.85) la Teensy todavía decía BAJA, así que acortar la ventana no alcanza para ese caso.

**Qué separa las buenas de las malas en la rotonda (20 de 20):** hacia dónde gira la Pi entre +1,9 y +3,0 s
después del primer verde, cuando llega a la salida.

| Pasadas | Qué manda la Pi | Resultado |
|---|---|---|
| 11:47 ×8 (sin segundo verde) y 12:49 ×5 (4 con segundo verde) | izquierda: 16–23 cuadros, media +25..+64 | bien |
| 11:47 1:04.00, 12:49 5:17.55, 12:38 ×5 | derecha: 24–27 cuadros, media −52..−61 | mal |

Cuando el segundo verde se detecta, la Teensy hace el giro a la izquierda. Sin él, sale bien solo si la Pi ya ve
la salida a la izquierda. En las 7 malas no pasó ninguna de las dos cosas: el cuadrado quedó en el borde
izquierdo de la imagen y la Pi siguió el círculo a la derecha.

## Lo que no se sabe todavía

- Por qué en las 12:38 fallaron los 5 intentos del tramo 2 seguidos, contra 5 de 6 bien en 12:49 con el mismo
  programa.
