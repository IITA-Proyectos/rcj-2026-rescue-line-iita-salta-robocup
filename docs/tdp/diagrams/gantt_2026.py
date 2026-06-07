# -*- coding: utf-8 -*-
"""
RescueBot IITA 2026 - Generador del Gantt del proyecto (estilo Airborne).

Eje mensual (trimestral en 2023-24, mensual en 2025-26 para priorizar esa etapa),
gates y el hito de clasificacion como filas propias, color por responsable.

COMO EDITAR:
  - Cada fila esta en la lista ROWS. Tipos:
      {"kind":"task",      "label":..., "start":"YYYY-MM-DD", "end":"YYYY-MM-DD", "owner":"<clave de OWNERS>"}
      {"kind":"gate",      "label":..., "date":"YYYY-MM-DD"}
      {"kind":"milestone", "label":..., "date":"YYYY-MM-DD"}   # hito destacado (estrella)
  - El orden de ROWS (arriba->abajo) es el orden visual.
  - "owner" debe existir en OWNERS (define el color).
  - Corre:   python gantt_2026.py
  - Salidas: ../assets/project-gantt-2026-detailed.png  y  .svg
"""
import os
import datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

# ---- Personas / colores (edita aca) ----
OWNERS = {
    "Team":        ("#4C6EF5", "Team"),
    "Benjamin":    ("#F59F00", "Benjamin"),
    "Lucio":       ("#2F9E44", "Lucio"),
    "Laureano":    ("#9C36B5", "Laureano"),
    "Team+mentor": ("#1098AD", "Team + mentor"),
}
GATE_COLOR = "#d9480f"
MILE_COLOR = "#e8a200"

# ---- Filas del cronograma (edita / agrega aca, arriba -> abajo) ----
ROWS = [
    {"kind": "task", "label": "Robot concept & architecture decisions",     "start": "2023-08-01", "end": "2023-09-30", "owner": "Team"},
    {"kind": "task", "label": "PCB design & electronics architecture",       "start": "2023-09-01", "end": "2024-03-01", "owner": "Benjamin"},
    {"kind": "task", "label": "Early line-following algorithm",              "start": "2023-08-01", "end": "2024-12-31", "owner": "Lucio"},
    {"kind": "task", "label": "Full 3D robot design (CAD)",                  "start": "2024-01-01", "end": "2024-07-15", "owner": "Laureano"},
    {"kind": "gate", "label": "Gate: stable CAD",                            "date":  "2024-07-15"},
    {"kind": "task", "label": "Base line-following code integration",        "start": "2024-06-15", "end": "2024-12-31", "owner": "Lucio"},
    {"kind": "task", "label": "Green-marker detection & turns",              "start": "2024-08-01", "end": "2025-03-01", "owner": "Lucio"},
    {"kind": "task", "label": "OpenCV rescue-zone prototype",                "start": "2024-09-01", "end": "2025-03-01", "owner": "Benjamin"},
    {"kind": "task", "label": "Reliable full line-following version",        "start": "2025-03-01", "end": "2025-08-31", "owner": "Lucio"},
    {"kind": "task", "label": "YOLOv8n rescue-model migration",              "start": "2025-04-01", "end": "2025-08-31", "owner": "Benjamin"},
    {"kind": "task", "label": "Complete rescue-zone behavior",               "start": "2025-08-01", "end": "2025-09-30", "owner": "Benjamin"},
    {"kind": "task", "label": "First complete robot (ONNX model)",          "start": "2025-09-01", "end": "2025-10-15", "owner": "Team"},
    {"kind": "gate", "label": "Gate: first full robot (ONNX)",              "date":  "2025-09-20"},
    {"kind": "task", "label": "RoboLiga lessons & high deposit-zone update", "start": "2025-10-15", "end": "2025-12-31", "owner": "Benjamin"},
    {"kind": "milestone", "label": "Qualified for RoboCup 2026 (Nov 2025)",  "date":  "2025-11-15"},
    {"kind": "task", "label": "Repository migration & 2026 planning",        "start": "2026-01-01", "end": "2026-02-28", "owner": "Team"},
    {"kind": "task", "label": "Benchmark, rules & risk audit",               "start": "2026-02-01", "end": "2026-03-01", "owner": "Team+mentor"},
    {"kind": "gate", "label": "Gate: 2026 audit & plan",                     "date":  "2026-02-28"},
    {"kind": "task", "label": "Power-tree & electronics documentation",      "start": "2026-02-01", "end": "2026-04-30", "owner": "Benjamin"},
    {"kind": "task", "label": "Motion safety & encoder reliability",         "start": "2026-02-01", "end": "2026-05-31", "owner": "Laureano"},
    {"kind": "task", "label": "TFLite deployment & AI speed optimization",   "start": "2026-03-01", "end": "2026-04-30", "owner": "Benjamin"},
    {"kind": "task", "label": "Anti-flash, AGCWD & dataset retraining",      "start": "2026-03-01", "end": "2026-05-31", "owner": "Benjamin"},
    {"kind": "task", "label": "Serial protocol & runtime hardening",         "start": "2026-05-01", "end": "2026-05-31", "owner": "Benjamin"},
    {"kind": "task", "label": "APDS floor confirmation (red/silver)",        "start": "2026-05-01", "end": "2026-05-31", "owner": "Laureano"},
    {"kind": "task", "label": "Physical measurement & TEST_LOG campaign",    "start": "2026-05-01", "end": "2026-06-07", "owner": "Team"},
    {"kind": "gate", "label": "Gate: TEST_LOG / service logs",               "date":  "2026-06-07"},
    {"kind": "task", "label": "Final TDP diagrams & documentation",          "start": "2026-05-01", "end": "2026-06-30", "owner": "Team"},
    {"kind": "task", "label": "Evacuation exit-search fix (validated)",      "start": "2026-05-15", "end": "2026-06-07", "owner": "Team"},
    {"kind": "task", "label": "Final PDF, poster & competition strategy",    "start": "2026-06-01", "end": "2026-06-30", "owner": "Team"},
    {"kind": "gate", "label": "Gate: final PDF",                             "date":  "2026-06-30"},
]

AXIS_START = "2023-07-01"
AXIS_END = "2026-08-01"

def d(s):
    return dt.datetime.strptime(s, "%Y-%m-%d")

def month_iter(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield dt.datetime(y, m, 1)
        m += 1
        if m > 12:
            m, y = 1, y + 1

fig, ax = plt.subplots(figsize=(20, 12.5))
n = len(ROWS)

# bandas de anios alternadas + linea marcada en cada enero
for k, yr in enumerate([2023, 2024, 2025, 2026]):
    if k % 2 == 0:
        ax.axvspan(d("%d-01-01" % yr), d("%d-01-01" % (yr + 1)), color="#f3f5f7", zorder=0)
for yr in [2024, 2025, 2026]:
    ax.axvline(d("%d-01-01" % yr), color="#adb5bd", linewidth=1.0, alpha=0.7, zorder=1)

ylabels, label_colors = [], []
for i, row in enumerate(ROWS):
    y = n - 1 - i
    ylabels.append(row["label"])
    if row["kind"] == "task":
        start, end = d(row["start"]), d(row["end"])
        ax.barh(y, mdates.date2num(end) - mdates.date2num(start),
                left=mdates.date2num(start), height=0.6,
                color=OWNERS[row["owner"]][0], edgecolor="white", linewidth=0.8, zorder=3)
        label_colors.append("#212529")
    elif row["kind"] == "gate":
        gd = d(row["date"])
        ax.axvline(gd, color=GATE_COLOR, linestyle="--", linewidth=1.1, alpha=0.45, zorder=2)
        ax.scatter([gd], [y], marker="D", s=95, color=GATE_COLOR, edgecolor="white", linewidth=0.8, zorder=6)
        label_colors.append(GATE_COLOR)
    else:  # milestone
        md = d(row["date"])
        ax.axvline(md, color=MILE_COLOR, linestyle="--", linewidth=1.2, alpha=0.55, zorder=2)
        ax.scatter([md], [y], marker="*", s=460, color=MILE_COLOR, edgecolor="#7f5500", linewidth=0.8, zorder=7)
        label_colors.append(MILE_COLOR)

# eje Y
ax.set_yticks(range(n))
ax.set_yticklabels(list(reversed(ylabels)), fontsize=9.5)
for tick, col in zip(ax.get_yticklabels(), list(reversed(label_colors))):
    tick.set_color(col)
    if col in (GATE_COLOR, MILE_COLOR):
        tick.set_fontweight("bold")
ax.set_ylim(-0.6, n - 0.4)

# eje X: trimestral en 2023-24, mensual en 2025-26 (prioriza la etapa densa)
major_ticks, major_labels = [], []
for mdt in month_iter(d(AXIS_START), d(AXIS_END)):
    if mdt.year >= 2025 or mdt.month in (1, 4, 7, 10):
        major_ticks.append(mdt)
        major_labels.append(mdt.strftime("%b %y"))
ax.set_xlim(d(AXIS_START), d(AXIS_END))
ax.set_xticks(major_ticks)
ax.set_xticklabels(major_labels, rotation=45, ha="left", fontsize=9)
ax.xaxis.set_minor_locator(mdates.MonthLocator())
ax.grid(axis="x", which="minor", color="#eceef0", linewidth=0.6, alpha=0.8, zorder=0)
ax.grid(axis="x", which="major", color="#ced4da", linewidth=0.8, alpha=0.9, zorder=0)
ax.tick_params(axis="x", which="both", length=0, pad=2)
ax.xaxis.set_ticks_position("top")
for spine in ax.spines.values():
    spine.set_visible(False)

# leyenda abajo
legend_items = [Patch(facecolor=OWNERS[k][0], label=OWNERS[k][1])
                for k in ["Team", "Benjamin", "Lucio", "Laureano", "Team+mentor"]]
legend_items.append(plt.Line2D([0], [0], marker="D", color="w", markerfacecolor=GATE_COLOR, markersize=10, label="Review gate"))
legend_items.append(plt.Line2D([0], [0], marker="*", color="w", markerfacecolor=MILE_COLOR, markeredgecolor="#7f5500", markersize=16, label="Key milestone"))
ax.legend(handles=legend_items, loc="upper center", ncol=7, fontsize=10.5, frameon=False, bbox_to_anchor=(0.5, -0.04))

fig.suptitle("RescueBot IITA - Project Schedule (Gantt) 2023-2026", y=0.975, fontsize=17, fontweight="bold")
plt.subplots_adjust(left=0.255, right=0.99, top=0.85, bottom=0.07)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets"))
png = os.path.join(OUT, "project-gantt-2026-detailed.png")
svg = os.path.join(OUT, "project-gantt-2026-detailed.svg")
fig.savefig(png, dpi=200)
fig.savefig(svg)
print("OK ->", png)
print("OK ->", svg)
