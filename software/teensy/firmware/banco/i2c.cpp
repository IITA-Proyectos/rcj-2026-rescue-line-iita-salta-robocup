// ============================================================================
//  banco/i2c.cpp - POR QUE NO ARRANCA EL FIRMWARE.
//
//  Sintoma: banco_barrido queda mudo con el LED apagado, o sea que setup() no
//  termina. En MODO_BANCO la unica llamada del setup que puede no volver es
//  bno.begin(), que habla I2C y NO tiene timeout. El `#if MODO_BANCO` que hace
//  no-fatal el fallo del BNO solo sirve si begin() VUELVE; si un esclavo dejo
//  SDA agarrado en bajo, no vuelve nunca y el cuelgue es mudo.
//
//  Este sketch va en orden, imprimiendo en cada paso, para que se vea EN QUE
//  PASO se cuelga aunque se cuelgue:
//    1. nivel de SDA y SCL ANTES de tocar el bus (leidos como entradas)
//    2. si SDA esta en bajo, recuperacion: hasta 9 pulsos de reloj bit-bang
//       para que el esclavo termine la transaccion que dejo a medias y suelte
//    3. escaneo del bus: que direcciones responden
//    4. recien ahi, el BNO en 0x28
//
//  El LED parpadea todo el tiempo desde el primer instante: si deja de
//  parpadear, el paso que se estaba imprimiendo es el que colgo.
// ============================================================================
#include <Arduino.h>
#include <Wire.h>

static const uint8_t SDA_PIN = 18, SCL_PIN = 19;   // Wire en Teensy 4.1

static void latido(int veces)
{
    for (int i = 0; i < veces; i++)
    { digitalWrite(LED_BUILTIN, HIGH); delay(60); digitalWrite(LED_BUILTIN, LOW); delay(60); }
}

void setup()
{
    pinMode(LED_BUILTIN, OUTPUT);
    Serial.begin(115200);
    uint32_t t0 = millis();
    while (!Serial && millis() - t0 < 3000) latido(1);   // no bloquea para siempre
    Serial.println("PASO 1: leyendo SDA/SCL sin tocar el bus");
    latido(2);

    pinMode(SDA_PIN, INPUT_PULLUP);
    pinMode(SCL_PIN, INPUT_PULLUP);
    delayMicroseconds(500);
    int sda = digitalReadFast(SDA_PIN), scl = digitalReadFast(SCL_PIN);
    Serial.print("  SDA="); Serial.print(sda);
    Serial.print("  SCL="); Serial.println(scl);
    if (sda && scl)      Serial.println("  -> bus LIBRE (los dos en alto, como corresponde)");
    else if (!sda)       Serial.println("  -> SDA EN BAJO: un esclavo tiene el bus agarrado");
    else                 Serial.println("  -> SCL en bajo: algo esta forzando el reloj");

    if (!sda)
    {
        Serial.println("PASO 2: recuperacion, hasta 9 pulsos de reloj");
        pinMode(SCL_PIN, OUTPUT);
        for (int i = 0; i < 9 && !digitalReadFast(SDA_PIN); i++)
        {
            digitalWrite(SCL_PIN, LOW);  delayMicroseconds(5);
            digitalWrite(SCL_PIN, HIGH); delayMicroseconds(5);
        }
        pinMode(SCL_PIN, INPUT_PULLUP);
        delayMicroseconds(500);
        Serial.print("  despues de los pulsos: SDA=");
        Serial.println(digitalReadFast(SDA_PIN));
    }
    else Serial.println("PASO 2: no hace falta recuperar");
    latido(3);

    Serial.println("PASO 3: Wire.begin() y escaneo");
    Wire.begin();
    Wire.setClock(100000);
    int n = 0;
    for (uint8_t a = 8; a < 120; a++)
    {
        Wire.beginTransmission(a);
        if (Wire.endTransmission() == 0)
        { Serial.print("  responde 0x"); Serial.println(a, HEX); n++; }
    }
    Serial.print("  dispositivos encontrados: "); Serial.println(n);
    if (n == 0) Serial.println("  -> NADIE responde. El BNO no esta en el bus.");
    latido(4);

    Serial.println("PASO 4: hablando con el BNO en 0x28 (chip id, registro 0x00)");
    Wire.beginTransmission(0x28);
    Wire.write((uint8_t)0x00);
    uint8_t e = Wire.endTransmission();
    Serial.print("  endTransmission="); Serial.println(e);
    if (e == 0)
    {
        Wire.requestFrom((uint8_t)0x28, (uint8_t)1);
        if (Wire.available())
        { Serial.print("  chip id = 0x"); Serial.println(Wire.read(), HEX);
          Serial.println("  (0xA0 es el BNO055 sano)"); }
        else Serial.println("  pidio el byte y no vino nada");
    }
    Serial.println("TERMINO SIN COLGARSE.");
}

void loop() { latido(1); delay(400); }
