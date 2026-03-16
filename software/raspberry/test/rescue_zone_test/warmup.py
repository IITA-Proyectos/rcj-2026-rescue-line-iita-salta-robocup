##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# time: measure warmup and inference duration.
import time
# ultralytics.YOLO: detection model for performance testing.
from ultralytics import YOLO
# numpy: array construction for synthetic inputs.
import numpy as np

##################################################

### CONFIGURACION GLOBAL

##################################################

MODEL_PATH = "zonasdepositoalta.onnx"  # ONNX model path.
IMGSZ = 256                            # Inference size.
WARMUP_ITERS = 5                       # Warmup passes.

##################################################

### FUNCIONES AUXILIARES

##################################################

def load_model():
    """
    Technical description.

    Load YOLO model from ONNX file for detection benchmarking.

    Parameters:
    None

    Returns:
    YOLO: loaded model instance.

    Side effects:
    - Reads model file from disk.
    """
    return YOLO(MODEL_PATH, task="detect")


def synthetic_image():
    """
    Technical description.

    Generate a blank synthetic image for warmup runs.

    Parameters:
    None

    Returns:
    ndarray: zeroed image of shape (IMGSZ, IMGSZ, 3).

    Side effects:
    - None.
    """
    return np.zeros((IMGSZ, IMGSZ, 3), dtype=np.uint8)


def warmup(model, img):
    """
    Technical description.

    Execute multiple inference passes to stabilize performance.

    Parameters:
    model (YOLO): detection model.
    img (ndarray): input image.

    Returns:
    None

    Side effects:
    - Repeated inference calls.
    """
    for _ in range(WARMUP_ITERS):
        model.predict(img, imgsz=IMGSZ, conf=0.25, iou=0.45, stream=False, verbose=False)


##################################################

### PROCESAMIENTO PRINCIPAL

##################################################

# Pipeline: load model, create synthetic image, warm up, then run one timed
# inference for latency measurement.

##################################################

### LOOP PRINCIPAL

##################################################

# Main system loop.
# Executes continuous real-time processing.
def main():
    """
    Technical description.

    Benchmark ONNX YOLO model by warming up on synthetic data and timing a
    single inference pass.

    Parameters:
    None

    Returns:
    None

    Side effects:
    - Disk I/O for model.
    - Inference execution and timing printout.
    """
    model = load_model()
    img = synthetic_image()
    warmup(model, img)
    start = time.time()
    model.predict(img, imgsz=IMGSZ, conf=0.25, iou=0.45, stream=False, verbose=False)
    elapsed = time.time() - start
    print(f"Inference time: {elapsed*1000:.2f} ms")


if __name__ == "__main__":
    main()
