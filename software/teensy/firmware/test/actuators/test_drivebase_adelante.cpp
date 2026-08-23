/*
  test_drivebase_adelante.cpp — Marcha adelante a velocidad baja y constante
  USANDO la libreria DriveBase (lazo cerrado con encoders + PID).

  [IA 2026-08-22] Escrito por IA a pedido del equipo. Contraparte de
  test_4_motores.cpp (lazo abierto): aquel prueba el CABLEADO, este prueba la
  LIBRERIA.

  ---------------------------------------------------------------------------
  POR QUE ESTE PROGRAMA MIDE ANTES DE MOVER
  ---------------------------------------------------------------------------
  [IA 2026-08-22] Hay una contradiccion SIN RESOLVER sobre la polaridad del PWM
  entre dos fuentes, las dos validas:

    (a) lib/drivebase/drivebase.cpp, Moto::setSpeed():
          analogWrite(_pwmPin, 255 - _pwmVal)
        => driver ACTIVO-BAJO: 255 en el pin = parado, 0 = potencia maxima.
        Es lo que corre el robot de Incheon desde hace meses.

    (b) Roboliga-2026/fabri/pruebasinencoder_copy_20260822210317.ino (22-ago-2026),
        que segun el equipo ANDA en el prototipo nuevo:
          analogWrite(pin, 0)   en setup como "parado"
          analogWrite(pin, 200) en loop  como "mover"
        => driver ACTIVO-ALTO: 0 = parado.

  Esa prueba "anda" bajo las DOS convenciones (con distinta potencia, y con o
  sin un arranque a fondo de 1 s), asi que no discrimina. Y el error es
  asimetrico: si el prototipo es ACTIVO-ALTO y le corremos DriveBase, entonces
  robot.steer(0, ...) escribe 255 al pin = POTENCIA MAXIMA. El "parar" seria
  "arrancar a fondo".

  Por eso la FASE 0 determina la polaridad midiendo pulsos de encoder, y si el
  robot NO es activo-bajo el programa ABORTA sin engranar el lazo cerrado.

  ---------------------------------------------------------------------------
  SEGUNDO RIESGO CUBIERTO: WIND-UP DEL PID
  ---------------------------------------------------------------------------
  [IA 2026-08-22] El PID de cada Moto es solo-integral (_kp=0, _ki=22, _kd=0,
  ver lib/drivebase/drivebase.h). Si un encoder no cuenta, getSpeed() da 0, el
  error nunca baja y outputSum satura en 255 en ~1 s => motor a fondo. Por eso:
    - FASE 1 verifica los 4 encoders ANTES de engranar el lazo cerrado.
    - FASE 2 lleva un watchdog: PWM saturado + encoder sin contar => para todo.

  ---------------------------------------------------------------------------
  USO
      pio run -e test_drivebase -t upload
      pio device monitor -b 115200
  Teclas en el monitor:  g = arrancar   s = parar   + / - = setpoint   ? = ayuda

  RUEDAS AL AIRE en la primera pasada.
*/

#include <Arduino.h>
#include <drivebase.h>

#define FORWARD 0
#define BACKWARD 1

// ---------------------------------------------------------------------------
// PARAMETROS
// ---------------------------------------------------------------------------

// Setpoint de DriveBase. NO son RPM reales: es la pseudo-unidad
// 111111 / microsegundos_por_flanco que devuelve Moto::getSpeed().
// [IA 2026-08-22] El firmware de Incheon usa 10..30 para maniobras lentas y 100
// para marcha rapida (ver runTime() en test/actuators/motors_move.cpp), asi que
// 15 es "bajo" en la escala que el equipo ya viene usando.
double setpoint = 15.0;
const double SETPOINT_MIN = 5.0;
const double SETPOINT_MAX = 40.0; // tope de ESTE test; steer() admite hasta 159

const uint16_t SEGUNDOS_DE_MARCHA = 15; // corta sola; con g se reengancha

// Switch de arranque (INPUT_PULLUP: 1 = apagado). Poner false si no esta cableado.
const bool USAR_SWITCH = true;
const uint8_t PIN_SWITCH = 32;

// Valores de lazo abierto, en escala "numero que se escribe al pin"
// (que eso sea mucha o poca potencia es lo que decide la FASE 0).
const uint8_t PIN_BAJO = 40;
const uint8_t PIN_ALTO = 215; // complemento: 255 - 40
const uint16_t MS_SONDEO = 250;

// [IA 2026-08-22] NO existe un valor de PWM que sea "parado" bajo las dos
// convenciones: 0 para en activo-alto y es potencia maxima en activo-bajo, y
// 255 al reves. Hasta que la FASE 0 mida, hay que apostar a una. Se elige 255
// (= activo-bajo), que es lo que hacen las tres fuentes independientes:
//   - lib/drivebase/drivebase.cpp:   analogWrite(pin, 255 - pwmVal)
//   - lib/basemovil/motor_bm.cpp:    analogWrite(pin, 255 - pwm)
//   - banco/prueba_basemovil.cpp, en el repo del robot nuevo, parkea en 255
//     citando una auditoria del 4-ago-2026: "PWM invertido: un pin flotante
//     puede ser velocidad maxima".
// La prueba sin encoder del 22-ago (Roboliga-2026/fabri/) parkea en 0, lo que
// sugeriria activo-alto, pero NO es evidencia: ese sketch se comporta de forma
// verosimil bajo las dos convenciones, y como el equipo trabaja con la bateria
// desconectada, el fogonazo de 1 s que delataria el activo-bajo ocurre sin
// potencia en los motores y nadie lo vería.
const uint8_t PARADO_ANTES_DE_MEDIR = 255;

// Valor de "parado" vigente. Arranca en la apuesta y se fija cuando la FASE 0
// determina la polaridad real.
uint8_t parkeoVigente = PARADO_ANTES_DE_MEDIR;

// ---------------------------------------------------------------------------
// MOTORES — mismos pines que src/main.cpp:137-140
// ---------------------------------------------------------------------------

Moto fl(7, 6, 5, "FL");
Moto fr(4, 3, 2, "FR");
Moto bl(29, 28, 27, "BL");
Moto br(36, 37, 38, "BR");
DriveBase robot(&fl, &fr, &bl, &br);

const uint8_t N = 4;
Moto *MOTOR[N] = {&fl, &fr, &bl, &br};
const char *NOMBRE[N] = {"FL", "FR", "BL", "BR"};
// DriveBase::steer() manda dir a las izquierdas y !dir a las derechas.
const bool ESPEJADO[N] = {false, true, false, true};

// ISRs: la libreria cuenta los flancos. Mismo cableado que src/main.cpp.
void isrFL() { fl.updatePulse(); }
void isrFR() { fr.updatePulse(); }
void isrBL() { bl.updatePulse(); }
void isrBR() { br.updatePulse(); }

// ---------------------------------------------------------------------------
// UTILIDADES
// ---------------------------------------------------------------------------

long pulsos(uint8_t i)
{
    noInterrupts();
    long v = MOTOR[i]->pulseCount;
    interrupts();
    return v;
}

bool switchApagado()
{
    if (!USAR_SWITCH)
        return false;
    return digitalRead(PIN_SWITCH) == 1;
}

// Escribe el pin PWM crudo, sin pasar por el PID.
void escribirCrudo(uint8_t i, int dirRobot, uint8_t valorPin)
{
    int d = ESPEJADO[i] ? !dirRobot : dirRobot;
    MOTOR[i]->_dir = d; // para que updatePulse() firme bien el signo
    digitalWrite(MOTOR[i]->_dirPin, d);
    analogWrite(MOTOR[i]->_pwmPin, valorPin);
}

void pararCrudo(uint8_t valorParado)
{
    for (uint8_t i = 0; i < N; i++)
        analogWrite(MOTOR[i]->_pwmPin, valorParado);
}

bool esperar(uint32_t ms, uint8_t valorParado)
{
    uint32_t t0 = millis();
    while (millis() - t0 < ms)
    {
        if (switchApagado())
        {
            pararCrudo(valorParado);
            Serial.println("!! SWITCH APAGADO - abortado.");
            return false;
        }
        delay(2);
    }
    return true;
}

// ---------------------------------------------------------------------------
// FASE 0 — determinar la polaridad del driver midiendo, no suponiendo
// ---------------------------------------------------------------------------

enum Polaridad
{
    INDETERMINADA,
    ACTIVO_BAJO,
    ACTIVO_ALTO
};

// Cuenta cuantos flancos genera el motor i con valorPin durante MS_SONDEO.
// Devuelve -1 si hubo que abortar.
long sondear(uint8_t i, uint8_t valorPin, uint8_t valorParado)
{
    long antes = pulsos(i);
    escribirCrudo(i, FORWARD, valorPin);
    bool ok = esperar(MS_SONDEO, valorParado);
    analogWrite(MOTOR[i]->_pwmPin, valorParado);
    long delta = pulsos(i) - antes;
    if (delta < 0)
        delta = -delta;
    if (!ok)
        return -1;
    delay(300); // que frene antes del siguiente sondeo
    return delta;
}

Polaridad detectarPolaridad(uint8_t i)
{
    Serial.println();
    Serial.println("--- FASE 0: polaridad del driver PWM (midiendo, no suponiendo) ---");
    Serial.print("    motor de sondeo: ");
    Serial.println(NOMBRE[i]);

    // Cada sondeo usa el extremo opuesto como "parado", asi que sea cual sea la
    // convencion real, el motor arranca quieto en los dos casos.
    long nBajo = sondear(i, PIN_BAJO, PIN_ALTO);
    if (nBajo < 0)
        return INDETERMINADA;
    Serial.print("    pin = ");
    Serial.print(PIN_BAJO);
    Serial.print("   -> ");
    Serial.print(nBajo);
    Serial.println(" flancos");

    long nAlto = sondear(i, PIN_ALTO, PIN_BAJO);
    if (nAlto < 0)
        return INDETERMINADA;
    Serial.print("    pin = ");
    Serial.print(PIN_ALTO);
    Serial.print("  -> ");
    Serial.print(nAlto);
    Serial.println(" flancos");

    if (nBajo == 0 && nAlto == 0)
    {
        Serial.println("    => NINGUN flanco. Motor sin alimentacion, driver sin");
        Serial.println("       habilitar, o encoder desconectado. No puedo decidir.");
        return INDETERMINADA;
    }
    if (nBajo > nAlto * 3 / 2)
    {
        parkeoVigente = 255; // en activo-bajo, 255 es el parado
        Serial.println("    => ACTIVO-BAJO: numero chico = mas potencia.");
        Serial.println("       Coincide con drivebase.cpp (255 - pwmVal). COMPATIBLE.");
        return ACTIVO_BAJO;
    }
    if (nAlto > nBajo * 3 / 2)
    {
        parkeoVigente = 0; // en activo-alto, 0 es el parado
        Serial.println("    => ACTIVO-ALTO: numero grande = mas potencia.");
        return ACTIVO_ALTO;
    }
    Serial.println("    => Ambiguo: los dos extremos dan parecido. No decido.");
    return INDETERMINADA;
}

// ---------------------------------------------------------------------------
// FASE 1 — cuentan los 4 encoders? (obligatorio antes de engranar el PID)
// ---------------------------------------------------------------------------

bool verificarEncoders(uint8_t valorMueve, uint8_t valorParado)
{
    Serial.println();
    Serial.println("--- FASE 1: los 4 encoders (lazo abierto, sin PID) ---");
    bool todosOk = true;

    for (uint8_t i = 0; i < N; i++)
    {
        long antes = pulsos(i);
        escribirCrudo(i, FORWARD, valorMueve);
        bool ok = esperar(MS_SONDEO, valorParado);
        analogWrite(MOTOR[i]->_pwmPin, valorParado);
        long delta = pulsos(i) - antes;

        Serial.print("    ");
        Serial.print(NOMBRE[i]);
        Serial.print("  delta pulsos = ");
        Serial.print(delta);
        if (delta == 0)
        {
            Serial.print("   <-- NO CUENTA");
            todosOk = false;
        }
        else if (delta < 0)
        {
            Serial.print("   <-- NEGATIVO yendo adelante: rueda o encoder invertido");
            todosOk = false;
        }
        Serial.println();

        if (!ok)
            return false;
        delay(250);
    }
    return todosOk;
}

// ---------------------------------------------------------------------------
// FASE 2 — marcha adelante con DriveBase, lazo cerrado
// ---------------------------------------------------------------------------

void encabezadoTelemetria()
{
    Serial.println();
    Serial.println("--- FASE 2: marcha adelante con DriveBase (lazo cerrado) ---");
    Serial.println("  t(s)  sp |  FL rpm/pwm |  FR rpm/pwm |  BL rpm/pwm |  BR rpm/pwm");
}

void imprimirTelemetria(uint32_t t0)
{
    Serial.print("  ");
    Serial.print((millis() - t0) / 1000.0, 1);
    Serial.print("  ");
    Serial.print(setpoint, 0);
    Serial.print(" |");
    for (uint8_t i = 0; i < N; i++)
    {
        Serial.print("  ");
        Serial.print(MOTOR[i]->_realrpm, 1);
        Serial.print(" / ");
        Serial.print((int)MOTOR[i]->_pwmVal);
        Serial.print(" |");
    }
    Serial.println();
}

// Devuelve false si el watchdog o el switch cortaron la marcha.
bool marchaAdelante()
{
    robot.reset(); // limpia el integrador de los 4 PID antes de engranar
    encabezadoTelemetria();

    uint32_t t0 = millis();
    uint32_t tImpresion = 0;
    long ultimoPulso[N];
    uint32_t tUltimoCambio[N];
    for (uint8_t i = 0; i < N; i++)
    {
        ultimoPulso[i] = pulsos(i);
        tUltimoCambio[i] = millis();
    }

    while (millis() - t0 < (uint32_t)SEGUNDOS_DE_MARCHA * 1000)
    {
        if (switchApagado())
        {
            robot.steer(0, FORWARD, 0);
            Serial.println("!! SWITCH APAGADO - marcha cortada.");
            return false;
        }

        // Comando por serial, sin bloquear
        if (Serial.available())
        {
            char c = Serial.read();
            if (c == 's')
            {
                robot.steer(0, FORWARD, 0);
                Serial.println("   [s] parado por el operador.");
                return true;
            }
            if (c == '+' && setpoint < SETPOINT_MAX)
                setpoint += 1;
            if (c == '-' && setpoint > SETPOINT_MIN)
                setpoint -= 1;
        }

        // ESTA es la llamada que se viene a ejercitar.
        robot.steer(setpoint, FORWARD, 0);

        // Watchdog de wind-up: PWM saturado y encoder sin contar.
        uint32_t ahora = millis();
        for (uint8_t i = 0; i < N; i++)
        {
            long p = pulsos(i);
            if (p != ultimoPulso[i])
            {
                ultimoPulso[i] = p;
                tUltimoCambio[i] = ahora;
            }
            else if (MOTOR[i]->_pwmVal > 240 && (ahora - tUltimoCambio[i]) > 600)
            {
                robot.steer(0, FORWARD, 0);
                pararCrudo(parkeoVigente);
                Serial.println();
                Serial.print("!! WATCHDOG: ");
                Serial.print(NOMBRE[i]);
                Serial.println(" con PWM saturado y encoder sin contar.");
                Serial.println("   El PID solo-integral estaba saturando. TODO PARADO.");
                Serial.println("   Revisar ese encoder antes de volver a intentar.");
                return false;
            }
        }

        if (ahora - tImpresion >= 250)
        {
            tImpresion = ahora;
            imprimirTelemetria(t0);
        }
    }

    robot.steer(0, FORWARD, 0);
    Serial.println("   Marcha completada.");
    return true;
}

// ---------------------------------------------------------------------------

Polaridad polaridad = INDETERMINADA;
bool esperandoOrden = true;

void ayuda()
{
    Serial.println("  teclas:  g = arrancar   s = parar   + / - = setpoint   ? = ayuda");
}

void setup()
{
    // [IA 2026-08-22] Lo PRIMERO, antes de cualquier otra cosa: dejar los 4 PWM
    // en el mejor candidato a "parado" mientras no se haya medido la polaridad
    // (ver PARADO_ANTES_DE_MEDIR arriba para por que se elige ese valor).
    for (uint8_t i = 0; i < N; i++)
        analogWrite(MOTOR[i]->_pwmPin, PARADO_ANTES_DE_MEDIR);

    attachInterrupt(digitalPinToInterrupt(5), isrFL, CHANGE);
    attachInterrupt(digitalPinToInterrupt(2), isrFR, CHANGE);
    attachInterrupt(digitalPinToInterrupt(27), isrBL, CHANGE);
    attachInterrupt(digitalPinToInterrupt(38), isrBR, CHANGE);

    pinMode(PIN_SWITCH, INPUT_PULLUP);
    pinMode(LED_BUILTIN, OUTPUT);

    Serial.begin(115200);
    delay(1500);

    Serial.println();
    Serial.println("=== PRUEBA DE DriveBase: marcha adelante, velocidad baja ===");
    Serial.println("RUEDAS AL AIRE. El switch (pin 32) corta todo.");
    ayuda();
    Serial.println("Mandar g para empezar.");
}

void loop()
{
    if (switchApagado())
    {
        pararCrudo(parkeoVigente);
        digitalWrite(LED_BUILTIN, LOW);
        delay(200);
        return;
    }

    if (esperandoOrden)
    {
        digitalWrite(LED_BUILTIN, LOW);
        if (!Serial.available())
        {
            delay(20);
            return;
        }
        char c = Serial.read();
        if (c == '?')
        {
            ayuda();
            return;
        }
        if (c == '+' && setpoint < SETPOINT_MAX)
        {
            setpoint += 1;
            Serial.print("  setpoint = ");
            Serial.println(setpoint, 0);
            return;
        }
        if (c == '-' && setpoint > SETPOINT_MIN)
        {
            setpoint -= 1;
            Serial.print("  setpoint = ");
            Serial.println(setpoint, 0);
            return;
        }
        if (c != 'g')
            return;
        esperandoOrden = false;
    }

    digitalWrite(LED_BUILTIN, HIGH);

    // FASE 0 — una sola vez por arranque de placa
    if (polaridad == INDETERMINADA)
    {
        polaridad = detectarPolaridad(0); // sondea FL

        if (polaridad == ACTIVO_ALTO)
        {
            pararCrudo(0); // en activo-alto, 0 es el parado
            Serial.println();
            Serial.println("###############################################################");
            Serial.println("# ABORTADO: este prototipo NO es compatible con DriveBase tal #");
            Serial.println("# como esta hoy.                                              #");
            Serial.println("#                                                             #");
            Serial.println("# El driver es ACTIVO-ALTO, pero Moto::setSpeed() escribe     #");
            Serial.println("# analogWrite(pin, 255 - pwmVal). En este robot eso significa #");
            Serial.println("# que robot.steer(0,...) manda POTENCIA MAXIMA, no para.      #");
            Serial.println("#                                                             #");
            Serial.println("# No engancho el lazo cerrado. Hay que decidir primero si se  #");
            Serial.println("# corrige drivebase o si se cambia el cableado del driver.    #");
            Serial.println("###############################################################");
            esperandoOrden = true;
            return;
        }
        if (polaridad == INDETERMINADA)
        {
            pararCrudo(parkeoVigente);
            Serial.println();
            Serial.println("ABORTADO: no pude determinar la polaridad. No engancho el PID.");
            Serial.println("Revisar alimentacion de motores, habilitacion del driver y encoder FL.");
            esperandoOrden = true;
            return;
        }
    }

    // FASE 1 — encoders (activo-bajo ya confirmado: mueve con 40, para con 255)
    if (!verificarEncoders(PIN_BAJO, parkeoVigente))
    {
        pararCrudo(parkeoVigente);
        Serial.println();
        Serial.println("ABORTADO: hay encoders que no cuentan (o cuentan al reves).");
        Serial.println("Con un encoder mudo, el PID solo-integral satura y manda el motor");
        Serial.println("a fondo. No engancho el lazo cerrado hasta que los 4 cuenten.");
        esperandoOrden = true;
        return;
    }
    Serial.println("    los 4 encoders cuentan. OK para lazo cerrado.");

    // FASE 2 — lo que se venia a probar
    marchaAdelante();

    pararCrudo(parkeoVigente);
    digitalWrite(LED_BUILTIN, LOW);
    Serial.println();
    Serial.println("Listo. g para repetir, + / - para cambiar el setpoint.");
    esperandoOrden = true;
}
