**Laureano — tu plan de trabajo está listo. Esto es lo primero que hacés HOY.**

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
Track A — **push libre hasta 2026-05-26**, después gate de Enzo. Aprovechá esta ventana: lo de hoy (#60/#61/#112) es escribir, no necesita el robot. El banco (#53 heartbeat, #27 WDT) viene en Sprint 2.

> El código del doc es una PROPUESTA para que vos valides, adaptes y pruebes. Vos hacés el commit/PR — no está commiteado.
