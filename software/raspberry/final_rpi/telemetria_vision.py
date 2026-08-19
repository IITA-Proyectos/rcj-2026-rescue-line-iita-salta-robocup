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
]


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
