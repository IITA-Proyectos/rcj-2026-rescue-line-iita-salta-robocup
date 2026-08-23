# Trabajo nocturno del 2026-08-23 — registro vivo

_Este archivo tiene que alcanzar para retomar exactamente donde quedé, sin depender del
contexto de la conversación. Se actualiza a medida que avanza, no al final._

**Punto de partida:** [ANALISIS-2026-08-23.md](ANALISIS-2026-08-23.md) (workflow de 13
agentes) e [INFORME-2026-08-22.md](INFORME-2026-08-22.md).

**Regla de seguridad de la noche: NO se mueve el robot.** Sólo código, git, CSV, videos,
replay, compilación y análisis.

---

## COMO RETOMAR SI SE CORTA LA SESION

**Los workflows corren en background y su resultado queda en disco.** Si la sesion se corta
por limite de tiempo o de creditos, NO hay que volver a empezar: hay que leer el journal.

### Los workflows lanzados

| run ID | que hace | estado |
|---|---|---|
| `wf_1d653bde-be6` | analisis de los 10 videos y 10 CSV | **terminado** -> `ANALISIS-2026-08-23.md` |
| `wf_94d7612a-538` | idem | **MURIO** por limite de sesion, 0 de 6 agentes terminaron. Sobrevivio `replay.py`, escrito antes de morir |
| `wf_3cd1cde7-d09` | relanzado sin el agente de replay: 3 investigaciones + 3 refutadores + auditoria de tiempo + sintesis | corriendo |

Todo cuelga de la carpeta de la sesion:

```
~/.claude/projects/
  C--Users-villa-rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/
    2ef17249-f56d-4c16-b09f-bc1b458bdb1d/
      workflows/scripts/<nombre>-<runID>.js         el script de cada corrida
      subagents/workflows/wf_<id>/journal.jsonl     una linea de resultado por agente
```

### El procedimiento, en orden

1. **Leer `journal.jsonl` de la corrida cortada.** Tiene una linea `{"type":"result",...}`
   por cada agente que llego a terminar, con su valor de retorno completo. Eso se aprovecha
   aunque el workflow entero no haya cerrado: **el trabajo de los agentes que terminaron no
   se pierde**.
2. **Si es la MISMA sesion**: relanzar con
   `Workflow({scriptPath: "<ruta del script>", resumeFromRunId: "<run ID>"})`. Los agentes
   con prompt y opciones sin cambiar devuelven su resultado cacheado al instante; solo corre
   lo que falta.
3. **Si es una sesion NUEVA**: `resumeFromRunId` no sirve, la cache es por sesion. Se
   relanza con `Workflow({scriptPath: "<ruta>"})` — pero antes hay que leer el journal,
   porque lo ya contestado no hace falta volver a preguntarlo: se edita el script para sacar
   las tareas resueltas.
4. **Este archivo manda.** Antes de relanzar nada, leer el estado y la bitacora. Si un
   hallazgo ya esta confirmado o descartado, NO se vuelve a investigar.

### Regla de la noche

**Nada de lo que se concluya vive solo en la conversacion.** Todo hallazgo confirmado baja a
este archivo apenas se confirma, con su numero y su archivo:linea. Si el contexto se compacta
o la sesion muere, este archivo tiene que alcanzar para seguir sin perder nada.


---

## ESTADO ACTUAL

| prioridad | tarea | estado |
|---|---|---|
| 1.1 | versionar el `main.py` real de la Pi | **hecho** (recuperado del transcripto) |
| 1.2 | `diagProcedencia` con las constantes del `case 7` | pendiente |
| 1.3 | log de la Pi: frame, timestamp, fps real, orden, estado de línea | pendiente |
| 1.4 | fps 20.0 hardcodeados | pendiente |
| 1.5 | auditar frame/timestamp/fps/dt en todo el código | en curso (`wf_3cd1cde7-d09`) |
| 2 | refutar la hipótesis de cancelación prematura | en curso (`wf_3cd1cde7-d09`) |
| 3 | herramienta de replay | **hecho y VALIDADO** |
| 4 | diseño de la lógica de giro comprometido | en curso (`wf_3cd1cde7-d09`) |
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

## H-2 — el banco de replay VALIDA, y de yapa fecha una constante

**Estado: CONFIRMADO. Herramienta usable.**

[`software/raspberry/final_rpi/replay.py`](software/raspberry/final_rpi/replay.py), 1081
líneas. Le da una corrida grabada a una ley de control y devuelve, frame a frame, el ángulo
que **esa** ley habría mandado.

**La validación, que es lo que lo hace usable** — reproduce el `rxsteer` real del CSV sobre
los 960 frames enganchados por `rxf` de la única corrida con video Y telemetría:

| fuente | exacto al grado | ≤1 gr | r |
|---|---|---|---|
| `mascara` | **92,5 %** | 95,5 % | 0,967 |
| `izq-impar` | 84,0 % | **96,2 %** | **0,9957** |

Contra el 81,1 % y r=0,945 del análisis previo. **Mejora la referencia.**

**Y modela el árbol del `case 7`**, alimentándolo con el `rxsteer` real del CSV para separar
firmware de visión:

| `confirma_ms` | \|rot\| dentro de 0,05 | rama igual |
|---|---|---|
| 0 | **92,9 %** | 94,1 % |
| 300 | 66,4 % | 94,1 % |

**Con 0 el modelo cierra y con 300 no**, o sea que esa corrida **no tenía**
`LINE_PIVOTE_CONFIRMA_MS` activo (`main.cpp:3303`). Eso confirma por una vía independiente
lo que ya se sabía: la confirmación de alineación se compiló y nunca se flasheó.

**LO QUE NO PUEDE** (está arriba de todo en el archivo, porque importa más que lo que sí
puede): es replay de **visión**, no simulación física. Las imágenes están grabadas con la
trayectoria que el robot realmente hizo; si la ley candidata hubiera girado antes, los
frames siguientes habrían sido otros. Es **lazo abierto, cortado justo donde vive el
problema**. NO puede decir si el robot habría completado la curva, ni cuántos grados habría
girado, ni si una ley pierde la línea menos veces.

Auditado antes de commitear (es código escrito por un agente): sólo lee, sin red, sin
subprocesos, sin `eval`.


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
- **01:14** — el workflow `wf_94d7612a-538` muere por límite de sesión con 0 de 6 agentes
  terminados (774k tokens, 209 llamadas). El journal sólo tiene líneas `started`: **no hay
  nada que rescatar de ahí**. Pero el agente de replay alcanzó a **escribir el archivo**
  antes de morir, y el archivo estaba completo.
- **H-2 confirmada**: corrí yo la validación que el agente no llegó a correr. Valida.
- **relanzado** como `wf_3cd1cde7-d09`, con el agente de replay reemplazado por su resultado
  ya verificado. Lección de método: **un agente que escribe su producto a disco deja algo
  aunque muera; uno que sólo lo devuelve, no.**
