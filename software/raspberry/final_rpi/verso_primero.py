# -*- coding: utf-8 -*-
"""H9 OPERATIVA: elegir el VERSO antes que el LOOKAHEAD. NO TOCA EL ROBOT.

De donde sale
-------------
H9 quedo confirmada: en los saltos grandes el verso previo desaparece del
conjunto candidato de la shell 50,4 veces mas seguido que en los frames sanos
(30,3 % contra 0,6 %, 10 videos, 10.885 frames NEAR). Y explica por que H8 salio
plana: un peso no puede rescatar un candidato que no esta en `cands`.

El falsador que yo habia propuesto -"el lado desaparecido reaparece?"- lo RETIRO.
ChatGPT senalo un confundidor estructural que no habia visto: los frames
posteriores son la trayectoria que el robot ejecuto OBEDECIENDO al controlador
viejo. Si el flip mando al otro lado, la pose futura cambio y con ella que parte
de la cinta reentra al FOV. Usar ese futuro como veredicto es circular. Es la
regla 7 del HANDOFF -el replay es lazo abierto- aplicada a mi propio test.

Lo que se prueba aca, que si es offline y no circular
-----------------------------------------------------
Elegir el verso con evidencia del frame ACTUAL mas historia ANTERIOR al flip, y
nada mas:

  1. en t-1 se guarda el path orientado start->target y su tangente;
  2. en t, desde el nuevo start, se enumeran las dos direcciones topologicas
     de la misma componente ANTES de aplicar la shell de LOOKAHEAD;
  3. cada direccion se compara con el path de t-1 por su primer tramo
     (15 a 30 px geodesicos): continuidad angular y espacial DEL TRAMO, no del
     target;
  4. se elige el verso por esa continuidad y recien despues se pone el
     LOOKAHEAD dentro de ese verso;
  5. si el verso elegido no tiene soporte visible suficiente, se devuelve
     evidencia insuficiente. NO se sostiene un target fantasma: eso es lo que
     mato a la variante "sostiene" (26,2 % fuera de la centerline).

El punto 5 es el que separa esto de un hold ciego.

Falsador de H9 operativa
------------------------
Si preservar el verso por continuidad de camino rompe `lineal_positivo`, o
necesita sostener un verso sin soporte visible durante varios frames, entonces
H9 describe el mecanismo pero no es una politica segura.

Uso
---
    python verso_primero.py --detalle hist.avi 1396 1418
    python verso_primero.py --controles
    python verso_primero.py
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
v3 = v4.v3
v2 = v4.v3.v2

from ab_v2_v3_v4 import metricas, AUTONOMOS, CONTROLES, FPS, fila, CAB  # noqa: E402

TRAMO_LO, TRAMO_HI = 15.0, 30.0     # el primer tramo que define el verso
MIN_NODOS_VERSO = 3                 # soporte visible minimo para aceptar un verso
MAX_ANG = 60.0                      # cambio de tangente que ya no es continuidad


class PercVerso(v3.PercepcionV3):
    """PercepcionV3 con el ORDEN invertido dentro de path_target.

    Copia de `nuevo_code_v2.py:237-314`. Lo unico que cambia es que, en la rama
    NEAR, se elige primero el verso por continuidad de camino y despues se pone
    el LOOKAHEAD dentro de ese verso.
    """

    def __init__(self, fps):
        v3.PercepcionV3.__init__(self, fps)
        self.prev_tramo = None       # punto representativo del primer tramo
        self.prev_tan = None         # tangente del primer tramo, en grados
        self.motivo = ""

    # -- el primer tramo de cada verso --------------------------------------
    def _tramos(self, pts, dist, finite, sx, sy):
        """Devuelve {lado: (centroide, tangente, n_nodos)} para lado -1 y +1."""
        out = {}
        for lado in (-1, 1):
            sel = [i for i in finite
                   if TRAMO_LO <= dist[i] <= TRAMO_HI
                   and (pts[i][1] - sx) * lado > 0]
            if len(sel) < MIN_NODOS_VERSO:
                out[lado] = None
                continue
            xs = np.array([pts[i][1] for i in sel], float)
            ys = np.array([pts[i][0] for i in sel], float)
            cx, cy = float(xs.mean()), float(ys.mean())
            tan = math.degrees(math.atan2(cx - sx, max(sy - cy, 1e-6)))
            out[lado] = (cx, cy, tan, len(sel))
        return out

    def path_target(self, comp, mode):
        if mode == "NEAR_BRANCH_LOCK":
            mode = "NEAR"
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
            self.motivo = "ahead"
        else:
            # ---------- PASO 1: elegir el VERSO, antes de la shell ----------
            tr = self._tramos(pts, dist, finite, sx, sy)
            viables = [l for l in (-1, 1) if tr[l] is not None]
            lado = None
            if not viables:
                self.motivo = "sin_verso"
                return sk, None                       # evidencia insuficiente
            if len(viables) == 1:
                lado = viables[0]
                self.motivo = "verso_unico"
            elif self.prev_tan is None:
                # sin historia: el que mas se acerca a ir hacia adelante
                lado = min(viables, key=lambda l: abs(tr[l][2]))
                self.motivo = "verso_sin_historia"
            else:
                # continuidad de CAMINO: tangente + posicion del primer tramo
                def costo(l):
                    cx, cy, tan, _n = tr[l]
                    d_ang = v2.angdiff(tan, self.prev_tan)
                    d_pos = (math.hypot(cx - self.prev_tramo[0],
                                        cy - self.prev_tramo[1])
                             if self.prev_tramo is not None else 0.0)
                    return d_ang + 0.8 * d_pos
                lado = min(viables, key=costo)
                # si ni el mejor se parece al camino previo, no hay continuidad
                cx, cy, tan, _n = tr[lado]
                self.motivo = ("verso_continuo"
                               if v2.angdiff(tan, self.prev_tan) <= MAX_ANG
                               else "verso_roto")

            # ---------- PASO 2: el LOOKAHEAD, DENTRO de ese verso -----------
            lo = max(18, v2.LOOKAHEAD - 16)
            hi = v2.LOOKAHEAD + 18
            cands = [i for i in finite
                     if lo <= dist[i] <= hi and pts[i][0] <= sy + 3
                     and (pts[i][1] - sx) * lado >= 0]
            if not cands:
                # el verso elegido no llega al lookahead: se acorta, NO se
                # cambia de lado ni se inventa un punto
                cands = [i for i in finite
                         if dist[i] >= TRAMO_LO and (pts[i][1] - sx) * lado >= 0]
                if not cands:
                    self.motivo += "|sin_soporte"
                    return sk, None
                cands = sorted(cands, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[:30]
                self.motivo += "|acortado"

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
            # memoria del camino, para el frame siguiente
            t = tr[lado]
            self.prev_tramo = (t[0], t[1])
            self.prev_tan = t[2]

        ty, tx = pts[target_idx]
        heading = math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6)))
        path = [(float(pts[i][1]), float(pts[i][0])) for i in path_idx]
        return sk, dict(start=(float(sx), float(sy)),
                        target=(float(tx), float(ty)),
                        heading=heading, path=path)


class V1RC(v4.NuevoCodeV4):
    """La candidata con verso-primero: V2 con el orden invertido + spatial."""

    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"

    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.per = PercVerso(fps)
        self.branch_guard = V1RC._Nulo()


class BASE(v4.NuevoCodeV4):
    """La candidata actual: V2 tal cual + spatial."""

    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"

    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.branch_guard = BASE._Nulo()


def corrida(cls, ruta, fps, desde=0, hasta=10 ** 9, detalle=False):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = cls(fps)
    out = []
    i = 0
    W, C = v2.W, v2.CENTER
    raw_ant = None
    per = tr.per
    orig = per.path_target
    caja = {}

    def espia(comp, mode):
        sk, res = orig(comp, mode)
        caja["raw"] = None if res is None else tuple(res["target"])
        return sk, res
    per.path_target = espia

    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        caja.clear()
        g = v2.frame_pi(fr)
        r = tr.step(g)
        raw = caja.get("raw")
        d = (math.hypot(raw[0] - raw_ant[0], raw[1] - raw_ant[1])
             if (raw is not None and raw_ant is not None) else None)
        if i >= desde:
            t = r.get("target")
            s = (None if t is None
                 else float(np.clip(-90.0 * (t[0] - C) / (W / 2.0), -90, 90)))
            out.append((t, s, r.get("state")))
            if detalle:
                print("    f%-5d %-9s raw %-12s salto %6s  steer %7s  %s"
                      % (i, r.get("state"),
                         "--" if raw is None else "(%.0f,%.0f)" % raw,
                         "--" if d is None else "%.1f" % d,
                         "--" if s is None else "%+.1f" % s,
                         getattr(per, "motivo", "")))
        raw_ant = raw
        i += 1
    cap.release()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--detalle", nargs=3, metavar=("VIDEO", "DESDE", "HASTA"))
    ap.add_argument("--controles", action="store_true")
    a = ap.parse_args(argv)

    if a.detalle:
        vid, d, h = a.detalle[0], int(a.detalle[1]), int(a.detalle[2])
        ruta = os.path.join(AQUI, vid)
        fps = 20.0 if "video_4" in vid else FPS
        for et, cls in (("BASE  (V2 tal cual + spatial)", BASE),
                        ("VERSO (verso primero + spatial)", V1RC)):
            print("")
            print("  %s   %s %d-%d" % (et, vid, d, h))
            corrida(cls, ruta, fps, d, h, detalle=True)
        return 0

    print("")
    print("=" * 88)
    print(" H9 OPERATIVA: elegir el verso antes que el lookahead")
    print(" BASE = la candidata actual   VERSO = con el orden invertido")
    print("=" * 88)
    print("")
    print(" CONTROLES   (hist_exito y lineal_positivo son OBLIGATORIOS)")
    print(CAB)
    for nom, vid, fps, d, h, ex in CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        print("  --- %s%s" % (nom, ("   exige %d" % ex) if ex else ""))
        for et, cls in (("BASE", BASE), ("VRSO", V1RC)):
            m = metricas(corrida(cls, ruta, fps, d, h))
            mark = ""
            if ex:
                mark = "  PASA" if m["con"] >= ex else "  *** FALLA ***"
            print(fila(et, m) + mark)
    if a.controles:
        return 0

    print("")
    print(" LOS 10 AUTONOMOS")
    print(CAB)
    for et, cls in (("BASE", BASE), ("VRSO", V1RC)):
        t = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, s_max=0.0,
                 sp=[], su=[])
        for vid in AUTONOMOS:
            ruta = os.path.join(AQUI, vid)
            if not os.path.exists(ruta):
                continue
            m = metricas(corrida(cls, ruta, FPS))
            for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
                t[k] += m[k]
            t["s_max"] = max(t["s_max"], m["s_max"])
            t["sp"].append(m["s_p90"])
            t["su"].append(m["suav"])
        t["disp"] = 100.0 * t["con"] / max(t["n"], 1)
        t["s_p90"] = float(np.mean(t["sp"]))
        t["suav"] = float(np.mean(t["su"]))
        print(fila(et, t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
