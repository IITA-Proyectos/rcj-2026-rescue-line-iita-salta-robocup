# Verdad vigente — 2026-08-23, cierre

_Consolidación. **No hay hipótesis nuevas acá**: sólo se clasifica lo que ya se midió._

---

## ORDEN DE AUTORIDAD

Cuando dos documentos se contradigan, **gana el de abajo**:

| documento | estado |
|---|---|
| `INFORME-2026-08-22.md` | **histórico.** Varias conclusiones corregidas al día siguiente |
| `ANALISIS-2026-08-23.md` | **parcialmente superado** por el trabajo nocturno |
| `OVERNIGHT_ANALYSIS_2026-08-23.md` | diario vivo. **Adentro, H-8/H-9/H-10 mandan sobre H-4/H-6 y sobre "ESTADO ACTUAL"** |
| **este archivo** | **manda sobre todos** |

**Por qué importa:** el diario tiene conclusiones muertas al lado de vivas. Después de una
compactación de contexto se puede recuperar una sección vieja y construir encima. Ya pasó.

---

## VIGENTE

### Método

- **Cuando existe CSV, el movimiento se lee de la columna `rot` REAL. Nunca de un modelo.**
  El modelo coincide 92 % en el estado pero cuenta 36 sueltas contra 55 reales (−35 %).
- **`ram` (columna 11) es `g_line_branch`** (`main.cpp:717`), **no** un indicador de pivote.
  Con `|rot| ≥ 0,95` tienen `ram != 3` el 58,7 % y el 73,6 % según la corrida.
  Para el pivote manda `rot`; `ram >= 0` sólo sirve para filtrar linetrack.
- **Unidades:** `rxsteer` ×1000; `yaw`, `pit`, `gx`, `gy`, `gz` ×10.
- **Los videos son de ~33 fps**, no 20. El `20.0` del `VideoWriter` es metadato fijo.
- **De 60 pares video×CSV posibles, existe UNO**: `hist.avi` ↔ `pivote_con_histeresis`.

### Física y actuación

- **295 episodios de pivote, p50 210 ms y 6,0 grados reales. 1 % llega a 45°.**
- En la falla 1354-1490: **147,6° brutos, −8,8° netos. Se cancela el 94 %.**
- **`rot` ordenado ↔ `gz` medido: r = 0,927 a 60 ms.** La mecánica obedece fielmente.
- **La tasa de giro satura:** `ls` 0-22 → 19,6 °/s; 32-42 → 39,3; 42-60 → 39,2.
  Subir de 20 a 35 rpm duplica; de 35 a 50 no compra nada.
- **Autoridad de sobra:** 1.184 a 2.174 grados por minuto en bruto, neto ±20.

### Visión

- **`min_line_size = 1` sobre una máscara 0/255**: la rama de pérdida exige CERO píxeles
  negros. En `hist` detecta el **13,5 %** de las pérdidas reales (recall).
- **El detector por componente conexa da 98,4-100 % de recall con 0,9-1,8 % de falsos
  positivos.** Ya está implementado y **no cambia el byte que se manda** (`b67096f`).
- **La señal MID**, sobre 285 eventos (68 malos / 217 buenos):
  *"no llega a la banda media en ninguno de los 5 primeros frames del giro"*
  → **captura 49 %, precisión 69 %, bloquea 7 % de los buenos.**
- **La captura de MID NO generaliza uniforme:** de 0 % (`con_planner`) a 89 % (`hist`).
  Tres videos aportan 22 de los 33 aciertos. **El bloqueo sí es robusto: 0-18 % en todos.**
- **En los 10 videos disponibles, el estado LOW nunca confundió una T**: 0 de 672 frames LOW
  tienen área de intersección (mediana 79 px contra 3216 de los HIGH).
  *(Enunciado corregido: es evidencia fuerte sobre el material disponible, **no** una
  imposibilidad geométrica. Una T parcialmente fuera del ROI o una segmentación rota podrían
  dar otra cosa.)*
- **El error de rumbo vale ~24 px de forma permanente** y el controlador no lo mide.
  Medido dos veces por caminos independientes (24 px y 28,6 px).
- **La cámara casi no tiene profundidad:** la fila más lejana del ROI está apenas **1,79×**
  más lejos que la más cercana (43 px de cinta contra 24 px).

### Firmware

- **El binario de competencia no compilaba el `case 7` nuevo.** `default_envs` era
  `teensy_hid_device` y `FIX_CURVA_CONTINUA` vale 0 por defecto. **Corregido** (`95cba6b`).
- **`LINE_PIVOTE_CONFIRMA_MS = 300` es inalcanzable:** las rachas de alineación duran 50-75 ms
  y sólo el 1,2-7,7 % llega a 300. Con ese valor el pivote sale por el tope de 2500 ms
  girando en el lugar. **Puesto en 0**, que es lo que corrió y lo que el replay valida.
- **La histéresis mantiene la MAGNITUD del pivote pero no la DIRECCIÓN:** el signo se
  recalcula desde `steerCmd` en cada trama, así que se puede invertir sin salir del pivote.

### P0 abierto, sin relación con las curvas

- **El detector de verde no disparó ni una vez en 417 s de video.** `green_mask` nunca pasó
  de 6 píxeles contra un umbral de 510. **Sin resolver.**

---

## SUPERADA

| conclusión | qué la superó |
|---|---|
| **428 ms / 11,1 grados por pivote** | 210 ms / 6,0 con `rot` real (H-8) |
| **224 sueltas, 88 % por alineación** | conteo del modelo, −35 % contra la telemetría |
| **El frame 1374 es una suelta** | el CSV dice `rot = −1,000`: seguía enganchado |
| **`forward_path_valid` con la banda LEJANA** | el contraejemplo `lineal` 800-872 (H-10) |
| **"la autoridad de giro casi se duplicó"** | era `LINE_PIVOT_SPEED` subiendo; la tasa satura |
| **El criterio PASS de "190 ms → 300 ms"** | esa población se midió sin latch |

*Nota: los **0,190 s / 4,9 grados** de la primera medición **NO** están superados — coinciden
con los 210 ms / 6,0 de la telemetría. Lo superado fue mi "corrección" a 428 ms.*

---

## REFUTADA

| hipótesis | el número que la mata |
|---|---|
| **El dwell del signo como fix central** | **74 inversiones dentro del pivote en 6 corridas** (0,16/s), y **39 son de la corrida contaminada**. En las limpias: 0, 14, 8, 6, 7 |
| **"No llega a LEJOS" como compuerta dura** | `lineal` 800-872 completa ~77° con `far` en 42,5 % |
| **El desvío lateral predice la pérdida** | 12,0 px antes de perder contra **12,0 px** de control |
| **"La pérdida sigue a una suelta de pivote"** | 61 % contra un control de **64-81 %** |
| **Techo de par / motores al límite** | PWM mediano 53-115 sobre 255; **0,00 % ≥250** |
| **Patinaje variable de las ruedas** | la constante grados/s por rpm es **1,15-1,29** en las 6 |
| **La ISR del registrador roba flancos** | contadores `volatile`; `dt` del ISR = 5000 µs de mediana **y de máximo** |
| **El umbral de negro es muy exigente** | aflojarlo a 180 recupera **8,1 %** de los frames perdidos |
| **El ROI está muy abajo** | el **93 %** del negro de arriba es el salón |
| **Bajar la velocidad para doblar mejor** | la velocidad se cancela en cm/grado |
| **`CONFIRMA_MS` como palanca** | subirlo **acorta** los tramos: 420 → 360 ms |
| **El "hallazgo de las 22:01"** | `como_esta` se grabó en otro tramo: 0,3-1,4 % de vistas compartidas contra 44-66 % |
| **PID ciego al signo** | ninguna rueda colapsó en 24 segmentos |

---

## NO PROBADA — son hipótesis, no resultados

1. **Que actuar sobre MID mejore la corrida.** El robot **nunca** dejó de comprometerse por
   falta de evidencia: no hay contrafáctico en ningún archivo. Todo es observacional.
2. **Que el dwell sirva.** Compilado, nunca flasheado.
3. **Si el `T_min` correcto son 250 o 400 ms.**
4. **Si los ~39 °/s se sostienen en el piso de la sede.**
5. **Cuántos grados pide realmente la curva que falla.** No hay mapa de pista.
6. **Que la geometría de cámara sea la causa raíz.** El 1,79× es una medición válida de
   **relación de distancias**; convertirlo a centímetros necesita altura, inclinación e
   intrínsecos, que están en el Fusion y no en los videos.
7. **Que `forward_path_valid` sea un mecanismo causal.** Es correlación con control.
8. **Si `FIX_LAZO_MOTOR` se porta bien en verde, plateado y rescate.** Ninguna corrida grabada
   llegó a evacuación.

---

## LA EXPLICACIÓN QUE SOBREVIVIÓ A TODO

> **La Raspberry produce un `angle` incluso cuando la geometría visible ya no justifica
> confiar en él. La Teensy trata ese número con la misma autoridad que uno obtenido con una
> trayectoria claramente conectada. El robot obedece esas órdenes contradictorias y gasta
> gran parte de su capacidad de giro cancelándose.**

Explica a la vez: que según cómo se lo coloque a veces funcione; que los motores sí giren;
que acumule 147° y termine igual; que el signo se contradiga; que el dwell ayude poco; y que
los giros buenos tengan mucha más estructura conectada que los malos.

**No explica el 51 % de los fallos que MID no captura.** Eso sigue abierto.

---

## EL PRÓXIMO TEST FÍSICO — dos etapas, no diez parámetros

### Etapa 1 — OBSERVAR (sin darle autoridad al robot)

Loguear por frame, **sin cambiar una sola orden**:

```
rxf, angle, near, mid, far, area, wmax, estado, rot, rxspeed
estado ∈ { PATH_HIGH, PATH_MID, PATH_LOW, PATH_LOST }
```

**La pregunta que resuelve, y es la única que importa ahora:**

| lo que se ve en el log | qué significa |
|---|---|
| `HIGH HIGH MID LOW LOW LOW → se sale` | el estado es **estable y anticipa**. Se conecta a la maniobra |
| `HIGH LOW HIGH LOW MID LOW…` | es **parpadeo**. NO se conecta nada |

Cuesta una corrida y no puede romper nada.

### Etapa 2 — ACTUAR, sólo si la etapa 1 valida

El patrón, que **no** es el dwell viejo:

- el dwell decía *"durante X ms no cambies de signo"*
- esto diría *"mientras la evidencia sea mala, una medida mala no tiene permiso para
  contradecir la última medida buena"*

```
último sentido confiable = el decidido con estado HIGH o MID
    LOW      -> mantener ese sentido, avance nulo o muy reducido, ventana corta
    vuelve a MID/HIGH -> control normal
    pasa a LOST       -> recuperación de línea (el case 4 ya existe)
    timeout           -> abortar
```

**Y no esperar que arregle todo: MID captura el 49 % de los fallos.** Aunque resolviera el
100 % de lo que detecta, queda la otra mitad.

### Las capas, en orden

| capa | qué | estado |
|---|---|---|
| 1 | pérdida de línea explícita | **implementada**, sin actuar (`b67096f`) |
| 2 | confianza geométrica (HIGH/MID/LOW/LOST) | **a instrumentar** |
| 3 | estimación real de rumbo | pendiente. El error de rumbo es ~24 px permanente y nadie lo mide |

### Lo que NO va

`green_state = 4` encendido, `CONFIRMA_MS = 300`, el objetivo extensible en grados, el
planner, una novena ley de control, y **tunear ganancias**.
