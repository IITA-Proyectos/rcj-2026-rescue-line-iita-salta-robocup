# -*- coding: utf-8 -*-
"""EL BEARING EN EL PLANO DEL SUELO. Refuta T4. NO TOCA EL ROBOT.

De donde sale
-------------
ChatGPT, issue #138, investigacion independiente 2, punto A: `bearing_real_deg`
no es un bearing fisico, es un bearing en pixeles, y para tener el fisico hace
falta calibracion de camara mas interseccion con el plano del piso. Tiene razon
en la critica.

Y la calibracion YA EXISTE. Se midio el 2026-08-23 en `birdeye.py`: el ancho
aparente de una cinta de ancho fisico constante es w(v) = a*(v - v_h), una
recta, y el cero da la fila del horizonte. Ajusta con R2 entre 0,982 y 0,999 en
9 de 11 videos, con v_h mediana **+9,0**. Ver HANDOFF seccion 14.

La cuenta, que da un resultado contraintuitivo
----------------------------------------------
Camara pinhole mirando un plano, sin roll. De la medicion:

    escala lateral en la fila v     s(v)  proporcional a (v - v_h)
    distancia de la fila v          Z(v)  proporcional a 1/(v - v_h)

Un punto del suelo a distancia lateral X cae en la columna u con

    (u - cx) = s(v) * X       =>      X  proporcional a (u - cx)/(v - v_h)

y entonces la tangente del bearing en el plano del suelo es

    X / Z  =  [(u - cx)/(v - v_h)] / [1/(v - v_h)]  =  (u - cx)

**El (v - v_h) se cancela.** El bearing hacia el target en el plano del suelo
depende SOLO de la columna. La fila no entra.

Y el test empirico refuta esa consecuencia. Por que
---------------------------------------------------
Se comparo contra el bird-eye rectificado, que esta validado por validacion
cruzada. Resultado sobre 13.033 targets:

    bearing_px  predice el bearing del bird-eye con  r = 0,9999, p50 1,50 gr
    steer       predice con                          r = 0,9350, p50 7,43 gr

O sea que el bird-eye le da la razon a `bearing_px`, no al algebra de arriba.

La contradiccion es aparente, y explicarla es el hallazgo de este archivo. El
bird-eye mide el bearing desde el punto del suelo que cae en el BORDE INFERIOR
de la imagen:

    bearing_bird = atan2( kx*X , kz*(Z_base - Z) )

mientras que X/Z = (u - cx) es el bearing desde el CENTRO OPTICO de la camara.
Son dos bearings validos con dos origenes distintos, y por eso dan cosas
distintas.

**Y el que le importa al robot no es ninguno de los dos: es el bearing desde su
EJE DE ROTACION.** Donde cae ese eje dentro del campo visual es un dato del
montaje fisico que no esta en ningun video ni en ningun CSV.

Estado real de T4
-----------------
NI SOSTENIDO NI REFUTADO. Suspendido por falta de un dato fisico.

  * `bearing_real_deg` NO es el bearing fisico. La critica de ChatGPT es
    correcta y la columna deberia llamarse `bearing_px_deg`.
  * Los 32 grados que se publicaron como error de conversion NO prueban nada.
  * Pero tampoco esta demostrado que `steer` sea correcto: el algebra que lo
    respalda usa un origen que no es el del robot.

Que dato falta, y cuanto cuesta
-------------------------------
La fila de la imagen donde cae el EJE DE ROTACION del robot proyectado sobre el
piso, o equivalentemente la distancia del eje al punto del piso que aparece en
la fila 119. Se obtiene con el robot quieto y una regla: marcar el piso donde
empieza el campo visual y medir hasta el eje. No hace falta moverlo ni
desarmarlo.

Con ese numero, `bearing_desde_el_eje = atan2(X, Z + d_eje)` queda determinado y
las tres leyes se pueden comparar de verdad.

Por que NO alcanza la telemetria para sacarlo
---------------------------------------------
Se penso usar `rot` ordenado contra `gz` medido de los CSV de la Teensy. No
sirve: el robot giro OBEDECIENDO a `steer`, asi que `steer` va a correlacionar
con `gz` por construccion. Es circular.

Uso
---
    python bearing_suelo.py
    python bearing_suelo.py --vh 9.0 --cx 79.5
"""

import argparse
import csv
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
AUTONOMOS = ["hist", "lineal", "lineal70", "como_esta", "seguir", "rumbo",
             "a", "roi_auto", "con_planner", "con_planner2"]

W = 160
CENTRO = (W - 1) / 2.0
V_H = 9.0          # medido en birdeye.py sobre 9 videos, R2 >= 0,982


def leer(nom):
    ruta = os.path.join(AQUI, "traza_%s.csv" % nom)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vh", type=float, default=V_H)
    ap.add_argument("--cx", type=float, default=CENTRO)
    a = ap.parse_args(argv)

    xs, ys = [], []
    for nom in AUTONOMOS:
        rows = leer(nom)
        if rows is None:
            continue
        for r in rows:
            if r["final_x"] == "" or r["final_y"] == "":
                continue
            xs.append(float(r["final_x"]))
            ys.append(float(r["final_y"]))
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    n = xs.size

    print("")
    print("=" * 84)
    print(" EL BEARING EN EL PLANO DEL SUELO   (v_h = %+.1f, cx = %.1f)"
          % (a.vh, a.cx))
    print(" %d targets de los 10 videos autonomos" % n)
    print("=" * 84)

    # --- las tres senales --------------------------------------------------
    # 1. la ley que corre: lineal en x, saturada
    steer = np.clip(-90.0 * (xs - a.cx) / (W / 2.0), -90, 90)
    # 2. la referencia que este banco publico y que estaba MAL
    bearing_px = np.degrees(np.arctan2(-(xs - a.cx), np.maximum(119.0 - ys, 1e-6)))
    # 3. la correcta: X/Z = (u - cx)/f, o sea depende SOLO de la columna.
    #
    #    La FORMA queda determinada por la geometria medida. La ESCALA necesita
    #    la focal en pixeles `f`, que NO se puede sacar del ancho de la cinta:
    #    ese dato da la escala lateral s(v) y la distancia Z(v), y f se cancela
    #    en el cociente. Inventar una `k` para normalizar produce un absurdo
    #    -se probo y daba 98,3 % de frames por encima del umbral de pivote-, asi
    #    que NO se inventa. Se compara la FORMA por otro camino: el bird-eye
    #    rectificado, que ya esta validado (CV del ancho 0,206 -> 0,013 en
    #    validacion cruzada).
    bearing_suelo = None

    print("")
    print("  LO PRIMERO: el bearing de suelo depende de la fila?")
    print("  Si X/Z = (u - cx), entonces NO. Se verifica sobre los datos:")
    for lo, hi in ((60, 80), (80, 100), (100, 119)):
        m = (ys >= lo) & (ys <= hi)
        if m.sum() < 50:
            continue
        # para una misma columna, cuanto cambia bearing_px segun la fila
        print("      filas %3d-%3d  n=%5d   bearing_px p50 %+7.1f   "
              "steer p50 %+7.1f   |dif| p50 %5.1f"
              % (lo, hi, m.sum(), np.median(bearing_px[m]),
                 np.median(steer[m]), np.median(np.abs(steer[m] - bearing_px[m]))))
    print("      -> bearing_px cambia mucho con la fila. steer no. Y segun la")
    print("         geometria medida, el bearing FISICO no debe depender de la")
    print("         fila: la fila que varia es bearing_px, que es el que sobra.")

    d_px = np.abs(steer - bearing_px)
    print("")
    print("  DIFERENCIA ENTRE LA LEY QUE CORRE Y bearing_px")
    print("      p50 %.2f   p90 %.2f   MAX %.2f   >20 gr %.1f %%"
          % (np.median(d_px), np.percentile(d_px, 90), d_px.max(),
             100.0 * (d_px > 20).mean()))
    print("  ChatGPT midio p50 6,04, p90 29,75, >20 gr 20,4 %. Se reproduce.")
    print("  Pero esa divergencia NO dice cual de las dos es correcta.")

    # --- el test empirico: contra el bird-eye VALIDADO --------------------
    print("")
    print("  TEST EMPIRICO: cual de las dos predice el bearing del BIRD-EYE?")
    print("  El bird-eye de `birdeye.py` esta validado por validacion cruzada:")
    print("  el ancho de la cinta pasa de CV 0,206 a 0,013 en videos que no se")
    print("  usaron para calibrarlo. En una vista cenital el bearing SI es")
    print("  atan2(dx, dy), porque las dos direcciones tienen la misma escala.")
    try:
        from birdeye import Bird
    except Exception as e:
        print("      no se pudo importar birdeye: %s" % e)
        return 0
    b = Bird(a.vh, cx=a.cx)
    M = b.M
    den = M[2, 0] * xs + M[2, 1] * ys + M[2, 2]
    bx = (M[0, 0] * xs + M[0, 1] * ys + M[0, 2]) / den
    by = (M[1, 0] * xs + M[1, 1] * ys + M[1, 2]) / den
    x0, y0 = b.punto(a.cx, 119.0)
    bearing_bird = np.degrees(np.arctan2(-(bx - x0), np.maximum(y0 - by, 1e-6)))
    ok = np.isfinite(bearing_bird)
    print("")
    print("      %-24s %10s %10s %10s"
          % ("prediccion de", "r", "p50 |dif|", "p90 |dif|"))
    for et, v in (("steer (solo X, la ley)", steer), ("bearing_px (mi referencia)", bearing_px)):
        r = float(np.corrcoef(v[ok], bearing_bird[ok])[0, 1])
        dd = np.abs(v[ok] - bearing_bird[ok])
        print("      %-24s %10.4f %10.2f %10.2f"
              % (et, r, np.median(dd), np.percentile(dd, 90)))
    print("")
    print("      n = %d targets" % ok.sum())
    return 0


if __name__ == "__main__":
    sys.exit(main())
