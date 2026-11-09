#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibrar_verde_multi.py - calibra el verde con MUCHOS cuadros y distintas luces, y comprueba que no agarre el
piso. Reemplaza a la tecla c del calibrador viejo, que usa un solo cuadro y el minimo/maximo de lo clickeado
(un pixel de piso blanco adentro del poligono y el rango se traga todo el piso).

Usa las grabaciones de captura_luz.py (QUE_LUZ):
    doble_* / izq_* / der_*   marcas verdes sobre la baldosa blanca  -> de aca sale el color del verde
    linea_* / piso_*          SIN marcas (cinta, piso blanco, piso verde de cancha) -> NO puede haber verde

    python calibrar_verde_multi.py CARPETA_CON_LAS_GRABACIONES
    python calibrar_verde_multi.py CARPETA --escribir /home/iita/robot/main.py

Que hace:
  1. Encuentra solo los cuadrados verdes en cada cuadro (lo claramente mas verde que el gris: a* < 118, ni
     negro ni blanco), los achica 1 px para no tomar el borde, y junta los pixeles de TODAS las grabaciones.
  2. Rango = percentil 1 a 99 de cada canal LAB, +-5. No el minimo/maximo: un pixel raro no lo estira.
  3. Si el rango deja entrar el piso o la cinta de las grabaciones sin marcas, lo va cerrando por el canal que
     mas piso saca y menos verde pierde, hasta que quede limpio.
  4. Dice cuanto de cada cuadrado cubre, cuanto piso entra, cuan lejos queda del piso blanco y que decidiria
     la Pi (el PRIMER verde de cada grabacion, que es el que ejecuta la Teensy) con el rango viejo y el nuevo.
  5. Con --escribir cambia lower_green y upper_green en ese main.py (deja una copia .antes_AAAAMMDD_HHMM).
     Sin --escribir no toca nada: muestra las dos lineas para pegar.

Lo que NO arregla un calibrador: que la Teensy ejecute el primer cuadro aunque diga "simple", ni el 1,2x del
doble en main.py. Eso es logica, no color (ver README).
"""
import argparse
import glob
import os
import re
import shutil
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from captura_luz import decidir_verde, leer_rangos  # noqa: E402

K1 = np.ones((3, 3), np.uint8)
MARCAS = ("doble", "izq", "der")
SIN_MARCA = ("linea", "piso")
ESPERADO = {"doble": 3, "izq": 1, "der": 2}
LIMITE_PISO = 100      # pixeles verdes falsos por cuadro tolerados (la Pi dispara con > min_square_size, ~510)


def que_es(carpeta):
    partes = os.path.basename(carpeta).split("_")
    return partes[2] if len(partes) > 2 else ""


def verde_de_las_marcas(fr):
    """Pixeles de los cuadrados verdes: claramente verdes (a* < 118), ni negros ni blancos, achicados 1 px."""
    lab = cv2.cvtColor(fr, cv2.COLOR_BGR2LAB)
    L, a = lab[..., 0].astype(int), lab[..., 1].astype(int)
    m = ((a < 118) & (L > 40) & (L < 235)).astype(np.uint8)
    m[:80] = 0
    m = cv2.erode(m, K1, iterations=1)
    n, et, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(m.shape, bool)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 25:
            keep |= et == i
    return lab[keep], lab


def adentro(px, lo, hi):
    return np.all((px >= lo) & (px <= hi), axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--main", default=os.path.join(AQUI, "main.py"), help="main.py del que se leen los rangos actuales")
    ap.add_argument("--escribir", default="", help="main.py donde escribir el rango nuevo (si no, solo se muestra)")
    ap.add_argument("--margen", type=int, default=5)
    a = ap.parse_args()

    R = leer_rangos(a.main)
    viejo = (np.array(R["lower_green"]), np.array(R["upper_green"]))
    grab = sorted(d for d in glob.glob(os.path.join(a.carpeta, "*")) if glob.glob(os.path.join(d, "f_*.png")))
    con = [d for d in grab if que_es(d) in MARCAS]
    sin = [d for d in grab if que_es(d) in SIN_MARCA]
    if not con:
        sys.exit("No hay grabaciones de marcas (doble_*, izq_*, der_*).")
    print("rango actual (de %s): %s - %s" % (R["origen"], viejo[0].tolist(), viejo[1].tolist()))
    print("grabaciones con marcas: %d | sin marcas: %d" % (len(con), len(sin)))
    if not sin:
        print("OJO: sin grabaciones linea_* o piso_* no se puede comprobar que no agarre el piso.")

    verdes, cuadros_con = [], {}
    for d in con:
        cuadros_con[d] = []
        for f in sorted(glob.glob(os.path.join(d, "f_*.png"))):
            fr = cv2.imread(f)
            px, _ = verde_de_las_marcas(fr)
            cuadros_con[d].append((fr, px))
            if len(px):
                verdes.append(px)
    P = np.vstack(verdes) if verdes else np.zeros((0, 3))
    if len(P) < 500:
        sys.exit("Muy pocos pixeles verdes (%d): las marcas no se ven en la franja de abajo." % len(P))
    piso = []
    for d in sin:
        for f in sorted(glob.glob(os.path.join(d, "f_*.png"))):
            piso.append(cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2LAB)[80:].reshape(-1, 3))

    lo = np.clip(np.percentile(P, 1, axis=0).astype(int) - a.margen, 0, 255)
    hi = np.clip(np.percentile(P, 99, axis=0).astype(int) + a.margen, 0, 255)

    def falsos(lo_, hi_):
        return [int(adentro(q, lo_, hi_).sum()) for q in piso] or [0]

    pasos = 0
    while max(falsos(lo, hi)) > LIMITE_PISO and pasos < 60:
        mejor = None
        for c in range(3):
            for lado in (0, 1):
                lo2, hi2 = lo.copy(), hi.copy()
                if lado == 0:
                    lo2[c] += 2
                else:
                    hi2[c] -= 2
                if lo2[c] >= hi2[c]:
                    continue
                perdido = 1 - adentro(P, lo2, hi2).mean() / max(1e-9, adentro(P, lo, hi).mean())
                ganado = max(falsos(lo, hi)) - max(falsos(lo2, hi2))
                score = ganado / (perdido + 1e-3)
                if ganado > 0 and (mejor is None or score > mejor[0]):
                    mejor = (score, lo2, hi2)
        if mejor is None:
            break
        lo, hi = mejor[1], mejor[2]
        pasos += 1

    print("\n=== Rango nuevo: lower_green = np.array(%s)  upper_green = np.array(%s)" % (lo.tolist(), hi.tolist()))
    if pasos:
        print("   (se cerro %d veces para sacar el piso)" % pasos)
    blanco = np.median(np.vstack(piso), axis=0).astype(int) if piso else None
    if blanco is not None:
        print("   piso sin marcas (mediana LAB): %s  -> a* queda a %d del rango" % (blanco.tolist(), blanco[1] - hi[1]))

    print("\n%-34s | %-26s | %-26s" % ("grabacion", "rango actual", "rango nuevo"))
    print("%-34s | %-26s | %-26s" % ("", "cubre / 1er verde / bien", "cubre / 1er verde / bien"))
    for d, cuadros in cuadros_con.items():
        fila = "%-34s" % os.path.basename(d)[:34]
        for (lo_, hi_) in (viejo, (lo, hi)):
            Rx = dict(R, lower_green=tuple(int(v) for v in lo_), upper_green=tuple(int(v) for v in hi_))
            ests = [decidir_verde(fr, Rx)[0] for fr, _ in cuadros]
            cub = np.mean([adentro(px, lo_, hi_).mean() for _, px in cuadros if len(px)]) * 100
            pri = next((e for e in ests if e), 0)
            esp = ESPERADO[que_es(d)]
            vistos = [e for e in ests if e]
            bien = (np.mean([e == esp for e in vistos]) * 100) if vistos else 0
            fila += " | %3.0f%% / %s / %3.0f%%%s" % (cub, {0: "-", 1: "IZQ", 2: "DER", 3: "DOBLE"}[pri], bien,
                                                     "" if pri == esp else " <- FALLA")
        print(fila)
    if piso:
        fv, fn = falsos(*viejo), falsos(lo, hi)
        print("%-34s | %-26s | %-26s" % ("piso/cinta sin marcas (px falsos)", "max %d" % max(fv), "max %d" % max(fn)))

    print("\nRecordar: si el 1er verde de un doble sale IZQ o DER con los dos rangos, no es el color: es la logica"
          " (la Teensy ejecuta el primer cuadro). Ver README.")
    if a.escribir:
        src = open(a.escribir, encoding="utf-8").read()
        nuevo = re.sub(r"^lower_green\s*=\s*np\.array\(\[[^\]]*\]\)",
                       "lower_green = np.array([%d, %d, %d])" % tuple(lo), src, count=1, flags=re.M)
        nuevo = re.sub(r"^upper_green\s*=\s*np\.array\(\[[^\]]*\]\)",
                       "upper_green = np.array([%d, %d, %d])" % tuple(hi), nuevo, count=1, flags=re.M)
        if nuevo == src:
            sys.exit("No encontre las lineas lower_green / upper_green en %s: no escribi nada." % a.escribir)
        copia = a.escribir + ".antes_" + time.strftime("%Y%m%d_%H%M")
        shutil.copy2(a.escribir, copia)
        open(a.escribir, "w", encoding="utf-8").write(nuevo)
        print("\nEscrito en %s (copia del anterior: %s). Probalo en pista antes de competir." % (a.escribir, copia))
    else:
        print("\nPara usarlo, en main.py (y en las constantes MAIN_* del calibrador viejo):")
        print("lower_green = np.array([%d, %d, %d])" % tuple(lo))
        print("upper_green = np.array([%d, %d, %d])" % tuple(hi))


if __name__ == "__main__":
    main()
