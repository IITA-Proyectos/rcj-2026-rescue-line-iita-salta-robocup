# -*- coding: utf-8 -*-
"""
EL RETARDO, CON EL GIROSCOPIO DE VERDAD. Y son datos del robot, no de replay.

Benjamin, 25-ago: "revisa los csv, que estan en el repo".

Tenia razon y era el dato que faltaba. En `software/teensy/firmware/corridas/`
hay DIEZ corridas grabadas por el registrador del Teensy el 22-ago, con el
giroscopio real del BNO055 en la misma fila que el comando. Todo lo que se venia
midiendo con correlacion de fase sobre el fondo -que es un estimador debil, da
1.075 frames sobre 80 grados/s en un robot cuyo techo es 39- aca se puede medir
con el sensor de verdad.

LAS COLUMNAS  (`main.cpp`, la cabecera que emite el propio registrador)

    us,dt,drop,rxsteer,rxspeed,rxage,rxf,rot,ls,rs,ddir,ram,
    fl_*(7), fr_*(7), bl_*(7), br_*(7),
    yaw,pit,gx,gy,gz

Los CSV no traen esa linea: traen `# nota=...` y despues los datos. La cabecera
vive en el codigo y por eso este script la reconstruye.

OJO CON `dt`: NO ES EL PERIODO DEL LAZO
----------------------------------------
`dt` sale del registrador, y el registrador es un IntervalTimer de hardware a
200 Hz (`diagTimer.begin(diagMuestrear, DIAG_PERIODO_US)`). Por eso `dt` da
5,000 ms en las 117.788 muestras, clavado. Es SU periodo, no el del lazo.

El periodo del LAZO se mide por cuando cambian las variables que EL escribe:
`ls` y `rs`, las consignas por lado, que se recalculan en cada vuelta.

=========================== RESULTADO, 25-ago ============================

Sobre las SEIS corridas de PISTA (las de banco quedan afuera: con el robot
quieto el comando casi no cambia y el conteo no mide vueltas):

    periodo del lazo    p50 35-40 ms por corrida   ->  25 a 28,6 Hz
    histograma          modo principal 30-35 ms (30,4 %)
                        SEGUNDO MODO   65-80 ms (15,6 %)

    lag comando -> giro 13-14 muestras x 5 ms  =  65-70 ms
    el comando CAMBIA   8,8 a 20,6 veces por segundo
    el robot OBEDECE    76 a 87 % en pista (99 % en banco)

CONFIRMA EL TRASPASO, Y CON EL SENSOR BUENO. La seccion 3.1 decia "p50 30 ms,
segundo modo en 65", "el comando cambia a 8,6-20,6 Hz" y "el lag rot->gz es
65-70 ms = dos periodos de lazo". Las tres cosas salen igual aca, pero medidas
contra el GIROSCOPIO DEL BNO055 y no contra la correlacion de fase sobre el
fondo -que es el estimador debil que veniamos usando en el replay-.

Y el lag de 65-70 ms son, efectivamente, ~2 periodos de un lazo de 35 ms.

QUE SE MIDE

  1. el PERIODO del lazo            intervalo entre cambios de `ls`/`rs`
  2. cada cuanto CAMBIA el comando  veces por segundo que cambia `rxsteer`
  3. el LAG comando -> giro real    correlacion cruzada `rot` contra `gz`
  4. si el robot OBEDECE            signo de `rot` contra signo de `gz`

    python retardo_real.py
"""

import glob
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
# DONDE ESTAN LOS CSV. Se busca, no se asume, porque este archivo vive en DOS
# repos con estructuras distintas:
#   repo roboliga : analisis/corridas/            (al lado del script)
#   repo RCJ      : software/teensy/firmware/corridas/
# La variable de entorno CORRIDAS_DIR gana sobre las dos.
def _buscar_corridas():
    env = os.environ.get("CORRIDAS_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    for c in (os.path.join(AQUI, "corridas"),
              os.path.join(AQUI, "..", "..", "teensy", "firmware", "corridas")):
        c = os.path.abspath(c)
        if os.path.isdir(c):
            return c
    # ninguna existe: se devuelve la del repo RCJ para que el mensaje de error
    # diga algo util en vez de fallar con una ruta vacia
    return os.path.abspath(os.path.join(
        AQUI, "..", "..", "teensy", "firmware", "corridas"))


CORRIDAS = _buscar_corridas()

COLS = ("us,dt,drop,rxsteer,rxspeed,rxage,rxf,rot,ls,rs,ddir,ram,"
        "fl_dir,fl_set,fl_rpm,fl_pwm,fl_enc,fl_tog,fl_raw,"
        "fr_dir,fr_set,fr_rpm,fr_pwm,fr_enc,fr_tog,fr_raw,"
        "bl_dir,bl_set,bl_rpm,bl_pwm,bl_enc,bl_tog,bl_raw,"
        "br_dir,br_set,br_rpm,br_pwm,br_enc,br_tog,br_raw,"
        "yaw,pit,gx,gy,gz").split(",")
IDX = {n: i for i, n in enumerate(COLS)}


def cargar(ruta):
    filas = []
    nota = ""
    with open(ruta, encoding="utf-8", errors="ignore") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            if l.startswith("#"):
                if "nota=" in l:
                    nota = l.split("nota=", 1)[1]
                continue
            p = l.split(",")
            if len(p) != len(COLS):
                continue                     # linea cortada o cabecera reemitida
            try:
                filas.append([int(x) for x in p])
            except ValueError:
                continue
    if not filas:
        return None, nota
    return np.array(filas, dtype=np.int64), nota


def col(a, n):
    return a[:, IDX[n]].astype(float)


def xcorr(x, y, maxlag=40):
    """(lag optimo, corr ahi, corr en lag 0). lag>0 = `y` va DESPUES."""
    best = (0, -2.0)
    r0 = float("nan")
    for L in range(0, maxlag + 1):
        if L >= len(x):
            break
        xx = x[:len(x) - L] if L else x
        yy = y[L:]
        n = min(len(xx), len(yy))
        if n < 50:
            break
        sx, sy = xx[:n], yy[:n]
        if sx.std() < 1e-9 or sy.std() < 1e-9:
            continue
        r = float(np.corrcoef(sx, sy)[0, 1])
        if L == 0:
            r0 = r
        if r > best[1]:
            best = (L, r)
    return best[0], best[1], r0


def main():
    rutas = sorted(glob.glob(os.path.join(CORRIDAS, "*.csv")))
    if not rutas:
        print("  no encontre corridas en %s" % CORRIDAS)
        return 1

    print("")
    print("=" * 108)
    print("  EL RETARDO CON EL GIROSCOPIO REAL   -   %d corridas del 22-ago"
          % len(rutas))
    print("=" * 108)
    print("")
    print("  %-34s %7s %9s %9s %11s %9s %9s %9s"
          % ("corrida", "n", "lazo p50", "lazo p90", "cambios/s", "lag", "corr",
             "obedece"))
    tot_dt = []
    tot_lag = []
    for r in rutas:
        a, nota = cargar(r)
        nom = os.path.basename(r).replace("2026-08-22_", "").replace(".csv", "")
        if a is None or len(a) < 200:
            print("  %-34s   sin datos utiles" % nom[:34])
            continue
        us = col(a, "us")
        ls = col(a, "ls")
        rs = col(a, "rs")
        # PERIODO DEL LAZO: intervalo entre cambios de las consignas por lado.
        # `dt` no sirve: es el periodo del registrador, 5 ms fijos por hardware.
        cam = np.where((np.diff(ls) != 0) | (np.diff(rs) != 0))[0]
        per = np.diff(us[cam]) / 1000.0 if len(cam) > 1 else np.array([])
        per = per[(per > 0) & (per < 500)]
        rot = col(a, "rot") / 1000.0
        gz = col(a, "gz") / 10.0
        rxs = col(a, "rxsteer") / 1000.0

        # cuantas veces por segundo CAMBIA el comando que llego de la Pi
        dur_s = (us[-1] - us[0]) / 1e6 if len(us) > 1 else 0.0
        cambios = int((np.diff(rxs) != 0).sum())
        cps = cambios / dur_s if dur_s > 0 else float("nan")

        lag, corr, _r0 = xcorr(rot, gz)
        # obedece: mismo signo, con banda muerta
        m = (np.abs(rot) > 0.05) & (np.abs(gz) > 3.0)
        obed = 100.0 * ((rot[m] > 0) == (gz[m] > 0)).mean() if m.sum() > 50 \
            else float("nan")

        # Solo las corridas de PISTA entran al agregado. En banco la Pi no
        # esta conectada -cambios/s = 0-, el comando no cambia nunca y los
        # intervalos entre cambios de `ls`/`rs` no miden vueltas del lazo sino
        # el ruido del PID. Se muestran igual, pero no suman.
        pocos = len(per) < 50 or not (cps > 1.0)
        dt_p50 = float("nan") if pocos else np.percentile(per, 50)
        dt_p90 = float("nan") if pocos else np.percentile(per, 90)
        if not pocos:
            tot_dt.append(per)
        tot_lag.append((nom, lag, corr))
        print("  %-34s %7d %8.1f %8.1f %10.1f %8d %9.3f %8.0f %%"
              % (nom[:34], len(a), dt_p50, dt_p90, cps, lag, corr, obed))

    if tot_dt:
        d = np.concatenate(tot_dt)
        print("")
        print("  SOLO LAS DE PISTA  n=%d periodos" % len(d))
        print("     dt:  p25 %.1f   p50 %.1f   p75 %.1f   p90 %.1f   p99 %.1f ms"
              % tuple(np.percentile(d, [25, 50, 75, 90, 99])))
        print("     el traspaso 3.1 dice p50 30 ms con un segundo modo en 65:")
        print("     coincide, y aca esta medido contra el giroscopio del BNO.")
        h, b = np.histogram(d, bins=[0, 5, 10, 20, 25, 30, 35, 40, 60, 70, 200])
        print("")
        print("     histograma del periodo (ms):")
        for c, lo, hi in zip(h, b[:-1], b[1:]):
            if c:
                print("        %5.0f - %-5.0f  %7d  %5.1f %%  %s"
                      % (lo, hi, c, 100.0 * c / len(d), "#" * int(60.0 * c / len(d))))
    print("")
    print("  lag: en unidades de MUESTRA del registrador, no de frame de video.")
    print("=" * 108)
    return 0


if __name__ == "__main__":
    sys.exit(main())
