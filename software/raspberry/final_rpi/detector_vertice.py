# -*- coding: utf-8 -*-
"""EL DETECTOR DE CODO QUE FUNCIONA: el VERTICE de la L sobre la cadena.

Idea de Benjamin, 26-ago, mirando el render de la cadena: "el vertice de la L
esta DENTRO de la cadena, dibujado, antes de que el robot llegue. A esa
distancia es donde ya tendrian que empezar a curvarse".

RESULTADO, sobre hist.avi (2091 frames, 1,74 min):

    ang40 >= 45 grados  y  residuos <= 2,0 px
       ->  9 eventos, 5,2 por minuto
       ->  Benjamin clasifico 8 de los 9 (V6 quedo sin juzgar): LOS 8 SON
           CODOS. Precision 8/8 sobre lo juzgado, no 9/9.

Y eso corrige el falsador que yo mismo habia preregistrado: el limite de
6 eventos/min estaba MAL CALIBRADO. No eran falsos positivos: la pista TIENE
unos 5 codos por minuto. Los dos detectores anteriores (16,2 y 17,0 ev/min)
si disparaban de mas; este esta en la tasa real.

POR QUE ESTE FUNCIONA Y LOS DOS ANTERIORES NO
---------------------------------------------
Los dos muertos median CURVATURA LOCAL punto a punto sobre el eje medial. En
la fila 115 la cinta ocupa 71 px de 160 y el eje medial se desvia +-35 px sin
que la cinta doble: el ruido era mayor que la senal.

Ajustar DOS RECTAS a tramos largos de la cadena promedia ese ruido: un ajuste
sobre 20 puntos no se mueve porque uno se corra 35 px. Y es exactamente lo que
NO-ROMPER-LA-CADENA-UNICA.md autoriza -"ajustar dos rectas a tramos de cad,
cerca y lejos"-, porque trabaja sobre la cadena que CAMINO ya eligio y nunca
sobre el esqueleto crudo.

UN ERROR QUE HUBO QUE CORREGIR, Y ES EL DE SIEMPRE
--------------------------------------------------
La primera version buscaba el corte que MAXIMIZA el angulo. Un maximizador
siempre encuentra algo: daba mediana 46 grados, o sea "la mitad de los frames
tienen un codo de 46 grados", falso por construccion. Con corte FIJO la
mediana bajo a 22,3, que ya es creible, y recien ahi el detector sirvio.
Es el mismo error #7 del traspaso: una metrica de eventos rota da veredictos
seguros y equivocados.

Y LO QUE MAS IMPORTA PARA EL CONTROL, que lo vio Benjamin:
    "todos son codos, lo que cambia es la CERRADA"

    V4 f743  ang=58   codo cerrado
    V2 f590  ang=55
    V9 f2054 ang=51
    V7 f1362 ang=42   codo suave
    V5 f881  ang=40
    V3 f647  ang=25   apenas dobla

El angulo NO es solo un detector: MIDE CUANTO HAY QUE GIRAR. Y `s_max` /
`flecha` dan la distancia al vertice, que es CUANDO. Los dos numeros que le
faltaban a la maniobra de codo del firmware.

QUE MIDE, por frame
    ang40   angulo entre la recta del primer 40 % de la cadena y la del ultimo
            40 %. Cortes FIJOS: no se maximiza nada.
    res_c   residuo del ajuste del tramo CERCA (px). Alto = no es una recta.
    res_l   residuo del ajuste del tramo LEJOS
    s_max   a que fraccion del largo esta el vertice (0 = pegado al robot).
            Es el CUANDO.
    flecha  cuanto se aparta el vertice de la recta robot->punta, en px
    fila_v  fila de imagen del vertice. Mas abajo = mas cerca del robot.

Un codo de verdad: ang40 grande Y los dos residuos CHICOS -son dos rectas que
se cruzan-. Ruido: ang40 grande pero residuos altos.

    python detector_vertice.py        # recalcula la serie sobre hist.avi
"""
import os
import sys

import cv2
import numpy as np

AQUI = r'C:\Users\villa\rcj-2026-rescue-line-iita-salta-robocup-priority-fixes\software\raspberry\final_rpi'
CACHE = r'C:\Users\villa\AppData\Local\Temp\claude\C--Users-villa-rcj-2026-rescue-line-iita-salta-robocup-priority-fixes\bd0705db-2741-4fd1-a38a-62e71bc7303b\scratchpad\serie_vert2.npz'

os.environ.setdefault("VISION_LINEA", "camino")
sys.path.insert(0, AQUI)
import vision_linea as VL


def panel(fr):
    h, w = fr.shape[:2]
    if (w, h) == (640, 240):
        fr = fr[:, :w // 2]
    return cv2.resize(fr, (160, 120), interpolation=cv2.INTER_NEAREST)


def ajuste(P):
    """Direccion principal y residuo perpendicular medio, por PCA."""
    A = np.asarray(P, float)
    if len(A) < 5:
        return None, np.nan
    m = A.mean(axis=0)
    B = A - m
    _, S, V = np.linalg.svd(B, full_matrices=False)
    d = V[0]
    perp = np.array([-d[1], d[0]])
    res = float(np.abs(B @ perp).mean())
    return d, res


def medir(cad, pts):
    n = len(cad)
    if n < 24:
        return None
    P = np.array([(pts[i][1], pts[i][0]) for i in cad], float)
    k1 = int(n * 0.40)
    k2 = int(n * 0.60)
    d1, r1 = ajuste(P[:k1])
    d2, r2 = ajuste(P[k2:])
    if d1 is None or d2 is None:
        return None
    c = min(1.0, max(-1.0, abs(float(np.dot(d1, d2)))))
    ang = float(np.degrees(np.arccos(c)))
    # donde esta el punto de la cadena mas lejos de la recta robot->punta:
    # si hay una L, el vertice es el punto de maxima flecha
    v = P[-1] - P[0]
    L = np.hypot(*v)
    if L > 1e-6:
        nrm = np.array([-v[1], v[0]]) / L
        flecha = np.abs((P - P[0]) @ nrm)
        j = int(np.argmax(flecha))
        s_max = j / float(n)
        f_max = float(flecha[j])
        fila_v = float(P[j][1])
    else:
        s_max = f_max = fila_v = np.nan
    return ang, r1, r2, s_max, f_max, fila_v, float(n)


def main():
    cap = cv2.VideoCapture(os.path.join(AQUI, 'hist.avi'))
    cols = {k: [] for k in ("ang", "res_c", "res_l", "s_max", "flecha", "fila_v", "npts")}
    n = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        try:
            VL.angulo(panel(fr))
        except Exception:
            pass
        v = None
        cp = VL._CP
        if cp is not None and "dist" in cp.CAP:
            pts, dist = cp.CAP["pts"], cp.CAP["dist"]
            prev, si = cp.CAP["prev"], cp.CAP["si"]
            fin = np.where(np.isfinite(dist))[0]
            if len(fin) >= 8:
                F = int(fin[int(np.argmax(dist[fin]))])
                cad = VL._v2.reconstruct(prev, si, F)
                if cad:
                    v = medir(cad, pts)
        vals = v if v else (np.nan,) * 7
        for k, x in zip(("ang", "res_c", "res_l", "s_max", "flecha", "fila_v", "npts"), vals):
            cols[k].append(x)
        n += 1
        if n % 400 == 0:
            print("   %d..." % n)
    cap.release()
    np.savez(CACHE, **{k: np.array(v) for k, v in cols.items()})
    print("guardado %d frames" % n)


if __name__ == "__main__":
    main()
