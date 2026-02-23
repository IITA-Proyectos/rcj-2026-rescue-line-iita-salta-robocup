import serial
import time

ser = serial.Serial("/dev/serial0", 115200, timeout = 0)

while True:
    ser.write(b'a')
    time.sleep(1)
    if ser.in_waiting > 0:
        a = ser.readline().rstrip()
        print(a)
    