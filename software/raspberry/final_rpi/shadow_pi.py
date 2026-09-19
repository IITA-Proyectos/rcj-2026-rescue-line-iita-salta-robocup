# -*- coding: utf-8 -*-
"""
SHADOW PI - la candidata corriendo sobre camara VIVA, en el robot, sin mandar
            nada a la Teensy.

Desbloquea la FASE 4 de PROTOCOLO_SABADO.md. Contesta una sola pregunta, que
el replay NO puede contestar:

    la candidata, sobre la camara de HOY -esta luz, esta exposicion, este
    foco, esta sede-, se comporta como en los videos de agosto?

Si la disponibilidad de target se cae aca, el problema es calibracion de
color/luz y NO arquitectura, y se ataca con calibrador_verde.py / medir_camara.py
en vez de tocar el skeleton.

============================================================================
 GARANTIAS
============================================================================
* NO abre el puerto serie. NO importa pyserial. No puede mandar un comando ni
  por error: no hay codigo para hacerlo.
* NO modifica la candidata ni Main.py ni camthreader.py.
* No hace I/O por frame: acumula en memoria y vuelca cada tanto.
* Ctrl-C cierra limpio y escribe todo.

============================================================================
 OPEN-LOOP IGUAL
============================================================================
Aunque los frames sean de hoy, el robot lo empujas VOS. La candidata no maneja.
Esto sigue sin ser prueba de lazo cerrado; es prueba de PERCEPCION EN VIVO.

USO
---
En la Pi, con el robot apoyado en la linea y empujandolo a mano:

    sudo systemctl stop iita-robot
    python3 shadow_pi.py --seg 90 --grabar shadow_pi_$(date +%H%M).avi

Para validarlo sin camara -o para comparar contra el replay-:

    python3 shadow_pi.py --fuente hist.avi

Las etapas intermedias se obtienen con el MISMO codigo verificado de
registro_visual.py (16.112 frames, 0 discrepancias), y aca se vuelve a
autoverificar en vivo: la columna `rederiv_ok` tiene que ser 1 siempre.
"""

import argparse
import csv
import os
import sys
import threading
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from registro_visual import (cargar, hacer_sinbranch, espiar_path_target,
                             rederivar, ULTIMO_RAW, steer_de, igual)

NS = time.perf_counter_ns
FPS_NOMINAL = 100.0 / 3.0

CAMPOS = [
    "i", "t_mono_ns", "seq", "repetido", "frame_age_ms", "proc_ms",
    "state", "mode", "reason",
    "raw_x", "raw_y", "cap_x", "cap_y", "low_x", "low_y", "fin_x", "fin_y",
    "spatial", "proposed_jump_px", "steer", "rederiv_ok",
]


# --------------------------------------------------------------------------
class CamaraViva(object):
    """Mismo patron que camthreader.WebcamVideoStream, con seq y timestamp
    monotonico de captura. camthreader.py NO se toca."""

    def __init__(self, src, ancho, alto):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
        self.cv = threading.Condition()
        self.frame = None
        self.seq = 0
        self.t_cap = 0
        self.stopped = False
        self.fallos = 0
        self.hilo = None
        ok, fr = self.stream.read()
        if ok:
            self.frame, self.seq, self.t_cap = fr, 1, NS()

    def abierta(self):
        return self.stream.isOpened()

    def info(self):
        return (self.stream.get(cv2.CAP_PROP_FRAME_WIDTH),
                self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT),
                self.stream.get(cv2.CAP_PROP_FPS))

    def start(self):
        self.hilo = threading.Thread(target=self._loop, daemon=True)
        self.hilo.start()
        return self

    def _loop(self):
        while not self.stopped:
            ok, fr = self.stream.read()
            t = NS()
            if not ok:
                self.fallos += 1
                continue
            with self.cv:
                self.frame = fr
                self.seq += 1
                self.t_cap = t
                self.cv.notify_all()

    def leer_nuevo(self, ultimo, timeout=2.0):
        with self.cv:
            ok = self.cv.wait_for(
                lambda: self.seq != ultimo or self.stopped, timeout)
            if not ok or self.frame is None:
                return None, ultimo, 0
            return self.frame.copy(), self.seq, self.t_cap

    def stop(self):
        self.stopped = True
        with self.cv:
            self.cv.notify_all()
        if self.hilo is not None:
            self.hilo.join(timeout=2.0)
        self.stream.release()


class FuenteVideo(object):
    """Un .avi haciendose pasar por camara, para validar sin hardware."""

    def __init__(self, ruta):
        self.cap = cv2.VideoCapture(ruta)
        self.seq = 0

    def abierta(self):
        return self.cap.isOpened()

    def info(self):
        return (self.cap.get(3), self.cap.get(4), self.cap.get(5))

    def start(self):
        return self

    def leer_nuevo(self, ultimo, timeout=None):
        ok, fr = self.cap.read()
        if not ok:
            return None, self.seq, 0
        self.seq += 1
        return fr, self.seq, NS()

    def stop(self):
        self.cap.release()

    fallos = 0


# --------------------------------------------------------------------------
def resumen(serie, edades, procs, repetidos, spat, rederiv_mal, n_seq_saltados):
    print("")
    print("=" * 74)
    print("  SHADOW PI - resumen")
    print("=" * 74)
    n = len(serie)
    con = sum(1 for t, s, e in serie if t is not None)
    print("")
    print("  frames procesados        %d" % n)
    if not n:
        return None
    print("  disponibilidad de target %.2f %%  (%d con target, %d sin)"
          % (100.0 * con / n, con, n - con))

    try:
        import ab_v2_v3_v4 as AB
        m = AB.metricas(serie)
        print("")
        print("  METRICAS COMPARABLES CON EL BANCO DE REPLAY")
        print("    huecos (perdida->reacq)  %d" % m["huecos"])
        print("    saltos > 24 px           %d   (medidos a traves de huecos)"
              % m["s_gt"])
        print("    inversiones de steer     %d   (banda muerta 10 grados)"
              % m["inv"])
        print("    salto maximo             %.1f px" % m["s_max"])
        print("    suavidad (mediana |ds|)  %.2f grados" % m["suav"])
    except Exception as e:
        m = None
        print("  (no se pudieron calcular las metricas del banco: %s)" % e)

    print("")
    print("  CAPTURA")
    if edades:
        a = np.asarray(edades, float) / 1e6
        print("    edad de frame  media %.2f  p50 %.2f  p95 %.2f  max %.2f ms"
              % (a.mean(), np.percentile(a, 50), np.percentile(a, 95), a.max()))
    if procs:
        p = np.asarray(procs, float) / 1e6
        print("    proc por frame media %.2f  p50 %.2f  p95 %.2f  max %.2f ms"
              % (p.mean(), np.percentile(p, 50), np.percentile(p, 95), p.max()))
    print("    frames repetidos         %d" % repetidos)
    print("    seq saltados             %d" % n_seq_saltados)

    print("")
    print("  SPATIAL GUARD")
    for k in sorted(spat, key=lambda z: -spat[z]):
        print("    %-18s %6d   %5.1f %%" % (k, spat[k], 100.0 * spat[k] / n))

    print("")
    print("  AUTOCHEQUEO DE ETAPAS")
    print("    discrepancias de re-derivacion  %d" % rederiv_mal)
    if rederiv_mal:
        print("    *** las columnas cap/low no son fiables en esos frames")

    print("")
    print("  RECORDATORIO: esto es percepcion en vivo, NO lazo cerrado.")
    print("  El robot lo empujaste vos. La candidata no manejo nada.")
    print("=" * 74)
    return m


def main():
    ap = argparse.ArgumentParser(
        description="Candidata sobre camara viva, log-only. No toca el serie.")
    ap.add_argument("--fuente", default=None,
                    help="ruta a un .avi en vez de la camara (validacion)")
    ap.add_argument("--camara", type=int, default=0)
    ap.add_argument("--ancho", type=int, default=160)
    ap.add_argument("--alto", type=int, default=120)
    ap.add_argument("--seg", type=float, default=60.0,
                    help="duracion en segundos (solo con camara)")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--grabar", default=None,
                    help="ademas guardar los frames crudos en un .avi")
    ap.add_argument("--volcar-cada", type=int, default=300,
                    dest="volcar_cada")
    a = ap.parse_args()

    v4, v3, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    restaurar = espiar_path_target(v2)

    if a.fuente:
        fuente = FuenteVideo(os.path.join(AQUI, a.fuente)
                             if not os.path.isabs(a.fuente) else a.fuente)
        etiqueta = "VIDEO %s" % a.fuente
    else:
        fuente = CamaraViva(a.camara, a.ancho, a.alto)
        etiqueta = "CAMARA %d" % a.camara
    if not fuente.abierta():
        print("*** no abre la fuente. Si el servicio tiene la camara:")
        print("    sudo systemctl stop iita-robot")
        restaurar()
        return 2
    fuente.start()

    destino = a.csv or os.path.join(
        AQUI, "shadow_pi_%s.csv" % time.strftime("%Y%m%d_%H%M%S"))
    grabador = None

    print("")
    print("  SHADOW PI  -  %s" % etiqueta)
    print("  fuente real  %s" % (fuente.info(),))
    print("  csv          %s" % destino)
    print("  NO se abre el puerto serie. La candidata NO maneja.")
    if not a.fuente:
        print("  duracion     %.0f s   (Ctrl-C corta antes y guarda igual)"
              % a.seg)
    print("")

    tr = SinBranch(FPS_NOMINAL)
    filas = []
    serie = []
    edades, procs = [], []
    spat = {}
    repetidos = 0
    saltados = 0
    rederiv_mal = 0
    ult_seq = -1
    i = 0
    t_ini = time.time()
    t_prox_print = t_ini + 2.0

    f = open(destino, "w", newline="", encoding="utf-8")
    wr = csv.writer(f)
    wr.writerow(CAMPOS)

    try:
        while True:
            if not a.fuente and (time.time() - t_ini) >= a.seg:
                break
            fr, seq, t_cap = fuente.leer_nuevo(ult_seq)
            if fr is None:
                if a.fuente:
                    break
                continue
            t0 = NS()
            edad = t0 - t_cap
            g = v2.frame_pi(fr)
            prev_t = tr.per.prev_target
            last_g = tr.per.last_good_target
            ULTIMO_RAW["res"] = None
            r = tr.step(g)
            proc = NS() - t0

            if grabador is None and a.grabar:
                h, w = fr.shape[:2]
                grabador = cv2.VideoWriter(
                    os.path.join(AQUI, a.grabar),
                    cv2.VideoWriter_fourcc(*"MJPG"), FPS_NOMINAL, (w, h))
            if grabador is not None:
                grabador.write(fr)

            res = ULTIMO_RAW["res"]
            raw = None if res is None else res["target"]
            t_cap_e = t_low = None
            ok_red = 1
            if raw is not None and r.get("skel") is not None:
                t_cap_e, t_low, _c, _l = rederivar(
                    raw, prev_t, r.get("state"), r["skel"], last_g)
                if not igual(t_low, r.get("target_geometric")):
                    ok_red = 0
                    rederiv_mal += 1

            fin = r.get("target")
            st = steer_de(fin, v2.W, v2.CENTER)
            sg = r.get("spatial_guard", "-")
            spat[sg] = spat.get(sg, 0) + 1

            rep = 1 if seq == ult_seq else 0
            repetidos += rep
            if not rep and ult_seq >= 0 and seq > ult_seq + 1:
                saltados += seq - ult_seq - 1
            ult_seq = seq

            def xy(p):
                return ("", "") if p is None else ("%.2f" % p[0], "%.2f" % p[1])

            filas.append([i, t0, seq, rep, "%.3f" % (edad / 1e6),
                          "%.3f" % (proc / 1e6), r.get("state", ""),
                          r.get("mode", ""), r.get("reason", "")]
                         + list(xy(raw)) + list(xy(t_cap_e))
                         + list(xy(t_low)) + list(xy(fin))
                         + [sg,
                            "" if r.get("proposed_jump_px") is None
                            else "%.2f" % r["proposed_jump_px"],
                            "" if st is None else "%.2f" % st, ok_red])
            serie.append((fin, st, r.get("state")))
            edades.append(edad)
            procs.append(proc)
            i += 1

            if len(filas) >= a.volcar_cada:
                wr.writerows(filas)
                del filas[:]
            if time.time() >= t_prox_print:
                con = sum(1 for t, s, e in serie if t is not None)
                print("  %5.1f s  %5d frames  disp %.1f %%  estado %-10s "
                      "steer %s" % (time.time() - t_ini, i,
                                    100.0 * con / max(i, 1),
                                    r.get("state", "?"),
                                    "--" if st is None else "%+6.1f" % st))
                t_prox_print = time.time() + 2.0
    except KeyboardInterrupt:
        print("\n  Ctrl-C: cerrando y guardando...")
    finally:
        if filas:
            wr.writerows(filas)
        f.close()
        fuente.stop()
        if grabador is not None:
            grabador.release()
        restaurar()

    m = resumen(serie, edades, procs, repetidos, spat, rederiv_mal, saltados)
    print("")
    print("  CSV      %s" % destino)
    if a.grabar:
        print("  video    %s   (material NUEVO para el banco de replay)"
              % os.path.join(AQUI, a.grabar))
    if m is not None:
        print("")
        print("  CRITERIO DE LA FASE 4: la disponibilidad tiene que quedar")
        print("  dentro de +-3 puntos de la del replay (93,78 % sobre los 10")
        print("  autonomos). Si se cae, es calibracion de color/luz y NO")
        print("  arquitectura: calibrador_verde.py / medir_camara.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
