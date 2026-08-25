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
} // namespace priority_fix_flags
