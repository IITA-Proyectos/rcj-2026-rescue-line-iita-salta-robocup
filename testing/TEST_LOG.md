# TEST_LOG - Bitacora de tests IITA RCJ 2026

**Equipo:** IITA Salta  
**Competencia:** RoboCupJunior Rescue Line 2026  
**Uso:** evidencia directa para TDP, poster y video.

Cada ensayo se anota con ID secuencial `T-XXX`, categoria entre corchetes y resultado claro: `PASS`, `PARTIAL` o `FAIL`.

---

## 1. Indice por categoria

### `[MECH]` - Mechanical reliability (TDP T7)

| ID | Fecha | Titulo | Resultado |
|---|---|---|---|
| T-001 | 2026-05-23 | Medicion fisica inicial con robot completo | PASS |

### `[ELEC]` - Electronic reliability (TDP T11)

| ID | Fecha | Titulo | Resultado |
|---|---|---|---|
| T-001 | 2026-05-23 | Medicion fisica inicial con robot completo | PASS/PARTIAL |

### `[SW]` - Software reliability (TDP T14)

| ID | Fecha | Titulo | Resultado |
|---|---|---|---|
| T-002 | 2026-05-23 | FPS real y transicion de estados desde systemd | PASS |

### `[PERF]` - Performance evaluation (TDP T15)

| ID | Fecha | Titulo | Resultado |
|---|---|---|---|
| T-001 | 2026-05-23 | Medicion fisica inicial con robot completo | PASS/PARTIAL |
| T-002 | 2026-05-23 | FPS real y transicion de estados desde systemd | PASS |

---

## 2. Convenciones

- **ID:** `T-001`, `T-002`, secuencial y sin reutilizar.
- **Fecha:** `YYYY-MM-DD`, fecha real del ensayo.
- **Categoria:** uno o dos tags, por ejemplo `[SW]` o `[MECH][PERF]`.
- **Resultado:** `PASS`, `PARTIAL` o `FAIL`.
- **Tester:** nombre o usuario GitHub de quien ejecuto.
- **Robot rev:** SHA corto, branch o `rev-current`.
- **Issue/PR:** link o numero de issue si verifica un fix o destapa un bug.
- **Evidencia:** foto, video, log serial, captura de pantalla, medicion o archivo relacionado.

---

## 3. Plantilla para nueva entrada

Copiar este bloque al final de la seccion 4 y agregar una fila en el indice.

```markdown
## T-XXX - YYYY-MM-DD - [CAT] Titulo corto descriptivo

**Tester:** @handle  
**Robot rev:** rev-current  
**Pista / banco:** sala IITA / pista oficial / mesa de electronica  
**Issue/PR relacionado:** #NNN

**Objetivo.** Una oracion con lo que se queria verificar.

**Setup.**
- Bateria: X.X V al arranque, X.X V al final.
- Iluminacion: fluorescente / mixta / LED zona / natural.
- Pista o banco: descripcion breve.
- Firmware commit: `<sha corto>`.
- RPi commit/modelo: `<sha corto>` / `<modelo usado>`.
- Modo RPi: headless / debug / grabacion.

**Procedimiento.**
1. Paso 1.
2. Paso 2.
3. Paso 3.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| ... | ... | ... | PASS/PARTIAL/FAIL |

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

---

## 4. Entradas

### T-001 - 2026-05-23 - `[MECH][ELEC][PERF]` Medicion fisica inicial con robot completo

**Tester:** Benjamin Villagran  
**Robot rev:** rev-current  
**Pista / banco:** robot completo en pista/banco de prueba  
**Issue/PR relacionado:** evidencia para TDP 2026

**Objetivo.** Medir valores fisicos que no se pueden obtener del codigo para completar la evidencia del TDP: autonomia, estabilidad de bateria, precision de `runDistance()` y precision de `runAngle()`.

**Setup.**
- Bateria: 12.6 V al arranque.
- Iluminacion: no registrada.
- Pista o banco: prueba con robot completo.
- Firmware commit: `rev-current`.
- RPi commit/modelo: `rev-current` / modelo de produccion.
- Modo RPi: programa completo corriendo.

**Procedimiento.**
1. Encender el robot con bateria cargada y registrar voltaje inicial.
2. Dejar el robot encendido en reposo durante 5 minutos y registrar voltaje.
3. Ejecutar movimiento continuo hasta que la bateria llegue a 10.5 V.
4. Ejecutar prueba de estres durante 10 minutos con programa completo, motores a `speed = 60` y secuencia de pickup.
5. Ejecutar pruebas de `runDistance()` en distancias cortas y largas.
6. Ejecutar pruebas de `runAngle()` y verificar si el robot corta dentro de la tolerancia de giro.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| Voltaje inicial bateria 3S | cerca de carga completa | 12.6 V | PASS |
| Caida en reposo 5 min | sin caida significativa | 12.6 V -> 12.5 V | PASS |
| Autonomia continua hasta 10.5 V | mantener funcionamiento prolongado | 1 h hasta 10.5 V | PASS |
| Estres motores + pickup | resistir carga alta sin evidencia de fallo | 10 min con programa completo, motores a `speed = 60` y pickup; voltaje final no registrado | PARTIAL |
| Error `runDistance()` en distancia corta | bajo y repetible | aproximadamente 1 cm | PASS |
| Error `runDistance()` en distancia mayor | bajo y repetible | aproximadamente 1-2 cm | PASS |
| Error `runAngle()` | detenerse dentro de la tolerancia IMU de +/-1 grado | frena al grado | PASS |

**Evidencia.**
- Video: pendiente de adjuntar si se usa en PDF/poster.
- Foto: pendiente de adjuntar si se usa en PDF/poster.
- Log: mediciones reportadas por el equipo durante sesion con robot a mano.
- Otro: usar esta entrada como fuente de la tabla de resultados fisicos del TDP.

**Conclusion.** El robot mostro buena estabilidad electrica en reposo, autonomia cercana a 1 h hasta 10.5 V y precision mecanica suficiente para documentar la calibracion de 25 counts/cm. `runAngle()` confirma la tolerancia de giro de aproximadamente +/-1 grado. La prueba de estres de 10 minutos es util como evidencia cualitativa, pero necesita el voltaje final exacto para cerrar como medicion cuantitativa completa.

**Accion.**
- Registrar voltaje final exacto en la prueba de estres con motores a `speed = 60` + pickup.
- Completar pruebas pendientes de FPS real, pickup X/10, deposit X/10, anti-flash y paredes de colores.

---

### T-002 - 2026-05-23 - `[SW][PERF]` FPS real y transicion de estados desde systemd

**Tester:** Benjamin Villagran  
**Robot rev:** rev-current  
**Pista / banco:** robot completo ejecutando el service de Raspberry Pi  
**Issue/PR relacionado:** evidencia para TDP 2026

**Objetivo.** Verificar velocidad real del programa ejecutado como service y confirmar una transicion Teensy -> Raspberry Pi durante la mision.

**Setup.**
- Bateria: no registrada en esta prueba.
- Iluminacion: no registrada.
- Pista o banco: robot encendido con programa completo.
- Firmware commit: `rev-current`.
- RPi commit/modelo: `rev-current` / modelo TFLite de produccion.
- Modo RPi: `systemd` service, salida capturada con `journalctl`.

**Procedimiento.**
1. Reiniciar/ejecutar el service de Raspberry Pi.
2. Esperar warmup del modelo TFLite.
3. Dejar el robot en `estado=linea` durante mas de 30 s.
4. Registrar el log `[LINE-FPS]`.
5. Ejecutar flujo de rescate/deposito hasta recibir el byte `0xF8` desde Teensy.
6. Registrar logs `[HEADLESS] FPS` durante `estado=depositar`.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| Service inicia TFLite y warmup | warmup completo antes de competir | `Warmup completado.` | PASS |
| FPS real de line following | estable durante 30 s | `[LINE-FPS] avg=91.33` | PASS |
| FPS rescue/deposit AI loop | estable con TFLite + anti-flash/AGCWD/tracker | 22.25-22.40 FPS | PASS |
| Transicion rescate -> depositar | Teensy envia `0xF8` y RPi cambia estado | `Llego 248 -> terminar rescate y cambiar a depositar` | PASS |
| Telemetria UART durante service | frames enviados siguen aumentando | `frames_sent` sube de 1 a 2204 durante linea | PASS |

**Evidencia.**
- Log line following: `[LINE-FPS] avg=91.33`.
- Log rescue/deposit: `[HEADLESS] FPS ~ 22.40`, `22.37`, `22.34`, `22.32`, `22.29`, `22.27`, `22.25`.
- Log de transicion: `Llego 248 -> terminar rescate y cambiar a depositar`.
- Fuente: `journalctl` del service de Raspberry Pi.

**Conclusion.** El programa no solo corre desde el service, sino que mantiene una tasa alta de linea y una tasa estable de rescate/deposito con TFLite, anti-flash, AGCWD y tracker activos. Tambien se verifico una transicion real de estado desde Teensy hacia Raspberry Pi.

**Accion.**
- Adjuntar captura o copia del `journalctl` al paquete final si el formato de entrega lo permite.
- Completar pickup, deposit, anti-flash con linterna y paredes de colores.

---

Bitacora inicializada para resolver el bloqueo de evidencia de TDP identificado en #93, #98 y `project/backlog/tdp-audit-bugs-prioritarios.md`.
