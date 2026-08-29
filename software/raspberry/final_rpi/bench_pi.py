# -*- coding: utf-8 -*-
"""BENCHMARK DE LA CANDIDATA EN LA PI. No mueve el robot.

Por que es lo primero
---------------------
La candidata V1 RC = NuevoCodeV2 + SpatialTargetGuard usa `skeletonize` de
skimage y un Dijkstra en Python puro. En la maquina de desarrollo tarda 1,0 a
1,5 ms por frame. La Pi 4B es mucho mas lenta en Python puro, y el presupuesto
del lazo es de 30 ms por frame a 33,3 fps -y ademas hay que meter ahi la
captura, el verde, el plateado, el rojo y el envio serie-.

Si no entra, la candidata no sirve y hay que saberlo AHORA, no el sabado con el
robot esperando.

Este script NO mueve el robot y NO manda nada por serie. Solo mide.

Uso en la Pi
------------
    python3 bench_pi.py                 # con la camara en vivo, 300 frames
    python3 bench_pi.py --frames 600
    python3 bench_pi.py --video hist.avi   # si copiaste un video
    python3 bench_pi.py --sin-camara       # frames sinteticos, ultimo recurso

Que mirar
---------
La linea TOTAL. Si el p95 pasa de 30 ms, el lazo no cierra a 33,3 fps.
El desglose dice DONDE se va el tiempo, que es lo que decide si se puede
arreglar o hay que cambiar de enfoque.
"""

import argparse
import importlib.util
import os
import sys
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)


def cargar():
    ruta = os.path.join(AQUI, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        raise IOError("falta nuevo_code_v4.py junto a este script")
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def candidata(v4):
    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _Nulo()
    return SinBranch


def fuente_camara(n):
    """La camara tal como la abre la Pi. Devuelve frames crudos."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    for _ in range(10):          # descartar los primeros, la camara se estabiliza
        cap.read()
    out = []
    for _ in range(n):
        ok, fr = cap.read()
        if not ok:
            break
        out.append(fr)
    cap.release()
    return out or None


def fuente_video(ruta, n):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        return None
    out = []
    while len(out) < n:
        ok, fr = cap.read()
        if not ok:
            break
        out.append(fr)
    cap.release()
    return out or None


def fuente_sintetica(n):
    """Ultimo recurso: una cinta oscura sobre piso claro, moviendose.

    NO es representativo del ruido real. Solo sirve para saber si el orden de
    magnitud entra, nunca para dar un numero definitivo.
    """
    out = []
    for k in range(n):
        f = np.full((480, 640, 3), 210, np.uint8)
        x = 320 + int(120 * np.sin(k / 12.0))
        cv2.line(f, (x, 479), (x - 60, 200), (25, 25, 25), 46)
        out.append(f)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--video", default=None)
    ap.add_argument("--sin-camara", action="store_true")
    a = ap.parse_args(argv)

    v4, _v3, v2 = cargar()
    Cls = candidata(v4)

    print("")
    print("=" * 72)
    print(" BENCHMARK DE LA CANDIDATA EN LA PI")
    print(" V2 + SpatialTargetGuard  (branch guard de V3 fuera)")
    print("=" * 72)
    print("  python  %s" % sys.version.split()[0])
    print("  opencv  %s" % cv2.__version__)
    print("  numpy   %s" % np.__version__)
    try:
        import skimage
        print("  skimage %s" % skimage.__version__)
    except Exception:
        print("  skimage NO INSTALADO  <- la candidata no puede correr")
        return 1
    try:
        t = open("/sys/class/thermal/thermal_zone0/temp").read().strip()
        print("  temp    %.1f C" % (int(t) / 1000.0))
    except Exception:
        pass
    print("")

    if a.video:
        print("  fuente: video %s" % a.video)
        frames = fuente_video(a.video if os.path.exists(a.video)
                              else os.path.join(AQUI, a.video), a.frames)
    elif a.sin_camara:
        print("  fuente: SINTETICA (no representativa del ruido real)")
        frames = fuente_sintetica(a.frames)
    else:
        print("  fuente: camara en vivo")
        frames = fuente_camara(a.frames)
        if frames is None:
            print("  no se pudo abrir la camara; probando sintetica")
            frames = fuente_sintetica(a.frames)

    if not frames:
        print("  sin frames")
        return 1
    print("  %d frames de %dx%d" % (len(frames), frames[0].shape[1],
                                    frames[0].shape[0]))
    print("")

    tr = Cls(100.0 / 3.0)

    # --- desglose por etapa -------------------------------------------------
    t_pi, t_mask, t_skel, t_step = [], [], [], []
    from skimage.morphology import skeletonize
    for fr in frames:
        t0 = time.perf_counter()
        g = v2.frame_pi(fr)
        t1 = time.perf_counter()
        m = v2.mask_linea(g)
        t2 = time.perf_counter()
        lab, cands = v2.cc_candidates(m)
        if cands:
            k = max(cands, key=lambda q: q["area"])["k"]
            skeletonize((lab == k))
        t3 = time.perf_counter()
        tr.step(g)                       # el pipeline completo
        t4 = time.perf_counter()
        t_pi.append((t1 - t0) * 1000.0)
        t_mask.append((t2 - t1) * 1000.0)
        t_skel.append((t3 - t2) * 1000.0)
        t_step.append((t4 - t3) * 1000.0)

    def linea(et, v):
        v = np.asarray(v)
        print("  %-26s %7.2f %7.2f %7.2f %7.2f"
              % (et, v.mean(), np.median(v), np.percentile(v, 95), v.max()))

    print("  %-26s %7s %7s %7s %7s" % ("etapa (ms)", "media", "p50", "p95", "max"))
    print("  " + "-" * 58)
    linea("frame_pi (rotar+resize)", t_pi)
    linea("mask_linea", t_mask)
    linea("skeletonize (una vez)", t_skel)
    linea("step COMPLETO", t_step)
    tot = np.asarray(t_pi) + np.asarray(t_step)
    print("  " + "-" * 58)
    linea("TOTAL vision de linea", tot)

    print("")
    p95 = float(np.percentile(tot, 95))
    print("  PRESUPUESTO: 30,0 ms por frame a 33,3 fps")
    print("  p95 medido : %.2f ms   -> %.0f %% del presupuesto" % (p95, 100.0 * p95 / 30.0))
    if p95 <= 15.0:
        print("  VEREDICTO: entra con margen. Queda lugar para verde/plateado/rojo.")
    elif p95 <= 30.0:
        print("  VEREDICTO: entra JUSTO. Ojo: falta sumar verde, plateado, rojo y")
        print("             el envio serie, que hoy no estan en esta medicion.")
    else:
        print("  *** VEREDICTO: NO ENTRA. El lazo no cierra a 33,3 fps. ***")
        print("  *** fps maximo con esta candidata: %.1f" % (1000.0 / p95))
    print("")
    print("  NOTA: esta medicion NO incluye la deteccion de verde, plateado ni")
    print("  rojo, ni el envio serie. Es el piso, no el total del lazo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
