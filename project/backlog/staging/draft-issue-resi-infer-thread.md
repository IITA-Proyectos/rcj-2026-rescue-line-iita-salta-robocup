## Resiliencia R-V04/R-V11 — `infer_thread` sin try/except: deadlock silencioso en modo rescate

**Origen:** auditoría de resiliencia 2026-05-18 (commit `c42e535`). Track B (visión/RPi). Severidad: **CRÍTICA**.

### Modo de falla
`software/raspberry/final_rpi/Main.py:452-503`: `infer_thread()` no tiene `try/except` alrededor de la inferencia. Si `interpreter.invoke()` tira excepción (OOM de TFLite, shape mismatch por frame raro, RuntimeError), el hilo **muere silenciosamente**. `main_loop()` saca `queue.Empty` cada 250 ms; `capture_thread` se bloquea en `frame_q.put()` (bloqueante, `MAX_QUEUE=2`). Deadlock de 3 hilos: capture bloqueado, infer muerto, main en spin. El robot manda `speed=10, angle=90` (búsqueda) **indefinidamente**. Además (R-V11): en shutdown, el sentinel `None` puede ser consumido por el drain antes que `infer_thread` lo lea → thread zombie que corrompe el `interpreter` compartido en el próximo ciclo de rescate.

### ¿Se recupera solo HOY?
**NO.** No hay `tinf.is_alive()` check, no hay respawn, no hay sentinel garantizado.

### Qué falta para self-healing
1. `try/except` dentro de `infer_thread` que ponga un resultado vacío/sentinel en `result_q` en vez de morir.
2. `tinf.is_alive()` periódico en `main_loop` → si muerto, parar y relanzar la sesión de rescate.
3. `frame_q.get(timeout=X)` (no `get()` sin timeout) + sentinel `None` garantizado en el `finally`.

### Test plan (banco)
Inyectar una excepción forzada en `interpreter.invoke()` (o pasar un frame de shape inválido) → verificar que el sistema detecta el hilo muerto, lo relanza, y vuelve a inferir en ≤2 s (no queda en búsqueda infinita).

**Régimen:** Track B (visión) — push libre ≤2026-06-11. **Asignar:** @luciouriel2011 @benjaminvillagran @gviollaz.
