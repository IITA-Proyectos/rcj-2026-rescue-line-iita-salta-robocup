// ============================================================================
//  banco/girar.cpp - EL ENCODER, ¿EMITE CUANDO SE LO COMANDA?
//
//  PARA QUE: girar la rueda con el dedo y no ver flancos NO prueba que el
//  encoder este roto. Varios drivers brushless -y el FIT0441 es uno- generan
//  la señal FG a partir de los Hall del rotor y no la entregan igual cuando se
//  los back-drivea a mano. Si el encoder solo habla mientras el driver comanda,
//  toda la prueba del dedo mide otra cosa.
//
//  Este sketch comanda UNA rueda por vez, despacio, y cuenta flancos en SU pin
//  mientras dura. Si aparecen flancos comandando y no aparecen a mano, los
//  encoders estan sanos y el problema nunca existio.
//
//  SEGURIDAD:
//   - 10 segundos de cuenta regresiva antes de mover nada.
//   - una sola rueda por vez, esfuerzo 60 sobre 255 (~24%), 2 segundos.
//   - entre rueda y rueda, 2 segundos con TODO en 255 (FIT0441: 255 = quieto).
//   - al terminar, todo queda quieto y no vuelve a arrancar.
//  El robot tiene que estar EN EL AIRE o sostenido: con una sola rueda girando
//  se va a mover.
// ============================================================================
#include <Arduino.h>

struct Rueda { uint8_t pwm, dir, enc; const char *id; };
// mismos pines que main.cpp: Moto(pwm, dir, enc)
static const Rueda R[4] = {
    {29, 28, 27, "bl"},
    { 7,  6,  5, "fl"},
    {36, 37, 38, "br"},
    { 4,  3,  2, "fr"},
};
static const int ESFUERZO = 90;      // sobre 255. Por encima del arranque del FIT0441.
static const uint16_t MS_GIRO = 2000;

static void quietas()
{
    for (int i = 0; i < 4; i++) analogWrite(R[i].pwm, 255);   // 255 = quieto
}

void setup()
{
    Serial.begin(115200);
    for (int i = 0; i < 4; i++)
    {
        pinMode(R[i].pwm, OUTPUT);
        pinMode(R[i].dir, OUTPUT);
        // MISMA FRECUENCIA QUE EL FIRMWARE DE VERDAD (drivebase.cpp:15).
        // Sin esto el analogWrite sale al default del Teensy (~4,5 kHz) y el
        // FIT0441 no arranca: el test parece decir "el encoder no emite"
        // cuando en realidad el motor nunca giro. Le paso a este sketch en la
        // primera corrida del 2026-08-22.
        analogWriteFrequency(R[i].pwm, 50000);
        pinMode(R[i].enc, INPUT);
        digitalWrite(R[i].dir, LOW);
    }
    quietas();
    delay(500);
    Serial.println("# EL ROBOT VA A MOVER UNA RUEDA POR VEZ. Sostenelo en el aire.");
    for (int s = 10; s > 0; s--) { Serial.print("# arranca en "); Serial.println(s); delay(1000); }
    Serial.println("rueda,flancos_quieta,flancos_comandada,nivel_ini,nivel_fin");

    for (int i = 0; i < 4; i++)
    {
        // 1) referencia: cuantos flancos hay con la rueda QUIETA (deberia ser 0)
        uint32_t q = 0; int prev = digitalReadFast(R[i].enc);
        uint32_t t0 = millis();
        while (millis() - t0 < 500)
        { int v = digitalReadFast(R[i].enc); if (v != prev) { q++; prev = v; } }
        int ini = digitalReadFast(R[i].enc);

        // 2) comandada
        analogWrite(R[i].pwm, 255 - ESFUERZO);
        uint32_t c = 0; prev = digitalReadFast(R[i].enc);
        t0 = millis();
        while (millis() - t0 < MS_GIRO)
        { int v = digitalReadFast(R[i].enc); if (v != prev) { c++; prev = v; } }
        analogWrite(R[i].pwm, 255);
        int fin = digitalReadFast(R[i].enc);

        Serial.print(R[i].id);  Serial.print(",");
        Serial.print(q);        Serial.print(",");
        Serial.print(c);        Serial.print(",");
        Serial.print(ini);      Serial.print(",");
        Serial.println(fin);
        quietas();
        delay(2000);
    }
    quietas();
    Serial.println("# TERMINO. Todo quieto.");
}

void loop() { quietas(); }
