#!/usr/bin/env python3
"""
Convierte el .jsonl grabado por WiFi al MISMO CSV que emite el registrador por
USB, para que todas las herramientas de analisis funcionen igual.

    python tools/wifi_a_csv.py corrida1.jsonl corrida1.csv
    python tools/analizar_diagnostico.py corrida1.csv

DIFERENCIAS con el CSV de 200 Hz, que van anotadas en la cabecera del archivo:
  - va a 10 Hz, no a 200
  - no hay columna `drop` real (queda en 0)
  - se agregan columnas *_pmin y *_rmax con las ENVOLVENTES de cada ventana de
    100 ms. Son las que permiten ver un desplome de PWM de 40 ms aunque el
    muestreo sea de 100: el analizador las usa para la deteccion de colapso si
    estan, y si no cae en los valores instantaneos.
"""
import argparse
import json
import sys

CAMPOS = ("us,dt,drop,rxsteer,rxspeed,rxage,rxf,rot,ls,rs,ddir,ram,"
          "fl_dir,fl_set,fl_rpm,fl_pwm,fl_enc,fl_tog,fl_raw,"
          "fr_dir,fr_set,fr_rpm,fr_pwm,fr_enc,fr_tog,fr_raw,"
          "bl_dir,bl_set,bl_rpm,bl_pwm,bl_enc,bl_tog,bl_raw,"
          "br_dir,br_set,br_rpm,br_pwm,br_enc,br_tog,br_raw,"
          "yaw,pit,gx,gy,gz,"
          "fl_pmin,fr_pmin,bl_pmin,br_pmin,fl_rmax,fr_rmax,bl_rmax,br_rmax")
RUEDAS = ("fl", "fr", "bl", "br")


def g(d, *camino, dflt=0):
    for k in camino:
        if not isinstance(d, dict):
            return dflt
        d = d.get(k)
        if d is None:
            return dflt
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("csv")
    args = ap.parse_args()

    nota, frames = None, []
    with open(args.jsonl, encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if "nota" in d and "t" not in d:
                nota = d["nota"]
                continue
            if d.get("t") is not None:
                frames.append(d)
    if not frames:
        sys.exit("El .jsonl no tiene frames validos.")
    frames.sort(key=lambda d: d["t"])

    with open(args.csv, "w", encoding="utf-8", newline="") as out:
        out.write("# RescueBot IITA - convertido de telemetria WiFi (10 Hz)\n")
        if nota:
            out.write("# nota: %s\n" % nota)
        out.write("# ORIGEN: frame JSON por WiFi. 10 Hz, no 200. La columna drop no\n")
        out.write("# existe en este camino. Las columnas *_pmin y *_rmax son las\n")
        out.write("# ENVOLVENTES de cada ventana de 100 ms: con ellas un desplome de\n")
        out.write("# PWM de 40 ms se ve igual, aunque el muestreo sea de 100 ms.\n")
        out.write("# hz=10 ticks_vuelta=540 fix_lazo=? fix_curva=? lazo=? commit=wifi\n")
        out.write(CAMPOS + "\n")

        ant = None
        for d in frames:
            t = int(d["t"])                      # millis del Teensy
            us = t * 1000
            dt = (t - ant) * 1000 if ant is not None else 0
            ant = t
            fila = [us, min(65535, dt), 0,
                    int(round(g(d, "rpi", "steer") * 1000)),
                    int(g(d, "rpi", "speed")),
                    int(g(d, "rxage", dflt=-1)),
                    int(g(d, "rpi", "rxf")),
                    int(round(g(d, "drv", "rot") * 1000)),
                    int(g(d, "drv", "ls")), int(g(d, "drv", "rs")),
                    int(g(d, "drv", "dir")), int(g(d, "drv", "ram"))]
            for w in RUEDAS:
                fila += [int(g(d, "dir", w)), int(g(d, "set", w)), int(g(d, "rpm", w)),
                         int(g(d, "pwm", w)), int(g(d, "enc", w)),
                         int(g(d, "tog", w)), int(g(d, "raw", w))]
            fila += [int(round(g(d, "imu", "yaw") * 10)),
                     int(round(g(d, "imu", "pit") * 10)),
                     int(round(g(d, "gyr", "x") * 10)),
                     int(round(g(d, "gyr", "y") * 10)),
                     int(round(g(d, "gyr", "z") * 10))]
            fila += [int(g(d, "pmin", w)) for w in RUEDAS]
            fila += [int(g(d, "rmax", w)) for w in RUEDAS]
            out.write(",".join(str(x) for x in fila) + "\n")

    dur = (frames[-1]["t"] - frames[0]["t"]) / 1000.0
    print("%d frames -> %s  (%.1f s, %.1f Hz)"
          % (len(frames), args.csv, dur, len(frames) / dur if dur else 0))
    faltan = [k for k in ("raw", "pmin", "rmax", "gyr", "drv", "set", "dir")
              if k not in frames[0]]
    if faltan:
        print("AVISO: el frame no trae %s. Es firmware viejo: reflashear el Teensy," % faltan)
        print("       si no, esas columnas van en 0 y el analisis pierde causas.")
    print("Analizar con:  python tools/analizar_diagnostico.py %s" % args.csv)


if __name__ == "__main__":
    main()
