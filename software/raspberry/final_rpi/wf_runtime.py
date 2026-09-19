# -*- coding: utf-8 -*-
"""
WF RUNTIME - cuanto CPU cuesta cada variante del seguimiento de linea.

LA PREGUNTA
-----------
Los videos autonomos son 100/3 = 33,333 fps: 30,00 ms de presupuesto por frame.
Hay tres arquitecturas sobre la mesa y ninguna se comparo NUNCA por costo:

  a) SinBranch          la candidata tal cual (V4 con el branch guard nulo)
  b) CAMINO+MONO        SinBranch + camino principal + monotonia (Coulter 1992)
  c) V1                 airborne_v1_adaptado.py: POI sobre contorno crudo

La Raspberry no esta accesible. El tiempo ABSOLUTO de esta PC no predice el de
la Pi y no se usa para nada. Lo que si se transporta -aproximadamente- es la
RAZON entre variantes corridas sobre el mismo material en la misma maquina.
Eso es lo que este banco mide.

QUE MIDE
--------
  T_algoritmo = preprocess + step   (frame ya disponible -> target listo)
El decode del .avi NO cuenta: en el robot el frame lo trae el hilo de camara.

DOS PASADAS por variante, y no se mezclan:
  LIMPIA         sin perfilador, sin un solo espia puesto. De aca salen los
                 p50/p90/p99/max del titular y las razones entre variantes.
  INSTRUMENTADA  con el perfilador de pila de bench_runtime.py (inclusivo /
                 exclusivo, sin doble conteo). De aca sale el desglose por etapa.
El overhead del perfilador se mide y se reporta.

FIDELIDAD (regla 2 del encargo)
-------------------------------
El shim de CAMINO+MONO re-implementa el selector para poder restringirlo. Con
las dos banderas APAGADAS tiene que devolver EXACTAMENTE el target de la
candidata, frame por frame, en los tres videos. Si hay una sola discrepancia,
aborta. Lo mismo para el shim de poi_component y para la instrumentacion.

poi_component
-------------
BENCH_RUNTIME.md afirma que `r["poi"]` lo lee unicamente `draw_panel` y que
pesaba 6,3-6,7 % del frame. Aca se re-verifica de dos maneras independientes:
  1. estatica: se escanea el fuente y se listan TODAS las lecturas de "poi".
  2. conductual: se anula poi_component y se exige que la serie de targets sea
     identica bit a bit sobre los 10 autonomos (metricas de ab_v2_v3_v4).
Y se cuantifica el ahorro con las dos pasadas.

    python wf_runtime.py
    python wf_runtime.py --reps 5 --hilos 1
"""

import argparse
import importlib.util
import json
import math
import os
import platform
import re
import sys
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB

NS = time.perf_counter_ns
FPS = 100.0 / 3.0
PRESUPUESTO_MS = 1000.0 / FPS          # 30,00 ms exactos

VIDEOS = ["hist.avi", "lineal.avi", "roi_auto.avi"]
WARMUP = 100
LIMITE = None          # solo para --smoke: corta cada video en N frames

# --------------------------------------------------------------------------
# ETAPAS. Union de las de la candidata (bench_runtime.py) y las de V1.
# --------------------------------------------------------------------------
ETAPAS = (
    "decode",                # lectura/decode del .avi        (NO cuenta)
    # ---- candidata SinBranch -------------------------------------------
    "frame_pi",
    "mask_linea",
    "cc_candidates",
    "component_distance",
    "choose_component",
    "fill_contornos",
    "state",
    "skeletonize",
    "graph_from_skeleton",
    "dijkstra",
    "reconstruct",
    "runs_1d",
    "path_target",
    # ---- extras que agrega CAMINO+MONO ---------------------------------
    "camino_extra",          # cadena start -> nodo mas lejano + filtrado
    "mono_extra",            # ancla + test de ancestro
    "shim_resel",            # re-seleccion DUPLICADA que paga solo el shim
    # ---- resto de la candidata -----------------------------------------
    "percepcion_resto",
    "spatial_guard",
    "ctrl",
    "poi_component",
    "v4_resto",
    "curvatura_prod",       # _curvatura() de vision_linea.velocidad()
    # ---- V1 -------------------------------------------------------------
    "v1_frame",
    "v1_mascara",
    "v1_contorno",
    "v1_confianza",
    "v1_poi",
    "v1_interpretar",
    "v1_resto",
)
IDX = dict((e, i) for i, e in enumerate(ETAPAS))
NE = len(ETAPAS)
NO_CUENTAN = ("decode",)

# Clasificacion aproximada interprete-de-Python vs codigo compilado.
# Criterio heredado de BENCH_RUNTIME.md (seccion "Lo que si se aprende").
# Es APROXIMADO: casi toda etapa mezcla numpy con bucles de Python. Sirve para
# anticipar como puede moverse la razon en ARM, no como medida exacta.
PY_PURO = (
    "graph_from_skeleton", "dijkstra", "reconstruct", "runs_1d",
    "path_target", "choose_component",
    "camino_extra", "mono_extra", "shim_resel", "curvatura_prod",
    "v1_contorno", "v1_interpretar",
)


# --------------------------------------------------------------------------
# PERFILADOR de pila (copiado de bench_runtime.py)
# --------------------------------------------------------------------------
class Perfilador(object):
    def __init__(self):
        self.activo = False
        self.pila = []
        self.excl = np.zeros(NE, np.int64)
        self.incl = np.zeros(NE, np.int64)

    def frame_nuevo(self):
        self.excl[:] = 0
        self.incl[:] = 0
        del self.pila[:]

    def entrar(self, i):
        self.pila.append([i, NS(), 0])

    def salir(self):
        i, t0, hijos = self.pila.pop()
        total = NS() - t0
        self.incl[i] += total
        self.excl[i] += total - hijos
        if self.pila:
            self.pila[-1][2] += total


P = Perfilador()


def _in(i):
    if P.activo:
        P.entrar(i)


def _out():
    if P.activo:
        P.salir()


class Buffer(object):
    def __init__(self, cap=8192):
        self.a = np.zeros((cap, NE), np.int64)
        self.n = 0

    def add(self, fila):
        if self.n == self.a.shape[0]:
            self.a = np.concatenate([self.a, np.zeros_like(self.a)], 0)
        self.a[self.n] = fila
        self.n += 1

    def datos(self):
        return self.a[:self.n]


# --------------------------------------------------------------------------
# ESPIAS reversibles (copiados de bench_runtime.py)
# --------------------------------------------------------------------------
_PARCHES = []


def _envolver(orig, i):
    def envoltorio(*a, **k):
        if not P.activo:
            return orig(*a, **k)
        P.entrar(i)
        try:
            return orig(*a, **k)
        finally:
            P.salir()
    envoltorio.__name__ = getattr(orig, "__name__", "espia")
    return envoltorio


def espiar(obj, nombre, etapa, obligatorio=True):
    try:
        orig = getattr(obj, nombre)
    except AttributeError:
        if obligatorio:
            raise
        return False
    try:
        setattr(obj, nombre, _envolver(orig, IDX[etapa]))
    except Exception:
        if obligatorio:
            raise
        return False
    _PARCHES.append((obj, nombre, orig))
    return True


def desespiar():
    while _PARCHES:
        obj, nombre, orig = _PARCHES.pop()
        setattr(obj, nombre, orig)


def instrumentar_candidata(v4, v3, v2):
    faltan = []
    espiar(v2, "frame_pi", "frame_pi")
    espiar(v2, "mask_linea", "mask_linea")
    espiar(v2, "cc_candidates", "cc_candidates")
    espiar(v2, "component_distance", "component_distance")
    espiar(v2, "skeletonize", "skeletonize")
    espiar(v2, "graph_from_skeleton", "graph_from_skeleton")
    espiar(v2, "dijkstra", "dijkstra")
    espiar(v2, "reconstruct", "reconstruct")
    espiar(v2, "runs_1d", "runs_1d")
    espiar(v2.NuevoCodeV2, "path_target", "path_target")
    espiar(v2.NuevoCodeV2, "state", "state")
    espiar(v2.NuevoCodeV2, "step", "percepcion_resto")
    espiar(v3.PercepcionV3, "choose_component", "choose_component")
    espiar(v2.NuevoCodeV2, "choose_component", "choose_component")
    espiar(v3, "poi_component", "poi_component")
    espiar(v4.SpatialTargetGuard, "step", "spatial_guard")
    espiar(v4.ControlPreviewV4, "step", "ctrl")
    espiar(v4.NuevoCodeV4, "step", "v4_resto")
    if not espiar(cv2, "findContours", "fill_contornos", obligatorio=False):
        faltan.append("fill_contornos(findContours)")
    if not espiar(cv2, "drawContours", "fill_contornos", obligatorio=False):
        faltan.append("fill_contornos(drawContours)")
    return faltan


def instrumentar_v1(v1):
    espiar(v1, "frame_de_la_pi", "v1_frame")
    espiar(v1.AirborneV1, "mascara", "v1_mascara")
    espiar(v1.AirborneV1, "seleccionar_contorno", "v1_contorno")
    espiar(v1.AirborneV1, "confianza", "v1_confianza")
    espiar(v1.AirborneV1, "puntos_interes", "v1_poi")
    espiar(v1.AirborneV1, "interpretar", "v1_interpretar")
    espiar(v1.AirborneV1, "paso", "v1_resto")
    return []


# --------------------------------------------------------------------------
# CARGA
# --------------------------------------------------------------------------
def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    sp1 = importlib.util.spec_from_file_location(
        "airborne_v1", os.path.join(AQUI, "airborne_v1_adaptado.py"))
    v1 = importlib.util.module_from_spec(sp1)
    sp1.loader.exec_module(v1)
    return v4, v4.v3, v4.v3.v2, v1


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


# --------------------------------------------------------------------------
# SHIM CAMINO+MONO  (copiado de camino_principal.py, con ganchos de perfilado)
# --------------------------------------------------------------------------
CAP = {}
CHK = {"n": 0, "mal": 0}
USO = {"camino_vacio": 0, "camino_ok": 0, "mono_vacio": 0, "mono_ok": 0}


def es_ancestro(prev, ancla, cand):
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


def instalar_camino(v2, camino, mono):
    """Devuelve restaurar(). Instalar ANTES de instrumentar."""
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    o_r = v2.reconstruct

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["si"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        CAP.clear()
        sk, res = o_p(self, comp, mode)
        if res is None or "dist" not in CAP or mode.startswith("AHEAD"):
            return sk, res

        _in(IDX["shim_resel"])
        pts, dist, prev, si = CAP["pts"], CAP["dist"], CAP["prev"], CAP["si"]
        sy, sx = pts[si]
        lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        fin = np.where(np.isfinite(dist))[0]
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            cands = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
                :min(30, len(fin))]
        _out()

        # --- CAMINO PRINCIPAL: la cadena start -> nodo mas lejano ----------
        if camino and len(fin):
            _in(IDX["camino_extra"])
            F = int(fin[int(np.argmax(dist[fin]))])
            cadena = set(o_r(prev, si, F) or [])
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub
                USO["camino_ok"] += 1
            else:
                USO["camino_vacio"] += 1
            _out()

        # --- MONOTONIA HACIA ADELANTE (Coulter 1992) -----------------------
        if mono and self.prev_target is not None and len(fin):
            _in(IDX["mono_extra"])
            ys = np.array([q[0] for q in pts])
            xs = np.array([q[1] for q in pts])
            dd = ((xs[fin] - self.prev_target[0]) ** 2
                  + (ys[fin] - self.prev_target[1]) ** 2)
            ancla = int(fin[int(np.argmin(dd))])
            adm = [i for i in cands if es_ancestro(prev, ancla, i)]
            if adm:
                cands = adm
                USO["mono_ok"] += 1
            else:
                USO["mono_vacio"] += 1
            _out()

        _in(IDX["shim_resel"])

        def score(i):
            y, x = pts[i]
            dy = sy - y
            h = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
            s = 0.35 * abs(dist[i] - v2.LOOKAHEAD)
            s += 0.55 * v2.angdiff(h, self.prev_heading)
            if self.prev_target is not None:
                s += 0.10 * math.hypot(x - self.prev_target[0],
                                       y - self.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        ti = min(cands, key=score)
        ty, tx = pts[ti]

        if not camino and not mono:
            # MODO FIDELIDAD: la variante esta apagada, asi que el selector
            # re-implementado tiene que coincidir con el de la candidata.
            CHK["n"] += 1
            if (abs(tx - res["target"][0]) > 1e-6
                    or abs(ty - res["target"][1]) > 1e-6):
                CHK["mal"] += 1
            _out()
            return sk, res

        cam_idx = o_r(prev, si, ti) or [si, ti]
        salida = dict(
            start=res["start"], target=(float(tx), float(ty)),
            heading=math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6))),
            path=[(float(pts[i][1]), float(pts[i][0])) for i in cam_idx])
        _out()
        return sk, salida

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


# --------------------------------------------------------------------------
# SHIM SIN POI
# --------------------------------------------------------------------------
_POI_VACIO = dict(top=None, bottom=None, left=None, right=None)


def instalar_sin_poi(v3):
    o = v3.poi_component

    def nada(comp, ref_x=None):
        return _POI_VACIO

    v3.poi_component = nada

    def restaurar():
        v3.poi_component = o
    return restaurar


# --------------------------------------------------------------------------
# CORREDORES
# --------------------------------------------------------------------------
def mk_cand(SinBranch, v2):
    """Devuelve (constructor, preprocess, paso)."""
    return (lambda: SinBranch(FPS), lambda fr: v2.frame_pi(fr),
            lambda tr, g: tr.step(g))


def mk_v1(v1):
    return (lambda: v1.AirborneV1(FPS), lambda fr: v1.frame_de_la_pi(fr),
            lambda tr, g: tr.paso(g))


# --------------------------------------------------------------------------
# CURVATURA DE PRODUCCION
# Copia LITERAL de vision_linea._curvatura() (vision_linea.py:127-172), que
# `velocidad()` llama una vez por frame cuando VISION_LINEA esta activa. Lee el
# mismo CAP que llena el shim. Se mide su costo, no su valor.
# --------------------------------------------------------------------------
def curvatura_prod(v2):
    try:
        if "dist" not in CAP:
            return None
        pts, dist = CAP["pts"], CAP["dist"]
        prev, si = CAP["prev"], CAP["si"]
        fin = np.where(np.isfinite(dist))[0]
        if len(fin) < 8:
            return None
        F = int(fin[int(np.argmax(dist[fin]))])
        cad = v2.reconstruct(prev, si, F)
        if not cad or len(cad) < 8:
            return None
        f_px = (v2.W / 2.0) / math.tan(math.radians(60.0 / 2.0))

        def suelo(u, v):
            z = (119.0 - 9.0) / max(v - 9.0, 1e-6)
            return ((u - v2.CENTER) * z / f_px, z)

        Pl = [suelo(pts[i][1], pts[i][0]) for i in cad]
        Q = Pl[::6] if len(Pl) >= 18 else Pl
        if len(Q) < 3:
            return None
        arco = 0.0
        hs = []
        for a, b in zip(Q, Q[1:]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            Lg = math.hypot(dx, dz)
            if Lg < 1e-9:
                continue
            arco += Lg
            hs.append(math.degrees(math.atan2(dx, dz)))
        if len(hs) < 2 or arco < 1e-9:
            return None
        giro = sum(abs((b - a + 180) % 360 - 180) for a, b in zip(hs, hs[1:]))
        return giro / arco
    except Exception:
        return None


def mk_cand_kappa(SinBranch, v2):
    """Como mk_cand pero llamando a _curvatura() igual que velocidad()."""
    def paso(tr, g):
        r = tr.step(g)
        _in(IDX["curvatura_prod"])
        curvatura_prod(v2)
        _out()
        return r
    return (lambda: SinBranch(FPS), lambda fr: v2.frame_pi(fr), paso)


def pasada_limpia(mk, ruta, warmup=None):
    """SIN perfilador y SIN espias. Devuelve ns por frame."""
    warmup = WARMUP if warmup is None else warmup
    cons, prep, paso = mk
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = cons()
    xs = []
    i = 0
    while True:
        if LIMITE is not None and i >= LIMITE:
            break
        ok, fr = cap.read()
        if not ok:
            break
        t0 = NS()
        g = prep(fr)
        paso(tr, g)
        dt = NS() - t0
        if i >= warmup:
            xs.append(dt)
        i += 1
    cap.release()
    return np.asarray(xs, np.int64)


def pasada_instrumentada(mk, ruta, buf, warmup=None):
    warmup = WARMUP if warmup is None else warmup
    cons, prep, paso = mk
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = cons()
    fila = np.zeros(NE, np.int64)
    i = 0
    n = 0
    P.activo = True
    while True:
        if LIMITE is not None and i >= LIMITE:
            break
        P.frame_nuevo()
        P.entrar(IDX["decode"])
        ok, fr = cap.read()
        P.salir()
        if not ok:
            break
        g = prep(fr)
        paso(tr, g)
        if i >= warmup:
            fila[:] = P.excl
            buf.add(fila)
            n += 1
        i += 1
    P.activo = False
    cap.release()
    return n


def serie_cand(SinBranch, v2, ruta, fps=FPS, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(fps)
    out = []
    i = 0
    while True:
        if LIMITE is not None and i >= LIMITE:
            break
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            t = r.get("target")
            out.append((t, None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90)),
                r.get("state")))
        i += 1
    cap.release()
    return out


def serie_v1(v1, ruta, fps=FPS, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = v1.AirborneV1(fps)
    out = []
    i = 0
    while True:
        if LIMITE is not None and i >= LIMITE:
            break
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.paso(v1.frame_de_la_pi(fr))
        if i >= desde:
            t = r.get("target")
            a = r.get("angle_target")
            out.append((t, None if (t is None or a is None
                                    or not np.isfinite(a)) else float(a),
                        r.get("estado")))
        i += 1
    cap.release()
    return out


def targets(serie):
    return [None if t is None else (round(float(t[0]), 9), round(float(t[1]), 9))
            for t, _s, _e in serie]


# --------------------------------------------------------------------------
# ESTADISTICA
# --------------------------------------------------------------------------
def stats_ms(ns):
    a = np.asarray(ns, np.float64) / 1e6
    if a.size == 0:
        return dict(n=0, media=0.0, p50=0.0, p90=0.0, p95=0.0, p99=0.0,
                    max=0.0, total=0.0)
    return dict(n=int(a.size), media=float(a.mean()),
                p50=float(np.percentile(a, 50)),
                p90=float(np.percentile(a, 90)),
                p95=float(np.percentile(a, 95)),
                p99=float(np.percentile(a, 99)),
                max=float(a.max()), total=float(a.sum()))


def total_alg(datos):
    mask = np.ones(NE, bool)
    for e in NO_CUENTAN:
        mask[IDX[e]] = False
    return datos[:, mask].sum(1)


# --------------------------------------------------------------------------
# EVIDENCIA ESTATICA sobre poi
# --------------------------------------------------------------------------
def escanear_poi():
    """Lista TODA lectura de 'poi' en los fuentes de la candidata."""
    fuentes = ["nuevo_code_v2.py", "nuevo_code_v3.py", "nuevo_code_v4.py",
               "Main.py", "main_rpi_2026-08-22.py", "camthreader.py",
               "vision_linea.py", "telemetria_vision.py", "shadow_pi.py"]
    hits = []
    for f in fuentes:
        ru = os.path.join(AQUI, f)
        if not os.path.exists(ru):
            continue
        with open(ru, "r", encoding="utf-8", errors="replace") as fh:
            for k, ln in enumerate(fh, 1):
                if re.search(r"\bpoi\b|\[.poi.\]|poi_component", ln):
                    hits.append((f, k, ln.strip()))
    return hits


# --------------------------------------------------------------------------
def entorno():
    e = {}
    e["timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    e["platform"] = platform.platform()
    e["machine"] = platform.machine()
    e["procesador"] = platform.processor()
    e["cpu_count"] = os.cpu_count()
    e["python"] = sys.version.split()[0]
    e["numpy"] = np.__version__
    e["opencv"] = cv2.__version__
    e["opencv_hilos"] = cv2.getNumThreads()
    try:
        import skimage
        e["scikit_image"] = skimage.__version__
    except Exception as ex:
        e["scikit_image"] = "AUSENTE %s" % ex
    e["es_raspberry"] = False
    try:
        with open("/proc/device-tree/model", "rb") as f:
            e["es_raspberry"] = "raspberry" in f.read().decode(
                "utf-8", "replace").lower()
    except Exception:
        pass
    return e


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Costo de CPU por variante")
    ap.add_argument("--reps", type=int, default=5,
                    help="repeticiones de la pasada limpia (intercaladas)")
    ap.add_argument("--hilos", type=int, default=None,
                    help="cv2.setNumThreads(N). Por defecto no se toca.")
    ap.add_argument("--json", default=None)
    ap.add_argument("--smoke", type=int, default=0,
                    help="corrida de humo: N frames por video")
    ap.add_argument("--produccion", action="store_true",
                    help="agrega las dos variantes que corre vision_linea.py")
    ap.add_argument("--sin-ab", action="store_true", dest="sin_ab",
                    help="saltear el A/B de 10 autonomos de poi")
    a = ap.parse_args()

    if a.hilos is not None:
        cv2.setNumThreads(a.hilos)
    if a.smoke:
        global LIMITE, WARMUP
        LIMITE = a.smoke
        WARMUP = max(5, a.smoke // 10)

    env = entorno()
    v4, v3, v2, v1 = cargar()
    SinBranch = hacer_sinbranch(v4)

    vids = [v for v in VIDEOS if os.path.exists(os.path.join(AQUI, v))]
    if len(vids) != len(VIDEOS):
        print("*** faltan videos: %s" % (set(VIDEOS) - set(vids)))
        return 2
    rutas = [os.path.join(AQUI, v) for v in vids]

    L = print
    L("")
    L("=" * 100)
    L("  WF RUNTIME - costo de CPU por variante del seguimiento de linea")
    L("  presupuesto %.2f ms/frame  (%.3f fps nominales)"
      % (PRESUPUESTO_MS, FPS))
    L("=" * 100)
    L("")
    L("  MAQUINA   %s / %s   %d nucleos" % (env["platform"], env["machine"],
                                            env["cpu_count"] or 0))
    L("            python %s  numpy %s  opencv %s (hilos %s)  skimage %s"
      % (env["python"], env["numpy"], env["opencv"], env["opencv_hilos"],
         env["scikit_image"]))
    L("  VIDEOS    %s   warmup %d frames por video   reps limpias %d"
      % (", ".join(vids), WARMUP, a.reps))
    if not env["es_raspberry"]:
        L("")
        L("  *** ESTA NO ES UNA RASPBERRY PI. Los ms absolutos NO valen. ***")
        L("  *** Solo vale la RAZON entre variantes.                     ***")
    L("")

    # ======================================================================
    # 0. EVIDENCIA ESTATICA sobre poi_component
    # ======================================================================
    L("-" * 100)
    L("  0. poi_component: quien lee r['poi'] (escaneo del fuente)")
    L("-" * 100)
    hits = escanear_poi()
    for f, k, ln in hits:
        L("     %-22s :%-4d  %s" % (f, k, ln[:66]))
    lecturas = [h for h in hits if '["poi"]' in h[2] and "r[\"poi\"] =" not in h[2]]
    L("")
    L("     lecturas de r['poi']: %d   -> %s" % (
        len(lecturas), ", ".join("%s:%d" % (h[0], h[1]) for h in lecturas)))
    L("")

    # ======================================================================
    # 1. FIDELIDAD
    # ======================================================================
    L("-" * 100)
    L("  1. FIDELIDAD - con la variante apagada tiene que dar el MISMO target")
    L("-" * 100)
    t0 = time.time()
    base_t = {}
    for v, ru in zip(vids, rutas):
        base_t[v] = targets(serie_cand(SinBranch, v2, ru))
    L("     candidata pristina: %d frames en %.1f s"
      % (sum(len(x) for x in base_t.values()), time.time() - t0))

    fid = {}

    # 1a. shim CAMINO+MONO con las dos banderas apagadas
    CHK["n"] = CHK["mal"] = 0
    rest = instalar_camino(v2, False, False)
    mal = 0
    for v, ru in zip(vids, rutas):
        s = targets(serie_cand(SinBranch, v2, ru))
        mal += sum(1 for x, y in zip(base_t[v], s) if x != y)
        mal += abs(len(base_t[v]) - len(s))
    rest()
    fid["shim_camino_off"] = dict(discrepancias=mal, chk_n=CHK["n"],
                                  chk_mal=CHK["mal"])
    L("     shim CAMINO+MONO apagado : %d discrepancias de serie   "
      "selector re-implementado %d/%d frames mal   %s"
      % (mal, CHK["mal"], CHK["n"], "OK" if (mal == 0 and CHK["mal"] == 0)
         else "*** ABORTA"))
    if mal or CHK["mal"]:
        return 3

    # 1b. shim sin poi
    rest = instalar_sin_poi(v3)
    mal = 0
    for v, ru in zip(vids, rutas):
        s = targets(serie_cand(SinBranch, v2, ru))
        mal += sum(1 for x, y in zip(base_t[v], s) if x != y)
        mal += abs(len(base_t[v]) - len(s))
    rest()
    fid["sin_poi"] = dict(discrepancias=mal)
    L("     poi_component anulado    : %d discrepancias   %s"
      % (mal, "OK" if mal == 0 else "*** ABORTA"))
    if mal:
        return 3

    # 1c. instrumentacion
    faltan = instrumentar_candidata(v4, v3, v2)
    P.activo = True
    P.frame_nuevo()
    mal = 0
    for v, ru in zip(vids, rutas):
        s = targets(serie_cand(SinBranch, v2, ru))
        mal += sum(1 for x, y in zip(base_t[v], s) if x != y)
        mal += abs(len(base_t[v]) - len(s))
    P.activo = False
    desespiar()
    fid["instrumentada"] = dict(discrepancias=mal)
    L("     instrumentacion          : %d discrepancias   %s"
      % (mal, "OK" if mal == 0 else "*** ABORTA"))
    if mal:
        return 3
    if faltan:
        L("     etapas no instrumentadas: %s" % ", ".join(faltan))
    L("")

    # ======================================================================
    # 2. LA VARIANTE ESTA VIVA (control negativo: CAMINO+MONO debe DIFERIR)
    # ======================================================================
    for k in USO:
        USO[k] = 0
    rest = instalar_camino(v2, True, True)
    dif = 0
    ntot = 0
    for v, ru in zip(vids, rutas):
        s = targets(serie_cand(SinBranch, v2, ru))
        dif += sum(1 for x, y in zip(base_t[v], s) if x != y)
        ntot += len(s)
    rest()
    L("-" * 100)
    L("  2. CONTROL: CAMINO+MONO encendido cambia %d de %d targets (%.1f %%)"
      % (dif, ntot, 100.0 * dif / max(ntot, 1)))
    L("     camino aplicado %d frames (vacio %d)   mono aplicado %d "
      "(vacio %d)" % (USO["camino_ok"], USO["camino_vacio"], USO["mono_ok"],
                      USO["mono_vacio"]))
    L("     Si esto fuera 0 la medicion de costo no significaria nada.")
    L("")

    # ======================================================================
    # 3. PASADAS LIMPIAS (titular)
    # ======================================================================
    L("-" * 100)
    L("  3. PASADAS LIMPIAS - sin perfilador y sin un solo espia instalado")
    L("-" * 100)

    VARIANTES = ["BASE", "CAMINO+MONO", "V1", "BASE sin POI",
                 "CAMINO+MONO sin POI"]
    if a.produccion:
        VARIANTES += ["PROD base+shim", "PROD camino+kappa"]

    def con_variante(nombre, fn):
        """Instala los shims de `nombre`, corre fn(), restaura."""
        rs = []
        if nombre.startswith("CAMINO+MONO"):
            rs.append(instalar_camino(v2, True, True))
        if nombre == "PROD base+shim":
            rs.append(instalar_camino(v2, False, False))
        if nombre == "PROD camino+kappa":
            rs.append(instalar_camino(v2, True, True))
        if nombre.endswith("sin POI"):
            rs.append(instalar_sin_poi(v3))
        try:
            return fn()
        finally:
            for r in reversed(rs):
                r()

    def mk_de(nombre):
        if nombre == "V1":
            return mk_v1(v1)
        if nombre == "PROD camino+kappa":
            return mk_cand_kappa(SinBranch, v2)
        return mk_cand(SinBranch, v2)

    # Intercalado fino: dentro de cada repeticion se recorre video por video y,
    # dentro de cada video, las cinco variantes seguidas. Ademas el orden ROTA
    # con la repeticion. Asi ninguna variante se lleva sistematicamente el
    # turbo del principio ni el throttling del final.
    limpio = dict((n, {}) for n in VARIANTES)   # variante -> video -> [ns]
    t0 = time.time()
    nv = len(VARIANTES)
    for rep in range(a.reps):
        orden = [VARIANTES[(rep + j) % nv] for j in range(nv)]
        for v, ru in zip(vids, rutas):
            for nom in orden:
                def corr(nom=nom, ru=ru):
                    return pasada_limpia(mk_de(nom), ru)
                limpio[nom].setdefault(v, []).append(
                    con_variante(nom, corr))
        L("     rep %d/%d  orden %s  %.1f s"
          % (rep + 1, a.reps, " > ".join(x.replace("CAMINO+MONO", "C+M")
                                         for x in orden), time.time() - t0))
    L("")

    pool = {}
    for nom in VARIANTES:
        pool[nom] = np.concatenate(
            [np.concatenate(limpio[nom][v]) for v in vids])

    s_base = stats_ms(pool["BASE"])
    L("  TIEMPO TOTAL POR FRAME  (preprocess + step, ms). %d frames por "
      "variante" % s_base["n"])
    L("  %-22s %8s %8s %8s %8s %8s %9s %9s"
      % ("variante", "media", "p50", "p90", "p99", "max", "x BASE p50",
         "x BASE med"))
    stats = {}
    for nom in VARIANTES:
        s = stats_ms(pool[nom])
        stats[nom] = s
        L("  %-22s %8.3f %8.3f %8.3f %8.3f %8.3f %9.3f %9.3f"
          % (nom, s["media"], s["p50"], s["p90"], s["p99"], s["max"],
             s["p50"] / s_base["p50"], s["media"] / s_base["media"]))
    L("")
    L("  DELTA CONTRA BASE  (ms por frame)")
    L("  %-22s %10s %10s %10s %10s"
      % ("variante", "d media", "d p50", "d p90", "d p99"))
    for nom in VARIANTES:
        s = stats[nom]
        L("  %-22s %+10.3f %+10.3f %+10.3f %+10.3f"
          % (nom, s["media"] - s_base["media"], s["p50"] - s_base["p50"],
             s["p90"] - s_base["p90"], s["p99"] - s_base["p99"]))
    L("")

    L("  POR VIDEO  (p50 ms, pasadas limpias agrupadas)")
    L("  %-22s %12s %12s %12s" % ("variante", vids[0], vids[1], vids[2]))
    porvideo = {}
    for nom in VARIANTES:
        fila = []
        porvideo[nom] = {}
        for v in vids:
            s = stats_ms(np.concatenate(limpio[nom][v]))
            porvideo[nom][v] = s
            fila.append(s["p50"])
        L("  %-22s %12.3f %12.3f %12.3f" % (nom, fila[0], fila[1], fila[2]))
    L("")
    L("  DISPERSION ENTRE REPETICIONES (p50 de cada rep, ms) - ruido de la PC")
    L("  %-22s %s" % ("variante", "p50 por rep"))
    for nom in VARIANTES:
        ps = [float(np.percentile(np.concatenate(
            [limpio[nom][v][r] for v in vids]), 50)) / 1e6
            for r in range(a.reps)]
        L("  %-22s %s   (spread %.3f ms)"
          % (nom, "  ".join("%.3f" % x for x in ps), max(ps) - min(ps)))
    L("")

    # ======================================================================
    # 4. PASADAS INSTRUMENTADAS (desglose por etapa)
    # ======================================================================
    L("-" * 100)
    L("  4. DESGLOSE POR ETAPA (tiempo EXCLUSIVO, ms)")
    L("-" * 100)
    instr = {}
    for nom in VARIANTES:
        buf = Buffer(16384)

        def corr(nom=nom, buf=buf):
            if nom == "V1":
                instrumentar_v1(v1)
            else:
                instrumentar_candidata(v4, v3, v2)
            try:
                for ru in rutas:
                    pasada_instrumentada(mk_de(nom), ru, buf)
            finally:
                desespiar()
            return buf.datos()
        instr[nom] = con_variante(nom, corr)

    tabla_etapas = {}
    for nom in VARIANTES:
        d = instr[nom]
        alg = total_alg(d)
        s_alg = stats_ms(alg)
        L("")
        L("  --- %s ---   %d frames   ALGORITMO media %.3f  p50 %.3f  "
          "p90 %.3f  p99 %.3f  max %.3f ms"
          % (nom, d.shape[0], s_alg["media"], s_alg["p50"], s_alg["p90"],
             s_alg["p99"], s_alg["max"]))
        L("      %-22s %9s %9s %9s %9s  %7s"
          % ("etapa", "media", "p50", "p90", "max", "% tot"))
        tot_media = s_alg["media"]
        tabla_etapas[nom] = {}
        py_ms = 0.0
        for e in ETAPAS:
            if e in NO_CUENTAN:
                continue
            col = d[:, IDX[e]]
            if col.sum() == 0:
                continue
            s = stats_ms(col)
            tabla_etapas[nom][e] = s
            if e in PY_PURO:
                py_ms += s["media"]
            L("      %-22s %9.4f %9.4f %9.4f %9.4f  %6.1f"
              % (e, s["media"], s["p50"], s["p90"], s["max"],
                 100.0 * s["media"] / tot_media if tot_media else 0.0))
        s_dec = stats_ms(d[:, IDX["decode"]])
        L("      %-22s %9.4f %9.4f %9.4f %9.4f  %6s"
          % ("(decode, no cuenta)", s_dec["media"], s_dec["p50"],
             s_dec["p90"], s_dec["max"], "-"))
        L("      interprete de Python (aprox) %.1f %% del frame"
          % (100.0 * py_ms / tot_media if tot_media else 0.0))
        tabla_etapas[nom]["_py_pct"] = (100.0 * py_ms / tot_media
                                        if tot_media else 0.0)
        tabla_etapas[nom]["_alg"] = s_alg
    L("")

    L("  OVERHEAD DEL PERFILADOR  (instrumentado p50 - limpio p50)")
    L("  %-22s %10s %10s %10s" % ("variante", "limpio", "instrum", "delta %"))
    for nom in VARIANTES:
        pl = stats[nom]["p50"]
        pi_ = tabla_etapas[nom]["_alg"]["p50"]
        L("  %-22s %10.3f %10.3f %+10.1f"
          % (nom, pl, pi_, 100.0 * (pi_ - pl) / pl if pl else 0.0))
    L("")

    # ======================================================================
    # 5. poi_component: cuanto se ahorra
    # ======================================================================
    L("-" * 100)
    L("  5. poi_component - cuanto pesa y cuanto se ahorra sacandolo")
    L("-" * 100)
    poi_base = tabla_etapas["BASE"].get("poi_component", stats_ms([]))
    runs_base = tabla_etapas["BASE"].get("runs_1d", stats_ms([]))
    alg_base_i = tabla_etapas["BASE"]["_alg"]
    L("     peso medido de la etapa poi_component en BASE: %.4f ms = %.2f %% "
      "del frame" % (poi_base["media"],
                     100.0 * poi_base["media"] / alg_base_i["media"]))
    L("     (poi_component llama a runs_1d: parte de su costo real esta")
    L("      contabilizado en la etapa runs_1d, %.4f ms totales)"
      % runs_base["media"])
    for par in (("BASE", "BASE sin POI"),
                ("CAMINO+MONO", "CAMINO+MONO sin POI")):
        c, s = stats[par[0]], stats[par[1]]
        L("     %-20s -> %-20s  p50 %.3f -> %.3f ms  (%+.3f ms, %+.2f %%)"
          % (par[0], par[1], c["p50"], s["p50"], s["p50"] - c["p50"],
             100.0 * (s["p50"] - c["p50"]) / c["p50"]))
    L("")

    # ======================================================================
    # 6. A/B de percepcion de quitar poi sobre los 10 autonomos
    # ======================================================================
    ab = None
    if not a.sin_ab:
        L("-" * 100)
        L("  6. QUITAR poi_component - A/B de percepcion sobre los 10 "
          "autonomos + controles")
        L("-" * 100)
        t0 = time.time()

        def agregado(con_shim):
            rs = instalar_sin_poi(v3) if con_shim else None
            try:
                tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0,
                           suav=[])
                for vid in AB.AUTONOMOS:
                    ru = os.path.join(AQUI, vid)
                    if not os.path.exists(ru):
                        continue
                    m = AB.metricas(serie_cand(SinBranch, v2, ru))
                    for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
                        tot[k] += m[k]
                    tot["suav"].append(m["suav"])
                tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
                tot["suav"] = float(np.mean(tot["suav"]))
                ctl = []
                okc = True
                for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
                    ru = os.path.join(AQUI, vid)
                    if not os.path.exists(ru) or not ex:
                        continue
                    ser = serie_cand(SinBranch, v2, ru, fps, d0, h0)
                    m = AB.metricas(ser)
                    st = [x for _t, x, _e in ser if x is not None]
                    ctl.append("%s %d/%d" % (cn.split("_")[0], m["con"], ex))
                    okc &= (m["con"] >= ex)
                    if cn == "lineal_positivo":
                        ctl.append("smax %+.0f" % (max(st) if st else 0))
                tot["ctl"] = "  ".join(ctl)
                tot["ctl_ok"] = bool(okc)
                return tot
            finally:
                if rs:
                    rs()

        ab = {"BASE": agregado(False), "SIN POI": agregado(True)}
        L("     %.1f s" % (time.time() - t0))
        L("")
        L("  %-14s %9s %9s %9s %9s %11s %9s   %s"
          % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
             "inversiones", "suav", "controles"))
        b = ab["BASE"]
        L("  %-14s %9.2f %9d %9d %9d %11d %9.2f   %s %s"
          % ("BASE", b["disp"], b["sin_aut"], b["huecos"], b["s_gt"],
             b["inv"], b["suav"], b["ctl"], "OK" if b["ctl_ok"] else "FALLA"))
        s = ab["SIN POI"]
        L("  %-14s %+9.2f %+9d %+9d %+9d %+11d %+9.2f   %s %s"
          % ("SIN POI", s["disp"] - b["disp"], s["sin_aut"] - b["sin_aut"],
             s["huecos"] - b["huecos"], s["s_gt"] - b["s_gt"],
             s["inv"] - b["inv"], s["suav"] - b["suav"], s["ctl"],
             "OK" if s["ctl_ok"] else "FALLA"))
        L("")

    # ======================================================================
    # 7. LECTURA
    # ======================================================================
    L("=" * 100)
    L("  LECTURA")
    L("=" * 100)
    cm = stats["CAMINO+MONO"]
    u1 = stats["V1"]
    L("  CAMINO+MONO cuesta x%.3f el p50 de BASE (%+.3f ms/frame en ESTA PC)."
      % (cm["p50"] / s_base["p50"], cm["p50"] - s_base["p50"]))
    ce = tabla_etapas["CAMINO+MONO"]
    extra_puro = (ce.get("camino_extra", {"media": 0.0})["media"]
                  + ce.get("mono_extra", {"media": 0.0})["media"])
    resel = ce.get("shim_resel", {"media": 0.0})["media"]
    L("  De ese sobrecosto, %.4f ms/frame son las etapas NUEVAS de verdad"
      % extra_puro)
    L("  (camino_extra + mono_extra) y %.4f ms/frame son la RE-SELECCION"
      % resel)
    L("  DUPLICADA que paga el shim y que una implementacion in-place no")
    L("  pagaria. Cota inferior de produccion: x%.3f. Cota superior (shim tal"
      % ((s_base["media"] + extra_puro) / s_base["media"]))
    L("  cual): x%.3f." % (cm["media"] / s_base["media"]))
    L("")
    L("  V1 cuesta x%.3f el p50 de BASE: es %.1f %% mas BARATA (%+.3f ms)."
      % (u1["p50"] / s_base["p50"], 100.0 * (1 - u1["p50"] / s_base["p50"]),
         u1["p50"] - s_base["p50"]))
    L("  Es decir, BASE cuesta x%.2f lo que cuesta V1."
      % (s_base["p50"] / u1["p50"]))
    L("")
    L("  EL TIEMPO ABSOLUTO DE ESTA PC NO PREDICE EL DE LA PI. Ninguno de los")
    L("  ms de arriba es un pronostico. Lo unico que se puede llevar a la Pi")
    L("  es la RAZON entre variantes, y con reserva: el mix interprete/")
    L("  compilado cambia entre x86 y ARM (ver la fila 'interprete de Python'")
    L("  de cada variante). Si una variante es mas pesada JUSTO en la parte")
    L("  interpretada, en la Pi la razon puede ser PEOR que aca.")
    L("=" * 100)
    L("")

    salida = dict(
        entorno=env, argumentos=vars(a), videos=vids, warmup=WARMUP,
        fidelidad=fid, control_variante_viva=dict(cambia=dif, de=ntot),
        limpio=dict((n, stats[n]) for n in VARIANTES),
        limpio_por_video=dict((n, porvideo[n]) for n in VARIANTES),
        etapas=dict((n, dict((k, v) for k, v in tabla_etapas[n].items()))
                    for n in VARIANTES),
        poi=dict(lecturas=[(h[0], h[1], h[2]) for h in lecturas],
                 peso_ms=poi_base["media"]),
        ab_poi=ab,
        uso_camino=dict(USO),
    )
    destino = a.json or os.path.join(AQUI, "wf_runtime.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=1, default=str)
    L("  JSON: %s" % destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
