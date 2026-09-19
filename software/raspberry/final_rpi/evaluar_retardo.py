# -*- coding: utf-8 -*-
"""EVALUAR EL BARRIDO DE RETARDO desde los CSV de la Teensy.

Que decide, y por que ese numero
--------------------------------
El HANDOFF tiene medido lo que hay que mover:

    en la falla el robot gira 147,6 grados BRUTOS y termina en -8,8 NETOS:
    se cancela el 94 %.

O sea: la mecanica obedece, y el giro se anula solo porque las ordenes se
contradicen. Si el retardo sirve, esa cancelacion BAJA. Si sube, el retardo
empeora y se descarta aunque a ojo parezca mas suave.

    bruto       = sum(|gz|) * dt        grados girados en total
    neto        = |sum(gz)| * dt        rumbo efectivamente ganado
    cancelacion = 1 - neto / bruto

`gz` es la columna **44**, no la 10. Se verifico contra `DIAG_CABECERA` en
`main.cpp:1353-1358`, que es la fuente de verdad del orden de las 45 columnas:

    us,dt,drop,rxsteer,rxspeed,rxage,rxf,rot,ls,rs,ddir,ram, ... ,yaw,pit,gx,gy,gz
     0  1   2     3       4      5    6   7   8  9  10   11         40  41  42 43 44

y viene x10 (HANDOFF: "yaw/pit/gx/gy/gz x10"). El `dt` REAL sale de la columna 1,
en microsegundos: no se supone 200 Hz, se lee.

La primera version de este archivo usaba la columna 10 -que es `ddir`- y daba
bruto = 0,0. Por eso se valida contra la falla historica antes de usarlo.

Uso
---
    python3 evaluar_retardo.py corridas/*.csv
    python3 evaluar_retardo.py r0_a.csv r30_a.csv r60_a.csv r0_b.csv

Nombrar los archivos con el valor adentro -r0, r30, r60, r90- para que los
agrupe solo.
"""

import argparse
import os
import re
import sys

import numpy as np

COL_DT = 1          # dt en microsegundos  (main.cpp:1353)
COL_GZ = 44         # gz                   (main.cpp:1358)
ESC_GZ = 10.0       # gz viene x10
DT_FALLBACK = 0.005  # si la columna dt no sirve


def leer_gz(ruta):
    """gz y dt de las filas de 45 campos. Igual criterio que replay.py.

    gz es la columna 44 y dt la 1, verificadas contra DIAG_CABECERA en
    main.cpp:1353-1358. dt viene en microsegundos.
    """
    gz, dt = [], []
    with open(ruta, "r", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\n").split(",")
            if len(p) != 45:
                continue
            try:
                gz.append(int(p[COL_GZ]) / ESC_GZ)
                dt.append(int(p[COL_DT]) / 1e6)
            except (ValueError, IndexError):
                continue
    gz = np.asarray(gz, float)
    dt = np.asarray(dt, float)
    ok = (dt > 1e-5) & (dt < 0.1)
    if ok.sum() < 0.5 * max(dt.size, 1):
        dt = np.full(gz.shape, DT_FALLBACK)
    else:
        dt = np.where(ok, dt, np.median(dt[ok]))
    return gz, dt


def metricas(gz, dt):
    if gz.size < 100:
        return None
    bruto = float((np.abs(gz) * dt).sum())
    neto = float(abs((gz * dt).sum()))
    canc = 1.0 - neto / bruto if bruto > 1e-9 else float("nan")
    # inversiones del giro: cuantas veces cambia de signo con banda muerta
    s = [1 if x > 5 else (-1 if x < -5 else 0) for x in gz]
    s = [x for x in s if x]
    inv = sum(1 for a, b in zip(s, s[1:]) if a != b)
    seg = float(dt.sum())
    return dict(n=gz.size, seg=seg, bruto=bruto, neto=neto,
                canc=100.0 * canc, inv=inv, inv_s=inv / max(seg, 1e-9))


def valor_de(nombre):
    m = re.search(r"r(\d+)", os.path.basename(nombre).lower())
    return int(m.group(1)) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv", nargs="+")
    a = ap.parse_args(argv)

    print("")
    print("=" * 84)
    print(" BARRIDO DE RETARDO   -   cancelacion del giro, de la telemetria real")
    print("=" * 84)
    print("")
    print("  %-28s %7s %9s %9s %9s %7s %8s"
          % ("archivo", "seg", "bruto gr", "neto gr", "CANCELA", "inv", "inv/s"))
    por = {}
    for ruta in a.csv:
        if not os.path.exists(ruta):
            print("  falta %s" % ruta)
            continue
        m = metricas(*leer_gz(ruta))
        if m is None:
            print("  %-28s  sin datos suficientes" % os.path.basename(ruta))
            continue
        v = valor_de(ruta)
        if v is not None:
            por.setdefault(v, []).append(m)
        print("  %-28s %7.1f %9.1f %9.1f %8.1f %% %7d %8.2f"
              % (os.path.basename(ruta), m["seg"], m["bruto"], m["neto"],
                 m["canc"], m["inv"], m["inv_s"]))

    if len(por) >= 2:
        print("")
        print("  AGRUPADO POR VALOR DE RETARDO")
        print("  %-12s %6s %12s %12s %12s"
              % ("RETARDO_MS", "n", "cancelacion", "inv/s", "neto gr"))
        for v in sorted(por):
            g = por[v]
            c = [x["canc"] for x in g]
            i = [x["inv_s"] for x in g]
            nt = [x["neto"] for x in g]
            print("  %-12d %6d %11.1f %% %12.2f %12.1f"
                  % (v, len(g), np.mean(c), np.mean(i), np.mean(nt)))

        ceros = por.get(0, [])
        if len(ceros) >= 2:
            c0 = [x["canc"] for x in ceros]
            print("")
            print("  CONTROL: las corridas con RETARDO_MS=0 dan %.1f %% y %.1f %%"
                  % (min(c0), max(c0)))
            if max(c0) - min(c0) > 5.0:
                print("  *** Los dos controles diferen mas de 5 puntos. Algo derivo")
                print("  *** entre corridas -bateria, luz, temperatura-. EL BARRIDO")
                print("  *** NO VALE hasta repetirlo con controles estables.")
            else:
                print("  Los controles cierran: las diferencias entre valores se")
                print("  pueden atribuir al retardo.")
        elif ceros:
            print("")
            print("  *** Falta el SEGUNDO control con RETARDO_MS=0. Sin el no se")
            print("  *** puede descartar que algo haya derivado durante el barrido.")

    print("")
    print("  COMO LEERLO")
    print("  cancelacion BAJA  -> el retardo ayuda: el giro se anula menos")
    print("  cancelacion SUBE  -> el retardo empeora, descartarlo")
    print("  referencia de la falla historica: 94 %")
    print("")
    print("  Y anotar aparte lo unico que importa de verdad: cuantas veces se")
    print("  salio de la pista en cada corrida. Un numero mejor con el robot")
    print("  afuera de la pista no sirve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
