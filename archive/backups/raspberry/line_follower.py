import cv2
from camthreader import *
import numpy as np
import math
import time
import serial
import sys


debugOriginal = True
debugBlack = True
debugGreen = True
debugBlue = False
debugHori = False
record = False
noise_blob_threshold = 16
min_square_size = 150
min_line_size =6000
fixed_angle_value = 0
fixed_angle_active = False
fixed_angle_start_time = 0
estado='esperando'

vs = WebcamVideoStream(src=0).start()
ser = serial.Serial('/dev/serial0', 115200)
lower_black = np.array([0, 0,0])  # BGR
upper_black = np.array([90, 65, 50])
lower_green = np.array([86,102, 96])  # lab
upper_green = np.array([201,118, 117])
lower_silver_hsv = np.array([90, 5, 35])  # Valores en espacio HSV para detectar el plateado
upper_silver_hsv = np.array([140, 115, 210])  # Ajusta estos valores si es necesario
last_angles = []

test_frame = vs.read()

width, height = 160, 120
print(width, height)

cam_x = width / 2 - 1   # 79 ~ middle column
cam_y = height - 1      # 119 ~ bottom row

timer_active = False
green_output_duration = 1  # DuraciÃƒÆ’Ã‚Â³n en segundos para mostrar el estado
green_output_cooldown_duration = 2  # DuraciÃƒÆ’Ã‚Â³n en segundos para estar en 0
green_state_final = 0
timer_active = False
timer_start_time = 0

# GET X AND Y ARRAYS
# scaled by frame dimensions, use this for filtering pixels
x_com = np.zeros(shape=(height, width))
y_com = np.zeros(shape=(height, width))

for i in range(height):
    for j in range(width):
        x_com[i][j] = (j - cam_x) / (width / 2)   # [-1, 1]
        y_com[i][j] = (cam_y - i) / height        # [0, 1]

while True:
    
    while estado == 'esperando':
        if ser.in_waiting > 0:
            data = ser.read(1)
            if data == b'\xf9':
                estado = 'linea'
            ser.reset_input_buffer()

            
    while estado == 'linea':

        frame = vs.read()
        frame = cv2.rotate(frame, cv2.ROTATE_180)
        frame_resized = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_NEAREST)


        # Luego, recortar la parte superior
        #cv2.imshow("frameresize",frame_resized)
        kernel = np.ones((3, 3), np.uint8)
        lab = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)
        # FILTER BLACK PIXELS
        black_mask = cv2.inRange(frame_resized, lower_black, upper_black)
        black_mask[:75, :] = 0
        x_black = cv2.bitwise_and(x_com, x_com, mask=black_mask)
        x_black *= (1 - y_com)
        y_black = cv2.bitwise_and(y_com, y_com, mask=black_mask)
        green_mask=np.zeros((120,160),dtype=np.uint8)
        green_mask[90:,:]=cv2.inRange(lab[90:,:,:],lower_green,upper_green)
        cut_line = np.zeros((120,160),dtype=np.uint8)
        hsv_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2HSV)  # Convertir la imagen de BGR a HSV
        cut_line[62:,:]=cv2.inRange(frame_resized[62:,:,:], lower_black, upper_black)
        silver_mask = cv2.inRange(hsv_frame, lower_silver_hsv, upper_silver_hsv)
        silver_mask[:80,:]=0
        # CALCULATE RESULTANT
        green_state = 0
        x_resultant = np.mean(x_black)
        y_resultant = np.mean(y_black)
        angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90
        speed =  20
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
            #print(area)

            if area > 1500 :  # Define un umbral para el ÃƒÆ’Ã‚Â¡rea para evitar ruido
                silver_line = True
                break
        output = [255, speed,
                  254, round(angle) + 90 ,
                  253, green_state,
                  252, int(silver_line)]  # 1 si se detecta la lÃƒÆ’Ã‚Â­nea plateada, 0 en caso contrario

        print(output)
        ser.write(output)
        if silver_line==True:
            estado='rescate'
        while estado=='rescate':
            if ser.in_waiting > 0:
                data=ser.read()
            if data== b'\xff':
                estado='esperando'

        if ser.in_waiting > 0:

            data=ser.read()
            if data== b'\xff':
                estado='esperando'
                
        #time.sleep(3)
        #print(np.sum(black_mask))
        # DEBUGS
        if debugOriginal:
            cv2.imshow('Original', frame_resized)

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