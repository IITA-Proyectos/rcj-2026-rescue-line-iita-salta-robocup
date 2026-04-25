##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# OpenCV: image display and mouse event handling.
import cv2
# os: filesystem path utilities for image loading.
import os

##################################################

### CONFIGURACION GLOBAL

##################################################

IMAGE_DIR = "imagenes"  # Directory containing images to annotate.
current_image = None     # Current image frame shown on screen.
points = []              # Collected annotation points.

##################################################

### FUNCIONES AUXILIARES

##################################################

def mouse_callback(event, x, y, flags, param):
    """
    Technical description.

    Capture mouse clicks to store annotation points and draw markers.

    Parameters:
    event (int): OpenCV mouse event.
    x (int): X coordinate.
    y (int): Y coordinate.
    flags (int): OpenCV event flags.
    param (Any): extra parameter (unused).

    Returns:
    None

    Side effects:
    - Modifies global points list.
    - Draws circles on the displayed image.
    """
    global current_image, points
    if event == cv2.EVENT_LBUTTONDOWN and current_image is not None:
        points.append((x, y))
        cv2.circle(current_image, (x, y), 3, (0, 255, 0), -1)
        cv2.imshow("Annotator", current_image)

##################################################

### PROCESAMIENTO PRINCIPAL

##################################################

# Pipeline: load images from IMAGE_DIR, present them for manual point
# annotation, and print collected coordinates after each image.

##################################################

### LOOP PRINCIPAL

##################################################

# Main system loop.
# Executes continuous real-time processing.
def main():
    """
    Technical description.

    Iterate through images in IMAGE_DIR, allow manual point annotation,
    and print collected points per image.

    Parameters:
    None

    Returns:
    None

    Side effects:
    - Opens OpenCV window and waits for user input.
    - Prints annotation results to stdout.
    """
    global current_image, points
    cv2.namedWindow("Annotator")
    cv2.setMouseCallback("Annotator", mouse_callback)

    for fname in sorted(os.listdir(IMAGE_DIR)):
        path = os.path.join(IMAGE_DIR, fname)
        current_image = cv2.imread(path)
        if current_image is None:
            continue
        points = []
        cv2.imshow("Annotator", current_image)
        key = cv2.waitKey(0)
        if key == 27:  # ESC to quit
            break
        print(f"{fname}: {points}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
