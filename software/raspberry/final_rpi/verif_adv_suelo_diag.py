# -*- coding: utf-8 -*-
"""VERIFICADOR ADVERSARIO - diagnostico independiente del mecanismo de SUELO.

Reimplementa desde cero (sin importar wf_suelo_camino) el conteo que el reporte
afirma haber medido en un "pase aparte":
  - frames con shell geodesica en los 10 autonomos
  - cuantas veces cambia el nodo F (mas lejano) de metrica pixel a metrica suelo
  - cuantas veces la shell de SUELO queda vacia -> fallback
  - candidatos por frame en cada metrica
No modifica ningun archivo compartido.
"""
import heapq, importlib.util, math, os, sys
import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
V_H = 9.0
HFOV = 60.0
SH_LO, SH_HI = 0.77, 1.26
LD60 = 0.735          # el que calibra pursuit.py --medir --hfov 60

CAP = {}
ACC = dict(n=0, f_dist=0, shell_vacia_suelo=0, shell_vacia_px=0,
           cp=[], cs=[], ymin=[], zmax=[])


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3.v2


def sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SB(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SB


def dij_suelo(adj, start, PX, PZ):
    n = len(adj)
    dist = [float("inf")] * n
    prev = [-1] * n
    dist[start] = 0.0
    pq = [(0.0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]:
            continue
        x0, z0 = PX[u], PZ[u]
        for v, _w in adj[u]:
            nd = d + math.hypot(PX[v] - x0, PZ[v] - z0)
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return np.asarray(dist), prev


def instalar(v2):
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    f_px = (v2.W / 2.0) / math.tan(math.radians(HFOV / 2.0))

    def g(sk):
        r = o_g(sk)
        CAP["pts"], CAP["adj"] = r[0], r[1]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["si"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        CAP.clear()
        sk, res = o_p(self, comp, mode)
        if res is None or "dist" not in CAP or mode.startswith("AHEAD"):
            return sk, res
        pts, adj = CAP["pts"], CAP["adj"]
        dist, si = CAP["dist"], CAP["si"]
        sy, sx = pts[si]
        ys = np.array([q[0] for q in pts], float)
        xs = np.array([q[1] for q in pts], float)
        zz = (119.0 - V_H) / np.maximum(ys - V_H, 1e-6)
        PX = ((xs - v2.CENTER) * zz / f_px)
        ds, _pp = dij_suelo(adj, si, PX.tolist(), zz.tolist())

        ACC["n"] += 1
        ACC["ymin"].append(float(ys.min()))
        ACC["zmax"].append(float(zz.max()))
        fp = np.where(np.isfinite(dist))[0]
        fs = np.where(np.isfinite(ds))[0]
        if len(fp) and len(fs):
            Fp = int(fp[int(np.argmax(dist[fp]))])
            Fs = int(fs[int(np.argmax(ds[fs]))])
            if Fp != Fs:
                ACC["f_dist"] += 1
        lo_p, hi_p = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        cp = [i for i in fp if lo_p <= dist[i] <= hi_p and pts[i][0] <= sy + 3]
        lo_s, hi_s = LD60 * SH_LO, LD60 * SH_HI
        cs = [i for i in fs if lo_s <= ds[i] <= hi_s and pts[i][0] <= sy + 3]
        ACC["cp"].append(len(cp))
        ACC["cs"].append(len(cs))
        if not cp:
            ACC["shell_vacia_px"] += 1
        if not cs:
            ACC["shell_vacia_suelo"] += 1
        return sk, res

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def rest():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p
    return rest


def main():
    v4, v2 = cargar()
    SB = sinbranch(v4)
    rest = instalar(v2)
    for vid in AB.AUTONOMOS:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru):
            continue
        cap = cv2.VideoCapture(ru)
        tr = SB(FPS)
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            tr.step(v2.frame_pi(fr))
        cap.release()
    rest()
    n = ACC["n"]
    cp = np.array(ACC["cp"])
    cs = np.array(ACC["cs"])
    print("")
    print("  DIAGNOSTICO INDEPENDIENTE  (10 autonomos, HFOV %.0f, ld %.3f)" % (HFOV, LD60))
    print("  frames con shell geodesica ............ %d" % n)
    print("  nodo F distinto pixel vs suelo ........ %d  (%.1f %%)"
          % (ACC["f_dist"], 100.0 * ACC["f_dist"] / max(n, 1)))
    print("  shell de SUELO vacia -> fallback ...... %d  (%.1f %%)"
          % (ACC["shell_vacia_suelo"], 100.0 * ACC["shell_vacia_suelo"] / max(n, 1)))
    print("  shell de PIXEL vacia -> fallback ...... %d  (%.1f %%)"
          % (ACC["shell_vacia_px"], 100.0 * ACC["shell_vacia_px"] / max(n, 1)))
    print("  candidatos pixel  p50 %d   media %.1f" % (np.median(cp), cp.mean()))
    print("  candidatos suelo  p50 %d   media %.1f" % (np.median(cs), cs.mean()))
    print("  fila minima del esqueleto: min %.0f  p01 %.0f   (FLOOR_TOP=35)"
          % (min(ACC["ymin"]), np.percentile(ACC["ymin"], 1)))
    print("  Z maximo por frame: p50 %.2f  max %.2f  (Z(119)=1)"
          % (np.median(ACC["zmax"]), max(ACC["zmax"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
