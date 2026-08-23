# HANDOFF — seguimiento de línea, cierre del 2026-08-23

_Equipo IITA Salta · RoboCupJunior Rescue Line 2026 · rama `roboliga` · HEAD `ee264d9`_

**Este archivo es autosuficiente.** Una sesión nueva puede continuar leyendo sólo esto más
los archivos que lista, sin releer la conversación anterior.

**Regla de autoridad:** cuando este archivo contradiga a cualquier otro documento del repo,
**gana este archivo**.

---

## 1. QUÉ ES EL PROYECTO Y CUÁL ES EL PROBLEMA REAL

Robot de RoboCupJunior Rescue Line 2026. **Raspberry Pi 4B** procesa la cámara y manda por
UART un ángulo y una velocidad; **Teensy 4.1** ejecuta el movimiento con encoders y PID. El
protocolo es `[0xFF, speed, 0xFE, angle+90, 0xFD, green_state, 0xFC, silver_line]`.

**El hardware NO se cambia.** Ni ruedas, ni cámara, ni montaje.

### El problema observado en pista

En ciertas curvas cerradas el robot **a veces la toma y a veces se sale, con el mismo
firmware y en la misma corrida**, dependiendo de cómo entre. Benjamín lo detectó a mano
mucho antes que cualquier análisis: *"si lo pongo en cierta posición sí gira"*.

**Mecánicamente gira bien.** Lo que falla es que las órdenes se contradicen entre sí.

### Lo que NO es el objetivo

No es "más PID", no es "más velocidad", no es tunear ganancias. **El objetivo es que el robot
siga una trayectoria coherente: saber no sólo dónde está la línea, sino hacia dónde
continúa.** Hoy el código colapsa las dos cosas en un solo número.

---

## 2. ESTADO DE VERDAD

| HALLAZGO | ESTADO | EVIDENCIA | DÓNDE |
|---|---|---|---|
| **Usar `rot` REAL del CSV para saber qué ejecutó el firmware, nunca un modelo** | **VIGENTE** | el modelo coincide 92 % en el estado pero cuenta 36 sueltas contra 55 reales (−35 %) | `OVERNIGHT` H-8 |
| El pivote dura **210 ms** y entrega **6,0 grados**; 1 % llega a 45° | **VIGENTE** | 295 episodios, 6 CSV, columna `rot` real | `OVERNIGHT` H-8 |
| En la falla el robot gira **147,6° brutos** y termina en **−8,8° netos**: se cancela el **94 %** | **VIGENTE** | `gz` real, tramo 1354-1490 | `OVERNIGHT` H-8 |
| **La mecánica obedece**: `rot` ordenado ↔ `gz` medido, **r = 0,927 a 60 ms** | **VIGENTE** | mismo tramo | `OVERNIGHT` H-8 |
| `min_line_size = 1` sobre máscara 0/255: el robot detecta **13,5 %** de las pérdidas | **VIGENTE** | recall sobre `hist.avi` | `OVERNIGHT` H-1, H-3 |
| Detector por componente conexa: **98,4-100 % de recall, 0,9-1,8 % de falsos positivos** | **VIGENTE como DETECTOR** | replay validado, 3 videos | `OVERNIGHT` H-3 |
| **`SIN_CERCA` ≠ `PERDIDA`**: de los frames sin línea debajo, el **61 % tiene pista adelante** | **VIGENTE** | 14.542 frames, 11 videos | `shadow.py` |
| La señal MID: captura 49 %, precisión 69 %, bloquea 7 % de los buenos | **VIGENTE como MEDICIÓN** | 285 eventos, 10 videos | `OVERNIGHT` H-10 |
| La captura de MID **no generaliza uniforme**: 0 % a 89 % según video | **VIGENTE** | desglose por video | `OVERNIGHT` H-10 |
| `near_mid` corta las inversiones de signo **a la mitad**: 736 → 409 | **VIGENTE como MEDICIÓN OFFLINE** | 10 videos, 13.900 frames | `leyes.py` |
| El error de rumbo vale **~24 px permanente** y el control no lo mide | **VIGENTE** | dos caminos independientes (24 y 28,6 px) | `OVERNIGHT` H-6 |
| El binario de competencia **no compilaba** `FIX_CURVA_CONTINUA` | **VIGENTE — CORREGIDO** | `platformio.ini` `default_envs` | commit `95cba6b` |
| `LINE_PIVOTE_CONFIRMA_MS = 300` es **inalcanzable** | **VIGENTE — PUESTO EN 0** | rachas de alineación 50-75 ms, 1,2-7,7 % llega a 300 | commit `57f1133` |
| Los videos son de **~33,3 fps**, no 20 | **VIGENTE** | `parche_planner.py:294` tiene 20.0 fijo | commit `32c148b` |
| `rxsteer` está **×1000**; `yaw/pit/gx/gy/gz` **×10** | **VIGENTE** | `main.cpp:614, 634-635, 713` | — |
| El detector de verde **no disparó ni una vez en 417 s** | **VIGENTE — P0 ABIERTO** | `green_mask` nunca pasó de 6 px contra umbral 510 | `OVERNIGHT` |
| **De 60 pares video×CSV posibles existe UNO** | **VIGENTE** | `hist.avi` ↔ `pivote_con_histeresis` | — |

### SUPERADAS — no volver a usarlas

| conclusión vieja | qué la superó |
|---|---|
| **el frame 1374 fue una "suelta" real** | el CSV dice `rot = −1,000`: el pivote seguía enganchado a fondo |
| **428 ms / 11,1° por pivote** | con `rot` real son **210 ms / 6,0°**. Ese número salía de un modelo |
| **224 sueltas, 88 % por alineación** | conteo del modelo, subestima un 35 % |
| **`forward_path_valid` con la banda LEJANA** | el contraejemplo `lineal` 800-872 |
| **"la autoridad de giro casi se duplicó"** | era `LINE_PIVOT_SPEED` subiendo. La tasa satura en ~39 °/s |
| **el criterio PASS "190 ms → 300 ms"** | esa población se midió sin latch de pivote |

> Los **0,190 s / 4,9°** de la PRIMERA medición **NO** están superados: coinciden con los
> 210 ms / 6,0 de la telemetría. Lo superado fue la "corrección" a 428 ms.

### REFUTADAS — con el número que las mata

| hipótesis | el número |
|---|---|
| **El dwell del signo como solución central** | **74 inversiones dentro del pivote en 6 corridas** (0,16/s), y **39 son de la corrida contaminada**. En las limpias: 0, 14, 8, 6, 7 |
| **"no llega a LEJOS" como compuerta dura** | `lineal` completa ~77° con `far` en 42,5 % |
| **"si no toca abajo hay que retroceder"** | **el 61 % de los frames sin línea debajo tiene pista adelante** |
| **magnitud alta de rumbo = fallo** | `lineal` completa con **52°** de rumbo; la falla tiene 41,7° |
| **estar descentrado explica el fallo** | desvío 12,0 px antes de perder contra **12,0 px** de control. Cuarta medición que lo dice |
| **"la pérdida sigue a una suelta de pivote"** | 61 % contra un control de **64-81 %** |
| **Techo de par / motores al límite** | PWM mediano 53-115 sobre 255; **0,00 % ≥250** |
| **Patinaje variable de las ruedas** | la constante grados/s por rpm es **1,15-1,29** en las 6 corridas |
| **La ISR del registrador roba flancos** | contadores `volatile`; `dt` del ISR = 5000 µs de mediana **y de máximo** |
| **El umbral de negro es muy exigente** | aflojarlo a 180 recupera **8,1 %** de los frames perdidos |
| **El ROI está muy abajo** | el **93 %** del negro de arriba es el salón |
| **Bajar la velocidad para doblar mejor** | la velocidad se cancela en cm/grado |
| **`CONFIRMA_MS` como palanca** | subirlo **acorta** los tramos: 420 → 360 ms |
| **el "hallazgo de las 22:01"** | `como_esta` se grabó en otro tramo: 0,3-1,4 % de vistas compartidas |
| **el replay demuestra que una ley completaría la curva** | **es lazo abierto.** Ver §5 |

### NO PROBADAS EN ROBOT

Todo lo siguiente es **offline**. El robot **nunca corrió** con ninguna de estas cosas:

1. Que la máquina de estados HIGH/MEDIUM/LOW/SIN_CERCA/PERDIDA mejore la corrida.
2. Que `near_mid` o `lookahead` mejoren la corrida.
3. Que el dwell (`LINE_PIVOTE_DWELL_MS`, hoy en 0) sirva.
4. La acción física de cada estado.
5. Si los ~39 °/s se sostienen en el piso de la sede.
6. Cuántos grados pide realmente la curva que falla — **no hay mapa de pista**.
7. Que la geometría de cámara sea la causa raíz.

---

## 3. LOS CUATRO CASOS DE CONTROL — NO SE PUEDEN PERDER

Son la razón por la que este proyecto dejó de girar en círculos. **Toda ley nueva se mide
contra los cuatro antes de decir nada.**

| caso | qué es | por qué importa |
|---|---|---|
| **`hist.avi` 580-679** | ÉXITO | mismo firmware, misma sesión, misma corrida que la falla |
| **`hist.avi` 1354-1490** | FALLA | el tramo del "punto morado" que marcó Benjamín |
| **`lineal.avi` 800-872** | CONTROL POSITIVO FUERTE | completa ~77° con `far` en 42,5 %. **Mata FAR como requisito** |
| **`video_4.avi`** | TEACHER TRACE | Benjamín mueve el robot **a mano** por la trayectoria correcta |

### Por qué `video_4` es el más importante

**Es el único caso donde se conoce de antemano cuál es la respuesta correcta.** Todo lo
demás son fallas: se puede ver qué salió mal, pero no qué habría estado bien.

`video_4` ya encontró **dos errores de diseño** que ningún otro material podía exponer:

1. `near=false ⇒ retroceder` está mal (61 % de esos frames tienen pista adelante).
2. En `SIN_CERCA`, sostener el último signo confiable hacía girar **alejándose** de la cinta
   que estaba reapareciendo. La evidencia presente tiene que mandar sobre la memoria.

**Formato:** `video_4.avi` es **crudo 640×480**. Se procesa `rotate 180 → resize (160,120)
INTER_NEAREST`, igual que hace la Pi. **No es un panel de `GRABAR`.**

Distribución de estados: **HIGH 89 %, MEDIUM 4 %, LOW 1 %, SIN_CERCA 2 %, PERDIDA 4 %.**
Ésa es la firma de una trayectoria correcta.

---

## 4. MANIFEST — qué es cada archivo

### Documentos

| archivo | estado |
|---|---|
| **`HANDOFF_LINEA_2026-08-23_FINAL.md`** | **este. VIGENTE, manda sobre todos** |
| `CURRENT_TRUTH_2026-08-23.md` | **VIGENTE.** Clasificación previa, consistente con ésta |
| `OVERNIGHT_ANALYSIS_2026-08-23.md` | **DIARIO VIVO — CONTIENE SECCIONES SUPERADAS.** Adentro, **H-8, H-9 y H-10 mandan sobre H-4, H-6 y sobre "ESTADO ACTUAL"** |
| `ANALISIS-2026-08-23.md` | **CONTIENE SECCIONES SUPERADAS** |
| `INFORME-2026-08-22.md` | **HISTÓRICO** |
| `ROBOT_TEST_PLAN.md` | **PARCIALMENTE SUPERADO**: su prueba central es el barrido de dwell, que quedó refutado |
| `TRASPASO-2026-08-22.md` | **HISTÓRICO**, reemplazado por `INFORME-2026-08-22.md` |

### Código de visión — `software/raspberry/final_rpi/`

| archivo | estado |
|---|---|
| `main_rpi_2026-08-22.py` | **VIGENTE como REFERENCIA.** Es la foto del `main.py` que REALMENTE corrió. Verificado: su recorte en la fila 60 da 81,1 % de coincidencia contra el CSV; el `Main.py` del repo (fila 55) da 58,1 % |
| `Main.py` | **HISTÓRICO Y DISTINTO.** Otra versión, más vieja. **No confundir** |
| `parche_planner.py` | **VIGENTE.** Parchea el `main.py` de la Pi. Reversible, todo apagado por defecto |
| `replay.py` | **VIGENTE Y VALIDADO**: 84,0 % exacto al grado, r = 0,9957 contra el `rxsteer` real |
| `shadow.py` | **VIGENTE.** Máquina de estados candidata en paralelo. No toca el robot |
| `leyes.py` | **VIGENTE como BANCO.** Las cuatro leyes comparadas. La ley `lookahead` **no** está lista |
| `airborne_birdeye_replay.py` | **PROCEDENCIA DESCONOCIDA, SIN VALIDAR.** 465 líneas, no lo creó esta sesión y **nadie verificó que reproduzca el controlador real**. Tratarlo como borrador |
| `analizar_corrida.py` | **VIGENTE** con el fps corregido |
| `video_dwell.py`, `video_centrado.py` | **HISTÓRICOS**: sirvieron para ver el zangoloteo y el centrado |
| `seguidor_linea.py` | **REFUTADO**: 11 ms/frame y recorre el borde de la mancha |

### Firmware — `software/teensy/firmware/`

| archivo | estado |
|---|---|
| `src/main.cpp` | **VIGENTE.** `case 7` = seguimiento de línea; `case 4` = línea perdida |
| `lib/drivebase/` | **VIGENTE.** `steer()`: `_leftspeed = speed − 2·rot·speed`, y si sale negativa invierte el pin de dirección |
| `platformio.ini` | **VIGENTE.** `default_envs = competencia_fix` desde `95cba6b` |

**Constantes del `case 7`** — desde `a33cf90` son `#define` con guarda y salen en la
procedencia de cada CSV: `LINE_STEER_GAIN` 1.35, `LINE_ROT_EXP` 0.50, `LINE_PIVOTE_ENTRA`
0.60, `LINE_PIVOTE_SALE` 0.15, `LINE_PIVOTE_MAX_MS` 2500, **`LINE_PIVOTE_CONFIRMA_MS` 0**,
`LINE_PIVOT_SPEED` 50, **`LINE_PIVOTE_DWELL_MS` 0**.

### Datos

| qué | dónde | nota |
|---|---|---|
| 10 videos originales | `software/raspberry/final_rpi/*.avi` | paneles **640×240** |
| `video_4.avi` | **`software/raspberry/final_rpi/video_4.avi`** | **crudo 640×480**, 642 frames, **20 fps**. Los bancos lo detectan por nombre y le aplican 20 fps en `--todos` |
| 10 CSV de la Teensy | `software/teensy/firmware/corridas/*.csv` | 45 columnas a 200 Hz. **`..._INVALIDA_ruedas_en_el_aire.csv` NO SE USA** |
| `shadow_*.csv` | derivados | 25 columnas: estado + comando físico completo |
| `leyes_*.csv` | derivados | 14 columnas: las 4 leyes + `x_near`, `x_mid`, `e_lat`, `e_head` |
| `shadow_*.avi`, `leyes_*.avi` | derivados | en `.gitignore`, se regeneran |

---

## 5. REGLAS DE MÉTODO — no negociables

Cada una salió de un error que ya se cometió y costó tiempo.

1. **Validar el replay ANTES de usarlo.** Toda reimplementación del control se compara
   contra el `rxsteer` real del único par enganchado (`hist.avi` ↔
   `2026-08-22_pista_pivote_con_histeresis.csv`, por `rxf`). Referencia: **84,0 % exacto al
   grado, r = 0,9957**. Si no llega a ese orden, **no sirve para comparar leyes**.

2. **Cuando hay CSV, el movimiento se lee de la columna `rot` REAL.** Nunca de un modelo.
   *Esto ya falló: se publicaron estadísticas con un modelo teniendo la telemetría al lado.*

3. **`ram` (columna 11) NO es un indicador de pivote.** Es `g_line_branch` (`main.cpp:717`).
   Con `|rot| ≥ 0,95` tienen `ram != 3` el 58,7 % y el 73,6 % según la corrida. `ram >= 0`
   sólo sirve para filtrar linetrack.

4. **fps real de cada corrida.** Los AVI declaran 20,0 porque el `VideoWriter` lo tiene
   fijo; el lazo corría a ~33,3. **Todos los tiempos publicados antes del 23-ago están
   inflados 1,67×.**

5. **Dos formatos de entrada, y confundirlos da todo al revés.**
   - **640×240** = panel de `GRABAR`: el lado izquierdo YA está rotado y reescalado.
   - **cualquier otro** = video crudo: hay que rotar 180 y reescalar a 160×120 INTER_NEAREST.

6. **El submuestreo del panel vale 19 puntos.** `[::2,::2]` da 65,2 % exacto;
   **`[1::2,1::2]` da 84,0 %**. Tomar los pares —lo intuitivo— es peor.

7. **El replay NO es simulación física.** Las imágenes están grabadas con la trayectoria que
   el robot realmente hizo. Si la ley candidata hubiera girado distinto, los frames
   siguientes habrían sido OTROS. **Nunca afirmar "esto completaría la curva".**

8. **El teacher trace es control PERCEPTUAL, no dinámico.** Dice cómo se ve una trayectoria
   correcta desde la cámara. No dice qué habría hecho el robot.

9. **Medir sobre TODOS los videos antes de declarar generalización.** Ya pasó dos veces que
   un hallazgo fuerte en `hist` se diluyera a la mitad al ampliarlo.

10. **No ajustar un gain porque mejora una métrica offline.**

11. **Buscar contraejemplos activamente.** `lineal` 800-872 mató `FAR` como compuerta; sin
    buscarlo, se habría implementado.

12. **Toda métrica nueva se valida contra 3 casos de respuesta conocida Y un grupo de
    control.** Sin control, "el 53,9 % de los frames de pérdida tiene negro arriba" parece un
    hallazgo y es el salón.

13. **Cuidado con la mediana con signo** sobre poblaciones simétricas: da ~0 y no mide nada.

14. **Un cociente sin unidad no es un porcentaje.**

15. **Gana el código, no la documentación.**

---

## 6. LA ARQUITECTURA DE CONFIANZA — estado y límites

Implementada en `shadow.py`. **No conectada al robot.**

| estado | condición | qué se propone hacer |
|---|---|---|
| **HIGH** | componente conexa desde NEAR hasta FAR | el ángulo manda, sin intervención |
| **MEDIUM** | llega a MID pero no a FAR | el ángulo manda, sin intervención |
| **LOW** | hay referencia cercana pero pobre | **una evidencia pobre no puede invertir instantáneamente una decisión tomada con evidencia buena.** Velocidad reducida |
| **SIN_CERCA** | no toca la zona cercana, **pero hay componente visible adelante** | **ir hacia la mancha visible**, despacio. **NO retroceder** |
| **PERDIDA** | ni debajo ni adelante | maniobra física de recuperación (`case 4`) |

**Bandas:** NEAR filas 110-119, MID 95-105, FAR 75-85, mínimo 8 px por banda.
**Velocidades propuestas:** `VEL_LOW` 15, `VEL_SIN_CERCA` 12 con `ROT_SIN_CERCA` 0,60,
`VEL_PERDIDA` 25.

### El descubrimiento que cambió el diseño

**`near = false` NO equivale a "retroceder".** Sobre 14.542 frames de 11 videos, **el 61 % de
los frames sin línea debajo TIENE pista adelante.** Retroceder ahí sería alejarse de la cinta
que está volviendo.

### Por qué la T no se rompe

Una T tiene el travesaño a distancia media y conectado al tronco, así que da `mid` verdadero
→ cae en HIGH o MEDIUM → **el candidato no interviene**. Medido: de 672 frames LOW, **ninguno**
tenía área de intersección (mediana 79 px contra 3216 de los HIGH).

**Enunciado correcto:** *en los 10 videos disponibles, LOW nunca confundió una T.* Es
evidencia fuerte, **no** una imposibilidad geométrica.

### Lo que NO está probado

**La acción física de cada estado.** Los porcentajes de estado son percepción; que la
conducta asociada mejore la corrida **no tiene ninguna evidencia**, porque el robot nunca
dejó de comprometerse por falta de evidencia. No hay contrafáctico en ningún archivo.

### Comportamiento sobre los casos de control

| tramo | HIGH | MEDIUM | LOW | SIN_CERCA | PERDIDA | inversiones rechazadas | intervenciones |
|---|---|---|---|---|---|---|---|
| `video_4` MANUAL | **89 %** | 4 % | 1 % | 2 % | 4 % | **0** | 44 |
| `hist` ÉXITO | 86 % | 14 % | 0 % | 0 % | 0 % | **0** | **0** |
| `lineal` POSITIVO | 42 % | 58 % | 0 % | 0 % | 0 % | **0** | **0** |
| `hist` FALLA | 41 % | 15 % | 20 % | 10 % | 15 % | 10 | 61 |

**Cero frames tocados en los dos controles positivos.** Es la propiedad más valiosa que
tiene: no estorba lo que ya funciona.

---

## 7. ANTICIPACIÓN — medida, y por qué no alcanza

La caída sostenida de HIGH anticipa algunas pérdidas:

| | |
|---|---|
| p50 | **0,18 s** |
| p75 | 0,30 s |
| p90 | **1,32 s** |
| máx | 1,50 s |
| **falsas alarmas** | **16,2 por minuto** |

Contra 2-3 fallas reales por minuto.

**Conclusión: la pérdida de HIGH sirve como información o contexto, NO como gatillo único.**
Como gatillo suelto dispararía casi todo el tiempo.

Ese número sólo aparece midiendo **por evento**. En el agregado la señal se veía prometedora.

---

## 8. `near_mid` Y `lookahead` — qué se intentó y por qué no está cerrado

### El problema que atacan

El código del 22-ago hace `black_mask → mean(x,y) → atan2 → UN angle`. Ese número **mezcla**
"dónde estoy respecto de la cinta" con "hacia dónde sigue la cinta".

Se demuestra en un frame: **`hist` #1365** tiene la cinta 31 px a la **izquierda** debajo del
robot y yéndose a la **derecha** adelante. El promedio global da −33,9°; el robot gira a la
derecha y nunca se recentra, porque para ponerse sobre la cinta tendría que ir a un lado y
para seguirla al otro. **Un solo número no puede decir las dos cosas.**

### `near_mid`

Elige **LA** componente que representa la trayectoria —con memoria del frame anterior, que el
código actual no tiene: promedia TODO el negro, así que el zócalo pesa igual que la cinta— y
saca **dos errores separados**: `e_lat` y `e_head`.

**Resultado, inversiones de signo sobre 10 videos y 13.900 frames:**

| | actual | estados | **near_mid** | lookahead |
|---|---|---|---|---|
| total | 736 | 714 | **409** | **801** |
| vs actual | — | 97 % | **56 %** | **109 %** |

Gana en 8 de 10 videos, fuerte en `hist` (188 → 30) y `como_esta` (87 → 33).
**Pierde en `con_planner` (5 → 17) y `con_planner2` (41 → 84).**

### Los contraejemplos que impiden declararla superior

1. **En el teacher trace `near_mid` da MÁS inversiones: 18 contra 7.** Al mirarlas: 8 de 13
   tienen ambos lados por debajo de 10°, o sea **cruces de ruido alrededor del cero** con un
   rumbo típico de 15,8°. No son cambios reales de dirección — pero **el conteo crudo la
   deja peor**, y eso hay que decirlo.

2. **La magnitud del rumbo NO clasifica.** `lineal` completa un giro de 77° con **52°** de
   rumbo, más que la falla (41,7°). En una curva fuerte legítima el rumbo *tiene* que ser
   grande. Un umbral de rumbo habría bloqueado un giro bueno.

3. **`lookahead` es el PEOR de los cuatro**: 801 contra 736 del actual. La idea de perseguir
   un punto objetivo, tal como está implementada, **empeora** la estabilidad. **No está lista.**

### Conclusión

**Separar posición y rumbo sigue siendo una idea válida y bien fundada.** Esta
implementación particular **no** se considera final ni superior. Lo único demostrado es que
la señal de rumbo es **más estable**, no que produzca mejor control.

---

## 9. PRÓXIMO PASO 1 — investigar Airborne

> **NO SE INVESTIGÓ EN ESTA SESIÓN. No hay ningún conocimiento de su arquitectura acá.**
> La sesión nueva **tiene que ir al repositorio y leerlo** antes de diseñar nada.

Repositorio público: **`JamesBond6873/Airborne_Rescue_Line_2025`**

Archivos a estudiar:
- `RobotCode_Field_Version/line_cam.py`
- `RobotCode_Field_Version/robot.py`
- `RobotCode_Field_Version/config.py`

**La hipótesis a verificar** (no a asumir) es que Airborne hace algo más cercano a:

```
máscara → contornos → seleccionar UNA línea por continuidad
        → puntos de interés (TOP/LEFT/RIGHT/BOTTOM)
        → elegir objetivo → control
```

en lugar de nuestro `todos los negros → mean → atan2 global`.

**NO copiar sus parámetros.** Nuestra cámara, resolución (160×120), chasis (4 fijas de
silicona) y reglamento son distintos. Lo que se quiere entender es **la arquitectura**.

Existe `airborne_birdeye_replay.py` en el repo (465 líneas, sin trackear) que dice comparar
el ángulo actual contra un seguimiento inspirado en Airborne y contra una homografía.
**Procedencia desconocida y SIN VALIDAR.** Tratarlo como borrador: antes de usarlo hay que
verificar que reproduce el controlador real (regla de método 1).

---

## 10. PRÓXIMO PASO 2 — bird-eye / IPM

**El hardware NO se toca.** La pregunta es si por software se puede convertir la perspectiva
de la cámara inclinada en algo más parecido a mirar el piso desde arriba, con una homografía
(*inverse perspective mapping*).

Cadena a evaluar:

```
frame de cámara → rotate 180 → homografía/IPM → segmentación → seguimiento
```

**Hacer la transformación a resolución MAYOR antes de reducir a 160×120.** Rectificar después
de haber perdido resolución no recupera información.

**NO asumir que IPM es mejor.** Comparar contra la vista normal en, como mínimo:
`hist` éxito, `hist` falla, `lineal` positivo, `video_4` teacher trace, y después el resto.

**Limitación conocida:** una homografía fija falla en rampas, porque cambia el pitch. Eso se
resolvería después por software (el BNO da `pit`), no por hardware.

**Dato que motiva esta línea:** la fila más lejana que el robot usa está apenas **1,79×** más
lejos que la más cercana (43 px de ancho de cinta contra 24 px). Un seguidor normal mira de
1× a 5×. **Esa relación es una medición válida; convertirla a centímetros necesita altura,
inclinación e intrínsecos, que están en el Fusion y no en los videos.**

---

## 11. QUÉ NO DEBE HACER LA SESIÓN NUEVA AL EMPEZAR

**No empezar por:**

- modificar firmware
- tunear KP/KI/KD
- cambiar velocidad
- agregar dwell (**está refutado**)
- inventar umbrales
- implementar Airborne de memoria
- afirmar que bird-eye funciona sin validarlo

**El orden correcto:**

1. leer este handoff completo
2. revisar los archivos marcados VIGENTE
3. investigar Airborne **leyendo el repositorio**
4. reconstruir su arquitectura real
5. compararla conceptualmente con la nuestra
6. armar el banco SHADOW correspondiente, **validado** contra el `rxsteer` real
7. recién después recomendar una arquitectura

---

## 12. COMANDOS PARA REPRODUCIR LOS ANÁLISIS

Desde `software/raspberry/final_rpi/`:

```bash
python replay.py --validar
```

```bash
python shadow.py hist.avi --desde 1354 --hasta 1490 --tag falla
```

```bash
python shadow.py video_4.avi --tag manual --fps 20
```

```bash
python leyes.py --todos
```

```bash
python leyes.py hist.avi --desde 1330 --hasta 1500 --tag falla --avi
```

Firmware, desde `software/teensy/firmware/`:

```bash
pio run -e diagnostico_fix
```

En **PowerShell**, para barrer una constante (la variable queda pegada a la consola, hay que
borrarla):

```powershell
$env:PLATFORMIO_BUILD_FLAGS = "-D LINE_PIVOTE_DWELL_MS=300UL"
pio run -e diagnostico_fix -t upload
Remove-Item Env:PLATFORMIO_BUILD_FLAGS
```

---

## 13. ESTADO DEL REPOSITORIO

- **Rama:** `roboliga`
- **HEAD:** `ee264d9`
- **18 commits** en esta sesión, ninguno cambia el movimiento del robot salvo dos, y están
  marcados: `95cba6b` (el entorno por defecto pasa a `competencia_fix`) y `57f1133`
  (`CONFIRMA_MS` de 300 a 0). **Los dos hay que confirmarlos antes de la corrida.**
- **`LINE_PIVOTE_DWELL_MS = 0`** — el dwell está en el árbol pero **inerte**, y **refutado**
  como solución. No sacarlo apurado: cuesta nada y no estorba.
- Sin push. Hay derivados sin trackear (`leyes_*.csv`, `shadow_*.avi`) que están en
  `.gitignore` o se regeneran.

### Lo único que está probado FÍSICAMENTE

**Nada de lo de esta sesión.** El robot no se movió. Lo probado en pista es del 22-ago:
los dos fixes de banco (`FIX_LAZO_MOTOR`, `FIX_CURVA_CONTINUA`) medidos neutros, y las 10
corridas grabadas.

---

## PROMPT_DE_ARRANQUE_NUEVA_SESION

```
Sos parte del equipo IITA Salta (RoboCupJunior Rescue Line 2026). El robot se sale en
ciertas curvas cerradas y venimos de dos sesiones largas de analisis.

ANTES DE HACER NADA:

1. Lee COMPLETO el archivo HANDOFF_LINEA_2026-08-23_FINAL.md en la raiz del repo.
   Sus estados VIGENTE / SUPERADA / REFUTADA / NO PROBADA EN ROBOT son la FUENTE DE
   VERDAD. Si otro documento del repo lo contradice, gana el handoff.

2. Mira los archivos marcados VIGENTE, sobre todo:
     software/raspberry/final_rpi/main_rpi_2026-08-22.py   (el codigo que corrio)
     software/raspberry/final_rpi/replay.py                (banco validado)
     software/raspberry/final_rpi/shadow.py                (maquina de estados)
     software/raspberry/final_rpi/leyes.py                 (las 4 leyes)
     software/teensy/firmware/src/main.cpp                 (case 7 y case 4)

3. NO repitas ninguna hipotesis marcada REFUTADA. En particular NO propongas: el dwell
   del signo, FAR como compuerta dura, retroceder cuando no hay linea debajo, tunear
   ganancias, ni "el robot no gira lo suficiente".

REGLAS DE METODO, seccion 5 del handoff, no negociables:
 - validar todo replay contra el rxsteer real ANTES de usarlo (referencia: 84,0 % exacto,
   r = 0,9957)
 - cuando hay CSV, el movimiento se lee de la columna `rot` REAL, nunca de un modelo
 - fps real 33,3, no el 20,0 que declaran los AVI
 - distinguir paneles 640x240 de videos crudos 640x480
 - el replay es LAZO ABIERTO: nunca afirmar "esto completaria la curva"
 - medir sobre los 10 videos antes de declarar que algo generaliza
 - buscar contraejemplos activamente

LO QUE QUIERO QUE HAGAS, en este orden:

A. Investigar el repositorio publico JamesBond6873/Airborne_Rescue_Line_2025,
   especialmente RobotCode_Field_Version/line_cam.py, robot.py y config.py.
   LEELO DE VERDAD, no de memoria. Reconstrui su arquitectura real de percepcion y
   control, y compararla conceptualmente con la nuestra, que hoy es:
       black_mask -> mean(x,y) -> atan2 -> UN angle
   La hipotesis a VERIFICAR (no asumir) es que ellos hacen:
       mascara -> contornos -> seleccionar UNA linea por continuidad -> puntos de
       interes -> elegir objetivo -> control

B. Evaluar bird-eye / IPM por software, SIN tocar hardware: homografia sobre el frame
   antes de reducir a 160x120. Compararla contra la vista normal en los cuatro casos de
   control. NO asumir que es mejor.

C. Todo lo nuevo entra primero como banco SHADOW, sin conectar nada al movimiento del
   robot, y validado.

LOS CUATRO CASOS DE CONTROL, que se usan para todo:
   hist.avi 580-679      EXITO   (mismo firmware y sesion que la falla)
   hist.avi 1354-1490    FALLA
   lineal.avi 800-872    CONTROL POSITIVO (mata FAR como requisito)
   video_4.avi           TEACHER TRACE, movido a mano por la trayectoria correcta.
                         Esta en software/raspberry/final_rpi/video_4.avi
                         Es CRUDO 640x480 y a 20 fps -no 33,3-: rotate 180 +
                         resize 160x120 INTER_NEAREST, igual que hace la Pi.
                         Es el UNICO caso donde se conoce la respuesta correcta.

REGLAS DE LA CASA:
 - verifica contra el codigo, no contra la documentacion; si se contradicen gana el codigo
 - compilar no es funcionar, y flashear tampoco
 - una variable por corrida
 - poner a refutar toda conclusion antes de darla
 - espanol rioplatense
 - no escribir el fix completo por los alumnos: mostrar el patron, que el jurado los
   entrevista sobre el codigo

El robot esta disponible una vez por semana, sabados, 3 h 30. Un error de metodo no cuesta
una hora: cuesta la semana.
```
