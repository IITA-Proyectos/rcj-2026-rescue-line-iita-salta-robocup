#include <Arduino.h>
#include <Servo.h>

#ifndef claw_h
#define claw_h

class DFServo
{
public:
    DFServo(int pin, double minMicroseconds, double maxMicroseconds, double angularRange);
    void begin();  // Attach servo after global initialization
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
    void begin();  // Initialize claw after setup
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
    // ClawState enumerates the named steps of the non-blocking pickup sequences.
    // Usage summary:
    //  - Call `pickupLeft()` or `pickupRight()` to "fire" the sequence (sets `_state` to STEP1).
    //  - `update()` is called frequently from `loop()`; it checks `_state` and `millis()`
    //    to perform the current step (move servos) and advance to the next step.
    //  - `busy()` returns true while `_state` is not `CL_IDLE` (sequence in progress).
    //  - This replaces blocking `delay()` calls so the MCU keeps processing Serial and motors.
  enum ClawState {
    CL_IDLE = 0,                // 0: pinza en reposo (no hay secuencia)
    CL_PICKUP_LEFT_STEP1,       // paso 1 de recogida izquierda (disparado por pickupLeft())
    CL_PICKUP_LEFT_STEP2,       // paso 2 de recogida izquierda (espera -> sort+lift)
    CL_PICKUP_LEFT_STEP3,       // paso 3 de recogida izquierda (abrir)
    CL_PICKUP_LEFT_STEP4,       // paso 4 de recogida izquierda (finalizar, vuelta a CL_IDLE)
    CL_PICKUP_RIGHT_STEP1,      // igual que arriba, para recogida derecha
    CL_PICKUP_RIGHT_STEP2,
    CL_PICKUP_RIGHT_STEP3,
    CL_PICKUP_RIGHT_STEP4
};
    ClawState _state;
    unsigned long _stateStartedAt;
    bool _concurrentRequested;
};

#endif