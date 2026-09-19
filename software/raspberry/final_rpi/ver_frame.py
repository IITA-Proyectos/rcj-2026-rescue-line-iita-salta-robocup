# -*- coding: utf-8 -*-
"""VERIFICAR una afirmacion sobre un frame concreto. NO TOCA EL ROBOT.

Se dibujan TODAS las componentes del ROI con su area y su rango de filas, se
marca con borde blanco la que V2 eligio, y se pone el target. Si no existe otra
componente que sea mejor candidata a "la cinta", la afirmacion de que la
elegida es la equivocada es FALSA y hay que retirarla.

Uso
---
    python ver_frame.py hist.avi 1405 1409 1413 1417
"""

import argparse
import importlib.util
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
_sp = importlib.util.spec_from_file_location(
    "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
v4 = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(v4)
v2 = v4.v3.v2

COLS = [(0, 0, 255), (0, 255, 0), (255, 80, 0), (0, 255, 255),
        (255, 0, 255), (255, 255, 0), (120, 120, 255)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("frames", nargs="+", type=int)
    ap.add_argument("--fps", type=float, default=None)
    ap.add_argument("--salida", default="ver_frame")
    a = ap.parse_args(argv)

    ruta = a.video if os.path.exists(a.video) else os.path.join(AQUI, a.video)
    fps = a.fps if a.fps else (20.0 if "video_4" in os.path.basename(ruta)
                               else 100.0 / 3.0)
    want = set(a.frames)
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = v4.NuevoCodeV4(fps)
    i = 0
    hechos = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > max(want):
            break
        g = v2.frame_pi(fr)
        r = tr.step(g)
        if i in want:
            m = v2.mask_linea(g)
            n, lab, st, _cen = cv2.connectedComponentsWithStats(
                (m > 0).astype(np.uint8), 8)
            vis = np.zeros((v2.H, v2.W, 3), np.uint8)
            info = []
            for k in range(1, n):
                ar = int(st[k, cv2.CC_STAT_AREA])
                if ar < v2.MIN_AREA:
                    continue
                c = COLS[(k - 1) % len(COLS)]
                vis[lab == k] = c
                mm = (lab == k)
                y0 = int(st[k, cv2.CC_STAT_TOP])
                y1 = y0 + int(st[k, cv2.CC_STAT_HEIGHT]) - 1
                info.append((k, ar, y0, y1, int(st[k, cv2.CC_STAT_WIDTH]),
                             int(st[k, cv2.CC_STAT_HEIGHT]),
                             int(mm[110:120].sum()) >= 8, c))
            comp = r.get("comp")
            if comp is not None:
                cc = (comp > 0).astype(np.uint8)
                borde = cv2.dilate(cc, np.ones((3, 3), np.uint8)) - cc
                vis[borde > 0] = (255, 255, 255)
            t = r.get("target")
            if t is not None:
                cv2.drawMarker(vis, (int(round(t[0])), int(round(t[1]))),
                               (255, 255, 255), cv2.MARKER_TILTED_CROSS, 13, 2)
            cv2.line(vis, (0, 60), (v2.W - 1, 60), (100, 100, 100), 1)
            cv2.line(vis, (0, v2.FLOOR_TOP), (v2.W - 1, v2.FLOOR_TOP), (60, 60, 60), 1)
            par = np.hstack([g, vis])
            par = cv2.resize(par, (960, 360), interpolation=cv2.INTER_NEAREST)
            cv2.putText(par, "frame %d   %s   %s   target %s"
                        % (i, r["state"], r.get("mode", ""),
                           "--" if t is None else "(%.0f,%.0f)" % t),
                        (6, 20), cv2.FONT_HERSHEY_SIMPLEX, .6,
                        (255, 255, 255), 1, cv2.LINE_AA)
            y = 46
            for k, ar, y0, y1, w, h, near, c in sorted(info, key=lambda z: -z[1])[:6]:
                cv2.putText(par, "comp%d  area=%-5d filas %3d-%3d  %2dx%-3d  near=%s"
                            % (k, ar, y0, y1, w, h, near),
                            (6, y), cv2.FONT_HERSHEY_SIMPLEX, .44, c, 1, cv2.LINE_AA)
                y += 19
            cv2.putText(par, "borde blanco = la ELEGIDA por V2   |   linea gris = fila 60",
                        (6, y + 4), cv2.FONT_HERSHEY_SIMPLEX, .42,
                        (255, 255, 255), 1, cv2.LINE_AA)
            out = os.path.join(AQUI, "%s_%d.png" % (a.salida, i))
            cv2.imwrite(out, par)
            print("  %s   comps=%d   estado=%s" % (os.path.basename(out),
                                                   len(info), r["state"]))
            hechos += 1
        i += 1
    cap.release()
    print("  %d frames escritos" % hechos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
