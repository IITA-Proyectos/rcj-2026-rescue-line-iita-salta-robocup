// ============================================================================
//  banco/finales.cpp - QUE LEEN LOS FINALES DE CARRERA (FCL pin 40, FCR pin 26).
//
//  Los lee IGUAL que el robot (INPUT_PULLDOWN, HIGH = apretado) y cada 100 ms
//  imprime una linea por USB:
//
//    FCL(40)=1 FCR(26)=1 [pin41=0] | reb L=0 R=0 | ambos 0 ms | CONFIRMA=SI
//
//    FCL/FCR   nivel ahora (1 = apretado)
//    reb       cambios de nivel en esos 100 ms, muestreando rapido. Apretando
//              firme tiene que dar 0 salvo al apretar/soltar. Muchos cambios
//              con el final quieto = falso contacto o ruido en el cable.
//    ambos     cuanto hace que los DOS estan en 1 sin cortar
//    CONFIRMA  la regla de retrocederHastaFinales(): los dos en 1 durante 50 ms
//
//  Suelto tiene que leer 0. Si suelto lee 1, algo tira el pin a 3,3 V (final
//  pegado, cable en corto). Si salta entre 0 y 1 sin tocarlo, el cable esta
//  flojo o el pull-down interno no alcanza.
//
//  No mueve motores ni usa ninguna libreria del robot.
//  Flashear:  pio run -e banco_finales -t upload
//  Ver:       pio device monitor -b 115200
// ============================================================================
#include <Arduino.h>

static const uint8_t FCL = 40;
static const uint8_t FCR = 26;          // Cambiado de 41 a 26
static const uint8_t PIN41_VIEJO = 41;  // Monitoreo comparativo
static const unsigned long CONFIRMACION_MS = 50;   // igual que retrocederHastaFinales()

void setup()
{
    Serial.begin(115200);
    pinMode(FCL, INPUT_PULLDOWN);
    pinMode(FCR, INPUT_PULLDOWN);
    pinMode(PIN41_VIEJO, INPUT_PULLDOWN);
    delay(500);
    Serial.println("# finales de carrera: FCL pin 40, FCR pin 26 (anterior pin 41) (1 = apretado)");
}

void loop()
{
    static unsigned long ambosDesde = 0;
    uint32_t rebL = 0, rebR = 0;
    int l = digitalReadFast(FCL), r = digitalReadFast(FCR), p41 = digitalReadFast(PIN41_VIEJO);
    const unsigned long t0 = millis();
    while (millis() - t0 < 100)
    {
        const int nl = digitalReadFast(FCL), nr = digitalReadFast(FCR);
        if (nl != l) { rebL++; l = nl; }
        if (nr != r) { rebR++; r = nr; }
        if (l && r)
        {
            if (ambosDesde == 0) ambosDesde = millis();
        }
        else
            ambosDesde = 0;
    }
    const unsigned long ambosMs = ambosDesde ? millis() - ambosDesde : 0;
    Serial.printf("FCL(40)=%d FCR(26)=%d [pin41=%d] | reb L=%lu R=%lu | ambos %lu ms | CONFIRMA=%s\n",
                  l, r, p41, (unsigned long)rebL, (unsigned long)rebR, ambosMs,
                  ambosMs >= CONFIRMACION_MS ? "SI" : "no");
}
