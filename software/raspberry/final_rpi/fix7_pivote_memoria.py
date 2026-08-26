# -*- coding: utf-8 -*-
"""
CUANTIFICACION DEL FIX (7): EL PIVOTE POR MEMORIA TRAZA, NO GIRA EN EL LUGAR.

QUE PROPONE EL FIX (una sola rama del case 7, main.cpp:3808-3812)

    hoy:        if (s_en_pivote) rot = 1.0;
    con el fix: if (s_en_pivote) {
                    rot = 1.0;
                    if (FLAG && absSteer < LINE_PIVOTE_ENTRA)
                        rot = max(pow(absSteer, LINE_ROT_EXP), kPivoteRotMemoriaMin);
                }

O sea: mientras el pivote esta enganchado PERO el comando fresco ya bajo del
umbral de entrada -la region de MEMORIA-, `rot` deja de ser 1,0 y pasa a ser la
propia rampa del firmware con un PISO. Con el piso en 0,681 el robot traza
R = b_eff*(1-rot)/(2*rot) = 4,9 cm, que es la curva mas cerrada del reglamento.
Cuando el comando fresco SI pide angulo grande (absSteer >= ENTRA, y la regla
puntual de 0,92) no cambia absolutamente nada.

===========================================================================
FALSADOR, ESCRITO ANTES DE CORRER NADA (regla 1). Umbrales en BANDA (regla 2).
===========================================================================

BANDA PREREGISTRADA
    gain   in {1.30, 1.35, 1.40}
    ENTRA  in {0.55, 0.60, 0.65}
    rxage  in {sin filtro, <= 100 ms}
    piso   in {1.000 (=apagado), 0.681, 0.500}
Solo hay conclusion si el VEREDICTO es el mismo en toda la banda (PLATEAU).

H-M1  LA REGION DE MEMORIA EXISTE Y NO ES MARGINAL.
      El tiempo con el pivote enganchado y absSteer < ENTRA tiene que ser
      >= 10 % del tiempo de pista en TODAS las celdas de la banda.
      Si en alguna baja de 10 %, el fix toca poco y NO vale el riesgo: se cae.

H-M2  EL FIX DEVUELVE AVANCE SIN ABRIR LA CURVA.
      En esa region, con el piso 0,681: v_centro/vel p50 >= 0,20 (hoy es 0,00
      por definicion) Y el radio pedido p50 tiene que quedar en [3,0 ; 8,0] cm
      en toda la banda. Si el R p50 se va arriba de 8 cm el fix aflojo
      demasiado y deja de trazar una curva de reglamento: se cae.

H-M3  NO ROMPER (identidad algebraica).
      El tiempo con rot = 1,0 pedido POR NIVEL -absSteer >= ENTRA, mas la regla
      puntual absSteer >= 0,92- tiene que ser IDENTICO con y sin el fix, hasta
      la ultima muestra. Si difiere aunque sea en una, el sim no es el firmware
      y todo lo demas se tira.

C-1   CONTROL POSITIVO. Con piso = 1.000 el fix tiene que dar EXACTAMENTE los
      mismos numeros que hoy, muestra por muestra (max |dif| = 0). Si no da 0,
      el codigo del simulador no reproduce el del firmware y no se publica nada.

C-2   CONTROL DE FRESCURA. Todo repetido con rxage <= 100 ms (y age >= 0: el
      -1 de "nunca llego" es MENOR que cualquier umbral y se colaria). Si los
      porcentajes se mueven mas de 5 puntos entre crudo y filtrado, el
      resultado depende de tramas viejas y hay que reportarlo como tal.

C-3   SANIDAD FISICA (regla 6). rot = 1 tiene que verse en los sensores como
      "gira y no avanza". Se contrasta |gz| y el avance por encoders en las
      muestras de memoria contra las de rot < 1.

MEDIDO (no simulado): la parte A usa la columna `rot` que el firmware GRABO,
no un replay. La parte B es replay open loop y esta marcada como tal.

    python software/raspberry/final_rpi/fix7_pivote_memoria.py
"""

import glob
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import retardo_real as RR  # noqa: E402

CORRIDAS = os.path.abspath(os.path.join(
    AQUI, "..", "..", "teensy", "firmware", "corridas"))

B_EFF = 20.9          # cm, drivebase.h, medido el 26-ago
DIAM = 6.88           # cm, diametro efectivo de rodadura
RPM_A_CMS = np.pi * DIAM / 60.0
DT = 0.005            # s por muestra (registrador a 200 Hz)

ROT_EXP = 0.50
PIV_SALE = 0.15
PIV_MAX_MS = 2500.0
PIV_PUNTUAL = 0.92
PIVOT_SPEED = 50.0
VEL_BASE = 45.0       # velocidadBaseDeLinea() por defecto

GAIN_NOTA = {         # gain declarado en la nota del CSV
    "pista_arbol_de_ramas": 1.35,
    "pista_gain18": 1.80,
    "pista_pivote35": 1.35,
    "pista_pivote_con_histeresis": 1.35,
    "pista_pivote_sin_histeresis": 1.35,
    "pista_rampa_continua_pivote20": 1.35,
}


def nombre(ruta):
    return os.path.basename(ruta).replace("2026-08-22_", "").replace(".csv", "")


def cargar_pista():
    out = []
    for r in sorted(glob.glob(os.path.join(CORRIDAS, "2026-08-22_pista_*.csv"))):
        a, nota = RR.cargar(r)
        out.append((nombre(r), a, nota))
    return out


def abs_steer(a, gain):
    s = RR.col(a, "rxsteer") / 1000.0
    return np.abs(np.clip(s * gain, -1.0, 1.0))


def simular_latch(absS, t_ms, entra):
    """Maquina de estados del case 7 de HOY. CONFIRMA_MS = 0.
    Devuelve el vector booleano s_en_pivote muestra a muestra."""
    n = len(absS)
    en = np.zeros(n, dtype=bool)
    latched = False
    t0 = 0.0
    for i in range(n):
        if not latched and absS[i] >= entra:
            latched = True
            t0 = t_ms[i]
        elif latched:
            # CONFIRMA_MS = 0 -> alcanza con una muestra alineada
            if absS[i] <= PIV_SALE or (t_ms[i] - t0) > PIV_MAX_MS:
                latched = False
        en[i] = latched
    return en


def rot_hoy(absS, en):
    r = np.where(en, 1.0, np.power(absS, ROT_EXP))
    r = np.where(absS >= PIV_PUNTUAL, 1.0, r)
    return np.minimum(r, 1.0)


def rot_fix(absS, en, entra, piso):
    """Identico a rot_hoy salvo en la region de MEMORIA."""
    r = rot_hoy(absS, en)
    mem = en & (absS < entra) & (absS < PIV_PUNTUAL)
    traza = np.maximum(np.power(absS, ROT_EXP), piso)
    return np.where(mem, np.minimum(r, traza), r)


def vel_firmware(absS):
    k = np.clip(absS / PIV_PUNTUAL, 0.0, 1.0)
    return VEL_BASE + k * k * (PIVOT_SPEED - VEL_BASE)


def radio(rot):
    with np.errstate(divide="ignore", invalid="ignore"):
        R = B_EFF * (1.0 - rot) / (2.0 * rot)
    return np.where(rot <= 0, np.inf, R)


def p50(x):
    return float(np.median(x)) if len(x) else float("nan")


def main():
    datos = cargar_pista()
    print("=" * 104)
    print("  FIX (7)  EL PIVOTE POR MEMORIA TRAZA EN VEZ DE GIRAR EN EL LUGAR")
    print("  6 corridas de PISTA del 22-ago, registrador a 200 Hz (1 muestra = 5 ms)")
    print("=" * 104)

    # -----------------------------------------------------------------
    print("\n  A. MEDIDO (columna `rot` que el firmware GRABO, sin replay)")
    print("     memoria = |rot| >= 0,995  Y  absSteer < ENTRA  (el comando fresco")
    print("     ya bajo del umbral, pero el firmware seguia pidiendo pivote)\n")
    hdr = ("  corrida                        gain   n_val   t_val  |rot|=1   MEMORIA"
           "   R p50  vc p50")
    print(hdr)
    tot = {}
    for nom, a, _ in datos:
        g = GAIN_NOTA[nom]
        absS = abs_steer(a, g)
        rotr = np.abs(RR.col(a, "rot") / 1000.0)
        age = RR.col(a, "rxage")
        val = (age >= 0) & (age <= 100)
        n = int(val.sum())
        r1 = rotr >= 0.995
        mem = val & r1 & (absS < 0.60)
        niv = val & r1 & (absS >= 0.60)
        vel = vel_firmware(absS)
        rfix = np.maximum(np.power(absS, ROT_EXP), 0.681)
        Rn = radio(rfix)
        vc = vel * (1.0 - rfix) * RPM_A_CMS
        print("  %-28s %5.2f %7d %6.1fs %7.1f%% %8.1f%% %7.2f %6.2f" % (
            nom, g, n, n * DT,
            100.0 * (val & r1).sum() / max(n, 1),
            100.0 * mem.sum() / max(n, 1),
            p50(Rn[mem]), p50(vc[mem])))
        tot[nom] = (n, int((val & r1).sum()), int(mem.sum()), int(niv.sum()))
    N = sum(v[0] for v in tot.values())
    M = sum(v[2] for v in tot.values())
    R1 = sum(v[1] for v in tot.values())
    NIV = sum(v[3] for v in tot.values())
    print("  %-28s %5s %7d %6.1fs %7.1f%% %8.1f%%" % (
        "TODAS", "-", N, N * DT, 100.0 * R1 / N, 100.0 * M / N))
    print("\n     del tiempo con rot = 1 GRABADO, la MEMORIA se lleva %.1f %%  (%.1f s de %.1f s)"
          % (100.0 * M / max(R1, 1), M * DT, R1 * DT))
    print("     el resto (%.1f s) es NIVEL: el comando fresco pide >= 0,60 y no se toca."
          % (NIV * DT))
    print("\n     OJO: LAS 6 CORRIDAS NO CORRIERON LA MISMA CONFIG. La unica cuya nota")
    print("     declara la histeresis 0.60/0.15 -la de HOY- es `pivote_con_histeresis`.")
    print("     VALIDACION FUERA DE MUESTRA, medido contra simulado por corrida:\n")
    print("  corrida                       MEM medido  MEM simulado   nota del CSV")
    for nom, a, nota in datos:
        g = GAIN_NOTA[nom]
        absS_m = abs_steer(a, g)
        rotr = np.abs(RR.col(a, "rot") / 1000.0)
        age = RR.col(a, "rxage")
        val = (age >= 0) & (age <= 100)
        mem_m = val & (rotr >= 0.995) & (absS_m < 0.60)
        absS = abs_steer(a, 1.35)
        t_ms = (RR.col(a, "us") - RR.col(a, "us")[0]) / 1000.0
        en = simular_latch(absS, t_ms, 0.60)
        mem_s = val & en & (absS < 0.60) & (absS < PIV_PUNTUAL)
        print("  %-28s %9.1f %% %11.1f %%   %s" % (
            nom, 100.0 * mem_m.sum() / val.sum(),
            100.0 * mem_s.sum() / val.sum(), nota[:46]))

    # -----------------------------------------------------------------
    print("\n  A2. CONTROL C-3, SANIDAD FISICA (regla 6): rot = 1 gira y no avanza?")
    print("      |gz| del BNO055 y avance por encoders, en las muestras de MEMORIA\n")
    print("  corrida                       |gz| mem   v_enc mem  |gz| rot<1  v_enc rot<1")
    for nom, a, _ in datos:
        g = GAIN_NOTA[nom]
        absS = abs_steer(a, g)
        rotr = np.abs(RR.col(a, "rot") / 1000.0)
        age = RR.col(a, "rxage")
        val = (age >= 0) & (age <= 100)
        mem = val & (rotr >= 0.995) & (absS < 0.60)
        lo = val & (rotr < 0.995)
        gz = np.abs(RR.col(a, "gz") / 10.0)
        # `ls`/`rs` del CSV son MAGNITUDES (main.cpp:877, despues de que steer()
        # les saca el signo). El sentido de verdad esta en fl_dir/fr_dir:
        # izquierda dir 0 = adelante, derecha dir 1 = adelante. Con eso el
        # avance del CENTRO por encoders es (v_izq + v_der)/2 CON SIGNO.
        vi = RR.col(a, "fl_rpm") * np.where(RR.col(a, "fl_dir") == 0, 1.0, -1.0)
        vd = RR.col(a, "fr_rpm") * np.where(RR.col(a, "fr_dir") == 1, 1.0, -1.0)
        vcen = (vi + vd) / 2.0 * RPM_A_CMS
        print("  %-28s %8.1f d/s %8.2f c/s %9.1f d/s %8.2f c/s" % (
            nom, p50(gz[mem]), p50(np.abs(vcen[mem])),
            p50(gz[lo]), p50(np.abs(vcen[lo]))))

    # -----------------------------------------------------------------
    print("\n  B. SIMULADO (REPLAY OPEN LOOP de la maquina de estados de HOY sobre el")
    print("     rxsteer grabado). Mismo simulador que valido 58,5 % contra 61,5 %")
    print("     medido en la unica corrida que corrio esta config.\n")
    print("  BARRIDO DE LA BANDA PREREGISTRADA")
    print("  gain  ENTRA  age  |  %pista  %MEM   |  piso  |  rot p50  R p50   vc/vel  vc cm/s | rot=1 NIVEL")
    filas = []
    for gain in (1.30, 1.35, 1.40):
        for entra in (0.55, 0.60, 0.65):
            for agemax in (None, 100):
                nn = mm = 0
                acu_r, acu_R, acu_ratio, acu_vc = [], [], [], []
                niv_hoy = niv_fix = 0
                for nom, a, _ in datos:
                    absS = abs_steer(a, gain)
                    t_ms = (RR.col(a, "us") - RR.col(a, "us")[0]) / 1000.0
                    age = RR.col(a, "rxage")
                    val = np.ones(len(absS), dtype=bool) if agemax is None \
                        else ((age >= 0) & (age <= agemax))
                    en = simular_latch(absS, t_ms, entra)
                    rh = rot_hoy(absS, en)
                    rf = rot_fix(absS, en, entra, 0.681)
                    mem = val & en & (absS < entra) & (absS < PIV_PUNTUAL)
                    nn += int(val.sum())
                    mm += int(mem.sum())
                    vel = vel_firmware(absS)
                    acu_r.append(rf[mem])
                    acu_R.append(radio(rf)[mem])
                    acu_ratio.append(1.0 - rf[mem])
                    acu_vc.append(vel[mem] * (1.0 - rf[mem]) * RPM_A_CMS)
                    niv_hoy += int((val & (rh >= 0.9999) &
                                    ((absS >= entra) | (absS >= PIV_PUNTUAL))).sum())
                    niv_fix += int((val & (rf >= 0.9999) &
                                    ((absS >= entra) | (absS >= PIV_PUNTUAL))).sum())
                r = np.concatenate(acu_r)
                Rr = np.concatenate(acu_R)
                ra = np.concatenate(acu_ratio)
                vc = np.concatenate(acu_vc)
                filas.append((gain, entra, agemax, 100.0 * mm / nn,
                              p50(r), p50(Rr), p50(ra), p50(vc),
                              niv_hoy, niv_fix))
                print("  %.2f  %.2f  %4s |  %6d %5.1f%% |  0.681 |  %6.3f %6.2f  %6.3f  %6.2f  | %6d = %6d %s"
                      % (gain, entra, "-" if agemax is None else agemax,
                         nn, 100.0 * mm / nn, p50(r), p50(Rr), p50(ra), p50(vc),
                         niv_hoy, niv_fix, "OK" if niv_hoy == niv_fix else "**ROTO**"))

    memmin = min(f[3] for f in filas)
    memmax = max(f[3] for f in filas)
    Rmin = min(f[5] for f in filas)
    Rmax = max(f[5] for f in filas)
    ramin = min(f[6] for f in filas)
    h3 = all(f[8] == f[9] for f in filas)
    print("\n  H-M1  memoria en la banda: min %.1f %%  max %.1f %%   (falsador: >= 10 %%)  -> %s"
          % (memmin, memmax, "SOBREVIVE" if memmin >= 10.0 else "SE CAE"))
    print("  H-M2  R p50 en la banda:    min %.2f cm max %.2f cm (falsador: [3,0 ; 8,0]) -> %s"
          % (Rmin, Rmax, "SOBREVIVE" if (Rmin >= 3.0 and Rmax <= 8.0) else "SE CAE"))
    print("        v_centro/vel p50:     min %.3f            (falsador: >= 0,20, hoy 0,000) -> %s"
          % (ramin, "SOBREVIVE" if ramin >= 0.20 else "SE CAE"))
    print("  H-M3  rot=1 por NIVEL identico con y sin fix en las %d celdas -> %s"
          % (len(filas), "SOBREVIVE" if h3 else "REFUTADA"))

    # -----------------------------------------------------------------
    print("\n  C. CONTROL POSITIVO C-1: con el piso en 1.000 el fix es la identidad")
    peor = 0.0
    for nom, a, _ in datos:
        absS = abs_steer(a, 1.35)
        t_ms = (RR.col(a, "us") - RR.col(a, "us")[0]) / 1000.0
        en = simular_latch(absS, t_ms, 0.60)
        d = np.max(np.abs(rot_fix(absS, en, 0.60, 1.000) - rot_hoy(absS, en)))
        peor = max(peor, float(d))
    print("     max |rot_fix(piso=1.000) - rot_hoy| sobre las 6 corridas = %.1e  -> %s"
          % (peor, "PASA" if peor == 0.0 else "FALLA"))

    # -----------------------------------------------------------------
    print("\n  D. BARRIDO DEL PISO (la constante que se tunea el sabado)")
    print("     gain 1.35, ENTRA 0.60, sin filtro de frescura\n")
    print("  piso   R que traza  |  rot p50 mem  R p50 mem  vc/vel p50  vc cm/s  | avance recuperado")
    for piso in (1.000, 0.800, 0.681, 0.600, 0.500):
        acu_r, acu_R, acu_ra, acu_vc, gan = [], [], [], [], 0.0
        for nom, a, _ in datos:
            absS = abs_steer(a, 1.35)
            t_ms = (RR.col(a, "us") - RR.col(a, "us")[0]) / 1000.0
            en = simular_latch(absS, t_ms, 0.60)
            rf = rot_fix(absS, en, 0.60, piso)
            rh = rot_hoy(absS, en)
            mem = en & (absS < 0.60) & (absS < PIV_PUNTUAL)
            vel = vel_firmware(absS)
            acu_r.append(rf[mem])
            acu_R.append(radio(rf)[mem])
            acu_ra.append(1.0 - rf[mem])
            acu_vc.append(vel[mem] * (1.0 - rf[mem]) * RPM_A_CMS)
            gan += float(np.sum((rh[mem] - rf[mem]) * vel[mem] * RPM_A_CMS * DT))
        r = np.concatenate(acu_r)
        print("  %.3f  %10.2f cm |  %10.3f %10.2f %11.3f %8.2f  | %8.1f cm" % (
            piso, B_EFF * (1 - piso) / (2 * piso) if piso < 1 else 0.0,
            p50(r), p50(np.concatenate(acu_R)), p50(np.concatenate(acu_ra)),
            p50(np.concatenate(acu_vc)), gan))

    # -----------------------------------------------------------------
    print("\n  E. CONTRA EL FIX (5) QUE YA EXISTE (techo global rot <= 0,681)")
    print("     gain 1.35, ENTRA 0.60, sin filtro. Cuanto tiempo de pista toca cada uno\n")
    tocado5 = tocado7 = ntot = 0
    piv5 = 0
    for nom, a, _ in datos:
        absS = abs_steer(a, 1.35)
        t_ms = (RR.col(a, "us") - RR.col(a, "us")[0]) / 1000.0
        en = simular_latch(absS, t_ms, 0.60)
        rh = rot_hoy(absS, en)
        r5 = np.minimum(rh, 0.681)
        r7 = rot_fix(absS, en, 0.60, 0.681)
        ntot += len(absS)
        tocado5 += int(np.sum(r5 != rh))
        tocado7 += int(np.sum(r7 != rh))
        piv5 += int(np.sum((absS >= PIV_PUNTUAL) & (r5 != rh)))
    print("     fix (5) techo global : cambia %5.1f %% del tiempo de pista (%.1f s)"
          % (100.0 * tocado5 / ntot, tocado5 * DT))
    print("     fix (7) solo memoria : cambia %5.1f %% del tiempo de pista (%.1f s)"
          % (100.0 * tocado7 / ntot, tocado7 * DT))
    print("     el (5) le saca el giro en el lugar en %.1f s en los que la vision"
          % (piv5 * DT))
    print("     estaba pidiendo FONDO DE ESCALA (absSteer >= 0,92). El (7) ahi no")
    print("     toca nada: 0,0 s por construccion.")


if __name__ == "__main__":
    main()
