/*
  test_4_motores.cpp — Prueba de banco de los 4 motores del robot Rescue Line.

  [IA 2026-08-15] Escrito por IA a pedido del equipo. Objetivo: verificar, motor
  por motor, que (a) el motor gira, (b) gira para el lado correcto y (c) su
  encoder cuenta pulsos. Recien despues mueve los 4 juntos.

  POR QUE NO USA DriveBase::steer():
  [IA 2026-08-15] steer() cierra el lazo con el PID de cada Moto, que esta
  configurado solo-integral (ki=22, kp=kd=0, ver drivebase.h). Si un encoder no
  esta conectado, getSpeed() devuelve 0, el error nunca baja y outputSum satura
  en 255 en ~1 s; como setSpeed() escribe analogWrite(pwm, 255 - pwmVal), eso
  deja el motor al maximo. Para un bring-up de cableado eso es exactamente lo
  que no queres. Este test maneja el PWM directo, sin PID.

  INVERSION DEL PWM:
  [IA 2026-08-15] La libreria escribe analogWrite(pwm, 255 - pwmVal), o sea que
  el driver es activo-bajo: duty 255 en el pin = motor parado, duty 0 = maximo.
  Este archivo respeta esa convencion (PWM_PARADO = 255). Verificado contra
  drivebase.cpp; CONFIRMAR EN BANCO que con el robot en pie de banco los motores
  arrancan quietos.

  COMO SE COMPILA Y SUBE:
      cd software/teensy/firmware
      pio run -e test_motores -t upload
      pio device monitor -b 115200
  (el env por defecto sigue siendo el firmware real: `pio run` no cambia)

  SEGURIDAD DE BANCO: levantar el robot con las ruedas al aire antes de probar.
*/

#include <Arduino.h>

// ---------------------------------------------------------------------------
// CONFIGURACION
// ---------------------------------------------------------------------------

#define FORWARD 0
#define BACKWARD 1

// Duty de prueba, 0..255 en escala "potencia" (no es lo que se escribe al pin).
// 90/255 ~= 35%: alcanza para mover el robot sin que salga disparado.
const uint8_t DUTY_PRUEBA = 90;

// Pin del switch de arranque (INPUT_PULLUP: 1 = apagado, 0 = encendido),
// igual que en src/main.cpp. Poner en false si el switch todavia no esta
// cableado y queres probar solo los motores.
const bool USAR_SWITCH = true;
const uint8_t PIN_SWITCH = 32;

const uint16_t MS_POR_SENTIDO = 1500; // cuanto gira cada motor en cada sentido
const uint16_t MS_PAUSA = 800;        // pausa entre pasos
const uint16_t MS_ENTRE_CICLOS = 3000;

// PWM que deja el motor parado (ver nota de inversion arriba).
const uint8_t PWM_PARADO = 255;

// ---------------------------------------------------------------------------
// MAPA DE PINES — copiado de src/main.cpp:137-140 (Moto: pwm, dir, enc)
// `espejado` = true para las ruedas derechas: DriveBase::steer() les manda
// !dir, porque estan montadas al reves respecto de las izquierdas.
// ---------------------------------------------------------------------------

struct Motor
{
    const char *id;
    uint8_t pwm;
    uint8_t dir;
    uint8_t enc;
    bool espejado;
};

const Motor MOTORES[4] = {
    {"FL", 7, 6, 5, false},
    {"FR", 4, 3, 2, true},
    {"BL", 29, 28, 27, false},
    {"BR", 36, 37, 38, true},
};

const uint8_t N_MOTORES = 4;

// ---------------------------------------------------------------------------
// CONTEO DE PULSOS — contadores propios, independientes de la clase Moto, para
// que el diagnostico no dependa de la libreria que estamos probando.
// ---------------------------------------------------------------------------

volatile uint32_t pulsos[N_MOTORES] = {0, 0, 0, 0};

void isrFL() { pulsos[0]++; }
void isrFR() { pulsos[1]++; }
void isrBL() { pulsos[2]++; }
void isrBR() { pulsos[3]++; }

uint32_t leerPulsos(uint8_t i)
{
    noInterrupts();
    uint32_t v = pulsos[i];
    interrupts();
    return v;
}

void resetPulsos()
{
    noInterrupts();
    for (uint8_t i = 0; i < N_MOTORES; i++)
        pulsos[i] = 0;
    interrupts();
}

// ---------------------------------------------------------------------------
// CONTROL DE BAJO NIVEL
// ---------------------------------------------------------------------------

void pararMotor(uint8_t i)
{
    analogWrite(MOTORES[i].pwm, PWM_PARADO);
}

void pararTodo()
{
    for (uint8_t i = 0; i < N_MOTORES; i++)
        pararMotor(i);
}

// dirRobot: FORWARD o BACKWARD, en marco del ROBOT (el espejado lo resuelve aca)
void moverMotor(uint8_t i, int dirRobot, uint8_t duty)
{
    int d = MOTORES[i].espejado ? !dirRobot : dirRobot;
    digitalWrite(MOTORES[i].dir, d);
    analogWrite(MOTORES[i].pwm, PWM_PARADO - duty);
}

bool switchApagado()
{
    if (!USAR_SWITCH)
        return false;
    return digitalRead(PIN_SWITCH) == 1;
}

// Espera `ms` vigilando el switch. Devuelve false si hubo que abortar.
bool esperar(uint16_t ms)
{
    uint32_t t0 = millis();
    while (millis() - t0 < ms)
    {
        if (switchApagado())
        {
            pararTodo();
            return false;
        }
        delay(5);
    }
    return true;
}

// ---------------------------------------------------------------------------
// PRUEBAS
// ---------------------------------------------------------------------------

// Gira un solo motor en un sentido y reporta cuantos pulsos conto su encoder.
bool probarMotor(uint8_t i, int dirRobot)
{
    const char *nombreDir = (dirRobot == FORWARD) ? "ADELANTE" : "ATRAS   ";
    uint32_t antes = leerPulsos(i);

    Serial.print("  ");
    Serial.print(MOTORES[i].id);
    Serial.print("  ");
    Serial.print(nombreDir);
    Serial.print("  ... ");

    moverMotor(i, dirRobot, DUTY_PRUEBA);
    bool ok = esperar(MS_POR_SENTIDO);
    pararMotor(i);

    uint32_t contados = leerPulsos(i) - antes;
    Serial.print(contados);
    Serial.print(" pulsos");
    if (contados == 0)
        Serial.print("   <-- SIN PULSOS: motor o encoder no responde");
    Serial.println();

    if (!ok)
        return false;
    return esperar(MS_PAUSA);
}

// Mueve los 4 a la vez, como lo hace el robot real.
bool probarTodos(int dirRobot)
{
    const char *nombreDir = (dirRobot == FORWARD) ? "ADELANTE" : "ATRAS";
    Serial.print("  LOS 4 ");
    Serial.print(nombreDir);
    Serial.print(" ... ");

    resetPulsos();
    for (uint8_t i = 0; i < N_MOTORES; i++)
        moverMotor(i, dirRobot, DUTY_PRUEBA);
    bool ok = esperar(MS_POR_SENTIDO * 2);
    pararTodo();

    for (uint8_t i = 0; i < N_MOTORES; i++)
    {
        Serial.print(MOTORES[i].id);
        Serial.print("=");
        Serial.print(leerPulsos(i));
        Serial.print("  ");
    }
    Serial.println();

    if (!ok)
        return false;
    return esperar(MS_PAUSA);
}

// ---------------------------------------------------------------------------

void setup()
{
    for (uint8_t i = 0; i < N_MOTORES; i++)
    {
        pinMode(MOTORES[i].pwm, OUTPUT);
        pinMode(MOTORES[i].dir, OUTPUT);
        pinMode(MOTORES[i].enc, INPUT_PULLUP);
        analogWriteFrequency(MOTORES[i].pwm, 50000); // igual que Moto::Moto()
        pararMotor(i);                               // arrancar quietos, antes que nada
    }

    attachInterrupt(digitalPinToInterrupt(MOTORES[0].enc), isrFL, CHANGE);
    attachInterrupt(digitalPinToInterrupt(MOTORES[1].enc), isrFR, CHANGE);
    attachInterrupt(digitalPinToInterrupt(MOTORES[2].enc), isrBL, CHANGE);
    attachInterrupt(digitalPinToInterrupt(MOTORES[3].enc), isrBR, CHANGE);

    pinMode(PIN_SWITCH, INPUT_PULLUP);
    pinMode(LED_BUILTIN, OUTPUT);

    Serial.begin(115200);
    delay(1500); // dar tiempo a abrir el monitor serie

    Serial.println();
    Serial.println("=== TEST DE LOS 4 MOTORES (lazo abierto, sin PID) ===");
    Serial.print("duty de prueba: ");
    Serial.print(DUTY_PRUEBA);
    Serial.println("/255");
    Serial.println("Ruedas AL AIRE. El switch (pin 32) corta el test.");
    Serial.println();
}

void loop()
{
    if (switchApagado())
    {
        pararTodo();
        Serial.println("SWITCH APAGADO — motores parados. Encender para probar.");
        digitalWrite(LED_BUILTIN, HIGH);
        delay(400);
        digitalWrite(LED_BUILTIN, LOW);
        delay(400);
        return;
    }

    digitalWrite(LED_BUILTIN, HIGH);

    Serial.println("--- Paso 1: un motor por vez ---");
    for (uint8_t i = 0; i < N_MOTORES; i++)
    {
        if (!probarMotor(i, FORWARD))
            return;
        if (!probarMotor(i, BACKWARD))
            return;
    }

    Serial.println("--- Paso 2: los 4 juntos ---");
    if (!probarTodos(FORWARD))
        return;
    if (!probarTodos(BACKWARD))
        return;

    pararTodo();
    digitalWrite(LED_BUILTIN, LOW);
    Serial.println("--- Ciclo completo. Repite en 3 s. ---");
    Serial.println();
    esperar(MS_ENTRE_CICLOS);
}
