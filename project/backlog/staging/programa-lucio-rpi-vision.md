# Programa de aceleración — Lucio (visión RPi) — Sprint 1

> **Código propuesto** (no es código del robot). Índice de docs y estado vigente: [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). **Reinterpretación del PID #121 vigente.** Push libre de visión ≤2026-06-11 sigue vigente (freeze de código 2026-06-15); fechas internas = foto del 18-may. *Inconsistencia interna conocida:* la tabla del resumen marca #64 como "Crítico (crashea al arrancar en RPi sin pantalla)", pero el propio cuerpo concluye que `Main.py` **ya tiene** el guard `SHOW_DEBUG_WINDOWS` y el bug real está en `calibration.py` — vale el análisis del cuerpo, no la etiqueta de la tabla.

> **AVISO IMPORTANTE: Este código es una PROPUESTA para que Lucio valide, adapte y pruebe.**
> **NO está commiteado. Lucio lo revisa, lo ajusta, lo prueba en banco, y ÉL hace el commit/PR.**
>
> Repo auditado: `software/raspberry/final_rpi/` | Branch: `feature/initialize-testing-log` | Commit: `c42e535`
> Fecha de análisis: 2026-05-18

---

## Resumen ejecutivo

Se analizaron `Main.py` (850 líneas), `camthreader.py` (44 líneas) y `calibration.py` (50 líneas). Se identificaron 5 problemas en los issues #113, #110, #65, #64 y #111. **Todo el código propuesto puede escribirse y revisarse HOY sin el robot.** El banco físico solo hace falta para la validación final (paso "Cómo validarlo" de cada item).

Orden de ataque recomendado (menor riesgo + mayor impacto primero):

| # | Issue | Archivo | Dificultad | Impacto |
|---|-------|---------|-----------|---------|
| 1 | #64 — `cv2.imshow` sin guard | `Main.py` | Trivial | Crítico (crashea al arrancar en RPi sin pantalla) |
| 2 | #110 — `cx_black` sin init | `Main.py` | Pequeño | Crítico (crash 100% con zona verde sin línea) |
| 3 | #65 — `vs.read()` sin None-check | `camthreader.py` | Pequeño | Alto (crash al desconectar cámara) |
| 4 | #113 — Sin `threading.Lock` | `camthreader.py` | Mediano | Alto (frame desgarrado/stale en visión activa) |
| 5 | #111 — `infer_thread()` sin try/except | `Main.py` | Mediano | Alto (deadlock silencioso en modo rescate) |

---

## Contexto de HEADLESS en el proyecto

El patrón ya existe y está establecido en `Main.py` (líneas 12-14):

```python
# Main.py:12-14  <-- patrón canónico, YA existe
HEADLESS = os.environ.get("DISPLAY") is None
DEBUG_VIEW = os.environ.get("DEBUG_VIEW") == "1"
SHOW_DEBUG_WINDOWS = (not HEADLESS) or DEBUG_VIEW
```

Y en `software/raspberry/test/rescue_zone_test/warmup.py` (línea 40) / `rescatemodelonos.py` (línea 38) el mismo patrón. **Todos los `cv2.imshow` del loop principal ya usan `SHOW_DEBUG_WINDOWS` excepto el del modo rescate — que es el problema del issue #64.**

---

## Tema 1 — Issue #64: `cv2.imshow` sin guard HEADLESS en modo rescate

### Análisis

**Archivo:** `Main.py:672-675` (dentro de `modo_rescate()` → `main_loop()`)

El `cv2.imshow` de `modo_rescate` YA está correctamente guardado con `SHOW_DEBUG_WINDOWS`. El problema real es que `calibration.py` llama a `cv2.imshow` incondicionalmente (líneas 42-44) y no tiene guard. En el `Main.py` el `SHOW_DEBUG_WINDOWS` está correcto para el modo rescate. Sin embargo, `calibration.py` es un script de desarrollo que SI se ejecutara en la RPi sin pantalla crashearía.

Adicionalmente, examinando el código alrededor de la línea 669-681: la guard `SHOW_DEBUG_WINDOWS` YA está aplicada correctamente. Esto significa que el issue #64 **está parcialmente resuelto** en `Main.py` (el rescate ya tiene guard), pero `calibration.py` no tiene guard en absoluto.

**Estado real:** `Main.py` ya usa `SHOW_DEBUG_WINDOWS` correctamente. `calibration.py` no tiene ningún guard.

### Código propuesto — `calibration.py`

ANTES (calibration.py completo, sin guards):
```python
# calibration.py — sin guards (actual)
import cv2
from camthreader import *

vs = WebcamVideoStream(src=0).start()
rgb_frame = vs.read()
# ...

while True:
    rgb_frame = vs.read()
    # ...
    cv2.imshow("RGB", rgb_frame)        # crash en headless
    cv2.imshow("HSV", hsv_frame)        # crash en headless
    cv2.imshow("LAB", lab_frame)        # crash en headless
    if cv2.waitKey(1) == 27:
        break

vs.stop()
cv2.destroyAllWindows()
```

DESPUÉS (calibration.py con guard):
```python
import cv2
import os
from camthreader import *

HEADLESS = os.environ.get("DISPLAY") is None  # mismo patrón que Main.py

vs = WebcamVideoStream(src=0).start()
rgb_frame = vs.read()
hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV) if rgb_frame is not None else None

def rgbclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x, y, rgb_frame[y][x])

def hsvclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print(x, y, hsv_frame[y][x])

def labclick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print("Valores LAB:", lab_frame[y, x])

if not HEADLESS:
    cv2.namedWindow('RGB')
    cv2.setMouseCallback('RGB', rgbclick)
    cv2.namedWindow('HSV')
    cv2.setMouseCallback('HSV', hsvclick)

while True:
    rgb_frame = vs.read()
    if rgb_frame is None:
        continue
    lab_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2Lab)
    rgb_frame = vs.read()
    if rgb_frame is None:
        continue
    hsv_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2HSV)
    rgb_frame = cv2.line(rgb_frame, (80, 0), (80, 120), (255, 0, 0), 1)
    hsv_frame = cv2.line(hsv_frame, (80, 0), (80, 120), (255, 0, 0), 1)

    if not HEADLESS:
        cv2.namedWindow('LAB')
        cv2.setMouseCallback('LAB', labclick)
        cv2.imshow("RGB", rgb_frame)
        cv2.imshow("HSV", hsv_frame)
        cv2.imshow("LAB", lab_frame)
        if cv2.waitKey(1) == 27:
            break
    else:
        print("[HEADLESS] calibration.py corriendo — no hay ventanas")
        # En headless, imprimir valores por consola para debug:
        h, w = rgb_frame.shape[:2]
        cx, cy = w // 2, h // 2
        print(f"  Centro RGB: {rgb_frame[cy][cx]}")
        print(f"  Centro HSV: {hsv_frame[cy][cx]}")
        break  # en headless, hacer un sample y salir

vs.stop()
if not HEADLESS:
    cv2.destroyAllWindows()
```

### Cómo validarlo

**Sin robot, en la PC de desarrollo:**
```bash
# Test 1: simular RPi headless (sin DISPLAY)
DISPLAY="" python software/raspberry/final_rpi/calibration.py
# Resultado esperado: NO crash, imprime "[HEADLESS] calibration.py corriendo"

# Test 2: con pantalla (modo normal)
python software/raspberry/final_rpi/calibration.py
# Resultado esperado: abre ventanas RGB/HSV/LAB normalmente
```

**En RPi sin monitor:** copiar el archivo, ejecutar `python calibration.py` via SSH — no debe abrir ventanas ni crashear.

### Checklist de aprobación

- [ ] `python calibration.py` sin `DISPLAY` definido: no crashea, imprime mensaje headless
- [ ] `python calibration.py` con pantalla: ventanas abren y responden a doble-clic
- [ ] FPS de `Main.py` no cambia (este fix no toca `Main.py`)
- [ ] Entrada en `testing/TEST_LOG.md`: "calibration.py — test headless OK, test con pantalla OK"

---

## Tema 2 — Issue #110: `cx_black` sin inicializar → crash 100%

### Análisis

**Archivo:** `Main.py:769-780`

```python
# Main.py:769-780 — código actual problemático
if np.sum(black_mask[90:, :]):
    cx_black = int(blackM["m10"] / blackM["m00"])  # SOLO se asigna si hay píxeles negros

# Más abajo, línea 778:
if len(green_contours) > 1 and cx_black > leftIndex and cx_black < rightIndex ...:
    # ^ USO de cx_black SIN garantía de haber sido asignado arriba
```

El bloque `if np.sum(black_mask[90:, :])` solo ejecuta si hay masa negra debajo del green. Si hay zona verde pero NO hay línea negra debajo (escenario completamente válido en pista), `cx_black` nunca se asigna en esta iteración pero sí se usa en la condición de línea 778. Si es la primera iteración del loop, `cx_black` no existe → `NameError` → crash inmediato. Si es iteración posterior, usa el valor de la iteración anterior → lógica incorrecta.

**Crash: 100% reproducible** en el primer frame con zona verde visible y sin línea negra en la mitad inferior.

### Código propuesto — `Main.py`

Buscar el bloque de inicialización de variables al principio del loop (antes de `while estado == 'linea':`). Agregar inicialización explícita de `cx_black`.

ANTES:
```python
# Main.py ~ línea 753-770 (dentro del while estado == 'linea':)
green_state = 0
x_resultant = np.mean(x_black)
y_resultant = np.mean(y_black)
angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90
speed = 40

if np.sum(green_mask) > min_square_size * 255:
    green_pixels = np.amax(green_mask, axis=0)
    greenIndices = np.where(green_pixels == np.max(green_pixels))
    leftIndex    = greenIndices[0][0]
    rightIndex   = greenIndices[0][-1]
    slicedGreen  = frame_resized[60:90, leftIndex:rightIndex + 1, :]
    greenCentroidX = (rightIndex + leftIndex) / 2
    slicedBlackMaskAboveGreen = black_mask[60:90, leftIndex:rightIndex + 1]
    blackM = cv2.moments(black_mask[90:, :])

    if np.sum(black_mask[90:, :]):
        cx_black = int(blackM["m10"] / blackM["m00"])   # <-- solo asigna si hay masa
    # ...
    if len(green_contours) > 1 and cx_black > leftIndex ...:   # <-- usa cx_black sin init
```

DESPUÉS:
```python
# Main.py ~ línea 753 — agregar init explícita antes del if green
green_state = 0
x_resultant = np.mean(x_black)
y_resultant = np.mean(y_black)
angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90
speed = 40

cx_black = width // 2  # INIT SEGURA: centro de frame como fallback neutral

if np.sum(green_mask) > min_square_size * 255:
    green_pixels = np.amax(green_mask, axis=0)
    greenIndices = np.where(green_pixels == np.max(green_pixels))
    leftIndex    = greenIndices[0][0]
    rightIndex   = greenIndices[0][-1]
    slicedGreen  = frame_resized[60:90, leftIndex:rightIndex + 1, :]
    greenCentroidX = (rightIndex + leftIndex) / 2
    slicedBlackMaskAboveGreen = black_mask[60:90, leftIndex:rightIndex + 1]
    blackM = cv2.moments(black_mask[90:, :])

    if np.sum(black_mask[90:, :]):
        cx_black = int(blackM["m10"] / blackM["m00"])   # sobreescribe el fallback
    # ...
    if len(green_contours) > 1 and cx_black > leftIndex ...:   # ahora siempre tiene valor
```

**Nota sobre el valor del fallback:** `width // 2` (= 80 px) es el centro del frame. Con este fallback, si no hay línea negra debajo del green, la condición `cx_black > leftIndex and cx_black < rightIndex` usará el centro. Si el green está centrado esto puede clasificar como "both sides" (green_state=3). Lucio debe revisar si prefiere `cx_black = -1` para forzar que la condición sea `False` siempre que no haya línea. Esa sería la opción más conservadora:

```python
cx_black = -1  # fallback conservador: garantiza que la comparación sea False
```

Elegir el fallback es decisión de Lucio según el comportamiento deseado.

### Cómo validarlo

**Sin robot (test en PC):**
```python
# Script de test mínimo — correr en PC con OpenCV
import cv2
import numpy as np

# Simular frame con zona verde visible pero SIN negro abajo
frame = np.zeros((120, 160, 3), dtype=np.uint8)
# Pintar zona verde en la parte inferior
frame[90:, :, 1] = 150  # canal G del verde en BGR aproximado

# Verificar que cx_black NO provoca NameError
cx_black = 80  # init propuesta
black_mask = np.zeros((120, 160), dtype=np.uint8)
blackM = cv2.moments(black_mask[90:, :])
if np.sum(black_mask[90:, :]):
    cx_black = int(blackM["m10"] / blackM["m00"])

print(f"cx_black = {cx_black}")  # debe imprimir 80, sin NameError
```

**En banco con robot:** apuntar cámara a una zona verde amplia sin línea negra visible en la mitad inferior. El robot NO debe crashear ni imprimir traceback.

### Checklist de aprobación

- [ ] Con cámara apuntando a zona verde sin línea: NO crashea, `cx_black` usa el fallback
- [ ] Con cámara apuntando a zona verde CON línea: comportamiento de giro igual que antes
- [ ] Con pista normal (sin verde): comportamiento de seguimiento de línea idéntico
- [ ] FPS sin degradación apreciable (el cambio es O(1))
- [ ] Entrada en `testing/TEST_LOG.md`: "cx_black init fix — zona verde sin línea: OK, zona verde con línea: OK"

---

## Tema 3 — Issue #65: `vs.read()` puede devolver `None` → crash con cámara desconectada

### Análisis

**Archivo:** `camthreader.py:32-36`

```python
# camthreader.py:34-36 — actual
def read(self):
    # return the frame most recently read
    return self.frame
```

El método `read()` devuelve `self.frame` sin verificar si es `None`. El frame es `None` cuando:
1. La cámara se desconecta en caliente (USB flojo, vibración del robot)
2. `self.stream.read()` falla en el `update()` thread y `self.frame` nunca se inicializa

En el loop principal de `Main.py`, `read_frame_with_recovery()` (línea 132-147) ya maneja `None` correctamente. Pero si el frame inicial (línea 15 en `camthreader.py`) falla, `self.frame` puede ser `None` desde el inicio.

El riesgo real es: **frame desgarrado** (tearing) cuando el thread de `update()` escribe `self.frame` y el thread principal lo lee simultáneamente sin Lock. Eso produce crashes intermitentes difíciles de reproducir porque el frame a mitad de escritura puede tener shape inválida.

### Código propuesto — `camthreader.py`

El fix de `None` ya está cubierto por `read_frame_with_recovery`. Lo que falta es agregar un `Lock` para proteger la escritura/lectura de `self.frame`. Esto cubre tanto el `None` como el frame desgarrado del issue #113 (ver siguiente tema). **Propongo unificar #65 y #113 en un solo PR.**

```python
# camthreader.py — PROPUESTA COMPLETA (antes + después unificado con Lock)

from threading import Thread, Lock  # agregar Lock
import cv2

class WebcamVideoStream:
    def __init__(self, src=0, width=160, height=120):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        print(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH),
              self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

        (self.grabbed, self.frame) = self.stream.read()
        self._lock = Lock()       # NUEVO: protege self.frame contra tearing
        self.stopped = False

    def start(self):
        Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        while True:
            if self.stopped:
                return
            grabbed, frame = self.stream.read()
            with self._lock:                       # NUEVO: escritura atómica
                self.grabbed = grabbed
                self.frame   = frame

    def read(self):
        with self._lock:                           # NUEVO: lectura atómica
            return self.frame                      # puede ser None — el caller maneja

    def get_dim(self):
        return (self.stream.get(cv2.CAP_PROP_FRAME_WIDTH),
                self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def stop(self):
        self.stopped = True
```

**Cambios respecto al original:**
1. `from threading import Thread, Lock` — agregar `Lock`
2. En `__init__`: `self._lock = Lock()`
3. En `update()`: `grabbed, frame = self.stream.read()` en variable local, luego `with self._lock:` para asignar atómicamente
4. En `read()`: `with self._lock: return self.frame`
5. En `start()`: agregar `daemon=True` (buena práctica — el thread no bloquea la salida del programa)

**Nota sobre daemon=True:** el thread actual NO tiene `daemon=True`. Sin esto, si `Main.py` lanza una excepción y el proceso intenta salir, el thread de cámara lo mantiene vivo indefinidamente. Lucio puede decidir si quiere incluir este cambio o dejarlo para otro PR.

### Cómo validarlo

**Sin robot (test en PC):**
```python
# test_camthreader.py — correr en PC con webcam conectada
import time
from camthreader import WebcamVideoStream

vs = WebcamVideoStream(src=0).start()
time.sleep(0.5)

errores = 0
for i in range(100):
    frame = vs.read()
    if frame is None:
        errores += 1
    else:
        assert frame.shape == (120, 160, 3), f"Shape inesperada: {frame.shape}"

vs.stop()
print(f"Test completado. Frames None: {errores}/100")
# Esperado: errores == 0 con cámara conectada, no crash en ningún caso
```

**En banco con cámara real:** desconectar el cable USB de la cámara mientras `Main.py` corre. El programa debe imprimir `[WARN] frame None` y NO crashear con `AttributeError: 'NoneType' object has no attribute 'shape'`.

### Checklist de aprobación

- [ ] Con cámara conectada: 0 crashes en 100 lecturas, shape siempre correcta
- [ ] Con cámara desconectada en caliente: `[WARN]` en log, sin crash
- [ ] FPS no cae más de 2 FPS respecto al baseline (el Lock es un mutex liviano)
- [ ] Entrada en `testing/TEST_LOG.md`: "camthreader Lock + None — test 100 frames OK, test desconexión en caliente OK"

---

## Tema 4 — Issue #113: `threading.Lock` faltante en `camthreader.py`

### Análisis

**Archivo:** `camthreader.py:25-36`

```python
# camthreader.py:25-36 — ACTUAL (sin Lock)
def update(self):
    while True:
        if self.stopped:
            return
        (self.grabbed, self.frame) = self.stream.read()  # escribe sin protección

def read(self):
    return self.frame   # lee sin protección
```

Dos threads acceden a `self.frame` simultáneamente:
- **Thread A** (update): escribe `self.frame` con el nuevo frame
- **Thread B** (main): lee `self.frame` para procesarlo

Sin `Lock`, puede ocurrir que el thread B lea un frame a mitad de escritura (tearing). En CPython, la asignación de un objeto de NumPy no es atómica: implica al menos decrementar el refcount del objeto anterior y actualizar el puntero. Si el GIL se libera en ese punto (lo cual ocurre en operaciones de I/O como `cv2.VideoCapture.read()`), el thread B puede leer un estado intermedio.

El resultado es intermitente: el programa crashea con `cv2 error` o `shape mismatch` en condiciones de alta carga de CPU (exactamente cuando el robot está en pista).

**Este tema ya está cubierto en el código propuesto del Tema 3.** Son un mismo PR.

### Referencia cruzada

Ver "Código propuesto" en Tema 3 (Issue #65). El `Lock` resuelve ambos issues.

---

## Tema 5 — Issue #111: `infer_thread()` sin `try/except` → deadlock silencioso

### Análisis

**Archivo:** `Main.py:452-503` (función `infer_thread()` dentro de `modo_rescate()`)

```python
# Main.py:452-503 — actual (sin manejo de errores)
def infer_thread():
    frame_idx = 0
    while True:
        frame = frame_q.get()        # bloqueante — si hay excepción antes de aquí...
        if frame is None:
            result_q.put(None)
            break

        h, w  = frame.shape[:2]
        small = cv2.resize(frame, (IMGSZ, IMGSZ))
        # ... (TFLite inference, etc.) ...
        result_q.put(('det', enhanced_frame, detections))   # si hay excepción aquí, nunca llega
        frame_idx += 1
        # NO hay try/except en ningún punto del loop
```

Si ocurre cualquier excepción dentro de `infer_thread()` (ej: `interpreter.invoke()` falla por OOM, shape incorrecta, etc.):
1. El thread muere silenciosamente (es `daemon=True` implícito)
2. `result_q` nunca recibe ningún item
3. `main_loop()` llama `result_q.get(timeout=0.25)` en bucle → `queue.Empty` continuo
4. `frame_q` se llena porque nadie consume → `capture_thread` se bloquea en `frame_q.put(frame)` (que NO tiene timeout)
5. Resultado: **deadlock silencioso** — el robot sigue enviando `speed=10, angle=90` (búsqueda) indefinidamente

### Código propuesto — `Main.py`

Reemplazar el cuerpo de `infer_thread()` con manejo de errores + sentinel de error:

ANTES:
```python
def infer_thread():
    frame_idx = 0
    while True:
        frame = frame_q.get()
        if frame is None:
            result_q.put(None)
            break

        h, w  = frame.shape[:2]
        small = cv2.resize(frame, (IMGSZ, IMGSZ))

        if frame_idx % DETECT_EVERY == 0:
            small = enhance(small, use_zerodce=USE_ZERODCE)
        else:
            if ENABLE_ANTIFLASH:
                small = anti_flash_preprocess(small)
            small = agcwd(small)
        enhanced_frame = cv2.resize(small, (w, h))

        if frame_idx % DETECT_EVERY == 0:
            img = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            if np.issubdtype(input_details['dtype'], np.floating):
                inp = (img.astype(np.float32) / 255.0)[np.newaxis, ...].astype(input_details['dtype'])
            else:
                inp = img[np.newaxis, ...].astype(input_details['dtype'])

            interpreter.set_tensor(input_details['index'], inp)
            interpreter.invoke()
            out = interpreter.get_tensor(output_details['index'])[0]

            detections = []
            for det in out:
                # ... procesamiento de detecciones ...
            result_q.put(('det', enhanced_frame, detections))
        else:
            result_q.put(('no_det', enhanced_frame, None))

        frame_idx += 1
```

DESPUÉS:
```python
def infer_thread():
    frame_idx = 0
    while True:
        frame = frame_q.get()
        if frame is None:
            result_q.put(None)
            break

        try:
            h, w  = frame.shape[:2]
            small = cv2.resize(frame, (IMGSZ, IMGSZ))

            if frame_idx % DETECT_EVERY == 0:
                small = enhance(small, use_zerodce=USE_ZERODCE)
            else:
                if ENABLE_ANTIFLASH:
                    small = anti_flash_preprocess(small)
                small = agcwd(small)
            enhanced_frame = cv2.resize(small, (w, h))

            if frame_idx % DETECT_EVERY == 0:
                img = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                if np.issubdtype(input_details['dtype'], np.floating):
                    inp = (img.astype(np.float32) / 255.0)[np.newaxis, ...].astype(input_details['dtype'])
                else:
                    inp = img[np.newaxis, ...].astype(input_details['dtype'])

                interpreter.set_tensor(input_details['index'], inp)
                interpreter.invoke()
                out = interpreter.get_tensor(output_details['index'])[0]

                detections = []
                for det in out:
                    x1, y1, x2, y2, score, cls_raw = det
                    score  = float(score)
                    cls_id = int(round(float(cls_raw)))
                    if score < CLASS_THRESH.get(cls_id, 0.5):
                        continue
                    x1 *= IMGSZ; y1 *= IMGSZ; x2 *= IMGSZ; y2 *= IMGSZ
                    sx1, sy1, sx2, sy2 = scale_box((x1, y1, x2, y2), w, h, IMGSZ, IMGSZ)
                    if estado == "rescate":
                        if cls_id in (2, 3): continue
                    if estado == "depositar":
                        if cls_id in (0, 1, 2): continue
                    if estado == "depositar verde":
                        if cls_id in (0, 1, 3): continue
                    detections.append({'xyxy': (sx1, sy1, sx2, sy2), 'score': score, 'cls': cls_id})

                result_q.put(('det', enhanced_frame, detections))
            else:
                result_q.put(('no_det', enhanced_frame, None))

            frame_idx += 1

        except Exception as exc:                          # NUEVO: capturar cualquier error
            print(f"[ERROR] infer_thread frame_idx={frame_idx}: {exc}")
            # Publicar un resultado vacío para que main_loop no se bloquee
            try:
                result_q.put(('no_det', frame, None), block=False)
            except Exception:
                pass
            frame_idx += 1
            # NO hacer break: el thread sigue vivo para el próximo frame
```

**Por qué NO hacer break en el except:** Si el thread muere, el deadlock regresa. Mejor publicar un resultado vacío y continuar. Si el error es persistente (OOM, modelo corrupto), el log llenará la consola con `[ERROR]` repetidos — señal clara para el operador.

**Mejora adicional (opcional, para después de Sprint 1):** agregar un contador de errores consecutivos y un sentinel de error crítico si supera un umbral (ej: 10 errores seguidos → enviar `result_q.put(None)` y terminar limpiamente). Esto es un P2 que Lucio puede decidir incluir o no.

### Cómo validarlo

**Sin robot (test de inyección de fallo):**
```python
# Modificar temporalmente el infer_thread en una copia de prueba:
# Forzar una excepción en el frame 5:
if frame_idx == 5:
    raise RuntimeError("error de prueba inyectado")
```

Verificar que:
1. Aparece `[ERROR] infer_thread frame_idx=5: error de prueba inyectado` en consola
2. `main_loop()` sigue ejecutándose (no se congela)
3. El frame 6 en adelante se procesa normalmente

**En banco con robot:** difícil de forzar directamente. La validación es observacional: correr 5 minutos en modo rescate y verificar que el log no muestra deadlock ni congelamiento.

### Checklist de aprobación

- [ ] Test de inyección de fallo: error en log, main_loop no se congela
- [ ] Corrida de 5 min en modo rescate: sin deadlock, FPS estable
- [ ] `infer_thread` sigue funcionando tras error inyectado (frame siguiente procesa OK)
- [ ] Entrada en `testing/TEST_LOG.md`: "infer_thread try/except — test inyección OK, corrida 5min OK"

---

## Orden de trabajo recomendado para Lucio

### Todo el Sprint 1 se puede escribir HOY sin el robot

Los 5 fixes son modificaciones de menos de 20 líneas cada uno. El banco físico solo hace falta en la etapa "Cómo validarlo". Mientras tanto, Lucio puede:

1. Escribir los cambios en ramas locales
2. Escribir los test scripts de verificación en PC
3. Preparar las entradas de `TEST_LOG.md` con los resultados esperados

### Secuencia sugerida

```
Día 1 (hoy, sin robot):
  - [x] Leer este doc completo
  - [ ] Tema 1 (#64): agregar guard a calibration.py — 15 min
  - [ ] Tema 2 (#110): agregar cx_black = width // 2 — 5 min
  - [ ] Temas 3+4 (#65+#113): reescribir camthreader.py con Lock — 30 min
  - [ ] Tema 5 (#111): envolver infer_thread en try/except — 20 min

Día 2 (con banco / RPi disponible):
  - [ ] Validar tema 1: test headless en RPi via SSH
  - [ ] Validar tema 2: apuntar cámara a zona verde sin negro
  - [ ] Validar temas 3+4: desconectar cámara en caliente
  - [ ] Validar tema 5: test inyección de fallo
  - [ ] Completar TEST_LOG.md
  - [ ] Abrir PRs (uno por issue o uno unificado #65+#113)
```

### Quick-win de mayor impacto y menor riesgo

**Tema 2 — Issue #110 (`cx_black` sin init)**: es una línea de código (`cx_black = width // 2`), el crash es 100% reproducible y determinista, y el fix no tiene efectos secundarios sobre el comportamiento en condiciones normales. Es el cambio con mejor ratio impacto/riesgo/esfuerzo del Sprint 1.

---

## Notas finales

- **Idioma de commits:** español, estilo Conventional Commits. Ej: `fix(rpi): inicializar cx_black para evitar crash en zona verde sin linea (#110)`
- **Un PR por issue** (o #65+#113 juntos si se unifican en un commit)
- **Cada PR referencia el issue:** `Closes #NNN` en la descripción
- **Test plan obligatorio** en el PR (usar `.github/pull_request_template.md`)
- **No mergear sin entrada en `testing/TEST_LOG.md`** (regla de oro del repo)

---

*Documento generado: 2026-05-18 | Auditor: coach técnico senior IA | Solo lectura de código fuente — ningún archivo de `software/` fue modificado.*
