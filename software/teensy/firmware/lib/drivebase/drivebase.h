/*
  drivebase.h - Library for controlling motors.
  Created by Heng Tenge, Jan 2, 2022.
*/
#include <Arduino.h>
#include "PID.h"

#ifndef drivebase_h
#define drivebase_h

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
    const char* id; // Identificador del motor

public:
    long pulseCount; 
    int _pwmPin, _dirPin, _encPin;
    int _nAvg; // samples to take for speed computation
    int _dir;  // direction of rotation for setSpeed
    double _rpm, _pwmVal, _realrpm, _begin, _end, _now;
    double _rpmlist[4] = {111111, 111111, 111111, 111111};
    double _kp = 0, _ki = 22, _kd = 0;
    PID _motoPID = PID(&_realrpm, &_pwmVal, &_rpm, _kp, _ki, _kd, DIRECT);
};

class DriveBase
{
public:
    DriveBase(Moto *fl, Moto *fr, Moto *bl, Moto *br);
    void steer(double speed, int direction, double rotation);
    void reset();

public:
    Moto *_fl, *_fr, *_bl, *_br;
    double _speed, _rotation, _leftspeed, _rightspeed, _leftdir, _rightdir;
    int _direction;
};

#endif