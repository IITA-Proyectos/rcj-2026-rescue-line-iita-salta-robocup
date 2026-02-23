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

DFServo sort(20, 540, 2390, 274);
DFServo left(14, 540, 2390, 274);
DFServo right(21, 540, 2390, 274);
DFServo lift(22, 540, 2390, 274);
DFServo deposit(23, 540, 2390, 274);
Claw claw(&lift, &left, &right, &sort, &deposit);

// Front Ultrasonic Sensor9)
// Color Sensor
Adafruit_APDS9960 apds;
struct Color {
  const char* name;
  uint16_t r, g, b, c;
};

Color known_colors[] = {
  {"Blanco", 25, 35, 49, 131},
  {"Negro", 2, 6, 7, 20},
  {"Verde", 3, 4, 5, 15},
  {"Plateado", 16, 22, 25, 77}//19,25,43,124
};

// Función para leer los valores del sensor y determinar el color
const char* get_color() {
  uint16_t r, g, b, c;
  
  // Esperar a que los datos de color estén listos
  while (!apds.colorDataReady()) {
    delay(5);
  }

  // Obtener los datos del sensor
  apds.getColorData(&r, &g, &b, &c);

  // Calcular el color más cercano utilizando mínimos cuadrados
  const char* closest_color = "Desconocido";
  uint32_t min_error = UINT32_MAX;

  for (size_t i = 0; i < sizeof(known_colors) / sizeof(known_colors[0]); i++) {
    uint32_t error = pow(known_colors[i].r - r, 2) +
                     pow(known_colors[i].g - g, 2) +
                     pow(known_colors[i].b - b, 2) +
                     pow(known_colors[i].c - c, 2);
    if (error < min_error) {
      min_error = error;
      closest_color = known_colors[i].name;
    }
  }

  // Imprimir los valores de R, G, B y Clear
  Serial.print("red: ");
  Serial.print(r);
  Serial.print(" green: ");
  Serial.print(g);
  Serial.print(" blue: ");
  Serial.print(b);
  Serial.print(" clear: ");
  Serial.println(c);

  return closest_color;
}


void setup()
{
  // put your setup code here, to run once:
  Serial.begin(115200);
  claw.lower(); 
  if(!apds.begin()){
    Serial.println("failed to initialize device! Please check your wiring.");
  }
  else Serial.println("Device initialized!");

  //enable color sensign mode
  apds.enableColor(true);
}

void loop()
{/*
  // Ultrasound Sensor get data
  distance = front_ultrasonic.read();
  Serial.print("Distance in CM: ");
  Serial.println(distance);*/

  const char* color_detected = get_color();
  // Imprimir el color detectado
  Serial.print("Color detectado: ");
  Serial.println(color_detected);
  delay(1000);
}