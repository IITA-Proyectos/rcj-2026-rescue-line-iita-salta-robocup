// ============================================================================
//  banco/pines.cpp - QUE PASA EN LAS LINEAS DE ENCODER.
//
//  PARA QUE: el registrador dice "raw no se mueve", y eso tiene causas que se
//  arreglan en lugares distintos. El CSV del robot no las separa; esto si.
//
//  DOS INSTRUMENTOS EN UNO:
//
//  1) NIVEL LOGICO + FLANCOS, en los 4 pines. Se mide con el pull-up interno
//     prendido y apagado a proposito: un pin al aire lee 1 con pull-up, un pin
//     que sigue en 0 contra el pull-up tiene algo tirandolo a masa.
//     Los flancos se cuentan por muestreo rapido, SIN interrupciones, para no
//     depender de la misma cadena que se esta poniendo en duda.
//
//  2) VOLTIMETRO, en los dos pines que caen en entradas analogicas del
//     Teensy 4.1 (27 = A13 y 38 = A14). El equipo no tiene tester, y esta era
//     la limitacion declarada del diagnostico: "no hay sensor y no tienen
//     voltimetro". Con pull-up, pull-down y sin nada, la TENSION separa cosas
//     que el nivel logico confunde:
//
//       con pull-up ~3,3 V  -> no hay NADA del otro lado (linea abierta)
//       con pull-up ~0,6 V  -> hay un chip SIN ALIMENTAR: el pull-up entra por
//                              su diodo de proteccion y queda clampeado. Esta
//                              es la firma de "al encoder no le llega VCC"
//       con pull-up ~0,0 V  -> corto a masa, o un chip alimentado forzando 0
//
//     Un 0 logico no distingue esos tres casos. 0,6 V contra 0,0 V si.
//
//  CONTROL POSITIVO: el pin 32 (SWITCH) va con pull-up y con la llave abierta
//  tiene que leer 1. Sin control, "todos los pines dan 0" no distingue "el
//  hardware esta mudo" de "mi medicion esta mal", y esa distincion es la
//  diferencia entre revisar el robot y revisar el sketch.
//
//  No incluye ninguna libreria del robot y no toca los motores.
// ============================================================================
#include <Arduino.h>

static const uint8_t PINES[5]   = {27, 5, 38, 2, 32};
static const char   *NOMBRE[5]  = {"27=bl", "5=fl", "38=br", "2=fr", "32=CONTROL"};
static const bool    ANALOGICO[5] = {true, false, true, false, false};  // 27=A13, 38=A14

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

// Promedia para que el ruido no decida. Devuelve milivolts.
static int milivolts(uint8_t pin)
{
    uint32_t s = 0;
    for (int i = 0; i < 64; i++) s += analogRead(pin);
    return (int)((s / 64) * 3300UL / 4095UL);
}

void setup()
{
    Serial.begin(115200);
    analogReadResolution(12);
    analogReadAveraging(8);
    for (uint8_t i = 0; i < 5; i++) pinMode(PINES[i], INPUT);
    delay(300);
    Serial.println("# lineas de encoder: nivel, flancos y TENSION. Gira las ruedas.");
    Serial.println("pin,sin_pu,con_pu,flancos,mv_libre,mv_pullup,mv_pulldown");
}

void loop()
{
    for (uint8_t i = 0; i < 5; i++)
    {
        pinMode(PINES[i], INPUT);
        delayMicroseconds(300);
        int sinPu = digitalReadFast(PINES[i]);
        int mvLib = ANALOGICO[i] ? milivolts(PINES[i]) : -1;
        uint32_t fl = contarFlancos(PINES[i], 200);

        pinMode(PINES[i], INPUT_PULLUP);
        delayMicroseconds(300);
        int conPu = digitalReadFast(PINES[i]);
        int mvPu  = ANALOGICO[i] ? milivolts(PINES[i]) : -1;

        pinMode(PINES[i], INPUT_PULLDOWN);
        delayMicroseconds(300);
        int mvPd  = ANALOGICO[i] ? milivolts(PINES[i]) : -1;

        pinMode(PINES[i], INPUT);
        Serial.print(NOMBRE[i]); Serial.print(",");
        Serial.print(sinPu); Serial.print(",");
        Serial.print(conPu); Serial.print(",");
        Serial.print(fl);    Serial.print(",");
        Serial.print(mvLib); Serial.print(",");
        Serial.print(mvPu);  Serial.print(",");
        Serial.println(mvPd);
    }
    Serial.println("--");
}
