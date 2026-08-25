#pragma once

namespace priority_fix_flags
{
inline constexpr bool kEnableAllPriorityFixes = false;

inline constexpr bool kFixIssue57RescueWallTurnDirection = true;
inline constexpr bool kFixIssue58Case12ControlFlow = true;
inline constexpr bool kFixIssue59ServiceStateMachinesDuringMotion = true;
inline constexpr bool kFixIssue60RunDistanceTimeout = true;
inline constexpr bool kFixIssue61ColorSensorTimeout = true;
inline constexpr bool kFixIssue62VisibleSensorInitFailures = true;
inline constexpr bool kFixIssue63KeepSerialDuringMotions = false;
inline constexpr bool kFixIssue67InitializeMotorPulseCount = true;
inline constexpr bool kFixIssue74ValidateSerialPayloads = true;
inline constexpr bool kFixIssue75SerialTelemetry = true;
inline constexpr bool kFixIssue76DocumentSerialProtocol = true;
inline constexpr bool kFixIssue112RunAngleTimeout = true;

// Sensores bloqueantes dentro del lazo de seguimiento de linea.
//
// El `while (rutina == "linea")` llamaba a leer_tof() y leer_ultrasonidos() en
// CADA vuelta. Las dos son bloqueantes:
//
//   leer_tof()           VL53L0X en modo continuo hace ESPERA ACTIVA hasta
//                        tener muestra nueva (~33 ms de presupuesto por
//                        defecto: nunca se llama setMeasurementTimingBudget).
//   leer_ultrasonidos()  tres ping_cm() de NewPing, hasta ~8,7 ms cada uno con
//                        MAX_DISTANCE=150.
//
// Medido sobre 7673 periodos de lazo en 6 corridas: p50 = 30 ms, con un
// segundo modo en 65 ms. Una distribucion asi de angosta con un modo en 2x no
// es "trabajo variable": es un enganche al reloj del sensor.
//
// Consecuencia: la Pi manda a 66-86 Hz y el comando cambia a 8,6-20,6 Hz. Tres
// de cada cuatro tramas de vision se descartan, y la correlacion rot->gz tiene
// su maximo en lag 65-70 ms = dos periodos de lazo.
//
// Y los ToF no hacian falta ahi: `distance_left_tof` y `distance_right_tof`
// solo los consumen el seguimiento de pared -que llama leer_tof() por su
// cuenta- y la telemetria. En linea se pagaban 30 ms por vuelta para un valor
// que no leia nadie.
//
// De los tres ultrasonidos, en linea solo se usa `front_distance` (obstaculo a
// menos de 12 cm). Cada rama que usa left/right_distance vuelve a llamar a
// leer_ultrasonidos() por su cuenta antes de usarlos.
//
// PENDIENTE DE BANCO. Falsador escrito antes de probar: el p50 del periodo de
// lazo tiene que bajar de 30 ms a menos de 10, y el lag de rot->gz de 65-70 ms
// a 20 o menos. Si el lag NO se mueve, esta hipotesis esta muerta y el retardo
// esta en el pipeline de la camara.
inline constexpr bool kFixLazoLineaSensoresBloqueantes = true;

// Usar el `speed` que manda la Raspberry en el seguimiento de linea.
//
// El protocolo es [255, speed, 254, angle, 253, green, 252, silver] y el byte de
// velocidad se recibe y se valida en serialEvent5 (main.cpp:1694). Pero el case
// de linea NUNCA LO USA: arranca de ajustarVelocidadPorPendiente(45), un 45
// hardcodeado. El canal existe y esta ignorado.
//
// POR QUE IMPORTA. La Teensy ya frena en curva:
//     k   = constrain(absSteer / LINE_PIVOT_STEER, 0, 1)
//     vel = velocidadAjustada + k*k*(LINE_PIVOT_SPEED - velocidadAjustada)
// 40 en recta, 42 a mitad de curva, 50 en pivote. Eso funciona, y el comentario
// de esa rampa dice que se midio en pista.
//
// El problema es que FRENA TARDE: absSteer sube cuando la curva ya esta encima,
// porque el steer sale de un target a lookahead fijo.
//
// APAGADO EL 25-ago. LA JUSTIFICACION QUE TENIA SE CAYO.
//
// Este comentario decia: "del lado Raspberry ya se midio que la curvatura del
// camino visible avisa la curva con ~1 segundo de anticipacion en el 84 % de
// los casos". Ese numero NO VALE. El test que lo produjo (`curva_cerrada.py`)
// preguntaba si habia ALGUNA kappa sobre el umbral en los 40 frames previos y
// se quedaba con la MAS ANTIGUA, sin cortar el lazo. Con el umbral en el p75 el
// 25 % de los frames lo supera, asi que "al menos uno en 40" sale casi siempre
// por azar, y el lead grande tambien.
//
// Rehecho con precision, tasa base y placebo (`curva_cerrada2.py`, 13.900
// frames): el lift maximo es 1,47x contra la base y 1,26x contra el placebo,
// por debajo del 1,5 preregistrado. Con el KAPPA_REF de produccion (139,5) da
// 1,38x a 10 frames y 1,09x a 40. La anticipacion NO esta demostrada.
// Lo encontro ChatGPT en la auditoria del 25-ago.
//
// Y hay una segunda razon para apagarlo, de diseno experimental: con la
// anticipacion tambien apagada del lado Raspberry (VEL_ANTICIPADA), este flag
// haria que la Teensy use el 40 que manda Main.py en vez del 45 historico. Eso
// es un cambio de velocidad que se colaria adentro de una prueba de PERCEPCION.
// Un cambio por fase.
//
// SEGURIDAD, cuando se vuelva a encender. Si la Raspberry manda 0 o un valor
// absurdo NO se obedece: se usa el 45 de siempre. Un byte perdido o una trama
// corrupta no puede frenar el robot. El rango se eligio alrededor del 45.
inline constexpr bool kFixVelocidadDesdeVision = false;
inline constexpr int  kVelVisionMin = 20;    // por debajo se ignora
inline constexpr int  kVelVisionMax = 60;    // por encima se ignora

// Watchdog de COMUNICACION en el seguimiento de linea.
//
// Hoy no hay ninguno. `grep 'WDT|watchdog' src/main.cpp` da cero. `g_last_rx_ms`
// se calcula y se usa SOLO en telemetria: ninguna rama apaga los motores por
// comando rancio.
//
// Medido en una corrida grabada: 49 % de las muestras con mas de 1 s sin trama
// nueva, una ventana continua de 17,1 s sobre el mismo comando, y un maximo de
// 27,0 s. Si la Raspberry se cuelga en pista, la Teensy sigue ejecutando la
// ultima orden indefinidamente y el robot se va dando vueltas.
//
// PRECAUCION QUE HACE FALTA: durante runAngle/runTime la Teensy NO lee el serie
// (kFixIssue63KeepSerialDuringMotions esta en false), asi que al volver de un
// esquive o de un verde el `rxage` puede venir legitimamente viejo -medido: p50
// 1849 ms, max 4677 ms durante maniobra-. Por eso no alcanza con el timeout:
// se exige que la condicion se sostenga varias vueltas seguidas del lazo.
inline constexpr bool kFixWatchdogComunicacion = true;
inline constexpr unsigned long kWatchdogMs = 400;   // sin trama valida
inline constexpr int kWatchdogVueltas = 10;         // OBSOLETO: ver kWatchdogConfirmaMs
// Confirmacion por TIEMPO, no por vueltas del lazo.
//
// Estaba en 10 vueltas, y eso se rompia justo con el otro fix de este archivo:
// sacar el ToF bloqueante baja el periodo del lazo de ~30 ms a menos de 10, asi
// que "10 vueltas" pasaba de ~300 ms a ~100 sin que nadie lo decidiera. Un
// criterio de seguridad no puede cambiar de significado porque otra bandera se
// encienda. (Auditoria de ChatGPT, 25-ago.)
inline constexpr unsigned long kWatchdogConfirmaMs = 300;

// ===========================================================================
//  PERIODO DEL LAZO, SEGUNDA VUELTA.  25-ago-2026
//
//  kFixLazoLineaSensoresBloqueantes saco el ToF (33 ms) del lazo de linea. Pero
//  dejo `leer_ultrasonido_frontal()`, y ESE es ahora el que domina.
//
//  El numero, de la propia libreria vendorizada en lib/NewPing/NewPing.h:
//      US_ROUNDTRIP_CM  = 57 us/cm      (NewPing.h:163)
//      MAX_SENSOR_DELAY = 5800 us       (NewPing.h:172)
//      _maxEchoTime = MAX_DISTANCE * 57 + 28
//  Con MAX_DISTANCE = 150 (main.cpp:1230) eso da 8578 us = 8,58 ms, MAS hasta
//  5800 us si el sensor tarda en arrancar el ping: 14,4 ms de peor caso.
//
//  Y ES EL CASO NORMAL, no el raro: `ping_cm()` bloquea hasta el TIMEOUT cuando
//  NO hay eco, y en seguimiento de linea casi nunca hay una pared a menos de
//  150 cm adelante. O sea que en pista abierta se pagan 8,6 ms por vuelta para
//  que la unica pregunta del lazo -`front_distance < 12`- de siempre "no hay
//  nada". El sensor NO es lento: el timeout esta puesto 5 veces mas lejos de lo
//  que el lazo pregunta.
// ===========================================================================

// (1) Pedirle al ping frontal solo la distancia que el lazo de linea usa.
//
// `NewPing::ping_cm(unsigned int max_cm_distance = 0)` acepta la distancia por
// llamada (NewPing.h:223), asi que no hay que tocar el objeto ni el resto de
// las rutinas. El lazo de linea pregunta `front_distance < 12`; con 30 cm de
// techo sobra el doble y el timeout cae a 30*57+28 = 1738 us.
//
//      8578 us  ->  1738 us     -6,84 ms por vuelta, 4,9x
//
// OJO: `set_max_distance()` PERSISTE en el objeto, asi que las otras rutinas
// -evacuacion usa `front_distance < 120`- tienen que pasar su propio valor.
// Por eso el fix pasa el numero EXPLICITO en los dos lados.
inline constexpr bool kFixPingFrontalCorto = true;
inline constexpr unsigned int kPingLineaCm = 30;    // el lazo pregunta < 12
inline constexpr unsigned int kPingLargoCm = 150;   // el resto, como siempre

// (2) No pingear en CADA vuelta.
//
// A 30 cm/s el robot recorre 3 mm en 10 ms. Un obstaculo no aparece entre dos
// vueltas del lazo, y el umbral es de 12 cm. Pingear cada 40 ms deja 1,2 cm de
// avance entre lecturas, que es un decimo del umbral.
//
// Con (1) y (2): 1738 us cada 40 ms en vez de 8578 us cada vuelta. Si el lazo
// corre a 2 ms, el costo MEDIO del ultrasonido pasa de 8578 a ~87 us.
inline constexpr bool kFixPingFrontalPeriodico = true;
inline constexpr unsigned long kPingFrontalPeriodoMs = 40;

// (3) I2C a 400 kHz.  APAGADO POR DEFECTO, Y HAY QUE MEDIRLO ANTES.
//
// No hay UN SOLO `Wire.setClock()` en las 4.146 lineas de main.cpp, asi que el
// bus corre al default de `Wire.begin()`, que en Teensy 4.x es 100 kHz
// (documentacion de PJRC). Todo lo que cuelga del bus paga eso:
//
//      enviarTelemetria()   dos lecturas del BNO055 (getEvent + getVector),
//                           ~12 bytes utiles + overhead -> ~1,8 ms cada 100 ms
//      get_color_fast()     colorDataReady() -> ~0,36 ms, hasta cada 2 ms
//      leer_tof()           dos lecturas de 2 bytes (fuera del lazo de linea)
//
// A 400 kHz todo eso se divide por 4. `Wire.setClock()` soporta hasta 1 MHz en
// Teensy 4.1.
//
// POR QUE VA APAGADO: los pull-up internos del Teensy 4.1 son debiles y el bus
// tiene TRES esclavos (BNO055, APDS9960, dos VL53L0X). Si los modulos no traen
// pull-up suficiente, a 400 kHz los flancos no llegan y el bus se cuelga -que
// es peor que ser lento-. Es el unico fix de este bloque que puede ROMPER algo,
// y no se enciende sin banco: 10 minutos leyendo los tres sensores seguidos y
// mirando que ninguno devuelva basura ni se cuelgue.
inline constexpr bool kFixI2cRapido = false;
inline constexpr unsigned long kI2cHz = 400000UL;

// (4) Presupuesto de medicion de los ToF.
//
// `readRangeContinuousMillimeters()` es espera activa hasta que hay muestra
// nueva, y el presupuesto por defecto del VL53L0X es 33 ms (documentacion de
// Pololu); el minimo admitido es 20 ms. Nunca se llamo
// `setMeasurementTimingBudget()`.
//
// En el lazo de linea ya no se leen -ese es el fix anterior-, asi que esto NO
// toca el periodo del seguimiento de linea. Importa en seguimiento de pared,
// que si los relee: ahi cada lectura pasa de 33 a 20 ms.
inline constexpr bool kFixTofPresupuesto = true;
inline constexpr uint32_t kTofBudgetUs = 20000;

// (5) EL PIVOTE NO AVANZA.  APAGADO POR DEFECTO. Necesita banco.
//
// `steer()` reparte  v_ext = vel  y  v_int = vel*(1 - 2*rot)
// (drivebase.cpp:212-215), asi que
//
//      v_centro = vel * (1 - rot)
//
// y en `rot = 1` el centro del robot NO AVANZA: las dos ruedas van iguales y
// opuestas. Eso no es un efecto secundario, es la definicion del pivote.
//
// El problema es CUANTO tiempo se pasa ahi. `main.cpp:3749-3753` pone rot = 1
// en dos casos, y el primero es pegajoso:
//
//      if (s_en_pivote)                  rot = 1.0;   <-- se queda enganchado
//      if (absSteer >= LINE_PIVOT_STEER) rot = 1.0;   <-- 0,92, puntual
//
// `s_en_pivote` no se suelta hasta que `absSteer <= LINE_PIVOTE_SALE` (0,15)
// se sostenga LINE_PIVOTE_CONFIRMA_MS. O sea: se entra por un pico y se sale
// recien cuando el robot esta casi alineado.
//
// MEDIDO el 2026-08-26 sobre los CSV del 22-ago (`radio_minimo.py`), en las
// tres corridas que pasan el control de signo, con el lag de 14 muestras:
//
//      radio trazado      n        v p50       omega p50     rot p50
//      R < 2 cm          4087    0,81 cm/s     58,3 d/s       1,00
//      2 - 4,9 cm        1599    2,70 cm/s     50,0 d/s       1,00
//      4,9 - 8 cm        1233    4,59 cm/s     41,7 d/s       0,79
//      8 - 15 cm          893    5,94 cm/s     35,2 d/s       0,65
//      15 - 30 cm         151   10,36 cm/s     33,7 d/s       0,43
//
// El 51 % del tiempo que el robot GIRA lo hace con radio < 2 cm avanzando
// 0,81 cm/s. La curva del reglamento que hay que trazar es de 4,9 cm.
//
// QUE HACE EL FIX: pone un TECHO a `rot` mientras se sigue la linea, de modo
// que el robot conserve avance. El techo por defecto es el que traza
// exactamente la curva mas cerrada del reglamento:
//
//      rot = b_eff / (2*R + b_eff) = 20,9 / (2*4,9 + 20,9) = 0,681
//
// con eso v_centro = 0,319*vel en vez de 0.
//
// POR QUE VA APAGADO, y hay que decirlo fuerte: esto le SACA autoridad de giro
// instantanea al robot, y la regla 3 del traspaso dice que nunca se limite la
// magnitud del steer. No es lo mismo -aquel steer es el angulo que manda la
// vision, esto es el reparto entre ruedas- pero esta cerca, y el argumento a
// favor es de trayectoria, no de magnitud: para SEGUIR una curva de 4,9 cm hay
// que TRAZAR 4,9 cm, y girando en el lugar no se traza nada.
//
// COMO SE VALIDA EN BANCO (falsador, antes de encenderlo):
//   1. el robot tiene que SEGUIR pasando las curvas que hoy pasa. Si pierde
//      una que hoy toma, se apaga y listo.
//   2. la fraccion de muestras con radio < 2 cm tiene que BAJAR de 51 %.
//   3. la velocidad mediana mientras gira tiene que SUBIR de 0,81 cm/s.
//   4. si las intersecciones o los giros de 90 grados con verde empeoran,
//      es que ese caso SI necesitaba girar en el lugar -> se apaga.
inline constexpr bool kFixPivoteAvanza = false;
// 0,681 traza R = 4,9 cm con b_eff = 20,9 cm. Subirlo a 1,0 es el de hoy.
inline constexpr double kPivoteRotMax = 0.681;

// (6) EL WATCHDOG SELLA TRAMAS VIEJAS COMO FRESCAS. APAGADO POR DEFECTO.
//
// El razonamiento completo, con los numeros del periodo del lazo que fijan el
// umbral, esta en el comentario de serialEvent5() en main.cpp.
//
// Resumen: durante una maniobra bloqueante nadie lee el serial; al volver, la
// primera trama parseada hace `g_last_rx_ms = millis()` y el watchdog cree que
// el comando es fresco cuando puede tener segundos.
//
// FALSADOR PARA EL BANCO, antes de encenderlo:
//   1. `g_serial_drenados` tiene que ser > 0 en una corrida con maniobras. Si
//      es 0, el fix no actuo y cualquier diferencia que se vea es otra cosa.
//   2. el robot NO tiene que frenar en tramos donde hoy anda bien. Si el
//      watchdog empieza a disparar en linea recta, el umbral quedo corto.
//   3. desconectar el cable de la Pi A PROPOSITO durante una maniobra: con el
//      fix el robot tiene que frenar; sin el fix sigue con la orden vieja.
inline constexpr bool kFixWatchdogTramaFresca = false;
// 250 ms: p90 del lazo es 95 ms y p99 es 445. Ver la tabla en main.cpp.
inline constexpr unsigned long kSerialCiegoMs = 250;

// (7) EL MAPEO steer -> rot PIDE RADIOS QUE NO EXISTEN. APAGADO POR DEFECTO.
//
// Derivado de la DISTRIBUCION REAL de lo que manda la Raspberry, no de teoria
// -Benjamin, 26-ago: "guiate de lo que recibe y en base a eso hay q hacerlo"-.
//
// n = 50.962 muestras con comando fresco y speed > 0, sobre las SEIS corridas
// del 22-ago que tienen tramas de la Pi. Las otras cuatro tienen rxf max = 0
// -nunca llego una trama: son barridos de banco con la Pi callada-, asi que
// para esta pregunta no aportan; para medir b_eff si aportaron (control C4).
//
//   decil  |steer|   rot HOY   R que pide HOY
//     20    0,144     0,441      13,25 cm
//     30    0,233     0,561       8,18 cm
//     40    0,322     0,659       5,40 cm
//     50    0,411     0,745       3,58 cm     <- ya mas cerrado que 4,9
//     70    0,555     0,866       1,62 cm
//     90    0,822     1,000     EN EL LUGAR
//
// EL 57,9 % DEL TIEMPO EL FIRMWARE PIDE UN RADIO MAS CERRADO QUE 4,9 cm, que
// es la curva mas cerrada que EXISTE en el reglamento (RCJ 2.2.2, radio
// interno >= 40 mm). Los radios que una pista Rescue Line realmente tiene van
// de 4,9 cm a ~15 cm (cuarto de circulo en un tile de 30) mas las rectas, y a
// ese rango le corresponden solo los deciles 20 a 40 del steer que llega.
//
// QUE HACE EL FIX:   rot = kMapeoRotMax * sqrt(|steer|)
// saca la ganancia LINE_STEER_GAIN y escala para que el steer maximo pida
// EXACTAMENTE la curva mas cerrada del reglamento:
//
//   |steer|   R nuevo    avanza        contra HOY
//     0,144   29,99 cm     74 %        13,25 cm / 56 %
//     0,411   13,49 cm     56 %         3,58 cm / 26 %
//     0,822    6,48 cm     38 %       EN EL LUGAR / 0 %
//     1,000    4,90 cm     32 %       EN EL LUGAR / 0 %
//
//   avance promedio             0,320 -> 0,595   (+86 %)
//   tiempo en rot=1              19,0 % -> 0 %
//   tiempo pidiendo R < 4,9 cm   62,1 % -> 0,3 %
//
// EL RIESGO, y es grande: ES MUCHO MENOS GIRO QUE HOY. En el decil 50 pasa de
// pedir 3,58 cm a pedir 13,49. Si el robot NECESITABA ese giro, con esto CORTA
// las curvas. El supuesto de abajo -que el cuantil k del steer tiene que
// mapear al cuantil k del radio de la pista- es razonable pero NO ESTA
// VERIFICADO: `steer` es un error angular, no un radio deseado, y elegir la
// curva error->radio es elegir una ganancia de control.
//
// Por eso hay DOS flags y no uno:
//   kFixPivoteAvanza  = techo sobre el rot de hoy. CAMBIO MINIMO, conserva la
//                       forma actual y solo corta el exceso. avance 0,434.
//   kFixMapeoRot      = este. CAMBIO GRANDE, rehace la curva entera.
// Se prueban POR SEPARADO. Si los dos estan encendidos gana este, y el techo
// queda redundante (kMapeoRotMax ya es el mismo 0,681).
//
// FALSADOR DE BANCO, antes de encenderlo:
//   1. si el robot CORTA una curva que hoy toma, se apaga. Es el riesgo #1.
//   2. la fraccion de muestras con rot=1 tiene que dar 0 (es aritmetica: el
//      techo es 0,681). Si no da 0, el flag no esta actuando.
//   3. la velocidad mediana mientras gira tiene que SUBIR de 0,81 cm/s.
//   4. las intersecciones y los giros de 90 con verde no pasan por este
//      camino (son otros case), pero verificar igual que no cambiaron.
inline constexpr bool kFixMapeoRot = false;
// 0,681 = b_eff/(2R + b_eff) con R = 4,9 cm y b_eff = 20,9 cm.
inline constexpr double kMapeoRotMax = 0.681;
} // namespace priority_fix_flags
