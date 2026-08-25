# -*- coding: utf-8 -*-
"""
TEST DE INTEGRACION DE LA LEY DE STEER. Tres preguntas, las tres obligatorias.

  1. APAGADA, no cambia NADA. El angulo que sale de vision_linea sin
     LEY_STEER tiene que ser identico, bit a bit, al que salia antes del
     parche. La referencia es `_sep_cache.pkl`, extraido ANTES de tocar el
     modulo.

  2. ENCENDIDA, hace exactamente lo que el banco midio. El angulo de
     produccion tiene que coincidir con ley_steer.steer_stanley calculado
     aparte sobre el mismo dict, con los mismos parametros.

  3. FALTA el archivo y el robot SIGUE. Lo que corre en la Raspberry es un
     archivo suelto: alcanza con olvidarse de copiar `ley_steer.py` al lado
     para que la ley no arranque. Tiene que caer a la ley de hoy y avisar UNA
     sola vez, no por frame -en la Pi eso es I/O sincronico adentro del lazo
     de vision, o sea FPS perdido por avisar de algo que ya no va a cambiar-.

Si (1) falla, el parche voltea el comportamiento de hoy y se revierte.
Si (2) falla, lo que corre en el robot no es lo que se midio en el banco, y
el A/B no vale.
Si (3) falla, un archivo olvidado voltea una corrida.

    python test_ley_steer.py
"""

import importlib.util
import os
import pickle
import sys

import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402

VIDEOS = ["hist.avi", "lineal.avi", "seguir.avi", "con_planner.avi"]
CACHE = os.path.join(AQUI, "_sep_cache.pkl")


def cargar_vl(ley):
    """Recarga vision_linea con el entorno pedido. Sin cache de modulos."""
    os.environ["VISION_LINEA"] = "camino"
    if ley:
        os.environ["LEY_STEER"] = "stanley"
    else:
        os.environ.pop("LEY_STEER", None)
    sys.modules.pop("vision_linea", None)
    sp = importlib.util.spec_from_file_location(
        "vision_linea", os.path.join(AQUI, "vision_linea.py"))
    vl = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(vl)
    return vl


def corrida(vl, vid):
    """Angulos de produccion, y el dict crudo, frame a frame."""
    vl._tr = None
    vl._arrancar()
    cap = cv2.VideoCapture(os.path.join(AQUI, vid))
    out = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = vl._v2.frame_pi(fr)
        a = vl.angulo(g)
        out.append((a, dict(vl.ultimo())))
    cap.release()
    return out


def main():
    with open(CACHE, "rb") as f:
        ref = pickle.load(f)

    print("")
    print("=" * 96)
    print("  1) APAGADA - el angulo tiene que ser el de siempre, bit a bit")
    print("     referencia: _sep_cache.pkl, extraido ANTES del parche")
    print("=" * 96)
    print("")
    vl = cargar_vl(False)
    print("  LEY_ACTIVA = %s" % vl.LEY_ACTIVA)
    total = mal = 0
    for vid in VIDEOS:
        r = corrida(vl, vid)
        d = 0
        for (a, _u), f in zip(r, ref[vid]):
            if a is None and f["ang_prod"] is None:
                continue
            total += 1
            if a != f["ang_prod"]:
                d += 1
        mal += d
        print("  %-18s %6d frames   %d discrepancias" % (vid, len(r), d))
    print("")
    print("  TOTAL %d angulos comparados, %d discrepancias -> %s"
          % (total, mal, "OK" if mal == 0 else "*** REVERTIR EL PARCHE"))

    print("")
    print("=" * 96)
    print("  2) ENCENDIDA - tiene que dar lo que el banco midio")
    print("=" * 96)
    print("")
    vl2 = cargar_vl(True)
    print("  LEY_ACTIVA = %s   k=%.4f g=%.4f k_psi=%.2f hfov=%.0f arco=%.2f"
          % (vl2.LEY_ACTIVA, vl2.LEY_K, vl2.LEY_G, vl2.LEY_KPSI,
             vl2.LEY_HFOV, vl2.LEY_ARCO))
    total2 = mal2 = cae = distintos = 0
    peor = 0.0
    for vid in VIDEOS:
        r = corrida(vl2, vid)
        d = 0
        for (a, u), f in zip(r, ref[vid]):
            if f["target"] is None:
                continue
            esperado = LS.steer_stanley(f, v_norm=f["factor"], k=vl2.LEY_K,
                                        k_psi=vl2.LEY_KPSI, g=vl2.LEY_G,
                                        hfov=vl2.LEY_HFOV, arco=vl2.LEY_ARCO)
            if esperado is None:
                esperado = f["ang_prod"]
                cae += 1
            total2 += 1
            if a is None or abs(a - esperado) > 1e-9:
                d += 1
                peor = max(peor, abs((a or 0.0) - esperado))
            if a is not None and abs(a - f["ang_prod"]) > 1e-9:
                distintos += 1
        mal2 += d
        print("  %-18s %6d frames   %d discrepancias" % (vid, len(r), d))
    print("")
    print("  TOTAL %d angulos, %d discrepancias (peor %.2e) -> %s"
          % (total2, mal2, peor, "OK" if mal2 == 0 else "*** EL ROBOT NO CORRE LO MEDIDO"))
    print("  frames donde la ley nueva cae a la vieja (sin rumbo): %d (%.1f %%)"
          % (cae, 100.0 * cae / max(total2, 1)))
    print("  frames donde la ley nueva da OTRO angulo que la vieja: %d (%.1f %%)"
          % (distintos, 100.0 * distintos / max(total2, 1)))
    print("")
    print("=" * 96)
    print("  3) SIN ley_steer.py EN EL DISCO - el robot tiene que seguir")
    print("=" * 96)
    print("")
    ruta = os.path.join(AQUI, "ley_steer.py")
    guardado = os.path.join(AQUI, "_ley_steer.test_movido")
    ok3 = False
    try:
        os.rename(ruta, guardado)
        vl3 = cargar_vl(True)
        vl3._arrancar()
        cap = cv2.VideoCapture(os.path.join(AQUI, VIDEOS[3]))
        n = sin = 0
        vals = []
        while True:
            leido, fr = cap.read()
            if not leido:
                break
            a = vl3.angulo(vl3._v2.frame_pi(fr))
            n += 1
            if a is None:
                sin += 1
            else:
                vals.append(a)
        cap.release()
        # los angulos tienen que ser los de la LEY VIEJA, no otra cosa
        iguales = sum(1 for a, f in zip(vals, [x for x in ref[VIDEOS[3]]
                                               if x["ang_prod"] is not None])
                      if a == f["ang_prod"])
        print("  %d frames, %d sin opinion, %d angulos" % (n, sin, len(vals)))
        print("  ACTIVA %s   _LS_FALLO %s   (tiene que ser True / True)"
              % (vl3.ACTIVA, vl3._LS_FALLO))
        print("  angulos identicos a la ley vieja: %d de %d"
              % (iguales, len(vals)))
        ok3 = (vl3.ACTIVA and vl3._LS_FALLO and len(vals) > 0
               and iguales == len(vals))
        print("  -> %s" % ("OK" if ok3 else "*** un archivo olvidado voltea la corrida"))
    finally:
        if os.path.exists(guardado):
            os.rename(guardado, ruta)
    print("=" * 96)
    return 0 if (mal == 0 and mal2 == 0 and ok3) else 1


if __name__ == "__main__":
    sys.exit(main())
