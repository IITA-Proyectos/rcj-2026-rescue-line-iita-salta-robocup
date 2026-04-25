##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# OpenCV: image processing, feature extraction, drawing and tracking.
import cv2
# camthreader: threaded camera capture for continuous frame availability.
from camthreader import *
# NumPy: numerical arrays and vectorized computations for masks and geometry.
import numpy as np
# math: trigonometric operations for angle calculations.
import math
# time: timing utilities for cooldowns and performance.
import time
# serial: UART communication with Teensy controller.
import serial
# sys: interpreter access and exit handling.
import sys
# ultralytics.YOLO: object detection model loading and inference.
from ultralytics import YOLO


##################################################

### CONFIGURACION GLOBAL

##################################################

debugOriginal = False  # Enable display of original frames for visual inspection.
debugBlack = True      # Enable display of black mask used for line detection.
debugGreen = True      # Enable display of green mask used for intersection handling.
debugBlue = False      # Placeholder debug flag for blue detection visuals.
debugHori = False      # Enable display focused on horizontal lines or horizon masks.
record = False         # Enable recording or auxiliary windows for debugging.
noise_blob_threshold = 16  # Minimum blob area to discard noise in mask filtering.
min_square_size = 150      # Minimum green area (px) to consider a square marker.
min_line_size =1000        # Minimum black line area to maintain angular correction.
fixed_angle_value = 0      # Manual override angle used when fixed control is active.
fixed_angle_active = False # Toggle to enforce fixed_angle_value regardless of detection.
fixed_angle_start_time = 0 # Timestamp when fixed angle mode was activated.
estado='esperando'         # Current high-level state machine mode.

##################################################

### DEBUG Y VISUALIZACION

##################################################

# Debug flags enable OpenCV windows for masks and overlays to validate
# segmentation, steering decisions, and YOLO detections during runtime.

##################################################

### COMUNICACION / IO

##################################################

#
# Camera input: threaded capture on /dev/video0.
# Serial output: UART to Teensy on /dev/serial0 at 115200 bps, command packets 255-prefixed.
#
vs = WebcamVideoStream(src=0).start()            # Threaded camera stream for low-latency capture.
ser = serial.Serial('/dev/serial0', 115200)      # UART link to Teensy at 115200 bps.
lower_black = np.array([0, 0,0])                 # BGR lower bound for black line segmentation.
upper_black = np.array([90, 90, 90])
lower_green = np.array([120,90, 100])            # Lab lower bound for green square detection.
upper_green = np.array([170,120, 140])
lower_silver_hsv = np.array([ 79, 16, 46])       # HSV lower bound for silver tape detection.
upper_silver_hsv = np.array([168, 28, 79])       # HSV upper bound for silver tape detection.
lower_red = np.array([1, 147,159])               # HSV lower bound for red line detection.
upper_red = np.array([7, 205, 216])              # HSV upper bound for red line detection.
last_angles = []                                  # Rolling buffer for recent steering angles.

MODEL_PATH = "/home/iita/Desktop/zonasdepositoalta.onnx"  # ONNX model for deposit zone detection.
YOLO_IMGSZ = 256                                             # Input size for YOLO inference.

test_frame = vs.read()                         # Warm-up capture to validate camera readiness.

width, height = 160, 120
print(width, height)

cam_x = width / 2 - 1   # 79 ~ middle column
cam_y = height - 1      # 119 ~ bottom row

timer_active = False
green_output_duration = 1
green_output_cooldown_duration = 2
green_state_final = 0
timer_active = False
timer_start_time = 0
silver_line= False
# GET X AND Y ARRAYS
# scaled by frame dimensions, use this for filtering pixels
x_com = np.zeros(shape=(height, width))
y_com = np.zeros(shape=(height, width))

for i in range(height):
    for j in range(width):
        x_com[i][j] = (j - cam_x) / (width / 2)   # [-1, 1]
        y_com[i][j] = (cam_y - i) / height        # [0, 1]

model = YOLO(MODEL_PATH, task='detect')
imagen_negra = np.zeros((YOLO_IMGSZ, YOLO_IMGSZ, 3), dtype=np.uint8)
model.predict(imagen_negra, imgsz=YOLO_IMGSZ, conf=0.25, iou=0.45, stream=False, verbose=False)

##################################################

### FUNCIONES AUXILIARES

##################################################

def modo_rescate():
    """
    Technical description.

    Coordinates rescue mode with detection, tracking, and serial control.

    Parameters:
    None

    Returns:
    None

    Side effects:
    - Starts capture, inference, and serial monitor threads.
    - Sends command packets over serial.
    - Opens OpenCV windows when enabled.
    """
    global last_target_box
    last_target_box = None  
    global is_stopped  
    global estado, ser
    stop_rescate = False
    import cv2
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerMOSSE_create"):
        print("Legacy MOSSE disponible")
    else:
        print("Legacy MOSSE NO disponible")
    try:
        tr = cv2.legacy.TrackerMOSSE_create() if hasattr(cv2, "legacy") else cv2.TrackerMOSSE_create()
        print("Creado ok:", type(tr))
    except Exception as e:
        print("fallo:", e)

    import os
    os.environ["OMP_NUM_THREADS"] = str(max(1, (os.cpu_count() or 4) - 1))
    os.environ["MKL_NUM_THREADS"] = os.environ["OMP_NUM_THREADS"]

    import time
    import threading
    import queue
    import numpy as np
    import math

    # ---- CONFIG ----
    CLASS_NAMES = ['negro', 'plateado', 'rojo alto', 'verde_alto']
    SCORE_THRESHOLD = 0.45
    IMGSZ = YOLO_IMGSZ
    DETECT_EVERY = 1
    MAX_QUEUE = 2
    DRAW_EVERY = 1
    HEADLESS = False

    last_target_box = None
    CENTER_TOLERANCE_PX = 10
    STOP_WIDTH_RATIO = 0.20
    STOP_WIDTH_RATIO_BOX = 0.93
    red_deposited=False
    green_deposited=False
    RESUME_WIDTH_RATIO = 0.18
    is_stopped = False

    def make_mosse():
        """
        Technical description.

        Create a MOSSE tracker using available OpenCV entry points.

        Parameters:
        None

        Returns:
        Any: tracker instance or None when unavailable.

        Side effects:
        - None.
        """
        # Attempt compatibility with OpenCV legacy API
        try:
            if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerMOSSE_create"):
                return cv2.legacy.TrackerMOSSE_create()
        except Exception:
            pass
        try:
            if hasattr(cv2, "TrackerMOSSE_create"):
                return cv2.TrackerMOSSE_create()
        except Exception:
            pass
        try:
            if hasattr(cv2, "Tracker_create"):
                return cv2.Tracker_create("MOSSE")
        except Exception:
            pass
        return None

    class CentroidTracker:
        """
        Technical description.

        Minimal centroid-based tracker to maintain object IDs across frames.

        Parameters:
        max_lost (int): allowed missed frames before deletion.

        Returns:
        None

        Side effects:
        - Maintains internal dictionaries for tracked objects.
        """
        def __init__(self, max_lost=5):
            """
            Technical description.

            Initialize tracker state dictionaries.

            Parameters:
            max_lost (int): frames tolerated without detection before removal.

            Returns:
            None

            Side effects:
            - Initializes counters and storage dictionaries.
            """
            self.next_object_id = 0
            self.objects = {}
            self.lost = {}
            self.max_lost = max_lost

        def register(self, bbox):
            """
            Technical description.

            Assign a new ID to a detected bounding box.

            Parameters:
            bbox (tuple): (x1, y1, x2, y2) coordinates.

            Returns:
            int: assigned object ID.

            Side effects:
            - Updates internal tracking dictionaries.
            """
            oid = self.next_object_id
            self.next_object_id += 1
            self.objects[oid] = bbox
            self.lost[oid] = 0
            return oid

        def deregister(self, oid):
            """
            Technical description.

            Remove an object ID from tracking tables.

            Parameters:
            oid (int): object identifier to remove.

            Returns:
            None

            Side effects:
            - Modifies objects and lost dictionaries.
            """
            if oid in self.objects: del self.objects[oid]
            if oid in self.lost: del self.lost[oid]

        def update(self, detections):
            """
            Technical description.

            Update tracked objects with a new set of detections.

            Parameters:
            detections (list): list of bounding boxes (x1, y1, x2, y2).

            Returns:
            list: current tracked objects [{'id': int, 'bbox': tuple}].

            Side effects:
            - Advances lost counters and registers/deregisters objects.
            """
            if len(detections) == 0:
                remove = []
                for oid in list(self.lost.keys()):
                    self.lost[oid] += 1
                    if self.lost[oid] > self.max_lost:
                        remove.append(oid)
                for oid in remove: self.deregister(oid)
                return [{'id': oid, 'bbox': self.objects[oid]} for oid in self.objects]

            if len(self.objects) == 0:
                for d in detections: self.register(d)
                return [{'id': oid, 'bbox': bbox} for oid, bbox in self.objects.items()]

            object_ids = list(self.objects.keys())
            object_bboxes = [self.objects[oid] for oid in object_ids]

            def centroid(b):
                """
                Technical description.

                Compute centroid coordinates for a bounding box.

                Parameters:
                b (tuple): (x1, y1, x2, y2) bounding box.

                Returns:
                tuple: (cx, cy) centroid integer coordinates.

                Side effects:
                - None.
                """
                x1,y1,x2,y2 = b
                return ((x1+x2)//2, (y1+y2)//2)

            obj_centroids = [centroid(b) for b in object_bboxes]
            det_centroids = [centroid(d) for d in detections]

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
                    triples.append((i,j,D[i][j]))
            triples.sort(key=lambda x: x[2])
            for i,j,_ in triples:
                if i in matched_obj or j in matched_det: continue
                matched_obj.add(i); matched_det.add(j); assignments[i] = j

            for i,j in assignments.items():
                oid = object_ids[i]
                self.objects[oid] = detections[j]
                self.lost[oid] = 0

            for j in range(len(detections)):
                if j not in matched_det:
                    self.register(detections[j])

            for i in range(len(object_ids)):
                if i not in assignments:
                    oid = object_ids[i]
                    self.lost[oid] += 1
                    if self.lost[oid] > self.max_lost:
                        self.deregister(oid)

            return [{'id': oid, 'bbox': bbox} for oid, bbox in self.objects.items()]

    frame_q = queue.Queue(MAX_QUEUE)
    result_q = queue.Queue(MAX_QUEUE)
    stop_event = threading.Event()

    def scale_box(box_xyxy, src_w, src_h, in_w=IMGSZ, in_h=IMGSZ):
        """
        Technical description.

        Rescale coordinates from model input size back to source frame size.

        Parameters:
        box_xyxy (tuple): (x1, y1, x2, y2) in inference scale.
        src_w (int): source frame width.
        src_h (int): source frame height.
        in_w (int): inference width (default IMGSZ).
        in_h (int): inference height (default IMGSZ).

        Returns:
        tuple: (x1, y1, x2, y2) scaled to source dimensions.

        Side effects:
        - None.
        """
        x1, y1, x2, y2 = box_xyxy
        scale_x = src_w / in_w
        scale_y = src_h / in_h
        return int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y)

    def capture_thread():
        """
        Technical description.

        Capture frames continuously and push them to the frame queue.

        Parameters:
        None

        Returns:
        None

        Side effects:
        - Reads from camera hardware in a dedicated thread.
        - Populates frame_q with frames or None sentinel.
        """
        while not stop_event.is_set():
            frame = vs.read()
            ret = frame is not None
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            if not ret:
                frame_q.put(None)
                break
            frame_q.put(frame)
        frame_q.put(None)

    CLASS_THRESH = {

        0: 0.45,  # negro
        1: 0.45,  # plateado
        2: 0.2,  # rojo alto
        3: 0.6   # verde_alto
    }

    CLASS_COLORS = {

        0: (0,0,0),       # negro
        1: (192,192,192), # plateado
        2: (0,100,255),   # rojo alto
        3: (0,255,100)    # verde alto
    }

    def infer_thread():
        """
        Technical description.

        Run YOLO inference on frames from the queue and push detections.

        Parameters:
        None

        Returns:
        None

        Side effects:
        - Uses GPU/CPU for inference.
        - Writes detection results into result_q.
        """
        frame_idx = 0
        while True:
            frame = frame_q.get()
            if frame is None:
                result_q.put(None)
                break
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (IMGSZ, IMGSZ))
            if frame_idx % DETECT_EVERY == 0:
                results = model.predict(
                    small, imgsz=IMGSZ, conf=min(CLASS_THRESH.values()),
                    iou=0.45, stream=False, verbose=False
                )
                detections = []
                for res in results:
                    for box in res.boxes:
                        score = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        if score < CLASS_THRESH.get(cls_id, 0.5):
                            continue
                        xyxy = box.xyxy[0].cpu().numpy() if hasattr(box.xyxy[0], "cpu") else np.array(box.xyxy[0])
                        x1,y1,x2,y2 = scale_box(xyxy, w, h, IMGSZ, IMGSZ)
                        if estado == "rescate":
                                                  
                            if cls_id in (2, 3):
                                continue
                        if estado =="depositar":
                            if cls_id in (0, 1,2):
                                    continue

                        if estado=="depositar verde":
                            if cls_id in (0, 1, 3):
                                continue

                        detections.append({'xyxy': (x1,y1,x2,y2), 'score': score, 'cls': cls_id})
                result_q.put(('det', frame, detections))
            else:
                result_q.put(('no_det', frame, None))
            frame_idx += 1
    def select_target_from_list(boxes, estado):
            """
            Technical description.

            Filter detections according to current state to choose candidates.

            Parameters:
            boxes (list): detections containing 'cls' and 'xyxy' keys.
            estado (str): finite state guiding class preference.

            Returns:
            dict or None: selected detection or None if no match.

            Side effects:
            - None.
            """
            targets = []

            if estado == 'rescate':
                for d in boxes:
                    if d['cls'] in (0, 1):
                        targets.append(d)

            if estado == 'depositar':
                for d in boxes:
                    if d['cls'] in (3,):   # zonas red + green
                        targets.append(d)
            if estado=="depositar verde":
                for d in boxes:
                    if d['cls'] in (2,):   # zonas red + green
                        targets.append(d)
            if not targets:
                return None

            return targets[0]

    def choose_stable_target(detections, last_target,estado):
        """
        Technical description.

        Maintain target stability by selecting detection nearest to last target.

        Parameters:
        detections (list): current detection dicts.
        last_target (dict|None): previously chosen target.
        estado (str): current state for class filtering.

        Returns:
        dict or None: stable target selection.

        Side effects:
        - None.
        """
        if not detections:
            return None
        if last_target is None:
            return select_target_from_list(detections,estado)
        lx = (last_target['xyxy'][0] + last_target['xyxy'][2]) // 2
        ly = (last_target['xyxy'][1] + last_target['xyxy'][3]) // 2
        best = None
        best_dist = 1e12
        for d in detections:
            cx = (d['xyxy'][0] + d['xyxy'][2]) // 2
            cy = (d['xyxy'][1] + d['xyxy'][3]) // 2
            dist = math.hypot(cx - lx, cy - ly)
            if dist < best_dist:
                best = d
                best_dist = dist
        return best

    serial_stop_evt = threading.Event()
    def serial_monitor_local():
        """
        Technical description.

        Monitor serial port for stop command and trigger rescue exit.

        Parameters:
        None

        Returns:
        None

        Side effects:
        - Reads from serial port and updates stop_rescate flag.
        """
        nonlocal stop_rescate
        global estado   # Required to modify global state machine variable.
        while not serial_stop_evt.is_set():
            try:
                if ser.in_waiting > 0:
                    data = ser.read()

                    if data == b'\xff':
                        print("serial monitor ")
                        stop_rescate = True
                        estado = 'esperando'
                        break
                    if data == b'\xf8' and estado=="rescate":   # 248
                        print("Llego 248 -> terminar rescate y cambiar a depositar")
                        estado = 'depositar'

            except Exception as e:
                print("serial_monitor_local error:", e)
            time.sleep(0.01)


    t_serial_mon = threading.Thread(target=serial_monitor_local, daemon=True)
    t_serial_mon.start()

    def main_loop():
        """
        Technical description.

        Main rescue processing loop using detections or trackers to compute
        steering commands, render overlays, and transmit serial packets.

        Parameters:
        None

        Returns:
        None

        Side effects:
        - Serial transmissions.
        - OpenCV visualization when enabled.
        """
        global last_target_box
        global is_stopped
        global estado
        processed = 0
        start = time.time()

        mosse_available = (make_mosse() is not None)
        if mosse_available:
            print("Usando MOSSE de OpenCV (legacy).")
        else:
            print("MOSSE no disponible: usando CentroidTracker fallback.")
        centroid_tracker = CentroidTracker(max_lost=5)
        trackers = []
        last_detections = []

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
                if mosse_available:
                    trackers = []
                    for d in last_detections:
                        x1,y1,x2,y2 = d['xyxy']
                        w = x2 - x1; h = y2 - y1
                        if w <= 0 or h <= 0: continue
                        trk = make_mosse()
                        if trk is None: continue
                        ok = trk.init(frame, (x1,y1,w,h))
                        if ok: trackers.append({'tracker': trk, 'cls': d['cls'], 'score': d['score']})
                else:
                    bboxes = [d['xyxy'] for d in last_detections]
                    ct_objs = centroid_tracker.update(bboxes)
                    new_list = []
                    for obj in ct_objs:
                        bx = obj['bbox']
                        best = None; best_dist = 1e12
                        for d in last_detections:
                            cx = (d['xyxy'][0]+d['xyxy'][2])//2
                            cy = (d['xyxy'][1]+d['xyxy'][3])//2
                            ox = (bx[0]+bx[2])//2
                            oy = (bx[1]+bx[3])//2
                            dx = cx-ox; dy = cy-oy; dd = dx*dx+dy*dy
                            if dd < best_dist: best_dist = dd; best = d
                        if best is not None:
                            new_list.append({'xyxy': bx, 'cls': best['cls'], 'score': best['score']})
                        else:
                            new_list.append({'xyxy': bx, 'cls': 0, 'score': 0.0})
                    last_detections = new_list

            else:  # no_det
                if mosse_available:
                    updated = []
                    for t in trackers:
                        ok, bbox = t['tracker'].update(frame)
                        if not ok: continue
                        x, y, w, h = map(int, bbox)
                        updated.append({'xyxy': (x, y, x+w, y+h), 'cls': t['cls'], 'score': t.get('score',0.0)})
                    last_detections = updated
                else:
                    ct_objs = centroid_tracker.update([])
                    last_detections = []
                    for obj in ct_objs:
                        last_detections.append({'xyxy': obj['bbox'], 'cls': 0, 'score': 0.0})

            target = choose_stable_target(last_detections, last_target_box, estado)

            last_target_box = target

            STOP_RATIO = 0.3
            green_state=0
            speed = 0
            angle = 0

            if target:
                x1, y1, x2, y2 = target['xyxy']
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                bbox_w = x2 - x1
                bbox_h = y2 - y1
                area = bbox_w * bbox_h
                frame_w = frame.shape[1]

                error_x = cx - (frame_w // 2)
                error_norm = error_x / (frame_w // 2)

                centered = abs(error_x) < CENTER_TOLERANCE_PX
                width_ratio = bbox_w / float(frame_w)
                cv2.putText(frame, f"w_ratio={width_ratio:.3f}", (10,50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
                if estado=="depositar" or estado=="depositar verde":
                    close_enough = width_ratio >= STOP_WIDTH_RATIO_BOX
                else:
                    close_enough = width_ratio >= STOP_WIDTH_RATIO

                resume_close = width_ratio >= RESUME_WIDTH_RATIO

                if close_enough:
                    speed = 5
                    if not centered:
                        angle = int(-error_norm * 90)
                    else:
                        angle = 0
                        speed=0
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
                            estado="depositar verde"
                    if not is_stopped:
                        angle = 0
                        speed=0
                        ball_type = None
                        if target['cls'] == 0:
                            ball_type = "silver"
                        elif target['cls'] == 1:
                            ball_type = "black"
                        elif target['cls'] == 3:
                            ball_type = "green_zone"
                        elif target['cls'] == 2:
                            ball_type = "red_zone"
                        if ball_type == "silver":
                            green_state = 6
                        elif ball_type == "black":
                            green_state = 7
                        elif ball_type == "red_zone":
                            green_state = 8
                        elif ball_type == "green_zone":
                            green_state = 9
                            estado="depositar verde"

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
                    cv2.circle(frame, (cx, cy), 5, (0,0,255), -1)
                    cv2.line(frame, (frame.shape[1]//2, 0),
                             (frame.shape[1]//2, frame.shape[0]), (255,0,0), 1)
                    cv2.putText(frame,
                                f"{CLASS_NAMES[target['cls']]} {target.get('score',0):.2f} w={bbox_w}",
                                (x1, y1-6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            else:
                speed = 10
                angle = 90
                green_state=0

            output = [255, speed, 254, angle + 90, 253, green_state, 252, 0]
            ser.write(output)
            print(output)
            processed += 1
            elapsed = time.time() - start
            fps = processed / elapsed if elapsed>0 else 0.0
            cv2.putText(frame, f"FPS: {fps:.2f}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

            if not HEADLESS:
                cv2.imshow("Optimizado", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    stop_event.set(); break
            else:
                if processed % 30 == 0:
                    print(f"[HEADLESS] FPS ~ {fps:.2f}  detecciones: {len(last_detections)}")

        if not HEADLESS:
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
        tcap.join(timeout=1)
        tinf.join(timeout=1)
        t_serial_mon.join(timeout=0.5)

##################################################

### PROCESAMIENTO PRINCIPAL

##################################################

# Pipeline overview: wait state monitors serial for start code, line-follow
# state performs color segmentation and steering, and rescue state invokes
# modo_rescate for detection, tracking, and deposit logic.

##################################################

### LOOP PRINCIPAL

##################################################

# Main system loop.
# Executes continuous real-time processing.
while True:

    while estado == 'esperando':
        # ===== ETAPA: Waiting for start command =====
        frame = vs.read()
        silver_line=False
        if ser.in_waiting > 0:
            data = ser.read()
            if data == b'\xf9':
                estado = 'linea'
            ser.reset_input_buffer()

    while estado =='rescate':
        # ===== ETAPA: Rescue routine =====
        modo_rescate()

    while estado == 'linea':
        # ===== ETAPA: Line following =====
        frame = vs.read()
        frame = cv2.rotate(frame, cv2.ROTATE_180)
        frame_resized = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_NEAREST)


        # ===== ETAPA: Mask preparation =====
        kernel = np.ones((3, 3), np.uint8)
        lab = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)
        # FILTER BLACK PIXELS
        black_mask = cv2.inRange(frame_resized, lower_black, upper_black)
        black_mask[:55, :] = 0
        x_black = cv2.bitwise_and(x_com, x_com, mask=black_mask)
        x_black *= (1 - y_com)
        y_black = cv2.bitwise_and(y_com, y_com, mask=black_mask)
        green_mask=np.zeros((120,160),dtype=np.uint8)
        green_mask[90:,:]=cv2.inRange(lab[90:,:,:],lower_green,upper_green)
        cut_line = np.zeros((120,160),dtype=np.uint8)
        hsv_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2HSV)  # Convert BGR to HSV for chroma masks
        cut_line[62:,:]=cv2.inRange(frame_resized[62:,:,:], lower_black, upper_black)
        red_mask = cv2.inRange(hsv_frame, lower_red, upper_red)
        red_mask[:75,:]=0
        silver_mask = cv2.inRange(frame_resized, lower_silver_hsv, upper_silver_hsv)
        silver_mask[:75,:]=0
        # ===== ETAPA: Resultant calculation =====
        green_state = 0
        x_resultant = np.mean(x_black)
        y_resultant = np.mean(y_black)
        angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90
        speed =  40
        #print((2*np.sum(green_mask))/255)
        #print(min_square_size * 255)
        #if np.sum(cut_line)<min_line_size:
        #    angle=0

        if np.sum(green_mask) > min_square_size * 255:

            green_pixels = np.amax(green_mask, axis=0)  # for every column, if green: 1 else 0, shape = (160,)

            greenIndices = np.where(green_pixels == np.max(green_pixels))   # get indices of columns that have green
            leftIndex = greenIndices[0][0]
            rightIndex = greenIndices[0][-1]
            slicedGreen = frame_resized[60:90, leftIndex:rightIndex + 1, :]

            greenCentroidX = (rightIndex + leftIndex) / 2
            slicedBlackMaskAboveGreen = black_mask[60:90, leftIndex:rightIndex + 1]

            blackM = cv2.moments(black_mask[90:, :])

            if np.sum(black_mask[90:, :]):  # if there is black, prevents divide by 0 error
                cx_black = int(blackM["m10"] / blackM["m00"])   # get x-value of black centroid
            if (np.sum(slicedBlackMaskAboveGreen) / (255 * 30 * (rightIndex - leftIndex))) > 0.32:  # if mean is high -> square before line
                greenSquare = False
                filtered_green_mask = cv2.erode(green_mask, kernel)
                filtered_green_mask = cv2.dilate(green_mask, kernel)
                green_contours, hierarchy = cv2.findContours(filtered_green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if len(green_contours) > 1 and cx_black > leftIndex and cx_black < rightIndex and np.sum(green_mask) > (1.35 * min_square_size * 255):
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


        if np.sum(black_mask)<min_line_size:
            angle=0

        silver_contours, _ = cv2.findContours(silver_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        silver_line = False
        for contour in silver_contours:

            area = cv2.contourArea(contour)
            print(area)
            if area > 50:
                silver_line = True
                break
        red_line=False
        red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cont in red_contours:
            area = cv2.contourArea(cont)
            #print("rojo: " ,area)
            if area > 25 :
                red_line = True
                break
        if red_line == True:
            green_state=10

        output = [255, speed,
                  254, round(angle) + 90 ,
                  253, green_state,
                  252, int(silver_line)]

        #print(output)
        ser.write(output)
        if silver_line==True:
            estado='rescate'

        if ser.in_waiting > 0:

            data=ser.read()
            if data== b'\xff':
                estado='esperando'
                print("cambiando estadopa")

        #time.sleep(3)
        #print(np.sum(black_mask))
        # DEBUGS
        if debugOriginal:
            cv2.imshow('Original', frame_resized)
        if record:
            cv2.imshow('redd', red_mask)
        if debugBlack:
            cv2.imshow('Black Mask', black_mask)
        if debugGreen:
            cv2.imshow('Green Mask', green_mask)
        if debugHori:
            cv2.imshow('Silver Mask', silver_mask)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()
vs.stop()
