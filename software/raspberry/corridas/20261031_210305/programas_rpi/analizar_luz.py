#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analizar_luz.py - mide, sobre las carpetas que grabo captura_luz.py, si el verde y el negro aguantan cada luz.

    python analizar_luz.py CARPETA_CON_TODAS_LAS_PRUEBAS [--main ruta/a/main.py]

Para cada prueba (QUE_LUZ, ver captura_luz.py) dice:
  - verde:  en que % de los cuadros con la marca a la vista la Pi decide lo correcto (doble=3, izq=1, der=2),
            cuanto de cada cuadrado entra en el rango de verde (izq / der), y cual fue el PRIMER estado
            distinto de 0 (es el que ejecuta la Teensy).
  - piso:   cuadros en que el piso verde sin marca dispara un verde (tiene que ser 0).
  - negro:  % de cuadros con la cinta conectada abajo, y negro suelto (no conectado) que mete ruido.
  - color:  mediana y p5-p95 en LAB de los cuadrados, para ver cuanto los corre cada luz.
Al final propone un rango de verde que cubra todas las luces con margen, y avisa si agarra el piso.
Los rangos actuales los lee del main.py del robot (por defecto, el del freeze del 10-oct).
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from captura_luz import decidir_verde, leer_rangos  # noqa: E402

K1 = np.ones((3, 3), np.uint8)
ESPERADO = {"doble": 3, "izq": 1, "der": 2}


def cuadrados(fr):
    """Los dos cuadrados verdes, recortados por color (teal: G y B muy arriba de R), achicados 1 px."""
    b, g, r = [fr[..., i].astype(int) for i in range(3)]
    m = ((g - r > 40) & (b - r > 40)).astype(np.uint8)
    m[:80] = 0
    m = cv2.erode(m, K1, iterations=1)
    n, et, st, cen = cv2.connectedComponentsWithStats(m, 8)
    blobs = sorted([(st[i, cv2.CC_STAT_AREA], i) for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 25], reverse=True)[:2]
    return [et == i for _, i in sorted(blobs, key=lambda x: cen[x[1]][0])]


def linea(fr, R):
    """(hay_cinta_conectada, px_cinta, px_negro_suelto) como _solo_mi_linea de main.py."""
    bm = cv2.inRange(fr, np.array(R["lower_black"]), np.array(R["upper_black"]))
    bm[:60] = 0
    n, et, st, _ = cv2.connectedComponentsWithStats((bm > 0).astype(np.uint8), 8)
    abajo = set(et[118][et[118] > 0].tolist())
    con = np.isin(et, list(abajo)) & (bm > 0) if abajo else np.zeros(bm.shape, bool)
    return bool(con.sum() >= 200), int(con.sum()), int(((bm > 0) & ~con).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--main", default=r"C:/Users/villa/Downloads/V6_6_FREEZE_2026-10-10/RASPBERRY_V6_6_FIELD_REV/main.py")
    a = ap.parse_args()
    R = leer_rangos(a.main)
    lo, hi = np.array(R["lower_green"]), np.array(R["upper_green"])
    print("rangos de", R["origen"], "| verde", R["lower_green"], R["upper_green"], "| negro <=", R["upper_black"])
    pruebas = sorted(d for d in glob.glob(os.path.join(a.carpeta, "*")) if glob.glob(os.path.join(d, "f_*.png")))
    todos_cuadrados, todo_piso = [], []
    print("\n%-34s %5s | %-30s | %-22s | %-28s | %s" % ("prueba", "cuad", "verde (bien / cubre izq-der / 1ro)",
                                                    "piso verde: falsos", "negro (cinta ok / suelto)", "color cuadrados LAB"))
    for d in pruebas:
        nombre = os.path.basename(d)
        que = nombre.split("_")[2] if len(nombre.split("_")) > 2 else ""
        fs = sorted(glob.glob(os.path.join(d, "f_*.png")))
        estados, cov, primero, falsos, lin, suelto, px = [], [], None, 0, [], [], []
        for f in fs:
            fr = cv2.imread(f)
            est, ng, nb = decidir_verde(fr, R)
            ok, _, s = linea(fr, R)
            lin.append(ok); suelto.append(s)
            lab = cv2.cvtColor(fr, cv2.COLOR_BGR2LAB)
            if que == "piso":
                falsos += est != 0
                todo_piso.append(lab[80:].reshape(-1, 3))
                continue
            c = cuadrados(fr)
            if que in ESPERADO and len(c) >= (2 if que == "doble" else 1):
                estados.append(est)
                if est and primero is None:
                    primero = est
                cov.append([float(np.mean(np.all((lab[m] >= lo) & (lab[m] <= hi), axis=1))) for m in c])
                for m in c:
                    px.append(lab[m]); todos_cuadrados.append(lab[m])
        txt_v = "-"
        if estados:
            bien = np.mean([e == ESPERADO[que] for e in estados]) * 100
            ci = np.median([x[0] for x in cov]) * 100
            cd = np.median([x[-1] for x in cov]) * 100
            txt_v = "%3.0f%% / %3.0f%%-%3.0f%% / %s" % (bien, ci, cd, primero if primero is not None else "nunca")
        txt_p = ("%d de %d cuadros" % (falsos, len(fs))) if que == "piso" else "-"
        txt_n = "%3.0f%% / mediana %4d px" % (100 * np.mean(lin), np.median(suelto))
        txt_c = "-"
        if px:
            P = np.vstack(px)
            txt_c = "a %d (%d-%d) b %d (%d-%d)" % (np.median(P[:, 1]), np.percentile(P[:, 1], 5), np.percentile(P[:, 1], 95),
                                                   np.median(P[:, 2]), np.percentile(P[:, 2], 5), np.percentile(P[:, 2], 95))
        print("%-34s %5d | %-30s | %-22s | %-28s | %s" % (nombre[:34], len(fs), txt_v, txt_p, txt_n, txt_c))

    if todos_cuadrados:
        P = np.vstack(todos_cuadrados)
        p_lo = np.percentile(P, 1, axis=0).astype(int) - 5
        p_hi = np.percentile(P, 99, axis=0).astype(int) + 5
        print("\nRango de verde que cubre el 98 %% de los cuadrados en TODAS las luces (+-5): %s - %s" % (p_lo.tolist(), p_hi.tolist()))
        print("Rango actual del robot: %s - %s" % (lo.tolist(), hi.tolist()))
        for i, canal in enumerate("Lab"):
            print("  %s: los cuadrados van de %3d a %3d | el rango actual corta en %3d y %3d" % (
                canal, np.percentile(P[:, i], 1), np.percentile(P[:, i], 99), lo[i], hi[i]))
        if todo_piso:
            Q = np.vstack(todo_piso)
            dentro = np.mean(np.all((Q >= p_lo) & (Q <= p_hi), axis=1)) * 100
            print("  el piso verde que cae ADENTRO de ese rango propuesto: %.1f %% de sus pixeles %s" % (
                dentro, "(OJO: lo agarra)" if dentro > 1 else "(ok)"))
        print("  Es una propuesta para mirar, no para pegar: el rango se cambia en main.py y en el calibrador,"
              " y se prueba en pista.")


if __name__ == "__main__":
    main()
