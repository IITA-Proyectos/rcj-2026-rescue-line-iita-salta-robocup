# -*- coding: utf-8 -*-
"""
airborne_birdeye_replay.py

Banco SHADOW para comparar:
  1) angle actual (atan2 global del 22-ago)
  2) seguimiento inspirado en Airborne: contorno + continuidad + POI
  3) el mismo seguimiento luego de una homografia bird-eye PROVISIONAL

NO ES SIMULACION FISICA.
Los frames futuros son los de la trayectoria que realmente ocurrio.

Uso:
  python airborne_birdeye_replay.py hist.avi --desde 1354 --hasta 1490 --fps 33.3
  python airborne_birdeye_replay.py video_4.avi --desde 500 --hasta 570 --fps 20
"""

import argparse
import csv
import math
from collections import deque
import cv2
import numpy as np

LO = np.array([0, 0, 0], np.uint8)
HI = np.array([90, 90, 90], np.uint8)
W, H = 160, 120
CENTER = 79.5


def runs(xs):
    xs = list(map(int, xs))
    if not xs:
        return []
    out = []
    s = p = xs[0]
    for x in xs[1:]:
        if x == p + 1:
            p = x
        else:
            out.append((s, p))
            s = p = x
    out.append((s, p))
    return out


class RollingMean:
    def __init__(self, n):
        self.q = deque(maxlen=max(1, int(n)))

    def add(self, x):
        if x is not None and np.isfinite(x):
            self.q.append(float(x))
        return float(np.mean(self.q)) if self.q else None

    def last(self):
        return self.q[-1] if self.q else None


def frame_pi(frame):
    """
    Panel GRABAR 640x240:
      lado izquierdo = 160x120 escalado x2; usar submuestreo impar.
    Video crudo:
      rotate 180 -> resize 160x120 INTER_NEAREST.
    """
    if frame.shape[0] == 240 and frame.shape[1] >= 640:
        return frame[:, :320][1::2, 1::2]

    g = cv2.rotate(frame, cv2.ROTATE_180)
    return cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)


def mascara_actual(g):
    m = cv2.inRange(g, LO, HI)
    m[:60, :] = 0
    return m


def angle_actual(g):
    """Reimplementacion compacta del atan2 global."""
    m = mascara_actual(g)
    if m.sum() < 1:
        return 0.0

    ys, xs = np.nonzero(m)
    xc = (xs - (W / 2 - 1)) / (W / 2)
    yc = ((H - 1) - ys) / H

    xb = np.mean(xc * (1 - yc))
    yb = np.mean(yc)

    return (math.atan2(yb, xb) / math.pi * 180.0) - 90.0


class AirbornePOI:
    """
    Adaptacion para NUESTROS videos de las ideas de Airborne:
      - selecciona UN contorno de linea
      - si hay varios candidatos bajos usa continuidad x/y
      - obtiene POI de arriba/abajo/laterales
      - el target X se suaviza ~0.15 s

    No copia sus ganancias, morfologia ni reglas de interseccion:
    esas dependen de su camara/chasis.
    """

    def __init__(self, fps=33.3, bird=False):
        self.fps = fps
        self.bird = bird

        self.x_last = CENTER
        self.y_last = 75.0
        self.avg_target = RollingMean(round(0.15 * fps))

        # Homografia PROVISIONAL en 160x120.
        # Usa mas piso lejano que el ROI viejo (empieza aprox en y=45).
        src = np.float32([
            [45, 45],
            [114, 45],
            [159, 119],
            [0, 119],
        ])
        dst = np.float32([
            [0, 0],
            [159, 0],
            [159, 119],
            [0, 119],
        ])
        self.M = cv2.getPerspectiveTransform(src, dst)

    def preparar(self, g):
        m = cv2.inRange(g, LO, HI)

        if not self.bird:
            m[:60, :] = 0
            return m

        return cv2.warpPerspective(
            m, self.M, (W, H), flags=cv2.INTER_NEAREST
        )

    def paso(self, g):
        m = self.preparar(g)

        contours, _ = cv2.findContours(
            m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = [
            c for c in contours
            if len(c) >= 2 and cv2.contourArea(c) >= 20
        ]

        if not contours:
            return {
                "ok": False,
                "mask": m,
                "contour": None,
                "target": None,
                "bottom": None,
                "angle": float("nan"),
                "reason": "PERDIDA",
            }

        candidatos = []
        off_bottom = 0

        for i, c in enumerate(contours):
            box = cv2.boxPoints(cv2.minAreaRect(c))
            bottom_y = float(np.max(box[:, 1]))
            x_mean = float(np.mean(np.clip(box[:, 0], 0, 159)))
            y_mean = float(np.mean(np.clip(box[:, 1], 0, 119)))

            if bottom_y >= H * 0.75:
                off_bottom += 1

            dist = abs(self.x_last - x_mean) + abs(self.y_last - y_mean)

            candidatos.append(
                (i, bottom_y, dist, x_mean, y_mean, cv2.contourArea(c))
            )

        # Idea Airborne:
        # si hay varias alternativas cerca del robot, manda continuidad.
        if off_bottom >= 2:
            usables = [c for c in candidatos if c[1] >= H * 0.75]
            usables.sort(key=lambda z: z[2])
        else:
            usables = sorted(
                candidatos, key=lambda z: z[1], reverse=True
            )

        elegido = usables[0]
        contour = contours[elegido[0]]
        self.x_last = elegido[3]
        self.y_last = elegido[4]

        pts = contour[:, 0, :]

        # Airborne default_crop es aprox 0.45.
        # Aqui 0.50 conserva similitud con el ROI del robot del 22-ago.
        cropped = pts[pts[:, 1] > H * 0.50]
        use = cropped if len(cropped) >= 2 else pts

        # Bottom real del contorno
        ymax = int(np.max(pts[:, 1]))
        bx = pts[pts[:, 1] == ymax][:, 0]
        bottom = (float(np.mean(bx)), float(ymax))

        # Top del recorte.
        ymin = int(np.min(use[:, 1]))
        top_xs = np.sort(np.unique(use[use[:, 1] == ymin][:, 0]))
        top_runs = runs(top_xs)

        ref = self.avg_target.last()
        if ref is None:
            ref = self.x_last

        if top_runs:
            rr = min(
                top_runs,
                key=lambda r: abs((r[0] + r[1]) / 2 - ref)
            )
            top = ((rr[0] + rr[1]) / 2.0, float(ymin))
        else:
            top = (float(np.mean(top_xs)), float(ymin))

        xmin = int(np.min(use[:, 0]))
        xmax = int(np.max(use[:, 0]))

        ly = use[use[:, 0] == xmin][:, 1]
        ry = use[use[:, 0] == xmax][:, 1]

        left = (float(xmin), float(np.mean(ly)))
        right = (float(xmax), float(np.mean(ry)))

        # POI provisional.
        # IMPORTANTE: las T/verdes deben seguir usando las reglas reglamentarias
        # ya existentes; esto solo prueba seguimiento normal.
        if xmin <= 1 and xmax >= 158:
            opciones = [left, right, top]
            target_raw = min(
                opciones,
                key=lambda p: abs(p[0] - ref)
            )
            reason = "AMBOS_BORDES_CONTINUIDAD"

        elif xmin <= 1 and left[1] > H * 0.50:
            target_raw = left
            reason = "BORDE_IZQ"

        elif xmax >= 158 and right[1] > H * 0.50:
            target_raw = right
            reason = "BORDE_DER"

        else:
            target_raw = top
            reason = "TOP_POI"

        tx = self.avg_target.add(target_raw[0])
        target = (tx, target_raw[1])

        # SOLO SHADOW:
        # Airborne real usa PID sobre lineCenterX.
        # Aqui se convierte X a +/-90 para comparar signos visualmente.
        err = tx - CENTER
        angle = float(np.clip(-90.0 * err / (W / 2), -90, 90))

        return {
            "ok": True,
            "mask": m,
            "contour": contour,
            "target": target,
            "bottom": bottom,
            "angle": angle,
            "reason": reason,
        }


def dibujar(resultado, titulo):
    vis = np.zeros((H, W, 3), np.uint8)
    vis[resultado["mask"] > 0] = (60, 60, 60)

    if resultado["contour"] is not None:
        cv2.drawContours(
            vis, [resultado["contour"]], -1, (90, 210, 100), 1
        )

    if resultado["bottom"] is not None:
        b = tuple(int(round(x)) for x in resultado["bottom"])
        cv2.circle(vis, b, 3, (255, 190, 70), -1)

    if resultado["target"] is not None:
        t = tuple(int(round(x)) for x in resultado["target"])
        cv2.drawMarker(
            vis, t, (80, 180, 255),
            cv2.MARKER_TILTED_CROSS, 9, 1
        )

        if resultado["bottom"] is not None:
            b = tuple(int(round(x)) for x in resultado["bottom"])
            cv2.line(vis, b, t, (80, 180, 255), 1)

    cv2.putText(
        vis, titulo, (3, 12),
        cv2.FONT_HERSHEY_SIMPLEX, 0.38,
        (235, 235, 235), 1, cv2.LINE_AA
    )
    return vis


def correr(ruta, salida_avi, salida_csv,
           desde=0, hasta=10**9, fps=33.3):

    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir " + ruta)

    air = AirbornePOI(fps=fps, bird=False)
    bird = AirbornePOI(fps=fps, bird=True)

    E = 3
    CW, CH = W * E, H * E
    OW, OH = CW * 3, CH + 130

    vw = cv2.VideoWriter(
        salida_avi,
        cv2.VideoWriter_fourcc(*"MJPG"),
        fps,
        (OW, OH),
    )

    fcsv = open(salida_csv, "w", newline="")
    writer = csv.writer(fcsv)
    writer.writerow([
        "source_frame",
        "current_angle",
        "airborne_angle",
        "airborne_reason",
        "bird_angle",
        "bird_reason",
        "airborne_seen",
        "bird_seen",
    ])

    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if idx < desde:
            idx += 1
            continue
        if idx > hasta:
            break

        g = frame_pi(frame)
        cur = angle_actual(g)
        ra = air.paso(g)
        rb = bird.paso(g)

        p0 = cv2.resize(
            g, (CW, CH), interpolation=cv2.INTER_NEAREST
        )
        p1 = cv2.resize(
            dibujar(ra, "AIRBORNE-POI"),
            (CW, CH),
            interpolation=cv2.INTER_NEAREST,
        )
        p2 = cv2.resize(
            dibujar(rb, "BIRD-EYE + AIRBORNE"),
            (CW, CH),
            interpolation=cv2.INTER_NEAREST,
        )

        canvas = np.zeros((OH, OW, 3), np.uint8)
        canvas[:CH, :CW] = p0
        canvas[:CH, CW:CW*2] = p1
        canvas[:CH, CW*2:] = p2

        # trapecio de la homografia provisional
        poly = np.array([
            [45*E, 45*E],
            [114*E, 45*E],
            [159*E, 119*E],
            [0, 119*E],
        ], np.int32)

        cv2.polylines(
            canvas[:CH, :CW], [poly], True,
            (0, 220, 255), 1
        )

        y = CH + 24
        cv2.putText(
            canvas,
            f"frame {idx} | CURRENT atan2 {cur:+6.1f} deg",
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55, (220, 220, 220), 1, cv2.LINE_AA
        )
        cv2.putText(
            canvas,
            f"AIRBORNE POI {ra.get('angle', np.nan):+6.1f} | {ra['reason']}",
            (10, y+30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55, (100, 220, 120), 1, cv2.LINE_AA
        )
        cv2.putText(
            canvas,
            f"BIRD-EYE {rb.get('angle', np.nan):+6.1f} | {rb['reason']} | HOMOGRAFIA PROVISIONAL",
            (10, y+60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55, (80, 180, 255), 1, cv2.LINE_AA
        )
        cv2.putText(
            canvas,
            "SHADOW: percepcion solamente; NO predice la trayectoria fisica futura",
            (10, y+92),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48, (80, 210, 240), 1, cv2.LINE_AA
        )

        vw.write(canvas)

        writer.writerow([
            idx,
            f"{cur:.3f}",
            "" if not ra["ok"] else f"{ra['angle']:.3f}",
            ra["reason"],
            "" if not rb["ok"] else f"{rb['angle']:.3f}",
            rb["reason"],
            int(ra["ok"]),
            int(rb["ok"]),
        ])

        idx += 1

    cap.release()
    vw.release()
    fcsv.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10**9)
    ap.add_argument("--fps", type=float, default=33.3)
    ap.add_argument("--avi", default="airborne_birdeye_out.avi")
    ap.add_argument("--csv", default="airborne_birdeye_out.csv")
    a = ap.parse_args()

    correr(
        a.video, a.avi, a.csv,
        desde=a.desde,
        hasta=a.hasta,
        fps=a.fps,
    )


if __name__ == "__main__":
    main()
