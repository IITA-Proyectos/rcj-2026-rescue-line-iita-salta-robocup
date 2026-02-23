# Resumen de Datasheets: Componentes Críticos de Potencia

Este documento contiene los parámetros técnicos vitales extraídos de los manuales de los fabricantes para el diseño del robot RCJ 2026.

## 1. Regulador DC-DC XL4016 (Alimentación Raspberry Pi)
*   **Voltaje de Entrada:** 4V a 40V DC.
*   **Voltaje de Salida:** 1.25V a 35V DC (Ajustable).
*   **Corriente Máxima:** 8A constantes (requiere disipador de calor arriba de 5A).
*   **Frecuencia de Conmutación:** 180 kHz.
*   **Eficiencia:** Hasta 96%.
*   **Protección:** Cortocircuito, sobrecalentamiento y limitación de corriente.
*   *Nota Crítica:* Ajustar a **5.1V** para alimentar la Raspberry Pi 4B/5 por pines GPIO o USB.

## 2. Driver de Motores VNH5019 (Tracción 12V)
*   **Voltaje de Operación:** 5.5V a 41V.
*   **Corriente de Salida:** 30A continuos (se recomienda ventilación forzada para corrientes sostenidas >12A).
*   **Frecuencia PWM:** Hasta 20 kHz.
*   **Diagnóstico:** Provee salida analógica proporcional a la corriente del motor (Current Sense).
*   **Protección:** Apagado térmico, bloqueo por bajo voltaje y protección contra voltaje inverso de batería.

## 3. Sensor de Telemetría INA219 (I2C)
*   **Voltaje de Bus:** 0V a 26V.
*   **Precisión:** Resolución de 12 bits para corriente y voltaje.
*   **Interfaz:** I2C (Dirección configurable mediante jumpers).
*   **Función en el Robot:** Monitorear el estado de carga de la batería LiPo 3S para evitar descargas profundas (<3.3V por celda).

## 4. Batería LiPo 3S (Parámetros de Seguridad)
*   **Voltaje Nominal:** 11.1V (3 celdas de 3.7V).
*   **Voltaje Cargada (Max):** 12.6V (4.2V por celda).
*   **Voltaje Descarga (Min):** 9.9V (3.3V por celda). **NO DESCENDER DE ESTE VALOR**.
*   **Tasa de Descarga (C):** 35C (Permite picos de corriente muy altos para el arranque de motores).

---
*Archivos técnicos de referencia para IITA Salta.*
