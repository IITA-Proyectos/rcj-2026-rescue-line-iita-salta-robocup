# -*- coding: utf-8 -*-
"""
PODA PREVIA - cortar las costillas del esqueleto ANTES de Dijkstra.

LA PREGUNTA
-----------
CAMINO (camino_principal.py) restringe los CANDIDATOS de la shell a la cadena
start -> nodo mas lejano. Pero el grafo y el Dijkstra siguen viendo las
costillas del eje medial, y sobre todo sigue viendolas la ELECCION DE `start`,
que ocurre ANTES de Dijkstra y se hace sobre `maxy` del esqueleto completo.

Si una costilla baja mas que la cinta, `maxy` la sigue a ella y `start` puede
caer sobre la costilla. CAMINO no puede arreglar eso: toma `start` como dado y
arma la cadena desde una raiz ya equivocada.

Este archivo poda el ESQUELETO y despues vuelve a correr TODO el pipeline
(maxy -> start -> Dijkstra -> shell) sobre el esqueleto podado.

AVISO QUE VENIA EN LA TAREA
---------------------------
H6 ya probo "podar por longitud con un umbral en pixeles" y cayo porque la
distribucion de longitudes es continua y cualquier umbral era arbitrario.
Aca NO hay ningun umbral absoluto. Las tres reglas son relativas:

  PODA-R  raiz.       En cada bifurcacion del arbol de Dijkstra enraizado en
                      `start` se conserva solo la rama que llega mas lejos,
                      recursivamente. Sin umbral: es un argmax.
  PODA-D  diametro.   Lo mismo pero SIN raiz: el punto fijo de "en cada
                      bifurcacion quedate con la rama que llega mas lejos"
                      aplicado sin privilegiar ningun extremo es el DIAMETRO
                      del esqueleto (doble Dijkstra). Sin umbral.
  PODA-C  costillas.  Una costilla del eje medial nace en la esquina interior
                      de una banda y su largo es del orden del RADIO LOCAL de
                      la banda. Entonces: se poda la ramita colgante cuyo largo
                      geodesico L sea menor que k veces la transformada de
                      distancia en el nodo de bifurcacion, r = DT[b].
                      L < k*r. Es relativo: compara dos cosas MEDIDAS EN EL
                      MISMO FRAME. No es un umbral en pixeles.
                      k es el unico parametro y se corre la BANDA COMPLETA
                      preregistrada k in {0.5, 1.0, 1.5, 2.0, 3.0}.
                      A diferencia de R y D, PODA-C NO colapsa a una sola
                      cadena: conserva las bifurcaciones REALES (las dos ramas
                      largas de una interseccion) y solo mata las costillas.

DIFERENCIA CON CAMINO QUE SI O SI HAY QUE MEDIR
-----------------------------------------------
  1. la poda puede cambiar `maxy` y por lo tanto `start` (CAMINO no puede)
  2. la poda cambia el fallback: si la shell queda vacia, CAMINO vuelve a los
     candidatos SIN restringir; la poda nunca tiene candidatos sin restringir
  3. con --sk-podado la poda tambien cambia el esqueleto que ve la proyeccion
     de continuidad de `step` (v2 linea ~355) y los guards. CAMINO nunca toca eso.
  4. PODA-D no privilegia el borde inferior: puede BORRAR la entrada de la
     cinta en una T donde los dos brazos son mas largos que el tramo de entrada.
     Eso es un riesgo real de podar sin raiz y hay que verlo en los numeros.

PREREGISTRO (escrito antes de correr el banco)
----------------------------------------------
  A  BASE                    fidelidad: con todo apagado tiene que reproducir
                             EXACTAMENTE start, target y heading de la candidata
  A  CAMINO                  referencia a batir; tiene que reproducir los deltas
                             ya publicados (+0.17 disp, -24 s/aut, -12 huecos,
                             -12 saltos, +23 inv, +0.06 suav)
  B  PODA-R                  sin umbral
  B  PODA-D                  sin umbral
  C  PODA-C k                k in {0.5, 1.0, 1.5, 2.0, 3.0}, banda completa
  D  CAMINO+MONO             el mejor actual
  D  PODA-R+MONO / PODA-D+MONO / PODA-C(1.5)+MONO / PODA-C(1.5)+CAMINO+MONO
     (1.5 es el CENTRO de la banda, elegido por posicion, no por resultado)
  E  PODA-D y PODA-C(1.5) devolviendo tambien el ESQUELETO podado

CRITERIO (preregistrado): la poda "da algo que CAMINO no da" solo si alguna
variante con poda mejora alguna metrica respecto de CAMINO sin empeorar
disponibilidad, huecos ni saltos, y sin romper los controles positivos.

    python wf_poda_previa.py
    python wf_poda_previa.py --smoke      (1 video corto, para medir tiempos)
"""

import argparse
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
CHK = {"n": 0, "mal": 0, "mal_start": 0}
USO = {}


def reset_uso():
    for k in ("poda_ok", "poda_degen", "px_in", "px_out", "start_movido",
              "camino_vacio", "mono_vacio", "sin_res", "frames"):
        USO[k] = 0


reset_uso()


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


# ---------------------------------------------------------------- utilidades

def es_ancestro(prev, ancla, cand):
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


def componentes(adj):
    n = len(adj)
    col = [-1] * n
    out = []
    for s in range(n):
        if col[s] != -1:
            continue
        k = len(out)
        col[s] = k
        pila = [s]
        miem = []
        while pila:
            u = pila.pop()
            miem.append(u)
            for v, _w in adj[u]:
                if col[v] == -1:
                    col[v] = k
                    pila.append(v)
        out.append(miem)
    return out


def elegir_start(v2, yo, pts, comp, mode):
    """Replica EXACTA de nuevo_code_v2.path_target lineas 242-264."""
    arr = np.array([(x, y) for y, x in pts], float)
    maxy = max(y for y, x in pts)
    W, CENTER = v2.W, v2.CENTER
    if mode == "NEAR":
        cand = [i for i, (y, x) in enumerate(pts) if y >= maxy - 8]
        if not cand:
            return None
        row_x = np.where(comp[min(119, int(round(maxy)))] > 0)[0]
        bruns = v2.runs_1d(row_x)
        ys_all, xs_all = np.nonzero(comp > 0)
        width = (xs_all.max() - xs_all.min() + 1) if len(xs_all) else 0
        if len(bruns) >= 2 or width >= 0.85 * W:
            run = (min(bruns, key=lambda r: abs(((r[0] + r[1]) / 2) - CENTER))
                   if bruns else (CENTER, CENTER))
            rc = (run[0] + run[1]) / 2
            return min(cand, key=lambda i: abs(arr[i, 0] - rc)
                       + 0.2 * abs(arr[i, 1] - maxy))
        return min(cand, key=lambda i: (arr[i, 0] - yo.prev_entry[0]) ** 2
                   + (arr[i, 1] - yo.prev_entry[1]) ** 2)
    cand = [i for i, (y, x) in enumerate(pts) if y >= maxy - 3]
    if not cand:
        return None
    ref = yo.prev_target if yo.prev_target is not None else yo.prev_entry
    return min(cand, key=lambda i: (arr[i, 0] - ref[0]) ** 2
               + (arr[i, 1] - ref[1]) ** 2)


# ------------------------------------------------------------------- podas

def podar_cadena(v2, sk, pts, adj, start):
    """PODA-R: en cada bifurcacion del arbol enraizado en start queda solo la
    rama que llega mas lejos. Sin umbral."""
    dist, prev = v2.dijkstra(adj, start)
    fin = np.where(np.isfinite(dist))[0]
    if not len(fin):
        return None
    F = int(fin[int(np.argmax(dist[fin]))])
    cad = v2.reconstruct(prev, start, F)
    if len(cad) < 2:
        return None
    sk2 = np.zeros_like(sk)
    for i in cad:
        y, x = pts[i]
        sk2[y, x] = True
    return sk2


def podar_diametro(v2, sk, pts, adj):
    """PODA-D: la misma regla pero sin raiz. El punto fijo es el diametro."""
    sk2 = np.zeros_like(sk)
    tot = 0
    for miem in componentes(adj):
        if len(miem) < 2:
            if len(miem) == 1:
                y, x = pts[miem[0]]
                sk2[y, x] = True
                tot += 1
            continue
        d1, _ = v2.dijkstra(adj, miem[0])
        a = max(miem, key=lambda i: d1[i] if np.isfinite(d1[i]) else -1.0)
        d2, p2 = v2.dijkstra(adj, a)
        b = max(miem, key=lambda i: d2[i] if np.isfinite(d2[i]) else -1.0)
        cam = v2.reconstruct(p2, a, b) or [a, b]
        for i in cam:
            y, x = pts[i]
            sk2[y, x] = True
            tot += 1
    return sk2 if tot >= 2 else None


def podar_costillas(sk, pts, adj, dt, k, max_it=20):
    """PODA-C: se corta la ramita colgante cuyo largo geodesico L sea menor que
    k veces el radio local de la banda en el nodo de bifurcacion, r = DT[b].
    Relativo, sin umbral en pixeles. Conserva las bifurcaciones reales."""
    n = len(pts)
    vivo = np.ones(n, bool)

    for _ in range(max_it):
        grado = np.zeros(n, np.int32)
        for i in range(n):
            if not vivo[i]:
                continue
            g = 0
            for j, _w in adj[i]:
                if vivo[j]:
                    g += 1
            grado[i] = g
        quitar = []
        for h in range(n):
            if not vivo[h] or grado[h] != 1:
                continue
            prevn = -1
            cur = h
            L = 0.0
            nodos = []
            b = -1
            guard = 0
            while guard < 3000:
                guard += 1
                nb = [(j, w) for j, w in adj[cur]
                      if vivo[j] and j != prevn]
                if len(nb) > 1:
                    b = cur
                    break
                nodos.append(cur)
                if not nb:
                    b = -1
                    break
                j, w = nb[0]
                L += w
                prevn = cur
                cur = j
            if b < 0 or not nodos:
                continue
            yb, xb = pts[b]
            if L < k * float(dt[yb, xb]):
                quitar.extend(nodos)
        if not quitar:
            break
        for i in quitar:
            vivo[i] = False
        if int(vivo.sum()) < 2:
            return None

    if int(vivo.sum()) < 2 or int(vivo.sum()) == n:
        return None if int(vivo.sum()) < 2 else sk
    sk2 = np.zeros_like(sk)
    for i in np.where(vivo)[0]:
        y, x = pts[i]
        sk2[y, x] = True
    return sk2


# --------------------------------------------------- pipeline reimplementado

def calcular(v2, yo, comp, mode, sk, cfg):
    """Reimplementacion COMPLETA de path_target (incluida la eleccion de start)
    con la poda previa insertada entre skeletonize y graph_from_skeleton."""
    pts, adj, deg = v2.graph_from_skeleton(sk)
    if len(pts) < 2:
        return None
    simple = "AHEAD" if mode.startswith("AHEAD") else mode

    sk_uso = sk
    start_orig = None
    if simple != "AHEAD" and cfg.get("poda"):
        sk2 = None
        if cfg["poda"] == "R":
            start_orig = elegir_start(v2, yo, pts, comp, mode)
            if start_orig is not None:
                sk2 = podar_cadena(v2, sk, pts, adj, start_orig)
        elif cfg["poda"] == "D":
            sk2 = podar_diametro(v2, sk, pts, adj)
        elif cfg["poda"] == "C":
            dt = cv2.distanceTransform((comp > 0).astype(np.uint8),
                                       cv2.DIST_L2, 5)
            sk2 = podar_costillas(sk, pts, adj, dt, cfg["k"])
        if sk2 is None or int(sk2.sum()) < 2:
            USO["poda_degen"] += 1
        else:
            if start_orig is None:
                start_orig = elegir_start(v2, yo, pts, comp, mode)
            p_orig = pts[start_orig] if start_orig is not None else None
            USO["px_in"] += int(sk.sum())
            USO["px_out"] += int(sk2.sum())
            USO["poda_ok"] += 1
            sk_uso = sk2
            pts, adj, deg = v2.graph_from_skeleton(sk_uso)
            if len(pts) < 2:
                return None
            st_new = elegir_start(v2, yo, pts, comp, mode)
            if st_new is not None and p_orig is not None \
                    and pts[st_new] != p_orig:
                USO["start_movido"] += 1
            # DIAGNOSTICO: podar el grafo pero NO dejar que el start se mueva.
            # Aisla "el grafo cambio" de "maxy bajo y la ventana y>=maxy-8 se
            # corrio". El start original esta siempre en la cadena podada.
            if cfg.get("start_fijo") and p_orig is not None:
                try:
                    fijo = pts.index(p_orig)
                except ValueError:
                    fijo = None
                if fijo is not None:
                    return _resolver(v2, yo, comp, mode, sk_uso, pts, adj,
                                     fijo, cfg)

    start = elegir_start(v2, yo, pts, comp, mode)
    if start is None:
        return None
    return _resolver(v2, yo, comp, mode, sk_uso, pts, adj, start, cfg)


def _resolver(v2, yo, comp, mode, sk_uso, pts, adj, start, cfg):
    simple = "AHEAD" if mode.startswith("AHEAD") else mode
    sy, sx = pts[start]
    dist, prev = v2.dijkstra(adj, start)
    fin = np.where(np.isfinite(dist))[0]
    if not len(fin):
        return None

    if simple == "AHEAD":
        maxy = max(y for y, x in pts)
        cands = [i for i in fin if pts[i][0] >= maxy - 4]
        if not cands:
            cands = [start]
        ref = yo.prev_target if yo.prev_target is not None else (sx, sy)
        ti = min(cands, key=lambda i: (pts[i][1] - ref[0]) ** 2
                 + (pts[i][0] - ref[1]) ** 2)
        camino = [start, ti] if ti != start else [start]
    else:
        lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            cands = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
                :min(30, len(fin))]

        if cfg.get("camino"):
            F = int(fin[int(np.argmax(dist[fin]))])
            cadena = set(v2.reconstruct(prev, start, F) or [])
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub
            else:
                USO["camino_vacio"] += 1

        if cfg.get("mono") and yo.prev_target is not None:
            ys = np.array([q[0] for q in pts])
            xs = np.array([q[1] for q in pts])
            dd = ((xs[fin] - yo.prev_target[0]) ** 2
                  + (ys[fin] - yo.prev_target[1]) ** 2)
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
            s += 0.55 * v2.angdiff(h, yo.prev_heading)
            if yo.prev_target is not None:
                s += 0.10 * math.hypot(x - yo.prev_target[0],
                                       y - yo.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        ti = min(cands, key=score)
        camino = v2.reconstruct(prev, start, ti) or [start, ti]

    ty, tx = pts[ti]
    return sk_uso, dict(
        start=(float(sx), float(sy)), target=(float(tx), float(ty)),
        heading=math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6))),
        path=[(float(pts[i][1]), float(pts[i][0])) for i in camino])


def instalar(v2, cfg):
    o_p = v2.NuevoCodeV2.path_target

    def p(self, comp, mode):
        sk, res = o_p(self, comp, mode)
        if res is None:
            return sk, res
        USO["frames"] += 1
        mio = calcular(v2, self, comp, mode, sk, cfg)
        if mio is None:
            USO["sin_res"] += 1
            return sk, res
        sk_uso, r2 = mio

        if not (cfg.get("poda") or cfg.get("camino") or cfg.get("mono")):
            CHK["n"] += 1
            if (abs(r2["target"][0] - res["target"][0]) > 1e-6
                    or abs(r2["target"][1] - res["target"][1]) > 1e-6
                    or abs(r2["heading"] - res["heading"]) > 1e-6):
                CHK["mal"] += 1
            if (abs(r2["start"][0] - res["start"][0]) > 1e-6
                    or abs(r2["start"][1] - res["start"][1]) > 1e-6):
                CHK["mal_start"] += 1
            return sk, res

        return (sk_uso if cfg.get("sk_podado") else sk), r2

    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


# ----------------------------------------------------------------- el banco

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


def correr_variante(SinBranch, v2, cfg, videos, controles):
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, suav=[],
               s_max=0.0)
    for vid in videos:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru):
            continue
        m = AB.metricas(serie(SinBranch, v2, ru, FPS))
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
        tot["s_max"] = max(tot["s_max"], m["s_max"])
        tot["suav"].append(m["suav"])
    ctl = []
    okc = True
    for cn, vid, fps, d0, h0, ex in controles:
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
            okc &= (smax >= 88.0)
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav"])) if tot["suav"] else float("nan")
    return tot, ctl, okc


VARIANTES = [
    ("BASE", dict()),
    ("CAMINO", dict(camino=True)),
    ("PODA-R", dict(poda="R")),
    ("PODA-D", dict(poda="D")),
    ("PODA-C k=0.5", dict(poda="C", k=0.5)),
    ("PODA-C k=1.0", dict(poda="C", k=1.0)),
    ("PODA-C k=1.5", dict(poda="C", k=1.5)),
    ("PODA-C k=2.0", dict(poda="C", k=2.0)),
    ("PODA-C k=3.0", dict(poda="C", k=3.0)),
    ("CAMINO+MONO", dict(camino=True, mono=True)),
    ("PODA-R+MONO", dict(poda="R", mono=True)),
    ("PODA-D+MONO", dict(poda="D", mono=True)),
    ("PODA-C1.5+MONO", dict(poda="C", k=1.5, mono=True)),
    ("PODA-C1.5+CAM+MONO", dict(poda="C", k=1.5, camino=True, mono=True)),
    ("PODA-D  skPodado", dict(poda="D", sk_podado=True)),
    ("PODA-C1.5 skPodado", dict(poda="C", k=1.5, sk_podado=True)),
]

# Diagnostico del mecanismo. PODA-R usa LA MISMA REGLA que CAMINO (la cadena
# start -> nodo mas lejano) pero rinde la mitad. Hay dos sospechosos:
#   (a) al podar cae `maxy` y la ventana y>=maxy-8 se corre, asi que el start
#       se muda a otro pixel  -> se mide congelando el start
#   (b) CAMINO, cuando la cadena no interseca la shell, vuelve a los candidatos
#       SIN restringir; la poda no tiene esa salida de emergencia
# Si PODA-R con start congelado reproduce CAMINO, el culpable es (a).
DIAG = [
    ("BASE", dict()),
    ("CAMINO", dict(camino=True)),
    ("PODA-R", dict(poda="R")),
    ("PODA-R startFijo", dict(poda="R", start_fijo=True)),
    ("CAMINO+MONO", dict(camino=True, mono=True)),
    ("PODA-R startFijo+MONO", dict(poda="R", start_fijo=True, mono=True)),
]


def main():
    ap = argparse.ArgumentParser(description="Poda previa del esqueleto")
    ap.add_argument("--smoke", action="store_true",
                    help="1 video corto y 3 variantes, para medir tiempos")
    ap.add_argument("--diag", action="store_true",
                    help="por que PODA-R rinde la mitad que CAMINO con la "
                         "misma regla: congela el start")
    a = ap.parse_args()
    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)

    videos = AB.AUTONOMOS
    controles = AB.CONTROLES
    variantes = DIAG if a.diag else VARIANTES
    if a.smoke:
        videos = ["con_planner.avi"]
        variantes = [VARIANTES[0], VARIANTES[1], VARIANTES[3], VARIANTES[6]]
        controles = [c for c in AB.CONTROLES if c[0] == "lineal_positivo"]

    print("")
    print("=" * 108)
    print("  PODA PREVIA - podar el ESQUELETO antes de Dijkstra, y volver a")
    print("  correr maxy -> start -> Dijkstra -> shell sobre el esqueleto podado.")
    print("  Tres reglas RELATIVAS, ningun umbral en pixeles.")
    print("  PODA-R  argmax en cada bifurcacion, enraizado en start")
    print("  PODA-D  lo mismo sin raiz = diametro del esqueleto")
    print("  PODA-C  ramita colgante con L < k * DT[bifurcacion]  (banda de k)")
    print("=" * 108)

    base = None
    filas = []
    print("")
    for nom, cfg in variantes:
        t0 = time.time()
        CHK["n"] = CHK["mal"] = CHK["mal_start"] = 0
        reset_uso()
        rest = instalar(v2, cfg)
        try:
            tot, ctl, okc = correr_variante(SinBranch, v2, cfg, videos,
                                            controles)
        finally:
            rest()
        dt = time.time() - t0

        if nom == "BASE":
            base = tot
            print("  FIDELIDAD sobre %d frames con path: %d discrepancias de "
                  "target/heading, %d de start   %s"
                  % (CHK["n"], CHK["mal"], CHK["mal_start"],
                     "OK" if (CHK["mal"] == 0 and CHK["mal_start"] == 0)
                     else "*** ABORTA"))
            if CHK["mal"] or CHK["mal_start"]:
                print("  La reimplementacion NO reproduce la candidata. "
                      "Todo lo que siga seria basura. Corto aca.")
                return 3
            print("")
            print("  BASELINE  disp %.2f %%  sin_aut %d  huecos %d  saltos %d  "
                  "inversiones %d  suav %.2f   (%.0f s)"
                  % (tot["disp"], tot["sin_aut"], tot["huecos"], tot["s_gt"],
                     tot["inv"], tot["suav"], dt))
            print("")
            print("  %-20s %8s %8s %8s %9s %11s %8s   %s"
                  % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
                     "inversiones", "suav", "controles"))
            print("  " + "-" * 104)
            print("  %-20s %+8.2f %+8d %+8d %+9d %+11d %+8.2f   %s %s"
                  % ("BASE", 0, 0, 0, 0, 0, 0, "  ".join(ctl),
                     "OK" if okc else "*** FALLA"))
            filas.append((nom, tot, okc))
            continue

        print("  %-20s %+8.2f %+8d %+8d %+9d %+11d %+8.2f   %s %s"
              % (nom, tot["disp"] - base["disp"],
                 tot["sin_aut"] - base["sin_aut"],
                 tot["huecos"] - base["huecos"], tot["s_gt"] - base["s_gt"],
                 tot["inv"] - base["inv"], tot["suav"] - base["suav"],
                 "  ".join(ctl), "OK" if okc else "*** FALLA"))
        if cfg.get("poda"):
            pod = USO["poda_ok"]
            pc = (100.0 * (USO["px_in"] - USO["px_out"]) / max(USO["px_in"], 1))
            print("       poda aplicada %d/%d frames, degenerada %d, "
                  "quita %.1f %% de los px, mueve start en %d frames, "
                  "sin resultado %d   (%.0f s)"
                  % (pod, USO["frames"], USO["poda_degen"], pc,
                     USO["start_movido"], USO["sin_res"], dt))
        filas.append((nom, tot, okc))

    # ---- comparacion explicita contra CAMINO, que es la pregunta de la tarea
    ref = dict((n, t) for n, t, _o in filas)
    if "CAMINO" in ref:
        c = ref["CAMINO"]
        print("")
        print("  DELTAS CONTRA CAMINO (la pregunta: la poda da algo que")
        print("  restringir candidatos no da?)")
        print("  %-20s %8s %8s %8s %9s %11s %8s"
              % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
                 "inversiones", "suav"))
        print("  " + "-" * 84)
        for n, t, _o in filas:
            if n in ("BASE", "CAMINO"):
                continue
            print("  %-20s %+8.2f %+8d %+8d %+9d %+11d %+8.2f"
                  % (n, t["disp"] - c["disp"], t["sin_aut"] - c["sin_aut"],
                     t["huecos"] - c["huecos"], t["s_gt"] - c["s_gt"],
                     t["inv"] - c["inv"], t["suav"] - c["suav"]))

    print("")
    print("  CRITERIO PREREGISTRADO: la poda aporta solo si mejora contra")
    print("  CAMINO sin empeorar disponibilidad, huecos ni saltos, y sin")
    print("  romper ningun control positivo.")
    print("=" * 108)
    return 0


if __name__ == "__main__":
    sys.exit(main())
