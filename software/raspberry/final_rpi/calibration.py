import cv2
from camthreader import *

vs = WebcamVideoStream(src=0).start()

rgb_frame = vs.read()
hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)


def rgbclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x,y,rgb_frame[y][x])


def hsvclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x,y,hsv_frame[y][x])

def labclick(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDBLCLK:
            print("Valores LAB:", lab_frame[y, x])

cv2.namedWindow('RGB')
cv2.setMouseCallback('RGB', rgbclick)
cv2.namedWindow('HSV')
cv2.setMouseCallback('HSV', hsvclick)

while True:
    rgb_frame = vs.read()
    lab_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2Lab)

    cv2.namedWindow('LAB')
    cv2.setMouseCallback('LAB', labclick)

    

    rgb_frame = vs.read()
    #rgb_frame[:25, :, :] = 255  # block out horizon
    hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)
    rgb_frame = cv2.line(rgb_frame, (80, 0), (80, 120), (255, 0, 0), 1)
    hsv_frame = cv2.line(hsv_frame, (80, 0), (80, 120), (255, 0, 0), 1)
    cv2.imshow("RGB", rgb_frame)
    cv2.imshow("HSV", hsv_frame)
    cv2.imshow("LAB", lab_frame)
    
    if cv2.waitKey(1) == 27:
        break  # esc to quit

vs.stop()
cv2.destroyAllWindows()