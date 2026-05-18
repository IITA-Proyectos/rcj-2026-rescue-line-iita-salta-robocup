# Auditoría de Resiliencia y Auto-Recuperación — RCJ 2026 IITA Salta

**Fecha:** 2026-05-18
**Branch/commit auditado:** `feature/initialize-testing-log` @ `c42e535`
**Método:** 4 auditores independientes en paralelo (firmware-Teensy, RPi-visión, comms-serial, arquitectura-FMEA) orquestados por la skill `rcj-rescue-reviewer`. Pedido del director: foco EXCLUSIVO en confiabilidad y auto-recuperación (no performance).

---

## Veredicto

> **Auto-recuperabilidad del sistema HOY: 2/10.** El robot NO se recupera solo de casi ninguna falla común de competencia. La mayoría lo dejan **descontrolado** (motores activos, fuera de pista) o **muerto silencioso**, sin posibilidad de intervención (no se puede tocar el robot durante la corrida).

Con la "arquitectura mínima de resiliencia" (3 palancas, ~medio día de trabajo) sube a **~6/10**. Con la capa de salud + degradación, **8/10**.

## Objetivo decidido (Gustavo, 2026-05-18)

**Objetivo para Incheon = 8/10 sólido y validado en banco. El tramo 8→10 es post-mundial.** Razón: rendimientos decrecientes brutales (2→6 medio día, 6→8 ~1 semana, 8→10 semanas); cada capa extra es código nuevo que toca sistemas validados (riesgo de regresión); el 8→10 es sobre todo *validación* (tiempo de banco que se necesita para puntuar); y 8→10 no pasa el filtro de fases del propio régimen. **Un robot 8/10 probado gana más corridas que un 10/10 teórico sin validar.** Decisión completa en `journal/decisiones/2026-05-18-objetivo-confiabilidad-8-incheon.md`. Plan de trabajo por sprints en **#114**.

---

## Meta-hallazgo (confirmado por los 4 auditores por separado)

Los timeouts/safeguards del commit `5bac4a5` (#60 runDistance, #61 sensor color, #62 init visible, drenaje serial en maniobras) **fueron revertidos por `cead75e`** (al arreglar un error de `claw.cpp` se arrastraron −181 líneas de resiliencia) y **nunca se restauraron**. El equipo hizo el trabajo correcto y lo perdió por accidente. El firmware en `c42e535` no tiene ninguna red de seguridad.

---

## Críticos de auto-recuperación (consolidado, deduplicado)

| # | Falla | Gatillo en competencia | ¿Se recupera solo HOY? | Issue |
|---|---|---|---|---|
| 1 | Sin heartbeat serial + sin failsafe | Cable USB-serial flojo / crash Python → Teensy repite último `speed/steer` para siempre | ❌ NO — descontrolado, fuera de pista | #53 |
| 2 | Sin Watchdog HW en Teensy | Cualquier cuelgue de SW deja motores activos | ❌ NO — solo switch físico | #27 |
| 3 | Sin auto-restart de Main.py | Proceso Python muere (≥4 paths) → Pi ciega | ❌ NO — sin systemd en el repo | #108 |
| 4a | runDistance sin timeout | Encoder muerto → avanza infinito | ❌ NO — timeout revertido | #60 |
| 4b | get_color/colorDataReady sin timeout | I2C colgado → Teensy congelada | ❌ NO — timeout revertido | #61 |
| 4c | runAngle sin timeout ni dreno serial | IMU ruidosa → gira infinito; kill-switch serial ignorado | ❌ NO — nunca tuvo fix | #112 |
| 5 | BNO055 sin detección de fallo runtime | Golpe/ruido I2C → navega con heading basura sin saberlo | ❌ NO — `resetear_bno()` nunca se llama sola | #109 |
| 6 | Reset Teensy (brown-out) sin resync | Stall 4 motores → reset → estados RPi/Teensy desfasados permanente | ❌ NO | #72 |
| 7 | `cx_black` sin inicializar | Verde sin línea negra abajo (escenario normal) → crash 100% reproducible | ❌ NO — mata el proceso | #110 |
| 8 | infer_thread sin try/except | Falla TFLite → thread muere → robot en búsqueda infinita | ❌ NO — sin respawn | #111 |

## Las 3 cascadas de fallo más peligrosas

1. **Cable UART flojo → descontrol total** (la más probable). Vibración suelta el conector → Teensy repite último comando → robot fuera de pista. **Instantáneo, sin detección.**
2. **APDS9960 cuelga I2C → robot congelado silencioso** (4-5 s). `get_color()` sin timeout bloquea todo el firmware; sin LED/buzzer (también revertido) no hay diagnóstico.
3. **Brown-out de motores → desincronización permanente**. Reset Teensy → estados RPi/Teensy desfasados → robot inerte sin diagnóstico hasta intervención manual = ronda perdida.

## Arquitectura mínima de resiliencia que falta (3 palancas de máximo impacto)

Consenso de los 4 auditores. ~medio día → sube de 2/10 a ~6/10:

1. **Heartbeat UART + safe-state 500ms en Teensy** (#53) → elimina la cascada #1 (la más probable).
2. **Restaurar timeouts revertidos #60/#61 + agregar #112 (runAngle) + WDT hardware #27** → elimina los cuelgues infinitos.
3. **systemd `Restart=always` para Main.py + try/except global** (#108) → crash de Pi pasa de catastrófico a recuperable en ~2s.

Capas que el sistema NO tiene y debería tener:
- **Capa 1 — Watchdog HW** (Teensy, `WDT_T4`, callback que para motores).
- **Capa 2 — Tabla de salud de subsistemas** (`bno_ok`, `apds_ok`, `tof_ok`, `encoder_stall` → decisiones degradadas seguras).
- **Capa 3 — Safe-state explícito** (motores 0, esperar recuperación, escape de FSM de rescate por timeout).

---

## Lente de coach (régimen + orden)

Casi todo es **Track A (firmware/comms)** → 🟢 push libre hasta **2026-05-26** (régimen vigente: ver memoria/SKILL). Los items 3/7/8 son Track B (RPi/visión) → push libre hasta **2026-06-11**.

**Reordena la prioridad del proyecto:** el issue #105 ("re-aplicar timeouts") deja de ser eso y pasa a ser **"construir la red de seguridad que no existe"** (heartbeat + WDT + timeouts + safe-state). Es lo más importante que el equipo puede hacer en los 8 días de Track A, **por encima de cualquier mejora de performance**.

Orden recomendado de ataque (Track A, antes del 26-may):
1. #53 heartbeat + failsafe (la palanca #1).
2. #27 WDT hardware (red de seguridad de todo).
3. #60 + #61 + #112 timeouts (restaurar + runAngle).
4. #109 BNO runtime + #72 resync post-reset.
Track B (hasta 11-jun): #108 systemd, #110 cx_black (quick, 100% reproducible), #111 infer_thread.

---

## Apéndice — Índice de hallazgos por subsistema (trazabilidad)

**Firmware Teensy (R-Txx):** R-T01 runAngle sin timeout→#112 · R-T02 get_color sin timeout→#61 · R-T03 sin WDT→#27 · R-T04/R-T11 lectura no atómica encoders · R-T05 runDistance sin timeout→#60 · R-T06 BNO runtime→#109 · R-T07 setup while(1) mudo→#62 · R-T08 serialEvent5 1 byte · R-T09 ToF sin timeout · R-T10 FSM rescate sin escape (tiemporescate muerto) · R-T12 case12 fall-through→#58 · R-T13 runTime tipo ull · R-T14 nonBlockingDelay · R-T15 apds.enableColor post-fallo.

**RPi visión (R-Vxx):** R-V01 sin systemd→#108 · R-V02 arranque sin guarda · R-V03 camthreader sin Lock · R-V04 infer_thread sin except→#111 · R-V05 restart cámara sin verificar · R-V06 busy-loop cámara muerta · R-V07 ser.flush() puede colgar · R-V08 cx_black sin init→#110 · R-V09 loop esperando sin except · R-V10 estado inconsistente post-recovery · R-V11 infer_thread zombie→#111 · R-V12 tracker sin cota · R-V13 sin `__main__` guard · R-V14 calibration sin headless · R-V15 requirements sin pin→#68.

**Comms (R-Cxx):** R-C01 sin heartbeat→#53 · R-C02 runAngle deadlock IMU→#112 · R-C03 saturación buffer + bytes debug→#63/#70 · R-C04 desync por byte debug→#74 · R-C05 reset Teensy sin resync→#72 · R-C06 runAngle sin dreno serial→#63 · R-C07 sin enforcement contrato rangos→#76 · R-C08 ser.read timeout (mitigado #73) · R-C09 ser.write sin except→#66 · R-C10 startup buffer no limpiado→#72 · R-C11 get_color deadlock→#61.

**FMEA arquitectónico:** 10 SPOF mapeados (UART, BNO, proceso Python, APDS, cámara, encoders, runAngle, bus I2C compartido, infer_thread, brown-out). 15 modos de falla tabulados. 3 cascadas. Score 2/10.

---

*Auditoría asistida por Claude Code (orquestador `rcj-rescue-reviewer` + 4 subagentes) bajo supervisión de @gviollaz. Los reportes completos de cada auditor quedaron en el log de la sesión; este documento es el consolidado trazable.*
