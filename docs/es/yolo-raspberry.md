# Raspberry + YOLO (rescate)

Este documento explica como funciona la vision en la Raspberry Pi, como se integra YOLO y por que se eligio ONNX Runtime en ARM. Esta basado en:
- `rpi/final_rpi/Main.py`
- Modelos en `rpi/AI/`

## Objetivo

- Seguir linea en tiempo real (vision clasica).
- En rescate, detectar pelotas y zonas con YOLO.
- Enviar comandos a la Teensy por serial (ver `rpi/Comunicacion de la raspberry y la teensy.md`).

## Hardware

- Raspberry Pi 4 Model B 8GB
- Camara USB 2MP WIDE 140°

## Estados del programa (Main.py)

- `esperando`: espera byte `0xF9` desde la Teensy para empezar.
- `linea`: seguimiento de linea y deteccion de verdes/rojo/plateado.
- `rescate`: YOLO + tracking para pelotas.
- `depositar`: YOLO para zonas de deposito.
- `depositar verde`: sub-estado para la zona verde.

## Reglamento 2026 - Zona de rescate (resumen operativo)

Resumen basado en el reglamento 2026:
- La **zona de evacuacion** mide **120 cm x 90 cm** y tiene paredes de al menos 10 cm.
- La entrada tiene una **cinta plateada reflectiva** (25 mm x 250 mm).
- La salida tiene una **cinta negra** (25 mm x 250 mm).
- La **linea negra termina** en la entrada y **vuelve a comenzar** en la salida.
- Hay **dos zonas altas** de evacuacion: una **roja** (victima muerta) y una **verde** (victimas vivas).
- Las zonas son **triangulos rectos de 30 cm x 30 cm** con paredes de **6 cm** y centro hueco.
- Las zonas pueden estar en cualquier esquina que no sea entrada/salida.
- Puede haber **obstaculos o speed bumps** dentro de la zona, pero **no suman puntos**.
- Puede haber **luces LED blancas** en la parte alta de las paredes.
- Las victimas son esferas de 4-5 cm, con masa descentrada (max 80 g):
  - **Vivas**: plateadas, reflectivas y conductoras.
  - **Muerta**: negra, no conductora.
- Se pueden colocar **victimas falsas** y el robot debe ignorarlas.




## Pipeline de vision en linea

1. Captura con `camthreader` y rotacion 180.
2. Resize a `160x120`.
3. Mascaras:
   - Negro (BGR) para linea.
   - Verde (LAB) para cuadrados.
   - Rojo (HSV) para linea roja.
   - Plateado (HSV) para linea de rescate.
4. Se calcula angulo por centroides y se envia:
   - `speed`, `angle`, `green_state`, `silver_line`.

## Pipeline de rescate (YOLO)

- Modelo ONNX cargado con `ultralytics`.
- Imagen de entrada: `IMGSZ = 256`.
- Inferencia cada `DETECT_EVERY` frames.
- Hilos:
  - `capture_thread` (camara)
  - `infer_thread` (YOLO)
  - `serial_monitor_local`
- Tracking:
  - MOSSE si esta disponible en OpenCV contrib.
  - Si no, fallback con `CentroidTracker`.

## Clases del modelo

En rescate se usan 4 clases:
- `0`: negro (pelota negra)
- `1`: plateado (pelota plateada)
- `2`: rojo alto (zona roja)
- `3`: verde alto (zona verde)

## Modelos y versiones (carpeta `rpi/AI`)

| Fecha | Archivo | Notas |
|---|---|---|
| 11-09 | `roboliga.onnx` | Primeras pruebas de rescate. |
| 11-09 | `Roboliga 2025.v5-rescate.yolov8.zip` | Dataset Version exportada YOLOv8. |
| 20-11 | `depositoalto.onnx` | Pruebas de zonas. |
| 20-11 | `Roboliga 2025.v12-zonas-alta.yolov8.zip` | Dataset Version exportada YOLOv8. |
| 23-11 | `zonasdepositoalta.onnx` | Modelo usado en `Main.py`. |
| 23-11 | `Roboliga 2025.v15-sinboxes-bajas.yolov8.zip` | Dataset Version exportada YOLOv8. |



## Dependencias (Raspberry Pi)

- `opencv-python` + `opencv-contrib-python`
- `numpy`
- `pyserial`
- `ultralytics`
- `onnxruntime` (backend para ONNX en ARM)

## Por que ONNX Runtime en ARM

Se probaron varias opciones (tflite, yolov8n, yolov8_ncnn, FOMO) y **ONNX Runtime fue la que dio mejores FPS en nuestra Raspberry**. Por eso el modelo final se exporta a `.onnx` y se corre con `ultralytics` + `onnxruntime`.

### Precision y cuantizacion

- Los modelos **ONNX actuales estan en FP32** (no INT8).
- Se intento cuantizar (INT8) en un entorno muy similar al real, pero **la precision empeoro** y los resultados no fueron confiables.
- En esta etapa se priorizo **robustez y precision** por encima del FPS.

#### Cuantizacion

La cuantizacion reduce el costo de computo y memoria cambiando el tipo de dato:
- **FP32**: 32 bits, mas precision, mas costo.
- **FP16/INT8**: menos bits, mas velocidad y menor memoria, pero puede perder precision.

En vision, la cuantizacion puede afectar:
- Bordes y detalles finos.
- Confianza de detecciones.
- Calibracion de thresholds.

Por eso se dejo en FP32 hasta lograr un set de calibracion confiable y un comportamiento estable en pista.

### CPU-only (sin acelerador)

No se usa ningun acelerador de IA (no NPU, no TPU, no GPU). **Todo corre en CPU** de la Raspberry Pi.  
Esto limita el FPS maximo y obliga a optimizar el pipeline.

### Optimizacion y multihilo

Para alcanzar la maxima velocidad posible se optimizo el programa y se uso multihilo:
- Hilo de **captura** de camara.
- Hilo de **inferencia** (YOLO).
- Hilo de **serial** (estado y sincronizacion con Teensy).

Esto permite procesar en paralelo y **mantener sincronizados** los estados sin perder frames, lo que mejora la estabilidad y el rendimiento general.

## Benchmarks externos (referencia)

A continuacion se incluyen graficos externos que comparan runtimes en Raspberry Pi 4B. No son nuestros modelos, pero sirven como referencia del rendimiento relativo entre ONNX Runtime, TFLite y otros runtimes en ARM.

### Paper: Performance Characterization of using Quantization for DNN Inference on Edge Devices (Raspberry Pi 4B)

![Raspberry Pi 4B - Single-stream latency](imagenes/benchmarks/rpi4b_mobilenetv2_single_stream_latency.png)

![Raspberry Pi 4B - Multi-stream latency](imagenes/benchmarks/rpi4b_mobilenetv2_multistream_latency.png)

![Raspberry Pi 4B - Offline images/sec](imagenes/benchmarks/rpi4b_mobilenetv2_offline_ips.png)

### Otros datos publicos (referencia rapida)

| Metodo | Referencia | Dato aproximado |
|---|---|---|
| YOLOv8n (NCNN) | Qengineering (Raspberry Pi 4 1950MHz) | ~3.1 FPS (YOLOv8n 640) |
| FOMO | Edge Impulse (Raspberry Pi 4) | ~60 FPS (160x160, MobileNetV2 0.1) |

> Nota: estos valores **no son comparables 1:1** porque cambian modelos, resoluciones, datasets y configuraciones. Se usan solo como referencia externa.

## Como correr el main de Raspberry

1. Copiar el modelo ONNX a la Raspberry (ej: `/home/iita/Desktop/zonasdepositoalta.onnx`).
2. Instalar dependencias de Python.
3. Ejecutar `Main.py`.

## Ajustes rapidos de rendimiento

- `IMGSZ`: bajar resolucion aumenta FPS pero reduce precision.
- `DETECT_EVERY`: inferir cada N frames reduce carga.
- `OMP_NUM_THREADS`: limitar threads CPU.
- `HEADLESS = True`: desactiva ventanas y sube FPS.

## Checklist al cambiar modelo

- Actualizar `MODEL_PATH` en `Main.py`.
- Confirmar `CLASS_NAMES` y mapeo de clases.
- Ajustar thresholds por clase.
- Actualizar este documento.

## Fuentes

- https://ar5iv.labs.arxiv.org/html/2303.05016
- https://github.com/Qengineering/YoloV8-ncnn-Raspberry-Pi-4
- https://docs.edgeimpulse.com/docs/tutorials/end-to-end/object-detection-with-fomo
