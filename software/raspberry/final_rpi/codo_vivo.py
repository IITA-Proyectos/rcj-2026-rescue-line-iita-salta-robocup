# -*- coding: utf-8 -*-
"""EL DETECTOR DE CODO EN VIVO, y VOS marcas cuando hay codo. Con la L dibujada.

Benjamin, 26-ago: "yo tambien tendria que apretar cuando es un codo, con el
espacio si se puede".

ESO CIERRA EL EXPERIMENTO. Vos marcas la verdad, el detector marca lo que cree,
y al final sale PRECISION y RECALL sin que nadie tenga que interpretar nada:

    verdadero positivo  disparo del detector con una marca tuya cerca
    falso positivo      disparo sin marca  -> ve codos donde no hay
    falso negativo      marca sin disparo  -> se pierde codos que hay

TECLAS (con la ventana en foco, por VNC)
    ESPACIO   "ACA HAY UN CODO"      <- lo marcas vos
    g         guardar una foto de este frame, dispare o no
    +  /  -   subir o bajar el umbral en vivo
    ESC       salir y mostrar el resultado

QUE SE VE
    amarillo  la cadena que eligio CAMINO
    circulo   el vertice
    L         los DOS BRAZOS son las dos rectas ajustadas a la cadena. La
              APERTURA DE LA L ES EL ANGULO MEDIDO: si el detector se equivoca,
              la L se ve torcida contra la cinta y se nota mirando.
              verde = no dispara   rojo = CODO
    barra     el angulo 0-90, con la marca blanca en el umbral
    ang       la CERRADA del codo   -> cuanto habria que girar
    npts      el largo de la cadena -> la LEJANIA, o sea cuando

NO toca main.py, NO abre el puerto serie, NO mueve un motor. El robot puede
estar apagado: se lo pasea a mano.

    python3 codo_vivo.py
    python3 codo_vivo.py --umbral 35

Deja codos_vivo/sesion.csv con todo, y las fotos de cada disparo y cada marca.
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
ESC_VIS = 4
TOL = 1.5          # s de tolerancia para aparear una marca con un disparo


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


def pintar(f160, m, dispara, umbral, marcado, n_marcas, n_disp):
    W, H = 160 * ESC_VIS, 120 * ESC_VIS
    vis = cv2.resize(f160, (W, H), interpolation=cv2.INTER_NEAREST)
    vis = (vis * 0.55).astype(np.uint8)
    if m:
        for p, q in zip(m["P"], m["P"][1:]):
            cv2.line(vis, (int(p[0] * ESC_VIS), int(p[1] * ESC_VIS)),
                     (int(q[0] * ESC_VIS), int(q[1] * ESC_VIS)), (0, 220, 255), 2)
        col = (0, 0, 255) if dispara else (0, 255, 0)
        v = m["vert"] * ESC_VIS
        for d in (m["d1"], m["d2"]):
            p2 = v + d * (36 * ESC_VIS)
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
        cv2.rectangle(vis, (x0, y0),
                      (x0 + int((x1 - x0) * min(m["ang"], 90) / 90.0), y0 + 16), col, -1)
        xu = x0 + int((x1 - x0) * umbral / 90.0)
        cv2.line(vis, (xu, y0 - 4), (xu, y0 + 20), (255, 255, 255), 2)
    else:
        for c, g in (((0, 0, 0), 5), ((150, 150, 150), 2)):
            cv2.putText(vis, "sin cadena", (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, c, g)

    if marcado:                                     # flash al apretar espacio
        cv2.rectangle(vis, (0, 0), (W - 1, H - 1), (255, 255, 0), 14)
        for c, g in (((0, 0, 0), 8), ((255, 255, 0), 4)):
            cv2.putText(vis, "MARCADO", (W // 2 - 150, H // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.6, c, g)

    hud = "ESPACIO=hay codo   g=foto   +/-=umbral %.0f   ESC=salir" % umbral
    for c, g in (((0, 0, 0), 4), ((230, 230, 230), 1)):
        cv2.putText(vis, hud, (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.48, c, g)
    cnt = "marcas %d   disparos %d" % (n_marcas, n_disp)
    for c, g in (((0, 0, 0), 4), ((255, 255, 0), 1)):
        cv2.putText(vis, cnt, (10, H - 44), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, g)
    return vis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--umbral", type=float, default=45.0)
    ap.add_argument("--res", type=float, default=2.0)
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--dir", default="codos_vivo")
    ap.add_argument("--cooldown", type=float, default=1.2,
                    help="s minimos entre dos disparos, para contar EVENTOS y no frames")
    a = ap.parse_args()

    os.environ.setdefault("VISION_LINEA", "camino")
    sys.path.insert(0, AQUI)
    try:
        import vision_linea as VL
    except Exception as e:
        sys.exit("no pude importar vision_linea (%s)" % e)
    if not VL.ACTIVA:
        sys.exit("vision_linea dice ACTIVA=False")

    os.makedirs(a.dir, exist_ok=True)
    cap = cv2.VideoCapture(a.cam)
    if not cap.isOpened():
        sys.exit("no pude abrir la camara %d" % a.cam)

    csv = open(os.path.join(a.dir, "sesion.csv"), "w")
    csv.write("t,frame,ang,npts,res_c,res_l,dispara,marca_humana\n")

    print("ESPACIO = hay codo   |   g = foto   |   +/- = umbral   |   ESC = salir")
    print("Pasea el robot A MANO. Marca con ESPACIO cada vez que veas un codo.\n")

    t0 = time.time()
    umbral = a.umbral
    n = 0
    marcas, disparos = [], []
    ult_disp = -9.0
    t_flash = -9.0
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

            t = time.time() - t0
            dispara = bool(m and m["ang"] >= umbral and m["r1"] <= a.res and m["r2"] <= a.res)
            nuevo = dispara and (t - ult_disp) >= a.cooldown
            if nuevo:
                ult_disp = t
                disparos.append(t)

            vis = pintar(f, m, dispara, umbral, (t - t_flash) < 0.35,
                         len(marcas), len(disparos))
            cv2.imshow("codo", vis)
            k = cv2.waitKey(1) & 0xFF

            marca = 0
            if k == 32:                                   # ESPACIO
                marcas.append(t)
                t_flash = t
                marca = 1
                cv2.imwrite("%s/MARCA_%03d_t%05.1f.png" % (a.dir, len(marcas), t), vis)
                print("  MARCA %d  t=%5.1f s   (detector: %s, ang=%s)"
                      % (len(marcas), t, "CODO" if dispara else "nada",
                         "%.0f" % m["ang"] if m else "-"))
            elif k == ord('g'):
                cv2.imwrite("%s/FOTO_t%05.1f.png" % (a.dir, t), vis)
                print("  foto guardada t=%.1f" % t)
            elif k in (ord('+'), ord('=')):
                umbral = min(90.0, umbral + 5)
            elif k == ord('-'):
                umbral = max(5.0, umbral - 5)
            elif k == 27:                                 # ESC
                break

            if nuevo:
                cv2.imwrite("%s/CODO_%03d_ang%02d.png"
                            % (a.dir, len(disparos), int(m["ang"])), vis)
                print("  detector: CODO %d  t=%5.1f s  ang=%2.0f  npts=%3d"
                      % (len(disparos), t, m["ang"], m["npts"]))

            csv.write("%.3f,%d,%s,%s,%s,%s,%d,%d\n"
                      % (t, n,
                         "%.1f" % m["ang"] if m else "",
                         "%d" % m["npts"] if m else "",
                         "%.2f" % m["r1"] if m else "",
                         "%.2f" % m["r2"] if m else "",
                         1 if dispara else 0, marca))
            n += 1
    except KeyboardInterrupt:
        pass
    cap.release()
    cv2.destroyAllWindows()
    csv.close()

    # ---------------- el resultado, apareando marcas con disparos -------------
    print("\n" + "=" * 62)
    print("RESULTADO   umbral %.0f grados, residuo <= %.1f px" % (umbral, a.res))
    print("  %d frames, %.1f s" % (n, time.time() - t0))
    print("  marcas tuyas: %d      disparos del detector: %d" % (len(marcas), len(disparos)))
    if not marcas:
        print("\n  No marcaste ningun codo: sin verdad de campo no hay veredicto.")
        return
    usados = set()
    tp = 0
    for mt in marcas:
        cand = [(abs(dt - mt), i) for i, dt in enumerate(disparos)
                if i not in usados and abs(dt - mt) <= TOL]
        if cand:
            cand.sort()
            usados.add(cand[0][1])
            tp += 1
    fp = len(disparos) - len(usados)
    fn = len(marcas) - tp
    print("\n  apareado con tolerancia de %.1f s:" % TOL)
    print("    aciertos (TP)          %d" % tp)
    print("    falsos positivos (FP)  %d   <- vio codo donde no marcaste" % fp)
    print("    se le escaparon (FN)   %d   <- marcaste y no disparo" % fn)
    if tp + fp:
        print("\n    PRECISION  %.0f %%   de lo que dispara, cuanto es codo de verdad"
              % (100.0 * tp / (tp + fp)))
    if tp + fn:
        print("    RECALL     %.0f %%   de los codos que hay, cuantos agarra"
              % (100.0 * tp / (tp + fn)))
    print("\n  Todo en %s/sesion.csv" % a.dir)


if __name__ == "__main__":
    main()
