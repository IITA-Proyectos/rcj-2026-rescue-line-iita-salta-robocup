# Programa de trabajo — Benjamin Villagran · RPi 4B + Hardware gate

> **Propuesta para que Benjamin valide, adapte y pruebe. NO commiteado. Él lo ajusta, prueba, y hace el commit/PR.**

**Equipo:** IITA Salta · **Mundial:** RoboCup Junior Rescue Line 2026 — Incheon (~6 semanas).
**Branch de trabajo:** `feature/initialize-testing-log` · commit base `c42e535`.
**Fecha de preparación:** 2026-05-18.

---

## Tabla de contenidos

1. [#108 — Auto-restart del proceso `Main.py` (CRÍTICO, Sprint 1)](#108)
2. [#68 — `requirements.txt` sin pinning (Sprint 1)](#68)
3. [#66 — `send_frame()` sin clamp de rango ni `SerialException` (Track A/comms)](#66)
4. [Protocolo de banco — Gate de calidad reusable](#banco)

---

## Diagnóstico previo: confirmación de ausencia de auto-restart

Búsqueda realizada sobre todo el repo (`grep -rn` equivalente vía Grep tool) con los términos:
`service`, `systemd`, `supervisor`, `rc.local`, `crontab`, `autostart`, `ExecStart`.

**Resultado:** ningún match en código operativo ni en `software/`. Los únicos documentos que mencionan estos términos son archivos de docs/análisis en `docs/es/` y `docs/en/` (no son configuración activa).

**Conclusión:** el proceso `Main.py` no tiene ningún mecanismo de auto-restart. Si falla (excepción no capturada, OOM, cámara desconectada en caliente, etc.), el robot queda detenido sin enviar frames, y el Teensy sigue en el último estado recibido o hace timeout. **Esto es el riesgo más alto del equipo para Incheon.**

---

<a name="108"></a>
## 1. #108 — Auto-restart del proceso `Main.py` (CRÍTICO, Sprint 1)

### 1.1 Análisis

**Situación observada en `software/raspberry/final_rpi/Main.py`:**

- Líneas 66–67 (módulo top-level): `vs = WebcamVideoStream(src=0).start()` y `ser = serial.Serial(...)` se ejecutan **al momento de importación**. Si cualquiera de estos falla (cámara no disponible al arranque, `/dev/serial0` ocupado), el proceso termina con traceback y no hay nada que lo reinicie.
- Líneas 711–849: el `while True` principal es código de módulo sin `if __name__ == "__main__":` guard. Esto impide que systemd o cualquier supervisor controlen limpiamente el ciclo de vida del proceso, y hace que importar el módulo desde otro contexto lo ejecute inmediatamente.
- No hay `try/except` de último recurso alrededor del `while True` que envíe `speed=0` al Teensy antes de morir.

**Riesgo sin fix:** en cualquier corrida de Incheon, un pico de USB, un frame None en cascada, o un pico de memoria mata el proceso. El robot queda inmóvil con el Teensy congelado. El juez lo anota como abandono. Estimado de impacto: 3-4 puntos por corrida.

**Riesgo con fix:** el proceso hace restart en ~2-3 s. El Teensy recibe `speed=0` en la señal de salida (failsafe). El robot para en lugar de continuar incontrolado. systemd registra el crash en journal para post-mortem.

### 1.2 Propuesta A: Unit `robot.service` (systemd)

Archivo a crear en la Pi: `/etc/systemd/system/robot.service`

```ini
[Unit]
Description=IITA RCJ 2026 – proceso principal visión RPi
Documentation=https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/rcj-2026-rescue-line-iita-salta-robocup/software/raspberry/final_rpi
ExecStart=/usr/bin/python3 /home/pi/rcj-2026-rescue-line-iita-salta-robocup/software/raspberry/final_rpi/Main.py
Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal
SyslogIdentifier=robot-rpi
Environment=PYTHONUNBUFFERED=1
Environment=HEADLESS=1
# Opcional: limitar memoria para evitar OOM silencioso
# MemoryMax=600M

[Install]
WantedBy=multi-user.target
```

**Comandos de activación en la Pi (una sola vez):**
```bash
sudo cp robot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable robot.service    # arranque en boot
sudo systemctl start robot.service     # arranque inmediato
```

**Comandos de operación:**
```bash
sudo systemctl status robot.service    # ver estado y últimas 10 líneas de log
sudo journalctl -u robot.service -f    # seguir logs en vivo
sudo journalctl -u robot.service -n 50 --no-pager  # últimas 50 líneas post-crash
```

**Nota sobre la ruta:** ajustar la ruta del `ExecStart` y `WorkingDirectory` al clone real en la Pi. Si el repo está en `/home/pi/Downloads/...`, cambiar en consecuencia. Benjamin confirma la ruta antes de commitearlo.

### 1.3 Propuesta B: `try/except` de último recurso + `__main__` guard en `Main.py`

Esta es la modificación mínima a `Main.py`. Benjamin la adapta, prueba, y hace el commit — no se tocó código aquí.

**Estructura propuesta para el final de `Main.py`** (reemplaza las líneas 711–849 del `while True` desnudo):

```python
# ---- helper de parada de emergencia ----
def _emergency_stop():
    """Envía speed=0 al Teensy y espera ACK por hasta 500 ms.
    Se llama desde el handler de señales y desde el except de último recurso.
    No lanza excepciones.
    """
    try:
        # Construir frame de parada directamente (no via send_frame para evitar
        # dependencias de estado global que podrían estar corruptos)
        stop_frame = bytes([
            SYNC_SPEED, 0,
            SYNC_ANGLE, clamp_byte(0 + 90),
            SYNC_GREEN_STATE, 0,
            SYNC_SILVER_LINE, 0,
        ])
        ser.write(stop_frame)
        ser.flush()
        print("[EMERGENCY_STOP] frame speed=0 enviado al Teensy")
    except Exception as e:
        print(f"[EMERGENCY_STOP] no se pudo enviar stop frame: {e}")


import signal

def _signal_handler(signum, frame_):
    print(f"[SIGNAL] recibida señal {signum} -> emergency stop + exit")
    _emergency_stop()
    sys.exit(0)

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT,  _signal_handler)


# -----------------------------------------------
# LOOP PRINCIPAL — envuelto en try/except de último recurso
# -----------------------------------------------
def main():
    global estado, silver_line

    _restart_count = 0
    _MAX_RESTARTS_PER_SESSION = 20   # evita loop infinito si hay falla de HW dura

    while _restart_count < _MAX_RESTARTS_PER_SESSION:
        try:
            # ---- loop principal (mover acá el contenido del while True actual) ----
            while True:

                while estado == 'esperando':
                    silver_line = False
                    if ser.in_waiting > 0:
                        data = ser.read()
                        handle_control_byte(data, context="esperando")
                    time.sleep(FRAME_NONE_RETRY_SLEEP_S)

                while estado == 'rescate':
                    modo_rescate()

                line_none_count = 0
                while estado == 'linea':
                    # ... (contenido del while linea sin cambios) ...
                    pass   # <-- BENJAMIN: mover el bloque linea completo acá

        except KeyboardInterrupt:
            print("[MAIN] KeyboardInterrupt -> exit limpio")
            _emergency_stop()
            break

        except Exception as exc:
            _restart_count += 1
            print(f"[MAIN] EXCEPCION NO CAPTURADA (restart {_restart_count}/{_MAX_RESTARTS_PER_SESSION}): {exc!r}")
            _emergency_stop()
            if _restart_count >= _MAX_RESTARTS_PER_SESSION:
                print("[MAIN] Demasiados reinicios. Saliendo para que systemd gestione el reinicio.")
                sys.exit(1)
            print("[MAIN] Esperando 2 s antes de reintentar...")
            time.sleep(2)
            # Reinicializar estado para el reintento
            estado = 'esperando'

    _emergency_stop()


if __name__ == "__main__":
    main()
```

**Nota para Benjamin:** el bloque `while estado == 'linea':` (líneas 724-845 del archivo actual) se mueve adentro del `try` sin modificar ni una línea de su lógica. Solo se agrega el wrapping. El `if __name__ == "__main__":` guard al final es indispensable para que systemd funcione correctamente.

### 1.4 Cómo validarlo en banco (sin pista completa)

```bash
# 1. Verificar que el servicio arranca
sudo systemctl start robot.service
sudo systemctl status robot.service   # esperar "active (running)"

# 2. Forzar crash del proceso y medir tiempo de restart
MAIN_PID=$(systemctl show -p MainPID robot.service | cut -d= -f2)
sudo kill -9 $MAIN_PID
# Esperar y medir:
time (until systemctl is-active --quiet robot.service; do sleep 0.1; done)
# Debe ser < 5 s (RestartSec=2 + startup ~2 s en Pi 4B con modelo cargado)

# 3. Ver en journal que el restart quedó registrado
sudo journalctl -u robot.service -n 30 --no-pager

# 4. Verificar que el Teensy recibió speed=0 tras el kill (ver serial monitor del Teensy)

# 5. Repetir 3 veces para confirmar estabilidad
```

### 1.5 Checklist de aprobación — #108

- [ ] `robot.service` copiado a `/etc/systemd/system/` en la Pi de producción.
- [ ] `systemctl enable robot.service` ejecutado y confirmado con `is-enabled`.
- [ ] Restart tras `kill -9` verificado ≤ 5 s (medir 3 veces, anotar tiempos en TEST_LOG T-001).
- [ ] Journal muestra el crash + el restart limpio.
- [ ] Teensy recibe `speed=0` antes del restart (confirmar con serial monitor en PC o LED de estado del Teensy).
- [ ] `if __name__ == "__main__":` guard presente en `Main.py` antes del merge.
- [ ] `_emergency_stop()` llamado en SIGTERM, SIGINT y `except Exception`.
- [ ] PR creado con referencia a #108, entrada T-001 en `testing/TEST_LOG.md`.

---

<a name="68"></a>
## 2. #68 — `requirements.txt` sin pinning (Sprint 1)

### 2.1 Análisis

**Situación observada en `software/raspberry/requirements.txt`:**

```
opencv-contrib-python
numpy
pyserial
ultralytics
onnxruntime
tflite-runtime==2.14.0
ai-edge-litert==2.1.3
```

Las dependencias `opencv-contrib-python`, `numpy`, `pyserial`, `ultralytics` y `onnxruntime` no tienen versión pineada. Si en Incheon hay que reinstalar la SD (tarjeta dañada, corrupción, Pi de repuesto), `pip install -r requirements.txt` puede traer versiones incompatibles. En particular:

- `ultralytics` rompe API en minors con frecuencia.
- `opencv-contrib-python` tiene builds específicos para ARM/Pi que pueden no existir en todas las versiones.
- `numpy` 2.x rompe compatibilidad con código que usa `.astype(np.float32)` de ciertas formas.

**Riesgo sin fix:** reinstalar desde cero la noche anterior a la competencia puede dejar el robot sin funcionar con versiones nuevas que son binariamente incompatibles con el modelo `.tflite` o con la API de `ultralytics`.

**Riesgo con fix:** el entorno es 100% reproducible en < 15 minutos desde una SD limpia.

### 2.2 Propuesta: `requirements.txt` pineado

**Paso 1 — obtener versiones reales de la Pi de producción (Benjamin ejecuta esto en la Pi):**

```bash
# En la Pi que funciona hoy:
source /home/pi/robot-venv/bin/activate   # o el venv que usen
pip freeze > /tmp/pip-freeze-$(date +%Y%m%d).txt
cat /tmp/pip-freeze-$(date +%Y%m%d).txt
```

Filtrar las líneas relevantes y reemplazar el `requirements.txt` con las versiones exactas obtenidas. Ejemplo de cómo quedaría (Benjamin llena las versiones reales):

```
# software/raspberry/requirements.txt
# Generado con: pip freeze | grep -E "opencv|numpy|pyserial|ultralytics|onnxruntime|tflite|litert"
# Pi de producción: Pi 4B, Raspbian Bookworm 64-bit, Python 3.11.x
# Fecha de freeze: 2026-MM-DD  <-- completar

opencv-contrib-python==4.X.X.XX   # <-- completar con pip freeze
numpy==1.X.X                       # <-- IMPORTANTE: confirmar que 1.x no 2.x
pyserial==3.X                      # <-- completar
ultralytics==8.X.X                 # <-- completar
onnxruntime==1.X.X                 # <-- completar (si se usa; si no, quitar)
tflite-runtime==2.14.0             # ya pineado
ai-edge-litert==2.1.3              # ya pineado
```

**Paso 2 — validar reproducibilidad (hacer UNA vez antes del mundial):**

```bash
# En una Pi de repuesto o en un venv limpio de la misma Pi:
python3 -m venv /tmp/test-venv
source /tmp/test-venv/bin/activate
pip install --upgrade pip
pip install -r /path/to/requirements.txt
# Verificar que todo instala sin errores:
python3 -c "import cv2; import numpy; import serial; print('OK')"
python3 -c "from tflite_runtime.interpreter import Interpreter; print('TFLite OK')"
# Tiempo esperado: 8-15 min en Pi 4B con conexión decente
deactivate
rm -rf /tmp/test-venv
```

**Paso 3 — incluir versión de Python en el comentario del archivo.**

### 2.3 Cómo validarlo en banco

```bash
# En Pi de producción o venv limpio:
python3 -m venv /tmp/venv-ci
source /tmp/venv-ci/bin/activate
pip install -r software/raspberry/requirements.txt 2>&1 | tee /tmp/install-log.txt
grep -i "error\|conflict\|incompatible" /tmp/install-log.txt
# Si no hay líneas: PASS
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "import numpy as np; print(np.__version__)"
deactivate && rm -rf /tmp/venv-ci
```

### 2.4 Checklist de aprobación — #68

- [ ] `pip freeze` ejecutado en la Pi de producción activa (la que corre el modelo).
- [ ] `requirements.txt` actualizado con versiones exactas (no `>=`, no rangos).
- [ ] Versión de Python anotada en comentario del archivo.
- [ ] Instalación desde cero probada en venv limpio sin errores.
- [ ] Resultado anotado en TEST_LOG como T-002 `[SW]`.
- [ ] PR creado con referencia a #68.

---

<a name="66"></a>
## 3. #66 — `send_frame()` sin clamp de rango ni `SerialException` (Track A/comms)

### 3.1 Análisis

**Situación observada en `software/raspberry/final_rpi/Main.py` líneas 98-116:**

```python
def send_frame(speed, angle, green_state, silver_line_flag):
    output = bytes([
        SYNC_SPEED, clamp_byte(speed),
        SYNC_ANGLE, clamp_byte(angle + 90),
        ...
    ])
    ser.write(output)    # <-- sin try/except
    ser.flush()          # <-- sin try/except; puede bloquearse si write_timeout no es respetado
```

**Problemas específicos:**

1. **`angle + 90` puede exceder 255.** Si el algoritmo de línea devuelve `angle = 180` (caso extremo válido según el contrato del protocolo: "angle [0,180] se envía como angle + 90"), entonces `angle + 90 = 270 > 255`. `clamp_byte(270) = 255` lo atrapa en ese caso, pero `angle = -90` da `clamp_byte(0)` = 0, que colisiona con un byte neutro. El contrato real del código de línea (línea 756: `angle = (math.atan2(...)/math.pi*180) - 90`) produce ángulos en [-90°, +90°], así que el rango efectivo enviado es `[0°, 180°]` — pero si otro estado produce ángulo fuera de rango, el clamp global de `clamp_byte` lo silencia silenciosamente sin warning.

2. **Sin `try/except serial.SerialException` en `ser.write()` / `ser.flush()`.** Un cable desconectado, un reset del Teensy, o un overflow del buffer UART durante `flush()` lanza `SerialException`. Esta excepción no está capturada → sube al `while True` de módulo → mata el proceso entero. Con el fix del #108 (systemd), el proceso reinicia, pero se pierde el frame en curso y el Teensy recibe silencio durante ~2 s. Sin el fix del #108, el proceso muere y no hay restart.

3. **`ser.flush()` en pyserial con `write_timeout`:** la doc de pyserial indica que `flush()` espera vaciado del buffer de escritura del OS. Si el UART está saturado y el timeout del driver expira, `flush()` puede levantar `SerialTimeoutException` (subclase de `SerialException`). El `write_timeout=SERIAL_TIMEOUT_S` en línea 67 no garantiza protección en `flush()` en todas las versiones de pyserial en ARM.

### 3.2 Propuesta: helper `send_frame_safe()`

Benjamin decide si reemplaza `send_frame()` en su lugar o si crea `send_frame_safe()` como wrapper temporal. Se muestra como función nueva para minimizar el diff:

```python
import serial  # ya importado al tope del archivo

# Contador de errores serial (para telemetría y decisión de reinicio)
_serial_error_count = 0
_SERIAL_ERROR_THRESHOLD = 5   # Si falla 5 veces seguidas, el proceso se considera disfuncional

def send_frame_safe(speed, angle, green_state, silver_line_flag):
    """
    Versión defensiva de send_frame:
    - Clampea speed a [0, 100] y angle a [-90, 90] (rangos reales del algoritmo de línea)
      antes de pasárselos a clamp_byte, con warning si se sale del rango esperado.
    - Captura SerialException / SerialTimeoutException sin matar el proceso.
    - Cuenta errores consecutivos y relanza si supera el threshold para que el
      restart de último recurso (try/except en main()) pueda actuar.
    """
    global _serial_error_count

    # ---- 1. Clamp con diagnóstico ----
    SPEED_MAX = 100
    ANGLE_MIN, ANGLE_MAX = -90, 90

    if speed < 0 or speed > SPEED_MAX:
        print(f"[WARN send_frame] speed={speed} fuera de [0,{SPEED_MAX}] -> clampando")
        speed = max(0, min(SPEED_MAX, speed))

    if angle < ANGLE_MIN or angle > ANGLE_MAX:
        print(f"[WARN send_frame] angle={angle} fuera de [{ANGLE_MIN},{ANGLE_MAX}] -> clampando")
        angle = max(ANGLE_MIN, min(ANGLE_MAX, angle))

    output = bytes([
        SYNC_SPEED,      clamp_byte(speed),
        SYNC_ANGLE,      clamp_byte(int(angle) + 90),
        SYNC_GREEN_STATE, clamp_byte(green_state),
        SYNC_SILVER_LINE, clamp_byte(int(bool(silver_line_flag))),
    ])

    # ---- 2. Escribir con manejo de excepcion ----
    try:
        ser.write(output)
        ser.flush()
        _serial_error_count = 0   # reset contador en éxito
    except serial.SerialTimeoutException as e:
        _serial_error_count += 1
        print(f"[WARN serial] SerialTimeoutException en send_frame ({_serial_error_count}/{_SERIAL_ERROR_THRESHOLD}): {e}")
        if _serial_error_count >= _SERIAL_ERROR_THRESHOLD:
            print("[ERROR serial] Demasiados timeouts consecutivos -> relanzando para restart")
            raise   # el try/except de main() lo captura y hace restart limpio
    except serial.SerialException as e:
        _serial_error_count += 1
        print(f"[WARN serial] SerialException en send_frame ({_serial_error_count}/{_SERIAL_ERROR_THRESHOLD}): {e}")
        if _serial_error_count >= _SERIAL_ERROR_THRESHOLD:
            print("[ERROR serial] Demasiados errores serial -> relanzando para restart")
            raise
    except Exception as e:
        # Excepcion inesperada — siempre relanzar
        print(f"[ERROR send_frame] excepcion inesperada: {e!r}")
        raise

    # ---- 3. Telemetria (sin cambios respecto al original) ----
    global frames_sent, last_tx_telemetry
    frames_sent += 1
    now = time.monotonic()
    if now - last_tx_telemetry >= TELEMETRY_INTERVAL_S:
        print(f"[TLM] frames_sent={frames_sent} estado={estado} serial_errors={_serial_error_count}")
        last_tx_telemetry = now

    return output
```

**Integración:** reemplazar cada llamada a `send_frame(...)` por `send_frame_safe(...)` en el resto del archivo (hay 3 call sites: línea 663 en `modo_rescate`, línea 814 en el loop de línea). El `send_frame` original puede dejarse como stub o eliminarse.

### 3.3 Cómo validarlo en banco

```bash
# Test de desconexión de cable serial en caliente:
# 1. Arrancar el proceso con systemd o directamente.
# 2. Mientras el robot está en estado 'linea', desconectar el cable UART entre RPi y Teensy.
# 3. Observar en journalctl que aparecen los [WARN serial] sin traceback fatal.
# 4. Reconectar el cable.
# 5. Verificar que el proceso continúa vivo (systemctl status debe seguir "active").
# 6. Verificar que cuando se alcanzan 5 errores consecutivos, el proceso reinicia
#    (systemd lo relanza en 2 s).

# Test de clamp:
python3 -c "
import sys; sys.path.insert(0, '.')
# Simular import parcial para testear solo send_frame_safe:
# (simplificado — en banco real conviene un test script dedicado)
def clamp_byte(v): return max(0, min(255, int(v)))
speed = 150; angle = 120
speed = max(0, min(100, speed))
angle = max(-90, min(90, angle))
print(f'speed={speed} angle={angle} angle+90={int(angle)+90}')
assert speed == 100
assert angle == 90
assert int(angle)+90 == 180
print('PASS')
"
```

### 3.4 Checklist de aprobación — #66

- [ ] `send_frame_safe()` o el reemplazo inline tiene `try/except serial.SerialException`.
- [ ] `try/except serial.SerialTimeoutException` separado (subclase de `SerialException`).
- [ ] Clamp de `speed` a [0, 100] y `angle` a [-90, 90] con print de warning si fuera de rango.
- [ ] Contador `_serial_error_count` visible en telemetría.
- [ ] Test de desconexión en caliente: el proceso no muere (o reinicia limpiamente vía systemd).
- [ ] Test de clamp: valores fuera de rango producen warning en log.
- [ ] Entrada T-003 `[SW][COMMS]` en `testing/TEST_LOG.md`.
- [ ] PR creado con referencia a #66.

---

<a name="banco"></a>
## 4. Protocolo de banco — Gate de calidad reusable (rol de Benjamin)

> Este protocolo lo usa Benjamin para validar **todos** los PRs que toquen RPi o comms, incluyendo los de Lucio (#113, #110, #65, #64, #111) y los de Laureano. Es el activo más valioso de Benjamin: un banco reproducible valen más que un review de código en papel.

### 4.1 Equipamiento mínimo del banco

| Elemento | Propósito |
|---|---|
| RPi 4B (la de producción o una idéntica) | target real |
| Teensy 4.1 con firmware de producción | comms real |
| Cable UART entre RPi y Teensy | test de desconexión en caliente |
| Cámara USB | test de desconexión de cámara en caliente |
| PC de monitoreo con cable UART adicional | ver serial del Teensy independientemente |
| Fuente de laboratorio 5V/3A para RPi | evitar brownout por batería descargada |
| `testing/TEST_LOG.md` + cronómetro | registro obligatorio |
| Linterna o luz ajustable | simular condiciones de pista |

### 4.2 Sesión de banco — flujo estándar

```
ANTES DEL TEST
──────────────
[ ] Cargar batería / conectar fuente de lab.
[ ] Verificar que el firmware Teensy en el banco es el commit que dice el PR.
[ ] Verificar que el código RPi en el banco es el branch del PR (no main).
[ ] Anotar en TEST_LOG: T-XXX, fecha, tester, firmware commit, RPi commit.

DURANTE EL TEST
───────────────
[ ] Arrancar proceso RPi (manual o vía systemd según lo que esté testeando).
[ ] Ejecutar los pasos del procedimiento del PR (o del test específico abajo).
[ ] Anotar métricas observadas en tabla de TEST_LOG mientras ocurren, no de memoria.
[ ] Si algo falla, NO modificar nada. Anotar la falla exacta (mensaje de error, línea, timestamp).

DESPUÉS DEL TEST
────────────────
[ ] Commitar TEST_LOG con el resultado antes de cerrar la sesión.
[ ] Si pasó: aprobar PR con referencia al ID del test ("Test T-XXX ✅, ver TEST_LOG").
[ ] Si falló: comentar en el PR con la falla exacta y qué se necesita para re-test.
[ ] Si abrió un bug nuevo: abrir Issue antes de cerrar la sesión de banco.
```

### 4.3 Test de inyección de fallas — guía rápida

Estos son los tests de falla que Benjamin ejecuta para validar resiliencia. Aplicar a cualquier PR que toque visión, comms, o arranque:

#### Falla F1 — Desconexión de cámara en caliente

```
Setup: proceso RPi corriendo en estado 'linea', video activo.
Acción: desconectar físicamente el cable USB de la cámara mientras corre.
Esperar: 3 segundos.
Reconectar: el cable.
Medir:
  - ¿El proceso siguió vivo? (systemctl status)
  - ¿Cuántos frames None antes del restart del VideoStream? (ver logs)
  - ¿El Teensy recibió algún comando durante el blackout? (serial monitor)
  - ¿El VideoStream se recuperó solo? (FRAME_NONE_RESTART_THRESHOLD = 30 → ~0.3 s)
Criterio PASS: proceso vivo, VideoStream recuperado en ≤ 2 s, Teensy no recibió garbage.
Repetir: 3 veces.
```

#### Falla F2 — Desconexión de cable UART en caliente

```
Setup: proceso RPi corriendo, Teensy conectado, ver output de ambos.
Acción: desconectar el cable TX/RX entre RPi y Teensy mientras el robot está en 'linea'.
Esperar: 5 segundos.
Reconectar.
Medir:
  - ¿Apareció SerialException en log de RPi?
  - ¿El proceso reinició (systemd) o continuó?
  - ¿Cuántos frames de error serial antes del reinicio?
  - ¿El Teensy hizo timeout y activó su watchdog? (si tiene uno implementado)
Criterio PASS: SerialException capturada con warning, no traceback fatal, reinicio limpio.
Repetir: 3 veces.
```

#### Falla F3 — Kill -9 del proceso (simula OOM o crash duro)

```
Setup: proceso corriendo vía systemd, estado 'linea'.
Acción: sudo kill -9 $(systemctl show -p MainPID robot.service | cut -d= -f2)
Medir (con cronómetro):
  - Tiempo hasta que systemctl muestra "active" nuevamente.
  - Tiempo hasta que aparece el primer "[TLM]" en journalctl.
  - ¿El Teensy recibió speed=0 antes del kill? (no, porque kill -9 no llama atexit/SIGTERM)
    → esto es esperado: el fix del #108 propone SIGTERM para el stop limpio.
    Verificar que SIGTERM (systemctl stop) sí envía speed=0.
Criterio PASS: restart en ≤ 5 s, journalctl muestra crash + restart, SIGTERM envía speed=0.
Repetir: 3 veces, anotar tiempos individuales.
```

#### Falla F4 — Arranque con cámara no disponible

```
Setup: desconectar cámara ANTES de arrancar el proceso.
Acción: sudo systemctl start robot.service
Medir:
  - ¿El proceso falla al arrancar? (antes del fix: sí, crash en línea 66 module-level)
  - ¿Systemd lo reintenta?
  - ¿Cuántos reintentos antes de encontrar la cámara?
Acción: conectar la cámara después de 10 s.
Criterio PASS: proceso eventualmente arranca cuando la cámara está disponible, ≤ 3 reintentos.
```

#### Falla F5 — Arranque con Teensy apagado

```
Setup: apagar o desconectar el Teensy. Arrancar proceso RPi.
Medir:
  - ¿El proceso falla en la apertura del serial (línea 67)?
  - Si falla, ¿systemd reintenta correctamente?
  - Una vez conectado el Teensy, ¿el proceso detecta el TEENSY_BOOT y pasa a 'esperando' correctamente?
Criterio PASS: proceso arranca o reintenta, y al conectar Teensy el handshake funciona.
```

### 4.4 Qué medir y cómo registrar en TEST_LOG.md

Cada test de banco genera una entrada en `testing/TEST_LOG.md` con el formato de la plantilla del archivo. Para los tests de falla de Benjamin, la tabla de métricas debe incluir:

| Métrica | Descripción |
|---|---|
| `proceso_vivo` | ✅ si `systemctl is-active` retorna "active" al final del test |
| `tiempo_restart_s` | segundos desde kill/falla hasta `active` en systemd (medir con cronómetro) |
| `serial_errors` | cantidad de líneas `[WARN serial]` en journalctl durante el test |
| `teensy_speed0` | ✅ si el serial monitor del Teensy confirmó recibir speed=0 en el shutdown limpio |
| `frames_none_count` | cantidad de frames None consecutivos hasta recovery (del log) |
| `reproducible` | si el resultado fue el mismo en las 3 repeticiones |

**Frecuencia mínima:** una sesión de banco por PR de RPi/comms antes de dar el approve. Para PRs de solo Teensy que no tocan comms, puede reducirse a F3 + F5.

### 4.5 Template de entrada TEST_LOG para tests de falla (copiar y llenar)

```markdown
## T-XXX · YYYY-MM-DD · [SW] Inyección de falla F1/F2/F3/F4/F5 — <nombre del PR>

**Tester:** @benjaminvillagran · **Robot:** rev-current · **Pista:** banco IITA
**Issue/PR relacionado:** #NNN

**Objetivo.** Verificar que el sistema se recupera de <tipo de falla> sin intervención humana.

**Setup.**
- Batería / fuente: X.XV.
- Firmware Teensy commit: <sha>.
- RPi branch/commit: <sha>.
- Cámara: conectada / desconectada según el test.
- Serial: conectado / desconectado según el test.

**Procedimiento.**
1. Arrancar proceso con `sudo systemctl start robot.service`.
2. Verificar estado 'linea' activo (ver journalctl).
3. <Acción de falla específica de F1/F2/F3/F4/F5>.
4. Esperar N segundos.
5. <Acción de recovery si aplica>.
6. Medir métricas.
7. Repetir 3 veces.

**Resultado.**

| Métrica | Esperado | Run 1 | Run 2 | Run 3 | OK |
|---|---|---|---|---|---|
| proceso_vivo | ✅ | | | | |
| tiempo_restart_s | < 5 s | | | | |
| serial_errors | ≤ 5 | | | | |
| teensy_speed0 | ✅ (en SIGTERM) | | | | |
| reproducible | ✅ | | | | |

**Conclusión.** <qué pasó realmente>

**Acción.**
- PR #NNN: aprobado / necesita cambios.
- Issues abiertos: <si aplica>.
```

---

## Resumen de prioridades para Benjamin

| Prioridad | Tema | Issue | Sprint | Estimado horas |
|---|---|---|---|---|
| P0 | Auto-restart systemd | #108 | Sprint 1 | 2-3 h (incluyendo validación) |
| P0 | `try/except` + `__main__` guard | #108 | Sprint 1 | 1-2 h |
| P1 | `requirements.txt` pineado | #68 | Sprint 1 | 0.5-1 h |
| P1 | `send_frame_safe()` | #66 | Track A | 1-2 h |
| Continuo | Gate de banco (PRs de Lucio y Laureano) | — | Todo | ~1 h por PR |

**Camino crítico inmediato:**

1. Implementar y testear `robot.service` + `__main__` guard (puede hacerse sin robot, solo con Pi + Teensy en banco).
2. Hacer `pip freeze` en la Pi de producción y commitear `requirements.txt` pineado (5 minutos).
3. Implementar `send_frame_safe()` y validar con test F2.
4. Usar el protocolo de banco para aprobar el primer PR de Lucio cuando llegue.

---

*Preparado el 2026-05-18. NO commiteado. Benjamin valida, adapta las rutas y parámetros a su setup real, y hace el commit/PR. Coach: @gviollaz.*
