## Resiliencia R-T01/R-C02 — `runAngle()` sin timeout ni dreno serial: deadlock permanente por IMU

**Origen:** auditoría de resiliencia 2026-05-18 (commit `c42e535`). Track A (control/firmware). Severidad: **CRÍTICA**. Nuevo: los #60/#61 cubren `runDistance`/`colorDataReady`; **`runAngle` nunca tuvo fix, ni siquiera en el revertido `5bac4a5`**.

### Modo de falla
`software/teensy/firmware/src/main.cpp:434-529`: `runAngle()` corre un `while(true)` que solo sale si `fabs(error) <= 1.0` o `digitalRead(32) == 1` (switch físico). **Sin timeout de tiempo.** Si el BNO055 devuelve ángulo constante/ruidoso (I2C colgado, ruido EMI en rampa), `error` nunca converge → el robot **gira indefinidamente con motores a tope**. Además, `serialEvent5()` NO se llama dentro de `runAngle()`: el kill-switch serial (`0xFF` de la RPi) queda en el buffer sin procesarse → la RPi **no puede cancelar el giro**.

### ¿Se recupera solo HOY?
**NO.** Único escape = switch físico (intervención humana). Sin timeout, sin dreno serial, sin detección de no-convergencia.

### Qué falta para self-healing
1. Timeout de pared: `unsigned long start=millis()` antes del while; `if (millis()-start > maxMs) break;` con `maxMs` = 3× el tiempo estimado para el ángulo pedido.
2. Llamar `serialEvent5()` dentro del while; si llega `0xFF` → `break` (la RPi puede abortar el giro).
3. Detección de no-convergencia: si `error` no mejora en N iteraciones → declarar IMU sospechoso, salir por tiempo.

### Test plan (banco)
Forzar `runAngle(30, 90)` y desconectar el BNO en caliente → el robot debe terminar el giro por timeout (no girar infinito) y responder a un `0xFF` de la RPi durante el giro.

**Régimen:** Track A (firmware) — push libre ≤2026-05-26. Combinar con la re-aplicación de #60/#61 (#105). **Asignar:** @Laumonteros @gviollaz.
