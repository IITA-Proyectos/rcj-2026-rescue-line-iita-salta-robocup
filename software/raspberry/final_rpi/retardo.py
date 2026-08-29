# -*- coding: utf-8 -*-
"""RETARDO DELIBERADO DEL ENVIO. Apagado por defecto.

Pedido por el profesor: si el robot "reacciona tarde", probar valores de retardo
de envio hasta encontrar el que funcione.

Como se implementa, y por que asi
---------------------------------
"Retardo" puede significar dos cosas muy distintas:

  a) DORMIR antes de enviar (`time.sleep`). Eso ademas BAJA EL FPS: si el lazo
     tarda 25 ms y se agregan 20, la vuelta pasa a 45 ms y el robot ve 22 frames
     por segundo en vez de 33. Mezcla dos variables y no se puede atribuir el
     resultado a ninguna.

  b) COLA FIFO. Se procesan TODOS los frames igual que siempre y se envia la
     orden que se calculo hace N ms. El FPS no cambia; lo unico que cambia es la
     antiguedad de la orden.

Se usa (b). Es lo unico que permite barrer valores y comparar: una variable por
corrida.

Garantia dura
-------------
SIEMPRE se envia exactamente una orden por vuelta. Mientras la cola se llena, se
manda la orden actual. Si algo falla, se manda la orden actual. El firmware
nunca se queda sin comando: un hueco de ordenes dispara el watchdog y eso seria
un efecto del andamiaje, no del experimento.

El retardo se pide en MILISEGUNDOS y se convierte a frames con el periodo REAL
del lazo, medido en vivo con una media movil. Si el lazo cambia de velocidad, el
retardo en ms se mantiene.

Uso desde main.py
-----------------
    from retardo import Retardo
    _retardo = Retardo()                       # lee RETARDO_MS del entorno

    ...dentro del lazo, en vez de:
        output = send_frame(speed, round(angle), green_state, silver_line)
    poner:
        output = _retardo.enviar(send_frame, speed, round(angle),
                                 green_state, silver_line)

Con RETARDO_MS sin definir o en 0, `enviar` llama a `send_frame` directo y el
comportamiento es identico byte por byte al de hoy.

Como barrer
-----------
    RETARDO_MS=0   python3 main.py        # control, lo de siempre
    RETARDO_MS=30  python3 main.py
    RETARDO_MS=60  python3 main.py
    RETARDO_MS=90  python3 main.py

Una corrida por valor, y grabando el CSV de la Teensy en cada una. Ver al final
de este archivo como se evalua si sirve.
"""

import collections
import os
import time


class Retardo(object):
    """Cola FIFO de ordenes. Con ms=0 es transparente."""

    def __init__(self, ms=None, telemetria_s=5.0):
        if ms is None:
            try:
                ms = float(os.environ.get("RETARDO_MS", "0"))
            except ValueError:
                ms = 0.0
        self.ms = max(0.0, float(ms))
        self.cola = collections.deque()
        self.periodo = 0.030          # arranca suponiendo 33,3 fps
        self._t_ant = None
        self._n = 0
        self._retenidas = 0
        self._t_tlm = time.monotonic()
        self.telemetria_s = telemetria_s
        if self.ms > 0:
            print("[RETARDO] ACTIVO: %.0f ms de retardo de envio" % self.ms)
        else:
            print("[RETARDO] apagado (RETARDO_MS=0): envio directo")

    # -- periodo real del lazo, media movil ------------------------------
    def _medir_periodo(self):
        t = time.monotonic()
        if self._t_ant is not None:
            dt = t - self._t_ant
            if 0.005 < dt < 0.5:            # descartar hipos y pausas largas
                self.periodo = 0.9 * self.periodo + 0.1 * dt
        self._t_ant = t

    def frames_de_retardo(self):
        if self.ms <= 0:
            return 0
        return max(1, int(round((self.ms / 1000.0) / max(self.periodo, 1e-6))))

    def enviar(self, send_frame, speed, angle, green_state, silver_line):
        """Manda UNA orden por llamada. Devuelve lo que devuelva send_frame."""
        self._medir_periodo()
        self._n += 1

        if self.ms <= 0:
            return send_frame(speed, angle, green_state, silver_line)

        self.cola.append((speed, angle, green_state, silver_line))
        n_ret = self.frames_de_retardo()

        if len(self.cola) > n_ret:
            s, a, g, sl = self.cola.popleft()
        else:
            # la cola todavia se esta llenando: se manda lo actual para NO
            # dejar al firmware sin comando. No se retiene nada.
            s, a, g, sl = speed, angle, green_state, silver_line
            self._retenidas += 1

        ahora = time.monotonic()
        if ahora - self._t_tlm >= self.telemetria_s:
            print("[RETARDO] %.0f ms pedidos = %d frames | periodo real %.1f ms "
                  "(%.1f fps) | cola %d | arranque %d"
                  % (self.ms, n_ret, self.periodo * 1000.0,
                     1.0 / max(self.periodo, 1e-6), len(self.cola),
                     self._retenidas))
            self._t_tlm = ahora

        try:
            return send_frame(s, a, g, sl)
        except Exception as exc:
            # si la orden vieja falla por lo que sea, mandar la actual: nunca
            # dejar al firmware sin comando
            print("[RETARDO] fallo el envio retardado (%s): mando la actual" % exc)
            return send_frame(speed, angle, green_state, silver_line)

    def vaciar(self, send_frame):
        """Al frenar: descartar la cola y mandar un stop limpio."""
        self.cola.clear()
        try:
            return send_frame(0, 0, 0, 0)
        except Exception:
            return None


# ---------------------------------------------------------------------------
#  COMO SE EVALUA SI SIRVE. No mirar "se ve mejor".
# ---------------------------------------------------------------------------
#
# El HANDOFF tiene medido el numero que hay que mover:
#
#     en la falla el robot gira 147,6 grados BRUTOS y termina en -8,8 NETOS:
#     se cancela el 94 %.
#
# O sea que la mecanica obedece y el giro se anula solo. Si el retardo sirve,
# esa cancelacion tiene que BAJAR. Si sube, el retardo empeora las cosas y hay
# que descartarlo aunque a ojo parezca mas suave.
#
# Con el CSV de la Teensy de cada corrida (columna `gz`, x10):
#
#     bruto = sum(|gz|) * dt          grados girados en total
#     neto  = |sum(gz)| * dt          grados de rumbo efectivamente ganados
#     cancelacion = 1 - neto / bruto
#
# Protocolo del barrido, una variable por corrida:
#
#   1. misma pista, mismo tramo, misma luz, misma bateria (o cargada igual)
#   2. RETARDO_MS = 0 PRIMERO y ULTIMO, para descartar que algo derive entre
#      corridas -bateria, temperatura, luz-. Si los dos controles no dan
#      parecido, el barrido no vale
#   3. tres corridas por valor, no una
#   4. anotar tambien cuantas veces se sale de la pista, que es lo que importa
#
# Si la cancelacion no baja en ningun valor, el retardo no era la palanca y se
# vuelve a RETARDO_MS=0.
