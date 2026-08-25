# -*- coding: utf-8 -*-
"""
VERIFICADOR ADVERSARIO de wf_v1_mejorado.py.

No reusa la clase V1Mejorado del autor. Reconstruye todo por otro camino:

  BASE      = airborne_v1_adaptado.AirborneV1 TAL CUAL (sin subclase, sin espia)
  YSUAV(w)  = se deriva POST-HOC de la serie de BASE. Es exacto porque en el
              original target=(tx, raw[1]) => raw[1] ES target[1], y avg_y no
              toca nada mas. Si el numero del autor coincide con este, su
              implementacion no tiene acoplamiento oculto.
  SCHIST(h) = subclase MINIMA que solo pisa confianza() y el bump tras PERDIDA.
              No copia paso().
  SIN_SC    = idem, la rama nunca se usa.

Ademas mide lo que el reporte NO midio:

  H1  la distribucion de |dx| DENTRO del balde "solo fila". El reporte dice que
      esos 469 "no mueven ni un grado el comando". Con el corte dx<=24 px un
      salto puede tener dx=24 => |dsteer| = 27 grados. Si la masa esta pegada a
      24, la frase es falsa.
  H2  invariancia estructural: si el conjunto de frames CON target es identico
      entre BASE y las variantes, entonces disp / sin_aut / huecos Y LOS DOS
      CONTROLES POSITIVOS son vacios como gate: no pueden refutar nada.
  H3  smax exacto del control lineal (sin redondear a %+.0f).
  H4  reparto por video de la mejora de salt_col (si sale de un solo video no
      es una mejora, es una anecdota).

    python verif_adv_v1mejorado.py
"""

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


def cargar_v1():
    sp = importlib.util.spec_from_file_location(
        "airborne_v1_adv", os.path.join(AQUI, "airborne_v1_adaptado.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def cargar_cand():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4_adv", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)

    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch, v4.v3.v2


def hacer_sc(v1):
    """Subclase MINIMA: solo confianza() + bump tras PERDIDA. paso() intacto."""

    class V1SC(v1.AirborneV1):
        def __init__(self, fps, h=1, nunca=False):
            v1.AirborneV1.__init__(self, fps)
            self.h = h
            self.nunca = nunca
            self.racha = 0

        def seleccionar_contorno(self, m):
            c, r = v1.AirborneV1.seleccionar_contorno(self, m)
            if c is None:
                # tras una perdida no hay gracia (misma regla declarada)
                self.racha = max(self.racha, self.h)
            return c, r

        def confianza(self, c):
            if c is None:
                self.racha = max(self.racha, self.h)
                return 'PERDIDA'
            mm = np.zeros((v1.H, v1.W), np.uint8)
            cv2.drawContours(mm, [c], -1, 255, -1)

            def band(ab):
                a, b = ab
                return int((mm[a:b + 1] > 0).sum()) >= v1.PIX_MIN_BAND
            near, mid, far = band(v1.NEAR), band(v1.MID), band(v1.FAR)
            if not near:
                self.racha += 1
                if self.racha >= self.h and not self.nunca:
                    return 'SIN_CERCA'
            else:
                self.racha = 0
            if mid and far:
                return 'HIGH'
            if mid:
                return 'MEDIUM'
            return 'LOW'
    return V1SC


# ---------------------------------------------------------------- corridas
def decodificar(ruta, v1):
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


def serie_v1(tr, v1, frames, desde=0, hasta=10 ** 9):
    out = []
    for i, g in enumerate(frames):
        if i > hasta:
            break
        r = tr.paso(g)
        if i >= desde:
            t = r.get("target")
            a = r.get("angle_target")
            s = None if (t is None or a is None or not np.isfinite(a)) \
                else float(a)
            out.append((t, s, r.get("estado"), r.get("motivo_target")))
    return out


def serie_cand(tr, v2, frames, desde=0, hasta=10 ** 9):
    out = []
    for i, g in enumerate(frames):
        if i > hasta:
            break
        r = tr.step(g)
        if i >= desde:
            t = r.get("target")
            s = None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90))
            out.append((t, s, r.get("state"), r.get("state")))
    return out


def aplicar_ysuav(serie, w_s, fps=FPS):
    """POST-HOC exacto: reemplaza la Y por la media movil causal, igual que
    Promedio(w*fps). No toca X, ni steer, ni presencia de target."""
    n = max(1, int(round(w_s * fps)))
    from collections import deque
    q = deque(maxlen=n)
    out = []
    for t, s, e, mt in serie:
        if t is None:
            out.append((None, s, e, mt))
            continue
        y = float(t[1])
        if np.isfinite(y):
            q.append(y)
        ty = float(np.mean(q)) if q else y
        out.append(((t[0], ty), s, e, mt))
    return out


# ---------------------------------------------------------------- metricas
def consec(serie, dxs_fila=None):
    """Saltos entre frames CONSECUTIVOS con target en los dos."""
    tot = col = fila = 0
    prev = None
    ds = []
    prevs = None
    for t, s, e, mt in serie:
        if t is not None and prev is not None:
            dx = abs(t[0] - prev[0])
            dy = abs(t[1] - prev[1])
            if s is not None and prevs is not None:
                ds.append(abs(s - prevs))
            if math.hypot(dx, dy) > UMBRAL:
                tot += 1
                if dx > UMBRAL:
                    col += 1
                else:
                    fila += 1
                    if dxs_fila is not None:
                        dxs_fila.append(dx)
        if t is None:
            prev = None
            prevs = None
        else:
            prev = t
            prevs = s
    return tot, col, fila, ds


def presencia(serie):
    return tuple(t is not None for t, _s, _e, _m in serie)


def acumular(dst, m):
    for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
        dst[k] += m[k]
    dst["smax"] = max(dst["smax"], m["s_max"])
    dst["suav"].append(m["suav"])


def nuevo_tot():
    return dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, smax=0.0,
                suav=[], tot=0, col=0, fila=0)


def main():
    v1 = cargar_v1()
    V1SC = hacer_sc(v1)
    SinBranch, v2 = cargar_cand()

    CFG = [
        ("BASE (V1 puro)", dict(kind="v1", h=1)),
        ("SCHIST 5 (mio)", dict(kind="v1", h=5)),
        ("SIN_SC (mio)", dict(kind="v1", h=1, nunca=True)),
        ("YSUAV.15 (posthoc)", dict(kind="post", src="BASE (V1 puro)",
                                    w=0.15)),
        ("YSUAV.15+SC5 (post)", dict(kind="post", src="SCHIST 5 (mio)",
                                     w=0.15)),
        ("CANDIDATA", dict(kind="cand")),
    ]

    tot = {n: nuevo_tot() for n, _ in CFG}
    dxs_fila = {n: [] for n, _ in CFG}
    percol = {n: {} for n, _ in CFG}
    ds_all = {n: [] for n, _ in CFG}
    ctl = {n: [] for n, _ in CFG}
    presencia_igual = {"v1_vs_sc5": True, "v1_vs_sinsc": True}

    videos = [v for v in AB.AUTONOMOS if os.path.exists(os.path.join(AQUI, v))]
    ctls = [c for c in AB.CONTROLES
            if c[5] and os.path.exists(os.path.join(AQUI, c[1]))]
    necesarios = list(videos)
    for c in ctls:
        if c[1] not in necesarios:
            necesarios.append(c[1])

    print("")
    print("=" * 100)
    print("  VERIFICADOR ADVERSARIO  -  re-derivacion independiente")
    print("=" * 100)

    t0 = time.time()
    for vid in necesarios:
        print("  %-18s" % vid, end="")
        sys.stdout.flush()
        frames = decodificar(os.path.join(AQUI, vid), v1)
        es_auto = vid in videos
        series = {}
        for nom, cfg in CFG:
            if cfg["kind"] == "v1":
                tr = V1SC(FPS, cfg.get("h", 1), cfg.get("nunca", False))
                series[nom] = serie_v1(tr, v1, frames)
            elif cfg["kind"] == "cand":
                series[nom] = serie_cand(SinBranch(FPS), v2, frames)
            else:
                series[nom] = aplicar_ysuav(series[cfg["src"]], cfg["w"])
        if es_auto:
            for nom, _ in CFG:
                s = series[nom]
                m = AB.metricas([(t, st, e) for t, st, e, _ in s])
                acumular(tot[nom], m)
                a, b, c, ds = consec(s, dxs_fila[nom])
                tot[nom]["tot"] += a
                tot[nom]["col"] += b
                tot[nom]["fila"] += c
                ds_all[nom].extend(ds)
                percol[nom][vid] = b
            presencia_igual["v1_vs_sc5"] &= (
                presencia(series["BASE (V1 puro)"])
                == presencia(series["SCHIST 5 (mio)"]))
            presencia_igual["v1_vs_sinsc"] &= (
                presencia(series["BASE (V1 puro)"])
                == presencia(series["SIN_SC (mio)"]))
        for cn, cvid, cfps, d0, h0, ex in ctls:
            if cvid != vid:
                continue
            for nom, cfg in CFG:
                if cfg["kind"] == "v1":
                    tr = V1SC(cfps, cfg.get("h", 1), cfg.get("nunca", False))
                    s = serie_v1(tr, v1, frames, d0, h0)
                elif cfg["kind"] == "cand":
                    s = serie_cand(SinBranch(cfps), v2, frames, d0, h0)
                else:
                    continue
                m = AB.metricas([(t, st, e) for t, st, e, _ in s])
                sts = [x for _t, x, _e, _m in s if x is not None]
                ctl[nom].append((cn, m["con"], ex,
                                 max(sts) if sts else float("nan")))
        del frames
        print("  %6.1f s" % (time.time() - t0))

    for n, _ in CFG:
        tot[n]["disp"] = 100.0 * tot[n]["con"] / max(tot[n]["n"], 1)
        tot[n]["suavm"] = float(np.mean(tot[n]["suav"]))

    print("")
    print("  " + "-" * 96)
    print("  ABSOLUTOS (re-derivados por otro camino)")
    print("  " + "-" * 96)
    print("  %-22s %7s %8s %7s %10s %11s %11s %7s %6s"
          % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
             "salt_col>24", "inversiones", "s_max", "suav"))
    for nom, _ in CFG:
        t = tot[nom]
        print("  %-22s %7.2f %8d %7d %10d %11d %11d %7.1f %6.2f"
              % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
                 t["col"], t["inv"], t["smax"], t["suavm"]))

    print("")
    print("  consecutivos totales / columna / solo fila")
    for nom, _ in CFG:
        t = tot[nom]
        print("    %-22s tot %5d   col %5d   fila %5d" % (nom, t["tot"],
                                                          t["col"],
                                                          t["fila"]))

    # ---- H1 -------------------------------------------------------------
    print("")
    print("  " + "-" * 96)
    print("  H1  distribucion de |dx| DENTRO del balde 'solo fila' de BASE")
    print("      (el reporte afirma que esos saltos 'no mueven ni un grado')")
    print("  " + "-" * 96)
    d = np.asarray(dxs_fila["BASE (V1 puro)"]) if dxs_fila["BASE (V1 puro)"] \
        else np.array([0.0])
    print("      n = %d   |dx| p50 %.2f  p90 %.2f  max %.2f"
          % (d.size, np.median(d), np.percentile(d, 90), d.max()))
    print("      |dsteer| = 1.125*|dx|:  p50 %.2f  p90 %.2f  max %.2f grados"
          % (1.125 * np.median(d), 1.125 * np.percentile(d, 90),
             1.125 * d.max()))
    for umb in (1, 2, 4, 8, 12, 16, 20, 24):
        k = int((d > umb).sum())
        print("      |dx| >  %2d px  (|dsteer| > %5.1f deg) : %5d  (%5.1f %%)"
              % (umb, 1.125 * umb, k, 100.0 * k / max(d.size, 1)))

    # ---- H2 -------------------------------------------------------------
    print("")
    print("  " + "-" * 96)
    print("  H2  invariancia estructural de la presencia de target")
    print("  " + "-" * 96)
    print("      BASE vs SCHIST5   presencia identica frame a frame : %s"
          % presencia_igual["v1_vs_sc5"])
    print("      BASE vs SIN_SC    presencia identica frame a frame : %s"
          % presencia_igual["v1_vs_sinsc"])
    print("      -> si es True, disp / sin_aut / huecos y los DOS controles")
    print("         positivos (que solo cuentan targets) NO pueden distinguir")
    print("         ninguna variante de rama de POI. Son gate VACIO.")

    # ---- H3 -------------------------------------------------------------
    print("")
    print("  " + "-" * 96)
    print("  H3  controles positivos, smax EXACTO (sin redondear)")
    print("  " + "-" * 96)
    for nom, _ in CFG:
        if not ctl[nom]:
            continue
        txt = "   ".join("%s %d/%d smax %+.4f" % (a, b, c, dd)
                         for a, b, c, dd in ctl[nom])
        print("      %-22s %s" % (nom, txt))

    # ---- H4 -------------------------------------------------------------
    print("")
    print("  " + "-" * 96)
    print("  H4  reparto por video de salt_col>24")
    print("  " + "-" * 96)
    print("      %-16s %8s %8s %8s %8s" % ("video", "BASE", "SC5", "SIN_SC",
                                           "d(SC5)"))
    for vid in videos:
        b = percol["BASE (V1 puro)"].get(vid, 0)
        s5 = percol["SCHIST 5 (mio)"].get(vid, 0)
        sn = percol["SIN_SC (mio)"].get(vid, 0)
        print("      %-16s %8d %8d %8d %+8d" % (vid.replace(".avi", ""), b,
                                                s5, sn, s5 - b))

    # ---- dsteer ---------------------------------------------------------
    print("")
    print("  |dsteer| todos los frames consecutivos")
    for nom, _ in CFG:
        x = np.asarray(ds_all[nom]) if ds_all[nom] else np.array([0.0])
        print("      %-22s p50 %5.2f  p90 %6.2f  max %6.2f"
              % (nom, np.median(x), np.percentile(x, 90), x.max()))
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
