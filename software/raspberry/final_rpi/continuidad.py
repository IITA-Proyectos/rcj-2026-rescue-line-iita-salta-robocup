# -*- coding: utf-8 -*-
"""H8: el peso de continuidad del score de `path_target`. NO TOCA EL ROBOT.

De donde sale
-------------
H6a gano: las ramas del esqueleto son topologia REAL (acuerdo de posicion 0,917
bajo perturbacion). Entonces el problema no es limpiar la mascara sino ELEGIR
por cual rama sigue la trayectoria, y eso ya existe en el codigo. El score de
`nuevo_code_v2.py:289-298` tiene cuatro terminos y uno es continuidad:

    s  = 0.35 * |dist - LOOKAHEAD|                 llegar a 70 px
       + 0.55 * angdiff(heading, prev_heading)     mantener el rumbo
       + 0.10 * dist(punto, prev_target)           <-- CONTINUIDAD, peso 0,10
       + 0.30 * max(0, 8 - dy)                     no elegir algo pegado al start

H8: el termino de continuidad pesa 0,10 y por eso la eleccion se va de rama.

Como se prueba sin caer en tuning
---------------------------------
No se busca "el mejor peso". Se BARRE y se mira la FORMA de la curva:

  * meseta amplia donde el salto baja y los controles siguen en 100/100 y 73/73
    -> el efecto es robusto y el peso original es bajo;
  * pico agudo -> sobreajuste a estos diez videos, no se toca nada;
  * curva plana -> H8 cae, el peso no es la palanca.

La regla 10 del HANDOFF original prohibe ajustar una ganancia porque mejora una
metrica offline. Este banco NO propone un valor: mide la forma y reporta.

Autovalidacion
--------------
La copia parametrizada de `path_target` tiene que reproducir EXACTAMENTE el
original con w = 0,10. Si no coincide al 100 %, la copia esta mal y nada de lo
que sigue vale. Se imprime y se aborta.

Uso
---
    python continuidad.py
"""

import argparse
import importlib.util
import math
import os
import sys

import numpy as np
import cv2
from skimage.morphology import skeletonize

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
_sp = importlib.util.spec_from_file_location(
    "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
v4 = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(v4)
v3 = v4.v3
v2 = v4.v3.v2

from ab_v2_v3_v4 import metricas, AUTONOMOS, CONTROLES, FPS   # noqa: E402


class PercCont(v3.PercepcionV3):
    """PercepcionV3 con el peso de continuidad abierto.

    `path_target` es copia literal de `nuevo_code_v2.py:237-314` con UNA sola
    diferencia: el 0.10 pasa a ser `self.w_cont`. Se hereda de PercepcionV3 para
    conservar su `choose_component`, que es lo que corre hoy.
    """

    def __init__(self, fps, w_cont=0.10):
        v3.PercepcionV3.__init__(self, fps)
        self.w_cont = float(w_cont)

    def path_target(self, comp, mode):
        if mode == "NEAR_BRANCH_LOCK":
            mode = "NEAR"
        sk = skeletonize(comp > 0)
        pts, adj, deg = v2.graph_from_skeleton(sk)
        if len(pts) < 2:
            return sk, None
        arr = np.array([(x, y) for y, x in pts], float)
        maxy = max(y for y, x in pts)

        if mode == "NEAR":
            cand = [i for i, (y, x) in enumerate(pts) if y >= maxy - 8]
            row_x = np.where(comp[min(119, int(round(maxy)))] > 0)[0]
            bruns = v2.runs_1d(row_x)
            ys_all, xs_all = np.nonzero(comp > 0)
            width = (xs_all.max() - xs_all.min() + 1) if len(xs_all) else 0
            if len(bruns) >= 2 or width >= 0.85 * v2.W:
                run = (min(bruns, key=lambda r: abs(((r[0] + r[1]) / 2) - v2.CENTER))
                       if bruns else (v2.CENTER, v2.CENTER))
                rc = (run[0] + run[1]) / 2
                start = min(cand, key=lambda i: abs(arr[i, 0] - rc)
                            + 0.2 * abs(arr[i, 1] - maxy))
            else:
                start = min(cand, key=lambda i: (arr[i, 0] - self.prev_entry[0]) ** 2
                            + (arr[i, 1] - self.prev_entry[1]) ** 2)
        else:
            cand = [i for i, (y, x) in enumerate(pts) if y >= maxy - 3]
            ref = self.prev_target if self.prev_target is not None else self.prev_entry
            start = min(cand, key=lambda i: (arr[i, 0] - ref[0]) ** 2
                        + (arr[i, 1] - ref[1]) ** 2)

        sy, sx = pts[start]
        dist, prev = v2.dijkstra(adj, start)
        finite = np.where(np.isfinite(dist))[0]
        if not len(finite):
            return sk, None
        simple = "AHEAD" if mode.startswith("AHEAD") else mode

        if simple == "AHEAD":
            cands = [i for i in finite if pts[i][0] >= maxy - 4]
            if not cands:
                cands = [start]
            ref = self.prev_target if self.prev_target is not None else (sx, sy)
            target_idx = min(cands, key=lambda i: (pts[i][1] - ref[0]) ** 2
                             + (pts[i][0] - ref[1]) ** 2)
            path_idx = [start, target_idx] if target_idx != start else [start]
        else:
            lo = max(18, v2.LOOKAHEAD - 16)
            hi = v2.LOOKAHEAD + 18
            cands = [i for i in finite if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
            if not cands:
                cands = sorted(finite, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
                    :min(30, len(finite))]

            def score(i):
                y, x = pts[i]
                dy = sy - y
                heading = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
                s = 0.35 * abs(dist[i] - v2.LOOKAHEAD)
                s += 0.55 * v2.angdiff(heading, self.prev_heading)
                if self.prev_target is not None:
                    s += self.w_cont * math.hypot(x - self.prev_target[0],
                                                  y - self.prev_target[1])
                s += 0.30 * max(0, 8 - dy)
                return s

            target_idx = min(cands, key=score)
            path_idx = v2.reconstruct(prev, start, target_idx)
            if not path_idx:
                path_idx = [start, target_idx]

        ty, tx = pts[target_idx]
        heading = math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6)))
        path = [(float(pts[i][1]), float(pts[i][0])) for i in path_idx]
        return sk, dict(start=(float(sx), float(sy)),
                        target=(float(tx), float(ty)),
                        heading=heading, path=path)


def hacer(w):
    """V4 completo pero con la percepcion parametrizada."""
    class C(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.per = PercCont(fps, w)
    return C


def corrida(cls, ruta, fps, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = cls(fps)
    out = []
    i = 0
    W, C = v2.W, v2.CENTER
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        g = v2.frame_pi(fr)
        r = tr.step(g)
        if i >= desde:
            t = r.get("target")
            s = (None if t is None
                 else float(np.clip(-90.0 * (t[0] - C) / (W / 2.0), -90, 90)))
            out.append((t, s, r.get("state")))
        i += 1
    cap.release()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)

    print("")
    print("=" * 84)
    print(" H8: BARRIDO DEL PESO DE CONTINUIDAD   (el original es 0,10)")
    print(" No se busca el mejor valor: se mira la FORMA de la curva.")
    print("=" * 84)

    base = corrida(v4.NuevoCodeV4, os.path.join(AQUI, "hist.avi"), FPS, 0, 400)
    copia = corrida(hacer(0.10), os.path.join(AQUI, "hist.avi"), FPS, 0, 400)
    ig = 0
    for a, b in zip(base, copia):
        if (a[0] is None) != (b[0] is None):
            continue
        if a[0] is None or (abs(a[0][0] - b[0][0]) < 1e-9
                            and abs(a[0][1] - b[0][1]) < 1e-9):
            ig += 1
    print("")
    print("  AUTOVALIDACION w=0,10 contra el original: %d/%d (%.1f %%)  %s"
          % (ig, len(base), 100.0 * ig / max(len(base), 1),
             "OK" if ig == len(base) else "*** MAL, no usar el resto ***"))
    if ig != len(base):
        return 1

    print("")
    print("  %-6s %9s %7s %7s %7s %6s %7s | %s"
          % ("w", "disp", "s/aut", "huecos", ">24px", "inv", "suav", "controles"))
    for w in (0.0, 0.10, 0.25, 0.50, 1.0, 2.0):
        cls = hacer(w)
        t = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, su=[])
        for vid in AUTONOMOS:
            r = os.path.join(AQUI, vid)
            if not os.path.exists(r):
                continue
            m = metricas(corrida(cls, r, FPS))
            for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
                t[k] += m[k]
            t["su"].append(m["suav"])
        disp = 100.0 * t["con"] / max(t["n"], 1)
        ctrl, ok = [], True
        for nom, vid, fps, d, h, ex in CONTROLES:
            rr = os.path.join(AQUI, vid)
            if not os.path.exists(rr) or not ex:
                continue
            m = metricas(corrida(cls, rr, fps, d, h))
            ctrl.append("%d/%d" % (m["con"], ex))
            ok = ok and (m["con"] >= ex)
        print("  %-6.2f %8.2f %% %7d %7d %7d %6d %7.2f | %s %s"
              % (w, disp, t["sin_aut"], t["huecos"], t["s_gt"], t["inv"],
                 float(np.mean(t["su"])), " ".join(ctrl),
                 "PASA" if ok else "*** FALLA ***"))

    print("")
    print("  LECTURA")
    print("  meseta amplia -> el efecto es robusto y 0,10 es bajo")
    print("  pico agudo    -> sobreajuste a estos diez videos, no tocar nada")
    print("  curva plana   -> H8 cae, el peso no es la palanca")
    return 0


if __name__ == "__main__":
    sys.exit(main())
