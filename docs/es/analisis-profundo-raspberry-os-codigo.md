# Análisis Profundo: Código, OS y Robustez de la Raspberry Pi

> **Autor:** Ai Gemini - **A pedido de:** Gustavo Viollaz
> **Fecha:** 2026-02-23 (America/Argentina/Salta)
> **Área:** Raspberry Pi 4B (Visión, SO y Concurrencia)

Este documento audita el comportamiento interno del programa de la Raspberry Pi, la interacción con la Teensy y el Sistema Operativo, identificando cuellos de botella y proponiendo estándares de élite para la competencia RoboCup Junior.

---

## 1. Secuencia de Inicio y Robustez de Conexión

### A. ¿Quién debe encender primero?
El diseño actual en `Main.py` implementa un estado inicial `esperando`:
```python
while estado == 'esperando':
    frame = vs.read()
    if ser.in_waiting > 0:
        data = ser.read()
        if data == b'\xf9': # 249
            estado = 'linea'
```
*   **Evaluación:** Es un diseño **robusto para el arranque**. La Raspberry Pi (que tarda ~30s en bootear el SO) puede encender primero. Se quedará purgando el buffer serial (`ser.reset_input_buffer()`) y procesando frames al vacío hasta que la Teensy envíe el byte `249` (que ocurre cuando el usuario presiona el switch de arranque físico).
*   **Orden Ideal:** 1. Encender Raspberry Pi y esperar a que cargue el script (se recomienda configurar un script en `systemd` que haga parpadear un LED cuando el script en Python esté corriendo). 2. Presionar el Switch en la Teensy.

### B. ¿Qué pasa si la Teensy se reinicia/apaga en plena ejecución?
*   **Vulnerabilidad:** Si la Teensy sufre un *brownout* (caída de tensión) y se reinicia, la Raspberry Pi **no se entera**. La RPi seguirá en el estado `linea` o `rescate` escupiendo comandos (`[255, speed, 254, angle...]`) al puerto Serial.
*   **Consecuencia:** Cuando la Teensy reviva, entrará en su `loop()` esperando a que el humano presione el switch, pero la RPi ya estará mandando velocidades. Se pierde la sincronización.
*   **Solución (Heartbeat):** La RPi debe exigir un byte de "estoy vivo" (Heartbeat) de la Teensy cada 500ms. Si no lo recibe, la RPi debe forzar su estado de vuelta a `'esperando'`.

---

## 2. Gestión de Buffer y Latencia Serial

El código actual envía ráfagas de 8 bytes continuamente:
```python
output = [255, speed, 254, angle + 90, 253, green_state, 252, 0]
ser.write(output)
```
*   **Análisis de Buffer:** La Raspberry Pi no espera una confirmación (ACK) de la Teensy. Envía en modo *Fire and Forget*. A 30 FPS, son 240 bytes/segundo. El buffer de la UART de la Teensy no se desbordará **salvo que la Teensy use `delay()`**.
*   **El Riesgo Real:** Como detallamos en el análisis de la Teensy, si la Teensy hace un `delay(1000)` para mover la pinza, dejará de leer el Serial. La RPi seguirá metiendo datos. Cuando el delay termine, la Teensy leerá comandos "viejos" de hace 1 segundo, reaccionando tarde.
*   **Solución:** Implementar `ser.flush()` o migrar a un protocolo de solicitud: La RPi solo envía un comando nuevo cuando la Teensy le pide "dame datos".

---

## 3. Análisis de Eficiencia y Frame Rate (FPS)

He analizado línea por línea el `Main.py` y encontré tres "asesinos" de FPS:

### 1. Invocación de YOLO en Tiempo de Ejecución (Bloqueo Severo)
```python
def modo_rescate():
    # ...
    model = YOLO(MODEL_PATH, task='detect') # LÍNEA CRÍTICA
```
*   **Problema:** Cada vez que el robot detecta la línea plateada y entra a `modo_rescate()`, el disco SD tiene que leer el archivo `.onnx` y cargarlo en la memoria RAM. Esto **congela todo el programa** por varios segundos.
*   **Solución:** Instanciar `model = YOLO(...)` en la línea 1 del archivo, a nivel global, para que se cargue una sola vez durante el boot del sistema.

### 2. Creación y Destrucción de Hilos (Memory Leaks)
*   **Problema:** Dentro de `modo_rescate()`, se crean los hilos `tcap` y `tinf` y se destruyen al salir. Crear hilos de captura de video sobre la marcha causa fragmentación de memoria y fugas (memory leaks) en OpenCV con el tiempo.
*   **Solución:** Crear un sistema de hilos persistentes (Worker Threads) en `camthreader.py` que nunca mueran, simplemente se les envíe un "flag" para cambiar entre procesar colores o procesar YOLO.

### 3. Monitoreo Remoto (`cv2.imshow`)
```python
if debugOriginal:
    cv2.imshow('Original', frame_resized)
```
*   **El impacto de la GUI:** Ejecutar `cv2.imshow` cuando la Raspberry Pi está conectada por SSH con Forwarding X11 o VNC **destruye el FPS**. Obliga a la CPU a comprimir la imagen de la ventana y mandarla por Wi-Fi.
*   **Solución de Élite:** En competencia, ejecutar en entorno "Headless" (sin entorno gráfico). Para monitorear, es 1000 veces más eficiente crear un pequeño servidor web usando Flask en un hilo separado que envíe un stream MJPEG, o grabar un video localmente usando `cv2.VideoWriter` a la tarjeta SD para revisar después del round.

---

## 4. Hardware Externo y Mecánica (Luces y Cámara)

### A. Control de Iluminación por Software (Totalmente Recomendado)
*   **El problema:** Los umbrales de color HSV (rojo, verde, plateado) se rompen si cambia la luz ambiental (una nube, el flash de una cámara, sombras del propio robot).
*   **Estrategia:** Añadir un anillo LED blanco alrededor de la cámara.
*   **¿Cómo hacerlo?** Usar un pin GPIO de la Raspberry Pi conectado a un transistor MOSFET. En el código, encender las luces con `GPIO.output(PIN, HIGH)` justo antes de capturar el primer frame.
*   **Ventaja:** Inunda el área de luz constante, matando las sombras. Los valores HSV calibrados en casa funcionarán exactamente igual en Japón o en cualquier estadio.

### B. Evidencias y Calibración Faltante en el Repositorio
Durante la revisión del repo, **NO se encontraron evidencias documentadas** sobre:
1.  **Backups de la SD (Imágenes ISO):** No hay instrucciones sobre cómo clonar la SD. Si la SD se corrompe en competencia por apagar mal la RPi, el equipo queda eliminado. Debe existir un manual en el repo (ej. "Cómo usar Win32DiskImager para hacer un backup mensual del OS").
2.  **Calibración del Foco:** Las cámaras USB baratas tienen lentes enroscables. Con la vibración del robot, el lente gira microscópicamente y se desenfoca. Se debe documentar el proceso de usar una carta de ajuste, enfocar y **fijar la rosca con pegamento epoxi o cinta Kapton**.
3.  **Configuración del Sistema Operativo (OS):** No hay un archivo `setup.sh`. Si se rompe la SD, ¿cómo se configuran los permisos del puerto Serial `/dev/serial0`? ¿Cómo se deshabilita el entorno de escritorio para liberar RAM? Esto debe estar documentado (ej. uso de `raspi-config` para deshabilitar la consola serial en los pines de hardware).

---

## 5. Resumen de Optimizaciones Inmediatas (Action Items)

Para transformar este código en un sistema robusto de grado competencia:

1.  **Mover `YOLO()` al Scope Global:** Sacarlo de la función `modo_rescate()`.
2.  **Activar modo Headless por defecto:** Evitar `cv2.imshow` en producción.
3.  **Implementar un Watchdog Serial:** Forzar el estado a `'esperando'` si el buffer serial de lectura está vacío durante más de 1 segundo.
4.  **Hardware:** Instalar LED de iluminación gestionado por GPIO y documentar el clonado de la tarjeta SD.
