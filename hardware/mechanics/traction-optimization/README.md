# Optimización de Tracción y Estabilidad en Rampas (RCJ Rescue Line)

> **Autor:** Ai Gemini - **A pedido de:** Gustavo Viollaz
> **Fecha:** 2026-02-23 (America/Argentina/Salta)
> **Prioridad:** P1 (Crucial para superar el 100% de la pista)

Este documento analiza las soluciones mecánicas y de software utilizadas por equipos de nivel internacional para superar rampas de 25°, lomos de burro y planos inclinados laterales sin perder la línea ni volcar.

---

## 1. Ruedas y Neumáticos de Alto Rendimiento

El material de contacto es la variable más importante para la tracción.

### Ruedas de Silicona Personalizadas
Los equipos ganadores suelen fabricar sus propios neumáticos mediante moldes impresos en 3D.
- **Material:** Silicona de grado técnico (ej. **Smooth-On Dragon Skin** o **VytaFlex**).
- **Dureza Shore A:** Se recomienda una dureza de **10A a 20A** (muy blanda). Proporciona un agarre excepcional en las baldosas de la competencia, incluso si hay polvo.
- **Tread (Dibujo):** Superficies lisas (slick) maximizan el área de contacto en superficies limpias, mientras que dibujos con surcos transversales ayudan en rampas con suciedad o irregularidades.

### Ruedas Omni con Rodillos de Silicona
Si el robot usa tracción omnidireccional, se deben reemplazar los rodillos de plástico duro por rodillos de silicona blanda para evitar el patinamiento lateral en rampas transversales.

---

## 2. Gestión Dinámica del Centro de Gravedad (CG)

Un robot con el CG alto volcará en rampas de 25°. El objetivo es mantener el vector de gravedad siempre dentro de la base de sustentación.

### Ajuste Activo mediante Servomotores
1.  **Chasis Basculante:** Algunos equipos montan los ejes de las ruedas sobre brazos accionados por servomotores de alto torque. Al detectar una subida (vía IMU), el robot "baja" su chasis o desplaza las ruedas hacia adelante/atrás para evitar el caballito (*wheelie*).
2.  **Contrapeso con la Garra:** La propia garra/pinza del robot, que suele ser pesada, se utiliza como contrapeso. 
    - **Subida:** Garra hacia adelante y abajo.
    - **Bajada:** Garra hacia atrás y arriba para evitar el vuelco frontal.

### Ubicación de Masas (Diseño Estático)
- La batería (el componente más pesado) debe colocarse lo más cerca posible del suelo, idealmente debajo de los motores si el despeje lo permite.

---

## 3. Sistemas de Suspensión

Mantener las 4 ruedas en contacto con el suelo es vital. Si una rueda queda en el aire, el robot pierde el 25% de su tracción y el PID de dirección se vuelve errático.

- **Suspensión Pasiva (Rocker-Bogie):** Un sistema de pivotes mecánicos (sin resortes) que permite que un lado del robot suba un obstáculo mientras el otro permanece plano. Es el sistema de los rovers de Marte.
- **Chasis Flexible:** Diseñar el chasis con materiales que permitan una ligera torsión (como placas de fibra de vidrio delgadas) actúa como una suspensión natural simplificada.

---

## 4. Control de Tracción por Software (Traction Control)

Incluso con las mejores ruedas, si aplicas demasiada potencia de golpe, la rueda patinará.

### Algoritmo de Detección de Slip
Fusión sensorial entre **Encoders** e **IMU (Acelerómetro)**:
1.  La Teensy mide la velocidad teórica según los encoders ($V_e$).
2.  La Teensy mide la aceleración real del chasis mediante el BNO055 e integra para obtener la velocidad real ($V_r$).
3.  **Si $V_e > V_r$:** La rueda está patinando.
4.  **Acción:** El código reduce automáticamente el PWM del motor hasta que $V_e \approx V_r$.

### Ramping de Velocidad
Nunca aplicar el 100% de PWM instantáneamente. Implementar una curva de aceleración suave (S-Curve o rampa lineal) especialmente cuando se detecta (vía Pitch en la IMU) que el robot está en una inclinación.

---

## 5. Recomendaciones de Implementación

1.  **Prototipado:** Probar moldes de silicona con diferentes durezas Shore.
2.  **Sensores:** Colocar la IMU BNO055 en el centro geométrico del robot para lecturas de Pitch/Roll más limpias.
3.  **Software:** Integrar la lectura del Pitch en el bucle principal de control para reducir la velocidad máxima automáticamente en bajadas pronunciadas.

---
*Este documento guía la evolución mecánica del robot IITA Salta para alcanzar estándares internacionales.*
