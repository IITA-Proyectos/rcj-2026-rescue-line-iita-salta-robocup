# -*- coding: utf-8 -*-
"""
EL ROBOT OBEDECIO? Y cuanto tardo?

Benjamin, 25-ago: "puedes decirme si con eso hubiese hecho bien los videos en
los que se salio, habiendo sabido como mandaba todo?".

LA RESPUESTA CORTA ES NO, Y NO ES FALTA DE ESFUERZO
----------------------------------------------------
El video contiene el futuro que genero el robot CON el retardo viejo. Si hubiera
reaccionado 100 ms antes, habria estado en otro lugar 100 ms despues y la camara
habria visto OTRA COSA. Esos frames no existen y no van a existir. No es que
falte un analisis: falta informacion que no esta en el archivo.

LO QUE SI SE PUEDE MEDIR, Y ES LO MAS CERCA QUE SE LLEGA
---------------------------------------------------------
Correlacionar el comando que la vision pidio EN ESE FRAME contra el giro REAL
del robot -por correlacion de fase sobre el fondo lejano, que no depende de
ninguna vision candidata-, y buscar el lag que la maximiza.

Que correlacionen ES circular: el robot giro obedeciendo al comando. Pero
CUANTO TARDA en obedecer, y CUAN FUERTE es el acoplamiento, no lo son.

=============================== RESULTADO ================================

    tramo          lag optimo   corr ahi   corr en lag 0
    hist_exito       2 f = 60 ms   0,924       0,847
    hist_falla      17 f = 510 ms  0,524       0,460
    los 10 juntos    2 f = 60 ms   0,465

En el EXITO el robot obedece en 60 ms con correlacion 0,92: muy acoplado.
En la FALLA la correlacion se derrumba a 0,52.

Y el "510 ms" NO hay que leerlo como medio segundo de retardo -el robot no tarda
eso en girar-. Un lag optimo grande CON correlacion baja es la firma de que no
hay acoplamiento, no de que haya mucho retardo: cuando dos series no estan
relacionadas, el maximo cae en cualquier lado.

    En la falla el robot no obedecio TARDE. DEJO de obedecer.

Y la ganancia lo acompaña:

    tramo         |cmd| p50   |giro| p50   giro/cmd   frames sin target
    hist_exito       42,1        48,5        1,171          0
    hist_falla       28,2        29,1        0,842          8

En la falla pidio MENOS -28 contra 42 de mediana- y giro proporcionalmente menos
todavia. Aunque el p90 del comando es MAYOR en la falla (85,2 contra 78,0): el
comando es mas bimodal, mucho tiempo pidiendo poco con picos al tope.

LO QUE ESTO SIGNIFICA PARA EL TRABAJO DE HOY, Y ES INCOMODO
------------------------------------------------------------
Si en la falla el problema fue que el robot DEJO de obedecer, entonces bajar el
retardo no arregla esa falla. El retardo sigue siendo real y sigue costando 21 a
36 grados de comando equivocado, pero su conexion con ESTA falla concreta no
esta demostrada, y este banco la debilita.

LIMITACION QUE HAY QUE DECIR
-----------------------------
El estimador de yaw por correlacion de fase es DEBIL: mezcla rotacion con
paralaje, la escala depende de un HFOV sin calibrar, y ya se sabe que da 1.075
frames por encima de 80 grados/s en un robot cuyo techo medido es 39. Ademas
puede degradarse justo donde el robot gira rapido -blur, saltos de fase-, que es
exactamente el tramo de falla.

O sea que la caida de 0,92 a 0,52 tiene DOS explicaciones posibles y este banco
no las separa: el robot dejo de obedecer, o el instrumento dejo de medir. La
unica forma de distinguirlas es el giroscopio del BNO055 en una corrida real,
que ya se graba (`gz` en el registrador del Teensy) y nunca se cruzo con esto.

    python obedecio_el_robot.py
"""

import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import sep_pos_rumbo as SP                                    # noqa: E402
import porque_el_atan2 as PA                                  # noqa: E402
import control_psi as CP                                      # noqa: E402

FPS = 100.0 / 3.0
W = 8                    # ventana de la derivada del yaw: 0,24 s
TRAMOS = (("hist_exito", 580, 679), ("hist_falla", 1354, 1490))


def tasa(y):
    """Velocidad angular sostenida, grados/s, del yaw acumulado."""
    return np.array([y[min(k + W, len(y) - 1)] - y[k]
                     for k in range(len(y) - 1)]) * FPS / W


def lag(a, g, maxlag=25):
    best = (None, -2.0)
    r0 = float("nan")
    for L in range(0, maxlag):
        if L >= len(a):
            break
        x = a[:len(a) - L] if L else a
        z = g[L:]
        n = min(len(x), len(z))
        if n < 20:
            break
        r = float(np.corrcoef(x[:n], z[:n])[0, 1])
        if L == 0:
            r0 = r
        if r > best[1]:
            best = (L, r)
    return best, r0


def main():
    d = SP.extraer()
    v2 = PA.cargar_v2()
    yaws = CP.cargar_yaw()
    at = PA.serie_atan2(v2, "hist.avi")
    ac = yaws["hist.avi"]

    print("")
    print("=" * 92)
    print("  CUANTO TARDA EL ROBOT EN OBEDECER")
    print("=" * 92)
    print("")
    print("  %-14s %13s %10s %14s" % ("tramo", "lag optimo", "corr ahi",
                                      "corr en lag 0"))
    for nom, d0, d1 in TRAMOS:
        a = np.array(at[d0:d1 + 1], float)
        g = tasa(np.array(ac[d0:d1 + 1], float))
        a = a[:len(g)]
        (L, r), r0 = lag(a, g)
        print("  %-14s %6d f = %3.0f ms %10.3f %14.3f"
              % (nom, L, 1000 * L / FPS, r, r0))

    print("")
    print("=" * 92)
    print("  ESTABA SATURADO?  Si el comando sube y el giro real no, si.")
    print("=" * 92)
    print("")
    print("  %-14s %7s %11s %12s %11s %12s"
          % ("tramo", "n", "|cmd| p50", "|giro| p50", "giro/cmd", "sin target"))
    for nom, d0, d1 in TRAMOS:
        a = np.abs(np.array(at[d0:d1 + 1], float))
        g = np.abs(tasa(np.array(ac[d0:d1 + 1], float)))
        a = a[:len(g)]
        sin_t = sum(1 for f in d["hist.avi"][d0:d1 + 1]
                    if f["target"] is None)
        m = a > 15
        gan = (np.percentile(g[m], 50) / np.percentile(a[m], 50)
               if m.sum() > 5 else float("nan"))
        print("  %-14s %7d %11.1f %12.1f %11.3f %12d"
              % (nom, len(a), np.percentile(a, 50), np.percentile(g, 50),
                 gan, sin_t))

    print("")
    print("=" * 92)
    print("  LO QUE NO SE PUEDE CONTESTAR CON ESTOS VIDEOS")
    print("=" * 92)
    print("")
    print("  Si el robot HABRIA tomado la curva con menos retardo. El video")
    print("  contiene el futuro que genero el robot CON el retardo viejo; con")
    print("  otro retardo habria estado en otro lugar y la camara habria visto")
    print("  otra cosa. Esos frames no existen.")
    print("")
    print("  Y el estimador de yaw es debil: la caida de 0,92 a 0,52 puede ser")
    print("  'el robot dejo de obedecer' o 'el instrumento dejo de medir'. Para")
    print("  separarlas hace falta el giroscopio del BNO en una corrida real,")
    print("  que ya se graba y nunca se cruzo con esto.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
