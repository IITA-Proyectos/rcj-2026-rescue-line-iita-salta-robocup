##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# time: performance measurement for inference warmup.
import time
# numpy: array handling for image preprocessing.
import numpy as np
# cv2: image decoding and color conversions.
import cv2
# ultralytics.YOLO: model loading and inference.
from ultralytics import YOLO

##################################################

### CONFIGURACION GLOBAL

##################################################

MODEL_PATH = "zonasdepositoalta.onnx"  # Path to ONNX detection model.
IMGSZ = 256                            # Inference image size.
WARMUP_ITERS = 3                       # Number of warmup passes.
TEST_IMAGE = "imagen.jpg"              # Sample image for testing.

##################################################

### FUNCIONES AUXILIARES

##################################################

def load_model():
    """
    Technical description.

    Load YOLO model from ONNX file for detection tasks.

    Parameters:
    None

    Returns:
    YOLO: loaded model instance.

    Side effects:
    - Reads model file from disk.
    """
    return YOLO(MODEL_PATH, task="detect")


def preprocess_image(path):
    """
    Technical description.

    Read image from disk and resize to IMGSZ square.

    Parameters:
    path (str): file path to the image.

    Returns:
    ndarray: resized image ready for inference.

    Side effects:
    - Disk read via OpenCV.
    """
    img = cv2.imread(path)
    if img is None:
        return None
    return cv2.resize(img, (IMGSZ, IMGSZ))


def run_inference(model, image):
    """
    Technical description.

    Execute model prediction on provided image.

    Parameters:
    model (YOLO): loaded YOLO model.
    image (ndarray): preprocessed image.

    Returns:
    list: inference results.

    Side effects:
    - Uses CPU/GPU for model inference.
    """
    return model.predict(image, imgsz=IMGSZ, conf=0.25, iou=0.45, stream=False, verbose=False)


def warmup(model, image):
    """
    Technical description.

    Perform multiple inference passes to stabilize performance.

    Parameters:
    model (YOLO): loaded YOLO model.
    image (ndarray): preprocessed image.

    Returns:
    None

    Side effects:
    - Executes inference WARMUP_ITERS times.
    """
    for _ in range(WARMUP_ITERS):
        run_inference(model, image)


##################################################

### PROCESAMIENTO PRINCIPAL

##################################################

# Pipeline: load model, preprocess sample image, run warmup passes, then
# execute a timed inference and print results.

##################################################

### LOOP PRINCIPAL

##################################################

# Main system loop.
# Executes continuous real-time processing.
def main():
    """
    Technical description.

    Load YOLO model, warm it up, run timed inference on TEST_IMAGE, and
    print detections along with latency.

    Parameters:
    None

    Returns:
    None

    Side effects:
    - File I/O for model and image.
    - Inference execution.
    - Prints timing and detections to stdout.
    """
    model = load_model()
    img = preprocess_image(TEST_IMAGE)
    if img is None:
        print("Image not found.")
        return

    warmup(model, img)
    start = time.time()
    results = run_inference(model, img)
    elapsed = time.time() - start
    print(f"Inference time: {elapsed*1000:.2f} ms")
    for res in results:
        print(res)


if __name__ == "__main__":
    main()
