# -*- coding: utf-8 -*-
"""Saca las fotos del tablero para calibrar_camara.py. Corre EN LA PI, por SSH.

No hace falta pantalla ni cinta metrica: calibrar_camara.py usa unidades
arbitrarias (np.mgrid), asi que el HFOV sale sin medir el tablero. Solo tiene
que ser PLANO y con los cuadrados iguales -sirve mostrarlo en la pantalla del
celular-.

    python3 capturar_tablero.py                # 20 fotos, una cada 3 s
    python3 capturar_tablero.py --n 24 --cada 4

Va contando en voz alta por consola. Entre foto y foto MOVE el tablero:

    * al CENTRO y a las CUATRO ESQUINAS del cuadro
    * inclinado en distintos angulos, no siempre de frente
    * a veces ocupando medio cuadro, a veces casi todo

Las de las ESQUINAS son las que fijan la distorsion y son las que no se sacan.
Sin ellas el resultado sale lindo y es mentira.

Despues, en la PC:
    python calibrar_camara.py tablero/
"""
import argparse
import os
import time

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="cuantas fotos")
    ap.add_argument("--cada", type=float, default=3.0, help="segundos entre fotos")
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--dir", default="tablero")
    ap.add_argument("--filas", type=int, default=6, help="esquinas INTERNAS")
    ap.add_argument("--cols", type=int, default=9, help="esquinas INTERNAS")
    a = ap.parse_args()

    os.makedirs(a.dir, exist_ok=True)
    cap = cv2.VideoCapture(a.cam)
    if not cap.isOpened():
        raise SystemExit("no pude abrir la camara %d" % a.cam)

    print("%d fotos, una cada %.0f s. Move el tablero entre foto y foto." % (a.n, a.cada))
    print("Ctrl-C para cortar; lo que ya se guardo sirve igual.\n")
    buenas = 0
    try:
        for i in range(1, a.n + 1):
            for s in range(int(a.cada), 0, -1):
                print("   foto %2d/%d en %d..." % (i, a.n, s), end="\r")
                time.sleep(1)
            for _ in range(5):          # drenar el buffer: si no, sale una vieja
                ok, fr = cap.read()
            if not ok:
                print("   foto %2d: la camara no entrego frame" % i)
                continue
            ruta = os.path.join(a.dir, "tab_%02d.jpg" % i)
            cv2.imwrite(ruta, fr)
            # Aviso EN EL MOMENTO si el tablero no se ve: sirve de poco
            # enterarse en la PC media hora despues.
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            visto, _ = cv2.findChessboardCorners(
                g, (a.cols, a.filas),
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK)
            buenas += 1 if visto else 0
            print("   foto %2d/%d  %s   %s" % (i, a.n, ruta,
                                               "tablero OK" if visto else "NO se ve el tablero"))
    except KeyboardInterrupt:
        print("\ncortado.")
    cap.release()
    print("\n%d fotos con tablero detectado, de %d." % (buenas, a.n))
    if buenas < 10:
        print("OJO: con menos de 10 la calibracion no es confiable.")
    print("Copialas a la PC y corre:  python calibrar_camara.py %s/" % a.dir)


if __name__ == "__main__":
    main()
