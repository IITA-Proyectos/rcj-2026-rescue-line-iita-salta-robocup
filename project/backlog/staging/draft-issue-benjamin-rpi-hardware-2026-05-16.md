## Cluster RPi + hardware — para Benjamin (codeowner RPi/hardware, dueño del banco)

**Fase:** 🟢 Fase 1 — push exhaustivo · **T–6 semanas a Incheon** · freeze el 2026-05-20.

Benjamin: este issue junta **lo previo abierto que te toca** + **los hallazgos nuevos de RPi/visión** de la auditoría 2026-05-16. Sos codeowner RPi+hardware y el que tiene mejor acceso al banco, así que además de tus temas propios sos el **gate de validación en banco** de todo el cluster RPi (los fixes de Lucio se mergean con tu check de banco + entrada en `testing/TEST_LOG.md`).

Formato de cada tema: riesgo-si-NO / riesgo-si-SÍ / tiempo / criterio de "hecho".

---

### A) Hallazgos PREVIOS ya con issue abierto (referencia — NO reabrir, trabajarlos desde su issue)

Estos ya están como issue; los listo para que tengas el cluster completo en un solo lugar:

- **#65** `vs.read()` puede devolver `None` → crash visión con cámara desconectada. Fix ~3 líneas. **must.**
- **#73** `serial.Serial` sin timeout → deadlock. Fix 1 parámetro. **must.**
- **#66** `ser.write()` sin clamp → `ValueError` rompe frame loop. Fix helper ~5 líneas. **must.**
- **#64** `cv2.imshow` sin guard HEADLESS → CPU desperdiciado, menos FPS. Fix ~4 líneas (patrón ya en `warmup.py`). **must.**
- **#68** `requirements.txt` sin pinning → reinstalar SD limpia rompe todo pre-mundial. Fix `pip freeze` + pinear. **must** *(ya estabas asignado en #68).*

Tu rol acá: ejecutar #68 vos, y **co-review + banco** de #65/#66/#73/#64 (los toca Lucio).

---

### B) Hallazgos NUEVOS de RPi/visión (auditoría 2026-05-16 — para abrir/triage)

#### TEMA V-A — Frame race condition en `camthreader`
- **Archivo:** `software/raspberry/final_rpi/camthreader.py:32-36`
- **Qué:** `self.grabbed, self.frame = self.stream.read()` sin lock; el main lee `self.frame` concurrente → frames stale o duplicados (no son `None`, el guard de #65 no los detecta).
- **Riesgo si NO:** decisiones de ángulo sobre frame con 2-3 frames de latencia extra → en curva cerrada el ángulo es de la recta anterior → se sale de línea / se pasa rampa.
- **Riesgo si SÍ:** bajo. `threading.Lock()` en `__init__`, adquirir en `update()` y `read()`. ~6 líneas, no cambia interfaz.
- **Tiempo:** ~20 min + banco.
- **Hecho:** PR + banco: `print(id(frame))` 5 s, sin lock hay IDs repetidos; con lock no. Entrada en TEST_LOG.
- **Balde:** must.

#### TEMA V-B — `enhance()` hace doble/triple conversión BGR↔HSV por frame
- **Archivo:** `software/raspberry/final_rpi/Main.py:188-248` (`agcwd`, `anti_flash_preprocess`, `enhance`)
- **Qué:** 2-3 conversiones de color completas por frame sobre 256×256 (anti-flash HSV + agcwd HSV + BGR2RGB del modelo). ~3-7 ms/frame desperdiciados; TFLite ya es el cuello.
- **Riesgo si NO:** FPS de inferencia limitado por conversiones evitables, no por el modelo. `frame_q` se llena antes, capture_thread bloquea.
- **Riesgo si SÍ:** bajo. Fusionar a una sola pasada HSV (flash mask + LUT sobre canal V, una conversión). ~30 líneas, lógica equivalente.
- **Tiempo:** ~45 min + banco (verificar que los colores detectados no cambian).
- **Hecho:** `perf_counter` alrededor de `enhance()` baja de ~8 ms a ~4-5 ms en la Pi; FPS +15-25%. Número en TEST_LOG.
- **Balde:** must (mayor potencial de performance absoluto).

#### TEMA V-C — `frame_q` (maxsize=2) bloquea `capture_thread` bajo throttling térmico
- **Archivo:** `software/raspberry/final_rpi/Main.py:314,449`
- **Qué:** `frame_q.put(frame)` sin `nowait`/timeout → si la inferencia tiene un spike (calor de arena, throttling), la cola se llena en 2 frames y el capturador se congela; al liberar procesa 2 frames viejos.
- **Riesgo si NO:** en competencia con Pi caliente, comandos basados en frames de 200-400 ms de antigüedad justo cerca de la zona de rescate (tracking fino crítico).
- **Riesgo si SÍ:** bajo-medio. Patrón drop-oldest (`put_nowait` + `get_nowait` en `except Full`). ~5 líneas. El `CentroidTracker max_lost=8` ya tolera gaps.
- **Tiempo:** ~15 min + banco.
- **Hecho:** inyectar `sleep(0.15)` en infer_thread y verificar que el main procesa el frame más fresco (no 2 stale). Entrada en TEST_LOG.
- **Balde:** must (lo que el auditor marcó como más importante de visión).

#### TEMA V-D — `agcwd()` arma el LUT con list-comprehension Python (256 iter/frame)
- **Archivo:** `software/raspberry/final_rpi/Main.py:198-199`
- **Qué:** LUT de 256 con `[int(255*(i/255)**(1-w_cdf[i])) for i in range(256)]` en Python puro, cada frame. ~0.5-1 ms/frame evitable.
- **Riesgo si NO:** CPU desperdiciada en hot path; suma al V-B.
- **Riesgo si SÍ:** mínimo. Vectorizar con `np.power(np.arange(256)/255, 1-w_cdf)...`. 1 línea, semántica idéntica (±1 LSB irrelevante).
- **Tiempo:** ~10 min + banco.
- **Hecho:** `timeit` 1000 iter, 3-4× speedup. Entrada en TEST_LOG.
- **Balde:** must (quick win casi sin riesgo).

#### TEMA V-E — `calibration.py` desincroniza los frames mostrados
- **Archivo:** `software/raspberry/final_rpi/calibration.py:29-37`
- **Qué:** 2 `vs.read()` por iteración (el primero se descarta); LAB es del frame N y RGB del N+1. `namedWindow` dentro del loop. El operador calibra color sobre frames distintos.
- **Riesgo si NO:** umbrales de color mal calibrados → falsos +/− de verde/zona → puntos perdidos en competencia.
- **Riesgo si SÍ:** muy bajo. Reordenar el `read()` y sacar `namedWindow` del loop. ~3 líneas.
- **Tiempo:** ~10 min + banco.
- **Hecho:** apuntar a objeto en movimiento lento; ventanas RGB/LAB sincronizadas. Entrada en TEST_LOG.
- **Balde:** must (afecta directamente la calidad de calibración pre-mundial — tu dominio de banco).

#### TEMA V-F — `print(area)` en el hot path del loop de línea
- **Archivo:** `software/raspberry/final_rpi/Main.py:799`
- **Qué:** `print(area)` por cada contorno de plata, en cada frame del estado `linea`. Con piso reflectivo (5-10 contornos de ruido) → hasta ~20 ms I/O bloqueante/frame.
- **Riesgo si NO:** FPS del loop de línea cae justo en piso brillante de estadio (de ~40 Hz a ~20 Hz en el peor caso). Ensucia el journal y dificulta debug real.
- **Riesgo si SÍ:** mínimo. Borrar o poner detrás de flag debug. La telemetría cada 5 s ya cubre.
- **Tiempo:** ~5 min + banco.
- **Hecho:** medir FPS con piso brillante con/sin el print; recuperación 2-8 FPS. Entrada en TEST_LOG.
- **Balde:** must (mejor ratio impacto/esfuerzo de todo el cluster).

---

### Tu prioridad sugerida esta semana (antes del freeze 2026-05-20)

1. **#68** (tuyo) — pinear `requirements.txt` desde la Pi de la última corrida buena.
2. **Banco + co-review** de los fixes de Lucio (#65/#66/#73/#64 + V-A/V-D/V-E/V-F) — sos el gate de validación.
3. **V-B y V-C** — los de mayor potencial de performance; coordinar con Lucio quién los toma, vos validás en banco con medición de FPS antes/después.

Regla de "hecho" transversal: **PR mergeado + 1 corrida de banco que lo valide + 1 línea en `testing/TEST_LOG.md`** (existe gracias al PR #101).

*Auditoría asistida por Claude Code bajo supervisión de @gviollaz. Cluster RPi/hardware extraído del consolidado (ver issue gemelo asignado a @enzzo19 para el panorama de los 3 subsistemas).*
