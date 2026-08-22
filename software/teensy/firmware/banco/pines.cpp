// ============================================================================
//  banco/pines.cpp - QUE NIVEL TIENEN LOS PINES DE ENCODER.
//
//  PARA QUE: el registrador dice "raw no se mueve", y eso tiene tres causas
//  distintas que se arreglan en lugares distintos:
//     - el pin esta FIJO EN 0     -> no llega señal (motor sin alimentacion,
//                                    o la salida del FIT0441 muerta)
//     - el pin FLOTA (cambia solo) -> cable suelto: la entrada esta al aire
//     - el pin cambia AL GIRAR     -> la señal llega y el problema es de
//                                    firmware, no de hardware
//  Sin esto la unica salida es probar cosas al azar, y hoy no sobra tiempo.
//
//  Mide de dos maneras a proposito:
//     - SIN pull-up: el nivel tal como lo entrega el circuito
//     - CON pull-up interno: si sin pull-up da 0 y con pull-up da 1, la linea
//       esta al aire o es colector abierto sin nada que la levante
//  y ademas cuenta flancos por muestreo rapido, sin interrupciones, para no
//  depender de la misma cadena que se esta poniendo en duda.
// ============================================================================
#include <Arduino.h>

// El pin 32 es el SWITCH, que va con pull-up y con la llave ABIERTA tiene que
// leer 1. Es el CONTROL POSITIVO: si tambien diera 0, el que esta roto es este
// sketch y no el robot. Sin un control, "todos los pines dan 0" no distingue
// "el hardware esta mudo" de "mi medicion esta mal".
static const uint8_t PINES[5] = {27, 5, 38, 2, 32};
static const char *NOMBRE[5] = {"27=bl", "5=fl", "38=br", "2=fr", "32=CONTROL"};

// Cuenta cambios de nivel durante `ms`, muestreando lo mas rapido posible.
static uint32_t contarFlancos(uint8_t pin, uint16_t ms)
{
    uint32_t n = 0;
    int prev = digitalReadFast(pin);
    uint32_t t0 = millis();
    while (millis() - t0 < ms)
    {
        int v = digitalReadFast(pin);
        if (v != prev) { n++; prev = v; }
    }
    return n;
}

void setup()
{
    Serial.begin(115200);
    for (uint8_t i = 0; i < 5; i++) pinMode(PINES[i], INPUT);
    delay(300);
    Serial.println("# nivel de los pines de encoder. Gira las ruedas mientras corre.");
    Serial.println("pin,sin_pullup,con_pullup,flancos_200ms");
}

void loop()
{
    for (uint8_t i = 0; i < 5; i++)
    {
        pinMode(PINES[i], INPUT);
        delayMicroseconds(200);
        int sinPu = digitalReadFast(PINES[i]);
        uint32_t fl = contarFlancos(PINES[i], 200);
        pinMode(PINES[i], INPUT_PULLUP);
        delayMicroseconds(200);
        int conPu = digitalReadFast(PINES[i]);
        pinMode(PINES[i], INPUT);
        Serial.print(NOMBRE[i]); Serial.print(",");
        Serial.print(sinPu);     Serial.print(",");
        Serial.print(conPu);     Serial.print(",");
        Serial.println(fl);
    }
    Serial.println("--");
}
