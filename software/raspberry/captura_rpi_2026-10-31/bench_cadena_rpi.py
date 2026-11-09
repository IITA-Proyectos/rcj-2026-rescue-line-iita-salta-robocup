# -*- coding: utf-8 -*-
"""CUANTO CUESTA LA CADENA EN LA RASPBERRY. Se corre EN LA PI, antes de engancharla.

NO toca main.py, NO abre el puerto serie, NO mueve un motor. Solo camara y CPU.

    python3 bench_cadena_rpi.py                 # camara, 300 frames
    python3 bench_cadena_rpi.py --n 500
    python3 bench_cadena_rpi.py --video x.avi   # sobre un video, si no hay camara

POR QUE ESTE NUMERO DECIDE
--------------------------
La cadena (CAMINO/MONO) esqueletiza. Si el lazo baja de 28 a 18 fps, el robot
reacciona MAS TARDE y se sale MAS, aunque la vision sea mejor. Una mejora de
percepcion que cuesta retardo puede salir negativa en pista, y eso NO se ve
en un replay: el replay es lazo abierto.

FALSADOR, PREREGISTRADO (esto se escribe antes de correr, no despues):

    ENTRA   si el fps cae MENOS del 20 %
    DUDOSO  entre 20 y 35 %  -> solo si en pista gana claro
    NO ENTRA si cae MAS del 35 %

Se mide el DELTA sobre LOS MISMOS frames, no dos corridas distintas: el
pipeline de hoy y la cadena procesan el mismo frame, uno detras del otro.
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np

LOWER_BLACK = np.array([0, 0, 0])
UPPER_BLACK = np.array([90, 90, 90])


def pct(v, q):
    return float(np.percentile(v, q)) if len(v) else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="frames a medir")
    ap.add_argument("--video", default=None, help="usar un video en vez de la camara")
    ap.add_argument("--cam", type=int, default=0, help="indice de /dev/video*")
    args = ap.parse_args()

    if not os.environ.get("VISION_LINEA"):
        os.environ["VISION_LINEA"] = "camino"
        print("VISION_LINEA no estaba: la pongo en 'camino' para poder medir.")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import vision_linea as VL
    except Exception as e:
        sys.exit("No pude importar vision_linea (%s).\n"
                 "Copiaste vision_linea.py, camino_principal.py y nuevo_code_v2.py?" % e)
    if not VL.ACTIVA:
        sys.exit("vision_linea dice ACTIVA=False. Revisa VISION_LINEA.")

    cap = cv2.VideoCapture(args.video if args.video else args.cam)
    if not cap.isOpened():
        sys.exit("No pude abrir %s" % (args.video or "la camara %d" % args.cam))

    t_viejo, t_cadena, opino = [], [], 0
    # Un frame de calentamiento: la primera pasada de la cadena construye
    # estado y tablas. Contarlo como tipico seria mentir el numero.
    ok, fr = cap.read()
    if ok:
        f = cv2.resize(fr, (160, 120), interpolation=cv2.INTER_NEAREST)
        try:
            VL.angulo(f)
        except Exception:
            pass

    print("midiendo %d frames..." % args.n)
    n = 0
    while n < args.n:
        ok, fr = cap.read()
        if not ok:
            break
        f = cv2.resize(fr, (160, 120), interpolation=cv2.INTER_NEAREST)

        t0 = time.perf_counter()
        bm = cv2.inRange(f, LOWER_BLACK, UPPER_BLACK)
        bm[:60, :] = 0
        ys, xs = np.nonzero(bm)
        if len(xs):
            np.arctan2(ys.mean(), xs.mean())
        t1 = time.perf_counter()

        a = VL.angulo(f)
        t2 = time.perf_counter()

        t_viejo.append((t1 - t0) * 1000.0)
        t_cadena.append((t2 - t1) * 1000.0)
        if a is not None:
            opino += 1
        n += 1
    cap.release()

    if n < 20:
        sys.exit("Solo %d frames: muy pocos para concluir." % n)

    v50, c50 = pct(t_viejo, 50), pct(t_cadena, 50)
    print()
    print("frames medidos: %d      la cadena OPINO en %d (%.0f %%)" % (n, opino, 100.0 * opino / n))
    print("                     p50      p90      p99     max")
    print("  pipeline de hoy  %6.2f   %6.2f   %6.2f  %6.2f  ms"
          % (v50, pct(t_viejo, 90), pct(t_viejo, 99), max(t_viejo)))
    print("  la CADENA        %6.2f   %6.2f   %6.2f  %6.2f  ms"
          % (c50, pct(t_cadena, 90), pct(t_cadena, 99), max(t_cadena)))
    print()
    print("  la cadena AGREGA %.2f ms por frame (p50)   /  %.2f ms (p90)"
          % (c50, pct(t_cadena, 90)))
    print()
    print("QUE PASA CON EL FPS, segun a cuanto corra el lazo HOY:")
    print("   fps hoy  ->  fps con cadena   caida")
    for f_hoy in (30.0, 25.0, 20.0, 15.0):
        per = 1000.0 / f_hoy
        f_new = 1000.0 / (per + c50)
        print("     %4.0f    ->      %4.1f         %5.1f %%   %s"
              % (f_hoy, f_new, 100.0 * (f_hoy - f_new) / f_hoy,
                 "ENTRA" if (f_hoy - f_new) / f_hoy < 0.20
                 else ("dudoso" if (f_hoy - f_new) / f_hoy < 0.35 else "NO ENTRA")))
    print()
    print("OJO: el fps de hoy hay que medirlo aparte -mira lo que imprime main.py-.")
    print("Esta tabla no lo sabe: te dice que pasaria para cada valor posible.")


if __name__ == "__main__":
    main()
