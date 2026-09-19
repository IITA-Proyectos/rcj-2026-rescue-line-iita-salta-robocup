# -*- coding: utf-8 -*-
"""
65-70 ms DE RETARDO, EN CENTIMETROS Y EN GRADOS.

Benjamin, 25-ago: "65 y 70 ms de retardo es mucho? 65 mm es el diametro de la
rueda".

La coincidencia numerica es casual -65 ms y 65 mm son unidades distintas- pero
la pregunta de fondo es la correcta: un retardo en milisegundos no significa
nada hasta que se traduce a cuanto se movio el robot mientras tanto.

Y AHORA SE PUEDE, porque los CSV del 22-ago traen las RPM de las cuatro ruedas y
el giroscopio en la misma fila. Con el diametro de rueda:

    v = RPM/60 * pi * D           avance, cm/s
    distancia en 70 ms = v * 0,070
    giro en 70 ms      = |gz| * 0,070

DIAMETRO: 65 mm, dato de Benjamin. No esta en el codigo ni en config.h, asi que
si el numero real es otro, este script se corre con --diametro y listo.

CONTRA QUE SE COMPARA
---------------------
    ancho de la cinta         2,0 cm    (RCJ: cinta de ~2 cm)
    radio de curva cerrada    4,9 cm    (RCJ 2.2.2: radio interno >= 40 mm)
    diametro de la rueda      6,5 cm
    ancho del cuadro a la
    fila 119                  ~44 % de 160 px, o sea la cinta ocupa 71 px

    python cuanto_es_el_retardo.py
    python cuanto_es_el_retardo.py --diametro 6.5 --lag-ms 70
"""

import argparse
import glob
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                     # noqa: E402

ANCHO_CINTA_CM = 2.0
R_CERRADA_CM = 4.9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diametro", type=float, default=6.5,
                    help="diametro de rueda en cm (dato de Benjamin: 65 mm)")
    ap.add_argument("--lag-ms", type=float, default=70.0)
    a = ap.parse_args()

    circ = math.pi * a.diametro
    print("")
    print("=" * 96)
    print("  EL RETARDO EN CENTIMETROS Y EN GRADOS")
    print("  rueda de %.1f cm -> %.1f cm de circunferencia   ·   lag %.0f ms"
          % (a.diametro, circ, a.lag_ms))
    print("=" * 96)
    print("")
    print("  %-32s %9s %9s %11s %11s"
          % ("corrida", "RPM p50", "v cm/s", "avanza cm", "gira deg"))
    Vs, Gs = [], []
    for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv"))):
        arr, _nota = RR.cargar(r)
        if arr is None or len(arr) < 200:
            continue
        nom = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        if not nom.startswith("pista"):
            continue                       # en banco el robot no avanza
        rpm = np.vstack([RR.col(arr, "%s_rpm" % w)
                         for w in ("fl", "fr", "bl", "br")])
        # `_realrpm` es 111111/promedio y puede dar valores absurdos: se acota a
        # un rango fisicamente posible antes de promediar.
        rpm = np.where((rpm > 0) & (rpm < 500), rpm, np.nan)
        vr = np.nanmean(rpm, axis=0)
        vr = vr[~np.isnan(vr)]
        if not len(vr):
            continue
        rpm50 = float(np.percentile(vr, 50))
        v = rpm50 / 60.0 * circ
        gz = np.abs(RR.col(arr, "gz") / 10.0)
        gz = gz[gz < 400]
        g50 = float(np.percentile(gz, 50))
        Vs.append(v)
        Gs.append(g50)
        print("  %-32s %9.0f %9.1f %11.2f %11.1f"
              % (nom[:32], rpm50, v, v * a.lag_ms / 1000.0,
                 g50 * a.lag_ms / 1000.0))

    if not Vs:
        print("  sin corridas de pista utiles")
        return 1
    v = float(np.median(Vs))
    g = float(np.median(Gs))
    d = v * a.lag_ms / 1000.0
    gr = g * a.lag_ms / 1000.0

    print("")
    print("=" * 96)
    print("  MEDIANA DE LAS CORRIDAS DE PISTA")
    print("=" * 96)
    print("")
    print("  el robot avanza a          %.1f cm/s" % v)
    print("  y gira a                   %.0f grados/s" % g)
    print("")
    print("  EN LOS %.0f ms DE RETARDO:" % a.lag_ms)
    print("     avanza                  %.2f cm" % d)
    print("     gira                    %.1f grados" % gr)
    print("")
    print("  CONTRA QUE COMPARARLO")
    print("     ancho de la cinta       %.1f cm   ->  el robot avanza %.1f anchos"
          % (ANCHO_CINTA_CM, d / ANCHO_CINTA_CM))
    print("     diametro de la rueda    %.1f cm   ->  %.2f de vuelta de rueda"
          % (a.diametro, d / circ))
    print("     radio de curva cerrada  %.1f cm   ->  %.0f %% del radio"
          % (R_CERRADA_CM, 100.0 * d / R_CERRADA_CM))
    print("")
    arco = math.radians(gr) * R_CERRADA_CM
    print("  Y EN UNA CURVA DE RADIO %.1f cm:" % R_CERRADA_CM)
    print("     una curva de 90 grados tiene %.1f cm de arco"
          % (math.radians(90) * R_CERRADA_CM))
    print("     en el retardo el robot recorre %.2f cm de ese arco  = %.0f %%"
          % (d, 100.0 * d / (math.radians(90) * R_CERRADA_CM)))
    print("     y gira %.1f grados de los 90  = %.0f %%"
          % (gr, 100.0 * gr / 90.0))
    print("")
    print("=" * 96)
    print("  LA LECTURA")
    print("=" * 96)
    print("")
    if d > ANCHO_CINTA_CM:
        print("  El robot avanza MAS QUE EL ANCHO DE LA CINTA mientras espera el")
        print("  comando. O sea que cuando la orden llega, la cinta ya no esta")
        print("  donde estaba cuando se la vio.")
    else:
        print("  El robot avanza MENOS que el ancho de la cinta en ese tiempo.")
        print("  En recta eso es despreciable; en curva cerrada no tanto.")
    print("")
    print("  Y la comparacion que mas dice: en una curva de 90 grados de radio")
    print("  %.1f cm, el robot se come el %.0f %% de la curva a ciegas."
          % (R_CERRADA_CM, 100.0 * d / (math.radians(90) * R_CERRADA_CM)))
    print("")
    print("  LIMITACION: la velocidad sale de las RPM del encoder, que informan")
    print("  MAGNITUD y no sentido, y `_realrpm` puede dar valores absurdos -es")
    print("  111111/promedio-. Se acota a 0-500 RPM antes de promediar. Y el")
    print("  diametro es un dato de Benjamin, no del codigo: si es otro, todo")
    print("  escala lineal con el.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
