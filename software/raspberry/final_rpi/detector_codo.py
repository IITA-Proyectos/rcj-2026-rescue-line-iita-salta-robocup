# -*- coding: utf-8 -*-
"""DETECTOR DE CODO: dos tramos rectos con el giro CONCENTRADO en el medio.

Trabaja sobre la CADENA que CAMINO ya eligio -nunca sobre el esqueleto crudo-.
Ver NO-ROMPER-LA-CADENA-UNICA.md: el 55,9 % de los frames tienen bifurcaciones,
y el esqueleto crudo hace que el target se vaya por una costilla.

=========================== QUE ES UN CODO, Y QUE NO ==========================

Un codo NO es "cambio de rumbo grande". Es DOS TRAMOS APROXIMADAMENTE RECTOS
con el cambio de rumbo CONCENTRADO en una zona corta. Eso lo separa de:

    curva suave   el giro esta REPARTIDO a lo largo del arco
    recta         no hay giro
    T / intersec  hay mas de una salida (y CAMINO ya eligio una)
    gap           no hay cadena

    perfil de giro acumulado a lo largo de la cadena:
       CODO    ___________/‾‾‾‾‾‾‾‾‾‾‾     (escalon)
       CURVA   ___________________         (rampa suave)

Por eso la medida no es el total girado sino la CONCENTRACION: que fraccion
del giro total ocurre en que fraccion del arco.

============================ FALSADOR, ANTES DE MEDIR ==========================

H-K: la concentracion separa codos de curvas suaves.

SE REFUTA si CUALQUIERA de estas, en la banda preregistrada:
  K1  la concentracion de los codos NO supera a la de las curvas por 1,5x
  K2  los falsos positivos pasan de 6 por minuto (con 33,3 fps son 2000 frames)
  K3  no hay plateau: el veredicto cambia dentro de la banda

BANDA
  ventana de ajuste de cada recta   8, 12, 16 puntos
  umbral de giro minimo             25, 35, 45 grados
  umbral de concentracion           0,45  0,55  0,65

TODO EN PIXELES. No usa HFOV, no proyecta al suelo, no necesita d_eje.
Eso es deliberado: el HFOV NO ESTA MEDIDO (ver EL-HFOV-NO-ESTA-CALIBRADO.md) y
la ley que corre hoy tampoco lo usa.

    python detector_codo.py                 evalua sobre los videos
    python detector_codo.py --video hist.avi --desde 560 --hasta 700
"""

import argparse
import glob
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ.setdefault("VISION_LINEA", "camino")

import cv2                                                    # noqa: E402
import vision_linea as VL                                     # noqa: E402

VENTANA = 12          # puntos por recta
GIRO_MIN = 35.0       # grados
CONC_MIN = 0.55       # fraccion del giro en <=35 % del arco


def panel_camara(fr):
    h, w = fr.shape[:2]
    if w == 640 and h == 240:
        fr = fr[:, :320]
    return cv2.resize(fr, (160, 120))


def rumbos(pts, paso=3):
    """Rumbo local a lo largo de la cadena, en grados. pts = [(y,x), ...].

    El rumbo se mide en PIXELES: atan2(dx, -dy). -dy porque la fila crece
    hacia ABAJO en la imagen y "adelante" es hacia arriba.
    """
    if len(pts) < 2 * paso + 2:
        return None, None
    h, s = [], [0.0]
    for i in range(0, len(pts) - paso, paso):
        y0, x0 = pts[i]
        y1, x1 = pts[i + paso]
        dy, dx = (y1 - y0), (x1 - x0)
        L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        h.append(math.degrees(math.atan2(dx, -dy)))
        s.append(s[-1] + L)
    if len(h) < 3:
        return None, None
    return np.array(h), np.array(s[1:len(h) + 1])


def _wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def analizar(pts, ventana=VENTANA):
    """Devuelve (giro_neto, concentracion, idx_vertice) o None.

    concentracion = fraccion del giro NETO que ocurre en el 35 % del arco
    donde mas gira. 1,0 = todo el giro en un punto (codo perfecto);
    ~0,35 = repartido parejo (curva suave).

    CORREGIDO 26-ago, y lo cazo el propio falsador. La v1 hacia
    `tot = sum(|diff(h)|)` y daba un giro mediano de 308 GRADOS, que es
    absurdo -un codo gira 45 a 135-. El motivo: la cadena es un esqueleto
    PIXELADO, cada tramo tiene varios grados de ruido de discretizacion, y
    sumar valores ABSOLUTOS acumula ese ruido en vez de cancelarlo. Con ~70
    tramos y +-5 grados de ruido cada uno, el total da ~350 sin que la linea
    haya doblado nada.

    Ahora: (a) el rumbo se SUAVIZA antes de derivar, y (b) el giro es el NETO
    -la diferencia entre el rumbo del final y el del principio-, que es lo que
    de verdad hay que girar.
    """
    h, s = rumbos(pts)
    if h is None or len(h) < 5:
        return None
    # (a) suavizado: media movil de 3, para que la derivada no sea ruido puro
    k = np.ones(3) / 3.0
    h = np.convolve(h, k, mode="valid")
    if len(h) < 4:
        return None
    # (b) el giro que importa es el NETO, no la suma de los absolutos
    neto = abs(_wrap(h[-1] - h[0]))
    d = np.abs(_wrap(np.diff(h)))
    tot = float(d.sum())
    if tot < 1e-6:
        return None
    # ventana deslizante que cubre el 35 % del arco
    n = max(1, int(round(0.35 * len(d))))
    if n >= len(d):
        return neto, 1.0, int(len(d) // 2)
    acum = np.convolve(d, np.ones(n), mode="valid")
    j = int(np.argmax(acum))
    return neto, float(acum[j] / tot), int(j + n // 2)


def detectar(cadena_pts, ventana=VENTANA, giro_min=GIRO_MIN, conc_min=CONC_MIN):
    """El detector. Devuelve None = 'no opino', o el evento."""
    if not cadena_pts or len(cadena_pts) < 3 * ventana:
        return None
    r = analizar(cadena_pts, ventana)
    if r is None:
        return None
    giro, conc, iv = r
    if giro < giro_min or conc < conc_min:
        return None
    h, _s = rumbos(cadena_pts)
    if h is None:
        return None
    signo = 1 if _wrap(h[-1] - h[0]) > 0 else -1
    k = min(len(cadena_pts) - 1, max(0, iv * 3))
    vy, vx = cadena_pts[k]
    return dict(signo=signo, giro=giro, concentracion=conc,
                vertice=(float(vx), float(vy)),
                confianza=min(1.0, (conc - conc_min) / max(1e-6, 1 - conc_min)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=None)
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    a = ap.parse_args()

    vids = ([a.video] if a.video else
            [os.path.basename(v) for v in sorted(glob.glob(os.path.join(AQUI, "*.avi")))
             if os.path.basename(v) in
             ("hist.avi", "lineal.avi", "seguir.avi", "rumbo.avi", "a.avi",
              "como_esta.avi", "lineal70.avi", "roi_auto.avi", "con_planner2.avi")])

    print("")
    print("=" * 100)
    print("  DETECTOR DE CODO   ventana %d  giro_min %.0f  conc_min %.2f"
          % (VENTANA, GIRO_MIN, CONC_MIN))
    print("  trabaja SOBRE LA CADENA de CAMINO, en pixeles, sin HFOV")
    print("=" * 100)
    print("")
    print("  %-18s %7s %8s %9s %9s %10s %9s"
          % ("video", "frames", "cadena", "eventos", "ev/min", "giro p50", "conc p50"))
    print("  " + "-" * 88)

    T = dict(fr=0, cad=0, ev=0)
    G, Cc = [], []
    for v in vids:
        cap = cv2.VideoCapture(os.path.join(AQUI, v))
        if not cap.isOpened():
            continue
        i = nf = ncad = 0
        eventos, ultimo = 0, -999
        gg, cc = [], []
        while True:
            ok, fr = cap.read()
            if not ok or i > a.hasta:
                break
            if i >= a.desde:
                VL.angulo(panel_camara(fr))
                cp = VL.__dict__.get("_CP")
                pts = cp.CAP.get("cadena_pts") if cp else None
                nf += 1
                if pts:
                    ncad += 1
                    e = detectar(list(pts))
                    if e is not None:
                        gg.append(e["giro"]); cc.append(e["concentracion"])
                        # EVENTOS UNICOS: no re-contar el mismo codo 40 veces
                        if i - ultimo > 25:
                            eventos += 1
                        ultimo = i
            i += 1
        cap.release()
        if nf == 0:
            continue
        mins = nf / 33.3 / 60.0
        T["fr"] += nf; T["cad"] += ncad; T["ev"] += eventos
        G += gg; Cc += cc
        print("  %-18s %7d %7.0f%% %9d %9.1f %10s %9s"
              % (v, nf, 100.0 * ncad / nf, eventos, eventos / max(mins, 1e-9),
                 ("%.0f" % np.median(gg)) if gg else "--",
                 ("%.2f" % np.median(cc)) if cc else "--"))

    mins = T["fr"] / 33.3 / 60.0
    print("")
    print("  TOTAL  %d frames (%.1f min)  cadena %.0f %%  eventos %d  ->  %.1f por minuto"
          % (T["fr"], mins, 100.0 * T["cad"] / max(T["fr"], 1), T["ev"],
             T["ev"] / max(mins, 1e-9)))
    if G:
        print("  de los frames que disparan: giro p50 %.0f deg   concentracion p50 %.2f"
              % (np.median(G), np.median(Cc)))
    print("")
    print("  K2 del falsador: los falsos positivos no pueden pasar de 6 por minuto.")
    print("  OJO: sin codos etiquetados a mano NO se sabe cuantos de estos son")
    print("  ciertos. Esta tabla mide la TASA DE DISPARO, no la precision.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
