# -*- coding: utf-8 -*-
"""CUANTO RECORRE EL ROBOT POR CADA GRADO QUE GIRA. UN SOLO SCRIPT, REPRODUCIBLE.

Lo pidio ChatGPT en su auditoria del 26-ago, y con razon: yo habia publicado DOS
numeros que no cierran entre si.

    dije A:  R trazado 7,3 cm   ->  en 90 grados recorre 11,5 cm
    dije B:  0,080 cm/grado     ->  en 90 grados recorre  7,2 cm
    y 0,080 cm/grado son 4,58 cm/rad, NO 7,3.  Factor 1,59.

NO ERA UN ERROR DE ARITMETICA: son dos estimadores distintos sobre poblaciones
distintas -A es un tramo de 3 s de UNA corrida, B es la mediana por frame sobre
las SEIS-. Pero los presente juntos como si fueran lo mismo, y eso induce a
error. Este script los calcula LOS DOS, con la misma carga de datos, y muestra
la distribucion entera en vez de un numero suelto.

=================== Y UNA CORRECCION DE NOMBRE, TAMBIEN SUYA ===================

Lo que se mide NO es "el avance del centro del robot". Es:

    (v_izq + v_der) / 2   reconstruido de los encoders

y los encoders de este robot son de UN SOLO CANAL (drivebase.cpp:8,
`Moto(pwmPin, dirPin, encPin)`; main.cpp:2913, `attachInterrupt(..., CHANGE)`;
y `pulsesRaw++` dice literalmente "crudo, sin signo"). El sentido se INFIERE del
comando de direccion, no se mide.

Y en un skid steer de 4 ruedas fijas durante un pivote, las ruedas BARREN
superficie con el chasis casi quieto. O sea:

    recorrido de rueda / giro   !=   traslacion del centro / giro

Por eso aca se llama **RECORRIDO DE RUEDA POR GRADO**, que es lo que realmente
se mide. Para tener traslacion del centro hace falta filmar el chasis desde
arriba, o marcarlo en el piso. Eso NO esta hecho.

    python recorrido_por_grado.py
"""

import glob
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                     # noqa: E402
import radio_minimo as RM                                     # noqa: E402

DIAM = 6.88                  # cm, efectivo de rodadura
LAG = 14                     # muestras; el lag comando->giro ya medido
CIRC = math.pi * DIAM


def cargar(ruta):
    a, _ = RR.cargar(ruta)
    if a is None or len(a) < 500:
        return None
    vi, vd = RM.signo_ruedas(a)
    vc = (vi + vd) / 2.0 * CIRC / 60.0       # cm/s, RECORRIDO DE RUEDA
    w = RR.col(a, "gz") / 10.0               # deg/s, giroscopio del BNO
    yaw = RR.col(a, "yaw") / 10.0
    d = np.diff(yaw)
    d = np.where(d > 180, d - 360, np.where(d < -180, d + 360, d))
    yw = np.concatenate([[0.0], np.cumsum(d)])
    return vc, w, yw


def main():
    rutas = [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
             if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]
    print("")
    print("=" * 96)
    print("  RECORRIDO DE RUEDA POR GRADO GIRADO")
    print("  rueda %.2f cm   lag %d muestras   |   NO es traslacion del centro"
          % (DIAM, LAG))
    print("=" * 96)

    # ---------------- ESTIMADOR B: por frame, sobre las seis ----------------
    print("")
    print("-" * 96)
    print("  B) POR FRAME, todas las corridas   (|gz| > 25 deg/s y vc > 0,5 cm/s)")
    print("-" * 96)
    print("")
    print("  %-30s %9s %9s %9s %9s %8s"
          % ("corrida", "p25", "p50", "p75", "p90", "n"))
    tod = []
    for r in rutas:
        z = cargar(r)
        if z is None:
            continue
        vc, w, _ = z
        n = len(vc) - LAG
        v, wl = vc[:n], np.abs(w[LAG:LAG + n])
        m = (wl > 25) & (v > 0.5) & np.isfinite(v)
        if m.sum() < 100:
            continue
        cg = v[m] / wl[m]                    # cm por grado
        tod.append(cg)
        print("  %-30s %9.3f %9.3f %9.3f %9.3f %8d"
              % (os.path.basename(r)[11:-4][:30],
                 np.percentile(cg, 25), np.median(cg),
                 np.percentile(cg, 75), np.percentile(cg, 90), m.sum()))
    T = np.concatenate(tod)
    print("")
    print("  GLOBAL   p25=%.3f  p50=%.3f  p75=%.3f  p90=%.3f   n=%d cm/grado"
          % (np.percentile(T, 25), np.median(T), np.percentile(T, 75),
             np.percentile(T, 90), len(T)))
    print("")
    print("  en un codo de 90 grados eso es   p25 %4.1f   p50 %4.1f   p75 %4.1f"
          "   p90 %4.1f  cm de RECORRIDO DE RUEDA"
          % (90 * np.percentile(T, 25), 90 * np.median(T),
             90 * np.percentile(T, 75), 90 * np.percentile(T, 90)))
    print("")
    print("  OJO CON LA DISPERSION: el p90 es %.1fx el p25. Publicar solo la"
          % (np.percentile(T, 90) / max(np.percentile(T, 25), 1e-9)))
    print("  mediana esconde eso, y fue parte del problema de los dos numeros.")

    # ---------------- ESTIMADOR A: por tramo largo -------------------------
    print("")
    print("-" * 96)
    print("  A) POR TRAMO LARGO, integrando 3 s   (es lo que dio el 7,3 cm/rad)")
    print("-" * 96)
    print("")
    print("  %-30s %9s %10s %11s %11s"
          % ("corrida", "giro deg", "recorr cm", "cm/grado", "cm/rad"))
    for r in rutas:
        z = cargar(r)
        if z is None:
            continue
        vc, w, yw = z
        N = 600                              # 3 s a 200 Hz
        best, bi = 0.0, 0
        for i in range(0, len(yw) - N, 50):
            g = abs(yw[i + N] - yw[i])
            if g > best:
                best, bi = g, i
        s = slice(bi, bi + N)
        rec = float(np.nansum(np.where(vc[s] > 0, vc[s], 0) * 0.005))
        if best < 1:
            continue
        print("  %-30s %9.0f %10.1f %11.3f %11.2f"
              % (os.path.basename(r)[11:-4][:30], best, rec,
                 rec / best, rec / math.radians(best)))

    print("")
    print("=" * 96)
    print("  POR QUE LOS DOS NUMEROS NO COINCIDEN, Y CUAL USAR")
    print("=" * 96)
    print("")
    print("  A integra un tramo de 3 s ENTERO: adentro hay pedazos donde el robot")
    print("    casi no gira y sigue recorriendo, y eso INFLA el cm/grado.")
    print("  B toma solo los frames en que esta girando de verdad (|gz| > 25).")
    print("")
    print("  Para disenar la maniobra del codo sirve B, porque el codo es")
    print("  justamente el rato en que el robot ESTA girando. A sobreestima.")
    print("")
    print("  PERO NINGUNO DE LOS DOS ES TRASLACION DEL CENTRO. Los dos salen de")
    print("  encoders de un canal con el signo inferido del comando, en un skid")
    print("  steer que patina. Para cerrar el numero de verdad hace falta marcar")
    print("  el chasis en el piso, o filmarlo desde arriba. NO ESTA HECHO.")
    print("=" * 96)
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
