from rampa_transicion import RampTransition, VERSION as RAMPA_TRANSICION_VERSION
_ramp_transition = RampTransition()
print("[RAMPA] " + RAMPA_TRANSICION_VERSION)
import cv2
from verde_oscuro import detectar_verde_oscuro, detectar_verde_sombra, VERSION_SOMBRA
from recuperacion_guard import RecoveryGuard
_rec_guard = RecoveryGuard()
from camthreader import *
import numpy as np
import math
import time
import serial
import sys
import os
import threading
import queue

# ==============================================================================
# CONFIGURACION POR DEFECTO PARA EL SERVICIO DE COMPETENCIA (IITA 2026)
# Activa todos los flags de competencia y palillos automaticamente al arrancar.
# Si se desea sobreescribir alguna variable por terminal, se respeta el entorno.
# ==============================================================================
import datetime

_now_str = datetime.datetime.now().strftime("%m%d_%H%M")
_SERVICE_ENV_DEFAULTS = {
    "PALILLOS_RECTA": "2",
    "GRABAR_CRUDO": "",   # Desactivado para maximo rendimiento (sin guardado de PNGs)
    "GRABAR": "",         # Desactivado para maximo rendimiento (sin encoder de video)
    "OBST_SIN_RECUP": "1",
    "DOBLE_SIN_FACTOR": "1",
    "BAJADA_SIN_RECUP": "1",
    "BAJADA_RECTA": "1",
    "BAJADA_POST_S": "4",
    "ROI_RAMPA": "cresta",
    "RECTA_RAMPA": "1",
    "RAMPA_SIN_RECUP": "1",
    "AMBIGUA_GAP": "1",
    "TERM_PISO": "1",
    "RECUP": "1",
    "RETROCEDER": "1",
    "RECUP_CAMINO": "1",
    "TERM_HARD_SHADOW": "1",
    "TERM_HARD_AUTH": "1",
    "SIDE_CHECK_SHADOW": "1",
    "SIDE_CHECK_AUTH": "1",
    "SAFE_NO_LINE_GUARD": "1",
    "CURVE_LATCH": "1",
    "COMPLETAR_GIRO": "1"
}

for _k, _v in _SERVICE_ENV_DEFAULTS.items():
    if _k not in os.environ:
        os.environ[_k] = _v

if os.environ.get("GRABAR_CRUDO"):
    try:
        os.makedirs(os.path.expanduser(os.environ["GRABAR_CRUDO"]), exist_ok=True)
    except Exception:
        pass

# Redirigir stdout y stderr a /home/iita/pista_$N.log ademas de la consola/systemd
class _TeeLogger:
    def __init__(self, filepath, stream):
        self.stream = stream
        try:
            self.file = open(filepath, "a", buffering=1, encoding="utf-8")
        except Exception:
            self.file = None

    def write(self, data):
        self.stream.write(data)
        if self.file:
            try:
                self.file.write(data)
            except Exception:
                pass

    def flush(self):
        self.stream.flush()
        if self.file:
            try:
                self.file.flush()
            except Exception:
                pass

_log_file = os.environ.get("LOG_FILE", f"/home/iita/pista_{_now_str}.log")
if not isinstance(sys.stdout, _TeeLogger):
    sys.stdout = _TeeLogger(_log_file, sys.stdout)
    sys.stderr = _TeeLogger(_log_file, sys.stderr)

print(f"[SERVICE] Flags de competencia cargados para corrida {_now_str}:")
print(f"  [SERVICE] Video -> {os.environ.get('GRABAR')}")
print(f"  [SERVICE] Log   -> {_log_file}")
print(f"  [SERVICE] Crudo -> {os.environ.get('GRABAR_CRUDO')}")
# ==============================================================================

# ================== MEJORAS DE SEGUIMIENTO (parche IITA) ==================
# Todo apagado por defecto: sin las variables de entorno el robot se comporta
# EXACTAMENTE como antes.
_MODO = os.environ.get("PLANNER", "0")
USAR_PLANNER = _MODO in ("1", "2")
MODO_HIBRIDO = _MODO == "2"
RUTA_VIDEO   = os.environ.get("GRABAR", "")
# CAMARA (12-oct). La camara corria con balance de blancos y exposicion en AUTOMATICO: el color de las mismas
# marcas verdes se fue corriendo dia a dia (canal b 126 -> 120 -> 115) y el rango dejaba de alcanzar.
#   CAMARA_WB=4600   balance de blancos fijo en esa temperatura (medirla en el lugar con medir_wb.py)
#   CAMARA_EXPO=40   exposicion fija (decimas de ms). Probar en el lugar: 100 o mas quemo la imagen el 12-oct
# Vacias = automatico, exactamente como antes. Se aplican al abrir la camara y cada vez que se reabre.
CAMARA_WB    = os.environ.get("CAMARA_WB", "")
CAMARA_EXPO  = os.environ.get("CAMARA_EXPO", "")
# DOBLE_SIN_FACTOR=1 (12-oct): el doble verde pedia ademas 1,2 x min_square_size pixeles verdes. El primer
# cuadro con los dos cuadrados a la vista podia quedar justo abajo (299 contra 300) y salia como verde SIMPLE,
# que es lo que ejecuta la Teensy. Con 1, alcanza con dos manchas y la cinta entre ellas. 0 = como antes.
FACTOR_DOBLE = 1.0 if os.environ.get("DOBLE_SIN_FACTOR", "0") == "1" else 1.2
# GRABAR_CRUDO=carpeta (12-oct): ademas del video, guarda CADA cuadro sin comprimir (PNG 160x120), lo que se
# mando a la Teensy, los pixeles de verde/negro, los rangos y la camara (ver grabador_crudo.py). Sirve para
# calibrar y analizar despues con todos los datos. Vacio = apagado.
GRABAR_CRUDO = os.environ.get("GRABAR_CRUDO", "")
_crudo = None
ROI_MODO     = os.environ.get("ROI", "60")
CTRL         = os.environ.get("CTRL", "atan2")
RECUP        = os.environ.get("RECUP", "0") == "1"
# RETROCEDER AL PERDER LA LINEA (idea de Benjamin). En vez de girar buscando a
# ciegas, se le avisa al firmware -green_state = 4- y el robot RETROCEDE un paso
# corto y vuelve a mirar. La linea no desaparece por casualidad: desaparece
# porque el robot se paso, y un segundo antes la tenia abajo. Retroceder rehace
# el camino; girar a ciegas puede alejarlo mas. Y cuando reaparece, aunque sea
# en un borde, el control normal gira hacia ella solo: el "alinearse" sale gratis.
RETROCEDER   = os.environ.get("RETROCEDER", "0") == "1"
GS_LINEA_PERDIDA = 4
K_CERCA      = float(os.environ.get("K_CERCA", "40"))
K_LEJOS      = float(os.environ.get("K_LEJOS", "40"))
RECUP_ANG    = float(os.environ.get("RECUP_ANG", "75"))
SATURA_DESDE = float(os.environ.get("SATURA_DESDE", "70"))
AREA_MIN_LINEA = float(os.environ.get("AREA_MIN", "200"))   # px; ver _solo_mi_linea
ROI_ABAJO    = int(os.environ.get("ROI_ABAJO", "120"))   # 120 = sin recorte abajo
ROI_ARRIBA   = int(os.environ.get("ROI_ARRIBA", "60"))    # 60 = como hoy
# ROI DE RAMPA (26-sep). Subiendo, arriba de la rampa se ve la sala y la mascara la toma como negro
# (codo_cg_1.avi, 25-34 s). SOLO mientras la Teensy avisa SUBIENDO (0xF2) y SOLO para el angulo de
# linea; verdes, recuperacion y gap siguen mirando la mascara de siempre. Se elige en el comando:
#   ROI_RAMPA=linea  el angulo se calcula solo con el negro CONECTADO con el robot (_solo_mi_linea):
#                    saca el paisaje suelto y conserva la parte lejana de la linea.
#   ROI_RAMPA=corte  el angulo se calcula desde la fila ROI_RAMPA_CORTE (100). Ojo: con 20 filas el
#                    angulo satura en +-80 ante cualquier corrimiento (codo_cg_1.avi, 26,4-27,6 s).
#   ROI_RAMPA=cresta como `linea`, y ademas corta en la CRESTA: si pasando la cresta la sala forma
#                    una franja ancha de negro pegada al borde de arriba y PEGADA a la punta de la
#                    cinta, el angulo se calcula solo por debajo (_corte_paisaje). rampa_roi_1.avi
#                    179 s: de +24 (hacia la sala) a -49 (hacia la cinta).
#   sin ROI_RAMPA    exactamente el paquete del 15-sep.
ROI_RAMPA       = {"1": "corte", "corte": "corte", "linea": "linea", "cresta": "cresta"}.get(
                      os.environ.get("ROI_RAMPA", "0"), "")
ROI_RAMPA_CORTE = int(os.environ.get("ROI_RAMPA_CORTE", "100"))
ROI_RAMPA_VIGENCIA_S = 1.5   # la Teensy lo reenvia cada 0,5 s; sin aviso fresco vuelve a lo normal
# CRESTA (solo ROI_RAMPA=cresta). Con la sala cortada quedan 12-40 filas de cinta y el atan2 se
# dispara con una linea tan corta (rampa_cresta_1.avi 5,9-6,6 s: -53 +20 +68 +71 -3 -80 -83 con el
# robot derecho sobre la cinta). Con un pedazo corto solo se puede CENTRAR: angulo = -CRESTA_K x el
# error lateral de la cinta (-1 izq .. +1 der). Mismo tramo: -7 +2 +11 +12 0 -12 -19 -8.
# Y cuando la cinta desaparece bajo la trompa (6,7-6,8 s) la Pi disparaba la recuperacion (retroceso
# y pivote en plena cresta): ahora sigue DERECHO hasta CRESTA_RECTO_MAX_S desde la ultima vez que vio
# la cinta, mientras sube o hasta CRESTA_POST_S despues de que la Teensy dejo de decir SUBE.
CRESTA_K            = float(os.environ.get("CRESTA_K", "30"))
CRESTA_RECTO_MAX_S  = float(os.environ.get("CRESTA_RECTO_MAX_S", "1.5"))
CRESTA_POST_S       = 1.5
# RECTA SUBIENDO (27-sep). Subiendo una recta la Pi corrige milimetros (~8 grados por mm corrido): el
# robot se tambalea y las ruedas de un lado dejan de empujar (codo_cg_1.avi 19,6-25 s: angulo tipico
# 13, p90 37, 1,7 cambios de lado por s). Con RECTA_RAMPA=1, si la cinta que se ve es RECTA, esta
# DERECHA y CERCA DEL CENTRO durante RECTA_CUADROS cuadros seguidos, se manda una correccion chica:
#   angulo = RECTA_KH x inclinacion de la cinta (grados)  -  RECTA_KE x corrimiento abajo (-1..+1)
# En cuanto deja de ser recta (curva, "Z", cruce), en ESE cuadro vuelve el angulo de siempre.
# Medido sobre los videos (mismos cuadros): curva en Z de rampa_mapa_1 = 0 %% tomada como recta;
# recta de codo_cg_1 = 76 %% (angulo tipico 13 -> 2, cambios de lado 1,7 -> 0,2 por s).
# RAMPA_CERO=1 = PRUEBA DE AISLAMIENTO: subiendo (fuera de la cresta) manda SIEMPRE 0, como la Pi
# apagada en la RoboCup. Es para probar, no para correr.
# Las dos necesitan ROI_RAMPA=linea o cresta. Sin ellas, exactamente el FREEZE del 27-sep.
RECTA_RAMPA      = os.environ.get("RECTA_RAMPA", "0") == "1"
RAMPA_CERO       = os.environ.get("RAMPA_CERO", "0") == "1"
RECTA_DESVIO_PX  = float(os.environ.get("RECTA_DESVIO_PX", "1.0"))   # cuanto se aparta de una recta
RECTA_PENDIENTE  = float(os.environ.get("RECTA_PENDIENTE", "0.4"))   # px de corrimiento por fila
RECTA_ABAJO      = float(os.environ.get("RECTA_ABAJO", "0.45"))      # corrimiento abajo, -1..+1
RECTA_ALTO_MIN   = int(os.environ.get("RECTA_ALTO_MIN", "40"))       # filas de cinta minimas
RECTA_CUADROS    = int(os.environ.get("RECTA_CUADROS", "3"))
RECTA_KH         = float(os.environ.get("RECTA_KH", "1.0"))
RECTA_KE         = float(os.environ.get("RECTA_KE", "30"))
# PERSPECTIVA (3-oct, rampa_corta_1.avi 5:54-5:56). Una cinta PARALELA al robot pero corrida a un costado
# se ve inclinada en la imagen (converge al horizonte). Sin descontar eso, "corrida" y "torcida" se
# anulaban: la regla mandaba ~-2 mientras la cinta se iba de -0,18 a -0,45, y al soltar venia el volantazo
# (+56, despues -82). Con RECTA_PERSPECTIVA=1 la inclinacion se mide respecto de la que tendria una cinta
# paralela corrida lo mismo: pendiente - corrimiento / (fila_cerca - RECTA_VH). 0 = como antes.
RECTA_PERSPECTIVA = os.environ.get("RECTA_PERSPECTIVA", "1") == "1"
RECTA_VH          = float(os.environ.get("RECTA_VH", "10"))   # fila del horizonte (medida 9,6-10, R2 0,997)
# SUBIENDO SIN RECUPERACION (3-oct). En la subida, perder la cinta disparaba la recuperacion: el robot
# retrocede cuesta abajo y se cae (rampa_cero_1.log: dos disparos con SUBE, uno "GAP"). Con
# RAMPA_SIN_RECUP=1, mientras la Teensy dice SUBE y hasta CRESTA_POST_S (1,5 s) despues (al arrancar la
# subida el aviso parpadea SUBE/LLANO), sin cinta sigue DERECHO y no dispara nada. Pasado eso, todo
# sigue como siempre.
# Necesita ROI_RAMPA=linea o cresta. Sin ella, exactamente lo de antes.
RAMPA_SIN_RECUP  = os.environ.get("RAMPA_SIN_RECUP", "0") == "1"
# Tambien con RAMPA_SIN_RECUP=1 y subiendo: llegando a la cresta la cinta se termina y abajo queda un
# pedazo corto que no sube ni sale por un costado. El atan2 de ese pedazo da +-80 (rampa_recta_1.avi:
# 34,4 s se fue a la derecha; 47-50 s zigzag de lado a lado). Si la cinta conectada tiene menos de
# RAMPA_CORTA_FILAS filas y no toca los costados de la imagen, se trata como "sin cinta": DERECHO.
# Una curva de verdad sale por un costado o sigue para arriba: esa no se toca.
RAMPA_CORTA_FILAS = int(os.environ.get("RAMPA_CORTA_FILAS", "35"))
# Y en la cresta (rampa_corta_1.avi 6:03-6:05): el detector de la cresta se prendia y apagaba cuadro por
# medio; en los cuadros que fallaba, el angulo de siempre tomaba la T y la sala (+37...+88). Con
# RAMPA_SIN_RECUP=1, si se detecto la cresta hace menos de CRESTA_HOLD_S, se sigue usando ese corte, SOLO
# si es una cresta estable (CRESTA_HOLD_MIN detecciones en el ultimo segundo): al pie de la rampa, en la Z
# de rampa_mapa_1, el detector salta 3 cuadros por el manchon negro y ahi no hay que sostener nada.
CRESTA_HOLD_S   = float(os.environ.get("CRESTA_HOLD_S", "0.4"))
CRESTA_HOLD_MIN = int(os.environ.get("CRESTA_HOLD_MIN", "6"))
# BAJADA COMO LA SUBIDA (10-oct, freeze_.avi 5:34-5:44). Bajando, la Pi usaba la ley de siempre: con la
# cinta derecha mandaba +60, -54, +83 (zigzag, como la subida antes de la recta), llego torcida a la T de
# abajo, se salio y la recuperacion la tiro de la pista. Dos interruptores, solo mientras la Teensy dice
# BAJA (pitch <= -14 sostenido 200 ms; en ningun CSV de piso pasa andando):
#   BAJADA_SIN_RECUP=1  como RAMPA_SIN_RECUP: sin cinta sigue DERECHO y no dispara la recuperacion,
#                       mientras dice BAJA y hasta BAJADA_POST_S (1,5 s) despues. Pasado eso, como siempre.
#   BAJADA_RECTA=1      la misma ley de linea que subiendo: solo la cinta conectada con el robot, la regla
#                       de la recta (RECTA_RAMPA) y cinta corta = derecho. SIN el corte de la cresta (eso es
#                       de arriba de la subida). Cartel `bajada-...` en vez de `rampa-...`.
# Necesitan ROI_RAMPA=linea o cresta. Sin ellos, exactamente el freeze del 3-oct.
BAJADA_SIN_RECUP = os.environ.get("BAJADA_SIN_RECUP", "0") == "1"
BAJADA_RECTA     = os.environ.get("BAJADA_RECTA", "0") == "1"
# Cuanto dura BAJADA_SIN_RECUP despues de que la Teensy deja de decir BAJA. Con dos bajadas seguidas (la
# pista del 10-oct: bajada, descanso corto, segunda bajada) la cinta se pierde en el BORDE de la segunda
# ANTES de que el robot se incline: 2,6 s (bajada_1010_2043.csv) y 3,5 s (bajada_.avi) despues de la
# primera. Con 4 s queda cubierto. Contra: en ese rato, una perdida en el piso sigue derecho en vez de
# recuperar.
BAJADA_POST_S    = float(os.environ.get("BAJADA_POST_S", "1.5"))
# OBSTACULO SIN RECUPERACION (12-oct, crudo 1012_135700 cuadros 8314-8590). Durante el esquive la cinta se
# pierde: la Pi pedia la recuperacion (GS=4) y esperaba el 0xEF todo el esquive (3,5 a 7 s); al volver a
# la cinta la Teensy la ejecutaba, retrocedia, pivoteaba y se iba de la pista. Con OBST_SIN_RECUP=1, desde
# que la Teensy avisa 0xF5 (empieza el esquive) hasta OBST_POST_S despues del 0xF6 (volvio a la cinta), sin
# cinta sigue DERECHO y no dispara la recuperacion ni el gap, igual que en la rampa. Con la cinta a la vista
# la sigue como siempre. Si el 0xF6 no llega, la ventana se cierra sola a los OBST_MAX_S.
# Necesita la Teensy con OBSTACULO_AVISA_PI. Sin la variable, exactamente lo de antes.
OBST_SIN_RECUP   = os.environ.get("OBST_SIN_RECUP", "0") == "1"
OBST_POST_S      = float(os.environ.get("OBST_POST_S", "3"))
OBST_MAX_S       = 10.0
# PALILLOS EN LA RECUPERACION (17-oct, pista_.avi: 6:18, 6:47, 7:39, 9:00, 12:23, 14:21, 14:32). El
# reglamento deja escombros sueltos (palillos, varillas de hasta 3 mm) tambien sobre la linea. Una brocheta
# atravesada abajo del robot le corta la cinta y dispara la recuperacion; despues del retroceso la cinta
# se ve en pedazos y el arbitro elige CURVA (en 7:39, una recta, giro y salio de la pista). Con
# PALILLOS_RECTA=N, si en N cuadros despues del retroceso el pedazo de cinta de abajo esta a
# PALILLOS_CORTE px o menos de otro pedazo mas adelante, se decide RECTA: derecho, como en un gap.
# 0 = como antes.
PALILLOS_RECTA   = int(os.environ.get("PALILLOS_RECTA", "0"))
PALILLOS_CORTE   = float(os.environ.get("PALILLOS_CORTE", "14"))

_ult_lado = 0.0        # +1 la linea estaba a la derecha, -1 a la izquierda
_frames_sin = 0        # cuantos frames seguidos sin verla

# --- RECUPERACION ANTIFALSOS / ANTI-RETRIGGER -------------------------------
# GS=4 NO significa "este frame no vio negro".
# Significa: "venia siguiendo linea estable y la perdi de forma confirmada".
# Todos los valores se pueden barrer por entorno sin editar el archivo.
RECUP_PERDIDA_FRAMES   = int(os.environ.get("RECUP_PERDIDA_FRAMES", "3"))
RECUP_RECAPTURA_FRAMES = int(os.environ.get("RECUP_RECAPTURA_FRAMES", "3"))
RECUP_RECAPTURA_MIN_S  = float(os.environ.get("RECUP_RECAPTURA_MIN_S", "0.55"))
RECUP_REARME_FRAMES    = int(os.environ.get("RECUP_REARME_FRAMES", "8"))
RECUP_BLOQUEO_VERDE_S  = float(os.environ.get("RECUP_BLOQUEO_VERDE_S", "3.0"))
RECUP_BLOQUEO_DOBLE_S  = float(os.environ.get("RECUP_BLOQUEO_DOBLE_S", "6.0"))
RECUP_SOLTAR_CONTROL_S   = float(os.environ.get("RECUP_SOLTAR_CONTROL_S", "1.35"))
RECUP_POST_NORMAL_S      = float(os.environ.get("RECUP_POST_NORMAL_S", "1.50"))

_recup_armada = False
_recup_activa = False
_recup_malos = 0
_recup_buenos = 0
_recup_rearme_buenos = 0
_recup_bloqueo_hasta = 0.0
_recup_ultimo_angle = 0.0
_recup_inicio_ts = 0.0
_recup_post_hasta = 0.0

# CAMINO+MONO se usa SOLO como sensor de rumbo para recovery.
# No reemplaza angle normal ni mueve el robot mientras la linea existe.
RECUP_CAMINO = os.environ.get("RECUP_CAMINO", "0") == "1"
RECUP_CAMINO_MAX_AGE_S = float(os.environ.get("RECUP_CAMINO_MAX_AGE_S", "0.45"))
RECUP_CAMINO_REANALISIS_MAX_AGE_S = float(os.environ.get("RECUP_CAMINO_REANALISIS_MAX_AGE_S", "0.12"))
_recup_rumbo_camino_raw = None      # DER+ tal como lo calcula CAMINO
_recup_rumbo_congelado = 0.0        # convencion protocolo: derecha negativa
_recup_rumbo_fuente = "sin-camino"
_camino_shadow = None

# INTEGRACION AUDITADA: la camara decide geometria/negro; APDS decide colores.
GS_GAP_BUSQUEDA = 18
GS_PERDIDA_FAILSAFE = 19
GAP_RECAPTURA_FRAMES = 3
GAP_REARME_BLOQUEO_S = 0.35
PERDIDA_AMBIGUA_MAX_S = 1.00
# AMBIGUA -> GAP (3-oct). Casi todas las perdidas que quedan AMBIGUA ("sin CAMINO confiable": despues del
# retroceso no se ve cinta) son gaps, y el STOP deja al robot parado. Con AMBIGUA_GAP=1, si al terminar
# la ventana de PERDIDA_AMBIGUA_MAX_S sigue AMBIGUA, arranca la busqueda de GAP derecho (igual que la
# decision RECTA). Mientras dura la ventana, nada cambia: si se resuelve a CURVA o RECTA, hace eso.
AMBIGUA_GAP = os.environ.get("AMBIGUA_GAP", "0") == "1"

_loss_arb = None
_loss_camino_frame = None
_loss_retro_done = False
_loss_retro_ts = 0.0
_loss_decision = None
_loss_curve_sent_ts = 0.0
_gap_activa = False
_gap_origen_superado = False
_gap_buenos = 0
_gap_failsafe = False

# --- V6.6 FIELD: parches MINIMOS sobre FREEZE V6.5 -------------------------
# TERM_HARD_SHADOW=1: medir/loguear terminal local sin cambiar decisiones.
# TERM_HARD_AUTH=1: permite SOLO vetar dos CURVA por memoria lateral vieja.
# SAFE_NO_LINE_GUARD=1: cuando recovery NO puede actuar y no hay componente
# conectada, fuerza angle=0 para que atan2(0,0)-90 no genere un volantazo.
TERM_HARD_SHADOW = os.environ.get("TERM_HARD_SHADOW", "1") == "1"
TERM_HARD_AUTH = os.environ.get("TERM_HARD_AUTH", "0") == "1"
SAFE_NO_LINE_GUARD = os.environ.get("SAFE_NO_LINE_GUARD", "1") == "1"
# REV2: SIDE_CHECK post-retro. SHADOW=1 loguea WOULD_FLIP; AUTH=1 invierte el lado de una
# CURVA decidida SOLO por memoria (reglas 3b/4) cuando >=2 frames post-retro 'falso +/-90'
# muestran la rama del lado contrario (|shift|>=40 y |dx|>=40, mismo signo).
SIDE_CHECK_SHADOW = os.environ.get("SIDE_CHECK_SHADOW", "1") == "1"
SIDE_CHECK_AUTH = os.environ.get("SIDE_CHECK_AUTH", "0") == "1"
# REV3: congelar una CURVA una vez elegida y recordar laterales reales
# vistos durante TODO el episodio para que el deque de 7 frames no los olvide.
CURVE_LATCH = os.environ.get("CURVE_LATCH", "1") == "1"
_side_check_logged = False
_side_seen_raw_lateral = set()
_curve_latched_decision = None
_curve_latch_logged = False
_term_guard = None
_term_episode_evidence = None
_term_veto_logged = False
try:
    if TERM_HARD_SHADOW or TERM_HARD_AUTH:
        from terminal_local_guard import TerminalLocalHard, apply_optional_veto, apply_side_check, VERSION as TERM_HARD_VERSION, TERM_PISO
        _term_guard = TerminalLocalHard()
        print("[V6.6] %s SHADOW=%d AUTH=%d SAFE_NO_LINE=%d SIDE_SHADOW=%d SIDE_AUTH=%d LATCH=%d TERM_PISO=%d" %
              (TERM_HARD_VERSION, int(TERM_HARD_SHADOW), int(TERM_HARD_AUTH), int(SAFE_NO_LINE_GUARD),
               int(SIDE_CHECK_SHADOW), int(SIDE_CHECK_AUTH), int(CURVE_LATCH), int(TERM_PISO)))
except Exception as _term_import_err:
    print("[V6.6] TERM_HARD no disponible; V6.5 sigue intacta: %s" % _term_import_err)
    _term_guard = None

# COMPLETAR_GIRO (2026-09-13): despues del pivote de recuperacion, si la cinta quedo
# DE FRENTE, seguir girando al mismo lado hasta que suba. Apagado por defecto.
# Necesita la Teensy que manda 0xED al terminar el pivote. Ver completar_giro.py.
COMPLETAR_GIRO = False
_cg = None
try:
    from completar_giro import CompletarGiro, COMPLETAR_GIRO, CG_ANG, CG_VENTANA_S, CG_MAX_S, CG_DESARMA_AD
    _cg = CompletarGiro()
    print("[CG] COMPLETAR_GIRO=%d ang=%.0f ventana=%.2f max=%.2f desarma=%d" %
          (int(COMPLETAR_GIRO), CG_ANG, CG_VENTANA_S, CG_MAX_S, CG_DESARMA_AD))
except Exception as _cg_import_err:
    COMPLETAR_GIRO = False
    _cg = None
    print("[CG] no disponible; comportamiento anterior: %s" % _cg_import_err)
# ---------------------------------------------------------------------------


def _fila_horizonte(frame_bgr, minimo=25, maximo=60):
    """Primera fila donde termina el SALON y empieza el piso de la pista.

    main.py recorta con black_mask[:60, :] = 0, un numero fijo. Medido sobre las
    corridas del 2026-08-22: el salon termina en la fila 35-40, asi que el
    recorte fijo tira 17-20 FILAS DE PISTA -casi un tercio del ROI utilizable, y
    justamente las mas lejanas, las unicas que sirven para anticipar-.

    Mira DOS cosas, no una: que la fila sea razonablemente clara (>110) y que
    sea PAREJA (desvio < 55). El salon es oscuro y texturado -muebles, sillas,
    patas-; el piso de la pista es claro y uniforme. La textura los separa mejor
    que el brillo solo, que es lo que fallaba en la primera version (cortaba en
    la fila 54 y recuperaba 5 filas en vez de 20).

    Validado a ojo sobre seis frames repartidos: la fila elegida cae en el borde
    salon/piso en los seis, y lo que se recupera es pista con cinta. Confundir
    negro con linea ya paso dos veces este mismo dia, asi que la validacion
    visual no es opcional.
    """
    try:
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).astype(float)
        brillo = g.mean(axis=1)
        textura = g.std(axis=1)
        for y in range(maximo + 20):
            if brillo[y] > 110 and textura[y] < 55 and brillo[y:y + 10].mean() > 110:
                return max(minimo, y)
    except Exception:
        pass
    return maximo


def _corte_paisaje(mask, desde=60, ancho_min=50, alto_min=10, huecos=2, cuello=0.5):
    """Fila desde la que se calcula el angulo subiendo la rampa, sin la sala de la cresta.

    Pasando la cresta la camara ve la sala y la mascara la toma como negro: una franja ANCHA
    (>= ancho_min px por fila; medido 86-93 de 160 contra 7-30 de la cinta) que arranca en el
    borde de arriba del recorte y mide >= alto_min filas, con un CUELLO angosto debajo (la cinta
    llegando a la cresta: < cuello x el ancho de la franja). Sin cuello es la cinta misma, grande y
    cerca: no se corta. Una curva de la rampa es una franja finita con rampa blanca arriba: no
    llega al borde y no se corta. Si no hay franja devuelve `desde` (no corta).
    Validado a ojo en rampa_roi_1.avi 172-185 s y codo_cg_1.avi 22-34 s.
    """
    try:
        cuenta = (mask > 0).sum(axis=1)
        ultima = None
        malas = 0
        for y in range(desde, mask.shape[0]):
            if cuenta[y] >= ancho_min:
                ultima = y
                malas = 0
            else:
                malas += 1
                if malas > huecos:
                    break
        if ultima is None or ultima - desde + 1 < alto_min:
            return desde
        banda = float(np.median(cuenta[desde:ultima + 1]))
        debajo = cuenta[ultima + 1:]
        if len(debajo) == 0 or debajo.min() >= cuello * banda:
            return desde
        return ultima + 1
    except Exception:
        return desde


def _forma_recta(mask):
    """Forma de la cinta conectada con el robot (filas 60-119): None si hay muy poca.
    desvio = cuanto se aparta el centro de la cinta de una recta (px); pendiente = px de corrimiento
    por fila (0 = derecha en la imagen); abajo = donde esta la cinta cerca del robot (-1 izq..+1 der);
    alto = filas con cinta."""
    try:
        filas, centros = [], []
        for y in range(60, mask.shape[0], 2):
            xs = np.flatnonzero(mask[y] > 0)
            if len(xs) >= 3:
                filas.append(y)
                centros.append(float(xs.mean()))
        if len(filas) < 6:
            return None
        f = np.array(filas, float)
        c = np.array(centros)
        a, b = np.polyfit(f, c, 1)
        desvio = float(np.sqrt(np.mean((c - (a * f + b)) ** 2)))
        cerca = c[f >= 104].mean() if (f >= 104).any() else c[-1]
        fila_cerca = f[f >= 104].mean() if (f >= 104).any() else f[-1]
        mitad = mask.shape[1] / 2.0
        return {"desvio": desvio, "pendiente": float(a), "alto": int(f.max() - f.min()),
                "abajo": float((cerca - (mitad - 1)) / mitad), "fila_cerca": float(fila_cerca),
                "mitad": mitad}
    except Exception:
        return None


def _cinta_partida(frame_bgr):
    """PALILLOS_RECTA: True si el pedazo de cinta de abajo esta a PALILLOS_CORTE px o menos de otro
    pedazo de cinta mas adelante (lo que deja un palillo atravesado)."""
    try:
        b = cv2.inRange(frame_bgr, lower_black, upper_black)
        b[:50, :] = 0
        n, et, st, cen = cv2.connectedComponentsWithStats(b, 8)
        abajo = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 60 and
                 st[i, cv2.CC_STAT_TOP] + st[i, cv2.CC_STAT_HEIGHT] - 1 >= 105]
        if not abajo:
            return False
        i = max(abajo, key=lambda k: st[k, cv2.CC_STAT_AREA])
        dist = cv2.distanceTransform((et != i).astype(np.uint8), cv2.DIST_L2, 3)
        for j in range(1, n):
            if j == i or st[j, cv2.CC_STAT_AREA] < 40 or cen[j][1] >= cen[i][1] - 5:
                continue
            if float(dist[et == j].min()) <= PALILLOS_CORTE:
                return True
        return False
    except Exception:
        return False


def _solo_mi_linea(mask):
    """Deja SOLO la mancha que toca al robot; el resto del negro se descarta.

    En el ROI caen otros tramos negros de la pista -otra cinta cruzando, juntas
    del piso, cables- que no son la linea que el robot esta siguiendo. Medido:
    en el 38% de los frames hay algo asi, y aunque casi siempre es inofensivo,
    en el 2,2% corre el centroide lejano hasta 1,51 (de un extremo al otro).
    La linea seguible es, por definicion, la conectada con la que esta debajo.
    Cuesta 0,09 ms por frame.
    """
    try:
        num, et, st, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
        fila = et[mask.shape[0] - 2]
        suyas = np.unique(fila[fila > 0])
        # SI NADA TOCA AL ROBOT, DEVOLVER VACIO, NO LA MASCARA ENTERA.
        # Devolver la mascara completa era el peor fallback posible: cuando el
        # robot se sale a un piso de madera o al salon, el ruido de la veta pasa
        # el filtro, _error_lateral encuentra sus 20 pixeles y devuelve un
        # numero -basura, pero un numero-, asi que la recuperacion de linea
        # NUNCA se activa. Medido el 2026-08-22 en el video a.avi: en los cinco
        # episodios de salida la componente que toca al robot tiene area 0, y el
        # overlay decia "centroide" en vez de "buscando" durante los 3,7 s.
        if not len(suyas):
            return np.zeros_like(mask)
        # Y una mancha demasiado chica tampoco es una linea: es ruido pegado al
        # borde. Umbral sacado de los datos, no a ojo: con 200 px se marcan como
        # "sin linea" el 100% de los frames de salida y solo el 11% de los
        # normales, donde la mediana del area es 3080 px.
        area = max(int(st[i, cv2.CC_STAT_AREA]) for i in suyas)
        if area < AREA_MIN_LINEA:
            return np.zeros_like(mask)
        return (np.isin(et, suyas) * 255).astype(np.uint8)
    except Exception:
        return mask


def _error_lateral(mask, y0, y1):
    """Donde esta la cinta entre las filas y0 e y1, de -1 (izquierda) a +1."""
    banda = mask[y0:y1, :]
    xs = np.nonzero(banda)[1]
    if len(xs) < 20:
        return None
    return (float(xs.mean()) - (mask.shape[1] - 1) / 2.0) / (mask.shape[1] / 2.0)


def _angulo_lineal(mask, corte):
    """Dos terminos lineales. El atan2 que usa main.py no es un controlador, es
    un cambio de coordenadas, y su ganancia esta INVERTIDA. Medido sobre 3221
    frames de pista:

        desvio       angulo medio   ganancia
        0 - 5 px        19,3 gr      1,04 gr/px
        5 - 10 px       26,9         1,74
        30 - 45 px      55,6         0,29
        45 - 80 px      57,5        -0,61    <- deja de corregir

    A UN pixel del centro ya corrige 1,45 grados -por eso oscila- y a 45 px no
    corrige mas que a 30 -por eso, cuando se fue, no vuelve-.

        e_cerca  cuan corrido esta AHORA   -> lo endereza
        e_lejos  para donde va la cinta    -> lo anticipa
    Los dos con ganancia CONSTANTE (K/80 grados por pixel).
    """
    mask = _solo_mi_linea(mask)
    e_pos = _error_lateral(mask, 105, 119)
    if e_pos is None:
        e_pos = _error_lateral(mask, corte, 120)
        if e_pos is None:
            return None
    # RUMBO = la DIFERENCIA entre donde esta la linea lejos y donde esta cerca.
    # NO es la posicion lejana: eso seria medir posicion otra vez, un poco mas
    # arriba, y es el error que tenia la primera version -los dos terminos eran
    # posicion, correlacionados, asi que el controlador tenia UNO SOLO-.
    #
    # Medido el 2026-08-22 sobre hist.avi, y es el hallazgo que faltaba:
    #   el robot esta CENTRADO (|pos| < 12 px) el 40% del tiempo,
    #   pero de esos frames el 57% tiene el RUMBO torcido (>20 px),
    #   con una mediana de 28,6 px, que es casi un ancho de cinta.
    # O sea que se para sobre la linea apuntando para otro lado, y desde ahi se
    # vuelve a ir. Observado en pista por Benjamin: "no se reacomoda con el
    # centro de la linea y queda chueco hasta que en algun giro la pierde".
    #
    # Las cinco leyes de control probadas ese dia eran TODAS de posicion pura.
    # Ninguna miraba el rumbo, y por eso ninguna le gano al atan2 original.
    lejos = _error_lateral(mask, corte, min(corte + 18, 96))
    if lejos is None:
        # sin banda lejana no hay rumbo medible: solo posicion, con todo el peso
        return max(-90.0, min(90.0, -(K_CERCA + K_LEJOS) * e_pos))
    e_rumbo = lejos - e_pos
    return max(-90.0, min(90.0, -(K_CERCA * e_pos + K_LEJOS * e_rumbo)))


_seguidor = None
if USAR_PLANNER:
    try:
        from seguidor_linea import Seguidor
        _seguidor = Seguidor()
        print("[PLANNER] encendido")
    except Exception as _e:
        print("[PLANNER] no se pudo cargar (%s): sigo con el metodo de siempre" % _e)
        USAR_PLANNER = False

# Shadow independiente: CAMINO+MONO solo calcula heading para una eventual
# recuperacion. Su salida NO se asigna a `angle` durante seguimiento normal.
if RECUP_CAMINO:
    try:
        from camino_heading import CaminoHeading
        _camino_shadow = CaminoHeading()
        print("[RECUP-CAMINO] CAMINO+MONO shadow encendido (solo heading)")
    except Exception as _e:
        _camino_shadow = None
        print("[RECUP-CAMINO] no se pudo cargar (%s): recovery queda sin giro dirigido" % _e)

if _camino_shadow is not None:
    try:
        from camino_loss_arbiter import LossArbiter
        _loss_arb = LossArbiter()
        print("[PERDIDA] arbitro CURVA/RECTA/AMBIGUA cargado")
    except Exception as _e:
        _loss_arb = None
        print("[PERDIDA] arbitro no cargo (%s): se conserva recovery congelado como fallback" % _e)

print("[PARCHE] ROI=%s CTRL=%s RECUP=%s PLANNER=%s RECUP_CAMINO=%s" %
      (ROI_MODO, CTRL, RECUP, _MODO, int(bool(_camino_shadow))))

_video = None
_video_n = 0


def _cerrar_video():
    """cv2.VideoWriter escribe el indice del AVI recien en release(). Sin esto,
    cortando con Ctrl-C -que es como se corta siempre- el archivo puede no
    abrir. atexit corre igual con KeyboardInterrupt."""
    global _video
    if _video is not None:
        try:
            _video.release()
            print("[GRABAR] cerrado: %d frames en %s" % (_video_n, RUTA_VIDEO))
        except Exception:
            pass
        _video = None


import atexit
atexit.register(_cerrar_video)


def _grabar(frame_bgr, ang_viejo, ang_nuevo, r, quien, corte):
    """Una imagen por frame: lo que el robot vio Y lo que decidio.
    Nunca levanta una excepcion hacia el lazo de vision."""
    global _video, _video_n
    if not RUTA_VIDEO:
        return
    try:
        vis = cv2.resize(frame_bgr, (320, 240), interpolation=cv2.INTER_NEAREST)
        cv2.line(vis, (0, corte * 2), (319, corte * 2), (0, 255, 255), 1)
        if r is not None and r.get("mascara") is not None:
            mk = cv2.cvtColor(cv2.resize(r["mascara"], (320, 240),
                              interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        else:
            m = cv2.inRange(frame_bgr, lower_black, upper_black)
            m[:corte, :] = 0
            mk = cv2.cvtColor(cv2.resize(_solo_mi_linea(m), (320, 240),
                              interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        if r is not None and r.get("puntos"):
            p = [(int(x * 2), int(y * 2)) for x, y in r["puntos"]]
            for u, v in zip(p, p[1:]):
                cv2.line(vis, u, v, (0, 255, 0), 2)
            for x, y in p:
                cv2.circle(mk, (int(x * 2), int(y * 2)), 2, (0, 0, 255), -1)
        cv2.putText(vis, "viejo %+.0f" % ang_viejo, (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        if ang_nuevo is not None:
            cv2.putText(vis, "manda %+.0f" % ang_nuevo, (4, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        cv2.putText(vis, quien, (4, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 128, 255) if quien == "buscando" else (0, 255, 0), 1)
        cv2.putText(mk, "mascara  corte f%d" % corte, (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 128, 0), 1)
        vis = np.hstack([vis, mk])
        if _video is None:
            _video = cv2.VideoWriter(os.path.expanduser(RUTA_VIDEO),
                                     cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (640, 240))
            print("[GRABAR] escribiendo en %s" % RUTA_VIDEO)
        _video.write(vis)
        _video_n += 1
    except Exception as _e:
        print("[GRABAR] se apaga por error: %s" % _e)
        globals()["RUTA_VIDEO"] = ""


def _grabar_crudo(frame_bgr, green_mask, black_mask, speed, angle, green_state, silver, quien):
    """GRABAR_CRUDO: un PNG y una linea de CSV por cuadro. Nunca levanta una excepcion hacia el lazo."""
    global _crudo
    try:
        if _crudo is None:
            from grabador_crudo import GrabadorCrudo
            g = globals()
            par = {k: (g[k].tolist() if hasattr(g.get(k), "tolist") else g.get(k)) for k in (
                "lower_green", "upper_green", "lower_black", "upper_black", "min_square_size",
                "lower_red1", "upper_red1", "lower_red2", "upper_red2", "lower_silver_hsv", "upper_silver_hsv")}
            _crudo = GrabadorCrudo(os.path.expanduser(GRABAR_CRUDO), par, os.path.abspath(__file__))
        _crudo.cuadro(frame_bgr, estado, speed, angle, green_state, silver, quien,
                      int(np.count_nonzero(green_mask)), int(np.count_nonzero(black_mask)), _rampa_teensy)
    except Exception as _e:
        print("[GRABAR_CRUDO] se apaga por error: %s" % _e)
        globals()["GRABAR_CRUDO"] = ""
# =========================================================================


HEADLESS = os.environ.get("DISPLAY") is None
DEBUG_VIEW = os.environ.get("DEBUG_VIEW") == "1"
SHOW_DEBUG_WINDOWS = (not HEADLESS) or DEBUG_VIEW
ENABLE_CX_BLACK_GUARD = True

# PROTOCOLO RPi -> Teensy
# Frame: [0xFF, speed, 0xFE, angle, 0xFD, green_state, 0xFC, silver_line]
#
# CONTRATO DE RANGOS:
# speed:       [0, 100]
# angle:       [0, 180]   # se envia como angle + 90
# green_state: 0..20
# silver_line: 0 o 1
#
# Los payloads NO deben colisionar con los sync bytes 0xFC..0xFF.

SYNC_SPEED = 0xFF
SYNC_ANGLE = 0xFE
SYNC_GREEN_STATE = 0xFD
SYNC_SILVER_LINE = 0xFC

TEENSY_BOOT = b'\xfa'
TEENSY_READY = b'\xf9'
TEENSY_RESCATE_DONE = b'\xf8'
TEENSY_STOP = b'\xff'
TEENSY_RESCATE = b'\xf1'      # 241 = APDS plateado confirmado / iniciar rescate
TEENSY_EVACUACION = b'\xf7'  # 247 = termino rescate, iniciar evacuacion
TEENSY_RETRO_DONE = b'\xef'   # 239 = retroceso recovery terminado; analizar pose nueva
TEENSY_GAP_TIMEOUT = b'\xf0'  # 240 = GAP excedio limite fisico/tiempo
TEENSY_GAP_ORIGIN = b'\xee'   # 238 = ya avanzo mas que retroceso_real + 1 cm
TEENSY_PIVOTE_DONE = b'\xed'  # 237 = termino el pivote de recuperacion (COMPLETAR_GIRO)
TEENSY_RAMPA_SUBE  = b'\xf2'  # 242 = subiendo (pitch >= 14 sostenido 200 ms)
TEENSY_RAMPA_BAJA  = b'\xf3'  # 243 = bajando
TEENSY_RAMPA_LLANO = b'\xf4'  # 244 = llano
TEENSY_OBST_INICIO = b'\xf5'  # 245 = empieza el esquive del obstaculo (OBST_SIN_RECUP)
TEENSY_OBST_FIN    = b'\xf6'  # 246 = termino el esquive: volvio a la cinta
_rampa_teensy = 0            # ultimo aviso de la Teensy: 1 sube, -1 baja, 0 llano
_rampa_teensy_ts = 0.0       # time.monotonic() de ese aviso
_rampa_sube_fin_ts = 0.0     # time.monotonic() de cuando la Teensy dejo de decir SUBE
_rampa_baja_fin_ts = 0.0     # time.monotonic() de cuando la Teensy dejo de decir BAJA
_obst = {"ini": 0.0, "fin": 0.0, "reset": False}
_palillo = {"ts": None, "n": 0}   # PALILLOS_RECTA: cuadros con la cinta partida en este episodio   # OBST_SIN_RECUP: cuando empezo / termino el esquive
_cresta = {"ult_linea": 0.0}  # time.monotonic() de la ultima vez que se vio la cinta (modo cresta)
_recta = {"n": 0}            # cuadros seguidos con la cinta recta, derecha y centrada (RECTA_RAMPA)
SERIAL_TIMEOUT_S = 0.05
FRAME_NONE_RETRY_SLEEP_S = 0.01
FRAME_NONE_RESTART_THRESHOLD = 30
TELEMETRY_INTERVAL_S = 5.0

# ---- SWITCH PRINCIPAL ----
# True  -> Zero-DCE en det + AGCWD en intermedios  (Pi 5,  ~20 FPS)
# False -> AGCWD en todos los frames               (Pi 4B, ~35 FPS)
USE_ZERODCE  = False
ZERODCE_PATH = "/home/pi/Downloads/AI_enhance/dcenet_int8.tflite"
ZERODCE_GAIN = 1.65
# --------------------------

debugOriginal = False
debugBlack = True
debugGreen = True
debugBlue = False
debugHori = False
record = True
noise_blob_threshold = 16
min_square_size = 200
min_line_size = 1
fixed_angle_value = 0
fixed_angle_active = False
fixed_angle_start_time = 0
estado = 'esperando'
frames_sent = 0
last_tx_telemetry = time.monotonic()

vs = WebcamVideoStream(src=0).start()


def _fijar_camara(esperar=True):
    """CAMARA_WB / CAMARA_EXPO: fija los controles con v4l2-ctl. Sin las variables no hace nada."""
    if not (CAMARA_WB or CAMARA_EXPO):
        return
    import subprocess
    try:
        _fijar_camara_v4l2(subprocess, esperar)
    except Exception as e:   # sin v4l2-ctl o sin camara: sigue en automatico, como antes
        print("[CAMARA] no se pudo fijar la camara: %s" % e)


def _fijar_camara_v4l2(subprocess, esperar):
    ordenes = []
    if CAMARA_EXPO:
        ordenes += ["auto_exposure=1", "exposure_time_absolute=%d" % int(CAMARA_EXPO)]   # primero manual
    if CAMARA_WB:
        ordenes += ["white_balance_automatic=0", "white_balance_temperature=%d" % int(CAMARA_WB)]
    for o in ordenes:
        r = subprocess.run(["v4l2-ctl", "-d", "/dev/video0", "-c", o], capture_output=True, text=True)
        if r.returncode != 0:
            print("[CAMARA] no se pudo aplicar %s: %s" % (o, r.stderr.strip()))
    r = subprocess.run(["v4l2-ctl", "-d", "/dev/video0", "--list-ctrls"], capture_output=True, text=True)
    print("[CAMARA] " + " | ".join(l.split()[0] + "=" + l.split("value=")[1].split()[0]
                                   for l in r.stdout.splitlines()
                                   if "value=" in l and ("exposure" in l or "white_balance" in l)))
    if esperar:
        time.sleep(0.5)          # el sensor tarda unos cuadros en asentarse con los valores nuevos


_fijar_camara()
ser = serial.Serial('/dev/serial0', 115200, timeout=SERIAL_TIMEOUT_S, write_timeout=SERIAL_TIMEOUT_S)
lower_black   = np.array([0, 0, 0])
upper_black   = np.array([90, 90, 90])

VERDE_L_MIN = int(os.environ.get("VERDE_L_MIN", "50"))
VERDE_L_MAX = int(os.environ.get("VERDE_L_MAX", "220"))
VERDE_A_MIN = int(os.environ.get("VERDE_A_MIN", "80"))
VERDE_A_MAX = int(os.environ.get("VERDE_A_MAX", "115"))
VERDE_B_MIN = int(os.environ.get("VERDE_B_MIN", "120"))
VERDE_B_MAX = int(os.environ.get("VERDE_B_MAX", "155"))

lower_green = np.array([120, 90, 110])  # lab
upper_green = np.array([198, 109, 134])
lower_silver_hsv = np.array([79, 16, 46])
upper_silver_hsv = np.array([168, 28, 79])
lower_red1 = np.array([0, 84, 54])  # hsv
upper_red1 = np.array([7, 255, 200])
lower_red2 = np.array([170, 84, 54])  # hsv
upper_red2 = np.array([179, 255, 200])
last_angles   = []

YOLO_IMGSZ  = 256

width, height = 160, 120
print(width, height)

cam_x = width / 2 - 1
cam_y = height - 1

timer_active = False
green_output_duration = 1
green_output_cooldown_duration = 2
green_state_final = 0
timer_start_time = 0
silver_line = False

def clamp_byte(value):
    return max(0, min(255, int(value)))

def send_frame(speed, angle, green_state, silver_line_flag):
    global frames_sent, last_tx_telemetry

    output = bytes([
        SYNC_SPEED, clamp_byte(speed),
        SYNC_ANGLE, clamp_byte(angle + 90),
        SYNC_GREEN_STATE, clamp_byte(green_state),
        SYNC_SILVER_LINE, clamp_byte(int(bool(silver_line_flag))),
    ])
    bytes_written = ser.write(output)
    ser.flush()
    #print(f"[TX] bytes_written={bytes_written} raw={output.hex()} speed={speed} angle={angle} gs={green_state} sl={silver_line_flag}")

    frames_sent += 1
    now = time.monotonic()
    if now - last_tx_telemetry >= TELEMETRY_INTERVAL_S:
        print(f"[TLM] frames_sent={frames_sent} estado={estado}")
        last_tx_telemetry = now

    return output

def stop_teensy_safely(reason):
    try:
        print(f"[SAFE-STOP] {reason}: enviando speed=0 al Teensy")
        send_frame(0, 0, 0, 0)
    except Exception as exc:
        print(f"[SAFE-STOP] no se pudo enviar stop: {exc}")

def restart_video_stream():
    global vs

    try:
        vs.stop()
    except Exception:
        pass

    time.sleep(0.1)
    vs = WebcamVideoStream(src=0).start()
    _fijar_camara(esperar=False)  # al reabrir puede volver a automatico: se fija de nuevo, sin esperar
    return vs

def read_frame_with_recovery(none_count, context):
    frame = vs.read()
    if frame is not None:
        return frame, 0

    none_count += 1
    if none_count == 1 or none_count % 10 == 0:
        print(f"[WARN] {context}: frame None ({none_count})")

    if none_count >= FRAME_NONE_RESTART_THRESHOLD:
        print(f"[WARN] {context}: reiniciando VideoStream tras {FRAME_NONE_RESTART_THRESHOLD} frames vacios")
        restart_video_stream()
        none_count = 0

    time.sleep(FRAME_NONE_RETRY_SLEEP_S)
    return None, none_count

def handle_control_byte(data, context="serial"):
    global estado, _loss_retro_done, _loss_retro_ts
    global _gap_origen_superado, _gap_failsafe
    global _rampa_teensy, _rampa_teensy_ts, _rampa_sube_fin_ts, _rampa_baja_fin_ts

    if not data:
        return None

    if data in (TEENSY_RAMPA_SUBE, TEENSY_RAMPA_BAJA, TEENSY_RAMPA_LLANO):
        nuevo = 1 if data == TEENSY_RAMPA_SUBE else (-1 if data == TEENSY_RAMPA_BAJA else 0)
        if ROI_RAMPA and nuevo != _rampa_teensy:
            print("[ROI-RAMPA] %s: Teensy %s -> angulo %s" %
                  (context, {1: "SUBE", -1: "BAJA", 0: "LLANO"}[nuevo],
                   ("modo " + ROI_RAMPA + (" +CERO" if RAMPA_CERO else " +RECTA" if RECTA_RAMPA else "") +
                    (" +SINRECUP" if RAMPA_SIN_RECUP else ""))
                   if nuevo == 1 else
                   ("como subiendo" + (" +SINRECUP" if BAJADA_SIN_RECUP else ""))
                   if nuevo == -1 and BAJADA_RECTA else
                   ("normal +SINRECUP" if nuevo == -1 and BAJADA_SIN_RECUP else "normal")))
        if _rampa_teensy == 1 and nuevo != 1:
            _rampa_sube_fin_ts = time.monotonic()
        if _rampa_teensy == -1 and nuevo != -1:
            _rampa_baja_fin_ts = time.monotonic()
        _rampa_teensy = nuevo
        _rampa_teensy_ts = time.monotonic()
        return 'rampa'

    if data in (TEENSY_OBST_INICIO, TEENSY_OBST_FIN):
        if data == TEENSY_OBST_INICIO:
            _obst.update(ini=time.monotonic(), fin=0.0, reset=True)
        elif _obst["ini"] > 0:
            _obst["fin"] = time.monotonic()
        if OBST_SIN_RECUP:
            print("[OBST] %s: %s" % (context, "empieza el esquive (0xF5): sin recuperacion"
                                     if data == TEENSY_OBST_INICIO else
                                     "volvio a la cinta (0xF6): sin recuperacion %.1f s mas" % OBST_POST_S))
        return 'obstaculo'

    if data == TEENSY_BOOT:
        print(f"[INFO] {context}: Teensy reseteado -> esperando")
        estado = 'esperando'
        return 'boot'

    if data == TEENSY_STOP:
        estado = 'esperando'
        return 'stop'

    if data == TEENSY_READY:
        if estado in ('esperando', 'evacuacion'):
            estado = 'linea'
            return 'linea'
        return 'ready'

    if data == TEENSY_RETRO_DONE:
        _loss_retro_done = True
        _loss_retro_ts = time.monotonic()
        print(f"[PERDIDA] {context}: retroceso terminado (0xEF), analizando pose nueva")
        return 'retro_done'

    if data == TEENSY_GAP_ORIGIN:
        _gap_origen_superado = True
        print(f"[GAP] {context}: origen superado por encoder (0xEE)")
        return 'gap_origin'

    if data == TEENSY_GAP_TIMEOUT:
        _gap_failsafe = True
        print(f"[SAFE] {context}: Teensy detuvo busqueda GAP por limite (0xF0)")
        return 'gap_timeout'

    if data == TEENSY_PIVOTE_DONE:
        if _cg is not None:
            _cg.pivote_hecho(time.monotonic())
        if COMPLETAR_GIRO:
            print(f"[CG] {context}: pivote terminado (0xED)")
        return 'pivote_done'

    if data == TEENSY_RESCATE:
        print(f"[INFO] {context}: Llego 241 -> entrando a rescate")
        estado = 'rescate'
        return 'rescate'

    if data == TEENSY_RESCATE_DONE:
        if estado == 'rescate':
            estado = 'depositar'
            return 'depositar'
        return 'rescate_done'

    if data == TEENSY_EVACUACION:
        if estado in ('rescate', 'depositar', 'depositar verde'):
            estado = 'evacuacion'
            return 'evacuacion'
        return 'evacuacion_ignored'

    return None

x_com = np.zeros(shape=(height, width))
y_com = np.zeros(shape=(height, width))
for i in range(height):
    for j in range(width):
        x_com[i][j] = (j - cam_x) / (width / 2)
        y_com[i][j] = (cam_y - i) / height

# ---- AGCWD ----
def agcwd(img_bgr, w=0.5):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    v   = hsv[:, :, 2]
    hist = np.bincount(v.ravel(), minlength=256).astype(np.float32)
    hist_min, hist_max = hist.min(), hist.max()
    if hist_max - hist_min < 1e-6:
        return img_bgr
    w_pdf = hist_max * ((hist - hist_min) / (hist_max - hist_min)) ** w
    w_cdf = np.cumsum(w_pdf)
    w_cdf = w_cdf / w_cdf[-1]
    lut = np.array([int(255 * (i / 255.0) ** (1.0 - w_cdf[i]))
                    for i in range(256)], dtype=np.uint8)
    mean_v = float(np.mean(v))
    if mean_v > 120:
        lut = (lut * 0.3 + np.arange(256, dtype=np.float32) * 0.7).astype(np.uint8)
    hsv[:, :, 2] = cv2.LUT(v, lut)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

# ---- inicializar Zero-DCE si hace falta ----
if USE_ZERODCE:
    sys.path.insert(0, '/home/pi/Downloads/AI_enhance')
    from zero_dce import ZeroDCE
    print("Cargando Zero-DCE...")
    _enhancer = ZeroDCE(ZERODCE_PATH, patch_size=(YOLO_IMGSZ, YOLO_IMGSZ), num_threads=2)
    print("Zero-DCE listo.")
ENABLE_ANTIFLASH = True

def anti_flash_preprocess(img_bgr, v_flash=215, s_low=60, compress=0.45):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = s.astype(np.float32)
    v = v.astype(np.float32)

    flash_mask = (v >= v_flash) & (s <= s_low)

    if not np.any(flash_mask):
        return img_bgr

    mask_blur = flash_mask.astype(np.uint8) * 255
    mask_blur = cv2.GaussianBlur(mask_blur, (5,5), 0)
    alpha = mask_blur.astype(np.float32) / 255.0

    v = v * (1 - alpha) + (v_flash + (v - v_flash) * compress) * alpha

    hsv[:, :, 1] = s.astype(np.uint8)
    hsv[:, :, 2] = v.astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

def enhance(img_bgr, use_zerodce=False):
    if use_zerodce:
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        rgb = _enhancer.enhance(rgb, gain=ZERODCE_GAIN)
        out = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    else:
        out = img_bgr
    if ENABLE_ANTIFLASH:
        out = anti_flash_preprocess(out)
    return agcwd(out)

# ---- Inicializar TFLite global + warmup ----
from ai_edge_litert.interpreter import Interpreter as TFLiteInterpreter
print("Usando ai_edge_litert.interpreter")

TFLITE_MODEL_PATH = "/home/iita/Desktop/yolov8n_rescuebot_2026.tflite"
NUM_THREADS = 2

interpreter = TFLiteInterpreter(model_path=TFLITE_MODEL_PATH, num_threads=NUM_THREADS)
interpreter.allocate_tensors()
_input_details  = interpreter.get_input_details()[0]
_output_details = interpreter.get_output_details()[0]
print("TFLite input:", _input_details)
print("TFLite output:", _output_details)
print("TFLite input:", _input_details)
print("TFLite output:", _output_details)

print("Realizando warmup del modelo TFLite...")
_dummy = np.zeros((YOLO_IMGSZ, YOLO_IMGSZ, 3), dtype=np.uint8)
if np.issubdtype(_input_details['dtype'], np.floating):
    _dummy_inp = (_dummy.astype(np.float32) / 255.0)[np.newaxis, ...].astype(_input_details['dtype'])
else:
    _dummy_inp = _dummy[np.newaxis, ...].astype(_input_details['dtype'])
interpreter.set_tensor(_input_details['index'], _dummy_inp)
interpreter.invoke()
_ = interpreter.get_tensor(_output_details['index'])
print("Warmup completado.")

def modo_rescate(evac_mode=False):
    global last_target_box, is_stopped, estado, ser

    input_details  = _input_details
    output_details = _output_details

    last_target_box = None
    stop_rescate    = False

    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerMOSSE_create"):
        print("Legacy MOSSE disponible")
    else:
        print("Legacy MOSSE NO disponible")
    try:
        tr = cv2.legacy.TrackerMOSSE_create() if hasattr(cv2, "legacy") else cv2.TrackerMOSSE_create()
        print("Creado ok:", type(tr))
    except Exception as e:
        print("fallo:", e)

    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["MKL_NUM_THREADS"] = "2"

    CLASS_NAMES = ['negro', 'plateado', 'rojo alto', 'verde_alto']
    IMGSZ       = YOLO_IMGSZ
    DETECT_EVERY = 3
    MAX_QUEUE    = 2
    DRAW_EVERY   = 1

    last_target_box      = None
    CENTER_TOLERANCE_PX  = 8
    STOP_WIDTH_RATIO     = 0.25
    STOP_WIDTH_RATIO_BOX = 0.98
    STOP_EVAC = 0.68
    RESUME_WIDTH_RATIO   = 0.18
    is_stopped           = False

    CLASS_THRESH = {
        0: 0.45,
        1: 0.45,
        2: 0.5,
        3: 0.6
    }

    CLASS_COLORS = {
        0: (0, 0, 0),
        1: (192, 192, 192),
        2: (0, 100, 255),
        3: (0, 255, 100)
    }

    def make_mosse():
        return None

    class CentroidTracker:
        def __init__(self, max_lost=8):
            self.next_object_id = 0
            self.objects  = {}
            self.lost     = {}
            self.meta     = {}
            self.max_lost = max_lost

        def register(self, bbox, cls=0, score=0.0):
            oid = self.next_object_id
            self.next_object_id += 1
            self.objects[oid] = bbox
            self.lost[oid]    = 0
            self.meta[oid]    = {'cls': cls, 'score': score}
            return oid

        def deregister(self, oid):
            if oid in self.objects: del self.objects[oid]
            if oid in self.lost:    del self.lost[oid]
            if oid in self.meta:    del self.meta[oid]

        def update(self, detections):
            bboxes = [d['xyxy'] for d in detections]

            if len(bboxes) == 0:
                remove = []
                for oid in list(self.lost.keys()):
                    self.lost[oid] += 1
                    if self.lost[oid] > self.max_lost:
                        remove.append(oid)
                for oid in remove: self.deregister(oid)
                return [{'id': oid, 'bbox': self.objects[oid], **self.meta[oid]}
                        for oid in self.objects]

            if len(self.objects) == 0:
                for d in detections:
                    self.register(d['xyxy'], d['cls'], d['score'])
                return [{'id': oid, 'bbox': self.objects[oid], **self.meta[oid]}
                        for oid in self.objects]

            object_ids    = list(self.objects.keys())
            object_bboxes = [self.objects[oid] for oid in object_ids]

            def centroid(b):
                x1, y1, x2, y2 = b
                return ((x1+x2)//2, (y1+y2)//2)

            obj_centroids = [centroid(b) for b in object_bboxes]
            det_centroids = [centroid(d) for d in bboxes]

            D = []
            for oc in obj_centroids:
                row = []
                for dc in det_centroids:
                    dx = oc[0]-dc[0]; dy = oc[1]-dc[1]
                    row.append(dx*dx + dy*dy)
                D.append(row)

            matched_obj = set()
            matched_det = set()
            assignments = {}
            triples = []
            for i in range(len(D)):
                for j in range(len(D[0])):
                    triples.append((i, j, D[i][j]))
            triples.sort(key=lambda x: x[2])
            for i, j, _ in triples:
                if i in matched_obj or j in matched_det: continue
                matched_obj.add(i); matched_det.add(j); assignments[i] = j

            for i, j in assignments.items():
                oid = object_ids[i]
                self.objects[oid] = bboxes[j]
                self.meta[oid]    = {'cls': detections[j]['cls'], 'score': detections[j]['score']}
                self.lost[oid]    = 0

            for j in range(len(detections)):
                if j not in matched_det:
                    self.register(bboxes[j], detections[j]['cls'], detections[j]['score'])

            for i in range(len(object_ids)):
                if i not in assignments:
                    oid = object_ids[i]
                    self.lost[oid] += 1
                    if self.lost[oid] > self.max_lost:
                        self.deregister(oid)

            return [{'id': oid, 'bbox': self.objects[oid], **self.meta[oid]}
                    for oid in self.objects]

    frame_q    = queue.Queue(MAX_QUEUE)
    result_q   = queue.Queue(MAX_QUEUE)
    stop_event = threading.Event()

    def scale_box(box_xyxy, src_w, src_h, in_w=IMGSZ, in_h=IMGSZ):
        x1, y1, x2, y2 = box_xyxy
        scale_x = src_w / in_w
        scale_y = src_h / in_h
        return int(x1*scale_x), int(y1*scale_y), int(x2*scale_x), int(y2*scale_y)

    def capture_thread():
        none_count = 0
        while not stop_event.is_set():
            frame, none_count = read_frame_with_recovery(none_count, "rescate-capture")
            if frame is None:
                continue
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            frame_q.put(frame)
        frame_q.put(None)

    def infer_thread():
        frame_idx = 0
        while True:
            try:
                frame = frame_q.get()
                if frame is None:
                    result_q.put(None)
                    break

                h, w  = frame.shape[:2]
                small = cv2.resize(frame, (IMGSZ, IMGSZ))

                if frame_idx % DETECT_EVERY == 0:
                    small = enhance(small, use_zerodce=USE_ZERODCE)
                else:
                    if ENABLE_ANTIFLASH:
                        small = anti_flash_preprocess(small)
                    small = agcwd(small)
                enhanced_frame = cv2.resize(small, (w, h))

                if frame_idx % DETECT_EVERY == 0:
                    img = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                    if np.issubdtype(input_details['dtype'], np.floating):
                        inp = (img.astype(np.float32) / 255.0)[np.newaxis, ...].astype(input_details['dtype'])
                    else:
                        inp = img[np.newaxis, ...].astype(input_details['dtype'])

                    interpreter.set_tensor(input_details['index'], inp)
                    interpreter.invoke()
                    out = interpreter.get_tensor(output_details['index'])[0]

                    detections = []
                    for det in out:
                        x1, y1, x2, y2, score, cls_raw = det
                        score  = float(score)
                        cls_id = int(round(float(cls_raw)))
                        if score < CLASS_THRESH.get(cls_id, 0.5):
                            continue
                        x1 *= IMGSZ; y1 *= IMGSZ; x2 *= IMGSZ; y2 *= IMGSZ
                        sx1, sy1, sx2, sy2 = scale_box((x1, y1, x2, y2), w, h, IMGSZ, IMGSZ)
                        if estado == "rescate":
                            if cls_id in (2, 3): continue
                        if estado == "depositar":
                            if cls_id in (0, 1, 2): continue
                        if estado == "depositar verde":
                            if cls_id in (0, 1, 3): continue
                        if evac_mode:
                            if cls_id in (0, 1): continue  # ignorar pelotas, solo dejar zonas 2 y 3
                        detections.append({'xyxy': (sx1, sy1, sx2, sy2), 'score': score, 'cls': cls_id})

                    result_q.put(('det', enhanced_frame, detections))
                else:
                    result_q.put(('no_det', enhanced_frame, None))

                frame_idx += 1
            except Exception as exc:
                print(f"[ERROR] infer_thread: {exc}")
                stop_event.set()
                result_q.put(None)
                break

    def select_target_from_list(boxes, estado):
        targets = []
        if estado == 'rescate':
            for d in boxes:
                if d['cls'] in (0, 1): targets.append(d)
        if estado == 'depositar':
            for d in boxes:
                if d['cls'] in (3,): targets.append(d)
        if estado == 'depositar verde':
            for d in boxes:
                if d['cls'] in (2,): targets.append(d)
        if estado == 'evacuacion':
            for d in boxes:
                if d['cls'] in (2, 3): targets.append(d)
        if not targets:
            return None
        return targets[0]

    def choose_stable_target(detections, last_target, estado):
        if not detections:
            return None
        if last_target is None:
            return select_target_from_list(detections, estado)
        lx = (last_target['xyxy'][0] + last_target['xyxy'][2]) // 2
        ly = (last_target['xyxy'][1] + last_target['xyxy'][3]) // 2
        best      = None
        best_dist = 1e12
        for d in detections:
            cx   = (d['xyxy'][0] + d['xyxy'][2]) // 2
            cy   = (d['xyxy'][1] + d['xyxy'][3]) // 2
            dist = math.hypot(cx - lx, cy - ly)
            if dist < best_dist:
                best = d
                best_dist = dist
        return best

    serial_stop_evt = threading.Event()
    def serial_monitor_local():
        nonlocal stop_rescate
        global estado
        while not serial_stop_evt.is_set():
            try:
                if ser.in_waiting > 0:
                    data = ser.read()
                    action = handle_control_byte(data, context="serial-monitor")
                    if action in ('boot', 'stop'):
                        print("serial monitor: switch apagado")
                        stop_rescate = True
                        break
                    elif action == 'depositar':
                        print("Llego 248 -> terminar rescate y cambiar a depositar")
                    elif action == 'evacuacion':
                        print("Llego 247 -> entrando a evacuacion")
                        stop_rescate = True
                        break
                    elif action == 'linea':
                        print("Llego 249 -> volviendo a linea")
                        stop_rescate = True
                        break
            except Exception as e:
                print("serial_monitor_local error:", e)
            time.sleep(0.01)

    t_serial_mon = threading.Thread(target=serial_monitor_local, daemon=True)
    t_serial_mon.start()

    def main_loop():
        global last_target_box, is_stopped, estado
        processed = 0
        start     = time.time()

        centroid_tracker = CentroidTracker(max_lost=8)
        last_detections  = []

        while True:
            if stop_rescate:
                print("main_loop: stop_rescate activo -> saliendo de rescate")
                break

            try:
                item = result_q.get(timeout=0.25)
            except queue.Empty:
                continue

            if item is None:
                break

            typ, frame, detections = item

            if typ == 'det':
                last_detections = detections or []
                ct_objs         = centroid_tracker.update(last_detections)
                last_detections = [{'xyxy': o['bbox'], 'cls': o['cls'], 'score': o['score']}
                                   for o in ct_objs]
            else:
                ct_objs         = centroid_tracker.update([])
                last_detections = [{'xyxy': o['bbox'], 'cls': o['cls'], 'score': o['score']}
                                   for o in ct_objs]

            target = choose_stable_target(last_detections, last_target_box, estado)
            last_target_box = target

            green_state = 0
            speed       = 0
            angle       = 0

            if target:
                x1, y1, x2, y2 = target['xyxy']
                cx      = (x1 + x2) // 2
                cy      = (y1 + y2) // 2
                bbox_w  = x2 - x1
                frame_w = frame.shape[1]

                error_x    = cx - (frame_w // 2)
                error_norm = error_x / (frame_w // 2)
                centered   = abs(error_x) < CENTER_TOLERANCE_PX
                width_ratio = bbox_w / float(frame_w)

                cv2.putText(frame, f"w_ratio={width_ratio:.3f}", (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

                if evac_mode:
                    close_enough = width_ratio >= STOP_EVAC
                elif estado == "depositar" or estado == "depositar verde":
                    close_enough = width_ratio >= STOP_WIDTH_RATIO_BOX
                else:
                    close_enough = width_ratio >= STOP_WIDTH_RATIO

                if close_enough:
                    speed = 0
                    angle = 0
                    ball_type = None
                    if target['cls'] == 0:   ball_type = "silver"
                    elif target['cls'] == 1: ball_type = "black"
                    elif target['cls'] == 2: ball_type = "red_zone"
                    elif target['cls'] == 3: ball_type = "green_zone"

                    if ball_type == "silver":       green_state = 6
                    elif ball_type == "black":      green_state = 7
                    elif ball_type == "red_zone":   green_state = 8
                    elif ball_type == "green_zone":
                        green_state = 9
                        if not evac_mode:           # <- agregar esto
                            estado = "depositar verde"

                    if not centered:
                        angle = int(-error_norm * 90)
                        speed = 5

                    if not is_stopped:
                        print(f"[STOP] width_ratio={width_ratio:.3f}, bbox_w={bbox_w}, frame_w={frame_w}")
                    is_stopped = True
                else:
                    is_stopped = False
                    angle = int(-error_norm * 90)
                    speed = int(20 * (1 - abs(error_norm)))
                    speed = min(speed, 20)

                if processed % DRAW_EVERY == 0:
                    color = CLASS_COLORS.get(target['cls'], (0, 255, 255))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                    cv2.line(frame, (frame_w//2, 0), (frame_w//2, frame.shape[0]), (255, 0, 0), 1)
                    cv2.putText(frame,
                                f"{CLASS_NAMES[target['cls']]} {target.get('score',0):.2f} w={bbox_w}",
                                (x1, y1-6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            else:
                speed       = 20
                angle       = 90
                green_state = 0

            # ---- Envio con ACK ----
            output = send_frame(speed, angle, green_state, 0)

            processed += 1
            elapsed = time.time() - start
            fps     = processed / elapsed if elapsed > 0 else 0.0
            modo    = "ZeroDCE+AGCWD" if USE_ZERODCE else "AGCWD"
            cv2.putText(frame, f"FPS: {fps:.2f} [{modo}]", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            if SHOW_DEBUG_WINDOWS:
                cv2.imshow("Optimizado", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    stop_event.set(); break
            else:
                if processed % 30 == 0:
                    print(f"[HEADLESS] FPS ~ {fps:.2f}  detecciones: {len(last_detections)}")

        if SHOW_DEBUG_WINDOWS:
            cv2.destroyAllWindows()

    # ---- lanzar hilos ----
    tcap = threading.Thread(target=capture_thread, daemon=True)
    tinf = threading.Thread(target=infer_thread, daemon=True)
    tcap.start(); tinf.start()
    try:
        main_loop()
    finally:
        stop_event.set()
        serial_stop_evt.set()
        stop_rescate = False

        # --- FIX ZOMBI: Drenar colas para destrabar los hilos ---
        while not frame_q.empty():
            try: frame_q.get_nowait()
            except: pass
        while not result_q.empty():
            try: result_q.get_nowait()
            except: pass
        # --------------------------------------------------------

        tcap.join(timeout=1)
        tinf.join(timeout=1)
        t_serial_mon.join(timeout=0.5)

def main():
    global estado, silver_line, _ult_lado, _frames_sin
    global _recup_armada, _recup_activa, _recup_malos, _recup_buenos
    global _recup_rearme_buenos, _recup_bloqueo_hasta, _recup_ultimo_angle, _recup_inicio_ts, _recup_post_hasta
    global _recup_rumbo_camino_raw, _recup_rumbo_congelado, _recup_rumbo_fuente
    global _loss_camino_frame, _loss_retro_done, _loss_retro_ts, _loss_decision, _loss_curve_sent_ts
    global _gap_activa, _gap_origen_superado, _gap_buenos, _gap_failsafe
    global _term_guard, _term_episode_evidence, _term_veto_logged, _side_check_logged
    global _side_seen_raw_lateral, _curve_latched_decision, _curve_latch_logged

    # -----------------------------------------------
    # LOOP PRINCIPAL
    # -----------------------------------------------
    while True:

        while estado == 'esperando':
            silver_line = False
            if ser.in_waiting > 0:
                data = ser.read()
                handle_control_byte(data, context="esperando")
            time.sleep(FRAME_NONE_RETRY_SLEEP_S)

        while estado == 'rescate':
            modo_rescate()
        while estado == 'evacuacion':
            modo_rescate(evac_mode=True)
        line_none_count = 0
        line_t0 = time.time()
        line_frames = 0

        # Cada entrada al modo linea empieza DESARMADA. Esto evita que quede un
        # episodio viejo vivo al volver de rescate, evacuacion, un reset o un verde.
        _recup_armada = False
        _recup_activa = False
        _recup_malos = 0
        _recup_buenos = 0
        _recup_rearme_buenos = 0
        _recup_bloqueo_hasta = 0.0
        _recup_ultimo_angle = 0.0
        _recup_inicio_ts = 0.0
        _recup_post_hasta = 0.0
        _recup_rumbo_camino_raw = None
        _recup_rumbo_congelado = 0.0
        _recup_rumbo_fuente = "sin-camino"
        _obst.update(ini=0.0, fin=0.0, reset=False)
        _loss_camino_frame = None
        _loss_retro_done = False
        _loss_retro_ts = 0.0
        _loss_decision = None
        _loss_curve_sent_ts = 0.0
        _gap_activa = False
        _gap_origen_superado = False
        _gap_buenos = 0
        _gap_failsafe = False
        _term_episode_evidence = None
        _term_veto_logged = False
        _side_seen_raw_lateral = set()
        _curve_latched_decision = None
        _curve_latch_logged = False
        if _term_guard is not None:
            try:
                _term_guard.reset()
            except Exception:
                pass
        if _camino_shadow is not None:
            try:
                _camino_shadow.reset()
            except Exception as _e:
                print("[RECUP-CAMINO] reset fallo: %s" % _e)
        if _loss_arb is not None:
            _loss_arb.reset_all()
        if _cg is not None:
            _cg.reset()

        _rec_guard.reset(); _ramp_transition.reset()
        print('[RECUP-GUARD] ' + RecoveryGuard.VERSION)
        print('[RAMPA] ' + RAMPA_TRANSICION_VERSION)
        print('[VERDE] ' + VERSION_SOMBRA)

        while estado == 'linea':
            frame, line_none_count = read_frame_with_recovery(line_none_count, "linea")
            if frame is None:
                continue

            frame = cv2.rotate(frame, cv2.ROTATE_180)
            frame_resized = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_NEAREST)

            kernel = np.ones((3, 3), np.uint8)
            lab    = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)

            black_mask = cv2.inRange(frame_resized, lower_black, upper_black)
            black_mask[:60, :] = 0
            x_black = cv2.bitwise_and(x_com, x_com, mask=black_mask)
            x_black *= (1 - y_com)
            y_black = cv2.bitwise_and(y_com, y_com, mask=black_mask)

            green_mask = np.zeros((120, 160), dtype=np.uint8)
            green_mask[80:, :] = cv2.inRange(lab[80:, :, :], lower_green, upper_green)

            cut_line  = np.zeros((120, 160), dtype=np.uint8)
            hsv_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2HSV)
            cut_line[62:, :] = cv2.inRange(frame_resized[62:, :, :], lower_black, upper_black)

            red_mask = cv2.bitwise_or(
                cv2.inRange(hsv_frame, lower_red1, upper_red1),
                cv2.inRange(hsv_frame, lower_red2, upper_red2)
            )
            red_mask[:75, :] = 0
            silver_mask = cv2.inRange(frame_resized, lower_silver_hsv, upper_silver_hsv)
            silver_mask[:75, :] = 0

            green_state = 0
            x_resultant = np.mean(x_black)
            y_resultant = np.mean(y_black)
            angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90
            speed = 40

            # ================= PARCHE IITA =================
            # 1. ROI: recortar en el horizonte real en vez de la fila 60.
            _corte = 60
            if ROI_MODO == "auto":
                _corte = _fila_horizonte(frame_resized)
                if _corte < 60:
                    black_mask = cv2.inRange(frame_resized, lower_black, upper_black)
                    black_mask[:_corte, :] = 0
                    x_black = cv2.bitwise_and(x_com, x_com, mask=black_mask)
                    x_black *= (1 - y_com)
                    y_black = cv2.bitwise_and(y_com, y_com, mask=black_mask)
                    x_resultant = np.mean(x_black)
                    y_resultant = np.mean(y_black)
                    angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90

            _ang_viejo = angle
            _quien = "centroide"
            _r = None

            # 1.b RECORTE DEL ROI. Medido sobre video_4.avi -591 frames
            #     validos, f524-574 fuera por MANUAL_LIFT-, en los 349 frames
            #     donde hoy el firmware pivotea:
            #
            #         ROI_ABAJO=95   ->  |ang| BAJA 13,1 gr  (336 de 349)
            #         ROI_ARRIBA=80  ->  |ang| SUBE  7,9 gr
            #         ROI_ARRIBA=90  ->  |ang| SUBE 12,4 gr
            #         ROI_ARRIBA=40  ->  |ang| BAJA  9,3 gr   <- esto hace ROI=auto
            #
            #     angle = atan2(mean(y_com), mean(x_com*(1-y_com))) - 90, y las
            #     filas lejanas tienen y_com ALTO. Sumar vision lejana empuja el
            #     atan2 hacia 90 y el angulo hacia 0: MAS VISTA ADELANTE = MENOS
            #     GIRO PEDIDO. Por eso recortar abajo -que era la idea- va para
            #     el lado contrario, y la palanca que sube el giro es bajar el
            #     corte de arriba.
            #
            #     Sobre una COPIA: black_mask lo usa el verde para cx_black.
            _subiendo = (bool(ROI_RAMPA) and _rampa_teensy == 1 and
                         (time.monotonic() - _rampa_teensy_ts) <= ROI_RAMPA_VIGENCIA_S)
            _bajando = (bool(ROI_RAMPA) and _rampa_teensy == -1 and
                        (time.monotonic() - _rampa_teensy_ts) <= ROI_RAMPA_VIGENCIA_S)
            _roi_arriba = ROI_ARRIBA
            if _subiendo and ROI_RAMPA == "corte":
                _roi_arriba = max(ROI_ARRIBA, ROI_RAMPA_CORTE)   # subiendo: sin el paisaje
            if _roi_arriba != 60 or ROI_ABAJO < 120:
                _m_ang = cv2.inRange(frame_resized, lower_black, upper_black)
                _m_ang[:_roi_arriba, :] = 0
                if ROI_ABAJO < 120:
                    _m_ang[ROI_ABAJO:, :] = 0
                if np.count_nonzero(_m_ang):
                    _xb = cv2.bitwise_and(x_com, x_com, mask=_m_ang)
                    _xb = _xb * (1 - y_com)
                    _yb = cv2.bitwise_and(y_com, y_com, mask=_m_ang)
                    angle = (math.atan2(float(np.mean(_yb)),
                                        float(np.mean(_xb))) / math.pi * 180) - 90
                    _quien = "rampa-corte" if _roi_arriba != ROI_ARRIBA else "recorte"
                else:
                    # banda vacia: atan2(0,0) daria -90, un volantazo salido de
                    # la nada. Se deja el angulo de siempre.
                    _quien = "sin_banda"
            if (_subiendo or (BAJADA_RECTA and _bajando)) and ROI_RAMPA in ("linea", "cresta"):
                # Solo el negro conectado con el robot: el paisaje suelto no entra. Con `cresta`,
                # antes se saca la franja de la sala pegada a la punta de la cinta. Si no queda
                # linea (menos de AREA_MIN_LINEA px), se deja el angulo de siempre.
                _base = black_mask
                _fila_cresta = 60
                if ROI_RAMPA == "cresta" and _subiendo:
                    _fila_cresta = _corte_paisaje(black_mask)
                    if RAMPA_SIN_RECUP and CRESTA_HOLD_S > 0:
                        _ahora_ch = time.monotonic()
                        _det = _cresta.setdefault("det", [])
                        _det[:] = [x for x in _det if _ahora_ch - x <= 1.0]
                        if _fila_cresta > 60:
                            _cresta["fila"] = _fila_cresta
                            _cresta["fila_ts"] = _ahora_ch
                            _det.append(_ahora_ch)
                        elif (_ahora_ch - _cresta.get("fila_ts", -1e9) <= CRESTA_HOLD_S and
                              len(_det) >= CRESTA_HOLD_MIN):
                            _fila_cresta = _cresta["fila"]
                    if _fila_cresta > 60:
                        _base = black_mask.copy()
                        _base[:_fila_cresta, :] = 0
                _m_lin = _solo_mi_linea(_base)
                if _fila_cresta > 60:
                    # Cresta: con la linea corta solo se centra (ver CRESTA_K). Sin cinta, derecho.
                    _recta["n"] = 0
                    _e_cr = _error_lateral(_m_lin, _fila_cresta, 120) if np.count_nonzero(_m_lin) else None
                    if _e_cr is not None:
                        angle = -CRESTA_K * _e_cr
                        _quien = "rampa-centra%d" % _fila_cresta
                    else:
                        angle = 0.0
                        _quien = "rampa-cresta-recto"
                elif np.count_nonzero(_m_lin):
                    _xb = cv2.bitwise_and(x_com, x_com, mask=_m_lin)
                    _xb = _xb * (1 - y_com)
                    _yb = cv2.bitwise_and(y_com, y_com, mask=_m_lin)
                    angle = (math.atan2(float(np.mean(_yb)),
                                        float(np.mean(_xb))) / math.pi * 180) - 90
                    _quien = "rampa-linea"
                    _corta = False
                    if RAMPA_SIN_RECUP:
                        _fl = np.flatnonzero(_m_lin.any(axis=1))
                        _corta = (_fl.size > 0 and
                                  _m_lin.shape[0] - int(_fl[0]) < RAMPA_CORTA_FILAS and
                                  not (_m_lin[:, :2].any() or _m_lin[:, -2:].any()))
                    if RAMPA_CERO:
                        angle = 0.0
                        _quien = "rampa-cero"
                    elif _corta:
                        angle = 0.0
                        _quien = "rampa-corta-recto"
                        _recta["n"] = 0
                    elif RECTA_RAMPA:
                        _fr = _forma_recta(_m_lin)
                        _pend = None
                        if _fr is not None:
                            _pend = _fr["pendiente"]
                            if RECTA_PERSPECTIVA:
                                _pend -= (_fr["abajo"] * _fr["mitad"]) / max(1.0, _fr["fila_cerca"] - RECTA_VH)
                        _es_recta = (_fr is not None and _fr["desvio"] < RECTA_DESVIO_PX and
                                     _fr["alto"] >= RECTA_ALTO_MIN and
                                     abs(_pend) < RECTA_PENDIENTE and
                                     abs(_fr["abajo"]) < RECTA_ABAJO)
                        _recta["n"] = _recta["n"] + 1 if _es_recta else 0
                        if _recta["n"] >= RECTA_CUADROS:
                            angle = (RECTA_KH * math.degrees(math.atan(_pend)) -
                                     RECTA_KE * _fr["abajo"])
                            _quien = "rampa-recta"
                else:
                    _recta["n"] = 0
                if not _subiendo and _quien.startswith("rampa-"):
                    _quien = "bajada-" + _quien[len("rampa-"):]
            else:
                _recta["n"] = 0

            # Solo el fallback de una subida recta ya confirmada; colores se procesan despues.
            if ROI_RAMPA == "cresta" and CTRL == "atan2":
                _rt = _ramp_transition.step(_subiendo, _quien, _m_lin if _subiendo else black_mask,
                                           time.monotonic())
                if _rt is not None:
                    angle, _quien = _rt["angle"], _rt["who"]

            # 2. CONTROL: dos terminos de ganancia constante.
            if CTRL == "lineal":
                _al = _angulo_lineal(black_mask, _corte)
                if _al is not None:
                    angle = _al
                    _quien = "lineal"

            # 3. MEDICION DE LINEA PARA RECUPERACION.
            #
            # IMPORTANTE: aca NO se manda GS=4. Un solo frame vacio puede aparecer
            # al arrancar, durante un giro verde o por ruido. La decision se toma
            # al FINAL del frame, despues de verde/rojo/plateado, con antirrebote.
            _linea_recup_ok = True
            if RECUP:
                _mm = _solo_mi_linea(black_mask)
                _e = _error_lateral(_mm, 100, 120)
                if _e is None:
                    _e = _error_lateral(_mm, _corte, 120)

                # Esta es la condicion que dispara recovery: hay (o no hay) una
                # componente de linea realmente conectada con la zona del robot.
                # NO usamos planner.ok para disparar: un "trazo corto" del planner
                # no significa necesariamente que la linea haya desaparecido.
                _linea_recup_ok = (_e is not None)

                # CRESTA (solo ROI_RAMPA=cresta): la cinta se pierde bajo la trompa al pasar el borde.
                # Cruzar DERECHO sin disparar la recuperacion, como mucho CRESTA_RECTO_MAX_S desde la
                # ultima vez que se vio la cinta. Pasado ese tiempo, todo sigue como siempre.
                if ROI_RAMPA == "cresta":
                    _now_cr = time.monotonic()
                    _vent_cr = _subiendo or (_rampa_sube_fin_ts > 0 and
                                             _now_cr - _rampa_sube_fin_ts <= CRESTA_POST_S)
                    if _linea_recup_ok:
                        _cresta["ult_linea"] = _now_cr
                    elif (_vent_cr and _cresta["ult_linea"] > 0 and
                          _now_cr - _cresta["ult_linea"] <= CRESTA_RECTO_MAX_S):
                        _linea_recup_ok = True
                        angle = 0.0
                        _quien = "rampa-cresta-recto"

                # SUBIENDO: nunca recuperacion ni gap. Sin cinta, derecho (ver RAMPA_SIN_RECUP).
                _vent_sub = _subiendo or (_rampa_sube_fin_ts > 0 and
                                          time.monotonic() - _rampa_sube_fin_ts <= CRESTA_POST_S)
                if RAMPA_SIN_RECUP and _vent_sub and not _linea_recup_ok:
                    _linea_recup_ok = True
                    angle = 0.0
                    _quien = "rampa-sin-recup"

                # BAJANDO: tampoco recuperacion ni gap. Sin cinta, derecho (ver BAJADA_SIN_RECUP).
                _vent_baj = _bajando or (_rampa_baja_fin_ts > 0 and
                                         time.monotonic() - _rampa_baja_fin_ts <= BAJADA_POST_S)
                if BAJADA_SIN_RECUP and _vent_baj and not _linea_recup_ok:
                    _linea_recup_ok = True
                    angle = 0.0
                    _quien = "bajada-sin-recup"

                # ESQUIVANDO EL OBSTACULO y hasta OBST_POST_S despues: tampoco (ver OBST_SIN_RECUP).
                _now_ob = time.monotonic()
                _vent_obs = OBST_SIN_RECUP and _obst["ini"] > 0 and (
                    (_obst["fin"] == 0.0 and _now_ob - _obst["ini"] <= OBST_MAX_S) or
                    (_obst["fin"] > 0 and _now_ob - _obst["fin"] <= OBST_POST_S))
                if _vent_obs and not _linea_recup_ok:
                    _linea_recup_ok = True
                    angle = 0.0
                    _quien = "obstaculo-sin-recup"

                if _e is not None:
                    _frames_sin = 0
                    if abs(_e) > 0.15:
                        _ult_lado = 1.0 if _e > 0 else -1.0
                else:
                    _frames_sin += 1

                    # Mantener el comportamiento viejo si se usa RECUP=1 pero
                    # RETROCEDER=0. El nuevo arbitro GS4 solo corre con RETROCEDER=1.
                    if (not RETROCEDER) and _ult_lado != 0.0:
                        _k = min(1.0, 0.4 + 0.1 * _frames_sin)
                        angle = -_ult_lado * RECUP_ANG * _k
                        _quien = "buscando"

            # 4. PLANNER, si se pidio.
            if USAR_PLANNER:
                try:
                    _r = _seguidor.paso(frame_resized, ya_procesado=True)
                    if not MODO_HIBRIDO:
                        angle = _r["angle_filtrado"]
                        _quien = "planner"
                    elif _r.get("ok") and abs(_ang_viejo) >= SATURA_DESDE:
                        angle = _r["angle_filtrado"]
                        _quien = "planner*"
                except Exception as _e2:
                    print("[PLANNER] error, sigo con el centroide: %s" % _e2)
                    _r = None
            # ==============================================

            # 5. CAMINO+MONO SHADOW PARA RECUPERACION.
            # Corre en paralelo y SOLO alimenta memoria de rumbo. No toca `angle`.
            # El heading de CAMINO es DER+; la conversion al signo historico del
            # protocolo se hace unicamente al disparar GS=4.
            _loss_camino_frame = None
            if _camino_shadow is not None:
                try:
                    _loss_camino_frame = _camino_shadow.paso(frame_resized)
                except Exception as _e3:
                    # Si CAMINO falla, no se inventa una clasificacion nueva.
                    # El fallback conserva el recovery historico si el arbitro
                    # no esta disponible; durante un episodio ya iniciado se frena.
                    print("[RECUP-CAMINO] error: %s; shadow apagado" % _e3)
                    globals()["_camino_shadow"] = None
                    _loss_camino_frame = None


            if np.sum(green_mask) > min_square_size * 255:
                green_pixels = np.amax(green_mask, axis=0)
                greenIndices = np.where(green_pixels == np.max(green_pixels))
                leftIndex    = greenIndices[0][0]
                rightIndex   = greenIndices[0][-1]
                slicedGreen  = frame_resized[60:90, leftIndex:rightIndex + 1, :]
                greenCentroidX = (rightIndex + leftIndex) / 2
                slicedBlackMaskAboveGreen = black_mask[60:90, leftIndex:rightIndex + 1]
                blackM = cv2.moments(black_mask[90:, :])

                if ENABLE_CX_BLACK_GUARD:
                    cx_black = None
                    if np.sum(black_mask[90:, :]) and blackM["m00"] != 0:
                        cx_black = int(blackM["m10"] / blackM["m00"])
                    valid_green_reference = cx_black is not None
                else:
                    if np.sum(black_mask[90:, :]):
                        cx_black = int(blackM["m10"] / blackM["m00"])
                    valid_green_reference = True

                if valid_green_reference and (np.sum(slicedBlackMaskAboveGreen) / (255 * 30 * (rightIndex - leftIndex))) > 0.32:
                    greenSquare = False
                    filtered_green_mask = cv2.erode(green_mask, kernel, iterations=1)
                    filtered_green_mask = cv2.dilate(filtered_green_mask, kernel, iterations=2)
                    green_contours, hierarchy = cv2.findContours(filtered_green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    if len(green_contours) > 1 and cx_black > leftIndex and cx_black < rightIndex and np.sum(green_mask) > (FACTOR_DOBLE * min_square_size * 255):
                        green_state = 3
                    elif greenCentroidX < cx_black:
                        green_state = 1
                    else:
                        green_state = 2
                else:
                    greenSquare = False
                    green_state = 0
            else:
                greenSquare = False
                green_state = 0

            # Respaldo oscuro: conserva toda decision del detector principal.
            if green_state == 0:
                _gs_oscuro, _mask_oscuro = detectar_verde_oscuro(
                    lab, black_mask, lower_green, upper_green, min_square_size, FACTOR_DOBLE)
                if _gs_oscuro:
                    green_state = _gs_oscuro
                    green_mask = _mask_oscuro

            # Sombra profunda: solo cuando los dos detectores probados no deciden.
            if green_state == 0:
                _gs_sombra, _mask_sombra = detectar_verde_sombra(
                    lab, black_mask, lower_green, upper_green, min_square_size, FACTOR_DOBLE)
                if _gs_sombra:
                    green_state, green_mask = _gs_sombra, _mask_sombra
                    print("[VERDE-SOMBRA] gs=%d px=%d" % (green_state, np.count_nonzero(green_mask)))

            if (not RECUP) and np.sum(black_mask) < min_line_size:
                angle = 0

            silver_contours, _ = cv2.findContours(silver_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            silver_line = False
            for contour in silver_contours:
                area = cv2.contourArea(contour)
                if area > 50:
                    silver_line = True
                    break

            red_line = False
            double_red_line = False

            red_mask_zone = red_mask.copy()
            red_mask_zone[:60, :] = 0  # ignorar parte superior

            row_sum = np.sum(red_mask_zone, axis=1)  # shape (120,)

            RED_ROW_THRESHOLD = 1500  # ajustar segun camara
            red_rows = row_sum > RED_ROW_THRESHOLD

            # Encontrar grupos de filas rojas consecutivas (cada grupo = una linea)
            in_band = False
            red_bands = 0
            for val in red_rows:
                if val and not in_band:
                    red_bands += 1
                    in_band = True
                elif not val:
                    in_band = False

            red_line = red_bands >= 1
            double_red_line = red_bands >= 2

            # COLOR DE CAMARA = DEBUG SOLAMENTE.
            # La autoridad de ROJO y PLATEADO es EXCLUSIVAMENTE el APDS de Teensy.
            # Esto es intencional: al aire libre blanco y plateado pueden verse
            # practicamente iguales en camara. No convertir red_line/silver_line
            # en acciones ni en bloqueos de recovery.
            silver_line = False

            # ================================================================
            # ARBITRO FINAL DE RECUPERACION (ANTI FALSOS POSITIVOS)
            #
            # GS=4 solo puede nacer de:
            #   linea estable -> 3 frames consecutivos realmente sin linea.
            #
            # Nunca nace:
            #   - al iniciar;
            #   - durante/despues inmediato de un verde;
            #   - por rojo/plateado;
            #   - por un solo frame malo;
            #   - otra vez mientras el mismo episodio sigue activo.
            # ================================================================
            if RECUP and RETROCEDER:
                _now_rec = time.monotonic()
                if not _recup_activa and not _gap_activa and green_state == 0:
                    _rec_guard.observe(_mm)

                # Guardar exactamente el ultimo comando normal confiable.
                if _linea_recup_ok and not _gap_activa:
                    try:
                        _recup_ultimo_angle = float(angle)
                    except (TypeError, ValueError):
                        pass

                # Verdes conservan prioridad completa y comportamiento congelado.
                _marca_prioritaria = green_state in (1, 2, 3)
                if OBST_SIN_RECUP and _obst["reset"]:
                    _obst["reset"] = False
                    _marca_prioritaria = True
                if _marca_prioritaria:
                    _rec_guard.reset(); _ramp_transition.reset()
                    _recup_activa = False
                    _recup_armada = False
                    _recup_malos = 0
                    _recup_buenos = 0
                    _recup_rearme_buenos = 0
                    _loss_retro_done = False
                    _loss_retro_ts = 0.0
                    _loss_decision = None
                    _loss_curve_sent_ts = 0.0
                    _gap_activa = False
                    _gap_origen_superado = False
                    _gap_buenos = 0
                    if _loss_arb is not None:
                        _loss_arb.clear_episode()
                    _term_episode_evidence = None
                    _term_veto_logged = False
                    _side_seen_raw_lateral = set()
                    _curve_latched_decision = None
                    _curve_latch_logged = False
                    if _term_guard is not None:
                        try:
                            _term_guard.reset()
                        except Exception:
                            pass

                    if green_state == 3:
                        _recup_bloqueo_hasta = max(
                            _recup_bloqueo_hasta,
                            _now_rec + RECUP_BLOQUEO_DOBLE_S,
                        )
                    else:
                        _recup_bloqueo_hasta = max(
                            _recup_bloqueo_hasta,
                            _now_rec + RECUP_BLOQUEO_VERDE_S,
                        )

                elif _gap_failsafe:
                    # Fail-safe persistente: una sola trama GS19 no alcanza, porque
                    # en el frame siguiente GS0 reanudaria case 7. Se sostiene STOP
                    # hasta reset/cambio de estado fisico.
                    green_state = GS_PERDIDA_FAILSAFE
                    angle = 0.0
                    _quien = "perdida-failsafe-persistente"

                elif _gap_activa:
                    # GAP se conduce RECTO en Teensy. La camara solo decide cuando
                    # reaparecio NUESTRA componente negra conectada.
                    green_state = GS_GAP_BUSQUEDA
                    angle = 0.0
                    _quien = "gap-busca-negro"

                    if _gap_failsafe:
                        green_state = GS_PERDIDA_FAILSAFE
                        angle = 0.0
                        _quien = "gap-failsafe"
                    else:
                        # Antes del ACK 0xEE, una linea conectada puede ser la linea
                        # vieja a la que volvimos con los 400 ms de retroceso.
                        if _gap_origen_superado and _linea_recup_ok:
                            _gap_buenos += 1
                        else:
                            _gap_buenos = 0

                        if _gap_buenos >= GAP_RECAPTURA_FRAMES:
                            print("[GAP] linea negra conectada recuperada -> control normal")
                            _gap_activa = False
                            _gap_origen_superado = False
                            _gap_buenos = 0
                            _recup_activa = False
                            _recup_armada = False
                            _recup_malos = 0
                            _recup_rearme_buenos = 0
                            _recup_post_hasta = 0.0
                            _recup_bloqueo_hasta = max(
                                _recup_bloqueo_hasta,
                                _now_rec + GAP_REARME_BLOQUEO_S,
                            )
                            _loss_retro_done = False
                            _loss_retro_ts = 0.0
                            _loss_decision = None
                            _loss_curve_sent_ts = 0.0
                            _gap_failsafe = False
                            if _loss_arb is not None:
                                _loss_arb.reset_all()
                            _term_episode_evidence = None
                            _term_veto_logged = False
                            _side_seen_raw_lateral = set()
                            _curve_latched_decision = None
                            _curve_latch_logged = False
                            if _term_guard is not None:
                                try:
                                    _term_guard.reset()
                                except Exception:
                                    pass
                            green_state = 0
                            _quien = "gap-recuperado"

                elif _recup_activa:
                    # Fallback: si el nuevo arbitro no cargo, conservar exactamente
                    # la politica historica de recovery que ya funciona.
                    if _loss_arb is None:
                        _recup_edad = _now_rec - _recup_inicio_ts if _recup_inicio_ts else 0.0
                        if _recup_edad >= RECUP_SOLTAR_CONTROL_S:
                            _recup_activa = False
                            _recup_armada = False
                            _recup_malos = 0
                            _recup_buenos = 0
                            _recup_rearme_buenos = 0
                            _recup_inicio_ts = 0.0
                            _recup_post_hasta = _now_rec + RECUP_POST_NORMAL_S
                            _recup_bloqueo_hasta = max(_recup_bloqueo_hasta, _recup_post_hasta)
                            green_state = 0
                            if not _linea_recup_ok:
                                angle = 0.0
                                _quien = "recup-post-recto"
                        else:
                            green_state = GS_LINEA_PERDIDA
                            angle = 0.0
                            if _camino_shadow is not None:
                                try:
                                    _ch = _camino_shadow.ultimo(RECUP_CAMINO_REANALISIS_MAX_AGE_S)
                                    if _ch.get("vigente") and _ch.get("heading") is not None:
                                        angle = max(-90.0, min(90.0, -float(_ch["heading"])))
                                        _quien = "recup-fallback-camino"
                                except Exception:
                                    pass
                    else:
                        # NUEVA INTEGRACION. GS4 hace el MISMO retroceso de 400 ms.
                        # Teensy manda 0xEF al terminar; solo desde ahi se clasifican
                        # frames de la pose nueva.
                        green_state = GS_LINEA_PERDIDA
                        angle = 0.0

                        if not _loss_retro_done:
                            _quien = "recup-espera-retro-ack"
                        else:
                            # REV3: una CURVA ya comprometida queda congelada. En la
                            # corrida fisica el overlay recup-CURVA llego a cambiar de signo
                            # mientras pivotaba porque decide() seguia corriendo sobre un deque
                            # deslizante. Eso puede sacar al robot hacia el lado contrario.
                            if _curve_latched_decision is None:
                                if _loss_camino_frame is not None and _camino_shadow is not None:
                                    try:
                                        _obs_post = _loss_arb.observe_post(
                                            _loss_camino_frame,
                                            _camino_shadow.ultimo_resultado,
                                            now=_now_rec,
                                        )
                                        if isinstance(_obs_post, dict):
                                            _rawp = _obs_post.get("raw")
                                            if _rawp == "LATERAL_DER":
                                                _side_seen_raw_lateral.add(1)
                                            elif _rawp == "LATERAL_IZQ":
                                                _side_seen_raw_lateral.add(-1)
                                    except Exception as _ea:
                                        print("[PERDIDA] observe_post fallo: %s" % _ea)
                                if PALILLOS_RECTA > 0:
                                    if _palillo["ts"] != _loss_retro_ts:
                                        _palillo["ts"] = _loss_retro_ts
                                        _palillo["n"] = 0
                                    if _cinta_partida(frame_resized):
                                        _palillo["n"] += 1
                                _dec = _loss_arb.decide(now=_now_rec)
                            else:
                                _dec = dict(_curve_latched_decision)
                            _loss_decision = _dec

                            # V6.6 FIELD: NO re-clasifica curvas. Solo puede vetar
                            # dos fallbacks V6.5 basados en memoria lateral vieja,
                            # usando evidencia congelada ANTES de la perdida.
                            if _term_guard is not None and _term_episode_evidence is not None:
                                try:
                                    _v65_dec = _dec
                                    _dec2, _would_veto, _applied_veto = apply_optional_veto(
                                        _v65_dec, _term_episode_evidence, authority=TERM_HARD_AUTH)
                                    if _would_veto and not _term_veto_logged:
                                        print("[TERM-HARD] advance=%s last_ymin=%s side_recent=%s n=%s | V65=%s | %s" % (
                                            _term_episode_evidence.get("advance"),
                                            _term_episode_evidence.get("last_ymin"),
                                            _term_episode_evidence.get("side_recent"),
                                            _term_episode_evidence.get("n"),
                                            _v65_dec.get("reason"),
                                            "VETO_APLICADO" if _applied_veto else "WOULD_VETO_SHADOW"))
                                        _term_veto_logged = True
                                    _dec = _dec2
                                    _loss_decision = _dec
                                except Exception as _te:
                                    print("[TERM-HARD] error; conserva V6.5: %s" % _te)

                            # REV3 SIDE_CHECK: conserva el criterio REV2 sobre los
                            # falsos +/-90 MAS RECIENTES, pero no deja que el deque olvide
                            # un LATERAL real ya visto del lado de la memoria.
                            if (_curve_latched_decision is None and _term_guard is not None and
                                    (SIDE_CHECK_SHADOW or SIDE_CHECK_AUTH) and _dec.get("kind") == "CURVA"):
                                try:
                                    _mem_side = int(_dec.get("side") or 0)
                                    if _mem_side and _mem_side in _side_seen_raw_lateral:
                                        _dec_s = _dec; _would_flip = False; _applied_flip = False
                                        _ev = {"signo": 0, "n_same": 0, "n_opp": 0, "votes": []}
                                        if not _side_check_logged:
                                            print("[SIDE-CHECK] BLOQUEADO por LATERAL real previo lado=%s vistos=%s" %
                                                  (_mem_side, sorted(_side_seen_raw_lateral)))
                                            _side_check_logged = True
                                    else:
                                        _dec_s, _would_flip, _applied_flip, _ev = apply_side_check(
                                            _dec, list(_loss_arb.post), authority=SIDE_CHECK_AUTH)
                                        if _would_flip and not _side_check_logged:
                                            print("[SIDE-CHECK] memoria=%s post_signo=%s n=%s/%s votos=%s | V65=%s | %s" % (
                                                _dec.get("side"), (_ev or {}).get("signo"), (_ev or {}).get("n_same"),
                                                (_ev or {}).get("n_opp"), (_ev or {}).get("votes"), _dec.get("reason"),
                                                "FLIP_APLICADO" if _applied_flip else "WOULD_FLIP_SHADOW"))
                                            _side_check_logged = True
                                    _dec = _dec_s
                                    _loss_decision = _dec
                                except Exception as _se:
                                    print("[SIDE-CHECK] error; conserva V6.5: %s" % _se)

                            # PALILLOS_RECTA: la cinta partida por un palillo -> derecho, como un gap.
                            if (PALILLOS_RECTA > 0 and _curve_latched_decision is None and
                                    _dec.get("kind") != "RECTA" and _palillo["ts"] == _loss_retro_ts and
                                    _palillo["n"] >= PALILLOS_RECTA):
                                print("[PALILLO] cinta partida en %d cuadros: %s -> RECTA" % (
                                    _palillo["n"], _dec.get("kind")))
                                _dec = dict(kind="RECTA", side=0, heading=0.0, reason="palillo: cinta partida")
                                _loss_decision = _dec

                            # Contrastar la decision final con evidencia previa al retroceso.
                            if _curve_latched_decision is None:
                                _dec, _guard_change = _rec_guard.decide(
                                    _dec, _term_episode_evidence,
                                    max(0.0, _now_rec - _loss_retro_ts) if _loss_retro_ts else 0.0,
                                    PERDIDA_AMBIGUA_MAX_S)
                                _loss_decision = _dec
                                if _guard_change:
                                    print("[RECUP-GUARD] %s side=%s heading=%s" %
                                          (_guard_change, _dec.get("side"), _dec.get("heading")))

                            # REV3: despues de TERM_HARD + SIDE_CHECK, congelar la primera
                            # decision final de CURVA hasta que termine el recovery.
                            if (_curve_latched_decision is None and CURVE_LATCH and
                                    _dec.get("kind") == "CURVA"):
                                _curve_latched_decision = dict(_dec)
                                if not _curve_latch_logged:
                                    print("[CURVE-LATCH] side=%s heading=%s reason=%s" % (
                                        _curve_latched_decision.get("side"),
                                        _curve_latched_decision.get("heading"),
                                        _curve_latched_decision.get("reason")))
                                    _curve_latch_logged = True

                            if _dec["kind"] == "CURVA":
                                # CAMINO usa DER+, protocolo historico usa derecha negativa.
                                _h = float(_dec.get("heading") or 0.0)
                                angle = max(-90.0, min(90.0, -_h))
                                _recup_rumbo_camino_raw = _h
                                _recup_rumbo_congelado = angle
                                _recup_rumbo_fuente = _dec.get("reason", "curva")
                                _quien = "recup-CURVA"
                                if _loss_curve_sent_ts <= 0.0:
                                    _loss_curve_sent_ts = _now_rec
                                # Soltar con el MISMO reloj de 1.35 s del backup, pero
                                # nunca en el mismo frame en que se tomo por primera
                                # vez la decision: Teensy debe recibir al menos una
                                # trama GS4 con el heading lateral.
                                _recup_edad = _now_rec - _recup_inicio_ts if _recup_inicio_ts else 0.0
                                if (_recup_edad >= RECUP_SOLTAR_CONTROL_S and
                                        (_now_rec - _loss_curve_sent_ts) >= 0.04):
                                    _recup_activa = False
                                    _recup_armada = False
                                    _recup_malos = 0
                                    _recup_rearme_buenos = 0
                                    _recup_inicio_ts = 0.0
                                    _curve_latched_decision = None
                                    _curve_latch_logged = False
                                    _side_seen_raw_lateral = set()
                                    _recup_post_hasta = _now_rec + RECUP_POST_NORMAL_S
                                    _recup_bloqueo_hasta = max(_recup_bloqueo_hasta, _recup_post_hasta)
                                    green_state = 0
                                    if not _linea_recup_ok:
                                        angle = 0.0
                                    print("[PERDIDA] CURVA %s -> recovery congelado" %
                                          ("DER" if _dec.get("side", 0) > 0 else "IZQ"))
                                    _rec_guard.begin_finish(int(_dec.get("side") or 0), _now_rec)
                                    if _cg is not None:
                                        _cg.soltar(int(_dec.get("side") or 0), _now_rec)

                            elif _dec["kind"] == "RECTA":
                                # No pivotar. Teensy empieza busqueda recta; APDS sigue
                                # leyendo rojo/plateado y puede interrumpir en cualquier momento.
                                print("[PERDIDA] RECTA -> busqueda GAP/camara; APDS vigila colores")
                                _gap_activa = True
                                _gap_origen_superado = False
                                _gap_buenos = 0
                                _gap_failsafe = False
                                _loss_curve_sent_ts = 0.0
                                _curve_latched_decision = None
                                _curve_latch_logged = False
                                _side_seen_raw_lateral = set()
                                _recup_activa = False
                                _recup_armada = False
                                _recup_malos = 0
                                green_state = GS_GAP_BUSQUEDA
                                angle = 0.0
                                _quien = "gap-inicio"

                            else:
                                # Ambigua = quieto y observar mas, nunca 30 cm recto ni
                                # pivote inventado. Si no se resuelve, fail-safe STOP.
                                _quien = "recup-AMBIGUA"
                                if (AMBIGUA_GAP and _loss_retro_ts > 0.0 and
                                        (_now_rec - _loss_retro_ts) >= PERDIDA_AMBIGUA_MAX_S):
                                    # Igual que la rama RECTA de arriba.
                                    print("[PERDIDA] AMBIGUA sin resolver -> busqueda GAP derecho (AMBIGUA_GAP)")
                                    _gap_activa = True
                                    _gap_origen_superado = False
                                    _gap_buenos = 0
                                    _gap_failsafe = False
                                    _loss_curve_sent_ts = 0.0
                                    _curve_latched_decision = None
                                    _curve_latch_logged = False
                                    _side_seen_raw_lateral = set()
                                    _recup_activa = False
                                    _recup_armada = False
                                    _recup_malos = 0
                                    green_state = GS_GAP_BUSQUEDA
                                    angle = 0.0
                                    _quien = "gap-inicio"
                                elif (_loss_retro_ts > 0.0 and
                                        (_now_rec - _loss_retro_ts) >= PERDIDA_AMBIGUA_MAX_S):
                                    print("[SAFE] perdida sigue AMBIGUA -> STOP, no adivinar")
                                    green_state = GS_PERDIDA_FAILSAFE
                                    angle = 0.0
                                    _recup_activa = False
                                    _recup_armada = False
                                    _recup_malos = 0
                                    _curve_latched_decision = None
                                    _curve_latch_logged = False
                                    _side_seen_raw_lateral = set()
                                    _gap_failsafe = True

                else:
                    # Seguimiento normal: el clasificador observa pero NO controla.
                    # Se actualiza solo con linea conectada y sin verde.
                    if (_linea_recup_ok and green_state == 0 and _term_guard is not None):
                        try:
                            _term_guard.observe_connected_mask(_mm, full_mask=black_mask, now=_now_rec)
                        except Exception:
                            pass

                    if (_linea_recup_ok and green_state == 0 and
                            _loss_arb is not None and _loss_camino_frame is not None and
                            _camino_shadow is not None):
                        try:
                            _loss_arb.observe_normal(
                                _loss_camino_frame,
                                _camino_shadow.ultimo_resultado,
                                now=_now_rec,
                            )
                        except Exception as _eo:
                            print("[PERDIDA] observe_normal fallo: %s" % _eo)

                    if _now_rec < _recup_bloqueo_hasta:
                        _recup_armada = False
                        _recup_malos = 0
                        _recup_rearme_buenos = 0
                        if (SAFE_NO_LINE_GUARD and not _linea_recup_ok and
                                np.count_nonzero(black_mask) == 0):
                            # REV: SOLO mascara totalmente vacia. Ahi atan2(0,0)-90 = -90
                            # es un artefacto. Si hay negro no conectado (post-verde,
                            # linea lejana), se conserva el steer de V6.5 hacia ese negro.
                            angle = 0.0
                            _quien = "v66-bloqueo-mascara-vacia-recto"
                        elif _now_rec < _recup_post_hasta and not _linea_recup_ok:
                            angle = 0.0
                            _quien = "recup-cooldown-recto"
                        # COMPLETAR_GIRO: si al terminar el pivote la cinta quedo DE FRENTE,
                        # seguir girando al mismo lado hasta que suba. Fuera de ese caso
                        # paso() devuelve None y queda todo como arriba.
                        if (COMPLETAR_GIRO and RECUP and _cg is not None and green_state == 0 and
                                _now_rec < _recup_post_hasta):
                            try:
                                _ang_cg = _cg.paso(_mm, _linea_recup_ok, _now_rec)
                            except Exception as _ecg:
                                _ang_cg = None
                                print("[CG] error; conserva V6.6: %s" % _ecg)
                            if _ang_cg is not None:
                                angle = _ang_cg
                                _quien = "recup-completa-giro"
                                if not _cg.logueado:
                                    print("[CG] cinta de frente tras el pivote -> sigue girando %s" %
                                          ("DER" if _cg.lado > 0 else "IZQ"))
                                    _cg.logueado = True

                    elif _linea_recup_ok:
                        _recup_malos = 0
                        _recup_rearme_buenos += 1
                        if _recup_rearme_buenos >= RECUP_REARME_FRAMES:
                            _recup_armada = True

                    else:
                        _recup_rearme_buenos = 0
                        if _recup_armada:
                            _recup_malos += 1
                            angle = _recup_ultimo_angle
                            _quien = "recup-confirma"

                            if _recup_malos >= RECUP_PERDIDA_FRAMES:
                                _recup_activa = True
                                _recup_armada = False
                                _recup_malos = 0
                                _recup_buenos = 0
                                _recup_inicio_ts = _now_rec
                                print("[RECUP-GUARD] evidencia=%s" % _rec_guard.freeze())
                                _loss_retro_done = False
                                _loss_retro_ts = 0.0
                                _loss_decision = None
                                _loss_curve_sent_ts = 0.0
                                if _cg is not None:
                                    _cg.nuevo_episodio()
                                if _term_guard is not None:
                                    try:
                                        _term_episode_evidence = _term_guard.snapshot()
                                        # La evidencia queda congelada para ESTE episodio.
                                        # Vaciar la historia evita que un terminal viejo contamine
                                        # una perdida futura despues de una curva/rearme.
                                        _term_guard.reset()
                                        _term_veto_logged = False
                                        _side_check_logged = False
                                        _side_seen_raw_lateral = set()
                                        _curve_latched_decision = None
                                        _curve_latch_logged = False
                                        if TERM_HARD_SHADOW or TERM_HARD_AUTH:
                                            print("[TERM-HARD] snapshot strong=%s advance=%s last_ymin=%s side_recent=%s n=%s s4k=%s bb=%s | hoy=%s piso=%s (%s)" % (
                                                _term_episode_evidence.get("strong"),
                                                _term_episode_evidence.get("advance"),
                                                _term_episode_evidence.get("last_ymin"),
                                                _term_episode_evidence.get("side_recent"),
                                                _term_episode_evidence.get("n"),
                                                _term_episode_evidence.get("s4k"),
                                                _term_episode_evidence.get("bb"),
                                                _term_episode_evidence.get("strong_hoy"),
                                                _term_episode_evidence.get("strong_piso"),
                                                _term_episode_evidence.get("piso_why")))
                                    except Exception as _te:
                                        print("[TERM-HARD] snapshot fallo; conserva V6.5: %s" % _te)
                                        _term_episode_evidence = None
                                if _loss_arb is not None:
                                    _snap = _loss_arb.begin_episode(now=_now_rec)
                                    print("[PERDIDA] disparo; intencion previa=%s lado=%s edad=%s source=%s" %
                                          (_snap.get("prior"), _snap.get("side"), _snap.get("age_s"), _snap.get("source")))
                                _recup_rumbo_camino_raw = None
                                _recup_rumbo_congelado = 0.0
                                _recup_rumbo_fuente = "esperando-retroceso"
                                green_state = GS_LINEA_PERDIDA
                                angle = 0.0
                                _quien = "recup-disparo-sin-decision"
                        else:
                            _recup_malos = 0
                            if SAFE_NO_LINE_GUARD and np.count_nonzero(black_mask) == 0:
                                # REV: recovery no armada y mascara TOTALMENTE vacia:
                                # el -90 de atan2(0,0) no debe salir. Con negro no
                                # conectado se conserva V6.5.
                                angle = 0.0
                                _quien = "v66-desarmado-mascara-vacia-recto"

            # Guardar la posicion REAL del fragmento durante el giro dirigido.
            if RECUP and RETROCEDER and green_state == 4 and abs(angle) > 10:
                _rec_guard.remember_fragment(black_mask, time.monotonic())

            # Solo el cierre de una recuperacion lateral; GAP y marcas conservan prioridad.
            if RECUP and RETROCEDER and green_state == 0:
                _finish_guard = _rec_guard.finish(time.monotonic(), _mm, black_mask, angle)
                if _finish_guard is not None:
                    angle = _finish_guard["angle"]
                    if _finish_guard["action"] == "STOP":
                        green_state = GS_PERDIDA_FAILSAFE
                        _gap_failsafe = True
                        _recup_activa = False
                        _recup_armada = False
                        _quien = "recup-guard-stop"
                    else:
                        _quien = "recup-guard-reenganche" if _finish_guard["action"] == "SEARCH" else "recup-guard-completa"

            output = send_frame(speed, round(angle), green_state, silver_line)
            _grabar(frame_resized, _ang_viejo, angle, _r, _quien, _corte)
            if GRABAR_CRUDO:
                _grabar_crudo(frame_resized, green_mask, black_mask, speed, angle, green_state, silver_line, _quien)
            line_frames += 1
            if time.time() - line_t0 >= 30:
                print(f"[LINE-FPS] avg={line_frames / (time.time() - line_t0):.2f}")
                line_t0 = time.time()
                line_frames = 0
            # ---- Envio con ACK ----

            # La camara NO tiene autoridad para entrar a rescate. APDS/Teensy
            # manda 0xF1 cuando confirma plateado fisicamente.

            # FIX: while en lugar de if para drenar el buffer completo cada iteracion.
            # Con if, si el Teensy envia ~30 ACKs/s y el loop de vision tarda ~25ms,
            # el buffer se acumula y el watchdog reporta falsos timeouts.
            # El break al detectar 0xFF es critico: evita procesar bytes de un estado
            # que ya cambio si el buffer contiene [ACK, ACK, 0xFF, ACK].
            while ser.in_waiting > 0:
                data = ser.read()
                action = handle_control_byte(data, context="linea")
                if action in ('boot', 'stop'):
                    print("cambiando estado")
                    break  # salir inmediatamente: el estado ya cambio

            if SHOW_DEBUG_WINDOWS and debugOriginal:
                cv2.imshow('Original', frame_resized)
            if SHOW_DEBUG_WINDOWS and record:
                cv2.imshow('redd', red_mask)
            if SHOW_DEBUG_WINDOWS and debugBlack:
                cv2.imshow('Black Mask', black_mask)
            if SHOW_DEBUG_WINDOWS and debugGreen:
                cv2.imshow('Green Mask', green_mask)
            if SHOW_DEBUG_WINDOWS and debugHori:
                cv2.imshow('Silver Mask', silver_mask)

            if SHOW_DEBUG_WINDOWS and cv2.waitKey(1) & 0xFF == ord('q'):
                break

if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            stop_teensy_safely("KeyboardInterrupt")
            break
        except Exception as exc:
            print(f"[FATAL] Main.py se recupera de excepcion global: {exc}")
            stop_teensy_safely("excepcion global")
            estado = 'esperando'
            time.sleep(1.0)

