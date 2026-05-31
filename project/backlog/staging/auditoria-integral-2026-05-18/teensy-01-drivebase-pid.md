# Auditoría integral 2026-05-18 — Teensy / Control de motores (drivebase + PID)

**Dominio:** `software/teensy/firmware/lib/drivebase/drivebase.cpp` + `.h`, `lib/PID/PID.cpp` + `.h`, y su uso en `src/main.cpp` (`steer()`, `runTime()`, `runDistance()`, `runAngle()`, ISRs de encoder).
**Autor:** auditor de control de motores (lectura solamente, sin tocar código).
**Branch analizada:** `feature/initialize-testing-log` (contenido también en `main`, post-PR #101).
**Fecha:** 2026-05-18 (redactado 2026-05-31).

> **Marco de lectura (LEER ANTES):** cada hallazgo se presenta como **TEMA A ANALIZAR**, no como "bug a fixear". Para cada uno se da: causa raíz, **riesgo de NO tocar**, **riesgo de tocar**, esfuerzo estimado, fix conceptual y plan de validación en banco. La decisión final es del equipo. Este código lleva meses de tuneo de los alumnos y "hoy anda" — varios de estos temas son delicados justamente porque el comportamiento actual compensa el bug.

---

## 0. Contexto de hardware (clave para interpretar todo el módulo)

Del BOM (`hardware/electronics/_legacy/ELECTRONICA/Lista de materiales y link de compra.md`):

- **Motores:** 4× **DFRobot FIT0441 "Brushless DC Motor with Encoder 12V 159RPM"**. Este es un motor brushless **con driver integrado de 3 hilos de señal**:
  - **Entrada PWM INVERTIDA**: `PWM=255 (duty alto) → motor PARADO`; `PWM=0 (duty bajo) → velocidad MÁXIMA`. **Esto explica el `255 - _pwmVal` de `drivebase.cpp:50`** y es correcto a nivel de hardware (no es un bug en sí — el bug es la interacción con el sentido del PID, ver T-01).
  - **Salida de pulsos (tacómetro/FG)**: un tren de pulsos cuya frecuencia es proporcional a la velocidad. Es lo que entra por `encPin` y dispara `updatePulse()`. **No es un encoder en cuadratura** (no hay canal A/B, no da sentido de giro por hardware) — de ahí que el sentido se infiera por software desde `_dir` (ver T-05).
  - Hilo de dirección (`dirPin`) selecciona sentido.
- **Velocidad nominal 159 RPM** → explica `constrain(speed, 0, 159)` en `steer()`: el parámetro `speed` está expresado directamente en **RPM de setpoint**, no en 0-100 ni en PWM. (Ojo: la RPi manda `speed = data/100*100`, 0-100; ese valor de 0-100 entra como "RPM" 0-100, por debajo del tope de 159. Coherente pero confuso, ver T-08.)
- **Ruedas tracción:** Omniwheel 58 mm (Ø ≈ 5.8 cm) + 2 ruedas fijas Pololu. Relevante para la calibración pulsos→cm (T-04).

Que el motor sea **brushless con PWM invertido** es el dato que cambia el análisis del "PID invertido": el `255 - _pwmVal` **no es el error**; el problema es el **acople de sentido entre el lazo PID (DIRECT) y un actuador de ganancia negativa** (T-01).

---

## 1. Resumen de hallazgos

| ID | Tema | Sev | Confirma/Amplía | Esfuerzo |
|----|------|-----|-----------------|----------|
| **T-01** | Lazo PID + actuador invertido: el lazo **no regula**, satura. | **P0** | Confirma #B1 (#121), profundiza | M |
| **T-02** | `SampleTime=100 ms` del PID vs. `setSpeed()` llamado a ~cientos de Hz: el integrador avanza 1 vez cada 100 ms → lazo lentísimo + `getSpeed()` recomputado en cada call sin usarse. | **P0** | NUEVO | M |
| **T-03** | `ki=22`, `kp=0`, `kd=0`: control **puramente integral**, sin término proporcional → respuesta lenta y propensa a oscilar/sobrepasar. | P1 | NUEVO (amplía #B1) | M |
| **T-04** | Constante `25 pulsos/cm` sin origen + ISR en `CHANGE` (x2 conteo). `runDistance` puede estar ~2× mal. | P1 | Confirma #B10 (#126) | S |
| **T-05** | Sentido de pulso se infiere de `_dir` (software), no del hardware. En frenada/inversión el conteo se corrompe (cuenta pulsos de inercia con el `_dir` nuevo). | P1 | NUEVO (amplía #B10) | M |
| **T-06** | Histéresis de dirección `if (_pwmVal < 10) _dir = !_dir;` **invierte el sentido comandado** en baja demanda. Lógica peligrosa y casi-muerta por T-01. | P1 | NUEVO | S |
| **T-07** | `getSpeed()`: ventana RPM rota — usa `max(_end-_begin, _now-_end)` y `_rpmlist[3]` se pisa; división por cero parcheada pero el filtro mezcla magnitudes. Medición de RPM ruidosa/sesgada. | P1 | NUEVO | M |
| **T-08** | `pulseCount` sin inicializar en constructor; `_dir` sin inicializar; unidades de `speed` ambiguas (RPM vs 0-100). | P2 | Confirma #67, amplía | S |
| **T-09** | `noInterrupts()` alrededor de `getSpeed()` en `setSpeed()` pero **no** en lecturas de `pulseCount` en `runDistance` (`int32_t frCount = fr.pulseCount`): lectura no atómica de `long` volátil + ISR. | P2 | NUEVO | S |
| **T-10** | Sin rampa de aceleración / sin slew-rate: cambios bruscos de setpoint → tirones, pérdida de tracción y de línea, picos de corriente. | P2 (oportunidad) | NUEVO | M |
| **T-11** | `reset()` del PID sólo limpia `outputSum`; no resetea `lastInput`/`lastTime` → primer `Compute()` tras reset puede dar patada derivativa (mitigado hoy por `kd=0`). | P2 | NUEVO | S |

Leyenda severidad: **P0** = puede impedir completar la corrida / afecta todo; **P1** = pérdida de puntaje o errático; **P2** = robustez/deuda.

---

## 2. Detalle por hallazgo

### T-01 — El lazo PID no regula: satura por acople de sentido (confirma #B1 / #121) — P0

**Código (`drivebase.cpp:38-52`):**
```cpp
double Moto::setSpeed(int dir, double rpm) {
    noInterrupts();
    _realrpm = this->getSpeed();
    interrupts();
    _rpm = rpm;                       // setpoint
    if (_pwmVal < 10) _dir = !_dir;   // histéresis (ver T-06)
    else _dir = dir;
    _motoPID.Compute();               // PID DIRECT: out sube si (setpoint - input) sube
    digitalWrite(_dirPin, _dir);
    analogWrite(_pwmPin, (int)(255 - _pwmVal));  // actuador invertido (FIT0441)
    return _realrpm;
}
```
Y `drivebase.h:31`: `PID _motoPID = PID(&_realrpm, &_pwmVal, &_rpm, _kp, _ki, _kd, DIRECT);`

**Causa raíz (matizada respecto de #B1):** el PID está en **DIRECT**, es decir: si `error = _rpm - _realrpm > 0` (vamos más lento que el setpoint), el PID **sube** `_pwmVal`. Pero el actuador es de **ganancia negativa**: `analogWrite(255 - _pwmVal)` → subir `_pwmVal` **baja** el duty efectivo. En un FIT0441 (PWM invertido) bajar el duty **sube** la velocidad. Hay que cerrar el lazo de sentido completo:

- PID DIRECT: `error>0 ⇒ _pwmVal↑`.
- Actuador: `_pwmVal↑ ⇒ (255-_pwmVal)↓ ⇒ duty físico↓ ⇒ velocidad FIT0441↑`.

O sea: **error positivo ⇒ velocidad sube**. ¡El sentido global **sí** cierra! El problema **no** es un simple "signo invertido" como sugiere el título de #B1, sino algo más sutil y que conviene verificar en banco antes de tocar:

1. **El integrador arranca en `Initialize()` con `outputSum = *myOutput`** (PID.cpp:210). En el constructor `_pwmVal` vale 0 (sin inicializar explícito, ver T-08) → `outputSum≈0`. Con `kp=0`, el output es **sólo** `outputSum`. Con error positivo persistente y `ki` grande (T-03), `outputSum` trepa a `outMax=255` en pocas iteraciones efectivas y **se queda saturado en 255**. Entonces `analogWrite(255-255)=analogWrite(0)` → **duty 0 → FIT0441 a máxima velocidad** todo el tiempo. **El robot anda "a fondo" no porque el PID regule, sino porque está saturado arriba.** Esto coincide con lo que dice #121 ("hoy anda porque el saturado entrega PWM máximo").
2. Como nunca sale de saturación (con `kp=0` no hay término que reaccione rápido y `getSpeed()` está sesgado, T-07), el lazo **es efectivamente lazo abierto a tope**. La diferenciación de velocidad entre ruedas que necesita `steer()` para girar se la da **el reparto de setpoints** (`_leftspeed`/`_rightspeed`), no el PID. Por eso "gira", pero sin control de RPM real.

**Conclusión:** #B1 está **confirmado en su efecto** (lazo saturado, no regula) pero la **causa precisa** es la combinación *DIRECT + actuador negativo + ki dominante + kp=0*, no un signo suelto. Cambiar a ciegas a `analogWrite(_pwmVal)` (como sugiere #121 como opción) **invertiría el sentido global y muy probablemente haría que las ruedas frenen al pedirles velocidad** — empeoraría. **Este es el cambio más delicado del firmware.**

**Riesgo de NO tocar:** el control de velocidad nunca regula; las 4 ruedas van saturadas. Pérdidas concretas: imposible bajar RPM de forma fina en rampas/bajadas (depende de hacks como `ajustarVelocidadPorPendiente`), tracción despareja entre ruedas (cada FIT0441 satura a su RPM mecánica real, no a un setpoint común) → deriva lateral en recto, y el robot "tira" en curvas. En auto-recuperación, la falta de velocidad controlada hace los reposicionamientos por tiempo (`runTime`) poco repetibles.

**Riesgo de tocar:** **alto**. Es el lazo que mueve todo. Un signo mal cerrado = ruedas que aceleran cuando deberían frenar (runaway) o que no arrancan. Hay que tocarlo con el robot **elevado sobre soportes (ruedas al aire)** y switch de corte a mano.

**Fix conceptual (a validar, NO aplicar a ciegas):**
- Opción A (preferida): **mantener** `255 - _pwmVal` (respeta el HW FIT0441) y **dar `kp` real** (T-03) para que el lazo regule en vez de saturar; **además** acortar `SampleTime` (T-02). Verificar con medición de RPM real que ante un setpoint de, p.ej., 80 RPM el `_realrpm` converja a ~80 y `_pwmVal` se estabilice en un valor intermedio (no pegado a 255).
- Opción B: declarar el PID **REVERSE** y usar `analogWrite(_pwmVal)` — equivalente algebraico, pero cambia dos cosas a la vez (más riesgo de confundirse). Si se elige, hacerlo en un commit aislado.
- En cualquier caso: **primero arreglar la medición** (`getSpeed`, T-07) y la **frecuencia** (T-02); sin una medida de RPM confiable y un lazo que corra rápido, sintonizar es imposible.

**Plan de validación en banco:**
1. Robot sobre soportes, ruedas libres. Switch de corte accesible.
2. Instrumentar: `Serial.print` de `_rpm` (setpoint), `_realrpm`, `_pwmVal` por motor (ya hay prints comentados en `updatePulse`).
3. Banco escalón: setpoint 0→40→80→120 RPM, registrar si `_realrpm` sigue al setpoint y si `_pwmVal` queda en zona media (regula) o pegado a 0/255 (satura).
4. Repetir por las 4 ruedas; comparar RPM real a igual setpoint (detecta desbalance mecánico).
5. Recién con lazo regulando: prueba de recto 1 m en piso y medir deriva lateral.
6. Registrar en `testing/TEST_LOG.md` (setpoint, RPM medida, PWM, deriva).

---

### T-02 — Desfase brutal entre `SampleTime=100 ms` y la frecuencia de `setSpeed()` — P0 (NUEVO)

**Causa:** `PID.cpp:25` fija `SampleTime = 100` ms y `Compute()` (PID.cpp:54-56) **no hace nada** si no pasaron 100 ms desde el último cómputo. Pero `setSpeed()` se llama una vez por rueda **en cada `steer()`**, y `steer()` se llama en bucles tipo `case 7` (linetrack) o `runTime`/`runDistance` **cientos de veces por segundo** (el `runDistance` tiene `delay(10)` → ~100 Hz; el linetrack del `case 7` no tiene delay → miles de Hz). Resultado:

- En ~99 de cada 100 llamadas, `Compute()` retorna `false` sin recalcular → `_pwmVal` queda congelado y `setSpeed()` igual escribe el PWM viejo.
- **El lazo de velocidad corre en realidad a 10 Hz** (1/100 ms). Para un control de RPM de un robot que cambia de setpoint en curvas, 10 Hz es **muy lento**.
- Peor: `getSpeed()` se **recalcula carísimo en cada llamada** (incluso las que no computan PID) y dentro de `noInterrupts()` (T-09). En el linetrack a miles de Hz, eso es CPU tirada y secciones críticas innecesarias.

**Interacción con T-01:** como el integrador sólo avanza cada 100 ms, **tarda más en saturar**, pero igual satura porque `ki·error·SampleTimeInSec` (PID.cpp:127, `ki=22·0.1=2.2` por iteración) llena `outputSum` (0→255) en ~115 iteraciones efectivas = ~11.5 s la primera vez, y se mantiene saturado. Si se acelera `SampleTime`, satura más rápido aún si no se corrige `ki` (T-03). **T-02 y T-03 se sintonizan juntos.**

**Riesgo de NO tocar:** lazo de velocidad a 10 Hz → no puede corregir perturbaciones rápidas (una rueda que patina, un bache). Sumado a T-01, el control de velocidad es prácticamente decorativo.

**Riesgo de tocar:** medio. Bajar `SampleTime` cambia la ganancia integral efectiva (la lib reescala `ki` y `kd` en `SetSampleTime`, pero acá se setea por constructor, no por esa vía). Hay que re-sintonizar.

**Fix conceptual:** definir una frecuencia de control explícita (p.ej. 50-100 Hz, `SampleTime = 10–20 ms`), **llamar `Compute()` a esa cadencia fija** (idealmente con un `elapsedMillis` o timer, desacoplado de cuántas veces se llame `steer()`), y **separar** "calcular PID/PWM" de "escribir PWM": escribir el último PWM siempre, recalcular sólo a la cadencia. Y mover `getSpeed()` para que se evalúe sólo cuando se va a computar.

**Validación en banco:** medir con `micros()` la frecuencia real de `Compute()` que efectivamente recalcula (contar `true` de retorno). Verificar respuesta a escalón antes/después: tiempo de subida y overshoot del `_realrpm`.

---

### T-03 — Control puramente integral (`kp=0, ki=22, kd=0`) — P1 (NUEVO, amplía #B1)

**Código (`drivebase.h:30`):** `double _kp = 0, _ki = 22, _kd = 0;`

**Causa:** sin término proporcional, el actuador **sólo** reacciona vía la acumulación integral. Un lazo I-puro:
- Es **lento** (la corrección crece con el tiempo, no con el error instantáneo).
- **Sobrepasa y oscila** con facilidad (el integrador "se pasa" y tarda en descargar).
- Combinado con `ki=22` (alto) y el reescalado `ki_efectivo = 22 × 0.1 = 2.2` por paso, **empuja a saturación** (T-01).

`kd=0` es defendible (el ruido de `getSpeed`, T-07, haría que un D real meta ruido), pero `kp=0` es la causa de que el lazo no tenga "reflejos".

**Riesgo de NO tocar:** el lazo nunca tendrá respuesta fina; seguirá saturado/lento. Imposibilita aprovechar el control de RPM para tracción pareja.

**Riesgo de tocar:** medio. Sintonizar mal `kp` puede meter oscilación visible (robot "tiembla" en recto) o, si T-01 no se resolvió primero, no cambiar nada (porque ya está saturado).

**Fix conceptual:** sintonizar en este orden, **después** de T-01/T-02/T-07: arrancar `ki` mucho más bajo (p.ej. 0.5-1.0 con el `SampleTime` nuevo), subir `kp` desde 0 hasta obtener respuesta rápida sin oscilación sostenida, dejar `kd=0` salvo que la medición de RPM ya esté filtrada. Documentar las ganancias finales con la velocidad de muestreo a la que fueron sintonizadas (las ganancias **no son portables** entre `SampleTime`).

**Validación en banco:** método de escalón (setpoint fijo, observar `_realrpm`): buscar <10-15% overshoot y settling <0.3 s, sin oscilación sostenida. Hacerlo por rueda. Probar bajo carga (robot apoyado, no al aire) porque la inercia cambia la dinámica.

---

### T-04 — Constante `25 pulsos/cm` sin origen + ISR en `CHANGE` (confirma #B10 / #126) — P1

**Código (`main.cpp:537`):** `int32_t encoder = 25*Distance;` (idéntico en `test/actuators/runDistance.cpp:59` y `motors_move.cpp:99`).
**ISRs (`main.cpp:743-746`):** `attachInterrupt(..., CHANGE)` en los 4 encoders.

**Causa / chequeo numérico:** con rueda Ø 58 mm, 1 vuelta = π·5.8 = **18.22 cm**. Si `25 pulsos/cm`, entonces 1 vuelta ≈ **455 pulsos/rev**. El FIT0441 publica del orden de ~**45 pulsos/rev** en su salida FG por vуelta de **eje del motor** (depende de polos), y la reducción interna y el `CHANGE` (cuenta flancos de subida **y** bajada → ×2) hacen el número final. **El punto de #B10 es correcto:** la constante `25` es opaca, sin trazabilidad, y **si se calibró contando un solo flanco pero el `attachInterrupt` quedó en `CHANGE`** (o viceversa), `runDistance` está **factor 2 de error**. En rescate, recorrer "5 cm" reales cuando se pidieron 5 (`runDistance(30,FORWARD,5)`) define si la pinza agarra o no la pelota → impacto directo en puntaje.

**Sub-observación nueva:** `runDistance` usa **sólo `fr` y `fl`** (`frCount`/`flCount`) para medir distancia y rompe con `>=` "cualquiera de las dos". Si una rueda delantera patina o su FG falla, la otra dispara el corte → ok como OR de seguridad, pero **no promedia** ni detecta desbalance; y si **ambas** delanteras fallan, no hay timeout (eso es #60, fuera de mi dominio pero se toca acá).

**Riesgo de NO tocar:** distancias en rescate y reposicionamientos sistemáticamente erróneos (probablemente ~2×). Recolección y depósito poco repetibles.

**Riesgo de tocar:** bajo. Es una constante de calibración; el riesgo es calibrar mal (mitigable midiendo varias veces).

**Fix conceptual:** medir empíricamente. Mandar `runDistance` para una distancia conocida grande (1 m), leer `pulseCount` real, y definir `PULSES_PER_CM = pulsos_medidos / 100`. Documentar el modo de ISR usado (`CHANGE` vs `RISING`) **junto** a la constante, porque cambiar uno sin el otro rompe la calibración. Idealmente, `#define PULSES_PER_CM` en un header de parámetros (se conecta con #83 "magic numbers a parametros.h").

**Validación en banco:** marcar 100 cm en el piso, correr `runDistance(velocidad_baja, FORWARD, 100)`, medir distancia física recorrida con cinta; ajustar constante hasta que físico ≈ pedido en 3 corridas. Repetir hacia atrás. Registrar pulsos crudos por rueda.

---

### T-05 — Sentido del pulso se infiere por software desde `_dir`; en frenada/inversión el conteo se corrompe — P1 (NUEVO, amplía #B10)

**Código (`drivebase.cpp:59-91`):** `updatePulse()` incrementa/decrementa `pulseCount` según `_dir` (la dirección **comandada**) y según el `id` del motor (`FL`/`BL` cuentan al revés que `FR`/`BR`, por el espejado del chasis).

**Causa:** el FIT0441 entrega un tren de pulsos **sin signo** (no es cuadratura). El sentido se toma de `_dir`, que es lo que el software **pidió**, no lo que la rueda **hace**. Problemas:
1. **Inversión de sentido con inercia:** al pasar de FORWARD a BACKWARD (típico en `runDistance`, que arranca con `runTime(30,BACKWARD,0,20); runTime(30,FORWARD,0,20)` para "asentar"), durante la desaceleración la rueda **sigue girando hacia adelante por inercia** pero `_dir` ya es BACKWARD → esos pulsos de inercia se **restan** cuando deberían sumar. Error acumulado en cada cambio de sentido.
2. **Histéresis T-06:** cuando `_pwmVal<10`, `_dir` se invierte artificialmente (`_dir=!_dir`), y `updatePulse` contará en el sentido equivocado durante esos instantes.
3. **Lectura del `_dir` en la ISR sin sincronía:** `_dir` se escribe en `setSpeed()` (contexto main) y se lee en `updatePulse()` (ISR). No es `volatile` (está en la clase como `int _dir;`), aunque al ser acceso de una sola palabra el riesgo real es bajo; lo grave es el **desfase semántico** (1) y (2).

**Riesgo de NO tocar:** odometría sesgada justo en las maniobras que más dependen de ella (rescate: avances cortos con arranques/frenadas). Sumado a T-04, el error de distancia es estructural.

**Riesgo de tocar:** medio. Cambiar el conteo de sentido puede romper la calibración existente (que hoy compensa parte del error). Hay que recalibrar T-04 junto.

**Fix conceptual:** dado que el HW no da sentido real, las opciones son: (a) asumir que durante un `runDistance` el sentido es constante y **contar siempre en valor absoluto** dentro de la maniobra (la dirección la fija el `dir` del `runDistance`, no el `_dir` instantáneo con histéresis), evitando que la histéresis T-06 y la inercia ensucien; (b) ignorar pulsos durante la ventana de inversión inicial (los `runTime` de "asentado"); (c) a futuro, si se quisiera odometría seria, migrar a motores con encoder en cuadratura. Para el mundial, (a)+(b) es lo razonable y de bajo costo.

**Validación en banco:** con la rueda al aire, comandar FORWARD y luego BACKWARD y observar que `pulseCount` suba monótono en cada fase (no que "rebote" en la transición). Medir el error de `pulseCount` tras N ciclos adelante/atrás del mismo tramo: debería volver cerca de 0 si el conteo es consistente.

---

### T-06 — Histéresis `if (_pwmVal < 10) _dir = !_dir;` invierte el sentido comandado — P1 (NUEVO)

**Código (`drivebase.cpp:44-47`):**
```cpp
if (_pwmVal < 10) _dir = !_dir;   // ¿anti-zona-muerta? invierte la dirección
else _dir = dir;
```
**Causa:** la intención aparente es alguna forma de "patада" para vencer la zona muerta del motor cuando el PWM pedido es muy bajo. Pero lo que hace literalmente es: **cuando `_pwmVal<10`, mandar la rueda en sentido contrario al pedido**. Con un actuador `255-_pwmVal`, `_pwmVal<10 ⇒ duty físico >245 ⇒ FIT0441 casi parado`. O sea, justo cuando el motor está casi parado, le invierte el `dirPin`. En la práctica:
- Con T-01 (lazo saturado, `_pwmVal` pegado a 255), esta rama **casi nunca se ejecuta** → es código semi-muerto **hoy**. Pero si se arregla T-01/T-03 y el lazo empieza a entregar PWM bajos legítimos (rueda interna en una curva suave, o setpoint chico), **esta rama se despierta y empieza a invertir ruedas espontáneamente** → comportamiento errático difícil de diagnosticar.
- Rompe T-05 (cuenta pulsos al revés en esos instantes).

**Riesgo de NO tocar:** bomba de tiempo. Mientras el lazo esté saturado no molesta; en cuanto se sintonice el PID (T-01/T-03), aparecen micro-inversiones de ruedas en baja demanda → robot "nervioso", líneas perdidas, odometría sucia. Es una **trampa acoplada**: arreglar T-01 puede "destapar" T-06.

**Riesgo de tocar:** bajo-medio. Quitar/cambiar la histéresis es simple, pero si los alumnos la pusieron para un síntoma real de zona muerta, hay que reemplazarla por algo correcto (no sólo borrarla).

**Fix conceptual:** eliminar la inversión de `_dir` por bajo PWM. Si se necesita vencer zona muerta, hacerlo **sin cambiar el sentido**: o un `feed-forward`/offset mínimo de PWM en el sentido correcto, o un piso de PWM (clamp del duty físico) que mantenga el motor justo arriba de su umbral de arranque. La dirección debe seguir **siempre** a `dir`.

**Validación en banco:** comandar setpoints bajos (5-15 RPM) tras sintonizar el PID y verificar que **ninguna** rueda invierta sentido. Observar `_dir` por Serial mientras se barre el setpoint de 0 hacia arriba.

---

### T-07 — `getSpeed()`: ventana de RPM mal formada y filtro que mezcla magnitudes — P1 (NUEVO)

**Código (`drivebase.cpp:22-36` + `updatePulse` 59-66):**
```cpp
double Moto::getSpeed() {
    double _now = micros();
    if ((_now - _end) > 111111) { _realrpm = 0; }       // >111 ms sin pulso ⇒ 0
    else {
        _rpmlist[3] = max(_end - _begin, _now - _end);  // (1) pisa _rpmlist[3]
        _realrpm = (_rpmlist[0]+_rpmlist[1]+_rpmlist[2]+_rpmlist[3]) / 4;  // promedio de PERIODOS
        _realrpm = (_realrpm != 0) ? (111111.0 / _realrpm) : 0;            // periodo→"rpm"
    }
    return _realrpm;
}
```
con `_rpmlist` inicializado a `{111111,111111,111111,111111}` y `updatePulse()` haciendo `_rpmlist[3] = _end - _begin` (período entre los dos últimos pulsos).

**Causas (varias, sutiles):**
1. **`max(_end - _begin, _now - _end)` mezcla dos cosas distintas:** `_end-_begin` es el período del **último** intervalo entre pulsos; `_now-_end` es el tiempo transcurrido **desde el último pulso hasta ahora** (aún sin pulso nuevo). Tomar el `max` intenta "estirar" la estimación cuando el motor frena (no llegan pulsos), lo cual es un parche razonable contra quedarse con un período viejo optimista, **pero** entonces `getSpeed()` **escribe en `_rpmlist[3]`** un valor que **no es un período de pulso real** — y ese valor lo va a pisar el próximo `updatePulse`. El filtro de media móvil queda contaminado por una muestra que no es homogénea con las otras tres.
2. **Doble escritura de `_rpmlist[3]`:** lo escribe `updatePulse()` (ISR, período real) **y** `getSpeed()` (main, el `max`). Race + semántica inconsistente.
3. **La constante `111111`** (≈ µs) aparece como umbral de timeout (>111 ms ⇒ 0 RPM, equivale a ~0.5 RPM mínimo medible con este esquema) **y** como numerador de conversión período→RPM. No está documentada de dónde sale ni a qué "RPM" corresponde (no parece dar RPM reales sino una unidad propia; con período en µs, `111111/periodo` no es rev/min salvo coincidencia de calibración). Esto refuerza que el `speed` del sistema **no está en RPM físicas** sino en una escala interna (ver T-08).
4. **Cuantización a bajas RPM:** con pocos pulsos la media de 4 períodos reacciona lento; a alta velocidad, ok.

**Por qué importa para el PID:** un PID sólo es tan bueno como su medición. Con `_realrpm` ruidoso/sesgado, sintonizar `kp` (T-03) es adivinar, y `kd` real sería inviable. **T-07 es prerrequisito de T-01/T-03.**

**Riesgo de NO tocar:** el lazo nunca tendrá una realimentación limpia → imposible que regule fino aunque se arregle T-01. Hoy se "salva" porque está saturado y la medición no se usa de verdad.

**Riesgo de tocar:** medio. Reescribir `getSpeed` cambia la entrada del PID → re-sintonía obligada. Riesgo de introducir otro sesgo.

**Fix conceptual:** separar responsabilidades — que **sólo la ISR** escriba los períodos en el buffer; que `getSpeed()` **sólo lea** y filtre, sin pisar el buffer; manejar el caso "motor frenando / sin pulsos recientes" como una rama explícita (si `_now-_end > umbral`, decaer la estimación hacia 0 sin contaminar el buffer de períodos). Documentar la conversión a unidades reales (µs/pulso → RPM usando pulsos/rev del FIT0441) para que `speed` sea RPM de verdad o, al menos, una escala documentada y estable.

**Validación en banco:** con la rueda girando a velocidad fija conocida (medir con tacómetro óptico o contando pulsos en 1 s), verificar que `getSpeed()` devuelva un valor estable y proporcional. Barrer velocidades y graficar `getSpeed` vs RPM real (debe ser lineal).

---

### T-08 — Inicialización indefinida (`pulseCount`, `_dir`) y unidades ambiguas de `speed` — P2 (confirma #67, amplía)

**Causas:**
- `Moto::pulseCount` (`drivebase.h:24`, `volatile long`) **no se inicializa en el constructor** (`drivebase.cpp:8-19`). Antes del primer `resetPulseCount()` vale basura. **Esto es exactamente #67** (P2 abierto). Cualquier `runDistance` que corra antes de un reset usa un origen indefinido. `setup()` no llama a `reset_enconder()` antes del primer movimiento real (aunque `runDistance` sí resetea al entrar — mitigación parcial).
- `_dir` tampoco se inicializa → el primer `setSpeed` con `_pwmVal<10` (T-06) hace `_dir=!_dir` sobre un valor basura.
- `_pwmVal`, `_realrpm`, `_begin`, `_end` sin inicializar explícito (la primera `getSpeed` usa `_end` basura → `_now-_end` puede dar cualquier cosa en el primer ciclo).
- **Unidades de `speed`:** la RPi manda `speed = data/100*100` (0-100); `steer()` lo trata como RPM y lo limita a 159; `getSpeed`/`PID` operan en la escala interna de `111111/periodo`. **No hay una unidad coherente declarada.** Mantenibilidad pobre y fuente de bugs de calibración.

**Riesgo de NO tocar:** bajo en operación estable (los resets enmascaran), pero genera comportamientos no reproducibles en el arranque y dificulta razonar sobre el sistema. Deuda que paga caro al sintonizar.

**Riesgo de tocar:** muy bajo. Inicializar miembros en el constructor es seguro.

**Fix conceptual:** inicializar en el constructor `pulseCount=0; _dir=FORWARD; _pwmVal=0; _realrpm=0; _begin=_end=micros();`. Definir y documentar la unidad de `speed` (RPM real, idealmente, conectado a T-07) en un header de parámetros.

**Validación:** compilación + arranque en banco; verificar que `pulseCount` sea 0 antes del primer movimiento sin depender de resets.

---

### T-09 — Lectura no atómica de `pulseCount` (long volátil) en `runDistance` — P2 (NUEVO)

**Código (`main.cpp:542-543`):** `int32_t frCount = fr.pulseCount; int32_t flCount = fl.pulseCount;` sin `noInterrupts()`.

**Causa:** `pulseCount` es `long` (32 bits). En Teensy 4.1 (Cortex-M7, 32-bit) un `long` de 32 bits se lee en **una** instrucción → la lectura **sí es atómica** en esta plataforma. Por eso lo marco P2 y no P1: **en este hardware no hay tearing**. Sin embargo: (a) el código es frágil si alguna vez se porta o si `pulseCount` pasa a 64 bits; (b) hay **incoherencia** con `setSpeed()`, que sí envuelve `getSpeed()` en `noInterrupts()` (drivebase.cpp:40-42) — criterio inconsistente. La sección crítica en `setSpeed` además es **innecesariamente cara** si se llama a miles de Hz (T-02).

**Riesgo de NO tocar:** prácticamente nulo en Teensy 4.1. Sólo deuda de robustez/portabilidad.

**Riesgo de tocar:** nulo.

**Fix conceptual:** estandarizar criterio: como en M7 la lectura de 32 bits es atómica, **quitar** el `noInterrupts()` superfluo de `setSpeed` (gana CPU) y dejar las lecturas de `pulseCount` directas, documentando la suposición "32-bit atomic en M7". Si se quisiera 100% portable, un helper `readPulseAtomic()` con guarda.

**Validación:** N/A funcional; revisar que no cambie comportamiento (sólo performance).

---

### T-10 — Sin rampa de aceleración / slew-rate en el setpoint (OPORTUNIDAD) — P2

**Causa:** `steer()` aplica el setpoint nuevo **de golpe**. Cuando la RPi cambia `speed`/`steer` bruscamente (curva cerrada, `case 7` que salta de 25 a 55 RPM, ver #122/B5), o cuando una rutina hace `runTime(0,...)` seguido de `runTime(30,...)`, el setpoint salta escalón. Con el lazo saturado (T-01) el PWM va a fondo instantáneamente → **tirón mecánico**, posible pérdida de tracción de las omniwheels, micro-derrape que descalibra la odometría (T-05), y pico de corriente en los 4 FIT0441 a la vez (estrés de batería 3S y posible brownout → se conecta con la familia de resiliencia #53/#27).

**Riesgo de NO tocar:** arranques/frenadas bruscos → pérdida de línea en transiciones, derrape en giros, y picos de consumo. No bloquea pero resta puntaje fino y estabilidad.

**Riesgo de tocar:** medio. Una rampa mal puesta hace el robot "perezoso" (tarda en responder a correcciones de línea). Hay que limitar la rampa sólo a cambios grandes de velocidad lineal, no a las micro-correcciones de `steer`.

**Fix conceptual:** introducir un **slew-rate limiter** en el setpoint de velocidad (limitar Δrpm por unidad de tiempo) — sólo en la magnitud de avance, dejando la corrección de dirección ágil. Alternativamente, una rampa de arranque/parada en `runTime`/`runDistance`. Mantenerla suave pero no lenta. **Hacerlo DESPUÉS de T-01/T-03** (sobre un lazo que ya regula).

**Validación en banco:** medir corriente de batería (pinza amperométrica) en arranque con y sin rampa; verificar que el robot no derrape en arranque (marca de tiza en piso) y que el tiempo de respuesta a una corrección de línea no se degrade.

---

### T-11 — `PID::Reset()` parcial deja `lastInput`/`lastTime` viejos — P2 (NUEVO)

**Código (`PID.cpp:104-106`):** `void PID::Reset() { outputSum = 0; }` y `Moto::reset()` (drivebase.cpp:98-100) lo llama. `DriveBase::reset()` resetea los 4.

**Causa:** `Reset()` limpia el integrador pero **no** reinicia `lastInput` ni `lastTime`. Tras un reset, el primer `Compute()`: (a) calcula `dInput = input - lastInput` con un `lastInput` potencialmente muy viejo → **patada derivativa** (mitigada hoy porque `kd=0`); (b) `timeChange = now - lastTime` puede ser enorme si pasó mucho entre reset y el siguiente compute, disparando un cómputo inmediato. Es una bomba latente que se activa **si se le pone `kd≠0`** (T-03).

**Riesgo de NO tocar:** nulo hoy (`kd=0`). Se vuelve real si se sintoniza con derivativo.

**Riesgo de tocar:** muy bajo.

**Fix conceptual:** que `Reset()` haga lo de `Initialize()`: `outputSum=*myOutput; lastInput=*myInput; lastTime=millis();` (o similar), para un reinicio "bumpless". Documentar cuándo se debe llamar.

**Validación:** con `kd≠0` de prueba, verificar que tras un `reset()` no haya salto de PWM en el primer ciclo.

---

## 3. Reparto de velocidad `steer()` — análisis dedicado

`steer()` (drivebase.cpp:110-155) reparte así (validado contra los comentarios empíricos de `test/actuators/motors_move.cpp:286-291`, que son la "verdad de campo" de los alumnos):

```
rotation>=0 (giro a IZQUIERDA): derecha = base; izquierda = base·(1 - 2·rotation)
rotation<0  (giro a DERECHA):   izquierda = base; derecha  = base·(1 + 2·rotation)
```
- `rotation=±1` ⇒ la rueda interna recibe `base·(-1)`, se detecta `<0`, se invierte su dir y se manda a `|base|` hacia atrás ⇒ **giro sobre el eje** (una banda adelante, otra atrás). Coincide con el comentario `robot.steer(10,FORWARD,1) // izq: atras | der: frente`. **Correcto.**
- **Observaciones:**
  1. **`constrain(speed, 0, 159)`** (línea 112) impide velocidad negativa: el sentido siempre viene por `direction`/`dir`, nunca por signo de `speed`. Coherente con el resto del código. OK.
  2. **Espejado del chasis:** `_fr->setSpeed(!_rightdir, ...)` y `_br->setSpeed(!_rightdir, ...)` — las ruedas derechas reciben el `dir` **negado**. Esto es porque los motores derechos están montados espejados (giran al revés para el mismo avance). Es correcto **siempre que** el cableado `dirPin` de FR/BR esté montado como asume el código. **Riesgo:** si alguna vez se recablea un motor, este `!` queda inconsistente y una rueda irá al revés. Vale documentarlo en `hardware/cambios_de_hardware.md`.
  3. **`_leftdir`/`_rightdir` son `double`** (drivebase.h:43) aunque representan booleanos de dirección. Funciona (0.0/1.0) pero es type-smell; un `!` sobre `double` y un `digitalWrite(double)` dependen de conversión implícita. P2 de limpieza.
  4. **No hay zona muerta ni mínimo de arranque por rueda:** la rueda interna en curvas suaves puede quedar en un PWM que no la mueve (zona muerta del FIT0441) → la curva sale más cerrada de lo pedido. Se conecta con T-06/T-10.
  5. **Sin saturación conjunta:** si en una curva la rueda externa pidiera más que el máximo, no hay normalización (acá no pasa porque `base≤159` y la externa nunca supera `base`), pero conviene tenerlo en mente si se sube el tope.

**Veredicto:** la **lógica geométrica de `steer()` es correcta** y está validada empíricamente por el equipo. Los problemas del módulo **no están en el reparto** sino en el **lazo de velocidad por rueda** (T-01/02/03/07) y en la **odometría** (T-04/05). No tocar la geometría de `steer()`.

---

## 4. Conversión pulsos → grados

No existe conversión pulsos→grados en este módulo: **todos los giros usan el IMU BNO055** (`runAngle()` en main.cpp:434-530), no los encoders. Por lo tanto la odometría de los encoders se usa **sólo** para distancia lineal (`runDistance`), y los giros dependen del IMU. Esto **acota** el impacto de los bugs de encoder (T-04/05) a las maniobras lineales de rescate/reposicionamiento, no a los giros. (Los bugs de `runAngle` — signo de error, `runAngle(180)`, falta de timeout — son #B8/#125, #112 y caen en otra ficha; los menciono sólo para delimitar alcance.)

---

## 5. Orden de ataque recomendado (dependencias)

Los temas están **acoplados**; tocarlos en desorden puede empeorar. Secuencia sugerida (todo en banco, ruedas al aire primero):

1. **T-08** (init) + **T-07** (medición de RPM limpia) — prerrequisitos baratos. Sin medida confiable no se sintoniza nada.
2. **T-02** (frecuencia de control) — fijar `SampleTime`/cadencia real.
3. **T-01** (sentido del lazo) — decidir A vs B con RPM medida; verificar que regula, no satura.
4. **T-06** (histéresis) — **junto** con T-01, porque arreglar T-01 la "despierta".
5. **T-03** (sintonía kp/ki/kd) — escalón por rueda.
6. **T-05** + **T-04** (odometría: sentido + calibración) — recalibrar `PULSES_PER_CM` con el conteo ya consistente.
7. **T-10** (rampa) y **T-11** (reset bumpless) — mejoras finales sobre lazo sano.
8. **T-09** — limpieza de atomicidad/CPU (oportunista).

**Regla de oro del repo:** cada cambio = rama propia + PR + review + entrada en `testing/TEST_LOG.md` con RPM medida / distancia medida. Nada de esto se mergea sin banco (CLAUDE.md, regla 3).

---

## 6. Relación con auditorías previas (no se repiten, se citan)

- **#121 / B1** (PID invertido): **confirmado en efecto, matizado en causa** → ver T-01. La causa no es un signo suelto sino DIRECT + actuador negativo + ki dominante + kp=0; el fix "naive" `analogWrite(_pwmVal)` probablemente **empeora**. Agrego T-02 (frecuencia) y T-03 (kp=0) como co-causas no listadas en #121.
- **#126 / B10** (encoder 25 p/cm + ISR CHANGE): **confirmado** → T-04. Agrego T-05 (sentido por software se corrompe en inversión/histéresis), no contemplado en #126.
- **#67** (pulseCount sin init): **confirmado** → T-08, ampliado con `_dir`/`_pwmVal`/`_end` sin init.
- **#60** (runDistance sin timeout): fuera de mi dominio (resiliencia) pero se cruza con T-04/T-05; lo menciono sin re-auditar.
- **#59** (runDistance/runTime/runAngle no llaman claw.update()/actualizarRescate()): fuera de dominio, pero relevante: durante un `runDistance` el lazo PID **sí** corre (vía `steer`→`setSpeed`→`Compute`), pero a 10 Hz (T-02).
- **#122 / B5** (vel 55 en curva): fuera de dominio puro de drivebase pero T-10 (rampa) y T-06 (zona muerta) inciden en cómo se siente ese 55.

---

## 7. Conclusión

El **reparto de velocidad `steer()` es correcto** y está validado por el equipo; **no tocarlo**. El núcleo de problemas del módulo de control está en el **lazo de velocidad por rueda**: el PID **no regula, satura** (T-01), corre a **10 Hz** por desfase de `SampleTime` (T-02), es **I-puro** (T-03) y se alimenta de una **medición de RPM mal formada** (T-07). En paralelo, la **odometría lineal** arrastra una **constante sin calibrar** (T-04) y un **conteo de sentido que se corrompe en frenadas/inversiones** (T-05), con una **histéresis de dirección peligrosa** (T-06) que hoy está dormida por la saturación pero que **se despierta al arreglar el PID**.

El riesgo dominante para Incheon no es que "no ande" (anda, saturado), sino: **(a)** imposibilidad de control fino de velocidad → tracción despareja, deriva en recto, tirones en curva; **(b)** distancias de rescate sistemáticamente erróneas (~2×) → recolección/depósito poco repetibles, que es justo donde está el puntaje de víctimas y la auto-recuperación 8/10 que el equipo busca. Son temas **acoplados y delicados**: la recomendación fuerte es atacarlos **en el orden de la sección 5**, **en banco con ruedas al aire**, midiendo RPM y distancia reales, y **no** aplicar el fix naive de #B1 a ciegas.
