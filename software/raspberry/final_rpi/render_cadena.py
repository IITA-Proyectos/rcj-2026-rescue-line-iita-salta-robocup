# -*- coding: utf-8 -*-
"""RENDER QUE SEPARA LA CADENA ELEGIDA DEL ESQUELETO COMPLETO.

Benjamin, 26-ago, con dos capturas: "necesito que no tenga las bifurcaciones del
esqueleto al costado como en otras versiones; ya lo arreglaste, no lo vuelvas a
arruinar".

Y ChatGPT, que escribio el render anterior, lo confirma: "en el panel amarillo
dibuja el skeleton completo... habria que agregar una visualizacion distinta de
active_path / rama seleccionada, separada del skeleton completo".

=================== LAS DOS COSAS QUE ARREGLA ===================

1. EL RENDER ANTERIOR DIBUJABA EL ESQUELETO ENTERO EN AMARILLO
   (render_chunk_nuevo_code.py:118-121)
       sk = d.get('skel')
       ss = resize_keep((sk>0)...)
       pan[ss] = (0,200,240)
   O sea que las bifurcaciones se veian TAN brillantes como el camino real, y
   eso se lee como si el algoritmo se hubiera ido por una costilla -cuando en
   realidad CAMINO ya restringe los candidatos a UNA cadena-.

   Aca: esqueleto completo en GRIS TENUE, cadena elegida en AMARILLO. Se ve de
   un vistazo que lo que el algoritmo usa es una sola cadena.

2. EL RENDER ANTERIOR CORRIA `SinBranch = V2 + SpatialTargetGuard`
   (render_chunk_nuevo_code.py:31-32), que NO es lo que corre hoy.
   Aca se renderiza CAMINO+MONO, que es lo que sale con VISION_LINEA=camino.

=================== DE DONDE SALE LA CADENA ===================

`camino_principal.py` la calcula en su bloque CAMINO y ahora la expone en
`CAP["cadena_pts"]` (instrumentacion pura: escribe un dict de captura, el flujo
no la lee).

OJO CON ALGO QUE CUESTA MEDIA HORA SI NO SE SABE: `vision_linea` NO hace
`import camino_principal`, lo carga con `spec_from_file_location`, o sea que es
una INSTANCIA SEPARADA. La buena esta en `vision_linea._CP`, no en el modulo que
importes vos. Verificado: leyendo la instancia equivocada, USO da todo 0 y
parece que CAMINO no corre.

    python render_cadena.py hist.avi 560 700
    python render_cadena.py hist.avi 560 700 --mp4 salida.mp4
"""

import argparse
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ.setdefault("VISION_LINEA", "camino")

import vision_linea as VL                                     # noqa: E402

ESC = 4                     # 160x120 -> 640x480
FONT = cv2.FONT_HERSHEY_SIMPLEX


def panel_camara(fr):
    """Del video de debug de 640x240 saca la imagen de la camara, 160x120."""
    h, w = fr.shape[:2]
    if w == 640 and h == 240:
        fr = fr[:, :320]
    return cv2.resize(fr, (160, 120))


def txt(im, s, xy, sc=0.5, col=(230, 230, 230), th=1):
    cv2.putText(im, str(s), xy, FONT, sc, col, th, cv2.LINE_AA)


def marca(pan, p, col, lab, mk):
    if p is None:
        return
    x, y = int(round(p[0] * ESC)), int(round(p[1] * ESC))
    cv2.drawMarker(pan, (x, y), col, mk, 20, 2, cv2.LINE_AA)
    txt(pan, lab, (min(x + 8, 610), max(16, y - 8)), 0.45, col)


def componer(cam, u, cp, ang, i):
    out = np.zeros((480, 1280, 3), np.uint8)
    out[:, :640] = cv2.resize(cam, (640, 480), interpolation=cv2.INTER_NEAREST)

    pan = np.zeros((480, 640, 3), np.uint8)

    # 1) el esqueleto COMPLETO, en gris tenue: se ve que existe, no compite
    sk = u.get("skel")
    if sk is not None:
        m = cv2.resize((np.asarray(sk) > 0).astype(np.uint8), (640, 480),
                       interpolation=cv2.INTER_NEAREST) > 0
        pan[m] = (70, 70, 70)

    # 2) LA CADENA ELEGIDA, en amarillo brillante: es lo que el algoritmo USA
    pts = cp.CAP.get("cadena_pts") if cp else None
    if pts:
        for (y, x) in pts:
            cv2.circle(pan, (int(x * ESC), int(y * ESC)), 2, (0, 210, 255), -1)

    cv2.line(pan, (320, 0), (320, 479), (90, 90, 90), 1)
    marca(pan, u.get("raw"), (60, 60, 255), "raw", cv2.MARKER_CROSS)
    marca(pan, u.get("cap"), (0, 165, 255), "cap", cv2.MARKER_DIAMOND)
    marca(pan, u.get("target"), (255, 255, 255), "FINAL", cv2.MARKER_TILTED_CROSS)
    out[:, 640:] = pan

    txt(out, "CAMARA", (10, 22), 0.55, (240, 240, 240))
    txt(out, "esqueleto COMPLETO (gris)  +  CADENA ELEGIDA (amarillo)",
        (650, 22), 0.5, (240, 240, 240))
    txt(out, "gris = ramas que el esqueleto tiene y CAMINO DESCARTA",
        (650, 44), 0.42, (150, 150, 150))
    n = len(pts) if pts else 0
    est = u.get("estado", "")
    txt(out, "frame %d | modo %s | estado %s | cadena %d px | angulo %s"
        % (i, VL.estado().get("modo", "?"), est, n,
           ("%+.1f" % ang) if ang is not None else "--"),
        (10, 466), 0.5, (210, 210, 210))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("desde", type=int, nargs="?", default=0)
    ap.add_argument("hasta", type=int, nargs="?", default=10 ** 9)
    ap.add_argument("--mp4", default=None)
    ap.add_argument("--png", default=None, help="contact sheet en vez de video")
    a = ap.parse_args()

    cap = cv2.VideoCapture(os.path.join(AQUI, a.video))
    if not cap.isOpened():
        print("no se pudo abrir", a.video)
        return 1
    wr = None
    if a.mp4:
        wr = cv2.VideoWriter(a.mp4, cv2.VideoWriter_fourcc(*"mp4v"),
                             33.3, (1280, 480))
    tiles, i, n_cad = [], 0, 0
    while True:
        ok, fr = cap.read()
        if not ok or i > a.hasta:
            break
        if i >= a.desde:
            cam = panel_camara(fr)
            ang = VL.angulo(cam)
            u = VL.ultimo()
            cp = VL.__dict__.get("_CP")          # la instancia BUENA
            if cp and cp.CAP.get("cadena_pts"):
                n_cad += 1
            im = componer(cam, u, cp, ang, i)
            if wr is not None:
                wr.write(im)
            if a.png and (i - a.desde) % 12 == 0 and len(tiles) < 6:
                tiles.append(cv2.resize(im, (640, 240)))
        i += 1
    cap.release()
    if wr is not None:
        wr.release()
        print("mp4 ->", a.mp4)
    if a.png and tiles:
        cv2.imwrite(a.png, np.vstack(tiles))
        print("png ->", a.png)
    tot = min(i, a.hasta + 1) - a.desde
    print("frames %d | con cadena %d (%.0f %%)"
          % (tot, n_cad, 100.0 * n_cad / max(tot, 1)))
    cp = VL.__dict__.get("_CP")
    if cp:
        print("USO de camino_principal:", cp.USO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
