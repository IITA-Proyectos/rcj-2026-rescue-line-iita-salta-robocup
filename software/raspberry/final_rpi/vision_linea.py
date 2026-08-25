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

MODO = (os.environ.get("VISION_LINEA") or "").strip().lower()
ACTIVA = MODO in ("1", "si", "base", "camino", "v1")

_tr = None
_v2 = None
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

    if MODO in ("1", "si", "camino"):
        sp2 = importlib.util.spec_from_file_location(
            "camino_principal", os.path.join(aqui, "camino_principal.py"))
        cp = importlib.util.module_from_spec(sp2)
        sp2.loader.exec_module(cp)
        cp.instalar(_v2, dict(camino=True, mono=True))
        _modo_real = "camino+mono"
    else:
        _modo_real = "base"


def _angulo_de(x):
    W, C = _v2.W, _v2.CENTER
    a = -90.0 * (x - C) / (W / 2.0)
    return max(-90.0, min(90.0, a))


def angulo(frame_resized):
    """Devuelve el angulo en grados, o None si no opina.

    None significa "quedate con el que ya tenias". Nunca levanta excepcion.
    """
    global _tr, ACTIVA, _fallos
    if not ACTIVA:
        return None
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
                    razon=r.get("reason"), modo=_modo_real)
        if t is None:
            return None
        return _angulo_de(float(t[0]))
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
