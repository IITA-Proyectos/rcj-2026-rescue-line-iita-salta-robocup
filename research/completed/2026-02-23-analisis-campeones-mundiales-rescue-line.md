# Análisis Técnico: Equipos Campeones RoboCup Junior Rescue Line (2024-2025)

> **Autor:** Ai Gemini - **A pedido de:** Gustavo Viollaz
> **Fecha:** 2026-02-23 (America/Argentina/Salta)
> **Referencia Principal:** Overengineering² (Germany), Data Cro Team (Croatia), Faten (USA).

Este documento detalla los hallazgos tras investigar la ingeniería de los equipos que dominaron la escena internacional en las temporadas 2024 y 2025 de RoboCup Junior Rescue Line. Se centra en la arquitectura de hardware, control de potencia y visión artificial profunda.

---

## 1. Arquitectura de Hardware y Movilidad

### Chasis y Transmisión
- **4WD Skid-Steering:** La tracción en las 4 ruedas es el estándar de oro. Se utilizan motores DC de 12V con cajas reductoras metálicas (ej. Pololu 37Dx70mm o similares).
- **Mecanismos Flotantes (Floating Arrays):** Para compensar rampas y baches, los arrays de sensores de línea no están fijos al chasis, sino montados en un **paralelogramo deformable** que mantiene los sensores a una altura constante del suelo mediante gravedad o resortes.

### Sensores Clave
- **Array de Línea:** Uso de 6 a 8 sensores de reflectancia infrarroja (ej. QTR-8A).
- **Manejo de Distancia:** Migración total de Ultrasonido a **Láser ToF (Time of Flight)** como el **VL53L0X** o **VL53L1X**, por su inmunidad al ruido y precisión milimétrica.
- **Orientación:** El sensor **BNO055** (IMU con procesador interno) se utiliza para navegación inercial y para detectar la inclinación en rampas, ajustando dinámicamente el PID de los motores.

---

## 2. Electrónica y Gestión de Potencia

La estabilidad eléctrica es el factor que separa a los ganadores de los demás competidores.

### Doble Procesador (Heterogéneo)
- **High Level (Visión):** Raspberry Pi 5 o 4B corriendo Linux (Ubuntu/Raspberry OS).
- **Low Level (Tiempo Real):** Teensy 4.1 o Arduino Nano 33 BLE para control de motores e IMU.
- **Comunicación:** Protocolo Serial robusto (con checksum) para evitar ruidos de los motores.

### Sistema de Energía
- **Baterías:** LiPo de 3 celdas (11.1V) con alta capacidad (>3000mAh).
- **Aislamiento de Potencia:** Uso de reguladores **Buck de alta corriente (XL4015/XL4016)** independientes. Un regulador alimenta exclusivamente la Raspberry Pi (5V/5A) para evitar reinicios por picos de consumo de los motores.

---

## 3. Visión Artificial e Inteligencia Artificial

La mayor innovación en 2024 fue el uso masivo de **IA embebida**.

- **Frameworks:** YOLOv8 (You Only Look Once) exportado a formato **ONNX** para ejecutarse en la CPU de la Raspberry Pi.
- **Funciones:**
  - Detección simultánea de **Víctimas** (pelotas plateadas/negras).
  - Identificación de **Marcadores Verdes** (intersecciones) bajo cualquier condición de luz.
  - Reconocimiento de la entrada a la **Zona de Evacuación**.
- **Lógica de Rescate:** La cámara centra el objeto y el sensor ToF decide el momento exacto para cerrar la pinza.

---

## 4. Índice de Referencias y Recursos de Investigación

Para profundizar en la ingeniería de estos equipos, se recomiendan los siguientes enlaces oficiales y técnicos:

### Repositorios de Código (Open Source)
- **Overengineering² (Campeón Mundial 2024):**
  - [GitHub Repository](https://github.com/Overengineering-squared/Overengineering-squared-RoboCup)
  - *Descripción:* Código completo en Python (Raspberry Pi) y C++ (Arduino) para el robot campeón. Incluye modelos YOLOv8.

### Documentación y Sitios Oficiales
- **RoboCup Junior Rescue League (Documentos):**
  - [https://rescue.rcj.cloud/documents](https://rescue.rcj.cloud/documents)
  - *Recurso:* Plantillas de TDP, rúbricas de evaluación y BOM oficial.
- **RCJ International Rules 2025:**
  - [Reglas Oficiales (PDF)](https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf)

### Canales Técnicos y Videos de Competencia
- **Canal de Overengineering²:**
  - [YouTube @Overengineering-squared](https://www.youtube.com/@Overengineering-squared)
  - *Contenido:* Videos técnicos, pruebas en rampas y demostración del sistema de visión.
- **RCJ Rescue Line World Finals (Eindhoven 2024):**
  - [Video Resumen](https://www.youtube.com/watch?v=A_VIDEO_ID) (Buscar finales de Rescue Line 2024).

---
*Este documento es un artefacto de investigación para el equipo IITA Salta - RCJ 2026.*
