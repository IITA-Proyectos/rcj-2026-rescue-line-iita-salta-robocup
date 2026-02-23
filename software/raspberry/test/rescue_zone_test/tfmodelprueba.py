""" estoy probando el codigo este con otro formato diferente al que venimos trabajando tflite NMS que ya incluye filtrado por score como el onnx lo que hace que no tenga que cambiar nada de la logica"""

global last_target_box
last_target_box = None
global is_stopped
global estado, ser
stop_rescate = False
estado="rescate"
import cv2
if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerMOSSE_create"):
    print("ok")
else:
    print("tracker no funciona")
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


MODEL_PATH = "/home/pi/Downloads/best_float32 (1).tflite"
CLASS_NAMES = ['negro', 'plateado', 'rojo alto', 'verde_alto']
SCORE_THRESHOLD = 0.45
IMGSZ = 256
DETECT_EVERY = 1
MAX_QUEUE = 2
DRAW_EVERY = 1
HEADLESS = False
VIDEO_PATH = "/home/pi/Downloads/xdsdsd.mp4"  
vs = cv2.VideoCapture(VIDEO_PATH)

#ddummy para simular mi serial ya que no tengo nada al serial de la raspberry
class DummySerial:
    in_waiting = 0
    def read(self, n=1):
        return b''
    def write(self, data):
        pass
ser = globals().get('ser', None) or DummySerial()

print("tflite cargado:", MODEL_PATH)
try:
    from tflite_runtime.interpreter import Interpreter as TFLiteInterpreter
except Exception:
    import tensorflow as tf
    TFLiteInterpreter = tf.lite.Interpreter

NUM_THREADS = 2
try:
    interpreter = TFLiteInterpreter(model_path=MODEL_PATH, num_threads=NUM_THREADS)
except TypeError:
    interpreter = TFLiteInterpreter(model_path=MODEL_PATH)
    try:
        interpreter.set_num_threads(NUM_THREADS)
    except Exception:
        pass
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()[0]
output_details = interpreter.get_output_details()[0]
print("TFLite input:", input_details)
print("TFLite output:", output_details)

print("Modelo cargado.")
last_target_box = None
CENTER_TOLERANCE_PX = 10
STOP_WIDTH_RATIO = 0.20
STOP_WIDTH_RATIO_BOX = 0.93
red_deposited = False
green_deposited = False
RESUME_WIDTH_RATIO = 0.18
is_stopped = False

def make_mosse():
    return None

class CentroidTracker:
    def __init__(self, max_lost=5):
        self.next_object_id = 0
        self.objects = {}
        self.lost = {}
        self.max_lost = max_lost

    def register(self, bbox):
        oid = self.next_object_id
        self.next_object_id += 1
        self.objects[oid] = bbox
        self.lost[oid] = 0
        return oid

    def deregister(self, oid):
        if oid in self.objects: del self.objects[oid]
        if oid in self.lost: del self.lost[oid]

    def update(self, detections):
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
    x1, y1, x2, y2 = box_xyxy
    scale_x = src_w / in_w
    scale_y = src_h / in_h
    return int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y)

def capture_thread():
    while not stop_event.is_set():
        ret, frame = vs.read()
        if not ret or frame is None:
            frame_q.put(None)
            break

        frame_q.put(frame)
    frame_q.put(None)

CLASS_THRESH = {
    0: 0.45,  # negro
    1: 0.45,  # plateado
    2: 0.2,   # rojo alto
    3: 0.6    # verde_alto
}

CLASS_COLORS = {
    0: (0,0,0),       # negro
    1: (192,192,192), # plateado
    2: (0,100,255),   # rojo alto
    3: (0,255,100)    # verde alto
}

def infer_thread():
    frame_idx = 0
    while True:
        frame = frame_q.get()
        if frame is None:
            result_q.put(None)
            break
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (IMGSZ, IMGSZ))

        if frame_idx % DETECT_EVERY == 0:
            # --- PREPROCESS para el interpreter ---
            img = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            # Ultralytics export con nms=True suele esperar floats 0..1
            if np.issubdtype(input_details['dtype'], np.floating):
                inp = (img.astype(np.float32) / 255.0)[np.newaxis, ...].astype(input_details['dtype'])
            else:
                inp = img[np.newaxis, ...].astype(input_details['dtype'])

            # inferencia tflite
            interpreter.set_tensor(input_details['index'], inp)
            interpreter.invoke()
            # salida con NMS: shape (1, N, 6) -> [x1,y1,x2,y2,score,class]
            out = interpreter.get_tensor(output_details['index'])[0]

            detections = []
            for det in out:
                x1, y1, x2, y2, score, cls_raw = det
                score = float(score)
                cls_id = int(round(float(cls_raw)))

                if score < CLASS_THRESH.get(cls_id, 0.5):
                    continue

                x1 *= IMGSZ; y1 *= IMGSZ; x2 *= IMGSZ; y2 *= IMGSZ

                sx1, sy1, sx2, sy2 = scale_box((x1, y1, x2, y2), w, h, IMGSZ, IMGSZ)

                if estado == "rescate":
                    if cls_id in (2, 3):
                        continue
                if estado == "depositar":
                    if cls_id in (0, 1, 2):
                        continue
                if estado == "depositar verde":
                    if cls_id in (0, 1, 3):
                        continue

                detections.append({'xyxy': (sx1, sy1, sx2, sy2), 'score': score, 'cls': cls_id})

            result_q.put(('det', frame, detections))
        else:
            result_q.put(('no_det', frame, None))

        frame_idx += 1

def select_target_from_list(boxes, estado):
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
    if not targets:
        return None
    return targets[0]

def choose_stable_target(detections, last_target, estado):
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
    global stop_rescate

    global estado
    while not serial_stop_evt.is_set():
        try:
            if ser.in_waiting > 0:
                data = ser.read()
                if data == b'\xff':
                    print("serial monitor ")
                    stop_rescate = True
                    estado = 'esperando'
                    break
                if data == b'\xf8' and estado == "rescate":
                    print("Llego 248 -> terminar rescate y cambiar a depositar")
                    estado = 'depositar'
        except Exception as e:
            print("serial_monitor_local error:", e)
        time.sleep(0.01)

t_serial_mon = threading.Thread(target=serial_monitor_local, daemon=True)
t_serial_mon.start()

def main_loop():
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