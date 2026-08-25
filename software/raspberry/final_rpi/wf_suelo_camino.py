# -*- coding: utf-8 -*-
"""
SUELO SOBRE CAMINO PRINCIPAL - el lookahead metrico, pero sin costillas.

DE DONDE SALE
-------------
`pursuit.py` ya probo SUELO (lookahead en unidades del piso, Snider 2009) sobre
el baseline crudo y EMPEORO: inversiones +21 a HFOV 60, +31 a HFOV 45.

Pero ese experimento se corrio sobre un esqueleto que en el 55,7 % de los frames
tiene 3 o mas extremos (medido en `estrella.py`). La metrica de suelo se estaba
calculando sobre un grafo lleno de costillas del eje medial. Y la metrica de
suelo es EXACTAMENTE la que mas castiga a una costilla: Z(v) = 110/(v-9) explota
cerca del horizonte, asi que una rama que sube dos filas de mas se lleva una
distancia de suelo enorme y se corre de la shell. Sobre un grafo sucio eso puede
estar barajando los candidatos de cualquier manera.

HIPOTESIS
---------
Sobre el CAMINO PRINCIPAL limpio (la cadena start -> nodo mas lejano del arbol de
Dijkstra, que por construccion no tiene costillas) mas MONO (busqueda monotona
hacia adelante, Coulter 1992), el lookahead de suelo puede comportarse distinto
al que midio `pursuit.py`.

FALSADOR, escrito antes de correr
---------------------------------
Si SUELO sobre CAMINO+MONO tampoco baja las inversiones respecto de CAMINO+MONO
-o empeora disponibilidad, huecos o saltos- en NINGUNO de los tres HFOV
preregistrados, la hipotesis queda refutada y la rama del lookahead metrico se
cierra: el problema no eran las costillas.

COMO SE MIDE EL SUELO   (identico a pursuit.py, ya verificado)
--------------------------------------------------------------
Se cambian los PESOS DE LAS ARISTAS del grafo del esqueleto. En vez de 1 y
raiz(2) pixeles, cada arista pesa su longitud EN EL SUELO:

    Z(v)    = (119 - 9) / (v - 9)            en unidades de Z(fila 119)
    X(u,v)  = (u - CENTRO) * Z(v) / f_px     f_px = (W/2)/tan(HFOV/2)
    peso    = hypot(dX, dZ)

Dijkstra, skeletonize, la mascara y el resto no se tocan.

PREREGISTRO
-----------
  HFOV (banda completa, se corren los tres):  45, 60, 75 grados
  ld_suelo:  mediana del arco de suelo que consigue el BASELINE, medida con el
             mismo procedimiento de `pursuit.py --medir` (AUTONOMOS[:4]).
             NO se elige a ojo ni a posteriori.
  shell:     [0,77*ld, 1,26*ld], que replica la proporcion de [54,88] sobre 70.

  DOS BRAZOS, los dos declarados antes de ver un solo numero:

  SUELO    literal, tal cual `pursuit.py`. El termino 0,35*|dist-ld| del score
           queda en unidades de suelo (ld ~ 0,7) mientras los otros terminos
           siguen en grados y pixeles, o sea que ese termino practicamente se
           apaga. Es el confundidor conocido de pursuit.py.

  SUELO-N  identico pero con ese termino reescalado por 70/ld, para que pese lo
           mismo que pesaba en pixeles. Separa "shell en unidades de suelo" de
           "colapso del peso del score". Sin este brazo, un resultado negativo
           no distingue las dos causas.

VARIANTES
---------
  BASE            la candidata SinBranch tal cual        (control de fidelidad)
  CAMINO+MONO     la mejor actual                        (referencia del criterio)
  CM+SUELO   @45 @60 @75
  CM+SUELO-N @45 @60 @75

FIDELIDAD: el selector se re-implementa para poder restringir y para poder
cambiar la metrica, asi que con TODO apagado tiene que reproducir el target de la
candidata EXACTAMENTE. Se verifica frame a frame; una sola discrepancia aborta.

REPLAY OPEN-LOOP: esto mide PERCEPCION sobre video grabado. No prueba nada sobre
la trayectoria que haria el robot.

    python wf_suelo_camino.py

============================================================================
 RESULTADO MEDIDO   2026-08-24   (fidelidad 12.065 frames, 0 discrepancias)
============================================================================
HIPOTESIS REFUTADA. Los 6 brazos empeoran contra CAMINO+MONO.

  DELTAS CONTRA CAMINO+MONO
  variante           disp %  sin_aut   huecos  saltos>24  inversiones     suav
  CM+SUELO  @45       -0.09      +13       +3         +2          +29    +0.45
  CM+SUELO  @60       -0.06       +8       +4         +3          +23    +0.45
  CM+SUELO  @75       -0.09      +13       +2         -1          +12    +0.22
  CM+SUELO-N @45      -0.18      +25       +9         +9          +25    +0.34
  CM+SUELO-N @60      -0.22      +30      +12        +11          +27    +0.45
  CM+SUELO-N @75      -0.07      +10       +9         +7          +17    +0.34

Ninguno pasa el criterio: TODOS bajan disponibilidad, TODOS suben inversiones
(+12 a +29) y casi todos suben huecos y saltos. Los controles aguantan en los 8
brazos (hist 100/100, lineal 73/73, smax +89), asi que el resultado no es un
artefacto de haber roto la percepcion.

POR QUE. Diagnostico sobre los 10 autonomos, 10.908 frames con shell geodesica:

  el nodo F (mas lejano) cambia de metrica pixel a metrica suelo:  6,8 %
  la shell de SUELO queda VACIA -> fallback a los 30 mas cercanos: 7,4 %
  candidatos por frame   pixel  p50 31 (media 34,0)
  candidatos por frame   suelo  p50 18 (media 21,0)

O sea: la metrica de suelo NO mueve el camino principal (el 93,2 % de los frames
elige el mismo extremo). Lo unico que mueve es QUE punto del mismo camino se
elige, y lo elige peor: la shell de suelo esta poblada por la mitad y se vacia
1 de cada 13 frames, y ahi cae al fallback de los 30 mas cercanos, que es un
selector distinto. Mas fallback = mas inestabilidad = mas inversiones.

El brazo -N descarta el confundidor de pursuit.py: reescalar el termino del
score a peso de pixel no rescata nada, lo empeora. El problema no es el peso del
score, es la shell.

CONCLUSION. La causa del fracaso de SUELO en pursuit.py NO eran las costillas del
eje medial. Con o sin costillas, el lookahead metrico sobre este esqueleto
empeora. La rama del lookahead en unidades de suelo queda CERRADA para esta
arquitectura. CAMINO+MONO se queda como esta.
"""

import argparse
import heapq
import importlib.util
import math
import os
import sys
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
V_H = 9.0                 # fila del horizonte, medida en birdeye.py (R2 .98-.99)
HFOVS = [45.0, 60.0, 75.0]        # BANDA PREREGISTRADA, se corren los tres
SH_LO, SH_HI = 0.77, 1.26         # ancho de la shell, proporcion de [54,88]/70

CAP = {}
CHK = {"n": 0, "mal": 0}
USO = {"camino_vacio": 0, "camino_ok": 0, "mono_vacio": 0, "shell_vacia": 0}


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
# METRICA DEL SUELO   (misma formula que pursuit.py, vectorizada)
# --------------------------------------------------------------------------
def hacer_suelo(v2, hfov):
    f_px = (v2.W / 2.0) / math.tan(math.radians(hfov / 2.0))

    def pxz(ys, xs):
        """ys, xs: arrays de filas/columnas del esqueleto -> (X, Z) del suelo."""
        zz = (119.0 - V_H) / np.maximum(ys - V_H, 1e-6)
        return ((xs - v2.CENTER) * zz / f_px), zz
    return pxz


def dijkstra_suelo(adj, start, PX, PZ):
    """Mismo Dijkstra, pesos en unidades de suelo en vez de pixeles."""
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


def es_ancestro(prev, ancla, cand):
    """True si `ancla` esta en el camino desde start hasta `cand`."""
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

        ys = np.array([q[0] for q in pts], float)
        xs = np.array([q[1] for q in pts], float)

        # ---- calibracion: arco de suelo hasta el target del BASELINE -------
        if medidas is not None:
            idx = {p_: i_ for i_, p_ in enumerate(pts)}
            k = idx.get((int(round(res["target"][1])),
                         int(round(res["target"][0]))))
            if k is not None:
                for pxz_fn, lista in medidas:
                    PX, PZ = pxz_fn(ys, xs)
                    ds, _pp = dijkstra_suelo(adj, si, PX.tolist(), PZ.tolist())
                    if np.isfinite(ds[k]):
                        lista.append(float(ds[k]))

        # ---- SUELO: se reemplaza la metrica del grafo ----------------------
        if cfg["suelo"]:
            PX, PZ = cfg["pxz"](ys, xs)
            dist, prev = dijkstra_suelo(adj, si, PX.tolist(), PZ.tolist())
            lo, hi = cfg["lo"], cfg["hi"]
            obj = cfg["ld"]
            kdist = cfg["kdist"]          # 0,35 literal, o reescalado a pixeles
        else:
            lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
            obj = v2.LOOKAHEAD
            kdist = 0.35

        fin = np.where(np.isfinite(dist))[0]
        if not len(fin):
            return sk, res
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            USO["shell_vacia"] += 1
            cands = sorted(fin, key=lambda i: abs(dist[i] - obj))[
                :min(30, len(fin))]

        # ---- CAMINO PRINCIPAL: la cadena start -> nodo mas lejano ----------
        if cfg["camino"]:
            F = int(fin[int(np.argmax(dist[fin]))])
            cadena = set(o_r(prev, si, F) or [])
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub
                USO["camino_ok"] += 1
            else:
                USO["camino_vacio"] += 1

        # ---- MONOTONIA HACIA ADELANTE (Coulter 1992) ----------------------
        if cfg["mono"] and self.prev_target is not None:
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
            s = kdist * abs(dist[i] - obj)
            s += 0.55 * v2.angdiff(h, self.prev_heading)
            if self.prev_target is not None:
                s += 0.10 * math.hypot(x - self.prev_target[0],
                                       y - self.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        ti = min(cands, key=score)
        ty, tx = pts[ti]

        # ---- CHEQUEO DE FIDELIDAD: todo apagado -> mismo target ------------
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
    """Corre los 10 autonomos + los controles obligatorios."""
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

    ctl, ok, smax = [], True, 0.0
    for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru) or not ex:
            continue
        s = serie(SinBranch, v2, ru, fps, d0, h0)
        m = AB.metricas(s)
        st = [x for _t, x, _e in s if x is not None]
        ctl.append("%s %d/%d" % (cn.split("_")[0], m["con"], ex))
        ok &= (m["con"] >= ex)
        if cn == "lineal_positivo":
            smax = max(st) if st else 0.0
            ctl.append("smax %+.0f" % smax)
    ok &= (smax >= 85.0)
    tot["ctl"] = "  ".join(ctl)
    tot["ok"] = ok
    return tot


CAB = ("  %-16s %8s %8s %8s %10s %12s %8s" %
       ("variante", "disp %", "sin_aut", "huecos", "saltos>24", "inversiones",
        "suav"))


def abs_fila(nom, t):
    return ("  %-16s %8.2f %8d %8d %10d %12d %8.2f   %s %s"
            % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"], t["inv"],
               t["suav"], t["ctl"], "OK" if t["ok"] else "*** FALLA"))


def dif_fila(nom, t, r):
    return ("  %-16s %+8.2f %+8d %+8d %+10d %+12d %+8.2f   %s"
            % (nom, t["disp"] - r["disp"], t["sin_aut"] - r["sin_aut"],
               t["huecos"] - r["huecos"], t["s_gt"] - r["s_gt"],
               t["inv"] - r["inv"], t["suav"] - r["suav"],
               "OK" if t["ok"] else "*** FALLA"))


def main():
    ap = argparse.ArgumentParser(
        description="Lookahead de suelo sobre el camino principal")
    ap.add_argument("--medir", action="store_true",
                    help="solo la calibracion del ld de suelo")
    a = ap.parse_args()

    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)

    print("")
    print("=" * 104)
    print("  SUELO SOBRE CAMINO PRINCIPAL")
    print("  pursuit.py midio SUELO sobre el baseline crudo y empeoro las")
    print("  inversiones (+21 a HFOV 60, +31 a HFOV 45). Pero ese esqueleto")
    print("  tiene 3+ extremos en el 55,7 % de los frames: la metrica de suelo")
    print("  se calculaba sobre un grafo lleno de costillas del eje medial.")
    print("  Aca se repite sobre CAMINO+MONO, que las elimina.")
    print("=" * 104)

    # ---- CALIBRACION del ld de suelo, un solo pase para los tres HFOV -----
    t0 = time.time()
    med = [(hacer_suelo(v2, hf), []) for hf in HFOVS]
    cfg0 = dict(camino=False, mono=False, suelo=False, pxz=None, ld=0.0,
                lo=0.0, hi=0.0, kdist=0.35)
    rest = instalar(v2, cfg0, medidas=med)
    for vid in AB.AUTONOMOS[:4]:
        ru = os.path.join(AQUI, vid)
        if os.path.exists(ru):
            serie(SinBranch, v2, ru, FPS)
    rest()

    LD = {}
    print("")
    print("  CALIBRACION DEL ld DE SUELO  (mediana del arco que consigue el")
    print("  BASELINE, mismo procedimiento que pursuit.py --medir)")
    print("  %-6s %8s %8s %8s %8s %8s   %10s  %s"
          % ("HFOV", "p05", "p25", "p50", "p75", "p95", "p95/p05", "shell"))
    for hf, (_fn, lista) in zip(HFOVS, med):
        m = np.array(lista)
        q = np.percentile(m, [5, 25, 50, 75, 95])
        LD[hf] = float(q[2])
        print("  %-6.0f %8.3f %8.3f %8.3f %8.3f %8.3f   %9.1fx  [%.3f, %.3f]"
              % (hf, q[0], q[1], q[2], q[3], q[4], q[4] / max(q[0], 1e-9),
                 q[2] * SH_LO, q[2] * SH_HI))
    print("  n = %d frames medidos.  (%.0f s)" % (len(med[1][1]),
                                                  time.time() - t0))

    if a.medir:
        return 0

    # ---- A/B PREREGISTRADO ------------------------------------------------
    VAR = [("BASE", dict(camino=False, mono=False, suelo=False, hf=None,
                         norm=False)),
           ("CAMINO+MONO", dict(camino=True, mono=True, suelo=False, hf=None,
                                norm=False))]
    for hf in HFOVS:
        VAR.append(("CM+SUELO  @%.0f" % hf,
                    dict(camino=True, mono=True, suelo=True, hf=hf,
                         norm=False)))
    for hf in HFOVS:
        VAR.append(("CM+SUELO-N @%.0f" % hf,
                    dict(camino=True, mono=True, suelo=True, hf=hf,
                         norm=True)))

    res = {}
    print("")
    print("  VALORES ABSOLUTOS")
    print(CAB + "   controles")
    for nom, v in VAR:
        ld = LD.get(v["hf"], 0.0)
        cfg = dict(camino=v["camino"], mono=v["mono"], suelo=v["suelo"],
                   pxz=hacer_suelo(v2, v["hf"]) if v["hf"] else None,
                   ld=ld, lo=ld * SH_LO, hi=ld * SH_HI,
                   kdist=(0.35 * 70.0 / ld) if (v["norm"] and ld) else 0.35)
        CHK["n"] = CHK["mal"] = 0
        for k in USO:
            USO[k] = 0
        t1 = time.time()
        rest = instalar(v2, cfg)
        t = evaluar(SinBranch, v2)
        rest()
        t["seg"] = time.time() - t1
        res[nom] = t
        if nom == "BASE":
            print("  FIDELIDAD: %d frames, %d discrepancias  %s"
                  % (CHK["n"], CHK["mal"],
                     "OK" if CHK["mal"] == 0 else "*** ABORTA"))
            if CHK["mal"]:
                return 3
        print(abs_fila(nom, t))
        sys.stdout.flush()

    base, ref = res["BASE"], res["CAMINO+MONO"]
    print("")
    print("  DELTAS CONTRA BASE (la candidata SinBranch tal cual)")
    print(CAB)
    for nom, _v in VAR:
        print(dif_fila(nom, res[nom], base))

    print("")
    print("  DELTAS CONTRA CAMINO+MONO  <-- ESTA ES LA PREGUNTA DEL EXPERIMENTO")
    print(CAB)
    for nom, _v in VAR[1:]:
        print(dif_fila(nom, res[nom], ref))

    print("")
    print("  BASELINE ABSOLUTO  disp %.2f %%  sin_aut %d  huecos %d  saltos %d"
          "  inversiones %d  suav %.2f"
          % (base["disp"], base["sin_aut"], base["huecos"], base["s_gt"],
             base["inv"], base["suav"]))
    print("")
    print("  CRITERIO PREREGISTRADO: SUELO entra solo si, contra CAMINO+MONO,")
    print("  mejora sin empeorar disponibilidad, huecos ni saltos, y sin romper")
    print("  ningun control (hist 100/100, lineal 73/73, smax >= +85).")
    print("  REPLAY OPEN-LOOP: mide percepcion, no trayectoria.")
    print("=" * 104)
    return 0


if __name__ == "__main__":
    sys.exit(main())
