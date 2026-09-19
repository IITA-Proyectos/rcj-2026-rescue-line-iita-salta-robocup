# -*- coding: utf-8 -*-
"""
H10 - SELECCION RETROGRADA: la candidata puede elegir un target DETRAS del robot.

DE DONDE SALE
-------------
De una pregunta de Benjamin sobre `seguir` f1186. Yo habia afirmado que ir a la
izquierda ahi era correcto porque era una horquilla. ERA FALSO. La rotacion real
del robot, medida con correlacion de fase sobre el fondo del propio video, da
+59 GRADOS MONOTONOS A LA DERECHA entre f1140 y f1230, sin ninguna U. Para que
esos 314 px de corrimiento fueran 180 grados la camara necesitaria 183 grados de
campo. La rama izquierda que la candidata siguio 20 frames era el pedazo de
cinta YA RECORRIDO.

EL MECANISMO
------------
El esqueleto es una curva conectada y Dijkstra camina LOOKAHEAD px en CUALQUIERA
DE LOS DOS SENTIDOS. Nada en el score distingue adelante de atras: el gate
`y<=sy+3` solo descarta lo que esta por debajo del start, y `0,30*max(0,8-dy)`
muere a 8 filas. Queda `prev_heading`, que sale de la eleccion anterior: una vez
enganchado, volver cuesta ~38 puntos contra ~3 de seguir mal.

QUE MIDE
--------
Sobre el arbol de Dijkstra QUE YA CALCULO LA CANDIDATA (se espian
`graph_from_skeleton` y `dijkstra`), para cada nodo se computa el ALCANCE de su
subarbol: la fila mas lejana alcanzable pasando por el.

    delta_alcance = alcance(target elegido) - mejor alcance de la shell

DOS CORRECCIONES DE METODO PEDIDAS POR CHATGPT EN #138
------------------------------------------------------
1) "84 % en cero + cola" NO demuestra bimodalidad ni threshold natural. Puede
   ser zero-inflated con cola. Por eso este banco imprime el HISTOGRAMA COMPLETO
   y corre el analisis para TODOS los thresholds preregistrados 10/15/20/30/40.
   Si la conclusion solo aparece en un numero puntual, NO hay threshold
   defendible y H10 cae igual que H6.

2) "rachas con al menos una inversion" NO es "porcentaje de las inversiones".
   Aca se cuentan EVENTOS DE INVERSION UNICOS. Las ventanas post-racha se unen
   en un CONJUNTO, asi que ventanas superpuestas no cuentan dos veces, y se
   comparan TASAS por frame cubierto contra un placebo con la misma
   construccion. Tasas, no "al menos una".

NO TOCA LA CANDIDATA. Espias reversibles.
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
DEAD = 10.0
UMBRAL_SALTO = 24.0
VENTANA = 10          # frames despues del final de la racha
PLACEBO_OFF = 60      # el placebo mira 2 s antes del inicio de la racha
TOL_RACHA = 2         # frames de hueco tolerados dentro de una racha

AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
CONTROLES = [
    ("lineal_positivo", "lineal.avi", 800, 872),
    ("hist_exito", "hist.avi", 580, 679),
    ("hist_falla", "hist.avi", 1354, 1490),
    ("seguir_evento", "seguir.avi", 1160, 1200),
]
UMBRALES = (10, 15, 20, 30, 40)


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


CAP = {}


def espiar(v2):
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["start_i"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        CAP.clear()
        CAP["mode"] = mode
        sk, res = o_p(self, comp, mode)
        CAP["res"] = res
        return sk, res

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


def alcance_subarbol(pts, dist, prev):
    """Fila MINIMA alcanzable pasando por cada nodo. De hojas a raiz."""
    alc = np.array([p[0] for p in pts], np.int32)
    fin = np.where(np.isfinite(dist))[0]
    for i in fin[np.argsort(-dist[fin])]:
        pa = prev[i]
        if pa != -1 and alc[i] < alc[pa]:
            alc[pa] = alc[i]
    return alc


def analizar_frame(v2):
    res = CAP.get("res")
    if res is None or "dist" not in CAP:
        return None
    if CAP.get("mode", "").startswith("AHEAD"):
        return None
    pts, dist, prev = CAP["pts"], CAP["dist"], CAP["prev"]
    si = CAP["start_i"]
    sy, sx = pts[si]
    idx = {}
    for i, p in enumerate(pts):
        idx.setdefault(p, i)
    ti = idx.get((int(round(res["target"][1])), int(round(res["target"][0]))))
    if ti is None:
        return None
    lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
    fin = np.where(np.isfinite(dist))[0]
    shell = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
    fallback = False
    if not shell:
        shell = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
            :min(30, len(fin))]
        fallback = True
    if ti not in shell:
        return None
    alc = alcance_subarbol(pts, dist, prev)
    mejor = min(shell, key=lambda i: alc[i])
    return dict(delta=int(alc[ti] - alc[mejor]),
                lado_t=int(np.sign(pts[ti][1] - sx)),
                lado_b=int(np.sign(pts[mejor][1] - sx)),
                fallback=fallback)


def corrida(SinBranch, v2, ruta, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(FPS)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        g = v2.frame_pi(fr)
        r = tr.step(g)
        if i >= desde:
            a = analizar_frame(v2)
            t = r.get("target")
            out.append(dict(
                i=i, an=a, target=t, state=r.get("state"),
                steer=None if t is None else float(np.clip(
                    -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90))))
        i += 1
    cap.release()
    return out


# --------------------------------------------------------------------------
# EVENTOS  (misma definicion que ab_v2_v3_v4.metricas)
# --------------------------------------------------------------------------
def inversiones(reg):
    ult = None
    ev = []
    for k, x in enumerate(reg):
        s = x["steer"]
        if s is None:
            continue
        g = 1 if s > DEAD else (-1 if s < -DEAD else None)
        if g is None:
            continue
        if ult is not None and g != ult:
            ev.append(k)
        ult = g
    return ev


def saltos(reg):
    ult = None
    ev = []
    for k, x in enumerate(reg):
        t = x["target"]
        if t is None:
            continue
        if ult is not None and math.hypot(t[0] - ult[0],
                                          t[1] - ult[1]) > UMBRAL_SALTO:
            ev.append(k)
        ult = t
    return ev


def rachas(marcados):
    rr = sorted(marcados)
    out = []
    j = 0
    while j < len(rr):
        k = j
        while k + 1 < len(rr) and rr[k + 1] - rr[k] <= TOL_RACHA:
            k += 1
        out.append((rr[j], rr[k]))
        j = k + 1
    return out


def cobertura(rs, n, placebo=False):
    """Union de ventanas. Sin placebo: (fin, fin+VENTANA].
    Con placebo: la misma ventana pero 2 s antes del INICIO de la racha."""
    s = set()
    for ini, fin in rs:
        base = (ini - PLACEBO_OFF - VENTANA) if placebo else fin
        for m in range(base + 1, base + 1 + VENTANA):
            if 0 <= m < n:
                s.add(m)
    return s


# --------------------------------------------------------------------------
def histograma(d):
    print("")
    print("  HISTOGRAMA COMPLETO DE delta_alcance   (n = %d)" % len(d))
    print("  La pregunta no es si hay cola: es si hay un HUECO defendible.")
    print("")
    cero = int((d == 0).sum())
    print("    %-12s %7d  %6.2f %%  %s"
          % ("delta = 0", cero, 100.0 * cero / len(d), "#" * 56))
    bordes = [1, 3, 5, 8, 10, 13, 15, 18, 20, 25, 30, 35, 40, 50, 60, 100]
    filas = []
    mx = 0
    for a, b in zip(bordes, bordes[1:]):
        c = int(((d >= a) & (d < b)).sum())
        filas.append((a, b, c))
        mx = max(mx, c)
    for a, b, c in filas:
        print("    %-12s %7d  %6.2f %%  %s"
              % ("[%d,%d)" % (a, b), c, 100.0 * c / len(d),
                 "#" * int(round(56.0 * c / max(mx, 1)))))
    print("")
    print("  CUANTILES")
    linea = ""
    for q in (50, 60, 70, 75, 80, 85, 88, 90, 92, 94, 95, 96, 97, 98, 99):
        linea += "p%-3d %5.1f   " % (q, np.percentile(d, q))
        if len(linea) > 90:
            print("    " + linea)
            linea = ""
    if linea:
        print("    " + linea)
    print("    max %.0f" % d.max())
    nz = d[d > 0]
    if len(nz):
        print("")
        print("  SOLO LOS NO-CERO (n = %d, %.2f %% del total)"
              % (len(nz), 100.0 * len(nz) / len(d)))
        print("    p10 %.0f   p25 %.0f   p50 %.0f   p75 %.0f   p90 %.0f"
              % tuple(np.percentile(nz, [10, 25, 50, 75, 90])))


def tabla_umbrales(regs):
    print("")
    print("=" * 116)
    print("  H10 CONTRA INVERSIONES, PARA CADA THRESHOLD PREREGISTRADO")
    print("  Eventos de inversion UNICOS. Ventanas unidas en un conjunto (sin")
    print("  doble conteo). Se comparan TASAS por frame cubierto.")
    print("=" * 116)
    print("")
    print("  %5s %7s %7s %8s %8s %9s %9s %8s %8s %9s"
          % ("umbr", "frames", "rachas", "cobert", "inv en", "tasa post",
             "tasa plac", "RR plac", "RR base", "% de todas"))

    inv_tot = sum(len(inversiones(r)) for r in regs.values())
    frames_tot = sum(len(r) for r in regs.values())
    base = 100.0 * inv_tot / max(frames_tot, 1)

    filas = []
    for U in UMBRALES:
        n_marc = n_rach = cob = cob_p = inv_post = inv_plac = 0
        for reg in regs.values():
            n = len(reg)
            inv = set(inversiones(reg))
            marc = [k for k, x in enumerate(reg)
                    if x["an"] and x["an"]["delta"] >= U]
            n_marc += len(marc)
            rs = rachas(marc)
            n_rach += len(rs)
            cp, cq = cobertura(rs, n), cobertura(rs, n, True)
            cob += len(cp)
            cob_p += len(cq)
            inv_post += len(inv & cp)
            inv_plac += len(inv & cq)
        tasa = 100.0 * inv_post / max(cob, 1)
        tasa_p = 100.0 * inv_plac / max(cob_p, 1)
        f = dict(U=U, marc=n_marc, rach=n_rach, cob=cob, inv=inv_post,
                 tasa=tasa, tasa_p=tasa_p, rr_p=tasa / max(tasa_p, 1e-9),
                 rr_b=tasa / max(base, 1e-9),
                 pct=100.0 * inv_post / max(inv_tot, 1))
        filas.append(f)
        print("  %5d %7d %7d %8d %8d %8.2f %% %8.2f %% %7.2fx %7.2fx %8.1f %%"
              % (U, f["marc"], f["rach"], f["cob"], f["inv"], f["tasa"],
                 f["tasa_p"], f["rr_p"], f["rr_b"], f["pct"]))

    print("")
    print("  eventos de inversion UNICOS en los 10 autonomos: %d" % inv_tot)
    print("  (el A/B reporta 247 para el baseline: tiene que coincidir)")
    print("  tasa base de inversion: %.2f %% de los frames" % base)
    print("")
    rr = [f["rr_p"] for f in filas]
    pc = [f["pct"] for f in filas]
    print("  ESTABILIDAD")
    print("    RR contra placebo   de %.2fx a %.2fx sobre 10..40"
          % (min(rr), max(rr)))
    print("    %% de inversiones    de %.1f %% a %.1f %%" % (min(pc), max(pc)))
    if min(rr) > 1.5:
        print("    HAY PLATEAU: la conclusion no depende de elegir un numero.")
    else:
        print("    NO HAY PLATEAU: la conclusion depende del threshold.")
        print("    Sin threshold defendible, H10 cae igual que H6.")
    return filas, inv_tot


def main():
    ap = argparse.ArgumentParser(description="H10 diagnostico")
    ap.add_argument("--solo-controles", action="store_true",
                    dest="solo_controles")
    a = ap.parse_args()

    v4, v3, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    restaurar = espiar(v2)

    print("")
    print("=" * 116)
    print("  H10 - SELECCION RETROGRADA  (diagnostico)")
    print("=" * 116)
    print("")
    print("  CONTROLES  (los dos primeros TIENEN que dar cero)")
    print("  %-18s %7s %7s %7s %7s %7s %7s"
          % ("", "aplic", ">=10", ">=15", ">=20", ">=30", ">=40"))
    for nom, vid, d0, h0 in CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        reg = corrida(SinBranch, v2, ruta, d0, h0)
        ap_ = [x for x in reg if x["an"]]
        dd = (np.array([x["an"]["delta"] for x in ap_], float) if ap_
              else np.zeros(0))
        print("  %-18s %7d %7d %7d %7d %7d %7d"
              % (nom, len(ap_), int((dd >= 10).sum()), int((dd >= 15).sum()),
                 int((dd >= 20).sum()), int((dd >= 30).sum()),
                 int((dd >= 40).sum())))

    if a.solo_controles:
        restaurar()
        return 0

    print("")
    print("  DIEZ AUTONOMOS")
    regs = {}
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        regs[vid] = corrida(SinBranch, v2, ruta, 0, 10 ** 9)
        ap_ = [x for x in regs[vid] if x["an"]]
        dd = np.array([x["an"]["delta"] for x in ap_], float)
        print("    %-16s %5d frames, %5d aplicables, >=15 en %4d (%5.2f %%)"
              % (vid.replace(".avi", ""), len(regs[vid]), len(ap_),
                 int((dd >= 15).sum()),
                 100.0 * (dd >= 15).sum() / max(len(ap_), 1)))

    d = np.array([x["an"]["delta"] for reg in regs.values() for x in reg
                  if x["an"]], float)
    histograma(d)
    tabla_umbrales(regs)
    restaurar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
