# -*- coding: utf-8 -*-
"""Reconstruye la tabla por video y los eventos de perdida SOLO desde los CSV.

Existe para que la auditoria no dependa de correr `trazar.py`: quien tenga los
once `traza_*.csv` puede reproducir cada numero publicado en
`TRAZAR_AUDITORIA.md` sin los videos y sin nuevo_code_*.py.

    python resumen_traza.py
"""

import csv
import glob
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))

# los ONCE videos. Los cuatro casos de control (`--casos`) generan CSV con otro
# nombre y NO entran aca: serian frames contados dos veces.
ONCE = ["hist", "lineal", "lineal70", "como_esta", "seguir", "rumbo", "a",
        "roi_auto", "con_planner", "con_planner2", "video_4"]

FPS = {v: (20.0 if v == "video_4" else 100.0 / 3.0) for v in ONCE}


def leer(nom):
    ruta = os.path.join(AQUI, "traza_%s.csv" % nom)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(v):
    return None if v in (None, "", "inf") else float(v)


def eventos(rows):
    """perdida -> reacquisicion. Definicion completa en TRAZAR_AUDITORIA.md."""
    ev = []
    ult = None
    ini = None
    for r in rows:
        x, y = f(r["final_x"]), f(r["final_y"])
        if x is None:
            if ini is None:
                ini = r
            continue
        if ini is not None and ult is not None:
            ux, uy = f(ult["final_x"]), f(ult["final_y"])
            us, ns = f(ult["steer_request_deg"]), f(r["steer_request_deg"])
            uh, nh = f(ult["heading_deg"]), f(r["heading_deg"])
            ev.append(dict(
                desde=int(ini["frame"]), hasta=int(r["frame"]) - 1,
                largo=int(r["frame"]) - int(ini["frame"]),
                ux=ux, uy=uy, nx=x, ny=y,
                salto=math.hypot(x - ux, y - uy),
                dsteer=None if (us is None or ns is None) else ns - us,
                dhead=None if (uh is None or nh is None) else nh - uh,
                est_antes=ult["state"], est_desp=r["state"],
                sg=r["spatial_guard"], bg=r["branch_guard"]))
            ini = None
        elif ini is not None:
            ini = None
        ult = r
    return ev


def main():
    print("")
    print("TABLA POR VIDEO  (reconstruida desde los CSV, sin correr trazar.py)")
    print("%-14s %5s %6s %6s | %5s %5s %5s %5s | %4s | %5s %5s"
          % ("video", "fps", "frames", "s/tgt", "cap2", "lowp", "brV3", "spV4",
             "FA", "ev", ">24"))
    tot = dict(n=0, sin=0, c2=0, lp=0, b3=0, s4=0, fa=0)
    todos_ev = []
    for v in ONCE:
        rows = leer(v)
        if rows is None:
            print("%-14s  FALTA traza_%s.csv" % (v, v))
            continue
        n = len(rows)
        sin = sum(1 for r in rows if r["final_x"] == "")
        c2 = sum(1 for r in rows if (f(r["movio_cap_px"]) or 0) > 0.01)
        lp = sum(1 for r in rows if (f(r["movio_lowproj_px"]) or 0) > 0.01)
        b3 = sum(1 for r in rows if (f(r["movio_branch_px"]) or 0) > 0.01)
        s4 = sum(1 for r in rows if (f(r["movio_spatial_px"]) or 0) > 0.01)
        fa = sum(1 for r in rows if r["cap_via"] == "FALLA_ABIERTA")
        ev = eventos(rows)
        todos_ev += ev
        g24 = sum(1 for e in ev if e["salto"] > 24.0)
        print("%-14s %5.1f %6d %6d | %5d %5d %5d %5d | %4d | %5d %5d"
              % (v, FPS[v], n, sin, c2, lp, b3, s4, fa, len(ev), g24))
        for k, val in (("n", n), ("sin", sin), ("c2", c2), ("lp", lp),
                       ("b3", b3), ("s4", s4), ("fa", fa)):
            tot[k] += val
    print("%-14s %5s %6d %6d | %5d %5d %5d %5d | %4d | %5d %5d"
          % ("TOTAL", "", tot["n"], tot["sin"], tot["c2"], tot["lp"],
             tot["b3"], tot["s4"], tot["fa"], len(todos_ev),
             sum(1 for e in todos_ev if e["salto"] > 24.0)))

    s = np.array([e["salto"] for e in todos_ev])
    ds = np.array([abs(e["dsteer"]) for e in todos_ev if e["dsteer"] is not None])
    lg = np.array([e["largo"] for e in todos_ev])
    print("")
    print("EVENTOS DE PERDIDA -> REACQUISICION: %d" % len(todos_ev))
    print("  salto px          p50 %.1f  p90 %.1f  MAX %.1f" %
          (np.median(s), np.percentile(s, 90), s.max()))
    print("  salto > 24 px     %d  (%.1f %%)" %
          ((s > 24).sum(), 100.0 * (s > 24).sum() / len(s)))
    print("  |d steer| grados  p50 %.0f  p90 %.0f  MAX %.0f" %
          (np.median(ds), np.percentile(ds, 90), ds.max()))
    print("  largo frames      p50 %.0f  p90 %.0f  MAX %d" %
          (np.median(lg), np.percentile(lg, 90), lg.max()))
    guards = {}
    for e in todos_ev:
        guards[e["sg"]] = guards.get(e["sg"], 0) + 1
    print("  spatial_guard en el frame de reenganche: " +
          "  ".join("%s %d" % kv for kv in sorted(guards.items(), key=lambda t: -t[1])))
    print("")
    print("LOS 10 MAYORES")
    print("  %-14s %6s %6s %11s %11s %8s %8s" %
          ("video", "frames", "salto", "ultima X", "nueva X", "d steer", "guard"))
    idx = {}
    for v in ONCE:
        rows = leer(v)
        if rows:
            for e in eventos(rows):
                idx[id(e)] = v
                todos_ev.append(e) if False else None
    pares = []
    for v in ONCE:
        rows = leer(v)
        if rows:
            for e in eventos(rows):
                pares.append((v, e))
    for v, e in sorted(pares, key=lambda t: -t[1]["salto"])[:10]:
        print("  %-14s %6d %6.1f %11s %11s %8s %8s"
              % (v, e["largo"], e["salto"],
                 "(%.0f,%.0f)" % (e["ux"], e["uy"]),
                 "(%.0f,%.0f)" % (e["nx"], e["ny"]),
                 "--" if e["dsteer"] is None else "%+.0f" % e["dsteer"], e["sg"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
