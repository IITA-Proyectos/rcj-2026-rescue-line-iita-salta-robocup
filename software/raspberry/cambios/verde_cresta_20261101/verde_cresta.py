# -*- coding: utf-8 -*-
"""VERDE EN LA CRESTA: completar el giro de un verde que aparece subiendo (1-nov-2026).

Problema medido en las corridas del 1-nov (12:49, 13:54 y 14:09), sobre el cruce con verde que esta
arriba de la rampa. La Teensy hace su maniobra fija (800 ms derecho + 39 grados) y despues sigue a la Pi:
  - El cruce necesita ~78 grados a la derecha (medido con flujo optico en 5:01.60 de las 13:54, que salio
    bien) y ~85 a la izquierda. La Teensy hace 39-41 a la derecha y 52-60 a la izquierda. El resto lo
    tiene que completar la Pi.
  - En el piso lo completa: la rama aparece como un pedacito abajo, del lado del verde, y la ley de
    siempre manda -89 hasta que la cinta se conecta (5:01.60 de las 13:54 y 19:07.5 de las 12:49).
  - Subiendo no: los modos de la rampa (cresta, sin-recup) tiran el pedacito y mandan 0. El robot sigue
    derecho y se va (14:09: los 3 intentos a la derecha, 50 a 60 cuadros mandando 0).
  - A la izquierda, ademas, la rama queda cruzada en diagonal (lejos a la izquierda, cerca a la derecha)
    y la ley de siempre manda -43: para el lado contrario (14:09: los 2 intentos a la izquierda).
  - Y el mismo cuadrado se volvia a ver despues del giro: una segunda maniobra de la Teensy lo pasaba a
    -110 grados (13:54 en 4:29.65 y 4:48.70; 12:49 en 20:08.40 y 20:11.95).

Regla. SOLO si el verde (1 o 2) aparece con la Teensy en SUBE:
  1. Se manda ese verde igual que siempre, cuadro a cuadro (la Teensy hace su maniobra).
  2. Durante VC_VENTANA_S desde el primer cuadro del verde: no se manda otro verde (ni doble) y main no
     usa los modos de subida (cresta, recta, transicion): queda la ley del piso. RAMPA_SIN_RECUP sigue
     igual: subiendo nunca se dispara la recuperacion (retrocede cuesta abajo).
  3. Desde VC_INICIO_S (la maniobra de la Teensy termina a 1,45-1,67 s) se manda giro fuerte hacia el
     lado del verde mientras no haya cinta conectada al robot que vaya hacia ese lado (ley de la cinta
     conectada con menos de VC_TOL grados hacia el lado contrario). Con VC_OK cuadros seguidos asi, se
     suelta y ya no vuelve. Tope: VC_MAX_S de giro forzado.
Un verde en el piso, bajando o un doble no lo arman: ahi todo queda como hoy.

Apagado por defecto: VERDE_CRESTA=1 para activarlo.
"""
import math
import os

import cv2
import numpy as np

VERSION = "VERDE-CRESTA-1"
VERDE_CRESTA = os.environ.get("VERDE_CRESTA", "0") == "1"
# Los verdes repetidos aparecieron a 1,2-1,3 s y a 3,9-4,2 s del primero.
VC_VENTANA_S = float(os.environ.get("VC_VENTANA_S", "5.0"))
VC_INICIO_S = float(os.environ.get("VC_INICIO_S", "1.4"))
VC_MAX_S = float(os.environ.get("VC_MAX_S", "0.7"))
# 85 grados de protocolo = pivote en el lugar, como COMPLETAR_GIRO. En los dos giros que salieron bien
# la Pi mando -88/-89 en ese mismo momento.
VC_ANG = float(os.environ.get("VC_ANG", "85"))
VC_TOL = float(os.environ.get("VC_TOL", "25"))
# 18:58 de las 12:49: la cinta se conecto 2 cuadros, se solto y el robot la perdio. Con 4 sigue girando.
VC_OK = int(os.environ.get("VC_OK", "4"))
AREA_MIN_LINEA = 200

_W, _H = 160, 120
_jj, _ii = np.meshgrid(np.arange(_W), np.arange(_H))
_X_COM = (_jj - (_W / 2 - 1)) / (_W / 2)
_Y_COM = ((_H - 1) - _ii) / _H


def _solo_mi_linea(mask):
    """La mancha que toca la fila de abajo, como _solo_mi_linea de main.py."""
    num, et, st, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    fila = et[mask.shape[0] - 2]
    suyas = np.unique(fila[fila > 0])
    if not len(suyas):
        return None
    if max(int(st[i, cv2.CC_STAT_AREA]) for i in suyas) < AREA_MIN_LINEA:
        return None
    return np.isin(et, suyas)


def _ley(m):
    """La ley de siempre de main.py (atan2 del centroide), izquierda positiva."""
    xb = np.where(m, _X_COM, 0.0) * (1 - _Y_COM)
    yb = np.where(m, _Y_COM, 0.0)
    return math.degrees(math.atan2(float(yb.mean()), float(xb.mean()))) - 90


class VerdeCresta(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.lado = 0            # +1 izquierda, -1 derecha (signo del angulo de protocolo)
        self.t0 = 0.0
        self.en_bloque = False
        self.t_forzado = 0.0
        self.n_ok = 0
        self.soltado = False
        self.bloqueados = 0
        self.forzados = 0
        self.evento = None

    def activo(self, now):
        """True mientras main no tiene que usar los modos de subida."""
        return self.lado != 0 and now - self.t0 <= VC_VENTANA_S

    def verde(self, gs, subiendo, now):
        """El green_state a mandar. Arma con un verde simple nuevo en SUBE; en la ventana bloquea otros."""
        es_verde = gs in (1, 2, 3)
        if self.activo(now):
            if self.en_bloque and es_verde:
                return gs
            self.en_bloque = False
            if es_verde:
                self.bloqueados += 1
                return 0
            return gs
        self.en_bloque = False
        if gs in (1, 2) and subiendo:
            self.reset()
            self.lado = 1 if gs == 1 else -1
            self.t0 = now
            self.en_bloque = True
        return gs

    def completar(self, black_mask, now):
        """Angulo a mandar para completar el giro, o None para dejar el de main."""
        if not self.activo(now) or self.soltado or now - self.t0 < VC_INICIO_S:
            return None
        if self.t_forzado <= 0.0:
            self.t_forzado = now
        if now - self.t_forzado > VC_MAX_S:
            self.soltado = True
            self.evento = "suelta por tope: %d cuadros girando" % self.forzados
            return None
        m = _solo_mi_linea(black_mask)
        ley = _ley(m) if m is not None else None
        if ley is not None and ley * self.lado >= -VC_TOL:
            self.n_ok += 1
            if self.n_ok >= VC_OK:
                self.soltado = True
                self.evento = "suelta: cinta conectada (ley %+.0f) tras %d cuadros girando" % (ley, self.forzados)
            return None
        self.n_ok = 0
        self.forzados += 1
        return VC_ANG * self.lado
