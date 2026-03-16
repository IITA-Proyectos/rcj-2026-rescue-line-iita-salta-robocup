##################################################

### IMPORTACION DE LIBRERIAS

##################################################

# OpenCV: image capture, color space conversions, drawing and UI callbacks.
import cv2
# camthreader: threaded webcam acquisition for non-blocking frame reads.
from camthreader import *

##################################################

### CONFIGURACION GLOBAL

##################################################

# Threaded video stream for continuous frame acquisition.
vs = WebcamVideoStream(src=0).start()

# Frame buffers used across callbacks for on-click inspection.
rgb_frame = vs.read()
hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)


def rgbclick(event, x, y, flags, param):
    """
    Print BGR values of the clicked pixel on the RGB window.

    Parameters:
    event (int): OpenCV mouse event identifier.
    x (int): X coordinate of the click.
    y (int): Y coordinate of the click.
    flags (int): Event flags provided by OpenCV.
    param (Any): Extra callback parameter (unused).

    Returns:
    None: Outputs pixel values to standard output.

    Side effects:
    - stdout: prints diagnostic pixel values.
    """
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x, y, rgb_frame[y][x])


def hsvclick(event, x, y, flags, param):
    """
    Print HSV values of the clicked pixel on the HSV window.

    Parameters:
    event (int): OpenCV mouse event identifier.
    x (int): X coordinate of the click.
    y (int): Y coordinate of the click.
    flags (int): Event flags provided by OpenCV.
    param (Any): Extra callback parameter (unused).

    Returns:
    None: Outputs pixel values to standard output.

    Side effects:
    - stdout: prints diagnostic pixel values.
    """
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x, y, hsv_frame[y][x])


def labclick(event, x, y, flags, param):
    """
    Print Lab values of the clicked pixel on the LAB window.

    Parameters:
    event (int): OpenCV mouse event identifier.
    x (int): X coordinate of the click.
    y (int): Y coordinate of the click.
    flags (int): Event flags provided by OpenCV.
    param (Any): Extra callback parameter (unused).

    Returns:
    None: Outputs pixel values to standard output.

    Side effects:
    - stdout: prints diagnostic pixel values.
    """
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print("Valores LAB:", lab_frame[y, x])


##################################################

### PROCESAMIENTO PRINCIPAL

##################################################

# Pipeline: set up interactive windows, update frames, convert color spaces,
# render reference lines, and display outputs for manual threshold calibration.

cv2.namedWindow('RGB')
cv2.setMouseCallback('RGB', rgbclick)
cv2.namedWindow('HSV')
cv2.setMouseCallback('HSV', hsvclick)

##################################################

### LOOP PRINCIPAL

##################################################

# Main system loop.
# Executes continuous real-time processing.
while True:
    # ===== ETAPA: Acquisition and conversion =====
    rgb_frame = vs.read()
    lab_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2Lab)

    cv2.namedWindow('LAB')
    cv2.setMouseCallback('LAB', labclick)

    rgb_frame = vs.read()
    #rgb_frame[:25, :, :] = 255  # block out horizon
    # ===== ETAPA: Color conversion =====
    hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)
    # ===== ETAPA: Reference overlays =====
    rgb_frame = cv2.line(rgb_frame, (80, 0), (80, 120), (255, 0, 0), 1)
    hsv_frame = cv2.line(hsv_frame, (80, 0), (80, 120), (255, 0, 0), 1)
    # ===== ETAPA: Visualization =====
    cv2.imshow("RGB", rgb_frame)
    cv2.imshow("HSV", hsv_frame)
    cv2.imshow("LAB", lab_frame)

    if cv2.waitKey(1) == 27:
        break  # esc to quit

vs.stop()
cv2.destroyAllWindows()
