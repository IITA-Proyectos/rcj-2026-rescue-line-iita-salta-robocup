## Consolidado de auditoría 2026-05-16 — input para el triage #91

**Fase:** 🟢 Fase 1 — push exhaustivo · **T–6 semanas a Incheon** · freeze el 2026-05-20 (3-4 días).
Auditoría integral de los 3 subsistemas (Teensy firmware / RPi visión / comms) sobre branch `feature/initialize-testing-log` (commit `c42e535`). Deduplicado contra issues #4–#102 y `AUDIT-ACTION-PLAN.md`.

**Para Enzo:** esto es el insumo para cerrar el triage del #91 (vence). Decidir baldes (must/should/post-mundial) y qué se congela el 2026-05-20.

---

### 🔴 ALERTA P0 — confirmado (no es finding nuevo, es estado de #59/#60/#61/#62)

Los timeouts de los issues **#59 / #60 / #61 / #62 están REVERTIDOS** en el código actual.

- `5bac4a5 feat(teensy): timeouts implementados` los implementó.
- `cead75e fix(teensy): error de libreria claw.cpp` borró 181 líneas (incl. `priority_fix_flags.h`).
- Ningún commit posterior los restauró.

El equipo opera creyendo que están resueltos y **no lo están**. Recomendación: re-aplicar incremental (issue por issue) tras arreglar el error de `claw.cpp` que forzó el revert. **Prioridad #1 de Lautaro antes del freeze.**

---

### Quick-wins de CONFIABILIDAD (bajo riesgo · alto potencial · entran antes del 05-20)

| Tema | Subsist | Archivo | Fix | Riesgo fix | Por qué alto impacto |
|---|---|---|---|---|---|
| **T-A** `get_color()` sin timeout | control | `main.cpp:336` | 3 líneas (guard `millis()`) | Muy bajo | Se llama cada iteración del loop de línea. I2C flojo por vibración/rampa → freeze permanente → LoP sin recuperación |
| **T-B** `taskDone` nunca vuelve a `false` | control | `main.cpp:59` | 1 línea (init `true`) | Bajo | Si arranca sin ritual switch-off, no despacha acciones (ignora verde/obstáculo). El juez puede no dar tiempo al ritual |
| **V-A** Frame race en `camthreader` | visión | `camthreader.py:32` | `threading.Lock`, 6 líneas | Bajo | `grabbed,frame` sin lock → decisiones de ángulo sobre frame stale → se pasa rampa/curva |
| **V-E** `calibration.py` desincronizada | visión | `calibration.py:29` | 3 líneas | Muy bajo | Operador calibra color viendo LAB y RGB de frames distintos → umbrales mal → falsos +/− de verde |
| **C-A** Test comms 57600 vs prod 115200 | comms | `test/comms/serialReceive.cpp:21` | 1 número | Muy bajo | La única herramienta de diagnóstico de comms da resultados falsos — agujero ciego en semanas de banco |

### Quick-wins de PERFORMANCE (bajo riesgo · alto potencial)

| Tema | Subsist | Archivo | Fix | Riesgo fix | Ganancia estimada |
|---|---|---|---|---|---|
| **V-F** `print(area)` en hot path de línea | visión | `Main.py:799` | borrar / flag debug | Mínimo | `print` por contorno por frame, ~20 ms I/O. +5-15% FPS en piso reflectivo. *Mejor ratio de todos* |
| **V-D** `agcwd()` LUT con list-comprehension | visión | `Main.py:198` | 1 línea (vectorizar) | Mínimo | 256 iter Python/frame × 35 fps. Sin cambio de semántica |
| **V-B** `enhance()` doble conversión BGR↔HSV | visión | `Main.py:188-248` | refactor ~30 líneas | Bajo (banco) | 2-3 conversiones color/frame. +15-25% FPS de inferencia — mayor potencial absoluto |
| **V-C** `frame_q` bloquea `capture_thread` | visión | `Main.py:314,449` | drop-oldest, ~5 líneas | Bajo-medio | Throttling térmico → productor colgado → frames 200-400 ms viejos en rescate |
| **T-C** `delay(10)` por iter en `runDistance` | control | `main.cpp:551,575` | quitar/bajar a 1 ms | Bajo | PID limitado a 100 Hz → menos precisión en avances de 5-8 cm de zona de rescate |

### NO son quick-win (banco con cuidado o post-freeze — honestidad de coach)

| Tema | Subsist | Por qué medio/alto riesgo |
|---|---|---|
| FSM rescate llama `runDistance/runTime` bloqueantes (relac. #59) | control | Refactor a sub-FSM con `millis()`. Alto payoff pero toca lógica de rescate validada |
| `serialEvent5` desfase post-maniobra → `speed=254` aberrante (relac. #70) | comms | Refactor parser, afecta 5 call-sites. Medio-alto |
| `Serial5.write(255)` colisiona con `SYNC_SPEED` (5 sitios) | comms | Switch accidental → RPi en `'esperando'` infinito. Fix bilateral |
| Doble-pick `green_state==6/7` con `if` sin `else if` | comms/control | Re-detección → secuencia pinza 2× → `ball_counter` falso → depósito falla |
| `runTime/runDistance` consumen serial sin parsear (relac. #63) | comms | Comandos de pinza en rescate se pierden. Cuidar la parada por switch |

---

### Verificación útil (riesgo descartado)

Los auditores confirmaron que los **rangos del payload serial NO colisionan con sync bytes** en producción (`speed` 0-40, `angle+90` 0-180, todos < 252). Un riesgo que se puede tachar de la lista.

### Acciones sugeridas para el triage #91

1. Mover los 10 quick-wins a `must-ship-incheon` (caben antes del freeze, bajo riesgo).
2. Re-aplicar timeouts #59/#60/#61/#62 → prioridad #1 Lautaro.
3. Los 5 medio-riesgo → evaluar uno por uno: ¿entra antes del 05-20 con banco, o `post-mundial`?
4. Cluster RPi/hardware detallado → ver el issue de Benjamin (creado en paralelo a este).

*Auditoría asistida por Claude Code bajo supervisión de @gviollaz. Hallazgos en formato TEMA A ANALIZAR (riesgo-si-no / riesgo-si-sí / tiempo).*
