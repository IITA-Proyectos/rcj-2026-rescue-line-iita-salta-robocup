## Resiliencia R-V03 — `camthreader` sin Lock: frame desgarrado/stale → decisiones sobre datos corruptos

> **DOCUMENTO HISTÓRICO (2026-05-18).** Estado de proyecto y régimen vigente: ver [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). Las fechas y pendientes de abajo pueden estar superados.
>
> **Nota (al 2026-05-31):** el push libre de visión **≤2026-06-11 sigue vigente** (freeze de código 2026-06-15), pero este doc es **foto del 18-may** y la numeración de issues/sprints es histórica; el seguimiento real vive en el estado vigente. **DUPLICADO:** gemelo de #113 en `programa-lucio-rpi-vision.md` y de Sprint 1 en `draft-issue-roadmap-confiabilidad-8.md`.

**Origen:** auditoría de resiliencia 2026-05-18 (commit `c42e535`). Track B (visión/RPi). Severidad: **CRÍTICA** (marcada CRÍTICA por el auditor de RPi; quedó sin issue propio en el primer lote).

### Modo de falla
`software/raspberry/final_rpi/camthreader.py:32-36`: el hilo `update()` escribe `self.grabbed, self.frame = self.stream.read()` (dos asignaciones) mientras `Main.py` llama `vs.read()` → `return self.frame` **sin ningún `threading.Lock`**. El frame leído por el main puede ser: (a) el anterior (stale), (b) un objeto a medio actualizar, (c) un `grabbed=True` que corresponde al frame siguiente. El guard de `None` (#65) NO detecta estos frames stale. La probabilidad de corrupción **crece con la carga de CPU** (más liberaciones de GIL en operaciones numpy) — justo cuando la Pi está caliente en competencia.

### ¿Se recupera solo HOY?
**NO.** El código asume que la asignación es atómica. Un frame corrupto pasa directo a `cv2.cvtColor`/`cv2.inRange` → puede tirar `cv2.error`/shape mismatch que mata el loop de línea (y sin systemd, #108, = proceso muerto).

### Qué falta para self-healing
1. `threading.Lock()` en `__init__`; adquirirlo en `update()` antes de la asignación y en `read()` antes de retornar (el lock se sostiene microsegundos, no afecta FPS).
2. Combinar con verificación de `self.grabbed` antes de asignar `self.frame` (evita propagar frame fallido).

### Test plan (banco)
`print(id(frame))` en el main loop durante 5 s bajo carga: sin lock aparecen IDs repetidos consecutivos (frame duplicado/stale); con lock se eliminan. Verificar que no baja el FPS.

**Régimen:** Track B (visión) — push libre ≤2026-06-11. Fix chico (~6 líneas). **Asignar:** @luciouriel2011 @benjaminvillagran @gviollaz.
