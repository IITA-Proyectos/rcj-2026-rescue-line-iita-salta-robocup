#!/usr/bin/env python3
"""
Marca en un CSV de registrar_diagnostico.py donde el robot iba SUBIENDO, BAJANDO, de COSTADO o en LLANO.

    python tools/tramos_rampa.py bajada_1010_2045.csv

Usa la columna `pit` (pitch x10, + = trompa arriba) con los MISMOS umbrales que el aviso que la Teensy le
manda a la Pi (actualizarEstadoRampaPi): entra con +-14 grados sostenidos 200 ms y vuelve a llano con
+-8. Es lo que la Pi ve como SUBE / BAJA / LLANO en el log ([ROI-RAMPA]).
COSTADO = rampa lateral: |rol| >= 15 grados sostenidos 300 ms, sale con <= 8 (en la subida recta el roll
no pasa de 8).

OJO: la columna `rampa` del CSV es OTRO detector (rampa.h: 14 grados 1 s + 5 cm de avance, sale con 10).
Llega mas tarde; no es lo que ve la Pi.

En cada tramo cuenta tambien lo que hizo el robot (columna `ram`): 13 = pivote de la recuperacion,
21 = doble verde subiendo. "andando" = % del tramo con alguna rueda con consigna: con 0 % el robot estaba
quieto (antes de largar, o levantado a mano) y el tramo no cuenta.
"""
import csv
import sys

import numpy as np


def leer(ruta):
    # La Teensy repite la cabecera cada tanto; si el registrador arranco a mitad de camino, la primera
    # linea ya es de datos. Se usa la primera cabecera que aparezca y se saltan las repetidas.
    filas = [l for l in open(ruta, encoding="utf-8", errors="ignore") if not l.startswith("#")]
    cab = next((l for l in filas if l.startswith("us,")), None)
    if cab is None:
        sys.exit("%s no tiene la cabecera (linea que empieza con us,)" % ruta)
    r = [next(csv.reader([cab]))] + list(csv.reader(l for l in filas if not l.startswith("us,")))
    c = {k: i for i, k in enumerate(r[0])}
    for k in ("us", "pit"):
        if k not in c:
            sys.exit("%s no tiene la columna %s" % (ruta, k))
    datos = []
    for x in r[1:]:
        try:
            datos.append((float(x[c["us"]]), float(x[c["pit"]]) / 10,
                          float(x[c["rol"]]) / 10 if "rol" in c else 0.0,
                          int(float(x[c["ram"]])) if "ram" in c else 0,
                          any(float(x[c[k]]) != 0 for k in ("fl_set", "fr_set", "bl_set", "br_set") if k in c)))
        except (ValueError, IndexError):
            pass
    a = np.array(datos)
    # Tiempo desde el principio del archivo. Si la Teensy se reinicio, `us` vuelve a cero: se salta.
    dt = np.diff(a[:, 0])
    dt[(dt <= 0) | (dt > 1e6)] = 5000
    t = np.concatenate([[0.0], np.cumsum(dt)]) / 1e6
    return t, a[:, 1], a[:, 2], a[:, 3].astype(int), a[:, 4] > 0


def histeresis(x, entra, sale, t, ms_entra, ms_sale):
    """1 desde que x >= entra sostenido ms_entra, hasta que x <= sale sostenido ms_sale."""
    est = cand = 0
    desde = 0.0
    out = np.zeros(len(t), int)
    for i in range(len(t)):
        nc = (1 if x[i] >= entra else 0) if est == 0 else (0 if x[i] <= sale else 1)
        if nc != cand:
            cand, desde = nc, t[i]
        if cand != est and t[i] - desde >= (ms_entra if cand else ms_sale):
            est = cand
        out[i] = est
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    t, pit, rol, ram, anda = leer(sys.argv[1])
    sube = histeresis(pit, 14, 8, t, 0.2, 0.2)
    baja = histeresis(-pit, 14, 8, t, 0.2, 0.2)
    costado = histeresis(np.abs(rol), 15, 8, t, 0.3, 0.2)
    estado = np.where(sube == 1, "SUBE", np.where(baja == 1, "BAJA",
                      np.where(costado == 1, "COSTADO", "llano")))

    print("%s: %.1f s" % (sys.argv[1], t[-1]))
    print("  desde    hasta   tramo     pitch(min..max)  roll(min..max)  andando  recup ram13  doble verde ram21")
    i = 0
    while i < len(t):
        j = i
        while j + 1 < len(t) and estado[j + 1] == estado[i]:
            j += 1
        m = slice(i, j + 1)
        dur = t[j] - t[i]
        if estado[i] != "llano" or dur >= 1.0:
            n13 = int(np.sum(np.diff(np.concatenate([[0], (ram[m] == 13).astype(int)])) == 1))
            n21 = int(np.sum(np.diff(np.concatenate([[0], (ram[m] == 21).astype(int)])) == 1))
            print("  %7.1f %7.1f   %-8s %+5.0f..%+4.0f      %+5.0f..%+4.0f       %3.0f %%     %s            %s" % (
                t[i], t[j], estado[i], pit[m].min(), pit[m].max(), rol[m].min(), rol[m].max(),
                100.0 * anda[m].mean(), n13 if n13 else "-", n21 if n21 else "-"))
        i = j + 1


if __name__ == "__main__":
    main()
