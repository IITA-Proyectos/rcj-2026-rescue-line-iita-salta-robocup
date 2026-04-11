/*
  drivebase.h - Library for controlling motors.
  Created by Heng Tenge, Jan 2, 2022.
  Extended: Pybricks-inspired API para Teensy 4.1

  FIXES aplicados:
    1. turn() fallback a encoders si no hay IMU
    2. drive() inicializa _motion_start_ms y _last_update_us
    3. curve() unidades consistentes (grados, no mm/s²)
    4. getHeadingDegFromEncoders() fórmula corregida
    5. Signo rotación curve() corregido
    6. Signo corrección heading en straight() corregido
    + setDistancePID/setTurnPID conectados
    + stop(BRAKE/HOLD) documentado
    + startCurve(radius≈0) limpia estado
    + getTelemetry() corregido para MT_DRIVE
*/
#include <Arduino.h>
#include "PID.h"
#include <Adafruit_BNO055.h>
#include <Adafruit_Sensor.h>

#ifndef drivebase_h
#define drivebase_h

// ════════════════════════════════════════════════════════════
// MOTO — IDÉNTICO AL ORIGINAL, cero cambios
// ════════════════════════════════════════════════════════════
class Moto
{
public:
    Moto(int pwmPin, int dirPin, int encPin, const char* id);
    double getSpeed();
    double setSpeed(int dir, double rpm);
    void   updatePulse();
    void   resetPulseCount();
    double getPWM();
    void   reset();
    const char* id;

public:
    volatile long pulseCount;
    int    _pwmPin, _dirPin, _encPin;
    int    _nAvg;
    int    _dir;
    double _rpm, _pwmVal, _realrpm, _begin, _end, _now;
    double _rpmlist[4] = {111111, 111111, 111111, 111111};
    double _kp = 0, _ki = 22, _kd = 0;
    PID    _motoPID = PID(&_realrpm, &_pwmVal, &_rpm,
                          _kp, _ki, _kd, DIRECT);
};

// ════════════════════════════════════════════════════════════
// ENUMS Y STRUCTS
// ════════════════════════════════════════════════════════════
enum StopMode    { COAST, BRAKE, HOLD };
enum MotionState { MS_IDLE, MS_RUNNING, MS_FINISHED,
                   MS_STALLED, MS_TIMEOUT, MS_ERROR };
enum MotionType  { MT_NONE, MT_STRAIGHT, MT_TURN,
                   MT_CURVE, MT_DRIVE };

struct Telemetry {
    long    ticks_left;
    long    ticks_right;
    float   distance_mm;
    float   heading_enc_deg;
    float   heading_imu_deg;
    float   target;
    float   error;
    float   speed_cmd;
    MotionState state;
};

// ════════════════════════════════════════════════════════════
// DRIVEBASE
// ════════════════════════════════════════════════════════════
class DriveBase
{
public:
    // ── CONSTRUCTOR — idéntico al original ───────────────────
    DriveBase(Moto *fl, Moto *fr, Moto *bl, Moto *br);

    // ── API ORIGINAL — SIN CAMBIOS ───────────────────────────
    void steer(double speed, int direction, double rotation);
    void reset();

    // ── CONFIGURACIÓN ────────────────────────────────────────
    // ticks_per_rev: 540 con CHANGE (6×45:1×2 flancos)
    void setKinematics(float wheel_diameter_mm,
                       float axle_track_mm,
                       int   ticks_per_rev);

    // IMU opcional.
    // - straight(): usa IMU si disponible, encoders si no
    // - turn():     usa IMU si disponible, encoders si no
    // Siempre llamar setIMU(&bno) en setup() para mejor precisión
    void setIMU(Adafruit_BNO055* imu);

    void setMaxSpeed(float speed_mm_s);       // default 200 mm/s
    void setMaxAccel(float accel_mm_s2);      // default 400 mm/s²
    void setMaxTurnRate(float deg_s);         // default 180 deg/s
    void setMaxTurnAccel(float deg_s2);       // default 360 deg/s²

    // PID heading: corrección lateral en straight()
    void setHeadingPID(float kp, float ki, float kd);

    // PID distancia: corrección de distancia en straight()
    // kp/ki/kd afectan la corrección proporcional del perfil
    void setDistancePID(float kp, float ki, float kd);

    // PID turn: corrección angular en turn()
    // kp/ki/kd afectan la ganancia del controlador de ángulo
    void setTurnPID(float kp, float ki, float kd);

    // Detección de traba: mínimo ticks_threshold ticks
    // en time_ms ms para no considerarse stalled
    void setStallThreshold(float ticks_threshold, float time_ms);

    // ── ODOMETRÍA ────────────────────────────────────────────
    void    resetEncoders();
    long    getLeftTicks();
    long    getRightTicks();
    float   getDistanceMm();

    // Heading incremental por diferencia de ticks FL/FR
    // FIX #4: fórmula corregida dθ = diff_mm / axle_track
    float   getHeadingDegFromEncoders();

    // ── MOVIMIENTOS BLOQUEANTES ───────────────────────────────
    // Convenio de signos (igual que Pybricks):
    //   distancia+ = adelante,  distancia- = atrás
    //   ángulo+    = derecha (CW desde arriba)
    //   ángulo-    = izquierda
    //   radio+     = arco a la derecha
    //   radio-     = arco a la izquierda
    void straight(float distance_mm,    float speed_mm_s = -1);
    void turn(float angle_deg,          float turn_rate_deg_s = -1);
    void curve(float radius_mm, float angle_deg,
               float speed_mm_s = -1);

    // drive() continuo — no termina solo, llamar stop()
    // FIX #2: ahora inicializa timers correctamente
    void drive(float speed_mm_s, float turn_rate_deg_s);
    void setMotionTimeout(unsigned long ms) { _motion_timeout_ms = ms; }

    // stop() — COAST: rueda libre
    //          BRAKE: freno activo (steer(0,0,0))
    //          HOLD:  mismo que BRAKE (hardware no soporta hold)
    void stop(StopMode mode = COAST);

    // ── MOVIMIENTOS NO BLOQUEANTES ────────────────────────────
    // Uso:
    //   robot.startStraight(500);
    //   while (robot.isBusy()) {
    //       serialEvent5();
    //       leer_ultrasonidos();
    //       if (cond) robot.cancelMotion();
    //   }
    void startStraight(float distance_mm, float speed_mm_s = -1);
    void startTurn(float angle_deg,       float turn_rate_deg_s = -1);
    void startCurve(float radius_mm, float angle_deg,
                    float speed_mm_s = -1);
    void update();
    bool isBusy();
    void cancelMotion();

    // ── DIAGNÓSTICO ───────────────────────────────────────────
    MotionState getMotionState();
    Telemetry   getTelemetry();
    bool        isStalled();
    void        emergencyStop();

public:
    // ── MEMBER VARIABLES ORIGINALES — SIN CAMBIOS ────────────
    Moto*  _fl;
    Moto*  _fr;
    Moto*  _bl;
    Moto*  _br;
    double _speed, _rotation, _leftspeed, _rightspeed;
    double _leftdir, _rightdir;
    int    _direction;

private:
    // ── NUEVAS ───────────────────────────────────────────────
    Adafruit_BNO055* _imu = nullptr;

    // FIX #1: dos fuentes de heading con fallback
    float _readIMU();                    // retorna yaw IMU, -1 si no hay
    float _readHeading();                // IMU si disponible, encoders si no
    float _headingAtMotionStart = 0;     // snapshot inicio movimiento

    // Cinemática
    float _mm_per_tick   = 0.349f;       // π×60/540
    float _axle_track_mm = 172.5f;
    int   _ticks_per_rev = 540;

    // Límites
    float _max_speed      = 200.0f;
    float _max_accel      = 400.0f;
    float _max_turn_rate  = 180.0f;
    float _max_turn_accel = 360.0f;

    // PID gains — todos conectados a su función
    float _kp_head = 0.03f,  _ki_head = 0.0f, _kd_head = 0.003f;
    float _kp_dist = 1.0f,   _ki_dist = 0.0f, _kd_dist = 0.05f;
    float _kp_turn = 3.0f,   _ki_turn = 0.0f, _kd_turn = 0.08f;

    // Máquina de estados
    MotionState _state     = MS_IDLE;
    MotionType  _type      = MT_NONE;

    // Parámetros del movimiento activo
    float _target_dist   = 0;
    float _target_angle  = 0;
    float _target_radius = 0;
    float _cmd_speed     = 0;
    float _cmd_turn_rate = 0;

    // Perfil trapezoidal
    float         _profile_vel       = 0;
    unsigned long _last_update_us    = 0;
    unsigned long _motion_start_ms   = 0;
    unsigned long _motion_timeout_ms = 12000;

    // Snapshot inicio movimiento
    long  _ticks_left_0  = 0;
    long  _ticks_right_0 = 0;
    float _heading_0     = 0;

    // PID acumuladores
    float _head_integral = 0, _head_prev_err = 0;
    float _dist_integral = 0, _dist_prev_err = 0;
    float _turn_integral = 0, _turn_prev_err = 0;

    // Stall detection
    float         _stall_ticks_threshold = 2.0f;
    float         _stall_time_ms         = 500.0f;
    long          _stall_last_ticks_l    = 0;
    long          _stall_last_ticks_r    = 0;
    unsigned long _stall_check_ms        = 0;
    unsigned long _stall_start_ms        = 0;
    bool          _stall_active          = false;

    // Helpers privados
    void  _startMotionCommon(MotionType type);
    void  _finishMotion();
    float _trapezoidalStep(float current_vel, float remaining,
                            float max_vel, float accel, float dt_s);
    float _angleError(float current_deg, float target_deg);
    void  _applyDifferential(float speed_mm_s, float turn_rot);
    void  _updateStraight(float dt_s);
    void  _updateTurn(float dt_s);
    void  _updateCurve(float dt_s);
    void  _updateStall();
    void  _resetPIDState();
};

#endif