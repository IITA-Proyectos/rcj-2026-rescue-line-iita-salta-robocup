# -*- coding: utf-8 -*-
"""
NUEVO CODE V3 - shadow de seguimiento de línea adaptado al robot.

Objetivo de V3:
1) Mantener la geometría/centerline de V2.
2) Evitar que una bifurcación cambie de rama por "la mancha que está abajo".
   Si hay varias componentes NEAR, manda continuidad con el TARGET anterior.
3) Separar dos cosas:
      TARGET DE PERCEPCIÓN = dónde creemos que sigue la trayectoria.
      ANGLE DE CONTROL     = lo que mandaríamos a Teensy.
4) El target siempre queda sobre la centerline seleccionada.
5) Una inversion fuerte NO puede saltar directamente de un lado al otro:
   debe atravesar una zona neutral de la centerline o reacquirirse.
6) El preview de control aplica slew para evitar latigazos mismo-lado.

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
V2_PATH = os.path.join(HERE, "nuevo_code_v2.py")

spec = importlib.util.spec_from_file_location("nuevo_code_v2", V2_PATH)
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)

W, H, CENTER = v2.W, v2.H, v2.CENTER

COLORS = {
    "HIGH": (80, 220, 80),
    "MEDIUM": (80, 210, 220),
    "LOW": (0, 165, 255),
    "LOW_FORWARD": (0, 190, 255),
    "SIN_CERCA": (255, 180, 60),
    "PERDIDA": (80, 80, 255),
}

def pxy(p):
    if p is None:
        return None
    return int(round(p[0])), int(round(p[1]))

def sgn(x, dead=12.0):
    if x is None or not np.isfinite(x):
        return 0
    if x > dead:
        return 1
    if x < -dead:
        return -1
    return 0

def poi_component(comp, ref_x=None):
    """POI T/B/L/R sólo para diagnóstico visual."""
    if comp is None:
        return dict(top=None, bottom=None, left=None, right=None)

    ys, xs = np.nonzero(comp > 0)
    if len(xs) == 0:
        return dict(top=None, bottom=None, left=None, right=None)

    ref_x = CENTER if ref_x is None else float(ref_x)
    ymin, ymax = int(ys.min()), int(ys.max())
    xmin, xmax = int(xs.min()), int(xs.max())

    def choose_run(vals, ref):
        rs = v2.runs_1d(vals)
        if not rs:
            return float(np.mean(vals))
        r = min(rs, key=lambda q: abs(((q[0] + q[1]) / 2.0) - ref))
        return (r[0] + r[1]) / 2.0

    top = (choose_run(xs[ys == ymin], ref_x), float(ymin))
    bottom = (choose_run(xs[ys == ymax], CENTER), float(ymax))
    left = (float(xmin), float(np.mean(ys[xs == xmin])))
    right = (float(xmax), float(np.mean(ys[xs == xmax])))

    return dict(top=top, bottom=bottom, left=left, right=right)

class PercepcionV3(v2.NuevoCodeV2):
    """
    Diferencia esencial con V2:
    cuando DOS o más componentes válidas llegan a NEAR,
    V2 miraba continuidad con prev_entry.
    V3 mira primero continuidad con prev_target.

    Esto conserva la rama que ya veníamos persiguiendo en una bifurcación.
    """

    def choose_component(self, m):
        lab, cands = v2.cc_candidates(m)
        if not cands:
            return lab, None, "PERDIDA"

        near = [c for c in cands if c["near"]]

        if near:
            amax = max(c["area"] for c in near)
            viable = [
                c for c in near
                if c["area"] >= max(v2.MIN_AREA, 0.05 * amax)
            ]

            if len(viable) >= 2 and self.prev_target is not None:
                def score(q):
                    d_target = v2.component_distance(
                        lab, q["k"], self.prev_target
                    )
                    d_entry = v2.component_distance(
                        lab, q["k"], self.prev_entry
                    )
                    # target = identidad de la rama; entry sólo desempata
                    return d_target + 0.20 * d_entry

                c = min(viable, key=score)
                mode = "NEAR_BRANCH_LOCK"
            else:
                c = min(
                    viable,
                    key=lambda q: v2.component_distance(
                        lab, q["k"], self.prev_entry
                    )
                )
                mode = "NEAR"

            if not c["mid"] and self.prev_target is not None:
                ahead = [
                    a for a in cands
                    if not a["near"] and a["ymax"] >= 45
                ]
                if ahead:
                    a = min(
                        ahead,
                        key=lambda q: v2.component_distance(
                            lab, q["k"], self.prev_target
                        )
                    )
                    if v2.component_distance(
                        lab, a["k"], self.prev_target
                    ) < 35:
                        return lab, a, "AHEAD_BRIDGE"

            return lab, c, mode

        # SIN_CERCA: evidencia de adelante, con continuidad al target previo.
        ref = (
            self.prev_target
            if self.prev_target is not None
            else self.prev_entry
        )

        amax = max(c["area"] for c in cands)
        viable = [
            c for c in cands
            if c["area"] >= max(v2.MIN_AREA, 0.03 * amax)
        ]

        c = min(
            viable,
            key=lambda q:
                v2.component_distance(lab, q["k"], ref)
                + 0.08 * (119 - q["ymax"])
        )

        if (
            v2.component_distance(lab, c["k"], ref) > 75
            and c["ymax"] < 70
        ):
            return lab, None, "PERDIDA"

        return lab, c, "AHEAD"

    def path_target(self, comp, mode):
        # El resto del algoritmo V2 espera "NEAR".
        if mode == "NEAR_BRANCH_LOCK":
            base_mode = "NEAR"
        else:
            base_mode = mode
        return super().path_target(comp, base_mode)

class TargetContinuityGuard:
    """
    Regla geometrica V3:
    una trayectoria fuerte no puede teletransportarse de un lado fuerte al
    contrario en UN frame mientras seguimos viendo una centerline continua.

    Una inversion legitima tiene que atravesar la zona central o venir despues
    de una perdida/reacquisicion.
    """

    def __init__(self):
        self.previous = None
        self.DEAD = 10.0

    def _raw_angle(self, target):
        if target is None:
            return None
        return float(np.clip(
            -90.0 * (target[0] - CENTER) / (W / 2.0),
            -90.0, 90.0
        ))

    def step(self, proposed, skel):
        if proposed is None or skel is None:
            self.previous = None
            return None, "NO_TARGET"

        proposed = (float(proposed[0]), float(proposed[1]))
        accepted = proposed
        action = "ACCEPT"

        if self.previous is not None:
            pa = self._raw_angle(self.previous)
            na = self._raw_angle(proposed)

            direct_flip = (
                abs(pa) > self.DEAD and
                abs(na) > self.DEAD and
                np.sign(pa) != np.sign(na)
            )

            if direct_flip:
                ys, xs = np.nonzero(skel)

                if xs.size:
                    angles = np.clip(
                        -90.0 * (xs - CENTER) / (W / 2.0),
                        -90.0, 90.0
                    )

                    # Primera opcion: atravesar una zona neutral REAL de la
                    # centerline actual.
                    neutral = np.where(np.abs(angles) <= self.DEAD)[0]

                    if neutral.size:
                        dist = np.sqrt(
                            (xs[neutral] - self.previous[0]) ** 2 +
                            (ys[neutral] - self.previous[1]) ** 2
                        )
                        j = neutral[int(np.argmin(dist))]
                        accepted = (float(xs[j]), float(ys[j]))
                        action = "NEUTRAL_BRIDGE"

                    else:
                        # Segunda opcion: si la centerline aun conserva el lado
                        # anterior, acercarse al centro SIN cambiar de rama.
                        same = np.where(np.sign(angles) == np.sign(pa))[0]

                        if same.size:
                            dprev = np.sqrt(
                                (xs[same] - self.previous[0]) ** 2 +
                                (ys[same] - self.previous[1]) ** 2
                            )
                            center_dist = np.abs(xs[same] - CENTER)
                            score = 0.70 * center_dist + 0.30 * dprev
                            j = same[int(np.argmin(score))]
                            accepted = (float(xs[j]), float(ys[j]))
                            action = "SAME_SIDE_BRIDGE"
                        else:
                            accepted = None
                            action = "REACQ_PENDING"
                else:
                    accepted = None
                    action = "REACQ_PENDING"

        # Toda cruz aceptada tiene que estar SOBRE la centerline elegida.
        if accepted is not None:
            x, y = pxy(accepted)
            if not (
                0 <= x < W and 0 <= y < H and bool(skel[y, x])
            ):
                accepted = None
                action = "REJECT_OFF_CENTERLINE"

        self.previous = accepted
        return accepted, action


class ControlPreview:
    """
    Preview de lo que eventualmente se traducira al protocolo angle+90.

    V3 NO tunea el controlador fisico. Solo limita la velocidad de cambio del
    comando para que un salto grande MISMO-LADO tampoco se convierta en un
    latigazo mecanico instantaneo.
    """

    def __init__(self, fps):
        self.fps = float(fps)
        self.angle = 0.0
        self.SLEW_DEG_PER_SEC = 500.0

    def raw_angle(self, target):
        if target is None:
            return None
        return float(np.clip(
            -90.0 * (target[0] - CENTER) / (W / 2.0),
            -90.0, 90.0
        ))

    def step(self, target):
        raw = self.raw_angle(target)

        if raw is None:
            return dict(raw=None, control=None, action="SIN_TARGET")

        max_delta = self.SLEW_DEG_PER_SEC / self.fps
        delta = float(np.clip(
            raw - self.angle,
            -max_delta,
            max_delta
        ))

        self.angle += delta

        action = "TRACK" if abs(raw - self.angle) < 1e-6 else "SLEW"
        return dict(raw=raw, control=self.angle, action=action)


class NuevoCodeV3:
    def __init__(self, fps):
        self.per = PercepcionV3(fps)
        self.guard = TargetContinuityGuard()
        self.ctrl = ControlPreview(fps)

    def step(self, g):
        r = self.per.step(g)

        original_target = r.get("target")
        accepted, guard_action = self.guard.step(
            original_target,
            r.get("skel")
        )

        r["target_original"] = original_target
        r["target"] = accepted
        r["branch_guard"] = guard_action

        c = self.ctrl.step(accepted)
        r["angle_target_raw"] = c["raw"]
        r["angle_control"] = c["control"]
        r["control_action"] = guard_action + "|" + c["action"]

        ref = accepted[0] if accepted is not None else CENTER
        r["poi"] = poi_component(r.get("comp"), ref)

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
            [
                (int(round(x)), int(round(y)))
                for x, y in r["path"]
            ],
            np.int32
        )
        if len(q) >= 2:
            cv2.polylines(
                vis, [q], False, (255, 170, 60), 1
            )

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
            vis, label,
            (q[0] + 3, max(10, q[1] - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.32, col, 1, cv2.LINE_AA
        )

    if r.get("start") is not None:
        cv2.circle(
            vis, pxy(r["start"]),
            3, (255, 130, 40), -1
        )

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

    # Flecha de ANGLE CONTROL desde el centro inferior.
    a = r.get("angle_control")
    if a is not None:
        # positivo en el convenio actual = izquierda en imagen
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
        vis,
        (int(round(CENTER)), 0),
        (int(round(CENTER)), H - 1),
        (95, 95, 95), 1
    )

    return vis

def sign_flip(a, b, thr=10.0):
    if a is None or b is None:
        return False
    if not np.isfinite(a) or not np.isfinite(b):
        return False
    return (
        abs(a) > thr and
        abs(b) > thr and
        np.sign(a) != np.sign(b)
    )

def run(video, outavi, outcsv, fps, desde=0, hasta=10**9):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir " + video)

    tr = NuevoCodeV3(fps)

    E = 4
    CW, CH = W * E, H * E
    OW, OH = CW * 2, CH + 235

    vw = cv2.VideoWriter(
        outavi,
        cv2.VideoWriter_fourcc(*"MJPG"),
        fps,
        (OW, OH)
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
        "control_action",
        "target_on_skeleton",
        "mode", "reason"
    ])

    i = 0
    metrics = dict(
        frames=0,
        targets=0,
        off_path=0,
        raw_flips=0,
        control_flips=0,
        reversals_pending=0,
        reversals_confirmed=0,
    )

    prev_raw = None
    prev_control = None

    while True:
        ok, fr = cap.read()
        if not ok:
            break

        g = v2.frame_pi(fr)
        r = tr.step(g)
        old = v2.atan2_actual(g)

        if i < desde:
            i += 1
            continue
        if i > hasta:
            break

        metrics["frames"] += 1

        tgt = r.get("target")
        raw = r.get("angle_target_raw")
        control = r.get("angle_control")

        if tgt is not None:
            metrics["targets"] += 1
            if not r["target_on_skeleton"]:
                metrics["off_path"] += 1

        if sign_flip(prev_raw, raw):
            metrics["raw_flips"] += 1
        if sign_flip(prev_control, control):
            metrics["control_flips"] += 1

        if r["control_action"].startswith("REVERSA_PENDIENTE"):
            metrics["reversals_pending"] += 1
        if r["control_action"] == "REVERSA_CONFIRMADA":
            metrics["reversals_confirmed"] += 1

        if raw is not None:
            prev_raw = raw
        else:
            prev_raw = None

        if control is not None:
            prev_control = control
        else:
            prev_control = None

        wr.writerow([
            i, f"{i/fps:.3f}", r["state"],
            f"{old:.3f}",
            "" if tgt is None else f"{tgt[0]:.2f}",
            "" if tgt is None else f"{tgt[1]:.2f}",
            "" if raw is None else f"{raw:.2f}",
            "" if r.get("heading") is None else f"{r['heading']:.2f}",
            "" if control is None else f"{control:.2f}",
            r["control_action"],
            int(r["target_on_skeleton"]),
            r.get("mode", ""),
            r.get("reason", "")
        ])

        cam = cv2.resize(
            g, (CW, CH),
            interpolation=cv2.INTER_NEAREST
        )
        pan = cv2.resize(
            draw_panel(r), (CW, CH),
            interpolation=cv2.INTER_NEAREST
        )

        out = np.zeros((OH, OW, 3), np.uint8)
        out[:CH, :CW] = cam
        out[:CH, CW:] = pan

        cv2.putText(
            out, "CAMARA QUE VIO LA PI", (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX, .6,
            (235,235,235), 1, cv2.LINE_AA
        )
        cv2.putText(
            out, "NUEVO CODE V3", (CW + 10, 24),
            cv2.FONT_HERSHEY_SIMPLEX, .6,
            (235,235,235), 1, cv2.LINE_AA
        )

        y0 = CH + 28
        col = COLORS.get(r["state"], (235,235,235))

        cv2.putText(
            out,
            f"frame {i}  t={i/fps:.2f}s   ESTADO {r['state']}",
            (10, y0),
            cv2.FONT_HERSHEY_SIMPLEX, .58,
            col, 1, cv2.LINE_AA
        )

        cv2.putText(
            out,
            f"ANGLE viejo atan2          {old:+6.1f} deg",
            (10, y0 + 31),
            cv2.FONT_HERSHEY_SIMPLEX, .52,
            (100,100,255), 1, cv2.LINE_AA
        )

        rawtxt = "--" if raw is None else f"{raw:+6.1f}"
        cv2.putText(
            out,
            f"ANGLE target geometrico    {rawtxt} deg",
            (10, y0 + 61),
            cv2.FONT_HERSHEY_SIMPLEX, .52,
            (120,230,120), 1, cv2.LINE_AA
        )

        h = r.get("heading")
        htxt = "--" if h is None else f"{h:+6.1f}"
        cv2.putText(
            out,
            f"RUMBO centerline (der+)    {htxt} deg",
            (10, y0 + 91),
            cv2.FONT_HERSHEY_SIMPLEX, .52,
            (0,210,255), 1, cv2.LINE_AA
        )

        ctxt = "--" if control is None else f"{control:+6.1f}"
        cv2.putText(
            out,
            f"ANGLE CONTROL -> Teensy    {ctxt} deg",
            (10, y0 + 121),
            cv2.FONT_HERSHEY_SIMPLEX, .54,
            (255,255,255), 1, cv2.LINE_AA
        )

        tgt_txt = (
            "--" if tgt is None
            else f"({tgt[0]:.1f},{tgt[1]:.1f})"
        )
        cv2.putText(
            out,
            f"TARGET {tgt_txt} | {r['control_action']} | {r.get('mode','')}",
            (10, y0 + 151),
            cv2.FONT_HERSHEY_SIMPLEX, .46,
            (210,210,210), 1, cv2.LINE_AA
        )

        cv2.putText(
            out,
            "T/B/L/R = POI | amarillo = centerline | X = target | flecha = control",
            (10, y0 + 181),
            cv2.FONT_HERSHEY_SIMPLEX, .42,
            (190,190,190), 1, cv2.LINE_AA
        )

        cv2.putText(
            out,
            "SHADOW: valida percepcion/control pedido; NO simula trayectoria fisica futura",
            (10, y0 + 211),
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
    ap.add_argument("--avi", default="nuevo_code_v3.avi")
    ap.add_argument("--csv", default="nuevo_code_v3.csv")
    a = ap.parse_args()

    run(
        a.video, a.avi, a.csv,
        a.fps, a.desde, a.hasta
    )

if __name__ == "__main__":
    main()
