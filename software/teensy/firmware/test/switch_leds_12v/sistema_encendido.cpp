// ##################################################
//
// ### IMPORTACION DE LIBRERIAS
//
// ##################################################

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
    /*
    Technical description.

    Reset encoder pulse counters for all drive motors.

    Parameters:
    None

    Returns:
    void

    Side effects:
    - Clears motor pulse counts.
    */
    bl.resetPulseCount();
    fl.resetPulseCount();
    br.resetPulseCount();
    fr.resetPulseCount();
}
void setup()
{
  /*
  Technical description.

  Initialize interrupts, pins, serial links, and default drive state for LED switch test.

  Parameters:
  None

  Returns:
  void

  Side effects:
  - Configures GPIO and serial ports.
  - Starts drivebase with zero motion.
  */
  robot.steer(0,0,0);
  attachInterrupt(digitalPinToInterrupt(2), ISR1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(36), ISR2, CHANGE);
  attachInterrupt(digitalPinToInterrupt(5), ISR3, CHANGE);
  attachInterrupt(digitalPinToInterrupt(29), ISR4, CHANGE);
  pinMode(32, INPUT_PULLUP); // switch
  pinMode(13, OUTPUT);       // in-built LED for debugging
  pinMode(29,OUTPUT); //transistor
  Serial1.begin(57700);  // for reading IMU
  Serial5.begin(115200); // for reading data from rpi and state
  Serial.begin(115200);  // displays ultrasound ping results

}

void loop()
{
  // Main system loop.
  // Executes continuous real-time processing.
  /*
  Technical description.

  Manage 12V LED switch behavior tied to safety switch status.

  Parameters:
  None

  Returns:
  void

  Side effects:
  - Drives LEDs via transistor pin.
  - Sends Serial5 notification when off.
  */

  if (digitalRead(32) == 1) // Apagado
  {
  robot.steer(0,0,0);
  digitalWrite(13, LOW);
  digitalWrite(29,LOW);
  Serial5.write(255);
  }

  else if (digitalRead(32) == 0 && !startUp) //Reinicio
  {
    startUp = true;
    digitalWrite(13, HIGH);
    delay(500); 
    digitalWrite(13, LOW);
    delay(500);
  }

  else //Prendido
  { 
    digitalWrite(13, HIGH); 
    digitalWrite(29,HIGH); //leds prendidos

  }
}
