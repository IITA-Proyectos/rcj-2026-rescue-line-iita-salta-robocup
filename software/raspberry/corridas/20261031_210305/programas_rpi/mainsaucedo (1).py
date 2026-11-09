import cv2
from camthreader import *
import numpy as np
import math
import time
import serial
import sys
import os
import threading
import queue
import atexit
from collections import deque

# ================== MEJORAS DE SEGUIMIENTO (parche IITA) ==================
_MODO = os.environ.get("PLANNER", "0")
USAR_PLANNER = _MODO in ("1", "2")
MODO_HIBRIDO = _MODO == "2"
RUTA_VIDEO   = os.environ.get("GRABAR", "")
ROI_MODO     = os.environ.get("ROI", "60")
CTRL         = os.environ.get("CTRL", "atan2")
RECUP        = os.environ.get("RECUP", "0") == "1"

RETROCEDER   = os.environ.get("RETROCEDER", "0") == "1"
GS_LINEA_PERDIDA = 4
K_CERCA      = float(os.environ.get("K_CERCA", "40"))
K_LEJOS      = float(os.environ.get("K_LEJOS", "40"))
RECUP_ANG    = float(os.environ.get("RECUP_ANG", "75"))
SATURA_DESDE = float(os.environ.get("SATURA_DESDE", "70"))
AREA_MIN_LINEA = float(os.environ.get("AREA_MIN", "200"))

_ult_lado = 0.0
_frames_sin = 0


def _fila_horizonte(frame_bgr, minimo=25, maximo=60):
    try:
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).astype(float)
        brillo = g.mean(axis=1)
        textura = g.std(axis=1)

        for y in range(maximo + 20):
            if (
                brillo[y] > 110
                and textura[y] < 55
                and brillo[y:y + 10].mean() > 110
            ):
                return max(minimo, y)

    except Exception:
        pass

    return maximo


def _solo_mi_linea(mask):
    try:
        num, et, st, _ = cv2.connectedComponentsWithStats(
            (mask > 0).astype(np.uint8),
            8
        )

        fila = et[mask.shape[0] - 2]
        suyas = np.unique(fila[fila > 0])

        if not len(suyas):
            return np.zeros_like(mask)

        area = max(
            int(st[i, cv2.CC_STAT_AREA])
            for i in suyas
        )

        if area < AREA_MIN_LINEA:
            return np.zeros_like(mask)

        return (np.isin(et, suyas) * 255).astype(np.uint8)

    except Exception:
        return mask


def _error_lateral(mask, y0, y1):
    banda = mask[y0:y1, :]
    xs = np.nonzero(banda)[1]

    if len(xs) < 20:
        return None

    return (
        float(xs.mean()) - (mask.shape[1] - 1) / 2.0
    ) / (mask.shape[1] / 2.0)


def _angulo_lineal(mask, corte):

    mask = _solo_mi_linea(mask)

    e_pos = _error_lateral(mask, 105, 119)

    if e_pos is None:
        e_pos = _error_lateral(mask, corte, 120)

        if e_pos is None:
            return None

    lejos = _error_lateral(
        mask,
        corte,
        min(corte + 18, 96)
    )

    if lejos is None:
        return max(
            -90.0,
            min(
                90.0,
                -(K_CERCA + K_LEJOS) * e_pos
            )
        )

    e_rumbo = lejos - e_pos

    return max(
        -90.0,
        min(
            90.0,
            -(K_CERCA * e_pos + K_LEJOS * e_rumbo)
        )
    )


_seguidor = None

if USAR_PLANNER:
    try:
        from seguidor_linea import Seguidor
        _seguidor = Seguidor()
        print("[PLANNER] encendido")

    except Exception as _e:
        print(
            "[PLANNER] no se pudo cargar (%s): "
            "sigo con el metodo de siempre"
            % _e
        )
        USAR_PLANNER = False


print(
    "[PARCHE] ROI=%s CTRL=%s RECUP=%s PLANNER=%s"
    % (ROI_MODO, CTRL, RECUP, _MODO)
)


_video = None
_video_n = 0


def _cerrar_video():

    global _video

    if _video is not None:
        try:
            _video.release()

            print(
                "[GRABAR] cerrado: %d frames en %s"
                % (_video_n, RUTA_VIDEO)
            )

        except Exception:
            pass

        _video = None


atexit.register(_cerrar_video)


def _grabar(
    frame_bgr,
    ang_viejo,
    ang_nuevo,
    r,
    quien,
    corte
):

    global _video
    global _video_n

    if not RUTA_VIDEO:
        return

    try:

        vis = cv2.resize(
            frame_bgr,
            (320, 240),
            interpolation=cv2.INTER_NEAREST
        )

        cv2.line(
            vis,
            (0, corte * 2),
            (319, corte * 2),
            (0, 255, 255),
            1
        )

        if r is not None and r.get("mascara") is not None:

            mk = cv2.cvtColor(
                cv2.resize(
                    r["mascara"],
                    (320, 240),
                    interpolation=cv2.INTER_NEAREST
                ),
                cv2.COLOR_GRAY2BGR
            )

        else:

            m = cv2.inRange(
                frame_bgr,
                lower_black,
                upper_black
            )

            m[:corte, :] = 0

            mk = cv2.cvtColor(
                cv2.resize(
                    _solo_mi_linea(m),
                    (320, 240),
                    interpolation=cv2.INTER_NEAREST
                ),
                cv2.COLOR_GRAY2BGR
            )

        if r is not None and r.get("puntos"):

            p = [
                (int(x * 2), int(y * 2))
                for x, y in r["puntos"]
            ]

            for u, v in zip(p, p[1:]):
                cv2.line(
                    vis,
                    u,
                    v,
                    (0, 255, 0),
                    2
                )

            for x, y in p:
                cv2.circle(
                    mk,
                    (int(x * 2), int(y * 2)),
                    2,
                    (0, 0, 255),
                    -1
                )

        cv2.putText(
            vis,
            "viejo %+.0f" % ang_viejo,
            (4, 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1
        )

        if ang_nuevo is not None:

            cv2.putText(
                vis,
                "manda %+.0f" % ang_nuevo,
                (4, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                1
            )

        cv2.putText(
            vis,
            quien,
            (4, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 128, 255)
            if quien == "buscando"
            else (0, 255, 0),
            1
        )

        cv2.putText(
            mk,
            "mascara corte f%d" % corte,
            (4, 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 128, 0),
            1
        )

        vis = np.hstack([vis, mk])

        if _video is None:

            _video = cv2.VideoWriter(
                os.path.expanduser(RUTA_VIDEO),
                cv2.VideoWriter_fourcc(*"MJPG"),
                20.0,
                (640, 240)
            )

            print(
                "[GRABAR] escribiendo en %s"
                % RUTA_VIDEO
            )

        _video.write(vis)
        _video_n += 1

    except Exception as _e:

        print(
            "[GRABAR] se apaga por error: %s"
            % _e
        )

        globals()["RUTA_VIDEO"] = ""


# ========================================================================
# CONFIGURACION
# ========================================================================

HEADLESS = os.environ.get("DISPLAY") is None
DEBUG_VIEW = os.environ.get("DEBUG_VIEW") == "1"
SHOW_DEBUG_WINDOWS = (not HEADLESS) or DEBUG_VIEW
ENABLE_CX_BLACK_GUARD = True


# ========================================================================
# PROTOCOLO RPi -> Teensy
# ========================================================================

SYNC_SPEED = 0xFF
SYNC_ANGLE = 0xFE
SYNC_GREEN_STATE = 0xFD
SYNC_SILVER_LINE = 0xFC

TEENSY_BOOT = b'\xfa'
TEENSY_READY = b'\xf9'
TEENSY_RESCATE_DONE = b'\xf8'
TEENSY_STOP = b'\xff'
TEENSY_RESCATE = False
TEENSY_EVACUACION = b'\xf7'

SERIAL_TIMEOUT_S = 0.05
FRAME_NONE_RETRY_SLEEP_S = 0.01
FRAME_NONE_RESTART_THRESHOLD = 30
TELEMETRY_INTERVAL_S = 5.0


# ========================================================================
# DELAY DE ENVIO
# ========================================================================

# El Teensy recibe cada 8 ms.
INTERVALO_ENVIO_S = 0.008

# El dato enviado tiene 100 ms de antigüedad.
DELAY_ENVIO_S = 0.100

# Archivo donde se guarda el historial.
HISTORIAL_PATH = "historial"


# ========================================================================
# HISTORIAL
# ========================================================================

# Al iniciar:
# - si no existe -> lo crea
# - si existe -> borra todo
# - empieza nuevamente desde cero

try:

    with open(
        HISTORIAL_PATH,
        "w"
    ) as historial:

        historial.write(
            "timestamp,angle\n"
        )

    print(
        "[HISTORIAL] iniciado: %s"
        % os.path.abspath(HISTORIAL_PATH)
    )

except Exception as e:

    print(
        "[HISTORIAL] ERROR creando archivo: %s"
        % e
    )


# ========================================================================
# BUFFER TEMPORAL
# ========================================================================

datos_buffer = deque()

datos_buffer_lock = threading.Lock()

envio_stop_event = threading.Event()

ultimo_dato_calculado = {
    "speed": 0,
    "angle": 0,
    "green_state": 0,
    "silver_line": 0
}

ultimo_dato_lock = threading.Lock()


# ========================================================================
# SWITCH PRINCIPAL
# ========================================================================

USE_ZERODCE = False
ZERODCE_PATH = (
    "/home/pi/Downloads/AI_enhance/"
    "dcenet_int8.tflite"
)

ZERODCE_GAIN = 1.65


debugOriginal = False
debugBlack = True
debugGreen = True
debugBlue = False
debugHori = False
record = True

noise_blob_threshold = 16
min_square_size = 510
min_line_size = 1

fixed_angle_value = 0
fixed_angle_active = False
fixed_angle_start_time = 0

estado = 'esperando'

frames_sent = 0

last_tx_telemetry = time.monotonic()


# ========================================================================
# CAMARA Y SERIAL
# ========================================================================

vs = WebcamVideoStream(
    src=0
).start()

ser = serial.Serial(
    '/dev/serial0',
    115200,
    timeout=SERIAL_TIMEOUT_S,
    write_timeout=SERIAL_TIMEOUT_S
)


lower_black = np.array(
    [0, 0, 0]
)

upper_black = np.array(
    [90, 90, 90]
)

lower_green = np.array(
    [70, 85, 138]
)

upper_green = np.array(
    [104, 102, 158]
)

lower_silver_hsv = np.array(
    [79, 16, 46]
)

upper_silver_hsv = np.array(
    [168, 28, 79]
)

lower_red1 = np.array(
    [0, 84, 54]
)

upper_red1 = np.array(
    [7, 255, 200]
)

lower_red2 = np.array(
    [170, 84, 54]
)

upper_red2 = np.array(
    [179, 255, 200]
)


last_angles = []

YOLO_IMGSZ = 256

width = 160
height = 120

print(width, height)

cam_x = width / 2 - 1
cam_y = height - 1

timer_active = False

green_output_duration = 1
green_output_cooldown_duration = 2

green_state_final = 0
timer_start_time = 0

silver_line = False


# ========================================================================
# FUNCIONES DE SERIAL
# ========================================================================

def clamp_byte(value):

    return max(
        0,
        min(
            255,
            int(value)
        )
    )


def send_frame(
    speed,
    angle,
    green_state,
    silver_line_flag
):

    global frames_sent
    global last_tx_telemetry

    output = bytes([
        SYNC_SPEED,
        clamp_byte(speed),

        SYNC_ANGLE,
        clamp_byte(angle + 90),

        SYNC_GREEN_STATE,
        clamp_byte(green_state),

        SYNC_SILVER_LINE,
        clamp_byte(
            int(bool(silver_line_flag))
        )
    ])

    ser.write(output)

    # IMPORTANTE:
    # no usamos ser.flush() en cada paquete.
    # El puerto ya tiene una cola de transmision.
    #
    # Esto ayuda a que el hilo pueda mantener
    # aproximadamente los 8 ms.

    frames_sent += 1

    now = time.monotonic()

    if (
        now - last_tx_telemetry
        >= TELEMETRY_INTERVAL_S
    ):

        print(
            f"[TLM] frames_sent={frames_sent} "
            f"estado={estado}"
        )

        last_tx_telemetry = now

    return output


# ========================================================================
# AGREGAR DATO AL HISTORIAL + BUFFER
# ========================================================================

def registrar_dato_envio(
    speed,
    angle,
    green_state,
    silver_line
):

    global ultimo_dato_calculado

    timestamp = time.monotonic()

    speed = int(speed)
    angle = int(angle)
    green_state = int(green_state)
    silver_line = int(bool(silver_line))

    # ----------------------------------------------------
    # Guardar el ultimo dato calculado
    # ----------------------------------------------------

    with ultimo_dato_lock:

        ultimo_dato_calculado = {
            "speed": speed,
            "angle": angle,
            "green_state": green_state,
            "silver_line": silver_line
        }

    # ----------------------------------------------------
    # Guardar angle en archivo
    # ----------------------------------------------------

    try:

        with open(
            HISTORIAL_PATH,
            "a"
        ) as historial:

            historial.write(
                f"{timestamp:.6f},{angle}\n"
            )

    except Exception as e:

        print(
            "[HISTORIAL] error escribiendo: %s"
            % e
        )

    # ----------------------------------------------------
    # Agregar al buffer
    # ----------------------------------------------------

    with datos_buffer_lock:

        datos_buffer.append(
            (
                timestamp,
                speed,
                angle,
                green_state,
                silver_line
            )
        )


# ========================================================================
# HILO DE ENVIO RETARDADO
# ========================================================================

def hilo_envio_retardado():

    """
    Este hilo es independiente de OpenCV.

    La vision calcula datos actuales.

    Los datos quedan en datos_buffer.

    Cuando pasan 100 ms:
        salen del buffer
        y se envian al Teensy.

    El Teensy recibe un paquete cada 8 ms.

    Si durante algun momento no hay un dato nuevo que
    haya cumplido los 100 ms, se repite el ultimo dato.

    De esta manera NUNCA dejamos de enviar.
    """

    ultimo_enviado = (
        0,
        0,
        0,
        0
    )

    proximo_envio = time.monotonic()

    while not envio_stop_event.is_set():

        ahora = time.monotonic()

        # ====================================================
        # Buscar el dato correspondiente a hace 100 ms
        # ====================================================

        limite = ahora - DELAY_ENVIO_S

        dato_para_enviar = None

        with datos_buffer_lock:

            while datos_buffer:

                dato = datos_buffer[0]

                timestamp = dato[0]

                if timestamp <= limite:

                    dato_para_enviar = (
                        datos_buffer.popleft()
                    )

                    # dato:
                    # timestamp
                    # speed
                    # angle
                    # green_state
                    # silver_line

                    ultimo_enviado = dato[1:]

                else:

                    break

        # ====================================================
        # Si todavia no existe un dato de hace 100 ms
        # repetimos el ultimo.
        # ====================================================

        speed, angle, green_state, silver_line = (
            ultimo_enviado
        )

        # ====================================================
        # Enviar
        # ====================================================

        try:

            send_frame(
                speed,
                angle,
                green_state,
                silver_line
            )

        except Exception as e:

            print(
                "[ENVIO] error serial: %s"
                % e
            )

        # ====================================================
        # Intentar mantener periodo de 8 ms
        # ====================================================

        proximo_envio += INTERVALO_ENVIO_S

        espera = (
            proximo_envio
            - time.monotonic()
        )

        if espera > 0:

            time.sleep(espera)

        else:

            # Si nos atrasamos demasiado,
            # recalculamos el siguiente periodo.

            proximo_envio = time.monotonic()


# ========================================================================
# INICIAR HILO DE ENVIO
# ========================================================================

t_envio_retardado = threading.Thread(
    target=hilo_envio_retardado,
    daemon=True
)

t_envio_retardado.start()

print(
    "[DELAY] sistema de buffer iniciado"
)

print(
    "[DELAY] retardo = %.0f ms"
    % (DELAY_ENVIO_S * 1000)
)

print(
    "[DELAY] envio = %.0f ms"
    % (INTERVALO_ENVIO_S * 1000)
)


def stop_teensy_safely(reason):

    try:

        print(
            f"[SAFE-STOP] {reason}: "
            f"enviando speed=0 al Teensy"
        )

        # El stop tambien entra por el sistema normal.
        registrar_dato_envio(
            0,
            0,
            0,
            0
        )

    except Exception as exc:

        print(
            f"[SAFE-STOP] "
            f"no se pudo enviar stop: {exc}"
        )


# ========================================================================
# VIDEO RECOVERY
# ========================================================================

def restart_video_stream():

    global vs

    try:
        vs.stop()
    except Exception:
        pass

    time.sleep(0.1)

    vs = WebcamVideoStream(
        src=0
    ).start()

    return vs


def read_frame_with_recovery(
    none_count,
    context
):

    frame = vs.read()

    if frame is not None:

        return frame, 0

    none_count += 1

    if (
        none_count == 1
        or none_count % 10 == 0
    ):

        print(
            f"[WARN] {context}: "
            f"frame None ({none_count})"
        )

    if (
        none_count
        >= FRAME_NONE_RESTART_THRESHOLD
    ):

        print(
            f"[WARN] {context}: "
            f"reiniciando VideoStream tras "
            f"{FRAME_NONE_RESTART_THRESHOLD} frames vacios"
        )

        restart_video_stream()

        none_count = 0

    time.sleep(
        FRAME_NONE_RETRY_SLEEP_S
    )

    return None, none_count


# ========================================================================
# CONTROL DESDE TEENSY
# ========================================================================

def handle_control_byte(
    data,
    context="serial"
):

    global estado

    if not data:
        return None

    if data == TEENSY_BOOT:

        print(
            f"[INFO] {context}: "
            f"Teensy reseteado -> esperando"
        )

        estado = 'esperando'

        return 'boot'

    if data == TEENSY_STOP:

        estado = 'esperando'

        return 'stop'

    if data == TEENSY_READY:

        if estado in (
            'esperando',
            'evacuacion'
        ):

            estado = 'linea'

            return 'linea'

        return 'ready'

    if data == TEENSY_RESCATE:

        print(
            f"[INFO] {context}: "
            f"Llego 241 -> entrando a rescate"
        )

        estado = 'rescate'

        return 'rescate'

    if data == TEENSY_RESCATE_DONE:

        if estado == 'rescate':

            estado = 'depositar'

            return 'depositar'

        return 'rescate_done'

    if data == TEENSY_EVACUACION:

        if estado in (
            'rescate',
            'depositar',
            'depositar verde'
        ):

            estado = 'evacuacion'

            return 'evacuacion'

        return 'evacuacion_ignored'

    return None


# ========================================================================
# MATRICES DE CAMARA
# ========================================================================

x_com = np.zeros(
    shape=(height, width)
)

y_com = np.zeros(
    shape=(height, width)
)

for i in range(height):

    for j in range(width):

        x_com[i][j] = (
            j - cam_x
        ) / (width / 2)

        y_com[i][j] = (
            cam_y - i
        ) / height


# ========================================================================
# AGCWD
# ========================================================================

def agcwd(
    img_bgr,
    w=0.5
):

    hsv = cv2.cvtColor(
        img_bgr,
        cv2.COLOR_BGR2HSV
    )

    v = hsv[:, :, 2]

    hist = np.bincount(
        v.ravel(),
        minlength=256
    ).astype(
        np.float32
    )

    hist_min = hist.min()
    hist_max = hist.max()

    if hist_max - hist_min < 1e-6:

        return img_bgr

    w_pdf = hist_max * (
        (
            hist - hist_min
        ) /
        (
            hist_max - hist_min
        )
    ) ** w

    w_cdf = np.cumsum(w_pdf)

    w_cdf = (
        w_cdf /
        w_cdf[-1]
    )

    lut = np.array(
        [
            int(
                255 *
                (i / 255.0) **
                (1.0 - w_cdf[i])
            )
            for i in range(256)
        ],
        dtype=np.uint8
    )

    mean_v = float(
        np.mean(v)
    )

    if mean_v > 120:

        lut = (
            lut * 0.3
            +
            np.arange(
                256,
                dtype=np.float32
            ) * 0.7
        ).astype(
            np.uint8
        )

    hsv[:, :, 2] = cv2.LUT(
        v,
        lut
    )

    return cv2.cvtColor(
        hsv,
        cv2.COLOR_HSV2BGR
    )


# ========================================================================
# ZERO DCE
# ========================================================================

if USE_ZERODCE:

    sys.path.insert(
        0,
        '/home/pi/Downloads/AI_enhance'
    )

    from zero_dce import ZeroDCE

    print(
        "Cargando Zero-DCE..."
    )

    _enhancer = ZeroDCE(
        ZERODCE_PATH,
        patch_size=(
            YOLO_IMGSZ,
            YOLO_IMGSZ
        ),
        num_threads=2
    )

    print(
        "Zero-DCE listo."
    )


ENABLE_ANTIFLASH = True


def anti_flash_preprocess(
    img_bgr,
    v_flash=215,
    s_low=60,
    compress=0.45
):

    hsv = cv2.cvtColor(
        img_bgr,
        cv2.COLOR_BGR2HSV
    )

    h, s, v = cv2.split(hsv)

    s = s.astype(
        np.float32
    )

    v = v.astype(
        np.float32
    )

    flash_mask = (
        (v >= v_flash)
        &
        (s <= s_low)
    )

    if not np.any(
        flash_mask
    ):

        return img_bgr

    mask_blur = (
        flash_mask.astype(
            np.uint8
        ) * 255
    )

    mask_blur = cv2.GaussianBlur(
        mask_blur,
        (5, 5),
        0
    )

    alpha = (
        mask_blur.astype(
            np.float32
        ) / 255.0
    )

    v = (
        v * (1 - alpha)
        +
        (
            v_flash
            +
            (
                v - v_flash
            ) * compress
        ) * alpha
    )

    hsv[:, :, 1] = (
        s.astype(
            np.uint8
        )
    )

    hsv[:, :, 2] = (
        v.astype(
            np.uint8
        )
    )

    return cv2.cvtColor(
        hsv,
        cv2.COLOR_HSV2BGR
    )


def enhance(
    img_bgr,
    use_zerodce=False
):

    if use_zerodce:

        rgb = cv2.cvtColor(
            img_bgr,
            cv2.COLOR_BGR2RGB
        )

        rgb = _enhancer.enhance(
            rgb,
            gain=ZERODCE_GAIN
        )

        out = cv2.cvtColor(
            rgb,
            cv2.COLOR_RGB2BGR
        )

    else:

        out = img_bgr

    if ENABLE_ANTIFLASH:

        out = anti_flash_preprocess(
            out
        )

    return agcwd(out)


# ========================================================================
# TFLITE
# ========================================================================

from ai_edge_litert.interpreter import (
    Interpreter as TFLiteInterpreter
)

print(
    "Usando ai_edge_litert.interpreter"
)

TFLITE_MODEL_PATH = (
    "/home/iita/Desktop/"
    "yolov8n_rescuebot_2026.tflite"
)

NUM_THREADS = 2

interpreter = TFLiteInterpreter(
    model_path=TFLITE_MODEL_PATH,
    num_threads=NUM_THREADS
)

interpreter.allocate_tensors()

_input_details = (
    interpreter.get_input_details()[0]
)

_output_details = (
    interpreter.get_output_details()[0]
)

print(
    "TFLite input:",
    _input_details
)

print(
    "TFLite output:",
    _output_details
)


# ========================================================================
# WARMUP
# ========================================================================

print(
    "Realizando warmup del modelo TFLite..."
)

_dummy = np.zeros(
    (
        YOLO_IMGSZ,
        YOLO_IMGSZ,
        3
    ),
    dtype=np.uint8
)

if np.issubdtype(
    _input_details['dtype'],
    np.floating
):

    _dummy_inp = (
        _dummy.astype(
            np.float32
        ) / 255.0
    )[np.newaxis, ...].astype(
        _input_details['dtype']
    )

else:

    _dummy_inp = (
        _dummy[np.newaxis, ...]
        .astype(
            _input_details['dtype']
        )
    )

interpreter.set_tensor(
    _input_details['index'],
    _dummy_inp
)

interpreter.invoke()

_ = interpreter.get_tensor(
    _output_details['index']
)

print(
    "Warmup completado."
)


# ========================================================================
# MODO RESCATE
# ========================================================================

def modo_rescate(
    evac_mode=False
):

    global last_target_box
    global is_stopped
    global estado
    global ser

    input_details = _input_details
    output_details = _output_details

    last_target_box = None

    stop_rescate = False

    if (
        hasattr(cv2, "legacy")
        and
        hasattr(
            cv2.legacy,
            "TrackerMOSSE_create"
        )
    ):

        print(
            "Legacy MOSSE disponible"
        )

    else:

        print(
            "Legacy MOSSE NO disponible"
        )

    try:

        tr = (
            cv2.legacy.TrackerMOSSE_create()
            if hasattr(cv2, "legacy")
            else cv2.TrackerMOSSE_create()
        )

        print(
            "Creado ok:",
            type(tr)
        )

    except Exception as e:

        print(
            "fallo:",
            e
        )

    os.environ[
        "OMP_NUM_THREADS"
    ] = "2"

    os.environ[
        "MKL_NUM_THREADS"
    ] = "2"

    CLASS_NAMES = [
        'negro',
        'plateado',
        'rojo alto',
        'verde_alto'
    ]

    IMGSZ = YOLO_IMGSZ

    DETECT_EVERY = 3
    MAX_QUEUE = 2
    DRAW_EVERY = 1

    last_target_box = None

    CENTER_TOLERANCE_PX = 8

    STOP_WIDTH_RATIO = 0.25
    STOP_WIDTH_RATIO_BOX = 0.98

    STOP_EVAC = 0.68

    RESUME_WIDTH_RATIO = 0.18

    is_stopped = False

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

    class CentroidTracker:

        def __init__(
            self,
            max_lost=8
        ):

            self.next_object_id = 0

            self.objects = {}

            self.lost = {}

            self.meta = {}

            self.max_lost = max_lost


        def register(
            self,
            bbox,
            cls=0,
            score=0.0
        ):

            oid = self.next_object_id

            self.next_object_id += 1

            self.objects[oid] = bbox

            self.lost[oid] = 0

            self.meta[oid] = {
                'cls': cls,
                'score': score
            }

            return oid


        def deregister(
            self,
            oid
        ):

            if oid in self.objects:
                del self.objects[oid]

            if oid in self.lost:
                del self.lost[oid]

            if oid in self.meta:
                del self.meta[oid]


        def update(
            self,
            detections
        ):

            bboxes = [
                d['xyxy']
                for d in detections
            ]

            if len(bboxes) == 0:

                remove = []

                for oid in list(
                    self.lost.keys()
                ):

                    self.lost[oid] += 1

                    if (
                        self.lost[oid]
                        >
                        self.max_lost
                    ):

                        remove.append(
                            oid
                        )

                for oid in remove:

                    self.deregister(
                        oid
                    )

                return [
                    {
                        'id': oid,
                        'bbox': self.objects[oid],
                        **self.meta[oid]
                    }
                    for oid in self.objects
                ]

            if len(self.objects) == 0:

                for d in detections:

                    self.register(
                        d['xyxy'],
                        d['cls'],
                        d['score']
                    )

                return [
                    {
                        'id': oid,
                        'bbox': self.objects[oid],
                        **self.meta[oid]
                    }
                    for oid in self.objects
                ]

            object_ids = list(
                self.objects.keys()
            )

            object_bboxes = [
                self.objects[oid]
                for oid in object_ids
            ]

            def centroid(b):

                x1, y1, x2, y2 = b

                return (
                    (x1 + x2) // 2,
                    (y1 + y2) // 2
                )

            obj_centroids = [
                centroid(b)
                for b in object_bboxes
            ]

            det_centroids = [
                centroid(d)
                for d in bboxes
            ]

            D = []

            for oc in obj_centroids:

                row = []

                for dc in det_centroids:

                    dx = oc[0] - dc[0]
                    dy = oc[1] - dc[1]

                    row.append(
                        dx * dx
                        +
                        dy * dy
                    )

                D.append(row)

            matched_obj = set()
            matched_det = set()

            assignments = {}

            triples = []

            for i in range(len(D)):

                for j in range(
                    len(D[0])
                ):

                    triples.append(
                        (
                            i,
                            j,
                            D[i][j]
                        )
                    )

            triples.sort(
                key=lambda x: x[2]
            )

            for i, j, _ in triples:

                if (
                    i in matched_obj
                    or
                    j in matched_det
                ):
                    continue

                matched_obj.add(i)
                matched_det.add(j)

                assignments[i] = j

            for i, j in assignments.items():

                oid = object_ids[i]

                self.objects[oid] = (
                    bboxes[j]
                )

                self.meta[oid] = {
                    'cls': detections[j]['cls'],
                    'score': detections[j]['score']
                }

                self.lost[oid] = 0

            for j in range(
                len(detections)
            ):

                if j not in matched_det:

                    self.register(
                        bboxes[j],
                        detections[j]['cls'],
                        detections[j]['score']
                    )

            for i in range(
                len(object_ids)
            ):

                if i not in assignments:

                    oid = object_ids[i]

                    self.lost[oid] += 1

                    if (
                        self.lost[oid]
                        >
                        self.max_lost
                    ):

                        self.deregister(
                            oid
                        )

            return [
                {
                    'id': oid,
                    'bbox': self.objects[oid],
                    **self.meta[oid]
                }
                for oid in self.objects
            ]


    frame_q = queue.Queue(
        MAX_QUEUE
    )

    result_q = queue.Queue(
        MAX_QUEUE
    )

    stop_event = threading.Event()


    def scale_box(
        box_xyxy,
        src_w,
        src_h,
        in_w=IMGSZ,
        in_h=IMGSZ
    ):

        x1, y1, x2, y2 = box_xyxy

        scale_x = src_w / in_w
        scale_y = src_h / in_h

        return (
            int(x1 * scale_x),
            int(y1 * scale_y),
            int(x2 * scale_x),
            int(y2 * scale_y)
        )


    def capture_thread():

        none_count = 0

        while not stop_event.is_set():

            frame, none_count = (
                read_frame_with_recovery(
                    none_count,
                    "rescate-capture"
                )
            )

            if frame is None:
                continue

            frame = cv2.rotate(
                frame,
                cv2.ROTATE_180
            )

            frame_q.put(
                frame
            )

        frame_q.put(
            None
        )


    def infer_thread():

        frame_idx = 0

        while True:

            try:

                frame = frame_q.get()

                if frame is None:

                    result_q.put(
                        None
                    )

                    break

                h, w = frame.shape[:2]

                small = cv2.resize(
                    frame,
                    (
                        IMGSZ,
                        IMGSZ
                    )
                )

                if (
                    frame_idx
                    % DETECT_EVERY
                    == 0
                ):

                    small = enhance(
                        small,
                        use_zerodce=
                        USE_ZERODCE
                    )

                else:

                    if ENABLE_ANTIFLASH:

                        small = (
                            anti_flash_preprocess(
                                small
                            )
                        )

                    small = agcwd(
                        small
                    )

                enhanced_frame = (
                    cv2.resize(
                        small,
                        (w, h)
                    )
                )

                if (
                    frame_idx
                    % DETECT_EVERY
                    == 0
                ):

                    img = cv2.cvtColor(
                        small,
                        cv2.COLOR_BGR2RGB
                    )

                    if np.issubdtype(
                        input_details['dtype'],
                        np.floating
                    ):

                        inp = (
                            img.astype(
                                np.float32
                            )
                            / 255.0
                        )[
                            np.newaxis,
                            ...
                        ].astype(
                            input_details['dtype']
                        )

                    else:

                        inp = (
                            img[np.newaxis, ...]
                            .astype(
                                input_details['dtype']
                            )
                        )

                    interpreter.set_tensor(
                        input_details['index'],
                        inp
                    )

                    interpreter.invoke()

                    out = (
                        interpreter.get_tensor(
                            output_details['index']
                        )[0]
                    )

                    detections = []

                    for det in out:

                        (
                            x1,
                            y1,
                            x2,
                            y2,
                            score,
                            cls_raw
                        ) = det

                        score = float(score)

                        cls_id = int(
                            round(
                                float(
                                    cls_raw
                                )
                            )
                        )

                        if (
                            score
                            <
                            CLASS_THRESH.get(
                                cls_id,
                                0.5
                            )
                        ):

                            continue

                        x1 *= IMGSZ
                        y1 *= IMGSZ
                        x2 *= IMGSZ
                        y2 *= IMGSZ

                        (
                            sx1,
                            sy1,
                            sx2,
                            sy2
                        ) = scale_box(
                            (
                                x1,
                                y1,
                                x2,
                                y2
                            ),
                            w,
                            h,
                            IMGSZ,
                            IMGSZ
                        )

                        if estado == "rescate":

                            if cls_id in (2, 3):
                                continue

                        if estado == "depositar":

                            if cls_id in (0, 1, 2):
                                continue

                        if estado == "depositar verde":

                            if cls_id in (0, 1, 3):
                                continue

                        if evac_mode:

                            if cls_id in (0, 1):
                                continue

                        detections.append(
                            {
                                'xyxy': (
                                    sx1,
                                    sy1,
                                    sx2,
                                    sy2
                                ),
                                'score': score,
                                'cls': cls_id
                            }
                        )

                    result_q.put(
                        (
                            'det',
                            enhanced_frame,
                            detections
                        )
                    )

                else:

                    result_q.put(
                        (
                            'no_det',
                            enhanced_frame,
                            None
                        )
                    )

                frame_idx += 1

            except Exception as exc:

                print(
                    f"[ERROR] infer_thread: {exc}"
                )

                stop_event.set()

                result_q.put(
                    None
                )

                break


    def select_target_from_list(
        boxes,
        estado
    ):

        targets = []

        if estado == 'rescate':

            for d in boxes:

                if d['cls'] in (0, 1):

                    targets.append(d)

        if estado == 'depositar':

            for d in boxes:

                if d['cls'] in (3,):

                    targets.append(d)

        if estado == 'depositar verde':

            for d in boxes:

                if d['cls'] in (2,):

                    targets.append(d)

        if estado == 'evacuacion':

            for d in boxes:

                if d['cls'] in (2, 3):

                    targets.append(d)

        if not targets:

            return None

        return targets[0]


    def choose_stable_target(
        detections,
        last_target,
        estado
    ):

        if not detections:

            return None

        if last_target is None:

            return select_target_from_list(
                detections,
                estado
            )

        lx = (
            last_target['xyxy'][0]
            +
            last_target['xyxy'][2]
        ) // 2

        ly = (
            last_target['xyxy'][1]
            +
            last_target['xyxy'][3]
        ) // 2

        best = None

        best_dist = 1e12

        for d in detections:

            cx = (
                d['xyxy'][0]
                +
                d['xyxy'][2]
            ) // 2

            cy = (
                d['xyxy'][1]
                +
                d['xyxy'][3]
            ) // 2

            dist = math.hypot(
                cx - lx,
                cy - ly
            )

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

                    action = (
                        handle_control_byte(
                            data,
                            context="serial-monitor"
                        )
                    )

                    if action in (
                        'boot',
                        'stop'
                    ):

                        print(
                            "serial monitor: "
                            "switch apagado"
                        )

                        stop_rescate = True

                        break

                    elif action == 'depositar':

                        print(
                            "Llego 248 -> "
                            "terminar rescate "
                            "y cambiar a depositar"
                        )

                    elif action == 'evacuacion':

                        print(
                            "Llego 247 -> "
                            "entrando a evacuacion"
                        )

                        stop_rescate = True

                        break

                    elif action == 'linea':

                        print(
                            "Llego 249 -> "
                            "volviendo a linea"
                        )

                        stop_rescate = True

                        break

            except Exception as e:

                print(
                    "serial_monitor_local error:",
                    e
                )

            time.sleep(
                0.01
            )


    t_serial_mon = threading.Thread(
        target=serial_monitor_local,
        daemon=True
    )

    t_serial_mon.start()


    def main_loop():

        global last_target_box
        global is_stopped
        global estado

        processed = 0

        start = time.time()

        centroid_tracker = CentroidTracker(
            max_lost=8
        )

        last_detections = []

        while True:

            if stop_rescate:

                print(
                    "main_loop: "
                    "stop_rescate activo "
                    "-> saliendo de rescate"
                )

                break

            try:

                item = result_q.get(
                    timeout=0.25
                )

            except queue.Empty:

                continue

            if item is None:

                break

            typ, frame, detections = item

            if typ == 'det':

                last_detections = (
                    detections or []
                )

                ct_objs = (
                    centroid_tracker.update(
                        last_detections
                    )
                )

                last_detections = [
                    {
                        'xyxy': o['bbox'],
                        'cls': o['cls'],
                        'score': o['score']
                    }
                    for o in ct_objs
                ]

            else:

                ct_objs = (
                    centroid_tracker.update(
                        []
                    )
                )

                last_detections = [
                    {
                        'xyxy': o['bbox'],
                        'cls': o['cls'],
                        'score': o['score']
                    }
                    for o in ct_objs
                ]

            target = (
                choose_stable_target(
                    last_detections,
                    last_target_box,
                    estado
                )
            )

            last_target_box = target

            green_state = 0
            speed = 0
            angle = 0

            if target:

                x1, y1, x2, y2 = (
                    target['xyxy']
                )

                cx = (
                    x1 + x2
                ) // 2

                cy = (
                    y1 + y2
                ) // 2

                bbox_w = x2 - x1

                frame_w = frame.shape[1]

                error_x = (
                    cx
                    -
                    (frame_w // 2)
                )

                error_norm = (
                    error_x
                    /
                    (frame_w // 2)
                )

                centered = (
                    abs(error_x)
                    <
                    CENTER_TOLERANCE_PX
                )

                width_ratio = (
                    bbox_w
                    /
                    float(frame_w)
                )

                cv2.putText(
                    frame,
                    f"w_ratio={width_ratio:.3f}",
                    (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    1
                )

                if evac_mode:

                    close_enough = (
                        width_ratio
                        >= STOP_EVAC
                    )

                elif estado in (
                    "depositar",
                    "depositar verde"
                ):

                    close_enough = (
                        width_ratio
                        >= STOP_WIDTH_RATIO_BOX
                    )

                else:

                    close_enough = (
                        width_ratio
                        >= STOP_WIDTH_RATIO
                    )

                if close_enough:

                    speed = 0
                    angle = 0

                    ball_type = None

                    if target['cls'] == 0:
                        ball_type = "silver"

                    elif target['cls'] == 1:
                        ball_type = "black"

                    elif target['cls'] == 2:
                        ball_type = "red_zone"

                    elif target['cls'] == 3:
                        ball_type = "green_zone"

                    if ball_type == "silver":

                        green_state = 6

                    elif ball_type == "black":

                        green_state = 7

                    elif ball_type == "red_zone":

                        green_state = 8

                    elif ball_type == "green_zone":

                        green_state = 9

                        if not evac_mode:

                            estado = (
                                "depositar verde"
                            )

                    if not centered:

                        angle = int(
                            -error_norm * 90
                        )

                        speed = 5

                    if not is_stopped:

                        print(
                            f"[STOP] "
                            f"width_ratio={width_ratio:.3f}, "
                            f"bbox_w={bbox_w}, "
                            f"frame_w={frame_w}"
                        )

                    is_stopped = True

                else:

                    is_stopped = False

                    angle = int(
                        -error_norm * 90
                    )

                    speed = int(
                        20 *
                        (
                            1 -
                            abs(error_norm)
                        )
                    )

                    speed = min(
                        speed,
                        20
                    )

                if (
                    processed
                    %
                    DRAW_EVERY
                    == 0
                ):

                    color = (
                        CLASS_COLORS.get(
                            target['cls'],
                            (0, 255, 255)
                        )
                    )

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        color,
                        2
                    )

                    cv2.circle(
                        frame,
                        (cx, cy),
                        5,
                        (0, 0, 255),
                        -1
                    )

                    cv2.line(
                        frame,
                        (
                            frame_w // 2,
                            0
                        ),
                        (
                            frame_w // 2,
                            frame.shape[0]
                        ),
                        (255, 0, 0),
                        1
                    )

                    cv2.putText(
                        frame,
                        f"{CLASS_NAMES[target['cls']]} "
                        f"{target.get('score',0):.2f} "
                        f"w={bbox_w}",
                        (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2
                    )

            else:

                speed = 20
                angle = 90
                green_state = 0

            # ============================================================
            # IMPORTANTE:
            # YA NO SE ENVIA DIRECTAMENTE AL TEENSY.
            #
            # Se guarda y el hilo de envio lo mandara 100 ms despues.
            # ============================================================

            registrar_dato_envio(
                speed,
                angle,
                green_state,
                0
            )

            processed += 1

            elapsed = (
                time.time()
                -
                start
            )

            fps = (
                processed / elapsed
                if elapsed > 0
                else 0.0
            )

            modo = (
                "ZeroDCE+AGCWD"
                if USE_ZERODCE
                else
                "AGCWD"
            )

            cv2.putText(
                frame,
                f"FPS: {fps:.2f} [{modo}]",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            if SHOW_DEBUG_WINDOWS:

                cv2.imshow(
                    "Optimizado",
                    frame
                )

                if (
                    cv2.waitKey(1)
                    &
                    0xFF
                ) == ord('q'):

                    stop_event.set()

                    break

            else:

                if processed % 30 == 0:

                    print(
                        f"[HEADLESS] "
                        f"FPS ~ {fps:.2f} "
                        f"detecciones: "
                        f"{len(last_detections)}"
                    )

        if SHOW_DEBUG_WINDOWS:

            cv2.destroyAllWindows()


    # ====================================================================
    # LANZAR HILOS
    # ====================================================================

    tcap = threading.Thread(
        target=capture_thread,
        daemon=True
    )

    tinf = threading.Thread(
        target=infer_thread,
        daemon=True
    )

    tcap.start()
    tinf.start()

    try:

        main_loop()

    finally:

        stop_event.set()

        serial_stop_evt.set()

        stop_rescate = False

        while not frame_q.empty():

            try:
                frame_q.get_nowait()
            except:
                pass

        while not result_q.empty():

            try:
                result_q.get_nowait()
            except:
                pass

        tcap.join(
            timeout=1
        )

        tinf.join(
            timeout=1
        )

        t_serial_mon.join(
            timeout=0.5
        )


# ========================================================================
# MAIN
# ========================================================================

def main():

    global estado
    global silver_line
    global _ult_lado
    global _frames_sin

    while True:

        while estado == 'esperando':

            silver_line = False

            if ser.in_waiting > 0:

                data = ser.read()

                handle_control_byte(
                    data,
                    context="esperando"
                )

            time.sleep(
                FRAME_NONE_RETRY_SLEEP_S
            )

        while estado == 'rescate':

            modo_rescate()

        while estado == 'evacuacion':

            modo_rescate(
                evac_mode=True
            )

        line_none_count = 0

        line_t0 = time.time()

        line_frames = 0

        while estado == 'linea':

            frame, line_none_count = (
                read_frame_with_recovery(
                    line_none_count,
                    "linea"
                )
            )

            if frame is None:

                continue

            frame = cv2.rotate(
                frame,
                cv2.ROTATE_180
            )

            frame_resized = cv2.resize(
                frame,
                (160, 120),
                interpolation=cv2.INTER_NEAREST
            )

            kernel = np.ones(
                (3, 3),
                np.uint8
            )

            lab = cv2.cvtColor(
                frame_resized,
                cv2.COLOR_BGR2LAB
            )

            black_mask = cv2.inRange(
                frame_resized,
                lower_black,
                upper_black
            )

            black_mask[:60, :] = 0

            x_black = cv2.bitwise_and(
                x_com,
                x_com,
                mask=black_mask
            )

            x_black *= (
                1 - y_com
            )

            y_black = cv2.bitwise_and(
                y_com,
                y_com,
                mask=black_mask
            )

            green_mask = np.zeros(
                (120, 160),
                dtype=np.uint8
            )

            green_mask[80:, :] = (
                cv2.inRange(
                    lab[80:, :, :],
                    lower_green,
                    upper_green
                )
            )

            cut_line = np.zeros(
                (120, 160),
                dtype=np.uint8
            )

            hsv_frame = cv2.cvtColor(
                frame_resized,
                cv2.COLOR_BGR2HSV
            )

            cut_line[62:, :] = (
                cv2.inRange(
                    frame_resized[62:, :, :],
                    lower_black,
                    upper_black
                )
            )

            red_mask = cv2.bitwise_or(
                cv2.inRange(
                    hsv_frame,
                    lower_red1,
                    upper_red1
                ),
                cv2.inRange(
                    hsv_frame,
                    lower_red2,
                    upper_red2
                )
            )

            red_mask[:75, :] = 0

            silver_mask = cv2.inRange(
                frame_resized,
                lower_silver_hsv,
                upper_silver_hsv
            )

            silver_mask[:75, :] = 0

            green_state = 0

            x_resultant = np.mean(
                x_black
            )

            y_resultant = np.mean(
                y_black
            )

            angle = (
                math.atan2(
                    y_resultant,
                    x_resultant
                )
                /
                math.pi
                *
                180
            ) - 90

            speed = 40

            # ============================================================
            # PARCHE IITA
            # ============================================================

            _corte = 60

            if ROI_MODO == "auto":

                _corte = _fila_horizonte(
                    frame_resized
                )

                if _corte < 60:

                    black_mask = cv2.inRange(
                        frame_resized,
                        lower_black,
                        upper_black
                    )

                    black_mask[:_corte, :] = 0

                    x_black = cv2.bitwise_and(
                        x_com,
                        x_com,
                        mask=black_mask
                    )

                    x_black *= (
                        1 - y_com
                    )

                    y_black = (
                        cv2.bitwise_and(
                            y_com,
                            y_com,
                            mask=black_mask
                        )
                    )

                    x_resultant = np.mean(
                        x_black
                    )

                    y_resultant = np.mean(
                        y_black
                    )

                    angle = (
                        math.atan2(
                            y_resultant,
                            x_resultant
                        )
                        /
                        math.pi
                        *
                        180
                    ) - 90

            _ang_viejo = angle

            _quien = "centroide"

            _r = None

            # ============================================================
            # CONTROL LINEAL
            # ============================================================

            if CTRL == "lineal":

                _al = _angulo_lineal(
                    black_mask,
                    _corte
                )

                if _al is not None:

                    angle = _al

                    _quien = "lineal"

            # ============================================================
            # RECUPERACION
            # ============================================================

            if RECUP:

                _mm = _solo_mi_linea(
                    black_mask
                )

                _e = _error_lateral(
                    _mm,
                    100,
                    120
                )

                if _e is None:

                    _e = _error_lateral(
                        _mm,
                        _corte,
                        120
                    )

                if _e is not None:

                    _frames_sin = 0

                    if abs(_e) > 0.15:

                        _ult_lado = (
                            1.0
                            if _e > 0
                            else -1.0
                        )

                else:

                    _frames_sin += 1

                    if RETROCEDER:

                        green_state = (
                            GS_LINEA_PERDIDA
                        )

                        angle = 0

                        _quien = "retrocede"

                    elif _ult_lado != 0.0:

                        _k = min(
                            1.0,
                            0.4
                            +
                            0.1
                            *
                            _frames_sin
                        )

                        angle = (
                            -_ult_lado
                            *
                            RECUP_ANG
                            *
                            _k
                        )

                        _quien = "buscando"

            # ============================================================
            # PLANNER
            # ============================================================

            if USAR_PLANNER:

                try:

                    _r = _seguidor.paso(
                        frame_resized,
                        ya_procesado=True
                    )

                    if not MODO_HIBRIDO:

                        angle = (
                            _r[
                                "angle_filtrado"
                            ]
                        )

                        _quien = "planner"

                    elif (
                        _r.get("ok")
                        and
                        abs(_ang_viejo)
                        >= SATURA_DESDE
                    ):

                        angle = (
                            _r[
                                "angle_filtrado"
                            ]
                        )

                        _quien = "planner*"

                except Exception as _e2:

                    print(
                        "[PLANNER] error, "
                        "sigo con el centroide: %s"
                        % _e2
                    )

                    _r = None

            # ============================================================
            # VERDE
            # ============================================================

            if (
                np.sum(green_mask)
                >
                min_square_size * 255
            ):

                green_pixels = np.amax(
                    green_mask,
                    axis=0
                )

                greenIndices = np.where(
                    green_pixels
                    ==
                    np.max(
                        green_pixels
                    )
                )

                leftIndex = (
                    greenIndices[0][0]
                )

                rightIndex = (
                    greenIndices[0][-1]
                )

                slicedGreen = (
                    frame_resized[
                        60:90,
                        leftIndex:rightIndex + 1,
                        :
                    ]
                )

                greenCentroidX = (
                    rightIndex
                    +
                    leftIndex
                ) / 2

                slicedBlackMaskAboveGreen = (
                    black_mask[
                        60:90,
                        leftIndex:rightIndex + 1
                    ]
                )

                blackM = cv2.moments(
                    black_mask[90:, :]
                )

                if ENABLE_CX_BLACK_GUARD:

                    cx_black = None

                    if (
                        np.sum(
                            black_mask[90:, :]
                        )
                        and
                        blackM["m00"] != 0
                    ):

                        cx_black = int(
                            blackM["m10"]
                            /
                            blackM["m00"]
                        )

                    valid_green_reference = (
                        cx_black is not None
                    )

                else:

                    if np.sum(
                        black_mask[90:, :]
                    ):

                        cx_black = int(
                            blackM["m10"]
                            /
                            blackM["m00"]
                        )

                    valid_green_reference = True

                if (
                    valid_green_reference
                    and
                    (
                        np.sum(
                            slicedBlackMaskAboveGreen
                        )
                        /
                        (
                            255
                            *
                            30
                            *
                            (
                                rightIndex
                                -
                                leftIndex
                            )
                        )
                    )
                    > 0.32
                ):

                    greenSquare = False

                    filtered_green_mask = (
                        cv2.erode(
                            green_mask,
                            kernel,
                            iterations=1
                        )
                    )

                    filtered_green_mask = (
                        cv2.dilate(
                            filtered_green_mask,
                            kernel,
                            iterations=2
                        )
                    )

                    green_contours, hierarchy = (
                        cv2.findContours(
                            filtered_green_mask,
                            cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE
                        )
                    )

                    if (
                        len(green_contours) > 1
                        and
                        cx_black > leftIndex
                        and
                        cx_black < rightIndex
                        and
                        np.sum(green_mask)
                        >
                        (
                            1.2
                            *
                            min_square_size
                            *
                            255
                        )
                    ):

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

            # ============================================================
            # LINEA PERDIDA
            # ============================================================

            if (
                not RECUP
                and
                np.sum(black_mask)
                <
                min_line_size
            ):

                angle = 0

            # ============================================================
            # PLATEADO
            # ============================================================

            silver_contours, _ = (
                cv2.findContours(
                    silver_mask,
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE
                )
            )

            silver_line = False

            for contour in silver_contours:

                area = cv2.contourArea(
                    contour
                )

                print(area)

                if area > 50:

                    silver_line = True

                    break

            # ============================================================
            # ROJO
            # ============================================================

            red_line = False

            double_red_line = False

            red_mask_zone = red_mask.copy()

            red_mask_zone[:60, :] = 0

            row_sum = np.sum(
                red_mask_zone,
                axis=1
            )

            RED_ROW_THRESHOLD = 1500

            red_rows = (
                row_sum
                >
                RED_ROW_THRESHOLD
            )

            in_band = False

            red_bands = 0

            for val in red_rows:

                if val and not in_band:

                    red_bands += 1

                    in_band = True

                elif not val:

                    in_band = False

            red_line = (
                red_bands >= 1
            )

            double_red_line = (
                red_bands >= 2
            )

            if double_red_line:

                green_state = 11

            elif red_line:

                green_state = 10

            # ============================================================
            # IMPORTANTE:
            #
            # Antes:
            #
            # send_frame(...)
            #
            # Ahora:
            #
            # guardar -> esperar 100 ms -> hilo envia
            # ============================================================

            registrar_dato_envio(
                speed,
                round(angle),
                green_state,
                silver_line
            )

            _grabar(
                frame_resized,
                _ang_viejo,
                angle,
                _r,
                _quien,
                _corte
            )

            line_frames += 1

            if (
                time.time()
                -
                line_t0
                >= 30
            ):

                print(
                    f"[LINE-FPS] avg="
                    f"{line_frames / "
                    f"(time.time() - line_t0):.2f}"
                )

                line_t0 = time.time()

                line_frames = 0

            # ============================================================
            # CAMBIO DE ESTADO
            # ============================================================

            if silver_line:

                estado = 'rescate'

            # ============================================================
            # LEER TEENSY
            # ============================================================

            while ser.in_waiting > 0:

                data = ser.read()

                action = (
                    handle_control_byte(
                        data,
                        context="linea"
                    )
                )

                if action in (
                    'boot',
                    'stop'
                ):

                    print(
                        "cambiando estado"
                    )

                    break

            # ============================================================
            # DEBUG
            # ============================================================

            if (
                SHOW_DEBUG_WINDOWS
                and
                debugOriginal
            ):

                cv2.imshow(
                    'Original',
                    frame_resized
                )

            if (
                SHOW_DEBUG_WINDOWS
                and
                record
            ):

                cv2.imshow(
                    'redd',
                    red_mask
                )

            if (
                SHOW_DEBUG_WINDOWS
                and
                debugBlack
            ):

                cv2.imshow(
                    'Black Mask',
                    black_mask
                )

            if (
                SHOW_DEBUG_WINDOWS
                and
                debugGreen
            ):

                cv2.imshow(
                    'Green Mask',
                    green_mask
                )

            if (
                SHOW_DEBUG_WINDOWS
                and
                debugHori
            ):

                cv2.imshow(
                    'Silver Mask',
                    silver_mask
                )

            if (
                SHOW_DEBUG_WINDOWS
                and
                cv2.waitKey(1) & 0xFF
            ) == ord('q'):

                break


# ========================================================================
# EJECUCION
# ========================================================================

if __name__ == "__main__":

    while True:

        try:

            main()

        except KeyboardInterrupt:

            envio_stop_event.set()

            stop_teensy_safely(
                "KeyboardInterrupt"
            )

            break

        except Exception as exc:

            print(
                f"[FATAL] Main.py se recupera "
                f"de excepcion global: {exc}"
            )

            stop_teensy_safely(
                "excepcion global"
            )

            estado = 'esperando'

            time.sleep(1.0)