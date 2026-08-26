# -*- coding: utf-8 -*-
"""COMO SE APOYA EL TRANSPORTADOR SOBRE UN CODO. Benjamin, 26-ago."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, os

fig, ax = plt.subplots(1, 3, figsize=(18, 6.4))
ANG = 115.0                      # angulo interior de ejemplo

def codo(a, ang, lw=13):
    """dibuja el codo con vertice en (0,0): una rama hacia abajo, otra al angulo"""
    a.plot([0, 0], [0, -13], lw=lw, color="k", solid_capstyle="butt", zorder=1)
    th = np.radians(ang - 90)
    a.plot([0, 15*np.cos(th)], [0, 15*np.sin(th)], lw=lw, color="k",
           solid_capstyle="butt", zorder=1)

# ---------------------------------------------------- 1: donde va el centro --
a = ax[0]
codo(a, ANG)
a.add_patch(plt.Circle((0, 0), 8.5, color="#3b4ccc", alpha=0.10, zorder=2))
arc = np.linspace(0, np.pi, 120)
a.plot(8.5*np.cos(arc), 8.5*np.sin(arc), color="#3b4ccc", lw=2.5, zorder=3)
a.plot([-8.5, 8.5], [0, 0], color="#3b4ccc", lw=2.5, zorder=3)
a.plot(0, 0, "o", ms=13, color="#d62728", zorder=6)
a.annotate("EL CENTRO del transportador\nVA EN EL VÉRTICE\n(donde se cruzan los EJES\nde las dos cintas)",
           xy=(0, 0), xytext=(-13, 11), fontsize=11, fontweight="bold",
           color="#d62728",
           arrowprops=dict(arrowstyle="->", color="#d62728", lw=2.2))
a.text(0, -16.5, "NO en el borde de la cinta:\nen el MEDIO de la cinta",
       ha="center", fontsize=10.5, color="#d62728")
a.set_title("1. Dónde apoyarlo", fontsize=13, fontweight="bold")

# ------------------------------------------------------- 2: como alinear -----
b = ax[1]
codo(b, ANG)
b.plot([0, 0], [0, -13], lw=2.2, color="#ff7f0e", ls="--", zorder=5)
th = np.radians(ANG - 90)
b.plot([0, 15*np.cos(th)], [0, 15*np.sin(th)], lw=2.2, color="#ff7f0e",
       ls="--", zorder=5)
arc2 = np.linspace(-np.pi/2, np.radians(ANG-90), 60)
b.plot(6*np.cos(arc2), 6*np.sin(arc2), color="#d62728", lw=3, zorder=6)
b.text(6.0, -1.5, r"$\alpha$", fontsize=26, color="#d62728", fontweight="bold")
b.text(-14, 12, "La RAYA DEL 0 se alinea\ncon el EJE de una rama\n(la línea naranja punteada,\nno el borde negro)",
       fontsize=11, fontweight="bold", color="#ff7f0e")
b.text(0, -16.5, "y se lee dónde cae la otra rama", ha="center", fontsize=10.5)
b.set_title("2. Cómo alinearlo — se lee α", fontsize=13, fontweight="bold")

# ------------------------------------------------- 3: lo que hay que anotar --
c = ax[2]
codo(c, ANG)
arc3 = np.linspace(-np.pi/2, np.radians(ANG-90), 60)
c.plot(5*np.cos(arc3), 5*np.sin(arc3), color="#d62728", lw=3, zorder=6)
c.text(5.2, -2.0, r"$\alpha$", fontsize=22, color="#d62728", fontweight="bold")
# el giro que hace el robot
thm = np.radians(ANG - 90)
c.annotate("", xy=(9*np.cos(thm), 9*np.sin(thm)), xytext=(0, 9),
           arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=3,
                           connectionstyle="arc3,rad=0.42"))
c.text(-12.5, 13.5, "GIRO del robot = 180° − α",
       fontsize=14, fontweight="bold", color="#2ca02c")
c.text(-12.5, -17.5,
       "α = 115°  →  el robot gira 65°\n"
       "α =  90°  →  gira 90°\n"
       "α =  40°  →  gira 140°  (casi vuelve)\n\n"
       "CUANTO MÁS CHICO α,\nMÁS TIENE QUE GIRAR.",
       fontsize=11, color="#2ca02c", fontweight="bold")
c.set_title("3. Lo que se anota", fontsize=13, fontweight="bold")

for x in ax:
    x.set_xlim(-16, 17); x.set_ylim(-22, 17)
    x.set_aspect("equal"); x.axis("off")

fig.suptitle("Cómo poner el transportador en un codo — y el error clásico: "
             "α NO es lo que gira el robot",
             fontsize=14, fontweight="bold")
fig.subplots_adjust(left=0.02, right=0.98, top=0.87, bottom=0.03, wspace=0.05)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TRANSPORTADOR.png")
fig.savefig(out, dpi=112, facecolor="white")
print("->", out)
