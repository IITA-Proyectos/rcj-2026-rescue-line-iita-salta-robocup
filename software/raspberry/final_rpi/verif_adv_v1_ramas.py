# -*- coding: utf-8 -*-
"""
Segundo verificador adversario: CUANTO de la rama SIN_CERCA queda viva con
SCHIST 5.

El reporte presenta SCHIST 5 como el arreglo CONSERVADOR y SIN_SC como el caso
limite que "no se puede adoptar porque el banco es ciego a su costo". Si h=5 ya
mata la mayor parte de los 2569 frames de sin_cerca_bottom_visible, esa
distincion es cosmetica: el arreglo conservador hereda la MISMA ceguera.

Se cuenta el motivo_target frame a frame para BASE, SCHIST 5 y SIN_SC.

    python verif_adv_v1_ramas.py
"""

import importlib.util
import os
import sys
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0


def cargar_v1():
    sp = importlib.util.spec_from_file_location(
        "airborne_v1_ramas", os.path.join(AQUI, "airborne_v1_adaptado.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def hacer_sc(v1):
    class V1SC(v1.AirborneV1):
        def __init__(self, fps, h=1, nunca=False):
            v1.AirborneV1.__init__(self, fps)
            self.h = h
            self.nunca = nunca
            self.racha = 0

        def seleccionar_contorno(self, m):
            c, r = v1.AirborneV1.seleccionar_contorno(self, m)
            if c is None:
                self.racha = max(self.racha, self.h)
            return c, r

        def confianza(self, c):
            if c is None:
                self.racha = max(self.racha, self.h)
                return 'PERDIDA'
            mm = np.zeros((v1.H, v1.W), np.uint8)
            cv2.drawContours(mm, [c], -1, 255, -1)

            def band(ab):
                a, b = ab
                return int((mm[a:b + 1] > 0).sum()) >= v1.PIX_MIN_BAND
            near, mid, far = band(v1.NEAR), band(v1.MID), band(v1.FAR)
            if not near:
                self.racha += 1
                if self.racha >= self.h and not self.nunca:
                    return 'SIN_CERCA'
            else:
                self.racha = 0
            if mid and far:
                return 'HIGH'
            if mid:
                return 'MEDIUM'
            return 'LOW'
    return V1SC


def main():
    v1 = cargar_v1()
    V1SC = hacer_sc(v1)
    CFG = [("BASE", 1, False), ("SCHIST 5", 5, False),
           ("SCHIST 12", 12, False), ("SIN_SC", 1, True)]
    cnt = {n: {} for n, _, _ in CFG}
    # cuantos frames tienen la banda cercana APAGADA (el disparador crudo)
    sin_near = {n: 0 for n, _, _ in CFG}
    nfr = 0
    videos = [v for v in AB.AUTONOMOS if os.path.exists(os.path.join(AQUI, v))]
    t0 = time.time()
    for vid in videos:
        cap = cv2.VideoCapture(os.path.join(AQUI, vid))
        frames = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            frames.append(v1.frame_de_la_pi(f))
        cap.release()
        nfr += len(frames)
        print("  %-18s %5d frames  %6.1f s" % (vid, len(frames),
                                               time.time() - t0))
        sys.stdout.flush()
        for nom, h, nunca in CFG:
            tr = V1SC(FPS, h, nunca)
            for g in frames:
                r = tr.paso(g)
                mt = r.get("motivo_target")
                cnt[nom][mt] = cnt[nom].get(mt, 0) + 1
                if r.get("estado") == 'SIN_CERCA':
                    sin_near[nom] += 1
        del frames

    print("")
    print("=" * 92)
    print("  FRAMES POR motivo_target  (total %d frames)" % nfr)
    print("=" * 92)
    todas = sorted(set().union(*[set(c) for c in cnt.values()]))
    print("  %-30s %10s %10s %10s %10s" % ("motivo", "BASE", "SCHIST 5",
                                           "SCHIST 12", "SIN_SC"))
    for mt in todas:
        print("  %-30s %10d %10d %10d %10d"
              % (mt, cnt["BASE"].get(mt, 0), cnt["SCHIST 5"].get(mt, 0),
                 cnt["SCHIST 12"].get(mt, 0), cnt["SIN_SC"].get(mt, 0)))
    print("")
    b = cnt["BASE"].get("sin_cerca_bottom_visible", 0)
    for nom in ("SCHIST 5", "SCHIST 12", "SIN_SC"):
        v = cnt[nom].get("sin_cerca_bottom_visible", 0)
        print("  %-12s deja %5d de los %5d frames de sin_cerca  "
              "-> mata el %5.1f %%" % (nom, v, b,
                                       100.0 * (b - v) / max(b, 1)))
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
