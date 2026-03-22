/*
  drivebase_test.cpp — Test de todas las funciones nuevas del DriveBase
  
  INSTRUCCIONES:
  1. Subir este archivo al Teensy
  2. Abrir Serial Monitor a 115200 baud
  3. Encender el switch para iniciar
  4. Cada test se ejecuta en secuencia con pausa de 3s entre ellos
  5. Observar el Serial Monitor para ver resultados
  
  TESTS EN ORDEN:
    T01 — Odometría básica (resetEncoders, getTicks, getDistanceMm)
    T02 — HeadingFromEncoders vs BNO055
    T03 — straight() bloqueante 300mm adelante y atrás
    T04 — turn() bloqueante 90° derecha e izquierda
    T05 — turn() 180°
    T06 — curve() arco 200mm radio, 90°
    T07 — startStraight() no bloqueante con cancelación
    T08 — startTurn() no bloqueante con cancelación
    T09 — drive() continuo + stop()
    T10 — isStalled() y emergencyStop()
    T11 — getTelemetry() durante movimiento
    T12 — setMaxSpeed / setMaxAccel tuning
*/

#include <Wire.h>
#include <Arduino.h>
#include <drivebase.h>
#include <PID.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include "math.h"

// ── Pines ──────────────────────────────────────────────────
#define FORWARD  0
#define BACKWARD 1
#define BUZZER   33
#define LED_ROJO 39
#define SWITCH   32

// ── Hardware ───────────────────────────────────────────────
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
Moto bl(29, 28, 27, "BL");
Moto fl(7,  6,  5,  "FL");
Moto br(36, 37, 38, "BR");
Moto fr(4,  3,  2,  "FR");
DriveBase robot(&fl, &fr, &bl, &br);

// ── ISRs ───────────────────────────────────────────────────
void ISR1() { bl.updatePulse(); }
void ISR2() { fl.updatePulse(); }
void ISR3() { br.updatePulse(); }
void ISR4() { fr.updatePulse(); }

// ── Estado ─────────────────────────────────────────────────
bool startUp = false;
int  testIndex = 0;
bool testDone  = false;

// ── Helper: imprimir separador ─────────────────────────────
void printSep(const char* title) {
    Serial.println("─────────────────────────────────────");
    Serial.println(title);
    Serial.println("─────────────────────────────────────");
}

// ── Helper: imprimir telemetría completa ───────────────────
void printTelemetry(const char* label) {
    Telemetry t = robot.getTelemetry();
    Serial.print(label);
    Serial.print("  ticks L/R: ");
    Serial.print(t.ticks_left);
    Serial.print(" / ");
    Serial.print(t.ticks_right);
    Serial.print("  dist: ");
    Serial.print(t.distance_mm, 1);
    Serial.print("mm  enc_head: ");
    Serial.print(t.heading_enc_deg, 1);
    Serial.print("°  imu_head: ");
    Serial.print(t.heading_imu_deg, 1);
    Serial.print("°  target: ");
    Serial.print(t.target, 1);
    Serial.print("  err: ");
    Serial.print(t.error, 1);
    Serial.print("  state: ");
    Serial.println(t.state);
}

// ── Helper: esperar con update() activo ────────────────────
void waitBusy() {
    while (robot.isBusy()) {
        robot.update();
        if (digitalRead(SWITCH) == 1) {
            robot.emergencyStop();
            return;
        }
    }
}

// ═══════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════

// ── T01: Odometría básica ───────────────────────────────────
void test_odometria() {
    printSep("T01 — Odometría básica");

    robot.resetEncoders();
    Serial.print("Antes de mover — L: ");
    Serial.print(robot.getLeftTicks());
    Serial.print("  R: ");
    Serial.print(robot.getRightTicks());
    Serial.print("  dist: ");
    Serial.print(robot.getDistanceMm(), 1);
    Serial.println("mm");

    // Avanzar 1 segundo a velocidad baja
    unsigned long t0 = millis();
    robot.resetEncoders();
    while (millis() - t0 < 1500) {
        robot.steer(20, FORWARD, 0);
        robot.update();
    }
    robot.steer(0, 0, 0);
    delay(200);

    Serial.print("Después 1.5s — L: ");
    Serial.print(robot.getLeftTicks());
    Serial.print("  R: ");
    Serial.print(robot.getRightTicks());
    Serial.print("  dist: ");
    Serial.print(robot.getDistanceMm(), 1);
    Serial.println("mm");
    Serial.println("► Esperado: ticks positivos, dist > 0mm");

    // Volver
    t0 = millis();
    robot.resetEncoders();
    while (millis() - t0 < 1500) {
        robot.steer(20, BACKWARD, 0);
        robot.update();
    }
    robot.steer(0, 0, 0);
}

// ── T02: HeadingFromEncoders vs BNO055 ─────────────────────
void test_heading() {
    printSep("T02 — HeadingFromEncoders vs BNO055");

    robot.resetEncoders();
    float imu_antes = robot.getTelemetry().heading_imu_deg;

    // Girar 90° con runAngle para comparar
    sensors_event_t event;
    bno.getEvent(&event);
    float target = fmod(event.orientation.x + 90.0f, 360.0f);
    while (true) {
        bno.getEvent(&event);
        float err = target - event.orientation.x;
        if (err > 180) err -= 360;
        if (err < -180) err += 360;
        if (fabs(err) <= 1.5f) break;
        robot.steer(20, FORWARD, -1);
        robot.update();
    }
    robot.steer(0, 0, 0);
    delay(300);

    float enc_head = robot.getHeadingDegFromEncoders();
    float imu_head = robot.getTelemetry().heading_imu_deg;

    Serial.print("Heading encoders: ");
    Serial.print(enc_head, 1);
    Serial.print("°  |  IMU: ");
    Serial.print(imu_head - imu_antes, 1);
    Serial.println("°");
    Serial.println("► Esperado: ambos ~90°, el IMU es más preciso");

    // Volver
    bno.getEvent(&event);
    float target2 = fmod(event.orientation.x - 90.0f + 360.0f, 360.0f);
    while (true) {
        bno.getEvent(&event);
        float err = target2 - event.orientation.x;
        if (err > 180) err -= 360;
        if (err < -180) err += 360;
        if (fabs(err) <= 1.5f) break;
        robot.steer(20, FORWARD, 1);
        robot.update();
    }
    robot.steer(0, 0, 0);
}

// ── T03: straight() bloqueante ─────────────────────────────
void test_straight() {
    printSep("T03 — straight() 300mm adelante y atrás");

    robot.resetEncoders();
    Serial.println("Avanzando 300mm...");

    robot.straight(300);   // bloqueante

    printTelemetry("Después straight(300):");
    Serial.println("► Esperado: dist ~300mm, sin desvío de heading");

    delay(1000);

    Serial.println("Retrocediendo 300mm...");
    robot.straight(-300);

    printTelemetry("Después straight(-300):");
    Serial.println("► Esperado: dist ~0mm (neto), volvió al origen");
}

// ── T04: turn() 90° ────────────────────────────────────────
void test_turn_90() {
    printSep("T04 — turn() 90° derecha e izquierda");

    float imu_antes = robot.getTelemetry().heading_imu_deg;
    Serial.print("IMU antes: ");
    Serial.print(imu_antes, 1);
    Serial.println("°");

    Serial.println("Girando 90° derecha...");
    robot.turn(90);   // bloqueante
    delay(300);

    float imu_despues = robot.getTelemetry().heading_imu_deg;
    float diff = imu_despues - imu_antes;
    if (diff > 180)  diff -= 360;
    if (diff < -180) diff += 360;
    Serial.print("IMU después: ");
    Serial.print(imu_despues, 1);
    Serial.print("°  |  diff: ");
    Serial.print(diff, 1);
    Serial.println("°");
    Serial.println("► Esperado: diff ~+90°");

    delay(1000);

    Serial.println("Girando -90° izquierda (volviendo)...");
    robot.turn(-90);
    delay(300);

    float imu_final = robot.getTelemetry().heading_imu_deg;
    float diff2 = imu_final - imu_antes;
    if (diff2 > 180)  diff2 -= 360;
    if (diff2 < -180) diff2 += 360;
    Serial.print("IMU final: ");
    Serial.print(imu_final, 1);
    Serial.print("°  |  diff total: ");
    Serial.print(diff2, 1);
    Serial.println("°");
    Serial.println("► Esperado: diff total ~0° (volvió al heading inicial)");
}

// ── T05: turn() 180° ───────────────────────────────────────
void test_turn_180() {
    printSep("T05 — turn() 180°");

    float imu_antes = robot.getTelemetry().heading_imu_deg;
    Serial.println("Girando 180°...");
    robot.turn(180);
    delay(300);

    float diff = robot.getTelemetry().heading_imu_deg - imu_antes;
    if (diff > 180)  diff -= 360;
    if (diff < -180) diff += 360;
    Serial.print("diff: ");
    Serial.print(diff, 1);
    Serial.println("°");
    Serial.println("► Esperado: ~180°");

    delay(1000);
    Serial.println("Girando -180° (volviendo)...");
    robot.turn(-180);
}

// ── T06: curve() ───────────────────────────────────────────
void test_curve() {
    printSep("T06 — curve() radio 200mm, 90°");

    robot.resetEncoders();
    float imu_antes = robot.getTelemetry().heading_imu_deg;

    Serial.println("Arco radio 200mm, 90° derecha...");
    robot.curve(200, 90);   // bloqueante
    delay(300);

    printTelemetry("Después curve(200, 90):");
    float diff = robot.getTelemetry().heading_imu_deg - imu_antes;
    if (diff > 180)  diff -= 360;
    if (diff < -180) diff += 360;
    Serial.print("Giro real (IMU): ");
    Serial.print(diff, 1);
    Serial.println("°");
    Serial.println("► Esperado: heading ~+90°, dist ~π×200/2 ~314mm");

    delay(1000);

    // Volver con arco opuesto
    Serial.println("Volviendo con arco opuesto...");
    robot.curve(-200, 90);
}

// ── T07: startStraight() no bloqueante ─────────────────────
void test_nonblocking_straight() {
    printSep("T07 — startStraight() no bloqueante");

    robot.resetEncoders();
    Serial.println("Iniciando startStraight(500)...");
    Serial.println("(Serial5 y sensores viven durante el movimiento)");

    robot.startStraight(500);

    int updates = 0;
    while (robot.isBusy()) {
        robot.update();
        updates++;

        // Simular lectura de sensores mientras avanza
        if (updates % 50 == 0) {
            Serial.print("  update #");
            Serial.print(updates);
            Serial.print("  dist: ");
            Serial.print(robot.getDistanceMm(), 0);
            Serial.println("mm");
        }

        // Test de cancelación: cancelar a los 300mm
        if (robot.getDistanceMm() >= 300) {
            Serial.println("  ► Cancelando a 300mm (test cancelMotion)");
            robot.cancelMotion();
            break;
        }

        if (digitalRead(SWITCH) == 1) {
            robot.emergencyStop();
            return;
        }
    }

    printTelemetry("Tras cancelación:");
    Serial.print("Total updates ejecutados: ");
    Serial.println(updates);
    Serial.println("► Esperado: canceló ~300mm, loop corrió sin bloquear");

    delay(500);
    // Volver
    robot.startStraight(-robot.getDistanceMm());
    waitBusy();
}

// ── T08: startTurn() no bloqueante ─────────────────────────
void test_nonblocking_turn() {
    printSep("T08 — startTurn() no bloqueante");

    float imu_antes = robot.getTelemetry().heading_imu_deg;
    Serial.println("Iniciando startTurn(90)...");

    robot.startTurn(90);
    int updates = 0;

    while (robot.isBusy()) {
        robot.update();
        updates++;

        if (updates % 30 == 0) {
            Serial.print("  imu: ");
            Serial.print(robot.getTelemetry().heading_imu_deg, 1);
            Serial.println("°");
        }

        if (digitalRead(SWITCH) == 1) {
            robot.emergencyStop();
            return;
        }
    }

    float diff = robot.getTelemetry().heading_imu_deg - imu_antes;
    if (diff > 180)  diff -= 360;
    if (diff < -180) diff += 360;
    Serial.print("Giro real: ");
    Serial.print(diff, 1);
    Serial.print("°  updates: ");
    Serial.println(updates);
    Serial.println("► Esperado: ~90°, no bloqueó el loop");

    delay(500);
    robot.startTurn(-90);
    waitBusy();
}

// ── T09: drive() continuo + stop() ─────────────────────────
void test_drive_stop() {
    printSep("T09 — drive() continuo + stop()");

    Serial.println("drive(150 mm/s, 0°/s) por 2s...");
    robot.drive(150, 0);

    unsigned long t0 = millis();
    robot.resetEncoders();
    while (millis() - t0 < 2000) {
        robot.update();
        if (digitalRead(SWITCH) == 1) {
            robot.emergencyStop();
            return;
        }
    }

    robot.stop(COAST);
    delay(300);
    Serial.print("dist recorrida: ");
    Serial.print(robot.getDistanceMm(), 0);
    Serial.println("mm");
    Serial.println("► Esperado: ~300mm (150mm/s × 2s)");

    delay(500);

    // Probar con curva continua
    Serial.println("drive(100 mm/s, 45°/s) arco continuo por 2s...");
    robot.drive(100, 45);
    t0 = millis();
    while (millis() - t0 < 2000) {
        robot.update();
        if (digitalRead(SWITCH) == 1) {
            robot.emergencyStop();
            return;
        }
    }
    robot.stop(BRAKE);
    delay(300);
    Serial.println("► drive() con curva continua OK");

    // Volver al origen aproximado
    robot.straight(-robot.getDistanceMm() * 0.8f);
}

// ── T10: isStalled() y emergencyStop() ─────────────────────
void test_stall() {
    printSep("T10 — isStalled() y emergencyStop()");

    Serial.println("Iniciando straight(1000) — bloqueá la rueda");
    Serial.println("con la mano para provocar stall...");
    Serial.println("(Si no se bloquea, el test pasa el timeout en 12s)");

    robot.setStallThreshold(3, 600);  // 3 ticks, 600ms
    robot.startStraight(1000, 100);

    unsigned long t0 = millis();
    bool stalled = false;

    while (robot.isBusy()) {
        robot.update();

        if (robot.isStalled()) {
            stalled = true;
            Serial.println("  ► STALL DETECTADO");
            robot.emergencyStop();
            break;
        }

        if (millis() - t0 > 8000) {
            Serial.println("  ► Timeout test — sin stall detectado");
            robot.cancelMotion();
            break;
        }

        if (digitalRead(SWITCH) == 1) {
            robot.emergencyStop();
            return;
        }
    }

    Serial.print("Stall detectado: ");
    Serial.println(stalled ? "SÍ ✓" : "NO (normal si no bloqueaste)");
    Serial.print("Estado final: ");
    Serial.println(robot.getMotionState());

    // Restaurar threshold normal
    robot.setStallThreshold(2, 500);
    delay(500);

    // Volver
    robot.straight(-200);
}

// ── T11: getTelemetry() durante movimiento ──────────────────
void test_telemetry() {
    printSep("T11 — getTelemetry() durante movimiento");

    robot.resetEncoders();
    robot.startStraight(400);

    Serial.println("dist_mm | enc_head | imu_head | target | error | state");
    int count = 0;
    while (robot.isBusy()) {
        robot.update();
        count++;

        if (count % 20 == 0) {
            Telemetry t = robot.getTelemetry();
            Serial.print(t.distance_mm, 0);
            Serial.print(" | ");
            Serial.print(t.heading_enc_deg, 1);
            Serial.print(" | ");
            Serial.print(t.heading_imu_deg, 1);
            Serial.print(" | ");
            Serial.print(t.target, 0);
            Serial.print(" | ");
            Serial.print(t.error, 0);
            Serial.print(" | ");
            Serial.println(t.state);
        }

        if (digitalRead(SWITCH) == 1) {
            robot.emergencyStop();
            return;
        }
    }

    Serial.println("Estado final: FINISHED (2)");
    Serial.println("► Verificar que dist_mm llegó ~400mm y error ~0");

    delay(500);
    robot.straight(-400);
}

// ── T12: setMaxSpeed / setMaxAccel ─────────────────────────
void test_tuning() {
    printSep("T12 — setMaxSpeed / setMaxAccel tuning");

    Serial.println("Test 1: velocidad BAJA (80mm/s, accel 160mm/s²)");
    robot.setMaxSpeed(80);
    robot.setMaxAccel(160);
    unsigned long t0 = millis();
    robot.resetEncoders();
    robot.straight(200);
    unsigned long t1 = millis();
    Serial.print("Tiempo: "); Serial.print(t1 - t0); Serial.println("ms");
    Serial.println("► Esperado: ~3.5s (lento y suave)");

    delay(500);
    robot.straight(-200);
    delay(500);

    Serial.println("Test 2: velocidad ALTA (250mm/s, accel 500mm/s²)");
    robot.setMaxSpeed(250);
    robot.setMaxAccel(500);
    t0 = millis();
    robot.resetEncoders();
    robot.straight(200);
    t1 = millis();
    Serial.print("Tiempo: "); Serial.print(t1 - t0); Serial.println("ms");
    Serial.println("► Esperado: ~1s (rápido y agresivo)");

    delay(500);
    robot.straight(-200);

    // Restaurar valores por defecto
    robot.setMaxSpeed(200);
    robot.setMaxAccel(400);
    robot.setMaxTurnRate(180);
    robot.setMaxTurnAccel(360);
    Serial.println("► Valores restaurados a default");
}

// ═══════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════

void setup() {
    robot.steer(0, 0, 0);

    attachInterrupt(digitalPinToInterrupt(27), ISR1, CHANGE);
    attachInterrupt(digitalPinToInterrupt(5),  ISR2, CHANGE);
    attachInterrupt(digitalPinToInterrupt(38), ISR3, CHANGE);
    attachInterrupt(digitalPinToInterrupt(2),  ISR4, CHANGE);

    pinMode(SWITCH,      INPUT_PULLUP);
    pinMode(BUZZER,      OUTPUT);
    pinMode(LED_ROJO,    OUTPUT);
    pinMode(LED_BUILTIN, OUTPUT);

    Serial.begin(115200);
    Serial5.begin(115200);

    if (!bno.begin()) {
        Serial.println("ERROR: No BNO055 detectado");
        while (1);
    }
    bno.setExtCrystalUse(true);

    // ── Configurar nuevo DriveBase ────────────────────────
    robot.setKinematics(60.0f, 172.5f, 540);
    robot.setIMU(&bno);
    robot.setMaxSpeed(200.0f);
    robot.setMaxAccel(400.0f);
    robot.setMaxTurnRate(180.0f);
    robot.setMaxTurnAccel(360.0f);

    Serial.println("═══════════════════════════════════════");
    Serial.println("  DriveBase Test Suite — Teensy 4.1");
    Serial.println("  Enciende el switch para comenzar");
    Serial.println("═══════════════════════════════════════");
}

// ═══════════════════════════════════════════════════════════
// LOOP
// ═══════════════════════════════════════════════════════════

void loop() {
    robot.update();  // ← siempre primera línea

    if (digitalRead(SWITCH) == 1) {
        robot.emergencyStop();
        testIndex = 0;
        startUp   = false;
        testDone  = false;
        robot.steer(0, 0, 0);

        while (true) {
            digitalWrite(LED_BUILTIN, HIGH);
            digitalWrite(LED_ROJO,    HIGH);
            delay(300);
            digitalWrite(LED_BUILTIN, LOW);
            digitalWrite(LED_ROJO,    LOW);
            delay(300);
            if (digitalRead(SWITCH) == 0) break;
        }
        return;
    }

    if (!startUp) {
        // Pequeño movimiento de inicialización
        runTime(10, BACKWARD, 0, 200);
        runTime(10, FORWARD,  0, 200);
        startUp = true;
        Serial.println("Setup OK — Iniciando tests en 2s...");
        delay(2000);
    }

    if (testDone) {
        digitalWrite(LED_BUILTIN, HIGH);
        return;
    }

    // ── Secuencia de tests ─────────────────────────────────
    switch (testIndex) {
        case 0:  test_odometria();            break;
        case 1:  test_heading();              break;
        case 2:  test_straight();             break;
        case 3:  test_turn_90();              break;
        case 4:  test_turn_180();             break;
        case 5:  test_curve();                break;
        case 6:  test_nonblocking_straight(); break;
        case 7:  test_nonblocking_turn();     break;
        case 8:  test_drive_stop();           break;
        case 9:  test_stall();                break;
        case 10: test_telemetry();            break;
        case 11: test_tuning();               break;

        default:
            Serial.println("═══════════════════════════════════════");
            Serial.println("  TODOS LOS TESTS COMPLETADOS");
            Serial.println("  Revisar resultados en Serial Monitor");
            Serial.println("═══════════════════════════════════════");
            testDone = true;
            return;
    }

    testIndex++;
    Serial.println();
    Serial.print("► Próximo test en 3s... (test ");
    Serial.print(testIndex + 1);
    Serial.println(" de 12)");
    delay(3000);
}