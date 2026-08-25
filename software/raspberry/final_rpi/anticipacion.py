# -*- coding: utf-8 -*-
"""
DE DONDE PUEDE SALIR ANTICIPACION. Benjamin, 25-ago: "pero justamente necesito
anticipacion".

Tiene razon, y el planteo es correcto: si ninguna de las tres leyes anticipa a
las otras -medido, lag 0- entonces cambiar de ley no le da anticipacion a nadie.
Este banco mide de donde SI puede salir.

=========================== LO QUE YA ESTA MEDIDO ==========================

1. NINGUNA LEY ANTICIPA A LA OTRA.  Correlacion cruzada, lags -20 a +20:
       atan2 -> lineal   lag 0 (+1 f, corr 0,737 contra 0,734 en lag 0)
       atan2 -> Stanley  lag 0
       lineal -> Stanley lag 0
   Las tres leen el MISMO camino visible.

2. ESTIRAR EL ARCO DE psi TAMPOCO.  arco 0,30 / 0,60 / 1,30 / 2,00: lag 0 en
   todos los pares, corr 0,95 a 0,99. Y se satura: el fin del arco 1,30 y el de
   2,00 caen en el mismo Z_rel (1,59), porque EL CAMINO SE ACABA.

3. PERO HAY CAMINO SIN USAR.  Medido sobre 13.061 frames:
       el TARGET esta en la fila 77 (p50)   ->  Z_rel 1,62
       la CINTA se ve hasta la fila 45      ->  Z_rel 3,06
       el ESQUELETO llega a la fila 49      ->  Z_rel 2,75
   El target usa el 60 % de la distancia que la cinta alcanza. `LOOKAHEAD = 70`
   px geodesicos es lo que lo fija.

4. Y EL RETRASO DEL LAZO CUESTA ESTO, en grados de comando:
       retraso    p50    p75    p90       ms
       1 frame    1,1    5,6   14,6       30
       2 frames   3,4   10,1   21,4       60   <- el lag medido
       4 frames   9,0   20,2   36,0      120   <- lo que da 8,6 Hz de comando
   Eso es error PURO DE TIEMPO: la vision ya sabia la respuesta correcta y la
   Teensy estaba ejecutando la vieja.

============================ LAS DOS FUENTES ==============================

A) DEJAR DE EJECUTAR EL PASADO.  Recupera 21 grados en el p90 con 60 ms, y
   hasta 36 con 120. No pide ver mas lejos, no cambia la ley, no arriesga nada
   de percepcion, y el fix ya esta escrito (kFixLazoLineaSensoresBloqueantes).
   Para el robot, ejecutar 120 ms antes es INDISTINGUIBLE de haber anticipado
   120 ms.

B) MIRAR MAS LEJOS.  Hay margen optico -60 % de uso- y `LOOKAHEAD` es un
   parametro suelto. Tres reservas, y las tres son serias:
     * Coulter: ld <= 2*R. Con R = 4,9 cm -la curva mas cerrada del reglamento-
       eso son ~10 cm. Si Z_rel 1,62 ya son mas de 10 cm, subirlo rompe la cota
       y el controlador pasa a resolver un problema SIN SOLUCION. Y no lo se,
       porque la escala absoluta no esta medida.
     * la zona alta del cuadro es donde la segmentacion es PEOR: la cinta mide
       1 o 2 px ahi.
     * un lookahead mas largo ES mas amortiguacion, o sea MENOS reaccion en
       curva cerrada. Puede empeorar justo lo que se quiere arreglar.

Por eso A va primero: es la unica de las dos que no puede empeorar nada.

    python anticipacion.py
"""

import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

K, G = 6.1328, 0.6406


def main():
    d = SP.extraer()

    print("")
    print("=" * 92)
    print("  1) CUANTO CUESTA EL RETRASO, en grados de comando")
    print("=" * 92)
    print("")
    por = {}
    for vid in SP.AUTONOMOS:
        v, s = [], []
        for f in d.get(vid, []):
            if f["target"] is None:
                v.append(np.nan)
                s.append(np.nan)
                continue
            c = LS.componentes(f, v_norm=f["factor"], k=K, g=G)
            v.append(LS.steer_actual(f))
            s.append(np.nan if c is None else c["delta"])
        por[vid] = (np.array(v), np.array(s))
    print("  %-14s %9s %9s %9s %10s" % ("retraso", "p50", "p75", "p90", "ms"))
    for N in (1, 2, 3, 4, 6):
        A = []
        for _vid, (v, _s) in por.items():
            a = np.abs(v[N:] - v[:-N])
            A.append(a[~np.isnan(a)])
        a = np.concatenate(A)
        print("  %-14s %9.1f %9.1f %9.1f %9.0f"
              % ("%d frames" % N, *np.percentile(a, [50, 75, 90]),
                 1000 * N / (100.0 / 3.0)))
    print("")
    print("  El lag medido en el robot es 65-70 ms = 2 frames, y como el comando")
    print("  solo cambia a 8,6-20,6 Hz, en la practica son 2 a 4.")

    print("")
    print("=" * 92)
    print("  2) HAY CAMINO SIN USAR?")
    print("=" * 92)
    print("")
    vl, v2 = SP._produccion()
    ft, fc, fs = [], [], []
    for vid in SP.AUTONOMOS:
        if not os.path.exists(os.path.join(AQUI, vid)):
            continue
        vl._tr = None
        vl._arrancar()
        cap = cv2.VideoCapture(os.path.join(AQUI, vid))
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            r = vl._tr.step(v2.frame_pi(fr))
            t, comp, sk = r.get("target"), r.get("comp"), r.get("skel")
            if t is None or comp is None:
                continue
            ys, _xs = np.nonzero(comp)
            if not len(ys):
                continue
            ft.append(t[1])
            fc.append(ys.min())
            if sk is not None:
                sy, _ = np.nonzero(sk)
                if len(sy):
                    fs.append(sy.min())
        cap.release()
    ft, fc, fs = np.array(ft), np.array(fc), np.array(fs)
    print("  n = %d frames" % len(ft))
    print("")
    print("  %-30s %8s %8s %10s" % ("", "fila p50", "Z_rel", "% de uso"))
    zt = np.percentile([LS.suelo(80, x)[1] for x in ft], 50)
    zc = np.percentile([LS.suelo(80, x)[1] for x in fc], 50)
    zs = np.percentile([LS.suelo(80, x)[1] for x in fs], 50)
    print("  %-30s %8.0f %8.2f %9.0f %%"
          % ("el TARGET", np.percentile(ft, 50), zt, 100 * zt / zc))
    print("  %-30s %8.0f %8.2f" % ("el ESQUELETO llega a",
                                   np.percentile(fs, 50), zs))
    print("  %-30s %8.0f %8.2f" % ("la CINTA se ve hasta",
                                   np.percentile(fc, 50), zc))
    print("")
    print("  LOOKAHEAD = 70 px geodesicos es lo que fija el target ahi.")
    print("")
    print("=" * 92)
    print("  LAS DOS FUENTES DE ANTICIPACION")
    print("=" * 92)
    print("")
    print("  A  dejar de ejecutar el pasado   recupera 21 grados (p90) con 60 ms")
    print("     y hasta 36 con 120. No cambia la ley ni la percepcion, y el fix")
    print("     ya esta escrito. Para el robot, ejecutar 120 ms antes es")
    print("     INDISTINGUIBLE de haber anticipado 120 ms.")
    print("")
    print("  B  mirar mas lejos              hay margen optico, pero Coulter")
    print("     acota ld <= 2*R (~10 cm con R=4,9), la zona alta es donde peor")
    print("     segmenta, y mas lookahead es MAS amortiguacion, o sea MENOS")
    print("     reaccion en curva cerrada. Puede empeorar justo lo que se busca.")
    print("")
    print("  A va primero porque es la unica que no puede empeorar nada.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
