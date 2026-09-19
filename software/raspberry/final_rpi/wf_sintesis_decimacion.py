# -*- coding: utf-8 -*-
"""
DECIMACION - el banco mide a 33,3 Hz un comando que el robot cambia a 8,6-20,6 Hz.

DE DONDE SALE
-------------
commit 4c1d456 (fix de firmware PENDIENTE DE BANCO): el `while (rutina=="linea")`
llamaba leer_tof() en cada vuelta y el VL53L0X hace espera activa (~33 ms).
Medido sobre 7673 periodos en 6 corridas: p50 = 30 ms, segundo modo en 65 ms.
"La Pi manda a 66-86 Hz y EL COMANDO CAMBIA A 8,6-20,6 Hz. Tres de cada cuatro
tramas de vision se descartan."

TODO el banco de vision (ab_v2_v3_v4.metricas) evalua la serie a 33,3 Hz, o sea
CADA frame. El robot de hoy no consume cada frame. Pregunta:

  las conclusiones de percepcion (CAMINO+MONO mejor que BASE; V1 pierde en
  saltos) SOBREVIVEN al punto de operacion que el robot realmente tiene?

MODELO, declarado ANTES de correr
---------------------------------
La Pi procesa TODOS los frames (su lazo corre mas rapido que el video), y lo que
se pierde es el CONSUMO del comando. Entonces la decimacion se aplica a la SERIE
DE SALIDA, no a la entrada del tracker: el estado interno (prev_target, medias
moviles) NO se toca. Es el modelo fiel del hallazgo del firmware.

BANDA PREREGISTRADA:  D = 1, 2, 3, 4
  D=1 el banco de hoy (33,3 Hz).
  D=2 y D=3 encierran la banda medida 8,6-20,6 Hz contra 33,3 fps de video.
  D=4 el caso literal "tres de cada cuatro tramas se descartan".
Para cada D se promedian las D FASES (offset 0..D-1) para que el resultado no
dependa de con que frame arranca la ventana.

FALSADOR, escrito ANTES de correr
---------------------------------
H: el ORDEN de las variantes es invariante en D.
  Si se sostiene -> el punto de operacion no importa y las conclusiones
     de percepcion transfieren tal cual.
  Si se rompe    -> la comparacion se hizo a una tasa que el robot no tiene.
PREDICCION ESPECIFICA (falsable): `saltos>24` de CAMINO+MONO tiene que SUBIR mas
rapido con D que la de V1, porque el tope de C+M es 24 px POR FRAME
(SpatialTargetGuard) y a D=4 ese tope deja pasar hasta 96 px, mientras que el de
V1 (31,8 px = 159/5, cota del promedio de 5 frames) tambien se relaja pero desde
un valor mas alto y sin ser un clamp duro. Si a D>=3 C+M deja de ganar en saltos,
la unica metrica en la que C+M le gana a V1 es un artefacto del punto de
operacion.
Falsador del falsador: si `disp` cambia mas de 0,5 pp con D, la decimacion esta
haciendo algo que no deberia (disp es una proporcion y no deberia moverse).

FIDELIDAD
---------
1) con camino=False y mono=False el espia de camino_principal.instalar tiene que
   reproducir EXACTAMENTE el target de la candidata (CHK). Aborta si no.
2) D=1 tiene que reproducir el BASELINE ABSOLUTO publicado
   (93,78 / 864 / 276 / 247 / 392 / 1,91). Si no, el arnes esta mal conectado y
   no se mira nada mas.

NO TOCA NINGUN ARCHIVO COMPARTIDO. Importa camino_principal y
airborne_v1_adaptado sin modificarlos.

    python wf_sintesis_decimacion.py
"""

import importlib.util
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
BANDA_D = [1, 2, 3, 4]


def _mod(nombre, arch):
    sp = importlib.util.spec_from_file_location(
        nombre, os.path.join(AQUI, arch))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def serie_sk(SinBranch, v2, ruta, fps, desde=0, hasta=10 ** 9):
    """Serie de la rama ESQUELETO (BASE / CAMINO+MONO)."""
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(fps)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            t = r.get("target")
            out.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                r.get("state")))
        i += 1
    cap.release()
    return out


def serie_v1(a1, ruta, fps, desde=0, hasta=10 ** 9):
    """Serie de la rama POI (Airborne V1). Misma ley de steer."""
    cap = cv2.VideoCapture(ruta)
    tr = a1.AirborneV1(fps)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.paso(a1.frame_de_la_pi(fr))
        if i >= desde:
            t = r.get("target")
            out.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - a1.CENTER) / (a1.W / 2.0), -90, 90)),
                r.get("estado")))
        i += 1
    cap.release()
    return out


def agregar(series):
    """Suma AB.metricas sobre una lista de series (los 10 autonomos)."""
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, suav=[])
    for s in series:
        m = AB.metricas(s)
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
        tot["suav"].append(m["suav"])
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav"]))
    return tot


def decimar(series, D):
    """Promedia las D fases. Devuelve el agregado medio sobre las fases."""
    if D == 1:
        return agregar(series)
    acc = None
    for off in range(D):
        t = agregar([s[off::D] for s in series])
        if acc is None:
            acc = dict((k, 0.0) for k in t)
        for k in t:
            acc[k] += t[k]
    for k in acc:
        acc[k] /= float(D)
    return acc


def fila(nom, t):
    return ("  %-14s %8.2f %9.1f %8.1f %10.1f %11.1f %8.2f"
            % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
               t["inv"], t["suav"]))


def main():
    v4 = _mod("nuevo_code_v4", "nuevo_code_v4.py")
    v2 = v4.v3.v2
    cp = _mod("camino_principal", "camino_principal.py")
    a1 = _mod("airborne_v1_adaptado", "airborne_v1_adaptado.py")
    SinBranch = cp.hacer_sinbranch(v4)

    vids = [os.path.join(AQUI, v) for v in AB.AUTONOMOS]
    vids = [v for v in vids if os.path.exists(v)]

    print("")
    print("=" * 104)
    print("  DECIMACION DEL COMANDO - el banco mide 33,3 Hz, el robot cambia el")
    print("  comando a 8,6-20,6 Hz (commit 4c1d456, ToF bloqueante en el lazo).")
    print("  Banda preregistrada D = 1,2,3,4, promediando las D fases.")
    print("=" * 104)
    print("")

    guardado = {}

    # ---- BASE (con el espia instalado y APAGADO: chequeo de fidelidad) ----
    cp.CHK["n"] = cp.CHK["mal"] = 0
    rest = cp.instalar(v2, dict(camino=False, mono=False))
    guardado["BASE"] = [serie_sk(SinBranch, v2, v, FPS) for v in vids]
    rest()
    print("  FIDELIDAD (espia apagado contra la candidata): %d frames, "
          "%d discrepancias  %s"
          % (cp.CHK["n"], cp.CHK["mal"],
             "OK" if cp.CHK["mal"] == 0 else "*** ABORTA"))
    if cp.CHK["mal"]:
        return 3

    # ---- CAMINO+MONO ----
    rest = cp.instalar(v2, dict(camino=True, mono=True))
    guardado["CAMINO+MONO"] = [serie_sk(SinBranch, v2, v, FPS) for v in vids]
    rest()

    # ---- V1 ----
    guardado["V1"] = [serie_v1(a1, v, FPS) for v in vids]

    # control de que las variantes estan VIVAS
    pa = [x for s in guardado["BASE"] for x in s]
    pb = [x for s in guardado["CAMINO+MONO"] for x in s]
    dif = 0
    for a, b in zip(pa, pb):
        if (a[0] is None) != (b[0] is None):
            dif += 1
        elif a[0] is not None and b[0] is not None:
            if abs(a[0][0] - b[0][0]) > 1e-9 or abs(a[0][1] - b[0][1]) > 1e-9:
                dif += 1
    ntot = len(pa)
    print("  CONTROL de que la variante esta viva: CAMINO+MONO cambia %d de %d "
          "targets (%.1f %%)" % (dif, ntot, 100.0 * dif / max(ntot, 1)))
    print("")

    # ---- ANCLA: D=1 tiene que reproducir los numeros publicados ----
    print("-" * 104)
    print("  ANCLA D=1 (tiene que reproducir el BASELINE ABSOLUTO y las filas "
          "publicadas)")
    print("-" * 104)
    print("  %-14s %8s %9s %8s %10s %11s %8s"
          % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
             "inversiones", "suav"))
    a_base = agregar(guardado["BASE"])
    for nom in ("BASE", "CAMINO+MONO", "V1"):
        print(fila(nom, agregar(guardado[nom])))
    print("")
    esp = dict(disp=93.78, sin_aut=864, huecos=276, s_gt=247, inv=392, suav=1.91)
    ok = all(abs(a_base[k] - esp[k]) < (0.01 if k in ("disp", "suav") else 0.5)
             for k in esp)
    print("  BASELINE ABSOLUTO esperado 93.78 / 864 / 276 / 247 / 392 / 1.91"
          "   ->  %s" % ("REPRODUCE" if ok else "*** NO REPRODUCE, ABORTA"))
    if not ok:
        return 3

    # ---- controles obligatorios, solo a D=1 ----
    print("")
    ctl = []
    for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru) or not ex:
            continue
        rest = cp.instalar(v2, dict(camino=True, mono=True))
        s = serie_sk(SinBranch, v2, ru, fps, d0, h0)
        rest()
        s1 = serie_v1(a1, ru, fps, d0, h0)
        m, m1 = AB.metricas(s), AB.metricas(s1)
        st = [x for _t, x, _e in s if x is not None]
        st1 = [x for _t, x, _e in s1 if x is not None]
        ctl.append("%s C+M %d/%d V1 %d/%d" % (cn.split("_")[0], m["con"], ex,
                                              m1["con"], ex))
        if cn == "lineal_positivo":
            ctl.append("smax C+M %+.2f V1 %+.2f"
                       % (max(st) if st else 0, max(st1) if st1 else 0))
    print("  CONTROLES OBLIGATORIOS (D=1): " + " | ".join(ctl))

    # ---- BARRIDO DE D ----
    print("")
    print("-" * 104)
    print("  BARRIDO DE LA BANDA PREREGISTRADA (promedio de las D fases)")
    print("-" * 104)
    print("  %-14s %8s %9s %8s %10s %11s %8s"
          % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
             "inversiones", "suav"))
    res = {}
    for D in BANDA_D:
        print("  --- D = %d   (comando efectivo %.1f Hz) ---" % (D, FPS / D))
        for nom in ("BASE", "CAMINO+MONO", "V1"):
            t = decimar(guardado[nom], D)
            res[(nom, D)] = t
            print(fila(nom, t))

    # ---- LECTURA DEL FALSADOR ----
    print("")
    print("-" * 104)
    print("  FALSADOR: como cambia el ORDEN con D")
    print("-" * 104)

    def cmp(c, v, k, mejor_menor=True):
        d = c[k] - v[k]
        if abs(d) < 1e-9:
            return "%.1f vs %.1f empate" % (c[k], v[k])
        gana = "C+M" if ((d < 0) == mejor_menor) else "V1"
        return "%.1f vs %.1f -> %s" % (c[k], v[k], gana)

    print("  %-4s %26s %26s %26s"
          % ("D", "saltos>24 C+M|V1", "disp C+M|V1", "inversiones C+M|V1"))
    for D in BANDA_D:
        c, v = res[("CAMINO+MONO", D)], res[("V1", D)]
        print("  %-4d %26s %26s %26s"
              % (D, cmp(c, v, "s_gt"), cmp(c, v, "disp", False),
                 cmp(c, v, "inv")))

    print("")
    print("  falsador del falsador (disp no deberia moverse con D):")
    for nom in ("BASE", "CAMINO+MONO", "V1"):
        ds = [res[(nom, D)]["disp"] for D in BANDA_D]
        print("    %-14s disp  %s   rango %.2f pp"
              % (nom, "  ".join("%.2f" % x for x in ds), max(ds) - min(ds)))

    print("")
    print("  DELTAS CAMINO+MONO menos BASE, por D (asi se lee si la ganancia de")
    print("  CAMINO+MONO sobrevive al punto de operacion del robot)")
    print("  %-4s %9s %9s %8s %10s %11s %8s"
          % ("D", "disp %", "sin_aut", "huecos", "saltos>24", "inversiones",
             "suav"))
    for D in BANDA_D:
        c, b = res[("CAMINO+MONO", D)], res[("BASE", D)]
        print("  %-4d %+9.2f %+9.1f %+8.1f %+10.1f %+11.1f %+8.2f"
              % (D, c["disp"] - b["disp"], c["sin_aut"] - b["sin_aut"],
                 c["huecos"] - b["huecos"], c["s_gt"] - b["s_gt"],
                 c["inv"] - b["inv"], c["suav"] - b["suav"]))
    print("=" * 104)
    return 0


if __name__ == "__main__":
    sys.exit(main())
