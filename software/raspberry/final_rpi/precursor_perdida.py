# -*- coding: utf-8 -*-
"""
EL CONFLICTO POSICION-RUMBO, PREDICE QUE EL ROBOT PIERDA LA LINEA?

Benjamin, 25-ago: "por que no es asi?" -por que no puedo decir que separar
posicion de rumbo sea EL arreglo de las curvas cerradas-.

Para decir "X arregla las curvas cerradas" hacen falta TRES eslabones:

  1. X es un defecto real                            -> DEMOSTRADO
  2. X CAUSA que el robot se salga                   -> es lo que se prueba aca
  3. corregir X mejora la trayectoria                -> imposible en replay

El eslabon 2 nunca se probo de frente. `porque_el_atan2.py` lo ataco por
tramos y dio EN CONTRA (0,58x), pero eran dos tramos de 100 y 118 frames y los
controles son debiles. Este banco lo prueba con la unidad de analisis que el
mecanismo predice: el EVENTO.

Si mezclar posicion y rumbo hace que el robot se vaya de la cinta, entonces el
conflicto -las dos causas apuntando a lados OPUESTOS- tiene que estar mas
concentrado JUSTO ANTES de perder la linea que en un frame cualquiera.

FALSADORES, escritos antes de correr
------------------------------------
FP1  Si la razon de riesgo contra la TASA BASE es menor que 1,3 en toda la
     banda de ventanas, el conflicto no anticipa la perdida. MUERE el eslabon 2.

FP2  Si la razon contra el PLACEBO -la misma ventana corrida 2 s hacia atras-
     es menor que 1,3, entonces lo que se ve es "esto pasa en zonas de curva" y
     no "esto pasa antes de perder la linea". MUERE igual.

FP3  Si el efecto aparece en UNA sola ventana de la banda y no en las demas, no
     hay plateau y no hay conclusion.

BANDA PREREGISTRADA de ventana: 5 / 10 / 20 / 30 frames (0,15 a 0,9 s).

DENOMINADOR, explicito: solo entran frames CON target y con `e` y `psi`
definidos, porque el conflicto no existe sin los dos. Los tres grupos -ventana,
placebo y base- salen de ese mismo conjunto elegible.

CONTROL DE SANIDAD: se corre el mismo analisis con una variable que SI deberia
predecir la perdida -el estado LOW/SIN_CERCA de la propia candidata-. Si esa
tampoco predice nada, el instrumento esta roto y no hay conclusion sobre nada.

    python precursor_perdida.py
"""

import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

BANDA = (5, 10, 20, 30)
PLACEBO_ATRAS = 66          # 2 s a 33,3 fps
RR_MIN = 1.3


def preparar(datos):
    """Por video: lista de (elegible, conflicto, low, perdida) por frame."""
    todo = {}
    qe = np.percentile([abs(LS.errores(f)[0]) for vid in SP.AUTONOMOS
                        for f in datos.get(vid, [])
                        if f["target"] is not None
                        and LS.errores(f)[0] is not None], 25)
    qp = np.percentile([abs(LS.errores(f)[1]) for vid in SP.AUTONOMOS
                        for f in datos.get(vid, [])
                        if f["target"] is not None
                        and LS.errores(f)[1] is not None], 25)
    for vid in SP.AUTONOMOS:
        filas = datos.get(vid, [])
        out = []
        for f in filas:
            e = p = None
            if f["target"] is not None:
                e, p = LS.errores(f)
            eleg = e is not None and p is not None
            conf = False
            if eleg and abs(e) > qe and abs(p) > qp:
                conf = (e > 0) != (p > 0)
            low = f.get("state") in ("LOW", "LOW_FORWARD", "SIN_CERCA")
            perd = f["target"] is None
            out.append((eleg, conf, low, perd))
        todo[vid] = out
    return todo, qe, qp


def eventos(serie):
    """Frames donde ARRANCA una perdida: habia target y deja de haberlo."""
    ev = []
    for i in range(1, len(serie)):
        if serie[i][3] and not serie[i - 1][3]:
            ev.append(i)
    return ev


def tasa(todo, k, desplazo=0):
    """(en_ventana, total_ventana, fuera, total_fuera) para el conflicto."""
    a = b = c = d = 0
    for vid, serie in todo.items():
        ev = eventos(serie)
        vent = set()
        for i in ev:
            fin = i - desplazo
            for j in range(max(0, fin - k), fin):
                vent.add(j)
        for j, (eleg, conf, _low, _p) in enumerate(serie):
            if not eleg:
                continue
            if j in vent:
                b += 1
                a += conf
            else:
                d += 1
                c += conf
    return a, b, c, d


def tasa_var(todo, k, idx, desplazo=0):
    """Igual, pero para otra variable del tuple (2 = low)."""
    a = b = c = d = 0
    for vid, serie in todo.items():
        ev = eventos(serie)
        vent = set()
        for i in ev:
            fin = i - desplazo
            for j in range(max(0, fin - k), fin):
                vent.add(j)
        for j, fila in enumerate(serie):
            if not fila[0]:
                continue
            if j in vent:
                b += 1
                a += fila[idx]
            else:
                d += 1
                c += fila[idx]
    return a, b, c, d


def bloque(todo, titulo, idx):
    print("")
    print("  %s" % titulo)
    print("  %-8s %9s %10s %10s %10s %9s %9s"
          % ("ventana", "n vent", "% vent", "% base", "% placebo",
             "RR base", "RR plac"))
    rrs = []
    for k in BANDA:
        a, b, c, d = tasa_var(todo, k, idx)
        pa, pb, _pc, _pd = tasa_var(todo, k, idx, PLACEBO_ATRAS)
        pv = 100.0 * a / max(b, 1)
        pb_ = 100.0 * c / max(d, 1)
        pp = 100.0 * pa / max(pb, 1)
        rr = pv / max(pb_, 1e-9)
        rp = pv / max(pp, 1e-9)
        rrs.append((rr, rp))
        print("  %-8d %9d %9.1f %% %9.1f %% %9.1f %% %8.2fx %8.2fx"
              % (k, b, pv, pb_, pp, rr, rp))
    return rrs


def main():
    datos = SP.extraer()
    todo, qe, qp = preparar(datos)
    nev = sum(len(eventos(s)) for s in todo.values())
    neleg = sum(1 for s in todo.values() for f in s if f[0])
    print("")
    print("=" * 100)
    print("  EL CONFLICTO POSICION-RUMBO, ANTICIPA LA PERDIDA DE LINEA?")
    print("=" * 100)
    print("")
    print("  eventos de perdida en los 10 autonomos: %d" % nev)
    print("  frames elegibles (con e y psi): %d" % neleg)
    print("  conflicto = signos opuestos con |e| > %.4f y |psi| > %.2f deg"
          % (qe, qp))
    print("  placebo   = la misma ventana corrida %d frames (2 s) hacia atras"
          % PLACEBO_ATRAS)

    rrs = bloque(todo, "CONFLICTO POSICION-RUMBO", 1)

    print("")
    print("  %s" % ("-" * 96))
    ctrl = bloque(todo, "CONTROL DE SANIDAD: el estado LOW/SIN_CERCA de la "
                        "candidata,\n  que SI deberia anticipar la perdida", 2)

    print("")
    print("=" * 100)
    peor_base = max(r for r, _p in rrs)
    peor_plac = max(p for _r, p in rrs)
    ctrl_base = max(r for r, _p in ctrl)
    print("  CONTROL: RR base maxima del estado LOW = %.2fx  ->  %s"
          % (ctrl_base,
             "el instrumento detecta precursores" if ctrl_base >= RR_MIN
             else "*** EL INSTRUMENTO NO DETECTA NADA: no concluir"))
    print("")
    print("  FP1  RR contra la tasa base, maxima en la banda: %.2fx  ->  %s"
          % (peor_base, "sobrevive" if peor_base >= RR_MIN else "*** MUERE"))
    print("  FP2  RR contra el placebo,   maxima en la banda: %.2fx  ->  %s"
          % (peor_plac, "sobrevive" if peor_plac >= RR_MIN else "*** MUERE"))
    todas = all(r >= RR_MIN for r, _p in rrs)
    print("  FP3  se sostiene en TODA la banda: %s" % ("si" if todas else "no"))
    print("")
    if ctrl_base < RR_MIN:
        print("  VEREDICTO: sin conclusion. El control no detecta ni lo que")
        print("  deberia, asi que el instrumento no sirve para este contraste.")
    elif peor_base < RR_MIN or peor_plac < RR_MIN:
        print("  VEREDICTO: el conflicto NO anticipa la perdida de linea.")
        print("  El eslabon 2 -que el defecto CAUSE que el robot se salga-")
        print("  sigue sin evidencia, y ahora tambien por esta via.")
    else:
        print("  VEREDICTO: hay evidencia de que el conflicto anticipa la")
        print("  perdida. Es diagnostico, NO politica: sigue sin probarse que")
        print("  corregirlo mejore la trayectoria, y eso es prueba de robot.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
