# -*- coding: utf-8 -*-
"""RETARDO DELIBERADO DEL ANGULO. Apagado por defecto.

Pedido por el profesor: si el robot "reacciona tarde", probar valores de retardo
de envio hasta encontrar el que funcione.

Como se implementa, y por que asi
---------------------------------
"Retardo" puede significar dos cosas muy distintas:

  a) DORMIR antes de enviar (`time.sleep`). Eso ademas BAJA EL FPS: si el lazo
     tarda 25 ms y se agregan 20, la vuelta pasa a 45 ms y el robot ve 22 frames
     por segundo en vez de 33. Mezcla dos variables y no se puede atribuir el
     resultado a ninguna.

  b) COLA FIFO. Se procesan TODOS los frames igual que siempre y se envia el
     angulo que se calculo hace N ms. El FPS no cambia; lo unico que cambia es
     la antiguedad de la orden de giro.

Se usa (b). Es lo unico que permite barrer valores y comparar: una variable por
corrida.

POR QUE SE RETRASA SOLO EL ANGULO
---------------------------------
La primera version encolaba la tupla entera -speed, angle, green_state,
silver_line-. Leyendo el main.py REAL de la Pi aparecio que eso ROMPE la entrada
al modo rescate. En el lazo de linea:

    output = send_frame(speed, round(angle), green_state, silver_line)
    ...
    if silver_line:
        estado = 'rescate'

En el frame que ve la cinta plateada, la tupla con `silver_line=True` se ENCOLA y
se MANDA la de tres frames atras, que tiene `silver_line=False`. Un renglon
despues `estado` pasa a 'rescate', el lazo de linea termina y `modo_rescate()`
manda por su cuenta. La cola queda abandonada: **la Teensy nunca recibe el 1**.

Y `green_state` es el mismo problema mas barato: el verde llegaria 90 ms tarde,
o sea el robot doblaria varios centimetros despues de la marca. Eso es una
SEGUNDA variable en un experimento que tiene que tener una sola.

`speed` en el lazo de linea es constante (40), asi que retrasarlo no cambia nada
y se manda en vivo por coherencia.

Entonces: el angulo va con retardo; green_state, silver_line y speed van en vivo.
Es ademas la version fiel a la hipotesis del profesor, que es sobre CUANDO llega
la orden de GIRO, no sobre los eventos.

Si alguien quiere igual la version literal -retrasar todo-, esta:

    RETARDO_CAMPOS=todo RETARDO_MS=60 python3 main.py

pero entonces hay que acordarse de que la plateada no llega, y esa corrida no
sirve para el tramo de rescate.

Garantia dura
-------------
SIEMPRE se envia exactamente una orden por vuelta. Mientras la cola se llena, se
manda el angulo actual. Si algo falla, se manda el actual. El firmware nunca se
queda sin comando: un hueco de ordenes dispara el watchdog y eso seria un efecto
del andamiaje, no del experimento.

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
    """Cola FIFO del angulo. Con ms=0 es transparente."""

    def __init__(self, ms=None, telemetria_s=5.0, campos=None):
        if ms is None:
            try:
                ms = float(os.environ.get("RETARDO_MS", "0"))
            except ValueError:
                ms = 0.0
        self.ms = max(0.0, float(ms))
        if campos is None:
            campos = os.environ.get("RETARDO_CAMPOS", "angulo").strip().lower()
        self.solo_angulo = (campos != "todo")
        self.cola = collections.deque()
        self.periodo = 0.030          # arranca suponiendo 33,3 fps
        self._t_ant = None
        self._n = 0
        self._retenidas = 0
        self._t_tlm = time.monotonic()
        self.telemetria_s = telemetria_s
        if self.ms > 0:
            print("[RETARDO] ACTIVO: %.0f ms   campos=%s"
                  % (self.ms, "solo el angulo" if self.solo_angulo else "TODO"))
            if not self.solo_angulo:
                print("[RETARDO] *** campos=todo: la plateada NO va a llegar a la")
                print("[RETARDO] *** Teensy. Esta corrida no sirve para el rescate.")
        else:
            print("[RETARDO] apagado (RETARDO_MS=0): envio directo")

    # -- periodo real del lazo, media movil ------------------------------
    def _medir_periodo(self):
        t = time.monotonic()
        if self._t_ant is not None:
            dt = t - self._t_ant
            if 0.005 < dt < 0.5:            # descartar hipos y pausas largas
                self.periodo = 0.9 * self.periodo + 0.1 * dt
            elif dt >= 0.5:
                # PAUSA LARGA = el lazo de linea estuvo cortado: el switch se
                # apago, entro al rescate, o hubo una excepcion y main() se
                # reinicio. Los angulos que quedaron en la cola son de ANTES del
                # corte y no describen nada de lo que el robot tiene enfrente
                # ahora. Mandarlos al volver seria basura justo en el arranque,
                # que es donde se mira si toma bien la linea.
                if self.cola:
                    print("[RETARDO] pausa de %.1f s: descarto %d ordenes viejas"
                          % (dt, len(self.cola)))
                self.cola.clear()
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
            viejo = self.cola.popleft()
        else:
            # la cola todavia se esta llenando: se manda lo actual para NO
            # dejar al firmware sin comando. No se retiene nada.
            viejo = (speed, angle, green_state, silver_line)
            self._retenidas += 1

        if self.solo_angulo:
            # SOLO el angulo viaja atrasado. Ver el docstring: encolar
            # silver_line hace que la Teensy nunca reciba el 1, y encolar
            # green_state mete una segunda variable en el experimento.
            s, a, g, sl = speed, viejo[1], green_state, silver_line
        else:
            s, a, g, sl = viejo

        ahora = time.monotonic()
        if ahora - self._t_tlm >= self.telemetria_s:
            print("[RETARDO] %.0f ms pedidos = %d frames | periodo real %.1f ms "
                  "(%.1f fps) | cola %d | arranque %d | ang ahora %+d -> manda %+d"
                  % (self.ms, n_ret, self.periodo * 1000.0,
                     1.0 / max(self.periodo, 1e-6), len(self.cola),
                     self._retenidas, int(angle), int(a)))
            self._t_tlm = ahora

        try:
            return send_frame(s, a, g, sl)
        except Exception as exc:
            # si la orden vieja falla por lo que sea, mandar la actual: nunca
            # dejar al firmware sin comando
            print("[RETARDO] fallo el envio retardado (%s): mando la actual" % exc)
            return send_frame(speed, angle, green_state, silver_line)

    def vaciar(self, send_frame=None):
        """Al frenar o cambiar de estado: descartar la cola.

        Sin esto, al volver de 'esperando' a 'linea' los primeros frames
        mandarian angulos calculados ANTES del corte. Son pocos -a lo sumo
        n_ret- pero son basura, y el arranque es justo donde se mira si el
        robot toma bien la linea.
        """
        self.cola.clear()
        self._t_ant = None
        if send_frame is None:
            return None
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
