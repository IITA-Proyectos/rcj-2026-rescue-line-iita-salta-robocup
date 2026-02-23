# Análisis Estratégico y de Código: Lógica de Rescate (Teensy)

> **Autor:** Ai Gemini - **A pedido de:** Gustavo Viollaz
> **Fecha:** 2026-02-23 (America/Argentina/Salta)
> **Enfoque:** Vulnerabilidades de la Máquina de Estados, Fallo de Sensores y Escenarios Borde (Edge Cases).

Este documento evalúa de forma crítica la sección del código de la Teensy dedicada a la Zona de Rescate (`rutina == "rescate"`), contrastando la lógica programada con las condiciones hostiles del reglamento internacional RoboCup Junior Rescue Line.

---

## 1. Estrategia Integrada (RPi + Teensy) y Lógica Implícita

El paradigma actual del robot asume que la **Raspberry Pi tiene visión perfecta** y que **la física del entorno es ideal**. 
- La Teensy se subordina completamente a los comandos de la RPi (`green_state`).
- Cuando la RPi detecta una pelota (ej. `green_state == 6`), la Teensy entra en una **secuencia ciega y bloqueante** de recolección de aproximadamente 8 segundos.
- La orientación y el depósito se basan en giros absolutos (ej. `runAngle(180)`), asumiendo que la zona de depósito siempre estará exactamente a sus espaldas.

---

## 2. Casos de Fallo en el Entorno Real (Edge Cases)

El diseño actual es muy frágil ante las variaciones que los jueces introducen en la pista:

### A. Pelotas Falsas y Reflejos (Luz que encandila)
*   **El Problema:** La luz del sol o focos LED pueden crear reflejos plateados en el suelo o en las paredes blancas. Si la RPi se encandila y emite un falso positivo (`green_state = 6`), la Teensy detendrá el robot y ejecutará una recolección "en el aire".
*   **Impacto:** El robot pierde 10 segundos vitales. Si esto se repite, el contador `ball_counter` aumentará falsamente a 3, forzando al robot a intentar depositar pelotas fantasmas, perdiendo los puntos de evacuación.
*   **Solución Sugerida:** **Detección Táctil/Cercana.** Antes de cerrar la pinza, la Teensy debe confirmar la lectura de la cámara verificando si el sensor ToF o el ultrasonido ven un objeto físico a menos de 10 cm.

### B. Palitos (Debris) y Pérdida de Tracción
*   **El Problema:** Al atrapar la pelota, el código ejecuta `runDistance(30, FORWARD, 8)`. Si el robot pisa los palitos (debris) del reglamento, las ruedas patinarán.
*   **Impacto:** Los motores giran, los encoders suman pulsos, y el software cree que avanzó 8 cm, pero el robot no se movió físicamente. La pinza se cerrará *antes* de alcanzar la pelota, empujándola lejos.
*   **Solución Sugerida:** Fusión de Encoders + IMU para asegurar el avance real, o avanzar hasta que un sensor de colisión o el ToF marque distancia cero con la pelota.

### C. Obstáculos dentro de la Zona de Rescate
*   **El Problema:** El bloque `while (rutina == "rescate")` simplemente inyecta velocidad y dirección: `robot.steer(speed, FORWARD, steer)`.
*   **Impacto:** Si hay un obstáculo (ladrillo negro) entre el robot y la pelota, el robot se estrellará contra él de frente.
*   **Solución Sugerida:** La Teensy debe usar sus ultrasonidos en modo interrupción. Si `front_distance < 10` y la cámara no reporta una pelota, el robot debe abortar el avance y rodear el obstáculo.

### D. Posiciones Aleatorias de Entrada y Salida
*   **El Problema:** Al llegar a 3 pelotas, el robot ejecuta `runAngle(20, FORWARD, 180)` y retrocede para depositar.
*   **Impacto:** El reglamento permite zonas de rescate cuadradas donde la entrada está en el "Sur" y la zona de depósito en el "Este". Girar 180° siempre asume un escenario simétrico (Sur-Norte). El robot depositará las pelotas contra una pared vacía.
*   **Solución Sugerida:** La RPi debe buscar visualmente el triángulo rojo/verde de la zona de depósito y guiar a la Teensy dinámicamente, en lugar de usar rutinas codificadas rígidas.

---

## 3. Análisis de Fallo de Sensores (Single Points of Failure)

¿Qué pasa cuando el hardware falla en medio de la competencia?

1.  **Falla del Giroscopio (BNO055):** 
    - En la función `runAngle()`, el código depende de un `while(true)` comprobando si el `error` angular es menor a 1.0. Si el bus I2C se cuelga por estática o un cable se afloja, el BNO055 deja de actualizar `event.orientation.x`. El error nunca llegará a cero y **el robot se congelará para siempre** (Infinite Loop).
    - **Fix:** Añadir un timeout de emergencia (`if (steertimer > 5000) break;`).
2.  **Falla del Sensor de Distancia Frontal:**
    - En la línea 641, durante la fase de depósito, el robot entra en un bucle: `while(digitalRead(32) == 0) { if(!alineado && front_distance < 12) ... }`.
    - Si el cable Echo/Trig del ultrasonido se corta, `front_distance` devolverá 0 de forma errática o se clavará en infinito. El robot jamás considerará que llegó a la pared, destrozando la pinza contra la madera.
    - **Fix:** Validar usando el impacto detectado por el acelerómetro (picos bruscos en X/Y).

---

## 4. Auditoría de Código Línea por Línea (Fragmentos Críticos de `main.cpp`)

| Líneas | Función / Bloque | Crítica Técnica |
| :--- | :--- | :--- |
| **250-325** | `runAngle()` | Carece de *Timeout*. Es la función más peligrosa del robot. Si las ruedas se atascan en la pared y el robot no puede girar físicamente, los motores se quemarán y el programa no avanzará al siguiente estado. |
| **328-369** | `runDistance()` | `while (fr.pulseCount <= encoder)`. Si una rueda se traba mecánicamente (ej. pelo enredado en el eje), el encoder no suma pulsos. El robot queda en bucle infinito. Falta un watchdog timer. |
| **569-588** | Secuencia `green_state == 6` | Está construida íntegramente con llamadas sucesivas a `delay(1000)`. Mientras esto ocurre, el robot queda ciego, sordo y no puede procesar comandos nuevos de la Raspberry Pi (se desborda el buffer UART). |
| **604-608** | Lógica `ball_counter>= 3` | Inflexible. Si el robot falló un intento de captura, el contador igual subió. El robot creerá que tiene la panza llena y se irá a depositar pelotas inexistentes temprano. |
| **634-645** | `alineado=false` | Intento de alineación contra la pared usando ultrasonidos simples. Muy vulnerable al ángulo de incidencia del sonido; si el robot choca a 45°, el ultrasonido rebotará hacia otra dirección y leerá distancia máxima, fallando la alineación. |

---
*Este análisis evidencia la necesidad de transicionar de un "script secuencial" a un "sistema reactivo basado en eventos" para garantizar la invulnerabilidad del robot en competencias internacionales.*