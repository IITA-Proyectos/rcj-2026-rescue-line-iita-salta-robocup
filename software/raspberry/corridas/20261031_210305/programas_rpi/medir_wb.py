#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medir_wb.py - busca el balance de blancos fijo (CAMARA_WB de main.py) con el que el rango de verde de main.py
cubre mejor los cuadrados y no agarra el piso.

Va en la Pi, en la misma carpeta que main.py y camthreader.py, con main.py PARADO (la camara no se comparte).
El robot QUIETO, apoyado frente a un DOBLE VERDE, con los dos cuadrados en la mitad de abajo de la imagen (como
cuando decide) y piso blanco alrededor. Con la luz del lugar donde se va a correr.

    python3 medir_wb.py
    python3 medir_wb.py --desde 3600 --hasta 5600 --paso 100      (afinar alrededor del mejor)

Prueba cada temperatura (2800-6500), espera que la camara se asiente, y de 5 cuadros mide:
    cubre    que parte de los cuadrados verdes entra en el rango de main.py (la marca la encuentra sola)
    piso     pixeles del piso blanco/cinta que entran en el rango (tienen que ser ~0)
    decide   lo que decidiria main.py con ese cuadro (tiene que ser DOBLE)
    blanco   color del piso blanco (a, b en LAB; 128 = neutro)
La exposicion queda en automatico (o la que se pase con --expo, igual que CAMARA_EXPO).
Al terminar deja la camara en AUTOMATICO otra vez, como la usa el robot sin CAMARA_WB.
Guarda un cuadro por temperatura en /home/iita/luz/wb_MMDD_HHMMSS/ para mirarlo despues.

Ojo: el rango de main.py se calibro con la camara en automatico. Si el mejor WB cubre poco, hay que recalibrar el
verde CON ese WB fijo (captura_luz.py --fijar ... y calibrar_verde_multi.py).
"""
import argparse
import os
import subprocess
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from captura_luz import decidir_verde, leer_rangos  # noqa: E402

K1 = np.ones((3, 3), np.uint8)
NOMBRE = {0: "-", 1: "IZQ", 2: "DER", 3: "DOBLE"}


def v4l2(*ordenes):
    for o in ordenes:
        r = subprocess.run(["v4l2-ctl", "-d", "/dev/video0", "-c", o], capture_output=True, text=True)
        if r.returncode != 0:
            print("  v4l2-ctl -c %s: %s" % (o, r.stderr.strip()))


def marcas(lab):
    """Pixeles de los cuadrados verdes (claramente verdes, ni negros ni blancos), achicados 1 px. Filas >= 80."""
    L, a = lab[..., 0].astype(int), lab[..., 1].astype(int)
    m = ((a < 118) & (L > 40) & (L < 235)).astype(np.uint8)
    m[:80] = 0
    m = cv2.erode(m, K1, iterations=1)
    n, et, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(m.shape, bool)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 25:
            keep |= et == i
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2800)
    ap.add_argument("--hasta", type=int, default=6500)
    ap.add_argument("--paso", type=int, default=200)
    ap.add_argument("--expo", type=int, default=0, help="exposicion fija (como CAMARA_EXPO). 0 = automatica")
    ap.add_argument("--salida", default="/home/iita/luz")
    a = ap.parse_args()

    R = leer_rangos(os.path.join(AQUI, "main.py"))
    lo, hi = np.array(R["lower_green"]), np.array(R["upper_green"])
    print("rango de verde de %s: %s - %s  min_square_size %d" % (R["origen"], lo.tolist(), hi.tolist(),
                                                                R["min_square_size"]))
    carpeta = os.path.join(a.salida, "wb_" + time.strftime("%m%d_%H%M%S"))
    os.makedirs(carpeta, exist_ok=True)

    from camthreader import WebcamVideoStream
    vs = WebcamVideoStream(src=0).start()
    time.sleep(1.0)
    if a.expo:
        v4l2("auto_exposure=1", "exposure_time_absolute=%d" % a.expo)
    v4l2("white_balance_automatic=0")

    filas = []
    print("\n  WB   | cubre | piso px | verde px | decide | blanco L  a   b")
    try:
        for wb in range(a.desde, a.hasta + 1, a.paso):
            v4l2("white_balance_temperature=%d" % wb)
            time.sleep(0.8)              # que la camara se asiente con el valor nuevo
            cub, piso, est, ng, bl = [], [], [], [], []
            for k in range(5):
                f = vs.read()
                if f is None:
                    time.sleep(0.05)
                    continue
                fr = cv2.resize(cv2.rotate(f, cv2.ROTATE_180), (160, 120), interpolation=cv2.INTER_NEAREST)
                lab = cv2.cvtColor(fr, cv2.COLOR_BGR2LAB)
                mk = marcas(lab)
                adentro = np.all((lab >= lo) & (lab <= hi), axis=2)
                abajo = np.zeros(mk.shape, bool)
                abajo[80:] = True
                # el piso: lo que NO es marca (ni su borde), en la franja que mira main.py
                cerca = cv2.dilate(mk.astype(np.uint8), K1, iterations=3).astype(bool)
                if mk.sum():
                    cub.append(adentro[mk].mean())
                piso.append(int((adentro & abajo & ~cerca).sum()))
                s, n, _ = decidir_verde(fr, R)
                est.append(s)
                ng.append(n)
                L, aa, bb = lab[..., 0].astype(int), lab[..., 1].astype(int), lab[..., 2].astype(int)
                w = abajo & (L > 140) & (abs(aa - 128) < 15) & (abs(bb - 128) < 30)
                if w.sum() > 200:
                    bl.append(np.median(lab[w], axis=0))
                if k == 0:
                    cv2.imwrite(os.path.join(carpeta, "wb_%d.png" % wb), fr)
                time.sleep(0.05)
            c = np.mean(cub) * 100 if cub else 0.0
            p = max(piso) if piso else 0
            d = max(set(est), key=est.count) if est else 0
            b = np.median(bl, axis=0) if bl else (0, 0, 0)
            filas.append((wb, c, p, d, int(np.median(ng)) if ng else 0, b))
            print("  %4d | %4.0f%% | %7d | %8d | %-6s | %5.0f %3.0f %3.0f" % (wb, c, p, filas[-1][4], NOMBRE[d], *b))
    except KeyboardInterrupt:
        print("cortado")
    finally:
        v4l2("white_balance_automatic=1")
        if a.expo:
            v4l2("auto_exposure=3")
        vs.stop()
        print("\ncamara de nuevo en automatico.")

    if not filas:
        return
    lineas = ["%d cubre=%.0f%% piso=%d decide=%s verde=%d blanco=%s" % (wb, c, p, NOMBRE[d], n, list(np.round(b)))
              for wb, c, p, d, n, b in filas]
    open(os.path.join(carpeta, "resultado.txt"), "w").write(
        "rango %s-%s\n%s\n" % (lo.tolist(), hi.tolist(), "\n".join(lineas)))
    if not any(c for _, c, _, _, _, _ in filas):
        print("No encontre cuadrados verdes en la mitad de abajo: acercar el robot al doble verde.")
        return
    # el mejor: decide DOBLE, piso limpio (< 1/4 de min_square_size) y la mayor cobertura
    buenos = [f for f in filas if f[3] == 3 and f[2] < R["min_square_size"] / 4]
    if not buenos:
        print("Con NINGUNA temperatura el rango actual decide DOBLE con el piso limpio.")
        print("Elegir la temperatura con el blanco mas neutro (a y b cerca de 128) y recalibrar el verde con ella.")
        return
    mejor = max(buenos, key=lambda f: (f[1], -f[2]))
    # la zona de temperaturas seguidas que cubren casi igual (hasta 5 puntos menos): se elige el MEDIO, que es
    # lo que mas aguanta si la luz cambia un poco
    casi = {f[0] for f in buenos if f[1] >= mejor[1] - 5}
    desde = hasta = mejor[0]
    while desde - a.paso in casi:
        desde -= a.paso
    while hasta + a.paso in casi:
        hasta += a.paso
    medio = desde + ((hasta - desde) // 2 // a.paso) * a.paso
    fm = next(f for f in filas if f[0] == medio)
    print("Funcionan bien de %d a %d (la mejor, %d: cubre %.0f%%, piso %d px)." % (
        desde, hasta, mejor[0], mejor[1], mejor[2]))
    print(">>> usar CAMARA_WB=%d  (el medio: cubre %.0f%%, piso %d px)" % (medio, fm[1], fm[2]))
    if hasta - desde < 2 * a.paso:
        print("    La zona es angosta: el color depende mucho del WB. Conviene recalibrar el verde con ese WB fijo.")
    print("Cuadros guardados en %s" % carpeta)


if __name__ == "__main__":
    main()
