# -*- coding: utf-8 -*-
"""CALIBRAR LA CAMARA AUTOMATICAMENTE. Saca el HFOV real y la distorsion.

Benjamin, 26-ago: "no hay algo q lo calibre automaticamente? porque el modelo si
dice camara wide de 140 grados, asi que bueno entonces con eso esta bien el
calculo del angulo?".

Si hay, y es esto. Y la respuesta corta a la segunda pregunta es NO DEL TODO,
por dos razones que este script resuelve juntas:

  1. LOS 140 DEL FABRICANTE SUELEN SER DIAGONALES, no horizontales. En un sensor
     4:3, 140 diagonales son 131 horizontales. El codigo necesita el HORIZONTAL.

  2. Y LO MAS GRANDE: con una lente asi el modelo PINHOLE que usa el codigo
     -X = (u-cx)*Z/f con f CONSTANTE- deja de valer. Una gran angular tiene
     DISTORSION DE BARRIL: el f efectivo cambia segun donde este el pixel.
     Cerca del centro el error es chico; en los bordes es grande. Y en un codo
     el target cae justo en los bordes.

La calibracion de OpenCV devuelve las DOS cosas a la vez: la matriz intrinseca
(de la que sale el HFOV verdadero) y los coeficientes de distorsion.

=============================== COMO SE USA ===============================

PASO 1 - imprimir un tablero de ajedrez. Cualquiera sirve; el clasico es 9x6
         esquinas INTERNAS (10x7 cuadrados). Pegarlo en algo PLANO y rigido:
         una carpeta, un carton. Si el papel se comba, la calibracion miente.

PASO 2 - sacar 15-20 fotos con LA CAMARA DEL ROBOT, a 160x120 si se puede
         (o a la resolucion nativa: el script reescala). El tablero tiene que
         aparecer:
             * en el CENTRO y en las CUATRO ESQUINAS del cuadro
             * inclinado en distintos angulos, no siempre de frente
             * ocupando a veces medio cuadro, a veces casi todo
         Las fotos de las ESQUINAS son las que fijan la distorsion, y son las
         que la gente no saca. Sin ellas el resultado sale lindo y es mentira.

PASO 3 -
    python calibrar_camara.py fotos/*.jpg
    python calibrar_camara.py fotos/ --filas 6 --cols 9

Y si no hay tablero a mano, el modo rapido que NO necesita nada:

    python calibrar_camara.py --pared 50 275
                                      D   L        (cm)

    camara mirando una pared plana y perpendicular, D = distancia de la lente a
    la pared, L = ancho de pared que entra en el cuadro. Da el HFOV pero NO la
    distorsion.

=========================== QUE HACER CON EL RESULTADO ===========================

El script imprime la linea exacta para poner en el repo. El HFOV entra por una
variable de entorno que YA EXISTE:

    LEY_STEER_HFOV=<el medido> python3 Main.py

Y si la distorsion sale grande (k1 fuerte), lo dice y explica que el pinhole no
alcanza.
"""

import argparse
import glob
import math
import os
import sys

import numpy as np

try:
    import cv2
except Exception as e:                                        # pragma: no cover
    print("hace falta opencv: %s" % e)
    sys.exit(1)

W_OBJ, H_OBJ = 160, 120          # la resolucion en la que trabaja el robot


def hfov_de(fx, w):
    """HFOV en grados a partir de la focal en pixeles y el ancho."""
    return 2.0 * math.degrees(math.atan((w / 2.0) / fx))


def modo_pared(D, L):
    hf = 2.0 * math.degrees(math.atan(L / (2.0 * D)))
    f = (W_OBJ / 2.0) / math.tan(math.radians(hf / 2.0))
    print("")
    print("=" * 84)
    print("  MODO PARED  (rapido, sin tablero; da el HFOV pero NO la distorsion)")
    print("=" * 84)
    print("")
    print("  distancia a la pared   D = %.1f cm" % D)
    print("  ancho que entra        L = %.1f cm" % L)
    print("")
    print("  HFOV  = 2*atan(L/(2D)) = %.1f grados" % hf)
    print("  f_px  = (160/2)/tan(HFOV/2) = %.1f px" % f)
    print("")
    print("  el codigo asume HFOV = 60 -> f_px = 138,6")
    print("  tu camara da          %.0f -> f_px = %.1f   (factor %.2fx en X)"
          % (hf, f, 138.6 / f))
    print("")
    print("  PARA USARLO:")
    print("      LEY_STEER_HFOV=%.1f python3 Main.py" % hf)
    print("")
    if hf > 100:
        print("  OJO: con %.0f grados la DISTORSION DE BARRIL es fuerte y el" % hf)
        print("  modelo pinhole del codigo no alcanza en los bordes. Para eso")
        print("  hace falta el modo tablero, que ademas devuelve k1/k2.")
    print("=" * 84)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fotos", nargs="*", help="imagenes del tablero, o una carpeta")
    ap.add_argument("--filas", type=int, default=6, help="esquinas INTERNAS")
    ap.add_argument("--cols", type=int, default=9, help="esquinas INTERNAS")
    ap.add_argument("--pared", nargs=2, type=float, metavar=("D", "L"),
                    help="modo rapido: distancia y ancho en cm")
    a = ap.parse_args()

    if a.pared:
        return modo_pared(a.pared[0], a.pared[1])

    rutas = []
    for f in a.fotos:
        if os.path.isdir(f):
            for e in ("jpg", "jpeg", "png", "bmp"):
                rutas += glob.glob(os.path.join(f, "*." + e))
        else:
            rutas += glob.glob(f)
    rutas = sorted(set(rutas))
    if not rutas:
        print("no hay fotos. Usa --pared D L para el modo rapido, o pasa imagenes.")
        print("   python calibrar_camara.py --pared 50 275")
        return 1

    patron = (a.cols, a.filas)
    obj = np.zeros((a.filas * a.cols, 3), np.float32)
    obj[:, :2] = np.mgrid[0:a.cols, 0:a.filas].T.reshape(-1, 2)
    P3, P2, tam = [], [], None
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    print("")
    print("=" * 84)
    print("  CALIBRACION CON TABLERO   patron %dx%d esquinas internas"
          % (a.cols, a.filas))
    print("=" * 84)
    print("")
    esquinas_vistas = []
    for r in rutas:
        img = cv2.imread(r)
        if img is None:
            print("  %-40s no se pudo leer" % os.path.basename(r)[:40])
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if tam is None:
            tam = g.shape[::-1]
        elif g.shape[::-1] != tam:
            print("  %-40s TAMANO DISTINTO, la salteo" % os.path.basename(r)[:40])
            continue
        ok, c = cv2.findChessboardCorners(
            g, patron,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
        if ok:
            c = cv2.cornerSubPix(g, c, (11, 11), (-1, -1), crit)
            P3.append(obj); P2.append(c)
            cx = float(np.mean(c[:, 0, 0])) / tam[0]
            cy = float(np.mean(c[:, 0, 1])) / tam[1]
            esquinas_vistas.append((cx, cy))
            print("  %-40s OK   centro del tablero en (%.2f, %.2f)"
                  % (os.path.basename(r)[:40], cx, cy))
        else:
            print("  %-40s no se encontro el tablero" % os.path.basename(r)[:40])

    if len(P3) < 5:
        print("")
        print("  SOLO %d fotos utiles. Hacen falta 10-15 como minimo, y varias" % len(P3))
        print("  con el tablero en las ESQUINAS del cuadro.")
        return 1

    # cobertura: sin fotos en los bordes la distorsion sale inventada
    xs = [p[0] for p in esquinas_vistas]
    ys = [p[1] for p in esquinas_vistas]
    borde = sum(1 for x, y in esquinas_vistas
                if x < 0.33 or x > 0.67 or y < 0.33 or y > 0.67)
    rms, K, dist, _, _ = cv2.calibrateCamera(P3, P2, tam, None, None)
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    hf = hfov_de(fx, tam[0])
    vf = hfov_de(fy, tam[1])
    dfov = 2 * math.degrees(math.atan(
        math.hypot(tam[0] / 2.0, tam[1] / 2.0) / fx))
    # la focal escalada a la resolucion en la que trabaja el robot
    fx160 = fx * (W_OBJ / float(tam[0]))

    print("")
    print("=" * 84)
    print("  RESULTADO   (%d fotos, RMS de reproyeccion %.3f px)" % (len(P3), rms))
    print("=" * 84)
    print("")
    print("  resolucion de las fotos   %d x %d" % tam)
    print("  fx = %8.2f      fy = %8.2f" % (fx, fy))
    print("  cx = %8.2f      cy = %8.2f   (el centro optico, no siempre el medio)"
          % (cx, cy))
    print("")
    print("  HFOV horizontal .......... %6.1f grados   <- ES EL QUE NECESITA EL CODIGO"
          % hf)
    print("  VFOV vertical ............ %6.1f grados" % vf)
    print("  DFOV diagonal ............ %6.1f grados   <- el que suele publicar el fabricante"
          % dfov)
    print("")
    print("  f_px a 160 de ancho ...... %6.1f px       (el codigo asume 138,6)"
          % fx160)
    print("")
    d = dist.ravel()
    print("  distorsion  k1=%+.4f  k2=%+.4f  p1=%+.4f  p2=%+.4f  k3=%+.4f"
          % (d[0], d[1], d[2], d[3], d[4] if len(d) > 4 else 0.0))
    print("")

    print("-" * 84)
    print("  QUE HACER CON ESTO")
    print("-" * 84)
    print("")
    print("  1) EL HFOV, que es el cambio de una linea:")
    print("")
    print("        LEY_STEER_HFOV=%.1f python3 Main.py" % hf)
    print("")
    print("     y en ley_steer.py:98    HFOV_NOMINAL = %.1f" % hf)
    print("     y en vision_linea.py:217 el 60.0 hardcodeado -> %.1f" % hf)
    print("     y rehacer HFOV_BANDA alrededor de %.0f, no de 60." % hf)
    print("")
    if rms > 1.0:
        print("  OJO: RMS = %.2f px es ALTO. Suele significar tablero combado," % rms)
        print("  fotos movidas, o pocas fotos en los bordes. No le creas al k1.")
        print("")
    if borde < 4:
        print("  OJO: solo %d de %d fotos tienen el tablero fuera del centro." % (borde, len(P3)))
        print("  La distorsion se determina en los BORDES: con esta cobertura")
        print("  k1 esta poco restringido. Saca mas fotos en las esquinas.")
        print("")
    if abs(d[0]) > 0.15:
        print("  2) LA DISTORSION ES FUERTE (k1 = %+.3f) Y ESTO IMPORTA:" % d[0])
        print("")
        print("     el codigo hace X = (u - cx) * Z / f con f CONSTANTE. Eso es")
        print("     un modelo PINHOLE, y con esta lente no vale en los bordes.")
        print("     Cerca del centro el error es chico; a media imagen ya se")
        print("     nota; en el borde es grande. Y en un CODO el target cae")
        print("     justo cerca del borde.")
        print("")
        print("     Lo correcto es corregir ANTES de proyectar:")
        print("")
        print("         K    = np.array([[%.2f,0,%.2f],[0,%.2f,%.2f],[0,0,1]])"
              % (fx160, cx * W_OBJ / tam[0], fy * (H_OBJ / float(tam[1])),
                 cy * H_OBJ / tam[1]))
        print("         dist = np.array([%.4f,%.4f,%.4f,%.4f,%.4f])"
              % (d[0], d[1], d[2], d[3], d[4] if len(d) > 4 else 0.0))
        print("         u2,v2 = cv2.undistortPoints(pt, K, dist, P=K)  # por PUNTO")
        print("")
        print("     Corregir solo los pocos puntos del camino cuesta microsegundos;")
        print("     corregir la imagen entera cuesta milisegundos. Con el camino")
        print("     alcanza: son los unicos pixeles que se proyectan al suelo.")
    else:
        print("  2) La distorsion es CHICA (k1 = %+.3f): el modelo pinhole del" % d[0])
        print("     codigo alcanza y solo hay que corregir el HFOV.")
    print("")
    print("=" * 84)
    print("")
    print("  Y UN CONTROL QUE VALE LA PENA: sacar UNA foto de algo con lineas")
    print("  rectas largas (el borde de una mesa, una puerta) ocupando todo el")
    print("  ancho. Si en la imagen se ven CURVADAS, hay distorsion de barril y")
    print("  se ve a ojo. Es el chequeo de sanidad de los numeros de arriba.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
