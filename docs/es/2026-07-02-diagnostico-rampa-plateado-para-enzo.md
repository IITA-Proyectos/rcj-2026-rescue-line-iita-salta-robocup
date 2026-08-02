# Diagnóstico técnico — Robot NO sube rampas / NO detecta plateado

**Fecha:** 2026-07-02
**Contexto:** primera pasada en pista. Se observaron 2 problemas:
1. El robot **no sube bien las rampas**.
2. El robot **no ingresa a la zona de rescate / no detecta la línea plateada**.

**Alcance:** análisis 100 % de software (firmware Teensy + visión RPi). El testing en banco lo cierra el equipo.

> **Cómo leer esto:** cada causa tiene su evidencia `archivo:línea`. Distingo lo **confirmado en código** de lo que **falta confirmar en banco**. Las líneas citadas son del **firmware que corrió hoy** (ver punto siguiente), no del repo.

---

## 0) OJO: la versión que corrió hoy NO es la del repo

El `main.cpp` que se está flasheando es **más nuevo** que el del repo. Diferencias que importan para estos dos problemas:

- **Velocidad en rampa:** repo `pitch>10 → 30/25` ; **actual `pitch>3.9 → 45/40`**.
- **Anti-atasco (loma de burro):** en el repo **no existe**; en el actual está agregado (`chequearAtasco` / `recuperarAtasco`).
- **`accionNegro`:** reescrito en el actual (se queda quieto leyendo serial).

Todo lo de abajo es sobre la **versión actual**. Conviene commitear esa versión al repo para que quede una sola fuente de verdad.

---

# PROBLEMA 1 — No sube las rampas

Tres mecanismos de software, **todos confirmados en código**, que se combinan. Ordenados por probabilidad de ser la causa dominante.

## CR-A — La rampa quizá ni se detecta (o se detecta errática)
Si `pitch > 3.9` no se cumple, **todo lo demás queda inerte**: el robot corre la rampa a 40 RPM tratándola como llano.

- **Umbral de un solo signo (falta `fabs`):** `if (pitch > 3.9)` en `ajustarVelocidadPorPendiente`. Si el montaje da pitch **negativo** al subir, nunca dispara.
- **Posible eje EQUIVOCADO del BNO (load-bearing):** `pitch = event.orientation.y` en `leer_pitch()`. En la convención Adafruit BNO055 (NDOF) `orientation.y` suele ser **roll**, y `orientation.z` el **pitch**. Puede estar leyendo el eje que no es. → **FALTA CONFIRMAR EN BANCO.**
- **Sin offset de montaje ni histéresis:** si el robot en llano ya marca ~3-4°, roza el umbral; y sin banda muerta conmuta 40/45 con el ruido del BNO justo en el borde de la rampa (donde más par se necesita).

## CR-B — El "boost" de rampa es casi nulo y en curva desaparece
- 45 vs 40 RPM = **+12 %**, insuficiente. Y es **setpoint de RPM del PID, no PWM**: el PID ya intentaba mantener RPM en llano; pedirle 5 RPM más no es "más fuerza" directa.
- El parámetro `velocidadBase` es **código muerto**: `ajustarVelocidadPorPendiente(45)` ignora el 45 y siempre devuelve 45/40.
- En curva sobre rampa (`|steer|>0.7`) usa **55 fijo** ignorando la velocidad de rampa, y con ese steer `drivebase` manda la **rueda interna en reversa** (`_leftspeed = 55 − 2·0.7·55 = −22`) → pivota y patina en la pendiente.
  - Evidencia: `drivebase.cpp` función `steer()` (`_leftspeed = _speed - (2*rotation*_speed);` y el bloque que invierte dir si queda negativo).

## CR-C — El anti-atasco puede hacerlo RETROCEDER en plena rampa (el más alarmante)
No es que le falte fuerza: **activamente da marcha atrás**.

- `chequearAtasco` marca atasco si `min(Δrueda_der, Δrueda_izq) < 15 pulsos/100ms` sostenido 3 s.
- Con **25 pulsos/cm**, eso es **6 cm/s**. En rampa recta las dos ruedas van parejo y **lento**; si baja de ~6 cm/s por 3 s → dispara `recuperarAtasco()` = `runTime(90, BACKWARD…) + runTime(100, FORWARD…)` → **retrocede en la rampa**.
- **No tiene ninguna condición de pitch.** La única protección es el grace de 8 s, **armado solo al arrancar**: si la rampa está a más de 8 s del arranque, queda desprotegida.
- **FALTA CONFIRMAR EN BANCO:** que el robot efectivamente sostenga <6 cm/s por 3 s en la rampa (muy plausible bajo carga).

## Factor de segundo orden (confirmado, no dominante)
- **PID integral puro:** `_kp=0, _ki=22, _kd=0` (`drivebase.h`). El PWM sube lento al empezar a trepar (solo lo levanta el integrador, ~2.2 por ciclo de 100 ms). **Sí hay headroom** (límite de salida 0-255): en llano no satura.

## SOLUCIÓN (software), en orden

**PASO 0 — Pasada de diagnóstico ANTES de tocar umbrales.** Loguear en el case 7 los 3 ejes del BNO + PWM de una rueda:

```cpp
sensors_event_t e; bno.getEvent(&e);
Serial.print("x="); Serial.print(e.orientation.x);
Serial.print(" y="); Serial.print(e.orientation.y);
Serial.print(" z="); Serial.print(e.orientation.z);
Serial.print(" pwmFL="); Serial.println(fl.getPWM());
```

**Sin esto, los pasos 1-2 son a ciegas.** Si el PWM ya está pegado en ~255 y aun así no sube → **el techo es mecánico/tracción, no software** (y ahí paramos el trabajo de firmware).

1. **Arreglar la detección** (`ajustarVelocidadPorPendiente`): usar el eje correcto (según Paso 0), `fabs(pitch − offset)`, umbral con **histéresis** (entrada ~4.5° / salida ~2.5°, a calibrar), y **capturar el offset de pitch en llano** en el bucle de arranque (promediar N lecturas con el robot quieto y plano). Requisito operativo a documentar: **arrancar siempre en llano**.
2. **Boost real + no pivotar en rampa:** subir la velocidad de rampa de verdad (`VEL_RAMPA ≈ 65`, validar rango 60-80) y, mientras esté en rampa, **recortar `steer` a ±0.5** para que la rueda interna llegue a 0 en vez de ir en reversa.
   - Alternativa más robusta y transversal: **clampear a 0 (no invertir)** en `drivebase.cpp` — pero afecta a TODOS los movimientos (giros, maniobras); probar con cuidado.
3. **Gatear el anti-atasco por pitch:** al inicio de `chequearAtasco`, si `fabs(pitch − offset) > umbral_rampa` → `stuck_since = now; return false;`. Respaldo por si el pitch no es fiable: subir `STUCK_TIME_MS` de 3000 a ~5000. Trade-off: no auto-recupera de un atasco **real** mientras esté en la pendiente.
4. **(Menor) Agregar Kp al PID:** `drivebase.h` `_kp = 0 → 1` (tunear 1-5). Mejora la dinámica de par. **OJO:** afecta a los 4 motores y a TODOS los movimientos → probar recta, giros y maniobras antes de mergear.

---

# PROBLEMA 2 — No detecta plateado / no entra a rescate

**Hallazgo central:** hay **DOS caminos** independientes para disparar el rescate y **los dos están rotos a la vez**. Por eso hoy no quedó ningún disparador vivo. Arreglar uno solo puede no alcanzar.

- **Camino A** = sensor de color APDS9960 (Teensy) → `classify_color()="Plateado"` → `Serial5.write(241)` + `action=2`.
- **Camino B** = visión HSV (RPi) → manda `silver_line=1` por serial → Teensy `action=2`.

## CR-1 — Camino B: la máscara de plata está en el espacio de color EQUIVOCADO (confirmado)
En `Main.py`: `silver_mask = cv2.inRange(frame_resized, lower_silver_hsv, upper_silver_hsv)` — pero `frame_resized` es **BGR**, no HSV. En la misma cuadra, el rojo sí usa `hsv_frame` correctamente. Los rangos `[79,16,46]-[168,28,79]` leídos como BGR exigen un píxel **azul-oscuro sin verde**: lo opuesto a la plata (gris neutro B≈G≈R). La RPi manda `silver_line=0` casi siempre.
- Lo confirma `calibration.py`, que calibra con el picker **HSV** (por eso los valores están en HSV, pero después se aplican sobre BGR).

## CR-2 — Camino A: el umbral de "Plateado" descarta la propia plata como "Blanco" (confirmado)
`classify_color` exige `c > 2220 && ratio_rc > 0.234`, pero la referencia guardada de plata `{r500, g900, b900, c2300}` da `ratio_rc = 500/2300 = 0.217` — **no supera 0.234** → cae en la rama "Blanco". Nunca devuelve "Plateado".

- **INCONSISTENCIA a marcar (el código manda):** el umbral (0.234) está **por encima** del ratio de la propia referencia de plata (0.217). Además la plata (0.217) y el blanco (0.212) tienen `ratio_rc` casi idéntico, y en la tabla `c(Blanco)=2685 > c(Plateado)=2300`. Con esos valores **ni `c` ni `ratio_rc` separan plata de blanco.** → **Recalibrar en banco es obligatorio, no opcional.**

## CR-3 — Aunque arregles el Camino B, queda muerto en el tramo recto (confirmado)
El `while(rutina=="linea")` **no llama `serialEvent5()`** en el linetrack (case 7), y como ese `while` nunca vuelve a `loop()`, el `serialEvent5()` automático de Teensy tampoco corre. → `silver_line` (y `steer`, `green_state`) quedan **congelados** durante todo el recto. La única vía interna (`actualizarContadorVerdes`) está gateada por `CONTAR_VERDES` / `SUPERTEAM`, **ambos en false**.
- **Matiz honesto:** hoy el robot igual siguió la línea, así que "todo congelado" está incompleto → **FALTA CONFIRMAR EN BANCO** qué valor real toma `steer`. El bug de `silver_line` es real de todos modos.

## CR-4 — En maniobras el serial se corrompe (confirmado)
Con `kFixIssue63KeepSerialDuringMotions = false`, las funciones `runTime` / `runDistance` hacen `Serial5.read()` + `print` **tirando el byte** sin pasarlo por la máquina de estados → descuadra el framing `[255, speed, 254, angle, 253, gs, 252, silver]` y pierde `silver_line`.

## CR-5 — Desincronización RPi ↔ Teensy (confirmado)
La RPi hace `estado='rescate'` sola (apenas ve plata) y arranca YOLO, sin esperar el 241. Si la Teensy no procesó `silver_line` (por CR-3), quedan desincronizadas. Y si el disparo viene por camino B, la Teensy **no reenvía el 241** (el único `write(241)` está en el camino de color).

## SOLUCIÓN (software), en orden — casi todo es 1 línea

**PASO 0 — Banco:** medir las nubes reales de color.
- Firmware: poner `shouldPrint = true` en `classify_color` y loguear R,G,B,C,ratio sobre **plata / blanco / negro** reales, con la luz de la cancha.
- RPi: correr `calibration.py` sobre la cinta plateada real.
- Recién con esos datos elegir el discriminador que caiga ENTRE plata y blanco (probablemente **C absoluto** o la **varianza especular** frame-a-frame, NO `ratio_rc`).

1. **RPi — máscara de plata:** cambiar `cv2.inRange(frame_resized, …)` por `cv2.inRange(hsv_frame, …)` (el `hsv_frame` ya está calculado). Después recalibrar con el Paso 0.
2. **Teensy — drenar serial en la línea:** agregar `serialEvent5();` como **primera línea** del `while(rutina=="linea")`. Arregla el camino B congelado y de paso refresca el `steer` (ayuda también al Problema 1). **Detrás de un flag** para poder revertir, porque hoy la línea funciona.
3. **Teensy — `priority_fix_flags.h`:** `kFixIssue63KeepSerialDuringMotions = true`. Deja de tirar bytes en maniobras.
4. **Teensy — umbral de plata** (`classify_color`): recalibrar con el Paso 0. **NO usar `ratio_rc` como piso** (el blanco da 0.212 → falsos positivos masivos). Discriminar por **C absoluto** o **varianza especular** (el historial `color_c_history[]` ya existe). Ajustar la rama "Blanco" para que su cota de `c` no se solape con el nuevo umbral de plata.
5. **Teensy — re-sincronizar** (case 2, ANTES de `rescateAvisado = true`): `if (!rescateAvisado) Serial5.write(241);` — idempotente (si vino por color ya salió el 241; si vino por `silver_line`, lo dispara y la RPi confirma).
6. **Higiene RPi:** sacar el `print(area)` del hot loop (baja FPS y ensucia el log).

> **CUIDADO con endurecer:** si el síntoma es **falso negativo**, agregar confirmación de N muestras lo **EMPEORA**. Eso va solo DESPUÉS de bajar el umbral, y solo si aparecen falsos positivos. Y si se agrega confirmación en línea, contar **solo muestras frescas** (no repetir el mismo sample stale).

---

## Lo que se DESCARTÓ (transparencia)
- **"`resetear_bno()` pierde el cero de pitch":** refutado. No existe un cero guardado, y solo corre en evacuación (después de las rampas).
- **"Los umbrales de plata HSV no son razonables":** refutado como estaba planteado — la premisa asumía que se aplicaban en HSV; el bug real es que se aplican sobre BGR (eso es CR-1).

---

## Qué HAY QUE MEDIR EN BANCO antes de dar por cerrado

**Rampa:**
- Qué eje del BNO varía al subir (x/y/z) y con qué signo → define si `.y` es correcto o hay que usar `.z`.
- Pitch real en llano (offset de montaje).
- `getPWM()` de las ruedas EN la rampa → si ya satura en ~255, el techo es mecánico.
- RPM mínimo (`VEL_RAMPA`) que sube sin patinar.
- Confirmar si la velocidad real cae bajo 6 cm/s por 3 s (dispara el falso atasco).

**Plateado:**
- Cuál de los dos caminos estaba activo hoy (loguear si llega `silver_line=1` y si el APDS clasifica "Plateado").
- Nubes de color del APDS sobre plata / blanco / negro reales.
- Rangos HSV de plata re-derivados con `calibration.py` bajo la luz de la cancha.
- Que el `steer` fresco (Paso 2) no rompa el seguimiento de línea que hoy funciona.

---

## Riesgos principales (regla de oro #4: no romper lo validado)
- **`serialEvent5()` en la línea:** refresca `steer`/`green_state` que hoy andan → posible regresión en el seguimiento. Mitigar con flag reversible + prueba completa de línea en banco.
- **Subir velocidad / Kp del PID:** afecta a todos los movimientos, no solo la rampa. Un flag por cambio + prueba de cada subsistema.
- **Umbral de plata flojo:** falsos positivos (el robot se para en medio de la pista). No usar ratio como piso; discriminar por C/varianza.
- **Todo cambio de firmware:** un flag por fix en `priority_fix_flags.h` (patrón ya usado) + entrada en `testing/TEST_LOG.md` antes de mergear.

---

## Recomendación / próximos pasos

Lo más rentable es **una sola pasada de diagnóstico con logging** (Paso 0 de los dos problemas) antes de tunear nada: te dice el eje/signo del pitch, si el PWM satura (techo mecánico) y las nubes de color reales. Sin eso, cualquier umbral nuevo es a ciegas — y la calibración guardada ya demostró estar internamente contradictoria.

Los fixes confirmados y baratos (plateado 1-2-3-5 + gate anti-atasco por pitch) se pueden dejar **detrás de flags**, en un PR con su entrada en `TEST_LOG.md`, sin tocar lo que hoy funciona. El **testing en banco lo cierra el equipo**.

---

### Referencias de archivos
- Firmware que corrió hoy: `software/teensy/firmware/src/main.cpp` (versión nueva — funciones clave: `ajustarVelocidadPorPendiente`, `leer_pitch`, `chequearAtasco`, `recuperarAtasco`, case 7 de linetrack, loop de línea, `classify_color`).
- Motores/PID: `software/teensy/firmware/lib/drivebase/drivebase.cpp` y `.h`, `software/teensy/firmware/lib/PID/PID.cpp`.
- Flags: `software/teensy/firmware/src/priority_fix_flags.h`.
- Visión: `software/raspberry/final_rpi/Main.py`, `calibration.py`.

*Diagnóstico asistido por análisis multi-agente verificado contra el código fuente. Los puntos "FALTA CONFIRMAR EN BANCO" son hipótesis con evidencia de código pero sin validación física.*
