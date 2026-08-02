/*
  RescueBot — Telemetria ESP32-MINI  (Access Point WiFi + GUI web)
  ============================================================================
  IITA Salta · RoboCup Junior Rescue Line 2026.

  ROL DE LA ESP32: "tubo tonto". El Teensy envia por Serial8 UNA linea JSON por
  frame (~10 Hz) con TODOS los valores de control. La ESP32:
     1) lee esas lineas por UART (UART1),
     2) guarda siempre la ultima (latest),
     3) monta un Access Point WiFi,
     4) sirve una GUI web (software/esp32/telemetria/gui/dashboard.html, embebida
        en web_ui.h) que consulta /data cada 100 ms y renderiza todo.
  La ESP32 NO interpreta el esquema: solo reenvia. El esquema vive en el Teensy
  (enviarTelemetria() en main.cpp) y en el JS de la GUI. Asi no hay duplicacion.

  ---------------------------------------------------------------------------
  CABLEADO (ya existente del ex-SuperTema, 3.3V ambos lados, GND comun):
     Teensy TX8 (pin 35)  ->  ESP32  UART_RX_PIN   (OBLIGATORIO: es el dato)
     Teensy RX8 (pin 34)  <-  ESP32  UART_TX_PIN   (opcional: telemetria no lo usa)
     Alimentacion: 5V del regulador del robot -> VIN/5V de la ESP32 ; GND comun.

  USO:
     1) Flashear esta ESP32.  2) Encender el robot.  3) Desde el celular/laptop
     conectarse al WiFi  "RescueBot-Telemetria"  (clave: rescate2026).
     4) Abrir el navegador en  http://192.168.4.1/
  ============================================================================
*/
#include <WiFi.h>
#include <WebServer.h>
#include "web_ui.h"

// ---------------------- CONFIG (ajustar si hace falta) ----------------------
static const char *AP_SSID = "RescueBot-Telemetria";
static const char *AP_PASS = "rescate2026";   // >= 8 caracteres (requisito WPA2)

// Pines UART hacia el Teensy. Son GPIOs libres del ESP32-C3 Super Mini.
// Conecta el TX8 del Teensy (pin 35) al UART_RX_PIN de aca.
#define UART_RX_PIN   4     // <- Teensy TX8 (pin 35)   [dato de telemetria]
#define UART_TX_PIN   5     // -> Teensy RX8 (pin 34)   [opcional]
#define UART_BAUD     115200

// --------------------------------------------------------------------------
WebServer server(80);
HardwareSerial &Teensy = Serial1;   // UART1 del ESP32

static const size_t TLM_LINE_MAX = 900;      // > frame JSON del Teensy (~0.5 KB)
static char lineBuf[TLM_LINE_MAX];           // acumulador de la linea en curso
static size_t lineLen = 0;
static char latest[TLM_LINE_MAX] = "{}";     // ultimo frame completo recibido
static bool haveData = false;
static unsigned long frameCount = 0;
static unsigned long lastFrameMs = 0;

// --------------------------- Handlers HTTP ---------------------------------
void handleRoot()
{
    server.send_P(200, "text/html; charset=utf-8", INDEX_HTML);
}

void handleData()
{
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", haveData ? latest : "{}");
}

void handleInfo()
{
    char b[220];
    unsigned long age = haveData ? (millis() - lastFrameMs) : 0;
    snprintf(b, sizeof(b),
             "{\"ssid\":\"%s\",\"clients\":%d,\"frames\":%lu,\"lastMs\":%lu,\"up\":%lu,\"heap\":%u}",
             AP_SSID, WiFi.softAPgetStationNum(), frameCount, age,
             (unsigned long)millis(), (unsigned)ESP.getFreeHeap());
    server.send(200, "application/json", b);
}

// ------------------------------ Setup --------------------------------------
void setup()
{
    Serial.begin(115200);

    // Buffer RX grande: evita perder frames mientras handleClient() sirve la
    // pagina (la lectura del UART es por interrupcion, en segundo plano).
    Teensy.setRxBufferSize(1024);
    Teensy.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);

    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    IPAddress ip = WiFi.softAPIP();
    Serial.printf("\n[RescueBot TLM] AP '%s'  ->  http://%s/\n", AP_SSID, ip.toString().c_str());

    server.on("/", handleRoot);
    server.on("/data", handleData);
    server.on("/info", handleInfo);
    server.onNotFound([]() { server.send(404, "text/plain", "404"); });
    server.begin();
}

// ------------------------------- Loop --------------------------------------
void loop()
{
    server.handleClient();

    // Drena todo lo disponible del UART y arma lineas terminadas en '\n'.
    // 'discarding' descarta la linea ENTERA si desborda, para no publicar jamas
    // un fragmento de JSON invalido; se resincroniza recien en el proximo '\n'.
    static bool discarding = false;
    while (Teensy.available())
    {
        char c = (char)Teensy.read();
        if (c == '\n' || c == '\r')
        {
            if (!discarding && lineLen > 0)
            {
                lineBuf[lineLen] = '\0';
                memcpy(latest, lineBuf, lineLen + 1);   // publica el frame nuevo
                haveData = true;
                frameCount++;
                lastFrameMs = millis();
            }
            lineLen = 0;
            discarding = false;   // fin de linea: resincronizado
        }
        else if (!discarding)
        {
            if (lineLen < TLM_LINE_MAX - 1)
            {
                lineBuf[lineLen++] = c;
            }
            else
            {
                discarding = true;   // linea sobre-larga: descartar entera hasta el proximo '\n'
                lineLen = 0;
            }
        }
    }
}
