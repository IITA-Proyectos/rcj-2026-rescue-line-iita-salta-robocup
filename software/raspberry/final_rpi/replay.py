# -*- coding: utf-8 -*-
"""
replay.py - BANCO DE REPLAY DE VISION. Le da una corrida grabada a una ley de
            control y devuelve, frame a frame, el angulo que ESA ley habria
            mandado. Sirve para comparar el controlador de hoy contra un
            candidato SIN MOVER EL ROBOT.

============================================================================
 LO PRIMERO, PORQUE ES LO QUE MAS IMPORTA: QUE PUEDE Y QUE NO PUEDE VALIDAR
============================================================================

Esto es un replay de VISION, no una simulacion fisica. Las imagenes estan
grabadas con la trayectoria que el robot REALMENTE hizo ese dia. Si la ley
candidata hubiera girado antes, mas fuerte o para el otro lado, los frames
siguientes habrian sido OTROS. Es un LAZO ABIERTO: se corta la realimentacion
justo donde el problema vive.

PREGUNTAS QUE SI SE PUEDEN CONTESTAR ACA
----------------------------------------
  1. Sobre ESTAS imagenes, cuanto difiere el angulo de la ley candidata del de
     la ley que corrio. Frame a frame, con el signo y la magnitud.
  2. Cuantos frames la ley candidata declara "no veo la linea", y cuantos de
     esos coinciden con que la linea este realmente ausente del ROI de
     decision. O sea: la ley, COMO DETECTOR DE PERDIDA, se puede medir aca sin
     ninguna suposicion fisica, porque detectar es una funcion de la imagen.
  3. Si la ley candidata satura, si pica alrededor de un umbral, si cambia de
     signo entre frames consecutivos, cuanto dura cada pedido de giro sostenido
     y cuantos grados de comando pide - todo eso es funcion del angulo, y el
     angulo es funcion de la imagen.
  4. Si un cambio de ROI, de umbral de negro o de criterio de mancha cambia el
     angulo en los frames que importan, y en cuales.
  5. Si la reimplementacion del codigo que corrio es fiel: se compara contra el
     rxsteer del CSV de la unica corrida que tiene video Y telemetria.

PREGUNTAS QUE **NO** SE PUEDEN CONTESTAR ACA - NI CON MAS FRAMES NI CON MAS LEYES
--------------------------------------------------------------------------------
  1. Si el robot habria completado la curva. NO. Es la pregunta que el equipo
     quiere contestar y es exactamente la que este banco no contesta.
  2. Cuantos grados habria girado el robot. NO. Ver mas abajo "por que no hay
     grados logrados": esta medido, no es una precaucion retorica.
  3. Si la ley candidata pierde la linea MENOS VECES. NO. La cantidad de veces
     que se pierde la linea depende de por donde paso el robot, y por donde
     paso el robot depende de la ley. Lo unico medible es si la ley DETECTA la
     perdida que hay en el video grabado.
  4. Si una ley es mejor que otra "en las 4 metricas de analizar_corrida.py".
     NO, y esto es una trampa concreta: esas cuatro metricas se calculan sobre
     los pixeles del video y NO dependen del angulo. En replay dan IDENTICO
     para todas las leyes. Este programa las imprime UNA sola vez, como
     propiedad de la GRABACION, justamente para que nadie las lea como si
     compararan controladores. En el informe del 22-ago esas cuatro metricas si
     distinguian entre configuraciones - pero porque cada configuracion volaba
     una trayectoria distinta, con el robot andando. Eso aca no pasa.
  5. Nada sobre tiempos del lazo, latencia, rxage, ni sobre si la Teensy
     alcanzo a ejecutar la orden. El replay corre sobre frames, no sobre el
     reloj del robot.

POR QUE NO HAY "GRADOS LOGRADOS" (esta medido, no es prudencia)
---------------------------------------------------------------
Para pasar de "grados de comando" a "grados girados" haria falta una constante
de chasis. Se probo estimarla sobre la unica corrida con telemetria
(2026-08-22_pista_pivote_con_histeresis.csv), integrando gz por episodio de
pivote y dividiendo por (duracion x ls pedida):

    K por episodio en pivote (n=35):  mediana 0,911  p25 0,326  p75 1,024
    CONTROL, los mismos episodios FUERA del pivote (n=32):
                                      mediana 1,199  p25 0,411  p75 2,537

La banda es de factor 3 y NO se separa de su grupo de control. Ademas, en esa
misma corrida, la integral de gz contra el yaw desenrollado da r = -0,856 con
pendiente -0,785: ni el signo ni la escala cierran. Con eso, cualquier "grados
proyectados" que este archivo imprimiera tendria una barra de error de x3 y un
signo dudoso. No se imprime. Se imprimen los GRADOS PEDIDOS, que son exactos, y
la demanda acumulada en grado*segundo, que lleva su unidad escrita.

(El 1,15-1,29 (grados/s)/rpm del ANALISIS-2026-08-23 es otro estimador -mediana
de |gz| instantaneo sobre ls- y no contradice esto: mide velocidad tipica, no
grados netos por episodio. Los dos numeros son correctos y miden cosas
distintas.)

============================================================================
 DE DONDE SALEN LOS FRAMES, Y UN BUG DE MEDICION QUE HAY QUE CONOCER
============================================================================

Los AVI son de 640x240. El panel IZQUIERDO es el frame de 160x120 que el robot
proceso, escalado x2 con INTER_NEAREST. El panel DERECHO es la mascara de negro
YA recortada en la fila 60, tambien escalada x2.

EL BUG: `parche_planner.py:267` dibuja una linea AMARILLA horizontal sobre el
panel izquierdo, en la fila `corte*2` = 120 de la imagen de 240. Al recuperar el
frame con el muestreo PAR -`f[:, :320][::2, ::2]`, que es lo que hace
`analizar_corrida.py:92`- esa fila 120 cae justo en la fila 60 del frame de
120, que es la PRIMERA fila del ROI. Resultado: la fila 60 queda pintada de
amarillo y no aporta ni un pixel negro.

Medido sobre los 2091 frames de hist.avi, con filas de control:

    fila   par([::2,::2])   impar([1::2,1::2])   mascara real (panel derecho)
     58        18,0 px            18,0 px               0 px  (fuera del ROI)
     59        18,4              18,4                   0
     60         0,0              18,5                  17,3     <-- destruida
     61        18,8              18,8                  18,0
     70        23,5              23,5                  23,4
    100        42,8              42,8                  42,7
    119        57,5              57,5                  57,3

Y el efecto sobre la fidelidad del angulo reproducido (contra el CSV):

    muestreo par     coincidencia exacta 65,2 %
    muestreo impar   coincidencia exacta 84,0 %

Como el escalado es x2 con vecino mas cercano, las filas 2i y 2i+1 salen las dos
de la fila i del original: el muestreo IMPAR recupera el mismo frame y esquiva
la linea dibujada. Por eso el default de este archivo es `izq-impar`.

Esto afecta a `analizar_corrida.py`: su `medir()` usa filas 100.. y esta bien,
pero su `ganancia()` usa FILA_ROI=60 y esta midiendo con la fila 60 en cero.

============================================================================
 VALIDACION DE LA REIMPLEMENTACION (correr `python replay.py --validar`)
============================================================================

De 60 pares video x CSV posibles existe UNO:
    hist.avi  <->  2026-08-22_pista_pivote_con_histeresis.csv

Se engancha por `rxf` (contador de tramas completas de la Teensy). El desfasaje
que gana es 0 y el pico es limpio: en offset +-1 la coincidencia se cae de 84 %
a 29 %, asi que no hay ambiguedad de alineacion.

    fuente        exacto   <=1 gr   <=3 gr    r
    izq-impar      84,0 %   96,3 %   99,2 %   0,9957     <- default
    izq-par        65,2 %   91,7 %   97,8 %   0,9971
    mascara        92,5 %   95,5 %   97,5 %   0,9671

El listón que puso el analisis previo era 81,1 % y r=0,945. Se supera. Si al
correr `--validar` estos numeros bajan mucho, la reimplementacion se rompio y
NADA de lo que salga de este archivo sirve para comparar leyes.

Lo que queda sin reproducir (~16 % de los frames en izq-impar) es, casi todo,
compresion: los AVI son MJPEG con perdida y en los frames con la mancha de
negro muy chica (1-15 px en el ROI) un puñado de pixeles al borde del umbral 90
mueve el atan2 decenas de grados. De los 8 frames con error > 5 gr, 4 son
frames donde la reconstruccion se quedo con CERO pixeles y disparo la guarda de
linea perdida.

============================================================================
 USO
============================================================================

    python replay.py --validar
        Valida la reimplementacion contra el CSV. Correr esto PRIMERO, siempre.

    python replay.py hist.avi
        Corre todas las leyes registradas sobre el video e imprime la tabla.

    python replay.py hist.avi rumbo.avi --leyes 2026-08-22,perdida-explicita

    python replay.py hist.avi --firmware
        Ademas pasa el angulo por el modelo del `case 7` del firmware
        (main.cpp:3275+) para ver cuanto dura el pivote que cada ley pediria.

    python replay.py --lista
        Lista las leyes registradas.

Sin la Raspberry: solo hacen falta cv2 y numpy.

============================================================================
 COMO SE ENCHUFA UNA LEY NUEVA
============================================================================

    def mi_ley(v, mem):
        # v   : Vista  -> v.bgr (160x120x3), v.mascara(desde_fila), v.idx, v.t
        # mem : dict por corrida, para leyes con memoria (histeresis, filtros)
        return Decision(angulo=..., perdida=..., nota="")

    registrar("mi-ley", mi_ley, "una linea de que hace")

`angulo` va en grados, mismo convenio que el codigo de la Pi: 0 = derecho,
NEGATIVO = la linea esta a la derecha del centro. Se manda como `angle + 90`
(main_rpi_2026-08-22.py:145) y la Teensy hace `steer = (data-90)/90`
(main.cpp:1578).
"""

import argparse
import math
import os
import sys

import cv2
import numpy as np

# ---------------------------------------------------------------------------
#  CONSTANTES. Todas salen de codigo, no de documentacion.
# ---------------------------------------------------------------------------

# El AVI declara 20 fps porque `parche_planner.py:294` le pasa 20.0 fijo al
# VideoWriter. El fps REAL de la corrida es 33,3. Toda conversion frame->segundo
# de este archivo usa 33,3.
FPS = 100.0 / 3.0

ANCHO, ALTO = 160, 120
NEGRO_LO = np.array([0, 0, 0])            # main_rpi_2026-08-22.py:110-111
NEGRO_HI = np.array([90, 90, 90])
FILA_ROI = 60                             # main_rpi_2026-08-22.py:805
MIN_LINE_SIZE = 1                         # main_rpi_2026-08-22.py:99
CENTRO_PX = (ANCHO - 1) / 2.0             # 79,5
FILAS_CERCA = slice(100, 120)             # ROI de decision del analizador
PX_MIN_LINEA = 30                         # analizar_corrida.py:107

# Constantes del `case 7`, rama FIX_CURVA_CONTINUA (main.cpp:3282-3310).
FW_STEER_GAIN = 1.35
FW_ROT_EXP = 0.50
FW_PIVOTE_ENTRA = 0.60
FW_PIVOTE_SALE = 0.15
FW_PIVOTE_MAX_MS = 2500
FW_PIVOT_STEER = 0.92
FW_CURVE_STEER = 0.08
FW_HARD_CURVE_STEER = 0.35
FW_PIVOT_SPEED = 50
FW_VEL_BASE = 45                          # ajustarVelocidadPorPendiente(45) en llano

# Umbral por defecto para contar "pedido de giro": el angulo de camara que hace
# que el firmware entre en pivote. absSteer = |angulo/90 * 1,35| >= 0,60
# => |angulo| >= 40,0 grados. No es un numero elegido a mano.
UMBRAL_GIRO_GR = FW_PIVOTE_ENTRA / FW_STEER_GAIN * 90.0

RUTA_ESTE = os.path.dirname(os.path.abspath(__file__))
VIDEO_VALIDACION = os.path.join(RUTA_ESTE, "hist.avi")
CSV_VALIDACION = os.path.abspath(os.path.join(
    RUTA_ESTE, "..", "..", "teensy", "firmware", "corridas",
    "2026-08-22_pista_pivote_con_histeresis.csv"))


def _rejillas():
    """x_com / y_com, copiadas literal de main_rpi_2026-08-22.py:237-242.

    Se arman con el mismo doble for a proposito: es codigo que se compara
    contra el original a ojo, no codigo que tenga que ser rapido (corre una vez).
    """
    cam_x = ANCHO / 2 - 1          # 79,0  (OJO: no es 79,5)
    cam_y = ALTO - 1               # 119
    x = np.zeros(shape=(ALTO, ANCHO))
    y = np.zeros(shape=(ALTO, ANCHO))
    for i in range(ALTO):
        for j in range(ANCHO):
            x[i][j] = (j - cam_x) / (ANCHO / 2)
            y[i][j] = (cam_y - i) / ALTO
    return x, y


X_COM, Y_COM = _rejillas()
PESO_FILA = 1.0 - Y_COM            # el `x_black *= (1 - y_com)` del original


# ---------------------------------------------------------------------------
#  LO QUE UNA LEY VE, Y LO QUE UNA LEY DEVUELVE
# ---------------------------------------------------------------------------

class Decision(object):
    """Lo que una ley decide para un frame.

    angulo   grados. 0 = derecho. Negativo = linea a la DERECHA del centro
             (es el convenio del atan2 del codigo de la Pi, no una eleccion mia).
    perdida  la ley DECLARA que no ve la linea. Es la declaracion de la ley,
             no la verdad: el banco la compara despues contra la perdida real.
    nota     texto libre para depurar (que rama tomo la ley, por ejemplo).
    """
    __slots__ = ("angulo", "perdida", "nota")

    def __init__(self, angulo, perdida=False, nota=""):
        self.angulo = float(angulo)
        self.perdida = bool(perdida)
        self.nota = nota


class Vista(object):
    """Un frame, tal como lo vio el robot, mas las mascaras cacheadas.

    `bgr` es el frame de 160x120 reconstruido del video. `mascara(desde_fila)`
    devuelve la mascara de negro con las filas de arriba en cero, que es lo que
    hace el codigo de la Pi.

    Si la corrida se lee con fuente="mascara" (el panel derecho del AVI, que es
    la mascara que el robot calculo de verdad), `bgr` es None y la unica
    mascara disponible es la de la fila 60: pedirle otra es un error, no un
    valor aproximado.
    """
    __slots__ = ("idx", "t", "bgr", "_dada", "_cache")

    def __init__(self, idx, t, bgr, mascara_dada=None):
        self.idx = idx
        self.t = t
        self.bgr = bgr
        self._dada = mascara_dada
        self._cache = {}

    def mascara(self, desde_fila=FILA_ROI, umbral=90):
        clave = (desde_fila, umbral)
        m = self._cache.get(clave)
        if m is not None:
            return m
        if self._dada is not None:
            if desde_fila != FILA_ROI or umbral != 90:
                raise ValueError(
                    "con fuente='mascara' solo existe la mascara de la fila 60 "
                    "al umbral 90: el panel derecho del AVI ya viene recortado "
                    "(parche_planner.py:272-273). Para probar otro ROI u otro "
                    "umbral hay que leer con fuente='izq-impar'.")
            m = self._dada
        else:
            hi = np.array([umbral, umbral, umbral])
            m = cv2.inRange(self.bgr, NEGRO_LO, hi)
            if desde_fila > 0:
                m = m.copy()
                m[:desde_fila, :] = 0
        self._cache[clave] = m
        return m

    def mascara_cruda(self, umbral=90):
        """Mascara SIN recortar arriba. Con fuente='mascara' no existe."""
        if self._dada is not None:
            return self._dada
        hi = np.array([umbral, umbral, umbral])
        return cv2.inRange(self.bgr, NEGRO_LO, hi)


# ---------------------------------------------------------------------------
#  LECTURA DE LA CORRIDA
# ---------------------------------------------------------------------------

FUENTES = ("izq-impar", "izq-par", "mascara")


def leer_corrida(ruta, fuente="izq-impar"):
    """Generador de Vista. No carga el video entero en memoria.

    izq-impar   f[:, :320][1::2, 1::2]  <- DEFAULT. Mismo frame que el par pero
                sin la fila amarilla que el grabador dibuja en la fila 60.
    izq-par     f[:, :320][::2, ::2]    <- lo que hace analizar_corrida.py:92.
                Se deja para poder reproducir mediciones viejas.
    mascara     f[:, 320:][1::2, 1::2] binarizada. Es la mascara que el robot
                calculo de verdad, pero ya recortada en la fila 60.
    """
    if fuente not in FUENTES:
        raise ValueError("fuente desconocida: %s (hay %s)" % (fuente, ", ".join(FUENTES)))
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError("no se pudo abrir %s" % ruta)
    idx = 0
    try:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            ancho = f.shape[1]
            if fuente == "mascara":
                if ancho < 640:
                    raise IOError(
                        "%s no tiene panel de mascara (mide %d px de ancho). "
                        "Usar fuente='izq-impar'." % (os.path.basename(ruta), ancho))
                pan = f[:, 320:][1::2, 1::2]
                gris = cv2.cvtColor(pan, cv2.COLOR_BGR2GRAY)
                m = ((gris > 127).astype(np.uint8)) * 255
                m[:FILA_ROI, :] = 0
                yield Vista(idx, idx / FPS, None, mascara_dada=m)
            else:
                izq = f[:, :320] if ancho >= 640 else f
                bgr = izq[1::2, 1::2] if fuente == "izq-impar" else izq[::2, ::2]
                yield Vista(idx, idx / FPS, bgr)
            idx += 1
    finally:
        cap.release()


# ---------------------------------------------------------------------------
#  LEYES DE CONTROL
# ---------------------------------------------------------------------------

_LEYES = {}
_ORDEN = []


def registrar(nombre, funcion, doc):
    if nombre in _LEYES:
        raise ValueError("ya hay una ley llamada %s" % nombre)
    _LEYES[nombre] = (funcion, doc)
    _ORDEN.append(nombre)


def _atan2_original(m):
    """El calculo exacto de main_rpi_2026-08-22.py:806-828, sin la guarda.

    x_black = x_com enmascarado, multiplicado despues por (1 - y_com), o sea
    pesado hacia las filas de ABAJO. y_black = y_com enmascarado. Los promedios
    van sobre la imagen ENTERA de 120x160, no sobre el ROI: las filas de arriba
    entran como ceros y bajan las dos medias por igual, asi que el atan2 no
    cambia... salvo que x_resultant sea negativo, donde si importa el signo.
    Se reproduce tal cual para no introducir diferencias.
    """
    xb = cv2.bitwise_and(X_COM, X_COM, mask=m)
    xb = xb * PESO_FILA
    yb = cv2.bitwise_and(Y_COM, Y_COM, mask=m)
    xr = np.mean(xb)
    yr = np.mean(yb)
    return (math.atan2(yr, xr) / math.pi * 180.0) - 90.0


def ley_2026_08_22(v, mem):
    """LA QUE CORRIO EL 22-AGO. Es la referencia; no tocar.

    atan2 del centroide pesado sobre el ROI filas 60..119, y la guarda
    `np.sum(black_mask) < min_line_size` con min_line_size = 1. Sobre una
    mascara de 0/255 eso significa CERO pixeles negros en todo el ROI: por eso
    la guarda casi nunca se dispara.
    """
    m = v.mascara(FILA_ROI)
    a = _atan2_original(m)
    perdida = bool(np.sum(m) < MIN_LINE_SIZE)
    if perdida:
        a = 0.0
    return Decision(a, perdida, "atan2")


def ley_perdida_explicita(v, mem):
    """MISMO ANGULO que la que corrio, pero declara la perdida en serio.

    Unico cambio: en vez de exigir cero pixeles en todo el ROI, pide que la
    mancha de negro que TOCA EL BORDE DE ABAJO tenga al menos 30 px. Es la
    unica ley del set que separa "no veo nada" de "veo el zocalo".

    Sirve para medir de a un cambio: como el angulo es identico al de la ley de
    referencia, cualquier diferencia en la tabla es 100 % atribuible al
    detector de perdida.
    """
    m = v.mascara(FILA_ROI)
    a = _atan2_original(m)
    perdida = _mancha_de_abajo(m) < PX_MIN_LINEA
    if perdida:
        a = 0.0
    return Decision(a, perdida, "atan2+perdida")


def ley_lineal(v, mem):
    """Control proporcional plano sobre el centroide de las filas 100..119.

    Existe como contraste: el atan2 tiene la ganancia INVERTIDA (mucha cerca
    del centro, poca lejos) y este no. K=70 es el valor que se probo en pista
    el 22-ago (`seguir.avi`), asi que el numero no es inventado.
    """
    K = mem.get("K", 70.0)
    m = v.mascara_cruda()[FILAS_CERCA, :]
    cols = np.nonzero(m)[1]
    if cols.size < PX_MIN_LINEA:
        return Decision(0.0, True, "sin linea")
    err = (float(cols.mean()) - CENTRO_PX) / (ANCHO / 2.0)
    a = max(-90.0, min(90.0, -K * err))
    return Decision(a, False, "lineal")


registrar("2026-08-22", ley_2026_08_22,
          "la que corrio el 22-ago: atan2 + guarda min_line_size=1 (REFERENCIA)")
registrar("perdida-explicita", ley_perdida_explicita,
          "identica en angulo, pero declara perdida con mancha conexa < 30 px")
registrar("lineal-70", ley_lineal,
          "proporcional plano K=70 sobre el centroide de las filas 100..119")


# ---------------------------------------------------------------------------
#  QUE ES "PERDER LA LINEA DE VERDAD". Dos definiciones, las dos se reportan.
# ---------------------------------------------------------------------------

def _mancha_de_abajo(m):
    """Area de la mayor componente conexa del ROI que toca la fila 119.

    Es la definicion "conexa" que pedia OVERNIGHT_ANALYSIS: la cinta que el
    robot puede seguir es la que le llega abajo, no una mancha suelta en el
    medio del cuadro.
    """
    n, etq, stats, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
    if n <= 1:
        return 0
    ultima = etq[ALTO - 1, :]
    vivas = np.unique(ultima[ultima > 0])
    if vivas.size == 0:
        return 0
    return int(stats[vivas, cv2.CC_STAT_AREA].max())


def perdida_real(v):
    """Devuelve (roi_bajo, conexa, error_lateral_px).

    roi_bajo  <30 px negros en las filas 100..119. Es la definicion de
              analizar_corrida.py:107, la que produjo el 20,9 % del analisis
              de anoche. Se mantiene para poder comparar.
    conexa    la mancha que toca la fila 119 tiene <30 px. Mas exigente con el
              mobiliario suelto.
    lateral   columna media de los pixeles negros de las filas 100..119 menos
              79,5. NaN si roi_bajo.

    Las DOS se reportan a proposito: si un hallazgo cambia de signo segun cual
    se use, el hallazgo es de la definicion y no del robot.
    """
    cerca = v.mascara_cruda()[FILAS_CERCA, :]
    npx = int((cerca > 0).sum())
    if npx < PX_MIN_LINEA:
        lat = float("nan")
        bajo = True
    else:
        lat = float(np.nonzero(cerca)[1].mean()) - CENTRO_PX
        bajo = False
    conexa = _mancha_de_abajo(v.mascara(FILA_ROI)) < PX_MIN_LINEA
    return bajo, conexa, lat


# ---------------------------------------------------------------------------
#  MODELO DEL `case 7` DEL FIRMWARE (opcional)
# ---------------------------------------------------------------------------

class ModeloCase7(object):
    """Replica la maquina de estados del `case 7` (main.cpp:3320-3460).

    Es una funcion PURA del angulo y del tiempo: el enganche del pivote, la
    histeresis y la rampa de rotation no dependen de la fisica. Por eso se puede
    replayear sin el robot.

    VALIDADO contra 2026-08-22_pista_pivote_con_histeresis.csv alimentandolo con
    el rxsteer REAL del CSV (control que aisla el modelo de la vision), tomando
    la ULTIMA muestra de cada rxf -que es la que ya vio la orden nueva-:

        CONFIRMA_MS = 0     |rot| a menos de 0,05 en 92,9 % de 960 frames,
                            rama del case 7 igual en 94,1 %
        CONFIRMA_MS = 300   66,4 % y 94,1 %

    O sea: esa corrida NO tenia activo LINE_PIVOTE_CONFIRMA_MS. Por eso el
    default de este modelo es 0 y no los 300 que hoy estan en main.cpp:3303.

    LO QUE ESTE MODELO NO DICE: cuanto giro el robot. Da rot, vel y ls, que son
    CONSIGNAS. Ver arriba por que no se convierten a grados.
    """

    def __init__(self, confirma_ms=0, vel_base=FW_VEL_BASE):
        self.confirma_ms = confirma_ms
        self.vel_base = vel_base
        self.en_pivote = False
        self._t = 0.0
        self._t0 = 0.0
        self._alineado = None

    def paso(self, angulo_gr, dt_s):
        """Un paso del case 7. `angulo_gr` es el angulo YA redondeado que se
        manda por serial (la Teensy nunca ve el float)."""
        ms = self._t * 1000.0
        steer = angulo_gr / 90.0
        sc = max(-1.0, min(1.0, steer * FW_STEER_GAIN))
        ab = abs(sc)

        if not self.en_pivote and ab >= FW_PIVOTE_ENTRA:
            self.en_pivote = True
            self._t0 = ms
            self._alineado = None
        elif self.en_pivote:
            if ab > FW_PIVOTE_SALE:
                self._alineado = None
            elif self._alineado is None:
                self._alineado = ms
            sostenido = (self._alineado is not None and
                         ms - self._alineado >= self.confirma_ms)
            if sostenido or ms - self._t0 > FW_PIVOTE_MAX_MS:
                self.en_pivote = False
                self._alineado = None

        rot = 1.0 if self.en_pivote else math.pow(ab, FW_ROT_EXP)
        if ab >= FW_PIVOT_STEER:
            rot = 1.0
        rot = min(rot, 1.0)
        k = max(0.0, min(1.0, ab / FW_PIVOT_STEER))
        vel = int(self.vel_base + k * k * (FW_PIVOT_SPEED - self.vel_base))
        rama = (3 if ab > FW_PIVOT_STEER else
                2 if ab > FW_HARD_CURVE_STEER else
                1 if ab > FW_CURVE_STEER else 0)
        # DriveBase::steer(drivebase.cpp:205): el lado interno se invierte si la
        # consigna sale negativa; lo que se registra en el CSV es la MAGNITUD.
        base = vel
        otro = abs(vel - 2.0 * rot * vel)
        ls, rs = (otro, base) if sc > 0 else (base, otro)
        self._t += dt_s
        return {"rot": rot if sc > 0 else -rot, "vel": vel, "ls": ls, "rs": rs,
                "rama": rama, "en_pivote": self.en_pivote}


# ---------------------------------------------------------------------------
#  METRICAS
# ---------------------------------------------------------------------------

def metricas_grabacion(lat, n_frames, perdidos_bajo, perdidos_conexa, fps=FPS):
    """LAS 4 DE analizar_corrida.py, A 33,3 FPS.

    ATENCION: NO DEPENDEN DE LA LEY. Se calculan sobre los pixeles del video.
    En un replay son identicas para todas las leyes. Se imprimen una sola vez,
    como propiedad de la GRABACION.
    """
    lat = np.asarray(lat, dtype=float)
    buenos = lat[~np.isnan(lat)]
    if buenos.size < 50:
        return None
    signos = np.sign(buenos)
    cruces = int((np.diff(signos) != 0).sum())
    return {
        "frames": n_frames,
        "seg": n_frames / fps,
        "cruces": cruces / (buenos.size / fps),
        "centrado": 100.0 * float(np.mean(np.abs(buenos) < 10)),
        "desvio": float(np.mean(np.abs(buenos))),
        "perdida": 100.0 * perdidos_bajo / n_frames,
        "perdida_conexa": 100.0 * perdidos_conexa / n_frames,
    }


def episodios_de_giro(angulos, umbral_gr, fps=FPS):
    """Tramos consecutivos con |angulo| >= umbral. Lo que se pide, no lo que se logra.

    Por episodio:
        dur_s        duracion, a 33,3 fps
        pico_gr      |angulo| maximo pedido
        medio_gr     |angulo| medio pedido
        demanda      integral de |angulo| dt, en GRADO*SEGUNDO (lleva la unidad
                     escrita porque no es un angulo: es una demanda acumulada)
        signo        +1 / -1 segun el lado
    """
    a = np.asarray(angulos, dtype=float)
    dentro = np.abs(a) >= umbral_gr
    eps = []
    ini = None
    for i, v in enumerate(dentro):
        if v and ini is None:
            ini = i
        elif not v and ini is not None:
            eps.append((ini, i))
            ini = None
    if ini is not None:
        eps.append((ini, len(dentro)))
    out = []
    dt = 1.0 / fps
    for i0, i1 in eps:
        tr = np.abs(a[i0:i1])
        out.append({
            "i0": i0, "i1": i1,
            "dur_s": (i1 - i0) * dt,
            "pico_gr": float(tr.max()),
            "medio_gr": float(tr.mean()),
            "demanda_gr_s": float(tr.sum() * dt),
            "signo": 1 if a[i0:i1].mean() > 0 else -1,
        })
    return out


def metricas_ley(angulos, perdidas, reales_bajo, reales_conexa, fps=FPS,
                 umbral_gr=UMBRAL_GIRO_GR, modelo=None):
    """Todo lo que SI depende de la ley."""
    a = np.asarray(angulos, dtype=float)
    n = a.size
    seg = n / fps
    dec = np.asarray(perdidas, dtype=bool)
    rb = np.asarray(reales_bajo, dtype=bool)
    rc = np.asarray(reales_conexa, dtype=bool)

    eps = episodios_de_giro(a, umbral_gr, fps)
    dur = np.array([e["dur_s"] for e in eps]) if eps else np.array([])
    pico = np.array([e["pico_gr"] for e in eps]) if eps else np.array([])
    dem = np.array([e["demanda_gr_s"] for e in eps]) if eps else np.array([])

    # picoteo: episodios que vuelven a entrar con el MISMO signo en < 300 ms
    reentradas = 0
    for x, y in zip(eps, eps[1:]):
        if x["signo"] == y["signo"] and (y["i0"] - x["i1"]) / fps < 0.300:
            reentradas += 1

    r = {
        "n": n, "seg": seg,
        "ang_abs_med": float(np.median(np.abs(a))),
        "ang_p95": float(np.percentile(np.abs(a), 95)),
        "salto_med": float(np.median(np.abs(np.diff(a)))) if n > 1 else 0.0,
        "cambios_signo_s": float((np.diff(np.sign(a)) != 0).sum()) / seg,
        "frac_sobre_umbral": 100.0 * float(np.mean(np.abs(a) >= umbral_gr)),
        "eps_n": len(eps),
        "eps_por_s": len(eps) / seg,
        "eps_dur_med": float(np.median(dur)) if dur.size else float("nan"),
        "eps_dur_p90": float(np.percentile(dur, 90)) if dur.size else float("nan"),
        "eps_pico_med": float(np.median(pico)) if pico.size else float("nan"),
        "eps_dem_med": float(np.median(dem)) if dem.size else float("nan"),
        "eps_largos": int((dur >= 0.5).sum()) if dur.size else 0,
        "reentradas": reentradas,
        # detector de perdida
        "det": 100.0 * float(dec.mean()),
        "real_bajo": 100.0 * float(rb.mean()),
        "real_conexa": 100.0 * float(rc.mean()),
        "vp_bajo": 100.0 * float((dec & rb).mean()),
        "fn_bajo": 100.0 * float((~dec & rb).mean()),
        "fp_bajo": 100.0 * float((dec & ~rb).mean()),
        "vp_conexa": 100.0 * float((dec & rc).mean()),
        "fn_conexa": 100.0 * float((~dec & rc).mean()),
        "fp_conexa": 100.0 * float((dec & ~rc).mean()),
        "recall_bajo": (100.0 * float((dec & rb).sum()) / max(int(rb.sum()), 1)),
        "recall_conexa": (100.0 * float((dec & rc).sum()) / max(int(rc.sum()), 1)),
    }

    if modelo is not None:
        piv = np.asarray(modelo["en_pivote"], dtype=bool)
        cortes = []
        ini = None
        for i, v in enumerate(piv):
            if v and ini is None:
                ini = i
            elif not v and ini is not None:
                cortes.append((i - ini) / fps)
                ini = None
        if ini is not None:
            cortes.append((len(piv) - ini) / fps)
        r["fw_frac_pivote"] = 100.0 * float(piv.mean())
        r["fw_pivotes"] = len(cortes)
        r["fw_pivotes_s"] = len(cortes) / seg
        r["fw_pivote_dur_med"] = float(np.median(cortes)) if cortes else float("nan")
        r["fw_pivote_dur_p90"] = float(np.percentile(cortes, 90)) if cortes else float("nan")
        r["fw_rot_abs_med"] = float(np.median(np.abs(modelo["rot"])))
    return r


# ---------------------------------------------------------------------------
#  CORRER UNA LEY SOBRE UNA CORRIDA
# ---------------------------------------------------------------------------

def correr(ruta, nombres_ley, fuente="izq-impar", fps=FPS, con_firmware=False,
           confirma_ms=0, umbral_gr=UMBRAL_GIRO_GR, mem_por_ley=None):
    """Una sola pasada por el video, todas las leyes a la vez.

    Devuelve (grabacion, {nombre: (angulos, perdidas, metricas)}).
    """
    leyes = []
    for nom in nombres_ley:
        if nom not in _LEYES:
            raise ValueError("ley desconocida: %s" % nom)
        mem = dict((mem_por_ley or {}).get(nom, {}))
        leyes.append((nom, _LEYES[nom][0], mem, [], []))

    lat, rb, rc = [], [], []
    n = 0
    for v in leer_corrida(ruta, fuente):
        n += 1
        if fuente == "mascara":
            # sin panel izquierdo no hay mascara cruda: el ROI de decision
            # (filas 100..119) igual esta dentro de la mascara recortada.
            cerca = v.mascara(FILA_ROI)[FILAS_CERCA, :]
            npx = int((cerca > 0).sum())
            bajo = npx < PX_MIN_LINEA
            l = float("nan") if bajo else float(np.nonzero(cerca)[1].mean()) - CENTRO_PX
            conexa = _mancha_de_abajo(v.mascara(FILA_ROI)) < PX_MIN_LINEA
        else:
            bajo, conexa, l = perdida_real(v)
        lat.append(l)
        rb.append(bajo)
        rc.append(conexa)
        for nom, f, mem, angs, perds in leyes:
            d = f(v, mem)
            angs.append(d.angulo)
            perds.append(d.perdida)

    if n == 0:
        raise IOError("%s no tiene frames" % ruta)

    grab = metricas_grabacion(lat, n, sum(rb), sum(rc), fps)
    salida = {}
    for nom, _f, _mem, angs, perds in leyes:
        modelo = None
        if con_firmware:
            fw = ModeloCase7(confirma_ms=confirma_ms)
            acc = {"rot": [], "en_pivote": [], "ls": [], "rama": []}
            dt = 1.0 / fps
            for a in angs:
                s = fw.paso(float(round(a)), dt)
                acc["rot"].append(s["rot"])
                acc["en_pivote"].append(s["en_pivote"])
                acc["ls"].append(s["ls"])
                acc["rama"].append(s["rama"])
            modelo = acc
        m = metricas_ley(angs, perds, rb, rc, fps, umbral_gr, modelo)
        salida[nom] = (angs, perds, m)
    return grab, salida, (lat, rb, rc)


# ---------------------------------------------------------------------------
#  VALIDACION CONTRA EL CSV
# ---------------------------------------------------------------------------

def leer_csv(ruta):
    """Filas de 45 campos exactos. Todo lo demas se tira.

    La linea 1 es la nota y la cabecera puede faltar o venir cortada porque el
    drenaje arranca a mitad de linea. La fuente de verdad del orden de columnas
    es DIAG_CABECERA en main.cpp:798.
    """
    filas = []
    with open(ruta, "r", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\n").split(",")
            if len(p) != 45:
                continue
            try:
                filas.append([int(x) for x in p])
            except ValueError:
                continue
    filas.sort(key=lambda r: r[0])
    return filas


def rxsteer_por_trama(filas, cual="primera"):
    """rxsteer indexado por rxf.

    'primera' es lo correcto para el ANGULO: rxsteer se escribe cuando llega el
    byte de angulo (main.cpp:1578) y rxf recien se incrementa con el byte de
    silver (main.cpp:1594), asi que la primera muestra con rxf=N ya tiene el
    angulo N y todavia no el N+1. Medido: 'primera' da 84,0 % de coincidencia
    exacta y 'ultima' 82,0 %.

    'ultima' es lo correcto para la RESPUESTA del firmware (rot, ls, rama):
    esas necesitan que el lazo haya corrido al menos una vez con la orden nueva.
    Medido con el modelo del case 7: 'ultima' 92,9 % y 'primera' 82,4 %.
    """
    d = {}
    for r in filas:
        rxf = r[6]
        if cual == "primera":
            if rxf not in d:
                d[rxf] = r
        else:
            d[rxf] = r
    return d


def _byte_a_rxsteer(angulo_gr):
    """El viaje completo del angulo: round -> +90 -> clamp -> (data-90)/90 -> x1000.

    main_rpi_2026-08-22.py:145 y main.cpp:1578,614.
    """
    a = int(round(angulo_gr))
    b = max(0, min(255, a + 90))
    return int(((b - 90) / 90.0) * 1000.0)      # (int16_t) trunca hacia cero


def validar(video=VIDEO_VALIDACION, csv=CSV_VALIDACION, ley="2026-08-22",
            fuentes=FUENTES, con_firmware=True):
    """Reproduce el rxsteer del CSV y reporta cuanto se parece.

    El offset video->rxf se busca por barrido y se imprime el pico junto con sus
    vecinos: si el pico no es agudo, el enganche no es confiable y ningun numero
    de este archivo vale.
    """
    if not os.path.exists(video):
        print("  no esta el video de validacion: %s" % video)
        return 2
    if not os.path.exists(csv):
        print("  no esta el CSV de validacion: %s" % csv)
        return 2

    filas = leer_csv(csv)
    prim = rxsteer_por_trama(filas, "primera")
    ult = rxsteer_por_trama(filas, "ultima")
    print("  CSV: %d filas de 45 campos, rxf %d..%d" %
          (len(filas), min(prim), max(prim)))

    print("")
    print("  " + "-" * 74)
    print("  VALIDACION DEL ANGULO   ley '%s'   video %s" % (ley, os.path.basename(video)))
    print("  " + "-" * 74)
    print("  fuente       off     n   exacto    <=1 gr   <=3 gr      r")
    mejor = None
    for fuente in fuentes:
        try:
            _g, sal, _e = correr(video, [ley], fuente=fuente)
        except (IOError, ValueError) as e:
            print("  %-12s  ---  no se pudo: %s" % (fuente, e))
            continue
        ang = np.asarray(sal[ley][0], dtype=float)

        def puntaje(off):
            rx = np.array([prim[k + off][3] if (k + off) in prim else np.nan
                           for k in range(ang.size)], dtype=float)
            ok = ~np.isnan(rx)
            if ok.sum() < 300:
                return None
            ac = np.round(rx[ok] * 0.09)
            ap = np.round(ang[ok])
            dif = np.abs(ac - ap)
            return (float(np.mean(dif == 0)), float(np.mean(dif <= 1)),
                    float(np.mean(dif <= 3)),
                    float(np.corrcoef(ac, ap)[0, 1]), int(ok.sum()))

        rango = range(-40, max(prim) + 2)
        cand = [(o, puntaje(o)) for o in rango]
        cand = [(o, p) for o, p in cand if p is not None]
        if not cand:
            print("  %-12s  ---  sin solape suficiente entre video y CSV" % fuente)
            continue
        off, p = max(cand, key=lambda t: t[1][0])
        print("  %-12s %+4d %5d   %5.1f %%   %5.1f %%   %5.1f %%   %.4f"
              % (fuente, off, p[4], 100 * p[0], 100 * p[1], 100 * p[2], p[3]))
        if mejor is None or p[0] > mejor[2][0]:
            mejor = (fuente, off, p, ang)
        if fuente == fuentes[0]:
            vec = [(o, puntaje(o)) for o in (off - 2, off - 1, off, off + 1, off + 2)]
            print("       pico de alineacion: " + "  ".join(
                "%+d:%.0f%%" % (o, 100 * q[0]) for o, q in vec if q is not None))

    if mejor is None:
        print("\n  NO SE PUDO VALIDAR. No usar este replay para comparar leyes.")
        return 1

    fuente, off, p, ang = mejor
    print("")
    print("  Referencia del analisis previo: 81,1 %% exacto y r = 0,945.")
    if p[0] >= 0.80 and p[3] >= 0.94:
        print("  VALIDA: %.1f %% exacto y r = %.3f con fuente '%s'." % (100 * p[0], p[3], fuente))
    else:
        print("  *** NO VALIDA: %.1f %% exacto y r = %.3f. La reimplementacion esta mal."
              % (100 * p[0], p[3]))
        print("  *** No comparar leyes con este banco hasta arreglarlo.")
        return 1

    if con_firmware:
        print("")
        print("  " + "-" * 74)
        print("  VALIDACION DEL MODELO DEL case 7")
        print("  (control: se lo alimenta con el rxsteer REAL del CSV, no con el")
        print("   angulo reproducido, para separar el firmware de la vision)")
        print("  " + "-" * 74)
        ks = sorted(k for k in prim if k < ang.size)
        seq = [prim[k][3] * 0.09 for k in ks]
        print("  confirma_ms   n    |rot| a <=0,05   rama igual")
        for cms in (0, 300):
            fw = ModeloCase7(confirma_ms=cms)
            dr, dram = [], []
            dt = 1.0 / FPS
            for i, k in enumerate(ks):
                s = fw.paso(float(round(seq[i])), dt)
                r = ult[k]
                dr.append(abs(r[7] / 1000.0 - s["rot"]))
                dram.append(r[11] == s["rama"])
            print("      %4d     %4d       %5.1f %%        %5.1f %%"
                  % (cms, len(dr), 100 * float(np.mean(np.array(dr) <= 0.05)),
                     100 * float(np.mean(dram))))
        print("  Con confirma_ms=0 el modelo cierra; con 300 no. Esa corrida NO")
        print("  tenia activo LINE_PIVOTE_CONFIRMA_MS (main.cpp:3303).")
    return 0


# ---------------------------------------------------------------------------
#  INFORME
# ---------------------------------------------------------------------------

def informe(ruta, grab, sal, umbral_gr, con_firmware):
    print("")
    print("=" * 78)
    print("  %s" % os.path.basename(ruta))
    print("=" * 78)
    if grab is None:
        print("  pocos frames utiles")
        return
    print("  PROPIEDADES DE LA GRABACION - iguales para TODAS las leyes.")
    print("  (son las 4 de analizar_corrida.py, a 33,3 fps. NO dependen del")
    print("   angulo: se calculan sobre los pixeles. En replay no comparan")
    print("   controladores. Estan aca para ubicar la corrida, nada mas.)")
    print("     frames %d   %.1f s   cruces/s %.2f   centrado %.0f %%   desvio %.1f px"
          % (grab["frames"], grab["seg"], grab["cruces"], grab["centrado"], grab["desvio"]))
    print("     linea perdida: %.1f %% (filas 100..119 <30 px)   %.1f %% (mancha conexa que toca el borde)"
          % (grab["perdida"], grab["perdida_conexa"]))

    print("")
    print("  LO QUE SI DEPENDE DE LA LEY")
    print("  " + "-" * 74)
    print("  ley                  |ang| med  p95   salto  signo/s  >=%.0fgr" % umbral_gr)
    for nom, (_a, _p, m) in sal.items():
        print("  %-20s %6.1f  %6.1f  %5.1f   %5.2f    %5.1f %%"
              % (nom[:20], m["ang_abs_med"], m["ang_p95"], m["salto_med"],
                 m["cambios_signo_s"], m["frac_sobre_umbral"]))

    print("")
    print("  PEDIDO DE GIRO   (episodio = tramo con |angulo| >= %.0f gr, que es el" % umbral_gr)
    print("   angulo que hace entrar al pivote: |ang|/90*1,35 >= 0,60)")
    print("  ley                    n   ep/s   dur med  dur p90  pico med  demanda med   >=0,5s  re-entradas")
    for nom, (_a, _p, m) in sal.items():
        print("  %-20s %4d  %5.2f   %6.3f s %6.3f s  %6.1f gr  %6.2f gr*s   %4d    %4d"
              % (nom[:20], m["eps_n"], m["eps_por_s"], m["eps_dur_med"], m["eps_dur_p90"],
                 m["eps_pico_med"], m["eps_dem_med"], m["eps_largos"], m["reentradas"]))
    print("  ('demanda' es la integral de |angulo| dt: la unidad es GRADO*SEGUNDO,")
    print("   no grados. Grados girados no se pueden calcular aca - ver el docstring.)")

    print("")
    print("  DETECTOR DE LINEA PERDIDA   (esto SI se puede medir en replay:")
    print("   detectar es funcion de la imagen, no de la trayectoria)")
    print("  ley                  declara   real bajo  recall   FP     real conexa  recall   FP")
    for nom, (_a, _p, m) in sal.items():
        print("  %-20s %6.2f %%  %6.2f %%  %5.1f %% %5.2f %%   %6.2f %%  %5.1f %% %5.2f %%"
              % (nom[:20], m["det"], m["real_bajo"], m["recall_bajo"], m["fp_bajo"],
                 m["real_conexa"], m["recall_conexa"], m["fp_conexa"]))
    print("  (recall = de los frames en que la linea REALMENTE no esta, en que")
    print("   fraccion la ley lo declara. FP = frames en que la ley declara")
    print("   perdida y la linea estaba. Las dos definiciones de 'realmente' se")
    print("   reportan juntas a proposito.)")

    if con_firmware:
        print("")
        print("  MODELO DEL case 7 SOBRE EL ANGULO DE CADA LEY (lazo abierto)")
        print("  ley                  %pivote  pivotes  piv/s  dur med  dur p90  |rot| med")
        for nom, (_a, _p, m) in sal.items():
            if "fw_frac_pivote" not in m:
                continue
            print("  %-20s %6.1f %%   %5d  %5.2f  %6.3f s %6.3f s   %5.3f"
                  % (nom[:20], m["fw_frac_pivote"], m["fw_pivotes"], m["fw_pivotes_s"],
                     m["fw_pivote_dur_med"], m["fw_pivote_dur_p90"], m["fw_rot_abs_med"]))
        print("  OJO: es el pivote que el firmware pediria SI las imagenes fueran")
        print("  estas. Con otra ley el robot habria pasado por otro lado y habria")
        print("  visto otra cosa. No leer esto como 'la curva se completa'.")


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Banco de replay de VISION. Leer el docstring del archivo antes de usarlo.",
        add_help=True)
    ap.add_argument("videos", nargs="*", help="AVI de corridas")
    ap.add_argument("--validar", action="store_true",
                    help="valida la reimplementacion contra el CSV y sale")
    ap.add_argument("--lista", action="store_true", help="lista las leyes registradas")
    ap.add_argument("--leyes", default=",".join(_ORDEN),
                    help="leyes a correr, separadas por coma")
    ap.add_argument("--fuente", default="izq-impar", choices=list(FUENTES),
                    help="de donde salen los pixeles (default izq-impar; ver docstring)")
    ap.add_argument("--fps", type=float, default=FPS,
                    help="fps REAL de la grabacion (default 33,3; el AVI miente y dice 20)")
    ap.add_argument("--umbral-giro", type=float, default=UMBRAL_GIRO_GR,
                    help="grados a partir de los cuales cuenta como pedido de giro")
    ap.add_argument("--firmware", action="store_true",
                    help="ademas pasa el angulo por el modelo del case 7")
    ap.add_argument("--confirma-ms", type=int, default=0,
                    help="LINE_PIVOTE_CONFIRMA_MS del modelo (default 0: es lo que valida)")
    a = ap.parse_args(argv)

    if a.lista:
        print("  leyes registradas:")
        for n in _ORDEN:
            print("    %-20s %s" % (n, _LEYES[n][1]))
        return 0

    if a.validar:
        return validar()

    if not a.videos:
        print(__doc__)
        return 2

    nombres = [x.strip() for x in a.leyes.split(",") if x.strip()]
    print("")
    print("  ADVERTENCIA PERMANENTE: esto es un replay de VISION en LAZO ABIERTO.")
    print("  Compara que ANGULO habria mandado cada ley sobre las MISMAS imagenes.")
    print("  NO dice si el robot habria completado la curva. Si una ley hubiera")
    print("  girado antes, los frames siguientes habrian sido otros.")
    for ruta in a.videos:
        try:
            grab, sal, _ = correr(ruta, nombres, fuente=a.fuente, fps=a.fps,
                                  con_firmware=a.firmware, confirma_ms=a.confirma_ms,
                                  umbral_gr=a.umbral_giro)
        except (IOError, ValueError) as e:
            print("\n  %s: %s" % (os.path.basename(ruta), e))
            continue
        informe(ruta, grab, sal, a.umbral_giro, a.firmware)
    return 0


if __name__ == "__main__":
    sys.exit(main())
