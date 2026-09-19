# -*- coding: utf-8 -*-
"""
PROBAR LAS CINCO SOLUCIONES OFFLINE, CONTRA EL DRIVEBASE, SIN ROBOT.

Benjamin, 26-ago: "podriamos probar aqui offline como hubiese reaccionado con el
drivebase y con las soluciones".

Se puede, y esto lo hace. La idea es simple: el `steer` que la Pi mando quedo
grabado en los CSV. Cada solucion es una funcion `steer -> rot` distinta. Y de
`rot` sale TODO lo demas por algebra del drivebase:

    v_centro  = vel * (1 - rot)                  drivebase.cpp:212-215
    R_pedido  = b_eff * (1 - rot) / (2 * rot)
    R_trazado = R_pedido * APERTURA              el robot se abre

Asi que se puede correr las cinco leyes sobre el MISMO steer real y comparar.

======================== LO QUE ESTO **NO** PUEDE HACER =======================

ES LAZO ABIERTO, y hay que decirlo fuerte porque es la trampa de siempre:

    Se le da a las cinco leyes el `steer` que la Pi mando MIENTRAS CORRIA OTRA
    LEY. Si el robot se hubiera movido distinto, la camara habria visto otra
    cosa y la Pi habria mandado otro steer.

O sea que esto caracteriza **EL MAPEO**, no una corrida. Sirve para:
    * ver que radio pide cada ley sobre la distribucion REAL de angulos
    * detectar que una ley pide radios imposibles o que no avanza
    * ordenar las candidatas antes de gastar sabado
NO sirve para decir "con esta ley el robot habria tomado la curva".

Y OTRA COSA, que Benjamin marco el 26-ago y cambia la lectura:

    HOY EL ROBOT NO CORRE CON EL PLANNER, CORRE CON EL `atan2` DE SIEMPRE.
    Main.py:41-44 -- sin la variable de entorno VISION_LINEA el modulo nuevo
    no se activa. Asi que el `steer` de estos CSV es el del atan2.

Si despues se enciende el planner, la DISTRIBUCION de steer cambia, y con ella
cambian los numeros de abajo. Por eso el script acepta --csv para correr sobre
una corrida nueva, y por eso la telemetria de la Pi tiene `ang_viejo`: con el
planner encendido, una sola corrida da las dos leyes a la vez.

    python simular_leyes.py
    python simular_leyes.py --apertura 1.15 --beff 20.9
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

GAIN = 1.35        # LINE_STEER_GAIN
EXP = 0.50         # LINE_ROT_EXP
PIVOT = 0.92       # LINE_PIVOT_STEER (en absSteer)
ENTRA = 0.60       # LINE_PIVOTE_ENTRA
SALE = 0.15        # LINE_PIVOTE_SALE


# ---------------------------------------------------------------- las leyes --
#  Cada una recibe |steer| en [0,1] y el estado del pivote, y devuelve `rot`.
#  Son las CINCO de docs/tareas/cuatro-soluciones.md del repo de Roboliga.

def ley_hoy(s, piv, piso=0.710):
    ab = np.minimum(s * GAIN, 1.0)
    rot = np.where(piv | (ab >= PIVOT), 1.0, ab ** EXP)
    return np.minimum(rot, 1.0)


def ley_gap(s, piv, piso=0.710):
    """BASE - el gap suelta el pivote. `piv` ya viene calculado con esa regla,
    asi que aca la ley es la de hoy: lo que cambia es el ESTADO."""
    return ley_hoy(s, piv)


def ley_mateo(s, piv, piso=0.710):
    """MATEO - rehacer la curva steer -> rot. Saca la ganancia y escala."""
    return np.minimum(piso * np.sqrt(s), piso)


def ley_laureano(s, piv, piso=0.710, beff=20.9):
    """LAUREANO - pedir RADIO en cm. Mapea |steer| a un radio entre R_MAX
    (casi recto) y R_MIN, y convierte con rot = b_eff/(2R + b_eff)."""
    R_MAX, R_MIN = 60.0, 4.26         # 4.26 pedido traza 4.9 con apertura 1.15
    R = R_MAX - (R_MAX - R_MIN) * np.sqrt(s)
    R = np.maximum(R, R_MIN)
    return beff / (2.0 * R + beff)


def ley_lucio(s, piv, piso=0.710):
    """LUCIO - soltar el pivote antes. La ley es la de hoy pero el pivote
    NO es pegajoso: sale apenas el comando baja de ENTRA."""
    ab = np.minimum(s * GAIN, 1.0)
    return np.minimum(np.where(ab >= PIVOT, 1.0, ab ** EXP), 1.0)


def ley_benjamin(s, piv, piso=0.710):
    """BENJAMIN - que el pivote AVANCE en la region de memoria."""
    ab = np.minimum(s * GAIN, 1.0)
    rot = np.where(piv, 1.0, ab ** EXP)
    mem = piv & (ab < ENTRA) & (ab < PIVOT)
    rot = np.where(mem, np.maximum(ab ** EXP, piso), rot)
    rot = np.where(ab >= PIVOT, 1.0, rot)
    return np.minimum(rot, 1.0)


LEYES = (
    ("HOY (lo que corre)", ley_hoy, "pegajoso"),
    ("BASE  gap suelta piv", ley_gap, "gap"),
    ("MATEO  remapeo", ley_mateo, "pegajoso"),
    ("LAUREANO  radio cm", ley_laureano, "pegajoso"),
    ("LUCIO  suelta antes", ley_lucio, "sin_memoria"),
    ("BENJAMIN  piv avanza", ley_benjamin, "pegajoso"),
)


def estado_pivote(ab, modo, steer_crudo):
    """Reproduce la maquina de estados de main.cpp:3775-3810."""
    piv = np.zeros(len(ab), bool)
    e = False
    for i in range(len(ab)):
        if not e and ab[i] >= ENTRA:
            e = True
        elif e:
            if modo == "sin_memoria":
                if ab[i] < ENTRA:
                    e = False
            elif modo == "gap":
                # el gap (steer == 0 exacto) suelta el pivote
                if ab[i] <= SALE or steer_crudo[i] == 0.0:
                    e = False
            else:
                if ab[i] <= SALE:
                    e = False
        piv[i] = e
    return piv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beff", type=float, default=20.9)
    ap.add_argument("--apertura", type=float, default=1.15)
    ap.add_argument("--piso", type=float, default=0.710)
    ap.add_argument("--csv", default=None, help="una corrida puntual")
    a = ap.parse_args()

    rutas = ([a.csv] if a.csv else
             [r for r in sorted(glob.glob(os.path.join(RR.CORRIDAS, "*.csv")))
              if os.path.basename(r).replace("2026-08-22_", "").startswith("pista")])

    S, V = [], []
    for r in rutas:
        arr, _ = RR.cargar(r)
        if arr is None:
            continue
        st = RR.col(arr, "rxsteer") / 1000.0
        ag = RR.col(arr, "rxage")
        sp = RR.col(arr, "rxspeed")
        m = (ag >= 0) & (ag < 200) & (sp > 0)
        S.append(st[m])
        V.append(sp[m])
    if not S:
        print("sin datos")
        return 1
    steer = np.concatenate(S)
    vel = np.concatenate(V)
    s = np.abs(steer)
    ab = np.minimum(s * GAIN, 1.0)

    print("")
    print("=" * 104)
    print("  LAS CINCO SOLUCIONES, CORRIDAS OFFLINE CONTRA EL DRIVEBASE")
    print("  b_eff %.1f cm   apertura %.2f   piso %.3f   |   n = %d muestras"
          % (a.beff, a.apertura, a.piso, len(s)))
    print("=" * 104)
    print("")
    print("  OJO: es LAZO ABIERTO. Caracteriza el MAPEO, no una corrida.")
    print("  Y el `steer` es el del atan2: HOY el planner NO corre (Main.py:41-44).")
    print("")
    print("  %-22s %9s %9s %10s %10s %10s"
          % ("ley", "avance", "%rot=1", "R traza p50", "R traza p10", "%R<4,9"))
    print("  " + "-" * 96)

    for nom, fn, modo in LEYES:
        piv = estado_pivote(ab, modo, steer)
        rot = fn(s, piv) if fn is not ley_laureano else fn(s, piv, a.piso, a.beff)
        rot = np.clip(rot, 0.0, 1.0)
        avance = 1.0 - rot
        with np.errstate(divide="ignore", invalid="ignore"):
            Rped = np.where(rot > 1e-9, a.beff * (1 - rot) / (2 * rot), np.inf)
        Rtra = Rped * a.apertura
        fin = np.isfinite(Rtra)
        print("  %-22s %9.3f %8.1f%% %10.2f %10.2f %9.1f%%"
              % (nom, avance.mean(), 100 * np.mean(rot >= 0.999),
                 np.median(Rtra[fin]) if fin.any() else float("nan"),
                 np.percentile(Rtra[fin], 10) if fin.any() else float("nan"),
                 100 * np.mean(Rtra[fin] < 4.9) if fin.any() else 0.0))

    # ------- que le pasa a cada ley en los angulos que de verdad llegan ------
    print("")
    print("=" * 104)
    print("  QUE RADIO TRAZA CADA LEY EN LOS DECILES REALES DE |steer|")
    print("=" * 104)
    print("")
    dec = [np.percentile(s, q) for q in range(10, 101, 10)]
    print("  %8s" % "decil", end="")
    for nom, _, _ in LEYES:
        print(" %13s" % nom.split()[0][:13], end="")
    print("")
    print("  " + "-" * 96)
    for q, sv in zip(range(10, 101, 10), dec):
        print("  %4d %.3f" % (q, sv), end="")
        for nom, fn, modo in LEYES:
            arrs = np.array([sv])
            pivv = np.array([sv * GAIN >= ENTRA])
            rot = (fn(arrs, pivv, a.piso, a.beff) if fn is ley_laureano
                   else fn(arrs, pivv, a.piso))
            rot = float(np.clip(rot, 0, 1)[0])
            R = a.beff * (1 - rot) / (2 * rot) * a.apertura if rot > 1e-9 else float("inf")
            print(" %13s" % (("%.1f" % R) if R < 999 else "recto"), end="")
        print("")

    print("")
    print("=" * 104)
    print("  COMO SE LEE")
    print("=" * 104)
    print("")
    print("  * `avance` es v_centro/vel promedio. Hoy da 0,32: el robot se pasa")
    print("    un tercio de su capacidad de avanzar girando en el lugar.")
    print("  * `%rot=1` es el tiempo que NO AVANZA. Cualquier ley que lo deje")
    print("    arriba de 0 esta regalando avance.")
    print("  * `R traza p10` es el radio mas cerrado que la ley pide seguido.")
    print("    Si da menos que el radio real de la pista, la ley pide imposibles.")
    print("  * NINGUNA de estas columnas dice si el robot TOMA la curva. Eso")
    print("    solo lo dice la pista.")
    print("")
    print("  DOS TRAMPAS DE ESTA TABLA, y hay que decirlas:")
    print("")
    print("  1. BASE DA IGUAL QUE HOY, Y NO ES QUE EL FIX NO SIRVA. El fix del")
    print("     gap actua en 19 episodios puntuales de 63; en un promedio sobre")
    print("     50.962 muestras eso no se ve. Su efecto es PUNTUAL, no")
    print("     distribucional, y esta tabla solo mide lo distribucional.")
    print("     Para verlo hay que contar cruces de gap, no promediar radios.")
    print("")
    print("  2. LAS SEIS CORRIDAS SON SEIS FIRMWARES DISTINTOS (gain 1,35 y 1,80;")
    print("     pivote 20/35/60; con y sin histeresis). Aca se les aplica UNA")
    print("     sola maquina de estados a todas, asi que el `%rot=1` de la fila")
    print("     HOY esta inflado: mezcla corridas que tenian la histeresis con")
    print("     corridas que no. El numero medido sobre la columna `rot` REAL de")
    print("     los CSV es 19 % por nivel y 17-61 % total segun la corrida.")
    print("")
    print("  EL NUMERO QUE FALTA, y lo tiene que traer Laureano con una cinta:")
    print("  EL RADIO REAL de las curvas mas cerradas de nuestra pista. Sin el,")
    print("  la columna `%R<4,9` se compara contra una cita que no pudimos")
    print("  verificar en el reglamento.")
    print("=" * 104)
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
