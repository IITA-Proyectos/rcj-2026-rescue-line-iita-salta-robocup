// ##################################################
//
// ### IMPORTACION DE LIBRERIAS
//
// ##################################################

#include <Wire.h>
#include <Arduino.h>

void setup()
{
  /*
  Technical description.

  Initialize dual I2C buses and serial console for scanning devices.

  Parameters:
  None

  Returns:
  void

  Side effects:
  - Starts Wire and Wire1.
  - Opens Serial at 9600 baud.
  */
  Wire.begin();
  Wire1.begin();
  Serial.begin(9600);
  while (!Serial)
    ;
  Serial.println("\nI2C0 and I2C1 Scanner");
}

void loop()
{
  // Main system loop.
  // Executes continuous real-time processing.
  /*
  Technical description.

  Scan both I2C buses for active device addresses and print findings.

  Parameters:
  None

  Returns:
  void

  Side effects:
  - Bus transactions on Wire and Wire1.
  - Serial output of scan results.
  */
  byte error, address;
  int nDevices;

  Serial.println("Scanning...");

  nDevices = 0;
  for (address = 1; address < 127; address++)
  {
    // The i2c_scanner uses the return value of
    // the Write.endTransmisstion to see if
    // a device did acknowledge to the address.
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0)
    {
      Serial.print("I2C0 device found at address 0x");
      if (address < 16)
        Serial.print("0");
      Serial.print(address, HEX);
      Serial.println("  !");

      nDevices++;
    }
    else if (error == 4)
    {
      Serial.print("Unknown I2C0 error at address 0x");
      if (address < 16)
        Serial.print("0");
      Serial.println(address, HEX);
    }
  }
  for (address = 1; address < 127; address++)
  {
    // The i2c_scanner uses the return value of
    // the Write.endTransmisstion to see if
    // a device did acknowledge to the address.
    Wire1.beginTransmission(address);
    error = Wire1.endTransmission();

    if (error == 0)
    {
      Serial.print("I2C1 device found at address 0x");
      if (address < 16)
        Serial.print("0");
      Serial.print(address, HEX);
      Serial.println("  !");

      nDevices++;
    }
    else if (error == 4)
    {
      Serial.print("Unknown I2C1 error at address 0x");
      if (address < 16)
        Serial.print("0");
      Serial.println(address, HEX);
    }
  }
  if (nDevices == 0)
    Serial.println("No I2C devices found\n");
  else
    Serial.println("done\n");

  delay(3000); // wait 5 seconds for next scan
}
