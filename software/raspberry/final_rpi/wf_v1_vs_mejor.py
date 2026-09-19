# -*- coding: utf-8 -*-
"""
V1 (POI) CONTRA CAMINO+MONO, CON EL MISMO METRO.

POR QUE
-------
`ab_v1_vs_candidata.py` midio V1 contra la CANDIDATA SinBranch pelada. Pero la
candidata pelada ya no es el mejor: `camino_principal.py` mostro que
CAMINO+MONO mejora las cinco metricas a la vez sobre ella. O sea que V1 se
comparo contra un rival que ya fue superado.

Este banco corre LAS TRES en la misma tabla, mismos 10 videos, mismas metricas,
mismos controles:

    BASELINE      la candidata SinBranch tal cual (= NuevoCodeV4 con el
                  branch_guard neutralizado)
    CAMINO+MONO   el mejor actual: candidatos restringidos a la cadena
                  start -> nodo mas lejano del arbol de Dijkstra, y busqueda
                  monotona hacia adelante (Coulter 1992)
    V1            POI sobre contorno crudo (Overengineering 2024 / Airborne
                  2025), sin esqueleto, sin grafo, sin Dijkstra

DOS COLUMNAS EXTRA QUE YA SE SABE QUE IMPORTAN
---------------------------------------------
  dx>24     saltos medidos SOLO EN COLUMNA. El steer de este robot es
            -90*(x-CENTER)/(W/2): depende UNICAMENTE de x. Un salto de fila
            pura no mueve ni un grado el comando. La metrica euclidea `s_gt`
            los cuenta igual, y por eso castiga a V1, que mueve el target
            arriba y abajo del contorno.
  dsteer    |cambio de steer| entre frames consecutivos con target en los dos.
            Se reportan p90 y max. `suav` ya es la MEDIANA de esa misma lista;
            p90 mide la cola que el robot realmente siente y max el peor
            evento. Misma convencion que `suav` para que las tres columnas
            hablen de la misma poblacion.

FIDELIDAD
---------
El espia sobre `path_target` re-implementa el selector para poder restringir
los candidatos. Con CAMINO y MONO apagados tiene que devolver EXACTAMENTE el
target de la candidata. Se verifica frame a frame y una sola discrepancia
aborta el banco.

Las tres corren en la MISMA pasada de video: el frame se decodifica una vez y
se le da a los tres trackers (`frame_pi` de nuevo_code_v2 y `frame_de_la_pi`
de airborne_v1_adaptado son la misma funcion, byte por byte). Cada tracker
arrastra su propio estado.

REPLAY OPEN-LOOP: mide PERCEPCION, no trayectoria. Nada de lo que salga aca
dice cual de las dos dobla mejor.

    python wf_v1_vs_mejor.py
    python wf_v1_vs_mejor.py --solo hist.avi     (prueba rapida)
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
UMBRAL = 24.0

CAP = {}
CFG = {"camino": False, "mono": False}
CHK = {"n": 0, "mal": 0}
USO = {"camino_ok": 0, "camino_vacio": 0, "mono_vacio": 0}


# --------------------------------------------------------------------------
# carga
# --------------------------------------------------------------------------
def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    sp1 = importlib.util.spec_from_file_location(
        "airborne_v1", os.path.join(AQUI, "airborne_v1_adaptado.py"))
    v1 = importlib.util.module_from_spec(sp1)
    sp1.loader.exec_module(v1)
    return v4, v4.v3.v2, v1


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
# el espia reversible sobre path_target (identico al de camino_principal.py)
# --------------------------------------------------------------------------
def es_ancestro(prev, ancla, cand):
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


def instalar(v2):
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

        # --- CAMINO PRINCIPAL ------------------------------------------------
        if CFG["camino"] and len(fin):
            F = int(fin[int(np.argmax(dist[fin]))])
            cadena = set(o_r(prev, si, F) or [])
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub
                USO["camino_ok"] += 1
            else:
                USO["camino_vacio"] += 1

        # --- MONOTONIA HACIA ADELANTE ---------------------------------------
        if CFG["mono"] and self.prev_target is not None and len(fin):
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

        if not CFG["camino"] and not CFG["mono"]:
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
# una sola pasada de video para las tres versiones
# --------------------------------------------------------------------------
NOMS = ("BASELINE", "CAMINO+MONO", "V1")


def pasada(SinBranch, v2, v1mod, ruta, fps, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tb, tc = SinBranch(fps), SinBranch(fps)
    tv = v1mod.AirborneV1(fps)
    out = {n: [] for n in NOMS}
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        g = v2.frame_pi(fr)

        CFG["camino"] = False
        CFG["mono"] = False
        rb = tb.step(g)

        CFG["camino"] = True
        CFG["mono"] = True
        rc = tc.step(g)

        CFG["camino"] = False
        CFG["mono"] = False
        rv = tv.paso(g)

        if i >= desde:
            for nom, r in (("BASELINE", rb), ("CAMINO+MONO", rc)):
                t = r.get("target")
                out[nom].append((t, None if t is None else float(np.clip(
                    -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                    r.get("state")))
            t = rv.get("target")
            a = rv.get("angle_target")
            out["V1"].append(
                (t, None if (t is None or a is None or not np.isfinite(a))
                 else float(a), rv.get("estado")))
        i += 1
    cap.release()
    return out


# --------------------------------------------------------------------------
# metricas extra: saltos SOLO EN COLUMNA y |dsteer|
# --------------------------------------------------------------------------
def crudos_extra(serie):
    """Devuelve (|dx| a traves de los huecos, |dsteer| entre consecutivos).

    |dx| usa exactamente el mismo recorrido que `s_gt` de AB.metricas -contra
    el ultimo target que hubo, sin resetear en el hueco- pero se queda solo con
    la componente que el steer puede ver.

    |dsteer| usa la misma convencion que `suav`: pares de frames CONSECUTIVOS
    con target en los dos. Asi p90, max y suav describen la misma poblacion.
    """
    tg = [x[0] for x in serie]
    st = [x[1] for x in serie]
    dxc, dxg = [], []
    ult, ulti = None, -1
    for i, t in enumerate(tg):
        if t is None:
            continue
        if ult is not None:
            d = abs(t[0] - ult[0])
            if i == ulti + 1:
                dxc.append(d)      # frames CONTIGUOS: el steer lo ve entero
            else:
                dxg.append(d)      # a traves de un hueco: hubo frames sin
                                   # autoridad en el medio
        ult, ulti = t, i
    ds = [abs(b - a) for a, b in zip(st, st[1:])
          if a is not None and b is not None]
    xs = [t[0] for t in tg if t is not None]
    # duracion de cada hueco, en frames (mismo criterio de hueco que AB)
    dur = []
    largo = 0
    visto = False
    for t in tg:
        if t is None:
            if visto:
                largo += 1
        else:
            if largo:
                dur.append(largo)
            largo = 0
            visto = True
    return dxc, dxg, ds, xs, dur


def acumular(tot, m, dxc, dxg, ds, xs, dur):
    for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
        tot[k] += m[k]
    tot["s_max"] = max(tot["s_max"], m["s_max"])
    tot["suav_v"].append(m["suav"])
    tot["dxc"].extend(dxc)
    tot["dxg"].extend(dxg)
    tot["ds"].extend(ds)
    tot["xs"].extend(xs)
    tot["dur"].extend(dur)


def nuevo_tot():
    return dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, s_max=0.0,
                suav_v=[], dxc=[], dxg=[], ds=[], xs=[], dur=[])


def cerrar(tot):
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav_v"])) if tot["suav_v"] else float("nan")
    dxc = np.asarray(tot["dxc"]) if tot["dxc"] else np.array([0.0])
    dxg = np.asarray(tot["dxg"]) if tot["dxg"] else np.array([0.0])
    ds = np.asarray(tot["ds"]) if tot["ds"] else np.array([0.0])
    tot["dxc_gt"] = int((dxc > UMBRAL).sum())
    tot["dxg_gt"] = int((dxg > UMBRAL).sum())
    tot["dx_gt"] = tot["dxc_gt"] + tot["dxg_gt"]
    tot["dx_max"] = float(max(dxc.max(), dxg.max()))
    tot["ds_p90"] = float(np.percentile(ds, 90))
    tot["ds_p99"] = float(np.percentile(ds, 99))
    tot["ds_max"] = float(ds.max())
    tot["ds_gt"] = int((ds > 27.0).sum())
    tot["dxc_p99"] = float(np.percentile(dxc, 99))
    tot["dxc_max"] = float(dxc.max())
    xs = np.asarray(tot["xs"]) if tot["xs"] else np.array([80.0])
    tot["borde"] = 100.0 * float(((xs < 3.0) | (xs > 156.0)).mean())
    du = np.asarray(tot["dur"]) if tot["dur"] else np.array([0.0])
    tot["h_med"] = float(du.mean())
    tot["h_p90"] = float(np.percentile(du, 90))
    tot["h_max"] = float(du.max())
    return tot


CAB = ("  %-13s %8s %8s %8s %9s %7s %10s %8s %7s %7s %7s %6s"
       % ("version", "disp %", "sin_aut", "huecos", "saltos>24", "dx>24",
          "inversion.", "s_max", "ds p90", "ds p99", "ds max", "suav"))


def fila(nom, t):
    return ("  %-13s %8.2f %8d %8d %9d %7d %10d %8.1f %7.2f %7.2f %7.2f %6.2f"
            % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
               t["dx_gt"], t["inv"], t["s_max"], t["ds_p90"], t["ds_p99"],
               t["ds_max"], t["suav"]))


def fila_delta(nom, t, b):
    return ("  %-13s %+8.2f %+8d %+8d %+9d %+7d %+10d %+8.1f %+7.2f %+7.2f "
            "%+7.2f %+6.2f"
            % (nom, t["disp"] - b["disp"], t["sin_aut"] - b["sin_aut"],
               t["huecos"] - b["huecos"], t["s_gt"] - b["s_gt"],
               t["dx_gt"] - b["dx_gt"], t["inv"] - b["inv"],
               t["s_max"] - b["s_max"], t["ds_p90"] - b["ds_p90"],
               t["ds_p99"] - b["ds_p99"], t["ds_max"] - b["ds_max"],
               t["suav"] - b["suav"]))


def main():
    ap = argparse.ArgumentParser(description="V1 contra CAMINO+MONO")
    ap.add_argument("--solo", default=None,
                    help="correr un solo video (prueba rapida)")
    a = ap.parse_args()

    v4, v2, v1mod = cargar()
    SinBranch = hacer_sinbranch(v4)
    rest = instalar(v2)

    videos = [a.solo] if a.solo else list(AB.AUTONOMOS)

    print("")
    print("=" * 116)
    print("  V1 (POI sobre contorno crudo)  CONTRA  CAMINO+MONO (el mejor "
          "actual)  CONTRA  BASELINE (candidata SinBranch)")
    print("  Mismos %d videos, mismas metricas, mismos controles. Las tres "
          "en la misma pasada de frames." % len(videos))
    print("=" * 116)

    tot = {n: nuevo_tot() for n in NOMS}
    porvid = {}
    t0 = time.time()
    for vid in videos:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  (falta %s)" % vid)
            continue
        ser = pasada(SinBranch, v2, v1mod, ruta, FPS)
        porvid[vid] = {}
        for n in NOMS:
            m = AB.metricas(ser[n])
            dxc, dxg, ds, xs, dur = crudos_extra(ser[n])
            acumular(tot[n], m, dxc, dxg, ds, xs, dur)
            porvid[vid][n] = (m, dxc, dxg, ds)
        print("  ... %-18s %6d frames   %6.1f s acumulados"
              % (vid, len(ser["BASELINE"]), time.time() - t0))
    for n in NOMS:
        cerrar(tot[n])

    print("")
    print("  FIDELIDAD DEL ESPIA: %d frames comparados, %d discrepancias   %s"
          % (CHK["n"], CHK["mal"],
             "OK" if CHK["mal"] == 0 else "*** ABORTA"))
    if CHK["mal"]:
        rest()
        return 3
    print("  CAMINO aplicado en %d frames (sin candidatos en %d).  "
          "MONO sin admisibles en %d." % (USO["camino_ok"], USO["camino_vacio"],
                                          USO["mono_vacio"]))

    print("")
    print("  ABSOLUTOS SOBRE LOS %d VIDEOS AUTONOMOS" % len(videos))
    print(CAB)
    for n in NOMS:
        print(fila(n, tot[n]))

    print("")
    print("  DIFERENCIAS CONTRA EL BASELINE   (negativo = mejor, salvo disp)")
    print(CAB)
    b = tot["BASELINE"]
    for n in NOMS:
        print(fila_delta(n, tot[n], b))

    print("")
    print("  DIFERENCIAS CONTRA EL MEJOR ACTUAL (CAMINO+MONO)")
    print(CAB)
    c = tot["CAMINO+MONO"]
    print(fila_delta("V1 - C+M", tot["V1"], c))

    # -- desglose de saltos: cuanto es fila pura ---------------------------
    print("")
    print("  DE QUE SON LOS SALTOS")
    print("    s_gt   euclideo (lo que se venia midiendo)")
    print("    dx>24  solo columna: lo unico que el steer puede ver")
    print("    de esos, CONTIGUO = el salto ocurre entre dos frames seguidos")
    print("    con target, o sea que el comando salta de golpe. HUECO = hubo")
    print("    frames sin autoridad en el medio; el steer nunca vio el salto")
    print("    porque no habia con que compararlo.")
    print("")
    print("  %-13s %8s %8s %8s %9s %9s %9s"
          % ("version", "s_gt", "dx>24", "% fila", "dx contig", "dx hueco",
             "ds>27"))
    for n in NOMS:
        t = tot[n]
        fila_pct = (100.0 * (t["s_gt"] - t["dx_gt"]) / t["s_gt"]
                    if t["s_gt"] else 0.0)
        print("  %-13s %8d %8d %7.1f %% %9d %9d %9d"
              % (n, t["s_gt"], t["dx_gt"], fila_pct, t["dxc_gt"],
                 t["dxg_gt"], t["ds_gt"]))

    print("")
    print("  ANATOMIA DEL HUECO   (a %.2f fps: 1 frame = %.0f ms)"
          % (FPS, 1000.0 / FPS))
    print("  %-13s %8s %10s %9s %9s %9s"
          % ("version", "huecos", "sin_aut", "medio", "p90", "max"))
    for n in NOMS:
        t = tot[n]
        print("  %-13s %8d %10d %6.1f fr %6.1f fr %6.0f fr"
              % (n, t["huecos"], t["sin_aut"], t["h_med"], t["h_p90"],
                 t["h_max"]))
        print("  %-13s %8s %10s %6.0f ms %6.0f ms %6.0f ms"
              % ("", "", "", 1000.0 * t["h_med"] / FPS,
                 1000.0 * t["h_p90"] / FPS, 1000.0 * t["h_max"] / FPS))

    print("")
    print("  DE DONDE SALEN LOS SALTOS DE COLUMNA DE V1")
    print("    V1 promedia su target X sobre 5 frames. Un salto >24 px en el")
    print("    promedio exige que el POI crudo se corra >120 px en 5 frames,")
    print("    o sea CRUZAR LA IMAGEN. V1 tiene reglas que devuelven el borde")
    print("    literal: multi_bottom manda (0, H-1) o (W-1, H-1), y")
    print("    sale_izquierda / sale_derecha pegan el target contra el margen.")
    print("  %-13s %14s %12s %12s"
          % ("version", "% en el borde", "dx cont p99", "dx cont max"))
    for n in NOMS:
        t = tot[n]
        print("  %-13s %13.2f %% %12.1f %12.1f"
              % (n, t["borde"], t["dxc_p99"], t["dxc_max"]))

    # -- por video ---------------------------------------------------------
    if len(videos) > 1:
        print("")
        print("  POR VIDEO   disp %% | saltos>24 | dx>24 | dx contiguo | "
              "inversiones")
        print("  %-14s %-27s %-27s %-27s"
              % ("video", "BASELINE", "CAMINO+MONO", "V1"))
        for vid in videos:
            if vid not in porvid:
                continue
            cel = []
            for n in NOMS:
                m, dxc, dxg, _ds = porvid[vid][n]
                gc = int((np.asarray(dxc) > UMBRAL).sum()) if dxc else 0
                gg = int((np.asarray(dxg) > UMBRAL).sum()) if dxg else 0
                cel.append("%6.2f %5d %5d %5d %5d"
                           % (m["disp"], m["s_gt"], gc + gg, gc, m["inv"]))
            print("  %-14s %-27s %-27s %-27s"
                  % (vid.replace(".avi", ""), cel[0], cel[1], cel[2]))

    # -- controles ---------------------------------------------------------
    print("")
    print("  CONTROLES POSITIVOS OBLIGATORIOS")
    ctl = {n: [] for n in NOMS}
    okc = {n: True for n in NOMS}
    for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta) or not ex:
            continue
        ser = pasada(SinBranch, v2, v1mod, ruta, fps, d0, h0)
        for n in NOMS:
            m = AB.metricas(ser[n])
            st = [x for _t, x, _e in ser[n] if x is not None]
            ctl[n].append("%s %d/%d" % (cn, m["con"], ex))
            okc[n] &= (m["con"] >= ex)
            if cn == "lineal_positivo":
                ctl[n].append("smax %+.0f" % (max(st) if st else 0))
    for n in NOMS:
        print("  %-13s %-6s  %s" % (n, "PASA" if okc[n] else "FALLA",
                                    "   ".join(ctl[n])))

    rest()
    print("")
    print("  COMO LEER ESTO")
    print("    Replay OPEN-LOOP: mide PERCEPCION, no trayectoria. Nada de esto")
    print("    dice cual de las dos dobla mejor. Lo que si dice es que le")
    print("    cuesta a cada arquitectura sostener el target frame a frame.")
    print("=" * 116)
    return 0


if __name__ == "__main__":
    sys.exit(main())
