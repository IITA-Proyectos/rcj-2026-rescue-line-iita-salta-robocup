# -*- coding: utf-8 -*-
"""
QUE MIRA CADA LEY. La pregunta de Benjamin, 25-ago:

    "el robot gira en base a start? o al punto de mas arriba de start? o en
     base a la cruz con circulo verde?"

La respuesta corta, y no es obvia mirando el video porque el registro dibuja
TODO junto:

    LA LEY DE HOY MIRA UN SOLO PUNTO: la X.
        angle = -90 * (x_target - CENTER) / (W/2)
    Ni el start, ni la entrada, ni el arco. Un numero, de una columna.

    STANLEY NO MIRA LA X EN ABSOLUTO.
        delta = -g * ( psi + atan(k*e/v) )
    `e` sale del CUADRADO (entrada) y `psi` de la LINEA CELESTE. La X no entra.

O sea que las dos leyes no discrepan por como pesan lo mismo: discrepan porque
LEEN COSAS DISTINTAS DE LA MISMA IMAGEN.

Este script arma la figura de dos paneles que lo muestra, eligiendo un frame
donde la divergencia es maxima por construccion: la cinta pasa centrada bajo el
robot -asi que no hay error de posicion- pero el target esta lejos del centro.

    python que_mira_cada_ley.py
"""

import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

ESC = 6
K, G = 6.1328, 0.6406
F = cv2.FONT_HERSHEY_SIMPLEX
BLANCO = (245, 245, 245)
GRIS = (110, 110, 110)
CIAN = (255, 220, 90)
MAGENTA = (230, 120, 235)
VERDE = (110, 230, 120)
NARANJA = (60, 170, 255)
APAGA = (55, 55, 55)


def txt(img, s, x, y, col=BLANCO, esc=0.5, gr=1):
    cv2.putText(img, s, (x, y), F, esc, col, gr, cv2.LINE_AA)


# Videos donde la cinta se ve COMO cinta. En con_planner2 hay tramos donde la
# mascara agarra el piso oscuro entero y la componente ocupa medio cuadro: el
# frame es valido para el algoritmo pero no sirve para explicar nada.
PREFERIDOS = ("hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi")


def elegir(datos):
    """Frame donde la cinta pasa CENTRADA bajo el robot y el target esta lejos."""
    best = None
    for vid in PREFERIDOS:
        for f in datos.get(vid, []):
            if f["target"] is None or not f.get("entrada"):
                continue
            if f["entrada"][1] < 110:          # la cinta tiene que estar ABAJO
                continue
            c = LS.componentes(f, v_norm=f["factor"], k=K, g=G)
            if c is None:
                continue
            ent = abs(f["entrada"][0] - LS.CENTER)
            tgt = abs(f["target"][0] - LS.CENTER)
            sep = abs(f["start"][0] - f["entrada"][0])
            # el target tiene que estar ARRIBA -si no, no se ve como cinta- y
            # el estado HIGH, para que sea un frame representativo y no un caso
            # degenerado donde la componente ocupa medio cuadro
            if (ent < 10 and tgt > 30 and sep > 15
                    and 50 < f["target"][1] < 85 and f["state"] == "HIGH"):
                sc = tgt + sep
                if best is None or sc > best[0]:
                    best = (sc, vid, f["i"], f, c)
    return best


def base(g, r):
    vis = cv2.resize(g, (LS.W * ESC, LS.H * ESC),
                     interpolation=cv2.INTER_NEAREST)
    vis = (vis * 0.32).astype(np.uint8)
    for m, col, a in ((r.get("comp"), (25, 85, 35), 0.65),
                      (r.get("skel"), (60, 200, 220), 0.35)):
        if m is None:
            continue
        mm = cv2.resize(m, (LS.W * ESC, LS.H * ESC),
                        interpolation=cv2.INTER_NEAREST) > 0
        vis[mm] = (vis[mm] * (1 - a) + np.array(col) * a).astype(np.uint8)
    cv2.line(vis, (int(LS.CENTER * ESC), LS.H * ESC),
             (int(LS.CENTER * ESC), 0), (70, 70, 70), 1)
    return vis


def px(p):
    return (int(p[0] * ESC), int(p[1] * ESC))


def flecha(vis, deg, col, etq):
    """El comando, dibujado como flecha desde la base del robot."""
    o = (int(LS.CENTER * ESC), LS.H * ESC - 30)
    L = 190
    a = math.radians(-deg)          # + es izquierda
    p = (int(o[0] + L * math.sin(a)), int(o[1] - L * math.cos(a)))
    cv2.arrowedLine(vis, o, p, col, 4, cv2.LINE_AA, tipLength=0.22)
    txt(vis, etq, p[0] - 40, p[1] - 12, col, 0.55, 2)


def main():
    datos = SP.extraer()
    el = elegir(datos)
    if el is None:
        print("  no se encontro un frame que ilustre")
        return 1
    _sc, vid, i, f, c = el
    print("  %s f%d" % (vid, i))
    print("   entrada %s   start %s   target %s"
          % (f["entrada"], f["start"], f["target"]))
    viejo = LS.steer_actual(f)
    print("   LEY DE HOY %+.1f     STANLEY %+.1f" % (viejo, c["delta"]))

    vl, v2 = SP._produccion()
    vl._tr = None
    vl._arrancar()
    cap = cv2.VideoCapture(os.path.join(AQUI, vid))
    r = g = None
    k = 0
    while k <= i:
        ok, fr = cap.read()
        if not ok:
            break
        g = v2.frame_pi(fr)
        r = vl._tr.step(g)
        k += 1
    cap.release()

    W = LS.W * ESC
    H = LS.H * ESC
    izq = base(g, r)
    der = base(g, r)

    # ---- IZQUIERDA: lo que mira la ley de HOY ----------------------------
    for p in (f["entrada"], f["start"]):
        cv2.circle(izq, px(p), 6, APAGA, 1)
    t = px(f["target"])
    cv2.drawMarker(izq, t, BLANCO, cv2.MARKER_TILTED_CROSS, 30, 3)
    cv2.circle(izq, t, 18, VERDE, 2)
    cv2.line(izq, (t[0], t[1]), (t[0], H), (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(izq, (int(LS.CENTER * ESC), H - 40), (t[0], H - 40), BLANCO, 2)
    txt(izq, "%.0f px" % abs(f["target"][0] - LS.CENTER),
        min(t[0], int(LS.CENTER * ESC)) + 20, H - 50, BLANCO, 0.5)
    flecha(izq, viejo, BLANCO, "%+.0f" % viejo)

    # ---- DERECHA: lo que mira STANLEY ------------------------------------
    cv2.drawMarker(der, px(f["target"]), APAGA, cv2.MARKER_TILTED_CROSS, 30, 2)
    e = px(f["entrada"])
    cv2.drawMarker(der, e, MAGENTA, cv2.MARKER_SQUARE, 20, 3)
    cv2.line(der, (int(LS.CENTER * ESC), e[1]), e, MAGENTA, 2)
    txt(der, "e = %+.3f" % c["e"], e[0] + 16, e[1] + 6, MAGENTA, 0.5)
    path = r.get("path") or []
    if len(path) >= 2:
        P = [LS.suelo(x, y) for x, y in path]
        ac, j = 0.0, 0
        for q in range(1, len(P)):
            ac += math.hypot(P[q][0] - P[q - 1][0], P[q][1] - P[q - 1][1])
            j = q
            if ac >= LS.ARCO_PSI:
                break
        cv2.line(der, px(f["start"]), px(path[j]), CIAN, 3, cv2.LINE_AA)
        cv2.circle(der, px(path[j]), 8, CIAN, 2)
        txt(der, "psi = %+.1f" % c["psi"], px(path[j])[0] + 14,
            px(path[j])[1], CIAN, 0.5)
    flecha(der, c["delta"], CIAN, "%+.0f" % c["delta"])

    for v, tit, sub in ((izq, "LA LEY DE HOY MIRA UN SOLO PUNTO",
                         "angle = -90 * (x_target - centro) / 80"),
                        (der, "STANLEY NO MIRA ESE PUNTO",
                         "delta = -g * ( psi + atan(k*e/v) )")):
        cv2.rectangle(v, (0, 0), (W, 56), (0, 0, 0), -1)
        txt(v, tit, 12, 24, BLANCO, 0.6, 2)
        txt(v, sub, 12, 46, GRIS, 0.48)

    sep = np.full((H, 4, 3), 60, np.uint8)
    out = np.hstack([izq, sep, der])
    pie = np.full((70, out.shape[1], 3), 18, np.uint8)
    txt(pie, "%s  f%d   -   la cinta pasa CENTRADA bajo el robot (e = %+.3f), "
             "y sin embargo la ley de hoy pide %+.0f" % (vid, i, c["e"], viejo),
        14, 26, BLANCO, 0.52)
    txt(pie, "Las dos leyes no pesan distinto lo mismo: LEEN COSAS DISTINTAS "
             "de la misma imagen.", 14, 52, GRIS, 0.5)
    out = np.vstack([out, pie])
    ruta = os.path.join(AQUI, "QUE_MIRA_CADA_LEY.png")
    cv2.imwrite(ruta, out)
    print("  escrito %s  (%dx%d)" % (ruta, out.shape[1], out.shape[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
