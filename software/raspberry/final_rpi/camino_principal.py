# -*- coding: utf-8 -*-
"""
CAMINO PRINCIPAL - que el esqueleto sea UNA LINEA y no una estrella.

DE DONDE SALE
-------------
Benjamin, mirando el video cuadro a cuadro: el esqueleto se bifurca, aparece una
costilla que se mete en el recodo de la mancha, y el target cae justo en la
horquilla en vez de seguir la cinta.

Medido en `estrella.py` sobre 13.242 frames:

  linea limpia (exactamente 2 extremos)   44,3 %
  3 o mas extremos                        55,7 %
  con alguna bifurcacion                  55,9 %
  estrellas de 5+ extremos                 8,1 %   (max 14 extremos, 36 bifurc.)

MAS DE LA MITAD DEL TIEMPO EL ESQUELETO NO ES UNA LINEA.

Esto NO es lo que refuto H6b. H6b pregunto si las ramas eran ruido de MASCARA y
mostro que persisten en multiescala: son reales. Y son reales, pero son ramas del
EJE MEDIAL de una mancha con recodos, no cinta. El eje medial de una franja
gruesa que dobla tiene costillas hacia cada esquina interior. Son geometricamente
correctas y semanticamente basura.

H6 tampoco: H6 probo podar por LONGITUD y cayo porque la distribucion de
longitudes es continua y cualquier umbral era arbitrario. Aca no se poda por
longitud ni por ningun umbral.

LA IDEA
-------
Del arbol de caminos mas cortos que Dijkstra YA calculo desde `start`:

    F = el nodo alcanzable mas lejano
    camino principal = la cadena start -> F

Se restringen los candidatos de la shell a esa cadena.

SIN UMBRALES. Sin parametros nuevos. Sin tocar la mascara ni skeletonize.

CORRECCION DE ALCANCE, 25-ago (auditoria de ChatGPT)
----------------------------------------------------
Este archivo decia "las costillas no estan en esa cadena, POR CONSTRUCCION".
Eso es falso, y la refutacion es de una linea: si una costilla espuria resulta
ser el nodo geodesicamente MAS LEJANO desde `start`, entonces F es la punta de
la costilla y la cadena reconstruida ES la costilla.

Lo que la construccion garantiza es una sola cosa:

    me quedo con UNA cadena raiz->hoja del esqueleto

y NO garantiza que esa cadena sea la cinta semanticamente correcta. La
literatura de eje medial dice lo mismo: preservar conectividad no equivale a
recuperar la semantica, y una perturbacion chica del borde genera ramas.

Como hay que hablar de CAMINO, entonces:

    NO  "extrae el camino principal correcto"
    SI  "elige heuristicamente una cadena larga y temporalmente consistente"

El A/B sigue valiendo -mejora las cinco metricas- y eso no cambia. Lo que cambia
es que es una heuristica que funciona, no un problema resuelto.

Y el limite se ve en los datos: todavia queda un 2,7 % de frames donde el camino
proyectado al suelo apunta hacia ATRAS (|psi| > 90 grados).

VARIANTES QUE SE PRUEBAN
------------------------
  BASE      la candidata tal cual
  CAMINO    candidatos restringidos a la cadena elegida
  MONO      monotonia temporal INSPIRADA en Coulter 1992 (ver abajo)
  CAMINO+MONO

SOBRE MONO Y COULTER, tambien corregido
---------------------------------------
Coulter parte de un camino YA ORDENADO: busca el punto mas cercano y avanza "up
the path". Nuestro problema es ANTERIOR -un esqueleto sin orientacion, donde ni
siquiera se sabe cual rama es "adelante"-. MONO fabrica ese orden proyectando el
target anterior al esqueleto actual y exigiendo relacion ancestro->descendiente
en el arbol de Dijkstra.

Es una buena heuristica TEMPORAL, y es de donde salio la idea. Pero Coulter no
valida esa decision: el ya presupone conocida la secuencia del camino.

FIDELIDAD: el selector se re-implementa para poder restringir, asi que con todo
apagado tiene que reproducir el target de la candidata EXACTAMENTE. Se verifica
en cada frame y si hay una sola discrepancia, aborta.

    python3 camino_principal.py
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
CAP = {}
CHK = {"n": 0, "mal": 0}
USO = {"camino_vacio": 0, "camino_ok": 0, "mono_vacio": 0}


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


def es_ancestro(prev, ancla, cand):
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


def instalar(v2, cfg):
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    o_r = v2.reconstruct

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
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
        pts, dist, prev, si = CAP["pts"], CAP["dist"], CAP["prev"], CAP["si"]
        sy, sx = pts[si]
        lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        fin = np.where(np.isfinite(dist))[0]
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            cands = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
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
            s = 0.35 * abs(dist[i] - v2.LOOKAHEAD)
            s += 0.55 * v2.angdiff(h, self.prev_heading)
            if self.prev_target is not None:
                s += 0.10 * math.hypot(x - self.prev_target[0],
                                       y - self.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        ti = min(cands, key=score)
        ty, tx = pts[ti]

        if not cfg["camino"] and not cfg["mono"]:
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


def main():
    ap = argparse.ArgumentParser(description="Camino principal del esqueleto")
    ap.parse_args()
    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)

    print("")
    print("=" * 98)
    print("  CAMINO PRINCIPAL - que el esqueleto sea una linea y no una estrella")
    print("  El esqueleto tiene 3+ extremos en el 55,7 % de los frames.")
    print("  Se restringen los candidatos a la cadena start -> nodo mas lejano.")
    print("  Sin umbrales, sin parametros nuevos, sin tocar la mascara.")
    print("=" * 98)

    VAR = [("BASE", False, False), ("CAMINO", True, False),
           ("MONO", False, True), ("CAMINO+MONO", True, True)]
    base = None
    print("")
    for nom, cam, mono in VAR:
        cfg = dict(camino=cam, mono=mono)
        CHK["n"] = CHK["mal"] = 0
        for k in USO:
            USO[k] = 0
        rest = instalar(v2, cfg)
        tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, suav=[])
        for vid in AB.AUTONOMOS:
            ru = os.path.join(AQUI, vid)
            if not os.path.exists(ru):
                continue
            m = AB.metricas(serie(SinBranch, v2, ru, FPS))
            for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
                tot[k] += m[k]
            tot["suav"].append(m["suav"])
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
                ctl.append("smax %+.0f" % (max(st) if st else 0))
        rest()
        tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
        tot["suav"] = float(np.mean(tot["suav"]))
        if nom == "BASE":
            base = tot
            print("  FIDELIDAD: %d frames, %d discrepancias  %s"
                  % (CHK["n"], CHK["mal"],
                     "OK" if CHK["mal"] == 0 else "*** ABORTA"))
            if CHK["mal"]:
                return 3
            print("")
            print("  BASELINE  disp %.2f %%  sin_aut %d  huecos %d  saltos %d  "
                  "inversiones %d  suav %.2f"
                  % (tot["disp"], tot["sin_aut"], tot["huecos"], tot["s_gt"],
                     tot["inv"], tot["suav"]))
            print("")
            print("  %-14s %9s %9s %9s %9s %11s %9s   %s"
                  % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
                     "inversiones", "suav", "controles"))
            print("  %-14s %+9.2f %+9d %+9d %+9d %+11d %+9.2f   %s %s"
                  % ("BASE", 0, 0, 0, 0, 0, 0, "  ".join(ctl),
                     "OK" if okc else "*** FALLA"))
            continue
        print("  %-14s %+9.2f %+9d %+9d %+9d %+11d %+9.2f   %s %s"
              % (nom, tot["disp"] - base["disp"],
                 tot["sin_aut"] - base["sin_aut"],
                 tot["huecos"] - base["huecos"], tot["s_gt"] - base["s_gt"],
                 tot["inv"] - base["inv"], tot["suav"] - base["suav"],
                 "  ".join(ctl), "OK" if okc else "*** FALLA"))
        if cam:
            print("       camino principal aplicado en %d frames, sin "
                  "candidatos en %d" % (USO["camino_ok"], USO["camino_vacio"]))
    print("")
    print("  CRITERIO: entra solo si mejora sin empeorar disponibilidad,")
    print("  huecos ni saltos, y sin romper ningun control.")
    print("=" * 98)
    return 0


if __name__ == "__main__":
    sys.exit(main())
