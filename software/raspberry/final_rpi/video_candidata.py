# -*- coding: utf-8 -*-
"""VIDEO DE DIAGNOSTICO de la candidata V1 RC. NO TOCA EL ROBOT.

Corre `NuevoCodeV2 + SpatialTargetGuard` -o sea V4 con el branch guard de V3
neutralizado- sobre los casos de control y arma UN solo video con todos los
tramos rotulados.

Es registro visual, NO prueba de nada: sigue siendo replay de lazo abierto. Las
imagenes las genero la trayectoria que el robot realmente hizo con el
controlador viejo.

`video_4` entra solo en los tramos fisicamente validos: entre ~515 y ~575 el
robot estaba levantado del piso.

Uso
---
    python video_candidata.py
    python video_candidata.py --escala 3 --png
"""

import argparse
import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
_sp = importlib.util.spec_from_file_location(
    "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
v4 = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(v4)
v3 = v4.v3
v2 = v4.v3.v2

W, H, CENTER = v2.W, v2.H, v2.CENTER

TRAMOS = [
    ("hist_exito      EXITO",            "hist.avi",    33.3,  580,  679),
    ("hist_falla      FALLA HISTORICA",  "hist.avi",    33.3, 1354, 1490),
    ("lineal_positivo GIRO POSITIVO",    "lineal.avi",  33.3,  800,  872),
    ("video_4 (0-514) TEACHER, valido",  "video_4.avi", 20.0,    0,  514),
    ("video_4 (576+)  TEACHER, valido",  "video_4.avi", 20.0,  576, 10 ** 9),
]


class Candidata(v4.NuevoCodeV4):
    """V2 + spatial guard. El branch guard de V3 queda neutralizado.

    No se modifica ningun archivo: se sustituye el objeto por uno que deja
    pasar el target sin tocarlo.
    """

    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"

    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.branch_guard = Candidata._Nulo()


def panel(r):
    """El panel de `nuevo_code_v4.draw_panel`, reusado tal cual."""
    return v4.draw_panel(r)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--escala", type=int, default=3)
    ap.add_argument("--salida", default=os.path.join(AQUI, "candidata_v1rc.avi"))
    ap.add_argument("--png", action="store_true",
                    help="ademas, una hoja de contacto con frames clave")
    a = ap.parse_args(argv)

    E = a.escala
    CW, CH = W * E, H * E
    OW, OH = CW * 2, CH + 132
    vw = cv2.VideoWriter(a.salida, cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (OW, OH))
    if not vw.isOpened():
        print("no se pudo abrir el VideoWriter")
        return 1

    claves = []
    total = 0
    for etiqueta, vid, fps, d, h in TRAMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  falta %s" % vid)
            continue
        cap = cv2.VideoCapture(ruta)
        tr = Candidata(fps)
        i = 0
        n_tramo = 0
        while True:
            ok, fr = cap.read()
            if not ok or i > h:
                break
            g = v2.frame_pi(fr)
            r = tr.step(g)          # el estado se arrastra desde el frame 0
            if i >= d:
                pan = panel(r)
                out = np.zeros((OH, OW, 3), np.uint8)
                out[:CH, :CW] = cv2.resize(g, (CW, CH), interpolation=cv2.INTER_NEAREST)
                out[:CH, CW:] = cv2.resize(pan, (CW, CH), interpolation=cv2.INTER_NEAREST)

                t = r.get("target")
                st = (None if t is None else
                      float(np.clip(-90.0 * (t[0] - CENTER) / (W / 2.0), -90, 90)))
                col = v4.COLORS.get(r["state"], (235, 235, 235))
                y0 = CH + 24
                cv2.putText(out, etiqueta, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                            .58, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(out, "NUEVO CODE V1 RC   V2 + spatial guard",
                            (CW + 10, 22), cv2.FONT_HERSHEY_SIMPLEX, .5,
                            (120, 230, 120), 1, cv2.LINE_AA)
                cv2.putText(out, "frame %d   ESTADO %s   modo %s"
                            % (i, r["state"], r.get("mode", "")),
                            (10, y0), cv2.FONT_HERSHEY_SIMPLEX, .5, col, 1, cv2.LINE_AA)
                cv2.putText(out, "steer_request %s deg    atan2 viejo %+6.1f deg"
                            % ("   --" if st is None else "%+6.1f" % st,
                               v2.atan2_actual(g)),
                            (10, y0 + 26), cv2.FONT_HERSHEY_SIMPLEX, .48,
                            (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(out, "spatial %s     target %s"
                            % (r.get("spatial_guard", ""),
                               "--" if t is None else "(%.0f,%.0f)" % (t[0], t[1])),
                            (10, y0 + 50), cv2.FONT_HERSHEY_SIMPLEX, .44,
                            (200, 200, 200), 1, cv2.LINE_AA)
                cv2.putText(out, "amarillo = centerline | X = target | flecha = control"
                            "   |   REPLAY LAZO ABIERTO, no prueba trayectoria futura",
                            (10, y0 + 74), cv2.FONT_HERSHEY_SIMPLEX, .4,
                            (0, 200, 255), 1, cv2.LINE_AA)
                vw.write(out)
                n_tramo += 1
                total += 1
                if n_tramo in (1, 25, 60):
                    claves.append(out.copy())
            i += 1
        cap.release()
        print("  %-34s %4d frames" % (etiqueta, n_tramo))
    vw.release()
    print("")
    print("  VIDEO: %s   (%d frames)" % (os.path.basename(a.salida), total))

    if a.png and claves:
        filas = []
        for k in range(0, min(len(claves), 12), 2):
            par = claves[k:k + 2]
            if len(par) == 2:
                filas.append(np.hstack(par))
        if filas:
            hoja = np.vstack(filas)
            rp = os.path.join(AQUI, "candidata_v1rc.png")
            cv2.imwrite(rp, hoja)
            print("  PNG  : %s" % os.path.basename(rp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
