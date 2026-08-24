# -*- coding: utf-8 -*-
"""H9: el VERSO lo decide la disponibilidad de la shell. NO TOCA EL ROBOT.

De donde sale
-------------
ChatGPT, issue #138, tras ver el video: en `hist` f1399->f1400 el `raw` salta de
(26,116) a (157,116) -de un extremo al otro de la MISMA componente horizontal- y
la causa no es el guard ni la seleccion de componente. Es que la shell geodesica
[54, 88] con el filtro vertical `pts[i][0] <= sy+3` se queda con **0 candidatos
de un lado y 17 del otro**, porque el alcance de ese lado cae de 74,8 a 59,0 px.

Cuando el lado previo desaparece del conjunto candidato, `prev_heading` no puede
salvarlo: el score solo puntua lo que esta en `cands`.

Por que esto importa mas que todo lo anterior
---------------------------------------------
Explica un resultado propio que habia quedado suelto: **H8 salio plana**. Subir
el peso de continuidad de 0,10 a 2,0 no cambio los saltos (245-251) y ahora se
entiende por que: **un peso no puede rescatar un candidato que no esta en el
conjunto**. Las dos cosas encajan.

H9, enunciada para ser falsable
-------------------------------
    En los frames donde el `raw` pega un salto grande, el VERSO previo -el lado
    del skeleton hacia donde se venia avanzando- desapareció del conjunto de
    candidatos de la shell.

    Falsable: si en los saltos el verso previo SEGUIA teniendo candidatos, H9
    cae y el salto lo decide el score, no la disponibilidad.

Como se mide
------------
Se reproduce la rama NEAR de `nuevo_code_v2.py:283-298` con las funciones del
propio modulo, y por frame se cuenta cuantos candidatos de la shell caen de cada
lado del `start`. El verso previo se define por el signo de `prev_heading`, que
es exactamente lo que el score usa para mantener el rumbo.

Uso
---
    python verso.py --frames hist.avi 1396 1406
    python verso.py            # los 10 autonomos
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
v2 = v4.v3.v2

AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
FPS = 100.0 / 3.0
UMBRAL = 24.0


def shell_por_lado(comp, prev_entry, prev_heading):
    """Reproduce la rama NEAR y devuelve cuantos candidatos hay de cada lado.

    Copia de `nuevo_code_v2.py:245-285`, usando las funciones del modulo. Lo
    unico que se agrega es separar `cands` por el signo del heading.
    """
    sk = skeletonize(comp > 0)
    pts, adj, deg = v2.graph_from_skeleton(sk)
    if len(pts) < 2:
        return None
    arr = np.array([(x, y) for y, x in pts], float)
    maxy = max(y for y, x in pts)
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
        start = min(cand, key=lambda i: (arr[i, 0] - prev_entry[0]) ** 2
                    + (arr[i, 1] - prev_entry[1]) ** 2)
    sy, sx = pts[start]
    dist, _prev = v2.dijkstra(adj, start)
    finite = np.where(np.isfinite(dist))[0]
    if not len(finite):
        return None
    lo = max(18, v2.LOOKAHEAD - 16)
    hi = v2.LOOKAHEAD + 18
    cands = [i for i in finite if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
    usa_fallback = (len(cands) == 0)
    if not cands:
        cands = sorted(finite, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
            :min(30, len(finite))]

    izq = der = 0
    for i in cands:
        y, x = pts[i]
        dy = sy - y
        h = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
        if h < 0:
            izq += 1
        else:
            der += 1
    # alcance geodesico maximo de cada lado, sobre TODO el grafo
    alc_i = alc_d = 0.0
    for i in finite:
        y, x = pts[i]
        if x < sx:
            alc_i = max(alc_i, float(dist[i]))
        elif x > sx:
            alc_d = max(alc_d, float(dist[i]))
    lado_prev = -1 if (prev_heading is not None and prev_heading < 0) else 1
    n_prev = izq if lado_prev < 0 else der
    return dict(start=(float(sx), float(sy)), izq=izq, der=der,
                alc_izq=alc_i, alc_der=alc_d, fallback=usa_fallback,
                lado_prev=lado_prev, n_lado_prev=n_prev, n_cands=len(cands))


def correr(ruta, fps, desde=0, hasta=10 ** 9, detalle=False):
    vidnom = os.path.basename(ruta)
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = v4.NuevoCodeV4(fps)
    per = tr.per
    orig = per.path_target
    caja = {}

    def espia(comp, mode):
        sk, res = orig(comp, mode)
        caja["raw"] = None if res is None else tuple(res["target"])
        caja["mode"] = mode
        caja["comp"] = comp
        return sk, res
    per.path_target = espia

    filas = []
    raw_ant = None
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        caja.clear()
        g = v2.frame_pi(fr)
        ph = per.prev_heading
        pe = per.prev_entry
        r = tr.step(g)
        raw = caja.get("raw")
        d = None
        if raw is not None and raw_ant is not None:
            d = math.hypot(raw[0] - raw_ant[0], raw[1] - raw_ant[1])
        sh = None
        if caja.get("comp") is not None and caja.get("mode") in ("NEAR", "NEAR_BRANCH_LOCK"):
            try:
                sh = shell_por_lado(caja["comp"], pe, ph)
            except Exception:
                sh = None
        if i >= desde:
            filas.append(dict(i=i, d=d, sh=sh, raw=raw, ph=ph, vid=vidnom,
                              state=r.get("state"), mode=caja.get("mode", "")))
            if detalle and sh is not None:
                print("    f%-5d %-9s raw %-12s salto %6s | prev_head %+7.1f "
                      "lado_prev %+d | cands izq %3d der %3d  del lado prev %3d"
                      "  | alcance izq %5.1f der %5.1f %s"
                      % (i, r.get("state"),
                         "--" if raw is None else "(%.0f,%.0f)" % raw,
                         "--" if d is None else "%.1f" % d,
                         ph if ph is not None else 0.0, sh["lado_prev"],
                         sh["izq"], sh["der"], sh["n_lado_prev"],
                         sh["alc_izq"], sh["alc_der"],
                         "FALLBACK" if sh["fallback"] else ""))
        raw_ant = raw
        i += 1
    cap.release()
    return filas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frames", nargs=3, metavar=("VIDEO", "DESDE", "HASTA"),
                    help="detalle frame a frame de un tramo")
    a = ap.parse_args(argv)

    if a.frames:
        vid, d, h = a.frames[0], int(a.frames[1]), int(a.frames[2])
        ruta = os.path.join(AQUI, vid)
        fps = 20.0 if "video_4" in vid else FPS
        print("")
        print("  DETALLE %s %d-%d" % (vid, d, h))
        correr(ruta, fps, d, h, detalle=True)
        return 0

    print("")
    print("=" * 86)
    print(" H9: el verso previo desaparece del conjunto candidato?")
    print(" shell [%d, %d] con el filtro vertical de nuevo_code_v2.py:285"
          % (max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18))
    print("=" * 86)
    todo = []
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        todo += correr(ruta, FPS)
    con = [f for f in todo if f["d"] is not None and f["sh"] is not None]
    salta = [f for f in con if f["d"] > UMBRAL]
    no = [f for f in con if f["d"] <= UMBRAL]
    print("")
    print("  %d frames NEAR con shell medible; %d saltan > %.0f px"
          % (len(con), len(salta), UMBRAL))

    def tasa(g, key):
        return 100.0 * np.mean([key(f) for f in g]) if g else float("nan")

    print("")
    print("  %-42s %10s %10s %8s" % ("", "salta >24", "no salta", "razon"))
    pruebas = [
        ("el verso previo se quedo SIN candidatos", lambda f: f["sh"]["n_lado_prev"] == 0),
        ("uno de los dos lados quedo sin candidatos",
         lambda f: f["sh"]["izq"] == 0 or f["sh"]["der"] == 0),
        ("se uso el FALLBACK", lambda f: f["sh"]["fallback"]),
        ("los dos lados tienen candidatos",
         lambda f: f["sh"]["izq"] > 0 and f["sh"]["der"] > 0),
    ]
    for et, fn in pruebas:
        t1, t0 = tasa(salta, fn), tasa(no, fn)
        print("  %-42s %9.1f %% %9.1f %% %7.2f x"
              % (et, t1, t0, t1 / max(t0, 1e-9)))

    # --- EL FALSADOR: el lado que desaparece, REAPARECE? -----------------
    # Si desaparece porque la cinta se fue de verdad, preservar el verso seria
    # apuntar a un lado que ya no existe: el mismo mecanismo que mato la
    # variante "sostiene" (26,2 % de targets fuera de la centerline).
    print("")
    print("  FALSADOR DE H9 OPERATIVA: el lado desaparecido reaparece?")
    porvid = {}
    for f in todo:
        porvid.setdefault(f.get("vid", "?"), []).append(f)
    reap = {k: 0 for k in (1, 2, 3, 5, 8, 12, 20)}
    casos = 0
    nunca = 0
    for serie in porvid.values():
        for k, f in enumerate(serie):
            if f["sh"] is None or f["sh"]["n_lado_prev"] != 0:
                continue
            casos += 1
            lado = f["sh"]["lado_prev"]
            vuelve = None
            for j in range(k + 1, min(k + 21, len(serie))):
                sh = serie[j]["sh"]
                if sh is None:
                    continue
                n = sh["izq"] if lado < 0 else sh["der"]
                if n > 0:
                    vuelve = j - k
                    break
            if vuelve is None:
                nunca += 1
            else:
                for u in reap:
                    if vuelve <= u:
                        reap[u] += 1
    print("      %d frames donde el verso previo se quedo sin candidatos" % casos)
    if casos:
        for u in sorted(reap):
            print("        vuelve a tener candidatos en <= %2d frames: %4d (%.1f %%)"
                  % (u, reap[u], 100.0 * reap[u] / casos))
        print("        no vuelve en 20 frames:                    %4d (%.1f %%)"
              % (nunca, 100.0 * nunca / casos))
        print("")
        if 100.0 * reap[5] / casos >= 60.0:
            print("      -> El lado REAPARECE rapido en la mayoria: el flip era")
            print("         prematuro y preservar el verso tiene sentido. H9 operativa")
            print("         se sostiene.")
        elif 100.0 * nunca / casos >= 50.0:
            print("      -> El lado NO vuelve: la cinta se fue de verdad y el flip era")
            print("         la respuesta correcta. H9 describe el mecanismo pero NO")
            print("         justifica preservar el verso.")
        else:
            print("      -> Resultado mixto: no decide por si solo.")

    print("")
    print("  VEREDICTO SOBRE H9")
    t1 = tasa(salta, lambda f: f["sh"]["n_lado_prev"] == 0)
    t0 = tasa(no, lambda f: f["sh"]["n_lado_prev"] == 0)
    if t1 > 2.0 * t0:
        print("      SE SOSTIENE: en los saltos el verso previo desaparece del")
        print("      conjunto candidato %.1f veces mas seguido." % (t1 / max(t0, 1e-9)))
        print("      Y explica por que H8 salio plana: un peso no puede rescatar")
        print("      un candidato que no esta en `cands`.")
    else:
        print("      CAE: el verso previo sigue teniendo candidatos en los saltos")
        print("      (%.1f %% contra %.1f %% del control). El salto lo decide el"
              % (t1, t0))
        print("      score, no la disponibilidad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
