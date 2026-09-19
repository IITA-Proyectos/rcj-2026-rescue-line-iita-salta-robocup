# -*- coding: utf-8 -*-
"""
APENDICE POST-HOC DE zona_muerta.py  --  ESCRITO DESPUES DE VER LOS DATOS.

    python zona_muerta_apendice.py

ESTO NO ES CONFIRMATORIO. Se escribe porque el CONTROL PREREGISTRADO C-H FALLO
y, cuando un control falla, la regla del equipo es NO reportar el veredicto de
esa hipotesis y averiguar por que fallo. Nada de lo que sale de aca puede
contarse como "H-Z5 confirmada": es DIAGNOSTICO DEL METODO.

QUE FALLO
---------
C-H pedia que `pista_pivote_sin_histeresis` diera fraccion pegajosa ~ 0. Dio
70,8 % (E3). Leyendo la nota del CSV se ve por que la premisa del control era
mala:

    con_histeresis   "HISTERESIS pivote 0.60/0.15"
    sin_histeresis   "LINE_PIVOTE_DESDE=0.60, rampa concava exp 0.5"

La corrida "sin histeresis" NO es "sin maquina de estado de pivote": tiene un
UMBRAL DE ENTRADA en absSteer 0,60 -mas bajo que el 0,92 de la regla puntual-,
solo que sin el enganche a la salida. Las dos corridas producen rot = 1 con
`ram` < 3. El control, tal como lo escribi, NO SEPARA "umbral bajo" de
"histeresis". El control esta mal, no el robot.

Y ADEMAS: E2 ESTA CONFUNDIDO POR EL DESFASAJE rxsteer -> rot
-----------------------------------------------------------
E2 usaba S_hi = max{|steer| con rot < 1} y el argumento de monotonia. El
argumento exige que `rot` y `rxsteer` de la MISMA FILA vengan de la misma vuelta
del lazo, y no vienen: `rxsteer` es `g_rx_steer`, que se actualiza cuando llega
la trama, mientras que `rot` es `robot._rotation`, que solo se recalcula en la
proxima vuelta. Por eso S_hi dio 0,88-0,98 en las seis corridas -o sea "el
umbral es > 0,88"- cuando las notas dicen 0,35 y 0,60: es el desfasaje, no el
umbral. UNA SOLA FILA con el comando fresco y el `rot` viejo tira el maximo
arriba de todo y arrastra a E2 al 85 %.

CORRECCION DE UN ERROR MIO: los 65-70 ms que midio retardo_real.py son el
retardo `rot` -> `gz`, o sea COMANDO -> GIRO REAL, que es MECANICO. El
desfasaje que confunde a E2 es otro -`rxsteer` -> `rot`, que es de SOFTWARE- y
esta acotado por el periodo del lazo (p50 35-40 ms, segundo modo 65-80 ms). Por
eso el apendice lo MIDE aparte en la seccion A2 en vez de suponerlo.

LO QUE MIDE ESTE APENDICE
-------------------------
A. BARRIDO DEL DESFASAJE. E1/E2 recalculados alineando |steer| L muestras antes.
   Si el efecto se derrite cerca de L = 13-14, era artefacto del desfasaje.

B. LA FIRMA DIRECTA DE LA HISTERESIS: ENTRADA contra SALIDA. Una regla puntual
   entra y sale en el MISMO |steer| (ancho ~ 0). Una histeresis entra en T_alto
   y sale en T_bajo. Se mide el |steer| en el borde de subida y en el de bajada
   de cada episodio de rot = 1, con y sin alinear por el desfasaje.
       ancho = mediana(entrada) - mediana(salida)
   Con la histeresis 0,60/0,15 declarada, el ancho esperado en unidades de
   `steer` es 0,60/1,35 - 0,15/1,35 = 0,444 - 0,111 = 0,333.

A2. EL DESFASAJE rxsteer -> rot, MEDIDO. Correlacion cruzada de |steer| contra
   |rot| y, ademas, la distancia real en muestras entre el flanco de subida de
   |steer| y el flanco de subida de rot = 1. Esto acota lo que puede explicar el
   desfasaje y lo que no.

C. LA PRUEBA INMUNE AL DESFASAJE. Dentro de cada episodio de rot = 1, la racha
   CONTINUA mas larga con |steer| <= q. Ninguna regla SIN MEMORIA con un
   desfasaje acotado por el periodo del lazo puede sostener rot = 1 con el
   comando bajo durante mas de un periodo. Si dura 150 ms o mas -o sea 2 a 4
   periodos- hay MEMORIA, y la memoria es el pegajoso.
   Banda: q en {0.111, 0.20, 0.30, 0.444, 0.50} y duracion en
   {100, 150, 200, 300} ms.

D. EL EPISODIO SATURADO DE 16,5 s de `pivote_con_histeresis`, que es un outlier
   de un orden de magnitud y hay que mirarlo antes de promediarlo con el resto.
"""

import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from zona_muerta import (MS, ROT1, AGE_BASE, cargar_pista, episodios, pct, sec,
                         val)                                          # noqa

LAG_MEDIDO = 14                 # muestras; 70 ms, medido por retardo_real.py
BANDA_LAG = (0, 2, 4, 7, 10, 12, 14, 16, 20)
# q se compara contra los umbrales DECLARADOS en las notas de los CSV
# (0,15 y 0,60 en unidades de absSteer -> 0,111 y 0,444 en unidades de steer):
# no son valores elegidos para que de lindo, son los de la config.
BANDA_Q = (0.111, 0.20, 0.30, 0.444, 0.50)
BANDA_MEM_MS = (100, 150, 200, 300)


def shift(x, L):
    """|steer| de L muestras ANTES (el que causo el rot de esta fila)."""
    if L == 0:
        return x
    y = np.empty_like(x)
    y[:L] = x[0]
    y[L:] = x[:-L]
    return y


def a_barrido_lag(runs):
    print("=" * 84)
    print("A. BARRIDO DEL DESFASAJE COMANDO -> rot  (E1 y E2 realineados)")
    print("=" * 84)
    print("El desfasaje NO se elige aca: 13-14 muestras es lo que midio")
    print("retardo_real.py contra el giroscopio del BNO055, antes y aparte.")
    print()
    print("  %4s %6s | %8s %8s | %8s %8s"
          % ("lag", "ms", "E1 n", "E1 %", "E2 n", "E2 %"))
    for L in BANDA_LAG:
        e1t = e2t = n1t = 0
        for d in runs:
            m = val(d, AGE_BASE)
            sa = shift(d["s"], L)
            rot1 = (d["rot"] >= ROT1) & m
            base = sa[m & (d["rot"] < ROT1)]
            S_hi = float(np.max(base)) if len(base) else 0.0
            e1t += int((rot1 & (sa * 1.35 < 0.92)).sum())
            e2t += int((rot1 & (sa < S_hi)).sum())
            n1t += int(rot1.sum())
        print("  %4d %6.0f | %8d %7.1f%% | %8d %7.1f%%"
              % (L, L * MS, e1t, 100.0 * e1t / n1t, e2t, 100.0 * e2t / n1t))
    print()
    print("  S_hi realineado a lag 14 (compararlo con el umbral declarado en la nota):")
    for d in runs:
        m = val(d, AGE_BASE)
        sa = shift(d["s"], LAG_MEDIDO)
        base = sa[m & (d["rot"] < ROT1)]
        print("    %-24s S_hi(L=0) = %.3f   S_hi(L=14) = %.3f   p99(L=14) = %.3f"
              % (d["n"], float(np.max(shift(d["s"], 0)[m & (d["rot"] < ROT1)])),
                 float(np.max(base)), float(np.percentile(base, 99))))
    print()


def a2_desfasaje(runs):
    print("=" * 84)
    print("A2. EL DESFASAJE rxsteer -> rot, MEDIDO (no supuesto)")
    print("=" * 84)
    print("Dos estimadores: (i) correlacion cruzada |steer| vs |rot|, (ii) la")
    print("distancia en muestras entre el flanco de subida de |steer| por encima")
    print("del umbral efectivo y el flanco de subida de rot = 1.")
    print()
    print("  %-24s %10s %10s | %10s %10s %10s"
          % ("corrida", "lag_xcorr", "ms", "flanco p50", "p90", "max"))
    for d in runs:
        m = val(d, AGE_BASE)
        x = d["s"][m] - d["s"][m].mean()
        y = d["rot"][m] - d["rot"][m].mean()
        best, bl = -2.0, 0
        for L in range(0, 41):
            n = len(x) - L
            if n < 200:
                break
            a, b = x[:n], y[L:L + n]
            c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
            if c > best:
                best, bl = c, L
        # flancos: para cada subida de rot=1, cuantas muestras antes subio |steer|
        r1 = (d["rot"] >= ROT1) & m
        subs = [i for i, f in episodios(r1, dmin=2)]
        dist = []
        for i in subs:
            # el |steer| que lo causo: primera muestra hacia atras (max 40) donde
            # |steer| ya estaba en su nivel alto (>= el |steer| del propio flanco)
            s0 = d["s"][i]
            k = 0
            while k < 40 and i - k - 1 >= 0 and d["s"][i - k - 1] >= s0 - 1e-9:
                k += 1
            dist.append(k)
        dist = np.array(dist) if dist else np.array([0])
        print("  %-24s %10d %10.0f | %10.0f %10.0f %10.0f"
              % (d["n"], bl, bl * MS, pct(dist, 50) * MS, pct(dist, 90) * MS,
                 dist.max() * MS))
    print()
    print("  El lag de xcorr es el desfasaje MEDIO de la senal entera; el de")
    print("  flanco es cuanto tiempo el comando YA estaba alto antes de que rot")
    print("  subiera. Los dos acotan lo que el desfasaje puede explicar.")
    print()


def b_entrada_salida(runs):
    print("=" * 84)
    print("B. FIRMA DIRECTA DE LA HISTERESIS: |steer| DE ENTRADA vs DE SALIDA")
    print("=" * 84)
    print("Una regla puntual entra y sale en el mismo |steer|: ancho ~ 0.")
    print("Una histeresis 0,60/0,15 (absSteer) da ancho 0,444 - 0,111 = 0,333 en")
    print("unidades de `steer`. Se reporta con L = 0 y con L = 14 (70 ms).")
    print()
    for L in (0, LAG_MEDIDO):
        print("  --- alineado L = %d muestras (%.0f ms) ---" % (L, L * MS))
        print("  %-24s %5s | %7s %7s | %7s %7s | %8s"
              % ("corrida", "epis", "ent p50", "ent p25", "sal p50", "sal p75",
                 "ANCHO"))
        for d in runs:
            m = val(d, AGE_BASE)
            sa = shift(d["s"], L)
            eps = episodios((d["rot"] >= ROT1) & m, dmin=2)
            if not eps:
                print("  %-24s %5d" % (d["n"], 0))
                continue
            ent = np.array([sa[i] for i, f in eps])
            sal = np.array([sa[f - 1] for i, f in eps])
            print("  %-24s %5d | %7.3f %7.3f | %7.3f %7.3f | %8.3f"
                  % (d["n"], len(eps), pct(ent, 50), pct(ent, 25),
                     pct(sal, 50), pct(sal, 75), pct(ent, 50) - pct(sal, 50)))
        print()


def c_memoria(runs):
    print("=" * 84)
    print("C. PRUEBA INMUNE AL DESFASAJE: rot = 1 SOSTENIDO CON EL COMANDO BAJO")
    print("=" * 84)
    print("Dentro de cada episodio de rot = 1, la racha CONTINUA mas larga con")
    print("|steer| <= q. Con un retardo acotado de ~70 ms, ninguna regla sin")
    print("memoria puede sostener eso 150 ms o mas. Si pasa, hay MEMORIA.")
    print()
    for q in BANDA_Q:
        print("  --- q = %.3f  (absSteer <= %.2f) ---" % (q, q * 1.35))
        print("  %-24s %6s | " % ("corrida", "ep r1")
              + " ".join("%6dms" % t for t in BANDA_MEM_MS)
              + " | %8s" % "t_memoria")
        for d in runs:
            m = val(d, AGE_BASE)
            eps = episodios((d["rot"] >= ROT1) & m, dmin=2)
            largos, t_mem = [], 0.0
            for i, f in eps:
                sub = d["s"][i:f] <= q
                mx, cur = 0, 0
                for v in sub:
                    cur = cur + 1 if v else 0
                    mx = max(mx, cur)
                largos.append(mx * MS)
                t_mem += int(sub.sum()) * MS
            largos = np.array(largos) if largos else np.array([0.0])
            print("  %-24s %6d | " % (d["n"], len(eps))
                  + " ".join("%8d" % int(np.sum(largos >= t)) for t in BANDA_MEM_MS)
                  + " | %7.1fs" % (t_mem / 1000.0))
        tot = {t: 0 for t in BANDA_MEM_MS}
        tmt = 0.0
        for d in runs:
            m = val(d, AGE_BASE)
            for i, f in episodios((d["rot"] >= ROT1) & m, dmin=2):
                sub = d["s"][i:f] <= q
                mx, cur = 0, 0
                for v in sub:
                    cur = cur + 1 if v else 0
                    mx = max(mx, cur)
                for t in BANDA_MEM_MS:
                    if mx * MS >= t:
                        tot[t] += 1
                tmt += int(sub.sum()) * MS
        print("  %-24s %6s | " % ("TODAS", "")
              + " ".join("%8d" % tot[t] for t in BANDA_MEM_MS)
              + " | %7.1fs" % (tmt / 1000.0))
        print()


def d_outlier(runs):
    print("=" * 84)
    print("D. EL EPISODIO SATURADO DE 16,5 s (outlier de un orden de magnitud)")
    print("=" * 84)
    thr = 1.0 / 1.35
    for d in runs:
        m = val(d, AGE_BASE)
        eps = episodios((d["s"] >= thr) & m, dmin=1)
        if not eps:
            continue
        dur = np.array([(f - i) * MS for i, f in eps])
        j = int(np.argmax(dur))
        if dur[j] < 3000:
            continue
        i, f = eps[j]
        print("  corrida: %s" % d["n"])
        print("    episodio %d de %d, %.0f ms = %.0f %% de todo el tiempo saturado"
              % (j + 1, len(eps), dur[j], 100.0 * dur[j] / dur.sum()))
        print("    indices %d..%d   |steer| p50 %.3f   rot p50 %.3f"
              % (i, f, pct(d["s"][i:f], 50), pct(d["rot"][i:f], 50)))
        print("    |gz| medio %.1f d/s   v_enc medio %.2f cm/s   rxage p50 %.0f ms"
              % (np.mean(np.abs(d["gz"][i:f])), np.mean(d["v_enc"][i:f]),
                 pct(d["age"][i:f], 50)))
        print("    -> si |gz| ~ 0 y v_enc ~ 0 con comando fresco, el robot estaba")
        print("       TRABADO, y ese tramo no es 'seguir la linea saturado'.")
        print()
        print("    SIN ese episodio, la corrida %s da:" % d["n"])
        dur2 = np.delete(dur, j)
        print("      %d episodios  p50 %.0f ms  max %.0f ms  total %.1f s"
              % (len(dur2), pct(dur2, 50), dur2.max(), dur2.sum() / 1000.0))
        print()
    print("  RECUENTO GLOBAL SIN NINGUN EPISODIO SATURADO > 3 s:")
    tot, dall = 0, []
    for d in runs:
        m = val(d, AGE_BASE)
        for i, f in episodios((d["s"] >= thr) & m, dmin=1):
            if (f - i) * MS <= 3000:
                tot += 1
                dall.append((f - i) * MS)
    dall = np.array(dall)
    print("    %d episodios  p50 %.0f ms  p90 %.0f ms  max %.0f ms  total %.1f s"
          % (tot, pct(dall, 50), pct(dall, 90), dall.max(), dall.sum() / 1000.0))
    n_val = sum(int(np.sum(val(d, AGE_BASE))) for d in runs)
    print("    = %.1f %% del tiempo de pista (contra 18,5 %% con el outlier dentro)"
          % (100.0 * dall.sum() / MS / n_val))
    print()


# =============================================================================
# E. LA CONFIG DE HOY, SIMULADA SOBRE EL rxsteer GRABADO
#
# HALLAZGO QUE OBLIGA A ESTA SECCION: main.cpp:104 define hoy
#     LINE_PIVOTE_ENTRA = 0.60   LINE_PIVOTE_SALE = 0.15
#     LINE_PIVOTE_CONFIRMA_MS = 0   LINE_PIVOTE_MAX_MS = 2500
# o sea que el pivote NO engancha en absSteer 0,92 como decia la premisa del
# encargo: engancha en 0,60. Con gain 1.35 eso es |steer| >= 0,444, o sea
# CUARENTA GRADOS de imagen, no 61,3. Y no suelta hasta |steer| <= 0,111
# (10 grados) o hasta los 2500 ms.
#
# Y la corrida `pista_pivote_con_histeresis` ("HISTERESIS pivote 0.60/0.15") es
# EXACTAMENTE esa config: es la unica de las seis que corre el pivote de hoy.
#
# LIMITE DE ESTE REPLAY, dicho antes del numero: es OPEN LOOP. Se le da a la
# maquina de estados el rxsteer que la Pi mando EN OTRA corrida; si el robot se
# hubiera movido distinto, la Pi habria mandado otra cosa. NO prueba una
# politica: caracteriza el MAPEO. Ademas se simula a 200 Hz y el lazo va a 28,
# lo que da MAS oportunidades de salir -o sea que el tiempo enganchado que sale
# de aca es una COTA INFERIOR-.
# =============================================================================
def e_config_de_hoy(runs):
    print("=" * 84)
    print("E. LA MAQUINA DE ESTADOS DE HOY (ENTRA 0.60 / SALE 0.15 / MAX 2500 ms)")
    print("=" * 84)
    print("REPLAY OPEN LOOP sobre el rxsteer grabado. Cota INFERIOR del enganche.")
    print("gain 1.35 -> entra en |steer| >= 0.444 (40 grados), sale en <= 0.111 (10).")
    print()
    print("  %-24s %8s %8s %8s %8s %9s %9s"
          % ("corrida", "t rot=1", "% pista", "episod", "p50 ms", "p90 ms", "por MAX"))
    T_ENTRA, T_SALE, MAXMS = 0.60, 0.15, 2500.0
    tot_t = tot_n = tot_max = 0
    tot_val = 0
    durs_all = []
    for d in runs:
        m = val(d, AGE_BASE)
        aS = np.minimum(d["s"] * 1.35, 1.0)
        piv = np.zeros(len(aS), dtype=bool)
        en, t0 = False, 0.0
        n_max = 0
        for i in range(len(aS)):
            if not m[i]:
                en = False
                continue
            t = i * MS
            if not en and aS[i] >= T_ENTRA:
                en, t0 = True, t
            elif en:
                if aS[i] <= T_SALE:
                    en = False
                elif t - t0 > MAXMS:
                    en = False
                    n_max += 1
            piv[i] = en
        eps = episodios(piv, dmin=1)
        dur = np.array([(f - i) * MS for i, f in eps]) if eps else np.array([0.0])
        nv = int(m.sum())
        tot_t += int(piv.sum()); tot_n += len(eps); tot_max += n_max; tot_val += nv
        durs_all.append(dur)
        print("  %-24s %7.1fs %7.1f%% %8d %8.0f %9.0f %9d"
              % (d["n"], sec(piv.sum()), 100.0 * piv.sum() / max(1, nv),
                 len(eps), pct(dur, 50), pct(dur, 90), n_max))
    da = np.concatenate(durs_all)
    print("  %-24s %7.1fs %7.1f%% %8d %8.0f %9.0f %9d"
          % ("TODAS", sec(tot_t), 100.0 * tot_t / max(1, tot_val), tot_n,
             pct(da, 50), pct(da, 90), tot_max))
    print()
    print("  Contra lo MEDIDO en la unica corrida que corrio esta config:")
    for d in runs:
        if "con_histeresis" not in d["n"]:
            continue
        m = val(d, AGE_BASE)
        r1 = (d["rot"] >= ROT1) & m
        print("    %s: rot=1 REAL %.1f s (%.1f %% de la corrida)"
              % (d["n"], sec(r1.sum()), 100.0 * r1.sum() / max(1, int(m.sum()))))
    print()
    print("  FRACCION DEL TIEMPO POR ENCIMA DE CADA UMBRAL (nivel, sin memoria):")
    S = np.concatenate([d["s"][val(d, AGE_BASE)] for d in runs])
    for thr, etq in ((0.4444, "ENTRA del pivote de HOY (absSteer 0.60, 40 gr)"),
                     (0.6815, "regla puntual 0.92 (61.3 gr)"),
                     (0.7407, "saturacion del clamp (66.7 gr)"),
                     (0.1111, "SALE del pivote de HOY (absSteer 0.15, 10 gr)")):
        print("    |steer| >= %.4f  %-46s %6.1f %%  %6.1f s"
              % (thr, etq, 100.0 * np.mean(S >= thr), sec(np.sum(S >= thr))))
    print()


def main():
    runs = cargar_pista()
    print()
    a_barrido_lag(runs)
    a2_desfasaje(runs)
    b_entrada_salida(runs)
    c_memoria(runs)
    d_outlier(runs)
    e_config_de_hoy(runs)


if __name__ == "__main__":
    main()
