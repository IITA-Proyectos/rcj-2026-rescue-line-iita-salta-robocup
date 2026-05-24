# Mediciones fisicas pendientes - sesion ~45 min con el robot

Estos valores NO se pueden obtener del codigo. Hay que medirlos con el robot encendido antes de cerrar el TDP.

## Prioridad ALTA (afectan la nota directamente)

### 1. FPS real de vision (5 min)

**Estado:** medido en T-002. Resultado: line-following loop a 91.33 FPS durante una ventana de 30 s desde el service real de Raspberry Pi.

- Agregar al inicio de `Main.py`:

```python
import time
t0 = time.time()
frames = 0
```

- Agregar al final del loop principal:

```python
frames += 1
print(f"FPS: {frames / (time.time() - t0):.1f}")
```

- Correr 30 segundos en modo line following.
- Anotar el FPS promedio.
- Donde va en el TDP: Seccion 4a, reemplaza "camera-loop speed" o cualquier descripcion generica de velocidad.

### 2. Voltaje bajo carga (10 min)

**Estado:** parcialmente medido en T-001. Ya hay 12.6 V inicial, 12.5 V despues de 5 min en reposo y 1 h hasta 10.5 V en funcionamiento continuo. Falta registrar el voltaje final exacto de la prueba extrema con motores a `speed = 60` + pickup.

- Multimetro en los bornes de la bateria.
- Medir en reposo con el robot quieto y encendido.
- Medir mientras los 4 motores corren y los 5 servos ejecutan una secuencia de pickup.
- Anotar `V_reposo` y `V_carga`.
- Donde va en el TDP: Seccion 3b y Tabla 9.

### 3. Precision de `runDistance()` (10 min)

**Estado:** medido en T-001. Resultado inicial: error aproximado de 1 cm en distancias cortas y 1-2 cm en distancias mayores.

- Marcar 10 cm, 25 cm y 50 cm en el piso con cinta.
- Correr cada distancia 5 veces.
- Medir con regla el error real.
- Anotar: distancia pedida, media real y error maximo.
- Donde va en el TDP: Tabla 5 y Tabla 8.

### 4. Precision de `runAngle()` (10 min)

**Estado:** medido en T-001. Resultado inicial: el robot frena aproximadamente al grado, consistente con la tolerancia IMU de +/-1.0 grado.

- Pedir 90 grados exactos, 10 veces.
- Medir angulo final con transportador o display de IMU.
- Anotar error promedio y maximo.
- El codigo corta con tolerancia IMU de +/-1.0 grado. Confirmar si se cumple fisicamente.
- Donde va en el TDP: Tabla 5 y Tabla 8.

### 5. Tasa de pickup (10 min)

- Posicionar victima negra en posicion estandar.
- Ejecutar 10 intentos de pickup.
- Contar exitosos, fallidos y casos en que la victima cae despues.
- Repetir con victima plateada.
- Anotar: X/10 negra, Y/10 plateada.
- Donde va en el TDP: Tabla 8, Seccion 5.

## Prioridad MEDIA (mejoran la nota pero no son criticas)

### 6. Autonomia de bateria

**Estado:** medido en T-001. Resultado inicial: aproximadamente 1 h de funcionamiento continuo hasta 10.5 V.

- Cargar la bateria completa.
- Correr el robot en line following continuo.
- Anotar cuantos minutos pasan hasta bajar a 10.5 V.
- Donde va: Seccion 3b.

### 7. FPS del detector AI

**Estado:** medido en T-002 para el loop rescue/deposit completo. Resultado: 22.25-22.40 FPS desde `journalctl` con TFLite, anti-flash/AGCWD y tracker activos.

- En modo rescue, agregar un timer alrededor de la llamada de inferencia.
- Anotar ms por inferencia y FPS resultante.
- Donde va: Seccion 4a.

### 8. Validacion anti-flash + AGCWD con linterna fuerte

- Activar modo rescue con `ENABLE_ANTIFLASH=True`.
- Apuntar una linterna blanca fuerte contra la pared/zona de evacuacion.
- Grabar 30 segundos con y sin destello directo.
- Registrar falsos positivos antes/despues de pasar por `anti_flash_preprocess()` + AGCWD.
- Verificar que la pelota negra y plateada sigan detectandose cuando no quedan totalmente tapadas por el destello.
- Donde va: Seccion 4b, Innovation 3.

### 9. Validacion del modelo nuevo con paredes de colores

- Usar la rama que contiene el modelo reentrenado desde Roboflow.
- Confirmar que el entrenamiento usado corresponde a `yolov8n.pt`, 100 epochs, `imgsz=256`, AMP activado, `hsv_s=0.7`, `hsv_v=0.8`, `mosaic=1.0`, `mixup=0.1`, `copy_paste=0.1` y `erasing=0.4`.
- Probar detecciones con pared blanca, marron claro, naranja, amarilla y gris.
- Repetir explicitamente el caso critico: pared naranja fluor + victimas negras + zona roja visible.
- Registrar falsos positivos de `rojo_alto`, falsos negativos de `negro` y estabilidad de `plateado`.
- Confirmar que pelota negra y pelota plateada se mantienen separadas bajo linterna fuerte.
- Anotar si la pared naranja deja de confundirse con la zona de deposito roja.
- Donde va: Seccion 4b, Tabla 8 y dataset robustness snapshot.

## Formato para anotar resultados

Cuando terminen la sesion, abrir `testing/TEST_LOG.md` y agregar una entrada `T-001` con todos los valores medidos.

Usar la plantilla del punto 3 de `testing/TEST_LOG.md`:

```markdown
## T-001 - YYYY-MM-DD - [MECH][ELEC][SW][PERF] Medicion fisica final para TDP

**Tester:** @handle
**Robot rev:** rev-current
**Pista / banco:** sala IITA / pista oficial / mesa de electronica
**Issue/PR relacionado:** #NNN

**Objetivo.** Medir los valores fisicos que no pueden extraerse del codigo para completar la evidencia del TDP.

**Setup.**
- Bateria: X.X V al arranque, X.X V al final.
- Iluminacion: fluorescente / mixta / LED zona / natural.
- Pista o banco: descripcion breve.
- Firmware commit: `<sha corto>`.
- RPi commit/modelo: `<sha corto>` / `<modelo usado>`.
- Modo RPi: headless / debug / grabacion.

**Procedimiento.**
1. Medir FPS real de vision.
2. Medir voltaje en reposo y bajo carga.
3. Ejecutar pruebas de `runDistance()`.
4. Ejecutar pruebas de `runAngle()`.
5. Ejecutar pruebas de pickup negro y plateado.
6. Ejecutar validacion anti-flash + AGCWD con linterna fuerte.
7. Ejecutar validacion del modelo nuevo con paredes de colores.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| FPS real de vision | estable durante 30 s | ... | PASS/PARTIAL/FAIL |
| Voltaje bajo carga | sin reset ni caida critica | ... | PASS/PARTIAL/FAIL |
| Error `runDistance()` | bajo y repetible | ... | PASS/PARTIAL/FAIL |
| Error `runAngle()` | cerca de +/-1.0 grado IMU | ... | PASS/PARTIAL/FAIL |
| Pickup victima negra | 10 intentos | .../10 | PASS/PARTIAL/FAIL |
| Pickup victima plateada | 10 intentos | .../10 | PASS/PARTIAL/FAIL |
| Anti-flash + AGCWD | sin falsos positivos por destello visible | ... | PASS/PARTIAL/FAIL |
| Pared naranja fluor sin falso `rojo_alto` | sin confusion con deposito rojo | ... | PASS/PARTIAL/FAIL |
| Paredes blanca/marron/amarilla/gris | deteccion estable | ... | PASS/PARTIAL/FAIL |

**Evidencia.**
- Video:
- Foto:
- Log:
- Otro:

**Conclusion.** Que paso realmente y que se aprendio.

**Accion.**
- Issue abierto/cerrado:
- Re-test programado:
- Cambio de hardware/software:
```
