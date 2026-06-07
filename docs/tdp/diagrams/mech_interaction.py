# -*- coding: utf-8 -*-
"""
RescueBot IITA 2026 - Mapa de interaccion de submodulos mecanicos (logica corregida).
Chasis = backbone. Izquierda/arriba = interfaces de montaje. Derecha = camino de la
victima (claw -> storage -> deposit -> zone). FCL/FCR -> deposit habilita el soltado.

Correr:   python mech_interaction.py
Salidas:  ../assets/mechanical-interaction-map-2026.png  y  .svg
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch, FancyArrowPatch

C_CHASSIS = "#343a40"
C_STRUCT = "#4C6EF5"
C_SENSOR = "#2F9E44"
C_RESCUE = "#F59F00"
C_SWITCH = "#1098AD"
C_ZONE = "#ced4da"
C_FLOW = "#d9480f"
C_MOUNT = "#868e96"

fig, ax = plt.subplots(figsize=(16, 10))
ax.set_xlim(0, 162)
ax.set_ylim(0, 105)
ax.axis("off")

def box(cx, cy, w, h, text, color, fs=10.5, tcolor="white", dashed=False, ec="white"):
    ls = (0, (5, 3)) if dashed else "solid"
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                 boxstyle="round,pad=0.6,rounding_size=2.2",
                 facecolor=color, edgecolor=ec, linewidth=1.6, linestyle=ls, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center", color=tcolor,
            fontsize=fs, fontweight="bold", zorder=4)

def arrow(p1, p2, label, color, fs=8.5, rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=16,
                 connectionstyle="arc3,rad=%s" % rad, color=color, linewidth=1.9, zorder=2))
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    ax.text(mx, my, label, ha="center", va="center", fontsize=fs, color=color,
            fontweight="bold", zorder=5,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=color, lw=0.8, alpha=0.95))

# --- Bloques ---
box(76, 54, 32, 17, "CHASSIS FRAME\n(PLA modular, M3 screws)", C_CHASSIS, fs=12)
box(20, 88, 30, 11, "Camera arm", C_STRUCT)
box(20, 62, 30, 12, "Electronics tray\n(PCB / RPi / Teensy)", C_STRUCT)
box(20, 32, 30, 15, "Drivebase\n(4x motor+encoder,\nwheels + omniwheels)", C_STRUCT)
box(76, 91, 38, 11, "Sensor mounts\n(ToF / ultrasonic / APDS9960)", C_SENSOR)
box(137, 88, 36, 14, "Claw assembly\n(Servo L / R / Lift,\nshared 3D-printed rail)", C_RESCUE)
box(137, 62, 36, 12, "Storage channel\n(Servo Sort)", C_RESCUE)
box(137, 36, 36, 12, "Deposit guide\n(Servo Deposit)", C_RESCUE)
box(137, 13, 36, 11, "Deposit zone\n(red / green side)", C_ZONE, tcolor="#343a40", dashed=True, ec="#868e96")
box(99, 20, 28, 11, "FCL / FCR\nlimit switches", C_SWITCH)

# --- Interfaces de montaje (modulo -> chasis), grises ---
arrow((35, 86), (62, 59), "fixed calibration mount", C_MOUNT, rad=-0.15)
arrow((35, 62), (60, 56), "PCB-outline mounts", C_MOUNT)
arrow((35, 34), (61, 49), "M3 motor brackets, low CoG", C_MOUNT, rad=0.12)
arrow((76, 85), (76, 63), "fixed brackets, no drift", C_SENSOR)
arrow((119, 86), (92, 58), "shared printed rail, servo axes", C_MOUNT, rad=0.12)

# --- Camino de la victima (derecha, arriba->abajo), naranja ---
arrow((137, 81), (137, 68), "victim released (sort-during-lift)", C_FLOW)
arrow((137, 56), (137, 42), "gravity feed to L/R channel", C_FLOW)
arrow((137, 30), (137, 19), "release at aligned side", C_FLOW)

# --- Alineacion: FCL/FCR -> deposit, celeste ---
arrow((113, 22), (120, 33), "wall-contact alignment gates release", C_SWITCH, rad=-0.1)

# --- Leyenda ---
legend = [
    Patch(facecolor=C_CHASSIS, label="Structural backbone"),
    Patch(facecolor=C_STRUCT, label="Structural module"),
    Patch(facecolor=C_SENSOR, label="Sensing module"),
    Patch(facecolor=C_RESCUE, label="Rescue mechanism"),
    Patch(facecolor=C_SWITCH, label="Alignment switches"),
    Patch(facecolor=C_ZONE, edgecolor="#868e96", label="External target (deposit zone)"),
    FancyArrowPatch((0, 0), (1, 0), arrowstyle="-|>", mutation_scale=12, color=C_FLOW, label="Victim pathway"),
]
ax.legend(handles=legend, loc="lower center", ncol=7, fontsize=9, frameon=False, bbox_to_anchor=(0.5, -0.02))

ax.set_title("Mechanical submodule interaction map - mounting interfaces and victim pathway",
             fontsize=15, fontweight="bold", pad=16)
plt.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.07)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets"))
png = os.path.join(OUT, "mechanical-interaction-map-2026.png")
svg = os.path.join(OUT, "mechanical-interaction-map-2026.svg")
fig.savefig(png, dpi=200)
fig.savefig(svg)
print("OK ->", png)
print("OK ->", svg)
