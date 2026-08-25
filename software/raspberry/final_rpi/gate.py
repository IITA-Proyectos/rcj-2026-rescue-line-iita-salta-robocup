# -*- coding: utf-8 -*-
"""
GATE - el control positivo endurecido. El anterior estaba ciego.

POR QUE EXISTE
--------------
La auditoria de V1 encontro que el gate que use en TODOS los A/B de esta
investigacion no ve lo que dice ver. Con una variante de slew K=20:

    hist_exito        100/100   PASA
    lineal_positivo    73/73    PASA
    steer maximo       +89,4    PASA

y sin embargo el steer MINIMO dentro de lineal f800-872 se desplomaba de +85,61
a -64,7. **Una inversion de signo completa adentro del control positivo, y el
gate la dejo pasar.**

Contar targets y mirar el maximo no alcanza. Lo que sigue era mi conclusion, y
la seccion siguiente la desmiente con una medicion: LEER LAS DOS.

CORRECCION DE UN NUMERO QUE VENIA REPITIENDO
--------------------------------------------
Vengo escribiendo "conservar el +87" en cada commit. El banco mide en esa
ventana un rango de [+85,61 , +89,44], con +87,64 en f871. El +87 es el valor de
UN frame, no el maximo. Un gate escrito contra "+87" chequea un numero que el
banco no produce. Aca se escribe como RANGO.

LO QUE MEDI DESPUES, Y QUE DESMIENTE LA MITAD DE ESTE ARCHIVO
------------------------------------------------------------
Antes de aplicar el gate endurecido verifique su premisa: exigir "cero
inversiones dentro del control" solo vale si esos tramos son curvas de UN SOLO
SENTIDO. Medi el yaw real por correlacion de fase sobre el fondo lejano, que no
depende de ninguna vision candidata:

    hist_exito        giro neto  -41,5 deg   |giro| bruto 213,5   8 cambios
    lineal_positivo   giro neto  +12,0 deg   |giro| bruto 100,2   9 cambios
    hist_falla        giro neto  -20,6 deg   |giro| bruto 231,1  17 cambios

EN LOS DOS CONTROLES EL ROBOT CAMBIA DE SENTIDO VARIAS VECES. Exigir cero
inversiones en el comando es exigir algo que la trayectoria fisica NO TIENE.

Y el criterio de RANGO [+80,+90] tampoco se sostiene: lo escribi a partir de un
rango observado que probablemente sea el de una variante concreta, asi que estaba
ajustado al resultado que queria validar. Eso es circular.

QUE QUEDA EN PIE, ENTONCES
--------------------------
  * el conteo de targets: valido y sigue vigente
  * el maximo de steer en lineal: valido, ahi hay un giro extremo correcto
  * cero inversiones: RETIRADO, la trayectoria real oscila
  * rango cerrado: RETIRADO, era circular

Los dos criterios retirados se dejan como AVISO -se imprimen pero no reprueban-
porque el ejemplo que motivo todo sigue siendo real: una variante llevo el steer
minimo de lineal de +85,6 a -64,7 y el gate viejo no dijo nada. Un -64,7 en un
tramo cuyo giro neto es +12 merece que alguien lo mire, aunque no sea causal para
reprobar automaticamente.

Y HAY UN HALLAZGO MAS GRANDE ADENTRO DE ESTO
--------------------------------------------
Los tramos que usamos como "control positivo" tienen 213 y 100 grados de giro
BRUTO para 41 y 12 de giro NETO. O sea que el robot ya venia oscilando fuerte
adentro de las corridas que consideramos exitosas. Son controles mas debiles de
lo que creiamos: dicen "no perdio la linea", no dicen "manejo bien".

EL GATE
-------
  1. hist.avi   f580-679  -> 100/100 targets
  2. lineal.avi f800-872  ->  73/73 targets
  3. lineal f800-872 -> maximo de steer >= +89 (el giro extremo correcto)
  4. AVISOS que se imprimen y NO reprueban: inversiones dentro de la ventana, y
     steer fuera de [+80,+90] en lineal
  5. toda variante corre DESDE EL FRAME 0, nunca desde `--desde`: el estado
     (prev_target, prev_heading, deques) se arrastra y arrancar en el medio
     mide otra cosa

USO
---
    import gate
    ok, informe = gate.evaluar(lambda ruta, fps, d, h: serie_de_mi_variante(...))
    print(informe)
"""

import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

DEAD = 10.0          # banda muerta para contar signos, igual que ab_v2_v3_v4

CONTROLES = [
    dict(nombre="hist_exito", video="hist.avi", fps=100.0 / 3.0,
         desde=580, hasta=679, targets=100,
         rango=None, sin_inversiones=False, aviso_inversiones=True),
    dict(nombre="lineal_positivo", video="lineal.avi", fps=100.0 / 3.0,
         desde=800, hasta=872, targets=73,
         rango=None, sin_inversiones=False, minimo_max=89.0,
         # AVISO, no reprueba: ver el bloque de arriba
         aviso_rango=(80.0, 90.0), aviso_inversiones=True),
]


def _inversiones(steers):
    """Cambios de signo con banda muerta. Misma definicion que el banco."""
    ult = None
    n = 0
    for s in steers:
        if s is None:
            continue
        g = 1 if s > DEAD else (-1 if s < -DEAD else None)
        if g is None:
            continue
        if ult is not None and g != ult:
            n += 1
        ult = g
    return n


def evaluar(serie_fn, verbose=True):
    """serie_fn(ruta, fps, desde, hasta) -> lista de (target, steer, estado).

    OBLIGACION DEL LLAMADOR: procesar DESDE EL FRAME 0 y recortar a
    [desde, hasta] al final. Si arranca en `desde`, el estado arrastrado no es
    el mismo y el control no vale.
    """
    lineas = []
    todo_ok = True
    for c in CONTROLES:
        ruta = os.path.join(AQUI, c["video"])
        if not os.path.exists(ruta):
            lineas.append("  %-18s FALTA EL VIDEO" % c["nombre"])
            todo_ok = False
            continue
        serie = serie_fn(ruta, c["fps"], c["desde"], c["hasta"])
        st = [s for _t, s, _e in serie]
        con = sum(1 for t, _s, _e in serie if t is not None)
        vals = [s for s in st if s is not None]

        fallos = []
        if con < c["targets"]:
            fallos.append("targets %d/%d" % (con, c["targets"]))
        avisos = []
        if c.get("sin_inversiones"):
            inv = _inversiones(st)
            if inv:
                fallos.append("INVERSIONES DENTRO DEL CONTROL: %d" % inv)
        elif c.get("aviso_inversiones"):
            inv = _inversiones(st)
            if inv:
                avisos.append("inversiones %d" % inv)
        if c.get("aviso_rango") and vals:
            lo, hi = c["aviso_rango"]
            fu = [v for v in vals if not (lo <= v <= hi)]
            if fu:
                avisos.append("fuera de [%.0f,%.0f] %d frames min %.1f"
                              % (lo, hi, len(fu), min(fu)))
        if c.get("rango") and vals:
            lo, hi = c["rango"]
            fuera = [v for v in vals if not (lo <= v <= hi)]
            if fuera:
                fallos.append("fuera de [%.0f,%.0f]: %d frames, min %.1f max %.1f"
                              % (lo, hi, len(fuera), min(fuera), max(fuera)))
        if c.get("minimo_max") and vals and max(vals) < c["minimo_max"]:
            fallos.append("maximo %.1f < %.1f" % (max(vals), c["minimo_max"]))

        ok = not fallos
        todo_ok &= ok
        lineas.append("  %-18s %s  %d/%d targets   steer [%s, %s]%s"
                      % (c["nombre"], "PASA" if ok else "*** FALLA",
                         con, c["targets"],
                         "%.1f" % min(vals) if vals else "--",
                         "%.1f" % max(vals) if vals else "--",
                         ("   " + " | ".join(fallos)) if fallos else
                         ("   aviso: " + " | ".join(avisos)) if avisos else ""))
    informe = "\n".join(lineas)
    if verbose:
        print("  GATE  (reprueba por targets y por el maximo; el resto son avisos)")
        print(informe)
        print("  %s" % ("GATE OK" if todo_ok else "*** GATE FALLA"))
    return todo_ok, informe
