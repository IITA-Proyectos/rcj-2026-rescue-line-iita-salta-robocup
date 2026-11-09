# -*- coding: utf-8 -*-
"""V6.6 FIELD REV2 - TERMINAL_LOCAL_HARD endurecido + SIDE_CHECK post-retro (Claude, 2026-09-12).

Misma API que REV1 (TerminalLocalHard / would_veto_curve / apply_optional_veto) y una
funcion nueva, apply_side_check(). Ninguna toca camino_loss_arbiter.py.

CAMBIO 1 (dato del sabado 12-sep, video v66_shadow_curva1, perdida en frame 452):
  una ESQUINA de 90 grados vista de frente termina igual que un GAP en los ultimos
  frames (la rama saliente pasa por debajo del borde inferior del ROI). Lo que la
  delata son los frames anteriores: la componente se ENSANCHA en las filas de abajo
  (w_bot 92-156 px = la rama corriendo por el borde inferior) o llega a 8 px de un
  borde lateral (xmax 147-154 sin tocar 159). En un GAP real el ancho abajo queda en
  el ancho de la cinta (67-77 px en el gap del sabado; <=80 en como_esta 843).
  -> 'tocar borde' incluye un margen de 8 px, w_bot >= 100 cuenta como rama y reinicia
     s4k, y ADEMAS el ancho maximo abajo en los ultimos 16 frames validos (w_bot_max) tiene
     que ser <= 110. Medido el sabado: 9 esquinas -> w_bot_max 144-160; 5 fines reales de
     negro (gap del sabado, como_esta 843, plateado, rojo x2) -> 74-82. Todo lo demas igual:
     s4k>=7, avance>=30 (16 frames), last_ymin>=100, bb<=0.10.

CAMBIO 2 (perdidas 61 y 251 del sabado, ambas terminaron en reinicio):
  V6.5 decidio CURVA IZQ por memoria (reglas 3b/4) en esquinas que giraban a la
  DERECHA. La memoria LATERAL_IZQ venia de la cinta de ENTRADA inclinada a la
  izquierda, no de la rama de salida. Los frames post-retroceso SI vieron la rama:
  dx=+67/+70, shiftfar=+46/+48 (derecha), pero el arbitro los descarta como
  'falso +/-90' por falta de avance frontal (dy<18). En las 7 perdidas restantes del
  sabado el signo post-retro coincidio con la memoria (o fue mixto).
  -> apply_side_check(): si V6.5 decidio CURVA SOLO por memoria (3b/4) y >=2 frames
     post-retro 'falso +/-90' tienen |shiftfar|>=40 y |dx|>=40 con el MISMO signo, y
     ese signo es OPUESTO a la memoria, y NINGUN frame post-retro fuerte apunta al lado
     de la memoria -> propone invertir el lado (misma magnitud |hprior|). SHADOW por
     defecto: solo loguea WOULD_FLIP. Con SIDE_CHECK_AUTH=1 aplica el flip.
"""
import os
from collections import deque

import numpy as np

VERSION = "V6.6-FIELD-TERM-HARD-REV3-SIDE25-POSTMAG-PISO"

# ------------------------------------------------------------------------------------------------
# TERM_PISO (2026-09-15): GAP visto como "la punta de la cinta BAJO DESDE ARRIBA sin ninguna rama".
# TERM_HARD pide 7 cuadros seguidos sin tocar el margen lateral y ancho abajo < 100 px. Con el robot
# cruzado (despues de una curva, o subiendo una loma) la cinta diagonal roza el margen o mide > 100 px
# abajo, y el gap no se reconoce. Medido en los 4 videos: los 44 codos/curvas NUNCA muestran, desde que la
# punta se despega del borde de arriba hasta la perdida, una cinta sola sin rama: siempre hay una rama que
# sale por el costado o una fila de abajo de 3,4-4,5 cm en el piso. Los gaps, si (ancho 1,5-2,0 cm).
#   j = ultimo cuadro (de hasta 40 con cinta) en que la cinta toca arriba (ymin <= 63)
#   GAP_PISO si despues de j hay >= PISO_NMIN cuadros y en TODOS:
#     - la punta (3 filas mas altas) no toca el margen lateral de 8 px
#     - no hay rama por el costado: tramo de filas pegado al borde (x<=2 o x>=157) que empieza arriba de la
#       fila 105 y NO llega a la esquina de abajo (fila >= 116). Si llega, es la cinta entrando cruzada.
#     - cada fila de abajo (105-119), llevada al piso con el modelo de camara, mide <= PISO_WCM cm
#   y ademas la ultima punta quedo en la fila >= 100 y bb <= 0,10 (igual que TERM_HARD).
# TERM_PISO=1: el veto de TERM_HARD_AUTH usa (TERM_HARD o GAP_PISO). Sin TERM_PISO solo se loguea.
TERM_PISO = os.environ.get("TERM_PISO", "0") == "1"
PISO_W = 40
PISO_NMIN = 4
PISO_WCM = 2.6
# Modelo de camara verificado 15-sep (160x120): barril (division), pinhole inclinado 19,9 grados, roll 3,2.
_PISO_CAM = dict(f=117.22587273168617, th=0.3475742754916071, cx=79.5, cy=59.5, q=3.60528874940623e-05,
                 ro=0.05537706262356494, h=1.990498010210863)


def _tabla_x_piso():
    """X en el piso (cm) de cada pixel de las filas 105-119 de la imagen 160x120. Forma (15, 160)."""
    c = _PISO_CAM
    vv, uu = np.mgrid[105:120, 0:160].astype(float)
    du, dv = uu - c["cx"], vv - c["cy"]
    s = 1.0 / np.maximum(1.0 - c["q"] * (du * du + dv * dv), 0.05)
    du, dv = du * s, dv * s
    cr, sr = np.cos(c["ro"]), np.sin(c["ro"])
    u0 = cr * du + sr * dv
    v0 = -sr * du + cr * dv
    zc = c["f"] * c["h"] / ((v0 + c["f"] * np.tan(c["th"])) * np.cos(c["th"]))
    return u0 * zc / c["f"]


_TX = _tabla_x_piso()

MEMORY_ONLY_CURVE_REASONS = frozenset((
    "lateral previa muy reciente + post ambiguo no la refuta",
    "V6.4 lateral ESTABLE + colapso falso +/-90 post-retro",
))
FALSE90_REASON = "sin avance frontal: bloquea falso +/-90"


class TerminalLocalHard(object):
    def __init__(self, window=20, min_valid=4, advance_min=30, last_ymin_min=100,
                 side_recent_window=5, k_clear=7, rel_window=16, top_rows=63, bb_max=0.10,
                 edge_margin=8, wide_bot=100, wide_bot_max=110):
        self.window = int(window)
        self.min_valid = int(min_valid)
        self.advance_min = int(advance_min)
        self.last_ymin_min = int(last_ymin_min)
        self.side_recent_window = int(side_recent_window)
        self.k_clear = int(k_clear)
        self.rel_window = int(rel_window)
        self.top_rows = int(top_rows)
        self.bb_max = float(bb_max)
        self.edge_margin = int(edge_margin)
        self.wide_bot = int(wide_bot)
        self.wide_bot_max = int(wide_bot_max)
        self.hist = deque(maxlen=self.window)
        self._s4k = 0
        self.piso = deque(maxlen=PISO_W)

    def reset(self):
        self.hist.clear()
        self._s4k = 0
        self.piso.clear()

    def observe_connected_mask(self, connected_mask, full_mask=None, now=None):
        """Guarda geometria minima de la componente CONECTADA (_mm de _solo_mi_linea)."""
        try:
            ys, xs = np.nonzero(connected_mask)
            if len(ys) == 0:
                return False
            h, w = connected_mask.shape[:2]
            ymin = int(ys.min()); xmin = int(xs.min()); xmax = int(xs.max())
            touch_side = bool(xmin <= self.edge_margin or xmax >= (w - 1 - self.edge_margin))
            touch_top = bool(ymin <= self.top_rows)
            bot = xs[ys >= h - 15]
            w_bot = int(bot.max() - bot.min() + 1) if len(bot) else 0
            wide = bool(w_bot >= self.wide_bot)
            self._s4k = 0 if (touch_side or touch_top or wide) else self._s4k + 1
            bb = 0.0
            if full_mask is not None:
                cxt = float(xs[ys <= ymin + 5].mean())
                y1 = ymin - 8; y0 = y1 - 8
                x0 = max(0, int(cxt) - 4); x1 = min(w, x0 + 8)
                if y0 >= 0:
                    sub = full_mask[y0:y1, x0:x1]
                    if sub.size:
                        bb = float(np.count_nonzero(sub)) / float(sub.size)
            self.hist.append({
                "ymin": ymin, "touch_side": touch_side, "touch_top": touch_top, "wide": wide,
                "w_bot": w_bot, "s4k": int(self._s4k), "bb": bb, "area": int(len(ys)), "t": now,
            })
            # TERM_PISO: aparte, para que un error aca nunca toque lo de arriba.
            try:
                m = connected_mask > 0
                tx = xs[ys <= ymin + 2]
                punta_costado = bool(tx.min() <= self.edge_margin or tx.max() >= (w - 1 - self.edge_margin))
                rama = False
                for col in (m[:, :3].any(1), m[:, w - 3:].any(1)):
                    f = np.flatnonzero(col)
                    if len(f):
                        for seg in np.split(f, np.flatnonzero(np.diff(f) > 1) + 1):
                            if seg.min() < h - 15 and seg.max() < h - 4:
                                rama = True
                wcm = 99.0   # otra resolucion: sin tabla, nunca da GAP
                if h == 120 and w == 160:
                    wcm = 0.0
                    for k in range(15):
                        xr = np.flatnonzero(m[105 + k])
                        if len(xr):
                            wcm = max(wcm, float(_TX[k, xr[-1]] - _TX[k, xr[0]]))
                self.piso.append({"ymin": ymin, "arriba": touch_top, "punta_costado": punta_costado,
                                  "rama": rama, "wcm": wcm, "bb": bb})
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _piso(self):
        """(gap_piso, motivo). Ver TERM_PISO arriba."""
        v = list(self.piso)
        js = [k for k, x in enumerate(v) if x["arriba"]]
        if not js:
            return False, "la punta no bajo desde arriba"
        tramo = v[js[-1] + 1:]
        if len(tramo) < PISO_NMIN:
            return False, "pocos cuadros desde arriba (%d)" % len(tramo)
        for x in tramo:
            if x["punta_costado"]:
                return False, "punta en el costado (y%d)" % x["ymin"]
            if x["rama"]:
                return False, "rama por el costado (y%d)" % x["ymin"]
            if x["wcm"] > PISO_WCM:
                return False, "ancho abajo %.1f cm (y%d)" % (x["wcm"], x["ymin"])
        if v[-1]["ymin"] < self.last_ymin_min:
            return False, "ultima punta y%d" % v[-1]["ymin"]
        if v[-1]["bb"] > self.bb_max:
            return False, "negro mas alla de la punta"
        return True, "GAP: %d cuadros desde arriba, ancho max %.1f cm" % (len(tramo), max(x["wcm"] for x in tramo))

    def snapshot(self):
        try:
            piso_ok, piso_why = self._piso()
        except Exception as e:
            piso_ok, piso_why = False, "error %s" % e
        vals = list(self.hist)[-self.window:]
        n = len(vals)
        if n < self.min_valid:
            return {"strong": False, "strong_hoy": False, "strong_piso": piso_ok, "piso_why": piso_why,
                    "advance": 0, "last_ymin": None, "side_recent": 99,
                    "n": n, "s4k": 0, "bb": None, "w_bot_max": None,
                    "reason": "insuficientes frames validos"}
        y = [int(v["ymin"]) for v in vals]
        last = y[-1]
        baseline = min(y[-self.rel_window:])
        advance = int(last - baseline)
        recent = vals[-self.side_recent_window:]
        side_recent = sum(1 for v in recent if bool(v.get("touch_side")))
        s4k = int(vals[-1].get("s4k", 0))
        bb = vals[-1].get("bb", 0.0)
        w_bot_max = max(int(v.get("w_bot", 0)) for v in vals[-self.rel_window:])
        strong_hoy = bool(
            s4k >= self.k_clear and
            advance >= self.advance_min and
            last >= self.last_ymin_min and
            (bb is None or bb <= self.bb_max) and
            w_bot_max <= self.wide_bot_max
        )
        strong = bool(strong_hoy or (TERM_PISO and piso_ok))
        return {
            "strong": strong, "strong_hoy": strong_hoy, "strong_piso": piso_ok, "piso_why": piso_why,
            "advance": advance, "last_ymin": int(last),
            "baseline_ymin": int(baseline), "side_recent": int(side_recent),
            "n": n, "s4k": s4k, "bb": (None if bb is None else round(float(bb), 3)),
            "w_bot_max": w_bot_max,
            "reason": ("TERM_HARD" if strong_hoy else "TERM_PISO" if strong else "no cumple s4k/avance/last/bb"),
        }


def would_veto_curve(v65_decision, evidence):
    if not isinstance(v65_decision, dict):
        return False
    if v65_decision.get("kind") != "CURVA":
        return False
    if v65_decision.get("reason") not in MEMORY_ONLY_CURVE_REASONS:
        return False
    return bool((evidence or {}).get("strong", False))


def apply_optional_veto(v65_decision, evidence, authority=False):
    would = would_veto_curve(v65_decision, evidence)
    if not (would and authority):
        return v65_decision, would, False
    d = dict(v65_decision)
    d.update({"kind": "RECTA", "side": 0, "heading": None,
              "reason": "V6.6 TERM_HARD veta SOLO fallback lateral viejo"})
    return d, True, True


# --------------------------- SIDE_CHECK post-retro ---------------------------
SIDE_MIN_FRAMES = 2
SIDE_SHIFT_MIN = 18.0   # 2026-09-13: era 40; esquina 728 de completo_auth_1 dio shift +22/+30
SIDE_DX_MIN = 25.0      # 2026-09-13: era 40; esquina 728 de completo_auth_1 dio dx +31/+44


def _fin(v):
    try:
        return v is not None and np.isfinite(float(v))
    except Exception:
        return False


def side_evidence(post_items):
    """Signo de la rama vista post-retro en los frames 'falso +/-90'.
    Devuelve dict(signo=+1/-1/0, n_same, n_opp, detalle)."""
    votes = []
    for x in post_items or []:
        if x.get("reason") != FALSE90_REASON:
            continue
        sh = x.get("shiftfar"); dx = x.get("dx")
        if not (_fin(sh) and _fin(dx)):
            continue
        sh = float(sh); dx = float(dx)
        if abs(sh) >= SIDE_SHIFT_MIN and abs(dx) >= SIDE_DX_MIN and (sh > 0) == (dx > 0):
            votes.append(1 if sh > 0 else -1)
    pos = sum(1 for v in votes if v > 0); neg = sum(1 for v in votes if v < 0)
    if pos >= SIDE_MIN_FRAMES and neg == 0:
        return {"signo": 1, "n_same": pos, "n_opp": neg, "votes": votes}
    if neg >= SIDE_MIN_FRAMES and pos == 0:
        return {"signo": -1, "n_same": neg, "n_opp": pos, "votes": votes}
    return {"signo": 0, "n_same": max(pos, neg), "n_opp": min(pos, neg), "votes": votes}


def would_flip_side(v65_decision, post_items):
    if not isinstance(v65_decision, dict) or v65_decision.get("kind") != "CURVA":
        return False, None
    if v65_decision.get("reason") not in MEMORY_ONLY_CURVE_REASONS:
        return False, None
    side = int(v65_decision.get("side") or 0)
    ev = side_evidence(post_items)
    if side == 0 or ev["signo"] == 0:
        return False, ev
    # ningun frame post-retro fuerte a favor de la memoria (raw LATERAL del lado de la memoria)
    lat_mem = "LATERAL_DER" if side > 0 else "LATERAL_IZQ"
    if any(x.get("raw") == lat_mem for x in post_items or []):
        return False, ev
    return (ev["signo"] == -side), ev


def _median(xs, fb):
    xs = sorted(xs)
    if not xs:
        return fb
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def _post_heading_mag(post_items, new_side):
    """Mediana del |heading| de los frames post-retro 'falso +/-90' que apuntan al
    nuevo lado (los que justificaron el flip). Es la evidencia FRESCA que valido la
    inversion; se usa para la magnitud del giro en vez del heading viejo de memoria."""
    hs = []
    for x in post_items or []:
        if x.get("reason") != FALSE90_REASON:
            continue
        h = x.get("heading")
        if _fin(h) and (float(h) > 0) == (new_side > 0):
            hs.append(abs(float(h)))
    return _median(hs, 0.0) if hs else 0.0


def apply_side_check(v65_decision, post_items, authority=False):
    """Devuelve (decision, would_flip, applied, evidencia)."""
    would, ev = would_flip_side(v65_decision, post_items)
    if not (would and authority):
        return v65_decision, would, False, ev
    d = dict(v65_decision)
    new_side = -int(d.get("side") or 0)
    # POSTMAG: magnitud desde el post fresco (no el heading viejo de la memoria).
    mag_post = _post_heading_mag(post_items, new_side)
    h = d.get("heading")
    mag_old = abs(float(h)) if _fin(h) else 0.0
    mag = max(mag_post, mag_old)   # nunca por debajo de lo que ya daba SIDE25
    if mag < 10.0:
        mag = 12.0
    d.update({"side": new_side, "heading": mag * new_side,
              "reason": "V6.6 SIDE_CHECK+POSTMAG: rama post-retro contradice memoria (%s)" % d.get("reason")})
    return d, True, True, ev


def _selftest():
    g = TerminalLocalHard()
    for y in (66, 68, 72, 78, 84, 90, 96, 102, 106):
        m = np.zeros((120, 160), np.uint8); m[y:120, 74:86] = 255
        assert g.observe_connected_mask(m, full_mask=m)
    e = g.snapshot(); assert e["strong"], e
    old = {"kind": "CURVA", "reason": "lateral previa muy reciente + post ambiguo no la refuta", "side": 1, "heading": 30.0}
    out, would, applied = apply_optional_veto(old, e, authority=True)
    assert would and applied and out["kind"] == "RECTA"
    # esquina: rama ancha abajo unos frames antes -> no strong
    g.reset()
    for i, y in enumerate((66, 70, 76, 82, 88, 94, 100, 104, 108)):
        m = np.zeros((120, 160), np.uint8); m[y:120, 74:86] = 255
        if i < 3:
            m[108:120, 20:140] = 255      # rama horizontal por abajo
        g.observe_connected_mask(m, full_mask=m)
    assert not g.snapshot()["strong"], g.snapshot()
    # esquina: a 8 px del borde
    g.reset()
    for i, y in enumerate((66, 70, 76, 82, 88, 94, 100, 104, 108)):
        m = np.zeros((120, 160), np.uint8); m[y:120, 74:86] = 255
        if i < 3:
            m[y:y + 6, 74:153] = 255
        g.observe_connected_mask(m, full_mask=m)
    assert not g.snapshot()["strong"], g.snapshot()
    # side check: memoria IZQ, post-retro rama a la DER en 2 frames -> flip
    post = [dict(raw="AMBIGUA", reason=FALSE90_REASON, shiftfar=46.0, dx=67.0),
            dict(raw="AMBIGUA", reason=FALSE90_REASON, shiftfar=48.0, dx=70.0),
            dict(raw="AMBIGUA", reason=FALSE90_REASON, shiftfar=44.0, dx=50.0)]
    dec = {"kind": "CURVA", "side": -1, "heading": -40.1, "reason": "V6.4 lateral ESTABLE + colapso falso +/-90 post-retro"}
    d2, would, applied, ev = apply_side_check(dec, post, authority=False)
    assert would and not applied and d2 is dec
    d2, would, applied, ev = apply_side_check(dec, post, authority=True)
    assert applied and d2["side"] == 1 and abs(d2["heading"] - 40.1) < 1e-6
    # mixto -> no flip
    post2 = [dict(raw="AMBIGUA", reason=FALSE90_REASON, shiftfar=46.0, dx=73.0),
             dict(raw="AMBIGUA", reason=FALSE90_REASON, shiftfar=-43.0, dx=-46.0)]
    assert not apply_side_check(dec, post2, authority=True)[1]
    # coincide con memoria -> no flip
    post3 = [dict(raw="AMBIGUA", reason=FALSE90_REASON, shiftfar=-48.0, dx=-70.0),
             dict(raw="AMBIGUA", reason=FALSE90_REASON, shiftfar=-46.0, dx=-68.0)]
    assert not apply_side_check(dec, post3, authority=True)[1]
    # razon con evidencia real (regla 1) -> nunca
    dec1 = dict(dec); dec1["reason"] = "3 frames laterales post-retro"
    assert not apply_side_check(dec1, post, authority=True)[1]
    # --- TERM_PISO ---
    def correr_piso(frames):
        gg = TerminalLocalHard()
        for mm in frames:
            gg.observe_connected_mask(mm, full_mask=mm)
        return gg.snapshot()

    def recta(y, x0=74, x1=86):
        mm = np.zeros((120, 160), np.uint8); mm[y:120, x0:x1] = 255
        return mm

    tops = [recta(60), recta(60), recta(62)]
    bajando = [recta(y) for y in (66, 72, 78, 84, 90, 96, 102, 106)]
    e = correr_piso(tops + bajando)
    assert e["strong_piso"], e
    assert e["strong"] == (e["strong_hoy"] or TERM_PISO), e
    # cruzada: entra por la esquina de abajo a la izquierda (toca el borde desde la fila 98 hasta abajo = esquina,
    # no rama) y el robot se va enderezando
    def cruzada(ytop):
        mm = np.zeros((120, 160), np.uint8)
        for y in range(ytop, 120):
            xc = int(15 + (119 - y) * 0.8)
            mm[y, max(0, xc - 30):xc + 30] = 255
        return mm
    e = correr_piso([cruzada(60), cruzada(61)] + [cruzada(y) for y in (66, 72, 80)] +
                    [recta(y, 50, 110) for y in (88, 96, 104)])
    assert e["strong_piso"], e
    # la misma cinta, pero con una rama que sale por el borde izquierdo entre las filas 70 y 90
    fr_rama = [cruzada(60), cruzada(61)]
    for y in (66, 72, 80):
        mm = cruzada(y); mm[70:90, 0:60] = 255; fr_rama.append(mm)
    e = correr_piso(fr_rama + [recta(y, 50, 110) for y in (88, 96, 104)])
    assert not e["strong_piso"] and "rama" in e["piso_why"], e
    # rama que sale por el costado derecho
    ramas = []
    for y in (66, 72, 78, 84, 90, 96, 102, 106):
        mm = recta(y)
        if y < 90:
            mm[y + 8:y + 14, 74:160] = 255   # debajo de la punta: la punta queda limpia, la rama toca el borde
        ramas.append(mm)
    e = correr_piso(tops + ramas)
    assert not e["strong_piso"] and "rama" in e["piso_why"], e
    # rama por abajo (fila ancha en el piso)
    anchas = []
    for i, y in enumerate((66, 72, 78, 84, 90, 96, 102, 106)):
        mm = recta(y)
        if i < 3:
            mm[108:120, 10:150] = 255
        anchas.append(mm)
    e = correr_piso(tops + anchas)
    assert not e["strong_piso"] and "ancho" in e["piso_why"], e
    # nunca toco arriba (aparecio de golpe en el medio)
    e = correr_piso(bajando)
    assert not e["strong_piso"], e
    print("TERMINAL_LOCAL_HARD REV3 SELFTEST OK", VERSION, "TERM_PISO=%d" % int(TERM_PISO))


if __name__ == "__main__":
    _selftest()
