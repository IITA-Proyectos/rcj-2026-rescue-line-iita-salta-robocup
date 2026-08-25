"""
telemetria_vision.py — registro por frame del lado de la Raspberry.

PARA QUE: el CSV del Teensy dice QUE comando llego y que hicieron los motores.
Cuando el veredicto es "la vision nunca pidio el giro", ese CSV no puede decir
POR QUE: si la mascara quedo vacia, si el centroide se puso mudo en media curva,
o si el angulo degenerado fijo la busqueda para un lado. Esto lo completa.

COMO SE CRUZAN LOS DOS REGISTROS: la columna `i` de aca es el numero de frame
enviado (`frames_sent`), y el Teensy graba `rxf`, su contador de tramas COMPLETAS
recibidas. Son el mismo numero mientras no se pierda una trama, asi que sirve de
clave de union sin tocar el protocolo de 8 bytes. Si al final los totales no
coinciden, la diferencia es exactamente la cantidad de tramas perdidas: eso
tambien es un dato, no un problema.

REGLAS QUE NO SE ROMPEN:
  - NUNCA levanta una excepcion hacia el lazo de vision. Si algo falla, se apaga
    sola y el robot sigue. Un registro no puede voltear una corrida.
  - Escribe en memoria y vuelca cada tanto: nada de I/O sincronico por frame.
  - Apagada por defecto. Se enciende con la variable de entorno TLM_VISION, que
    ademas dice donde escribir:
        TLM_VISION=/home/iita/corrida1_vision.csv python Main.py
    Sin esa variable no hace absolutamente nada (ni siquiera abre el archivo),
    para que en competencia no quede grabando por olvido.
"""
import os
import time

CAMPOS = [
    "i",            # numero de frame enviado == `rxf` del Teensy (clave de union)
    "t_ms",         # time.monotonic() en ms desde que arranco el registro
    "proc_ms",      # cuanto tardo en procesarse ESTE frame
    "estado",       # 0=linea 1=rescate 2=evacuacion 3=esperando
    "black_sum",    # np.sum(black_mask): 255 por pixel negro dentro del ROI
    "valida",       # 1 si black_sum >= min_line_size (hay linea de verdad)
    "degenerado",   # 1 si la mascara quedo VACIA -> atan2(0,0)-90 = -90 espurio
    "xr",           # x_resultant x1000 (componente horizontal del centroide)
    "yr",           # y_resultant x1000
    "ang_crudo",    # el angulo que salio del atan2, ANTES de cualquier override
    "ang_env",      # el angulo que REALMENTE se mando por serie
    "vel_env",      # la velocidad que se mando
    "perdida",      # 1 si se entro en la rutina de linea perdida
    "dir_busq",     # last_line_search_dir (+1 / -1)
    "green",        # green_state enviado
    "silver",       # silver_line enviado
    "rojo_bandas",  # cuantas bandas rojas se contaron
    "fps",          # fps instantaneo x10
    # ---- LA CANDIDATA (vision_linea.ultimo()) -----------------------------
    # Se agregan AL FINAL a proposito: un CSV viejo sigue siendo legible y la
    # clave de union con el `rxf` del Teensy no se mueve.
    # Todos enteros, porque el volcado es str(int(...)). El factor de escala
    # va en el nombre y en el comentario, igual que xr/yr.
    # ---- LA CAMARA: el primer eslabon del retardo, el que faltaba ---------
    # Sin estos cuatro campos el retardo total no se puede ATRIBUIR: si el robot
    # reacciona tarde, no se distingue "la camara entrego un frame viejo" de "la
    # Pi tardo en procesar" o de "la Teensy tardo en ejecutar".
    "cam_seq",      # numero de frame que la camara entrego
    "cam_edad",     # ms x10 desde que ESE frame se capturo, al empezar a procesar
    "cam_rep",      # acumulado: veces que se proceso DOS veces el mismo frame
    "cam_salt",     # acumulado: frames que la camara entrego y el lazo no vio
    "ctrl_source",  # QUIEN mando este comando. Sin esto, un comando raro no
                    # se puede atribuir: `angle` es la misma variable para los
                    # tres controladores.
                    #   0 vision vieja (la nueva esta apagada)
                    #   1 vision nueva
                    #   2 la nueva no opino -> vieja
                    #   3 la nueva no opino y no hay linea -> busqueda
                    #   4 la nueva se apago sola por fallos -> vieja
    "vl_activa",    # 1 mientras la vision nueva sigue viva; 0 si se apago sola
    "vl_modo",      # 0 apagada  1 base  2 camino+mono  3 v1
    "vl_estado",    # 0 -  1 HIGH 2 MEDIUM 3 LOW 4 LOW_FORWARD 5 SIN_CERCA 6 PERDIDA
    "tg_x",         # target FINAL, x10   (etapa 5)
    "tg_y",
    "geo_x",        # etapa 3: salida de la percepcion V2, x10. OJO: NO es el
    "geo_y",        # geometrico crudo; ya trae el cap y la proyeccion LOW
                    # aplicados. Es `target_geometric` de V4, y el nombre
                    # enganaba: las etapas 1 y 2 son raw_x/y y cap_x/y, mas abajo
    "bra_x",        # etapa 4: despues del guard de rama, x10
    "bra_y",
    "salto_px",     # proposed_jump_px x10: cuanto QUERIA saltar el target
    "guard_sp",     # 0 -  1 ACCEPT 2 SPATIAL_LIMIT 3 REACQ_ACCEPT
                    # 4 REACQ_PENDING 5 NO_TARGET 6 NO_SKELETON
    "razon",        # modo del planificador: 0 desconocido  1 near  2 ahead
                    # 3 ahead_bridge  4 perdida  5 sin_componente  6 sin_path
    "razon_fl",     # bitmask de guards que ACTUARON: 1 continuidad, 2 low_proj
    "kappa",        # curvatura del camino visible x10
    "fvel",         # factor de velocidad anticipada x1000 (1000 = sin frenar)
    # ---- LA LEY DE STEER (ley_steer.py) -----------------------------------
    "ley",          # 0 la de siempre  1 stanley  2 stanley no pudo y cayo
    "e_pos",        # cross-track en el suelo x1000  (signo: + a la derecha)
    "psi",          # rumbo de la tangente del camino, grados x10
    "t_pos",        # termino de POSICION del comando, grados x10
    "t_psi",        # termino de RUMBO del comando, grados x10
    "ang_viejo",    # lo que la ley VIEJA habria mandado en este mismo frame,
                    # grados x10. Con esto el A/B de leyes se hace sobre la
                    # corrida real, sin correr el robot dos veces.
    # ---- las dos etapas que faltaban -------------------------------------
    # PROTOCOLO_SABADO.md las pide por nombre: "son las CINCO etapas, no
    # cuatro. Sin ellas un log no sirve para clasificar la falla".
    # La cadena completa queda:
    #    raw -> cap -> geo (== lowproj) -> bra -> tg
    "raw_x",        # etapa 1: salida cruda de path_target, x10
    "raw_y",
    "cap_x",        # etapa 2: despues del cap de continuidad, x10
    "cap_y",
]

_MODO = {"base": 1, "camino+mono": 2, "v1": 3}
_ESTADO = {"HIGH": 1, "MEDIUM": 2, "LOW": 3, "LOW_FORWARD": 4,
           "SIN_CERCA": 5, "PERDIDA": 6}
_GUARD = {"ACCEPT": 1, "SPATIAL_LIMIT": 2, "REACQ_ACCEPT": 3,
          "REACQ_PENDING": 4, "NO_TARGET": 5, "NO_SKELETON": 6}
# `reason` sale de `mode`, que NO es lo mismo que `state`: choose_component
# devuelve NEAR / AHEAD / AHEAD_BRIDGE / PERDIDA, y ademas hay dos razones sin
# sufijo `_path` cuando no llega a planificar. La primera version de esta tabla
# usaba los estados (HIGH/MEDIUM/LOW) y dejaba el 93 % de los frames en 0.
_RAZON = {"near": 1, "ahead": 2, "ahead_bridge": 3, "perdida": 4,
          "sin_componente": 5, "sin_path": 6}
_LEY = {"stanley": 1, "cae_a_vieja": 2}


def _e(v, escala=1):
    """A entero, tolerante a None y a NaN. Fuera de rango -> 0."""
    try:
        if v is None:
            return 0
        v = float(v) * escala
        if v != v or v in (float("inf"), float("-inf")):
            return 0
        return int(round(v))
    except Exception:
        return 0


def _punto(p, pref, d):
    d[pref + "_x"] = _e(None if p is None else p[0], 10)
    d[pref + "_y"] = _e(None if p is None else p[1], 10)


def campos_vision(u):
    """Traduce vision_linea.ultimo() a los campos enteros del CSV.

    NUNCA levanta. Un dict vacio -la vision apagada- devuelve todo en 0, que
    es exactamente lo que el CSV ya escribia antes de existir estos campos.
    """
    d = {}
    if not u:
        return d
    try:
        d["vl_activa"] = _e(u.get("vl_activa"))
        d["vl_modo"] = _MODO.get(u.get("modo"), 0)
        d["vl_estado"] = _ESTADO.get(u.get("estado"), 0)
        _punto(u.get("target"), "tg", d)
        _punto(u.get("geom"), "geo", d)
        _punto(u.get("branch"), "bra", d)
        _punto(u.get("raw"), "raw", d)
        _punto(u.get("cap"), "cap", d)
        d["salto_px"] = _e(u.get("salto"), 10)
        d["guard_sp"] = _GUARD.get(u.get("spatial"), 0)

        raz = (u.get("razon") or "")
        partes = raz.split("|")
        base = partes[0][:-5] if partes[0].endswith("_path") else partes[0]
        d["razon"] = _RAZON.get(base, 0)
        fl = 0
        if "continuidad" in partes:
            fl |= 1
        if "low_proj" in partes:
            fl |= 2
        d["razon_fl"] = fl

        d["kappa"] = _e(u.get("kappa"), 10)
        # sin default: si no se calculo el factor -la anticipacion esta
        # apagada- va 0, que significa "no se midio". Un 1000 ahi seria decir
        # "velocidad plena" cuando en realidad nadie la evaluo.
        d["fvel"] = _e(u.get("factor_vel"), 1000)
        d["ley"] = _LEY.get(u.get("ley"), 0)
        d["e_pos"] = _e(u.get("e_pos"), 1000)
        d["psi"] = _e(u.get("psi"), 10)
        d["t_pos"] = _e(u.get("t_pos"), 10)
        d["t_psi"] = _e(u.get("t_psi"), 10)
        d["ang_viejo"] = _e(u.get("ang_viejo"), 10)
    except Exception:
        pass                      # un registro roto no puede voltear el lazo
    return d


class TelemetriaVision:
    def __init__(self, ruta=None, cada=200, cada_s=1.0):
        self.activa = False
        self._buf = []
        self._cada = cada
        self._cada_s = cada_s
        self._ult_volcado = 0.0
        self._t0 = 0.0
        self._f = None
        self._errores = 0

        ruta = ruta or os.environ.get("TLM_VISION")
        if not ruta:
            return                      # apagada: todas las llamadas son no-op
        try:
            # 'x' a proposito: no pisar una corrida anterior sin avisar.
            modo = "x" if not os.environ.get("TLM_VISION_PISAR") else "w"
            self._f = open(ruta, modo, encoding="utf-8", newline="")
            self._f.write("# RescueBot IITA - telemetria de vision (Raspberry)\n")
            self._f.write("# la columna i se cruza con la columna rxf del CSV del Teensy\n")
            self._f.write(",".join(CAMPOS) + "\n")
            self._t0 = time.monotonic()
            self._ult_volcado = self._t0
            self.activa = True
            print("[TLM-VISION] grabando en %s" % ruta)
        except Exception as e:
            print("[TLM-VISION] no se pudo abrir (%s): sigo SIN registro" % e)
            self.activa = False

    def frame(self, **k):
        """Una linea. Recibe solo lo que se tenga; lo que falte va en 0."""
        if not self.activa:
            return
        try:
            ahora = time.monotonic()
            # `vision=vision_linea.ultimo()` se expande aca y no en el lazo,
            # asi el llamador agrega UNA linea y el objeto nulo la ignora
            # sin enterarse.
            u = k.pop("vision", None)
            if u:
                k.update(campos_vision(u))
            k.setdefault("t_ms", int((ahora - self._t0) * 1000))
            self._buf.append(",".join(str(int(k.get(c, 0))) for c in CAMPOS))
            if len(self._buf) >= self._cada or (ahora - self._ult_volcado) >= self._cada_s:
                self._volcar(ahora)
        except Exception:
            # Un registro roto NO puede voltear el lazo de vision. Se apaga sola.
            self._errores += 1
            if self._errores > 20:
                self.activa = False
                print("[TLM-VISION] demasiados errores: registro APAGADO")

    def _volcar(self, ahora=None):
        if not self._f or not self._buf:
            return
        try:
            self._f.write("\n".join(self._buf) + "\n")
            self._f.flush()
            self._buf = []
            self._ult_volcado = ahora if ahora is not None else time.monotonic()
        except Exception:
            self._errores += 1

    def cerrar(self):
        if not self.activa:
            return
        try:
            self._volcar()
            self._f.close()
            print("[TLM-VISION] cerrado")
        except Exception:
            pass
        self.activa = False


# Instancia unica: Main.py hace `from telemetria_vision import tlmv` y listo.
tlmv = TelemetriaVision()
