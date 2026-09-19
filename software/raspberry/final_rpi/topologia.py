# -*- coding: utf-8 -*-
"""H6a CONTRA H6b: las ramas del esqueleto son reales o artefactos?

NO TOCA EL ROBOT. No implementa ninguna poda.

Las dos hipotesis
-----------------
H6a  la ramificacion representa topologia REAL de la cinta (T, cruces, la propia
     forma de la mancha) y por eso el `path_target` se vuelve inestable.
H6b  la ramificacion es sintoma de una segmentacion INESTABLE: perturbaciones
     chicas del umbral o del cierre producen ramas espurias distintas, y esas
     ramas mueven el punto geodesico.

El discriminante
----------------
La prediccion que las separa es la ESTABILIDAD TOPOLOGICA BAJO PERTURBACION.

  * Si las ramas son reales (H6a), perturbar el umbral de negro en +-5 o el
    numero de iteraciones del cierre NO deberia cambiar cuantas ramas hay. Una T
    de la pista sigue estando ahi con umbral 85 o 95.
  * Si son artefactos (H6b), la cuenta de ramas va a bailar con la perturbacion,
    y ademas va a bailar MAS en los frames donde el target salta.

Esa segunda parte es la clave: no alcanza con que la topologia sea inestable en
general. Tiene que ser MAS inestable justo en los frames del salto. Si la
inestabilidad es la misma en los frames sanos y en los que saltan, H6b no
explica el salto y H6a queda en pie.

Perturbaciones
--------------
El codigo real usa `inRange(LO, [90,90,90])` y `MORPH_CLOSE` de 4 iteraciones
(`nuevo_code_v2.py:71-83`). Se prueban umbrales 85/90/95 y cierres 2/4/6, o sea
la vecindad razonable de lo que ya corre. No se cambia nada mas.

Junctions semanticas
--------------------
Contar pixeles de grado >= 3 sueltos sobrevalora: una bifurcacion gruesa da
varios pixeles vecinos. Se los agrupa por componentes conexas con 8-vecindad
antes de contar, que es lo que pidio Benjamin.

Persistencia
------------
Una rama real dura muchos frames; una espuria aparece y desaparece. Se rastrea
cada hoja al frame siguiente por cercania y se mide cuantos frames sobrevive.

Uso
---
    python topologia.py
    python topologia.py --videos hist.avi lineal.avi
"""

import argparse
import csv
import importlib.util
import math
import os
import sys

import numpy as np
import cv2
from skimage.morphology import skeletonize

AQUI = os.path.dirname(os.path.abspath(__file__))
AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
FPS = 100.0 / 3.0
UMBRAL_SALTO = 24.0

# la vecindad de lo que ya corre: umbral 90, cierre 4 (nuevo_code_v2.py:71-83)
UMBRALES = [85, 90, 95]
CIERRES = [2, 4, 6]


def cargar():
    ruta = os.path.join(AQUI, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        ruta = os.path.join(os.path.expanduser("~"), "Downloads", "nuevo_code_v4.py")
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def mascara_perturbada(v2, g, umbral, cierre):
    """Copia de `nuevo_code_v2.mask_linea` con dos parametros abiertos."""
    m = cv2.inRange(g, v2.LO, np.array([umbral, umbral, umbral], np.uint8))
    m[:v2.FLOOR_TOP, :] = 0
    htri = int(v2.H * 0.15)
    wtri = int(v2.W * 0.25)
    cv2.fillPoly(m, [np.array([[0, v2.FLOOR_TOP], [wtri, v2.FLOOR_TOP],
                               [0, min(v2.H - 1, v2.FLOOR_TOP + htri)]], np.int32)], 0)
    cv2.fillPoly(m, [np.array([[v2.W - 1, v2.FLOOR_TOP],
                               [v2.W - 1 - wtri, v2.FLOOR_TOP],
                               [v2.W - 1, min(v2.H - 1, v2.FLOOR_TOP + htri)]],
                              np.int32)], 0)
    if cierre > 0:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8),
                             iterations=cierre)
    return m


def comp_de_abajo(v2, m):
    """La misma eleccion que hace V2 cuando hay algo cerca: la mas grande que
    toca la banda NEAR. Se replica para que la perturbacion sea comparable."""
    lab, cands = v2.cc_candidates(m)
    if not cands:
        return None
    near = [c for c in cands if c["near"]]
    pool = near if near else cands
    c = max(pool, key=lambda q: q["area"])
    comp = (lab == c["k"]).astype(np.uint8) * 255
    ext, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if ext:
        lleno = np.zeros_like(comp)
        cv2.drawContours(lleno, ext, -1, 255, thickness=-1)
        comp = lleno
    return comp


def topo(v2, comp):
    """(n_hojas, n_junctions_semanticas, hojas_xy). None si no hay esqueleto."""
    if comp is None:
        return None
    sk = skeletonize(comp > 0)
    pts, adj, deg = v2.graph_from_skeleton(sk)
    if len(pts) < 3:
        return None
    hojas = [(pts[i][1], pts[i][0]) for i in range(len(pts)) if deg[i] == 1]
    # junctions SEMANTICAS: agrupar los pixeles de grado>=3 vecinos entre si
    jm = np.zeros(sk.shape, np.uint8)
    for i in range(len(pts)):
        if deg[i] >= 3:
            jm[pts[i][0], pts[i][1]] = 1
    n_j, _lab = cv2.connectedComponents(jm, 8)
    return dict(n_hojas=len(hojas), n_junc=max(0, n_j - 1), hojas=hojas,
                n_pix_junc=int(jm.sum()))


def persistencia(hojas_ant, hojas, tol=6.0):
    """Cuantas hojas del frame anterior siguen presentes (a menos de tol px)."""
    if not hojas_ant or not hojas:
        return 0, len(hojas_ant) if hojas_ant else 0
    a = np.asarray(hojas_ant, float)
    b = np.asarray(hojas, float)
    viv = 0
    for p in a:
        if np.min(np.hypot(b[:, 0] - p[0], b[:, 1] - p[1])) <= tol:
            viv += 1
    return viv, len(hojas_ant)


def correr(v4, v2, ruta):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = v4.NuevoCodeV4(FPS)
    per = tr.per
    orig = per.path_target
    caja = {}

    def espia(comp, mode):
        sk, res = orig(comp, mode)
        caja["raw"] = None if res is None else tuple(res["target"])
        return sk, res
    per.path_target = espia

    filas = []
    raw_ant = None
    hojas_ant = None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        caja.clear()
        g = v2.frame_pi(fr)
        r = tr.step(g)
        raw = caja.get("raw")
        d = None
        if raw is not None and raw_ant is not None:
            d = math.hypot(raw[0] - raw_ant[0], raw[1] - raw_ant[1])
        raw_ant = raw

        # --- la topologia bajo cada perturbacion --------------------------
        conteos = []
        base = None
        for u in UMBRALES:
            for c in CIERRES:
                t = topo(v2, comp_de_abajo(v2, mascara_perturbada(v2, g, u, c)))
                if t is None:
                    continue
                conteos.append((u, c, t["n_hojas"], t["n_junc"], t["hojas"]))
                if u == 90 and c == 4:
                    base = t
        if not conteos or base is None:
            hojas_ant = None
            filas.append(dict(d=d, disp=None, base=None, pers=None))
            continue
        hj = np.array([x[2] for x in conteos], float)
        jn = np.array([x[3] for x in conteos], float)
        # dispersion relativa de la cuenta bajo perturbacion
        disp_h = float(hj.std() / max(hj.mean(), 1e-9))
        disp_j = float(jn.std() / max(jn.mean(), 1e-9))
        rango_h = float(hj.max() - hj.min())

        # ACUERDO DE POSICION: que fraccion de las hojas de la config base
        # reaparece en el MISMO lugar bajo las otras configuraciones. Si las
        # hojas son reales, la posicion no deberia depender del umbral.
        acuerdos = []
        for (u, c, _nh, _nj, hj_c) in conteos:
            if u == 90 and c == 4:
                continue
            v, t_ = persistencia(base["hojas"], hj_c, tol=6.0)
            if t_:
                acuerdos.append(v / float(t_))
        acuerdo = float(np.mean(acuerdos)) if acuerdos else None

        viv, tot = persistencia(hojas_ant, base["hojas"])
        pers = (viv / tot) if tot else None
        hojas_ant = base["hojas"]

        filas.append(dict(d=d, disp_h=disp_h, disp_j=disp_j, rango_h=rango_h,
                          base=base, pers=pers, n_cfg=len(conteos),
                          acuerdo=acuerdo))
    for k in range(len(filas)):
        filas[k]["pers_ant"] = filas[k - 1].get("pers") if k > 0 else None
    cap.release()
    return filas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--videos", nargs="*", default=AUTONOMOS)
    a = ap.parse_args(argv)
    v4, _v3, v2 = cargar()

    print("")
    print("=" * 86)
    print(" H6a (ramas reales) CONTRA H6b (ramas por segmentacion inestable)")
    print(" perturbaciones: umbral %s x cierre %s   (lo que corre: 90 y 4)"
          % (UMBRALES, CIERRES))
    print("=" * 86)

    todo = []
    for vid in a.videos:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  falta %s" % vid)
            continue
        f = correr(v4, v2, ruta)
        todo += f
        print("  %-16s %d frames" % (vid.replace(".avi", ""), len(f)))

    con = [f for f in todo if f.get("base") is not None and f["d"] is not None]
    salta = [f for f in con if f["d"] > UMBRAL_SALTO]
    no = [f for f in con if f["d"] <= UMBRAL_SALTO]
    print("")
    print("  %d frames utiles; %d saltan > %.0f px" % (len(con), len(salta), UMBRAL_SALTO))

    print("")
    print("  1. ESTABILIDAD TOPOLOGICA BAJO PERTURBACION")
    print("     Si las ramas son reales, la cuenta NO deberia cambiar con el")
    print("     umbral ni con el cierre.")
    print("     %-30s %10s %10s" % ("", "salta >24", "no salta"))
    for et, k in (("dispersion rel. de hojas p50", "disp_h"),
                  ("dispersion rel. de junctions p50", "disp_j"),
                  ("rango absoluto de hojas p50", "rango_h")):
        v1 = np.median([f[k] for f in salta])
        v0 = np.median([f[k] for f in no])
        print("     %-30s %10.3f %10.3f" % (et, v1, v0))
    for et, k in (("hojas p50", "n_hojas"), ("junctions semanticas p50", "n_junc"),
                  ("pixeles grado>=3 p50", "n_pix_junc")):
        v1 = np.median([f["base"][k] for f in salta])
        v0 = np.median([f["base"][k] for f in no])
        print("     %-30s %10.1f %10.1f" % (et, v1, v0))

    print("")
    print("  2. LA CUENTA DE HOJAS CAMBIA CON EL UMBRAL?")
    rr = np.array([f["rango_h"] for f in con])
    print("     rango de hojas entre las 9 configuraciones:")
    print("       p50 %.1f   p90 %.1f   MAX %.1f" % (np.median(rr), np.percentile(rr, 90), rr.max()))
    print("     frames donde la cuenta NO cambia nada: %.1f %%" % (100.0 * (rr == 0).mean()))
    print("     frames donde cambia en 3 o mas       : %.1f %%" % (100.0 * (rr >= 3).mean()))

    print("")
    print("  3. PERSISTENCIA TEMPORAL DE LAS HOJAS")
    p1 = [f["pers"] for f in salta if f["pers"] is not None]
    p0 = [f["pers"] for f in no if f["pers"] is not None]
    if p1 and p0:
        print("     fraccion de hojas que sobreviven al frame siguiente:")
        print("       en frames que SALTAN    p50 %.2f  (n=%d)" % (np.median(p1), len(p1)))
        print("       en frames que NO saltan p50 %.2f  (n=%d)" % (np.median(p0), len(p0)))

    print("")
    print("  3b. LAS COLAS, que las medianas esconden")
    for et, k in (("dispersion de hojas", "disp_h"), ("rango de hojas", "rango_h")):
        v1 = np.array([f[k] for f in salta]); v0 = np.array([f[k] for f in no])
        print("     %-22s salta p75 %.2f p90 %.2f | no p75 %.2f p90 %.2f"
              % (et, np.percentile(v1, 75), np.percentile(v1, 90),
                 np.percentile(v0, 75), np.percentile(v0, 90)))
    for et, k in (("hojas", "n_hojas"), ("junctions", "n_junc")):
        v1 = np.array([f["base"][k] for f in salta], float)
        v0 = np.array([f["base"][k] for f in no], float)
        print("     %-22s salta p75 %.1f p90 %.1f | no p75 %.1f p90 %.1f"
              % (et, np.percentile(v1, 75), np.percentile(v1, 90),
                 np.percentile(v0, 75), np.percentile(v0, 90)))

    print("")
    print("  3c. LA PERSISTENCIA, ES PREDICTIVA O SOLO DESCRIPTIVA?")
    print("     Si baja UN FRAME ANTES del salto, sirve como senal de aviso.")
    print("     Si solo baja EN el salto, describe lo que ya paso.")
    pa1 = [f["pers_ant"] for f in salta if f.get("pers_ant") is not None]
    pa0 = [f["pers_ant"] for f in no if f.get("pers_ant") is not None]
    if pa1 and pa0:
        print("       persistencia del frame ANTERIOR:")
        print("         antes de un salto    p50 %.2f  p25 %.2f  (n=%d)"
              % (np.median(pa1), np.percentile(pa1, 25), len(pa1)))
        print("         antes de un no-salto p50 %.2f  p25 %.2f  (n=%d)"
              % (np.median(pa0), np.percentile(pa0, 25), len(pa0)))
        # capacidad de aviso: con un umbral sobre la persistencia previa
        import numpy as _np
        for u in (0.5, 0.8, 0.95):
            tp = _np.mean(_np.array(pa1) < u); fp = _np.mean(_np.array(pa0) < u)
            print("         umbral pers_ant < %.2f -> avisa %.0f %% de los saltos, "
                  "falsa alarma %.0f %%" % (u, 100 * tp, 100 * fp))

    print("")
    print("  3d. EL DISCRIMINANTE BUENO: la POSICION de las hojas, no la cantidad")
    print("     Si una hoja es real, tiene que estar en el MISMO lugar con")
    print("     umbral 85 y con 95. Si es artefacto, aparece en otro lado.")
    a1 = [f["acuerdo"] for f in salta if f.get("acuerdo") is not None]
    a0 = [f["acuerdo"] for f in no if f.get("acuerdo") is not None]
    if a1 and a0:
        print("       acuerdo de posicion entre las 9 configuraciones:")
        print("         frames que SALTAN    p50 %.3f  p25 %.3f  (n=%d)"
              % (np.median(a1), np.percentile(a1, 25), len(a1)))
        print("         frames que NO saltan p50 %.3f  p25 %.3f  (n=%d)"
              % (np.median(a0), np.percentile(a0, 25), len(a0)))
        print("       fraccion de frames con acuerdo < 0,60:")
        print("         SALTAN    %.1f %%     NO saltan %.1f %%"
              % (100.0 * np.mean(np.array(a1) < 0.6),
                 100.0 * np.mean(np.array(a0) < 0.6)))

    print("")
    print("  4. VEREDICTO")
    dh1 = np.median([f["disp_h"] for f in salta])
    dh0 = np.median([f["disp_h"] for f in no])
    nh1 = np.median([f["base"]["n_hojas"] for f in salta])
    nh0 = np.median([f["base"]["n_hojas"] for f in no])
    print("     H6b predice: la topologia es MAS inestable en los frames que saltan.")
    print("       dispersion: salta %.3f contra no-salta %.3f" % (dh1, dh0))
    print("     H6a predice: hay MAS ramas reales en los frames que saltan,")
    print("       con la misma estabilidad.")
    print("       hojas: salta %.1f contra no-salta %.1f (p75: %.1f contra %.1f)"
          % (nh1, nh0, np.percentile([f["base"]["n_hojas"] for f in salta], 75),
             np.percentile([f["base"]["n_hojas"] for f in no], 75)))
    print("")
    print("     Las DOS senales suben en los frames que saltan, asi que este")
    print("     experimento por si solo NO separa H6a de H6b: mas ramas y mas")
    print("     inestabilidad van juntas, y es esperable -mas ramas dan mas")
    print("     oportunidades de que alguna baile-. El discriminante es 3d.")

    out = os.path.join(AQUI, "topologia.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["salto_raw_px", "disp_hojas", "disp_junc", "rango_hojas",
                     "n_hojas", "n_junc", "n_pix_junc", "persistencia",
                     "acuerdo_posicion"])
        for f in con:
            wr.writerow(["%.2f" % f["d"], "%.4f" % f["disp_h"], "%.4f" % f["disp_j"],
                         "%.0f" % f["rango_h"], f["base"]["n_hojas"],
                         f["base"]["n_junc"], f["base"]["n_pix_junc"],
                         "" if f["pers"] is None else "%.3f" % f["pers"],
                         "" if f.get("acuerdo") is None else "%.3f" % f["acuerdo"]])
    print("")
    print("  CSV: %s" % os.path.basename(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
