# -*- coding: utf-8 -*-
"""
VISION_LINEA - enchufa la vision nueva al lazo de produccion, sin romperlo.

Hasta ahora todo el trabajo de `nuevo code` vivia en bancos de replay. `Main.py`
seguia corriendo la vision vieja (centroide + atan2) y no habia forma de elegir.
Este modulo es el interruptor.

============================================================================
 APAGADO POR DEFECTO
============================================================================
Sin la variable de entorno `VISION_LINEA` este modulo NO IMPORTA NADA PESADO,
no construye ningun objeto y `angulo()` devuelve None al instante. Main.py se
comporta EXACTAMENTE como hoy.

    VISION_LINEA=camino  python3 Main.py     # candidata + CAMINO + MONO
    VISION_LINEA=base    python3 Main.py     # candidata tal cual (SinBranch)
    VISION_LINEA=v1      python3 Main.py     # POI sobre contorno (Airborne V1)
    python3 Main.py                          # vision vieja, sin cambios

============================================================================
 NUNCA VOLTEA UNA CORRIDA
============================================================================
Mismo contrato que `telemetria_vision.py`, y por la misma razon: lo que corre en
la Raspberry es un archivo suelto, asi que alcanza con olvidarse de copiar un
.py al lado para que la vision no arranque.

  * el import de la candidata va adentro de un try, y si falla se apaga sola;
  * `angulo()` NUNCA levanta una excepcion hacia el lazo: si algo explota, se
    desactiva para siempre y devuelve None, y Main.py usa el angulo viejo;
  * `None` significa "no opino": el llamador se queda con lo que ya tenia.

============================================================================
 QUE ENTRA Y QUE SALE
============================================================================
Entra `frame_resized` de Main.py: 160x120 BGR, ya rotado 180. Es EXACTAMENTE lo
que produce `nuevo_code_v2.frame_pi`, y los umbrales de negro coinciden
([0,0,0] a [90,90,90] en los dos lados), asi que no hay conversion.

Sale el angulo en la misma convencion que la vision vieja: positivo a la
izquierda, saturado a +-90. Main.py lo manda por el mismo protocolo.

`ultimo()` devuelve las cinco etapas del target y la razon de cada guard, para
que la telemetria las pueda registrar sin volver a calcular nada.
"""

import math
import os

# --- anticipacion de curva -------------------------------------------------
# Umbral de curvatura calibrado sobre 13.220 frames de los 10 autonomos
# (curva_cerrada.py): p75 de la distribucion observada. Por debajo de esto el
# camino visible es "recta o curva suave" y se va a velocidad plena.
KAPPA_REF = 139.5
# Piso del factor de velocidad. Preregistrado: la Teensy ya rampa de 40 a 50 con
# absSteer, asi que esto NO es el freno principal: es la ANTICIPACION.
FACTOR_MIN = 0.55

MODO = (os.environ.get("VISION_LINEA") or "").strip().lower()
ACTIVA = MODO in ("1", "si", "base", "camino", "v1")

# --- ley de steer: separar POSICION de RUMBO -------------------------------
# Defecto 3.5.1 del traspaso. La ley de hoy es un solo numero y mezcla las dos
# cosas con UNA ganancia, y nunca ve la velocidad. Stanley las separa:
#
#     delta = psi + arctan(k*e / v)
#
# APAGADA POR DEFECTO. Sin LEY_STEER=stanley el angulo que sale es el mismo de
# siempre, bit a bit -verificado sobre 13.061 frames, 0 discrepancias-.
#
#     VISION_LINEA=camino LEY_STEER=stanley python3 Main.py
#
# Los parametros salen de sep_pos_rumbo2.py y NO se eligieron para ganar una
# metrica: k por reparto de varianza -conserva el balance 47,5/52,5 que la ley
# actual ya tiene- y g para conservar EXACTAMENTE el maximo de +89 del control
# positivo de lineal f800-872, que es la regla que no se negocia. Se pueden
# barrer por entorno el dia de robot sin tocar el codigo.
LEY = (os.environ.get("LEY_STEER") or "").strip().lower()
LEY_ACTIVA = LEY in ("stanley", "1", "si")


def _envf(nombre, defecto):
    try:
        return float(os.environ.get(nombre) or defecto)
    except Exception:
        return defecto


LEY_K = _envf("LEY_STEER_K", 4.4794)
LEY_G = _envf("LEY_STEER_G", 0.7419)
LEY_KPSI = _envf("LEY_STEER_KPSI", 1.0)
LEY_HFOV = _envf("LEY_STEER_HFOV", 60.0)
LEY_ARCO = _envf("LEY_STEER_ARCO", 0.60)

_LS = None                 # ley_steer, importado perezosamente igual que todo
_LS_FALLO = False          # si el import falla, no se reintenta ni se reimprime
_NFRAME = 0
_FACTOR = 1.0
_FACTOR_EN = -1

_tr = None
_v2 = None
_CP = None
_modo_real = None
_fallos = 0
_ULT = {}

MAX_FALLOS = 5          # despues de esto se apaga sola y no vuelve a intentar


def _arrancar():
    """Import y construccion perezosos. Solo se llama si ACTIVA."""
    global _tr, _v2, _modo_real, ACTIVA
    import importlib.util
    import sys
    aqui = os.path.dirname(os.path.abspath(__file__))
    if aqui not in sys.path:
        sys.path.insert(0, aqui)
    fps = 100.0 / 3.0

    if MODO == "v1":
        sp = importlib.util.spec_from_file_location(
            "airborne_v1", os.path.join(aqui, "airborne_v1_adaptado.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        _tr = m.AirborneV1(fps)
        _v2 = m
        _modo_real = "v1"
        return

    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(aqui, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    _v2 = v4.v3.v2

    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, f):
            v4.NuevoCodeV4.__init__(self, f)
            self.branch_guard = _Nulo()

    _tr = SinBranch(fps)

    # poi_component es SOLO DIAGNOSTICO: `r["poi"]` lo lee unicamente
    # draw_panel, que en el robot no corre. Y pesa: medido sobre 31.030 frames,
    # sacarlo baja el p50 de CAMINO+MONO de 1,609 a 1,483 ms, que es EXACTAMENTE
    # el p50 del baseline. O sea que apagarlo paga integro el sobrecosto de
    # CAMINO+MONO: la version buena sale al mismo precio que la de hoy.
    # Se neutraliza aca, en el modulo de integracion, sin tocar nuevo_code_v3.
    _v3 = v4.v3
    if not os.environ.get("VISION_LINEA_CON_POI"):
        _v3.poi_component = lambda comp, ref_x=None: dict(
            top=None, bottom=None, left=None, right=None)

    if MODO in ("1", "si", "camino"):
        sp2 = importlib.util.spec_from_file_location(
            "camino_principal", os.path.join(aqui, "camino_principal.py"))
        cp = importlib.util.module_from_spec(sp2)
        sp2.loader.exec_module(cp)
        cp.instalar(_v2, dict(camino=True, mono=True))
        globals()["_CP"] = cp
        _modo_real = "camino+mono"
    else:
        sp2 = importlib.util.spec_from_file_location(
            "camino_principal", os.path.join(aqui, "camino_principal.py"))
        cp = importlib.util.module_from_spec(sp2)
        sp2.loader.exec_module(cp)
        cp.instalar(_v2, dict(camino=False, mono=False))   # solo para espiar
        globals()["_CP"] = cp
        _modo_real = "base"


def _curvatura():
    """Curvatura del camino visible, en grados por unidad de suelo.

    Devuelve None si no hay camino usable o si el modo no tiene esqueleto.
    Lee el arbol de Dijkstra que la propia candidata acaba de calcular: no
    recalcula nada.
    """
    try:
        cp = _CP
        if cp is None or "dist" not in cp.CAP:
            return None
        pts, dist = cp.CAP["pts"], cp.CAP["dist"]
        prev, si = cp.CAP["prev"], cp.CAP["si"]
        import numpy as _np
        fin = _np.where(_np.isfinite(dist))[0]
        if len(fin) < 8:
            return None
        F = int(fin[int(_np.argmax(dist[fin]))])
        cad = _v2.reconstruct(prev, si, F)
        if not cad or len(cad) < 8:
            return None
        f_px = (_v2.W / 2.0) / math.tan(math.radians(60.0 / 2.0))

        def suelo(u, v):
            z = (119.0 - 9.0) / max(v - 9.0, 1e-6)
            return ((u - _v2.CENTER) * z / f_px, z)

        P = [suelo(pts[i][1], pts[i][0]) for i in cad]
        Q = P[::6] if len(P) >= 18 else P
        if len(Q) < 3:
            return None
        arco = 0.0
        hs = []
        for a, b in zip(Q, Q[1:]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz)
            if L < 1e-9:
                continue
            arco += L
            hs.append(math.degrees(math.atan2(dx, dz)))
        if len(hs) < 2 or arco < 1e-9:
            return None
        giro = sum(abs((b - a + 180) % 360 - 180) for a, b in zip(hs, hs[1:]))
        return giro / arco
    except Exception:
        return None


def velocidad(base):
    """Velocidad recomendada, anticipando la curva. Devuelve None si no opina.

    NO es un calculo fisico absoluto: es un factor RELATIVO calibrado sobre la
    distribucion de curvatura medida. La Teensy ya rampa con absSteer; esto
    aporta lo que absSteer no puede, que es llegar a la curva ya frenado.

    ESTO NO SE PUEDE VALIDAR CON REPLAY: frenar cambia la trayectoria y por lo
    tanto cambia lo que la camara ve. Es prueba de sabado.
    """
    if not ACTIVA or _tr is None:
        return None
    f = _factor_velocidad()
    if f >= 1.0:
        return None
    return int(round(base * f))


def _factor_velocidad():
    """Factor de velocidad anticipada en [FACTOR_MIN, 1,0], 1,0 = sin frenar.

    Se cachea por frame porque ahora hay DOS consumidores: `velocidad()`, que
    lo manda por el byte `speed`, y la ley de steer, que lo necesita como `v`
    para dividir el termino de posicion. Los dos tienen que ver el MISMO
    numero: si la ley usara una velocidad distinta de la que se comanda, el
    lazo estaria compensando una velocidad que el robot no va a tener.
    """
    global _FACTOR, _FACTOR_EN
    if _FACTOR_EN == _NFRAME:
        return _FACTOR
    k = _curvatura()
    if k is None:
        f = 1.0
    else:
        _ULT["kappa"] = round(k, 1)
        f = 1.0 if k <= KAPPA_REF else max(FACTOR_MIN, min(1.0, KAPPA_REF / k))
    _ULT["factor_vel"] = round(f, 3)
    _FACTOR, _FACTOR_EN = f, _NFRAME
    return f


def _angulo_de(x):
    W, C = _v2.W, _v2.CENTER
    a = -90.0 * (x - C) / (W / 2.0)
    return max(-90.0, min(90.0, a))


def _ley(r):
    """El angulo que sale. Ley de hoy, o Stanley si LEY_STEER esta encendida.

    Contrato: si la ley nueva no puede opinar -no hay camino, no hay rumbo-
    NO devuelve None. Cae a la ley de hoy. `None` significa "quedate con el
    atan2 viejo de Main.py", que es peor que cualquiera de las dos.
    """
    global _LS, _LS_FALLO
    viejo = _angulo_de(float(r["target"][0]))
    if not LEY_ACTIVA or _LS_FALLO:
        return viejo
    try:
        if _LS is None:
            import importlib.util
            import sys
            aqui = os.path.dirname(os.path.abspath(__file__))
            sp = importlib.util.spec_from_file_location(
                "ley_steer", os.path.join(aqui, "ley_steer.py"))
            m = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m)
            _LS = m
            print("[LEY-STEER] stanley  k=%.4f g=%.4f k_psi=%.2f hfov=%.0f "
                  "arco=%.2f" % (LEY_K, LEY_G, LEY_KPSI, LEY_HFOV, LEY_ARCO))
        c = _LS.componentes(r, v_norm=_factor_velocidad(), k=LEY_K,
                            k_psi=LEY_KPSI, g=LEY_G, hfov=LEY_HFOV,
                            arco=LEY_ARCO)
    except Exception as e:                                # pragma: no cover
        # UNA sola vez. La version anterior imprimia por frame: con el archivo
        # ausente eran 459 prints en 461 frames, y en la Pi eso es I/O
        # sincronico adentro del lazo de vision, o sea FPS que se pierde por
        # avisar de algo que ya no va a cambiar.
        _LS_FALLO = True
        print("[LEY-STEER] fallo (%s): APAGADA, sigo con la ley de hoy" % e)
        return viejo
    if c is None:
        _ULT["ley"] = "cae_a_vieja"
        return viejo
    _ULT.update(ley="stanley", e_pos=round(c["e"], 4),
                psi=round(c["psi"], 2), t_pos=round(c["t_pos"], 2),
                t_psi=round(c["t_psi"], 2), ang_viejo=round(viejo, 2))
    return c["delta"]


def angulo(frame_resized):
    """Devuelve el angulo en grados, o None si no opina.

    None significa "quedate con el que ya tenias". Nunca levanta excepcion.
    """
    global _tr, ACTIVA, _fallos, _NFRAME
    if not ACTIVA:
        return None
    _NFRAME += 1
    try:
        if _tr is None:
            _arrancar()
            print("[VISION-LINEA] activa en modo %s" % _modo_real)
        if _modo_real == "v1":
            r = _tr.paso(frame_resized)
            t = r.get("target")
            a = r.get("angle_target")
            _ULT.clear()
            _ULT.update(estado=r.get("estado"), target=t,
                        motivo=r.get("motivo_target"), modo=_modo_real)
            if t is None or a is None or a != a:      # a != a captura NaN
                return None
            return float(a)
        r = _tr.step(frame_resized)
        t = r.get("target")
        _ULT.clear()
        _ULT.update(estado=r.get("state"), target=t,
                    geom=r.get("target_geometric"),
                    branch=r.get("target_branch"),
                    spatial=r.get("spatial_guard"),
                    salto=r.get("proposed_jump_px"),
                    razon=r.get("reason"), modo=_modo_real,
                    inicio=r.get("start"), rumbo_chord=r.get("heading"),
                    raw=r.get("target_raw"), cap=r.get("target_cap"))
        if t is None:
            return None
        return _ley(r)
    except Exception as e:                            # pragma: no cover
        _fallos += 1
        print("[VISION-LINEA] fallo %d/%d: %s" % (_fallos, MAX_FALLOS, e))
        if _fallos >= MAX_FALLOS:
            ACTIVA = False
            print("[VISION-LINEA] APAGADA. Sigo con la vision vieja.")
        return None


def ultimo():
    """Las cinco etapas y las razones del ultimo frame, para telemetria."""
    return dict(_ULT)


def estado():
    return dict(activa=ACTIVA, modo=_modo_real, fallos=_fallos)
