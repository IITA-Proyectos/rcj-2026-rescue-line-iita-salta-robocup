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
| `wf_3cd1cde7-d09` | relanzado sin replay: 3 investigaciones + refutadores + auditoria + sintesis | **terminado**, 8/8 |
| `wf_9aebdda4-0b8` | revision independiente de los 5 commits | **terminado**: 3 bloqueantes, los 3 cerrados |

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
| 1.2 | `diagProcedencia` con las constantes del `case 7` | **hecho** (`a33cf90`) |
| 1.3 | log de la Pi: frame, timestamp, fps real, orden, estado de línea | **hecho** (`b67096f`) |
| 1.4 | fps 20.0 hardcodeados | **hecho** (`32c148b`) |
| 1.5 | auditar frame/timestamp/fps/dt en todo el código | **hecho** |
| 2 | refutar la hipótesis de cancelación prematura | **hecho**: se cayó el mecanismo, quedó **H-4** |
| 3 | herramienta de replay | **hecho y VALIDADO** |
| 4 | diseño de la lógica de giro comprometido | **hecho e implementado** (`6f143b5`) |
| 5 | pérdida de línea como estado explícito | **detector hecho** (`b67096f`); la MANIOBRA no se toca |

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

## H-3 — el detector de pérdida: 13,5 % de recall contra 98,5 %

**Estado: CONFIRMADO en replay. Es la medición que decide el fix de la pérdida.**

Corrido con el banco de replay ya validado, sobre dos corridas y con **las dos definiciones
de "realmente perdida" reportadas juntas** (filas 100-119 con <30 px, y mancha conexa que
toca el borde inferior):

| video | ley | declara | **recall** | falsos positivos |
|---|---|---|---|---|
| `hist.avi` | la que corrió (`min_line_size=1`) | 2,10 % | **13,5 %** | 0,00 % |
| `hist.avi` | pérdida explícita (mancha conexa <30 px) | 16,21 % | **98,5 %** | 0,91 % |
| `como_esta.avi` | la que corrió | 5,01 % | **40,1 %** | 0,00 % |
| `como_esta.avi` | pérdida explícita | 13,22 % | **98,4 %** | 0,93 % |

**Recall** = de los frames en que la línea realmente NO está, en qué fracción la ley lo
declara. Es la métrica correcta acá, y es peor que lo que sugería el cociente global de H-1:
en `hist.avi` el robot se entera de **1 de cada 7** pérdidas, no de 1 de cada 4.

**Esto se puede medir en replay sin ninguna suposición física**, porque detectar es función
de la imagen, no de la trayectoria. Es exactamente la clase de pregunta que el banco sí
contesta.

### El riesgo que había que despejar, despejado

La preocupación era que detectar la pérdida 3 a 8 veces más seguido rompiera el giro (el
robot pasaría a retroceder una quinta parte de la corrida). **Los números dicen que no
empeora el pedido de giro:**

| | `hist`: la que corrió | `hist`: pérdida explícita |
|---|---|---|
| episodios de giro por segundo | 1,85 | 1,88 |
| duración p90 del pedido | 0,495 s | **0,390 s** |
| re-entradas | 16 | **15** |
| demanda mediana | 9,31 gr·s | 8,79 gr·s |

### Lo que queda abierto

**Los falsos positivos no son cero: 0,91 %.** Sobre 13.900 frames son ~127 frames en que la
ley declararía pérdida con la línea presente. Falta definir qué hace el robot en esos casos
— si la respuesta a la pérdida es cara (retroceder), un 0,9 % de falsos positivos puede
costar. Eso hay que resolverlo en el diseño, no en el detector.

**Y ojo con la unidad:** el replay reporta "demanda" en **grado·segundo**, no en grados.
Los grados girados NO se pueden calcular en replay. Está dicho en el docstring y no es una
precaución retórica.


---

## H-4 — LA CAUSA. El pivote dura 0,190 s y entrega 4,9 grados

**Estado: es la única hipótesis que quedó en pie después de tres investigaciones y tres
refutaciones adversariales. Reproducida con script propio.**

Tramos contiguos de linetrack con `|rot| ≥ 0,95` y **signo de `rot` constante**, las 6
corridas de pista juntas:

| | valor |
|---|---|
| tramos | **369** |
| duración p50 / p90 | **0,190 s** / 0,385 s |
| grados entregados p50 / p90 | **4,9°** / 14,9° |
| tramos que llegaron a 45° | 1 de 369 |
| tramos que llegaron a 90° | **0 de 369** |
| tramos consecutivos que **cambian de signo** | **32 % a 87 %** |

Y el presupuesto global de rotación en linetrack:

| corrida | ∫\|gz\| bruto | neto | °/min bruto |
|---|---|---|---|
| arbol_de_ramas | 885° | −78° | 1184 |
| gain18 | 1279° | −283° | 1549 |
| pivote35 | 1731° | **+3°** | 2100 |
| pivote_con_histeresis | 1404° | +2° | 1530 |
| pivote_sin_histeresis | 1684° | +13° | 2174 |
| rampa_continua_pivote20 | 1134° | +20° | 1449 |

**El robot gira 1.184 a 2.174 grados por minuto y entrega neto ±20.** Autoridad sobra para
13 a 24 curvas de 90° por minuto. Lo que falta es **persistencia de dirección**.

**No es "el controlador cancela el giro" ni "la intención es ruidosa": es un ciclo límite.**
Y la variable de diseño que lo gobierna no es el gatillo ni el umbral ni el detector: es
**el tiempo mínimo que el signo de `rot` queda quieto**.

### Las dos mitades del mecanismo, medidas

- **El actuador.** Grados por tramo contra duración: 1,0 / 3,8 / 5,3 / 8,8 / 12,1 / 19,2
  para tramos de 0-0,1 / 0,1-0,15 / 0,15-0,25 / 0,25-0,4 / 0,4-0,6 / 0,6-3,0 s. La **tasa**
  es plana en ~39 °/s arriba de 150 ms y cae a 21,6 abajo de 100 ms.
- **El sensor.** Δ(ángulo de cámara) contra Δ(rumbo real): **6,96 a 9,57 grados de cámara
  por grado real**, consistente en las seis corridas. La visión no mide rumbo.

### Y la tasa de giro SATURA

| `ls` | tasa | 90° cuestan |
|---|---|---|
| 0–22 | 19,6 °/s | 4,60 s |
| 32–42 | **39,3 °/s** | 2,29 s |
| 42–60 | 39,2 °/s | 2,29 s |

**Subir de 20 a 35 rpm duplica el giro; de 35 a 50 no compra nada.** Esto contradice los
"55-65 °/s a 50 rpm" que circulaban: ese número sale de muestras instantáneas, éste de
tramos sostenidos, que es lo que importa para una curva. Con 39 °/s, **el tope de
`LINE_PIVOTE_MAX_MS = 2500` está sobre el filo**, no con margen.

---

## EL HALLAZGO MÁS INCÓMODO: el binario de competencia no compilaba nada de esto

`default_envs = teensy_hid_device` (platformio.ini:5) y `FIX_CURVA_CONTINUA` vale **0** por
defecto (main.cpp:49-50). El `#if FIX_CURVA_CONTINUA` abarca las líneas 3323-3464 y el
`#else` es el árbol de ramas histórico.

**Toda la maquinaria que se midió y se tuneó el 22-ago —rampa continua, pivote, histéresis,
velocidad de pivote— vive dentro de ese `#if`, y `pio run -t upload` a secas no lo
compilaba.** Diez CSV grabados con `diagnostico_fix` mientras el binario que iría a la pista
se habría comportado distinto.

Verificado leyendo los dos bloques: `competencia_fix` extiende a `teensy_hid_device` y
agrega **sólo** `-D FIX_LAZO_MOTOR=1` y `-D FIX_CURVA_CONTINUA=1`. Misma placa, mismo
framework, mismas librerías, mismo script de commit.

---

## LO QUE SE IMPLEMENTÓ ESTA NOCHE

Cinco commits chicos, cada uno con su hipótesis, su verificación y su vuelta atrás.

| commit | qué | verificado |
|---|---|---|
| `a33cf90` | las constantes del `case 7` salen en `diagProcedencia` y se barren por `build_flags` | compilan los 3 entornos; los valores no cambian |
| `6f143b5` | **el fix central**: el signo del pivote no se da vuelta antes de `T_min` | compila con dwell 0 y 300; bandera verificada con `pio run -v` |
| `95cba6b` | el binario por defecto compila el árbol nuevo | `pio run` a secas ahora da `competencia_fix` |
| `b67096f` | log de visión por frame + detector de pérdida por mancha conexa | parche aplicado sobre el `main.py` real; recall 98,5/98,9/100 % contra 13,5-40,1 % |
| `32c148b` | el fps de 20 estaba escrito a mano | `como_esta.avi` pasa de 75 s declarados a 45 s reales |

### El patrón del fix central

Con el pivote enganchado `rot` vale 1,0 —la magnitud queda latcheada— pero el **signo** sale
de `steerCmd`, o sea de la trama que acaba de llegar. El fix guarda el signo al enganchar y
lo sostiene `T_min` ms. **No** hay objetivo en grados, **no** se integra la IMU, **no** hay
condición de salida nueva y **no** se toca el gatillo. Sólo retrasa la inversión.

Queda **inhibido en rampa**: 40 líneas más abajo, con `pitch > PITCH_RAMPA`, las traseras se
pisan en configuración de marcha recta **después** del `steer`, así que en pendiente
pelearían contra el pivote.

**`LINE_PIVOTE_DWELL_MS = 0` es el valor por defecto y deja el comportamiento histórico byte
por byte** — la comparación unsigned contra `0UL` nunca se cumple. Se vuelve atrás con una
constante, sin `git revert` y sin recompilar de memoria en la pista.

### El criterio de éxito, falsable y medible del CSV

Los tramos de pivote con signo constante tienen que pasar de **0,190 s / 4,9°** a ≥ `T_min`
y ≈ `39 × T_min` grados. Con `T_min = 0,30 s`: unos 11-12 grados, o sea **2,3×**.

**Si un tramo de 0,30 s entrega menos de 8 grados, la hipótesis del transitorio se cae** y
lo que sigue es la actuación, no el control.

---

## LO QUE SE DESCARTÓ ESTA NOCHE, con el número

- **El diseño de "giro comprometido con objetivo extensible"**: simulado sobre el `rxsteer`
  grabado, el **100 %** de los episodios cierra en el tope de 100° y **0 %** por tiempo, y
  ocupa 23,7-56,0 % del linetrack. Degenera; no se rescata con tuneo.
- **`LINE_PIVOTE_CONFIRMA_MS = 300` tal como está compilado**: 71-100 % de los episodios
  terminaría por el tope de 2500 ms. Y el replay lo confirma por otra vía: con 0 el modelo
  del `case 7` reproduce el 94,1 % de la rama, con 300 baja a 66,4 %.
- **"La autoridad de giro se duplicó"**: era `LINE_PIVOT_SPEED` subiendo. Y la tasa satura
  arriba de 35 rpm.

---

## UN P0 LATENTE QUE APARECIÓ DE COSTADO

**El detector de verde no disparó ni una vez en 417 s de video.** `green_mask` nunca pasó de
6 píxeles contra un umbral de 510. O no había verde en esa pista, o el rango de color no
sirve con esa luz. **Hay que resolverlo aparte, y antes de la competencia.**

Y uno preexistente: la cadena de `if` de `main.cpp:3063-3110` no tiene `else` ni `default`, y
`action` es global. Un `green_state` no contemplado —la Pi manda **10 y 11**— deja la acción
anterior. Si la anterior fue 4, el robot sigue retrocediendo mientras la Pi pide otra cosa.

---

## LA REVISIÓN INDEPENDIENTE — encontró tres bloqueantes, los tres míos

Tres revisores independientes sobre los cinco commits. **Veredicto inicial: no se lleva a la
pista.** Los tres bloqueantes están cerrados y verificados con medición propia.

### B-1 — `LINE_PIVOTE_CONFIRMA_MS = 300` se iba a flashear por primera vez

Al poner `competencia_fix` por defecto se enciende `FIX_CURVA_CONTINUA`, y adentro vive un
pivote que exige **300 ms de alineación sostenida** para soltar. **Ese valor nunca corrió en
el robot.**

Medido por mí sobre los 6 CSV — las rachas continuas de `absSteer ≤ 0,15`:

| corrida | p50 | p90 | **% que llega a 300 ms** |
|---|---|---|---|
| arbol_de_ramas | 75 ms | 240 ms | 7,7 % |
| gain18 | 55 ms | 235 ms | 6,6 % |
| pivote35 | 70 ms | 195 ms | 1,2 % |
| pivote_con_histeresis | 50 ms | 150 ms | 1,7 % |
| pivote_sin_histeresis | 50 ms | 195 ms | 1,9 % |
| rampa_continua_pivote20 | 70 ms | 230 ms | 3,3 % |

**La salida por alineación es inalcanzable.** El pivote saldría siempre por el tope de
2500 ms, y en pivote `rot = 1,0` → `_leftspeed = −speed` → **avance cero por diseño**. El
robot giraría en el lugar 2,5 s, soltaría, y volvería a enganchar. **Eso es Lack of Progress
delante del árbitro.**

Y había una contradicción interna que lo decidía sola: mi propio comentario decía *"NO
flashear en 300 sin medirlo antes"* y el commit siguiente lo flasheaba.

**Cerrado:** el default pasa a **0**, que es la histéresis simple que realmente corrió el
22-ago y que el replay valida al 94,1 % de rama igual. Rango útil medido: 300 ms deja pasar
el 3 %, **100 ms el 31 %**, 50 ms el 61 %.

### B-2 — el dwell contaba desde la entrada al pivote

Sólo protegía la **primera** inversión de cada episodio; después el signo volvía a
rescribirse cada trama. **Cerrado:** cada inversión se gana su propia ventana, y el static
se limpia al salir del pivote o al entrar en rampa.

### B-3 — `LOG=` no estaba documentado

Ni en el docstring ni en las instrucciones que el parche imprime. **El sábado habrían
corrido lo que dice la pantalla y vuelto sin CSV: los dos commits de la noche no habrían
entregado nada.** Cerrado en los dos lugares.

---

## EL CRITERIO PASS ESTABA MEDIDO SOBRE UNA POBLACIÓN QUE YA NO EXISTE

Lo más valioso de la revisión, y no lo había visto ningún agente antes.

Los **0,190 s** salen de las seis corridas del 22-ago, y **ninguna tenía el latch de pivote
encendido** — verificado: `s_en_pivote` no existe en los commits que las produjeron. Sin
latch, `rot` sigue a `absSteer` y el tramo se corta apenas baja el ángulo.

| | termina por cambio de signo | por salir de banda |
|---|---|---|
| `arbol_de_ramas` (sin latch) | 0,0 % | 100,0 % |
| `pivote_sin_histeresis` (umbral, sin latch) | 7,3 % | 92,7 % |
| **`pivote_con_histeresis` (con latch)** | **52,0 %** | 48,0 % |
| **TOTAL** | **20,1 %** | **79,9 %** |

**Encender el latch solo, sin dwell, ya lleva el p50 a ~245 ms.** Así que la base del sábado
**no es 0,190 s: es el bloque de `T_min = 0` de ese mismo día.**

Y el efecto esperado del dwell es **moderado**: 245 → 305 ms de p50, y 39 → 51 % de tramos
sobre 300 ms. El salto grande lo da el latch, no el dwell.

**Esto reencuadra la prueba del sábado y ya está corregido en el plan.**

---

## LO QUE LA REVISIÓN DESCARTÓ A PROPÓSITO, con el número

- **Bajar `LINE_PIVOTE_MAX_MS` a 800 ms**: a 39 °/s, 90° cuestan 2,3 s. Capa el pivote en
  ~31° y mata justo lo que se quiere habilitar. Y con `CONFIRMA=0` sólo el 0-12 % de los
  episodios llega al tope.
- **La guarda `availableForWrite() < 420`**: inerte por USB, que devuelve múltiplos de 2048.
  Sólo mordería en `diagnostico_suelto` (Serial8).
- **Revertir `FIX_LAZO_MOTOR`**: corrió en pista en 5 de 6 corridas (`fix_lazo=1` en la
  procedencia). Lo que sigue sin medir es `MOTO_PWM_ANTICOAST 20.0` y el comportamiento en
  verde/rescate.
- **Tocar `PITCH_RAMPA`**: `pitch > 12` pasa el 0,00 % del tiempo en 4 corridas y 0,3-0,8 %
  en dos, con ráfagas de 125-185 ms. Existe, es raro, y para el dwell falla del lado seguro.

---

## ESTADO FINAL DE LA NOCHE

**Ocho commits.** Los tres bloqueantes cerrados. Los tres entornos compilan. El parche entra
sobre el `main.py` real, compila, y `--revertir` deja el archivo **idéntico byte a byte**.

**Lo que NO se puede saber sin el robot, y por eso el sábado existe:**

1. Si sostener el signo completa la curva. Todo el análisis es **lazo abierto** sobre
   `rxsteer` grabado con la trayectoria que el robot realmente hizo.
2. Si el `T_min` correcto son 250 o 400 ms.
3. Si los ~39 °/s se sostienen en el piso de la sede.
4. Cuántos grados pide de verdad la curva que falla — no hay mapa de pista.
5. Si `FIX_LAZO_MOTOR` se porta bien en verde, plateado y rescate: ninguna corrida grabada
   llegó a evacuación.
6. **Si un giro sostenido tapa un verde.** Y arriba de eso, el P0 aparte: **el detector de
   verde no disparó ni una vez en 417 s de video.**

---

## H-5 — la pérdida NO es deriva: el robot va a CRUZAR la cinta

**Estado: la única señal anticipatoria que apareció. 5,7x de enriquecimiento.**

Benjamín observó en dos frames que el robot queda descentrado después de girar y propuso
que eso es lo que lo saca de pista. **Su hipótesis, medida contra control, NO se sostiene —
pero la intuición geométrica sí, y apunta a otra cosa.**

### Lo que se cae: el desvío no predice nada

Desvío lateral en la fila 119, en los instantes previos a cada pérdida, sobre 8 videos:

| momento | desvío | control |
|---|---|---|
| −1,0 a −0,4 s | 10-13 px | **12,0 px** |
| −0,4 a −0,2 s | 12,0 px | 12,0 px |

**Hasta 200 ms antes, el robot está idéntico a un frame sano.** No hay deriva gradual. Y al
soltar el pivote el desvío da 13,5-16,2 px contra 9,5-17,0 de control: comparable.

### Lo que también se cae: mi propia cadena causal

"La pérdida viene después de que el pivote suelta": **61 %** de las pérdidas tienen una
suelta en el segundo previo — pero el **control es 64-81 %**. El pivote suelta cada ~0,8 s,
así que "soltó hace poco" no informa nada. **Refutado.**

### Lo que SÍ aparece: la mancha se aplana

| momento | ancho | alto | **alto/ancho** |
|---|---|---|---|
| −1,0 a −0,63 s | 107 | 59 | 0,51 |
| −0,60 a −0,30 s | 123 | 50 | **0,38** |
| −0,27 a −0,15 s | 134 | 30 | **0,24** |
| −0,12 a −0,06 s | 55 | 16 | 0,24 |
| **control** | 98 | 59 | **0,56** |

**Una banda ancha y chata es la cinta cruzando el campo de visión.** O sea: el robot no se
va despacio hacia el costado — **se va derecho a atravesar la cinta en vez de seguirla.**
Es "no gira lo suficiente", pero expresado en geometría y no en posición.

### Separabilidad, que es lo que decide si sirve

Ventana −0,60 a −0,12 s, n=809 pre-pérdida contra n=4591 control:

| umbral | % pre-pérdida | % control | enriquecimiento |
|---|---|---|---|
| alto/ancho < 0,25 | 22,4 % | 3,9 % | **5,7x** |
| **alto/ancho < 0,30** | **36,3 %** | **6,3 %** | **5,7x** |
| alto/ancho < 0,35 | 46,4 % | 8,4 % | 5,5x |
| alto/ancho < 0,40 | 58,3 % | 18,2 % | 3,2x |

**No es un detector limpio** —se le escapa el 64 % de las pre-pérdidas y prende en el 6 % de
las sanas— pero es **la primera variable del proyecto que separa algo**. El desvío da 1,0x.

Y da **0,3 a 0,6 s de aviso**, que a 39 grados/s son **12 a 23 grados de giro disponibles**
antes de perderla.

### Lo que NO está probado

Que actuar sobre esa señal sirva. Es una correlación medida con control, no un mecanismo
demostrado. Y el proyecto ya enterró once conclusiones que parecían mecanismos.


---

## H-6 — el dwell no puede arreglar esto, y la reconstrucción frame a frame dice por qué

**Estado: el fix de anoche ataca un mecanismo que no es el dominante. Confirmado por dos
caminos independientes.**

Un análisis externo (ChatGPT, aportado por Benjamín) recorrió los 960 frames del video
comparativo. **Verifiqué todos sus números y dan todos:**

| | él dice | yo mido |
|---|---|---|
| frames con la misma orden | 823 | **823** |
| frames que difieren | 137 | **137** |
| de esos, ambos EN PIVOTE | 137 (100 %) | **137** |
| ancho de la mancha en el frame 1365 | 94 % | **94 % (151/160)** |
| frames con `rot ≈ 0` | 28 | **28** |
| de esos, sin cinta útil cerca | 23 (82 %) | **24 (85 %)** |

**Su punto estructural es correcto y es el que importa: los 137 cambios del dwell son TODOS
pivote-signo-A por pivote-signo-B. El dwell nunca evita que el pivote SUELTE.** Es cierto
por construcción de la implementación, y significa que no puede tocar el fallo dominante —
que es la suelta, el 88 % de las terminaciones.

### El frame 1374, la suelta en flagrante

```
1373  -27.0 | cerca  +5.2   lejos -32.6   tang -37.8 | PIVOTE
1374   -3.0 | cerca  +1.7   lejos -42.6   tang -44.3 | SUELTA (absSteer=0.04 <= 0.15)
1375..1384  | cerca  +0.0 (perfecto)      lejos -44 -> -72
```

Suelta con la banda cercana centrada mientras la continuación está a 42 px para el otro
lado. Y después queda **impecablemente alineado con el piso que ya pasó** y completamente
equivocado para adonde va.

Después: 1400-1433 el área colapsa (1482 → 964 → 475 → ... → 3) con el ángulo saturado en
±85-90, y en **1434-1463** hay ~0,9 s con área 0 en los que la visión sigue mandando +37 a
+40 grados **calculados sobre el salón** — el bug de `min_line_size`, en vivo.

### Pero la generalización es más débil que la anécdota, y hay que decirlo

Sobre **224 sueltas** de 6 videos:

| | al soltar | control |
|---|---|---|
| \|cerca\| | 11,7 px | 13,1 px |
| **\|tang\|** | **23,8 px** | **23,4 px** |

**El `tang` al soltar es igual al del control.** La suelta NO selecciona momentos de mal
rumbo: es **ciega al rumbo siempre**. El 44 % de las sueltas tienen `|cerca| < 10` ("la
visión las llama alineado") y de ésas el 50 % tiene `|tang| > 20`, o sea que el caso limpio
del 1374 es el **22 %** de las sueltas, no la mayoría.

**Lo que sí queda demostrado, y es más fuerte:** el error de rumbo vale **~24 px de forma
permanente**, pivotee o no. Coincide con lo medido el 22-ago por otro camino ("centrado 40 %
del tiempo pero 57 % de esos con rumbo torcido, mediana 28,6 px"). **El controlador no lo
corrige nunca porque no lo mide.**

### Consecuencia para el plan

El dwell (`6f143b5`) **queda, porque es inerte en 0 y no estorba**, pero **baja de prioridad**:
no puede evitar una suelta. Lo que hay que atacar es la condición de salida, que hoy es
`absSteer <= 0,15` sobre una máscara dominada por la banda cercana.

Y el intento de término de rumbo del 22-ago (`rumbo.avi`) bajó el rumbo torcido de 28,6 a
22,3 px pero derrumbó el centrado de 40 % a 26 %: **falló por balance de ganancias, no por
concepto.** Eso lo vuelve a poner sobre la mesa.


---

## H-7 — el experimento natural: la MISMA curva, 27 veces bien y 12 veces mal

**Estado: el mejor control que apareció en todo el proyecto, y da vuelta el orden causal.**

Benjamín notó mirando `hist.avi` entero que **el robot sí hace la misma curva en otros
momentos**. Eso es un experimento natural: misma corrida, mismo firmware, misma pista, mismo
día — elimina de un saque todos los confounds de tramo y configuración.

Catalogados los **49 eventos de giro** de `hist.avi` (|ángulo| ≥ 40° sostenido ≥ 8 frames):

**27 completan sin perder la línea. 12 la pierden.**

### Qué los distingue — y NO es la posición

Rasgos medidos en los 10 frames **previos a entrar** al giro:

| rasgo | completa | pierde | razón |
|---|---|---|---|
| **área de la mancha** | **2731 px** | **150 px** | **0,05x** |
| ancho en la fila 119 | 75,5 | 26,0 | 0,34x |
| alto | 39,8 | 9,2 | 0,23x |
| alto/ancho | 0,3 | 0,3 | 0,79x |
| **desvío \|cerca\|** | **18,9** | **19,2** | **1,01x** |

**El desvío lateral es idéntico.** Por tercera vez, la posición no discrimina nada.

**Lo que discrimina es cuánta cinta tiene el robot cuando ARRANCA el giro.**

### El orden causal se da vuelta

No es "el giro falla y entonces pierde la línea". Es **"ya casi no tiene línea, y entonces
se compromete a un giro grande sobre lo que queda"**. Y ese giro falla.

Eso encaja exactamente con H-1: como `min_line_size = 1` no dispara nunca, el robot calcula
un ángulo confiado sobre un resto de 150 px —o sobre el salón— y se manda.

### Generalizado a 8 videos, más débil pero en la misma dirección

| | completa | pierde |
|---|---|---|
| `hist.avi` sola (n=32/8) | 2731 px | 150 px (**18x**) |
| 8 videos (n=192/66) | 3532 px | 974 px (**3,6x**) |

Como detector, con umbral de 500 px: atrapa el **45 %** de los giros que fallan con **14 %**
de falsa alarma (~3,2x de enriquecimiento). Es la señal más fuerte del proyecto junto con el
aplanamiento, y muy por encima del desvío, que da 1,0x.

**Caveat honesto:** el área antes del giro está autocorrelacionada con el área después, y
"perder" significa que el área se fue a cero. O sea que parte de la separación es trivial.
Lo que NO es trivial es que sea **medible antes de comprometerse**, y que el robot hoy no la
mire.

### Consecuencia directa sobre lo que se commiteó anoche

`AREA_PERDIDA = 30` (en `b67096f`) sólo atrapa el **24 %** de estos giros. Ese umbral está
pensado para "no hay línea", no para "casi no hay línea". **Para esta señal hace falta un
umbral 10 a 30 veces mayor, y como condición de ENTRADA al giro, no de pérdida.**

El patrón que sale: **no comprometerse a un giro grande cuando la evidencia es pobre.** Hoy
el gatillo es sólo `absSteer >= 0,60`, sin mirar sobre cuántos píxeles se calculó ese ángulo.


---

## H-8 — ERROR MIO: usé un modelo teniendo la telemetría al lado. Y el dwell está muerto.

**Estado: corrección. Un análisis externo detectó que mi replay contradice al CSV, y tenía
razón.**

### El error

Le dije a Benjamín que en el frame 1374 el pivote soltaba. **El CSV dice `rot = −1,000`: el
pivote seguía enganchado a fondo.** Yo alimenté un MODELO del `case 7` con el `rxsteer` real
en vez de leer **la columna `rot`, que estaba en el mismo archivo**.

Validación que nunca hice, sobre los 961 frames enganchados:

| `confirma_ms` | coincide con el `rot` real | sueltas del modelo | **sueltas reales** |
|---|---|---|---|
| 0 | 92,0 % | 36 | **55** |
| 300 | 63,5 % | 10 | 55 |

El modelo coincide 92 % en el estado pero **subestima las sueltas un 35 %**. Todas mis
estadísticas de "224 sueltas" y "88 % por alineación" están construidas sobre ese conteo.

### Los números corregidos, con `rot` real, 295 episodios de 6 corridas

| | modelo (mal) | **telemetría** | mi 1ra medición |
|---|---|---|---|
| duración p50 | 428 ms | **210 ms** | 190 ms ✓ |
| grados p50 | 11,1 | **6,0** | 4,9 ✓ |
| llegan a 45° | 5 % | **1 %** | 0,3 % ✓ |

**Mi primera medición era la correcta.** La "corrección" a 428 ms fue el error: sustituí
telemetría por modelo y empeoré un número que ya estaba bien.

### El dwell queda muerto, y con número

**74 inversiones de signo DENTRO del pivote en las 6 corridas** — 0,16 por segundo. Y **39
de las 74 son de `pivote_con_histeresis`**, la corrida con los motores parados la mitad del
tiempo. En las cinco limpias: 0, 14, 8, 6, 7.

El dwell (`6f143b5`) sólo puede actuar sobre esos 74 eventos. **No es la palanca.** Queda en
el árbol porque es inerte en 0, pero sale del plan del sábado.

### Y la mecánica está sana, medido

En el tramo 1354-1490, con `gz` real:

| | |
|---|---|
| giro **neto** | **−8,8°** |
| giro **bruto** (suma de \|gz\|) | **147,6°** |
| **se cancela** | **94 %** |
| correlación `rot` ordenado ↔ `gz` medido | **r = 0,927 a 60 ms** |

**El robot gira 147° en 3,7 s y termina donde empezó.** Y los motores obedecen fielmente. El
problema no es la autoridad ni la mecánica: es que la orden se contradice a sí misma.

---

## H-9 — `forward_path_valid`: la variable que falta

**Estado: el discriminador más fuerte del proyecto. Mismo firmware, misma corrida.**

Benjamín tenía un video de cuando **sí** tomaba la curva. Resultó ser **los frames 580-679
de `hist.avi`** — o sea el mismo firmware, la misma sesión y el mismo algoritmo que la falla
de 1354-1490. Es el control positivo que faltaba.

| | éxito 580-679 | falla 1354-1490 |
|---|---|---|
| frames | 100 | 137 |
| componente conexa CERCA (filas 110-119) | **100/100** | 105/137 |
| ...que llega a MEDIA (95-105) | **100/100** | 76/137 |
| ...que llega a LEJOS (75-85) | **86/100** | 56/137 |
| sin componente cercana | **0/100** | 32/137 |
| **giros fuertes (≥30°) con continuación LEJANA conectada** | **55/69 = 79,7 %** | **12/63 = 19,0 %** |

**4,2× de diferencia, con el firmware y la corrida controlados.**

Cuando sale bien, el giro fuerte está **respaldado por una trayectoria que va desde debajo
del robot hasta adelante**. Cuando se sale, casi todos los giros fuertes ocurren **sin
ninguna continuación frontal conectada**: hay negro, pero no hay camino.

**El robot no distingue "veo negro" de "sé por dónde sigue la línea".** Esa variable no
existe en el código: todo se comprime en `angle = atan2(...)` sobre la máscara entera.

Y explica lo que Benjamín venía diciendo desde el principio: **"si lo pongo en cierta
posición sí gira"**. No cambiaba ruedas ni ganancias — cambiaba la geometría que entraba en
la cámara.


### H-9b — GENERALIZA. No fue suerte de ese par.

Corrido el mismo criterio sobre **los 10 videos** (4 leyes de control distintas, tramos
distintos de pista), 4.247 frames de giro:

| | con camino al frente |
|---|---|
| giros que **completan** | **76,2 %** |
| giros que **pierden** | **19,1 %** |
| | **4,00x** |

Contra el 79,7 % / 19,0 % del par único: **prácticamente idéntico**. La señal no depende del
tramo ni de la ley de control.

**Como detector, por evento** (n=217 completan, 68 pierden). Evidencia = fracción de los
primeros 5 frames del giro con camino conectado:

| regla | giros MALOS que evita | giros BUENOS que bloquea | balance |
|---|---|---|---|
| **sin NINGÚN camino** | **63 %** | **16 %** | **4,0x** |
| camino en ≤1 de 5 | 66 % | 19 % | 3,5x |
| camino en ≤2 de 5 | 71 % | 23 % | 3,1x |
| camino en ≤3 de 5 | 74 % | 30 % | 2,4x |

**63 % de los giros que se salen, evitados, bloqueando el 16 % de los buenos.** Es el
detector más usable que apareció en todo el proyecto.

**Hoy el gatillo del pivote es sólo `absSteer >= 0,60`**, sin mirar sobre qué evidencia se
calculó ese ángulo. El patrón que sale: **no comprometerse a un giro fuerte sin un camino
conexo que vaya desde debajo del robot hasta adelante.**

**Lo que sigue sin estar probado:** que actuar sobre la señal mejore la corrida. Todo esto
es observacional sobre trayectorias grabadas; el robot nunca dejó de comprometerse por falta
de evidencia, así que no hay contrafáctico. Eso se mide en pista.


---

## H-10 — MEDIA, no LEJOS. Y el contraejemplo que lo prueba.

**Estado: la señal se afina y el riesgo de romper la T queda cerrado. Pero aparece un
límite de generalización que hay que decir.**

Un análisis externo encontró el contraejemplo que tumba la versión anterior. Reproducido con
mis definiciones (giro fuerte = |ángulo| ≥ 30°):

| caso | n | near | mid | **far** | área p50 |
|---|---|---|---|---|---|
| `hist` BUENO 580-679 | 69 | 100 % | 100 % | 79,7 % | **3017** |
| **`lineal` BUENO 800-872** | 73 | 100 % | **100 %** | **42,5 %** | **1538** |
| `hist` FALLA 1354-1490 | 63 | 90,5 % | **47,6 %** | 19,0 % | **532** |

**Las áreas dan exactas** contra su medición (3017 / 1538 / 532).

**`lineal` completa un giro de ~77° con `far` en 42,5 %.** O sea que **"no llega a LEJOS" no
puede ser una compuerta dura**: bloquearía un giro que sale bien. Pero `mid` vale 100 % ahí,
y 47,6 % en la falla.

### Matriz de confusión, 10 videos, 285 eventos (68 malos / 217 buenos)

| regla | captura | **precisión** | **bloquea buenos** |
|---|---|---|---|
| no llega a LEJOS en 5 de 5 | 63 % | 56 % | **16 %** |
| **no llega a MEDIA en 5 de 5** | 49 % | **69 %** | **7 %** |
| no llega a MEDIA en ≥4 de 5 | 53 % | 65 % | 9 % |
| área mediana < 800 px | 59 % | 55 % | 15 % |

**MEDIA cambia 14 puntos de captura por 13 de precisión y la mitad del bloqueo.** El área no
aporta nada por encima de MEDIA.

### El límite que hay que decir: la captura NO generaliza uniforme

| video | captura | bloqueo |
|---|---|---|
| `hist` | **89 %** | 18 % |
| `lineal` | 67 % | 17 % |
| `lineal70` | 67 % | 5 % |
| `roi_auto` | **29 %** | 3 % |
| `como_esta` | 33 % | 0 % |
| `seguir` | 29 % | 9 % |
| `con_planner` | **0 %** | 0 % |

**Tres videos aportan 22 de los 33 aciertos, y la regla anda mejor justo donde se
descubrió.** El **bloqueo sí es robusto** (0-18 % en todos), pero la captura va de 0 a 89 %.
Es un indicio de sobreajuste a `hist` y hay que tratarlo como tal.

### El riesgo de la T queda cerrado por construcción

| estado | n | área p50 | travesaño p50 | % con área ≥1500 |
|---|---|---|---|---|
| cerca + media | 9.022 | 3216 | 63 | 89,2 % |
| **sólo cerca (LOW)** | 672 | **79** | **0** | **0,0 %** |

**Ninguno de los 672 frames LOW tiene área de intersección.** Una T tiene el travesaño a
distancia media y conectado al tronco, así que **satisface `mid`**. La regla de MEDIA no
puede dispararse en una T.

### Nota de método que queda cerrada

`ram` (columna 11) es `g_line_branch` (`main.cpp:717`), **no** un indicador de pivote. De las
muestras con `|rot| ≥ 0,95`, tienen `ram != 3` el **58,7 %** en `pivote_con_histeresis` y el
**73,6 %** en `sin_histeresis`. **Para el pivote manda `rot`.** (Ese error no se cometió acá
—siempre se usó `rot`, y `ram >= 0` sólo para filtrar linetrack— pero queda escrito.)

### Lo que sigue sin probarse

Que actuar sobre la señal mejore la corrida. El robot **nunca** dejó de comprometerse por
falta de evidencia, así que no hay contrafáctico en ningún archivo. Y con 69 % de precisión
no alcanza para **prohibir** un giro: alcanza para **cambiar de estado**, que es distinto.


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
