# -*- coding: utf-8 -*-
"""
LA CURVA, ES FISICAMENTE POSIBLE A ESA VELOCIDAD?

Salio de la pregunta de Benjamin del 25-ago: "65 y 70 ms de retardo es mucho?".
Para contestarla hubo que convertir el retardo a centimetros, y para eso hubo que
sacar la velocidad real del robot de las RPM del encoder. Y ahi aparecio otra
cosa.

Es el punto 1 del checklist de la skill `seguimiento-de-trayectoria`, y dice
textualmente que suele cerrar el caso:

    v_max = omega_max * R

Si el robot va mas rapido que eso, SE VA DE LA PISTA Y NINGUN ARREGLO DE VISION
LO CAMBIA. Nunca se habia calculado con datos del robot.

LOS DATOS, todos de los CSV del 22-ago
---------------------------------------
    RPM medidas por el encoder      set p50 ~ rpm p50, o sea que el PID sigue
                                    la consigna: 16 a 35 RPM segun la corrida
    giro real por el giroscopio     p90 de 36,8 a 71,8 grados/s
    diametro de rueda               6,5 cm (dato de Benjamin; no esta en el
                                    codigo, y todo escala lineal con el)
    radio de la curva mas cerrada   4,9 cm (RCJ 2.2.2: radio interno >= 40 mm)

Las RPM son CREIBLES: la consigna y la medida coinciden -16/16, 20/19, 35/30,
20/20- con caida solo en las dos corridas de pivote (43/32 y 41/30), que es
justo donde el skid steer patina.

    python factibilidad.py
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

R_CERRADA = 4.9          # cm, RCJ 2.2.2
R_SUAVE = 15.0           # cm, cuarto de circulo en un tile de 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diametro", type=float, default=6.5)
    a = ap.parse_args()
    circ = math.pi * a.diametro

    print("")
    print("=" * 100)
    print("  FACTIBILIDAD CINEMATICA   v_max = omega_max * R")
    print("  rueda %.1f cm -> %.1f cm de circunferencia" % (a.diametro, circ))
    print("=" * 100)
    print("")
    print("  %-30s %8s %9s %9s %11s %10s"
          % ("corrida", "RPM p50", "v cm/s", "gz p90", "v_max cm/s", "veredicto"))
    Vs, Gs = [], []
    for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv"))):
        arr, _n = RR.cargar(r)
        if arr is None or len(arr) < 200:
            continue
        nom = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        if not nom.startswith("pista"):
            continue
        rpm = np.vstack([RR.col(arr, "%s_rpm" % w)
                         for w in ("fl", "fr", "bl", "br")])
        rpm = np.where((rpm > 0) & (rpm < 500), rpm, np.nan)
        v = float(np.nanpercentile(rpm, 50)) / 60.0 * circ
        gz = np.abs(RR.col(arr, "gz") / 10.0)
        gz = gz[gz < 200]                 # >200 deg/s es ruido del giroscopio
        w90 = float(np.percentile(gz, 90))
        vmax = math.radians(w90) * R_CERRADA
        Vs.append(v)
        Gs.append(w90)
        print("  %-30s %8.0f %9.1f %9.1f %11.1f %10s"
              % (nom[:30], np.nanpercentile(rpm, 50), v, w90, vmax,
                 "OK" if v <= vmax else "*** NO"))

    v = float(np.median(Vs))
    w = float(np.median(Gs))
    print("")
    print("=" * 100)
    print("  MEDIANA DE LAS SEIS CORRIDAS DE PISTA")
    print("=" * 100)
    print("")
    print("  el robot avanza a           %.1f cm/s" % v)
    print("  y su giro sostenido p90 es  %.1f grados/s = %.3f rad/s"
          % (w, math.radians(w)))
    print("")
    for nom, R in (("curva mas cerrada del reglamento", R_CERRADA),
                   ("curva suave (tile de 30 cm)", R_SUAVE)):
        vmax = math.radians(w) * R
        wnec = math.degrees(v / R)
        print("  %s  (R = %.1f cm)" % (nom, R))
        print("     v_max admisible        %.1f cm/s" % vmax)
        print("     el robot va a          %.1f cm/s   ->  %s"
              % (v, "OK, %.0f %% del limite" % (100 * v / vmax) if v <= vmax
                 else "*** %.0f %% POR ENCIMA del limite" % (100 * (v / vmax - 1))))
        print("     giro que la curva EXIGE  %.0f grados/s   (el robot da %.0f)"
              % (wnec, w))
        print("")

    print("=" * 100)
    print("  LO QUE ESTO SIGNIFICA")
    print("=" * 100)
    print("")
    vmax = math.radians(w) * R_CERRADA
    if v > vmax:
        print("  A la velocidad a la que el robot iba el 22-ago, la curva mas")
        print("  cerrada del reglamento NO ES FISICAMENTE POSIBLE. No es que el")
        print("  controlador elija mal: no existe una trayectoria que la tome a")
        print("  esa velocidad con ese giro.")
        print("")
        print("  Las tres salidas, y hay que elegir UNA:")
        print("     1. FRENAR en curva hasta %.1f cm/s (o menos)" % vmax)
        print("     2. SUBIR el giro. El techo NO es fisico: LINE_PIVOT_SPEED")
        print("        por la ganancia de giro. Hay que BARRER ese parametro y")
        print("        confirmar que la respuesta se aplana antes de declarar un")
        print("        techo. Esta delegado en el issue #2 de Roboliga.")
        print("     3. GIRAR EN EL LUGAR: determinista pero caro, ~2,3 s por")
        print("        cada 90 grados a 39 grados/s.")
    else:
        print("  A esta velocidad la curva ES posible. El problema no es")
        print("  cinematico y el esfuerzo va al retardo y a la ley.")
    print("")
    print("=" * 100)
    print("  EL DIAMETRO CAMBIA EL NUMERO, NO EL VEREDICTO")
    print("=" * 100)
    print("")
    print("  Benjamin pregunto si los 65 mm son CON las gomas. Importa, porque el")
    print("  que cuenta es el diametro EFECTIVO DE RODADURA: la rueda con la")
    print("  banda puesta y COMPRIMIDA bajo el peso del robot, medida en el punto")
    print("  de contacto. Con silicona Shore A20-30 la compresion es de 1 a 3 mm,")
    print("  asi que el efectivo es algo MENOR que el libre.")
    print("")
    rpm50 = float(np.nanmedian([np.nanpercentile(
        np.where((np.vstack([RR.col(RR.cargar(r)[0], "%s_rpm" % w)
                             for w in ("fl", "fr", "bl", "br")]) > 0) &
                 (np.vstack([RR.col(RR.cargar(r)[0], "%s_rpm" % w)
                             for w in ("fl", "fr", "bl", "br")]) < 500),
                 np.vstack([RR.col(RR.cargar(r)[0], "%s_rpm" % w)
                            for w in ("fl", "fr", "bl", "br")]), np.nan), 50)
        for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
        if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]))
    vmax49 = math.radians(w) * R_CERRADA
    print("  %-14s %10s %10s %11s %16s"
          % ("diametro", "circunf", "v cm/s", "v/v_max", "veredicto"))
    for D in (4.445, 5.08, 6.0, 6.35, 6.5, 7.0, 7.62, 8.5):
        c = math.pi * D
        vv = rpm50 / 60.0 * c
        print("  %-14s %10.1f %10.1f %10.2fx %16s"
              % ("%.2f cm" % D, c, vv, vv / vmax49,
                 "OK" if vv <= vmax49 else "%.0f %% por encima"
                 % (100 * (vv / vmax49 - 1))))
    dcrit = vmax49 * 60 / rpm50 / math.pi
    print("")
    print("  Para que la curva cerrada fuera POSIBLE la rueda tendria que medir")
    print("  %.2f cm. Ninguna rueda de robot mide eso." % dcrit)
    print("")
    print("  -> LA CONCLUSION NO DEPENDE DEL DIAMETRO. Con cualquier rueda entre")
    print("     44 y 85 mm el robot esta entre 24 % y 137 % por encima del")
    print("     limite. Con gomas o sin gomas, la curva cerrada no da.")
    print("")
    print("  Y COMO SE MIDE BIEN, sin calibre y sin suponer: hacer rodar el robot")
    print("  una distancia MEDIDA -un metro alcanza- y contar los pulsos del")
    print("  encoder. `runDistance()` ya imprime flCount y frCount.")
    print("")
    print("      D_efectivo = distancia / (vueltas * pi)")
    print("")
    print("  Eso da el diametro EFECTIVO directo, con la goma puesta, comprimida")
    print("  y sobre la superficie real. Es lo unico que importa y sale gratis.")
    print("")
    print("=" * 100)
    print("  OTRAS INCERTIDUMBRES")
    print("=" * 100)
    print("")
    print("     * `omega_max` sale del p90 del giroscopio en esas corridas, que")
    print("       no es lo mismo que el techo del robot: si nunca se le pidio")
    print("       mas, el p90 subestima. Por eso la salida 2 empieza por BARRER.")
    print("     * las RPM del encoder son MAGNITUD, no llevan sentido.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
