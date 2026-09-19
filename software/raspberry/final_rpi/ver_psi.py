# -*- coding: utf-8 -*-
"""
VER psi. Cuando dos instrumentos discrepan y ninguno es de referencia, se mira.

El estimador de rumbo da p50 |psi| = 44 grados sobre 12.000 frames. El control
externo -yaw por correlacion de fase- no lo confirma NI lo refuta, porque el
control mismo es debil: da 1.075 frames por encima de 80 grados/s en un robot
cuyo techo medido es 39.

Asi que se mira la imagen. Se eligen frames en distintos niveles de |psi| y se
dibuja lo que el estimador esta viendo: la componente, el esqueleto, el camino
que Dijkstra reconstruyo, el start, el target y la direccion psi como flecha.

Si con |psi| = 45 la cinta se ve derecha adelante, el estimador esta roto.
Si se ve doblando 45 grados, el numero es real y el sistema opera asi.
"""

import argparse
import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

ESC = 4


def panel(g, r, psi, e, titulo):
    vis = cv2.resize(g, (LS.W * ESC, LS.H * ESC),
                     interpolation=cv2.INTER_NEAREST)
    vis = (vis * 0.45).astype(np.uint8)

    if r.get("comp") is not None:
        m = cv2.resize(r["comp"], (LS.W * ESC, LS.H * ESC),
                       interpolation=cv2.INTER_NEAREST)
        vis[m > 0] = (0.5 * vis[m > 0] + np.array([20, 90, 20])).astype(np.uint8)
    if r.get("skel") is not None:
        m = cv2.resize(r["skel"], (LS.W * ESC, LS.H * ESC),
                       interpolation=cv2.INTER_NEAREST)
        vis[m > 0] = (0, 200, 255)

    path = r.get("path") or []
    if len(path) >= 2:
        q = np.asarray([[int(x * ESC), int(y * ESC)] for x, y in path], np.int32)
        cv2.polylines(vis, [q], False, (255, 160, 60), 2)

    st = r.get("start")
    tg = r.get("target")
    if st:
        cv2.circle(vis, (int(st[0] * ESC), int(st[1] * ESC)), 6, (255, 90, 40), -1)
    if tg:
        p = (int(tg[0] * ESC), int(tg[1] * ESC))
        cv2.drawMarker(vis, p, (255, 255, 255), cv2.MARKER_TILTED_CROSS, 16, 2)

    # el punto del camino donde se cierra el arco de tangente
    if st and len(path) >= 2:
        P = [LS.suelo(x, y) for x, y in path]
        acum, j = 0.0, 0
        for i in range(1, len(P)):
            acum += math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1])
            j = i
            if acum >= LS.ARCO_PSI:
                break
        pj = path[j]
        cv2.circle(vis, (int(pj[0] * ESC), int(pj[1] * ESC)), 5, (60, 255, 255), 2)
        cv2.line(vis, (int(st[0] * ESC), int(st[1] * ESC)),
                 (int(pj[0] * ESC), int(pj[1] * ESC)), (60, 255, 255), 1)

    # eje del robot
    cv2.line(vis, (int(LS.CENTER * ESC), LS.H * ESC),
             (int(LS.CENTER * ESC), 0), (120, 120, 120), 1)

    cv2.rectangle(vis, (0, 0), (LS.W * ESC, 34), (0, 0, 0), -1)
    cv2.putText(vis, titulo, (5, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.34,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(vis, "psi %+.1f   e %+.3f   steer_viejo %+.1f"
                % (psi, e, LS.steer_actual(r) or 0.0),
                (5, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.34,
                (80, 255, 255), 1, cv2.LINE_AA)
    return vis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="hist.avi")
    ap.add_argument("--salida", default="ver_psi.png")
    ap.add_argument("--niveles", default="5,20,35,50,65,85")
    a = ap.parse_args()

    datos = SP.extraer()
    filas = datos[a.video]
    cand = []
    for f in filas:
        if f["target"] is None:
            continue
        e, psi = LS.errores(f)
        if psi is None:
            continue
        cand.append((f["i"], abs(psi), psi, e))

    objetivos = [float(x) for x in a.niveles.split(",")]
    elegidos = []
    for o in objetivos:
        best = min(cand, key=lambda c: abs(c[1] - o))
        elegidos.append(best)
        cand = [c for c in cand if abs(c[0] - best[0]) > 15]
    print("  frames elegidos: %s"
          % ", ".join("f%d(|psi|=%.1f)" % (c[0], c[1]) for c in elegidos))

    vl, v2 = SP._produccion()
    vl._tr = None
    vl._arrancar()
    quiero = {c[0]: c for c in elegidos}
    salidas = {}
    cap = cv2.VideoCapture(os.path.join(AQUI, a.video))
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = v2.frame_pi(fr)
        r = vl._tr.step(g)
        if i in quiero:
            _idx, ap_, psi, e = quiero[i]
            salidas[i] = panel(g, r, psi, e, "%s  f%d" % (a.video, i))
        i += 1
    cap.release()

    orden = [salidas[c[0]] for c in elegidos if c[0] in salidas]
    fila1 = np.hstack(orden[:3])
    fila2 = np.hstack(orden[3:6])
    out = np.vstack([fila1, fila2])
    cv2.imwrite(os.path.join(AQUI, a.salida), out)
    print("  escrito %s  (%dx%d)" % (a.salida, out.shape[1], out.shape[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
