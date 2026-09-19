# -*- coding: utf-8 -*-
"""
V1 MEJORADO - el punto debil de V1 es la RAMA SIN_CERCA (y la fila cruda).

DE DONDE SALE
-------------
V1 (`airborne_v1_adaptado.py`, POI sobre contorno crudo, la arquitectura de los
campeones) le gana al baseline en 4 de 5 metricas:

    version     disp %   sin_aut   huecos  saltos>24  inversiones   s_max   suav
    BASELINE     93.78       864      276        247          392   163.8   1.91
    V1           95.61       610       72        928          345    86.1   1.63

La unica que pierde -y pierde feo, 3,8x- es saltos>24 px. La atribucion por
rama de POI dio esto:

    sin_cerca_bottom_visible    371 saltos de 2569 frames en la rama = 14,4 %
    top_continuacion            188 de 4752 =  4,0 %
    sale_izquierda              104 de 1705 =  6,1 %
    top_crop                     70 de 1114 =  6,3 %
    sale_derecha                 63 de  920 =  6,8 %

y 260 de los 371 de sin_cerca son de esa rama A SI MISMA.

LO QUE HAY EN EL CODIGO
-----------------------
`airborne_v1_adaptado.py:162`

    if estado=='SIN_CERCA': return bottom,'sin_cerca_bottom_visible'

devuelve `bottom` CRUDO: el punto mas bajo del contorno elegido. Y en
`paso()` (linea 216-219):

    tx=self.avg_target.agregar(raw[0])      # la X se promedia 0,15 s
    ...
    target=(tx, raw[1])                     # la Y sale SIN SUAVIZAR

La X pasa por una media movil de 5 frames; la Y es el maximo de fila del
contorno de ESE frame. Cuando el contorno cambia de forma -o cuando se elige
otro contorno- la fila del bottom pega un salto entero, y la metrica de salto
es `hypot(dx, dy)`: cuenta fila y columna por igual.

PERO EL STEER SOLO USA LA COLUMNA:

    ang = -90 * (tx - CENTER) / (W/2)       # airborne_v1_adaptado.py:217

Asi que un salto de pura FILA no mueve ni un grado el comando. Si la mayor
parte de los 887 saltos consecutivos son de fila, el "punto debil de V1" es en
buena parte un ARTEFACTO DE LA METRICA y no un defecto de control.

Este banco no lo asume: lo MIDE, descomponiendo cada salto en |dx| y |dy|.

QUE SE PRUEBA (preregistrado antes de correr)
---------------------------------------------
  YSUAV(w)   la Y del target pasa por la misma media movil que la X, con
             ventana w. BANDA: w = 0,09 / 0,15 / 0,24 / 0,30 s. La ventana
             "natural" -la misma que la X, TARGET_AVG_S = 0,15 s- se declara de
             antemano como la que entra en las combinaciones.

             FALSADOR: la Y no entra en el steer. Si YSUAV cambia disp,
             sin_aut, huecos, inversiones o suavidad aunque sea en 1 unidad,
             hay un BUG en mi implementacion y el resultado no vale.

  SCHIST(h)  histeresis para ENTRAR en SIN_CERCA: hace falta que la banda
             cercana (filas 110-119) falle h frames seguidos. h = 1 es el
             comportamiento actual exacto. BANDA: h = 1 / 2 / 3 / 4 / 5
             frames, y se mira si hay MESETA en vez de quedarse con el mejor
             punto de la banda.
             Esto SI cambia la columna: durante la gracia el target sale por la
             logica de top/crop en vez de por el bottom.
             Tras una PERDIDA no hay gracia (no hay linea estable previa que
             sostener), se declara SIN_CERCA en el primer frame.

  COMBO      YSUAV(0,15) x cada h > 1 de la banda.

  SIN_SC     caso LIMITE, extension declarada: la rama SIN_CERCA no se usa
             nunca. Es el falsador del arreglo. Si el limite es lo mejor de
             todo, la conclusion NO es "hay que agregar histeresis" sino
             "la rama SIN_CERCA de V1 esta de mas", que es otra cosa.
             Ojo: con h finito, despues de una PERDIDA no hay gracia, asi que
             "SCHIST inf" todavia entra en SIN_CERCA en el primer frame sin
             banda cercana posterior a una perdida. SIN_SC no.

METRICA NUEVA QUE SE REPORTA
----------------------------
  saltos>24    los de siempre, `hypot(dx,dy)` A TRAVES de los huecos (los 928).
  salt_col>24  saltos CONSECUTIVOS con |dx| > 24 px. Son los unicos que pueden
               mover el steer. Es la metrica honesta para este defecto.

FIDELIDAD
---------
`V1Mejorado` hereda de `AirborneV1` y reimplementa solo `confianza` y `paso`.
Con TODO apagado tiene que reproducir frame a frame el target (x e y exactos),
el estado y el motivo del V1 original, que se corre en paralelo sobre los
mismos frames. Una sola discrepancia y aborta.

Replay OPEN-LOOP: mide percepcion, no trayectoria.

    python wf_v1_mejorado.py
    python wf_v1_mejorado.py --sin-baseline     (no corre la candidata)
"""

import argparse
import importlib.util
import math
import os
import sys
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
UMBRAL = 24.0

# --- banda preregistrada -------------------------------------------------
BANDA_YSUAV = [0.09, 0.15, 0.24, 0.30]
BANDA_SCHIST = [1, 2, 3, 4, 5]
# La banda de arriba bajo MONOTONAMENTE (no hubo meseta). Extension DECLARADA
# como post-hoc, hasta el caso limite h = infinito = la rama SIN_CERCA nunca se
# usa. Si el limite tambien mejora, el hallazgo no es "falta histeresis" sino
# "la rama SIN_CERCA es la que rompe", que es una conclusion distinta.
EXT_SCHIST = [8, 12, 10 ** 9]
YSUAV_NATURAL = 0.15          # la misma ventana que la X (TARGET_AVG_S)

CHK = {"n": 0, "mal": 0, "ej": []}


def cargar():
    sp1 = importlib.util.spec_from_file_location(
        "airborne_v1", os.path.join(AQUI, "airborne_v1_adaptado.py"))
    v1 = importlib.util.module_from_spec(sp1)
    sp1.loader.exec_module(v1)
    return v1


def cargar_candidata():
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
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


# =========================================================================
#  LA VARIANTE
# =========================================================================
def hacer_v1mejorado(v1):

    class V1Mejorado(v1.AirborneV1):
        """Espia reversible sobre V1. cfg = dict(ysuav=None|segundos,
        schist=1|2|3). Con cfg neutra reproduce V1 exactamente."""

        def __init__(self, fps, cfg):
            v1.AirborneV1.__init__(self, fps)
            self.cfg = cfg
            self.racha_sin_cerca = 0
            self.avg_y = v1.Promedio(
                (cfg.get("ysuav") or 0.15) * fps) if cfg.get("ysuav") else None

        # --- histeresis de SIN_CERCA (h=1 -> identico al original) --------
        def confianza(self, c):
            h = self.cfg.get("schist", 1)
            nunca = self.cfg.get("nunca_sc", False)
            if c is None:
                # tras una perdida no se regala gracia: la linea no esta cerca
                self.racha_sin_cerca = max(self.racha_sin_cerca, h)
                return 'PERDIDA'
            mm = np.zeros((v1.H, v1.W), np.uint8)
            cv2.drawContours(mm, [c], -1, 255, -1)

            def band(ab):
                a, b = ab
                return int((mm[a:b + 1] > 0).sum()) >= v1.PIX_MIN_BAND
            near, mid, far = band(v1.NEAR), band(v1.MID), band(v1.FAR)
            if not near:
                self.racha_sin_cerca += 1
                if self.racha_sin_cerca >= h and not nunca:
                    return 'SIN_CERCA'
            else:
                self.racha_sin_cerca = 0
            if mid and far:
                return 'HIGH'
            if mid:
                return 'MEDIUM'
            return 'LOW'

        # --- paso: copia literal de AirborneV1.paso + la Y opcional -------
        def paso(self, g):
            self.frame_local += 1
            m = self.mascara(g)
            c, ms = self.seleccionar_contorno(m)
            if c is None:
                self.confianza(None)          # mantiene la racha coherente
                return dict(mask=m, contour=None, estado='PERDIDA', target=None,
                            top=None, bottom=None, left=None, right=None,
                            angle_target=float('nan'), motivo_sel=ms,
                            motivo_target='perdida_sin_target')
            estado = self.confianza(c)
            full, crop = self.puntos_interes(c)
            raw, mt = self.interpretar(full, crop, estado)
            if raw is None:
                return dict(mask=m, contour=c, estado=estado, target=None,
                            top=full['top'], bottom=full['bottom'],
                            left=full['left'], right=full['right'],
                            angle_target=float('nan'), motivo_sel=ms,
                            motivo_target=mt)
            tx = self.avg_target.agregar(raw[0])
            bx = self.avg_bottom.agregar(full['bottom'][0])
            ty = raw[1] if self.avg_y is None else self.avg_y.agregar(raw[1])
            ang = float(np.clip(-90.0 * (tx - v1.CENTER) / (v1.W / 2.0),
                                -90, 90))
            return dict(mask=m, contour=c, estado=estado, target=(tx, ty),
                        top=full['top'],
                        bottom=(bx if bx is not None else full['bottom'][0],
                                full['bottom'][1]),
                        left=full['left'], right=full['right'],
                        angle_target=ang, motivo_sel=ms, motivo_target=mt)

    return V1Mejorado


# =========================================================================
#  CORRIDAS
# =========================================================================
def decodificar(ruta, v1):
    """Un solo decode por video; todas las variantes ven los MISMOS frames."""
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(v1.frame_de_la_pi(f))
    cap.release()
    return fr


def salida(r):
    t = r.get("target")
    a = r.get("angle_target")
    s = None if (t is None or a is None or not np.isfinite(a)) else float(a)
    return (t, s, r.get("estado"), r.get("motivo_target"))


def correr_v1(V1Mejorado, v1, frames, fps, cfg, desde=0, hasta=10 ** 9,
              chequear=False):
    tr = V1Mejorado(fps, cfg)
    ref = v1.AirborneV1(fps) if chequear else None
    out = []
    for i, g in enumerate(frames):
        if i > hasta:
            break
        r = tr.paso(g)
        if ref is not None:
            q = ref.paso(g)
            CHK["n"] += 1
            a, b = salida(r), salida(q)
            igual = (a[2] == b[2] and a[3] == b[3]
                     and (a[0] is None) == (b[0] is None)
                     and (a[0] is None
                          or (abs(a[0][0] - b[0][0]) < 1e-9
                              and abs(a[0][1] - b[0][1]) < 1e-9)))
            if not igual:
                CHK["mal"] += 1
                if len(CHK["ej"]) < 3:
                    CHK["ej"].append((i, a, b))
        if i >= desde:
            out.append(salida(r))
    return out


def correr_cand(SinBranch, v2, frames, fps, desde=0, hasta=10 ** 9):
    tr = SinBranch(fps)
    out = []
    for i, g in enumerate(frames):
        if i > hasta:
            break
        r = tr.step(g)
        if i >= desde:
            t = r.get("target")
            out.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                r.get("state"), r.get("state")))
    return out


# =========================================================================
#  DESCOMPOSICION DE LOS SALTOS
# =========================================================================
def acumular_saltos(recs, ac):
    """Saltos CONSECUTIVOS (los dos frames con target). Se descompone en
    columna (la que mueve el steer) y fila (la que no)."""
    prev = None
    prevs = None
    for t, s, e, mt in recs:
        ac["ramas"].setdefault(mt, [0, 0, 0])[0] += 1
        if t is not None and prev is not None:
            dx = abs(t[0] - prev[0])
            dy = abs(t[1] - prev[1])
            d = math.hypot(dx, dy)
            if s is not None and prevs is not None:
                ac["ds_todos"].append(abs(s - prevs))
            if d > UMBRAL:
                ac["tot"] += 1
                ac["ramas"][mt][1] += 1
                if dx > UMBRAL:
                    ac["col"] += 1
                else:
                    ac["fila"] += 1
                    ac["ramas"][mt][2] += 1
                if s is not None and prevs is not None:
                    ac["ds_salto"].append(abs(s - prevs))
        if t is None:
            prev = None
            prevs = None
        else:
            prev = t
            prevs = s
    return ac


def ac_nuevo():
    return dict(tot=0, col=0, fila=0, ramas={}, ds_salto=[], ds_todos=[])


def pct(a, b):
    return 100.0 * a / max(b, 1)


# =========================================================================
def main():
    ap = argparse.ArgumentParser(description="V1 mejorado: rama SIN_CERCA")
    ap.add_argument("--sin-baseline", action="store_true",
                    help="no corre la candidata (baseline) en este pase")
    a = ap.parse_args()

    v1 = cargar()
    V1Mejorado = hacer_v1mejorado(v1)

    VAR = [("BASE (V1)", dict())]
    for w in BANDA_YSUAV:
        VAR.append(("YSUAV %.2f s" % w, dict(ysuav=w)))
    for h in BANDA_SCHIST + EXT_SCHIST:
        if h == 1:
            continue
        et = "SCHIST inf" if h > 100 else "SCHIST %d" % h
        if h in EXT_SCHIST:
            et += " (ext)"
        VAR.append((et, dict(schist=h)))
    for h in BANDA_SCHIST + EXT_SCHIST:
        if h == 1:
            continue
        et = ("YSUAV.15+SCinf" if h > 100 else "YSUAV.15+SC%d" % h)
        if h in EXT_SCHIST:
            et += " (ext)"
        VAR.append((et, dict(ysuav=YSUAV_NATURAL, schist=h)))
    # caso LIMITE de verdad: la rama SIN_CERCA no se usa nunca, ni siquiera
    # despues de una perdida. Es el falsador del arreglo: si esto es lo mejor,
    # el problema no es la histeresis sino la rama entera.
    VAR.append(("SIN_SC limite (ext)", dict(nunca_sc=True)))
    VAR.append(("YSUAV.15+SIN_SC(ext)", dict(ysuav=YSUAV_NATURAL,
                                             nunca_sc=True)))

    print("")
    print("=" * 112)
    print("  V1 MEJORADO - la rama SIN_CERCA devuelve el bottom crudo y la Y")
    print("  del target NUNCA se suaviza (airborne_v1_adaptado.py:162 y 216).")
    print("  Se mide cuanto de los 887 saltos es FILA (no mueve el steer) y se")
    print("  prueban dos arreglos con banda preregistrada.")
    print("=" * 112)

    videos = [v for v in AB.AUTONOMOS
              if os.path.exists(os.path.join(AQUI, v))]
    ctls = [c for c in AB.CONTROLES
            if c[5] and os.path.exists(os.path.join(AQUI, c[1]))]

    # acumuladores
    tot = {n: dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, smax=0.0,
                   suav=[]) for n, _ in VAR}
    acs = {n: ac_nuevo() for n, _ in VAR}
    ctlres = {n: [] for n, _ in VAR}
    ctlok = {n: True for n, _ in VAR}
    cand = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, smax=0.0,
                suav=[])
    cand_ac = ac_nuevo()
    cand_ctl = []
    cand_ok = True

    if not a.sin_baseline:
        v4, v2 = cargar_candidata()
        SinBranch = hacer_sinbranch(v4)

    # que videos hay que decodificar
    necesarios = list(videos)
    for c in ctls:
        if c[1] not in necesarios:
            necesarios.append(c[1])

    t0 = time.time()
    for vid in necesarios:
        print("  decodificando %-18s" % vid, end="")
        sys.stdout.flush()
        frames = decodificar(os.path.join(AQUI, vid), v1)
        print(" %5d frames   corriendo variantes..." % len(frames), end="")
        sys.stdout.flush()
        es_auto = vid in videos
        for nom, cfg in VAR:
            if es_auto:
                recs = correr_v1(V1Mejorado, v1, frames, FPS, cfg,
                                 chequear=(nom == "BASE (V1)"))
                m = AB.metricas([(t, s, e) for t, s, e, _ in recs])
                for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
                    tot[nom][k] += m[k]
                tot[nom]["smax"] = max(tot[nom]["smax"], m["s_max"])
                tot[nom]["suav"].append(m["suav"])
                acumular_saltos(recs, acs[nom])
            for cn, cvid, cfps, d0, h0, ex in ctls:
                if cvid != vid:
                    continue
                rc = correr_v1(V1Mejorado, v1, frames, cfps, cfg, d0, h0)
                mc = AB.metricas([(t, s, e) for t, s, e, _ in rc])
                st = [s for _t, s, _e, _m in rc if s is not None]
                txt = "%s %d/%d" % (cn.split("_")[0], mc["con"], ex)
                if cn == "lineal_positivo":
                    txt += " smax %+.0f" % (max(st) if st else 0)
                ctlres[nom].append(txt)
                ctlok[nom] &= (mc["con"] >= ex)
        if not a.sin_baseline:
            if es_auto:
                recs = correr_cand(SinBranch, v2, frames, FPS)
                m = AB.metricas([(t, s, e) for t, s, e, _ in recs])
                for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
                    cand[k] += m[k]
                cand["smax"] = max(cand["smax"], m["s_max"])
                cand["suav"].append(m["suav"])
                acumular_saltos(recs, cand_ac)
            for cn, cvid, cfps, d0, h0, ex in ctls:
                if cvid != vid:
                    continue
                rc = correr_cand(SinBranch, v2, frames, cfps, d0, h0)
                mc = AB.metricas([(t, s, e) for t, s, e, _ in rc])
                st = [s for _t, s, _e, _m in rc if s is not None]
                txt = "%s %d/%d" % (cn.split("_")[0], mc["con"], ex)
                if cn == "lineal_positivo":
                    txt += " smax %+.0f" % (max(st) if st else 0)
                cand_ctl.append(txt)
                cand_ok &= (mc["con"] >= ex)
        del frames
        print(" %6.1f s" % (time.time() - t0))

    # --- fidelidad --------------------------------------------------------
    print("")
    print("  FIDELIDAD (BASE contra airborne_v1_adaptado.AirborneV1 original)")
    print("    %d frames comparados, %d discrepancias  %s"
          % (CHK["n"], CHK["mal"], "OK" if CHK["mal"] == 0 else "*** ABORTA"))
    if CHK["mal"]:
        for e in CHK["ej"]:
            print("      frame %d  mio %s  original %s" % e)
        return 3

    for n, _ in VAR:
        tot[n]["disp"] = pct(tot[n]["con"], tot[n]["n"])
        tot[n]["suav"] = float(np.mean(tot[n]["suav"]))
    if not a.sin_baseline:
        cand["disp"] = pct(cand["con"], cand["n"])
        cand["suav"] = float(np.mean(cand["suav"]))

    # --- diagnostico ------------------------------------------------------
    ac = acs["BASE (V1)"]
    print("")
    print("  " + "-" * 108)
    print("  DIAGNOSTICO: de que estan hechos los saltos de V1")
    print("  " + "-" * 108)
    print("    saltos CONSECUTIVOS > 24 px .................. %5d" % ac["tot"])
    print("      con |dx| > 24 px  (pueden mover el steer) ... %5d  (%.1f %%)"
          % (ac["col"], pct(ac["col"], ac["tot"])))
    print("      solo FILA |dx| <= 24 px (no mueven nada) .... %5d  (%.1f %%)"
          % (ac["fila"], pct(ac["fila"], ac["tot"])))
    ds = np.asarray(ac["ds_salto"]) if ac["ds_salto"] else np.array([0.0])
    dt = np.asarray(ac["ds_todos"]) if ac["ds_todos"] else np.array([0.0])
    print("    |dsteer| en los frames de salto:  p50 %5.2f  p90 %6.2f  max %6.2f"
          % (np.median(ds), np.percentile(ds, 90), ds.max()))
    print("    |dsteer| en todos los frames:     p50 %5.2f  p90 %6.2f  max %6.2f"
          % (np.median(dt), np.percentile(dt, 90), dt.max()))
    print("    (steer = -90*(x-CENTER)/80, o sea |dsteer| = 1,125*|dx|:")
    print("     salt_col>24 es EXACTAMENTE la cuenta de frames con |dsteer| > 27)")
    if not a.sin_baseline:
        print("")
        print("    la CANDIDATA sobre el mismo material, saltos CONSECUTIVOS:")
        print("      > 24 px %d   de columna %d   solo fila %d"
              % (cand_ac["tot"], cand_ac["col"], cand_ac["fila"]))
        print("      (su guard espacial 24/30 px recorta el salto consecutivo y")
        print("       abre un hueco en su lugar: por eso sus 247 saltos>24 estan")
        print("       casi todos A TRAVES de huecos, no entre frames seguidos)")
        dsc = (np.asarray(cand_ac["ds_todos"]) if cand_ac["ds_todos"]
               else np.array([0.0]))
        print("      |dsteer| candidata, todos los frames:  p50 %5.2f  p90 %6.2f"
              "  max %6.2f" % (np.median(dsc), np.percentile(dsc, 90),
                               dsc.max()))
    print("")
    print("    %-28s %8s %8s %8s %10s" % ("rama de POI", "frames", "saltos",
                                          "solo fila", "tasa %"))
    for mt, (nf, ns, nfila) in sorted(ac["ramas"].items(),
                                      key=lambda kv: -kv[1][1]):
        if ns == 0 and nf < 200:
            continue
        print("    %-28s %8d %8d %8d %9.1f" % (mt, nf, ns, nfila, pct(ns, nf)))

    # --- tabla ------------------------------------------------------------
    cab = ("  %-20s %8s %8s %7s %10s %11s %11s %7s %6s   %s"
           % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
              "salt_col>24", "inversiones", "s_max", "suav", "controles"))
    print("")
    print("  " + "-" * 108)
    print("  ABSOLUTOS")
    print("  " + "-" * 108)
    print(cab)
    if not a.sin_baseline:
        print("  %-20s %8.2f %8d %7d %10d %11d %11d %7.1f %6.2f   %s %s"
              % ("BASELINE (cand.)", cand["disp"], cand["sin_aut"],
                 cand["huecos"], cand["s_gt"], cand_ac["col"], cand["inv"],
                 cand["smax"], cand["suav"], "  ".join(cand_ctl),
                 "OK" if cand_ok else "*** FALLA"))
    for nom, _ in VAR:
        t = tot[nom]
        print("  %-20s %8.2f %8d %7d %10d %11d %11d %7.1f %6.2f   %s %s"
              % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
                 acs[nom]["col"], t["inv"], t["smax"], t["suav"],
                 "  ".join(ctlres[nom]), "OK" if ctlok[nom] else "*** FALLA"))

    b = tot["BASE (V1)"]
    ab_ = acs["BASE (V1)"]
    print("")
    print("  " + "-" * 108)
    print("  DELTAS CONTRA V1 TAL CUAL (negativo = mejor salvo en disp)")
    print("  " + "-" * 108)
    print("  %-20s %8s %8s %7s %10s %11s %11s %7s %6s"
          % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
             "salt_col>24", "inversiones", "s_max", "suav"))
    for nom, _ in VAR:
        t = tot[nom]
        print("  %-20s %+8.2f %+8d %+7d %+10d %+11d %+11d %+7.1f %+6.2f"
              % (nom, t["disp"] - b["disp"], t["sin_aut"] - b["sin_aut"],
                 t["huecos"] - b["huecos"], t["s_gt"] - b["s_gt"],
                 acs[nom]["col"] - ab_["col"], t["inv"] - b["inv"],
                 t["smax"] - b["smax"], t["suav"] - b["suav"]))

    # --- falsador de YSUAV ------------------------------------------------
    print("")
    print("  FALSADOR DE YSUAV (la Y no entra en el steer: solo pueden cambiar")
    print("  saltos>24, salt_col>24 -por el hypot- y s_max)")
    for nom, cfg in VAR:
        if (not cfg.get("ysuav") or cfg.get("schist", 1) != 1
                or cfg.get("nunca_sc")):
            continue
        t = tot[nom]
        malo = [k for k in ("disp", "sin_aut", "huecos", "inv")
                if abs(t[k] - b[k]) > (1e-9 if k == "disp" else 0)]
        if abs(t["suav"] - b["suav"]) > 1e-9:
            malo.append("suav")
        print("    %-20s %s" % (nom, "OK, solo cambiaron los saltos"
                                if not malo
                                else "*** CAMBIO " + ",".join(malo)
                                + " -> hay un bug"))

    print("")
    print("  CRITERIO PREREGISTRADO: una variante entra solo si baja")
    print("  salt_col>24 (la parte que puede mover el steer) sin empeorar")
    print("  disponibilidad, huecos ni inversiones, y sin romper los controles.")
    print("  Bajar solo saltos>24 por la via de la fila NO es una mejora de")
    print("  control: es sacarle a la metrica una dimension que el steer no usa.")
    print("")
    print("  LO QUE ESTE BANCO NO PUEDE VER")
    print("    disp, sin_aut y huecos NO dependen de la rama de POI: solo salen")
    print("    de que haya o no contorno. Por eso salen identicos en TODAS las")
    print("    variantes. La rama SIN_CERCA es un comportamiento de RECUPERACION")
    print("    -la linea no esta cerca, apunto a lo mas cercano que veo- y su")
    print("    beneficio caeria justamente en esas tres metricas. El replay es")
    print("    ESTRUCTURALMENTE CIEGO al costo de sacarla. Que SIN_SC mida mejor")
    print("    en todo lo visible NO autoriza a sacar la rama sin una prueba")
    print("    en lazo cerrado.")
    print("=" * 112)
    return 0


if __name__ == "__main__":
    sys.exit(main())
