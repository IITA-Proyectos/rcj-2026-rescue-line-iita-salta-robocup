# Programa Laureano — Teensy Resiliencia (Incheon 2026)

> **Código propuesto** (no es código del robot). Índice de docs y estado vigente: [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). **Reinterpretación del PID #121 vigente** (motores DFRobot FIT0441 con PWM invertido: `255 - _pwmVal` correcto; el problema es el lazo PID DIRECT + ki dominante + kp=0, es rediseño, NO un fix de signo). El régimen "Track A push ≤05-26" es histórico → hoy firmware entra por gate de Enzo; buena parte de estos fixes vive en **PR #129 (OPEN), validar en banco**. Fechas internas = foto del 18-may.

> **AVISO IMPORTANTE — LEER ANTES DE TOCAR CUALQUIER ARCHIVO:**
> Todo el código que aparece en este documento es una **PROPUESTA** para que Laureano (Laureano Monteros, `Laumonteros`) valide, adapte y pruebe.
> **NO está commiteado en ninguna rama.** Laureano lo revisa, lo ajusta a la realidad del hardware que tiene en banco, lo prueba, y **EL hace el commit y el PR.**
> El coach (Gustavo) o cualquier otro colaborador NO deben hacer push de estos snippets directamente.

---

## Contexto: qué pasó con el commit `5bac4a5`

El commit `5bac4a5` (`feat(teensy): timeouts implementados`) agregó ~180 líneas de infraestructura de resiliencia a `main.cpp`:

- Archivo `src/priority_fix_flags.h` con feature flags en tiempo de compilación.
- Funciones `fixIssue60Enabled()`, `fixIssue61Enabled()`, `fixIssue62Enabled()` (y otras).
- Función `serviceMotionBackgroundTasks()` — mantiene `claw.update()` y la FSM de rescate activas durante movimientos bloqueantes.
- Timeout en `runDistance()` — sale del loop por tiempo máximo estimado.
- Timeout en `get_color()` — sale del `while (!apds.colorDataReady())` en 50 ms.
- Flag global `color_sensor_ok` — si el APDS9960 falla en `setup()`, no se bloquea en `get_color()`.
- Señal visual/audible de fallo de sensor en `setup()` (`blinkVisibleError`, `fatalSensorInitLoop`).

El commit `cead75e` (`fix(teensy): error de libreria claw.cpp`) revirtió las 181 líneas de `main.cpp` como efecto colateral al arreglar `claw.cpp`. El archivo `priority_fix_flags.h` también desapareció. La **branch activa `c42e535` NO tiene nada de ese código**.

**La tarea principal del Sprint 1 es recuperar ese código, adaptarlo, y también agregar el fix de `runAngle()` (#112) que nunca existió.**

---

## Orden de ataque recomendado

| Sprint | Issues | Requiere robot | Descripción |
|--------|--------|---------------|-------------|
| Sprint 1 | #60, #61, #62, #112 | NO — se escribe HOY en cualquier PC | Re-aplicar timeouts y fixes del `5bac4a5` + timeout `runAngle()` |
| Sprint 2 | #53, #27 | SI — requiere banco con Teensy y RPi | Heartbeat serial failsafe + watchdog hardware WDT_T4 |
| Sprint 3 | #109, #72, #67, #59 | SI — requiere banco completo con sensores | BNO055 runtime fault + resync + encoders + FSM rescate |

---

## SPRINT 1 — Sin robot, se escribe YA

### Issue #60 — `runDistance()` puede colgar infinito si encoder falla

**Archivo:** `software/teensy/firmware/src/main.cpp`, funcion `runDistance()` (~línea 533)

**Qué falla:** si un encoder deja de contar (cable suelto, ISR perdida, mecánica), el `while(true)` nunca sale. El robot se queda girando en el lugar indefinidamente. En competencia = corrida perdida.

**Origen del fix:** el commit `5bac4a5` ya lo tenía. Fue revertido por error en `cead75e`.

**Codigo propuesto — dos archivos:**

#### Archivo 1: `src/priority_fix_flags.h` (crear nuevo, no existe en `c42e535`)

```cpp
// software/teensy/firmware/src/priority_fix_flags.h
// Feature flags para activar fixes de resiliencia de forma segura.
// Cada flag arranca en false — Laureano los activa de a uno en banco.
// Cuando todos esten validados, poner kEnableAllPriorityFixes = true.
#pragma once

namespace priority_fix_flags
{
    // Maestro: activa todos los fixes a la vez (usar solo cuando todos esten banqueados)
    inline constexpr bool kEnableAllPriorityFixes = false;

    // #60 — timeout en runDistance() para salir si encoder no cuenta
    inline constexpr bool kFixIssue60RunDistanceTimeout = true;

    // #61 — timeout en get_color() para salir si APDS9960 no responde
    inline constexpr bool kFixIssue61ColorSensorTimeout = true;

    // #62 — LED+buzzer visible en setup() si sensor falla al init
    inline constexpr bool kFixIssue62VisibleSensorInitFailures = true;

    // #112 — timeout en runAngle() para salir si BNO055 no converge
    inline constexpr bool kFixIssue112RunAngleTimeout = true;

} // namespace priority_fix_flags
```

> NOTA para Laureano: los flags que ya banqueaste los pones en `true`. Los que todavia no validaste los dejas en `false`. Eso te permite mergear de forma incremental sin romper lo que ya funciona.

#### Archivo 2: parche sobre `main.cpp` para `runDistance()`

En `main.cpp`, agregar los includes y declaraciones antes del enum `RescateState` (despues de la linea `int ball_counter=2;`):

```cpp
// --- RESILIENCIA: agregar inmediatamente despues de "int ball_counter=2;" ---
#include "priority_fix_flags.h"

bool color_sensor_ok = true;           // true = APDS9960 inicializo OK
bool rescateUpdateInProgress = false;  // mutex simple para actualizarRescate()

// Forward declarations (necesarias porque las funciones estan definidas despues)
void actualizarRescate();
void runTime(int speed, int dir, double steer, unsigned long long time);
void runAngle(int speed, int dir, double angle);
void runDistance(int speed, int dir, int Distance);

// Estima el timeout maximo en ms para runDistance()
// Formula: distancia / velocidad_estimada * 1.5 + 500ms margen
unsigned long computeRunDistanceTimeoutMs(int speed, int distance)
{
    unsigned long distanceCm = static_cast<unsigned long>(abs(distance));
    int effectiveSpeed = speed > 0 ? speed : 30;
    // ~3/4 de la velocidad nominal como estimacion conservadora
    unsigned long estimatedSpeedCmPerSecond = static_cast<unsigned long>(max(8, effectiveSpeed * 3 / 4));
    unsigned long estimatedMs = (distanceCm * 1000UL) / estimatedSpeedCmPerSecond;
    return (estimatedMs * 3UL) / 2UL + 500UL;
}

// Mantiene claw y FSM rescate vivas durante movimientos bloqueantes
void serviceMotionBackgroundTasks()
{
    claw.update();
    actualizarRescate();
}
```

Luego, reemplazar la funcion `runDistance()` completa (lineas ~533-589 en `c42e535`):

```cpp
void runDistance(int speed, int dir, int Distance) {
    runTime(30, BACKWARD, 0, 20);
    runTime(30, FORWARD, 0, 20);
    reset_enconder();
    int32_t encoder = 25 * Distance;

    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);

    if (dir == FORWARD) {
        while (true) {
            // #60 — timeout: sale si encoder no progresa
            if (priority_fix_flags::kFixIssue60RunDistanceTimeout &&
                (millis() - startTime) >= timeoutMs) {
                Serial.println("[WARN] runDistance FORWARD timeout — salida por tiempo");
                break;
            }
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;
            if (frCount >= encoder || flCount >= encoder) break;

            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();  // #59 — mantiene claw y FSM vivos
            Serial.print(flCount);
            Serial.print(" | ");
            Serial.print(frCount);
            digitalWrite(13, HIGH);
            delay(10);

            if (Serial5.available() > 0) {
                int lecturas = Serial5.read();
                Serial.print(lecturas);
            }
            if (digitalRead(32) == 1) {
                Serial5.write(255);
                break;
            }
        }
    } else {
        while (true) {
            // #60 — timeout: sale si encoder no progresa
            if (priority_fix_flags::kFixIssue60RunDistanceTimeout &&
                (millis() - startTime) >= timeoutMs) {
                Serial.println("[WARN] runDistance BACKWARD timeout — salida por tiempo");
                break;
            }
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;
            if (frCount <= -encoder || flCount <= -encoder) break;

            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();  // #59 — mantiene claw y FSM vivos
            Serial.print(flCount);
            Serial.print(" | ");
            Serial.print(frCount);
            delay(10);

            if (Serial5.available() > 0) {
                int lecturas = Serial5.read();
                Serial.print(lecturas);
            }
            if (digitalRead(32) == 1) {
                Serial5.write(255);
                break;
            }
        }
    }

    // Para el robot limpiamente al salir (sea por encoder, timeout o switch)
    if (priority_fix_flags::kFixIssue60RunDistanceTimeout) {
        robot.steer(0, dir, 0);
    }
}
```

**Cómo validar en banco (#60):**

1. Conectar Teensy. Llamar `runDistance(30, FORWARD, 50)` desde el loop.
2. **Test A — camino normal:** encoders funcionando. Verificar que sale cuando frCount >= 1250 (= 25 * 50). El robot debe parar limpiamente.
3. **Test B — encoder muerto:** desconectar el cable del encoder de FR (pin 2) antes de llamar. Verificar que sale despues de `timeoutMs` (~4500 ms para 50 cm a speed=30) y imprime el mensaje `[WARN]`. El robot debe parar.
4. Ambos tests sin que el Teensy se cuelgue ni requiera reset manual.

**Checklist de aprobacion (#60):**

- [ ] Compila sin warnings con `pio run`
- [ ] Test A: sale por encoder, robot para limpio
- [ ] Test B: sale por timeout, robot para limpio, mensaje en Serial
- [ ] `kFixIssue60RunDistanceTimeout = true` en flags (no en modo maestro todavia)
- [ ] Resultado documentado en `testing/TEST_LOG.md` con fecha, test y resultado
- [ ] PR referencia `Closes #60`

---

### Issue #61 — `get_color()` bloquea indefinido si APDS9960 no responde

**Archivo:** `main.cpp`, funcion `get_color()` (~linea 331)

**Qué falla:** el `while (!apds.colorDataReady()) { delay(5); }` no tiene salida si el sensor se cuelga o pierde I2C. El robot se paraliza leyendo color para siempre. En rescate esto es critico.

**Codigo propuesto — reemplazar `get_color()` completa:**

```cpp
String get_color()
{
    // #62 — si el sensor no inicializo, no intentar leer
    if (priority_fix_flags::kFixIssue61ColorSensorTimeout && !color_sensor_ok) {
        return "Desconocido";
    }

    uint16_t r, g, b, c;
    unsigned long waitStart = millis();

    // #61 — timeout de 50 ms para colorDataReady()
    while (!apds.colorDataReady())
    {
        if (priority_fix_flags::kFixIssue61ColorSensorTimeout &&
            (millis() - waitStart) > 50) {
            Serial.println("[WARN] get_color timeout — APDS9960 no responde");
            return "Desconocido";
        }
        delay(5);
    }

    apds.getColorData(&r, &g, &b, &c);

    String closest_color = "Desconocido";
    uint32_t min_error = UINT32_MAX;

    for (size_t i = 0; i < sizeof(known_colors) / sizeof(known_colors[0]); i++)
    {
        uint32_t error = pow(known_colors[i].r - r, 2) +
                         pow(known_colors[i].g - g, 2) +
                         pow(known_colors[i].b - b, 2) +
                         pow(known_colors[i].c - c, 2);
        if (error < min_error)
        {
            min_error = error;
            closest_color = known_colors[i].name;
        }
    }

    return closest_color;
}
```

**Cómo validar en banco (#61):**

1. **Test A — normal:** sensor conectado. Llamar `get_color()` 100 veces en loop. Verificar que nunca tarda mas de 20 ms ni retorna siempre "Desconocido".
2. **Test B — sensor colgado:** desconectar SDA del APDS9960 en caliente (con el robot corriendo). Verificar que `get_color()` retorna `"Desconocido"` en menos de 60 ms y el robot no se cuelga.
3. **Test C — init fallido:** desconectar el sensor antes de encender. Verificar que `color_sensor_ok` queda en `false` (ver issue #62 abajo) y `get_color()` retorna `"Desconocido"` instantaneamente sin entrar al while.

**Checklist de aprobacion (#61):**

- [ ] Compila sin warnings
- [ ] Test A: respuesta < 20 ms en condicion normal
- [ ] Test B: no se cuelga con sensor desconectado, mensaje en Serial
- [ ] Test C: retorno instantaneo cuando `color_sensor_ok == false`
- [ ] Resultado en `testing/TEST_LOG.md`
- [ ] PR referencia `Closes #61`

---

### Issue #62 — Fallo de sensor en `setup()` no es visible

**Archivo:** `main.cpp`, funcion `setup()` (~linea 736)

**Qué falla:** si el BNO055 o el APDS9960 fallan al init, el comportamiento es un `while(1)` silencioso (BNO055) o simplemente se ignora (APDS9960). No hay señal visual ni auditiva. El operador no sabe que el robot esta muerto.

**Codigo propuesto — helpers y parche de `setup()`:**

Agregar junto a las otras funciones auxiliares (antes de `setup()`):

```cpp
// --- #62 — Señalizacion visible de errores de inicializacion ---

// Parpadea LED rojo + buzzer N veces. Usa delay(), OK en setup().
void blinkVisibleError(unsigned long onMs, unsigned long offMs, int cycles)
{
    for (int i = 0; i < cycles; ++i) {
        digitalWrite(LED_ROJO, HIGH);
        digitalWrite(BUZZER, HIGH);
        delay(onMs);
        digitalWrite(LED_ROJO, LOW);
        digitalWrite(BUZZER, LOW);
        delay(offMs);
    }
}

// Bucle de error fatal (sensor critico): parpadeo rapido continuo, nunca sale.
void fatalSensorInitLoop()
{
    while (true) {
        digitalWrite(LED_ROJO, HIGH);
        digitalWrite(BUZZER, HIGH);
        delay(200);
        digitalWrite(LED_ROJO, LOW);
        digitalWrite(BUZZER, LOW);
        delay(800);
    }
}
```

Reemplazar el bloque de init del BNO055 en `setup()`:

```cpp
    // Initialise BNO055
    if (!bno.begin())
    {
        Serial.println("[ERROR] No BNO055 detected — revisar cableado o I2C ADDR!");
        if (priority_fix_flags::kFixIssue62VisibleSensorInitFailures)
        {
            fatalSensorInitLoop();  // Parpadeo continuo, no arranca
        }
        while (1);  // fallback si el flag esta apagado
    }
    bno.setExtCrystalUse(true);
```

Reemplazar el bloque de init del APDS9960 en `setup()`:

```cpp
    // Initialise APDS9960 Color Sensor
    color_sensor_ok = apds.begin();
    if (!color_sensor_ok)
    {
        Serial.println("[WARN] APDS9960 no inicializo — sensor de color deshabilitado");
        if (priority_fix_flags::kFixIssue62VisibleSensorInitFailures)
        {
            blinkVisibleError(120, 120, 3);  // 3 destellos rapidos = advertencia
        }
    }

    // Habilitar modo color solo si el sensor inicializo
    if (color_sensor_ok) {
        apds.enableColor(true);
    }
```

**Cómo validar en banco (#62):**

1. **Test A — BNO055 desconectado al encender:** verificar que LED rojo parpadea continuo (200ms on / 800ms off), buzzer suena al mismo ritmo, robot no arranca.
2. **Test B — APDS9960 desconectado al encender:** verificar 3 destellos rapidos (120ms), robot arranca (BNO055 OK), color devuelve `"Desconocido"` siempre.
3. **Test C — todo conectado:** verificar que NO parpadea nada extra en el boot, comportamiento identico al actual.

**Checklist de aprobacion (#62):**

- [ ] Compila sin warnings
- [ ] Test A: parpadeo continuo visible, robot no arranca
- [ ] Test B: 3 destellos, robot arranca con `color_sensor_ok == false`
- [ ] Test C: boot limpio sin señales extra
- [ ] Resultado en `testing/TEST_LOG.md`
- [ ] PR referencia `Closes #62`

---

### Issue #112 — `runAngle()` puede colgar si BNO055 no converge

**Archivo:** `main.cpp`, funcion `runAngle()` (~linea 434)

**Qué falla:** el `while(true)` de `runAngle()` no tiene timeout. Si el BNO055 da lecturas erraticas (ruido, cable suelto, EMI de los motores) o el robot mecanicamente no puede alcanzar el angulo objetivo (traba, superficie resbaladiza), el loop jamas sale. El dreno de bytes del Serial5 tampoco existe — si la RPi manda datos durante el giro, el buffer se llena y los bytes subsiguientes se corrompen.

**Este fix nunca existio en `5bac4a5`; Laureano lo escribe por primera vez.**

**Codigo propuesto — reemplazar `runAngle()` completa:**

```cpp
void runAngle(int speed, int dir, double angle)
{
    sensors_event_t event;
    bno.getEvent(&event);
    float initialAngle = event.orientation.x;
    float targetAngle = initialAngle + angle;

    // Normalizar el angulo objetivo al rango 0-360
    targetAngle = fmod(targetAngle, 360.0);
    if (targetAngle < 0) targetAngle += 360;

    // #112 — Timeout: tiempo maximo para completar el giro.
    // Formula conservadora: 1 grado/segundo minimo para el robot.
    // Para 180 grados = 5s; para 90 grados = 3s. Siempre al menos 2s.
    const unsigned long TIMEOUT_MS_PER_DEGREE = 25UL; // 25ms por grado = ~2 seg para 90°
    unsigned long timeoutMs = max(2000UL, (unsigned long)(fabs(angle) * TIMEOUT_MS_PER_DEGREE));
    unsigned long startTime = millis();

    while (true)
    {
        bno.getEvent(&event);
        float currentAngle = event.orientation.x;

        // #112 — Dreno serial: leer y descartar bytes del Serial5 durante el giro
        while (Serial5.available() > 0) {
            Serial5.read();  // dreno — los datos llegarán de nuevo post-giro
        }

        if (digitalRead(32) == 1) {
            Serial5.clear();
            Serial5.write(255);
            break;
        }

        // #112 — Timeout: sale si el giro no termina en tiempo maximo
        if (priority_fix_flags::kFixIssue112RunAngleTimeout &&
            (millis() - startTime) >= timeoutMs) {
            Serial.print("[WARN] runAngle timeout — angulo no alcanzado. Error: ");
            float finalError = targetAngle - currentAngle;
            if (finalError > 180) finalError -= 360;
            if (finalError < -180) finalError += 360;
            Serial.println(fabs(finalError));
            break;
        }

        // Calcular la diferencia mas corta entre los angulos
        float error = targetAngle - currentAngle;
        if (error > 180) error -= 360;
        if (error < -180) error += 360;

        if (fabs(error) <= 1.0) break;

        // Logica de giro (sin cambios respecto al codigo actual)
        if (angle == 180)
        {
            robot.steer(speed, dir, 1);
        }
        else if (angle == 90 || angle == -270)
        {
            robot.steer(speed, dir, (error > 0 && error <= 180) ? -1.0 : 1.0);
        }
        else if (angle == -90 || angle == 270)
        {
            robot.steer(speed, dir, (error < 0 && error >= -180) ? 1.0 : -1.0);
        }
        else if (angle == 45 || angle == -315)
        {
            robot.steer(speed, dir, (error > 0 && error <= 180) ? -1.0 : 1.0);
        }
        else if (angle == -45 || angle == 315)
        {
            robot.steer(speed, dir, (error < 0 && error >= -180) ? 1.0 : -1.0);
        }
        else if (angle > 0)
        {
            robot.steer(speed, dir, -1);
        }
        else if (angle < 0)
        {
            robot.steer(speed, dir, 1);
        }
    }
    robot.steer(0, FORWARD, 0);
}
```

**Cómo validar en banco (#112):**

1. **Test A — giro normal:** pedir `runAngle(25, FORWARD, 90)` en superficie lisa. Verificar que completa en < 3s y para limpio.
2. **Test B — giro forzado a fallar:** bloquear fisicamente las ruedas con la mano durante `runAngle(25, FORWARD, 90)`. Verificar que sale despues del timeout (~2.25s), imprime el mensaje `[WARN]` con el error angular, y el robot para.
3. **Test C — dreno serial:** conectar la RPi enviando datos continuos durante el giro. Verificar que post-giro el Serial5 retoma sincronismo y el primer byte que llega es el marcador 255.

**Checklist de aprobacion (#112):**

- [ ] Compila sin warnings
- [ ] Test A: giro normal completa correctamente
- [ ] Test B: sale por timeout, para limpio, mensaje en Serial
- [ ] Test C: serial retoma sincronismo post-giro
- [ ] `kFixIssue112RunAngleTimeout = true` en flags
- [ ] Resultado en `testing/TEST_LOG.md`
- [ ] PR referencia `Closes #112`

---

## SPRINT 2 — Requiere banco con Teensy + Serial5 activo (antes del 26-may)

### Issue #53 — Sin heartbeat serial: si RPi se cuelga, Teensy no lo detecta

**Archivo:** `main.cpp`, `serialEvent5()` (~linea 383) y zona de loop principal.

**Qué falla:** el protocolo actual es puramente reactivo — la Teensy solo actua cuando llegan bytes. Si la RPi se cuelga, se reinicia o pierde la UART, la Teensy sigue ejecutando el ultimo `speed` y `steer` recibidos indefinidamente. En pista abierta = robot descontrolado.

**Propuesta de implementacion — heartbeat + failsafe:**

El mecanismo requiere coordinacion con el lado RPi (que debe enviar el heartbeat). Verificar con Enzo/Benjamin que la RPi puede enviar el byte 0xFE (254 esta tomado — usar otro marcador, ver abajo) cada ~200ms.

```cpp
// --- #53 — Heartbeat y failsafe serial ---
// Agregar cerca de las otras variables globales (~linea 52):

// Marcador de heartbeat: la RPi manda este byte cada HEARTBEAT_INTERVAL_MS
// IMPORTANTE: no puede colisionar con los marcadores de protocolo (255,254,253,252)
// Usar 0xF0 = 240 (libre en el protocolo actual)
static const int HEARTBEAT_BYTE = 240;
static const unsigned long HEARTBEAT_TIMEOUT_MS = 600;  // 3x el intervalo RPi
static unsigned long lastHeartbeatMs = 0;
static bool heartbeatReceived = false;

// Agregar dentro de serialEvent5(), en el switch de data:
//   else if (data == HEARTBEAT_BYTE)
//       lastHeartbeatMs = millis();
//
// Reemplazar el cuerpo de serialEvent5() completo:

void serialEvent5()
{
    if (Serial5.available() > 0)
    {
        int data = Serial5.read();

        // #53 — heartbeat: resetea el timer de watchdog serial
        if (data == HEARTBEAT_BYTE) {
            lastHeartbeatMs = millis();
            return;
        }

        if (data == 255)
            serial5state = 0;
        else if (data == 254)
            serial5state = 1;
        else if (data == 253)
            serial5state = 2;
        else if (data == 252)
            serial5state = 3;
        else if (serial5state == 0)
            speed = (double)data / 100 * 100;
        else if (serial5state == 1)
            steer = ((double)data - 90) / 90;
        else if (serial5state == 2)
            green_state = data;
        else if (serial5state == 3)
            silver_line = data;
    }
}

// Funcion de chequeo de heartbeat — llamar desde loop() al inicio:
bool serialHeartbeatOk()
{
    // Si nunca recibimos un heartbeat, no activar failsafe
    // (permite arrancar sin RPi conectada para test de firmware)
    if (lastHeartbeatMs == 0) return true;
    return (millis() - lastHeartbeatMs) < HEARTBEAT_TIMEOUT_MS;
}

// En loop(), al inicio del bloque principal (antes de if (digitalRead(32) == 1)):
// Agregar:
//
//   if (!serialHeartbeatOk()) {
//       robot.steer(0, FORWARD, 0);  // failsafe: para motores
//       // Opcional: buzzer corto cada 1s para alertar al operador
//       return;
//   }
```

**IMPORTANTE para Laureano:** antes de implementar, confirmar con Benjamin/Enzo que el lado RPi puede enviar el byte 240 cada 200ms sin romper el protocolo existente. El byte 240 no esta en el protocolo actual pero hay que verificarlo en `software/raspberry/final_rpi/Main.py`.

**Cómo validar en banco (#53):**

1. **Test A — RPi conectada y enviando heartbeat:** robot opera normal. `serialHeartbeatOk()` retorna true siempre.
2. **Test B — RPi desconectada despues de conectar:** desconectar cable UART con robot corriendo. Despues de 600ms, robot debe parar (speed=0). Buzzer opcional.
3. **Test C — RPi reinicia:** simular reinicio de RPi (cortar y reconectar en < 2s). Verificar que robot para durante el reinicio y retoma cuando llegan heartbeats nuevos.

**Checklist de aprobacion (#53):**

- [ ] Coordinacion con lado RPi confirmada (byte 240 no colisiona)
- [ ] Test A: operacion normal con heartbeat
- [ ] Test B: robot para en < 700ms sin heartbeat
- [ ] Test C: retoma operacion al volver el heartbeat
- [ ] Resultado en `testing/TEST_LOG.md`
- [ ] PR referencia `Closes #53`

---

### Issue #27 — Sin watchdog hardware: si el firmware se cuelga, el robot no se resetea

**Archivo:** `main.cpp`, `setup()` y `loop()`.

**Qué falla:** si el firmware entra en un estado imposible (stack overflow, corrupcion de memoria, loop infinito no previsto), el Teensy se queda colgado sin recuperarse. El watchdog de hardware de Teensy 4.1 (WDOG1, via libreria `WDT_T4`) parchea esto: si el firmware no "patear" el watchdog periodicamente, el MCU se resetea automaticamente.

**ADVERTENCIA:** el watchdog reset borra los estados de `speed`, `steer`, `green_state`, `rutina`, etc. La FSM vuelve a `startUp = false`. El robot se detiene y espera el switch — comportamiento correcto en competencia.

**Propuesta:**

```cpp
// --- #27 — Watchdog hardware WDT_T4 ---
// Agregar al inicio de los includes:
#include <WDT_T4.h>

// Callback cuando el watchdog va a disparar (llamado ~1s antes del reset):
void watchdogCallback()
{
    // Para motores antes del reset
    robot.steer(0, FORWARD, 0);
    // Señal auditiva/visual de que el WDT disparo
    digitalWrite(BUZZER, HIGH);
    digitalWrite(LED_ROJO, HIGH);
    // No hacer delay aqui — el reset viene en ~1s
    Serial.println("[CRITICAL] Watchdog timeout — robot se resetea!");
}

// Variable global para el watchdog
WDT_T4<WDT1> wdt;  // Usar WDOG1 del Teensy 4.1

// En setup(), al FINAL (despues de claw.begin()):
//   WDT_T4_Config cfg;
//   cfg.timeout = 5000;   // 5 segundos sin patear = reset
//   cfg.callback = watchdogCallback;
//   wdt.begin(cfg);
//
// En loop(), al inicio del bloque principal (cada iteracion):
//   wdt.feed();            // "patear" el watchdog — estoy vivo
```

**IMPORTANTE para Laureano:** la libreria `WDT_T4` debe estar en `platformio.ini` como dependencia. Verificar que este o agregar `wlbmtbw/WDT_T4@^1.3.0` en `lib_deps`. Revisar que el `timeout` de 5000ms es suficientemente largo para las operaciones mas lentas del robot (como `runDistance` en distancias largas — con el timeout de #60 ya garantizado, 5s es conservador).

**Cómo validar en banco (#27):**

1. **Test A — operacion normal:** robot corriendo, verificar que wdt.feed() se llama > 1 vez por segundo y el watchdog no dispara.
2. **Test B — simular cuelgue:** agregar temporalmente un `while(true) {}` en un path del codigo. Verificar que despues de 5s el robot hace buzzer+LED rojo y se resetea.
3. **Test C — reset limpio:** despues del reset por watchdog, verificar que el robot queda en estado detenido esperando el switch, no en un estado corrupto.

**Checklist de aprobacion (#27):**

- [ ] `WDT_T4` en `platformio.ini`
- [ ] Compila sin warnings
- [ ] Test A: no dispara watchdog en operacion normal de 5 min
- [ ] Test B: dispara en ~5s, robot para, buzzer suena
- [ ] Test C: post-reset robot en estado limpio
- [ ] Resultado en `testing/TEST_LOG.md` con duracion del test
- [ ] PR referencia `Closes #27`

---

## SPRINT 3 — Requiere banco completo con todos los sensores (post-gate Enzo)

### Issue #109 — BNO055: sin deteccion de fallo en runtime

**Archivo:** `main.cpp`, `leer_yaw()` y cualquier llamada a `bno.getEvent()`.

**Qué falla:** si el BNO055 pierde comunicacion I2C durante la corrida (golpe, cable, EMI), `getEvent()` devuelve el ultimo valor conocido o datos basura. `runAngle()` intenta girar a un angulo que nunca llega y (sin #112) cuelga. Con #112 sale, pero no sabe que el IMU esta muerto.

**Propuesta (boceto — Laureano ajusta en banco):**

```cpp
// #109 — Deteccion de fallo runtime del BNO055
// Estrategia: verificar que el IMU actualiza (el valor cambia en tiempo razonable)

static float lastBnoYaw = -999.0f;
static unsigned long lastBnoChangeMs = 0;
static bool bnoRuntimeOk = true;
const unsigned long BNO_STUCK_TIMEOUT_MS = 2000;  // 2s sin cambio = fallo

bool checkBnoHealth()
{
    sensors_event_t event;
    bno.getEvent(&event);
    float yaw = event.orientation.x;

    if (fabs(yaw - lastBnoYaw) > 0.1f) {  // valor cambio
        lastBnoYaw = yaw;
        lastBnoChangeMs = millis();
        bnoRuntimeOk = true;
    } else if ((millis() - lastBnoChangeMs) > BNO_STUCK_TIMEOUT_MS) {
        bnoRuntimeOk = false;
    }
    return bnoRuntimeOk;
}

// Intento de re-init (llamar cuando bnoRuntimeOk == false):
bool tryReinitBno()
{
    Serial.println("[WARN] BNO055 stuck — intentando re-init...");
    if (bno.begin()) {
        bno.setExtCrystalUse(true);
        delay(200);
        lastBnoChangeMs = millis();
        bnoRuntimeOk = true;
        Serial.println("[INFO] BNO055 re-init OK");
        return true;
    }
    Serial.println("[ERROR] BNO055 re-init FAIL");
    return false;
}
```

> NOTA para Laureano: `checkBnoHealth()` debe llamarse periodicamente desde `loop()`. Cuando `bnoRuntimeOk == false`, `runAngle()` debe ser llamada con cuidado (puede retornar inmediatamente si el IMU esta muerto). Ajustar el umbral `0.1f` en banco — si el robot esta parado el IMU no deberia cambiar, pero hay drift de ~0.05 grados/segundo en BNO055.

**Cómo validar en banco (#109):**

1. Desconectar SDA del BNO055 en caliente. Verificar que `bnoRuntimeOk` pasa a `false` en < 2.5s.
2. Reconectar SDA. Verificar que el re-init funciona y `bnoRuntimeOk` vuelve a `true`.

---

### Issue #72 — Sin resincronizacion post-reset del protocolo serial

**Archivo:** `main.cpp`, `serialEvent5()` y las variables `speed`, `steer`, `green_state`, `silver_line`.

**Qué falla:** despues de un reset del Teensy (watchdog #27, power cycle, etc.), las variables de estado quedan en sus valores de inicializacion (`speed=0`, `steer=0`, `green_state=0`). Pero el `serial5state` queda en `0` (estado inicial). Si la RPi reinicia el protocolo enviando `[255, speed, 254, ...]` desde el principio, funciona. El problema es si el Teensy se resetea en medio de un paquete — el primer byte recibido puede ser un valor de datos, no un marcador, y se interpreta mal.

**Propuesta (boceto):**

```cpp
// #72 — Post-reset: esperar sync byte 255 antes de procesar datos
static bool serialSynced = false;

// Modificar serialEvent5():
void serialEvent5()
{
    if (Serial5.available() > 0)
    {
        int data = Serial5.read();

        // #72 — ignorar todo hasta recibir el primer marcador 255 (resync)
        if (!serialSynced) {
            if (data == 255) {
                serialSynced = true;
                serial5state = 0;
            }
            return;  // descartar bytes hasta sincronizar
        }

        if (data == HEARTBEAT_BYTE) {
            lastHeartbeatMs = millis();
            return;
        }

        // ... resto del protocolo igual ...
    }
}

// En setup(), agregar:
//   serialSynced = false;  // asegurar que empieza desincronizado
```

**Cómo validar en banco (#72):**

1. Arrancar Teensy con RPi enviando stream continuo. Verificar que la primera lectura valida de `speed` es correcta (no basura).
2. Resetear el Teensy manualmente (boton reset) con RPi activa. Verificar que despues del reset el primer comando procesado es correcto.

---

### Issue #67 — Encoders: `pulseCount` sin init, lectura no atomica, `_dir` no volatile

**Archivo:** `software/teensy/firmware/lib/drivebase/drivebase.h` y `drivebase.cpp`.

**Qué falla (tres problemas independientes):**

**A. `pulseCount` sin init:** en `drivebase.h` linea 24, `volatile long pulseCount;` no tiene valor inicial en el header. Si el constructor no lo inicializa explicitamente, queda con basura. Verificar en `drivebase.cpp` si el constructor hace `pulseCount = 0`. En la version actual **no lo hace** — `reset_enconder()` lo hace, pero solo si es llamado. Si `runDistance()` se llama antes de un `reset_enconder()`, el encoder puede empezar desde un valor basura.

**Propuesta para `drivebase.cpp`, constructor `Moto::Moto()`:**
```cpp
// Agregar al final del constructor:
pulseCount = 0;
```

**B. Lectura no atomica de `pulseCount`:** en `runDistance()`, las lineas:
```cpp
int32_t frCount = fr.pulseCount;
int32_t flCount = fl.pulseCount;
```
...leen una variable `volatile long` de 32 bits sin deshabilitar interrupciones. En Cortex-M7 (Teensy 4.1), una lectura de 32 bits es atomica en alineacion natural — pero `long` puede ser 64 bits dependiendo de la plataforma. Verificar el tamano con `sizeof(long)`. Si es 4 bytes, la lectura es atomica. Si es 8 bytes, no lo es.

**Propuesta defensiva (siempre correcta):**
```cpp
// Lectura atomica segura para cualquier tamano de long:
noInterrupts();
int32_t frCount = (int32_t)fr.pulseCount;
int32_t flCount = (int32_t)fl.pulseCount;
interrupts();
```

**C. `_dir` no volatile:** en `drivebase.h`, `int _dir` es leido en `updatePulse()` (ISR) pero escrito en `setSpeed()` (context normal). Sin `volatile`, el compilador puede cachear el valor. Cambiar a `volatile int _dir;`.

**Cómo validar en banco (#67):**

1. **Test A — init:** llamar `runDistance(30, FORWARD, 10)` inmediatamente sin `reset_enconder()` previo. Verificar que completa correctamente (si `pulseCount` empieza en 0 por el constructor).
2. **Test B — atomicidad:** no hay test directo sin oscilloscopio. La lectura atomica es una correccion defensiva — verificar que compila y el comportamiento de `runDistance` no cambia.
3. **Test C — volatile `_dir`:** correr a maxima velocidad por 10 segundos. Verificar que la direccion de conteo de pulsos es siempre correcta (no hay glitches de conteo invertido).

---

### Issue #59 — FSM de rescate: `tiemporescate` declarado pero nunca usado como timeout

**Archivo:** `main.cpp`, zona de rescate (~linea 1129) y la variable `tiemporescate` (~linea 47).

**Qué falla:** `tiemporescate = millis()` se asigna en el `case 2:` del switch (cuando la rutina pasa a "rescate"), pero nunca se lee para sacar al robot de la zona de rescate si tarda demasiado. Si el robot queda atrapado en la zona de rescate (pelota no detectada, sensor falla, la RPi no manda `green_state` esperado), el robot nunca vuelve a la linea.

**Propuesta (boceto — requiere decision de Laureano sobre el timeout correcto):**

```cpp
// #59 — Timeout de rescate: si lleva mas de N segundos en rescate, volver a linea
// Ajustar RESCATE_TIMEOUT_MS en banco segun el tiempo real de una corrida de rescate
const unsigned long RESCATE_TIMEOUT_MS = 120000UL;  // 2 minutos

// En el while (rutina == "rescate" && digitalRead(32) == 0):
// Al inicio del bucle, agregar:
//
//   if (millis() - tiemporescate > RESCATE_TIMEOUT_MS) {
//       Serial.println("[WARN] Timeout rescate — volviendo a linea");
//       robot.steer(0, FORWARD, 0);
//       rutina = "linea";
//       // Aqui va la logica de re-entry a la linea (issue #72 relacionado)
//       break;
//   }
```

> NOTA para Laureano: el valor de `RESCATE_TIMEOUT_MS` es critico y debe ajustarse en banco. Muy corto = sale antes de depositar todas las pelotas (penalizacion). Muy largo = no ayuda cuando el robot queda atrapado. El timeout de RCJ 2026 es 8 minutos total, la zona de rescate tipicamente toma 2-3 min. Discutir con Enzo el valor correcto.

---

## Resumen de dependencias entre issues

```
priority_fix_flags.h (nuevo) <-- dependen: #60, #61, #62, #112
       |
       +-- #60 runDistance timeout  (Sprint 1, sin robot)
       +-- #61 get_color timeout    (Sprint 1, sin robot)
       +-- #62 init visible         (Sprint 1, sin robot)
       +-- #112 runAngle timeout    (Sprint 1, sin robot)

serviceMotionBackgroundTasks()  <-- usada por: #60
       (ya incluida en parche #60)

heartbeat serial                <-- #53 (Sprint 2, banco)
       |
       +-- #72 resync post-reset    (Sprint 2, banco)

WDT_T4 watchdog                 <-- #27 (Sprint 2, banco)

BNO055 runtime health           <-- #109 (Sprint 3)
Encoder fixes                   <-- #67 (Sprint 3)
Rescate timeout                 <-- #59 (Sprint 3, depende de #53 conceptualmente)
```

---

## Notas finales para Laureano

1. **Empeza por `priority_fix_flags.h`**: es el prerequisito de todo Sprint 1. Si no compila, el resto no avanza.
2. **Un PR por issue o grupo coherente**: no meter #60+#61+#62+#112 en un solo PR gigante. Facilita el review y el rollback si algo falla.
3. **TEST_LOG.md es obligatorio antes de mergear**: sin entrada en el log de testing, el PR no se mergea segun las reglas del repo (CLAUDE.md regla #3).
4. **Los flags empiezan todos en `true`**: la propuesta los tiene en `true` porque ya los validaste en papel y son los mas seguros. Si un test falla, lo pones en `false` para aislar el problema.
5. **Deadline Sprint 1**: el 26-may es el gate con Enzo. El Sprint 1 se puede terminar HOY o manana sin ir al laboratorio. No hay excusa para dejarlo para despues.
6. **Este documento no es el codigo final**: es una propuesta. Si algo en banco no funciona como esperado, ajustar con criterio propio. Vos sos el que tiene el robot en frente.

---

*Documento generado por coach tecnico senior, 2026-05-18. Branch target: `feature/initialize-testing-log` @ `c42e535`. NO commiteado.*
