# -*- coding: utf-8 -*-
"""GROUND TRUTH RETROSPECTIVO sobre `video_4.avi`. NO TOCA EL ROBOT.

Que problema resuelve
---------------------
En `video_4` la cinta desaparece 32 frames y NUEVO CODE V4 la reengancha con un
salto de 160 px sobre una imagen de 160 px de ancho, con +171 grados de cambio
en la orden. La pregunta que hay que contestar ANTES de tocar nada es:

    el target perceptual, esta MAL?
    o esta BIEN y lo que esta mal es la politica de reacquisicion o la
    conversion target -> orden?

No es lo mismo, y llevan a arreglos distintos.

`video_4` es el unico material donde se puede contestar, porque Benjamin movio
el robot A MANO por la trayectoria correcta: la cinta que el robot termina
teniendo debajo ES la que habia que seguir.

Como se construye el ground truth
---------------------------------
Se ANCLA en un frame posterior donde la respuesta es inequivoca -la cinta toca
el borde de abajo, una sola componente grande- y se PROPAGA HACIA ATRAS por
solape, frame a frame. Se corre el video al reves: en el frame t, la cinta
correcta es la componente que mas se superpone con la cinta correcta de t+1.

Eso da, para cada frame, una de tres respuestas:

    gt = una componente     la cinta correcta esta visible y es esta
    gt = None               la cinta correcta NO esta visible en este frame
    (antes del ancla)       no aplica

Que gt sea None NO es un fallo del metodo: es el dato. Si la cinta no esta en el
cuadro, no habia nada que seguir, y cualquier target que el tracker produzca ahi
es inventado.

Los cuatro tipos de error que se separan
----------------------------------------
  T1  SELECCION      V4 siguio una componente que NO es la cinta correcta.
  T2  DISCONTINUIDAD V4 siguio la componente correcta y el target salto, pero
                     salto porque la geometria visible cambio de verdad: la
                     cinta no estaba y volvio a entrar. El salto es real, no un
                     error del tracker.
  T3  REACQUISICION  el target salto en el reenganche TENIENDO la cinta correcta
                     visible tambien antes. Ahi si habia continuidad que
                     preservar y no se preservo.
  T4  CONVERSION     el target esta bien pero `steer_request` no representa la
                     direccion hacia el: usa solo X y descarta Y.

El target de referencia se calcula con el MISMO `path_target` de
`nuevo_code_v2.py`, alimentado con la componente correcta. No se inventa una ley
nueva: se le pregunta al codigo que habria hecho si hubiera elegido bien.

Limite que no se puede saltear
------------------------------
Sigue siendo replay de lazo abierto. El ground truth dice cual era la cinta
correcta EN LA IMAGEN. No dice que habria hecho el robot con otro control.

Uso
---
    python groundtruth_v4.py
    python groundtruth_v4.py --ancla 575 --desde 490 --hasta 600 --avi
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

# umbral de solape para decidir "es la misma cinta". Se mide como la fraccion de
# la componente MAS CHICA que queda cubierta, no IoU: la cinta entra al cuadro y
# crece rapido, y el IoU castiga el crecimiento aunque sea el mismo objeto.
SOLAPE_MIN = 0.30
DILATA = 9              # px de tolerancia al movimiento entre frames


def cargar(code_dir):
    ruta = os.path.join(code_dir, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        raise IOError("no esta nuevo_code_v4.py en %s" % code_dir)
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def solape(a, b):
    """Fraccion de la componente mas chica que queda cubierta por la otra."""
    ia = float((a & b).sum())
    if ia == 0:
        return 0.0
    return ia / max(1.0, float(min(a.sum(), b.sum())))


def componentes(v2, g):
    """Todas las componentes de la mascara de V2, como mascaras booleanas."""
    m = v2.mask_linea(g)
    n, lab, st, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
    out = []
    for k in range(1, n):
        if st[k, cv2.CC_STAT_AREA] < v2.MIN_AREA:
            continue
        out.append(dict(k=k, mask=(lab == k), area=int(st[k, cv2.CC_STAT_AREA])))
    return m, out


def anclar(v2, comps):
    """La cinta correcta en un frame ancla: la mayor que toca el borde de abajo.

    Es el unico caso donde la respuesta es inequivoca sin mirar nada mas: si una
    componente toca la fila 119, el robot LA TIENE DEBAJO, y en un teacher trace
    -donde la trayectoria es correcta por construccion- esa es la cinta buena.
    """
    toca = [c for c in comps if c["mask"][119, :].any()]
    if not toca:
        return None
    return max(toca, key=lambda c: c["area"])


def propagar(v2, frames, i0, i1, anclas_min_area=200):
    """gt[i] para todo i en [i0, i1], por propagacion BIDIRECCIONAL.

    Un solo ancla no alcanza: en `video_4` la cinta desaparece 32 frames, y una
    propagacion en una sola direccion no puede cruzar ese hueco -ni deberia,
    porque del otro lado el robot ya se movio mucho-. Entonces:

      * se marca como ANCLA todo frame donde una componente toca la fila 119;
      * desde cada ancla se propaga hacia adelante y hacia atras por solape,
        hasta que se rompe;
      * cada frame se queda con la asignacion de la ancla MAS CERCANA, que es la
        que menos eslabones de propagacion arrastra.

    Los frames a los que no llega ninguna propagacion quedan en None, y eso es
    un dato, no una falla: ahi la cinta correcta no es determinable del video.
    """
    ker = np.ones((3, 3), np.uint8)
    cache = {}

    def comps_de(i):
        if i not in cache:
            cache[i] = componentes(v2, frames[i])[1]
        return cache[i]

    anclas = []
    for i in range(i0, i1 + 1):
        a = anclar(v2, comps_de(i))
        if a is not None and a["area"] >= anclas_min_area:
            anclas.append((i, a["mask"]))
    if not anclas:
        raise ValueError(
            "no hay ningun frame en [%d,%d] con una componente que toque el "
            "borde de abajo. Sin ancla no hay ground truth." % (i0, i1))

    gt = {}
    dist = {}
    for i_a, m_a in anclas:
        for paso in (+1, -1):
            ref = m_a
            i = i_a
            d = 0
            while True:
                if d > 0:
                    cs = comps_de(i)
                    if not cs:
                        break
                    ext = cv2.dilate(ref.astype(np.uint8), ker,
                                     iterations=max(1, DILATA // 2)).astype(bool)
                    mejor, mejor_s = None, 0.0
                    for c in cs:
                        sv = solape(c["mask"], ext)
                        if sv > mejor_s:
                            mejor, mejor_s = c, sv
                    if mejor is None or mejor_s < SOLAPE_MIN:
                        break
                    ref = mejor["mask"]
                if i in dist and dist[i] <= d:
                    pass
                else:
                    gt[i] = ref
                    dist[i] = d
                i += paso
                d += 1
                if i < i0 or i > i1:
                    break
    for i in range(i0, i1 + 1):
        gt.setdefault(i, None)
    return gt, [i for i, _ in anclas]


def target_de_referencia(v2mod, comp_mask, modo, prev_target, prev_entry, prev_heading):
    """Que target habria dado V2 sobre la componente CORRECTA.

    Se instancia un NuevoCodeV2 aparte y se le inyecta la memoria del ground
    truth, para no reimplementar `path_target`.
    """
    if comp_mask is None:
        return None, None, None
    aux = v2mod.NuevoCodeV2(20.0)
    aux.prev_target = prev_target
    aux.prev_entry = prev_entry if prev_entry is not None else (v2mod.CENTER, 119.0)
    aux.prev_heading = prev_heading or 0.0
    comp = (comp_mask.astype(np.uint8)) * 255
    ext, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if ext:
        lleno = np.zeros_like(comp)
        cv2.drawContours(lleno, ext, -1, 255, thickness=-1)
        comp = lleno
    try:
        _sk, res = aux.path_target(comp, modo)
    except Exception:
        return None, None, None
    if res is None:
        return None, None, None
    return tuple(res["target"]), tuple(res["start"]), res["heading"]


def clasificar(f):
    """Los cuatro tipos. Un frame puede tener mas de uno."""
    t = []
    if f["gt"] is None:
        if f["v4"] is not None:
            t.append("T1_INVENTADO")     # no habia cinta y V4 dio target igual
        return t
    if f["v4"] is None:
        t.append("T0_SIN_ORDEN")         # habia cinta y V4 no dio target
        return t
    if f["sol_v4_gt"] < SOLAPE_MIN:
        t.append("T1_SELECCION")
    if f["salto"] is not None and f["salto"] > 24.0:
        t.append("T2_DISCONTINUIDAD" if f["gt_ant_none"] else "T3_REACQUISICION")
    if f["dif_conv"] is not None and f["dif_conv"] > 20.0:
        t.append("T4_CONVERSION")
    return t


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--code-dir", default=os.path.join(
        os.path.expanduser("~"), "Downloads"))
    ap.add_argument("--video", default=os.path.join(AQUI, "video_4.avi"))
    ap.add_argument("--ancla", type=int, default=575,
                    help="solo fija el tope del rango; las anclas se detectan solas")
    ap.add_argument("--desde", type=int, default=490)
    ap.add_argument("--hasta", type=int, default=600)
    ap.add_argument("--avi", action="store_true", help="ademas, video de evidencia")
    a = ap.parse_args(argv)

    code_dir = a.code_dir
    if not os.path.exists(os.path.join(code_dir, "nuevo_code_v4.py")):
        if os.path.exists(os.path.join(AQUI, "nuevo_code_v4.py")):
            code_dir = AQUI
    v4, v3, v2 = cargar(code_dir)
    W, H, CENTER = v2.W, v2.H, v2.CENTER

    # --- cargar los frames del tramo (mas margen para el ancla) -----------
    cap = cv2.VideoCapture(a.video)
    if not cap.isOpened():
        raise IOError(a.video)
    frames = []
    i = 0
    tope = max(a.hasta, a.ancla) + 2
    while True:
        ok, fr = cap.read()
        if not ok or i > tope:
            break
        frames.append(v2.frame_pi(fr))
        i += 1
    cap.release()
    if a.ancla >= len(frames):
        raise ValueError("el ancla %d esta fuera del video (%d frames)"
                         % (a.ancla, len(frames)))

    print("")
    print("=" * 82)
    print(" GROUND TRUTH RETROSPECTIVO   %s" % os.path.basename(a.video))
    print(" ancla en el frame %d, propagacion hacia atras por solape >= %.2f"
          % (a.ancla, SOLAPE_MIN))
    print("=" * 82)

    i0 = max(0, a.desde - 30)
    i1 = min(len(frames) - 1, max(a.hasta, a.ancla))
    gt, anclas = propagar(v2, frames, i0, i1)
    print("  anclas (frames con la cinta tocando el borde de abajo): %d de %d"
          % (len(anclas), i1 - i0 + 1))

    # --- correr V4 desde el frame 0 para que la memoria llegue viva -------
    tr = v4.NuevoCodeV4(20.0)
    filas = []
    gt_prev_t = gt_prev_e = None
    gt_prev_h = 0.0
    gt_ant = None
    v4_ant = None
    for i in range(0, min(a.hasta, len(frames) - 1) + 1):
        g = frames[i]
        r = tr.step(g)
        if i < a.desde:
            if i in gt and gt[i] is not None:
                gt_ant = gt[i]
            continue
        gmask = gt.get(i)
        modo = "NEAR" if (gmask is not None and gmask[119, :].any()) else "AHEAD"
        gt_t, gt_s, gt_h = target_de_referencia(
            v2, gmask, modo, gt_prev_t, gt_prev_e, gt_prev_h)
        if gt_t is not None:
            gt_prev_t, gt_prev_e, gt_prev_h = gt_t, gt_s, gt_h

        tv4 = r.get("target")
        comp_v4 = r.get("comp")
        sol = 0.0
        if gmask is not None and comp_v4 is not None:
            sol = solape(comp_v4 > 0, gmask)

        salto = None
        if tv4 is not None and v4_ant is not None:
            salto = math.hypot(tv4[0] - v4_ant[0], tv4[1] - v4_ant[1])

        steer = (None if tv4 is None else
                 float(np.clip(-90.0 * (tv4[0] - CENTER) / (W / 2.0), -90, 90)))
        bearing = (None if tv4 is None else
                   math.degrees(math.atan2(-(tv4[0] - CENTER),
                                           max(119.0 - tv4[1], 1e-6))))
        dif = None if steer is None else abs(steer - bearing)

        # error del target de V4 contra el de referencia
        err_t = None
        if tv4 is not None and gt_t is not None:
            err_t = math.hypot(tv4[0] - gt_t[0], tv4[1] - gt_t[1])

        f = dict(i=i, gt=gmask, v4=tv4, gt_t=gt_t, sol_v4_gt=sol,
                 salto=salto, dif_conv=dif, err_t=err_t,
                 gt_ant_none=(gt_ant is None), state=r.get("state"),
                 mode=r.get("mode", ""), sg=r.get("spatial_guard", ""),
                 bg=r.get("branch_guard", ""), steer=steer, bearing=bearing,
                 heading=r.get("heading"), gt_h=gt_h)
        f["tipos"] = clasificar(f)
        filas.append(f)
        if tv4 is not None:
            v4_ant = tv4
        else:
            v4_ant = None
        gt_ant = gmask

    # --- CSV ---------------------------------------------------------------
    out = os.path.join(AQUI, "groundtruth_video_4.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["frame", "state", "mode", "spatial_guard",
                     "gt_visible", "gt_area",
                     "gt_target_x", "gt_target_y",
                     "v4_target_x", "v4_target_y",
                     "solape_v4_gt", "error_target_px", "salto_v4_px",
                     "steer_request_deg", "bearing_real_deg", "dif_conversion_deg",
                     "tipos"])
        for f in filas:
            wr.writerow([
                f["i"], f["state"], f["mode"], f["sg"],
                int(f["gt"] is not None),
                "" if f["gt"] is None else int(f["gt"].sum()),
                "" if f["gt_t"] is None else "%.2f" % f["gt_t"][0],
                "" if f["gt_t"] is None else "%.2f" % f["gt_t"][1],
                "" if f["v4"] is None else "%.2f" % f["v4"][0],
                "" if f["v4"] is None else "%.2f" % f["v4"][1],
                "%.3f" % f["sol_v4_gt"],
                "" if f["err_t"] is None else "%.2f" % f["err_t"],
                "" if f["salto"] is None else "%.2f" % f["salto"],
                "" if f["steer"] is None else "%.2f" % f["steer"],
                "" if f["bearing"] is None else "%.2f" % f["bearing"],
                "" if f["dif_conv"] is None else "%.2f" % f["dif_conv"],
                "|".join(f["tipos"])])

    # --- informe -----------------------------------------------------------
    n = len(filas)
    vis = sum(1 for f in filas if f["gt"] is not None)
    print("")
    print("  frames analizados %d  (%d..%d)" % (n, filas[0]["i"], filas[-1]["i"]))
    print("  la cinta correcta esta VISIBLE en %d (%.1f %%), y NO visible en %d"
          % (vis, 100.0 * vis / n, n - vis))
    tramos = []
    ini = None
    for f in filas:
        if f["gt"] is None and ini is None:
            ini = f["i"]
        elif f["gt"] is not None and ini is not None:
            tramos.append((ini, f["i"] - 1))
            ini = None
    if ini is not None:
        tramos.append((ini, filas[-1]["i"]))
    if tramos:
        print("  tramos sin cinta correcta visible: " +
              ", ".join("%d-%d (%d f)" % (x, y, y - x + 1) for x, y in tramos))

    cnt = {}
    for f in filas:
        for t in f["tipos"]:
            cnt[t] = cnt.get(t, 0) + 1
    print("")
    print("  CLASIFICACION DE ERRORES")
    if not cnt:
        print("      ninguno")
    for k in ("T0_SIN_ORDEN", "T1_INVENTADO", "T1_SELECCION",
              "T2_DISCONTINUIDAD", "T3_REACQUISICION", "T4_CONVERSION"):
        print("      %-18s %4d" % (k, cnt.get(k, 0)))

    err = [f["err_t"] for f in filas if f["err_t"] is not None]
    if err:
        print("")
        print("  ERROR DEL TARGET DE V4 CONTRA EL DE REFERENCIA (solo donde hay gt)")
        print("      n=%d   p50 %.1f px   p90 %.1f px   MAX %.1f px"
              % (len(err), np.median(err), np.percentile(err, 90), max(err)))
    dc = [f["dif_conv"] for f in filas if f["dif_conv"] is not None]
    if dc:
        print("  DIFERENCIA steer_request CONTRA bearing real")
        print("      n=%d   p50 %.1f gr   p90 %.1f gr   MAX %.1f gr"
              % (len(dc), np.median(dc), np.percentile(dc, 90), max(dc)))

    print("")
    print("  FRAMES CON ALGUN TIPO MARCADO")
    print("      %5s %-11s %-9s %7s %7s %8s %8s  %s"
          % ("frame", "estado", "guard", "sol", "err px", "steer", "bearing", "tipos"))
    for f in filas:
        if not f["tipos"]:
            continue
        print("      %5d %-11s %-9s %7.2f %7s %8s %8s  %s"
              % (f["i"], f["state"], f["sg"], f["sol_v4_gt"],
                 "--" if f["err_t"] is None else "%.1f" % f["err_t"],
                 "--" if f["steer"] is None else "%+.0f" % f["steer"],
                 "--" if f["bearing"] is None else "%+.0f" % f["bearing"],
                 "|".join(f["tipos"])))
    print("")
    print("  CSV: %s" % os.path.basename(out))

    # --- video de evidencia -----------------------------------------------
    if a.avi:
        E = 4
        CW, CH = W * E, H * E
        vw = cv2.VideoWriter(os.path.join(AQUI, "groundtruth_video_4.avi"),
                             cv2.VideoWriter_fourcc(*"MJPG"), 20.0,
                             (CW * 2, CH + 120))
        if not vw.isOpened():
            print("  *** no se pudo abrir el VideoWriter, no se escribe el AVI")
        else:
            for f in filas:
                g = frames[f["i"]]
                pan = np.zeros((H, W, 3), np.uint8)
                if f["gt"] is not None:
                    pan[f["gt"]] = (40, 90, 40)
                if f["gt_t"] is not None:
                    cv2.drawMarker(pan, (int(round(f["gt_t"][0])),
                                         int(round(f["gt_t"][1]))),
                                   (90, 255, 90), cv2.MARKER_CROSS, 11, 2)
                if f["v4"] is not None:
                    cv2.drawMarker(pan, (int(round(f["v4"][0])),
                                         int(round(f["v4"][1]))),
                                   (255, 255, 255), cv2.MARKER_TILTED_CROSS, 11, 2)
                cv2.line(pan, (int(round(CENTER)), 0),
                         (int(round(CENTER)), H - 1), (90, 90, 90), 1)
                out_fr = np.zeros((CH + 120, CW * 2, 3), np.uint8)
                out_fr[:CH, :CW] = cv2.resize(g, (CW, CH),
                                              interpolation=cv2.INTER_NEAREST)
                out_fr[:CH, CW:] = cv2.resize(pan, (CW, CH),
                                              interpolation=cv2.INTER_NEAREST)
                cv2.putText(out_fr, "CAMARA", (10, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, .6, (235, 235, 235), 1, cv2.LINE_AA)
                cv2.putText(out_fr, "VERDE = cinta correcta (ground truth) | "
                            "cruz verde = target de referencia | X blanca = target V4",
                            (CW + 10, 22), cv2.FONT_HERSHEY_SIMPLEX, .38,
                            (200, 200, 200), 1, cv2.LINE_AA)
                y0 = CH + 26
                for k, (txt, col) in enumerate([
                    ("frame %d   %s   gt %s" % (
                        f["i"], f["state"],
                        "VISIBLE" if f["gt"] is not None else "NO VISIBLE"),
                     (235, 235, 235)),
                    ("steer_request %s   bearing real %s   dif %s" % (
                        "--" if f["steer"] is None else "%+.0f" % f["steer"],
                        "--" if f["bearing"] is None else "%+.0f" % f["bearing"],
                        "--" if f["dif_conv"] is None else "%.0f" % f["dif_conv"]),
                     (120, 230, 255)),
                    (" | ".join(f["tipos"]) if f["tipos"] else "sin error marcado",
                     (80, 80, 255) if f["tipos"] else (140, 200, 140)),
                ]):
                    cv2.putText(out_fr, txt, (10, y0 + 30 * k),
                                cv2.FONT_HERSHEY_SIMPLEX, .52, col, 1, cv2.LINE_AA)
                vw.write(out_fr)
            vw.release()
            print("  AVI: groundtruth_video_4.avi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
