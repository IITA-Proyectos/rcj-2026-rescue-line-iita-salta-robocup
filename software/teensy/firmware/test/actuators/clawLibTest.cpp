// ##################################################
//
// ### IMPORTACION DE LIBRERIAS
//
// ##################################################

#include <Wire.h>
#include <Arduino.h>
#include <drivebase.h>
#include <PID.h>
#include <elapsedMillis.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include "math.h"
#include <Servo.h>
#include <Adafruit_I2CDevice.h>
#include <claw.h>
#include "Adafruit_APDS9960.h"
#include <NewPing.h>
#include <Wire.h>
#include <VL53L0X.h>



// ##################################################
//
// ### CONFIGURACION GLOBAL
//
// ##################################################

// SERVOS
DFServo sort(12, 540, 2390, 274);
DFServo left(14, 540, 2390, 274);
DFServo right(15, 540, 2390, 274);
DFServo lift(22, 540, 2390, 274);
DFServo deposit(23, 540, 2390, 274);
Claw claw(&lift, &left, &right, &sort, &deposit);

// ##################################################
//
// ### PROCESAMIENTO PRINCIPAL
//
// ##################################################

void setup()
{
    // Initialize serial monitor if needed for diagnostics.
    // Serial.begin(115200);
}

void loop()
{
    // Main system loop.
    // Executes continuous real-time processing.
    claw.lower();
    delay(1000);

}
