# -*- coding: utf-8 -*-
"""VERIFICACION ADVERSARIA de wf_runtime.py.

Tres huecos que el banco original NO cierra:
  A) el claim "sin POI es identico bit a bit en los 10 autonomos": wf_runtime
     solo lo verifica bit a bit sobre hist/lineal/roi_auto (seccion 1b). Aca
     se corren los 10.
  B) nunca se verifico que sacar poi sea bit-exacto CON CAMINO+MONO ENCENDIDO,
     que es justo la config que se propone llevar al sabado.
  C) "PROD base+shim x1.032": Main.py:879 llama velocidad() SIEMPRE, y con
     VISION_LINEA=base ACTIVA es True y _CP esta instalado, asi que _curvatura()
     tambien corre en modo base. wf_runtime modela kappa SOLO en camino.
     Aca se mide PROD base+shim+kappa.
"""
import os, sys, time
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import cv2
import wf_runtime as WF
import ab_v2_v3_v4 as AB


def main():
    cv2.setNumThreads(1)
    v4, v3, v2, v1 = WF.cargar()
    SinBranch = WF.hacer_sinbranch(v4)
    L = print

    L("")
    L("=" * 92)
    L("  VERIFICACION ADVERSARIA de wf_runtime.py   (opencv hilos %d)"
      % cv2.getNumThreads())
    L("=" * 92)

    # ---------------- A y B: bit-exactitud sobre los 10 autonomos ----------
    vids = [v for v in AB.AUTONOMOS if os.path.exists(os.path.join(AQUI, v))]
    L("  autonomos presentes: %d de %d  -> %s" % (len(vids), len(AB.AUTONOMOS),
                                                  ", ".join(vids)))

    def series(rutas):
        return dict((v, WF.targets(WF.serie_cand(
            SinBranch, v2, os.path.join(AQUI, v)))) for v in rutas)

    t0 = time.time()
    base = series(vids)
    n_tot = sum(len(x) for x in base.values())
    L("  A) base SinBranch: %d frames en %.0f s" % (n_tot, time.time() - t0))

    r = WF.instalar_sin_poi(v3)
    sp = series(vids)
    r()
    mal = sum(sum(1 for x, y in zip(base[v], sp[v]) if x != y)
              + abs(len(base[v]) - len(sp[v])) for v in vids)
    L("  A) sin POI vs base, 10 autonomos : %d discrepancias de %d frames  %s"
      % (mal, n_tot, "OK" if mal == 0 else "*** REFUTA"))

    rc = WF.instalar_camino(v2, True, True)
    cm = series(vids)
    rc()
    dif = sum(sum(1 for x, y in zip(base[v], cm[v]) if x != y) for v in vids)
    L("  B) CAMINO+MONO cambia %d de %d targets (%.1f %%) en los 10 autonomos"
      % (dif, n_tot, 100.0 * dif / max(n_tot, 1)))

    rc = WF.instalar_camino(v2, True, True)
    rp = WF.instalar_sin_poi(v3)
    cms = series(vids)
    rp(); rc()
    mal2 = sum(sum(1 for x, y in zip(cm[v], cms[v]) if x != y)
               + abs(len(cm[v]) - len(cms[v])) for v in vids)
    L("  B) CAMINO+MONO sin POI vs CAMINO+MONO: %d discrepancias de %d  %s"
      % (mal2, n_tot, "OK" if mal2 == 0 else "*** REFUTA"))
    L("")

    # ---------------- C: PROD base+shim con y sin kappa --------------------
    rutas = [os.path.join(AQUI, v) for v in WF.VIDEOS]
    VAR = ["BASE limpio", "PROD base+shim", "PROD base+shim+kappa",
           "PROD camino+kappa"]
    acum = dict((n, []) for n in VAR)
    REPS = 4
    t0 = time.time()
    for rep in range(REPS):
        orden = [VAR[(rep + j) % len(VAR)] for j in range(len(VAR))]
        for ru in rutas:
            for nom in orden:
                rs = []
                if nom == "PROD base+shim":
                    rs.append(WF.instalar_camino(v2, False, False))
                    mk = WF.mk_cand(SinBranch, v2)
                elif nom == "PROD base+shim+kappa":
                    rs.append(WF.instalar_camino(v2, False, False))
                    mk = WF.mk_cand_kappa(SinBranch, v2)
                elif nom == "PROD camino+kappa":
                    rs.append(WF.instalar_camino(v2, True, True))
                    mk = WF.mk_cand_kappa(SinBranch, v2)
                else:
                    mk = WF.mk_cand(SinBranch, v2)
                try:
                    acum[nom].append(WF.pasada_limpia(mk, ru))
                finally:
                    for x in reversed(rs):
                        x()
        L("     rep %d/%d  %.0f s" % (rep + 1, REPS, time.time() - t0))

    L("")
    L("  C) COSTO DE LO QUE CORRE HOY EN PRODUCCION (p50 ms, %d frames)"
      % sum(len(x) for x in acum["BASE limpio"]))
    b = WF.stats_ms(np.concatenate(acum["BASE limpio"]))
    L("  %-24s %8s %8s %10s" % ("variante", "media", "p50", "x BASE p50"))
    for nom in VAR:
        s = WF.stats_ms(np.concatenate(acum[nom]))
        L("  %-24s %8.3f %8.3f %10.3f"
          % (nom, s["media"], s["p50"], s["p50"] / b["p50"]))
    L("")
    nv = len(rutas)
    for nom in VAR:
        ps = [float(np.percentile(np.concatenate(
            acum[nom][r * nv:(r + 1) * nv]), 50)) / 1e6 for r in range(REPS)]
        L("  %-24s p50 por rep: %s" % (nom, "  ".join("%.3f" % x for x in ps)))
    L("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
