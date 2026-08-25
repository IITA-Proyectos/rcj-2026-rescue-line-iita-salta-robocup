/*
  drivebase.h - Library for controlling motors.
  Created by Heng Tenge, Jan 2, 2022.
*/
#include <Arduino.h>
#include "PID.h"

#ifndef drivebase_h
#define drivebase_h


// ============================================================================
//  FIX_LAZO_MOTOR - el lazo de velocidad por rueda
//
//  1 = lazo nuevo (feedforward + integrador acotado + piso de esfuerzo)
//  0 = lazo historico, el que compitio (integral pura + toggle de direccion)
//
//  DEJAR EL INTERRUPTOR: esto cambia el comportamiento de TODOS los movimientos,
//  incluidos los que hoy funcionan. Sin poder volver atras en una linea no se
//  puede saber si una corrida mejoro por el fix o empeoro por el fix.
//
//  QUE ARREGLA (los tres defectos verificados en el codigo historico):
//
//  a) EL LAZO ES CIEGO AL SENTIDO. `_realrpm` sale de 111111/promedio(intervalos)
//     -> siempre positiva. La consigna tambien llega en magnitud (DriveBase le
//     saca el signo y se lo da a un pin). Entonces, cuando el chasis ARRASTRA a
//     la rueda interna hacia adelante mientras se le pidio ir en reversa, el
//     encoder reporta un numero sano, el error da chico o negativo, y el lazo
//     BAJA el PWM. Como el FIT0441 a PWM bajo hace COAST (medido en banco por el
//     equipo el 2026-08-08), la rueda queda SUELTA y el robot gira menos todavia.
//     Se realimenta hacia el fallo.
//
//  b) NO HAY FEEDFORWARD. Con kp = 0 y kd = 0 el lazo es un integrador puro: el
//     PWM sale ENTERAMENTE de la medicion. Si la medicion miente (a), no hay
//     nada que sostenga el esfuerzo. El feedforward ancla el PWM al COMANDO.
//
//  c) EL TOGGLE DE DIRECCION. `if (_pwmVal < 10) _dir = !_dir;` invierte el pin
//     de direccion en CADA llamada mientras el esfuerzo sea bajo, o sea a la
//     frecuencia del loop(). Ademas ensucia pulseCount, que cuenta segun _dir.
//
//  EL PUNTO CLAVE ES MOTO_PISO: el integrador ya no puede llevar el esfuerzo a
//  cero mientras haya consigna. Sin ese piso, el feedforward solo retrasa el
//  desplome en vez de impedirlo. Dicho en una frase: el encoder no sabe para
//  donde gira la rueda, asi que no lo dejamos apagar el motor.
// ============================================================================
// POR DEFECTO 0 - A PROPOSITO. El binario de competencia NO cambia de
// comportamiento por un fix que todavia no corrio en el robot, y el entorno de
// diagnostico mide EL ROBOT ACTUAL, que es de lo que hay que sacar el veredicto.
// El fix se enciende explicitamente con el entorno `diagnostico_fix`.
#ifndef FIX_LAZO_MOTOR
#define FIX_LAZO_MOTOR 0
#endif

// PWM de arranque: lo que hace falta para vencer la friccion estatica.
#define MOTO_KS   8.0
// PWM por RPM de consigna. 215/159: el motor da 159 RPM a 12 V y necesita ~215
// de PWM para llegar. PROVISORIO - sale del banco (ensayo de escalones).
#define MOTO_KV   1.35
// El esfuerzo total nunca baja de esta fraccion del feedforward mientras haya
// consigna viva. No es 1.0 a proposito: si kV quedo alto, el integrador tiene
// que poder recortar. 0.5 deja recortar la mitad y no mas.
#define MOTO_PISO 0.5
// PISO ABSOLUTO ANTI-COAST. El de arriba es una FRACCION del feedforward, y el
// feedforward es proporcional a la consigna: en curva cerrada la consigna de la
// rueda interna es MINIMA (7,3 rpm en la rama de curva dura), asi que ese piso
// caia a 8,9 sobre 255 = 3,5% de PWM, apenas 11% por encima de MOTO_KS, que es
// lo que hace falta SOLO para vencer la friccion estatica SIN carga. O sea que
// el fix no sostenia nada justo en el caso que ataca.
// Este es un piso en unidades ABSOLUTAS de PWM y se MIDE en banco: el esfuerzo
// mas bajo al que el FIT0441 todavia empuja en vez de soltar (mismo ensayo que
// dio COAST el 2026-08-08).
//
// ESTUVO EN 45,0 Y ERA UN ERROR, por dos razones distintas:
//
//  1) 45 es MAS que el feedforward completo de TODA la curva. ff = 8 + 1,35*rpm
//     llega a 45 recien en 27,4 rpm, y el case 7 corre las curvas a 26 / 22 / 20
//     rpm. O sea que con el fix encendido las CUATRO ruedas se iban al piso en
//     cada curva y la consigna de rotation dejaba de significar algo: el piso
//     tapaba al lazo justo donde el lazo tenia que trabajar.
//
//  2) El comentario viejo decia que el piso tenia que quedar POR ENCIMA del
//     COLAPSO_PWM=30 del analizador "para poder distinguir las dos corridas".
//     Eso es al reves: con el piso en 45 la condicion pw < 30 no puede ocurrir
//     NUNCA, asi que la causa [A] es IMPOSIBLE POR CONSTRUCCION y el A/B entre
//     `diagnostico` y `diagnostico_lazo` da "[A] desaparecio" siempre, aunque
//     el control no haya mejorado nada. La herramienta no podia distinguir
//     ARREGLADO de TAPADO.
//     El orden correcto es el otro: el piso es una propiedad del FIT0441 y se
//     mide; el umbral del analizador es una propiedad del analisis y se ajusta
//     a lo que el piso resulte ser. Nunca al reves.
#define MOTO_PWM_ANTICOAST 20.0   // [PROVISORIO: lo fija el barrido del sabado]
// La consigna mas lenta que pide el seguidor de linea (LINE_PIVOT_SPEED del
// case 7). Vive aca y no en main.cpp para que el static_assert de abajo la vea.
#define MOTO_RPM_CURVA_MIN 20.0
// EL INVARIANTE, en el compilador y no en un comentario: el piso tiene que
// quedar por DEBAJO del feedforward de la consigna de curva mas lenta. Si no,
// el piso manda sobre el lazo en todas las curvas. Que el build falle es
// justamente el punto: este numero ya se subio de mas una vez.
static_assert(MOTO_PWM_ANTICOAST < MOTO_KS + MOTO_KV * MOTO_RPM_CURVA_MIN,
              "MOTO_PWM_ANTICOAST quedo por encima del feedforward de la curva "
              "mas lenta: el piso tapa al lazo en toda curva. Bajalo.");
// Por debajo de esta consigna se considera "parar" y se suelta (no hay freno).
#define MOTO_RPM_MIN 0.5

// ============================================================================
//  LA CADENA DEL ENCODER, EN UN SOLO LUGAR.
//  Estaba duplicada y en dos formas: el 111111 hardcodeado aca adentro y un
//  TICKS_VUELTA = 540 escrito a mano en analizar_diagnostico.py. Si el numero
//  real fuera otro, `rpm_real` -que es la UNICA referencia fisica del analisis-
//  sale con factor de escala y la causa G dispara (o no dispara) en todas las
//  ruedas, sin que nada se vea incoherente en el CSV.
//  SE VERIFICA EN BANCO: girar la rueda 10 vueltas a mano y leer el delta de
//  fl_raw. Tiene que dar TICKS_VUELTA*10 +/- 20, en las cuatro.
// ============================================================================
#define TICKS_VUELTA   540UL              // 6 pulsos/vuelta x 2 flancos x 45
#define US_POR_RPM     (60000000UL / TICKS_VUELTA)   // el historico 111111

class Moto
{
public:
    Moto(int pwmPin, int dirPin, int encPin, const char* id);
    double getSpeed();
    double setSpeed(int dir, double rpm);
    void updatePulse();
    void resetPulseCount();
    double getPWM();
    void reset();
    const char* id; // Identificador del motor

public:
    volatile long pulseCount;
    // DIAGNOSTICO (telemetria): cuenta cuantas veces se ejecuto el toggle
    // `if (_pwmVal < 10) _dir = !_dir;` de setSpeed. Ese toggle invierte el pin
    // de direccion en CADA llamada mientras el esfuerzo sea bajo, o sea a la
    // frecuencia del loop(). Si este contador sube durante una curva, la rueda
    // interna esta con el pin de direccion oscilando en vez de quieto.
    // Es un contador PURO: no cambia el comportamiento.
    volatile unsigned long dirToggles = 0;

    // CONTEO CRUDO de flancos del encoder: SIEMPRE incrementa, sin mirar _dir.
    // Hace falta porque pulseCount suma o resta segun _dir, y cuando se dispara
    // el toggle `if (_pwmVal < 10) _dir = !_dir` el signo alterna y el conteo
    // queda sucio JUSTO en el momento que queremos medir. Este contador dice si
    // la rueda se movio FISICAMENTE, sin depender de ninguna suposicion.
    // Es la referencia contra la que se chequea si _realrpm esta mintiendo.
    volatile unsigned long pulsesRaw = 0;

    // Esfuerzo TOTAL aplicado (feedforward + integrador, ya con el piso y el
    // clamp). Con el lazo historico coincide con _pwmVal; con el nuevo NO,
    // porque _pwmVal pasa a ser solo la parte integral. La telemetria tiene
    // que mostrar este, que es el que realmente sale por el pin.
    double _pwmTotal = 0;

    // ENVOLVENTE del ciclo de telemetria. La telemetria manda a 10 Hz (cada
    // 100 ms) pero el control corre a la frecuencia del loop(): una foto cada
    // 100 ms se pierde los transitorios, que es JUSTO donde vive el fallo de
    // la curva (el PWM se desploma en decenas de ms). Estos cuatro guardan el
    // minimo y el maximo vistos desde el ultimo frame, asi cada envio resume
    // la ventana entera en vez de dar un instante suelto.
    // Los actualiza setSpeed(); los resetea resetEnvolvente() al mandar.
    double _pwmMin = 0, _pwmMax = 0, _rpmMin = 0, _rpmMax = 0;
    bool   _envVirgen = true;
    void resetEnvolvente();
    int _pwmPin, _dirPin, _encPin;
    int _nAvg; // samples to take for speed computation
    int _dir;  // direction of rotation for setSpeed
    double _rpm, _pwmVal, _realrpm, _begin, _end, _now;
    double _rpmlist[4] = {(double)US_POR_RPM, (double)US_POR_RPM,
                          (double)US_POR_RPM, (double)US_POR_RPM};
    double _kp = 0, _ki = 22, _kd = 0;
    PID _motoPID = PID(&_realrpm, &_pwmVal, &_rpm, _kp, _ki, _kd, DIRECT);
};

// ============================================================================
//  EL ANCHO DE VIA EFECTIVO, MEDIDO. No es el del CAD y no puede serlo.
//
//  `steer()` reparte v_ext = vel y v_int = vel*(1 - 2*rot), asi que el giro
//  que sale es  omega = (v_ext - v_int) / b  = 2*vel*rot / b.  Ese `b` NO es
//  la distancia entre ruedas: es la que hace cerrar la cuenta CON el patinaje
//  del skid steer, que en un robot de 4 ruedas fijas de silicona A10 es
//  grande. Por eso se llama EFECTIVO y por eso se mide, no se deduce.
//
//  MEDIDO el 2026-08-26 sobre los 10 CSV del 22-ago (`radio_minimo.py`), como
//  b = dv_encoder / gz_giroscopio muestra a muestra, con el lag comando->giro
//  de 14 muestras aplicado:
//
//      pista_pivote35              21,35 cm      (C1 signo: 95,9 %)
//      pista_pivote_con_histeresis 21,38 cm      (C1 signo: 97,2 %)
//      pista_pivote_sin_histeresis 21,28 cm      (C1 signo: 95,2 %)
//      -------------------------------------------------------------
//      banco_piso_historico        22,41 cm      <- OTRA superficie
//      banco_piso_con_fixes        22,31 cm      <- y OTRO firmware
//
//  Las tres de pista coinciden en 0,5 % entre si, y el banco -que es otra
//  superficie y otro binario- cae a 7 %. Ese es el control C4 del falsador
//  FALSADOR-RADIO-MINIMO.md, y lo pasa.
//
//  SANIDAD FISICA: el CAD da 17,69 cm de ANCHO TOTAL del robot
//  (docs/tdp/TDP-IITA-2026.md:161), asi que la via real es MENOR que eso. Un
//  b_eff de 20,9 > 17,69 es exactamente lo que tiene que pasar: el skid steer
//  patina y necesita mas diferencial del que pediria la geometria pura. Si
//  hubiera dado MENOR que la via real, habria que sospechar del metodo.
//
//  SE REVALIDA: volver a correr `radio_minimo.py` sobre las corridas nuevas.
//  Si cambian las ruedas o la superficie, este numero cambia.
#define DRIVE_ANCHO_VIA_EFECTIVO 20.9

class DriveBase
{
public:
    DriveBase(Moto *fl, Moto *fr, Moto *bl, Moto *br);
    void steer(double speed, int direction, double rotation);
    // Pide un RADIO en centimetros en vez de una rotacion adimensional.
    //
    // POR QUE EXISTE: `rot` no es una magnitud fisica y no se puede razonar
    // con ella. El radio si. Y la diferencia importa porque
    //
    //     v_centro = vel * (1 - rot)
    //
    // o sea que en rot = 1 el robot NO AVANZA: gira en el lugar. Medido sobre
    // las corridas del 22-ago, el 51 % del tiempo que el robot gira lo hace
    // con radio < 2 cm y avanzando 0,81 cm/s. Para SEGUIR una curva de 4,9 cm
    // hay que TRAZAR 4,9 cm, no girar en el lugar.
    //
    //     rot = b_eff / (2*R + b_eff)
    //
    //   R = 4,9 cm (la curva mas cerrada del reglamento) -> rot = 0,681
    //   R = 15 cm  (curva suave de un tile)              -> rot = 0,411
    //
    // radius_cm <= 0 significa girar en el lugar (rot = 1), que es el
    // comportamiento de hoy y se conserva.
    // `sign` > 0 gira a la izquierda, igual que el signo de rotation.
    void steerRadius(double speed, int direction, double radius_cm, int sign);
    // Igual que steer(), pero escala la consigna de cada EJE por separado.
    // frontScale/rearScale en 0..1 multiplican la RPM pedida a las ruedas
    // delanteras y traseras. Sirve para correr el centro de rotacion hacia
    // un eje, que es lo que hacian las omni traseras.
    // RECUPERADA del desensamblado de .pio/build/teensy_hid_device/firmware.elf
    // (build del 2026-08-15 21:04, el que esta flasheado): la implementacion
    // se perdio al revertir drivebase.cpp el 16-ago y nunca estuvo commiteada,
    // dejando main.cpp llamando a una funcion inexistente -> no compilaba.
    void steerAxleBias(double speed, int direction, double rotation,
                       double frontScale, double rearScale);
    void reset();

public:
    Moto *_fl, *_fr, *_bl, *_br;
    double _speed, _rotation, _leftspeed, _rightspeed, _leftdir, _rightdir;
    int _direction;
};

#endif
