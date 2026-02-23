# Análisis Exhaustivo de Código: Firmware Teensy 4.1

> **Autor:** Ai Gemini - **Solicitado por:** Gustavo Viollaz
> **Fecha:** 22 de febrero de 2026

Este documento presenta una auditoría técnica profunda (línea por línea) del código fuente en C++ que controla la Teensy 4.1 del robot de RoboCup Junior Rescue Line (IITA Salta). Se analizan funcionalidades, convenciones de estilo, riesgos críticos y oportunidades de refactorización.

---

## 1. Análisis de Componentes y Funcionalidad

El código de la Teensy está compuesto por un archivo principal (`main.cpp`) y dos librerías personalizadas (`DriveBase` y `Claw`).

### A. Librería `DriveBase` y `Moto` (Tracción)
- **Función:** Controla los 4 motores DC en configuración *skid-steering*.
- **PID:** Cada motor (`Moto`) posee una instancia de la librería PID clásica de Arduino. La velocidad se calcula midiendo el tiempo transcurrido (`micros()`) entre 4 pulsos del encoder (promedio móvil de 4 muestras en `_rpmlist`).
- **Problema Estructural:** Dentro de la Rutina de Servicio de Interrupción (ISR) `Moto::updatePulse()`, se evalúa la dirección contando hacia adelante o hacia atrás dependiendo del motor.

### B. Librería `Claw` (Pinza)
- **Función:** Modela la cinemática de la pinza usando 5 servomotores y expone métodos de alto nivel (`open()`, `pickupRight()`, etc.).
- **Problema Estructural:** Contiene llamadas fuertemente acopladas a la función bloqueante `delay(500)` en su interior, lo que paraliza completamente al microcontrolador.

### C. Bucle Principal (`main.cpp`)
- **Gestión de Sensores:** Mantiene polling sobre la IMU BNO055 (orientación), VL53L0X (distancia láser I2C), ultrasonidos (HC-SR04) y el sensor de color APDS9960.
- **Odometría y Tareas:** Ejecuta rutinas de movimiento basadas en tiempo (`runTime`), en distancia medida por encoders (`runDistance`) y giros angulares estrictos midiendo la IMU de forma bloqueante (`runAngle`).
- **Estados de Competencia:** El flujo del `loop()` se bifurca en dos grandes bloques `while`: uno para `rutina == "linea"` y otro para `rutina == "rescate"`.

---

## 2. Auditoría de Bugs Críticos (Riesgos de Fallo)

La revisión del código reveló problemas severos en el manejo de interrupciones, la memoria y la concurrencia que podrían causar cuelgues durante la competencia.

### 1. Variables Volátiles Omitidas (CRÍTICO)
- **Hallazgo:** La variable `pulseCount` en la clase `Moto` se modifica dentro de las ISRs (`ISR1`, `ISR2`, etc.) y se lee en el bucle principal (ej. dentro de `runDistance()`). Sin embargo, está declarada simplemente como `long pulseCount;`.
- **Riesgo:** El compilador de GCC, al optimizar, puede asumir que la variable no cambia dentro del bloque principal, almacenándola en un registro temporal de la CPU. Esto provocaría que el robot avance infinitamente porque nunca ve que `pulseCount` alcance el valor deseado.
- **Solución:** Debe declararse obligatoriamente como `volatile long pulseCount;`.

### 2. Comparación de Cadenas en ISR (CRÍTICO)
- **Hallazgo:** En `drivebase.cpp` (Línea 49), la interrupción `updatePulse()` realiza la evaluación `if (this->id == "FL" || this->id == "BL")`.
- **Riesgo:** Por un lado, ejecutar comparaciones de strings dentro de una interrupción es computacionalmente lento y mala práctica. Por otro lado, esto es una **comparación de punteros en C++**, no de contenido. Funciona de milagro porque el compilador agrupa los literales de cadena, pero es una bomba de tiempo si cambia el nivel de optimización.
- **Solución:** Reemplazar el `const char* id` por un `enum` interno para designar la posición (ej. `enum Position { FRONT_LEFT, BACK_LEFT, ... }`).

### 3. Concurrencia Bloqueada (`delay()` vs PID)
- **Hallazgo:** Funciones como `runTime()` o las sentencias `delay(1000)` en la recolección (`green_state == 6`) paralizan el hilo principal.
- **Riesgo:** Mientras el procesador duerme en un `delay()`, la función `_motoPID.Compute()` deja de ejecutarse a tiempo, el buffer serial `Serial5` de la Raspberry Pi se rebalsa de datos perdidos, y la lectura de los sensores ultrasónicos se congela.

### 4. Protocolo Serial Sin Integridad (ALTO)
- **Hallazgo:** La función `serialEvent5()` asume que si llega el byte `255`, el próximo byte **si o si** es la velocidad.
- **Riesgo:** Los cables seriales cerca de motores DC sufren de Ruido Electromagnético (EMI). Si un byte se corrompe o se pierde, el robot interpretará un ángulo como velocidad, causando movimientos erráticos, giros bruscos y saliéndose de la pista sin motivo aparente.

---

## 3. Análisis de Nomenclaturas y Estilo (Clean Code)

El código actual presenta una marcada **falta de uniformidad** y abuso de *"Magic Numbers"* (números mágicos codificados duro).

*   **Mezcla de Idiomas:** Variables en inglés conviven con variables en español, a veces en la misma línea (`front_distance`, `left_distance`, `esquinas_negro`, `lado_plateado`, `tiemporescate`, `green_state`).
*   **Convenciones Mixtas:** Hay variables en `snake_case` (`color_detected`, `distance_left_tof`), otras en `camelCase` (`steertimer`, `RanNumber`, `taskDone`), y algunas sin separación (`tiemporescate`).
*   **Magic Numbers:** Instrucciones como `runAngle(25, FORWARD, -95)` o `robot.steer(55, FORWARD, steer)`. Modificar la velocidad del robot requiere buscar en más de 20 líneas diferentes esparcidas por el `main.cpp`.
*   **Punteros y Referencias:** La sintaxis es mayormente correcta al pasar actuadores, pero la encapsulación dentro de `Claw` y `DriveBase` mezcla el acceso a propiedades públicas y privadas.

---

## 4. Oportunidades de Mejora y Cambios Sugeridos

A continuación, una lista priorizada de cambios estructurados (Refactorización):

| ID | Área | Descripción de la Mejora | Cambio a Realizar | Mejora Esperada |
|---|---|---|---|---|
| **OPT-1** | ISR | **Variables Volátiles y Enums** | Cambiar a `volatile long pulseCount`. Usar un `enum` en lugar de `const char* id` en la clase `Moto`. | Previene que el robot "patine infinito" al leer mal la odometría y hace las interrupciones más seguras. |
| **OPT-2** | Concurrencia | **Máquina de Estados Finita (FSM)** | Eliminar todos los `delay()`. Usar un `enum SystemState` y temporizadores `millis() - last_time`. | El PID de los motores será preciso, y el UART nunca se desbordará. El robot será "multitarea" real. |
| **OPT-3** | Comunicaciones | **Protocolo UART Ensobrado** | Cambiar el parser posicional por un paquete estructurado. Ej: `<V:100,A:45,G:0>
`. | Evitar "saltos" fantasmas del robot causados por bytes corruptos o perdidos entre RPi y Teensy. |
| **OPT-4** | Estilo | **Archivo `Config.h` Unificado** | Extraer todos los números, velocidades y pines a un archivo de cabecera. Unificar estilo a `camelCase` e inglés. | Cualquier miembro del equipo podrá ajustar la velocidad o pines en un solo lugar en 5 segundos, sin riesgo de romper otra función. |
| **OPT-5** | Arquitectura | **Desanidar los `while()` principales** | Cambiar los `while(rutina == "linea")` y bucles similares dentro del `loop()` por un modelo plano `if/else if/else`. | Código 10 veces más fácil de leer y depurar. Facilita la inyección de fallos controlados para testing. |

---
*Este análisis documenta los hallazgos técnicos para elevar la calidad arquitectónica del código fuente antes del congelamiento de software para la RoboCup 2026.*
