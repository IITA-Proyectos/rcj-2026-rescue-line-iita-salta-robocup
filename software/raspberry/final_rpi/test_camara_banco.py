# -*- coding: utf-8 -*-
"""Valida CamaraBanco con una camara FALSA a ritmo fijo. No toca la webcam."""
import importlib.util, os, sys, time
import numpy as np
import cv2

FINAL = os.path.join(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

FPS_FALSA = 30.0
PERIODO = 1.0 / FPS_FALSA
VC_REAL = cv2.VideoCapture          # guardar ANTES de parchear


class CapFalsa(object):
    """Se comporta como cv2.VideoCapture: read() bloquea hasta el proximo
    frame, como hace V4L2 a fps fijo. Sirve frames reales de hist.avi."""

    def __init__(self, src):
        self.real = VC_REAL(os.path.join(AQUI, "hist.avi"))
        self.t = time.perf_counter()
        self.abierta = True

    def set(self, *a):
        return True

    def get(self, prop):
        return {3: 160.0, 4: 120.0, 5: FPS_FALSA}.get(prop, 0.0)

    def isOpened(self):
        return self.abierta

    def read(self):
        self.t += PERIODO
        d = self.t - time.perf_counter()
        if d > 0:
            time.sleep(d)
        ok, fr = self.real.read()
        if not ok:
            self.real.set(1, 0)
            ok, fr = self.real.read()
        return ok, fr

    def release(self):
        self.abierta = False
        self.real.release()


sp = importlib.util.spec_from_file_location(
    "bench_runtime", os.path.join(AQUI, "bench_runtime.py"))
B = importlib.util.module_from_spec(sp)
sp.loader.exec_module(B)

B.cv2.VideoCapture = CapFalsa           # solo dentro de este test

v4, v3, v2 = B.cargar()
SinBranch = B.hacer_sinbranch(v4)

print("camara falsa a %.1f fps (periodo %.1f ms)" % (FPS_FALSA, PERIODO * 1e3))
c = B.medir_camara(SinBranch, v2, 400, 0, 160, 120)
B.imprimir_camara(c)

print("")
print("=== CHEQUEOS ===")
ok = True


def chk(nombre, cond, detalle=""):
    global ok
    print("  %-52s %s   %s" % (nombre, "OK" if cond else "*** FALLA", detalle))
    ok = ok and cond


lib, nue = c["libre"], c["nuevo"]
chk("libre reprocesa frames (algoritmo mas rapido que camara)",
    lib["frames_repetidos"] > 0, "%d repetidos" % lib["frames_repetidos"])
chk("esperar-nuevo NO reprocesa ninguno",
    nue["frames_repetidos"] == 0, "%d repetidos" % nue["frames_repetidos"])
chk("fps de camara observado ~= 30",
    abs(nue["fps_camara_observado"] - FPS_FALSA) < 3.0,
    "%.2f fps" % nue["fps_camara_observado"])
chk("edad de frame nuevos < un periodo (%.1f ms)" % (PERIODO * 1e3),
    nue["T_frame_age_nuevos"]["p95"] < PERIODO * 1e3,
    "p95 %.2f ms" % nue["T_frame_age_nuevos"]["p95"])
chk("edad de TODOS en modo libre > edad de nuevos (detecta staleness)",
    lib["T_frame_age_todos"]["p50"] > lib["T_frame_age_nuevos"]["p50"],
    "todos p50 %.2f vs nuevos p50 %.2f ms"
    % (lib["T_frame_age_todos"]["p50"], lib["T_frame_age_nuevos"]["p50"]))
chk("T_observed = frame_age + algorithm (coherencia)",
    abs(lib["T_observed"]["media"]
        - (lib["T_frame_age_todos"]["media"] + lib["T_algorithm"]["media"]))
    < 1e-6, "")
chk("T_algorithm parecido en ambos modos",
    abs(lib["T_algorithm"]["p50"] - nue["T_algorithm"]["p50"]) < 2.0,
    "%.3f vs %.3f ms" % (lib["T_algorithm"]["p50"], nue["T_algorithm"]["p50"]))
chk("sin lecturas fallidas del hilo",
    nue["lecturas_fallidas_del_hilo"] == 0, "")

print("")
print("RESULTADO:", "TODO OK" if ok else "*** HAY FALLAS")
sys.exit(0 if ok else 1)
