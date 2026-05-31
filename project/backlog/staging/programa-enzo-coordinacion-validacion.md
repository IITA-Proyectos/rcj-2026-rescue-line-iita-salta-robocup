# Programa de coordinación y validación — Enzo Juarez

> **Documento de apoyo para Enzo. NO commiteado. Es guía de coordinación/aprobación, no una directiva — Enzo decide y adapta.**
>
> Generado por Claude Code (Sonnet 4.6) a pedido del director @gviollaz · 2026-05-18.
> Branch: `feature/initialize-testing-log` · Commit: `c42e535`.

---

## 0. El contexto en una frase

El equipo lleva ~7 días sin un solo commit ni issue cerrado. El diseño está completo (#114 tiene el roadmap). El cuello no es técnico: es arranque de ejecución. Tus 2 acciones de Sprint 0 desbloquean todo lo demás.

---

## 1. Mapa del tablero esta semana — 1 página

### Régimen de tracks

| Track | Fase actual | Push libre hasta | Gate Enzo | Gate Gustavo |
|-------|-------------|------------------|-----------|--------------|
| **Track A** (firmware/comms + Teensy) | Sprint 1-2 | 2026-05-26 | 27-may → 06-jun | desde 07-jun |
| **Track B** (docs/visión + RPi) | Sprint 1 | 2026-06-11 | desde 12-jun | desde 12-jun |

### Qué hace cada alumno esta semana

#### Laureano / Laureano Monteros (`@Laumonteros`) — Track A · Firmware Teensy

Foco de Sprint 1-2: código que se escribe sin robot enfrente + validación en banco.

| # | Issue | Tarea | Sprint | Robot necesario | Prioridad |
|---|-------|-------|--------|-----------------|-----------|
| 1 | #105 / #59-#62 | Re-aplicar timeouts revertidos (diagnóstico `claw.cpp` primero, re-aplicar issue por issue) | Sprint 1 | NO para escribir / SÍ para banco | PRIMERO |
| 2 | #112 | Timeout + dreno serial en `runAngle()` (patrón idéntico a #60; `runAngle` nunca tuvo fix) | Sprint 1 | NO para escribir / SÍ para banco | SEGUNDO |
| 3 | #105 T-A | `get_color()` sin timeout en `while (!apds.colorDataReady())` — 3 líneas | Sprint 1 | SÍ (banco para validar) | TERCERO |
| 4 | #105 T-B | `taskDone` nunca vuelve a `false` — 1 línea | Sprint 1 | SÍ (banco) | CUARTO |
| 5 | #53 | Heartbeat serial + failsafe `speed=0` (**palanca #1 de confiabilidad**) | Sprint 2 | SÍ (banco para tunear timeout real) | Con banco |
| 6 | #27 | Watchdog de hardware `WDT_T4` + callback que para motores | Sprint 2 | SÍ (banco para validar reset+recuperación) | Con banco |

> Orden de arranque concreto para Laureano: leer `claw.cpp` en el commit `cead75e` para entender qué rompió el revert, luego re-aplicar #60 → #61 → #59 → #62 de a uno, con banco entre cada uno.

#### Lucio (`@luciouriel2011`) — Track B · Visión RPi

Foco de Sprint 1: código que se escribe en cualquier PC, sin robot enfrente.

| # | Issue | Tarea | Sprint | Robot necesario | Prioridad |
|---|-------|-------|--------|-----------------|-----------|
| 1 | #113 | `threading.Lock` en `camthreader.py` — ~6 líneas | Sprint 1 | NO para escribir / SÍ para banco | PRIMERO |
| 2 | #110 | Inicializar `cx_black = width//2` + `try/except` en loop de línea — ~2 líneas | Sprint 1 | NO para escribir / SÍ para banco | SEGUNDO |
| 3 | #108 | Unit `systemd` `robot.service` con `Restart=always` + `try/except Exception` global en `Main.py` | Sprint 1 | NO (se puede probar en cualquier Pi/PC) | TERCERO |

> Lucio puede empezar HOLA mismo en su notebook/checkout. Los cambios #113 y #110 son cirugía de 6 y 2 líneas respectivamente.

#### Benjamin (`@benjaminvillagran`) — Track B · RPi + Hardware + Banco

Rol dual: fix propio + **gate de validación en banco** de los fixes de Lucio.

| # | Issue | Tarea | Sprint | Observación |
|---|-------|-------|--------|-------------|
| 1 | #68 | Pinear `requirements.txt` desde la Pi de la última corrida buena — `pip freeze` | Sprint 1 | Fix tuyo, sin banco especial |
| 2 | Co-review + banco de Lucio | Validar #113/#110/#108 con banco (FPS, kill -9, frame ID) | Sprint 1 | Sos el gate de banco del cluster RPi |
| 3 | #104 V-F | `print(area)` en hot path del loop de línea — borrar o poner detrás de flag debug (5 min) | Sprint 1 | Mejor ratio esfuerzo/impacto de visión |
| 4 | #104 V-D | Vectorizar LUT de `agcwd()` con `np.power` — 1 línea | Sprint 1 | Quick-win de FPS |

> Benjamin es el "banco coordinator" del Track B. Ningún PR de visión se mergea sin su check en hardware real.

---

## 2. Sprint 0 — Las 2 acciones de destrabe de Enzo

**Sin estas 2, nada fluye. Son tuyas. Esta semana.**

### Acción 1: Mergear PR #101 (TEST_LOG.md)

- **Qué es:** agrega `testing/TEST_LOG.md` y `testing/README.md`. Solo documentación. 196 líneas agregadas, 0 eliminadas. Riesgo cero.
- **Por qué importa:** ~27 pts del TDP de Incheon. Sin este archivo, NINGÚN PR de fix puede dejar el registro de banco requerido por las reglas del repo.
- **Cómo:** ir a [PR #101](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/pull/101) → revisar que el checklist obligatorio esté completo (está) → **Merge pull request**. Lleva menos de 5 minutos.
- **Check previo:** el PR ya tiene su checklist marcado. El test plan dice "no aplica banco, es solo documentación". Vas a ver un review del chatgpt-codex-connector; podés ignorarlo o leerlo. La aprobación es tuya.

### Acción 2: Correr el triage de #91 (vencido desde 2026-05-17)

El issue #91 pedía una sesión de 60-90 min con Benjamin. Con el roadmap #114 ya definido (publicado el 2026-05-18), el triage se simplifica: la decisión ya fue tomada, solo falta registrarla.

#### Guion del triage en 1 hora (podés hacerlo solo, o con Benjamin)

**Minutos 0-10: preparar la vista**

Abrí estos 4 tabs en GitHub:
- Issue #91 (donde vas a pegar el resultado)
- Issue #114 (el roadmap — es tu referencia maestra de prioridades)
- Issue #103 (el consolidado de auditoría — tiene todos los issues agrupados)
- Issue #105 (cluster Laureano) + Issue #104 (cluster Benjamin)

**Minutos 10-40: clasificar en 3 baldes**

Para cada issue de #103 y #91, asignalo a uno de estos baldes:

| Balde | Criterio | Issues de referencia |
|-------|----------|----------------------|
| **must-ship-Incheon Track A** (cierra antes 26-may) | Firmware/comms, tiene fix escrito en Sprint 1-2, banco disponible | #59, #60, #61, #62, #112, #53, #27 + T-A, T-B, T-C de #105 |
| **must-ship-Incheon Track B** (cierra antes 11-jun) | Visión/RPi, fix escrito en Sprint 1, banco con Benjamin | #108, #110, #113, #68, #65, #66, #73, #64 + V-A, V-B, V-C, V-D, V-E, V-F de #104 |
| **post-mundial** | Requiere banco intensivo, riesgo medio/alto, o refactor grande | FSM rescate bloqueante, `serialEvent5` desfase, doble-pick `green_state`, `Serial5.write(255)` colisión |

**Regla rápida:** si el fix tiene riesgo "muy bajo" o "bajo" en el issue → `must-ship`. Si tiene "medio" o "alto" → `post-mundial` salvo que el banco esté disponible y el equipo lo pueda validar antes del freeze.

**Minutos 40-55: asignar dueño a cada must-ship**

| Dueño | Issues |
|-------|--------|
| @Laumonteros | Todo lo de Track A en #105 + #112 + #53 + #27 |
| @luciouriel2011 | #113, #110, #108 |
| @benjaminvillagran | #68, #104 V-F, V-D + co-review banco de lo de Lucio |

**Minutos 55-60: pegar el resumen en issue #91**

Formato mínimo para cerrar el issue:

```
Triage completado 2026-05-[XX]
Track A (cierra ≤2026-05-26): #60, #61, #62, #59, #112, #53, #27 → dueño @Laumonteros
Track B (cierra ≤2026-06-11): #113, #110, #108, #68, #65, #66, #73, #64 → dueños @luciouriel2011 @benjaminvillagran
Post-mundial: [lista]
```

> Ese comentario en #91 = triage cerrado. No necesita ser perfecto — necesita existir.

---

## 3. Checklist de aprobación de PRs (activo reutilizable)

### Checklist base — aplica a TODO PR antes de mergear

- [ ] El PR está vinculado a un issue con `Closes #NNN` en el cuerpo
- [ ] El título sigue Conventional Commits en español (`fix(teensy): ...`, `feat(rpi): ...`, `docs(testing): ...`)
- [ ] El PR no toca archivos fuera del scope del issue que cierra (revisar el diff — si toca `main.cpp` y `Main.py` al mismo tiempo sin que el issue lo pida, es sospechoso)
- [ ] El checklist obligatorio del PR template está completado (no solo marcado a ciegas)
- [ ] No hay binarios pesados en el diff (`.onnx`, `.tflite`, videos)
- [ ] No hay secretos ni tokens (buscar visualmente en el diff)
- [ ] El idioma del diff es español (comentarios, mensajes)
- [ ] Hay una entrada real en `testing/TEST_LOG.md` con fecha, escenario y resultado (no la entrada-ejemplo T-001)

---

### Checklist por tipo: Firmware Teensy (PRs de Laureano)

- [ ] **Compila sin error:** el PR describe que `pio run` pasa (o hay log en el PR). Si no hay mención de compilación, pedísela.
- [ ] **Banco ejecutado antes del merge:** el cuerpo del PR dice explícitamente "Probado en banco" y describe el escenario (qué pusiste, qué observaste). Si dice "NO PROBADO EN BANCO — pendiente antes de merge", **no mergear hasta que actualice el PR con el resultado**.
- [ ] **Escenario de falla provocado:** para fixes de timeout/watchdog, el banco debe incluir el escenario de falla forzado (encoder desconectado, IMU desconectado, no solo "funcionó normal"). Si el PR no muestra el escenario de falla, pedíselo.
- [ ] **No rompe el ritual de arranque:** verificar que el PR no cambia la secuencia switch-off/switch-on ni el comportamiento de `taskDone` salvo que ese sea el fix explícito.
- [ ] **Un issue a la vez:** si el PR re-aplica los timeouts de #60, #61, #62 de golpe en un solo commit, pedís que lo partan. Los timeouts van de a uno para poder bisectar si algo rompe.
- [ ] **Entrada en TEST_LOG.md:** formato `YYYY-MM-DD — [fix] #NNN descripción` con medición (tiempo de timeout, corridas exitosas / corridas totales, valores medidos).

> Regla de oro del repo (CLAUDE.md): **banco antes de mergear firmware, sin excepciones.**

---

### Checklist por tipo: Python RPi — visión y sistema (PRs de Lucio y Benjamin)

- [ ] **Compila (sintaxis):** el PR menciona `python -m py_compile software/raspberry/final_rpi/Main.py` o equivalente. Si no, pedíselo — es un comando de 10 segundos.
- [ ] **No baja el FPS:** para cualquier fix de visión (camthreader, loop de línea, agcwd), el banco debe incluir medición de FPS antes/después (aunque sea 5 s de `print(time.time())`). Si el fix optimiza y el PR no muestra FPS, pedíselo.
- [ ] **Escenario de falla provocado para resiliencia:** para #113 (Lock), el banco debe mostrar que los IDs de frame ya no se repiten. Para #110 (cx_black), que frente a verde sin línea el robot no crashea. Para #108 (systemd), que `kill -9` se recupera en ≤5 s.
- [ ] **No rompe la calibración:** cualquier cambio en `Main.py` que toque la detección de verde/plata/negro debe mostrar una corrida de calibración que confirme que los umbrales siguen funcionando.
- [ ] **Entrada en TEST_LOG.md:** incluir FPS medido, tiempo de recuperación, o el identificador de frame según aplique.

---

### Checklist por tipo: systemd/config (PRs de Benjamin — OS, requirements, services)

- [ ] **Probado en la Pi real** (no en laptop): los servicios systemd, el `requirements.txt` y el `rc.local` solo se pueden validar en hardware. Si el PR dice "probado en VM", pedís que se pruebe en la Pi del equipo.
- [ ] **`requirements.txt` con versiones exactas (`==`)**: no acepta `>=` en ninguna dependencia crítica (`opencv-python`, `numpy`, `tflite-runtime`, `pyserial`). Si hay `>=`, pedís que lo pinee.
- [ ] **`robot.service` con `Restart=always` y `RestartSec` razonable (2-5 s)**: revisar el diff del `.service` file.
- [ ] **Banco: `kill -9` del proceso y cronometrar recuperación**: resultado esperado ≤5 s. Si el PR no tiene ese resultado, pedíselo.

---

## 4. Gate por fase — qué significa que seas el gate en fase amarilla

### Fase 🟡 Track A: desde 2026-05-27 hasta 2026-06-06

A partir del 27-may, **todo PR de firmware/comms/Teensy pasa por tu aprobación antes de mergear a main**.

Esto no significa revisar el código línea por línea (eso es rol de auditor). Significa verificar:

1. **¿El PR cierra un issue del must-ship-Incheon?** Si cierra un issue post-mundial o introduce algo no planeado, es una conversación antes del merge.
2. **¿El checklist de firmware está completo?** (ver sección 3 arriba). Si falta banco, no mergea.
3. **¿El scope está contenido?** Un PR de `fix(teensy): timeout runDistance #60` no debería tocar `Main.py` ni agregar features nuevas. Si lo hace, pedís que lo parta.
4. **¿El robot sigue siendo capaz de correr una corrida completa?** Después de cualquier merge de firmware en freeze, el criterio mínimo es: enciende, linetrack básico funciona, no hay watchdog reset en 2 min de banco. Si no podés hacer esa validación antes del merge, pedís que alguien del equipo la haga y te mande el resultado.

**Lo que NO hacés en freeze:**
- No aprobás PRs que agregan features no listadas en #114 Sprint 1-2-3.
- No aprobás PRs de "mejora de performance" sin bench antes/después.
- No aprobás PRs que toquen la lógica de rescate o la FSM principal sin banco intensivo documentado.

### Fase 🟡 Track B: desde 2026-06-12

Misma lógica que Track A pero para RPi/visión. Checklist Python RPi (sección 3). El criterio de "robot sigue corriendo" incluye visión funcional: `Main.py` arranca, detecta línea en banco, no crashea en 2 min.

---

## 5. Ritmo semanal — los 8 días críticos de Track A (18-26 mayo)

### Cada día, 5-10 minutos de check

```
Abrir GitHub → Issues → filter: assignee:Laumonteros state:open
```

Preguntas que guían el check:
- ¿Laureano abrió una rama hoy? (`git log --oneline --all` o ver la pestaña Branches)
- ¿Hay un PR nuevo o actualizado?
- ¿El PR más reciente tiene banco o dice "NO PROBADO"?

### Señales de alerta (actuar si aparecen)

| Señal | Qué hacer |
|-------|-----------|
| 48 hs sin commits de Laureano en Track A | Escribirle directo: "¿en qué estás trabado? ¿tenés el robot?" |
| PR de firmware sin banco después de 24 hs | Comentar en el PR: "¿cuándo bancás esto?" — no mergear |
| PR que toca más de 1 issue a la vez | Pedir que lo divida antes de revisar |
| Laureano pregunta por el revert de `claw.cpp` | Decirle: leer el diff del commit `cead75e`, entender qué dependía de `priority_fix_flags.h`, reconstruir solo esa parte antes de re-aplicar el timeout |

### Uso de `/coach-checkin` y el journal

El repo tiene un journal en `journal/` (si existe) o en las notas de clase. El checkin diario de Enzo puede ser tan simple como:

```
2026-05-19 — Enzo
- PR #101 mergeado ✓
- Triage #91 completado ✓ (Track A: 7 issues / Track B: 8 issues)
- Laureano: rama abierta para #60, sin banco aún
- Lucio: sin actividad — escribirle mañana
- Pendiente: revisar que Laureano tiene el robot disponible esta semana
```

No tiene que ser perfecto — tiene que existir para que Gustavo pueda leerlo en el gate del 27-may.

---

## 6. Guion de la reunión de arranque — 15 minutos

**Objetivo:** romper la inercia de 7 días sin movimiento. No es una reunión de planificación (eso ya está hecho). Es una reunión de ARRANQUE.

**Cuándo:** lo antes posible esta semana — si podés hacerla hoy o mañana, mejor.

**Formato sugerido:** presencial o videollamada de 15 min exactos (ponés un timer).

---

### Apertura (2 minutos)

> "Voy a ser directo: llevamos 7 días sin un commit. El plan está listo, el roadmap está en el issue #114, todo está decidido. La única razón por la que no avanzamos es que nadie arrancó. Hoy arrancamos. Esta reunión dura 15 minutos y cuando termina cada uno tiene UNA tarea que empieza hoy."

---

### Contexto en 2 frases (1 minuto)

> "El objetivo para Incheon es 8/10 de confiabilidad. Hoy estamos en 2/10. No necesitamos diseñar nada nuevo — el diseño ya existe. Lo que necesitamos es escribir código y validarlo en banco. Eso empieza hoy."

---

### Asignación de tareas (5 minutos — una por persona)

Decirle a cada uno su PRIMERA tarea, no la lista completa:

**Laureano:**
> "Tu primera tarea, esta semana: leer el commit `cead75e` en GitHub y entender qué borró. Después me contás qué rompió `claw.cpp` y cómo re-aplicamos el timeout de `runDistance` sin volver a romper nada. No hay que hacer todo a la vez — empezá por el diagnóstico. Abrís una rama `fix/issue-60-timeout-runDistance` hoy."

**Lucio:**
> "Tu primera tarea es la más chica del equipo: 6 líneas en `camthreader.py` para agregar un threading Lock. Podés hacerlo en tu notebook ahora mismo, sin el robot. Abrís una rama `fix/issue-113-camthreader-lock` hoy."

**Benjamin:**
> "Tu primera tarea: mergear los cambios de Lucio en banco cuando estén listos. Y mientras, pinear el `requirements.txt` desde la Pi — es `pip freeze > requirements.txt` y un PR. Eso podés hacerlo hoy también."

---

### Reglas del juego (3 minutos)

> "Tres reglas simples hasta Incheon:
>
> 1. **Banco antes de mergear firmware.** Sin excepción. Si Laureano hace un fix y no lo bancó, el PR queda abierto hasta que haya banco. La foto o el log va en el PR.
>
> 2. **Un issue a la vez.** No mezclen fixes en el mismo PR. Si terminan uno y arranca el siguiente, está perfecto — pero los commits son separados.
>
> 3. **Si estás trabado más de 30 minutos, avisás en el issue.** No pierdan media clase en algo que se resuelve con un comentario."

---

### Pregunta de cierre (2 minutos)

> "¿Alguien tiene algo que no le queda claro de su primera tarea? ¿Alguien no tiene acceso al robot o al repo?"

Escuchar. Si alguien dice "no tengo el robot", resolver la logística en el momento (¿quién tiene acceso al banco esta semana?).

---

### Cierre (2 minutos)

> "Bien. Mañana a esta hora reviso el repo. No espero que esté terminado — espero ver una rama abierta por cada uno. Eso me dice que arrancaron. ¿Alguna duda antes de empezar?"

Timer suena. La reunión terminó.

---

## Apéndice rápido: comandos de lectura GitHub para Enzo

```bash
# Ver estado de PRs abiertos
gh pr list --state open

# Ver un PR específico
gh pr view 101

# Ver issues de un alumno
gh issue list --assignee Laumonteros --state open
gh issue list --assignee luciouriel2011 --state open
gh issue list --assignee benjaminvillagran --state open

# Ver el roadmap maestro
gh issue view 114

# Ver el consolidado de auditoría
gh issue view 103
```

---

## Resumen ejecutivo — qué hacer esta semana en orden

| Día | Enzo hace |
|-----|-----------|
| Hoy (18-may) | Mergear PR #101 (5 min) |
| Hoy o mañana | Correr triage #91 (60 min) + reunión de arranque con los 3 (15 min) |
| 19-22 may | Check diario 5-10 min: ¿hay ramas abiertas? ¿PRs nuevos? |
| 22-24 may | Primer PR de Laureano esperado (#60 o #112) — revisar con checklist firmware |
| 25-26 may | Primer PR de Lucio esperado (#113 o #110) — revisar con checklist Python RPi |
| 27-may | **Gate Track A abierto.** Desde acá, todo PR de firmware pasa por vos antes de merge |

**Señal de éxito al 26-may:** al menos 3 PRs mergeados (1 por alumno), cada uno con banco documentado en `testing/TEST_LOG.md`, y el tablero de issues moviéndose.
