# -*- coding: utf-8 -*-
"""
TEST DE LA TELEMETRIA DE LA CANDIDATA.

`vision_linea.ultimo()` ya exponia las cinco etapas del target y la razon de
cada guard, pero nadie las escribia: el CSV terminaba en `fps` y cuando el
veredicto es "la vision pidio el giro pero el target venia de un guard", ese CSV
no lo puede decir.

Se verifican cuatro cosas, y las cuatro tienen que dar bien:

  1. El CSV tiene TODAS las columnas y ninguna fila con un largo distinto.
  2. Los campos nuevos se pueblan de verdad: no todos cero.
  3. Se pueden DESHACER las escalas y recuperar los valores originales. Un
     campo que no se puede invertir es ruido con nombre.
  4. Con la vision APAGADA el CSV sigue teniendo las mismas columnas y los
     campos nuevos van en 0, o sea que un registro viejo se sigue leyendo.

    python test_telemetria_vision.py
"""

import csv
import importlib.util
import os
import sys

import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

VIDEO = "con_planner.avi"
SALIDA = os.path.join(AQUI, "_tlm_test.csv")


def cargar_vl(activa, ley):
    if activa:
        os.environ["VISION_LINEA"] = "camino"
    else:
        os.environ.pop("VISION_LINEA", None)
    if ley:
        os.environ["LEY_STEER"] = "stanley"
    else:
        os.environ.pop("LEY_STEER", None)
    sys.modules.pop("vision_linea", None)
    sp = importlib.util.spec_from_file_location(
        "vision_linea", os.path.join(AQUI, "vision_linea.py"))
    vl = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(vl)
    return vl


def correr(vl, tv, v2):
    cap = cv2.VideoCapture(os.path.join(AQUI, VIDEO))
    i = 0
    ultimos = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = v2.frame_pi(fr) if v2 is not None else fr
        a = vl.angulo(g)
        u = vl.ultimo()
        ultimos.append((a, dict(u)))
        tv.frame(i=i, ang_env=int(round(a)) if a is not None else 0,
                 vel_env=40, vision=u)
        i += 1
    cap.release()
    tv.cerrar()
    return ultimos


def leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        lineas = [l for l in f if not l.startswith("#")]
    r = list(csv.DictReader(lineas))
    return r, lineas


def main():
    import telemetria_vision as TV

    fallos = []
    print("")
    print("=" * 92)
    print("  1-3) VISION ENCENDIDA (camino+mono) + LEY STANLEY")
    print("=" * 92)
    print("")
    if os.path.exists(SALIDA):
        os.remove(SALIDA)
    vl = cargar_vl(True, True)
    vl._arrancar()
    tv = TV.TelemetriaVision(SALIDA)
    ult = correr(vl, tv, vl._v2)
    filas, lineas = leer(SALIDA)
    print("  %d frames, %d filas en el CSV, %d columnas"
          % (len(ult), len(filas), len(TV.CAMPOS)))

    largos = set(len(l.rstrip("\n").split(",")) for l in lineas[1:])
    print("  largos de fila distintos: %s  -> %s"
          % (sorted(largos), "OK" if largos == {len(TV.CAMPOS)} else "*** MAL"))
    if largos != {len(TV.CAMPOS)}:
        fallos.append("largo de fila")

    # Los campos DE RELOJ no son campos de vision: se llenan igual con la
    # vision apagada, porque salen de time.monotonic_ns() y no de la imagen.
    # Meterlos en `nuevos` haria fallar el punto 4 ("apagada no cambia el
    # CSV") por una razon que no es la que ese punto quiere vigilar. La
    # invariante real es: los campos que DESCRIBEN LO QUE VIO LA CAMARA tienen
    # que ser 0 cuando no hay camara.
    RELOJES = ("t_mono_ns",)
    nuevos = [c for c in TV.CAMPOS[TV.CAMPOS.index("ctrl_source"):]
              if c not in RELOJES]
    print("")
    print("  %-12s %8s %10s %10s %10s" % ("campo", "no-cero", "min", "max", ""))
    for c in nuevos:
        v = [int(f[c]) for f in filas]
        nz = sum(1 for x in v if x != 0)
        marca = ""
        if nz == 0 and c not in ("razon_fl", "ctrl_source"):
            marca = "*** SIEMPRE CERO"
            fallos.append("campo vacio: %s" % c)
        print("  %-12s %8d %10d %10d %10s" % (c, nz, min(v), max(v), marca))

    print("")
    print("  3) invertir las escalas y recuperar el original")
    # La tolerancia es MEDIA unidad de escala mas un epsilon: eso es la
    # resolucion del redondeo y nada mas. La primera version de este test
    # exigia estrictamente menos de media unidad y contaba 48 "desviaciones"
    # que eran el limite exacto del round(). El test estaba mal, no el codigo.
    mal = 0
    for f, (a, u) in zip(filas, ult):
        if not u or u.get("target") is None:
            continue
        for campo, clave, esc in (("tg_x", None, 10), ("psi", "psi", 10),
                                  ("ang_viejo", "ang_viejo", 10),
                                  ("e_pos", "e_pos", 1000)):
            orig = u["target"][0] if clave is None else u.get(clave, 0)
            if abs(int(f[campo]) / float(esc) - orig) > 0.5 / esc + 1e-9:
                mal += 1
    print("     tg_x, psi, ang_viejo, e_pos:  %d desviaciones fuera de media"
          " unidad de escala -> %s" % (mal, "OK" if mal == 0 else "*** MAL"))
    if mal:
        fallos.append("escalas no invertibles")

    print("")
    print("  coherencia interna: t_pos + t_psi tiene que dar ang_env")
    mal2 = 0
    n2 = 0
    for f in filas:
        if int(f["ley"]) != 1:
            continue
        s = (int(f["t_pos"]) + int(f["t_psi"])) / 10.0
        s = max(-90.0, min(90.0, s))
        n2 += 1
        if abs(s - int(f["ang_env"])) > 1.0:      # ang_env va redondeado a 1
            mal2 += 1
    print("     %d frames con ley=stanley, %d incoherentes -> %s"
          % (n2, mal2, "OK" if mal2 == 0 else "*** MAL"))
    if mal2:
        fallos.append("t_pos + t_psi no reproduce ang_env")

    print("")
    print("=" * 92)
    print("  4) VISION APAGADA - el CSV no cambia de forma")
    print("=" * 92)
    print("")
    if os.path.exists(SALIDA):
        os.remove(SALIDA)
    vl2 = cargar_vl(False, False)
    import nuevo_code_v2 as v2mod
    tv2 = TV.TelemetriaVision(SALIDA)
    ult2 = correr(vl2, tv2, v2mod)
    filas2, lineas2 = leer(SALIDA)
    largos2 = set(len(l.rstrip("\n").split(",")) for l in lineas2[1:])
    nz2 = sum(1 for f in filas2 for c in nuevos if int(f[c]) != 0)
    print("  ACTIVA = %s   %d filas   largos %s   campos nuevos no-cero: %d"
          % (vl2.ACTIVA, len(filas2), sorted(largos2), nz2))
    ok4 = largos2 == {len(TV.CAMPOS)} and nz2 == 0
    print("  -> %s" % ("OK" if ok4 else "*** MAL"))
    if not ok4:
        fallos.append("apagada cambia el CSV")

    if os.path.exists(SALIDA):
        os.remove(SALIDA)
    print("")
    print("=" * 92)
    print("  %s" % ("TODO OK" if not fallos else "*** FALLAN: " + ", ".join(fallos)))
    print("=" * 92)
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(main())
