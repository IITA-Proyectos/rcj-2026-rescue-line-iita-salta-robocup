# -*- coding: utf-8 -*-
"""QUE ETAPA GENERA EL SALTO. Refuta o sostiene H1. NO TOCA EL ROBOT.

La pregunta
-----------
`clasificar_huecos.py` mostro que cuando un guard rechaza, el salto propuesto ya
venia grande: p50 53 px en spatial y 113 px en branch, con solo 2 de 209 por
debajo del limite de 24 px. O sea que el defecto no nace en el guard.

Nace en alguna de las cinco etapas. Este banco lo atribuye.

H1, declarada por Claude en el issue #138 ANTES de medir
--------------------------------------------------------
    "el salto nace en la etapa 1 (`raw`, el punto geodesico a LOOKAHEAD=70),
     porque un cambio de topologia del esqueleto mueve el punto 70 px de
     distancia geodesica de golpe."

    Falsable: si en esos eventos `raw` es estable y el salto aparece recien en
    `cap` o `low_proj`, H1 cae.

Como se mide
------------
Se usan los once `traza_*.csv` YA GENERADOS: tienen las cinco etapas por frame.
No hace falta re-correr nada, y cualquiera puede repetirlo con solo los CSV.

Para cada etapa e y cada frame t se calcula el salto temporal

    d_e(t) = | e(t) - e(t-1) |

y se compara la distribucion en dos poblaciones:

    EVENTO   frames que abren un hueco, o el frame previo a uno
    CONTROL  todos los demas frames con target en t y t-1

El CONTROL es imprescindible: `raw` puede saltar mucho de forma legitima cuando
la cinta se mueve rapido. Sin control, "raw salta 40 px en los eventos" no dice
nada.

Atribucion
----------
Un salto se atribuye a la PRIMERA etapa donde aparece. Si d_raw ya es grande, es
de la etapa 1. Si d_raw es chico y d_cap es grande, lo introdujo el cap, y asi.

Uso
---
    python atribuir_salto.py
"""

import argparse
import csv
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))

AUTONOMOS = ["hist", "lineal", "lineal70", "como_esta", "seguir", "rumbo",
             "a", "roi_auto", "con_planner", "con_planner2"]

ETAPAS = [("raw", "raw_x", "raw_y"),
          ("cap", "cap_x", "cap_y"),
          ("lowproj", "lowproj_x", "lowproj_y"),
          ("branch", "branch_x", "branch_y"),
          ("final", "final_x", "final_y")]

UMBRAL = 24.0     # el limite que declara SpatialTargetGuard a 33,3 fps


def punto(r, cx, cy):
    if r[cx] == "" or r[cy] == "":
        return None
    return (float(r[cx]), float(r[cy]))


def d(a, b):
    if a is None or b is None:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cargar(nom):
    ruta = os.path.join(AQUI, "traza_%s.csv" % nom)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def analizar(rows):
    """Devuelve por frame: los saltos de cada etapa y si es frame de evento."""
    out = []
    ant = None
    for r in rows:
        cur = {n: punto(r, cx, cy) for n, cx, cy in ETAPAS}
        saltos = {}
        if ant is not None:
            for n, _cx, _cy in ETAPAS:
                saltos[n] = d(cur[n], ant[n])
        out.append(dict(i=int(r["frame"]), p=cur, s=saltos,
                        sg=r["spatial_guard"], bg=r["branch_guard"],
                        state=r["state"], reason=r["reason"],
                        cap_via=r["cap_via"]))
        ant = cur
    # marcar frames de evento: el primero sin `final`, y el previo
    for k, f in enumerate(out):
        f["evento"] = False
    for k, f in enumerate(out):
        if f["p"]["final"] is None and k > 0 and out[k - 1]["p"]["final"] is not None:
            f["evento"] = True
            out[k - 1]["evento"] = True
    return out


def resumen(pop, nombre):
    print("  %s  (n=%d frames)" % (nombre, len(pop)))
    print("      %-10s %6s %8s %8s %8s %9s"
          % ("etapa", "n", "p50", "p90", "MAX", ">24 px"))
    for n, _cx, _cy in ETAPAS:
        v = np.array([f["s"].get(n) for f in pop
                      if f["s"].get(n) is not None], dtype=float)
        if v.size < 5:
            print("      %-10s %6d   sin datos" % (n, v.size))
            continue
        print("      %-10s %6d %8.1f %8.1f %8.1f %8.1f %%"
              % (n, v.size, np.median(v), np.percentile(v, 90), v.max(),
                 100.0 * (v > UMBRAL).mean()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a = ap.parse_args(argv)

    print("")
    print("=" * 84)
    print(" QUE ETAPA GENERA EL SALTO   (H1: nace en `raw`)")
    print(" Solo los 10 autonomos. Solo los CSV ya generados.")
    print("=" * 84)

    ev, ctl = [], []
    for nom in AUTONOMOS:
        rows = cargar(nom)
        if rows is None:
            print("  falta traza_%s.csv" % nom)
            continue
        fr = analizar(rows)
        ev += [f for f in fr if f["evento"]]
        ctl += [f for f in fr if not f["evento"]]

    print("")
    resumen(ctl, "CONTROL: frames que NO abren hueco")
    print("")
    resumen(ev, "EVENTO: frames que abren un hueco, y el previo")

    # --- atribucion: primera etapa donde el salto supera el umbral ---------
    print("")
    print("  ATRIBUCION: primera etapa donde el salto supera %.0f px" % UMBRAL)
    print("      %-12s %8s %8s" % ("etapa", "eventos", "%"))
    cuenta = {n: 0 for n, _a, _b in ETAPAS}
    cuenta["ninguna"] = 0
    usados = 0
    for f in ev:
        usados += 1
        prim = None
        for n, _cx, _cy in ETAPAS:
            s = f["s"].get(n)
            if s is not None and s > UMBRAL:
                prim = n
                break
        cuenta[prim or "ninguna"] += 1
    for k in [n for n, _a, _b in ETAPAS] + ["ninguna"]:
        print("      %-12s %8d %7.1f %%"
              % (k, cuenta[k], 100.0 * cuenta[k] / max(usados, 1)))

    # --- veredicto sobre H1 -----------------------------------------------
    vr_ev = np.array([f["s"]["raw"] for f in ev if f["s"].get("raw") is not None])
    vr_ct = np.array([f["s"]["raw"] for f in ctl if f["s"].get("raw") is not None])
    print("")
    print("  VEREDICTO SOBRE H1")
    print("      salto de `raw` en CONTROL: p50 %.1f  p90 %.1f  >24 px %.1f %%"
          % (np.median(vr_ct), np.percentile(vr_ct, 90),
             100.0 * (vr_ct > UMBRAL).mean()))
    print("      salto de `raw` en EVENTO : p50 %.1f  p90 %.1f  >24 px %.1f %%"
          % (np.median(vr_ev), np.percentile(vr_ev, 90),
             100.0 * (vr_ev > UMBRAL).mean()))
    razon = (100.0 * (vr_ev > UMBRAL).mean()) / max(1e-9, 100.0 * (vr_ct > UMBRAL).mean())
    print("      razon de tasas evento/control: %.1f x" % razon)
    if cuenta["raw"] >= 0.5 * usados:
        print("      -> H1 SE SOSTIENE: el salto ya esta en `raw` en la mayoria.")
    else:
        print("      -> H1 CAE o queda parcial: `raw` es la primera etapa que")
        print("         supera el umbral en solo %.1f %% de los eventos."
              % (100.0 * cuenta["raw"] / max(usados, 1)))

    # --- cuanto de los saltos grandes de raw sobreviven hasta final -------
    print("")
    print("  PROPAGACION: de los frames con salto de `raw` > %.0f px," % UMBRAL)
    print("  cuanto queda al final de la cadena?")
    pares = [(f["s"]["raw"], f["s"].get("final")) for f in ctl + ev
             if f["s"].get("raw") is not None and f["s"]["raw"] > UMBRAL]
    con_final = [(r, fi) for r, fi in pares if fi is not None]
    print("      %d frames con salto de raw > %.0f px" % (len(pares), UMBRAL))
    print("      de esos, %d (%.0f %%) llegan con un `final` medible"
          % (len(con_final), 100.0 * len(con_final) / max(len(pares), 1)))
    if con_final:
        rr = np.array([r for r, _f in con_final])
        ff = np.array([f for _r, f in con_final])
        print("      salto raw   p50 %.1f   salto final p50 %.1f   atenuacion %.0f %%"
              % (np.median(rr), np.median(ff),
                 100.0 * (1 - np.median(ff) / max(np.median(rr), 1e-9))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
