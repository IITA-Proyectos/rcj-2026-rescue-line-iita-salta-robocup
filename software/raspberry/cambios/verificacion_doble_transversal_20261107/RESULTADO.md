# Verificación: el doble de ChatGPT junto con el paquete de Claude (7-nov-2026)

Se probó si `doble_transversal_20261102` (de ChatGPT) cambia algo del paquete CRESTA-BAJADA + PLATEADO instalado en
la Pi el 7-nov. Ese paquete es `main.py` `9da00beb…`, con verde de la cresta, bajada y plateado.

- **A (simD):** lo instalado en la Pi el 7-nov, con el `doble_dato.py` original (`fdb930c1`, el mismo que
  ChatGPT usó de referencia).
- **B (simE):** lo mismo, más el `doble_dato.py` (`DOBLE-DATO-TRANSVERSAL-2`) y el `doble_transversal.py` de
  ChatGPT.

Se usó el simulador con el `main.py` completo, en las 13 corridas: las 11 del 31-oct y el 1-nov, y las 2 del 7-nov.
Cada corrida se cortó en las reubicaciones y los rescates, y cada tramo arranca de cero.

## Resultado

- **156.316 cuadros comparados.** Cambian solo 4 tramos, y en cada uno 1 o 2 cuadros: un verde que salía "2"
  (simple derecha) sale "3" (doble) un cuadro antes.
  - 12:49 del 1-nov, cuadros 1651 y 17706: los dos que ChatGPT había encontrado.
  - 19:53 del 31-oct, cuadros 1850 y 6949: nuevos.
- **Los 4 son dobles de verdad,** un cuadrado a cada lado de la línea antes del travesaño. Ver
  `dobles_cambiados.jpg`.
  - Hoy, el primer dato es "2". Como la Teensy ejecuta el primer verde que recibe, haría un giro simple a la
    derecha en vez de la vuelta.
  - Con el cambio, el primer dato es "3".
  - Después del cambio, el resto de cada tramo es idéntico.
- **Nada más cambia.** Los eventos del log son iguales en A y B:

  | Evento | Veces |
  |---|---|
  | Verde de la cresta armado | 17 |
  | Suelta con cinta conectada | 6 |
  | Suelta por tope | 11 |
  | Bajada que recupera | 6 |
  | Plateado que manda derecho | 10 |

- **Fidelidad del simulador** (etiqueta igual a la del robot): 90–93 % en las corridas del 7-nov y 73–97 % en
  las demás.

## Límites

Es a lazo abierto: no muestra la trayectoria nueva después de un cambio, solo qué decidiría en cada cuadro. Que el
robot haga la vuelta del doble bien hay que verlo en pista. Lo de "suelta por tope" en la cresta es propio del lazo
abierto, porque el robot del video no giró; es igual en A y en B.

Herramientas: `herramientas/tramos_doble.py` (corre las dos variantes) y `herramientas/comparar_doble.py`.
