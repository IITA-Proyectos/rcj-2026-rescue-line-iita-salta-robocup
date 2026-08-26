# -*- coding: utf-8 -*-
"""
LENTE 3 - QUE PASA CON LA TRAYECTORIA FISICA ALREDEDOR DEL EVENTO `rxsteer == 0`.

Se mira el SENSOR, no el comando: el yaw desenvuelto del BNO055 y los encoders.

Benjamin, 26-ago: "para darte cuenta cuando se sale tienes que ver cuando
llegue desde la raspberry un angle de 90 o un steer=0; previo a esos angulos
son los que hacen que se salga".

=========================== FALSADOR, ESCRITO ANTES ==========================

H-T   los episodios de `rxsteer == 0` con comando FRESCO son el final de una
      CURVA: el robot venia girando y sale DERECHO.

PREDICCIONES EN NUMEROS (si H-T es cierta):
  A) mediana(|dyaw| en los W ms PREVIOS) / mediana(|dyaw| en los W ms POSTERIORES) >= 2,0
  B) fraccion de episodios con |dyaw_prev| >= UP grados Y |dyaw_post| <= UD grados
     con LIFT >= 1,5 contra la tasa base (instantes al azar de la misma corrida)
  C) la velocidad de avance POSTERIOR es MAYOR que la previa (sale derecho a fondo)

SE REFUTA si CUALQUIERA de estas:
  G1  la razon A cae por debajo de 2,0 en algun punto de la banda
  G2  el LIFT de B cae por debajo de 1,5 contra la tasa base, o contra el
      PLACEBO DESPLAZADO (el mismo test aplicado 3000 ms antes del episodio)
  G3  NO HAY PLATEAU: el veredicto cambia dentro de la banda preregistrada
  G4  n < 10 episodios frescos -> NO SE CONCLUYE NADA (potencia insuficiente)

BANDA PREREGISTRADA (se barre entera; no se elige un punto)
  duracion minima del episodio de steer=0     100, 200, 300 ms
  ventana W previa y posterior                1000, 1500, 2000 ms
  umbral de "comando FRESCO"  rxage <=         100, 200, 300 ms   (y rxage >= 0)
  umbral "giro antes"  UP                      30, 45, 60 grados
  umbral "recto despues" UD                    10, 20, 30 grados

POBLACIONES SEPARADAS, NO SE MEZCLAN  (control que importa)
  FRESCO   0 <= rxage <= umbral      la Pi dijo "centrado"
  VIEJO    rxage >= 700 ms           el watchdog ya disparo o esta por hacerlo
                                     (kWatchdogMs=400 + kWatchdogConfirmaMs=300)
  NUNCA    rxage == -1               nunca llego una trama en toda la corrida
  OJO: `rxage == -1` es MENOR que cualquier umbral. Un filtro `age < 200` sin
  `age >= 0` mete la poblacion NUNCA adentro de la FRESCA. Aca se excluye.

EVENTOS UNICOS, no muestras. Cada episodio cuenta UNA vez. Dos rachas separadas
por menos de 60 ms (menos de dos periodos de lazo) se funden en un episodio.

EL INDICE DE MUESTRA NO ES EL TIEMPO. El registro tiene huecos de hasta 61 s
(anillo lleno, `drop`). Todas las ventanas se toman por TIMESTAMP `us` y solo
dentro de un TRAMO CONTINUO (sin salto > 100 ms). Un episodio cuya ventana
+-W no entra entera en su tramo se DESCARTA.

CONTROL POSITIVO QUE NO SE PUEDE ROMPER: el giro por encoders
(v_der - v_izq)/b_eff tiene que correlacionar con `gz` del BNO, y la derivada
del yaw desenvuelto tiene que ser -gz. Si eso no da, el sensor no sirve y no
se publica nada.

LOS SIGNOS, MEDIDOS (26-ago, no supuestos):
  drivebase.cpp:210  `rotation >= 0` = girar a la IZQUIERDA, y ahi las ruedas
                     DERECHAS quedan a velocidad base -> dv = v_der - v_izq > 0
  gz  del BNO055     POSITIVO en el mismo sentido que dv (mismo criterio que
                     usa radio_minimo.py, control C1, 95-97 %)
  yaw del BNO055     es un RUMBO tipo brujula: AUMENTA en sentido HORARIO.
                     Medido: corr(d yaw/dt, gz) = -0,62 a -0,95, pendiente
                     -0,67 a -0,91. O sea  d yaw/dt = -gz.  Los dos sensores
                     dicen lo mismo con el signo cambiado. Como aca se usa
                     |dyaw|, el signo no cambia ningun numero, pero se deja
                     escrito para que nadie lo "arregle" al reves.

    python trayectoria_alrededor.py
"""

import glob
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import retardo_real as RR                                     # noqa: E402

DIAM_CM = 6.88                      # diametro efectivo de rodadura, 26-ago
CIRC_CM = np.pi * DIAM_CM           # 21,61 cm por vuelta
B_EFF_CM = 20.9                     # ancho de via efectivo MEDIDO, drivebase.h
RPM_A_CMS = CIRC_CM / 60.0          # 0,3602 cm/s por rpm

CORTE_TRAMO_MS = 100.0              # salto mayor a esto = tramo nuevo
FUNDIR_MS = 60.0                    # rachas mas juntas que esto = un episodio
PLACEBO_MS = 3000.0                 # desplazamiento del placebo
VIEJO_MS = 700.0                    # watchdog: 400 de stale + 300 de confirmacion

BANDA_DUR = (100, 200, 300)
BANDA_W = (1000, 1500, 2000)
BANDA_FRESCO = (100, 200, 300)
BANDA_UP = (30, 45, 60)
BANDA_UD = (10, 20, 30)

N_BASE = 400                        # instantes al azar por corrida para la tasa base
SEMILLA = 20260826


# ------------------------------------------------------------------ utilidades
def tramos_continuos(us):
    """Lista de (i0, i1) con `us` continuo (sin salto > CORTE_TRAMO_MS)."""
    d = np.diff(us) / 1000.0
    cortes = np.flatnonzero(d > CORTE_TRAMO_MS) + 1
    bordes = np.concatenate([[0], cortes, [len(us)]])
    return [(int(a), int(b)) for a, b in zip(bordes[:-1], bordes[1:]) if b - a > 1]


def vel_avance_cms(a):
    """Velocidad de avance del centro, cm/s, por encoders y con SIGNO.
    izquierda: dir 0 = adelante ; derecha: dir 1 = adelante."""
    fl = RR.col(a, "fl_rpm") * np.where(RR.col(a, "fl_dir") == 0, 1.0, -1.0)
    bl = RR.col(a, "bl_rpm") * np.where(RR.col(a, "bl_dir") == 0, 1.0, -1.0)
    fr = RR.col(a, "fr_rpm") * np.where(RR.col(a, "fr_dir") == 1, 1.0, -1.0)
    br = RR.col(a, "br_rpm") * np.where(RR.col(a, "br_dir") == 1, 1.0, -1.0)
    izq = (fl + bl) / 2.0
    der = (fr + br) / 2.0
    v = (izq + der) / 2.0 * RPM_A_CMS
    # giro por encoders, deg/s. drivebase.cpp:210: rot>=0 = izquierda y ahi las
    # ruedas DERECHAS van a velocidad base -> dv = v_der - v_izq, MISMO signo
    # que gz (es la convencion que valida radio_minimo.py con su control C1).
    w = (der - izq) * RPM_A_CMS / B_EFF_CM * 180.0 / np.pi
    return v, w


def yaw_desenvuelto(a):
    """yaw 0..360 (x10 en el CSV) desenvuelto, en grados, POR TRAMO."""
    y = RR.col(a, "yaw") / 10.0
    us = RR.col(a, "us")
    out = np.empty_like(y)
    for i0, i1 in tramos_continuos(us):
        out[i0:i1] = np.degrees(np.unwrap(np.radians(y[i0:i1])))
    return out


def episodios_us(mask, us, dur_min_ms):
    """Episodios UNICOS: rachas de `mask`, fundiendo huecos < FUNDIR_MS,
    con duracion >= dur_min_ms. Devuelve (i_ini, i_fin) indices."""
    m = mask.astype(np.int8)
    d = np.diff(np.concatenate([[0], m, [0]]))
    ini = list(np.flatnonzero(d == 1))
    fin = list(np.flatnonzero(d == -1))
    if not ini:
        return []
    fus_i, fus_f = [ini[0]], [fin[0]]
    for i, f in zip(ini[1:], fin[1:]):
        if (us[i] - us[fus_f[-1] - 1]) / 1000.0 < FUNDIR_MS:
            fus_f[-1] = f
        else:
            fus_i.append(i)
            fus_f.append(f)
    out = []
    for i, f in zip(fus_i, fus_f):
        if (us[f - 1] - us[i]) / 1000.0 >= dur_min_ms:
            out.append((int(i), int(f)))
    return out


def ventana(us, i, t_ini_ms, t_fin_ms, i0, i1):
    """Indices dentro de [us[i]+t_ini, us[i]+t_fin], acotados al tramo.
    Devuelve None si la ventana no entra ENTERA en el tramo."""
    t0 = us[i] + t_ini_ms * 1000.0
    t1 = us[i] + t_fin_ms * 1000.0
    if t0 < us[i0] or t1 > us[i1 - 1]:
        return None
    j0 = int(np.searchsorted(us[i0:i1], t0)) + i0
    j1 = int(np.searchsorted(us[i0:i1], t1)) + i0
    if j1 <= j0:
        return None
    return j0, j1


def dyaw(yw, us, i, W, i0, i1):
    """(|dyaw| previo, |dyaw| posterior) en grados, o None si no hay ventana."""
    a = ventana(us, i, -W, 0.0, i0, i1)
    b = ventana(us, i, 0.0, W, i0, i1)
    if a is None or b is None:
        return None
    return abs(yw[a[1] - 1] - yw[a[0]]), abs(yw[b[1] - 1] - yw[b[0]])


def dyaw_firmado(yw, us, i, W, i0, i1):
    """(dyaw previo CON SIGNO, dyaw posterior CON SIGNO, TV previa, TV post).
    TV = variacion total = suma de |dyaw| muestra a muestra. Un giro sostenido
    da TV ~ |dyaw|; una oscilacion da TV grande con |dyaw| chico."""
    a = ventana(us, i, -W, 0.0, i0, i1)
    b = ventana(us, i, 0.0, W, i0, i1)
    if a is None or b is None:
        return None
    return (yw[a[1] - 1] - yw[a[0]], yw[b[1] - 1] - yw[b[0]],
            float(np.abs(np.diff(yw[a[0]:a[1]])).sum()),
            float(np.abs(np.diff(yw[b[0]:b[1]])).sum()))


# ------------------------------------------------------------------ carga
def cargar_todo():
    rutas = [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
             if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")]
    D = {}
    for r in rutas:
        a, nota = RR.cargar(r)
        if a is None or len(a) < 500:
            continue
        n = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        v, w = vel_avance_cms(a)
        D[n] = dict(us=RR.col(a, "us"), steer=RR.col(a, "rxsteer") / 1000.0,
                    age=RR.col(a, "rxage"), speed=RR.col(a, "rxspeed"),
                    rot=RR.col(a, "rot") / 1000.0, ls=RR.col(a, "ls"),
                    rs=RR.col(a, "rs"), gz=RR.col(a, "gz") / 10.0,
                    yw=yaw_desenvuelto(a), v=v, wenc=w,
                    tramos=tramos_continuos(RR.col(a, "us")), nota=nota)
    return D


# ------------------------------------------------------------------ 0. control
def control_positivo(D):
    print("")
    print("=" * 104)
    print("  0. CONTROL POSITIVO   el sensor sirve?   encoders vs BNO055")
    print("=" * 104)
    print("")
    print("  C-A  encoders (v_der - v_izq)/b_eff  CONTRA  gz del BNO, con lag 14 muestras")
    print("  C-B  d(yaw)/dt  CONTRA  -gz          (yaw es rumbo horario; gz es CCW)")
    print("  C-C  b_eff implicito = |dv| / |gz|   tiene que dar cerca de 20,9 cm")
    print("")
    print("  %-30s %9s %8s %10s %8s %10s %10s"
          % ("corrida", "corr C-A", "pend", "corr C-B", "pend", "b_eff cm", "|gz| p99"))
    LAG = 14                                   # 70 ms, medido en retardo_real.py
    for n, d in D.items():
        gz, we = d["gz"], d["wenc"]
        m = (np.abs(we[:-LAG]) > 5) | (np.abs(gz[LAG:]) > 5)
        cA = float(np.corrcoef(we[:-LAG][m], gz[LAG:][m])[0, 1])
        pA = float(np.polyfit(we[:-LAG][m], gz[LAG:][m], 1)[0])
        # derivada del yaw sobre 100 ms, por tramo
        dyr = np.full(len(d["us"]), np.nan)
        us = d["us"]
        for i0, i1 in d["tramos"]:
            k = 20
            if i1 - i0 > 2 * k + 2:
                num = d["yw"][i0 + 2 * k:i1] - d["yw"][i0:i1 - 2 * k]
                den = (us[i0 + 2 * k:i1] - us[i0:i1 - 2 * k]) / 1e6
                dyr[i0 + k:i1 - k] = num / den
        mb = np.isfinite(dyr) & ((np.abs(gz) > 5) | (np.abs(dyr) > 5))
        cB = float(np.corrcoef(dyr[mb], -gz[mb])[0, 1])
        pB = float(np.polyfit(-gz[mb], dyr[mb], 1)[0])
        dv = we * B_EFF_CM * np.pi / 180.0     # vuelve a cm/s
        sel = m & (np.abs(gz[LAG:]) > 20) & (np.abs(dv[:-LAG]) > 3)
        beff = (np.median(np.abs(dv[:-LAG][sel])
                          / (np.abs(gz[LAG:][sel]) * np.pi / 180.0))
                if sel.sum() > 50 else float("nan"))
        print("  %-30s %9.3f %8.2f %10.3f %8.2f %10.2f %10.0f"
              % (n[:30], cA, pA, cB, pB, beff, np.percentile(np.abs(gz), 99)))
    print("")
    print("  C-A positiva y C-B positiva = los tres sensores cuentan la misma historia.")
    print("  Como abajo se usa |dyaw| (valor absoluto), el signo no mueve ningun numero,")
    print("  pero si C-B hubiera dado ~0 el yaw no serviria y no se publicaria nada.")
    print("")
    print("  C-D  SANIDAD FISICA: techo de giro que la traccion PUEDE dar.")
    print("       peor caso rot=1: dv = 2*vel -> omega = dv/b_eff. Lo que pase de ahi")
    print("       no lo hicieron los motores (golpe, mano, o pico del giroscopio).")
    print("")
    print("  %-30s %10s %12s %11s %11s"
          % ("corrida", "ls|rs max", "techo d/s", "|gz|>techo", "|gz|>2xtecho"))
    for n, d in D.items():
        vmax = max(d["ls"].max(), d["rs"].max())
        wmax = (2 * vmax * RPM_A_CMS) / B_EFF_CM * 180.0 / np.pi
        g = np.abs(d["gz"])
        print("  %-30s %10.0f %12.0f %10.1f %% %10.1f %%"
              % (n[:30], vmax, wmax, 100 * (g > wmax).mean(),
                 100 * (g > 2 * wmax).mean()))


# ------------------------------------------------------------------ 1. censo
def censo(D):
    print("")
    print("=" * 104)
    print("  1. CENSO DE POBLACIONES   cuantos steer=0 hay y de que tipo, POR CORRIDA")
    print("=" * 104)
    print("")
    print("  %-30s %7s %9s %8s %10s %10s %10s %10s"
          % ("corrida", "n", "dur s", "tramos", "steer=0", "rxage p50",
             "rxage p90", "rxage max"))
    for n, d in D.items():
        us, m = d["us"], d["steer"] == 0
        dur = sum((us[b - 1] - us[a]) for a, b in d["tramos"]) / 1e6
        ag = d["age"][m]
        print("  %-30s %7d %9.1f %8d %8.1f %% %10.0f %10.0f %10.0f"
              % (n[:30], len(us), dur, len(d["tramos"]), 100 * m.mean(),
                 np.median(ag), np.percentile(ag, 90), ag.max()))
    print("")
    print("  reparto de las MUESTRAS con steer=0 por poblacion (umbral fresco = 200 ms):")
    print("")
    print("  %-30s %12s %12s %12s %12s"
          % ("corrida", "FRESCO", "medio", "VIEJO>=700", "NUNCA(-1)"))
    for n, d in D.items():
        m = d["steer"] == 0
        ag = d["age"][m]
        tot = max(len(ag), 1)
        fr = int(((ag >= 0) & (ag <= 200)).sum())
        vi = int((ag >= VIEJO_MS).sum())
        nu = int((ag < 0).sum())
        me = tot - fr - vi - nu
        print("  %-30s %12d %12d %12d %12d" % (n[:30], fr, me, vi, nu))


# ------------------------------------------------------------------ 2. episodios
def clasificar(d, fresco_ms):
    ag = d["age"]
    z = d["steer"] == 0
    return {"FRESCO": z & (ag >= 0) & (ag <= fresco_ms),
            "VIEJO": z & (ag >= VIEJO_MS),
            "NUNCA": z & (ag < 0)}


def recolectar(D, dur, W, fresco):
    """Devuelve {clase: [dict por episodio]}, conteo por corrida y DESCARTES."""
    out = {"FRESCO": [], "VIEJO": [], "NUNCA": []}
    porcor = {}
    desc = {"FRESCO": 0, "VIEJO": 0, "NUNCA": 0}
    for n, d in D.items():
        us = d["us"]
        cl = clasificar(d, fresco)
        porcor[n] = {}
        for clase, mask in cl.items():
            cnt = 0
            for i0, i1 in d["tramos"]:
                sub = np.zeros(len(us), bool)
                sub[i0:i1] = mask[i0:i1]
                for i, f in episodios_us(sub, us, dur):
                    r = dyaw(d["yw"], us, i, W, i0, i1)
                    if r is None:
                        desc[clase] += 1        # sin ventana +-W entera
                        continue
                    fw = dyaw_firmado(d["yw"], us, i, W, i0, i1)
                    pv = ventana(us, i, -W, 0.0, i0, i1)
                    po = ventana(us, i, 0.0, W, i0, i1)
                    jp = int(np.searchsorted(us[i0:i1],
                                             us[i] - PLACEBO_MS * 1000.0)) + i0
                    rp = dyaw(d["yw"], us, jp, W, i0, i1) if jp > i0 else None
                    dist = float(np.trapezoid(d["v"][po[0]:po[1]],
                                          us[po[0]:po[1]] / 1e6))
                    out[clase].append(dict(
                        corrida=n, i=i, f=f,
                        t_s=(us[i] - us[0]) / 1e6,
                        dur_ms=(us[f - 1] - us[i]) / 1000.0,
                        dprev=r[0], dpost=r[1],
                        sprev=fw[0], spost=fw[1], tvprev=fw[2], tvpost=fw[3],
                        mismo=1.0 if (fw[0] * fw[1]) > 0 else 0.0,
                        pbo_prev=rp[0] if rp else np.nan,
                        pbo_post=rp[1] if rp else np.nan,
                        v_prev=float(np.mean(d["v"][pv[0]:pv[1]])),
                        v_epi=float(np.mean(d["v"][i:f])),
                        v_post=float(np.mean(d["v"][po[0]:po[1]])),
                        cm_post=dist,
                        cm_epi=float(np.trapezoid(d["v"][i:f], us[i:f] / 1e6)),
                        rot_epi=float(np.mean(np.abs(d["rot"][i:f]))),
                        rot_prev=float(np.mean(np.abs(d["rot"][pv[0]:pv[1]]))),
                        piv_prev=float(np.mean(np.abs(d["rot"][pv[0]:pv[1]]) >= 0.999)),
                        rot_ini=float(abs(d["rot"][i])),
                        igual=float(np.mean(d["ls"][i:f] == d["rs"][i:f])),
                        spd=float(np.median(d["speed"][i:f])),
                        ls=float(np.median(d["ls"][i:f])),
                        rs=float(np.median(d["rs"][i:f]))))
                    cnt += 1
            porcor[n][clase] = cnt
    return out, porcor, desc


def tasa_base(D, W, up, ud, rng):
    """Tasa base: mismo test 'giro antes / recto despues' en instantes al azar."""
    ok = tot = 0
    for n, d in D.items():
        us = d["us"]
        for i0, i1 in d["tramos"]:
            k = int(N_BASE * (i1 - i0) / len(us))
            if k <= 0:
                continue
            for i in rng.integers(i0, i1, size=k):
                r = dyaw(d["yw"], us, int(i), W, i0, i1)
                if r is None:
                    continue
                tot += 1
                if r[0] >= up and r[1] <= ud:
                    ok += 1
    return (ok / tot if tot else float("nan")), tot


# ------------------------------------------------------------------ main
def main():
    D = cargar_todo()
    if not D:
        print("  no hay corridas de pista")
        return 1

    print("")
    print("=" * 104)
    print("  LENTE 3   TRAYECTORIA FISICA ALREDEDOR DE `rxsteer == 0`")
    print("  yaw desenvuelto del BNO055 + encoders. Falsador preregistrado en el docstring.")
    print("  %d corridas de pista del 22-ago" % len(D))
    print("=" * 104)

    control_positivo(D)
    censo(D)

    print("")
    print("=" * 104)
    print("  2. EPISODIOS UNICOS POR CORRIDA Y CLASE  (dur>=200 ms, W=2000 ms, fresco<=200 ms)")
    print("     un episodio solo cuenta si su ventana +-2 s entra ENTERA en un tramo continuo")
    print("=" * 104)
    eps, porcor, desc = recolectar(D, 200, 2000, 200)
    eps100, porcor100, desc100 = recolectar(D, 100, 2000, 200)
    print("")
    print("  %-30s %10s %10s %10s %6s %10s %10s"
          % ("corrida", "FRESCO", "VIEJO>=700", "NUNCA(-1)", "|", "FRESCO 100",
             "VIEJO 100"))
    for n in D:
        p, q = porcor[n], porcor100[n]
        print("  %-30s %10d %10d %10d %6s %10d %10d"
              % (n[:30], p["FRESCO"], p["VIEJO"], p["NUNCA"], "|",
                 q["FRESCO"], q["VIEJO"]))
    print("  %-30s %10d %10d %10d %6s %10d %10d"
          % ("TOTAL", len(eps["FRESCO"]), len(eps["VIEJO"]), len(eps["NUNCA"]),
             "|", len(eps100["FRESCO"]), len(eps100["VIEJO"])))
    print("")
    print("  DESCARTADOS por no tener la ventana +-2 s entera dentro del tramo:")
    print("     dur>=200 ms  FRESCO %d   VIEJO %d   NUNCA %d"
          % (desc["FRESCO"], desc["VIEJO"], desc["NUNCA"]))
    print("     dur>=100 ms  FRESCO %d   VIEJO %d   NUNCA %d"
          % (desc100["FRESCO"], desc100["VIEJO"], desc100["NUNCA"]))
    print("  (los NUNCA(-1) caen casi todos al ARRANQUE de la corrida, antes de que")
    print("   llegue la primera trama, y por eso no tienen 2 s previos que mirar.)")

    for clase in ("FRESCO", "VIEJO", "NUNCA"):
        E = eps[clase]
        print("")
        print("-" * 104)
        print("  3. TRAYECTORIA  clase %s   n = %d episodios" % (clase, len(E)))
        print("-" * 104)
        if not E:
            print("     ninguno.")
            continue
        if len(E) < 10:
            print("     *** n < 10: SE LISTAN TODOS, NO SE CONCLUYE NADA ***")
        print("")
        print("  %-25s %6s %6s %7s %7s %6s %6s %6s %6s %6s %6s %6s %5s"
              % ("corrida", "t s", "dur ms", "dyaw-", "dyaw+", "TV-", "TV+",
                 "v_prev", "v_epi", "v_post", "cm 2s", "rotpre", "ls=rs"))
        for e in sorted(E, key=lambda x: (x["corrida"], x["i"]))[:45]:
            print("  %-25s %6.1f %6.0f %7.1f %7.1f %6.0f %6.0f %6.1f %6.1f"
                  " %6.1f %6.1f %6.2f %4.0f%%"
                  % (e["corrida"][:25], e["t_s"], e["dur_ms"], e["sprev"],
                     e["spost"], e["tvprev"], e["tvpost"], e["v_prev"],
                     e["v_epi"], e["v_post"], e["cm_post"], e["rot_prev"],
                     100 * e["igual"]))
        if len(E) > 45:
            print("  ... (%d mas)" % (len(E) - 45))

        def g(k):
            return np.array([x[k] for x in E], float)

        print("")
        print("     dyaw CON SIGNO: + es giro a izquierda (gz>0 / yaw decreciente).")
        print("     TV = variacion total del yaw en la ventana (oscilar suma, girar tambien).")
        print("")
        print("     MEDIANAS   |dyaw|prev %.1f deg   |dyaw|post %.1f deg   razon A %.2f"
              % (np.median(g("dprev")), np.median(g("dpost")),
                 np.median(g("dprev")) / max(np.median(g("dpost")), 1e-6)))
        print("     TV         TVprev %.1f deg   TVpost %.1f deg   razon TV %.2f"
              % (np.median(g("tvprev")), np.median(g("tvpost")),
                 np.median(g("tvprev")) / max(np.median(g("tvpost")), 1e-6)))
        sp = g("tvprev") / np.maximum(np.abs(g("sprev")), 1.0)
        sq = g("tvpost") / np.maximum(np.abs(g("spost")), 1.0)
        print("     SINUOSIDAD TV/|dyaw|  antes %.1f   despues %.1f   (1 = curva limpia;"
              " >3 = va y viene)" % (np.median(sp), np.median(sq)))
        print("                mas sinuoso ANTES que despues en %.0f %% de los episodios (n=%d)"
              % (100 * np.mean(sp > sq), len(E)))
        print("     SENTIDO    sigue girando para el MISMO lado despues: %.0f %% de los episodios"
              % (100 * np.mean(g("mismo"))))
        print("     PLACEBO -3 s  |dyaw|prev %.1f   |dyaw|post %.1f"
              % (np.nanmedian(g("pbo_prev")), np.nanmedian(g("pbo_post"))))
        print("     VELOCIDAD  v_prev %.1f   v_epi %.1f   v_post %.1f cm/s"
              % (np.median(g("v_prev")), np.median(g("v_epi")),
                 np.median(g("v_post"))))
        print("                avance DURANTE el episodio %.1f cm   en los 2 s POSTERIORES %.1f cm"
              % (np.median(g("cm_epi")), np.median(g("cm_post"))))
        print("     METRICA C  v_post > v_prev en %.0f %% de los episodios; v_epi > v_prev en %.0f %%"
              % (100 * np.mean(g("v_post") > g("v_prev")),
                 100 * np.mean(g("v_epi") > g("v_prev"))))
        print("     DERECHO?   ls==rs durante el episodio %.0f %%   |rot| medio en el episodio %.2f"
              % (100 * np.mean(g("igual")), np.median(g("rot_epi"))))
        print("                rxspeed p50 %.0f   ls p50 %.0f   rs p50 %.0f"
              % (np.median(g("spd")), np.median(g("ls")), np.median(g("rs"))))
        print("     ANTES      |rot| medio en los 2 s previos %.2f   fraccion con pivote"
              " enganchado (|rot|=1) %.0f %%"
              % (np.median(g("rot_prev")), 100 * np.median(g("piv_prev"))))

    print("")
    print("=" * 104)
    print("  4. BARRIDO DE LA BANDA PREREGISTRADA   solo clase FRESCO")
    print("     metrica A = razon de medianas |dyaw|prev / |dyaw|post   (falsador: >= 2,0)")
    print("=" * 104)
    print("")
    print("  %6s %6s %8s %8s %10s %10s %9s %10s"
          % ("dur", "W", "fresco", "n epis", "med prev", "med post", "razon A",
             "razon pbo"))
    razones = []
    for dur in BANDA_DUR:
        for W in BANDA_W:
            for fr in BANDA_FRESCO:
                E2, _, _ = recolectar(D, dur, W, fr)
                E2 = E2["FRESCO"]
                if len(E2) < 3:
                    print("  %6d %6d %8d %8d          -          -         -          -"
                          % (dur, W, fr, len(E2)))
                    continue
                dp = np.array([x["dprev"] for x in E2])
                dq = np.array([x["dpost"] for x in E2])
                pp = np.array([x["pbo_prev"] for x in E2], float)
                pq = np.array([x["pbo_post"] for x in E2], float)
                A = np.median(dp) / max(np.median(dq), 1e-6)
                P = np.nanmedian(pp) / max(np.nanmedian(pq), 1e-6)
                razones.append((dur, W, fr, len(E2), A, P))
                print("  %6d %6d %8d %8d %10.1f %10.1f %9.2f %10.2f"
                      % (dur, W, fr, len(E2), np.median(dp), np.median(dq), A, P))

    print("")
    print("=" * 104)
    print("  5. METRICA B (EVENTO UNICO)   giro >= UP antes  Y  <= UD despues")
    print("     contra TASA BASE (instantes al azar) y contra PLACEBO (-3 s)")
    print("     dur = 200 ms, W = 2000 ms, fresco <= 200 ms")
    print("=" * 104)
    EF = eps["FRESCO"]
    print("")
    print("  %6s %6s %8s %10s %10s %9s %11s %10s"
          % ("UP", "UD", "n epis", "p epis", "p base", "lift", "p placebo",
             "lift pbo"))
    lifts = []
    ntb = 0
    for up in BANDA_UP:
        for ud in BANDA_UD:
            base, ntb = tasa_base(D, 2000, up, ud, np.random.default_rng(SEMILLA))
            if not EF:
                print("  %6d %6d %8d %10s %9.1f%% %9s %11s %10s"
                      % (up, ud, 0, "-", 100 * base, "-", "-", "-"))
                continue
            dp = np.array([x["dprev"] for x in EF])
            dq = np.array([x["dpost"] for x in EF])
            pp = np.array([x["pbo_prev"] for x in EF], float)
            pq = np.array([x["pbo_post"] for x in EF], float)
            p = float(np.mean((dp >= up) & (dq <= ud)))
            ok = np.isfinite(pp) & np.isfinite(pq)
            pb = float(np.mean((pp[ok] >= up) & (pq[ok] <= ud))) if ok.sum() else np.nan
            lift = p / base if base > 0 else float("inf")
            liftp = p / pb if (np.isfinite(pb) and pb > 0) else float("inf")
            lifts.append((up, ud, len(EF), p, base, lift, pb, liftp))
            print("  %6d %6d %8d %9.1f%% %9.1f%% %9s %10.1f%% %10s"
                  % (up, ud, len(EF), 100 * p, 100 * base,
                     ("%.2f" % lift) if np.isfinite(lift) else "inf",
                     100 * pb if np.isfinite(pb) else float("nan"),
                     ("%.2f" % liftp) if np.isfinite(liftp) else "inf"))
    print("")
    print("  (tasa base sobre %d instantes al azar con ventana completa)" % ntb)

    # -------- 5b. perfil disparado por el evento -----------------------------
    print("")
    print("=" * 104)
    print("  5b. PERFIL DISPARADO POR EL EVENTO   mediana sobre los %d episodios FRESCOS"
          % len(eps["FRESCO"]))
    print("      t = 0 es el arranque del episodio de steer=0. Bins de 250 ms.")
    print("      DESCRIPTIVO: con n = %d no se concluye, se muestra la forma."
          % len(eps["FRESCO"]))
    print("=" * 104)
    print("")
    print("  %10s %10s %10s %10s %10s"
          % ("t (ms)", "v cm/s", "|gz| d/s", "|rot|", "|rxsteer|"))
    BIN = 250
    for t in range(-2000, 2000, BIN):
        acc = {"v": [], "gz": [], "rot": [], "st": []}
        for e in eps["FRESCO"]:
            d = D[e["corrida"]]
            us = d["us"]
            i0, i1 = next((a, b) for a, b in d["tramos"] if a <= e["i"] < b)
            w = ventana(us, e["i"], t, t + BIN, i0, i1)
            if w is None:
                continue
            acc["v"].append(np.mean(d["v"][w[0]:w[1]]))
            acc["gz"].append(np.mean(np.abs(d["gz"][w[0]:w[1]])))
            acc["rot"].append(np.mean(np.abs(d["rot"][w[0]:w[1]])))
            acc["st"].append(np.mean(np.abs(d["steer"][w[0]:w[1]])))
        if not acc["v"]:
            continue
        marca = "  <-- t=0" if t == 0 else ""
        print("  %10d %10.1f %10.1f %10.2f %10.2f%s"
              % (t, np.median(acc["v"]), np.median(acc["gz"]),
                 np.median(acc["rot"]), np.median(acc["st"]), marca))

    # -------- 6. sesgo de supervivencia -------------------------------------
    print("")
    print("=" * 104)
    print("  6. SESGO DE SUPERVIVENCIA   los episodios que MAS importan pueden ser")
    print("     justo los que el filtro de ventana +-2 s tira. Si el robot se fue de")
    print("     la pista, la corrida SE CORTA y no hay 2 s posteriores que mirar.")
    print("     Aca se cuentan TODOS los episodios frescos SIN pedir ventana.")
    print("=" * 104)
    print("")
    print("  %-30s %8s %9s %9s %9s %10s %11s"
          % ("corrida", "n sin", "dur p50", "dur p90", "dur max",
             "ult 3 s?", "steer=0 fr."))
    tot_sin = tot_ult = 0
    todas_dur = []
    for n, d in D.items():
        us = d["us"]
        cl = clasificar(d, 200)["FRESCO"]
        durs, ult = [], 0
        for i0, i1 in d["tramos"]:
            sub = np.zeros(len(us), bool)
            sub[i0:i1] = cl[i0:i1]
            for i, f in episodios_us(sub, us, 200):
                durs.append((us[f - 1] - us[i]) / 1000.0)
                if (us[i1 - 1] - us[f - 1]) / 1e6 < 3.0:
                    ult += 1
        dfr = sum((us[b - 1] - us[a]) for a, b in d["tramos"]) / 1e6
        frac = 100.0 * cl.sum() * 0.005 / max(dfr, 1e-9)
        tot_sin += len(durs)
        tot_ult += ult
        todas_dur += durs
        print("  %-30s %8d %8.0f %8.0f %8.0f %10d %10.1f %%"
              % (n[:30], len(durs),
                 np.percentile(durs, 50) if durs else float("nan"),
                 np.percentile(durs, 90) if durs else float("nan"),
                 max(durs) if durs else float("nan"), ult, frac))
    print("  %-30s %8d %8.0f %8.0f %8.0f %10d"
          % ("TOTAL", tot_sin,
             np.percentile(todas_dur, 50) if todas_dur else float("nan"),
             np.percentile(todas_dur, 90) if todas_dur else float("nan"),
             max(todas_dur) if todas_dur else float("nan"), tot_ult))
    print("")
    print("  n sin        = episodios frescos de >= 200 ms SIN exigir ventana +-2 s")
    print("  ult 3 s?     = cuantos de esos caen en los ultimos 3 s de su tramo")
    print("  steer=0 fr.  = %% del tiempo de la corrida con steer=0 Y comando fresco")

    print("")
    print("=" * 104)
    print("  7. VEREDICTO CONTRA EL FALSADOR")
    print("=" * 104)
    print("")
    nF = len(EF)
    print("  G4  n < 10 episodios FRESCOS ................... n = %d  -> %s"
          % (nF, "SE CUMPLE: NO SE CONCLUYE" if nF < 10 else "no"))
    if razones:
        As = [r[4] for r in razones if r[3] >= 3]
        print("  G1  razon A < 2,0 en algun punto de la banda ... min %.2f  max %.2f  -> %s"
              % (min(As), max(As), "SE CUMPLE -> REFUTA" if min(As) < 2.0 else "no"))
        print("  G3  el veredicto de A cambia dentro de la banda  -> %s"
              % ("SE CUMPLE -> SIN PLATEAU" if (min(As) < 2.0) != (max(As) < 2.0)
                 else "no"))
    if lifts:
        L = [x[5] for x in lifts if np.isfinite(x[5])]
        Lp = [x[7] for x in lifts if np.isfinite(x[7])]
        if L:
            print("  G2  lift < 1,5 contra tasa base ................ min %.2f  max %.2f  -> %s"
                  % (min(L), max(L), "SE CUMPLE -> REFUTA" if min(L) < 1.5 else "no"))
        if Lp:
            print("      lift < 1,5 contra placebo .................. min %.2f  max %.2f  -> %s"
                  % (min(Lp), max(Lp), "SE CUMPLE -> REFUTA" if min(Lp) < 1.5 else "no"))
    print("")
    print("=" * 104)
    return 0


if __name__ == "__main__":
    sys.exit(main())
