# -*- coding: utf-8 -*-
"""
LENTE 2 - CUANTO TIEMPO VIVE EL ROBOT EN LA ZONA MUERTA DEL STEER.

    python zona_muerta.py

EL PLANTEO
----------
La cadena de control de hoy, verificada en el codigo:

    Main.py:72,160     angle [-90,+90] -> byte angle+90
    main.cpp:1839      steer = (data-90)/90            -> [-1,+1]
    main.cpp:3659      steerCmd = clamp(steer*1.35, -1, 1)     GAIN = 1.35
    main.cpp:3813-14   rot = absSteer^0.50 ; rot = 1 si absSteer >= 0.92
                       y ADEMAS rot = 1 mientras s_en_pivote (PEGAJOSO)
    drivebase.cpp:215  v_ext = vel ; v_int = vel*(1-2*rot)
                       v_centro = vel*(1-rot)   R = b_eff*(1-rot)/(2*rot)

Con GAIN = 1.35 el clamp satura en |steer| >= 1/1.35 = 0,7407, o sea a partir de
66,7 grados de imagen. De 66,7 a 90 grados el comando que sale es IDENTICO: un
cuarto del rango que manda la Pi NO TRANSMITE INFORMACION. Y el umbral de pivote
(absSteer >= 0,92) cae aun antes: |steer| >= 0,92/1.35 = 0,6815, o sea 61,3
grados. Arriba de ahi rot = 1 y v_centro = vel*(1-1) = 0: EL ROBOT NO AVANZA.

Este script mide CUANTO TIEMPO REAL vive el robot ahi, sobre las 6 corridas de
pista del 22-ago.

============================ FALSADOR, ESCRITO ANTES ==========================
(regla 1 del equipo: el falsador va en numeros y ANTES de mirar los datos)

H-Z1  LA ZONA MUERTA EXISTE EN TIEMPO.
      La fraccion del tiempo de pista con |steer| >= 1/gain (saturado) es
      sustancial.
      REFUTADA si esa fraccion cae por debajo del 5 % en CUALQUIER punto de la
      banda preregistrada.

H-Z2  ES UN ESTADO, NO UN TRANSITORIO.
      Los episodios saturados duran, en mediana, >= 100 ms, o sea >= 3 periodos
      de un lazo de 35 ms (retardo_real.py ya midio p50 35-40 ms).
      REFUTADA si la mediana cae por debajo de 100 ms en cualquier punto de la
      banda.

H-Z3  EL MAPEO VIEJO HABRIA AVANZADO DONDE EL DE HOY NO.
      OJO: esto es ALGEBRA, no un hallazgo empirico, y se reporta como tal
      (regla 7). Lo unico falsable aca es que la fraccion de tiempo con rot = 1
      sea despreciable, que ya cubre H-Z1.
      El mapeo VIEJO (dato historico de Benjamin, epoca de las omniwheels, NO es
      un objetivo) es: rotation = steer directo.

H-Z4  LOS TRAMOS SATURADOS TERMINAN EN steer = 0 MAS SEGUIDO.
      (steer = 0 es el marcador de "se salio" que dio Benjamin: byte angle = 90,
      y el protocolo no distingue eso de "perfectamente centrado".)
      REFUTADA si el LIFT contra la tasa base es < 1,5x, O si el LIFT contra el
      PLACEBO desplazado -3 s es < 1,5x, en cualquier punto de la banda.
      EVENTOS UNICOS: la unidad de analisis es el EPISODIO, no la muestra.

H-Z5  LA CULPA ES DE LA HISTERESIS, NO DEL UMBRAL.
      Se declara "el problema es la HISTERESIS" solo si la fraccion del tiempo
      de rot = 1 que SOLO puede venir del pegajoso es >= 50 % en los TRES
      estimadores independientes y en toda la banda.
      Se declara "el problema es el UMBRAL" si esa fraccion es < 20 % en los
      tres. Entre 20 % y 50 %, o si los tres no coinciden: NO CONCLUYENTE.

BANDA PREREGISTRADA (no se elige un punto: se barre y se exige PLATEAU)
    gain barrido                     1.30 , 1.35 , 1.40
    rxage maximo (comando fresco)    sin filtro , 100 , 50 , 30 ms
    duracion minima de episodio      50 , 100 , 200 ms
    ventana posterior (H-Z4)         300 , 500 , 800 ms
    piso de "curva no saturada"      0.20 , 0.30 , 0.40
    percentil para el estimador E2   p99 , p99.9 , max

LOS TRES ESTIMADORES DE H-Z5 (independientes entre si)
    E1  CONSTANTES DE HOY: |rot| >= 0.999 y |steer|*1.35 < 0.92.
        Depende de suponer gain 1.35 en las seis corridas, que es FALSO en la
        corrida `gain18` y dudoso en el resto (el campo `gain=` de la linea de
        procedencia se agrego DESPUES del 22-ago). Se reporta igual, marcado.
    E2  CONFIG-AGNOSTICO Y MONOTONO: por corrida, S_hi = max{ |steer| con
        |rot| < 0.999 }. Cualquier regla puntual es monotona en |steer|
        (rot = 1  <=>  |steer| >= T), asi que si existe una muestra con
        |steer| = S_hi y rot < 1, entonces T > S_hi. Toda muestra con rot = 1 y
        |steer| < S_hi es, POR LOGICA, imposible bajo la regla puntual: solo
        puede venir del pegajoso. No supone NINGUNA constante.
    E3  TELEMETRIA DE RAMA: la columna `ram` del CSV es `g_line_branch`
        (main.cpp:880 -> 3860), que vale 3 si y solo si absSteer >
        LINE_PIVOT_STEER en esa misma vuelta del lazo. Entonces |rot| >= 0.999
        con ram < 3 es rot = 1 SIN que haya disparado la regla puntual.

CONTROL QUE NO SE PUEDE FALSEAR (sin el cual no se reporta nada de H-Z5)
    C-H  la corrida `pista_pivote_sin_histeresis` tiene que dar fraccion
         pegajosa ~ 0 (< 10 %) y la corrida `pista_pivote_con_histeresis` tiene
         que dar MAS que ella. Si el estimador no separa esas dos corridas, el
         estimador esta roto.
    C-F  en los episodios de steer = 0 contados, `rxage` tiene que ser bajo.
    C-S  SANIDAD FISICA (regla 6): en las muestras con rot = 1 el giroscopio
         tiene que marcar giro y el avance por encoders tiene que ser ~ 0.

LO QUE ESTE SCRIPT NO PUEDE CONCLUIR
    - Las 6 corridas tienen CONFIGURACIONES DISTINTAS (gain 1.80 en una, pivote
      0.35 en otra, con y sin histeresis). El histograma de |rxsteer| es lo que
      mando la Pi, pero en LAZO CERRADO: depende de como se movio el robot, que
      depende de la config de esa corrida. No son seis repeticiones del mismo
      experimento.
    - b_eff = 20,9 cm es del robot de HOY (4 fijas de silicona). Los radios en
      cm NO valen para la epoca de las omni. Lo que no depende de b_eff es que
      rot = 1 => v_centro = 0.
    - Diagnostico confirmado != politica adoptada (regla 7).
"""

import glob
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                        # noqa: E402

MS = 5.0                        # el registrador va a 200 Hz -> 5 ms por muestra
B_EFF = 20.9                    # cm, ancho de via EFECTIVO del robot de HOY
D_RUEDA = 6.88                  # cm, diametro efectivo de rodadura de HOY
RPM_A_CMS = np.pi * D_RUEDA / 60.0        # rpm -> cm/s

BANDA_GAIN = (1.30, 1.35, 1.40)
BANDA_AGE = (None, 100, 50, 30)
BANDA_DUR_MS = (50, 100, 200)
BANDA_VENT_MS = (300, 500, 800)
BANDA_PISO = (0.20, 0.30, 0.40)
BANDA_PCT = ("p99", "p99.9", "max")
PLACEBO_MS = 3000
CERO_MIN_MS = 100               # duracion minima del episodio de steer = 0
# Filtro base de frescura del comando. Esta EN LA BANDA PREREGISTRADA
# (None, 100, 50, 30 ms). Se elige por variable de entorno para poder correr
# todo el analisis en cada punto de la banda sin tocar el codigo.
AGE_BASE = (None if os.environ.get("ZM_AGE", "") in ("", "none")
            else int(os.environ["ZM_AGE"]))
ROT1 = 0.999                    # rot viene x1000 entero: rot = 1 es exacto


def episodios(mask, dmin=1):
    """Rachas contiguas de `mask` de al menos `dmin` muestras -> [(ini, fin)]."""
    m = np.asarray(mask, dtype=np.int8)
    d = np.diff(np.concatenate([[0], m, [0]]))
    ini, fin = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return [(i, f) for i, f in zip(ini, fin) if f - i >= dmin]


def cargar_pista():
    rutas = [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
             if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]
    out = []
    for r in rutas:
        a, nota = RR.cargar(r)
        if a is None:
            continue
        d = {
            "n": os.path.basename(r).replace("2026-08-22_pista_", "").replace(".csv", ""),
            "nota": nota,
            "s": np.abs(RR.col(a, "rxsteer")) / 1000.0,
            "rot": np.abs(RR.col(a, "rot")) / 1000.0,
            "age": RR.col(a, "rxage"),
            "ram": RR.col(a, "ram"),
            "ls": RR.col(a, "ls"),
            "rs": RR.col(a, "rs"),
            "gz": RR.col(a, "gz") / 10.0,
        }
        # avance real por encoders (magnitud + signo de las columnas *_dir)
        sl = np.where(RR.col(a, "fl_dir") == 0, 1.0, -1.0)
        sl2 = np.where(RR.col(a, "bl_dir") == 0, 1.0, -1.0)
        sr = np.where(RR.col(a, "fr_dir") == 1, 1.0, -1.0)
        sr2 = np.where(RR.col(a, "br_dir") == 1, 1.0, -1.0)
        vl = (RR.col(a, "fl_rpm") * sl + RR.col(a, "bl_rpm") * sl2) / 2.0
        vr = (RR.col(a, "fr_rpm") * sr + RR.col(a, "br_rpm") * sr2) / 2.0
        d["v_enc"] = (vl + vr) / 2.0 * RPM_A_CMS       # cm/s, avance del centro
        d["vel_ext"] = np.maximum(np.abs(d["ls"]), np.abs(d["rs"]))   # rpm
        out.append(d)
    return out


def val(d, age_max):
    """Muestras validas: linea activa y, opcionalmente, comando fresco."""
    m = d["ram"] >= 0
    if age_max is not None:
        m = m & (d["age"] >= 0) & (d["age"] <= age_max)
    return m


def pct(x, q):
    return float(np.percentile(x, q)) if len(x) else float("nan")


def sec(k):
    return k * MS / 1000.0


# =============================================================================
def q1_histograma(runs):
    print("=" * 84)
    print("1. HISTOGRAMA DE |steer| EN BINS DE 0,05  (lo que manda la Pi)")
    print("=" * 84)
    print("Filtro base: `ram` >= 0 (el lazo de linea esta activo).")
    print()
    bins = np.arange(0, 1.0001, 0.05)
    nrun = [int(np.sum(val(d, AGE_BASE))) for d in runs]
    n_tot = sum(nrun)
    print("  bin       " + "".join("%9s" % d["n"][:8] for d in runs) + "     TOTAL")
    for i in range(len(bins) - 1):
        fila, tot = [], 0
        for d in runs:
            s = d["s"][val(d, AGE_BASE)]
            if i == len(bins) - 2:
                k = int(np.sum((s >= bins[i]) & (s <= 1.0)))
            else:
                k = int(np.sum((s >= bins[i]) & (s < bins[i + 1])))
            fila.append(k)
            tot += k
        print("  %.2f-%.2f " % (bins[i], bins[i + 1])
              + "".join("%8.1f%%" % (100.0 * f / max(1, nrun[j]))
                        for j, f in enumerate(fila))
              + "  %7.1f%%" % (100.0 * tot / max(1, n_tot)))
    print()
    print("FRACCION DEL TIEMPO EN CADA ZONA, por corrida, con gain 1.35:")
    print("  %-24s %10s %10s %10s" % ("corrida", "SATURADO", "PIVOTE", "steer=0"))
    print("  %-24s %10s %10s %10s" % ("", ">=0.7407", ">=0.6815", "exacto"))
    for d in runs:
        s = d["s"][val(d, AGE_BASE)]
        print("  %-24s %9.1f%% %9.1f%% %9.1f%%"
              % (d["n"], 100 * np.mean(s >= 1 / 1.35),
                 100 * np.mean(s >= 0.92 / 1.35), 100 * np.mean(s == 0)))
    resumen = {}
    for g in BANDA_GAIN:
        thr_sat, thr_piv = 1.0 / g, 0.92 / g
        for age in BANDA_AGE:
            ts = tp = na = 0
            for d in runs:
                s = d["s"][val(d, age)]
                ts += int(np.sum(s >= thr_sat))
                tp += int(np.sum(s >= thr_piv))
                na += len(s)
            resumen[(g, age)] = (ts / max(1, na), tp / max(1, na), na)
    print()
    print("  BANDA COMPLETA (las 6 corridas juntas):")
    print("  %6s %8s %9s %10s %10s %10s"
          % ("gain", "age_max", "thr_sat", "SATURADO", "PIVOTE", "n"))
    for g in BANDA_GAIN:
        for age in BANDA_AGE:
            fs, fp, n = resumen[(g, age)]
            print("  %6.2f %8s %9.4f %9.1f%% %9.1f%% %10d"
                  % (g, "-" if age is None else age, 1.0 / g, 100 * fs, 100 * fp, n))
    mn = min(v[0] for v in resumen.values())
    print()
    print("  H-Z1 (>= 5 %% saturado en TODA la banda): minimo %.1f %% -> %s"
          % (100 * mn, "SOBREVIVE" if mn >= 0.05 else "REFUTADA"))
    print()


# =============================================================================
def q2_episodios(runs):
    print("=" * 84)
    print("2. EPISODIOS SATURADOS: cuantos son y cuanto duran")
    print("=" * 84)
    print("EVENTOS UNICOS: cada racha contigua de |steer| >= 1/gain cuenta UNA vez.")
    print()
    for g in BANDA_GAIN:
        thr = 1.0 / g
        print("  --- gain %.2f  (satura en |steer| >= %.4f) ---" % (g, thr))
        print("  %-24s %6s %8s %8s %8s %8s %10s"
              % ("corrida", "epis", "p50 ms", "p90 ms", "max ms", "media", "t_total"))
        tot_ep, tot_dur = 0, []
        for d in runs:
            eps = episodios((d["s"] >= thr) & val(d, AGE_BASE), dmin=1)
            dur = np.array([(f - i) * MS for i, f in eps])
            if len(dur) == 0:
                print("  %-24s %6d" % (d["n"], 0))
                continue
            tot_ep += len(eps)
            tot_dur.append(dur)
            print("  %-24s %6d %8.0f %8.0f %8.0f %8.1f %9.1fs"
                  % (d["n"], len(eps), pct(dur, 50), pct(dur, 90), dur.max(),
                     dur.mean(), dur.sum() / 1000.0))
        allc = np.concatenate(tot_dur)
        print("  %-24s %6d %8.0f %8.0f %8.0f %8.1f %9.1fs"
              % ("TODAS", tot_ep, pct(allc, 50), pct(allc, 90), allc.max(),
                 allc.mean(), allc.sum() / 1000.0))
        print("  episodios >= 100 ms: %d de %d (%.0f %%), se llevan el %.0f %% del tiempo saturado"
              % (int(np.sum(allc >= 100)), len(allc), 100.0 * np.mean(allc >= 100),
                 100.0 * allc[allc >= 100].sum() / allc.sum()))
        print()
    thr = 1.0 / 1.35
    allc = np.concatenate([np.array([(f - i) * MS for i, f in
                                     episodios((d["s"] >= thr) & val(d, AGE_BASE))])
                           for d in runs])
    print("  H-Z2 (p50 >= 100 ms, gain 1.35): p50 = %.0f ms -> %s"
          % (pct(allc, 50), "SOBREVIVE" if pct(allc, 50) >= 100 else "REFUTADA"))
    print()


# =============================================================================
def q3_viejo_vs_hoy(runs):
    print("=" * 84)
    print("3. MAPEO VIEJO (rot = steer) CONTRA EL DE HOY, muestra por muestra")
    print("=" * 84)
    print("ALGEBRA, NO MEDICION. Se calcula que rot / R / v_centro habrian salido")
    print("con cada mapeo para el MISMO |steer| que mando la Pi.")
    print("R usa b_eff = 20,9 cm, que es del ROBOT DE HOY (4 fijas de silicona).")
    print("El mapeo viejo es de la epoca de las OMNI: su R en cm es contrafactico.")
    print()
    S = np.concatenate([d["s"][val(d, AGE_BASE)] for d in runs])
    ROT_R = np.concatenate([d["rot"][val(d, AGE_BASE)] for d in runs])
    VEL = np.concatenate([d["vel_ext"][val(d, AGE_BASE)] for d in runs])
    n = len(S)

    aS = np.minimum(S * 1.35, 1.0)
    rot_hoy = np.where(aS >= 0.92, 1.0, np.sqrt(aS))          # sin el pegajoso
    rot_vie = np.minimum(S, 1.0)

    def R(rot):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(rot > 0, B_EFF * (1 - rot) / (2 * np.maximum(rot, 1e-9)),
                            np.inf)

    print("  n = %d muestras validas = %.1f s de pista" % (n, sec(n)))
    print()
    print("  %-36s %10s %10s %10s" % ("", "VIEJO", "HOY(form)", "HOY(real)"))
    print("  %-36s %10s %10s %10s" % ("", "rot=steer", "sin pegaj", "log CSV"))
    for etq, q in (("rot p10", 10), ("rot p50", 50), ("rot p90", 90)):
        print("  %-36s %10.3f %10.3f %10.3f"
              % (etq, pct(rot_vie, q), pct(rot_hoy, q), pct(ROT_R, q)))
    print("  %-36s %9.1f%% %9.1f%% %9.1f%%"
          % ("fraccion del tiempo con rot = 1",
             100 * np.mean(rot_vie >= ROT1), 100 * np.mean(rot_hoy >= ROT1),
             100 * np.mean(ROT_R >= ROT1)))
    print("  %-36s %9.1fs %9.1fs %9.1fs"
          % ("segundos con rot = 1 (v_centro = 0)",
             sec(np.sum(rot_vie >= ROT1)), sec(np.sum(rot_hoy >= ROT1)),
             sec(np.sum(ROT_R >= ROT1))))
    vfc_v, vfc_h, vfc_r = 1 - rot_vie, 1 - rot_hoy, 1 - ROT_R
    print("  %-36s %10.3f %10.3f %10.3f"
          % ("v_centro/vel  media", vfc_v.mean(), vfc_h.mean(), vfc_r.mean()))
    print("  %-36s %10.3f %10.3f %10.3f"
          % ("v_centro/vel  p50", pct(vfc_v, 50), pct(vfc_h, 50), pct(vfc_r, 50)))
    print()
    print("  RADIO trazado (cm), con b_eff = 20,9 del robot de HOY:")
    Rv, Rh, Rr = R(rot_vie), R(rot_hoy), R(ROT_R)
    for etq, q in (("R p50", 50), ("R p90", 90)):
        print("  %-36s %10.2f %10.2f %10.2f" % (etq, pct(Rv, q), pct(Rh, q), pct(Rr, q)))
    print("  %-36s %9.1f%% %9.1f%% %9.1f%%"
          % ("fraccion con R < 4,9 cm (curva RCJ)",
             100 * np.mean(Rv < 4.9), 100 * np.mean(Rh < 4.9), 100 * np.mean(Rr < 4.9)))
    print()
    print("  CUANTO TIEMPO HABRIA AVANZADO Y NO AVANZO")
    solo_hoy = (ROT_R >= ROT1) & (rot_vie < ROT1)
    print("    rot_REAL = 1 pero rot_VIEJO < 1 : %d muestras = %.1f s = %.1f %% del tiempo"
          % (int(solo_hoy.sum()), sec(solo_hoy.sum()), 100 * solo_hoy.mean()))
    solo_f = (rot_hoy >= ROT1) & (rot_vie < ROT1)
    print("    (solo por la FORMULA, sin el pegajoso): %d muestras = %.1f s = %.1f %%"
          % (int(solo_f.sum()), sec(solo_f.sum()), 100 * solo_f.mean()))
    v_perd = VEL[solo_hoy] * (1 - rot_vie[solo_hoy]) * RPM_A_CMS
    print("    v_centro que habria tenido ahi, con la MISMA vel comandada:")
    print("      p50 = %.2f cm/s   media = %.2f cm/s   (hoy: 0,00 cm/s por definicion)"
          % (pct(v_perd, 50), v_perd.mean()))
    print("    avance NO recorrido = %.1f cm en las 6 corridas (integral v*dt)"
          % (v_perd.sum() * MS / 1000.0))
    print()
    print("  TABLA steer -> lo que sale con cada mapeo (algebra pura):")
    print("  %8s %8s | %8s %8s %10s | %8s %8s %10s"
          % ("|steer|", "grados", "rot_VIE", "vc/vel", "R_vie cm",
             "rot_HOY", "vc/vel", "R_hoy cm"))
    for s in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.681, 0.7, 0.741, 0.8, 0.9, 1.0):
        a = min(s * 1.35, 1.0)
        rh = 1.0 if a >= 0.92 else a ** 0.5
        rv = s
        Rh_ = B_EFF * (1 - rh) / (2 * rh)
        Rv_ = B_EFF * (1 - rv) / (2 * rv)
        print("  %8.3f %8.1f | %8.3f %8.3f %10.2f | %8.3f %8.3f %10.2f"
              % (s, s * 90, rv, 1 - rv, Rv_, rh, 1 - rh, Rh_))
    print()


# =============================================================================
def q4_terminan_en_cero(runs):
    print("=" * 84)
    print("4. LOS TRAMOS SATURADOS TERMINAN EN steer = 0 MAS SEGUIDO?")
    print("=" * 84)
    print("EVENTOS UNICOS + TASA BASE + PLACEBO DESPLAZADO -3 s (reglas 3 y 4).")
    print("Evento: dentro de la ventana posterior EMPIEZA un episodio de steer == 0")
    print("de al menos %d ms." % CERO_MIN_MS)
    print()
    filas = []
    for g in BANDA_GAIN:
        thr = 1.0 / g
        for piso in BANDA_PISO:
            if piso >= thr:
                continue
            for dmin_ms in BANDA_DUR_MS:
                dmin = int(dmin_ms / MS)
                for vent_ms in BANDA_VENT_MS:
                    W = int(vent_ms / MS)
                    P = int(PLACEBO_MS / MS)
                    n_sat = n_sat_ok = n_sat_pl = 0
                    n_no = n_no_ok = 0
                    n_base = n_base_ok = 0
                    ages = []
                    for d in runs:
                        m = val(d, AGE_BASE)
                        s, N = d["s"], len(d["s"])
                        ci = np.array(sorted(i for i, f in
                                             episodios((s == 0) & m,
                                                       int(CERO_MIN_MS / MS))),
                                      dtype=int)

                        def hay(a, b):
                            return bool(len(ci)) and bool(np.any((ci >= a) & (ci < b)))

                        for i, f in episodios((s >= thr) & m, dmin):
                            n_sat += 1
                            if hay(f, min(N, f + W)):
                                n_sat_ok += 1
                                j = ci[(ci >= f) & (ci < f + W)][0]
                                ages.append(d["age"][j])
                            if f - P >= 0 and hay(f - P, f - P + W):
                                n_sat_pl += 1
                        for i, f in episodios((s >= piso) & (s < thr) & m, dmin):
                            n_no += 1
                            if hay(f, min(N, f + W)):
                                n_no_ok += 1
                        for a0 in range(0, N - W, W):          # ventanas disjuntas
                            if not m[a0]:
                                continue
                            n_base += 1
                            if hay(a0, a0 + W):
                                n_base_ok += 1
                    filas.append((g, piso, dmin_ms, vent_ms, n_sat,
                                  n_sat_ok / max(1, n_sat), n_no,
                                  n_no_ok / max(1, n_no),
                                  n_sat_pl / max(1, n_sat),
                                  n_base_ok / max(1, n_base),
                                  float(np.median(ages)) if ages else float("nan")))
    print("  %5s %5s %5s %5s | %5s %7s | %5s %7s | %7s %7s | %6s %6s %6s | %5s"
          % ("gain", "piso", "dmin", "vent", "nSAT", "p_SAT", "nNO", "p_NO",
             "p_plac", "p_base", "liftB", "liftP", "liftN", "age"))
    for (g, piso, dm, vt, ns, ps, nn, pn, pp, pb, ag) in filas:
        lb = ps / pb if pb > 0 else float("inf")
        lp = ps / pp if pp > 0 else float("inf")
        ln = ps / pn if pn > 0 else float("inf")
        print("  %5.2f %5.2f %5d %5d | %5d %6.1f%% | %5d %6.1f%% | %6.1f%% %6.1f%% | %6.2f %6.2f %6.2f | %5.0f"
              % (g, piso, dm, vt, ns, 100 * ps, nn, 100 * pn, 100 * pp, 100 * pb,
                 lb, lp, ln, ag))
    lb = [f[5] / f[9] if f[9] > 0 else float("inf") for f in filas]
    lp = [f[5] / f[8] if f[8] > 0 else float("inf") for f in filas]
    ln = [f[5] / f[7] if f[7] > 0 else float("inf") for f in filas]
    print()
    print("  lift contra TASA BASE : min %.2f  p50 %.2f  max %.2f"
          % (min(lb), float(np.median(lb)), max(lb)))
    print("  lift contra PLACEBO   : min %.2f  p50 %.2f  max %.2f"
          % (min(lp), float(np.median(lp)), max(lp)))
    print("  lift contra NO-SAT    : min %.2f  p50 %.2f  max %.2f"
          % (min(ln), float(np.median(ln)), max(ln)))
    print("  H-Z4 (lift >= 1,5x contra base Y placebo en TODA la banda): %s"
          % ("SOBREVIVE" if (min(lb) >= 1.5 and min(lp) >= 1.5) else "REFUTADA"))
    print()


# =============================================================================
def q5_pegajoso(runs):
    print("=" * 84)
    print("5. EL PIVOTE PEGAJOSO: rot = 1 con absSteer YA BAJO")
    print("=" * 84)
    print("Tres estimadores independientes. E2 y E3 NO suponen ninguna constante.")
    print()
    print("  --- por corrida, muestras con |rot| >= 0.999 ---")
    print("  %-22s %7s %8s | %6s %7s | %6s %7s | %6s %7s"
          % ("corrida", "n_rot1", "t_rot1", "E1 n", "E1 %", "E2 n", "E2 %",
             "E3 n", "E3 %"))
    tab = {}
    for d in runs:
        m = val(d, AGE_BASE)
        rot1 = (d["rot"] >= ROT1) & m
        n1 = int(rot1.sum())
        s = d["s"]
        e1 = rot1 & (s * 1.35 < 0.92)
        base = s[m & (d["rot"] < ROT1)]
        S_hi = float(np.max(base)) if len(base) else 0.0
        e2 = rot1 & (s < S_hi)
        e3 = rot1 & (d["ram"] < 3)
        tab[d["n"]] = (n1, e1, e2, e3, S_hi)
        print("  %-22s %7d %7.1fs | %6d %6.1f%% | %6d %6.1f%% | %6d %6.1f%%"
              % (d["n"], n1, sec(n1),
                 int(e1.sum()), 100 * e1.sum() / max(1, n1),
                 int(e2.sum()), 100 * e2.sum() / max(1, n1),
                 int(e3.sum()), 100 * e3.sum() / max(1, n1)))
    n1t = sum(v[0] for v in tab.values())
    print()
    for k, idx in (("E1", 1), ("E2", 2), ("E3", 3)):
        tot = sum(int(v[idx].sum()) for v in tab.values())
        print("  TOTAL %s: %d de %d muestras rot=1 = %.1f %%   (%.1f s de %.1f s)"
              % (k, tot, n1t, 100.0 * tot / max(1, n1t), sec(tot), sec(n1t)))
    print()
    print("  S_hi por corrida (el |steer| mas alto que NO disparo rot = 1):")
    for d in runs:
        print("    %-24s S_hi = %.3f   (x1.35 = %.3f en unidades de absSteer)"
              % (d["n"], tab[d["n"]][4], 1.35 * tab[d["n"]][4]))
    print()
    print("  --- CONTROL C-H: corrida SIN histeresis contra corrida CON ---")
    sin_h = [d["n"] for d in runs if "sin_histeresis" in d["n"]]
    con_h = [d["n"] for d in runs if "con_histeresis" in d["n"]]
    if sin_h and con_h:
        for k, idx in (("E1", 1), ("E2", 2), ("E3", 3)):
            a, b = tab[sin_h[0]], tab[con_h[0]]
            fa = 100.0 * a[idx].sum() / max(1, a[0])
            fb = 100.0 * b[idx].sum() / max(1, b[0])
            print("    %s: sin_histeresis %5.1f %%  vs  con_histeresis %5.1f %%   -> %s"
                  % (k, fa, fb, "PASA" if (fa < 10.0 and fb > fa) else "FALLA"))
    print()
    print("  --- EPISODIOS de rot = 1 que SOLO pueden venir del pegajoso (E2) ---")
    for dmin_ms in BANDA_DUR_MS:
        dmin = int(dmin_ms / MS)
        durs, cuenta = [], 0
        for d in runs:
            m = val(d, AGE_BASE)
            rot1 = (d["rot"] >= ROT1) & m
            base = d["s"][m & (d["rot"] < ROT1)]
            S_hi = float(np.max(base)) if len(base) else 0.0
            eps = episodios(rot1 & (d["s"] < S_hi), dmin)
            cuenta += len(eps)
            durs += [(f - i) * MS for i, f in eps]
        durs = np.array(durs) if durs else np.array([0.0])
        print("    dmin %3d ms: %4d episodios  p50 %5.0f  p90 %6.0f  max %6.0f ms  total %6.1f s"
              % (dmin_ms, cuenta, pct(durs, 50), pct(durs, 90), durs.max(),
                 durs.sum() / 1000.0))
    print()
    print("  --- PLATEAU sobre el percentil de S_hi (banda preregistrada) ---")
    print("  %-8s %8s %10s" % ("pctil", "n_E2", "% de rot1"))
    for q in BANDA_PCT:
        tot, n1 = 0, 0
        for d in runs:
            m = val(d, AGE_BASE)
            base = d["s"][m & (d["rot"] < ROT1)]
            S_hi = (float(np.max(base)) if q == "max"
                    else float(np.percentile(base, 99.0 if q == "p99" else 99.9)))
            rot1 = (d["rot"] >= ROT1) & m
            tot += int((rot1 & (d["s"] < S_hi)).sum())
            n1 += int(rot1.sum())
        print("  %-8s %8d %9.1f%%" % (q, tot, 100.0 * tot / max(1, n1)))
    print()
    print("  --- cuanto del TIEMPO TOTAL de pista es rot=1 solo por el pegajoso ---")
    n_val = sum(int(np.sum(val(d, AGE_BASE))) for d in runs)
    for k, idx in (("E1", 1), ("E2", 2), ("E3", 3)):
        tot = sum(int(v[idx].sum()) for v in tab.values())
        print("    %s: %.1f %% del tiempo de pista (%.1f s de %.1f s)"
              % (k, 100.0 * tot / max(1, n_val), sec(tot), sec(n_val)))
    print()
    fr = [100.0 * sum(int(v[i].sum()) for v in tab.values()) / max(1, n1t)
          for i in (1, 2, 3)]
    if min(fr) >= 50:
        ver = "LA HISTERESIS"
    elif max(fr) < 20:
        ver = "EL UMBRAL"
    else:
        ver = "NO CONCLUYENTE con el criterio preregistrado"
    print("  H-Z5 -> el problema es: %s   [E1 %.1f %% | E2 %.1f %% | E3 %.1f %%]"
          % (ver, fr[0], fr[1], fr[2]))
    print()


# =============================================================================
def controles(runs):
    print("=" * 84)
    print("CONTROLES DE SANIDAD (regla 6: sanidad fisica antes de publicar)")
    print("=" * 84)
    print("  %-24s %11s %11s %11s %11s"
          % ("corrida", "|gz| rot1", "v_enc rot1", "|gz| rot<1", "v_enc rot<1"))
    for d in runs:
        m = val(d, AGE_BASE)
        r1 = m & (d["rot"] >= ROT1)
        r0 = m & (d["rot"] < ROT1)
        print("  %-24s %8.1f d/s %8.2f c/s %8.1f d/s %8.2f c/s"
              % (d["n"], np.mean(np.abs(d["gz"][r1])), np.mean(d["v_enc"][r1]),
                 np.mean(np.abs(d["gz"][r0])), np.mean(d["v_enc"][r0])))
    print()
    print("  Notas de procedencia (las CONFIGS SON DISTINTAS entre corridas):")
    for d in runs:
        print("    %-24s %s" % (d["n"], d["nota"]))
    print()


def main():
    runs = cargar_pista()
    n = sum(len(d["s"]) for d in runs)
    print()
    print("CORRIDAS DE PISTA: %d   muestras: %d   tiempo: %.1f s" % (len(runs), n, sec(n)))
    print()
    q1_histograma(runs)
    q2_episodios(runs)
    q3_viejo_vs_hoy(runs)
    q4_terminan_en_cero(runs)
    q5_pegajoso(runs)
    controles(runs)


if __name__ == "__main__":
    main()
