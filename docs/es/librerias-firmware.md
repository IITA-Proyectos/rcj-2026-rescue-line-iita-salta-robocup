# Librerias en uso (Raspberry Pi y Teensy)

Este documento resume **las librerias que realmente usa el codigo actual** y para que se usan. 

## Raspberry Pi (Python)

| Libreria | Para que se usa | En que archivo |
|---|---|---|
| `opencv-python` (`cv2`) | Captura y procesamiento de imagenes, mascaras, segmentacion, deteccion de lineas, visualizacion. En rescate tambien se usa el tracker MOSSE. | `rpi/final_rpi/Main.py`
| `numpy` | Operaciones con matrices, mascaras y calculos rapidos sobre pixeles. | `rpi/final_rpi/Main.py`
| `pyserial` (`serial`) | Comunicacion serial con la Teensy (`/dev/serial0`, 115200). | `rpi/final_rpi/Main.py`
| `camthreader` (propia) | Hilo de captura de camara con mejor rendimiento que `cv2.VideoCapture`. | `rpi/final_rpi/camthreader.py`
| `ultralytics` (YOLO) | Deteccion de objetos en modo rescate. Se usa un modelo ONNX. | `rpi/final_rpi/Main.py`
| `onnxruntime` | Backend de ejecucion para modelos `.onnx` en ARM. | `rpi/final_rpi/Main.py`
| `threading`, `queue` | Hilos y colas para separar captura, inferencia y control. | `rpi/final_rpi/Main.py`
| `math`, `time`, `os`, `sys` | Calculos, tiempos, configuracion de hilos y sistema. | `rpi/final_rpi/Main.py`

Notas importantes:
- Para el tracker MOSSE se necesita **OpenCV contrib** (`opencv-contrib-python`).
- El modelo de rescate se carga desde `MODEL_PATH = /home/iita/Desktop/zonasdepositoalta.onnx`.
- La Raspberry envia comandos a Teensy en un protocolo de bytes descrito en `rpi/Comunicacion de la raspberry y la teensy.md`.

## Teensy 4.1 (C++/Arduino)

| Libreria | Para que se usa | En que archivo |
|---|---|---|
| `Arduino.h`, `Wire.h` | Base Arduino e I2C. | `src/main.cpp`
| `drivebase.h` | Control de motores y cinematica del robot (propia del equipo). | `src/main.cpp`
| `PID.h` | Control PID en el movimiento. | `src/main.cpp`
| `elapsedMillis.h` | Temporizadores sin `delay`. | `src/main.cpp`
| `Adafruit_BNO055` y `Adafruit_Sensor` | IMU para yaw/pitch y correcciones de giro. | `src/main.cpp`
| `Adafruit_APDS9960` | Sensor de color. | `src/main.cpp`
| `NewPing` | Ultrasonidos (izquierda, frente, derecha). | `src/main.cpp`
| `VL53L0X` | Sensores ToF laterales. | `src/main.cpp`
| `Servo` | Control de servos del claw. | `src/main.cpp`
| `claw.h` | Logica del mecanismo de garra (propia del equipo). | `src/main.cpp`
| `Adafruit_I2CDevice` | Soporte I2C para dispositivos Adafruit. | `src/main.cpp`

Si agregamos o quitamos librerias, este archivo se debe actualizar junto con el codigo para que no quede desfasado.
