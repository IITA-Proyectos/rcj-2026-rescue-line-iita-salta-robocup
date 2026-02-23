#include <Wire.h>
#include <VL53L0X.h>

VL53L0X left_tof;   // Sensor 1
VL53L0X right_tof;  // Sensor 2

void setup()
{
  Serial.begin(9600);
  Wire1.begin();   // Initialize the first I2C bus
  Wire2.begin();  // Initialize the second I2C bus

  left_tof.setBus(&Wire2);   // Assign the first bus to Sensor 1
  right_tof.setBus(&Wire1); // Assign the second bus to Sensor 2

  left_tof.setAddress(0x30); // Set unique address for Sensor 1
  right_tof.setAddress(0x30); // Set unique address for Sensor 2

// Continue with your setup and loop functions as before

  left_tof.init();
  left_tof.setTimeout(500);
  left_tof.startContinuous();

  right_tof.init();
  right_tof.setTimeout(500);
  right_tof.startContinuous();
}

void loop()
{
  int distance_left_tof = left_tof.readRangeContinuousMillimeters();
  int distance_right_tof = right_tof.readRangeContinuousMillimeters();

  Serial.print("Distance Left: ");
  Serial.print(distance_left_tof);
  Serial.print("mm");

  if (left_tof.timeoutOccurred()) { Serial.print(" TIMEOUT"); }

  Serial.print("   Distance Right: ");
  Serial.print(distance_right_tof);
  Serial.print("mm");

  if (right_tof.timeoutOccurred()) { Serial.print(" TIMEOUT"); }

  Serial.println();
  delay(100);
}