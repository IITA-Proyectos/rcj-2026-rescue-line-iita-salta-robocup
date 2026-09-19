// telemetria.h - transporte de la telemetria JSON por Serial8 a la ESP32-MINI (AP WiFi + GUI).
// Solo transporta (el esquema vive en main.cpp), con ritmo limitado y sin bloquear: si el frame
// no entra en el buffer TX se descarta y se cuenta.
// Cableado: TX8 (pin 35) -> RX ESP32; RX8 (pin 34) <- TX ESP32 (opcional); GND comun, 3,3 V.
// TLM_BAUD (main.cpp) tiene que coincidir con UART_BAUD del firmware de la ESP32.
#ifndef TELEMETRIA_H
#define TELEMETRIA_H

#include <Arduino.h>

// HardwareSerialIMXRT y no HardwareSerial: addMemoryForWrite() solo existe en la clase concreta.
class Telemetria
{
public:
    // port: puerto hardware (Serial8). intervaloMs: periodo minimo entre frames.
    Telemetria(HardwareSerialIMXRT &port, unsigned long intervaloMs = 100);

    // Abre el puerto y agranda el buffer TX para que write() no bloquee. Idempotente.
    // main.cpp siempre pasa TLM_BAUD: el default no se usa.
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

    // Buffer extra del TX de Serial8. availableForWrite() nunca pasa de 40 + TX_EXTRA - 1 y
    // enviar() descarta el frame que no entra entero: es el techo duro del frame, y en silencio.
    static const size_t TX_EXTRA = 1536;
    uint8_t _txExtra[TX_EXTRA];
};

#endif // TELEMETRIA_H
