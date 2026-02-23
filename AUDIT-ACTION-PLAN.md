# 📋 Plan de Acción de Auditoría Técnica - RCJ 2026

> **IMPORTANTE:** Este documento contiene la lista de **Bugs Críticos** detectados por IA Gemini bajo supervisión de Gustavo Viollaz. Su resolución es de máxima prioridad para garantizar la estabilidad del robot en competencia.

---

## 🚨 1. Bugs Críticos (Resolución Inmediata)

| Prioridad | Bug | Ubicación | Impacto |
| :--- | :--- | :--- | :--- |
| **P0** | **Optimización de Encoders:** Falta de palabra clave `volatile`. | `drivebase.h` | El robot puede avanzar infinitamente sin detenerse. |
| **P0** | **Latencia de IA:** Carga del modelo YOLO cada vez que entra a rescate. | `Main.py` | Congelamiento del robot por 3-5 segundos al entrar a zona de pelotas. |
| **P1** | **Bloqueo Serial:** Uso de `delay()` en secuencias de pinza. | `main.cpp` / `claw.cpp` | Pérdida de comandos de la Raspberry Pi y lag en la dirección. |
| **P1** | **Comparación Segura:** Comparación de strings por puntero (`==`). | `drivebase.cpp` | Fallos lógicos aleatorios en el control de motores. |
| **P2** | **Watchdogs Faltantes:** Bucles `while` sin tiempo límite (timeout). | `main.cpp` | El robot se bloquea permanentemente si se atasca físicamente. |

---

## 🚀 2. Oportunidades de Mejora (Refactorización)

1.  **Heartbeat Serial:** Implementar un sistema de "latido" entre RPi y Teensy. Si la comunicación se corta, el robot debe detenerse por seguridad.
2.  **Iluminación por GPIO:** Controlar un anillo de LEDs blancos desde la Raspberry Pi para estabilizar la detección de colores sin importar la luz del estadio.
3.  **FSM No Bloqueante:** Migrar la lógica de la Teensy a una **Máquina de Estados** basada en tiempo (`millis()`) para que el PID de motores nunca se detenga.
4.  **Fusión ToF-Visión:** Utilizar los sensores láser para confirmar la captura de pelotas, no solo el ancho de la caja en la cámara.
5.  **Control de Velocidad por Inclinación:** Usar la IMU para reducir automáticamente la velocidad en bajadas y evitar volcamientos.

---

## 🏗️ 3. Sugerencias Organizativas (IITA Standards)

*   **GitHub Issues:** Mover todos los pendientes a Issues individuales con sus etiquetas de prioridad.
*   **OS Backups:** Mantener imágenes clonadas de la SD de la Raspberry Pi en una carpeta dedicada `hardware/raspberry/os-backups/`.
*   **Testing Matrix:** Registrar cada prueba en `testing/TEST_LOG.md` con métricas de éxito (ej. "8/10 verdes detectados").
*   **Manual de Calibración:** Crear una guía rápida para calibrar colores y foco en menos de 5 minutos antes de un round.

---
*Este plan es dinámico y debe actualizarse a medida que se cierren los Issues correspondientes.*
