# -*- coding: utf-8 -*-
"""
PREFLIGHT DEL SABADO - se corre ANTES de tocar el robot.

Quedan como maximo DOS sabados con el robot. Media hora perdida en descubrir
que falta scikit-image, que el servicio tiene la camara tomada, que la SD esta
llena o que la Pi viene con under-voltage de la semana pasada es media hora que
no se recupera.

Esto NO mueve el robot. NO escribe en el serie. Solo mira.

    python3 preflight_sabado.py

Salida: una linea GO / NO-GO por item y un veredicto final. Codigo de salida 0
si se puede arrancar, 1 si hay algo bloqueante.

Opcional, si se quiere confirmar que el puerto de la Teensy abre de verdad
(abre y LEE, nunca escribe):

    python3 preflight_sabado.py --serial-abrir
"""

import argparse
import glob
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAMA_ESPERADA = "collab/nuevo-code"

AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]

# Bit -> descripcion, de vcgencmd get_throttled
THROT = [(0, "under-voltage AHORA"), (1, "frecuencia capada AHORA"),
         (2, "throttling AHORA"), (3, "limite de temperatura AHORA"),
         (16, "hubo under-voltage"), (17, "hubo capado de frecuencia"),
         (18, "hubo throttling"), (19, "hubo limite de temperatura")]

RES = []


def item(nombre, estado, detalle="", bloqueante=True):
    """estado: True=GO, False=NO-GO, None=aviso."""
    RES.append(dict(nombre=nombre, estado=estado, detalle=detalle,
                    bloqueante=bloqueante))
    marca = {True: "  GO  ", False: "NO-GO ", None: " aviso"}[estado]
    print("  [%s] %-34s %s" % (marca, nombre, detalle))


def leer(p):
    try:
        with open(p, "rb") as f:
            return f.read().decode("utf-8", "replace").strip("\x00\n\r ")
    except Exception:
        return None


def cmd(args, timeout=6):
    try:
        return subprocess.check_output(
            args, stderr=subprocess.DEVNULL, timeout=timeout
        ).decode("utf-8", "replace").strip()
    except Exception:
        return None


# --------------------------------------------------------------------------
def chk_git():
    rama = cmd(["git", "-C", AQUI, "rev-parse", "--abbrev-ref", "HEAD"])
    sha = cmd(["git", "-C", AQUI, "rev-parse", "HEAD"])
    sucio = cmd(["git", "-C", AQUI, "status", "--porcelain",
                 "--untracked-files=no"])
    if sha is None:
        item("git", False, "no es un repo git o falta el binario")
        return
    item("git rama", rama == RAMA_ESPERADA,
         "%s (esperada %s)" % (rama, RAMA_ESPERADA))
    item("git SHA", True, sha[:10] + "   ANOTAR ESTE SHA EN EL LOG")
    item("git arbol limpio", not sucio,
         "sucio: no se sabe que codigo corrio" if sucio else "sin cambios")
    cmd(["git", "-C", AQUI, "fetch", "--quiet", "origin"], timeout=25)
    tras = cmd(["git", "-C", AQUI, "rev-list", "--count",
                "HEAD..origin/" + RAMA_ESPERADA])
    if tras is not None:
        item("git al dia con origin", tras == "0",
             "faltan %s commits del remoto" % tras if tras != "0" else "si",
             bloqueante=False)


def chk_dependencias():
    import numpy
    item("numpy", True, numpy.__version__)
    try:
        import cv2
        item("opencv", True, "%s   hilos %d" % (cv2.__version__,
                                                cv2.getNumThreads()))
    except Exception as e:
        item("opencv", False, str(e))
    try:
        import skimage
        item("scikit-image", True, skimage.__version__ +
             "   (la candidata NO corre sin esto)")
    except Exception:
        item("scikit-image", False,
             "AUSENTE -> sudo apt install python3-skimage")
    try:
        import serial
        item("pyserial", True, serial.__version__, bloqueante=False)
    except Exception:
        item("pyserial", None, "ausente (solo hace falta para hablar "
             "con la Teensy)", bloqueante=False)
    item("python", sys.version_info >= (3, 7), sys.version.split()[0])


def chk_pi():
    modelo = leer("/proc/device-tree/model")
    es_pi = bool(modelo and "raspberry" in modelo.lower())
    item("hardware", es_pi if es_pi else None,
         modelo or "no es una Pi (%s)" % platform.machine(),
         bloqueante=False)
    if not es_pi:
        item("temperatura", None, "no medible fuera de la Pi", bloqueante=False)
        return

    th = cmd(["vcgencmd", "get_throttled"])
    if th and "=" in th:
        v = int(th.split("=", 1)[1], 16)
        flags = [d for b, d in THROT if v & (1 << b)]
        ahora = [d for b, d in THROT if b < 4 and v & (1 << b)]
        item("throttling / alimentacion", not ahora,
             th + ("   " + "; ".join(flags) if flags else "   limpio"))
        if flags and not ahora:
            item("historial de energia", None,
                 "hubo eventos antes: " + "; ".join(flags), bloqueante=False)
    else:
        item("vcgencmd", None, "no disponible", bloqueante=False)

    t = leer("/sys/class/thermal/thermal_zone0/temp")
    if t:
        c = float(t) / 1000.0
        item("temperatura de arranque", c < 70.0, "%.1f C" % c)
    gov = leer("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    fmax = leer("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
    item("governor", True, "%s   max %s kHz" % (gov, fmax), bloqueante=False)

    try:
        u = shutil.disk_usage(AQUI)
        libre_gb = u.free / 1e9
        item("espacio en disco", libre_gb > 1.0, "%.2f GB libres" % libre_gb)
    except Exception as e:
        item("espacio en disco", None, str(e), bloqueante=False)

    ntp = cmd(["timedatectl", "show", "-p", "NTPSynchronized", "--value"])
    item("reloj", ntp == "yes" if ntp else None,
         "NTP %s   ahora %s" % (ntp, time.strftime("%Y-%m-%d %H:%M:%S")),
         bloqueante=False)


def chk_servicio():
    est = cmd(["systemctl", "is-active", "iita-robot"])
    if est is None:
        item("servicio iita-robot", None, "systemctl no disponible",
             bloqueante=False)
        return
    item("servicio iita-robot parado", est != "active",
         "%s  (si esta activo tiene la camara tomada: "
         "sudo systemctl stop iita-robot)" % est)


def chk_camara(a):
    import cv2
    cap = cv2.VideoCapture(a.camara)
    if not cap.isOpened():
        item("camara abre", False, "dispositivo %d no abre" % a.camara)
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.ancho)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.alto)
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    item("camara abre", True, "dispositivo %d" % a.camara)
    item("resolucion", (w, h) == (a.ancho, a.alto),
         "pedida %dx%d  real %dx%d" % (a.ancho, a.alto, w, h),
         bloqueante=False)
    for _ in range(10):
        cap.read()
    n = 0
    nulos = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < a.seg_camara:
        ok, fr = cap.read()
        if ok and fr is not None:
            n += 1
        else:
            nulos += 1
    dt = time.perf_counter() - t0
    cap.release()
    fps = n / dt if dt > 0 else 0.0
    item("fps real de camara", fps >= 25.0,
         "%.2f fps medidos en %.1f s   (los autonomos son 33,33; "
         "NO creerle al header)" % (fps, dt))
    item("frames nulos", nulos == 0, "%d nulos de %d" % (nulos, n + nulos),
         bloqueante=False)


def chk_serial(a):
    puertos = (sorted(glob.glob("/dev/ttyAMA*")) + sorted(glob.glob("/dev/serial*"))
               + sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*")))
    if not puertos:
        item("puerto de la Teensy", False if os.name != "nt" else None,
             "no aparece ningun /dev/tty{AMA,USB,ACM}* ni /dev/serial*")
        return
    item("puerto de la Teensy", True, ", ".join(puertos))
    p = puertos[0]
    try:
        ok = os.access(p, os.R_OK | os.W_OK)
        item("permisos del puerto", ok,
             p + ("" if ok else "   -> sudo usermod -aG dialout $USER"))
    except Exception:
        pass
    if not a.serial_abrir:
        item("apertura del puerto", None,
             "no probada (usar --serial-abrir). NUNCA se escribe.",
             bloqueante=False)
        return
    try:
        import serial
        s = serial.Serial(p, 115200, timeout=1.0)
        time.sleep(1.0)
        n = s.in_waiting
        datos = s.read(n) if n else b""
        s.close()
        item("apertura del puerto", True,
             "%s abrio; %d bytes en 1 s (solo lectura)" % (p, len(datos)))
    except Exception as e:
        item("apertura del puerto", False, str(e))


def chk_material():
    faltan = [v for v in AUTONOMOS if not os.path.exists(os.path.join(AQUI, v))]
    item("videos autonomos", not faltan,
         "los 10 presentes" if not faltan else "faltan: " + ", ".join(faltan),
         bloqueante=False)
    for f in ("bench_runtime.py", "arquitectura_minima.py", "nuevo_code_v2.py",
              "nuevo_code_v3.py", "nuevo_code_v4.py", "medir_eje.py"):
        if not os.path.exists(os.path.join(AQUI, f)):
            item("archivo " + f, False, "FALTA")
            return
    item("archivos de la candidata", True, "completos")


def chk_candidata():
    """Que la candidata levante y procese un frame de verdad."""
    try:
        import cv2
        import numpy as np
        sp = importlib.util.spec_from_file_location(
            "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
        v4 = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(v4)
        v2 = v4.v3.v2

        class _N(object):
            def step(self, p, s):
                return p, "PASA"

        class SB(v4.NuevoCodeV4):
            def __init__(self, fps):
                v4.NuevoCodeV4.__init__(self, fps)
                self.branch_guard = _N()

        ruta = os.path.join(AQUI, "hist.avi")
        if not os.path.exists(ruta):
            item("candidata procesa un frame", None, "falta hist.avi",
                 bloqueante=False)
            return
        cap = cv2.VideoCapture(ruta)
        tr = SB(100.0 / 3.0)
        okf = 0
        t0 = time.perf_counter()
        for _ in range(60):
            ok, fr = cap.read()
            if not ok:
                break
            tr.step(v2.frame_pi(fr))
            okf += 1
        dt = (time.perf_counter() - t0) / max(okf, 1) * 1e3
        cap.release()
        item("candidata procesa frames", okf > 0,
             "%d frames, %.2f ms/frame (60 frames, sin warmup: "
             "NO es el benchmark)" % (okf, dt))
        del np
    except Exception as e:
        item("candidata procesa frames", False, "%s: %s"
             % (type(e).__name__, e))


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Preflight del sabado")
    ap.add_argument("--camara", type=int, default=0)
    ap.add_argument("--ancho", type=int, default=160)
    ap.add_argument("--alto", type=int, default=120)
    ap.add_argument("--seg-camara", type=float, default=3.0,
                    dest="seg_camara")
    ap.add_argument("--sin-camara", action="store_true", dest="sin_camara")
    ap.add_argument("--serial-abrir", action="store_true", dest="serial_abrir")
    a = ap.parse_args()

    print("")
    print("=" * 74)
    print("  PREFLIGHT DEL SABADO   %s   %s"
          % (time.strftime("%Y-%m-%d %H:%M:%S"), platform.node()))
    print("=" * 74)
    print("")
    print(" CODIGO")
    chk_git()
    chk_material()
    print("")
    print(" ENTORNO")
    chk_dependencias()
    chk_pi()
    print("")
    print(" HARDWARE")
    chk_servicio()
    if not a.sin_camara:
        try:
            chk_camara(a)
        except Exception as e:
            item("camara", False, "%s: %s" % (type(e).__name__, e))
    else:
        item("camara", None, "salteada por --sin-camara", bloqueante=False)
    chk_serial(a)
    print("")
    print(" CANDIDATA")
    chk_candidata()

    malos = [r for r in RES if r["estado"] is False and r["bloqueante"]]
    avisos = [r for r in RES if r["estado"] is None or
              (r["estado"] is False and not r["bloqueante"])]
    print("")
    print("-" * 74)
    if malos:
        print("  NO-GO. %d item(s) bloqueantes:" % len(malos))
        for r in malos:
            print("    - %s: %s" % (r["nombre"], r["detalle"]))
        print("")
        print("  Resolver esto ANTES de gastar tiempo de robot.")
    else:
        print("  GO. Ningun bloqueante.")
    if avisos:
        print("")
        print("  %d aviso(s) no bloqueantes:" % len(avisos))
        for r in avisos:
            print("    - %s: %s" % (r["nombre"], r["detalle"]))
    print("-" * 74)
    print("")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
