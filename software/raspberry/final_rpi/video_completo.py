# -*- coding: utf-8 -*-
"""
VIDEO COMPLETO - los 10 autonomos seguidos, con TODO el pipeline corriendo.

13.900 frames, ~6 min 57 s a 33,3 fps. Es todo el material autonomo que hay.

QUE SE VE, y todo sale del MISMO paso de vision, no de una reconstruccion:

  izquierda   el frame real con la mascara, la componente elegida, el esqueleto,
              el camino que Dijkstra reconstruyo, y las TRES etapas del target
              (geometrico -> guard de rama -> final) dibujadas por separado para
              que se vea cual guard lo movio

  derecha     el estado de la candidata, la razon del planificador, la
              anticipacion de curva, y la ley de steer ABIERTA en sus dos
              terminos: cuanto pide por POSICION y cuanto por RUMBO

  abajo       los ultimos 10 s de comando, con las DOS leyes superpuestas:
              la de hoy en gris y Stanley en color. Es la comparacion que el
              defecto 3.5.1 pedia poder mirar

LO QUE ESTE VIDEO NO ES: una simulacion. Es replay open-loop. El robot de la
imagen se movio obedeciendo a la ley VIEJA; la curva de Stanley es lo que
habria pedido en ese mismo frame, no la trayectoria que habria hecho.

    python video_completo.py                       # los 10, salida por defecto
    python video_completo.py --videos hist.avi     # uno solo
    python video_completo.py --salida x.mp4 --fps 33.3
"""

import argparse
import importlib.util
import math
import os
import sys
from collections import deque

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402

W, H = 160, 120
ESC = 5                                   # 160x120 -> 800x600
PW, PH = 800, 600                         # panel de imagen
LW = 480                                  # panel de datos
SH = 120                                  # tira de tiempo
OUT_W, OUT_H = PW + LW, PH + SH           # 1280 x 720
TIRA = 320                                # ~10 s de historia a 33,3 fps

AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]

F = cv2.FONT_HERSHEY_SIMPLEX
GRIS = (150, 150, 150)
BLANCO = (245, 245, 245)
CIAN = (255, 220, 90)
NARANJA = (60, 170, 255)
VERDE = (110, 230, 120)
ROJO = (90, 90, 245)
AMARILLO = (60, 235, 255)
MAGENTA = (230, 120, 235)


def txt(img, s, x, y, col=BLANCO, esc=0.42, gr=1):
    cv2.putText(img, s, (x, y), F, esc, col, gr, cv2.LINE_AA)


def contar(ruta):
    """Frames REALES. CAP_PROP_FRAME_COUNT miente en estos avi -da 154 para un
    video de 461-, y `grab()` no decodifica, asi que contar es barato."""
    cap = cv2.VideoCapture(ruta)
    n = 0
    while cap.grab():
        n += 1
    cap.release()
    return n


def cargar_vl():
    """vision_linea con CAMINO+MONO y la ley nueva encendida."""
    os.environ["VISION_LINEA"] = "camino"
    os.environ["LEY_STEER"] = "stanley"
    sys.modules.pop("vision_linea", None)
    sp = importlib.util.spec_from_file_location(
        "vision_linea", os.path.join(AQUI, "vision_linea.py"))
    vl = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(vl)
    return vl


# --------------------------------------------------------------------------
def pintar_imagen(g, r, u):
    """El frame con las capas de percepcion encima."""
    vis = cv2.resize(g, (PW, PH), interpolation=cv2.INTER_NEAREST)
    vis = (vis * 0.40).astype(np.uint8)

    def cap(m, color, alpha):
        if m is None:
            return
        mm = cv2.resize(m, (PW, PH), interpolation=cv2.INTER_NEAREST) > 0
        vis[mm] = (vis[mm] * (1 - alpha) + np.array(color) * alpha).astype(np.uint8)

    cap(r.get("mask"), (70, 70, 70), 0.45)
    cap(r.get("comp"), (30, 105, 40), 0.65)
    cap(r.get("skel"), AMARILLO, 0.95)

    # eje del robot
    cv2.line(vis, (int(LS.CENTER * ESC), PH), (int(LS.CENTER * ESC), 0),
             (70, 70, 70), 1)

    # camino reconstruido
    path = r.get("path") or []
    if len(path) >= 2:
        q = np.asarray([[int(x * ESC), int(y * ESC)] for x, y in path], np.int32)
        cv2.polylines(vis, [q], False, NARANJA, 2, cv2.LINE_AA)

    st = r.get("start")
    if st:
        cv2.circle(vis, (int(st[0] * ESC), int(st[1] * ESC)), 7, (245, 130, 40), -1)
        txt(vis, "start", int(st[0] * ESC) + 10, int(st[1] * ESC) + 4,
            (245, 160, 90), 0.38)

    # ENTRADA: donde esta la CINTA bajo el robot, que es de donde sale `e`.
    # Es distinto del `start` -que es un nodo del esqueleto- y la diferencia
    # entre los dos es el defecto que encontro Benjamin mirando este video:
    # p50 14 px, p90 35, max 152.
    ent = r.get("entrada")
    if ent:
        px = (int(ent[0] * ESC), int(ent[1] * ESC) - 6)
        cv2.drawMarker(vis, px, MAGENTA, cv2.MARKER_SQUARE, 14, 2)
        txt(vis, "entrada (e)", px[0] + 10, px[1] + 4, MAGENTA, 0.38)
        if math.hypot(ent[0] - st[0], ent[1] - st[1]) > 3:
            cv2.line(vis, px, (int(st[0] * ESC), int(st[1] * ESC)),
                     MAGENTA, 1)

    # LAS CINCO ETAPAS:  raw -> cap -> geo -> bra -> tg
    # Cada una se dibuja SOLO si movio el punto respecto de la anterior, y se
    # une con una linea roja. Asi se ve de un vistazo QUE guard lo movio, que es
    # justo lo que un log de cuatro columnas no permitia clasificar.
    etapas = [("raw", r.get("target_raw"), VERDE, 13),
              ("cap", r.get("target_cap"), AMARILLO, 11),
              ("low", r.get("target_geometric"), NARANJA, 9),
              ("rama", r.get("target_branch"), MAGENTA, 7)]
    fin = r.get("target")
    ant = None
    movio = []
    for et, pt, col, rad in etapas:
        if pt is None:
            continue
        if ant is None or math.hypot(pt[0] - ant[0], pt[1] - ant[1]) > 0.5:
            if ant is not None:
                cv2.line(vis, (int(ant[0] * ESC), int(ant[1] * ESC)),
                         (int(pt[0] * ESC), int(pt[1] * ESC)), ROJO, 1)
                movio.append(et)
            cv2.circle(vis, (int(pt[0] * ESC), int(pt[1] * ESC)), rad, col, 2)
        ant = pt
    if fin:
        p = (int(fin[0] * ESC), int(fin[1] * ESC))
        if ant is not None and math.hypot(fin[0] - ant[0], fin[1] - ant[1]) > 0.5:
            cv2.line(vis, (int(ant[0] * ESC), int(ant[1] * ESC)), p, ROJO, 1)
            movio.append("spatial")
        cv2.drawMarker(vis, p, BLANCO, cv2.MARKER_TILTED_CROSS, 22, 2)
    if movio:
        txt(vis, "lo movio: " + " + ".join(movio), 10, 22, ROJO, 0.44)

    # el arco sobre el que se mide la tangente (psi)
    if st and len(path) >= 2:
        P = [LS.suelo(x, y) for x, y in path]
        acum, j = 0.0, 0
        for i in range(1, len(P)):
            acum += math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1])
            j = i
            if acum >= LS.ARCO_PSI:
                break
        pj = path[j]
        cv2.line(vis, (int(st[0] * ESC), int(st[1] * ESC)),
                 (int(pj[0] * ESC), int(pj[1] * ESC)), CIAN, 2, cv2.LINE_AA)
        cv2.circle(vis, (int(pj[0] * ESC), int(pj[1] * ESC)), 6, CIAN, 2)

    # leyenda: sin esto los circulos son adornos
    # Arriba a la DERECHA: es la zona de fondo lejano, la unica del cuadro
    # donde nunca hay cinta. Abajo a la izquierda tapaba los targets cuando la
    # linea queda al ras del borde inferior, que es justo cuando importa mirar.
    x0 = PW - 372
    sub = vis[0:96, x0:PW]
    vis[0:96, x0:PW] = (sub * 0.25).astype(np.uint8)
    txt(vis, "camino de Dijkstra", x0 + 10, 18, NARANJA, 0.38)
    txt(vis, "arco donde se mide psi", x0 + 10, 34, CIAN, 0.38)
    txt(vis, "cuadrado = entrada: de ahi sale e", x0 + 190, 18,
        MAGENTA, 0.36)
    txt(vis, "las CINCO etapas del target, en orden:", x0 + 10, 52, GRIS, 0.36)
    for k, (et, col) in enumerate((("raw", VERDE), ("cap", AMARILLO),
                                   ("low", NARANJA), ("rama", MAGENTA))):
        cv2.circle(vis, (x0 + 18 + k * 66, 70), 6, col, 2)
        txt(vis, et, x0 + 28 + k * 66, 74, col, 0.36)
    cv2.drawMarker(vis, (x0 + 18 + 4 * 66, 70), BLANCO,
                   cv2.MARKER_TILTED_CROSS, 13, 2)
    txt(vis, "final", x0 + 28 + 4 * 66, 74, BLANCO, 0.36)
    txt(vis, "solo se dibuja la etapa que MOVIO el punto", x0 + 10, 90,
        GRIS, 0.34)
    return vis


def barra(img, x, y, w, h, v, vmax, col, etiqueta):
    """Barra bipolar centrada, para un valor en [-vmax, vmax]."""
    cv2.rectangle(img, (x, y), (x + w, y + h), (55, 55, 55), 1)
    cx = x + w // 2
    cv2.line(img, (cx, y), (cx, y + h), (85, 85, 85), 1)
    f = max(-1.0, min(1.0, v / float(vmax)))
    px = int(cx + f * (w // 2 - 2))
    if px >= cx:
        cv2.rectangle(img, (cx, y + 2), (px, y + h - 2), col, -1)
    else:
        cv2.rectangle(img, (px, y + 2), (cx, y + h - 2), col, -1)
    txt(img, etiqueta, x, y - 4, GRIS, 0.36)


def pintar_datos(vid, i, n, r, u, ang, vel_base, vel, prog):
    p = np.full((PH, LW, 3), 22, np.uint8)
    cv2.line(p, (0, 0), (0, PH), (55, 55, 55), 1)
    y = 26
    txt(p, "%s   f%d / %d" % (vid, i, n - 1), 14, y, BLANCO, 0.50, 1)
    y += 20
    txt(p, "autonomo %d de %d   -   %d:%02d de %d:%02d"
        % (prog[0], prog[1], prog[2] // 60, prog[2] % 60,
           prog[3] // 60, prog[3] % 60), 14, y, GRIS, 0.38)
    y += 8
    cv2.rectangle(p, (14, y), (LW - 14, y + 5), (55, 55, 55), 1)
    if prog[3]:
        cv2.rectangle(p, (15, y + 1),
                      (15 + int((LW - 30) * prog[2] / float(prog[3])), y + 4),
                      CIAN, -1)
    y += 18
    txt(p, "VISION_LINEA=camino   LEY_STEER=stanley", 14, y, GRIS, 0.36)

    y += 30
    cv2.line(p, (14, y), (LW - 14, y), (55, 55, 55), 1)
    y += 20
    txt(p, "PERCEPCION", 14, y, CIAN, 0.44)
    y += 22
    txt(p, "estado    %s" % (u.get("estado") or "--"), 22, y)
    y += 19
    txt(p, "razon     %s" % (u.get("razon") or "--"), 22, y)
    y += 19
    txt(p, "guard     %s" % (u.get("spatial") or "--"), 22, y)
    y += 19
    sal = u.get("salto")
    txt(p, "salto     %s px  (lo que el target QUERIA saltar)"
        % ("--" if sal is None else "%.1f" % sal), 22, y, GRIS, 0.38)
    y += 19
    tg = u.get("target")
    txt(p, "target    %s" % ("--" if tg is None else
                             "(%.1f, %.1f)" % (tg[0], tg[1])), 22, y)

    y += 28
    cv2.line(p, (14, y), (LW - 14, y), (55, 55, 55), 1)
    y += 20
    txt(p, "ANTICIPACION DE CURVA   (APAGADA en produccion)", 14, y,
        CIAN, 0.40)
    y += 22
    k = u.get("kappa")
    txt(p, "curvatura %s   (umbral %.1f)"
        % ("--" if k is None else "%.1f" % k, 139.5), 22, y)
    y += 22
    fv = u.get("factor_vel", 1.0)
    cv2.rectangle(p, (22, y - 10), (22 + 240, y + 4), (55, 55, 55), 1)
    cv2.rectangle(p, (24, y - 8), (24 + int(236 * min(1.0, fv)), y + 2),
                  VERDE if fv >= 0.999 else NARANJA, -1)
    txt(p, "vel %d -> %d  (x%.2f)" % (vel_base, vel, fv), 272, y, BLANCO, 0.38)

    y += 32
    cv2.line(p, (14, y), (LW - 14, y), (55, 55, 55), 1)
    y += 20
    txt(p, "LEY DE STEER   -   los dos errores, separados", 14, y, CIAN, 0.44)
    y += 24
    e = u.get("e_pos")
    ps = u.get("psi")
    txt(p, "e    %s        cross-track en el suelo"
        % ("  --  " if e is None else "%+.3f" % e), 22, y, BLANCO, 0.40)
    y += 19
    txt(p, "psi  %s deg    rumbo de la tangente"
        % ("  --  " if ps is None else "%+6.1f" % ps), 22, y, BLANCO, 0.40)
    y += 19
    txt(p, "v    %5.2f        divide SOLO al termino de posicion"
        % u.get("factor_vel", 1.0), 22, y, GRIS, 0.38)

    y += 26
    tp, tq = u.get("t_pos"), u.get("t_psi")
    barra(p, 22, y, 200, 16, tp or 0.0, 90.0, NARANJA, "POSICION")
    txt(p, "  --  " if tp is None else "%+6.1f" % tp, 232, y + 13, NARANJA, 0.42)
    barra(p, 22, y + 30, 200, 16, tq or 0.0, 90.0, VERDE, "RUMBO")
    txt(p, "  --  " if tq is None else "%+6.1f" % tq, 232, y + 43, VERDE, 0.42)

    y += 54
    cv2.line(p, (14, y), (LW - 14, y), (55, 55, 55), 1)
    y += 20
    av = u.get("ang_viejo")
    barra(p, 22, y, 300, 20, av or 0.0, 90.0, GRIS, "LEY DE HOY")
    txt(p, "  --  " if av is None else "%+6.1f" % av, 332, y + 16, GRIS, 0.46)
    y += 38
    barra(p, 22, y, 300, 20, ang or 0.0, 90.0, CIAN, "STANLEY  (es la que sale)")
    txt(p, "  --  " if ang is None else "%+6.1f" % ang, 332, y + 16, CIAN, 0.46)
    y += 28
    if ang is not None and av is not None:
        d = ang - av
        txt(p, "diferencia %+.1f deg" % d, 22, y,
            ROJO if abs(d) > 20 else GRIS, 0.42)
    if u.get("ley") == "cae_a_vieja":
        txt(p, "sin rumbo: cae a la ley de hoy", 22, y + 18, NARANJA, 0.38)
    return p


def pintar_tira(hist):
    t = np.full((SH, OUT_W, 3), 18, np.uint8)
    cv2.line(t, (0, 0), (OUT_W, 0), (55, 55, 55), 1)
    mid = SH // 2
    for v, col in ((0, (60, 60, 60)), (45, (40, 40, 40)), (-45, (40, 40, 40))):
        yy = int(mid - v / 90.0 * (mid - 8))
        cv2.line(t, (0, yy), (OUT_W, yy), col, 1)
    if len(hist) >= 2:
        dx = OUT_W / float(TIRA)
        for serie, col, gr in ((0, (185, 185, 185), 2), (1, CIAN, 2)):
            pts = []
            for j, h in enumerate(hist):
                v = h[serie]
                if v is None:
                    continue
                pts.append([int(j * dx), int(mid - v / 90.0 * (mid - 8))])
            if len(pts) >= 2:
                cv2.polylines(t, [np.asarray(pts, np.int32)], False, col, gr,
                              cv2.LINE_AA)
    txt(t, "ultimos 10 s del comando", 12, 16, GRIS, 0.38)
    txt(t, "ley de hoy", OUT_W - 230, 16, GRIS, 0.40)
    txt(t, "Stanley", OUT_W - 110, 16, CIAN, 0.40)
    txt(t, "+90", 4, 14, (80, 80, 80), 0.32)
    txt(t, "-90", 4, SH - 6, (80, 80, 80), 0.32)
    return t


def portada(vid, k, total):
    f = np.full((OUT_H, OUT_W, 3), 16, np.uint8)
    txt(f, vid, OUT_W // 2 - 130, OUT_H // 2 - 10, BLANCO, 1.4, 2)
    txt(f, "autonomo %d de %d" % (k, total), OUT_W // 2 - 90,
        OUT_H // 2 + 34, GRIS, 0.6)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", default=None,
                    help="lista separada por comas; por defecto los 10")
    ap.add_argument("--salida", default="REGISTRO_COMPLETO.mp4")
    ap.add_argument("--fps", type=float, default=100.0 / 3.0)
    ap.add_argument("--vel-base", type=int, default=50)
    a = ap.parse_args()

    videos = [v.strip() for v in a.videos.split(",")] if a.videos else AUTONOMOS
    videos = [v for v in videos if os.path.exists(os.path.join(AQUI, v))]

    vl = cargar_vl()
    ruta = os.path.join(AQUI, a.salida)
    vw = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*"mp4v"), a.fps,
                         (OUT_W, OUT_H))
    if not vw.isOpened():
        ruta = ruta.rsplit(".", 1)[0] + ".avi"
        vw = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*"XVID"), a.fps,
                             (OUT_W, OUT_H))
        if not vw.isOpened():
            print("  no se pudo abrir el VideoWriter")
            return 1
    print("  escribiendo %s  (%dx%d @ %.1f fps)" % (ruta, OUT_W, OUT_H, a.fps))
    cuentas = {v: contar(os.path.join(AQUI, v)) for v in videos}
    gran = sum(cuentas.values())
    print("  %d frames en total, %d:%02d de video"
          % (gran, int(gran / a.fps) // 60, int(gran / a.fps) % 60))

    total = 0
    for k, vid in enumerate(videos, 1):
        # tracker fresco por video: el estado se arrastra
        vl._tr = None
        vl._arrancar()
        cap = cv2.VideoCapture(os.path.join(AQUI, vid))
        n = cuentas[vid]
        hist = deque(maxlen=TIRA)
        port = portada(vid, k, len(videos))
        for _ in range(int(a.fps * 0.8)):
            vw.write(port)
        hechos = total      # frames de los videos ANTERIORES; `total` sigue
        i = 0               # creciendo adentro del lazo y contaria doble
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            g = vl._v2.frame_pi(fr)
            # UN solo paso de vision: el dict crudo y el angulo salen de aca
            r = vl._tr.step(g)
            vl._NFRAME += 1
            t = r.get("target")
            vl._ULT.clear()
            vl._ULT.update(estado=r.get("state"), target=t,
                           geom=r.get("target_geometric"),
                           branch=r.get("target_branch"),
                           spatial=r.get("spatial_guard"),
                           salto=r.get("proposed_jump_px"),
                           razon=r.get("reason"), modo=vl._modo_real,
                           inicio=r.get("start"), rumbo_chord=r.get("heading"),
                           raw=r.get("target_raw"), cap=r.get("target_cap"))
            ang = None if t is None else vl._ley(r)
            fv = vl._factor_velocidad()
            vel = int(round(a.vel_base * fv))
            u = vl.ultimo()
            hist.append((u.get("ang_viejo"), ang))

            marco = np.zeros((OUT_H, OUT_W, 3), np.uint8)
            marco[:PH, :PW] = pintar_imagen(g, r, u)
            marco[:PH, PW:] = pintar_datos(
                vid, i, n, r, u, ang, a.vel_base, vel,
                (k, len(videos), int((hechos + i) / a.fps), int(gran / a.fps)))
            marco[PH:, :] = pintar_tira(hist)
            vw.write(marco)
            i += 1
            total += 1
        cap.release()
        print("  %-18s %6d frames" % (vid, i))
    vw.release()
    seg = total / a.fps
    print("")
    print("  %d frames   %d:%02d   %s" % (total, int(seg // 60), int(seg % 60),
                                          ruta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
