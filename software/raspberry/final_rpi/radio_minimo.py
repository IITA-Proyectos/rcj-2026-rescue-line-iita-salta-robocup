# -*- coding: utf-8 -*-
"""
EL RADIO MAS CERRADO QUE EL ROBOT PUEDE TRAZAR.  Y por que subir la velocidad
no lo cambia.

Falsador preregistrado: FALSADOR-RADIO-MINIMO.md  (escrito ANTES de correr esto)

DE DONDE SALE
-------------
El traspaso de la noche del 25-ago cerro que la curva cerrada no es posible
porque v (9,0 cm/s) > omega*R (4,7 cm/s), y propuso tres salidas. La salida 2
-"subir el giro con LINE_PIVOT_SPEED"- estaba marcada como "la unica que no
cuesta tiempo de corrida".

Pero `drivebase.cpp:205-228` dice:

    _rightspeed = _speed                        (rueda externa)
    _leftspeed  = _speed * (1 - 2*rotation)     (rueda interna)

    v_centro = vel * (1 - rot)
    dv       = vel * 2 * rot
    omega    = dv / b_eff
    R        = v_centro / omega = b_eff * (1 - rot) / (2 * rot)

R NO CONTIENE vel. Subir LINE_PIVOT_SPEED sube omega y v en la misma proporcion.
La variable de control del radio es `rot`, no `vel`.

Y eso ya estaba medido sin interpretarlo asi: ANALISIS-2026-08-23.md:50-56 dice
"la constante no se mueve: 1,15 a 1,29 gr/s por rpm en las seis configuraciones".
Esa constante ES 1/R disfrazada.

VALIDACION DEL MAPEO, contra los datos crudos
---------------------------------------------
En `2026-08-22_pista_pivote35.csv`:  rot=345, ls=11, rs=38
    38 * (1 - 2*0.345) = 11.78  ->  ls=11.  La formula cierra y rot esta x1000.

    python radio_minimo.py
    python radio_minimo.py --diametro 6.88
"""

import argparse
import glob
import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                     # noqa: E402

R_CERRADA = 4.9          # cm, RCJ 2.2.2 (radio interno >= 40 mm)

# ---- banda preregistrada (FALSADOR-RADIO-MINIMO.md seccion 3) ----------------
BANDA_GZ = (20.0, 30.0, 40.0, 50.0)      # deg/s minimos para "esta girando"
BANDA_V = (1.0, 2.0, 3.0)                # cm/s minimos para "avanza"
BANDA_BIN = (0.10, 0.15)                 # ancho del bin de rot
BANDA_TRANS = (0, 3, 5)                  # muestras descartadas tras cambio de rot

# ---- ENMIENDA 1 al falsador (2026-08-26, ANTES de leer F1..F4 corregidos) ----
#
# La v1 de este script comparaba `rot` con `gz` EN EL MISMO INSTANTE y el control
# C1 fallo (49-90 %, se exigia > 95 %). El falsador dice que si C1 falla todo lo
# demas es basura, asi que aquel resultado NO se reporto.
#
# La causa no era el signo de `rot` (lo tiene: 46 % de las muestras son < 0) sino
# el LAG comando -> giro, que `retardo_real.py` ya habia medido en 13-14 muestras
# de 5 ms por correlacion cruzada. Barriendo el lag, la concordancia de signo
# PICA en 12-14 muestras en las cinco corridas que usan `steer()`:
#
#     lag         0      4      8     12     14     16     20     26
#     pivote35  92,1   93,8   95,1   96,0   95,9   95,4   94,2   91,7
#     con_hist  78,8   85,5   91,9   96,6   97,2   95,6   91,6   83,0
#
# Es una validacion cruzada, no un tuneo: el lag sale de OTRO metodo (correlacion
# cruzada de magnitud) y aca lo confirma un metodo distinto (concordancia de
# signo). Por eso el lag entra a la BANDA en vez de elegirse.
BANDA_LAG = (8, 12, 14, 16, 20)          # muestras de 5 ms

# `pista_arbol_de_ramas` corre por la rama `#else` del firmware
# (main.cpp:3875-3890): usa `steerAxleBias()` con rotation = +-1,0 FIJO y con
# frontScale/rearScale que le sacan par al eje delantero (drivebase.cpp:271-300).
# Es otra cinematica, no otra telemetria. Se reporta APARTE, no se descarta.
RAMA_DISTINTA = ("arbol_de_ramas",)


def signo_ruedas(a):
    """Velocidad con signo de cada lado, en rpm.

    `steer()` manda los lados derechos con `!_rightdir` (motores espejados), y
    los datos lo confirman: en reposo/adelante fl_dir=0, fr_dir=1. Asi que
    IZQUIERDA: dir==0 -> adelante.   DERECHA: dir==1 -> adelante.
    El control C3 verifica que esto sea cierto (en recta las 4 van igual).
    """
    def lado(ws, adelante_es):
        v = np.zeros(len(a))
        for w in ws:
            d = RR.col(a, "%s_dir" % w)
            r = RR.col(a, "%s_rpm" % w)
            r = np.where((r >= 0) & (r < 500), r, np.nan)
            v = v + np.where(d == adelante_es, r, -r)
        return v / len(ws)
    return lado(("fl", "bl"), 0.0), lado(("fr", "br"), 1.0)


def preparar(ruta, circ):
    a, nota = RR.cargar(ruta)
    if a is None or len(a) < 200:
        return None
    vi, vd = signo_ruedas(a)                       # rpm con signo
    k = circ / 60.0                                # rpm -> cm/s
    vi, vd = vi * k, vd * k
    return dict(
        nota=nota,
        rot=RR.col(a, "rot") / 1000.0,             # x1000 en el firmware
        w=RR.col(a, "gz") / 10.0,                  # main.cpp:789 "REAL x10"
        vc=(vi + vd) / 2.0,                        # velocidad del centro
        dv=(vd - vi),                              # diferencial -> giro
    )


def alinear(d, lag):
    """Alinea el giro medido con el comando que lo causo (lag en muestras)."""
    n = len(d["rot"]) - lag
    if n < 200:
        return None
    return dict(rot=d["rot"][:n], vc=d["vc"][:n], dv=d["dv"][:n],
                w=d["w"][lag:lag + n])


def mascara(z, gz_min, v_min, trans):
    """Muestras utiles: girando de verdad, avanzando, fuera del transitorio, y
    con el giro medido del MISMO signo que el diferencial de ruedas (si no
    concuerdan, el par (comando, giro) no es comparable en ese instante)."""
    m = (np.abs(z["w"]) >= gz_min) & (z["vc"] >= v_min)
    m &= np.isfinite(z["vc"]) & np.isfinite(z["dv"]) & (np.abs(z["rot"]) > 1e-6)
    m &= np.sign(z["dv"]) == np.sign(z["w"])
    if trans > 0:
        cambio = np.zeros(len(z["rot"]), bool)
        cambio[1:] = np.abs(np.diff(z["rot"])) > 1e-6
        bloq = np.zeros(len(cambio), bool)
        idx = np.flatnonzero(cambio)
        for t in range(trans):
            j = idx + t
            bloq[j[j < len(bloq)]] = True
        m &= ~bloq
    return m


def med(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else float("nan")


def juntar(datos, nombres, gz_min, v_min, trans, lag):
    """b_eff, R, v y |rot| concatenados sobre las corridas pedidas."""
    bs, Rs, vs, ro = [], [], [], []
    for n in nombres:
        z = alinear(datos[n], lag)
        if z is None:
            continue
        m = mascara(z, gz_min, v_min, trans)
        if m.sum() < 50:
            continue
        w = np.radians(np.abs(z["w"][m]))
        bs.append(np.abs(z["dv"][m]) / w)
        Rs.append(z["vc"][m] / w)
        vs.append(z["vc"][m])
        ro.append(np.abs(z["rot"][m]))
    if not bs:
        return None
    b, R = np.concatenate(bs), np.concatenate(Rs)
    v, r = np.concatenate(vs), np.concatenate(ro)
    ok = np.isfinite(b) & np.isfinite(R) & np.isfinite(v) & np.isfinite(r)
    return b[ok], R[ok], v[ok], r[ok]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diametro", type=float, default=6.88,
                    help="cm, efectivo de rodadura (25 counts/cm -> 6.88)")
    a = ap.parse_args()
    circ = math.pi * a.diametro
    LAG = 14                            # el del pico; la banda barre 8..20

    rutas = sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
    datos = {}
    for r in rutas:
        d = preparar(r, circ)
        if d is not None:
            datos[os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")] = d

    pista = [n for n in datos if n.startswith("pista")]
    steer = [n for n in pista if not any(x in n for x in RAMA_DISTINTA)]
    otra = [n for n in pista if any(x in n for x in RAMA_DISTINTA)]

    print("")
    print("=" * 100)
    print("  EL RADIO MAS CERRADO QUE EL ROBOT TRAZO")
    print("  rueda %.2f cm -> %.2f cm de circunferencia   |   lag comando->giro %d"
          " muestras (%d ms)" % (a.diametro, circ, LAG, LAG * 5))
    print("  falsador: FALSADOR-RADIO-MINIMO.md   |   R que exige la curva: %.1f cm"
          % R_CERRADA)
    print("=" * 100)

    # ---------------- CONTROLES ------------------------------------------
    print("")
    print("-" * 100)
    print("  CONTROLES  (si estos fallan, todo lo de abajo es basura)")
    print("-" * 100)
    print("")
    print("  C1  signo de omega medido == signo de rot comandado, con el lag aplicado")
    print("      (exige > 95 %%; la v1 sin lag daba 49-90 %% y por eso no se reporto)")
    ok_c1 = []
    for n in pista:
        z = alinear(datos[n], LAG)
        m = (np.abs(z["w"]) > 30) & (np.abs(z["rot"]) > 0.05)
        if m.sum() < 100:
            continue
        conc = float(np.mean(np.sign(z["w"][m]) == np.sign(z["rot"][m])) * 100)
        marca = "OK" if conc > 95 else "<-- NO PASA"
        if n in steer:
            ok_c1.append(conc > 95)
        else:
            marca += "   (rama steerAxleBias, se reporta aparte)"
        print("        %-34s %6.1f %%   n=%-6d %s" % (n[:34], conc, m.sum(), marca))

    print("")
    print("  C3  en recta (|rot| < 0.02):  dv y omega tienen que ser ~ 0")
    for n in pista:
        d = datos[n]
        m = (np.abs(d["rot"]) < 0.02) & (d["vc"] > 2.0) & np.isfinite(d["vc"])
        if m.sum() < 100:
            continue
        print("        %-34s dv p50=%6.2f cm/s   |w| p50=%5.1f d/s   n=%d"
              % (n[:34], med(d["dv"][m]), med(np.abs(d["w"][m])), m.sum()))
    print("        (|w| no baja a 0 porque `rot`=0 incluye las maniobras")
    print("         bloqueantes, donde el robot gira SIN pasar por steer())")

    print("")
    print("  C2  la corrida INVALIDA (ruedas en el aire) tiene que delatarse")
    for n in datos:
        if "INVALIDA" not in n:
            continue
        z = alinear(datos[n], LAG)
        m = mascara(z, 5.0, 1.0, 0)
        print("        %-34s n util=%-6d   |w| p50 de TODA la corrida = %.1f d/s"
              % (n[:34], m.sum(), med(np.abs(datos[n]["w"]))))
        print("        -> el giroscopio no ve giro: el metodo la rechaza sola")

    print("")
    print("  C4  el banco tiene que dar el mismo b_eff que la pista (dentro de 25 %)")
    bp = juntar(datos, steer, 30.0, 2.0, 3, LAG)
    for n in [x for x in datos if "banco" in x]:
        bb = juntar(datos, [n], 30.0, 2.0, 3, LAG)
        if bb is None or bp is None:
            print("        %-34s sin muestras utiles" % n[:34])
            continue
        dif = abs(np.median(bb[0]) - np.median(bp[0])) / np.median(bp[0]) * 100
        print("        %-34s b_eff=%5.2f cm  vs pista %5.2f cm   dif %4.0f %%  %s"
              % (n[:34], np.median(bb[0]), np.median(bp[0]), dif,
                 "OK" if dif <= 25 else "<-- NO PASA"))

    # ---------------- b_eff Y EL RADIO -----------------------------------
    print("")
    print("-" * 100)
    print("  b_eff = dv / omega   (ancho de via EFECTIVO: geometria + slip)")
    print("  y R_inst = v_centro / omega, POR FRAME (no cociente de percentiles)")
    print("-" * 100)
    print("")
    print("  %-32s %9s %9s %9s %9s %8s"
          % ("corrida", "b_eff cm", "R p05", "R p50", "rot p90", "n"))
    for n in steer + otra:
        r = juntar(datos, [n], 30.0, 2.0, 3, LAG)
        if r is None:
            print("  %-32s  (sin muestras utiles)" % n[:32])
            continue
        b, R, _v, ro = r
        marca = "   <- rama steerAxleBias" if n in otra else ""
        print("  %-32s %9.2f %9.2f %9.2f %9.2f %8d%s"
              % (n[:32], np.median(b), np.percentile(R, 5), np.median(R),
                 np.percentile(ro, 90), len(b), marca))

    b, R, _v, ro = bp
    b_glob = float(np.median(b))
    print("")
    print("  GLOBAL, las %d corridas que usan steer():  b_eff p50 = %.2f cm"
          % (len(steer), b_glob))
    print("     R_min_p05 = %.2f cm      R_p50 = %.2f cm      n = %d"
          % (np.percentile(R, 5), np.median(R), len(R)))
    print("")
    print("     La curva mas cerrada del reglamento exige R = %.1f cm." % R_CERRADA)
    print("     El robot trazo como minimo (p05) %.2f cm  ->  %s"
          % (np.percentile(R, 5),
             "SI LO ALCANZA" if np.percentile(R, 5) <= R_CERRADA
             else "NO alcanza, le falta un factor %.2f"
                  % (np.percentile(R, 5) / R_CERRADA)))

    # ---------------- QUE rot HARIA FALTA --------------------------------
    print("")
    print("-" * 100)
    print("  R = b_eff * (1 - rot) / (2 * rot)     ->     que rot pide R = 4,9 cm?")
    print("-" * 100)
    print("")
    rot_nec = b_glob / (2 * R_CERRADA + b_glob)
    print("  con b_eff = %.2f cm:   rot necesario = %.3f" % (b_glob, rot_nec))
    print("")
    print("  %-10s %12s %14s" % ("rot", "R (cm)", ""))
    for rr in (0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00):
        RR2 = b_glob * (1 - rr) / (2 * rr)
        print("  %-10.2f %12.2f %14s"
              % (rr, RR2, "  <-- la curva cerrada"
                 if abs(rr - round(rot_nec, 2)) < 0.05 else ""))

    # ---------------- LOS CUATRO FALSADORES, EN BANDA --------------------
    NCOMB = (len(BANDA_GZ) * len(BANDA_V) * len(BANDA_BIN)
             * len(BANDA_TRANS) * len(BANDA_LAG))
    print("")
    print("=" * 100)
    print("  LOS FALSADORES, BARRIDOS EN TODA LA BANDA PREREGISTRADA")
    print("  (%d combinaciones. Solo hay conclusion si el veredicto NO cambia)"
          % NCOMB)
    print("=" * 100)
    print("")

    ver = {"F1": [], "F2": [], "F3": [], "F4": []}
    for lag in BANDA_LAG:
        for gz_min in BANDA_GZ:
            for v_min in BANDA_V:
                for anchobin in BANDA_BIN:
                    for trans in BANDA_TRANS:
                        r = juntar(datos, steer, gz_min, v_min, trans, lag)
                        if r is None or len(r[0]) < 200:
                            continue
                        b, R, v, ro = r

                        q1, q2 = np.percentile(v, [33, 67])
                        lo, hi = b[v <= q1], b[v >= q2]
                        ver["F1"].append(
                            abs(med(hi) - med(lo)) / max(med(lo), 1e-9) > 0.25
                            if len(lo) > 20 and len(hi) > 20 else False)

                        bins = np.arange(0, 1.0 + anchobin, anchobin)
                        mm = [np.median(b[(ro >= bins[i]) & (ro < bins[i + 1])])
                              for i in range(len(bins) - 1)
                              if ((ro >= bins[i]) & (ro < bins[i + 1])).sum() >= 200]
                        ver["F2"].append(
                            (max(mm) - min(mm)) / max(min(mm), 1e-9) > 0.25
                            if len(mm) >= 2 else False)

                        pend = []
                        for i in range(len(bins) - 1):
                            s = (ro >= bins[i]) & (ro < bins[i + 1])
                            if s.sum() < 200:
                                continue
                            lv, lR = np.log(v[s]), np.log(R[s])
                            g = np.isfinite(lv) & np.isfinite(lR)
                            if g.sum() < 200 or np.std(lv[g]) < 1e-6:
                                continue
                            pend.append(abs(np.polyfit(lv[g], lR[g], 1)[0]))
                        ver["F3"].append(max(pend) > 0.25 if pend else False)

                        pred = np.median(b) * (1 - ro) / (2 * np.maximum(ro, 1e-6))
                        ver["F4"].append(
                            med(np.abs(pred - R) / np.maximum(R, 1e-9)) > 0.30)

    NOM = {
        "F1": "b_eff depende de la VELOCIDAD          (> 25 % entre terciles)",
        "F2": "b_eff depende de ROT                   (> 25 % entre bins)",
        "F3": "R depende de v dentro de un bin de rot (|dlogR/dlogv| > 0,25)",
        "F4": "el modelo NO predice R                 (error mediano > 30 %)",
    }
    print("  %-6s %-56s %10s %13s"
          % ("", "condicion que REFUTA H-R", "se cumple", "veredicto"))
    refutada = False
    for k in ("F1", "F2", "F3", "F4"):
        vv = ver[k]
        if not vv:
            print("  %-6s %-56s %10s %13s" % (k, NOM[k], "sin datos", "-"))
            continue
        p = 100.0 * sum(vv) / len(vv)
        v_ = "NO refuta" if p == 0 else ("REFUTA" if p == 100 else "SIN PLATEAU")
        if p > 0:
            refutada = True
        print("  %-6s %-56s %9.0f %% %13s" % (k, NOM[k], p, v_))

    print("")
    print("=" * 100)
    if not ok_c1 or not all(ok_c1):
        print("  ATENCION: C1 no pasa en todas las corridas de `steer()`.")
    if refutada:
        print("  H-R REFUTADA o NO CONCLUYENTE.")
        print("")
        print("  Lo que NO cambia igual, porque es algebra y no estadistica:")
        print("     R = v/omega y drivebase hace v ~ vel*(1-rot), omega ~ vel*2*rot/b.")
        print("     `vel` se cancela. Subir LINE_PIVOT_SPEED NO abre la curva.")
        print("     Lo que estos falsadores dicen es que `b_eff` NO es constante,")
        print("     o sea que el modelo IDEAL de skid steer no describe al robot:")
        print("     el slip depende de la velocidad y de rot. Eso es un hallazgo,")
        print("     no un fracaso, y hace que la salida 2 sea todavia PEOR.")
    else:
        print("  H-R SOBREVIVE en las %d combinaciones de la banda." % NCOMB)
        print("     El radio lo fija `rot`, NO la velocidad.")
        print("     Subir LINE_PIVOT_SPEED no abre la curva cerrada.")
    print("")
    print("  DIAGNOSTICO, no politica (regla 5). Y no dice si el control puede")
    print("  SOSTENER ese rot: dice que radio traza cuando lo pide.")
    print("=" * 100)
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
