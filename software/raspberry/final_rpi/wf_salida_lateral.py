# -*- coding: utf-8 -*-
"""
SALIDA LATERAL - la regla de curva cerrada de los campeones, sobre CAMINO+MONO.

DE DONDE SALE
-------------
Overengineering (campeon 2024) y Airborne no resuelven la curva cerrada con un
modo de recuperacion aparte. Lo resuelven DENTRO del seguidor:

  "If this point is not at the top edge of the cropped frame, either the left or
   right point is selected for following, depending on their distance to the edge
   of the frame, to prevent overrunning the line."

Y cuando hay dos ramas al fondo saturan el comando hacia un lado y lo enganchan
con un TIMER (~0,6 s) con memoria del lado.

TRADUCCION A NUESTRA ARQUITECTURA
---------------------------------
Nosotros no tenemos "el punto de arriba del contorno": tenemos una shell
geodesica sobre el esqueleto. El equivalente exacto de "este punto NO llega al
borde de arriba" es "el target elegido NO llega a la distancia geodesica
nominal": dist[target] < LOOKAHEAD. Es decir, la cinta visible se ACABA antes
del lookahead. Cuando eso pasa, la cinta se fue por un costado del cuadro.

REGLA (sin parametros nuevos salvo el latch)
  1. Se miran los nodos ALCANZABLES del esqueleto con columna < 3 % de W
     (x < 4,8) o > 97 % de W (x > 155,2). Son la salida lateral.
  2. Por cada lado se toma el nodo de MAYOR distancia geodesica: el final real
     de la cinta por ese costado.
  3. DISPARA si el target actual no llega lejos (dist[ti] < LOOKAHEAD) y existe
     un nodo de borde AL MENOS TAN ADELANTE como el target
     (dist[borde] >= dist[ti], para no tirar el target hacia atras).
  4. Si los dos lados califican, gana el de mayor distancia geodesica: el lado
     por el que la cinta realmente se va.
  5. LATCH: al disparar se memoriza el lado y se sostiene N frames. Mientras el
     latch esta vivo, si ese lado sigue teniendo nodo de borde, el target se
     fuerza ahi aunque la regla no vuelva a disparar.

BANDA PREREGISTRADA DEL LATCH (se corren las cuatro, no se elige despues)
  0,0 s   la regla sin latch (aisla el efecto de la regla)
  0,3 s
  0,6 s   el valor de los campeones
  0,9 s

FIDELIDAD: el selector se re-implementa para poder restringir/forzar, asi que
con TODO apagado tiene que reproducir el target de la candidata EXACTAMENTE. Se
verifica frame a frame y si hay una sola discrepancia, aborta.

LIMITACION HONESTA: el espia actua sobre path_target. Aguas abajo siguen vivos
el cap de continuidad de V2 (16/12/20 px) y los guards de V4, que amortiguan el
salto forzado. El latch es justamente lo que permite caminar hasta el borde en
varios frames en vez de un solo salto.

    python3 wf_salida_lateral.py
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
FRAC_BORDE = 0.03          # 3 % del ancho: columnas < 4,8 y > 155,2
CAP = {}
CHK = {"n": 0, "mal": 0}
USO = {"camino_vacio": 0, "camino_ok": 0, "mono_vacio": 0,
       "lat_fire": 0, "lat_hold": 0, "lat_cambio": 0, "lat_rompe_mono": 0,
       "lat_frames_borde": 0}


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

    LIM_L = FRAC_BORDE * v2.W
    LIM_R = (1.0 - FRAC_BORDE) * v2.W

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["si"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        # el latch corre en tiempo, no en "frames utiles"
        if getattr(self, "_lat_left", 0) > 0:
            self._lat_left -= 1

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

        ys_a = np.array([q[0] for q in pts], float)
        xs_a = np.array([q[1] for q in pts], float)

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
        ancla = None
        if cfg["mono"] and self.prev_target is not None and len(fin):
            dd = ((xs_a[fin] - self.prev_target[0]) ** 2
                  + (ys_a[fin] - self.prev_target[1]) ** 2)
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

        if not cfg["camino"] and not cfg["mono"] and cfg["lat_s"] is None:
            CHK["n"] += 1
            ty, tx = pts[ti]
            if (abs(tx - res["target"][0]) > 1e-6
                    or abs(ty - res["target"][1]) > 1e-6):
                CHK["mal"] += 1
            return sk, res

        # --- SALIDA LATERAL DE LOS CAMPEONES -------------------------------
        if cfg["lat_s"] is not None and len(fin):
            borde = {}
            bl = fin[xs_a[fin] < LIM_L]
            br = fin[xs_a[fin] > LIM_R]
            if len(bl):
                borde[-1] = int(bl[int(np.argmax(dist[bl]))])
            if len(br):
                borde[+1] = int(br[int(np.argmax(dist[br]))])
            if borde:
                USO["lat_frames_borde"] += 1

            elegido = None
            if borde and dist[ti] < v2.LOOKAHEAD:
                apto = [s for s in borde if dist[borde[s]] >= dist[ti]]
                if apto:
                    lado = max(apto, key=lambda s: dist[borde[s]])
                    elegido = borde[lado]
                    self._lat_side = lado
                    self._lat_left = int(round(cfg["lat_s"] * self.fps))
                    USO["lat_fire"] += 1
            if elegido is None and getattr(self, "_lat_left", 0) > 0:
                ls = getattr(self, "_lat_side", None)
                if ls in borde:
                    elegido = borde[ls]
                    USO["lat_hold"] += 1

            if elegido is not None:
                if elegido != ti:
                    USO["lat_cambio"] += 1
                if ancla is not None and not es_ancestro(prev, ancla, elegido):
                    USO["lat_rompe_mono"] += 1
                ti = elegido

        ty, tx = pts[ti]
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


def correr_variante(SinBranch, v2, nom, cfg):
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
    smax = None
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
            okc &= (smax >= 88.5)
    rest()
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav"]))
    tot["ctl"] = "  ".join(ctl)
    tot["okc"] = okc
    tot["smax"] = smax
    tot["uso"] = dict(USO)
    tot["chk"] = dict(CHK)
    return tot


def fila(nom, t, b):
    return ("  %-16s %+9.2f %+9d %+9d %+9d %+11d %+9.2f   %s %s"
            % (nom, t["disp"] - b["disp"], t["sin_aut"] - b["sin_aut"],
               t["huecos"] - b["huecos"], t["s_gt"] - b["s_gt"],
               t["inv"] - b["inv"], t["suav"] - b["suav"],
               t["ctl"], "OK" if t["okc"] else "*** FALLA"))


CAB = ("  %-16s %9s %9s %9s %9s %11s %9s   %s"
       % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
          "inversiones", "suav", "controles"))


def main():
    ap = argparse.ArgumentParser(description="Salida lateral de los campeones")
    ap.parse_args()
    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)

    print("")
    print("=" * 112)
    print("  SALIDA LATERAL - la regla de curva cerrada de Overengineering /"
          " Airborne, sobre CAMINO+MONO")
    print("  Si el target no llega a LOOKAHEAD y el esqueleto toca una columna"
          " < 3 %% o > 97 %% del ancho,")
    print("  el target se manda a ese punto de borde y se sostiene con un latch"
          " con memoria del lado.")
    print("  Banda preregistrada del latch: 0,0 / 0,3 / 0,6 / 0,9 s.  Se corren"
          " las cuatro.")
    print("=" * 112)

    VAR = [("BASE", dict(camino=False, mono=False, lat_s=None)),
           ("CAMINO+MONO", dict(camino=True, mono=True, lat_s=None)),
           ("LAT 0.0s", dict(camino=True, mono=True, lat_s=0.0)),
           ("LAT 0.3s", dict(camino=True, mono=True, lat_s=0.3)),
           ("LAT 0.6s", dict(camino=True, mono=True, lat_s=0.6)),
           ("LAT 0.9s", dict(camino=True, mono=True, lat_s=0.9))]

    res = {}
    base = None
    print("")
    for nom, cfg in VAR:
        t = correr_variante(SinBranch, v2, nom, cfg)
        res[nom] = t
        if nom == "BASE":
            base = t
            print("  FIDELIDAD: %d frames, %d discrepancias  %s"
                  % (t["chk"]["n"], t["chk"]["mal"],
                     "OK" if t["chk"]["mal"] == 0 else "*** ABORTA"))
            if t["chk"]["mal"]:
                return 3
            print("")
            print("  BASELINE  disp %.2f %%  sin_aut %d  huecos %d  saltos %d  "
                  "inversiones %d  suav %.2f"
                  % (t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
                     t["inv"], t["suav"]))
            print("")
            print("  DELTAS CONTRA EL BASELINE (candidata SinBranch tal cual)")
            print(CAB)
            print("  %-16s %+9.2f %+9d %+9d %+9d %+11d %+9.2f   %s %s"
                  % ("BASE", 0, 0, 0, 0, 0, 0, t["ctl"],
                     "OK" if t["okc"] else "*** FALLA"))
            continue
        print(fila(nom, t, base))
        u = t["uso"]
        if cfg["lat_s"] is not None:
            print("       borde visible en %d frames | dispara %d | sostiene %d"
                  " | cambia el target %d | rompe monotonia %d"
                  % (u["lat_frames_borde"], u["lat_fire"], u["lat_hold"],
                     u["lat_cambio"], u["lat_rompe_mono"]))
        sys.stdout.flush()

    cm = res["CAMINO+MONO"]
    print("")
    print("  DELTAS CONTRA CAMINO+MONO (que es el mejor actual)")
    print(CAB)
    print("  %-16s %+9.2f %+9d %+9d %+9d %+11d %+9.2f   %s %s"
          % ("CAMINO+MONO", 0, 0, 0, 0, 0, 0, cm["ctl"],
             "OK" if cm["okc"] else "*** FALLA"))
    for nom, cfg in VAR:
        if cfg["lat_s"] is None:
            continue
        print(fila(nom, res[nom], cm))

    print("")
    print("  ABSOLUTOS")
    print("  %-16s %9s %9s %9s %9s %11s %9s"
          % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
             "inversiones", "suav"))
    for nom, _ in VAR:
        t = res[nom]
        print("  %-16s %9.2f %9d %9d %9d %11d %9.2f"
              % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
                 t["inv"], t["suav"]))

    print("")
    print("  CRITERIO PREREGISTRADO: la salida lateral entra solo si contra")
    print("  CAMINO+MONO mejora algo sin empeorar disponibilidad, huecos ni")
    print("  saltos, y sin romper ningun control (100/100, 73/73, smax >= +89).")
    print("=" * 112)
    return 0


if __name__ == "__main__":
    sys.exit(main())
