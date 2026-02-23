# Carpeta `rpi`

Esta carpeta contiene el software que corre en la Raspberry Pi.

## Estructura actual

- `final_rpi/`:
  - `Main.py`: **programa principal** que se usa en competencia (linea + rescate).
  - `camthreader.py`: captura de camara por hilo.
  - `calibration.py`: utilidades de calibracion.
- `test/`: scripts de prueba (camara, serial, etc.).
- `AI/`: modelos 

## Programa principal

El punto de entrada es `rpi/final_rpi/Main.py`. Este archivo:
- Lee la camara y procesa imagen.
- Envia comandos a la Teensy por serial (`/dev/serial0`, 115200).
- Cambia de estado entre `esperando`, `linea`, `rescate`, `depositar`.

La comunicacion completa esta documentada en:
- `rpi/Comunicacion de la raspberry y la teensy.md`
- `rpi/YOLO y Raspberry.md`

## Enlaces

- Carpeta de fotos y videos (Drive):
  - https://drive.google.com/drive/folders/155xTIpLF9liF-LiiE0WMLb7epZ9MYj3t?usp=sharing
