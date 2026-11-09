# -*- coding: utf-8 -*-
"""A/B ESTRUCTURAL: V2 solo contra V3 contra V4. NO TOCA EL ROBOT.

La pregunta
-----------
`clasificar_huecos.py` dejo esto: de 277 huecos en los 10 videos autonomos, 209
(75,4 %) los abre un guard y no la percepcion, y el guard rechaza un salto de
p50 63,0 px para terminar aceptando uno de 65,4 px un frame despues. Delta
mediano +0,0.

Si eso es asi, la pregunta no es que guard agregar sino **si V3 y V4 aportan
algo medible**. Este banco los corre a los tres sobre el mismo material y los
compara. Ninguno se modifica: se instancian tal cual.

    NuevoCodeV2   percepcion sola, con sus dos limitadores internos
    NuevoCodeV3   + guard de rama (signo) + slew del preview
    NuevoCodeV4   + guard espacial 24/30 px

Como se compara, para no decidir por una sola metrica
-----------------------------------------------------
Benjamin pidio explicitamente no decidir por cantidad de saltos. Se miden seis
cosas, y una version solo "gana" si no empeora ninguna de las obligatorias:

  disponibilidad   % de frames con target. Un frame sin target es un frame sin
                   autoridad, y eso tiene costo aunque no aparezca en los saltos.
  saltos reales    saltos del target > 24 px MEDIDOS A TRAVES DE LOS HUECOS.
                   Es la metrica honesta: la de V4 pone prev=None en el hueco y
                   por eso no puede ver el unico salto que no limita.
  inversiones      cambios de signo del steer con banda muerta de 10 grados.
  huecos           eventos perdida->reacquisicion.
  suavidad         mediana del cambio de steer entre frames consecutivos.
  controles        `hist_exito` y `lineal_positivo` son OBLIGATORIOS: cualquier
                   version que no de 100/100 y 73/73 queda descartada.

`video_4` se reporta aparte y solo en los tramos fisicamente validos: entre ~515
y ~575 el robot estaba levantado.

Uso
---
    python ab_v2_v3_v4.py
    python ab_v2_v3_v4.py --controles
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
AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
CONTROLES = [
    ("hist_exito", "hist.avi", 33.3, 580, 679, 100),
    ("hist_falla", "hist.avi", 33.3, 1354, 1490, None),
    ("lineal_positivo", "lineal.avi", 33.3, 800, 872, 73),
    # video_4 solo en los tramos fisicamente validos
    ("video_4_pre", "video_4.avi", 20.0, 0, 514, None),
    ("video_4_post", "video_4.avi", 20.0, 576, 10 ** 9, None),
]
FPS = 100.0 / 3.0
DEAD = 10.0
UMBRAL = 24.0


def cargar():
    ruta = os.path.join(AQUI, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        ruta = os.path.join(os.path.expanduser("~"), "Downloads", "nuevo_code_v4.py")
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def variantes(v4, v3, v2, fps):
    return [("V2", v2.NuevoCodeV2(fps)),
            ("V3", v3.NuevoCodeV3(fps)),
            ("V4", v4.NuevoCodeV4(fps))]


def steer_de(t, W, CENTER):
    if t is None:
        return None
    return float(np.clip(-90.0 * (t[0] - CENTER) / (W / 2.0), -90, 90))


def correr(v4, v3, v2, ruta, fps, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    W, CENTER = v2.W, v2.CENTER
    vs = variantes(v4, v3, v2, fps)
    series = {n: [] for n, _ in vs}
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        g = v2.frame_pi(fr)
        for n, tr in vs:
            r = tr.step(g)          # el estado se arrastra desde el frame 0
            if i >= desde:
                t = r.get("target")
                series[n].append((t, steer_de(t, W, CENTER), r.get("state")))
        i += 1
    cap.release()
    return series


def metricas(serie):
    n = len(serie)
    tgts = [x[0] for x in serie]
    st = [x[1] for x in serie]
    con = sum(1 for t in tgts if t is not None)

    # saltos REALES: a traves de los huecos, comparando contra el ultimo target
    # que hubo, no reseteando en el hueco. Es la diferencia con la metrica de V4.
    saltos = []
    ult = None
    for t in tgts:
        if t is None:
            continue
        if ult is not None:
            saltos.append(math.hypot(t[0] - ult[0], t[1] - ult[1]))
        ult = t
    saltos = np.asarray(saltos) if saltos else np.array([0.0])

    # huecos
    huecos = 0
    dentro = False
    visto = False
    for t in tgts:
        if t is None:
            if visto and not dentro:
                huecos += 1
                dentro = True
        else:
            dentro = False
            visto = True

    # inversiones con banda muerta
    sg = []
    for a in st:
        if a is None:
            continue
        if a > DEAD:
            sg.append(1)
        elif a < -DEAD:
            sg.append(-1)
    inv = sum(1 for a, b in zip(sg, sg[1:]) if a != b)

    # suavidad del comando entre frames CONSECUTIVOS con target en los dos
    dif = [abs(b - a) for a, b in zip(st, st[1:])
           if a is not None and b is not None]
    return dict(n=n, con=con, disp=100.0 * con / max(n, 1),
                sin_aut=n - con, huecos=huecos,
                s_gt=int((saltos > UMBRAL).sum()),
                s_p50=float(np.median(saltos)), s_p90=float(np.percentile(saltos, 90)),
                s_max=float(saltos.max()), inv=inv,
                suav=float(np.median(dif)) if dif else float("nan"))


def fila(et, m):
    return ("  %-4s %6d %7.2f %% %7d %7d %7d %7.1f %7.1f %6d %7.2f"
            % (et, m["n"], m["disp"], m["sin_aut"], m["huecos"], m["s_gt"],
               m["s_p90"], m["s_max"], m["inv"], m["suav"]))


CAB = ("  %-4s %6s %9s %7s %7s %7s %7s %7s %6s %7s"
       % ("ver", "n", "disp", "s/aut", "huecos", ">24px", "s p90", "s max",
          "inv", "suav"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--controles", action="store_true",
                    help="solo los casos de control")
    a = ap.parse_args(argv)
    v4, v3, v2 = cargar()

    print("")
    print("=" * 88)
    print(" A/B ESTRUCTURAL   V2 solo  contra  V3  contra  V4")
    print(" saltos medidos A TRAVES de los huecos, que es lo que la metrica de")
    print(" V4 no puede ver (nuevo_code_v4.py:316-318 pone prev=None)")
    print("=" * 88)

    print("")
    print(" CASOS DE CONTROL   (hist_exito y lineal_positivo son OBLIGATORIOS)")
    print(CAB)
    obligatorios = {}
    for nom, vid, fps, d, h, exige in CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        ser = correr(v4, v3, v2, ruta, fps, d, h)
        print("  --- %s%s" % (nom, ("   exige %d/%d targets" % (exige, exige))
                              if exige else ""))
        for et in ("V2", "V3", "V4"):
            m = metricas(ser[et])
            print(fila(et, m))
            if exige:
                obligatorios.setdefault(et, []).append(
                    (nom, m["con"], exige, m["con"] >= exige))
    if obligatorios:
        print("")
        print("  VEREDICTO SOBRE LOS OBLIGATORIOS")
        for et, lst in obligatorios.items():
            ok = all(x[3] for x in lst)
            det = "  ".join("%s %d/%d" % (n, c, e) for n, c, e, _ in lst)
            print("      %-4s %s   %s" % (et, "PASA" if ok else "FALLA", det))

    if a.controles:
        return 0

    print("")
    print(" LOS 10 VIDEOS AUTONOMOS")
    print(CAB)
    acum = {et: [] for et in ("V2", "V3", "V4")}
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        ser = correr(v4, v3, v2, ruta, FPS)
        print("  --- %s" % vid.replace(".avi", ""))
        for et in ("V2", "V3", "V4"):
            m = metricas(ser[et])
            print(fila(et, m))
            acum[et].append(m)

    print("")
    print(" TOTAL SOBRE LOS 10 AUTONOMOS")
    print(CAB)
    tot = {}
    for et in ("V2", "V3", "V4"):
        ms = acum[et]
        t = dict(n=sum(m["n"] for m in ms), con=sum(m["con"] for m in ms),
                 sin_aut=sum(m["sin_aut"] for m in ms),
                 huecos=sum(m["huecos"] for m in ms),
                 s_gt=sum(m["s_gt"] for m in ms),
                 s_p90=float(np.mean([m["s_p90"] for m in ms])),
                 s_max=max(m["s_max"] for m in ms),
                 inv=sum(m["inv"] for m in ms),
                 suav=float(np.mean([m["suav"] for m in ms])))
        t["disp"] = 100.0 * t["con"] / max(t["n"], 1)
        tot[et] = t
        print(fila(et, t))

    print("")
    print(" DIFERENCIAS CONTRA V2 SOLO")
    print("  %-4s %12s %10s %10s %10s %10s"
          % ("ver", "disp", "sin autor.", "huecos", ">24 px", "inversiones"))
    b = tot["V2"]
    for et in ("V2", "V3", "V4"):
        t = tot[et]
        print("  %-4s %+11.2f %% %+10d %+10d %+10d %+10d"
              % (et, t["disp"] - b["disp"], t["sin_aut"] - b["sin_aut"],
                 t["huecos"] - b["huecos"], t["s_gt"] - b["s_gt"],
                 t["inv"] - b["inv"]))

    print("")
    print(" LECTURA")
    print("  Una version solo justifica su complejidad si MEJORA algo sin")
    print("  empeorar la disponibilidad. Si V3 o V4 bajan la disponibilidad y no")
    print("  bajan los saltos >24 px medidos a traves de los huecos, no aportan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
