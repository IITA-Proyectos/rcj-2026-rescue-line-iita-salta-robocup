// ##################################################
//
// ### IMPORTACION DE LIBRERIAS
//
// ##################################################

#include <Arduino.h>
#include <NewPing.h>
#define SONAR_NUM 3
#define MAX_DISTANCE 400
#define PING_INTERVAL 33

NewPing sonar[SONAR_NUM] = {
    NewPing(8, 9, MAX_DISTANCE),   // right
    NewPing(11, 10, MAX_DISTANCE), // left
    NewPing(39, 33, MAX_DISTANCE), // front
};                                 // trigger, echo, max distance in cm

unsigned long pingTimer[SONAR_NUM]; // Holds the next ping time.
unsigned int cm[SONAR_NUM];
uint8_t currentSonar = 0;

void ISR5()
{ // If ping echo, set distance to array.
    /*
    Technical description.

    Interrupt callback to capture echo time and store distance.

    Parameters:
    None

    Returns:
    void

    Side effects:
    - Updates cm[currentSonar] with measured distance.
    */
    if (sonar[currentSonar].check_timer())
        cm[currentSonar] = sonar[currentSonar].ping_result / US_ROUNDTRIP_CM;
}

void oneSensorCycle()
{ // Do something with the results.
    /*
    Technical description.

    Print distances from all sonar sensors after a full cycle.

    Parameters:
    None

    Returns:
    void

    Side effects:
    - Writes measurement data to Serial.
    */
    for (uint8_t i = 0; i < SONAR_NUM; i++)
    {
        Serial.print(i);
        Serial.print("=");
        Serial.print(cm[i]);
        Serial.print("cm ");
    }
    Serial.println();
}

void setup()
{
    /*
    Technical description.

    Initialize Serial and schedule initial ping times for each sonar.

    Parameters:
    None

    Returns:
    void

    Side effects:
    - Starts Serial at 115200.
    - Seeds ping timers for non-blocking sequence.
    */
    Serial.begin(115200); // Open serial monitor at 115200 baud to see ping results.
    pingTimer[0] = millis() + 75;
    for (uint8_t i = 1; i < SONAR_NUM; i++)
        pingTimer[i] = pingTimer[i - 1] + PING_INTERVAL;
}

void loop()
{
    // Main system loop.
    // Executes continuous real-time processing.
    /*
    Technical description.

    Iterate sonar sensors, schedule non-blocking pings, and trigger reporting.

    Parameters:
    None

    Returns:
    void

    Side effects:
    - Controls sonar ping scheduling and serial output.
    */
    for (uint8_t i = 0; i < SONAR_NUM; i++)
    {
        if (millis() >= pingTimer[i])
        {
            pingTimer[i] += PING_INTERVAL * SONAR_NUM;
            if (i == 0 && currentSonar == SONAR_NUM - 1)
                oneSensorCycle(); // Do something with results.
            sonar[currentSonar].timer_stop();
            currentSonar = i;
            cm[currentSonar] = 0;
            sonar[currentSonar].ping_timer(ISR5);
        }
    }
}
