# -*- coding: utf-8 -*-
"""
CURVA CERRADA - ver la curva ANTES de estar adentro.

EL OBJETIVO, dicho por Benjamin: el robot se sale en las curvas cerradas y eso
tiene que dejar de pasar.

============================================================================
 POR QUE ESTO Y NO OTRA COSA
============================================================================
De la literatura sale una desigualdad que no se negocia:

    v_max = omega_max * R

Con la velocidad angular que da el robot, una curva de radio R solo se puede
tomar por debajo de cierta velocidad. Frenar en curva ES el arreglo.

Y la Teensy YA FRENA. En `main.cpp`, dentro del case de linea:

    double k = constrain(absSteer / LINE_PIVOT_STEER, 0.0, 1.0);
    int vel = velocidadAjustada + k*k*(LINE_PIVOT_SPEED - velocidadAjustada);

40 en recta, 42 a mitad de curva, 50 en pivote. El propio comentario dice que lo
midieron en pista: "en la zona intermedia la corrida MAS LENTA rindio mejor".

ENTONCES EL PROBLEMA NO ES QUE NO FRENE: ES QUE FRENA TARDE. `absSteer` sube
cuando la curva ya esta encima, porque el steer sale del target y el target esta
a un lookahead fijo. Lo que falta es ANTICIPACION.

============================================================================
 QUE MIDE ESTE MODULO
============================================================================
Del camino principal del esqueleto -la cadena start -> nodo mas lejano, la misma
que usa CAMINO- se proyecta cada punto al suelo y se mide:

    giro_visible   cuanto dobla el camino visible, en grados
    arco           cuanto mide ese camino en el suelo
    kappa          giro / arco = curvatura
    v_seguro       omega_max / kappa, la velocidad que la curva admite

Y despues se mide LO UNICO QUE IMPORTA: cuantos frames ANTES que `absSteer`
avisa esto.

Si la anticipacion es de 0 frames, no sirve y hay que decirlo.

============================================================================
 COMO LLEGA A LA TEENSY
============================================================================
El protocolo ya tiene el byte: [255, speed, 254, angle, 253, green, 252, silver].
La auditoria de firmware encontro que la Teensy lo RECIBE, lo VALIDA y NO LO USA
en linea: usa `ajustarVelocidadPorPendiente(45)` hardcodeado.

O sea que el canal existe y esta ignorado. Del lado Teensy el cambio es una
linea: usar el `speed` recibido como `velocidadAjustada` en vez del 45 fijo.

NO TOCA LA CANDIDATA. Espia reversible.

    python3 curva_cerrada.py
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

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
V_H = 9.0
HFOV = 60.0
OMEGA_MAX = 39.0         # grados/s sostenidos, medido en el robot
CAP = {}


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3.v2


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, f):
            v4.NuevoCodeV4.__init__(self, f)
            self.branch_guard = _N()
    return SinBranch


def instalar(v2):
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["si"] = r[0], r[1], start
        return r

    v2.graph_from_skeleton, v2.dijkstra = g, d

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
    return restaurar


def geometria(v2):
    f_px = (v2.W / 2.0) / math.tan(math.radians(HFOV / 2.0))

    def suelo(u, v):
        z = (119.0 - V_H) / max(v - V_H, 1e-6)
        return ((u - v2.CENTER) * z / f_px, z)
    return suelo


def curvatura(v2, suelo):
    """Del camino principal: giro visible, arco y curvatura. En unidades de
    Z(fila 119). Devuelve None si no hay camino usable."""
    if "dist" not in CAP:
        return None
    pts, dist, prev, si = CAP["pts"], CAP["dist"], CAP["prev"], CAP["si"]
    fin = np.where(np.isfinite(dist))[0]
    if len(fin) < 8:
        return None
    F = int(fin[int(np.argmax(dist[fin]))])
    cad = v2.reconstruct(prev, si, F)
    if not cad or len(cad) < 8:
        return None
    P = [suelo(pts[i][1], pts[i][0]) for i in cad]
    # remuestreo cada ~6 nodos para que el ruido pixel a pixel no domine
    Q = P[::6] if len(P) >= 18 else P
    if len(Q) < 3:
        return None
    giro = 0.0
    arco = 0.0
    hs = []
    for a, b in zip(Q, Q[1:]):
        dx, dz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dz)
        if L < 1e-9:
            continue
        arco += L
        hs.append(math.degrees(math.atan2(dx, dz)))
    if len(hs) < 2 or arco < 1e-9:
        return None
    for a, b in zip(hs, hs[1:]):
        giro += abs((b - a + 180) % 360 - 180)
    kappa = giro / arco
    return dict(giro=giro, arco=arco, kappa=kappa,
                v_seguro=(OMEGA_MAX / kappa) if kappa > 1e-9 else 1e9)


def main():
    ap = argparse.ArgumentParser(description="Anticipacion de curva cerrada")
    ap.add_argument("--umbral-steer", type=float, default=45.0,
                    dest="u_steer")
    ap.parse_args()
    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    suelo = geometria(v2)
    rest = instalar(v2)

    print("")
    print("=" * 96)
    print("  ANTICIPACION DE CURVA CERRADA")
    print("  La Teensy ya frena con absSteer. La pregunta es si la curvatura del")
    print("  camino visible avisa ANTES, y cuantos frames antes.")
    print("=" * 96)

    KA = []
    todos = []
    for vid in AB.AUTONOMOS:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru):
            continue
        cap = cv2.VideoCapture(ru)
        tr = SinBranch(FPS)
        serie = []
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            CAP.clear()
            r = tr.step(v2.frame_pi(fr))
            t = r.get("target")
            s = None if t is None else abs(float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)))
            c = curvatura(v2, suelo)
            serie.append((s, c["kappa"] if c else None,
                          c["v_seguro"] if c else None))
            if c:
                KA.append(c["kappa"])
        cap.release()
        todos.append((vid, serie))
    rest()

    KA = np.array(KA)
    print("")
    print("  CURVATURA DEL CAMINO VISIBLE  (grados por unidad de suelo)")
    print("    n %d   p50 %.1f   p75 %.1f   p90 %.1f   p95 %.1f   max %.1f"
          % (len(KA), *np.percentile(KA, [50, 75, 90, 95]), KA.max()))
    print("")
    print("  BARRIDO DE UMBRAL, con deteccion por VENTANA y no por racha")
    print("  (exigir frames consecutivos era un artefacto mio: un solo bache")
    print("   cortaba la racha y perdia el aviso)")
    print("")
    print("  %-10s %9s %9s %10s %10s %10s"
          % ("percentil", "umbral", "eventos", "avisados", "cobertura", "lead p50"))
    for pc in (50, 60, 70, 75, 80, 85, 90):
        U = float(np.percentile(KA, pc))
        ev_tot = av_tot = 0
        leads = []
        for vid, serie in todos:
            st = [x[0] for x in serie]
            ka = [x[1] for x in serie]
            ev = [i for i in range(1, len(st))
                  if st[i] is not None and st[i - 1] is not None
                  and st[i] > 45.0 >= st[i - 1]]
            ev_tot += len(ev)
            for e in ev:
                # el aviso mas TEMPRANO dentro de una ventana de 40 frames
                mejor = 0
                for k in range(1, 41):
                    j = e - k
                    if j < 0:
                        break
                    if ka[j] is not None and ka[j] > U:
                        mejor = k
                if mejor > 0:
                    av_tot += 1
                    leads.append(mejor)
        L = np.array(leads) if leads else np.zeros(0)
        print("  p%-9d %9.1f %9d %10d %9.0f %% %10s"
              % (pc, U, ev_tot, av_tot, 100.0 * av_tot / max(ev_tot, 1),
                 "%.0f f = %.0f ms" % (np.percentile(L, 50),
                                       1000 * np.percentile(L, 50) / FPS)
                 if len(L) else "-"))

    print("")
    print("  LECTURA")
    print("    Si la ventaja mediana es de pocos frames, esto NO sirve y hay que")
    print("    decirlo: la Teensy ya reacciona con absSteer y no ganamos nada.")
    print("    Si son decenas de ms, alcanza para llegar a la curva ya frenado,")
    print("    que es lo que pide v_max = omega_max * R.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
