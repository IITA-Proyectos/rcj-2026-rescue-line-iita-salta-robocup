# -*- coding: utf-8 -*-
"""
EL EMBUDO - donde se pierde lo que la vision ve.

Benjamin, 25-ago, mirando el registro: "porque veo que el circulo con la X sabe
siempre a donde ir correctamente".

Tiene razon, y esta medido. Este script pone la cadena entera en una tabla, para
que se vea DONDE se cae lo que la vision acierta. Cada fila trae su fuente: lo
que se midio aca, y lo que ya estaba medido en el traspaso.

NO ES UN MODELO. Es una tabla de numeros medidos, cada uno con su origen. Las
dos ultimas filas son de OTRA fuente -telemetria real del Teensy, 7.673
periodos- y no salen de este banco.
"""

import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402


def main():
    d = SP.extraer()
    n = atras = salto = movido = 0
    sal = []
    ntot = 0
    for vid in SP.AUTONOMOS:
        if vid not in d:
            continue
        ntot += len(d[vid])
        ult = None
        for f in d[vid]:
            t = f["target"]
            if t is None:
                ult = None
                continue
            e, p = LS.errores(f)
            if e is None or p is None:
                continue
            n += 1
            if abs(p) > 90:
                atras += 1
            raw = f.get("raw")
            if raw is not None and math.hypot(t[0] - raw[0],
                                              t[1] - raw[1]) > 20:
                movido += 1
            if ult is not None:
                s = math.hypot(t[0] - ult[0], t[1] - ult[1])
                sal.append(s)
                if s > 24:
                    salto += 1
            ult = t
    sal = np.array(sal)

    print("")
    print("=" * 98)
    print("  EL EMBUDO   -   %d frames de los 10 autonomos" % ntot)
    print("=" * 98)
    print("")
    print("  %-46s %10s   %s" % ("eslabon", "resultado", "fuente"))
    print("  %s" % ("-" * 94))
    print("  %-46s %9.1f %%   %s"
          % ("hay target", 100.0 * n / ntot, "este banco"))
    print("  %-46s %10s   %s"
          % ("el target esta SOBRE la cinta correcta", "50 / 50",
             "verdad_componente.py"))
    print("  %-46s %9.1f %%   %s"
          % ("...y es estable (salto <= 24 px)",
             100.0 * (1 - salto / max(len(sal), 1)), "este banco"))
    print("  %-46s %9.1f %%   %s"
          % ("...y apunta hacia ADELANTE (|psi| <= 90)",
             100.0 * (1 - atras / n), "este banco"))
    print("  %-46s %9.1f %%   %s"
          % ("...y ningun guard lo corrio mas de 20 px",
             100.0 * (1 - movido / n), "este banco"))
    print("  %s" % ("-" * 94))
    print("  %-46s %10s   %s"
          % ("la Pi manda el comando", "66-86 Hz", "traspaso 3.1"))
    print("  %-46s %10s   %s"
          % ("la Teensy CAMBIA el comando", "8,6-20,6 Hz", "traspaso 3.1"))
    print("  %-46s %10s   %s"
          % ("   -> tramas de vision que se descartan", "~3 de 4",
             "traspaso 3.1"))
    print("  %-46s %10s   %s"
          % ("retardo comando -> giroscopio", "65-70 ms", "traspaso 3.1"))
    print("")
    print("  Las cuatro ultimas filas NO salen de este banco: son telemetria")
    print("  real del Teensy sobre 7.673 periodos en 6 corridas.")
    print("")
    print("=" * 98)
    print("  LO QUE DICE LA TABLA")
    print("=" * 98)
    print("")
    print("  La vision acierta la cinta, es estable y apunta bien casi siempre.")
    print("  Lo unico que sigue sucio aguas arriba es el %.1f %% donde un guard"
          % (100.0 * movido / n))
    print("  corre el target mas de 20 px -y en hist f1381 lo corre 129-.")
    print("")
    print("  Y despues de eso, TRES DE CADA CUATRO comandos se descartan.")
    print("")
    print("  Un %.1f %% contra un 75 %%. Por eso el orden del sabado importa mas"
          % (100.0 * movido / n))
    print("  que cual ley se elija: si el lazo sigue a 30 Hz, la ley que gane el")
    print("  A/B offline va a llegar tarde igual.")
    print("=" * 98)
    return 0


if __name__ == "__main__":
    sys.exit(main())
