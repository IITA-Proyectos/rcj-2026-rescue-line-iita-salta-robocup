#include <Wire.h>
#include <Arduino.h>
#include <drivebase.h>
#include <PID.h>
#include <elapsedMillis.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include "math.h"
#include <Servo.h>
#include <Adafruit_I2CDevice.h>
#include <claw.h>
#include "Adafruit_APDS9960.h"
#include <NewPing.h>
#include <Wire.h>
#include <VL53L0X.h>
#include "priority_fix_flags.h"



// SERVOS
DFServo sort(23, 540, 2390, 274);
DFServo left(14, 540, 2390, 274);
DFServo right(15, 540, 2390, 274);
DFServo lift(22, 540, 2390, 274);
DFServo deposit(12, 540, 2390, 274);
Claw claw(&lift, &left, &right, &sort, &deposit);

// CONSTANTS //
#define FORWARD 0         // Def direction ADELANTE
#define BACKWARD 1        // Def direction ATRAS
#define RELAY 0
#define BUZZER 31         // Definicion de PIN BUZZER
#define LED_ROJO 30       // Definicion de PIN LED_ROJO
#define SWITCH 32         // Definicion de PIN SWITCH
#define FCL 40
#define FCR 41
elapsedMillis steertimer; // Cuenta el tiempo transcurrido
bool contador = false;    // Para saber si estamos contando el tiempo o no
bool retroceder = false;  // Para saber si debe retroceder
bool rescateAvisado = false;
// INITIALISE BNO055 //
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
// INITIALISE ACTUATORS //
Moto bl(29, 28, 27, "BL"); // pwm, dir, enc
Moto fl(7, 6, 5, "FL");
Moto br(36, 37, 38, "BR");
Moto fr(4, 3, 2, "FR");
DriveBase robot(&fl, &fr, &bl, &br);
// STATE VARIABLES & FLAGS //
String color_detected;
unsigned long tiemporescate=0;
static unsigned long lastTurn = 0;           // persiste entre iteraciones
const unsigned long turnCooldown = 600;      // ms (ajusta)
int counter = 0;

int laststeer = 0;
int serial5state = 0;  // serial code e.g. 255
double speed;          // speed (0 to 100)
double steer;          // angle (0 to 180 deg, will -90 later)
int green_state = 0;   // 0 = no green squares, 1 = left, 2 = right, 3 = double
int silver_line = 0;   // if there is a line to reacquire after obstacle
// PROTOCOLO RPi -> Teensy:
// Frame: [255, speed, 254, angle, 253, green_state, 252, silver_line]
// speed: 0..100; angle: 0..180 (RPi envia angle + 90);
// green_state: 0..20; silver_line: 0..1.
// Los sync bytes 252..255 no deben usarse como payload.
constexpr int SERIAL_SYNC_SPEED = 255;
constexpr int SERIAL_SYNC_STEER = 254;
constexpr int SERIAL_SYNC_TASK = 253;
constexpr int SERIAL_SYNC_SILVER = 252;
constexpr int SERIAL_MAX_SPEED = 100;
constexpr int SERIAL_MAX_ANGLE = 180;
constexpr int SERIAL_MAX_GREEN_STATE = 20;
constexpr int SERIAL_MAX_SILVER_LINE = 1;
unsigned long serial_bytes_rx = 0;
unsigned long serial_frames_rx = 0;
elapsedMillis serialTelemetryTimer;
int servo = 0;
int action =7;            // action to take (part of a task)
bool taskDone = false; // if true, update current_task
int angle0;            // initial IMU reading
bool startUp = false;
float frontUSReading;
int RanNumber;
String rutina = "linea";
bool first_rescate = 1;
String wall = "right";
bool esquinas_negro[3];
bool final_rescate = 1;
String lado_plateado="";
bool lectura =0;
int cccounter,
    leftLidarReading, rightLidarReading;
VL53L0X left_tof;  // Sensor 1
VL53L0X right_tof; // Sensor 2
int distance_left_tof;
int distance_right_tof;
float angulo_rescate = 0;
float centrar = 0;
String pared="";
bool alineado=false;
bool depositando=false;
int veces_deposit=2;
int ball_counter=2;
bool evacuacion_iniciada=false;
bool evacuacion_straight=false;
int last_right_distance = 0;
int right_jump_counter = 0;

// Máquina de Estados para Rescate (No Bloqueante)
bool color_sensor_ok = true;
bool rescateUpdateInProgress = false;

void actualizarRescate();
void serialEvent5();
void runTime(int speed, int dir, double steer, unsigned long long time);
void runAngle(int speed, int dir, double angle);
void runDistance(int speed, int dir, int Distance);

bool fixIssue57Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue57RescueWallTurnDirection;
}

bool fixIssue58Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue58Case12ControlFlow;
}

bool fixIssue59Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue59ServiceStateMachinesDuringMotion;
}

bool fixIssue60Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue60RunDistanceTimeout;
}

bool fixIssue61Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue61ColorSensorTimeout;
}

bool fixIssue62Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue62VisibleSensorInitFailures;
}

bool fixIssue63Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue63KeepSerialDuringMotions;
}

bool fixIssue74Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue74ValidateSerialPayloads;
}

bool fixIssue75Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue75SerialTelemetry;
}

bool fixIssue112Enabled()
{
    return priority_fix_flags::kEnableAllPriorityFixes ||
           priority_fix_flags::kFixIssue112RunAngleTimeout;
}

void blinkVisibleError(unsigned long onMs, unsigned long offMs, int cycles)
{
    for (int i = 0; i < cycles; ++i)
    {
        digitalWrite(LED_ROJO, HIGH);
        digitalWrite(BUZZER, HIGH);
        delay(onMs);
        digitalWrite(LED_ROJO, LOW);
        digitalWrite(BUZZER, LOW);
        delay(offMs);
    }
}

void fatalSensorInitLoop()
{
    while (true)
    {
        digitalWrite(LED_ROJO, HIGH);
        digitalWrite(BUZZER, HIGH);
        delay(200);
        digitalWrite(LED_ROJO, LOW);
        digitalWrite(BUZZER, LOW);
        delay(800);
    }
}

void handleBnoInitFailure()
{
    Serial.print("No BNO055 detected ... Check your wiring or I2C ADDR!");
    if (fixIssue62Enabled())
    {
        fatalSensorInitLoop();
    }
    while (1)
        ;
}

void notifyOptionalSensorWarning()
{
    if (fixIssue62Enabled())
    {
        blinkVisibleError(120, 120, 3);
    }
}

void serviceMotionBackgroundTasks()
{
    if (!fixIssue59Enabled())
    {
        return;
    }

    claw.update();
    actualizarRescate();
}

unsigned long computeRunDistanceTimeoutMs(int speed, int distance)
{
    unsigned long distanceCm = static_cast<unsigned long>(abs(distance));
    int effectiveSpeed = speed > 0 ? speed : 30;
    unsigned long estimatedSpeedCmPerSecond = static_cast<unsigned long>(max(8, effectiveSpeed * 3 / 4));
    unsigned long estimatedMs = (distanceCm * 1000UL) / estimatedSpeedCmPerSecond;

    return (estimatedMs * 3UL) / 2UL + 500UL;
}

unsigned long computeRunAngleTimeoutMs(double angle)
{
    unsigned long angleDeg = static_cast<unsigned long>(fabs(angle));
    if (angleDeg < 1)
    {
        return 1000UL;
    }

    return max(1500UL, angleDeg * 35UL + 1000UL);
}

enum RescateState {
    RESCATE_IDLE = 0,          // Estado inactivo
    RESCATE_NEGRA_STEP1,       // Baja garra
    RESCATE_NEGRA_STEP2,       // Posiciona depósito centro
    RESCATE_NEGRA_STEP3,       // Clasifica derecha
    RESCATE_NEGRA_STEP4,       // Avanza distancia
    RESCATE_NEGRA_STEP5,       // Cierra garra
    RESCATE_NEGRA_STEP6,       // Levanta garra
    RESCATE_NEGRA_STEP7,       // Abre garra
    RESCATE_NEGRA_STEP8,       // Retrocede un poco
    RESCATE_PLATEADA_STEP1,    // Baja garra
    RESCATE_PLATEADA_STEP2,    // Clasifica izquierda
    RESCATE_PLATEADA_STEP3,    // Posiciona depósito centro
    RESCATE_PLATEADA_STEP4,    // Avanza distancia
    RESCATE_PLATEADA_STEP5,    // Cierra garra
    RESCATE_PLATEADA_STEP6,    // Levanta garra
    RESCATE_PLATEADA_STEP7,    // Abre garra
    RESCATE_PLATEADA_STEP8     // Retrocede un poco
};
RescateState rescateState = RESCATE_IDLE;  // Estado actual de la máquina de rescate
unsigned long rescateLastTime = 0;         // Timestamp del último paso
const unsigned long RESCATE_STEP_DELAY = 1000;  // Delay entre pasos en ms

// Función para iniciar recolección de pelota negra
void iniciarRecoleccionNegra() {
    if (rescateState == RESCATE_IDLE) {
        rescateState = RESCATE_NEGRA_STEP1;
        rescateLastTime = millis();
    }
}

// Función para iniciar recolección de pelota plateada
void iniciarRecoleccionPlateada() {
    if (rescateState == RESCATE_IDLE) {
        rescateState = RESCATE_PLATEADA_STEP1;
        rescateLastTime = millis();
    }
}

// Función para actualizar la máquina de estados de rescate (llamar en loop())
void actualizarRescate() {
    if (rescateUpdateInProgress) {
        return;
    }

    rescateUpdateInProgress = true;
    unsigned long now = millis();
    switch (rescateState) {
        case RESCATE_IDLE:
            // Nada que hacer
            break;
        case RESCATE_NEGRA_STEP1:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lower();
                rescateState = RESCATE_NEGRA_STEP2;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP2:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.depositCenter();
                rescateState = RESCATE_NEGRA_STEP3;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP3:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.sortRight();
                rescateState = RESCATE_NEGRA_STEP4;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP4:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                runDistance(30, FORWARD, 8);
                rescateState = RESCATE_NEGRA_STEP5;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP5:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.close();
                digitalWrite(BUZZER, HIGH);
                delay(100);  // Pequeño delay para buzzer, considerar no-bloqueante si necesario
                digitalWrite(BUZZER, LOW);
                rescateState = RESCATE_NEGRA_STEP6;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP6:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lift();
                rescateState = RESCATE_NEGRA_STEP7;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP7:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.open();
                rescateState = RESCATE_NEGRA_STEP8;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP8:
            if (now - rescateLastTime >= 200) {  // Menor delay para retroceso
                runTime(30, FORWARD, 0, 200);
                runTime(30, BACKWARD, 0, 200);
                ball_counter++;
                rescateState = RESCATE_IDLE;
            }
            break;
        // Estados para pelota plateada (análogos)
        case RESCATE_PLATEADA_STEP1:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lower();
                rescateState = RESCATE_PLATEADA_STEP2;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP2:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.sortLeft();
                rescateState = RESCATE_PLATEADA_STEP3;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP3:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.depositCenter();
                rescateState = RESCATE_PLATEADA_STEP4;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP4:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                runDistance(20, FORWARD, 8);
                rescateState = RESCATE_PLATEADA_STEP5;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP5:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.close();
                digitalWrite(BUZZER, HIGH);
                delay(100);
                digitalWrite(BUZZER, LOW);
                rescateState = RESCATE_PLATEADA_STEP6;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP6:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lift();
                rescateState = RESCATE_PLATEADA_STEP7;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP7:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.open();
                rescateState = RESCATE_PLATEADA_STEP8;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP8:
            if (now - rescateLastTime >= 200) {
                runTime(30, FORWARD, 0, 200);
                runTime(30, BACKWARD, 0, 200);
                ball_counter++;
                rescateState = RESCATE_IDLE;
            }
            break;
    }
    rescateUpdateInProgress = false;
}
#define SONAR_NUM 3      // Number of sensors.
#define MAX_DISTANCE 150 // Maximum distance (in cm) to ping.

NewPing sonar[SONAR_NUM] = {     // Sensor object array.
    NewPing(8, 9, MAX_DISTANCE), // Each sensor's trigger pin, echo pin, and max distance to ping.
    NewPing(11, 10, MAX_DISTANCE),
    NewPing(39, 33, MAX_DISTANCE)};

int front_distance;
int left_distance;
int right_distance;

// -----------  FUNCTIONS  -----------
// ULTRASONIDOS FRENTE IZQ DER
void leer_ultrasonidos()
{
    front_distance = sonar[0].ping_cm();
    left_distance = sonar[1].ping_cm();
    right_distance = sonar[2].ping_cm();
}

void imprimir_ultrasonidos()
{
    Serial.print("|D: ");
    Serial.print(right_distance);
    //Serial.println("cm ");
}

// TOF
void leer_tof()
{
    distance_left_tof = left_tof.readRangeContinuousMillimeters();
    distance_right_tof = right_tof.readRangeContinuousMillimeters();
}

void imprimir_tof()
{
    Serial.print("Distance Left: ");
    Serial.print(distance_left_tof);
    Serial.print("mm");

    if (left_tof.timeoutOccurred())
    {
        Serial.print(" TIMEOUT");
    }

    Serial.print("   Distance Right: ");
    Serial.print(distance_right_tof);
    Serial.print("mm");

    if (right_tof.timeoutOccurred())
    {
        Serial.print(" TIMEOUT");
    }
}
void reset_enconder(){
    bl.resetPulseCount();
    fl.resetPulseCount();
    br.resetPulseCount();
    fr.resetPulseCount();
}
// Color Sensor
Adafruit_APDS9960 apds;
struct Color
{
    String name;
    uint16_t r, g, b, c;
};

Color known_colors[] = {
  {"Blanco", 570, 1010, 1025, 2685},
  {"Negro", 60, 135, 135, 310},
  {"Verde", 62, 181, 175, 470},
  {"Plateado", 500, 900, 900, 2300}
  
};
// Función para leer los valores del sensor y determinar el color
constexpr unsigned long APDS_COLOR_INTEGRATION_MS = 10;
constexpr unsigned long APDS_COLOR_STATUS_POLL_MS = 2;
constexpr unsigned long APDS_COLOR_FRESH_TIMEOUT_MS = 35;
constexpr uint8_t APDS_COLOR_FILTER_SAMPLES = 3;

uint16_t color_r_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint16_t color_g_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint16_t color_b_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint16_t color_c_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint8_t color_history_index = 0;
uint8_t color_history_count = 0;
unsigned long last_color_sample_ms = 0;
unsigned long last_color_status_poll_ms = 0;
String last_color_detected = "Desconocido";

uint64_t square_error(uint16_t expected, uint16_t actual)
{
    int32_t diff = static_cast<int32_t>(expected) - static_cast<int32_t>(actual);
    return static_cast<uint64_t>(diff) * static_cast<uint64_t>(diff);
}

void push_color_sample(uint16_t r, uint16_t g, uint16_t b, uint16_t c)
{
    color_r_history[color_history_index] = r;
    color_g_history[color_history_index] = g;
    color_b_history[color_history_index] = b;
    color_c_history[color_history_index] = c;
    color_history_index = (color_history_index + 1) % APDS_COLOR_FILTER_SAMPLES;
    if (color_history_count < APDS_COLOR_FILTER_SAMPLES)
    {
        color_history_count++;
    }
}

void get_filtered_color(uint16_t &r, uint16_t &g, uint16_t &b, uint16_t &c)
{
    uint32_t r_sum = 0, g_sum = 0, b_sum = 0, c_sum = 0;
    uint8_t samples = color_history_count > 0 ? color_history_count : 1;

    for (uint8_t i = 0; i < color_history_count; i++)
    {
        r_sum += color_r_history[i];
        g_sum += color_g_history[i];
        b_sum += color_b_history[i];
        c_sum += color_c_history[i];
    }

    r = r_sum / samples;
    g = g_sum / samples;
    b = b_sum / samples;
    c = c_sum / samples;
}

String classify_color(uint16_t r, uint16_t g, uint16_t b, uint16_t c)
{
    float ratio_rc = c > 0 ? static_cast<float>(r) / static_cast<float>(c) : 0.0f;
    float ratio_rg = g > 0 ? static_cast<float>(r) / static_cast<float>(g) : 0.0f;
    float ratio_rb = b > 0 ? static_cast<float>(r) / static_cast<float>(b) : 0.0f;

    static unsigned long lastPrint = 0;
    bool shouldPrint = (millis() - lastPrint > 500);
    if (shouldPrint)
    {
        Serial.print("R: "); Serial.print(r);
        Serial.print(" | B: "); Serial.print(b);
        Serial.print(" | G: "); Serial.print(g);
        Serial.print(" | C: "); Serial.print(c);
        Serial.print(" | R/C: "); Serial.print(ratio_rc, 3);
        Serial.print(" | R/G: "); Serial.print(ratio_rg, 3);
        Serial.print(" | R/B: "); Serial.print(ratio_rb, 3);
        Serial.print(" | -> ");
    }

    String detected = "Desconocido";
    if (c > 1700 && ratio_rc > 0.240f)
    {
        detected = "Plateado";
    }
    else if (c > 1500 && ratio_rc <= 0.235f)
    {
        detected = "Blanco";
    }
    else if (c >= 300 && c <= 600 && ratio_rg > 1.62f && ratio_rc > 0.440f)
    {
        detected = "Rojo";
    }
    else
    {
        uint64_t min_error = UINT64_MAX;
        for (size_t i = 0; i < sizeof(known_colors) / sizeof(known_colors[0]); i++)
        {
            if (known_colors[i].name == "Blanco" || known_colors[i].name == "Plateado")
                continue;

            uint64_t error = square_error(known_colors[i].r, r) +
                             square_error(known_colors[i].g, g) +
                             square_error(known_colors[i].b, b) +
                             square_error(known_colors[i].c, c);
            if (error < min_error)
            {
                min_error = error;
                detected = known_colors[i].name;
            }
        }
    }

    if (shouldPrint)
    {
        Serial.println(detected);
        lastPrint = millis();
    }

    return detected;
}

bool update_color_nonblocking(bool force_poll = false)
{
    if ((fixIssue61Enabled() || fixIssue62Enabled()) && !color_sensor_ok)
        return false;

    unsigned long now = millis();
    if (!force_poll && (now - last_color_status_poll_ms) < APDS_COLOR_STATUS_POLL_MS)
        return false;

    last_color_status_poll_ms = now;
    if ((now - last_color_sample_ms) < APDS_COLOR_INTEGRATION_MS)
        return false;

    if (!apds.colorDataReady())
        return false;

    uint16_t r, g, b, c;
    apds.getColorData(&r, &g, &b, &c);
    push_color_sample(r, g, b, c);
    get_filtered_color(r, g, b, c);
    last_color_detected = classify_color(r, g, b, c);
    last_color_sample_ms = now;
    return true;
}

String get_color_fresh(unsigned long timeoutMs = APDS_COLOR_FRESH_TIMEOUT_MS)
{
    unsigned long start = millis();
    while ((millis() - start) <= timeoutMs)
    {
        if (update_color_nonblocking(true))
            return last_color_detected;

        serviceMotionBackgroundTasks();
        if (Serial5.available() > 0 && fixIssue63Enabled())
        {
            serialEvent5();
        }
        delay(1);
    }

    return "Desconocido";
}

String get_color_fast()
{
    if (update_color_nonblocking(false))
        return last_color_detected;

    return "Desconocido";
}

String get_color_old()
{
    if ((fixIssue61Enabled() || fixIssue62Enabled()) && !color_sensor_ok)
    {
        return "Desconocido";
    }

    uint16_t r, g, b, c;
    unsigned long waitStart = millis();

    // Esperar a que los datos de color estén listos
    while (!apds.colorDataReady())
    {
        if (fixIssue61Enabled() && (millis() - waitStart) > 50)
        {
            return "Desconocido";
        }
        delay(5);
    }

    // Obtener los datos del sensor
    apds.getColorData(&r, &g, &b, &c);

    // Calcular el color más cercano utilizando mínimos cuadrados
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

    // Imprimir los valores de R, G, B y Clear
    /*
    Serial.print("red: ");
    Serial.print(r);
    Serial.print(" green: ");
    Serial.print(g);
    Serial.print(" blue: ");
    Serial.print(b);
    Serial.print(" clear: ");
    //Serial.println(c);
    */

    return closest_color;
}

String get_color_blocking_legacy()
{
    if ((fixIssue61Enabled() || fixIssue62Enabled()) && !color_sensor_ok)
        return "Desconocido";

    uint16_t r_sum = 0, g_sum = 0, b_sum = 0, c_sum = 0;
    const int muestras = 5;

    for (int i = 0; i < muestras; i++)
    {
        uint16_t r, g, b, c;
        unsigned long waitStart = millis();
        while (!apds.colorDataReady())
        {
            if (fixIssue61Enabled() && (millis() - waitStart) > 50)
                return "Desconocido";
            delay(5);
        }
        apds.getColorData(&r, &g, &b, &c);
        r_sum += r; g_sum += g; b_sum += b; c_sum += c;
    }

    uint16_t r = r_sum / muestras;
    uint16_t g = g_sum / muestras;
    uint16_t b = b_sum / muestras;
    uint16_t c = c_sum / muestras;

    float ratio_rc = c > 0 ? (float)r / (float)c : 0.0f;
    float ratio_rg = g > 0 ? (float)r / (float)g : 0.0f;
    float ratio_rb = b > 0 ? (float)r / (float)b : 0.0f;

    // Print siempre antes de los returns
    static unsigned long lastPrint = 0;
    if (millis() - lastPrint > 500)
    {
        Serial.print("R: "); Serial.print(r);
        Serial.print(" | B: "); Serial.print(b);
        Serial.print(" | G: "); Serial.print(g);
        Serial.print(" | C: "); Serial.print(c);
        Serial.print(" | R/C: "); Serial.print(ratio_rc, 3);
        Serial.print(" | R/G: "); Serial.print(ratio_rg, 3);
        Serial.print(" | R/B: "); Serial.print(ratio_rb, 3);

        Serial.print(" | -> ");
        if      (c > 1700 && ratio_rc > 0.240)                          Serial.println("Plateado");
        else if (c > 1500 && ratio_rc <= 0.235)                         Serial.println("Blanco");
        else if (c >= 300 && c <= 600 && ratio_rg > 1.6f && ratio_rb > 1.5f) Serial.println("Rojo");
        else if (c < 600)                                                Serial.println("Negro");
        else                                                             Serial.println("Verde");
        lastPrint = millis();
    }

    // Returns en el mismo orden que el print
    if (c > 1700 && ratio_rc > 0.240)        return "Plateado";
    if (c > 1500 && ratio_rc <= 0.235)       return "Blanco";
    if (c >= 300 && c <= 600 && ratio_rg > 1.62f && ratio_rc > 0.440f) return "Rojo";

    // Negro y Verde por mínimos cuadrados
    String closest_color = "Desconocido";
    uint32_t min_error = UINT32_MAX;
    for (size_t i = 0; i < sizeof(known_colors) / sizeof(known_colors[0]); i++)
    {
        if (known_colors[i].name == "Blanco" || known_colors[i].name == "Plateado")
            continue;
        uint32_t error = pow(known_colors[i].r - r, 2) +
                         pow(known_colors[i].g - g, 2) +
                         pow(known_colors[i].b - b, 2) +
                         pow(known_colors[i].c - c, 2);
        if (error < min_error) { min_error = error; closest_color = known_colors[i].name; }
    }
    return closest_color;
}

String get_color()
{
    return get_color_fast();
}

// ISR for updating motor pulses
void ISR1() { bl.updatePulse(); }
void ISR2() { fl.updatePulse(); }
void ISR3() { br.updatePulse(); }
void ISR4() { fr.updatePulse(); }

bool serialPayloadOutOfRange(const char *field, int value, int maxValue)
{
    if (!fixIssue74Enabled())
    {
        return false;
    }

    if (value >= 0 && value <= maxValue)
    {
        return false;
    }

    Serial.print("[WARN] ");
    Serial.print(field);
    Serial.print(" fuera de rango: ");
    Serial.println(value);
    return true;
}

void maybePrintSerialTelemetry()
{
    if (!fixIssue75Enabled() || serialTelemetryTimer < 5000)
    {
        return;
    }

    Serial.print("[TLM] serial_bytes_rx=");
    Serial.print(serial_bytes_rx);
    Serial.print(" serial_frames_rx=");
    Serial.println(serial_frames_rx);
    serialTelemetryTimer = 0;
}

// Read Data from Raspberry by Serial TX-RX
void serialEvent5()
{
    while (Serial5.available() > 0)
    {
        int data = Serial5.read(); // read serial code
        if (fixIssue75Enabled())
        {
            serial_bytes_rx++;
        }
         
        if (data == SERIAL_SYNC_SPEED) // speed incoming
            serial5state = 0;
        else if (data == SERIAL_SYNC_STEER) // steer incoming
            serial5state = 1;
        else if (data == SERIAL_SYNC_TASK) // task incoming
            serial5state = 2;
        else if (data == SERIAL_SYNC_SILVER) // line_middle incoming
            serial5state = 3;
        else if (serial5state == 0)           // set speed
        {
            if (serialPayloadOutOfRange("speed", data, SERIAL_MAX_SPEED))
                continue;
            speed = (double)data / 100 * 100; // max speed = 100
        }
        else if (serial5state == 1)           // set steer
        {
            if (serialPayloadOutOfRange("angle", data, SERIAL_MAX_ANGLE))
                continue;
            steer = ((double)data - 90) / 90;
        }
        else if (serial5state == 2) // set task
        {
            if (serialPayloadOutOfRange("green_state", data, SERIAL_MAX_GREEN_STATE))
                continue;
            green_state = data;
    Serial.print("[RX] green_state recibido: ");
    Serial.println(green_state);
        }
        else if (serial5state == 3) // set line_middle
        {
            if (serialPayloadOutOfRange("silver_line", data, SERIAL_MAX_SILVER_LINE))
                continue;
            silver_line = data;
            if (fixIssue75Enabled())
            {
                serial_frames_rx++;
            }
        }
    }

    maybePrintSerialTelemetry();
}

// HELPER FUNCTIONS //

// Do a predefined move by time
void runTime(int speed, int dir, double steer, unsigned long long time)
{
    unsigned long long startTime = millis();
    while ((millis() - startTime) < time)
    {
        robot.steer(speed, dir, steer);
        serviceMotionBackgroundTasks();
        digitalWrite(13, HIGH);
        if (Serial5.available() > 0)
        {
            if (fixIssue63Enabled() )
            {
                serialEvent5();
            }
            else
            {
                int lecturas = Serial5.read();
                Serial.print(lecturas);
            }
        }

        if (digitalRead(32) == 1)
        { // switch is off
            Serial5.clear();
            Serial5.write(255);
            break;
        }
    }

    digitalWrite(13, LOW);
}
void runAngle(int speed, int dir, double angle)
{
    sensors_event_t event;
    bno.getEvent(&event);
    float initialAngle = event.orientation.x;
    float targetAngle = initialAngle + angle;
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunAngleTimeoutMs(angle);

    // Normalizar el ángulo objetivo al rango 0-360
    targetAngle = fmod(targetAngle, 360.0);
    if (targetAngle < 0)
        targetAngle += 360;

    while (true)
    {
        bno.getEvent(&event);
        float currentAngle = event.orientation.x;
        serviceMotionBackgroundTasks();
        if (Serial5.available() > 0 && fixIssue63Enabled())
        {
            serialEvent5();
        }
        if (fixIssue112Enabled() && (millis() - startTime) >= timeoutMs)
        {
            Serial.println("[WARN] runAngle timeout");
            break;
        }
        if (digitalRead(32) == 1)
        { // switch is off
            Serial5.clear();
            Serial5.write(255);
            break;
        }
        // Calcular la diferencia más corta entre los ángulos
       // Calcular la diferencia más corta entre los ángulos
        float error = targetAngle - currentAngle;
        if (error > 180)
            error -= 360;
        if (error < -180)
            error += 360;
        Serial.print("Error actual: ");
        //Serial.println(fabs(error));
        if (fabs(error) <= 1.0)
            break;
        // Lógica para manejar los 5 valores de ángulo específicos
        if (angle == 180)
        {
            // Girar 180 grados (media vuelta)
            robot.steer(speed, dir, 1); // Girar a la derecha
        }
        else if (angle == 90 || angle == -270)
        {
            // Girar 90 grados a la derecha
            if (error > 0 && error <= 180)
            {
                robot.steer(speed, dir, -1);
            }
            else
            {
                robot.steer(speed, dir, 1);
            }
        }
        else if (angle == -90 || angle == 270)
        {
            // Girar 90 grados a la izquierda
            if (error < 0 && error >= -180)
            {
                robot.steer(speed, dir, 1);
            }
            else
            {
                robot.steer(speed, dir, -1);
            }
        }
        else if (angle == 45 || angle == -315)
        {
            // Girar 45 grados a la derecha
            if (error > 0 && error <= 180)
            {
                robot.steer(speed, dir, -1);
            }
            else
            {
                robot.steer(speed, dir, 1);
            }
        }
        else if (angle == -45 || angle == 315)
        {
            // Girar 45 grados a la izquierda
            if (error < 0 && error >= -180)
            {
                robot.steer(speed, dir, 1);
            }
            else
            {
                robot.steer(speed, dir, -1);
            }
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

void runDistance(int speed, int dir, int Distance) {
    runTime(30,BACKWARD,0,20);
    runTime(30,FORWARD,0,20);
    reset_enconder();
    int32_t  encoder = 25*Distance;
    bool stopOnExit = fixIssue60Enabled();
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);
    
    if (dir == FORWARD) {
        while (true) {
            if (fixIssue60Enabled() && (millis() - startTime) >= timeoutMs) break;
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;
            if (frCount >= encoder || flCount >= encoder) break;

            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();
            Serial.print(flCount);
            Serial.print(" | ");
            Serial.print(frCount);
            //Serial.println(fr.pulseCount);
            digitalWrite(13, HIGH);
            delay(10);
            
            if (Serial5.available() > 0) {
                if (fixIssue63Enabled())
                {
                    serialEvent5();
                }
                else
                {
                    int lecturas = Serial5.read();
                    Serial.print(lecturas);
                }
            }
            
            if (digitalRead(32) == 1) { // switch is off
                Serial5.write(255);
                break;
            }
        }
    }else{
         while (true) 
        {
            if (fixIssue60Enabled() && (millis() - startTime) >= timeoutMs) break;
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;

            if (frCount <= -encoder || flCount <= -encoder) break;
            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();
            Serial.print(flCount);
            Serial.print(" | ");
            Serial.print(frCount);
            //Serial.println(fr.pulseCount);
            delay(10);
            if (Serial5.available() > 0) {
                if (fixIssue63Enabled())
                {
                    serialEvent5();
                }
                else
                {
                    int lecturas = Serial5.read();
                    Serial.print(lecturas);
                }
            }
            
            if (digitalRead(32) == 1) { // switch is off
                Serial5.write(255);
                break;
            }
        }
         
         
    }

    if (stopOnExit)
    {
        robot.steer(0, dir, 0);
    }
}

// non-blocking delay that keeps processing serial and claw state
void nonBlockingDelay(unsigned long ms)
{
    unsigned long start = millis();
    while (millis() - start < ms)
    {
        claw.update();
        if (Serial5.available() > 0)
            serialEvent5();
    }
}

void accionNegro() {
    runTime(30,FORWARD,0,1000);
    Serial5.write(249);
    rutina = "linea";
    digitalWrite(BUZZER, HIGH);
    delay(300);
    digitalWrite(BUZZER, LOW);
    robot.steer(0, FORWARD, 0);
}

void accionPlateado() {
    runDistance(30, BACKWARD, 10);
    runAngle(30, FORWARD, 90);
    runDistance(30, FORWARD, 2);
    digitalWrite(BUZZER, HIGH);
    delay(100);
    digitalWrite(BUZZER, LOW);
    robot.steer(0, FORWARD, 0);
}

bool detectarNegro() {
    color_detected = get_color_fresh();
    return (color_detected == "Negro");
}

bool detectarPlateado() {
    color_detected = get_color_fresh();
    return (color_detected == "Plateado");
}

#define TARGET_DISTANCE 70.0 // distancia deseada en cm
#define KP_DISTANCE 0.05     // constante proporcional para la distancia
#define KP_ANGLE 0.05        // constante proporcional para el ángulo de rotación
#define MAX_STEER 1          // valor máximo de steer permitido
#define ANGLE_THRESHOLD 2.0  // umbral de inclinación en grados (yaw)
#define TARGET_ANGLE 0       // ángulo objetivo (robot paralelo a la pared)
float yaw = 0;               // Ángulo de rotación (yaw)
float pitch=0;
float leer_yaw()
{
    sensors_event_t event;
    bno.getEvent(&event);
    float yaw = event.orientation.x; // Yaw es el ángulo de rotación (en grados)
    return yaw;
}
void leer_pitch()
{
    sensors_event_t event;
    bno.getEvent(&event);
    pitch = event.orientation.y; // Yaw es el ángulo de rotación (en grados)
}
void imprimir_yaw()
{
    Serial.print("Yaw: ");
    //Serial.println(yaw);
}
int ajustarVelocidadPorPendiente(int velocidadBase)
{
    leer_pitch();

    int velocidadAjustada = velocidadBase;
    if (pitch > 10) 
    {
            velocidadAjustada = 30;
    }
    else{
        velocidadAjustada= 25;
    }
    return velocidadAjustada;
}
// Función para calcular la diferencia de ángulo en un rango circular de 0 a 360 grados
float calcularDiferenciaAngulo(float anguloActual, float anguloObjetivo)
{
    float error = anguloObjetivo - anguloActual;

    // Ajustar la diferencia para que esté en el rango [-180, 180]
    if (error > 180)
    {
        error -= 360;
    }
    else if (error < -180)
    {
        error += 360;
    }

    return error;
}

void resetear_bno()
{
    if (!bno.begin())
    {
        handleBnoInitFailure();
    }
    bno.setExtCrystalUse(true);
    delay(200);
}

void avance_recto(String pared)
{
    leer_yaw();
    leer_tof();
    imprimir_tof();
    // Calcular el error de ángulo correctamente con la función circular
    float angle_error = calcularDiferenciaAngulo(yaw, TARGET_ANGLE); // Diferencia angular ajustada

    // Si el ángulo de giro es mayor que el umbral, ignorar el ultrasonido y corregir el ángulo
    if (abs(angle_error - TARGET_ANGLE) > ANGLE_THRESHOLD)
    {
        steer = KP_ANGLE * (-angle_error); // Invertir el signo del error angular
        // Limitar el valor de steer entre [-MAX_STEER, MAX_STEER]
        if (steer > MAX_STEER)
            steer = MAX_STEER;
        if (steer < -MAX_STEER)
            steer = -MAX_STEER;

        // Mover el robot con la corrección de ángulo
        robot.steer(45, FORWARD, steer);

        // Imprimir para depuración
        Serial.print("Corrigiendo con ángulo. Steer: ");
        //Serial.println(steer);
    }
    else
    {
        // El ángulo está alineado, utilizar sensores TOF para mantener la distancia
        float distance_error = TARGET_DISTANCE - (pared == "left" ? distance_left_tof : distance_right_tof);

        steer = KP_DISTANCE * -distance_error;

        // Error de distancia a la pared

        // Calcular la corrección para el steer basada en la distancia

        steer = constrain(steer, -MAX_STEER, MAX_STEER); // Limitar steer

        // Mover el robot utilizando la corrección de distancia
        robot.steer(45, FORWARD, steer);

        // Imprimir para depuración
        Serial.print("Corrigiendo con TOF. Steer: ");
        //Serial.println(steer);
    }
}

void lado_pared()
{
    if (left_distance != 0 && right_distance != 0 && right_distance < left_distance)
    {
        wall = "right";
    }
    else
    {
        wall = "left";
    }
}
void pelotita()
{
    
}


void setup()
{

    robot.steer(0, 0, 0);
    // claw.lift();  // Moved to begin()
    angulo_rescate = fmod(20, 360.0);
    //Serial.println(angulo_rescate);
    attachInterrupt(digitalPinToInterrupt(27), ISR1, CHANGE);
    attachInterrupt(digitalPinToInterrupt(5), ISR2, CHANGE);
    attachInterrupt(digitalPinToInterrupt(38), ISR3, CHANGE);
    attachInterrupt(digitalPinToInterrupt(2), ISR4, CHANGE);
    pinMode(SWITCH, INPUT_PULLUP); // SWITCH
    pinMode(BUZZER, OUTPUT);       // BUZZER
    pinMode(LED_ROJO, OUTPUT);     // LED ROJO
    pinMode(LED_BUILTIN, OUTPUT);  //  LED BUILT-IN for debugging
    pinMode(RELAY, OUTPUT);           
//Serial1.begin(57600);          // for reading IMU
    Serial5.begin(115200);         // for reading data from rpi and state
    delay(200);
    //Serial.begin(115200);          // displays ultrasound ping result
    // Initialise BNO055
    if (!bno.begin())
    {
        handleBnoInitFailure();
    }
    bno.setExtCrystalUse(true);

    // Initialise APDS9960 Color Sensor
    color_sensor_ok = apds.begin();
    if (!color_sensor_ok)
    {
        if (fixIssue62Enabled())
        {
            notifyOptionalSensorWarning();
        }
    }
    else
    {
        //Serial.println("Device initialized!");
    }

    // enable color sensign mode
    if (fixIssue61Enabled() || fixIssue62Enabled())
    {
        if (color_sensor_ok)
        {
            apds.enableColor(true);
            apds.enableProximity(true);
        }
    }
    else
    {
        apds.enableColor(true);
        apds.enableProximity(true);
    }

    // Initialise TOF
    Wire1.begin(); // Initialize the first I2C bus
    Wire2.begin(); // Initialize the second I2C bus

    left_tof.setBus(&Wire2);  // Assign the first bus to Sensor 1
    right_tof.setBus(&Wire1); // Assign the second bus to Sensor 2

    left_tof.setAddress(0x30);  // Set unique address for Sensor 1
    right_tof.setAddress(0x30); // Set unique address for Sensor 2

    // Continue with your setup and loop functions as before

    left_tof.init();
    left_tof.setTimeout(500);
    left_tof.startContinuous();

    right_tof.init();
    right_tof.setTimeout(500);
    right_tof.startContinuous();
    pinMode(FCL, INPUT);
    pinMode(FCR, INPUT);

    // Inicializar la garra después de setup
    claw.begin();
    for (int i = 0; i < 20; i++)
    {
        Serial5.write(0xFA);
        delay(100);
    }

}



void loop()
{
    // Advance non-blocking claw state machine each loop
    claw.update();
    // Actualizar máquina de estados de rescate no-bloqueante
    actualizarRescate();
    if (digitalRead(32) == 1)
    {                               // switch is off
        robot.steer(0, FORWARD, 0); // stop moving
        claw.lift();
        claw.sortLeft();
        Serial5.clear();
        esquinas_negro[0] = 0;
        esquinas_negro[1] = 0;
        esquinas_negro[2] = 0;
        first_rescate = 1;
        final_rescate = 1;
        evacuacion_iniciada = false;
        evacuacion_straight = false;
        action = 7;
        startUp = false;
        last_right_distance = 0;
        right_jump_counter = 0;
        taskDone = true;
        Serial5.write(255);
        while (true)
        {
            robot.steer(0, 0, 0);
                    digitalWrite(RELAY,LOW);
            claw.lift();
            //get_color_fast();
            serialEvent5();
            centrar = leer_yaw();            
            centrar = fmod(centrar, 360.0);
             if (centrar < 0) centrar += 360;
            digitalWrite(LED_BUILTIN, HIGH);
            // digitalWrite(BUZZER, HIGH);
            digitalWrite(LED_ROJO, HIGH);
            delay(500);
            robot.steer(0, 0, 0);
            digitalWrite(LED_BUILTIN, LOW);
            digitalWrite(BUZZER, LOW);
            digitalWrite(LED_ROJO, LOW);
            digitalWrite(RELAY,LOW); 


            delay(500);
            if (digitalRead(SWITCH) == 0)
            {
                break;
            }
        }
    }
    else if (digitalRead(32) == 0 && !startUp)
    {
        digitalWrite(LED_BUILTIN, LOW);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, LOW);
        runTime(20, BACKWARD, 0, 300);
        runTime(20, FORWARD, 0, 300);
        // Serial5.write(254);
        startUp = true;
        rutina = "linea";
        evacuacion_iniciada = false;
        evacuacion_straight = false;
        rescateAvisado = false;
        claw.lift();
        claw.depositCenter();
        action = 7;
        Serial5.write(249);

    }
    else
    {

        digitalWrite(LED_BUILTIN, HIGH);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, HIGH);
        // int lectura = ultrasonic.read();
        /*if(steer<30 or steer>150){
            counter++;
        }
        if(laststeer<30 and steer>30 and counter>15){
            runTime(20,1,0.5,500);
            counter=0;
        }
        if(laststeer>150 and steer<150 and counter>15){
            runTime(20,1,-0.5,500);
            counter=0;
        }
        */
        while (rutina == "linea" && digitalRead(32) == 0)
        {
            bool plateadoDetectado = false;

            color_detected = get_color_fast();
            leer_tof();
            leer_ultrasonidos();
            
            if (color_detected == "Plateado") {

                    plateadoDetectado = true;

                    if (!rescateAvisado) {
                        Serial5.write(241);
                        rescateAvisado = true;
                    }
            }

            if (color_detected == "Rojo") {
                    runTime(0, FORWARD, 0, 10000);
                    break;
            
            }
            
            if (taskDone)
            { // robot is currently not performing any task

                // //Serial.println("Incoming Task: ");
                // //Serial.println(green_state);
                if (green_state == 0)
                {
                    action = 7;
                }
                if (green_state == 1)
                {
                    action = 6; // verde izquierda  
                }
                if (green_state == 2)
                {
                    action = 5; // verde derecha
                }
                if (green_state == 3)
                {
                    action = 14;
                }
                if (front_distance != 0 && front_distance < 12)
                {
                    action = 1;
                }
                
                if (green_state == 14)
                {
                    action = 12;
                }
                if (silver_line == 1)
                {
                    action = 2;
                }
                if (plateadoDetectado) {
                    action = 2;
                }


                switch (action)
                {
                case 1:
                    digitalWrite(BUZZER, HIGH);
                    delay(100);
                    digitalWrite(BUZZER, LOW);
                        RanNumber = random(3);
                        RanNumber = random(1, 3);
                        if (RanNumber == 1)
                        {
                            runAngle(25, FORWARD, -95);
                            runTime(30, FORWARD, -0.35, 1000);
                            while (digitalRead(32) == 0)
                            {
                                robot.steer(30, FORWARD, -0.35);
                                // serialEvent5();
                                if (get_color_fast() == "Negro")
                                {
                                    runAngle(30, FORWARD, -90);
                                    break;
                                }
                            }
                        }
                        if (RanNumber == 2)
                        {
                            runAngle(25, FORWARD, 95);
                            runTime(30, FORWARD, 0.35, 1000);
                            while (digitalRead(32) == 0)
                            {
                                robot.steer(30, FORWARD, 0.35);
                                // serialEvent5();
                                if (get_color_fast() == "Negro")
                                {
                                    runAngle(30, FORWARD, 90);
                                    break;
                                }
                            }
                        }
                    
                    break;
                case 2:
                    digitalWrite(BUZZER, HIGH);
                    delay(100);
                    digitalWrite(BUZZER, LOW);
                    rutina="rescate";
                    rescateAvisado = true;

                    digitalWrite(RELAY,HIGH);
                    ball_counter=0;
                    veces_deposit = 0;
                    alineado=false;
                    depositando=false;
                    runTime(0, FORWARD, 0, 1000);
                     runTime(30,FORWARD,0,2000);


                   
                    leer_ultrasonidos();
                    if(left_distance < right_distance)
                    {
                        /*runAngle(30,FORWARD,90);
                        runTime(0,BACKWARD,0,900);
                        runTime(40,BACKWARD,0,380);
                        runTime(40,FORWARD,0,800);
                        runTime(0,BACKWARD,0,1000);*/
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0);
                        if (angulo_rescate < 0) angulo_rescate += 360;
                        runTime(20,FORWARD,0,1500);
                        runTime(0,BACKWARD,0,1000);
                        runAngle(30,FORWARD,45);
                        runTime(30,FORWARD,0,3000);

                        pared="left";
                        lado_plateado="derecha";
                    }
                    if(right_distance < left_distance)
                    {
                       /* runAngle(30,FORWARD,-90);
                        runTime(0,BACKWARD,0,900);
                        runTime(60,BACKWARD,0,380);
                        runTime(40,FORWARD,0,800);*/
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0); 
                        if (angulo_rescate < 0)                        
                        angulo_rescate += 360;
                        runTime(20,FORWARD,0,1500);
                        runTime(0,BACKWARD,0,1000);
                        runAngle(30,FORWARD,-45);
                        runTime(30,FORWARD,0,3000);
                        pared="right";
                        lado_plateado="izquierda";
                    }
                   /* if(right_distance && left_distance>=50){
                        leer_ultrasonidos();

                        while(front_distance>12){
                            robot.steer(25,FORWARD,0);
                            leer_ultrasonidos();
                        }
                        runAngle(30,FORWARD,180);
                        runTime(0,BACKWARD,0,800);
                        runTime(60,BACKWARD,0,200);
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0); 
                        if (angulo_rescate < 0)                        
                        angulo_rescate += 360;
                        lado_plateado="medio";
                        pared="derecha";
                    }*/
                    runTime(0,FORWARD,0,3000);
                    tiemporescate=millis();
                    break;
                case 6:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    if (green_state == 1)
                    {
                        runAngle(35, FORWARD, -60);
                    }
                    break;
                case 5:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    if (green_state == 2)
                    {
                        runAngle(25, FORWARD, 60);
                    }
                    break;
                case 7: // linetrack
                
                    {int velocidadAjustada = ajustarVelocidadPorPendiente(25);

                     if (steer < -0.7 || steer > 0.7)
                    {
                            robot.steer(55, FORWARD, steer);
                    }

                    else
                    {
                        robot.steer(velocidadAjustada, FORWARD, steer);
                    }
                
                    break;
                    }

                case 12:
                    {
                        serialEvent5();

                        float diferencia = calcularDiferenciaAngulo(leer_yaw(), centrar);
                        runAngle(30, FORWARD, diferencia);
                        runTime(30, BACKWARD, 0, 300);
                        runTime(0, FORWARD, 0, 2000);
                        unsigned long waitStart = millis();
                    while(digitalRead(32) == 0){
                        robot.steer(0, FORWARD, 0);
                        
                        serialEvent5();

                        if (fixIssue58Enabled() && (millis() - waitStart) >= 5000)
                        {
                            break;
                        }

                        if (green_state == 15)
                        {
                            runTime(30, FORWARD, 0, 500);
                            runAngle(30, FORWARD, 80);
                            break;
                        }

                        if (green_state == 16)
                        {
                            runTime(30, FORWARD, 0, 200);
                            runAngle(30, FORWARD, -80);
                            break;
                        }

                        if (green_state == 17)
                        {
                            runDistance(30, FORWARD, 15);
                            break;
                        }

                        if (!fixIssue58Enabled())
                        {
                            break;
                        }
                    }
                    }

                    if (fixIssue58Enabled())
                    {
                        break;
                    }

                case 14: // turn 180 deg for double green squares
                    serialEvent5();
                    if (green_state == 3)
                    {
                        runAngle(30, FORWARD, 180);
                        runTime(30, BACKWARD, 0, 200);
                    }
                    action = 7;
                    break;

                }

            }
        }
        while (rutina == "rescate" && digitalRead(32) == 0)
        {
            digitalWrite(RELAY, HIGH);
           digitalWrite(LED_BUILTIN, LOW);
            serialEvent5();
            robot.steer(speed, FORWARD, steer);
            digitalWrite(0,LOW);

            if (green_state == 6) // Recoleccion Pelota negra
            {
                digitalWrite(RELAY, HIGH);
                runTime(0,FORWARD,0,1000);
                claw.lower();
                nonBlockingDelay(1000);
                claw.depositCenter();
                nonBlockingDelay(1400);
                claw.sortRight();
                nonBlockingDelay(1000);
                runDistance(30,FORWARD,5);
                runTime(0,FORWARD,0,1000);
                claw.close();
                nonBlockingDelay(1000);
                digitalWrite(BUZZER, HIGH);
                delay(100); 
                digitalWrite(BUZZER, LOW);
                runTime(0,FORWARD,0,1000);
                claw.lift();
                nonBlockingDelay(1000);
                claw.open();
                nonBlockingDelay(1000);
                runTime(30,FORWARD,0,200);
                runTime(30,BACKWARD,0,200);
                 ball_counter++;
            }
            if (green_state == 7)            { // Recoleccion Pelota platea
                digitalWrite(RELAY, HIGH);
                runTime(0,FORWARD,0,1000);
                claw.lower();
                claw.sortLeft();
                nonBlockingDelay(1400);
                claw.depositCenter();
                nonBlockingDelay(1000);
                runDistance(20,FORWARD,5);
                runTime(0,FORWARD,0,1000);
                claw.close();
                nonBlockingDelay(1000);
                digitalWrite(BUZZER, HIGH);
                delay(100); 
                digitalWrite(BUZZER, LOW);
                runTime(0,FORWARD,0,1000);
                claw.lift();
                nonBlockingDelay(1000);
                claw.open();
                nonBlockingDelay(1000);
                runTime(30,FORWARD,0,200);
                runTime(30,BACKWARD,0,200);
                ball_counter++;
            }

            if (ball_counter>= 3 && depositando==false)
            {
                digitalWrite(RELAY, HIGH);
                Serial5.write(248);
                depositando=true;
                serialEvent5();
                robot.steer(speed, FORWARD, steer);   
            }
            if(green_state == 9)//verde
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    while(digitalRead(32) == 0){
                        robot.steer(15, BACKWARD, 0);
                        if (digitalRead(FCL) == HIGH && digitalRead(FCR) == HIGH)
                        {
                            break;
                        }
                    }
                    claw.depositRight();
                    nonBlockingDelay(2000);
                    claw.depositCenter();
                    runTime(0,FORWARD,0,500);
                    runTime(30,BACKWARD,0,500);
                    runTime(0,FORWARD,0,500);
                    runDistance(30,FORWARD,4+60);
                    veces_deposit++;
                }
            if (green_state == 8)//rojo
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    while(digitalRead(32) == 0){
                        robot.steer(15, BACKWARD, 0);
                        if (digitalRead(FCL) == HIGH && digitalRead(FCR) == HIGH)
                        {
                            break;
                        }
                    }
                    claw.depositLeft();
                    nonBlockingDelay(2000);
                    claw.depositCenter();
                    runTime(0,FORWARD,0,500);
                    runTime(0,FORWARD,0,500);
                    runAngle(20,FORWARD,45);
                    runTime(30,FORWARD,0,500);
                    runAngle(20,FORWARD,-45);

                    veces_deposit++;

                }
            if (veces_deposit == 2)
            {
                if (!evacuacion_iniciada) {
                    Serial5.write(247);
                    evacuacion_iniciada = true;
                }
                rutina = "evacuacion";
                break;
            }
            /*if(green_state == 10)
                { 
                    estado == "salida"
                    runTime(0,BACKWARD,0,3000);

                }*/
            
        } // end while (rutina == "rescate" && digitalRead(32) == 0)
        while (rutina == "evacuacion" && digitalRead(32) == 0)
        {
            color_detected = get_color_fast();

            if (color_detected == "Negro") {
                accionNegro();
            }
            else if (color_detected == "Plateado") {
                accionPlateado();
            }

            robot.steer(30, FORWARD, 0);

            digitalWrite(RELAY, LOW);
            serialEvent5();
            leer_ultrasonidos();

            robot.steer(20, FORWARD, 0);

            if (right_distance == 0 || (right_distance - last_right_distance) > 30) {
                runDistance(30,FORWARD,8);

                if (detectarNegro()) accionNegro();
                if (detectarPlateado()) accionPlateado();

                runAngle(30, FORWARD, 90);
                runDistance(20,FORWARD,1);
            }

            last_right_distance = right_distance;

            if (right_jump_counter >= 3) {
                if (detectarNegro()) accionNegro();

                right_jump_counter = 0;
                robot.steer(0,FORWARD,0);
                runAngle(30, FORWARD, 90);
            }

            if (green_state == 0 && front_distance != 0 && front_distance < 10) {
                runAngle(30, FORWARD, 90);

                if (detectarNegro()) accionNegro();
            }

            if ((green_state == 8 || green_state == 9) && front_distance != 0 && front_distance < 30) {

                if (detectarNegro()) accionNegro();

                resetear_bno();
                runAngle(30, FORWARD, 90);
                runDistance(30, FORWARD, 27);
                runAngle(30, FORWARD, -90);

                leer_ultrasonidos();

                while (digitalRead(32) == 0 && front_distance != 0 && front_distance > 15) {
                    robot.steer(30, FORWARD, 0);
                    leer_ultrasonidos();
                }

                runAngle(30, FORWARD, 180);
                runDistance(15, BACKWARD, 5);
                runAngle(30, FORWARD, -90);

                green_state = 0;
            }


        }
    } // end else (principal del loop)
} // end loop()
