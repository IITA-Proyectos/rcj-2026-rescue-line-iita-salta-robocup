## Resiliencia R-V01 — Sin auto-restart del proceso Main.py (RPi queda ciega para siempre si crashea)

**Origen:** auditoría de resiliencia 2026-05-18 (branch `feature/initialize-testing-log`, commit `c42e535`). Track B (visión/RPi). Severidad: **CRÍTICA**.

### Modo de falla
`Main.py` muere por cualquier excepción no capturada (≥4 paths confirmados: arranque module-level sin guarda, `cx_black` sin init, `ser.write` sin try/except, loop `esperando` sin try/except). **Búsqueda exhaustiva en el repo: NO existe `systemd`, `supervisor`, `rc.local`, `crontab` ni watcher de ningún tipo.** Si el proceso muere a mitad de corrida, la Pi queda ciega y nadie puede abrir una terminal en competencia.

### ¿Se recupera solo HOY?
**NO.** Si el proceso muere, muere para siempre hasta intervención manual. Esto convierte CUALQUIER crash en pérdida total de la corrida.

### Qué falta para self-healing
1. Unit `systemd` `/etc/systemd/system/robot.service` con `Restart=always`, `RestartSec=2`.
2. `try/except Exception` de último recurso alrededor del `while True` principal que loguee, mande `speed=0` al Teensy, y reintente.
3. `if __name__ == "__main__":` guard + init de hardware en función con retry.

> ⚠️ El equipo debe verificar si hay algo en el OS de la SD (fuera del repo). Si no, este es el agujero de auto-recuperación #1 de la RPi.

### Test plan (banco)
Matar `Main.py` con `kill -9` durante una corrida → verificar que vuelve solo y operativo en ≤5 s, con el Teensy habiendo recibido `speed=0` durante el gap.

**Régimen:** Track B (visión) — push libre ≤2026-06-11. **Asignar:** @luciouriel2011 @benjaminvillagran @gviollaz.
