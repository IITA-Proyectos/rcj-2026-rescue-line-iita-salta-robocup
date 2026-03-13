#include <Arduino.h>
#include <Servo.h>
#include "claw.h"

DFServo::DFServo(int pin, double minMicroseconds, double maxMicroseconds, double angularRange)
{
    _pin = pin;
    // Do not attach here to avoid global initialization issues
    // _servo.attach(_pin);
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
    _servo.writeMicroseconds(_minMicroseconds + ((_maxMicroseconds - _minMicroseconds) / _angularRange * _angle));
}

double DFServo::getAngle() { return _angle; }

Claw::Claw(DFServo *liftDFServo, DFServo *leftDFServo, DFServo *rightDFServo, DFServo *sortDFServo, DFServo *depositDFServo)
{
    this->_liftDFServo = liftDFServo;
    this->_leftDFServo = leftDFServo;
    this->_rightDFServo = rightDFServo;
    this->_sortDFServo = sortDFServo;
    this->_depositDFServo = depositDFServo;

    
    this->_state = CL_IDLE;
    this->_stateStartedAt = 0;
    this->_concurrentRequested = false;

}

void Claw::begin()
{
    // Attach all servos first
    _liftDFServo->begin();
    _leftDFServo->begin();
    _rightDFServo->begin();
    _sortDFServo->begin();
    _depositDFServo->begin();
    
    reset();  // Initialize claw positions after setup

}

bool Claw::available()
{
    return (millis() - _lastAction) > 1000;
}

void Claw::open(bool concurrent = false)
{
    _leftDFServo->setAngle(120);
    _rightDFServo->setAngle(180);
    if (!concurrent) _lastAction = millis();
}

void Claw::close(bool concurrent = false)
{
    _leftDFServo->setAngle(210);
    _rightDFServo->setAngle(90);
    if (!concurrent) _lastAction = millis();
}

void Claw::lift(bool concurrent = false)
{
    _liftDFServo->setAngle(210);
    if (!concurrent) _lastAction = millis();
}

void Claw::lower(bool concurrent = false)
{
    _liftDFServo->setAngle(75);
    if (!concurrent) _lastAction = millis();
}

void Claw::sortLeft(bool concurrent = false)
{
    _sortDFServo->setAngle(170);
    if (!concurrent) _lastAction = millis();
}

void Claw::sortRight(bool concurrent = false)
{
    _sortDFServo->setAngle(90);
    if (!concurrent) _lastAction = millis();
}

void Claw::depositLeft(bool concurrent = false)
{
    _depositDFServo->setAngle(190);
    if (!concurrent) _lastAction = millis();
}
void Claw::depositCenter(bool concurrent = false)
{
    _depositDFServo->setAngle(130);
    if (!concurrent) _lastAction = millis();
}

void Claw::depositRight(bool concurrent = false)
{
    _depositDFServo->setAngle(85);
    if (!concurrent) _lastAction = millis();
}

void Claw::reset(bool concurrent = false)
{
    this->lower();
    _sortDFServo->setAngle(135);
    this->open();
    if (!concurrent) _lastAction = millis();
}
// Non-blocking pickup: start sequences and advance via update()
void Claw::pickupLeft(bool concurrent = false)
{
    if (_state == CL_IDLE)
    {
        _concurrentRequested = concurrent;
        _state = CL_PICKUP_LEFT_STEP1;
        _stateStartedAt = millis();
    }
}

void Claw::pickupRight(bool concurrent = false)
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
    const unsigned long STEP_DELAY = 500; // ms between steps
    unsigned long now = millis();

    switch (_state)
    {
    case CL_IDLE:
        // nothing to do
        break;
    case CL_PICKUP_LEFT_STEP1:
        // step1: close
        this->close();
        _state = CL_PICKUP_LEFT_STEP2;
        _stateStartedAt = now;
        break;
    case CL_PICKUP_LEFT_STEP2:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            // step2: sort left + lift
            this->sortLeft();
            this->lift();
            _state = CL_PICKUP_LEFT_STEP3;
            _stateStartedAt = now;
        }
        break;
    case CL_PICKUP_LEFT_STEP3:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            // step3: open
            this->open();
            _state = CL_PICKUP_LEFT_STEP4;
            _stateStartedAt = now;
        }
        break;
    case CL_PICKUP_LEFT_STEP4:
        // finish
        if (now - _stateStartedAt >= 0)
        {
            _state = CL_IDLE;
            if (!_concurrentRequested)
                _lastAction = now;
        }
        break;
    case CL_PICKUP_RIGHT_STEP1:
        this->close();
        _state = CL_PICKUP_RIGHT_STEP2;
        _stateStartedAt = now;
        break;
    case CL_PICKUP_RIGHT_STEP2:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            this->sortRight();
            this->lift();
            _state = CL_PICKUP_RIGHT_STEP3;
            _stateStartedAt = now;
        }
        break;
    case CL_PICKUP_RIGHT_STEP3:
        if (now - _stateStartedAt >= STEP_DELAY)
        {
            this->open();
            _state = CL_PICKUP_RIGHT_STEP4;
            _stateStartedAt = now;
        }
        break;
    case CL_PICKUP_RIGHT_STEP4:
        if (now - _stateStartedAt >= 0)
        {
            _state = CL_IDLE;
            if (!_concurrentRequested)
                _lastAction = now;
        }
        break;
    }
}