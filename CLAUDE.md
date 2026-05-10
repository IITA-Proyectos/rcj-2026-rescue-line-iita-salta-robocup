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
5. **Idioma fuente: español.** Todo PR, issue, doc, comentario de código y commit message va en español. La carpeta `docs/en/` se autotraduce por CI (no editar a mano).
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

Este repo tiene 4 skills en `.claude/skills/` que orquestan la auditoría:

- **[`rcj-rescue-reviewer`](.claude/skills/rcj-rescue-reviewer/SKILL.md)** — orquestador. Decide qué subsistemas auditar y consolida findings.
- **[`teensy-firmware-auditor`](.claude/skills/teensy-firmware-auditor/SKILL.md)** — audita C++ Teensy (ISR, `volatile`, `delay()`, watchdogs, PID, race conditions).
- **[`rpi-vision-auditor`](.claude/skills/rpi-vision-auditor/SKILL.md)** — audita Python/OpenCV/YOLO (model loading, FPS, threading, calibración).
- **[`rpi-teensy-comms-auditor`](.claude/skills/rpi-teensy-comms-auditor/SKILL.md)** — audita el protocolo serial (framing, heartbeat, timeouts).

---

## Plantillas

- **Issues**: `.github/ISSUE_TEMPLATE/audit-finding.yml` — usar para todo finding nuevo.
- **PRs**: `.github/pull_request_template.md` — incluye Test Plan obligatorio.

---

## Documento vivo: AUDIT-ACTION-PLAN.md

[`AUDIT-ACTION-PLAN.md`](AUDIT-ACTION-PLAN.md) es la lista maestra curada de bugs. **Antes de abrir un finding nuevo**, verificar que no esté ya listado ahí. Bugs cerrados se mueven a la sección "Resueltos" con link al PR.

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
```

---

*Última actualización: 2026-05-09*
