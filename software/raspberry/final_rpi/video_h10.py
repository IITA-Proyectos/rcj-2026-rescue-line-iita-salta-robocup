# -*- coding: utf-8 -*-
"""
VIDEO DE AUDITORIA DE H10 - baseline contra la politica experimental, lado a lado.

Cumple el requisito de ChatGPT en #138: "revisar visualmente el 100 % de las
intervenciones si son manejables". A U=20 son 89 sobre 14.000 frames: manejable.

Corre las DOS variantes sobre EXACTAMENTE los mismos frames -es replay, asi que
es valido- y muestra tres paneles: camara, diagnostico baseline, diagnostico
H10. Marca el target de cada uno y el delta_alcance que disparo.

    python3 video_h10.py                 # seguir + todas las intervenciones
    python3 video_h10.py --umbral 40

OPEN-LOOP REPLAY. La candidata no manejo: los frames los genero el controlador
que realmente estaba en el robot. Esto muestra QUE ELIGE cada variante sobre las
mismas observaciones, no que trayectoria haria.
"""

import argparse
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retro_guard_exp as R

FPS_SALIDA = 100.0 / 3.0
AVISO = "OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF"
FT = cv2.FONT_HERSHEY_SIMPLEX
E = 3
CTX_ANTES, CTX_DESPUES = 4, 8

C_MASK = (45, 45, 45)
C_COMP = (35, 95, 35)
C_SKEL = (0, 150, 190)
C_PATH = (255, 170, 60)
C_BASE = (0, 120, 255)      # naranja: baseline
C_H10 = (120, 255, 120)     # verde:   H10
C_EST = {"HIGH": (70, 220, 70), "MEDIUM": (80, 210, 220),
         "LOW": (0, 160, 255), "LOW_FORWARD": (0, 190, 255),
         "SIN_CERCA": (255, 180, 60), "PERDIDA": (80, 80, 255)}


def txt(img, x, y, s, col=(210, 210, 210), esc=0.5, gr=1):
    cv2.putText(img, s, (x, y), FT, esc, col, gr, cv2.LINE_AA)


def panel(v2, r, col_target, etiqueta):
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
    big = cv2.resize(vis, (v2.W * E, v2.H * E),
                     interpolation=cv2.INTER_NEAREST)
    t = r.get("target")
    if t is not None:
        cv2.drawMarker(big, (int(t[0] * E + E // 2), int(t[1] * E + E // 2)),
                       col_target, cv2.MARKER_TILTED_CROSS, 9 * E, 2)
    if r.get("start") is not None:
        cv2.circle(big, (int(r["start"][0] * E + E // 2),
                         int(r["start"][1] * E + E // 2)), 4, (255, 130, 40), -1)
    cv2.rectangle(big, (0, 0), (v2.W * E, 26), (0, 0, 0), -1)
    txt(big, 8, 19, etiqueta, col_target, 0.55, 2)
    return big


def steer_de(t, v2):
    if t is None:
        return None
    return float(np.clip(-90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90))


def cuadro(v2, g, rb, rh, meta, W_out, H_out):
    cam = cv2.resize(g, (v2.W * E, v2.H * E),
                     interpolation=cv2.INTER_NEAREST)
    pb = panel(v2, rb, C_BASE, "BASELINE  SinBranch")
    ph = panel(v2, rh, C_H10, "H10 experimental")
    out = np.zeros((H_out, W_out), np.uint8)
    out = np.zeros((H_out, W_out, 3), np.uint8)
    w = v2.W * E
    out[:v2.H * E, :w] = cam
    out[:v2.H * E, w:2 * w] = pb
    out[:v2.H * E, 2 * w:3 * w] = ph
    cv2.rectangle(out, (0, 0), (w, 26), (0, 0, 0), -1)
    txt(out, 8, 19, "CAMARA (entrada del replay)", (230, 230, 230), 0.55, 2)

    y0 = v2.H * E + 30
    txt(out, 12, y0, "%s   f%d" % (meta["video"], meta["frame"]),
        (90, 230, 255), 0.8, 2)
    st = rb.get("state", "?")
    txt(out, 330, y0, "ESTADO %s" % st, C_EST.get(st, (220, 220, 220)), 0.65, 2)
    if meta.get("interv"):
        cv2.rectangle(out, (600, y0 - 22), (600 + 420, y0 + 8), (0, 90, 0), -1)
        txt(out, 610, y0, "INTERVIENE   delta_alcance %d" % meta["delta"],
            (150, 255, 150), 0.62, 2)

    tb, th = rb.get("target"), rh.get("target")
    sb, sh = steer_de(tb, v2), steer_de(th, v2)
    txt(out, 12, y0 + 34, "baseline  target %s   steer %s"
        % ("--" if tb is None else "(%3.0f,%3.0f)" % tb,
           "--" if sb is None else "%+6.1f" % sb), C_BASE, 0.6, 2)
    txt(out, 12, y0 + 64, "H10       target %s   steer %s"
        % ("--" if th is None else "(%3.0f,%3.0f)" % th,
           "--" if sh is None else "%+6.1f" % sh), C_H10, 0.6, 2)
    if sb is not None and sh is not None and abs(sb - sh) > 0.05:
        txt(out, 620, y0 + 64, "diferencia de steer  %+.1f deg" % (sh - sb),
            (255, 255, 255), 0.6, 2)
    txt(out, 12, y0 + 94, "naranja = baseline    verde = H10    "
        "amarillo = skeleton    azul = path", (130, 130, 130), 0.48)
    txt(out, W_out - 470, H_out - 12, AVISO, (110, 110, 110), 0.46)
    return out


def placa(W_out, H_out, lineas, seg):
    img = np.zeros((H_out, W_out, 3), np.uint8)
    y = int(H_out * 0.28)
    for s, esc, gr, col in lineas:
        (tw, _), _ = cv2.getTextSize(s, FT, esc, gr)
        txt(img, (W_out - tw) // 2, y, s, col, esc, gr)
        y += int(38 * esc + 24)
    txt(img, W_out - 470, H_out - 12, AVISO, (110, 110, 110), 0.46)
    return [img] * int(round(seg * FPS_SALIDA))


def main():
    ap = argparse.ArgumentParser(description="Auditoria visual de H10")
    ap.add_argument("--umbral", type=int, default=20)
    ap.add_argument("--salida", default="REGISTRO_H10.mp4")
    a = ap.parse_args()

    v4, v3, v2 = R.cargar()
    SinBranch = R.hacer_sinbranch(v4)
    ctx = ["", 0]
    activo = [False]
    R.instalar(v2, a.umbral, activo, ctx)

    W_out = v2.W * E * 3
    H_out = v2.H * E + 150

    # --- 1) descubrir en que frames interviene -----------------------------
    print("  buscando intervenciones con umbral %d ..." % a.umbral)
    porvideo = {}
    for vid in R.AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        ctx[0] = vid
        del R.LOG[:]
        activo[0] = True
        cap = cv2.VideoCapture(ruta)
        tr = SinBranch(FPS_SALIDA)
        i = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            ctx[1] = i
            tr.step(v2.frame_pi(fr))
            i += 1
        cap.release()
        activo[0] = False
        if R.LOG:
            porvideo[vid] = {e["frame"]: e["delta"] for e in R.LOG}
            print("    %-16s %3d intervenciones" % (vid, len(R.LOG)))
    total = sum(len(v) for v in porvideo.values())
    print("  total %d intervenciones" % total)

    vw = cv2.VideoWriter(os.path.join(AQUI, a.salida),
                         cv2.VideoWriter_fourcc(*"mp4v"), FPS_SALIDA,
                         (W_out, H_out))
    if not vw.isOpened():
        print("*** no abre el writer")
        return 2
    n_out = 0
    for f in placa(W_out, H_out, [
            ("AUDITORIA H10 - POLITICA EXPERIMENTAL", 1.1, 3, (255, 255, 255)),
            ("baseline SinBranch  contra  SinBranch + H10", 0.75, 2,
             (90, 230, 255)),
            ("umbral delta_alcance = %d   ->   %d intervenciones"
             % (a.umbral, total), 0.7, 2, (200, 200, 200)),
            ("las dos variantes ven EXACTAMENTE los mismos frames", 0.6, 1,
             (160, 160, 160)),
            ("RESULTADO DEL A/B: las inversiones SUBEN en los 5 umbrales", 0.7,
             2, (0, 165, 255)),
            ("politica DESCARTADA - esto es la evidencia, no una candidata",
             0.65, 2, (0, 165, 255))], 5.0):
        vw.write(f)
        n_out += 1

    # --- 2) renderizar: seguir completo + ventanas de cada intervencion -----
    tramos = [("seguir.avi", 1160, 1210, "el caso que motivo H10")]
    for vid, marcas in porvideo.items():
        for f in sorted(marcas):
            if vid == "seguir.avi" and 1160 <= f <= 1210:
                continue
            tramos.append((vid, f - CTX_ANTES, f + CTX_DESPUES, None))

    # unir ventanas solapadas del mismo video
    fusion = []
    for vid, d, h, nota in tramos:
        if fusion and fusion[-1][0] == vid and d <= fusion[-1][2] + 2:
            fusion[-1] = (vid, fusion[-1][1], max(h, fusion[-1][2]),
                          fusion[-1][3])
        else:
            fusion.append((vid, d, h, nota))
    print("  %d tramos a renderizar" % len(fusion))

    for k, (vid, d, h, nota) in enumerate(fusion):
        marcas = porvideo.get(vid, {})
        ruta = os.path.join(AQUI, vid)
        cap = cv2.VideoCapture(ruta)
        tb = SinBranch(FPS_SALIDA)
        th = SinBranch(FPS_SALIDA)
        ctx[0] = vid
        i = 0
        for f in placa(W_out, H_out, [
                ("%s   f%d-%d" % (vid.replace(".avi", ""), max(d, 0), h),
                 1.0, 2, (90, 230, 255))]
                + ([(nota, 0.7, 1, (200, 200, 200))] if nota else []), 0.7):
            vw.write(f)
            n_out += 1
        while True:
            ok, fr = cap.read()
            if not ok or i > h:
                break
            ctx[1] = i
            g = v2.frame_pi(fr)
            activo[0] = False
            rb = tb.step(g)
            activo[0] = True
            rh = th.step(g)
            activo[0] = False
            if i >= max(d, 0):
                meta = dict(video=vid.replace(".avi", ""), frame=i,
                            interv=(i in marcas), delta=marcas.get(i, 0))
                img = cuadro(v2, g, rb, rh, meta, W_out, H_out)
                reps = 3 if i in marcas else 1
                for _ in range(reps):
                    vw.write(img)
                    n_out += 1
            i += 1
        cap.release()
        if (k + 1) % 10 == 0:
            print("    %d/%d tramos, %d frames de salida"
                  % (k + 1, len(fusion), n_out))

    vw.release()
    ruta = os.path.join(AQUI, a.salida)
    print("")
    print("  %s   %d frames   %.1f s   %.1f MB"
          % (a.salida, n_out, n_out / FPS_SALIDA,
             os.path.getsize(ruta) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
