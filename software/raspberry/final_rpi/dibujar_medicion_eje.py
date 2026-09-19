# -*- coding: utf-8 -*-
"""
La figura del PASO 0 de `medir_eje.py`: como se encuentra el eje de rotacion.

Benjamin, 25-ago: "d_eje como se mide entonces?".

El procedimiento entero esta en el docstring de `medir_eje.py`, pero el paso 0
-encontrar el centro de rotacion con dos mediatrices- no se entiende leyendolo.
Se entiende viendolo, y encima es el paso que hay que hacer con las manos abajo
del robot el sabado.

POR QUE NO ALCANZA CON "EL CENTRO DEL ROBOT": con 4 ruedas fijas el centro de
rotacion NO es el centro geometrico. Se corre hacia el eje delantero y depende
de la superficie (Mandow et al., IROS 2007: el skid steer se comporta como un
diferencial de ancho alfa*B, con alfa ~1,5 en vinilo). Hay que MEDIRLO.

LA GEOMETRIA, y es exacta para un cuerpo rigido: si el robot rota alrededor de
un punto C, entonces CUALQUIER punto P del chasis se mueve sobre un circulo
centrado en C. Por lo tanto |CP| = |CP'|, o sea que C esta en la MEDIATRIZ del
segmento PP'. Con DOS puntos hay dos mediatrices, y se cruzan en C.

    python dibujar_medicion_eje.py
"""

import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib.patches import FancyArrowPatch               # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))

FONDO = "#14161a"
TINTA = "#e9e9ec"
GRIS = "#7d8288"
CIAN = "#5ac8f5"
MAGENTA = "#e878eb"
NARANJA = "#ffa53c"
VERDE = "#6ee67a"


def chasis(ax, cx, cy, ang, color, alpha=1.0, lw=2.0):
    """Un rectangulo con una muesca adelante, rotado `ang` grados."""
    L, W = 16.0, 12.0
    pts = np.array([[-L / 2, -W / 2], [L / 2, -W / 2], [L / 2, W / 2],
                    [-L / 2, W / 2]])
    a = math.radians(ang)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    q = pts @ R.T + np.array([cx, cy])
    ax.add_patch(plt.Polygon(q, closed=True, fill=False, edgecolor=color,
                             lw=lw, alpha=alpha))
    # nariz: hacia donde mira
    nariz = np.array([[L / 2, 0], [L / 2 + 3, 0]]) @ R.T + np.array([cx, cy])
    ax.plot(nariz[:, 0], nariz[:, 1], color=color, lw=lw, alpha=alpha)
    return R


def punto_chasis(cx, cy, ang, local):
    a = math.radians(ang)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return np.array(local) @ R.T + np.array([cx, cy])


def mediatriz(ax, P, Q, color, largo=17.0, etiqueta=None):
    M = (P + Q) / 2.0
    d = Q - P
    n = np.array([-d[1], d[0]])
    n = n / np.linalg.norm(n)
    A, B = M - n * largo, M + n * largo
    ax.plot([A[0], B[0]], [A[1], B[1]], color=color, lw=1.6, ls="--",
            alpha=0.95)
    ax.plot(*M, "o", color=color, ms=5)
    if etiqueta:
        ax.text(M[0] + 1.0, M[1] + 1.0, etiqueta, color=color, fontsize=8.5)
    return M, n


def panel(ax, titulo):
    ax.set_facecolor(FONDO)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#2b2f36")
    ax.set_title(titulo, color=TINTA, fontsize=10.5, pad=9, loc="left")


def main():
    fig, axs = plt.subplots(1, 4, figsize=(19, 5.4))
    fig.patch.set_facecolor(FONDO)

    # geometria del ejemplo: el CENTRO DE ROTACION esta corrido hacia adelante
    C = np.array([6.0, 0.0])       # corrido hacia ADELANTE: ese es el punto
    ang0, ang1 = 0.0, 75.0         # 75 y no 90: no hace falta que sea exacto
    # dos puntos del chasis, en coordenadas del robot. Bien SEPARADOS entre si:
    # si los dos caen cerca del centro de rotacion los segmentos son cortos y
    # las mediatrices se cruzan con angulo chico, que es donde el trazado a mano
    # pierde precision.
    loc_P = (8.0, 5.0)      # esquina delantera
    loc_Q = (-8.0, -5.0)    # esquina trasera opuesta

    def pose(ang):
        """El chasis rotado `ang` ALREDEDOR DE C (no de su centro)."""
        a = math.radians(ang)
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        centro = C + (np.array([0.0, 0.0]) - C) @ R.T
        return centro, ang

    (c0, a0) = pose(ang0)
    (c1, a1) = pose(ang1)
    P0 = punto_chasis(c0[0], c0[1], a0, loc_P)
    Q0 = punto_chasis(c0[0], c0[1], a0, loc_Q)
    P1 = punto_chasis(c1[0], c1[1], a1, loc_P)
    Q1 = punto_chasis(c1[0], c1[1], a1, loc_Q)

    # ---- 1: pose A -------------------------------------------------------
    ax = axs[0]
    panel(ax, "1 · marcá dos puntos del chasis")
    chasis(ax, c0[0], c0[1], a0, CIAN)
    for p, n in ((P0, "P"), (Q0, "Q")):
        ax.plot(*p, "o", color=NARANJA, ms=9)
        ax.text(p[0] + 1.2, p[1] + 1.2, n, color=NARANJA, fontsize=12,
                fontweight="bold")
    ax.text(-17, -17, "hoja de papel pegada al piso,\nplomada sobre el "
                      "paragolpes\ny sobre el centro trasero",
            color=GRIS, fontsize=8.5)
    ax.set_xlim(-20, 22)
    ax.set_ylim(-20, 22)

    # ---- 2: pose B -------------------------------------------------------
    ax = axs[1]
    panel(ax, "2 · pivoteá ~90° y marcá LOS MISMOS dos")
    chasis(ax, c0[0], c0[1], a0, CIAN, alpha=0.22, lw=1.4)
    chasis(ax, c1[0], c1[1], a1, CIAN)
    for p, n in ((P0, "P"), (Q0, "Q")):
        ax.plot(*p, "o", color=NARANJA, ms=7, alpha=0.3)
    for p, n in ((P1, "P'"), (Q1, "Q'")):
        ax.plot(*p, "o", color=NARANJA, ms=9)
        ax.text(p[0] + 1.2, p[1] + 1.2, n, color=NARANJA, fontsize=12,
                fontweight="bold")
    ax.set_xlim(-20, 22)
    ax.set_ylim(-20, 22)

    # ---- 3: las mediatrices ---------------------------------------------
    ax = axs[2]
    panel(ax, "3 · uní P→P' y Q→Q', trazá las mediatrices")
    chasis(ax, c0[0], c0[1], a0, CIAN, alpha=0.18, lw=1.2)
    chasis(ax, c1[0], c1[1], a1, CIAN, alpha=0.18, lw=1.2)
    for A, B, col in ((P0, P1, NARANJA), (Q0, Q1, VERDE)):
        ax.plot([A[0], B[0]], [A[1], B[1]], color=col, lw=2.0)
        ax.plot(*A, "o", color=col, ms=7)
        ax.plot(*B, "o", color=col, ms=7)
    mediatriz(ax, P0, P1, NARANJA)
    mediatriz(ax, Q0, Q1, VERDE)
    ax.plot(*C, "X", color=MAGENTA, ms=17, mew=3.2)
    ax.text(C[0] + 1.6, C[1] - 3.2, "EJE DE\nROTACIÓN", color=MAGENTA,
            fontsize=10, fontweight="bold")
    ax.text(-20, -19.5, "un cuerpo rígido que rota alrededor de C cumple\n"
                        "|CP| = |CP'|  →  C está en la mediatriz de PP'",
            color=GRIS, fontsize=8.5)
    ax.set_xlim(-22, 24)
    ax.set_ylim(-22, 24)

    # ---- 4: los travesaños y la recta -----------------------------------
    ax = axs[3]
    ax.set_facecolor(FONDO)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#2b2f36")
    ax.set_title("4 · travesaños → una RECTA cuya ordenada es d_eje",
                 color=TINTA, fontsize=10.5, pad=9, loc="left")
    k_true, d_true, vh = 900.0, 12.0, 9.0
    filas = np.array([110.0, 85.0, 60.0, 45.0])
    x = 1.0 / (filas - vh)
    D = k_true * x + d_true
    xx = np.linspace(0, x.max() * 1.12, 50)
    ax.plot(xx, k_true * xx + d_true, color=CIAN, lw=2.0)
    ax.plot(x, D, "o", color=NARANJA, ms=10)
    ax.axhline(d_true, color=MAGENTA, ls=":", lw=1.6)
    ax.plot(0, d_true, "X", color=MAGENTA, ms=15, mew=3)
    ax.annotate("d_eje = %.0f cm" % d_true, xy=(0, d_true),
                xytext=(x.max() * 0.10, d_true * 0.42),
                color=MAGENTA, fontsize=11.5, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=MAGENTA, lw=1.8))
    for xi, Di, fi in zip(x, D, filas):
        ax.annotate("fila %d\n%.0f cm" % (fi, Di), (xi, Di),
                    textcoords="offset points", xytext=(9, -16),
                    color=GRIS, fontsize=8)
    ax.set_xlabel("x = 1 / (fila − v_h)", color=TINTA, fontsize=9.5)
    ax.set_ylabel("D medida con regla (cm)", color=TINTA, fontsize=9.5)
    ax.tick_params(colors=GRIS)
    ax.set_xlim(-x.max() * 0.06, x.max() * 1.12)
    ax.set_ylim(0, D.max() * 1.12)
    ax.text(x.max() * 0.30, D.max() * 0.28,
            "D(v) = k/(v − v_h) + d_eje\n\nes una RECTA en x, y la\n"
            "ORDENADA AL ORIGEN es d_eje",
            color=TINTA, fontsize=9.5)

    fig.suptitle("Cómo se mide  d_eje   ·   ~20 minutos, el robot no se "
                 "desarma   ·   medir_eje.py",
                 color=TINTA, fontsize=13, y=0.985)
    fig.text(0.5, 0.015,
             "criterios de aceptación:  R² ≥ 0,98  ·  d_eje > 0  ·  n ≥ 3 "
             "travesaños  ·  con 2 puntos la recta pasa exacta y el R² no dice "
             "nada",
             color=GRIS, fontsize=9, ha="center")
    fig.tight_layout(rect=[0, 0.035, 1, 0.955])
    ruta = os.path.join(AQUI, "COMO_MEDIR_D_EJE.png")
    fig.savefig(ruta, facecolor=FONDO, dpi=115)
    print("  escrito %s" % ruta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
