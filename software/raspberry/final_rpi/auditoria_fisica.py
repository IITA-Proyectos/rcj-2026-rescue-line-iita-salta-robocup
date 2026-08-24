# -*- coding: utf-8 -*-
"""
AUDITORIA FISICA - la pregunta que no nos hicimos en semanas de investigacion.

Se refutaron H5, H6, H6b, H8, H9, H9-GATE y H10. Todas eran hipotesis sobre la
PERCEPCION. Cuando cae un arbol entero de hipotesis, lo que suele estar mal es
el marco, no las hojas.

Este banco mide DOS cosas que nunca medimos, y las dos son fisicas:

============================================================================
 A) FACTIBILIDAD CINEMATICA
============================================================================
Dato ya medido: velocidad angular sostenida del robot ~39 grados/s.
Nunca comparamos ese techo contra la velocidad angular que la PISTA EXIGE.

Se estima el yaw real del robot frame a frame por correlacion de fase sobre la
banda de fondo (arriba del piso), que no depende de nada de la candidata. Si en
los tramos que fallan la pista exige mas de 39 grados/s, entonces NINGUN arreglo
de vision puede salvar la curva y llevamos semanas mirando el lugar equivocado.

Limitacion honesta: la correlacion de fondo mezcla rotacion con paralaje de
traslacion. Se usa la banda mas ALTA (fondo lejano) para minimizarlo, y la
escala grados/pixel depende del campo visual, que no esta calibrado. Por eso se
reporta el resultado para VARIOS campos visuales y se calcula a partir de que
FOV cambiaria la conclusion.

============================================================================
 B) EL LOOKAHEAD NO ES UNA DISTANCIA FISICA
============================================================================
LOOKAHEAD = 70 PIXELES geodesicos sobre el esqueleto. Pero la camara mira casi
horizontal: de `birdeye.py` (validado, R2 0,982-0,999) sabemos que la distancia
en el suelo va como Z proporcional a 1/(v - v_h) con v_h ~ 9.

Entonces 70 px de esqueleto NO son una distancia constante en el suelo: si el
target queda en la fila 95 esta cerca, si queda en la fila 50 esta lejisimos.
Pure pursuit necesita el lookahead en unidades del SUELO. Con lookahead
variable, pure pursuit oscila.

Se mide la distancia relativa al suelo del target elegido, normalizada a la
fila 119 (lo mas cerca que ve el robot):

    Z_rel(v) = (119 - v_h) / (v - v_h)

Si Z_rel varia por un factor grande entre frames, el lookahead efectivo es
variable y eso es un defecto de diseno, no un bug de implementacion.

NO TOCA LA CANDIDATA.
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

FPS = 100.0 / 3.0
V_H = 9.0                 # fila del horizonte, medida en birdeye.py
TECHO_YAW = 39.0          # grados/s sostenidos, medido en el robot
FOVS = (45.0, 60.0, 75.0, 90.0)
FOV_NOMINAL = 60.0

AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
TRAMOS = [
    ("hist_falla", "hist.avi", 1354, 1490),
    ("hist_exito", "hist.avi", 580, 679),
    ("lineal_positivo", "lineal.avi", 800, 872),
    ("seguir_evento", "seguir.avi", 1160, 1210),
]


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


# --------------------------------------------------------------------------
# A) YAW REAL POR CORRELACION DE FASE
# --------------------------------------------------------------------------
def yaw_px(ruta, desde=0, hasta=10 ** 9):
    """Corrimiento horizontal del fondo, en px por frame. Signo: + = el robot
    gira a la DERECHA (el fondo se corre a la izquierda)."""
    cap = cv2.VideoCapture(ruta)
    prev = None
    out = {}
    i = 0
    han = None
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        half = fr[:, :320] if fr.shape[1] >= 640 else fr
        g = cv2.cvtColor(cv2.rotate(half, cv2.ROTATE_180), cv2.COLOR_BGR2GRAY)
        # banda ALTA: fondo lejano, minimo paralaje de traslacion
        banda = g[5:45, :].astype(np.float32)
        if han is None:
            han = (np.hanning(banda.shape[0])[:, None]
                   * np.hanning(banda.shape[1])[None, :])
        banda = (banda - banda.mean()) * han
        if prev is not None and i >= desde:
            (dx, _dy), resp = cv2.phaseCorrelate(prev, banda)
            out[i] = (-dx, resp)
        prev = banda
        i += 1
    cap.release()
    return out


VENTANA_YAW = 10          # 0,3 s: "sostenida" no es instantanea


def resumen_yaw(nombre, y, fov, ventana=VENTANA_YAW):
    """Tasa SOSTENIDA: se acumula el corrimiento y se deriva sobre una ventana.

    Frame a frame la correlacion de fase es ruido puro -da maximos de 900
    grados/s en un robot que gira a 39-, porque mezcla jitter, blur de
    movimiento y artefactos de MJPEG. Acumulada sobre ~0,3 s el ruido se
    promedia y queda la rotacion real, que es lo que se comparaba con el techo.
    """
    if not y:
        return None
    gpp = fov / 320.0
    ks = sorted(y)
    if len(ks) < ventana + 2:
        return None
    acum = np.zeros(len(ks))
    for j, k in enumerate(ks):
        d, r = y[k]
        acum[j] = acum[j - 1] if j else 0.0
        if r > 0.03:
            acum[j] += d * gpp
    v = np.abs(acum[ventana:] - acum[:-ventana]) / (ventana / FPS)
    if not len(v):
        return None
    d = dict(nombre=nombre, n=len(v), p50=float(np.percentile(v, 50)),
             p90=float(np.percentile(v, 90)), p95=float(np.percentile(v, 95)),
             p99=float(np.percentile(v, 99)), max=float(v.max()),
             sobre=100.0 * (v > TECHO_YAW).mean())
    return d


# --------------------------------------------------------------------------
# B) LOOKAHEAD EN UNIDADES DEL SUELO
# --------------------------------------------------------------------------
def z_rel(v):
    """Distancia en el suelo relativa a la fila 119 (=1,0)."""
    return (119.0 - V_H) / max(v - V_H, 1e-6)


def lookahead_suelo(SinBranch, v2, ruta, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(FPS)
    zs, filas = [], []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            t = r.get("target")
            if t is not None:
                filas.append(t[1])
                zs.append(z_rel(t[1]))
        i += 1
    cap.release()
    return np.array(zs), np.array(filas)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Auditoria fisica")
    ap.add_argument("--fov", type=float, default=FOV_NOMINAL)
    a = ap.parse_args()

    v4, v3, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)

    print("")
    print("=" * 100)
    print("  A) FACTIBILIDAD CINEMATICA")
    print("  velocidad angular que la PISTA EXIGE, contra el techo medido del")
    print("  robot: %.0f grados/s sostenidos" % TECHO_YAW)
    print("=" * 100)
    print("")
    print("  yaw estimado por correlacion de fase sobre el fondo lejano.")
    print("  APROXIMADO: mezcla rotacion con paralaje, y la escala depende del")
    print("  campo visual, que NO esta calibrado. Por eso van varios FOV.")
    print("")
    print("  TRAMOS CLAVE  (grados/s, |yaw|)")
    print("  %-18s %6s %7s %7s %7s %7s %9s"
          % ("tramo", "n", "p50", "p90", "p95", "max", "% >39/s"))
    guardo = {}
    for nom, vid, d, h in TRAMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        y = yaw_px(ruta, d, h)
        guardo[nom] = y
        s = resumen_yaw(nom, y, a.fov)
        if s:
            print("  %-18s %6d %7.1f %7.1f %7.1f %7.1f %8.1f %%"
                  % (nom, s["n"], s["p50"], s["p90"], s["p95"], s["max"],
                     s["sobre"]))

    print("")
    print("  SENSIBILIDAD AL CAMPO VISUAL  (p90 de |yaw| en grados/s)")
    print("  %-18s %s" % ("tramo", "".join("%10s" % ("FOV %.0f" % f)
                                           for f in FOVS)))
    for nom in guardo:
        fila = ""
        for f in FOVS:
            s = resumen_yaw(nom, guardo[nom], f)
            fila += "%10.1f" % (s["p90"] if s else 0)
        print("  %-18s %s" % (nom, fila))

    # a partir de que FOV el p90 de hist_falla supera el techo
    if "hist_falla" in guardo:
        lo, hi = 10.0, 200.0
        for _ in range(40):
            m = (lo + hi) / 2
            s = resumen_yaw("x", guardo["hist_falla"], m)
            if s["p90"] < TECHO_YAW:
                lo = m
            else:
                hi = m
        print("")
        print("  El p90 de hist_falla cruza los %.0f grados/s con FOV = %.0f"
              % (TECHO_YAW, (lo + hi) / 2))
        print("  Si el campo visual real es MAYOR que eso, la pista exige mas")
        print("  giro del que el robot puede dar y la vision no es la causa.")

    print("")
    print("  LOS 10 AUTONOMOS COMPLETOS  (FOV %.0f)" % a.fov)
    print("  %-18s %6s %7s %7s %7s %7s %9s"
          % ("video", "n", "p50", "p90", "p95", "max", "% >39/s"))
    tot = []
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        y = yaw_px(ruta)
        s = resumen_yaw(vid.replace(".avi", ""), y, a.fov)
        if s:
            tot.append(s)
            print("  %-18s %6d %7.1f %7.1f %7.1f %7.1f %8.1f %%"
                  % (s["nombre"], s["n"], s["p50"], s["p90"], s["p95"],
                     s["max"], s["sobre"]))

    print("")
    print("=" * 100)
    print("  B) EL LOOKAHEAD NO ES UNA DISTANCIA FISICA")
    print("  LOOKAHEAD = 70 px geodesicos. Z en el suelo va como 1/(v - %.0f)."
          % V_H)
    print("  Z_rel = 1,0 significa 'tan lejos como la fila 119'.")
    print("=" * 100)
    print("")
    print("  %-18s %6s %8s %8s %8s %8s %8s %10s"
          % ("video", "n", "p05", "p25", "p50", "p75", "p95", "p95/p05"))
    todas = []
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        zs, filas = lookahead_suelo(SinBranch, v2, ruta)
        if not len(zs):
            continue
        todas.append(zs)
        q = np.percentile(zs, [5, 25, 50, 75, 95])
        print("  %-18s %6d %8.2f %8.2f %8.2f %8.2f %8.2f %9.1fx"
              % (vid.replace(".avi", ""), len(zs), q[0], q[1], q[2], q[3],
                 q[4], q[4] / max(q[0], 1e-9)))
    z = np.concatenate(todas)
    q = np.percentile(z, [1, 5, 25, 50, 75, 95, 99])
    print("")
    print("  TOTAL  n=%d" % len(z))
    print("    p01 %.2f   p05 %.2f   p25 %.2f   p50 %.2f   p75 %.2f   "
          "p95 %.2f   p99 %.2f" % tuple(q))
    print("    max %.2f" % z.max())
    print("")
    print("    El lookahead efectivo varia %.1fx entre el p05 y el p95."
          % (q[5] / max(q[1], 1e-9)))
    print("    En pure pursuit el lookahead se elige para la velocidad y el")
    print("    radio minimo. Si varia por ese factor frame a frame, el lazo")
    print("    alterna entre sobre-corregir y cortar la curva SIN QUE HAYA")
    print("    NINGUN ERROR DE PERCEPCION.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
