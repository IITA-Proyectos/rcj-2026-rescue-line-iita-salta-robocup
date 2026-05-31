**Benjamin — tu plan de trabajo está listo. Esto es lo primero que hacés HOY.**

> **DOCUMENTO HISTÓRICO (2026-05-18).** Estado de proyecto y régimen vigente: ver [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). Las fechas y pendientes de abajo pueden estar superados.
>
> **Nota (al 2026-05-31):** push libre de tu frente (docs/visión) **≤2026-06-11 sigue vigente** (freeze de código 2026-06-15), pero este mensaje es **foto del 18-may**. Es el resumen de `programa-benjamin-rpi-hardware.md`.

Tu frente: **RPi/hardware + sos el GATE de banco de todo el equipo (Track B)**.

### Lo primero, HOY, sin el robot
**#108 — el agujero #1 de la RPi: no existe auto-restart del proceso.** Si `Main.py` crashea en competencia, la Pi queda ciega para siempre. En tu doc está lista para revisar:
1. La unit `systemd` `robot.service` (`Restart=always`) completa.
2. El `try/except Exception` global + `if __name__ == "__main__"` (hoy no existe) que manda `speed=0` al Teensy antes de reintentar.
Se prueba **sin el robot**, con `kill -9` al proceso y verificando que vuelve en ≤5 s.

En paralelo:
- **#68**: `requirements.txt` pineado (tu doc trae el comando `pip freeze` para sacar las versiones reales en la Pi).
- **#66**: `send_frame_safe()` con clamp + `try/except` (el `flush()` actual puede colgar el loop).

### Tu rol más importante: el protocolo de banco
Tu doc trae **5 tests de inyección de fallas codificados** (cámara/UART/kill/arranque) con PASS/FAIL y template para `TEST_LOG.md`. **Vos sos el gate**: ningún PR de firmware/visión (Laureano, Lucio) se mergea sin tu validación de banco. Montá ese protocolo esta semana — es lo que convierte "código escrito" en "8/10 probado".

### Tu plan completo
`project/backlog/staging/programa-benjamin-rpi-hardware.md` (661 líneas). **Te lo pasa Enzo.**

### Régimen
Track B — push libre hasta 2026-06-11. #108 es CRÍTICO, hacelo ya (no necesita robot).

> El código del doc es una PROPUESTA para que vos valides, adaptes y pruebes. Vos hacés el commit/PR.
