// drivebase.cpp - Moto y DriveBase (ver drivebase.h).
#include <Arduino.h>
#include <string.h>
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
    pulseCount = 0;
    _motoPID.SetMode(AUTOMATIC);
    this->id = id;
}


double Moto::getSpeed()
{
    double _now = micros();
    if ((_now - _end) > (double)US_POR_RPM)
    {
        _realrpm = 0;
    }
    else
    {
        _rpmlist[3] = max(_end - _begin, _now - _end);
        _realrpm = (_rpmlist[0] + _rpmlist[1] + _rpmlist[2] + _rpmlist[3]) / 4;
        _realrpm = (_realrpm != 0) ? ((double)US_POR_RPM / _realrpm) : 0;
    }
    return _realrpm;
}

double Moto::setSpeed(int dir, double rpm)
{
    noInterrupts();
    _realrpm = this->getSpeed();
    interrupts();
    _rpm = rpm;

#if FIX_LAZO_MOTOR

    // 1. El sentido es siempre el pedido; al invertir se descarta el integrador.
    if (dir != _dir)
    {
        _motoPID.Reset();
        _envVirgen = true;
    }
    _dir = dir;

    // Consigna ~0 = apagar ya. PID::Reset() no toca _pwmVal y Compute() corre cada 20 ms: sin
    // limpiarlo a mano se seguiria aplicando la correccion anterior.
    if (rpm <= MOTO_RPM_MIN)
    {
        _motoPID.Reset();
        _pwmVal = 0;
        _pwmTotal = 0;
        _dir = dir;
        if (_envVirgen) { _pwmMin = _pwmMax = 0; _rpmMin = _rpmMax = _realrpm; _envVirgen = false; }
        else { if (_pwmMin > 0) _pwmMin = 0;
               if (_realrpm < _rpmMin) _rpmMin = _realrpm;
               if (_realrpm > _rpmMax) _rpmMax = _realrpm; }
        digitalWrite(_dirPin, _dir);
        analogWrite(_pwmPin, 255);   // FIT0441: 255 = quieto (y es COAST, no freno)
        return _realrpm;
    }

    // 2. Feedforward: el esfuerzo base sale del comando, no de la medicion.
    double ff = MOTO_KS + MOTO_KV * rpm;

    // 3. Anti-windup: el integrador se acota a [ff*PISO - ff, 255 - ff], asi el total no baja de
    //    ff*PISO con consigna viva (no puede apagar el motor) ni pasa de 255.
    _motoPID.SetOutputLimits(ff * MOTO_PISO - ff, 255.0 - ff);

    // 4. El PID (solo integral) corrige sobre el feedforward.
    _motoPID.Compute();
    _pwmTotal = constrain(ff + _pwmVal, 0.0, 255.0);

    // 5. Piso absoluto del actuador, aparte del anti-windup: por debajo de MOTO_PWM_ANTICOAST el
    //    FIT0441 suelta la rueda, y el piso proporcional se desvanece con consigna chica.
    if (_pwmTotal < MOTO_PWM_ANTICOAST) _pwmTotal = MOTO_PWM_ANTICOAST;

#else   // lazo historico (FIX_LAZO_MOTOR=0)

    if (_pwmVal < 10)
    {
        _dir = !_dir;
        dirToggles++;
    }
    else
        _dir = dir;
    _motoPID.Compute();
    _pwmTotal = _pwmVal;

#endif

    // Envolvente min/max para la telemetria: todas las llamadas de control pasan por aca.
    if (_envVirgen)
    {
        _pwmMin = _pwmMax = _pwmTotal;
        _rpmMin = _rpmMax = _realrpm;
        _envVirgen = false;
    }
    else
    {
        if (_pwmTotal < _pwmMin) _pwmMin = _pwmTotal;
        if (_pwmTotal > _pwmMax) _pwmMax = _pwmTotal;
        if (_realrpm < _rpmMin) _rpmMin = _realrpm;
        if (_realrpm > _rpmMax) _rpmMax = _realrpm;
    }

    digitalWrite(_dirPin, _dir);
    analogWrite(_pwmPin, (int)(255 - _pwmTotal));
    return _realrpm;
}

double Moto::getPWM()
{
    return _pwmTotal;   // el esfuerzo que REALMENTE sale por el pin
}

void Moto::updatePulse()
{
    pulsesRaw++;   // crudo, sin signo: la unica medida de movimiento fisico
    _begin = _end;
    _end = micros();
    _rpmlist[0] = _rpmlist[1];
    _rpmlist[1] = _rpmlist[2];
    _rpmlist[2] = _rpmlist[3];
    _rpmlist[3] = _end - _begin;
    if (_dir== 0){
        if (this->id != NULL && (strcmp(this->id, "FL") == 0 || strcmp(this->id, "BL") == 0)){
            pulseCount ++;
        }
        else{
            pulseCount --;
        }
       
    }
    if (_dir == 1){
        if (this->id != NULL && (strcmp(this->id, "FL") == 0 || strcmp(this->id, "BL") == 0)){
            pulseCount --;
        }
        else{
            pulseCount ++;
        }
    }
}

// La telemetria lo llama despues de cada frame: min/max por ventana, no acumulado.
void Moto::resetEnvolvente()
{
    _envVirgen = true;
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
    if (rotation >= 0)  // gira a la izquierda: el lado derecho va a velocidad base
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
        _fr->setSpeed(!_rightdir, _rightspeed);
        _br->setSpeed(!_rightdir, _rightspeed);
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
        _fr->setSpeed(!_rightdir, _rightspeed);
        _br->setSpeed(!_rightdir, _rightspeed);
    }
}

// steerAxleBias: steer() con la consigna de RPM de cada eje multiplicada por su escala.
// Ojo: bajarle la consigna a un eje no lo frena contra el piso (chasis rigido); el PID ve la RPM
// medida por encima de la pedida y le baja el PWM hasta dejarlo sin par. Sin validar en banco.
void DriveBase::steerAxleBias(double speed, int direction, double rotation,
                              double frontScale, double rearScale)
{
    _speed = constrain(speed, 0, 159);
    _rotation = constrain(rotation, -1, 1);
    frontScale = constrain(frontScale, 0, 1);
    rearScale = constrain(rearScale, 0, 1);
    _direction = direction;
    if (rotation >= 0)  // gira a la izquierda: el lado derecho va a velocidad base
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
    }
    // mismo orden de llamadas que steer(): fl, bl, fr, br
    _fl->setSpeed(_leftdir, _leftspeed * frontScale);
    _bl->setSpeed(_leftdir, _leftspeed * rearScale);
    _fr->setSpeed(!_rightdir, _rightspeed * frontScale);
    _br->setSpeed(!_rightdir, _rightspeed * rearScale);
}

// steerFrenoDelantero: ver drivebase.h. Con frenoInterna = kFrenoComoSteer reparte igual que
// steer() (control negativo).
void DriveBase::steerFrenoDelantero(double speed, int direction,
                                    double rotation, double frenoInterna)
{
    _speed = constrain(speed, 0, 159);
    _rotation = constrain(rotation, -1, 1);
    // kFrenoComoSteer (9.0) es el centinela: queda fuera del constrain, que acota el rango util.
    if (frenoInterna < kFrenoComoSteer)
        frenoInterna = constrain(frenoInterna, -1, 1);
    _direction = direction;

    // Igual que steer(): quien es la interna y a que velocidad va.
    if (rotation >= 0)  // gira a la izquierda: la INTERNA es la izquierda
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
    }
    else                // gira a la derecha: la INTERNA es la derecha
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
    }

    // Delantera interna: frenoInterna es fraccion de `speed` con signo respecto de la marcha
    // (+1 adelante, 0 quieta, -1 reversa), no de _leftspeed, que con rot > 0,5 ya es una reversa.
    // Solo la reversa cierra el radio (vel 40, rot 0,5: R = 3,48 cm; quieta o como steer(): 10,45).
    double vFrontInt, dirBase;
    int dirFrontInt;
    if (frenoInterna >= kFrenoComoSteer)
    {
        vFrontInt = (rotation >= 0 ? _leftspeed : _rightspeed);
        dirFrontInt = (rotation >= 0 ? _leftdir : _rightdir);
    }
    else
    {
        vFrontInt = _speed * frenoInterna;
        dirFrontInt = _direction;
        if (vFrontInt < 0)
        {
            dirFrontInt = !dirFrontInt;
            vFrontInt *= -1;
        }
    }
    (void)dirBase;

    // Mismo orden de llamadas que steer(): fl, bl, fr, br; lado derecho negado (montaje espejado).
    if (rotation >= 0)                     // interna = izquierda -> se frena FL
    {
        _fl->setSpeed(dirFrontInt, vFrontInt);
        _bl->setSpeed(_leftdir, _leftspeed);
        _fr->setSpeed(!_rightdir, _rightspeed);
        _br->setSpeed(!_rightdir, _rightspeed);
    }
    else                                   // interna = derecha  -> se frena FR
    {
        _fl->setSpeed(_leftdir, _leftspeed);
        _bl->setSpeed(_leftdir, _leftspeed);
        _fr->setSpeed(!dirFrontInt, vFrontInt);
        _br->setSpeed(!_rightdir, _rightspeed);
    }
}

// steerSuma: ver drivebase.h. Mismo orden fl, bl, fr, br y lado derecho negado que steer().
// Cada lado satura en 159: saturado, el radio real se abre respecto del pedido.
void DriveBase::steerSuma(double base, int direction, double u)
{
    _speed = constrain(base, 0, 159);
    _direction = direction;
    _rotation = u;                       // se guarda tal cual, para telemetria

    double vIzq = _speed * (1.0 + u);
    double vDer = _speed * (1.0 - u);

    _leftdir = _direction;
    if (vIzq < 0) { _leftdir = !_leftdir; vIzq = -vIzq; }
    _rightdir = _direction;
    if (vDer < 0) { _rightdir = !_rightdir; vDer = -vDer; }

    if (vIzq > 159) vIzq = 159;
    if (vDer > 159) vDer = 159;
    _leftspeed = vIzq;
    _rightspeed = vDer;

    _fl->setSpeed(_leftdir, _leftspeed);
    _bl->setSpeed(_leftdir, _leftspeed);
    _fr->setSpeed(!_rightdir, _rightspeed);
    _br->setSpeed(!_rightdir, _rightspeed);
}

// steerRadius: convierte el radio a `rotation` y delega en steer().
// R = b_eff*(1-rot)/(2*rot)  =>  rot = b_eff/(2*R + b_eff); la velocidad se cancela.
void DriveBase::steerRadius(double speed, int direction, double radius_cm,
                            int sign)
{
    double rot;
    if (radius_cm <= 0.0)
    {
        rot = 1.0;                 // girar en el lugar
    }
    else
    {
        rot = DRIVE_ANCHO_VIA_EFECTIVO /
              (2.0 * radius_cm + DRIVE_ANCHO_VIA_EFECTIVO);
        if (rot > 1.0) rot = 1.0;  // no pasa con R > 0; defensivo
        if (rot < 0.0) rot = 0.0;
    }
    steer(speed, direction, sign >= 0 ? rot : -rot);
}

void DriveBase::reset(){
    _fl->reset();
    _fr->reset();
    _bl->reset();
    _br->reset();
}
