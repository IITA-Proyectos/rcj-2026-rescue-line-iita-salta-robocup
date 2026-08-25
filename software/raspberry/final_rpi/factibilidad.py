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
    print("  INCERTIDUMBRES, y son grandes:")
    print("     * el DIAMETRO es un dato de Benjamin, no del codigo. Todo escala")
    print("       lineal: si la rueda es de 5 cm, v baja a %.1f cm/s."
          % (v * 5.0 / a.diametro))
    print("     * `omega_max` sale del p90 del giroscopio en esas corridas, que")
    print("       no es lo mismo que el techo del robot: si nunca se le pidio")
    print("       mas, el p90 subestima. Por eso la salida 2 empieza por BARRER.")
    print("     * las RPM del encoder son MAGNITUD, no llevan sentido.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
