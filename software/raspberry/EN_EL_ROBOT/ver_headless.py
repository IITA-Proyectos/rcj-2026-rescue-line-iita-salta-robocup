#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISOR HEADLESS — lo que ve el robot, servido por HTTP.  2026-08-28

Para mirar desde la notebook sin depender de X, de Qt ni de wayland: abre la
camara, corre EXACTAMENTE la misma vision que main.py, dibuja todo encima y lo
sirve como MJPEG.  Se abre con el navegador.

    python3 ver_headless.py
    -> y en la notebook:   http://<ip-de-la-pi>:8080

NO MANEJA EL ROBOT.  No abre el puerto serie, no manda nada a la Teensy.  Es
solo para mirar.  Como la camara no se puede abrir dos veces, hay que correrlo
CON main.py APAGADO.

QUE DIBUJA
  rojo          la mascara del robot (inRange BGR <= 90), o sea lo que llama LINEA
  linea amarilla  la fila 60: el recorte de arriba que ya existe
  linea celeste   la fila CORTE_ABAJO: lo que sacaria el parche del recorte
  flecha blanca   el angulo que manda hoy
  flecha verde    el angulo con el recorte de abajo
  trazo verde     el camino del planner, si PLANNER=1
  circulo         el target del planner
  barras laterales  se prenden cuando la linea toca ese borde del ROI
                    (es el discriminador GAP vs CURVA del parche de perdida)

VARIABLES
  PUERTO=8080        puerto HTTP
  CORTE_ABAJO=105    donde dibuja la linea celeste y calcula la flecha verde
  PLANNER=1          enciende el trazo del planner
  ESCALA=4           tamano del panel
"""
import io
import math
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

PUERTO = int(os.environ.get("PUERTO", "8080"))
CORTE_ABAJO = int(os.environ.get("CORTE_ABAJO", "105"))
USAR_PLANNER = os.environ.get("PLANNER", "0") in ("1", "2")
S = int(os.environ.get("ESCALA", "4"))
BORDE = int(os.environ.get("PERDIDA_BORDE", "4"))

W, H = 160, 120
CAM_X, CAM_Y = W / 2 - 1, H - 1
LO = np.array([0, 0, 0], np.uint8)
HI = np.array([90, 90, 90], np.uint8)

# los mismos x_com / y_com que main.py
x_com = np.zeros((H, W))
y_com = np.zeros((H, W))
for _i in range(H):
    for _j in range(W):
        x_com[_i][_j] = (_j - CAM_X) / (W / 2.0)
        y_com[_i][_j] = (CAM_Y - _i) / float(H)

from camthreader import WebcamVideoStream          # noqa: E402

_seguidor = None
if USAR_PLANNER:
    try:
        from seguidor_linea import Seguidor
        _seguidor = Seguidor()
        print("[VISOR] planner encendido")
    except Exception as e:
        print("[VISOR] no pude cargar el planner (%s): sigo sin el" % e)

_ultimo_jpg = [None]
_lock = threading.Lock()
FN = cv2.FONT_HERSHEY_SIMPLEX


def _ang(mask):
    if not mask.any():
        return float("nan")
    xb = cv2.bitwise_and(x_com, x_com, mask=mask)
    xb *= (1 - y_com)
    yb = cv2.bitwise_and(y_com, y_com, mask=mask)
    return (math.atan2(np.mean(yb), np.mean(xb)) / math.pi * 180) - 90


def _txt(img, x, y, s, col, sc=0.5, th=1):
    cv2.putText(img, s, (x, y), FN, sc, (0, 0, 0), th + 3, cv2.LINE_AA)
    cv2.putText(img, s, (x, y), FN, sc, col, th, cv2.LINE_AA)


def _flecha(img, ang, col, largo, gr=3):
    if ang is None or (isinstance(ang, float) and math.isnan(ang)):
        return
    r = math.radians(90 - ang)
    o = (int(CAM_X) * S, int(CAM_Y) * S)
    cv2.arrowedLine(img, o, (int(o[0] + largo * math.cos(r)),
                             int(o[1] - largo * math.sin(r))), col, gr, tipLength=0.15)


def lazo():
    vs = WebcamVideoStream(src=0).start()
    time.sleep(1.0)
    n, t0, fps = 0, time.time(), 0.0
    while True:
        f = vs.read()
        if f is None:
            time.sleep(0.02)
            continue
        f = cv2.rotate(f, cv2.ROTATE_180)
        fr = cv2.resize(f, (W, H), interpolation=cv2.INTER_NEAREST)

        m = cv2.inRange(fr, LO, HI)
        m[:60, :] = 0
        a_hoy = _ang(m)

        mc = m.copy()
        mc[CORTE_ABAJO:, :] = 0
        a_corte = _ang(mc) if mc.any() else a_hoy

        # discriminador GAP vs CURVA: bordes de la componente mas grande
        iz = de = False
        if m.any():
            nn, lb, st, _ = cv2.connectedComponentsWithStats(m, 8)
            if nn > 1:
                big = 1 + int(np.argmax(st[1:, 4]))
                g = (lb == big)
                iz = bool(g[:, :BORDE].any())
                de = bool(g[:, -BORDE:].any())

        r = None
        if _seguidor is not None:
            try:
                # ya_procesado=True: `fr` YA viene rotado 180 y en 160x120,
                # igual que en main.py. Con False lo rotaria dos veces.
                r = _seguidor.paso(fr, ya_procesado=True)
            except Exception:
                r = None

        vis = cv2.resize(fr, (W * S, H * S), interpolation=cv2.INTER_NEAREST)
        ov = vis.copy()
        ov[cv2.resize(m, (W * S, H * S), interpolation=cv2.INTER_NEAREST) > 0] = (40, 40, 255)
        vis = cv2.addWeighted(vis, 0.5, ov, 0.5, 0)

        cv2.line(vis, (0, 60 * S), (W * S, 60 * S), (0, 230, 230), 2)
        cv2.line(vis, (0, CORTE_ABAJO * S), (W * S, CORTE_ABAJO * S), (255, 190, 80), 2)
        _txt(vis, 6, 60 * S - 8, "fila 60", (0, 230, 230), 0.45)
        _txt(vis, 6, CORTE_ABAJO * S - 8, "fila %d" % CORTE_ABAJO, (255, 190, 80), 0.45)

        if iz:
            cv2.rectangle(vis, (0, 60 * S), (10, H * S), (0, 220, 255), -1)
        if de:
            cv2.rectangle(vis, (W * S - 10, 60 * S), (W * S, H * S), (0, 220, 255), -1)

        if r is not None and r.get("puntos"):
            p = [(int(x * S), int(y * S)) for x, y in r["puntos"]]
            for u, v in zip(p, p[1:]):
                cv2.line(vis, u, v, (0, 255, 120), 2)
            cv2.circle(vis, p[-1], 8, (0, 255, 120), 2)

        _flecha(vis, a_hoy, (255, 255, 255), 230, 4)
        _flecha(vis, a_corte, (120, 255, 120), 300, 3)

        n += 1
        if time.time() - t0 >= 1.0:
            fps = n / (time.time() - t0)
            n, t0 = 0, time.time()

        barra = np.full((104, W * S, 3), 18, np.uint8)
        _txt(barra, 10, 26, "HOY      %+6.0f" % a_hoy if not math.isnan(a_hoy) else "HOY      SIN LINEA",
             (255, 255, 255), 0.62, 2)
        _txt(barra, 10, 52, "corte%-3d %+6.0f" % (CORTE_ABAJO, a_corte) if not math.isnan(a_corte)
             else "corte     SIN LINEA", (140, 255, 140), 0.62, 2)
        lado = "IZQ" if (iz and not de) else ("DER" if (de and not iz) else ("LOS DOS" if iz and de else "-"))
        _txt(barra, 10, 78, "borde %-8s   px %-5d   %4.1f fps"
             % (lado, int(m.sum() // 255), fps), (190, 190, 190), 0.55)
        if r is not None:
            _txt(barra, 330, 26, "planner %s  %s"
                 % ("ok" if r.get("ok") else "no", r.get("motivo", "")), (0, 255, 120), 0.55)
            _txt(barra, 330, 52, "ang %+.0f" % r.get("angle_filtrado", 0.0), (0, 255, 120), 0.55)

        ok, jpg = cv2.imencode(".jpg", np.vstack([vis, barra]),
                               [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            with _lock:
                _ultimo_jpg[0] = jpg.tobytes()


PAGINA = b"""<!doctype html><meta charset=utf-8>
<title>lo que ve el robot</title>
<style>body{background:#111;color:#ddd;font-family:system-ui,sans-serif;margin:0;
padding:14px;text-align:center}img{max-width:100%;image-rendering:pixelated;
border:1px solid #333}p{font-size:13px;color:#888}</style>
<h3 style="font-weight:600">lo que ve el robot</h3>
<img src="/stream">
<p>rojo = lo que llama LINEA &middot; amarillo = fila 60 &middot; celeste = corte de abajo
&middot; blanco = angulo de hoy &middot; verde = con el recorte &middot; trazo verde = planner
&middot; barra lateral = la linea toca ese borde</p>
"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGINA)))
            self.end_headers()
            self.wfile.write(PAGINA)
            return
        if self.path != "/stream":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                with _lock:
                    j = _ultimo_jpg[0]
                if j is None:
                    time.sleep(0.05)
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                 b"Content-Length: " + str(len(j)).encode() + b"\r\n\r\n")
                self.wfile.write(j)
                self.wfile.write(b"\r\n")
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass


def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "la-ip-de-la-pi"


if __name__ == "__main__":
    threading.Thread(target=lazo, daemon=True).start()
    print()
    print("  VISOR LISTO   ->   http://%s:%d" % (ip_local(), PUERTO))
    print()
    print("  Ctrl+C para salir.  NO maneja el robot: solo mira.")
    print("  Correlo con main.py APAGADO (la camara no se abre dos veces).")
    print()
    try:
        ThreadingHTTPServer(("0.0.0.0", PUERTO), H).serve_forever()
    except KeyboardInterrupt:
        print("\nchau")
