/*
  drivebase.cpp - Library for controlling motors.
  Created by Heng Tenge, Jan 2, 2022.
  Extended: Pybricks-inspired API para Teensy 4.1
*/
#include <Arduino.h>
#include <string.h>
#include "drivebase.h"
#include "PID.h"
#include <math.h>

// ════════════════════════════════════════════════════════════
// MOTO — IDÉNTICO AL ORIGINAL, cero cambios de comportamiento
// ════════════════════════════════════════════════════════════

Moto::Moto(int pwmPin, int dirPin, int encPin, const char* id)
{
    pinMode(pwmPin, OUTPUT);
    _pwmPin = pwmPin;
    pinMode(dirPin, OUTPUT);
    _dirPin = dirPin;
    pinMode(encPin, INPUT_PULLUP);
    analogWriteFrequency(_pwmPin, 50000);
    _encPin = encPin;
    _motoPID.SetMode(AUTOMATIC);
    this->id = id;
}

double Moto::getSpeed()
{
    double _now = micros();
    if ((_now - _end) > 111111)
    {
        _realrpm = 0;
    }
    else
    {
        _rpmlist[3] = max(_end - _begin, _now - _end);
        _realrpm = (_rpmlist[0] + _rpmlist[1] + _rpmlist[2] + _rpmlist[3]) / 4;
        _realrpm = (_realrpm != 0) ? (111111.0 / _realrpm) : 0;
    }
    return _realrpm;
}

double Moto::setSpeed(int dir, double rpm)
{
    noInterrupts();
    _realrpm = this->getSpeed();
    interrupts();
    _rpm = rpm;
    if (_pwmVal < 10)
        _dir = !_dir;
    else
        _dir = dir;
    _motoPID.Compute();
    digitalWrite(_dirPin, _dir);
    analogWrite(_pwmPin, (int)(255 - _pwmVal));
    return _realrpm;
}

double Moto::getPWM() { return _pwmVal; }

void Moto::updatePulse()
{
    _begin = _end;
    _end   = micros();
    _rpmlist[0] = _rpmlist[1];
    _rpmlist[1] = _rpmlist[2];
    _rpmlist[2] = _rpmlist[3];
    _rpmlist[3] = _end - _begin;

    if (_dir == 0) {
        if (this->id != NULL &&
            (strcmp(this->id, "FL") == 0 ||
             strcmp(this->id, "BL") == 0))
            pulseCount++;
        else
            pulseCount--;
    }
    if (_dir == 1) {
        if (this->id != NULL &&
            (strcmp(this->id, "FL") == 0 ||
             strcmp(this->id, "BL") == 0))
            pulseCount--;
        else
            pulseCount++;
    }
}

void Moto::resetPulseCount() { pulseCount = 0; }
void Moto::reset()            { _motoPID.Reset(); }

// ════════════════════════════════════════════════════════════
// DRIVEBASE — Constructor
// ════════════════════════════════════════════════════════════

DriveBase::DriveBase(Moto *fl, Moto *fr, Moto *bl, Moto *br)
{
    this->_fl = fl;
    this->_fr = fr;
    this->_bl = bl;
    this->_br = br;
}

// ════════════════════════════════════════════════════════════
// API ORIGINAL — SIN CAMBIOS
// Reproducción EXACTA del original, incluyendo member variables
// ════════════════════════════════════════════════════════════

void DriveBase::steer(double speed, int direction, double rotation)
{
    _speed     = constrain(speed, 0, 159);
    _rotation  = constrain(rotation, -1, 1);
    _direction = direction;

    if (rotation >= 0)  // turn left, set right wheels as base speed
    {
        _rightspeed = _speed;
        _rightdir   = _direction;
        _leftdir    = _direction;
        _leftspeed  = _speed - (2 * rotation * _speed);
        if (_leftspeed < 0)
        {
            _leftdir   = !_leftdir;
            _leftspeed *= -1;
        }
        _fl->setSpeed(_leftdir,   _leftspeed);
        _bl->setSpeed(_leftdir,   _leftspeed);
        _fr->setSpeed(!_rightdir, _rightspeed);
        _br->setSpeed(!_rightdir, _rightspeed);
    }
    else
    {
        _leftspeed  = _speed;
        _leftdir    = _direction;
        _rightdir   = _direction;
        _rightspeed = _speed + (2 * rotation * _speed);
        if (_rightspeed < 0)
        {
            _rightdir   = !_rightdir;
            _rightspeed *= -1;
        }
        _fl->setSpeed(_leftdir,   _leftspeed);
        _bl->setSpeed(_leftdir,   _leftspeed);
        _fr->setSpeed(!_rightdir, _rightspeed);
        _br->setSpeed(!_rightdir, _rightspeed);
    }
}

void DriveBase::reset()
{
    _fl->reset();
    _fr->reset();
    _bl->reset();
    _br->reset();
}

// ════════════════════════════════════════════════════════════
// CONFIGURACIÓN
// ════════════════════════════════════════════════════════════

void DriveBase::setKinematics(float wheel_diameter_mm,
                               float axle_track_mm,
                               int   ticks_per_rev)
{
    _ticks_per_rev = ticks_per_rev;
    _axle_track_mm = axle_track_mm;
    _mm_per_tick   = (float)(M_PI * wheel_diameter_mm) /
                     (float)ticks_per_rev;
}

void DriveBase::setIMU(Adafruit_BNO055* imu) { _imu = imu; }

void DriveBase::setMaxSpeed(float s)     { _max_speed      = s; }
void DriveBase::setMaxAccel(float a)     { _max_accel      = a; }
void DriveBase::setMaxTurnRate(float r)  { _max_turn_rate  = r; }
void DriveBase::setMaxTurnAccel(float a) { _max_turn_accel = a; }

void DriveBase::setHeadingPID(float kp, float ki, float kd)
    { _kp_head = kp; _ki_head = ki; _kd_head = kd; }
void DriveBase::setDistancePID(float kp, float ki, float kd)
    { _kp_dist = kp; _ki_dist = ki; _kd_dist = kd; }
void DriveBase::setTurnPID(float kp, float ki, float kd)
    { _kp_turn = kp; _ki_turn = ki; _kd_turn = kd; }

void DriveBase::setStallThreshold(float ticks_threshold, float time_ms)
{
    _stall_ticks_threshold = ticks_threshold;
    _stall_time_ms         = time_ms;
}

// ════════════════════════════════════════════════════════════
// ODOMETRÍA
// Solo FL y FR — omniwheels atrás son pasivos (no traccionan)
// ════════════════════════════════════════════════════════════

void DriveBase::resetEncoders()
{
    _fl->resetPulseCount();
    _fr->resetPulseCount();
    _bl->resetPulseCount();
    _br->resetPulseCount();
}

long  DriveBase::getLeftTicks()  { return _fl->pulseCount; }
long  DriveBase::getRightTicks() { return _fr->pulseCount; }

float DriveBase::getDistanceMm()
{
    float avg = ((float)_fl->pulseCount +
                 (float)_fr->pulseCount) / 2.0f;
    return avg * _mm_per_tick;
}

float DriveBase::getHeadingDegFromEncoders()
{
    // yaw incremental: diferencia FR-FL
    // positivo = derecha (CW desde arriba), igual que BNO055
    float diff = (float)_fr->pulseCount - (float)_fl->pulseCount;
    float rad  = (diff * _mm_per_tick) / (_axle_track_mm / 2.0f);
    return rad * (180.0f / (float)M_PI);
}

// ════════════════════════════════════════════════════════════
// IMU helper
// ════════════════════════════════════════════════════════════

float DriveBase::_readIMU()
{
    if (_imu == nullptr) return 0.0f;
    sensors_event_t event;
    _imu->getEvent(&event);
    return event.orientation.x;   // yaw 0..360
}

// ════════════════════════════════════════════════════════════
// HELPERS PRIVADOS
// ════════════════════════════════════════════════════════════

// Perfil trapezoidal — igual que Pybricks internamente
// Retorna velocidad actualizada para este step
float DriveBase::_trapezoidalStep(float current_vel,
                                   float remaining,
                                   float max_vel,
                                   float accel,
                                   float dt_s)
{
    // velocidad necesaria para frenar a tiempo: v = sqrt(2*a*d)
    float vel_decel = sqrtf(2.0f * accel * fabsf(remaining));
    float target    = min(max_vel, vel_decel);
    target          = max(target, 0.0f);

    if (current_vel < target) {
        current_vel += accel * dt_s;
        if (current_vel > target) current_vel = target;
    } else if (current_vel > target) {
        current_vel -= accel * dt_s;
        if (current_vel < 0) current_vel = 0;
    }
    return constrain(current_vel, 0.0f, max_vel);
}

// Error angular normalizado [-180, 180]
float DriveBase::_angleError(float current_deg, float target_deg)
{
    float err = target_deg - current_deg;
    while (err >  180.0f) err -= 360.0f;
    while (err < -180.0f) err += 360.0f;
    return err;
}

// ─────────────────────────────────────────────────────────────
// _applyDifferential — convierte mm/s + rotación a steer()
//
// Verificación con fórmula real de steer():
//   rotation >= 0 (izquierda): leftSpeed  = speed - 2*rot*speed
//   rotation <  0 (derecha):   rightSpeed = speed + 2*rot*speed
//
// speed en RPM (0..159), turn_rot en [-1..1]
// ─────────────────────────────────────────────────────────────
void DriveBase::_applyDifferential(float speed_mm_s, float turn_rot)
{
    // circunferencia de rueda en mm
    float circ = _mm_per_tick * (float)_ticks_per_rev;  // ~188.5mm

    // convertir mm/s a RPM: RPM = (mm/s × 60) / circ
    double rpm = constrain(
        (double)(fabsf(speed_mm_s) * 60.0f) / (double)circ,
        0.0, 159.0
    );

    int dir = (speed_mm_s >= 0) ? 0 : 1;  // 0=FORWARD, 1=BACKWARD
    steer(rpm, dir, (double)constrain(turn_rot, -1.0f, 1.0f));
}

void DriveBase::_resetPIDState()
{
    _head_integral = 0; _head_prev_err = 0;
    _turn_integral = 0; _turn_prev_err = 0;
    _profile_vel   = 0;
}

void DriveBase::_startMotionCommon(MotionType type)
{
    _ticks_left_0    = _fl->pulseCount;
    _ticks_right_0   = _fr->pulseCount;
    _heading_0       = _readIMU();
    _resetPIDState();
    _state           = MS_RUNNING;
    _type            = type;
    _motion_start_ms = millis();
    _last_update_us  = micros();
    _stall_active    = false;
    _stall_check_ms  = millis();
    _stall_start_ms  = 0;
    _stall_last_ticks_l = _fl->pulseCount;
    _stall_last_ticks_r = _fr->pulseCount;
}

void DriveBase::_finishMotion()
{
    steer(0, 0, 0);
    _state = MS_FINISHED;
    _type  = MT_NONE;
}

// ─────────────────────────────────────────────────────────────
// _updateStraight
// Distancia por encoders FL+FR, corrección lateral por BNO055
// ─────────────────────────────────────────────────────────────
void DriveBase::_updateStraight(float dt_s)
{
    float ticks_l  = (float)(_fl->pulseCount - _ticks_left_0);
    float ticks_r  = (float)(_fr->pulseCount - _ticks_right_0);
    float dist_now = ((ticks_l + ticks_r) / 2.0f) * _mm_per_tick;
    float remaining = _target_dist - dist_now;

    // tolerancia 2mm
    if (fabsf(remaining) <= 2.0f ||
        (remaining < 0 && _target_dist > 0) ||
        (remaining > 0 && _target_dist < 0)) {
        _finishMotion();
        return;
    }

    _profile_vel = _trapezoidalStep(
        _profile_vel, remaining,
        fabsf(_cmd_speed), _max_accel, dt_s
    );

    // corrección de heading: mantener _heading_0
    float imu_now  = _readIMU();
    float head_err = _angleError(imu_now, _heading_0);

    // PID heading (P+D suficiente para ir recto)
    _head_integral += head_err * dt_s;
    float head_deriv = (dt_s > 0)
                       ? (head_err - _head_prev_err) / dt_s : 0;
    float head_corr  = _kp_head * head_err
                     + _ki_head * _head_integral
                     + _kd_head * head_deriv;
    _head_prev_err   = head_err;
    head_corr        = constrain(head_corr, -0.35f, 0.35f);

    float speed_signed = (_target_dist >= 0)
                         ? _profile_vel : -_profile_vel;
    _applyDifferential(speed_signed, head_corr);
}

// ─────────────────────────────────────────────────────────────
// _updateTurn — FIX APLICADO
//
// Bug anterior: steer(0, 0, rot) → speed=0 → no se mueve
// Fix: convertir deg/s del perfil a RPM real de rueda
//
// Cinemática del giro en el lugar:
//   velocidad tangencial de rueda = omega × (axle_track/2)
//   omega (rad/s) = profile_vel (deg/s) × π/180
//   RPM = (vel_tangencial × 60) / circunferencia
// ─────────────────────────────────────────────────────────────
void DriveBase::_updateTurn(float dt_s)
{
    float imu_now  = _readIMU();
    float err      = _angleError(imu_now, _heading_0 + _target_angle);

    // tolerancia 1.0°
    if (fabsf(err) <= 1.0f) {
        _finishMotion();
        return;
    }

    _profile_vel = _trapezoidalStep(
        _profile_vel, fabsf(err),
        fabsf(_cmd_turn_rate), _max_turn_accel, dt_s
    );

    // convertir deg/s → RPM de rueda
    // v_wheel = omega_rad_s × (axle_track/2)
    float omega_rad_s  = _profile_vel * (float)(M_PI / 180.0);
    float v_wheel_mm_s = omega_rad_s * (_axle_track_mm / 2.0f);
    float circ         = _mm_per_tick * (float)_ticks_per_rev;
    double turn_rpm    = constrain(
        (double)(v_wheel_mm_s * 60.0f) / (double)circ,
        0.0, 159.0
    );

    // err > 0 → hay que girar más a la derecha → rotation = -1
    // err < 0 → hay que girar más a la izquierda → rotation = +1
    double rot_dir = (err > 0) ? -1.0 : 1.0;

    // giro en el lugar: steer(rpm, FORWARD, ±1)
    steer((double)turn_rpm, 0, rot_dir);
}

// ─────────────────────────────────────────────────────────────
// _updateCurve — FIX APLICADO
//
// Bug anterior: rot = axle_track / (2*radius)  ← incorrecto
//
// Derivación correcta desde fórmula de steer():
//   rotation >= 0: leftSpeed = speed - 2*rot*speed
//   Para un arco de radio R (al centro del robot):
//     v_left  = v × (R - track/2) / R
//     v_right = v × (R + track/2) / R
//   En steer(): leftSpeed = speed - 2*rot*speed
//     → 1 - 2*rot = (R - track/2) / R
//     → rot = track / (2*R)   ... solo si track << R
//
//   Fórmula exacta que sí funciona con radios pequeños:
//     v_left / v_right = (R - t/2) / (R + t/2)
//     En steer(rot >= 0): leftSpeed = speed*(1 - 2*rot)
//     speed*(1-2*rot)/speed = (R-t/2)/(R+t/2)
//     1-2*rot = (R-t/2)/(R+t/2)
//     2*rot = 1 - (R-t/2)/(R+t/2) = t/(R+t/2)
//     rot = t / (2*R + t)
// ─────────────────────────────────────────────────────────────
void DriveBase::_updateCurve(float dt_s)
{
    float ticks_l  = (float)(_fl->pulseCount - _ticks_left_0);
    float ticks_r  = (float)(_fr->pulseCount - _ticks_right_0);
    float dist_avg = ((ticks_l + ticks_r) / 2.0f) * _mm_per_tick;

    // ángulo recorrido en grados
    float angle_now = (fabsf(_target_radius) > 0.1f)
        ? (dist_avg / fabsf(_target_radius)) * (180.0f / (float)M_PI)
        : 0;

    float remaining = _target_angle - angle_now;

    if (fabsf(remaining) <= 1.0f) {
        _finishMotion();
        return;
    }

    _profile_vel = _trapezoidalStep(
        _profile_vel, fabsf(remaining),
        fabsf(_cmd_speed), _max_accel, dt_s
    );

    // FIX: fórmula exacta de rotación
    // rot = track / (2*|R| + track)
    float rot = _axle_track_mm /
                (2.0f * fabsf(_target_radius) + _axle_track_mm);
    rot = constrain(rot, 0.0f, 0.99f);

    // signo según lado del arco
    if (_target_radius < 0) rot = -rot;   // arco izquierda
    if (_target_angle  < 0) rot = -rot;   // arco hacia atrás

    float speed_signed = (_target_angle >= 0)
                         ? _profile_vel : -_profile_vel;
    _applyDifferential(speed_signed, rot);
}

// ─────────────────────────────────────────────────────────────
// _updateStall — chequea cada 100ms
// ─────────────────────────────────────────────────────────────
void DriveBase::_updateStall()
{
    unsigned long now = millis();
    if (now - _stall_check_ms < 100) return;

    long dl = abs(_fl->pulseCount - _stall_last_ticks_l);
    long dr = abs(_fr->pulseCount - _stall_last_ticks_r);

    _stall_last_ticks_l = _fl->pulseCount;
    _stall_last_ticks_r = _fr->pulseCount;
    _stall_check_ms     = now;

    bool moving = (dl > (long)_stall_ticks_threshold ||
                   dr > (long)_stall_ticks_threshold);

    if (!moving) {
        if (_stall_start_ms == 0) _stall_start_ms = now;
        if (now - _stall_start_ms > (unsigned long)_stall_time_ms) {
            _stall_active = true;
            _state        = MS_STALLED;
        }
    } else {
        _stall_start_ms = 0;
        _stall_active   = false;
    }
}

// ════════════════════════════════════════════════════════════
// MOVIMIENTOS BLOQUEANTES
// Llaman a su versión no bloqueante y esperan con update()
// ════════════════════════════════════════════════════════════

void DriveBase::straight(float distance_mm, float speed_mm_s)
{
    startStraight(distance_mm, speed_mm_s);
    while (_state == MS_RUNNING) update();
}

void DriveBase::turn(float angle_deg, float turn_rate_deg_s)
{
    startTurn(angle_deg, turn_rate_deg_s);
    while (_state == MS_RUNNING) update();
}

void DriveBase::curve(float radius_mm, float angle_deg,
                       float speed_mm_s)
{
    startCurve(radius_mm, angle_deg, speed_mm_s);
    while (_state == MS_RUNNING) update();
}

void DriveBase::drive(float speed_mm_s, float turn_rate_deg_s)
{
    // comando continuo — equivalente a Pybricks drive()
    float rot = constrain(
        turn_rate_deg_s / _max_turn_rate, -1.0f, 1.0f
    );
    _applyDifferential(speed_mm_s, rot);
    _state = MS_RUNNING;
    _type  = MT_DRIVE;
}

void DriveBase::stop(StopMode mode)
{
    steer(0, 0, 0);
    _state     = MS_IDLE;
    _type      = MT_NONE;
    _stop_mode = mode;
}

// ════════════════════════════════════════════════════════════
// MOVIMIENTOS NO BLOQUEANTES
// ════════════════════════════════════════════════════════════

void DriveBase::startStraight(float distance_mm, float speed_mm_s)
{
    _target_dist = distance_mm;
    _cmd_speed   = (speed_mm_s < 0) ? _max_speed
                                     : constrain(speed_mm_s, 0, _max_speed);
    _startMotionCommon(MT_STRAIGHT);
}

void DriveBase::startTurn(float angle_deg, float turn_rate_deg_s)
{
    _target_angle  = angle_deg;
    _cmd_turn_rate = (turn_rate_deg_s < 0) ? _max_turn_rate
                     : constrain(turn_rate_deg_s, 0, _max_turn_rate);
    _startMotionCommon(MT_TURN);
}

void DriveBase::startCurve(float radius_mm, float angle_deg,
                            float speed_mm_s)
{
    if (fabsf(radius_mm) < 1.0f) return;  // radio 0 → usar turn()
    _target_radius = radius_mm;
    _target_angle  = angle_deg;
    _cmd_speed     = (speed_mm_s < 0) ? _max_speed
                     : constrain(speed_mm_s, 0, _max_speed);
    _startMotionCommon(MT_CURVE);
}

// ─────────────────────────────────────────────────────────────
// update() — CORAZÓN DEL SISTEMA NO BLOQUEANTE
// Llamar en cada loop(). Si no hay movimiento activo, retorna
// inmediatamente sin costo (~1 µs en Teensy 4.1 a 600 MHz).
// ─────────────────────────────────────────────────────────────
void DriveBase::update()
{
    if (_state != MS_RUNNING) return;

    unsigned long now_us = micros();
    float dt_s = (float)(now_us - _last_update_us) / 1e6f;
    _last_update_us = now_us;
    dt_s = constrain(dt_s, 0.0001f, 0.05f);

    // timeout global
    if (millis() - _motion_start_ms > _motion_timeout_ms) {
        steer(0, 0, 0);
        _state = MS_TIMEOUT;
        return;
    }

    // stall detection
    _updateStall();
    if (_state == MS_STALLED) {
        steer(0, 0, 0);
        return;
    }

    switch (_type) {
        case MT_STRAIGHT: _updateStraight(dt_s); break;
        case MT_TURN:     _updateTurn(dt_s);     break;
        case MT_CURVE:    _updateCurve(dt_s);    break;
        case MT_DRIVE:    /* continuo */          break;
        default:                                  break;
    }
}

bool DriveBase::isBusy() { return (_state == MS_RUNNING); }

void DriveBase::cancelMotion()
{
    steer(0, 0, 0);
    _state = MS_IDLE;
    _type  = MT_NONE;
    _resetPIDState();
}

// ════════════════════════════════════════════════════════════
// DIAGNÓSTICO Y SEGURIDAD
// ════════════════════════════════════════════════════════════

MotionState DriveBase::getMotionState() { return _state; }

Telemetry DriveBase::getTelemetry()
{
    Telemetry t;
    t.ticks_left      = _fl->pulseCount;
    t.ticks_right     = _fr->pulseCount;
    t.distance_mm     = getDistanceMm();
    t.heading_enc_deg = getHeadingDegFromEncoders();
    t.heading_imu_deg = _readIMU();

    if (_type == MT_TURN) {
        t.target = _heading_0 + _target_angle;
        t.error  = _angleError(_readIMU(), t.target);
    } else {
        float dist_from_start =
            ((float)(_fl->pulseCount - _ticks_left_0) +
             (float)(_fr->pulseCount - _ticks_right_0))
            / 2.0f * _mm_per_tick;
        t.target = _target_dist;
        t.error  = _target_dist - dist_from_start;
    }
    t.speed_cmd = _profile_vel;
    t.state     = _state;
    return t;
}

bool DriveBase::isStalled() { return _stall_active; }

void DriveBase::emergencyStop()
{
    steer(0, 0, 0);
    _state = MS_ERROR;
    _type  = MT_NONE;
    _resetPIDState();
}