# -*- coding: utf-8 -*-
"""
analizar_corrida.py - Mide una corrida de seguimiento de linea y la compara
                      contra la linea de base del robot.

PARA QUE
--------
Para que dos personas que prueban dos ideas distintas puedan comparar NUMEROS en
vez de impresiones. Toda idea nueva se graba igual y se mide igual.

USO
---
    python3 analizar_corrida.py corrida.avi
    python3 analizar_corrida.py corrida.avi otra.avi    compara varias

COMO SE GRABA UNA CORRIDA
-------------------------
En la Raspberry, con el parche aplicado y SIN ninguna otra variable -o sea, el
robot funcionando exactamente como siempre-:

    sudo systemctl stop iita-robot
    cd ~/Desktop
    GRABAR=~/Desktop/como_esta.avi python3 main.py

Eso graba un video de 640x240: a la izquierda lo que la camara vio con el angulo
que se decidio, a la derecha la mascara. El panel izquierdo es el frame de
160x120 que el robot realmente proceso, escalado x2, asi que se recupera EXACTO
tomando un pixel de cada dos -sin interpolar, sin perder nada-.

LAS CUATRO METRICAS Y POR QUE ESTAS
-----------------------------------
  cruces por segundo   cuantas veces por segundo la linea cruza el centro de la
                       camara. Un seguidor sano cruza poco: si cruza mucho, esta
                       zigzagueando sobre la cinta en vez de seguirla.
  tiempo centrado      que fraccion del tiempo la linea esta a menos de 10 px
                       del centro. La cinta mide ~36 px en la imagen, asi que
                       10 px es menos de un tercio de cinta.
  desvio medio         cuan lejos del centro esta, en promedio.
  linea perdida        fraccion de frames sin cinta utilizable en el ROI. Es la
                       que mas duele: sin linea el robot no sabe que hacer.

LINEA DE BASE, medida el 2026-08-22 sobre 6772 frames de pista
--------------------------------------------------------------
    control            cruces/s   centrado   desvio   perdida
    atan2 (original)     1,88       42 %     20,0 px   17,9 %
    planner              1,07       37 %     19,4      24,8 %
    control lineal K=40  1,14       22 %     26,1      33,9 %
    control lineal K=70  1,62       37 %     21,1      22,6 %

Cuatro leyes de control distintas y las cuatro en la misma banda. Ninguna le
gana al original en las cuatro a la vez. Si una idea nueva mejora DOS de estas
sin empeorar las otras dos, es la primera que lo logra.

LO QUE ESTE ANALIZADOR NO PUEDE DECIR
-------------------------------------
Si el robot completo la pista. Mide como se comporta la vision y el control
respecto de la cinta, no si termino la corrida. Un robot puede tener numeros
lindos y salirse igual en la curva que importa.
"""
import os
import sys

import cv2
import numpy as np

W, H = 160, 120
CENTRO = (W - 1) / 2.0
LO = np.array([0, 0, 0])
HI = np.array([90, 90, 90])
FILA_ROI = 60

BASE = [
    ("atan2 (original)", 1.88, 42, 20.0, 17.9),
    ("planner", 1.07, 37, 19.4, 24.8),
    ("lineal K=40", 1.14, 22, 26.1, 33.9),
    ("lineal K=70", 1.62, 37, 21.1, 22.6),
]


def leer(ruta):
    """El panel izquierdo del video es el frame de 160x120 duplicado pixel a
    pixel, asi que se recupera exacto con [::2, ::2]. Nada de interpolar: un
    suavizado rompe la mascara y ya arruino dos mediciones."""
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        return None
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(f[:, :320][::2, ::2] if f.shape[1] >= 640 else f[::2, ::2])
    cap.release()
    return fr


def medir(fr):
    lat = []
    perdidos = 0
    for f in fr:
        m = cv2.inRange(f, LO, HI)[100:, :]
        if (m > 0).sum() < 30:
            lat.append(np.nan)
            perdidos += 1
        else:
            lat.append(float(np.nonzero(m)[1].mean()) - CENTRO)
    lat = np.array(lat)
    buenos = lat[~np.isnan(lat)]
    if len(buenos) < 50:
        return None
    seg = len(fr) / 20.0
    signos = np.sign(buenos)
    cruces = int((np.diff(signos) != 0).sum())
    # episodios de perdida sostenida: los candidatos a "se salio"
    vac = np.isnan(lat)
    eps = []
    ini = None
    for i, x in enumerate(vac):
        if x and ini is None:
            ini = i
        elif not x and ini is not None:
            if i - ini >= 15:
                eps.append((ini, i))
            ini = None
    if ini is not None and len(vac) - ini >= 15:
        eps.append((ini, len(vac)))
    return {
        "frames": len(fr), "seg": seg,
        "cruces": cruces / (len(buenos) / 20.0),
        "centrado": 100.0 * np.mean(np.abs(buenos) < 10),
        "desvio": float(np.mean(np.abs(buenos))),
        "perdida": 100.0 * perdidos / len(fr),
        "episodios": eps,
    }


def ganancia(fr):
    """Cuantos grados de correccion por pixel de desvio, segun cuan lejos este.

    Es el numero que explico por que el robot oscila: el atan2 tiene la ganancia
    INVERTIDA -mucha cerca del centro, cero lejos-, o sea que sobrecorrige
    cuando esta casi bien y se queda sin autoridad cuando de verdad se fue.
    Un control sano tiene esta curva PLANA.
    """
    import math
    xc = np.zeros((H, W)); yc = np.zeros((H, W))
    for i in range(H):
        for j in range(W):
            xc[i][j] = (j - (W / 2 - 1)) / (W / 2)
            yc[i][j] = ((H - 1) - i) / H
    L, A = [], []
    for f in fr:
        m = cv2.inRange(f, LO, HI)
        cerca = m[100:, :]
        if (cerca > 0).sum() < 30:
            continue
        mm = m.copy(); mm[:FILA_ROI, :] = 0
        if mm.sum() < 1:
            continue
        xb = cv2.bitwise_and(xc, xc, mask=mm) * (1 - yc)
        yb = cv2.bitwise_and(yc, yc, mask=mm)
        A.append((math.atan2(np.mean(yb), np.mean(xb)) / math.pi * 180) - 90)
        L.append(float(np.nonzero(cerca)[1].mean()) - CENTRO)
    if len(L) < 200:
        return None
    L = np.abs(np.array(L)); A = np.abs(np.array(A))
    out = []
    for a, b in ((0, 5), (5, 10), (10, 20), (20, 30), (30, 45), (45, 80)):
        sel = (L >= a) & (L < b)
        if sel.sum() < 40:
            continue
        g = np.polyfit(L[sel], A[sel], 1)[0]
        out.append((a, b, int(sel.sum()), float(A[sel].mean()), float(g)))
    return out


def main():
    archivos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not archivos:
        print(__doc__)
        return 2

    print("=" * 78)
    print("  corrida                   | frames |  s  | cruces/s | centrado | desvio | perdida")
    print("=" * 78)
    for n, c, ce, d, p in BASE:
        print("  %-26s|    -   |  -  |  %6.2f  |   %3d %%  | %5.1f  | %5.1f %%"
              % ("[base] " + n, c, ce, d, p))
    print("  " + "-" * 76)

    resultados = []
    for ruta in archivos:
        fr = leer(ruta)
        if not fr:
            print("  %-26s *** no se pudo abrir" % os.path.basename(ruta))
            continue
        r = medir(fr)
        if r is None:
            print("  %-26s *** pocos frames utiles" % os.path.basename(ruta))
            continue
        resultados.append((ruta, fr, r))
        print("  %-26s| %6d | %3.0f |  %6.2f  |   %3.0f %%  | %5.1f  | %5.1f %%"
              % (os.path.basename(ruta)[:26], r["frames"], r["seg"], r["cruces"],
                 r["centrado"], r["desvio"], r["perdida"]))
    print("=" * 78)

    for ruta, fr, r in resultados:
        print("\n" + "-" * 78)
        print("  %s" % os.path.basename(ruta))
        print("-" * 78)
        if r["episodios"]:
            print("  Episodios de linea perdida de mas de 0,7 s (candidatos a 'se salio'): %d"
                  % len(r["episodios"]))
            for a, b in r["episodios"][:8]:
                print("     frames %5d - %5d   (%.1f s)" % (a, b, (b - a) / 20.0))
        else:
            print("  Sin episodios de linea perdida sostenida.")

        g = ganancia(fr)
        if g:
            print("\n  GANANCIA: cuantos grados corrige por cada pixel de desvio")
            print("     desvio        n    angulo medio   ganancia")
            for a, b, n, am, gg in g:
                marca = "   <- deja de corregir" if gg <= 0.05 else ""
                print("     %3d-%3d px  %5d      %5.1f gr     %6.2f gr/px%s" % (a, b, n, am, gg, marca))
            cerca = [x for x in g if x[1] <= 10]
            lejos = [x for x in g if x[0] >= 30]
            if cerca and lejos:
                gc = np.mean([x[4] for x in cerca]); gl = np.mean([x[4] for x in lejos])
                print("\n     cerca del centro %.2f gr/px   |   lejos %.2f gr/px" % (gc, gl))
                if gl <= 0.1 < gc:
                    print("     -> GANANCIA INVERTIDA: sobrecorrige cerca del centro y se queda")
                    print("        sin autoridad lejos. Es la firma de un robot que zigzaguea")
                    print("        y que, cuando se sale, no vuelve.")
                elif abs(gc - gl) < 0.3 * max(gc, 0.01):
                    print("     -> ganancia PLANA, que es lo que corresponde.")

        # Con TOLERANCIA del 5%: una diferencia mas chica que eso es ruido de
        # medicion, no una mejora. Sin esto, comparar una corrida contra si
        # misma daba "mejora en 2 de 4" por puro redondeo, que es justo el tipo
        # de numero que hace tomar una decision equivocada.
        bn, bc, bce, bd, bp = BASE[0]

        def cmp_(valor, base, menor_es_mejor):
            if abs(valor - base) <= 0.05 * max(abs(base), 1e-9):
                return 0
            mejor = valor < base if menor_es_mejor else valor > base
            return 1 if mejor else -1

        votos = [("cruces", cmp_(r["cruces"], bc, True)),
                 ("centrado", cmp_(r["centrado"], bce, False)),
                 ("desvio", cmp_(r["desvio"], bd, True)),
                 ("perdida", cmp_(r["perdida"], bp, True))]
        mej = sum(1 for _, v in votos if v > 0)
        peo = sum(1 for _, v in votos if v < 0)
        igu = sum(1 for _, v in votos if v == 0)
        print("")
        print("  Contra la base (atan2 original), con 5% de tolerancia:")
        print("     mejor en %d | igual en %d | PEOR en %d" % (mej, igu, peo))
        print("     " + "   ".join("%s %s" % (k, "+" if v > 0 else ("=" if v == 0 else "-"))
                                   for k, v in votos))
        if mej >= 3 and peo == 0:
            print("  Es la primera configuracion que mejora de verdad. Guardar el video.")
        elif mej == 0 and peo > 0:
            print("  No mejora en ninguna y empeora en %d: no aporta como esta." % peo)
        elif mej and peo:
            print("  Mejora unas y empeora otras: todavia no es un avance claro.")
        else:
            print("  Practicamente igual que la base.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
