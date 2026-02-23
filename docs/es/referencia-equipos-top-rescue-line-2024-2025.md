# Estudio de referencia: enfoques de equipos top en RoboCupJunior Rescue Line (2024–2025) y lecturas clave de reglas 2025

**Fecha de creación:** 2026-02-23 (America/Argentina/Salta)  
**Creado por:** ChatGPT 5.2 (GPT-5.2 Pro) a pedido de **Gustavo Viollaz**  
**Propósito:** Documento de **referencia técnica** para diseño de robot, estrategia de puntaje y armado del TDP/Poster/Video en Rescue Line.  
**Ubicación sugerida en el repo:** `docs/es/referencia-equipos-top-rescue-line-2024-2025.md`  
**Alcance:** Navegación, tracción y mecánica para rampas/seesaw, detección de línea y verde, zona de evacuación, búsqueda y clasificación de víctimas, sensores, potencia, comunicación en SuperTeam y estrategias de scoring (reglas 2025).

---

## 0) Transparencia y metodología (para no inventar)

RoboCupJunior no obliga a que el TDP de todos los equipos sea público en internet. En la práctica, **muchos TDP ganadores no están accesibles públicamente** (o están detrás de plataformas de evento).

Para mantener este documento 100% verificable, el análisis se basa en fuentes abiertas y rastreables:

1) **Resultados oficiales** (para identificar ganadores 2024 y 2025).  
2) **Reglamento oficial RCJ Rescue Line 2025 (final)** (para números, restricciones y scoring).  
3) **Documentation técnica pública de equipos de alto rendimiento**, incluyendo:
   - **Overengineering²** (campeón mundial 2024; repositorio público y muy detallado).
   - **Airborne** (equipo 2025 con documentación pública extremadamente completa —no necesariamente campeón— pero útil como “referencia de ingeniería + documentación”, porque publica arquitectura, componentes y enfoque).

> Si tu objetivo es comparar exactamente con el TDP del campeón 2025 (“Danesh”), necesitás acceso al TDP (si existe) vía la organización del evento o el equipo. Este documento incluye prácticas de referencia “nivel campeón” basadas en lo que sí es público.

---

## 1) Ganadores 2024 y 2025 (confirmación oficial)

### RoboCup 2024 (World Championship)
- **1º Overengineering²**
- 2º Danesh
- 3º Školska knjiga CRO Team

Fuente (awards oficiales): https://rescue.rcj.cloud/events/2024/RoboCup2024/award

### RoboCup 2025 (World Championship)
- **1º Danesh**
- 2º Offroad
- 3º .Jonson

Fuente (awards oficiales): https://rescue.rcj.cloud/events/2025/RoboCup2025/award

---

## 2) Qué “obliga” la pista: números que deben guiar el diseño (Reglas 2025)

Este resumen no es para memorizar: es para diseñar contra la realidad del campo.

### 2.1 Línea y tiles
- Tiles: **30×30 cm**
- Línea negra: **1–2 cm** de ancho
- Puede haber “juntas” entre tiles de hasta **3 mm**

### 2.2 Gaps
- Antes de un gap hay **≥ 5 cm** de línea negra.
- Largo de gap: **≤ 20 cm**

### 2.3 Marcadores verdes (intersecciones)
- Verdes: **25×25 mm**
- Sin verde: seguir recto
- “Dead end”: dos verdes (uno a cada lado) → robot debe girar **180°**

### 2.4 Obstáculos, bumps, debris
- Speed bump: altura **≤ 1 cm**
- Debris: altura **≤ 3 mm**, suelto (no fijado)
- Obstáculo: al menos **15 cm** de alto

### 2.5 Rampas y seesaw (la parte que más define mecánica)
- Rampas: inclinación **≤ 25°**; pueden ser multi-tile.
- Seesaw: inclinación **< 20°**, línea recta.

### 2.6 Evacuation Zone (EZ)
- Dimensiones: **120×90 cm**, con paredes alrededor (≥ 10 cm)
- Entrada EZ: cinta **plateada reflectiva 25×250 mm**
- Salida EZ: cinta **negra 25×250 mm**
- Víctimas: esferas de **4–5 cm**, peso hasta **80 g**
  - “Viva”: **plateada**, reflectiva y **conductiva**
  - “Muerta”: **negra**, no conductiva
  - Total: **2 vivas + 1 muerta**

**Fuente de todo lo anterior:** Reglamento RCJ Rescue Line 2025 (final):  
https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

---

## 3) Scoring 2025: cómo se gana (y cómo se pierde) sin darte cuenta

En 2025, ganar no es solo “andar”: es **andar + documentar + resolver technical challenge**.

### 3.1 Puntos de campo (resumen útil)
- Tiles entre checkpoints:  
  - 1º intento: **5 pts/tile**  
  - 2º intento: **3 pts/tile**  
  - 3º intento: **1 pt/tile**  
  - >3: **0**  
- Hazards por tile: gaps (10), bumps (10), intersecciones (10), rampa (10 por tile inclinado), obstáculo (20), seesaw (20).

**Traducción:** consistencia > velocidad. Evitar reintentos y LOP da más puntos que correr.

### 3.2 Multiplicadores por rescate (SVR)
- Cada viva rescatada: multiplicador **×1.4**.
- La muerta suma **×1.4** solo si ya se evacuaron las 2 vivas.
- Cada Lack of Progress en el run con EZ recorta multiplicador: se resta **0.05 × LOP** (con mínimo 1.25).

**Lectura estratégica:** entrar a la EZ sin plan robusto es el camino más corto a perder multiplicadores.

### 3.3 Peso de documentación y technical challenge
Score total =  
- 0.6 field + 0.2 rubrics + 0.2 technical challenge (normalizados).  
Rubrics = 0.6 TDP + 0.2 video + 0.2 poster.

**Lectura:** un robot excelente puede perder contra uno “apenas menor” pero con documentación impecable.

Fuente: Reglamento RCJ Rescue Line 2025 (final):  
https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

---

## 4) Arquitectura “patrón campeón” 2024–2025

Analizando Overengineering² (campeón 2024) y Airborne (equipo 2025 con docs públicas completas) aparece un patrón común:

1) **Visión como sensor principal** (línea + verde + objetos/zonas).  
2) **Compute fuerte + aceleración** (ej. Coral TPU) para inferencia en tiempo real.  
3) **Arquitectura distribuida**: SBC (Pi) para percepción/decisión + microcontrolador para control determinista.  
4) **4WD + ruedas blandas + compliance** (suspensión o chasis que “perdona” el terreno).  
5) **Observabilidad**: telemetría, GUI o interfaz web para calibrar rápido.

### 4.1 Overengineering² (campeón 2024): “visión-first” + ecosistema de debug
En su repo público reportan:
- Raspberry Pi (en iteraciones recientes mencionan Pi 5) + **Coral USB Accelerator**.
- Programa principal en Python con **OpenCV + NumPy**, usando **multiprocessing**.
- GUI para monitorear cámaras/sensores en vivo.
- Uso de IMU (mencionan BNO055), y una cantidad importante de sensores IR.
- Iluminación LED dedicada para estabilizar visión.

Fuente: https://github.com/Overengineering-squared/Overengineering-squared-RoboCup

### 4.2 Airborne (2025, docs públicas ejemplares): dual-procesador + YOLOv8 + ToF masivo
En su documentación pública reportan:
- Raspberry Pi 5 + Raspberry Pi Pico + Coral USB.
- 2 modelos YOLOv8: víctimas y detección de la tira plateada de entrada a EZ.
- **5× VL53L0X (ToF)** + mux I2C, más IMU.
- 4× motores DC 12V (77 RPM), ruedas de silicona, suspensión pasiva.
- Reguladores buck dedicados, PCBs custom, interfaz Websocket/HTML para debug.

Fuente: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

---

## 5) Navegación (seguir la línea): enfoques y trade-offs reales

### 5.1 Enfoque 1: Cámara + visión clásica (OpenCV)
**Qué hace:** segmentación de línea (negro/blanco), cálculo de error lateral/ángulo, control PID.

**Por qué funciona en nivel top:**
- Una cámara puede ver *mucho más* que un sensor puntual: curvas, intersecciones, gaps, y contexto.
- Con ROI bien elegido, el control es estable y rápido.

**Dónde falla si no sos cuidadoso:**
- Iluminación variable: sombras, reflejos, luz cálida/fría.
- Motion blur y rolling shutter.

**Mitigaciones típicas de equipos fuertes:**
- Iluminación propia (LED) + control de exposición/balance.
- GUI/calibración rápida en sitio (sliders de HSV / umbrales).
- Logging (FPS, latencia, tasa de error).

Referencia de implementación real (campeón 2024): Overengineering² usa OpenCV/NumPy y multiprocessing.  
Fuente: https://github.com/Overengineering-squared/Overengineering-squared-RoboCup

### 5.2 Enfoque 2: Array de reflectancia IR (clásico)
**Qué hace:** 8–16 sensores al piso, estima posición de línea por ponderación, PID sobre error.

**Ventajas:**
- Muy baja latencia.
- Muy fácil de depurar y tunear.

**Desventajas:**
- Verde (25×25 mm) se vuelve un problema aparte.
- En rampas/seesaw cambia la distancia sensor-piso → lectura se deforma.
- En gaps (hasta 20 cm) necesitás estrategia extra (IMU/encoders/visión).

**Cuándo elegirlo:**
- Si el equipo quiere máxima simplicidad y estabilidad.
- Si el hardware de cámara/compute es débil o está restringido localmente.

### 5.3 Enfoque 3: Híbrido (visión + IR)
Muchos equipos (aunque no siempre lo publican) combinan:
- Visión para contexto (verde, gaps, línea “lejana”)
- IR para control fino a alta frecuencia

**Trade-off:** más hardware y calibración, pero redundancia ante fallos.

---

## 6) Gaps: cómo no perder puntos por “un vacío de 20 cm”

**Dato de regla:** gap ≤ 20 cm y siempre precedido por ≥5 cm de línea.  
Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

### Estrategia A (visión): “predicción de continuidad”
- Detectar que “desaparece” la línea y usar el heading estimado por la recta anterior.
- Mantener velocidad moderada + corrección suave.
- Reanudar line-follow cuando reaparece el negro.

### Estrategia B (IMU/encoders): “mantener rumbo”
- Congelar setpoint de dirección.
- Avanzar distancia estimada (encoders) o tiempo calibrado.
- Rehabilitar sensores al detectar negro.

**Comparativa:**
- Visión suele ser más tolerante a pequeñas desviaciones si el FOV captura el reenganche.
- Encoders son buenos si el piso es consistente; patinaje en rampa puede engañar.

---

## 7) Detección de verde en intersecciones: el filtro anti-falsos-positivos

**Dato de regla:** verdes 25×25 mm; doble verde = dead end (giro 180°).  
Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

### Solución con cámara (la más escalable)
**Best practice:** *buscar verde solo cuando hay evidencia de intersección*.  
Ejemplo: si la línea se ensancha, aparece “T”, o hay múltiples blobs negros.

Así evitás:
- detectar verde en ruido / objetos fuera de pista,
- o confundir tonos por iluminación.

### Alternativa: sensor de color cercano al piso
Funciona si:
- el robot pasa “cerca” del cuadrado verde,
- y el sensor está bien posicionado.

Es muy simple, pero menos tolerante al error de trayectoria.

---

## 8) Tracción, rampas y seesaw: mecánica que se nota en el score

### 8.1 Lo que la regla obliga
- Rampas hasta 25°
- Seesaw < 20°
- Speed bumps hasta 1 cm

Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

### 8.2 Patrón observado en equipos fuertes
- **4WD** y **ruedas blandas** (neopreno/silicona).  
  - Airborne: ruedas de silicona + 4 motores 12V.  
  - Overengineering²: ruedas de neopreno + 4 motores DC.

Fuentes:  
- Airborne: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/  
- Overengineering²: https://github.com/Overengineering-squared/Overengineering-squared-RoboCup

### 8.3 Comparativa mecánica de alternativas (con lectura “coach”)
**2WD + rueda loca**
- ✅ simple y liviana  
- ❌ patina más en rampas y cambia el apoyo en seesaw  
- ❌ suele requerir correcciones más agresivas → más riesgo de LOP

**4WD rígido**
- ✅ mejor tracción y control  
- ❌ si el chasis es rígido, en irregularidades puede “apoyar en 2 ruedas” → perdés tracción

**4WD + compliance (suspensión o chasis flexible + ruedas blandas)**
- ✅ maximiza tracción y estabilidad  
- ✅ reduce vibración (mejor visión)  
- ❌ más piezas y complejidad

Airborne publica suspensión pasiva como una decisión explícita.  
Fuente: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

### 8.4 Control de rampa (software)
Recomendación de alta tasa de éxito:
- Detectar rampa por IMU (pitch).
- Cambiar a “modo rampa”: velocidad menor + control de velocidad con encoders (si hay).
- Evitar giros bruscos (patinaje).

---

## 9) Sensores: el “tridente” moderno (Cámara + IMU + Distancia)

### 9.1 Cámara
Sirve para:
- línea, verde, gaps
- entrada EZ (plateado)
- víctimas y zonas

### 9.2 IMU
Overengineering² usa BNO055; Airborne usa ICM-20948.  
Fuentes:
- https://github.com/Overengineering-squared/Overengineering-squared-RoboCup  
- https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

Usos típicos:
- sostener heading en gaps
- detectar rampas/seesaw (pitch/roll)
- estabilizar control ante bumps

### 9.3 Distancia: ToF vs ultrasonido (y por qué ToF se ve mucho en 2025)
Airborne reporta 5× VL53L0X (ToF) + mux I2C.  
Fuente: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

**ToF**
- ✅ preciso en corto alcance, rápido, compacto  
- ❌ sensible a superficies negras/absorción y ángulos extremos  
- ❌ muchos ToF en I2C → mux

**Ultrasonido**
- ✅ barato y simple  
- ❌ ecos y “fantasmas” en espacios chicos  
- ❌ más lento / menos determinista

**Coach tip:** en EZ (paredes y objetos), ToF suele dar conducta más repetible.

---

## 10) Entrada a la Evacuation Zone: detección de “plateado” (y por qué algunos usan IA)

**Dato de regla:** entrada EZ marcada por cinta plateada reflectiva 25×250 mm.  
Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

Airborne reporta un modelo YOLOv8 dedicado a detectar esa tira.  
Fuente: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

### Alternativas comparadas
1) Sensor reflectivo al piso (umbral)  
   - ✅ simple y rápido  
   - ❌ sensible a luz, ángulo, desgaste, brillos “falsos”

2) Cámara + umbral por brillo/color  
   - ✅ más contexto  
   - ❌ requiere calibración fina y control de exposición

3) Cámara + modelo ML (YOLO/segmentation)  
   - ✅ robusto si dataset está bien  
   - ❌ requiere dataset/entrenamiento/compute (ej. Coral)

---

## 11) Víctimas: detección, clasificación y manipulación (la parte que multiplica)

### 11.1 Qué define a viva/muerta (regla)
- Viva: plateada reflectiva y **conductiva**  
- Muerta: negra, **no conductiva**  
Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

### 11.2 Detección de víctimas: visión clásica vs IA
Overengineering² indica que migraron a IA porque ciertas técnicas OpenCV (ej. Hough Circles) eran frágiles para tareas de detección.  
Fuente: https://github.com/Overengineering-squared/Overengineering-squared-RoboCup

Airborne usa YOLOv8 para víctimas.  
Fuente: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

**Conclusión práctica:** en 2024–2025 la tendencia es usar ML donde OpenCV se vuelve muy dependiente del “caso ideal”.

### 11.3 Clasificación viva/muerta: visión vs conductividad vs híbrido
**A) Solo visión (color/reflexión)**
- ✅ sin contacto  
- ❌ plateado con sombra puede parecer oscuro; negro brillante puede engañar

**B) Conductividad**
- ✅ confirmación muy robusta si el contacto es bueno  
- ❌ requiere diseño mecánico (electrodos) y lectura estable al agarrar

**C) Híbrido (recomendado)**
- Visión para localizar/posicionar  
- Conductividad para confirmar una vez capturada

### 11.4 Mecanismo de rescate: características de “alto % de éxito”
Airborne publica brazo de rescate con doble servo.  
Overengineering² lista servos de alto torque (hasta 35 kg).

Fuentes:
- https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/  
- https://github.com/Overengineering-squared/Overengineering-squared-RoboCup

**Best practices observadas en equipos fuertes:**
- “Funnel” o guía física que encamina la esfera hacia la garra.
- Fijación estable (sin rebotar) antes de levantar.
- Depósito con geometría que evita que la pelota rebote y salga.

---

## 12) Motores y transmisión: por qué aparece tanto 12V y RPM bajas

Airborne reporta 4× motores DC 12V 77 RPM.  
Fuente: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

**Lectura:** 77 RPM (dependiendo del diámetro de rueda) ofrece:
- torque alto para rampas,
- velocidad controlable para seguir línea y no sobrepasar verdes.

### Alternativas (y cómo impactan)
- **Más RPM:** más rápido, pero más difícil de controlar y más patinaje en rampas.
- **Menos RPM:** más torque, más estable, pero puede quedar lento si el control es pobre.

**Coach tip 2025:** por scoring y penalizaciones, “rápido pero errático” suele perder.

---

## 13) Potencia: baterías y reguladores (lo que mata runs sin que lo veas)

Airborne reporta:
- 3S LiPo 2700mAh
- step-downs dedicados (Pololu D24V50F5 / D36V28F5)
- PCBs custom para distribución

Fuente: https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

### Alternativas comparadas
**2S LiPo**
- ✅ simple  
- ❌ para 12V necesitás boost o motores distintos

**3S LiPo (muy común en “pro”)**
- ✅ alimenta 12V con margen  
- ✅ buck a 5V para SBC + sensores  
- ❌ exige buen diseño de distribución y protecciones

**Rails separados (batería lógica vs motores)**
- ✅ reduce resets por ruido  
- ❌ peso y logística extra

**Best practices “competencia”:**
- Buck serio para 5V de Raspberry + Coral.
- Filtrado (capacitancia) cerca de drivers/compute.
- Cableado y conectores robustos (cero protoboard suelta).

---

## 14) Reglas 2025: cambios y puntos “polémicos” (IA, herramientas, falsas víctimas)

### 14.1 Restricción de herramientas “demasiado mágicas”
El rules 2025 incluye una sección sobre herramientas de desarrollo:
- Se permiten herramientas propias o que no completan tareas por sí solas.
- Se prohíben herramientas no desarrolladas por el equipo que completen tareas y den ventaja sin desarrollo (ejemplos: line-following sensors, AI cameras, OCR libraries).

Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

**Lectura:** usar una cámara normal + software propio es razonable; usar un “módulo comercial” que ya te devuelve “línea” como servicio puede ser cuestionable.

### 14.2 “Víctimas falsas” y “luces intermitentes en EZ”
En el texto del rules 2025 revisado para este estudio:
- No aparece una mecánica explícita de “víctimas falsas”.
- No aparece una regla de penalización por evacuar falsas (porque no las define).
- No aparece una indicación oficial sobre “luces intermitentes en la zona de rescate” como elemento de scoring.

Esto no descarta que:
- existan **variantes locales**,  
- o que esos cambios estén discutiéndose en 2026 (hay borradores 2026 en foros),  
pero **no es parte del rules 2025 final** usado acá.

Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

---

## 15) SuperTeam Challenge: comunicación permitida y diseño mínimo viable

El rules 2025 aclara:
- SuperTeam existe como award separado; no afecta score individual.
- Recomiendan llevar comunicación inalámbrica.
- Comunicación: **2.4 GHz**, potencia ≤ **100 mW EIRP**.

Fuente: Rules 2025: https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

### Alternativas de comunicación (comparativa rápida)
- Wi‑Fi local (AP): alto throughput, pero congestión posible.
- BLE: simple, payload limitado.
- ESP‑NOW: rápido, directo, pero stack extra.

**Recomendación coach:** protocolo simple y robusto (handshake + estado + mensajes cortos), probado en ambiente ruidoso.

---

## 16) “Receta” de estrategia 2025 (práctica y medible)

### 16.1 Prioridad de ingeniería (orden recomendado)
1) Terminar pista lineal con **mínimos LOP**.
2) Manejar intersecciones verdes con alta tasa de acierto.
3) Resolver rampas y seesaw con estabilidad (no patinar, no volcar).
4) Entrar a EZ y rescatar con **plan** (visión + distancia + mecanismo).
5) Optimizar velocidad una vez que el éxito es alto.

### 16.2 Metas cuantitativas (para testeo)
- 90–95% de éxito en intersecciones y dead ends.
- 90% en gaps de 20 cm (en iluminación variable).
- 80–90% de éxito de pickup y depósito por víctima (en serie de 10 intentos).
- 0–1 LOP por run completo (ideal).

---

## 17) Fuentes (enlaces)

- RCJ Rescue Line Rules 2025 (final):  
  https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

- Awards oficiales RoboCup 2024 (Rescue Line):  
  https://rescue.rcj.cloud/events/2024/RoboCup2024/award

- Awards oficiales RoboCup 2025 (Rescue Line):  
  https://rescue.rcj.cloud/events/2025/RoboCup2025/award

- Overengineering² (campeón 2024) — repo público:  
  https://github.com/Overengineering-squared/Overengineering-squared-RoboCup

- Airborne (2025) — repo público (arquitectura + componentes + documentación):  
  https://github.com/JamesBond6873/Airborne_Rescue_Line_2025/

---

## 18) Historial de revisiones

- 2026-02-23 — v1.0 — Creación inicial (ChatGPT 5.2 a pedido de Gustavo Viollaz).
