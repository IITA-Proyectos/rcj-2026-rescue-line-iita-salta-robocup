# -*- coding: utf-8 -*-
"""
SEPARAR POSICION DE RUMBO - el banco. Falsadores en FALSADOR-STANLEY.md.

Corre la vision DE PRODUCCION (CAMINO+MONO, la que enciende VISION_LINEA=camino)
sobre los 10 autonomos, guarda por frame lo que hace falta, y evalua los cinco
falsadores que quedaron escritos ANTES de medir.

    python sep_pos_rumbo.py --extraer        # una vez; cachea en _sep_cache.pkl
    python sep_pos_rumbo.py --f12            # F1 y F2: hay dos grados de libertad?
    python sep_pos_rumbo.py --fidelidad      # el espia reproduce la ley actual?
    python sep_pos_rumbo.py --calibrar       # k y g, con criterio principiado
    python sep_pos_rumbo.py --f345           # F3, F4, F5 + banda de umbrales

NO TOCA LA CANDIDATA. Instala CAMINO+MONO igual que vision_linea.py y consume
el dict que ya devuelve.
"""

import argparse
import importlib.util
import math
import os
import pickle
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402

CACHE = os.path.join(AQUI, "_sep_cache.pkl")
FPS = 100.0 / 3.0

AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]


# --------------------------------------------------------------------------
# EXTRACCION - usa la instancia de produccion, no una copia
# --------------------------------------------------------------------------
def _produccion():
    """Levanta vision_linea en modo camino y devuelve (modulo, v2).

    Se usa el modulo de integracion a proposito: asi lo que se mide es lo que
    corre en el robot con VISION_LINEA=camino, incluido el apagado de
    poi_component. Cualquier reimplementacion local seria otra cosa.
    """
    os.environ["VISION_LINEA"] = "camino"
    for m in ("vision_linea",):
        sys.modules.pop(m, None)
    sp = importlib.util.spec_from_file_location(
        "vision_linea", os.path.join(AQUI, "vision_linea.py"))
    vl = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(vl)
    vl._arrancar()
    return vl, vl._v2


def _pt(p):
    return None if p is None else (float(p[0]), float(p[1]))


def extraer(videos=None, forzar=False):
    if os.path.exists(CACHE) and not forzar:
        with open(CACHE, "rb") as f:
            return pickle.load(f)

    vl, v2 = _produccion()
    datos = {}
    for vid in (videos or AUTONOMOS):
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  falta %s" % vid)
            continue
        # tracker fresco por video: el estado se arrastra y arrancar en el
        # medio mide otra cosa (regla del gate)
        vl._tr = None
        vl._arrancar()
        cap = cv2.VideoCapture(ruta)
        filas = []
        i = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            r = vl._tr.step(v2.frame_pi(fr))
            t = r.get("target")
            st = r.get("start")
            # Factor de velocidad anticipada: lee el arbol de Dijkstra que la
            # candidata acaba de calcular, sin recalcular nada.
            #
            # OJO: se toma `_factor_velocidad()` CONTINUO, no `velocidad(100)`.
            # `velocidad()` devuelve el byte que va por el protocolo, o sea un
            # entero, y dividirlo por la base cuantiza el factor a 1/base. La
            # primera version de este extractor hacia eso y el caché quedo con
            # factores en multiplos exactos de 0,01, lo que despues aparecio
            # como 1.098 discrepancias de hasta 0,18 grados contra la ley
            # cableada en produccion. El bug era del extractor, no del cableado.
            vl._NFRAME += 1
            factor = vl._factor_velocidad()
            kappa = vl._ULT.get("kappa")
            filas.append(dict(
                i=i,
                start=None if st is None else (float(st[0]), float(st[1])),
                target=None if t is None else (float(t[0]), float(t[1])),
                path=[(float(x), float(y)) for x, y in (r.get("path") or [])],
                heading=r.get("heading"),
                state=r.get("state"),
                reason=r.get("reason"),
                # las CINCO etapas, para que el cache refleje el codigo:
                #   raw -> cap -> geo(=lowproj) -> bra -> target
                raw=_pt(r.get("target_raw")),
                cap=_pt(r.get("target_cap")),
                geo=_pt(r.get("target_geometric")),
                bra=_pt(r.get("target_branch")),
                spatial=r.get("spatial_guard"),
                entrada=_pt(r.get("entrada")),
                salto=r.get("proposed_jump_px"),
                factor=factor,
                kappa=kappa,
                ang_prod=None if t is None else vl._angulo_de(float(t[0])),
            ))
            i += 1
        cap.release()
        datos[vid] = filas
        con = sum(1 for f in filas if f["target"] is not None)
        print("  %-18s %6d frames   %6d con target" % (vid, len(filas), con))
    with open(CACHE, "wb") as f:
        pickle.dump(datos, f)
    return datos


def _todos(datos):
    for vid in AUTONOMOS:
        for f in datos.get(vid, []):
            yield vid, f


# --------------------------------------------------------------------------
# F1 y F2 - hay dos grados de libertad?
# --------------------------------------------------------------------------
def f12(datos):
    print("")
    print("=" * 100)
    print("  F1 y F2 - HAY DOS GRADOS DE LIBERTAD?")
    print("  F1 muere si |corr(e,psi)| >= 0,90.   F2 muere si R2(psi ~ x_target) >= 0,90.")
    print("=" * 100)

    print("")
    print("  Definiciones VIEJAS, para reproducir el numero ya publicado")
    print("  (e_lat = start_x - CENTER en px, psi = heading = chord start->target)")
    E, P, S = [], [], []
    for _v, f in _todos(datos):
        if f["target"] is None or f["start"] is None or f["heading"] is None:
            continue
        E.append(f["start"][0] - LS.CENTER)
        P.append(f["heading"])
        S.append(f["ang_prod"])
    E, P, S = np.array(E), np.array(P), np.array(S)
    A = np.column_stack([E, P, np.ones(len(S))])
    c, _, _, _ = np.linalg.lstsq(A, S, rcond=None)
    pred = A @ c
    r2 = 1 - ((S - pred) ** 2).sum() / ((S - S.mean()) ** 2).sum()
    sE, sP = np.std(E) * abs(c[0]), np.std(P) * abs(c[1])
    print("    n = %d" % len(S))
    print("    steer = %+.3f*e_lat %+.3f*psi %+.2f     R2 = %.3f"
          % (c[0], c[1], c[2], r2))
    print("    varianza:  posicion %.1f %%   rumbo %.1f %%"
          % (100 * sE / (sE + sP), 100 * sP / (sE + sP)))
    print("    corr(e_lat, psi) = %+.3f" % np.corrcoef(E, P)[0, 1])

    print("")
    print("  Definiciones NUEVAS (e y psi proyectados al suelo), en banda de HFOV")
    print("  y de arco de tangente. Cada celda: corr(e,psi) / R2(psi~x_target)")
    print("")
    print("    %-10s %s" % ("arco", "".join("%22s" % ("HFOV %.0f" % h)
                                            for h in LS.HFOV_BANDA)))
    veredictos = []
    for arco in LS.ARCO_PSI_BANDA:
        fila = ""
        for hfov in LS.HFOV_BANDA:
            ee, pp, xx = [], [], []
            for _v, f in _todos(datos):
                if f["target"] is None:
                    continue
                e, psi = LS.errores(f, hfov, arco)
                if e is None or psi is None:
                    continue
                ee.append(e)
                pp.append(psi)
                xx.append(f["target"][0])
            ee, pp, xx = np.array(ee), np.array(pp), np.array(xx)
            r_ep = float(np.corrcoef(ee, pp)[0, 1])
            B = np.column_stack([xx, np.ones(len(xx))])
            cc, _, _, _ = np.linalg.lstsq(B, pp, rcond=None)
            pr = B @ cc
            r2x = 1 - ((pp - pr) ** 2).sum() / ((pp - pp.mean()) ** 2).sum()
            fila += "%22s" % ("%+.3f / %.3f" % (r_ep, r2x))
            veredictos.append((arco, hfov, abs(r_ep), r2x, len(ee)))
        print("    %-10.2f %s" % (arco, fila))

    print("")
    peor_f1 = max(v[2] for v in veredictos)
    peor_f2 = max(v[3] for v in veredictos)
    print("    F1: max |corr(e,psi)| en toda la banda = %.3f   -> %s"
          % (peor_f1, "*** MUERE" if peor_f1 >= 0.90 else "SOBREVIVE"))
    print("    F2: max R2(psi ~ x_target) en toda la banda = %.3f   -> %s"
          % (peor_f2, "*** MUERE" if peor_f2 >= 0.90 else "SOBREVIVE"))
    print("=" * 100)
    return peor_f1 < 0.90 and peor_f2 < 0.90


# --------------------------------------------------------------------------
# FIDELIDAD - el espia reproduce la ley de produccion?
# --------------------------------------------------------------------------
def fidelidad(datos):
    print("")
    print("=" * 100)
    print("  FIDELIDAD DEL ESPIA")
    print("  ley_steer.steer_actual tiene que reproducir EXACTAMENTE el angulo")
    print("  que vision_linea entrega hoy. Criterio: 0 discrepancias.")
    print("=" * 100)
    print("")
    n = mal = 0
    peor = 0.0
    for vid in AUTONOMOS:
        d = 0
        pv = 0.0
        for f in datos.get(vid, []):
            if f["target"] is None:
                continue
            a = LS.steer_actual(f)
            b = f["ang_prod"]
            n += 1
            if a != b:
                d += 1
                pv = max(pv, abs(a - b))
        mal += d
        peor = max(peor, pv)
        if vid in datos:
            print("  %-18s %6d frames   %d discrepancias" % (vid, sum(
                1 for f in datos[vid] if f["target"] is not None), d))
    print("")
    print("  TOTAL %d frames, %d discrepancias, peor delta %.2e" % (n, mal, peor))
    print("  %s" % ("FIDELIDAD OK" if mal == 0 else "*** ABORTAR: el espia cambia lo que mide"))
    print("=" * 100)
    return mal == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extraer", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--f12", action="store_true")
    ap.add_argument("--fidelidad", action="store_true")
    a = ap.parse_args()

    if a.extraer or a.forzar:
        print("  extrayendo (vision de produccion, CAMINO+MONO)...")
        extraer(forzar=a.forzar)
        return 0

    datos = extraer()
    if a.fidelidad:
        fidelidad(datos)
    if a.f12:
        f12(datos)
    if not (a.fidelidad or a.f12):
        fidelidad(datos)
        f12(datos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
