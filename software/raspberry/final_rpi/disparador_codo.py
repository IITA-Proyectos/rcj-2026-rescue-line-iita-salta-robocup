# -*- coding: utf-8 -*-
"""EL DISPARADOR DEL CODO: LA LINEA SE ACHICA ANTES DE PERDERSE?

El workflow dejo esto: la maniobra (cerrar el pivote por rumbo) es correcta,
pero el DISPARADOR falla -detectar el codo por absSteer saturado da 87,5 % de
falsos positivos-.

Candidato nuevo, que salio de mirar el video bien: la CANTIDAD DE LINEA VISIBLE
cae de forma sostenida ANTES de que se pierda. Si eso es cierto y es especifico,
es un disparador mucho mejor, y sale gratis: `black_sum` ya se calcula.

FALSADOR, ESCRITO ANTES:
  H-D: una caida sostenida de px_neg PRECEDE a la perdida de linea mas que el azar.
  SE REFUTA si:
    D1  el lift contra la tasa base < 2,0 en algun punto de la banda
    D2  la caida tambien ocurre seguido SIN perdida despues (precision < 30 %)
    D3  no hay plateau en la banda
  BANDA:  caida = px cae por debajo de FRAC de su mediana movil, sostenida SOST frames
          FRAC in {0.5, 0.6, 0.7}   SOST in {3, 5, 8}   horizonte in {20, 40} frames
  PERDIDA = px_neg < 50 (el gate de Main.py, en px del ROI)

    python disparador_codo.py
"""
import os, sys, glob
os.environ.setdefault("VISION_LINEA", "camino")
import numpy as np, cv2
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)

def panel(fr):
    h, w = fr.shape[:2]
    if w == 640 and h == 240:
        fr = fr[:, :320]
    return cv2.resize(fr, (160, 120))

def pxneg(fr):
    g = cv2.cvtColor(panel(fr), cv2.COLOR_BGR2GRAY)
    m = (g < 90).astype(np.uint8)
    m[:55, :] = 0
    return int(m.sum())

def serie(v):
    cap = cv2.VideoCapture(os.path.join(AQUI, v))
    out = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        out.append(pxneg(fr))
    cap.release()
    return np.array(out)

VIDS = ["hist.avi", "lineal.avi", "seguir.avi", "rumbo.avi", "a.avi",
        "como_esta.avi", "lineal70.avi"]
print("")
print("=" * 96)
print("  LA LINEA SE ACHICA ANTES DE PERDERSE?   (perdida = px_neg < 50)")
print("=" * 96)
S = {}
for v in VIDS:
    if not os.path.exists(os.path.join(AQUI, v)):
        continue
    s = serie(v)
    if len(s) < 200:
        continue
    S[v] = s
    print("  %-16s n=%5d  px p50=%5d  frames perdidos=%4d (%4.1f %%)"
          % (v, len(s), int(np.median(s)), int((s < 50).sum()),
             100 * np.mean(s < 50)))
if not S:
    print("  sin videos"); sys.exit(1)

print("")
print("  %6s %6s %6s | %7s %10s %9s %8s %9s"
      % ("frac", "sost", "horiz", "n event", "precision", "base", "lift", "veredicto"))
print("  " + "-" * 84)
lifts, prec = [], []
for FRAC in (0.5, 0.6, 0.7):
    for SOST in (3, 5, 8):
        for HOR in (20, 40):
            ev = ok = 0
            base_n = base_d = 0
            for v, s in S.items():
                med = np.convolve(s, np.ones(31) / 31, mode="same")
                bajo = s < FRAC * np.maximum(med, 1)
                perd = s < 50
                base_n += int(perd.sum()); base_d += len(perd)
                i = 0
                while i < len(s) - HOR - SOST:
                    if bajo[i:i + SOST].all() and not perd[i:i + SOST].any():
                        ev += 1
                        if perd[i + SOST:i + SOST + HOR].any():
                            ok += 1
                        i += HOR          # eventos unicos: no re-contar
                    else:
                        i += 1
            if ev < 5:
                continue
            p = ok / ev
            b = 1 - (1 - base_n / base_d) ** HOR   # prob de al menos una perdida por azar
            lf = p / b if b > 0 else float("nan")
            lifts.append(lf); prec.append(p)
            print("  %6.1f %6d %6d | %7d %9.0f %% %8.1f %% %8.2f %9s"
                  % (FRAC, SOST, HOR, ev, 100 * p, 100 * b, lf,
                     "ok" if (lf >= 2.0 and p >= 0.30) else "no"))
print("")
print("=" * 96)
if lifts:
    lo, hi = min(lifts), max(lifts)
    pl = min(prec)
    d1 = lo < 2.0
    d2 = pl < 0.30
    d3 = (lo < 2.0) != (hi < 2.0)
    print("  lift  min %.2f  max %.2f   |   precision min %.0f %%" % (lo, hi, 100 * pl))
    print("  D1 lift < 2,0 en algun punto ..... %s" % ("SE CUMPLE -> REFUTA" if d1 else "no"))
    print("  D2 precision < 30 %% ............. %s" % ("SE CUMPLE -> REFUTA" if d2 else "no"))
    print("  D3 sin plateau ................... %s" % ("SE CUMPLE -> REFUTA" if d3 else "no"))
    print("")
    print("  H-D %s" % ("NO SOBREVIVE" if (d1 or d2 or d3) else "SOBREVIVE en toda la banda"))
print("=" * 96)
