# -*- coding: utf-8 -*-
"""
INDICE DEL REGISTRO COMPLETO - donde mirar en los 6:56.

Benjamin, 25-ago: "revise el video y veo que esta la mayoria de cosas
correctas, mi duda es que tengo que ver visualmente aqui? cual es el punto clave
de ese frame?".

Un video de 13.900 frames en el que casi todo esta bien no se mira entero. Este
script busca los frames donde pasa ALGO y los devuelve con el minuto y segundo
del registro, para ir directo.

LAS CINCO COSAS QUE VALE LA PENA BUSCAR

  GUARD      un guard piso al planificador: el target final NO es el que la
             percepcion eligio. En el video se ven los circulos separados,
             unidos por linea roja, y arriba a la izquierda el cartel
             "lo movio: ...". Es el hallazgo 3.6 del traspaso.

  CONFLICTO  POSICION y RUMBO con SIGNO OPUESTO y los dos fuertes. Es el caso
             que la ley de hoy no puede expresar: para ponerse sobre la cinta
             hay que ir para un lado y para seguirla, para el otro. 43 % de los
             frames tienen algun conflicto; aca salen los mas extremos.

  DISCREPA   las dos leyes piden cosas muy distintas. En la tira de abajo se ve
             la gris y la celeste separadas.

  INVIERTE   una ley cambia de signo y la otra NO. Es lo mas importante de
             todo: ahi las dos mandan al robot para lados CONTRARIOS.

  FRENA      la vision anticipo una curva y bajo la velocidad. La barra verde
             se pone naranja.

    python indice_video.py
    python indice_video.py --cuantos 8
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

FPS = 100.0 / 3.0
PORTADA = int(FPS * 0.8)          # los frames de titulo que video_completo.py
                                  # mete antes de cada autonomo
K, G = 4.4794, 0.7419


def mmss(t):
    return "%d:%02d" % (int(t // 60), int(t % 60))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuantos", type=int, default=6)
    a = ap.parse_args()

    datos = SP.extraer()

    # offset de cada video dentro del registro
    off = {}
    acum = 0
    for vid in SP.AUTONOMOS:
        if vid not in datos:
            continue
        acum += PORTADA
        off[vid] = acum
        acum += len(datos[vid])

    filas = []
    for vid in SP.AUTONOMOS:
        if vid not in datos:
            continue
        prev_v = prev_s = None
        for f in datos[vid]:
            i = f["i"]
            t = f["target"]
            if t is None:
                prev_v = prev_s = None
                continue
            viejo = LS.steer_actual(f)
            c = LS.componentes(f, v_norm=f["factor"], k=K, g=G)
            st = None if c is None else c["delta"]

            # CUANTO movio el target respecto de lo que el planificador
            # eligio, y QUE etapa lo movio. La primera version comparaba contra
            # `path[0]`, que es el START y no el target crudo: daba 0,0 px en
            # todos y el indice listaba frames sin interes, espaciados justo por
            # el filtro de separacion temporal.
            raw = f.get("raw")
            movio_px = 0.0 if raw is None else math.hypot(t[0] - raw[0],
                                                          t[1] - raw[1])
            quien = []
            rz = f.get("reason") or ""
            if "continuidad" in rz:
                quien.append("cap")
            if "low_proj" in rz:
                quien.append("low")
            if f.get("spatial") in ("SPATIAL_LIMIT",):
                quien.append("spatial")
            movio = movio_px > 0.5

            conf = 0.0
            if c is not None and (c["t_pos"] > 0) != (c["t_psi"] > 0):
                conf = min(abs(c["t_pos"]), abs(c["t_psi"]))

            disc = 0.0 if st is None else abs(st - viejo)

            inv = False
            if st is not None and prev_v is not None and prev_s is not None:
                sv = 1 if viejo > 10 else (-1 if viejo < -10 else 0)
                ss = 1 if st > 10 else (-1 if st < -10 else 0)
                pv = 1 if prev_v > 10 else (-1 if prev_v < -10 else 0)
                ps = 1 if prev_s > 10 else (-1 if prev_s < -10 else 0)
                inv = ((sv != pv and sv != 0 and pv != 0)
                       != (ss != ps and ss != 0 and ps != 0))
            prev_v, prev_s = viejo, st

            filas.append(dict(
                vid=vid, i=i, t=(off[vid] + i) / FPS,
                movio=movio, salto=movio_px,
                quien="+".join(quien) or "-",
                conf=conf, disc=disc, inv=inv,
                factor=f["factor"], viejo=viejo, st=st,
                e=None if c is None else c["e"],
                psi=None if c is None else c["psi"],
                tp=None if c is None else c["t_pos"],
                tq=None if c is None else c["t_psi"]))

    def top(clave, filtro, n, orden=None):
        cs = [f for f in filas if filtro(f)]
        if orden:
            cs.sort(key=orden, reverse=True)
        # separar en el tiempo: no sirven 6 frames consecutivos
        sel = []
        for f in cs:
            if all(abs(f["t"] - g["t"]) > 3.0 for g in sel):
                sel.append(f)
            if len(sel) >= n:
                break
        return sel

    print("")
    print("=" * 104)
    print("  INDICE DEL REGISTRO COMPLETO  -  %s de video, %d frames"
          % (mmss(acum / FPS), len(filas)))
    print("  El minuto es el del REGISTRO, no el del video original.")
    print("=" * 104)

    print("")
    print("  1) UN GUARD PISO AL PLANIFICADOR   (cartel rojo 'lo movio')")
    print("     %-7s %-16s %8s %10s %12s" % ("min", "video", "frame",
                                             "movio px", "quien"))
    for f in top("guard", lambda f: f["movio"], a.cuantos,
                 lambda f: f["salto"]):
        print("     %-7s %-16s %8d %10.1f %12s"
              % (mmss(f["t"]), f["vid"], f["i"], f["salto"], f["quien"]))

    print("")
    print("  2) POSICION Y RUMBO PARA LADOS OPUESTOS, los dos fuertes")
    print("     Es el caso que UN solo numero no puede decir.")
    print("     %-7s %-16s %8s %9s %9s %9s %9s"
          % ("min", "video", "frame", "e", "psi", "POSICION", "RUMBO"))
    for f in top("conf", lambda f: f["conf"] > 0, a.cuantos,
                 lambda f: f["conf"]):
        print("     %-7s %-16s %8d %+9.3f %+9.1f %+9.1f %+9.1f"
              % (mmss(f["t"]), f["vid"], f["i"], f["e"], f["psi"],
                 f["tp"], f["tq"]))

    print("")
    print("  3) UNA LEY SE INVIERTE Y LA OTRA NO  -  LO MAS IMPORTANTE")
    print("     Ahi las dos mandan el robot para lados CONTRARIOS.")
    print("     %-7s %-16s %8s %11s %11s" % ("min", "video", "frame",
                                             "ley de hoy", "Stanley"))
    for f in top("inv", lambda f: f["inv"], a.cuantos, lambda f: f["disc"]):
        print("     %-7s %-16s %8d %+11.1f %+11.1f"
              % (mmss(f["t"]), f["vid"], f["i"], f["viejo"], f["st"]))

    print("")
    print("  4) LAS DOS LEYES MAS DISCREPAN   (tira de abajo, gris vs celeste)")
    print("     %-7s %-16s %8s %11s %11s %9s"
          % ("min", "video", "frame", "ley de hoy", "Stanley", "dif"))
    for f in top("disc", lambda f: f["st"] is not None, a.cuantos,
                 lambda f: f["disc"]):
        print("     %-7s %-16s %8d %+11.1f %+11.1f %+9.1f"
              % (mmss(f["t"]), f["vid"], f["i"], f["viejo"], f["st"],
                 f["st"] - f["viejo"]))

    print("")
    print("  5) LA VISION ANTICIPO LA CURVA Y FRENO  (barra naranja)")
    print("     %-7s %-16s %8s %9s %11s" % ("min", "video", "frame", "factor",
                                            "vel 50 ->"))
    for f in top("frena", lambda f: f["factor"] < 0.999, a.cuantos,
                 lambda f: -f["factor"]):
        print("     %-7s %-16s %8d %9.2f %11d"
              % (mmss(f["t"]), f["vid"], f["i"], f["factor"],
                 int(round(50 * f["factor"]))))

    print("")
    print("=" * 104)
    print("  LO QUE EL VIDEO NO MUESTRA, Y NO LO VA A MOSTRAR NUNCA:")
    print("  la trayectoria. El robot de la imagen se movio obedeciendo a la")
    print("  LEY VIEJA. La curva celeste es lo que Stanley HABRIA PEDIDO en ese")
    print("  frame, no por donde habria ido el robot. Eso es prueba de robot.")
    print("=" * 104)
    return 0


if __name__ == "__main__":
    sys.exit(main())
