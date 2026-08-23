# -*- coding: utf-8 -*-
"""BANCO DE INSTRUMENTACION de NUEVO CODE V2/V3/V4. NO TOCA EL ROBOT.

Para que existe
---------------
La auditoria del 23-ago dejo una conclusion: no se puede saber QUE CAPA tomo la
decision equivocada, porque el CSV de V4 no exporta los intermedios y porque las
metricas no miran el borde de la perdida.

Este banco NO cambia la percepcion. Envuelve V2/V3/V4 y saca a la luz lo que ya
pasa adentro. Si al correrlo los numeros de V4 cambian, el banco esta mal.

LAS CINCO ETAPAS. No son cuatro
-------------------------------
Adentro de V2 hay DOS limitadores distintos y consecutivos, no uno:

  1. target_raw        `nuevo_code_v2.py:305`   el punto geodesico a LOOKAHEAD
  2. target_cap        `nuevo_code_v2.py:352-364`  cap de continuidad 16/12/20 px
  3. target_lowproj    `nuevo_code_v2.py:366-372`  proyeccion a last_good_target
  4. target_branch     `nuevo_code_v3.py:196-283`  guard de rama (signo)
  5. target_final      `nuevo_code_v4.py:53-120`   guard espacial 24/30 px

La 3 es la que V4 llama `target_geometric` (`nuevo_code_v4.py:146,156`), o sea
que lo que el .md llama "el target geometrico" YA paso por dos limitadores.

Como se instrumenta sin tocar el codigo
---------------------------------------
* Las etapas 3, 4 y 5 ya estan en el dict que devuelve `NuevoCodeV4.step`
  (`nuevo_code_v4.py:156-158`). Solo hay que escribirlas.
* La etapa 1 se captura interceptando `path_target`, que devuelve `res["target"]`
  antes de cualquier cap (`nuevo_code_v2.py:305-314`). Se envuelve el metodo, no
  se lo reescribe.
* La etapa 2 hay que REPRODUCIRLA, porque es una variable local que no sale de
  `step`. Y por eso el banco SE AUTOVALIDA: en todo frame donde `low_proj` no
  disparo, la etapa 2 reproducida tiene que ser IDENTICA a `target_geometric`.
  El porcentaje de coincidencia se imprime. Si no da 100 %, la reproduccion esta
  mal y nada de lo que sigue vale.

Que se mide en el borde de la perdida
-------------------------------------
`nuevo_code_v4.py:316-318` pone `prev = None` cuando no hay target, asi que el
salto de reacquisicion nunca entra en `max_accepted_jump`. Y
`SpatialTargetGuard.step:81-83` acepta esa primera evidencia SIN limite. El
unico salto sin limitar es tambien el unico sin medir. Aca cada perdida es un
EVENTO con su propia fila.

Distancia geodesica
-------------------
`nuevo_code_v4.py:100-116` usa una bola euclidea: dos ramas distintas pueden
estar a pocos px alrededor de una bifurcacion. Este banco calcula ademas la
distancia GEODESICA sobre el esqueleto entre el target previo y el nuevo,
reusando el Dijkstra de `nuevo_code_v2.py:144`. Si es infinita, el target
cambio de rama aunque la euclidea sea chica.

Uso
---
    python trazar.py --casos            # los 4 casos de control
    python trazar.py --todos            # los 11 videos
    python trazar.py hist.avi --desde 1354 --hasta 1490 --tag falla
    python trazar.py --code-dir C:/otra/carpeta --todos
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

# --- videos --------------------------------------------------------------
CASOS = [
    ("hist_exito",      "hist.avi",    33.3,  580,  679, "EXITO"),
    ("hist_falla",      "hist.avi",    33.3, 1354, 1490, "FALLA"),
    ("lineal_positivo", "lineal.avi",  33.3,  800,  872, "CONTROL POSITIVO"),
    ("video_4_manual",  "video_4.avi", 20.0,    0, 10 ** 9, "TEACHER TRACE"),
]
TODOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi", "seguir.avi",
         "rumbo.avi", "a.avi", "roi_auto.avi", "con_planner.avi",
         "con_planner2.avi", "video_4.avi"]


def fps_de(v):
    """20 para video_4, que es crudo. 33,3 para los paneles.

    Los AVI declaran 20,0 los dos porque el VideoWriter del grabador lo tiene
    fijo (HANDOFF regla de metodo 4). NO leer cap.get(CAP_PROP_FPS): miente.
    """
    return 20.0 if "video_4" in os.path.basename(v) else 100.0 / 3.0


# --- carga de la arquitectura vigente ------------------------------------
def cargar(code_dir):
    ruta = os.path.join(code_dir, "nuevo_code_v4.py")
    if not os.path.exists(ruta):
        raise IOError(
            "no esta nuevo_code_v4.py en %s. Pasar --code-dir." % code_dir)
    sp = importlib.util.spec_from_file_location("nuevo_code_v4", ruta)
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


# ---------------------------------------------------------------------------
#  EL TRAZADOR
# ---------------------------------------------------------------------------

class Trazador(object):
    """Envuelve NuevoCodeV4 y saca los intermedios. No modifica la percepcion."""

    def __init__(self, v4, v3, v2, fps):
        self.v4, self.v3, self.v2 = v4, v3, v2
        self.fps = float(fps)
        self.tr = v4.NuevoCodeV4(fps)
        self.per = self.tr.per

        # intercepta path_target para quedarse con el target ANTES de los caps
        self._raw = None
        self._orig_pt = self.per.path_target

        def espia(comp, mode):
            sk, res = self._orig_pt(comp, mode)
            self._raw = None if res is None else tuple(res["target"])
            return sk, res
        self.per.path_target = espia

        # edades y trazas
        self.prev_target_ant = None
        self.last_good_ant = None
        self.edad_prev = 0
        self.edad_lg = 0
        self.comp_ant = None
        self.rama_id = 0
        self.cap_ok = 0
        self.cap_total = 0

    # -- reproduccion de la etapa 2, la unica que no sale de step ----------
    def _cap_v2(self, raw, prev_target, estado, sk):
        """Copia literal de `nuevo_code_v2.py:352-364`. Se valida sola."""
        if prev_target is None or raw is None:
            return raw, "sin_prev", None
        jump = math.hypot(raw[0] - prev_target[0], raw[1] - prev_target[1])
        cap = (16 if estado in ("HIGH", "MEDIUM")
               else 12 if estado in ("LOW", "LOW_FORWARD") else 20)
        if jump <= cap:
            return raw, "bajo_cap", jump
        ys, xs = np.nonzero(sk)
        dp = np.sqrt((xs - prev_target[0]) ** 2 + (ys - prev_target[1]) ** 2)
        poss = np.where(dp <= cap)[0]
        if len(poss):
            j = poss[np.argmin((xs[poss] - raw[0]) ** 2 + (ys[poss] - raw[1]) ** 2)]
            return (float(xs[j]), float(ys[j])), "capeado", jump
        # `if len(poss):` de v2:361 -> si no hay ninguno, NO capea. Falla abierta.
        return raw, "FALLA_ABIERTA", jump

    # -- distancia geodesica sobre el esqueleto ----------------------------
    def _geodesica(self, sk, a, b, max_proy=6.0):
        """Distancia a lo largo del esqueleto entre dos puntos.

        Los dos se proyectan al nodo mas cercano del esqueleto ACTUAL. Si la
        proyeccion pasa de `max_proy` px, el punto no esta sobre esta centerline
        y se devuelve None (no es comparable). Si estan en componentes distintas
        del grafo, se devuelve inf: cambio de rama.
        """
        if a is None or b is None or sk is None:
            return None, None
        ys, xs = np.nonzero(sk)
        if xs.size == 0:
            return None, None
        da = (xs - a[0]) ** 2 + (ys - a[1]) ** 2
        db = (xs - b[0]) ** 2 + (ys - b[1]) ** 2
        ia, ib = int(np.argmin(da)), int(np.argmin(db))
        pa, pb = math.sqrt(da[ia]), math.sqrt(db[ib])
        if pa > max_proy or pb > max_proy:
            return None, max(pa, pb)
        pts, adj, _deg = self.v2.graph_from_skeleton(sk)
        idx = {(int(y), int(x)): i for i, (y, x) in enumerate(pts)}
        na = idx.get((int(ys[ia]), int(xs[ia])))
        nb = idx.get((int(ys[ib]), int(xs[ib])))
        if na is None or nb is None:
            return None, max(pa, pb)
        dist, _prev = self.v2.dijkstra(adj, na)
        d = float(dist[nb])
        return (d if np.isfinite(d) else float("inf")), max(pa, pb)

    # -- identidad de rama por solape --------------------------------------
    def _rama(self, comp):
        if comp is None:
            self.comp_ant = None
            return -1, 0.0
        c = comp > 0
        sol = 0.0
        if self.comp_ant is not None:
            inter = float((c & self.comp_ant).sum())
            union = float((c | self.comp_ant).sum())
            sol = inter / union if union else 0.0
        if sol < 0.25:
            self.rama_id += 1
        self.comp_ant = c
        return self.rama_id, sol

    # -- un frame -----------------------------------------------------------
    def paso(self, g):
        prev_target = self.per.prev_target
        last_good = self.per.last_good_target
        self._raw = None

        r = self.tr.step(g)

        raw = self._raw
        sk = r.get("skel")
        estado = r.get("state")

        t_cap, cap_via, cap_jump = self._cap_v2(raw, prev_target, estado, sk)
        t_geo = r.get("target_geometric")     # = post low_proj (v4:146,156)
        t_br = r.get("target_branch")
        t_fin = r.get("target")
        reason = r.get("reason", "") or ""

        # AUTOVALIDACION: sin low_proj, la etapa 2 reproducida tiene que ser
        # identica a lo que V2 devolvio.
        if t_geo is not None and t_cap is not None and "low_proj" not in reason:
            self.cap_total += 1
            if (abs(t_cap[0] - t_geo[0]) < 1e-6 and abs(t_cap[1] - t_geo[1]) < 1e-6):
                self.cap_ok += 1

        # edades
        if prev_target != self.prev_target_ant:
            self.edad_prev = 0
        else:
            self.edad_prev += 1
        self.prev_target_ant = prev_target
        if last_good != self.last_good_ant:
            self.edad_lg = 0
        else:
            self.edad_lg += 1
        self.last_good_ant = last_good

        rid, sol = self._rama(r.get("comp"))

        euc = None
        geo = None
        proy = None
        if prev_target is not None and t_fin is not None:
            euc = math.hypot(t_fin[0] - prev_target[0], t_fin[1] - prev_target[1])
            geo, proy = self._geodesica(sk, prev_target, t_fin)

        return dict(
            state=estado, mode=r.get("mode", ""), reason=reason,
            raw=raw, cap=t_cap, cap_via=cap_via, cap_jump=cap_jump,
            geo_t=t_geo, br=t_br, fin=t_fin,
            bg=r.get("branch_guard", ""), sg=r.get("spatial_guard", ""),
            heading=r.get("heading"),
            euclidea=euc, geodesica=geo, proyeccion=proy,
            rama=rid, solape=sol,
            edad_prev=self.edad_prev, edad_lg=self.edad_lg,
            prev_target=prev_target, last_good=last_good,
            atan2=self.v2.atan2_actual(g),
        )


# ---------------------------------------------------------------------------
#  CORRIDA Y SALIDA
# ---------------------------------------------------------------------------

CAB = ["frame", "t_s", "state", "mode", "reason",
       "raw_x", "raw_y",
       "cap_x", "cap_y", "cap_via", "cap_jump_px",
       "lowproj_x", "lowproj_y",
       "branch_x", "branch_y", "branch_guard",
       "final_x", "final_y", "spatial_guard",
       "movio_cap_px", "movio_lowproj_px", "movio_branch_px", "movio_spatial_px",
       "euclidea_px", "geodesica_px", "proyeccion_px",
       "rama_id", "solape_rama",
       "edad_prev_target", "edad_last_good",
       "heading_deg", "steer_request_deg", "bearing_real_deg", "atan2_viejo_deg"]


def _d(a, b):
    if a is None or b is None:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _xy(p):
    return ("", "") if p is None else ("%.2f" % p[0], "%.2f" % p[1])


def correr(v4mod, v3mod, v2mod, ruta, fps, desde, hasta, salida_csv):
    W, CENTER = v2mod.W, v2mod.CENTER
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError("no se pudo abrir %s" % ruta)
    tz = Trazador(v4mod, v3mod, v2mod, fps)
    filas = []
    i = 0
    fh = open(salida_csv, "w", newline="", encoding="utf-8")
    wr = csv.writer(fh)
    wr.writerow(CAB)
    try:
        while True:
            ok, fr = cap.read()
            if not ok or i > hasta:
                break
            g = v2mod.frame_pi(fr)
            d = tz.paso(g)                 # el estado se arrastra desde el 0
            if i >= desde:
                fin = d["fin"]
                steer = (None if fin is None else
                         float(np.clip(-90.0 * (fin[0] - CENTER) / (W / 2.0), -90, 90)))
                bearing = (None if fin is None else
                           math.degrees(math.atan2(-(fin[0] - CENTER),
                                                   max(119.0 - fin[1], 1e-6))))
                d["i"] = i
                d["steer"] = steer
                d["bearing"] = bearing
                filas.append(d)
                wr.writerow(
                    [i, "%.3f" % (i / fps), d["state"], d["mode"], d["reason"]]
                    + list(_xy(d["raw"]))
                    + list(_xy(d["cap"])) + [d["cap_via"],
                                             "" if d["cap_jump"] is None else "%.2f" % d["cap_jump"]]
                    + list(_xy(d["geo_t"]))
                    + list(_xy(d["br"])) + [d["bg"]]
                    + list(_xy(d["fin"])) + [d["sg"]]
                    + ["" if _d(d["raw"], d["cap"]) is None else "%.2f" % _d(d["raw"], d["cap"]),
                       "" if _d(d["cap"], d["geo_t"]) is None else "%.2f" % _d(d["cap"], d["geo_t"]),
                       "" if _d(d["geo_t"], d["br"]) is None else "%.2f" % _d(d["geo_t"], d["br"]),
                       "" if _d(d["br"], d["fin"]) is None else "%.2f" % _d(d["br"], d["fin"])]
                    + ["" if d["euclidea"] is None else "%.2f" % d["euclidea"],
                       "" if d["geodesica"] is None else ("inf" if math.isinf(d["geodesica"]) else "%.2f" % d["geodesica"]),
                       "" if d["proyeccion"] is None else "%.2f" % d["proyeccion"],
                       d["rama"], "%.3f" % d["solape"],
                       d["edad_prev"], d["edad_lg"],
                       "" if d["heading"] is None else "%.2f" % d["heading"],
                       "" if steer is None else "%.2f" % steer,
                       "" if bearing is None else "%.2f" % bearing,
                       "%.2f" % d["atan2"]])
            i += 1
    finally:
        cap.release()
        fh.close()
    return filas, tz


def eventos_perdida(filas):
    """Cada perdida es un EVENTO. Es lo que la metrica de V4 no puede ver."""
    ev = []
    ult = None
    ini = None
    for f in filas:
        if f["fin"] is None:
            if ini is None:
                ini = f
            continue
        if ini is not None and ult is not None:
            salto = math.hypot(f["fin"][0] - ult["fin"][0],
                               f["fin"][1] - ult["fin"][1])
            dsteer = (None if (ult["steer"] is None or f["steer"] is None)
                      else f["steer"] - ult["steer"])
            dhead = (None if (ult["heading"] is None or f["heading"] is None)
                     else f["heading"] - ult["heading"])
            ev.append(dict(
                desde=ini["i"], hasta=f["i"] - 1, largo=f["i"] - ini["i"],
                ult=ult["fin"], nuevo=f["fin"], salto=salto,
                dsteer=dsteer, dhead=dhead,
                est_antes=ult["state"], est_despues=f["state"],
                sg=f["sg"], bg=f["bg"],
                rama_antes=ult["rama"], rama_despues=f["rama"],
                edad_lg=f["edad_lg"]))
            ini = None
        elif ini is not None:
            ini = None
        ult = f
    return ev


def informe(nom, etiqueta, filas, tz, ev):
    n = len(filas)
    sin = sum(1 for f in filas if f["fin"] is None)
    print("")
    print("  " + "-" * 76)
    print("  %-18s %-18s  n=%d   sin target %d (%.1f %%)"
          % (nom, etiqueta, n, sin, 100.0 * sin / max(n, 1)))
    val = 100.0 * tz.cap_ok / max(tz.cap_total, 1)
    marca = "OK" if val >= 99.9 else "*** MAL, no usar el resto ***"
    print("      autovalidacion de la etapa 2 (cap de V2): %.1f %% de %d frames  %s"
          % (val, tz.cap_total, marca))

    # cuanto movio cada capa
    print("      %-16s %6s %8s %8s %8s" % ("capa", "actua", "p50 px", "p90 px", "MAX px"))
    for et, a, b in (("2 cap V2", "raw", "cap"),
                     ("3 low_proj", "cap", "geo_t"),
                     ("4 branch V3", "geo_t", "br"),
                     ("5 spatial V4", "br", "fin")):
        ds = [x for x in (_d(f[a], f[b]) for f in filas) if x is not None and x > 0.01]
        if not ds:
            print("      %-16s %6d %8s %8s %8s" % (et, 0, "-", "-", "-"))
            continue
        print("      %-16s %6d %8.1f %8.1f %8.1f"
              % (et, len(ds), np.median(ds), np.percentile(ds, 90), max(ds)))

    fa = sum(1 for f in filas if f["cap_via"] == "FALLA_ABIERTA")
    print("      cap de V2 con FALLA ABIERTA (v2:361 no encuentra punto): %d" % fa)

    # rama: cuando la euclidea es chica pero la geodesica no
    saltos_rama = [f for f in filas
                   if f["euclidea"] is not None and f["euclidea"] <= 24.0
                   and f["geodesica"] is not None and math.isinf(f["geodesica"])]
    print("      cambios de rama INVISIBLES al guard euclideo "
          "(euclidea<=24 px pero geodesica infinita): %d" % len(saltos_rama))

    edades = [f["edad_lg"] for f in filas if f["state"] == "LOW"]
    if edades:
        print("      edad de last_good_target en LOW: p50 %.0f  p90 %.0f  MAX %d frames"
              % (np.median(edades), np.percentile(edades, 90), max(edades)))

    if ev:
        s = [e["salto"] for e in ev]
        print("      EVENTOS DE PERDIDA: %d   salto de reacquisicion px: "
              "p50 %.1f  p90 %.1f  MAX %.1f"
              % (len(ev), np.median(s), np.percentile(s, 90), max(s)))
        print("      de esos, con salto > 24 px (el limite que el guard NO aplica): %d"
              % sum(1 for x in s if x > 24.0))
        print("      %6s %6s %10s %10s %9s %9s %8s" %
              ("frames", "salto", "ult X", "nueva X", "d steer", "d rumbo", "guard"))
        for e in sorted(ev, key=lambda q: -q["salto"])[:5]:
            print("      %6d %6.1f %10s %10s %9s %9s %8s"
                  % (e["largo"], e["salto"],
                     "(%.0f,%.0f)" % e["ult"], "(%.0f,%.0f)" % e["nuevo"],
                     "--" if e["dsteer"] is None else "%+.0f" % e["dsteer"],
                     "--" if e["dhead"] is None else "%+.0f" % e["dhead"],
                     e["sg"]))
    return dict(n=n, sin=sin, ev=ev, fa=fa, rama=len(saltos_rama),
                val=val, val_n=tz.cap_total)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("videos", nargs="*")
    ap.add_argument("--code-dir", default=os.path.join(
        os.path.expanduser("~"), "Downloads"),
        help="carpeta con nuevo_code_v2/v3/v4.py")
    ap.add_argument("--casos", action="store_true")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    ap.add_argument("--tag", default="")
    ap.add_argument("--salida", default=AQUI)
    a = ap.parse_args(argv)

    code_dir = a.code_dir
    if not os.path.exists(os.path.join(code_dir, "nuevo_code_v4.py")):
        if os.path.exists(os.path.join(AQUI, "nuevo_code_v4.py")):
            code_dir = AQUI
    v4, v3, v2 = cargar(code_dir)
    print("")
    print("=" * 80)
    print(" TRAZA DE LAS CINCO ETAPAS DE NUEVO CODE   (banco shadow, no toca el robot)")
    print(" codigo: %s" % code_dir)
    print("=" * 80)

    tareas = []
    if a.casos:
        tareas = [(n, os.path.join(AQUI, v), f, d, h, e)
                  for n, v, f, d, h, e in CASOS]
    elif a.todos:
        tareas = [(v.replace(".avi", ""), os.path.join(AQUI, v), fps_de(v),
                   0, 10 ** 9, "completo") for v in TODOS]
    else:
        for v in a.videos:
            r = v if os.path.exists(v) else os.path.join(AQUI, v)
            nom = os.path.basename(r).replace(".avi", "")
            if a.tag:
                nom += "_" + a.tag
            tareas.append((nom, r, fps_de(r), a.desde, a.hasta, a.tag or "tramo"))
    if not tareas:
        ap.print_help()
        return 2

    tot_ev = []
    malos = []
    for nom, ruta, fps, d, h, et in tareas:
        if not os.path.exists(ruta):
            print("  falta %s" % ruta)
            continue
        out = os.path.join(a.salida, "traza_%s.csv" % nom)
        filas, tz = correr(v4, v3, v2, ruta, fps, d, h, out)
        ev = eventos_perdida(filas)
        r = informe(nom, et, filas, tz, ev)
        tot_ev += ev
        if r["val"] < 99.9:
            malos.append(nom)
        print("      CSV: %s" % os.path.basename(out))

    if tot_ev:
        s = [e["salto"] for e in tot_ev]
        print("")
        print("  " + "=" * 76)
        print("  TOTAL: %d eventos de perdida" % len(tot_ev))
        print("  salto de reacquisicion px: p50 %.1f  p90 %.1f  MAX %.1f"
              % (np.median(s), np.percentile(s, 90), max(s)))
        print("  con salto > 24 px: %d (%.1f %%)"
              % (sum(1 for x in s if x > 24.0),
                 100.0 * sum(1 for x in s if x > 24.0) / len(s)))
        ds = [abs(e["dsteer"]) for e in tot_ev if e["dsteer"] is not None]
        if ds:
            print("  cambio de steer_request a traves de la perdida: "
                  "p50 %.0f  p90 %.0f  MAX %.0f grados"
                  % (np.median(ds), np.percentile(ds, 90), max(ds)))
    if malos:
        print("")
        print("  *** LA AUTOVALIDACION FALLO EN: %s" % ", ".join(malos))
        print("  *** La reproduccion del cap de V2 no coincide. No usar esas trazas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
