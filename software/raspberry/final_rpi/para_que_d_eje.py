# -*- coding: utf-8 -*-
"""
PARA QUE SIRVE MEDIR d_eje. Benjamin, 25-ago: "para que esto?".

Pregunta justa: son 20 minutos de un sabado en el que hay pocas horas de robot.
Esto no la contesta con una promesa, la contesta con la cuenta.

LO QUE d_eje DESBLOQUEA, Y ES UNA SOLA COSA
--------------------------------------------
La ESCALA. Hoy toda la geometria de este repo esta en unidades relativas:
Z_rel = 1,0 es "tan lejos como la fila 119" y nada mas. La regresion de
`medir_eje.py` devuelve DOS numeros a la vez -k y d_eje- y con esos dos,

    D(v) = k / (v - v_h) + d_eje        [cm desde el EJE DE ROTACION]

todo lo relativo pasa a centimetros.

LA PREGUNTA QUE ESO CONTESTA, Y PUEDE EXPLICAR LA FALLA
-------------------------------------------------------
Coulter (CMU-RI-TR-92-01) demuestra que para un camino de radio R los lookahead
admisibles estan acotados en [0, 2R]. Por encima de 2R

    "there is no single arc that joins the two points; any driven arc will
     induce error"

o sea que el controlador NO esta eligiendo mal: esta resolviendo un problema SIN
SOLUCION. Y el reglamento RCJ fija radio interno >= 40 mm, asi que en la curva
mas cerrada R ~ 4,9 cm y la cota es ~9,8 cm.

Medido en este repo: el target cae en Z_rel 1,62 (p50). Si eso resulta ser mas
de 9,8 cm desde el eje, entonces **el robot se sale de las curvas cerradas por
una razon geometrica, y ningun arreglo de percepcion ni de ley lo cambia**.

Hoy esa frase no se puede ni afirmar ni negar. Con k y d_eje, si.

QUE HACE ESTE SCRIPT
--------------------
El barrido de sensibilidad, para saber QUE ESTA EN JUEGO antes de gastar los 20
minutos: para cada par (k, d_eje) plausible, donde cae el lookahead actual
respecto de la cota de Coulter.

Si la region "fuera de la cota" fuera diminuta, la medicion no valdria la pena.
Si fuera casi todo el mapa, tampoco -ya sabriamos la respuesta-. Lo que decide
es cuanto del mapa esta de cada lado.

    python para_que_d_eje.py
"""

import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402

V_H = 9.0
FILA_TARGET = 77.0        # p50 medido: Z_rel 1,62
FILA_CINTA = 45.0         # hasta donde se ve la cinta, p50: Z_rel 3,06
R_CERRADA = 4.9           # cm. RCJ 2.2.2 fija radio interno >= 40 mm
R_SUAVE = 15.0            # cm. cuarto de circulo en un tile de 30 cm


def D(k, d_eje, fila):
    return k / (fila - V_H) + d_eje


def main():
    print("")
    print("=" * 96)
    print("  QUE ESTA EN JUEGO AL MEDIR d_eje")
    print("=" * 96)
    print("")
    print("  El target cae en la fila %.0f (Z_rel %.2f), medido sobre 13.061"
          % (FILA_TARGET, LS.suelo(80, FILA_TARGET)[1]))
    print("  frames. La cota de Coulter para la curva mas cerrada del")
    print("  reglamento (R = %.1f cm) es 2R = %.1f cm." % (R_CERRADA, 2 * R_CERRADA))
    print("")
    print("  Cada celda: el lookahead en cm desde el eje de rotacion.")
    print("  FUERA = por encima de 2R, o sea sin solucion geometrica.")
    print("")
    ks = [400, 600, 800, 1000, 1400, 1800]
    ds = [4, 8, 12, 16, 20]
    print("  %-10s %s" % ("", "".join("%14s" % ("d_eje %d cm" % d) for d in ds)))
    fuera = total = 0
    for k in ks:
        fila = ""
        for d in ds:
            v = D(k, d, FILA_TARGET)
            total += 1
            mal = v > 2 * R_CERRADA
            if mal:
                fuera += 1
            fila += "%14s" % ("%.1f %s" % (v, "FUERA" if mal else "ok"))
        print("  k=%-8d %s" % (k, fila))
    print("")
    print("  %d de %d combinaciones quedan FUERA de la cota (%.0f %%)"
          % (fuera, total, 100.0 * fuera / total))
    print("")
    print("  Y contra la curva SUAVE (R = %.0f cm, 2R = %.0f):"
          % (R_SUAVE, 2 * R_SUAVE))
    fuera2 = 0
    for k in ks:
        for d in ds:
            if D(k, d, FILA_TARGET) > 2 * R_SUAVE:
                fuera2 += 1
    print("  %d de %d quedan fuera (%.0f %%)"
          % (fuera2, total, 100.0 * fuera2 / total))

    print("")
    print("=" * 96)
    print("  LA FRONTERA, Y ES MAS SIMPLE DE LO QUE PARECE")
    print("=" * 96)
    print("")
    print("  D(77) = k/68 + d_eje, y la cota es 2R = %.1f cm. Despejando, el k"
          % (2 * R_CERRADA))
    print("  MAXIMO que todavia deja el lookahead adentro:")
    print("")
    print("     %-12s %-14s %s" % ("d_eje (cm)", "k maximo", "Z(fila 119) que implica"))
    for dd in (2, 4, 6, 8, 9, 2 * R_CERRADA, 12, 16):
        kmax = (2 * R_CERRADA - dd) * 68.0
        if kmax <= 0:
            print("     %-12.1f %-14s %s"
                  % (dd, "NINGUNO", "esta FUERA sea cual sea k"))
        else:
            print("     %-12.1f %-14.0f %.1f cm" % (dd, kmax, kmax / 110.0))
    print("")
    print("  LEIDO AL REVES, y es lo unico que hay que retener:")
    print("")
    print("     si  d_eje >= %.1f cm  ->  el lookahead esta FUERA de la cota"
          % (2 * R_CERRADA))
    print("                              SIN IMPORTAR k, porque el eje ya esta")
    print("                              a mas de 2R del punto mas cercano que")
    print("                              la camara ve.")
    print("")
    print("  Y `d_eje` es cuanto ADELANTE del eje de rotacion empieza a ver la")
    print("  camara. Con la camara montada adelante y casi horizontal, 10 a 15 cm")
    print("  es lo esperable. Para quedar DENTRO con d_eje = 6 cm haria falta")
    print("  k <= %.0f, o sea que la camara viera el piso a %.1f cm en la fila 119."
          % ((2 * R_CERRADA - 6) * 68, ((2 * R_CERRADA - 6) * 68) / 110.0))
    print("")
    print("=" * 96)
    print("  LO QUE ESO SIGNIFICA")
    print("=" * 96)
    print("")
    print("  La medicion NO es una formalidad: el resultado cae de un lado o del")
    print("  otro segun la escala real, y las dos respuestas cambian que hacer.")
    print("")
    print("  * si el lookahead queda DENTRO de la cota -> el problema no es")
    print("    geometrico, y todo el esfuerzo va al retardo y a la ley.")
    print("  * si queda FUERA en la curva cerrada -> el controlador esta")
    print("    resolviendo un problema sin solucion cada vez que entra a una, y")
    print("    hay que BAJAR el lookahead o frenar antes de entrar. Ahi si")
    print("    LOOKAHEAD=70 px pasa de ser un parametro a ser el bug.")
    print("")
    print("  Y hay un segundo uso, mas barato de explicar: con la escala, el")
    print("  RETARDO se convierte en distancia. 150 ms a 30 cm/s son 4,5 cm a")
    print("  ciegas; si eso importa en una curva de radio 5 cm es una cuenta,")
    print("  no una opinion. Hoy no se puede hacer.")
    print("")
    print("  LO QUE NO ES: un arreglo. d_eje no mueve el robot ni un milimetro.")
    print("  Es la medicion que decide QUE ARREGLAR DESPUES. Si el fix del")
    print("  retardo resulta que alcanza, esto no hacia falta -pero eso tampoco")
    print("  se sabe hasta correrlo-.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
