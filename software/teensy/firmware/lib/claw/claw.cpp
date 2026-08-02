#include <Arduino.h>
#include <Servo.h>
#include "claw.h"

// =========================
// DFServo
// =========================

DFServo::DFServo(int pin, double minMicroseconds, double maxMicroseconds, double angularRange)
{
    _pin = pin;
    _angle = 0;
    _minMicroseconds = minMicroseconds;
    _maxMicroseconds = maxMicroseconds;
    _angularRange = angularRange;
}

void DFServo::begin()
{
    _servo.attach(_pin);
}

void DFServo::setAngle(double angle)
{
    _angle = angle;

    double microseconds = _minMicroseconds +
                          ((_maxMicroseconds - _minMicroseconds) / _angularRange * _angle);

    _servo.writeMicroseconds(microseconds);
}

double DFServo::getAngle()
{
    return _angle;
}

// =========================
// Claw
// =========================

Claw::Claw(DFServo *liftDFServo,
           DFServo *leftDFServo,
           DFServo *rightDFServo,
           DFServo *sortDFServo,
           DFServo *depositDFServo)
{
    _liftDFServo = liftDFServo;
    _leftDFServo = leftDFServo;
    _rightDFServo = rightDFServo;
    _sortDFServo = sortDFServo;
    _depositDFServo = depositDFServo;

    _lastAction = 0;
    _state = CL_IDLE;
    _stateStartedAt = 0;
    _concurrentRequested = false;
}

void Claw::begin()
{
    _liftDFServo->begin();
    _leftDFServo->begin();
    _rightDFServo->begin();
    _sortDFServo->begin();
    _depositDFServo->begin();

    reset();
}

bool Claw::available()
{
    return (millis() - _lastAction) > 1000;
}

// =========================
// Movimientos básicos
// =========================

void Claw::open(bool concurrent)
{
    _leftDFServo->setAngle(120);
    _rightDFServo->setAngle(180);

    if (!concurrent)
        _lastAction = millis();
}

void Claw::close(bool concurrent)
{
    _leftDFServo->setAngle(190);
    _rightDFServo->setAngle(85);

    if (!concurrent)
        _lastAction = millis();
}

void Claw::lift(bool concurrent)
{
    _liftDFServo->setAngle(190);

    if (!concurrent)
        _lastAction = millis();
}

void Claw::lower(bool concurrent)
{
    _liftDFServo->setAngle(48);

    if (!concurrent)
        _lastAction = millis();
}

// =========================
// Sort
// =========================

void Claw::sortLeft(bool concurrent)
{
    _sortDFServo->setAngle(170);

    if (!concurrent)
        _lastAction = millis();
}

void Claw::sortRight(bool concurrent)
{
    _sortDFServo->setAngle(90);

    if (!concurrent)
        _lastAction = millis();
}

void Claw::sortCenter(bool concurrent)
{
    _sortDFServo->setAngle(130); // Si mecánicamente queda mejor, probá 135

    if (!concurrent)
        _lastAction = millis();
}

// =========================
// Deposit
// =========================

void Claw::depositLeft(bool concurrent)
{
    _depositDFServo->setAngle(190);

    if (!concurrent)
        _lastAction = millis();
}

void Claw::depositCenter(bool concurrent)
{
    _depositDFServo->setAngle(130);

    if (!concurrent)
        _lastAction = millis();
}

void Claw::depositRight(bool concurrent)
{
    _depositDFServo->setAngle(85);

    if (!concurrent)
        _lastAction = millis();
}

// =========================
// Reset
// =========================

void Claw::reset(bool concurrent)
{
    lower(true);
    sortCenter(true);
    open(true);

    if (!concurrent)
        _lastAction = millis();
}

// =========================
// Secuencias no bloqueantes
// =========================

void Claw::pickupLeft(bool concurrent)
{
    if (_state == CL_IDLE)
    {
        _concurrentRequested = concurrent;
        _state = CL_PICKUP_LEFT_STEP1;
        _stateStartedAt = millis();
    }
}

void Claw::pickupRight(bool concurrent)
{
    if (_state == CL_IDLE)
    {
        _concurrentRequested = concurrent;
        _state = CL_PICKUP_RIGHT_STEP1;
        _stateStartedAt = millis();
    }
}

bool Claw::busy()
{
    return _state != CL_IDLE;
}

void Claw::update()
{
    const unsigned long STEP_DELAY = 500;
    unsigned long now = millis();

    switch (_state)
    {
    case CL_IDLE:
        break;

    case CL_PICKUP_LEFT_STEP1:
        close(true);
        _state = CL_PICKUP_LEFT_STEP2;
        _stateStartedAt = now;
        break;

    case CL_PICKUP_LEFT_STEP2:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            sortLeft(true);
            lift(true);

            _state = CL_PICKUP_LEFT_STEP3;
            _stateStartedAt = now;
        }
        break;

    case CL_PICKUP_LEFT_STEP3:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            open(true);

            _state = CL_PICKUP_LEFT_STEP4;
            _stateStartedAt = now;
        }
        break;

    case CL_PICKUP_LEFT_STEP4:
        _state = CL_IDLE;

        if (!_concurrentRequested)
            _lastAction = now;

        break;

    case CL_PICKUP_RIGHT_STEP1:
        close(true);
        _state = CL_PICKUP_RIGHT_STEP2;
        _stateStartedAt = now;
        break;

    case CL_PICKUP_RIGHT_STEP2:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            sortRight(true);
            lift(true);

            _state = CL_PICKUP_RIGHT_STEP3;
            _stateStartedAt = now;
        }
        break;

    case CL_PICKUP_RIGHT_STEP3:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            open(true);

            _state = CL_PICKUP_RIGHT_STEP4;
            _stateStartedAt = now;
        }
        break;

    case CL_PICKUP_RIGHT_STEP4:
        _state = CL_IDLE;

        if (!_concurrentRequested)
            _lastAction = now;

        break;
    }
}