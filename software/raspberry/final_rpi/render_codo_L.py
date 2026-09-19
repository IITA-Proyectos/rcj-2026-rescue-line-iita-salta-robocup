# -*- coding: utf-8 -*-
"""REGISTRO VISUAL DEL DETECTOR DE CODO: dibuja la L que el detector cree ver.

Benjamin, 26-ago: "necesito que me hagas un registro completo y verlo yo mismo
y ver si es verdad. Simbolizalo con una L el codo que se detecta: entre mas
cerrado el codo, mas cerrada tiene que ser esa L".

QUE DIBUJA, y por que asi
-------------------------
La L NO es un dibujo decorativo: sus dos brazos son LAS DOS RECTAS que el
detector ajusto a la cadena -el primer 40 % y el ultimo 40 %-, apoyadas en el
vertice. O sea que **la apertura de la L ES el angulo medido**. Si el detector
se equivoca, la L se ve torcida contra la cinta y se nota a simple vista. Ese
es el punto: que sea falsable mirando.

  amarillo   la cadena que eligio CAMINO (sobre la que se mide todo)
  circulo    el vertice: el punto de la cadena mas apartado de la recta
             robot -> punta. Es el "donde".
  L          verde  = el detector NO dispara en este frame
             rojo   = DISPARA: ang >= UMBRAL y los dos residuos <= RES_MAX
  barra      el angulo, de 0 a 90. Cuanto mas llena, mas cerrado el codo.
  npts       largo de la cadena. Es la LEJANIA: cadena larga = el codo esta
             lejos todavia; cadena corta = ya llego el momento.

Los dos numeros de arriba son los que la maniobra necesita:
    ang  -> CUANTO girar        npts -> CUANDO girar

    python render_codo_L.py
    python render_codo_L.py --video hist.avi --salida REGISTRO_CODO_L.mp4
    python render_codo_L.py --desde 300 --hasta 900     # solo un tramo
"""
import argparse
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
UMBRAL = 45.0        # ang40 para disparar
RES_MAX = 2.0        # residuo maximo de los dos ajustes, px
ESC = 4              # 160x120 -> 640x480


def panel(fr):
    """hist.avi y compania son 640x240: DOS paneles. El izquierdo es la camara."""
    h, w = fr.shape[:2]
    if (w, h) == (640, 240):
        fr = fr[:, :w // 2]
    return cv2.resize(fr, (160, 120), interpolation=cv2.INTER_NEAREST)


def ajuste(P):
    A = np.asarray(P, float)
    if len(A) < 5:
        return None, np.nan
    m = A.mean(axis=0)
    B = A - m
    _, _, V = np.linalg.svd(B, full_matrices=False)
    d = V[0]
    perp = np.array([-d[1], d[0]])
    return d, float(np.abs(B @ perp).mean())


def medir(cad, pts):
    n = len(cad)
    if n < 24:
        return None
    P = np.array([(pts[i][1], pts[i][0]) for i in cad], float)
    k1, k2 = int(n * 0.40), int(n * 0.60)
    d1, r1 = ajuste(P[:k1])
    d2, r2 = ajuste(P[k2:])
    if d1 is None or d2 is None:
        return None
    ang = float(np.degrees(np.arccos(min(1.0, max(-1.0, abs(float(np.dot(d1, d2))))))))
    v = P[-1] - P[0]
    L = float(np.hypot(*v))
    if L < 1e-6:
        return None
    nrm = np.array([-v[1], v[0]]) / L
    j = int(np.argmax(np.abs((P - P[0]) @ nrm)))
    # orientar cada brazo DESDE el vertice: uno hacia el robot, otro adelante
    if np.dot(d1, P[0] - P[j]) < 0:
        d1 = -d1
    if np.dot(d2, P[-1] - P[j]) < 0:
        d2 = -d2
    return dict(ang=ang, r1=r1, r2=r2, P=P, vert=P[j], d1=d1, d2=d2, npts=n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="hist.avi")
    ap.add_argument("--salida", default="REGISTRO_CODO_L.mp4")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    ap.add_argument("--fps", type=float, default=15.0)
    a = ap.parse_args()

    os.environ.setdefault("VISION_LINEA", "camino")
    sys.path.insert(0, AQUI)
    import vision_linea as VL
    if not VL.ACTIVA:
        sys.exit("vision_linea dice ACTIVA=False")

    ruta = a.video if os.path.exists(a.video) else os.path.join(AQUI, a.video)
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        sys.exit("no pude abrir %s" % ruta)

    W, H = 160 * ESC, 120 * ESC
    out = cv2.VideoWriter(a.salida, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
    n = disparos = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if n > a.hasta:
            break
        f = panel(fr)
        try:
            VL.angulo(f)
        except Exception:
            pass
        if n < a.desde:
            n += 1
            continue

        vis = cv2.resize(f, (W, H), interpolation=cv2.INTER_NEAREST)
        vis = (vis * 0.55).astype(np.uint8)      # oscurecer para que resalte

        m = None
        cp = VL._CP
        if cp is not None and "dist" in cp.CAP:
            pts, dist = cp.CAP["pts"], cp.CAP["dist"]
            prev, si = cp.CAP["prev"], cp.CAP["si"]
            fin = np.where(np.isfinite(dist))[0]
            if len(fin) >= 8:
                F = int(fin[int(np.argmax(dist[fin]))])
                cad = VL._v2.reconstruct(prev, si, F)
                if cad:
                    m = medir(cad, pts)

        if m:
            # la cadena
            for p, q in zip(m["P"], m["P"][1:]):
                cv2.line(vis, (int(p[0] * ESC), int(p[1] * ESC)),
                         (int(q[0] * ESC), int(q[1] * ESC)), (0, 220, 255), 2)
            dispara = m["ang"] >= UMBRAL and m["r1"] <= RES_MAX and m["r2"] <= RES_MAX
            if dispara:
                disparos += 1
            col = (0, 0, 255) if dispara else (0, 255, 0)
            v = m["vert"] * ESC
            BRAZO = 36 * ESC
            for d in (m["d1"], m["d2"]):
                p2 = v + d * BRAZO
                cv2.line(vis, (int(v[0]), int(v[1])), (int(p2[0]), int(p2[1])), col, 5)
            cv2.circle(vis, (int(v[0]), int(v[1])), 9, col, -1)
            cv2.circle(vis, (int(v[0]), int(v[1])), 9, (255, 255, 255), 2)

            # HUD
            txt = "ang %2.0f   npts %3d" % (m["ang"], m["npts"])
            cv2.putText(vis, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 5)
            cv2.putText(vis, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
            if dispara:
                cv2.putText(vis, "CODO", (W - 150, 34), cv2.FONT_HERSHEY_SIMPLEX,
                            1.0, (0, 0, 0), 6)
                cv2.putText(vis, "CODO", (W - 150, 34), cv2.FONT_HERSHEY_SIMPLEX,
                            1.0, (0, 0, 255), 3)
            # barra del angulo: 0 a 90
            x0, y0, x1 = 10, H - 26, W - 10
            cv2.rectangle(vis, (x0, y0), (x1, y0 + 16), (60, 60, 60), -1)
            ancho = int((x1 - x0) * min(m["ang"], 90.0) / 90.0)
            cv2.rectangle(vis, (x0, y0), (x0 + ancho, y0 + 16), col, -1)
            xu = x0 + int((x1 - x0) * UMBRAL / 90.0)
            cv2.line(vis, (xu, y0 - 4), (xu, y0 + 20), (255, 255, 255), 2)
        else:
            cv2.putText(vis, "sin cadena", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 0, 0), 5)
            cv2.putText(vis, "sin cadena", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (150, 150, 150), 2)

        cv2.putText(vis, "f%d" % n, (10, H - 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 4)
        cv2.putText(vis, "f%d" % n, (10, H - 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 1)
        cv2.putText(vis, "L verde = no dispara | L roja = CODO | brazos = las dos rectas ajustadas",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3)
        cv2.putText(vis, "L verde = no dispara | L roja = CODO | brazos = las dos rectas ajustadas",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1)
        out.write(vis)
        n += 1
        if n % 300 == 0:
            print("   %d frames..." % n)
    cap.release()
    out.release()
    print("listo: %s   %d frames, %d con CODO" % (a.salida, n, disparos))


if __name__ == "__main__":
    main()
