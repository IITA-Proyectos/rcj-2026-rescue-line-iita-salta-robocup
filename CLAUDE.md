# CLAUDE.md — Contexto para asistentes de IA

Este archivo es leído automáticamente por Claude Code y otros asistentes que abran este repo. Define **el contexto técnico, las reglas de trabajo y el workflow de auditoría** del equipo IITA Salta para RoboCup Junior Rescue Line 2026.

> ⚠️ **Este es código rumbo a un mundial.** No hay rollback. Antes de proponer un cambio, leé las secciones **Reglas de oro** y **Workflow de auditoría**.

---

## Stack y arquitectura

| Subsistema | Hardware | Lenguaje | Toolchain | Punto de entrada |
|---|---|---|---|---|
| Firmware control | Teensy 4.1 | C++ | PlatformIO | [`software/teensy/firmware/src/main.cpp`](software/teensy/firmware/src/main.cpp) |
| Visión | Raspberry Pi 4B | Python 3 | OpenCV + YOLO (ONNX/NCNN/TFLite) | [`software/raspberry/final_rpi/Main.py`](software/raspberry/final_rpi/Main.py) |
| Comunicación | UART 115200 baud | — | Serial | Protocolo `[255, speed, 254, angle, 253, green, 252, silver]` |

**División de responsabilidades:**
- **Teensy** → control de motores con encoders, PID, lectura de ToF (VL53L0X), ultrasonidos (NewPing), IMU (BNO055), sensor de color, accionamiento de pinza/servos.
- **Raspberry Pi** → visión, detección de víctimas, detección de zona de evacuación con YOLO, decisión estratégica de alto nivel.
- **Comms** → la RPi manda comandos a la Teensy. La Teensy es "tonta" y reactiva.

---

## Reglas de oro (NO negociables)

1. **No hacer push directo a `main`.** Toda mejora pasa por PR con al menos un review.
2. **Todo cambio se vincula a un Issue.** No hay PRs huérfanos.
3. **Antes de mergear un fix de firmware, probar en banco.** Mínimo: el robot enciende, los motores responden, no hay watchdog reset. Resultado documentado en [`testing/TEST_LOG.md`](testing/TEST_LOG.md).
4. **No tocar lo que funciona "porque suena mejor".** Si una mejora teórica rompe un subsistema validado, se revierte. Los alumnos llevan meses tuneando — respetá su trabajo.
5. **Idioma fuente: español.** Todo PR, issue, doc, comentario de código y commit message va en español. ⏸ **La autotraducción de `docs/en/` está SUSPENDIDA desde el 2026-08-02** (no hay documentación rumbo a campeonato internacional). `docs/en/` quedó **congelada** en su último estado: no la edites a mano y no confíes en que esté al día — la fuente de verdad es `docs/es/`. Para reactivar la traducción automática, seguí las instrucciones al tope de [`.github/workflows/translate-docs.yml`](.github/workflows/translate-docs.yml).
6. **Hardware versionado.** Cambios físicos van en `hardware/cambios_de_hardware.md` con fecha y razón.
7. **Conventional Commits** en español: `fix(teensy): agregar volatile a contadores de encoder`, `feat(rpi): cargar YOLO una sola vez al arranque`.

---

## Workflow de auditoría (vibe reviewing)

Cuando alguien pide "revisá X" o "auditá X", el flujo es:

```
1. TRIAGE       → leer subsistema completo, listar OBSERVACIONES con riesgos y tiempo
2. PROPONER     → 1 Issue por observación, framing TEMA A ANALIZAR (no directiva de fix)
3. DECIDIR      → el equipo evalúa cada tema y decide: tomar / posponer / descartar
4. VERIFICAR    → si se toma, el fix se mergea sólo con entrada en testing/TEST_LOG.md
```

### 📌 Filosofía: TEMAS A ANALIZAR, no directivas de fix

El equipo lleva meses afinando el robot. Lo que parece bug puede ser **workaround intencional** o algo conocido que ya decidieron no priorizar. Toda observación va con tres campos obligatorios:

1. **Riesgo de NO cambiar nada** — qué pasa en competencia si se deja así (alto/medio/bajo + escenario).
2. **Riesgo de cambiarlo** — probabilidad de regresión, qué se toca, plan de rollback.
3. **Estimación de tiempo realista** — incluyendo test en banco y en pista, no sólo el typing.

Ver plantilla `.github/ISSUE_TEMPLATE/audit-finding.yml`.

### Prioridades (orientativas, opcionales)

- **P0 (`priority/high`)** — Riesgo "alto" de no cambiar: afecta cada corrida o escenario típico.
- **P1 (`priority/medium`)** — Riesgo "medio": afecta en escenarios edge.
- **P2 (`priority/low`)** — Riesgo "bajo": deuda técnica sin impacto inmediato.

La prioridad **no obliga**. El equipo decide caso por caso con los riesgos y el tiempo en la mano.

### Skills disponibles

Este repo tiene 5 skills en `.claude/skills/`:

**Dirección del proyecto:**
- **[`rcj-coach-director`](.claude/skills/rcj-coach-director/SKILL.md)** — director técnico / coach. Prioriza, planifica la semana, asigna tareas, documenta decisiones, aplica el régimen de fases vigente (Track A firmware/comms: push cerrado, entra por gate de Enzo; Track B docs/visión: push libre hasta 2026-06-11; freeze de código 2026-06-15 — ver [docs/es/ESTADO-ACTUAL-2026-05-31.md](docs/es/ESTADO-ACTUAL-2026-05-31.md)). NO escribe código.

**Auditoría técnica:**
- **[`rcj-rescue-reviewer`](.claude/skills/rcj-rescue-reviewer/SKILL.md)** — orquestador. Decide qué subsistemas auditar y consolida findings.
- **[`teensy-firmware-auditor`](.claude/skills/teensy-firmware-auditor/SKILL.md)** — audita C++ Teensy (ISR, `volatile`, `delay()`, watchdogs, PID, race conditions).
- **[`rpi-vision-auditor`](.claude/skills/rpi-vision-auditor/SKILL.md)** — audita Python/OpenCV/YOLO (model loading, FPS, threading, calibración).
- **[`rpi-teensy-comms-auditor`](.claude/skills/rpi-teensy-comms-auditor/SKILL.md)** — audita el protocolo serial (framing, heartbeat, timeouts).

---

## Plantillas

- **Issues**: `.github/ISSUE_TEMPLATE/audit-finding.yml` — usar para todo finding nuevo.
- **PRs**: `.github/pull_request_template.md` — incluye Test Plan obligatorio.

---

## Fuente de verdad de findings: GitHub Issues

Los findings activos viven en **GitHub Issues** (label `priority/*`). **Antes de abrir un finding nuevo**, buscar en Issues con `gh issue list` (ver comandos abajo).

[`AUDIT-ACTION-PLAN.md`](AUDIT-ACTION-PLAN.md) quedó **archivado como histórico** (23-feb) y NO debe usarse para priorizar. El estado vigente del proyecto vive en [docs/es/ESTADO-ACTUAL-2026-05-31.md](docs/es/ESTADO-ACTUAL-2026-05-31.md) y en el informe director [docs/es/2026-05-31-informe-coach-auditoria-integral.md](docs/es/2026-05-31-informe-coach-auditoria-integral.md).

---

## Comandos útiles

```bash
# Listar issues abiertos por prioridad (P0 = priority/high, P1 = priority/medium, P2 = priority/low)
gh issue list --label priority/high --state open
gh issue list --label priority/medium --state open

# Buscar issues por subsistema
gh issue list --label subsystem/control --state all  # Teensy / motores / PID
gh issue list --label subsystem/vision  --state all  # RPi / YOLO / OpenCV
gh issue list --label subsystem/comms   --state all  # serial / protocolo

# Crear issue desde plantilla
gh issue create --template audit-finding.yml

# Build firmware Teensy (requiere PlatformIO)
cd software/teensy/firmware && pio run

# Test rápido visión (RPi en LAN)
python software/raspberry/final_rpi/calibration.py

# Ritual semanal del director (lunes a primera hora)
/coach-checkin
```

---

*Fuente de verdad del estado del proyecto (PRs mergeados, régimen de fases vigente, pendientes reales): [docs/es/ESTADO-ACTUAL-2026-05-31.md](docs/es/ESTADO-ACTUAL-2026-05-31.md).*

*Última actualización: 2026-05-31*
