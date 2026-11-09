# -*- coding: utf-8 -*-
"""
simular.py - corre el main.py de la Pi SIN robot, cuadro por cuadro, sobre una grabacion GRABAR_CRUDO.

    python simular.py CARPETA_CRUDO salida.csv [desde] [hasta]   (las variables de main.py van por entorno)

- La camara entrega los PNG de la grabacion (los mismos cuadros que vio el robot).
- El reloj (time.monotonic/time.time) es el de la grabacion: las ventanas en segundos dan igual.
- Una Teensy de mentira contesta lo que la Pi espera: 0xF9 al arrancar, el aviso de rampa tal como se
  grabo, 0xEF 11 cuadros despues de pedir el retroceso (GS=4), 0xED 23 cuadros despues de una CURVA,
  0xEE 10 cuadros despues de entrar al gap.
Ojo: es a lazo abierto. Los cuadros son los de la corrida real; si la simulacion decide distinto, lo que
viene despues ya no corresponde a lo que el robot hubiera visto. Sirve para comparar el PRIMER cuadro en
que algo cambia, no lo que pasa despues.

Con SIM_VIDEO=<video GRABAR> lee los cuadros del panel izquierdo del video ([1::2, 1::2]) en vez de los PNG
(copia del simulador de Downloads/SIMULADOR_PI_2026-10-17 con ese agregado, 1-nov-2026).
"""
import csv
import os
import sys
import time as _time
import types

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[1]
SALIDA = sys.argv[2]
DESDE = int(sys.argv[3]) if len(sys.argv) > 3 else 1
HASTA = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9

orig = [x for x in csv.DictReader(open(os.path.join(D, "cuadros.csv"))) if DESDE <= int(x["n"]) <= HASTA]


# Cuando contesto la Teensy real (deducido de las etiquetas): 0xEF en el ultimo cuadro de
# 'recup-espera-retro-ack'; 0xEE 10 cuadros despues de entrar al gap (o 3 antes de salir).
Q0 = [x["quien"] for x in orig]
ACK_EF = {i for i in range(len(Q0) - 1) if Q0[i] == "recup-espera-retro-ack" and Q0[i + 1] != "recup-espera-retro-ack"}
ACK_EE = set()
i = 0
while i < len(Q0):
    if Q0[i] == "gap-busca-negro":
        j = i
        while j < len(Q0) and Q0[j] == "gap-busca-negro":
            j += 1
        ACK_EE.add(max(i, j - 4))
        i = j
    else:
        i += 1


class Fin(BaseException):
    pass


# ---------------- reloj ----------------
RELOJ = {"t": float(orig[0]["t"]) + 1000.0}
_time.monotonic = lambda: RELOJ["t"]
_time.time = lambda: RELOJ["t"]
_time.perf_counter = lambda: RELOJ["t"]
_sleep_real = _time.sleep
_time.sleep = lambda s: RELOJ.__setitem__("t", RELOJ["t"] + max(0.0, s))

# ---------------- Teensy de mentira ----------------
ENTRADA = []          # bytes que la Pi va a leer
PROG = []             # (indice_cuadro, byte)
EST = {"i": -1, "gs_prev": 0, "q_prev": "", "rampa": None}
REG = []              # lo que mando la Pi en cada cuadro


def programar(desde_ahora, b):
    PROG.append((EST["i"] + desde_ahora, b))


class SerialFalso(object):
    def __init__(self, *a, **k):
        self.buf = bytearray()

    @property
    def in_waiting(self):
        return len(ENTRADA)

    def read(self, n=1):
        out = bytes(ENTRADA[:n])
        del ENTRADA[:n]
        return out

    def write(self, data):
        data = bytes(data)
        # trama [255, speed, 254, angle, 253, gs, 252, silver]
        if len(data) == 8 and data[0] == 255 and data[2] == 254 and data[4] == 253:
            gs = data[5]
            i = EST["i"]
            if gs == 4 and EST["gs_prev"] != 4 and not any(i <= k <= i + 25 for k in ACK_EF):
                programar(11, 0xEF)            # episodio que la corrida real no tuvo
            if gs == 18 and EST["gs_prev"] != 18 and not any(i - 10 <= k <= i + 25 for k in ACK_EE):
                programar(10, 0xEE)
            EST["gs_prev"] = gs
        return len(data)

    def flush(self):
        pass


serial_mod = types.ModuleType("serial")
serial_mod.Serial = SerialFalso
serial_mod.SerialException = Exception
serial_mod.SerialTimeoutException = Exception
sys.modules["serial"] = serial_mod


# ---------------- camara de mentira ----------------
_VID = {"cap": None, "n": 0}


def _leer_video(n):
    """Cuadro n (1 = primero) del video GRABAR: el panel izquierdo [1::2, 1::2] es lo que vio la Pi."""
    if _VID["cap"] is None or n != _VID["n"] + 1:
        _VID["cap"] = cv2.VideoCapture(os.environ["SIM_VIDEO"])
        _VID["cap"].set(cv2.CAP_PROP_POS_FRAMES, n - 1)
    ok, f = _VID["cap"].read()
    _VID["n"] = n
    return f[1::2, 1:320:2][:120, :160].copy()


class CamaraFalsa(object):
    def __init__(self, src=0, width=160, height=120):
        pass

    def start(self):
        return self

    def read(self):
        EST["i"] += 1
        i = EST["i"]
        if i >= len(orig):
            raise Fin()
        x = orig[i]
        RELOJ["t"] = float(x["t"]) + 1000.0
        # bytes programados para este cuadro
        for (k, b) in [p for p in PROG if p[0] <= i]:
            ENTRADA.append(b)
            PROG.remove((k, b))
        if i in ACK_EF:
            ENTRADA.append(0xEF)
        if i in ACK_EE:
            ENTRADA.append(0xEE)
        # aviso de rampa: al cambiar y cada 0,5 s, como la Teensy
        # la columna "rampa" del cuadro i+1 es lo que se leyo al final del cuadro i
        xs = orig[i + 1] if i + 1 < len(orig) else x
        r = int(xs["rampa"]) if xs["rampa"] not in ("", None) else 0
        if r != EST["rampa"] or RELOJ["t"] - EST.get("rampa_t", 0) >= 0.5:
            ENTRADA.append({1: 0xF2, -1: 0xF3}.get(r, 0xF4))
            EST["rampa"] = r
            EST["rampa_t"] = RELOJ["t"]
        fr = _leer_video(int(x["n"])) if os.environ.get("SIM_VIDEO") else cv2.imread(os.path.join(D, "f_%06d.png" % int(x["n"])))
        big = cv2.resize(fr, (640, 480), interpolation=cv2.INTER_NEAREST)
        return cv2.rotate(big, cv2.ROTATE_180)

    def stop(self):
        pass

    def get_dim(self):
        return (640, 480)


cam_mod = types.ModuleType("camthreader")
cam_mod.WebcamVideoStream = CamaraFalsa
sys.modules["camthreader"] = cam_mod


# ---------------- modelo de mentira ----------------
class InterpreteFalso(object):
    def __init__(self, *a, **k):
        pass

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [{"index": 0, "dtype": np.uint8, "shape": np.array([1, 320, 320, 3]), "quantization": (0.0, 0)}]

    def get_output_details(self):
        return [{"index": 1, "dtype": np.float32, "shape": np.array([1, 8, 2100]), "quantization": (0.0, 0)}]

    def set_tensor(self, *a):
        pass

    def invoke(self):
        pass

    def get_tensor(self, i):
        return np.zeros((1, 8, 2100), np.float32)


lit = types.ModuleType("ai_edge_litert")
lit_i = types.ModuleType("ai_edge_litert.interpreter")
lit_i.Interpreter = InterpreteFalso
lit.interpreter = lit_i
sys.modules["ai_edge_litert"] = lit
sys.modules["ai_edge_litert.interpreter"] = lit_i

os.environ.pop("DISPLAY", None)
os.environ.pop("GRABAR", None)
os.environ["GRABAR_CRUDO"] = "registro"          # engancha el hook; abajo se reemplaza por el registro
sys.path.insert(0, AQUI)
os.chdir(AQUI)
ENTRADA.append(0xF9)                              # la Teensy dice "listo": pasa a modo linea

import io, contextlib
_log = io.StringIO()
with contextlib.redirect_stdout(_log):
    import main as M


def registrar(frame_bgr, green_mask, black_mask, speed, angle, green_state, silver, quien):
    i = EST["i"]
    q = str(quien)
    if q == "recup-CURVA" and EST["q_prev"] != "recup-CURVA":
        programar(23, 0xED)
    EST["q_prev"] = q
    REG.append((int(orig[i]["n"]), q, float(angle), int(green_state), int(speed)))


M._grabar_crudo = registrar

# registro de lo que clasifica el arbitro en cada cuadro despues del retroceso
import camino_loss_arbiter as CLA
CLASIF = []
_clasif_orig = CLA.classify_frame
_obs_post_orig = CLA.LossArbiter.observe_post
EST["post"] = False


def _clasif(cf, res):
    o = _clasif_orig(cf, res)
    if EST["post"]:
        rr = res or {}
        CLASIF.append((int(orig[EST["i"]]["n"]), o.get("raw"), o.get("reason"), o.get("heading"), o.get("dx"), o.get("dy"),
                       o.get("maxexc"), o.get("reach"), o.get("shiftfar"), bool((cf or {}).get("confiable")),
                       len(rr.get("path") or []), rr.get("start"), rr.get("target")))
    return o


def _obs_post(self, cf, res, now=None):
    EST["post"] = True
    try:
        return _obs_post_orig(self, cf, res, now)
    finally:
        EST["post"] = False


CLA.classify_frame = _clasif
CLA.LossArbiter.observe_post = _obs_post
try:
    with contextlib.redirect_stdout(_log):
        M.main()
except Fin:
    pass

open(SALIDA.replace(".csv", ".log"), "w", encoding="utf-8").write(_log.getvalue())
ref = {int(x["n"]): x for x in orig}
with open(SALIDA, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["n", "quien", "angle", "green_state", "quien_robot", "angle_robot", "gs_robot"])
    for n, q, a, gs, sp in REG:
        o = ref[n]
        w.writerow([n, q, "%.1f" % a, gs, o["quien"], o["angle"], o["green_state"]])
with open(SALIDA.replace(".csv", "_clasif.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["n", "raw", "razon", "heading", "dx", "dy", "maxexc", "reach", "shiftfar", "confiable", "npath", "start", "target"])
    for c in CLASIF:
        w.writerow(c)
igual = sum(1 for n, q, a, gs, sp in REG if q == ref[n]["quien"])
print("cuadros %d | misma etiqueta que el robot: %d (%.1f %%)" % (len(REG), igual, 100.0 * igual / max(1, len(REG))))
