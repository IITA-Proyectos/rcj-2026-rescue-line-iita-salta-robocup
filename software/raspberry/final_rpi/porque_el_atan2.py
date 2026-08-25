# -*- coding: utf-8 -*-
"""
POR QUE EL atan2 DEJO DE TOMAR LAS CURVAS CERRADAS.

La pregunta de Benjamin, 25-ago: "toda mi vida probe con mi calculo de angulo
del atan2, por que ahora mismo ya dejo de hacer las curvas cerradas? no le da
tiempo? sentia que lo unico que le pasaba era que si sabia que tenia que girar
al otro lado ya tenia en cuenta su direccion".

LA INTUICION NO ES INGENUA, Y EL CODIGO LA RESPALDA
---------------------------------------------------
    x_black *= (1 - y_com)

Esa linea de Main.py pondera la componente horizontal por la ALTURA: los pixeles
de arriba -la cinta LEJANA, la que dice hacia donde va- pesan mas que los de
abajo -la cinta bajo el robot, la que dice donde estoy-. O sea que el atan2 SI
mira el rumbo, y a proposito. La pregunta no es si lo mira: es si puede
distinguirlo de la posicion.

LA HIPOTESIS QUE SE PONE A PRUEBA
---------------------------------
H-ATAN2: cuando la posicion y el rumbo apuntan a lados OPUESTOS, el atan2 los
promedia en un numero cuyo SIGNO depende de cuantos pixeles hay en cada fila.
Como eso cambia frame a frame, el comando se da vuelta SIN que ninguna de las
dos causas se haya dado vuelta. Eso es un ciclo limite, y no se arregla con mas
autoridad ni con mas velocidad de lazo.

FALSADORES, escritos antes de correr
------------------------------------
FA1  Si `e` y `psi` apuntan a lados opuestos en MENOS del 10 % de los frames,
     el conflicto es raro y no puede explicar una falla sistematica. MUERE.

FA2  Si las inversiones ESPURIAS del atan2 -cambia de signo sin que ni sign(e)
     ni sign(psi) cambien- son menos del 5 % de sus inversiones totales, el
     mecanismo no es el dominante y hay que buscar en latencia o cinematica.
     MUERE.

FA3  CONTROL. Si el fenomeno NO es mas frecuente en el tramo de FALLA
     (hist f1354-1490) que en el de EXITO (hist f580-679), entonces describe al
     sistema entero y no a la falla, y no explica por que se sale en las curvas
     cerradas. Es la prueba mas dura de las tres.

FA4  EL atan2 RESPONDE AL RUMBO?  Con el robot CENTRADO -donde el comando NO
     puede venir de la posicion-, si |atan2| crece monotonamente con |psi|,
     entonces el atan2 SI traduce rumbo a comando y no hay subcorreccion.
     Este falsador se agrego DESPUES de ver FA3, y se dice: mata una lectura
     mia, no una del equipo.

BANDA PREREGISTRADA para la banda muerta de signo: 5 / 10 / 15 / 20 grados.
Solo hay conclusion si el veredicto se sostiene en toda la banda.

============================ RESULTADO, 25-ago ============================

FA1  SOBREVIVE   43,0 % de 12.050 frames tienen `e` y `psi` a lados OPUESTOS
FA2  SOBREVIVE   65 a 73 % de las inversiones del atan2 son ESPURIAS -el
                 comando se da vuelta y la geometria no- en toda la banda
FA3  *** MUERE   el conflicto es MAS frecuente en el EXITO (47,0 %) que en la
                 FALLA (27,1 %). Razon 0,58x
FA4  *** MUERE   con el robot centrado, |atan2| CRECE monotonamente con |psi|:
                 26,7 -> 31,0 -> 39,3 -> 53,0 -> 63,9 -> 65,6 grados

LO QUE ESO SIGNIFICA, Y ES INCOMODO
-----------------------------------
El mecanismo EXISTE y es masivo, pero **no explica la falla**. Pasa igual o mas
en los tramos que salieron bien. Y la intuicion de Benjamin estaba bien: el
atan2 SI traduce rumbo a comando, monotonamente, y la ponderacion
`x_black *= (1 - y_com)` es lo que lo hace.

Fenomeno confirmado, causa de la falla NO. Son dos veredictos distintos y hay
que darlos por separado.

Lo que queda en pie como candidato, y esta medido en el traspaso 3.1: el lazo
del Teensy corria a 30 Hz descartando 3 de cada 4 tramas, con 65-70 ms de lag.
Eso ES "no le da tiempo", literal, sobre 7.673 periodos reales. Su fix esta
escrito y SIN PROBAR.

QUE ESTE BANCO NO PUEDE CONTESTAR
---------------------------------
"No le da tiempo" es una pregunta de LATENCIA y este banco no la mide: el
replay no tiene lazo. Los numeros de latencia ya estan medidos en el traspaso
(seccion 3.1) sobre 7.673 periodos reales del Teensy, y son de otra fuente.

    python porque_el_atan2.py
"""

import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ley_steer as LS                                        # noqa: E402
import sep_pos_rumbo as SP                                    # noqa: E402

BANDA_DEAD = (5.0, 10.0, 15.0, 20.0)
TRAMOS = [("hist_exito", "hist.avi", 580, 679),
          ("hist_falla", "hist.avi", 1354, 1490)]


def cargar_v2():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v2_at", os.path.join(AQUI, "nuevo_code_v2.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def serie_atan2(v2, video):
    cap = cv2.VideoCapture(os.path.join(AQUI, video))
    out = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        out.append(v2.atan2_actual(v2.frame_pi(fr)))
    cap.release()
    return out


def signo(v, dead):
    if v is None:
        return None
    return 1 if v > dead else (-1 if v < -dead else None)


def analizar(at, E, P, dead, dead_e, dead_p):
    """(inversiones, espurias, conflicto) sobre una serie alineada."""
    inv = esp = 0
    conflicto = 0
    n = 0
    ult = None
    ult_e = ult_p = None
    for a, e, p in zip(at, E, P):
        if e is None or p is None:
            continue
        n += 1
        se, sp_ = signo(e, dead_e), signo(p, dead_p)
        if se is not None and sp_ is not None and se != sp_:
            conflicto += 1
        sa = signo(a, dead)
        if sa is not None:
            if ult is not None and sa != ult:
                inv += 1
                # espuria: el comando se dio vuelta y la geometria NO
                giro_e = (ult_e is not None and se is not None and se != ult_e)
                giro_p = (ult_p is not None and sp_ is not None and sp_ != ult_p)
                if not giro_e and not giro_p:
                    esp += 1
            ult = sa
            if se is not None:
                ult_e = se
            if sp_ is not None:
                ult_p = sp_
    return n, inv, esp, conflicto


def main():
    v2 = cargar_v2()
    datos = SP.extraer()

    # e y psi por frame, de la descomposicion geometrica
    geo = {}
    for vid in SP.AUTONOMOS:
        if vid not in datos:
            continue
        geo[vid] = [LS.errores(f) if f["target"] is not None else (None, None)
                    for f in datos[vid]]

    print("")
    print("=" * 100)
    print("  FA1 - POSICION Y RUMBO, CUANTAS VECES TIRAN PARA LADOS OPUESTOS?")
    print("  Muere si es menos del 10 %: el conflicto seria raro y no explicaria")
    print("  una falla sistematica.")
    print("=" * 100)
    print("")
    qe = np.percentile([abs(e) for g in geo.values() for e, p in g
                        if e is not None], 25)
    qp = np.percentile([abs(p) for g in geo.values() for e, p in g
                        if p is not None], 25)
    print("  banda muerta: |e| < %.4f y |psi| < %.2f deg (p25 de cada uno) no"
          " cuentan" % (qe, qp))
    print("")
    print("  %-18s %8s %10s %10s" % ("video", "frames", "conflicto", "%"))
    tn = tc = 0
    ats = {}
    for vid in SP.AUTONOMOS:
        if vid not in geo:
            continue
        ats[vid] = serie_atan2(v2, vid)
        E = [e for e, p in geo[vid]]
        P = [p for e, p in geo[vid]]
        n, _i, _e, c = analizar(ats[vid], E, P, 10.0, qe, qp)
        tn += n
        tc += c
        print("  %-18s %8d %10d %9.1f %%" % (vid, n, c, 100.0 * c / max(n, 1)))
    print("")
    print("  TOTAL  %d frames, %d en conflicto (%.1f %%)  ->  %s"
          % (tn, tc, 100.0 * tc / max(tn, 1),
             "*** MUERE" if 100.0 * tc / max(tn, 1) < 10.0 else "SOBREVIVE"))

    print("")
    print("=" * 100)
    print("  FA2 - INVERSIONES ESPURIAS DEL atan2")
    print("  el comando se da vuelta y NI la posicion NI el rumbo se dieron")
    print("  vuelta. Muere si son menos del 5 % de las inversiones totales.")
    print("=" * 100)
    print("")
    print("  %-8s %10s %10s %10s   %s" % ("dead", "invers", "espurias", "%",
                                          "veredicto"))
    for dead in BANDA_DEAD:
        ti = te = 0
        for vid in ats:
            E = [e for e, p in geo[vid]]
            P = [p for e, p in geo[vid]]
            _n, i, e_, _c = analizar(ats[vid], E, P, dead, qe, qp)
            ti += i
            te += e_
        pc = 100.0 * te / max(ti, 1)
        print("  %-8.0f %10d %10d %9.1f %%   %s"
              % (dead, ti, te, pc, "*** MUERE" if pc < 5.0 else "SOBREVIVE"))

    print("")
    print("=" * 100)
    print("  FA3 - EL CONTROL, Y ES LA PRUEBA MAS DURA")
    print("  el fenomeno tiene que ser MAS frecuente en la FALLA que en el")
    print("  EXITO. Si no, describe al sistema entero y no a la falla.")
    print("=" * 100)
    print("")
    print("  %-16s %7s %9s %9s %9s %9s"
          % ("tramo", "frames", "conflicto", "%", "espurias", "% de inv"))
    res = {}
    for nom, vid, d0, d1 in TRAMOS:
        E = [e for e, p in geo[vid][d0:d1 + 1]]
        P = [p for e, p in geo[vid][d0:d1 + 1]]
        at = ats[vid][d0:d1 + 1]
        n, i, e_, c = analizar(at, E, P, 10.0, qe, qp)
        res[nom] = (n, i, e_, c)
        print("  %-16s %7d %9d %8.1f %% %9d %8.1f %%"
              % (nom, n, c, 100.0 * c / max(n, 1), e_,
                 100.0 * e_ / max(i, 1)))
    if "hist_falla" in res and "hist_exito" in res:
        nf, _if, ef, cf = res["hist_falla"]
        ne, _ie, ee, ce = res["hist_exito"]
        rf = 100.0 * cf / max(nf, 1)
        re = 100.0 * ce / max(ne, 1)
        print("")
        print("  conflicto en la falla %.1f %% contra %.1f %% en el exito"
              "  ->  razon %.2fx" % (rf, re, rf / max(re, 1e-9)))
        print("  FA3 -> %s" % ("SOBREVIVE" if rf > re else
                               "*** MUERE: no distingue la falla del exito"))
    print("")
    print("=" * 100)
    print("  FA4 - EL atan2 RESPONDE AL RUMBO?")
    print("  Solo con el robot CENTRADO: ahi el comando NO puede venir de la")
    print("  posicion, asi que lo que quede es respuesta al rumbo.")
    print("=" * 100)
    print("")
    A = []
    Pa = []
    Ea = []
    for vid in SP.AUTONOMOS:
        if vid not in ats:
            continue
        for f, a in zip(datos[vid], ats[vid]):
            if f["target"] is None:
                continue
            e, p = LS.errores(f)
            if e is None or p is None:
                continue
            A.append(abs(a))
            Pa.append(abs(p))
            Ea.append(abs(e))
    A, Pa, Ea = np.array(A), np.array(Pa), np.array(Ea)
    cen = Ea < np.percentile(Ea, 25)
    print("  n = %d, de los cuales centrados (|e| < p25 = %.3f): %d"
          % (len(A), np.percentile(Ea, 25), cen.sum()))
    print("")
    print("  %-14s %8s %11s %11s" % ("|psi| (deg)", "n", "|atan2| p50",
                                     "|atan2| p90"))
    bord = [0, 15, 30, 45, 60, 75, 90, 180]
    prev = None
    monot = True
    for lo, hi in zip(bord, bord[1:]):
        m = cen & (Pa >= lo) & (Pa < hi)
        if m.sum() < 25:
            continue
        v = float(np.percentile(A[m], 50))
        if prev is not None and v < prev - 1.0 and hi <= 90:
            monot = False
        prev = v
        print("  %-14s %8d %11.1f %11.1f"
              % ("%d - %d" % (lo, hi), m.sum(), v, np.percentile(A[m], 90)))
    print("")
    print("  crece monotonamente hasta psi=90: %s" % ("SI" if monot else "NO"))
    if monot:
        print("  FA4 -> *** MUERE: el atan2 SI traduce rumbo a comando.")
        print("         La intuicion de Benjamin estaba bien y no hay")
        print("         subcorreccion sistematica.")
    else:
        print("  FA4 -> SOBREVIVE: el comando no sigue al rumbo")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
