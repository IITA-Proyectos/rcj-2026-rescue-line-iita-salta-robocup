// drivebase.h - Moto (una rueda FIT0441 con encoder y PID de velocidad) y DriveBase (4 ruedas).
// Base original: Heng Tenge.
#include <Arduino.h>
#include "PID.h"

#ifndef drivebase_h
#define drivebase_h


// FIX_LAZO_MOTOR: 1 = lazo de competencia (feedforward + integrador acotado + pisos de esfuerzo);
// 0 = lazo historico (integrador puro + toggle del pin de direccion).
// El encoder mide magnitud, no sentido: si el chasis arrastra la rueda, el integrador baja el PWM
// y el FIT0441 a PWM bajo hace COAST (suelta la rueda). Los pisos no lo dejan apagar el motor.
#ifndef FIX_LAZO_MOTOR
#define FIX_LAZO_MOTOR 1
#endif

// PWM de arranque: lo que hace falta para vencer la friccion estatica.
#define MOTO_KS   8.0
// PWM por RPM de consigna: ~215 de PWM para 159 RPM a 12 V. Provisorio (ensayo de escalones).
#define MOTO_KV   1.35
// Con consigna viva el esfuerzo total no baja de MOTO_PISO * feedforward. Es < 1 para que el
// integrador pueda recortar si MOTO_KV quedo alto.
#define MOTO_PISO 0.5
// Piso ABSOLUTO de PWM (sobre 255) con consigna viva: por debajo el FIT0441 suelta la rueda (coast).
// Hace falta aparte de MOTO_PISO, que es proporcional a la consigna: en la rueda interna de una
// curva cerrada (7,3 rpm) ese piso cae a 8,9, apenas sobre MOTO_KS. Provisorio: se mide en banco.
// No subirlo sobre el feedforward de curva (en 45 tapaba al lazo). El umbral COLAPSO_PWM del
// analizador se ajusta a este valor, nunca al reves.
#define MOTO_PWM_ANTICOAST 20.0
// Consigna de curva mas lenta contra la que se valida el piso anti-coast (static_assert de abajo).
// No se sincroniza sola con LINE_PIVOT_SPEED de main.cpp.
#define MOTO_RPM_CURVA_MIN 20.0
// Invariante: el piso anti-coast queda debajo del feedforward de la curva mas lenta; si no, tapa
// al lazo en toda curva.
static_assert(MOTO_PWM_ANTICOAST < MOTO_KS + MOTO_KV * MOTO_RPM_CURVA_MIN,
              "MOTO_PWM_ANTICOAST quedo por encima del feedforward de la curva "
              "mas lenta: el piso tapa al lazo en toda curva. Bajalo.");
// Por debajo de esta consigna se considera "parar" y se suelta (no hay freno).
#define MOTO_RPM_MIN 0.5

// Cadena del encoder, unica fuente del factor. Verificar en banco: 10 vueltas a mano de la rueda
// = TICKS_VUELTA*10 +/- 20 en fl_raw, en las cuatro.
#define TICKS_VUELTA   540UL              // 6 pulsos/vuelta x 2 flancos x 45
#define US_POR_RPM     (60000000UL / TICKS_VUELTA)   // rpm = US_POR_RPM / intervalo (us)

class Moto
{
public:
    Moto(int pwmPin, int dirPin, int encPin, const char* id);
    double getSpeed();
    double setSpeed(int dir, double rpm);
    void updatePulse();
    void resetPulseCount();
    double getPWM();
    void reset();
    const char* id; // "FL"/"FR"/"BL"/"BR": decide el signo de pulseCount en updatePulse()

public:
    volatile long pulseCount;
    // Veces que el lazo historico (FIX_LAZO_MOTOR=0) invirtio el pin de direccion por esfuerzo
    // bajo. Solo cuenta; con el lazo de competencia queda en 0.
    volatile unsigned long dirToggles = 0;

    // Flancos crudos del encoder, siempre suman: movimiento fisico sin depender de _dir.
    volatile unsigned long pulsesRaw = 0;

    // Esfuerzo que sale por el pin (0-255): feedforward + integrador + pisos. Con el lazo de
    // competencia _pwmVal es solo la parte integral.
    double _pwmTotal = 0;

    // Envolvente min/max de PWM y RPM desde el ultimo frame de telemetria (10 Hz), para no perder
    // transitorios de decenas de ms. La actualiza setSpeed() y la rearma resetEnvolvente().
    double _pwmMin = 0, _pwmMax = 0, _rpmMin = 0, _rpmMax = 0;
    bool   _envVirgen = true;
    void resetEnvolvente();
    int _pwmPin, _dirPin, _encPin;
    int _nAvg;
    int _dir;  // nivel del pin de direccion (0/1)
    double _rpm, _pwmVal, _realrpm, _begin, _end, _now;
    double _rpmlist[4] = {(double)US_POR_RPM, (double)US_POR_RPM,
                          (double)US_POR_RPM, (double)US_POR_RPM};
    double _kp = 0, _ki = 22, _kd = 0;
    PID _motoPID = PID(&_realrpm, &_pwmVal, &_rpm, _kp, _ki, _kd, DIRECT);
};

// Ancho de via EFECTIVO (cm) en omega = 2*vel*rot/b: incluye el patinaje del skid steer, por eso
// supera el ancho total del robot (17,69 cm). Se mide con radio_minimo.py (b = dv_encoder / gz,
// ~21,3 cm en pista); revalidar si cambian las ruedas o la superficie.
#define DRIVE_ANCHO_VIA_EFECTIVO 20.9

class DriveBase
{
public:
    DriveBase(Moto *fl, Moto *fr, Moto *bl, Moto *br);
    void steer(double speed, int direction, double rotation);
    // Pide un radio en cm: rot = b_eff / (2*R + b_eff); el radio no depende de la velocidad.
    // radius_cm <= 0 = girar en el lugar (rot = 1). `sign` > 0 gira a la izquierda.
    void steerRadius(double speed, int direction, double radius_cm, int sign);

    // Reparto por suma/resta: v_izq = base*(1+u), v_der = base*(1-u). A diferencia de steer()
    // (v_centro = vel*(1-rot), cero en rot = 1) el centro siempre avanza a `base`.
    // R = b_eff / (2*u); con u > 1 el lado interno va en reversa. Cada lado satura en 159.
    void steerSuma(double base, int direction, double u);
    // Como steer(), pero la delantera interna va a speed*frenoInterna, con signo respecto de la
    // marcha (1 = adelante, 0 = quieta, -1 = reversa). Las otras tres quedan igual que en steer().
    // Con 4 ruedas fijas el centro de giro no se impone por consigna: efecto dinamico, se barre.
    void steerFrenoDelantero(double speed, int direction, double rotation,
                             double frenoInterna);

    // Centinela: con este valor steerFrenoDelantero() reparte exactamente igual que steer().
    static constexpr double kFrenoComoSteer = 9.0;

    // Como steer(), pero escala la consigna de RPM de cada eje (frontScale/rearScale en 0..1).
    void steerAxleBias(double speed, int direction, double rotation,
                       double frontScale, double rearScale);
    void reset();

public:
    Moto *_fl, *_fr, *_bl, *_br;
    double _speed, _rotation, _leftspeed, _rightspeed, _leftdir, _rightdir;
    int _direction;
};

#endif
