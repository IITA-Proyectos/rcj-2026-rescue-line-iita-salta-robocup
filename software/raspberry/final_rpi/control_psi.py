# -*- coding: utf-8 -*-
"""
CONTROL EXTERNO DEL ESTIMADOR DE RUMBO.

El problema: `psi` medido sobre el camino proyectado al suelo da p50 = 44 grados
de |rumbo| sobre 12.000 frames. Eso es MUCHO para un robot que supuestamente
sigue una linea, y antes de reportar un solo numero mas hay que decidir si el
estimador esta roto o si el sistema realmente opera asi.

Coincide con el `heading` que la propia candidata ya calcula (p50 50,2), asi que
no es un error de escala. Pero los dos podrian estar mal de la misma forma.

EL CONTROL: el yaw real por correlacion de fase sobre el fondo lejano, que NO
depende de ninguna vision candidata. Es el mismo estimador que uso `gate.py`
para descubrir que los controles positivos oscilan.

    Si el robot NO esta girando durante ~0,3 s y esta siguiendo la cinta,
    entonces la cinta esta derecha adelante y |psi| tiene que ser CHICO.
    Si |psi| es igual de grande ahi que en las curvas, el estimador esta roto
    y todo lo que sigue se cae.

Y al reves: si |psi| crece monotonamente con el giro real, el estimador mide
algo fisico.

NO ES CIRCULAR: `psi` es una variable geometrica derivada del camino visible,
no del comando. Lo circular seria usar el yaw real para decidir CUAL ley es
mejor -el robot giro obedeciendo a la ley vieja-, y eso no se hace aca.
"""

import argparse
import math
import os
import pickle
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

CACHE_YAW = os.path.join(AQUI, "_yaw_cache.pkl")
FPS = 100.0 / 3.0
VENTANA = 10          # 0,3 s. Frame a frame la correlacion de fase es ruido
                      # puro: da 900 grados/s en un robot que gira a 39.
GPP = 60.0 / 320.0    # grados por pixel con el FOV nominal


def yaw_video(ruta):
    """Corrimiento acumulado del fondo lejano, en grados, por frame."""
    cap = cv2.VideoCapture(ruta)
    prev = None
    han = None
    acum = []
    a = 0.0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        half = fr[:, :320] if fr.shape[1] >= 640 else fr
        g = cv2.cvtColor(cv2.rotate(half, cv2.ROTATE_180), cv2.COLOR_BGR2GRAY)
        b = g[5:45, :].astype(np.float32)
        if han is None:
            han = (np.hanning(b.shape[0])[:, None]
                   * np.hanning(b.shape[1])[None, :])
        b = (b - b.mean()) * han
        if prev is not None:
            (dx, _dy), resp = cv2.phaseCorrelate(prev, b)
            if resp > 0.03:
                a += -dx * GPP
        prev = b
        acum.append(a)
    cap.release()
    return np.array(acum)


def cargar_yaw(forzar=False):
    if os.path.exists(CACHE_YAW) and not forzar:
        with open(CACHE_YAW, "rb") as f:
            return pickle.load(f)
    out = {}
    for vid in SP.AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        out[vid] = yaw_video(ruta)
        print("  %-18s %6d frames de yaw" % (vid, len(out[vid])))
    with open(CACHE_YAW, "wb") as f:
        pickle.dump(out, f)
    return out


def tasa(acum, i, ventana=VENTANA):
    """Grados/s sostenidos centrados en el frame i. None si no alcanza."""
    a = max(0, i - ventana // 2)
    b = min(len(acum) - 1, a + ventana)
    if b - a < ventana:
        return None
    return (acum[b] - acum[a]) / ((b - a) / FPS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--arco", type=float, default=LS.ARCO_PSI)
    ap.add_argument("--hfov", type=float, default=LS.HFOV_NOMINAL)
    a = ap.parse_args()

    print("  yaw real por correlacion de fase (fondo lejano, ventana 0,3 s)")
    yaws = cargar_yaw(a.forzar)
    datos = SP.extraer()

    filas = []
    for vid in SP.AUTONOMOS:
        if vid not in yaws or vid not in datos:
            continue
        ac = yaws[vid]
        for f in datos[vid]:
            if f["target"] is None or f["i"] >= len(ac):
                continue
            e, psi = LS.errores(f, a.hfov, a.arco)
            if e is None or psi is None:
                continue
            t = tasa(ac, f["i"])
            if t is None:
                continue
            filas.append((abs(t), abs(psi), abs(e), abs(f["ang_prod"])))
    A = np.array(filas)
    print("")
    print("=" * 96)
    print("  |psi| CONTRA EL GIRO REAL DEL ROBOT   (n = %d frames)" % len(A))
    print("  arco %.2f   HFOV %.0f" % (a.arco, a.hfov))
    print("=" * 96)
    print("")
    print("  Si el estimador es sano, |psi| tiene que CRECER con el giro real,")
    print("  y ser chico en la banda donde el robot no gira.")
    print("")
    bordes = [0, 5, 10, 20, 39, 80, 1e9]
    print("  %-18s %7s %8s %8s %8s %10s %10s"
          % ("|yaw real| deg/s", "n", "|psi|p25", "|psi|p50", "|psi|p75",
             "|e| p50", "|steer|p50"))
    for lo, hi in zip(bordes, bordes[1:]):
        m = (A[:, 0] >= lo) & (A[:, 0] < hi)
        if m.sum() < 30:
            continue
        s = A[m]
        et = "%.0f - %.0f" % (lo, hi) if hi < 1e9 else "> %.0f" % lo
        print("  %-18s %7d %8.1f %8.1f %8.1f %10.3f %10.1f"
              % (et, m.sum(), np.percentile(s[:, 1], 25),
                 np.percentile(s[:, 1], 50), np.percentile(s[:, 1], 75),
                 np.percentile(s[:, 2], 50), np.percentile(s[:, 3], 50)))
    print("")
    print("  correlacion de |yaw real| con |psi|         %+.3f"
          % np.corrcoef(A[:, 0], A[:, 1])[0, 1])
    print("  correlacion de |yaw real| con |e|           %+.3f"
          % np.corrcoef(A[:, 0], A[:, 2])[0, 1])
    print("  correlacion de |yaw real| con |steer actual| %+.3f"
          % np.corrcoef(A[:, 0], A[:, 3])[0, 1])
    print("")
    quieto = A[A[:, 0] < 5]
    print("  ROBOT PRACTICAMENTE QUIETO (|yaw| < 5 deg/s): %d frames (%.1f %%)"
          % (len(quieto), 100 * len(quieto) / len(A)))
    if len(quieto):
        print("    |psi| ahi:  p10 %.1f  p25 %.1f  p50 %.1f  p75 %.1f  p90 %.1f"
              % tuple(np.percentile(quieto[:, 1], [10, 25, 50, 75, 90])))
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
