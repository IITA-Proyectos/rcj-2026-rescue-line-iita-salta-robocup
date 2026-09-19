# -*- coding: utf-8 -*-
"""
medir_camara.py - Cuanta pista ve el robot, en numeros.

PARA QUE
--------
El 2026-08-22, con el robot en pista, el video mostro esto:

  * la cinta ocupa el 22 % del ancho de la imagen (mediana, fila mas cercana)
  * en el 58 % de los frames la cinta cubre mas del 25 % del ROI
  * arriba del ROI no hay pista: hay SALON (pared, zocalo, patas de mesa)

O sea que la camara esta montada muy baja y mirando casi horizontal: el cuadro
se reparte entre "piso a cinco centimetros" y "el fondo de la sala", sin
distancia media utilizable. El robot NO VE VENIR LA CURVA, y con cuatro ruedas
fijas -que obligan a comprometerse con el giro antes- eso lo saca de la pista.

Ningun algoritmo arregla eso. Se arregla subiendo la camara y bajandole el
angulo. Y para saber si el cambio sirvio hace falta un numero, no una impresion.

USO
---
    sudo systemctl stop iita-robot          el servicio tiene la camara tomada
    python3 medir_camara.py                 mide 6 segundos y dictamina

    python3 medir_camara.py --seg 10        mas tiempo
    python3 medir_camara.py --guardar       ademas deja medicion.avi

COMO SE USA DE VERDAD
---------------------
Apoya el robot sobre la linea, justo ANTES de la curva que falla, como si
fuera a arrancar. No hace falta que ande: se mide lo que ve, quieto.
Corres esto, movés la camara, volvés a correrlo. Tres o cuatro iteraciones y
el numero te dice cuando parar.
"""
import os
import sys
import time

import cv2
import numpy as np

W, H = 160, 120
FILA_ROI = 60                       # el recorte que usa main.py: black_mask[:60,:] = 0
LO = np.array([0, 0, 0])
HI = np.array([90, 90, 90])

# --- objetivos, y de donde salen ---------------------------------------------
# Una cinta de Rescue Line mide 1-2 cm. Para poder anticipar, el robot tiene que
# ver del orden de 20-25 cm de piso de ancho, asi que la cinta deberia ocupar
# cerca del 8 % del cuadro. Medido el 2026-08-22: 22 %.
ANCHO_OBJETIVO = 12.0               # % del ancho de la imagen, o menos
# LA METRICA PRINCIPAL. Cuanto del ROI ocupa la cinta. Es la unica que resulto
# ESTABLE: 29,5 / 35,7 / 35,4 / 30,9 % en cuatro mediciones con el robot en
# lugares distintos. El "ancho" salta de 17 a 45 % segun donde se apoye el
# robot, asi que no sirve para comparar posiciones de camara; esta si.
COBERTURA_OBJETIVO = 10.0           # % del ROI, o menos
# HUBO UNA SEGUNDA METRICA Y SE DESCARTO. Intentaba medir "perspectiva" como
# ancho_lejos / ancho_cerca, suponiendo que una cinta que se aleja se estrecha.
# Validada contra frames del video del 2026-08-22 con la respuesta conocida a
# ojo, clasifico 3 de 5 AL REVES: un trapecio claro le dio 0,97 (mancha) y tres
# bandas evidentes le dieron 0,14 / 0,17 / 0,27 (perspectiva). Se saca en vez de
# dejarla adentro: una metrica que no se valido contra la realidad es peor que
# no tener metrica, porque se le cree.
# Y tiene que haber cinta bien arriba del recorte: eso es la anticipacion.
# Medido: 0 filas utiles arriba del ROI (lo que hay es el salon).
ALCANCE_OBJETIVO = 25               # filas de pista visibles por encima de FILA_ROI


def medir(frame):
    """Devuelve las metricas de UN frame, o None si no hay cinta."""
    f = cv2.rotate(frame, cv2.ROTATE_180)
    f = cv2.resize(f, (W, H), interpolation=cv2.INTER_NEAREST)
    m = cv2.inRange(f, LO, HI)

    roi = m[FILA_ROI:, :]
    cob = float((roi > 0).mean())
    if cob < 0.005:
        return None, f, m

    # ancho aparente de la cinta en la fila mas cercana al robot
    fila = m[H - 2]
    xs = np.where(fila > 0)[0]
    ancho = 0
    if len(xs):
        cortes = np.where(np.diff(xs) > 1)[0]
        ancho = max(len(t) for t in np.split(xs, cortes + 1))

    # ALCANCE: hasta que altura llega LA MISMA MANCHA que toca al robot.
    #
    # La primera version de esto contaba "hasta que fila hacia arriba hay algo
    # negro", y daba 32 filas de anticipacion sobre el video del 2026-08-22...
    # cuando mirando los frames se ve que arriba del ROI hay SALON: pared,
    # zocalo, patas de mesa. Contaba negro y lo llamaba linea. Es el mismo
    # error dos veces, asi que la leccion va escrita: NEGRO NO ES LINEA.
    #
    # La cinta que el robot puede seguir es la que esta CONECTADA con la que
    # tiene debajo. El salon entra por el borde de arriba y no toca la cinta,
    # asi que la conectividad los separa sin depender de ningun umbral de
    # densidad elegido a dedo.
    num, etiquetas = cv2.connectedComponents((m > 0).astype(np.uint8))
    fila_cerca = etiquetas[H - 2]
    suyas = set(int(v) for v in fila_cerca[fila_cerca > 0])
    alcance = 0
    if suyas:
        filas = np.where(np.isin(etiquetas, list(suyas)).any(axis=1))[0]
        if len(filas):
            alcance = max(0, FILA_ROI - int(filas.min()))
    return {"cob": cob, "ancho": ancho, "alcance": alcance}, f, m


def main():
    seg = 6.0
    if "--seg" in sys.argv:
        seg = float(sys.argv[sys.argv.index("--seg") + 1])
    guardar = "--guardar" in sys.argv

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("*** No pude abrir la camara.")
        print("    Esta corriendo el servicio? ->  sudo systemctl stop iita-robot")
        return 2
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("Apoya el robot sobre la linea, antes de la curva. Midiendo %.0f s..." % seg)
    datos = []
    sin_cinta = 0
    n = 0
    grab = None
    t0 = time.time()
    while time.time() - t0 < seg:
        ok, crudo = cap.read()
        if not ok:
            continue
        n += 1
        d, f, m = medir(crudo)
        if d is None:
            sin_cinta += 1
        else:
            datos.append(d)
        if guardar:
            vis = np.hstack([cv2.resize(f, (320, 240), interpolation=cv2.INTER_NEAREST),
                             cv2.cvtColor(cv2.resize(m, (320, 240),
                                          interpolation=cv2.INTER_NEAREST),
                                          cv2.COLOR_GRAY2BGR)])
            cv2.line(vis, (0, FILA_ROI * 2), (639, FILA_ROI * 2), (0, 255, 255), 1)
            if grab is None:
                grab = cv2.VideoWriter("medicion.avi",
                                       cv2.VideoWriter_fourcc(*"MJPG"), 15.0, (640, 240))
            grab.write(vis)
    cap.release()
    if grab is not None:
        grab.release()
        print("video: medicion.avi")

    if not datos:
        print("\n*** En %d frames no vi cinta en ningun lado." % n)
        print("    El robot esta sobre la linea? La camara mira al piso?")
        return 1

    anchos = np.array([d["ancho"] for d in datos], dtype=float)
    alcances = np.array([d["alcance"] for d in datos], dtype=float)
    cobs = np.array([d["cob"] for d in datos], dtype=float)

    ancho_pct = 100.0 * np.median(anchos) / W
    alcance = float(np.median(alcances))
    cob_pct = 100.0 * np.median(cobs)

    print("\n" + "=" * 62)
    print("  %d frames  |  sin cinta: %d (%.0f%%)" % (n, sin_cinta, 100.0 * sin_cinta / n))
    print("=" * 62)
    print("  cobertura del ROI          : %5.1f %%              (objetivo: <= %.0f %%)"
          % (cob_pct, COBERTURA_OBJETIVO))
    print("  ancho aparente de la cinta : %5.1f %% del cuadro   (referencia, inestable)"
          % ancho_pct)
    print("  anticipacion sobre el ROI  : %5.0f filas de pista"  % alcance)
    print()

    bien_cob = cob_pct <= COBERTURA_OBJETIVO
    if bien_cob:
        print("  LISTO. La cinta se ve como una cinta que se aleja, no como una mancha.")
        print("  Ahora si vale comparar centroide contra planner: hasta aca la")
        print("  comparacion no era justa para ninguno de los dos.")
    else:
        print("  LA CAMARA ESTA DEMASIADO CERCA DEL PISO. -> SUBILA.")
        print()
        print("  Con la cinta ocupando un tercio de lo que el robot mira, NINGUN")
        print("  algoritmo puede seguirla: el centroide la promedia y se satura en")
        print("  +-90, y el trazo le recorre el borde en vez de un centro. Se vio")
        print("  en el video del 2026-08-22, en la mascara del propio planner.")
        print()
        print("  Cada centimetro que subas baja la cobertura. Volve a medir DESDE EL")
        print("  MISMO PUNTO de la pista: marcalo con cinta, o el numero es ruido.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
