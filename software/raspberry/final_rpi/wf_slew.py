# -*- coding: utf-8 -*-
"""
WF_SLEW - la capa de COMANDO sobre CAMINO+MONO.

QUE SE PRUEBA
-------------
Dos cosas, las dos sobre el mismo tronco: la candidata SinBranch con CAMINO+MONO
(lo mejor medido hasta hoy). Ninguna toca la percepcion ni el target.

  A) LIMITADOR DE VELOCIDAD DE COMANDO (slew)
     `v1_slew.py` midio que sobre V1, a 1500 grados/s, el latigazo maximo baja
     de 88 a 45 sin costar nada. La candidata ya viene topeada por construccion
     a 27 px de salto por su SpatialTargetGuard, asi que aca puede no aportar.
     Hay que medirlo, no suponerlo.

  B) SOSTENER EL ANGULO EN EL HUECO (hold)
     El lazo de comando del replay (y el de `v1_slew.py`) pone el angulo en 0
     cuando no hay target. Eso mete un escalon artificial en cada hueco: el
     comando cae a neutro y despues tiene que volver a rampar desde 0. La
     variante sostiene el ULTIMO angulo durante el hueco, con limite de tiempo.

     Nota honesta sobre el codigo real: `ControlPreview.step` de
     nuevo_code_v3.py NO pone self.angle en 0 - devuelve control=None y se
     guarda el valor interno. El 0 lo pone el arnes de replay. Y `Main.py`
     (linea 922) en produccion ni siquiera manda 0 cuando pierde la linea:
     manda un barrido de busqueda de 65 grados. Por eso el escalon del hueco se
     reporta abajo bajo el MODELO EXPLICITO "el comando efectivo en el hueco es
     0", que es el que usa el arnes. Con otro downstream el numero cambia.

QUE PUEDE Y QUE NO PUEDE MOVER ESTE EXPERIMENTO
-----------------------------------------------
El target NO se toca. Por lo tanto disp, sin_aut, huecos y saltos>24 - que
`AB.metricas` calcula SOBRE LOS TARGETS - son INVARIANTES por construccion.
Que salgan +0 en la tabla no es un resultado: es el chequeo de que el espia no
se metio donde no debia. Lo unico que este experimento puede mover es:

    inversiones   signo del comando con banda muerta de 10 grados
    suav_t        mediana de |dsteer| entre frames CON TARGET los dos
    |ds| max      el latigazo maximo del comando (frames con comando)
    |ds|max T     idem pero SOLO entre pares que los dos tienen target. Aisla
                  el latigazo de PERCEPCION del artefacto del reset del hueco.
                  Sin este corte, "|ds| max" con slew mide el reencendido del
                  integrador desde 0 al salir del hueco, no la percepcion.
    sin_cmd       frames sin comando (los que el hold rellena)
    |ds| max ef.  latigazo del comando EFECTIVO (None -> 0), que es el que ve
                  el escalon del hueco. Es un maximo: un solo evento lo fija.
    esc_ef        CUENTOS de escalones > 24 grados en el comando efectivo. Es
                  la version de tasa del anterior, mucho menos fragil.

suav_t se mide solo entre frames que los dos tienen target a proposito: durante
un hold el comando es constante y las diferencias son 0, lo que desinflaria una
mediana calculada sobre todos los pares. Seria hacerse trampa.

FIDELIDAD - DOS NIVELES
-----------------------
  1) Espia de percepcion: con CAMINO y MONO apagados, el selector
     re-implementado tiene que reproducir el target de la candidata frame a
     frame. Una sola discrepancia y aborta. (Igual que camino_principal.py.)
  2) Capa de comando: con slew=sin y hold=0, la serie de steer tiene que ser
     IDENTICA a la formula base. Se verifica frame a frame y aborta.

PREREGISTRO (escrito antes de correr, no se toca despues)
---------------------------------------------------------
  Banda de slew (con hold=0):   sin, 1500, 1000, 500, 350 grados/s
  Banda de hold (con el slew elegido):  0 / 0,2 / 0,4 s
      + "inf" como LIMITE DIAGNOSTICO, declarado NO ELEGIBLE.

  CRITERIO DE ELECCION DEL SLEW
    duro   controles intactos: hist_exito 100/100, lineal_positivo 73/73,
           y el steer maximo de lineal_positivo sigue llegando a +89
           (>= 88,5). Ese +89 es correcto: el robot completo esa curva.
    obj    entre los que pasan el duro, el de MENOR |ds| max.
           Desempate: menor inversiones, despues menor suav_t.
    nulo   si ninguno baja |ds| max respecto de "sin", el veredicto es
           NO APORTA y queda "sin".

  CRITERIO DE ELECCION DEL HOLD
    duro   el mismo de arriba.
    obj    el hold MAS LARGO de la banda que baje |ds| max efectivo y no
           aumente ni |ds| max ni inversiones.
    nulo   si ninguno cumple, queda hold=0.

Replay OPEN-LOOP: esto mide el comando que la percepcion habria emitido sobre
video grabado. No dice nada sobre como habria doblado el robot.

    python wf_slew.py
"""

import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB

FPS = 100.0 / 3.0
CAP = {}
CHK = {"n": 0, "mal": 0}

# --- PREREGISTRO ----------------------------------------------------------
BANDA_SLEW = [None, 1500.0, 1000.0, 500.0, 350.0]
BANDA_HOLD = [0.0, 0.2, 0.4]
HOLD_DIAG = float("inf")          # limite diagnostico, NO elegible
SMAX_EXIGIDO = 88.5


# =========================== percepcion ===================================

def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3.v2


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


def es_ancestro(prev, ancla, cand):
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


def instalar(v2, cfg):
    """Espia reversible sobre path_target. Copiado de camino_principal.py."""
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
        pts, dist, prev, si = CAP["pts"], CAP["dist"], CAP["prev"], CAP["si"]
        sy, sx = pts[si]
        lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        fin = np.where(np.isfinite(dist))[0]
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            cands = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
                :min(30, len(fin))]

        if cfg["camino"] and len(fin):
            F = int(fin[int(np.argmax(dist[fin]))])
            cadena = set(o_r(prev, si, F) or [])
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub

        if cfg["mono"] and self.prev_target is not None and len(fin):
            ys = np.array([q[0] for q in pts])
            xs = np.array([q[1] for q in pts])
            dd = ((xs[fin] - self.prev_target[0]) ** 2
                  + (ys[fin] - self.prev_target[1]) ** 2)
            ancla = int(fin[int(np.argmin(dd))])
            adm = [i for i in cands if es_ancestro(prev, ancla, i)]
            if adm:
                cands = adm

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

        if not cfg["camino"] and not cfg["mono"]:
            CHK["n"] += 1
            if (abs(tx - res["target"][0]) > 1e-6
                    or abs(ty - res["target"][1]) > 1e-6):
                CHK["mal"] += 1
            return sk, res

        camino = o_r(prev, si, ti) or [si, ti]
        return sk, dict(
            start=res["start"], target=(float(tx), float(ty)),
            heading=math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6))),
            path=[(float(pts[i][1]), float(pts[i][0])) for i in camino])

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


def percibir(SinBranch, v2, ruta, fps, desde=0, hasta=10 ** 9):
    """Corre la percepcion UNA vez y cachea (target, estado) por frame.

    Ni el slew ni el hold realimentan la percepcion, asi que una sola pasada
    sirve para todas las variantes de comando. Eso es exacto, no aproximado.
    """
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    tr = SinBranch(fps)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        r = tr.step(v2.frame_pi(fr))
        if i >= desde:
            out.append((r.get("target"), r.get("state")))
        i += 1
    cap.release()
    return out


# =========================== capa de comando ==============================

def raw_de(t, v2):
    if t is None:
        return None
    return float(np.clip(-90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90.0, 90.0))


def comando(cache, v2, fps, slew_dps, hold_s):
    """Aplica slew y hold sobre la serie de targets ya percibida.

    slew_dps=None  -> sin limitador
    hold_s=0       -> comportamiento base: en el hueco se emite None y el
                      integrador vuelve a 0
    """
    maxd = None if slew_dps is None else float(slew_dps) / float(fps)
    if hold_s <= 0:
        hmax = 0
    elif not np.isfinite(hold_s):
        hmax = 10 ** 9
    else:
        hmax = int(round(hold_s * fps))
    ang = 0.0
    hn = 0
    out = []
    for t, st in cache:
        raw = raw_de(t, v2)
        if raw is None:
            if hn < hmax:
                hn += 1
                s = ang
            else:
                ang = 0.0
                s = None
        else:
            hn = 0
            if maxd is None:
                ang = raw
            else:
                ang = ang + float(np.clip(raw - ang, -maxd, maxd))
            s = ang
        # el 4to campo es el crudo: AB.metricas solo mira [0] y [1], asi que
        # arrastrarlo no cambia ninguna metrica del banco.
        out.append((t, s, st, raw))
    return out


def extra(serie_cmd):
    """Metricas que AB.metricas no calcula porque no mira el comando."""
    st = [x[1] for x in serie_cmd]
    tg = [x[0] for x in serie_cmd]
    rw = [x[3] for x in serie_cmd]
    # LAG: cuanto se queda atras el comando respecto de lo que ve la percepcion.
    # Es el COSTO del slew, y sin esta columna el slew parece gratis.
    lag = [abs(r - s) for r, s in zip(rw, st)
           if r is not None and s is not None]
    sin_cmd = sum(1 for s in st if s is None)
    dsmax = 0.0
    dsmax_t = 0.0
    difs_t = []
    for k in range(1, len(st)):
        a, b = st[k - 1], st[k]
        if a is None or b is None:
            continue
        dsmax = max(dsmax, abs(b - a))
        if tg[k - 1] is not None and tg[k] is not None:
            dsmax_t = max(dsmax_t, abs(b - a))
            difs_t.append(abs(b - a))
    ef = [0.0 if s is None else s for s in st]
    dsmax_ef = 0.0
    esc_ef = 0
    for k in range(1, len(ef)):
        d = abs(ef[k] - ef[k - 1])
        dsmax_ef = max(dsmax_ef, d)
        if d > 24.0:
            esc_ef += 1
    return dict(sin_cmd=sin_cmd, dsmax=dsmax, dsmax_t=dsmax_t,
                dsmax_ef=dsmax_ef, esc_ef=esc_ef,
                lag_p90=float(np.percentile(lag, 90)) if lag else 0.0,
                suav_t=float(np.median(difs_t)) if difs_t else float("nan"))


def evaluar(caches, ctl_caches, v2, slew_dps, hold_s):
    tot = dict(n=0, con=0, sin_aut=0, huecos=0, s_gt=0, inv=0,
               sin_cmd=0, esc_ef=0, suav=[], suav_t=[], lag_p90=[])
    dsmax = 0.0
    dsmax_t = 0.0
    dsmax_ef = 0.0
    for _vid, fps, cache in caches:
        S = comando(cache, v2, fps, slew_dps, hold_s)
        m = AB.metricas(S)
        e = extra(S)
        for k in ("n", "con", "sin_aut", "huecos", "s_gt", "inv"):
            tot[k] += m[k]
        tot["sin_cmd"] += e["sin_cmd"]
        tot["esc_ef"] += e["esc_ef"]
        tot["suav"].append(m["suav"])
        tot["suav_t"].append(e["suav_t"])
        tot["lag_p90"].append(e["lag_p90"])
        dsmax = max(dsmax, e["dsmax"])
        dsmax_t = max(dsmax_t, e["dsmax_t"])
        dsmax_ef = max(dsmax_ef, e["dsmax_ef"])
    tot["disp"] = 100.0 * tot["con"] / max(tot["n"], 1)
    tot["suav"] = float(np.mean(tot["suav"]))
    tot["suav_t"] = float(np.mean(tot["suav_t"]))
    tot["lag_p90"] = float(np.mean(tot["lag_p90"]))
    tot["dsmax"] = dsmax
    tot["dsmax_t"] = dsmax_t
    tot["dsmax_ef"] = dsmax_ef

    det = []
    ok = True
    smax = None
    for cn, fps, ex, cache in ctl_caches:
        S = comando(cache, v2, fps, slew_dps, hold_s)
        m = AB.metricas(S)
        det.append("%s %d/%d" % (cn.split("_")[0], m["con"], ex))
        ok &= (m["con"] >= ex)
        if cn == "lineal_positivo":
            stl = [x[1] for x in S if x[1] is not None]
            smax = max(stl) if stl else 0.0
            det.append("smax %+.1f" % smax)
            ok &= (smax >= SMAX_EXIGIDO)
    tot["ctl"] = "  ".join(det)
    tot["ctl_ok"] = bool(ok)
    tot["smax"] = smax
    return tot


# =============================== main =====================================

CAB = ("  %-14s %7s %7s %7s %8s %9s %7s %7s %8s %8s %9s %10s %7s"
       % ("variante", "disp %", "sin_aut", "huecos", "saltos>24",
          "inversion", "suav_t", "lag p90", "sin_cmd", "|ds| max",
          "|ds|max T", "|ds|max ef", "esc_ef"))


def fila(nom, t, b):
    if b is None:
        return ("  %-14s %7.2f %7d %7d %8d %9d %7.2f %7.2f %7d %8.2f %9.2f "
                "%10.2f %7d   %s %s"
                % (nom, t["disp"], t["sin_aut"], t["huecos"], t["s_gt"],
                   t["inv"], t["suav_t"], t["lag_p90"], t["sin_cmd"],
                   t["dsmax"], t["dsmax_t"], t["dsmax_ef"], t["esc_ef"],
                   t["ctl"], "OK" if t["ctl_ok"] else "*** FALLA"))
    return ("  %-14s %+7.2f %+7d %+7d %+8d %+9d %+7.2f %+7.2f %+7d %8.2f "
            "%9.2f %10.2f %7d   %s %s"
            % (nom, t["disp"] - b["disp"], t["sin_aut"] - b["sin_aut"],
               t["huecos"] - b["huecos"], t["s_gt"] - b["s_gt"],
               t["inv"] - b["inv"], t["suav_t"] - b["suav_t"],
               t["lag_p90"] - b["lag_p90"], t["sin_cmd"] - b["sin_cmd"],
               t["dsmax"], t["dsmax_t"], t["dsmax_ef"], t["esc_ef"],
               t["ctl"], "OK" if t["ctl_ok"] else "*** FALLA"))


def et_slew(s):
    return "sin" if s is None else "%d d/s" % int(s)


def et_hold(h):
    if h <= 0:
        return "hold 0"
    if not np.isfinite(h):
        return "hold inf"
    return "hold %.1fs" % h


def cachear(SinBranch, v2):
    caches = []
    for vid in AB.AUTONOMOS:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru):
            continue
        caches.append((vid, FPS, percibir(SinBranch, v2, ru, FPS)))
        sys.stdout.write(".")
        sys.stdout.flush()
    ctl = []
    for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
        ru = os.path.join(AQUI, vid)
        if not os.path.exists(ru) or not ex:
            continue
        ctl.append((cn, fps, ex, percibir(SinBranch, v2, ru, fps, d0, h0)))
        sys.stdout.write("c")
        sys.stdout.flush()
    print(" listo")
    return caches, ctl


def main():
    v4, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)

    print("")
    print("=" * 122)
    print("  WF_SLEW - capa de COMANDO sobre CAMINO+MONO")
    print("  A) limitador de velocidad de comando   B) sostener el angulo en el hueco")
    print("  El target NO se toca: disp, sin_aut, huecos y saltos>24 son INVARIANTES")
    print("  por construccion. Que salgan +0 es el chequeo, no el resultado.")
    print("=" * 122)

    # ---- pasada 1: fidelidad del espia + baseline absoluto de la candidata
    print("")
    sys.stdout.write("  percepcion 1/2 (espia apagado, fidelidad) ")
    sys.stdout.flush()
    CHK["n"] = CHK["mal"] = 0
    rest = instalar(v2, dict(camino=False, mono=False))
    c_base, ctl_base = cachear(SinBranch, v2)
    rest()
    print("  FIDELIDAD DEL ESPIA: %d frames, %d discrepancias  %s"
          % (CHK["n"], CHK["mal"], "OK" if CHK["mal"] == 0 else "*** ABORTA"))
    if CHK["mal"]:
        return 3

    # ---- pasada 2: CAMINO+MONO, el tronco de este experimento
    sys.stdout.write("  percepcion 2/2 (CAMINO+MONO) ")
    sys.stdout.flush()
    rest = instalar(v2, dict(camino=True, mono=True))
    caches, ctlc = cachear(SinBranch, v2)
    rest()

    # ---- fidelidad de la capa de comando -------------------------------
    mal = 0
    n = 0
    for _vid, fps, cache in caches:
        S = comando(cache, v2, fps, None, 0.0)
        for row, (t0, _st0) in zip(S, cache):
            s = row[1]
            n += 1
            r = raw_de(t0, v2)
            if (s is None) != (r is None):
                mal += 1
            elif s is not None and abs(s - r) > 1e-12:
                mal += 1
    print("  FIDELIDAD DE COMANDO (slew=sin, hold=0): %d frames, %d "
          "discrepancias  %s" % (n, mal, "OK" if mal == 0 else "*** ABORTA"))
    if mal:
        return 3

    ref = evaluar(c_base, ctl_base, v2, None, 0.0)
    print("")
    print("  REFERENCIA - candidata SinBranch SIN camino ni mono (baseline absoluto)")
    print(CAB)
    print(fila("BASELINE", ref, None))

    base = evaluar(caches, ctlc, v2, None, 0.0)
    print("")
    print("  TRONCO DE ESTE EXPERIMENTO - CAMINO+MONO, slew=sin, hold=0")
    print(CAB)
    print(fila("CAMINO+MONO", base, None))
    print("  (vs baseline: disp %+.2f  sin_aut %+d  huecos %+d  saltos %+d  inv %+d)"
          % (base["disp"] - ref["disp"], base["sin_aut"] - ref["sin_aut"],
             base["huecos"] - ref["huecos"], base["s_gt"] - ref["s_gt"],
             base["inv"] - ref["inv"]))

    # ---- BANDA A: slew, con hold = 0 -----------------------------------
    print("")
    print("  A) BANDA DE SLEW PREREGISTRADA, hold = 0   (deltas contra CAMINO+MONO)")
    print(CAB)
    res_slew = []
    for sl in BANDA_SLEW:
        t = evaluar(caches, ctlc, v2, sl, 0.0)
        res_slew.append((et_slew(sl), sl, t))
        print(fila(et_slew(sl), t, base))

    apt = [x for x in res_slew if x[2]["ctl_ok"]]
    print("")
    print("  Pasan el criterio duro (controles + smax >= %.1f): %s"
          % (SMAX_EXIGIDO, ", ".join(x[0] for x in apt) or "NINGUNO"))
    elegido = None
    if apt:
        apt.sort(key=lambda x: (x[2]["dsmax"], x[2]["inv"], x[2]["suav_t"]))
        cand_k, cand_sl, cand_t = apt[0]
        if cand_t["dsmax"] < base["dsmax"] - 1e-9:
            elegido = (cand_k, cand_sl, cand_t)
            print("  SLEW ELEGIDO por criterio preregistrado: %s "
                  "(|ds| max %.2f contra %.2f sin limitador)"
                  % (cand_k, cand_t["dsmax"], base["dsmax"]))
        else:
            print("  NINGUN slew baja el |ds| max (%.2f sin limitador). "
                  "Veredicto: NO APORTA, queda 'sin'." % base["dsmax"])
    sl_hold = elegido[1] if elegido else None
    nom_sl = elegido[0] if elegido else "sin"

    # --- lectura de la banda A, con las columnas de diagnostico ----------
    tope_px = 24.0                       # cap del SpatialTargetGuard, en px
    g_px = 90.0 / (v2.W / 2.0)           # grados de steer por pixel de columna
    tope_dps = tope_px * g_px * FPS
    print("")
    print("  LECTURA DE LA BANDA A")
    print("  1) Sin limitador el |ds| max ya es %.2f grados = %.0f px x %.3f "
          "grados/px:" % (base["dsmax"], tope_px, g_px))
    print("     es EXACTAMENTE el cap de 24 px del SpatialTargetGuard traducido")
    print("     a grados. La candidata ya viene topeada. Cualquier slew por")
    print("     encima de %.0f grados/s no puede morder nada." % tope_dps)
    print("  2) Ojo con la columna '|ds| max' cuando el slew esta prendido: con")
    print("     hold=0 el integrador vuelve a 0 en el hueco, y el primer paso al")
    print("     salir del hueco vale min(slew/fps, |raw|). Por eso 1500 y 1000")
    print("     d/s dan un |ds| max PEOR que no poner nada. La columna honesta")
    print("     para el latigazo de percepcion es '|ds|max T'.")

    # ---- BANDA B: hold, con el slew elegido -----------------------------
    print("")
    print("  B) BANDA DE HOLD PREREGISTRADA, slew = %s   (deltas contra "
          "slew=%s hold=0)" % (nom_sl, nom_sl))
    b2 = evaluar(caches, ctlc, v2, sl_hold, 0.0)
    print(CAB)
    print(fila("hold 0", b2, b2))
    res_hold = []
    for h in BANDA_HOLD[1:] + [HOLD_DIAG]:
        t = evaluar(caches, ctlc, v2, sl_hold, h)
        res_hold.append((h, t))
        print(fila(et_hold(h) + ("  DIAG" if not np.isfinite(h) else ""),
                   t, b2))

    print("")
    eleg_h = None
    for h, t in sorted([x for x in res_hold if np.isfinite(x[0])],
                       key=lambda x: -x[0]):
        if not t["ctl_ok"]:
            continue
        if t["dsmax"] > b2["dsmax"] + 1e-9 or t["inv"] > b2["inv"]:
            continue
        if t["dsmax_ef"] < b2["dsmax_ef"] - 1e-9:
            eleg_h = (h, t)
            break
    if eleg_h:
        print("  HOLD ELEGIDO por criterio preregistrado: %s  "
              "(|ds| max efectivo %.2f contra %.2f;  sin_cmd %d contra %d)"
              % (et_hold(eleg_h[0]), eleg_h[1]["dsmax_ef"], b2["dsmax_ef"],
                 eleg_h[1]["sin_cmd"], b2["sin_cmd"]))
    else:
        print("  NINGUN hold cumple el criterio. Queda hold = 0.")

    print("")
    print("  LECTURA DE LA BANDA B - donde el criterio preregistrado se quedo corto")
    print("  El objetivo que preregistre para el hold era el MAXIMO del |ds|")
    print("  efectivo. Un maximo lo fija UN evento: alcanza con que exista un solo")
    print("  hueco mas largo que el hold para que no baje nada. Eso es lo que")
    print("  paso. La version de TASA de la misma cosa (esc_ef = cuantos")
    print("  escalones > 24 grados hay en el comando efectivo) si se mueve:")
    for h, t in [(0.0, b2)] + res_hold:
        print("      %-10s esc_ef %5d   sin_cmd %5d   inversiones %4d%s"
              % (et_hold(h), t["esc_ef"], t["sin_cmd"], t["inv"],
                 "   (DIAG, no elegible)" if not np.isfinite(h) else ""))
    print("  No cambio el criterio despues de ver los numeros: la eleccion")
    print("  preregistrada es hold=0 y asi queda. Esto es diagnostico, y para")
    print("  adoptarlo hay que preregistrar esc_ef y volver a correr.")

    # --- control de separacion: el hold SIN slew -------------------------
    print("")
    print("  CONTROL DE SEPARACION - la misma banda de hold pero con slew=sin,")
    print("  para saber si lo que mueve el hold depende del slew o no.")
    print("  (Sale gratis: la percepcion ya esta cacheada, no se vuelve a correr.)")
    b3 = evaluar(caches, ctlc, v2, None, 0.0)
    print(CAB)
    print(fila("sin + hold 0", b3, b3))
    for h in BANDA_HOLD[1:] + [HOLD_DIAG]:
        t = evaluar(caches, ctlc, v2, None, h)
        print(fila("sin + " + et_hold(h), t, b3))

    print("")
    print("  CONFIGURACION FINAL POR CRITERIO PREREGISTRADO: slew=%s, %s"
          % (nom_sl, et_hold(eleg_h[0]) if eleg_h else "hold 0"))
    print("  Recordatorio: replay OPEN-LOOP. Mide el comando que la percepcion")
    print("  habria emitido sobre video grabado, no como habria doblado el robot.")
    print("=" * 122)
    return 0


if __name__ == "__main__":
    sys.exit(main())
