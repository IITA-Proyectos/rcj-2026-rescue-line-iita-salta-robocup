# -*- coding: utf-8 -*-
"""
PURSUIT - los dos P0 de vision que salieron de la auditoria profunda.

No son hipotesis nuevas: son dos defectos identificados contra literatura, con
arreglo publicado. Se implementan por separado para poder atribuir el efecto.

============================================================================
 V1 - BUSQUEDA MONOTONA HACIA ADELANTE      (Coulter 1992, CMU-RI-TR-92-01)
============================================================================
El paper original de pure pursuit especifica el orden de operaciones:

  "The path point closest to the vehicle will first be found, and the search
   for a point 1 lookahead distance away from the vehicle will start at this
   point and commence up the path."

Primero el punto mas cercano, despues se avanza MONOTONAMENTE HACIA ADELANTE.
Nunca una busqueda global por distancia.

Nuestro `path_target` hace busqueda global: cualquier nodo a distancia geodesica
en [54,88] es candidato, y nada distingue adelante de atras. Por eso el target
puede caer sobre el pedazo de cinta YA RECORRIDO (H10, medido y confirmado).

IMPLEMENTACION: el ancla es el punto del esqueleto actual mas cercano al target
del frame anterior -"the path point closest to the vehicle"-. Un candidato es
admisible solo si el ancla esta en su camino desde `start`, o sea si el ancla es
ANCESTRO del candidato en el arbol de Dijkstra. Eso es exactamente "commence up
the path".

Sin target previo (arranque, reacquisicion) NO hay restriccion: es lo que dice
el paper, se vuelve a encontrar el punto mas cercano.

============================================================================
 V2 - LOOKAHEAD EN UNIDADES DEL SUELO       (Snider 2009, CMU-RI-TR-09-08)
============================================================================
Pure pursuit es un proporcional con ganancia 2/ld^2. Si `ld` no es una distancia
fisica, la ganancia del lazo es una variable desconocida.

`LOOKAHEAD = 70` son 70 PIXELES geodesicos, y con la camara casi horizontal la
escala pixel->suelo varia hasta 300x dentro del cuadro. Medido: la distancia
real al suelo del target varia 2,3x entre p05 y p95. Como la ganancia va al
cuadrado, la ganancia varia 5,3x.

IMPLEMENTACION: se cambian los PESOS DE LAS ARISTAS del grafo del esqueleto. En
vez de 1 y raiz(2) pixeles, cada arista pesa su longitud EN EL SUELO:

    Z(v) = (119 - v_h) / (v - v_h)          en unidades de Z(fila 119)
    X(u,v) = (u - cx) * Z(v) / f_px
    peso = hypot(dX, dZ)

Asi la shell geodesica pasa a ser una shell de distancia real. Dijkstra,
skeletonize y el resto no se tocan.

============================================================================
 GARANTIA DE FIDELIDAD
============================================================================
El selector se re-implementa dentro del espia para poder aplicar la restriccion.
Con las dos variantes APAGADAS tiene que reproducir EXACTAMENTE el target de la
candidata en cada frame. Se verifica y se reporta; si hay una sola discrepancia,
aborta. Sin eso, el A/B no mide lo que dice medir.

NO MODIFICA V2/V3/V4. Espia reversible sobre `path_target`.

    python3 pursuit.py --medir     # calibra el lookahead de suelo equivalente
    python3 pursuit.py             # A/B preregistrado de las 4 variantes
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

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
V_H = 9.0                 # fila del horizonte, medida en birdeye.py (R2 .98-.99)
HFOV_DEF = 60.0           # campo horizontal supuesto. NO calibrado: ver --hfov

CAP = {}
CHK = {"n": 0, "mal": 0}


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


# --------------------------------------------------------------------------
# METRICA DEL SUELO
# --------------------------------------------------------------------------
def hacer_suelo(v2, hfov):
    f_px = (v2.W / 2.0) / math.tan(math.radians(hfov / 2.0))

    def z(v):
        return (119.0 - V_H) / max(v - V_H, 1e-6)

    def xz(u, v):
        zz = z(v)
        return ((u - v2.CENTER) * zz / f_px, zz)
    return xz


def dijkstra_suelo(pts, adj, start, xz):
    """Mismo Dijkstra, pesos en unidades de suelo en vez de pixeles."""
    import heapq
    n = len(pts)
    dist = [float("inf")] * n
    prev = [-1] * n
    dist[start] = 0.0
    pq = [(0.0, start)]
    P = [xz(x, y) for y, x in pts]
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]:
            continue
        x0, z0 = P[u]
        for v, _w in adj[u]:
            x1, z1 = P[v]
            nd = d + math.hypot(x1 - x0, z1 - z0)
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return np.asarray(dist), prev


def es_ancestro(prev, ancla, cand):
    """True si `ancla` esta en el camino desde start hasta `cand`."""
    x = cand
    guard = 0
    while x != -1 and guard < 5000:
        if x == ancla:
            return True
        x = prev[x]
        guard += 1
    return False


# --------------------------------------------------------------------------
# ESPIA
# --------------------------------------------------------------------------
def instalar(v2, cfg, medidas=None):
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    o_r = v2.reconstruct
    xz = cfg["xz"]

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
        dist, prev, si = CAP["dist"], CAP["prev"], CAP["si"]
        sy, sx = pts[si]

        # --- V2: metrica del suelo -------------------------------------
        if cfg["suelo"]:
            dist, prev = dijkstra_suelo(pts, adj, si, xz)
            lo, hi = cfg["lo_suelo"], cfg["hi_suelo"]
            obj = cfg["ld_suelo"]
        else:
            lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
            obj = v2.LOOKAHEAD

        fin = np.where(np.isfinite(dist))[0]
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            cands = sorted(fin, key=lambda i: abs(dist[i] - obj))[
                :min(30, len(fin))]

        # --- V1: monotonia hacia adelante ------------------------------
        if cfg["mono"] and self.prev_target is not None and len(fin):
            ys, xs = np.array([q[0] for q in pts]), np.array([q[1] for q in pts])
            dd = (xs[fin] - self.prev_target[0]) ** 2 \
                + (ys[fin] - self.prev_target[1]) ** 2
            ancla = int(fin[int(np.argmin(dd))])
            adm = [i for i in cands if es_ancestro(prev, ancla, i)]
            if adm:                       # si ninguno califica, no se traba
                cands = adm

        # --- score identico al de V2 -----------------------------------
        def score(i):
            y, x = pts[i]
            dy = sy - y
            heading = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
            s = 0.35 * abs(dist[i] - obj)
            s += 0.55 * v2.angdiff(heading, self.prev_heading)
            if self.prev_target is not None:
                s += 0.10 * math.hypot(x - self.prev_target[0],
                                       y - self.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        ti = min(cands, key=score)
        ty, tx = pts[ti]

        if medidas is not None:           # calibracion: arco de suelo real
            ds, _ps = dijkstra_suelo(pts, adj, si, xz)
            idx = {}
            for k, q in enumerate(pts):
                idx.setdefault(q, k)
            k = idx.get((int(round(res["target"][1])),
                         int(round(res["target"][0]))))
            if k is not None and np.isfinite(ds[k]):
                medidas.append(float(ds[k]))

        # --- chequeo de fidelidad: apagado tiene que dar lo mismo -------
        if not cfg["mono"] and not cfg["suelo"]:
            CHK["n"] += 1
            if (abs(tx - res["target"][0]) > 1e-6
                    or abs(ty - res["target"][1]) > 1e-6):
                CHK["mal"] += 1
            return sk, res

        camino = o_r(prev, si, ti) or [si, ti]
        return sk, dict(
            start=res["start"], target=(float(tx), float(ty)),
            heading=math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6))),
            path=[(float(pts[i][1]), float(pts[i][0])) for i in camino])

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


# --------------------------------------------------------------------------
def corrida(SinBranch, v2, ruta, fps, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(fps)
    ser = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            t = r.get("target")
            ser.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                r.get("state")))
        i += 1
    cap.release()
    return ser


def agregado(SinBranch, v2):
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0)
    for vid in AB.AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        m = AB.metricas(corrida(SinBranch, v2, ruta, FPS))
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    return tot


def controles(SinBranch, v2):
    out = {}
    for nom, vid, fps, d, h, ex in AB.CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        ser = corrida(SinBranch, v2, ruta, fps, d, h)
        m = AB.metricas(ser)
        st = [s for _t, s, _e in ser if s is not None]
        out[nom] = (m["con"], ex, max(st) if st else 0.0)
    return out


def main():
    ap = argparse.ArgumentParser(description="Los dos P0 de vision")
    ap.add_argument("--medir", action="store_true")
    ap.add_argument("--hfov", type=float, default=HFOV_DEF)
    a = ap.parse_args()

    v4, v3, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    xz = hacer_suelo(v2, a.hfov)

    if a.medir:
        med = []
        cfg = dict(mono=False, suelo=False, xz=xz, lo_suelo=0, hi_suelo=0,
                   ld_suelo=0)
        rest = instalar(v2, cfg, medidas=med)
        for vid in AB.AUTONOMOS[:4]:
            ruta = os.path.join(AQUI, vid)
            if os.path.exists(ruta):
                corrida(SinBranch, v2, ruta, FPS)
        rest()
        m = np.array(med)
        q = np.percentile(m, [5, 25, 50, 75, 95])
        print("")
        print("  ARCO DE SUELO hasta el target del baseline  (HFOV %.0f)"
              % a.hfov)
        print("  unidades: Z(fila 119) = 1,0. n = %d" % len(m))
        print("    p05 %.3f   p25 %.3f   p50 %.3f   p75 %.3f   p95 %.3f"
              % tuple(q))
        print("    variacion p95/p05: %.1fx" % (q[4] / max(q[0], 1e-9)))
        print("")
        print("  -> ld_suelo = %.3f   shell [%.3f, %.3f]"
              % (q[2], q[2] * 0.77, q[2] * 1.26))
        print("  (se conserva el punto de operacion mediano y se le saca la")
        print("   varianza; el ancho replica la proporcion de [54,88] sobre 70)")
        return 0

    # calibracion rapida para fijar la shell de suelo
    med = []
    cfg0 = dict(mono=False, suelo=False, xz=xz, lo_suelo=0, hi_suelo=0,
                ld_suelo=0)
    rest = instalar(v2, cfg0, medidas=med)
    for vid in AB.AUTONOMOS[:4]:
        ruta = os.path.join(AQUI, vid)
        if os.path.exists(ruta):
            corrida(SinBranch, v2, ruta, FPS)
    rest()
    LD = float(np.percentile(np.array(med), 50))

    print("")
    print("=" * 96)
    print("  LOS DOS P0 DE VISION - A/B PREREGISTRADO")
    print("  MONO  = busqueda monotona hacia adelante   (Coulter 1992)")
    print("  SUELO = lookahead en unidades del suelo    (Snider 2009)")
    print("  ld_suelo calibrado = %.3f (mediana del baseline), HFOV %.0f"
          % (LD, a.hfov))
    print("=" * 96)

    VAR = [("BASE", False, False), ("MONO", True, False),
           ("SUELO", False, True), ("MONO+SUELO", True, True)]
    base = None
    filas = []
    for nom, mono, suelo in VAR:
        cfg = dict(mono=mono, suelo=suelo, xz=xz, ld_suelo=LD,
                   lo_suelo=LD * 0.77, hi_suelo=LD * 1.26)
        CHK["n"] = CHK["mal"] = 0
        rest = instalar(v2, cfg)
        t = agregado(SinBranch, v2)
        c = controles(SinBranch, v2)
        rest()
        if nom == "BASE":
            base = t
            print("")
            print("  FIDELIDAD DEL SELECTOR RE-IMPLEMENTADO")
            print("    %d frames, %d discrepancias  %s"
                  % (CHK["n"], CHK["mal"],
                     "OK" if CHK["mal"] == 0 else "*** ABORTA"))
            if CHK["mal"]:
                return 3
            print("")
            print("  %-12s %9s %9s %9s %11s %9s   %s"
                  % ("variante", "disp %", "huecos", "saltos>24", "INVERSIONES",
                     "sin_aut", "controles"))
        filas.append((nom, t, c))
        ctl = "  ".join("%s %d/%s" % (k[:9], v[0], v[1])
                        for k, v in sorted(c.items()) if v[1])
        ok87 = c.get("lineal_positivo", (0, 0, 0))[2] >= 85.0
        print("  %-12s %+9.2f %+9d %+9d %+11d %+9d   %s %s"
              % (nom, t["disp"] - base["disp"], t["huecos"] - base["huecos"],
                 t["s_gt"] - base["s_gt"], t["inv"] - base["inv"],
                 t["sin_aut"] - base["sin_aut"], ctl,
                 "" if ok87 else "*** PIERDE EL +87"))

    print("")
    print("  BASELINE ABSOLUTO  disp %.2f %%  huecos %d  saltos %d  inv %d"
          % (base["disp"], base["huecos"], base["s_gt"], base["inv"]))
    print("")
    print("  CRITERIO: una variante entra solo si mejora sin romper ningun")
    print("  control y sin empeorar disponibilidad, huecos ni saltos.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
