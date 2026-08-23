# -*- coding: utf-8 -*-
"""BANCO SHADOW - las dos ideas de Airborne que nuestro codigo NO tiene.

NO TOCA EL ROBOT. Mide, no arregla.

De donde salen las dos ideas
----------------------------
Se leyo el repositorio `JamesBond6873/Airborne_Rescue_Line_2025`, rama `main`,
carpeta `RobotCode_Field_Version`. La hipotesis del handoff (seccion 9) quedo
CONFIRMADA leyendo el codigo: ellos hacen
`mascara -> contornos -> UNA linea por continuidad -> POI -> objetivo -> control`.

De todo lo que hacen, dos cosas son transferibles a 160x120 y NO estan en
nuestro codigo. Este banco mide esas dos, cada una por separado.

  IDEA 1 - CIERRE MORFOLOGICO antes de buscar contornos.
      `line_cam.py:1053-1055`:  erode x5, dilate x17, erode x9  (kernel 3x3,
      sobre 448x256). Nuestro `main_rpi_2026-08-22.py:804` va DIRECTO de
      `inRange` a usar la mascara: cero morfologia en el camino de la linea.
      El cierre tapa los reflejos especulares que agujerean la cinta y une los
      pedazos, que es lo que hace posible "elegir UNA linea".

  IDEA 2 - EL OBJETIVO ES UN PUNTO EXTREMO, no un promedio.
      `line_cam.py:356-455` saca top/left/right/bottom del contorno elegido, y
      `457-570` elige UNO segun hasta donde llega la linea. Nosotros
      promediamos: `leyes.py:65-71` usa el centroide de la banda.
      En una curva cerrada el centroide de la banda cae en el medio de la cinta;
      la punta del contorno cae en la punta. No es lo mismo.

Lo que este banco NO hace
-------------------------
No copia sus parametros: su camara es 448x256 con servo, la nuestra 160x120
fija. Las iteraciones de morfologia se escalan por area
(sqrt(19200/114688) = 0,409), no se copian.
No implementa su maquina de intersecciones ni su crop dinamico: verificado en
`line_cam.py:743-798`, el crop 0,75 lo abre la RAMPA, no la curva; el nombre
`turn_crop` enganha.
No simula trayectoria: es LAZO ABIERTO (HANDOFF regla 7).

Uso
---
    python cierre.py --validar     # el banco base tiene que seguir validando
    python cierre.py --idea1       # barrido de morfologia
    python cierre.py --idea2       # objetivo extremo vs centroide
"""

import os
import sys
import math
import argparse

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

from shadow import (frame_de_la_pi, confianza, W, H, CENTRO,        # noqa: E402
                    LO, HI, NEAR, MID, FAR, PIX_MIN, AREA_LOST)
from leyes import inversiones, suavidad                             # noqa: E402
import replay                                                       # noqa: E402
from birdeye import vistas, CASOS, VIDEOS_10                        # noqa: E402

K3 = np.ones((3, 3), np.uint8)

# Airborne hace erode5 / dilate17 / erode9 sobre 448x256 (line_cam.py:1053-1055).
# Escala lineal a 160x120: sqrt(19200/114688) = 0,409.
AIRBORNE_ESCALADO = (2, 7, 4)

MORFOS = [
    ("nada", None),                 # lo que corre hoy
    ("cierre1", ("cierre", 1)),
    ("cierre2", ("cierre", 2)),
    ("cierre3", ("cierre", 3)),
    ("airborne", ("aeda", AIRBORNE_ESCALADO)),
]


def aplicar_morfo(m, morfo):
    """UNA variable: la morfologia. Todo lo demas queda igual."""
    if morfo is None:
        return m
    tipo, par = morfo
    if tipo == "cierre":
        m = cv2.dilate(m, K3, iterations=par)
        m = cv2.erode(m, K3, iterations=par)
        return m
    e1, d, e2 = par
    m = cv2.erode(m, K3, iterations=e1)
    m = cv2.dilate(m, K3, iterations=d)
    m = cv2.erode(m, K3, iterations=e2)
    return m


def percibir_con(g, morfo):
    """Copia fiel de shadow.percibir con UN cambio: la morfologia.

    Se reimplementa en vez de importarse porque `shadow.percibir` calcula la
    mascara adentro y no acepta que se le pase otra. Todo lo demas -las bandas,
    los umbrales, el criterio de "la mas grande que toca la fila 119"- es
    identico a shadow.py:116-150, para que los numeros sean comparables con lo
    ya publicado.
    """
    m = cv2.inRange(g, LO, HI)
    m[:60, :] = 0
    m = aplicar_morfo(m, morfo)
    m[:60, :] = 0            # el dilate puede meter pixeles arriba del ROI
    n, et, est, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
    mejor, k0 = 0, 0
    for k in range(1, n):
        if np.any(et[119, :] == k) and est[k, cv2.CC_STAT_AREA] > mejor:
            mejor, k0 = est[k, cv2.CC_STAT_AREA], k
    d = {"area": 0.0, "wmax": 0, "trav": 0, "near": False, "mid": False,
         "far": False, "comp": None, "cx": None, "area_arriba": 0.0,
         "cx_arriba": None, "n_comp": n - 1, "toca_tope": 0}
    for k in range(1, n):
        if not np.any(et[119, :] == k):
            a = float(est[k, cv2.CC_STAT_AREA])
            if a > d["area_arriba"]:
                d["area_arriba"] = a
                _ys, xs = np.nonzero(et == k)
                d["cx_arriba"] = float(xs.mean()) - CENTRO
    if not k0 or mejor < AREA_LOST:
        return d
    mm = (et == k0)
    anchos = [len(np.nonzero(mm[y, :])[0]) for y in range(60, 120)]
    d["comp"] = mm
    d["area"] = float(mejor)
    d["wmax"] = max(anchos)
    d["trav"] = max(anchos[:40])
    for nom, (a, b) in (("near", NEAR), ("mid", MID), ("far", FAR)):
        d[nom] = mm[a:b + 1, :].sum() >= PIX_MIN
    xs = np.nonzero(mm[119, :])[0]
    d["cx"] = (float(xs.mean()) - CENTRO) if len(xs) else None
    # RIESGO: que el cierre enganche la cinta con el salon. Si la componente
    # elegida toca la fila 60 con mucho ancho, es sospechosa.
    d["toca_tope"] = int(anchos[0])
    return d


# ---------------------------------------------------------------------------
#  EL OBJETIVO: punto extremo (Airborne) contra centroide de banda (nuestro)
# ---------------------------------------------------------------------------

def centroide_banda(mm, a, b):
    sub = mm[a:b + 1, :]
    ys, xs = np.nonzero(sub)
    if xs.size < PIX_MIN:
        return None, None
    return float(xs.mean()), float(ys.mean()) + a


def poi_extremos(mm):
    """top / left / right del contorno, al estilo `calculatePointsOfInterest`.

    Airborne los saca del contorno (`line_cam.py:361-424`); aca se sacan de la
    mascara de la componente, que es lo mismo y no depende de findContours.
    """
    ys, xs = np.nonzero(mm)
    if xs.size == 0:
        return None
    y_min = int(ys.min())
    top = (float(xs[ys == y_min].mean()), float(y_min))
    x_min = int(xs.min())
    izq = (float(x_min), float(ys[xs == x_min].mean()))
    x_max = int(xs.max())
    der = (float(x_max), float(ys[xs == x_max].mean()))
    y_max = int(ys.max())
    bot = (float(xs[ys == y_max].mean()), float(y_max))
    return dict(top=top, izq=izq, der=der, bot=bot)


def objetivo_airborne(mm):
    """La regla de `interpretPOI` reducida a lo que aplica sin verde ni timers.

    `line_cam.py:481-516`, rama DEFAULT TRACKING:
      - si la linea llega arriba del todo -> el TOP
      - si ademas toca un borde lateral   -> ese borde
      - si no llega arriba                -> el TOP del recorte cercano
    Se traduce a nuestras filas: "arriba del todo" = llega a la banda FAR.
    """
    p = poi_extremos(mm)
    if p is None:
        return None, "sin_comp"
    llega_far = mm[FAR[0]:FAR[1] + 1, :].sum() >= PIX_MIN
    if p["izq"][0] <= 1:
        return p["izq"], "borde_izq"
    if p["der"][0] >= W - 2:
        return p["der"], "borde_der"
    if llega_far:
        return p["top"], "top_far"
    return p["top"], "top_cerca"


def rumbo_desde(bot, obj):
    if bot is None or obj is None:
        return float("nan")
    return math.degrees(math.atan2(obj[0] - bot[0], max(bot[1] - obj[1], 1e-6)))


# ---------------------------------------------------------------------------
#  CORRIDAS
# ---------------------------------------------------------------------------

ESTADOS = ["HIGH", "MEDIUM", "LOW", "SIN_CERCA", "PERDIDA"]


def correr_idea1(ruta, desde, hasta):
    """Un solo pase por el video, todas las morfologias sobre el mismo frame."""
    acc = {nom: dict(est={e: 0 for e in ESTADOS}, area=[], ncomp=[],
                     tope=[], rumbo=[]) for nom, _ in MORFOS}
    n = 0
    for _i, g in vistas(ruta, desde, hasta):
        n += 1
        for nom, morfo in MORFOS:
            p = percibir_con(g, morfo)
            a = acc[nom]
            a["est"][confianza(p)] += 1
            a["ncomp"].append(p["n_comp"])
            if p["comp"] is not None:
                a["area"].append(p["area"])
                a["tope"].append(p["toca_tope"])
                xn, yn = centroide_banda(p["comp"], *NEAR)
                xm, ym = centroide_banda(p["comp"], *MID)
                if xn is not None and xm is not None:
                    a["rumbo"].append(math.degrees(
                        math.atan2(xm - xn, max(yn - ym, 1e-6))))
                else:
                    a["rumbo"].append(float("nan"))
            else:
                a["rumbo"].append(float("nan"))
    return acc, n


def correr_idea2(ruta, desde, hasta, morfo):
    """Misma componente, mismo frame; cambia SOLO como se elige el objetivo."""
    cen, ext, mot = [], [], {}
    n = 0
    for _i, g in vistas(ruta, desde, hasta):
        n += 1
        p = percibir_con(g, morfo)
        if p["comp"] is None:
            cen.append(float("nan"))
            ext.append(float("nan"))
            continue
        mm = p["comp"]
        xn, yn = centroide_banda(mm, *NEAR)
        xm, ym = centroide_banda(mm, *MID)
        xf, yf = centroide_banda(mm, *FAR)
        xa, ya = (xm, ym) if xm is not None else (xf, yf)
        cen.append(rumbo_desde((xn, yn) if xn is not None else None,
                               (xa, ya) if xa is not None else None))
        pe = poi_extremos(mm)
        obj, motivo = objetivo_airborne(mm)
        mot[motivo] = mot.get(motivo, 0) + 1
        ext.append(rumbo_desde(pe["bot"] if pe else None, obj))
    return cen, ext, mot, n


def _fin(v):
    return [x for x in v if not (isinstance(x, float) and math.isnan(x))]


def tabla_idea1(nombre, etiqueta, acc, n):
    print("  %-16s %-18s n=%4d" % (nombre, etiqueta, n))
    print("      %-9s %5s %5s %5s %5s %5s | %6s %6s %6s | %5s %6s"
          % ("morfo", "HIGH", "MED", "LOW", "SINC", "PERD",
             "ncomp", "area", "tope", "inv", "salt50"))
    base = None
    for nom, _ in MORFOS:
        a = acc[nom]
        e = a["est"]
        f = _fin(a["rumbo"])
        hi = 100.0 * e["HIGH"] / max(n, 1)
        if base is None:
            base = hi
        print("      %-9s %4.1f%% %4.1f%% %4.1f%% %4.1f%% %4.1f%% | %6.1f %6.0f %6.1f | %5d %6.2f"
              % (nom, hi, 100.0 * e["MEDIUM"] / n, 100.0 * e["LOW"] / n,
                 100.0 * e["SIN_CERCA"] / n, 100.0 * e["PERDIDA"] / n,
                 float(np.median(a["ncomp"])) if a["ncomp"] else float("nan"),
                 float(np.median(a["area"])) if a["area"] else float("nan"),
                 float(np.median(a["tope"])) if a["tope"] else float("nan"),
                 inversiones(a["rumbo"]),
                 suavidad(a["rumbo"]) if len(f) > 3 else float("nan")))
    print("")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--idea1", action="store_true", help="barrido de morfologia")
    ap.add_argument("--idea2", action="store_true", help="objetivo extremo vs centroide")
    ap.add_argument("--morfo", default="nada", help="morfologia base para --idea2")
    ap.add_argument("--todos", action="store_true", help="ademas, los 10 videos")
    a = ap.parse_args(argv)

    if a.validar:
        return replay.validar(con_firmware=False)

    tareas = [(nom, os.path.join(AQUI, vid), d, h, et)
              for nom, vid, d, h, et in CASOS]
    if a.todos:
        tareas += [(v.replace(".avi", ""), os.path.join(AQUI, v), 0, 10 ** 9,
                    "completo") for v in VIDEOS_10]

    if a.idea1:
        print("")
        print("IDEA 1 - CIERRE MORFOLOGICO ANTES DE BUSCAR LA COMPONENTE")
        print("  ncomp = componentes en el ROI (mediana). area = de la elegida.")
        print("  tope  = ancho de la componente elegida en la fila 60. Si se")
        print("          dispara, el cierre se engancho con el salon: eso es el")
        print("          contraejemplo que hay que buscar, no un exito.")
        print("  HIGH sube = la cinta deja de estar rota por los reflejos.")
        print("")
        for nom, ruta, d, h, et in tareas:
            if not os.path.exists(ruta):
                print("  falta %s" % ruta)
                continue
            acc, n = correr_idea1(ruta, d, h)
            tabla_idea1(nom, et, acc, n)
        return 0

    if a.idea2:
        morfo = dict(MORFOS)[a.morfo]
        print("")
        print("IDEA 2 - OBJETIVO: PUNTO EXTREMO (Airborne) vs CENTROIDE (nuestro)")
        print("  misma componente, mismo frame, morfologia '%s'." % a.morfo)
        print("  Cambia SOLO de donde sale el punto de adelante.")
        print("")
        print("  %-16s %-18s %5s | %5s %6s %6s | %5s %6s %6s"
              % ("tramo", "etiqueta", "n", "invC", "s50C", "|med|C",
                 "invE", "s50E", "|med|E"))
        for nom, ruta, d, h, et in tareas:
            if not os.path.exists(ruta):
                continue
            cen, ext, mot, n = correr_idea2(ruta, d, h, morfo)
            fc, fe = _fin(cen), _fin(ext)
            print("  %-16s %-18s %5d | %5d %6.2f %6.1f | %5d %6.2f %6.1f"
                  % (nom, et, n,
                     inversiones(cen), suavidad(cen),
                     float(np.median(np.abs(fc))) if fc else float("nan"),
                     inversiones(ext), suavidad(ext),
                     float(np.median(np.abs(fe))) if fe else float("nan")))
            tot = sum(mot.values()) or 1
            print("      motivos: " + "  ".join(
                "%s %.0f%%" % (k, 100.0 * v / tot)
                for k, v in sorted(mot.items(), key=lambda t: -t[1])))
        print("")
        print("  C = centroide de banda (nuestro).  E = punto extremo (Airborne).")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
