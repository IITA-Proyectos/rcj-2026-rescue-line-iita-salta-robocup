/*
  drivebase.cpp - Library for controlling motors.
*/
#include <Arduino.h>
#include "drivebase.h"
#include "PID.h"
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

double Moto::getPWM()
{
    return _pwmVal;
}

void Moto::updatePulse()
{
    _begin = _end;
    _end = micros();
    _rpmlist[0] = _rpmlist[1];
    _rpmlist[1] = _rpmlist[2];
    _rpmlist[2] = _rpmlist[3];
    _rpmlist[3] = _end - _begin;
    if (_dir== 0){
        if (this->id == "FL" || this->id == "BL" ){
            pulseCount ++;
        }
        else{
            pulseCount --;
        }
       
    }
    if (_dir == 1){
        if (this->id == "FL" || this->id == "BL" ){
            pulseCount --;
        }
        else{
            pulseCount ++;
        }
    }
    /*
    Serial.print("Motor "); 
        Serial.print(id); 
        Serial.print(": ");
        Serial.println(pulseCount);
    */
    
}

void Moto::resetPulseCount()
{
    pulseCount = 0;
}

void Moto::reset() {
    _motoPID.Reset();
}

DriveBase::DriveBase(Moto *fl, Moto *fr, Moto *bl, Moto *br)
{
    this->_fl = fl;
    this->_fr = fr;
    this->_bl = bl;
    this->_br = br;
}

void DriveBase::steer(double speed, int direction, double rotation)
{
    _speed = constrain(speed, 0, 159);
    _rotation = constrain(rotation, -1, 1);
    _direction = direction;
    if (rotation >= 0)  // turn left, set right wheels as base speed
    {
        _rightspeed = _speed;
        _rightdir = _direction;
        _leftdir = _direction;
        _leftspeed = _speed - (2 * rotation * _speed);
        if (_leftspeed < 0)
        {
            _leftdir = !_leftdir;
            _leftspeed *= -1;
        }
        _fl->setSpeed(_leftdir, _leftspeed);
        _bl->setSpeed(_leftdir, _leftspeed);
        // analogWrite(35, 255 - _bl->getPWM());
        // digitalWrite(34, _leftdir);
        _fr->setSpeed(!_rightdir, _rightspeed);
        _br->setSpeed(!_rightdir, _rightspeed);
        // analogWrite(30, 255 - _br->getPWM());
        // digitalWrite(28, !_rightdir);
    }
    else
    {
        _leftspeed = _speed;
        _leftdir = _direction;
        _rightdir = _direction;
        _rightspeed = _speed + (2 * rotation * _speed);
        if (_rightspeed < 0)
        {
            _rightdir = !_rightdir;
            _rightspeed *= -1;
        }
        _fl->setSpeed(_leftdir, _leftspeed);
        _bl->setSpeed(_leftdir, _leftspeed);
        // analogWrite(35, 255 - _bl->getPWM());
        // digitalWrite(34, _leftdir);
        _fr->setSpeed(!_rightdir, _rightspeed);
        _br->setSpeed(!_rightdir, _rightspeed);
        // analogWrite(30, 255 - _br->getPWM());
        // digitalWrite(28, !_rightdir);
    }
}

void DriveBase::reset(){
    _fl->reset();
    _fr->reset();
    _bl->reset();
    _br->reset();
}