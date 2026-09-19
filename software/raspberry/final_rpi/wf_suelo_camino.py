# -*- coding: utf-8 -*-
"""
LOOKAHEAD EN UNIDADES DEL SUELO, PERO SOBRE EL CAMINO PRINCIPAL.

DE DONDE SALE
-------------
`pursuit.py` ya probo SUELO (Snider 2009: el lookahead de pure pursuit tiene que
ser una distancia FISICA, no pixeles) sobre el baseline y EMPEORO: inversiones
+21 a HFOV 60, +31 a HFOV 45.

Pero ese A/B se corrio sobre el esqueleto crudo. Y `estrella.py` midio que el
55,7 % de los frames tienen 3 o mas extremos: el eje medial de una mancha con
recodos tiene costillas. O sea que la metrica de suelo se estaba calculando
sobre un grafo lleno de ramas espurias, y la shell de suelo podia caer sobre
una costilla igual de facil que la shell de pixeles.

HIPOTESIS: sobre el camino principal limpio (CAMINO+MONO), donde los candidatos
ya estan restringidos a la cadena start -> nodo mas lejano y a los descendientes
del ancla, el lookahead de suelo puede comportarse distinto.

FALSADOR: si CAMINO+MONO+SUELO no mejora ninguna metrica respecto de
CAMINO+MONO en ninguno de los tres HFOV preregistrados, la hipotesis cae y el
resultado de pursuit.py se confirma: el problema no era el esqueleto sucio.

LA METRICA DEL SUELO (identica a pursuit.py, verificada ahi)
------------------------------------------------------------
    Z(v)    = (119 - v_h) / (v - v_h)         en unidades de Z(fila 119)
    X(u,v)  = (u - CENTRO) * Z(v) / f_px      f_px = (W/2)/tan(HFOV/2)
    peso    = hypot(dX, dZ)

Con la metrica de suelo puesta, TODO el pipeline geodesico pasa a vivir en el
suelo: la shell, el nodo mas lejano F del camino principal, y el arbol de
ancestros que usa MONO. Eso es lo que significa "cambiar los pesos de arista".

EL CONFUNDIDOR QUE PURSUIT.PY NO CONTROLO
-----------------------------------------
El score del selector tiene un termino `0.35 * |dist - objetivo|`. En pixeles el
objetivo es 70 y el termino vale decenas. En unidades de suelo el objetivo es
~1-3 y el mismo termino vale decimas: queda aplastado contra el termino de
rumbo (`0.55 * angdiff` en GRADOS) y contra el de continuidad (`0.10 * hypot` en
PIXELES). O sea que "poner la metrica en el suelo" tambien apaga, sin querer, el
termino de distancia del score.

Por eso se corren DOS formas, las dos preregistradas antes de mirar ningun
numero:

  SUELO    exactamente como pursuit.py: el termino queda como queda.
  SUELO-N  el mismo termino reescalado por 70/ld, o sea la desviacion expresada
           en PIXELES EQUIVALENTES en el punto de operacion. Asi el score
           conserva el mismo balance relativo que el baseline y lo unico que
           cambia es DONDE cae la shell.

BANDA PREREGISTRADA
-------------------
  HFOV     45, 60, 75 grados      (la camara no esta calibrada; se barre)
  ld       mediana del arco de suelo que consigue CAMINO+MONO, por HFOV.
           NO se elige: es la mediana. Preserva el punto de operacion y le saca
           la varianza, que es todo el argumento de Snider.
  shell    [0.77*ld, 1.26*ld], las mismas proporciones que [54,88] sobre 70.

FIDELIDAD
---------
El selector se re-implementa para poder restringir, asi que con todo apagado
tiene que reproducir el target de la candidata EXACTAMENTE. Se verifica frame a
frame y si hay una sola discrepancia, aborta.

NO MODIFICA V2/V3/V4 ni ningun archivo compartido. Espia reversible.

    python wf_suelo_camino.py
"""

import argparse
import heapq
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
V_H = 9.0                     # fila del horizonte, medida en birdeye.py
HFOVS = [45.0, 60.0, 75.0]    # PREREGISTRADO
LO_REL, HI_REL = 0.77, 1.26   # 54/70 y 88/70

CAP = {}
CHK = {"n": 0, "mal": 0}
USO = {"camino_ok": 0, "camino_vacio": 0, "mono_vacio": 0, "shell_vacia": 0}


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3.v2


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
# METRICA DEL SUELO  (copiada de pursuit.py, ya verificada)
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
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


# --------------------------------------------------------------------------
# ESPIA REVERSIBLE SOBRE path_target
# --------------------------------------------------------------------------
def instalar(v2, cfg, medidas=None):
    """cfg: camino, mono, suelo, xz, ld, escala.
    medidas: si no es None, lista de (xz, hfov, lista_destino) para calibrar."""
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    o_r = v2.reconstruct

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

        # --- SUELO: se cambian los pesos de arista -------------------------
        if cfg["suelo"]:
            dist, prev = dijkstra_suelo(pts, adj, si, cfg["xz"])
            obj = cfg["ld"]
            lo, hi = obj * LO_REL, obj * HI_REL
            esc = cfg["escala"]
        else:
            obj = v2.LOOKAHEAD
            lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
            esc = 1.0

        fin = np.where(np.isfinite(dist))[0]
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            USO["shell_vacia"] += 1
            cands = sorted(fin, key=lambda i: abs(dist[i] - obj))[
                :min(30, len(fin))]

        # --- CAMINO PRINCIPAL: la cadena start -> nodo mas lejano ----------
        if cfg["camino"] and len(fin):
            F = int(fin[int(np.argmax(dist[fin]))])
            cadena = set(o_r(prev, si, F) or [])
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub
                USO["camino_ok"] += 1
            else:
                USO["camino_vacio"] += 1

        # --- MONOTONIA HACIA ADELANTE (Coulter 1992) -----------------------
        if cfg["mono"] and self.prev_target is not None and len(fin):
            ys = np.array([q[0] for q in pts])
            xs = np.array([q[1] for q in pts])
            dd = ((xs[fin] - self.prev_target[0]) ** 2
                  + (ys[fin] - self.prev_target[1]) ** 2)
            ancla = int(fin[int(np.argmin(dd))])
            adm = [i for i in cands if es_ancestro(prev, ancla, i)]
            if adm:
                cands = adm
            else:
                USO["mono_vacio"] += 1

        def score(i):
            y, x = pts[i]
            dy = sy - y
            h = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
            s = 0.35 * abs(dist[i] - obj) * esc
            s += 0.55 * v2.angdiff(h, self.prev_heading)
            if self.prev_target is not None:
                s += 0.10 * math.hypot(x - self.prev_target[0],
                                       y - self.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        ti = min(cands, key=score)
        ty, tx = pts[ti]

        # --- calibracion: arco de suelo hasta el target elegido ------------
        if medidas is not None:
            for xzf, _hf, dest in medidas:
                ds, _pp = dijkstra_suelo(pts, adj, si, xzf)
                if np.isfinite(ds[ti]):
                    dest.append(float(ds[ti]))

        # --- fidelidad: con todo apagado tiene que dar lo mismo ------------
        if not cfg["camino"] and not cfg["mono"] and not cfg["suelo"]:
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
def serie(SinBranch, v2, ruta, fps, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(fps)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            t = r.get("target")
            out.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                r.get("state")))
        i += 1
    cap.release()
    return out


def evaluar(SinBranch, v2):
    """Devuelve (totales, texto_controles, controles_ok)."""
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, suav=[])
    for vid in AB.AUTONOMOS:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru):
            continue
        m = AB.metricas(serie(SinBranch, v2, ru, FPS))
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
        tot["suav"].append(m["suav"])
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav"]))

    ctl = []
    okc = True
    for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru) or not ex:
            continue
        s = serie(SinBranch, v2, ru, fps, d0, h0)
        m = AB.metricas(s)
        st = [x for _t, x, _e in s if x is not None]
        ctl.append("%s %d/%d" % (cn.split("_")[0], m["con"], ex))
        okc &= (m["con"] >= ex)
        if cn == "lineal_positivo":
            smax = max(st) if st else 0.0
            ctl.append("smax %+.0f" % smax)
            okc &= (smax >= 85.0)
    return tot, "  ".join(ctl), okc


def reset_uso():
    for k in USO:
        USO[k] = 0


FMT = "  %-18s %9s %9s %9s %9s %11s %9s   %s"
ROW = "  %-18s %+9.2f %+9d %+9d %+9d %+11d %+9.2f   %s %s"


def main():
    ap = argparse.ArgumentParser(
        description="Lookahead de suelo sobre el camino principal")
    ap.parse_args()
    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)

    print("")
    print("=" * 104)
    print("  SUELO SOBRE CAMINO PRINCIPAL")
    print("  pursuit.py probo SUELO sobre el esqueleto crudo (55,7 % de los")
    print("  frames tienen costillas) y empeoro. Aca se prueba sobre CAMINO+MONO.")
    print("  HFOV preregistrado: 45 / 60 / 75.  ld = mediana del arco de suelo.")
    print("=" * 104)

    # ---------------- 1) FIDELIDAD + baseline de la candidata --------------
    cfg0 = dict(camino=False, mono=False, suelo=False, xz=None, ld=0.0,
                escala=1.0)
    CHK["n"] = CHK["mal"] = 0
    reset_uso()
    rest = instalar(v2, cfg0)
    base_cand, ctl0, ok0 = evaluar(SinBranch, v2)
    rest()
    print("")
    print("  FIDELIDAD DEL SELECTOR RE-IMPLEMENTADO")
    print("    %d frames, %d discrepancias  %s"
          % (CHK["n"], CHK["mal"], "OK" if CHK["mal"] == 0 else "*** ABORTA"))
    if CHK["mal"]:
        return 3
    print("")
    print("  BASELINE ABSOLUTO (candidata SinBranch)")
    print("    disp %.2f %%  sin_aut %d  huecos %d  saltos>24 %d  "
          "inversiones %d  suav %.2f"
          % (base_cand["disp"], base_cand["sin_aut"], base_cand["huecos"],
             base_cand["s_gt"], base_cand["inv"], base_cand["suav"]))

    # ---------------- 2) CAMINO+MONO = la referencia de esta prueba --------
    cfgCM = dict(camino=True, mono=True, suelo=False, xz=None, ld=0.0,
                 escala=1.0)
    reset_uso()
    rest = instalar(v2, cfgCM)
    ref, ctlR, okR = evaluar(SinBranch, v2)
    rest()
    print("")
    print("  REFERENCIA DE ESTA PRUEBA: CAMINO+MONO")
    print("    disp %.2f %%  sin_aut %d  huecos %d  saltos>24 %d  "
          "inversiones %d  suav %.2f"
          % (ref["disp"], ref["sin_aut"], ref["huecos"], ref["s_gt"],
             ref["inv"], ref["suav"]))
    print("    contra el baseline absoluto: disp %+.2f  sin_aut %+d  huecos %+d"
          "  saltos %+d  inv %+d  suav %+.2f"
          % (ref["disp"] - base_cand["disp"],
             ref["sin_aut"] - base_cand["sin_aut"],
             ref["huecos"] - base_cand["huecos"],
             ref["s_gt"] - base_cand["s_gt"],
             ref["inv"] - base_cand["inv"],
             ref["suav"] - base_cand["suav"]))

    # ---------------- 3) CALIBRACION del ld de suelo, por HFOV -------------
    print("")
    print("  CALIBRACION  arco de suelo hasta el target de CAMINO+MONO")
    print("  (4 primeros videos; unidades Z(fila 119) = 1,0)")
    med = [(hacer_suelo(v2, h), h, []) for h in HFOVS]
    rest = instalar(v2, cfgCM, medidas=med)
    for vid in AB.AUTONOMOS[:4]:
        ru = os.path.join(AQUI, vid)
        if os.path.exists(ru):
            serie(SinBranch, v2, ru, FPS)
    rest()

    LD = {}
    print("    %-7s %6s %8s %8s %8s %8s %8s   %s"
          % ("HFOV", "n", "p05", "p25", "p50", "p75", "p95", "p95/p05"))
    for xzf, h, lst in med:
        m = np.array(lst)
        if not len(m):
            print("    HFOV %.0f: sin medidas" % h)
            return 4
        q = np.percentile(m, [5, 25, 50, 75, 95])
        LD[h] = float(q[2])
        print("    %-7.0f %6d %8.3f %8.3f %8.3f %8.3f %8.3f   %6.1fx"
              % (h, len(m), q[0], q[1], q[2], q[3], q[4],
                 q[4] / max(q[0], 1e-9)))
    print("")
    for h in HFOVS:
        print("    HFOV %.0f -> ld %.3f   shell [%.3f, %.3f]"
              % (h, LD[h], LD[h] * LO_REL, LD[h] * HI_REL))

    # ---------------- 4) A/B ------------------------------------------------
    print("")
    print("  TODO LO DE ABAJO ES DELTA CONTRA **CAMINO+MONO**, no contra el")
    print("  baseline absoluto. Negativo es mejor salvo en disp y smax.")
    print("")
    print(FMT % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
                 "inversiones", "suav", "controles"))
    print(ROW % ("CAMINO+MONO", 0, 0, 0, 0, 0, 0, ctlR,
                 "OK" if okR else "*** FALLA"))

    filas = []
    for h in HFOVS:
        xzf = hacer_suelo(v2, h)
        for etiq, esc in (("SUELO", 1.0), ("SUELO-N", 70.0 / LD[h])):
            cfg = dict(camino=True, mono=True, suelo=True, xz=xzf,
                       ld=LD[h], escala=esc)
            reset_uso()
            rest = instalar(v2, cfg)
            t, ctl, okc = evaluar(SinBranch, v2)
            rest()
            nom = "+%s h%.0f" % (etiq, h)
            filas.append((nom, t, okc))
            print(ROW % (nom, t["disp"] - ref["disp"],
                         t["sin_aut"] - ref["sin_aut"],
                         t["huecos"] - ref["huecos"],
                         t["s_gt"] - ref["s_gt"],
                         t["inv"] - ref["inv"],
                         t["suav"] - ref["suav"],
                         ctl, "OK" if okc else "*** FALLA"))
            print("       camino ok %d / vacio %d   mono vacio %d   "
                  "shell vacia %d"
                  % (USO["camino_ok"], USO["camino_vacio"], USO["mono_vacio"],
                     USO["shell_vacia"]))

    # ---------------- 5) VEREDICTO -----------------------------------------
    print("")
    print("  CRITERIO PREREGISTRADO: entra solo si mejora alguna metrica sin")
    print("  empeorar disponibilidad, huecos ni saltos, y sin romper controles.")
    print("")
    ganan = []
    for nom, t, okc in filas:
        mejora = (t["sin_aut"] < ref["sin_aut"] or t["huecos"] < ref["huecos"]
                  or t["s_gt"] < ref["s_gt"] or t["inv"] < ref["inv"]
                  or t["suav"] < ref["suav"] - 1e-9
                  or t["disp"] > ref["disp"] + 1e-9)
        nopeor = (t["disp"] >= ref["disp"] - 1e-9
                  and t["huecos"] <= ref["huecos"]
                  and t["s_gt"] <= ref["s_gt"])
        if okc and mejora and nopeor:
            ganan.append(nom)
        print("    %-18s controles %-9s mejora %-3s  no-empeora %-3s  -> %s"
              % (nom, "OK" if okc else "FALLA", "si" if mejora else "no",
                 "si" if nopeor else "no",
                 "PASA" if (okc and mejora and nopeor) else "no pasa"))
    print("")
    if ganan:
        print("  PASAN EL CRITERIO: %s" % ", ".join(ganan))
    else:
        print("  NINGUNA VARIANTE DE SUELO PASA EL CRITERIO SOBRE CAMINO+MONO.")
        print("  La hipotesis queda refutada tambien sobre el camino limpio:")
        print("  el problema de SUELO no era que el esqueleto tuviera costillas.")
    print("=" * 104)
    return 0


if __name__ == "__main__":
    sys.exit(main())
