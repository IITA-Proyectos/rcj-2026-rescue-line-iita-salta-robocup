# -*- coding: utf-8 -*-
"""
REGISTRO VISUAL PRE-SABADO de NUEVO CODE V1 RC.

Corre LA CANDIDATA EXACTA sobre los 11 videos y produce un unico MP4 con el
overlay diagnostico real. No usa la vision vieja de Main.py para nada.

    candidata = arquitectura_minima.py :: SinBranch
              = NuevoCodeV2 + SpatialTargetGuard
              sin V3 (branch guard neutralizado) y sin H9-GATE

ESTO ES REGISTRO, NO OPTIMIZACION. No se cambia un solo parametro de la
candidata para que el video "se vea mejor".

============================================================================
 OPEN-LOOP REPLAY - NO ES PRUEBA FISICA NI DE LAZO CERRADO
============================================================================
Los frames los genero el controlador que REALMENTE manejo el robot. Si la
candidata hubiera decidido otra cosa, los frames siguientes habrian sido otros.
El video muestra que VE y que DECIDE la candidata sobre observaciones fijas.
No muestra que trayectoria haria.

COMO SE OBTIENEN LAS CINCO ETAPAS SIN TOCAR LA CANDIDATA
-------------------------------------------------------
`SinBranch.step()` solo devuelve `target_geometric` (post low_proj),
`target_branch` y `target` (post spatial). `target_raw` y `target_cap` viven
dentro de `NuevoCodeV2.step` y no salen.

  target_raw       espia reversible sobre `NuevoCodeV2.path_target`, que
                   devuelve el target crudo en `res["target"]`.
  target_cap       se RE-DERIVA con las mismas ocho lineas de V2.step, a partir
                   de (raw, prev_target, state, skeleton), todos capturados.

Y la re-derivacion SE AUTOVERIFICA: aplicando tambien el bloque de low_proj, el
resultado tiene que dar EXACTAMENTE `target_geometric`, que si expone la
candidata. Se compara en CADA frame y se reporta el conteo. Si hay una sola
discrepancia, el video sale igual pero el banner lo dice: no se maquilla.

USO
---
    python3 registro_visual.py                    # todo: video completo + clips
    python3 registro_visual.py --solo-clips
    python3 registro_visual.py --escala 3         # mas chico / mas rapido
"""

import argparse
import hashlib
import importlib.util
import math
import os
import subprocess
import sys
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
FPS_AUTON = 100.0 / 3.0
FPS_SALIDA = 100.0 / 3.0

# (nombre visible, archivo, fps real)
SEGMENTOS = [
    ("hist",         "hist.avi",         FPS_AUTON),
    ("lineal",       "lineal.avi",       FPS_AUTON),
    ("lineal70",     "lineal70.avi",     FPS_AUTON),
    ("como_esta",    "como_esta.avi",    FPS_AUTON),
    ("seguir",       "seguir.avi",       FPS_AUTON),
    ("rumbo",        "rumbo.avi",        FPS_AUTON),
    ("a",            "a.avi",            FPS_AUTON),
    ("roi_auto",     "roi_auto.avi",     FPS_AUTON),
    ("con_planner",  "con_planner.avi",  FPS_AUTON),
    ("con_planner2", "con_planner2.avi", FPS_AUTON),
    ("video_4",      "video_4.avi",      20.0),
]

MANUAL_LIFT = (524, 574)          # solo en video_4
AVISO = "OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF"

# Colores BGR de las cinco etapas. Distintos entre si y distintos del skeleton.
C_MASK = (45, 45, 45)
C_COMP = (35, 95, 35)
C_SKEL = (0, 150, 190)
C_PATH = (255, 170, 60)
C_START = (255, 130, 40)
C_RAW = (255, 0, 255)          # magenta
C_CAP = (0, 255, 255)          # amarillo
C_LOW = (255, 200, 0)          # celeste
C_FIN = (255, 255, 255)        # blanco
C_EST = {
    "HIGH": (70, 220, 70), "MEDIUM": (80, 210, 220), "LOW": (0, 160, 255),
    "LOW_FORWARD": (0, 190, 255), "SIN_CERCA": (255, 180, 60),
    "PERDIDA": (80, 80, 255),
}

FT = cv2.FONT_HERSHEY_SIMPLEX


# --------------------------------------------------------------------------
# CANDIDATA + ESPIA
# --------------------------------------------------------------------------
def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def hacer_sinbranch(v4):
    """SinBranch tal cual arquitectura_minima.py."""
    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _Nulo()

    return SinBranch


ULTIMO_RAW = {"res": None}


def espiar_path_target(v2):
    """Captura res["target"] = target_raw. Reversible."""
    orig = v2.NuevoCodeV2.path_target

    def envoltorio(self, comp, mode):
        sk, res = orig(self, comp, mode)
        ULTIMO_RAW["res"] = res
        return sk, res

    v2.NuevoCodeV2.path_target = envoltorio
    return lambda: setattr(v2.NuevoCodeV2, "path_target", orig)


def rederivar(raw, prev_target, st, sk, last_good):
    """Las MISMAS ocho lineas de NuevoCodeV2.step, para separar cap de low_proj.

    Devuelve (target_cap, target_lowproj, disparo_cont, disparo_low).
    `target_lowproj` tiene que coincidir con r["target_geometric"]: es el
    autochequeo.
    """
    target = raw
    cont = False
    low = False
    if prev_target is not None:
        jump = math.hypot(raw[0] - prev_target[0], raw[1] - prev_target[1])
        cap = 16 if st in ("HIGH", "MEDIUM") else \
            12 if st in ("LOW", "LOW_FORWARD") else 20
        if jump > cap:
            ys, xs = np.nonzero(sk)
            dp = np.sqrt((xs - prev_target[0]) ** 2 + (ys - prev_target[1]) ** 2)
            poss = np.where(dp <= cap)[0]
            if len(poss):
                j = poss[np.argmin((xs[poss] - raw[0]) ** 2
                                   + (ys[poss] - raw[1]) ** 2)]
                target = (float(xs[j]), float(ys[j]))
                cont = True
    t_cap = target
    if st == "LOW" and last_good is not None:
        if math.hypot(target[0] - last_good[0],
                      target[1] - last_good[1]) > 28:
            ys, xs = np.nonzero(sk)
            j = np.argmin((xs - last_good[0]) ** 2 + (ys - last_good[1]) ** 2)
            target = (float(xs[j]), float(ys[j]))
            low = True
    return t_cap, target, cont, low


def igual(a, b):
    if a is None or b is None:
        return a is b
    return abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6


def steer_de(t, W, CENTER):
    if t is None:
        return None
    return float(np.clip(-90.0 * (t[0] - CENTER) / (W / 2.0), -90.0, 90.0))


# --------------------------------------------------------------------------
# DIBUJO
# --------------------------------------------------------------------------
def pxy(p):
    return None if p is None else (int(round(p[0])), int(round(p[1])))


def panel(v2, r, etapas):
    """Panel diagnostico en resolucion nativa 160x120."""
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
    return vis


def marcar(vis, E, etapas, r):
    """Marcas de las cinco etapas sobre el panel YA ampliado."""
    def P(p):
        q = pxy(p)
        return None if q is None else (int(q[0] * E + E // 2),
                                       int(q[1] * E + E // 2))

    raw, cap, low, fin = (etapas["raw"], etapas["cap"],
                          etapas["lowproj"], etapas["final"])
    # cadena raw -> cap -> lowproj -> final, solo donde hay movimiento real
    cadena = [x for x in (raw, cap, low, fin) if x is not None]
    for a, b in zip(cadena, cadena[1:]):
        if not igual(a, b):
            cv2.arrowedLine(vis, P(a), P(b), (120, 120, 120), 1,
                            tipLength=0.15)
    if r.get("start") is not None:
        cv2.circle(vis, P(r["start"]), max(3, E), C_START, -1)
    if raw is not None:
        cv2.drawMarker(vis, P(raw), C_RAW, cv2.MARKER_CROSS, 7 * E, 2)
    if cap is not None and not igual(cap, raw):
        cv2.drawMarker(vis, P(cap), C_CAP, cv2.MARKER_SQUARE, 6 * E, 2)
    if low is not None and not igual(low, cap):
        cv2.drawMarker(vis, P(low), C_LOW, cv2.MARKER_DIAMOND, 6 * E, 2)
    if fin is not None:
        cv2.drawMarker(vis, P(fin), C_FIN, cv2.MARKER_TILTED_CROSS, 8 * E, 2)
    return vis


def barra_steer(img, x0, y0, ancho, alto, steer):
    """steer = -90*(x-CENTER)/(W/2): POSITIVO ES A LA IZQUIERDA.
    Por eso el positivo se dibuja hacia la izquierda, no al reves."""
    cv2.rectangle(img, (x0, y0), (x0 + ancho, y0 + alto), (70, 70, 70), 1)
    cx = x0 + ancho // 2
    cv2.line(img, (cx, y0), (cx, y0 + alto), (110, 110, 110), 1)
    texto(img, x0 - 62, y0 + alto - 5, "IZQ +90", (110, 110, 110), 0.42)
    texto(img, x0 + ancho + 8, y0 + alto - 5, "-90 DER", (110, 110, 110), 0.42)
    if steer is None:
        texto(img, cx - 48, y0 + alto - 5, "SIN TARGET", (80, 80, 255), 0.5)
        return
    w = int(round((ancho / 2.0) * (steer / 90.0)))
    a, b = (cx - w, cx) if w >= 0 else (cx, cx - w)
    cv2.rectangle(img, (a, y0 + 2), (b, y0 + alto - 2), (235, 235, 235), -1)


def texto(img, x, y, s, col=(210, 210, 210), esc=0.5, gr=1):
    cv2.putText(img, s, (x, y), FT, esc, col, gr, cv2.LINE_AA)


def cuadro(v2, r, etapas, meta, W_out, H_out, E, alto_txt):
    cam = cv2.resize(meta["g"], (v2.W * E, v2.H * E),
                     interpolation=cv2.INTER_NEAREST)
    pan = cv2.resize(panel(v2, r, etapas), (v2.W * E, v2.H * E),
                     interpolation=cv2.INTER_NEAREST)
    pan = marcar(pan, E, etapas, r)

    out = np.zeros((H_out, W_out, 3), np.uint8)
    out[:v2.H * E, :v2.W * E] = cam
    out[:v2.H * E, v2.W * E:v2.W * E * 2] = pan

    # los .avi de origen ya traen overlay quemado: fondo opaco para el titulo
    cv2.rectangle(out, (0, 0), (W_out, 32), (0, 0, 0), -1)
    texto(out, 10, 23, "CAMARA QUE VIO LA PI (entrada cruda del replay)",
          (235, 235, 235), 0.55)
    texto(out, v2.W * E + 10, 23, "NUEVO CODE V1 RC  -  SinBranch",
          (235, 235, 235), 0.55)

    # banner del segmento
    cv2.rectangle(out, (0, v2.H * E - 34), (W_out, v2.H * E), (0, 0, 0), -1)
    texto(out, 10, v2.H * E - 10, meta["nombre"].upper(), (90, 230, 255), 0.8, 2)
    texto(out, v2.W * E + 10, v2.H * E - 11,
          "frame %d / %d    t=%.2f s    %.3f fps reales"
          % (meta["i"], meta["n"], meta["i"] / meta["fps"], meta["fps"]),
          (170, 170, 170), 0.48)

    if meta.get("manual_lift"):
        sub = out[:v2.H * E, :]
        cv2.rectangle(sub, (0, 150), (W_out, 215), (0, 0, 120), -1)
        texto(out, 40, 195, "MANUAL_LIFT - INVALID FOR AUTONOMOUS CONTROL GT",
              (255, 255, 255), 0.95, 2)

    y0 = v2.H * E + 30
    st = r.get("state", "?")
    texto(out, 12, y0, "ESTADO  %s" % st, C_EST.get(st, (235, 235, 235)), 0.7, 2)
    texto(out, 250, y0, "modo %s" % r.get("mode", "-"), (170, 170, 170), 0.5)
    texto(out, 470, y0, "razon V2: %s" % (r.get("reason") or "-"),
          (170, 170, 170), 0.5)

    sg = r.get("spatial_guard", "-")
    col_sg = (0, 200, 255) if sg in ("SPATIAL_LIMIT", "REACQ_PENDING",
                                     "NO_SKELETON") else (150, 150, 150)
    texto(out, 12, y0 + 28, "BRANCH  PASA (V3 fuera)", (140, 140, 140), 0.5)
    texto(out, 250, y0 + 28, "SPATIAL  %s" % sg, col_sg, 0.55,
          2 if col_sg[0] == 0 else 1)
    pj = r.get("proposed_jump_px")
    if pj is not None:
        texto(out, 560, y0 + 28, "salto propuesto %.1f px" % pj,
              col_sg, 0.5)

    s = etapas["steer"]
    texto(out, 12, y0 + 58, "STEER  %s"
          % ("--" if s is None else "%+6.1f deg" % s), (235, 235, 235), 0.6, 2)
    barra_steer(out, 262, y0 + 40, 340, 22, s)

    # leyenda de las cinco etapas
    yl = y0 + 92
    leyenda = [
        ("target_raw", C_RAW, etapas["raw"]),
        ("target_cap", C_CAP, etapas["cap"]),
        ("target_lowproj", C_LOW, etapas["lowproj"]),
        ("target_final", C_FIN, etapas["final"]),
    ]
    x = 12
    for nom, col, val in leyenda:
        cv2.rectangle(out, (x, yl - 11), (x + 12, yl + 1), col, -1)
        v = "--" if val is None else "(%.0f,%.0f)" % (val[0], val[1])
        texto(out, x + 18, yl, "%s %s" % (nom, v), col, 0.46)
        x += 305
    x = 12
    for nom, col in (("skeleton", C_SKEL), ("componente elegida", C_COMP),
                     ("mascara", C_MASK), ("path", C_PATH),
                     ("start/entry", C_START)):
        cv2.rectangle(out, (x, yl + 14), (x + 12, yl + 26), col, -1)
        cv2.rectangle(out, (x, yl + 14), (x + 12, yl + 26), (90, 90, 90), 1)
        texto(out, x + 18, yl + 25, nom, (140, 140, 140), 0.44)
        (tw, _), _ = cv2.getTextSize(nom, FT, 0.44, 1)
        x += tw + 46

    if meta.get("aviso_rederiv"):
        texto(out, 12, yl + 46, meta["aviso_rederiv"], (0, 165, 255), 0.45)

    texto(out, W_out - 470, H_out - 12, AVISO, (110, 110, 110), 0.46)
    return out


def placa(W_out, H_out, lineas, seg, fps):
    img = np.zeros((H_out, W_out, 3), np.uint8)
    y = int(H_out * 0.30)
    for s, esc, gr, col in lineas:
        (tw, _), _ = cv2.getTextSize(s, FT, esc, gr)
        texto(img, (W_out - tw) // 2, y, s, col, esc, gr)
        y += int(38 * esc + 26)
    texto(img, W_out - 470, H_out - 12, AVISO, (110, 110, 110), 0.46)
    return [img] * int(round(seg * fps))


# --------------------------------------------------------------------------
# ESCRITOR
# --------------------------------------------------------------------------
def abrir_writer(ruta, W_out, H_out, fps, preferidos=("mp4v", "avc1", "MJPG")):
    for cc in preferidos:
        vw = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*cc), fps,
                             (W_out, H_out))
        if vw.isOpened():
            return vw, cc
        vw.release()
    return None, None


def sha_candidata():
    h = hashlib.sha256()
    for f in ("nuevo_code_v2.py", "nuevo_code_v3.py", "nuevo_code_v4.py",
              "arquitectura_minima.py"):
        with open(os.path.join(AQUI, f), "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:16]


def git_info():
    def c(a):
        try:
            return subprocess.check_output(
                a, cwd=AQUI, stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            return None
    return dict(sha=c(["git", "rev-parse", "HEAD"]),
                rama=c(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
                sucio=bool(c(["git", "status", "--porcelain",
                              "--untracked-files=no"])))


# --------------------------------------------------------------------------
# RENDER
# --------------------------------------------------------------------------
def render_segmento(v4, v2, SinBranch, nombre, archivo, fps, vw, W_out, H_out,
                    E, alto_txt, desde=0, hasta=10 ** 9, con_placa=True,
                    manual_lift=None, cont=None):
    ruta = os.path.join(AQUI, archivo)
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        print("    *** no abre %s" % archivo)
        return 0
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    tr = SinBranch(fps)
    escritos = 0
    i = 0
    # conversion de fps: cada frame fuente ocupa 1/fps s en la salida
    t_out = 0.0
    if con_placa:
        for f in placa(W_out, H_out,
                       [(nombre.upper(), 1.7, 3, (90, 230, 255)),
                        ("%s   %.3f fps reales" % (archivo, fps), 0.7, 1,
                         (180, 180, 180))], 1.0, FPS_SALIDA):
            vw.write(f)
            escritos += 1
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        g = v2.frame_pi(fr)
        prev_t = tr.per.prev_target
        last_g = tr.per.last_good_target
        ULTIMO_RAW["res"] = None
        r = tr.step(g)

        res = ULTIMO_RAW["res"]
        raw = None if res is None else res["target"]
        t_cap = t_low = None
        if raw is not None and r.get("skel") is not None:
            t_cap, t_low, _c, _l = rederivar(raw, prev_t, r.get("state"),
                                             r["skel"], last_g)
            cont["n"] += 1
            if not igual(t_low, r.get("target_geometric")):
                cont["mal"] += 1
        etapas = dict(raw=raw, cap=t_cap, lowproj=t_low,
                      final=r.get("target"),
                      steer=steer_de(r.get("target"), v2.W, v2.CENTER))

        if i >= desde:
            ml = (manual_lift is not None
                  and manual_lift[0] <= i <= manual_lift[1])
            meta = dict(g=g, nombre=nombre, i=i, n=n_total, fps=fps,
                        manual_lift=ml, aviso_rederiv=cont.get("aviso"))
            img = cuadro(v2, r, etapas, meta, W_out, H_out, E, alto_txt)
            # repetir/omitir para conservar el tiempo real
            t_out += FPS_SALIDA / fps
            reps = int(t_out)
            t_out -= reps
            for _ in range(max(1, reps)):
                vw.write(img)
                escritos += 1
        i += 1
    cap.release()
    return escritos


def main():
    ap = argparse.ArgumentParser(description="Registro visual de la candidata")
    ap.add_argument("--escala", type=int, default=4)
    ap.add_argument("--solo-clips", action="store_true", dest="solo_clips")
    ap.add_argument("--solo-completo", action="store_true",
                    dest="solo_completo")
    ap.add_argument("--salida", default="REGISTRO_V1RC.mp4")
    ap.add_argument("--codec", default="mp4v,avc1,MJPG",
                    help="mp4v mide 5x mejor que avc1 con este build de OpenCV")
    a = ap.parse_args()

    v4, v3, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    restaurar = espiar_path_target(v2)

    E = a.escala
    W_out = v2.W * E * 2
    alto_txt = 240
    H_out = v2.H * E + alto_txt

    gi = git_info()
    shac = sha_candidata()
    fecha = time.strftime("%Y-%m-%d")
    print("")
    print("  candidata  arquitectura_minima.py :: SinBranch = V2 + Spatial")
    print("  git        %s  %s%s" % (gi["rama"], (gi["sha"] or "?")[:10],
                                     "  (ARBOL SUCIO)" if gi["sucio"] else ""))
    print("  sha fuente %s  (v2+v3+v4+arquitectura_minima)" % shac)
    print("  salida     %dx%d @ %.3f fps" % (W_out, H_out, FPS_SALIDA))
    print("")

    cont = {"n": 0, "mal": 0, "aviso": None}
    t0 = time.time()

    # ---- clips cortos -----------------------------------------------------
    clips = [
        ("CLIP_hist_curva_problematica.mp4", "hist", "hist.avi", FPS_AUTON,
         1340, 1470, None),
        ("CLIP_lineal_control_positivo.mp4", "lineal", "lineal.avi", FPS_AUTON,
         795, 875, None),
    ]
    hechos = []
    if not a.solo_completo:
        for nom, etq, arch, fps, d, h, ml in clips:
            ruta = os.path.join(AQUI, nom)
            vw, cc = abrir_writer(ruta, W_out, H_out, FPS_SALIDA, tuple(a.codec.split(",")))
            if vw is None:
                print("  *** no se pudo abrir writer para %s" % nom)
                continue
            n = render_segmento(v4, v2, SinBranch, "%s  f%d-%d" % (etq, d, h),
                                arch, fps, vw, W_out, H_out, E, alto_txt,
                                desde=d, hasta=h, manual_lift=ml, cont=cont)
            vw.release()
            hechos.append((nom, n, cc))
            print("  clip %-38s %5d frames  (%s)" % (nom, n, cc))

    # ---- video completo ---------------------------------------------------
    if not a.solo_clips:
        ruta = os.path.join(AQUI, a.salida)
        vw, cc = abrir_writer(ruta, W_out, H_out, FPS_SALIDA, tuple(a.codec.split(",")))
        if vw is None:
            print("  *** no se pudo abrir el writer del video completo")
            restaurar()
            return 2
        total = 0
        for f in placa(W_out, H_out, [
                ("NUEVO CODE V1 RC", 1.9, 3, (255, 255, 255)),
                ("SinBranch = V2 + SpatialTargetGuard", 0.9, 2,
                 (90, 230, 255)),
                ("sin V3 branch guard   -   sin H9-GATE", 0.65, 1,
                 (170, 170, 170)),
                ("git %s  %s%s" % (gi["rama"], (gi["sha"] or "?")[:10],
                                   "  (ARBOL SUCIO)" if gi["sucio"] else ""),
                 0.6, 1, (170, 170, 170)),
                ("sha fuente candidata %s" % shac, 0.6, 1, (170, 170, 170)),
                (fecha, 0.6, 1, (170, 170, 170)),
                ("OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF", 0.7, 2,
                 (0, 165, 255))], 4.0, FPS_SALIDA):
            vw.write(f)
            total += 1
        for nombre, archivo, fps in SEGMENTOS:
            if not os.path.exists(os.path.join(AQUI, archivo)):
                print("  ... %-14s FALTA, se saltea" % nombre)
                continue
            ml = MANUAL_LIFT if nombre == "video_4" else None
            n = render_segmento(v4, v2, SinBranch, nombre, archivo, fps, vw,
                                W_out, H_out, E, alto_txt, manual_lift=ml,
                                cont=cont)
            total += n
            print("  ... %-14s %6d frames de salida   (%.0f s acumulados)"
                  % (nombre, n, total / FPS_SALIDA))
        vw.release()
        hechos.append((a.salida, total, cc))

    restaurar()

    print("")
    print("  AUTOCHEQUEO DE LA RE-DERIVACION DE ETAPAS")
    print("    frames con target     %d" % cont["n"])
    print("    discrepancias         %d" % cont["mal"])
    if cont["mal"] == 0:
        print("    OK: target_cap -> low_proj re-derivado reproduce EXACTAMENTE")
        print("    el target_geometric que devuelve la candidata.")
    else:
        print("    *** HAY DISCREPANCIAS. Las etapas intermedias del video no")
        print("    *** son fiables en esos frames.")
    print("")
    for nom, n, cc in hechos:
        p = os.path.join(AQUI, nom)
        mb = os.path.getsize(p) / 1e6 if os.path.exists(p) else 0
        print("  %-40s %6d frames   %6.1f s   %7.1f MB   codec %s"
              % (nom, n, n / FPS_SALIDA, mb, cc))
    print("")
    print("  tiempo de render %.1f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
