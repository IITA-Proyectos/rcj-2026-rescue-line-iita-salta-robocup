# -*- coding: utf-8 -*-
"""COMPLETAR EL GIRO despues del pivote de recuperacion (codo cerrado de 135 grados).

Problema medido el 13-sep-2026 en v66r3_auth_1 (banco del codo): el pivote de la Teensy
gira hacia el lado correcto pero se queda corto y la cinta queda DE FRENTE, atravesada.
El seguidor la ve centrada, manda casi 0, el robot sigue recto y la cruza.

Regla: SOLO despues de una CURVA soltada y SOLO cuando la Teensy avisa que termino el
pivote (byte 0xED). Si en ese momento la cinta esta de frente, se manda giro fuerte hacia
el MISMO lado del pivote hasta que la cinta suba (alineada o diagonal). Con topes de
tiempo. Si la cinta no esta de frente, no hace nada: el robot se comporta como hoy.

Medido sobre los videos, con esta misma clasificacion y anclando al fin del pivote:
  completo_auth_1  (la corrida casi completa): no se activa en ninguno de sus 11 recoveries.
  v66r3_auth_1     se activa en 7 codos que se fueron; no en los 2 que salieron bien.

Apagado por defecto: COMPLETAR_GIRO=1 para activarlo.
"""
import os

import numpy as np

COMPLETAR_GIRO = os.environ.get("COMPLETAR_GIRO", "0") == "1"
# 85 grados de protocolo = steer 0,94: la Teensy pivota en el lugar (>= LINE_PIVOT_STEER 0,92).
CG_ANG = float(os.environ.get("CG_ANG", "85"))
# Tiempo, desde que el pivote termino y la Pi solto el control, para que aparezca la cinta de frente.
CG_VENTANA_S = float(os.environ.get("CG_VENTANA_S", "0.80"))
# Tope de giro forzado una vez que empezo. A ~70 grados/s de pivote son ~30 grados como maximo.
CG_MAX_S = float(os.environ.get("CG_MAX_S", "0.45"))
# Frames seguidos con la cinta subiendo (A o D) que dan el giro por completo.
CG_DESARMA_AD = int(os.environ.get("CG_DESARMA_AD", "2"))


def forma_cinta(mm, ok=True):
    """Forma de la componente conectada con el robot (mascara 160x120 recortada en la fila 60).

    A  alineada: llega arriba y es angosta
    D  diagonal: llega arriba, ancha, cruza en diagonal
    F  DE FRENTE: atravesada de lado a lado
    b  mancha baja parcial
    .  sin linea conectada
    """
    if not ok or mm is None:
        return "."
    ys, xs = np.nonzero(mm)
    if len(ys) == 0:
        return "."
    ymin = int(ys.min())
    span = int(xs.max()) - int(xs.min()) + 1
    xt = np.nonzero(mm[ymin:ymin + 6, :])[1]
    wt = int(xt.max() - xt.min() + 1) if len(xt) else 0
    if ymin <= 63 and wt >= 90:
        return "F"
    if ymin >= 66 and span >= 110:
        return "F"
    if ymin <= 63 and span <= 95 and wt <= 60:
        return "A"
    if ymin <= 63 and span > 95 and wt <= 75:
        return "D"
    return "b"


class CompletarGiro(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.lado = 0            # +1 DER, -1 IZQ (convencion del arbitro)
        self.t_soltar = 0.0
        self.t_pivote = 0.0
        self.t_inicio = 0.0
        self.n_ad = 0
        self.frames = 0
        self.desarmado = False
        self.logueado = False

    def nuevo_episodio(self):
        self.reset()

    def pivote_hecho(self, now):
        self.t_pivote = now

    def soltar(self, lado, now):
        self.lado = 1 if lado > 0 else (-1 if lado < 0 else 0)
        self.t_soltar = now

    def paso(self, mm, ok, now):
        """Angulo a mandar (protocolo: derecha negativa) o None si no corresponde."""
        if self.desarmado or not self.lado or self.t_soltar <= 0.0 or self.t_pivote <= 0.0:
            return None
        t0 = max(self.t_soltar, self.t_pivote)
        if now < t0:
            return None
        if self.t_inicio > 0.0:
            if now - self.t_inicio > CG_MAX_S:
                self.desarmado = True
                return None
        elif now - t0 > CG_VENTANA_S:
            self.desarmado = True
            return None
        f = forma_cinta(mm, ok)
        if f in ("A", "D"):
            self.n_ad += 1
            if self.n_ad >= CG_DESARMA_AD:
                self.desarmado = True
            return None
        self.n_ad = 0
        if f != "F":
            return None
        if self.t_inicio <= 0.0:
            self.t_inicio = now
        self.frames += 1
        return -CG_ANG * self.lado
