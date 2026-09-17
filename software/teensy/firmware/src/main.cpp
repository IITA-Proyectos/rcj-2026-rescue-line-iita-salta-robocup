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
#include <telemetria.h>

// ============================================================================
//
//   RescueBot IITA Salta  -  FIRMWARE DE COMPETENCIA DEL TEENSY 4.1
//   RoboCupJunior Rescue Line 2026
//
//   ESTE ES EL BINARIO QUE VA A LA PISTA. Se compila y se flashea asi, PELADO,
//   sin variables de entorno y sin elegir entorno:
//
//       pio run --target upload
//
//   Hasta el 2026-09-06 hacia falta esto ANTES de cada flasheo:
//       set PLATFORMIO_BUILD_FLAGS=-D LINE_STEER_GAIN=1.0 -D LINE_ROT_EXP=0.85
//            -D LINE_PIVOTE_ENTRA=1.01 -D LINE_RECTA_FACTOR=0.8
//            -D LINE_FRENO_DELANTERO=1 -D LINE_FRENO_STEER=0.70 -D LINE_FRENO_VEL=55
//   Esos siete valores ya son los DEFAULT del panel de abajo. El binario que
//   sale hoy es identico byte a byte al que salia con esa linea, verificado
//   funcion por funcion sobre el .elf. Si algun dia volves a usar la variable
//   de entorno, acordate de borrarla despues (`Remove-Item Env:PLATFORMIO_BUILD_FLAGS`):
//   en PowerShell queda pegada a esa consola y contamina todo build posterior.
//
//   ------------------------------------------------------------------------
//   MAPA DEL ARCHIVO  (en este orden)
//
//     1. PANEL DE CONFIGURACION ....... aca abajo. TODO lo que se toca.
//     2. Estado de la recuperacion de linea y del GAP
//     3. Objetos de hardware: servos, garra, IMU, motores, DriveBase
//     4. Estado global del robot y protocolo con la Raspberry
//     5. Sensores: ultrasonidos, ToF, color (APDS9960)
//     6. Serial con la Raspberry (serialEvent5)
//     7. Primitivas de movimiento: runTime / runAngle / runDistance
//     8. Evacuacion: colores, esquive, finales de carrera
//     9. Anti-atasco (loma de burro) y traccion en rampa
//    10. Telemetria JSON hacia la ESP32
//    11. setup()
//    12. loop()  ->  idle / arranque / lazo de linea / rescate / evacuacion
//
//   >>> QUE TRAE EL BINARIO QUE SE FLASHEA, Y POR QUE SORPRENDE <<<
//
//   El entorno `competencia` define MODO_DIAGNOSTICO = 1 y TELEMETRIA = 0.
//   O sea que el robot que corre en pista lleva el REGISTRADOR CSV DE 200 Hz
//   PRENDIDO y la TELEMETRIA A LA ESP32 APAGADA. No es un descuido: es el
//   binario con el que se tuneo toda la configuracion de movimiento que hoy
//   funciona (hasta el 2026-09-06 se flasheaba como `-e diagnostico_fix`).
//
//   Y NO ES GRATIS: DIAG_TICK() hace una lectura I2C del BNO055 a 50 Hz, que
//   son ~2 ms cada 20 ms, alrededor del 10 % del lazo. Apagar el registrador
//   haria el lazo MAS RAPIDO, o sea que el robot reaccionaria a la camara mas
//   seguido: es un cambio de comportamiento, no una limpieza. Si se hace, se
//   vuelve a probar en pista.
//
//   Para ver el robot en vivo por WiFi esta el entorno `telemetria`, que es el
//   intercambio inverso. NO es el binario tuneado.
//
//   COMO ANDA, EN UNA FRASE. La Raspberry manda por Serial5 una trama de 8
//   bytes con velocidad, angulo, un codigo de tarea y el plateado. El Teensy es
//   REACTIVO: traduce ese angulo a consignas de rueda con el PID de encoder de
//   drivebase, y ejecuta las maniobras (verde, 180, esquive, rescate) cuando el
//   codigo de tarea se lo pide. La camara decide QUE hacer; el Teensy, COMO.
//
//   ARCHIVOS HERMANOS
//     lib/drivebase/     steer(), el PID por rueda y la geometria del chasis
//     lib/claw/          la garra
//     src/diagnostico.h  registrador CSV de 200 Hz (SI entra en el binario que
//                        se flashea: ver el aviso de abajo)
//     platformio.ini     entornos de compilacion
//
// ============================================================================


// ############################################################################
// #                                                                          #
// #                      1.  PANEL DE CONFIGURACION                          #
// #                                                                          #
// #  Todo lo que se toca para cambiar como se mueve el robot esta aca.        #
// #  Cada constante va detras de un #ifndef, asi que ademas se puede pisar    #
// #  desde platformio.ini o con PLATFORMIO_BUILD_FLAGS sin editar el fuente.  #
// #                                                                          #
// ############################################################################

// ----------------------------------------------------------------------------
//  1.1  SEGUIMIENTO DE LINEA  (case 7 del switch de loop())
//
//  LA CADENA COMPLETA, de la camara a las ruedas:
//
//      byte angle (0..180)                        lo manda la Pi
//        -> steer = (angle - 90) / 90             -1.0 .. +1.0
//        -> steerCmd = constrain(steer * LINE_STEER_GAIN, -1, 1)
//        -> absSteer = |steerCmd|                 0.0 .. 1.0  SIEMPRE
//        -> rot      = absSteer ^ LINE_ROT_EXP    cuanto se cierra la curva
//        -> vel      = rampa cuadratica entre la velocidad base y LINE_PIVOT_SPEED
//        -> robot.steer(vel, FORWARD, +-rot)      o la rama de curva cerrada
//
//  DE DONDE SALE EL RADIO:  R = b_eff * (1 - rot) / (2 * rot),  con b_eff = 20,9 cm.
//  La VELOCIDAD NO APARECE en esa formula: ir mas lento NO cierra la curva.
//  Medido en pista el 26-ago-2026 (la corrida freno_ctrl_1 subio la curva a 55 y
//  dio igual que la base en las cinco columnas). Lo unico que cierra el radio es
//  subir `rot`.
//  Y el robot ABRE un 15 % respecto de lo que pide: medido en banco el 22-ago
//  sobre las 4 ruedas al piso, R_real / R_pedido = 1,15 constante en todo el rango.
// ----------------------------------------------------------------------------

// GANANCIA DE LA CAMARA AL COMANDO. Amplifica el angulo antes de decidir `rot`.
// En 1.0 el angulo pasa tal cual. Con 1.80 el cabeceo empeoro de -11,8 a -20,3
// grados y la banda media de rotation cayo de 32 % a 22 %: satura antes.
#ifndef LINE_STEER_GAIN
#define LINE_STEER_GAIN 1.0
#endif

// EXPONENTE DE LA RAMPA DE ROTATION:  rot = absSteer ^ LINE_ROT_EXP
//
// Es LA palanca del radio. La distancia que el robot recorre POR CADA GRADO que
// gira vale (1-rot)/(k*rot), y eso NO depende de la velocidad (verificado
// comparando dos corridas a 29 y 37 rpm: 0,49 contra 0,44 cm/grado). En la curva
// de 90 grados que fallaba: rot 0,30 -> 44 cm recorridos mientras gira;
// rot 0,87 -> 3,6 cm. Y el robot ve unos 2-3 cm de piso.
//
// MAS CHICO = MAS AGRESIVO (la curva se cierra antes). 1.0 es la rampa lineal.
#ifndef LINE_ROT_EXP
#define LINE_ROT_EXP 0.85
#endif

// >>> EL PIVOTE (giro sobre el eje) ESTA APAGADO, Y ES A PROPOSITO. <<<
//
// `absSteer` no puede pasar de 1.0 NUNCA -sale de un constrain(...,-1,1) antes
// del fabs-, asi que con el umbral de entrada en 1.01 la maquina de estados del
// pivote no se dispara jamas. Es un interruptor, no un descuido.
//
// POR QUE SE APAGO (medido el 30-ago-2026): con el pivote enganchado el robot se
// pasaba el 29,7 % del tiempo girando SIN AVANZAR (rot = 1 => v_centro = 0).
// Apagandolo eso cayo al 7,8 % y el robot empezo a tomar los codos. Es la razon
// principal por la que la configuracion actual funciona.
//
// PARA VOLVER A PRENDERLO: poner 0.60 aca. Toda la maquinaria de histeresis
// (LINE_PIVOTE_SALE / _CONFIRMA_MS / _MAX_MS) esta escrita mas abajo, intacta y
// esperando. Con 1.01 esa maquinaria se compila pero no se ejecuta nunca.
#ifndef LINE_PIVOTE_ENTRA
#define LINE_PIVOTE_ENTRA 1.01
#endif

// Umbral para SALIR del pivote (solo aplica si LINE_PIVOTE_ENTRA <= 1.0).
// Entra alto y sale bajo: sin esa histeresis el robot picoteaba el giro
// (3,6 entradas y salidas por segundo, 8 grados por episodio).
#ifndef LINE_PIVOTE_SALE
#define LINE_PIVOTE_SALE 0.15
#endif

// Cuanto tiene que SOSTENERSE la alineacion antes de soltar el pivote.
// En 0 = histeresis simple. OJO si lo subis: medido sobre 6 CSV, las rachas
// continuas de absSteer <= LINE_PIVOTE_SALE duran 50-75 ms de mediana, asi que
// con 300 ms el pivote NO sale nunca por alineacion -sale por el tope de tiempo-
// y el robot gira 2,5 s en el lugar. Eso es Lack of Progress delante del arbitro.
#ifndef LINE_PIVOTE_CONFIRMA_MS
#define LINE_PIVOTE_CONFIRMA_MS 0UL
#endif

// Tope de seguridad del pivote. Medido el 23-ago sobre tramos sostenidos, la
// tasa de giro satura en ~39 grados/s: 90 grados cuestan 2,3 s, asi que estos
// 2500 ms estan sobre el filo, no con margen.
#ifndef LINE_PIVOTE_MAX_MS
#define LINE_PIVOTE_MAX_MS 2500UL
#endif

// VELOCIDAD EN LA PARTE MAS CERRADA DE LA CURVA, en rpm. Es el techo de la rampa
// cuadratica de velocidad: en recta manda la velocidad base y hacia la curva
// sube hasta aca. Medido el 23-ago sobre tramos de signo constante de mas de
// 150 ms: 20 rpm dan 19,6 grados/s, 35 dan 39,3 y 50 dan 39,2. O sea que subir
// de 20 a 35 DUPLICA el giro y de 35 a 50 no compra nada.
#ifndef LINE_PIVOT_SPEED
#define LINE_PIVOT_SPEED 50
#endif

// VELOCIDAD EN RECTA, como fraccion de la velocidad base. 1.0 = sin cambio.
//
// Benjamin, 26-ago: "tiene que ir mas lento normalmente como un 50 % y de ahi
// girar brusco". Con 0.8 el robot va a 36 rpm en recta y salta a 55 en la curva
// cerrada (ver LINE_FRENO_VEL).
//
// OJO CON LO QUE ESTO NO HACE: bajar la velocidad NO cierra el radio (ver la
// formula de arriba: `vel` no aparece). LO QUE SI HACE es dar TIEMPO DE
// REACCION: a la mitad de velocidad el robot recorre la mitad de centimetros por
// frame, o sea el doble de frames por centimetro de pista. Con el lazo de vision
// a ~50 fps y el lag comando->giro de 60-70 ms medido, es el doble de margen
// para corregir antes de llegar al codo.
#ifndef LINE_RECTA_FACTOR
#define LINE_RECTA_FACTOR 0.8
#endif

// ----------------------------------------------------------------------------
//  1.2  RAMA DE CURVA CERRADA  ("freno delantero")
//
//  >>> LEER ESTO ANTES DE TOCAR NADA DE ESTE BLOQUE. <<<
//
//  EL NOMBRE MIENTE: HOY NO FRENA NINGUNA RUEDA. LINE_FRENO_FACTOR vale
//  DriveBase::kFrenoComoSteer, que es el CENTINELA DEL CONTROL NEGATIVO del
//  experimento: con ese valor, steerFrenoDelantero() reparte exactamente igual
//  que steer() (drivebase.cpp, la rama `if (frenoInterna >= kFrenoComoSteer)`).
//
//  ENTONCES, QUE HACE HOY ESTA RAMA? UNA SOLA COSA: cuando |steer| pasa de
//  LINE_FRENO_STEER, la velocidad deja de ser `vel * LINE_RECTA_FACTOR` y pasa a
//  ser LINE_FRENO_VEL fija. Es el escalon de velocidad recta->curva que pidio
//  Benjamin, y nada mas. (Tambien marca la rama 7 en la telemetria.)
//
//  Con los valores de hoy, en llano, el escalon en el umbral es:
//      absSteer 0,6999  ->  rot 0,7384 , velocidad 36
//      absSteer 0,7000  ->  rot 0,7385 , velocidad 55        (+53 % de golpe)
//  `rot` es continuo; la velocidad NO. Esta anotado a proposito: si algun dia
//  aparece un tiron entrando a la curva, empezar por aca.
//
//  POR QUE SE DEJO ASI Y NO SE BORRO: el escalon de velocidad es parte de la
//  configuracion que anda, y la funcion steerFrenoDelantero() es el unico camino
//  para probar el freno de verdad sin volver a escribirla. Para probarlo:
//      pio run -t upload  con  -D LINE_FRENO_FACTOR=-1.0   (delantera interna en
//      reversa, que es lo unico que cierra el radio de verdad: 3,48 cm contra
//      10,45 cm con la rueda quieta o al 50 %)
//  CUIDADO CON LA SILICONA: -1.0 es el mayor scrub de todo lo probado. Mirar las
//  ruedas entre pasadas.
// ----------------------------------------------------------------------------

// 1 = la rama de curva cerrada existe. 0 = una sola ley para todo el rango.
#ifndef LINE_FRENO_DELANTERO
#define LINE_FRENO_DELANTERO 1
#endif

// Desde que |steer| se entra a la curva cerrada.
#ifndef LINE_FRENO_STEER
#define LINE_FRENO_STEER 0.70
#endif

// Velocidad FIJA dentro de la curva cerrada, en rpm. Es la que usaban con la
// traccion anterior (2 fijas + 2 omni): 40 de base y 55 en la curva.
#ifndef LINE_FRENO_VEL
#define LINE_FRENO_VEL 55
#endif

// Consigna de la rueda DELANTERA INTERNA, como fraccion de LINE_FRENO_VEL:
//     DriveBase::kFrenoComoSteer   igual que steer()  <- CONTROL NEGATIVO, el de hoy
//                           0.0    quieta
//                          -0.5    reversa a media velocidad
//                          -1.0    reversa a velocidad completa
#ifndef LINE_FRENO_FACTOR
#define LINE_FRENO_FACTOR DriveBase::kFrenoComoSteer
#endif

// Multiplicador de `rot` SOLO dentro de la curva cerrada. 1.0 = sin cambio.
// Va aparte de LINE_ROT_EXP a proposito: el exponente toca TODO el rango
// -incluida la recta, donde bajarlo trajo cabeceo- y esto toca solo la curva.
#ifndef LINE_FRENO_ROT_MULT
#define LINE_FRENO_ROT_MULT 1.0
#endif

// ----------------------------------------------------------------------------
//  1.3  QUIEN DECIDE EL PLATEADO (entrada a la zona de evacuacion)
// ----------------------------------------------------------------------------

// 1 = manda el APDS9960, y la camara NO opina. El sensor va pegado al piso y
// calibrado sobre la pista real; ademas se exigen 4 ventanas filtradas seguidas
// (cada una promedia 3 muestras) antes de mandar el ACK, para que un reflejo
// aislado no meta al robot en rescate en medio de la linea.
// El byte `silver_line` del protocolo se sigue recibiendo por compatibilidad
// pero NO tiene autoridad.
// EN 0 el robot NUNCA entra a la zona de evacuacion. Es el interruptor de panico
// si el APDS empieza a dar falsos positivos en la sede.
#define PLATEADO_TEENSY     1

// ----------------------------------------------------------------------------
//  1.4  SENSORES: cuanto cuesta preguntarles
//
//  El lazo de linea corria a 30 ms de periodo (p50 sobre 7673 vueltas, con un
//  segundo modo en 65 ms) y la Pi manda a 66-86 Hz: tres de cada cuatro tramas
//  de vision se descartaban. La causa eran dos lecturas bloqueantes por vuelta.
//  Estas constantes son lo que quedo de arreglarlo.
// ----------------------------------------------------------------------------

// PING FRONTAL. `NewPing::ping_cm()` BLOQUEA hasta el timeout cuando no hay eco,
// y en linea el caso normal ES no tener nada adelante: se pagaban 8578 us por
// vuelta para que la unica pregunta del lazo -`front_distance < 12`- diera
// siempre "no hay nada". Con 30 cm de techo sobra el doble y el timeout cae a
// 1738 us. El valor va EXPLICITO en cada llamada porque set_max_distance()
// PERSISTE en el objeto, y evacuacion necesita el rango largo.
static const unsigned int PING_LINEA_CM = 30;    // el lazo de linea pregunta < 12
static const unsigned int PING_LARGO_CM = 150;   // evacuacion pregunta < 120

// Y no en cada vuelta: a 30 cm/s el robot avanza 1,2 cm en 40 ms, un decimo del
// umbral de 12 cm.
static const unsigned long PING_FRONTAL_PERIODO_MS = 40;

// Presupuesto de medicion de los VL53L0X. El default del sensor es 33 ms y el
// minimo admitido 20 ms; antes nunca se llamaba.
// OJO: hoy NADIE LEE LOS ToF. leer_tof() solo se llamaba desde el seguimiento de
// pared, que esta fuera del binario. Los dos sensores se inicializan y publican
// 0 mm en la telemetria: ese 0 significa "nadie pregunto", NO "sensor tapado".
static const uint32_t TOF_PRESUPUESTO_US = 20000;

// ----------------------------------------------------------------------------
//  1.5  WATCHDOG DE COMUNICACION CON LA RASPBERRY
//
//  Si la Pi se cuelga, el Teensy NO se entera solo: seguiria ejecutando el
//  ultimo `steer` para siempre y el robot se va de la pista creyendo que
//  obedece. Medido en una corrida grabada: 49 % de las muestras con mas de 1 s
//  sin trama nueva, una ventana continua de 17,1 s sobre el mismo comando y un
//  maximo de 27,0 s.
// ----------------------------------------------------------------------------

// Sin trama valida por mas de esto, el comando se considera rancio.
static const unsigned long WATCHDOG_MS = 400;

// Y ademas tiene que SOSTENERSE, porque durante runAngle/runTime nadie lee el
// serial y al volver de un esquive el comando viene legitimamente viejo (p50
// 1849 ms, max 4677 ms durante maniobra).
// La confirmacion es por TIEMPO y no por vueltas del lazo: el periodo del lazo
// bajo de ~30 ms a menos de 10 al sacar los ToF, y un criterio de seguridad no
// puede cambiar de significado porque se toque otra cosa.
static const unsigned long WATCHDOG_CONFIRMA_MS = 300;

// ----------------------------------------------------------------------------
//  1.6  SERIAL DURANTE LAS MANIOBRAS  (decision de diseno, no hay constante)
//
//  runTime / runAngle / runDistance / runDistanceEvacuacion NO parsean el serial
//  mientras corren: leen UN byte por vuelta y LO TIRAN, solo para que el buffer
//  de Serial5 no se desborde. O sea que una maniobra empezada SE TERMINA, y el
//  robot no cambia de idea a mitad de un giro de 90 grados por una trama nueva.
//
//  El precio, y hay que saberlo: al volver de la maniobra el parser arranca
//  desincronizado y el watchdog puede ver el comando como fresco cuando tiene
//  segundos. Se resincroniza solo en el siguiente byte de sync (255/254/253/252).
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
//  1.7  INTERRUPTORES DE COMPILACION
// ----------------------------------------------------------------------------

// MODO_DIAGNOSTICO: registrador CSV de 200 Hz por USB. LO ENCIENDE EL ENTORNO
// `competencia`, o sea que ESTA PRENDIDO EN EL ROBOT QUE CORRE EN PISTA.
// Ver src/diagnostico.h y el aviso de la cabecera del archivo.
// Va ACA ARRIBA porque de el dependen las macros DBG_*, que se usan en todo el
// archivo: en modo diagnostico el USB transporta UNICAMENTE el CSV, y cualquier
// print suelto se mete adentro de una linea de datos y la corrompe en silencio.
#ifndef MODO_DIAGNOSTICO
#define MODO_DIAGNOSTICO 0
#endif

#if MODO_DIAGNOSTICO
  #define DBG_PRINT(...)   do { } while (0)
  #define DBG_PRINTLN(...) do { } while (0)
#else
  #define DBG_PRINT(...)   Serial.print(__VA_ARGS__)
  #define DBG_PRINTLN(...) Serial.println(__VA_ARGS__)
#endif

// ----------------------------------------------------------------------------
//  1.8  RECUPERACION DE LINEA PERDIDA  (green_state = 4)
//
//  La Raspberry manda GS=4 cuando confirmo que se quedo sin linea, y en el MISMO
//  byte `angle` de esa trama pone el ultimo rumbo confiable de su cadena
//  CAMINO+MONO (convertido a la convencion historica: derecha negativa).
//
//  LA MANIOBRA, y es UN EPISODIO, no un nivel que se pueda repetir sin fin:
//    1. RETROCEDER una sola vez.       La linea no desaparece por casualidad:
//       desaparece porque el robot se paso. Un segundo antes la tenia abajo.
//       Retroceder rehace el camino; girar a ciegas puede alejarlo mas.
//    2. QUEDARSE QUIETO y volver a mirar, para que CAMINO opine desde la pose
//       nueva. Todo rumbo visto MIENTRAS retrocedia se descarta.
//    3. PIVOTAR una sola vez hacia el lado que dijo CAMINO, con el signo
//       CONGELADO. Si no hay rumbo fresco, no inventa lado: se queda quieto.
//    4. Si la Pi sigue mandando 4 despues de eso, NO repite: espera.
//
//  Los cinco archivos de la cadena CAMINO+MONO tienen que estar en la Pi o esto
//  falla en silencio (el Teensy se queda esperando un rumbo que no llega).
// ----------------------------------------------------------------------------
#define LINEA_PERDIDA_GS          4       // el codigo que manda la Raspberry
#define RECUP_VEL                25       // rpm, despacio: se esta yendo a ciegas
#define RECUP_MS                400       // retroceso: gana campo visual antes de decidir el lado
#define RECUP_STEER_MIN          0.10     // 9 grados de CAMINO: debajo no se elige lado
#define RECUP_GIRO_VEL           35       // velocidad del pivote de busqueda
#define RECUP_PIVOTE_ROT         1.00     // giro sobre el eje: no consume zona mientras se orienta
#define RECUP_GIRO_BASE_GRADOS   28.0f    // base estable: el test de 45 deg funciono bien
#define RECUP_GIRO_CAMINO_K      0.22f    // 2026-09-12: un poco menos agresivo; BASE=28 intacta
#define RECUP_GIRO_DER_EXTRA_GRADOS 0.0f  // solo recovery DERECHA. 0 = igual que completo_auth_1; probar 10 en banco
#define RECUP_GIRO_MIN_GRADOS    35.0f    // nunca corregir menos que esto
#define RECUP_GIRO_MAX_GRADOS    58.0f    // evita los pivotes exagerados de 70-90 deg
#define RECUP_GIRO_MAX_MS        1600UL   // failsafe del pivote dirigido
#define RECUP_REANALISIS_MS      120UL    // quieto despues de retroceder, para que CAMINO mire
#define RECUP_REANALISIS_EDAD_MS 180UL    // solo se acepta rumbo recibido DESPUES del retroceso
#define RECUP_REARME_TEENSY_MS   300UL    // GS=0 continuo exigido antes de permitir otro episodio
#define RECUP_WAIT_ACTION        21       // accion interna: GS4 no habilitado -> quieto

// ----------------------------------------------------------------------------
//  1.9  GAP (linea cortada) Y FAIL-SAFE
//  Pi -> Teensy: GS 18 = avanzar recto buscando el otro lado del gap
//                GS 19 = fail-safe, parar
//  Teensy -> Pi: los cuatro ACK de abajo
// ----------------------------------------------------------------------------
#define GAP_BUSQUEDA_GS          18
#define PERDIDA_FAILSAFE_GS      19
#define GAP_ACTION               22       // accion interna del switch
#define PERDIDA_FAILSAFE_ACTION  23       // accion interna del switch
#define GAP_VEL                  25
#define GAP_MAX_CM               50       // el reglamento da gaps de hasta 20 cm
#define GAP_MAX_MS               8000UL
#define GAP_ORIGIN_MARGIN_CM     1
#define TEENSY_ACK_GAP_ORIGIN    238      // 0xEE  ya paso el punto donde perdio la linea
#define TEENSY_ACK_RETRO_DONE    239      // 0xEF  termino de retroceder
#define TEENSY_ACK_GAP_TIMEOUT   240      // 0xF0  se acabo el margen del gap
#define TEENSY_ACK_RESCATE_APDS  241      // 0xF1  el APDS confirmo plateado
#define TEENSY_ACK_PIVOTE_DONE   237      // 0xED  termino el pivote de recuperacion (COMPLETAR_GIRO en la Pi)

// Antes de entrar a rescate, el APDS mira SOLO la ultima recuperacion FISICA.
// Si fue lateral reciente: deshace LA MITAD del giro real, en sentido contrario.
// Si fue RECTA/GAP, no hubo recovery reciente, o la memoria vencio: NO gira.
#define SILVER_REC_MEMORY_MS       5000UL
#define SILVER_REC_UNDO_FACTOR     0.50f
#define SILVER_REC_UNDO_VEL        25
#define SILVER_REC_UNDO_MAX_MS     1400UL

// SALIDA DE EVACUACION POR EL NEGRO (accionNegro). El robot va pegado a una
// pared cuando el APDS ve la cinta negra de salida, y por eso queda torcido
// respecto de la cinta. Al verla, gira NEGRO_SALIDA_GIRO_GRADOS hacia el lado
// CONTRARIO a la pared.
// DE QUE LADO ESTABA LA PARED lo dice una MEMORIA que se refresca durante toda
// la evacuacion con los ultrasonidos: el ultimo lado que tuvo pared a menos de
// _PARED_MAX_CM. NO se decide con la lectura del instante del negro: justo en
// la salida la pared se abre donde esta la cinta y ese ultrasonido ve vacio.
// Si la memoria tiene mas de _MEMORIA_MS, o nunca hubo pared, no gira.
// 0 = comportamiento anterior (recto, sin giro).
#define NEGRO_SALIDA_GIRO          1
#define NEGRO_SALIDA_GIRO_GRADOS   30.0
#define NEGRO_SALIDA_PARED_MAX_CM  60
#define NEGRO_SALIDA_MEMORIA_MS    5000UL
#define NEGRO_SALIDA_MUESTREO_MS   100UL     // en el lazo recto inicial, que no lee ultrasonidos

// Memoria de pared en evacuacion: -1 izquierda, +1 derecha, 0 nunca vio pared.
static int g_evac_pared_lado = 0;
static unsigned long g_evac_pared_ms = 0;

// ############################################################################
// #              2.  ESTADO DE LA RECUPERACION Y DEL GAP                     #
// ############################################################################

static int g_recup_signo = 0;             // -1/+1, CONGELADO al perder la linea
// Cuando llega una trama GS=4 el byte `angle` YA NO es control normal: es el
// heading congelado de CAMINO+MONO. Esta copia es la UNICA fuente para elegir el
// lado del giro de recuperacion; el steer normal del case 7 no se reutiliza.
static double g_recup_rumbo_camino_rx = 0.0;
static unsigned long g_recup_rumbo_camino_rx_ms = 0;

// ANTIFALSOS / ANTI-RETRIGGER. La Pi hace el filtro fuerte de linea; esto es la
// SEGUNDA barrera, del lado del Teensy, contra frames viejos o rebotes del serial.
static bool g_recup_episodio_activo = false;
static bool g_recup_habilitada = false;
static unsigned long g_recup_gs0_desde = 0;
// Fases fisicas del MISMO episodio: evitan repetir el retroceso o el giro
// mientras la Raspberry siga mandando GS4.
static bool g_recup_retroceso_hecho = false;
static bool g_recup_giro_hecho = false;

static bool g_gap_activo = false;
static bool g_gap_origen_enviado = false;
static bool g_gap_timeout_enviado = false;
static long g_gap_retro_pulsos = 0;
static long g_gap_inicio_fl = 0;
static long g_gap_inicio_fr = 0;
static unsigned long g_gap_inicio_ms = 0;

// Memoria PERSISTENTE para la entrada al plateado.
// No se borra cuando GS0 cierra el episodio de recovery: justamente debe
// sobrevivir hasta que el APDS encuentre el plateado unos instantes despues.
enum SilverRecKind : int8_t {
    SILVER_REC_NONE = 0,
    SILVER_REC_RECTA = 1,
    SILVER_REC_LATERAL = 2
};
static SilverRecKind g_silver_rec_kind = SILVER_REC_NONE;
static int g_silver_rec_pivot_sign = 0;       // signo FISICO usado por robot.steer()
static float g_silver_rec_actual_deg = 0.0f;  // yaw realmente recorrido, no objetivo teorico
static unsigned long g_silver_rec_ms = 0;

static long gapPulsosDesdeInicio();
static void resetGapState();
#ifndef TELEMETRIA          // el entorno `competencia` la APAGA por -D
#define TELEMETRIA          1
#endif       // TELEMETRIA: 1=envia TODOS los valores por Serial8 a la ESP32-MINI (AP+GUI) | 0=off
#define TELEMETRIA_DEBUG_USB 0      // DIAGNOSTICO: 1=imprime por USB (COM del Teensy) cuantos frames salieron por Serial8. Util si la GUI queda en "MODO DEMO".
// ============================================================================
//  TELEMETRIA — Teensy -> ESP32-MINI por Serial8 (RX=pin34 / TX=pin35, 3.3V, 115200)
//  La ESP32-MINI monta un AP WiFi y sirve una GUI web con TODOS los valores de
//  control. Es 100% NO INTRUSIVA: escribe una linea JSON por Serial8 a 10 Hz y,
//  si el buffer TX no tiene lugar, DESCARTA el frame (nunca frena el control).
//  Firmware ESP32 + GUI: software/esp32/telemetria/  (ver README ahi).
//  Serial8 es SOLO telemetria: si el enlace muere, el control ni se entera.
// ============================================================================
// ============================================================================
//  GLOBALES DE DIAGNOSTICO - fuera de cualquier #if.
//  Los usan TANTO la telemetria JSON (entorno normal) COMO el registrador CSV
//  de alta frecuencia (que es el que corre en pista y apaga TELEMETRIA). Si viven
//  adentro de #if TELEMETRIA, el binario de diagnostico no compila.
// ============================================================================
// DIAGNOSTICO DE CURVAS: que rama del case 7 se ejecuto en la ultima vuelta.
//   0 = recto  1 = curva  2 = curva dura  3 = pivot  9 = atasco
// Sin esto, en la telemetria no hay forma de saber por que rama paso el robot
// cuando se fue de la linea: se ve el steer que llego pero no que se hizo con el.
//  -1 = el movimiento en curso NO viene del case 7 (es un runAngle/runTime de
//       una maniobra: verde, 180, esquive). Sin esta marca el valor queda
//       PEGADO del ultimo linetrack y el analizador cree que la curva la pidio
//       la vision cuando en realidad fue una maniobra programada.
int g_line_branch = 0;

// millis() de la ULTIMA trama COMPLETA recibida de la RPi (los 4 pares
// sync+dato). Si la vision se cuelga, la Teensy NO se entera: sigue usando el
// ultimo `steer` para siempre y el robot se va derecho creyendo que obedece.
// Con esto, en la telemetria se ve al instante si el comando esta rancio.
unsigned long g_last_rx_ms = 0;
unsigned long g_wd_stale_ms = 0;  // desde cuando la trama esta vieja (0 = no)
unsigned long g_wd_ref_ms = 0;    // referencia si NUNCA llego una trama
bool g_wd_activo  = false;  // el watchdog esta frenando

// Copia INTOCABLE del ultimo angulo que mando la RPi. La global `steer` la
// pisa el propio firmware (por ejemplo la alineacion por IMU), asi que no
// sirve para responder 'que le pidio la vision'. Solo la escribe serialEvent5.
double g_rx_steer = 0;

// Periodo del loop(): el actual y el PICO desde el ultimo frame de telemetria.
// El control de ruedas vive dentro del loop(); si el loop se traba, las ruedas
// se quedan con la ultima consigna. El pico es lo que delata esos parones.
unsigned long g_loop_dt = 0, g_loop_dt_max = 0;

#if TELEMETRIA
// ============================================================================
//  VELOCIDAD DEL ENLACE Teensy -> ESP32  (Serial8)
//
//  >>> SI CAMBIAS ESTE NUMERO, CAMBIA TAMBIEN  UART_BAUD  EN
//  >>> software/esp32/telemetria/src/main.cpp  Y FLASHEA LAS DOS PLACAS. <<<
//  Si quedan distintos, la ESP32 recibe basura y la telemetria muere entera
//  (el control no se entera: Serial8 es SOLO telemetria).
//
//  POR QUE 230400 Y NO 115200: el frame v2 mide ~1000 bytes. A 115200 (1152
//  bytes utiles por cada 100 ms) eso es el 87% del enlace, y con el buffer TX
//  tan lleno cualquier demora hace que enviar() descarte el frame. Ese descarte
//  es SILENCIOSO -la telemetria es best-effort por diseño- asi que se ve como
//  datos que faltan, no como un error: es exactamente el sintoma que ya medimos
//  (7,7 Hz en vez de 10 y huecos de 1 s). A 230400 el mismo frame usa el 43% y
//  queda margen para crecer.
//  230400 y no mas: es el salto conservador, sigue siendo un baud estandar que
//  cualquier adaptador USB-TTL levanta si algun dia hay que pinchar el cable
//  para diagnosticar, y el cable es corto y a 3.3 V adentro del robot.
// ============================================================================
#define TLM_BAUD 230400

Telemetria telemetria(Serial8, 100);   // 100 ms => 10 Hz
void enviarTelemetria();

// ============================================================================
//  DIAGNOSTICO DE VERDES — para VER si el green_state llega y se confirma en la
//  Teensy (el problema de los verdes 1/2/3). Cuenta, por tipo (1=izq,2=der,3=doble):
//    g_rx   : cuantos verdes DISTINTOS llegaron de la RPi (flanco, no repeticion)
//    g_act  : cuantos se CONFIRMARON en el re-chequeo y ejecutaron el giro
//    g_kill : cuantos MATO el re-chequeo (el verde se apago/cambio durante el avance)
//  g_last_recheck_gs = green_state visto en el ultimo re-chequeo (0 = se apago).
//  Son contadores PUROS: no cambian en nada el comportamiento del robot.
// ============================================================================


unsigned long g_rx[4]   = {0, 0, 0, 0};
unsigned long g_act[4]  = {0, 0, 0, 0};
unsigned long g_kill[4] = {0, 0, 0, 0};
int  g_last_type = 0;              // ultimo verde recibido (1/2/3)
unsigned long g_last_ms = 0;       // millis de la ultima llegada
int  g_last_recheck_gs = -1;       // green_state en el ultimo re-chequeo
int  g_prev_seen = 0;              // estado previo para detectar flancos

// Llamar donde la RPi setea green_state: cuenta cada verde nuevo (flanco).
inline void telemGreenRx(int gs)
{
    if (gs != g_prev_seen)
    {
        if (gs >= 1 && gs <= 3)
        {
            g_rx[gs]++;
            g_last_type = gs;
            g_last_ms = millis();
        }
        g_prev_seen = gs;
    }
}

// Llamar en el re-chequeo de las maniobras de verde (case 5/6/14), con el
// green_state que se vio al re-chequear. Registra si giro o si lo mato.
inline void telemGreenResultado(int tipo, int gsEnRecheck)
{
    if (tipo < 1 || tipo > 3) return;
    g_last_recheck_gs = gsEnRecheck;
    if (gsEnRecheck == tipo) g_act[tipo]++;
    else                     g_kill[tipo]++;
}

// ============================================================================
//  QUE PRIMITIVA DE MOVIMIENTO ESTA CORRIENDO  ->  campo "prim" del frame
//
//  POR QUE HACE FALTA: cuando en la telemetria se ve que el robot se quedo
//  quieto, hoy no hay forma de saber si estaba en un runDistance esperando los
//  pulsos, en un runAngle que no llega al angulo, o directamente trabado.
//
//  POR QUE RAII Y NO UNA ASIGNACION A MANO: las primitivas SE ANIDAN. La cadena
//  real es runDistance -> serviceMotionBackgroundTasks -> actualizarRescate ->
//  runTime, o sea hasta 4 niveles. Si al salir de runTime pusieramos g_prim = "",
//  le borrariamos el nombre al runDistance que TODAVIA esta corriendo. Por eso
//  cada primitiva GUARDA el valor anterior al entrar y lo RESTAURA al salir.
//
//  El destructor corre en toda salida de scope: por break, por timeout y por
//  return temprano. Hoy estas funciones tienen una sola salida, pero el return
//  temprano es idioma corriente en este archivo (ver get_color_fresh), asi que
//  esto es inmune por construccion al dia que alguien agregue uno.
//
//  const char* a un literal, NUNCA String: un String aca metería alloc/free de
//  heap adentro del lazo de movimiento (fragmentacion y jitter en el control).
//  Con const char* el costo es UN store de puntero por LLAMADA -no por vuelta
//  del while-, o sea ~2 ciclos. En un Cortex-M7 de un solo nucleo y sin
//  preemption, un store alineado de 32 bits es atomico: no hace falta volatile
//  ni seccion critica (ninguna ISR toca esto).
// ============================================================================
const char *g_prim = "";

struct PrimScope
{
    const char *prev;
    explicit PrimScope(const char *n) : prev(g_prim) { g_prim = n; }
    ~PrimScope() { g_prim = prev; }
};
#define PRIM(nombre) PrimScope _prim_(nombre)

// ============================================================================
//  CABECERA DE CORRIDA (campo "hdr")  ->  con que firmware se hizo esta corrida
//
//  TLM_COMMIT lo define git_commit.py en tiempo de compilacion. Como es un
//  string LITERAL, se concatena aca abajo dentro de la cadena y NO gasta un
//  argumento del snprintf: sale gratis en tiempo de ejecucion.
//  El #ifndef es la red por si alguien compila sin el extra_script.
// ============================================================================
#ifndef TLM_COMMIT
#define TLM_COMMIT "nodef"
#endif
static const char HDR_JSON[] = "\"hdr\":{\"commit\":\"" TLM_COMMIT "\",\"tlm\":2},";
#else
inline void enviarTelemetria() {}
inline void telemGreenRx(int) {}
inline void telemGreenResultado(int, int) {}
// Con TELEMETRIA en 0 el marcador desaparece en el preprocesador: no queda ni
// la variable ni el objeto. No depende de que el optimizador lo saque.
#define PRIM(nombre) ((void)0)
#endif


// ############################################################################
// #                                                                          #
// #  3.  HARDWARE: servos, garra, IMU, motores, tren motriz                  #
// #                                                                          #
// #  Los 4 motores son FIT0441 con encoder. El reparto entre ruedas y el PID #
// #  por rueda viven en lib/drivebase/. `DriveBase robot(&fl,&fr,&bl,&br)` es#
// #  el unico objeto por el que pasa TODO el movimiento del robot.           #
// #                                                                          #
// #  TRACCION: 4 ruedas FIJAS de silicona (antes eran 2 fijas + 2 omni atras).#
// #  Con 4 fijas el centro de giro NO se puede correr por consigna: FL y BL  #
// #  comparten posicion lateral y por lo tanto velocidad de rodadura. Solo se#
// #  puede correr por DINAMICA, y eso se mide, no se calcula.                #
// ############################################################################

// SERVOS
DFServo sort(23, 540, 2390, 274);
DFServo left(14, 540, 2390, 274);
DFServo right(15, 540, 2390, 274);
DFServo lift(22, 540, 2390, 274);
DFServo deposit(12, 540, 2390, 274);
Claw claw(&lift, &left, &right, &sort, &deposit);

// CONSTANTS //
#define FORWARD 0         // Def direction ADELANTE
#define BACKWARD 1        // Def direction ATRAS
#define RELAY 0
#define BUZZER 31         // Definicion de PIN BUZZER
#define LED_ROJO 30       // Definicion de PIN LED_ROJO
#define SWITCH 32         // Definicion de PIN SWITCH
#define FCL 40
#define FCR 41
bool rescateAvisado = false;
// INITIALISE BNO055 //
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
// INITIALISE ACTUATORS //
Moto bl(29, 28, 27, "BL"); // pwm, dir, enc
Moto fl(7, 6, 5, "FL");
Moto br(36, 37, 38, "BR");
Moto fr(4, 3, 2, "FR");
DriveBase robot(&fl, &fr, &bl, &br);

static long gapPulsosDesdeInicio()
{
    const long dfl = labs((long)fl.pulseCount - g_gap_inicio_fl);
    const long dfr = labs((long)fr.pulseCount - g_gap_inicio_fr);
    return (dfl + dfr) / 2;
}

static void resetGapState()
{
    g_gap_activo = false;
    g_gap_origen_enviado = false;
    g_gap_timeout_enviado = false;
    g_gap_inicio_fl = (long)fl.pulseCount;
    g_gap_inicio_fr = (long)fr.pulseCount;
    g_gap_inicio_ms = 0;
}
// ############################################################################
// #                                                                          #
// #  4.  ESTADO GLOBAL Y PROTOCOLO CON LA RASPBERRY                          #
// #                                                                          #
// #  PROTOCOLO Serial5, 115200 baud, 8 bytes por trama:                      #
// #                                                                          #
// #      [255, speed] [254, angle] [253, green_state] [252, silver_line]     #
// #                                                                          #
// #    speed        0..100   NO SE USA: el case 7 arranca de VELOCIDAD_BASE_LINEA#
// #    angle        0..180   la Pi manda angulo+90; aca vuelve a -1.0 .. +1.0#
// #    green_state  0..20    QUE hacer (ver la tabla de abajo)               #
// #    silver_line  0..1     NO tiene autoridad: el plateado lo decide el APDS#
// #                                                                          #
// #  Los bytes 252..255 son SYNC y no pueden aparecer como dato.             #
// #                                                                          #
// #  TABLA DE green_state (lo que manda la Pi -> que hace el Teensy):        #
// #     0  linea normal                    -> case 7, seguimiento            #
// #     1  marca verde a la IZQUIERDA      -> case 6, avanza 800 ms y gira -60#
// #     2  marca verde a la DERECHA        -> case 5, avanza 800 ms y gira +60#
// #     3  DOBLE verde                     -> case 14, media vuelta          #
// #     4  linea PERDIDA                   -> case 4, retroceso + pivote dirigido#
// #     6  pelota negra (en evacuacion)    -> secuencia de garra             #
// #     7  pelota plateada (en evacuacion) -> secuencia de garra             #
// #     8  triangulo ROJO de deposito      -> deposita a la izquierda        #
// #     9  triangulo VERDE de deposito     -> deposita a la derecha          #
// #    14  interseccion                    -> case 12, se realinea con la IMU#
// #    15/16/17  respuesta de la Pi al case 12 (izq / der / recto)           #
// #    18  buscar el otro lado de un GAP   -> avanza recto acotado           #
// #    19  fail-safe: parar                                                  #
// #                                                                          #
// #  De vuelta (Teensy -> Pi): 0xF9 arranque, 0xFA listo, 0xF7 evacuacion,   #
// #  0xF8 depositando, y los cinco ACK del panel (0xED..0xF1).               #
// ############################################################################

// STATE VARIABLES & FLAGS //
String color_detected;

int serial5state = 0;  // serial code e.g. 255
double speed;          // speed (0 to 100)
double steer;          // angle (0 to 180 deg, will -90 later)
int green_state = 0;   // 0 = no green squares, 1 = left, 2 = right, 3 = double
int silver_line = 0;   // if there is a line to reacquire after obstacle
// PROTOCOLO RPi -> Teensy:
// Frame: [255, speed, 254, angle, 253, green_state, 252, silver_line]
// speed: 0..100; angle: 0..180 (RPi envia angle + 90);
// green_state: 0..20; silver_line: 0..1.
// Los sync bytes 252..255 no deben usarse como payload.
constexpr int SERIAL_SYNC_SPEED = 255;
constexpr int SERIAL_SYNC_STEER = 254;
constexpr int SERIAL_SYNC_TASK = 253;
constexpr int SERIAL_SYNC_SILVER = 252;
constexpr int SERIAL_MAX_SPEED = 100;
constexpr int SERIAL_MAX_ANGLE = 180;
constexpr int SERIAL_MAX_GREEN_STATE = 20;
constexpr int SERIAL_MAX_SILVER_LINE = 1;
unsigned long serial_bytes_rx = 0;
unsigned long serial_frames_rx = 0;
elapsedMillis serialTelemetryTimer;
int action =7;            // action to take (part of a task)
bool taskDone = false; // if true, update current_task
bool startUp = false;
int RanNumber;
String rutina = "linea";
String lado_plateado="";
VL53L0X left_tof;  // Sensor 1
VL53L0X right_tof; // Sensor 2
int distance_left_tof;
int distance_right_tof;
float angulo_rescate = 0;
float centrar = 0;
String pared="";
bool depositando=false;
int veces_deposit=2;
int ball_counter=1;
bool evacuacion_iniciada=false;
bool evacuacion_straight=false;
bool silver_latch=false;  // true mientras seguimos "sobre" un plateado ya atendido (evita repetir la accion)

// Máquina de Estados para Rescate (No Bloqueante)
bool color_sensor_ok = true;
bool rescateUpdateInProgress = false;

void actualizarRescate();
void serialEvent5();
void runTime(int speed, int dir, double steer, unsigned long long time);
void runAngle(int speed, int dir, double angle);
void runDistance(int speed, int dir, int Distance);


// VELOCIDAD BASE DEL SEGUIMIENTO DE LINEA, en rpm.
//
// FIJA, y NO la manda la Raspberry. El byte `speed` del protocolo se recibe y se
// valida en serialEvent5(), pero el case 7 no lo usa: se probo usarlo y se apago
// el 25-ago-2026 porque la anticipacion de curva que lo justificaba no resistio
// el re-analisis con placebo (lift 1,26x contra el 1,5 preregistrado).
//
// Es el PUNTO DE PARTIDA de dos ajustes que vienen despues:
//   ajustarVelocidadPorPendiente()  la deja en 40 en llano y la sube a 45 en rampa
//   la rampa cuadratica del case 7  la lleva hasta LINE_PIVOT_SPEED en la curva
static const int VELOCIDAD_BASE_LINEA = 45;

void blinkVisibleError(unsigned long onMs, unsigned long offMs, int cycles)
{
    for (int i = 0; i < cycles; ++i)
    {
        digitalWrite(LED_ROJO, HIGH);
        digitalWrite(BUZZER, HIGH);
        delay(onMs);
        digitalWrite(LED_ROJO, LOW);
        digitalWrite(BUZZER, LOW);
        delay(offMs);
    }
}

void fatalSensorInitLoop()
{
    while (true)
    {
        digitalWrite(LED_ROJO, HIGH);
        digitalWrite(BUZZER, HIGH);
        delay(200);
        digitalWrite(LED_ROJO, LOW);
        digitalWrite(BUZZER, LOW);
        delay(800);
    }
}

void handleBnoInitFailure()
{
    DBG_PRINT("No BNO055 detected ... Check your wiring or I2C ADDR!");
    fatalSensorInitLoop();   // no vuelve nunca: parpadeo + chicharra para siempre
}

// Sensor OPCIONAL que no arranco (hoy: el APDS9960). NO es fatal -el robot puede
// seguir la linea sin color- pero tiene que NOTARSE antes de largar la corrida.
void notifyOptionalSensorWarning()
{
    blinkVisibleError(120, 120, 3);
}


// ============================================================================
//  REGISTRADOR CSV DE 200 Hz - herramienta de banco, NO entra en competencia.
//  Va ACA y no arriba con el resto de los #include porque lee las globales que
//  se declaran mas arriba en este mismo archivo. Ver el banner de diagnostico.h.
//  OJO: en el binario que se flashea MODO_DIAGNOSTICO vale 1, asi que esto SI
//  se compila y SI cuesta tiempo de lazo. Ver el aviso de la cabecera.
// ============================================================================
#include "diagnostico.h"

void serviceMotionBackgroundTasks()
{
    DIAG_TICK();   // muestreo de alta frecuencia DURANTE las maniobras bloqueantes
    // Telemetria primero, asi sigue fluyendo durante TODAS las maniobras
    // bloqueantes (runTime/runAngle/runDistance/...). Es rate-limited y no
    // bloqueante: costo despreciable.
    enviarTelemetria();

    claw.update();
    actualizarRescate();
}

unsigned long computeRunDistanceTimeoutMs(int speed, int distance)
{
    unsigned long distanceCm = static_cast<unsigned long>(abs(distance));
    int effectiveSpeed = speed > 0 ? speed : 30;
    unsigned long estimatedSpeedCmPerSecond = static_cast<unsigned long>(max(8, effectiveSpeed * 3 / 4));
    unsigned long estimatedMs = (distanceCm * 1000UL) / estimatedSpeedCmPerSecond;

    return (estimatedMs * 3UL) / 2UL + 500UL;
}

unsigned long computeRunAngleTimeoutMs(double angle)
{
    unsigned long angleDeg = static_cast<unsigned long>(fabs(angle));
    if (angleDeg < 1)
    {
        return 1000UL;
    }

    return max(1500UL, angleDeg * 35UL + 1000UL);
}

// ============================================================================
//  MAQUINA DE ESTADOS DE RESCATE (garra)  -  HOY NO SE EJECUTA NUNCA.
//
//  LEER ESTO ANTES DE CREER QUE ESTA ES LA QUE CORRE. `rescateState` arranca en
//  RESCATE_IDLE y NADA lo saca de ahi: las dos funciones que lo hacian
//  (iniciarRecoleccionNegra / iniciarRecoleccionPlateada) no tenian un solo
//  llamador y se borraron el 2026-09-06. O sea que actualizarRescate() se llama
//  en cada vuelta del lazo y en cada vuelta de runTime/runAngle/runDistance,
//  pero siempre cae en `case RESCATE_IDLE: break;`.
//
//  EL RESCATE QUE SI CORRE es el codigo en linea del lazo de evacuacion:
//  procesarColorEvacuacion() -> accionNegro() / accionPlateado(), y las
//  secuencias de garra de los green_state 6 y 7 dentro de `rutina == "rescate"`.
//
//  SE DEJA porque la secuencia de garra esta bien escrita y sirve como plan B no
//  bloqueante. PARA REVIVIRLA alcanza con poner, desde donde corresponda:
//      rescateState = RESCATE_NEGRA_STEP1;  rescateLastTime = millis();
//  (o RESCATE_PLATEADA_STEP1). En la telemetria el campo `resc` es este estado:
//  mientras esto no se toque, ese campo vale 0 siempre y eso NO es un fallo.
// ============================================================================
enum RescateState {
    RESCATE_IDLE = 0,          // Estado inactivo
    RESCATE_NEGRA_STEP1,       // Baja garra
    RESCATE_NEGRA_STEP2,       // Posiciona depósito centro
    RESCATE_NEGRA_STEP3,       // Clasifica derecha
    RESCATE_NEGRA_STEP4,       // Avanza distancia
    RESCATE_NEGRA_STEP5,       // Cierra garra
    RESCATE_NEGRA_STEP6,       // Levanta garra
    RESCATE_NEGRA_STEP7,       // Abre garra
    RESCATE_NEGRA_STEP8,       // Retrocede un poco
    RESCATE_PLATEADA_STEP1,    // Baja garra
    RESCATE_PLATEADA_STEP2,    // Clasifica izquierda
    RESCATE_PLATEADA_STEP3,    // Posiciona depósito centro
    RESCATE_PLATEADA_STEP4,    // Avanza distancia
    RESCATE_PLATEADA_STEP5,    // Cierra garra
    RESCATE_PLATEADA_STEP6,    // Levanta garra
    RESCATE_PLATEADA_STEP7,    // Abre garra
    RESCATE_PLATEADA_STEP8     // Retrocede un poco
};
RescateState rescateState = RESCATE_IDLE;  // Estado actual de la máquina de rescate
unsigned long rescateLastTime = 0;         // Timestamp del último paso
const unsigned long RESCATE_STEP_DELAY = 1000;  // Delay entre pasos en ms



// Función para actualizar la máquina de estados de rescate (llamar en loop())
void actualizarRescate() {
    if (rescateUpdateInProgress) {
        return;
    }

    rescateUpdateInProgress = true;
    unsigned long now = millis();
    switch (rescateState) {
        case RESCATE_IDLE:
            // Nada que hacer
            break;
        case RESCATE_NEGRA_STEP1:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lower();
                rescateState = RESCATE_NEGRA_STEP2;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP2:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.depositCenter();
                rescateState = RESCATE_NEGRA_STEP3;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP3:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.sortRight();
                rescateState = RESCATE_NEGRA_STEP4;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP4:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                runDistance(30, FORWARD, 8);
                rescateState = RESCATE_NEGRA_STEP5;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP5:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.close();
                digitalWrite(BUZZER, HIGH);
                delay(100);  // Pequeño delay para buzzer, considerar no-bloqueante si necesario
                digitalWrite(BUZZER, LOW);
                rescateState = RESCATE_NEGRA_STEP6;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP6:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lift();
                rescateState = RESCATE_NEGRA_STEP7;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP7:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.open();
                rescateState = RESCATE_NEGRA_STEP8;
                rescateLastTime = now;
            }
            break;
        case RESCATE_NEGRA_STEP8:
            if (now - rescateLastTime >= 200) {  // Menor delay para retroceso
                runTime(30, FORWARD, 0, 200);
                runTime(30, BACKWARD, 0, 200);
                ball_counter++;
                rescateState = RESCATE_IDLE;
            }
            break;
        // Estados para pelota plateada (análogos)
        case RESCATE_PLATEADA_STEP1:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lower();
                rescateState = RESCATE_PLATEADA_STEP2;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP2:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.sortLeft();
                rescateState = RESCATE_PLATEADA_STEP3;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP3:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.depositCenter();
                rescateState = RESCATE_PLATEADA_STEP4;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP4:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                runDistance(20, FORWARD, 8);
                rescateState = RESCATE_PLATEADA_STEP5;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP5:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.close();
                digitalWrite(BUZZER, HIGH);
                delay(100);
                digitalWrite(BUZZER, LOW);
                rescateState = RESCATE_PLATEADA_STEP6;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP6:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.lift();
                rescateState = RESCATE_PLATEADA_STEP7;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP7:
            if (now - rescateLastTime >= RESCATE_STEP_DELAY) {
                claw.open();
                rescateState = RESCATE_PLATEADA_STEP8;
                rescateLastTime = now;
            }
            break;
        case RESCATE_PLATEADA_STEP8:
            if (now - rescateLastTime >= 200) {
                runTime(30, FORWARD, 0, 200);
                runTime(30, BACKWARD, 0, 200);
                ball_counter++;
                rescateState = RESCATE_IDLE;
            }
            break;
    }
    rescateUpdateInProgress = false;
}
#define SONAR_NUM 3      // Number of sensors.
#define MAX_DISTANCE 150 // Maximum distance (in cm) to ping.

NewPing sonar[SONAR_NUM] = {     // Sensor object array.
    NewPing(8, 9, MAX_DISTANCE), // Each sensor's trigger pin, echo pin, and max distance to ping.
    NewPing(11, 10, MAX_DISTANCE),
    NewPing(39, 33, MAX_DISTANCE)};

int front_distance;
int left_distance;
int right_distance;

// ############################################################################
// #                                                                          #
// #  5.  SENSORES: ultrasonidos, ToF, color (APDS9960)                       #
// #                                                                          #
// #  ULTRASONIDOS (HC-SR04, NewPing): frente / izquierda / derecha. Son      #
// #  BLOQUEANTES: ping_cm() espera hasta el timeout cuando no hay eco. Por eso#
// #  el lazo de linea usa leer_ultrasonido_frontal(), con techo corto y      #
// #  periodico, y no leer_ultrasonidos(). Ver el punto 1.4 del panel.        #
// #                                                                          #
// #  ToF VL53L0X (izq/der, uno por bus I2C): SE INICIALIZAN Y NADIE LOS LEE. #
// #  leer_tof() solo se llamaba desde el seguimiento de pared, que no esta en#
// #  este binario. La telemetria publica 0 mm: eso significa "nadie pregunto".#
// #                                                                          #
// #  COLOR APDS9960: es el que decide el plateado (entrada a evacuacion) y el#
// #  rojo (fin de la corrida). Muestreo NO BLOQUEANTE con promedio movil de 3#
// #  muestras. Tres formas de preguntarle, y la diferencia importa:          #
// #     get_color_fast()   devuelve la ultima clasificacion, sin esperar.    #
// #                        "Desconocido" = no hay dato fresco todavia.       #
// #     get_color_fresh()  espera hasta 35 ms una muestra NUEVA. Es la que se#
// #                        usa para CONFIRMAR antes de actuar.               #
// #     confirmarPlateadoLinea()  4 ventanas filtradas seguidas (12 muestras).#
// ############################################################################

// -----------  FUNCTIONS  -----------
// ULTRASONIDOS FRENTE IZQ DER
void leer_ultrasonidos()
{
    // Rango LARGO explicito: si el lazo de linea corrio con kPingLineaCm, el
    // objeto quedo con ese techo -set_max_distance() persiste- y evacuacion
    // necesita 120 cm (`front_distance < 120`).
    const unsigned int largo = PING_LARGO_CM;
    front_distance = sonar[0].ping_cm(largo);
    left_distance = sonar[1].ping_cm(largo);
    right_distance = sonar[2].ping_cm(largo);
}

// MEMORIA DE PARED EN EVACUACION. Se llama despues de cada leer_ultrasonidos()
// del lazo de evacuacion: si un lateral ve pared cerca, recuerda ese lado.
// Cuando la pared desaparece (salida, esquina abierta) la memoria NO se borra:
// eso es justamente lo que accionNegro() necesita saber.
void memoriaParedEvacuacion()
{
    const bool izqOk = (left_distance  > 0 && left_distance  <= NEGRO_SALIDA_PARED_MAX_CM);
    const bool derOk = (right_distance > 0 && right_distance <= NEGRO_SALIDA_PARED_MAX_CM);
    if (izqOk && (!derOk || left_distance < right_distance))
    {
        g_evac_pared_lado = -1;
        g_evac_pared_ms = millis();
    }
    else if (derOk && (!izqOk || right_distance < left_distance))
    {
        g_evac_pared_lado = +1;
        g_evac_pared_ms = millis();
    }
}

// Version con muestreo propio, para el lazo recto inicial de evacuacion que no
// lee los ultrasonidos por su cuenta. Lee cada NEGRO_SALIDA_MUESTREO_MS.
void memoriaParedEvacuacionPeriodica()
{
    static unsigned long t_ultimo = 0;
    const unsigned long ahora = millis();
    if (t_ultimo != 0 && (ahora - t_ultimo) < NEGRO_SALIDA_MUESTREO_MS)
        return;
    t_ultimo = ahora;
    leer_ultrasonidos();
    memoriaParedEvacuacion();
}

// SOLO EL FRONTAL. Es el unico ultrasonido que el lazo de linea consulta en
// cada vuelta (obstaculo a menos de 12 cm); las ramas que usan left/right lo
// vuelven a pedir por su cuenta con leer_ultrasonidos(). Ahorra dos ping
// bloqueantes por frame. Ver el punto 1.4 del panel de configuracion.
void leer_ultrasonido_frontal()
{
    // TIMEOUT CORTO. `ping_cm()` bloquea hasta el timeout cuando NO hay eco, y
    // en linea casi nunca hay una pared a menos de 150 cm: el caso normal ES el
    // peor caso. El lazo solo pregunta `front_distance < 12`, asi que 30 cm de
    // techo sobra el doble y el timeout cae de 8578 a 1738 us.
    // El valor va EXPLICITO porque set_max_distance() persiste en el objeto.
    // Y NO EN CADA VUELTA. A 30 cm/s el robot avanza 1,2 cm en 40 ms, un decimo
    // del umbral de 12 cm: un obstaculo no puede aparecer entre dos pings.
    static unsigned long t_ping = 0;
    unsigned long ahora = millis();
    if (t_ping != 0 &&
        (unsigned long)(ahora - t_ping) < PING_FRONTAL_PERIODO_MS)
        return;                       // se conserva la lectura anterior
    t_ping = ahora;
    front_distance = sonar[0].ping_cm(PING_LINEA_CM);
}


// TOF
void leer_tof()
{
    distance_left_tof = left_tof.readRangeContinuousMillimeters();
    distance_right_tof = right_tof.readRangeContinuousMillimeters();
}

void imprimir_tof()
{
    DBG_PRINT("Distance Left: ");
    DBG_PRINT(distance_left_tof);
    DBG_PRINT("mm");

    if (left_tof.timeoutOccurred())
    {
        DBG_PRINT(" TIMEOUT");
    }

    DBG_PRINT("   Distance Right: ");
    DBG_PRINT(distance_right_tof);
    DBG_PRINT("mm");

    if (right_tof.timeoutOccurred())
    {
        DBG_PRINT(" TIMEOUT");
    }
}
void reset_enconder(){
    bl.resetPulseCount();
    fl.resetPulseCount();
    br.resetPulseCount();
    fr.resetPulseCount();
}
// Color Sensor
Adafruit_APDS9960 apds;
struct Color
{
    String name;
    uint16_t r, g, b, c;
};

Color known_colors[] = {
  {"Blanco", 570, 1010, 1025, 2685},
  {"Negro", 60, 135, 135, 310},
  {"Verde", 62, 181, 175, 470},
  {"Plateado", 500, 900, 900, 2300}
 
};
// Función para leer los valores del sensor y determinar el color
constexpr unsigned long APDS_COLOR_INTEGRATION_MS = 10;
constexpr unsigned long APDS_COLOR_STATUS_POLL_MS = 2;
constexpr unsigned long APDS_COLOR_FRESH_TIMEOUT_MS = 35;
constexpr uint8_t APDS_COLOR_FILTER_SAMPLES = 3;

uint16_t color_r_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint16_t color_g_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint16_t color_b_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint16_t color_c_history[APDS_COLOR_FILTER_SAMPLES] = {0};
uint8_t color_history_index = 0;
uint8_t color_history_count = 0;
unsigned long last_color_sample_ms = 0;
unsigned long last_color_status_poll_ms = 0;
String last_color_detected = "Desconocido";

uint64_t square_error(uint16_t expected, uint16_t actual)
{
    int32_t diff = static_cast<int32_t>(expected) - static_cast<int32_t>(actual);
    return static_cast<uint64_t>(diff) * static_cast<uint64_t>(diff);
}

void push_color_sample(uint16_t r, uint16_t g, uint16_t b, uint16_t c)
{
    color_r_history[color_history_index] = r;
    color_g_history[color_history_index] = g;
    color_b_history[color_history_index] = b;
    color_c_history[color_history_index] = c;
    color_history_index = (color_history_index + 1) % APDS_COLOR_FILTER_SAMPLES;
    if (color_history_count < APDS_COLOR_FILTER_SAMPLES)
    {
        color_history_count++;
    }
}

void get_filtered_color(uint16_t &r, uint16_t &g, uint16_t &b, uint16_t &c)
{
    uint32_t r_sum = 0, g_sum = 0, b_sum = 0, c_sum = 0;
    uint8_t samples = color_history_count > 0 ? color_history_count : 1;

    for (uint8_t i = 0; i < color_history_count; i++)
    {
        r_sum += color_r_history[i];
        g_sum += color_g_history[i];
        b_sum += color_b_history[i];
        c_sum += color_c_history[i];
    }

    r = r_sum / samples;
    g = g_sum / samples;
    b = b_sum / samples;
    c = c_sum / samples;
}

// Limpia el historial del filtro de color para no arrastrar muestras viejas
// (stale) despues de una accion bloqueante en evacuacion. Fuerza que la
// proxima clasificacion se construya solo con muestras frescas.
void reset_color_history()
{
    color_history_index = 0;
    color_history_count = 0;
    last_color_sample_ms = 0;
    last_color_detected = "Desconocido";
}
String classify_color(uint16_t r, uint16_t g, uint16_t b, uint16_t c)
{
    float ratio_rc = c > 0 ? static_cast<float>(r) / static_cast<float>(c) : 0.0f;
    float ratio_rg = g > 0 ? static_cast<float>(r) / static_cast<float>(g) : 0.0f;
    float ratio_rb = b > 0 ? static_cast<float>(r) / static_cast<float>(b) : 0.0f;

    int diff_bg = static_cast<int>(b) - static_cast<int>(g);

    static unsigned long lastPrint = 0;
    bool shouldPrint = (millis() - lastPrint > 500);

    if (shouldPrint)
    {
        DBG_PRINT("R: "); DBG_PRINT(r);
        DBG_PRINT(" | B: "); DBG_PRINT(b);
        DBG_PRINT(" | G: "); DBG_PRINT(g);
        DBG_PRINT(" | C: "); DBG_PRINT(c);
        DBG_PRINT(" | R/C: "); DBG_PRINT(ratio_rc, 3);
        DBG_PRINT(" | R/G: "); DBG_PRINT(ratio_rg, 3);
        DBG_PRINT(" | R/B: "); DBG_PRINT(ratio_rb, 3);
        DBG_PRINT(" | B-G: "); DBG_PRINT(diff_bg);
        DBG_PRINT(" | -> ");
    }

    String detected = "Desconocido";

    // CALIBRACION REAL 2026-09-05 (APDS montado a altura de trabajo).
    // Rojo medido: C~371..817, R/C~0.301..0.501, R/G~1.144..1.979,
    // R/B~0.921..1.798. Se deja margen minimo sin invadir blanco/plateado.
    bool esRojo =
        (
            c >= 340 && c <= 900 &&
            ratio_rc >= 0.295f &&
            ratio_rg >= 1.10f &&
            ratio_rb >= 0.90f
        );

    // PLATEADO ROBUSTO 2026-09-05.
    // Datos reales del APDS montado:
    //   plateado estable: R/C~0.247..0.260, R/G~0.64..0.67, R/B~0.63..0.68
    //   blanco estable:   R/C~0.219..0.235, R/G~0.57..0.60
    // La calibracion anterior (R/C>=0.240) recuperaba bordes 0.243..0.245 pero
    // quedo demasiado permisiva y produjo rescates falsos. Para LINEA preferimos
    // perder una lectura de borde y confirmar el nucleo espectral real del plata.
    // B y G tambien deben quedar proximos: en las muestras de plata validas |B-G|
    // queda dentro de ~17, con margen hasta 30.
    bool esPlateado =
        (
            c >= 1500 &&
            ratio_rc >= 0.245f &&
            ratio_rc <= 0.268f &&
            ratio_rg >= 0.645f &&
            ratio_rg <= 0.700f &&
            ratio_rb >= 0.615f &&
            ratio_rb <= 0.700f &&
            abs(diff_bg) <= 30
        );

    // Blanco medido: R/C~0.219..0.235. Dejamos una zona muerta 0.235..0.245
    // antes del plateado en vez de forzar una clasificacion dudosa.
    bool esBlanco =
        (
            c >= 430 &&
            ratio_rc >= 0.195f &&
            ratio_rc < 0.245f
        );

    if (esRojo)
    {
        detected = "Rojo";
    }
    else if (esPlateado)
    {
        detected = "Plateado";
    }
    else if (esBlanco)
    {
        detected = "Blanco";
    }
    else
    {
        uint64_t min_error = UINT64_MAX;

        for (size_t i = 0; i < sizeof(known_colors) / sizeof(known_colors[0]); i++)
        {
            if (known_colors[i].name == "Blanco" || known_colors[i].name == "Plateado")
                continue;

            uint64_t error = square_error(known_colors[i].r, r) +
                             square_error(known_colors[i].g, g) +
                             square_error(known_colors[i].b, b) +
                             square_error(known_colors[i].c, c);

            if (error < min_error)
            {
                min_error = error;
                detected = known_colors[i].name;
            }
        }
    }

    if (shouldPrint)
    {
        DBG_PRINTLN(detected);
        lastPrint = millis();
    }

    return detected;
}
bool update_color_nonblocking(bool force_poll = false)
{
    if (!color_sensor_ok) return false;   // el APDS no arranco: no hay color

    unsigned long now = millis();
    if (!force_poll && (now - last_color_status_poll_ms) < APDS_COLOR_STATUS_POLL_MS)
        return false;

    last_color_status_poll_ms = now;
    if ((now - last_color_sample_ms) < APDS_COLOR_INTEGRATION_MS)
        return false;

    if (!apds.colorDataReady())
        return false;

    uint16_t r, g, b, c;
    apds.getColorData(&r, &g, &b, &c);
    push_color_sample(r, g, b, c);
    get_filtered_color(r, g, b, c);
    last_color_detected = classify_color(r, g, b, c);
    last_color_sample_ms = now;
    return true;
}

String 
get_color_fresh(unsigned long timeoutMs = APDS_COLOR_FRESH_TIMEOUT_MS)
{
    unsigned long start = millis();
    while ((millis() - start) <= timeoutMs)
    {
        if (update_color_nonblocking(true))
            return last_color_detected;

        serviceMotionBackgroundTasks();
        delay(1);
    }

    return "Desconocido";
}

String get_color_fast()
{
    if (update_color_nonblocking(false))
        return last_color_detected;

    return "Desconocido";
}




// ISR for updating motor pulses
void ISR1() { bl.updatePulse(); }
void ISR2() { fl.updatePulse(); }
void ISR3() { br.updatePulse(); }
void ISR4() { fr.updatePulse(); }

bool serialPayloadOutOfRange(const char *field, int value, int maxValue)
{
    if (value >= 0 && value <= maxValue)
    {
        return false;
    }

    DBG_PRINT("[WARN] ");
    DBG_PRINT(field);
    DBG_PRINT(" fuera de rango: ");
    DBG_PRINTLN(value);
    return true;
}

void maybePrintSerialTelemetry()
{
    if (serialTelemetryTimer < 5000) return;

    DBG_PRINT("[TLM] serial_bytes_rx=");
    DBG_PRINT(serial_bytes_rx);
    DBG_PRINT(" serial_frames_rx=");
    DBG_PRINTLN(serial_frames_rx);
    serialTelemetryTimer = 0;
}

// ############################################################################
// #                                                                          #
// #  6.  SERIAL CON LA RASPBERRY                                             #
// #                                                                          #
// #  serialEvent5() se llama A MANO desde donde haga falta escuchar: el      #
// #  callback automatico de Arduino casi nunca corre, porque el lazo se bloquea#
// #  adentro de los while largos de las maniobras.                           #
// #                                                                          #
// #  El parser es una maquina de 4 estados guiada por los bytes de sync. Si se#
// #  pierde un byte, el framing se recupera solo en el siguiente sync.       #
// ############################################################################

// Read Data from Raspberry by Serial TX-RX
void serialEvent5()
{
    // ------------------------------------------------------------------
    //  LIMITACION CONOCIDA, ANOTADA A PROPOSITO: LA TRAMA VIEJA SE SELLA
    //  COMO FRESCA.
    //
    //  Durante una maniobra bloqueante nadie llama a serialEvent5(), asi que
    //  los bytes de la Pi se apilan en el buffer de Serial5. Al volver al lazo,
    //  la PRIMERA trama que se termina de parsear ejecuta
    //      g_last_rx_ms = millis();
    //  o sea que sella con la hora de AHORA un comando emitido ANTES de la
    //  maniobra. El watchdog de comunicacion mide `millis() - g_last_rx_ms`,
    //  asi que durante una vuelta ve "fresco" algo que puede tener segundos.
    //
    //  MEDIDO: durante maniobra el comando llega con p50 1849 ms y max 4677 ms
    //  de atraso. En el peor caso el robot obedece UNA trama vieja antes de que
    //  llegue la siguiente (la Pi manda a 66-86 Hz: ~15 ms despues).
    //
    //  SE PROBO ARREGLARLO descartando el buffer si el serial estuvo ciego mas
    //  de 250 ms. Nunca se valido en pista y se saco el 2026-09-06: el
    //  falsador que se habia preregistrado -que el contador de descartes fuera
    //  mayor que cero en una corrida con maniobras- era INOBSERVABLE, porque
    //  ese contador no salia en la telemetria. Si se vuelve a intentar, lo
    //  primero es publicarlo.
    // ------------------------------------------------------------------
    while (Serial5.available() > 0)
    {
        int data = Serial5.read();
        serial_bytes_rx++;
         
        if (data == SERIAL_SYNC_SPEED) // speed incoming
            serial5state = 0;
        else if (data == SERIAL_SYNC_STEER) // steer incoming
            serial5state = 1;
        else if (data == SERIAL_SYNC_TASK) // task incoming
            serial5state = 2;
        else if (data == SERIAL_SYNC_SILVER) // line_middle incoming
            serial5state = 3;
        else if (serial5state == 0)           // set speed
        {
            if (serialPayloadOutOfRange("speed", data, SERIAL_MAX_SPEED))
                continue;
            speed = (double)data / 100 * 100; // max speed = 100
        }
        else if (serial5state == 1)           // set steer
        {
            if (serialPayloadOutOfRange("angle", data, SERIAL_MAX_ANGLE))
                continue;
            steer = ((double)data - 90) / 90;
            g_rx_steer = steer;   // copia para la telemetria: nadie mas la toca
        }
        else if (serial5state == 2) // set task
        {
            if (serialPayloadOutOfRange("green_state", data, SERIAL_MAX_GREEN_STATE))
                continue;
            green_state = data;
            // El protocolo llega en orden speed -> angle -> green_state -> silver.
            // Por eso al leer GS=4, g_rx_steer ya contiene el angle DE ESA MISMA
            // trama. En recovery ese angle es el rumbo CAMINO congelado por la Pi.
            if (data == LINEA_PERDIDA_GS)
            {
                // Durante recovery la RPi manda angle=0 cuando CAMINO aun no
                // tiene una lectura fresca. No dejar que ese "no se" pise un
                // heading valido obtenido despues del retroceso.
                if (fabs(g_rx_steer) >= RECUP_STEER_MIN)
                {
                    g_recup_rumbo_camino_rx = g_rx_steer;
                    g_recup_rumbo_camino_rx_ms = millis();
                }
            }
            telemGreenRx(data);   // TELEMETRIA: cuenta verdes que llegan de la RPi
    // DBG_PRINT("[RX] green_state recibido: ");
    // DBG_PRINTLN(green_state);
        }
        else if (serial5state == 3) // set line_middle
        {
            if (serialPayloadOutOfRange("silver_line", data, SERIAL_MAX_SILVER_LINE))
                continue;
            silver_line = data;
            serial_frames_rx++;
            g_last_rx_ms = millis();   // trama completa: el comando esta fresco
        }
    }

    maybePrintSerialTelemetry();
}

// ############################################################################
// #                                                                          #
// #  7.  PRIMITIVAS DE MOVIMIENTO (bloqueantes)                              #
// #                                                                          #
// #  runTime      avanza/gira durante N ms                                   #
// #  runAngle     gira hasta un angulo del BNO055, con timeout               #
// #  runDistance  avanza N cm contando pulsos de encoder, con timeout        #
// #  runDistanceEvacuacion  igual, pero corta si aparece una pared a <=18 cm #
// #                                                                          #
// #  LAS CUATRO SON BLOQUEANTES: el loop() no vuelve a correr hasta que      #
// #  terminan. Por eso todas llaman a serviceMotionBackgroundTasks() en cada #
// #  vuelta, que es el unico punto por donde siguen fluyendo la telemetria, la#
// #  garra y el registrador de diagnostico mientras el robot maniobra.       #
// #                                                                          #
// #  Y NINGUNA PARSEA EL SERIAL: drenan un byte y lo tiran. Una maniobra     #
// #  empezada se termina. Ver el punto 1.6 del panel.                        #
// #                                                                          #
// #  TODAS cortan si se apaga el switch (pin 32), en cualquier punto.        #
// ############################################################################

// HELPER FUNCTIONS //

// Do a predefined move by time
void runTime(int speed, int dir, double steer, unsigned long long time)
{
    g_line_branch = -1;   // este giro no lo pidio el case 7
    PRIM("runTime");
    unsigned long long startTime = millis();
    while ((millis() - startTime) < time)
    {
        robot.steer(speed, dir, steer);
        serviceMotionBackgroundTasks();
        digitalWrite(13, HIGH);
        // DRENA UN BYTE POR VUELTA Y LO TIRA: NO parsea la trama. Durante una
        // maniobra el robot NO obedece comandos nuevos, a proposito. Ver
        // "SERIAL DURANTE LAS MANIOBRAS" en el panel de configuracion.
        if (Serial5.available() > 0)
        {
            // OJO: la lectura va en su PROPIA sentencia y NO adentro del
            // DBG_PRINT. Con MODO_DIAGNOSTICO=1 la macro es `do {} while(0)` y
            // DESCARTA SUS ARGUMENTOS: metida adentro, Serial5.read() no se
            // llamaria y el buffer de Serial5 no se drenaria nunca.
            const int lecturas = Serial5.read();
            DBG_PRINT(lecturas);
            (void)lecturas;
        }

        if (digitalRead(32) == 1)
        { // switch is off
            Serial5.clear();
            Serial5.write(255);
            break;
        }
    }

    digitalWrite(13, LOW);
}
void runAngle(int speed, int dir, double angle)
{
    g_line_branch = -1;   // este giro no lo pidio el case 7
    PRIM("runAngle");
    sensors_event_t event;
    bno.getEvent(&event);
    float initialAngle = event.orientation.x;
    float targetAngle = initialAngle + angle;
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunAngleTimeoutMs(angle);

    // Normalizar el ángulo objetivo al rango 0-360
    targetAngle = fmod(targetAngle, 360.0);
    if (targetAngle < 0)
        targetAngle += 360;

    while (true)
    {
        bno.getEvent(&event);
        float currentAngle = event.orientation.x;
        serviceMotionBackgroundTasks();
        if ((millis() - startTime) >= timeoutMs)
        {
            DBG_PRINTLN("[WARN] runAngle timeout");
            break;
        }
        if (digitalRead(32) == 1)
        { // switch is off
            Serial5.clear();
            Serial5.write(255);
            break;
        }
        // Calcular la diferencia más corta entre los ángulos
       // Calcular la diferencia más corta entre los ángulos
        float error = targetAngle - currentAngle;
        if (error > 180)
            error -= 360;
        if (error < -180)
            error += 360;
        DBG_PRINT("Error actual: ");
        //DBG_PRINTLN(fabs(error));
        if (fabs(error) <= 1.0)
            break;
        // Lógica para manejar los 5 valores de ángulo específicos
        if (angle == 180)
        {
            // Girar 180 grados (media vuelta)
            robot.steer(speed, dir, 1); // Girar a la derecha
        }
        else if (angle == 90 || angle == -270)
        {
            // Girar 90 grados a la derecha
            if (error > 0 && error <= 180)
            {
                robot.steer(speed, dir, -1);
            }
            else
            {
                robot.steer(speed, dir, 1);
            }
        }
        else if (angle == -90 || angle == 270)
        {
            // Girar 90 grados a la izquierda
            if (error < 0 && error >= -180)
            {
                robot.steer(speed, dir, 1);
            }
            else
            {
                robot.steer(speed, dir, -1);
            }
        }
        else if (angle == 45 || angle == -315)
        {
            // Girar 45 grados a la derecha
            if (error > 0 && error <= 180)
            {
                robot.steer(speed, dir, -1);
            }
            else
            {
                robot.steer(speed, dir, 1);
            }
        }
        else if (angle == -45 || angle == 315)
        {
            // Girar 45 grados a la izquierda
            if (error < 0 && error >= -180)
            {
                robot.steer(speed, dir, 1);
            }
            else
            {
                robot.steer(speed, dir, -1);
            }
        }
        else if (angle > 0)
        {
            robot.steer(speed, dir, -1);
        }
        else if (angle < 0)
        {
            robot.steer(speed, dir, 1);
        }
    }
    robot.steer(0, FORWARD, 0);
}

void runDistance(int speed, int dir, int Distance) {
    PRIM("runDistance");
    runTime(30,BACKWARD,0,20);
    runTime(30,FORWARD,0,20);
    reset_enconder();
    int32_t  encoder = 25*Distance;
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);

    if (dir == FORWARD) {
        while (true) {
            if ((millis() - startTime) >= timeoutMs) break;   // no llego: se corta igual
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;
            if (frCount >= encoder || flCount >= encoder) break;

            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();
            DBG_PRINT(flCount);
            DBG_PRINT(" | ");
            DBG_PRINT(frCount);
            //DBG_PRINTLN(fr.pulseCount);
            digitalWrite(13, HIGH);
            delay(10);
           
            if (Serial5.available() > 0) {   // drena y tira: ver runTime()
                const int lecturas = Serial5.read();
                DBG_PRINT(lecturas);
                (void)lecturas;
            }
           
            if (digitalRead(32) == 1) { // switch is off
                Serial5.write(255);
                break;
            }
        }
    }else{
         while (true)
        {
            if ((millis() - startTime) >= timeoutMs) break;   // no llego: se corta igual
            int32_t frCount = fr.pulseCount;
            int32_t flCount = fl.pulseCount;

            if (frCount <= -encoder || flCount <= -encoder) break;
            robot.steer(speed, dir, 0);
            serviceMotionBackgroundTasks();
            DBG_PRINT(flCount);
            DBG_PRINT(" | ");
            DBG_PRINT(frCount);
            //DBG_PRINTLN(fr.pulseCount);
            delay(10);
            if (Serial5.available() > 0) {   // drena y tira: ver runTime()
                const int lecturas = Serial5.read();
                DBG_PRINT(lecturas);
                (void)lecturas;
            }
           
            if (digitalRead(32) == 1) { // switch is off
                Serial5.write(255);
                break;
            }
        }
         
         
    }

    robot.steer(0, dir, 0);   // se frena SIEMPRE al salir, se haya llegado o no
}


void runDistanceEvacuacion(int speed, int Distance) {
    PRIM("runDistEvac");
    runTime(30, BACKWARD, 0, 20);
    runTime(30, FORWARD, 0, 20);
    reset_enconder();
    int32_t encoder = 25 * Distance;
    unsigned long startTime = millis();
    unsigned long timeoutMs = computeRunDistanceTimeoutMs(speed, Distance);

    while (true) {
        if ((millis() - startTime) >= timeoutMs) break;   // no llego: se corta igual
        int32_t frCount = fr.pulseCount;
        int32_t flCount = fl.pulseCount;
        if (frCount >= encoder || flCount >= encoder) break;   // llego a la distancia pedida
        front_distance = sonar[0].ping_cm();
        if (front_distance != 0 && front_distance <= 18) break; // pared cerca -> corto el avance
        robot.steer(speed, FORWARD, 0);
        serviceMotionBackgroundTasks();
        delay(10);

        if (Serial5.available() > 0) {   // drena y tira: ver runTime()
            // OJO: la lectura va en su PROPIA sentencia y NO adentro del
            // DBG_PRINT. Con MODO_DIAGNOSTICO=1 la macro es `do {} while(0)` y
            // DESCARTA SUS ARGUMENTOS: metida adentro, Serial5.read() no se
            // llamaria y el buffer de Serial5 no se drenaria nunca.
            const int lecturas = Serial5.read();
            DBG_PRINT(lecturas);
            (void)lecturas;
        }

        if (digitalRead(32) == 1) { // switch off
            Serial5.write(255);
            break;
        }
    }

    robot.steer(0, FORWARD, 0);   // se frena SIEMPRE al salir
}

// non-blocking delay that keeps processing serial and claw state
void nonBlockingDelay(unsigned long ms)
{
    unsigned long start = millis();
    while (millis() - start < ms)
    {
        claw.update();
        if (Serial5.available() > 0)
            serialEvent5();
    }
}

void accionNegro() {
#if NEGRO_SALIDA_GIRO
    // De que lado ESTUVO la pared antes de ver el negro: la memoria que se
    // refresco durante toda la evacuacion. -1 = izquierda, +1 = derecha, 0 = no.
    // La lectura del instante NO sirve: en la salida la pared se abre justo
    // donde esta la cinta y el ultrasonido de ese lado ve vacio.
    int ladoPared = 0;
    if (g_evac_pared_lado != 0 &&
        (millis() - g_evac_pared_ms) <= NEGRO_SALIDA_MEMORIA_MS)
        ladoPared = g_evac_pared_lado;
    DBG_PRINT("[EVAC] NEGRO salida: pared memoria=");
    DBG_PRINT(g_evac_pared_lado);
    DBG_PRINT(" edad_ms=");
    DBG_PRINT(g_evac_pared_ms ? (long)(millis() - g_evac_pared_ms) : -1L);
    DBG_PRINT(" -> lado=");
    DBG_PRINTLN(ladoPared);
#endif
    runDistance(30, FORWARD, 5);
#if NEGRO_SALIDA_GIRO
    // Giro hacia el lado CONTRARIO a la pared. runAngle: POSITIVO = derecha,
    // NEGATIVO = izquierda (misma convencion que los verdes, case 5 / case 6).
    if (ladoPared < 0)
        runAngle(30, FORWARD,  NEGRO_SALIDA_GIRO_GRADOS);   // pared izq -> derecha
    else if (ladoPared > 0)
        runAngle(30, FORWARD, -NEGRO_SALIDA_GIRO_GRADOS);   // pared der -> izquierda
    robot.steer(0, FORWARD, 0);
#endif
    Serial5.write(249);
    reset_color_history();
    digitalWrite(RELAY, LOW);

    // 1) romper la inercia (jiggle corto, como hace runDistance al arrancar)
    runTime(20, BACKWARD, 0, 300);
    runTime(20, FORWARD, 0, 300);

    // 2) quedarse QUIETO leyendo serial mientras la RPi sale de evacuacion y
    //    arranca la vision de linea (teardown ~1-2 s). Asi no se mueve con datos viejos.

    robot.steer(0, FORWARD, 0);
    unsigned long t0 = millis();
    while (millis() - t0 < 800) {
        serialEvent5();
    }

    // 3) limpiar lo stale de evacuacion para arrancar linea derecho

    green_state = 0;
    action = 7;
    steer = 0;
    speed = 0;
    taskDone = true;

    rutina = "linea";
}

void accionPlateado() {
    runDistance(30, BACKWARD, 10);
    runAngle(30, FORWARD, 90);
    runDistanceEvacuacion(30, 30);   // avanza 30 cm pero corta si hay pared a <=18 cm
    robot.steer(0, FORWARD, 0);
    reset_color_history();  // descarta muestras previas para no re-disparar con color stale
}



// Lecturas frescas consecutivas necesarias para confirmar un color antes de
// actuar en evacuacion. Subir si hay falsos positivos; bajar si queda lento.
constexpr uint8_t EVAC_COLOR_CONFIRM_SAMPLES = 1;

// Confirma que el sensor ve 'objetivo' en N lecturas frescas seguidas.
// Filtra ruido/sombras/reflejos que provocaban falsos "Negro"/"Plateado".
bool confirmarColor(const String &objetivo)
{
    for (uint8_t i = 0; i < EVAC_COLOR_CONFIRM_SAMPLES; i++)
    {
        if (get_color_fresh() != objetivo)
            return false;
    }
    return true;
}

// Plateado en evacuacion: misma robustez temporal que el plateado de LINEA.
// El primer get_color_fast() ya vio Plateado; exigimos 3 lecturas FRESCAS
// adicionales consecutivas antes de ejecutar accionPlateado().
constexpr uint8_t EVAC_PLATEADO_CONFIRM_SAMPLES = 3;
bool confirmarPlateadoEvacuacion()
{
    for (uint8_t i = 0; i < EVAC_PLATEADO_CONFIRM_SAMPLES; i++)
    {
        if (get_color_fresh() != "Plateado")
            return false;
    }
    return true;
}

// En LINEA el plateado tiene autoridad fisica. Exigimos TRES lecturas FRESCAS
// adicionales al primer get_color_fast() que lo detecto: 4 ventanas filtradas
// consecutivas en total. Cada ventana ya promedia 3 muestras APDS, por lo que
// un reflejo aislado no puede mandar 0xF1. La camara no participa.
constexpr uint8_t LINE_PLATEADO_CONFIRM_SAMPLES = 3;
bool confirmarPlateadoLinea()
{
    for (uint8_t i = 0; i < LINE_PLATEADO_CONFIRM_SAMPLES; i++)
    {
        if (get_color_fresh() != "Plateado")
            return false;
    }
    return true;
}

// Detecta color en evacuacion con confirmacion anti-ruido y ejecuta la accion
// correspondiente. Devuelve true si ejecuto una accion (Negro o Plateado).
bool procesarColorEvacuacion()
{
    color_detected = get_color_fast();

    // El robot se despego del plateado (ve otro color confiable): rehabilita
    // una futura deteccion. "Desconocido" = sin dato fresco, no cuenta.
    if (color_detected != "Plateado" && color_detected != "Desconocido")
    {
        silver_latch = false;
    }

    if (color_detected == "Negro" && confirmarColor("Negro"))
    {
        accionNegro();
        return true;
    }

    if (color_detected == "Plateado" && !silver_latch && confirmarPlateadoEvacuacion())
    {
        Serial.println("[EVAC] Plateado confirmado -> accionPlateado");
        accionPlateado();
        silver_latch = true;  // ya atendido; no repetir hasta despegarse del plateado
        return true;
    }

    return false;
}

// ############################################################################
// #                                                                          #
// #  8.  EVACUACION: colores, esquive, finales de carrera                    #
// #                                                                          #
// ############################################################################

#define TARGET_DISTANCE 70.0 // distancia deseada en cm
#define KP_DISTANCE 0.05     // constante proporcional para la distancia
#define KP_ANGLE 0.05        // constante proporcional para el ángulo de rotación
#define MAX_STEER 1          // valor máximo de steer permitido
#define ANGLE_THRESHOLD 2.0  // umbral de inclinación en grados (yaw)
#define TARGET_ANGLE 0       // ángulo objetivo (robot paralelo a la pared)
float pitch=0;
float leer_yaw()
{
    sensors_event_t event;
    bno.getEvent(&event);
    float yaw = event.orientation.x; // Yaw es el ángulo de rotación (en grados)
    return yaw;
}
float leer_pitch()
{  
    sensors_event_t event;
    bno.getEvent(&event);

    pitch = event.orientation.y; // eje que estás usando para inclinación
    return pitch;
}
int ajustarVelocidadPorPendiente(int velocidadBase)
{
    leer_pitch();

    int velocidadAjustada = velocidadBase;
    if (pitch > 3.9)
    {
            velocidadAjustada = 45;
    }
    else if (pitch > 25)
    {
           runTime(100, FORWARD, 0.35, 100);
           runTime(100, FORWARD, -0.35, 100);
    }
    else{
        velocidadAjustada= 40;
    }
    return velocidadAjustada;
}
// Función para calcular la diferencia de ángulo en un rango circular de 0 a 360 grados
float calcularDiferenciaAngulo(float anguloActual, float anguloObjetivo)
{
    float error = anguloObjetivo - anguloActual;

    // Ajustar la diferencia para que esté en el rango [-180, 180]
    if (error > 180)
    {
        error -= 360;
    }
    else if (error < -180)
    {
        error += 360;
    }

    return error;
}


// Decide la correccion ANTES de action 2 usando la recuperacion que REALMENTE
// hizo la Teensy, no intentando volver a ver la linea despues del plateado.
void corregirEntradaPlateadoDesdeRecovery()
{
    const unsigned long ahora = millis();
    const unsigned long edad = g_silver_rec_ms ? (ahora - g_silver_rec_ms)
                                               : 0xFFFFFFFFUL;

    // RECTA/GAP, sin recovery, o recovery viejo: ya venia bien orientado.
    if (g_silver_rec_kind != SILVER_REC_LATERAL ||
        g_silver_rec_pivot_sign == 0 ||
        g_silver_rec_actual_deg < 5.0f ||
        edad > SILVER_REC_MEMORY_MS)
    {
        robot.steer(0, FORWARD, 0);
        return;
    }

    // "La mitad al sentido inverso": usamos la mitad del YAW FISICO realmente
    // recorrido por el recovery. Asi un timeout o deslizamiento no se supone.
    float objetivo = g_silver_rec_actual_deg * SILVER_REC_UNDO_FACTOR;
    objetivo = constrain(objetivo, 0.0f, 30.0f);

    const int signoCorreccion = -g_silver_rec_pivot_sign;
    const float yaw0 = leer_yaw();
    const unsigned long t0 = millis();

    robot.steer(0, FORWARD, 0);
    while (digitalRead(SWITCH) == 0)
    {
        serviceMotionBackgroundTasks();
        if (Serial5.available() > 0)
            serialEvent5();

        const float girado = fabs(calcularDiferenciaAngulo(yaw0, leer_yaw()));
        if (girado >= objetivo)
            break;
        if ((millis() - t0) >= SILVER_REC_UNDO_MAX_MS)
            break;

        robot.steer(SILVER_REC_UNDO_VEL, FORWARD,
                    signoCorreccion > 0 ? RECUP_PIVOTE_ROT : -RECUP_PIVOTE_ROT);
    }

    robot.steer(0, FORWARD, 0);

    // Consumir la memoria: este plateado ya fue corregido.
    g_silver_rec_kind = SILVER_REC_NONE;
    g_silver_rec_pivot_sign = 0;
    g_silver_rec_actual_deg = 0.0f;
    g_silver_rec_ms = 0;
}

void resetear_bno()
{
    if (!bno.begin())
    {
        handleBnoInitFailure();
    }
    bno.setExtCrystalUse(true);
    delay(200);
}



// Prototipo: la funcion se define mas abajo, pero maniobraEsquive() la usa antes.
bool retrocederHastaFinales(int velocidad);

// Decide si hay que esquivar en evacuacion. Dos casos separados:
//  - Esquina de deposito: la camara ve triangulo rojo/verde (green_state 8/9)
//    Y el ultrasonido confirma cercania (<=31 cm). Fusion camara + ultrasonido.
//  - Pared frontal lisa: solo ultrasonido, dispara mas cerca (<=18 cm).
bool debeEsquivar()
{
    if ((green_state == 8 || green_state == 9) && front_distance != 0 && front_distance <= 31)
        return true;

    return false;
}

// Maniobra de esquive en evacuacion: retrocede, gira 90, avanza paralelo, gira
// 90, retrocede hasta los finales de carrera y se reacomoda. La usan tanto la
// esquina de deposito como la pared frontal lisa.
void maniobraEsquive()
{
    resetear_bno();
    runTime(30, BACKWARD, 0, 300);
    runAngle(30, FORWARD, 90);
    runDistance(30, FORWARD, 27);
    runAngle(30, FORWARD, 90);

    // Finales de carrera con pull-down + antirrebote de 50 ms.
    // Si no se confirman antes del timeout, no continuar la maniobra.
    if (!retrocederHastaFinales(20))
        return;

    runAngle(30, FORWARD, -90);
}


// CONTADOR DE MARCAS VERDES.
// HOY QUEDA SIEMPRE EN 0: el contador que lo incrementaba era del desafio de
// Roboliga (paridad de verdes para elegir el lado del esquive e invertir las
// zonas de deposito) y se saco el 2026-09-06 junto con el resto de ese modo.
// Se conserva la variable porque la telemetria la publica en el campo `verd`,
// y porque el case 6 y el case 5 la miran: con el contador apagado esa
// comparacion da siempre la rama normal.
int  verdes_total = 0;

// Cooldown despues de cruzar la linea roja, para que un rebote del sensor no
// vuelva a disparar la parada.
unsigned long rojo_ignorar_hasta = 0;


// ############################################################################
// #                                                                          #
// #  9.  ANTI-ATASCO (loma de burro) Y TRACCION EN RAMPA                     #
// #                                                                          #
// ############################################################################

// ============================================================================
//  DETECCION DE ATASCO — loma de burro (palos sobre la linea).
//  DATO DE CALIBRACION: en la loma una rueda queda CLAVADA (~0) y la otra
//  patina (~45). En recta las DOS giran parejo (~40 c/u). Discriminador:
//     min(|frD|,|flD|)  ->  ~0 atascado   /   ~40 recta
//  Atascado = una rueda parada (min < UMBRAL_RUEDA) sostenido >= STUCK_TIME_MS.
//  La aceleracion NO servia (igual en recta que trabado) -> descartada.
// ============================================================================
long          stuck_lastFr    = 0;
long          stuck_lastFl    = 0;
unsigned long stuck_since      = 0;
unsigned long stuck_lastSample = 0;
unsigned long atascoArmedSince = 0;    // cuando arranco a correr (startUp) -> para el grace period
const long          UMBRAL_RUEDA    = 15;    // pulsos/100ms: por debajo, una rueda esta "clavada" (TUNEAR)
const unsigned long STUCK_SAMPLE_MS = 100;   // cada cuanto mido las ruedas
const unsigned long STUCK_TIME_MS   = 3000;  // 3 s con una rueda parada = atascado
const unsigned long ATASCO_GRACE_MS = 8000;  // no disparar los primeros 8 s tras arrancar (ponerlo en pista)

// --- Traccion en pendiente: pisar las traseras cuando el pitch esta inclinado ---
const float  PITCH_RAMPA       = 12.0;  // pitch (grados) desde el cual considero "pendiente" (llano ~±5, rampa ~23)
const double POTENCIA_TRASERAS = 80;   // potencia (rpm objetivo, 0-159) para las traseras en pendiente

bool chequearAtasco(int comandoVel)
{

    unsigned long now = millis();

    // grace: recien arranco / apreto switch -> NO dispara (molesto al ponerlo en pista)
    if (now - atascoArmedSince < ATASCO_GRACE_MS)
    {
        stuck_since = now;
        return false;
    }

    // no comandado a avanzar -> no cuenta como atasco
    if (comandoVel <= 0)
    {
        stuck_since = now;
        return false;
    }

    // muestreo las ruedas cada STUCK_SAMPLE_MS (no en cada vuelta)
    if (now - stuck_lastSample >= STUCK_SAMPLE_MS)
    {
        stuck_lastSample = now;
        long frNow = (long)fr.pulseCount, flNow = (long)fl.pulseCount;
        long frD = labs(frNow - stuck_lastFr);   // giro rueda DERECHA en ~100 ms
        long flD = labs(flNow - stuck_lastFl);   // giro rueda IZQUIERDA en ~100 ms
        stuck_lastFr = frNow; stuck_lastFl = flNow;
        long minRueda = min(frD, flD);

        // las DOS ruedas giran (recta/curva/pivote) -> avanza bien -> reinicio el timer
        if (minRueda >= UMBRAL_RUEDA)
            stuck_since = now;
        // una rueda clavada (min < umbral) -> no reinicio, acumula tiempo
    }

    // EN PENDIENTE: NO disparar atasco (la rueda clavada es por la inclinacion;
    // el retroceso rampa abajo seria peligroso -> lo maneja el boost de traseras).
    if (pitch > PITCH_RAMPA)
    {
        stuck_since = now;
        return false;
    }

    // una rueda parada sostenido por >= STUCK_TIME_MS -> atascado
    return (now - stuck_since >= STUCK_TIME_MS);
}

void recuperarAtasco()
{
    DBG_PRINTLN("[ATASCO] rueda clavada -> retro + avance brusco");
    runTime(90,  BACKWARD, 0, 150);   // retroceso corto (bajar de la loma)
    runTime(100, FORWARD,  0, 250);   // avance a full para saltarla
    // reiniciar el detector
    stuck_lastFr = (long)fr.pulseCount;
    stuck_lastFl = (long)fl.pulseCount;
    stuck_since  = millis();
    stuck_lastSample = millis();
}


#if TELEMETRIA
// ============================================================================
//  enviarTelemetria() — arma UNA linea JSON con TODOS los valores de control y
//  la manda por Serial8 a la ESP32-MINI. Rate-limited (10 Hz) y NO BLOQUEANTE
//  (si no hay lugar en el TX, descarta el frame). Se puede llamar desde
//  cualquier lado del loop sin miedo: el rate-limit y la guardia lo protegen.
//
//  Esquema (agrupado por subsistema, claves cortas para ahorrar ancho de banda):
//   t                          millis del Teensy
//   rpi  {speed,steer,green,silver,rxb,rxf,st}   enlace con la Raspberry (Serial5)
//   col  {d,r,g,b,c,ok}         sensor de color APDS9960 (filtrado) + estado
//   us   {f,l,r}                ultrasonidos frente/izq/der (cm)
//   tof  {l,r}                  ToF VL53L0X izq/der (mm)
//   imu  {yaw,pit,rol,cen}      BNO055 (grados) + angulo de referencia 'centrar'
//   enc  {fl,fr,bl,br}          contadores de encoder de las 4 ruedas
//   fsm  {rut,act,task,up,resc,balls,dep,verd,evi,evs,slatch,pared,lado,ran}
//   io   {sw,fcl,fcr,rel,buz,led}  entradas/salidas digitales
//   claw {busy}                garra ocupada (maquina de estados no bloqueante)
// ============================================================================
// Sanea floats para que el JSON SIEMPRE sea valido: un NaN/inf (p.ej. BNO sin
// calibrar o desconectado) imprimiria "nan"/"inf" y JSON.parse() en la GUI
// fallaria -> se quedaria en modo demo silenciosamente. Con esto, 0.0 en su lugar.
static float sanef(float v)
{
    return (isnan(v) || isinf(v)) ? 0.0f : v;
}

// ############################################################################
// #                                                                          #
// #  10.  TELEMETRIA JSON HACIA LA ESP32 (Serial8, 10 Hz)                    #
// #                                                                          #
// #  NO INTRUSIVA POR DISENIO: si el buffer TX no tiene lugar, DESCARTA el   #
// #  frame. Nunca frena el control. La telemetria MIRA, no toca: por eso aca no#
// #  se llama a getSpeed(), que le corromperia el promedio movil al PID.     #
// ############################################################################

void enviarTelemetria()
{
    if (!telemetria.debeEnviar())
    {
        return;
    }

    // IMU fresco (una sola lectura I2C por frame, ~2 ms cada 100 ms: despreciable).
    sensors_event_t ev;
    bno.getEvent(&ev);
    float t_yaw = sanef(ev.orientation.x);
    float t_pit = sanef(ev.orientation.y);
    float t_rol = sanef(ev.orientation.z);
    float t_cen = sanef(centrar);
    // VELOCIDAD ANGULAR REAL, medida por el giroscopo (no derivada del yaw:
    // a 10 Hz derivar el yaw da ruido, y ademas el yaw envuelve en 0/360).
    // Es EL dato que faltaba: dice cuanto giro el robot DE VERDAD, para poder
    // contrastarlo con cuanto se le pidio. Si se comanda curva y esto queda
    // cerca de cero, el robot no esta girando aunque las ruedas 'obedezcan'.
    // Se mandan los tres ejes porque cual es el yaw depende del montaje y eso
    // se identifica en banco (ver la skill imu-bno055).
    imu::Vector<3> gv = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);
    float t_gx = sanef(gv.x()), t_gy = sanef(gv.y()), t_gz = sanef(gv.z());

    // Color filtrado actual (lee los buffers de historial, no dispara el sensor).
    uint16_t cr = 0, cg = 0, cb = 0, cc = 0;
    get_filtered_color(cr, cg, cb, cc);

    // NOTA: los %s (color_detected/rutina/pared/lado_plateado) SOLO deben contener
    // literales cerrados sin comillas ni backslash (ver known_colors y las rutinas),
    // asi el JSON queda valido sin necesidad de escaparlos.
    long g_age = g_last_ms ? (long)(millis() - g_last_ms) : -1L;   // ms desde el ultimo verde (-1 = nunca)

    // ---- PWM y RPM por rueda ------------------------------------------------
    // OJO: aca NO se llama a getSpeed(). Esa funcion ESCRIBE _rpmlist[3] y
    // _realrpm, y _realrpm es el input del PID (ver drivebase.h: PID(&_realrpm,
    // &_pwmVal, &_rpm, ...)). Llamarla desde la telemetria le meteria al control
    // una muestra fuera de fase y le corromperia el promedio movil. La regla es
    // que la telemetria MIRA, no toca.
    // _realrpm y _pwmVal son los ultimos valores que YA calculo el lazo: leerlos
    // es una lectura pura. Tampoco hace falta noInterrupts(): la unica ISR que
    // existe (updatePulse) toca _begin/_end/_rpmlist/pulseCount, nunca estos dos.
    // getPWM() si es puro (solo devuelve _pwmVal) y _pwmVal ya viene acotado a
    // 0..255 por SetOutputLimits del PID.
    // _realrpm en cambio NO esta acotado (es 111111.0/promedio, puede dar ~444444
    // con el motor casi parado), asi que se satura y se pasa por sanef() para que
    // un NaN no invalide el JSON entero del frame.
    const int pwm_fl = (int)fl.getPWM(), pwm_fr = (int)fr.getPWM();
    const int pwm_bl = (int)bl.getPWM(), pwm_br = (int)br.getPWM();
    const float r_fl = sanef(fl._realrpm), r_fr = sanef(fr._realrpm);
    const float r_bl = sanef(bl._realrpm), r_br = sanef(br._realrpm);
    const int rpm_fl = (int)constrain(r_fl, -9999.0f, 99999.0f);
    const int rpm_fr = (int)constrain(r_fr, -9999.0f, 99999.0f);
    const int rpm_bl = (int)constrain(r_bl, -9999.0f, 99999.0f);
    const int rpm_br = (int)constrain(r_br, -9999.0f, 99999.0f);

    // ---- Ventana de la cabecera --------------------------------------------
    // El "hdr" NO va en todos los frames: iria 10 veces por segundo y cada uno
    // le cuesta al colector un SELECT y dos UPDATE sobre la tabla de corridas.
    // Va solo durante los primeros 2 s despues de que el switch arranca, que a
    // 10 Hz son ~20 frames: mas que suficiente para que el colector lo vea aunque
    // pierda alguno.
    // El flanco se detecta con estaticas ACA ADENTRO, y no tocando loop(): asi
    // este cambio no agrega ni una linea al lazo de control. No se puede perder
    // el flanco porque para llegar a startUp=true el robot pasa si o si por dos
    // runTime de 300 ms (600 ms), seis veces el periodo de muestreo.
    // Resta unsigned, que es el idioma del archivo y sobrevive al wrap de millis().
    static bool prevUp = false;
    static unsigned long hdrDesde = 0;
    if (startUp && !prevUp) { hdrDesde = millis(); }
    prevUp = startUp;
    const bool hdrOn = startUp && (millis() - hdrDesde < 2000UL);

#define TSAT(v) (int)constrain(sanef(v), -9999.0f, 99999.0f)
    static unsigned long tlm_trunc = 0;   // frames descartados por no entrar en buf
    static char buf[1664];   // subido de 1152: el frame v3 agrega dir/set/tog/drv/loop
    int n = snprintf(
        buf, sizeof(buf),
        "{\"t\":%lu,%s"
        "\"rpi\":{\"speed\":%d,\"steer\":%.3f,\"green\":%d,\"silver\":%d,\"rxb\":%lu,\"rxf\":%lu,\"st\":%d},"
        "\"col\":{\"d\":\"%s\",\"dc\":\"%s\",\"r\":%u,\"g\":%u,\"b\":%u,\"c\":%u,\"ok\":%d},"
        "\"us\":{\"f\":%d,\"l\":%d,\"r\":%d},"
        "\"tof\":{\"l\":%d,\"r\":%d},"
        "\"imu\":{\"yaw\":%.1f,\"pit\":%.1f,\"rol\":%.1f,\"cen\":%.1f},"
        "\"enc\":{\"fl\":%ld,\"fr\":%ld,\"bl\":%ld,\"br\":%ld},"
        // flancos CRUDOS: siempre incrementan, sin mirar _dir. Es la unica
        // medida de movimiento fisico que no depende de ninguna suposicion,
        // y sin ella la causa G (el estimador miente) no se puede evaluar.
        "\"raw\":{\"fl\":%lu,\"fr\":%lu,\"bl\":%lu,\"br\":%lu},"
        "\"pwm\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"rpm\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        // ---- DIAGNOSTICO DE CURVAS (frame v3) ----
        // dir = sentido COMANDADO a cada rueda. Sin esto, `rpm` es una MAGNITUD
        //       y no se puede distinguir una rueda que va en reversa de una que
        //       va hacia adelante: es justo el dato que falta para ver por que
        //       la rueda interna no toma la curva.
        // set = consigna de RPM de cada rueda. Junto con rpm da el error QUE VE
        //       EL PID, que es lo unico que el lazo usa para decidir el PWM.
        // tog = veces que se disparo el toggle `if (_pwmVal < 10) _dir = !_dir`.
        // drv = lo que recibio DriveBase y por que rama del case 7 se paso.
        "\"dir\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"set\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"tog\":{\"fl\":%lu,\"fr\":%lu,\"bl\":%lu,\"br\":%lu},"
        "\"drv\":{\"rot\":%.3f,\"ls\":%d,\"rs\":%d,\"dir\":%d,\"ram\":%d},"
        "\"loop\":{\"ms\":%lu,\"max\":%lu},"
        // ENVOLVENTE de la ventana de 100 ms: min y max de PWM y RPM por rueda.
        // pmin bajo con consigna viva = el esfuerzo se desplomo en algun momento
        // de la ventana. rmax alto = la rueda giro mas rapido de lo pedido (la
        // estan arrastrando). Los instantaneos solos se pierden los transitorios.
        "\"pmin\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"pmax\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"rmin\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"rmax\":{\"fl\":%d,\"fr\":%d,\"bl\":%d,\"br\":%d},"
        "\"gyr\":{\"x\":%.1f,\"y\":%.1f,\"z\":%.1f},"
        "\"rxage\":%ld,"
        "\"fsm\":{\"rut\":\"%s\",\"act\":%d,\"task\":%d,\"up\":%d,\"resc\":%d,\"balls\":%d,\"dep\":%d,\"verd\":%d,\"evi\":%d,\"evs\":%d,\"slatch\":%d,\"pared\":\"%s\",\"lado\":\"%s\",\"prim\":\"%s\",\"ran\":%d},"
        "\"io\":{\"sw\":%d,\"fcl\":%d,\"fcr\":%d,\"rel\":%d,\"buz\":%d,\"led\":%d},"
        "\"claw\":{\"busy\":%d},"
        "\"grn\":{\"rx\":[%lu,%lu,%lu,%lu],\"act\":[%lu,%lu,%lu,%lu],\"kill\":[%lu,%lu,%lu,%lu],\"lt\":%d,\"age\":%ld,\"lrc\":%d}}\n",
        millis(), hdrOn ? HDR_JSON : "",
        (int)speed, steer, green_state, silver_line, serial_bytes_rx, serial_frames_rx, serial5state,
        // d  = lo que el sensor ve AHORA (se refresca con cada muestra) -> para CALIBRAR.
        // dc = lo que esta usando el control (solo se asigna en las rutinas de marcha).
        last_color_detected.c_str(), color_detected.c_str(),
        (unsigned)cr, (unsigned)cg, (unsigned)cb, (unsigned)cc, color_sensor_ok ? 1 : 0,
        front_distance, left_distance, right_distance,
        distance_left_tof, distance_right_tof,
        t_yaw, t_pit, t_rol, t_cen,
        (long)fl.pulseCount, (long)fr.pulseCount, (long)bl.pulseCount, (long)br.pulseCount,
        (unsigned long)fl.pulsesRaw, (unsigned long)fr.pulsesRaw,
        (unsigned long)bl.pulsesRaw, (unsigned long)br.pulsesRaw,
        pwm_fl, pwm_fr, pwm_bl, pwm_br,
        rpm_fl, rpm_fr, rpm_bl, rpm_br,
        fl._dir, fr._dir, bl._dir, br._dir,
        (int)fl._rpm, (int)fr._rpm, (int)bl._rpm, (int)br._rpm,
        (unsigned long)fl.dirToggles, (unsigned long)fr.dirToggles,
        (unsigned long)bl.dirToggles, (unsigned long)br.dirToggles,
        robot._rotation, (int)robot._leftspeed, (int)robot._rightspeed,
        robot._direction, g_line_branch,
        g_loop_dt, g_loop_dt_max,
        TSAT(fl._pwmMin), TSAT(fr._pwmMin), TSAT(bl._pwmMin), TSAT(br._pwmMin),
        TSAT(fl._pwmMax), TSAT(fr._pwmMax), TSAT(bl._pwmMax), TSAT(br._pwmMax),
        TSAT(fl._rpmMin), TSAT(fr._rpmMin), TSAT(bl._rpmMin), TSAT(br._rpmMin),
        TSAT(fl._rpmMax), TSAT(fr._rpmMax), TSAT(bl._rpmMax), TSAT(br._rpmMax),
        t_gx, t_gy, t_gz,
        g_last_rx_ms ? (long)(millis() - g_last_rx_ms) : -1L,
        rutina.c_str(), action, taskDone ? 1 : 0, startUp ? 1 : 0, (int)rescateState,
        ball_counter, veces_deposit, verdes_total,
        evacuacion_iniciada ? 1 : 0, evacuacion_straight ? 1 : 0, silver_latch ? 1 : 0,
        pared.c_str(), lado_plateado.c_str(), g_prim, RanNumber,
        digitalRead(SWITCH), digitalRead(FCL), digitalRead(FCR),
        digitalRead(RELAY), digitalRead(BUZZER), digitalRead(LED_ROJO),
        claw.busy() ? 1 : 0,
        g_rx[0], g_rx[1], g_rx[2], g_rx[3],
        g_act[0], g_act[1], g_act[2], g_act[3],
        g_kill[0], g_kill[1], g_kill[2], g_kill[3],
        g_last_type, g_age, g_last_recheck_gs);

    // ---- Un frame que no entero NO SE MANDA ---------------------------------
    // Antes esto clampeaba n y mandaba igual los 895 bytes cortados al medio.
    // Eso es peor que no mandar nada, y la cadena entera lo demuestra: un frame
    // truncado sale SIN el '\n' final (es el ultimo caracter del formato), la
    // ESP32 lo concatena con el frame siguiente, la linea se pasa de
    // TLM_LINE_MAX y descarta LOS DOS. O sea: por mandar basura se pierde
    // ademas un frame sano, y se gasta el 78% del ancho de banda del enlace en
    // algo que ningun JSON.parse va a poder leer.
    // Descartar de este lado preserva la unica invariante que importa: todo lo
    // que sale del Teensy es una linea JSON completa y valida.
    // El contador se incrementa ANTES del bloque de diagnostico por USB: si no,
    // el dia que TODOS los frames truncaran no se imprimiria nunca el numero que
    // explica por que se apago la telemetria.
    const bool trunco = (n < 0 || n >= (int)sizeof(buf));
    if (trunco)
    {
        tlm_trunc++;
    }

#if TELEMETRIA_DEBUG_USB
    // DIAGNOSTICO: una linea/seg por USB con cuantos frames salieron por Serial8.
    // env sube  -> el Teensy transmite (el problema es el cable/pin del lado ESP32).
    // env queda -> revisar Serial8/firmware.
    static unsigned long lastDbg = 0;
    if (millis() - lastDbg >= 1000)
    {
        lastDbg = millis();
        DBG_PRINT("[TLM] env=");
        DBG_PRINT(telemetria.framesEnviados());
        DBG_PRINT(" desc=");
        DBG_PRINT(telemetria.framesDescartados());
        // trunc = frames que no entraron en buf[] y se descartaron ACA. Si este
        // numero sube, el frame crecio mas que el buffer: hay que agrandar buf
        // (y TLM_LINE_MAX del lado ESP32) o acortar campos. len = el tamanio del
        // ultimo frame que salio, para ver cuanto margen queda de verdad.
        DBG_PRINT(" trunc=");
        DBG_PRINT(tlm_trunc);
        DBG_PRINT(" len=");
        DBG_PRINT(n);
        DBG_PRINT(" avail=");
        DBG_PRINTLN(Serial8.availableForWrite());
    }
#endif

    if (trunco)
    {
        return;
    }
    telemetria.enviar(buf, n);
    g_loop_dt_max = 0;

    // el min/max es POR VENTANA: se rearma recien despues de mandarlo
    fl.resetEnvolvente(); fr.resetEnvolvente();
    bl.resetEnvolvente(); br.resetEnvolvente();   // el pico es POR FRAME, no acumulado desde el arranque
}
#endif // TELEMETRIA

#if TELEMETRIA
// Espera 'ms' (MISMA duracion que delay(ms)) pero aprovechando la pausa para
// mandar telemetria y refrescar el muestreo de color. Se usa SOLO en el loop de
// idle (switch apagado): ahi es donde se calibra el sensor y hace falta ver los
// valores fluidos, no una foto por segundo. No altera el timing del parpadeo.
void delayTelemetria(unsigned long ms)
{
    unsigned long t0 = millis();
    while (millis() - t0 < ms)
    {
        enviarTelemetria();
        get_color_fast();   // muestra fresca para el panel de calibracion
        yield();            // conserva la semantica de delay() (serialEventN, USB)
        delay(2);
    }
}
#else
inline void delayTelemetria(unsigned long ms) { delay(ms); }
#endif

// ############################################################################
// #                                                                          #
// #  11.  setup()  -  arranque y verificacion de sensores                    #
// #                                                                          #
// #  SI EL BNO055 NO ARRANCA, EL ROBOT NO ARRANCA: parpadeo + chicharra para #
// #  siempre. Es deliberado. Sin IMU no hay runAngle, y sin runAngle el robot#
// #  no puede hacer ninguna maniobra: es mejor que se note en el banco de    #
// #  pruebas que a mitad de la corrida.                                      #
// #  Si el que no arranca es el APDS (color), el robot SI arranca: avisa con 3#
// #  parpadeos y sigue. Se puede seguir la linea sin color; lo que se pierde es#
// #  la entrada a evacuacion y la deteccion del rojo final.                  #
// ############################################################################

void setup()
{
    DIAG_SETUP();   // registrador CSV de 200 Hz: VACIO en competencia (ver diagnostico.h)

    robot.steer(0, 0, 0);
    // claw.lift();  // Moved to begin()
    angulo_rescate = fmod(20, 360.0);
    //DBG_PRINTLN(angulo_rescate);
    attachInterrupt(digitalPinToInterrupt(27), ISR1, CHANGE);
    attachInterrupt(digitalPinToInterrupt(5), ISR2, CHANGE);
    attachInterrupt(digitalPinToInterrupt(38), ISR3, CHANGE);
    attachInterrupt(digitalPinToInterrupt(2), ISR4, CHANGE);
    pinMode(SWITCH, INPUT_PULLUP); // SWITCH
    pinMode(BUZZER, OUTPUT);       // BUZZER
    pinMode(LED_ROJO, OUTPUT);     // LED ROJO
    pinMode(LED_BUILTIN, OUTPUT);  //  LED BUILT-IN for debugging
    pinMode(RELAY, OUTPUT);          
//Serial1.begin(57600);          // for reading IMU
    Serial5.begin(115200);         // for reading data from rpi and state
#if TELEMETRIA
    telemetria.begin(TLM_BAUD);    // TELEMETRIA: abre Serial8 hacia la ESP32-MINI (AP + GUI)
#endif
    delay(200);
    //Serial.begin(115200);          // displays ultrasound ping result
    // Initialise BNO055
    if (!bno.begin())
    {
        handleBnoInitFailure();
    }
    bno.setExtCrystalUse(true);

    // Initialise APDS9960 Color Sensor
    color_sensor_ok = apds.begin();
    if (!color_sensor_ok)
    {
        notifyOptionalSensorWarning();   // 3 parpadeos + chicharra, y sigue igual
    }
    else
    {
        apds.enableColor(true);
        apds.enableProximity(true);
    }

    // Initialise TOF
    Wire1.begin(); // Initialize the first I2C bus
    Wire2.begin(); // Initialize the second I2C bus

    left_tof.setBus(&Wire2);  // Assign the first bus to Sensor 1
    right_tof.setBus(&Wire1); // Assign the second bus to Sensor 2

    left_tof.setAddress(0x30);  // Set unique address for Sensor 1
    right_tof.setAddress(0x30); // Set unique address for Sensor 2

    // Continue with your setup and loop functions as before

    // EL TIMEOUT VA ANTES DE init(), NO DESPUES. El constructor del VL53L0X deja
    // io_timeout = 0, y su guarda es  (io_timeout > 0 && ...), que con 0 da false
    // SIEMPRE. Con setTimeout() escrito despues, durante todo init() los tres
    // while de la libreria -getSpadInfo y las dos performSingleRefCalibration-
    // tienen adentro un if que no se cumple nunca: son bucles SIN SALIDA. Tres
    // por sensor, dos sensores. Si un ToF contesta pero no completa la secuencia
    // (brownout al arrancar motores y servos, o un reset de la Teensy con el
    // sensor todavia alimentado y en modo continuo), setup() no termina: LED
    // apagado y puerto mudo, en la pista y delante del arbitro.
    // Regla general: un setTimeout() se configura en el mismo bloque donde se
    // construye el objeto, nunca despues de la primera llamada bloqueante.
    // EL BUS I2C CORRE A 100 kHz (el default de Wire.begin() en Teensy 4.x) y se
    // deja asi A PROPOSITO. Subirlo a 400 kHz dividiria por 4 el costo del
    // BNO055, del APDS9960 y de los dos ToF, PERO los pull-up internos del
    // Teensy 4.1 son debiles y hay TRES esclavos colgados del bus. Nunca se
    // midio en banco: un bus lento anda, un bus que se cuelga deja al robot
    // mudo en la pista. Si algun dia se prueba, es un Wire.setClock(400000UL)
    // aca, y hay que mirar 10 minutos que ningun sensor devuelva basura.
    left_tof.setTimeout(500);
    right_tof.setTimeout(500);

    left_tof.init();
    // Presupuesto de medicion: el default del VL53L0X es 33 ms y el minimo
    // admitido 20 ms; nunca se habia llamado. En linea los ToF ya no se leen,
    // asi que esto NO cambia el periodo del seguimiento de linea: importa en
    // seguimiento de pared, que si los relee.
    left_tof.setMeasurementTimingBudget(TOF_PRESUPUESTO_US);
    left_tof.startContinuous();

    right_tof.init();
    right_tof.setMeasurementTimingBudget(TOF_PRESUPUESTO_US);
    right_tof.startContinuous();
    pinMode(FCL, INPUT_PULLDOWN);
    pinMode(FCR, INPUT_PULLDOWN);

    // Inicializar la garra después de setup
    claw.begin();
    for (int i = 0; i < 20; i++)
    {
        Serial5.write(0xFA);
        delay(100);
    }

}


bool retrocederHastaFinales(int velocidad)
{
    const unsigned long CONFIRMACION_MS = 50;
    const unsigned long TIMEOUT_MS = 20000;

    unsigned long inicio = millis();
    unsigned long ambosDesde = 0;

    while (digitalRead(SWITCH) == 0)
    {
        robot.steer(velocidad, BACKWARD, 0);
        serialEvent5();

        bool fcl = (digitalRead(FCL) == HIGH);
        bool fcr = (digitalRead(FCR) == HIGH);

        // Los DOS tienen que permanecer presionados continuamente.
        if (fcl && fcr)
        {
            if (ambosDesde == 0)
            {
                ambosDesde = millis();
            }

            if (millis() - ambosDesde >= CONFIRMACION_MS)
            {
                robot.steer(0, FORWARD, 0);
                return true;
            }
        }
        else
        {
            // Si cualquiera se suelta, empieza a contar de nuevo.
            ambosDesde = 0;
        }

        // Seguridad por si un final nunca llega.
        if (millis() - inicio >= TIMEOUT_MS)
        {
            robot.steer(0, FORWARD, 0);
            return false;
        }
    }

    robot.steer(0, FORWARD, 0);
    return false;
}

// ############################################################################
// #                                                                          #
// #  12.  loop()  -  idle / arranque / linea / rescate / evacuacion          #
// #                                                                          #
// #  TRES ESTADOS SEGUN EL SWITCH (pin 32):                                  #
// #                                                                          #
// #    switch APAGADO (==1)  -> lazo de IDLE: motores en cero, garra arriba, #
// #       LED y luz roja parpadeando, y se resetea TODO el estado de la corrida.#
// #       Es tambien el modo de CALIBRACION: la telemetria y el sensor de color#
// #       siguen fluyendo, asi que se pueden mirar los valores del APDS sin  #
// #       riesgo de que el robot se mueva.                                   #
// #                                                                          #
// #    switch RECIEN ENCENDIDO (==0 y !startUp) -> arranque: dos sacudones   #
// #       cortos para romper la inercia y avisar 0xF9 a la Pi.               #
// #                                                                          #
// #    switch ENCENDIDO -> las tres rutinas, en este orden:                  #
// #         rutina == "linea"       seguimiento + maniobras (el grueso)      #
// #         rutina == "rescate"     zona de evacuacion, garra                #
// #         rutina == "evacuacion"  busqueda de pared y deposito             #
// #                                                                          #
// #  EL SWITCH CORTA EN CUALQUIER PUNTO: todos los while largos lo miran.    #
// ############################################################################

void loop()
{
    DIAG_TICK();
    // DIAGNOSTICO: periodo del loop y su pico (se resetea al mandar el frame).
    {
        static unsigned long _lastLoopUs = 0;
        unsigned long _nowUs = micros();
        if (_lastLoopUs) {
            g_loop_dt = (_nowUs - _lastLoopUs) / 1000UL;
            if (g_loop_dt > g_loop_dt_max) g_loop_dt_max = g_loop_dt;
        }
        _lastLoopUs = _nowUs;
    }
    // Advance non-blocking claw state machine each loop
    claw.update();
    // Actualizar máquina de estados de rescate no-bloqueante
    actualizarRescate();
    enviarTelemetria();   // TELEMETRIA (rate-limited + no bloqueante)
    if (digitalRead(32) == 1)
    {                               // switch is off
        robot.steer(0, FORWARD, 0); // stop moving
        claw.lift();
        claw.sortLeft();
        Serial5.clear();
        evacuacion_iniciada = false;
        evacuacion_straight = false;
        silver_latch = false;
        action = 7;
        startUp = false;
        g_recup_signo = 0;
        g_recup_rumbo_camino_rx = 0.0;
        g_recup_rumbo_camino_rx_ms = 0;
        g_recup_episodio_activo = false;
        g_recup_habilitada = false;
        g_recup_gs0_desde = 0;
        g_gap_retro_pulsos = 0;
        resetGapState();
        rojo_ignorar_hasta = 0;
        g_evac_pared_lado = 0;
        g_evac_pared_ms = 0;
        taskDone = true;
        Serial5.write(255);
        verdes_total=0;
        while (true)
        {
            // DRENAR EL REGISTRADOR TAMBIEN EN IDLE. Sin esto, con el switch
            // apagado el CSV no sale y el puerto parece MUDO -que es justo el
            // sintoma de un setup() colgado-. El 2026-08-22 eso hizo diagnosticar
            // tres veces "la placa no arranco" cuando la placa estaba perfecta,
            // y perder corridas creyendo que un flasheo no habia entrado.
            // Es el mismo bug que ya se habia arreglado para el seguimiento de
            // linea (DIAG_TICK no se alcanzaba) y que quedo en el idle.
            // Y es JUSTO en idle cuando uno quiere verificar que binario corre:
            // con el switch apagado, o sea sin riesgo de que el robot se mueva.
            DIAG_TICK();
            enviarTelemetria();   // TELEMETRIA en idle (util para calibrar en banco)
            robot.steer(0, 0, 0);
                    digitalWrite(RELAY,LOW);
            claw.lift();
            get_color_fast();
            serialEvent5();
            centrar = leer_yaw();            
            centrar = fmod(centrar, 360.0);
             if (centrar < 0) centrar += 360;
            digitalWrite(LED_BUILTIN, HIGH);
            // digitalWrite(BUZZER, HIGH);
            digitalWrite(LED_ROJO, HIGH);
            delayTelemetria(500);   // misma pausa, pero con telemetria/color fluidos (calibracion)
            robot.steer(0, 0, 0);
            //DBG_PRINTLN(leer_pitch()); // para imprimirlo
           get_color_fast();
           //DBG_PRINTLN("FCL: " + String(digitalRead(FCL)));
            //DBG_PRINTLN("FCR: " + String(digitalRead(FCR)));
            digitalWrite(LED_BUILTIN, LOW);
            digitalWrite(BUZZER, LOW);
            digitalWrite(LED_ROJO, LOW);
            digitalWrite(RELAY,LOW);
            claw.open();
            delayTelemetria(500);   // idem: telemetria fluida en idle

            get_color_fast();

            if (digitalRead(SWITCH) == 0)
            {
                break;
            }
        }
    }
    else if (digitalRead(32) == 0 && !startUp)
    {
        digitalWrite(LED_BUILTIN, LOW);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, LOW);
        runTime(20, BACKWARD, 0, 300);
        runTime(20, FORWARD, 0, 300);
        // Serial5.write(254);
        startUp = true;
        atascoArmedSince = millis();   // arranca el grace: no dispara el anti-atasco al ponerlo en pista
        rutina = "linea";
        evacuacion_iniciada = false;
        evacuacion_straight = false;
        silver_latch = false;
        rescateAvisado = false;
        g_evac_pared_lado = 0;
        g_evac_pared_ms = 0;
        g_silver_rec_kind = SILVER_REC_NONE;
        g_silver_rec_pivot_sign = 0;
        g_silver_rec_actual_deg = 0.0f;
        g_silver_rec_ms = 0;
        claw.lift();
        claw.depositCenter();
        action = 7;
        Serial5.write(249);


    }
    else
    {

        digitalWrite(LED_BUILTIN, HIGH);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, HIGH);
        while (rutina == "linea" && digitalRead(32) == 0)
        {
            serialEvent5();

            // WATCHDOG DE COMUNICACION. Si la Raspberry dejo de hablar, frenar.
            // Ejecutar una orden vieja indefinidamente es peor que quedarse
            // quieto: el robot se va de la pista solo. Ver el punto 1.5 del panel.
            // Si NUNCA llego una trama, `g_last_rx_ms` vale 0. Ese es el caso
            // MAS peligroso -la Pi muerta desde el arranque, el robot ejecutando
            // el default- asi que la cuenta arranca al entrar al lazo de linea.
            if (g_wd_ref_ms == 0)
                g_wd_ref_ms = millis();
            const unsigned long ref = g_last_rx_ms ? g_last_rx_ms : g_wd_ref_ms;
            const long edadRx = (long)(millis() - ref);
            if ((unsigned long)edadRx > WATCHDOG_MS)
            {
                if (g_wd_stale_ms == 0)
                    g_wd_stale_ms = millis();
            }
            else
            {
                g_wd_stale_ms = 0;
            }

            // La confirmacion es por TIEMPO y no por vueltas del lazo: al sacar
            // los ToF el periodo del lazo bajo de ~30 ms a menos de 10, y un
            // criterio de seguridad no puede cambiar de significado porque se
            // toque otra cosa.
            if (g_wd_stale_ms != 0 &&
                (millis() - g_wd_stale_ms)
                    >= WATCHDOG_CONFIRMA_MS)
            {
                if (!g_wd_activo)
                {
                    g_wd_activo = true;
                    DBG_PRINT("[WD] sin tramas hace ");
                    DBG_PRINT(edadRx);
                    DBG_PRINTLN(" ms: FRENO");
                }
                robot.steer(0, FORWARD, 0);
                digitalWrite(LED_BUILTIN, (millis() / 150) % 2);
                continue;          // no se decide nada con datos rancios
            }
            if (g_wd_activo)
            {
                g_wd_activo = false;
                DBG_PRINTLN("[WD] volvieron las tramas: sigo");
            }

            DIAG_TICK();   // drenaje del registrador DURANTE el seguimiento de linea
            enviarTelemetria();   // TELEMETRIA (seguimiento de linea)
            bool plateadoDetectado = false;
            color_detected = get_color_fast();
            // Los ToF NO se leen aca a proposito: nadie los consume durante el
            // seguimiento de linea y costaban ~30 ms de espera activa POR VUELTA
            // (readRangeContinuousMillimeters bloquea hasta tener muestra nueva).
            // De los tres ultrasonidos solo hace falta el frontal.
            leer_ultrasonido_frontal();

#if PLATEADO_TEENSY
            if (color_detected == "Plateado" && confirmarPlateadoLinea()) {
                    if (!rescateAvisado) {
                        // RECTO => 0 grados. LATERAL => mitad del giro real,
                        // en sentido inverso. No usamos camara sobre plateado.
                        corregirEntradaPlateadoDesdeRecovery();
                        Serial5.write(TEENSY_ACK_RESCATE_APDS);
                        rescateAvisado = true;
                    }
                    plateadoDetectado = true;
            }
#endif

            // LINEA ROJA = FIN DE LA CORRIDA. El robot para 10 s y se sale del
            // lazo de linea. Es lo que pide Rescue Line: la roja marca la meta.
            // (Habia dos politicas mas -girar 180, y distinguir roja simple de
            //  doble por movimiento- que eran de Roboliga; se sacaron el
            //  2026-09-06 y estan en el historial de git.)
            if (color_detected == "Rojo" && millis() >= rojo_ignorar_hasta) {
                runTime(0, FORWARD, 0, 10000);
                break;
            }
           
            if (taskDone)
            { // robot is currently not performing any task

                // //DBG_PRINTLN("Incoming Task: ");
                // //DBG_PRINTLN(green_state);
                // ------------------------------------------------------------
                // ARBITRO DE GS4: evita falsos positivos y re-disparos.
                // La Pi solo debe mandar 4 despues de una perdida CONFIRMADA.
                // Aun asi, Teensy exige que antes haya habido al menos 300 ms
                // continuos de comando normal (GS=0).
                // ------------------------------------------------------------
                if (green_state == 0)
                {
                    action = 7;

                    if (g_gap_activo)
                        resetGapState();

                    if (g_recup_episodio_activo)
                    {
                        // La Pi confirmo que la linea volvio. Cerrar el episodio,
                        // pero NO permitir otro inmediatamente por un frame que
                        // vuelva a quedar ciego.
                        g_recup_episodio_activo = false;
                        g_recup_habilitada = false;
                        g_recup_gs0_desde = millis();
                        g_recup_signo = 0;
                        g_recup_retroceso_hecho = false;
                        g_recup_giro_hecho = false;
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                    }
                    else
                    {
                        if (g_recup_gs0_desde == 0)
                            g_recup_gs0_desde = millis();
                        if (!g_recup_habilitada &&
                            (millis() - g_recup_gs0_desde) >= RECUP_REARME_TEENSY_MS)
                            g_recup_habilitada = true;
                    }
                }

                if (green_state == 1)
                {
                    // Maniobra verde conocida: GS4 queda desarmado.
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    // Verde a la IZQUIERDA. (Habia una guarda `verdes_total < 4`
                    // que despues de 4 verdes mandaba action = 20, y NO EXISTE un
                    // case 20: el verde se ignoraba en silencio. Venia del
                    // contador de Roboliga, que hoy deja verdes_total en 0, asi
                    // que la guarda nunca disparaba. Se saco el 2026-09-06.)
                    action = 6;
                }
                if (green_state == 2)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    action = 5;   // verde a la DERECHA. Ver el case de arriba.
                }

                if (green_state == LINEA_PERDIDA_GS)
                {
                    g_recup_gs0_desde = 0;

                    if (g_recup_episodio_activo)
                    {
                        // MISMA perdida: continuar la recuperacion, no re-disparar.
                        action = 4;
                    }
                    else if (g_recup_habilitada)
                    {
                        // Flanco valido: empieza UN episodio.
                        g_recup_episodio_activo = true;
                        g_recup_habilitada = false;
                        g_recup_retroceso_hecho = false;
                        g_recup_giro_hecho = false;
                        action = 4;
                    }
                    else
                    {
                        // GS4 al arrancar, despues de un verde o por rebote: no mover.
                        action = RECUP_WAIT_ACTION;
                    }
                }
                if (green_state == GAP_BUSQUEDA_GS)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_signo = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    if (!g_gap_activo)
                    {
                        g_gap_activo = true;
                        g_gap_origen_enviado = false;
                        g_gap_timeout_enviado = false;
                        g_gap_inicio_fl = (long)fl.pulseCount;
                        g_gap_inicio_fr = (long)fr.pulseCount;
                        g_gap_inicio_ms = millis();

                        // Pi clasifico RECTA/GAP: si enseguida aparece plateado,
                        // NO hay nada que "deshacer".
                        g_silver_rec_kind = SILVER_REC_RECTA;
                        g_silver_rec_pivot_sign = 0;
                        g_silver_rec_actual_deg = 0.0f;
                        g_silver_rec_ms = millis();
                    }
                    action = GAP_ACTION;
                }

                if (green_state == PERDIDA_FAILSAFE_GS)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    resetGapState();
                    action = PERDIDA_FAILSAFE_ACTION;
                }

                if (green_state == 3)
                {
                    g_recup_habilitada = false;
                    g_recup_episodio_activo = false;
                    g_recup_gs0_desde = 0;
                    g_recup_rumbo_camino_rx = 0.0;
                    g_recup_rumbo_camino_rx_ms = 0;
                    action = 14;
                }
                if (front_distance != 0 && front_distance < 2)
                {
                get_color_fast();
#if PLATEADO_TEENSY
            if (color_detected == "Plateado" && confirmarPlateadoLinea()) {
                    if (!rescateAvisado) {
                        // RECTO => 0 grados. LATERAL => mitad del giro real,
                        // en sentido inverso. No usamos camara sobre plateado.
                        corregirEntradaPlateadoDesdeRecovery();
                        Serial5.write(TEENSY_ACK_RESCATE_APDS);
                        rescateAvisado = true;
                    }
                    plateadoDetectado = true;
            }
#endif
                    action = 1;
                }
               
                if (green_state == 14)
                {
                    action = 12;
                }
                // `silver_line` de Raspberry se conserva en el protocolo por
                // compatibilidad, pero NO tiene autoridad de rescate. Plateado se
                // decide unicamente por APDS (`plateadoDetectado`).
                if (plateadoDetectado) {
                    action = 2;
                }


                switch (action)
                {
                case 1:
                    digitalWrite(BUZZER, HIGH);
                    delay(100);
                    digitalWrite(BUZZER, LOW);

                        // DE QUE LADO SE ESQUIVA EL OBSTACULO: AL AZAR, 1=izq 2=der.
                        // Al azar y no fijo para que dos intentos seguidos no
                        // repitan el mismo error si de ese lado no habia lugar.
                        //
                        // EL PRIMER random(3) PARECE UN RESTO Y NO SE PUEDE SACAR:
                        // su resultado se pisa en la linea siguiente, pero la
                        // llamada AVANZA EL GENERADOR. Como nadie llama a
                        // randomSeed(), la secuencia es la MISMA en cada
                        // encendido, asi que borrarlo cambiaria de que lado
                        // esquiva el robot en cada obstaculo de la corrida.
                        RanNumber = random(3);
                        RanNumber = random(1, 3);
                        if (RanNumber == 1)
                        {
                            runAngle(25, FORWARD, -95);
                                                        get_color_fast();
                                        while (digitalRead(32) == 0)
                            {
                                robot.steer(77, FORWARD, -0.38);
                                // serialEvent5();
                                if (get_color_fast() == "Negro")
                                {
                                    runAngle(70, FORWARD, -90);
                                    break;
                                }
                            }
                        }
                        if (RanNumber == 2)
                        {
                            runAngle(25, FORWARD, 95);
                            get_color_fast();
                            while (digitalRead(32) == 0)
                            {
                                robot.steer(77, FORWARD, 0.38);
                                // serialEvent5();
                                if (get_color_fast() == "Negro")
                                {
                                    runAngle(70, FORWARD, 90);
                                    break;
                                }
                            }
                        }
                   
                    break;
                case 2:
                    digitalWrite(BUZZER, HIGH);
                    delay(100);
                    digitalWrite(BUZZER, LOW);
                    rutina="rescate";
                    rescateAvisado = true;

                    digitalWrite(RELAY,HIGH);
                    ball_counter=0;
                    veces_deposit = 0;
                    depositando=false;
                    runTime(30, FORWARD, 0,800);
                    runTime(0, FORWARD, 0, 1000);
                    leer_ultrasonidos();
                    if(left_distance>right_distance){
                        runAngle(30,FORWARD,-20);
                    }
                    if(right_distance>left_distance){
                        runAngle(30,FORWARD,20);}
                     runTime(30,FORWARD,0,2000);


                   
                    leer_ultrasonidos();
                    if(left_distance < right_distance)
                    {
                        /*runAngle(30,FORWARD,90);
                        runTime(0,BACKWARD,0,900);
                        runTime(40,BACKWARD,0,380);
                        runTime(40,FORWARD,0,800);
                        runTime(0,BACKWARD,0,1000);*/
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0);
                        if (angulo_rescate < 0) angulo_rescate += 360;
                        runTime(20,FORWARD,0,1500);
                        runTime(0,BACKWARD,0,1000);
                        runAngle(30,FORWARD,45);
                        runTime(30,FORWARD,0,3000);

                        pared="left";
                        lado_plateado="derecha";
                    }
                    if(right_distance < left_distance)
                    {
                       /* runAngle(30,FORWARD,-90);
                        runTime(0,BACKWARD,0,900);
                        runTime(60,BACKWARD,0,380);
                        runTime(40,FORWARD,0,800);*/
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0);
                        if (angulo_rescate < 0)                        
                        angulo_rescate += 360;
                        runTime(20,FORWARD,0,1500);
                        runTime(0,BACKWARD,0,1000);
                        runAngle(30,FORWARD,-45);
                        runTime(30,FORWARD,0,3000);
                        pared="right";
                        lado_plateado="izquierda";
                    }
                   /* if(right_distance && left_distance>=50){
                        leer_ultrasonidos();

                        while(front_distance>12){
                            robot.steer(25,FORWARD,0);
                            leer_ultrasonidos();
                        }
                        runAngle(30,FORWARD,180);
                        runTime(0,BACKWARD,0,800);
                        runTime(60,BACKWARD,0,200);
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0);
                        if (angulo_rescate < 0)                        
                        angulo_rescate += 360;
                        lado_plateado="medio";
                        pared="derecha";
                    }*/
                    runTime(0,FORWARD,0,3000);
                    break;
                case 4:   // LINEA PERDIDA: UN SOLO RETROCESO -> REANALIZA -> PIVOTE
                {
                    // IMPORTANTE: GS4 puede durar muchos loops. Las fases quedan
                    // enclavadas para que el MISMO episodio NO vuelva a retroceder.
                    //   1) retroceso recto UNA SOLA VEZ;
                    //   2) CAMINO decide lado desde atras;
                    //   3) pivote UNA SOLA VEZ;
                    //   4) si GS4 sigue activo despues, quedarse quieto.

                    if (!g_recup_retroceso_hecho)
                    {
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                        g_recup_signo = 0;
                        g_line_branch = 14;
                        const long retroFl0 = (long)fl.pulseCount;
                        const long retroFr0 = (long)fr.pulseCount;
                        runTime(RECUP_VEL, BACKWARD, 0, RECUP_MS);
                        const long retroFl = labs((long)fl.pulseCount - retroFl0);
                        const long retroFr = labs((long)fr.pulseCount - retroFr0);
                        // Si uno de los dos encoders delanteros no dio una referencia
                        // minima, NO inventar la pose original: sin ACK 0xEE el GAP
                        // termina por fail-safe en vez de aceptar la linea vieja.
                        g_gap_retro_pulsos = (retroFl >= 10 && retroFr >= 10)
                            ? (retroFl + retroFr) / 2
                            : 0;
                        serialEvent5();
                        g_recup_retroceso_hecho = true;
                        Serial5.write(TEENSY_ACK_RETRO_DONE);

                        // Todo heading visto mientras se movia hacia atras se descarta:
                        // queremos decidir con la pose NUEVA y ya quieta.
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                    }

                    // Si ya completo el pivote en este episodio, NO repetir ni giro
                    // ni retroceso aunque la Pi siga mandando GS4.
                    if (g_recup_giro_hecho)
                    {
                        robot.steer(0, FORWARD, 0);
                        break;
                    }

                    // Reanalizar quieto. Si CAMINO aun no tiene heading fresco,
                    // se queda quieto y en el siguiente loop vuelve a MIRAR, no a retroceder.
                    const unsigned long tAnalisis = millis();
                    robot.steer(0, FORWARD, 0);
                    while (digitalRead(32) == 0 &&
                           (millis() - tAnalisis) < RECUP_REANALISIS_MS)
                    {
                        serviceMotionBackgroundTasks();
                        if (Serial5.available() > 0)
                            serialEvent5();
                    }
                    serialEvent5();

                    const unsigned long edadCamino = g_recup_rumbo_camino_rx_ms
                        ? (millis() - g_recup_rumbo_camino_rx_ms)
                        : 0xFFFFFFFFUL;

                    if (g_recup_rumbo_camino_rx_ms == 0 ||
                        edadCamino > RECUP_REANALISIS_EDAD_MS ||
                        fabs(g_recup_rumbo_camino_rx) < RECUP_STEER_MIN)
                    {
                        g_recup_signo = 0;
                        robot.steer(0, FORWARD, 0);
                        break;
                    }

                    g_recup_signo = (g_recup_rumbo_camino_rx > 0.0) ? 1 : -1;

                                        // ANGULO ESCALADO: CAMINO conserva lado + intensidad, pero NO
                    // se interpreta 1:1 como grados fisicos de yaw.
                    // Ej.: 20->35, 30->37.4, 45->41.6, 60->45.8, 90->54.2 grados.
                    const float headingCaminoDeg =
                        (float)(fabs(g_recup_rumbo_camino_rx) * 90.0);
                    float objetivoGiro = RECUP_GIRO_BASE_GRADOS
                                         + RECUP_GIRO_CAMINO_K * headingCaminoDeg;

                    // Asimetria FISICA observada 2026-09-12: a la derecha el robot gira
                    // menos de lo pedido (video completo_auth_1, ~43 pedidos: DER 33-42,
                    // IZQ 45-48). OJO SIGNO: g_recup_signo < 0 es la DERECHA (rx negativo
                    // -> rot negativo -> drivebase gira a la derecha). La version del
                    // 12-sep tenia "> 0" y sumaba el extra a la IZQUIERDA.
                    // Con el extra en 0 el pivote es identico al de completo_auth_1.
                    if (g_recup_signo < 0)
                        objetivoGiro += RECUP_GIRO_DER_EXTRA_GRADOS;

                    objetivoGiro = constrain(objetivoGiro,
                                             RECUP_GIRO_MIN_GRADOS,
                                             RECUP_GIRO_MAX_GRADOS);

                    const float yaw0 = leer_yaw();
                    const unsigned long tg0 = millis();

                    while (digitalRead(32) == 0)
                    {
                        serviceMotionBackgroundTasks();
                        if (Serial5.available() > 0)
                            serialEvent5();

                        // Una vez tomada la decision, COMPLETAR el objetivo fisico.
                        // Un GS0 temprano puede significar que reaparecio la linea vieja
                        // durante el pivote; no debe truncar la orientacion.
                        const float girado = fabs(calcularDiferenciaAngulo(
                                                    yaw0, leer_yaw()));
                        if (girado >= objetivoGiro)
                            break;
                        if ((millis() - tg0) >= RECUP_GIRO_MAX_MS)
                            break;

                        g_line_branch = 13;
                        robot.steer(RECUP_GIRO_VEL, FORWARD,
                                    g_recup_signo > 0 ? RECUP_PIVOTE_ROT
                                                     : -RECUP_PIVOTE_ROT);
                    }

                    robot.steer(0, FORWARD, 0);
                    // Aviso a la Pi: desde aca puede COMPLETAR EL GIRO si la cinta quedo
                    // de frente. Una Pi sin ese parche ignora el byte.
                    Serial5.write(TEENSY_ACK_PIVOTE_DONE);

                    // Guardar lo que FISICAMENTE giro este recovery. El APDS puede
                    // aparecer inmediatamente despues, cuando la Pi ya haya vuelto
                    // a GS0 y g_recup_signo normalmente se borra.
                    g_silver_rec_kind = SILVER_REC_LATERAL;
                    g_silver_rec_pivot_sign = g_recup_signo;
                    g_silver_rec_actual_deg =
                        fabs(calcularDiferenciaAngulo(yaw0, leer_yaw()));
                    g_silver_rec_ms = millis();

                    g_recup_giro_hecho = true;
                    serialEvent5();

                    if (green_state != LINEA_PERDIDA_GS)
                    {
                        g_recup_signo = 0;
                        g_recup_rumbo_camino_rx = 0.0;
                        g_recup_rumbo_camino_rx_ms = 0;
                        g_recup_episodio_activo = false;
                        g_recup_habilitada = false;
                        g_recup_gs0_desde = millis();
                        g_recup_retroceso_hecho = false;
                        g_recup_giro_hecho = false;
                    }
                    break;
                }
                case GAP_ACTION:
                {
                    if (!g_gap_activo)
                    {
                        g_gap_activo = true;
                        g_gap_inicio_fl = (long)fl.pulseCount;
                        g_gap_inicio_fr = (long)fr.pulseCount;
                        g_gap_inicio_ms = millis();
                    }
                    const long avanzados = gapPulsosDesdeInicio();
                    const long origenObjetivo = g_gap_retro_pulsos + 25L * GAP_ORIGIN_MARGIN_CM;
                    if (!g_gap_origen_enviado && g_gap_retro_pulsos > 0 && avanzados >= origenObjetivo)
                    {
                        Serial5.write(TEENSY_ACK_GAP_ORIGIN);
                        g_gap_origen_enviado = true;
                    }
                    const bool limiteDist = avanzados >= (25L * GAP_MAX_CM);
                    const bool limiteTiempo = (g_gap_inicio_ms != 0 && (millis() - g_gap_inicio_ms) >= GAP_MAX_MS);
                    if (limiteDist || limiteTiempo)
                    {
                        robot.steer(0, FORWARD, 0);
                        if (!g_gap_timeout_enviado)
                        {
                            Serial5.write(TEENSY_ACK_GAP_TIMEOUT);
                            g_gap_timeout_enviado = true;
                        }
                        action = PERDIDA_FAILSAFE_ACTION;
                        break;
                    }
                    robot.steer(GAP_VEL, FORWARD, 0);
                    break;
                }
                case PERDIDA_FAILSAFE_ACTION:
                    robot.steer(0, FORWARD, 0);
                    break;

                case RECUP_WAIT_ACTION:
                    // GS4 no habilitado: NO retrocede, NO gira y NO reutiliza
                    // la accion anterior. Solo espera una trama valida nueva.
                    robot.steer(0, FORWARD, 0);
                    if (Serial5.available() > 0)
                        serialEvent5();
                    break;
                case 6:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    telemGreenResultado(1, green_state);   // solo cuenta, no decide
                    // GIRA SIEMPRE. NO se vuelve a preguntar por el verde despues
                    // de avanzar: a los 800 ms el cuadrado YA salio del cuadro de
                    // la camara, la Pi manda green_state = 0 y el giro no se
                    // ejecutaba nunca. El sintoma en pista era que el robot
                    // bajaba la velocidad -eso es el runTime- y despues seguia
                    // derecho sin doblar. La decision se tomo al poner action = 6;
                    // volver a preguntarla despues de moverse es preguntar otra
                    // cosa. Si hay verdes espurios, se confirman ANTES de avanzar.
                    //
                    // SIGNO: NEGATIVO gira a la IZQUIERDA. Si algun dia la camara
                    // queda espejada, se invierten los signos del case 6 y del 5.
                    runAngle(35, FORWARD, -60);
                    break;
                case 5:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    telemGreenResultado(2, green_state);   // solo cuenta, no decide
                    runAngle(25, FORWARD, 60);   // POSITIVO = derecha. Ver el case 6.
                    break;
                case 7: // linetrack
                    // Guardamos el steer normal solo para diagnostico. La direccion
                    // de recovery YA NO sale de aca: sale del angle recibido junto
                    // con GS=4, que la Raspberry llena con CAMINO+MONO.
                    g_recup_signo = 0;
               
                    {int velocidadAjustada = ajustarVelocidadPorPendiente(VELOCIDAD_BASE_LINEA);

                     if (chequearAtasco(velocidadAjustada)) {   // obstaculo alto: no avanza -> recupero
                         g_line_branch = 9;
                         recuperarAtasco();
                         break;
                     }
                    // ----------------------------------------------------------
                    //  UMBRALES DE LA TELEMETRIA (y uno de control)
                    //
                    //  Los dos primeros SOLO clasifican la rama para el campo
                    //  `ram` del JSON y del CSV: no deciden nada del movimiento.
                    //  LINE_PIVOT_STEER SI decide, y en dos lugares: es el techo
                    //  puntual de `rot` y el denominador de la rampa de velocidad.
                    //  Si alguien lo "limpia", se lleva puesta la rampa entera.
                    // ----------------------------------------------------------
                    const double LINE_CURVE_STEER = 0.08;       // solo telemetria
                    const double LINE_HARD_CURVE_STEER = 0.35;  // solo telemetria
                    const double LINE_PIVOT_STEER = 0.92;       // CONTROL: ver abajo

                    double steerCmd = constrain(steer * LINE_STEER_GAIN, -1.0, 1.0);
                    double absSteer = fabs(steerCmd);

                    // ----------------------------------------------------------
                    //  DE ANGULO A `rot`  ->  rot = absSteer ^ LINE_ROT_EXP
                    //
                    //  ES UNA RAMPA CONCAVA, Y ESA ES LA PALANCA QUE IMPORTA.
                    //  La distancia que el robot recorre POR CADA GRADO que gira
                    //  vale (1-rot)/(k*rot), y la VELOCIDAD SE CANCELA: frenar lo
                    //  hace ir mas lento pero recorre los mismos centimetros
                    //  mientras completa el giro. Verificado el 22-ago-2026
                    //  comparando dos corridas a 29 y 37 rpm:
                    //      rot 0,20-0,40   0,49 cm/grado (lenta) vs 0,44 (rapida)
                    //      rot 0,60-0,80   0,10                  vs 0,11
                    //  Lo UNICO que reduce esa distancia es subir `rot`, y ahi el
                    //  efecto es enorme: de rot 0,30 a 0,87 cae 12 veces.
                    //
                    //  En la curva de 90 grados que se le escapaba:
                    //      rot 0,30 -> 44 cm recorridos mientras gira
                    //      rot 0,87 -> 3,6 cm
                    //  y el robot ve unos 2-3 cm de piso por delante. Con una
                    //  rampa LINEAL un angulo moderado (absSteer 0,20) pedia
                    //  rot 0,20 y se comia 75 cm de pista girando: perdia la
                    //  linea seguro. Con el exponente por debajo de 1 la rampa
                    //  sube rapido al principio y sigue llegando a 1 en el
                    //  extremo. LINE_ROT_EXP = 1.0 vuelve a la rampa lineal.
                    // ----------------------------------------------------------

                    // ----------------------------------------------------------
                    //  PIVOTE CON HISTERESIS  -  HOY NO SE EJECUTA (ver el panel 1.1)
                    //
                    //  `s_en_pivote` NO PUEDE VOLVERSE true con la configuracion
                    //  actual: absSteer sale de un constrain(...,-1,1) antes del
                    //  fabs, asi que su techo es 1.0, y LINE_PIVOTE_ENTRA vale
                    //  1.01. Es un interruptor deliberado, no un descuido, y esta
                    //  todo el bloque escrito para poder volver a prenderlo
                    //  bajando ese umbral a 0.60.
                    //
                    //  QUE HACIA CUANDO ESTABA PRENDIDO. Entraba con absSteer
                    //  alto y NO SOLTABA hasta quedar alineado. La histeresis
                    //  hacia falta porque con un solo umbral el robot picoteaba
                    //  el giro: medido el 22-ago, 3,6 entradas y salidas POR
                    //  SEGUNDO, episodios de 160 ms y 8 grados de mediana, y solo
                    //  4 de 76 episodios pasaban los 45 grados. Una curva cerrada
                    //  pide 90.
                    //
                    //  POR QUE SE APAGO IGUAL. Con la histeresis puesta tampoco
                    //  alcanzaba: 284 episodios simulados sobre el rxsteer real
                    //  dieron 210 ms y 6,0 GRADOS reales de mediana, con el 1 %
                    //  pasando los 45. La razon de fondo es que LA CAMARA NO MIDE
                    //  RUMBO: se mueve 7 a 9,6 grados de imagen por cada grado
                    //  real del robot, asi que once grados de giro bastan para
                    //  que el angulo cruce el cero y la condicion de salida se
                    //  cumpla aunque la curva no haya terminado. La condicion
                    //  estaba escrita sobre la variable equivocada.
                    //  Y el costo era caro: con rot = 1 el centro no avanza, y el
                    //  robot se pasaba el 29,7 % del tiempo girando sin avanzar.
                    //  Apagandolo eso cayo a 7,8 % y empezo a tomar los codos.
                    //
                    //  El tope de tiempo (LINE_PIVOTE_MAX_MS) es la red: si la
                    //  vision se quedara pidiendo giro para siempre -linea
                    //  perdida, un reflejo, un verde mal leido- el robot no puede
                    //  quedarse girando en el lugar indefinidamente.
                    // ----------------------------------------------------------
                    static bool s_en_pivote = false;
                    static unsigned long s_pivote_t0 = 0;
                    static unsigned long s_alineado_t0 = 0;
                    if (!s_en_pivote && absSteer >= LINE_PIVOTE_ENTRA)
                    {
                        s_en_pivote = true;
                        s_pivote_t0 = millis();
                    }
                    else if (s_en_pivote)
                    {
                        // NO ALCANZA CON QUE EL ANGULO BAJE UNA VEZ: hay que
                        // SOSTENERLO. Con la histeresis simple, absSteer entraba
                        // en 0,70 y caia a 0,12 en 245 ms habiendo girado solo
                        // 11 GRADOS, y el 81 % de las salidas volvia a pivotear
                        // antes de 400 ms. Esa alineacion era FALSA.
                        if (absSteer > LINE_PIVOTE_SALE)
                            s_alineado_t0 = 0;              // se desalineo: reiniciar
                        else if (s_alineado_t0 == 0)
                            s_alineado_t0 = millis();       // primer frame alineado

                        bool sostenido = (s_alineado_t0 != 0 &&
                                          millis() - s_alineado_t0 >= LINE_PIVOTE_CONFIRMA_MS);
                        if (sostenido ||
                            millis() - s_pivote_t0 > LINE_PIVOTE_MAX_MS)
                        {
                            s_en_pivote = false;
                            s_alineado_t0 = 0;
                        }
                    }

                    double rot;
                    if (s_en_pivote)
                    {
                        rot = 1.0;   // giro sobre el eje: el centro NO avanza
                    }
                    else
                        rot = pow(absSteer, LINE_ROT_EXP);
                    // GIRO EN EL LUGAR PUNTUAL, y este SI corre: cuando la vision
                    // pide fondo de escala (0,92 de 1,0) el robot pivotea. Es el
                    // unico camino que le queda al pivote con la config de hoy.
                    if (absSteer >= LINE_PIVOT_STEER) rot = 1.0;
                    if (rot > 1.0) rot = 1.0;

                    // ----------------------------------------------------------
                    //  VELOCIDAD: RAMPA CUADRATICA, no lineal, y a proposito.
                    //
                    //  La velocidad hace DOS cosas distintas segun donde este la
                    //  curva:
                    //    rot intermedio  el robot AVANZA mientras gira, asi que ir
                    //                    rapido lo pasa de largo
                    //    rot = 1         no avanza nada -las ruedas van iguales y
                    //                    opuestas-, y la velocidad solo controla
                    //                    que tan rapido GIRA
                    //  Medido el 22-ago comparando dos corridas por zona:
                    //    rot 0,40-0,60  a 29 rpm rinde 0,744/0,824  vs 0,716/0,757 a 37
                    //    rot 0,95-1,00  a 20 rpm da 23,7 grados/s   vs 45,3 a 35 rpm
                    //  O sea: en la zona intermedia la corrida MAS LENTA rindio
                    //  mejor, y en el pivote el giro se duplica con mas velocidad.
                    //
                    //  Con k al cuadrado la velocidad se queda baja en el medio y
                    //  sube recien cerca del fondo de escala: frena donde avanza,
                    //  empuja donde gira. Con la rampa lineal, a mitad de curva
                    //  daba 45 en vez de 42.
                    // ----------------------------------------------------------
                    double k = constrain(absSteer / LINE_PIVOT_STEER, 0.0, 1.0);
                    // RAMPA CUADRATICA, no lineal, y a proposito. La velocidad
                    // hace DOS cosas distintas segun donde este la curva:
                    //
                    //   rot intermedio  el robot AVANZA mientras gira, asi que
                    //                   ir rapido lo pasa de largo
                    //   rot = 1         no avanza nada -las ruedas van iguales
                    //                   y opuestas-, la velocidad solo controla
                    //                   que tan rapido GIRA
                    //
                    // Medido el 2026-08-22 comparando dos corridas de pista a
                    // distinta velocidad, por zona (rendimiento de giro):
                    //   rot 0,40-0,60   a 29 rpm: 0,744/0,824   a 37: 0,716/0,757
                    //   rot 0,95-1,00   a 20 rpm: 23,7 d/s      a 35: 45,3 d/s
                    // O sea: en la zona intermedia la corrida MAS LENTA rindio
                    // mejor, y en el pivote el giro se duplica con mas velocidad.
                    //
                    // Con k al cuadrado la velocidad se queda baja en el medio y
                    // sube recien cerca del pivote: 40 en recta, 42 a mitad de
                    // curva, 50 en el pivote. Frena donde avanza, empuja donde
                    // gira. Con la rampa lineal, a mitad de curva daba 45.
                    int vel = (int)(velocidadAjustada + k * k * (LINE_PIVOT_SPEED - velocidadAjustada));

                    // rama solo para la TELEMETRIA (que se lee igual que antes), no para decidir
                    g_line_branch = (absSteer > LINE_PIVOT_STEER) ? 3
                                  : (absSteer > LINE_HARD_CURVE_STEER) ? 2
                                  : (absSteer > LINE_CURVE_STEER) ? 1 : 0;

                    // SIGNO DEL GIRO: sale de la trama FRESCA, sin memoria.
                    // (Hubo un "dwell" que retrasaba las inversiones de signo;
                    //  se probo el 26-ago-2026 con 250 ms y no movio nada -ratio
                    //  giro_abs/giro_neto 5,6x contra 2,8-5,8x de la base- porque
                    //  solo actuaba dentro del pivote, y el robot esta en pivote
                    //  el 15-20 % del tiempo. Se saco el 2026-09-06.)
                    // OJO: con steerCmd == 0.0 exacto (byte 90 de la Pi, que es
                    // "centrado" o "no veo linea") signoCmd da -1, porque la
                    // comparacion es > 0. Con rot = 0 eso no mueve las ruedas.
                    const int signoCmd = (steerCmd > 0) ? 1 : -1;
                    // CURVA CERRADA: se frena la delantera interna y se sube la
                    // velocidad. Fuera del umbral, todo sigue como hoy.
                    if (absSteer >= LINE_FRENO_STEER)
                    {
                        g_line_branch = 7;
                        double rotF = rot * LINE_FRENO_ROT_MULT;
                        if (rotF > 1.0) rotF = 1.0;
                        robot.steerFrenoDelantero(LINE_FRENO_VEL, FORWARD,
                                                  signoCmd > 0 ? rotF : -rotF,
                                                  LINE_FRENO_FACTOR);
                    }
                    else
                        robot.steer(vel * LINE_RECTA_FACTOR, FORWARD,
                                    signoCmd > 0 ? rot : -rot);

                    // PENDIENTE: si el pitch esta inclinado, piso las traseras a full para
                    // que agarren y no resbale (fr/br usan dir invertida, igual que en steer).
                    if (pitch > PITCH_RAMPA)
                    {
                        bl.setSpeed(FORWARD,  POTENCIA_TRASERAS);   // trasera izquierda
                        br.setSpeed(!FORWARD, POTENCIA_TRASERAS);   // trasera derecha
                    }

                    break;
                    }

                case 12:
                    {
                        serialEvent5();

                        float diferencia = calcularDiferenciaAngulo(leer_yaw(), centrar);
                        runAngle(30, FORWARD, diferencia);
                        runTime(30, BACKWARD, 0, 300);
                        runTime(0, FORWARD, 0, 2000);
                        unsigned long waitStart = millis();
                    while(digitalRead(32) == 0){
                        robot.steer(0, FORWARD, 0);
                       
                        serialEvent5();

                        // TOPE DURO: si la Pi no manda 15/16/17 en 5 s, se sale.
                        // Sin esto el robot se queda quieto para siempre.
                        if ((millis() - waitStart) >= 5000) break;

                        if (green_state == 15)
                        {
                            runTime(30, FORWARD, 0, 500);
                            runAngle(30, FORWARD, 80);
                            break;
                        }

                        if (green_state == 16)
                        {
                            runTime(30, FORWARD, 0, 200);
                            runAngle(30, FORWARD, -80);
                            break;
                        }

                        if (green_state == 17)
                        {
                            runDistance(30, FORWARD, 15);
                            break;
                        }

                    }
                    }
                    break;   // NO cae al case 14: la maniobra del 12 termino aca

                case 14: // turn 180 deg for double green squares
                    serialEvent5();
                    telemGreenResultado(3, green_state);   // TELEMETRIA: giro o matado por re-chequeo
                    if (green_state == 3)
                    {
                        runAngle(30, FORWARD, 180);
                        runTime(30, FORWARD, 0, 500);
                    }
                    action = 7;
                    break;

                }

            }
        }
        while (rutina == "rescate" && digitalRead(32) == 0)
        {
            enviarTelemetria();   // TELEMETRIA (rescate)
            digitalWrite(RELAY, HIGH);
           digitalWrite(LED_BUILTIN, LOW);
            serialEvent5();
            robot.steer(speed, FORWARD, steer);
            digitalWrite(0,LOW);

            if (green_state == 6) // Recoleccion Pelota negra
            {
                digitalWrite(RELAY, HIGH);
                runTime(0,FORWARD,0,1000);
                claw.lower();
                nonBlockingDelay(1000);
                claw.depositCenter();
                nonBlockingDelay(1400);
                claw.sortRight();
                nonBlockingDelay(1000);
                runDistance(30,FORWARD,9);
                runTime(0,FORWARD,0,1000);
                claw.close();
                nonBlockingDelay(1000);
                digitalWrite(BUZZER, HIGH);
                delay(100);
                digitalWrite(BUZZER, LOW);
                runTime(0,FORWARD,0,1000);
                claw.lift();
                nonBlockingDelay(1000);
                claw.open();
                nonBlockingDelay(1000);
                claw.sortCenter();
                nonBlockingDelay(1000);
                claw.sortRight();
                nonBlockingDelay(1000);
                runTime(70,FORWARD,0,200);
                runTime(70,BACKWARD,0,200);
                 ball_counter++;
            }
            if (green_state == 7)            { // Recoleccion Pelota platea
                digitalWrite(RELAY, HIGH);
                runTime(0,FORWARD,0,1000);
                claw.lower();
                claw.sortLeft();
                nonBlockingDelay(1400);
                claw.depositCenter();
                nonBlockingDelay(1000);
                runDistance(20,FORWARD,8);
                runTime(0,FORWARD,0,1000);
                claw.close();
                nonBlockingDelay(1000);
                digitalWrite(BUZZER, HIGH);
                delay(100);
                digitalWrite(BUZZER, LOW);
                runTime(0,FORWARD,0,1000);
                claw.lift();
                nonBlockingDelay(1000);
                claw.open();
                nonBlockingDelay(1000);
                claw.sortCenter();
                nonBlockingDelay(1000);
                claw.sortLeft();
                nonBlockingDelay(1000);
                runTime(70,FORWARD,0,200);
                runTime(70,BACKWARD,0,200);
                ball_counter++;
            }
            if (ball_counter>=  3 && depositando==false)
            {
                claw.sortCenter();
                digitalWrite(RELAY, HIGH);
                Serial5.write(248);
                depositando=true;
                serialEvent5();
                robot.steer(speed, FORWARD, steer);  
                veces_deposit=0;
            }
            // Triangulo de deposito que ve la camara: 8 = rojo, 9 = verde.
            const int gs_dep = green_state;
            if(gs_dep == 9)//verde
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    if (!retrocederHastaFinales(20))
                        break;

                    claw.depositRight();
                    nonBlockingDelay(2000);
                    runTime(80,FORWARD,0,100);
                    
                    runTime(80,BACKWARD,0,250);
                    runTime(80,FORWARD,0,100);
                    
                    runTime(80,BACKWARD,0,250);
                    runTime(0,FORWARD,0,500);
                    claw.depositCenter();
                    runTime(0,FORWARD,0,500);
                    runDistance(30,FORWARD,4+60);
                    veces_deposit++;
                }
            if (gs_dep == 8)//rojo
                {
                    digitalWrite(RELAY, HIGH);
                    runAngle(20,FORWARD,180);
                    if (!retrocederHastaFinales(20))
                        break;

                    claw.depositLeft();
                    nonBlockingDelay(2000);
                    runTime(80,FORWARD,0,100);
                    runTime(80,BACKWARD,0,250);
                    runTime(0,FORWARD,0,500);
                    runTime(80,FORWARD,0,100);
                    
                    runTime(80,BACKWARD,0,250);
                    claw.depositCenter();
                    runAngle(20,FORWARD,45);
                    runTime(30,FORWARD,0,500);
                    runAngle(20,FORWARD,-45);

                    veces_deposit++;
                    green_state=0;

                }
            if (veces_deposit >= 2)
            {
                green_state = 0;
                if (!evacuacion_iniciada) {
                    Serial5.write(247);
                    evacuacion_iniciada = true;
                    evacuacion_straight = false;
                }
                rutina = "evacuacion";
                break;
            } // cierra if(veces_deposit >= 2)

        } // end while (rutina == "rescate" && digitalRead(32) == 0)
            /*if(green_state == 10)
                {
                    estado == "salida"
                    runTime(0,BACKWARD,0,3000);

                }*/
           
        // end while (rutina == "rescate" && digitalRead(32) == 0)
        while (rutina == "evacuacion" && digitalRead(32) == 0)
        {
            enviarTelemetria();   // TELEMETRIA (evacuacion)
            if (!evacuacion_straight)
            {
                green_state = 0;

                // Secuencia pre-ruedas fijas: al terminar depositos se separa de la zona
                // y toma el angulo de entrada que ya funcionaba fisicamente.
                runDistance(30, FORWARD, 25);
                runAngle(30, FORWARD, -135);
                leer_ultrasonidos();

                if (front_distance != 0 && front_distance < 120) {
                    runAngle(30, FORWARD, 180);

                    // Mismo filtro de finales usado en deposito: ambos deben
                    // permanecer HIGH durante 50 ms continuos.
                    if (!retrocederHastaFinales(20))
                        break;

                    runAngle(30, FORWARD, -90);

                }
                else
                {
                    while (rutina == "evacuacion" && digitalRead(32) == 0) {
                        robot.steer(30, FORWARD, 0);
                        memoriaParedEvacuacionPeriodica();   // para accionNegro()
                        procesarColorEvacuacion();
                        serialEvent5();
                    }
                }
                evacuacion_straight = true;
            }
            leer_ultrasonidos();
            memoriaParedEvacuacion();
                while (rutina == "evacuacion" && digitalRead(32) == 0) {
                    robot.steer(30, FORWARD, 0);
                    procesarColorEvacuacion();
                    if (rutina != "evacuacion") break;
                    serialEvent5();
                    leer_ultrasonidos();
                    memoriaParedEvacuacion();   // memoria de lado para accionNegro()

                    // PRIORIDAD 3 (orden pre-ruedas fijas): lado izquierdo abierto -> girar a buscar pared.
                    if (left_distance > 40 || left_distance == 0)
                    {
                        DBG_PRINT("[EVAC] P3 BUSCAR left="); DBG_PRINT(left_distance);
                        DBG_PRINT(" front="); DBG_PRINTLN(front_distance);
                        runDistance(30, FORWARD, 8);
                        runAngle(30, FORWARD, -90);
                        while (rutina == "evacuacion" && digitalRead(32) == 0)
                        {
                            robot.steer(30, FORWARD, 0);
                            procesarColorEvacuacion();
                            serialEvent5();
                            leer_ultrasonidos();
                            memoriaParedEvacuacion();
                            if (debeEsquivar())   // corto la busqueda al toparme con esquina o pared
                                break;
                        }
                    }

                    // PRIORIDAD 1: esquina de deposito = camara ve triangulo (green_state
                    // 8/9) Y el ultrasonido confirma cercania (<=31). Maniobra completa.
                    if ((green_state == 8 || green_state == 9) && front_distance != 0 && front_distance <= 34)
                    {
                        DBG_PRINT("[EVAC] P1 ESQUINA gs="); DBG_PRINT(green_state);
                        DBG_PRINT(" front="); DBG_PRINTLN(front_distance);
                        maniobraEsquive();
                        green_state = 0;   // evita re-disparo inmediato con valor stale de camara
                        break;
                    }

                    // PRIORIDAD 2 (pre-ruedas fijas): pared frontal lisa a <=18 cm.
                    if (front_distance != 0 && front_distance <= 18)
                    {
                        DBG_PRINT("[EVAC] P2 PARED front="); DBG_PRINTLN(front_distance);
                        runAngle(30, FORWARD, 90);
                        continue;
                    }


                }
            // cierra if(left_distance > right_distance)

        }
    } // end else (principal del loop)
} // end loop()
