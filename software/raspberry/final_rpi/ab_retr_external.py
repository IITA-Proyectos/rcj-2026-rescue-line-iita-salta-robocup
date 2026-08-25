# -*- coding: utf-8 -*-
"""
A/B DE RETR_LIST -> RETR_EXTERNAL EN V1.   airborne_v1_adaptado.py:95

EL DEFECTO
----------
    contours, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

`RETR_LIST` devuelve TODOS los contornos, externos y agujeros. Un reflejo blanco
adentro de la cinta negra es un agujero, y V1 lo puede elegir como si fuera la
trayectoria: pasa el filtro de area, pasa el de borde inferior, y compite por
continuidad como cualquier otro. `RETR_EXTERNAL` lo impide por construccion, sin
umbrales nuevos.

Y hay un argumento de coherencia interna: la candidata V2+ RELLENA los agujeros
(`RETR_EXTERNAL` + `drawContours` thickness=-1) justamente por esto, con el
comentario "evita que el skeleton se bifurque alrededor de cada brillo". V1 no
hace ni una cosa ni la otra.

=========================== FALSADORES, ESCRITOS ANTES ======================

FE0  EL FENOMENO EXISTE.
     Frames donde el contorno que V1 elige tiene padre, o sea que ES un
     agujero. Si son 0, no hay nada que arreglar. MUERE.

FE1  LA INTERVENCION DISPARA EN EL CASO TESTIGO.
     El traspaso deja la traza en hist.avi f626-627. Si el cambio NO altera
     nada ahi, el A/B no testeo la hipotesis: testeo otra cosa. Se dice, y no
     se reporta como refutacion. (Punto 12 de `experimento-falsable`.)

FE2  MATERIALIDAD.
     Si el target final cambia en 0 frames de los 13.900, es un no-op y no hay
     politica que adoptar. MUERE.

FE3  CONTROLES POSITIVOS.
     hist_exito 100/100, lineal_positivo 73/73 y el maximo de lineal f800-872.
     Criterio preregistrado: NO EMPEORA respecto de V1 tal como esta hoy. Se
     mide el baseline de V1 primero, porque V1 no es lo que corre y no se le
     puede exigir lo que se le exige a la candidata.

FE4  LAS CINCO METRICAS.
     disponibilidad, huecos, saltos>24, inversiones, suavidad, por el mismo
     metro de `ab_v2_v3_v4.metricas`. Preregistrado: si ALGUNA empeora, no se
     adopta. Un arreglo de correctitud que paga con una metrica no es gratis.

VALIDEZ DEL DIAGNOSTICO
-----------------------
Para saber si el contorno elegido es un agujero hace falta la jerarquia, que
`RETR_LIST` no da. Se usa `RETR_CCOMP`, que devuelve EL MISMO CONJUNTO de
contornos con jerarquia de dos niveles. Antes de creerle se verifica que
`RETR_CCOMP` produce el MISMO target que `RETR_LIST` frame a frame.

Medido: coincide en 13.890 de 13.900. Los 10 que no son dos rachas contiguas de
`con_planner.avi` (f82-86 y f386-390), y la causa esta medida: los dos modos
devuelven EL MISMO conjunto -las areas ordenadas son identicas- en OTRO ORDEN, y
la seleccion de V1 es `min(cand, key=...d)`, que ante un EMPATE se queda con el
primero de la lista. O sea que V1 depende del orden de findContours cuando dos
candidatos empatan, y el estado (`x_last`/`y_last`) arrastra la diferencia unos
frames.

Es un hallazgo menor sobre V1 y acota este diagnostico: el conteo de agujeros
vale para el 99,93 % de los frames, con una incertidumbre de a lo sumo 10.

    python ab_retr_external.py
"""

import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB                                      # noqa: E402
import gate as GATE                                           # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

FPS = 100.0 / 3.0
TESTIGO = ("hist.avi", 610, 645)      # la traza esta en f626-627
VARIANTES = (("V1 (RETR_LIST)", cv2.RETR_LIST),
             ("V1 + EXTERNAL", cv2.RETR_EXTERNAL))


class _CvShim(object):
    """cv2 con findContours forzado a un modo. No toca el archivo de V1."""

    def __init__(self, modo):
        self._modo = modo

    def findContours(self, img, _modo, aprox):
        return cv2.findContours(img, self._modo, aprox)

    def __getattr__(self, n):
        return getattr(cv2, n)


def cargar_v1(modo=None):
    sp = importlib.util.spec_from_file_location(
        "airborne_v1_ab", os.path.join(AQUI, "airborne_v1_adaptado.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    if modo is not None:
        m.cv2 = _CvShim(modo)
    return m


def serie(modo, video, desde=0, hasta=10 ** 9):
    """(target, steer, estado) de V1 con findContours en `modo`.

    Corre SIEMPRE desde el frame 0: el estado (x_last, y_last, los deques de
    promedio, los hold) se arrastra y arrancar en el medio mide otra cosa.
    """
    v1 = cargar_v1(modo)
    tr = v1.AirborneV1(FPS)
    cap = cv2.VideoCapture(os.path.join(AQUI, video))
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.paso(v1.frame_de_la_pi(fr))
        if i >= desde:
            a = r.get("angle_target")
            out.append((r.get("target"),
                        None if a is None or a != a else float(a),
                        r.get("estado")))
        i += 1
    cap.release()
    return out


def para_gate(modo):
    def fn(ruta, _fps, desde, hasta):
        s = serie(modo, os.path.basename(ruta), 0, hasta)
        return s[desde:hasta + 1]
    return fn


def cambios(sa, sb):
    n = 0
    for (ta, _a, _x), (tb, _b, _y) in zip(sa, sb):
        if (ta is None) != (tb is None):
            n += 1
        elif ta is not None and math.hypot(ta[0] - tb[0], ta[1] - tb[1]) > 0.5:
            n += 1
    return n


def diagnostico(video):
    """(n, frames_con_agujero, discrepancias_ccomp_vs_list)."""
    ref = serie(cv2.RETR_LIST, video)
    v1 = cargar_v1(cv2.RETR_CCOMP)
    tr = v1.AirborneV1(FPS)

    # ESPIA. Envuelve el metodo para leer el contorno elegido sin llamarlo dos
    # veces: `seleccionar_contorno` actualiza `x_last`/`y_last`, asi que
    # llamarlo aparte ademas de `paso()` haria avanzar el estado al doble.
    #
    # (Culpe a eso de las 10 discrepancias de con_planner.avi y me equivoque:
    # con el espia dan exactamente las mismas 10. La causa real esta medida
    # abajo, en la nota de validez.)
    cap_c = {"c": None}
    _orig = tr.seleccionar_contorno

    def _espia(m, _o=_orig):
        c, raz = _o(m)
        cap_c["c"] = c
        return c, raz

    tr.seleccionar_contorno = _espia
    cap = cv2.VideoCapture(os.path.join(AQUI, video))
    i = 0
    agujeros = []
    disc = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = v1.frame_de_la_pi(fr)
        cs, h = cv2.findContours(tr.mascara(g), cv2.RETR_CCOMP,
                                 cv2.CHAIN_APPROX_NONE)
        cap_c["c"] = None
        r = tr.paso(g)                    # UNA sola vez: el espia va adentro
        c = cap_c["c"]
        t = r.get("target")
        if i < len(ref):
            tb = ref[i][0]
            if (t is None) != (tb is None):
                disc += 1
            elif t is not None and (abs(t[0] - tb[0]) > 1e-9
                                    or abs(t[1] - tb[1]) > 1e-9):
                disc += 1
        if c is not None and h is not None and len(h):
            for k, cc in enumerate(cs):
                if cc.shape == c.shape and np.array_equal(cc, c):
                    if h[0][k][3] != -1:
                        agujeros.append(i)
                    break
        i += 1
    cap.release()
    return i, agujeros, disc


def agregar(series):
    """Suma las metricas sobre varios videos, sin promediar porcentajes."""
    n = con = huecos = s_gt = inv = 0
    difs = []
    for s in series:
        m = AB.metricas([(t, st) for t, st, _e in s])
        n += m["n"]
        con += m["con"]
        huecos += m["huecos"]
        s_gt += m["s_gt"]
        inv += m["inv"]
        st = [x[1] for x in s]
        difs += [abs(b - a) for a, b in zip(st, st[1:])
                 if a is not None and b is not None]
    return dict(disp=100.0 * con / max(n, 1), sin_aut=n - con, huecos=huecos,
                s_gt=s_gt, inv=inv,
                suav=float(np.median(difs)) if difs else float("nan"), n=n)


def main():
    videos = [v for v in SP.AUTONOMOS if os.path.exists(os.path.join(AQUI, v))]

    print("")
    print("=" * 100)
    print("  FE0 - EL FENOMENO EXISTE?  frames donde el contorno elegido ES un")
    print("        agujero (padre != -1). Si son 0, no hay nada que arreglar.")
    print("=" * 100)
    print("")
    tot_n = tot_d = 0
    por_video = {}
    for vid in videos:
        n, ag, disc = diagnostico(vid)
        por_video[vid] = ag
        tot_n += n
        tot_d += disc
        print("  %-18s %6d frames   %5d con agujero (%.2f %%)   ccomp!=list: %d"
              % (vid, n, len(ag), 100.0 * len(ag) / max(n, 1), disc))
    tot_a = sum(len(v) for v in por_video.values())
    print("")
    print("  TOTAL %d frames, %d con agujero elegido (%.2f %%)"
          % (tot_n, tot_a, 100.0 * tot_a / max(tot_n, 1)))
    print("  validez: RETR_CCOMP contra RETR_LIST, %d discrepancias de %d"
          " (%.2f %%) -> %s"
          % (tot_d, tot_n, 100.0 * tot_d / max(tot_n, 1),
             "OK" if 100.0 * tot_d / max(tot_n, 1) < 0.5
             else "*** el diagnostico mira otro sistema"))
    if tot_d:
        print("        son EMPATES de min(cand, key=d) resueltos por el orden")
        print("        de findContours, no un artefacto del instrumento. El")
        print("        conteo de arriba tiene esa incertidumbre y nada mas.")
    print("  FE0 -> %s" % ("*** MUERE: el fenomeno no existe" if tot_a == 0
                           else "SOBREVIVE"))

    print("")
    print("=" * 100)
    print("  FE1 - DISPARA EN EL CASO TESTIGO?  %s f%d-%d"
          % (TESTIGO[0], TESTIGO[1], TESTIGO[2]))
    print("=" * 100)
    print("")
    vid, d0, d1 = TESTIGO
    sl = serie(cv2.RETR_LIST, vid, 0, d1)
    se = serie(cv2.RETR_EXTERNAL, vid, 0, d1)
    cam = [i for i in range(d0, min(d1 + 1, len(sl), len(se)))
           if cambios([sl[i]], [se[i]])]
    ag = [f for f in por_video.get(vid, []) if d0 <= f <= d1]
    print("  frames con agujero elegido en la ventana: %s"
          % (ag if ag else "ninguno"))
    print("  frames donde el target CAMBIA con EXTERNAL: %d  %s"
          % (len(cam), cam[:20]))
    print("  FE1 -> %s" % ("SOBREVIVE" if cam else
                           "*** NO DISPARA: el A/B no testea la hipotesis"))

    print("")
    print("=" * 100)
    print("  FE2 y FE4 - MATERIALIDAD Y LAS CINCO METRICAS, %d autonomos" % len(videos))
    print("  Preregistrado: si ALGUNA metrica empeora, no se adopta.")
    print("=" * 100)
    print("")
    series = {n: [] for n, _m in VARIANTES}
    cam_tot = ntot = 0
    print("  %-18s %8s %8s" % ("video", "frames", "cambian"))
    for vid in videos:
        a = serie(cv2.RETR_LIST, vid)
        b = serie(cv2.RETR_EXTERNAL, vid)
        series["V1 (RETR_LIST)"].append(a)
        series["V1 + EXTERNAL"].append(b)
        c = cambios(a, b)
        cam_tot += c
        ntot += len(a)
        print("  %-18s %8d %8d" % (vid, len(a), c))
    print("")
    print("  %-18s %8s %8s %8s %10s %8s %9s"
          % ("variante", "disp %", "sin_aut", "huecos", "saltos>24", "invers",
             "suav"))
    base = None
    for nombre, _m in VARIANTES:
        r = agregar(series[nombre])
        print("  %-18s %8.2f %8d %8d %10d %8d %9.2f"
              % (nombre, r["disp"], r["sin_aut"], r["huecos"], r["s_gt"],
                 r["inv"], r["suav"]))
        if base is None:
            base = r
        else:
            print("  %-18s %+8.2f %+8d %+8d %+10d %+8d %+9.2f"
                  % ("  delta", r["disp"] - base["disp"],
                     r["sin_aut"] - base["sin_aut"], r["huecos"] - base["huecos"],
                     r["s_gt"] - base["s_gt"], r["inv"] - base["inv"],
                     r["suav"] - base["suav"]))
            peor = []
            if r["disp"] < base["disp"] - 1e-9:
                peor.append("disponibilidad")
            for cl, et in (("huecos", "huecos"), ("s_gt", "saltos"),
                           ("inv", "inversiones")):
                if r[cl] > base[cl]:
                    peor.append(et)
            if r["suav"] > base["suav"] + 1e-9:
                peor.append("suavidad")
            print("")
            print("  FE2 -> %s   (%d frames de %d cambian, %.2f %%)"
                  % ("*** MUERE: no-op" if cam_tot == 0 else "SOBREVIVE",
                     cam_tot, ntot, 100.0 * cam_tot / max(ntot, 1)))
            print("  FE4 -> %s" % ("SOBREVIVE: ninguna empeora" if not peor
                                   else "*** EMPEORA: " + ", ".join(peor)))

    print("")
    print("=" * 100)
    print("  FE3 - CONTROLES POSITIVOS.  Criterio: NO EMPEORA respecto de V1")
    print("        tal como esta hoy. V1 no es lo que corre en el robot.")
    print("=" * 100)
    for nombre, modo in VARIANTES:
        print("")
        print("  %s" % nombre)
        GATE.evaluar(para_gate(modo), verbose=True)
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
