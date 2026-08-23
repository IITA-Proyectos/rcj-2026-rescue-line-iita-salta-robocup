# -*- coding: utf-8 -*-
"""La memoria congelada, medida SOLO en conduccion autonoma. NO TOCA EL ROBOT.

Por que este archivo existe
---------------------------
El primer intento de demostrar que la memoria congelada bloquea la
reacquisicion usaba `video_4` frames 547-555. **Ese tramo no vale**: Benjamin
informo que ahi el robot estaba LEVANTADO del piso y siendo reposicionado a
mano. Con el robot en el aire la camara no conserva su pose, la premisa
"componente que toca la fila 119 = cinta debajo del robot" deja de ser cierta, y
nada de lo que pase ahi dice como se comportaria conduciendo.

Se intento construir un detector de pose por imagen para no depender de
anotacion humana. **Fallo**, y el numero esta publicado para que no se vuelva a
intentar sin datos nuevos: la mejor de tres senales -la fila donde termina el
suelo en la banda central- separa el tramo etiquetado con 1,34 sigma, y con el
umbral que cubre el 75 % del tramo marca ademas el 27,9 % de todo el resto del
video. Inservible.

La unica etiqueta solida disponible es a nivel de VIDEO, y no hay que medirla:
se sabe de como se grabo cada uno.

    AUTONOMO   los 10 paneles 640x240: la Pi corriendo, la Teensy moviendo, el
               panel grabado por `parche_planner.py`. El robot estaba apoyado.
    MANUAL     `video_4.avi`: Benjamin lo movio a mano, y ademas lo levanto
               entre ~515 y ~575.

Este banco mide SOLO los diez autonomos.

Que mide, y por que contesta la pregunta sin ground truth
---------------------------------------------------------
`nuevo_code_v2.py:320-322` y `:342-344` salen de PERDIDA sin resetear
`prev_target`, `prev_entry` ni `last_good_target`. Y `nuevo_code_v2.py:340`
descarta una componente y declara PERDIDA si

    component_distance(comp, ref) > 75   Y   comp["ymax"] < 70

donde `ref` es `prev_target` si existe. Si esa memoria quedo vieja, la distancia
se mide contra un lugar donde la cinta ya no esta, y una componente
perfectamente buena puede quedar rechazada por lejania.

La pregunta -la memoria congelada bloquea reacquisiciones de verdad?- se puede
contestar sin saber cual era la cinta correcta:

  * cuantos frames de PERDIDA tienen una componente candidata GRANDE que la
    regla rechaza,
  * cuan vieja estaba la memoria contra la que se la comparo,
  * y -el contrafactico- si con la memoria reseteada (`ref` = el centro de
    abajo, que es `prev_entry` inicial) esa misma componente habria pasado.

El contrafactico es aritmetica sobre la misma regla, no una ley nueva: se
recalcula `component_distance` contra (79.5, 119) y se aplica el mismo umbral.

Uso
---
    python memoria_perdida.py
"""

import argparse
import csv
import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))

# los DIEZ paneles. `video_4.avi` NO esta: es manual y ademas tiene un tramo con
# el robot levantado.
AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]

AREA_SERIA = 200        # una componente de este tamano no es ruido
FPS = 100.0 / 3.0


def cargar(code_dir):
    ruta = os.path.join(code_dir, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        raise IOError("no esta nuevo_code_v4.py en %s" % code_dir)
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def analizar(v4, v2, ruta):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = v4.NuevoCodeV4(FPS)
    CENTRO_ABAJO = (v2.CENTER, 119.0)

    filas = []
    prev_ant = None
    edad = 0
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = v2.frame_pi(fr)
        prev_target = tr.per.prev_target

        if prev_target != prev_ant:
            edad = 0
        else:
            edad += 1
        prev_ant = prev_target

        # --- que candidatas habia, y como las juzga la regla de v2:340 ------
        m = v2.mask_linea(g)
        lab, cands = v2.cc_candidates(m)
        hay_near = any(c["near"] for c in cands)
        bloqueada = None
        if cands and not hay_near:
            ref = prev_target if prev_target is not None else tr.per.prev_entry
            amax = max(c["area"] for c in cands)
            viable = [c for c in cands
                      if c["area"] >= max(v2.MIN_AREA, 0.03 * amax)]
            elegida = min(viable, key=lambda q:
                          v2.component_distance(lab, q["k"], ref)
                          + 0.08 * (119 - q["ymax"]))
            d_ref = v2.component_distance(lab, elegida["k"], ref)
            rechaza = (d_ref > 75 and elegida["ymax"] < 70)
            if rechaza and elegida["area"] >= AREA_SERIA:
                # CONTRAFACTICO: la MISMA regla, con la memoria reseteada
                d_reset = v2.component_distance(lab, elegida["k"], CENTRO_ABAJO)
                pasaria = not (d_reset > 75 and elegida["ymax"] < 70)
                bloqueada = dict(area=elegida["area"], ymax=elegida["ymax"],
                                 d_ref=d_ref, d_reset=d_reset,
                                 pasaria=pasaria, edad=edad)

        r = tr.step(g)
        filas.append(dict(i=i, state=r.get("state"), tgt=r.get("target"),
                          edad=edad, bloq=bloqueada))
        i += 1
    cap.release()
    return filas


def rachas(filas):
    """Rachas consecutivas de frames con una componente grande bloqueada."""
    out = []
    ini = None
    for f in filas:
        if f["bloq"] is not None:
            if ini is None:
                ini = f
        else:
            if ini is not None:
                tramo = [x for x in filas if ini["i"] <= x["i"] < f["i"]]
                out.append(dict(
                    desde=ini["i"], hasta=f["i"] - 1, largo=f["i"] - ini["i"],
                    area_max=max(x["bloq"]["area"] for x in tramo),
                    edad_max=max(x["bloq"]["edad"] for x in tramo),
                    d_ref_med=float(np.median([x["bloq"]["d_ref"] for x in tramo])),
                    d_reset_med=float(np.median([x["bloq"]["d_reset"] for x in tramo])),
                    pasarian=sum(1 for x in tramo if x["bloq"]["pasaria"])))
                ini = None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--code-dir", default=os.path.join(
        os.path.expanduser("~"), "Downloads"))
    a = ap.parse_args(argv)
    code_dir = a.code_dir
    if not os.path.exists(os.path.join(code_dir, "nuevo_code_v4.py")):
        if os.path.exists(os.path.join(AQUI, "nuevo_code_v4.py")):
            code_dir = AQUI
    v4, _v3, v2 = cargar(code_dir)

    print("")
    print("=" * 84)
    print(" LA MEMORIA CONGELADA, SOLO EN LOS 10 VIDEOS AUTONOMOS")
    print(" video_4 EXCLUIDO: es manual, y entre ~515 y ~575 el robot estaba")
    print(" levantado del piso. No sirve para juzgar conducta autonoma.")
    print("=" * 84)
    print("")
    print("  %-14s %6s %7s %8s %8s %9s %9s"
          % ("video", "frames", "bloq", "rachas", "max f", "edad max", "salvables"))

    tot = dict(n=0, bloq=0, rachas=0, salv=0)
    todas = []
    out = os.path.join(AQUI, "memoria_perdida.csv")
    fh = open(out, "w", newline="", encoding="utf-8")
    wr = csv.writer(fh)
    wr.writerow(["video", "desde", "hasta", "largo_frames", "largo_ms",
                 "area_max", "edad_prev_target_max",
                 "dist_a_memoria_vieja", "dist_a_centro_reseteado",
                 "frames_que_pasarian_con_reset"])
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  falta %s" % vid)
            continue
        filas = analizar(v4, v2, ruta)
        rs = rachas(filas)
        nb = sum(1 for f in filas if f["bloq"] is not None)
        salv = sum(r["pasarian"] for r in rs)
        tot["n"] += len(filas)
        tot["bloq"] += nb
        tot["rachas"] += len(rs)
        tot["salv"] += salv
        todas += [(vid, r) for r in rs]
        print("  %-14s %6d %7d %8d %8s %9s %9d"
              % (vid.replace(".avi", ""), len(filas), nb, len(rs),
                 max((r["largo"] for r in rs), default=0),
                 max((r["edad_max"] for r in rs), default=0), salv))
        for r in rs:
            wr.writerow([vid.replace(".avi", ""), r["desde"], r["hasta"],
                         r["largo"], "%.0f" % (1000.0 * r["largo"] / FPS),
                         r["area_max"], r["edad_max"],
                         "%.1f" % r["d_ref_med"], "%.1f" % r["d_reset_med"],
                         r["pasarian"]])
    fh.close()
    print("  %-14s %6d %7d %8d %8s %9s %9d"
          % ("TOTAL", tot["n"], tot["bloq"], tot["rachas"], "", "", tot["salv"]))

    print("")
    if not todas:
        print("  NO SE ENCONTRO NINGUN CASO en conduccion autonoma.")
        print("  La memoria congelada existe en el codigo, pero sobre este")
        print("  material NO produjo ningun bloqueo de reacquisicion medible.")
    else:
        largos = [r["largo"] for _v, r in todas]
        edades = [r["edad_max"] for _v, r in todas]
        print("  %d rachas en %d frames autonomos (%.2f %% de los frames)"
              % (len(todas), tot["n"], 100.0 * tot["bloq"] / max(tot["n"], 1)))
        print("  largo de la racha: p50 %.0f  p90 %.0f  MAX %d frames (%.0f ms)"
              % (np.median(largos), np.percentile(largos, 90), max(largos),
                 1000.0 * max(largos) / FPS))
        print("  edad de prev_target al bloquear: p50 %.0f  MAX %d frames"
              % (np.median(edades), max(edades)))
        print("  frames que HABRIAN pasado con la memoria reseteada: %d de %d (%.1f %%)"
              % (tot["salv"], tot["bloq"], 100.0 * tot["salv"] / max(tot["bloq"], 1)))
        print("")
        print("  LAS 10 RACHAS MAS LARGAS")
        print("      %-14s %7s %7s %8s %9s %8s %8s %9s"
              % ("video", "desde", "largo", "ms", "area max", "d vieja", "d reset",
                 "salvables"))
        for vid, r in sorted(todas, key=lambda t: -t[1]["largo"])[:10]:
            print("      %-14s %7d %7d %8.0f %9d %8.1f %8.1f %9d"
                  % (vid.replace(".avi", ""), r["desde"], r["largo"],
                     1000.0 * r["largo"] / FPS, r["area_max"],
                     r["d_ref_med"], r["d_reset_med"], r["pasarian"]))
    print("")
    print("  CSV: %s" % os.path.basename(out))
    print("")
    print("  LIMITE: los diez son autonomos por como se grabaron, no por una")
    print("  medicion. Si alguno de ellos corresponde a la corrida marcada")
    print("  INVALIDA_ruedas_en_el_aire, hay que sacarlo y volver a correr.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
