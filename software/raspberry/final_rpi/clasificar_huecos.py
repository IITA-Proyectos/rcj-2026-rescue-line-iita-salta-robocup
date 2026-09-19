# -*- coding: utf-8 -*-
"""QUIEN ABRE EL HUECO, y la percepcion de ese frame era buena o mala.

Hipotesis de ChatGPT (issue #138, investigacion independiente 1)
---------------------------------------------------------------
"278 reacquisiciones" mezcla tres fenomenos. El 75 % de los huecos NO los abre
la percepcion perdiendo la linea: los abre un GUARD al rechazar un target, y
como el rechazo hace `reset()`, el frame siguiente entra sin limite. El guard
fabrica el hueco y despues se desarma para cruzarlo.

Su falsador, textual: si en esos eventos la componente elegida era
visualmente falsa o inutilizable, entonces el `None` del guard es un rechazo
LEGITIMO de percepcion mala, y el problema cambia de "guard autodestructivo" a
"clasificador de confianza insuficiente".

Por que este banco no usa el etiquetado visual que propone
----------------------------------------------------------
ChatGPT propone mirar 20 montajes y etiquetar a mano `correcta / falsa /
ambigua`. Eso es subjetivo, no escala a 278 eventos y no lo puede repetir un
tercero. Se puede contestar la MISMA pregunta con tres criterios objetivos, y
los tres se calculan sobre los 278:

  A  SUPERVIVENCIA. La componente que estaba siguiendo cuando se abrio el hueco,
     sigue existiendo despues? Se rastrea por solape hacia adelante. Si la misma
     cinta seguia ahi, el rechazo tiro evidencia buena.
  B  APOYO FISICO. Esa componente tocaba la fila 119, o sea el robot la tenia
     debajo? Una componente que toca abajo no es "percepcion falsa".
  C  ESTABILIDAD PREVIA. Cuantos frames consecutivos venia siendo la elegida
     antes del rechazo. Una componente estable durante medio segundo no es ruido.

Si A, B y C dicen que la evidencia era buena, la lectura de ChatGPT se sostiene.
Si dicen que era mala, se sostiene su falsador y el problema es otro.

`video_4` se reporta aparte y EXCLUIDO de los agregados: es manual y entre ~515
y ~575 el robot estaba levantado.

Uso
---
    python clasificar_huecos.py
"""

import argparse
import csv
import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))

AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
MANUAL = ["video_4.avi"]
FPS_PANEL = 100.0 / 3.0
SOLAPE_MIN = 0.30
HORIZONTE = 12          # frames que se mira hacia adelante para la supervivencia


def cargar():
    ruta = os.path.join(AQUI, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        ruta = os.path.join(os.path.expanduser("~"), "Downloads", "nuevo_code_v4.py")
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def solape(a, b):
    i = float((a & b).sum())
    if i == 0:
        return 0.0
    return i / max(1.0, float(min(a.sum(), b.sum())))


def correr(v4, v2, ruta, fps):
    """Una pasada guardando lo necesario para mirar hacia adelante despues."""
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = v4.NuevoCodeV4(fps)
    ker = np.ones((3, 3), np.uint8)
    filas = []
    comp_ant = None
    estable = 0
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = v2.frame_pi(fr)
        r = tr.step(g)
        comp = r.get("comp")
        cb = None if comp is None else (comp > 0)
        if cb is not None and comp_ant is not None and solape(cb, comp_ant) >= SOLAPE_MIN:
            estable += 1
        else:
            estable = 0
        # todas las componentes del frame, para poder rastrear hacia adelante
        m = v2.mask_linea(g)
        n, lab, st, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
        comps = [(lab == k) for k in range(1, n)
                 if st[k, cv2.CC_STAT_AREA] >= v2.MIN_AREA]
        filas.append(dict(
            i=i, state=r.get("state"), bg=r.get("branch_guard"),
            sg=r.get("spatial_guard"), tgt=r.get("target"),
            geo=r.get("target_geometric"), br=r.get("target_branch"),
            comp=cb, comps=comps, estable=estable,
            toca=bool(cb is not None and cb[119, :].any()),
            area=0 if cb is None else int(cb.sum())))
        comp_ant = cb
        i += 1
    cap.release()
    return filas, ker


def sobrevive(filas, i0, comp0, ker, horizonte=HORIZONTE):
    """La componente comp0 del frame i0, sigue existiendo hacia adelante?

    Se la rastrea por solape frame a frame. Devuelve cuantos frames sobrevivio y
    si estaba viva en el frame de reenganche.
    """
    if comp0 is None:
        return 0
    ref = comp0
    vivos = 0
    for j in range(i0 + 1, min(i0 + 1 + horizonte, len(filas))):
        ext = cv2.dilate(ref.astype(np.uint8), ker, iterations=4).astype(bool)
        mejor, ms = None, 0.0
        for c in filas[j]["comps"]:
            s = solape(c, ext)
            if s > ms:
                mejor, ms = c, s
        if mejor is None or ms < SOLAPE_MIN:
            break
        ref = mejor
        vivos += 1
    return vivos


def eventos(filas, ker):
    """Un evento por hueco. Se clasifica por QUIEN lo abre en el primer frame
    vacio, exactamente como propuso ChatGPT, y se agregan A, B y C."""
    ev = []
    ult = None
    ini = None
    for f in filas:
        if f["tgt"] is None:
            if ini is None:
                ini = f
            continue
        if ini is not None and ult is not None:
            # quien abrio el hueco: se mira el PRIMER frame vacio
            if ini["state"] == "PERDIDA":
                origen = "LOSS_PERCEPTION"
            elif ini["bg"] in ("REACQ_PENDING", "REJECT_OFF_CENTERLINE"):
                origen = "REJECT_BRANCH"
            elif ini["sg"] in ("REACQ_PENDING", "NO_SKELETON"):
                origen = "REJECT_SPATIAL"
            else:
                origen = "OTRO_" + str(ini["sg"])
            salto = math.hypot(f["tgt"][0] - ult["tgt"][0],
                               f["tgt"][1] - ult["tgt"][1])
            ev.append(dict(
                desde=ini["i"], hasta=f["i"] - 1, largo=f["i"] - ini["i"],
                origen=origen, salto=salto,
                # A supervivencia de la componente que se venia siguiendo
                sobrevive=sobrevive(filas, ult["i"], ult["comp"], ker),
                # B/C en el frame ANTERIOR (contexto)
                tocaba=ult["toca"], area=ult["area"], estable=ult["estable"],
                # --- LO QUE IMPORTA: la evidencia EN EL FRAME DEL RECHAZO ---
                # el guard rechaza AHI. Si en ese frame habia una componente
                # tocando abajo y con un target propuesto, el rechazo tiro
                # evidencia utilizable. Si no habia nada, el rechazo es legitimo.
                rz_toca=ini["toca"], rz_area=ini["area"],
                rz_geo=(ini["geo"] is not None),
                rz_br=(ini["br"] is not None),
                rz_sobrevive=sobrevive(filas, ini["i"], ini["comp"], ker),
                rz_salto_prop=(None if (ini["geo"] is None or ult["tgt"] is None)
                               else math.hypot(ini["geo"][0] - ult["tgt"][0],
                                               ini["geo"][1] - ult["tgt"][1])),
                estado_ini=ini["state"], sg_ini=ini["sg"], bg_ini=ini["bg"]))
            ini = None
        elif ini is not None:
            ini = None
        ult = f
    return ev


def informe(nombre, evs, n_frames):
    print("")
    print("  %-14s %d frames, %d eventos" % (nombre, n_frames, len(evs)))
    por = {}
    for e in evs:
        por.setdefault(e["origen"], []).append(e)
    print("      %-18s %5s %7s %9s | %8s %7s %8s %9s %9s"
          % ("origen del hueco", "n", "%", "salto p50",
             "RZ toca", "RZ geo", "RZ sobrv", "RZ area", "RZ salto"))
    for k in sorted(por, key=lambda t: -len(por[t])):
        g = por[k]
        s = [x["salto"] for x in g]
        sp = [x["rz_salto_prop"] for x in g if x["rz_salto_prop"] is not None]
        print("      %-18s %5d %6.1f%% %9.1f | %7.0f%% %6.0f%% %8.1f %9.0f %9s"
              % (k, len(g), 100.0 * len(g) / max(len(evs), 1), np.median(s),
                 100.0 * np.mean([x["rz_toca"] for x in g]),
                 100.0 * np.mean([x["rz_geo"] for x in g]),
                 np.median([x["rz_sobrevive"] for x in g]),
                 np.median([x["rz_area"] for x in g]),
                 "--" if not sp else "%.0f" % np.median(sp)))
    return por


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--horizonte", type=int, default=HORIZONTE)
    a = ap.parse_args(argv)
    v4, _v3, v2 = cargar()

    print("")
    print("=" * 88)
    print(" QUIEN ABRE EL HUECO  -  contraste de la hipotesis de ChatGPT (#138)")
    print(" sobrevive = frames que la componente seguida sigue existiendo despues")
    print(" tocaba    = %% de eventos donde tocaba la fila 119 al abrirse el hueco")
    print(" estable   = frames que venia siendo la elegida antes del rechazo")
    print("=" * 88)

    tot = []
    filas_csv = []
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            print("  falta %s" % vid)
            continue
        filas, ker = correr(v4, v2, ruta, FPS_PANEL)
        evs = eventos(filas, ker)
        informe(vid.replace(".avi", ""), evs, len(filas))
        for e in evs:
            e["video"] = vid.replace(".avi", "")
        tot += evs
        filas_csv += evs

    print("")
    print("  " + "=" * 84)
    print("  TOTAL SOBRE LOS 10 AUTONOMOS  (video_4 excluido: manual + levantado)")
    por = informe("TOTAL", tot, sum(1 for _ in tot))
    print("")
    print("  DESGLOSE DEL SALTO POR ORIGEN")
    print("      %-18s %6s %8s %8s %8s %10s"
          % ("origen", "n", "p50", "p90", "MAX", ">24 px"))
    for k in sorted(por, key=lambda t: -len(por[t])):
        s = np.array([x["salto"] for x in por[k]])
        print("      %-18s %6d %8.1f %8.1f %8.1f %9d (%.0f%%)"
              % (k, len(s), np.median(s), np.percentile(s, 90), s.max(),
                 (s > 24).sum(), 100.0 * (s > 24).mean()))

    print("")
    print("  VEREDICTO SOBRE EL FALSADOR DE CHATGPT")
    print("  'si la componente era falsa/inutilizable, el rechazo era legitimo'")
    for k in ("REJECT_SPATIAL", "REJECT_BRANCH", "LOSS_PERCEPTION"):
        g = por.get(k, [])
        if not g:
            continue
        buena = [x for x in g
                 if x["rz_toca"] and x["rz_geo"] and x["rz_sobrevive"] >= 3]
        print("      %-18s %d eventos. EN EL FRAME DEL RECHAZO habia una "
              "componente tocando abajo, con target propuesto y sobreviviendo "
              ">=3 frames en %d (%.0f %%)"
              % (k, len(g), len(buena), 100.0 * len(buena) / len(g)))

    out = os.path.join(AQUI, "huecos_clasificados.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["video", "desde", "hasta", "largo", "origen", "salto_px",
                     "sobrevive_frames", "tocaba_fila119", "area_px",
                     "estable_frames",
                     "rz_tocaba_fila119", "rz_area_px", "rz_habia_target_geom",
                     "rz_habia_target_branch", "rz_sobrevive_frames",
                     "rz_salto_propuesto_px",
                     "estado_primer_vacio", "spatial_guard", "branch_guard"])
        for e in filas_csv:
            wr.writerow([e["video"], e["desde"], e["hasta"], e["largo"],
                         e["origen"], "%.2f" % e["salto"], e["sobrevive"],
                         int(e["tocaba"]), e["area"], e["estable"],
                         int(e["rz_toca"]), e["rz_area"], int(e["rz_geo"]),
                         int(e["rz_br"]), e["rz_sobrevive"],
                         "" if e["rz_salto_prop"] is None else "%.1f" % e["rz_salto_prop"],
                         e["estado_ini"], e["sg_ini"], e["bg_ini"]])
    print("")
    print("  CSV: %s" % os.path.basename(out))

    # video_4 aparte, sin entrar en ningun agregado
    ruta = os.path.join(AQUI, "video_4.avi")
    if os.path.exists(ruta):
        filas, ker = correr(v4, v2, ruta, 20.0)
        evs = eventos(filas, ker)
        print("")
        print("  APARTE, NO AGREGADO: video_4 (manual; ~515-575 robot levantado)")
        informe("video_4", evs, len(filas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
