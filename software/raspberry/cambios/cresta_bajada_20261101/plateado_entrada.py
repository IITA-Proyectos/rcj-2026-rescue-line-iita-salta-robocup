# -*- coding: utf-8 -*-
"""ENTRADA AL PLATEADO: si la recuperacion decide CURVA a la IZQUIERDA en la entrada, ir derecho (2-nov-2026).

Medido en las 11 corridas del 31-oct y 1-nov (356 recuperaciones, 13 entradas al plateado):
  - En la entrada la cinta llega oblicua a la banda, se pierde y salta la recuperacion. Las que la recuperacion
    mando DERECHO (GAP) entraron: el APDS confirma ~2 s despues. Las que decidieron CURVA a la izquierda
    (+50..+66) quedaron mirando la pared de la zona, sin cinta, y la Pi las freno (GS19).
  - La banda (gris con textura) vista AL LLEGAR (6 cuadros antes de la perdida) y DESPUES DEL RETROCESO (hasta la
    decision), las dos >= PLATEADO_UMBRAL, separa: 8 de 8 entradas que decidian CURVA IZQ y 0 de las 100 curvas a la
    izquierda que no son plateado. Sola, en cualquier recuperacion, NO sirve (piso de costado de noche, crestas).
Regla: SOLO cuando la decision es CURVA IZQ y la banda esta en la llegada y despues del retroceso -> RECTA (GAP,
derecho, como las que entraron). Cualquier otra decision queda igual. Cada CURVA (los dos lados) y cada RECTA de
la recuperacion escribe en el log la hora y sus dos puntajes, actue o no, para ajustar PLATEADO_UMBRAL en la sede.

Cerca de una rampa no actua: arriba de la rampa la camara ve la pista desde lo alto (baldosas, juntas, gente) y la
banda da 2000-4000 sin plateado; una CURVA IZQ a 11 s de una rampa dio 1868 al llegar. Las 13 entradas al plateado
estaban a mas de 90 s del ultimo aviso de rampa. PLATEADO_RAMPA_S = segundos sin aviso de rampa que exige.

PLATEADO_RECTA=1 actua, =sombra solo escribe en el log, =0 apagado (igual que antes).
"""
import os
from collections import deque

import cv2
import numpy as np

VERSION = "PLATEADO-ENTRADA-1"
PLATEADO_RECTA = os.environ.get("PLATEADO_RECTA", "0").strip().lower()
PLATEADO_UMBRAL = float(os.environ.get("PLATEADO_UMBRAL", "1790"))
PLATEADO_RAMPA_S = float(os.environ.get("PLATEADO_RAMPA_S", "20"))
LLEGADA_CUADROS = 6


def puntaje_banda(frame_bgr):
    """Pixeles grises con textura (reflejos en vetas) de la fila 40 para abajo, en el cuadro de 160x120."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    S = hsv[..., 1].astype(np.float32)
    V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5))
    sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    t = (S < 60) & (V > 110) & (V < 225) & (sd > 7)
    return int(np.count_nonzero(t[40:]))


class PlateadoEntrada(object):
    def __init__(self):
        self.ultimos = deque(maxlen=LLEGADA_CUADROS)
        self.s_llegada = []
        self.s_post = []
        self.resultado = None

    def activo(self):
        return PLATEADO_RECTA in ("1", "sombra")

    def observar(self, frame):
        """Cada cuadro, al final del lazo: los ultimos cuadros antes de una perdida."""
        self.ultimos.append(frame.copy())

    def perdida(self):
        """Se disparo la recuperacion: la llegada son los cuadros anteriores (el de ahora no)."""
        self.s_llegada = [puntaje_banda(f) for f in self.ultimos]
        self.s_post = []
        self.resultado = None

    def despues_del_retroceso(self, frame):
        """Cada cuadro desde el fin del retroceso hasta la decision, incluido el de la decision."""
        if self.resultado is None:
            self.s_post.append(puntaje_banda(frame))

    def evaluar(self, decision, seg_rampa=1e9):
        """(actua, mensaje) la primera vez en cada recuperacion; despues (resultado, None).
        decision: 'CURVA IZQ' (la unica que puede actuar), 'CURVA DER' o 'RECTA' (solo se anotan, para ajustar).
        seg_rampa: segundos desde el ultimo aviso de rampa de la Teensy (0 = en rampa ahora)."""
        if self.resultado is not None:
            return self.resultado, None
        if not self.s_llegada or not self.s_post:
            self.resultado = False
            return False, "%s sin cuadros (llegada %d, post %d) -> no actua" % (
                decision, len(self.s_llegada), len(self.s_post))
        lleg = float(np.median(self.s_llegada))
        post = float(np.median(self.s_post))
        banda = lleg >= PLATEADO_UMBRAL and post >= PLATEADO_UMBRAL
        izq = decision == "CURVA IZQ"
        lejos = seg_rampa >= PLATEADO_RAMPA_S
        self.resultado = banda and izq and lejos and PLATEADO_RECTA == "1"
        if not izq:
            fin = "solo se anota"
        elif self.resultado:
            fin = "RECTA"
        elif banda and not lejos:
            fin = "no actua: rampa hace %.0f s" % seg_rampa
        else:
            fin = "seria RECTA (sombra)" if banda else "no actua"
        msg = "%s llegada=%.0f post=%.0f (umbral %.0f, %d cuadros post) -> %s" % (
            decision, lleg, post, PLATEADO_UMBRAL, len(self.s_post), fin)
        return self.resultado, msg
