**Laureano — tu plan de trabajo está listo. Esto es lo primero que hacés HOY.**

> **DOCUMENTO HISTÓRICO (2026-05-18).** Estado de proyecto y régimen vigente: ver [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). Las fechas y pendientes de abajo pueden estar superados.
>
> **Correcciones (al 2026-05-31):** "Track A push libre hasta 2026-05-26" SUPERADO → firmware ya entra por **gate de Enzo** (freeze de código 2026-06-15). Si tu trabajo toca el **lazo de control / PID**, aplica **#121/B1**: motores DFRobot FIT0441 con PWM invertido (`255 - _pwmVal` correcto a nivel HW); el problema es el lazo, NO el signo. Es el resumen de `programa-laureano-teensy-resiliencia.md`.

Tu frente: **firmware Teensy / red de seguridad (Track A)** — es la prioridad #1 técnica del proyecto rumbo a Incheon (roadmap #114).

### Lo primero, HOY, sin el robot enfrente
**Recuperar los timeouts #60 y #61.** No los tenés que diseñar — **ese código ya existió** en el commit `5bac4a5` y se perdió por accidente en `cead75e`. En tu plan detallado está recuperado y adaptado a `c42e535`, listo para que lo revises:

```
git show 5bac4a5 -- software/teensy/firmware/src/main.cpp
```

1. Revisá el código propuesto en tu doc, adaptalo a lo que veas en el hardware.
2. Después seguí con **#112** (timeout + dreno serial en `runAngle()` — ese sí es nuevo, también está escrito en tu doc).
3. **Criterio de hecho:** PR con #60/#61 que **compila** + plan de banco escrito (validación viene después con Benjamin).

### Tu plan completo
`project/backlog/staging/programa-laureano-teensy-resiliencia.md` (865 líneas: código por tema, orden de ataque, validación en banco, checklist). **Te lo pasa Enzo.**

### Régimen
~~Track A — **push libre hasta 2026-05-26**, después gate de Enzo.~~ → **Al 2026-05-31: firmware con ventana de push vencida, ya entra por gate de Enzo** (freeze de código 2026-06-15). Lo de #60/#61/#112 es escribir, no necesita el robot. El banco (#53 heartbeat, #27 WDT) viene después.

> El código del doc es una PROPUESTA para que vos valides, adaptes y pruebes. Vos hacés el commit/PR — no está commiteado.
