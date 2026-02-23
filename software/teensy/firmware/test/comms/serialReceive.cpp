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
#include <Arduino.h>

void setup()
{
    Serial.begin(115200);
    Serial5.begin(57600);
}

void loop()
{
    int incomingByte;

    if (Serial5.available() > 0)
    {
        incomingByte = Serial5.read();
        Serial.print(char(incomingByte));
    }
}