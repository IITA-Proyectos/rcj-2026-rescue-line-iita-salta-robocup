# -*- coding: utf-8 -*-
"""
QUE ANGULOS VIENEN JUSTO ANTES DE QUE LA PI MANDE steer = 0.

Benjamin, 26-ago: "para darte cuenta cuando se sale tienes que ver cuando
llegue desde la raspberry un angle de 90 o un steer=0; previo a esos angulos
son los que hacen que se salga".

El marcador:  byte angle == 90  <=>  steer == 0  <=>  columna rxsteer == 0.
Y `angle = 0` es BYTE-IDENTICO a "perfectamente centrado" (el protocolo no
tiene codigo de linea perdida), asi que el Teensy manda las dos ruedas iguales
y el robot sale DERECHO A FONDO. Por eso el evento importa.

=========================== FALSADOR, ANTES DE MIRAR =========================

H-A: los episodios de `steer = 0` estan precedidos por angulos GRANDES -la
     linea saliendose del cuadro- mas de lo que se espera por azar.

SE REFUTA si CUALQUIERA de estas:

  A1  el |steer| p90 de la ventana previa no supera a la TASA BASE por 1,3x
      en algun punto de la banda
  A2  el mismo cociente contra el PLACEBO (misma ventana, -3 s) no llega a 1,3x
  A3  no hay plateau: el veredicto cambia dentro de la banda preregistrada

BANDA PREREGISTRADA
  duracion minima del episodio     50, 100, 200 ms
  ventana previa                   200, 500, 1000 ms
  umbral de rxage para "fresco"    100, 200, 400 ms

EVENTOS UNICOS: cada episodio cuenta UNA vez. La unidad es el EPISODIO.

POBLACIONES SEPARADAS, y no es opcional: hay corridas con rxage p90 de 8570 ms.
Un `steer = 0` con comando VIEJO no es la Pi diciendo "centrado", es que no
llego nada y actuo el watchdog. Mezclarlos arruina el analisis.

QUE SE MIDE ADEMAS, sin hipotesis (descriptivo)
  * la forma del angulo en la ventana: crece? oscila? cuantas inversiones?
  * cuanto tiempo estuvo SATURADO (|steer| >= 0.741, donde la ganancia 1.35
    lleva absSteer a 1.0 y de ahi a 90 grados el comando es identico)
  * que hace el robot DENTRO del episodio (rxspeed, ls, rs, gz)

    python angulos_previos.py
"""

import glob
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                     # noqa: E402

MS = 5.0
GAIN = 1.35
SAT = 1.0 / GAIN            # 0.741: de aca en adelante absSteer satura en 1.0
PIVOT = 0.92 / GAIN         # 0.681: de aca en adelante rot = 1 (no avanza)

BANDA_DUR = (50, 100, 200)          # ms minimos del episodio
BANDA_VENT = (200, 500, 1000)       # ms de ventana previa
BANDA_AGE = (100, 200, 400)         # ms: hasta aca el comando es "fresco"
PLACEBO_MS = 3000


def episodios(m, nmin):
    d = np.diff(np.concatenate([[0], m.view(np.int8), [0]]))
    ini, fin = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return [(i, f) for i, f in zip(ini, fin) if f - i >= nmin]


def main():
    rutas = [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
             if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]
    D = {}
    for r in rutas:
        a, _ = RR.cargar(r)
        if a is None or len(a) < 500:
            continue
        n = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        D[n] = dict(st=RR.col(a, "rxsteer") / 1000.0, age=RR.col(a, "rxage"),
                    sp=RR.col(a, "rxspeed"), rot=RR.col(a, "rot") / 1000.0,
                    ls=RR.col(a, "ls"), rs=RR.col(a, "rs"),
                    w=RR.col(a, "gz") / 10.0)

    print("")
    print("=" * 104)
    print("  QUE ANGULOS VIENEN ANTES DEL steer = 0")
    print("  saturacion de la ganancia en |steer| >= %.3f   |   pivote (rot=1) en"
          " >= %.3f" % (SAT, PIVOT))
    print("=" * 104)

    # ---------------- descriptivo, con la banda central -------------------
    dur0, vent0, age0 = 100, 500, 200
    nd, nv = int(dur0 / MS), int(vent0 / MS)
    print("")
    print("-" * 104)
    print("  LOS EPISODIOS, uno por uno  (episodio >= %d ms, ventana previa"
          " %d ms, fresco = rxage < %d ms)" % (dur0, vent0, age0))
    print("-" * 104)
    print("")
    print("  %-30s %6s %8s %8s %8s %8s %8s %7s %7s"
          % ("corrida", "n", "|s| p50", "|s| p90", "|s| max", "%sat",
             "%pivot", "inver", "dur ms"))

    filas = []
    for n, d in D.items():
        fresco = (d["age"] >= 0) & (d["age"] < age0)
        eps = episodios((d["st"] == 0) & fresco, nd)
        usa = [(i, f) for i, f in eps if i - nv >= 0]
        if not usa:
            print("  %-30s %6d   (ninguno con ventana completa)" % (n[:30], len(eps)))
            continue
        p50, p90, mx, sat, piv, inv, dur = [], [], [], [], [], [], []
        for i, f in usa:
            v = d["st"][i - nv:i]
            av = np.abs(v)
            p50.append(np.median(av)); p90.append(np.percentile(av, 90))
            mx.append(av.max()); sat.append(np.mean(av >= SAT))
            piv.append(np.mean(av >= PIVOT))
            s = np.sign(v[av > 0.05])
            inv.append(int(np.sum(np.diff(s) != 0)) if len(s) > 1 else 0)
            dur.append((f - i) * MS)
        filas.append((n, usa, np.median(p50), np.median(p90)))
        print("  %-30s %6d %8.3f %8.3f %8.3f %7.0f%% %7.0f%% %7.1f %7.0f"
              % (n[:30], len(usa), np.median(p50), np.median(p90),
                 np.median(mx), 100 * np.median(sat), 100 * np.median(piv),
                 np.median(inv), np.median(dur)))

    # ---------------- que hace el robot ADENTRO del episodio -------------
    print("")
    print("-" * 104)
    print("  Y QUE HACE EL ROBOT ADENTRO DEL EPISODIO  (va derecho a fondo?)")
    print("-" * 104)
    print("")
    print("  %-30s %10s %12s %12s %12s"
          % ("corrida", "rxspeed", "ls == rs", "|gz| p50", "avance cm"))
    for n, d in D.items():
        fresco = (d["age"] >= 0) & (d["age"] < age0)
        eps = episodios((d["st"] == 0) & fresco, nd)
        if not eps:
            continue
        sp, ig, gz, cm = [], [], [], []
        for i, f in eps:
            sp.append(np.median(d["sp"][i:f]))
            ig.append(np.mean(d["ls"][i:f] == d["rs"][i:f]))
            gz.append(np.median(np.abs(d["w"][i:f])))
            # rpm -> cm/s con la circunferencia efectiva, x la duracion
            cm.append(np.median(d["rs"][i:f]) / 60.0 * (3.1416 * 6.88)
                      * (f - i) * MS / 1000.0)
        print("  %-30s %10.0f %11.0f%% %12.1f %12.1f"
              % (n[:30], np.median(sp), 100 * np.median(ig), np.median(gz),
                 np.median(cm)))

    # ---------------- el falsador, en banda -------------------------------
    NC = len(BANDA_DUR) * len(BANDA_VENT) * len(BANDA_AGE)
    print("")
    print("=" * 104)
    print("  EL FALSADOR, BARRIDO EN LA BANDA PREREGISTRADA (%d combinaciones)" % NC)
    print("=" * 104)
    print("")
    print("  %5s %6s %5s %7s %10s %10s %10s %8s %8s"
          % ("dur", "vent", "age", "n epis", "|s|p90 prev", "base", "placebo",
             "lift", "lift_pb"))

    lifts, lifts_p = [], []
    for dur in BANDA_DUR:
        for vent in BANDA_VENT:
            for age in BANDA_AGE:
                nd, nv = int(dur / MS), int(vent / MS)
                npb = int(PLACEBO_MS / MS)
                prev, pbo, base_all, tot = [], [], [], 0
                for n, d in D.items():
                    fresco = (d["age"] >= 0) & (d["age"] < age)
                    base_all.append(np.abs(d["st"]))
                    for i, f in episodios((d["st"] == 0) & fresco, nd):
                        if i - nv - npb < 0:
                            continue
                        tot += 1
                        prev.append(np.percentile(np.abs(d["st"][i - nv:i]), 90))
                        j = i - npb
                        pbo.append(np.percentile(np.abs(d["st"][j - nv:j]), 90))
                if tot < 5:
                    continue
                mp = float(np.median(prev))
                mb = float(np.percentile(np.concatenate(base_all), 90))
                mq = float(np.median(pbo))
                lift = mp / mb if mb > 0 else float("nan")
                lp = mp / mq if mq > 0 else float("inf")
                lifts.append(lift); lifts_p.append(lp)
                print("  %5d %6d %5d %7d %10.3f %10.3f %10.3f %8.2f %8s"
                      % (dur, vent, age, tot, mp, mb, mq, lift,
                         ("%.2f" % lp) if np.isfinite(lp) else "inf"))

    print("")
    print("=" * 104)
    print("  VEREDICTO")
    print("=" * 104)
    print("")
    if not lifts:
        print("  SIN DATOS SUFICIENTES.")
        return 0
    lo, hi = min(lifts), max(lifts)
    lop = min([x for x in lifts_p if np.isfinite(x)] or [float("nan")])
    a1 = lo < 1.3
    a2 = (lop < 1.3) if np.isfinite(lop) else False
    a3 = (lo < 1.3) != (hi < 1.3)
    print("  lift contra tasa base   min %.2f   max %.2f" % (lo, hi))
    print("  lift contra placebo     min %.2f" % lop)
    print("")
    print("  A1  lift < 1,3 en algun punto ............ %s"
          % ("SE CUMPLE -> REFUTA" if a1 else "no"))
    print("  A2  lift vs placebo < 1,3 ............... %s"
          % ("SE CUMPLE -> REFUTA" if a2 else "no"))
    print("  A3  el veredicto cambia en la banda ..... %s"
          % ("SE CUMPLE -> SIN PLATEAU" if a3 else "no"))
    print("")
    if a1 or a2 or a3:
        print("  H-A NO SOBREVIVE tal como esta escrita.")
    else:
        print("  H-A SOBREVIVE en toda la banda: antes del `steer = 0` los")
        print("  angulos SON mas grandes que la tasa base y que el placebo.")
    print("=" * 104)
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
