#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
captura_luz.py - graba lo que ve el robot, CRUDO y SIN COMPRIMIR, para medir verde y negro con distintas luces.

Va en la Pi, en la MISMA carpeta que main.py y camthreader.py. Con main.py PARADO (la camara no se comparte).

    python3 captura_luz.py ETIQUETA
    python3 captura_luz.py ETIQUETA --segundos 30 --fps 10
    python3 captura_luz.py ETIQUETA --fijar "auto_exposure=1,exposure_time_absolute=100,white_balance_automatic=0,white_balance_temperature=4600,power_line_frequency=1"

ETIQUETA = QUE_LUZ, por ejemplo doble_base, doble_lampara, izq_sombra, linea_sol, piso_tubo.
QUE es lo que se le muestra al robot y sirve para el analisis:
    doble = doble verde  |  izq / der = verde simple  |  linea = solo cinta negra  |  piso = piso verde SIN marca

No mueve motores ni habla con la Teensy: el robot se empuja a mano o se apoya.
Guarda en /home/iita/luz/<MMDD_HHMM>_<ETIQUETA>/:
    f_00001.png ...   el cuadro de 160x120 tal cual lo procesa main.py (rotado 180 y achicado)
    ctx_000.jpg ...   una foto grande por segundo, para ver la escena
    controles_inicio.txt / controles_fin.txt   lo que dice v4l2-ctl de la camara
    resumen.txt       lo que decidio el verde cuadro por cuadro
Los rangos de verde y negro los lee de main.py, asi siempre son los del robot.
Ctrl-C corta antes de tiempo.
"""
import argparse
import os
import re
import subprocess
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)


def leer_rangos(ruta_main):
    """lower/upper green y black y min_square_size, sacados del main.py del robot."""
    r = {"lower_green": (100, 87, 118), "upper_green": (151, 108, 141),
         "lower_black": (0, 0, 0), "upper_black": (90, 90, 90), "min_square_size": 510}
    try:
        src = open(ruta_main, encoding="utf-8", errors="replace").read()
        for k in ("lower_green", "upper_green", "lower_black", "upper_black"):
            m = re.search(r"^" + k + r"\s*=\s*np\.array\(\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", src, re.M)
            if m:
                r[k] = tuple(int(g) for g in m.groups())
        m = re.search(r"^min_square_size\s*=\s*(\d+)", src, re.M)
        if m:
            r["min_square_size"] = int(m.group(1))
        r["origen"] = ruta_main
    except OSError:
        r["origen"] = "valores por defecto (no encontre main.py)"
    return r


def decidir_verde(fr, R, kernel=np.ones((3, 3), np.uint8)):
    """La misma cuenta que main.py: devuelve (estado, pixeles_verdes, pixeles_negros)."""
    lab = cv2.cvtColor(fr, cv2.COLOR_BGR2LAB)
    bm = cv2.inRange(fr, np.array(R["lower_black"]), np.array(R["upper_black"]))
    bm[:60, :] = 0
    gm = np.zeros((120, 160), np.uint8)
    gm[80:, :] = cv2.inRange(lab[80:, :, :], np.array(R["lower_green"]), np.array(R["upper_green"]))
    ng, nb = int(np.count_nonzero(gm)), int(np.count_nonzero(bm))
    mss = R["min_square_size"]
    if ng <= mss:
        return 0, ng, nb
    gp = np.amax(gm, axis=0)
    idx = np.where(gp == np.max(gp))[0]
    L, Rr = idx[0], idx[-1]
    sliced = bm[60:90, L:Rr + 1]
    m = cv2.moments(bm[90:, :])
    if not (np.sum(bm[90:, :]) and m["m00"] != 0):
        return 0, ng, nb
    cx = int(m["m10"] / m["m00"])
    if not (np.sum(sliced) / (255 * 30 * max(1, Rr - L)) > 0.32):
        return 0, ng, nb
    fg = cv2.dilate(cv2.erode(gm, kernel, iterations=1), kernel, iterations=2)
    nc = len(cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0])
    if nc > 1 and L < cx < Rr and ng > 1.2 * mss:
        return 3, ng, nb
    return (1 if (L + Rr) / 2 < cx else 2), ng, nb


def v4l2(args):
    try:
        r = subprocess.run(["v4l2-ctl", "-d", "/dev/video0"] + args, capture_output=True, text=True, timeout=5)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "v4l2-ctl no disponible: %s" % e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("etiqueta")
    ap.add_argument("--segundos", type=float, default=20.0)
    ap.add_argument("--fps", type=float, default=10.0, help="cuadros por segundo que se guardan")
    ap.add_argument("--fijar", default="", help="controles de v4l2-ctl separados por coma (ver README)")
    ap.add_argument("--salida", default="/home/iita/luz")
    ap.add_argument("--video", default="", help="solo para probar en la compu: lee un video en vez de la camara")
    a = ap.parse_args()

    R = leer_rangos(os.path.join(AQUI, "main.py"))
    carpeta = os.path.join(a.salida, time.strftime("%m%d_%H%M%S") + "_" + a.etiqueta)
    os.makedirs(carpeta, exist_ok=True)
    print("guardando en", carpeta)
    print("rangos de", R["origen"], "-> verde", R["lower_green"], R["upper_green"], "negro <=", R["upper_black"],
          "min_square_size", R["min_square_size"])

    if a.video:
        cam = cv2.VideoCapture(a.video)
        leer = lambda: cam.read()[1]
        parar = cam.release
    else:
        try:
            from camthreader import WebcamVideoStream
            vs = WebcamVideoStream(src=0).start()
            leer, parar = vs.read, vs.stop
        except Exception as e:
            print("camthreader no anduvo (%s): uso cv2.VideoCapture(0)" % e)
            cam = cv2.VideoCapture(0)
            leer = lambda: cam.read()[1]
            parar = cam.release
        time.sleep(0.5)
        if a.fijar:
            # el orden importa: primero pasar a manual, despues el valor
            for c in a.fijar.split(","):
                print("v4l2-ctl -c", c.strip(), "->", v4l2(["-c", c.strip()]) or "ok")
            for _ in range(15):          # el sensor tarda en asentarse
                leer(); time.sleep(0.03)
    open(os.path.join(carpeta, "controles_inicio.txt"), "w").write(
        "fijar: %s\n\n%s\n" % (a.fijar or "(nada: camara en automatico)", v4l2(["--list-ctrls-menus"])))

    n = 0; ctx = 0; t0 = time.monotonic(); prox = t0; ult_seg = -1; lineas = []
    try:
        while time.monotonic() - t0 < a.segundos:
            frame = leer()
            if frame is None:
                if a.video:
                    break
                time.sleep(0.01); continue
            ahora = time.monotonic()
            if not a.video:              # con la camara se guarda a --fps; con un video, todos los cuadros
                if ahora < prox:
                    time.sleep(0.002); continue
                prox = ahora + 1.0 / a.fps
            # exactamente como main.py: rotar 180 y achicar a 160x120 con NEAREST
            rot = cv2.rotate(frame, cv2.ROTATE_180)
            fr = cv2.resize(rot, (160, 120), interpolation=cv2.INTER_NEAREST)
            n += 1
            cv2.imwrite(os.path.join(carpeta, "f_%05d.png" % n), fr)
            t = ahora - t0
            est, ng, nb = decidir_verde(fr, R)
            lineas.append("%05d %.2f estado=%d verde=%d negro=%d" % (n, t, est, ng, nb))
            if int(t) != ult_seg:
                ult_seg = int(t)
                cv2.imwrite(os.path.join(carpeta, "ctx_%03d.jpg" % ctx), rot); ctx += 1
                print("t=%5.1f  verde %4d px -> estado %d %s | negro %4d px" % (
                    t, ng, est, {0: "", 1: "(IZQ)", 2: "(DER)", 3: "(DOBLE)"}[est], nb))
    except KeyboardInterrupt:
        print("cortado")
    finally:
        parar()
        open(os.path.join(carpeta, "resumen.txt"), "w").write("\n".join(lineas) + "\n")
        if not a.video:
            open(os.path.join(carpeta, "controles_fin.txt"), "w").write(v4l2(["--list-ctrls-menus"]) + "\n")
        print("listo: %d cuadros en %s" % (n, carpeta))


if __name__ == "__main__":
    main()
