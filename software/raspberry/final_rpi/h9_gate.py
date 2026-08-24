# -*- coding: utf-8 -*-
"""H9-GATE / SIDE_EXIT. NO TOCA EL ROBOT. No modifica V2/V3/V4.

La hipotesis, acotada
---------------------
H9 quedo confirmada como DIAGNOSTICO: en los saltos grandes el verso previo
desaparece del conjunto `cands` 50,4 veces mas seguido que en los frames sanos.
Y H9 como POLITICA GLOBAL ya cayo: `verso_primero.py` (commit 8f96d3c) elige el
verso por continuidad de camino y degrada las cinco metricas sobre los 10 videos.

H9-GATE es mucho mas chica. Dice que en algunos SIDE EXIT el camino previo
TODAVIA existe en el skeleton, con distancia geodesica adecuada, y desaparece de
la shell **solo por el gate vertical** `y <= sy + 3`, porque la curva se acuesta
y sale por el borde inferior de la camara.

    Si el gate vertical es la unica razon por la que el verso previo
    desaparecio, recuperar esos candidatos REALES es una correccion causal.
    Si el verso previo tampoco tiene soporte al quitar el gate, no se sostiene
    nada: baseline.

No se sostiene el signo. No se sostiene el target. No se inventa ningun punto.

El trigger, exacto
------------------
En `path_target`, rama NEAR, antes de cap / low_proj / spatial:

  A. shell nominal EXACTAMENTE como V2:
         lo = max(18, LOOKAHEAD-16) = 54
         hi = LOOKAHEAD + 18        = 88
         lo <= dist <= hi   AND   y <= sy+3
  B. verso previo = signo de prev_heading (es la variable con la que H9 se
     diagnostico; si H9-GATE sobrevive se puede pasar a path/tangente).
  C. SIDE_EXIT_GATE solo si TODAS:
        1. existe verso previo
        2. la shell nominal tiene CERO candidatos de ese verso
        3. al quitar UNICAMENTE el gate vertical aparecen candidatos de ese
           verso, dentro de la MISMA banda geodesica [lo, hi]
        4. son pixeles reales del skeleton actual
  D. si se cumple: `cands` = esos candidatos recuperados, y adentro el MISMO
     score de V2, sin tocarlo.
  E. si al quitar el gate tampoco hay soporte: `SIDE_EXIT_NO_SUPPORT`, baseline.

Falsadores preregistrados
-------------------------
Cae si rompe `lineal_positivo` o `hist_exito`, si recupera la rama equivocada en
T o cruces, si dispara lejos de curvas laterales, si necesita target fantasma, o
si arregla `hist_falla` a costa de regresion global.

Uso
---
    python h9_gate.py --detalle hist.avi 1398 1417
    python h9_gate.py --controles
    python h9_gate.py
    python h9_gate.py --triggers        # audita cada disparo
"""

import argparse
import csv
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
v3 = v4.v3
v2 = v4.v3.v2

from ab_v2_v3_v4 import metricas, AUTONOMOS, CONTROLES, FPS, fila, CAB  # noqa: E402


class PercGate(v3.PercepcionV3):
    """PercepcionV3 con el trigger H9-GATE dentro de path_target.

    Copia literal de `nuevo_code_v2.py:237-314`. Lo unico agregado es el bloque
    marcado H9-GATE. El score no se toca.
    """

    def __init__(self, fps, activo=True):
        v3.PercepcionV3.__init__(self, fps)
        self.activo = bool(activo)
        self.reason_gate = ""
        self.stats = dict(gate=0, no_support=0, nominal=0, sin_verso=0)
        self.ultimo = None       # info del ultimo trigger, para auditar

    def path_target(self, comp, mode):
        if mode == "NEAR_BRANCH_LOCK":
            mode = "NEAR"
        self.reason_gate = ""
        sk = skeletonize(comp > 0)
        pts, adj, deg = v2.graph_from_skeleton(sk)
        if len(pts) < 2:
            return sk, None
        arr = np.array([(x, y) for y, x in pts], float)
        maxy = max(y for y, x in pts)

        if mode == "NEAR":
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
                start = min(cand, key=lambda i: (arr[i, 0] - self.prev_entry[0]) ** 2
                            + (arr[i, 1] - self.prev_entry[1]) ** 2)
        else:
            cand = [i for i, (y, x) in enumerate(pts) if y >= maxy - 3]
            ref = self.prev_target if self.prev_target is not None else self.prev_entry
            start = min(cand, key=lambda i: (arr[i, 0] - ref[0]) ** 2
                        + (arr[i, 1] - ref[1]) ** 2)

        sy, sx = pts[start]
        dist, prev = v2.dijkstra(adj, start)
        finite = np.where(np.isfinite(dist))[0]
        if not len(finite):
            return sk, None
        simple = "AHEAD" if mode.startswith("AHEAD") else mode

        if simple == "AHEAD":
            cands = [i for i in finite if pts[i][0] >= maxy - 4]
            if not cands:
                cands = [start]
            ref = self.prev_target if self.prev_target is not None else (sx, sy)
            target_idx = min(cands, key=lambda i: (pts[i][1] - ref[0]) ** 2
                             + (pts[i][0] - ref[1]) ** 2)
            path_idx = [start, target_idx] if target_idx != start else [start]
        else:
            lo = max(18, v2.LOOKAHEAD - 16)
            hi = v2.LOOKAHEAD + 18
            # A. shell NOMINAL, exactamente V2
            cands = [i for i in finite
                     if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]

            # ---------------- H9-GATE ------------------------------------
            if self.activo and self.prev_heading is not None:
                lado = -1 if self.prev_heading < 0 else 1

                def del_verso(lista):
                    return [i for i in lista if (pts[i][1] - sx) * lado > 0]

                n_prev_nominal = len(del_verso(cands))
                if n_prev_nominal == 0:
                    # C.3: la MISMA banda geodesica, SIN el gate vertical
                    sin_gate = [i for i in finite if lo <= dist[i] <= hi]
                    recup = del_verso(sin_gate)
                    if recup:
                        cands = recup                  # D
                        self.reason_gate = "SIDE_EXIT_GATE"
                        self.stats["gate"] += 1
                        self.ultimo = dict(
                            start=(float(sx), float(sy)), lado=lado,
                            n_recup=len(recup),
                            n_nominal=len(cands) if False else len(recup),
                            dy=[float(sy - pts[i][0]) for i in recup][:6])
                    else:
                        self.reason_gate = "SIDE_EXIT_NO_SUPPORT"   # E
                        self.stats["no_support"] += 1
                else:
                    self.stats["nominal"] += 1
            elif self.activo:
                self.stats["sin_verso"] += 1
            # -------------- fin H9-GATE ----------------------------------

            if not cands:
                cands = sorted(finite, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
                    :min(30, len(finite))]

            def score(i):
                y, x = pts[i]
                dy = sy - y
                heading = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
                s = 0.35 * abs(dist[i] - v2.LOOKAHEAD)
                s += 0.55 * v2.angdiff(heading, self.prev_heading)
                if self.prev_target is not None:
                    s += 0.10 * math.hypot(x - self.prev_target[0],
                                           y - self.prev_target[1])
                s += 0.30 * max(0, 8 - dy)
                return s

            target_idx = min(cands, key=score)
            path_idx = v2.reconstruct(prev, start, target_idx)
            if not path_idx:
                path_idx = [start, target_idx]

        ty, tx = pts[target_idx]
        heading = math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6)))
        path = [(float(pts[i][1]), float(pts[i][0])) for i in path_idx]
        return sk, dict(start=(float(sx), float(sy)),
                        target=(float(tx), float(ty)),
                        heading=heading, path=path)


def _nulo():
    class N(object):
        def step(self, proposed, skel):
            return proposed, "PASA"
    return N()


class BASE(v4.NuevoCodeV4):
    """La candidata congelada: V2 tal cual + SpatialTargetGuard, sin V3."""
    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.branch_guard = _nulo()


class GATE(v4.NuevoCodeV4):
    """Igual, con H9-GATE dentro de path_target."""
    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.per = PercGate(fps, activo=True)
        self.branch_guard = _nulo()


def corrida(cls, ruta, fps, desde=0, hasta=10 ** 9, detalle=False, marcar=None):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = cls(fps)
    per = tr.per
    orig = per.path_target
    caja = {}

    def espia(comp, mode):
        sk, res = orig(comp, mode)
        caja["raw"] = None if res is None else tuple(res["target"])
        return sk, res
    per.path_target = espia

    out = []
    trig = []
    i = 0
    raw_ant = None
    W, C = v2.W, v2.CENTER
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        caja.clear()
        g = v2.frame_pi(fr)
        ph = per.prev_heading
        r = tr.step(g)
        raw = caja.get("raw")
        d = (math.hypot(raw[0] - raw_ant[0], raw[1] - raw_ant[1])
             if (raw is not None and raw_ant is not None) else None)
        rg = getattr(per, "reason_gate", "")
        if i >= desde:
            t = r.get("target")
            s = (None if t is None
                 else float(np.clip(-90.0 * (t[0] - C) / (W / 2.0), -90, 90)))
            out.append((t, s, r.get("state")))
            if rg == "SIDE_EXIT_GATE":
                trig.append(dict(i=i, raw=raw, tgt=t, steer=s, ph=ph,
                                 state=r.get("state")))
            if detalle:
                print("    f%-5d %-9s raw %-12s salto %6s  steer %7s  ph %+7.1f  %s"
                      % (i, r.get("state"),
                         "--" if raw is None else "(%.0f,%.0f)" % raw,
                         "--" if d is None else "%.1f" % d,
                         "--" if s is None else "%+.1f" % s,
                         ph if ph is not None else 0.0, rg))
        raw_ant = raw
        i += 1
    cap.release()
    return out, trig, getattr(per, "stats", {})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--detalle", nargs=3, metavar=("VIDEO", "DESDE", "HASTA"))
    ap.add_argument("--controles", action="store_true")
    ap.add_argument("--triggers", action="store_true")
    a = ap.parse_args(argv)

    if a.detalle:
        vid, d, h = a.detalle[0], int(a.detalle[1]), int(a.detalle[2])
        ruta = os.path.join(AQUI, vid)
        fps = 20.0 if "video_4" in vid else FPS
        for et, cls in (("BASE  (V2 + spatial)", BASE),
                        ("GATE  (+ H9-GATE)", GATE)):
            print("")
            print("  %s   %s %d-%d" % (et, vid, d, h))
            _o, tg, st = corrida(cls, ruta, fps, d, h, detalle=True)
            if st:
                print("      stats: %s" % st)
        return 0

    print("")
    print("=" * 90)
    print(" H9-GATE / SIDE_EXIT   contra la candidata congelada V2+spatial")
    print("=" * 90)
    print("")
    print(" A) CONTROLES   (hist_exito y lineal_positivo son OBLIGATORIOS)")
    print(CAB)
    for nom, vid, fps, d, h, ex in CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        print("  --- %s%s" % (nom, ("   exige %d" % ex) if ex else ""))
        for et, cls in (("BASE", BASE), ("GATE", GATE)):
            ser, tg, _st = corrida(cls, ruta, fps, d, h)
            m = metricas(ser)
            mk = ""
            if ex:
                mk = "  PASA" if m["con"] >= ex else "  *** FALLA ***"
            if et == "GATE":
                mk += "   triggers %d" % len(tg)
            print(fila(et, m) + mk)
    if a.controles:
        return 0

    print("")
    print(" B) LOS 10 AUTONOMOS")
    print(CAB)
    tot = {}
    trig_all = []
    for et, cls in (("BASE", BASE), ("GATE", GATE)):
        t = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, s_max=0.0,
                 sp=[], su=[])
        st_tot = dict(gate=0, no_support=0, nominal=0, sin_verso=0)
        for vid in AUTONOMOS:
            ruta = os.path.join(AQUI, vid)
            if not os.path.exists(ruta):
                continue
            ser, tg, st = corrida(cls, ruta, FPS)
            m = metricas(ser)
            for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
                t[k] += m[k]
            t["s_max"] = max(t["s_max"], m["s_max"])
            t["sp"].append(m["s_p90"])
            t["su"].append(m["suav"])
            for k in st_tot:
                st_tot[k] += st.get(k, 0)
            if et == "GATE" and tg:
                for x in tg:
                    x["video"] = vid.replace(".avi", "")
                trig_all += tg
        t["disp"] = 100.0 * t["con"] / max(t["n"], 1)
        t["s_p90"] = float(np.mean(t["sp"]))
        t["suav"] = float(np.mean(t["su"]))
        tot[et] = t
        print(fila(et, t) + ("   %s" % st_tot if et == "GATE" else ""))

    b, gt = tot["BASE"], tot["GATE"]
    print("")
    print(" DIFERENCIA GATE - BASE")
    for k, et in (("disp", "disponibilidad %"), ("sin_aut", "frames sin autoridad"),
                  ("huecos", "huecos"), ("s_gt", "saltos >24 px"),
                  ("inv", "inversiones")):
        print("      %-24s BASE %8.2f   GATE %8.2f   %+8.2f"
              % (et, b[k], gt[k], gt[k] - b[k]))
    print("")
    print("      triggers SIDE_EXIT_GATE: %d" % len(trig_all))
    if trig_all:
        porv = {}
        for x in trig_all:
            porv[x["video"]] = porv.get(x["video"], 0) + 1
        print("      por video: " + "  ".join("%s %d" % kv for kv in
                                              sorted(porv.items(), key=lambda t: -t[1])))
        out = os.path.join(AQUI, "h9_gate_triggers.csv")
        with open(out, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["video", "frame", "state", "prev_heading",
                         "raw_x", "raw_y", "target_x", "target_y", "steer"])
            for x in trig_all:
                wr.writerow([x["video"], x["i"], x["state"],
                             "" if x["ph"] is None else "%.2f" % x["ph"],
                             "" if x["raw"] is None else "%.1f" % x["raw"][0],
                             "" if x["raw"] is None else "%.1f" % x["raw"][1],
                             "" if x["tgt"] is None else "%.1f" % x["tgt"][0],
                             "" if x["tgt"] is None else "%.1f" % x["tgt"][1],
                             "" if x["steer"] is None else "%.1f" % x["steer"]])
        print("      CSV: %s" % os.path.basename(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
