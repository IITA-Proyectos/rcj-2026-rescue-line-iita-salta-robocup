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
TEENSY_RESCATE = b'\xf1'     # 241 = iniciar modo rescate
TEENSY_EVACUACION = b'\xf7'  # 247 = termino rescate, iniciar evacuacion
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
min_square_size = 550
min_line_size = 50000
fixed_angle_value = 0
fixed_angle_active = False
fixed_angle_start_time = 0
estado = 'esperando'
frames_sent = 0
last_tx_telemetry = time.monotonic()

vs = WebcamVideoStream(src=0).start()
ser = serial.Serial('/dev/serial0', 115200, timeout=SERIAL_TIMEOUT_S, write_timeout=SERIAL_TIMEOUT_S)
lower_black   = np.array([0, 0, 0])
upper_black   = np.array([90, 90, 90])
lower_green = np.array([80, 87, 85])
upper_green = np.array([205, 123, 120])
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
    global estado

    if not data:
        return None

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
try:
    from tflite_runtime.interpreter import Interpreter as TFLiteInterpreter
    print("Usando tflite_runtime.interpreter")
except Exception:
    import tensorflow as tf
    TFLiteInterpreter = tf.lite.Interpreter
    print("Usando tensorflow.lite.Interpreter (fallback)")

TFLITE_MODEL_PATH = "/home/iita/Documentos/best (2)_float32.tflite"
NUM_THREADS = 2
try:
    interpreter = TFLiteInterpreter(model_path=TFLITE_MODEL_PATH, num_threads=NUM_THREADS)
except TypeError:
    interpreter = TFLiteInterpreter(model_path=TFLITE_MODEL_PATH)
try:
    interpreter.set_num_threads(NUM_THREADS)
except Exception:
    pass

interpreter.allocate_tensors()
_input_details  = interpreter.get_input_details()[0]
_output_details = interpreter.get_output_details()[0]
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
    STOP_WIDTH_RATIO     = 0.21
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
    global estado, silver_line

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
        while estado == 'linea':
            frame, line_none_count = read_frame_with_recovery(line_none_count, "linea")
            if frame is None:
                continue

            frame = cv2.rotate(frame, cv2.ROTATE_180)
            frame_resized = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_NEAREST)

            kernel = np.ones((3, 3), np.uint8)
            lab    = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)

            black_mask = cv2.inRange(frame_resized, lower_black, upper_black)
            black_mask[:55, :] = 0
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

                    if len(green_contours) > 1 and cx_black > leftIndex and cx_black < rightIndex and np.sum(green_mask) > (1.25 * min_square_size * 255):
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

            if np.sum(black_mask) < min_line_size:
                angle = 0

            silver_contours, _ = cv2.findContours(silver_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            silver_line = False
            for contour in silver_contours:
                area = cv2.contourArea(contour)
                print(area)
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

            if double_red_line:
                green_state = 11  # codigo nuevo para doble linea roja
            elif red_line:
                green_state = 10

            output = send_frame(speed, round(angle), green_state, silver_line)
            line_frames += 1
            if time.time() - line_t0 >= 30:
                print(f"[LINE-FPS] avg={line_frames / (time.time() - line_t0):.2f}")
                line_t0 = time.time()
                line_frames = 0
            # ---- Envio con ACK ----

            if silver_line:
                estado = 'rescate'

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