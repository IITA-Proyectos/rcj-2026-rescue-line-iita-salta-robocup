# -*- coding: utf-8 -*-
"""EL REGISTRO VISUAL COMPLETO, con la cadena SEPARADA del esqueleto.

Benjamin, 26-ago: "dame la solucion que hiciste para ver el registro visual".

Es el reemplazo de render_chunk_nuevo_code.py / render_final_nuevo_code.py, con
las dos correcciones que pedia la captura de las bifurcaciones:

  1. el esqueleto COMPLETO va en GRIS TENUE y la CADENA ELEGIDA en AMARILLO.
     El render anterior pintaba el esqueleto entero en amarillo, y eso se lee
     como si el algoritmo se hubiera ido por una costilla.
  2. renderiza CAMINO+MONO -lo que corre hoy con VISION_LINEA=camino- y no
     SinBranch, que es lo que renderizaba el anterior.

    python registro_cadena.py                      # los 10 autonomos, un mp4
    python registro_cadena.py --videos hist.avi lineal.avi
    python registro_cadena.py --salida REGISTRO_CADENA.mp4

OJO: SIN ffmpeg se usa el VideoWriter de OpenCV. Si el mp4 no se abre en el
reproductor, probar --codec avc1 o --codec XVID (y salida .avi).
"""

import argparse
import os
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ.setdefault("VISION_LINEA", "camino")

import vision_linea as VL                                     # noqa: E402
import render_cadena as RC                                    # noqa: E402

# los mismos 10 que usaba el registro anterior (con_planner tiene 0 frames)
AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner2.avi", "video_4.avi"]

FONT = cv2.FONT_HERSHEY_SIMPLEX


def tarjeta(titulo, lineas, seg=1.2, fps=33.3):
    im = np.zeros((480, 1280, 3), np.uint8)
    cv2.putText(im, titulo, (50, 90), FONT, 1.0, (70, 210, 235), 2, cv2.LINE_AA)
    y = 150
    for t in lineas:
        s, col = t if isinstance(t, tuple) else (t, (225, 225, 225))
        cv2.putText(im, s, (55, y), FONT, 0.58, col, 1, cv2.LINE_AA)
        y += 40
    return im, int(seg * fps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", nargs="*", default=None)
    ap.add_argument("--salida", default="REGISTRO_CADENA.mp4")
    ap.add_argument("--codec", default="mp4v")
    ap.add_argument("--fps", type=float, default=33.3)
    a = ap.parse_args()

    vids = a.videos or AUTONOMOS
    vids = [v for v in vids if os.path.exists(os.path.join(AQUI, v))]
    if not vids:
        print("no hay videos")
        return 1

    out = os.path.join(AQUI, a.salida)
    wr = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*a.codec), a.fps,
                         (1280, 480))
    if not wr.isOpened():
        print("no se pudo abrir el VideoWriter con codec", a.codec)
        return 1

    im, n = tarjeta("REGISTRO VISUAL - CADENA vs ESQUELETO", [
        ("gris tenue = esqueleto COMPLETO, con todas sus bifurcaciones",
         (150, 150, 150)),
        ("AMARILLO   = la CADENA que CAMINO eligio: es lo que el robot usa",
         (0, 210, 255)),
        ("X blanca   = el target FINAL, que cae sobre la cadena",
         (255, 255, 255)),
        "",
        ("candidata renderizada: CAMINO + MONO  (VISION_LINEA=camino)",
         (120, 220, 220)),
        ("el registro anterior renderizaba SinBranch y pintaba el esqueleto"
         " entero", (150, 150, 150)),
        "",
        ("REPLAY OPEN-LOOP: muestra que VIO la camara, NO por donde paso el"
         " robot", (60, 70, 250)),
    ], 4.0, a.fps)
    for _ in range(n):
        wr.write(im)

    t0 = time.time()
    tot = con = 0
    for k, v in enumerate(vids, 1):
        im, n = tarjeta("%02d / %d   %s" % (k, len(vids), v),
                        [("CAMINO + MONO", (120, 220, 220))], 1.2, a.fps)
        for _ in range(n):
            wr.write(im)
        cap = cv2.VideoCapture(os.path.join(AQUI, v))
        i = nc = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            cam = RC.panel_camara(fr)
            ang = VL.angulo(cam)
            u = VL.ultimo()
            cp = VL.__dict__.get("_CP")
            if cp and cp.CAP.get("cadena_pts"):
                nc += 1
            wr.write(RC.componer(cam, u, cp, ang, i))
            i += 1
        cap.release()
        tot += i
        con += nc
        print("  %-18s %5d frames   con cadena %5d (%3.0f %%)   %.0fs"
              % (v, i, nc, 100.0 * nc / max(i, 1), time.time() - t0),
              flush=True)

    im, n = tarjeta("FIN DEL REGISTRO", [
        ("%d frames de %d videos" % (tot, len(vids)), (225, 225, 225)),
        ("con cadena: %d (%.0f %%)" % (con, 100.0 * con / max(tot, 1)),
         (225, 225, 225)),
        "",
        ("La proxima evidencia decisiva sale del robot, no de un replay.",
         (60, 70, 250)),
    ], 3.0, a.fps)
    for _ in range(n):
        wr.write(im)
    wr.release()

    mb = os.path.getsize(out) / 1e6 if os.path.exists(out) else 0
    print("")
    print("-> %s   (%.0f MB, %d frames, %.1f min)"
          % (out, mb, tot, tot / a.fps / 60.0))
    cp = VL.__dict__.get("_CP")
    if cp:
        print("   USO de camino_principal:", cp.USO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
