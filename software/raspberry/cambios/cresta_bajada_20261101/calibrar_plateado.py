# -*- coding: utf-8 -*-
"""calibrar_plateado.py - el umbral de la banda plateada (PLATEADO_UMBRAL) con grabaciones de la sede (2-nov-2026).

Corre en la Pi o en la PC sobre grabaciones GRABAR_CRUDO (los PNG + cuadros.csv). No abre la camara ni mueve el
robot. No sirve el video .avi: la compresion cambia la textura y con eso el puntaje.

    python3 calibrar_plateado.py --entrada /home/iita/crudo_sede_entrada --vuelta /home/iita/crudo_sede_vuelta

  --entrada  pasadas por la entrada al plateado, arrancando ANTES del zigzag, como en la competencia. Cada pasada
             termina en la entrada (entra, o se frena y se reubica): su ULTIMA recuperacion es la de la banda. Las
             de antes (el zigzag) cuentan como curvas comunes: ahi la regla no tiene que actuar.
  --vuelta   una vuelta SIN la entrada: sus curvas a la izquierda son las que NO tienen que activar la regla.
  Cada carpeta puede llevar una ventana del video (minuto:segundo, cuadro/20): CARPETA@4:00-4:30

Para cada recuperacion (GS4) calcula lo mismo que main.py: la banda en los 6 cuadros antes de perder la cinta
(llegada) y desde que termina el retroceso hasta la decision (post), y se queda con el menor de los dos. El umbral
va en el medio entre la curva a la izquierda mas alta de la vuelta y la entrada mas baja que se pueda separar.
"""
import argparse
import csv
import glob
import os
import re
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plateado_entrada import puntaje_banda  # noqa: E402  (la misma cuenta que main.py)

SEPARACION_MIN = 150     # entre la curva mas alta y una entrada, para dejar 75 de margen a cada lado
POCAS_CURVAS = 5
PASADA_HUECO_S = 3.0     # la grabacion se corta al reubicar o al entrar al rescate: ahi termina una pasada


def mmss(s):
    return "%d:%05.2f" % (s // 60, s % 60)


def leer_ventana(arg):
    """'CARPETA@4:00-4:30' -> (CARPETA, 240.0, 270.0) en segundos de video."""
    if "@" not in arg:
        return arg, None, None
    carpeta, v = arg.rsplit("@", 1)
    a, b = v.split("-")
    seg = lambda x: float(x.split(":")[0]) * 60 + float(x.split(":")[1]) if ":" in x else float(x)
    return carpeta, seg(a), seg(b)


def grabaciones(carpeta):
    rutas = sorted(glob.glob(os.path.join(carpeta, "**", "cuadros.csv"), recursive=True))
    if not rutas:
        sys.exit("No hay cuadros.csv adentro de %s (tiene que ser la carpeta de GRABAR_CRUDO)" % carpeta)
    return [os.path.dirname(r) for r in rutas]


def hora_inicio(d):
    """La subcarpeta de GRABAR_CRUDO se llama MMDD_HHMMSS: la hora en que arranco main.py."""
    m = re.match(r"\d{4}_(\d{2})(\d{2})(\d{2})$", os.path.basename(d))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def hhmmss(s):
    return "--:--:--" if s is None else "%02d:%02d:%02d" % (s // 3600 % 24, s // 60 % 60, s % 60)


def episodios(d, desde, hasta):
    r = list(csv.DictReader(open(os.path.join(d, "cuadros.csv"))))
    N = len(r)
    t = [float(x["t"]) for x in r]
    pasada = [0] * N
    for k in range(1, N):
        pasada[k] = pasada[k - 1] + (1 if t[k] - t[k - 1] > PASADA_HUECO_S else 0)
    h0 = hora_inicio(d)
    cache = {}

    def banda(k):
        n = int(r[k]["n"])
        if n not in cache:
            im = cv2.imread(os.path.join(d, "f_%06d.png" % n))
            cache[n] = None if im is None else puntaje_banda(im)
        return cache[n]

    out = []
    i = 6
    while i < N:
        if not (r[i]["green_state"] == "4" and r[i - 1]["green_state"] != "4"):
            i += 1
            continue
        i0 = i
        video = int(r[i0]["n"]) / 20.0
        # fin del retroceso: el ultimo cuadro esperando el 0xEF
        j = i0
        while j < N - 1 and t[j] - t[i0] < 4.0 and r[j]["quien"] != "recup-espera-retro-ack":
            j += 1
        while j < N - 1 and r[j + 1]["quien"] == "recup-espera-retro-ack":
            j += 1
        ini = j + 1
        i = ini
        if (desde is not None and not desde <= video <= hasta) or ini >= N or t[i0 - 1] - t[i0 - 6] > 1.0:
            continue
        kd = next((k for k in range(ini, min(N, ini + 80)) if r[k]["quien"] in ("recup-CURVA", "gap-inicio")), None)
        if kd is not None and r[kd]["quien"] == "recup-CURVA":
            ang = float(r[kd]["angle"])
            decision = "CURVA %s %+.0f" % ("IZQ" if ang > 0 else "DER", ang)
        elif kd is not None:
            amb = sum(1 for k in range(ini, kd) if r[k]["quien"] == "recup-AMBIGUA")
            decision = "AMBIGUA->GAP" if amb and t[kd] - t[ini] >= 0.9 else "GAP"
        else:
            decision = "otra (%s)" % r[ini]["quien"]
        fin = kd if kd is not None else min(N - 1, ini + 25)
        post_k = [k for k in range(ini, fin + 1) if r[k]["green_state"] == "4" or k == fin]
        sl = [banda(k) for k in range(i0 - 6, i0)]
        sp = [banda(k) for k in post_k]
        if None in sl or None in sp or not sp:
            continue
        # como main.py: segundos desde el ultimo aviso de rampa, al decidir
        ult = next((k for k in range(fin, -1, -1) if r[k]["rampa"] not in ("0", "")), None)
        rampa = None if ult is None else (0.0 if ult == fin else t[fin] - t[ult])
        lleg, post = float(np.median(sl)), float(np.median(sp))
        out.append(dict(video=video, hora=None if h0 is None else h0 + t[i0], decision=decision,
                        izq=decision.startswith("CURVA IZQ"), llegada=lleg, post=post, menor=min(lleg, post),
                        rampa=rampa, pasada=(d, pasada[i0]), entrada=False))
    return out


def tabla(titulo, eps, umbral, rampa_s):
    print("\n== %s: %d recuperaciones" % (titulo, len(eps)))
    if not eps:
        return
    print("   hora      video     decision        llegada  post  rampa    con umbral %.0f" % umbral)
    for e in eps:
        banda = e["llegada"] >= umbral and e["post"] >= umbral
        cerca = e["rampa"] is not None and e["rampa"] < rampa_s
        if not e["izq"]:
            ahora = "-"
        elif banda and not cerca:
            ahora = "RECTA"
        elif banda:
            ahora = "no (rampa)"
        else:
            ahora = "no actua"
        rampa = "-" if e["rampa"] is None else "%.0f s" % e["rampa"]
        marca = "<- entrada" if e["entrada"] else ("(antes de la banda)" if titulo == "ENTRADA" else "")
        print("   %s  %-8s  %-14s  %5.0f  %5.0f  %6s   %-10s %s" % (
            hhmmss(e["hora"]), mmss(e["video"]), e["decision"], e["llegada"], e["post"], rampa, ahora, marca))


def resultado(pasadas, curvas, umbral_actual):
    """pasadas: la ultima recuperacion de cada pasada (la de la banda). curvas: las curvas a la izquierda, lejos de
    rampas, que NO son la banda (las de la vuelta y las de antes de la banda en las pasadas, como el zigzag).
    Imprime el resumen y devuelve el umbral sugerido, o None si no hay que cambiarlo."""
    print("\n== Resultado")
    if not pasadas:
        print("En la entrada no hubo recuperaciones: el robot no perdio la cinta ahi (entro solo o el sensor")
        print("confirmo antes). En esa entrada la regla no hace falta: dejar el umbral como esta (%.0f)." % umbral_actual)
        return None
    print("Entrada: %d pasadas. De cada una, el menor de llegada y post: %s" % (
        len(pasadas), ", ".join("%.0f" % e["menor"] for e in pasadas)))
    if not curvas:
        print("Ninguna curva a la izquierda con recuperacion lejos de rampas, aparte de la banda: no hay con que comparar.")
        pasan = sum(1 for e in pasadas if e["menor"] >= umbral_actual)
        print("Con el umbral de ahora (%.0f) la banda lo pasa en %d de %d pasadas." % (umbral_actual, pasan, len(pasadas)))
        if pasan < len(pasadas):
            print("Para bajar el umbral hace falta una vuelta con curvas a la izquierda: dejar %.0f." % umbral_actual)
        else:
            print("Dejar %.0f." % umbral_actual)
        return None
    alta = max(curvas, key=lambda e: e["menor"])
    s_no = alta["menor"]
    n_antes = sum(1 for e in curvas if e["pasada_entrada"])
    print("Curvas a la izquierda que no son la banda, lejos de rampas: %d (%d de la vuelta, %d antes de la banda en las"
          " pasadas)." % (len(curvas), len(curvas) - n_antes, n_antes))
    print("La mas alta da %.0f (hora %s, video %s, %s)." % (
        s_no, hhmmss(alta["hora"]), mmss(alta["video"]),
        "en una pasada, ANTES de la banda" if alta["pasada_entrada"] else "en la vuelta"))
    if len(curvas) < POCAS_CURVAS:
        print("  Ojo: son pocas curvas (menos de %d). Si se puede, dar otra vuelta." % POCAS_CURVAS)
    separables = [e for e in pasadas if e["menor"] >= s_no + SEPARACION_MIN]
    if not separables:
        print("NO SEPARA con esta luz: ninguna pasada da %d mas que esa curva." % SEPARACION_MIN)
        if alta["pasada_entrada"]:
            print("  Esa curva es antes de la banda (el zigzag): ahi la camara ya ve la banda y la regla podria mandarlo")
            print("  derecho donde tiene que girar.")
        else:
            print("  Si esa curva de la vuelta era la entrada, cortar la vuelta antes con CARPETA@0:00-<minuto>.")
        print("Apagar la regla en el servicio (queda como antes del cambio):")
        print("  sed -i 's/\"PLATEADO_RECTA\": \"1\"/\"PLATEADO_RECTA\": \"0\"/' /home/iita/Desktop/main.py")
        return None
    baja = min(e["menor"] for e in separables)
    umbral = int(round((baja + s_no) / 2.0 / 10.0) * 10)
    pasan = [e for e in pasadas if e["menor"] >= umbral]
    print("Umbral sugerido: %d (en el medio; margen %.0f para cada lado)." % (umbral, (baja - s_no) / 2.0))
    print("Con %d la banda lo pasa en %d de %d pasadas." % (umbral, len(pasan), len(pasadas)))
    for e in pasadas:
        if e["menor"] < umbral:
            print("  No pasa la pasada de las %s (video %s, %.0f): o no llego a la banda, o ahi la banda casi no se"
                  " ve." % (hhmmss(e["hora"]), mmss(e["video"]), e["menor"]))
    print("Para usarlo en el servicio:")
    print("  sed -i 's/\"PLATEADO_UMBRAL\": \"[0-9]*\"/\"PLATEADO_UMBRAL\": \"%d\"/' /home/iita/Desktop/main.py" % umbral)
    print("Para una corrida a mano: PLATEADO_UMBRAL=%d adelante de python3." % umbral)
    return umbral


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--entrada", nargs="+", required=True, help="grabaciones de las pasadas por la entrada")
    ap.add_argument("--vuelta", nargs="*", default=[], help="grabaciones de la vuelta sin la entrada")
    ap.add_argument("--umbral", type=float, default=float(os.environ.get("PLATEADO_UMBRAL", "1790")))
    ap.add_argument("--rampa-s", type=float, default=float(os.environ.get("PLATEADO_RAMPA_S", "20")))
    a = ap.parse_args()

    ent, vue = [], []
    for nombre, lista, destino in (("entrada", a.entrada, ent), ("vuelta", a.vuelta, vue)):
        for arg in lista:
            carpeta, desde, hasta = leer_ventana(arg)
            for d in grabaciones(carpeta):
                eps = episodios(d, desde, hasta)
                print("leida (%s): %s  arranco %s, %d recuperaciones" % (
                    nombre, d, hhmmss(hora_inicio(d)), len(eps)))
                destino += eps
    # de cada pasada por la entrada, la ultima recuperacion es la de la banda
    ultima = {}
    for e in ent:
        if e["pasada"] not in ultima or e["video"] > ultima[e["pasada"]]["video"]:
            ultima[e["pasada"]] = e
    pasadas = sorted(ultima.values(), key=lambda e: (e["pasada"][0], e["video"]))
    for e in pasadas:
        e["entrada"] = True
    tabla("ENTRADA", ent, a.umbral, a.rampa_s)
    tabla("VUELTA", vue, a.umbral, a.rampa_s)

    # las curvas a la izquierda que NO son la banda: las de la vuelta y las de antes de la banda en las pasadas
    lejos = lambda e: e["izq"] and (e["rampa"] is None or e["rampa"] >= a.rampa_s)
    curvas = ([dict(e, pasada_entrada=False) for e in vue if lejos(e)] +
              [dict(e, pasada_entrada=True) for e in ent if lejos(e) and not e["entrada"]])
    resultado(pasadas, curvas, a.umbral)


if __name__ == "__main__":
    main()
