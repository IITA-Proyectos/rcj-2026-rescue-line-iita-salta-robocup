# DRAFT — Agenda por persona · Semana W20 (2026-05-16)

> **Estado:** BORRADOR del `rcj-coach-director` para que **Enzo lo revise, ajuste y distribuya**.
> No commiteado. No es asignación oficial — Enzo es quien asigna. Si un ítem no cierra, se mueve, no se fuerza.
> Cuando Enzo lo distribuya y procese, este archivo se borra de `staging/`.

**🟢 Fase 1 — push exhaustivo · T–6 semanas a Incheon (2026-06-30, 45 días).**

## 🔴 Dos deadlines que mandan esta semana

1. **Triage issue #91 vence MAÑANA (2026-05-17).** Hay que cerrarlo sí o sí.
2. **El freeze entra el 2026-05-20.** Quedan ~3-4 días de push. Todo lo de abajo que no esté **mergeado + verificado en banco antes del 2026-05-20** pasa a tener que demostrar "ventaja desproporcionada" para entrar (Fase 2), o se va a `post-mundial`. **Esta es la última ventana barata.**

Por eso esta agenda prioriza **quick-wins de bajo riesgo que cierran en 1-2 sentadas** sobre cualquier cosa grande.

---

## Tabla resumen (para Enzo)

| Issue | Eje | Sugerido | Esfuerzo | Balde | Cierra antes 05-20? |
|---|---|---|---|---|---|
| #65 vs.read() None | confiabilidad | Lucio | ~30 min | must | Sí, fácil |
| #73 serial timeout | confiabilidad | Lucio | ~15 min | must | Sí, fácil |
| #66 ser.write() clamp | confiabilidad | Lucio | ~45 min | must | Sí |
| #64 cv2.imshow HEADLESS | performance | Lucio | ~45 min | must | Sí |
| #58 case 12 sin break | comportamiento | Lautaro | ~1 h (ojo `while`) | must | Sí, con cuidado |
| #67 pulseCount init | confiabilidad | Lautaro | ~15 min | should | Sí, fácil |
| Verificar timeouts #60/#61/#62 | confiabilidad | Lautaro | ~1 h banco | must | Verificación, no fix |
| #68 requirements pinning | confiabilidad | Benjamin | ~30 min en la Pi | must | Sí |
| PR #101 TEST_LOG (~24 pts TDP) | proceso/TDP | Enzo | merge | must | **Hoy/mañana** |
| Triage #91 | proceso | Enzo | sesión equipo | must | **Vence 05-17** |

Regla de "hecho" transversal: **PR mergeado + 1 corrida de banco que lo valide + 1 entrada en `testing/TEST_LOG.md`** (ya existe gracias al PR #101).

---

## 👤 Lucio — RPi / visión (codeowner)

Cluster de 4 quick-wins en `Main.py`. Los 4 son chicos y no tocan la lógica de visión validada — son guardas defensivas y un guard de performance.

### TEMA #65 — `vs.read()` puede devolver `None`
- **Qué:** chequear `if frame is None: continue` antes de procesar el frame en `Main.py` (~líneas 566, 578).
- **Riesgo si NO se toca:** un glitch o desconexión de cámara → `AttributeError` → crash total de visión → robot ciego → **corrida perdida**.
- **Riesgo si SE toca:** muy bajo. Es un guard de 3 líneas, no cambia el pipeline.
- **Tiempo:** ~30 min + banco.
- **Hecho:** PR mergeado + banco: desconectar la cámara en caliente durante una corrida y verificar que NO crashea (degrada o reintenta) + entrada en TEST_LOG.
- **Balde:** must-ship-incheon.

### TEMA #73 — `serial.Serial` sin timeout
- **Qué:** `serial.Serial('/dev/serial0', 115200, timeout=0.05)` en `Main.py:35`.
- **Riesgo si NO se toca:** un solo `read()` sin guard `in_waiting` cuelga todo el script → robot inerte → LoP repetido (hasta −20 pts).
- **Riesgo si SE toca:** muy bajo. 50 ms es holgado vs. el ciclo de visión (~30 ms); si no llega byte, `read()` devuelve `b''` y sigue.
- **Tiempo:** ~15 min + banco.
- **Hecho:** PR mergeado + banco: corrida de 5 min sin cuelgues de comms + entrada en TEST_LOG.
- **Balde:** must-ship-incheon.

### TEMA #66 — `ser.write()` sin clamp
- **Qué:** helper que clampee cada valor del frame a `[0,255]` antes de `ser.write()` (Main.py ~523-524 y 664-669).
- **Riesgo si NO se toca:** un `angle`/`speed` fuera de rango → `ValueError` → rompe el frame loop → robot inerte.
- **Riesgo si SE toca:** bajo. El clamp solo actúa en valores ya anómalos; no cambia el comportamiento normal.
- **Tiempo:** ~45 min + banco.
- **Hecho:** PR mergeado + banco: forzar un ángulo fuera de rango en test y verificar que clampea sin romper + entrada en TEST_LOG.
- **Balde:** must-ship-incheon.

### TEMA #64 — `cv2.imshow` sin guard HEADLESS (performance)
- **Qué:** guardar `cv2.imshow`/`cv2.waitKey` detrás de `HEADLESS = os.environ.get("DISPLAY") is None`. El patrón ya existe en `warmup.py`/`rescatemodelonos.py` — copiarlo.
- **Riesgo si NO se toca:** en la Pi headless de competencia, `imshow` desperdicia CPU y sube la latencia del frame loop → **menos FPS de visión** → peor tracking y detección de víctimas.
- **Riesgo si SE toca:** muy bajo. Reusa un patrón ya validado en otros archivos del repo.
- **Tiempo:** ~45 min + medir FPS antes/después.
- **Hecho:** PR mergeado + banco headless: medir FPS antes/después (debería subir) + número en TEST_LOG.
- **Balde:** must-ship-incheon.

---

## 👤 Lautaro — Teensy / firmware (codeowner)

### TEMA #58 — `case 12` cae al `case 14` (falta `break;`)
- **Qué:** agregar el `break;` que falta al final del `case 12` (`main.cpp:1079-1115`). **Ojo:** el issue señala que dentro del `while(digitalRead(32)==0)` hay un `break;` incondicional (línea ~1112) que hace que el while corra una sola vez — revisar si ese `break` es intencional o parte del mismo bug antes de tocar.
- **Riesgo si NO se toca:** con `green_state==3`, el flujo cae al `case 14` y dispara `runAngle(...,180)` → giro de 180° inesperado en zona → se pierde el rescate / LoP.
- **Riesgo si SE toca:** bajo-medio. Agregar `break;` es trivial, pero la interacción con el `while` interno necesita leerse con cuidado (no es "1 línea a ciegas").
- **Tiempo:** ~1 h (lectura + fix + banco de la secuencia de rescate).
- **Hecho:** PR mergeado + banco: reproducir la secuencia con `green_state==3` y verificar que NO hay giro de 180° espurio + entrada en TEST_LOG.
- **Balde:** must-ship-incheon.

### TEMA #67 — `Moto::pulseCount` sin init en constructor
- **Qué:** `pulseCount = 0;` en el constructor de `Moto` (`drivebase.cpp`).
- **Riesgo si NO se toca:** valor basura entre el arranque y el primer `reset_enconder()`. En la práctica el primer `runDistance()` lo resetea, pero es una defensa de 1 línea casi sin costo.
- **Riesgo si SE toca:** mínimo.
- **Tiempo:** ~15 min + compilar.
- **Hecho:** PR mergeado + compila + robot enciende y mueve normal en banco.
- **Balde:** should-ship-incheon.

### TEMA — Verificar estado real de los timeouts #60/#61/#62
- **Qué:** confirmar si los timeouts del commit `5bac4a5 feat(teensy): timeouts implementados` siguen vivos en el firmware actual, **o si el commit siguiente `cead75e fix(teensy): error de libreria claw.cpp` los revirtió** (sacó −181 líneas de `main.cpp`).
- **Riesgo si NO se verifica:** cerrar #60/#61/#62 creyendo que están resueltos cuando en realidad se revirtieron → robot se cuelga en competencia por la causa que creíamos arreglada.
- **Riesgo si SE verifica:** ninguno (es lectura/banco, no cambio).
- **Tiempo:** ~1 h. Si se necesita ojo experto, disparar la skill `teensy-firmware-auditor` sobre `main.cpp`.
- **Hecho:** comentario en #60/#61/#62 con el estado real (vivos / revertidos / parcial) + qué falta. Recién ahí se decide cerrarlos o no.
- **Balde:** must-ship-incheon (es el mayor riesgo oculto del momento).

---

## 👤 Benjamin — RPi + hardware (codeowner)

### TEMA #68 — `requirements.txt` sin pinning
- **Qué:** en la Pi, `pip freeze | grep -iE "opencv|numpy|pyserial|ultralytics|onnx|tflite|ai-edge"` y pinear cada dependencia a la versión de la última corrida exitosa.
- **Riesgo si NO se toca:** reinstalar una SD limpia o una Pi nueva días antes del mundial trae versiones nuevas (OpenCV/NumPy) → breaking change → robot roto sin rollback en Incheon.
- **Riesgo si SE toca:** muy bajo (pinear lo ya funcionando).
- **Tiempo:** ~30 min en la Pi.
- **Hecho:** `requirements.txt` con versiones pineadas + probar `pip install -r` en venv limpio y que `Main.py` arranca + entrada en TEST_LOG.
- **Balde:** must-ship-incheon.

### Rol de co-review (codeowner RPi)
- **Qué:** revisar los 4 PRs de Lucio (#65, #73, #66, #64) y validar en banco con hardware real (Benjamin es quien tiene mejor acceso al banco + hardware).
- **Por qué:** los fixes son chicos pero la validación en banco es lo que los hace "hechos". Sin banco no se mergea firmware/visión (regla del repo).
- **Hecho:** cada PR con check de banco y su línea en TEST_LOG.
- **Balde:** must-ship-incheon (gate de calidad de todo el cluster RPi).

---

## 👤 Enzo — coach / docs / coordinación

### TEMA — Mergear PR #101 (TEST_LOG.md)
- **Qué:** revisar y mergear PR #101. Inicializa `testing/TEST_LOG.md` (~24 pts del TDP) y es el sustrato donde se registran los "hecho" de toda esta agenda.
- **Riesgo si NO se toca:** se pierde el mayor leverage de puntaje del TDP y los demás ítems no tienen dónde registrar la validación de banco.
- **Riesgo si SE toca:** cero (es doc).
- **Tiempo:** merge hoy/mañana.
- **Hecho:** PR #101 mergeado a `main`.
- **Balde:** must — **lo primero de la semana.**

### TEMA — Cerrar triage del issue #91 (vence 2026-05-17)
- **Qué:** correr la sesión de triage de los 31 issues. Usar esta agenda como input. Decidir baldes definitivos (must/should/nice/post-mundial) y qué se congela el 2026-05-20.
- **Riesgo si NO se toca:** el deadline vence mañana; sin triage cerrado el equipo entra al freeze sin prioridades claras.
- **Tiempo:** 1 sesión de equipo (1-2 h).
- **Hecho:** #91 cerrado con el resultado documentado; issues etiquetados por balde; los que no entran → label `post-mundial`.
- **Balde:** must — **vence 2026-05-17.**

### TEMA — Distribuir esta agenda + smoke tests del PR #100 (si hay aire)
- **Qué:** bajar esta agenda ajustada a cada chico. Si queda tiempo (no es prioridad sobre lo de arriba), correr los smoke tests del PR #100 (skill `rcj-coach-director`) para que los próximos checkins queden automáticos vía `/coach-checkin`. Si no, queda para post-freeze (la skill no afecta al robot).
- **Riesgo si NO se toca:** los smoke tests pueden esperar — no tocan al robot. Distribuir la agenda sí es urgente (sin eso nadie ejecuta).
- **Tiempo:** distribución ~30 min; smoke tests ~30 min opcionales.
- **Hecho:** cada chico con su lista; PR #100 con smoke tests marcados (o nota de que quedan post-freeze).
- **Balde:** distribución = must · smoke tests = nice.

---

## Recordatorio de régimen (para alinear expectativas con los chicos)

- **Hasta 2026-05-19:** 🟢 push — si suma o protege puntos y es bajo riesgo, entra. Esta agenda es eso.
- **Desde 2026-05-20:** 🟡 freeze — NO se cambia nada salvo ventaja desproporcionada (ganancia cuantificada, riesgo P2/P1 no P0, 1-2 archivos, 5+ corridas de banco antes del 2026-06-23). Lo que no cerró antes, se evalúa con esa vara o se va a `post-mundial`.
- **2026-06-23 a 06-29:** 🔴 logística pura, cero código.

**Mensaje de coach para la reunión:** esta es la última semana barata. Después del 20 cada cambio cuesta el triple en justificación y riesgo. Cerremos fuerte estos quick-wins de confiabilidad+performance ahora, que son exactamente "mucho potencial, poco riesgo", y entremos al freeze con el robot sólido.
