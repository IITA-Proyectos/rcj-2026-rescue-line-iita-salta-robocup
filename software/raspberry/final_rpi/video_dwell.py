# -*- coding: utf-8 -*-
"""
video_dwell.py - Video comparativo: que ORDENABA el firmware viejo y que
                 ORDENARIA el nuevo, sobre los MISMOS frames grabados.

============================================================================
 LO PRIMERO: QUE ES Y QUE NO ES ESTE VIDEO
============================================================================

ESTO NO ES una simulacion de como se moveria el robot. NO se puede hacer, y no
es una limitacion de este script: las imagenes estan grabadas con la trayectoria
que el robot REALMENTE hizo ese dia. Si el firmware nuevo hubiera sostenido el
giro, el robot habria quedado apuntando a otro lado y la camara habria visto
OTRA COSA en el frame siguiente. Es un lazo abierto y se corta justo donde vive
el problema.

LO QUE SI MUESTRA, y es exactamente la pregunta de "deja de hacer el movimiento
extrano": sobre CADA frame que el robot vio, cual era la DIRECCION de giro que
el firmware le ordenaba a las ruedas, con el codigo viejo y con el nuevo. El
"movimiento extrano" es el signo dandose vuelta cada pocas tramas -medido: entre
el 32% y el 87% de los pivotes consecutivos cambian de signo-, y eso SI es una
funcion del angulo y del tiempo, o sea que se puede calcular exacto sin mover el
robot.

O sea: el video contesta "el firmware nuevo deja de zangolotear el signo?" y NO
contesta "el robot completa la curva?".

============================================================================
 DE DONDE SALEN LOS DATOS
============================================================================

Del UNICO par que tiene video Y telemetria enganchados:
    hist.avi  <->  2026-08-22_pista_pivote_con_histeresis.csv
enganchados por `rxf`, el numero de frame que la Raspberry le manda a la Teensy.

El angulo NO se recalcula de la imagen: se lee el `rxsteer` REAL del CSV, que es
lo que la Raspberry mando de verdad. Asi el modelo se alimenta con la entrada
real y lo unico que cambia entre los dos paneles es el firmware.

El modelo del case 7 es la clase ModeloCase7 de replay.py, validada contra ese mismo
CSV: reproduce el 94,1% de la rama y el 92,9% de |rot| dentro de 0,05.

USO
---
    python3 video_dwell.py                      dwell 400 ms, salida por defecto
    python3 video_dwell.py --dwell 250
    python3 video_dwell.py --salida ~/Desktop/comparacion.avi
    python3 video_dwell.py --desde 1300 --hasta 1600     solo un tramo
"""
import argparse
import math
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from replay import (ModeloCase7, FW_STEER_GAIN, FW_PIVOTE_ENTRA,  # noqa: E402
                    FW_PIVOTE_SALE, FW_PIVOTE_MAX_MS, FW_VEL_BASE)

VIDEO = os.path.join(AQUI, "hist.avi")
CSV = os.path.normpath(os.path.join(
    AQUI, "..", "..", "teensy", "firmware", "corridas",
    "2026-08-22_pista_pivote_con_histeresis.csv"))

W, H = 160, 120
ESC = 3                      # el frame de la camara se agranda x3
FPS_REAL = 33.3
ANCHO, ALTO = 900, 560

NEGRO = (18, 18, 18)
BLANCO = (235, 235, 235)
GRIS = (110, 110, 110)
VIEJO_COL = (90, 90, 235)     # BGR: rojo
NUEVO_COL = (110, 220, 110)   # verde
AMARILLO = (60, 210, 235)


class Case7ConDwell(ModeloCase7):
    """El case 7 con el dwell del signo, tal como quedo en main.cpp.

    La unica diferencia con ModeloCase7 de replay.py es la que se agrego al
    firmware: con el pivote enganchado, el signo no se puede dar vuelta antes de
    `dwell_ms` desde el ULTIMO cambio aceptado. Con dwell_ms=0 se comporta
    identico a la clase base, que es la propiedad que tiene el firmware real.
    """

    def __init__(self, dwell_ms=0, **kw):
        ModeloCase7.__init__(self, **kw)
        self.dwell_ms = dwell_ms
        self._signo = 0
        self._signo_t0 = 0.0
        self.sostenidos = 0        # cuantas veces el dwell tapo una inversion

    def paso(self, angulo_gr, dt_s):
        ms = self._t * 1000.0
        r = ModeloCase7.paso(self, angulo_gr, dt_s)
        pedido = 1 if r["rot"] > 0 else (-1 if r["rot"] < 0 else 0)
        r["signo_pedido"] = pedido
        r["sostenido"] = False
        if not r["en_pivote"] or pedido == 0:
            self._signo = 0
            return r
        if self._signo == 0:
            self._signo = pedido
            self._signo_t0 = ms
        elif pedido != self._signo:
            if ms - self._signo_t0 < self.dwell_ms:
                r["rot"] = abs(r["rot"]) * self._signo    # se sostiene
                r["ls"], r["rs"] = r["rs"], r["ls"]
                r["sostenido"] = True
                self.sostenidos += 1
            else:
                self._signo = pedido
                self._signo_t0 = ms
        return r


def leer_csv():
    """{numero de frame -> angulo en grados que mando la Raspberry}."""
    ang = {}
    for ln in open(CSV, encoding="utf-8", errors="replace"):
        p = ln.rstrip("\n").split(",")
        if len(p) != 45:
            continue
        try:
            rxsteer, rxf = int(p[3]), int(p[6])
        except ValueError:
            continue
        ang.setdefault(rxf, rxsteer / 1000.0 * 90.0)
    return ang


def barra(img, x, y, w, h, valor, color, etiqueta):
    """Barra bipolar centrada: izquierda/derecha segun el signo de `valor`."""
    cx = x + w // 2
    cv2.rectangle(img, (x, y), (x + w, y + h), (55, 55, 55), 1)
    cv2.line(img, (cx, y), (cx, y + h), GRIS, 1)
    n = int(abs(valor) * (w // 2))
    if n > 1:
        a, b = (cx, cx + n) if valor > 0 else (cx - n, cx)
        cv2.rectangle(img, (a, y + 2), (b, y + h - 2), color, -1)
    cv2.putText(img, etiqueta, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)


def tira(img, x, y, w, h, hist, color):
    """Tira temporal del signo: arriba = derecha, abajo = izquierda."""
    cv2.rectangle(img, (x, y), (x + w, y + h), (45, 45, 45), 1)
    my = y + h // 2
    cv2.line(img, (x, my), (x + w, my), (70, 70, 70), 1)
    if not hist:
        return
    paso = max(1, len(hist) // w)
    for i in range(0, min(len(hist), w * paso), paso):
        s = hist[-1 - i] if i < len(hist) else 0
        px = x + w - 1 - (i // paso)
        if px < x:
            break
        if s > 0:
            cv2.line(img, (px, my - 1), (px, y + 2), color, 1)
        elif s < 0:
            cv2.line(img, (px, my + 1), (px, y + h - 2), color, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dwell", type=int, default=400, help="T_min en ms (400)")
    ap.add_argument("--salida", default=os.path.join(AQUI, "comparacion_dwell.avi"))
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    a = ap.parse_args()

    if not os.path.exists(VIDEO) or not os.path.exists(CSV):
        print("*** falta %s o %s" % (VIDEO, CSV))
        return 2

    ang = leer_csv()
    print("  CSV: %d frames con angulo, rxf %d..%d" % (len(ang), min(ang), max(ang)))

    cap = cv2.VideoCapture(VIDEO)
    vw = cv2.VideoWriter(os.path.expanduser(a.salida),
                         cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (ANCHO, ALTO))

    fw_v = Case7ConDwell(dwell_ms=0)      # lo que corrio
    fw_n = Case7ConDwell(dwell_ms=a.dwell)  # lo que correria
    dt = 1.0 / FPS_REAL
    hv, hn = [], []
    n = escritos = flips_v = flips_n = 0
    ult_v = ult_n = 0

    while True:
        ok, f = cap.read()
        if not ok:
            break
        i = n
        n += 1
        if i not in ang:
            continue
        g = f[:, :320][::2, ::2] if f.shape[1] >= 640 else f[::2, ::2]
        rv = fw_v.paso(ang[i], dt)
        rn = fw_n.paso(ang[i], dt)
        sv = 1 if rv["rot"] > 0 else (-1 if rv["rot"] < 0 else 0)
        sn = 1 if rn["rot"] > 0 else (-1 if rn["rot"] < 0 else 0)
        if rv["en_pivote"]:
            if ult_v and sv and sv != ult_v:
                flips_v += 1
            ult_v = sv or ult_v
        if rn["en_pivote"]:
            if ult_n and sn and sn != ult_n:
                flips_n += 1
            ult_n = sn or ult_n
        hv.append(sv if rv["en_pivote"] else 0)
        hn.append(sn if rn["en_pivote"] else 0)
        if not (a.desde <= i <= a.hasta):
            continue

        img = np.full((ALTO, ANCHO, 3), NEGRO, np.uint8)
        cam = cv2.resize(g, (W * ESC, H * ESC), interpolation=cv2.INTER_NEAREST)
        img[70:70 + H * ESC, 20:20 + W * ESC] = cam

        cv2.putText(img, "REPLAY DE VISION - NO es simulacion fisica.", (20, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, AMARILLO, 1, cv2.LINE_AA)
        cv2.putText(img, "Mismos frames grabados; lo unico que cambia es el firmware.",
                    (20, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.42, GRIS, 1, cv2.LINE_AA)
        cv2.putText(img, "frame %d   angulo que mando la Pi: %+6.1f gr" % (i, ang[i]),
                    (20, 70 + H * ESC + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.46, BLANCO, 1, cv2.LINE_AA)

        px = 20 + W * ESC + 30
        pw = ANCHO - px - 20
        cv2.putText(img, "QUE LE ORDENA A LAS RUEDAS", (px, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, BLANCO, 1, cv2.LINE_AA)

        barra(img, px, 70, pw, 34, rv["rot"], VIEJO_COL,
              "VIEJO  (dwell 0)      rot %+.2f%s" % (rv["rot"], "  PIVOTE" if rv["en_pivote"] else ""))
        barra(img, px, 150, pw, 34, rn["rot"], NUEVO_COL,
              "NUEVO  (dwell %d ms)  rot %+.2f%s" % (a.dwell, rn["rot"], "  PIVOTE" if rn["en_pivote"] else ""))

        if rn["sostenido"]:
            cv2.rectangle(img, (px - 6, 140), (px + pw + 6, 196), AMARILLO, 2)
            cv2.putText(img, "SOSTIENE EL GIRO (la camara pedia darlo vuelta)",
                        (px, 212), cv2.FONT_HERSHEY_SIMPLEX, 0.44, AMARILLO, 1, cv2.LINE_AA)

        cv2.putText(img, "signo del giro en el tiempo  (arriba=der, abajo=izq)",
                    (px, 258), cv2.FONT_HERSHEY_SIMPLEX, 0.42, GRIS, 1, cv2.LINE_AA)
        tira(img, px, 268, pw, 52, hv, VIEJO_COL)
        tira(img, px, 330, pw, 52, hn, NUEVO_COL)

        cv2.putText(img, "inversiones de signo acumuladas", (px, 416),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, GRIS, 1, cv2.LINE_AA)
        cv2.putText(img, "VIEJO  %d" % flips_v, (px, 446),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.66, VIEJO_COL, 2, cv2.LINE_AA)
        cv2.putText(img, "NUEVO  %d" % flips_n, (px, 480),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.66, NUEVO_COL, 2, cv2.LINE_AA)
        cv2.putText(img, "inversiones tapadas por el dwell: %d" % fw_n.sostenidos,
                    (px, 512), cv2.FONT_HERSHEY_SIMPLEX, 0.42, AMARILLO, 1, cv2.LINE_AA)
        cv2.putText(img, "Lo que NO dice: si el robot completa la curva.",
                    (20, ALTO - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, GRIS, 1, cv2.LINE_AA)

        vw.write(img)
        escritos += 1

    cap.release()
    vw.release()
    print("  %d frames escritos en %s" % (escritos, a.salida))
    print()
    print("  RESULTADO sobre los %d frames con telemetria:" % len(hv))
    print("     inversiones de signo dentro del pivote, VIEJO: %d" % flips_v)
    print("     inversiones de signo dentro del pivote, NUEVO: %d  (dwell %d ms)"
          % (flips_n, a.dwell))
    if flips_v:
        print("     reduccion: %.0f%%" % (100.0 * (flips_v - flips_n) / flips_v))
    print("     inversiones que el dwell tapo: %d" % fw_n.sostenidos)
    print()
    print("  Esto es lo que el replay SI puede decir. Si el robot completa la")
    print("  curva NO se puede saber aca: al girar distinto, la camara habria")
    print("  visto otra cosa. Eso se mide el sabado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
