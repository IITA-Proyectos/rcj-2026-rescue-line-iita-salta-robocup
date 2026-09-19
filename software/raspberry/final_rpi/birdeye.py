# -*- coding: utf-8 -*-
"""BANCO SHADOW - bird-eye / IPM por software. NO TOCA EL ROBOT.

Que responde este archivo
-------------------------
El HANDOFF, seccion 10, pide evaluar si rectificar la perspectiva por software
mejora la percepcion de la linea. Y pide explicitamente NO asumir que si.

Este banco hace tres cosas, en este orden, y cada una se puede refutar sola:

  1. CALIBRA el horizonte a partir de los datos, en vez de inventar 4 puntos.
  2. VALIDA la homografia con validacion cruzada: calibra en unos videos y
     verifica en OTROS, sobre curvas, no solo sobre las rectas donde calibro.
  3. COMPARA vista normal contra bird-eye con UNA SOLA variable cambiada y con
     la ganancia normalizada, que es justo lo que hacia invalida la comparacion
     del borrador `airborne_birdeye_replay.py`.

Por que la homografia se puede calibrar sin tocar el hardware
-------------------------------------------------------------
El handoff dice, con razon, que pasar a centimetros necesita altura, inclinacion
e intrinsecos, que estan en el Fusion y no en los videos. Pero el IPM NO necesita
centimetros: necesita la relacion proyectiva, y esa esta escrita en la propia
cinta.

Camara pinhole mirando un plano, sin roll. Un punto del suelo a distancia Z cae
en la fila v con (v - v_h) proporcional a 1/Z, siendo v_h la fila del horizonte.
La escala transversal (px por cm) es tambien proporcional a 1/Z. Entonces el
ancho aparente de una cinta de ancho fisico constante es

        w(v) = a * (v - v_h)            <-- una RECTA en v

Se ajusta la recta al ancho medido y el cero da v_h. UN solo parametro, sacado
de una medicion, con R2 y residuo publicados. Si el ancho NO es lineal en la
fila, el modelo no aplica y todo lo que sigue es basura: por eso el R2 se
imprime siempre, no solo cuando conviene.

Con v_h, la homografia sale sola. En homogeneas:

        [X, Z, 1] ~ [u - cx, 1, v - v_h]

o sea  X = (u - cx)/(v - v_h)  y  Z = 1/(v - v_h), que es exactamente

        M = [[1, 0, -cx],
             [0, 0,   1],
             [0, 1, -v_h]]

No hay ningun numero magico ahi adentro: hay v_h (medido) y cx (supuesto, y con
barrido de sensibilidad en --validar).

Reglas de metodo que este archivo respeta (HANDOFF seccion 5)
-------------------------------------------------------------
  * `--validar` re-corre la validacion de `replay.py` ANTES de dejar comparar
    nada. Si el banco base no da 84,0 % / r = 0,9957, aborta.
  * usa `shadow.frame_de_la_pi`, que resuelve panel 640x240 vs crudo, con el
    submuestreo impar. No se reimplementa: se importa.
  * fps 33,3 para los paneles, 20 para `video_4.avi`, autodetectado por nombre.
  * la comparacion normal-vs-bird cambia UNA cosa: la vista. Misma ROI, misma
    seleccion de componente, misma ganancia.
  * este banco NO simula la trayectoria. Es lazo abierto y no puede decir que
    una ley "completaria la curva".

Uso
---
    python birdeye.py --validar          # calibra, valida y barre sensibilidad
    python birdeye.py --todos            # los 10 videos + video_4
    python birdeye.py hist.avi --desde 1354 --hasta 1490 --tag falla
    python birdeye.py --resolucion       # solo video_4: IPM antes vs despues
                                         # de reducir a 160x120
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

from shadow import frame_de_la_pi, W, H, CENTRO, FPS, LO, HI          # noqa: E402
from leyes import inversiones, suavidad                               # noqa: E402
import replay                                                         # noqa: E402


# ---------------------------------------------------------------------------
#  CONSTANTES
# ---------------------------------------------------------------------------

FILA_ROI = 60                    # main_rpi_2026-08-22.py:805. No se toca.
FILAS_CAL = list(range(62, 120))  # filas donde se mide el ancho de la cinta

# Filtros de la calibracion. Cada uno esta para matar un sesgo concreto.
MAX_INCL_GR = 6.0     # una cinta a angulo th mide w/cos(th): INFLA. Se filtra.
MIN_FRAC_FILAS = 0.60  # el frame tiene que tener cinta limpia en casi todo el ROI
MIN_MUESTRAS_FILA = 15  # filas con menos de esto no entran al ajuste

CX_SUPUESTO = (W - 1) / 2.0       # 79,5. Es un SUPUESTO, no una medicion.

VIDEOS_10 = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]

CASOS = [
    ("hist_exito",     "hist.avi",    580, 679,  "EXITO"),
    ("hist_falla",     "hist.avi",   1354, 1490, "FALLA"),
    ("lineal_positivo", "lineal.avi",  800, 872,  "CONTROL POSITIVO"),
    ("video_4_manual", "video_4.avi",   0, 10 ** 9, "TEACHER TRACE"),
]


def fps_de(video):
    """20 para video_4 (crudo), 33,3 para los paneles. shadow.py:517."""
    return 20.0 if "video_4" in os.path.basename(video) else FPS


# ---------------------------------------------------------------------------
#  LECTURA
# ---------------------------------------------------------------------------

def vistas(ruta, desde=0, hasta=10 ** 9):
    """Genera (idx, frame 160x120 BGR) usando la conversion validada."""
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError("no se pudo abrir %s" % ruta)
    i = 0
    try:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            if i > hasta:
                break
            if i >= desde:
                yield i, frame_de_la_pi(f)
            i += 1
    finally:
        cap.release()


def mascara(g, desde_fila=FILA_ROI, umbral=90):
    """La mascara de negro del codigo real. main_rpi_2026-08-22.py:804-805."""
    m = cv2.inRange(g, LO, np.array([umbral, umbral, umbral]))
    if desde_fila > 0:
        m[:desde_fila, :] = 0
    return m


# ---------------------------------------------------------------------------
#  1. CALIBRACION DEL HORIZONTE
# ---------------------------------------------------------------------------

def _runs(fila_bool):
    idx = np.flatnonzero(fila_bool)
    if idx.size == 0:
        return []
    c = np.flatnonzero(np.diff(idx) > 1)
    ini = np.concatenate(([0], c + 1))
    fin = np.concatenate((c, [idx.size - 1]))
    return [(int(idx[a]), int(idx[b]) + 1) for a, b in zip(ini, fin)]


def _comp_abajo(m):
    """La componente conexa que toca el borde inferior. None si no hay."""
    n, lab, st, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
    if n <= 1:
        return None
    ids = [i for i in np.unique(lab[H - 1, :]) if i != 0]
    if not ids:
        return None
    return lab == max(ids, key=lambda i: st[i, cv2.CC_STAT_AREA])


def anchos_limpios(comp, filas=FILAS_CAL):
    """{fila: ancho} solo donde hay UN run que no toca ningun borde lateral.

    Dos runs = interseccion o la cinta volviendo: no mide el ancho de nada.
    Run pegado al borde = cinta cortada: el ancho medido es un recorte.
    """
    out = {}
    for v in filas:
        r = _runs(comp[v, :])
        if len(r) != 1:
            continue
        a, b = r[0]
        if a == 0 or b == W:
            continue
        out[v] = b - a
    return out


def inclinacion_gr(comp, filas=FILAS_CAL):
    """Angulo de la cinta respecto de la vertical. Sirve para FILTRAR."""
    vs, cs = [], []
    for v in filas:
        r = _runs(comp[v, :])
        if len(r) != 1:
            continue
        a, b = r[0]
        if a == 0 or b == W:
            continue
        vs.append(v)
        cs.append((a + b - 1) / 2.0)
    if len(vs) < 8:
        return None
    return math.degrees(math.atan(np.polyfit(np.asarray(vs, float),
                                             np.asarray(cs, float), 1)[0]))


def juntar_anchos(ruta, desde=0, hasta=10 ** 9):
    """Acumula anchos por fila sobre un video. Devuelve (acum, contadores)."""
    acum = {v: [] for v in FILAS_CAL}
    cnt = dict(total=0, sin_comp=0, pocas_filas=0, inclinado=0, ok=0)
    for _i, g in vistas(ruta, desde, hasta):
        cnt["total"] += 1
        c = _comp_abajo(mascara(g))
        if c is None:
            cnt["sin_comp"] += 1
            continue
        lim = anchos_limpios(c)
        if len(lim) < len(FILAS_CAL) * MIN_FRAC_FILAS:
            cnt["pocas_filas"] += 1
            continue
        th = inclinacion_gr(c)
        if th is None or abs(th) > MAX_INCL_GR:
            cnt["inclinado"] += 1
            continue
        cnt["ok"] += 1
        for k, w in lim.items():
            acum[k].append(w)
    return acum, cnt


def ajustar_horizonte(acum, min_n=MIN_MUESTRAS_FILA):
    """w(v) = a*v + b  ->  v_h = -b/a. Devuelve tambien R2 y residuo maximo."""
    vs, ws, ns = [], [], []
    for v in sorted(acum):
        if len(acum[v]) >= min_n:
            vs.append(float(v))
            ws.append(float(np.median(acum[v])))
            ns.append(len(acum[v]))
    if len(vs) < 8:
        return None
    vs = np.asarray(vs)
    ws = np.asarray(ws)
    a, b = np.polyfit(vs, ws, 1)
    pred = a * vs + b
    ss_tot = float(np.sum((ws - ws.mean()) ** 2))
    r2 = 1.0 - float(np.sum((ws - pred) ** 2)) / ss_tot if ss_tot > 0 else float("nan")
    return dict(a=float(a), b=float(b), v_h=float(-b / a) if a else float("nan"),
                r2=r2, res_max=float(np.max(np.abs(ws - pred))),
                n_filas=len(vs), n_muestras=int(sum(ns)),
                w_119=float(a * 119 + b), w_62=float(a * 62 + b), vs=vs, ws=ws)


# ---------------------------------------------------------------------------
#  2. LA HOMOGRAFIA, DERIVADA DE v_h
# ---------------------------------------------------------------------------

class Bird(object):
    """IPM de un parametro medido (v_h) mas un encuadre elegido.

    El encuadre NO es libre: se fija exigiendo dos cosas que hacen que la
    comparacion contra la vista normal sea honesta.

      (a) La escala lateral en la fila 119 vale 1. Un pixel de error lateral
          cerca del robot mide lo mismo en las dos vistas. Sin esto, comparar
          angulos entre vistas es comparar ganancias, que es el error que
          invalidaba `airborne_birdeye_replay.py` (hasta x2,3 de diferencia).
      (b) La fila 119 de la vista normal cae en la fila 119 del bird, y la
          fila `fila_tope` (por defecto la 60, la del ROI real) cae en la 0.
          Misma ROI en las dos vistas: no se le regala al bird piso que el
          robot nunca miro.
    """

    def __init__(self, v_h, cx=CX_SUPUESTO, fila_tope=FILA_ROI, fila_base=H - 1):
        if not (v_h < fila_tope):
            raise ValueError(
                "v_h=%.1f tiene que estar por ARRIBA de la fila tope %d; si no, "
                "la fila tope esta en el horizonte o mas alla y el warp diverge."
                % (v_h, fila_tope))
        self.v_h = float(v_h)
        self.cx = float(cx)
        self.fila_tope = int(fila_tope)
        self.fila_base = int(fila_base)

        # Z(v) = 1/(v - v_h). Cerca es v grande.
        z_base = 1.0 / (self.fila_base - self.v_h)
        z_tope = 1.0 / (self.fila_tope - self.v_h)

        # (a) escala lateral 1 en la fila base:  X = (u-cx)/(v-v_h)
        #     du/dX en v=fila_base vale (fila_base - v_h)
        self.kx = float(self.fila_base - self.v_h)
        # (b) Z -> fila:  v' = kz*(Z - z_tope) + 0, con v'(z_base) = fila_base
        self.kz = float(self.fila_base / (z_base - z_tope))
        self.z_tope = float(z_tope)

        # H_suelo: (u,v,1) -> (X, Z, 1)
        Hs = np.array([[1.0, 0.0, -self.cx],
                       [0.0, 0.0, 1.0],
                       [0.0, 1.0, -self.v_h]], dtype=np.float64)
        # A: (X,Z,1) -> (u', v', 1)   encuadre
        A = np.array([[self.kx, 0.0, self.cx],
                      [0.0, self.kz, -self.kz * self.z_tope],
                      [0.0, 0.0, 1.0]], dtype=np.float64)
        self.M = A.dot(Hs)
        self.Minv = np.linalg.inv(self.M)

    # -- utilidades -------------------------------------------------------
    def punto(self, u, v):
        """Mapea un punto de la vista normal al bird."""
        p = self.M.dot(np.array([float(u), float(v), 1.0]))
        return p[0] / p[2], p[1] / p[2]

    def warp(self, img, tam=None):
        """INTER_NEAREST a proposito: sobre una mascara binaria interpolar
        inventa pixeles grises que despues hay que re-binarizar."""
        tam = tam or (W, H)
        return cv2.warpPerspective(img, self.M, tam, flags=cv2.INTER_NEAREST,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    def escala_lateral(self, v):
        """Cuantos px del bird vale un px lateral de la fila v de la normal."""
        return self.kx / (v - self.v_h)


# ---------------------------------------------------------------------------
#  3. VALIDACION CRUZADA DE LA HOMOGRAFIA
# ---------------------------------------------------------------------------

def ancho_en_bird(bird, m):
    """{fila_bird: ancho} de la componente de abajo, ya rectificada."""
    mb = bird.warp(m)
    c = _comp_abajo(mb)
    if c is None:
        return {}
    return anchos_limpios(c, filas=list(range(2, H)))


def test_ancho_constante(bird, rutas, max_frames_por_video=400):
    """Si la homografia esta bien, el ancho de la cinta en bird-eye NO depende
    de la fila. Es la prueba directa, y se corre en videos que NO se usaron
    para calibrar, para que no sea circular.

    Devuelve el coeficiente de variacion del ancho a lo largo de las filas,
    en la vista normal y en el bird. Si el bird no baja, la homografia no sirve.
    """
    acum_n = {}
    acum_b = {}
    usados = 0
    for ruta in rutas:
        n = 0
        for _i, g in vistas(ruta):
            if n >= max_frames_por_video:
                break
            m = mascara(g)
            c = _comp_abajo(m)
            if c is None:
                continue
            th = inclinacion_gr(c)
            if th is None or abs(th) > MAX_INCL_GR:
                continue
            an = anchos_limpios(c)
            if len(an) < len(FILAS_CAL) * MIN_FRAC_FILAS:
                continue
            ab = ancho_en_bird(bird, m)
            if len(ab) < 30:
                continue
            n += 1
            usados += 1
            for k, w in an.items():
                acum_n.setdefault(k, []).append(w)
            for k, w in ab.items():
                acum_b.setdefault(k, []).append(w)

    def cv_de(acum, lo, hi):
        vs = [np.median(acum[k]) for k in sorted(acum)
              if lo <= k <= hi and len(acum[k]) >= MIN_MUESTRAS_FILA]
        if len(vs) < 8:
            return None, None, None
        vs = np.asarray(vs, float)
        return float(vs.std() / vs.mean()), float(vs.min()), float(vs.max())

    cvn, n_lo, n_hi = cv_de(acum_n, 62, 119)
    cvb, b_lo, b_hi = cv_de(acum_b, 5, 115)
    return dict(frames=usados, cv_normal=cvn, cv_bird=cvb,
                rango_normal=(n_lo, n_hi), rango_bird=(b_lo, b_hi))


# ---------------------------------------------------------------------------
#  4. LA SENAL QUE SE COMPARA
# ---------------------------------------------------------------------------

def _centroide_banda(comp, a, b, pix_min=8):
    sub = comp[a:b + 1, :]
    ys, xs = np.nonzero(sub)
    if xs.size < pix_min:
        return None, None
    return float(xs.mean()), float(ys.mean()) + a


def rumbo_de(comp, banda_cerca, banda_lejos):
    """Rumbo en grados del segmento cerca->lejos. Positivo = a la derecha.

    Es exactamente la definicion de `e_head` de leyes.py:139, para que los dos
    bancos sean comparables sin traducir nada.
    """
    xn, yn = _centroide_banda(comp, *banda_cerca)
    xf, yf = _centroide_banda(comp, *banda_lejos)
    if xn is None or xf is None:
        return None, None, None
    return (math.degrees(math.atan2(xf - xn, max(yn - yf, 1e-6))), xn, xf)


class Senal(object):
    """Extrae, del MISMO frame, la senal en las dos vistas.

    Lo unico que cambia entre las dos columnas es el warp. Misma mascara, misma
    ROI, misma seleccion de componente (la que toca el borde de abajo), mismas
    bandas en proporcion de la ROI, misma formula de rumbo. Una variable.
    """

    # bandas en la vista normal: NEAR y MID de shadow.py/leyes.py
    BANDA_CERCA_N = (110, 119)
    BANDA_LEJOS_N = (95, 105)

    def __init__(self, bird):
        self.bird = bird
        # las mismas dos bandas, mapeadas al bird por la homografia
        self.BANDA_CERCA_B = self._mapear(self.BANDA_CERCA_N)
        self.BANDA_LEJOS_B = self._mapear(self.BANDA_LEJOS_N)

    def _mapear(self, banda):
        a = self.bird.punto(self.bird.cx, banda[0])[1]
        b = self.bird.punto(self.bird.cx, banda[1])[1]
        lo, hi = sorted((a, b))
        return (max(0, int(round(lo))), min(H - 1, int(round(hi))))

    def paso(self, g):
        m = mascara(g)
        out = dict(ang_actual=float("nan"),
                   rumbo_n=float("nan"), lat_n=float("nan"),
                   rumbo_b=float("nan"), lat_b=float("nan"),
                   ve_n=0, ve_b=0)
        out["ang_actual"] = replay._atan2_original(m)

        cn = _comp_abajo(m)
        if cn is not None:
            r, xn, _xf = rumbo_de(cn, self.BANDA_CERCA_N, self.BANDA_LEJOS_N)
            if r is not None:
                out["rumbo_n"] = r
                out["lat_n"] = xn - CENTRO
                out["ve_n"] = 1

        mb = self.bird.warp(m)
        cb = _comp_abajo(mb)
        if cb is not None:
            r, xb, _xf = rumbo_de(cb, self.BANDA_CERCA_B, self.BANDA_LEJOS_B)
            if r is not None:
                out["rumbo_b"] = r
                # ganancia normalizada: en la fila base la escala vale 1, asi
                # que el error lateral del bird ya esta en px de la normal.
                out["lat_b"] = xb - self.bird.punto(CENTRO, H - 1)[0]
                out["ve_b"] = 1
        return out


# ---------------------------------------------------------------------------
#  5. CORRIDAS
# ---------------------------------------------------------------------------

def correr(ruta, bird, desde=0, hasta=10 ** 9):
    s = Senal(bird)
    filas = []
    for i, g in vistas(ruta, desde, hasta):
        d = s.paso(g)
        d["frame"] = i
        filas.append(d)
    return filas, s


def _col(filas, k):
    return [f[k] for f in filas]


def _finito(v):
    return [x for x in v if not (isinstance(x, float) and math.isnan(x))]


def _r2_acople(rumbo, lat):
    """Cuanto del rumbo aparente se explica por el corrimiento lateral.

    En la vista normal, dos rectas paralelas del suelo se ven con angulos
    distintos: convergen al punto de fuga. O sea que el angulo aparente depende
    de DONDE esta la cinta, no solo de hacia donde va. En bird-eye eso tiene
    que desaparecer. Este R2 mide justo ese acople.

    Es una prueba de la HOMOGRAFIA, no del control. Y puede salir que no baja.
    """
    pares = [(r, l) for r, l in zip(rumbo, lat)
             if not (math.isnan(r) or math.isnan(l))]
    if len(pares) < 60:
        return float("nan")
    r = np.asarray([p[0] for p in pares], float)
    l = np.asarray([p[1] for p in pares], float)
    if r.std() < 1e-9 or l.std() < 1e-9:
        return float("nan")
    return float(np.corrcoef(r, l)[0, 1] ** 2)


def informe_tramo(nombre, etiqueta, filas):
    rn, rb = _col(filas, "rumbo_n"), _col(filas, "rumbo_b")
    ln, lb = _col(filas, "lat_n"), _col(filas, "lat_b")
    act = _col(filas, "ang_actual")
    n = len(filas)
    print("  %-16s %-18s n=%4d   ve_n %5.1f %%  ve_b %5.1f %%"
          % (nombre, etiqueta, n,
             100.0 * sum(_col(filas, "ve_n")) / max(n, 1),
             100.0 * sum(_col(filas, "ve_b")) / max(n, 1)))
    print("      %-14s %8s %8s %8s %8s %8s"
          % ("senal", "inv", "salto50", "|med|", "p90", "R2(lat)"))
    for et, v, l in (("actual atan2", act, None),
                     ("rumbo normal", rn, ln),
                     ("rumbo BIRD", rb, lb)):
        f = _finito(v)
        if len(f) < 3:
            print("      %-14s   sin datos" % et)
            continue
        r2 = _r2_acople(v, l) if l is not None else float("nan")
        print("      %-14s %8d %8.2f %8.1f %8.1f %8s"
              % (et, inversiones(v), suavidad(v),
                 float(np.median(np.abs(f))),
                 float(np.percentile(np.abs(f), 90)),
                 "-" if math.isnan(r2) else "%.3f" % r2))
    print("")


# ---------------------------------------------------------------------------
#  6. VALIDACION
# ---------------------------------------------------------------------------

def calibrar(rutas, verbose=True):
    """Calibra v_h sobre una lista de videos. Devuelve (v_h, por_video)."""
    por_video = {}
    if verbose:
        print("  %-18s %6s %6s %6s %6s %6s | %7s %7s %6s %6s"
              % ("video", "total", "ok", "sinC", "pocas", "incl",
                 "v_h", "a", "R2", "w119"))
    for ruta in rutas:
        if not os.path.exists(ruta):
            continue
        acum, cnt = juntar_anchos(ruta)
        f = ajustar_horizonte(acum)
        nom = os.path.basename(ruta)
        if f is None:
            if verbose:
                print("  %-18s %6d %6d %6d %6d %6d | sin datos suficientes"
                      % (nom, cnt["total"], cnt["ok"], cnt["sin_comp"],
                         cnt["pocas_filas"], cnt["inclinado"]))
            continue
        por_video[nom] = f
        if verbose:
            print("  %-18s %6d %6d %6d %6d %6d | %+7.1f %7.4f %6.4f %6.1f"
                  % (nom, cnt["total"], cnt["ok"], cnt["sin_comp"],
                     cnt["pocas_filas"], cnt["inclinado"],
                     f["v_h"], f["a"], f["r2"], f["w_119"]))
    if not por_video:
        return None, {}
    # descarte explicito y justificado: si w(119) es chico, lo que se midio NO
    # es la cinta. Se reporta cual se descarto y por que.
    buenos = {k: v for k, v in por_video.items() if v["w_119"] >= 50.0}
    if verbose:
        for k, v in por_video.items():
            if k not in buenos:
                print("  DESCARTADO %s: w(119) = %.1f px. La cinta de este "
                      "montaje mide ~70 px en la fila 119 en todos los demas "
                      "videos; lo que se ajusto aca es otro objeto."
                      % (k, v["w_119"]))
    if not buenos:
        return None, por_video
    return float(np.median([v["v_h"] for v in buenos.values()])), por_video


def validar():
    print("")
    print("=" * 78)
    print(" PASO 0 - el banco base tiene que seguir validando (HANDOFF regla 1)")
    print("=" * 78)
    rc = replay.validar(con_firmware=False)
    if rc != 0:
        print("\n  *** El banco base NO valida. No se compara nada. ***")
        return 1

    print("")
    print("=" * 78)
    print(" PASO 1 - CALIBRACION DEL HORIZONTE   w(v) = a*(v - v_h)")
    print("          se refuta con el R2 y con el residuo maximo")
    print("=" * 78)
    rutas = [os.path.join(AQUI, v) for v in VIDEOS_10 + ["video_4.avi"]]
    v_h, por_video = calibrar(rutas)
    if v_h is None:
        print("\n  *** No se pudo calibrar. El modelo no aplica. ***")
        return 1
    buenos = {k: v for k, v in por_video.items() if v["w_119"] >= 50.0}
    vhs = [v["v_h"] for v in buenos.values()]
    r2s = [v["r2"] for v in buenos.values()]
    print("")
    print("  v_h aceptados: mediana %+.1f   min %+.1f   max %+.1f   "
          "dispersion %.1f filas   (n = %d videos)"
          % (np.median(vhs), min(vhs), max(vhs), max(vhs) - min(vhs), len(vhs)))
    print("  R2 del ajuste lineal: min %.4f   mediana %.4f"
          % (min(r2s), float(np.median(r2s))))
    z = lambda v: 1.0 / (v - v_h)
    print("  Con v_h = %+.1f: la fila 62 esta %.2f veces mas lejos que la 119."
          % (v_h, z(62) / z(119)))
    print("  Un seguidor de linea normal mira de 1x a 5x. Este mira de 1x a %.1fx."
          % (z(62) / z(119)))

    print("")
    print("=" * 78)
    print(" PASO 2 - VALIDACION CRUZADA DE LA HOMOGRAFIA")
    print("          se calibra en unos videos y se verifica en OTROS")
    print("=" * 78)
    nombres = sorted(buenos)
    mitad = len(nombres) // 2
    tren = [os.path.join(AQUI, n) for n in nombres[:mitad]]
    test = [os.path.join(AQUI, n) for n in nombres[mitad:]]
    v_h_tren, _ = calibrar(tren, verbose=False)
    print("  calibrado en : %s" % ", ".join(nombres[:mitad]))
    print("  verificado en: %s" % ", ".join(nombres[mitad:]))
    print("  v_h de entrenamiento = %+.1f  (contra %+.1f de todos)"
          % (v_h_tren, v_h))
    b = Bird(v_h_tren)
    t = test_ancho_constante(b, test)
    print("")
    print("  Si la homografia esta bien, el ancho de la cinta en bird-eye NO")
    print("  depende de la fila. Coeficiente de variacion del ancho por fila:")
    if t["cv_normal"] is None or t["cv_bird"] is None:
        print("      sin datos suficientes")
    else:
        print("      vista normal : CV = %.3f   (ancho de %.0f a %.0f px)"
              % (t["cv_normal"], t["rango_normal"][0], t["rango_normal"][1]))
        print("      bird-eye     : CV = %.3f   (ancho de %.0f a %.0f px)"
              % (t["cv_bird"], t["rango_bird"][0], t["rango_bird"][1]))
        if t["cv_bird"] < t["cv_normal"] * 0.5:
            print("      -> la homografia APLANA la perspectiva en videos que no")
            print("         se usaron para calibrarla.")
        else:
            print("      -> NO aplana lo suficiente. La homografia NO esta validada.")
    print("      (%d frames)" % t["frames"])

    print("")
    print("=" * 78)
    print(" PASO 3 - SENSIBILIDAD: cx es un SUPUESTO, no una medicion")
    print("=" * 78)
    print("  %8s %10s %10s" % ("cx", "CV bird", "delta"))
    base = None
    for cx in (69.5, 74.5, 79.5, 84.5, 89.5):
        bb = Bird(v_h_tren, cx=cx)
        tt = test_ancho_constante(bb, test[:2], max_frames_por_video=250)
        if tt["cv_bird"] is None:
            print("  %8.1f %10s" % (cx, "-"))
            continue
        if base is None:
            base = tt["cv_bird"]
        print("  %8.1f %10.3f %10.3f" % (cx, tt["cv_bird"], tt["cv_bird"] - base))
    print("")
    print("  Si la columna delta es chica, la conclusion no depende de cx.")
    print("")
    return 0


# ---------------------------------------------------------------------------
#  7. RESOLUCION: solo video_4, el unico crudo 640x480
# ---------------------------------------------------------------------------

def prueba_resolucion(v_h):
    """El HANDOFF seccion 10 pide hacer el IPM ANTES de reducir a 160x120.

    Se puede en UN solo video: `video_4.avi`, que es crudo 640x480. Los otros
    diez son paneles de GRABAR, y el panel guarda el frame YA reducido a
    160x120 y reescalado x2 con NEAREST (parche_planner.py:283). Esa
    informacion no existe: rectificar despues no la recupera.

    Asi que esta prueba mide el TECHO del beneficio por resolucion, en el unico
    material que lo permite, y no se puede extrapolar a los otros nueve.
    """
    ruta = os.path.join(AQUI, "video_4.avi")
    if not os.path.exists(ruta):
        print("  falta video_4.avi")
        return
    print("")
    print("=" * 78)
    print(" IPM ANTES vs DESPUES de reducir   (solo video_4.avi, crudo 640x480)")
    print("=" * 78)
    # el mismo v_h, escalado: 640x480 es 4x en x y 4x en y respecto de 160x120
    ESC_X, ESC_Y = 640.0 / W, 480.0 / H
    b_chico = Bird(v_h)
    b_grande = Bird(v_h * ESC_Y, cx=CX_SUPUESTO * ESC_X,
                    fila_tope=int(FILA_ROI * ESC_Y), fila_base=479)
    cap = cv2.VideoCapture(ruta)
    dif, n, sin_a, sin_d = [], 0, 0, 0
    sa = Senal(b_chico)
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.rotate(f, cv2.ROTATE_180)
        # (a) DESPUES: reducir y despues rectificar  <- lo que se puede hacer
        #     con los paneles
        chico = cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)
        d_desp = sa.paso(chico)
        # (b) ANTES: rectificar en 640x480 y reducir despues
        m_grande = cv2.inRange(g, LO, HI)
        m_grande[:int(FILA_ROI * ESC_Y), :] = 0
        mb = b_grande.warp(m_grande, tam=(640, 480))
        mb = cv2.resize(mb, (W, H), interpolation=cv2.INTER_AREA)
        mb = (mb > 127).astype(np.uint8) * 255
        cb = _comp_abajo(mb)
        r_ant = None
        if cb is not None:
            r_ant = rumbo_de(cb, sa.BANDA_CERCA_B, sa.BANDA_LEJOS_B)[0]
        r_desp = d_desp["rumbo_b"]
        n += 1
        if r_ant is None:
            sin_a += 1
        if math.isnan(r_desp):
            sin_d += 1
        if r_ant is not None and not math.isnan(r_desp):
            dif.append(abs(r_ant - r_desp))
    cap.release()
    print("  frames %d   sin senal ANTES %d (%.1f %%)   sin senal DESPUES %d (%.1f %%)"
          % (n, sin_a, 100.0 * sin_a / max(n, 1), sin_d, 100.0 * sin_d / max(n, 1)))
    if dif:
        d = np.asarray(dif)
        print("  |rumbo(ANTES) - rumbo(DESPUES)|: p50 %.2f gr   p90 %.2f gr   max %.2f gr"
              % (np.median(d), np.percentile(d, 90), d.max()))
        print("  Si la diferencia es chica, rectificar a 640x480 antes de reducir")
        print("  NO agrega nada sobre este material y el punto es discutible.")
    print("")


# ---------------------------------------------------------------------------
#  8. CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("videos", nargs="*")
    ap.add_argument("--validar", action="store_true",
                    help="valida el banco base, calibra y verifica la homografia")
    ap.add_argument("--todos", action="store_true",
                    help="los 4 casos de control y despues los 10 videos")
    ap.add_argument("--resolucion", action="store_true",
                    help="IPM antes vs despues de reducir (solo video_4)")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    ap.add_argument("--tag", default="")
    ap.add_argument("--vh", type=float, default=None,
                    help="forzar v_h en vez de calibrarlo (para barrer)")
    a = ap.parse_args(argv)

    if a.validar:
        return validar()

    v_h = a.vh
    if v_h is None:
        print("  calibrando v_h ...")
        rutas = [os.path.join(AQUI, v) for v in VIDEOS_10 + ["video_4.avi"]]
        v_h, _ = calibrar(rutas, verbose=False)
        if v_h is None:
            print("  no se pudo calibrar; pasar --vh a mano")
            return 1
    print("  v_h = %+.2f   cx = %.1f" % (v_h, CX_SUPUESTO))
    bird = Bird(v_h)
    s = Senal(bird)
    print("  bandas normal: cerca %s  lejos %s" % (s.BANDA_CERCA_N, s.BANDA_LEJOS_N))
    print("  bandas bird  : cerca %s  lejos %s" % (s.BANDA_CERCA_B, s.BANDA_LEJOS_B))
    print("")

    if a.resolucion:
        prueba_resolucion(v_h)
        return 0

    tareas = []
    if a.todos:
        for nom, vid, d, h, et in CASOS:
            tareas.append((nom, os.path.join(AQUI, vid), d, h, et))
        for v in VIDEOS_10:
            tareas.append((v.replace(".avi", ""), os.path.join(AQUI, v),
                           0, 10 ** 9, "completo"))
    else:
        for v in a.videos:
            r = v if os.path.exists(v) else os.path.join(AQUI, v)
            tareas.append((os.path.basename(r).replace(".avi", "") +
                           (("_" + a.tag) if a.tag else ""),
                           r, a.desde, a.hasta, a.tag or "tramo"))
    if not tareas:
        ap.print_help()
        return 2

    print("  inv     = inversiones de signo, banda muerta +-3 gr (leyes.py:303)")
    print("  salto50 = mediana del salto entre frames, en grados")
    print("  R2(lat) = cuanto del rumbo se explica por el corrimiento lateral.")
    print("            ALTO = la senal mezcla posicion con rumbo. BAJO = separa.")
    print("")
    for nom, ruta, d, h, et in tareas:
        if not os.path.exists(ruta):
            print("  falta %s" % ruta)
            continue
        filas, _ = correr(ruta, bird, d, h)
        informe_tramo(nom, et, filas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
