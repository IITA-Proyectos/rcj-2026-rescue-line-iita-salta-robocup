## Cluster Teensy / firmware — para Lautaro (Laureano Monteros, `Laumonteros`, codeowner firmware)

> Nota de nombres: **Lautaro = Laureano Monteros = `Laumonteros`** — misma persona, el del firmware Teensy.

**Fase:** 🟢 Fase 1 — push exhaustivo · **T–6 semanas a Incheon** · freeze el 2026-05-20 (3-4 días).

Lautaro: este issue junta tu frente de firmware Teensy — lo previo abierto + los hallazgos nuevos de la auditoría 2026-05-16 (branch `feature/initialize-testing-log`, commit `c42e535`). Formato de cada tema: riesgo-si-NO / riesgo-si-SÍ / tiempo / criterio de "hecho". Ver panorama completo en #103.

---

### 🔴 PRIORIDAD #1 — Re-aplicar los timeouts (CONFIRMADO revertidos)

Los issues **#59 / #60 / #61 / #62** tienen su fix **revertido en el código actual**:
- `5bac4a5 feat(teensy): timeouts implementados` los implementó.
- `cead75e fix(teensy): error de libreria claw.cpp` borró 181 líneas (incl. `priority_fix_flags.h`).
- Ningún commit posterior los restauró.

- **Riesgo si NO:** el equipo cree que están resueltos. En competencia, cualquiera de esas causas (encoder que no llega al target, sensor color colgado, fallo de init) **cuelga el robot sin recuperación** → LoP repetido (−5 c/u, tope −20).
- **Riesgo si SÍ:** medio — hay que primero entender el error de `claw.cpp` que forzó el revert, después re-aplicar incremental (un issue a la vez, con banco entre cada uno). NO re-aplicar los 181 líneas de golpe.
- **Tiempo:** ~3-4 h (diagnóstico claw.cpp + re-aplicación incremental + banco por cada uno).
- **Hecho:** #59/#60/#61/#62 con su fix vivo en `main`, cada uno con corrida de banco que reproduce el fallo y confirma el timeout + línea en `testing/TEST_LOG.md`.
- **Balde:** must — lo primero de la semana.

---

### A) Hallazgos PREVIOS de control ya con issue abierto (referencia — trabajar desde su issue)

- **#57** [P0] Zona rescate: ambas ramas rotan −90 en busca de pared. **must.**
- **#58** [P1] `case 12` cae al `case 14` por falta de `break` → `runAngle(180)` espurio. Fix: agregar `break;` entre líneas 1113-1115 (ojo: el `break` de la línea 1112 está dentro del `while` interno, no del `switch`). **must.**
- **#59/#60/#61/#62** — ver PRIORIDAD #1 arriba.
- **#67** [P2] `Moto::pulseCount` sin init en constructor → valor basura antes del primer reset. Fix 1 línea. **should.**

---

### B) Hallazgos NUEVOS de firmware (auditoría 2026-05-16)

#### TEMA T-A — `get_color()` bloquea sin timeout
- **Archivo:** `software/teensy/firmware/src/main.cpp:336-339`
- **Qué:** `while (!apds.colorDataReady()) { delay(5); }` sin timeout. Se llama **cada iteración** del loop de línea (main.cpp:887) y en evasión de obstáculo (951, 966). (Distinto del while que cubre #61.)
- **Riesgo si NO:** I2C flojo por vibración/rampa → `colorDataReady()` nunca devuelve true → **freeze permanente** del robot, sin recuperación.
- **Riesgo si SÍ:** muy bajo. Guardar `millis()` antes del while + `if ((millis()-waitStart)>50) return "Desconocido";`. Cambio atómico de 3 líneas en una función.
- **Tiempo:** ~10 min + 15 min banco.
- **Hecho:** desconectar SDA del APDS9960 con el robot corriendo → debe seguir avanzando en "Desconocido", no congelarse. Línea en TEST_LOG.
- **Balde:** must (confiabilidad alta, riesgo mínimo).

#### TEMA T-B — `taskDone` nunca se resetea a `false`
- **Archivo:** `software/teensy/firmware/src/main.cpp:59, 821, 900`
- **Qué:** `taskDone` sólo pasa a `true` en el handler de switch-off (821) y es la única condición que habilita el dispatch de acciones (900). Si el robot arranca sin pasar por el ritual switch-off → `taskDone=false` → **nunca entra al switch de acciones** (solo linetrack, ignora verde/obstáculo).
- **Riesgo si NO:** comportamiento errático según el orden de encendido. En competencia el juez puede no dar tiempo al ritual switch-off/on → el robot ignora todos los comandos de verde.
- **Riesgo si SÍ:** bajo-medio. Inicializar `taskDone=true` (línea 59) o setearlo en el bloque `startUp`. Verificar en banco que no rompe el ritual de arranque.
- **Tiempo:** ~15 min + 20 min banco.
- **Hecho:** encender y activar switch directamente sin ciclo switch-off previo → responde a comandos de verde. Línea en TEST_LOG.
- **Balde:** must (confiabilidad media, clase entera de bug errático).

#### TEMA T-C — `delay(10)` por iteración en `runDistance()`
- **Archivo:** `software/teensy/firmware/src/main.cpp:551, 575`
- **Qué:** `delay(10)` fijo por iteración en ambos loops de `runDistance` → control loop limitado a 100 Hz; el PID de posición responde a la mitad de lo que el hardware da. Durante esos 10 ms no se lee el switch ni `claw.update()`.
- **Riesgo si NO:** menos precisión en avances de 5-8 cm de la zona de rescate (recogida de pelota, posicionamiento de depósito) — donde cada cm cuesta puntos.
- **Riesgo si SÍ:** bajo. Quitar el `delay(10)` o bajarlo a 1 ms; reintegrar el timeout de #60 al mismo tiempo.
- **Tiempo:** ~20 min + 30 min banco (medir error a 5/10/20 cm con y sin delay).
- **Hecho:** error promedio de 5 corridas a 5/10/20 cm mejora medible. Línea en TEST_LOG.
- **Balde:** should (performance media; combinar con re-aplicación de timeout #60).

#### TEMA T-D — `runTime()` usa `unsigned long long` vs `millis()` `unsigned long` (menor)
- **Archivo:** `software/teensy/firmware/src/main.cpp:411-413`
- **Qué:** tipos mezclados; en Cortex-M7 los 64 bits no son atómicos (2 instrucciones de 32). Riesgo real bajo (en una competencia de días no hay overflow de 49 días; `startTime` se escribe una vez).
- **Riesgo si NO:** mínimo en práctica; queda como bug latente para futuros refactors.
- **Riesgo si SÍ:** muy bajo. Cambiar a `unsigned long` en 2 lugares; sin cambio observable.
- **Tiempo:** ~5 min + compilar con `-Wall -Wconversion`.
- **Hecho:** desaparecen los warnings de conversión implícita.
- **Balde:** nice-to-have (solo si sobra tiempo antes del freeze).

---

### NO quick-win de tu dominio (banco con cuidado o post-freeze)

- **FSM rescate llama `runDistance/runTime` bloqueantes** (relac. #59): `actualizarRescate()` se diseñó no-bloqueante pero `RESCATE_*_STEP4/STEP8` llaman a funciones bloqueantes que congelan el main loop por segundos (la garra no actualiza mientras avanza). Refactor a sub-FSM con `millis()`, 2-3 estados nuevos por secuencia. Alto payoff, **riesgo medio** — banco intensivo, evaluar si entra antes del 05-20 o `post-mundial`.

---

### Tu prioridad sugerida esta semana (antes del freeze 2026-05-20)

1. **Re-aplicar timeouts #59/#60/#61/#62** (PRIORIDAD #1 — diagnosticar claw.cpp primero, re-aplicar incremental).
2. **T-A `get_color()` timeout** + **T-B `taskDone`** + **#58 `break`** — 3 quick-wins de confiabilidad de bajo riesgo.
3. **T-C `delay(10)`** combinado con la re-aplicación del timeout de #60.
4. T-D y #67 si sobra tiempo (nice).

Regla de "hecho" transversal: **PR mergeado + 1 corrida de banco que lo valide + 1 línea en `testing/TEST_LOG.md`** (existe por PR #101). Banco obligatorio antes de mergear firmware (regla del repo).

*Auditoría asistida por Claude Code bajo supervisión de @gviollaz. Panorama de los 3 subsistemas en #103; cluster RPi/hardware en #104.*
