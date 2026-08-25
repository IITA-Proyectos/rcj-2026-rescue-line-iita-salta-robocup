# -*- coding: utf-8 -*-
"""
SEPARAR POSICION DE RUMBO - parte 2: calibracion, F3, F4, F5 y el gate.

F1 y F2 ya sobrevivieron (sep_pos_rumbo.py):
    max |corr(e,psi)|      = 0,258   en toda la banda   (muere a 0,90)
    max R2(psi ~ x_target) = 0,497   en toda la banda   (muere a 0,90)

o sea que HAY dos grados de libertad y x_target no los contiene. Falta ver si
la ley nueva los separa DE VERDAD, si el instrumento es sano, y si rompe algo.

CRITERIOS DE CALIBRACION, escritos antes de correr
--------------------------------------------------
NO ES "SIN TUNING". Es una INICIALIZACION hecha mirando el dataset, no una
optimizacion sobre desempeno de lazo cerrado -que no se puede medir aca-. La
version anterior de este archivo decia "calibracion sin tuning por metrica", y
eso confunde dos cosas: no se maximizo ninguna metrica de replay, pero las
ganancias igual salieron de mirar estos datos. Y conservar el reparto 47/52 de
la ley que se quiere reemplazar no demuestra que sea optimo: es conservador, y
nada mas. (Auditoria de ChatGPT, 25-ago.)

  k_psi = 1,0  FIJO. Es lo que dice Stanley: el rumbo entra con ganancia
               unitaria. No se toca.

  k            se resuelve para que el REPARTO DE VARIANZA del comando nuevo
               iguale el reparto que la ley actual efectivamente tiene
               (47,5 % posicion / 52,5 % rumbo, medido). No se elige para ganar
               ninguna metrica: se elige para conservar el balance que hoy hay.

  g            ganancia global de escala. NO se elige: se BARRE en banda, y se
               reporta la tabla entera. Se marcan dos valores de referencia:
                 g_sigma  el que conserva la desviacion estandar del comando
                 g_max    el que conserva el maximo del control positivo
"""

import argparse
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402
import gate as GATE                                           # noqa: E402

REPARTO_OBJETIVO = 0.475       # posicion, medido en la ley actual
BANDA_T = (2.0, 5.0, 8.0, 12.0, 20.0)      # F3, preregistrada
BANDA_G = (0.6, 0.8, 1.0, 1.2, 1.5, 2.0)   # g, preregistrada


def _pares(datos, hfov, arco):
    """(e, psi, factor, ang_actual) de todos los frames con target."""
    E, P, V, S = [], [], [], []
    for _v, f in SP._todos(datos):
        if f["target"] is None:
            continue
        e, psi = LS.errores(f, hfov, arco)
        if e is None or psi is None:
            continue
        E.append(e)
        P.append(psi)
        V.append(max(f["factor"], LS.V_MIN))
        S.append(f["ang_prod"])
    return (np.array(E), np.array(P), np.array(V), np.array(S))


def calibrar(datos, hfov=LS.HFOV_NOMINAL, arco=LS.ARCO_PSI, verbose=True):
    """Devuelve (k, g_sigma). k por reparto de varianza; g por sigma."""
    E, P, V, S = _pares(datos, hfov, arco)
    sP = float(np.std(P))

    def reparto(k):
        pos = np.degrees(np.arctan(k * E / V))
        sp = float(np.std(pos))
        return sp / (sp + sP)

    lo, hi = 1e-4, 1e4
    for _ in range(120):
        m = math.sqrt(lo * hi)
        if reparto(m) < REPARTO_OBJETIVO:
            lo = m
        else:
            hi = m
    k = math.sqrt(lo * hi)

    pos = np.degrees(np.arctan(k * E / V))
    d = -(P + pos)
    g_sigma = float(np.std(S) / np.std(d))
    if verbose:
        print("  HFOV %.0f  arco %.2f" % (hfov, arco))
        print("    k = %.4f   -> reparto posicion %.1f %% / rumbo %.1f %%"
              % (k, 100 * reparto(k), 100 * (1 - reparto(k))))
        print("    sigma(actual) = %.2f   sigma(stanley sin g) = %.2f"
              "   -> g_sigma = %.4f" % (np.std(S), np.std(d), g_sigma))
    return k, g_sigma


# --------------------------------------------------------------------------
def serie_desde_cache(datos, vid, desde, hasta, ley, **kw):
    """(target, steer, estado) para el gate, sin recalcular la vision.

    El caché se extrajo procesando DESDE EL FRAME 0, que es la obligacion que
    el gate impone al llamador: el estado (prev_target, prev_heading, deques)
    se arrastra y arrancar en el medio mide otra cosa.
    """
    out = []
    for f in datos[vid]:
        if not (desde <= f["i"] <= hasta):
            continue
        t = f["target"]
        if t is None:
            out.append((None, None, f["state"]))
            continue
        if ley == "actual":
            s = f["ang_prod"]
        else:
            s = LS.steer_stanley(f, v_norm=f["factor"], **kw)
        out.append((t, s, f["state"]))
    return out


def correr_gate(datos, ley, **kw):
    def fn(ruta, fps, desde, hasta):
        vid = os.path.basename(ruta)
        return serie_desde_cache(datos, vid, desde, hasta, ley, **kw)
    return GATE.evaluar(fn, verbose=False)


# --------------------------------------------------------------------------
def f345(datos, hfov=LS.HFOV_NOMINAL, arco=LS.ARCO_PSI):
    print("")
    print("=" * 104)
    print("  CALIBRACION  (k por reparto de varianza; g se barre, no se elige)")
    print("=" * 104)
    print("")
    k, g_sigma = calibrar(datos, hfov, arco)

    E, P, V, S = _pares(datos, hfov, arco)
    pos = np.degrees(np.arctan(k * E / V))
    base = -(P + pos)                       # sin g

    # g que conserva el maximo del control positivo (lineal f800-872 >= +89)
    lin = [f for f in datos["lineal.avi"] if 800 <= f["i"] <= 872
           and f["target"] is not None]
    mx = []
    for f in lin:
        c = LS.componentes(f, v_norm=f["factor"], k=k, g=1.0,
                           hfov=hfov, arco=arco)
        if c is not None:
            mx.append(c["delta_sin_sat"])
    g_max = 89.0 / max(mx) if mx and max(mx) > 0 else float("nan")
    print("    maximo sin g en lineal f800-872 = %+.2f  -> g_max = %.4f"
          % (max(mx) if mx else float("nan"), g_max))

    print("")
    print("=" * 104)
    print("  F3 - MATERIALIDAD.  banda T = %s   (muere si p90 de la"
          % ("/".join("%g" % t for t in BANDA_T)))
    print("       discrepancia queda por DEBAJO de T en toda la banda)")
    print("  F4 - SANIDAD.  en recta y centrado, p90(|stanley|) <= p90(|actual|)")
    print("=" * 104)
    print("")

    # F4: subconjunto elegible definido por los propios cuantiles
    q_e = np.percentile(np.abs(E), 25)
    q_p = np.percentile(np.abs(P), 25)
    recto = (np.abs(E) < q_e) & (np.abs(P) < q_p)
    print("  F4: 'recta y centrado' = |e| < %.4f (p25) y |psi| < %.2f deg (p25)"
          % (q_e, q_p))
    print("      %d frames de %d (%.1f %%)  -- p90(|actual|) ahi = %.2f deg"
          % (recto.sum(), len(E), 100 * recto.mean(),
             np.percentile(np.abs(S[recto]), 90)))
    print("")

    gs = sorted(set(list(BANDA_G) + [round(g_sigma, 4), round(g_max, 4)]))
    print("  %-8s %-9s %8s %8s %8s %8s %10s %9s   %s"
          % ("g", "cual", "sig_st", "max_lin", "p50 dif", "p90 dif", "p90>T?",
             "F4", "GATE"))
    filas = []
    for g in gs:
        d = np.clip(g * base, -90, 90)
        dif = np.abs(d - S)
        p50, p90 = np.percentile(dif, 50), np.percentile(dif, 90)
        f4 = (np.percentile(np.abs(d[recto]), 90)
              <= np.percentile(np.abs(S[recto]), 90))
        ok, _inf = correr_gate(datos, "stanley", k=k, g=g, hfov=hfov, arco=arco)
        dlin = [np.clip(g * c, -90, 90) for c in mx]
        cual = ("sigma" if abs(g - g_sigma) < 1e-6 else
                "MAX" if abs(g - g_max) < 1e-6 else "")
        pasa_t = "".join("S" if p90 >= t else "." for t in BANDA_T)
        print("  %-8.4f %-9s %8.2f %8.2f %8.2f %8.2f %10s %9s   %s"
              % (g, cual, np.std(d), max(dlin) if dlin else float("nan"),
                 p50, p90, pasa_t, "OK" if f4 else "*** ROTO",
                 "PASA" if ok else "*** FALLA"))
        filas.append(dict(g=g, p90=p90, f4=f4, gate=ok,
                          maxlin=max(dlin) if dlin else 0.0))

    print("")
    print("  columna 'p90>T?':  una S por cada T de la banda %s que el p90"
          % ("/".join("%g" % t for t in BANDA_T)))
    print("  de la discrepancia SUPERA. 'SSSSS' = material en toda la banda.")

    # ---- F5: la division por v hace algo? --------------------------------
    print("")
    print("=" * 104)
    print("  F5 - LA DIVISION POR v HACE ALGO?")
    print("  muere si p90(|delta(v=0,55) - delta(v=1,00)|) < 1 grado sobre los")
    print("  frames donde la vision efectivamente baja la velocidad")
    print("=" * 104)
    print("")
    fac = np.array([max(f["factor"], LS.V_MIN)
                    for _v, f in SP._todos(datos)
                    if f["target"] is not None
                    and LS.errores(f, hfov, arco)[1] is not None])
    baja = fac < 0.999
    print("  factor de velocidad:  p05 %.3f  p25 %.3f  p50 %.3f  p75 %.3f  min %.3f"
          % tuple(list(np.percentile(fac, [5, 25, 50, 75])) + [fac.min()]))
    print("  frames con freno anticipado (factor < 1): %d de %d (%.1f %%)"
          % (baja.sum(), len(fac), 100 * baja.mean()))
    g_ref = g_sigma
    d_lento = np.clip(g_ref * -(P + np.degrees(np.arctan(k * E / LS.V_MIN))),
                      -90, 90)
    d_rapido = np.clip(g_ref * -(P + np.degrees(np.arctan(k * E / 1.0))),
                       -90, 90)
    dd = np.abs(d_lento - d_rapido)
    print("  |delta(v=0,55) - delta(v=1,00)| sobre TODOS:  p50 %.2f  p90 %.2f  max %.2f"
          % (np.percentile(dd, 50), np.percentile(dd, 90), dd.max()))
    if baja.sum():
        ddb = dd[baja]
        print("  ... sobre los frames que FRENAN:            p50 %.2f  p90 %.2f  max %.2f"
              % (np.percentile(ddb, 50), np.percentile(ddb, 90), ddb.max()))
        p90b = np.percentile(ddb, 90)
    else:
        p90b = 0.0
    print("")
    print("  F5 -> %s" % ("*** MUERE: dividir por v no cambia nada"
                          if p90b < 1.0 else "SOBREVIVE"))
    print("=" * 104)
    return k, g_sigma, g_max, filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hfov", type=float, default=LS.HFOV_NOMINAL)
    ap.add_argument("--arco", type=float, default=LS.ARCO_PSI)
    a = ap.parse_args()
    datos = SP.extraer()
    f345(datos, a.hfov, a.arco)
    return 0


if __name__ == "__main__":
    sys.exit(main())
