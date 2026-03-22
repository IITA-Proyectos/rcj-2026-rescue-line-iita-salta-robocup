/*
  drivebase.h - Library for controlling motors.
  Created by Heng Tenge, Jan 2, 2022.
  Extended: Pybricks-inspired API para Teensy 4.1
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
    volatile long pulseCount;               // long, igual que original
    int    _pwmPin, _dirPin, _encPin;
    int    _nAvg;
    int    _dir;
    double _rpm, _pwmVal, _realrpm, _begin, _end, _now;
    double _rpmlist[4] = {111111, 111111, 111111, 111111};
    double _kp = 0, _ki = 22, _kd = 0;     // gains originales
    PID    _motoPID = PID(&_realrpm, &_pwmVal, &_rpm,
                          _kp, _ki, _kd, DIRECT);
};

// ════════════════════════════════════════════════════════════
// ENUMS Y STRUCTS NUEVOS — no rompen nada existente
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

    // ── CONFIGURACIÓN NUEVA ──────────────────────────────────
    // ticks_per_rev: usar 540 con CHANGE (6×45:1×2 flancos)
    void setKinematics(float wheel_diameter_mm,
                       float axle_track_mm,
                       int   ticks_per_rev);
    void setIMU(Adafruit_BNO055* imu);
    void setMaxSpeed(float speed_mm_s);
    void setMaxAccel(float accel_mm_s2);
    void setMaxTurnRate(float deg_s);
    void setMaxTurnAccel(float deg_s2);
    void setHeadingPID(float kp, float ki, float kd);
    void setDistancePID(float kp, float ki, float kd);
    void setTurnPID(float kp, float ki, float kd);
    void setStallThreshold(float ticks_threshold, float time_ms);

    // ── ODOMETRÍA NUEVA ──────────────────────────────────────
    void    resetEncoders();
    long    getLeftTicks();
    long    getRightTicks();
    float   getDistanceMm();
    float   getHeadingDegFromEncoders();

    // ── MOVIMIENTOS BLOQUEANTES (igual que Pybricks) ──────────
    // Signos: distancia+/velocidad+ = adelante
    //         angulo+ = derecha (CW desde arriba)
    //         angulo- = izquierda
    void straight(float distance_mm,    float speed_mm_s = -1);
    void turn(float angle_deg,          float turn_rate_deg_s = -1);
    void curve(float radius_mm, float angle_deg,
               float speed_mm_s = -1);
    void drive(float speed_mm_s, float turn_rate_deg_s);
    void stop(StopMode mode = COAST);

    // ── MOVIMIENTOS NO BLOQUEANTES ────────────────────────────
    // Ejemplo de uso:
    //   robot.startStraight(500);
    //   while (robot.isBusy()) {
    //       serialEvent5();       // serial vivo
    //       leer_ultrasonidos();  // sensores vivos
    //       if (cond) robot.cancelMotion();
    //   }
    void startStraight(float distance_mm, float speed_mm_s = -1);
    void startTurn(float angle_deg,       float turn_rate_deg_s = -1);
    void startCurve(float radius_mm, float angle_deg,
                    float speed_mm_s = -1);
    void update();        // llamar en CADA loop() — sin costo si IDLE
    bool isBusy();
    void cancelMotion();

    // ── DIAGNÓSTICO ───────────────────────────────────────────
    MotionState getMotionState();
    Telemetry   getTelemetry();
    bool        isStalled();
    void        emergencyStop();

public:
    // ── MEMBER VARIABLES ORIGINALES — SIN CAMBIOS ────────────
    // Mantenidas public para compatibilidad con código existente
    Moto*  _fl;
    Moto*  _fr;
    Moto*  _bl;
    Moto*  _br;
    double _speed, _rotation, _leftspeed, _rightspeed;
    double _leftdir, _rightdir;
    int    _direction;

private:
    // ── NUEVAS — solo para el nuevo API ──────────────────────
    Adafruit_BNO055* _imu = nullptr;
    float _readIMU();

    // Cinemática (setKinematics() las sobreescribe)
    // π × 60mm / 540 ticks = 0.349 mm/tick
    float _mm_per_tick   = 0.349f;
    float _axle_track_mm = 172.5f;
    int   _ticks_per_rev = 540;

    // Límites de movimiento
    float _max_speed      = 200.0f;   // mm/s
    float _max_accel      = 400.0f;   // mm/s²
    float _max_turn_rate  = 180.0f;   // deg/s
    float _max_turn_accel = 360.0f;   // deg/s²

    // PID gains para funciones nuevas
    float _kp_head = 0.03f,  _ki_head = 0.0f,  _kd_head = 0.003f;
    float _kp_dist = 2.0f,   _ki_dist = 0.0f,  _kd_dist = 0.05f;
    float _kp_turn = 3.0f,   _ki_turn = 0.0f,  _kd_turn = 0.08f;

    // Máquina de estados
    MotionState _state     = MS_IDLE;
    MotionType  _type      = MT_NONE;
    StopMode    _stop_mode = COAST;

    // Parámetros del movimiento activo
    float _target_dist   = 0;
    float _target_angle  = 0;
    float _target_radius = 0;
    float _cmd_speed     = 0;
    float _cmd_turn_rate = 0;

    // Perfil trapezoidal
    float         _profile_vel      = 0;
    unsigned long _last_update_us   = 0;
    unsigned long _motion_start_ms  = 0;
    unsigned long _motion_timeout_ms = 12000;

    // Snapshot al inicio del movimiento
    long  _ticks_left_0  = 0;
    long  _ticks_right_0 = 0;
    float _heading_0     = 0;

    // PID acumuladores
    float _head_integral = 0, _head_prev_err = 0;
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