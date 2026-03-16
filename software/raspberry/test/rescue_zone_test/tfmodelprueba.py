##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# tensorflow: model loading and inference for object detection.
import tensorflow as tf
# numpy: tensor manipulation and type conversions.
import numpy as np
# cv2: image loading and resizing.
import cv2
# time: measure inference latency.
import time

##################################################

### CONFIGURACION GLOBAL

##################################################

MODEL_PATH = "saved_model"   # Directory containing TensorFlow SavedModel.
IMGSZ = 256                  # Target input size.
TEST_IMAGE = "imagen.jpg"    # Sample image file.
WARMUP_ITERS = 3             # Warmup runs before timing.

##################################################

### FUNCIONES AUXILIARES

##################################################

def load_tf_model():
    """
    Technical description.

    Load TensorFlow SavedModel for detection tasks.

    Parameters:
    None

    Returns:
    tf.function: callable detection function.

    Side effects:
    - Reads model files from disk.
    """
    model = tf.saved_model.load(MODEL_PATH)
    return model.signatures["serving_default"]


def preprocess_image(path):
    """
    Technical description.

    Load image from disk, resize to IMGSZ, and expand batch dimension.

    Parameters:
    path (str): image path.

    Returns:
    tf.Tensor: preprocessed image tensor of shape (1, IMGSZ, IMGSZ, 3).

    Side effects:
    - Reads image file from disk.
    """
    img = cv2.imread(path)
    if img is None:
        return None
    img = cv2.resize(img, (IMGSZ, IMGSZ))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32)
    return tf.convert_to_tensor(img[None, ...])


def run_inference(detect_fn, tensor):
    """
    Technical description.

    Execute TensorFlow detection on preprocessed tensor.

    Parameters:
    detect_fn (tf.function): detection signature.
    tensor (tf.Tensor): input image tensor.

    Returns:
    dict: model outputs.

    Side effects:
    - Uses CPU/GPU resources for inference.
    """
    return detect_fn(tensor)


def warmup(detect_fn, tensor):
    """
    Technical description.

    Perform warmup inferences to stabilize performance.

    Parameters:
    detect_fn (tf.function): detection signature.
    tensor (tf.Tensor): input tensor.

    Returns:
    None

    Side effects:
    - Executes inference multiple times.
    """
    for _ in range(WARMUP_ITERS):
        run_inference(detect_fn, tensor)


##################################################

### PROCESAMIENTO PRINCIPAL

##################################################

# Pipeline: load TF model, preprocess image, warm up, run timed inference,
# and print output keys with timing.

##################################################

### LOOP PRINCIPAL

##################################################

# Main system loop.
# Executes continuous real-time processing.
def main():
    """
    Technical description.

    Load TensorFlow detection model, warm up, run inference on TEST_IMAGE,
    and print latency plus output tensors.

    Parameters:
    None

    Returns:
    None

    Side effects:
    - Disk I/O for model and image.
    - TensorFlow execution.
    - Prints results to stdout.
    """
    detect_fn = load_tf_model()
    tensor = preprocess_image(TEST_IMAGE)
    if tensor is None:
        print("Image not found.")
        return

    warmup(detect_fn, tensor)
    start = time.time()
    outputs = run_inference(detect_fn, tensor)
    elapsed = time.time() - start
    print(f"Inference time: {elapsed*1000:.2f} ms")
    for k, v in outputs.items():
        print(k, v.shape)


if __name__ == "__main__":
    main()
