// ##################################################
//
// ### IMPORTACION DE LIBRERIAS
//
// ##################################################

#include <Arduino.h>

// ##################################################
//
// ### PROCESAMIENTO PRINCIPAL
//
// ##################################################

void setup()
{
  // Configure built-in LED pin for output.
  pinMode(13, OUTPUT);
}

void loop()
{
  // Main system loop.
  // Executes continuous real-time processing.
  digitalWrite(13, HIGH);
  delay(1000);
  digitalWrite(13, LOW);
  delay(1000);
}
