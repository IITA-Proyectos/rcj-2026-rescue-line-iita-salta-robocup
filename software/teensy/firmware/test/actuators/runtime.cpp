#include <Arduino.h>
#include <drivebase.h>
#include <PID.h>
#include <claw.h>
#include <Wire.h>
#include <elapsedMillis.h>

bool startUp = false;
Moto bl(29, 28, 27, "BL"); // pwm, dir, enc
Moto fl(7, 6, 5, "FL");
Moto br(36, 37, 38, "BR");
Moto fr(4, 3, 2, "FR");
DriveBase robot(&fl, &fr, &bl, &br);

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
void setup() {
  robot.steer(0, 0, 0);
  attachInterrupt(digitalPinToInterrupt(27), ISR1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(5), ISR2, CHANGE);
  attachInterrupt(digitalPinToInterrupt(38), ISR3, CHANGE);
  attachInterrupt(digitalPinToInterrupt(2), ISR4, CHANGE);
  pinMode(32, INPUT_PULLUP); // switch
  pinMode(13, OUTPUT);       // in-built LED for debugging
  Serial1.begin(57700);      // for reading IMU
  Serial5.begin(115200);     // for reading data from rpi and state
  Serial.begin(115200);      // displays ultrasound ping results
}

void runTime(int speed, int dir, double steer, unsigned long long time)
{
  unsigned long long startTime = millis();
  // elapsedMillis startTime;
  while ((millis() - startTime) < time)
  {
    robot.steer(speed, dir, steer);
    digitalWrite(13, HIGH);
    if (digitalRead(32) == 1) // switch is off
    {
      Serial5.write(255);
    }
  }

  digitalWrite(13, LOW);

  // robot.steer(0, FORWARD, 0);
  // }11111111
}

void runTime2(int speed, int dir, double steer, unsigned long long time)
{
  unsigned long long startTime = millis();
  // elapsedMillis startTime;
  while ((millis() - startTime) < time)
  {
    robot.steer(speed, dir, steer);
    digitalWrite(13, HIGH);
    Serial5.write(255);
  }

  digitalWrite(13, LOW);
}


void loop() {
  if (digitalRead(32) == 1) { // Apagado
    digitalWrite(13, LOW); // Apagar LED de depuración
    Serial5.write(255); // Informar que el robot está apagado
    robot.steer(0, 0, 0); // Detener el movimiento
  } else if (digitalRead(32) == 0 && !startUp) { // Reinicio
    startUp = true;
    digitalWrite(13, HIGH); // Encender LED de depuración
    delay(500);
    digitalWrite(13, LOW);
    delay(500);
  } else { // Prendido
    digitalWrite(13, HIGH); 

      runTime(50, 1, 0, 3000);
        digitalWrite(13,LOW);
      runTime(0, 0, 0, 3000); 
      runTime(50, 0, 0, 3000);
      runTime(0, 0, 0, 3000); 
    
  }
}
