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
#include <telemetria.h>

// ============================================================================
// RescueBot IITA Salta - firmware de competencia del Teensy 4.1 (RCJ Rescue Line 2026). Se flashea
// con `pio run --target upload` (entorno por defecto `competencia`).
//
//   ------------------------------------------------------------------------
//   MAPA DEL ARCHIVO  (en este orden)
//
//     1. PANEL DE CONFIGURACION ....... aca abajo. TODO lo que se toca.
//     2. Estado de la recuperacion de linea y del GAP
//     3. Objetos de hardware: servos, garra, IMU, motores, DriveBase
//     4. Estado global del robot y protocolo con la Raspberry
//     5. Sensores: ultrasonidos, ToF, color (APDS9960)
//     6. Serial con la Raspberry (serialEvent5)
//     7. Primitivas de movimiento: runTime / runAngle / runDistance
//     8. Evacuacion: colores, esquive, finales de carrera
//     9. Anti-atasco (loma de burro) y traccion en rampa
//    10. Telemetria JSON hacia la ESP32
//    11. setup()
//    12. loop()  ->  idle / arranque / lazo de linea / rescate / evacuacion
//
// El entorno `competencia` compila MODO_DIAGNOSTICO=1 (CSV de 200 Hz por USB) y TELEMETRIA=0. El
// movimiento se tuneó con esa carga (~10 % del lazo): cambiarla cambia el comportamiento y obliga a
// volver a probar en pista. La GUI por WiFi está en el entorno `telemetria`.
//
// La Pi manda por Serial5 velocidad, ángulo, código de tarea (green_state) y plateado. La Teensy
// traduce el ángulo a consignas de rueda y ejecuta las maniobras que pide el código de tarea.
//
// Archivos hermanos: lib/drivebase (steer y PID por rueda), lib/claw (garra), src/diagnostico.h
// (registrador CSV; entra en `competencia`), platformio.ini (entornos).
//
// ============================================================================


// ############################################################################
// 1. PANEL DE CONFIGURACION. Cada constante va detrás de #ifndef y se puede pisar con -D desde
// platformio.ini.
// ############################################################################

// ----------------------------------------------------------------------------
// 1.1 SEGUIMIENTO DE LINEA (case 7):
//   angle 0..180 -> steer = (angle-90)/90 -> steerCmd = constrain(steer*LINE_STEER_GAIN, -1, 1)
//   -> absSteer = |steerCmd| -> rot = absSteer^LINE_ROT_EXP
//   Si absSteer >= LINE_FRENO_STEER: steerFrenoDelantero(LINE_FRENO_VEL, ±rot);
//   si no: steer(vel*LINE_RECTA_FACTOR, ±rot), vel = rampa cuadrática base -> LINE_PIVOT_SPEED.
// Radio R = b_eff*(1-rot)/(2*rot), b_eff = 20,9 cm: la velocidad no cierra la curva, solo `rot`.
// Medido: R_real ≈ 1,15 x R_pedido.
// ----------------------------------------------------------------------------

// Ganancia del ángulo antes de calcular rot. 1.0 = sin cambio (con 1.8 empeoró el cabeceo
// y satura antes).
#ifndef LINE_STEER_GAIN
#define LINE_STEER_GAIN 1.0
#endif

// rot = absSteer^LINE_ROT_EXP. Es la palanca del radio: más chico = más agresivo; 1.0
// = rampa lineal.
#ifndef LINE_ROT_EXP
#define LINE_ROT_EXP 0.85
#endif

// 1.01 = pivote con histéresis APAGADO (absSteer nunca pasa de 1.0). Está apagado a propósito: con
// el pivote, el robot pasaba el 29,7 % del tiempo girando sin avanzar (7,8 % sin él). Para
// prenderlo: 0.60.
#ifndef LINE_PIVOTE_ENTRA
#define LINE_PIVOTE_ENTRA 1.01
#endif

// Umbral de salida del pivote (solo si LINE_PIVOTE_ENTRA <= 1.0). La histéresis evita
// picotear el giro.
#ifndef LINE_PIVOTE_SALE
#define LINE_PIVOTE_SALE 0.15
#endif

// Tiempo que debe sostenerse la alineación para soltar el pivote. Las rachas alineadas duran
// 50-75 ms: con >= 300 ms solo sale por LINE_PIVOTE_MAX_MS.
#ifndef LINE_PIVOTE_CONFIRMA_MS
#define LINE_PIVOTE_CONFIRMA_MS 0UL
#endif

// Tope del pivote. A ~39 grados/s, 90 grados cuestan ~2,3 s: no hay margen.
#ifndef LINE_PIVOTE_MAX_MS
#define LINE_PIVOTE_MAX_MS 2500UL
#endif

// Techo (rpm) de la rampa cuadrática de velocidad, solo para absSteer < LINE_FRENO_STEER. Con
// LINE_FRENO_STEER=0.70 la rampa llega a k^2 ≈ 0,58 (~45 rpm): este valor no se alcanza. La curva
// cerrada usa LINE_FRENO_VEL.
#ifndef LINE_PIVOT_SPEED
#define LINE_PIVOT_SPEED 50
#endif

// Factor de velocidad fuera de la curva cerrada (1.0 = sin cambio). No cierra el radio: da tiempo
// de reacción (más frames de cámara por cm).
#ifndef LINE_RECTA_FACTOR
#define LINE_RECTA_FACTOR 0.8
#endif

// ----------------------------------------------------------------------------
// 1.2 CURVA CERRADA. Con |steer| >= LINE_FRENO_STEER la velocidad pasa a LINE_FRENO_VEL fija
// (escalón 36 -> 55 rpm; rot sigue continuo). NO frena ninguna rueda: LINE_FRENO_FACTOR =
// kFrenoComoSteer reparte igual que steer(). Para frenar de verdad: -D LINE_FRENO_FACTOR=-1.0
// (delantera interna en reversa; el que más gasta la silicona).
// ----------------------------------------------------------------------------

// OJO: este flag no gatea nada (la rama del case 7 no lo mira); solo se imprime en la
// cabecera del CSV.
#ifndef LINE_FRENO_DELANTERO
#define LINE_FRENO_DELANTERO 1
#endif

// Desde que |steer| se entra a la curva cerrada.
#ifndef LINE_FRENO_STEER
#define LINE_FRENO_STEER 0.70
#endif

// Velocidad fija (rpm) dentro de la curva cerrada.
#ifndef LINE_FRENO_VEL
#define LINE_FRENO_VEL 55
#endif

// Consigna de la rueda DELANTERA INTERNA, como fraccion de LINE_FRENO_VEL:
//     DriveBase::kFrenoComoSteer   igual que steer()  <- CONTROL NEGATIVO, el de hoy
//                           0.0    quieta
//                          -0.5    reversa a media velocidad
//                          -1.0    reversa a velocidad completa
#ifndef LINE_FRENO_FACTOR
#define LINE_FRENO_FACTOR DriveBase::kFrenoComoSteer
#endif

// Multiplicador de `rot` SOLO dentro de la curva cerrada. 1.0 = sin cambio.
// Va aparte de LINE_ROT_EXP a proposito: el exponente toca TODO el rango
// -incluida la recta, donde bajarlo trajo cabeceo- y esto toca solo la curva.
#ifndef LINE_FRENO_ROT_MULT
#define LINE_FRENO_ROT_MULT 1.0
#endif

// ----------------------------------------------------------------------------
//  1.3  QUIEN DECIDE EL PLATEADO (entrada a la zona de evacuacion)
// ----------------------------------------------------------------------------

// 1 = el plateado lo decide el APDS9960 (4 ventanas filtradas antes del ACK 0xF1); el byte
// silver_line de la Pi no tiene autoridad. 0 = nunca entra a evacuación (interruptor de pánico).
#define PLATEADO_TEENSY     1

// ----------------------------------------------------------------------------
// 1.4 SENSORES: costo de las lecturas bloqueantes dentro del lazo de línea.
// ----------------------------------------------------------------------------

// ping_cm() bloquea hasta el timeout si no hay eco. El techo va explícito en cada llamada porque
// set_max_distance() persiste: 30 cm en línea (timeout ~1,7 ms), 150 cm en evacuación.
static const unsigned int PING_LINEA_CM = 30;    // techo del lazo de línea (que pregunta < 2)
static const unsigned int PING_LARGO_CM = 150;   // evacuacion pregunta < 120

// Período mínimo entre pings del frontal dentro del lazo de línea.
static const unsigned long PING_FRONTAL_PERIODO_MS = 40;

// Presupuesto de medición de los VL53L0X (mínimo 20 ms). Hoy nadie lee los ToF: la telemetría
// publica 0 mm = no se preguntó.
static const uint32_t TOF_PRESUPUESTO_US = 20000;

// ----------------------------------------------------------------------------
// 1.5 WATCHDOG: sin tramas de la Pi, la Teensy seguiría con el último steer; el lazo
// de línea frena.
// ----------------------------------------------------------------------------

// Sin trama valida por mas de esto, el comando se considera rancio.
static const unsigned long WATCHDOG_MS = 400;

// Además tiene que sostenerse este tiempo (medido por tiempo, no por vueltas del lazo): al volver
// de una maniobra bloqueante el comando llega legítimamente viejo.
static const unsigned long WATCHDOG_CONFIRMA_MS = 300;

// ----------------------------------------------------------------------------
// 1.6 Las primitivas (runTime/runAngle/runDistance*) no parsean Serial5: drenan y tiran un byte por
// vuelta, así una maniobra empezada se termina. Al volver, la primera trama parseada puede ser
// vieja y el watchdog la ve fresca.
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
//  1.7  INTERRUPTORES DE COMPILACION
// ----------------------------------------------------------------------------

// MODO_DIAGNOSTICO=1 (lo define `competencia`): el USB lleva solo el CSV de diagnostico.h, por eso
// DBG_* no imprime. Nunca usar Serial.print suelto.
#ifndef MODO_DIAGNOSTICO
#define MODO_DIAGNOSTICO 0
#endif

#if MODO_DIAGNOSTICO
  #define DBG_PRINT(...)   do { } while (0)
  #define DBG_PRINTLN(...) do { } while (0)
#else
  #define DBG_PRINT(...)   Serial.print(__VA_ARGS__)
  #define DBG_PRINTLN(...) Serial.println(__VA_ARGS__)
#endif

// ----------------------------------------------------------------------------
// 1.8 LINEA PERDIDA (GS=4). Con GS=4, el byte angle trae el último rumbo de CAMINO+MONO (derecha
// negativa). Un episodio:
//   1) retrocede una vez (ACK 0xEF);
//   2) espera quieto un rumbo fresco;
//   3) pivota una vez hacia ese lado (ACK 0xED);
//   4) si sigue GS=4, espera.
// Sin los 5 archivos de CAMINO+MONO en la Pi se queda esperando en silencio.
// ----------------------------------------------------------------------------
#define LINEA_PERDIDA_GS          4       // el codigo que manda la Raspberry
#define RECUP_VEL                25       // rpm, despacio: se esta yendo a ciegas
#define RECUP_MS                400       // retroceso: gana campo visual antes de decidir el lado
#define RECUP_STEER_MIN          0.10     // 9 grados de CAMINO: debajo no se elige lado
#define RECUP_GIRO_VEL           35       // velocidad del pivote de busqueda
#define RECUP_PIVOTE_ROT         1.00     // giro sobre el eje: no consume zona mientras se orienta
#define RECUP_GIRO_BASE_GRADOS   28.0f    // grados base del pivote de recuperación
#define RECUP_GIRO_CAMINO_K      0.22f    // grados extra por grado de rumbo CAMINO
#define RECUP_GIRO_DER_EXTRA_GRADOS 0.0f  // extra al pivotar a la DERECHA (signo < 0); 0 = simétrico
#define RECUP_GIRO_MIN_GRADOS    35.0f    // nunca corregir menos que esto
#define RECUP_GIRO_MAX_GRADOS    58.0f    // evita los pivotes exagerados de 70-90 deg
#define RECUP_GIRO_MAX_MS        1600UL   // failsafe del pivote dirigido
#define RECUP_REANALISIS_MS      120UL    // quieto despues de retroceder, para que CAMINO mire
#define RECUP_REANALISIS_EDAD_MS 180UL    // solo se acepta rumbo recibido DESPUES del retroceso
#define RECUP_REARME_TEENSY_MS   300UL    // GS=0 continuo exigido antes de permitir otro episodio
#define RECUP_WAIT_ACTION        21       // accion interna: GS4 no habilitado -> quieto

// ----------------------------------------------------------------------------
//  1.9  GAP (linea cortada) Y FAIL-SAFE
//  Pi -> Teensy: GS 18 = avanzar recto buscando el otro lado del gap
//                GS 19 = fail-safe, parar
//  Teensy -> Pi: los cuatro ACK de abajo
// ----------------------------------------------------------------------------
#define GAP_BUSQUEDA_GS          18
#define PERDIDA_FAILSAFE_GS      19
#define GAP_ACTION               22       // accion interna del switch
#define PERDIDA_FAILSAFE_ACTION  23       // accion interna del switch
#define GAP_VEL                  25
#define GAP_MAX_CM               50       // el reglamento da gaps de hasta 20 cm
#define GAP_MAX_MS               8000UL
#define GAP_ORIGIN_MARGIN_CM     1
#define TEENSY_ACK_GAP_ORIGIN    238      // 0xEE  ya paso el punto donde perdio la linea
#define TEENSY_ACK_RETRO_DONE    239      // 0xEF  termino de retroceder
#define TEENSY_ACK_GAP_TIMEOUT   240      // 0xF0  se acabo el margen del gap
#define TEENSY_ACK_RESCATE_APDS  241      // 0xF1  el APDS confirmo plateado
#define TEENSY_ACK_PIVOTE_DONE   237      // 0xED  termino el pivote de recuperacion (COMPLETAR_GIRO en la Pi)
// Estado de pendiente para que la Raspberry ajuste SOLO el ROI del control de linea.
#define TEENSY_RAMPA_SUBE        242      // 0xF2  subiendo: Pi usa corte superior ROI=100
#define TEENSY_RAMPA_BAJA        243      // 0xF3  bajando: Pi vuelve al ROI normal
#define TEENSY_RAMPA_LLANO       244      // 0xF4  llano: Pi usa ROI normal

// Antes de entrar a rescate, el APDS mira SOLO la ultima recuperacion FISICA.
// Si fue lateral reciente: deshace LA MITAD del giro real, en sentido contrario.
// Si fue RECTA/GAP, no hubo recovery reciente, o la memoria vencio: NO gira.
#define SILVER_REC_MEMORY_MS       5000UL
#define SILVER_REC_UNDO_FACTOR     0.50f
#define SILVER_REC_UNDO_VEL        25
#define SILVER_REC_UNDO_MAX_MS     1400UL

// SALIDA DE EVACUACION POR EL NEGRO: al ver la cinta negra gira NEGRO_SALIDA_GIRO_GRADOS
// hacia el lado contrario a la última pared vista por los ultrasonidos (< _PARED_MAX_CM,
// memoria de _MEMORIA_MS). En la salida la pared se abre, así que la lectura instantánea no
// sirve. 0 = sale recto.
#define NEGRO_SALIDA_GIRO          1
#define NEGRO_SALIDA_GIRO_GRADOS   30.0
#define NEGRO_SALIDA_PARED_MAX_CM  60
#define NEGRO_SALIDA_MEMORIA_MS    5000UL
#define NEGRO_SALIDA_MUESTREO_MS   100UL     // en el lazo recto inicial, que no lee ultrasonidos

// Memoria de pared en evacuacion: -1 izquierda, +1 derecha, 0 nunca vio pared.
static int g_evac_pared_lado = 0;
static unsigned long g_evac_pared_ms = 0;

// ############################################################################
// #              2.  ESTADO DE LA RECUPERACION Y DEL GAP                     #
// ############################################################################

static int g_recup_signo = 0;             // -1/+1, CONGELADO al perder la linea
// Rumbo CAMINO (-1..+1) recibido junto con GS=4 y cuándo llegó: es la única fuente del lado del
// giro de recuperación.
static double g_recup_rumbo_camino_rx = 0.0;
static unsigned long g_recup_rumbo_camino_rx_ms = 0;

// Anti-retrigger del lado Teensy (el filtro fuerte está en la Pi): exige GS=0 sostenido antes
// de otro episodio.
static bool g_recup_episodio_activo = false;
static bool g_recup_habilitada = false;
static unsigned long g_recup_gs0_desde = 0;
// Fases fisicas del MISMO episodio: evitan repetir el retroceso o el giro
// mientras la Raspberry siga mandando GS4.
static bool g_recup_retroceso_hecho = false;
static bool g_recup_giro_hecho = false;

static bool g_gap_activo = false;
static bool g_gap_origen_enviado = false;
static bool g_gap_timeout_enviado = false;
static long g_gap_retro_pulsos = 0;
static long g_gap_inicio_fl = 0;
static long g_gap_inicio_fr = 0;
static unsigned long g_gap_inicio_ms = 0;

// Memoria PERSISTENTE para la entrada al plateado.
// No se borra cuando GS0 cierra el episodio de recovery: justamente debe
// sobrevivir hasta que el APDS encuentre el plateado unos instantes despues.
enum SilverRecKind : int8_t {
    SILVER_REC_NONE = 0,
    SILVER_REC_RECTA = 1,
    SILVER_REC_LATERAL = 2
};
static SilverRecKind g_silver_rec_kind = SILVER_REC_NONE;
static int g_silver_rec_pivot_sign = 0;       // signo FISICO usado por robot.steer()
static float g_silver_rec_actual_deg = 0.0f;  // yaw realmente recorrido, no objetivo teorico
static unsigned long g_silver_rec_ms = 0;

static long gapPulsosDesdeInicio();
static void resetGapState();
// TELEMETRIA: 1 = JSON por Serial8 a la ESP32-MINI (entorno `telemetria`); en `competencia` vale 0.
// TELEMETRIA_DEBUG_USB: 1 = imprime por USB cuántos frames salieron.
#ifndef TELEMETRIA
#define TELEMETRIA          1
#endif
#define TELEMETRIA_DEBUG_USB 0

// Telemetría: una línea JSON a 10 Hz por Serial8 (RX34/TX35) hacia la ESP32-MINI. Si no hay lugar
// en TX descarta el frame: nunca frena el control.

// Globales de diagnóstico fuera de todo #if: las leen la telemetría JSON y el CSV de diagnostico.h.
// Rama del último movimiento (solo telemetría/CSV): -1 primitiva de maniobra, 0 recto, 1 curva,
// 2 curva dura, 3 pivote (no aparece con LINE_FRENO_STEER=0.70), 7 curva cerrada, 9 atasco,
// 13 pivote de recuperación, 14 retroceso de recuperación, 15 empuje del palillo (rampa.h).
int g_line_branch = 0;

// millis() de la última trama completa de la Pi (0 = nunca). La usa el watchdog.
unsigned long g_last_rx_ms = 0;
unsigned long g_wd_stale_ms = 0;  // desde cuando la trama esta vieja (0 = no)
unsigned long g_wd_ref_ms = 0;    // referencia si NUNCA llego una trama
bool g_wd_activo  = false;  // el watchdog esta frenando

// Último ángulo recibido de la Pi (-1..+1). Solo lo escribe serialEvent5; `steer` también lo
// pisa el firmware.
double g_rx_steer = 0;

// Período del loop() y su pico desde el último frame de telemetría (ms).
unsigned long g_loop_dt = 0, g_loop_dt_max = 0;

#if TELEMETRIA
// Baud Teensy->ESP32. TIENE que ser igual a UART_BAUD de software/esp32/telemetria/src/main.cpp
// (flashear las dos placas). 230400 porque el frame (~1000 bytes) a 115200 ocupaba el 87 % del
// enlace y se descartaban frames.
#define TLM_BAUD 230400

Telemetria telemetria(Serial8, 100);   // 100 ms => 10 Hz
void enviarTelemetria();

// Contadores de verdes por tipo (1 izq, 2 der, 3 doble): recibidos (por flanco), confirmados y
// descartados en el re-chequeo. Solo telemetría; no deciden nada.


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

// Nombre de la primitiva en curso (campo `prim`). RAII porque las primitivas se anidan:
// cada una guarda y restaura el nombre anterior. const char* a un literal, nunca String
// (sin heap en el lazo).
const char *g_prim = "";

struct PrimScope
{
    const char *prev;
    explicit PrimScope(const char *n) : prev(g_prim) { g_prim = n; }
    ~PrimScope() { g_prim = prev; }
};
#define PRIM(nombre) PrimScope _prim_(nombre)

// Cabecera `hdr`: git_commit.py inyecta TLM_COMMIT como literal; el #ifndef cubre compilar
// sin ese script.
#ifndef TLM_COMMIT
#define TLM_COMMIT "nodef"
#endif
static const char HDR_JSON[] = "\"hdr\":{\"commit\":\"" TLM_COMMIT "\",\"tlm\":2},";
#else
inline void enviarTelemetria() {}
inline void telemGreenRx(int) {}
inline void telemGreenResultado(int, int) {}
// Con TELEMETRIA en 0 el marcador desaparece en el preprocesador: no queda ni
// la variable ni el objeto. No depende de que el optimizador lo saque.
#define PRIM(nombre) ((void)0)
#endif


// ############################################################################
// 3. HARDWARE: servos, garra, BNO055, 4 motores FIT0441 con encoder y DriveBase (todo el
// movimiento pasa por `robot`). Tracción: 4 ruedas fijas de silicona; el centro de giro no se
// puede correr por consigna.
// ############################################################################

DFServo sort(23, 540, 2390, 274);
DFServo left(14, 540, 2390, 274);
DFServo right(15, 540, 2390, 274);
DFServo lift(22, 540, 2390, 274);
DFServo deposit(12, 540, 2390, 274);
Claw claw(&lift, &left, &right, &sort, &deposit);

// Pines: BUZZER 31, LED_ROJO 30, SWITCH 32 (1 = apagado), RELAY 0.
// FCL/FCR: finales de carrera izq/der. FORWARD/BACKWARD = 0/1.
#define FORWARD 0
#define BACKWARD 1
#define RELAY 0
#define BUZZER 31
#define LED_ROJO 30
#define SWITCH 32
#define FCL 40
#define FCR 41
bool rescateAvisado = false;
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
Moto bl(29, 28, 27, "BL"); // pwm, dir, enc
Moto fl(7, 6, 5, "FL");
Moto br(36, 37, 38, "BR");
Moto fr(4, 3, 2, "FR");
DriveBase robot(&fl, &fr, &bl, &br);

static long gapPulsosDesdeInicio()
{
    const long dfl = labs((long)fl.pulseCount - g_gap_inicio_fl);
    const long dfr = labs((long)fr.pulseCount - g_gap_inicio_fr);
    return (dfl + dfr) / 2;
}

static void resetGapState()
{
    g_gap_activo = false;
    g_gap_origen_enviado = false;
    g_gap_timeout_enviado = false;
    g_gap_inicio_fl = (long)fl.pulseCount;
    g_gap_inicio_fr = (long)fr.pulseCount;
    g_gap_inicio_ms = 0;
}
// ############################################################################
// 4. ESTADO GLOBAL Y PROTOCOLO CON LA RASPBERRY.
// Pi -> Teensy (Serial5, 115200): [255,speed][254,angle][253,green_state][252,silver_line].
//   252..255 son sync y no pueden ser dato.
//   speed 0..100: solo la usa la rutina rescate.
//   angle 0..180 -> steer -1..+1.
//   silver_line: sin autoridad (el plateado lo decide el APDS).
//   green_state: 0 línea, 1 verde izq, 2 verde der, 3 doble verde, 4 línea perdida,
//     6/7 pelotas (verificar el mapeo con la Pi), 8/9 triángulo rojo/verde,
//     14 intersección (15/16/17 respuesta), 18 gap, 19 fail-safe.
// Teensy -> Pi: 0xFA boot (setup), 0xF9 listo / vuelta a línea, 0xFF switch apagado,
//   0xF7 evacuación, 0xF8 depositar, ACK 0xED..0xF1.
// ############################################################################

String color_detected;

int serial5state = 0;  // parser: 0 speed, 1 angle, 2 green_state, 3 silver
double speed;          // speed (0 to 100)
double steer;          // -1..+1; también lo pisa el firmware (ver g_rx_steer)
int green_state = 0;   // código de tarea de la Pi (ver tabla)
int silver_line = 0;   // flag de plateado de la Pi: sin autoridad
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
int action =7;            // case del switch del lazo de línea (7 = seguir línea)
bool taskDone = false;
bool startUp = false;
int RanNumber;
String rutina = "linea";
String lado_plateado="";
VL53L0X left_tof;
VL53L0X right_tof;
int distance_left_tof;
int distance_right_tof;
float angulo_rescate = 0;
float centrar = 0;
String pared="";
bool depositando=false;
int veces_deposit=2;
int ball_counter=1;
bool evacuacion_iniciada=false;
bool evacuacion_straight=false;
bool silver_latch=false;  // true mientras seguimos "sobre" un plateado ya atendido (evita repetir la accion)

bool color_sensor_ok = true;
bool rescateUpdateInProgress = false;

void actualizarRescate();
void serialEvent5();
void runTime(int speed, int dir, double steer, unsigned long long time);
void runAngle(int speed, int dir, double angle);
void runDistance(int speed, int dir, int Distance);


// Velocidad base de línea (rpm). OJO: hoy su valor no tiene efecto: ajustarVelocidadPorPendiente()
// devuelve 45 con pitch > 3,9 y 40 en el resto. El byte speed de la Pi no se usa en línea.
static const int VELOCIDAD_BASE_LINEA = 45;

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
    DBG_PRINT("No BNO055 detected ... Check your wiring or I2C ADDR!");
    fatalSensorInitLoop();   // no vuelve nunca: parpadeo + chicharra para siempre
}

// Sensor OPCIONAL que no arranco (hoy: el APDS9960). NO es fatal -el robot puede
// seguir la linea sin color- pero tiene que NOTARSE antes de largar la corrida.
void notifyOptionalSensorWarning()
{
    blinkVisibleError(120, 120, 3);
}


// Registrador CSV de 200 Hz (activo en `competencia`). Va acá y no arriba porque lee globales
// declaradas más arriba.
#include "rampa.h"   // detector de rampa y atasco en el palillo: lo alimenta diagnostico.h
#include "diagnostico.h"

void serviceMotionBackgroundTasks()
{
    DIAG_TICK();   // muestreo de alta frecuencia DURANTE las maniobras bloqueantes
    // Telemetría y garra siguen corriendo durante las maniobras bloqueantes (rate-limited,
    // no bloqueante).
    enviarTelemetria();

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

// Maquina de rescate no bloqueante: HOY NUNCA SALE de RESCATE_IDLE (nadie la inicia). El rescate
// real es el codigo en linea de las rutinas rescate/evacuacion.
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
RescateState rescateState = RESCATE_IDLE;
unsigned long rescateLastTime = 0;
const unsigned long RESCATE_STEP_DELAY = 1000;  // ms



void actualizarRescate() {
    if (rescateUpdateInProgress) {
        return;
    }

    rescateUpdateInProgress = true;
    unsigned long now = millis();
    switch (rescateState) {
        case RESCATE_IDLE:
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
                delay(100);
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
            if (now - rescateLastTime >= 200) {
                runTime(30, FORWARD, 0, 200);
                runTime(30, BACKWARD, 0, 200);
                ball_counter++;
                rescateState = RESCATE_IDLE;
            }
            break;
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
#define SONAR_NUM 3
#define MAX_DISTANCE 150 // cm; techo inicial del objeto (cada ping_cm(max) lo cambia y persiste)

NewPing sonar[SONAR_NUM] = {
    // (trigger, echo): [0] frente 8/9, [1] izquierda 11/10, [2] derecha 39/33
    NewPing(8, 9, MAX_DISTANCE),
    NewPing(11, 10, MAX_DISTANCE),
    NewPing(39, 33, MAX_DISTANCE)};

int front_distance;
int left_distance;
int right_distance;

// ############################################################################
// 5. SENSORES. Ultrasonidos: ping_cm() bloquea hasta el timeout si no hay eco (0 = sin eco); en
// linea solo se usa leer_ultrasonido_frontal() (ver panel 1.4).
// ToF VL53L0X: se inicializan en setup() y nadie los lee.
// APDS9960 (decide plateado y rojo): promedio movil de 3 muestras. get_color_fast() no espera y
// da "Desconocido" si en esa llamada no hubo muestra nueva; get_color_fresh() espera hasta 35 ms
// una muestra nueva.
// ############################################################################

void leer_ultrasonidos()
{
    // Techo largo explicito: el techo de ping_cm(max) persiste en el objeto y evacuacion
    // pregunta < 120 cm.
    const unsigned int largo = PING_LARGO_CM;
    front_distance = sonar[0].ping_cm(largo);
    left_distance = sonar[1].ping_cm(largo);
    right_distance = sonar[2].ping_cm(largo);
}

// Recuerda el ultimo lado con pared a <= NEGRO_SALIDA_PARED_MAX_CM (-1 izq, +1 der). No se borra al
// perder la pared: accionNegro() gira hacia el lado contrario.
void memoriaParedEvacuacion()
{
    const bool izqOk = (left_distance  > 0 && left_distance  <= NEGRO_SALIDA_PARED_MAX_CM);
    const bool derOk = (right_distance > 0 && right_distance <= NEGRO_SALIDA_PARED_MAX_CM);
    if (izqOk && (!derOk || left_distance < right_distance))
    {
        g_evac_pared_lado = -1;
        g_evac_pared_ms = millis();
    }
    else if (derOk && (!izqOk || right_distance < left_distance))
    {
        g_evac_pared_lado = +1;
        g_evac_pared_ms = millis();
    }
}

// Version con muestreo propio, para el lazo recto inicial de evacuacion que no
// lee los ultrasonidos por su cuenta. Lee cada NEGRO_SALIDA_MUESTREO_MS.
void memoriaParedEvacuacionPeriodica()
{
    static unsigned long t_ultimo = 0;
    const unsigned long ahora = millis();
    if (t_ultimo != 0 && (ahora - t_ultimo) < NEGRO_SALIDA_MUESTREO_MS)
        return;
    t_ultimo = ahora;
    leer_ultrasonidos();
    memoriaParedEvacuacion();
}

// Solo el frontal: el lazo de linea solo pregunta front_distance < 2; las ramas que usan izq/der
// llaman a leer_ultrasonidos().
void leer_ultrasonido_frontal()
{
    // Techo PING_LINEA_CM y periodo PING_FRONTAL_PERIODO_MS: ver panel 1.4. El techo va explicito
    // porque persiste en el objeto.
    static unsigned long t_ping = 0;
    unsigned long ahora = millis();
    if (t_ping != 0 &&
        (unsigned long)(ahora - t_ping) < PING_FRONTAL_PERIODO_MS)
        return;                       // se conserva la lectura anterior
    t_ping = ahora;
    front_distance = sonar[0].ping_cm(PING_LINEA_CM);
}


void leer_tof()
{
    distance_left_tof = left_tof.readRangeContinuousMillimeters();
    distance_right_tof = right_tof.readRangeContinuousMillimeters();
}

void imprimir_tof()
{
    DBG_PRINT("Distance Left: ");
    DBG_PRINT(distance_left_tof);
    DBG_PRINT("mm");

    if (left_tof.timeoutOccurred())
    {
        DBG_PRINT(" TIMEOUT");
    }

    DBG_PRINT("   Distance Right: ");
    DBG_PRINT(distance_right_tof);
    DBG_PRINT("mm");

    if (right_tof.timeoutOccurred())
    {
        DBG_PRINT(" TIMEOUT");
    }
}
void reset_enconder(){
    bl.resetPulseCount();
    fl.resetPulseCount();
    br.resetPulseCount();
    fr.resetPulseCount();
}
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

// Vacia el filtro: la proxima clasificacion usa solo muestras nuevas (se llama tras maniobras
// en evacuacion).
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
        DBG_PRINT("R: "); DBG_PRINT(r);
        DBG_PRINT(" | B: "); DBG_PRINT(b);
        DBG_PRINT(" | G: "); DBG_PRINT(g);
        DBG_PRINT(" | C: "); DBG_PRINT(c);
        DBG_PRINT(" | R/C: "); DBG_PRINT(ratio_rc, 3);
        DBG_PRINT(" | R/G: "); DBG_PRINT(ratio_rg, 3);
        DBG_PRINT(" | R/B: "); DBG_PRINT(ratio_rb, 3);
        DBG_PRINT(" | B-G: "); DBG_PRINT(diff_bg);
        DBG_PRINT(" | -> ");
    }

    String detected = "Desconocido";

    // Rojo medido con el APDS montado: C 371..817, R/C 0.30..0.50, R/G 1.14..1.98, R/B 0.92..1.80.
    bool esRojo =
        (
            c >= 340 && c <= 900 &&
            ratio_rc >= 0.295f &&
            ratio_rg >= 1.10f &&
            ratio_rb >= 0.90f
        );

    // Plateado medido: R/C 0.247..0.260, R/G 0.64..0.67, R/B 0.63..0.68, |B-G| <= ~17.
    // Rango estrecho a proposito: con R/C >= 0.240 hubo rescates falsos.
    bool esPlateado =
        (
            c >= 1500 &&
            ratio_rc >= 0.245f &&
            ratio_rc <= 0.268f &&
            ratio_rg >= 0.645f &&
            ratio_rg <= 0.700f &&
            ratio_rb >= 0.615f &&
            ratio_rb <= 0.700f &&
            abs(diff_bg) <= 30
        );

    // Blanco medido R/C 0.219..0.235. La banda 0.235..0.245 tambien cae en Blanco (con c >= 430).
    bool esBlanco =
        (
            c >= 430 &&
            ratio_rc >= 0.195f &&
            ratio_rc < 0.245f
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
        DBG_PRINTLN(detected);
        lastPrint = millis();
    }

    return detected;
}
bool update_color_nonblocking(bool force_poll = false)
{
    if (!color_sensor_ok) return false;   // el APDS no arranco: no hay color

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




// ISR de encoder (CHANGE, ver attachInterrupt en setup): bl pin 27, fl 5, br 38, fr 2
void ISR1() { bl.updatePulse(); }
void ISR2() { fl.updatePulse(); }
void ISR3() { br.updatePulse(); }
void ISR4() { fr.updatePulse(); }

bool serialPayloadOutOfRange(const char *field, int value, int maxValue)
{
    if (value >= 0 && value <= maxValue)
    {
        return false;
    }

    DBG_PRINT("[WARN] ");
    DBG_PRINT(field);
    DBG_PRINT(" fuera de rango: ");
    DBG_PRINTLN(value);
    return true;
}

void maybePrintSerialTelemetry()
{
    if (serialTelemetryTimer < 5000) return;

    DBG_PRINT("[TLM] serial_bytes_rx=");
    DBG_PRINT(serial_bytes_rx);
    DBG_PRINT(" serial_frames_rx=");
    DBG_PRINTLN(serial_frames_rx);
    serialTelemetryTimer = 0;
}

// ############################################################################
// 6. SERIAL CON LA RASPBERRY (protocolo en la seccion 4). Parser de 4 estados guiado por los sync
// 255/254/253/252.
// Se llama a mano desde los lazos y ademas el core de Teensy la llama desde yield() cuando hay
// bytes. Si se pierde un sync, el dato siguiente cae en el campo anterior.
// ############################################################################

void serialEvent5()
{
    // Limitacion: g_last_rx_ms se sella al PARSEAR, no cuando la Pi emitio. Bytes que quedaron en
    // el buffer durante una maniobra se ven frescos (medido: atraso p50 1849 ms, max 4677 ms).
    // Ver panel 1.5/1.6.
    while (Serial5.available() > 0)
    {
        int data = Serial5.read();
        serial_bytes_rx++;
         
        if (data == SERIAL_SYNC_SPEED)
            serial5state = 0;
        else if (data == SERIAL_SYNC_STEER)
            serial5state = 1;
        else if (data == SERIAL_SYNC_TASK)
            serial5state = 2;
        else if (data == SERIAL_SYNC_SILVER)
            serial5state = 3;
        else if (serial5state == 0)
        {
            if (serialPayloadOutOfRange("speed", data, SERIAL_MAX_SPEED))
                continue;
            speed = (double)data / 100 * 100;
        }
        else if (serial5state == 1)
        {
            if (serialPayloadOutOfRange("angle", data, SERIAL_MAX_ANGLE))
                continue;
            steer = ((double)data - 90) / 90;
            g_rx_steer = steer;   // ángulo de la Pi sin pisar (registrador y recuperación GS=4)
        }
        else if (serial5state == 2)
        {
            if (serialPayloadOutOfRange("green_state", data, SERIAL_MAX_GREEN_STATE))
                continue;
            green_state = data;
            // angle llega antes que green_state en la trama: con GS=4, g_rx_steer es el rumbo
            // CAMINO congelado por la Pi.
            if (data == LINEA_PERDIDA_GS)
            {
                // angle ~0 en recuperacion = CAMINO sin lectura: no pisa un rumbo valido.
                if (fabs(g_rx_steer) >= RECUP_STEER_MIN)
                {
                    g_recup_rumbo_camino_rx = g_rx_steer;
                    g_recup_rumbo_camino_rx_ms = millis();
                }
            }
            telemGreenRx(data);   // TELEMETRIA: cuenta verdes que llegan de la RPi
        }
        else if (serial5state == 3)
        {
            if (serialPayloadOutOfRange("silver_line", data, SERIAL_MAX_SILVER_LINE))
                continue;
            silver_line = data;
            serial_frames_rx++;
            g_last_rx_ms = millis();   // trama cerrada: refresca el watchdog (no verifica los 4 campos)
        }
    }

    maybePrintSerialTelemetry();
}

// ############################################################################
// 7. PRIMITIVAS DE MOVIMIENTO (bloqueantes): runTime (N ms), runAngle (angulo BNO055, con
// timeout), runDistance (N cm por encoder, con timeout), runDistanceEvacuacion (ademas corta con
// pared a <= 18 cm).
// Todas llaman a serviceMotionBackgroundTasks() en cada vuelta y cortan con el switch (pin 32).
// runTime y runDistance* tiran un byte de Serial5 por vuelta (ver panel 1.6).
// ############################################################################


void runTime(int speed, int dir, double steer, unsigned long long time)
{
    g_line_branch = -1;   // este giro no lo pidio el case 7
    PRIM("runTime");
    unsigned long long startTime = millis();
    while ((millis() - startTime) < time)
    {
        robot.steer(speed, dir, steer);
        serviceMotionBackgroundTasks();
        digitalWrite(13, HIGH);
        // Lee y descarta un byte por vuelta: la maniobra no obedece tramas nuevas (panel 1.6).
        if (Serial5.available() > 0)
        {
            // Serial5.read() va fuera del DBG_PRINT: con MODO_DIAGNOSTICO=1 la macro descarta
            // sus argumentos.
            const int lecturas = Serial5.read();
            DBG_PRINT(lecturas);
            (void)lecturas;
        }

        if (digitalRead(32) == 1)
        { // switch apagado: 0xFF = STOP para la Pi
            Serial5.clear();
            Serial5.write(255);
            break;
        }
    }

    digitalWrite(13, LOW);
}
void runAngle(int speed, int dir, double angle)
{
    g_line_branch = -1;   // este giro no lo pidio el case 7
    PRIM("runAngle");
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
        if ((millis() - startTime) >= timeoutMs)
        {
            DBG_PRINTLN("[WARN] runAngle timeout");
            break;
        }
        if (digitalRead(32) == 1)
        { // switch apagado: 0xFF = STOP para la Pi
            Serial5.clear();
            Serial5.write(255);
            break;
        }
        // Error al objetivo por el camino mas corto, en [-180, 180].
        float error = targetAngle - currentAngle;
        if (error > 180)
            error -= 360;
        if (error < -180)
            error += 360;
        DBG_PRINT("Error actual: ");
        if (fabs(error) <= 1.0)
            break;
        // +-45 y +-90: el sentido sale del signo del error (corrige si se pasa). 180 y cualquier
        // otro angulo: sentido fijo, sin corregir si se pasa. rot +1 = izquierda, -1 = derecha.
        if (angle == 180)
        {
            robot.steer(speed, dir, 1);
        }
        else if (angle == 90 || angle == -270)
        {
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
    PRIM("runDistance");
    runTime(30,BACKWARD,0,20);
    runTime(30,FORWARD,0,20);
    reset_enconder();
    int32_t  encoder = 25*Distance;
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);

    if (dir == FORWARD) {
        while (true) {
            if ((millis() - startTime) >= timeoutMs) break;   // no llego: se corta igual
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;
            if (frCount >= encoder || flCount >= encoder) break;

            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();
            DBG_PRINT(flCount);
            DBG_PRINT(" | ");
            DBG_PRINT(frCount);
            digitalWrite(13, HIGH);
            delay(10);
           
            if (Serial5.available() > 0) {   // drena y tira: ver runTime()
                const int lecturas = Serial5.read();
                DBG_PRINT(lecturas);
                (void)lecturas;
            }
           
            if (digitalRead(32) == 1) { // switch apagado: 0xFF = STOP para la Pi
                Serial5.write(255);
                break;
            }
        }
    }else{
         while (true)
        {
            if ((millis() - startTime) >= timeoutMs) break;
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;

            if (frCount <= -encoder || flCount <= -encoder) break;
            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();
            DBG_PRINT(flCount);
            DBG_PRINT(" | ");
            DBG_PRINT(frCount);
            delay(10);
            if (Serial5.available() > 0) {   // drena y tira: ver runTime()
                const int lecturas = Serial5.read();
                DBG_PRINT(lecturas);
                (void)lecturas;
            }
           
            if (digitalRead(32) == 1) { // switch apagado: 0xFF = STOP para la Pi
                Serial5.write(255);
                break;
            }
        }
         
         
    }

    robot.steer(0, dir, 0);   // se frena SIEMPRE al salir, se haya llegado o no
}


void runDistanceEvacuacion(int speed, int Distance) {
    PRIM("runDistEvac");
    runTime(30, BACKWARD, 0, 20);
    runTime(30, FORWARD, 0, 20);
    reset_enconder();
    int32_t encoder = 25 * Distance;
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);

    while (true) {
        if ((millis() - startTime) >= timeoutMs) break;
        int32_t frCount = fr.pulseCount;
        int32_t flCount = fl.pulseCount;
        if (frCount >= encoder || flCount >= encoder) break;
        front_distance = sonar[0].ping_cm();
        if (front_distance != 0 && front_distance <= 18) break; // pared cerca -> corto el avance
        robot.steer(speed, FORWARD, 0);
        serviceMotionBackgroundTasks();
        delay(10);

        if (Serial5.available() > 0) {   // drena y tira: ver runTime()
            const int lecturas = Serial5.read();
            DBG_PRINT(lecturas);
            (void)lecturas;
        }

        if (digitalRead(32) == 1) { // switch apagado: 0xFF = STOP para la Pi
            Serial5.write(255);
            break;
        }
    }

    robot.steer(0, FORWARD, 0);   // se frena SIEMPRE al salir
}

// Espera BLOQUEANTE que sigue moviendo la garra y parseando Serial5. No llama a DIAG_TICK ni a la
// telemetria, y no mira el switch.
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
#if NEGRO_SALIDA_GIRO
    // Lado de la pared segun la memoria de evacuacion (-1 izq, +1 der, 0 = sin dato o vencida). Ver
    // panel NEGRO_SALIDA_*.
    int ladoPared = 0;
    if (g_evac_pared_lado != 0 &&
        (millis() - g_evac_pared_ms) <= NEGRO_SALIDA_MEMORIA_MS)
        ladoPared = g_evac_pared_lado;
    DBG_PRINT("[EVAC] NEGRO salida: pared memoria=");
    DBG_PRINT(g_evac_pared_lado);
    DBG_PRINT(" edad_ms=");
    DBG_PRINT(g_evac_pared_ms ? (long)(millis() - g_evac_pared_ms) : -1L);
    DBG_PRINT(" -> lado=");
    DBG_PRINTLN(ladoPared);
#endif
    runDistance(30, FORWARD, 5);
#if NEGRO_SALIDA_GIRO
    // Gira hacia el lado contrario a la pared (runAngle: + derecha, - izquierda).
    if (ladoPared < 0)
        runAngle(30, FORWARD,  NEGRO_SALIDA_GIRO_GRADOS);   // pared izq -> derecha
    else if (ladoPared > 0)
        runAngle(30, FORWARD, -NEGRO_SALIDA_GIRO_GRADOS);   // pared der -> izquierda
    robot.steer(0, FORWARD, 0);
#endif
    Serial5.write(249);
    reset_color_history();
    digitalWrite(RELAY, LOW);

    // 1) romper la inercia (jiggle corto, como hace runDistance al arrancar)
    runTime(20, BACKWARD, 0, 300);
    runTime(20, FORWARD, 0, 300);

    // 2) 800 ms quieto parseando serial mientras la Pi vuelve a modo linea, para no moverse con
    // tramas de evacuacion.

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
    runDistance(30, BACKWARD, 10);
    runAngle(30, FORWARD, 90);
    runDistanceEvacuacion(30, 30);   // avanza 30 cm pero corta si hay pared a <=18 cm
    robot.steer(0, FORWARD, 0);
    reset_color_history();  // descarta muestras previas para no re-disparar con color stale
}



// Lecturas nuevas extra para confirmar Negro en evacuacion, ademas de la que lo detecto.
constexpr uint8_t EVAC_COLOR_CONFIRM_SAMPLES = 1;

// true si las proximas N lecturas nuevas del APDS dan 'objetivo'.
bool confirmarColor(const String &objetivo)
{
    for (uint8_t i = 0; i < EVAC_COLOR_CONFIRM_SAMPLES; i++)
    {
        if (get_color_fresh() != objetivo)
            return false;
    }
    return true;
}

// Plateado en evacuacion: 3 lecturas nuevas extra, igual que en linea.
constexpr uint8_t EVAC_PLATEADO_CONFIRM_SAMPLES = 3;
bool confirmarPlateadoEvacuacion()
{
    for (uint8_t i = 0; i < EVAC_PLATEADO_CONFIRM_SAMPLES; i++)
    {
        if (get_color_fresh() != "Plateado")
            return false;
    }
    return true;
}

// Plateado en linea (decide el 0xF1 y la entrada a rescate; la camara no participa): 3 lecturas
// nuevas extra. Son promedios moviles de 3 muestras que se solapan (unas 6 muestras distintas).
constexpr uint8_t LINE_PLATEADO_CONFIRM_SAMPLES = 3;
bool confirmarPlateadoLinea()
{
    for (uint8_t i = 0; i < LINE_PLATEADO_CONFIRM_SAMPLES; i++)
    {
        if (get_color_fresh() != "Plateado")
            return false;
    }
    return true;
}

// Evacuacion: Negro confirmado -> accionNegro(); Plateado confirmado y no atendido ->
// accionPlateado().
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
        accionNegro();
        return true;
    }

    if (color_detected == "Plateado" && !silver_latch && confirmarPlateadoEvacuacion())
    {
        Serial.println("[EVAC] Plateado confirmado -> accionPlateado");
        accionPlateado();
        silver_latch = true;  // ya atendido; no repetir hasta despegarse del plateado
        return true;
    }

    return false;
}

// ############################################################################
// 8. IMU (yaw, pitch y pendiente), entrada al plateado y esquive de evacuacion.
// accionNegro/accionPlateado y la confirmacion de color estan arriba.
// ############################################################################

#define TARGET_DISTANCE 70.0
#define KP_DISTANCE 0.05
#define KP_ANGLE 0.05
#define MAX_STEER 1
#define ANGLE_THRESHOLD 2.0
#define TARGET_ANGLE 0
float pitch=0;
float leer_yaw()
{
    sensors_event_t event;
    bno.getEvent(&event);
    float yaw = event.orientation.x; // orientation.x = yaw (heading), 0..360 grados
    return yaw;
}
float leer_pitch()
{  
    sensors_event_t event;
    bno.getEvent(&event);

    pitch = event.orientation.y; // pitch con este montaje (llano ~+-5, rampa ~23)
    return pitch;
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
// anguloObjetivo - anguloActual, llevado a [-180, 180] grados.
float calcularDiferenciaAngulo(float anguloActual, float anguloObjetivo)
{
    float error = anguloObjetivo - anguloActual;

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


// Antes de entrar a rescate: si la ultima recuperacion fue LATERAL y reciente, deshace
// SILVER_REC_UNDO_FACTOR del yaw que giro de verdad, en sentido contrario.
void corregirEntradaPlateadoDesdeRecovery()
{
    const unsigned long ahora = millis();
    const unsigned long edad = g_silver_rec_ms ? (ahora - g_silver_rec_ms)
                                               : 0xFFFFFFFFUL;

    // Sin recuperacion lateral reciente, o giro < 5 grados: ya venia orientado, no gira.
    if (g_silver_rec_kind != SILVER_REC_LATERAL ||
        g_silver_rec_pivot_sign == 0 ||
        g_silver_rec_actual_deg < 5.0f ||
        edad > SILVER_REC_MEMORY_MS)
    {
        robot.steer(0, FORWARD, 0);
        return;
    }

    // Objetivo = FACTOR x yaw medido de la recuperacion (no el objetivo teorico), tope 30 grados.
    float objetivo = g_silver_rec_actual_deg * SILVER_REC_UNDO_FACTOR;
    objetivo = constrain(objetivo, 0.0f, 30.0f);

    const int signoCorreccion = -g_silver_rec_pivot_sign;
    const float yaw0 = leer_yaw();
    const unsigned long t0 = millis();

    robot.steer(0, FORWARD, 0);
    while (digitalRead(SWITCH) == 0)
    {
        serviceMotionBackgroundTasks();
        if (Serial5.available() > 0)
            serialEvent5();

        const float girado = fabs(calcularDiferenciaAngulo(yaw0, leer_yaw()));
        if (girado >= objetivo)
            break;
        if ((millis() - t0) >= SILVER_REC_UNDO_MAX_MS)
            break;

        robot.steer(SILVER_REC_UNDO_VEL, FORWARD,
                    signoCorreccion > 0 ? RECUP_PIVOTE_ROT : -RECUP_PIVOTE_ROT);
    }

    robot.steer(0, FORWARD, 0);

    // Consumir la memoria: este plateado ya fue corregido.
    g_silver_rec_kind = SILVER_REC_NONE;
    g_silver_rec_pivot_sign = 0;
    g_silver_rec_actual_deg = 0.0f;
    g_silver_rec_ms = 0;
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



bool retrocederHastaFinales(int velocidad);

// Esquina de deposito: la camara ve un triangulo (GS 8 rojo / 9 verde) y el ultrasonido frontal lo
// confirma a <= 31 cm.
bool debeEsquivar()
{
    if ((green_state == 8 || green_state == 9) && front_distance != 0 && front_distance <= 31)
        return true;

    return false;
}

// Esquive de esquina de deposito: retrocede, gira 90, avanza 27 cm, gira 90, retrocede hasta los
// finales de carrera y, si llegan, gira -90.
void maniobraEsquive()
{
    resetear_bno();
    runTime(30, BACKWARD, 0, 300);
    runAngle(30, FORWARD, 90);
    runDistance(30, FORWARD, 27);
    runAngle(30, FORWARD, 90);

    // Si los finales de carrera no confirman (timeout), se corta la maniobra sin el giro final.
    if (!retrocederHastaFinales(20))
        return;

    runAngle(30, FORWARD, -90);
}


// Siempre 0; solo lo publica la telemetria (campo verd).
int  verdes_total = 0;

unsigned long rojo_ignorar_hasta = 0;


// ############################################################################
// #                                                                          #
// #  9.  ANTI-ATASCO (loma de burro) Y TRACCION EN RAMPA                     #
// #                                                                          #
// ############################################################################

// ATASCO (loma de burro): una rueda delantera clavada (~0 pulsos/100 ms) mientras la otra
// patina (~45); en recta las dos dan ~40. Atascado = min(|dFR|,|dFL|) < UMBRAL_RUEDA
// durante STUCK_TIME_MS.
long          stuck_lastFr    = 0;
long          stuck_lastFl    = 0;
unsigned long stuck_since      = 0;
unsigned long stuck_lastSample = 0;
unsigned long atascoArmedSince = 0;    // cuando arranco a correr (startUp) -> para el grace period
const long          UMBRAL_RUEDA    = 15;    // pulsos/STUCK_SAMPLE_MS; por debajo, rueda clavada
const unsigned long STUCK_SAMPLE_MS = 100;   // cada cuanto mido las ruedas
const unsigned long STUCK_TIME_MS   = 3000;  // 3 s con una rueda parada = atascado
const unsigned long ATASCO_GRACE_MS = 8000;  // no disparar los primeros 8 s tras arrancar (ponerlo en pista)

// --- Traccion en pendiente: las cuatro ruedas comparten una base alta, sin perder
//     el reparto izquierda/derecha que pide la Raspberry para seguir la linea. ---
const float  PITCH_RAMPA       = 12.0;  // pitch (grados) desde el cual considero "pendiente" (llano ~±5, rampa ~23)
const double POTENCIA_TRASERAS = 40;   // base de rampa (rpm objetivo, 0-159): 4 ruedas recto; se reparte al doblar
const double RAMPA_EXTERIOR_MAX_RPM = 50;   // correccion suave: evita patinar en la subida
const double RAMPA_GIRO_MUERTO      = 0.75; // solo una curva fuerte vence la subida recta

// --- Estado de rampa Teensy -> Raspberry para ROI dinamico -----------------
// No toca el detector mecanico de rampa ni la traccion. Es un aviso rapido
// exclusivo para vision: filtra cabeceos cortos antes de cambiar el ROI.
const float         ROI_RAMPA_ENTRA_GRADOS = 14.0f;
const float         ROI_RAMPA_SALE_GRADOS  = 8.0f;
const unsigned long ROI_RAMPA_CONFIRMA_MS  = 200UL;
const unsigned long ROI_RAMPA_REENVIO_MS   = 500UL;
const unsigned long BLOQUEO_POST_RAMPA_MS  = 10000UL; // no recuperar durante 10 s al volver de pendiente a llano

static int8_t       g_roi_rampa_estado = 0;       // +1 sube, -1 baja, 0 llano
static int8_t       g_roi_rampa_candidato = 0;
static unsigned long g_roi_rampa_candidato_desde = 0;
static int8_t       g_roi_rampa_ultimo_enviado = 99;
static unsigned long g_roi_rampa_ultimo_envio = 0;
static unsigned long g_bloqueo_post_rampa_hasta = 0;

void actualizarEstadoRampaPi()
{
    const unsigned long now = millis();
    int8_t candidato = g_roi_rampa_estado;

    // Histeresis: entrar exige +/-14 grados; para volver a llano hay que caer
    // dentro de +/-8 grados. Asi no oscila cerca del borde de la rampa.
    if (g_roi_rampa_estado == 0)
    {
        if (pitch >= ROI_RAMPA_ENTRA_GRADOS) candidato = 1;
        else if (pitch <= -ROI_RAMPA_ENTRA_GRADOS) candidato = -1;
        else candidato = 0;
    }
    else if (g_roi_rampa_estado > 0)
    {
        if (pitch <= -ROI_RAMPA_ENTRA_GRADOS) candidato = -1;
        else if (pitch <= ROI_RAMPA_SALE_GRADOS) candidato = 0;
        else candidato = 1;
    }
    else
    {
        if (pitch >= ROI_RAMPA_ENTRA_GRADOS) candidato = 1;
        else if (pitch >= -ROI_RAMPA_SALE_GRADOS) candidato = 0;
        else candidato = -1;
    }

    if (candidato != g_roi_rampa_candidato)
    {
        g_roi_rampa_candidato = candidato;
        g_roi_rampa_candidato_desde = now;
    }

    // Todo cambio debe sostenerse 200 ms: evita que un cabeceo corto cambie el ROI.
    if (g_roi_rampa_candidato != g_roi_rampa_estado &&
        (now - g_roi_rampa_candidato_desde) >= ROI_RAMPA_CONFIRMA_MS)
    {
        const int8_t estadoAnterior = g_roi_rampa_estado;
        g_roi_rampa_estado = g_roi_rampa_candidato;
        // Tras terminar una subida o bajada, el chasis se acomoda y los encoders
        // pueden parecer trabados. Durante 10 s no se permite la maniobra general.
        if (estadoAnterior != 0 && g_roi_rampa_estado == 0)
            g_bloqueo_post_rampa_hasta = now + BLOQUEO_POST_RAMPA_MS;
    }

    // Enviar al cambiar y revalidar cada 500 ms por si la Pi se reinicio o perdio un byte.
    if (g_roi_rampa_estado != g_roi_rampa_ultimo_enviado ||
        (now - g_roi_rampa_ultimo_envio) >= ROI_RAMPA_REENVIO_MS)
    {
        uint8_t dato = TEENSY_RAMPA_LLANO;
        if (g_roi_rampa_estado > 0) dato = TEENSY_RAMPA_SUBE;
        else if (g_roi_rampa_estado < 0) dato = TEENSY_RAMPA_BAJA;

        Serial5.write(dato);
        g_roi_rampa_ultimo_enviado = g_roi_rampa_estado;
        g_roi_rampa_ultimo_envio = now;
    }
}

bool chequearAtasco(int comandoVel)
{

    unsigned long now = millis();

    // Gracia de ATASCO_GRACE_MS tras arrancar: no dispara al apoyarlo en la pista.
    if (now - atascoArmedSince < ATASCO_GRACE_MS)
    {
        stuck_since = now;
        return false;
    }

    if (comandoVel <= 0)
    {
        stuck_since = now;
        return false;
    }

    if (now - stuck_lastSample >= STUCK_SAMPLE_MS)
    {
        stuck_lastSample = now;
        long frNow = (long)fr.pulseCount, flNow = (long)fl.pulseCount;
        long frD = labs(frNow - stuck_lastFr);
        long flD = labs(flNow - stuck_lastFl);
        stuck_lastFr = frNow; stuck_lastFl = flNow;
        long minRueda = min(frD, flD);

        // Las dos delanteras giran >= UMBRAL_RUEDA: no hay atasco, reinicio el tiempo.
        if (minRueda >= UMBRAL_RUEDA)
            stuck_since = now;
    }

    // En subida nunca entra la recuperacion general (retroceso + avance): un cabeceo puede hacer
    // que el pitch instantaneo baje de 12 aunque seguimos en rampa. Mientras cualquiera de los
    // detectores de rampa este activo, la unica recuperacion permitida es el pulso recto del
    // palillo de 1 s. Al salir de una pendiente tambien se espera 10 s antes de
    // permitir recuperar: evita una maniobra por el cabeceo de la transicion.
    const bool bloqueoPostRampa = g_bloqueo_post_rampa_hasta != 0 &&
        (long)(g_bloqueo_post_rampa_hasta - now) > 0;
    if (pitch > PITCH_RAMPA || g_rampa_estado == 1 || g_roi_rampa_estado == 1 || bloqueoPostRampa)
    {
        stuck_since = now;
        return false;
    }

    return (now - stuck_since >= STUCK_TIME_MS);
}

#if RAMPA_ACTIVA
// Empuje del palillo (ver rampa.h): la cuenta de DriveBase::steer() con el giro acotado a
// PALILLO_ROT_MAX -ninguna rueda va marcha atras- y UNA sola orden por trasera con consigna
// max(steer, minTrasera). Con dos ordenes por vuelta (steer y despues el refuerzo) la trasera de
// adentro de una curva de mas de ~40 grados recibe atras y adelante, se le borra el PID y queda
// clavada: por eso el palillo no pasaba. Es la opcion 4 del 16-sep, que paso el palillo con las 4
// ruedas; ahora solo corre mientras dura el empuje y las traseras suben de a poco.
#ifndef PALILLO_ROT_MAX
#define PALILLO_ROT_MAX    0.40    // interna a (1 - 2*0,40) = 20 % hacia adelante
#endif
#ifndef PALILLO_RPM_POR_S
#define PALILLO_RPM_POR_S  90.0    // de ~36 a 80 rpm en ~0,5 s: sin el tiron de la opcion 4
#endif

void steerRampaTraseras(double speed, int direction, double rotation, double minTrasera)
{
    robot._speed = constrain(speed, 0, 159);
    robot._rotation = constrain(rotation, -1, 1);
    robot._direction = direction;
    double ls, rs;
    int ld, rd;
    if (rotation >= 0)   // gira a la izquierda: la base es la derecha
    {
        rs = robot._speed;
        rd = direction;
        ld = direction;
        ls = robot._speed - (2 * rotation * robot._speed);
        if (ls < 0) { ld = !ld; ls = -ls; }
    }
    else
    {
        ls = robot._speed;
        ld = direction;
        rd = direction;
        rs = robot._speed + (2 * rotation * robot._speed);
        if (rs < 0) { rd = !rd; rs = -rs; }
    }
    robot._leftspeed = ls;
    robot._rightspeed = rs;
    robot._leftdir = ld;
    robot._rightdir = rd;
    fl.setSpeed(ld, ls);
    bl.setSpeed(ld, (ld == FORWARD) ? max(ls, minTrasera) : ls);
    fr.setSpeed(!rd, rs);    // lado derecho espejado, igual que steer()
    br.setSpeed(!rd, (rd == FORWARD) ? max(rs, minTrasera) : rs);
}
#endif

// Mezclador exclusivo de subida: normalmente las cuatro ruedas avanzan a 40 rpm.
// Solo una curva fuerte de la Pi supera la zona muerta y acelera suavemente el
// lado externo hasta 50 rpm; el interno nunca baja de 40 ni invierte. Asi el
// robot sube recto aun con las curvitas de la camara y conserva una correccion
// de emergencia para una curva real.
void steerRampaCuatroAdelante(double rotation)
{
    rotation = constrain(rotation, -1.0, 1.0);
    const double base = POTENCIA_TRASERAS;
    const double giro = fabs(rotation);
    const double extra = (giro <= RAMPA_GIRO_MUERTO) ? 0.0 :
        (RAMPA_EXTERIOR_MAX_RPM - base) *
        (giro - RAMPA_GIRO_MUERTO) / (1.0 - RAMPA_GIRO_MUERTO);
    double ls = base;
    double rs = base;
    if (rotation >= 0) rs = min(159.0, base + extra);  // giro a izquierda: derecha exterior
    else               ls = min(159.0, base + extra);  // giro a derecha: izquierda exterior

    robot._speed = base;
    robot._rotation = rotation;
    robot._direction = FORWARD;
    robot._leftspeed = ls;
    robot._rightspeed = rs;
    robot._leftdir = FORWARD;
    robot._rightdir = FORWARD;
    fl.setSpeed(FORWARD,  ls);
    bl.setSpeed(FORWARD,  ls);
    fr.setSpeed(!FORWARD, rs);  // motores derechos espejados
    br.setSpeed(!FORWARD, rs);
}

void recuperarAtasco()
{
    DBG_PRINTLN("[ATASCO] rueda clavada -> retro + avance brusco");
    // Retrocede corto para bajar de la loma y avanza fuerte (100, no es el maximo) para pasarla.
    runTime(90,  BACKWARD, 0, 150);
    runTime(100, FORWARD,  0, 250);
    stuck_lastFr = (long)fr.pulseCount;
    stuck_lastFl = (long)fl.pulseCount;
    stuck_since  = millis();
    stuck_lastSample = millis();
}


#if TELEMETRIA
// enviarTelemetria(): una linea JSON por Serial8 a la ESP32 (10 Hz, cadencia en
// Telemetria::debeEnviar). Las claves son las del snprintf de abajo; las parsea
// software/esp32/telemetria.

// NaN/inf -> 0: un 'nan' en el texto invalida el JSON en la GUI.
static float sanef(float v)
{
    return (isnan(v) || isinf(v)) ? 0.0f : v;
}

// ############################################################################
// 10. TELEMETRIA JSON HACIA LA ESP32 (solo entorno `telemetria`). Solo lee: no llama getSpeed() ni
// bloquea; si el TX no tiene lugar descarta el frame.
// ############################################################################

void enviarTelemetria()
{
    if (!telemetria.debeEnviar())
    {
        return;
    }

    // Dos lecturas I2C del BNO por frame (euler + giroscopo), ~2 ms cada 100 ms.
    sensors_event_t ev;
    bno.getEvent(&ev);
    float t_yaw = sanef(ev.orientation.x);
    float t_pit = sanef(ev.orientation.y);
    float t_rol = sanef(ev.orientation.z);
    float t_cen = sanef(centrar);
    // Giroscopo en grados/s, los 3 ejes: cual es el yaw depende del montaje.
    imu::Vector<3> gv = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);
    float t_gx = sanef(gv.x()), t_gy = sanef(gv.y()), t_gz = sanef(gv.z());

    // Color filtrado actual (lee los buffers de historial, no dispara el sensor).
    uint16_t cr = 0, cg = 0, cb = 0, cc = 0;
    get_filtered_color(cr, cg, cb, cc);

    // Los %s (colores, rutina, pared, lado, prim) son literales sin comillas ni
    // backslash: no se escapan.
    long g_age = g_last_ms ? (long)(millis() - g_last_ms) : -1L;   // ms desde el ultimo verde (-1 = nunca)

    // Solo lecturas: NO llamar getSpeed() aca (escribe _realrpm, que es la entrada del PID).
    // _realrpm no esta acotado: se sanea y satura.
    const int pwm_fl = (int)fl.getPWM(), pwm_fr = (int)fr.getPWM();
    const int pwm_bl = (int)bl.getPWM(), pwm_br = (int)br.getPWM();
    const float r_fl = sanef(fl._realrpm), r_fr = sanef(fr._realrpm);
    const float r_bl = sanef(bl._realrpm), r_br = sanef(br._realrpm);
    const int rpm_fl = (int)constrain(r_fl, -9999.0f, 99999.0f);
    const int rpm_fr = (int)constrain(r_fr, -9999.0f, 99999.0f);
    const int rpm_bl = (int)constrain(r_bl, -9999.0f, 99999.0f);
    const int rpm_br = (int)constrain(r_br, -9999.0f, 99999.0f);

    // hdr (commit del firmware) solo durante 2 s despues del flanco de subida de startUp,
    // no en cada frame.
    static bool prevUp = false;
    static unsigned long hdrDesde = 0;
    if (startUp && !prevUp) { hdrDesde = millis(); }
    prevUp = startUp;
    const bool hdrOn = startUp && (millis() - hdrDesde < 2000UL);

#define TSAT(v) (int)constrain(sanef(v), -9999.0f, 99999.0f)
    static unsigned long tlm_trunc = 0;   // frames descartados por no entrar en buf
    // Estado explicito del antiatasco de palillo. `ms` es el tiempo que lleva
    // verificando una rueda trabada (pal=1) o empujando con cuatro ruedas (pal=2).
    const unsigned long t_now = millis();
    const unsigned long pal_ms = (g_palillo == 1 && g_palilloCuentaDesdeMs)
        ? (t_now - g_palilloCuentaDesdeMs)
        : (g_palillo == 2 && g_palilloDesdeMs ? (t_now - g_palilloDesdeMs) : 0UL);

    static char buf[1664];   // frame v3 ~1400 B; si crece, agrandar tambien TLM_LINE_MAX en la ESP32
    int n = snprintf(
        buf, sizeof(buf),
        "{\"t\":%lu,%s"
        "\"rpi\":{\"speed\":%d,\"steer\":%.3f,\"green\":%d,\"silver\":%d,\"rxb\":%lu,\"rxf\":%lu,\"st\":%d},"
        "\"col\":{\"d\":\"%s\",\"dc\":\"%s\",\"r\":%u,\"g\":%u,\"b\":%u,\"c\":%u,\"ok\":%d},"
        "\"us\":{\"f\":%d,\"l\":%d,\"r\":%d},"
        "\"tof\":{\"l\":%d,\"r\":%d},"
        "\"imu\":{\"yaw\":%.1f,\"pit\":%.1f,\"rol\":%.1f,\"cen\":%.1f},"
        "\"rmp\":{\"det\":%d,\"roi\":%d,\"pal\":%d,\"ms\":%lu},"
        "\"enc\":{\"fl\":%ld,\"fr\":%ld,\"bl\":%ld,\"br\":%ld},"
        // raw = flancos crudos del encoder, sin signo (no dependen de _dir).
        "\"raw\":{\"fl\":%lu,\"fr\":%lu,\"bl\":%lu,\"br\":%lu},"
        "\"pwm\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"rpm\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        // dir = sentido comandado, set = consigna rpm, tog = inversiones de sentido del lazo
        // historico (siempre 0 con FIX_LAZO_MOTOR=1), drv = entrada de DriveBase + g_line_branch.
        "\"dir\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"set\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"tog\":{\"fl\":%lu,\"fr\":%lu,\"bl\":%lu,\"br\":%lu},"
        "\"drv\":{\"rot\":%.3f,\"ls\":%d,\"rs\":%d,\"dir\":%d,\"ram\":%d},"
        "\"loop\":{\"ms\":%lu,\"max\":%lu},"
        // pmin/pmax/rmin/rmax = envolvente de PWM y RPM desde el frame anterior.
        "\"pmin\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"pmax\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"rmin\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"rmax\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"gyr\":{\"x\":%.1f,\"y\":%.1f,\"z\":%.1f},"
        "\"rxage\":%ld,"
        "\"fsm\":{\"rut\":\"%s\",\"act\":%d,\"task\":%d,\"up\":%d,\"resc\":%d,\"balls\":%d,\"dep\":%d,\"verd\":%d,\"evi\":%d,\"evs\":%d,\"slatch\":%d,\"pared\":\"%s\",\"lado\":\"%s\",\"prim\":\"%s\",\"ran\":%d},"
        "\"io\":{\"sw\":%d,\"fcl\":%d,\"fcr\":%d,\"rel\":%d,\"buz\":%d,\"led\":%d},"
        "\"claw\":{\"busy\":%d},"
        "\"grn\":{\"rx\":[%lu,%lu,%lu,%lu],\"act\":[%lu,%lu,%lu,%lu],\"kill\":[%lu,%lu,%lu,%lu],\"lt\":%d,\"age\":%ld,\"lrc\":%d}}\n",
        t_now, hdrOn ? HDR_JSON : "",
        (int)speed, steer, green_state, silver_line, serial_bytes_rx, serial_frames_rx, serial5state,
        // d  = lo que el sensor ve AHORA (se refresca con cada muestra) -> para CALIBRAR.
        // dc = lo que esta usando el control (solo se asigna en las rutinas de marcha).
        last_color_detected.c_str(), color_detected.c_str(),
        (unsigned)cr, (unsigned)cg, (unsigned)cb, (unsigned)cc, color_sensor_ok ? 1 : 0,
        front_distance, left_distance, right_distance,
        distance_left_tof, distance_right_tof,
        t_yaw, t_pit, t_rol, t_cen,
        g_rampa_estado, (int)g_roi_rampa_estado, g_palillo, pal_ms,
        (long)fl.pulseCount, (long)fr.pulseCount, (long)bl.pulseCount, (long)br.pulseCount,
        (unsigned long)fl.pulsesRaw, (unsigned long)fr.pulsesRaw,
        (unsigned long)bl.pulsesRaw, (unsigned long)br.pulsesRaw,
        pwm_fl, pwm_fr, pwm_bl, pwm_br,
        rpm_fl, rpm_fr, rpm_bl, rpm_br,
        fl._dir, fr._dir, bl._dir, br._dir,
        (int)fl._rpm, (int)fr._rpm, (int)bl._rpm, (int)br._rpm,
        (unsigned long)fl.dirToggles, (unsigned long)fr.dirToggles,
        (unsigned long)bl.dirToggles, (unsigned long)br.dirToggles,
        robot._rotation, (int)robot._leftspeed, (int)robot._rightspeed,
        robot._direction, g_line_branch,
        g_loop_dt, g_loop_dt_max,
        TSAT(fl._pwmMin), TSAT(fr._pwmMin), TSAT(bl._pwmMin), TSAT(br._pwmMin),
        TSAT(fl._pwmMax), TSAT(fr._pwmMax), TSAT(bl._pwmMax), TSAT(br._pwmMax),
        TSAT(fl._rpmMin), TSAT(fr._rpmMin), TSAT(bl._rpmMin), TSAT(br._rpmMin),
        TSAT(fl._rpmMax), TSAT(fr._rpmMax), TSAT(bl._rpmMax), TSAT(br._rpmMax),
        t_gx, t_gy, t_gz,
        g_last_rx_ms ? (long)(millis() - g_last_rx_ms) : -1L,
        rutina.c_str(), action, taskDone ? 1 : 0, startUp ? 1 : 0, (int)rescateState,
        ball_counter, veces_deposit, verdes_total,
        evacuacion_iniciada ? 1 : 0, evacuacion_straight ? 1 : 0, silver_latch ? 1 : 0,
        pared.c_str(), lado_plateado.c_str(), g_prim, RanNumber,
        digitalRead(SWITCH), digitalRead(FCL), digitalRead(FCR),
        digitalRead(RELAY), digitalRead(BUZZER), digitalRead(LED_ROJO),
        claw.busy() ? 1 : 0,
        g_rx[0], g_rx[1], g_rx[2], g_rx[3],
        g_act[0], g_act[1], g_act[2], g_act[3],
        g_kill[0], g_kill[1], g_kill[2], g_kill[3],
        g_last_type, g_age, g_last_recheck_gs);

    // Un frame truncado no se manda: saldria sin '\n' y la ESP32 descartaria tambien el siguiente.
    const bool trunco = (n < 0 || n >= (int)sizeof(buf));
    if (trunco)
    {
        tlm_trunc++;
    }

#if TELEMETRIA_DEBUG_USB
    // Debug por USB, 1 linea/s: frames enviados, descartados, truncados y largo del ultimo.
    static unsigned long lastDbg = 0;
    if (millis() - lastDbg >= 1000)
    {
        lastDbg = millis();
        DBG_PRINT("[TLM] env=");
        DBG_PRINT(telemetria.framesEnviados());
        DBG_PRINT(" desc=");
        DBG_PRINT(telemetria.framesDescartados());
        DBG_PRINT(" trunc=");
        DBG_PRINT(tlm_trunc);
        DBG_PRINT(" len=");
        DBG_PRINT(n);
        DBG_PRINT(" avail=");
        DBG_PRINTLN(Serial8.availableForWrite());
    }
#endif

    if (trunco)
    {
        return;
    }
    telemetria.enviar(buf, n);
    g_loop_dt_max = 0;

    // el min/max es POR VENTANA: se rearma recien despues de mandarlo
    fl.resetEnvolvente(); fr.resetEnvolvente();
    bl.resetEnvolvente(); br.resetEnvolvente();
}
#endif // TELEMETRIA

#if TELEMETRIA
// Como delay(ms), pero sigue mandando telemetria y muestreando color. Solo se usa en
// idle (calibracion).
void delayTelemetria(unsigned long ms)
{
    unsigned long t0 = millis();
    while (millis() - t0 < ms)
    {
        enviarTelemetria();
        get_color_fast();   // muestra fresca para el panel de calibracion
        yield();            // conserva la semantica de delay() (serialEventN, USB)
        delay(2);
    }
}
#else
inline void delayTelemetria(unsigned long ms) { delay(ms); }
#endif

// ############################################################################
// 11. setup(). Sin BNO055 NO arranca (parpadeo + chicharra para siempre: sin IMU no hay runAngle).
// Sin APDS arranca con 3 parpadeos y sin color (se pierde la entrada a evacuacion y el rojo final).
// ############################################################################

void setup()
{
    DIAG_SETUP();   // registrador CSV de 200 Hz: activo en `competencia`, vacio en `telemetria`

    robot.steer(0, 0, 0);
    angulo_rescate = fmod(20, 360.0);
    attachInterrupt(digitalPinToInterrupt(27), ISR1, CHANGE);
    attachInterrupt(digitalPinToInterrupt(5), ISR2, CHANGE);
    attachInterrupt(digitalPinToInterrupt(38), ISR3, CHANGE);
    attachInterrupt(digitalPinToInterrupt(2), ISR4, CHANGE);
    pinMode(SWITCH, INPUT_PULLUP);
    pinMode(BUZZER, OUTPUT);
    pinMode(LED_ROJO, OUTPUT);
    pinMode(LED_BUILTIN, OUTPUT);
    pinMode(RELAY, OUTPUT);          
    Serial5.begin(115200);         // enlace con la Raspberry Pi (tramas 255/254/253/252 y ACKs)
#if TELEMETRIA
    telemetria.begin(TLM_BAUD);    // TELEMETRIA: abre Serial8 hacia la ESP32-MINI (AP + GUI)
#endif
    delay(200);
    if (!bno.begin())
    {
        handleBnoInitFailure();
    }
    bno.setExtCrystalUse(true);

    color_sensor_ok = apds.begin();
    if (!color_sensor_ok)
    {
        notifyOptionalSensorWarning();   // 3 parpadeos + chicharra, y sigue igual
    }
    else
    {
        apds.enableColor(true);
        apds.enableProximity(true);
    }

    Wire1.begin();
    Wire2.begin();

    // ToF izquierdo en Wire2, derecho en Wire1
    left_tof.setBus(&Wire2);
    right_tof.setBus(&Wire1);

    // cada ToF tiene su propio bus: la 0x30 repetida no choca
    left_tof.setAddress(0x30);
    right_tof.setAddress(0x30);


    // setTimeout() ANTES de init(): con timeout 0 los while internos de init() no tienen salida y
    // setup() se cuelga si un ToF no completa la secuencia.
    // I2C a 100 kHz (default) a proposito: 400 kHz (Wire.setClock) nunca se probo en banco.
    left_tof.setTimeout(500);
    right_tof.setTimeout(500);

    left_tof.init();
    left_tof.setMeasurementTimingBudget(TOF_PRESUPUESTO_US);
    left_tof.startContinuous();

    right_tof.init();
    right_tof.setMeasurementTimingBudget(TOF_PRESUPUESTO_US);
    right_tof.startContinuous();
    pinMode(FCL, INPUT_PULLDOWN);
    pinMode(FCR, INPUT_PULLDOWN);

    claw.begin();
    for (int i = 0; i < 20; i++)
    {
        Serial5.write(0xFA);
        delay(100);
    }

}


bool retrocederHastaFinales(int velocidad)
{
    const unsigned long CONFIRMACION_MS = 50;
    const unsigned long TIMEOUT_MS = 20000;

    unsigned long inicio = millis();
    unsigned long ambosDesde = 0;

    while (digitalRead(SWITCH) == 0)
    {
        robot.steer(velocidad, BACKWARD, 0);
        serialEvent5();

        bool fcl = (digitalRead(FCL) == HIGH);
        bool fcr = (digitalRead(FCR) == HIGH);

        // Confirmado = los dos finales en HIGH durante CONFIRMACION_MS seguidos.
        if (fcl && fcr)
        {
            if (ambosDesde == 0)
            {
                ambosDesde = millis();
            }

            if (millis() - ambosDesde >= CONFIRMACION_MS)
            {
                robot.steer(0, FORWARD, 0);
                return true;
            }
        }
        else
        {
            ambosDesde = 0;
        }

        // Seguridad por si un final nunca llega.
        if (millis() - inicio >= TIMEOUT_MS)
        {
            robot.steer(0, FORWARD, 0);
            return false;
        }
    }

    robot.steer(0, FORWARD, 0);
    return false;
}

// ############################################################################
// 12. loop(). Segun el switch (pin 32 = SWITCH):
//   APAGADO (1): idle. Motores en 0, avisa 255 a la Pi, resetea el estado de la corrida y parpadea
//     (en competencia fluye el CSV, no la telemetria).
//   RECIEN ENCENDIDO (0 y !startUp): dos sacudones de 300 ms, arma el anti-atasco y manda 0xF9.
//   ENCENDIDO: rutina "linea" -> "rescate" -> "evacuacion".
// ############################################################################

void loop()
{
    DIAG_TICK();
    // Periodo del loop en ms y su pico (lo publica y resetea la telemetria).
    {
        static unsigned long _lastLoopUs = 0;
        unsigned long _nowUs = micros();
        if (_lastLoopUs) {
            g_loop_dt = (_nowUs - _lastLoopUs) / 1000UL;
            if (g_loop_dt > g_loop_dt_max) g_loop_dt_max = g_loop_dt;
        }
        _lastLoopUs = _nowUs;
    }
    claw.update();
    actualizarRescate();
    enviarTelemetria();   // vacia en competencia (TELEMETRIA=0)
    if (digitalRead(32) == 1)
    {                               // switch APAGADO (INPUT_PULLUP: 1 = apagado)
        robot.steer(0, FORWARD, 0);
        claw.lift();
        claw.sortLeft();
        Serial5.clear();
        evacuacion_iniciada = false;
        evacuacion_straight = false;
        silver_latch = false;
        action = 7;
        startUp = false;
        g_recup_signo = 0;
        g_recup_rumbo_camino_rx = 0.0;
        g_recup_rumbo_camino_rx_ms = 0;
        g_recup_episodio_activo = false;
        g_recup_habilitada = false;
        g_recup_gs0_desde = 0;
        g_gap_retro_pulsos = 0;
        resetGapState();
        rojo_ignorar_hasta = 0;
        g_evac_pared_lado = 0;
        g_evac_pared_ms = 0;
        taskDone = true;
        Serial5.write(255);
        verdes_total=0;
        while (true)
        {
            // Drenar el registrador CSV tambien en idle: si no, con el switch apagado el USB queda
            // mudo y parece un setup() colgado.
            DIAG_TICK();
            enviarTelemetria();
            robot.steer(0, 0, 0);
                    digitalWrite(RELAY,LOW);
            claw.lift();
            get_color_fast();
            serialEvent5();
            centrar = leer_yaw();            
            centrar = fmod(centrar, 360.0);
             if (centrar < 0) centrar += 360;
            digitalWrite(LED_BUILTIN, HIGH);
            digitalWrite(LED_ROJO, HIGH);
            delayTelemetria(500);   // 500 ms; con TELEMETRIA=1 sigue mandando telemetria y color
            robot.steer(0, 0, 0);
           get_color_fast();
            digitalWrite(LED_BUILTIN, LOW);
            digitalWrite(BUZZER, LOW);
            digitalWrite(LED_ROJO, LOW);
            digitalWrite(RELAY,LOW);
            claw.open();
            delayTelemetria(500);

            get_color_fast();

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
        startUp = true;
        atascoArmedSince = millis();   // arranca el grace: no dispara el anti-atasco al ponerlo en pista
        rutina = "linea";
        evacuacion_iniciada = false;
        evacuacion_straight = false;
        silver_latch = false;
        rescateAvisado = false;
        g_evac_pared_lado = 0;
        g_evac_pared_ms = 0;
        g_silver_rec_kind = SILVER_REC_NONE;
        g_silver_rec_pivot_sign = 0;
        g_silver_rec_actual_deg = 0.0f;
        g_silver_rec_ms = 0;
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
        while (rutina == "linea" && digitalRead(32) == 0)
        {
            serialEvent5();

            // WATCHDOG DE COMUNICACION (panel 1.5): sin trama completa por WATCHDOG_MS,
            // sostenido WATCHDOG_CONFIRMA_MS, se frena. Si nunca llego trama se cuenta desde la
            // entrada al lazo.
            if (g_wd_ref_ms == 0)
                g_wd_ref_ms = millis();
            const unsigned long ref = g_last_rx_ms ? g_last_rx_ms : g_wd_ref_ms;
            const long edadRx = (long)(millis() - ref);
            if ((unsigned long)edadRx > WATCHDOG_MS)
            {
                if (g_wd_stale_ms == 0)
                    g_wd_stale_ms = millis();
            }
            else
            {
                g_wd_stale_ms = 0;
            }

            if (g_wd_stale_ms != 0 &&
                (millis() - g_wd_stale_ms)
                    >= WATCHDOG_CONFIRMA_MS)
            {
                if (!g_wd_activo)
                {
                    g_wd_activo = true;
                    DBG_PRINT("[WD] sin tramas hace ");
                    DBG_PRINT(edadRx);
                    DBG_PRINTLN(" ms: FRENO");
                }
                robot.steer(0, FORWARD, 0);
                digitalWrite(LED_BUILTIN, (millis() / 150) % 2);
                continue;          // no se decide nada con datos rancios
            }
            if (g_wd_activo)
            {
                g_wd_activo = false;
                DBG_PRINTLN("[WD] volvieron las tramas: sigo");
            }

            DIAG_TICK();   // este while no vuelve a loop(): el registrador se drena aca
            enviarTelemetria();
            bool plateadoDetectado = false;
            color_detected = get_color_fast();
            // Solo el ultrasonido frontal (cada 40 ms, techo 30 cm). Los ToF no se leen en
            // linea (panel 1.4).
            leer_ultrasonido_frontal();

#if PLATEADO_TEENSY
            if (color_detected == "Plateado" && confirmarPlateadoLinea()) {
                    if (!rescateAvisado) {
                        // deshace la mitad del ultimo pivote de recuperacion (SILVER_REC_*); la
                        // camara no opina
                        corregirEntradaPlateadoDesdeRecovery();
                        Serial5.write(TEENSY_ACK_RESCATE_APDS);
                        rescateAvisado = true;
                    }
                    plateadoDetectado = true;
            }
#endif

            // LINEA ROJA = fin de corrida: 10 s quieto y sale del lazo (loop() vuelve a
            // entrar despues).
            if (color_detected == "Rojo" && millis() >= rojo_ignorar_hasta) {
                runTime(0, FORWARD, 0, 10000);
                break;
            }
           
            if (taskDone)
            { // taskDone solo es false si se encendio con el switch en ON (nunca paso por idle)

                // ARBITRO DE GS4 (segunda barrera, la primera es la Pi): solo se abre un episodio
                // de recuperacion despues de RECUP_REARME_TEENSY_MS de GS=0 continuo.
                if (green_state == 0)
                {
                    action = 7;

                    if (g_gap_activo)
                        resetGapState();

                    if (g_recup_episodio_activo)
                    {
                        // Volvio la linea: cierra el episodio y reinicia la cuenta del rearme.
                        g_recup_episodio_activo = false;
                        g_recup_habilitada = false;
                        g_recup_gs0_desde = millis();
                        g_recup_signo = 0;
                        g_recup_retroceso_hecho = false;
                        g_recup_giro_hecho = false;
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                    }
                    else
                    {
                        if (g_recup_gs0_desde == 0)
                            g_recup_gs0_desde = millis();
                        if (!g_recup_habilitada &&
                            (millis() - g_recup_gs0_desde) >= RECUP_REARME_TEENSY_MS)
                            g_recup_habilitada = true;
                    }
                }

                if (green_state == 1)
                {
                    // Maniobra verde conocida: GS4 queda desarmado.
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    // verde a la IZQUIERDA
                    action = 6;
                }
                if (green_state == 2)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    action = 5;   // verde a la DERECHA
                }

                if (green_state == LINEA_PERDIDA_GS)
                {
                    g_recup_gs0_desde = 0;

                    if (g_recup_episodio_activo)
                    {
                        // MISMA perdida: continuar la recuperacion, no re-disparar.
                        action = 4;
                    }
                    else if (g_recup_habilitada)
                    {
                        // Flanco valido: empieza UN episodio.
                        g_recup_episodio_activo = true;
                        g_recup_habilitada = false;
                        g_recup_retroceso_hecho = false;
                        g_recup_giro_hecho = false;
                        action = 4;
                    }
                    else
                    {
                        // GS4 al arrancar, despues de un verde o por rebote: no mover.
                        action = RECUP_WAIT_ACTION;
                    }
                }
                if (green_state == GAP_BUSQUEDA_GS)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_signo = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    if (!g_gap_activo)
                    {
                        g_gap_activo = true;
                        g_gap_origen_enviado = false;
                        g_gap_timeout_enviado = false;
                        g_gap_inicio_fl = (long)fl.pulseCount;
                        g_gap_inicio_fr = (long)fr.pulseCount;
                        g_gap_inicio_ms = millis();

                        // memoria para el plateado: por GAP se entra recto, no hay
                        // giro que deshacer
                        g_silver_rec_kind = SILVER_REC_RECTA;
                        g_silver_rec_pivot_sign = 0;
                        g_silver_rec_actual_deg = 0.0f;
                        g_silver_rec_ms = millis();
                    }
                    action = GAP_ACTION;
                }

                if (green_state == PERDIDA_FAILSAFE_GS)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    resetGapState();
                    action = PERDIDA_FAILSAFE_ACTION;
                }

                if (green_state == 3)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    action = 14;
                }
                if (front_distance != 0 && front_distance < 2)
                {
                get_color_fast();
#if PLATEADO_TEENSY
            if (color_detected == "Plateado" && confirmarPlateadoLinea()) {
                    if (!rescateAvisado) {
                        corregirEntradaPlateadoDesdeRecovery();
                        Serial5.write(TEENSY_ACK_RESCATE_APDS);
                        rescateAvisado = true;
                    }
                    plateadoDetectado = true;
            }
#endif
                    action = 1;
                }
               
                if (green_state == 14)
                {
                    action = 12;
                }
                // el plateado lo decide solo el APDS; silver_line de la Pi no tiene autoridad
                if (plateadoDetectado) {
                    action = 2;
                }


                switch (action)
                {
                case 1:
                    digitalWrite(BUZZER, HIGH);
                    delay(100);
                    digitalWrite(BUZZER, LOW);

                        // Lado de esquive: 1 = izquierda, 2 = derecha. El primer random(3) no se
                        // usa pero avanza el generador (no hay randomSeed): borrarlo cambia la
                        // secuencia de lados.
                        RanNumber = random(3);
                        RanNumber = random(1, 3);
                        if (RanNumber == 1)
                        {
                            runAngle(25, FORWARD, -95);
                                                        get_color_fast();
                                        while (digitalRead(32) == 0)
                            {
                                robot.steer(77, FORWARD, -0.38);
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
                    depositando=false;
                    runTime(30, FORWARD, 0,800);
                    runTime(0, FORWARD, 0, 1000);
                    leer_ultrasonidos();
                    if(left_distance>right_distance){
                        runAngle(30,FORWARD,-20);
                    }
                    if(right_distance>left_distance){
                        runAngle(30,FORWARD,20);}
                     runTime(30,FORWARD,0,2000);


                   
                    leer_ultrasonidos();
                    if(left_distance < right_distance)
                    {
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
                    runTime(0,FORWARD,0,3000);
                    break;
                case 4:   // LINEA PERDIDA: UN SOLO RETROCESO -> REANALIZA -> PIVOTE
                {
                    // Fases enclavadas por episodio (GS4 llega muchas vueltas): retroceso 1 vez,
                    // mirar quieto, pivote 1 vez, despues quieto. Ver panel 1.8.

                    if (!g_recup_retroceso_hecho)
                    {
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                        g_recup_signo = 0;
                        g_line_branch = 14;
                        const long retroFl0 = (long)fl.pulseCount;
                        const long retroFr0 = (long)fr.pulseCount;
                        runTime(RECUP_VEL, BACKWARD, 0, RECUP_MS);
                        const long retroFl = labs((long)fl.pulseCount - retroFl0);
                        const long retroFr = labs((long)fr.pulseCount - retroFr0);
                        // Si un encoder delantero no midio >= 10 pulsos, retro_pulsos = 0: el GAP
                        // no manda 0xEE y termina por fail-safe.
                        g_gap_retro_pulsos = (retroFl >= 10 && retroFr >= 10)
                            ? (retroFl + retroFr) / 2
                            : 0;
                        serialEvent5();
                        g_recup_retroceso_hecho = true;
                        Serial5.write(TEENSY_ACK_RETRO_DONE);

                        // Se descarta el rumbo recibido durante el retroceso: se decide
                        // con la pose nueva.
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                    }

                    // Pivote ya hecho en este episodio: quieto mientras siga GS4.
                    if (g_recup_giro_hecho)
                    {
                        robot.steer(0, FORWARD, 0);
                        break;
                    }

                    // Mirar quieto RECUP_REANALISIS_MS. Sin rumbo fresco no se elige lado; la
                    // vuelta siguiente vuelve a mirar (no retrocede).
                    const unsigned long tAnalisis = millis();
                    robot.steer(0, FORWARD, 0);
                    while (digitalRead(32) == 0 &&
                           (millis() - tAnalisis) < RECUP_REANALISIS_MS)
                    {
                        serviceMotionBackgroundTasks();
                        if (Serial5.available() > 0)
                            serialEvent5();
                    }
                    serialEvent5();

                    const unsigned long edadCamino = g_recup_rumbo_camino_rx_ms
                        ? (millis() - g_recup_rumbo_camino_rx_ms)
                        : 0xFFFFFFFFUL;

                    if (g_recup_rumbo_camino_rx_ms == 0 ||
                        edadCamino > RECUP_REANALISIS_EDAD_MS ||
                        fabs(g_recup_rumbo_camino_rx) < RECUP_STEER_MIN)
                    {
                        g_recup_signo = 0;
                        robot.steer(0, FORWARD, 0);
                        break;
                    }

                    g_recup_signo = (g_recup_rumbo_camino_rx > 0.0) ? 1 : -1;

                    // objetivo = BASE + K * |rumbo CAMINO en grados|, acotado a [MIN, MAX]; no es
                    // 1:1 con el yaw.
                    const float headingCaminoDeg =
                        (float)(fabs(g_recup_rumbo_camino_rx) * 90.0);
                    float objetivoGiro = RECUP_GIRO_BASE_GRADOS
                                         + RECUP_GIRO_CAMINO_K * headingCaminoDeg;

                    // Extra solo a la DERECHA (g_recup_signo < 0 = derecha): a la derecha el
                    // pivote gira menos de lo pedido (medido DER 33-42 vs IZQ 45-48 grados).
                    // 0 = sin efecto.
                    if (g_recup_signo < 0)
                        objetivoGiro += RECUP_GIRO_DER_EXTRA_GRADOS;

                    objetivoGiro = constrain(objetivoGiro,
                                             RECUP_GIRO_MIN_GRADOS,
                                             RECUP_GIRO_MAX_GRADOS);

                    const float yaw0 = leer_yaw();
                    const unsigned long tg0 = millis();

                    while (digitalRead(32) == 0)
                    {
                        serviceMotionBackgroundTasks();
                        if (Serial5.available() > 0)
                            serialEvent5();

                        // Decidido el lado, se completa el giro aunque llegue GS0 (puede reaparecer
                        // la linea vieja durante el pivote).
                        const float girado = fabs(calcularDiferenciaAngulo(
                                                    yaw0, leer_yaw()));
                        if (girado >= objetivoGiro)
                            break;
                        if ((millis() - tg0) >= RECUP_GIRO_MAX_MS)
                            break;

                        g_line_branch = 13;
                        robot.steer(RECUP_GIRO_VEL, FORWARD,
                                    g_recup_signo > 0 ? RECUP_PIVOTE_ROT
                                                     : -RECUP_PIVOTE_ROT);
                    }

                    robot.steer(0, FORWARD, 0);
                    // 0xED: pivote terminado; la Pi puede COMPLETAR_GIRO.
                    Serial5.write(TEENSY_ACK_PIVOTE_DONE);

                    // Memoria del giro real para corregirEntradaPlateadoDesdeRecovery(); sobrevive
                    // al cierre del episodio por GS0.
                    g_silver_rec_kind = SILVER_REC_LATERAL;
                    g_silver_rec_pivot_sign = g_recup_signo;
                    g_silver_rec_actual_deg =
                        fabs(calcularDiferenciaAngulo(yaw0, leer_yaw()));
                    g_silver_rec_ms = millis();

                    g_recup_giro_hecho = true;
                    serialEvent5();

                    if (green_state != LINEA_PERDIDA_GS)
                    {
                        g_recup_signo = 0;
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                        g_recup_episodio_activo = false;
                        g_recup_habilitada = false;
                        g_recup_gs0_desde = millis();
                        g_recup_retroceso_hecho = false;
                        g_recup_giro_hecho = false;
                    }
                    break;
                }
                case GAP_ACTION:
                {
                    if (!g_gap_activo)
                    {
                        g_gap_activo = true;
                        g_gap_inicio_fl = (long)fl.pulseCount;
                        g_gap_inicio_fr = (long)fr.pulseCount;
                        g_gap_inicio_ms = millis();
                    }
                    const long avanzados = gapPulsosDesdeInicio();
                    const long origenObjetivo = g_gap_retro_pulsos + 25L * GAP_ORIGIN_MARGIN_CM;
                    if (!g_gap_origen_enviado && g_gap_retro_pulsos > 0 && avanzados >= origenObjetivo)
                    {
                        Serial5.write(TEENSY_ACK_GAP_ORIGIN);
                        g_gap_origen_enviado = true;
                    }
                    const bool limiteDist = avanzados >= (25L * GAP_MAX_CM);
                    const bool limiteTiempo = (g_gap_inicio_ms != 0 && (millis() - g_gap_inicio_ms) >= GAP_MAX_MS);
                    if (limiteDist || limiteTiempo)
                    {
                        robot.steer(0, FORWARD, 0);
                        if (!g_gap_timeout_enviado)
                        {
                            Serial5.write(TEENSY_ACK_GAP_TIMEOUT);
                            g_gap_timeout_enviado = true;
                        }
                        action = PERDIDA_FAILSAFE_ACTION;
                        break;
                    }
                    robot.steer(GAP_VEL, FORWARD, 0);
                    break;
                }
                case PERDIDA_FAILSAFE_ACTION:
                    robot.steer(0, FORWARD, 0);
                    break;

                case RECUP_WAIT_ACTION:
                    // GS4 sin habilitar (arranque, tras verde o rebote): quieto, sin
                    // retroceder ni girar.
                    robot.steer(0, FORWARD, 0);
                    if (Serial5.available() > 0)
                        serialEvent5();
                    break;
                case 6:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    telemGreenResultado(1, green_state);   // solo cuenta, no decide
                    // Gira siempre: no re-chequear el verde despues de avanzar (a los 800 ms el
                    // cuadrado ya salio de camara). Angulo negativo = izquierda; si la camara se
                    // espeja, invertir signos de case 5 y 6.
                    runAngle(35, FORWARD, -50);
                    break;
                case 5:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    telemGreenResultado(2, green_state);   // solo cuenta, no decide
                    runAngle(25, FORWARD, 50);   // POSITIVO = derecha. Ver el case 6.
                    break;
                case 7: // seguimiento de linea
                    g_recup_signo = 0;
               
                    {int velocidadAjustada = ajustarVelocidadPorPendiente(VELOCIDAD_BASE_LINEA);
                     // ajustarVelocidadPorPendiente() acaba de refrescar `pitch`: avisar a la Pi
                     // si estamos subiendo/bajando para que cambie SOLO el ROI angular.
                     actualizarEstadoRampaPi();

                     if (chequearAtasco(velocidadAjustada)) {   // obstaculo alto: no avanza -> recupero
                         g_line_branch = 9;
                         recuperarAtasco();
                         break;
                     }
                    // LINE_CURVE_STEER y LINE_HARD_CURVE_STEER solo clasifican
                    // g_line_branch. LINE_PIVOT_STEER controla: umbral de rot = 1 y
                    // denominador de la rampa de velocidad.
                    const double LINE_CURVE_STEER = 0.08;       // solo telemetria
                    const double LINE_HARD_CURVE_STEER = 0.35;  // solo telemetria
                    const double LINE_PIVOT_STEER = 0.92;       // CONTROL: ver abajo

                    double steerCmd = constrain(steer * LINE_STEER_GAIN, -1.0, 1.0);
                    double absSteer = fabs(steerCmd);

                    // rot = absSteer ^ LINE_ROT_EXP. El radio depende de rot, no de la velocidad
                    // (ver panel 1.1).

                    // Pivote con histeresis APAGADO: LINE_PIVOTE_ENTRA (1.01) supera el maximo de
                    // absSteer (1.0). Ver panel 1.1.
                    static bool s_en_pivote = false;
                    static unsigned long s_pivote_t0 = 0;
                    static unsigned long s_alineado_t0 = 0;
                    if (!s_en_pivote && absSteer >= LINE_PIVOTE_ENTRA)
                    {
                        s_en_pivote = true;
                        s_pivote_t0 = millis();
                    }
                    else if (s_en_pivote)
                    {
                        // Sale del pivote solo si la alineacion se sostiene LINE_PIVOTE_CONFIRMA_MS
                        // o vence LINE_PIVOTE_MAX_MS.
                        if (absSteer > LINE_PIVOTE_SALE)
                            s_alineado_t0 = 0;              // se desalineo: reiniciar
                        else if (s_alineado_t0 == 0)
                            s_alineado_t0 = millis();       // primer frame alineado

                        bool sostenido = (s_alineado_t0 != 0 &&
                                          millis() - s_alineado_t0 >= LINE_PIVOTE_CONFIRMA_MS);
                        if (sostenido ||
                            millis() - s_pivote_t0 > LINE_PIVOTE_MAX_MS)
                        {
                            s_en_pivote = false;
                            s_alineado_t0 = 0;
                        }
                    }

                    double rot;
                    if (s_en_pivote)
                    {
                        rot = 1.0;   // giro sobre el eje: el centro NO avanza
                    }
                    else
                        rot = pow(absSteer, LINE_ROT_EXP);
                    // Pivote puntual: absSteer >= LINE_PIVOT_STEER fuerza rot = 1.
                    if (absSteer >= LINE_PIVOT_STEER) rot = 1.0;
                    if (rot > 1.0) rot = 1.0;

                    double k = constrain(absSteer / LINE_PIVOT_STEER, 0.0, 1.0);
                    // Rampa cuadratica de velocidad: baja a mitad de curva (ahi avanza y se pasa) y
                    // sube cerca del pivote (ahi solo gira; de 20 a 35 rpm se duplican los
                    // grados/s). Despues se aplica LINE_RECTA_FACTOR o, en curva cerrada,
                    // LINE_FRENO_VEL.
                    int vel = (int)(velocidadAjustada + k * k * (LINE_PIVOT_SPEED - velocidadAjustada));

                    // g_line_branch: solo telemetria/CSV, no decide.
                    g_line_branch = (absSteer > LINE_PIVOT_STEER) ? 3
                                  : (absSteer > LINE_HARD_CURVE_STEER) ? 2
                                  : (absSteer > LINE_CURVE_STEER) ? 1 : 0;

                    // Signo de la trama actual, sin memoria. steerCmd == 0 da -1: inofensivo
                    // porque rot = 0.
                    const int signoCmd = (steerCmd > 0) ? 1 : -1;
#if RAMPA_ACTIVA
                    // Palillo (rampa.h): SOLO si quedo atascado subiendo. Si no, no entra y todo
                    // sigue exactamente como a las 19:00. Sin el refuerzo de abajo: las traseras ya
                    // llevan su orden unica.
                    if (palilloEmpuje(pitch > PITCH_RAMPA))
                    {
                        g_line_branch = 15;
                        // Recuperacion de palillo: un unico pulso recto y lento. No se usa el
                        // angulo de la Pi: las cuatro ruedas van a 40 rpm hacia adelante durante
                        // 300 ms, sin reversa ni maniobra general de atasco en plena subida.
                        runTime(40, FORWARD, 0, PALILLO_EMPUJE_MS);
                        break;
                    }
#endif
                    // Curva cerrada (absSteer >= LINE_FRENO_STEER): velocidad fija
                    // LINE_FRENO_VEL. Con LINE_FRENO_FACTOR = kFrenoComoSteer reparte igual que
                    // steer(): no frena ninguna rueda.
                    if (absSteer >= LINE_FRENO_STEER)
                    {
                        g_line_branch = 7;
                        double rotF = rot * LINE_FRENO_ROT_MULT;
                        if (rotF > 1.0) rotF = 1.0;
                        robot.steerFrenoDelantero(LINE_FRENO_VEL, FORWARD,
                                                  signoCmd > 0 ? rotF : -rotF,
                                                  LINE_FRENO_FACTOR);
                    }
                    else
                        robot.steer(vel * LINE_RECTA_FACTOR, FORWARD,
                                    signoCmd > 0 ? rot : -rot);

                    // Rampa: cuatro ruedas rectas a 40 rpm. Se mantiene durante toda la
                    // pendiente con la histeresis de los detectores, aunque el cabeceo haga
                    // caer momentaneamente el pitch instantaneo. Solo una curva fuerte puede
                    // acelerar el lado exterior; la interna nunca se frena ni invierte.
                    const bool traccionRampa = pitch > PITCH_RAMPA ||
                        g_rampa_estado == 1 || g_roi_rampa_estado == 1;
                    if (traccionRampa)
                    {
                        steerRampaCuatroAdelante(signoCmd > 0 ? rot : -rot);
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

                        // TOPE DURO: si la Pi no manda 15/16/17 en 5 s, se sale.
                        // Sin esto el robot se queda quieto para siempre.
                        if ((millis() - waitStart) >= 5000) break;

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

                    }
                    }
                    break;

                case 14: // Doble verde: media vuelta solo si el re-chequeo sigue viendo GS3.
                    serialEvent5();
                    telemGreenResultado(3, green_state);   // TELEMETRIA: giro o matado por re-chequeo
                    if (green_state == 3)
                    {
                        runAngle(30, FORWARD, 210);
                        runTime(30, FORWARD, 0, 500);
                    }
                    action = 7;
                    break;

                }

            }
        }
        while (rutina == "rescate" && digitalRead(32) == 0)
        {
            enviarTelemetria();
            digitalWrite(RELAY, HIGH);
           digitalWrite(LED_BUILTIN, LOW);
            serialEvent5();
            robot.steer(speed, FORWARD, steer);

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
                claw.sortCenter();
                nonBlockingDelay(1000);
                claw.sortRight();
                nonBlockingDelay(1000);
                runTime(70,FORWARD,0,200);
                runTime(70,BACKWARD,0,200);
                 ball_counter++;
            }
            if (green_state == 7)            { // Recoleccion pelota plateada
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
                claw.sortCenter();
                nonBlockingDelay(1000);
                claw.sortLeft();
                nonBlockingDelay(1000);
                runTime(70,FORWARD,0,200);
                runTime(70,BACKWARD,0,200);
                ball_counter++;
            }
            if (ball_counter>=  3 && depositando==false)
            {
                claw.sortCenter();
                digitalWrite(RELAY, HIGH);
                Serial5.write(248);
                depositando=true;
                serialEvent5();
                robot.steer(speed, FORWARD, steer);  
                veces_deposit=0;
            }
            // Triangulo de deposito que ve la camara: 8 = rojo, 9 = verde.
            const int gs_dep = green_state;
            if(gs_dep == 9)
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    if (!retrocederHastaFinales(20))
                        break;

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
            if (gs_dep == 8)
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    if (!retrocederHastaFinales(20))
                        break;

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
            }

        } // end while (rutina == "rescate" && digitalRead(32) == 0)
           
        while (rutina == "evacuacion" && digitalRead(32) == 0)
        {
            enviarTelemetria();
            if (!evacuacion_straight)
            {
                green_state = 0;

                // Al terminar los depositos: separarse de la zona y girar -135 para empezar
                // a buscar pared.
                runDistance(30, FORWARD, 25);
                runAngle(30, FORWARD, -135);
                leer_ultrasonidos();

                if (front_distance != 0 && front_distance < 120) {
                    runAngle(30, FORWARD, 180);

                    if (!retrocederHastaFinales(20))
                        break;

                    runAngle(30, FORWARD, -90);

                }
                else
                {
                    while (rutina == "evacuacion" && digitalRead(32) == 0) {
                        robot.steer(30, FORWARD, 0);
                        memoriaParedEvacuacionPeriodica();   // para accionNegro()
                        procesarColorEvacuacion();
                        serialEvent5();
                    }
                }
                evacuacion_straight = true;
            }
            leer_ultrasonidos();
            memoriaParedEvacuacion();
                while (rutina == "evacuacion" && digitalRead(32) == 0) {
                    robot.steer(30, FORWARD, 0);
                    procesarColorEvacuacion();
                    if (rutina != "evacuacion") break;
                    serialEvent5();
                    leer_ultrasonidos();
                    memoriaParedEvacuacion();

                    // P3: lado izquierdo abierto (> 40 cm o sin eco): girar -90 y avanzar hasta ver
                    // una esquina de deposito.
                    if (left_distance > 40 || left_distance == 0)
                    {
                        DBG_PRINT("[EVAC] P3 BUSCAR left="); DBG_PRINT(left_distance);
                        DBG_PRINT(" front="); DBG_PRINTLN(front_distance);
                        runDistance(30, FORWARD, 8);
                        runAngle(30, FORWARD, -90);
                        while (rutina == "evacuacion" && digitalRead(32) == 0)
                        {
                            robot.steer(30, FORWARD, 0);
                            procesarColorEvacuacion();
                            serialEvent5();
                            leer_ultrasonidos();
                            memoriaParedEvacuacion();
                            // corta solo en esquina de deposito (gs 8/9, front <= 31), no en pared
                            if (debeEsquivar())
                                break;
                        }
                    }

                    // P1: esquina de deposito: la camara ve triangulo (gs 8/9) y front <= 34 cm ->
                    // maniobraEsquive().
                    if ((green_state == 8 || green_state == 9) && front_distance != 0 && front_distance <= 34)
                    {
                        DBG_PRINT("[EVAC] P1 ESQUINA gs="); DBG_PRINT(green_state);
                        DBG_PRINT(" front="); DBG_PRINTLN(front_distance);
                        maniobraEsquive();
                        green_state = 0;   // evita re-disparo inmediato con valor stale de camara
                        break;
                    }

                    // P2: pared frontal a <= 18 cm: girar 90.
                    if (front_distance != 0 && front_distance <= 18)
                    {
                        DBG_PRINT("[EVAC] P2 PARED front="); DBG_PRINTLN(front_distance);
                        runAngle(30, FORWARD, 90);
                        continue;
                    }


                }

        }
    } // end else (principal del loop)
} // end loop()
