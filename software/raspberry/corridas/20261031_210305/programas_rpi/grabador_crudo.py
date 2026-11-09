# -*- coding: utf-8 -*-
"""
grabador_crudo.py - lo usa main.py con GRABAR_CRUDO=carpeta. Guarda, de cada cuadro, la imagen que proceso la Pi
SIN COMPRIMIR y sin cartel (160x120, PNG) y lo que decidio, para poder analizar despues con todos los datos.

Por corrida crea <carpeta>/<MMDD_HHMMSS>/ con:
    f_000001.png ...     el cuadro tal cual lo uso main.py (frame_resized)
    cuadros.csv          una linea por cuadro: hora, estado, velocidad, angulo y verde mandados, quien, pixeles
                         verdes y negros, aviso de rampa
    parametros.txt       rangos de verde y negro, min_square_size, variables de entorno, sha de main.py
    camara_inicio.txt    lo que dice v4l2-ctl de la camara al arrancar (y camara_fin.txt al cerrar)

Escribe en un hilo aparte: si el disco se atrasa, se pierden cuadros (quedan contados en cuadros.csv como
"perdidos") pero el lazo del robot nunca espera. Se corta solo a los MAX_CUADROS.
"""
import atexit
import hashlib
import os
import queue
import re
import subprocess
import threading
import time

import cv2

MAX_CUADROS = 40000          # ~25 min a 26 cuadros por segundo; ~0,8 GB


def _v4l2():
    try:
        r = subprocess.run(["v4l2-ctl", "-d", "/dev/video0", "--list-ctrls"], capture_output=True, text=True, timeout=5)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "v4l2-ctl no disponible: %s" % e


class GrabadorCrudo(object):
    def __init__(self, base, parametros, ruta_main=None):
        self.dir = os.path.join(base, time.strftime("%m%d_%H%M%S"))
        os.makedirs(self.dir, exist_ok=True)
        self.n = 0
        self.perdidos = 0
        self.t0 = time.monotonic()
        self.q = queue.Queue(maxsize=300)
        lineas = ["%s = %s" % (k, v) for k, v in parametros.items()]
        nombres = []
        if ruta_main:
            try:
                src = open(ruta_main, "rb").read()
                lineas.append("sha256 main.py = %s" % hashlib.sha256(src).hexdigest())
                # las variables que lee main.py, con el valor que tuvieron en esta corrida
                nombres = sorted(set(re.findall(r"os\.environ\.get\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']", src.decode("utf-8", "replace"))))
            except OSError:
                pass
        lineas.append("variables de main.py (vacio = no puesta, usa su valor por defecto):")
        lineas += ["  %s=%s" % (k, os.environ.get(k, "")) for k in nombres]
        open(os.path.join(self.dir, "parametros.txt"), "w").write("\n".join(lineas) + "\n")
        open(os.path.join(self.dir, "camara_inicio.txt"), "w").write(_v4l2() + "\n")
        self.csv = open(os.path.join(self.dir, "cuadros.csv"), "w")
        self.csv.write("n,t,estado,speed,angle,green_state,silver,quien,verde_px,negro_px,rampa,perdidos\n")
        self.hilo = threading.Thread(target=self._escribir, daemon=True)
        self.hilo.start()
        atexit.register(self.cerrar)
        print("[GRABAR_CRUDO] guardando cada cuadro en %s" % self.dir)

    def cuadro(self, frame, estado, speed, angle, green_state, silver, quien, verde_px, negro_px, rampa):
        if self.n >= MAX_CUADROS:
            return
        self.n += 1
        fila = "%d,%.3f,%s,%s,%.1f,%s,%d,%s,%d,%d,%s,%d\n" % (
            self.n, time.monotonic() - self.t0, estado, speed, angle, green_state, int(bool(silver)),
            str(quien).replace(",", ";"), verde_px, negro_px, rampa, self.perdidos)
        try:
            self.q.put_nowait((self.n, frame.copy(), fila))
        except queue.Full:
            self.perdidos += 1

    def _escribir(self):
        while True:
            item = self.q.get()
            if item is None:
                break
            n, frame, fila = item
            cv2.imwrite(os.path.join(self.dir, "f_%06d.png" % n), frame)
            self.csv.write(fila)
            if n % 50 == 0:
                self.csv.flush()

    def cerrar(self):
        if getattr(self, "_cerrado", False):
            return
        self._cerrado = True
        self.q.put(None)
        self.hilo.join(timeout=5)
        self.csv.flush()
        self.csv.close()
        open(os.path.join(self.dir, "camara_fin.txt"), "w").write(_v4l2() + "\n")
        print("[GRABAR_CRUDO] cerrado: %d cuadros (%d perdidos) en %s" % (self.n, self.perdidos, self.dir))
