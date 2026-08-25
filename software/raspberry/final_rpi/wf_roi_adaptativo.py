# -*- coding: utf-8 -*-
"""
ROI ADAPTATIVO sobre CAMINO+MONO - la idea de Airborne traducida a 160x120.

DE DONDE SALE
-------------
Airborne (2025) no usa un recorte fijo. Conmuta:

    default_crop = 0.45     en marcha normal
    turn_crop    = 0.75     cuando esta en giro forzado

Es decir: cuando la cosa se pone dificil, MIRA MAS CERCA. Menos suelo lejano
en el frame, menos posibilidad de que una rama que esta a 60 cm decida el
volante ahora.

Nuestra candidata usa un ROI FIJO: `FLOOR_TOP = 35` en nuevo_code_v2.py (mas el
recorte triangular de las dos esquinas altas, que ya esta anclado a FLOOR_TOP y
por lo tanto se mueve con el).

LOS NUMEROS DE AIRBORNE NO SON TRASLADABLES. Ellos corren a 448x252 y su crop
es una fraccion del alto. Nosotros corremos a 160x120 con el horizonte en la
fila 9, o sea que la parte util de la imagen ya esta comprimida contra el borde
inferior. Lo que se traslada es LA IDEA, no la constante.

QUE SE IMPLEMENTA
-----------------
Un ROI de dos posiciones, decidido con informacion del frame ANTERIOR (causal,
nada de mirar el futuro):

    ROI CORTO (FLOOR_TOP = alt)   si  estado(N-1) en {LOW, SIN_CERCA}
                                  o  |steer(N-1)| > UMBRAL
    ROI NORMAL (FLOOR_TOP = 35)   en cualquier otro caso

HIGH y MEDIUM devuelven el ROI normal, que es lo que pide la traduccion de
Airborne. PERDIDA se deja en ROI NORMAL a proposito: acortar el ROI cuando ya
se perdio la linea saca pixeles justo cuando hacen falta para reacquirir. Es la
lectura conservadora y queda declarada antes de correr.

BANDA PREREGISTRADA
-------------------
El pedido fija la banda del parametro principal:

    FLOOR_TOP alternativo:  35 (sin cambio) / 45 / 55 / 65

Pero el disparador tiene un SEGUNDO parametro (el umbral de |steer|) y elegirlo
despues de ver los resultados seria elegir el que mejor queda. Asi que se
preregistra tambien su banda y se corre la grilla COMPLETA:

    UMBRAL de |steer|:  30 / 45 / 60 / inf

`inf` no es relleno: es la variante de disparador PURO POR ESTADO (el steer
nunca acorta). Sirve para separar cual de los dos disparadores hace el trabajo.
Con FLOOR_TOP = 35 la variante es un no-op, asi que el umbral no aplica y se
corre una sola vez.

Total: 3 alturas x 4 umbrales + el no-op = 13 configuraciones.

DOS CHEQUEOS DE FIDELIDAD
-------------------------
1) Con CAMINO, MONO y ROI apagados, el selector re-implementado tiene que
   reproducir EXACTAMENTE el target de la candidata. Si hay una sola
   discrepancia, aborta.
2) La configuracion ROI35 tiene toda la maquineria del ROI adaptativo
   ENCENDIDA pero con altura alternativa igual a la normal. Su serie de targets
   tiene que ser identica, frame a frame, a la de CAMINO+MONO. Si no lo es, la
   maquineria tiene un efecto colateral y el resto de la tabla no vale nada.

REPLAY OPEN-LOOP: esto mide PERCEPCION sobre video grabado. No dice nada sobre
la trayectoria que el robot habria hecho.

    python wf_roi_adaptativo.py              grilla preregistrada + brazo post-hoc
    python wf_roi_adaptativo.py --mecanismo  por que acortar el ROI hace dano

===========================  RESULTADO (medido)  =============================
NEGATIVO, Y LIMPIO. 22 configuraciones corridas (13 preregistradas + 9
post-hoc). NINGUNA mejoro NINGUNA de las seis metricas. Ni una.

El dano es monotono con cuanto se acorta, contra CAMINO+MONO:

    FLOOR_TOP 45   disp -1.1 %   huecos +148
    FLOOR_TOP 55   disp -2.7 %   huecos +357
    FLOOR_TOP 65   disp -4.6 %   huecos +618

POR QUE (medido con --mecanismo, ROI forzado constante). No es la shell
geodesica: el fallback de la shell sube apenas de 6,8 % a 11,0 %. Lo que pasa
es que SE PIERDE LA COMPONENTE. Frames sin autoridad por `sin_componente`:

    ft=35 -> 643      ft=45 -> 985      ft=55 -> 1472     ft=65 -> 1952

y ese solo motivo explica el total (+1309 de +1236; las otras causas hasta
BAJAN, porque quedan menos frames vivos para rechazar).

La razon es geometrica y es especifica de NUESTRA camara. Con el horizonte en
la fila 9 y FLOOR_TOP ya en 35, la banda util son 85 filas de 120. Cuando la
linea esta LEJOS sus pixeles viven ARRIBA en la imagen, justo en las filas
35-64. Acortar el ROI borra exactamente la unica evidencia que quedaba, la
componente cae por debajo de MIN_AREA=30 y el frame se va a PERDIDA.

Por eso el disparador POR ESTADO era el mas caro: dispara en LOW/SIN_CERCA,
que es precisamente cuando la evidencia esta arriba. Con dosis 19 % hacia casi
todo el dano que el de steer con dosis 56 %.

Airborne puede darse el lujo del turn_crop porque corre a 448x252 con otra
geometria de camara. Nosotros no.

LIMITE DE ESTE EXPERIMENTO: se movio FLOOR_TOP con TODO LO DEMAS FIJO. MIN_AREA,
las bandas NEAR/MID/FAR y LOOKAHEAD=70 estan tuneados para FLOOR_TOP=35. Esto
refuta "acortar el ROI y nada mas"; no refuta "re-tunear el pipeline entero
para un ROI corto", que es otro experimento y bastante mas caro.
=============================================================================
"""

import argparse
import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
CAP = {}
CHK = {"n": 0, "mal": 0}
USO = {"camino_vacio": 0, "camino_ok": 0, "mono_vacio": 0,
       "shell_ok": 0, "shell_fallback": 0, "sin_alcance": 0}
ROI = {"corto": 0, "largo": 0, "por_estado": 0, "por_steer": 0}
RAZON = {}

FLOOR_NORMAL = 35
BANDA_ALT = [35, 45, 55, 65]
BANDA_UMBRAL = [30.0, 45.0, 60.0, float("inf")]


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3.v2


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


def hacer_roi(SinBranch, v2, alt, umbral, usar_estado=True):
    """Subclase con el ROI de dos posiciones. alt=None -> ROI fijo (apagado).

    usar_estado=False deja SOLO el disparador de |steer|. Es el brazo POST-HOC:
    no estaba preregistrado, se agrego despues de ver la tabla de dosis.
    """

    class RoiAdaptativo(SinBranch):
        def __init__(self, fps):
            SinBranch.__init__(self, fps)
            self.roi_corto = False

        def step(self, g):
            if alt is not None and self.roi_corto:
                v2.FLOOR_TOP = alt
                ROI["corto"] += 1
            else:
                v2.FLOOR_TOP = FLOOR_NORMAL
                ROI["largo"] += 1
            try:
                r = SinBranch.step(self, g)
            finally:
                v2.FLOOR_TOP = FLOOR_NORMAL

            # decision para el frame siguiente, con lo que se vio en este
            st = r.get("state")
            t = r.get("target")
            s = None
            if t is not None:
                s = float(np.clip(-90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0),
                                  -90.0, 90.0))
            por_estado = usar_estado and st in ("LOW", "SIN_CERCA")
            por_steer = (s is not None and abs(s) > umbral)
            self.roi_corto = bool(por_estado or por_steer)
            if alt is not None:
                if por_estado:
                    ROI["por_estado"] += 1
                if por_steer:
                    ROI["por_steer"] += 1
            return r

    return RoiAdaptativo


def hacer_roi_fijo(SinBranch, v2, ft):
    """ROI CONSTANTE en ft. No es una variante candidata: es el instrumento
    del diagnostico de mecanismo (--mecanismo)."""

    class RoiFijo(SinBranch):
        def step(self, g):
            v2.FLOOR_TOP = ft
            try:
                return SinBranch.step(self, g)
            finally:
                v2.FLOOR_TOP = FLOOR_NORMAL
    return RoiFijo


def es_ancestro(prev, ancla, cand):
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


def instalar(v2, cfg):
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    o_r = v2.reconstruct

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["si"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        CAP.clear()
        sk, res = o_p(self, comp, mode)
        if res is None or "dist" not in CAP or mode.startswith("AHEAD"):
            return sk, res
        pts, dist, prev, si = CAP["pts"], CAP["dist"], CAP["prev"], CAP["si"]
        sy, sx = pts[si]
        lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        fin = np.where(np.isfinite(dist))[0]
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if len(fin) and float(np.max(dist[fin])) < lo:
            USO["sin_alcance"] += 1
        if not cands:
            USO["shell_fallback"] += 1
            cands = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
                :min(30, len(fin))]
        else:
            USO["shell_ok"] += 1

        # --- CAMINO PRINCIPAL: la cadena start -> nodo mas lejano ----------
        if cfg["camino"] and len(fin):
            F = int(fin[int(np.argmax(dist[fin]))])
            cadena = set(o_r(prev, si, F) or [])
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub
                USO["camino_ok"] += 1
            else:
                USO["camino_vacio"] += 1

        # --- MONOTONIA HACIA ADELANTE (Coulter 1992) -----------------------
        if cfg["mono"] and self.prev_target is not None and len(fin):
            ys = np.array([q[0] for q in pts])
            xs = np.array([q[1] for q in pts])
            dd = ((xs[fin] - self.prev_target[0]) ** 2
                  + (ys[fin] - self.prev_target[1]) ** 2)
            ancla = int(fin[int(np.argmin(dd))])
            adm = [i for i in cands if es_ancestro(prev, ancla, i)]
            if adm:
                cands = adm
            else:
                USO["mono_vacio"] += 1

        def score(i):
            y, x = pts[i]
            dy = sy - y
            h = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
            s = 0.35 * abs(dist[i] - v2.LOOKAHEAD)
            s += 0.55 * v2.angdiff(h, self.prev_heading)
            if self.prev_target is not None:
                s += 0.10 * math.hypot(x - self.prev_target[0],
                                       y - self.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        ti = min(cands, key=score)
        ty, tx = pts[ti]

        if not cfg["camino"] and not cfg["mono"]:
            CHK["n"] += 1
            if (abs(tx - res["target"][0]) > 1e-6
                    or abs(ty - res["target"][1]) > 1e-6):
                CHK["mal"] += 1
            return sk, res

        camino = o_r(prev, si, ti) or [si, ti]
        return sk, dict(
            start=res["start"], target=(float(tx), float(ty)),
            heading=math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6))),
            path=[(float(pts[i][1]), float(pts[i][0])) for i in camino])

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


def serie(Tr, v2, ruta, fps, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = Tr(fps)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            t = r.get("target")
            if t is None:
                # de donde viene el frame sin autoridad: la percepcion no
                # encontro nada, o el guard espacial lo rechazo
                k = "%s / %s" % (r.get("reason") or r.get("state"),
                                 r.get("spatial_guard", "-"))
                RAZON[k] = RAZON.get(k, 0) + 1
            out.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                r.get("state")))
        i += 1
    cap.release()
    return out


def correr(Tr, v2, cfg):
    """Una configuracion completa: 10 autonomos + controles."""
    CHK["n"] = CHK["mal"] = 0
    for k in USO:
        USO[k] = 0
    for k in ROI:
        ROI[k] = 0
    RAZON.clear()
    rest = instalar(v2, cfg)
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0, suav=[])
    firma = []
    for vid in AB.AUTONOMOS:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru):
            continue
        s = serie(Tr, v2, ru, FPS)
        m = AB.metricas(s)
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
        tot["suav"].append(m["suav"])
        firma.extend([t for t, _s, _e in s])
    ctl = []
    okc = True
    for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru) or not ex:
            continue
        s = serie(Tr, v2, ru, fps, d0, h0)
        m = AB.metricas(s)
        st = [x for _t, x, _e in s if x is not None]
        ctl.append("%s %d/%d" % (cn.split("_")[0], m["con"], ex))
        okc &= (m["con"] >= ex)
        if cn == "lineal_positivo":
            smax = max(st) if st else 0.0
            ctl.append("smax %+.0f" % smax)
            okc &= (smax >= 88.0)
    rest()
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav"]))
    tot["ctl"] = "  ".join(ctl)
    tot["okc"] = okc
    tot["firma"] = firma
    tot["roi"] = dict(ROI)
    tot["uso"] = dict(USO)
    tot["razon"] = dict(RAZON)
    return tot


def iguales(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if (x is None) != (y is None):
            return False
        if x is not None and (abs(x[0] - y[0]) > 1e-9
                              or abs(x[1] - y[1]) > 1e-9):
            return False
    return True


CABE = ("  %-14s %9s %9s %9s %9s %11s %9s  %-5s  %s"
        % ("config", "disp %", "sin_aut", "huecos", "saltos>24",
           "inversiones", "suav", "corto", "controles"))


def linea(nom, t, ref, dosis=""):
    return ("  %-14s %+9.2f %+9d %+9d %+9d %+11d %+9.2f  %-5s  %s %s"
            % (nom, t["disp"] - ref["disp"], t["sin_aut"] - ref["sin_aut"],
               t["huecos"] - ref["huecos"], t["s_gt"] - ref["s_gt"],
               t["inv"] - ref["inv"], t["suav"] - ref["suav"], dosis,
               t["ctl"], "OK" if t["okc"] else "*** FALLA"))


def main():
    ap = argparse.ArgumentParser(description="ROI adaptativo estilo Airborne")
    ap.add_argument("--mecanismo", action="store_true",
                    help="diagnostico: por que acortar el ROI hace dano")
    a = ap.parse_args()
    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    CM = dict(camino=True, mono=True)

    if a.mecanismo:
        # POR QUE. La shell geodesica pide un target a LOOKAHEAD=70 px, o sea
        # candidatos con distancia geodesica entre 54 y 88 px desde el start.
        # Si el ROI se acorta, esa longitud deja de existir sobre el esqueleto
        # y la shell cae al fallback ("los 30 mas cercanos a LOOKAHEAD"), que
        # NO es lo mismo. Se mide con el ROI forzado constante en cada altura.
        print("")
        print("=" * 112)
        print("  DIAGNOSTICO DE MECANISMO   -   ROI forzado CONSTANTE en cada altura")
        print("  shell pedida: %.0f a %.0f px geodesicos    LOOKAHEAD = %.0f"
              % (max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18, v2.LOOKAHEAD))
        print("=" * 112)
        print("  %-10s %8s %10s %12s %14s %10s %10s"
              % ("FLOOR_TOP", "filas", "disp %", "shell ok", "shell fallback",
                 "fallback%", "sin alcance"))
        raz = []
        for ft in BANDA_ALT:
            t = correr(hacer_roi_fijo(SinBranch, v2, ft), v2, CM)
            u = t["uso"]
            nn = u["shell_ok"] + u["shell_fallback"]
            print("  %-10d %8d %10.2f %12d %14d %9.1f%% %10d"
                  % (ft, 119 - ft + 1, t["disp"], u["shell_ok"],
                     u["shell_fallback"],
                     100.0 * u["shell_fallback"] / max(nn, 1),
                     u["sin_alcance"]))
            raz.append((ft, t["razon"], t["sin_aut"]))
        print("")
        print("  DE DONDE SALEN LOS FRAMES SIN AUTORIDAD (autonomos + controles)")
        claves = sorted({k for _f, d, _s in raz for k in d})
        print("  %-34s %9s %9s %9s %9s"
              % ("motivo", "ft=35", "ft=45", "ft=55", "ft=65"))
        for k in claves:
            print("  %-34s %9d %9d %9d %9d"
                  % (k, raz[0][1].get(k, 0), raz[1][1].get(k, 0),
                     raz[2][1].get(k, 0), raz[3][1].get(k, 0)))
        print("  %-34s %9d %9d %9d %9d"
              % ("TOTAL", sum(raz[0][1].values()), sum(raz[1][1].values()),
                 sum(raz[2][1].values()), sum(raz[3][1].values())))
        print("=" * 112)
        return 0

    print("")
    print("=" * 112)
    print("  ROI ADAPTATIVO sobre CAMINO+MONO   -   la idea de Airborne, no sus constantes")
    print("  ROI CORTO si estado(N-1) en {LOW, SIN_CERCA}  o  |steer(N-1)| > UMBRAL")
    print("  ROI NORMAL (FLOOR_TOP=35) en HIGH / MEDIUM / PERDIDA")
    print("  BANDA PREREGISTRADA   FLOOR_TOP alt: 35 45 55 65    UMBRAL |steer|: 30 45 60 inf")
    print("  UMBRAL=inf  =  disparador puro por estado.   Se corre la grilla entera.")
    print("=" * 112)

    # ---------------- 1) fidelidad + baseline ------------------------------
    Fijo = hacer_roi(SinBranch, v2, None, float("inf"))
    base = correr(Fijo, v2, dict(camino=False, mono=False))
    print("")
    print("  FIDELIDAD 1 (selector re-implementado, todo apagado): "
          "%d frames, %d discrepancias  %s"
          % (CHK["n"], CHK["mal"], "OK" if CHK["mal"] == 0 else "*** ABORTA"))
    if CHK["mal"]:
        return 3
    print("  BASELINE  disp %.2f %%  sin_aut %d  huecos %d  saltos %d  "
          "inversiones %d  suav %.2f"
          % (base["disp"], base["sin_aut"], base["huecos"], base["s_gt"],
             base["inv"], base["suav"]))

    # ---------------- 2) referencia CAMINO+MONO ----------------------------
    cm = correr(Fijo, v2, CM)

    # ---------------- 3) grilla del ROI ------------------------------------
    filas = []
    for alt in BANDA_ALT:
        if alt == FLOOR_NORMAL:
            umbrales = [BANDA_UMBRAL[0]]     # no-op: el umbral no aplica
        else:
            umbrales = BANDA_UMBRAL
        for um in umbrales:
            Tr = hacer_roi(SinBranch, v2, alt, um)
            t = correr(Tr, v2, CM)
            nt = t["roi"]["corto"] + t["roi"]["largo"]
            dos = "%.0f%%" % (100.0 * t["roi"]["corto"] / max(nt, 1))
            if alt == FLOOR_NORMAL:
                nom = "ROI35 (no-op)"
                dos = "-"
            else:
                nom = "ROI%d/u%s" % (alt, "inf" if um == float("inf")
                                     else "%d" % um)
            filas.append((nom, alt, um, t, dos))

    # fidelidad 2: el no-op tiene que ser identico a CAMINO+MONO
    nop = [f for f in filas if f[1] == FLOOR_NORMAL][0]
    ok2 = iguales(nop[3]["firma"], cm["firma"])
    print("  FIDELIDAD 2 (maquineria ROI encendida con alt=35 vs CAMINO+MONO): "
          "%d frames  %s" % (len(cm["firma"]),
                             "IDENTICO OK" if ok2 else "*** ABORTA"))
    if not ok2:
        return 3

    # ---------------- 4) tablas --------------------------------------------
    print("")
    print("  TABLA A   deltas contra el BASELINE ABSOLUTO (comparable con la "
          "tabla de camino_principal)")
    print(CABE)
    print(linea("CAMINO+MONO", cm, base, "-"))
    for nom, alt, um, t, dos in filas:
        if alt == FLOOR_NORMAL:
            continue
        print(linea(nom, t, base, dos))

    print("")
    print("  TABLA B   deltas contra CAMINO+MONO  <-- ESTA es la pregunta: "
          "el ROI adaptativo, aporta algo?")
    print(CABE)
    for nom, alt, um, t, dos in filas:
        print(linea(nom, t, cm, dos))

    print("")
    print("  DOSIS del disparador (frames con ROI corto, sobre autonomos+controles)")
    print("  %-14s %10s %10s %12s %12s"
          % ("config", "corto", "total", "por estado", "por steer"))
    for nom, alt, um, t, dos in filas:
        if alt == FLOOR_NORMAL:
            continue
        r = t["roi"]
        print("  %-14s %10d %10d %12d %12d"
              % (nom, r["corto"], r["corto"] + r["largo"], r["por_estado"],
                 r["por_steer"]))

    # ---------------- 4b) brazo POST-HOC: solo el disparador de steer -------
    #
    # NO ESTABA PREREGISTRADO. Se agrego despues de leer la tabla de dosis:
    # la columna uinf (disparador puro por estado, dosis 15-19 %) hace
    # practicamente todo el dano, y sumarle el disparador de steer (dosis
    # 54-56 %) casi no agrega nada. O sea que lo que rompe es acortar el ROI
    # cuando la linea esta LEJOS, no acortarlo cuando el robot esta doblando.
    # Y "cuando el robot esta doblando" es lo que en realidad hace el
    # turn_crop de Airborne. Asi que se aisla ese brazo.
    #
    # Por ser post-hoc, si algo de aca ganara NO se adopta: se re-preregistra.
    print("")
    print("  BRAZO POST-HOC (no preregistrado): SOLO el disparador de |steer|.")
    print("  El estado nunca acorta el ROI. Es el turn_crop de Airborne literal.")
    print("  deltas contra CAMINO+MONO")
    print(CABE)
    ph = []
    for alt in [45, 55, 65]:
        for um in [30.0, 45.0, 60.0]:
            Tr = hacer_roi(SinBranch, v2, alt, um, usar_estado=False)
            t = correr(Tr, v2, CM)
            nt = t["roi"]["corto"] + t["roi"]["largo"]
            dos = "%.0f%%" % (100.0 * t["roi"]["corto"] / max(nt, 1))
            nom = "PH%d/u%d" % (alt, um)
            ph.append((nom, t))
            print(linea(nom, t, cm, dos))

    # ---------------- 5) veredicto automatico -------------------------------
    print("")
    print("  CRITERIO PREREGISTRADO: entra solo si contra CAMINO+MONO mejora")
    print("  algo y NO empeora disponibilidad, huecos ni saltos>24, y no rompe")
    print("  ningun control (hist 100/100, lineal 73/73, steer max >= +88).")
    print("")
    ganan = []
    for nom, alt, um, t, dos in filas:
        if alt == FLOOR_NORMAL:
            continue
        no_empeora = (t["disp"] >= cm["disp"] - 1e-9
                      and t["huecos"] <= cm["huecos"]
                      and t["s_gt"] <= cm["s_gt"])
        mejora = (t["disp"] > cm["disp"] + 1e-9 or t["huecos"] < cm["huecos"]
                  or t["s_gt"] < cm["s_gt"] or t["inv"] < cm["inv"])
        if no_empeora and mejora and t["okc"]:
            ganan.append(nom)
            print("  PASA   %s" % nom)
    if not ganan:
        print("  NINGUNA configuracion de la banda pasa el criterio.")
        print("  Resultado negativo: el ROI adaptativo no aporta sobre CAMINO+MONO.")
    print("")
    print("  (el brazo post-hoc queda fuera del criterio por construccion:")
    print("   se miro despues de los datos, no puede adoptarse sin re-correr)")
    for nom, t in ph:
        if (t["disp"] >= cm["disp"] - 1e-9 and t["huecos"] <= cm["huecos"]
                and t["s_gt"] <= cm["s_gt"] and t["okc"]):
            print("  post-hoc no empeora nada: %s   -> hipotesis, no politica"
                  % nom)
    print("=" * 112)
    return 0


if __name__ == "__main__":
    sys.exit(main())
