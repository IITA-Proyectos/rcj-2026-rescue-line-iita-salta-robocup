# ESTADO ACTUAL DEL PROYECTO — RCJ Rescue Line 2026 · IITA Salta

> **FUENTE DE VERDAD ÚNICA + MAPA DE DOCUMENTACIÓN.** Esta es la foto vigente de régimen, fechas, estado de `main` y correcciones factuales al **2026-05-31**, y el índice de toda la documentación. **Si cualquier otro doc te contradice en fechas, régimen de fases o estado de PRs, gana este archivo** (los demás son fotos de un momento y deben leerse como históricos). Si no sabés dónde mirar, empezá acá.

**Fecha:** 2026-05-31 · **Verificado a mano contra `origin/main`** · **Mantiene:** Gustavo Viollaz (Director).
**Mundial:** RoboCup Junior Rescue Line — Incheon, Corea — **30-jun a 06-jul-2026** (~30 días / **~4,3 semanas** desde hoy).
**Informe completo del director para el coach:** [`2026-05-31-informe-coach-auditoria-integral.md`](2026-05-31-informe-coach-auditoria-integral.md).

---

## 1. Estado al 2026-05-31

**YA mergeado en `main` (tip `315e338`):**

- **PR #101** — `TEST_LOG` inicializado. El archivo existe en `main` pero **vacío de datos reales**: las 2 corridas reales (T-001 batería/odometría, T-002 = **91,33 FPS** medidos, ambas n=1) viven **sin mergear** dentro de PR #129.
- **PR #119** — fix del nombre **Laureano** (era typo histórico "Lautaro" → es **Laureano Monteros**).
- **PR #100** — skill `rcj-coach-director` + las 26 auditorías + el informe del director 31-may en `docs/es/`.

**PENDIENTE real:**

- **PR #129 — OPEN.** Código del equipo (**+5707 / −506, 39 archivos, 0 reviews**): fixes B1–B10 + TDP + assets. **Hay que PARTIRLO y validarlo en banco, NO mergearlo a ciegas.** Plan: PR-código (drivebase, `main.cpp`, `Main.py`, systemd, `priority_fix_flags.h`) → mergear **primero con sesión de banco**; PR-TDP → después. Verificado a mano: el PID saturado sigue vivo en `drivebase.cpp:50` y `priority_fix_flags.h` **no existe** en `main`. **Mientras #129 esté abierto, el robot que viaja tiene los bugs B1–B10 vivos.**

> Corolario: todo doc que marque #100/#101/#119 como "pendientes de merge" está **desactualizado** — ya están en `main`.

---

## 2. Régimen de fases VIGENTE (autoritativo)

Del informe del director 31-may. **Reemplaza** a TODAS las versiones previas (2 fases / 3 fases / track-dual / extensión +7 días).

| Frente | Régimen vigente |
|---|---|
| **Firmware / comms (ex-"Track A")** | La ventana de push libre **YA VENCIÓ.** Todo entra por **review / gate de Enzo.** |
| **Docs / visión (ex-"Track B")** | **Push libre hasta 2026-06-11.** Desde el 12-jun, gate de Enzo. |
| **Freeze de código** | **2026-06-15.** |
| **Logística pura (cero código)** | Última semana: **22–29 jun.** |

> **Fechas HISTÓRICAS superadas** (no usar como vigentes): "push libre hasta 26-may", "freeze 20-may", "Track A push ≤05-26", "T-6 / T-7 semanas", "hoy 2026-05-18", "45 días", y cualquier fecha de mayo presentada como futura. Hoy es **31-may**.

**Reglas de trabajo nuevas (no negociables, desde hoy):** (1) lo que no está en `main` no existe; (2) ningún merge sin `APPROVED` formal, PRs **<400 líneas** y de un solo dominio; (3) ningún fix de firmware se mergea sin su entrada en `TEST_LOG`; (4) cada alumno escribe CÓDIGO de su subsistema cada semana; (5) recortar scope (sin finales de carrera, ESP32 ni Technical Challenges hasta after-Incheon).

---

## 3. Mapa de documentación

Tabla "documento → qué es → vigente/histórico → dónde está". **Si dos docs se contradicen, gana este archivo + el informe director del 31-may.**

| Documento | Qué es | Estado | Dónde |
|---|---|---|---|
| **Este archivo** | Fuente de verdad + mapa de docs | 🟢 **VIGENTE** | `docs/es/ESTADO-ACTUAL-2026-05-31.md` |
| **Informe Director para Enzo (31-may)** | Síntesis ejecutiva de la auditoría integral: semáforo por frente, 5 riesgos P0, plan por semanas, reglas nuevas, 2 simulaciones SuperTeam | 🟢 **VIGENTE** | `docs/es/2026-05-31-informe-coach-auditoria-integral.md` (+ PDF `2026-05-31-Informe-Director-para-Enzo.pdf`) |
| **26 reportes de auditoría integral** | 22 análisis de subsistema (firmware, visión, comms, hardware, doc, estrategia, equipo, SuperTeam) + 4 informes (3 por integrante + 1 director). Respaldo del informe 31-may | 🟢 **VIGENTE** (detalle de respaldo) | `project/backlog/staging/auditoria-integral-2026-05-18/` |
| **Índice de propuestas de código** | Mapa navegable de todos los snippets/código ejemplo por persona/subsistema, con la corrección del PID destacada | 🟢 **VIGENTE** | `docs/es/propuestas-codigo/README.md` |
| **Propuestas de código / programas por persona** | Planes de trabajo por integrante (`programa-laureano-*`, `-lucio-*`, `-benjamin-*`, `-enzo-*`), drafts de Issues (`draft-issue-*`), mensajes (`msg-*`), agenda W20 | 🟡 Insumo de trabajo (código propuesto, no del robot) | `project/backlog/staging/` (indexados en `docs/es/propuestas-codigo/`) |
| **Skill coach-director** | Director técnico / coach: prioriza, agenda, asigna, documenta decisiones. Aplica el régimen de §2. No escribe código | 🟢 **VIGENTE** (ya apunta a este doc) | `.claude/skills/rcj-coach-director/SKILL.md` |
| **Skills de auditoría (4)** | `rcj-rescue-reviewer` (orquestador), `teensy-firmware-auditor`, `rpi-vision-auditor`, `rpi-teensy-comms-auditor` | 🟢 Vigentes | `.claude/skills/` |
| **TEST_LOG** | Bitácora de tests de banco (evidencia citable para la rúbrica TDP) | 🟢 Vigente pero **VACÍO** (datos reales en PR #129) | `testing/TEST_LOG.md` |
| **AUDIT-ACTION-PLAN.md** | Lista vieja de "bugs críticos" generada por IA (feb-2026) | 🔴 **ARCHIVADO / obsoleto** (ya banner-eado, con la corrección del PID) | `/AUDIT-ACTION-PLAN.md` (raíz) |
| **Análisis tempranos 09/10-may** | `analisis-*.md`, `informe-coaching-repo.md`, `triage-issues-2026-05-10.md`, `analisis-documentacion-rubricas-2026-05-10.md`, etc. | 🟠 **HISTÓRICO** (foto de may-9/10) | `docs/es/` |
| **Diseño/plan de la skill coach (10-may)** | `2026-05-10-coach-director-skill-plan.md`, `2026-05-10-rcj-coach-director-design.md` | 🟠 Histórico (diseño) | `docs/es/` |
| **Análisis resiliencia / correctitud (18-may)** | `2026-05-18-auditoria-resiliencia.md`, `2026-05-18-analisis-correctitud-oportunidades.md` | 🟠 Histórico (insumo de la integral) | `docs/es/` |
| **Journal / decisiones** | Check-in semanal W20 + decisión "objetivo confiabilidad 8/10" | 🟡 Vigente (registro) | `journal/2026-W20-checkin.md`, `journal/decisiones/` |
| **CLAUDE.md / README / REFERENCE** | Contexto técnico para IA + stack + reglas de oro | 🟢 Vigente (CLAUDE.md ya apunta a este doc) | raíz del repo |
| `docs/en/**` | Traducción automática por CI — ⏸ **SUSPENDIDA el 2026-08-02** (no hay doc rumbo a mundial). Reactivación: ver cabecera de `.github/workflows/translate-docs.yml` | 🟠 **CONGELADA** en su último estado — no editar a mano, no asumir que está al día | `docs/en/` |

> **Dónde está cada cosa (para no confundirse):**
> - **El índice de código** vive en `docs/es/propuestas-codigo/README.md` (mapa navegable). **Los archivos de código** (`programa-*.md` por persona) viven en `project/backlog/staging/` — el índice apunta a ellos.
> - Los **"drafts históricos"** (agenda, mensajes, drafts de issues) están bajo `project/backlog/staging/`, no en un `staging/` a nivel raíz.

---

## 4. Correcciones factuales clave (NO seguir el dato viejo)

Verificadas por la auditoría integral del 31-may. **Prevalecen** sobre cualquier doc histórico.

**4.1 PID / PWM (#121 / B1) — el "fix de signo" es INCORRECTO.** Los motores son **DFRobot FIT0441 con PWM INVERTIDO** → a nivel hardware `255 - _pwmVal` es **correcto**. El "fix" naïve de cambiar el signo (`analogWrite(_pwmVal)`) está **mal y empeora el robot**. El problema real es el **lazo de control** (PID en modo **DIRECT** + `ki=22` dominante + `kp=0` → queda **saturado a fondo**): es un **rediseño de lazo, NO un quick-win de signo.** Todo doc que recomiende "cambiar el signo del PWM" debe corregirse con esta reinterpretación.

**4.2 Clases YOLO (#120 / B3) — NO están invertidas (matizado).** Las clases del modelo **coinciden** con `metadata.yaml`. Lo que estaba invertido eran nombres de **sub-estados de depósito**. Corregir donde se afirme tajante "clases YOLO invertidas".

**4.3 Rescate corre por código fantasma.** La FSM no-bloqueante de pinza (`actualizarRescate()`, `claw.cpp`) está **100% muerta**; corre la vieja secuencia **inline bloqueante** (`main.cpp:1137-1186`). El equipo tunea código que no se ejecuta.

**4.4 ESP32 NO está incorporado** (ni HW ni SW): es solo propuesta. Ojo: el firmware **ya remapeó pines** (BUZZER 35→31, LED 34→30) para una ESP32 que nunca se montó → estado inconsistente.

**4.5 Fechas vencidas.** Cualquier doc que diga "push libre hasta 26-may", "freeze 20-may", "T-7/T-6 semanas", "hoy 2026-05-18", etc. está **desactualizado**. Hoy es **31-may** (vale §2).

**4.6 PRs ya en `main`.** `#100` / `#101` / `#119` marcados "sin mergear" → ya están en `main` (ver §1).

---

## 5. Equipo y los 5 riesgos P0

**Equipo (3 alumnos):**

| Persona | GitHub | Rol |
|---|---|---|
| **Laureano Monteros** | `@Laumonteros` | Firmware Teensy (owner) |
| **Lucio Saucedo** | `@luciouriel2011` | Visión RPi (owner) |
| **Benjamin Villagran** | `@benjaminvillagran` | RPi + hardware + banco |
| **Enzo Juarez** | `@enzzo19` | Coach |
| **Gustavo Viollaz** | `@gviollaz` | Director |

> No existe "Lautaro" — es typo histórico de **Laureano**.

**Los 5 riesgos P0 (del informe 31-may):** (1) **PR #129 no se mergea** → el robot que viaja tiene B1–B10 vivos; (2) **bus-factor = 1** (Benjamin = 100% del código del último mes) → no podrán debuggear en el pit; (3) **documentación de jurado en cero** (TDP ~6-12/102 · Poster 0/18 · Video 0/24), `TEST_LOG` vacío; (4) **comms sin red de seguridad** (sin heartbeat, el Teensy nunca emite el handshake 0xFA, sin WDT) → un cuelgue deja el robot inerte; (5) **el riesgo #1 no es técnico**: es de **proceso, bus-factor y documentación** (cerrar = mergear + repartir + documentar).

---

## 6. Dónde mirar según tu rol

- **Enzo (coach):** leé el **Informe Director 31-may** (`docs/es/2026-05-31-informe-coach-auditoria-integral.md`) — ahí están el plan por semanas, las 3 cosas que más mueven la aguja, las reglas nuevas y las 2 simulaciones SuperTeam. Para priorizar/agendar, usá la skill `rcj-coach-director`. Aplicá el régimen de §2 (Track A cerrado, Track B hasta 11-jun, freeze 15-jun).
- **Laureano (firmware Teensy):** tu informe es `auditoria-integral-2026-05-18/INFORME-INTEGRANTE-laureano.md` + el detalle en `teensy-01-drivebase-pid.md` … `teensy-05-serial-teensy.md`. **Foco inmediato: #115 (recuperar TUS timeouts de `ec8e6ab`, que quedó fuera de `main`).** El PID (#121) es **rediseño de lazo, no cambio de signo** (ver §4.1).
- **Lucio (RPi visión):** tu informe es `INFORME-INTEGRANTE-lucio.md` + `rpi-01-vision.md` / `rpi-02-decision.md`. **Foco: medir `out.shape` del TFLite (#124/B7 — define si el rescate funciona) y traer tu TDP del Drive al repo (#46).**
- **Benjamin (RPi + hardware + banco):** tu informe es `INFORME-INTEGRANTE-benjamin.md` + `hw-01/02-*.md` y `rpi-03-comms-threading.md`. **Foco: partir PR #129 y mergear lo seguro con banco; completar el `TEST_LOG` (~1h de banco).**
- **Cualquiera, antes de empezar:** mirá **este archivo** y **CLAUDE.md** (reglas de oro). Si vas a abrir un finding, no dupliques: revisá los issues y la auditoría integral primero.

---

*Mantener ESTE documento (y solo este) como la foto vigente. Los docs en `project/backlog/staging/` y los `docs/es/analisis-*` son trazabilidad histórica de findings — no se borran, pero apuntan acá para el estado real.*
