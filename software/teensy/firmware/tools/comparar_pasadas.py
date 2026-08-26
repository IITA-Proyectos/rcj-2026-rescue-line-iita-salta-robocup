#!/usr/bin/env python3
"""Compara tandas de pasadas de pista: la base contra un cambio.

    python tools/comparar_pasadas.py 2026-08-26_base_*.csv --contra 2026-08-26_lineal_*.csv

QUE MIDE, Y POR QUE ESO
-----------------------
El robot lo para BENJAMIN con el switch cuando ve que se sale. Eso deja una
marca exacta en el CSV: la Pi deja de mandar y `rxage` empieza a crecer sin
parar. O sea que el INSTANTE EN QUE SE APRETO EL BOTON es medible, y es
"se salio" menos el tiempo de reaccion.

    DURACION UTIL = desde el primer rxspeed > 0 hasta la ultima trama nueva

Esa es la variable principal: cuanto aguanto la corrida. No es perfecta -depende
de donde arranco en la pista y del tiempo de reaccion- por eso se reportan
TODAS las pasadas y no un promedio suelto.

Y tres descriptores del ESTADO antes del final, que son los que separan
"se salio girando" de "se salio derecho":

    %pivote     fraccion del tiempo con |rot| >= 0.95  (rot=1: NO avanza)
    %saturado   fraccion con |rxsteer| >= 65 (en decimas: 6.5 grados)
    steer=0     fraccion con rxsteer == 0. En el main.py del robot y con
                RECUP=0, la LINEA PERDIDA manda exactamente 0 -o sea "segui
                derecho"-. Es la firma de "la Pi no ve la linea".

NO se promedian las dos tandas para dar un solo numero: con 3 pasadas por
tanda, la diferencia entre pasadas ES el ruido, y se muestra.
"""
import argparse
import glob
import os
import sys

import numpy as np


def cargar(ruta):
    cab, filas, nota = None, [], ""
    with open(ruta) as f:
        for ln in f:
            if ln.startswith('#'):
                if 'nota:' in ln and not nota:
                    nota = ln.split('nota:', 1)[1].strip()
                continue
            p = ln.rstrip('\n').split(',')
            if cab is None:
                cab = p
                continue
            if len(p) != len(cab):
                continue
            try:
                filas.append([int(x) for x in p])
            except ValueError:
                continue
    if not filas:
        return None, None, nota
    return np.array(filas, dtype=np.int64), {n: i for i, n in enumerate(cab)}, nota


def resumir(ruta):
    a, C, nota = cargar(ruta)
    if a is None:
        return None
    t = (a[:, C['us']] - a[0, C['us']]) / 1e6
    sp, rxf = a[:, C['rxspeed']], a[:, C['rxf']]
    st, rot = a[:, C['rxsteer']], a[:, C['rot']] / 1000.0

    mov = np.where(sp > 0)[0]
    if not len(mov):
        return None
    t_ini = t[mov[0]]
    # ultima trama NUEVA: a partir de ahi la Pi callo (el boton)
    i_fin = int(np.argmax(rxf))
    t_fin = t[i_fin]
    if t_fin <= t_ini:                       # nunca callo: corrida completa
        t_fin = t[mov[-1]]

    m = (t >= t_ini) & (t <= t_fin)
    if m.sum() < 10:
        return None
    return dict(
        archivo=os.path.basename(ruta), nota=nota,
        dur=t_fin - t_ini,
        pivote=100.0 * (np.abs(rot[m]) >= 0.95).mean(),
        satur=100.0 * (np.abs(st[m]) >= 65).mean(),
        cero=100.0 * (st[m] == 0).mean(),
        gz=float(np.median(np.abs(a[m, C['gz']] / 10.0))),
    )


def tanda(nombre, rutas):
    rs = [r for r in (resumir(p) for p in rutas) if r]
    if not rs:
        print("  %s: ninguna pasada utilizable" % nombre)
        return []
    print("\n%s" % nombre)
    print("  %-30s %8s %8s %9s %8s %7s" %
          ("archivo", "dur (s)", "%pivote", "%saturado", "steer=0", "gz med"))
    for r in rs:
        print("  %-30s %8.1f %8.1f %9.1f %8.1f %7.1f" %
              (r['archivo'], r['dur'], r['pivote'], r['satur'], r['cero'], r['gz']))
    d = [r['dur'] for r in rs]
    print("  %-30s %8.1f  <- mediana de %d pasadas (min %.1f, max %.1f)" %
          ("", float(np.median(d)), len(d), min(d), max(d)))
    return rs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="+", help="CSV de la linea base")
    ap.add_argument("--contra", nargs="*", default=[], help="CSV del cambio")
    a = ap.parse_args()

    exp = lambda ps: [q for p in ps for q in (glob.glob(p) or [p])]
    b = tanda("LINEA BASE", exp(a.base))
    c = tanda("CON EL CAMBIO", exp(a.contra)) if a.contra else []

    if not b or not c:
        return
    db = [r['dur'] for r in b]
    dc = [r['dur'] for r in c]
    print("\n" + "=" * 78)
    print("  mediana base   %.1f s   (n=%d)" % (float(np.median(db)), len(db)))
    print("  mediana cambio %.1f s   (n=%d)" % (float(np.median(dc)), len(dc)))
    print()
    # Con 3 y 3 no hay estadistica: lo unico honesto es preguntar si los
    # rangos se SOLAPAN. Si se solapan, no hay diferencia demostrable.
    if min(dc) > max(db):
        print("  Los rangos NO se solapan: el cambio aguanto MAS en las %d pasadas." % len(dc))
        print("  (la peor del cambio, %.1f s, supera a la mejor de la base, %.1f s)"
              % (min(dc), max(db)))
    elif max(dc) < min(db):
        print("  Los rangos NO se solapan: el cambio aguanto MENOS en todas.")
    else:
        print("  LOS RANGOS SE SOLAPAN: con estas pasadas NO hay diferencia demostrable")
        print("  en duracion. base [%.1f .. %.1f]  cambio [%.1f .. %.1f]"
              % (min(db), max(db), min(dc), max(dc)))
        print("  Mira las otras columnas y el veredicto de pista (completo el codo?):")
        print("  la duracion sola no alcanza para decidir.")


if __name__ == "__main__":
    main()
