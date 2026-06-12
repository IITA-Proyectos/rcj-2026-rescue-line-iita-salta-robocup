# Auditoría de desempeño — Benjamin Villagran (@benjaminvillagran)

> **Dominio:** Raspberry Pi (visión) · Hardware / electrónica / documentación · Banco de pruebas
> **Auditoría integral 2026-05-18** · Repo `rcj-2026-rescue-line-iita-salta-robocup` · Branch analizada: `feature/initialize-testing-log` (post-merge PR #101 → main)
> **Fecha del informe:** 2026-05-31 · Mundial: Incheon, 2026-06-30 → 07-06
> **Metodología:** minería git/gh (`Benjamin`, `Villagran`, `benjaminvillagran`, e identidad secundaria `Benjamin Villagran <148703811+...>`), lectura completa de docs de hardware/testing, revisión de calidad de código en rama mergeada y en rama abierta PR #129.

---

## 0. Resumen ejecutivo (TL;DR)

Benjamin es, después del coach, **el contribuidor más activo y de mayor amplitud del repo**: 28 commits únicos cruzando los cuatro subsistemas (visión RPi, firmware Teensy, documentación de hardware y comms). Su producto estrella, `hardware/cambios_de_hardware.md`, es **documentación de ingeniería de calidad profesional** — cita reglamento 2026, evalúa opciones con pros/contras y código de ejemplo. Su trabajo de fiabilidad (timeouts, validación de payload serial, recuperación de cámara, `systemd`) es **técnicamente competente y honesto** en su documentación.

El problema **no es la calidad ni la cantidad — es la entrega y el proceso**. Tres patrones lo definen y a la vez lo limitan:

1. **Su mejor trabajo está varado en una rama sin mergear y sin review.** PR #129 (`Bugs prioritarios`, +5707/-506, 39 archivos, "Closes #46…#126") tiene **0 reviews** y sigue OPEN. Casi todos sus fixes P0/P1 de fiabilidad (timeouts en `runDistance`/`runAngle`, validación serial, handshake de boot) **no están en `main`**: están solo ahí.
2. **El TEST_LOG que la rúbrica considera de mayor impacto (~24 pts del TDP, issue #93) está vacío en la rama auditada.** Benjamin lo llenó con tests reales (T-001, T-002), pero **otra vez, solo en PR #129 sin mergear**. Y los datos son de una sola corrida, con varios campos "no registrado".
3. **El 2026-05-10 mergeó timeouts a `main` y ~1 h después los revirtió** (`cead75e`, "error de libreria claw.cpp", −181 líneas), dejando `main` sin esos fixes hasta hoy.

**Veredicto:** alto potencial técnico y la mejor pluma de documentación del equipo, **frenado por disciplina de entrega**. Si PR #129 no se parte, se revisa y se mergea antes del mundial, gran parte de su esfuerzo de fiabilidad **no llega a la pista**.

---

## 1. Datos duros (minería git/gh)

### 1.1 Volumen de commits

| Métrica | Valor |
|---|---|
| Commits únicos (todas las ramas, ambas identidades) | **28** |
| Commits en `main` | **15** |
| Identidad primaria `benjaminvillagran <villagranbenjamin52@gmail.com>` | 23 |
| Identidad secundaria `Benjamin Villagran <148703811+...@users.noreply>` | 5 |
| Posición en el ranking del repo | **#2** (coach gviollaz 26+ commits; Benjamin 23; resto del equipo ≤5 c/u) |

> **Nota de identidad:** commitea bajo dos autores git distintos (cuenta web vs. cliente local). No afecta atribución pero ensucia `git shortlog`. Convendría unificar `user.email` en su entorno. **No** existe ningún "Lautaro" — confirmado, ese es Laureano Monteros, persona distinta.

### 1.2 Cadencia mensual

| Mes | Commits | Lectura |
|---|---|---|
| 2026-02 | 1 | Arranque (encoders atómicos) |
| 2026-03 | 12 | **Pico** — visión TFLite/NCNN, warmup, BOM, drivebase pybricks |
| 2026-04 | 6 | Heartbeating, navegación salida, ultrasonido bloqueante, doc hardware |
| 2026-05 | 9 | Timeouts, revert claw, sprint fiabilidad, TEST_LOG, TDP |
| **Último commit** | **2026-05-24** | 7 días antes del informe; **37 días antes del mundial** |

Actividad sostenida y reciente (bien), pero el último push es a una rama abierta, no a `main`.

### 1.3 Footprint de archivos (en `main`)

Lo declarado por `git log --numstat` son **41.378 líneas agregadas / 3.894 borradas**, pero **es engañoso**: ~34.000 de esas líneas son los PDF binarios del PCB (`ROBOCUP.SHEET.pdf` 10.831 + `pcb-preview.pdf` 22.323 líneas de PDF crudo) en `073b8a2`. Descontando binarios, su aporte de código/doc real en `main` ronda **~5.000–6.000 líneas** — sigue siendo el mayor del equipo después del coach.

Archivos tocados (en `main`): `main.cpp` (×4), `Main.py` (×3), `priority_fix_flags.h` (×2), tests de zona de rescate (warmup, tflite-balance, ncnn), PCB README/BOM, drivebase.h, requirements, modelos AI.

### 1.4 Pull Requests

| PR | Estado | Merge | Reviews | Aprobaciones formales | Tamaño |
|---|---|---|---|---|---|
| #34 `fix(teensy): lectura atomica de encoders` | MERGED | Sí | 1 (COMMENTED) | 0 | +115/−41 |
| #35 `fix(vision): velocidad primera inferencia` | MERGED | Sí | 1 (COMMENTED) | 0 | +614/−53 |
| #43 `hardware(docs): esquemático/BOM/pines` | MERGED | Sí | 3 (COMMENTED) | 0 | +963/−2 |
| #50 `Mejora velocidad inferencia + balance blancos` | MERGED | Sí | **0** | 0 | +1946/−363 |
| **#129 `Bugs prioritarios`** | **OPEN** | **No** | **0** | **0** | **+5707/−506, 39 files** |

**Hallazgos de proceso:**
- PR #50 (+1946/−363) **se mergeó con 0 reviews** → viola la Regla de Oro #1 del `CLAUDE.md` ("al menos un review"). El revisor habitual es siempre Enzo (@enzzo19) y nunca dejó un `APPROVED` formal (siempre `COMMENTED`); el merge se hace por acuerdo en clase, no por aprobación trazable en GitHub.
- **PR #129 es impractico de revisar:** +5707/−506 en 39 archivos mezcla firmware, RPi, systemd, TDP completo (458 líneas ×2 archivos duplicados `TDP.md` y `docs/tdp/TDP-IITA-2026.md`), 14 assets PNG/SVG, TEST_LOG, y un `image.png` suelto en la raíz. Nadie va a revisar eso con rigor a 37 días del mundial. **Debe partirse** (ver §6).

### 1.5 Issues

- **Abiertos por Benjamin:** 5 → #51, #49, #40 (Documentación Electrónica), #38 (Clonar SD), #31, #23, #24 (varios cerrados). Buen uso de issues para encuadrar su propio trabajo.
- **Asignado:** ~50 issues (es el "dueño" de facto del cluster RPi/hardware/comms #104, #98, #97, #96, #94, y casi toda la serie #57–#76 de fiabilidad). Carga de responsabilidad enorme — desproporcionada para un alumno.

### 1.6 Calidad de mensajes de commit

**Buena.** 25/28 siguen Conventional Commits en español (`fix(teensy):`, `feat(vision):`, `hardware(docs):`). Defectos menores: espacios sobrantes (`fix(comms) :`, `fix(control) :`), un typo en cuerpo (`eliminanacion`), y 2 mensajes no-convencionales ("Análisis de cambios en hardware", merges). Cumple Regla de Oro #7 mejor que el promedio.

---

## 2. Lo bueno: fortalezas reales y verificadas

### 2.1 Documentación de hardware — su mayor activo (sobresaliente)

`hardware/cambios_de_hardware.md` (commit `789cd7d`, **autoría 100% Benjamin**, ~717 líneas) es **lo mejor documentado del repo**. Cubre 4 mejoras de hardware con un rigor que excede lo esperable de un alumno:

1. **LED 12V + APDS9960 para línea negra de salida** — cita regla 2026 §3.9 (linterna LED en pared), explica por qué la detección por cámara falla (destellos → falsos positivos), y propone usar el APDS9960 como **sensor de reflectancia** (canal Clear + `readProximity()` IR para distinguir blanco difuso de plateado especular). Incluye la justificación física de por qué bajar la ganancia de `AGAIN_4X` a `AGAIN_1X`. **Nivel de ingeniería genuino.**
2. **ESP32 Super Mini para SuperTeam Challenge** — cita regla §6.3, descarta HC-05/HC-06 con análisis técnico completo (problema de MAC address pre-challenge, roles maestro/esclavo fijos, broadcast BLE como solución), mapea pines liberados (BUZZER/LED_ROJO → 31/30).
3. **Finales de carrera para alineación de depósito** — compara contra usar pitch del BNO055, con pros/contras honestos (falsos positivos en lomas de burro).
4. **Pin de conductividad para víctimas plateadas falsas** — cita §3.10/§3.10.3, propone detección por conductividad con `INPUT_PULLUP`, y —notablemente— anticipa el **modo de falla del cable físico** (fatiga por flexión repetitiva de la garra) recomendando cable siliconado/jumper. Pensar en el modo de falla mecánico es madurez de ingeniero, no de alumno.

Cada propuesta lleva **Problema → Opciones → Solución elegida → Pros/Contras** con cita de reglamento. Esto es exactamente el formato que pide la rúbrica del TDP. **Es su mejor trabajo y está en su dominio.**

### 2.2 Documentación de evidencia de fiabilidad — honesta y trazable

`docs/tdp/code-reliability-evidence-2026.md` (en PR #129) es **modelo de honestidad técnica**: tabula cada mecanismo de fiabilidad con número de archivo y línea exactos, separa explícitamente "mecanismos en código" de "mediciones físicas", y cierra con el caveat correcto: *"Physical testing must still validate the real-world effect of these safeguards."* No infla, no miente. Comparar con el riesgo opuesto (afirmar performance sin medir) — Benjamin **no** cae en eso.

### 2.3 BOM y PCB

`hardware/electronics/PCB_Main/README.md` (PRs #43, #50): BOM en tabla con componente, uso, cantidad, proveedor y link de compra (MercadoLibre/Adafruit/DFRobot/PJRC). Cumple buena parte de lo que pide el issue #96 (BOM para TDP §Electronic), aunque falta precio y modelo formal por componente (el propio Benjamin lo reconoce en el cuerpo de PR #129).

### 2.4 Código de fiabilidad — competente (donde existe)

Muestreo del `runDistance()` con timeout (PR #129, `main.cpp:1047+`):
```cpp
void runDistance(int speed, int dir, int Distance) {
    ...
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);
    if (dir == FORWARD) {
        while (true) {
            if (fixIssue60Enabled() && (millis() - startTime) >= timeoutMs) break;
            ...
            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();   // ← claw + serial siguen vivos durante el movimiento
        }
    }
}
```
Esto **resuelve dos hallazgos de la auditoría de RESILIENCIA a la vez**: el timeout (#60) y el bug de que `runDistance/runTime/runAngle` no actualizaban `claw.update()`/`actualizarRescate()` durante el movimiento (#59). El diseño con **feature flags por issue** (`priority_fix_flags.h`, default-off para el riesgoso #63) es **ingeniería defensiva correcta** — permite activar/desactivar cada fix sin recompilar lógica. El `systemd/robot.service` con `Restart=always` ataca el #108 (auto-restart de `Main.py`). Nada de esto es superficial.

---

## 3. Lo crítico: dónde el desempeño falla o queda a medias

> Cada finding sigue la convención del equipo: **riesgo-si-NO-se-corrige · riesgo-de-corregir · tiempo**. No son "bugs a fixear", son **temas a decidir**.

### 3.1 [PROCESO-P0] El trabajo de fiabilidad no llega a `main`

**Hecho duro verificado:**
- `main.cpp` en la rama auditada (= `main`): **~4–6 menciones** incidentales de timeout/flags. **No tiene** `priority_fix_flags.h` (fue borrado en `b10485e`).
- `main.cpp` en PR #129 (`af270d2`): **41 menciones** de timeout/flags. Ahí vive todo.

Es decir: **los fixes P0/P1 de fiabilidad que Benjamin escribió están fuera de `main`**. Si hoy se flashea el robot desde `main`, **no tiene** los timeouts de `runDistance`/`runAngle`/color, ni la validación de payload, ni el handshake de boot.

- **Riesgo si NO se corrige:** el robot va al mundial con los cuelgues permanentes que la auditoría de RESILIENCIA ya documentó (issues #57–#76). El esfuerzo de Benjamin es invisible en producción.
- **Riesgo de corregir:** mergear PR #129 tal cual mete 5707 líneas sin revisar, incluyendo TDP duplicado y assets — alto riesgo de romper algo validado (Regla de Oro #4).
- **Tiempo:** partir PR #129 en 4–5 PRs revisables: **6–10 h** de trabajo de Benjamin + review.

### 3.2 [TEST-P0] El TEST_LOG está vacío en `main` — y los tests reales viven en la rama sin mergear

Este es **el hallazgo central de su dominio de banco de pruebas**, porque el issue #93 lo marcó como el de mayor impacto del TDP (~24 pts).

**En la rama auditada** (`testing/TEST_LOG.md`): las 4 categorías (`MECH`/`ELEC`/`SW`/`PERF`) están **`(vacío — próximos tests acá)`**. Solo está el ejemplo didáctico T-000. **Cero tests reales.** El esqueleto lo inicializó el coach (`c42e535`), no Benjamin.

**En PR #129** (`af270d2`), Benjamin **sí** lo llenó:
- **T-001** `[MECH][ELEC][PERF]` — medición física: batería 12.6 V → 12.5 V en 5 min reposo, **~1 h hasta 10.5 V**, error `runDistance()` ~1–2 cm, `runAngle()` "frena al grado" (±1°). Prueba de estrés 10 min con `speed=60` + pickup marcada **PARTIAL** (voltaje final "no registrado").
- **T-002** `[SW][PERF]` — desde el `systemd` real con `journalctl`: **line-following 91.33 FPS**, **rescate/depósito 22.25–22.40 FPS** con TFLite + anti-flash + AGCWD + tracker, transición Teensy→RPi confirmada (byte `0xF8`/248), `frames_sent` 1→2204.

**Evaluación honesta de la calidad de esos tests:**
- ✅ Son **tests reales con números reales**, no inventados. T-002 cita logs concretos del servicio.
- ⚠️ **Una sola corrida cada uno** (n=1). La rúbrica de fiabilidad valora repetibilidad (X/10). No hay pickup X/10, deposit 5+5, ni matriz de confusión de color.
- ⚠️ Varios campos **"no registrado"** (iluminación en ambos; batería en T-002). Resta valor como evidencia citable.
- ⚠️ El acompañante `TEST_LOG_AUTO.md` (690 líneas) está **explícitamente marcado "Generated by Codex"** y es **extracción de constantes del código, NO tests medidos** (lo dice su propio header). Es útil como inventario, pero **no es banco de pruebas**. No debe presentarse como evidencia de testing físico.
- ✅ `MEDICIONES_PENDIENTES.md` es un **excelente plan de sesión de banco** (~45 min, 9 mediciones priorizadas ALTA/MEDIA, con dónde va cada una en el TDP). Muestra que Benjamin **sabe** qué falta medir.

**Conclusión del dominio banco:** Benjamin **entiende perfectamente** la disciplina de banco de pruebas (el plan y las 2 entradas lo prueban), pero la **ejecución está incompleta (n=1, campos faltantes) y, peor, no mergeada**. La afirmación de PR #129 "Closes #93" es **optimista**: el log existe pero con 2 tests parciales, no con la batería completa que el TDP necesita.

- **Riesgo si NO se corrige:** el TDP pierde la sección de evidencia de fiabilidad (~24 pts) o se entrega con n=1.
- **Riesgo de corregir:** ninguno técnico; es trabajo de banco. El riesgo es **de calendario** (necesita sesiones con el robot armado).
- **Tiempo:** la sesión de banco que falta = **~45–60 min con el robot** + 30 min de transcripción. Mergear lo ya hecho = parte de §3.1.

### 3.3 [PROCESO-P1] El revert de timeouts en `main` (2026-05-10)

Secuencia verificada en `main`:
1. `5bac4a5` (18:06) `feat(teensy): timeouts implementados` → mete timeouts + `priority_fix_flags.h`.
2. `b10485e` (18:27) borra `priority_fix_flags.h` (−13 líneas).
3. `cead75e` (19:26) `fix(teensy): error de libreria claw.cpp` → **−181 líneas**, arranca el `#include "priority_fix_flags.h"` y todas las funciones de fix/blink/fatal loop.

O sea: los timeouts vivieron en `main` **~80 minutos** y se revirtieron el mismo día por un error de compilación/librería de la garra. **Está bien revertir algo que no compila** (Regla de Oro #4) — el problema no es el revert en sí, es que **el re-arreglo correcto tardó 10 días y terminó en una rama sin mergear** (§3.1). La auditoría de RESILIENCIA ya citó `cead75e`; aquí se agrega el **dato de causa-raíz**: fue un fallo de integración de `claw.cpp` con los flags, no un rechazo de diseño.

- **Riesgo si NO se corrige:** ya cubierto en §3.1 (main sin timeouts).
- **Tiempo:** incluido en el re-merge de §3.1.

### 3.4 [HYGIENE-P2] Archivos basura y binarios en el repo

Benjamin commiteó al repo (agregados en sus commits):
- `image.png` **suelto en la raíz** (PR #129).
- Modelos con nombres de descarga sin limpiar: `best_float32 (1).tflite`, `best (2)_float32.tflite`, `dcenet_int8.tflite`, `model.ncnn.param`.
- 34.000+ líneas de PDF binario del PCB versionadas como texto en git.

Esto es exactamente el issue #69 (modelos `.onnx/.pt/.tflite` y videos al repo → migrar a Git LFS) que está **asignado a él y abierto**. El paréntesis y espacio en `best_float32 (1).tflite` es frágil en shells/CI.

- **Riesgo si NO se corrige:** repo pesado, clones lentos, posibles fallos de path en CI por espacios/paréntesis. No bloquea competencia.
- **Riesgo de corregir:** mover a LFS requiere reescribir historia o `git lfs migrate` — cuidado con romper checkouts del equipo a días del mundial. **Probablemente NO vale la pena tocar antes de Incheon.**
- **Tiempo:** 1–2 h si se hace; recomendación: **post-mundial**.

### 3.5 [PROCESO-P2] PRs sobredimensionados e irreviewables

PR #50 (+1946/−363, 0 reviews) y sobre todo PR #129 (+5707/−506, 39 files) son **demasiado grandes para review real**. Mezclan dominios (firmware + RPi + systemd + TDP + assets + testing). El TDP aparece **duplicado** (`TDP.md` y `docs/tdp/TDP-IITA-2026.md`, 458 líneas idénticas) — desperdicio y fuente de divergencia futura.

- **Riesgo si NO se corrige:** los reviews son rubber-stamp o no ocurren → bugs entran sin filtro (es lo que pasó con #50).
- **Tiempo:** disciplina de PR chico; costo cero, es hábito.

---

## 4. Relación con auditorías previas (no se repiten; se conectan)

| Issue previo | Cómo lo toca Benjamin | Estado real |
|---|---|---|
| #57–#62, #74–#76 (RESILIENCIA: timeouts, validación serial, init visible) | **Los implementa** en PR #129 con feature flags | ✅ Escrito, ❌ no mergeado a `main` |
| #59 (motion no actualiza claw/rescate) | `serviceMotionBackgroundTasks()` en loops de movimiento | ✅ Resuelto en PR #129 |
| #108 (sin auto-restart de Main.py) | `systemd/robot.service` con `Restart=always` | ✅ Escrito en PR #129 |
| `cead75e` (revert citado por RESILIENCIA) | **Es su commit**; causa-raíz = fallo integración `claw.cpp` + flags | Dato nuevo aportado aquí |
| #B7 (CORRECTITUD: formato tensor TFLite/NMS) | Asignado a él (#124), `TEST_LOG_AUTO` lo lista como "needs validation" | ⏳ Pendiente |
| #B10 (encoder sin calibrar) | T-001 mide `runDistance` ~1–2 cm error; doc TDP explica 25 counts/cm vs 28.65 teórico | ✅ Parcialmente caracterizado en banco |
| #93 (inicializar TEST_LOG, ~24 pts) | Lo llena (T-001/T-002) pero **solo en PR #129**, n=1 | ⚠️ Parcial |

Benjamin es, de hecho, **el ejecutor designado de la mayoría de los fixes de RESILIENCIA**. Su trabajo cierra muchos de esos issues en código — el cuello de botella es el merge, no la autoría.

---

## 5. Evaluación honesta del desempeño

**Calidad técnica:** Alta. Código de fiabilidad correcto (feature flags, timeouts no bloqueantes, background service durante movimiento). Documentación de hardware **sobresaliente** y honesta. Anticipa modos de falla físicos (cable de garra). Es el alumno con criterio de ingeniería más maduro visible en el repo.

**Cantidad:** Alta. #2 del repo en volumen, amplitud de 4 subsistemas, cadencia sostenida feb→may.

**Documentación de hardware (foco del encargo):** **Excelente.** `cambios_de_hardware.md` y el BOM son lo mejor del repo en su categoría. Cumple el formato de rúbrica TDP de forma natural.

**Documentación de testeos de banco (foco del encargo):** **Mixto / incompleto.** Demuestra que **sabe** hacerlo (plan `MEDICIONES_PENDIENTES.md` impecable, 2 entradas reales T-001/T-002 con números de `journalctl`). Pero: (a) n=1 por test, (b) campos "no registrado", (c) `TEST_LOG_AUTO` es AI-extraction, no tests, (d) **todo en rama sin mergear** → en `main` el banco está vacío. La promesa "Closes #93" es optimista.

**Disciplina de proceso:** **Es su debilidad.** PRs gigantes irreviewables, un merge sin review (#50), su mejor trabajo varado en PR #129 OPEN/0-reviews, basura commiteada, dos identidades git, revert a `main` sin re-merge oportuno. La brecha entre "lo que escribió" y "lo que está en producción" es grande y peligrosa a 37 días del mundial.

**Síntesis:** El talento y el esfuerzo de Benjamin **no son el problema**. El problema es de **flujo de entrega**: produce trabajo de calidad mundial y lo deja en ramas que nadie mergea ni revisa. **El riesgo más alto del equipo asociado a Benjamin no es que falle su código — es que su buen código nunca llegue a `main`.**

---

## 6. Recomendaciones accionables (priorizadas, framing temas-a-decidir)

1. **[P0 · ~6–10 h] Partir PR #129 en PRs revisables y mergear lo seguro a `main`.** Orden sugerido:
   - PR-A: firmware timeouts + `priority_fix_flags.h` + validación serial (cierra #57–#62, #74–#76, #112). **Probar en banco antes de mergear** (Regla de Oro #3) y anotar en `TEST_LOG`.
   - PR-B: RPi recovery + `systemd` (cierra #108, #65, #64).
   - PR-C: TEST_LOG con T-001/T-002 + `MEDICIONES_PENDIENTES` (referencia #93, sin "Closes" hasta completar n≥5).
   - PR-D: docs TDP (un solo `TDP.md`, eliminar duplicado) + assets.
   - *Riesgo de no hacerlo:* el robot va a Incheon sin los timeouts. *Riesgo de hacerlo:* romper algo validado → mitigado partiendo + probando.
2. **[P0 · ~1 h banco + 30 min doc] Completar la sesión de banco de `MEDICIONES_PENDIENTES.md`** con repeticiones (pickup X/10 negra+plateada, deposit 5+5, runDistance/runAngle ×10, voltaje final de estrés, anti-flash con linterna). Registrar iluminación y batería que hoy faltan. Convertir T-001/T-002 de n=1 a evidencia citable.
3. **[P1 · hábito] No volver a mergear sin un `APPROVED` formal en GitHub** y mantener PRs < ~400 líneas / un dominio. Aplica a todo el equipo, pero Benjamin es el reincidente.
4. **[P2 · post-mundial] Resolver #69 (LFS)** y quitar `image.png` de la raíz y los nombres `(1)`/`(2)` de modelos. **No tocar la historia antes de Incheon.**
5. **[P2 · 5 min] Unificar `user.email`** en su entorno git para dejar de commitear bajo dos identidades.
6. **[Coach] Re-balancear la carga de issues asignados a Benjamin** (~50). Es insostenible; varios del cluster comms #70–#76 podrían ir a Laureano/Lucio.

---

## 7. Apéndice — comandos de verificación usados

```bash
git shortlog -sne --all
git log --all --author="enjamin\|illagran" --format="%h | %ci | %s"
git log --all --format="%h|%an|%s" -- hardware/cambios_de_hardware.md   # → autor 100% Benjamin
git show af270d2:testing/TEST_LOG.md          # tests reales T-001/T-002 (rama PR#129)
grep -c "priority_fix_flags|timeout" main.cpp # main=~4 ; af270d2=41 (confirma revert)
gh pr list --author benjaminvillagran --state all --json number,state,reviews,mergedAt
gh issue list --assignee benjaminvillagran --state all   # ~50 asignados
```

*Informe generado para la auditoría integral 2026-05-18. Solo lectura — no se modificó código fuente, no se abrieron/cerraron issues ni PRs.*
