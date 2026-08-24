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
} // namespace priority_fix_flags
