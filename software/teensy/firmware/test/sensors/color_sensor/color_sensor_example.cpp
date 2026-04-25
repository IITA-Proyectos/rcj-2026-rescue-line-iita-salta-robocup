// ##################################################
//
// ### IMPORTACION DE LIBRERIAS
//
// ##################################################

#include <Adafruit_Sensor.h>
#include "Adafruit_APDS9960.h"
Adafruit_APDS9960 apds;

// ##################################################
//
// ### PROCESAMIENTO PRINCIPAL
//
// ##################################################

void setup() {
  /*
  Technical description.

  Initialize serial console and start APDS9960 color sensor in color mode.

  Parameters:
  None

  Returns:
  void

  Side effects:
  - Opens Serial at 115200.
  - Enables color sensing on APDS9960.
  */
  Serial.begin(115200);

  if(!apds.begin()){
    Serial.println("failed to initialize device! Please check your wiring.");
  }
  else Serial.println("Device initialized!");

  //enable color sensign mode
  apds.enableColor(true);
}

void loop() {
  // Main system loop.
  // Executes continuous real-time processing.
  /*
  Technical description.

  Wait for color data readiness, read channel values, and print over Serial.

  Parameters:
  None

  Returns:
  void

  Side effects:
  - Serial output with color channel values every 500 ms.
  */
  //create some variables to store the color data in
  uint16_t r, g, b, c;
  
  //wait for color data to be ready
  while(!apds.colorDataReady()){
    delay(5);
  }

  //get the data and print the different channels
  apds.getColorData(&r, &g, &b, &c);
  Serial.print("red: ");
  Serial.print(r);
  
  Serial.print(" green: ");
  Serial.print(g);
  
  Serial.print(" blue: ");
  Serial.print(b);
  
  Serial.print(" clear: ");
  Serial.println(c);
  Serial.println();
  
  delay(500);
}
