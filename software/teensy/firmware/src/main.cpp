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
#include <telemetria.h>

// ============================================================================
#define INVERTIR_VERDES     false   // D1.1 / 2025: verde izq<->der
#define MODO_DOBLE_VERDE    0       // 0=180(normal) | 1=ignorar/seguir recto (D1.2)
#define MODO_ROJO           0       // 0=parar(meta) | 1=girar180(profe) | 2=simple180/doble-parar sensor(2025)
#define ESQUIVE_POR_PARIDAD false   // D2.2: par=izq, impar=der (false=random normal)
#define CONTAR_VERDES       false   // D2.1: habilita el contador de verdes
#define INVERTIR_DEPOSITO   false   // D2.3: impar invierte zonas (necesita CONTAR_VERDES)
#define SUPERTEAM           0       // SUPER TEMA: 1=puente con ESP32-MINI por Serial8 | 0=corrida normal
#define TELEMETRIA          1       // TELEMETRIA: 1=envia TODOS los valores por Serial8 a la ESP32-MINI (AP+GUI) | 0=off
// ============================================================================
//  TELEMETRIA — Teensy -> ESP32-MINI por Serial8 (RX=pin34 / TX=pin35, 3.3V, 115200)
//  La ESP32-MINI monta un AP WiFi y sirve una GUI web con TODOS los valores de
//  control. Es 100% NO INTRUSIVA: escribe una linea JSON por Serial8 a 10 Hz y,
//  si el buffer TX no tiene lugar, DESCARTA el frame (nunca frena el control).
//  Firmware ESP32 + GUI: software/esp32/telemetria/  (ver README ahi).
//  NOTA: TELEMETRIA y SUPERTEAM comparten Serial8 -> no activar ambos a la vez.
// ============================================================================
#if SUPERTEAM && TELEMETRIA
#error "SUPERTEAM y TELEMETRIA comparten Serial8: activar solo uno (poner el otro en 0)."
#endif
#if TELEMETRIA
Telemetria telemetria(Serial8, 100);   // 100 ms => 10 Hz
void enviarTelemetria();

// ============================================================================
//  DIAGNOSTICO DE VERDES — para VER si el green_state llega y se confirma en la
//  Teensy (el problema de los verdes 1/2/3). Cuenta, por tipo (1=izq,2=der,3=doble):
//    g_rx   : cuantos verdes DISTINTOS llegaron de la RPi (flanco, no repeticion)
//    g_act  : cuantos se CONFIRMARON en el re-chequeo y ejecutaron el giro
//    g_kill : cuantos MATO el re-chequeo (el verde se apago/cambio durante el avance)
//  g_last_recheck_gs = green_state visto en el ultimo re-chequeo (0 = se apago).
//  Son contadores PUROS: no cambian en nada el comportamiento del robot.
// ============================================================================
unsigned long g_rx[4]   = {0, 0, 0, 0};
unsigned long g_act[4]  = {0, 0, 0, 0};
unsigned long g_kill[4] = {0, 0, 0, 0};
int  g_last_type = 0;              // ultimo verde recibido (1/2/3)
unsigned long g_last_ms = 0;       // millis de la ultima llegada
int  g_last_recheck_gs = -1;       // green_state en el ultimo re-chequeo
int  g_prev_seen = 0;              // estado previo para detectar flancos

// Llamar donde la RPi setea green_state: cuenta cada verde nuevo (flanco).
inline void telemGreenRx(int gs)
{
    if (gs != g_prev_seen)
    {
        if (gs >= 1 && gs <= 3)
        {
            g_rx[gs]++;
            g_last_type = gs;
            g_last_ms = millis();
        }
        g_prev_seen = gs;
    }
}

// Llamar en el re-chequeo de las maniobras de verde (case 5/6/14), con el
// green_state que se vio al re-chequear. Registra si giro o si lo mato.
inline void telemGreenResultado(int tipo, int gsEnRecheck)
{
    if (tipo < 1 || tipo > 3) return;
    g_last_recheck_gs = gsEnRecheck;
    if (gsEnRecheck == tipo) g_act[tipo]++;
    else                     g_kill[tipo]++;
}
#else
inline void enviarTelemetria() {}
inline void telemGreenRx(int) {}
inline void telemGreenResultado(int, int) {}
#endif

// ============================================================================
//  SUPER TEMA — puente Teensy <-> ESP32-MINI por Serial8 (RX=pin34 / TX=pin35, 3.3V)
//  Cableado: TX8(35)->ESP RX ; RX8(34)<-ESP TX ; GND comun. Sin level shifter.
//  Teensy -> ESP32 (salientes):  'L'=verde izq  'R'=verde der  'D'=doble  'X'=fin(rojo)
//  ESP32  -> Teensy (entrante):  'S'=start (arranque del companiero por BLE/BT)
//  OJO: serialEvent8() se llama A MANO (igual que serialEvent5): el loop se bloquea
//       en los while largos y el callback automatico casi nunca corre.
// ============================================================================
#if SUPERTEAM
const uint8_t SUPER_VERDE_IZQ   = 'L';
const uint8_t SUPER_VERDE_DER   = 'R';
const uint8_t SUPER_VERDE_DOBLE = 'D';
const uint8_t SUPER_FIN_ROJO    = 'X';
const uint8_t SUPER_START       = 'S';
const uint8_t SUPER_REARM       = 'B';  // Teensy reinicio (LoP/stop) -> que la C3 reenvie el start
bool superStart        = false;   // true cuando el companiero mando 'S'
bool super_fin_enviado = false;   // one-shot del aviso de rojo/fin
void serialEvent8();
#endif



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
bool verde_accion = false;
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
bool verde_stop=false;
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
int ball_counter=1;
bool evacuacion_iniciada=false;
bool evacuacion_straight=false;
bool silver_latch=false;  // true mientras seguimos "sobre" un plateado ya atendido (evita repetir la accion)
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
    // Telemetria primero: asi sigue fluyendo aunque el fix59 este desactivado y
    // durante TODAS las maniobras bloqueantes (runTime/runAngle/runDistance...).
    // Es rate-limited y no bloqueante: costo despreciable.
    enviarTelemetria();

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

// Limpia el historial del filtro de color para no arrastrar muestras viejas
// (stale) despues de una accion bloqueante en evacuacion. Fuerza que la
// proxima clasificacion se construya solo con muestras frescas.
void reset_color_history()
{
    color_history_index = 0;
    color_history_count = 0;
    last_color_sample_ms = 0;
    last_color_detected = "Desconocido";
}
String classify_color(uint16_t r, uint16_t g, uint16_t b, uint16_t c)
{
    float ratio_rc = c > 0 ? static_cast<float>(r) / static_cast<float>(c) : 0.0f;
    float ratio_rg = g > 0 ? static_cast<float>(r) / static_cast<float>(g) : 0.0f;
    float ratio_rb = b > 0 ? static_cast<float>(r) / static_cast<float>(b) : 0.0f;

    int diff_bg = static_cast<int>(b) - static_cast<int>(g);

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
        Serial.print(" | B-G: "); Serial.print(diff_bg);
        Serial.print(" | -> ");
    }

    String detected = "Desconocido";

    bool esRojo =
        (
            c >= 380 && c <= 900 &&
            ratio_rc >= 0.32f &&
            ratio_rg >= 1.10f &&
            ratio_rb >= 1.00f
        )
        ||
        (
            c > 900 && c <= 1300 &&
            ratio_rc >= 0.255f &&
            ratio_rg >= 0.75f &&
            ratio_rb >= 0.67f
        );

bool esPlateado =
    (
        c >= 1300 &&
        ratio_rc >= 0.246f &&
        ratio_rc <= 0.290f
    );

bool esBlanco =
    (
        c >= 430 &&
        ratio_rc >= 0.195f &&
        ratio_rc <  0.246f
    );

    if (esRojo)
    {
        detected = "Rojo";
    }
    else if (esPlateado)
    {
        detected = "Plateado";
    }
    else if (esBlanco)
    {
        detected = "Blanco";
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

String 
get_color_fresh(unsigned long timeoutMs = APDS_COLOR_FRESH_TIMEOUT_MS)
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
        if      (c > 1950 && ratio_rc > 0.234)                          Serial.println("Plateado");
        else if (c > 1500 && ratio_rc <= 0.235)                         Serial.println("Blanco");
        else if (c >= 300 && c <= 600 && ratio_rg > 1.6f && ratio_rb > 1.5f) Serial.println("Rojo");
        else if (c < 600)                                                Serial.println("Negro");
        else                                                             Serial.println("Verde");
        lastPrint = millis();
    }
    // Returns en el mismo orden que el print
    if (c > 1700 && ratio_rc > 0.234)        return "Plateado";
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
            telemGreenRx(data);   // TELEMETRIA: cuenta verdes que llegan de la RPi
    // Serial.print("[RX] green_state recibido: ");
    // Serial.println(green_state);
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

#if SUPERTEAM
// SUPER TEMA: lee el comando de arranque del companiero (llega por la ESP32-MINI).
// Se llama A MANO donde haga falta escuchar (igual criterio que serialEvent5).
void serialEvent8()
{
    while (Serial8.available() > 0)
    {
        int data = Serial8.read();
        if (data == SUPER_START)
            superStart = true;
    }
}
#endif

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


void runDistanceEvacuacion(int speed, int Distance) {
    runTime(30, BACKWARD, 0, 20);
    runTime(30, FORWARD, 0, 20);
    reset_enconder();
    int32_t encoder = 25 * Distance;
    bool stopOnExit = fixIssue60Enabled();
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);

    while (true) {
        if (fixIssue60Enabled() && (millis() - startTime) >= timeoutMs) break;
        int32_t frCount = fr.pulseCount;
        int32_t flCount = fl.pulseCount;
        if (frCount >= encoder || flCount >= encoder) break;   // llego a la distancia pedida
        front_distance = sonar[0].ping_cm();
        if (front_distance != 0 && front_distance <= 18) break; // pared cerca -> corto el avance
        robot.steer(speed, FORWARD, 0);
        serviceMotionBackgroundTasks();
        delay(10);

        if (Serial5.available() > 0) {
            if (fixIssue63Enabled())
                serialEvent5();
            else {
                int lecturas = Serial5.read();
                Serial.print(lecturas);
            }
        }

        if (digitalRead(32) == 1) { // switch off
            Serial5.write(255);
            break;
        }
    }

    if (stopOnExit)
        robot.steer(0, FORWARD, 0);
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
    runDistance(30, FORWARD, 5);
    Serial5.write(249);
    reset_color_history();
    digitalWrite(RELAY, LOW);

    // 1) romper la inercia (jiggle corto, como hace runDistance al arrancar)
    runTime(20, BACKWARD, 0, 300);
    runTime(20, FORWARD, 0, 300);

    // 2) quedarse QUIETO leyendo serial mientras la RPi sale de evacuacion y
    //    arranca la vision de linea (teardown ~1-2 s). Asi no se mueve con datos viejos.

    robot.steer(0, FORWARD, 0);
    unsigned long t0 = millis();
    while (millis() - t0 < 800) {
        serialEvent5();
    }

    // 3) limpiar lo stale de evacuacion para arrancar linea derecho

    green_state = 0;
    action = 7;
    steer = 0;
    speed = 0;
    taskDone = true;

    rutina = "linea";
}

void accionPlateado() {
    runDistance(30, FORWARD,3);
    Serial5.write(249);
    reset_color_history();
    digitalWrite(RELAY, LOW);

    // 1) romper la inercia (jiggle corto, como hace runDistance al arrancar)
    runTime(20, BACKWARD, 0, 300);
    runTime(20, FORWARD, 0, 300);

    // 2) quedarse QUIETO leyendo serial mientras la RPi sale de evacuacion y
    //    arranca la vision de linea (teardown ~1-2 s). Asi no se mueve con datos viejos.

    robot.steer(0, FORWARD, 0);
    unsigned long t0 = millis();
    while (millis() - t0 < 800) {
        serialEvent5();
    }

    // 3) limpiar lo stale de evacuacion para arrancar linea derecho

    green_state = 0;
    action = 7;
    steer = 0;
    speed = 0;
    taskDone = true;

    rutina = "linea";
}

bool detectarNegro() {
    color_detected = get_color_fresh();
    return (color_detected == "Negro");
}

bool detectarPlateado() {
    color_detected = get_color_fresh();
    return (color_detected == "Plateado");
}

// Lecturas frescas consecutivas necesarias para confirmar un color antes de
// actuar en evacuacion. Subir si hay falsos positivos; bajar si queda lento.
constexpr uint8_t EVAC_COLOR_CONFIRM_SAMPLES = 2;

// Confirma que el sensor ve 'objetivo' en N lecturas frescas seguidas.
// Filtra ruido/sombras/reflejos que provocaban falsos "Negro"/"Plateado".
bool confirmarColor(const String &objetivo)
{
    for (uint8_t i = 0; i < EVAC_COLOR_CONFIRM_SAMPLES; i++)
    {
        if (get_color_fresh() != objetivo)
            return false;
    }
    return true;
}

// Detecta color en evacuacion con confirmacion anti-ruido y ejecuta la accion
// correspondiente. Devuelve true si ejecuto una accion (Negro o Plateado).
bool procesarColorEvacuacion()
{
    color_detected = get_color_fast();

    // El robot se despego del plateado (ve otro color confiable): rehabilita
    // una futura deteccion. "Desconocido" = sin dato fresco, no cuenta.
    if (color_detected != "Plateado" && color_detected != "Desconocido")
    {
        silver_latch = false;
    }

    if (color_detected == "Negro" && confirmarColor("Negro"))
    {
        return false;
    }

    if (color_detected == "Plateado" && !silver_latch && confirmarColor("Plateado"))
    {
        Serial.println("[EVAC] Plateado confirmado -> accionPlateado");
        accionNegro();
        silver_latch = true;  // ya atendido; no repetir hasta despegarse del plateado
        return true;
    }

    return false;
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
float leer_pitch()
{  
    sensors_event_t event;
    bno.getEvent(&event);

    pitch = event.orientation.y; // eje que estás usando para inclinación
    return pitch;
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
    if (pitch > 3.9)
    {
            velocidadAjustada = 45;
    }
    else if (pitch > 25)
    {
           runTime(100, FORWARD, 0.35, 100);
           runTime(100, FORWARD, -0.35, 100);
    }
    else{
        velocidadAjustada= 40;
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

// Decide si hay que esquivar en evacuacion. Dos casos separados:
//  - Esquina de deposito: la camara ve triangulo rojo/verde (green_state 8/9)
//    Y el ultrasonido confirma cercania (<=31 cm). Fusion camara + ultrasonido.
//  - Pared frontal lisa: solo ultrasonido, dispara mas cerca (<=18 cm).
bool debeEsquivar()
{
    if ((green_state == 8 || green_state == 9) && front_distance != 0 && front_distance <= 31)
        return true;

    return false;
}

// Maniobra de esquive en evacuacion: retrocede, gira 90, avanza paralelo, gira
// 90, retrocede hasta los finales de carrera y se reacomoda. La usan tanto la
// esquina de deposito como la pared frontal lisa.
void maniobraEsquive()
{
    resetear_bno();
    runTime(30, BACKWARD, 0, 300);
    runAngle(30, FORWARD, 90);
    runDistance(30, FORWARD, 27);
    runAngle(30, FORWARD, 90);
    while (rutina == "evacuacion" && digitalRead(32) == 0) {
        robot.steer(30, BACKWARD, 0);
        serialEvent5();
        if (digitalRead(FCL) == 1 && digitalRead(FCR) == 1)
            break;
    }
    runAngle(30, FORWARD, -90);
}


// ============================================================================
//  TOOLKIT CHALLENGE — funciones para las FLAGS de arriba (ver PLAYBOOK)
// ============================================================================
// --- Contador de verdes + paridad (D2.1) ---
#define DOBLE_CUENTA_COMO 2     // un doble verde, suma 2 o 1? (preguntar al arbitro)
int  verdes_total = 0;
bool verde_estaba = false;

bool esMarcaVerde(int gs)
{
    return (gs == 1 || gs == 2 || gs == 3);
}

// Devuelve 1, 2 o 3 si el verde se mantiene confirmado.
// Devuelve 0 si fue falso, cambió o desapareció.
int confirmarMarcaVerde(unsigned long tiempoMs = 120)
{
    int gsInicial = green_state;

    if (!esMarcaVerde(gsInicial))
        return 0;

    unsigned long inicio = millis();

    while (millis() - inicio < tiempoMs)
    {
        serialEvent5();   // vuelve a leer el serial de la Raspberry

        if (green_state == 0)
            return 0;
        if (green_state != gsInicial)
            return 0;

        delay(5);
    }

    return gsInicial;
}

void actualizarContadorVerdes()
{
    serialEvent5();

    if (green_state == 0)
    {
        verde_estaba = false;
        return;
    }

    int verde_confirmado = confirmarMarcaVerde();

    if (esMarcaVerde(verde_confirmado) && !verde_estaba)
    {
        verdes_total += (verde_confirmado == 3) ? DOBLE_CUENTA_COMO : 1;
        verde_estaba = true;

#if SUPERTEAM
        // SUPER TEMA: avisar el verde confirmado al companiero (via ESP32-MINI)
        if      (verde_confirmado == 1) Serial8.write(SUPER_VERDE_IZQ);
        else if (verde_confirmado == 2) Serial8.write(SUPER_VERDE_DER);
        else if (verde_confirmado == 3) Serial8.write(SUPER_VERDE_DOBLE);
#endif

        Serial.print("[VERDE CONTADO] gs=");
        Serial.print(verde_confirmado);
        Serial.print(" total=");
        Serial.println(verdes_total);

        digitalWrite(BUZZER, HIGH);
        delay(40);
        digitalWrite(BUZZER, LOW);
    }
}
bool verdesPar()   { return (verdes_total % 2) == 0; }
bool verdesImpar() { return (verdes_total % 2) == 1; }
// --- Lado de esquive por paridad (D2.2) ---
int ladoEsquiveParidad() { return verdesPar() ? 1 : 2; }   // 1=izq, 2=der
// --- Invertir zonas de deposito (D2.3) ---
int trianguloEfectivo(int gs, bool invertir)
{
    if (!invertir) return gs;
    if (gs == 8) return 9;
    if (gs == 9) return 8;
    return gs;
}
// --- Linea roja simple vs doble por MOVIMIENTO (MODO_ROJO==2) ---
unsigned long rojo_ignorar_hasta = 0;   // cooldown anti-oscilacion tras el giro 180
// ============================================================================


// ============================================================================
//  DETECCION DE ATASCO — loma de burro (palos sobre la linea).
//  DATO DE CALIBRACION: en la loma una rueda queda CLAVADA (~0) y la otra
//  patina (~45). En recta las DOS giran parejo (~40 c/u). Discriminador:
//     min(|frD|,|flD|)  ->  ~0 atascado   /   ~40 recta
//  Atascado = una rueda parada (min < UMBRAL_RUEDA) sostenido >= STUCK_TIME_MS.
//  La aceleracion NO servia (igual en recta que trabado) -> descartada.
// ============================================================================
long          stuck_lastFr    = 0;
long          stuck_lastFl    = 0;
unsigned long stuck_since      = 0;
unsigned long stuck_lastSample = 0;
unsigned long atascoArmedSince = 0;    // cuando arranco a correr (startUp) -> para el grace period
const long          UMBRAL_RUEDA    = 15;    // pulsos/100ms: por debajo, una rueda esta "clavada" (TUNEAR)
const unsigned long STUCK_SAMPLE_MS = 100;   // cada cuanto mido las ruedas
const unsigned long STUCK_TIME_MS   = 3000;  // 3 s con una rueda parada = atascado
const unsigned long ATASCO_GRACE_MS = 8000;  // no disparar los primeros 8 s tras arrancar (ponerlo en pista)

// --- Traccion en pendiente: pisar las traseras cuando el pitch esta inclinado ---
const float  PITCH_RAMPA       = 12.0;  // pitch (grados) desde el cual considero "pendiente" (llano ~±5, rampa ~23)
const double POTENCIA_TRASERAS = 80;   // potencia (rpm objetivo, 0-159) para las traseras en pendiente

bool chequearAtasco(int comandoVel)
{

    unsigned long now = millis();

    // grace: recien arranco / apreto switch -> NO dispara (molesto al ponerlo en pista)
    if (now - atascoArmedSince < ATASCO_GRACE_MS)
    {
        stuck_since = now;
        return false;
    }

    // no comandado a avanzar -> no cuenta como atasco
    if (comandoVel <= 0)
    {
        stuck_since = now;
        return false;
    }

    // muestreo las ruedas cada STUCK_SAMPLE_MS (no en cada vuelta)
    if (now - stuck_lastSample >= STUCK_SAMPLE_MS)
    {
        stuck_lastSample = now;
        long frNow = (long)fr.pulseCount, flNow = (long)fl.pulseCount;
        long frD = labs(frNow - stuck_lastFr);   // giro rueda DERECHA en ~100 ms
        long flD = labs(flNow - stuck_lastFl);   // giro rueda IZQUIERDA en ~100 ms
        stuck_lastFr = frNow; stuck_lastFl = flNow;
        long minRueda = min(frD, flD);

        // telemetria de las TRASERAS (para ver si el boost las mueve en la rampa)
        static long stuck_lastBl = 0, stuck_lastBr = 0;
        long blNow = (long)bl.pulseCount, brNow = (long)br.pulseCount;
        long blD = labs(blNow - stuck_lastBl);
        long brD = labs(brNow - stuck_lastBr);
        stuck_lastBl = blNow; stuck_lastBr = brNow;

        // [CAL] atasco silenciado (rampa ya entendida) — reactivar si hace falta
        // Serial.print("[CAL] frD="); Serial.print(frD);
        // Serial.print(" flD="); Serial.print(flD);
        // Serial.print(" blD="); Serial.print(blD);
        // Serial.print(" brD="); Serial.print(brD);
        // Serial.print(" min="); Serial.print(minRueda);
        // Serial.print(" pitch="); Serial.println(pitch, 1);

        // las DOS ruedas giran (recta/curva/pivote) -> avanza bien -> reinicio el timer
        if (minRueda >= UMBRAL_RUEDA)
            stuck_since = now;
        // una rueda clavada (min < umbral) -> no reinicio, acumula tiempo
    }

    // EN PENDIENTE: NO disparar atasco (la rueda clavada es por la inclinacion;
    // el retroceso rampa abajo seria peligroso -> lo maneja el boost de traseras).
    if (pitch > PITCH_RAMPA)
    {
        stuck_since = now;
        return false;
    }

    // una rueda parada sostenido por >= STUCK_TIME_MS -> atascado
    return (now - stuck_since >= STUCK_TIME_MS);
}

void recuperarAtasco()
{
    Serial.println("[ATASCO] rueda clavada -> retro + avance brusco");
    runTime(90,  BACKWARD, 0, 150);   // retroceso corto (bajar de la loma)
    runTime(100, FORWARD,  0, 250);   // avance a full para saltarla
    // reiniciar el detector
    stuck_lastFr = (long)fr.pulseCount;
    stuck_lastFl = (long)fl.pulseCount;
    stuck_since  = millis();
    stuck_lastSample = millis();
}


#if TELEMETRIA
// ============================================================================
//  enviarTelemetria() — arma UNA linea JSON con TODOS los valores de control y
//  la manda por Serial8 a la ESP32-MINI. Rate-limited (10 Hz) y NO BLOQUEANTE
//  (si no hay lugar en el TX, descarta el frame). Se puede llamar desde
//  cualquier lado del loop sin miedo: el rate-limit y la guardia lo protegen.
//
//  Esquema (agrupado por subsistema, claves cortas para ahorrar ancho de banda):
//   t                          millis del Teensy
//   rpi  {speed,steer,green,silver,rxb,rxf,st}   enlace con la Raspberry (Serial5)
//   col  {d,r,g,b,c,ok}         sensor de color APDS9960 (filtrado) + estado
//   us   {f,l,r}                ultrasonidos frente/izq/der (cm)
//   tof  {l,r}                  ToF VL53L0X izq/der (mm)
//   imu  {yaw,pit,rol,cen}      BNO055 (grados) + angulo de referencia 'centrar'
//   enc  {fl,fr,bl,br}          contadores de encoder de las 4 ruedas
//   fsm  {rut,act,task,up,resc,balls,dep,verd,evi,evs,slatch,pared,lado,ran}
//   io   {sw,fcl,fcr,rel,buz,led}  entradas/salidas digitales
//   claw {busy}                garra ocupada (maquina de estados no bloqueante)
// ============================================================================
// Sanea floats para que el JSON SIEMPRE sea valido: un NaN/inf (p.ej. BNO sin
// calibrar o desconectado) imprimiria "nan"/"inf" y JSON.parse() en la GUI
// fallaria -> se quedaria en modo demo silenciosamente. Con esto, 0.0 en su lugar.
static float sanef(float v)
{
    return (isnan(v) || isinf(v)) ? 0.0f : v;
}

void enviarTelemetria()
{
    if (!telemetria.debeEnviar())
    {
        return;
    }

    // IMU fresco (una sola lectura I2C por frame, ~2 ms cada 100 ms: despreciable).
    sensors_event_t ev;
    bno.getEvent(&ev);
    float t_yaw = sanef(ev.orientation.x);
    float t_pit = sanef(ev.orientation.y);
    float t_rol = sanef(ev.orientation.z);
    float t_cen = sanef(centrar);

    // Color filtrado actual (lee los buffers de historial, no dispara el sensor).
    uint16_t cr = 0, cg = 0, cb = 0, cc = 0;
    get_filtered_color(cr, cg, cb, cc);

    // NOTA: los %s (color_detected/rutina/pared/lado_plateado) SOLO deben contener
    // literales cerrados sin comillas ni backslash (ver known_colors y las rutinas),
    // asi el JSON queda valido sin necesidad de escaparlos.
    long g_age = g_last_ms ? (long)(millis() - g_last_ms) : -1L;   // ms desde el ultimo verde (-1 = nunca)
    static char buf[896];
    int n = snprintf(
        buf, sizeof(buf),
        "{\"t\":%lu,"
        "\"rpi\":{\"speed\":%d,\"steer\":%.3f,\"green\":%d,\"silver\":%d,\"rxb\":%lu,\"rxf\":%lu,\"st\":%d},"
        "\"col\":{\"d\":\"%s\",\"r\":%u,\"g\":%u,\"b\":%u,\"c\":%u,\"ok\":%d},"
        "\"us\":{\"f\":%d,\"l\":%d,\"r\":%d},"
        "\"tof\":{\"l\":%d,\"r\":%d},"
        "\"imu\":{\"yaw\":%.1f,\"pit\":%.1f,\"rol\":%.1f,\"cen\":%.1f},"
        "\"enc\":{\"fl\":%ld,\"fr\":%ld,\"bl\":%ld,\"br\":%ld},"
        "\"fsm\":{\"rut\":\"%s\",\"act\":%d,\"task\":%d,\"up\":%d,\"resc\":%d,\"balls\":%d,\"dep\":%d,\"verd\":%d,\"evi\":%d,\"evs\":%d,\"slatch\":%d,\"pared\":\"%s\",\"lado\":\"%s\",\"ran\":%d},"
        "\"io\":{\"sw\":%d,\"fcl\":%d,\"fcr\":%d,\"rel\":%d,\"buz\":%d,\"led\":%d},"
        "\"claw\":{\"busy\":%d},"
        "\"grn\":{\"rx\":[%lu,%lu,%lu,%lu],\"act\":[%lu,%lu,%lu,%lu],\"kill\":[%lu,%lu,%lu,%lu],\"lt\":%d,\"age\":%ld,\"lrc\":%d}}\n",
        millis(),
        (int)speed, steer, green_state, silver_line, serial_bytes_rx, serial_frames_rx, serial5state,
        color_detected.c_str(), (unsigned)cr, (unsigned)cg, (unsigned)cb, (unsigned)cc, color_sensor_ok ? 1 : 0,
        front_distance, left_distance, right_distance,
        distance_left_tof, distance_right_tof,
        t_yaw, t_pit, t_rol, t_cen,
        (long)fl.pulseCount, (long)fr.pulseCount, (long)bl.pulseCount, (long)br.pulseCount,
        rutina.c_str(), action, taskDone ? 1 : 0, startUp ? 1 : 0, (int)rescateState,
        ball_counter, veces_deposit, verdes_total,
        evacuacion_iniciada ? 1 : 0, evacuacion_straight ? 1 : 0, silver_latch ? 1 : 0,
        pared.c_str(), lado_plateado.c_str(), RanNumber,
        digitalRead(SWITCH), digitalRead(FCL), digitalRead(FCR),
        digitalRead(RELAY), digitalRead(BUZZER), digitalRead(LED_ROJO),
        claw.busy() ? 1 : 0,
        g_rx[0], g_rx[1], g_rx[2], g_rx[3],
        g_act[0], g_act[1], g_act[2], g_act[3],
        g_kill[0], g_kill[1], g_kill[2], g_kill[3],
        g_last_type, g_age, g_last_recheck_gs);

    if (n < 0)
    {
        return;   // error de formato: no enviar
    }
    if (n >= (int)sizeof(buf))
    {
        n = sizeof(buf) - 1;   // snprintf trunco: clamp para no leer fuera de buf en enviar()
    }
    telemetria.enviar(buf, n);
}
#endif // TELEMETRIA

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
#if SUPERTEAM
    Serial8.begin(115200);         // SUPER TEMA: puente con la ESP32-MINI (RX=pin34 / TX=pin35)
#endif
#if TELEMETRIA
    telemetria.begin(115200);      // TELEMETRIA: abre Serial8 hacia la ESP32-MINI (AP + GUI)
#endif
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
    enviarTelemetria();   // TELEMETRIA (rate-limited + no bloqueante)
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
        silver_latch = false;
        action = 7;
        startUp = false;
        verde_stop=false;
        last_right_distance = 0;
        right_jump_counter = 0;
        verdes_total = 0; verde_estaba = false; rojo_ignorar_hasta = 0;   // === CHALLENGE: reset al reiniciar ===
        taskDone = true;
        Serial5.write(255);
        verdes_total=0;
        while (true)
        {
            enviarTelemetria();   // TELEMETRIA en idle (util para calibrar en banco)
            robot.steer(0, 0, 0);
                    digitalWrite(RELAY,LOW);
            claw.lift();
            get_color_fast();
            serialEvent5();
            centrar = leer_yaw();            
            centrar = fmod(centrar, 360.0);
             if (centrar < 0) centrar += 360;
            digitalWrite(LED_BUILTIN, HIGH);
            // digitalWrite(BUZZER, HIGH);
            digitalWrite(LED_ROJO, HIGH);
            delay(500);
            robot.steer(0, 0, 0);
            //Serial.println(leer_pitch()); // para imprimirlo
           get_color_fast();
           //Serial.println("FCL: " + String(digitalRead(FCL)));
            //Serial.println("FCR: " + String(digitalRead(FCR)));
            digitalWrite(LED_BUILTIN, LOW);
            digitalWrite(BUZZER, LOW);
            digitalWrite(LED_ROJO, LOW);
            digitalWrite(RELAY,LOW);
            claw.open();
            delay(500);
         
            get_color_fast();

            if (digitalRead(SWITCH) == 0)
            {
                break;
            }
        }
    }
    else if (digitalRead(32) == 0 && !startUp)
    {
#if SUPERTEAM
        // SUPER TEMA: ya en modo funcionamiento, esperar el 'start' del companiero
        // (BLE desde el Spike / BT clasico desde la ESP32). Parpadea el LED rojo.
        super_fin_enviado = false;
        Serial8.clear();                    // descartar 'S' viejos del buffer (evita auto-start tras LoP)
        Serial8.write(SUPER_REARM);         // re-arm: pedir a la C3 que reenvie el start
        while (!superStart && digitalRead(32) == 0) {
            serialEvent8();                 // escuchar la ESP32 a mano (el loop se bloquea)
            digitalWrite(LED_ROJO, HIGH);
            delay(120);
            digitalWrite(LED_ROJO, LOW);
            delay(120);
        }
        superStart = false;                 // consumir el comando para la proxima corrida
#endif
        digitalWrite(LED_BUILTIN, LOW);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, LOW);
        runTime(20, BACKWARD, 0, 300);
        runTime(20, FORWARD, 0, 300);
        // Serial5.write(254);
        startUp = true;
        atascoArmedSince = millis();   // arranca el grace: no dispara el anti-atasco al ponerlo en pista
        rutina = "linea";
        evacuacion_iniciada = false;
        evacuacion_straight = false;
        silver_latch = false;
        rescateAvisado = false;
        claw.lift();
        claw.depositCenter();
        action = 7;
        verde_accion=false;
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
            enviarTelemetria();   // TELEMETRIA (seguimiento de linea)
            bool plateadoDetectado = false;
            color_detected = get_color_fast();
            leer_tof();
            leer_ultrasonidos();
            if (CONTAR_VERDES || SUPERTEAM) actualizarContadorVerdes();   // === CHALLENGE D2.1 / SUPER TEMA ===
           
            if (color_detected == "Plateado") {   // confirmo 2 lecturas -> filtra brillos aislados

                    plateadoDetectado = true;

                    if (!rescateAvisado) {
                        Serial5.write(241);
                        rescateAvisado = true;
                    }
            }

            // === CHALLENGE: rojo segun MODO_ROJO ===
            if (color_detected == "Rojo" && millis() >= rojo_ignorar_hasta) {
#if SUPERTEAM
                // SUPER TEMA: avisar al companiero que llego al rojo / termino (one-shot)
                if (!super_fin_enviado) { Serial8.write(SUPER_FIN_ROJO); super_fin_enviado = true; }
#endif
                if (MODO_ROJO == 0) {
                    runTime(0, FORWARD, 0, 10000);     // parar (meta normal)
                    break;
                }
                else if (MODO_ROJO == 1) {
                    runAngle(30, FORWARD, 180);        // girar 180 (profe)
                    runTime(30, FORWARD, 0, 800);         // avanzar (meta)
                }
                else { 
                    unsigned long tcruce = millis();
                    while (get_color_fresh() == "Rojo" && millis() - tcruce < 2000) {
                        robot.steer(30, FORWARD, 0);
                    }
                    unsigned long inicio = millis();
                    bool doble = false;
                    while (millis() - inicio < 2500) {
                        robot.steer(30, FORWARD, 0);
                        if (get_color_fresh() == "Rojo") { doble = true; break; }  
                    }
                    unsigned long avanzado = millis() - inicio;
                    robot.steer(0, FORWARD, 0);
                    // 3) decido
                    if (doble) {
                        runTime(0, FORWARD, 0, 5000);          // DOBLE -> meta (parar)
                        break;
                    } else {
                        runTime(30, BACKWARD, 0, avanzado);    // SIMPLE -> retrocedo lo que avance
                        runAngle(30, FORWARD, 180);            // y giro 180
                        rojo_ignorar_hasta = millis() + 1500;  // cooldown anti-oscilacion
                    }
                }
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
    action = (verdes_total < 4) ? 6 : 20;   // <3 verdes: giro (case 6) | >=3: "otra cosa"
}
if (green_state == 2)
{
    action = (verdes_total < 4) ? 5 : 20;   // <3 verdes: giro (case 5) | >=3: "otra cos
}

                if (green_state == 3)
                {
                    action = 14;   // === CHALLENGE D1.2: 1=ignorar/recto ===
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

                    
                        // === CHALLENGE D2.2: esquive por paridad ===
                        if (ESQUIVE_POR_PARIDAD) {
                            RanNumber = ladoEsquiveParidad();   // par->izq(1), impar->der(2)
                        } else {
                            RanNumber = random(3);
                            RanNumber = random(1, 3);
                        }
                        if (RanNumber == 1)
                        {
                            runAngle(25, FORWARD, -95);
                                                        get_color_fast();
                                        while (digitalRead(32) == 0)
                            {
                                robot.steer(77, FORWARD, -0.38);
                                // serialEvent5();
                                if (get_color_fast() == "Negro")
                                {
                                    runAngle(70, FORWARD, -90);
                                    break;
                                }
                            }
                        }
                        if (RanNumber == 2)
                        {
                            runAngle(25, FORWARD, 95);
                            get_color_fast();
                            while (digitalRead(32) == 0)
                            {
                                robot.steer(77, FORWARD, 0.38);
                                // serialEvent5();
                                if (get_color_fast() == "Negro")
                                {
                                    runAngle(70, FORWARD, 90);
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
                    telemGreenResultado(1, green_state);   // TELEMETRIA: giro o matado por re-chequeo
                    if (green_state == 1)
                    {
                        runAngle(35, FORWARD, INVERTIR_VERDES ? 60 : -60);   // === CHALLENGE D1.1 ===
                    }
                    break;
                case 5:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    telemGreenResultado(2, green_state);   // TELEMETRIA: giro o matado por re-chequeo
                    if (green_state == 2)
                    {
                        runAngle(25, FORWARD, INVERTIR_VERDES ? -60 : 60);   // === CHALLENGE D1.1 ===
                    }
                    break;
                case 7: // linetrack
               
                    {int velocidadAjustada = ajustarVelocidadPorPendiente(45);

                     if (chequearAtasco(velocidadAjustada)) {   // obstaculo alto: no avanza -> recupero
                         recuperarAtasco();
                         break;
                     }

                     if (steer < -0.7 || steer > 0.7)
                    {
                            robot.steer(55, FORWARD, steer);
                    }

                    else
                    {
                        robot.steer(velocidadAjustada, FORWARD, steer);
                    }

                    // PENDIENTE: si el pitch esta inclinado, piso las traseras a full para
                    // que agarren y no resbale (fr/br usan dir invertida, igual que en steer).
                    if (pitch > PITCH_RAMPA)
                    {
                        bl.setSpeed(FORWARD,  POTENCIA_TRASERAS);   // trasera izquierda
                        br.setSpeed(!FORWARD, POTENCIA_TRASERAS);   // trasera derecha
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
                    telemGreenResultado(3, green_state);   // TELEMETRIA: giro o matado por re-chequeo
                    if (green_state == 3)
                    {
                        runAngle(30, FORWARD, 180);
                        runTime(30, FORWARD, 0, 500);
                    }
                    action = 7;
                    break;

                }

            }
        }
        while (rutina == "rescate" && digitalRead(32) == 0)
        {
            enviarTelemetria();   // TELEMETRIA (rescate)
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
                runDistance(30,FORWARD,9);
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
                claw.sortCenter();
                nonBlockingDelay(1000);
                claw.sortRight();
                nonBlockingDelay(1000);
                runTime(70,FORWARD,0,200);
                runTime(70,BACKWARD,0,200);
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
                runDistance(20,FORWARD,8);
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
                claw.sortCenter();
                nonBlockingDelay(1000);
                claw.sortLeft();
                nonBlockingDelay(1000);
                runTime(70,FORWARD,0,200);
                runTime(70,BACKWARD,0,200);
                ball_counter++;
            }
            if (ball_counter>=  2 && depositando==false)
            {
                claw.sortCenter();
                digitalWrite(RELAY, HIGH);
                Serial5.write(248);
                depositando=true;
                serialEvent5();
                robot.steer(speed, FORWARD, steer);  
                veces_deposit=2;
            }
            // === CHALLENGE D2.3: invertir zonas si es impar (necesita CONTAR_VERDES) ===
            int gs_dep = INVERTIR_DEPOSITO ? trianguloEfectivo(green_state, verdesImpar()) : green_state;
            if(gs_dep == 9)//verde
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    while(digitalRead(32) == 0){
                        robot.steer(20,BACKWARD,0);
                        serialEvent5();
                        if(digitalRead(FCL)==1 && digitalRead(FCR)==1){
                            break;
                        }
                    }
                    claw.depositRight();
                    nonBlockingDelay(2000);
                    runTime(80,FORWARD,0,100);
                    
                    runTime(80,BACKWARD,0,250);
                    runTime(80,FORWARD,0,100);
                    
                    runTime(80,BACKWARD,0,250);
                    runTime(0,FORWARD,0,500);
                    claw.depositCenter();
                    runTime(0,FORWARD,0,500);
                    runDistance(30,FORWARD,4+60);
                    veces_deposit++;
                }
            if (gs_dep == 8)//rojo
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    while(digitalRead(32) == 0){
                        robot.steer(20,BACKWARD,0);
                        serialEvent5();
                        if(digitalRead(FCL)==1 && digitalRead(FCR)==1){
                            break;
                        }
                    }
                    claw.depositLeft();
                    nonBlockingDelay(2000);
                    runTime(80,FORWARD,0,100);
                    runTime(80,BACKWARD,0,250);
                    runTime(0,FORWARD,0,500);
                    runTime(80,FORWARD,0,100);
                    
                    runTime(80,BACKWARD,0,250);
                    claw.depositCenter();
                    runAngle(20,FORWARD,45);
                    runTime(30,FORWARD,0,500);
                    runAngle(20,FORWARD,-45);

                    veces_deposit++;
                    green_state=0;

                }
            if (veces_deposit >= 2)
            {
                green_state = 0;
                if (!evacuacion_iniciada) {
                    Serial5.write(247);
                    evacuacion_iniciada = true;
                    evacuacion_straight = false;
                }
                rutina = "evacuacion";
                break;
            } // cierra if(veces_deposit >= 2)

        } // end while (rutina == "rescate" && digitalRead(32) == 0)
            /*if(green_state == 10)
                {
                    estado == "salida"
                    runTime(0,BACKWARD,0,3000);

                }*/
           
        // end while (rutina == "rescate" && digitalRead(32) == 0)
        while (rutina == "evacuacion" && digitalRead(32) == 0)
        {
            enviarTelemetria();   // TELEMETRIA (evacuacion)
            if (!evacuacion_straight)
            {
                green_state = 0;

                leer_ultrasonidos();

                if (front_distance != 0 && front_distance < 120) {
                    runAngle(30, FORWARD, 180);
                    while (rutina == "evacuacion" && digitalRead(32) == 0) {
                        robot.steer(30, BACKWARD, 0);
                        serialEvent5();
                        if (digitalRead(FCL) == 1 && digitalRead(FCR) == 1)
                            break;
                    }
                    runAngle(30, FORWARD, -90);

                }
                else
                {
                    unsigned long alignStart = millis();
                    while (rutina == "evacuacion" && digitalRead(32) == 0) {
                        robot.steer(30, FORWARD, 0);
                        procesarColorEvacuacion();
                        serialEvent5();
                    }
                }
                evacuacion_straight = true;
            }
            leer_ultrasonidos();
                while (rutina == "evacuacion" && digitalRead(32) == 0) {
                    robot.steer(30, FORWARD, 0);
                    procesarColorEvacuacion();
                    if (rutina != "evacuacion") break;  
                    serialEvent5();
                    leer_ultrasonidos();
 
                    // PRIORIDAD 1: esquina de deposito = camara ve triangulo (green_state
                    // 8/9) Y el ultrasonido confirma cercania (<=31). Maniobra completa.
                    if ((green_state == 8 || green_state == 9) && front_distance != 0 && front_distance <= 31)
                    {
                        Serial.print("[EVAC] P1 ESQUINA gs="); Serial.print(green_state);
                        Serial.print(" front="); Serial.println(front_distance);
                        maniobraEsquive();
                        green_state = 0;   // evita re-disparo inmediato con valor stale de camara
                        break;
                    }

                    // PRIORIDAD 2: pared frontal lisa = solo ultrasonido (<=18). Giro 90 y sigue.
                    if (front_distance != 0 && front_distance <= 14)
                    {
                        Serial.print("[EVAC] P2 PARED front="); Serial.println(front_distance);
                        runAngle(30, FORWARD, 90);
                        continue;
                    }
                                                            // PRIORIDAD 3: lado izquierdo abierto -> girar a buscar pared.
                    if (left_distance > 40 || left_distance == 0)
                    {
                        Serial.print("[EVAC] P3 BUSCAR left="); Serial.print(left_distance);
                        Serial.print(" front="); Serial.println(front_distance);
                        runDistance(30, FORWARD, 8);
                        runAngle(30, FORWARD, -90);
                        while (rutina == "evacuacion" && digitalRead(32) == 0)
                        {
                            robot.steer(30, FORWARD, 0);
                            procesarColorEvacuacion();
                            serialEvent5();
                            leer_ultrasonidos();
                            if (debeEsquivar())   // corto la busqueda al toparme con esquina o pared
                                break;
                        }
                    }


                }
            // cierra if(left_distance > right_distance)

        }
    } // end else (principal del loop)
} // end loop()