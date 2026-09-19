# -*- coding: utf-8 -*-
"""COMO SE MIDE UN CODO, QUE NO ES LO MISMO QUE UNA CURVA.

Benjamin, 26-ago, con un dibujo: "generalmente se sale en la linea asi, si ves
no son 90 grados". Y tiene razon: lo que dibujo son CODOS, no curvas.

Un codo VIVO no tiene radio: son dos rectas que se cruzan. Pedir "medi el radio
con una cinta" estaba mal planteado para esa geometria.

    python medir_codo.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

fig, ax = plt.subplots(1, 3, figsize=(16.5, 5.6))

# ---------------------------------------------------------------- 1: curva --
a = ax[0]
th = np.linspace(np.pi, np.pi/2, 100)
R = 8.0
a.plot(R*np.cos(th)+R, R*np.sin(th), lw=13, color="k", solid_capstyle="butt")
a.plot([R, R], [-9, 0], lw=13, color="k", solid_capstyle="butt")
a.plot([R, 18], [R, R], lw=13, color="k", solid_capstyle="butt")
a.plot([R], [0], "o", ms=7, color="#d62728")
a.annotate("", xy=(R, 0), xytext=(R, R),
           arrowprops=dict(arrowstyle="<->", color="#d62728", lw=2))
a.text(R+0.6, R/2, "R", color="#d62728", fontsize=17, fontweight="bold")
a.plot(R, R, "+", ms=14, color="#d62728", mew=2.5)
a.text(R+0.5, R+0.8, "centro", color="#d62728", fontsize=11)
a.set_title("CURVA — sí tiene radio\nse mide del centro al medio de la cinta",
            fontsize=12, fontweight="bold")

# ------------------------------------------------------------------ 2: codo --
b = ax[1]
b.plot([8, 8], [-9, 8], lw=13, color="k", solid_capstyle="butt")
b.plot([8, 18], [8, 8], lw=13, color="k", solid_capstyle="butt")
b.plot([8], [8], "o", ms=11, color="#d62728")
arc = np.linspace(np.pi/2, np.pi, 40)
b.plot(2.6*np.cos(arc)+8, 2.6*np.sin(arc)+8, color="#d62728", lw=2)
b.text(4.6, 10.6, r"$\alpha$", color="#d62728", fontsize=19, fontweight="bold")
b.text(8.6, -4, "NO hay radio.\nEl robot tiene que\nGIRAR EN EL LUGAR",
       color="#d62728", fontsize=11.5, fontweight="bold")
b.set_title("CODO VIVO — no tiene radio\nlo único que se mide es el ÁNGULO α",
            fontsize=12, fontweight="bold")

# ------------------------------------------------- 3: codo con acuerdo -------
c = ax[2]
r = 3.0
th2 = np.linspace(np.pi, np.pi/2, 60)
c.plot([8, 8], [-9, 8-r], lw=13, color="k", solid_capstyle="butt")
c.plot(r*np.cos(th2)+8+r, r*np.sin(th2)+8-r, lw=13, color="k", solid_capstyle="butt")
c.plot([8+r, 18], [8, 8], lw=13, color="k", solid_capstyle="butt")
c.plot([8+r], [8-r], "+", ms=14, color="#2ca02c", mew=2.5)
c.annotate("", xy=(8, 8-r), xytext=(8+r, 8-r),
           arrowprops=dict(arrowstyle="<->", color="#2ca02c", lw=2))
c.text(9.0, 8-r-1.3, "r", color="#2ca02c", fontsize=17, fontweight="bold")
c.text(-1, -6.5, "ESTE es el número que sirve:\nel radio de ACUERDO r.\n"
       "Es el más chico que el robot\ntiene que poder trazar.",
       color="#2ca02c", fontsize=11, fontweight="bold")
c.set_title("CODO CON ACUERDO — el caso real\nse mide r, el radio de la esquina",
            fontsize=12, fontweight="bold")

for x in ax:
    x.set_xlim(-3, 20); x.set_ylim(-10, 15)
    x.set_aspect("equal"); x.axis("off")
fig.suptitle("Cómo medir la línea:  una CURVA tiene radio, un CODO tiene ángulo, "
             "y un codo con acuerdo tiene las dos cosas",
             fontsize=13.5, fontweight="bold")
fig.tight_layout()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "COMO_MEDIR_CODO.png")
fig.savefig(out, dpi=115, facecolor="white")
print("->", out)
