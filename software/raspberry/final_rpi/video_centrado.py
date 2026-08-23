# -*- coding: utf-8 -*-
"""
video_centrado.py - Que hace el robot en pista con el codigo ACTUAL, marcado
                    con puntos fila por fila, y cuan descentrado queda.

QUE MUESTRA, sobre cada frame que el robot realmente proceso:

  puntos VERDES     el centroide de la cinta FILA POR FILA, de abajo hacia
                    arriba. Es el "espinazo" de lo que la vision ve: si los
                    puntos se van para un lado, la cinta dobla para ese lado.
  punto CELESTE     donde esta la cinta JUSTO DEBAJO del robot (fila 119), con
                    una flecha al centro. Ese es el desvio que importa para
                    "estoy centrado o no".
  cruz AMARILLA     el centroide global de la mascara: el unico punto que la
                    vision realmente usa para decidir. Cuando los verdes y el
                    celeste apuntan a lados distintos, este promedio no
                    representa a ninguno de los dos.
  barra de abajo    lo que el firmware le ordena a las ruedas, y si el pivote
                    esta enganchado.
  marca ROJA        el instante exacto en que el pivote SUELTA.

POR QUE ESTOS PUNTOS Y NO OTROS: medido sobre las 6 corridas, el 88% de los
pivotes se suelta porque `absSteer <= 0,15` -o sea, porque el centroide global
pasa cerca del centro-, despues de solo 11,1 grados de giro real. Y el 99% vuelve
a enganchar a los 270 ms. Este video muestra ese momento cuadro por cuadro.

LO QUE NO MUESTRA: como se moveria el robot con otro firmware. Las imagenes estan
grabadas con la trayectoria que hizo de verdad. Esto es el codigo ACTUAL.

USO
---
    python3 video_centrado.py                     hist.avi por defecto
    python3 video_centrado.py como_esta.avi
    python3 video_centrado.py hist.avi --desde 1300 --hasta 1500
"""
import argparse
import math
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from replay import (ModeloCase7, leer_corrida, ley_2026_08_22,  # noqa: E402
                    FW_STEER_GAIN, FW_PIVOTE_ENTRA)

LO = np.array([0, 0, 0])
HI = np.array([90, 90, 90])
W, H = 160, 120
CENTRO = 79.5
E = 4                                   # escala del frame
ANCHO, ALTO = W * E + 40, H * E + 150

NEGRO = (18, 18, 18)
BLANCO = (235, 235, 235)
GRIS = (120, 120, 120)
VERDE = (120, 235, 120)
CELESTE = (255, 200, 80)
AMARILLO = (60, 210, 235)
ROJO = (80, 80, 240)


def mancha_de_abajo(m):
    """La componente conexa que TOCA la fila 119. Es la unica que puede estar
    debajo del robot; una mancha flotando arriba es el salon."""
    n, et, est, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
    mejor, k0 = 0, 0
    for k in range(1, n):
        if np.any(et[119, :] == k) and est[k, cv2.CC_STAT_AREA] > mejor:
            mejor, k0 = est[k, cv2.CC_STAT_AREA], k
    return (et == k0) if k0 and mejor >= 30 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?", default="hist.avi")
    ap.add_argument("--salida", default="")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    a = ap.parse_args()

    ruta = a.video if os.path.isabs(a.video) else os.path.join(AQUI, a.video)
    if not os.path.exists(ruta):
        print("*** no existe %s" % ruta)
        return 2
    sal = a.salida or os.path.join(AQUI, "centrado_" + os.path.basename(ruta))

    cap = cv2.VideoCapture(ruta)
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(f[:, :320][::2, ::2] if f.shape[1] >= 640 else f[::2, ::2])
    cap.release()

    vistas = leer_corrida(ruta)
    mem = {}
    ang = [ley_2026_08_22(v, mem).angulo for v in vistas]
    fw = ModeloCase7(confirma_ms=0)
    est = []
    prev = False
    for x in ang:
        r = fw.paso(x, 1 / 33.3)
        est.append({"rot": r["rot"], "piv": r["en_pivote"], "suelta": prev and not r["en_pivote"]})
        prev = r["en_pivote"]

    vw = cv2.VideoWriter(sal, cv2.VideoWriter_fourcc(*"MJPG"), 15.0, (ANCHO, ALTO))
    n_suelta = descentrado = 0
    escritos = 0

    for i, g in enumerate(fr):
        if i >= len(est) or not (a.desde <= i <= a.hasta):
            continue
        m = cv2.inRange(g, LO, HI)
        m[:60, :] = 0
        mia = mancha_de_abajo(m)

        img = np.full((ALTO, ANCHO, 3), NEGRO, np.uint8)
        cam = cv2.resize(g, (W * E, H * E), interpolation=cv2.INTER_NEAREST)
        img[40:40 + H * E, 20:20 + W * E] = cam
        ox, oy = 20, 40
        cv2.line(img, (ox + int(CENTRO * E), oy), (ox + int(CENTRO * E), oy + H * E), (90, 90, 90), 1)

        # el espinazo: centroide fila por fila
        for y in range(62, 120, 3):
            xs = np.nonzero(m[y, :])[0]
            if len(xs) == 0:
                continue
            cx = int(xs.mean() * E) + ox
            cv2.circle(img, (cx, int(y * E) + oy), 3, VERDE, -1)

        # donde esta la cinta DEBAJO
        desv = None
        if mia is not None and np.any(mia[119, :]):
            xs = np.nonzero(mia[119, :])[0]
            desv = float(xs.mean()) - CENTRO
            px = int(xs.mean() * E) + ox
            py = oy + 119 * E
            cv2.circle(img, (px, py - 4), 7, CELESTE, -1)
            cv2.arrowedLine(img, (ox + int(CENTRO * E), py - 4), (px, py - 4), CELESTE, 2, tipLength=0.3)

        # el centroide GLOBAL, que es el que la vision usa
        ys, xs = np.nonzero(m)
        if len(xs):
            gx, gy = int(xs.mean() * E) + ox, int(ys.mean() * E) + oy
            cv2.drawMarker(img, (gx, gy), AMARILLO, cv2.MARKER_CROSS, 22, 2)

        e = est[i]
        cv2.putText(img, "%s  frame %d" % (os.path.basename(ruta), i), (20, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, BLANCO, 1, cv2.LINE_AA)
        y0 = oy + H * E + 26
        txt = ("cinta DEBAJO del robot: %+5.1f px" % desv) if desv is not None \
            else "NO HAY CINTA DEBAJO DEL ROBOT"
        cv2.putText(img, txt, (20, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    CELESTE if desv is not None else ROJO, 1, cv2.LINE_AA)
        if desv is None:
            descentrado += 1
        cv2.putText(img, "angulo %+6.1f gr    rot %+.2f    %s" %
                    (ang[i], e["rot"], "PIVOTE ENGANCHADO" if e["piv"] else "avanza girando"),
                    (20, y0 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    AMARILLO if e["piv"] else GRIS, 1, cv2.LINE_AA)

        bx, bw = 20, ANCHO - 40
        cx = bx + bw // 2
        cv2.rectangle(img, (bx, y0 + 40), (bx + bw, y0 + 66), (55, 55, 55), 1)
        cv2.line(img, (cx, y0 + 40), (cx, y0 + 66), GRIS, 1)
        nn = int(abs(e["rot"]) * (bw // 2))
        if nn > 1:
            p, q = (cx, cx + nn) if e["rot"] > 0 else (cx - nn, cx)
            cv2.rectangle(img, (p, y0 + 42), (q, y0 + 64),
                          AMARILLO if e["piv"] else GRIS, -1)
        if e["suelta"]:
            n_suelta += 1
            cv2.rectangle(img, (10, 10), (ANCHO - 10, ALTO - 10), ROJO, 3)
            cv2.putText(img, "SUELTA EL PIVOTE  (#%d)" % n_suelta, (20, ALTO - 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, ROJO, 2, cv2.LINE_AA)
        vw.write(img)
        escritos += 1

    vw.release()
    print("  %s: %d frames escritos en %s" % (os.path.basename(ruta), escritos, sal))
    print("  sueltas de pivote marcadas: %d" % n_suelta)
    print("  frames SIN cinta debajo del robot: %d (%.0f%%)"
          % (descentrado, 100.0 * descentrado / max(escritos, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
