# -*- coding: utf-8 -*-
"""Arbitro de perdida de linea: CURVA / RECTA / AMBIGUA.

No mueve el robot. No detecta colores. Su unica responsabilidad es decidir,
despues de la perdida CONFIRMADA por main.py y del retroceso fisico existente,
si hay evidencia geometrica para habilitar el recovery de curva o si la
continuacion venia recta y corresponde buscar GAP/color avanzando recto.

Reglas de seguridad incorporadas:
- heading pequeno NO implica recta: la forma completa del path puede demostrar
  lateralidad (excursion + desplazamiento del tramo lejano).
- un heading cercano a +/-90 no demuestra curva si el path/target no avanza.
- la intencion estable previa se conserva: 1-2 frames malos antes de perder la
  linea no la borran.
- una historia lateral previa NO puede convertirse en GAP solo porque 3 frames
  posteriores parezcan rectos; requiere evidencia compatible o queda AMBIGUA.
"""
from __future__ import print_function

import math
import os
import statistics
import time
from collections import Counter, deque

# Geometria medida sobre los videos disponibles. Conservadores para colores/GAP.
FORWARD_MIN = 18.0
STRAIGHT_DY_MIN = 45.0
STRAIGHT_HEADING_MAX = 28.0
STRAIGHT_EXC_MAX = 32.0
STRAIGHT_SHIFT_MAX = 18.0

# Ajuste V2 tras primera prueba fisica: el gate original era demasiado estricto
# y convertia curvas reales de borde en AMBIGUA por diferencias de 2-4 px.
# Se conserva INTACTA la barrera frontal (FORWARD_MIN=18) y el guard de target
# extrapolado, que son los que evitaron los falsos +/-90 de rojo/plateado.
LATERAL_EXC_MIN = 30.0
LATERAL_SHIFT_MIN = 20.0
LATERAL_EXC_STRONG = 42.0
LATERAL_HEADING_MIN = 32.0
LATERAL_DX_MIN = 26.0
LATERAL_HEADING_EXC_MIN = 28.0

# Fragmento parcial compatible con una intencion lateral ya demostrada antes.
FRAG_FORWARD_MIN = 8.0
FRAG_EXC_MIN = 18.0
FRAG_SHIFT_MIN = 10.0
FRAG_HEADING_MIN = 10.0

NORMAL_WINDOW = 7
NORMAL_STRAIGHT_NEED = 5
NORMAL_LATERAL_NEED = 3
PRIOR_MAX_AGE_S = 2.2
# Fallback de regresion: si la intencion LATERAL era MUY reciente y la pose
# post-retro no logra refutarla (solo AMBIGUA/transicion), conservar la decision
# de curva que el sistema funcional ya sabia tomar. Los logs fisicos 2026-09-05
# mostraron curvas reales con edades 0.289, 0.318 y 0.463 s.
PRIOR_LATERAL_FALLBACK_MAX_AGE_S = 0.60
PRIOR_LATERAL_FALLBACK_MIN_POST = 3
# V6: una contradiccion de UN frame post-retro ya no borra una curva demostrada.
# Hace falta una oposicion parcial sostenida; 3 laterales fuertes del lado contrario
# ya son atrapados antes por POST_LATERAL_NEED.
PRIOR_LATERAL_OPP_FRAG_BLOCK_NEED = 3

# V6: curva MUY abrupta. Puede perderse antes de juntar 3 votos LATERAL y por eso
# la ultima intencion estable sigue diciendo RECTA. Un GAP recto refresca RECTA
# hasta casi el borde; una curva abrupta deja esa RECTA "vieja" durante unas
# decimas mientras aparecen fragmentos laterales. Solo promovemos si coinciden:
#   - RECTA estable no demasiado fresca ni demasiado vieja,
#   - >=2 fragmentos del mismo lado en los ultimos frames CON linea conectada,
#   - sin fragmentos del lado contrario.
RECTA_STALE_CURVE_MIN_AGE_S = 0.20
RECTA_STALE_CURVE_MAX_AGE_S = 0.70
RECTA_STALE_CURVE_RECENT_S = 0.35
RECTA_STALE_CURVE_FRAG_NEED = 2

POST_WINDOW = 7
POST_LATERAL_NEED = 3
POST_STRAIGHT_NEED = 3
POST_FALLBACK_STRAIGHT_N = 5

# V6.3: si post-retro aparecen 2 laterales FUERTES del mismo lado y el resto
# de la ventana son AMBIGUA del guard +/-90 por falta de avance frontal, eso
# alcanza para CURVA.
POST_LATERAL_STRONG_WITH_FALSE90_NEED = 2
POST_FALSE90_AMBIG_NEED = 3

# V6.5: caso fisico de la curva cerrada DERECHA (2026-09-05). El primer bloque
# post-retro fue exactamente: 1 AMBIGUA falso +/-90 + 2 LATERAL_DER fuertes
# (h=74/71, reach=20/23, exc=61/58, shift=41/39). Esperar a juntar 3 falsos
# +/-90 hacia que esos 2 laterales salieran de la ventana y luego caia a GAP.
# Se acepta el par SOLO al comienzo de la pose nueva y con geometria lateral
# mucho mas fuerte que los umbrales generales. Es simetrico IZQ/DER.
POST_EARLY_PAIR_MAX_ITEMS = 4
POST_EARLY_PAIR_FALSE90_NEED = 1
POST_EARLY_PAIR_HEADING_MIN = 55.0
POST_EARLY_PAIR_REACH_MIN = 18.0
POST_EARLY_PAIR_EXC_MIN = 45.0
POST_EARLY_PAIR_SHIFT_MIN = 30.0

# Diagnostico opcional: SOLO imprime por consola; no cambia ninguna decision.
# Activar con LOSS_ARB_DIAG=1 al lanzar main.py.
LOSS_ARB_DIAG = os.environ.get("LOSS_ARB_DIAG", "0") == "1"
ARB_VERSION = "V6.5-EARLY-STRONG-PAIR"

# V6.4: extension MUY acotada para el caso fisico 2026-09-05:
# prior LATERAL estable edad=0.617 s + post-retro puro AMBIGUA por falso +/-90.
# No se sube el fallback general de 0.60 s porque una entrada a plateado ya
# produjo un falso prior LATERAL alrededor de 0.602 s. Solo una lateral que
# provenia de consenso ESTABLE puede usar esta extension, y unicamente cuando
# la pose post-retro colapsa en falsos +/-90 sin RECTA ni lateral fuerte.
PRIOR_LATERAL_STABLE_FALSE90_MAX_AGE_S = 0.80  # 2026-09-12: caso fisico 0.765 s; SIDE_CHECK decide el lado
PRIOR_LATERAL_STABLE_FALSE90_NEED = 3


def _finite(v):
    try:
        return v is not None and math.isfinite(float(v))
    except Exception:
        return False


def _median(vals, default=None):
    vals = [float(v) for v in vals if _finite(v)]
    return statistics.median(vals) if vals else default


def geometry(resultado):
    rr = resultado or {}
    path = rr.get("path") or []
    start = rr.get("start")
    target = rr.get("target")
    if not path or start is None or target is None:
        return dict(dx=None, dy=None, maxexc=None, span=None, reach=None,
                    shiftfar=None, npath=len(path))
    sx, sy = float(start[0]), float(start[1])
    tx, ty = float(target[0]), float(target[1])
    xs = [float(p[0]) for p in path]
    ys = [float(p[1]) for p in path]
    dx = tx - sx
    dy = sy - ty
    maxexc = max(abs(x - sx) for x in xs)
    span = max(xs) - min(xs)
    reach = sy - min(ys)
    n = max(1, len(xs) // 3)
    near = sum(xs[:n]) / float(len(xs[:n]))
    far = sum(xs[-n:]) / float(len(xs[-n:]))
    shiftfar = far - near
    return dict(dx=dx, dy=dy, maxexc=maxexc, span=span, reach=reach,
                shiftfar=shiftfar, npath=len(path))


def classify_frame(camino_frame, resultado):
    """Devuelve raw=RECTA/LATERAL_DER/LATERAL_IZQ/AMBIGUA y metricas."""
    cf = camino_frame or {}
    g = geometry(resultado)
    heading = cf.get("heading_frame")
    confiable = bool(cf.get("confiable"))
    vals = [heading, g["dx"], g["dy"], g["maxexc"], g["reach"], g["shiftfar"]]
    out = dict(raw="AMBIGUA", sign=0, heading=heading, small_heading=False,
               reason="sin CAMINO confiable", **g)
    if not confiable or any(not _finite(v) for v in vals):
        return out

    h = float(heading); dx = float(g["dx"]); dy = float(g["dy"])
    exc = float(g["maxexc"]); reach = float(g["reach"]); shift = float(g["shiftfar"])
    ah, adx, ash = abs(h), abs(dx), abs(shift)

    # Hallazgo de rojo/plateado: +/-90 con target/path que no avanzan.
    # Se bloquea ANTES de evaluar lateralidad.
    if dy < FORWARD_MIN or reach < FORWARD_MIN:
        out["reason"] = "sin avance frontal: bloquea falso +/-90"
        return out

    # Tambien bloquear un target extrapolado muy por delante del path observado.
    # Aparecio en los finales de negro de los videos de color.
    if dy >= 28.0 and reach < 0.48 * dy:
        out["reason"] = "target extrapolado; path observado demasiado corto"
        return out

    shape_lat = ((exc >= LATERAL_EXC_MIN and ash >= LATERAL_SHIFT_MIN)
                 or exc >= LATERAL_EXC_STRONG)
    heading_lat = (ah >= LATERAL_HEADING_MIN and adx >= LATERAL_DX_MIN
                   and exc >= LATERAL_HEADING_EXC_MIN)
    if shape_lat or heading_lat:
        side_src = shift if abs(shift) >= 10.0 else (dx if abs(dx) >= 10.0 else h)
        sign = 1 if side_src > 0 else -1  # CAMINO: + derecha
        out.update(raw="LATERAL_DER" if sign > 0 else "LATERAL_IZQ",
                   sign=sign,
                   small_heading=bool(ah < STRAIGHT_HEADING_MAX and shape_lat),
                   reason=("CURVA_HEADING_PEQUENO: forma lateral"
                           if ah < STRAIGHT_HEADING_MAX and shape_lat
                           else "continuacion lateral"))
        return out

    if (dy >= STRAIGHT_DY_MIN and reach >= STRAIGHT_DY_MIN
            and ah <= STRAIGHT_HEADING_MAX and exc <= STRAIGHT_EXC_MAX
            and ash <= STRAIGHT_SHIFT_MAX):
        out.update(raw="RECTA", reason="avance frontal largo y poca deriva")
    else:
        out["reason"] = "geometria insuficiente/contradictoria"
    return out


def fragment_side(camino_frame, resultado):
    """Lado de un fragmento parcial. SOLO se usa si ya habia lateral estable.

    V6.3: un frame sin avance frontal suficiente NO aporta fragment_side.
    """
    cf = camino_frame or {}
    g = geometry(resultado)
    h = cf.get("heading_frame")
    if not bool(cf.get("confiable")):
        return 0
    if not all(_finite(g[k]) for k in ("dx", "dy", "maxexc", "reach", "shiftfar")):
        return 0
    if not _finite(h):
        return 0
    # Guard V6.3: los falsos +/-90 tienen muy poco avance frontal. classify_frame
    # los marca AMBIGUA; no volver a meter su signo como fragmento lateral.
    if float(g["dy"]) < FORWARD_MIN or float(g["reach"]) < FORWARD_MIN:
        return 0

    if float(g["reach"]) < FRAG_FORWARD_MIN:
        return 0
    shift = float(g["shiftfar"]); dx = float(g["dx"]); h = float(h)
    if (abs(float(g["maxexc"])) < FRAG_EXC_MIN
            and abs(shift) < FRAG_SHIFT_MIN
            and abs(h) < FRAG_HEADING_MIN):
        return 0
    src = shift if abs(shift) >= FRAG_SHIFT_MIN else (dx if abs(dx) >= 8.0 else h)
    if abs(src) < 1e-6:
        return 0
    return 1 if src > 0 else -1


class LossArbiter(object):
    def __init__(self):
        self.normal = deque(maxlen=NORMAL_WINDOW)
        self.post = deque(maxlen=POST_WINDOW)
        self.last_intent = "NINGUNA"
        self.last_side = 0
        self.last_intent_t = 0.0
        self.last_intent_heading = None
        self.episode_prior = "NINGUNA"
        self.episode_side = 0
        self.episode_prior_age = None
        self.episode_prior_heading = None
        self.episode_prior_source = "NINGUNA"
        self.episode_t = 0.0
        self._diag_last_sig = None
        self._diag_last_t = 0.0

    def reset_all(self):
        self.normal.clear(); self.post.clear()
        self.last_intent = "NINGUNA"; self.last_side = 0; self.last_intent_t = 0.0
        self.last_intent_heading = None
        self.episode_prior = "NINGUNA"; self.episode_side = 0
        self.episode_prior_age = None; self.episode_prior_heading = None; self.episode_prior_source = "NINGUNA"; self.episode_t = 0.0

    def clear_episode(self):
        self.post.clear()
        self.episode_prior = "NINGUNA"; self.episode_side = 0
        self.episode_prior_age = None; self.episode_prior_heading = None; self.episode_prior_source = "NINGUNA"; self.episode_t = 0.0

    def observe_normal(self, camino_frame, resultado, now=None):
        now = time.monotonic() if now is None else float(now)
        s = classify_frame(camino_frame, resultado)
        # V6: guardar tambien el lado de fragmento y timestamp. Sigue siendo SHADOW:
        # no mueve nada; solo permite reconocer una curva abrupta que se pierde antes
        # de llegar a los 3 votos laterales estables.
        s["fragment_side"] = fragment_side(camino_frame, resultado)
        s["t"] = now
        self.normal.append(s)
        c = Counter(x["raw"] for x in self.normal)
        # Actualizar solo con CONSENSO. Ambiguos de transicion no borran memoria.
        for raw, side in (("LATERAL_DER", 1), ("LATERAL_IZQ", -1)):
            if c[raw] >= NORMAL_LATERAL_NEED and c["LATERAL_IZQ" if side > 0 else "LATERAL_DER"] == 0:
                same = [x for x in self.normal if x["raw"] == raw and _finite(x.get("heading"))]
                hmem = _median([x.get("heading") for x in same], 12.0 * side)
                if hmem is None or abs(float(hmem)) < 10.0:
                    hmem = 12.0 * side
                # Congelar signo coherente con la lateralidad estable; la magnitud
                # sale de los headings que realmente venian antes de la perdida.
                self.last_intent_heading = abs(float(hmem)) * side
                self.last_intent = "LATERAL"; self.last_side = side; self.last_intent_t = now
                return s
        if c["RECTA"] >= NORMAL_STRAIGHT_NEED and c["LATERAL_DER"] + c["LATERAL_IZQ"] <= 1:
            self.last_intent = "RECTA"; self.last_side = 0; self.last_intent_t = now
            self.last_intent_heading = None
        return s

    def begin_episode(self, now=None):
        now = time.monotonic() if now is None else float(now)
        age = (now - self.last_intent_t) if self.last_intent_t > 0 else None
        prior_before = self.last_intent
        side_before = self.last_side
        heading_before = self.last_intent_heading
        self.episode_prior_source = "ESTABLE" if self.last_intent != "NINGUNA" else "NINGUNA"
        if age is not None and age <= PRIOR_MAX_AGE_S:
            self.episode_prior = self.last_intent
            self.episode_side = self.last_side
            self.episode_prior_age = age
            self.episode_prior_heading = self.last_intent_heading
        else:
            self.episode_prior = "NINGUNA"; self.episode_side = 0; self.episode_prior_age = age
            self.episode_prior_heading = None
            self.episode_prior_source = "NINGUNA"

        # V6: rescate de CURVA ABRUPTA que aun figura como RECTA estable.
        # No se activa sobre una recta/gap normal: ahi RECTA acaba de refrescarse
        # (edad < 0.20 s). Tampoco sobre color viejo: si RECTA lleva >0.70 s sin
        # refrescarse, no inventamos lateralidad. Los votos salen SOLO de frames
        # donde main.py ya confirmo linea negra conectada.
        if (self.episode_prior == "RECTA" and age is not None and
                RECTA_STALE_CURVE_MIN_AGE_S <= age <= RECTA_STALE_CURVE_MAX_AGE_S):
            recientes = [x for x in self.normal
                         if _finite(x.get("t")) and (now - float(x["t"])) <= RECTA_STALE_CURVE_RECENT_S]
            fd = sum(1 for x in recientes if x.get("fragment_side") == 1)
            fi = sum(1 for x in recientes if x.get("fragment_side") == -1)
            if fd >= RECTA_STALE_CURVE_FRAG_NEED and fi == 0:
                hs = [x.get("heading") for x in recientes
                      if x.get("fragment_side") == 1 and _finite(x.get("heading"))]
                h = _median(hs, 12.0)
                self.episode_prior = "LATERAL"; self.episode_side = 1
                self.episode_prior_heading = abs(float(h))
                self.episode_prior_source = "PROMOVIDA_DESDE_RECTA_FRAGMENTOS"
            elif fi >= RECTA_STALE_CURVE_FRAG_NEED and fd == 0:
                hs = [x.get("heading") for x in recientes
                      if x.get("fragment_side") == -1 and _finite(x.get("heading"))]
                h = _median(hs, -12.0)
                self.episode_prior = "LATERAL"; self.episode_side = -1
                self.episode_prior_heading = -abs(float(h))
                self.episode_prior_source = "PROMOVIDA_DESDE_RECTA_FRAGMENTOS"

        if LOSS_ARB_DIAG:
            recientes_diag = [x for x in self.normal if _finite(x.get("t")) and (now - float(x["t"])) <= 0.80]
            cd = Counter(x.get("raw") for x in recientes_diag)
            fd = sum(1 for x in recientes_diag if x.get("fragment_side") == 1)
            fi = sum(1 for x in recientes_diag if x.get("fragment_side") == -1)
            print("[ARB-DIAG-PRE] version=%s before=%s/%d age=%s hbefore=%s -> after=%s/%d source=%s hafter=%s | n=%d R=%d LD=%d LI=%d fD=%d fI=%d" % (
                ARB_VERSION, prior_before, side_before,
                ("%.3f" % age) if age is not None else "None",
                ("%.1f" % heading_before) if _finite(heading_before) else "None",
                self.episode_prior, self.episode_side, self.episode_prior_source,
                ("%.1f" % self.episode_prior_heading) if _finite(self.episode_prior_heading) else "None",
                len(recientes_diag), cd["RECTA"], cd["LATERAL_DER"], cd["LATERAL_IZQ"], fd, fi))

        self.episode_t = now
        self.post.clear()
        return dict(prior=self.episode_prior, side=self.episode_side, age_s=age, source=self.episode_prior_source)

    def observe_post(self, camino_frame, resultado, now=None):
        now = time.monotonic() if now is None else float(now)
        s = classify_frame(camino_frame, resultado)
        s["fragment_side"] = fragment_side(camino_frame, resultado)
        s["t"] = now
        self.post.append(s)
        return s

    def _diag_ambigua(self, items, c, now):
        if not LOSS_ARB_DIAG:
            return
        fd = sum(1 for x in items if x.get("fragment_side") == 1)
        fi = sum(1 for x in items if x.get("fragment_side") == -1)
        opp_raw = "LATERAL_IZQ" if self.episode_side > 0 else "LATERAL_DER"
        opp_frag_n = sum(1 for x in items if x.get("fragment_side") == -self.episode_side) if self.episode_side else 0
        block_raw = c[opp_raw] if self.episode_prior == "LATERAL" and self.episode_side else 0
        sig = (tuple((x.get("raw"), x.get("fragment_side")) for x in items),
               self.episode_prior, self.episode_side, block_raw, opp_frag_n)
        # Imprimir cuando cambia la ventana o, como red, cada 0.35 s.
        if sig == self._diag_last_sig and (now - self._diag_last_t) < 0.35:
            return
        self._diag_last_sig = sig
        self._diag_last_t = now
        age = self.episode_prior_age
        print("[ARB-DIAG] prior=%s side=%d source=%s age=%s hprior=%s | R=%d LD=%d LI=%d fD=%d fI=%d | oppRaw=%d/%d oppFrag=%d/%d" % (
            self.episode_prior, self.episode_side, self.episode_prior_source,
            ("%.3f" % age) if age is not None else "None",
            ("%.1f" % self.episode_prior_heading) if _finite(self.episode_prior_heading) else "None",
            c["RECTA"], c["LATERAL_DER"], c["LATERAL_IZQ"], fd, fi,
            block_raw, POST_LATERAL_NEED, opp_frag_n, PRIOR_LATERAL_OPP_FRAG_BLOCK_NEED))
        for i, x in enumerate(items):
            def ff(k):
                v=x.get(k)
                return ("%.1f" % float(v)) if _finite(v) else "-"
            print("[ARB-DIAG] post%d raw=%s frag=%s h=%s dx=%s dy=%s reach=%s exc=%s shift=%s why=%s" % (
                i, x.get("raw"), x.get("fragment_side"), ff("heading"), ff("dx"), ff("dy"),
                ff("reach"), ff("maxexc"), ff("shiftfar"), x.get("reason", "")))

    def decide(self, now=None):
        now = time.monotonic() if now is None else float(now)
        items = list(self.post)
        if not items:
            return dict(kind="AMBIGUA", side=0, heading=None, reason="sin frames post-retro")
        c = Counter(x["raw"] for x in items)

        # 1) Curva post-retro fuerte. Tres frames bastan: no endurecer mas que el
        # recovery que ya fue validado fisicamente.
        for raw, side in (("LATERAL_DER", 1), ("LATERAL_IZQ", -1)):
            same = [x for x in items if x["raw"] == raw]
            opp = c["LATERAL_IZQ" if side > 0 else "LATERAL_DER"]
            if len(same) >= POST_LATERAL_NEED and opp == 0:
                hs = [x["heading"] for x in same if _finite(x.get("heading"))]
                heading = _median(hs, 12.0 * side)
                if abs(float(heading)) < 10.0:
                    heading = 12.0 * side
                return dict(kind="CURVA", side=side, heading=float(heading),
                            reason="%d frames laterales post-retro" % len(same))

        # 1a) V6.5 - par lateral MUY fuerte al inicio + al menos un falso +/-90.
        # Regresion fisica: prior RECTA age=0.753, pero la pose nueva mostro
        # [AMBIGUA falso90, LATERAL_DER fuerte, LATERAL_DER fuerte]. Era una
        # curva cerrada real. No esperar mas frames porque el deque puede perder
        # ese par y terminar en el fallback RECTA/GAP.
        if len(items) <= POST_EARLY_PAIR_MAX_ITEMS:
            false90_early = sum(1 for x in items
                                if x.get("raw") == "AMBIGUA" and
                                x.get("reason") == "sin avance frontal: bloquea falso +/-90")
            if false90_early >= POST_EARLY_PAIR_FALSE90_NEED:
                for raw, side in (("LATERAL_DER", 1), ("LATERAL_IZQ", -1)):
                    same = [x for x in items if x.get("raw") == raw]
                    opp_raw = "LATERAL_IZQ" if side > 0 else "LATERAL_DER"
                    strong = [x for x in same
                              if _finite(x.get("heading")) and abs(float(x.get("heading"))) >= POST_EARLY_PAIR_HEADING_MIN
                              and _finite(x.get("reach")) and float(x.get("reach")) >= POST_EARLY_PAIR_REACH_MIN
                              and _finite(x.get("maxexc")) and float(x.get("maxexc")) >= POST_EARLY_PAIR_EXC_MIN
                              and _finite(x.get("shiftfar")) and abs(float(x.get("shiftfar"))) >= POST_EARLY_PAIR_SHIFT_MIN
                              and ((float(x.get("shiftfar")) > 0) == (side > 0))]
                    if len(strong) >= 2 and c[opp_raw] == 0:
                        hs = [x.get("heading") for x in strong if _finite(x.get("heading"))]
                        heading = _median(hs, 12.0 * side)
                        heading = abs(float(heading)) * side
                        return dict(kind="CURVA", side=side, heading=heading,
                                    reason="V6.5 par lateral fuerte temprano + falso +/-90")

        # 1b) V6.3 - dos laterales fuertes + resto falsos +/-90.
        false90_n = sum(1 for x in items
                        if x.get("raw") == "AMBIGUA" and
                        x.get("reason") == "sin avance frontal: bloquea falso +/-90")
        for raw, side in (("LATERAL_DER", 1), ("LATERAL_IZQ", -1)):
            same = [x for x in items if x["raw"] == raw]
            opp_raw = "LATERAL_IZQ" if side > 0 else "LATERAL_DER"
            if (len(same) >= POST_LATERAL_STRONG_WITH_FALSE90_NEED and
                    c[opp_raw] == 0 and false90_n >= POST_FALSE90_AMBIG_NEED):
                hs = [x["heading"] for x in same if _finite(x.get("heading"))]
                heading = _median(hs, 12.0 * side)
                if abs(float(heading)) < 10.0:
                    heading = 12.0 * side
                return dict(kind="CURVA", side=side, heading=float(heading),
                            reason="%d laterales fuertes + %d ambiguas falso +/-90" %
                                   (len(same), false90_n))

        # 2) Proteccion de curva con pedacito pequeno: la intencion previa debe
        # haber sido lateral y el fragmento post-retro debe coincidir en lado.
        if self.episode_prior == "LATERAL" and self.episode_side:
            frags = [x for x in items if x.get("fragment_side") == self.episode_side]
            opposite = [x for x in items if x.get("fragment_side") == -self.episode_side]
            if len(frags) >= 2 and not opposite:
                hs = [x["heading"] for x in frags if _finite(x.get("heading"))]
                heading = _median(hs, 12.0 * self.episode_side)
                if heading is None or abs(float(heading)) < 10.0:
                    heading = 12.0 * self.episode_side
                # Forzar solo el SIGNO heredado; la magnitud sigue viniendo del
                # heading observado cuando existe.
                heading = abs(float(heading)) * self.episode_side
                return dict(kind="CURVA", side=self.episode_side, heading=heading,
                            reason="lateral previa + fragmento pequeno compatible")

        # 3) Recta post-retro clara.
        #
        # CORRECCION FISICA 2026-09-05: en las curvas MAS CERRADAS, despues de
        # retroceder 400 ms, CAMINO puede ver durante varios frames solo el tramo
        # local/tangente de la curva y clasificarlo RECTA. Con la V3, 3 RECTAS
        # hacian return AMBIGUA ACA MISMO, por lo que el fallback lateral de abajo
        # JAMAS llegaba a ejecutarse aunque la intencion previa fuese LATERAL con
        # edad 0.29-0.54 s. Ese es exactamente el patron medido en robot.
        #
        # Si la intencion previa NO era lateral, 3 rectas siguen significando
        # RECTA/GAP como antes. Si era LATERAL, no usamos la tangente post-retro
        # para borrar una intencion muy reciente: dejamos que el fallback de abajo
        # decida. La barrera del lado contrario se mantiene intacta.
        if c["RECTA"] >= POST_STRAIGHT_NEED:
            if self.episode_prior != "LATERAL":
                return dict(kind="RECTA", side=0, heading=None,
                            reason="recta clara post-retro")
            # Con prior LATERAL, NO retornar aca: caer al fallback temporal.

        # 3b) V6.4 - extension SOLO para lateral ESTABLE + colapso puro falso +/-90.
        # Caso fisico: prior=LATERAL side=-1 age=0.617, hprior=-39.2 y 7/7
        # frames post-retro AMBIGUA por falta de avance, sin RECTA, sin laterales
        # fuertes y sin fragmentos. El corte global 0.60 lo frenaba por 17 ms.
        # No extendemos el fallback promovido desde RECTA: eso protege el falso
        # LATERAL observado al entrar al plateado alrededor de 0.602 s.
        false90_n = sum(1 for x in items
                        if x.get("raw") == "AMBIGUA" and
                        x.get("reason") == "sin avance frontal: bloquea falso +/-90")
        if (self.episode_prior == "LATERAL" and self.episode_side and
                self.episode_prior_source == "ESTABLE" and
                self.episode_prior_age is not None and
                self.episode_prior_age <= PRIOR_LATERAL_STABLE_FALSE90_MAX_AGE_S and
                len(items) >= PRIOR_LATERAL_STABLE_FALSE90_NEED and
                false90_n >= PRIOR_LATERAL_STABLE_FALSE90_NEED and
                c["RECTA"] == 0 and c["LATERAL_DER"] == 0 and c["LATERAL_IZQ"] == 0 and
                all(x.get("fragment_side") == 0 for x in items)):
            h = self.episode_prior_heading
            if not _finite(h):
                h = 12.0 * self.episode_side
            h = abs(float(h)) * self.episode_side
            return dict(kind="CURVA", side=self.episode_side, heading=h,
                        reason="V6.4 lateral ESTABLE + colapso falso +/-90 post-retro")

        # 4) FALLBACK DE REGRESION PARA CURVA REAL.
        # Logs fisicos del 2026-09-05: tres curvas que el backup funcional giraba
        # llegaron aqui con intencion previa LATERAL MUY fresca (0.289-0.463 s),
        # pero la pose post-retro solo produjo AMBIGUA y el V1 termino en STOP.
        #
        # Regla asimetrica: una evidencia LATERAL estable y reciente NO se borra
        # solo porque despues del retroceso CAMINO se quede sin geometria suficiente.
        # Solo se permite si la pose nueva NO aporta evidencia positiva que la refute:
        #   - la intencion LATERAL es MUY reciente (<=0.60 s),
        #   - no hay lateral fuerte del lado opuesto,
        #   - no hay fragmento parcial del lado opuesto.
        # Esto preserva las curvas ya validadas sin convertir rojo/plateado en curva:
        # en los replays de color la intencion previa era RECTA, no LATERAL.
        if (self.episode_prior == "LATERAL" and self.episode_side and
                self.episode_prior_age is not None and
                self.episode_prior_age <= PRIOR_LATERAL_FALLBACK_MAX_AGE_S and
                len(items) >= PRIOR_LATERAL_FALLBACK_MIN_POST):
            opp_raw = "LATERAL_IZQ" if self.episode_side > 0 else "LATERAL_DER"
            opp_frag = [x for x in items if x.get("fragment_side") == -self.episode_side]
            # V6: 1-2 fragmentos contrarios NO alcanzan para refutar una lateral
            # estable y reciente. En las curvas mas cerradas la perspectiva post-
            # retroceso puede invertir un fragmento aislado. Si hay 3 laterales
            # fuertes contrarias, el paso 1 de arriba ya decide esa CURVA; si solo
            # hay fragmentos parciales, exigimos 3 sostenidos antes de bloquear.
            if c[opp_raw] < POST_LATERAL_NEED and len(opp_frag) < PRIOR_LATERAL_OPP_FRAG_BLOCK_NEED:
                h = self.episode_prior_heading
                if not _finite(h):
                    # Ultimo recurso: usar headings post compatibles si existen; si
                    # no, una magnitud minima. El pivote fisico conserva su formula
                    # 28 + 0.26*|heading| y sus limites actuales.
                    compatibles = [x.get("heading") for x in items
                                   if _finite(x.get("heading")) and
                                   (x.get("fragment_side") in (0, self.episode_side))]
                    h = _median(compatibles, 12.0 * self.episode_side)
                h = abs(float(h)) * self.episode_side
                return dict(kind="CURVA", side=self.episode_side, heading=h,
                            reason="lateral previa muy reciente + post ambiguo no la refuta")

        # 5) Rojo/plateado/GAP pueden dejar CAMINO sin camino util justo al final.
        # Si venia recta estable y cinco frames post-retro NO muestran lateralidad,
        # es mas seguro buscar recto con APDS activo que inventar un pivote.
        if self.episode_prior == "RECTA" and len(items) >= POST_FALLBACK_STRAIGHT_N:
            if c["LATERAL_DER"] == 0 and c["LATERAL_IZQ"] == 0:
                return dict(kind="RECTA", side=0, heading=None,
                            reason="recta previa + colapso frontal sin evidencia lateral")

        fd = sum(1 for x in items if x.get("fragment_side") == 1)
        fi = sum(1 for x in items if x.get("fragment_side") == -1)
        self._diag_ambigua(items, c, now)
        return dict(kind="AMBIGUA", side=0, heading=None,
                    reason=("evidencia insuficiente R=%d LD=%d LI=%d fD=%d fI=%d prior=%s/%d age=%s" %
                            (c["RECTA"], c["LATERAL_DER"], c["LATERAL_IZQ"], fd, fi,
                             self.episode_prior, self.episode_side,
                             ("%.3f" % self.episode_prior_age) if self.episode_prior_age is not None else "None")))


# ---------------------------- selftest -------------------------------------
def _fake(raw, h=0.0):
    # No usa classify_frame: sirve para probar la maquina temporal de forma pura.
    return dict(raw=raw, sign=(1 if raw.endswith("DER") else -1 if raw.endswith("IZQ") else 0),
                heading=h, small_heading=False, reason="fake", dx=0, dy=60,
                maxexc=10, span=10, reach=60, shiftfar=0, npath=60,
                fragment_side=0, t=0)


def selftest():
    # Geometria: heading pequeno pero path lateral debe ser curva.
    cf = dict(confiable=True, heading_frame=20.0)
    rr = dict(start=(80, 115), target=(96, 65),
              path=[(80+i*0.7, 115-i) for i in range(51)])
    g = classify_frame(cf, rr)
    assert g["raw"].startswith("LATERAL"), g
    assert g["small_heading"], g

    # Regresion hallada en la primera prueba fisica: una curva real puede quedar
    # apenas debajo del gate viejo (exc=30, shift=22, dx=30) y NO debe caer a AMBIGUA.
    cf = dict(confiable=True, heading_frame=-42.0)
    rr = dict(start=(80, 115), target=(50, 82),
              path=[(80 - 30.0*i/33.0, 115-i) for i in range(34)])
    g = classify_frame(cf, rr)
    assert g["raw"] == "LATERAL_IZQ", g

    # Una recta real sigue sin convertirse en curva por relajar el borde lateral.
    cf = dict(confiable=True, heading_frame=8.0)
    rr = dict(start=(80, 115), target=(86, 60),
              path=[(80 + 6.0*i/55.0, 115-i) for i in range(56)])
    g = classify_frame(cf, rr)
    assert g["raw"] == "RECTA", g

    # Falso 90 sin avance.
    g = classify_frame(dict(confiable=True, heading_frame=90.0),
                       dict(start=(80,115), target=(120,112), path=[(80+i,115) for i in range(12)]))
    assert g["raw"] == "AMBIGUA", g

    # Regresion fisica: lateral previa MUY reciente + 3 rectas post-retro
    # puede ser la tangente de una curva cerrada; debe conservar CURVA, no GAP/STOP.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=1; a.last_intent_t=10
    a.last_intent_heading=40.0
    a.begin_episode(10.2)
    a.post.extend([_fake("RECTA") for _ in range(3)])
    d=a.decide(10.3); assert d["kind"] == "CURVA" and d["side"] == 1, d

    # Regresion fisica V6.1: curva real con SOLO 2 laterales fuertes del mismo
    # lado y el resto de la ventana son AMBIGUA del guard falso +/-90. Debe
    # recuperar como curva; esos ambiguos no son evidencia lateral contraria.
    a = LossArbiter(); a.begin_episode(1.0)
    li1=_fake("LATERAL_IZQ", -73.5); li1["reason"]="continuacion lateral"
    li2=_fake("LATERAL_IZQ", -68.7); li2["reason"]="continuacion lateral"
    amb=[]
    for h in (79.2,82.2,-90.0,-90.0,-82.9):
        q=_fake("AMBIGUA", h); q["reason"]="sin avance frontal: bloquea falso +/-90"
        q["reach"]=13; q["dy"]=13; q["fragment_side"]=0
        amb.append(q)
    a.post.extend([li1,li2]+amb)
    d=a.decide(1.2); assert d["kind"]=="CURVA" and d["side"]==-1, d

    # Regresion FISICA V6.5: curva cerrada DERECHA. El prior todavia era
    # RECTA vieja (0.753 s), pero los primeros 3 post fueron un falso +/-90 y
    # dos laterales DERECHA muy fuertes. Debe decidir CURVA inmediatamente,
    # antes de que esos dos frames salgan de la ventana y el fallback diga GAP.
    a = LossArbiter(); a.last_intent="RECTA"; a.last_intent_t=10.0
    a.begin_episode(10.753)
    q=_fake("AMBIGUA",83.7); q.update(reason="sin avance frontal: bloquea falso +/-90",
        dx=29.0,dy=11.0,reach=12.0,maxexc=63.0,shiftfar=43.0,fragment_side=0)
    d1=_fake("LATERAL_DER",74.4); d1.update(reason="continuacion lateral",
        dx=44.0,dy=20.0,reach=20.0,maxexc=61.0,shiftfar=41.0,fragment_side=1)
    d2=_fake("LATERAL_DER",71.0); d2.update(reason="continuacion lateral",
        dx=58.0,dy=20.0,reach=23.0,maxexc=58.0,shiftfar=39.0,fragment_side=1)
    a.post.extend([q,d1,d2])
    d=a.decide(10.9); assert d["kind"]=="CURVA" and d["side"]==1, d

    # La misma regla debe ser simetrica para IZQUIERDA.
    a = LossArbiter(); a.last_intent="RECTA"; a.last_intent_t=20.0
    a.begin_episode(20.753)
    q=_fake("AMBIGUA",-83.7); q.update(reason="sin avance frontal: bloquea falso +/-90",
        dx=-29.0,dy=11.0,reach=12.0,maxexc=63.0,shiftfar=-43.0,fragment_side=0)
    i1=_fake("LATERAL_IZQ",-74.4); i1.update(reason="continuacion lateral",
        dx=-44.0,dy=20.0,reach=20.0,maxexc=61.0,shiftfar=-41.0,fragment_side=-1)
    i2=_fake("LATERAL_IZQ",-71.0); i2.update(reason="continuacion lateral",
        dx=-58.0,dy=20.0,reach=23.0,maxexc=58.0,shiftfar=-39.0,fragment_side=-1)
    a.post.extend([q,i1,i2])
    d=a.decide(20.9); assert d["kind"]=="CURVA" and d["side"]==-1, d

    # No debe disparar por un par lateral debil de transicion.
    a = LossArbiter(); a.last_intent="RECTA"; a.last_intent_t=30.0
    a.begin_episode(30.753)
    q=_fake("AMBIGUA",80.0); q.update(reason="sin avance frontal: bloquea falso +/-90",
        dy=12.0,reach=12.0,maxexc=50.0,shiftfar=35.0)
    d1=_fake("LATERAL_DER",40.0); d1.update(reach=20.0,maxexc=35.0,shiftfar=22.0)
    d2=_fake("LATERAL_DER",42.0); d2.update(reach=21.0,maxexc=36.0,shiftfar=23.0)
    a.post.extend([q,d1,d2])
    assert a.decide(30.9)["kind"] != "CURVA"

    # Recta previa + colapso sin lateral -> recta/GAP.
    a = LossArbiter(); a.last_intent="RECTA"; a.last_intent_t=10
    a.begin_episode(10.1)
    a.post.extend([_fake("AMBIGUA") for _ in range(5)])
    assert a.decide(10.4)["kind"] == "RECTA"

    # Curva post fuerte -> curva.
    a = LossArbiter(); a.begin_episode(1)
    a.post.extend([_fake("LATERAL_DER", 45) for _ in range(3)])
    d=a.decide(1.2); assert d["kind"]=="CURVA" and d["side"]==1, d

    # Lateral previa + pedacito pequeno compatible, aunque no sea lateral fuerte.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=1; a.last_intent_t=5.0
    a.begin_episode(5.1)
    cf_frag=dict(confiable=True, heading_frame=12.0)
    rr_frag=dict(start=(80,115), target=(89,96),
                 path=[(80+i*0.55,115-i) for i in range(20)])
    a.observe_post(cf_frag,rr_frag,5.2); a.observe_post(cf_frag,rr_frag,5.25)
    d=a.decide(5.3); assert d["kind"]=="CURVA" and d["side"]==1, d

    # Sin historia previa, el mismo fragmento NO alcanza para inventar curva.
    a = LossArbiter(); a.begin_episode(5.1)
    a.observe_post(cf_frag,rr_frag,5.2); a.observe_post(cf_frag,rr_frag,5.25)
    assert a.decide(5.3)["kind"]=="AMBIGUA"

    # Regresion FISICA 2026-09-05: lateral estable MUY reciente + pose nueva
    # totalmente ambigua debe conservar CURVA, no terminar en STOP.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=1; a.last_intent_t=10.0
    a.last_intent_heading=41.0
    a.begin_episode(10.463)
    a.post.extend([_fake("AMBIGUA") for _ in range(3)])
    d=a.decide(10.7); assert d["kind"]=="CURVA" and d["side"]==1 and abs(d["heading"]-41.0)<1e-6, d

    # La misma memoria, si ya es vieja, NO puede inventar una curva.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=-1; a.last_intent_t=10.0
    a.last_intent_heading=-38.0
    a.begin_episode(10.9)
    a.post.extend([_fake("AMBIGUA") for _ in range(4)])
    assert a.decide(11.0)["kind"]=="AMBIGUA"

    # Segunda regresion fisica: incluso 5 RECTAS post-retro pueden ser solo la
    # tangente local de una curva muy cerrada. Con prior LATERAL <=0.60 s se
    # conserva la curva. Esto cubre los casos reales edad=0.292 y 0.544 s.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=-1; a.last_intent_t=10.0
    a.last_intent_heading=-48.0
    a.begin_episode(10.544)
    a.post.extend([_fake("RECTA") for _ in range(5)])
    d=a.decide(10.7); assert d["kind"]=="CURVA" and d["side"]==-1, d

    # Si esa lateral previa ya paso de 0.60 s, NO puede forzar una curva.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=1; a.last_intent_t=10.0
    a.last_intent_heading=35.0
    a.begin_episode(10.61)
    a.post.extend([_fake("RECTA") for _ in range(5)])
    assert a.decide(10.8)["kind"]=="AMBIGUA"

    # Un fragmento del lado CONTRARIO tambien bloquea el fallback.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=1; a.last_intent_t=10.0
    a.last_intent_heading=35.0
    a.begin_episode(10.3)
    q=_fake("AMBIGUA"); q["fragment_side"]=-1
    a.post.extend([dict(q) for _ in range(3)])
    assert a.decide(10.5)["kind"]=="AMBIGUA"

    # Sin intencion recta previa, cinco ambiguos tampoco deben convertirse en GAP.
    a = LossArbiter(); a.begin_episode(1)
    a.post.extend([_fake("AMBIGUA") for _ in range(5)])
    assert a.decide(1.3)["kind"]=="AMBIGUA"

    # V6.4 caso fisico exacto: lateral ESTABLE 0.617 s + 7 falsos +/-90
    # sin ninguna evidencia fuerte post-retro -> debe conservar CURVA IZQ.
    a = LossArbiter(); a.last_intent="LATERAL"; a.last_side=-1; a.last_intent_t=10.0
    a.last_intent_heading=-39.2
    a.begin_episode(10.617)
    for h,dy,reach,exc,shift in [(86,5,10,71,48),(86,5,10,71,48),(84.5,7,13,73,50),
                                  (77.5,14,17,63,43),(76,16,19,64,44),(76,16,18,64,44),(76,16,19,64,44)]:
        q=_fake("AMBIGUA", h); q["reason"]="sin avance frontal: bloquea falso +/-90"
        q["dy"]=dy; q["reach"]=reach; q["maxexc"]=exc; q["shiftfar"]=shift; q["fragment_side"]=0
        a.post.append(q)
    d=a.decide(10.8); assert d["kind"]=="CURVA" and d["side"]==-1, d

    # Proteccion plateado: una lateral PROMOVIDA desde RECTA a ~0.602 s NO usa
    # la extension V6.4 aunque el post-retro colapse en falsos +/-90.
    a = LossArbiter(); a.episode_prior="LATERAL"; a.episode_side=-1
    a.episode_prior_age=0.602; a.episode_prior_heading=-35.0
    a.episode_prior_source="PROMOVIDA_DESDE_RECTA_FRAGMENTOS"
    for _ in range(7):
        q=_fake("AMBIGUA", 82.0); q["reason"]="sin avance frontal: bloquea falso +/-90"
        q["dy"]=12; q["reach"]=12; q["fragment_side"]=0
        a.post.append(q)
    assert a.decide(1.0)["kind"]=="AMBIGUA", a.decide(1.0)

    print("camino_loss_arbiter: SELFTEST OK")


if __name__ == "__main__":
    selftest()
