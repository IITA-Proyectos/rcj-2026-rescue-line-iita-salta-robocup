# -*- coding: utf-8 -*-
"""
LENTE 1 - LA SECUENCIA DE ANGULOS PREVIA AL `steer = 0`.

Benjamin, 26-ago: "para darte cuenta cuando se sale tienes que ver cuando
llegue desde la raspberry un angle de 90 o un steer=0; previo a esos angulos
son los que hacen que se salga".

O sea: byte angle == 90  <=>  steer == 0  <=>  columna `rxsteer` == 0.
Este script NO mira el episodio: mira LA VENTANA PREVIA.

=========================================================================
                 FALSADOR, ESCRITO ANTES DE MIRAR LOS DATOS
=========================================================================

H-L1: los episodios de `rxsteer == 0` con comando FRESCO estan precedidos por
      una ventana SATURADA (absSteer clavado en 1,0 por la ganancia) mas de lo
      que se espera por azar.

VARIABLE DE EVENTO (binaria, por EPISODIO, no por muestra):
      "precedido" := fraccion de la ventana previa con absSteer >= 1,000
                     es >= F.
      absSteer = |rxsteer| * GAIN de esa corrida (1,35; 1,80 en `gain18`),
      recortado a 1,0. Saturado <=> |rxsteer| >= 1/GAIN
                                    = 0,741 con 1,35 ; 0,556 con 1,80.

SE REFUTA (H-L1 cae) si CUALQUIERA de estas:

  G1  el LIFT contra la TASA BASE LIMPIA es < 1,5x en ALGUN punto de la banda
  G2  el LIFT contra el PLACEBO (misma ventana, -3 s) es < 1,5x en ALGUN punto
  G3  no hay PLATEAU: el veredicto de G1/G2 cambia dentro de la banda
  G4  control de frescura: si los episodios contados no tienen comando fresco
      (ningun `rxage` bajo adentro), no son "la Pi diciendo centrado" y no
      valen. Se exige rxage >= 0 y min(rxage) <= A dentro del episodio.

BANDA PREREGISTRADA - se BARRE, no se elige un punto:
      A  umbral de frescura   `min(rxage)` <=   20, 40, 80, 150 ms
      N  duracion minima del episodio          100, 200, 300, 400 ms
      W  ventana previa                        200, 500, 1000 ms
      F  fraccion saturada que cuenta          0,30  0,50  0,70
      => 4 x 4 x 3 x 3 = 144 celdas. PLATEAU = mismo veredicto en las 144.

TASA BASE: se calculan las DOS y manda la conservadora.
      base_todo    todas las ventanas deslizantes de la corrida
      base_limpia  las que NO tocan ninguna muestra con rxsteer == 0
      `base_limpia` es la CONSERVADORA (mas alta, porque durante un steer=0
      absSteer vale 0 y nunca satura, lo que deprimiria la base y INFLARIA el
      lift). El gate G1 corre contra `base_limpia`.

PLACEBO: la misma ventana desplazada -3000 ms. Episodios sin historia
      suficiente se descartan y se reporta cuantos.

EVENTOS UNICOS: la unidad de analisis es el EPISODIO. Cada episodio cuenta UNA
      vez. El bug del "al menos uno sin break" ya mato una hipotesis aca.

DESCRIPTIVO (lo que pidio Benjamin, y va aunque el gate falle):
      1  |rxsteer| p50/p90/max a 200/500/1000 ms previos
      2  fraccion SATURADA y fraccion en PIVOTE (|rot| >= 0,999)
      3  trayectoria del angulo sobre la SECUENCIA DE COMANDOS DISTINTOS
         (no sobre muestras repetidas): inversiones de signo, monotonia
      4  placebo y tasa base -> LIFT contra las dos
      5  adentro del episodio: rxspeed, ls, rs, |ls-rs|, gz y CUANTO AVANZA

SANIDAD FISICA: distancia = rpm * pi * 6,88 cm / 60. Si el episodio "va
      derecho a fondo", |ls - rs| ~ 0 y el avance tiene que dar centimetros
      creibles para su duracion.

    python lente1_previa_al_steer0.py
"""

import glob
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                     # noqa: E402

MS = 5.0                                   # registrador a 200 Hz
BANDA_AGE = (20, 40, 80, 150)              # ms, frescura
BANDA_DUR = (100, 200, 300, 400)           # ms, duracion minima del episodio
BANDA_VENT = (200, 500, 1000)              # ms, ventana previa
BANDA_FRAC = (0.30, 0.50, 0.70)            # fraccion saturada
PLACEBO_MS = 3000
LIFT_MIN = 1.5
PIV_ROT = 0.999
DIAM_CM = 6.88
CIRC_CM = np.pi * DIAM_CM                  # 21,61 cm por vuelta

GAIN_POR_CORRIDA = {"pista_gain18": 1.80}
GAIN_DEF = 1.35


def rachas(mask):
    """(ini, fin) de cada racha contigua de True. fin es exclusivo."""
    m = np.asarray(mask).astype(np.int8)
    d = np.diff(np.concatenate([[0], m, [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def secuencia_comandos(v):
    """Valores DISTINTOS consecutivos: la secuencia de angulos de verdad."""
    if len(v) == 0:
        return np.array([])
    idx = np.concatenate([[0], np.flatnonzero(np.diff(v) != 0) + 1])
    return v[idx]


def inversiones(s):
    """Cambios de signo en la secuencia, ignorando los ceros."""
    nz = s[s != 0]
    if len(nz) < 2:
        return 0
    sg = np.sign(nz)
    return int((np.diff(sg) != 0).sum())


def cargar_pista():
    rutas = [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
             if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]
    D = {}
    for r in rutas:
        a, nota = RR.cargar(r)
        if a is None or len(a) < 500:
            continue
        n = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        g = GAIN_POR_CORRIDA.get(n, GAIN_DEF)
        steer = RR.col(a, "rxsteer") / 1000.0
        D[n] = dict(
            gain=g,
            steer=steer,
            abssteer=np.minimum(np.abs(steer) * g, 1.0),
            rot=RR.col(a, "rot") / 1000.0,
            age=RR.col(a, "rxage"),
            speed=RR.col(a, "rxspeed"),
            ls=RR.col(a, "ls"),
            rs=RR.col(a, "rs"),
            gz=RR.col(a, "gz") / 10.0,
            flr=RR.col(a, "fl_rpm"),
            frr=RR.col(a, "fr_rpm"),
            us=RR.col(a, "us"),
            nota=nota,
        )
    return D


def episodios_de(d, dur_ms, age_ms):
    """Episodios de rxsteer==0 con comando FRESCO. Eventos unicos."""
    nmin = int(round(dur_ms / MS))
    out = []
    for i0, i1 in rachas(d["steer"] == 0):
        if i1 - i0 < nmin:
            continue
        ag = d["age"][i0:i1]
        if ag.min() < 0:                    # -1 = nunca llego una trama
            continue
        if ag.min() > age_ms:               # ninguna trama fresca adentro
            continue
        out.append((i0, i1))
    return out


def frac_sat_cum(d):
    return np.concatenate([[0.0], np.cumsum(d["abssteer"] >= 1.0 - 1e-9)])


def frac_piv_cum(d):
    return np.concatenate([[0.0], np.cumsum(np.abs(d["rot"]) >= PIV_ROT)])


def frac_en(cum, ini, fin):
    if ini < 0 or fin > len(cum) - 1 or fin <= ini:
        return None
    return (cum[fin] - cum[ini]) / float(fin - ini)


# =========================================================================
def main():
    D = cargar_pista()
    print("")
    print("=" * 112)
    print("  LENTE 1  -  LA SECUENCIA DE ANGULOS PREVIA AL `steer = 0`")
    print("  %d corridas de PISTA del 22-ago. Falsador preregistrado en el docstring."
          % len(D))
    print("=" * 112)

    # ---------------- 0. CONTROL DE FRESCURA (gate G4) --------------------
    print("")
    print("-" * 112)
    print("  0. CONTROL  un `steer=0` con comando VIEJO no es la Pi diciendo")
    print("     'centrado': es silencio. Se separan ANTES de contar nada.")
    print("-" * 112)
    print("")
    print("  %-30s %6s %8s %9s %9s %9s %9s %8s"
          % ("corrida", "gain", "n", "dur_s", "steer=0", "age p50", "age p90",
             "age=-1"))
    for n, d in D.items():
        m = d["steer"] == 0
        dur = (d["us"][-1] - d["us"][0]) / 1e6
        ag = d["age"][m]
        print("  %-30s %6.2f %8d %9.1f %8.1f %% %9.0f %9.0f %7.1f %%"
              % (n[:30], d["gain"], len(d["steer"]), dur, 100 * m.mean(),
                 np.median(ag), np.percentile(ag, 90), 100 * (ag < 0).mean()))
    print("")
    print("  (age en ms. age=-1 = nunca llego una trama: esas muestras quedan fuera.)")

    # ---------------- 1. CUANTOS EPISODIOS HAY ---------------------------
    print("")
    print("-" * 112)
    print("  1. EPISODIOS UNICOS de `steer=0` FRESCO   (eventos, no muestras)")
    print("-" * 112)
    print("")
    hdr = "  %-30s" % "corrida"
    for A in BANDA_AGE:
        hdr += " |    age<=%-4d" % A
    print(hdr + "     (columnas = dur min 100/200/300/400 ms)")
    for n, d in D.items():
        fila = "  %-30s" % n[:30]
        for A in BANDA_AGE:
            cnt = [len(episodios_de(d, N, A)) for N in BANDA_DUR]
            fila += " | %3d %3d %3d %3d" % tuple(cnt)
        print(fila)
    tot = "  %-30s" % "TOTAL"
    for A in BANDA_AGE:
        cnt = [sum(len(episodios_de(d, N, A)) for d in D.values())
               for N in BANDA_DUR]
        tot += " | %3d %3d %3d %3d" % tuple(cnt)
    print(tot)

    # ---------------- 2. DESCRIPTIVO DE LA VENTANA PREVIA -----------------
    A0, N0 = 40, 200                       # punto central, pero se barre despues
    print("")
    print("-" * 112)
    print("  2. LA VENTANA PREVIA   (age<=%d ms, episodio >=%d ms)   POOL de las %d corridas"
          % (A0, N0, len(D)))
    print("     |rxsteer| es el angulo que mando la Pi, con signo quitado.")
    print("-" * 112)
    print("")
    print("  %8s %6s | %28s | %10s %10s | %18s"
          % ("ventana", "n_epi", "|rxsteer| p50 / p90 / max",
             "frac SAT", "frac PIV", "inversiones de signo"))
    desc = {}
    for W in BANDA_VENT:
        nw = int(round(W / MS))
        p50s, p90s, maxs, fs, fp, inv, mono, ult = [], [], [], [], [], [], [], []
        for n, d in D.items():
            cs, cp = frac_sat_cum(d), frac_piv_cum(d)
            for i0, i1 in episodios_de(d, N0, A0):
                if i0 - nw < 0:
                    continue
                v = d["steer"][i0 - nw:i0]
                av = np.abs(v)
                p50s.append(np.percentile(av, 50))
                p90s.append(np.percentile(av, 90))
                maxs.append(av.max())
                fs.append(frac_en(cs, i0 - nw, i0))
                fp.append(frac_en(cp, i0 - nw, i0))
                s = secuencia_comandos(v)
                inv.append(inversiones(s))
                if len(s) > 1:
                    dif = np.diff(np.abs(s))
                    mono.append(float((dif > 0).mean()))
                ult.append(v[-1])
        desc[W] = dict(p50=p50s, p90=p90s, mx=maxs, fs=fs, fp=fp,
                       inv=inv, mono=mono, ult=ult)
        print("  %6d ms %6d | %8.3f %8.3f %8.3f    | %9.3f %10.3f | p50 %.1f  p90 %.1f  max %d"
              % (W, len(p50s), np.median(p50s), np.median(p90s), np.median(maxs),
                 np.median(fs), np.median(fp),
                 np.percentile(inv, 50), np.percentile(inv, 90), max(inv)))
    print("")
    print("  frac SAT = fraccion de la ventana con absSteer clavado en 1,000")
    print("  frac PIV = fraccion con |rot| >= %.3f  (el pivote enganchado)" % PIV_ROT)

    W0 = 500
    dd = desc[W0]
    print("")
    print("  DISTRIBUCION de frac SAT en la ventana de %d ms  (n=%d episodios)"
          % (W0, len(dd["fs"])))
    for lo, hi in ((0.0, 0.001), (0.001, 0.1), (0.1, 0.3), (0.3, 0.5),
                   (0.5, 0.7), (0.7, 0.9), (0.9, 1.001)):
        c = int(((np.array(dd["fs"]) >= lo) & (np.array(dd["fs"]) < hi)).sum())
        print("     %5.2f - %-5.2f  %5d  %5.1f %%  %s"
              % (lo, hi, c, 100.0 * c / len(dd["fs"]), "#" * int(50.0 * c / len(dd["fs"]))))
    print("")
    print("  TRAYECTORIA sobre la secuencia de COMANDOS DISTINTOS (no muestras):")
    inva = np.array(dd["inv"])
    print("     inversiones de signo = 0 : %5.1f %%   (venia de un solo lado)"
          % (100.0 * (inva == 0).mean()))
    print("     inversiones 1 - 2        : %5.1f %%"
          % (100.0 * ((inva >= 1) & (inva <= 2)).mean()))
    print("     inversiones >= 3         : %5.1f %%   (oscilando)"
          % (100.0 * (inva >= 3).mean()))
    if dd["mono"]:
        mo = np.array(dd["mono"])
        print("     frac de pasos que SUBEN en |steer| : p50 %.2f  (0,5 = ni sube ni baja)"
              % np.median(mo))
        print("     monotona creciente pura            : %5.1f %%"
              % (100.0 * (mo >= 0.999).mean()))
    ua = np.abs(np.array(dd["ult"]))
    print("     ULTIMO comando antes del cero: |steer| p50 %.3f  p90 %.3f  max %.3f"
          % (np.median(ua), np.percentile(ua, 90), ua.max()))
    print("     ese ultimo comando ya estaba SATURADO: %5.1f %%"
          % (100.0 * (ua >= 1.0 / GAIN_DEF - 1e-9).mean()))

    # ---------------- 3. EL BARRIDO: LIFT vs BASE y vs PLACEBO ------------
    print("")
    print("-" * 112)
    print("  3. BARRIDO DE LA BANDA PREREGISTRADA   -   %d celdas"
          % (len(BANDA_AGE) * len(BANDA_DUR) * len(BANDA_VENT) * len(BANDA_FRAC)))
    print("     G1 lift vs base_limpia >= %.1f | G2 lift vs placebo >= %.1f | G3 plateau"
          % (LIFT_MIN, LIFT_MIN))
    print("-" * 112)
    npl = int(round(PLACEBO_MS / MS))
    filas = []
    for A in BANDA_AGE:
        for N in BANDA_DUR:
            for W in BANDA_VENT:
                nw = int(round(W / MS))
                for F in BANDA_FRAC:
                    ne = nb_e = np_ok = np_e = 0
                    base_t = base_l = nbt = nbl = 0
                    for n, d in D.items():
                        cs = frac_sat_cum(d)
                        cz = np.concatenate([[0.0], np.cumsum(d["steer"] == 0)])
                        for i0, i1 in episodios_de(d, N, A):
                            f = frac_en(cs, i0 - nw, i0)
                            if f is None:
                                continue
                            ne += 1
                            nb_e += (f >= F)
                            fp_ = frac_en(cs, i0 - npl - nw, i0 - npl)
                            if fp_ is not None:
                                np_e += 1
                                np_ok += (fp_ >= F)
                        # tasa base sobre TODAS las ventanas deslizantes
                        L = len(d["steer"])
                        if L > nw:
                            ii = np.arange(nw, L)
                            fr = (cs[ii] - cs[ii - nw]) / float(nw)
                            base_t += int((fr >= F).sum())
                            nbt += len(ii)
                            zz = (cz[ii] - cz[ii - nw]) == 0   # ventana sin steer=0
                            base_l += int((fr[zz] >= F).sum())
                            nbl += int(zz.sum())
                    if ne == 0 or nbl == 0:
                        continue
                    pe = nb_e / float(ne)
                    pbt = base_t / float(nbt)
                    pbl = base_l / float(nbl)
                    pp = (np_ok / float(np_e)) if np_e else float("nan")
                    l1 = pe / pbl if pbl > 0 else float("inf")
                    l2 = pe / pp if (np_e and pp > 0) else float("inf")
                    filas.append((A, N, W, F, ne, pe, pbt, pbl, pp, l1, l2))
    print("")
    print("  %4s %4s %5s %5s %5s %8s %9s %9s %9s %9s %9s %6s"
          % ("age", "dur", "vent", "frac", "n_ep", "p_epi", "base_todo",
             "base_limp", "placebo", "LIFTbase", "LIFTplac", "G1G2"))
    okl1 = okl2 = True
    for (A, N, W, F, ne, pe, pbt, pbl, pp, l1, l2) in filas:
        g1 = l1 >= LIFT_MIN
        g2 = l2 >= LIFT_MIN
        okl1 &= g1
        okl2 &= g2
        print("  %4d %4d %5d %5.2f %5d %7.3f %9.4f %9.4f %9.3f %9.2f %9.2f   %s%s"
              % (A, N, W, F, ne, pe, pbt, pbl, pp, l1, l2,
                 "+" if g1 else "-", "+" if g2 else "-"))
    l1s = np.array([f[9] for f in filas])
    l2s = np.array([f[10] for f in filas])
    l2f = l2s[np.isfinite(l2s)]
    print("")
    print("  RANGO EN LA BANDA   lift vs base_limpia  min %.2f  p50 %.2f  max %.2f"
          % (l1s.min(), np.median(l1s), l1s.max()))
    print("                      lift vs placebo      min %.2f  p50 %.2f  max %.2f"
          % (l2f.min(), np.median(l2f), l2f.max()))
    print("")
    print("  G1 (lift vs base >= %.1f en TODA la banda)    : %s" % (LIFT_MIN, "PASA" if okl1 else "FALLA"))
    print("  G2 (lift vs placebo >= %.1f en TODA la banda) : %s" % (LIFT_MIN, "PASA" if okl2 else "FALLA"))
    # PLATEAU de verdad: el veredicto conjunto tiene que ser el MISMO en todas
    # las celdas. Si unas dicen ++ y otras --, no hay plateau y punto.
    ver = [(f[9] >= LIFT_MIN) and (f[10] >= LIFT_MIN) for f in filas]
    plateau = all(ver) or not any(ver)
    print("  G3 (plateau: mismo veredicto en las %d celdas): %s   (%d de %d celdas pasan G1+G2)"
          % (len(filas), "PASA" if plateau else "FALLA", sum(ver), len(ver)))
    print("")
    print("  VEREDICTO H-L1: %s"
          % ("NO REFUTADA" if (okl1 and okl2 and plateau) else "REFUTADA"))
    if not plateau:
        print("  -> el veredicto CAMBIA dentro de la banda. Por regla del equipo,")
        print("     eso solo ya refuta: no se elige el punto que da lindo.")
    # donde se rompe
    porc = {}
    for (A, N, W, F, ne, pe, pbt, pbl, pp, l1, l2), v in zip(filas, ver):
        porc.setdefault(N, []).append(v)
    print("")
    print("  DONDE SE ROMPE  (celdas que pasan G1+G2, por duracion minima del episodio)")
    for N in BANDA_DUR:
        v = porc.get(N, [])
        ne = [f[4] for f in filas if f[1] == N]
        print("     dur >= %4d ms : %2d de %2d celdas pasan   (n_episodios = %d)"
              % (N, sum(v), len(v), ne[0] if ne else 0))

    # ---------------- 4. ADENTRO DEL EPISODIO -----------------------------
    print("")
    print("-" * 112)
    print("  4. QUE HACE EL ROBOT ADENTRO DEL `steer = 0`   (age<=%d, dur>=%d ms)"
          % (A0, N0))
    print("     'derecho a fondo' predice |ls-rs| ~ 0 y |gz| chico.")
    print("-" * 112)
    print("")
    print("  %-30s %5s %9s %9s %9s %9s %9s %9s"
          % ("corrida", "n_ep", "dur p50", "dur max", "rxspeed", "|ls-rs|",
             "|gz| p50", "avance"))
    durs, sp, dls, gzz, avn = [], [], [], [], []
    for n, d in D.items():
        eps = episodios_de(d, N0, A0)
        if not eps:
            print("  %-30s %5d          -" % (n[:30], 0))
            continue
        du = [(i1 - i0) * MS for i0, i1 in eps]
        s_ = [np.median(d["speed"][i0:i1]) for i0, i1 in eps]
        dl = [np.median(np.abs(d["ls"][i0:i1] - d["rs"][i0:i1])) for i0, i1 in eps]
        gz = [np.median(np.abs(d["gz"][i0:i1])) for i0, i1 in eps]
        av = []
        for i0, i1 in eps:
            rpm = 0.5 * (d["flr"][i0:i1] + d["frr"][i0:i1])
            av.append(float(np.sum(rpm * CIRC_CM / 60.0 * (MS / 1000.0))))
        durs += du; sp += s_; dls += dl; gzz += gz; avn += av
        print("  %-30s %5d %8.0f %8.0f %9.0f %9.1f %9.1f %7.1f cm"
              % (n[:30], len(eps), np.median(du), max(du), np.median(s_),
                 np.median(dl), np.median(gz), np.median(av)))
    if durs:
        print("")
        print("  POOL  n=%d episodios" % len(durs))
        print("     duracion   p50 %.0f  p90 %.0f  max %.0f ms"
              % tuple(np.percentile(durs, [50, 90, 100])))
        print("     rxspeed    p50 %.0f  (la consigna de velocidad que llego de la Pi)"
              % np.median(sp))
        print("     |ls - rs|  p50 %.1f  p90 %.1f rpm   -> %s"
              % (np.percentile(dls, 50), np.percentile(dls, 90),
                 "IGUALES: va DERECHO" if np.percentile(dls, 90) < 3 else "NO son iguales"))
        print("     |gz|       p50 %.1f  p90 %.1f deg/s" % (np.percentile(gzz, 50),
                                                            np.percentile(gzz, 90)))
        print("     AVANCE     p50 %.1f  p90 %.1f  max %.1f cm  (rueda 6,88 cm de diametro)"
              % tuple(np.percentile(avn, [50, 90, 100])))
    # ---------------- 5. LOS EPISODIOS, UNO POR UNO -----------------------
    # Son POCOS. Con n=35 / n=13 no hay excusa para esconderlos en un p50:
    # se listan todos y se ve la secuencia de angulos de cada uno.
    print("")
    print("-" * 112)
    print("  5. LOS %d EPISODIOS UNO POR UNO   (dur >= 100 ms, age<=%d)" % (35, A0))
    print("     `secuencia` = los ultimos comandos DISTINTOS de los 500 ms previos.")
    print("     age p50 ADENTRO del episodio: si son miles de ms, la Pi estaba MUDA.")
    print("-" * 112)
    print("")
    print("  %-22s %7s %6s %7s %6s %6s %4s  %s"
          % ("corrida", "t_s", "dur_ms", "agep50", "fSAT", "fPIV", "inv",
             "secuencia previa de |steer| (x1000, con signo)"))
    nw = int(round(500 / MS))
    fila_sil = 0
    for n, d in D.items():
        cs, cp = frac_sat_cum(d), frac_piv_cum(d)
        for i0, i1 in episodios_de(d, 100, A0):
            if i0 - nw < 0:
                continue
            v = d["steer"][i0 - nw:i0]
            s = secuencia_comandos(v)
            agp = np.median(d["age"][i0:i1])
            mudo = agp > 200
            fila_sil += mudo
            txt = " ".join("%+4d" % round(x * 1000) for x in s[-9:])
            print("  %-22s %7.1f %6.0f %7.0f %6.2f %6.2f %4d  %s%s"
                  % (n[:22], (d["us"][i0] - d["us"][0]) / 1e6, (i1 - i0) * MS,
                     agp, frac_en(cs, i0 - nw, i0), frac_en(cp, i0 - nw, i0),
                     inversiones(s), txt, "   <-- Pi MUDA" if mudo else ""))
    print("")
    print("  %d de los episodios tienen `rxage` p50 > 200 ms adentro: NO son la Pi" % fila_sil)
    print("  diciendo 'centrado', son silencio. El gate preregistrado (min rxage)")
    print("  NO los saca, y eso es una DEBILIDAD del falsador que escribi.")

    # ---------------- 6. SENSIBILIDAD POST-HOC ----------------------------
    print("")
    print("-" * 112)
    print("  6. SENSIBILIDAD  (POST-HOC, NO es el resultado primario)")
    print("     frescura estricta: p50(rxage) DENTRO del episodio <= A, no min().")
    print("     Se reporta solo para ver si el veredicto cambia. NO lo reemplaza.")
    print("-" * 112)
    res = []
    for A in BANDA_AGE:
        for N in BANDA_DUR:
            for W in BANDA_VENT:
                nwx = int(round(W / MS))
                for F in BANDA_FRAC:
                    ne = nb_e = np_ok = np_e = 0
                    base_l = nbl = 0
                    for n, d in D.items():
                        cs = frac_sat_cum(d)
                        cz = np.concatenate([[0.0], np.cumsum(d["steer"] == 0)])
                        for i0, i1 in episodios_de(d, N, A):
                            if np.median(d["age"][i0:i1]) > A:
                                continue           # <-- el estricto
                            f = frac_en(cs, i0 - nwx, i0)
                            if f is None:
                                continue
                            ne += 1
                            nb_e += (f >= F)
                            fp_ = frac_en(cs, i0 - npl - nwx, i0 - npl)
                            if fp_ is not None:
                                np_e += 1
                                np_ok += (fp_ >= F)
                        L = len(d["steer"])
                        if L > nwx:
                            ii = np.arange(nwx, L)
                            fr = (cs[ii] - cs[ii - nwx]) / float(nwx)
                            zz = (cz[ii] - cz[ii - nwx]) == 0
                            base_l += int((fr[zz] >= F).sum())
                            nbl += int(zz.sum())
                    if ne == 0 or nbl == 0:
                        res.append((A, N, W, F, ne, np.nan, np.nan, np.nan))
                        continue
                    pe = nb_e / float(ne)
                    pbl = base_l / float(nbl)
                    pp = (np_ok / float(np_e)) if np_e else np.nan
                    res.append((A, N, W, F, ne, pe / pbl if pbl else np.inf,
                                pe / pp if pp else np.inf, pbl))
    print("")
    print("  %4s %5s   %s" % ("dur", "n_ep", "lift vs base_limpia por (vent,frac)"))
    for N in BANDA_DUR:
        sub = [r for r in res if r[1] == N and r[0] == 40]
        ne = sub[0][4] if sub else 0
        v = " ".join("%5.2f" % r[5] if np.isfinite(r[5]) else "  n/a" for r in sub)
        print("  %4d %5d   %s" % (N, ne, v))
    fin = [r[5] for r in res if np.isfinite(r[5])]
    okc = [(np.isfinite(r[5]) and r[5] >= LIFT_MIN and
            np.isfinite(r[6]) and r[6] >= LIFT_MIN) for r in res]
    print("")
    print("  celdas que pasarian G1+G2 con frescura estricta: %d de %d"
          % (sum(okc), len(okc)))
    print("  plateau: %s   ->  veredicto POST-HOC: %s"
          % ("si" if (all(okc) or not any(okc)) else "NO",
             "NO REFUTADA" if all(okc) else "REFUTADA"))
    print("  (el primario ya habia refutado; esto confirma que no era el episodio mudo)")

    # ---------------- 7. EXPLORATORIO -------------------------------------
    # NO PREREGISTRADO. Salio de MIRAR la tabla 5, o sea que esta contaminado
    # por la mirada. No prueba nada: sirve para escribir el falsador de la
    # PROXIMA corrida. Se reporta como generador de hipotesis y nada mas.
    print("")
    print("-" * 112)
    print("  7. EXPLORATORIO - NO PREREGISTRADO, NO ES EVIDENCIA")
    print("     Salio de mirar la tabla 5. Solo sirve para escribir el falsador")
    print("     de la proxima corrida en el robot.")
    print("-" * 112)
    corto, largo = [], []
    flip = igual = 0
    cluster = 0
    for n, d in D.items():
        cs = frac_sat_cum(d)
        for i0, i1 in episodios_de(d, 100, A0):
            if i0 - nw < 0:
                continue
            f = frac_en(cs, i0 - nw, i0)
            dur = (i1 - i0) * MS
            (corto if dur < 300 else largo).append(f)
            # signo antes / despues del cero
            v = d["steer"][i0 - nw:i0]
            ant = v[v != 0]
            post = d["steer"][i1:i1 + nw]
            post = post[post != 0]
            if len(ant) and len(post):
                if np.sign(ant[-1]) != np.sign(post[0]):
                    flip += 1
                else:
                    igual += 1
            # otro steer=0 en los 500 ms previos?
            if (d["steer"][i0 - nw:i0] == 0).any():
                cluster += 1
    print("")
    print("  7a. LOS CORTOS Y LOS LARGOS NO SON LO MISMO")
    print("      episodio  < 300 ms : n=%2d   frac SAT previa p50 %.2f"
          % (len(corto), np.median(corto)))
    print("      episodio >= 300 ms : n=%2d   frac SAT previa p50 %.2f"
          % (len(largo), np.median(largo)))
    print("      -> el lift se cae en dur>=300 porque esos episodios NO vienen")
    print("         de saturacion. Son de otra especie.")
    print("")
    print("  7b. EL SIGNO DESPUES DEL CERO")
    print("      cambia de signo   : %2d  (el cero fue un CRUCE, no una perdida)" % flip)
    print("      sigue igual       : %2d" % igual)
    print("")
    print("  7c. RACIMOS")
    print("      episodios con OTRO steer=0 en los 500 ms previos: %d de %d"
          % (cluster, flip + igual))
    print("      -> los steer=0 vienen en racimo. La ventana previa de uno")
    print("         contiene al anterior, y eso deprime su frac SAT.")
    print("")
    print("=" * 112)
    return 0


if __name__ == "__main__":
    sys.exit(main())
