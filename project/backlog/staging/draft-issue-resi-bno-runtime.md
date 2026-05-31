## Resiliencia R-T06 — BNO055 sin detección de fallo en runtime ni re-init automático (heading basura silencioso)

> **DOCUMENTO HISTÓRICO (2026-05-18).** Estado de proyecto y régimen vigente: ver [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). Las fechas y pendientes de abajo pueden estar superados.
>
> **Correcciones (al 2026-05-31):** régimen "Track A push libre ≤2026-05-26" SUPERADO → firmware/comms ya entra por **gate de Enzo** (ventana de push vencida). **DUPLICADO:** gemelo del tema #109 en `programa-laureano-teensy-resiliencia.md`. Estado real de los fixes de firmware: en PR #129 (OPEN, validar en banco).

**Origen:** auditoría de resiliencia 2026-05-18 (commit `c42e535`). Track A (control/firmware). Severidad: **CRÍTICA**.

### Modo de falla
`leer_yaw()`, `leer_pitch()`, `runAngle()`, `avance_recto()` llaman `bno.getEvent()` **sin verificar el retorno** (`software/teensy/firmware/src/main.cpp:436-449, 611-622`). Si el BNO055 pierde I2C en runtime (golpe, ruido EMI de motores en rampa, conector flojo), la lib Adafruit devuelve `0.0` o el último valor cacheado. El robot navega con heading basura **sin saberlo** — falla silenciosa, la peor clase en competencia (no se cuelga, hace lo incorrecto). `resetear_bno()` existe pero **nunca se invoca automáticamente** desde el loop.

### ¿Se recupera solo HOY?
**NO.** No hay verificación del retorno de `getEvent()`, no hay flag `bno_ok`, no hay detección de "heading congelado", `resetear_bno()` solo sería manual.

### Qué falta para self-healing
1. Verificar el `bool` que retorna `bno.getEvent()`; si falla → `bno_ok = false`.
2. Detección de "heading congelado": mismo valor por >500 ms con motores girando → sospechar sensor muerto.
3. Mientras `!bno_ok`: llamar `resetear_bno()` (con timeout, sin el `while(1)` actual), y degradar `runAngle()` a giro por tiempo en vez de converger por ángulo.

### Test plan (banco)
Con el robot girando (`runAngle`), desconectar SDA del BNO055 en caliente → debe detectar el fallo, intentar re-init, y completar el giro por tiempo (no girar infinito ni navegar con heading 0).

**Régimen:** ~~Track A (firmware) — push libre ≤2026-05-26~~ → **al 2026-05-31: firmware/comms con ventana de push vencida, entra por gate de Enzo.** **Asignar:** @Laumonteros @gviollaz.
