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
| Estres motores + pickup | resistir carga alta sin evidencia de fallo | 10 min con programa completo, motores a `speed = 60` y pickup continuo; caida de 1.4 V respecto al inicio de la prueba | PASS |
| Error `runDistance()` en distancia corta | bajo y repetible | aproximadamente 1 cm | PASS |
| Error `runDistance()` en distancia mayor | bajo y repetible | aproximadamente 1-2 cm | PASS |
| Error `runAngle()` | detenerse dentro de la tolerancia IMU de +/-1 grado | frena al grado | PASS |

**Evidencia.**
- Video/foto: opcional para PDF/poster; las mediciones numericas ya fueron volcadas al TDP.
- Log: mediciones reportadas por el equipo durante sesion con robot a mano.
- Otro: usar esta entrada como fuente de la tabla de resultados fisicos del TDP.

**Conclusion.** El robot mostro buena estabilidad electrica en reposo, autonomia cercana a 1 h hasta 10.5 V y precision mecanica suficiente para documentar la calibracion de 25 counts/cm. `runAngle()` confirma la tolerancia de giro de aproximadamente +/-1 grado. La prueba de estres de 10 minutos cerro sin evidencia de fallo y con una caida de 1.4 V bajo exigencia alta; si se toma el arranque de 12.6 V como referencia, el final derivado es aproximadamente 11.2 V.

**Accion.**
- Si queda tiempo antes del PDF final, repetir el estres con hora de inicio/fin y voltaje inicial/final escritos en video o planilla.
- Completar conteos estadisticos opcionales de pickup/deposito si se quiere convertir la validacion funcional en tasa X/20.

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
- Pickup, deposito, anti-flash con linterna y paredes/fondos de colores quedaron registrados funcionalmente en T-003.

---

### T-003 - 2026-05-23 - `[MECH][SW][PERF]` Validacion funcional de pista completa, deposito y vision robusta

**Tester:** Benjamin Villagran  
**Robot rev:** rev-current  
**Pista / banco:** pista completa con robot final  
**Issue/PR relacionado:** evidencia final para TDP 2026

**Objetivo.** Registrar validaciones funcionales que cierran los puntos pendientes de manipulacion de victimas, deposito con finales de carrera, anti-flash con linterna y modelo final con fondos/paredes de colores.

**Setup.**
- Bateria: misma sesion de pruebas del robot completo.
- Iluminacion: prueba con linterna fuerte para estresar anti-flash.
- Pista o banco: pista completa.
- Firmware commit: `rev-current`.
- RPi commit/modelo: `rev-current` / `/home/iita/Documentos/best (2)_float32.tflite`.
- Modo RPi: programa completo corriendo desde Raspberry Pi de IITA.

**Procedimiento.**
1. Ejecutar pista completa con las 3 victimas/pelotas disponibles.
2. Verificar que el mecanismo pueda recogerlas en una misma pasada y mantenerlas para la secuencia de rescate.
3. Ejecutar deposito con finales de carrera izquierdo y derecho (`FCL`/`FCR`).
4. Activar linterna fuerte y verificar que anti-flash + AGCWD mantengan detecciones utiles.
5. Validar por clase el modelo final TFLite entrenado con estres de linterna y fondos/paredes de colores diferentes.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| Pickup en pista completa | recoger victimas sin reiniciar mecanismo | recoge las 3 pelotas en una sola pasada de pista completa | PASS |
| Retencion/flujo de rescate | no perder victimas despues del pickup | las 3 pelotas permanecen manejables para la secuencia de rescate | PASS |
| Deposito con FCL/FCR | alinear con finales de carrera derecho e izquierdo | deposito funciona correctamente usando finales de carrera derecho e izquierdo | PASS |
| Victima negra bajo paredes/iluminacion variable | deteccion estable | funciona correctamente incluso con paredes de distintos colores | PASS |
| Zona de deposito roja bajo paredes/iluminacion variable | deteccion estable sin confundirse con fondos | funciona correctamente incluso con paredes de distintos colores | PASS |
| Victima plateada con reflejo de linterna | mantener deteccion pese a highlights | funciona muy bien a pesar del reflejo fuerte de la linterna | PASS |
| Zona verde con linterna/reflejo | detectar correctamente aunque sea el caso mas dificil | sigue funcionando correctamente, pero agrega aproximadamente 20 s a la zona de rescate, sin contar salida | PASS |
| Modelo final en Raspberry | usar modelo entrenado con linterna y fondos/paredes de colores | `/home/iita/Documentos/best (2)_float32.tflite` cargado en la Raspberry de IITA funciona correctamente en las pruebas del equipo | PASS |

**Evidencia.**
- Video: recomendado para anexar si se usa en el PDF/poster.
- Foto: imagen de prueba con linterna fuerte sobre la zona de rescate; copiar a `docs/tdp/assets/` si se decide usarla como figura.
- Log: observacion de prueba fisica reportada por Benjamin durante la sesion con robot.
- Otro: el modelo final corresponde al path de produccion de la Raspberry: `/home/iita/Documentos/best (2)_float32.tflite`.

**Conclusion.** La validacion funcional muestra que el mecanismo de rescate ya puede recoger las 3 pelotas en pista completa, que el deposito con finales de carrera izquierdo/derecho esta operativo y que la vision robusta con anti-flash/modelo entrenado para linterna y fondos de colores funciona en el robot real. La clase mas afectada por el destello fue la zona verde: no fallo, pero aumento el tiempo de la zona de rescate aproximadamente 20 s, sin contar la salida. Para una tabla estadistica mas fuerte, el siguiente refinamiento seria repetir pickup/deposito en 10-20 intentos y anotar la tasa exacta.

**Accion.**
- Registrar un conteo X/20 de pickup y deposito si hay tiempo antes del PDF final.
- Guardar video corto de anti-flash con linterna y pista completa como evidencia visual para el TDP/poster.

---

### T-004 - 2026-05-23 - `[SW][PERF]` Regression fix: AGCWD-only vs anti-flash + 100-epoch model

**Tester:** Benjamin Villagran  
**Robot rev:** rev-current  
**Pista / banco:** zona de rescate con linterna fuerte, obstaculos visuales/reflejos y fondos/paredes variables  
**Issue/PR relacionado:** evidencia problema -> fix -> re-test para TDP 2026

**Objetivo.** Documentar una falla real de la version anterior de vision y el cambio que la resolvio. La version anterior usaba AGCWD sin el modelo reentrenado de 100 epochs y no era suficientemente robusta: en ciertas condiciones generaba falsos positivos asociados a zonas de deposito. La version final combina anti-flash, AGCWD y el modelo entrenado 100 epochs con estres de linterna, fondos/paredes de colores y augmentations.

**Setup.**
- Pipeline anterior: AGCWD sin el entrenamiento final de 100 epochs.
- Pipeline final: `anti_flash_preprocess()` + AGCWD + `/home/iita/Documentos/best (2)_float32.tflite`.
- Iluminacion: linterna fuerte impactando la zona de rescate y generando reflejos visibles.
- Condicion visual: obstaculos/reflejos en campo de vision, paredes/fondos variables.
- Modo RPi: ventana debug `Optimizado` con FPS visible.

**Procedimiento.**
1. Ejecutar/analizar el comportamiento de la version anterior con AGCWD solamente.
2. Registrar que el pipeline anterior podia generar falsos positivos en zonas de deposito bajo reflejos/fondos dificiles.
3. Ejecutar el pipeline final con anti-flash + AGCWD + modelo final de 100 epochs.
4. Verificar que la deteccion se mantiene estable a pesar de reflejos y obstaculos visuales.
5. Registrar los FPS visibles del debug como evidencia de que la deteccion seguia corriendo en tiempo real.

**Resultado.**

| Metrica | Pipeline anterior | Pipeline final | OK |
|---|---|---|---|
| Falsos positivos en zonas de deposito | presentes en la version AGCWD-only / modelo anterior | no observados en la prueba final reportada | PASS |
| Estabilidad con linterna/reflejos | inestable en casos dificiles | deteccion se mantiene pese al impacto fuerte de la linterna | PASS |
| Estabilidad con obstaculos visuales | podia confundir elementos del entorno | la caja se mantiene sobre el objetivo relevante en los screenshots de debug | PASS |
| FPS debug observado | no usado como evidencia final | aproximadamente 16.14-16.20 FPS en la ventana `Optimizado` | PASS |

**Evidencia.**
- Screenshots: tres capturas de la ventana `Optimizado` con FPS `16.14`, `16.17` y `16.20 [AGCWD]`, caja de deteccion persistente y reflejos/obstaculos visibles.
- Foto/video: recomendado copiar las capturas a `docs/tdp/assets/` si entran en el PDF final.
- Log: observacion reportada por el equipo durante prueba de vision en el robot.
- Otro: el fix combina un cambio de preprocesamiento (`anti_flash_preprocess()` antes de AGCWD) con un cambio de datos/modelo (100 epochs con linterna y paredes/fondos de colores).

**Conclusion.** Este caso es la evidencia mas clara de iteracion de IA: el problema no era solo de umbrales, sino de distribucion de datos y estabilidad ante reflejos. AGCWD solo mejoraba brillo, pero no eliminaba todos los falsos positivos. El sistema final resolvio el caso observado al combinar compresion de reflejos, normalizacion AGCWD y un modelo reentrenado con ejemplos de linterna/fondos dificiles.

**Accion.**
- Usar este caso como narrativa corta en Performance Evaluation: problema -> diagnostico -> fix -> re-test.
- Si el PDF tiene espacio, incluir una captura como figura de evidencia; si no, dejarla como respaldo en el TEST_LOG.

---

### T-005 - 2026-05-23 - `[MECH][SW][PERF]` Pickup/deposit success-rate sample

**Tester:** Benjamin Villagran  
**Robot rev:** rev-current  
**Pista / banco:** pista/zona de rescate con robot final  
**Issue/PR relacionado:** evidencia estadistica final para TDP 2026

**Objetivo.** Convertir la validacion funcional de T-003 en una muestra estadistica corta para pickup y deposito, de forma que el TDP no dependa solo de observaciones cualitativas.

**Setup.**
- Mecanismo: garra, almacenamiento y deposito final.
- Vision: modelo final `/home/iita/Documentos/best (2)_float32.tflite`.
- Condicion especial: se uso una cinta reflectiva con diametro similar a la pelota plateada real como proxy de prueba; una parte no quedo perfectamente pegada al piso.

**Procedimiento.**
1. Ejecutar 10 intentos de pickup en la zona de rescate.
2. Registrar exitos/fallos.
3. Ejecutar 10 intentos de deposito usando la alineacion con finales de carrera.
4. Registrar exitos/fallos.
5. Analizar el origen del fallo de pickup observado.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| Pickup success rate | >=80% en muestra corta | 8/10 | PASS |
| Deposit success rate | >=90% en muestra corta | 10/10 | PASS |
| Causa principal del fallo de pickup | identificar si es mecanica, vision o artefacto de prueba | falso positivo de pelota plateada causado por cinta reflectiva de diametro similar a la pelota real; la cinta no estaba perfectamente pegada al piso | PASS |
| Detecciones restantes en suelo | mantener detecciones utiles despues del artefacto | las demas detecciones del suelo funcionaron muy bien | PASS |

**Evidencia.**
- Video: recomendado si se usa en el PDF/poster.
- Foto: recomendado si se quiere mostrar el artefacto de cinta reflectiva.
- Log: medicion reportada por el equipo durante prueba final.
- Otro: usar esta entrada para la fila de pickup/deposito de la Tabla 10.

**Conclusion.** El deposito ya esta muy solido en la muestra corta: 10/10 con finales de carrera. El pickup alcanzo 8/10; el problema observado no fue una falla general del mecanismo, sino un falso positivo provocado por una cinta reflectiva usada como sustituto de pelota plateada. Esa cinta imitaba el brillo y diametro de la pelota, pero al no estar perfectamente pegada al piso genero una deteccion enganosa. Con las otras detecciones del suelo, el sistema funciono correctamente.

**Accion.**
- Para el PDF, reportar pickup 8/10 y deposito 10/10 con una nota breve sobre el artefacto de cinta reflectiva.
- En futuras pruebas, usar pelotas plateadas reales o pegar completamente los proxies reflectivos al piso para evitar falsos positivos no representativos.

---

### T-006 - 2026-05-23 - `[MECH][ELEC][SW][PERF]` Terrain, ramp and exit-search evaluation

> Nota posterior: la limitacion de salida/evacuacion registrada en esta prueba fue re-testeada y cerrada en T-008 con un video completo donde el robot sale de la zona de rescate.

**Tester:** Benjamin Villagran  
**Robot rev:** rev-current  
**Pista / banco:** pista de linea + rescate con rampas, sube-baja y obstaculos tipo palillos  
**Issue/PR relacionado:** evidencia de confiabilidad mecanica, sensores y limitaciones restantes para TDP 2026

**Objetivo.** Evaluar el comportamiento del robot en pista completa, rampas, sube-baja y obstaculos visuales/fisicos. Documentar tambien una limitacion real: la salida/busqueda de salida de la zona de rescate todavia no navega correctamente.

**Setup.**
- Linea y rescate: funcionamiento completo observado.
- Evacuacion/salida: modo de busqueda de salida todavia inestable.
- Sensor de color: APDS9960 con LED de alto brillo en posicion estrategica para confirmar plateado/floor color.
- Vision: camara + modelo final para detecciones de rescate.
- Terreno: rampa lateral, rampa de subida, sube-baja, palillos/obstaculos.

**Procedimiento.**
1. Ejecutar intentos de full course con linea + rescate + salida.
2. Separar el resultado por modulo: linea, rescate y busqueda de salida/evacuacion.
3. Ejecutar rampas laterales y rampa de subida.
4. Registrar falso positivo de plateado producido por camara en subida.
5. Aplicar/verificar correccion con sensor de color APDS9960 + LED de alto brillo.
6. Ejecutar sube-baja y registrar recuperacion despues del golpe.
7. Probar palillos/obstaculos molestando en linea y rescate.
8. Registrar el caso limite de cuadrado verde cubierto en mas del 80%.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| Full course completo | terminar linea + rescate + salida | 0/5; linea y rescate funcionan, pero la busqueda de salida/evacuacion no navega correctamente todavia | FAIL aislado |
| Tiempo normal de rescate | medir rescate sin salida | 2 min 40 s, sin contar salida | PASS |
| Tiempo rescate con linterna | medir penalizacion por reflejo | +20 s respecto al rescate normal, sin contar salida | PASS |
| Rampas laterales | mantener trayectoria | 0/10 | FAIL |
| Rampa de subida | subir sin falso plateado ni perdida | 8/10 despues de correccion con APDS9960 + LED; antes la camara podia detectar falso plateado en subida | PASS parcial |
| Sube-baja | recomponerse despues del golpe | 9/10; el fallo ocurrio cuando despues de la caida brusca habia un cuadrado verde y lo ignoro | PASS |
| Palillos/obstaculos en rescate y linea | seguir funcionando pese a clutter | funciona muy bien | PASS |
| Cuadrado verde tapado >80% | detectar marcador verde aunque este parcialmente cubierto | si el obstaculo tapa mas del 80% del cuadrado verde, el robot lo ignora | Limite identificado |

**Fix aplicado para falso plateado en subida.**
La camara podia confundir la subida con plateado. Se agrego confirmacion por APDS9960 usando un LED de alto brillo en posicion estrategica. El clasificador usa datos RGBC filtrados y reglas de ratio para separar plateado/blanco/rojo antes de caer al matching por minimos cuadrados para otros colores.

Parametros clave extraidos del firmware:
- Integracion APDS: 10 ms.
- Poll de estado: 2 ms.
- Timeout de lectura fresca: 35 ms.
- Filtro: 3 muestras.
- Regla plateado: `C > 1700` y `R/C > 0.240`.
- Regla blanco: `C > 1500` y `R/C <= 0.235`.

**Evidencia.**
- Codigo: `software/teensy/firmware/src/main.cpp`, bloque `known_colors`, `classify_color()`, `update_color_nonblocking()`, `get_color_fresh()`.
- Video/foto: recomendado grabar rampa de subida y sube-baja si se usa en PDF/poster.
- Observacion: el fallo de full course esta aislado a busqueda de salida/evacuacion; no a linea ni rescate.

**Conclusion.** La medicion separa claramente lo que funciona de lo que queda por mejorar. Linea, rescate, pickup/deposito y subida mejoraron con la fusion camara + APDS. El mayor bloqueo real para cerrar full course es la navegacion de salida de rescate/evacuacion. Mecanicamente, el sube-baja es aceptable con 9/10 y recuperacion despues del golpe; la rampa lateral sigue siendo un caso debil con 0/10. El caso de marcador verde tapado >80% se considera limite fisico/visual: si el marcador queda casi oculto, la vision no tiene suficiente informacion.

**Accion.**
- Prioridad tecnica antes de competir: corregir busqueda de salida de rescate/evacuacion.
- Si hay tiempo: repetir rampas laterales despues de ajustar velocidad, centro de masa o estrategia de enfoque.
- En el TDP, reportar esta prueba como evaluacion honesta de modulos y como evidencia del fix APDS+LED para falso plateado.

---

### T-007 - 2026-05-24 - `[ELEC]` Rail voltage and servo rail design check

**Tester:** Benjamin Villagran / Codex documentation check  
**Robot rev:** rev-current  
**Pista / banco:** power-tree documentation, component specifications and rail voltage measurement  
**Issue/PR relacionado:** evidencia final para TDP 2026

**Objetivo.** Documentar la arquitectura real de alimentacion y las mediciones de rail para que quede claro que los picos de corriente de los servos no cargan directamente el rail de la Raspberry Pi o la Teensy.

**Setup.**
- Servo rail: MP1584 medido a 6.1 V.
- Carga del MP1584: cinco servos DFRobot SER0056.
- Rail de computo/control: Raspberry Pi y Teensy alimentadas desde otro regulador, XL4016 medido a 5.0 V.
- Capacitor grande dedicado en rail de servos: no instalado.

**Resultado.**

| Metrica | Valor | Fuente / calculo | OK |
|---|---:|---|---|
| Servo rail medido | 6.1 V | medicion reportada por el equipo | PASS |
| Rail computo/control medido | 5.0 V | medicion reportada por el equipo | PASS |
| Regulador dedicado a servos | MP1584 | power tree del robot | PASS |
| Regulador compute/control | XL4016 a 5 V | power tree del robot | PASS |
| Corriente sin carga, 5 servos | 0.60 A | 5 x 0.12 A max no-load SER0056 a 6 V | DERIVED |
| Potencia sin carga, 5 servos | 3.66 W | 6.1 V x 0.60 A | DERIVED |
| Corriente stall teorica, 5 servos | 4.00 A | 5 x 0.80 A stall SER0056 a 6 V; limite conservador, no secuencia normal | DERIVED |
| Potencia stall teorica, 5 servos | 24.4 W | 6.1 V x 4.00 A; limite conservador, no secuencia normal | DERIVED |
| MP1584 continuo | 3 A | spec del modulo MP1584 | PASS |
| MP1584 pico | 4 A | spec del modulo MP1584 | PASS |
| Maximo grupo normal de comandos en pickup/deposito | 1-2 servos del mecanismo | `open()`/`close()` mueven los dos dedos; fases como sort/lift pueden combinar dos servos; no se observa una fase normal con los 5 servos comandados juntos | PASS |
| Boot critico | sensores y firmware llegan al flujo de arranque sin bloqueo en las pruebas finales | startup + T-008 | PASS |
| UART RPi <-> Teensy | bytes de estado y transicion observados en corrida integrada (`0xF9`, `0xF8`, `0xF7`) | service logs + T-002/T-008 | PASS |
| Conectores / PCB | inspeccion de servicio y corrida final sin resets ni desconexiones observadas | revision del robot + T-008 | PASS |
| Switch / stop seguro | comportamiento de espera/stop documentado en firmware y protocolo | `main.cpp` + startup flow | PASS |

**Evidencia.**
- BOM/specs: `hardware/electronics/PCB_Main/COMPONENT_SPECS_VERIFIED.md`.
- DFRobot SER0056: 4.8-6 V, no-load <=120 mA a 6 V, stall <=800 mA a 6 V, embrague mecanico protector y apagado por bloqueo despues de 5 s.
- MP1584: salida ajustable, 3 A continuo, 4 A pico.
- Observacion del equipo: MP1584 alimenta solo los 5 servos; Raspberry Pi y Teensy usan XL4016 separado medido a 5.0 V.
- Codigo: `claw.cpp` define `open()`/`close()` sobre los dos dedos, `lift()` sobre un servo, `sortLeft()`/`sortRight()` sobre un servo y `depositLeft()`/`depositRight()`/`depositCenter()` sobre un servo. `main.cpp` secuencia pickup/deposito con delays entre pasos; no hay una fase normal que mande los cinco servos juntos.
- Mini-log electronico final: boot OK, UART OK, conectores OK, rail de servos OK, rail de computo/control OK y switch/stop OK durante la evidencia integrada.

**Conclusion.** La arquitectura separa correctamente los servos del rail de computo/control. Las mediciones reportadas son 6.1 V para el rail de servos y 5.0 V para el rail de Raspberry Pi/Teensy. El MP1584 queda dentro de rango para movimiento secuenciado normal. El caso de cinco servos bloqueados simultaneamente exige aproximadamente 4.0 A, igualando el pico del MP1584 y superando su corriente continua de 3 A, pero esa condicion no aparece como fase normal del codigo: pickup/deposito mueve grupos de 1-2 servos y deja el escenario de cinco servos en stall como limite conservador de diseno. La mitigacion real es el rail separado, la secuencia por pasos, el embrague mecanico del SER0056 y la proteccion interna despues de 5 s de bloqueo. Como no hay capacitor grande dedicado en el rail de servos, la medicion fisica de caida de tension durante pickup sigue siendo recomendable si queda tiempo.

**Accion.**
- Para evidencia maxima, repetir medicion con multimetro durante pickup normal y durante la peor secuencia segura, para registrar caida minima del rail de servos.
- Si aparecen resets o vibracion de servos, agregar capacitor de bulk cerca de los conectores de servo.

---

### T-008 - 2026-06-07 - `[SW][PERF]` Full-course evacuation exit validation on video

**Tester:** Equipo IITA  
**Robot rev:** rev-current  
**Pista / banco:** pista completa con linea, zona de rescate, depositos y salida  
**Issue/PR relacionado:** re-test de la limitacion registrada en T-006 y roadmap de salida/evacuacion

**Objetivo.** Validar que la correccion de busqueda de salida/evacuacion permite completar una corrida grabada que incluya linea, rescate, deposito y salida de la zona de rescate.

**Setup.**
- Vision: modelo TFLite final desplegado en Raspberry Pi de IITA.
- Preprocesamiento: anti-flash + AGCWD en modo rescate.
- Control: Raspberry Pi + Teensy sincronizados por UART.
- Mecanismo: pickup, almacenamiento, deposito y finales de carrera FCL/FCR operativos.
- Evidencia: video completo registrado por el equipo.

**Procedimiento.**
1. Ejecutar una corrida completa desde linea hasta zona de rescate.
2. Confirmar busqueda, pickup y deposito de victimas.
3. Ejecutar la rutina de salida de evacuacion.
4. Verificar que el robot abandona la zona de rescate y vuelve al flujo esperado.
5. Registrar el resultado como re-test del bloqueo anterior `0/5` de T-006.

**Resultado.**

| Metrica | Esperado | Obtenido | OK |
|---|---|---|---|
| Corrida completa grabada | linea + rescate + deposito + salida | video completo conseguido por el equipo | PASS |
| Salida de zona de rescate | abandonar evacuacion despues de depositar | el robot sale de la zona de rescate en la corrida grabada | PASS |
| Limitacion T-006 | corregir bloqueo de busqueda de salida | el `0/5` anterior queda como fallo aislado previo a la correccion | PASS |

**Evidencia.**
- Video: corrida completa registrada por el equipo.
- Log: recomendado guardar `journalctl` o salida serial si se repite el test.
- TDP: actualizar Tabla 10 y conclusion para indicar que la salida ya fue validada en una corrida completa.

**Conclusion.** La rutina de salida/evacuacion, que era el principal bloqueo del full course en T-006, fue validada en una corrida completa grabada. Esta evidencia permite reportar que el robot ya completo una secuencia integrada de linea, rescate, deposito y salida, en lugar de dejar la salida como una limitacion abierta.

**Accion.**
- Conservar el video como evidencia para el TDP, poster o entrevista tecnica.
- Si queda tiempo, repetir el full course 3-5 veces para convertir la evidencia de video en una tasa estadistica.

---

Bitacora inicializada para resolver el bloqueo de evidencia de TDP identificado en #93, #98 y `project/backlog/tdp-audit-bugs-prioritarios.md`.
