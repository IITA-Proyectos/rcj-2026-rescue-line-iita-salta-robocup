# -*- coding: utf-8 -*-
"""
LEY DE RADIO EXPLICITO  -  cuanto cambia el rot, el R y el v_centro PEDIDOS.

NO TOCA EL ROBOT. Es un replay OPEN LOOP sobre el `rxsteer` grabado el 22-ago:
se le da a las dos leyes el MISMO comando de la Pi y se compara que habrian
pedido. No predice trayectoria (si el robot se hubiera movido distinto, la Pi
habria mandado otra cosa). Caracteriza EL MAPEO.

LA LEY QUE SE EVALUA
--------------------
    alfa = |steer| * 90 grados                (steer = lo que manda la vision, SIN tocar)
    R    = R_MIN / sin(alfa)                  R_MIN = radio a fondo de escala
    rot  = b_eff / (2R + b_eff)
         = b_eff*sin(alfa) / (2*R_MIN + b_eff*sin(alfa))     <- forma sin division por 0

contra la de HOY:
    absSteer = min(|steer|*1.35, 1)
    rot      = absSteer^0.5    ...  y 1.0 si el pivote esta enganchado
                                    o si absSteer >= 0.92

FALSADOR PREREGISTRADO  (escrito ANTES de correr nada, regla 1 del equipo)
--------------------------------------------------------------------------
La ley de radio explicito QUEDA REFUTADA como candidata si pasa cualquiera de:

 F1  NO ES UNA RELAJACION PURA.  Si existe algun |steer| en [0,1] donde la ley
     nueva pide MAS rot que la de hoy, entonces no es "el robot gira menos de
     lo que gira hoy": es un cambio de dos signos y no se puede razonar el
     riesgo. Gate: rot_nuevo(s) <= rot_hoy(s) para los 1001 puntos de una
     grilla de s en [0,1], con las dos reglas de pivote apagadas.

 F2  NO MUEVE LA AGUJA.  Si con el pivote conservado (R_pivote = 0, o sea el
     comportamiento de hoy en el latch) la fraccion de tiempo con R pedido
     < 2 cm no baja al menos 5 puntos porcentuales, el fix no hace nada donde
     duele y no vale el riesgo. Se reporta ADEMAS la variante con el pivote
     abierto.

 F3  SE COME LA AUTORIDAD EN LA BANDA UTIL.  Si en la banda |steer| en
     [0.05, 0.30] -donde el robot hoy sigue rectas y curvas suaves SIN
     enganchar el pivote- el radio pedido por la ley nueva se va por encima de
     30 cm (media pista de un tile de 30 cm), la ley no puede seguir una curva
     suave y hay que agrandar R_MIN o cambiar la forma.

 F4  PLATEAU.  El veredicto de F1 y F2 tiene que ser el MISMO en toda la banda
     preregistrada de R_MIN = {4.0, 4.9, 6.0, 8.0} cm y b_eff = {20.9, 21.4}
     cm (el b_eff medido y el peor de las tres corridas de pista). Si el
     veredicto cambia adentro de la banda, se elige punto y eso ya refuta.

 F5  SANIDAD FISICA. rot pedido tiene que quedar en [0,1] siempre, el R pedido
     tiene que ser monotono decreciente en |steer|, y en steer = 0 la ley tiene
     que dar rot = 0 EXACTO (recta). Si alguna falla, hay un error de algebra.

CONTROL C-1 (frescura). Todo se calcula sobre muestras con 0 <= rxage <= 100 ms.
`rxage = -1` significa QUE NUNCA LLEGO UNA TRAMA (main.cpp:874) y es MENOR que
cualquier umbral: hay que pedir `>= 0` explicito. Ese bug ya contamino un
analisis de este proyecto.

CONTROL C-2 (fuera de muestra). El simulador de la maquina de pivote de HOY se
contrasta contra la unica corrida que REALMENTE corrio esa config
(`pivote_con_histeresis`, nota "HISTERESIS pivote 0.60/0.15"): el % de tiempo
con rot=1 simulado tiene que caer cerca del medido en la columna `rot` del CSV.

    python ley_radio_explicito.py
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retardo_real as RR

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
DIR = os.path.join(RAIZ, "software", "teensy", "firmware", "corridas")

# --- constantes del firmware de HOY (main.cpp:90-147, 3636-3857) -------------
GAIN = 1.35
ROT_EXP = 0.50
PIV_ENTRA = 0.60
PIV_SALE = 0.15
PIV_CONFIRMA_MS = 0.0
PIV_MAX_MS = 2500.0
PIVOT_STEER = 0.92          # regla puntual
PIV_SPEED = 50.0
VEL_BASE = 40.0             # ajustarVelocidadPorPendiente() en llano
B_EFF = 20.9                # drivebase.h, MEDIDO el 26-ago
DIAM = 6.88                 # cm, diametro efectivo de rodadura
CM_POR_RPM = math.pi * DIAM / 60.0
DT_MS = 5.0                 # el registrador va a 200 Hz

# --- banda preregistrada -----------------------------------------------------
BANDA_RMIN = [4.0, 4.9, 6.0, 8.0]
BANDA_BEFF = [20.9, 21.4]


def rot_hoy_formula(s):
    """rot de HOY sin las reglas de pivote (solo gain + raiz + clamp)."""
    a = np.minimum(np.abs(s) * GAIN, 1.0)
    return np.minimum(np.power(a, ROT_EXP), 1.0)


def rot_nuevo(s, rmin, beff=B_EFF):
    """rot de la LEY DE RADIO EXPLICITO. Sin division por cero por construccion."""
    sa = np.sin(np.minimum(np.abs(s), 1.0) * math.pi / 2.0)
    return beff * sa / (2.0 * rmin + beff * sa)


def radio_de_rot(rot, beff=B_EFF):
    """R = b*(1-rot)/(2*rot). rot=0 -> infinito; rot=1 -> 0."""
    rot = np.asarray(rot, dtype=float)
    R = np.full(rot.shape, np.inf)
    m = rot > 1e-12
    R[m] = beff * (1.0 - rot[m]) / (2.0 * rot[m])
    return R


def sim_pivote(s):
    """Maquina de pivote de HOY sobre el rxsteer grabado. Devuelve (latch, absSteer).

    OPEN LOOP y a 200 Hz mientras el lazo real va a ~28 Hz: le doy MAS
    oportunidades de soltar de las que tiene, o sea COTA INFERIOR del enganche.
    """
    a = np.minimum(np.abs(s) * GAIN, 1.0)
    n = len(a)
    latch = np.zeros(n, dtype=bool)
    en = False
    t0 = 0.0
    ali0 = None
    for i in range(n):
        t = i * DT_MS
        if not en and a[i] >= PIV_ENTRA:
            en = True
            t0 = t
            ali0 = None
        elif en:
            if a[i] > PIV_SALE:
                ali0 = None
            elif ali0 is None:
                ali0 = t
            sostenido = (ali0 is not None and t - ali0 >= PIV_CONFIRMA_MS)
            if sostenido or (t - t0 > PIV_MAX_MS):
                en = False
                ali0 = None
        latch[i] = en
    return latch, a


def pct(x, q):
    return float(np.percentile(x, q)) if len(x) else float("nan")


def fmtR(r):
    if not np.isfinite(r):
        return "  inf"
    if r > 999:
        return " >999"
    return "%5.1f" % r


def main():
    corridas = sorted(f for f in os.listdir(DIR)
                      if f.startswith("2026-08-22_pista") and f.endswith(".csv"))
    print("=" * 100)
    print("  LEY DE RADIO EXPLICITO  -  replay open loop sobre el rxsteer del 22-ago")
    print("=" * 100)

    # ------------------------------------------------------------------ F1 / F5
    print("\n0. FALSADORES F1 y F5  (algebra pura, 1001 puntos de s en [0,1])")
    grid = np.linspace(0.0, 1.0, 1001)
    rh = rot_hoy_formula(grid)
    print("  R_MIN  b_eff |  F1 relajacion pura  |  F5 rot en [0,1]  monotono R  rot(0)=0")
    f1_todos, f5_todos = [], []
    for rmin in BANDA_RMIN:
        for beff in BANDA_BEFF:
            rn = rot_nuevo(grid, rmin, beff)
            f1 = bool(np.all(rn <= rh + 1e-12))
            Rn = radio_de_rot(rn, beff)
            mono = bool(np.all(np.diff(Rn[1:]) <= 1e-9))
            f5 = bool(np.all((rn >= -1e-12) & (rn <= 1.0 + 1e-12))
                      and mono and abs(rn[0]) < 1e-12)
            f1_todos.append(f1)
            f5_todos.append(f5)
            print("  %5.1f  %5.1f |  %-18s  |  %-16s  %-9s  %s"
                  % (rmin, beff, "PASA" if f1 else "FALLA",
                     "PASA" if np.all((rn >= 0) & (rn <= 1)) else "FALLA",
                     "PASA" if mono else "FALLA",
                     "PASA" if abs(rn[0]) < 1e-12 else "FALLA"))
    print("  F1 en TODA la banda: %s" % ("PASA" if all(f1_todos) else "FALLA"))
    print("  F5 en TODA la banda: %s" % ("PASA" if all(f5_todos) else "FALLA"))

    # ------------------------------------------------------------------ tabla
    print("\n1. LA TABLA DEL MAPEO  (b_eff = 20,9 cm ; R_MIN = 4,9 cm)")
    print("   |steer|  grados |   HOY: absSteer   rot     R cm   vc/vel |"
          "   NUEVO:  rot     R cm   vc/vel")
    for s in [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.444, 0.50,
              0.60, 0.681, 0.741, 0.80, 0.90, 1.00]:
        a = min(s * GAIN, 1.0)
        rh1 = min(a ** ROT_EXP, 1.0)
        if a >= PIVOT_STEER:
            rh1 = 1.0
        rn1 = float(rot_nuevo(np.array([s]), 4.9)[0])
        Rh = float(radio_de_rot(np.array([rh1]))[0])
        Rn = float(radio_de_rot(np.array([rn1]))[0])
        marca = "  <- ENTRA el pivote" if abs(s - 0.444) < 1e-9 else ""
        print("     %5.3f   %5.1f |          %5.3f  %5.3f   %s    %5.3f |"
              "           %5.3f   %s    %5.3f%s"
              % (s, s * 90, a, rh1, fmtR(Rh), 1 - rh1, rn1, fmtR(Rn), 1 - rn1, marca))

    # ------------------------------------------------------------- F3 en banda
    print("\n2. FALSADOR F3  -  radio pedido en la banda util |steer| en [0.05, 0.30]")
    print("   (gate: el R pedido a |steer| = 0.05 no puede pasar de 30 cm)")
    print("   R_MIN  b_eff |  R(0.05)  R(0.10)  R(0.20)  R(0.30) |  F3")
    f3_todos = []
    for rmin in BANDA_RMIN:
        for beff in BANDA_BEFF:
            ss = np.array([0.05, 0.10, 0.20, 0.30])
            Rr = radio_de_rot(rot_nuevo(ss, rmin, beff), beff)
            f3 = bool(Rr[0] <= 30.0)
            f3_todos.append(f3)
            print("   %5.1f  %5.1f |   %s    %s    %s    %s |  %s"
                  % (rmin, beff, fmtR(Rr[0]), fmtR(Rr[1]), fmtR(Rr[2]), fmtR(Rr[3]),
                     "PASA" if f3 else "FALLA"))
    print("   F3 en TODA la banda: %s" % ("PASA" if all(f3_todos) else "FALLA"))

    # ------------------------------------------------------------------- datos
    print("\n3. CONTROL C-1 (frescura) y C-2 (simulador fuera de muestra)")
    print("  corrida                        n_val   t_s  | rot=1 MEDIDO  rot=1 SIMULADO")
    datos = []
    for f in corridas:
        a, nota = RR.cargar(os.path.join(DIR, f))
        s_all = RR.col(a, "rxsteer") / 1000.0
        age = RR.col(a, "rxage")
        rot_log = np.abs(RR.col(a, "rot")) / 1000.0
        m = (age >= 0) & (age <= 100)
        latch, absS = sim_pivote(s_all)
        nom = f.replace("2026-08-22_pista_", "").replace(".csv", "")
        med = float(np.mean(rot_log[m] >= 0.999)) * 100 if m.sum() else float("nan")
        sim = float(np.mean(latch[m])) * 100 if m.sum() else float("nan")
        print("  %-28s %6d %6.1f  |     %5.1f %%        %5.1f %%"
              % (nom, m.sum(), m.sum() * DT_MS / 1000.0, med, sim))
        datos.append((nom, nota, s_all[m], latch[m], absS[m]))

    S = np.concatenate([d[2] for d in datos])
    L = np.concatenate([d[3] for d in datos])
    A = np.concatenate([d[4] for d in datos])
    print("  POOL  n = %d muestras = %.1f s" % (len(S), len(S) * DT_MS / 1000.0))

    # rot de HOY completo (formula + las dos reglas de pivote)
    rot_h = rot_hoy_formula(S)
    rot_h = np.where(L, 1.0, rot_h)
    rot_h = np.where(A >= PIVOT_STEER, 1.0, rot_h)

    # velocidad comandada: identica en las dos leyes (no se toca la rampa)
    k = np.clip(A / PIVOT_STEER, 0.0, 1.0)
    vel_rpm = VEL_BASE + k * k * (PIV_SPEED - VEL_BASE)
    vel_cms = vel_rpm * CM_POR_RPM

    def resumen(nombre, rot, beff=B_EFF):
        R = radio_de_rot(rot, beff)
        vc = vel_cms * (1.0 - rot)
        avance = float(np.sum(vc) * DT_MS / 1000.0)
        print("  %-26s rot p50 %5.3f  p90 %5.3f | rot=1 %5.1f %% | "
              "R<2cm %5.1f %%  R<4.9cm %5.1f %% | vc p50 %5.2f  media %5.2f cm/s | "
              "avance %7.1f cm"
              % (nombre, pct(rot, 50), pct(rot, 90),
                 float(np.mean(rot >= 0.999)) * 100,
                 float(np.mean(R < 2.0)) * 100, float(np.mean(R < 4.9)) * 100,
                 pct(vc, 50), float(np.mean(vc)), avance))
        return dict(rot=rot, R=R, vc=vc, avance=avance)

    print("\n4. QUE SE HABRIA PEDIDO, SOBRE EL MISMO rxsteer  (b_eff 20,9 ; pool de 6 corridas)")
    print("   la VELOCIDAD comandada es la misma en las dos leyes: la rampa k^2 no se toca")
    hoy = resumen("HOY  (formula+pivote)", rot_h)
    for rmin in BANDA_RMIN:
        rn = rot_nuevo(S, rmin)
        # variante A: el pivote sigue siendo giro en el lugar (R_pivote = 0)
        rA = np.where(L | (A >= PIVOT_STEER), 1.0, rn)
        resumen("NUEVO R_MIN=%.1f  piv=0" % rmin, rA)
    for rmin in BANDA_RMIN:
        rn = rot_nuevo(S, rmin)
        resumen("NUEVO R_MIN=%.1f  piv=R_MIN" % rmin, rn)

    # ------------------------------------------------------------- F2 y plateau
    print("\n5. FALSADOR F2 (baja la fraccion de R<2 cm al menos 5 puntos?) y F4 (plateau)")
    print("   R_MIN  b_eff |  R<2cm HOY  |  piv=0   delta  F2 |  piv=R_MIN  delta  F2")
    f2_A, f2_B = [], []
    for rmin in BANDA_RMIN:
        for beff in BANDA_BEFF:
            rh2 = rot_hoy_formula(S)
            rh2 = np.where(L | (A >= PIVOT_STEER), 1.0, rh2)
            base = float(np.mean(radio_de_rot(rh2, beff) < 2.0)) * 100
            rn = rot_nuevo(S, rmin, beff)
            rA = np.where(L | (A >= PIVOT_STEER), 1.0, rn)
            a2 = float(np.mean(radio_de_rot(rA, beff) < 2.0)) * 100
            b2 = float(np.mean(radio_de_rot(rn, beff) < 2.0)) * 100
            okA = (base - a2) >= 5.0
            okB = (base - b2) >= 5.0
            f2_A.append(okA)
            f2_B.append(okB)
            print("   %5.1f  %5.1f |    %5.1f %%   |  %5.1f %%  %5.1f  %-4s|   %5.1f %%  %5.1f  %s"
                  % (rmin, beff, base, a2, base - a2, "PASA" if okA else "FALLA",
                     b2, base - b2, "PASA" if okB else "FALLA"))
    print("   F2 con el pivote CONSERVADO  (piv=0)    : %s  (plateau F4: %s)"
          % ("PASA" if all(f2_A) else "FALLA",
             "SI" if len(set(f2_A)) == 1 else "NO"))
    print("   F2 con el pivote ABIERTO     (piv=R_MIN): %s  (plateau F4: %s)"
          % ("PASA" if all(f2_B) else "FALLA",
             "SI" if len(set(f2_B)) == 1 else "NO"))

    # ------------------------------------------------------- donde cambia y cuanto
    print("\n6. DONDE CAMBIA  (R_MIN = 4,9 ; b_eff = 20,9)  -  por banda de |steer|")
    rn49 = rot_nuevo(S, 4.9)
    rA49 = np.where(L | (A >= PIVOT_STEER), 1.0, rn49)
    bandas = [(0.0, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 0.444),
              (0.444, 0.60), (0.60, 0.741), (0.741, 1.01)]
    print("   banda |steer|      n    % t | rot HOY  rot piv=0  rot piv=R_MIN |"
          "  R HOY   R piv=R_MIN | d vc cm/s")
    for lo, hi in bandas:
        m = (np.abs(S) >= lo) & (np.abs(S) < hi)
        if m.sum() == 0:
            continue
        Rh = radio_de_rot(rot_h[m])
        Rn = radio_de_rot(rn49[m])
        dvc = float(np.mean(vel_cms[m] * (rot_h[m] - rn49[m])))
        print("   %5.3f - %5.3f %7d %5.1f | %7.3f  %8.3f  %12.3f | %s   %s |  %+6.2f"
              % (lo, hi, m.sum(), 100.0 * m.sum() / len(S),
                 pct(rot_h[m], 50), pct(rA49[m], 50), pct(rn49[m], 50),
                 fmtR(pct(Rh, 50)), fmtR(pct(Rn, 50)), dvc))

    # ------------------------------------------------------- sanidad: factibilidad
    print("\n7. SANIDAD FISICA  -  el giro que hace falta para trazar el R pedido")
    print("   omega = v_centro / R.  El techo MEDIDO del robot es 39-55 grados/s")
    print("   |steer|   R pedido   vel rpm   v_centro   omega pedido   pasa el techo?")
    for s in [0.10, 0.20, 0.30, 0.444, 0.60, 0.80, 1.00]:
        rn1 = float(rot_nuevo(np.array([s]), 4.9)[0])
        Rn1 = float(radio_de_rot(np.array([rn1]))[0])
        a = min(s * GAIN, 1.0)
        kk = min(a / PIVOT_STEER, 1.0)
        v = (VEL_BASE + kk * kk * (PIV_SPEED - VEL_BASE)) * CM_POR_RPM
        vc = v * (1 - rn1)
        om = math.degrees(vc / Rn1) if Rn1 > 0 else float("inf")
        print("     %5.3f    %s cm    %5.1f     %5.2f cm/s    %6.1f d/s      %s"
              % (s, fmtR(Rn1), v / CM_POR_RPM, vc, om,
                 "SI" if om <= 55 else "NO -> trazara MAS ABIERTO"))

    # ------------------------------------------------------------------ POST-HOC
    print("\n" + "=" * 100)
    print("  8. POST-HOC  -  NO ESTABA PREREGISTRADO. Sale de VER que F3 fallo.")
    print("     Genera hipotesis, no la confirma. Regla 7: esto NO es politica adoptada.")
    print("=" * 100)
    print("""
     F3 fallo porque `R = R_MIN/sin(alfa)` ata DOS cosas a un solo numero: el
     radio a fondo de escala Y la ganancia cerca del centro. Separarlas es un
     parametro mas, y la ley preregistrada queda como el caso L = 2*R_MIN:

         R(s) = max( L / (2*sin(|s|*90 gr)) , R_MIN )

     L = lookahead efectivo en cm (manda cerca del centro)
     R_MIN = piso, el radio mas cerrado que se pide (manda a fondo de escala)
""")
    print("   L cm | R(.05) R(.10) R(.20) R(.30) R(.44) R(1.0) | F3  F1  |"
          "  R<2cm  vc media  avance")
    Lgrid = [3.0, 4.0, 4.7, 5.5, 6.5, 8.0, 9.8, 12.0]

    def rot_2p(s, L, rmin, beff=B_EFF):
        sa = np.sin(np.minimum(np.abs(s), 1.0) * math.pi / 2.0)
        R = np.where(sa > 1e-12, L / (2.0 * np.maximum(sa, 1e-12)), np.inf)
        R = np.maximum(R, rmin)
        return beff / (2.0 * R + beff)

    fila_ok = {}
    for L in Lgrid:
        ss = np.array([0.05, 0.10, 0.20, 0.30, 0.444, 1.0])
        Rr = radio_de_rot(rot_2p(ss, L, 4.9), B_EFF)
        f3 = bool(Rr[0] <= 30.0)
        f1 = bool(np.all(rot_2p(grid, L, 4.9) <= rh + 1e-12))
        rn = rot_2p(S, L, 4.9)
        r2 = float(np.mean(radio_de_rot(rn) < 2.0)) * 100
        vc = vel_cms * (1.0 - rn)
        fila_ok[L] = (f3, f1)
        print("   %4.1f | %s %s %s %s %s %s |%-4s %-4s|  %4.1f %%  %6.2f   %7.1f cm"
              % (L, fmtR(Rr[0]), fmtR(Rr[1]), fmtR(Rr[2]), fmtR(Rr[3]),
                 fmtR(Rr[4]), fmtR(Rr[5]),
                 "PASA" if f3 else "FALLA", "PASA" if f1 else "no",
                 r2, float(np.mean(vc)), float(np.sum(vc) * DT_MS / 1000.0)))
    print("   (HOY, para comparar:      %s %s %s %s %s %s |          |  %4.1f %%  %6.2f   %7.1f cm)"
          % (fmtR(29.8), fmtR(18.0), fmtR(9.7), fmtR(6.0), fmtR(3.0), fmtR(0.0),
             62.5, float(np.mean(hoy["vc"])), hoy["avance"]))
    print("\n   'F1 no' NO es un defecto: significa que en la banda media la ley pide")
    print("   un radio MAS CERRADO que hoy (se compromete antes con la curva) y a")
    print("   fondo de escala pide uno MAS ABIERTO (no gira en el lugar).")
    print("   NO amplifica el steer de la vision: el byte se usa tal cual (regla 8).")

    print("\n   9. POST-HOC: cuanto se aparta la ley de dos parametros de la de HOY,")
    print("      por banda de |steer|  (L = 4.7 cm ; R_MIN = 4.9 ; b_eff = 20.9)")
    rn2 = rot_2p(S, 4.7, 4.9)
    print("   banda |steer|      % t | rot HOY   rot NUEVO |  R HOY    R NUEVO | d vc cm/s")
    for lo, hi in bandas:
        m = (np.abs(S) >= lo) & (np.abs(S) < hi)
        if m.sum() == 0:
            continue
        print("   %5.3f - %5.3f %6.1f | %7.3f   %8.3f | %s    %s |  %+6.2f"
              % (lo, hi, 100.0 * m.sum() / len(S),
                 pct(rot_h[m], 50), pct(rn2[m], 50),
                 fmtR(pct(radio_de_rot(rot_h[m]), 50)),
                 fmtR(pct(radio_de_rot(rn2[m]), 50)),
                 float(np.mean(vel_cms[m] * (rot_h[m] - rn2[m])))))

    print("\n   10. POST-HOC: el PISO R_MIN con L = 4,7 cm fijo.")
    print("       Con R_MIN = L/2 el piso NO ata nunca y no hay zona plana.")
    print("   R_MIN | s donde ata | R(.30) R(.44) R(.60) R(1.0) | rot(1.0) vc(1.0) |"
          " R<2cm  vc media")
    for rmin in [2.35, 3.0, 4.0, 4.9, 6.0]:
        sa_ata = 4.7 / (2.0 * rmin)
        s_ata = (math.degrees(math.asin(min(sa_ata, 1.0))) / 90.0) if sa_ata <= 1 else 9.99
        ss = np.array([0.30, 0.444, 0.60, 1.0])
        Rr = radio_de_rot(rot_2p(ss, 4.7, rmin), B_EFF)
        r1 = float(rot_2p(np.array([1.0]), 4.7, rmin)[0])
        rn = rot_2p(S, 4.7, rmin)
        vc = vel_cms * (1.0 - rn)
        print("   %5.2f |    %s     | %s %s %s %s |  %5.3f   %5.2f  | %4.1f %%  %6.2f"
              % (rmin, ("%5.3f" % s_ata) if s_ata <= 1 else " nunca",
                 fmtR(Rr[0]), fmtR(Rr[1]), fmtR(Rr[2]), fmtR(Rr[3]),
                 r1, 50.0 * CM_POR_RPM * (1 - r1),
                 float(np.mean(radio_de_rot(rn) < 2.0)) * 100, float(np.mean(vc))))

    print("\n   11. LA CONFIG QUE SE EMBARCA EN priority_fix_flags.h fix (8):")
    print("       kRadioLookaheadCm = 4.7   kRadioMinCm = 4.0   kRadioPivoteCm = 4.0")
    emb = rot_2p(S, 4.7, 4.0)
    LATCH = np.concatenate([d[3] for d in datos])   # `L` quedo pisada en la sec. 8
    embA = np.where(LATCH | (A >= PIVOT_STEER), 1.0, rot_2p(S, 4.7, 4.0))  # etapa 1
    print("   banda |steer|     % t |  rot HOY  rot EMB |   R HOY    R EMB  |"
          " vc HOY  vc EMB | d vc")
    for lo, hi in bandas:
        m = (np.abs(S) >= lo) & (np.abs(S) < hi)
        if m.sum() == 0:
            continue
        vch = vel_cms[m] * (1 - rot_h[m])
        vce = vel_cms[m] * (1 - emb[m])
        print("   %5.3f - %5.3f %6.1f | %7.3f  %7.3f | %s   %s  |"
              "  %5.2f  %5.2f  | %+5.2f"
              % (lo, hi, 100.0 * m.sum() / len(S), pct(rot_h[m], 50), pct(emb[m], 50),
                 fmtR(pct(radio_de_rot(rot_h[m]), 50)),
                 fmtR(pct(radio_de_rot(emb[m]), 50)),
                 float(np.mean(vch)), float(np.mean(vce)),
                 float(np.mean(vce - vch))))
    for nom, r in (("HOY                  ", rot_h),
                   ("EMBARCADA etapa 1 (piv=0) ", embA),
                   ("EMBARCADA etapa 2 (piv=4,0)", emb)):
        R = radio_de_rot(r)
        vc = vel_cms * (1.0 - r)
        print("   %-27s rot p50 %5.3f | R<2cm %5.1f %% | R<4,9cm %5.1f %% |"
              " vc p50 %5.2f media %5.2f | avance %7.1f cm"
              % (nom, pct(r, 50), float(np.mean(R < 2.0)) * 100,
                 float(np.mean(R < 4.9)) * 100, pct(vc, 50), float(np.mean(vc)),
                 float(np.sum(vc) * DT_MS / 1000.0)))

    print("\n" + "=" * 100)
    print("  VEREDICTO DE LOS FALSADORES  (sobre la ley PREREGISTRADA R = R_MIN/sin)")
    print("    F1 relajacion pura        : %s" % ("PASA" if all(f1_todos) else "FALLA"))
    print("    F2 mueve la aguja piv=0   : %s" % ("PASA" if all(f2_A) else "FALLA"))
    print("    F2 mueve la aguja piv=Rmin: %s" % ("PASA" if all(f2_B) else "FALLA"))
    print("    F3 banda util             : %s" % ("PASA" if all(f3_todos) else "FALLA"))
    print("    F4 plateau                : %s" % (
        "SI" if len(set(f2_A)) == 1 and len(set(f2_B)) == 1 else "NO"))
    print("    F5 sanidad algebraica     : %s" % ("PASA" if all(f5_todos) else "FALLA"))
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
