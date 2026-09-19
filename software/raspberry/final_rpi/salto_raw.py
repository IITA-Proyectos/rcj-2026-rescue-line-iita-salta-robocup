# -*- coding: utf-8 -*-
"""POR QUE EL PUNTO GEODESICO SALTA. Prueba H5. NO TOCA EL ROBOT.

La pregunta raiz
----------------
`atribuir_salto.py` dejo esto: cuando el spatial guard rechaza, el movimiento
real del punto geodesico es p50 **56,2 px** en 30 ms, y solo 4 de 166 rechazos
tenian el movimiento por debajo de 24 px. El guard no fabrica el salto: el salto
ya viene de la etapa 1.

Falta explicar por que un punto que deberia estar a 70 px de distancia geodesica
sobre la centerline se mueve 56 px de un frame al siguiente.

H5, declarada por Claude en el issue #138 ANTES de medir
--------------------------------------------------------
    "el salto de `raw` se produce cuando el largo total del esqueleto cruza los
     70 px, porque ahi `path_target` pasa de la rama normal al fallback
     `sorted(finite, key=|dist-LOOKAHEAD|)[:30]` (nuevo_code_v2.py:290-293) y el
     punto elegido cambia de regimen de golpe."

    Falsable: si los saltos grandes de `raw` no se concentran alrededor de
    `largo_esqueleto ~ 70`, H5 cae.

Como se mide
------------
Se corre V4 tal cual y, por frame, se recalcula el Dijkstra sobre el MISMO
esqueleto y desde el MISMO `start` que uso `path_target` -que V2 publica en
`res["start"]`-, usando las funciones de `nuevo_code_v2.py`. No se reimplementa
nada: se llama a `graph_from_skeleton` y `dijkstra` del propio modulo.

De ahi salen:

    largo_max     la mayor distancia geodesica alcanzable desde el start
    n_shell       cuantos nodos caen en la ventana [54, 88] que pide la rama
                  normal (lo = max(18, 70-16), hi = 70+18)
    fallback      n_shell == 0, o sea que se uso el `sorted(...)[:30]`
    n_hojas       nodos de grado 1: mide cuantas ramas tiene el esqueleto

Y se comparan las distribuciones en dos poblaciones: frames con salto de `raw`
mayor a 24 px, y el resto.

Uso
---
    python salto_raw.py
"""

import argparse
import csv
import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
FPS = 100.0 / 3.0
UMBRAL = 24.0


def cargar():
    ruta = os.path.join(AQUI, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        ruta = os.path.join(os.path.expanduser("~"), "Downloads", "nuevo_code_v4.py")
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def geometria(v2, sk, start):
    """largo_max, n_shell, fallback y n_hojas, con las funciones de V2."""
    if sk is None or start is None:
        return None
    pts, adj, deg = v2.graph_from_skeleton(sk)
    if len(pts) < 2:
        return None
    # el nodo del start, tal como lo devolvio path_target: (x, y)
    sx, sy = float(start[0]), float(start[1])
    mejor, md = None, 1e9
    for i, (y, x) in enumerate(pts):
        d = (x - sx) ** 2 + (y - sy) ** 2
        if d < md:
            mejor, md = i, d
    dist, _prev = v2.dijkstra(adj, mejor)
    fin = np.where(np.isfinite(dist))[0]
    if not len(fin):
        return None
    lo = max(18, v2.LOOKAHEAD - 16)
    hi = v2.LOOKAHEAD + 18
    shell = [i for i in fin
             if lo <= dist[i] <= hi and pts[i][0] <= pts[mejor][0] + 3]
    return dict(largo=float(dist[fin].max()), n_shell=len(shell),
                fallback=(len(shell) == 0), n_hojas=int((deg == 1).sum()),
                n_nodos=len(pts))


def correr(v4, v2, ruta):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = v4.NuevoCodeV4(FPS)
    # espia para quedarse con el `raw` antes de los caps
    per = tr.per
    orig = per.path_target
    caja = {}

    def espia(comp, mode):
        sk, res = orig(comp, mode)
        caja["raw"] = None if res is None else tuple(res["target"])
        caja["start"] = None if res is None else tuple(res["start"])
        caja["sk"] = sk
        return sk, res
    per.path_target = espia

    filas = []
    raw_ant = None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        caja.clear()
        g = v2.frame_pi(fr)
        r = tr.step(g)
        raw = caja.get("raw")
        gm = geometria(v2, caja.get("sk"), caja.get("start"))
        d = None
        if raw is not None and raw_ant is not None:
            d = math.hypot(raw[0] - raw_ant[0], raw[1] - raw_ant[1])
        filas.append(dict(d=d, gm=gm, mode=r.get("mode", ""),
                          state=r.get("state")))
        raw_ant = raw
    cap.release()
    return filas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a = ap.parse_args(argv)
    v4, _v3, v2 = cargar()

    print("")
    print("=" * 84)
    print(" POR QUE SALTA EL PUNTO GEODESICO   (H5: al cruzar LOOKAHEAD=%d)"
          % v2.LOOKAHEAD)
    print(" ventana de la rama normal: [%d, %d]"
          % (max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18))
    print("=" * 84)

    todo = []
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  falta %s" % vid)
            continue
        todo += correr(v4, v2, ruta)

    con = [f for f in todo if f["d"] is not None and f["gm"] is not None]
    salta = [f for f in con if f["d"] > UMBRAL]
    no = [f for f in con if f["d"] <= UMBRAL]
    print("")
    print("  %d frames con salto medible y geometria; %d saltan > %.0f px (%.1f %%)"
          % (len(con), len(salta), UMBRAL, 100.0 * len(salta) / max(len(con), 1)))

    print("")
    print("  %-22s %10s %10s %10s"
          % ("", "salta >24", "no salta", "razon"))
    for et, key in (("largo del esqueleto p50", "largo"),
                    ("nodos en la ventana p50", "n_shell"),
                    ("hojas del esqueleto p50", "n_hojas"),
                    ("nodos del esqueleto p50", "n_nodos")):
        a1 = np.median([f["gm"][key] for f in salta])
        a0 = np.median([f["gm"][key] for f in no])
        print("  %-22s %10.1f %10.1f %10.2f x"
              % (et, a1, a0, a1 / max(a0, 1e-9)))
    f1 = 100.0 * np.mean([f["gm"]["fallback"] for f in salta])
    f0 = 100.0 * np.mean([f["gm"]["fallback"] for f in no])
    print("  %-22s %9.1f %% %9.1f %% %10.2f x"
          % ("uso el FALLBACK", f1, f0, f1 / max(f0, 1e-9)))

    print("")
    print("  H5 DICE QUE LOS SALTOS SE CONCENTRAN CERCA DE largo = %d"
          % v2.LOOKAHEAD)
    print("      %-16s %8s %8s %10s" % ("largo", "n", "saltan", "tasa"))
    bordes = [0, 40, 55, 65, 75, 85, 100, 130, 10 ** 6]
    for lo, hi in zip(bordes, bordes[1:]):
        g = [f for f in con if lo <= f["gm"]["largo"] < hi]
        if len(g) < 20:
            continue
        s = sum(1 for f in g if f["d"] > UMBRAL)
        marca = "  <-- ventana" if lo <= v2.LOOKAHEAD < hi else ""
        print("      %6d-%-9s %8d %8d %9.1f %%%s"
              % (lo, ("%d" % hi) if hi < 10 ** 6 else "inf", len(g), s,
                 100.0 * s / len(g), marca))

    print("")
    print("  VEREDICTO SOBRE H5")
    cerca = [f for f in con if abs(f["gm"]["largo"] - v2.LOOKAHEAD) <= 15]
    lejos = [f for f in con if abs(f["gm"]["largo"] - v2.LOOKAHEAD) > 15]
    tc = 100.0 * np.mean([f["d"] > UMBRAL for f in cerca]) if cerca else 0
    tl = 100.0 * np.mean([f["d"] > UMBRAL for f in lejos]) if lejos else 0
    print("      tasa de salto con largo dentro de +-15 px de %d: %.1f %% (n=%d)"
          % (v2.LOOKAHEAD, tc, len(cerca)))
    print("      tasa de salto fuera de esa banda            : %.1f %% (n=%d)"
          % (tl, len(lejos)))
    if tc > 1.5 * tl:
        print("      -> H5 SE SOSTIENE: los saltos se concentran en la ventana.")
    else:
        print("      -> H5 CAE: no hay concentracion alrededor de LOOKAHEAD.")

    # el fallback como explicacion alternativa
    fb = [f for f in con if f["gm"]["fallback"]]
    nf = [f for f in con if not f["gm"]["fallback"]]
    print("")
    print("  ALTERNATIVA: es el FALLBACK, sin importar el largo?")
    if fb and nf:
        print("      tasa de salto CON fallback : %.1f %% (n=%d)"
              % (100.0 * np.mean([f["d"] > UMBRAL for f in fb]), len(fb)))
        print("      tasa de salto SIN fallback : %.1f %% (n=%d)"
              % (100.0 * np.mean([f["d"] > UMBRAL for f in nf]), len(nf)))

    # ramificacion como explicacion alternativa
    print("")
    print("  ALTERNATIVA: es la RAMIFICACION del esqueleto?")
    print("      %-14s %8s %8s %10s" % ("hojas", "n", "saltan", "tasa"))
    for lo, hi in ((0, 3), (3, 4), (4, 6), (6, 9), (9, 10 ** 6)):
        g = [f for f in con if lo <= f["gm"]["n_hojas"] < hi]
        if len(g) < 20:
            continue
        s = sum(1 for f in g if f["d"] > UMBRAL)
        print("      %5d-%-8s %8d %8d %9.1f %%"
              % (lo, ("%d" % hi) if hi < 10 ** 6 else "inf", len(g), s,
                 100.0 * s / len(g)))
    # --- ANALISIS ESTRATIFICADO -------------------------------------------
    # hojas y largo pueden estar correlacionados. Si la ramificacion explica el
    # salto POR SI SOLA, tiene que verse DENTRO de cada bin de largo.
    print("")
    print("  ESTRATIFICADO: la ramificacion predice el salto a largo FIJO?")
    print("      %-14s %-12s %7s %7s %8s" % ("largo", "hojas", "n", "saltan", "tasa"))
    bl = [(0, 65), (65, 100), (100, 140), (140, 10 ** 6)]
    bh = [(0, 4), (4, 6), (6, 10 ** 6)]
    for lo, hi in bl:
        gl = [f for f in con if lo <= f["gm"]["largo"] < hi]
        if len(gl) < 60:
            continue
        for hlo, hhi in bh:
            g = [f for f in gl if hlo <= f["gm"]["n_hojas"] < hhi]
            if len(g) < 25:
                continue
            sn = sum(1 for f in g if f["d"] > UMBRAL)
            print("      %5d-%-8s %5d-%-6s %7d %7d %7.1f %%"
                  % (lo, ("%d" % hi) if hi < 10 ** 6 else "inf",
                     hlo, ("%d" % hhi) if hhi < 10 ** 6 else "inf",
                     len(g), sn, 100.0 * sn / len(g)))

    out = os.path.join(AQUI, "salto_raw.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["salto_raw_px", "largo_esqueleto", "n_shell", "fallback",
                     "n_hojas", "n_nodos", "mode", "state"])
        for f in con:
            wr.writerow(["%.2f" % f["d"], "%.1f" % f["gm"]["largo"],
                         f["gm"]["n_shell"], int(f["gm"]["fallback"]),
                         f["gm"]["n_hojas"], f["gm"]["n_nodos"],
                         f["mode"], f["state"]])
    print("")
    print("  CSV: %s" % os.path.basename(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
