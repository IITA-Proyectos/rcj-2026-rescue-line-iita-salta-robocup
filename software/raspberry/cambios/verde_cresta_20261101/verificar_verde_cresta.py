# -*- coding: utf-8 -*-
"""Replay de verde_cresta.py sobre las corridas del 1-nov, cuadro a cuadro (lazo abierto).

Entradas por cuadro: green_state, rampa y t de cuadros.csv (lo que vio y mando la Pi), y la mascara negra
recalculada del video GRABAR (panel izquierdo [1::2, 1::2], validada: la ley recalculada da la misma que
mando el robot en 4303 cuadros 'centroide', diferencia mediana 0,0-0,1 grados).

Lazo abierto: despues del primer cuadro que cambia, los cuadros siguientes son los de la corrida real (el
robot NO giro). Sirve para ver DONDE se arma, QUE verdes bloquea y HACIA DONDE manda el giro; si el giro
completa la curva hay que verlo en la pista.

    python verificar_verde_cresta.py
"""
import csv
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("VERDE_CRESTA", "1")
sys.path.insert(0, AQUI)
import verde_cresta as vc  # noqa: E402

CORRIDAS = os.path.join(AQUI, "..", "..", "corridas")
RUNS = [
    ("20261101_124912", "pista_doble_dato_20261101_124912.avi", "cuadros.csv"),
    ("20261101_135438", "pista_giro_cresta_20261101_135438.avi", "crudo/cuadros.csv"),
    ("20261101_140905", "pista_cresta_verde_20261101_140905.avi", "crudo/cuadros.csv"),
]


def mascara(f):
    small = f[1::2, 1:320:2][:120, :160]
    bm = cv2.inRange(small, np.array([0, 0, 0]), np.array([90, 90, 90]))
    bm[:60] = 0
    return bm


def main():
    total_armados = 0
    for run, video, cuad in RUNS:
        d = os.path.join(CORRIDAS, run)
        filas = list(csv.DictReader(open(os.path.join(d, cuad))))
        cap = cv2.VideoCapture(os.path.join(d, video))
        g = vc.VerdeCresta()
        verdes, armados, bloqueados, forzados, eventos = 0, [], [], [], []
        prev_gs = "0"
        for x in filas:
            ok, f = cap.read()
            if not ok:
                break
            n, t, gs = int(x["n"]), float(x["t"]), int(x["green_state"])
            if gs in (1, 2, 3) and prev_gs not in ("1", "2", "3"):
                verdes += 1
            prev_gs = x["green_state"]
            t0 = g.t0
            gs2 = g.verde(gs, x["rampa"] == "1", t)
            if g.t0 != t0:
                armados.append((n, gs))
            if gs2 != gs:
                bloqueados.append((n, gs))
            if gs2 == 0:
                a = g.completar(mascara(f), t)
                if a is not None:
                    forzados.append((n, a, x["quien"], x["angle"]))
                if g.evento:
                    eventos.append((n, g.evento))
                    g.evento = None
        total_armados += len(armados)
        print("=== %s: %d cuadros, %d verdes, se arma en %d" % (run, len(filas), verdes, len(armados)))
        for n, gs in armados:
            fz = [z for z in forzados if n < z[0] <= n + 120]
            bl = [b for b in bloqueados if n < b[0] <= n + 120]
            ev = [e for e in eventos if n < e[0] <= n + 120]
            print("  %5d %d:%05.2f verde %d (%s) | bloquea %s | gira %s en %s..%s | antes mandaba %s" % (
                n, n / 20 // 60, n / 20 % 60, gs, "IZQ" if gs == 1 else "DER",
                sorted({b[0] for b in bl}) and "%d cuadros desde %d" % (len(bl), bl[0][0]) or "nada",
                "%+.0f" % fz[0][1] if fz else "-", fz[0][0] if fz else "-", fz[-1][0] if fz else "-",
                sorted({(z[2], z[3]) for z in fz})[:3] if fz else "-"))
            for e in ev:
                print("        %5d %s" % e)
    return total_armados


if __name__ == "__main__":
    main()
