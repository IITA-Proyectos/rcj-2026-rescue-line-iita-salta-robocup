#include <Wire.h>
#include <Arduino.h>
#include <drivebase.h>
#include <PID.h>
#include <elapsedMillis.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include "math.h"
#include <Servo.h>
#include <Adafruit_I2CDevice.h>
#include <claw.h>
#include "Adafruit_APDS9960.h"
#include <NewPing.h>
#include <Wire.h>
#include <VL53L0X.h>



// SERVOS
DFServo sort(23, 540, 2390, 274);
DFServo left(14, 540, 2390, 274);
DFServo right(15, 540, 2390, 274);
DFServo lift(22, 540, 2390, 274);
DFServo deposit(12, 540, 2390, 274);
Claw claw(&lift, &left, &right, &sort, &deposit);

// CONSTANTS //
#define FORWARD 0         // Def direction ADELANTE
#define BACKWARD 1        // Def direction ATRAS
#define RELAY 0
#define BUZZER 35         // Definicion de PIN BUZZER
#define LED_ROJO 34       // Definicion de PIN LED_ROJO
#define SWITCH 32         // Definicion de PIN SWITCH
elapsedMillis steertimer; // Cuenta el tiempo transcurrido
bool contador = false;    // Para saber si estamos contando el tiempo o no
bool retroceder = false;  // Para saber si debe retroceder
// INITIALISE BNO055 //
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
// INITIALISE ACTUATORS //
Moto bl(29, 28, 27, "BL"); // pwm, dir, enc
Moto fl(7, 6, 5, "FL");
Moto br(36, 37, 38, "BR");
Moto fr(4, 3, 2, "FR");
DriveBase robot(&fl, &fr, &bl, &br);
// STATE VARIABLES & FLAGS //
String color_detected;
unsigned long tiemporescate=0;
static unsigned long lastTurn = 0;           // persiste entre iteraciones
const unsigned long turnCooldown = 600;      // ms (ajusta)
int counter = 0;
int laststeer = 0;
int serial5state = 0;  // serial code e.g. 255
double speed;          // speed (0 to 100)
double steer;          // angle (0 to 180 deg, will -90 later)
int green_state = 0;   // 0 = no green squares, 1 = left, 2 = right, 3 = double
int silver_line = 0;   // if there is a line to reacquire after obstacle
int servo = 0;
int action =7;            // action to take (part of a task)
bool taskDone = false; // if true, update current_task
int angle0;            // initial IMU reading
bool startUp = false;
float frontUSReading;
int RanNumber;
String rutina = "linea";
bool first_rescate = 1;
String wall = "right";
bool esquinas_negro[3];
bool final_rescate = 1;
String lado_plateado="";
bool lectura =0;
int cccounter,
    leftLidarReading, rightLidarReading;
VL53L0X left_tof;  // Sensor 1
VL53L0X right_tof; // Sensor 2
int distance_left_tof;
int distance_right_tof;
float angulo_rescate = 0;
String pared="";
bool alineado=false;
bool depositando=false;
int veces_deposit=2;
int ball_counter=2;
#define SONAR_NUM 3      // Number of sensors.
#define MAX_DISTANCE 150 // Maximum distance (in cm) to ping.

NewPing sonar[SONAR_NUM] = {     // Sensor object array.
    NewPing(8, 9, MAX_DISTANCE), // Each sensor's trigger pin, echo pin, and max distance to ping.
    NewPing(11, 10, MAX_DISTANCE),
    NewPing(39, 33, MAX_DISTANCE)};

int front_distance;
int left_distance;
int right_distance;

// -----------  FUNCTIONS  -----------
// ULTRASONIDOS FRENTE IZQ DER
void leer_ultrasonidos()
{
    front_distance = sonar[0].ping_cm();
    left_distance = sonar[1].ping_cm();
    right_distance = sonar[2].ping_cm();
}

void imprimir_ultrasonidos()
{
    Serial.print("|D: ");
    Serial.print(right_distance);
    //Serial.println("cm ");
}

// TOF
void leer_tof()
{
    distance_left_tof = left_tof.readRangeContinuousMillimeters();
    distance_right_tof = right_tof.readRangeContinuousMillimeters();
}

void imprimir_tof()
{
    Serial.print("Distance Left: ");
    Serial.print(distance_left_tof);
    Serial.print("mm");

    if (left_tof.timeoutOccurred())
    {
        Serial.print(" TIMEOUT");
    }

    Serial.print("   Distance Right: ");
    Serial.print(distance_right_tof);
    Serial.print("mm");

    if (right_tof.timeoutOccurred())
    {
        Serial.print(" TIMEOUT");
    }
}
void reset_enconder(){
    bl.resetPulseCount();
    fl.resetPulseCount();
    br.resetPulseCount();
    fr.resetPulseCount();
}
// Color Sensor
Adafruit_APDS9960 apds;
struct Color
{
    String name;
    uint16_t r, g, b, c;
};

Color known_colors[] = {
  {"Rojo", 12, 5, 7, 24},
  {"Negro", 0, 0, 0, 67},
  {"Verde", 3, 7, 7, 19},
  
  };
// Función para leer los valores del sensor y determinar el color
String get_color()
{
    uint16_t r, g, b, c;

    // Esperar a que los datos de color estén listos
    while (!apds.colorDataReady())
    {
        delay(5);
    }

    // Obtener los datos del sensor
    apds.getColorData(&r, &g, &b, &c);

    // Calcular el color más cercano utilizando mínimos cuadrados
    String closest_color = "Desconocido";
    uint32_t min_error = UINT32_MAX;

    for (size_t i = 0; i < sizeof(known_colors) / sizeof(known_colors[0]); i++)
    {
        uint32_t error = pow(known_colors[i].r - r, 2) +
                         pow(known_colors[i].g - g, 2) +
                         pow(known_colors[i].b - b, 2) +
                         pow(known_colors[i].c - c, 2);
        if (error < min_error)
        {
            min_error = error;
            closest_color = known_colors[i].name;
        }
    }

    // Imprimir los valores de R, G, B y Clear
    /*
    Serial.print("red: ");
    Serial.print(r);
    Serial.print(" green: ");
    Serial.print(g);
    Serial.print(" blue: ");
    Serial.print(b);
    Serial.print(" clear: ");
    //Serial.println(c);
    */

    return closest_color;
}

// ISR for updating motor pulses
void ISR1() { bl.updatePulse(); }
void ISR2() { fl.updatePulse(); }
void ISR3() { br.updatePulse(); }
void ISR4() { fr.updatePulse(); }

// Read Data from Raspberry by Serial TX-RX
void serialEvent5()
{
    if (Serial5.available() > 0)
    {
        int data = Serial5.read(); // read serial code
         
        if (data == 255) // speed incoming
            serial5state = 0;
        else if (data == 254) // steer incoming
            serial5state = 1;
        else if (data == 253) // task incoming
            serial5state = 2;
        else if (data == 252) // line_middle incoming
            serial5state = 3;
        else if (serial5state == 0)           // set speed
            speed = (double)data / 100 * 100; // max speed = 100
        else if (serial5state == 1)           // set steer
            steer = ((double)data - 90) / 90;
        else if (serial5state == 2) // set task
            green_state = data;
        else if (serial5state == 3) // set line_middle
            silver_line = data;
    }
}

// HELPER FUNCTIONS //

// Do a predefined move by time
void runTime(int speed, int dir, double steer, unsigned long long time)
{
    unsigned long long startTime = millis();
    while ((millis() - startTime) < time)
    {
        robot.steer(speed, dir, steer);
        digitalWrite(13, HIGH);
        if (Serial5.available() > 0)
        {
            int lecturas = Serial5.read();
            Serial.print(lecturas);
        }

        if (digitalRead(32) == 1)
        { // switch is off
            Serial5.clear();
            Serial5.write(255);
            break;
        }
    }

    digitalWrite(13, LOW);
}
void runAngle(int speed, int dir, double angle)
{
    sensors_event_t event;
    bno.getEvent(&event);
    float initialAngle = event.orientation.x;
    float targetAngle = initialAngle + angle;

    // Normalizar el ángulo objetivo al rango 0-360
    targetAngle = fmod(targetAngle, 360.0);
    if (targetAngle < 0)
        targetAngle += 360;

    while (true)
    {
        bno.getEvent(&event);
        float currentAngle = event.orientation.x;
        if (digitalRead(32) == 1)
        { // switch is off
            Serial5.clear();
            Serial5.write(255);
            break;
        }
        // Calcular la diferencia más corta entre los ángulos
        float error = targetAngle - currentAngle;
        if (error > 180)
            error -= 360;
        if (error < -180)
            error += 360;
        Serial.print("Error actual: ");
        //Serial.println(fabs(error));
        if (fabs(error) <= 1.0)
            break;
        // Lógica para manejar los 5 valores de ángulo específicos
        if (angle == 180)
        {
            // Girar 180 grados (media vuelta)
            robot.steer(speed, dir, 1); // Girar a la derecha
        }
        else if (angle == 90 || angle == -270)
        {
            // Girar 90 grados a la derecha
            if (error > 0 && error <= 180)
            {
                robot.steer(speed, dir, -1);
            }
            else
            {
                robot.steer(speed, dir, 1);
            }
        }
        else if (angle == -90 || angle == 270)
        {
            // Girar 90 grados a la izquierda
            if (error < 0 && error >= -180)
            {
                robot.steer(speed, dir, 1);
            }
            else
            {
                robot.steer(speed, dir, -1);
            }
        }
        else if (angle == 45 || angle == -315)
        {
            // Girar 45 grados a la derecha
            if (error > 0 && error <= 180)
            {
                robot.steer(speed, dir, -1);
            }
            else
            {
                robot.steer(speed, dir, 1);
            }
        }
        else if (angle == -45 || angle == 315)
        {
            // Girar 45 grados a la izquierda
            if (error < 0 && error >= -180)
            {
                robot.steer(speed, dir, 1);
            }
            else
            {
                robot.steer(speed, dir, -1);
            }
        }
        else if (angle > 0)
        {
            robot.steer(speed, dir, -1);
        }
        else if (angle < 0)
        {
            robot.steer(speed, dir, 1);
        }
    }
    robot.steer(0, FORWARD, 0);
}


void runDistance(int speed, int dir, int Distance) {
    runTime(30,BACKWARD,0,20);
    runTime(30,FORWARD,0,20);
    reset_enconder();
    int encoder = 25*Distance;
    
    if (dir == FORWARD) {
        while (fr.pulseCount <= encoder && fl.pulseCount <= encoder) {
            robot.steer(speed, dir, 0);
            Serial.print("FL: ");
            Serial.print(fl.pulseCount); // Imprime el valor de pulseCount
            Serial.print(" | ");
            Serial.print("FR: ");
            //Serial.println(fr.pulseCount);
            digitalWrite(13, HIGH);
            delay(10);
            
            if (Serial5.available() > 0) {
                int lecturas = Serial5.read();
                Serial.print(lecturas);
            }
            
            if (digitalRead(32) == 1) { // switch is off
                Serial5.write(255);
                break;
            }
        }
    }else{
        while (fr.pulseCount >= -encoder && fl.pulseCount >= -encoder)
        {
            robot.steer(speed, dir, 0);
            Serial.print("FL: ");
            Serial.print(fl.pulseCount); // Imprime el valor de pulseCount
            Serial.print(" | ");
            Serial.print("FR: ");
            //Serial.println(fr.pulseCount);
            delay(10);
        }
        
        
    }
}
#define TARGET_DISTANCE 70.0 // distancia deseada en cm
#define KP_DISTANCE 0.05     // constante proporcional para la distancia
#define KP_ANGLE 0.05        // constante proporcional para el ángulo de rotación
#define MAX_STEER 1          // valor máximo de steer permitido
#define ANGLE_THRESHOLD 2.0  // umbral de inclinación en grados (yaw)
#define TARGET_ANGLE 0       // ángulo objetivo (robot paralelo a la pared)
float yaw = 0;               // Ángulo de rotación (yaw)
float pitch=0;
float leer_yaw()
{
    sensors_event_t event;
    bno.getEvent(&event);
    float yaw = event.orientation.x; // Yaw es el ángulo de rotación (en grados)
    return yaw;
}
void leer_pitch()
{
    sensors_event_t event;
    bno.getEvent(&event);
    pitch = event.orientation.y; // Yaw es el ángulo de rotación (en grados)
}
void imprimir_yaw()
{
    Serial.print("Yaw: ");
    //Serial.println(yaw);
}
int ajustarVelocidadPorPendiente(int velocidadBase)
{
    leer_pitch();

    int velocidadAjustada = velocidadBase;
    if (pitch > 10) 
    {
            velocidadAjustada = 30;
    }
    else{
        velocidadAjustada= 25;
    }
    return velocidadAjustada;
}
// Función para calcular la diferencia de ángulo en un rango circular de 0 a 360 grados
float calcularDiferenciaAngulo(float anguloActual, float anguloObjetivo)
{
    float error = anguloObjetivo - anguloActual;

    // Ajustar la diferencia para que esté en el rango [-180, 180]
    if (error > 180)
    {
        error -= 360;
    }
    else if (error < -180)
    {
        error += 360;
    }

    return error;
}

void resetear_bno()
{
    if (!bno.begin())
    {
        Serial.print("No BNO055 detected ... Check your wiring or I2C ADDR!");
        while (1)
            ;
    }
    bno.setExtCrystalUse(true);
    delay(200);
}

void avance_recto(String pared)
{
    leer_yaw();
    leer_tof();
    imprimir_tof();
    // Calcular el error de ángulo correctamente con la función circular
    float angle_error = calcularDiferenciaAngulo(yaw, TARGET_ANGLE); // Diferencia angular ajustada

    // Si el ángulo de giro es mayor que el umbral, ignorar el ultrasonido y corregir el ángulo
    if (abs(angle_error - TARGET_ANGLE) > ANGLE_THRESHOLD)
    {
        steer = KP_ANGLE * (-angle_error); // Invertir el signo del error angular
        // Limitar el valor de steer entre [-MAX_STEER, MAX_STEER]
        if (steer > MAX_STEER)
            steer = MAX_STEER;
        if (steer < -MAX_STEER)
            steer = -MAX_STEER;

        // Mover el robot con la corrección de ángulo
        robot.steer(45, FORWARD, steer);

        // Imprimir para depuración
        Serial.print("Corrigiendo con ángulo. Steer: ");
        //Serial.println(steer);
    }
    else
    {
        // El ángulo está alineado, utilizar sensores TOF para mantener la distancia
        float distance_error = TARGET_DISTANCE - (pared == "left" ? distance_left_tof : distance_right_tof);

        steer = KP_DISTANCE * -distance_error;

        // Error de distancia a la pared

        // Calcular la corrección para el steer basada en la distancia

        steer = constrain(steer, -MAX_STEER, MAX_STEER); // Limitar steer

        // Mover el robot utilizando la corrección de distancia
        robot.steer(45, FORWARD, steer);

        // Imprimir para depuración
        Serial.print("Corrigiendo con TOF. Steer: ");
        //Serial.println(steer);
    }
}

void lado_pared()
{
    if (left_distance != 0 && right_distance != 0 && right_distance < left_distance)
    {
        wall = "right";
    }
    else
    {
        wall = "left";
    }
}
void pelotita()
{
    
}


void setup()
{

    robot.steer(0, 0, 0);
    claw.lift();
    angulo_rescate = fmod(20, 360.0);
    //Serial.println(angulo_rescate);
    attachInterrupt(digitalPinToInterrupt(27), ISR1, CHANGE);
    attachInterrupt(digitalPinToInterrupt(5), ISR2, CHANGE);
    attachInterrupt(digitalPinToInterrupt(38), ISR3, CHANGE);
    attachInterrupt(digitalPinToInterrupt(2), ISR4, CHANGE);
    pinMode(SWITCH, INPUT_PULLUP); // SWITCH
    pinMode(BUZZER, OUTPUT);       // BUZZER
    pinMode(LED_ROJO, OUTPUT);     // LED ROJO
    pinMode(LED_BUILTIN, OUTPUT);  //  LED BUILT-IN for debugging
    pinMode(RELAY, OUTPUT);           
//Serial1.begin(57600);          // for reading IMU
    Serial5.begin(115200);         // for reading data from rpi and state
    delay(200);
    //Serial.begin(115200);          // displays ultrasound ping result
    // Initialise BNO055
    if (!bno.begin())
    {
        Serial.print("No BNO055 detected ... Check your wiring or I2C ADDR!");
        while (1)
            ;
    }
    bno.setExtCrystalUse(true);

    // Initialise APDS9960 Color Sensor
    if (!apds.begin())
    {
        //Serial.println("failed to initialize device! Please check your wiring.");
    }
    else
        //Serial.println("Device initialized!");

    // enable color sensign mode
    apds.enableColor(true);

    // Initialise TOF
    Wire1.begin(); // Initialize the first I2C bus
    Wire2.begin(); // Initialize the second I2C bus

    left_tof.setBus(&Wire2);  // Assign the first bus to Sensor 1
    right_tof.setBus(&Wire1); // Assign the second bus to Sensor 2

    left_tof.setAddress(0x30);  // Set unique address for Sensor 1
    right_tof.setAddress(0x30); // Set unique address for Sensor 2

    // Continue with your setup and loop functions as before

    left_tof.init();
    left_tof.setTimeout(500);
    left_tof.startContinuous();

    right_tof.init();
    right_tof.setTimeout(500);
    right_tof.startContinuous();
}



void loop()
{
    if (digitalRead(32) == 1)
    {                               // switch is off
        robot.steer(0, FORWARD, 0); // stop moving
        claw.lift();
        claw.sortLeft();
        Serial5.clear();
        esquinas_negro[0] = 0;
        esquinas_negro[1] = 0;
        esquinas_negro[2] = 0;
        first_rescate = 1;
        final_rescate = 1;
        action = 7;
        startUp = false;
        taskDone = true;
        Serial5.write(255);
        while (true)
        {
            robot.steer(0, 0, 0);
                    digitalWrite(RELAY,LOW);
            claw.open();
            digitalWrite(LED_BUILTIN, HIGH);
            // digitalWrite(BUZZER, HIGH);
            digitalWrite(LED_ROJO, HIGH);
            delay(500);
            robot.steer(0, 0, 0);
            digitalWrite(LED_BUILTIN, LOW);
            digitalWrite(BUZZER, LOW);
            digitalWrite(LED_ROJO, LOW);
            digitalWrite(RELAY,LOW); 


            delay(500);
            if (digitalRead(SWITCH) == 0)
            {
                break;
            }
        }
    }
    else if (digitalRead(32) == 0 && !startUp)
    {
        digitalWrite(LED_BUILTIN, LOW);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, LOW);
        runTime(20, BACKWARD, 0, 300);
        runTime(20, FORWARD, 0, 300);
        // Serial5.write(254);
        startUp = true;
        rutina = "linea";
        claw.lift();
        claw.depositCenter();
        action = 7;
        Serial5.write(249);

    }
    else
    {

        digitalWrite(LED_BUILTIN, HIGH);
        digitalWrite(BUZZER, LOW);
        digitalWrite(LED_ROJO, HIGH);
        // int lectura = ultrasonic.read();
        /*if(steer<30 or steer>150){
            counter++;
        }
        if(laststeer<30 and steer>30 and counter>15){
            runTime(20,1,0.5,500);
            counter=0;
        }
        if(laststeer>150 and steer<150 and counter>15){
            runTime(20,1,-0.5,500);
            counter=0;
        }
        */
        while (rutina == "linea" && digitalRead(32) == 0)
        {

            color_detected = get_color();
            leer_tof();
            leer_ultrasonidos();
            /*
            if (color_detected == "Plateado"){
                runTime(20,FORWARD,0,100);
                color_detected = get_color();
                if (color_detected == "Plateado"){
                rutina = "rescate";
                break;
            }
            }
            */
            if (taskDone)
            { // robot is currently not performing any task

                // //Serial.println("Incoming Task: ");
                // //Serial.println(green_state);
                if (green_state == 0)
                {
                    action = 7;
                }
                if (green_state == 1)
                {
                    action = 6; // verde izquierda  
                }
                if (green_state == 2)
                {
                    action = 5; // verde derecha
                }
                if (green_state == 3)
                {
                    action = 14;
                }
                if (front_distance != 0 && front_distance < 12)
                {
                    action = 1;
                }
                
                if (silver_line == 1)
                {
                    action = 2;
                }

                switch (action)
                {
                case 1:
                    digitalWrite(BUZZER, HIGH);
                    delay(100);
                    digitalWrite(BUZZER, LOW);
                        RanNumber = random(3);
                        RanNumber = random(1, 3);
                        if (RanNumber == 1)
                        {
                            runAngle(25, FORWARD, -95);
                            runTime(30, FORWARD, -0.35, 1000);
                            while (digitalRead(32) == 0)
                            {
                                robot.steer(30, FORWARD, -0.35);
                                // serialEvent5();
                                if (get_color() == "Negro")
                                {
                                    runAngle(30, FORWARD, -90);
                                    break;
                                }
                            }
                        }
                        if (RanNumber == 2)
                        {
                            runAngle(25, FORWARD, 95);
                            runTime(30, FORWARD, 0.35, 1000);
                            while (digitalRead(32) == 0)
                            {
                                robot.steer(30, FORWARD, 0.35);
                                // serialEvent5();
                                if (get_color() == "Negro")
                                {
                                    runAngle(30, FORWARD, 90);
                                    break;
                                }
                            }
                        }
                    
                    break;
                case 2:
                    digitalWrite(BUZZER, HIGH);
                    delay(100);
                    digitalWrite(BUZZER, LOW);
                    rutina="rescate";
                    ball_counter=0;
                    veces_deposit = 0;
                    alineado=false;
                    depositando=false;
                    runTime(0, FORWARD, 0, 1000);
                     runTime(30,FORWARD,0,2000);


                   
                    leer_ultrasonidos();
                    if(left_distance < right_distance)
                    {
                        /*runAngle(30,FORWARD,90);
                        runTime(0,BACKWARD,0,900);
                        runTime(40,BACKWARD,0,380);
                        runTime(40,FORWARD,0,800);
                        runTime(0,BACKWARD,0,1000);*/
                         angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0);
                        if (angulo_rescate < 0) angulo_rescate += 360;
                        runTime(20,FORWARD,0,1500);
                        runTime(0,BACKWARD,0,1000);
                        runAngle(30,FORWARD,45);
                        runTime(30,FORWARD,0,3000);

                        pared="left";
                        lado_plateado="derecha";
                    }
                    if(right_distance < left_distance)
                    {
                       /* runAngle(30,FORWARD,-90);
                        runTime(0,BACKWARD,0,900);
                        runTime(60,BACKWARD,0,380);
                        runTime(40,FORWARD,0,800);*/
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0); 
                        if (angulo_rescate < 0)                        
                        angulo_rescate += 360;
                        runTime(20,FORWARD,0,1500);
                        runTime(0,BACKWARD,0,1000);
                        runAngle(30,FORWARD,-45);
                        runTime(30,FORWARD,0,3000);
                        pared="right";
                        lado_plateado="izquierda";
                    }
                   /* if(right_distance && left_distance>=50){
                        leer_ultrasonidos();

                        while(front_distance>12){
                            robot.steer(25,FORWARD,0);
                            leer_ultrasonidos();
                        }
                        runAngle(30,FORWARD,180);
                        runTime(0,BACKWARD,0,800);
                        runTime(60,BACKWARD,0,200);
                        angulo_rescate = leer_yaw();            
                        angulo_rescate = fmod(angulo_rescate, 360.0); 
                        if (angulo_rescate < 0)                        
                        angulo_rescate += 360;
                        lado_plateado="medio";
                        pared="derecha";
                    }*/
                    runTime(0,FORWARD,0,3000);
                    tiemporescate=millis();
                    break;
                case 6:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    if (green_state == 1)
                    {
                        runAngle(35, FORWARD, -60);
                    }
                    break;
                case 5:
                    runTime(20, FORWARD, 0, 800);
                    serialEvent5();
                    if (green_state == 2)
                    {
                        runAngle(25, FORWARD, 60);
                    }
                    break;
                case 7: // linetrack
                
                    {int velocidadAjustada = ajustarVelocidadPorPendiente(25);

                     if (steer < -0.7 || steer > 0.7)
                    {
                            robot.steer(55, FORWARD, steer);
                    }

                    else
                    {
                        robot.steer(velocidadAjustada, FORWARD, steer);
                    }
                
                    break;
                    }
                case 14: // turn 180 deg for double green squares
                    serialEvent5();
                    if (green_state == 3)
                    {
                        runAngle(30, FORWARD, 180);
                        runTime(30, BACKWARD, 0, 200);
                    }
                    action = 7;
                    break;

                }

            }
        }
        while (rutina == "rescate" && digitalRead(32) == 0)
        {
           digitalWrite(LED_BUILTIN, LOW);
            serialEvent5();
            robot.steer(speed, FORWARD, steer);
            digitalWrite(0,LOW);

            if (green_state == 6)
            {
                runTime(0,FORWARD,0,1000);
                claw.lower();
                delay(1000);
                claw.depositCenter();
                delay(1000);
                claw.sortRight();
                delay(1000);
                runDistance(30,FORWARD,7);
                runTime(0,FORWARD,0,1000);
                claw.close();
                delay(1000);
                digitalWrite(BUZZER, HIGH);
                delay(100); 
                digitalWrite(BUZZER, LOW);
                runTime(0,FORWARD,0,1000);
                claw.lift();
                delay(1000);
                claw.open();
                delay(1000);
                runTime(30,FORWARD,0,200);
                runTime(30,BACKWARD,0,200);
                 ball_counter++;
            }
            if (green_state == 7)            {
                runTime(0,FORWARD,0,1000);
                claw.lower();
                claw.sortLeft();
                delay(1000);
                claw.depositCenter();
                delay(1000);
                runDistance(20,FORWARD,7);
                runTime(0,FORWARD,0,1000);
                claw.close();
                delay(1000);
                digitalWrite(BUZZER, HIGH);
                delay(100); 
                digitalWrite(BUZZER, LOW);
                runTime(0,FORWARD,0,1000);
                claw.lift();
                delay(1000);
                claw.open();
                delay(1000);
                runTime(30,FORWARD,0,200);
                runTime(30,BACKWARD,0,200);
                ball_counter++;
            }

            if (ball_counter>= 3 && depositando==false)
            {
                Serial5.write(248);
                depositando=true;
                serialEvent5();
                robot.steer(speed, FORWARD, steer);   
            }
            if(green_state == 9)
                {
                    runAngle(20,FORWARD,180);
                    runTime(10,BACKWARD,0,2000);
                    claw.depositRight();
                    delay(2000);
                    claw.depositCenter();
                    runTime(0,FORWARD,0,500);
                    runTime(30,BACKWARD,0,500);
                    runTime(0,FORWARD,0,500);
                    runDistance(30,FORWARD,4+60);
                    veces_deposit++;
                }
            if (green_state == 8)//rojo
                {
                    runAngle(20,FORWARD,180);
                    runTime(10,BACKWARD,0,2000);
                    claw.depositLeft();
                    delay(2000);
                    claw.depositCenter();
                    runTime(0,FORWARD,0,500);
                    runTime(30,BACKWARD,0,500);
                    runTime(0,FORWARD,0,500);
                    runDistance(30,FORWARD,40);
                    veces_deposit++;

                }
            
            if (veces_deposit == 2)
            {
                runTime(0,BACKWARD,0,3000);
                claw.close();
                runTime(0,FORWARD,0,1000);
                float diferencia = calcularDiferenciaAngulo(leer_yaw(), angulo_rescate);
                runAngle(30, FORWARD, diferencia);
                while(digitalRead(32) == 0){
                    leer_ultrasonidos();
                    robot.steer(25, FORWARD, 0); 

                    if(!alineado && front_distance < 12){
                        runTime(0, FORWARD, 0, 1000); 
                        if(pared == "left"){
                           
                            runAngle(25, FORWARD, 90);
                        }
                        if(pared == "right"){
                            runAngle(25, FORWARD, -90);
                        }
                        alineado = true; 
                    }
                    if(alineado){
                        leer_ultrasonidos();
                        robot.steer(25,FORWARD,0);
                        if(front_distance<12){
                            leer_ultrasonidos();
                            runTime(20,FORWARD,0,200);
                            if(left_distance < right_distance)
                            {

                                    
                                runAngle(25,FORWARD,-90);
                            }
                            else if(right_distance<left_distance)
                            {

                                    runAngle(25,FORWARD,-90);
                            }
                        }
                    }
                } // end inner while
            }
            /*if(green_state == 10)
                { 
                    estado == "salida"
                    runTime(0,BACKWARD,0,3000);

                }*/
            
        } // end while (rutina == "rescate" && digitalRead(32) == 0)
    } // end else (principal del loop)
} // end loop()