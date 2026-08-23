# -*- coding: utf-8 -*-
"""
leyes.py - Cuatro formas de mirar la misma cinta, sobre los mismos frames.

POR QUE EXISTE ESTE ARCHIVO
---------------------------
El codigo del 22-ago hace esto, y esta todo dicho en una linea:

    black_mask -> mean(x_black), mean(y_black) -> atan2 -> UN angle

Todos los pixeles negros del ROI se promedian en un punto y de ahi sale un solo
numero. Ese numero MEZCLA dos cosas que no son lo mismo:

    donde estoy respecto de la cinta      (error lateral)
    hacia donde sigue la cinta            (error de rumbo)

Y se puede demostrar que las mezcla, con un frame concreto. En hist.avi #1365 la
cinta pasa por DEBAJO del robot a 31 px a la izquierda y se va a la DERECHA
adelante. El promedio global da -33,9 grados; el robot gira a la derecha y nunca
se recentra, porque para ponerse sobre la cinta tendria que ir a la izquierda y
para seguirla tendria que girar a la derecha. Un solo numero no puede decir las
dos cosas.

Medido de forma independiente: el error de rumbo vale ~24 px de forma
PERMANENTE, pivotee el robot o no, y el control nunca lo corrige porque nunca lo
mide.

LAS CUATRO LEYES QUE SE COMPARAN
--------------------------------
  actual      el atan2 global del 22-ago. La referencia.
  estados     el mismo atan2, con la capa HIGH/MEDIUM/LOW/SIN_CERCA/PERDIDA
              decidiendo cuanta autoridad tiene.
  near_mid    elige LA componente que representa la trayectoria -con memoria del
              frame anterior- y saca DOS errores separados: lateral y rumbo.
              NO los colapsa en un gain: los reporta por separado.
  lookahead   sobre esa misma componente elige un PUNTO OBJETIVO segun el estado
              de confianza, y calcula hacia donde habria que ir para alcanzarlo.

REGLA DE ESTE ARCHIVO: no se tunean ganancias para ganar una metrica. Primero hay
que mostrar si `near+mid` produce una senal geometrica mas estable que el atan2
global. Si no la produce, no hay nada que tunear.

USO
---
    python3 leyes.py video_4.avi --tag manual --fps 20
    python3 leyes.py hist.avi --desde 1354 --hasta 1490 --tag falla
    python3 leyes.py --todos
"""
import argparse
import csv
import math
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from shadow import (frame_de_la_pi, percibir, confianza, angulo_atan2,  # noqa: E402
                    Candidato, ruedas, LO, HI, W, H, CENTRO, FPS, AREA_LOST,
                    NEAR, MID, FAR, PIX_MIN)


def centroide_banda(mm, a, b):
    """(x, y) del centroide de la componente dentro de la banda de filas [a,b]."""
    sub = mm[a:b + 1, :]
    ys, xs = np.nonzero(sub)
    if len(xs) < PIX_MIN:
        return None, None
    return float(xs.mean()), float(ys.mean()) + a


class Trayectoria(object):
    """Sigue UNA componente entre frames y saca lateral y rumbo por separado.

    LA SELECCION DE COMPONENTE ES LO QUE CAMBIA respecto del codigo actual:
      1. la que toca la fila 119 -la unica que puede estar debajo del robot-
      2. si no hay ninguna, la mas cercana a donde estaba la seguida el frame
         anterior. Esa memoria es lo que evita que una mancha cualquiera se
         convierta en "la linea" de un frame para el otro.

    El codigo del 22-ago no elige: promedia TODO el negro del ROI, asi que el
    zocalo del salon pesa igual que la cinta.
    """

    def __init__(self, salto_max=45.0):
        self.salto_max = salto_max      # px que puede saltar el punto seguido
        self.ult_x = None               # ultimo x seguido
        self.ult_lat = None             # ultimo error lateral confiable
        self.ult_head = None            # ultimo rumbo confiable

    def paso(self, g):
        m = cv2.inRange(g, LO, HI)
        m[:60, :] = 0
        n, et, est, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
        cand, k0 = [], 0
        for k in range(1, n):
            if est[k, cv2.CC_STAT_AREA] < AREA_LOST:
                continue
            toca = bool(np.any(et[119, :] == k))
            ys, xs = np.nonzero(et == k)
            cand.append((k, toca, float(xs.mean()), float(est[k, cv2.CC_STAT_AREA])))
        if not cand:
            return {"ok": False, "x_near": None, "y_near": None, "x_mid": None,
                    "y_mid": None, "e_lat": None, "e_head": None, "comp": None,
                    "origen": "sin_componente"}
        abajo = [c for c in cand if c[1]]
        if abajo:
            k0 = max(abajo, key=lambda c: c[3])[0]
            origen = "toca_abajo"
        elif self.ult_x is not None:
            cerca = min(cand, key=lambda c: abs(c[2] - self.ult_x))
            if abs(cerca[2] - self.ult_x) <= self.salto_max:
                k0 = cerca[0]
                origen = "continuidad"
            else:
                k0 = max(cand, key=lambda c: c[3])[0]
                origen = "salto_grande"
        else:
            k0 = max(cand, key=lambda c: c[3])[0]
            origen = "mas_grande"

        mm = (et == k0)
        xn, yn = centroide_banda(mm, *NEAR)
        xm, ym = centroide_banda(mm, *MID)
        xf, yf = centroide_banda(mm, *FAR)
        # el punto de adelante: MID si esta, si no FAR
        xa, ya = (xm, ym) if xm is not None else (xf, yf)
        d = {"ok": True, "comp": mm, "origen": origen,
             "x_near": xn, "y_near": yn, "x_mid": xa, "y_mid": ya,
             "e_lat": None, "e_head": None}
        if xn is not None:
            d["e_lat"] = xn - CENTRO
            self.ult_x = xn
            self.ult_lat = d["e_lat"]
        if xn is not None and xa is not None and yn is not None and ya is not None:
            # rumbo de la cinta respecto del chasis. y crece hacia ABAJO en la
            # imagen, asi que (yn - ya) es la profundidad hacia adelante.
            d["e_head"] = math.degrees(math.atan2(xa - xn, max(yn - ya, 1e-6)))
            self.ult_head = d["e_head"]
        elif xa is not None:
            self.ult_x = xa
        return d


def objetivo(t, estado, ult):
    """El punto al que hay que ir, segun cuanta evidencia hay.

    HIGH      -> el punto mas lejano disponible
    MEDIUM    -> el punto medio
    LOW       -> el ultimo objetivo confiable (memoria)
    SIN_CERCA -> la componente visible, que es lo unico que hay
    PERDIDA   -> no hay objetivo
    """
    if estado == "PERDIDA":
        return None, None, "sin objetivo"
    if estado in ("HIGH", "MEDIUM") and t["x_mid"] is not None:
        return t["x_mid"], t["y_mid"], "punto adelante de la componente"
    if estado == "SIN_CERCA" and t["x_mid"] is not None:
        return t["x_mid"], t["y_mid"], "componente visible arriba"
    if estado == "LOW":
        if t["x_mid"] is not None:
            return t["x_mid"], t["y_mid"], "punto adelante, evidencia pobre"
        return ult[0], ult[1], "ultimo objetivo confiable (memoria)"
    if t["x_near"] is not None:
        return t["x_near"], t["y_near"], "solo el punto cercano"
    return ult[0], ult[1], "memoria"


def curvatura_a(x, y):
    """Que tan fuerte hay que girar para alcanzar (x,y) desde el robot.

    El robot esta en (CENTRO, 120): abajo al medio de la imagen. Se usa la
    curvatura de un arco de persecucion pura, normalizada. Positivo = a la
    izquierda de la imagen, igual que el convenio del atan2 del codigo.
    """
    if x is None or y is None:
        return 0.0
    dx = x - CENTRO
    dy = max(120.0 - y, 1.0)
    return math.degrees(math.atan2(dx, dy))


def correr(ruta, desde=0, hasta=10 ** 9, tag="", fps=FPS, salida=None,
           con_video=False):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        print("*** no se pudo abrir %s" % ruta)
        return None
    base = os.path.splitext(os.path.basename(ruta))[0] + (("_" + tag) if tag else "")
    sal = salida or os.path.join(AQUI, "leyes_%s.csv" % base)
    f = open(sal, "w", newline="")
    w = csv.writer(f)
    w.writerow(["source_frame", "source_time_s", "estado", "origen_componente",
                "ang_actual", "ang_estados",
                "x_near", "x_mid", "e_lat", "e_head",
                "target_x", "target_y", "ang_lookahead", "motivo_target"])
    E = 4
    PW, PH = W * E, H * E
    ANCHO, ALTO = PW * 2 + 30, PH + 210
    vw = None
    if con_video:
        vw = cv2.VideoWriter(os.path.join(AQUI, "leyes_%s.avi" % base),
                             cv2.VideoWriter_fourcc(*"MJPG"), fps, (ANCHO, ALTO))
    tr = Trayectoria()
    cand = Candidato()
    ult = (None, None)
    i = 0
    S = {k: [] for k in ("actual", "estados", "near_mid", "lookahead")}
    est_cnt = {}
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        idx = i
        i += 1
        g = frame_de_la_pi(fr)
        p = percibir(g)
        est = confianza(p)
        t = tr.paso(g)
        ang, _ = angulo_atan2(g)
        r = {"rot": 0.0, "vel": 45}
        sc = max(-1.0, min(1.0, ang / 90.0 * 1.35))
        r["rot"] = sc
        c = cand.paso(est, 1 if sc > 0 else (-1 if sc < 0 else 0), r["rot"],
                      r["vel"], 1.0 / fps, p["cx_arriba"])
        tx, ty, mot = objetivo(t, est, ult)
        if tx is not None:
            ult = (tx, ty)
        ang_look = curvatura_a(tx, ty)
        if not (desde <= idx <= hasta):
            continue
        est_cnt[est] = est_cnt.get(est, 0) + 1
        w.writerow([idx, "%.3f" % (idx / fps), est, t["origen"],
                    "%.1f" % ang, "%.3f" % c["rot"],
                    "%.1f" % t["x_near"] if t["x_near"] is not None else "",
                    "%.1f" % t["x_mid"] if t["x_mid"] is not None else "",
                    "%.1f" % t["e_lat"] if t["e_lat"] is not None else "",
                    "%.1f" % t["e_head"] if t["e_head"] is not None else "",
                    "%.1f" % tx if tx is not None else "",
                    "%.1f" % ty if ty is not None else "",
                    "%.1f" % ang_look, mot])
        if vw is not None:
            img = np.full((ALTO, ANCHO, 3), (18, 18, 18), np.uint8)
            cam = cv2.resize(g, (PW, PH), interpolation=cv2.INTER_NEAREST)
            img[36:36 + PH, 10:10 + PW] = cam
            vis = np.zeros((H, W, 3), np.uint8)
            m = cv2.inRange(g, LO, HI)
            m[:60, :] = 0
            vis[m > 0] = (60, 60, 60)
            if t["comp"] is not None:
                vis[t["comp"]] = (110, 200, 110)
            vis = cv2.resize(vis, (PW, PH), interpolation=cv2.INTER_NEAREST)
            # los dos puntos de la trayectoria y la recta entre ellos
            if t["x_near"] is not None and t["x_mid"] is not None:
                pn = (int(t["x_near"] * E), int(t["y_near"] * E))
                pm = (int(t["x_mid"] * E), int(t["y_mid"] * E))
                cv2.line(vis, pn, pm, (60, 210, 235), 2)
                cv2.circle(vis, pn, 7, (255, 200, 80), -1)
                cv2.circle(vis, pm, 7, (255, 150, 200), -1)
                cv2.putText(vis, "NEAR", (pn[0] + 10, pn[1]), cv2.FONT_HERSHEY_SIMPLEX,
                            0.45, (255, 200, 80), 1, cv2.LINE_AA)
                cv2.putText(vis, "MID", (pm[0] + 10, pm[1]), cv2.FONT_HERSHEY_SIMPLEX,
                            0.45, (255, 150, 200), 1, cv2.LINE_AA)
            cv2.line(vis, (int(CENTRO * E), 0), (int(CENTRO * E), PH), (90, 90, 90), 1)
            if tx is not None:
                cv2.drawMarker(vis, (int(tx * E), int(ty * E)), (60, 210, 235),
                               cv2.MARKER_TILTED_CROSS, 20, 2)
            img[36:36 + PH, 20 + PW:20 + PW * 2] = vis
            cv2.putText(img, "%s  frame %d  t=%.2fs   estado %s" %
                        (os.path.basename(ruta), idx, idx / fps, est), (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
            y0 = 36 + PH + 26
            filas = [
                ("LO QUE MIDE EL CODIGO DE HOY:  un solo numero", (120, 120, 120), 0.5),
                ("   angle = %+6.1f gr   (mezcla posicion y rumbo)" % ang, (90, 90, 235), 0.6),
                ("LO QUE MIDE near+mid:  dos numeros separados", (120, 120, 120), 0.5),
                ("   error LATERAL = %s px     donde estoy" %
                 (("%+6.1f" % t["e_lat"]) if t["e_lat"] is not None else "   --"),
                 (255, 200, 80), 0.6),
                ("   error RUMBO   = %s gr     hacia donde sigue" %
                 (("%+6.1f" % t["e_head"]) if t["e_head"] is not None else "   --"),
                 (255, 150, 200), 0.6),
            ]
            for k, (txt, col, esc) in enumerate(filas):
                cv2.putText(img, txt, (10, y0 + k * 30), cv2.FONT_HERSHEY_SIMPLEX,
                            esc, col, 1, cv2.LINE_AA)
            cv2.putText(img, "REPLAY - NO ES SIMULACION FISICA", (ANCHO - 430, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 210, 235), 1, cv2.LINE_AA)
            vw.write(img)
        S["actual"].append(ang)
        S["estados"].append(c["rot"] * 90.0)
        S["near_mid"].append(t["e_head"] if t["e_head"] is not None else float("nan"))
        S["lookahead"].append(ang_look)
    cap.release()
    if vw is not None:
        vw.release()
    f.close()
    return S, est_cnt, sal


def inversiones(v):
    v = [x for x in v if not (isinstance(x, float) and math.isnan(x))]
    s = [1 if x > 3 else (-1 if x < -3 else 0) for x in v]
    s = [x for x in s if x]
    return sum(1 for a, b in zip(s, s[1:]) if a != b)


def suavidad(v):
    v = [x for x in v if not (isinstance(x, float) and math.isnan(x))]
    if len(v) < 3:
        return float("nan")
    return float(np.median(np.abs(np.diff(v))))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?", default="")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    ap.add_argument("--tag", default="")
    ap.add_argument("--fps", type=float, default=FPS)
    ap.add_argument("--avi", action="store_true", help="ademas del CSV, un AVI anotado")
    ap.add_argument("--todos", action="store_true")
    a = ap.parse_args()

    casos = []
    if a.todos:
        import glob
        for v in sorted(glob.glob(os.path.join(AQUI, "*.avi"))):
            b = os.path.basename(v)
            if b.startswith(("shadow_", "leyes_", "comparacion", "centrado",
                             "CONTROL", "CASO")):
                continue
            casos.append((v, 0, 10 ** 9, "", FPS))
    else:
        if not a.video:
            print(__doc__)
            return 2
        ruta = a.video if os.path.isabs(a.video) else os.path.join(AQUI, a.video)
        casos.append((ruta, a.desde, a.hasta, a.tag, a.fps))

    print("  CUATRO LEYES SOBRE LOS MISMOS FRAMES")
    print("  inversiones = cuantas veces cambia de lado la senal (menos es mejor)")
    print("  salto p50   = cuanto se mueve la senal entre frames consecutivos, en grados")
    print()
    print("  %-22s %6s | %-30s | %-30s" % ("", "", "  INVERSIONES DE SIGNO",
                                            "  SALTO ENTRE FRAMES (p50)"))
    print("  %-22s %6s | %7s %7s %7s %7s | %7s %7s %7s %7s" %
          ("caso", "n", "actual", "estados", "nearmid", "lookah",
           "actual", "estados", "nearmid", "lookah"))
    print("  " + "-" * 100)
    for ruta, d, h, tag, fps in casos:
        out = correr(ruta, d, h, tag, fps, con_video=(a.avi and not a.todos))
        if not out:
            continue
        S, est_cnt, sal = out
        n = len(S["actual"])
        if n < 20:
            continue
        nom = os.path.splitext(os.path.basename(ruta))[0] + (("_" + tag) if tag else "")
        print("  %-22s %6d | %7d %7d %7d %7d | %7.1f %7.1f %7.1f %7.1f" %
              (nom[:22], n,
               inversiones(S["actual"]), inversiones(S["estados"]),
               inversiones(S["near_mid"]), inversiones(S["lookahead"]),
               suavidad(S["actual"]), suavidad(S["estados"]),
               suavidad(S["near_mid"]), suavidad(S["lookahead"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
