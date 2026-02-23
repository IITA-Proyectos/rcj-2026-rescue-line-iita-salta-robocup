import os
os.environ["QT_QPA_PLATFORM"] = "xcb"
import cv2
if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerMOSSE_create"):
    print("Legacy MOSSE disponible")
else:
    print("Legacy MOSSE NO disponible")
try:
    tr = cv2.legacy.TrackerMOSSE_create() if hasattr(cv2, "legacy") else cv2.TrackerMOSSE_create()
    print("Creado ok:", type(tr))
except Exception as e:
    print("Trackbar mosse error ejecutar rescate sin eso", e)
#!/usr/bin/env python3
import os
os.environ["OMP_NUM_THREADS"] = str(max(1, (os.cpu_count() or 4) - 1))
os.environ["MKL_NUM_THREADS"] = os.environ["OMP_NUM_THREADS"]

import cv2
import time
import threading
import queue
import numpy as np
from ultralytics import YOLO
import math
import serial

# ---- CONFIG ----
MODEL_PATH = "/home/pi/Downloads/best (4).onnx"
VIDEO_PATH = "/home/pi/Downloads/xdsdsd.mp4"
CLASS_NAMES = ['negro', 'plateado', 'rojo alto', 'verde alto']
SCORE_THRESHOLD = 0.4
IMGSZ = 256
DETECT_EVERY = 1
MAX_QUEUE = 2
DRAW_EVERY = 1
#ser = serial.Serial('/dev/serial0', 115200) #comentado porque estaba probando en mi raspberry 

HEADLESS = os.environ.get("DISPLAY") is None
CAM = "/home/pi/Downloads/xdsdsd.mp4"  
# ---- cargar modelo ----
print("Loading model:", MODEL_PATH)
model = YOLO(MODEL_PATH, task='detect')
print("Modelo cargado.")
last_target_box = None
CENTER_TOLERANCE_PX = 10
STOP_WIDTH_RATIO = 0.20        # si bbox_width / frame_width >= esto => consid. cerca (ajustar)
STOP_WIDTH_RATIO_BOX = 0.95       # si bbox_width / frame_width >= esto => consid. cerca (ajustar)

RESUME_WIDTH_RATIO = 0.18
is_stopped = False              # estado persistente: si ya estamos parados
# ---- helpers: MOSSE maker + CentroidTracker fallback ----
def make_mosse():
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
    def __init__(self, max_lost=5):
        self.next_object_id = 0
        self.objects = {}      # id -> bbox
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
cap = cv2.VideoCapture(CAM)

if not cap.isOpened():
    raise SystemExit("No se pudo abrir el video")

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
        ret, frame = cap.read()
        #frame = cv2.rotate(frame, cv2.ROTATE_180)

        if not ret:
            frame_q.put(None)
            break
        frame_q.put(frame)
    frame_q.put(None)
CLASS_COLORS = {
    0: (0,255,0),        # boxgreen
    1: (192,192,192),        # boxred
    2: (0,0,255),          # negro
    3: (0,255,0),    # plateado
    4: (0,0,255),        # rojo alto
    5: (0,255,0),        # verde alto
}

CLASS_THRESH = {
    0: 0.12,
    1: 0.12,
    2: 0.6,
    3: 0.6,
    4: 0.6,  # rojo alto
    5: 0.6,  # verde alto
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
            results = model.predict(
                small, imgsz=IMGSZ, conf=min(CLASS_THRESH.values()),
                iou=0.45, stream=False, verbose=False
            )
            detections = []
            for res in results:
                for box in res.boxes:
                    score = float(box.conf[0])
                    cls_id = int(box.cls[0])

                    # aplicar threshold  por clase
                    if score < CLASS_THRESH.get(cls_id, 0.5):
                        continue

                    xyxy = box.xyxy[0].cpu().numpy() if hasattr(box.xyxy[0], "cpu") else np.array(box.xyxy[0])
                    x1,y1,x2,y2 = scale_box(xyxy, w, h, IMGSZ, IMGSZ)
                    detections.append({
                        'xyxy': (x1,y1,x2,y2),
                        'score': score,
                        'cls': cls_id
                    })
            result_q.put(('det', frame, detections))
        else:
            result_q.put(('no_det', frame, None))
        frame_idx += 1

def select_target_from_list(boxes):
    targets = {'plateado': [], 'negro': [], 'rojo_verde': [], 'otros': []}
    for d in boxes:
        cls_id = d['cls']
        if cls_id == 3:
            targets['plateado'].append(d)
        elif cls_id == 2:
            targets['negro'].append(d)
        elif cls_id in (4,5):
            targets['rojo_verde'].append(d)
        else:
            targets['otros'].append(d)

    for k in ('plateado','rojo_verde','negro','otros'):
        if targets[k]:
            return targets[k][0]
    return None

def choose_stable_target(detections, last_target):
    if not detections:
        return None

    # primer frame o se perdiÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¿Ãƒâ€šÃ‚Â½ target
    if last_target is None:
        return select_target_from_list(detections)

    # calcular centroide de la ultima box
    lx = (last_target['xyxy'][0] + last_target['xyxy'][2]) // 2
    ly = (last_target['xyxy'][1] + last_target['xyxy'][3]) // 2

    # elegir la mejro deteccion y no cambiar sin esto el calculo este el robot vibra mucho
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
def main_loop():
    global last_target_box, is_stopped

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
        item = result_q.get()
        if item is None: break
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
        global last_target_box



        target = choose_stable_target(last_detections, last_target_box)
        last_target_box = target

        STOP_RATIO = 0.3   # 30%

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

            # condiciones
            centered = abs(error_x) < CENTER_TOLERANCE_PX
            width_ratio = bbox_w / float(frame_w)
            cv2.putText(frame, f"w_ratio={width_ratio:.3f}", (10,50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
            close_enough = width_ratio >= STOP_WIDTH_RATIO
            resume_close = width_ratio >= RESUME_WIDTH_RATIO

            deposit=True
            if deposit:
                close_enough = width_ratio >= STOP_WIDTH_RATIO_BOX

            if close_enough:
                # STOP: no avanzar, solo girar hasta centrar
                speed = 10  # velocidad para girar sin detectar nada ya que al tener pocos fps si o si es necesario girar tan despacio
                if not centered:
                    # girar hasta centrar
                    angle = int(-error_norm * 90)  # girar
                else:
                    # ya centrado, no girar
                    angle = 0
                    speed=0
                    output = [255, speed, 254, angle + 90, 253, 5, 252, 0]
                    print(output)

                    #ser.write(output)
                if not is_stopped:
                    angle = 0
                    speed=0
                    output = [255, speed, 254, angle + 90, 253, 5, 252, 0]
                    print(output)
                    #ser.write(output)
                    print(f"[STOP] width_ratio={width_ratio:.3f}, bbox_w={bbox_w}, frame_w={frame_w}")
                is_stopped = True
            else:
                # movimiento normal: girar + avanzar
                is_stopped = False
                angle = int(-error_norm * 90)
                speed = int(20 * (1 - abs(error_norm)))
                speed = min(speed, 20)

        if processed % DRAW_EVERY == 0:
            for d in last_detections:
                x1, y1, x2, y2 = d['xyxy']
                cls = d['cls']
                score = d.get('score', 0.0)
                color = CLASS_COLORS.get(cls, (0, 255, 255))
                cx, cy = (x1+x2)//2, (y1+y2)//2
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.circle(frame, (cx, cy), 5, (0,0,255), -1)
                cv2.putText(frame, f"{CLASS_NAMES[cls]} {score:.2f}",
                            (x1, y1-6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.line(frame, (frame.shape[1]//2, 0),
                     (frame.shape[1]//2, frame.shape[0]), (255,0,0), 1)
        else:  # no hay target
            speed = 10
            angle = 90
        # enviar por Serial
        output = [255, speed, 254, angle + 90, 253, 0, 252, 0]
        #print(output)
        #ser.write(output)
        # FPS
        processed += 1
        elapsed = time.time() - start
        fps = processed / elapsed if elapsed>0 else 0.0
        cv2.putText(frame, f"FPS: {fps:.2f}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

        # mostrar o headless
        if not HEADLESS:
            cv2.imshow("Optimizado", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                stop_event.set(); break
        else:
            if processed % 30 == 0:
                print(f"[HEADLESS] FPS ~ {fps:.2f}  detecciones: {len(last_detections)}")

    cap.release()
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
    tcap.join(timeout=1)
    tinf.join(timeout=1)