**Lucio — tu plan de trabajo está listo. Esto es lo primero que hacés HOY.**

> **DOCUMENTO HISTÓRICO (2026-05-18).** Estado de proyecto y régimen vigente: ver [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). Las fechas y pendientes de abajo pueden estar superados.
>
> **Nota (al 2026-05-31):** tu push libre (visión) **≤2026-06-11 sigue vigente** (freeze de código 2026-06-15), pero este mensaje es **foto del 18-may**. Es el resumen de `programa-lucio-rpi-vision.md`.

Tu frente: **visión RPi (Track B)** — quick-wins de resiliencia, todo se escribe HOY sin el robot.

### Lo primero, HOY (el de mayor impacto / menor riesgo)
**#110 — `cx_black` sin inicializar.** Es un crash **100% reproducible** (pasa siempre que hay zona verde sin línea negra abajo — escenario normal en competencia) y el fix es **1 línea**: inicializar `cx_black = width // 2` antes del bloque condicional (`Main.py` ~769-780), más un `try/except` en el loop de línea. Cero riesgo de romper el comportamiento normal.

Después, en orden:
2. **#65 + #113 juntos** (un solo PR): `vs.read()` puede devolver `None` + `camthreader` sin `threading.Lock` → frame stale/desgarrado.
3. **#111**: `infer_thread` sin `try/except` → deadlock silencioso en rescate.
4. **#64**: ojo — el hallazgo del análisis es que `Main.py` **ya tiene** el guard correcto; el bug real está en `calibration.py`. Está explicado en tu doc.

**Criterio de hecho por PR:** corre sin crash en el escenario de falla + FPS no baja + entrada en `testing/TEST_LOG.md` (Benjamin valida en banco).

### Tu plan completo
`project/backlog/staging/programa-lucio-rpi-vision.md` (651 líneas: código antes→después por tema, orden, validación). **Te lo pasa Enzo.**

### Régimen
Track B — push libre hasta 2026-06-11. Pero #110 es 1 línea que mata un crash seguro: hacelo YA, no esperes.

> El código del doc es una PROPUESTA para que vos valides, adaptes y pruebes. Vos hacés el commit/PR.
