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
    // Do not call reset() in constructor to avoid global initialization issues
    // this->reset();  // Moved to begin()
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

void Claw::pickupLeft(bool concurrent = false)
{
    this->close();
    delay(500);
    this->sortLeft();
    this->lift();
    delay(500);
    this->open();
    if (!concurrent) _lastAction = millis();
}

void Claw::pickupRight(bool concurrent = false)
{
    this->close();
    delay(500);
    this->sortRight();
    this->lift();
    delay(500);
    this->open();
    if (!concurrent) _lastAction = millis();
}