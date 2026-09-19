# -*- coding: utf-8 -*-
"""
LA ANTICIPACION DE CURVA, REHECHA. El test viejo estaba sesgado.

QUIEN LO ENCONTRO
-----------------
ChatGPT, en la auditoria del 25-ago que Benjamin trajo al canal. Reviso
`curva_cerrada.py` y senalo el bug exacto. Verificado en el codigo, es cierto:

    for k in range(1, 41):
        j = e - k
        if ka[j] is not None and ka[j] > U:
            mejor = k               # <- NO hace break

El lazo no corta. `mejor` termina siendo el k MAS GRANDE que cumple, o sea el
aviso MAS ANTIGUO de la ventana. Y la cobertura cuenta "hubo AL MENOS UNO en 40
frames".

Con el umbral en el p75, el 25 % de TODOS los frames esta sobre el umbral. Si
fueran independientes, la probabilidad de encontrar al menos uno en 40 frames
seria 1 - 0,75^40 = 99,999 %, y el lead mediano por puro azar rondaria los 38
frames. El resultado publicado -84 % de cobertura, lead p50 34 frames- esta
dentro de lo que la estructura del test produce SIN capacidad predictiva.

Son los dos errores que la propia skill `experimento-falsable` del repo lista:
el punto 8 -"al menos uno" no es lo mismo que eventos unicos- y el punto 7
-hace falta tasa base y placebo-. El test viejo no tiene ninguno de los dos.

EL TEST CORRECTO
----------------
La pregunta no es "hubo alguna kappa alta antes". Es:

    P(curva en los proximos H frames | kappa_t > U)     <- precision
    P(curva en los proximos H frames | frame cualquiera) <- tasa base
    lift = precision / tasa base

Si lift ~ 1, kappa no anticipa nada: solo esta diciendo "esto es una zona de
curva", que es lo mismo que decir "aca suele haber curvas".

FALSADORES, escritos antes de correr
------------------------------------
FC1  Si el lift contra la tasa base es menor que 1,5 en toda la banda de
     horizontes, kappa no anticipa la curva. MUERE, y `kFixVelocidadDesdeVision`
     no puede entrar al sabado justificada por esta evidencia.

FC2  Si el lift contra el PLACEBO -kappa desplazada 2 s- es menor que 1,5,
     entonces lo que se ve es correlacion de zona y no anticipacion. MUERE.

FC3  Si el efecto aparece en un solo horizonte y no en la banda, no hay plateau
     y no hay conclusion.

BANDA PREREGISTRADA de horizonte H: 10 / 20 / 30 / 40 frames (0,3 a 1,2 s).
BANDA PREREGISTRADA de umbral: p50 / p75 / p90 de la kappa observada.

    python curva_cerrada2.py
"""

import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

FPS = 100.0 / 3.0
HORIZONTES = (10, 20, 30, 40)
PERCENTILES = (50, 75, 90)
UMBRAL_STEER = 45.0
PLACEBO = 66            # 2 s
LIFT_MIN = 1.5


def series(datos):
    """Por video: (kappa, |steer|) por frame, con None donde no hay."""
    out = {}
    for vid in SP.AUTONOMOS:
        if vid not in datos:
            continue
        ka, st = [], []
        for f in datos[vid]:
            ka.append(f.get("kappa"))
            t = f["target"]
            st.append(None if t is None else abs(LS.steer_actual(f)))
        out[vid] = (ka, st)
    return out


def eventos(st, umbral):
    """Frames donde |steer| CRUZA el umbral hacia arriba. Evento unico."""
    ev = []
    prev = False
    for i, s in enumerate(st):
        if s is None:
            continue
        alto = s > umbral
        if alto and not prev:
            ev.append(i)
        prev = alto
    return ev


def evaluar(ser, U, H, desplazo=0):
    """(precision, tasa_base, recall, n_pred, n_frames, n_eventos)."""
    tp = npred = nev = nfr = 0
    con_ev = 0
    for vid, (ka, st) in ser.items():
        ev = set(eventos(st, UMBRAL_STEER))
        nev += len(ev)
        for i in range(len(ka)):
            j = i + desplazo
            if j >= len(ka) or ka[j] is None:
                continue
            futuro = any((i + h) in ev for h in range(1, H + 1))
            nfr += 1
            if futuro:
                con_ev += 1
            if ka[j] > U:
                npred += 1
                if futuro:
                    tp += 1
    prec = tp / max(npred, 1)
    base = con_ev / max(nfr, 1)
    return prec, base, npred, nfr, nev


def main():
    datos = SP.extraer()
    ser = series(datos)
    todas = np.array([k for _v, (ka, _s) in ser.items() for k in ka
                      if k is not None])
    nev = sum(len(eventos(st, UMBRAL_STEER)) for _v, (_k, st) in ser.items())

    print("")
    print("=" * 100)
    print("  ANTICIPACION DE CURVA - EL TEST CORRECTO")
    print("  n kappa = %d   eventos de curva (|steer| cruza %.0f) = %d"
          % (len(todas), UMBRAL_STEER, nev))
    print("=" * 100)
    print("")
    print("  precision = P(curva en los proximos H | kappa > U)")
    print("  base      = P(curva en los proximos H | frame cualquiera)")
    print("  lift      = precision / base.   lift ~ 1 = no anticipa nada.")
    print("")
    print("  %-8s %8s %5s %10s %9s %8s %10s %9s"
          % ("umbral", "U", "H", "n kappa>U", "precision", "base", "LIFT",
             "lift plac"))
    lifts = []
    lifts_p = []
    for pc in PERCENTILES:
        U = float(np.percentile(todas, pc))
        for H in HORIZONTES:
            prec, base, npred, _nfr, _n = evaluar(ser, U, H)
            pp, pb, _a, _b, _c = evaluar(ser, U, H, PLACEBO)
            lift = prec / max(base, 1e-9)
            liftp = prec / max(pp, 1e-9)
            lifts.append(lift)
            lifts_p.append(liftp)
            print("  p%-7d %8.1f %5d %10d %8.1f %% %7.1f %% %9.2fx %8.2fx"
                  % (pc, U, H, npred, 100 * prec, 100 * base, lift, liftp))

    print("")
    print("  KAPPA_REF de produccion = 139.5  (era el p75 de la distribucion)")
    U = 139.5
    print("")
    print("  %-8s %5s %10s %9s %8s %10s %9s"
          % ("con ese", "H", "n kappa>U", "precision", "base", "LIFT",
             "lift plac"))
    lif_ref = []
    for H in HORIZONTES:
        prec, base, npred, _nfr, _n = evaluar(ser, U, H)
        pp, _pb, _a, _b, _c = evaluar(ser, U, H, PLACEBO)
        lift = prec / max(base, 1e-9)
        lif_ref.append(lift)
        print("  %-8s %5d %10d %8.1f %% %7.1f %% %9.2fx %8.2fx"
              % ("139.5", H, npred, 100 * prec, 100 * base, lift,
                 prec / max(pp, 1e-9)))

    print("")
    print("=" * 100)
    mx = max(lifts)
    mxp = max(lifts_p)
    print("  FC1  lift maximo contra la tasa base:  %.2fx  ->  %s"
          % (mx, "sobrevive" if mx >= LIFT_MIN else "*** MUERE"))
    print("  FC2  lift maximo contra el placebo:    %.2fx  ->  %s"
          % (mxp, "sobrevive" if mxp >= LIFT_MIN else "*** MUERE"))
    todos_ok = all(l >= LIFT_MIN for l in lif_ref)
    print("  FC3  con KAPPA_REF=139.5, se sostiene en toda la banda de H: %s"
          % ("si" if todos_ok else "no"))
    print("")
    if mx < LIFT_MIN or mxp < LIFT_MIN:
        print("  VEREDICTO: kappa NO anticipa la curva mas que el azar.")
        print("  `kFixVelocidadDesdeVision` NO puede entrar al sabado")
        print("  justificada por esta evidencia. ChatGPT tenia razon.")
    else:
        print("  VEREDICTO: kappa SI anticipa, con lift %.2fx contra la base." % mx)
        print("  Pero eso es DIAGNOSTICO: que frenar mejore la trayectoria")
        print("  sigue sin probarse, y frenar cambia lo que la camara ve.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
