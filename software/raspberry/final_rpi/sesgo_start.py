# -*- coding: utf-8 -*-
"""
EL `start` NO ESTA EN EL CENTRO DE LA CINTA. Cuanto sesga eso a `e`?

Benjamin, 25-ago, mirando el registro completo: "esas lineas de los costados son
basura a la linea, y el start no esta en el centro, fijate que esta en el
costado. Eso es lo unico a solucionar".

Lo vio a ojo y tiene razon. En `como_esta.avi` f918:

    la cinta en la fila 119 va de x=45 a x=109  ->  centro real 77,0
    el esqueleto ahi tiene DOS patas: x=48-55 y x=103-107  (las costillas del
    eje medial de una franja gruesa que dobla: hallazgo 3.4)
    el `start` quedo en x=103, o sea en la pata derecha
    -> 25,8 px de sesgo, en una imagen de 160 de ancho

POR QUE IMPORTA, Y ES UN DEFECTO MIO
------------------------------------
`ley_steer.errores()` toma el cross-track `e` EN EL `start`. Si el start cae en
una costilla lateral, `e` mide la distancia a la costilla y no a la cinta, y el
termino de POSICION de Stanley corrige un error que no existe. En f918 pide
-28,6 grados de posicion con el robot practicamente centrado.

La ley VIEJA no se ve afectada: usa el `target`, no el `start`. O sea que esto
es un defecto que YO introduje hoy al construir `e` sobre el start.

QUE SERIA LO CORRECTO
---------------------
El cross-track es la distancia lateral del robot AL CAMINO, y el camino en la
fila mas baja esta donde esta la CINTA, no donde el esqueleto puso un nodo. El
centroide de la componente en las filas mas bajas es esa posicion, y no depende
de la topologia del esqueleto.

FALSADORES, escritos antes de correr
------------------------------------
FS1  Si el p90 de |start_x - centro_real| es menor que 5 px, el sesgo es
     despreciable y no hay nada que arreglar. MUERE.

FS2  Si corregir `e` cambia el comando de Stanley en menos de 2 grados de p90,
     el arreglo es cosmetico. MUERE como politica.

FS3  Si el sesgo NO se concentra en los frames donde el esqueleto tiene varias
     patas abajo, entonces la causa no son las costillas y hay que buscar otra.

BANDA PREREGISTRADA para "cuantas filas de la componente se promedian" para
definir el centro real: 1 / 3 / 5 / 8. Si el veredicto cambia dentro de la
banda, no hay conclusion.

    python sesgo_start.py
"""

import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

BANDA_FILAS = (1, 3, 5, 8)


def centro_real(comp, filas):
    """x del centroide de la componente en las `filas` mas bajas que tiene."""
    ys, xs = np.nonzero(comp)
    if not len(xs):
        return None, None
    maxy = ys.max()
    m = ys >= maxy - (filas - 1)
    if not m.sum():
        return None, None
    return float(xs[m].mean()), int(m.sum())


def patas(skel):
    """Cuantos grupos separados tiene el esqueleto en sus 4 filas mas bajas."""
    ys, xs = np.nonzero(skel)
    if not len(xs):
        return 0
    m = ys >= ys.max() - 3
    v = sorted(set(xs[m].tolist()))
    if not v:
        return 0
    g = 1
    for a, b in zip(v, v[1:]):
        if b - a > 3:
            g += 1
    return g


def main():
    vl, v2 = SP._produccion()
    filas = []
    for vid in SP.AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        vl._tr = None
        vl._arrancar()
        cap = cv2.VideoCapture(ruta)
        i = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            r = vl._tr.step(v2.frame_pi(fr))
            st = r.get("start")
            comp = r.get("comp")
            if st is not None and comp is not None:
                fila = dict(vid=vid, i=i, sx=float(st[0]), sy=float(st[1]),
                            pat=patas(r.get("skel")) if r.get("skel") is not None
                            else 0)
                for k in BANDA_FILAS:
                    c, _n = centro_real(comp, k)
                    fila["c%d" % k] = c
                filas.append(fila)
            i += 1
        cap.release()
        print("  %-18s listo" % vid)

    print("")
    print("=" * 96)
    print("  SESGO DEL `start` CONTRA EL CENTRO REAL DE LA CINTA")
    print("  n = %d frames con start y componente" % len(filas))
    print("=" * 96)
    print("")
    print("  %-10s %9s %9s %9s %9s %11s"
          % ("filas", "|d| p50", "|d| p75", "|d| p90", "|d| max", "> 10 px"))
    for k in BANDA_FILAS:
        d = np.array([abs(f["sx"] - f["c%d" % k]) for f in filas
                      if f.get("c%d" % k) is not None])
        print("  %-10d %9.1f %9.1f %9.1f %9.1f %10.1f %%"
              % (k, np.percentile(d, 50), np.percentile(d, 75),
                 np.percentile(d, 90), d.max(), 100.0 * (d > 10).mean()))
    d3 = np.array([abs(f["sx"] - f["c3"]) for f in filas
                   if f.get("c3") is not None])
    p90 = float(np.percentile(d3, 90))
    print("")
    print("  FS1 -> %s   (p90 con 3 filas = %.1f px, muere por debajo de 5)"
          % ("*** MUERE: el sesgo es despreciable" if p90 < 5.0
             else "SOBREVIVE", p90))

    print("")
    print("=" * 96)
    print("  FS3 - EL SESGO SE CONCENTRA DONDE EL ESQUELETO TIENE VARIAS PATAS?")
    print("=" * 96)
    print("")
    print("  %-22s %9s %9s %9s" % ("patas abajo", "n", "|d| p50", "|d| p90"))
    for p in (1, 2, 3):
        sel = [f for f in filas if f["pat"] == p and f.get("c3") is not None]
        if len(sel) < 30:
            continue
        d = np.array([abs(f["sx"] - f["c3"]) for f in sel])
        print("  %-22s %9d %9.1f %9.1f"
              % ("%d" % p if p < 3 else "3 o mas", len(sel),
                 np.percentile(d, 50), np.percentile(d, 90)))
    sel = [f for f in filas if f["pat"] >= 3 and f.get("c3") is not None]
    if len(sel) >= 30:
        d = np.array([abs(f["sx"] - f["c3"]) for f in sel])
        print("  %-22s %9d %9.1f %9.1f"
              % ("3 o mas", len(sel), np.percentile(d, 50),
                 np.percentile(d, 90)))
    uno = [f for f in filas if f["pat"] <= 1 and f.get("c3") is not None]
    mas = [f for f in filas if f["pat"] >= 2 and f.get("c3") is not None]
    if uno and mas:
        du = np.percentile([abs(f["sx"] - f["c3"]) for f in uno], 90)
        dm = np.percentile([abs(f["sx"] - f["c3"]) for f in mas], 90)
        print("")
        print("  p90 con 1 pata: %.1f px    con 2 o mas: %.1f px    razon %.2fx"
              % (du, dm, dm / max(du, 1e-9)))
        print("  FS3 -> %s" % ("SOBREVIVE: son las costillas" if dm > du
                               else "*** MUERE: la causa no son las costillas"))
    print("=" * 96)

    import pickle
    with open(os.path.join(AQUI, "_sesgo.pkl"), "wb") as f:
        pickle.dump(filas, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
