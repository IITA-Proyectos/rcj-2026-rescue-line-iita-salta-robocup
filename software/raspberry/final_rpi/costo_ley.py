# -*- coding: utf-8 -*-
"""
QUE CUESTA LA LEY NUEVA, en CPU.

No es una pregunta de estilo. El traspaso mide que el robot opera a 8,6-20,6 Hz
y que CAMINO+MONO "sale gratis" sólo porque apagar `poi_component` paga su
sobrecosto entero. Meter una ley que recorre el camino punto a punto y proyecta
cada uno al suelo puede costar, y hay que saber cuánto ANTES del sábado.

Se mide el paso COMPLETO -percepción + ley-, que es lo que ocupa el presupuesto
por frame, en tres configuraciones, sobre los mismos frames y alternando el
orden para que la deriva térmica no le pegue siempre a la misma.

  A  la visión de hoy, ley vieja        (VISION_LINEA=camino)
  B  la misma visión, ley Stanley       (+ LEY_STEER=stanley)
  C  sólo la ley, sobre dicts ya calculados -para separar los dos costos-

Las dos variantes miden `angulo()` **y** `velocidad()`, que es lo que `Main.py`
hace por frame. Ver el comentario de `medir()`: medir sólo `angulo()` le cobra a
la ley el costo de la curvatura, que en producción se paga igual sin ella.

ESTO NO ES EL RUNTIME DE LA PI. Esta máquina no es una Raspberry 4B. Lo que se
puede leer acá es la RAZÓN entre las variantes, no el número absoluto: para el
absoluto está `bench_runtime.py`, y hay que correrlo EN la Pi.

    python costo_ley.py
"""

import importlib.util
import os
import sys
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402

K, G = 4.4794, 0.7419       # los mismos que vision_linea usa por defecto
VIDEO = "hist.avi"
N = 1200
REPES = 3


def cargar(ley):
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
    vl._arrancar()
    return vl


def frames(v2, n):
    cap = cv2.VideoCapture(os.path.join(AQUI, VIDEO))
    out = []
    while len(out) < n:
        ok, fr = cap.read()
        if not ok:
            break
        out.append(v2.frame_pi(fr))
    cap.release()
    return out


def medir(vl, gs):
    """ms por frame de lo que Main.py hace de verdad: angulo() Y velocidad().

    Las dos, siempre, en las dos variantes. La primera version media solo
    `angulo()` y daba +7,0 % de sobrecosto, que era un artefacto: con la ley
    apagada `angulo()` no toca la curvatura, y con la ley encendida si -la
    necesita como `v`-. Pero en produccion la curvatura se paga IGUAL en los dos
    casos, porque `Main.py` llama `velocidad(speed)` en la linea siguiente y el
    factor esta cacheado por frame. Comparar una contra la otra era comparar
    dos cosas distintas y cobrarle a la ley un costo que ya estaba.
    """
    vl._tr = None
    vl._arrancar()
    t = np.empty(len(gs))
    for i, g in enumerate(gs):
        t0 = time.perf_counter()
        vl.angulo(g)
        vl.velocidad(50)
        t[i] = (time.perf_counter() - t0) * 1000.0
    return t


def main():
    vl0 = cargar(False)
    gs = frames(vl0._v2, N)
    print("")
    print("=" * 92)
    print("  COSTO DE LA LEY   -   %s, %d frames, %d repeticiones alternadas"
          % (VIDEO, len(gs), REPES))
    print("  Esta maquina NO es una Raspberry 4B: vale la RAZON, no el absoluto.")
    print("=" * 92)
    print("")

    acc = {"A ley de hoy": [], "B ley Stanley": []}
    for rep in range(REPES):
        # alternar el orden en cada repeticion: si la maquina se calienta o
        # aparece otra carga, no le pega siempre a la misma variante
        orden = [("A ley de hoy", False), ("B ley Stanley", True)]
        if rep % 2:
            orden.reverse()
        for nombre, ley in orden:
            vl = cargar(ley)
            acc[nombre].append(medir(vl, gs))

    print("  %-16s %9s %9s %9s %9s" % ("variante", "p50 ms", "p90 ms",
                                       "media", "n"))
    base = None
    for nombre in ("A ley de hoy", "B ley Stanley"):
        t = np.concatenate(acc[nombre])
        p50 = float(np.percentile(t, 50))
        print("  %-16s %9.3f %9.3f %9.3f %9d"
              % (nombre, p50, np.percentile(t, 90), t.mean(), len(t)))
        if base is None:
            base = p50
        else:
            print("")
            print("  sobrecosto de separar posicion de rumbo:  %+.3f ms  (%+.1f %%)"
                  % (p50 - base, 100.0 * (p50 - base) / base))

    # C: solo la ley, sobre dicts ya calculados
    vl = cargar(True)
    vl._tr = None
    vl._arrancar()
    dicts = []
    for g in gs:
        r = vl._tr.step(g)
        if r.get("target") is not None:
            dicts.append(r)
    t = np.empty(len(dicts) * 3)
    k = 0
    for _ in range(3):
        for r in dicts:
            t0 = time.perf_counter()
            LS.componentes(r, v_norm=1.0, k=K, g=G)
            t[k] = (time.perf_counter() - t0) * 1000.0
            k += 1
    solo = float(np.percentile(t, 50))
    print("")
    print("  C solo la ley, sobre dicts ya calculados: p50 %.4f ms  p90 %.4f ms"
          % (solo, np.percentile(t, 90)))
    largos = [len(r.get("path") or []) for r in dicts]
    print("    largo del camino que recorre: p50 %d  p90 %d  max %d puntos"
          % (np.percentile(largos, 50), np.percentile(largos, 90), max(largos)))

    print("")
    print("  DISPERSION ENTRE REPETICIONES  (delta de p50, B menos A, en ms)")
    deltas = [float(np.percentile(b, 50) - np.percentile(a, 50))
              for a, b in zip(acc["A ley de hoy"], acc["B ley Stanley"])]
    print("    %s   ->  min %+.3f   max %+.3f"
          % ("  ".join("%+.3f" % d for d in deltas), min(deltas), max(deltas)))
    print("")
    print("  COMO LEER ESTO")
    print("  La medicion directa (C) es la solida: %.1f microsegundos, o sea el"
          % (solo * 1000))
    print("  %.1f %% de un paso completo. El delta A-B de arriba es del MISMO"
          % (100.0 * solo / base))
    print("  ORDEN pero mas ruidoso -mirar la dispersion entre repeticiones-,")
    print("  asi que el numero a citar es el de C, no el de la resta.")
    print("")
    print("  Y la referencia que importa: CAMINO+MONO entero costaba +0,126 ms")
    print("  sobre el baseline, y apagar poi_component lo pago. Esto es una")
    print("  fraccion de eso. Igual, el numero que manda es el de la Pi:")
    print("  bench_runtime.py, y todavia no se corrio ahi.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
