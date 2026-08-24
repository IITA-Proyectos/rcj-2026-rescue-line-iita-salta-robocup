# -*- coding: utf-8 -*-
"""
RETRO GUARD EXPERIMENTAL - UNA politica minima y descartable para H10.

Pedido por ChatGPT en #138 con condiciones estrictas. Esto NO es una candidata:
es UNA prueba falsable. Si no cumple el criterio de promocion, H10 queda como
diagnostico confirmado y politica descartada, exactamente como H9, y no se
sigue tuneando.

BASELINE   SinBranch = V2 + SpatialTargetGuard   (sin V3, sin H9-GATE)
VARIANTE   SinBranch + H10 experimental

DONDE INTERVIENE Y POR QUE AHI
------------------------------
Sobre la salida de `path_target`, o sea ANTES del cap de continuidad. El cap no
arregla la eleccion: la convierte en un barrido suave. Por eso en `seguir` el
episodio no produjo ningun salto >24 px y si produjo una inversion.

QUE HACE Y QUE NO HACE
----------------------
NO hace "target = la rama que llega mas arriba" globalmente. Interviene solo con
geometria de alta confianza, y ante cualquier ambiguedad deja el baseline:

  1. modo NEAR (nunca AHEAD ni AHEAD_BRIDGE);
  2. la shell geodesica es REAL, no el fallback de `sorted(finite,...)[:30]`;
  3. el target elegido esta dentro de esa shell real;
  4. desde `start` hay EXACTAMENTE DOS direcciones sustanciales.
     Esto es lo que separa el caso retrogrado de un T/cruce: en una T el robot
     viene por el pie, asi que desde `start` hay UNA sola direccion y la
     bifurcacion aparece mas adelante. Con tres o mas direcciones -cruce real-
     NO se interviene;
  5. la BIFURCACION REAL entre el target elegido y la alternativa -su ancestro
     comun en el arbol de Dijkstra, que puede estar mucho mas adelante que el
     start- tiene EXACTAMENTE DOS ramas sustanciales. Con tres o mas es un
     cruce real y NO se interviene. Un T simetrico se cae solo por (6): sus
     dos brazos tienen alcance parecido, asi que delta es chico;
  6. delta_alcance >= umbral preregistrado.

Si algo de eso falla: baseline, sin tocar nada.

  * no inventa pixeles: el reemplazo es un nodo REAL del esqueleto de este frame
    y de la misma shell;
  * no sostiene signo ni target viejo: no usa memoria;
  * dentro de la rama correcta elige el punto de lookahead (min |d - LOOKAHEAD|),
    o sea el criterio geometrico de V2, sin replicar su score.

NO MODIFICA V2/V3/V4 NI SinBranch. Espia reversible sobre `path_target`.

A/B PREREGISTRADO
-----------------
Se corren TODOS los umbrales 10/15/20/30/40. No se elige primero el que mejor
queda. Metrica primaria: INVERSIONES de steer.

    python3 retro_guard_exp.py
    python3 retro_guard_exp.py --seguir      # solo el detalle de f1181-1190
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
UMBRALES = (10, 15, 20, 30, 40)
DIR_MIN_NODOS = 12       # nodos minimos para que una direccion cuente
AUTONOMOS = list(AB.AUTONOMOS)

CAP = {}
LOG = []                 # intervenciones, para auditoria visual
GATES = {}               # por que NO intervino, condicion por condicion


def _g(k):
    GATES[k] = GATES.get(k, 0) + 1


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


def alcance_y_ramas(pts, dist, prev, si):
    """Devuelve (alcance de subarbol, id de rama desde start, tamanos)."""
    n = len(pts)
    alc = np.array([p[0] for p in pts], np.int32)
    rama = np.full(n, -1, np.int32)
    fin = np.where(np.isfinite(dist))[0]
    orden_asc = fin[np.argsort(dist[fin])]
    for i in orden_asc:
        if i == si:
            continue
        pa = prev[i]
        rama[i] = i if pa == si else (rama[pa] if pa != -1 else -1)
    for i in fin[np.argsort(-dist[fin])]:
        pa = prev[i]
        if pa != -1 and alc[i] < alc[pa]:
            alc[pa] = alc[i]
    tam = {}
    for i in fin:
        if rama[i] >= 0:
            tam[rama[i]] = tam.get(rama[i], 0) + 1
    # tamano de subarbol de CADA nodo, para poder mirar la bifurcacion real
    sub = np.ones(n, np.int32)
    for i in fin[np.argsort(-dist[fin])]:
        pa = prev[i]
        if pa != -1:
            sub[pa] += sub[i]
    return alc, rama, tam, sub


def ancestro_comun(prev, a, b):
    """Nodo donde se separan los caminos de a y b en el arbol de Dijkstra.
    LA BIFURCACION REAL no es el start: puede estar mucho mas adelante."""
    vistos = set()
    x = a
    while x != -1:
        vistos.add(x)
        x = prev[x]
    y = b
    while y != -1 and y not in vistos:
        y = prev[y]
    return y


def hijos_sustanciales(prev, sub, fin, nodo, minimo):
    return [i for i in fin if prev[i] == nodo and sub[i] >= minimo]


def instalar(v2, umbral, activo, contexto):
    """Espia reversible. `activo` es una lista de un bool para poder apagarlo."""
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    o_r = v2.reconstruct

    def g(sk):
        r = o_g(sk)
        CAP["pts"], CAP["adj"], CAP["deg"] = r
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["si"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        CAP.clear()
        sk, res = o_p(self, comp, mode)
        if not activo[0] or res is None or "dist" not in CAP:
            return sk, res
        if mode != "NEAR":                      # (1) solo NEAR
            _g("1_no_NEAR")
            return sk, res
        pts, dist, prev = CAP["pts"], CAP["dist"], CAP["prev"]
        si = CAP["si"]
        sy, sx = pts[si]
        lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        fin = np.where(np.isfinite(dist))[0]
        shell = [i for i in fin
                 if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not shell:                           # (2) shell real, no fallback
            _g("2_shell_vacia")
            return sk, res
        idx = {}
        for i, q in enumerate(pts):
            idx.setdefault(q, i)
        ti = idx.get((int(round(res["target"][1])),
                      int(round(res["target"][0]))))
        if ti is None or ti not in shell:       # (3) target dentro de la shell
            _g("3_target_fuera_shell")
            return sk, res

        alc, rama, tam, sub = alcance_y_ramas(pts, dist, prev, si)
        dirs = [k for k, c in tam.items() if c >= DIR_MIN_NODOS]
        if len(dirs) != 2:                      # (4) exactamente dos direcciones
            _g("4_dirs_%d" % len(dirs))
            return sk, res
        mejor = min(shell, key=lambda i: alc[i])
        if mejor == ti:
            _g("5_mismo_nodo")
            return sk, res
        # (5) la bifurcacion REAL entre elegido y alternativa. NO es el start.
        L = ancestro_comun(prev, ti, mejor)
        if L is None or L == -1:
            _g("5_sin_ancestro")
            return sk, res
        hijos = hijos_sustanciales(prev, sub, fin, L, DIR_MIN_NODOS)
        if len(hijos) >= 3:                     # cruce real: NO intervenir
            _g("5_cruce_%d_ramas" % len(hijos))
            return sk, res
        if len(hijos) < 2:
            _g("5_sin_bifurcacion")
            return sk, res
        delta = int(alc[ti] - alc[mejor])
        if delta < umbral:                      # (6) umbral preregistrado
            _g("6_delta_%s" % ("0" if delta == 0 else "bajo"))
            return sk, res

        # dentro de la rama correcta, el punto de lookahead. Nodo REAL.
        rama_ok = mejor
        while prev[rama_ok] != L and prev[rama_ok] != -1:
            rama_ok = prev[rama_ok]
        cands = [i for i in shell
                 if ancestro_comun(prev, i, mejor) != L or i == mejor]
        nuevo = min(cands, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))
        ny, nx = pts[nuevo]
        camino = o_r(prev, si, nuevo) or [si, nuevo]
        LOG.append(dict(video=contexto[0], frame=contexto[1], delta=delta,
                        antes=(float(res["target"][0]), float(res["target"][1])),
                        despues=(float(nx), float(ny)),
                        start=(float(sx), float(sy)),
                        alc_antes=int(alc[ti]), alc_despues=int(alc[nuevo]),
                        n_dirs=len(dirs), umbral=umbral))
        res = dict(
            start=res["start"], target=(float(nx), float(ny)),
            heading=math.degrees(math.atan2(nx - sx, max(sy - ny, 1e-6))),
            path=[(float(pts[i][1]), float(pts[i][0])) for i in camino])
        return sk, res

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


def corrida(SinBranch, v2, ruta, fps, contexto, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(fps)
    ser = []
    i = 0
    W, C = v2.W, v2.CENTER
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        contexto[1] = i
        g = v2.frame_pi(fr)
        r = tr.step(g)
        if i >= desde:
            t = r.get("target")
            s = None if t is None else float(np.clip(
                -90.0 * (t[0] - C) / (W / 2.0), -90, 90))
            ser.append((t, s, r.get("state")))
        i += 1
    cap.release()
    return ser


def agregado(SinBranch, v2, contexto):
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, perdida=0)
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        contexto[0] = vid
        ser = corrida(SinBranch, v2, ruta, FPS, contexto)
        m = AB.metricas(ser)
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
        tot["perdida"] += sum(1 for _t, _s, e in ser if e == "PERDIDA")
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    return tot


def controles(SinBranch, v2, contexto):
    out = {}
    for nom, vid, fps, d, h, ex in AB.CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        contexto[0] = vid
        ser = corrida(SinBranch, v2, ruta, fps, contexto, d, h)
        m = AB.metricas(ser)
        st = [s for _t, s, _e in ser if s is not None]
        out[nom] = dict(con=m["con"], esperado=ex, n=m["n"],
                        huecos=m["huecos"], s_gt=m["s_gt"], inv=m["inv"],
                        smax=max(st) if st else None,
                        smin=min(st) if st else None)
    return out


def main():
    ap = argparse.ArgumentParser(description="H10 politica experimental")
    ap.add_argument("--seguir", action="store_true")
    a = ap.parse_args()

    v4, v3, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    ctx = ["", 0]
    activo = [False]
    restaurar = instalar(v2, 0, activo, ctx)

    if a.seguir:
        print("")
        print("  seguir f1178-1195: RAW de path_target, ANTES del cap")
        print("  %6s | %-22s | %-22s" % ("frame", "BASELINE raw", "H10 raw"))
        base = {}
        for modo, umb in (("base", None), ("h10", 15)):
            activo[0] = (modo == "h10")
            restaurar()
            restaurar_ = instalar(v2, umb or 0, activo, ctx)
            ctx[0] = "seguir.avi"
            cap = cv2.VideoCapture(os.path.join(AQUI, "seguir.avi"))
            tr = SinBranch(FPS)
            i = 0
            crudos = {}
            o_p = v2.NuevoCodeV2.path_target

            def espia(self, comp, mode, _o=o_p):
                sk, res = _o(self, comp, mode)
                if res is not None:
                    crudos[ctx[1]] = tuple(res["target"])
                return sk, res
            v2.NuevoCodeV2.path_target = espia
            while i <= 1195:
                ok, fr = cap.read()
                if not ok:
                    break
                ctx[1] = i
                tr.step(v2.frame_pi(fr))
                i += 1
            cap.release()
            v2.NuevoCodeV2.path_target = o_p
            restaurar_()
            base[modo] = crudos
        for f in range(1178, 1196):
            b = base["base"].get(f)
            h = base["h10"].get(f)
            marca = "  <== CAMBIA" if b and h and b != h else ""
            print("  %6d | %-22s | %-22s%s"
                  % (f, "(%.0f,%.0f)" % b if b else "--",
                     "(%.0f,%.0f)" % h if h else "--", marca))
        return 0

    print("")
    print("=" * 104)
    print("  H10 - POLITICA EXPERIMENTAL. A/B PREREGISTRADO SOBRE 10/15/20/30/40")
    print("  metrica primaria: INVERSIONES. Los umbrales se corren TODOS.")
    print("=" * 104)

    activo[0] = False
    del LOG[:]
    b_tot = agregado(SinBranch, v2, ctx)
    b_ctl = controles(SinBranch, v2, ctx)
    print("")
    print("  BASELINE  disp %.2f %%  sin_aut %d  huecos %d  saltos>24 %d  "
          "inversiones %d  PERDIDA %d"
          % (b_tot["disp"], b_tot["sin_aut"], b_tot["huecos"], b_tot["s_gt"],
             b_tot["inv"], b_tot["perdida"]))
    print("")
    print("  %5s %8s %9s %8s %9s %11s %9s %9s"
          % ("umbr", "interv", "disp %", "huecos", "saltos>24", "INVERSIONES",
             "sin_aut", "PERDIDA"))
    print("  %5s %8s %+9.2f %+8d %+9d %+11d %+9d %+9d"
          % ("base", "-", 0.0, 0, 0, 0, 0, 0))

    filas = []
    for U in UMBRALES:
        restaurar()
        restaurar = instalar(v2, U, activo, ctx)
        activo[0] = True
        del LOG[:]
        GATES.clear()
        t = agregado(SinBranch, v2, ctx)
        n_int = len(LOG)
        if U == 15:
            print("        gates: %s" % sorted(GATES.items(),
                                                key=lambda z: -z[1])[:8])
        c = controles(SinBranch, v2, ctx)
        filas.append((U, t, c, n_int, list(LOG)))
        print("  %5d %8d %+9.2f %+8d %+9d %+11d %+9d %+9d"
              % (U, n_int, t["disp"] - b_tot["disp"],
                 t["huecos"] - b_tot["huecos"], t["s_gt"] - b_tot["s_gt"],
                 t["inv"] - b_tot["inv"], t["sin_aut"] - b_tot["sin_aut"],
                 t["perdida"] - b_tot["perdida"]))
        activo[0] = False

    print("")
    print("  GUARDRAILS OBLIGATORIOS")
    print("  %5s %-16s %-16s %-14s %-14s %s"
          % ("umbr", "lineal_positivo", "hist_exito", "video_4_pre",
             "video_4_post", "veredicto"))
    for U, t, c, n_int, _lg in filas:
        lp = c.get("lineal_positivo", {})
        he = c.get("hist_exito", {})
        v4a = c.get("video_4_pre", {})
        v4b = c.get("video_4_post", {})
        ok_lp = lp.get("con") == lp.get("esperado")
        ok_he = he.get("con") == he.get("esperado")
        ok_87 = (lp.get("smax") or 0) >= 85.0
        ok_v4 = (v4a.get("con") == b_ctl["video_4_pre"]["con"]
                 and v4b.get("con") == b_ctl["video_4_post"]["con"])
        ok_m = (t["disp"] >= b_tot["disp"] - 1e-9
                and t["huecos"] <= b_tot["huecos"]
                and t["s_gt"] <= b_tot["s_gt"]
                and t["perdida"] <= b_tot["perdida"])
        mejora = t["inv"] < b_tot["inv"]
        todo = ok_lp and ok_he and ok_87 and ok_v4 and ok_m and mejora
        print("  %5d %-16s %-16s %-14s %-14s %s"
              % (U, "%d/%s %s" % (lp.get("con"), lp.get("esperado"),
                                  "OK" if ok_lp else "FALLA"),
                 "%d/%s %s" % (he.get("con"), he.get("esperado"),
                               "OK" if ok_he else "FALLA"),
                 "%d %s" % (v4a.get("con"), "OK" if ok_v4 else "FALLA"),
                 "%d" % v4b.get("con"),
                 "PROMOVIBLE" if todo else "NO"))
        if not ok_87:
            print("        *** lineal_positivo perdio el +87 grados: smax %.1f"
                  % (lp.get("smax") or 0))

    print("")
    print("  DETALLE DE GUARDRAILS POR UMBRAL")
    for U, t, c, n_int, _lg in filas:
        print("    U=%-3d  disp %+.3f  huecos %+d  saltos %+d  PERDIDA %+d  "
              "sin_aut %+d   |  inversiones %+d"
              % (U, t["disp"] - b_tot["disp"], t["huecos"] - b_tot["huecos"],
                 t["s_gt"] - b_tot["s_gt"], t["perdida"] - b_tot["perdida"],
                 t["sin_aut"] - b_tot["sin_aut"], t["inv"] - b_tot["inv"]))

    # auditoria: guardar el log del umbral mediano
    med = [f for f in filas if f[0] == 20]
    if med:
        lg = med[0][4]
        with open(os.path.join(AQUI, "retro_guard_interv.csv"), "w",
                  encoding="utf-8") as f:
            f.write("video,frame,delta,antes_x,antes_y,despues_x,despues_y,"
                    "start_x,start_y,alc_antes,alc_despues\n")
            for e in lg:
                f.write("%s,%d,%d,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%d,%d\n"
                        % (e["video"], e["frame"], e["delta"], e["antes"][0],
                           e["antes"][1], e["despues"][0], e["despues"][1],
                           e["start"][0], e["start"][1], e["alc_antes"],
                           e["alc_despues"]))
        print("")
        print("  log de intervenciones (U=20, %d) -> retro_guard_interv.csv"
              % len(lg))

    print("")
    print("  CRITERIO DE PROMOCION (los cinco, o H10 politica CAE)")
    print("    1. baja inversiones de forma material")
    print("    2. la mejora es estable en una BANDA de umbrales")
    print("    3. no rompe ningun control")
    print("    4. no compra inversiones a costa de disp/huecos/saltos")
    print("    5. las intervenciones auditadas son semanticamente correctas")
    print("=" * 104)
    restaurar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
