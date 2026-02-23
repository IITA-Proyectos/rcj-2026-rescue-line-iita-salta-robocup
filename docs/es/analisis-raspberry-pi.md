# Análisis Detallado de Software: Raspberry Pi 4B

> **Autor:** Ai Gemini - **Solicitado por:** Gustavo Viollaz
> **Fecha:** 22 de febrero de 2026

## 1. Análisis de Funcionamiento

El software de la Raspberry Pi está diseñado para ser el nodo de procesamiento de imagen y toma de decisiones de alto nivel. Se divide en dos lógicas principales: **Seguimiento de Línea** (OpenCV Tradicional) y **Zona de Rescate** (Deep Learning).

### Flujo de Trabajo
1.  **Captura Asíncrona:** El archivo `camthreader.py` separa la captura de frames del procesamiento. Esto garantiza que el procesador siempre trabaje con la imagen más reciente, eliminando el retraso del buffer de hardware.
2.  **Seguimiento de Línea:** 
    *   Utiliza el método de **Centro de Masa Ponderado**. Los píxeles negros en la parte inferior del frame tienen más peso en el cálculo del error que los del horizonte.
    *   La detección de intersecciones verdes se realiza mediante ROIs (Region of Interest) laterales.
3.  **Zona de Rescate:**
    *   Cambia a un modelo de detección de objetos **YOLOv8** exportado a **ONNX**.
    *   Implementa un sistema de seguimiento (Centroid Tracking) para mantener la identidad de las pelotas detectadas.

---

## 2. Riesgos y Errores Identificados (Bugs & Risks)

### CRÍTICO: Gestión de Memoria en Rescate
La función `modo_rescate()` carga el modelo YOLO cada vez que se invoca. 
*   **Impacto:** Esto puede causar que el robot se detenga durante 3-5 segundos al entrar a la zona de rescate. Si la memoria RAM se fragmenta, el sistema operativo podría cerrar el programa por falta de memoria (OOM Killer).

### ALTO: Lógica de Búsqueda de Objetos
Si no hay objetivos en el frame durante el modo rescate, el robot tiene un comando por defecto de giro a 90°.
*   **Impacto:** El robot girará sin sentido si la pelota queda fuera de su campo visual inicial, sin una estrategia de exploración real.

### MEDIO: Sensibilidad a la Iluminación
Los umbrales de color (HSV/LAB) son estáticos. 
*   **Impacto:** El robot es vulnerable a cambios en la iluminación del ambiente de la competencia. El color "Plateado" de la entrada a rescate es especialmente propenso a confundirse con reflejos blancos.

---

## 3. Oportunidades de Mejora y Hallazgos

1.  **Carga Diferida de Modelos:** Mover la inicialización de YOLO al inicio del script principal (`Main.py`) para que solo ocurra una vez.
2.  **Integración de Sensores de Distancia:** Actualmente, la RPi "estima" la distancia a la pelota por su tamaño en píxeles. Se recomienda usar la lectura de los sensores **ToF (VL53L0X)** de la Teensy para validar que la pelota está realmente frente a la pinza antes de cerrar.
3.  **Optimización de FPS:** Implementar una máscara de búsqueda dinámica que solo procese el área donde se detectó la línea en el frame anterior.
4.  **Protocolo de Comunicación:** Añadir una suma de verificación (Checksum) a los datos enviados por Serial para evitar que ruidos eléctricos de los motores causen movimientos erráticos.

---
*Documento generado para el equipo de desarrollo de IITA Salta.*
