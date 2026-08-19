/*
  telemetria.h — Transporte de telemetria por Serial8 (Teensy 4.1 -> ESP32-MINI)
  ---------------------------------------------------------------------------
  IITA Salta — RoboCup Junior Rescue Line 2026.

  Objetivo: enviar TODOS los valores de control (sensores + estado + enlace RPi)
  a la ESP32-MINI, que monta un AP WiFi y sirve la GUI de telemetria. La ESP32
  es un "tubo tonto": recibe una linea JSON por UART y la reenvia al navegador.

  REGLA DE ORO — NO INTRUSIVO:
    * Esta clase SOLO transporta. NO define el esquema (eso vive en main.cpp,
      donde estan los globals).
    * La escritura es NO BLOQUEANTE: si el buffer TX de Serial8 no tiene lugar
      para el frame completo, el frame se DESCARTA (se cuenta) y el control
      sigue sin frenarse ni un microsegundo. La telemetria es best-effort.
    * Rate-limit interno (por defecto 10 Hz) para no saturar ni la UART ni el CPU.

  Cableado (ya existente del ex-SuperTema):
    Teensy TX8 (pin 35) -> ESP32 RX   |   Teensy RX8 (pin 34) <- ESP32 TX (opcional)
    GND comun. 3.3V ambos lados, sin level shifter.
    Velocidad: la fija TLM_BAUD en src/main.cpp (hoy 230400) y TIENE QUE
    coincidir con UART_BAUD del firmware de la ESP32.
*/
#ifndef TELEMETRIA_H
#define TELEMETRIA_H

#include <Arduino.h>

// NOTA: usamos HardwareSerialIMXRT (tipo concreto de Serial8 en Teensy 4.x) en vez
// de la base abstracta HardwareSerial porque addMemoryForWrite() -imprescindible
// para agrandar el buffer TX de 40 a ~1 KB- solo existe en la clase concreta.
class Telemetria
{
public:
    // port: puerto hardware (Serial8). intervaloMs: periodo minimo entre frames.
    Telemetria(HardwareSerialIMXRT &port, unsigned long intervaloMs = 100);

    // Abre el puerto y agranda el buffer TX para que write() nunca bloquee
    // mientras entre un frame completo. Idempotente.
    // El default es historico: main.cpp SIEMPRE pasa TLM_BAUD explicito.
    void begin(unsigned long baud = 115200);

    // true cuando ya paso el intervalo desde el ultimo envio (marca el tiempo).
    // Llamar una sola vez por frame: consumir el resultado.
    bool debeEnviar();

    // Escribe el frame SOLO si hay lugar en el buffer TX (no bloquea nunca).
    // Devuelve true si se envio, false si se descarto por falta de lugar.
    bool enviar(const char *buf, int len);

    unsigned long framesEnviados() const { return _enviados; }
    unsigned long framesDescartados() const { return _descartados; }

private:
    HardwareSerialIMXRT &_port;
    unsigned long _intervaloMs;
    unsigned long _ultimoMs;
    unsigned long _enviados;
    unsigned long _descartados;
    bool _iniciado;

    // Buffer extra para el TX de Serial8 (garantiza escritura no bloqueante de
    // un frame completo).
    // OJO: availableForWrite() nunca devuelve mas que (40 + TX_EXTRA - 1), y la
    // guarda de enviar() descarta el frame si no entra entero. O sea que este
    // numero es un TECHO DURO del tamanio del frame: si el frame lo pasa, la
    // telemetria se apaga del todo y en silencio.
    // 1536 deja margen sobre el frame v2 (~825 B en el peor caso con hdr).
    static const size_t TX_EXTRA = 1536;
    uint8_t _txExtra[TX_EXTRA];
};

#endif // TELEMETRIA_H
