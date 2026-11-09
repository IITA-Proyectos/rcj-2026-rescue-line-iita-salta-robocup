# -*- coding: utf-8 -*-
"""MEDIR EL RETARDO REAL DEL LAZO. No mueve el robot. Manda speed=0.

Por que
-------
La idea del profesor -que el timing importa- es correcta, y nunca lo medimos.
Hoy no sabemos cuantos ms pasan entre que la camara capta un frame y la Teensy
recibe la orden correspondiente. Sin ese numero no se puede decidir nada sobre
retardos, ni a favor ni en contra.

Este script lo mide con el `main.py` REAL, no con una version de laboratorio:
usa el mismo `WebcamVideoStream`, la misma cadena de mascaras y el mismo
`send_frame`. Manda **speed = 0** en todos los frames, asi que el robot no se
mueve.

Lo que separa
------------
    captura        vs.read()
    vision linea   mascaras + atan2, tal cual el main
    verde/plata/rojo   las otras tres mascaras del mismo lazo
    serial         ser.write() + ser.flush()
    drenaje        el `while ser.in_waiting` que lee los ACK
    TOTAL          lo que tarda una vuelta entera

Y mide dos cosas que hoy son sospechosas y estan en el codigo:

  1. `print(area)` dentro del bucle de contornos plateados
     (`main.py`, uno por contorno por frame). Se mide con y sin.
  2. `ser.flush()`, que bloquea hasta vaciar el buffer de salida.

Uso en la Pi
------------
    python3 medir_latencia.py                 # 300 frames, robot quieto
    python3 medir_latencia.py --sin-serial    # si no queres abrir el puerto
    python3 medir_latencia.py --frames 600
"""

import argparse
import math
import os
import sys
import time

import numpy as np
import cv2

LO = np.array([0, 0, 0], np.uint8)
HI = np.array([90, 90, 90], np.uint8)
W, H = 160, 120
CAM_X = W / 2 - 1
CAM_Y = H - 1

X_COM = np.zeros((H, W))
Y_COM = np.zeros((H, W))
for _i in range(H):
    for _j in range(W):
        X_COM[_i][_j] = (_j - CAM_X) / (W / 2)
        Y_COM[_i][_j] = (CAM_Y - _i) / H

LOWER_GREEN = np.array([70, 85, 138])
UPPER_GREEN = np.array([104, 102, 158])
LOWER_SILVER = np.array([79, 16, 46])
UPPER_SILVER = np.array([168, 28, 79])
LOWER_RED1 = np.array([0, 84, 54])
UPPER_RED1 = np.array([7, 255, 200])
LOWER_RED2 = np.array([170, 84, 54])
UPPER_RED2 = np.array([179, 255, 200])


def p(v):
    v = np.asarray(v, float)
    return (v.mean(), np.median(v), np.percentile(v, 95), v.max())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--sin-serial", action="store_true")
    ap.add_argument("--puerto", default="/dev/serial0")
    a = ap.parse_args(argv)

    print("")
    print("=" * 74)
    print(" RETARDO REAL DEL LAZO DE LINEA   (robot quieto, speed=0)")
    print("=" * 74)

    try:
        from camthreader import WebcamVideoStream
        vs = WebcamVideoStream(src=0).start()
        time.sleep(1.0)
        usa_hilo = True
        print("  captura: camthreader (igual que main.py)")
    except Exception as e:
        print("  camthreader no disponible (%s), uso VideoCapture" % e)
        vs = cv2.VideoCapture(0)
        usa_hilo = False

    ser = None
    if not a.sin_serial:
        try:
            import serial
            ser = serial.Serial(a.puerto, 115200, timeout=0.05, write_timeout=0.05)
            print("  serial : %s abierto" % a.puerto)
        except Exception as e:
            print("  serial : NO se pudo abrir (%s). Sigo sin serial." % e)

    t_cap, t_lin, t_otras, t_ser, t_flush, t_drena, t_tot = [], [], [], [], [], [], []
    t_print = []
    n = 0
    while n < a.frames:
        t0 = time.perf_counter()
        fr = vs.read() if usa_hilo else vs.read()[1]
        if fr is None:
            time.sleep(0.005)
            continue
        t1 = time.perf_counter()

        # --- vision de linea, igual que main.py -------------------------
        fr = cv2.rotate(fr, cv2.ROTATE_180)
        g = cv2.resize(fr, (W, H), interpolation=cv2.INTER_NEAREST)
        black = cv2.inRange(g, LO, HI)
        black[:60, :] = 0
        xb = cv2.bitwise_and(X_COM, X_COM, mask=black)
        xb = xb * (1 - Y_COM)
        yb = cv2.bitwise_and(Y_COM, Y_COM, mask=black)
        ang = (math.atan2(float(np.mean(yb)), float(np.mean(xb))) / math.pi * 180) - 90
        t2 = time.perf_counter()

        # --- las otras tres mascaras del mismo lazo ---------------------
        lab = cv2.cvtColor(g, cv2.COLOR_BGR2LAB)
        gm = np.zeros((H, W), np.uint8)
        gm[80:, :] = cv2.inRange(lab[80:, :, :], LOWER_GREEN, UPPER_GREEN)
        hsv = cv2.cvtColor(g, cv2.COLOR_BGR2HSV)
        rm = cv2.bitwise_or(cv2.inRange(hsv, LOWER_RED1, UPPER_RED1),
                            cv2.inRange(hsv, LOWER_RED2, UPPER_RED2))
        rm[:75, :] = 0
        sm = cv2.inRange(g, LOWER_SILVER, UPPER_SILVER)
        sm[:75, :] = 0
        cont, _ = cv2.findContours(sm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        t3 = time.perf_counter()

        # --- lo que cuesta el print(area) que esta en main.py -----------
        tp0 = time.perf_counter()
        for c in cont:
            print(cv2.contourArea(c))
        tp1 = time.perf_counter()

        # --- serial, speed=0 -------------------------------------------
        t4 = t5 = t6 = tp1
        if ser is not None:
            ang_b = max(0, min(255, int(round(ang)) + 90))
            out = bytes([0xFF, 0, 0xFE, ang_b, 0xFD, 0, 0xFC, 0])
            t4 = time.perf_counter()
            try:
                ser.write(out)
            except Exception:
                pass
            t5 = time.perf_counter()
            try:
                ser.flush()
            except Exception:
                pass
            t6 = time.perf_counter()
            while ser.in_waiting > 0:
                ser.read()
        t7 = time.perf_counter()

        t_cap.append((t1 - t0) * 1000)
        t_lin.append((t2 - t1) * 1000)
        t_otras.append((t3 - t2) * 1000)
        t_print.append((tp1 - tp0) * 1000)
        t_ser.append((t5 - t4) * 1000)
        t_flush.append((t6 - t5) * 1000)
        t_drena.append((t7 - t6) * 1000)
        t_tot.append((t7 - t0) * 1000)
        n += 1

    try:
        vs.stop() if usa_hilo else vs.release()
    except Exception:
        pass
    if ser is not None:
        try:
            ser.write(bytes([0xFF, 0, 0xFE, 90, 0xFD, 0, 0xFC, 0]))
            ser.flush()
            ser.close()
        except Exception:
            pass

    print("")
    print("  %-24s %8s %8s %8s %8s" % ("etapa (ms)", "media", "p50", "p95", "max"))
    print("  " + "-" * 60)
    for et, v in (("captura (vs.read)", t_cap),
                  ("vision de linea", t_lin),
                  ("verde/plata/rojo", t_otras),
                  ("print(area) <- sacar", t_print),
                  ("ser.write", t_ser),
                  ("ser.flush <- bloquea", t_flush),
                  ("drenar ACKs", t_drena)):
        m, md, p95, mx = p(v)
        print("  %-24s %8.2f %8.2f %8.2f %8.2f" % (et, m, md, p95, mx))
    print("  " + "-" * 60)
    m, md, p95, mx = p(t_tot)
    print("  %-24s %8.2f %8.2f %8.2f %8.2f" % ("TOTAL una vuelta", m, md, p95, mx))

    print("")
    print("  fps efectivo: %.1f   (media %.1f ms por vuelta)" % (1000.0 / m, m))
    pr = float(np.mean(t_print))
    print("  el print(area) se lleva %.2f ms de media, o sea el %.0f %% de la vuelta"
          % (pr, 100.0 * pr / max(m, 1e-9)))
    print("")
    print("  LO QUE ESTE NUMERO NO DICE: cuanto tarda la Teensy en parsear,")
    print("  correr el PID y mover los motores. Eso se suma aparte, y para")
    print("  medirlo hace falta la telemetria del CSV con el robot moviendose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
