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
1. TRIAGE       → leer subsistema completo, listar findings con prioridad y reproducción
2. PROPONER     → 1 Issue por finding con plantilla audit-finding (causa, fix, test, riesgo)
3. VERIFICAR    → cada fix se mergea sólo con entrada en testing/TEST_LOG.md
```

### Prioridades

- **P0** — Riesgo de no completar una corrida (robot se cuelga, se va de la pista, no arranca).
- **P1** — Pérdida significativa de puntaje o comportamiento errático intermitente.
- **P2** — Robustez / mantenibilidad / calidad. No bloquea competencia pero queda como deuda.

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
# Listar issues abiertos por prioridad
gh issue list --label audit/p0 --state open
gh issue list --label audit/p1 --state open

# Crear issue desde plantilla
gh issue create --template audit-finding.yml

# Build firmware Teensy (requiere PlatformIO)
cd software/teensy/firmware && pio run

# Test rápido visión (RPi en LAN)
python software/raspberry/final_rpi/calibration.py
```

---

*Última actualización: 2026-05-09*
