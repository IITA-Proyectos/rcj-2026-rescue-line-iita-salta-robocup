#!/usr/bin/env python3
# Cuanto tarda, por cuadro, cada cosa que main.py hace SOLO para registrar (no para manejar):
#   ventanas  cv2.imshow de Black Mask y Green Mask + waitKey(1): se prenden solas si hay DISPLAY
#   GRABAR    el video de 640x240 con el cartel
#   CRUDO     la copia para GRABAR_CRUDO (el PNG lo escribe otro hilo)
# Uso en la Pi, con main.py parado: DISPLAY=:0 python3 medir_costo_registro.py
import os
import queue
import threading
import time

import cv2
import numpy as np

N = 300
fr = (np.random.rand(120, 160, 3) * 255).astype(np.uint8)
mask = (np.random.rand(120, 160) > 0.7).astype(np.uint8) * 255


def medir(nombre, f):
    f()
    t0 = time.perf_counter()
    for _ in range(N):
        f()
    ms = (time.perf_counter() - t0) / N * 1000
    print("%-36s %6.2f ms por cuadro" % (nombre, ms))
    return ms


vw = cv2.VideoWriter("/tmp/bench.avi", cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (640, 240))


def grabar():
    vis = cv2.resize(fr, (320, 240), interpolation=cv2.INTER_NEAREST)
    cv2.line(vis, (0, 120), (319, 120), (0, 255, 255), 1)
    mk = cv2.cvtColor(cv2.resize(mask, (320, 240), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
    for i, s in enumerate(("viejo +10", "manda +12", "centroide")):
        cv2.putText(vis, s, (4, 14 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    cv2.putText(mk, "mascara  corte f60", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 128, 0), 1)
    vw.write(np.hstack([vis, mk]))


q = queue.Queue(maxsize=300)


def escritor():
    n = 0
    while True:
        item = q.get()
        if item is None:
            return
        n += 1
        cv2.imwrite("/tmp/bench_%d.png" % (n % 50), item)


threading.Thread(target=escritor, daemon=True).start()


def crudo():
    try:
        q.put_nowait(fr.copy())
    except queue.Full:
        pass


ms = {}
ms["GRABAR"] = medir("GRABAR (video con cartel)", grabar)
ms["CRUDO"] = medir("GRABAR_CRUDO (en el lazo)", crudo)
time.sleep(1)
if os.environ.get("DISPLAY"):
    def ventanas():
        cv2.imshow("Black Mask", mask)
        cv2.imshow("Green Mask", mask)
        cv2.waitKey(1)
    ms["ventanas"] = medir("ventanas (imshow x2 + waitKey)", ventanas)
    cv2.destroyAllWindows()
    cv2.waitKey(1)
else:
    print("sin DISPLAY: no mido las ventanas (correr con DISPLAY=:0)")
vw.release()
q.put(None)
print("\nA ~26 cuadros/s cada cuadro dura ~38 ms; la camara entrega como mucho ~30 (33 ms).")
