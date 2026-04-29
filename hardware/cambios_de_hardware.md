# LED 12V para Sensor de Color (APDS9960)
## Detección de Línea Negra de Salida


---

## 1. EL PROBLEMA

**Situación actual:**
- Robot en fase `evacuacion` espera que la **cámara Raspberry** detecte la línea **negra de salida** 
- La RPi debe procesar detección de víctimas (YOLO) Y detectar línea negra simultáneamente
- Linterna intermitente del torneo + luz ambiental = **variabilidad de luz incontrolable**
- Resultado: Falsos positivos, robot desorientado

**Línea de código crítica (main.cpp, línea 745):**
```cpp
while (rutina == "evacuacion" && digitalRead(32) == 0) {
    serialEvent5();  // Espera comando de cámara
    if(green_state==12) {
        rutina="linea";  // Salida detectada ← depende 100% de RPi
    }
}
```

---
### Opción A — Detección por cámara (método anterior)

La cámara detectaría la línea negra de salida por área de píxeles negros
en la parte inferior del frame, enviando `green_state=12` a la Teensy
por serial cuando el área supera un umbral.

**Por qué falló en la práctica:**

El reglamento 2026 agregó en la sección 3.9 una regla nueva:

> *"The organizers may place white LED lights, mounted perpendicular to
> the wall, on the upper part of the walls."*

Esto significa que hay una **linterna intermitente oficial** dentro de
la zona de evacuación. Cada destello cambia los valores RGB del frame
completo, haciendo que áreas que eran negras pasen a ser grises o
blancas por un frame, y viceversa. El resultado son falsos positivos
constantes: el robot cree que detectó la salida cuando en realidad
era un destello de luz sobre el piso blanco.

Problemas confirmados en pruebas reales:

| Problema | Causa |
|---|---|
| Falso positivo de línea negra | Sombra del robot sobre el piso blanco |
| Falso positivo de línea negra | Destello de linterna sobre objeto oscuro |
| Falso negativo | Linterna ilumina la línea justo cuando el robot pasa |
| Latencia | RPi procesa YOLO + detección de línea simultáneamente → frames perdidos |


## 2. Opción B — LED 12V + APDS9960 (solución elegida)

**Agregar un LED 12V** junto al sensor APDS9960 (ya montado en parte inferior trasera):

```cpp
// Lo que queremos lograr (3 líneas nuevas en loop):
while (rutina == "evacuacion" && digitalRead(32) == 0) {
    digitalWrite(RELAY, HIGH);  // LED enciende (relay ya existe)
    color_detected = get_color();  // ← Leer sensor directamente
    if (color_detected == "Negro") {
        green_state = 12;  // ← Ejecutar accion de salida
        rutina = "linea";
    }
}
```

**Por qué funciona:**
- Sensor en **parte inferior está aislado** de luz ambiente directa
- LED 12V proporciona iluminación **constante y controlada**
- APDS9960 lee reflexión predecible: Negro (C bajo) vs Blanco (C alto)
- **Cero latencia:** Detección en Teensy, no depende de RPi
- **Libera cámara:** RPi enfocada 100% en detección de víctimas (verde/rojo)

En caso de error podemos aplicar varias soluciones con el led de 12V una de ellas es aprovechar el on/off del rele y tambien el IR del sensor  ya que el blanco y plateado en RGB no se van a diferenciar tanto en cambio el blanco en un IR se dispersa en todas las direcciones, el plateado rebota concentradamente como un espejo.

**Solución :** Usar el APDS9960 como **sensor de reflectancia**, no de color:
- **Principal:** Canal C (Clear) = luminancia total
- **Secundario:** readProximity() = sensor IR que mide reflectancia
- **Terciario:** RGB normalizado = solo confirmar que no es color cromático

### Canal C (Clear) — Principal
El canal C es la luminancia total sin filtro de color. Es el indicador más directo de reflectancia:

| Superficie | Canal C |
|---|---|
| Negro | Muy bajo → absorbe casi toda la luz |
| Blanco | Medio-alto → reflexión difusa |
| Plateado | Alto e inestable → reflexión especular |

```cpp
if (c < white_reference_clear * COLOR_BLACK_CLEAR_RATIO) return "Negro";
```

### readProximity() — Secundario
El sensor emite IR y mide cuánto rebota. Aquí aparece la diferencia física entre blanco y plateado:

- **Blanco** → reflexión difusa, el IR se dispersa → PDATA moderado
- **Plateado** → reflexión especular (efecto espejo), el IR rebota concentrado hacia el sensor → PDATA alto

```cpp
if (neutro && c > white_reference_clear * COLOR_SILVER_CLEAR_RATIO
           && p > white_reference_prox  * COLOR_SILVER_PROX_RATIO) return "Plateado";
```

### RGB Normalizado — Terciario
Solo confirma que la superficie no tiene color cromático antes de clasificar 
como blanco o plateado:

```cpp
float rn = (float)r / c;
float gn = (float)g / c;
float bn = (float)b / c;
int delta = max(rn, max(gn, bn)) - min(rn, min(gn, bn));
bool neutro = delta < COLOR_NEUTRAL_SPREAD_MAX;
```

`delta` es la diferencia entre el canal más alto y el más bajo. 
Mide qué tan equilibrados están R, G y B entre sí:

| Superficie | rn / gn / bn | delta | Resultado |
|---|---|---|---|
| Blanco | 0.33 / 0.34 / 0.33 | 0.01 | neutro ✅ |
| Verde | 0.15 / 0.60 / 0.25 | 0.45 | tiene color ❌ |

- `neutro = true` → los tres canales están equilibrados → puede ser blanco o plateado  
- `neutro = false` → algún canal domina → tiene color propio (verde, rojo), se descarta

Solo cuando `neutro == true` se evalúan C y PDATA para decidir entre negro, blanco y plateado


Quedando asi el setup
```cpp
apds.begin(10, APDS9960_AGAIN_1X);  // Ganancia baja (1X)
apds.enableColor(true);
apds.enableProximity(true);         // Habilitar IR
```
Aclaracion la ganancia es muy importante por defecto antes nosotros usabamos el codigo de libreria basico que ponia asi
```cpp
    if (!apds.begin())
    {
        //Serial.println("failed to initialize device! Please check your wiring.");
    }
    else
        //Serial.println("Device initialized!");

    // enable color sensign mode
    apds.enableColor(true);
```
Estabamos pasandole los parametros por defecto que en la libreria nos dicen que son estos 
```cpp

boolean begin(uint16_t iTimeMS = 10, apds9960AGain_t = APDS9960_AGAIN_4X,
              uint8_t addr = APDS9960_ADDRESS, TwoWire *theWire = &Wire);
                              ↑
                    DEFAULT: APDS9960_AGAIN_4X
```

Al tener la ganancia en 4 es como si el sensor reaccionara mucho mas de lo que deberia esto va a fallar mucho en nuestro codigo cuando le implementemos el Led de 12V debido a que puede tomar la reflectancia del blanco y plateado de la misma manera gracias a la ganancia y no habria diferencia


## 4. ESPECIFICACIÓN

**Hardware:**
- LED 12V blanco 
- Conectado a rele existente (ya controlado por la Teensy)
- Ubicación: Junto a sensor APDS9960 en parte inferior 

**Código:**
- Función `get_color()` ya existe 
- APDS9960 ya inicializado 
- Relay ya controlado
- **Agregar:** 3-4 líneas en loop `evacuacion`



---

## 5. PROS Y CONTRAS

**✅ VENTAJAS:**
- Detección autónoma (sin dependencia de cámara)
- Aislada de luz ambiente (ubicación inferior)
- Iluminación controlada (LED 12V constante)
- Código simple (3-4 líneas)
- Hardware existente (relay + sensor ya montado)
- Libera RPi para tareas complejas


**❌ DESVENTAJAS:**
- Soporte 3D requerido para montar el LED
- Soldado o conexionado adicional

Esta es en mi opinion otra mejora prioritaria aunque requiere agregar un soporte 3D y montar un LED adicional, el beneficio en confiabilidad justifica completamente el cambio.La utilidad principal es asegurar una salida consistente de evacuación sin depender de condiciones externas imposibles de controlar.
# ESP32 Super Mini — Implementación SuperTeam Challenge

## 1. EL PROBLEMA

El reglamento 2026 indica en la sección 6.3:

> *"It is highly recommended that teams bring some kind of communication hardware
or think about a communication mechanism for this challenge."*

El robot actualmente **no tiene ningún mecanismo de comunicación** entre equipos.
Para el SuperTeam Challenge se necesita coordinar acciones entre dos robots de equipos distintos en tiempo real.

## 2. LA SOLUCIÓN

**Agregar una ESP32 Super Mini** conectada a la Teensy vía Serial8 (pines 34/35):

```cpp
// Comunicación Teensy ↔ ESP32
// Serial8 RX → pin 34  (antes: BUZZER)
// Serial8 TX → pin 35  (antes: LED_ROJO)
```

La ESP32 actúa como módulo BLE dedicado: recibe comandos de la Teensy por serial y los transmite al robot del otro equipo, y viceversa.

**Por qué ESP32 Super Mini:**
- Tamaño reducido → cabe en espacio limitado dentro del robot
- BLE nativo → sin hardware adicional para comunicación
- MicroPython ya conocido por el equipo → curva de aprendizaje mínima
- Bajo consumo → no impacta la alimentación del robot
## 3. CAMBIOS REQUERIDOS

### Software —  (2 líneas)
Todo el código usa los defines `BUZZER` y `LED_ROJO`, nunca los números de pin 
directamente. El compilador resuelve el resto solo:

```cpp
// Antes
#define BUZZER   35
#define LED_ROJO 34

// Después
#define BUZZER   31
#define LED_ROJO 30
```

### Hardware — 

| Tarea | Detalle |
|---|---|
| Desconectar BUZZER | desoldar cable del pin 35, reconectar al pin 31 |
| Desconectar LED_ROJO | desoldar cable del pin 34, reconectar al pin 30 |
| Conectar ESP32 | Pin 34 (RX8) y pin 35 (TX8) de la Teensy → UART de la ESP32 |
| Soporte 3D | Diseñar e imprimir soporte interno para montar la ESP32 |

Esto implica **desarmar el robot**, soldar cables y volver a armarlo.

---


### Alimentación
La ESP32 Super Mini se alimenta directamente desde el regulador de 5V del robot:

- **VIN de la ESP32** → 5V del regulador existente
- **GND** → GND común del robot

Sin componentes adicionales, sin regulador extra.

## 5. PROS Y CONTRAS

**✅ VENTAJAS:**
- Cumple el requerimiento de comunicación del SuperTeam Challenge
- Tamaño compacto (ESP32 Super Mini)
- MicroPython ya conocido por el equipo
- BLE integrado, sin módulos externos adicionales
- Cambio de código mínimo (solo 2 líneas)

**❌ DESVENTAJAS:**
- Requiere desarmar el robot para reconectar BUZZER y LED_ROJO
- Espacio interno limitado → requiere diseño 3D eficiente para el soporte

Asi quedaria el esquematico con la implementacion de la ESP32 para el superTeam

<img width="2000" height="1416" alt="descargar (1)-1" src="https://github.com/user-attachments/assets/368406a8-60e1-4fdb-89b7-d0d1ab1fe2d3" />



## 4. ANÁLISIS COMPARATIVO DE OPCIONES

Antes de elegir la ESP32 Super Mini se evaluaron otras opciones:

### HC-05 — Análisis detallado

#### Especificaciones técnicas
| Parámetro | Valor |
|---|---|
| Bluetooth | v2.0 + EDR |
| Frecuencia | 2.4 GHz ISM |
| Rango | hasta 100m |
| Baud rate data mode | 9600 bps por defecto |
| Baud rate AT mode | 38400 bps |
| Pines | 6 (EN, VCC, GND, TX, RX, STATE) |
| Roles | Maestro o Esclavo (configurable) |

#### Modos de operación

**Data Mode** (por defecto al encender):
- El módulo actúa como puente serial transparente
- Todo lo que entra por TX sale por Bluetooth y viceversa

**AT Command Mode** (para configurar):
- Se activa manteniendo el pin EN/KEY en HIGH al encender
- LED: parpadeo lento (~1 vez por segundo)
- Baud rate en este modo: 38400 bps
#### Proceso de configuración maestro-esclavo

Para conectar dos HC-05 entre dos robots se necesita hacer esto
**antes** del challenge:

**Paso 1 — Configurar el esclavo:**
- AT+ROLE=0          → modo esclavo
- AT+NAME=ROBOT_B    → nombre identificable
- AT+PSWD=1234       → contraseña
- AT+UART=115200,0,0 → baud rate
- AT+ADDR?           → obtener la MAC address del esclavo (formato: 1234:56:ABCDEF)


**Paso 2 — Configurar el maestro:**
AT+ROLE=1                    → modo maestro
AT+CMODE=0                   → conectar a dirección fija
AT+BIND=1234,56,ABCDEF       → MAC del esclavo (: reemplazado por ,)
AT+UART=115200,0,0           → mismo baud rate que esclavo

**Paso 3 — Verificar:**
- Apagar ambos módulos
- Encender primero el esclavo, luego el maestro
- El maestro busca y conecta automáticamente al esclavo
- Ambos LEDs pasan a doble parpadeo = conectados

#### El problema crítico para el SuperTeam Challenge

El proceso anterior tiene un supuesto fatal: **necesitás tener físicamente
el módulo del otro equipo para obtener su MAC address antes del challenge.**

En la competencia esto no es posible porque:
- Los equipos se asignan al momento del challenge
- No hay tiempo de configuración entre equipos
- Si el otro equipo trae HC-06 (solo esclavo), es imposible conectar
  dos HC-06 entre sí ya que ambos esperan que el otro inicie la conexión
- Si el otro equipo trae HC-05 pero con distinta versión de firmware,
  algunos comandos AT pueden no funcionar igual

Existe `AT+CMODE=1` que conecta al primer dispositivo disponible sin
necesitar la MAC, pero en una sala de torneo con múltiples equipos con
Bluetooth encendido, el maestro puede conectarse al robot equivocado.

#### Problema adicional: roles fijos durante la ejecución

En el SuperTeam Challenge la comunicación no es unidireccional.
Dependiendo de la tarea, un robot puede necesitar:
- **enviar** una señal al otro ("llegué al checkpoint")
- **recibir** una orden del otro ("esperame antes de continuar")

Con HC-05 los roles maestro y esclavo son **fijos en hardware**:
no se pueden intercambiar en tiempo de ejecución sin entrar al modo AT,
enviar comandos y reiniciar el módulo. Esto hace imposible que ambos
robots reaccionen dinámicamente según la situación.

Con la ESP32 en BLE, ambos robots pueden **transmitir y recibir
simultáneamente** sin cambiar de rol, ya que el broadcast es
independiente de quién inició la conexión.

### HC-06

- **Solo esclavo** — no puede iniciar conexiones, solo espera que otro
  dispositivo se conecte
- Dos HC-06 **no pueden comunicarse entre sí** bajo ninguna circunstancia
- Comandos AT muy limitados: solo permite cambiar nombre, baud rate y PIN
- Los comandos AT deben enviarse en menos de 1 segundo o el módulo no
  los reconoce
- **Descartado:** no sirve para robot-a-robot sin saber qué trae el otro equipo
### Por qué el broadcast de BLE es la clave

Con HC-05 o HC-06 la comunicación es como una llamada telefónica:
necesitás saber el número del otro antes de llamar, y solo uno puede
llamar mientras el otro espera. Con el BLE broadcast de la ESP32 es
como una radio: cualquiera transmite cuando necesita y cualquiera que
esté escuchando recibe, sin importar quién es el otro equipo ni qué
hardware trae.

Dado que el SuperTeam Challenge asigna equipos al momento de la
competencia, el broadcast elimina completamente la dependencia del
hardware del otro equipo y permite comunicación bidireccional dinámica.

Considero que la incorporación de una ESP32 Super Mini es una de las soluciones prioritarias ya que resuelve directamente el problema real de comunicación entre robots sin depender del hardware del otro equipo.
Las opciones como HC-05 o HC-06 presentan demasiadas limitaciones prácticas para una competencia donde los equipos se asignan en el momento. Tener que conocer previamente la MAC address del otro robot o depender de roles maestro/esclavo fijos introduce un riesgo innecesario que puede hacer fallar toda la prueba incluso antes de comenzar Aunque es necesario desarmar al robot para incorporar la mejora el beneficio para mi es mucho mayor

# Finales de Carrera — Mejora de Alineación y Retroceso

---

## 1. EL PROBLEMA

En la fase de rescate y evacuación el robot necesita:

**A) Alinearse contra la pared para depositar víctimas:**
```cpp
runAngle(20, FORWARD, 180);
runTime(10, BACKWARD, 0, 2000);  // ← retrocede por tiempo fijo
```
El problema es que retroceder por tiempo no garantiza la misma
distancia final. Según la distancia donde recogio su ultima victima el robot 
puede quedar más cerca o más lejos de la pared, lo que afecta
directamente la precisión del depósito. En caso de que nos quedemos corto de distancia nosotros aumentabamos los milisegundo de retroceso y con eso bastaba 

**B) Saber cuándo el robot está bien alineado:**
Actualmente se usa el BNO055 para girar 180° y retroceder, pero
el ángulo no garantiza que ambos lados del robot estén a la misma
distancia de la pared. Si el robot queda levemente torcido es perjudicial cuando navegamos a ciegas con los 3 ultrasonidos

---

## 2. OPCIONES EVALUADAS

### Opción A — Usar pitch del BNO055 (sin cambio de hardware)

El BNO055 ya tiene la función `leer_pitch()` implementada:

```cpp
void leer_pitch()
{
    sensors_event_t event;
    bno.getEvent(&event);
    pitch = event.orientation.y;
}
```

Y ya se usa para ajustar velocidad en rampas:

```cpp
int ajustarVelocidadPorPendiente(int velocidadBase)
{
    leer_pitch();
    if (pitch > 10) return 30;
    else return 25;
}
```

La idea sería: en vez de retroceder por tiempo fijo, retroceder
hasta que el pitch supere un umbral, indicando que el robot
comenzó a levantarse contra la pared.

```cpp
// Concepto
while (digitalRead(32) == 0) {
    leer_pitch();
    robot.steer(10, BACKWARD, 0);
    if (abs(pitch) > PITCH_WALL_THRESHOLD) break;
}
```

**Pros:**
- ✅ Sin cambio de hardware
- ✅ Sin desarmar el robot
- ✅ Sin diseño 3D adicional
- ✅ Sensor ya presente y funcionando

**Contras:**
- ❌ Menos preciso: el pitch varía según el peso de la garra y la carga
- ❌ El umbral cambia si hay pelotitas vs sin pelotitas
- ❌ No detecta alineación lateral: el robot puede estar torcido
  y aun así el pitch subir igual
- ❌ Se pierden segundos esperando que el pitch alcance el umbral
- ❌ En superficies irregulares como las lomas de burros el pitch puede dar falsos positivos

---

### Opción B — Finales de carrera (solución elegida)

Dos finales de carrera montados en la parte trasera del robot,
uno en cada extremo. Conectados a los **2 pines digitales libres**
que quedan disponibles en caso de la aprobacion de la ESP32 Super Mini.

#### Principio de funcionamiento

Cuando el robot retrocede contra la pared:

- Si **solo uno** se activa → el robot está torcido → seguir corrigiendo
- Si **los dos** se activan simultáneamente → el robot está alineado → frenar

```cpp
#define FC_IZQUIERDO 41   // pin digital libre
#define FC_DERECHO   40   // pin digital libre

// Retroceso con alineación por finales de carrera
while (digitalRead(32) == 0) {
    robot.steer(10, BACKWARD, 0);
    bool fc_izq = digitalRead(FC_IZQUIERDO) == LOW;
    bool fc_der = digitalRead(FC_DERECHO)   == LOW;
    if (fc_izq && fc_der) break;  // alineado → frenar
}
robot.steer(0, FORWARD, 0);
```

#### Aplicación en depósito de víctimas

Reemplaza el `runTime(10, BACKWARD, 0, 2000)` por retroceso
controlado:

```cpp
if (green_state == 8) // rojo
{
    digitalWrite(RELAY, HIGH);
    runAngle(20, FORWARD, 180);

    // Antes: runTime(10, BACKWARD, 0, 2000);  ← tiempo fijo
    // Ahora: retroceder hasta que ambos FC choquen
    while (digitalRead(32) == 0) {
        robot.steer(10, BACKWARD, 0);
        if (digitalRead(FC_IZQUIERDO) == LOW &&
            digitalRead(FC_DERECHO)   == LOW) break;
    }
    robot.steer(0, FORWARD, 0);

    claw.depositLeft();
    delay(2000);
    claw.depositCenter();
    runTime(0,  FORWARD, 0, 500);
    runTime(30, BACKWARD, 0, 500);
    runTime(0,  FORWARD, 0, 500);
    runDistance(30, FORWARD, 40);
    veces_deposit++;
}
```

Una vez que los dos finales de carrera chocaron simultáneamente
contra la pared, el robot está alineado y la garra queda siempre
a la misma distancia y ángulo del triángulo de depósito.
No hay riesgo de que las víctimas se caigan porque el robot
ya está contra la pared y no se mueve más hacia atrás.

**Pros:**
- ✅ Detección física directa: si los dos tocaron, estamos alineados
- ✅ Sin falsos positivos por superficie irregular
- ✅ Mismo pin digital de lectura simple (`digitalRead`)
- ✅ Usa los 2 pines libres disponibles tras la ESP32

**Contras:**
- ❌ Requiere desarmar el robot para el cableado
- ❌ Requiere diseño e impresión 3D de soportes para los finales


## PROS Y CONTRAS FINALES

**✅ VENTAJAS:**
- Alineación física garantizada contra la pared
- Depósito siempre a la misma distancia y ángulo
- Sin dependencia de sensores de orientación
- Aprovecha los pines liberados por la ESP32 Super Mini

**❌ DESVENTAJAS:**
- Requiere desarmar el robot
- Soporte 3D debe ser preciso y simétrico
- Cableado adicional interno

# Detección de Víctimas Plateadas Falsas — Pin de Conductividad
 
---
 
## 1. EL PROBLEMA
 
El reglamento 2026 indica en la sección 3.10:
 
> *"The organizers may place fake victims (objects or images) that
> resemble real victims in the evacuation zone. Robots should ignore them."*
 
Y en la sección 3.10.3:
> *"Living victims are silver, reflect light, and are electrically conductive."*
> *"Dead victims are black and not electrically conductive."*
 
Las víctimas plateadas falsas son visualmente idénticas a las reales
para la cámara. El modelo YOLO las clasificará como `plateado` igual
que a las verdaderas, enviando `green_state=7` a la Teensy.
 
**El problema:** el robot ejecuta toda la secuencia de recolección,
gasta tiempo, y deposita una víctima falsa que no suma puntos.
 
---
 
## 2. LA SOLUCIÓN
 
Dos cables conectados a la garra: uno a un pin digital de la Teensy
con `INPUT_PULLUP` y otro a GND. Cuando la garra cierra sobre
una víctima, los cables hacen contacto con su superficie.
 
- **Víctima plateada real** → conductiva → cierra el circuito → pin lee `LOW`
- **Víctima plateada falsa** → no conductiva → circuito abierto → pin lee `HIGH`

```cpp
#define CONDUCTIVIDAD 26  // único pin libre disponible
 
pinMode(CONDUCTIVIDAD, INPUT_PULLUP);
 
// Dentro de green_state == 7, después de claw.close():
if (green_state == 7) {
    digitalWrite(RELAY, HIGH);
    runTime(0, FORWARD, 0, 1000);
    claw.lower();
    claw.sortLeft();
    delay(1000);
    claw.depositCenter();
    delay(1000);
    runDistance(20, FORWARD, 7);
    runTime(0, FORWARD, 0, 1000);
    claw.close();
    delay(500);
 
    // Verificar conductividad
    if (digitalRead(CONDUCTIVIDAD) == LOW) {
        // Es real → continuar recolección normal
        digitalWrite(BUZZER, HIGH);
        delay(100);
        digitalWrite(BUZZER, LOW);
        runTime(0, FORWARD, 0, 1000);
        claw.lift();
        delay(1000);
        claw.open();
        delay(1000);
        runTime(30, FORWARD, 0, 200);
        runTime(30, BACKWARD, 0, 200);
        ball_counter++;
    } else {
        // Es falsa → soltar inmediatamente
        claw.open();
        delay(500);
        runTime(30, BACKWARD, 0, 300);
    }
}
```
 
---
 
## 3. EL PROBLEMA DEL CABLE
 
La solución es simple en electrónica pero el punto crítico
es el cable físico que va desde la Teensy hasta la garra.
 
La garra realiza este ciclo constantemente:
 
```
lower() → close() → lift() → open() → depositCenter() → lower() → ...
```
 
Esto significa que el cable sube y baja con cada recolección,
queda tensado en la posición alta, se dobla repetidamente en
el mismo punto y está expuesto a tirones cuando la garra
cierra sobre una víctima.
 
**Un cable UTP estándar fallaría porque:**
- Conductor de cobre sólido → se quiebra en pocas flexiones repetidas
- Aislante rígido → se agrieta y expone el conductor
- Sin margen de longitud → tirón directo en cada movimiento extremo
### Cable recomendado — disponible en Mercado Libre Argentina
 
| Tipo | Por qué sirve | Disponible en MercadoLibre |
|---|---|---|
| **Jumper** | Conductor multifilar, aislante tipo goma, diseñado para movimiento en robótica Arduino | ✅ Sí, múltiples vendedores |
| **Cable siliconado AWG 28** | Aislante de silicona ultra flexible, conductor cobre estañado trenzado 16 hilos, soporta flexión continua | ✅ Sí |
| **Cable multifilar flexible** | Conductor multifilar genérico, más económico | ✅ Sí |
 
La opción más práctica es el **Jumper** porque:
- Ya viene con el conductor multifilar que distribuye el estrés de flexión
- El aislante tipo goma no se agrieta con el movimiento repetitivo
- Se consigue fácilmente en cualquier tienda de electrónica o Mercado Libre
- No requiere crimpado ni procesado especial
### Consideraciones de montaje
 
- Dejar **holgura suficiente** en la posición más extendida de la garra
  para que nunca quede tensado
- Fijar el cable al brazo con una pequeña lazada para que el movimiento
  se distribuya a lo largo del cable y no se concentre en un punto
- El punto de soldadura al electrodo de la garra debe tener
  **alivio de tensión**: un punto de fijación a pocos mm de la soldadura
  para que el tirón no caiga directo sobre el estaño
---
 
## 4. ESPECIFICACIÓN
 
**Hardware:**
- 2 cables Dupont flexibles (o siliconados AWG 28)
- Pin Teensy: **26** con `INPUT_PULLUP`
- GND: GND común del robot
- Puntos de contacto en la garra: dos electrodos separados
  que toquen la superficie de la víctima al cerrar
**Código:**
- `pinMode(CONDUCTIVIDAD, INPUT_PULLUP)`
- `digitalRead(CONDUCTIVIDAD) == LOW` → víctima real → continuar
- `digitalRead(CONDUCTIVIDAD) == HIGH` → víctima falsa → soltar
---
 
## 5. PROS Y CONTRAS
 
**✅ VENTAJAS:**
- Solución electrónicamente muy simple (un pin, dos cables)
- Usa el único pin libre disponible (pin 26)
- Sin carga computacional adicional
- Detección instantánea: un solo `digitalRead`
- `INPUT_PULLUP` interno evita ruido sin resistencia externa
- Ahorra tiempo al soltar falsas inmediatamente
- Cable Jumper disponible en Mercado Libre Argentina

**❌ DESVENTAJAS:**
- Cable expuesto a fatiga mecánica por movimiento repetitivo
  → requiere cable flexible especial (no cable UTP estándar)
- El montaje de los cables en la garra debe asegurar
  contacto confiable con la víctima al cerrar
- Si el cable se rompe durante la competencia, se pierde
  la detección pero el robot no falla completamente

