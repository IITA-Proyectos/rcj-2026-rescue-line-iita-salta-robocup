# -*- coding: utf-8 -*-
"""
NUEVO CODE V4 - refinamiento de continuidad espacial del target.

V4 parte de la percepción V3 y agrega una regla que faltaba:
la X no puede "teletransportarse" grandes distancias dentro del mismo lado
aunque siga estando sobre una centerline válida.

Pipeline:
  máscara -> componente con identidad temporal -> centerline -> target geométrico
  -> guard de continuidad de rama -> guard de velocidad espacial del target
  -> angle preview (todavía NO DriveBase)

Propiedades buscadas:
- cada X aceptada está sobre la centerline elegida;
- una inversión fuerte no ocurre de un frame al siguiente;
- un salto grande mismo-lado se recorre gradualmente sobre la centerline actual;
- después de PERDIDA se resetea continuidad: evidencia nueva manda;
- no se copian gains/motores de Airborne ni se toca hardware.

NO mueve el robot. NO es simulación física.
"""

import argparse
import csv
import importlib.util
import math
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location(
    "nuevo_code_v3", os.path.join(HERE, "nuevo_code_v3.py")
)
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)

W, H, CENTER = v3.W, v3.H, v3.CENTER

COLORS = v3.COLORS.copy()
COLORS["TARGET_LIMIT"] = (0, 180, 255)


def pxy(p):
    if p is None:
        return None
    return int(round(p[0])), int(round(p[1]))


class SpatialTargetGuard:
    """
    Limita el movimiento espacial de la X ENTRE FRAMES.

    No interpola en el aire: si limita un salto, la nueva X se elige entre
    píxeles REALES del skeleton actual.

    El límite se eligió con margen sobre los controles positivos conocidos:
      - 33.3 fps: 24 px/frame
      - 20 fps: 30 px/frame
    """

    def __init__(self, fps):
        self.fps = float(fps)
        self.previous = None
        self.max_step = 30.0 if self.fps <= 25 else 24.0

    def reset(self):
        self.previous = None

    def step(self, proposed, skel):
        if proposed is None or skel is None:
            self.reset()
            return None, "NO_TARGET", None

        proposed = (float(proposed[0]), float(proposed[1]))

        # Primera evidencia luego de una pérdida: no arrastrar memoria vieja.
        if self.previous is None:
            self.previous = proposed
            return proposed, "REACQ_ACCEPT", None

        jump = math.hypot(
            proposed[0] - self.previous[0],
            proposed[1] - self.previous[1]
        )

        if jump <= self.max_step:
            self.previous = proposed
            return proposed, "ACCEPT", jump

        ys, xs = np.nonzero(skel)
        if xs.size == 0:
            self.reset()
            return None, "NO_SKELETON", jump

        # Puntos del skeleton físicamente alcanzables por la X en este frame.
        dprev = np.sqrt(
            (xs - self.previous[0]) ** 2 +
            (ys - self.previous[1]) ** 2
        )
        reachable = np.where(dprev <= self.max_step)[0]

        if reachable.size == 0:
            self.reset()
            return None, "REACQ_PENDING", jump

        # Entre los puntos alcanzables, elegir el que más se acerca al target
        # geométrico propuesto. Así no se congela: avanza sobre la centerline.
        dgoal = (
            (xs[reachable] - proposed[0]) ** 2 +
            (ys[reachable] - proposed[1]) ** 2
        )
        j = reachable[int(np.argmin(dgoal))]
        accepted = (float(xs[j]), float(ys[j]))

        self.previous = accepted
        return accepted, "SPATIAL_LIMIT", jump


class ControlPreviewV4(v3.ControlPreview):
    """
    Igual filosofía V3. El control preview sólo limita rapidez angular.
    Si no hay target, resetea la memoria para que la reacquisición nueva mande.
    """

    def step(self, target):
        if target is None:
            self.angle = 0.0
            return dict(raw=None, control=None, action="SIN_TARGET_RESET")
        return super().step(target)


class NuevoCodeV4:
    def __init__(self, fps):
        self.per = v3.PercepcionV3(fps)
        self.branch_guard = v3.TargetContinuityGuard()
        self.spatial_guard = SpatialTargetGuard(fps)
        self.ctrl = ControlPreviewV4(fps)

    def step(self, g):
        r = self.per.step(g)

        target_geom = r.get("target")

        branch_target, branch_action = self.branch_guard.step(
            target_geom, r.get("skel")
        )

        accepted, spatial_action, proposed_jump = self.spatial_guard.step(
            branch_target, r.get("skel")
        )

        r["target_geometric"] = target_geom
        r["target_branch"] = branch_target
        r["target"] = accepted
        r["branch_guard"] = branch_action
        r["spatial_guard"] = spatial_action
        r["proposed_jump_px"] = proposed_jump

        c = self.ctrl.step(accepted)
        r["angle_target_raw"] = c["raw"]
        r["angle_control"] = c["control"]
        r["control_action"] = (
            branch_action + "|" + spatial_action + "|" + c["action"]
        )

        ref = accepted[0] if accepted is not None else CENTER
        r["poi"] = v3.poi_component(r.get("comp"), ref)

        r["target_on_skeleton"] = False
        if accepted is not None and r.get("skel") is not None:
            x, y = pxy(accepted)
            r["target_on_skeleton"] = bool(
                0 <= x < W and 0 <= y < H and r["skel"][y, x]
            )

        return r


def draw_panel(r):
    vis = np.zeros((H, W, 3), np.uint8)
    vis[r["mask"] > 0] = (45, 45, 45)

    if r.get("comp") is not None:
        vis[r["comp"] > 0] = (35, 95, 35)

    if r.get("skel") is not None:
        vis[r["skel"] > 0] = (0, 210, 255)

    if r.get("path"):
        q = np.asarray(
            [(int(round(x)), int(round(y))) for x, y in r["path"]],
            np.int32
        )
        if len(q) >= 2:
            cv2.polylines(vis, [q], False, (255, 170, 60), 1)

    for label, key, col in [
        ("T", "top", (60, 60, 255)),
        ("B", "bottom", (0, 255, 255)),
        ("L", "left", (255, 100, 40)),
        ("R", "right", (255, 100, 40)),
    ]:
        p = r["poi"].get(key)
        if p is None:
            continue
        q = pxy(p)
        cv2.circle(vis, q, 3, col, -1)
        cv2.putText(
            vis, label, (q[0] + 3, max(10, q[1] - 3)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.32, col, 1, cv2.LINE_AA
        )

    if r.get("start") is not None:
        cv2.circle(vis, pxy(r["start"]), 3, (255, 130, 40), -1)

    if r.get("target") is not None:
        col = (
            (255, 255, 255)
            if r["state"] in ("HIGH", "MEDIUM")
            else (0, 230, 255)
        )
        cv2.drawMarker(
            vis, pxy(r["target"]), col,
            cv2.MARKER_TILTED_CROSS, 12, 2
        )

    a = r.get("angle_control")
    if a is not None:
        L = 35
        rad = math.radians(a)
        x0, y0 = int(round(CENTER)), H - 2
        x1 = int(round(x0 - L * math.sin(rad)))
        y1 = int(round(y0 - L * math.cos(rad)))
        cv2.arrowedLine(
            vis, (x0, y0), (x1, y1),
            (255, 255, 255), 1, tipLength=0.25
        )

    cv2.line(
        vis, (int(round(CENTER)), 0),
        (int(round(CENTER)), H - 1),
        (95, 95, 95), 1
    )
    return vis


def run(video, outavi, outcsv, fps, desde=0, hasta=10**9):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir " + video)

    tr = NuevoCodeV4(fps)

    E = 4
    CW, CH = W * E, H * E
    OW, OH = CW * 2, CH + 245

    vw = cv2.VideoWriter(
        outavi, cv2.VideoWriter_fourcc(*"MJPG"), fps, (OW, OH)
    )

    f = open(outcsv, "w", newline="", encoding="utf-8")
    wr = csv.writer(f)
    wr.writerow([
        "frame", "time_s", "state",
        "atan2_old_deg",
        "target_x", "target_y",
        "target_angle_raw_deg",
        "centerline_heading_deg",
        "control_angle_deg",
        "branch_guard", "spatial_guard",
        "proposed_jump_px",
        "target_on_skeleton",
        "mode", "reason"
    ])

    i = 0
    metrics = dict(
        frames=0, targets=0, no_target=0, off_path=0,
        spatial_limited=0, max_accepted_jump=0.0
    )
    prev = None

    while True:
        ok, fr = cap.read()
        if not ok:
            break

        g = v3.v2.frame_pi(fr)
        r = tr.step(g)
        old = v3.v2.atan2_actual(g)

        if i < desde:
            i += 1
            continue
        if i > hasta:
            break

        metrics["frames"] += 1
        tgt = r.get("target")

        if tgt is not None:
            metrics["targets"] += 1
            if not r["target_on_skeleton"]:
                metrics["off_path"] += 1
            if prev is not None:
                j = math.hypot(tgt[0] - prev[0], tgt[1] - prev[1])
                metrics["max_accepted_jump"] = max(
                    metrics["max_accepted_jump"], j
                )
            prev = tgt
        else:
            metrics["no_target"] += 1
            prev = None

        if r["spatial_guard"] == "SPATIAL_LIMIT":
            metrics["spatial_limited"] += 1

        wr.writerow([
            i, f"{i/fps:.3f}", r["state"], f"{old:.3f}",
            "" if tgt is None else f"{tgt[0]:.2f}",
            "" if tgt is None else f"{tgt[1]:.2f}",
            "" if r.get("angle_target_raw") is None else f"{r['angle_target_raw']:.2f}",
            "" if r.get("heading") is None else f"{r['heading']:.2f}",
            "" if r.get("angle_control") is None else f"{r['angle_control']:.2f}",
            r.get("branch_guard", ""),
            r.get("spatial_guard", ""),
            "" if r.get("proposed_jump_px") is None else f"{r['proposed_jump_px']:.2f}",
            int(r.get("target_on_skeleton", False)),
            r.get("mode", ""),
            r.get("reason", "")
        ])

        cam = cv2.resize(g, (CW, CH), interpolation=cv2.INTER_NEAREST)
        pan = cv2.resize(draw_panel(r), (CW, CH), interpolation=cv2.INTER_NEAREST)
        out = np.zeros((OH, OW, 3), np.uint8)
        out[:CH, :CW] = cam
        out[:CH, CW:] = pan

        cv2.putText(
            out, "CAMARA QUE VIO LA PI", (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX, .6,
            (235,235,235), 1, cv2.LINE_AA
        )
        cv2.putText(
            out, "NUEVO CODE V4", (CW + 10, 24),
            cv2.FONT_HERSHEY_SIMPLEX, .6,
            (235,235,235), 1, cv2.LINE_AA
        )

        y0 = CH + 28
        col = COLORS.get(r["state"], (235,235,235))

        lines = [
            (f"frame {i}  t={i/fps:.2f}s   ESTADO {r['state']}", col),
            (f"ANGLE viejo atan2          {old:+6.1f} deg", (100,100,255)),
            ("ANGLE target geometrico    " +
             ("--" if r.get("angle_target_raw") is None else f"{r['angle_target_raw']:+6.1f}") +
             " deg", (120,230,120)),
            ("RUMBO centerline (der+)    " +
             ("--" if r.get("heading") is None else f"{r['heading']:+6.1f}") +
             " deg", (0,210,255)),
            ("ANGLE CONTROL -> Teensy    " +
             ("--" if r.get("angle_control") is None else f"{r['angle_control']:+6.1f}") +
             " deg", (255,255,255)),
        ]

        for k, (txt, c) in enumerate(lines):
            cv2.putText(
                out, txt, (10, y0 + 30*k),
                cv2.FONT_HERSHEY_SIMPLEX,
                .54 if k else .58, c, 1, cv2.LINE_AA
            )

        tgt_txt = "--" if tgt is None else f"({tgt[0]:.1f},{tgt[1]:.1f})"
        cv2.putText(
            out,
            f"TARGET {tgt_txt} | BRANCH {r['branch_guard']} | SPACE {r['spatial_guard']}",
            (10, y0 + 155),
            cv2.FONT_HERSHEY_SIMPLEX, .44,
            (210,210,210), 1, cv2.LINE_AA
        )

        cv2.putText(
            out,
            "T/B/L/R=POI | amarillo=centerline | X=target | flecha=control",
            (10, y0 + 185),
            cv2.FONT_HERSHEY_SIMPLEX, .42,
            (190,190,190), 1, cv2.LINE_AA
        )

        cv2.putText(
            out,
            "SHADOW: refina percepcion/control pedido; NO simula la trayectoria fisica futura",
            (10, y0 + 215),
            cv2.FONT_HERSHEY_SIMPLEX, .42,
            (0,210,255), 1, cv2.LINE_AA
        )

        vw.write(out)
        i += 1

    cap.release()
    vw.release()
    f.close()
    print(metrics)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=33.3)
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10**9)
    ap.add_argument("--avi", default="nuevo_code_v4.avi")
    ap.add_argument("--csv", default="nuevo_code_v4.csv")
    a = ap.parse_args()

    run(a.video, a.avi, a.csv, a.fps, a.desde, a.hasta)


if __name__ == "__main__":
    main()
