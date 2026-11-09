# -*- coding: utf-8 -*-
"""
DUPLEX - PURE PURSUIT contra STANLEY, sobre los MISMOS frames.

QUE ES ESTE VIDEO, Y QUE NO ES
------------------------------
Las dos leyes que el equipo tiene implementadas, corriendo lado a lado sobre
la misma observacion. Es REPLAY EN LAZO ABIERTO: el video contiene el futuro
que genero la ley VIEJA manejando el robot. Sirve para ver QUE PIDE cada ley
sobre lo mismo. NO puede decir cual maneja mejor: eso es prueba de robot.

Y una aclaracion que el video repite en placa, porque es la confusion mas
facil de cometer: LAS DOS NO COMPITEN. Resuelven mitades distintas del lazo.

    PURE PURSUIT  ->  QUE PUNTO perseguir      (seleccion de target)
                      MONO  = busqueda monotona hacia adelante (Coulter 1992)
                      SUELO = lookahead en unidades del suelo  (Snider 2009)

    STANLEY       ->  COMO convertir el camino en comando   (ley de steer)
                      delta = -g*( k_psi*psi + atan(k*e/v) )

Por eso el panel de abajo muestra CUATRO comandos sobre el mismo frame:

    HOY            perception base  + ley de hoy      <- lo que corre
    PURE PURSUIT   perception PP    + ley de hoy
    STANLEY        perception base  + ley Stanley
    PP + STANLEY   perception PP    + ley Stanley     <- las dos juntas

USO
---
    python3 video_duplex_leyes.py
    python3 video_duplex_leyes.py --salida MI_VIDEO.mp4
    python3 video_duplex_leyes.py --hfov 140      # ver cuanto pesa el HFOV

OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF
"""

import argparse
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import pursuit as P
import ley_steer as LS

FPS = 100.0 / 3.0
E = 3                                   # escala de los paneles de 160x120
FT = cv2.FONT_HERSHEY_SIMPLEX
AVISO = "OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF"

# Parametros de produccion de la ley (vision_linea.py:108-112). NO se eligieron
# para ganar una metrica: `k` por reparto de varianza y `g` para conservar el
# +89 del control positivo.
LEY_K, LEY_G, LEY_KPSI, LEY_ARCO = 6.1328, 0.6406, 1.0, 0.60

# Anticipacion de velocidad (vision_linea.py:54-57). Es lo que le da sentido al
# /v de Stanley: sin esto `v` es constante y el termino de posicion no respira.
KAPPA_REF, FACTOR_MIN = 139.5, 0.55

# Shell del lookahead en unidades de suelo, calibrada en pursuit.py --medir
LD_SUELO = 0.735

C_MASK, C_COMP, C_SKEL = (45, 45, 45), (35, 95, 35), (0, 150, 190)
C_PATH = (255, 170, 60)
C_HOY = (235, 235, 235)                 # blanco
C_PP = (120, 255, 120)                  # verde
C_ST = (255, 220, 90)                   # celeste
C_DUO = (90, 220, 255)                  # amarillo
C_POS = (70, 140, 255)                  # naranja: termino de POSICION
C_PSI = (230, 130, 230)                 # violeta: termino de RUMBO
C_ENT = (255, 90, 200)                  # magenta: la entrada de la cinta
C_EST = {"HIGH": (70, 220, 70), "MEDIUM": (80, 210, 220), "LOW": (0, 160, 255),
         "LOW_FORWARD": (0, 190, 255), "SIN_CERCA": (255, 180, 60),
         "PERDIDA": (80, 80, 255)}

TRAMOS = [
    ("hist.avi", 752, 800,
     "EL CODO: la pata que entra y la que sale apuntan a lados opuestos"),
    ("seguir.avi", 1155, 1215,
     "H10: el baseline se engancha en el pedazo de cinta YA RECORRIDO"),
    ("hist.avi", 1354, 1470,
     "la falla historica"),
    ("lineal.avi", 795, 875,
     "CONTROL POSITIVO: steer +87 correcto y la curva SE COMPLETO. No se toca"),
]


def txt(img, x, y, s, col=(210, 210, 210), esc=0.5, gr=1):
    cv2.putText(img, s, (x, y), FT, esc, col, gr, cv2.LINE_AA)


def curvatura(v2, hfov):
    """Curvatura del camino visible, copiada de vision_linea._curvatura.

    Lee el arbol de Dijkstra que la candidata ACABA de calcular (pursuit.CAP),
    asi que hay que llamarla inmediatamente despues del step correspondiente.
    """
    try:
        cap = P.CAP
        if "dist" not in cap:
            return None
        pts, dist, prev, si = cap["pts"], cap["dist"], cap["prev"], cap["si"]
        fin = np.where(np.isfinite(dist))[0]
        if len(fin) < 8:
            return None
        F = int(fin[int(np.argmax(dist[fin]))])
        cad = v2.reconstruct(prev, si, F)
        if not cad or len(cad) < 8:
            return None
        pts_s = [LS.suelo(pts[i][1], pts[i][0], hfov) for i in cad]
        Q = pts_s[::6] if len(pts_s) >= 18 else pts_s
        if len(Q) < 3:
            return None
        arco, hs = 0.0, []
        for a, b in zip(Q, Q[1:]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz)
            if L < 1e-9:
                continue
            arco += L
            hs.append(math.degrees(math.atan2(dx, dz)))
        if len(hs) < 2 or arco < 1e-9:
            return None
        giro = sum(abs((b - a + 180) % 360 - 180) for a, b in zip(hs, hs[1:]))
        return giro / arco
    except Exception:
        return None


def factor_vel(k):
    if k is None:
        return 1.0
    return 1.0 if k <= KAPPA_REF else max(FACTOR_MIN, min(1.0, KAPPA_REF / k))


def base_panel(v2, r):
    """Mascara, componente, esqueleto y camino, ya escalado."""
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
    big = cv2.resize(vis, (v2.W * E, v2.H * E), interpolation=cv2.INTER_NEAREST)
    cv2.line(big, (int(round(v2.CENTER * E)), 0),
             (int(round(v2.CENTER * E)), v2.H * E - 1), (85, 85, 85), 1)
    return big


def px(p):
    return (int(round(p[0] * E + E // 2)), int(round(p[1] * E + E // 2)))


def cabecera(img, w, s, col):
    cv2.rectangle(img, (0, 0), (w, 26), (0, 0, 0), -1)
    txt(img, 8, 19, s, col, 0.55, 2)


def pie(img, w, h, n):
    """Franja negra al pie del panel, para que la leyenda se lea sobre la mascara."""
    cv2.rectangle(img, (0, h - 18 * n - 6), (w, h), (0, 0, 0), -1)


def panel_pursuit(v2, rb, rp):
    """Que punto elige cada seleccion de target, sobre la misma percepcion."""
    big = base_panel(v2, rp)
    tb, tp = rb.get("target"), rp.get("target")
    if tb is not None:
        cv2.drawMarker(big, px(tb), C_HOY, cv2.MARKER_TILTED_CROSS, 8 * E, 2)
    if tp is not None:
        cv2.drawMarker(big, px(tp), C_PP, cv2.MARKER_CROSS, 10 * E, 2)
    if tb is not None and tp is not None:
        cv2.line(big, px(tb), px(tp), (110, 110, 110), 1)
    st = rp.get("start")
    if st is not None:
        cv2.circle(big, px(st), 4, (255, 130, 40), -1)
    cabecera(big, v2.W * E, "PURE PURSUIT   que punto perseguir", C_PP)
    pie(big, v2.W * E, v2.H * E, 2)
    txt(big, 8, v2.H * E - 24, "x  target de hoy", C_HOY, 0.45, 1)
    txt(big, 8, v2.H * E - 8, "+  target MONO+SUELO", C_PP, 0.45, 1)
    return big


def panel_stanley(v2, rb, comp, hfov):
    """Las dos causas separadas: cuanto viene de POSICION y cuanto de RUMBO."""
    big = base_panel(v2, rb)
    cy = v2.H * E - 1
    ent, st = rb.get("entrada"), rb.get("start")
    cx = int(round(v2.CENTER * E))

    if ent is not None:
        e_px = px(ent)
        # cross-track: del centro del robot al punto donde la cinta ENTRA.
        # La fila 119 cae en el ultimo pixel del panel, asi que la flecha se
        # sube un poco: si no, queda cortada contra el borde y no se ve.
        ey = min(e_px[1], v2.H * E - 62)
        cv2.arrowedLine(big, (cx, ey), (e_px[0], ey), C_POS, 2, tipLength=0.25)
        cv2.circle(big, (e_px[0], ey), 5, C_ENT, -1)
        cv2.line(big, (e_px[0], ey), e_px, (90, 90, 90), 1)
    if st is not None and comp is not None:
        # tangente del camino: el rumbo psi, dibujado desde el start
        s_px = px(st)
        L = 46 * E / 1.0
        a = math.radians(comp["psi"])
        cv2.arrowedLine(big, s_px,
                        (int(s_px[0] + L * math.sin(a)),
                         int(s_px[1] - L * math.cos(a))), C_PSI, 2,
                        tipLength=0.18)
        cv2.circle(big, s_px, 4, (255, 130, 40), -1)
    t = rb.get("target")
    if t is not None:
        cv2.drawMarker(big, px(t), (120, 120, 120), cv2.MARKER_TILTED_CROSS,
                       7 * E, 1)
    cabecera(big, v2.W * E, "STANLEY   posicion + rumbo, por separado", C_ST)
    pie(big, v2.W * E, v2.H * E, 3)
    txt(big, 8, cy - 40, "->  e   cross-track (POSICION)", C_POS, 0.45, 1)
    txt(big, 8, cy - 24, "->  psi tangente    (RUMBO)", C_PSI, 0.45, 1)
    txt(big, 8, cy - 8, "HFOV %.0f  SIN CALIBRAR: psi escala con esto" % hfov,
        (0, 165, 255), 0.42, 1)
    return big


def agujas(img, x0, x1, y, items):
    """Las cuatro agujas, con las etiquetas escalonadas para que no se pisen.

    Cuando dos leyes piden casi lo mismo -que pasa seguido, y es informacion-
    las etiquetas caian una encima de otra y no se leia ninguna.
    """
    puestas = []
    for val, col, etiq in items:
        if val is None:
            continue
        v = max(-90.0, min(90.0, float(val)))
        x = int(x0 + (v + 90.0) / 180.0 * (x1 - x0))
        cv2.line(img, (x, y - 13), (x, y + 13), col, 2)
        cv2.circle(img, (x, y), 4, col, -1)
        (tw, _), _ = cv2.getTextSize(etiq, FT, 0.42, 1)
        tx = min(max(x - tw // 2, x0), x1 - tw)
        fila = 0
        while any(fila == f and not (tx + tw + 6 < a or a + b + 6 < tx)
                  for a, b, f in puestas):
            fila += 1
        puestas.append((tx, tw, fila))
        txt(img, tx, y - 20 - fila * 15, etiq, col, 0.42, 1)


def info(out, v2, meta, rb, comp_b, comp_p, angs, W, H):
    y0 = v2.H * E
    cv2.rectangle(out, (0, y0), (W, H), (14, 14, 14), -1)
    cv2.line(out, (0, y0), (W, y0), (60, 60, 60), 1)

    txt(out, 14, y0 + 30, "%s  f%d" % (meta["video"], meta["frame"]),
        (90, 230, 255), 0.78, 2)
    est = rb.get("state", "?")
    txt(out, 250, y0 + 30, "ESTADO %s" % est, C_EST.get(est, (200, 200, 200)),
        0.62, 2)
    if meta.get("nota"):
        txt(out, 430, y0 + 30, meta["nota"], (155, 155, 155), 0.5, 1)

    # ---- regla de comandos -------------------------------------------------
    gx0, gx1, gy = 100, W - 430, y0 + 100
    txt(out, 14, gy - 26, "COMANDO", (150, 150, 150), 0.46, 1)
    txt(out, 14, gy - 8, "en grados", (95, 95, 95), 0.4, 1)
    txt(out, 14, gy + 12, "- izquierda", (95, 95, 95), 0.4, 1)
    txt(out, 14, gy + 30, "+ derecha", (95, 95, 95), 0.4, 1)
    cv2.line(out, (gx0, gy), (gx1, gy), (80, 80, 80), 1)
    for gd in (-90, -45, 0, 45, 90):
        x = int(gx0 + (gd + 90) / 180.0 * (gx1 - gx0))
        cv2.line(out, (x, gy - 6), (x, gy + 6),
                 (150, 150, 150) if gd == 0 else (70, 70, 70), 1)
        txt(out, x - 12, gy + 22, "%+d" % gd, (110, 110, 110), 0.42, 1)
    agujas(out, gx0, gx1, gy, ((angs["hoy"], C_HOY, "HOY"),
                               (angs["pp"], C_PP, "PP"),
                               (angs["st"], C_ST, "STANLEY"),
                               (angs["duo"], C_DUO, "PP+ST")))

    # ---- los cuatro numeros ------------------------------------------------
    ly = y0 + 150
    for i, (et, val, col) in enumerate((
            ("HOY           base + ley de hoy", angs["hoy"], C_HOY),
            ("PURE PURSUIT  MONO+SUELO + ley de hoy", angs["pp"], C_PP),
            ("STANLEY       base + psi/e separados", angs["st"], C_ST),
            ("PP + STANLEY  las dos juntas", angs["duo"], C_DUO))):
        yy = ly + i * 24
        cv2.rectangle(out, (14, yy - 11), (26, yy + 1), col, -1)
        txt(out, 34, yy, et, col, 0.5, 1)
        txt(out, 400, yy, "--" if val is None else "%+7.1f" % val, col, 0.55, 2)

    # ---- descomposicion de Stanley ----------------------------------------
    bx, by = W - 400, y0 + 60
    txt(out, bx, by, "STANLEY, de donde sale el comando", (185, 185, 185),
        0.5, 1)
    if comp_b is None:
        txt(out, bx, by + 34, "sin camino: no puede opinar, cae a la ley de hoy",
            (120, 120, 120), 0.48, 1)
    else:
        cx0 = bx + 150
        esc = 2.6
        for i, (nom, val, col) in enumerate((
                ("POSICION  atan(k*e/v)", comp_b["t_pos"], C_POS),
                ("RUMBO     k_psi*psi", comp_b["t_psi"], C_PSI))):
            yy = by + 30 + i * 30
            txt(out, bx, yy + 4, nom, col, 0.45, 1)
            w = int(abs(val) * esc)
            x = cx0 if val >= 0 else cx0 - w
            cv2.rectangle(out, (x, yy - 8), (x + w, yy + 8), col, -1)
            txt(out, cx0 + 118, yy + 4, "%+6.1f" % val, col, 0.48, 1)
        cv2.line(out, (cx0, by + 12), (cx0, by + 78), (120, 120, 120), 1)
        txt(out, bx, by + 108,
            "e %+.3f suelo    psi %+6.1f deg    v %.2f"
            % (comp_b["e"], comp_b["psi"], comp_b["v"]),
            (200, 200, 200), 0.48, 1)
        if comp_b["t_pos"] * comp_b["t_psi"] < 0:
            txt(out, bx, by + 132,
                "los dos terminos SE OPONEN: %+.1f %+.1f = %+.1f"
                % (comp_b["t_pos"], comp_b["t_psi"], comp_b["delta"]),
                (0, 190, 255), 0.48, 2)

    txt(out, W - 470, H - 10, AVISO, (100, 100, 100), 0.45, 1)


def placa_tabla(W, H, titulo, sub, cols, filas, notas, seg):
    """Placa con una tabla de columnas fijas. Las de placa() van centradas y
    una tabla centrada linea por linea no alinea nada."""
    img = np.zeros((H, W, 3), np.uint8)
    (tw, _), _ = cv2.getTextSize(titulo, FT, 0.95, 3)
    txt(img, (W - tw) // 2, 62, titulo, (255, 255, 255), 0.95, 3)
    if sub:
        (tw, _), _ = cv2.getTextSize(sub, FT, 0.6, 1)
        txt(img, (W - tw) // 2, 96, sub, (90, 230, 255), 0.6, 1)
    x0 = 190
    y = 190
    for nom, dx, ali in cols:
        (tw, _), _ = cv2.getTextSize(nom, FT, 0.5, 1)
        txt(img, x0 + dx - (tw if ali == "r" else 0), y, nom,
            (150, 150, 150), 0.5, 1)
    cv2.line(img, (x0 - 10, y + 10), (W - x0 + 10, y + 10), (70, 70, 70), 1)
    y += 42
    for fila, col in filas:
        for (nom, dx, ali), val in zip(cols, fila):
            (tw, _), _ = cv2.getTextSize(val, FT, 0.56, 2)
            txt(img, x0 + dx - (tw if ali == "r" else 0), y, val, col, 0.56, 2)
        y += 32
    y += 18
    for s, col in notas:
        txt(img, x0 - 10, y, s, col, 0.55, 1)
        y += 30
    txt(img, W - 470, H - 10, AVISO, (100, 100, 100), 0.45, 1)
    return [img] * int(round(seg * FPS))


def placa(W, H, lineas, seg):
    img = np.zeros((H, W, 3), np.uint8)
    y = int(H * 0.20)
    for s, esc, gr, col in lineas:
        (tw, _), _ = cv2.getTextSize(s, FT, esc, gr)
        txt(img, (W - tw) // 2, y, s, col, esc, gr)
        y += int(34 * esc + 22)
    txt(img, W - 470, H - 10, AVISO, (100, 100, 100), 0.45, 1)
    return [img] * int(round(seg * FPS))


def main():
    ap = argparse.ArgumentParser(
        description="Pure Pursuit contra Stanley, sobre los mismos frames")
    ap.add_argument("--salida", default="REGISTRO_DUPLEX_LEYES.mp4")
    ap.add_argument("--hfov", type=float, default=60.0)
    a = ap.parse_args()

    v4, v3, v2 = P.cargar()
    SB = P.hacer_sinbranch(v4)
    xz = P.hacer_suelo(v2, a.hfov)
    cfg = dict(mono=False, suelo=False, xz=xz, ld_suelo=LD_SUELO,
               lo_suelo=LD_SUELO * 0.77, hi_suelo=LD_SUELO * 1.26)
    P.instalar(v2, cfg)

    W, H = v2.W * E * 3, v2.H * E + 230
    ruta_out = os.path.join(AQUI, a.salida)
    vw = cv2.VideoWriter(ruta_out, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    if not vw.isOpened():
        print("*** no abre el writer")
        return 2

    n = 0
    for f in placa(W, H, [
            ("PURE PURSUIT  y  STANLEY", 1.25, 3, (255, 255, 255)),
            ("las dos leyes que el equipo tiene implementadas", 0.7, 2,
             (90, 230, 255)),
            ("", 0.5, 1, (0, 0, 0)),
            ("NO COMPITEN: resuelven mitades distintas del lazo", 0.72, 2,
             (0, 190, 255)),
            ("PURE PURSUIT elige QUE PUNTO perseguir", 0.6, 1, (120, 255, 120)),
            ("STANLEY convierte el camino en COMANDO", 0.6, 1, (255, 220, 90)),
            ("", 0.5, 1, (0, 0, 0)),
            ("mismos frames, misma percepcion, cuatro comandos", 0.58, 1,
             (170, 170, 170))], 5.5):
        vw.write(f)
        n += 1
    for f in placa(W, H, [
            ("LO QUE ESTE VIDEO NO PUEDE PROBAR", 0.95, 3, (0, 165, 255)),
            ("", 0.5, 1, (0, 0, 0)),
            ("es REPLAY EN LAZO ABIERTO: el video contiene el futuro", 0.62, 1,
             (200, 200, 200)),
            ("que genero la ley VIEJA manejando el robot", 0.62, 1,
             (200, 200, 200)),
            ("", 0.4, 1, (0, 0, 0)),
            ("muestra QUE PIDE cada ley sobre lo mismo,", 0.62, 1,
             (200, 200, 200)),
            ("no por donde pasaria el robot. Eso es prueba de robot.", 0.62, 2,
             (255, 255, 255)),
            ("", 0.4, 1, (0, 0, 0)),
            ("y el HFOV %.0f NO esta calibrado: psi escala con ese numero"
             % a.hfov, 0.58, 1, (0, 165, 255))], 5.5):
        vw.write(f)
        n += 1

    for vid, d, h, nota in TRAMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  falta %s, lo salteo" % vid)
            continue
        for f in placa(W, H, [
                ("%s   f%d-%d" % (vid.replace(".avi", ""), d, h), 0.95, 2,
                 (90, 230, 255)),
                (nota, 0.6, 1, (200, 200, 200))], 1.6):
            vw.write(f)
            n += 1

        cap = cv2.VideoCapture(ruta)
        tb, tp = SB(FPS), SB(FPS)
        i = 0
        while True:
            ok, fr = cap.read()
            if not ok or i > h:
                break
            g = v2.frame_pi(fr)

            cfg["mono"] = cfg["suelo"] = False
            rb = tb.step(g)
            kb = curvatura(v2, a.hfov)          # CAP es del step de recien
            cfg["mono"] = cfg["suelo"] = True
            rp = tp.step(g)
            kp = curvatura(v2, a.hfov)
            cfg["mono"] = cfg["suelo"] = False

            if i >= d:
                vb, vp = factor_vel(kb), factor_vel(kp)
                cb = LS.componentes(rb, v_norm=vb, k=LEY_K, k_psi=LEY_KPSI,
                                    g=LEY_G, hfov=a.hfov, arco=LEY_ARCO)
                cp = LS.componentes(rp, v_norm=vp, k=LEY_K, k_psi=LEY_KPSI,
                                    g=LEY_G, hfov=a.hfov, arco=LEY_ARCO)
                angs = dict(
                    hoy=LS.steer_actual(rb),
                    pp=LS.steer_actual(rp),
                    st=None if cb is None else cb["delta"],
                    duo=None if cp is None else cp["delta"])

                out = np.zeros((H, W, 3), np.uint8)
                w = v2.W * E
                cam = cv2.resize(g, (w, v2.H * E),
                                 interpolation=cv2.INTER_NEAREST)
                if cam.ndim == 2:
                    cam = cv2.cvtColor(cam, cv2.COLOR_GRAY2BGR)
                out[:v2.H * E, :w] = cam
                cabecera(out, w, "CAMARA   entrada del replay", (230, 230, 230))
                out[:v2.H * E, w:2 * w] = panel_pursuit(v2, rb, rp)
                out[:v2.H * E, 2 * w:3 * w] = panel_stanley(v2, rb, cb, a.hfov)
                info(out, v2, dict(video=vid.replace(".avi", ""), frame=i,
                                   nota=nota), rb, cb, cp, angs, W, H)
                vw.write(out)
                n += 1
            i += 1
        cap.release()
        print("  %-14s f%d-%d  ok" % (vid, d, h))

    # ---- cierre: los numeros que ya estan medidos --------------------------
    COLS = [("variante", 0, "l"), ("disp %", 470, "r"), ("huecos", 610, "r"),
            ("saltos", 750, "r"), ("INVERSIONES", 940, "r"),
            ("controles", 1030, "l")]
    for f in placa_tabla(
            W, H, "PURE PURSUIT: el A/B ya se corrio",
            "14.462 frames, 0 discrepancias de fidelidad.  Base absoluta: "
            "disp 93,78 %  huecos 276  saltos 247  inversiones 392",
            COLS,
            [(["BASE", "+0,00", "+0", "+0", "+0", "100/100  73/73"], C_HOY),
             (["MONO      Coulter 1992", "-0,06", "+6", "+7", "-26",
               "100/100  73/73"], C_PP),
             (["SUELO     Snider 2009", "+0,06", "+0", "+2", "+21",
               "100/100  73/73"], C_PP),
             (["MONO+SUELO", "-0,10", "+14", "+15", "+11", "100/100  73/73"],
              C_PP)],
            [("CRITERIO PREREGISTRADO: entra solo si mejora sin empeorar "
              "disponibilidad, huecos ni saltos.", (200, 200, 200)),
             ("NINGUNA PASO. MONO baja 26 inversiones pero agrega 6 huecos y "
              "7 saltos.", (0, 165, 255)),
             ("Y falta `d_eje`: pure pursuit toma el bearing DESDE el eje de "
              "rotacion, y ese numero no esta medido.", (0, 165, 255))],
            8.0):
        vw.write(f)
        n += 1

    FCOL = [("falsador", 0, "l"), ("lo mataba si", 330, "l"),
            ("medido", 900, "l"), ("", 1180, "l")]
    for f in placa_tabla(
            W, H, "STANLEY: pasa sus cinco falsadores",
            "escritos ANTES de medir.  Ley de hoy: steer = -1,011*e -0,758*psi"
            "   R2 0,82   reparto 47,8 / 52,2",
            FCOL,
            [(["F1  colinealidad", "|corr(e,psi)| >= 0,90", "0,258 max",
               "vive"], C_ST),
             (["F2  suficiencia", "R2(psi ~ x_target) >= 0,90", "0,497 max",
               "vive"], C_ST),
             (["F3  materialidad", "cambio < 2/5/8/12/20 deg", "34,6 a 40,2",
               "vive"], C_ST),
             (["F4  instrumento", "pide MAS giro en recta", "OK 15/15",
               "vive"], C_ST),
             (["F5  velocidad", "dividir por v no mueve nada", "13,95 deg p90",
               "vive"], C_ST)],
            [("Gate 15/15, conserva el +89 del control positivo, cuesta 19 us "
              "(1,8 % de un paso). Y SIGUE APAGADA:", (200, 200, 200)),
             ("1. el HFOV no esta calibrado. El codigo asume 60 y el TDP dice "
              "140: el mismo target da psi de 19,3 o de 59,0 grados.",
              (0, 165, 255)),
             ("2. atan(k*e/v) explota con v -> 0, y v -> 0 es exactamente el "
              "pivote: esta mal definida justo en el codo.", (0, 165, 255)),
             ("3. esto es replay en lazo abierto. Que pida distinto no es que "
              "maneje mejor. Eso es prueba de robot.", (0, 165, 255))],
            9.0):
        vw.write(f)
        n += 1

    for f in placa(W, H, [
            ("LO QUE DESBLOQUEA A LAS DOS", 1.05, 3, (255, 255, 255)),
            ("", 0.4, 1, (0, 0, 0)),
            ("calibrar el HFOV - 5 minutos, una pared y una cinta metrica",
             0.68, 2, (120, 255, 120)),
            ("medir d_eje - del eje de rotacion al piso de la fila 119",
             0.68, 2, (120, 255, 120)),
            ("", 0.4, 1, (0, 0, 0)),
            ("las dos se miden SIN ROBOT, y las dos estan pendientes", 0.6, 1,
             (170, 170, 170)),
            ("", 0.4, 1, (0, 0, 0)),
            ("mientras tanto lo que corre en pista es el atan2,", 0.58, 1,
             (150, 150, 150)),
            ("que trabaja en pixeles y no depende de ninguno de los dos.",
             0.58, 1, (150, 150, 150))], 7.0):
        vw.write(f)
        n += 1

    vw.release()
    mb = os.path.getsize(ruta_out) / 1e6
    print("")
    print("  %s   %d frames   %.1f s   %.1f MB"
          % (a.salida, n, n / FPS, mb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
