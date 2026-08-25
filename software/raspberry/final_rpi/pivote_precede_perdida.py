# -*- coding: utf-8 -*-
"""
EL PIVOTE ENGANCHADO, PRECEDE A LA PERDIDA DE LINEA?

Benjamin, 26-ago: "en las curvas donde se sale en los csv (previo a tener
steer == 0 osea avanzar recto) esas son las curvas donde se sale".

LA CADENA QUE SE PROPONE  (y que este script trata de REFUTAR)

  1. curva cerrada -> absSteer sube -> se engancha el pivote (main.cpp:3750)
  2. con el pivote enganchado `rot = 1.0`, y drivebase.cpp:215 hace
     v_centro = vel*(1 - rot) = 0.  EL ROBOT GIRA SIN AVANZAR.
  3. sin avanzar, la linea se le va del campo / la curva lo pasa
  4. la Pi pierde la linea y manda `steer = 0`
  5. el Teensy lee `steer = 0` como "perfectamente centrado" y acelera DERECHO
     (ANALISIS-2026-08-23.md: `angle = 0` es byte-identico a centrado; el
     protocolo no tiene codigo de linea perdida)
  6. se va de la pista

El paso 2 ya esta MEDIDO (radio_minimo.py): el 51 % del tiempo que el robot
gira lo hace con R < 2 cm a 0,81 cm/s, con rot p50 = 1,00.

Lo que falta, y es lo que mide este script, es el ESLABON 3->4: que el episodio
de `steer = 0` este PRECEDIDO por pivote enganchado, y no sea la tasa base.

=========================== FALSADOR, ANTES DE MIRAR =========================

H-P: los episodios de `rxsteer = 0` sostenido estan precedidos por pivote
     enganchado (`|rot| = 1`) mas de lo que se espera por azar.

SE REFUTA si CUALQUIERA de estas:

  G1  el LIFT contra la TASA BASE es < 1,5x en algun punto de la banda
  G2  el LIFT contra el PLACEBO (misma ventana, desplazada -3 s) es < 1,5x
  G3  no hay plateau: el veredicto cambia dentro de la banda preregistrada

BANDA PREREGISTRADA (no se elige un punto: se barre y se exige plateau)
  duracion minima del episodio de steer=0    100, 200, 300, 400 ms
  ventana previa que se mira                 300, 500, 800 ms
  fraccion de la ventana con rot=1 que
     cuenta como "precedido"                 0,3  0,5  0,7

EVENTOS UNICOS, no muestras: cada episodio cuenta UNA vez. El bug del "al menos
uno sin break" ya mato una hipotesis en este proyecto (la anticipacion de curva,
25-ago); aca la unidad de analisis es el EPISODIO.

CONTROL: `rxage` tiene que ser bajo en los episodios contados. Un `steer = 0`
con comando VIEJO no es la Pi diciendo "centrado": es que no llego nada.

    python pivote_precede_perdida.py
"""

import glob
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                     # noqa: E402

MS = 5.0                                  # el registrador va a 200 Hz
BANDA_DUR = (100, 200, 300, 400)          # ms minimos del episodio steer=0
BANDA_VENT = (300, 500, 800)              # ms de ventana previa
BANDA_FRAC = (0.3, 0.5, 0.7)              # fraccion de la ventana con rot=1
PLACEBO_MS = 3000                         # desplazamiento del placebo


def episodios(mask, dur_min_muestras):
    """Arranques de rachas continuas de `mask` de al menos N muestras."""
    d = np.diff(np.concatenate([[0], mask.view(np.int8), [0]]))
    ini, fin = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return [(i, f) for i, f in zip(ini, fin) if f - i >= dur_min_muestras]


def main():
    rutas = [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
             if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]

    print("")
    print("=" * 100)
    print("  EL PIVOTE ENGANCHADO PRECEDE A `steer = 0`?")
    print("  eventos unicos (episodios), tasa base y placebo. Falsador en el docstring.")
    print("=" * 100)

    D = {}
    for r in rutas:
        a, _ = RR.cargar(r)
        if a is None or len(a) < 500:
            continue
        n = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        D[n] = dict(
            steer=RR.col(a, "rxsteer"),
            rot=RR.col(a, "rot"),
            age=RR.col(a, "rxage"),
            speed=RR.col(a, "rxspeed"),
        )

    # -------- control: los steer=0 son con comando FRESCO? -------------------
    print("")
    print("-" * 100)
    print("  CONTROL  un `steer = 0` con comando VIEJO no es la Pi diciendo")
    print("           'centrado': es que no llego nada. Se exige rxage bajo.")
    print("-" * 100)
    print("")
    print("  %-32s %10s %12s %12s %10s"
          % ("corrida", "steer=0", "rxage p50", "rxage p90", "speed p50"))
    for n, d in D.items():
        m = d["steer"] == 0
        print("  %-32s %9.1f %% %12.0f %12.0f %10.0f"
              % (n[:32], 100 * m.mean(), np.median(d["age"][m]),
                 np.percentile(d["age"][m], 90), np.median(d["speed"][m])))
    print("")
    print("  (rxage esta en ms. Si p90 es de miles, esos steer=0 son silencio")
    print("   de la Pi, no un comando de 'centrado', y hay que separarlos.)")

    # -------- el barrido ------------------------------------------------------
    print("")
    print("=" * 100)
    print("  BARRIDO DE LA BANDA PREREGISTRADA  (%d combinaciones)"
          % (len(BANDA_DUR) * len(BANDA_VENT) * len(BANDA_FRAC)))
    print("=" * 100)
    print("")
    print("  %6s %7s %6s %8s %10s %10s %9s %9s"
          % ("dur", "vent", "frac", "n epis", "precedido", "base", "lift", "lift_pbo"))

    lifts, lifts_p, filas = [], [], []
    for dur in BANDA_DUR:
        for vent in BANDA_VENT:
            for frac in BANDA_FRAC:
                nd = int(dur / MS)
                nv = int(vent / MS)
                tot = pre = pbo = 0
                base_num = base_den = 0
                for n, d in D.items():
                    piv = np.abs(d["rot"]) >= 999          # pivote enganchado
                    fresco = d["age"] < 200                # ms
                    m = (d["steer"] == 0) & fresco
                    base_num += piv.sum()
                    base_den += len(piv)
                    for i, _f in episodios(m, nd):
                        if i - nv < 0 or i - nv - int(PLACEBO_MS / MS) < 0:
                            continue
                        tot += 1
                        if piv[i - nv:i].mean() >= frac:
                            pre += 1
                        j = i - int(PLACEBO_MS / MS)
                        if piv[j - nv:j].mean() >= frac:
                            pbo += 1
                if tot < 5:
                    continue
                p_pre = pre / tot
                p_base = base_num / max(base_den, 1)
                p_pbo = pbo / tot
                lift = p_pre / p_base if p_base > 0 else float("nan")
                lift_p = p_pre / p_pbo if p_pbo > 0 else float("inf")
                lifts.append(lift)
                lifts_p.append(lift_p)
                filas.append((dur, vent, frac, tot, p_pre, p_base, lift, lift_p))
                print("  %6d %7d %6.1f %8d %9.1f %% %9.1f %% %9.2f %9s"
                      % (dur, vent, frac, tot, 100 * p_pre, 100 * p_base, lift,
                         ("%.2f" % lift_p) if np.isfinite(lift_p) else "inf"))

    print("")
    print("=" * 100)
    print("  VEREDICTO")
    print("=" * 100)
    print("")
    if not lifts:
        print("  SIN DATOS SUFICIENTES: menos de 5 episodios en toda la banda.")
        print("  No se concluye nada. (Y eso ya es un resultado: si `steer = 0`")
        print("  sostenido casi no ocurre, la cadena propuesta no es el camino.)")
        return 0

    lo, hi = min(lifts), max(lifts)
    lop = min([x for x in lifts_p if np.isfinite(x)] or [float("nan")])
    g1 = lo < 1.5
    g2 = (lop < 1.5) if np.isfinite(lop) else False
    g3 = (lo < 1.5) != (hi < 1.5)
    print("  lift contra tasa base    min %.2f   max %.2f" % (lo, hi))
    print("  lift contra placebo      min %s"
          % (("%.2f" % lop) if np.isfinite(lop) else "inf (el placebo nunca precede)"))
    print("")
    print("  G1  lift < 1,5 en algun punto de la banda ......... %s"
          % ("SE CUMPLE -> REFUTA" if g1 else "no"))
    print("  G2  lift vs placebo < 1,5 ........................ %s"
          % ("SE CUMPLE -> REFUTA" if g2 else "no"))
    print("  G3  el veredicto cambia dentro de la banda ....... %s"
          % ("SE CUMPLE -> SIN PLATEAU" if g3 else "no"))
    print("")
    if g1 or g2 or g3:
        print("  H-P NO SOBREVIVE tal como esta escrita.")
        print("  OJO: esto refuta el ESLABON 3->4 medido asi, NO refuta que el")
        print("  pivote enganchado deje al robot sin avanzar: eso es algebra")
        print("  (v = vel*(1-rot), rot=1 -> v=0) y esta medido aparte.")
    else:
        print("  H-P SOBREVIVE en toda la banda: el pivote enganchado precede a")
        print("  `steer = 0` mas que el azar y mas que el placebo.")
    print("=" * 100)
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
