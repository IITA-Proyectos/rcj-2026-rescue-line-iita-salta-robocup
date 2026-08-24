# -*- coding: utf-8 -*-
"""
BENCH RUNTIME - cuanto tarda de verdad la candidata EN LA RASPBERRY PI.

P0 del traspaso del 2026-08-23. La candidata NUEVO CODE V1 RC
(`SinBranch` = V2 + SpatialTargetGuard, sin el branch guard de V3) usa
skeletonize + construccion de grafo + Dijkstra en Python puro. Los diez videos
autonomos corresponden a 100/3 = 33,333 fps reales del loop, o sea un
presupuesto de ~30 ms por frame. Nunca medimos eso EN LA PI.

Descubrir el sabado que el loop tarda 45-80 ms/frame inutiliza la candidata
entera y nos cuesta una de las dos sesiones fisicas que quedan. Por eso se mide
antes, offline, y con un numero reproducible.

QUE ES Y QUE NO ES
------------------
* NO modifica ningun archivo de la candidata. Instrumenta con espias
  reversibles (monkeypatch dentro de ESTE proceso).
* Antes de medir VERIFICA que la version instrumentada produce exactamente la
  misma serie de targets que la limpia. Si no coincide, aborta: un banco que
  cambia lo que mide no sirve.
* Mide el overhead del propio perfilador y lo reporta.
* El numero que decide es `algoritmo` = frame_pi + SinBranch.step.
  El decode del .avi se mide APARTE y NO cuenta: en el robot el frame lo trae
  el hilo de camara (camthreader.WebcamVideoStream), no un decoder MJPG.
* El tiempo de esta PC NO es prueba de nada. Solo la Pi cuenta.

USO
---
    python bench_runtime.py                      # 10 autonomos, una pasada
    python bench_runtime.py --modo rapido        # hist/lineal/roi_auto
    python bench_runtime.py --modo sostenido --minutos 8
    python bench_runtime.py --camara 600         # captura real (Pi + camara)

Salida: tabla por etapa + veredicto + JSON con todo.
"""

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import threading
import time

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
NS = time.perf_counter_ns

# Presupuesto nominal: los autonomos son 100/3 fps.
FPS_NOMINAL = 100.0 / 3.0
PRESUPUESTO_MS = 1000.0 / FPS_NOMINAL          # 30.0 ms exactos

# Umbrales del veredicto. Se imprimen siempre para que no se puedan mover
# despues de ver el resultado (regla 27 del traspaso).
V_VERDE_P95 = 30.0
V_VERDE_P99 = 35.0
V_VERDE_PCT30 = 1.0
V_ROJO_P50 = 30.0
V_ROJO_PCT30 = 10.0

# Orden fijo de etapas. El indice es la columna del buffer de tiempos.
ETAPAS = (
    "decode",                # lectura/decode del .avi   (NO cuenta al robot)
    "frame_pi",              # 1. preprocess
    "mask_linea",            # 2. mascara
    "cc_candidates",         # 2b. connected components + stats
    "component_distance",    # 3b. distancia componente<->referencia
    "choose_component",      # 3. seleccion de componente (exclusivo)
    "fill_contornos",        # relleno de huecos internos (findContours+draw)
    "state",                 # clasificacion HIGH/MEDIUM/LOW/SIN_CERCA
    "skeletonize",           # 4. skeletonize (scikit-image)
    "graph_from_skeleton",   # 5. grafo desde el esqueleto
    "dijkstra",              # 6. Dijkstra en Python puro
    "reconstruct",           # 6b. reconstruccion del path
    "runs_1d",               # corridas 1D (path_target y poi_component)
    "path_target",           # 7. shell geodesica + score (exclusivo)
    "percepcion_resto",      # 8. cap de continuidad + low_proj + bookkeeping
    "spatial_guard",         # 9. SpatialTargetGuard
    "ctrl",                  # preview de control (slew)
    "poi_component",         # POI T/B/L/R  -- SOLO DIAGNOSTICO VISUAL
    "v4_resto",              # pegamento de NuevoCodeV4.step (exclusivo)
)
IDX = dict((e, i) for i, e in enumerate(ETAPAS))
NE = len(ETAPAS)

# Etapas que el robot NO paga en produccion.
NO_CUENTAN = ("decode",)


# --------------------------------------------------------------------------
# PERFILADOR de pila: tiempo inclusivo y exclusivo por etapa, sin doble conteo
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


class Buffer(object):
    """Buffer numpy que crece por duplicacion. Sin I/O durante la medida."""

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
# ESPIAS reversibles
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
    envoltorio.__doc__ = getattr(orig, "__doc__", None)
    return envoltorio


def espiar(obj, nombre, etapa, obligatorio=True):
    """Reemplaza obj.nombre por un envoltorio cronometrado. Reversible."""
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


# --------------------------------------------------------------------------
# CARGA de la candidata (identica a arquitectura_minima.py, sin tocar archivos)
# --------------------------------------------------------------------------
def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def hacer_sinbranch(v4):
    """SinBranch tal cual arquitectura_minima.py: V4 con el branch guard nulo."""
    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _Nulo()

    return SinBranch


def instrumentar(v4, v3, v2):
    """Coloca todos los espias. Devuelve las etapas que no se pudieron medir."""
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
    # El relleno de contornos vive inline dentro de V2.step: se llega por cv2.
    if not espiar(cv2, "findContours", "fill_contornos", obligatorio=False):
        faltan.append("fill_contornos(findContours)")
    if not espiar(cv2, "drawContours", "fill_contornos", obligatorio=False):
        faltan.append("fill_contornos(drawContours)")
    return faltan


# --------------------------------------------------------------------------
# ENTORNO y TELEMETRIA
# --------------------------------------------------------------------------
def _leer(p):
    try:
        with open(p, "rb") as f:
            return f.read().decode("utf-8", "replace").strip("\x00\n\r ")
    except Exception:
        return None


def _cmd(args, timeout=5):
    try:
        out = subprocess.check_output(args, stderr=subprocess.DEVNULL,
                                      timeout=timeout)
        return out.decode("utf-8", "replace").strip()
    except Exception:
        return None


def es_pi():
    m = _leer("/proc/device-tree/model") or ""
    return "raspberry" in m.lower()


def entorno():
    e = {}
    e["timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    e["modelo"] = _leer("/proc/device-tree/model")
    e["es_raspberry"] = es_pi()
    e["platform"] = platform.platform()
    e["machine"] = platform.machine()
    e["processor"] = platform.processor()
    e["kernel"] = " ".join(platform.uname()[:3])
    e["os_release"] = None
    osr = _leer("/etc/os-release")
    if osr:
        for ln in osr.splitlines():
            if ln.startswith("PRETTY_NAME="):
                e["os_release"] = ln.split("=", 1)[1].strip('"')
    e["cpu_count"] = os.cpu_count()

    ci = _leer("/proc/cpuinfo") or ""
    for clave in ("model name", "Model", "Hardware", "Revision"):
        for ln in ci.splitlines():
            if ln.lower().startswith(clave.lower()):
                e["cpuinfo_" + clave.replace(" ", "_")] = \
                    ln.split(":", 1)[1].strip()
                break

    mi = _leer("/proc/meminfo") or ""
    for ln in mi.splitlines():
        if ln.startswith("MemTotal"):
            e["mem_total"] = ln.split(":", 1)[1].strip()
            break

    e["freq_max_khz"] = _leer(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
    e["freq_min_khz"] = _leer(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq")
    e["governor"] = _leer(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")

    e["python"] = sys.version.split()[0]
    e["python_full"] = sys.version.replace("\n", " ")
    e["numpy"] = np.__version__
    e["opencv"] = cv2.__version__
    e["opencv_threads"] = cv2.getNumThreads()
    e["opencv_cpus"] = cv2.getNumberOfCPUs()
    e["opencv_optimizado"] = bool(cv2.useOptimized())
    try:
        bi = cv2.getBuildInformation()
        e["opencv_build"] = [ln.strip() for ln in bi.splitlines()
                             if any(k in ln for k in
                                    ("NEON", "Parallel framework", "OpenCL:",
                                     "TBB", "Lapack", "Custom HAL"))][:8]
    except Exception:
        e["opencv_build"] = None
    try:
        import skimage
        e["scikit_image"] = skimage.__version__
    except Exception as ex:
        e["scikit_image"] = "AUSENTE: %s" % ex
    try:
        import scipy
        e["scipy"] = scipy.__version__
    except Exception:
        e["scipy"] = None

    e["git_head"] = _cmd(["git", "-C", AQUI, "rev-parse", "HEAD"])
    e["git_branch"] = _cmd(["git", "-C", AQUI, "rev-parse",
                            "--abbrev-ref", "HEAD"])
    e["git_sucio"] = bool(_cmd(["git", "-C", AQUI, "status", "--porcelain",
                                "--untracked-files=no"]))
    e["hostname"] = platform.node()
    return e


THROT_BITS = [
    (0, "under-voltage AHORA"),
    (1, "frecuencia ARM capada AHORA"),
    (2, "throttling AHORA"),
    (3, "limite blando de temperatura AHORA"),
    (16, "hubo under-voltage"),
    (17, "hubo capado de frecuencia"),
    (18, "HUBO THROTTLING"),
    (19, "hubo limite blando de temperatura"),
]


def decodificar_throttled(txt):
    if not txt or "=" not in txt:
        return None, []
    try:
        v = int(txt.split("=", 1)[1], 16)
    except Exception:
        return None, []
    return v, [d for b, d in THROT_BITS if v & (1 << b)]


def telemetria(con_vcgencmd=True):
    t = {"t": time.time()}
    v = _leer("/sys/class/thermal/thermal_zone0/temp")
    if v:
        try:
            t["temp_c"] = round(float(v) / 1000.0, 2)
        except Exception:
            pass
    f = _leer("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    if f:
        try:
            t["freq_mhz"] = round(float(f) / 1000.0, 1)
        except Exception:
            pass
    try:
        t["loadavg"] = os.getloadavg()[0]
    except Exception:
        pass
    if con_vcgencmd:
        th = _cmd(["vcgencmd", "get_throttled"])
        if th:
            val, flags = decodificar_throttled(th)
            t["throttled_raw"] = th
            t["throttled"] = val
            t["throttled_flags"] = flags
        tc = _cmd(["vcgencmd", "measure_temp"])
        if tc and "temp_c" not in t:
            try:
                t["temp_c"] = float(tc.split("=")[1].replace("'C", ""))
            except Exception:
                pass
        cl = _cmd(["vcgencmd", "measure_clock", "arm"])
        if cl and "=" in cl:
            try:
                t["freq_arm_mhz"] = round(int(cl.split("=")[1]) / 1e6, 1)
            except Exception:
                pass
    return t


# --------------------------------------------------------------------------
# MEDICION
# --------------------------------------------------------------------------
def medir_video(SinBranch, v2, ruta, fps, buf, warmup, telem, cada_s,
                limite=None):
    """Corre un video completo. Devuelve (frames_medidos, ns_telemetria)."""
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError("no abre " + ruta)
    tr = SinBranch(fps)
    i = 0
    medidos = 0
    ns_telem = 0
    prox_telem = time.time() + cada_s
    fila = np.zeros(NE, np.int64)
    P.activo = True
    while True:
        if limite is not None and medidos >= limite:
            break
        P.frame_nuevo()
        P.entrar(IDX["decode"])
        ok, fr = cap.read()
        P.salir()
        if not ok:
            break
        g = v2.frame_pi(fr)
        tr.step(g)
        if i >= warmup:
            fila[:] = P.excl
            buf.add(fila)
            medidos += 1
        i += 1
        # Telemetria FUERA de la region cronometrada, y se descuenta del wall.
        if telem is not None and time.time() >= prox_telem:
            t0 = NS()
            telem.append(telemetria(True))
            ns_telem += NS() - t0
            prox_telem = time.time() + cada_s
    P.activo = False
    cap.release()
    return medidos, ns_telem


def serie_targets(cls, v2, ruta, fps, limite=None):
    """Serie de targets, para verificar equivalencia instrumentado/limpio."""
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError("no abre " + ruta)
    tr = cls(fps)
    out = []
    i = 0
    while True:
        if limite is not None and i >= limite:
            break
        ok, fr = cap.read()
        if not ok:
            break
        g = v2.frame_pi(fr)
        r = tr.step(g)
        t = r.get("target")
        out.append(None if t is None else (round(float(t[0]), 6),
                                           round(float(t[1]), 6)))
        i += 1
    cap.release()
    return out


def medir_limpio(cls, v2, ruta, fps, warmup, limite=None):
    """Total por frame SIN perfilador, para medir el overhead de instrumentar."""
    cap = cv2.VideoCapture(ruta)
    tr = cls(fps)
    xs = []
    i = 0
    while True:
        if limite is not None and len(xs) >= limite:
            break
        ok, fr = cap.read()
        if not ok:
            break
        t0 = NS()
        g = v2.frame_pi(fr)
        tr.step(g)
        dt = NS() - t0
        if i >= warmup:
            xs.append(dt)
        i += 1
    cap.release()
    return np.asarray(xs, np.int64)


# --------------------------------------------------------------------------
# ESTADISTICA Y REPORTE
# --------------------------------------------------------------------------
def stats_ms(ns):
    a = np.asarray(ns, np.float64) / 1e6
    if a.size == 0:
        return dict(n=0)
    return dict(
        n=int(a.size),
        media=float(a.mean()),
        p50=float(np.percentile(a, 50)),
        p90=float(np.percentile(a, 90)),
        p95=float(np.percentile(a, 95)),
        p99=float(np.percentile(a, 99)),
        max=float(a.max()),
        total_ms=float(a.sum()),
    )


def veredicto(s):
    if s["p50"] >= V_ROJO_P50 or s["pct30"] >= V_ROJO_PCT30:
        return "ROJO"
    if (s["p95"] < V_VERDE_P95 and s["p99"] < V_VERDE_P99
            and s["pct30"] < V_VERDE_PCT30):
        return "VERDE"
    return "AMARILLO"


def resumen_total(datos):
    """datos: (n, NE) int64 exclusivos. Devuelve el agregado `algoritmo`."""
    mask = np.ones(NE, bool)
    for e in NO_CUENTAN:
        mask[IDX[e]] = False
    alg = datos[:, mask].sum(1)
    s = stats_ms(alg)
    a = alg / 1e6
    s["pct30"] = float(100.0 * (a > 30.0).mean())
    s["pct35"] = float(100.0 * (a > 35.0).mean())
    s["pct40"] = float(100.0 * (a > 40.0).mean())
    s["fps_media"] = 1000.0 / s["media"] if s["media"] else 0.0
    s["fps_p95"] = 1000.0 / s["p95"] if s["p95"] else 0.0
    return s, alg


def imprimir(env, faltan, por_video, datos, s_alg, overhead, telem, args):
    L = print
    L("")
    L("=" * 78)
    L("  BENCH RUNTIME - candidata NUEVO CODE V1 RC (SinBranch = V2+Spatial)")
    L("=" * 78)
    L("")
    L("  MAQUINA")
    L("    modelo            %s" % (env.get("modelo") or "(no es una Pi)"))
    L("    plataforma        %s / %s" % (env["platform"], env["machine"]))
    L("    os                %s" % (env.get("os_release") or "-"))
    L("    cpu               %s   nucleos %s" % (
        env.get("cpuinfo_model_name") or env.get("cpuinfo_Model") or "-",
        env["cpu_count"]))
    L("    freq min/max kHz  %s / %s   governor %s" % (
        env.get("freq_min_khz"), env.get("freq_max_khz"),
        env.get("governor")))
    L("    memoria           %s" % (env.get("mem_total") or "-"))
    L("    python            %s" % env["python"])
    L("    numpy             %s" % env["numpy"])
    L("    opencv            %s   hilos %s   optimizado %s" % (
        env["opencv"], env["opencv_threads"], env["opencv_optimizado"]))
    L("    scikit-image      %s" % env["scikit_image"])
    L("    git               %s %s%s" % (
        env.get("git_branch"), (env.get("git_head") or "")[:10],
        "  (ARBOL SUCIO)" if env.get("git_sucio") else ""))
    if not env["es_raspberry"]:
        L("")
        L("    *** ESTA NO ES UNA RASPBERRY PI. El numero NO decide nada. ***")
    L("")

    if faltan:
        L("  ETAPAS NO INSTRUMENTADAS (se suman a la etapa que las contiene)")
        for f in faltan:
            L("    - %s" % f)
        L("")

    L("  CORRIDA")
    L("    modo              %s" % args.modo)
    L("    warmup            %d frames por video" % args.warmup)
    L("    videos            %d" % len(por_video))
    L("    frames medidos    %d" % datos.shape[0])
    L("    presupuesto       %.2f ms/frame  (%.3f fps nominales)"
      % (PRESUPUESTO_MS, FPS_NOMINAL))
    L("")

    L("  EQUIVALENCIA INSTRUMENTADO vs LIMPIO")
    if overhead.get("equivalente") is None:
        L("    (no verificada: --sin-verificar)")
    elif overhead["equivalente"]:
        L("    OK  %d/%d targets identicos en %s"
          % (overhead["iguales"], overhead["n"], overhead["video"]))
    else:
        L("    *** FALLA: %d/%d targets identicos. El banco cambia lo que mide."
          % (overhead["iguales"], overhead["n"]))
    if overhead.get("p50_limpio_ms") is not None:
        L("    overhead del perfilador   p50 limpio %.3f ms   "
          "p50 instrumentado %.3f ms   %+.3f ms (%+.1f %%)"
          % (overhead["p50_limpio_ms"], overhead["p50_instr_ms"],
             overhead["delta_ms"], overhead["delta_pct"]))
    L("")

    L("  TIEMPO POR ETAPA (exclusivo, ms) sobre %d frames" % datos.shape[0])
    L("    %-22s %8s %8s %8s %8s %8s %8s  %6s"
      % ("etapa", "media", "p50", "p90", "p95", "p99", "max", "% tot"))
    tot_media = sum(stats_ms(datos[:, IDX[e]])["media"]
                    for e in ETAPAS if e not in NO_CUENTAN)
    for e in ETAPAS:
        s = stats_ms(datos[:, IDX[e]])
        if s["n"] == 0:
            continue
        if e in NO_CUENTAN or not tot_media:
            pct = "  -  "
        else:
            pct = "%5.1f" % (100.0 * s["media"] / tot_media)
        marca = "  (no cuenta)" if e in NO_CUENTAN else ""
        L("    %-22s %8.3f %8.3f %8.3f %8.3f %8.3f %8.3f  %6s%s"
          % (e, s["media"], s["p50"], s["p90"], s["p95"], s["p99"], s["max"],
             pct, marca))
    L("    %s %s %s %s %s %s %s"
      % ("-" * 22, "-" * 8, "-" * 8, "-" * 8, "-" * 8, "-" * 8, "-" * 8))
    L("    %-22s %8.3f %8.3f %8.3f %8.3f %8.3f %8.3f  %6s"
      % ("ALGORITMO (total)", s_alg["media"], s_alg["p50"], s_alg["p90"],
         s_alg["p95"], s_alg["p99"], s_alg["max"], "100.0"))
    L("")
    L("    ALGORITMO = todo menos el decode del .avi. Es lo que paga el robot")
    L("    por frame una vez que el hilo de camara le entrego la imagen.")
    L("")

    L("  DISTRIBUCION CONTRA EL PRESUPUESTO")
    L("    frames > 30 ms    %6.2f %%" % s_alg["pct30"])
    L("    frames > 35 ms    %6.2f %%" % s_alg["pct35"])
    L("    frames > 40 ms    %6.2f %%" % s_alg["pct40"])
    L("    fps efectivo      %6.2f  (por la media)" % s_alg["fps_media"])
    L("    fps garantizado   %6.2f  (por el p95)" % s_alg["fps_p95"])
    L("")

    L("  POR VIDEO (algoritmo, ms)")
    L("    %-22s %7s %8s %8s %8s %8s"
      % ("video", "frames", "media", "p50", "p95", "max"))
    for v in por_video:
        L("    %-22s %7d %8.3f %8.3f %8.3f %8.3f"
          % (v["video"], v["frames"], v["media"], v["p50"], v["p95"],
             v["max"]))
    L("")

    if telem:
        t0, t1 = telem[0], telem[-1]
        temps = [t.get("temp_c") for t in telem if t.get("temp_c") is not None]
        L("  TERMICA Y THROTTLING  (%d muestras)" % len(telem))
        if temps:
            L("    temperatura       inicio %.1f C   final %.1f C   max %.1f C"
              % (temps[0], temps[-1], max(temps)))
        else:
            L("    temperatura       no disponible en esta maquina")
        fr = [t.get("freq_mhz") for t in telem if t.get("freq_mhz")]
        if fr:
            L("    frecuencia        inicio %.0f MHz  final %.0f MHz  "
              "min %.0f MHz" % (fr[0], fr[-1], min(fr)))
        flags = set()
        for t in telem:
            for f in t.get("throttled_flags", []):
                flags.add(f)
        if t1.get("throttled_raw"):
            L("    get_throttled     %s" % t1["throttled_raw"])
        if flags:
            L("    *** BANDERAS: %s" % "; ".join(sorted(flags)))
        elif t1.get("throttled_raw"):
            L("    sin throttling ni under-voltage")
        else:
            L("    vcgencmd no disponible en esta maquina")
        L("")

    ver = veredicto(s_alg)
    L("  REGLA DEL VEREDICTO (fijada antes de medir, no se mueve)")
    L("    Gobierna SOLO T_algorithm. La camara y la edad de frame se reportan")
    L("    aparte: son fallas distintas y piden soluciones distintas.")
    L("    ROJO      si p50 >= %.0f ms  o  frames>30ms >= %.0f %%"
      % (V_ROJO_P50, V_ROJO_PCT30))
    L("    VERDE     si p95 < %.0f ms  y  p99 < %.0f ms  y  frames>30ms < %.0f %%"
      % (V_VERDE_P95, V_VERDE_P99, V_VERDE_PCT30))
    L("    AMARILLO  cualquier otro caso")
    L("")
    L("  VEREDICTO: %s" % ver)
    if not env["es_raspberry"]:
        L("  (sobre una NO-Pi el veredicto es solo un ensayo del banco)")
    L("")
    L("=" * 78)
    return ver


# --------------------------------------------------------------------------
# CAMARA REAL (opcional, solo tiene sentido en la Pi con la camara conectada)
#
# Correccion metodologica pedida por ChatGPT en #138: con un hilo de captura
# asincrono, medir `read() + algoritmo` OCULTA LA EDAD DEL FRAME. El consumidor
# puede recibir al instante una imagen capturada N periodos antes: el throughput
# se ve excelente mientras la latencia sensor->actuador es peor.
#
# Por eso se separan TRES numeros y nunca se mezclan:
#
#   T_algorithm    frame ya disponible -> target/steer listo. Es lo que mide el
#                  banco de replay, y es lo UNICO que gobierna el veredicto.
#   T_frame_age    edad del frame al empezar a procesarlo, con timestamp
#                  monotonico estampado por el hilo apenas V4L2 entrega el frame.
#   T_observed     frame_age + algorithm. Aproximacion reproducible de
#                  entrega-de-camara -> comando. NO es foton->comando: no
#                  tenemos timestamp del sensor ni del USB.
# --------------------------------------------------------------------------
class CamaraBanco(object):
    """Copia DE BANCO del patron de camthreader.WebcamVideoStream, con numero
    de secuencia y timestamp monotonico de captura.

    NO modifica camthreader.py: el de produccion queda intacto. La unica
    diferencia es la instrumentacion (seq + t_cap) y una Condition para poder
    esperar frame nuevo en vez de girar en vacio.
    """

    def __init__(self, src, ancho, alto):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
        self.cv = threading.Condition()
        self.frame = None
        self.seq = 0
        self.t_cap = 0
        self.stopped = False
        self.fallos = 0
        self.hilo = None
        ok, fr = self.stream.read()
        if ok:
            self.frame, self.seq, self.t_cap = fr, 1, NS()

    def abierta(self):
        return self.stream.isOpened()

    def real(self):
        return (self.stream.get(cv2.CAP_PROP_FRAME_WIDTH),
                self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT),
                self.stream.get(cv2.CAP_PROP_FPS))

    def start(self):
        self.hilo = threading.Thread(target=self._loop, daemon=True)
        self.hilo.start()
        return self

    def _loop(self):
        while not self.stopped:
            ok, fr = self.stream.read()
            t = NS()
            if not ok:
                self.fallos += 1
                continue
            with self.cv:
                self.frame = fr
                self.seq += 1
                self.t_cap = t
                self.cv.notify_all()

    def leer(self):
        """Igual que camthreader: devuelve el ultimo frame, aunque ya se haya
        procesado. Es el patron que usa hoy el loop de produccion."""
        with self.cv:
            if self.frame is None:
                return None, -1, 0
            return self.frame.copy(), self.seq, self.t_cap

    def leer_nuevo(self, ultimo, timeout=2.0):
        """Espera a que haya un frame con seq distinto de `ultimo`."""
        with self.cv:
            ok = self.cv.wait_for(
                lambda: self.seq != ultimo or self.stopped, timeout)
            if not ok or self.frame is None:
                return None, ultimo, 0
            return self.frame.copy(), self.seq, self.t_cap

    def stop(self):
        self.stopped = True
        with self.cv:
            self.cv.notify_all()
        if self.hilo is not None:
            self.hilo.join(timeout=2.0)
        self.stream.release()


def _pasada_camara(SinBranch, v2, cam, n, esperar_nuevo):
    tr = SinBranch(FPS_NOMINAL)
    salto = min(60, max(1, n // 5))
    edad_todos, edad_nuevos, alg, obs = [], [], [], []
    repetidos = 0
    saltados = 0
    ult = -1
    seq0 = None
    t0 = None
    seq_f = None
    t_f = None
    for i in range(n):
        if esperar_nuevo:
            fr, seq, tcap = cam.leer_nuevo(ult)
        else:
            fr, seq, tcap = cam.leer()
        if fr is None:
            break
        t_ini = NS()
        edad = t_ini - tcap
        g = v2.frame_pi(fr)
        tr.step(g)
        t_fin = NS()
        nuevo = (seq != ult)
        if not nuevo:
            repetidos += 1
        elif ult >= 0 and seq > ult + 1:
            saltados += (seq - ult - 1)
        ult = seq
        if i >= salto:
            if t0 is None:
                t0, seq0 = t_ini, seq
            edad_todos.append(edad)
            alg.append(t_fin - t_ini)
            obs.append(edad + (t_fin - t_ini))
            if nuevo:
                edad_nuevos.append(edad)
            seq_f, t_f = seq, t_fin
    fps_cam = None
    if seq0 is not None and seq_f is not None and t_f > t0:
        fps_cam = (seq_f - seq0) / ((t_f - t0) / 1e9)
    n_med = len(alg)
    return {
        "modo": "esperar_frame_nuevo" if esperar_nuevo else "ultimo_disponible",
        "iteraciones": n_med,
        "T_algorithm": stats_ms(alg),
        "T_frame_age_todos": stats_ms(edad_todos),
        "T_frame_age_nuevos": stats_ms(edad_nuevos),
        "T_observed": stats_ms(obs),
        "frames_repetidos": repetidos,
        "frames_repetidos_pct": (100.0 * repetidos / n_med) if n_med else 0.0,
        "seq_saltados": saltados,
        "fps_camara_observado": fps_cam,
        "lecturas_fallidas_del_hilo": cam.fallos,
    }


def medir_camara(SinBranch, v2, n, indice, ancho, alto):
    cam = CamaraBanco(indice, ancho, alto)
    if not cam.abierta():
        cam.stop()
        return {"error": "no se pudo abrir el dispositivo %s" % indice}
    real = cam.real()
    cam.start()
    time.sleep(0.5)                      # que el hilo llene el primer frame
    out = {
        "dispositivo": indice,
        "pedido": [ancho, alto],
        "real_wxh_fps": real,
        "nota": ("T_observed NO es foton->comando: no hay timestamp del sensor "
                 "ni del USB. El veredicto del banco NO usa estos numeros."),
    }
    # Patron de produccion actual: tomar siempre el ultimo disponible.
    out["libre"] = _pasada_camara(SinBranch, v2, cam, n, False)
    # Patron recomendado: esperar frame nuevo (no reprocesar el mismo seq).
    out["nuevo"] = _pasada_camara(SinBranch, v2, cam, n, True)
    cam.stop()
    return out


def imprimir_camara(c):
    print("")
    print("  CAMARA REAL  (fuera del veredicto: son fallas distintas)")
    if "error" in c:
        print("    %s" % c["error"])
        return
    print("    pedido %sx%s   real %s" % (c["pedido"][0], c["pedido"][1],
                                          c["real_wxh_fps"]))
    for clave, titulo in (("libre", "ultimo disponible (patron actual)"),
                          ("nuevo", "esperar frame nuevo (recomendado)")):
        p = c.get(clave)
        if not p or not p["T_algorithm"].get("n"):
            continue
        print("")
        print("    -- %s --   %d iteraciones" % (titulo, p["iteraciones"]))
        print("       fps de camara observado   %s"
              % ("%.2f" % p["fps_camara_observado"]
                 if p["fps_camara_observado"] else "-"))
        print("       frames reprocesados       %d  (%.1f %%)"
              % (p["frames_repetidos"], p["frames_repetidos_pct"]))
        print("       seq saltados              %d" % p["seq_saltados"])
        print("       %-22s %8s %8s %8s %8s"
              % ("", "media", "p50", "p95", "max"))
        for k in ("T_algorithm", "T_frame_age_nuevos", "T_frame_age_todos",
                  "T_observed"):
            s = p[k]
            if not s.get("n"):
                continue
            print("       %-22s %8.3f %8.3f %8.3f %8.3f ms"
                  % (k, s["media"], s["p50"], s["p95"], s["max"]))
    print("")
    print("    LECTURA: si T_algorithm es VERDE pero T_frame_age es alto, el")
    print("    problema es la captura, NO el skeleton. Optimizar el algoritmo")
    print("    en ese caso seria un error.")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Runtime real de la candidata NUEVO CODE V1 RC")
    ap.add_argument("--modo", default="completo",
                    choices=["rapido", "completo", "sostenido"])
    ap.add_argument("--minutos", type=float, default=8.0,
                    help="solo en modo sostenido")
    ap.add_argument("--warmup", type=int, default=150,
                    help="frames descartados al principio de cada video")
    ap.add_argument("--videos", default=None,
                    help="lista separada por comas; pisa el modo")
    ap.add_argument("--hilos", type=int, default=None,
                    help="cv2.setNumThreads(N). Por defecto no se toca.")
    ap.add_argument("--telemetria-s", type=float, default=10.0,
                    dest="telemetria_s")
    ap.add_argument("--sin-verificar", action="store_true",
                    dest="sin_verificar")
    ap.add_argument("--json", default=None)
    ap.add_argument("--csv", default=None,
                    help="volcado por frame de todas las etapas (ns)")
    ap.add_argument("--camara", type=int, default=0,
                    help="N frames de camara REAL (0 = no medir)")
    ap.add_argument("--camara-indice", type=int, default=0,
                    dest="camara_indice")
    ap.add_argument("--camara-wh", default="160x120", dest="camara_wh")
    a = ap.parse_args()

    if a.hilos is not None:
        cv2.setNumThreads(a.hilos)

    v4, v3, v2 = cargar()
    try:
        sys.path.insert(0, AQUI)
        import ab_v2_v3_v4 as AB
        autonomos = list(AB.AUTONOMOS)
    except Exception:
        autonomos = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
                     "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
                     "con_planner.avi", "con_planner2.avi"]

    if a.videos:
        videos = [x.strip() for x in a.videos.split(",") if x.strip()]
    elif a.modo == "rapido":
        videos = ["hist.avi", "lineal.avi", "roi_auto.avi"]
    else:
        videos = autonomos
    videos = [v for v in videos if os.path.exists(os.path.join(AQUI, v))]
    if not videos:
        print("*** no hay videos. Corre esto dentro de final_rpi/ con los .avi")
        return 2

    env = entorno()
    if str(env["scikit_image"]).startswith("AUSENTE"):
        print("")
        print("*** scikit-image NO esta instalado. La candidata no corre.")
        print("    sudo apt install python3-skimage    "
              "(o pip install scikit-image)")
        print("    %s" % env["scikit_image"])
        return 3

    SinBranch = hacer_sinbranch(v4)

    # --- verificacion de equivalencia + overhead -----------------------------
    overhead = {"equivalente": None}
    control = "hist.avi" if "hist.avi" in videos else videos[0]
    ruta_ctl = os.path.join(AQUI, control)
    if not a.sin_verificar:
        print("  verificando equivalencia y overhead sobre %s ..." % control)
        limpio = serie_targets(SinBranch, v2, ruta_ctl, FPS_NOMINAL, 900)
        ns_limpio = medir_limpio(SinBranch, v2, ruta_ctl, FPS_NOMINAL, 150, 900)

    faltan = instrumentar(v4, v3, v2)

    if not a.sin_verificar:
        P.activo = True
        P.frame_nuevo()
        instr = serie_targets(SinBranch, v2, ruta_ctl, FPS_NOMINAL, 900)
        P.activo = False
        iguales = sum(1 for x, y in zip(limpio, instr) if x == y)
        overhead.update(
            video=control, n=len(limpio), iguales=iguales,
            equivalente=(len(limpio) == len(instr) and iguales == len(limpio)))
        if not overhead["equivalente"]:
            desespiar()
            print("*** ABORTA: la instrumentacion cambia el resultado "
                  "(%d/%d targets iguales)." % (iguales, len(limpio)))
            return 4
        buf_o = Buffer(1024)
        medir_video(SinBranch, v2, ruta_ctl, FPS_NOMINAL, buf_o, 150,
                    None, 1e9, limite=750)
        s_o, _ = resumen_total(buf_o.datos())
        p50_l = float(np.percentile(ns_limpio, 50)) / 1e6
        overhead.update(
            p50_limpio_ms=p50_l, p50_instr_ms=s_o["p50"],
            delta_ms=s_o["p50"] - p50_l,
            delta_pct=100.0 * (s_o["p50"] - p50_l) / p50_l if p50_l else 0.0)

    # --- medicion principal --------------------------------------------------
    buf = Buffer(16384)
    telem = [telemetria(True)]
    por_video = []
    t_ini = time.time()
    ns_telem = 0
    pasada = 0
    while True:
        pasada += 1
        for v in videos:
            n0 = buf.n
            m, nt = medir_video(SinBranch, v2, os.path.join(AQUI, v),
                                FPS_NOMINAL, buf, a.warmup, telem,
                                a.telemetria_s)
            ns_telem += nt
            d = buf.datos()[n0:]
            if d.shape[0]:
                s, _ = resumen_total(d)
                por_video.append(dict(
                    video=v if pasada == 1 else "%s #%d" % (v, pasada),
                    frames=int(d.shape[0]), media=s["media"], p50=s["p50"],
                    p95=s["p95"], max=s["max"]))
            print("  ... %-20s pasada %d  %5d frames  %.1f s"
                  % (v, pasada, m, time.time() - t_ini))
        if a.modo != "sostenido":
            break
        if (time.time() - t_ini) >= a.minutos * 60.0:
            break
    telem.append(telemetria(True))
    desespiar()

    datos = buf.datos()
    if datos.shape[0] == 0:
        print("*** 0 frames medidos: subi --warmup o revisa los videos")
        return 5
    s_alg, alg_ns = resumen_total(datos)
    wall = time.time() - t_ini - ns_telem / 1e9

    ver = imprimir(env, faltan, por_video, datos, s_alg, overhead, telem, a)

    salida = dict(
        entorno=env, argumentos=vars(a), videos=videos,
        frames=int(datos.shape[0]), veredicto=ver,
        algoritmo=s_alg, por_video=por_video, telemetria=telem,
        overhead=overhead, etapas_no_instrumentadas=faltan,
        wall_s=wall,
        etapas=dict((e, stats_ms(datos[:, IDX[e]])) for e in ETAPAS),
        umbrales=dict(presupuesto_ms=PRESUPUESTO_MS,
                      verde_p95=V_VERDE_P95, verde_p99=V_VERDE_P99,
                      verde_pct30=V_VERDE_PCT30,
                      rojo_p50=V_ROJO_P50, rojo_pct30=V_ROJO_PCT30),
    )

    if a.camara > 0:
        print("  midiendo camara real (%d frames)..." % a.camara)
        try:
            w, h = [int(x) for x in a.camara_wh.lower().split("x")]
        except Exception:
            w, h = 160, 120
        salida["camara"] = medir_camara(SinBranch, v2, a.camara,
                                        a.camara_indice, w, h)
        imprimir_camara(salida["camara"])
        print("")

    destino = a.json or os.path.join(
        AQUI, "bench_runtime_%s.json" % (env["hostname"] or "host"))
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=1, default=str)
    print("  JSON: %s" % destino)

    if a.csv:
        with open(a.csv, "w", encoding="utf-8") as f:
            f.write("frame," + ",".join(ETAPAS) + ",algoritmo_ns\n")
            for i in range(datos.shape[0]):
                f.write("%d,%s,%d\n" % (
                    i, ",".join(str(int(x)) for x in datos[i]),
                    int(alg_ns[i])))
        print("  CSV : %s" % a.csv)

    return 0


if __name__ == "__main__":
    sys.exit(main())
