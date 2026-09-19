# -*- coding: utf-8 -*-
"""
V1 CONTRA LA CANDIDATA - la comparacion que nunca se hizo.

Benjamin volvio sobre `airborne_v1_adaptado.py`, la PRIMERA version de nuevo
code, y dijo que le habia parecido que tenia potencial. Revisando el banco:
`ab_v2_v3_v4.py` compara V2 contra V3 contra V4. **V1 nunca entro.** Se
abandono antes de medirla con las cinco metricas, y desde entonces todo el
trabajo -H5, H6, H6b, H8, H9, H9-GATE, H10, MONO, SUELO- fue sobre el linaje
V2+.

Y hay una razon fuerte para mirarla de nuevo. La investigacion de literatura de
esta semana dio esto:

  Overengineering (campeon mundial 2024): camara baja, POI sobre el contorno
  crudo, ley lineal de columna. CERO IPM, cero esqueleto, cero grafo.
  Airborne (2025): el mismo sistema de 7 POI, con hold lateral.

V1 ES ESA ARQUITECTURA, ya adaptada a este robot. V2/V3/V4 son otra cosa:
skeletonize + grafo + Dijkstra + lookahead geodesico de 70 px, que es donde
aparecieron los defectos estructurales (lookahead no fisico con 5,9x de
variacion, mezcla de posicion y rumbo, target fuera del camino planificado).

Este banco corre V1 por EXACTAMENTE el mismo metro que la candidata: las cinco
metricas de `ab_v2_v3_v4.metricas` sobre los 10 autonomos, mas los controles
positivos obligatorios.

NO decide nada solo. Es replay open-loop: mide percepcion, no trayectoria.

    python3 ab_v1_vs_candidata.py
"""

import importlib.util
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    sp1 = importlib.util.spec_from_file_location(
        "airborne_v1", os.path.join(AQUI, "airborne_v1_adaptado.py"))
    v1 = importlib.util.module_from_spec(sp1)
    sp1.loader.exec_module(v1)
    return v4, v4.v3.v2, v1


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


def serie_candidata(SinBranch, v2, ruta, fps, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(fps)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            t = r.get("target")
            out.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                r.get("state")))
        i += 1
    cap.release()
    return out


def serie_v1(v1mod, ruta, fps, desde=0, hasta=10 ** 9):
    """V1 ya devuelve target suavizado y su propio angle_target. Se usa tal
    cual: cambiarlo seria comparar otra cosa."""
    cap = cv2.VideoCapture(ruta)
    tr = v1mod.AirborneV1(fps)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.paso(v1mod.frame_de_la_pi(fr))
        if i >= desde:
            t = r.get("target")
            a = r.get("angle_target")
            out.append((t, None if (t is None or a is None or not np.isfinite(a))
                        else float(a), r.get("estado")))
        i += 1
    cap.release()
    return out


def agregado(fn):
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, smax=0.0,
               suav=[])
    for vid in AB.AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        m = AB.metricas(fn(ruta, FPS))
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
        tot["smax"] = max(tot["smax"], m["s_max"])
        tot["suav"].append(m["suav"])
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav"])) if tot["suav"] else 0.0
    return tot


def main():
    v4, v2, v1mod = cargar()
    SinBranch = hacer_sinbranch(v4)

    print("")
    print("=" * 92)
    print("  V1 (POI sobre contorno, la arquitectura de los campeones)")
    print("  contra")
    print("  CANDIDATA SinBranch (skeleton + grafo + Dijkstra + lookahead 70px)")
    print("  Mismo metro: las cinco metricas de ab_v2_v3_v4 sobre 10 autonomos")
    print("=" * 92)

    res = {}
    for nom, fn in (
            ("CANDIDATA", lambda r, f: serie_candidata(SinBranch, v2, r, f)),
            ("V1", lambda r, f: serie_v1(v1mod, r, f))):
        res[nom] = agregado(fn)

    print("")
    print("  %-12s %9s %9s %9s %9s %11s %8s %8s"
          % ("version", "disp %", "sin_aut", "huecos", "saltos>24",
             "inversiones", "s_max", "suav"))
    for nom in ("CANDIDATA", "V1"):
        t = res[nom]
        print("  %-12s %9.2f %9d %9d %9d %11d %8.1f %8.2f"
              % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
                 t["inv"], t["smax"], t["suav"]))
    c, u = res["CANDIDATA"], res["V1"]
    print("")
    print("  %-12s %+9.2f %+9d %+9d %+9d %+11d"
          % ("V1 - CAND", u["disp"] - c["disp"], u["sin_aut"] - c["sin_aut"],
             u["huecos"] - c["huecos"], u["s_gt"] - c["s_gt"],
             u["inv"] - c["inv"]))

    print("")
    print("  CONTROLES POSITIVOS OBLIGATORIOS")
    print("  %-12s %s" % ("version", "por control: targets / esperados"))
    for nom, fn in (
            ("CANDIDATA", lambda r, f, d, h: serie_candidata(
                SinBranch, v2, r, f, d, h)),
            ("V1", lambda r, f, d, h: serie_v1(v1mod, r, f, d, h))):
        linea = []
        ok = True
        for cn, vid, fps, d, h, ex in AB.CONTROLES:
            ruta = os.path.join(AQUI, vid)
            if not os.path.exists(ruta) or not ex:
                continue
            ser = fn(ruta, fps, d, h)
            m = AB.metricas(ser)
            st = [s for _t, s, _e in ser if s is not None]
            linea.append("%s %d/%d" % (cn, m["con"], ex))
            ok &= (m["con"] >= ex)
            if cn == "lineal_positivo":
                linea.append("smax %+.0f" % (max(st) if st else 0))
        print("  %-12s %-9s %s" % (nom, "PASA" if ok else "*** FALLA",
                                   "   ".join(linea)))

    print("")
    print("  COMO LEER ESTO")
    print("    Es replay OPEN-LOOP: mide percepcion, no trayectoria. Que V1")
    print("    gane o pierda aca NO dice cual maneja mejor. Lo que si dice es")
    print("    si la complejidad de V2+ -skeleton, grafo, Dijkstra- se paga")
    print("    con alguna metrica, o si nunca se pago.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
