/*
  telemetria.cpp — ver telemetria.h para el contrato y las reglas de no-intrusion.
*/
#include "telemetria.h"

Telemetria::Telemetria(HardwareSerialIMXRT &port, unsigned long intervaloMs)
    : _port(port),
      _intervaloMs(intervaloMs),
      _ultimoMs(0),
      _enviados(0),
      _descartados(0),
      _iniciado(false)
{
}

void Telemetria::begin(unsigned long baud)
{
    if (_iniciado)
    {
        return;
    }
    _port.begin(baud);
    // Agranda el buffer de TX: con esto write() copia y retorna al toque
    // (no bloquea) siempre que entre el frame completo. La UART drena sola.
    _port.addMemoryForWrite(_txExtra, TX_EXTRA);
    _iniciado = true;
}

bool Telemetria::debeEnviar()
{
    unsigned long now = millis();
    if (now - _ultimoMs >= _intervaloMs)
    {
        _ultimoMs = now;
        return true;
    }
    return false;
}

bool Telemetria::enviar(const char *buf, int len)
{
    if (len <= 0)
    {
        return false;
    }
    // Guardia de NO BLOQUEO: si no hay lugar para el frame entero, se descarta.
    // El control jamas espera por la telemetria.
    if (_port.availableForWrite() < len)
    {
        _descartados++;
        return false;
    }
    _port.write(reinterpret_cast<const uint8_t *>(buf), len);
    _enviados++;
    return true;
}
