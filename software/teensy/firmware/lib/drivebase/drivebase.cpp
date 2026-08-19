/*
  drivebase.cpp - Library for controlling motors.
*/
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

    // --- 1. El sentido es SIEMPRE el pedido. Sin toggle (defecto c) ----------
    //     Al invertir, el esfuerzo acumulado yendo para el otro lado no vale
    //     nada: se descarta el integrador para que no reme en contra.
    if (dir != _dir)
    {
        _motoPID.Reset();
        _envVirgen = true;
    }
    _dir = dir;

    // --- 2. Feedforward: el piso de esfuerzo sale del COMANDO, no de la
    //        medicion. Es lo que sostiene a la rueda que el encoder no sabe
    //        leer (defectos a y b).
    // CONSIGNA ~0 = APAGAR YA. Sin esto, PID::Reset() pone en cero el acumulador
    // pero NO _pwmVal (es *myOutput, y Reset no lo toca), y Compute() solo corre
    // cada SampleTime: durante hasta 20 ms se seguiria aplicando la correccion
    // anterior. O sea que pedirle al robot que PARE lo dejaba andando un rato con
    // el esfuerzo viejo. Hallazgo de Codex, verificado en PID.cpp.
    if (rpm <= MOTO_RPM_MIN)
    {
        _motoPID.Reset();
        _pwmVal = 0;              // la correccion vieja no sobrevive al frenado
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

    double ff = MOTO_KS + MOTO_KV * rpm;

    // --- 3. ANTI-WINDUP CON FEEDFORWARD. El integrador se acota al rango que
    //        REALMENTE mueve la salida: de ahi para abajo o para arriba ya no
    //        cambia nada y solo acumula deuda que despues hay que remontar.
    //        El limite inferior ES el piso: con consigna viva el integrador no
    //        puede apagar el motor por mas que la medicion diga lo que diga.
    //        Sin esto el fix funciona DENTRO de la curva y deja la rueda
    //        dormida al salir, que es la misma falla con otra cara.
    _motoPID.SetOutputLimits(ff * MOTO_PISO - ff, 255.0 - ff);

    // --- 4. El integrador corrige; ya no manda solo ---------------------------
    _motoPID.Compute();
    _pwmTotal = constrain(ff + _pwmVal, 0.0, 255.0);

    // --- 5. PISO ABSOLUTO, aparte del anti-windup y a proposito: el limite del
    //        integrador es una cuestion de CONTROL y esto es una cuestion del
    //        ACTUADOR (por debajo de cierto PWM el FIT0441 suelta la rueda).
    //        Mezclarlos fue el error de la version anterior: el piso quedaba
    //        atado a la consigna y se desvanecia justo cuando la consigna era
    //        chica, o sea en la curva cerrada.
    if (_pwmTotal < MOTO_PWM_ANTICOAST) _pwmTotal = MOTO_PWM_ANTICOAST;

#else   // ---------------- lazo historico, el que compitio ---------------------

    if (_pwmVal < 10)
    {
        _dir = !_dir;
        dirToggles++;   // DIAGNOSTICO: solo cuenta, no altera nada
    }
    else
        _dir = dir;
    _motoPID.Compute();
    _pwmTotal = _pwmVal;

#endif

    // ENVOLVENTE: cada actualizacion del control entra aca, sin importar desde
    // donde se llamo (loop, runTime, runAngle). Es el unico punto por el que
    // pasan TODAS, asi que es donde el min/max queda completo.
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
    /*
    Serial.print("Motor "); 
        Serial.print(id); 
        Serial.print(": ");
        Serial.println(pulseCount);
    */
    
}

// La telemetria llama a esto DESPUES de mandar el frame: el min/max es POR
// VENTANA, no acumulado desde el arranque (si no, a los diez segundos el
// minimo de PWM es 0 para siempre y el dato deja de decir nada).
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

// ============================================================================
//  steerAxleBias - RECONSTRUIDA desde el desensamblado del firmware.elf del
//  2026-08-15 21:04 (simbolo DriveBase::steerAxleBias(double,int,double,
//  double,double) en 0x55e8). La fuente original se perdio al revertir este
//  archivo el 16-ago y nunca llego a un commit, pero main.cpp la seguia
//  llamando: por eso el arbol dejo de compilar.
//
//  Es steer() con un solo agregado: la consigna de RPM de cada EJE se
//  multiplica por su escala. Con frontScale < rearScale el eje delantero pide
//  menos vueltas que el trasero, que es como se intento emular el pivote sobre
//  el eje delantero que daban las omni.
//
//  OJO AL EFECTO REAL (no estaba documentado en ningun lado): bajarle la
//  consigna a un eje NO lo hace girar mas despacio contra el piso -lo obliga
//  la geometria del chasis rigido-. Lo que consigue es que la RPM medida
//  supere a la pedida, y como el PID solo ve magnitudes, le baja el PWM hasta
//  cero. Con frontScale = 0.55 el eje delantero queda practicamente sin par.
//  Medir con el banco antes de darla por buena.
// ============================================================================
void DriveBase::steerAxleBias(double speed, int direction, double rotation,
                              double frontScale, double rearScale)
{
    _speed = constrain(speed, 0, 159);
    _rotation = constrain(rotation, -1, 1);
    frontScale = constrain(frontScale, 0, 1);
    rearScale = constrain(rearScale, 0, 1);
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
    // mismo orden de llamadas que el binario: fl, bl, fr, br
    _fl->setSpeed(_leftdir, _leftspeed * frontScale);
    _bl->setSpeed(_leftdir, _leftspeed * rearScale);
    _fr->setSpeed(!_rightdir, _rightspeed * frontScale);
    _br->setSpeed(!_rightdir, _rightspeed * rearScale);
}

void DriveBase::reset(){
    _fl->reset();
    _fr->reset();
    _bl->reset();
    _br->reset();
}
