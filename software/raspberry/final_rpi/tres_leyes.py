# -*- coding: utf-8 -*-
"""
LAS TRES LEYES. Y son TRES, no dos: esa es la ambiguedad que hay que deshacer.

Benjamin, 25-ago: "el calculo del atan2 siempre estuvo correcto? o por que ahora
mismo dan muchas diferencias?".

La pregunta descubre una ambigüedad MIA en el registro visual: la aguja GRIS que
etiquete "ley de hoy" NO es el atan2. Son tres cosas distintas:

  1  atan2 de Main.py         centroide ponderado de TODOS los pixeles negros
                              del ROI.  `x_black *= (1 - y_com)` hace que los
                              lejanos pesen mas.
                              Es lo que corre SIN la variable VISION_LINEA.

  2  lineal sobre el target   -90 * (x_target - centro) / 80
                              Usa UN punto: el que el planificador eligio.
                              Es lo que corre CON VISION_LINEA=camino.
                              ES LA AGUJA GRIS DEL VIDEO.

  3  Stanley                  -g * ( psi + atan(k*e/v) )
                              Usa `e` (la entrada) y `psi` (la tangente).
                              Es la aguja CELESTE, y va apagada por defecto.

Cuando el video dice "ley de hoy" se refiere a la 2, no a la 1. La 1 es la ley
de SIEMPRE; la 2 ya es un cambio.

EL RESULTADO, Y NO ES EL QUE ESPERABA
-------------------------------------
Sobre los mismos 12.050 frames:

                        p50 |dif|  p90 |dif|   corr    signos opuestos
    atan2  vs  lineal       15,2      49,7    +0,755      12,2 %
    atan2  vs  Stanley      11,0      31,2    +0,858       4,4 %
    lineal vs  Stanley      17,9      39,7    +0,814       8,3 %

STANLEY SE PARECE MAS AL atan2 QUE LA LEY LINEAL. Por las tres medidas a la vez:
mas correlacion, menos discrepancia y un tercio de los cambios de signo.

Tiene una explicacion geometrica y es la misma razon por la que la intuicion de
Benjamin sobre el atan2 venia siendo buena: el atan2 y Stanley PROMEDIAN la
geometria -uno con pesos de pixel, el otro con dos terminos explicitos-, y la
ley lineal depende de UN punto que un planificador con guards puede mover 129 px.

CONSECUENCIA PARA EL SABADO, y es la que importa
------------------------------------------------
El salto grande NO es Stanley: es pasar del atan2 a la candidata. 12,2 % de
frames con el comando dado vuelta contra 4,4 %. O sea que la primera corrida con
VISION_LINEA=camino ya es el cambio mas grande de los dos, y conviene medirla
sola antes de encender nada mas.

    python tres_leyes.py
"""

import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402
import porque_el_atan2 as PA                                  # noqa: E402

K, G = 6.1328, 0.6406
DEAD = 10.0


def main():
    d = SP.extraer()
    v2 = PA.cargar_v2()
    AT, GR, ST = [], [], []
    for vid in SP.AUTONOMOS:
        at = PA.serie_atan2(v2, vid)
        for f, a in zip(d.get(vid, []), at):
            if f["target"] is None:
                continue
            c = LS.componentes(f, v_norm=f["factor"], k=K, g=G)
            if c is None:
                continue
            AT.append(a)
            GR.append(LS.steer_actual(f))
            ST.append(c["delta"])
    AT, GR, ST = np.array(AT), np.array(GR), np.array(ST)

    print("")
    print("=" * 92)
    print("  LAS TRES LEYES, sobre los mismos %d frames" % len(AT))
    print("=" * 92)
    print("")
    print("  1  atan2 de Main.py        centroide de TODOS los pixeles negros")
    print("     corre SIN la variable VISION_LINEA. Es la ley de SIEMPRE.")
    print("  2  lineal sobre el target  -90*(x_target-centro)/80")
    print("     corre CON VISION_LINEA=camino. ES LA AGUJA GRIS DEL VIDEO.")
    print("  3  Stanley                 -g*(psi + atan(k*e/v))")
    print("     la aguja CELESTE. Apagada por defecto.")
    print("")
    print("  %-26s %10s %10s %9s %14s"
          % ("", "p50 |dif|", "p90 |dif|", "corr", "signos opuestos"))
    for n, a, b in (("1 atan2   vs  2 lineal", AT, GR),
                    ("1 atan2   vs  3 Stanley", AT, ST),
                    ("2 lineal  vs  3 Stanley", GR, ST)):
        m = (np.abs(a) > DEAD) & (np.abs(b) > DEAD)
        print("  %-26s %10.1f %10.1f %+9.3f %13.1f %%"
              % (n, np.percentile(np.abs(a - b), 50),
                 np.percentile(np.abs(a - b), 90),
                 np.corrcoef(a, b)[0, 1],
                 100 * ((a[m] > 0) != (b[m] > 0)).mean()))
    print("")
    print("  %-26s %10s %10s %11s" % ("", "sigma", "|.| p50", "satura +-90"))
    for n, v in (("1 atan2", AT), ("2 lineal (gris)", GR),
                 ("3 Stanley (celeste)", ST)):
        print("  %-26s %10.1f %10.1f %10.1f %%"
              % (n, v.std(), np.percentile(np.abs(v), 50),
                 100 * (np.abs(v) >= 89.9).mean()))
    print("")
    print("=" * 92)
    print("  Las tres tienen autoridad parecida -sigma 43 a 45, |.| p50 33 a 35-.")
    print("  Lo que cambia no es CUANTO piden sino CUANDO.")
    print("")
    print("  Y Stanley se parece MAS al atan2 que la ley lineal, por las tres")
    print("  medidas a la vez. El salto grande no es la ley nueva: es pasar del")
    print("  atan2 a la candidata.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
