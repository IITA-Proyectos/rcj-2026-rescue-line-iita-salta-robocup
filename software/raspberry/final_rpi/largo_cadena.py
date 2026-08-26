# -*- coding: utf-8 -*-
"""LA CADENA ES MAS CORTA EN EL CODO? Idea de Benjamin, 26-ago.

    "puedes reanalizar todos los frames de los videos cuanto miden los
     esqueletos mas largos? porque la mayoria son unas L en donde se sale,
     pero una L sin tanta longitud"

POR QUE ESTA IDEA ES DISTINTA DE LAS DOS QUE FALLARON
-----------------------------------------------------
Los dos detectores anteriores median CURVATURA LOCAL sobre el eje medial, y
murieron por la misma razon: en la fila 115 la cinta ocupa 71 px de 160, y el
eje medial de una mancha asi se desvia +-35 px sin que la cinta doble nada.
El ruido era mayor que la senal.

El LARGO de la cadena es una propiedad GLOBAL: no depende de donde caiga el eje
medial en cada fila, sino de hasta donde llega la cinta. Un codo se sale del
cuadro; una recta llega hasta arriba. Es la misma clase de senal que la "cadena
que pasa de vertical a horizontal" que quedo anotada como pista sin medir.

Y respeta la restriccion dura: se mide sobre la CADENA que CAMINO ya eligio
-`cad`, y `dist[F]` que la propia candidata ya calculo-, NUNCA sobre el
esqueleto crudo. No recalcula nada ni vuelve a las bifurcaciones.

TRES MEDIDAS, no una, porque no se cual es la buena:
    dist[F]     largo geodesico de la cadena (lo que la candidata ya calculo)
    len(cad)    cantidad de puntos de la cadena
    fila_top    la fila MAS ALTA que alcanza la cadena. Menor = ve mas lejos.
                Es la mas directa para "la L es corta".

=========================== FALSADOR, ANTES DE MEDIR ===========================

H: en los frames del tramo donde el robot SE SALE, la cadena es mas corta
   (y llega menos arriba) que en el resto del mismo video.

GRUPOS, dentro del MISMO video para no confundir con luz ni pista:
    FALLA   hist.avi frames 1354-1490   (el tramo marcado como caso de falla)
    RESTO   hist.avi, todo lo demas
    PLACEBO hist.avi frames 1200-1336   (mismo largo, justo ANTES de la falla)

SE FALSA SI:
  * el lift de la mediana FALLA vs RESTO es < 1,3 en las tres medidas, o
  * el PLACEBO da un lift parecido al de FALLA -entonces no es el codo, es
    "cualquier tramo de esa parte del video"-, o
  * las distribuciones se solapan tanto que el AUC < 0,70.

AUC = probabilidad de que un frame de FALLA tomado al azar tenga la cadena mas
corta que uno de RESTO tomado al azar. 0,50 es el azar. Se reporta SIEMPRE,
tambien si sale mal.

    python largo_cadena.py
    python largo_cadena.py --video hist.avi --falla 1354 1490
"""
import argparse
import math
import os
import sys

import numpy as np

try:
    import cv2
except Exception as e:                                        # pragma: no cover
    sys.exit("hace falta opencv: %s" % e)

AQUI = os.path.dirname(os.path.abspath(__file__))


def panel_camara(fr):
    """hist.avi y compania son 640x240: DOS paneles de 320x240.

    El izquierdo es la camara, el derecho la mascara de debug. Medir sobre los
    dos juntos invalido un analisis entero el 26-ago (error #5 del traspaso).
    Aca se recorta el izquierdo y se lleva a los 160x120 en que trabaja el
    pipeline.
    """
    h, w = fr.shape[:2]
    if w == 2 * h * 320 // 240 or (w, h) == (640, 240):
        fr = fr[:, :w // 2]
    return cv2.resize(fr, (160, 120), interpolation=cv2.INTER_NEAREST)


def medidas_del_frame(VL):
    """Lee la cadena que la candidata ACABA de calcular. No recalcula nada."""
    cp = VL._CP
    if cp is None or "dist" not in cp.CAP:
        return None
    pts, dist = cp.CAP["pts"], cp.CAP["dist"]
    prev, si = cp.CAP["prev"], cp.CAP["si"]
    fin = np.where(np.isfinite(dist))[0]
    if len(fin) < 8:
        return None
    F = int(fin[int(np.argmax(dist[fin]))])
    cad = VL._v2.reconstruct(prev, si, F)
    if not cad or len(cad) < 4:
        return None
    filas = [pts[i][0] for i in cad]
    return dict(largo=float(dist[F]), npts=len(cad), fila_top=float(min(filas)))


def auc(a, b):
    """P(x de `a` < y de `b`). 0,5 = azar. Mann-Whitney sin scipy."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if not len(a) or not len(b):
        return float("nan")
    todo = np.concatenate([a, b])
    r = todo.argsort().argsort().astype(float) + 1
    # empates: promedio de rangos
    orden = np.sort(todo)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and orden[j + 1] == orden[i]:
            j += 1
        if j > i:
            m = (i + j) / 2.0 + 1
            r[np.argsort(todo)[i:j + 1]] = m
        i = j + 1
    ra = r[:len(a)].sum()
    u = ra - len(a) * (len(a) + 1) / 2.0
    return 1.0 - u / (len(a) * len(b))


def resumen(nombre, d, campos):
    if not d[campos[0]]:
        print("  %-10s  (sin frames)" % nombre)
        return
    fila = "  %-10s n=%4d " % (nombre, len(d[campos[0]]))
    for c in campos:
        v = np.array(d[c], float)
        fila += " | %s p50=%7.1f p25=%7.1f" % (c, np.median(v), np.percentile(v, 25))
    print(fila)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="hist.avi")
    ap.add_argument("--falla", nargs=2, type=int, default=[1354, 1490])
    ap.add_argument("--placebo", nargs=2, type=int, default=[1200, 1336])
    a = ap.parse_args()

    os.environ.setdefault("VISION_LINEA", "camino")
    sys.path.insert(0, AQUI)
    import vision_linea as VL
    if not VL.ACTIVA:
        sys.exit("vision_linea dice ACTIVA=False")

    ruta = a.video if os.path.exists(a.video) else os.path.join(AQUI, a.video)
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        sys.exit("no pude abrir %s" % ruta)

    CAMPOS = ("largo", "npts", "fila_top")
    grupos = {k: {c: [] for c in CAMPOS} for k in ("FALLA", "PLACEBO", "RESTO")}
    n, sin_cadena = 0, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        f = panel_camara(fr)
        try:
            VL.angulo(f)                     # corre el pipeline entero
        except Exception:
            pass
        m = medidas_del_frame(VL)
        if m is None:
            sin_cadena += 1
        else:
            if a.falla[0] <= n <= a.falla[1]:
                g = "FALLA"
            elif a.placebo[0] <= n <= a.placebo[1]:
                g = "PLACEBO"
            else:
                g = "RESTO"
            for c in CAMPOS:
                grupos[g][c].append(m[c])
        n += 1
    cap.release()

    print("video: %s   frames=%d   sin cadena usable: %d (%.1f %%)"
          % (os.path.basename(ruta), n, sin_cadena, 100.0 * sin_cadena / max(n, 1)))
    print("FALLA = %d-%d   PLACEBO = %d-%d   RESTO = el resto\n"
          % (a.falla[0], a.falla[1], a.placebo[0], a.placebo[1]))
    for k in ("FALLA", "PLACEBO", "RESTO"):
        resumen(k, grupos[k], CAMPOS)

    print("\nCONTRA EL FALSADOR (escrito antes de correr esto):")
    print("  %-10s %10s %10s %10s" % ("medida", "lift F/R", "lift P/R", "AUC F vs R"))
    veredicto = []
    for c in CAMPOS:
        R = np.array(grupos["RESTO"][c], float)
        F = np.array(grupos["FALLA"][c], float)
        P = np.array(grupos["PLACEBO"][c], float)
        if not len(R) or not len(F):
            continue
        mR = np.median(R)
        lf = mR / np.median(F) if np.median(F) else float("nan")
        lp = mR / np.median(P) if len(P) and np.median(P) else float("nan")
        au = auc(F, R)                       # F mas CHICO que R -> AUC alto
        print("  %-10s %10.2f %10.2f %10.3f" % (c, lf, lp, au))
        veredicto.append((c, lf, lp, au))

    print()
    sirve = [c for c, lf, lp, au in veredicto
             if lf >= 1.3 and au >= 0.70 and (np.isnan(lp) or lp < lf * 0.7)]
    if sirve:
        print("  PASA el falsador: %s" % ", ".join(sirve))
        print("  (lift >= 1,3, AUC >= 0,70, y el placebo NO reproduce el efecto)")
    else:
        print("  NO PASA. Ninguna de las tres medidas separa el codo del resto")
        print("  con los umbrales preregistrados. Mirar la columna que falla:")
        print("    lift bajo   -> la cadena no es mas corta en el codo")
        print("    AUC bajo    -> las distribuciones se solapan")
        print("    lift P alto -> el efecto tambien esta ANTES del codo, o sea")
        print("                   que no es el codo lo que lo produce")


if __name__ == "__main__":
    main()
