# -*- coding: utf-8 -*-
"""
VIDEO PURSUIT - baseline contra la busqueda monotona de Coulter, lado a lado.

Las dos variantes ven EXACTAMENTE los mismos frames. Es replay: sirve para ver
QUE ELIGE cada una sobre las mismas observaciones, no que trayectoria haria.

Muestra los tres tramos que deciden, mas todos los frames donde las dos
variantes eligen distinto:

  seguir f1160-1210   el caso que motivo H10: el baseline se engancha 20 frames
                      en el pedazo de cinta YA RECORRIDO
  hist   f1354-1490   la falla historica
  lineal f795-875     el control positivo: target en (2,95) con steer +87 y la
                      curva SE COMPLETO. No se puede romper.

    python3 video_pursuit.py
    python3 video_pursuit.py --solo-tramos     # sin el barrido de diferencias

OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF
"""

import argparse
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import pursuit as P

FPS = 100.0 / 3.0
E = 3
AVISO = "OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF"
FT = cv2.FONT_HERSHEY_SIMPLEX

C_MASK, C_COMP, C_SKEL, C_PATH = (45, 45, 45), (35, 95, 35), (0, 150, 190), (255, 170, 60)
C_BASE, C_MONO = (0, 120, 255), (120, 255, 120)
C_EST = {"HIGH": (70, 220, 70), "MEDIUM": (80, 210, 220), "LOW": (0, 160, 255),
         "LOW_FORWARD": (0, 190, 255), "SIN_CERCA": (255, 180, 60),
         "PERDIDA": (80, 80, 255)}

TRAMOS = [
    ("seguir.avi", 1160, 1210, "el caso que motivo H10: enganche 20 frames en la cinta ya recorrida"),
    ("hist.avi", 1354, 1490, "la falla historica"),
    ("lineal.avi", 795, 875, "CONTROL POSITIVO: steer +87 correcto, no se puede romper"),
]


def txt(img, x, y, s, col=(210, 210, 210), esc=0.5, gr=1):
    cv2.putText(img, s, (x, y), FT, esc, col, gr, cv2.LINE_AA)


def panel(v2, r, col, etiqueta):
    vis = np.zeros((v2.H, v2.W, 3), np.uint8)
    if r.get("mask") is not None:
        vis[r["mask"] > 0] = C_MASK
    if r.get("comp") is not None:
        vis[r["comp"] > 0] = C_COMP
    if r.get("skel") is not None:
        vis[r["skel"] > 0] = C_SKEL
    if r.get("path"):
        q = np.asarray([(int(round(x)), int(round(y))) for x, y in r["path"]],
                       np.int32)
        if len(q) >= 2:
            cv2.polylines(vis, [q], False, C_PATH, 1)
    cv2.line(vis, (int(round(v2.CENTER)), 0),
             (int(round(v2.CENTER)), v2.H - 1), (95, 95, 95), 1)
    big = cv2.resize(vis, (v2.W * E, v2.H * E), interpolation=cv2.INTER_NEAREST)
    t = r.get("target")
    if t is not None:
        cv2.drawMarker(big, (int(t[0] * E + E // 2), int(t[1] * E + E // 2)),
                       col, cv2.MARKER_TILTED_CROSS, 9 * E, 2)
    if r.get("start") is not None:
        cv2.circle(big, (int(r["start"][0] * E + E // 2),
                         int(r["start"][1] * E + E // 2)), 4, (255, 130, 40), -1)
    cv2.rectangle(big, (0, 0), (v2.W * E, 26), (0, 0, 0), -1)
    txt(big, 8, 19, etiqueta, col, 0.55, 2)
    return big


def steer(t, v2):
    return None if t is None else float(np.clip(
        -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90))


def cuadro(v2, g, rb, rm, meta, W, H):
    cam = cv2.resize(g, (v2.W * E, v2.H * E), interpolation=cv2.INTER_NEAREST)
    out = np.zeros((H, W, 3), np.uint8)
    w = v2.W * E
    out[:v2.H * E, :w] = cam
    out[:v2.H * E, w:2 * w] = panel(v2, rb, C_BASE, "BASELINE  busqueda global")
    out[:v2.H * E, 2 * w:3 * w] = panel(v2, rm, C_MONO, "MONO  Coulter 1992")
    cv2.rectangle(out, (0, 0), (w, 26), (0, 0, 0), -1)
    txt(out, 8, 19, "CAMARA (entrada del replay)", (230, 230, 230), 0.55, 2)

    y0 = v2.H * E + 30
    txt(out, 12, y0, "%s   f%d" % (meta["video"], meta["frame"]),
        (90, 230, 255), 0.8, 2)
    st = rb.get("state", "?")
    txt(out, 330, y0, "ESTADO %s" % st, C_EST.get(st, (220, 220, 220)), 0.65, 2)
    tb, tm = rb.get("target"), rm.get("target")
    sb, sm = steer(tb, v2), steer(tm, v2)
    if tb is not None and tm is not None and (abs(tb[0] - tm[0]) > 0.5
                                              or abs(tb[1] - tm[1]) > 0.5):
        cv2.rectangle(out, (600, y0 - 22), (600 + 300, y0 + 8), (0, 90, 0), -1)
        txt(out, 610, y0, "ELIGEN DISTINTO", (150, 255, 150), 0.62, 2)
    txt(out, 12, y0 + 34, "baseline  target %s   steer %s"
        % ("--" if tb is None else "(%3.0f,%3.0f)" % tb,
           "--" if sb is None else "%+6.1f" % sb), C_BASE, 0.6, 2)
    txt(out, 12, y0 + 64, "MONO      target %s   steer %s"
        % ("--" if tm is None else "(%3.0f,%3.0f)" % tm,
           "--" if sm is None else "%+6.1f" % sm), C_MONO, 0.6, 2)
    if sb is not None and sm is not None and abs(sb - sm) > 0.05:
        txt(out, 620, y0 + 64, "diferencia %+.1f deg" % (sm - sb),
            (255, 255, 255), 0.6, 2)
    if meta.get("nota"):
        txt(out, 12, y0 + 94, meta["nota"], (150, 150, 150), 0.48)
    txt(out, W - 470, H - 12, AVISO, (110, 110, 110), 0.46)
    return out


def placa(W, H, lineas, seg):
    img = np.zeros((H, W, 3), np.uint8)
    y = int(H * 0.28)
    for s, esc, gr, col in lineas:
        (tw, _), _ = cv2.getTextSize(s, FT, esc, gr)
        txt(img, (W - tw) // 2, y, s, col, esc, gr)
        y += int(38 * esc + 24)
    txt(img, W - 470, H - 12, AVISO, (110, 110, 110), 0.46)
    return [img] * int(round(seg * FPS))


def main():
    ap = argparse.ArgumentParser(description="BASE contra MONO, lado a lado")
    ap.add_argument("--solo-tramos", action="store_true", dest="solo_tramos")
    ap.add_argument("--salida", default="REGISTRO_MONO.mp4")
    a = ap.parse_args()

    v4, v3, v2 = P.cargar()
    SB = P.hacer_sinbranch(v4)
    xz = P.hacer_suelo(v2, P.HFOV_DEF)
    cfg = dict(mono=False, suelo=False, xz=xz, ld_suelo=0, lo_suelo=0,
               hi_suelo=0)
    P.instalar(v2, cfg)

    W, H = v2.W * E * 3, v2.H * E + 150
    vw = cv2.VideoWriter(os.path.join(AQUI, a.salida),
                         cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    if not vw.isOpened():
        print("*** no abre el writer")
        return 2

    n = 0
    for f in placa(W, H, [
            ("BUSQUEDA MONOTONA HACIA ADELANTE", 1.1, 3, (255, 255, 255)),
            ("Coulter 1992, CMU-RI-TR-92-01", 0.75, 2, (90, 230, 255)),
            ("primero el punto mas cercano, despues se avanza SOBRE el camino",
             0.6, 1, (180, 180, 180)),
            ("A/B: inversiones -26 de 392 (-6,6 %)", 0.75, 2, (120, 255, 120)),
            ("pero huecos +6 y saltos +7: NO pasa el criterio preregistrado",
             0.65, 2, (0, 165, 255))], 5.0):
        vw.write(f)
        n += 1

    tramos = list(TRAMOS)
    if not a.solo_tramos:
        print("  buscando frames donde eligen distinto...")
        for vid in P.AB.AUTONOMOS:
            ruta = os.path.join(AQUI, vid)
            if not os.path.exists(ruta) or vid in [t[0] for t in TRAMOS]:
                continue
            cap = cv2.VideoCapture(ruta)
            tb, tm = SB(FPS), SB(FPS)
            i, difs = 0, []
            while True:
                ok, fr = cap.read()
                if not ok:
                    break
                g = v2.frame_pi(fr)
                cfg["mono"] = False
                rb = tb.step(g)
                cfg["mono"] = True
                rm = tm.step(g)
                cfg["mono"] = False
                a_, b_ = rb.get("target"), rm.get("target")
                if a_ is not None and b_ is not None and (
                        abs(a_[0] - b_[0]) > 3 or abs(a_[1] - b_[1]) > 3):
                    difs.append(i)
                i += 1
            cap.release()
            if difs:
                print("    %-16s %3d frames distintos" % (vid, len(difs)))
                j = 0
                while j < len(difs):
                    k = j
                    while k + 1 < len(difs) and difs[k + 1] - difs[k] <= 6:
                        k += 1
                    tramos.append((vid, max(difs[j] - 4, 0), difs[k] + 8, None))
                    j = k + 1

    print("  %d tramos" % len(tramos))
    for vid, d, h, nota in tramos:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        for f in placa(W, H, [("%s   f%d-%d" % (vid.replace(".avi", ""), d, h),
                               1.0, 2, (90, 230, 255))]
                       + ([(nota, 0.62, 1, (200, 200, 200))] if nota else []),
                       0.8):
            vw.write(f)
            n += 1
        cap = cv2.VideoCapture(ruta)
        tb, tm = SB(FPS), SB(FPS)
        i = 0
        while True:
            ok, fr = cap.read()
            if not ok or i > h:
                break
            g = v2.frame_pi(fr)
            cfg["mono"] = False
            rb = tb.step(g)
            cfg["mono"] = True
            rm = tm.step(g)
            cfg["mono"] = False
            if i >= d:
                img = cuadro(v2, g, rb, rm,
                             dict(video=vid.replace(".avi", ""), frame=i,
                                  nota=nota), W, H)
                vw.write(img)
                n += 1
            i += 1
        cap.release()
    vw.release()
    ruta = os.path.join(AQUI, a.salida)
    print("")
    print("  %s   %d frames   %.1f s   %.1f MB"
          % (a.salida, n, n / FPS, os.path.getsize(ruta) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
