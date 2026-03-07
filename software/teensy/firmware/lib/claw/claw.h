#include <Arduino.h>
#include <Servo.h>

#ifndef claw_h
#define claw_h

class DFServo
{
public:
    DFServo(int pin, double minMicroseconds, double maxMicroseconds, double angularRange);
    void setAngle(double angle);
    double getAngle();

private:
    int _pin;
    double _angle, _minMicroseconds, _maxMicroseconds, _angularRange;
    Servo _servo;
};

class Claw
{
public:
    Claw(DFServo *liftDFServo, DFServo *leftDFServo, DFServo *rightDFServo, DFServo *sortDFServo, DFServo *depositDFServo);
    bool available();
    void open(bool concurrent = false);
    void close(bool concurrent = false);
    void lift(bool concurrent = false);
    void lower(bool concurrent = false);
    void sortLeft(bool concurrent = false);
    void sortRight(bool concurrent = false);
    void depositLeft(bool concurrent = false);
    void depositRight(bool concurrent = false);
    void depositCenter(bool concurrent = false);
    void reset(bool concurrent = false);
    // Start non-blocking pickup sequences (state machine)
    void pickupLeft(bool concurrent = false);
    void pickupRight(bool concurrent = false);
    // Call periodically from main loop to advance claw state
    void update();
    // Returns true if claw is performing a sequence
    bool busy();

private:
    DFServo *_liftDFServo,
        *_leftDFServo,
        *_rightDFServo,
        *_sortDFServo,
        *_depositDFServo;
    unsigned long long _lastAction;
    // State machine for non-blocking sequences
    enum ClawState {
        CL_IDLE = 0,                    // Reposo, no hay secuencia activa
        CL_PICKUP_LEFT_STEP1,           // Inicia cierre de garra para izquierda
        CL_PICKUP_LEFT_STEP2,           // Clasifica izquierda y levanta
        CL_PICKUP_LEFT_STEP3,           // Abre garra
        CL_PICKUP_LEFT_STEP4,           // Finaliza secuencia izquierda
        CL_PICKUP_RIGHT_STEP1,          // Inicia cierre de garra para derecha
        CL_PICKUP_RIGHT_STEP2,          // Clasifica derecha y levanta
        CL_PICKUP_RIGHT_STEP3,          // Abre garra
        CL_PICKUP_RIGHT_STEP4            // Finaliza secuencia derecha
    };
    ClawState _state;  // Estado actual de la máquina de claw. Valores válidos: 0-8. No debe ser negativo.
    unsigned long _stateStartedAt;
    bool _concurrentRequested;
};

#endif