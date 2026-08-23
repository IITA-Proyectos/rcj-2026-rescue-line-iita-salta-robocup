# Trabajo nocturno del 2026-08-23 — registro vivo

_Este archivo tiene que alcanzar para retomar exactamente donde quedé, sin depender del
contexto de la conversación. Se actualiza a medida que avanza, no al final._

**Punto de partida:** [ANALISIS-2026-08-23.md](ANALISIS-2026-08-23.md) (workflow de 13
agentes) e [INFORME-2026-08-22.md](INFORME-2026-08-22.md).

**Regla de seguridad de la noche: NO se mueve el robot.** Sólo código, git, CSV, videos,
replay, compilación y análisis.

---

## ESTADO ACTUAL

| prioridad | tarea | estado |
|---|---|---|
| 1.1 | versionar el `main.py` real de la Pi | **hecho** (recuperado del transcripto) |
| 1.2 | `diagProcedencia` con las constantes del `case 7` | pendiente |
| 1.3 | log de la Pi: frame, timestamp, fps real, orden, estado de línea | pendiente |
| 1.4 | fps 20.0 hardcodeados | pendiente |
| 1.5 | auditar frame/timestamp/fps/dt en todo el código | pendiente |
| 2 | refutar la hipótesis de cancelación prematura | pendiente |
| 3 | herramienta de replay | pendiente |
| 4 | diseño de la lógica de giro comprometido | pendiente |
| 5 | pérdida de línea como estado explícito | **hallazgo nuevo, abajo** |

---

## H-1 — `min_line_size = 1`: el robot casi nunca sabe que perdió la línea

**Estado: CONFIRMADO con medición propia sobre los 10 videos.**

El `main.py` real de la Pi (recuperado del transcripto, 920 líneas) hace:

```python
min_line_size = 1                                    # linea 60
...
black_mask[:60, :] = 0                               # linea 766  -> ROI = filas 60..119
...
if np.sum(black_mask) < min_line_size:               # linea 831
    angle = 0                                        # linea 832
```

`black_mask` es una máscara de **0/255**, así que `np.sum(...) < 1` sólo se cumple con
**cero píxeles negros en todo el ROI**. Con el salón en cuadro (zócalo, patas de mesa,
sombras) eso casi nunca pasa.

**Medición sobre 13.900 frames de los 10 videos:**

| | frames | % |
|---|---|---|
| la rama de pérdida se dispara (`suma < 1`) | 739 | **5,32 %** |
| la línea está **realmente** perdida (<30 px en filas 100-119) | 2.903 | **20,9 %** |

**El robot detecta la pérdida en 1 de cada 4 veces que realmente la perdió.** En las otras
2.164 (15,6 % de la corrida entera) calcula un `atan2` confiado sobre mobiliario y maneja a
velocidad 40.

Esto es **compatible con** y **más específico que** lo que había dicho el análisis previo
("en el 29 % de los frames perdidos la visión calcula un atan2 con ángulo mediano 40,8°
sobre negro que en el 93 % de los casos es el salón"). Aquel número salía del lado de la
máscara; éste sale del lado del **umbral**, y señala la línea de código exacta.

**Por qué importa para el problema de las curvas:** la pérdida no es un evento raro de
final de curva. Es un estado en el que el robot pasa **una quinta parte de la corrida**, y
durante el 75 % de ese tiempo **cree que está siguiendo la línea**.

**Cómo se refuta:** si al medir con el umbral correcto (área de componente conexa que toca
el borde inferior) el 20,9 % baja mucho, entonces la "pérdida real" está sobreestimada y el
gap es menor. Pendiente de verificar con la definición conexa.

### Nota sobre el otro `angle = 0`

Hay un segundo `angle = 0` en la línea 646 del mismo archivo, en otro camino. Hay que
auditarlo: si también significa "no sé", el estado ambiguo tiene dos orígenes, no uno.

---

## Verificación cruzada: éste ES el código que corrió

El workflow había deducido, sin ver el archivo, que el recorte del ROI estaba en la **fila
60** (81,1 % de coincidencia al grado contra el CSV) y no en la 55 del `Main.py` del repo
(58,1 %). El archivo recuperado tiene `black_mask[:60, :] = 0` en la línea 766.

**Coincide.** El `main.py` recuperado es el que generó las corridas del 22-ago.

---

## Hechos heredados que NO se vuelven a discutir

Del análisis del 23-ago, ya refutados o confirmados con número:

- **Descartado:** techo de par (0,00 % de PWM ≥250), patinaje variable (constante gr/s por
  rpm = 1,15–1,29 en las 6 configuraciones), umbral de negro, ROI muy abajo, ISR robando
  flancos de encoder (`volatile` presente, `dt` = 5000 µs de mediana y máximo).
- **Confirmado:** el pedido de curva dura 0,23–0,47 s y entrega 4,6–12,3 grados; 1 de 293
  episodios llegó a 90°. La constante de autoridad de giro es plana.
- **Confirmado:** `rxspeed` vale sólo 0 o 40 en 61.615 muestras.
- **Corregido:** los videos son de 33,3 fps, no 20. `rxsteer` está ×1000.
- **No atribuible:** el "hallazgo de las 22:01" (`como_esta.avi` se grabó en otro tramo).

---

## Bitácora

- **inicio** — recuperado el `main.py` real de la Pi del transcripto de la sesión
  (línea 1105, 33.411 chars). Sintaxis OK, 920 líneas. Guardado en scratchpad como
  `main_pi_real.py`.
- **H-1 confirmada** con medición propia sobre 13.900 frames.
