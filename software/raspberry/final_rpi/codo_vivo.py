# -*- coding: utf-8 -*-
"""EL DETECTOR DE CODO, EN VIVO EN LA RASPBERRY. Con la L dibujada.

Benjamin, 26-ago: "puedes darme para ejecutarlo visualmente en la raspberry
ahora que la tengo, asi te envio las capturas de los codos que tiene que
detectar?".

QUE HACE
  * abre la camara y corre el pipeline de la CADENA (CAMINO/MONO)
  * dibuja la L: sus dos brazos SON las dos rectas ajustadas a la cadena,
    apoyadas en el vertice, asi que la apertura de la L ES el angulo medido
  * GUARDA UN PNG cada vez que detecta un codo, con cooldown para no llenar
    la tarjeta
  * imprime una linea por segundo en la terminal, para que se vea por SSH
    aunque no haya pantalla

NO TOCA main.py, NO abre el puerto serie, NO mueve un motor. El robot puede
estar apagado: se lo pasea a mano por la pista.

    python3 codo_vivo.py
    python3 codo_vivo.py --umbral 35          # mas sensible
    python3 codo_vivo.py --todo               # guarda TAMBIEN los que no disparan
    python3 codo_vivo.py --video salida.avi   # ademas graba el video entero

Las fotos van a ./codos_vivo/ . Para traerlas a la PC:
    scp -r iita@<ip>:/home/iita/Desktop/codos_vivo .
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
ESC = 4


def ajuste(P):
    A = np.asarray(P, float)
    if len(A) < 5:
        return None, np.nan
    B = A - A.mean(axis=0)
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
    if np.dot(d1, P[0] - P[j]) < 0:
        d1 = -d1
    if np.dot(d2, P[-1] - P[j]) < 0:
        d2 = -d2
    return dict(ang=ang, r1=r1, r2=r2, P=P, vert=P[j], d1=d1, d2=d2, npts=n)


def pintar(f160, m, dispara, umbral):
    W, H = 160 * ESC, 120 * ESC
    vis = cv2.resize(f160, (W, H), interpolation=cv2.INTER_NEAREST)
    vis = (vis * 0.55).astype(np.uint8)
    if m:
        for p, q in zip(m["P"], m["P"][1:]):
            cv2.line(vis, (int(p[0] * ESC), int(p[1] * ESC)),
                     (int(q[0] * ESC), int(q[1] * ESC)), (0, 220, 255), 2)
        col = (0, 0, 255) if dispara else (0, 255, 0)
        v = m["vert"] * ESC
        for d in (m["d1"], m["d2"]):
            p2 = v + d * (36 * ESC)
            cv2.line(vis, (int(v[0]), int(v[1])), (int(p2[0]), int(p2[1])), col, 5)
        cv2.circle(vis, (int(v[0]), int(v[1])), 9, col, -1)
        cv2.circle(vis, (int(v[0]), int(v[1])), 9, (255, 255, 255), 2)
        t = "ang %2.0f   npts %3d" % (m["ang"], m["npts"])
        for c, g in (((0, 0, 0), 5), (col, 2)):
            cv2.putText(vis, t, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, c, g)
        if dispara:
            for c, g in (((0, 0, 0), 6), ((0, 0, 255), 3)):
                cv2.putText(vis, "CODO", (W - 160, 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, c, g)
        x0, y0, x1 = 10, H - 26, W - 10
        cv2.rectangle(vis, (x0, y0), (x1, y0 + 16), (60, 60, 60), -1)
        cv2.rectangle(vis, (x0, y0), (x0 + int((x1 - x0) * min(m["ang"], 90) / 90.0),
                                       y0 + 16), col, -1)
        xu = x0 + int((x1 - x0) * umbral / 90.0)
        cv2.line(vis, (xu, y0 - 4), (xu, y0 + 20), (255, 255, 255), 2)
    else:
        for c, g in (((0, 0, 0), 5), ((150, 150, 150), 2)):
            cv2.putText(vis, "sin cadena", (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, c, g)
    return vis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--umbral", type=float, default=45.0)
    ap.add_argument("--res", type=float, default=2.0)
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--dir", default="codos_vivo")
    ap.add_argument("--cooldown", type=float, default=1.0, help="s entre fotos")
    ap.add_argument("--todo", action="store_true", help="guardar tambien los no-codo")
    ap.add_argument("--video", default=None, help="grabar ademas el video entero")
    a = ap.parse_args()

    os.environ.setdefault("VISION_LINEA", "camino")
    sys.path.insert(0, AQUI)
    try:
        import vision_linea as VL
    except Exception as e:
        sys.exit("no pude importar vision_linea (%s).\nFaltan los modulos de la cadena?" % e)
    if not VL.ACTIVA:
        sys.exit("vision_linea dice ACTIVA=False")

    os.makedirs(a.dir, exist_ok=True)
    cap = cv2.VideoCapture(a.cam)
    if not cap.isOpened():
        sys.exit("no pude abrir la camara %d" % a.cam)

    hay_pantalla = bool(os.environ.get("DISPLAY"))
    vw = None
    print("umbral %.0f grados, residuo <= %.1f px.  Fotos en ./%s/" % (a.umbral, a.res, a.dir))
    print("Pasea el robot A MANO por la pista. Ctrl-C para cortar.")
    print("%s\n" % ("Mostrando ventana." if hay_pantalla else "Sin DISPLAY: solo consola y fotos."))

    n = guardadas = 0
    ult_foto = 0.0
    ult_log = time.time()
    try:
        while True:
            ok, fr = cap.read()
            if not ok:
                continue
            f = cv2.resize(fr, (160, 120), interpolation=cv2.INTER_NEAREST)
            try:
                VL.angulo(f)
            except Exception:
                pass
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
            dispara = bool(m and m["ang"] >= a.umbral and m["r1"] <= a.res and m["r2"] <= a.res)
            vis = pintar(f, m, dispara, a.umbral)

            ahora = time.time()
            if (dispara or a.todo) and ahora - ult_foto >= a.cooldown:
                guardadas += 1
                nom = "%s/%s_%03d_ang%02d.png" % (
                    a.dir, "CODO" if dispara else "no", guardadas,
                    int(m["ang"]) if m else 0)
                cv2.imwrite(nom, vis)
                ult_foto = ahora
                if dispara:
                    print("  CODO  ang=%2.0f  npts=%3d  -> %s" % (m["ang"], m["npts"], nom))

            if ahora - ult_log >= 1.0:
                if m:
                    print("    ang %2.0f  npts %3d  res %.1f/%.1f   %s"
                          % (m["ang"], m["npts"], m["r1"], m["r2"],
                             "<<< CODO" if dispara else ""))
                else:
                    print("    sin cadena")
                ult_log = ahora

            if a.video:
                if vw is None:
                    vw = cv2.VideoWriter(a.video, cv2.VideoWriter_fourcc(*"MJPG"),
                                         15.0, (vis.shape[1], vis.shape[0]))
                vw.write(vis)
            if hay_pantalla:
                cv2.imshow("codo", vis)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            n += 1
    except KeyboardInterrupt:
        print("\ncortado.")
    cap.release()
    if vw is not None:
        vw.release()
    if hay_pantalla:
        cv2.destroyAllWindows()
    print("%d frames, %d fotos guardadas en ./%s/" % (n, guardadas, a.dir))


if __name__ == "__main__":
    main()
