#include <Wire.h>
#include <Arduino.h>
#include <SPI.h>
#include <drivebase.h>
#include <PID.h>
#include <elapsedMillis.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_I2CDevice.h>
#include "Adafruit_APDS9960.h"
#include "math.h"                            
// CONSTANTS //
#define FORWARD 0
#define BACKWARD 1
#define BUZZER 33
#define LED_ROJO 39
#define SWITCH 32
const char* color_detected;
// INITIALISE BNO055 //
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
// INITIALISE ACTUATORS //
Moto bl(29, 28, 27, "BL"); // pwm, dir, enc
Moto fl(7, 6, 5, "FL");
Moto br(36, 37, 38, "BR");
Moto fr(4, 3, 2, "FR");
DriveBase robot(&fl, &fr, &bl, &br);
// STATE VARIABLES & FLAGS //
int counter=0;
int laststeer=0;
int serial5state = 0; // serial code e.g. 255
double speed;        // speed (0 to 100)
double steer;        // angle (0 to 180 deg, will -90 later)
int green_state = 0; // 0 = no green squares, 1 = left, 2 = right, 3 = double
int line_middle = 0; // if there is a line to reacquire after obstacle
int action;          // action to take (part of a task)
bool taskDone = false; // if true, update current_task
int angle0;             // initial IMU reading
bool startUp = false;
float frontUSReading;
unsigned long long lastfk = millis(), lastdblgreen = millis();
int cccounter, leftLidarReading, rightLidarReading;
// ISR for updating motor pulses
void ISR1() { bl.updatePulse(); }
void ISR2() { fl.updatePulse(); }
void ISR3() { br.updatePulse(); }
void ISR4() { fr.updatePulse(); }

void reset_enconder(){
    bl.resetPulseCount();
    fl.resetPulseCount();
    br.resetPulseCount();
    fr.resetPulseCount();
}

void runDistance(int speed, int dir, int Distance) {
    runTime(30,BACKWARD,0,20);
    runTime(30,FORWARD,0,20);
    reset_enconder();
    int32_t  encoder = 25*Distance;
    
    if (dir == FORWARD) {
        while (true) {
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;
            if (frCount >= encoder || flCount >= encoder) break;

            robot.steer(speed, dir, 0);
            Serial.print(flCount);
            Serial.print(" | ");
            Serial.print(frCount);
            //Serial.println(fr.pulseCount);
            digitalWrite(13, HIGH);
            delay(10);
            
            if (Serial5.available() > 0) {
                int lecturas = Serial5.read();
                Serial.print(lecturas);
            }
            
            if (digitalRead(32) == 1) { // switch is off
                Serial5.write(255);
                break;
            }
        }
    }else{
         while (true) 
        {
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;

            if (frCount <= -encoder || flCount <= -encoder) break;
            robot.steer(speed, dir, 0);
            Serial.print(flCount);
            Serial.print(" | ");
            Serial.print(frCount);
            //Serial.println(fr.pulseCount);
            delay(10);
            if (Serial5.available() > 0) {
                int lecturas = Serial5.read();
                Serial.print(lecturas);
            }
            
            if (digitalRead(32) == 1) { // switch is off
                Serial5.write(255);
                break;
            }
        }
        
        
    }
}
void setup() {
    robot.steer (0,0,0);
    attachInterrupt(digitalPinToInterrupt(27), ISR1, CHANGE);
    attachInterrupt(digitalPinToInterrupt(5), ISR2, CHANGE);
    attachInterrupt(digitalPinToInterrupt(38), ISR3, CHANGE);
    attachInterrupt(digitalPinToInterrupt(2), ISR4, CHANGE);
    pinMode(SWITCH, INPUT_PULLUP); // SWITCH
    pinMode(BUZZER, OUTPUT); // BUZZER
    pinMode(LED_ROJO, OUTPUT); // LED ROJO
    pinMode(LED_BUILTIN, OUTPUT); // LED BUILT-IN for debugging
    Serial1.begin(57600);  // for reading IMU
    Serial5.begin(115200); // for reading data from rpi and state
    Serial.begin(115200);  // displays ultrasound ping result
}
void loop() {
    if (digitalRead(32) == 1) { // switch is off
        robot.steer(0, FORWARD, 0); // stop moving
        action = 7;
        startUp = false;
        taskDone = true;
        Serial5.write(255);
        while (true){
            robot.steer(0,0,0);
            digitalWrite(LED_BUILTIN, HIGH);
            //digitalWrite(BUZZER, HIGH);
            digitalWrite(LED_ROJO, HIGH);
            delay(500); 
            robot.steer(0,0,0);
            digitalWrite(LED_BUILTIN, LOW);
            digitalWrite(BUZZER, LOW);
            digitalWrite(LED_ROJO, LOW);
            delay(500);
            if (digitalRead(SWITCH) == 0){
                break;
            }
        }
    } else if (digitalRead(32) == 0 && !startUp) {
        digitalWrite(LED_BUILTIN, LOW);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, LOW);
        //runTime(20, BACKWARD, 0, 300);
        //runTime(20, FORWARD, 0, 300);
        reset_enconder();
        //Serial5.write(254);
        startUp = true;
        action =7;
    }
    else{
        digitalWrite(LED_BUILTIN, HIGH);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, HIGH);
        runDistance(20, FORWARD, 15);
        runDistance(20, BACKWARD, 15);
        
        
      }
} 