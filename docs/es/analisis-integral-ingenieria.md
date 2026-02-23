# Analisis integral de ingenieria — IITA Salta RCJ 2026 Rescue Line

**Repositorio:** `IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup`
**Fecha de analisis:** 23 de febrero de 2026
**Analista:** Claude (a pedido de Gustavo Viollaz, Director del equipo)

---

## 1. Resumen ejecutivo

El equipo IITA Salta presenta un robot de doble procesador (Teensy 4.1 + Raspberry Pi 4B) para RoboCup Junior 2026 Rescue Line. El sistema demuestra un nivel de ambicion tecnica notable para la categoria: vision por computadora con YOLOv8, protocolo serial binario propio, cinematica diferencial con PID, y un mecanismo de garra con 5 servos. El equipo gano el campeonato nacional argentino en 2025, lo que valida la base de trabajo.

Sin embargo, el analisis detallado del codigo revela problemas estructurales importantes que, si no se resuelven antes de Incheon, pueden comprometer la confiabilidad del robot en competencia internacional. Los hallazgos principales son:

- **El firmware Teensy (main.cpp) es un monolito de ~700 lineas sin maquina de estados formal**, con logica de rescate hardcodeada por tiempos y angulos fijos, sin recuperacion de errores.
- **El programa de Raspberry (Main.py) mezcla toda la logica en un solo archivo de ~500 lineas**, con variables globales cruzadas entre estados y sin manejo robusto de excepciones.
- **El protocolo serial carece de checksums y acknowledgements**, lo que lo hace vulnerable a desincronizacion bajo ruido electrico — un escenario comun en competencia con motores DC.
- **La zona de rescate depende de secuencias temporales ciegas** (`runTime`) en lugar de feedback de sensores, lo que la hace fragil ante variaciones de bateria, superficie, y friccion.
- **Hay codigo duplicado significativo** entre `Main.py`, `rescatemodelonos.py`, y `tfmodelprueba.py`, lo que genera riesgo de divergencia.

El robot tiene una base solida. Las recomendaciones se priorizan segun impacto en competencia y factibilidad antes de Incheon.

---

## 2. Arquitectura del sistema

### 2.1 Diagrama de procesadores

```
┌─────────────────────┐     UART 115200      ┌──────────────────────┐
│   RASPBERRY PI 4B   │◄────────────────────►│    TEENSY 4.1         │
│   (8 GB RAM)        │   /dev/serial0        │                      │
│                     │   Serial5             │                      │
│  • OpenCV (vision)  │                      │  • 4x motores DC     │
│  • YOLOv8 (ONNX)   │   Protocolo:          │  • 5x servos (claw)  │
│  • Camara USB 2MP   │   [255,spd,254,ang,  │  • BNO055 (IMU)      │
│    WIDE 140°        │    253,gs,252,sl]     │  • 2x VL53L0X (ToF)  │
│                     │                      │  • 3x ultrasonicos   │
│  Estados:           │   RPi→Teensy: 8 bytes│  • APDS9960 (color)  │
│  esperando→linea→   │   Teensy→RPi: 1 byte │  • Encoders x4       │
│  rescate→depositar  │                      │                      │
└─────────────────────┘                      └──────────────────────┘
```

### 2.2 Evaluacion de la arquitectura

**Fortalezas:**
- La separacion de vision (RPi) y control (Teensy) es una decision acertada. La Teensy 4.1 a 600 MHz provee determinismo de control que la RPi no puede garantizar.
- La Raspberry Pi 4B con 8 GB es mas que suficiente para YOLOv8 en ONNX.
- La camara WIDE 140° es buena eleccion para seguimiento de linea y zona de rescate.

**Debilidades:**
- No hay segundo canal de comunicacion (ni I2C, ni SPI de respaldo). Si el UART falla, el robot queda completamente ciego.
- No existe mecanismo de watchdog bidireccional: si la RPi se congela, la Teensy no lo detecta (y viceversa).
- La Teensy no tiene logging persistente (ni SD card ni buffer circular), lo que dificulta el diagnostico post-competencia.

---

## 3. Analisis del firmware Teensy (main.cpp)

### 3.1 Estructura general

El archivo `main.cpp` tiene aproximadamente 700 lineas y concentra toda la logica del robot: inicializacion de hardware, lectura de sensores, maquina de estados implicita, rutinas de movimiento, y secuencias de rescate.

**Problema fundamental:** No existe una maquina de estados formal. La logica se controla mediante una variable `String rutina` ("linea" o "rescate") y `while` loops anidados dentro de `loop()`. Esto genera:

- Dificultad para agregar nuevos estados sin introducir bugs.
- Imposibilidad de hacer transiciones limpias entre estados.
- Codigo dificil de testear de forma aislada.

### 3.2 Hallazgos criticos en el firmware

**3.2.1 — Uso de `String` en lugar de enums**

```cpp
String rutina = "linea";
String wall = "right";
String lado_plateado = "";
String pared = "";
```

En un microcontrolador, `String` de Arduino causa fragmentacion de heap. Para un programa de competencia que corre continuamente, esto puede provocar crashes aleatorios despues de minutos de operacion. Deberia usarse `enum class` o al menos `const char*` con comparaciones `strcmp`.

**3.2.2 — Variables globales sin proteccion de concurrencia**

```cpp
double speed;
double steer;
int green_state = 0;
int silver_line = 0;
```

Estas variables se escriben en `serialEvent5()` (potencialmente desde interrupcion o polling) y se leen en `loop()`. No hay `volatile`, ni atomic reads, ni mutex. En Teensy 4.1, si `serialEvent5()` se ejecuta como polling (no ISR), el riesgo es menor, pero la practica es peligrosa y deberia documentarse explicitamente o corregirse.

**3.2.3 — Secuencias de rescate hardcodeadas por tiempo**

```cpp
// Ejemplo de secuencia ciega:
runTime(20, FORWARD, 0, 1500);
runTime(0, BACKWARD, 0, 1000);
runAngle(30, FORWARD, 45);
runTime(30, FORWARD, 0, 3000);
```

Estas secuencias asumen que el robot se mueve exactamente N milisegundos para recorrer X distancia. En competencia, esto falla porque:
- La bateria se descarga y la velocidad varia.
- La superficie cambia (alfombra vs. madera vs. vinilo).
- Los obstaculos y speed bumps alteran la trayectoria.

La funcion `runDistance()` existe y usa encoders, pero se usa poco. La recomendacion es migrar toda secuencia de rescate a `runDistance()` + `runAngle()`.

**3.2.4 — El caso `action = 1` (obstaculo frontal) usa random**

```cpp
RanNumber = random(1, 3);
if (RanNumber == 1) {
    runAngle(25, FORWARD, -95);
    // ...buscar linea a la izquierda
}
if (RanNumber == 2) {
    runAngle(25, FORWARD, 95);
    // ...buscar linea a la derecha
}
```

Elegir aleatoriamente a que lado esquivar un obstaculo es una estrategia de ultimo recurso. Los sensores ToF laterales ya estan disponibles y deberian usarse para decidir por que lado hay mas espacio. Esto es un cambio simple de alto impacto.

**3.2.5 — La funcion `runAngle` tiene logica duplicada y fragil**

La funcion intenta manejar angulos especificos (180, 90, -90, 45, -45) con cases especiales, pero el caso general (`else if (angle > 0)`) siempre gira a maximo steer=1 o -1, sin control proporcional. Esto causa overshooting. Un controlador P simple (`steer = constrain(Kp * error, -1, 1)`) seria mas robusto y eliminaria todos los cases especiales.

**3.2.6 — Inconsistencia en pines de servos**

En `main.cpp`:
```cpp
DFServo sort(23, ...);
DFServo deposit(12, ...);
```

En `test/actuators/clawLibTest.cpp`:
```cpp
DFServo sort(12, ...);
DFServo deposit(23, ...);
```

Los pines de `sort` y `deposit` estan invertidos entre el programa principal y el test. Esto indica que el test no refleja el hardware actual, lo que lo invalida como herramienta de diagnostico.

**3.2.7 — La salida de zona de rescate no esta implementada**

El backlog confirma: "Salida de la zona de rescate de manera correcta — tenemos una base pero no funciona con los obstaculos". En el codigo, `veces_deposit == 2` dispara una secuencia de alineacion con pared, pero no hay logica para encontrar la cinta negra de salida. Esto es un gap critico para puntaje.

### 3.3 Tabla de acciones del firmware

| action | Trigger | Comportamiento | Riesgo |
|--------|---------|---------------|--------|
| 1 | Obstaculo frontal (<12 cm) | Esquiva aleatoria izq/der | No usa ToF laterales |
| 2 | silver_line == 1 | Entra a rescate | Secuencia ciega por tiempo |
| 5 | green_state == 2 | Giro derecha (verde) | Angulo fijo 60° |
| 6 | green_state == 1 | Giro izquierda (verde) | Angulo fijo 60° |
| 7 | green_state == 0 | Seguimiento de linea | Funciona |
| 12 | green_state == 14 | Alineacion y espera RPi | Implementacion parcial |
| 14 | green_state == 3 | Media vuelta (doble verde) | Angulo fijo 180° |

---

## 4. Analisis del software Raspberry Pi (Main.py)

### 4.1 Estructura general

`Main.py` es un archivo de ~500 lineas que implementa todo: seguimiento de linea por vision clasica, deteccion YOLO para rescate, maquina de estados, comunicacion serial, y threading. La funcion `modo_rescate()` es una mega-funcion de ~300 lineas con clases, threads, y toda la logica de rescate adentro.

### 4.2 Hallazgos criticos

**4.2.1 — Toda la logica en un solo archivo**

El archivo mezcla responsabilidades que deberian estar separadas:
- Estado machine → modulo propio
- Vision de linea → modulo propio
- Comunicacion serial → modulo propio
- YOLO + tracking → modulo propio

Esto hace que cualquier cambio requiera entender las 500 lineas completas y que dos personas no puedan trabajar en paralelo sin conflictos de merge.

**4.2.2 — Variables globales cruzadas entre estados**

```python
estado = 'esperando'  # global
silver_line = False    # global, modificada en linea, leida en rescate
```

La variable `estado` se modifica tanto en el loop principal como dentro de `modo_rescate()` y dentro de `serial_monitor_local()`. Esta comparticion sin locks es una race condition esperando a ocurrir, especialmente con los threads de rescate.

**4.2.3 — No hay manejo de excepciones en serial**

```python
ser.write(output)  # sin try/except
```

Si la Teensy se desconecta o el buffer se llena, `ser.write()` puede lanzar una excepcion que mata el programa entero. En competencia, esto significa parada total del robot.

**4.2.4 — Thresholds de color hardcodeados**

```python
lower_black = np.array([0, 0, 0])
upper_black = np.array([90, 90, 90])
lower_green = np.array([120, 90, 100])
upper_green = np.array([170, 120, 140])
```

Estos valores funcionan en un entorno especifico de iluminacion. En competencia internacional, la iluminacion sera diferente. No existe un sistema de calibracion automatica ni adaptativa. El backlog confirma esta preocupacion.

**4.2.5 — La resolucion de vision es extremadamente baja**

```python
width, height = 160, 120
```

A 160x120, cada pixel cubre una porcion significativa del campo visual. Esto limita la precision angular del seguidor de linea y la deteccion de cuadrados verdes. Los equipos internacionales de alto nivel suelen usar 320x240 o superior.

**4.2.6 — El calculo del angulo de linea es simplista**

```python
x_resultant = np.mean(x_black)
y_resultant = np.mean(y_black)
angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90
```

Se calcula un centroide ponderado de todos los pixeles negros, lo que funciona para lineas rectas pero tiene problemas en intersecciones, curvas cerradas, y cuando hay ruido (sombras). No se usan tecnicas como look-ahead a multiples ROIs, segmentacion por contornos, o analisis de la curvatura.

**4.2.7 — La deteccion de plata es fragil**

```python
lower_silver_hsv = np.array([79, 16, 46])
upper_silver_hsv = np.array([168, 28, 79])
```

Los nombres sugieren HSV pero los valores se aplican como BGR (`cv2.inRange(frame_resized, ...)`). Esto es confuso y potencialmente incorrecto. Ademas, el threshold de area para detectar plata es apenas 50 pixeles, lo que da falsos positivos.

### 4.3 Pipeline de vision de linea — flujo

```
Camara (160x120) → rotate 180° → resize →
  ├── Mascara negra (BGR) → centroide ponderado → angulo
  ├── Mascara verde (LAB) → deteccion cuadrados → green_state
  ├── Mascara roja (HSV) → deteccion linea roja → green_state=10
  └── Mascara plata (BGR) → deteccion entrada rescate → silver_line=1
→ Serial: [255, speed, 254, angle+90, 253, green_state, 252, silver_line]
```

### 4.4 Pipeline de rescate YOLO — flujo

```
Camara → Thread captura → Queue →
  Thread inferencia (YOLO ONNX 256x256) → Queue →
  Main loop:
    ├── Detecciones → MOSSE tracker / CentroidTracker
    ├── Seleccion de target → control proporcional simple
    └── Serial: [255, speed, 254, angle+90, 253, green_state, 252, 0]
```

El pipeline multihilo es buena ingenieria. La separacion captura/inferencia/control maximiza throughput.

---

## 5. Protocolo de comunicacion

### 5.1 Formato actual

**RPi → Teensy (8 bytes):**
```
[255] [speed] [254] [angle] [253] [green_state] [252] [silver_line]
```

**Teensy → RPi (1 byte):**
```
0xF9 (249) = startup listo
0xF8 (248) = pelotas suficientes
0xFF (255) = switch apagado
```

### 5.2 Vulnerabilidades del protocolo

**Sin checksum ni CRC:** Si un byte se corrompe por ruido electromagnetico de los motores, el parser se desincroniza. Por ejemplo, si se pierde el marcador 255, el siguiente dato de speed se interpreta como marcador, y toda la trama se desplaza. No hay mecanismo de recuperacion.

**Sin acknowledgement:** La RPi envia comandos fire-and-forget. Si la Teensy esta ocupada en `runTime()` (que es blocking), los bytes se acumulan en el buffer serial y se procesan en batch al salir, con datos obsoletos.

**Los marcadores son valores validos de datos:** El speed puede ser 252 o 253, que colisionan con los marcadores de green_state y silver_line. En la implementacion, `serialEvent5()` asume que si `data >= 252`, es un marcador. Pero si el speed real fuera 252, se interpretaria como marcador de silver_line. Esto limita artificialmente el rango del speed al rango 0-251.

**Recomendacion:** Agregar un byte de checksum (XOR de los datos) y usar marcadores fuera del rango valido de datos (o escapar los marcadores con un byte de escape).

---

## 6. Sistema de IA y vision

### 6.1 Modelo YOLO

- Modelo: `zonasdepositoalta.onnx` (YOLOv8, FP32)
- Runtime: ONNX Runtime en CPU (sin acelerador)
- Entrada: 256x256
- Clases: negro (pelota), plateado (pelota), rojo alto (zona), verde alto (zona)
- Inferencia: cada frame (`DETECT_EVERY = 1`)

**Evaluacion:** La decision de FP32 sobre INT8 es conservadora pero razonable dado que reportaron perdida de precision en cuantizacion. El tamano de entrada 256x256 es un buen balance para Raspberry Pi. ONNX Runtime es la mejor opcion para ARM sin NPU segun los benchmarks que el equipo recopilo.

### 6.2 Preocupaciones del modelo

- **No hay augmentations para iluminacion variable en el dataset de entrenamiento** (pendiente en backlog).
- **Las clases del modelo en Main.py y en rescatemodelonos.py son diferentes:** Main.py usa 4 clases (negro, plateado, rojo alto, verde_alto) mientras que el test file usa 6 clases (boxgreen, boxred, negro, plateado, rojo alto, verde alto). Esto indica que el modelo cambio pero no todos los archivos se actualizaron.
- **No hay validacion de que el modelo cargo correctamente.** Si el path del modelo es incorrecto, la excepcion no se captura y el robot falla silenciosamente.
- **FPS no esta documentado en condiciones de competencia.** Los benchmarks son externos. El equipo necesita medir FPS reales con el modelo actual, la camara actual, y la resolucion actual.

### 6.3 Tracking

Se usa MOSSE (OpenCV contrib) como tracker primario y un CentroidTracker custom como fallback. MOSSE es extremadamente rapido pero fragil ante cambios bruscos de escala o oclusiones. El CentroidTracker implementado es basico pero funcional.

**Preocupacion:** La funcion `choose_stable_target()` selecciona el target mas cercano al ultimo conocido, pero no considera la clase. Si una pelota plateada pasa cerca de una negra, el tracker puede "saltar" entre targets de diferente clase.

---

## 7. Librerias custom (Teensy)

### 7.1 DriveBase

La clase `DriveBase` implementa steering diferencial con PID por motor. El PID usa solo Ki=22 (sin Kp ni Kd), lo que es esencialmente un controlador integral puro. Esto puede funcionar para velocidades bajas pero tendra problemas de overshoot y oscilacion a velocidades altas.

La funcion `steer()` calcula velocidades izquierda y derecha a partir de speed y rotation:
- `rotation = 0`: ambos lados iguales
- `rotation = 1`: izquierda atras, derecha adelante (giro en el lugar)
- `rotation = -1`: derecha atras, izquierda adelante

### 7.2 Claw

La clase `Claw` controla 5 servos: lift, left, right, sort, deposit. Las funciones `open()`, `close()`, `lift()`, `lower()` mueven los servos a posiciones hardcodeadas. Los angulos estan definidos en el .cpp con valores como `120`, `90`, `20`, etc. No hay feedback de posicion ni deteccion de atasco.

---

## 8. Calidad de codigo y practicas de ingenieria

### 8.1 Aspectos positivos

- **Documentacion existente y bilingue.** Los docs en `docs/es/` son buenos: protocolo serial, librerias, pipeline YOLO. El workflow de traduccion automatica es un plus.
- **Estructura de repositorio ICRS.** Sigue un estandar con carpetas de docs, software, hardware, testing, journal.
- **Tests de hardware separados.** La carpeta `test/` tiene scripts para cada sensor y actuador, lo que facilita diagnostico.
- **Backlog documentado.** `pendientes_generales.md` tiene pendientes claros con criterios de exito.
- **PlatformIO para el firmware.** Buena eleccion sobre Arduino IDE.
- **Requirements.txt para Raspberry.** Las dependencias estan documentadas.

### 8.2 Problemas de calidad

| Problema | Severidad | Ubicacion |
|----------|-----------|-----------|
| Sin type hints en Python | Baja | Main.py |
| Codigo comentado sin eliminar (dead code) | Media | main.cpp, Main.py |
| Prints de debug en produccion | Media | Main.py (multiples `print()`) |
| Sin logging formal (solo `print()`) | Media | Ambos |
| Magic numbers sin constantes | Alta | main.cpp (12, 0.7, 55, 3000, etc.) |
| Sin manejo de excepciones en serial | Alta | Main.py |
| Duplicacion masiva de codigo de rescate | Alta | Main.py, rescatemodelonos.py, tfmodelprueba.py |
| Variables globales compartidas entre threads | Alta | Main.py |
| Uso de `String` en firmware embedded | Alta | main.cpp |

### 8.3 Git y workflow

El repo tiene 4 issues abiertos y 6 PRs abiertos, lo que sugiere uso activo de GitHub Flow. El CONTRIBUTING.md define Conventional Commits, branches por tipo, y declaracion de uso de IA. La migracion desde un repo anterior esta documentada.

---

## 9. Analisis competitivo para RoboCup 2026

### 9.1 Capacidades vs. requerimientos del reglamento

| Requerimiento | Estado | Notas |
|--------------|--------|-------|
| Seguir linea negra | ✅ Funcional | Resolucion baja (160x120) limita precision |
| Detectar cuadrados verdes | ✅ Funcional | Deteccion por color en LAB |
| Giro en cuadrado verde simple | ✅ Funcional | Angulo fijo 60° |
| Doble verde (media vuelta) | ✅ Funcional | Usa runAngle(180) |
| Evitar obstaculos | ⚠️ Parcial | Solo ultrasonico frontal, esquiva aleatoria |
| Curvas cerradas (135°) | ⚠️ En desarrollo | Pendiente en backlog, sistema re-enganche disenado |
| Pendientes inclinadas | ⚠️ Parcial | Ajusta velocidad por pitch, sin control de traccion |
| Linea roja (senal) | ✅ Detecta | Envia green_state=10, Teensy no procesa |
| Entrada a rescate (plata) | ✅ Funcional | Deteccion por color + contorno |
| Detectar pelotas (YOLO) | ✅ Funcional | 4 clases, ONNX en CPU |
| Recoger pelotas | ✅ Funcional | Claw con 5 servos |
| Distinguir viva/muerta | ✅ Funcional | Plateada vs. negra por vision |
| Depositar en zona correcta | ⚠️ Parcial | Deteccion de zonas funciona, logica de deposito basica |
| Salida de zona de rescate | ❌ No funciona | Reconocido en backlog como no resuelto |
| Ignorar victimas falsas | ⚠️ No claro | El modelo deberia filtrarlas, pero no hay evidencia de entrenamiento con falsas |

### 9.2 Gaps criticos para competencia internacional

1. **Salida de zona de rescate.** Sin esto, el robot pierde todos los puntos de "rescue" si no puede continuar el recorrido.
2. **Robustez ante iluminacion variable.** Los equipos internacionales usan White Balance automatico o calibracion on-the-fly. Los thresholds fijos fallaran.
3. **Speed bumps en zona de rescate.** No hay manejo especifico.
4. **Linternas/LEDs intermitentes en zona de rescate.** El modelo YOLO no esta entrenado para esto.
5. **Gaps en la linea.** No hay logica de re-enganche implementada (solo disenada en backlog).

---

## 10. Recomendaciones priorizadas

### Prioridad 1 — CRITICO (antes de Incheon, minimo viable)

**R1. Implementar salida de zona de rescate.**
Despues de depositar, usar ultrasonidos + IMU para wall-following hasta encontrar la cinta negra (detectable por el sensor APDS9960 de color, que ya esta montado). Esto desbloquea puntos significativos.

**R2. Agregar checksum al protocolo serial.**
Un byte XOR al final de la trama. Si no coincide, descartar el frame. Esto toma ~1 hora de implementacion y previene crashes por desincronizacion.

**R3. Reemplazar `String` por `enum` en el firmware.**
Cambiar `String rutina` por `enum class Rutina { LINEA, RESCATE }` y lo mismo para `wall`, `pared`, `lado_plateado`. Esto elimina riesgo de fragmentacion de heap.

**R4. Agregar try/except en toda la comunicacion serial de la RPi.**
```python
try:
    ser.write(output)
except serial.SerialException:
    # intentar reconectar o continuar sin serial
```

**R5. Usar los ToF laterales para decidir direccion de esquiva de obstaculo** en lugar de `random()`.

### Prioridad 2 — IMPORTANTE (mejora significativa de rendimiento)

**R6. Migrar secuencias de rescate de `runTime()` a `runDistance()` + `runAngle()`.**
Las funciones ya existen. Esto hace que el comportamiento sea independiente del nivel de bateria.

**R7. Implementar `runAngle()` con control proporcional** en lugar de steer binario ±1.
```cpp
float steer = constrain(Kp * error, -1.0, 1.0);
robot.steer(speed, FORWARD, steer);
```

**R8. Agregar calibracion de color semi-automatica.**
Al arrancar, capturar N frames del suelo y calcular thresholds de negro adaptativos. Esto se puede hacer en los primeros segundos de la fase "esperando".

**R9. Implementar watchdog bidireccional.**
La Teensy envia heartbeat cada 500ms. Si la RPi no responde en 2s, la Teensy asume fallo de vision y entra en modo degradado (wall-following con sensores).

**R10. Subir resolucion de vision a 320x240** para linea. El overhead de procesamiento es ~4x pero la RPi 4B con 8GB puede manejarlo, y la precision angular mejora sustancialmente.

### Prioridad 3 — RECOMENDADO (mejora de calidad y mantenibilidad)

**R11. Refactorizar Main.py en modulos.**
- `state_machine.py` — transiciones de estados
- `line_follower.py` — vision de linea
- `rescue_vision.py` — YOLO + tracking
- `serial_comm.py` — comunicacion con Teensy
- `main.py` — orquestacion

**R12. Implementar maquina de estados formal en el firmware.**
```cpp
enum class State { LINE, RESCUE_ENTER, RESCUE_COLLECT, RESCUE_DEPOSIT, RESCUE_EXIT };
State currentState = State::LINE;
void loop() {
    readSensors();
    switch(currentState) { ... }
    actuate();
}
```

**R13. Unificar el codigo de rescate.** `rescatemodelonos.py` y `tfmodelprueba.py` deberian ser variantes parametrizadas del mismo codigo, no copias divergentes.

**R14. Agregar logging con timestamps** a un archivo en la RPi para analisis post-competencia.

**R15. Documentar el PID de los motores.** Ki=22 sin Kp ni Kd es inusual. Si funciona, documentar por que. Si no se ha tuneado, hacer un tuning formal con step response.

---

## 11. Resumen de riesgos para Incheon

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|-----------|
| Desincronizacion serial por ruido de motores | Alta | Alto | R2 (checksum) |
| Crash por fragmentacion de heap en Teensy | Media | Alto | R3 (eliminar String) |
| Fallo de vision por iluminacion diferente | Alta | Alto | R8 (calibracion) |
| No poder salir de zona de rescate | Certeza | Alto | R1 (implementar salida) |
| Secuencias de rescate fallan por bateria baja | Alta | Medio | R6 (usar encoders) |
| Crash de Main.py por excepcion serial | Media | Alto | R4 (try/except) |
| Modelo YOLO confundido por linternas LED | Media | Medio | Augmentations en dataset |
| RPi se congela, Teensy no lo detecta | Baja | Alto | R9 (watchdog) |

---

## 12. Conclusion

El equipo IITA Salta tiene un robot con fundamentos solidos: buena arquitectura de procesadores, librerias propias funcionales, vision con deep learning, y documentacion por encima del promedio para la categoria. El campeonato nacional de 2025 valida que el sistema base funciona.

Para competir a nivel internacional en Incheon, el foco debe estar en **confiabilidad, no en features nuevos**. Las recomendaciones R1 a R5 (salida de rescate, checksum serial, eliminar String, try/except, y uso de ToF para obstaculos) son cambios acotados que reducen dramaticamente los modos de fallo mas probables.

El mayor riesgo tecnico es la **fragilidad ante condiciones de competencia diferentes a las de entrenamiento**: iluminacion, superficies, nivel de bateria, y ruido electromagnetico. Cada hora invertida en robustez (calibracion adaptativa, watchdogs, fallbacks) vale mas que una hora invertida en features nuevos.

---

*Documento generado por Claude (Anthropic) como analisis de ingenieria del repositorio del equipo IITA Salta para RoboCup Junior 2026 Rescue Line. Solicitado y supervisado por Gustavo Viollaz.*