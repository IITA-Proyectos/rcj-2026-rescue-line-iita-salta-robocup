# -*- coding: utf-8 -*-
"""EL MECANISMO QUE DESCRIBIO BENJAMIN, DIBUJADO.

"no gira en el lugar sino que avanza, y llega un punto donde le queda casi nada
de linea, y ya el atan2 no es que tira mal el angulo sino que ya no sabe cual es
el angulo correcto porque el robot siguio avanzando y no giro correctamente"

    python por_que_se_sale.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrow
import numpy as np
import os

fig, ax = plt.subplots(1, 4, figsize=(19, 6.6))
PASOS = [
    (0.0,  0,  "1. LLEGA AL CODO",
     "ve linea abajo y a la izquierda\nel atan2 pide girar. BIEN.", "#2ca02c"),
    (2.2, 12,  "2. GIRA POCO Y AVANZA",
     "rot no llega a 1: el robot AVANZA\nmientras gira. Se come la esquina.", "#ff7f0e"),
    (4.4, 22,  "3. LE QUEDA POCA LINEA",
     "ya paso el codo. En el ROI queda\nun pedacito, y cada vez menos.", "#d62728"),
    (6.6, 30,  "4. EL atan2 SE QUEDA SIN QUE MEDIR",
     "el angulo no esta MAL:\nya no hay linea que lo defina.", "#8b0000"),
]

for a, (dy, rot_deg, tit, sub, col) in zip(ax, PASOS):
    # el codo
    a.plot([0, 0], [-12, 0], lw=11, color="k", solid_capstyle="butt", zorder=1)
    a.plot([0, 14], [0, 0], lw=11, color="k", solid_capstyle="butt", zorder=1)
    # el robot, que sube y rota de a poco
    cx, cy = 0.0, -8.0 + dy
    rb = Rectangle((-3.2, -3.2), 6.4, 6.4, color="#3b4ccc", alpha=0.85, zorder=3,
                   transform=(plt.matplotlib.transforms.Affine2D()
                              .rotate_deg(rot_deg).translate(cx, cy) + a.transData))
    a.add_patch(rb)
    # el ROI que ve la camara: por delante del robot
    th = np.radians(rot_deg + 90)
    fx, fy = cx + 7.5*np.cos(th), cy + 7.5*np.sin(th)
    a.add_patch(plt.Circle((fx, fy), 5.2, color="#3b4ccc", alpha=0.13, zorder=2))
    a.plot([fx], [fy], "+", color="#3b4ccc", ms=9, mew=2, zorder=4)
    a.text(fx+5.6, fy, "lo que ve", color="#3b4ccc", fontsize=9, va="center")
    a.set_title(tit, fontsize=11.5, fontweight="bold", color=col)
    a.text(0.5, -0.05, sub, transform=a.transAxes, ha="center", va="top",
           fontsize=10.2, color=col)
    a.set_xlim(-11, 20); a.set_ylim(-14, 16)
    a.set_aspect("equal"); a.axis("off")

fig.suptitle("Por qué se sale:  NO gira en el lugar — avanza mientras gira, se pasa "
             "el codo, y se queda sin línea que medir",
             fontsize=13.5, fontweight="bold")
fig.subplots_adjust(left=0.02, right=0.98, top=0.86, bottom=0.16, wspace=0.05)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "POR_QUE_SE_SALE.png")
fig.savefig(out, dpi=112, facecolor="white")
print("->", out)
