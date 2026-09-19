# -*- coding: utf-8 -*-
"""
LAS CURVAS QUE EL ROBOT TRAZO DE VERDAD, UNA POR UNA. Y como termino cada una.

Benjamin, 26-ago: "lo de la curva no se pueden chequear con los videos de
cuanto dan las curvas previas del robot al salirse de las zonas?"

Si, pero NO con los videos: con los CSV, y sale mejor.

  * el replay de video es LAZO ABIERTO. Mide que VIO la camara, no por donde
    paso el robot. Es la regla que ya esta escrita en el traspaso.
  * los CSV del Teensy tienen `yaw` (BNO055, absoluto, x10) y las RPM de las
    cuatro ruedas en la misma fila. Con eso se reconstruye la TRAYECTORIA por
    dead reckoning y se mide el radio de cada curva de verdad.

El yaw es del sensor de FUSION del BNO055, o sea que no acumula deriva de
integracion como lo haria integrar `gz`. Lo unico que se integra es la
POSICION, y para medir el radio de una curva de 1-2 segundos eso alcanza:
el error de posicion crece con el tiempo, pero el radio sale de v/omega, que
es instantaneo.

QUE HACE
  1. reconstruye (x, y) por dead reckoning
  2. parte la corrida en CURVAS: episodios de giro sostenido
  3. para cada curva mide radio, velocidad, angulo girado y duracion
  4. clasifica COMO TERMINO: sigue linea / `steer=0` sostenido (la Pi perdio
     la linea) / el watchdog freno
  5. compara las curvas que terminan bien contra las que terminan en perdida

    python curvas_reales.py
    python curvas_reales.py --fig
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
import radio_minimo as RM                                     # noqa: E402

R_CERRADA = 4.9
DT = 0.005                     # el registrador va a 200 Hz


def desenvolver(g):
    """yaw 0..360 con wrap -> continuo."""
    d = np.diff(g)
    d = np.where(d > 180, d - 360, np.where(d < -180, d + 360, d))
    return np.concatenate([[g[0]], g[0] + np.cumsum(d)])


def cargar(ruta, circ):
    a, nota = RR.cargar(ruta)
    if a is None or len(a) < 500:
        return None
    vi, vd = RM.signo_ruedas(a)
    k = circ / 60.0
    vc = (vi + vd) / 2.0 * k
    yaw = desenvolver(RR.col(a, "yaw") / 10.0)
    w = RR.col(a, "gz") / 10.0
    # trayectoria por dead reckoning
    th = np.radians(yaw)
    vcf = np.nan_to_num(vc)
    x = np.cumsum(vcf * np.cos(th) * DT)
    y = np.cumsum(vcf * np.sin(th) * DT)
    return dict(nota=nota, vc=vc, yaw=yaw, w=w, x=x, y=y,
                steer=RR.col(a, "rxsteer"), age=RR.col(a, "rxage"),
                speed=RR.col(a, "rxspeed"), rot=RR.col(a, "rot"))


def curvas(d, w_min=25.0, hueco_max=40, dur_min=20):
    """Episodios de giro sostenido. `hueco_max` permite bajones cortos adentro
    de una misma curva (si no, una curva real se parte en veinte pedazos)."""
    m = np.abs(d["w"]) >= w_min
    idx = np.flatnonzero(m)
    if len(idx) == 0:
        return []
    cortes = np.flatnonzero(np.diff(idx) > hueco_max)
    ini = np.concatenate([[idx[0]], idx[cortes + 1]])
    fin = np.concatenate([idx[cortes], [idx[-1]]])
    return [(i, f) for i, f in zip(ini, fin) if f - i >= dur_min]


def como_termino(d, fin, mirar=200):
    """Que paso en los `mirar` muestras (1 s) DESPUES de la curva."""
    s = slice(fin, min(fin + mirar, len(d["steer"])))
    st, ag, sp = d["steer"][s], d["age"][s], d["speed"][s]
    if len(st) < 20:
        return "fin de corrida"
    if np.mean(sp == 0) > 0.5:
        return "FRENO (speed=0)"
    if np.mean((st == 0) & (ag < 200)) > 0.25:
        return "PERDIDA (steer=0 fresco)"
    return "sigue linea"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diametro", type=float, default=6.88)
    ap.add_argument("--fig", action="store_true")
    a = ap.parse_args()
    circ = math.pi * a.diametro

    rutas = [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
             if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]

    print("")
    print("=" * 104)
    print("  LAS CURVAS QUE EL ROBOT TRAZO DE VERDAD  (dead reckoning desde el yaw del BNO)")
    print("  rueda %.2f cm   |   la curva mas cerrada del reglamento es R = %.1f cm"
          % (a.diametro, R_CERRADA))
    print("=" * 104)

    todas = []
    D = {}
    for r in rutas:
        d = cargar(r, circ)
        if d is None:
            continue
        n = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        D[n] = d
        cs = curvas(d)
        print("")
        print("-" * 104)
        print("  %s   -   %d curvas" % (n, len(cs)))
        print("-" * 104)
        print("  %5s %8s %9s %9s %9s %9s %9s   %s"
              % ("#", "dur s", "giro deg", "R p50 cm", "R min cm", "v p50", "rot p50",
                 "como termino"))
        for j, (i, f) in enumerate(cs):
            sl = slice(i, f + 1)
            dur = (f - i) * DT
            giro = abs(d["yaw"][f] - d["yaw"][i])
            wr = np.radians(np.abs(d["w"][sl]))
            vv = d["vc"][sl]
            # SOLO MARCHA ADELANTE. Con v_centro < 0 el robot esta yendo en
            # reversa (recuperarAtasco hace BACKWARD) y `R = v/omega` sale
            # negativo, que no es un radio: es otra maniobra. En la v1 esto
            # metia R = -1368 cm en la tabla.
            R = np.where((wr > 1e-6) & (vv > 0.0), vv / np.maximum(wr, 1e-6),
                         np.nan)
            R = R[np.isfinite(R)]
            if len(R) < 5:
                continue
            fin = como_termino(d, f)
            todas.append(dict(corrida=n, dur=dur, giro=giro,
                              Rp50=np.median(R), Rmin=np.percentile(R, 5),
                              v=float(np.nanmedian(vv[vv > 0]))
                              if np.any(vv > 0) else float("nan"),
                              rot=np.median(np.abs(d["rot"][sl])) / 1000.0,
                              fin=fin, i=i, f=f))
            if j < 12:
                print("  %5d %8.2f %9.0f %9.2f %9.2f %9.2f %9.2f   %s"
                      % (j, dur, giro, np.median(R), np.percentile(R, 5),
                         float(np.nanmedian(vv[vv > 0])) if np.any(vv > 0)
                         else float("nan"),
                         np.median(np.abs(d["rot"][sl])) / 1000.0, fin))
        if len(cs) > 12:
            print("  ... y %d mas" % (len(cs) - 12))

    # ---------------- LA COMPARACION QUE IMPORTA -------------------------
    print("")
    print("=" * 104)
    print("  LAS QUE TERMINAN MAL CONTRA LAS QUE TERMINAN BIEN")
    print("=" * 104)
    print("")
    if not todas:
        print("  sin curvas detectadas")
        return 0
    print("  %-28s %7s %9s %10s %10s %9s %9s"
          % ("como termino", "n", "dur s", "giro deg", "R p50 cm", "v p50", "rot p50"))
    for k in ("sigue linea", "PERDIDA (steer=0 fresco)", "FRENO (speed=0)",
              "fin de corrida"):
        g = [t for t in todas if t["fin"] == k]
        if not g:
            continue
        print("  %-28s %7d %9.2f %10.0f %10.2f %9.2f %9.2f"
              % (k, len(g), np.median([t["dur"] for t in g]),
                 np.median([t["giro"] for t in g]),
                 np.median([t["Rp50"] for t in g]),
                 np.median([t["v"] for t in g]),
                 np.median([t["rot"] for t in g])))

    print("")
    print("  Y LA PREGUNTA DE BENJAMIN: que radio venia trazando el robot")
    print("  en las curvas que terminan en perdida?")
    print("")
    mal = [t for t in todas if t["fin"] == "PERDIDA (steer=0 fresco)"]
    bien = [t for t in todas if t["fin"] == "sigue linea"]
    if mal and bien:
        rm = np.array([t["Rp50"] for t in mal])
        rb = np.array([t["Rp50"] for t in bien])
        vm = np.array([t["v"] for t in mal])
        vb = np.array([t["v"] for t in bien])
        gm = np.array([t["giro"] for t in mal])
        gb = np.array([t["giro"] for t in bien])
        print("     %-22s %14s %14s" % ("", "PERDIDA n=%d" % len(mal),
                                        "sigue n=%d" % len(bien)))
        for nom, xm, xb in (("radio p50 (cm)", rm, rb),
                            ("velocidad p50 (cm/s)", vm, vb),
                            ("giro total (deg)", gm, gb)):
            print("     %-22s %14.2f %14.2f" % (nom, np.median(xm), np.median(xb)))
        print("")
        print("     curvas con R p50 <= %.1f cm:  perdida %.0f %%   sigue %.0f %%"
              % (R_CERRADA, 100 * np.mean(rm <= R_CERRADA),
                 100 * np.mean(rb <= R_CERRADA)))
        print("     curvas con rot saturado (>0,95): perdida %.0f %%   sigue %.0f %%"
              % (100 * np.mean([t["rot"] > 0.95 for t in mal]),
                 100 * np.mean([t["rot"] > 0.95 for t in bien])))
    else:
        print("     no hay suficientes de las dos clases para comparar")
        print("     (perdida n=%d, sigue n=%d)" % (len(mal), len(bien)))

    # ---------------- distribucion de radios -----------------------------
    print("")
    print("=" * 104)
    print("  DISTRIBUCION DEL RADIO DE LAS %d CURVAS" % len(todas))
    print("=" * 104)
    print("")
    R = np.array([t["Rp50"] for t in todas])
    for lo, hi, lbl in ((0, 2, "R < 2  (gira casi en el lugar)"),
                        (2, 4.9, "2 - 4,9"),
                        (4.9, 10, "4,9 - 10"),
                        (10, 20, "10 - 20"),
                        (20, 1e9, "> 20  (curva suave)")):
        s = (R >= lo) & (R < hi)
        if s.sum() == 0:
            continue
        print("  %-34s %4d curvas  %5.1f %%   v p50 = %.2f cm/s"
              % (lbl, s.sum(), 100 * s.mean(),
                 np.median([t["v"] for t, k in zip(todas, s) if k])))

    if a.fig:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as e:                                # noqa: BLE001
            print("\n  (sin matplotlib: %s)" % e)
            return 0
        fig, axes = plt.subplots(2, 3, figsize=(16, 10))
        for ax, (n, d) in zip(axes.ravel(), D.items()):
            ax.plot(d["x"], d["y"], lw=0.7, color="#888")
            for t in [t for t in todas if t["corrida"] == n]:
                sl = slice(t["i"], t["f"] + 1)
                c = {"PERDIDA (steer=0 fresco)": "#d62728",
                     "FRENO (speed=0)": "#ff7f0e",
                     "sigue linea": "#2ca02c"}.get(t["fin"], "#1f77b4")
                ax.plot(d["x"][sl], d["y"][sl], lw=2.0, color=c)
            ax.set_title(n, fontsize=9)
            ax.set_aspect("equal")
            ax.grid(alpha=0.3)
        fig.suptitle("Trayectoria reconstruida (dead reckoning). "
                     "Verde: la curva sigue. Rojo: la Pi perdio la linea. "
                     "Naranja: freno el watchdog.", fontsize=11)
        fig.tight_layout()
        out = os.path.join(AQUI, "CURVAS_REALES.png")
        fig.savefig(out, dpi=110)
        print("\n  figura -> %s" % out)
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
