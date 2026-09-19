# Onboarding para una IA externa

**Corte: 2026-08-24 · rama `collab/nuevo-code` · competencia en noviembre 2026.**

Si sos un modelo al que le pasaron este repo (Gemini, ChatGPT, otro Claude),
**leé este archivo entero antes que cualquier otro**. El repo tiene 138 `.md` y
al menos cuatro se declaran, cada uno, «la fuente de verdad única». Todos son de
mayo o de la mañana del 23 de agosto. Ninguno está al día.

---

## 1. La restricción que ordena todo

**Quedan como máximo DOS SÁBADOS con el robot.** No hay tiempo de robot entre
medio. La pregunta que decide la prioridad de cualquier tarea es:

> ¿Descubrir esto recién el sábado podría costarnos una sesión física?

Si sí, es P0. Si no, baja.

**El hardware NO se puede cambiar.** Cámara fija, baja y casi horizontal; 4
ruedas fijas de silicona. Cualquier propuesta que empiece con «mover la cámara»
o «cambiar las ruedas» está fuera de alcance, por más que la literatura diga que
es lo correcto (y lo dice: el campeón mundial 2024 la monta mirando hacia
abajo). Se compensa en software o no se compensa.

---

## 2. Tu rol, y lo que NO tenés que hacer

El cuello de botella **no es falta de ideas ni de investigación**. Se refutaron
siete hipótesis de percepción seguidas. El cuello es que **la Raspberry está
apagada y no existe un runner de lazo cerrado**: nada de lo que se probó offline
tiene validación física.

Un modelo más generando hipótesis empeora eso. Tus dos trabajos útiles son:

| | |
|---|---|
| **A** | **Coherencia sobre el repo entero.** Sos el único que puede leerlo completo de una. Buscá documentos que se contradigan y afirmaciones ya refutadas que sigan escritas como verdad. Ver §6 |
| **B** | **Investigación de literatura**, siempre atada a una pregunta concreta y falsable |

**Lo que NO:** proponer hipótesis nuevas de percepción. Si encontrás una, anotala
como pregunta para después del sábado, no como tarea.

Y una advertencia honesta: **la respuesta no está en la web.** Ya se hizo la
búsqueda y dio mucho (§5). Lo que falta es una medición física sobre este robot.
Ninguna cantidad de investigación la produce.

---

## 3. El sistema, en un párrafo

Raspberry Pi 4B hace visión y manda por UART a 115200 la trama
`[255, speed, 254, angle, 253, green, 252, silver]`. Un Teensy 4.1 controla
motores con encoders, ToF VL53L0X, ultrasonidos, IMU BNO055 y la pinza. La Pi
decide, el Teensy ejecuta.

**La candidata de visión es `software/raspberry/final_rpi/arquitectura_minima.py :: SinBranch`**
= `NuevoCodeV2` + `SpatialTargetGuard`, sin el branch guard de V3. Pipeline:
máscara de negro → componente conectada → `skeletonize` → grafo → Dijkstra →
target a **70 px geodésicos** → cap de continuidad → low projection → guard
espacial → `steer = -90·(x − centro)/(ancho/2)`.

**Nunca corrió en lazo cerrado.** Todo lo que se sabe de ella sale de replay
sobre 10 videos autónomos grabados (a 100/3 = 33,333 fps reales, **no** los 20
que dice el header) más un video «teacher» a 20 fps.

---

## 4. Hipótesis muertas. No las repropongas.

Cada una consumió días. Están refutadas con datos y con controles.

| | qué era | por qué cayó |
|---|---|---|
| H5 | «LOOKAHEAD=70 es el origen» | refutada |
| H6 | podar el esqueleto por longitud | distribución continua, sin umbral defendible |
| H6b | las ramas son ruido de máscara | persisten en multiescala: son reales |
| H8 | subir el peso de continuidad | no es la palanca |
| H9 | selección de verso **global** | el diagnóstico se sostiene; la política degradaba las 5 métricas |
| H9-GATE | recuperar por el gate vertical | pasa los 4 controles pero es **globalmente neutra**. El gate explica sólo el 4,4 % |
| H10 | política de rama de mayor alcance | inversiones **suben** en los 5 umbrales preregistrados |
| dwell | dwell de pivote como fix central | 74 inversiones dentro del pivote en 6 corridas |
| bird-eye / IPM | como arquitectura principal | auditado y descartado |
| Airborne | copiar su morfología / su replay | homografía con puntos inventados; fabrica 19 pérdidas falsas de 137 |

**Tampoco:** hold del target, coast ciego, selección de verso global, path/tangente
orientada global.

---

## 5. Lo que se descubrió en agosto y NO está en ningún otro `.md`

Esto vive sólo en mensajes de commit y en tres skills. Es lo más importante del
repo y lo más fácil de perderse.

### 5.1 El lazo del Teensy corría a 30 Hz por una espera activa

El `while` de seguimiento de línea llamaba `leer_tof()` en cada vuelta, y el
VL53L0X en modo continuo **hace espera activa** hasta tener muestra (~33 ms; nunca
se llamó `setMeasurementTimingBudget`). Medido sobre 7.673 períodos en 6
corridas: **p50 = 30 ms, con un segundo modo en 65 ms**.

Consecuencia: la Pi manda a 66–86 Hz y **el comando cambia a 8,6–20,6 Hz. Tres de
cada cuatro tramas de visión se descartan.** El retardo `rot`→`gz` de 65–70 ms
son exactamente dos períodos de lazo.

Y los ToF **no se usaban ahí**: sólo los consumen el seguimiento de pared (que
los relee) y la telemetría.

→ Fix aplicado en commit `4c1d456`, detrás de
`kFixLazoLineaSensoresBloqueantes`. **NO PROBADO EN BANCO.** Falsador escrito:
el p50 del período debe bajar de 30 ms a < 10 y el lag de 65–70 ms a ≤ 20. Si el
lag no se mueve, la hipótesis muere.

### 5.2 El `LOOKAHEAD` no es una distancia física

70 px **geodésicos de imagen**. Con la cámara casi horizontal, la escala
píxel→suelo varía hasta 300× dentro del cuadro. Medido sobre 13.036 frames, el
**arco de suelo real** hasta el target va de **0,230 (p05) a 1,370 (p95): 5,9×**.

Pure pursuit es un proporcional con ganancia `2/ℓd²` (Snider 2009), así que
**la ganancia del lazo varía 35×**.

> Números viejos que vas a encontrar escritos y que están **superados**: 1,79× y
> 2,07× (`CURRENT_TRUTH`, `HANDOFF_LINEA`) medían otra cosa; 2,3× medía la
> profundidad, no el arco.

### 5.3 No hay watchdog en el Teensy

`grep 'WDT\|watchdog' src/main.cpp` = 0 resultados. `g_last_rx_ms` se calcula y
sólo se usa en telemetría. En una corrida grabada, **49 % de las muestras con más
de 1 s sin trama nueva, ventana continua de 17,1 s, máximo 27 s**. Si la Pi se
cuelga, el Teensy sigue ejecutando la última orden indefinidamente.

### 5.4 El 94 % de cancelación de giro ya tiene reparto

**76–87 % de las muestras tienen `sign(rot) == sign(gz)`: el robot hace lo que le
piden.** Sólo 10–27 % del giro bruto va contra el comando. La cancelación es
**comandada** — la visión da órdenes que se dan vuelta.

Y el techo de 39 °/s **no es físico**: es `LINE_PIVOT_SPEED = 20 × ganancia
0,55`. La ganancia de giro es lineal y sin saturar entre 40 y 96 rpm.

### 5.5 El lazo mezcla posición y rumbo

`steer` se mueve por dos causas físicamente distintas. Regresión sobre 13.036
frames: **47,8 % posición / 52,2 % rumbo, R² = 0,82**, por el mismo número y con
**una sola ganancia**. Y la ley de steer nunca ve la velocidad.

### 5.6 En el 4,7 % de los frames el target no está sobre el camino planificado

Los guards mueven el punto sin mirar el plan. Máximo: **140 px** en una imagen de
160 de ancho.

### 5.7 MONO: lo único que bajó las inversiones

`pursuit.py` implementa la búsqueda **monótona hacia adelante** de Coulter 1992,
que es el arreglo publicado para el problema que H10 diagnosticó. Resultado:
**inversiones −26 de 392 (−6,6 %)**, controles intactos. **Pero sube huecos +6 y
saltos +7, así que no pasa el criterio preregistrado.** Candidata fuerte, no
aprobada.

---

## 6. Documentos que NO deberías creer

Todos fueron correctos alguna vez. Ninguno tiene banner.

| documento | qué afirma | qué lo mata |
|---|---|---|
| `docs/es/2026-07-02-auditoria-independiente-rampa-plateado.md` | «el serial SÍ se drena, `steer` está fresco; **no** hace falta tocar el serial» | §5.1. La premisa es correcta, la conclusión falsa: el mismo `leer_tof()` que invoca como prueba **es** la espera activa |
| `ROBOT_TEST_PLAN.md` | el barrido de dwell es «LA PRUEBA DEL DÍA» | refutado 1 h 06 min después de escribirse |
| `OVERNIGHT_ANALYSIS_2026-08-23.md:238` | «H-4 — **LA CAUSA**» | su propio `:681` («H-8 — ERROR MÍO»), 440 líneas más abajo |
| `README.md` | ruedas «omniwheels»; `Main.py` es el código de competencia | las omni se eliminaron y **ése es el origen del problema**; `Main.py` es una versión vieja |
| `INFORME-2026-08-22.md:32-33` | videos a 20 fps; submuestreo «EXACTO» | son 33,3 fps; `[1::2,1::2]` da 84,0 % y `[::2,::2]` 65,2 % |
| `CLAUDE.md:57` + 9 archivos más | régimen de fases con fechas de junio, «mundial en Incheon 30-jun» | la competencia es en **noviembre** |
| `AUDIT-ACTION-PLAN.md` | lista de bugs vigente | archivado, pero 6 archivos lo siguen mandando leer |
| `docs/es/ESTADO-ACTUAL-2026-05-31.md` | «FUENTE DE VERDAD ÚNICA» | es de mayo |
| `docs/es/librerias-firmware.md`, `yolo-raspberry.md` | stack ONNX + `ultralytics` | corre **TFLite** |

**El patrón:** este repo no tiene documentos falsos por descuido. Tiene
documentos que fueron ciertos entre una hora y tres meses, escritos con banners
de autoridad que envejecieron peor que el contenido.

`TRAZAR_AUDITORIA.md` §15 es el único que lo resuelve bien: retracta punto por
punto, dice qué se retira y qué sobrevive, y deja el número que lo mata. **Ése es
el formato a imitar.**

---

## 7. Cosas que siguen siendo ciertas — no las descartes de más

- **No hay watchdog** en el Teensy.
- **El detector de verde no disparó ni una vez en 417 s de video.** P0 abierto.
- `testing/TEST_LOG.md` no se toca desde el **2026-06-07**, y `CLAUDE.md` regla 3
  exige entrada ahí antes de mergear firmware.
- La candidata sigue siendo `SinBranch`. Nada la reemplazó.
- `docs/es/2026-07-03-investigacion-ruedas-alto-grip.md` — física de compuestos,
  no caduca.

---

## 8. Reglas de método que no se negocian

1. **El replay es lazo abierto.** Los videos contienen el futuro que generó el
   controlador que realmente manejó. No infieras trayectoria física de un replay.
2. **Falsador escrito antes de medir**, en números.
3. **Umbrales preregistrados en banda**, y sólo hay conclusión si hay plateau.
4. **Controles positivos intactos:** `hist_exito` 100/100 y `lineal_positivo`
   73/73 conservando el **+87°**, que es correcto porque esa curva se completó.
   Nunca propongas «limitar la magnitud del steer».
5. **Diagnóstico confirmado ≠ política adoptada.** Pasó dos veces (H9, H10).
6. **Sanidad física antes de publicar.** Ya se estuvo a punto de publicar 900 °/s
   en un robot que gira a 39.
7. **No inventes resultados físicos.** Si no está medido, decilo.
8. **Español.** Es el idioma fuente del repo.

Las tres skills en `.claude/skills/` desarrollan esto:
`seguimiento-de-trayectoria`, `geometria-camara-suelo`, `experimento-falsable`.
La última documenta **cuatro errores estadísticos reales** que ya se cometieron.

---

## 9. Por dónde entrar al código

| | |
|---|---|
| la candidata | `software/raspberry/final_rpi/arquitectura_minima.py`, `nuevo_code_v2.py` |
| cómo se mide | `ab_v2_v3_v4.py` — las cinco métricas y los controles |
| los dos P0 de visión | `pursuit.py` |
| el plan del sábado | `software/raspberry/final_rpi/PROTOCOLO_SABADO.md` |
| el lazo real del Teensy | `software/teensy/firmware/src/main.cpp`, `priority_fix_flags.h` |
| historia reciente | `git log -20 --format=%B` — es la **única** fuente de H9/H10/MONO/el fix del lazo |

Para empaquetar todo esto en un archivo subible:

```bash
python3 tools/empaquetar_contexto.py
```

---

*Este documento se actualiza cuando cambia el estado, no cuando cambia el
calendario. Si lo que leés acá contradice a otro `.md` del repo, y el otro es
anterior al 2026-08-24, gana éste — pero decilo en voz alta en vez de asumirlo.*
