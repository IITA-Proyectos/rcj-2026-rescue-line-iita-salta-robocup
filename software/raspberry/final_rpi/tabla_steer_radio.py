# -*- coding: utf-8 -*-
"""
DE LOS GRADOS QUE MANDA LA PI AL RADIO QUE TRAZA EL ROBOT.

Benjamin, 26-ago: "cuanto es 12 grados a steer?"

OJO, SON DOS COSAS DISTINTAS Y CONVIENE NO MEZCLARLAS
-----------------------------------------------------
Los 12 grados que reporte en `curvas_reales.py` son el GIRO TOTAL ACUMULADO
del robot en una curva -yaw_final menos yaw_inicial, medido por el BNO055-.
Son grados FISICOS del mundo, integrados en el tiempo.

`steer` es otra cosa: el error angular INSTANTANEO de la linea en la IMAGEN.

No hay conversion entre los dos. Un robot puede acumular 90 grados de giro con
steer chico y sostenido, o con steer grande y corto. Lo que si se puede -y es
lo que hace esta tabla- es contestar: "si la Pi manda X grados, que radio traza
el robot".

LA CADENA, verificada en el codigo (no de memoria)
---------------------------------------------------
    Main.py:72,160     angle en [-90, +90] grados de imagen, se envia
                       como `angle + 90` -> byte [0, 180]
    main.cpp:1839      steer = (data - 90) / 90            -> [-1, +1]
    main.cpp:3659      steerCmd = clamp(steer * 1.35, -1, 1)   LINE_STEER_GAIN
    main.cpp:3660      absSteer = |steerCmd|
    main.cpp:3752      rot = absSteer ^ 0.50                   LINE_ROT_EXP
    main.cpp:3753      rot = 1.0  si absSteer >= 0.92          LINE_PIVOT_STEER
    drivebase.cpp:215  v_int = vel*(1 - 2*rot),  v_ext = vel
                       -> R = b_eff*(1 - rot)/(2*rot)
                       -> v_centro = vel*(1 - rot)

`b_eff` = 20,9 cm, medido (drivebase.h, DRIVE_ANCHO_VIA_EFECTIVO).

Y UNA ADVERTENCIA QUE YA ESTA EN EL PROYECTO: esos "grados" de la imagen NO
son grados del suelo. Salen de un atan2 sobre pixeles con la camara casi
horizontal. La columna "grados img" es fiel a lo que viaja por el cable; no
es un angulo del mundo.

    python tabla_steer_radio.py
    python tabla_steer_radio.py --grados 12
"""

import argparse
import sys

GAIN = 1.35        # LINE_STEER_GAIN,  main.cpp:91
EXP = 0.50         # LINE_ROT_EXP,     main.cpp:96
PIVOT = 0.92       # LINE_PIVOT_STEER, main.cpp:3637
SALE = 0.15        # LINE_PIVOTE_SALE, main.cpp:104
B_EFF = 20.9       # drivebase.h, medido


def cadena(grados):
    """grados de imagen -> (byte, steer, absSteer, rot, R cm, v/vel)."""
    g = max(-90.0, min(90.0, float(grados)))
    byte = int(round(g + 90))
    steer = g / 90.0
    cmd = max(-1.0, min(1.0, steer * GAIN))
    ab = abs(cmd)
    rot = ab ** EXP
    if ab >= PIVOT:
        rot = 1.0
    rot = min(rot, 1.0)
    R = float("inf") if rot <= 0 else B_EFF * (1.0 - rot) / (2.0 * rot)
    return byte, steer, ab, rot, R, 1.0 - rot


def fila(g):
    byte, steer, ab, rot, R, frac = cadena(g)
    rs = "en el lugar" if R == 0 else ("%.1f" % R if R < 1e6 else "recto")
    nota = ""
    if ab >= PIVOT:
        nota = "PIVOTE (rot=1, NO avanza)"
    elif ab >= 1.0 - 1e-9:
        nota = "ganancia saturada"
    elif ab <= SALE:
        nota = "por debajo de PIVOTE_SALE"
    return ("  %8.1f %7d %8.3f %9.3f %8.3f %11s %10.0f %%   %s"
            % (g, byte, steer, ab, rot, rs, 100 * frac, nota))


def main():
    global GAIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--grados", type=float, default=None)
    # La corrida `pista_gain18` del 22-ago corrio con LINE_STEER_GAIN = 1.80 y
    # no con el 1.35 del default: con otra ganancia TODA la tabla se corre.
    ap.add_argument("--gain", type=float, default=GAIN)
    a = ap.parse_args()
    GAIN = a.gain

    print("")
    print("=" * 104)
    print("  DE LOS GRADOS QUE MANDA LA PI AL RADIO QUE TRAZA EL ROBOT")
    print("  b_eff = %.1f cm   |   ganancia %.2f   |   rot = absSteer^%.2f   |"
          "   pivote desde absSteer %.2f" % (B_EFF, GAIN, EXP, PIVOT))
    print("=" * 104)
    print("")
    print("  %8s %7s %8s %9s %8s %11s %12s   %s"
          % ("grados", "byte", "steer", "absSteer", "rot", "R (cm)",
             "avance", "nota"))
    print("  " + "-" * 100)

    if a.grados is not None:
        print(fila(a.grados))
        print("")
        return 0

    for g in (1, 2, 5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 61.3, 66.7,
              70, 80, 90):
        print(fila(g))

    print("")
    print("=" * 104)
    print("  LOS UMBRALES DEL FIRMWARE, EN GRADOS DE IMAGEN")
    print("=" * 104)
    print("")
    for nom, ab in (("LINE_PIVOTE_SALE", SALE),
                    ("LINE_CURVE_STEER", 0.08),
                    ("LINE_HARD_CURVE_STEER", 0.35),
                    ("LINE_PIVOT_STEER", PIVOT),
                    ("ganancia saturada", 1.0)):
        g = ab / GAIN * 90.0
        print("  %-24s absSteer %.2f   =   %5.1f grados de imagen"
              % (nom, ab, g))

    print("")
    print("  O sea que el robot entra en PIVOTE PLENO -y deja de avanzar- desde")
    print("  los %.1f grados de imagen, y no sale hasta bajar de %.1f grados"
          % (PIVOT / GAIN * 90, SALE / GAIN * 90))
    print("  sostenidos. Esa histeresis es la que lo deja girando en el lugar.")
    print("")
    print("  Para trazar la curva mas cerrada del reglamento (R = 4,9 cm) hace")
    print("  falta rot = %.3f, que es absSteer = %.3f = %.1f grados de imagen."
          % (B_EFF / (2 * 4.9 + B_EFF),
             (B_EFF / (2 * 4.9 + B_EFF)) ** (1 / EXP),
             (B_EFF / (2 * 4.9 + B_EFF)) ** (1 / EXP) / GAIN * 90))
    print("=" * 104)
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
