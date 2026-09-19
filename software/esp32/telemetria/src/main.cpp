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
// CABLEADO REAL DEL ROBOT (verificado con el escaneo de pines, 2026-08-01):
// el TX8 del Teensy (pin 35) llega al GPIO20 de la ESP32-C3 (RX0 por defecto),
// que es el mismo cable que ya se usaba con el MicroPython del ex-SuperTema.
#define UART_RX_PIN   20    // <- Teensy TX8 (pin 35)   [dato de telemetria]
#define UART_TX_PIN   21    // -> Teensy RX8 (pin 34)   [opcional, TX0 del C3]
// >>> TIENE QUE COINCIDIR CON  TLM_BAUD  DE
// >>> software/teensy/firmware/src/main.cpp. Si quedan distintos, aca llega
// >>> basura y la telemetria no anda (el control del robot NO se ve afectado:
// >>> este enlace es solo telemetria). Al cambiarlo, flashear LAS DOS placas.
// Subido de 115200 a 230400 porque el frame v2 (~1000 B a 10 Hz) usaba el 87%
// del enlace viejo y se perdian frames en silencio. Ver el comentario largo en
// el main.cpp del Teensy.
#define UART_BAUD     230400

// DIAGNOSTICO: 1 = en vez de arrancar el AP, escanea los GPIOs buscando en cual
// llega el UART del Teensy (imprime el resultado por USB). Poner en 0 para operar.
#define UART_PIN_SCAN 0

// --------------------------------------------------------------------------
WebServer server(80);
HardwareSerial &Teensy = Serial1;   // UART1 del ESP32

// TECHO DE LINEA. Tiene que ser MAYOR que el frame que manda el Teensy, si no
// esta linea se descarta entera y la telemetria se apaga sin avisar (la GUI
// sigue mostrando el ultimo frame bueno, congelado, y en verde).
// El frame v2 del Teensy mide ~825 B en el peor caso (con la cabecera hdr).
// Se mueve junto con el buf[] de enviarTelemetria() y el TX_EXTRA de
// lib/telemetria/telemetria.h: si se toca uno solo, el techo se muda al otro.
static const size_t TLM_LINE_MAX = 1792;     // frame v3 del Teensy (~1380 B) + margen.
// SUBIDO de 1200 al agregar dir/set/tog/drv/loop del lado Teensy. TIENE QUE SER
// MAYOR que el buf[] de enviarTelemetria() en main.cpp del Teensy (hoy 1408):
// si queda por debajo, las lineas largas se descartan ACA y en silencio, y se
// ve como telemetria que 'se muere' sin ningun error. Las dos placas se
// flashean juntas.
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
    // Un frame VIEJO no es un frame. Si el Teensy dejo de mandar (cable de TX8
    // suelto, reset, baud distinto), servir el ultimo bueno para siempre hace
    // que todo el que consume /data -la GUI y tambien colector.py, que graba a
    // SQLite- lea datos de hace minutos como si fueran de ahora. Es la clase de
    // dato mal etiquetado que lleva a una conclusion equivocada con confianza.
    const bool fresco = haveData && (millis() - lastFrameMs) <= 1500;
    server.send(200, "application/json", fresco ? latest : "{}");
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

#if UART_PIN_SCAN
// Escanea GPIOs candidatos del ESP32-C3 buscando en cual llega el UART del Teensy.
// El pin correcto muestra bytes > 0, con '{' y '\n' (es el JSON de telemetria).
static const int SCAN_PINS[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 21};
void runPinScan()
{
    Serial.println("\n===== [SCAN] buscando el pin RX del Teensy (Serial8 -> ESP32) =====");
    int mejor = -1, mejorBraces = -1;
    for (unsigned i = 0; i < sizeof(SCAN_PINS) / sizeof(SCAN_PINS[0]); i++)
    {
        int pin = SCAN_PINS[i];
        Serial1.begin(UART_BAUD, SERIAL_8N1, pin, -1);   // solo RX en este GPIO
        delay(60);
        while (Serial1.available()) Serial1.read();   // vaciar
        unsigned long t0 = millis();
        int bytes = 0, braces = 0, nl = 0;
        while (millis() - t0 < 2500)                   // 2.5 s (el Teensy en idle manda ~1/s)
        {
            while (Serial1.available())
            {
                char c = (char)Serial1.read();
                bytes++;
                if (c == '{') braces++;
                if (c == '\n') nl++;
            }
        }
        Serial1.end();
        bool esEste = (braces > 0 && nl > 0);
        Serial.printf("[SCAN] GPIO%-2d : bytes=%-4d  '{'=%-3d  nl=%-3d  %s\n",
                      pin, bytes, braces, nl, esEste ? "<<<<< TEENSY ACA" : "");
        if (esEste && braces > mejorBraces) { mejorBraces = braces; mejor = pin; }
        delay(40);
    }
    if (mejor >= 0)
        Serial.printf("[SCAN] >>> Pon  #define UART_RX_PIN %d  y reflashea con UART_PIN_SCAN 0\n", mejor);
    else
        Serial.println("[SCAN] No llego nada en ningun pin. Revisar: GND comun, que el Teensy este mandando, y el cable de datos.");
}
#endif

// ------------------------------ Setup --------------------------------------
void setup()
{
    Serial.begin(115200);
#if UART_PIN_SCAN
    delay(1800);                 // dar tiempo a que el USB-CDC enumere
    return;                      // en modo scan no arrancamos WiFi ni el server
#endif

    // Buffer RX grande: evita perder frames mientras handleClient() sirve la
    // pagina (la lectura del UART es por interrupcion, en segundo plano).
    // 4096 y no 1024: el frame v3 mide ~1200 B, asi que con 1024 CUALQUIER
    // demora del loop mayor a ~44 ms (WiFi, HTTP, un cliente que se conecta)
    // desborda el buffer y parte la linea al medio. Una linea partida se
    // descarta -o peor, se pega con la siguiente- y la telemetria se degrada
    // sin avisar. 4096 son ~3 frames de colchon.
    Teensy.setRxBufferSize(4096);
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
#if UART_PIN_SCAN
    runPinScan();
    delay(1200);
    return;
#endif
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
