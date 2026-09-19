# -*- coding: utf-8 -*-
"""CAMINO+MONO como SENSOR DE RUMBO para recuperacion.

NO reemplaza el control normal del robot.
NO devuelve un steer para seguir linea.
Solo corre CAMINO+MONO en paralelo y conserva el ultimo `heading` confiable
(HIGH/MEDIUM) calculado por la cadena seleccionada.

Convencion importante:
    heading > 0  -> camino hacia la DERECHA (DER+)
    heading < 0  -> camino hacia la IZQUIERDA
El main de produccion convierte luego a la convencion historica del protocolo
(derecha negativa) haciendo `angle_recup = -heading` SOLO cuando GS=4.
"""
import importlib.util
import math
import os
import time


class CaminoHeading(object):
    def __init__(self, fps=100.0 / 3.0):
        self.fps = float(fps)
        self.ultimo_heading = None
        self.ultimo_t = 0.0
        self.ultimo_estado = "SIN_DATO"
        self.ultimo_target = None
        self.ultimo_resultado = None
        self._cargar()

    @staticmethod
    def _cargar_mod(nombre, ruta):
        sp = importlib.util.spec_from_file_location(nombre, ruta)
        if sp is None or sp.loader is None:
            raise ImportError("no se pudo crear spec para %s" % ruta)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    def _cargar(self):
        aqui = os.path.dirname(os.path.abspath(__file__))
        v4 = self._cargar_mod("recup_nuevo_code_v4", os.path.join(aqui, "nuevo_code_v4.py"))
        v2 = v4.v3.v2

        # Igual que vision_linea.py en modo CAMINO: V4 pero sin BranchGuard,
        # porque CAMINO+MONO decide la cadena dentro de path_target.
        class _Nulo(object):
            def step(self, proposed, skel):
                return proposed, "PASA"

        class SinBranch(v4.NuevoCodeV4):
            def __init__(self, fps):
                v4.NuevoCodeV4.__init__(self, fps)
                self.branch_guard = _Nulo()

        # POI es diagnostico y no aporta al heading. Neutralizarlo evita pagar
        # ese costo en la Pi, igual que la integracion medida del repo.
        v4.v3.poi_component = lambda comp, ref_x=None: dict(
            top=None, bottom=None, left=None, right=None
        )

        cp = self._cargar_mod(
            "recup_camino_principal_robot",
            os.path.join(aqui, "camino_principal_robot.py"),
        )
        cp.instalar(v2, dict(camino=True, mono=True))

        self._v4 = v4
        self._v2 = v2
        self._cp = cp
        self._SinBranch = SinBranch
        self._tr = SinBranch(self.fps)

    def reset(self):
        """Resetea memoria temporal al volver a entrar al modo linea."""
        self.ultimo_heading = None
        self.ultimo_t = 0.0
        self.ultimo_estado = "SIN_DATO"
        self.ultimo_target = None
        self.ultimo_resultado = None
        self._tr = self._SinBranch(self.fps)

    def paso(self, frame_resized):
        """Procesa UN frame 160x120 BGR ya rotado como el main de la Pi."""
        r = self._tr.step(frame_resized)
        self.ultimo_resultado = r

        estado = r.get("state")
        heading = r.get("heading")
        target = r.get("target")
        confiable = bool(
            r.get("ok")
            and estado in ("HIGH", "MEDIUM")
            and target is not None
            and heading is not None
            and math.isfinite(float(heading))
        )

        if confiable:
            self.ultimo_heading = float(heading)
            self.ultimo_t = time.monotonic()
            self.ultimo_estado = estado
            self.ultimo_target = target

        return dict(
            ok=bool(r.get("ok")),
            state=estado,
            heading_frame=None if heading is None else float(heading),
            target=target,
            confiable=confiable,
            ultimo_heading=self.ultimo_heading,
            ultimo_estado=self.ultimo_estado,
        )

    def ultimo(self, max_age_s=0.45):
        now = time.monotonic()
        if self.ultimo_heading is None or self.ultimo_t <= 0.0:
            return dict(vigente=False, heading=None, edad_s=None,
                        estado=self.ultimo_estado, target=self.ultimo_target)
        edad = now - self.ultimo_t
        return dict(
            vigente=edad <= float(max_age_s),
            heading=float(self.ultimo_heading),
            edad_s=float(edad),
            estado=self.ultimo_estado,
            target=self.ultimo_target,
        )
