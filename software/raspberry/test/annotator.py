import cv2
from camthreader import *
import os

### CAMTHEREADER ###


vs = WebcamVideoStream(src=0).start()

rgb_frame = vs.read()
hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)


def rgbclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x,y,rgb_frame[y][x])


def hsvclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x,y,hsv_frame[y][x])


def click_event(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        frame = vs.read()
        img_name = f"capture_{x}_{y}.png"
        img_path = os.path.join(img_name)
        cv2.imwrite(img_path, frame)

cv2.namedWindow('RGB')
cv2.setMouseCallback('RGB', rgbclick)
cv2.namedWindow('HSV')
cv2.setMouseCallback('HSV', hsvclick)
cv2.namedWindow('Para-hacer-click')
cv2.setMouseCallback('Para-hacer-click', click_event)
while True:
    rgb_frame = vs.read()
    hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)
    rgb_frame = cv2.line(rgb_frame, (80, 0), (80, 120), (255, 0, 0), 1)
    hsv_frame = cv2.line(hsv_frame, (80, 0), (80, 120), (255, 0, 0), 1)
    cv2.imshow("RGB", rgb_frame)
    cv2.imshow("HSV", hsv_frame)
    if cv2.waitKey(1) == 27:
        break  # esc to quit

vs.stop()
cv2.destroyAllWindows()

