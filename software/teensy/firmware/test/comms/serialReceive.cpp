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
#include "Adafruit_APDS9960.h>
#include <NewPing.h>
#include <Wire.h>
#include <VL53L0X.h>
#include <Arduino.h>

void setup()
{
    /*
    Technical description.

    Initialize serial ports for forwarding data from Serial5 to Serial.

    Parameters:
    None

    Returns:
    void

    Side effects:
    - Opens Serial and Serial5 at configured baud rates.
    */
    Serial.begin(115200);
    Serial5.begin(57600);
}

void loop()
{
    // Main system loop.
    // Executes continuous real-time processing.
    /*
    Technical description.

    Read bytes from Serial5 and echo them as characters on Serial.

    Parameters:
    None

    Returns:
    void

    Side effects:
    - Transfers data between serial interfaces.
    */
    int incomingByte;

    if (Serial5.available() > 0)
    {
        incomingByte = Serial5.read();
        Serial.print(char(incomingByte));
    }
}
