# Análisis fresco 2026-05-18 — Bugs de correctitud y Oportunidades de mejora

**Branch/commit:** `feature/initialize-testing-log` @ `5a868ea`
**Método:** 4 auditores independientes con mente fresca, por dominio de competencia (línea/verde · evacuación · percepción · control). Lente: **correctitud lógica + competitividad** (NO resiliencia — eso está en #108–#119).
**Pedido del director:** dos entregables separados — oportunidades de mejora / bugs a corregir.

---

## 🔴 BUGS A CORREGIR (priorizados por impacto en puntaje)

### B1 — PID de motores invertido *(el más profundo)*
- `software/teensy/firmware/lib/drivebase/drivebase.cpp:50` — `analogWrite(_pwmPin, (int)(255 - _pwmVal))` con PID en modo **DIRECT**. El integrador corrige en sentido contrario al actuador: error positivo → `_pwmVal` sube → `255 - _pwmVal` baja → motor desacelera. El control queda **siempre saturado** (tope o cero); la velocidad programada de rueda no se respeta.
- **Efecto:** afecta todo — seguimiento de línea errático, giros imprecisos, distancias mal. **Confianza alta.**
- **Fix conceptual:** `analogWrite(_pwmPin, (int)_pwmVal)` o pasar el PID a REVERSE. **Delicado — banco obligatorio** (hoy "anda" porque el saturado entrega PWM máximo; cambiarlo a ciegas puede empeorar).

### B2 — `silver_mask` calculada en BGR con rangos HSV *(quick-win, 1 línea)*
- `software/raspberry/final_rpi/Main.py:750` — `cv2.inRange(frame_resized, lower_silver_hsv, upper_silver_hsv)` sobre BGR. Bug activo **cada frame**. La línea plateada es prácticamente indetectable.
- **Efecto:** el robot puede **no entrar nunca a modo rescate** → 0 pts en la zona que más puntúa.
- **Fix:** usar `hsv_frame` (ya existe en scope, línea 745): `cv2.inRange(hsv_frame, lower_silver_hsv, upper_silver_hsv)`.

### B3 — Mapeo de clases YOLO invertido (negro↔plateado) *(quick-win, 1 línea)*
- `Main.py:624-631` — `cls==0 → ball_type="silver"`, `cls==1 → "black"`, pero `CLASS_NAMES=['negro','plateado',...]` (0=negro, 1=plateado). Invertido.
- **Efecto:** la pinza clasifica todas las víctimas igual sin importar color → imposible separar vivos/muertos → hasta −75 pts de depósito.
- **Fix:** intercambiar: `cls==0→"black"`, `cls==1→"silver"`.

### B4 — `leer_yaw()` no actualiza la global `yaw` *(confirmado por 3 auditores)*
- `main.cpp:673` — `leer_yaw();` sin asignar el retorno; la global `yaw` (línea 608) queda 0 siempre. `avance_recto()` calcula `angle_error` contra 0 → la corrección IMU es letra muerta.
- **Efecto:** el robot deriva en ángulo dentro de la zona de rescate (trayectorias en S, choca paredes). **Confianza muy alta** (3 confirmaciones independientes).
- **Fix:** `yaw = leer_yaw();` o que `leer_yaw()` asigne a la global.

### B5 — Velocidad sube a 55 en curva (lógica invertida)
- `main.cpp:1066-1069` — `if (steer<-0.7 || steer>0.7) robot.steer(55,...)`: en curva cerrada **acelera** en vez de frenar.
- **Efecto:** sale de pista en toda curva cerrada → LoP repetido. Causa más probable de salidas.
- **Fix:** invertir — alta velocidad con `abs(steer)<0.3`, reducir con `abs(steer)>0.7`.

### B6 — Salida anticipada del cuarto (`veces_deposit==2` sin verificar pelotas)
- `main.cpp:1222` — el trigger de salida no chequea `ball_counter`. Una falsa detección de esquina dispara la salida con 0 víctimas recogidas.
- **Efecto:** abandona el cuarto sin puntuar — pierde todo el puntaje de rescate.
- **Fix:** condicionar a `ball_counter >= N` además de `veces_deposit`.

### B7 — Formato del tensor TFLite sin verificar (NMS) *(verificar YA, 10 min)*
- `Main.py:480-489` — itera `out` asumiendo `[N,6]` con NMS interno, pero `metadata.yaml` dice `end2end:false`. Si el TFLite no tiene NMS, la salida es transpuesta `[6+nc, 8400]` → coords y clases basura.
- **Efecto:** TODA la detección de víctimas podría estar mal. Riesgo sistémico.
- **Fix:** imprimir `out.shape` en el warmup; si no es `(N,6)` aplicar NMS / transponer. Assert de shape.

### B8 — `runAngle(180)` ignora el signo del error
- `main.cpp` rama `angle==180` — siempre `robot.steer(speed,dir,+1)` sin elegir sentido por error. Con `initialAngle` en mitad superior recorre la dirección larga (≈360°−180° extra) o termina mal.
- **Efecto:** falla el giro de doble-verde (acción frecuente).
- **Fix:** `robot.steer(speed,dir,(error>0)?1:-1)`.

### B9 — Rango de rojo HSV sin wrap-around de matiz
- `Main.py:74-75` — `H∈[1,7]`; el rojo en HSV ocupa `[0-10]` ∪ `[170-180]`. Bajo luz fría de estadio el rojo cae fuera.
- **Efecto:** `green_state=10` (retorno) casi nunca dispara → pierde la fase de retorno.
- **Fix:** dos `cv2.inRange` (`[0-10]` y `[170-180]`) combinados con `bitwise_or`.

### B10 — Constante encoder `25 pulsos/cm` sin calibrar + ISR en CHANGE (×2)
- `main.cpp:537` — `encoder = 25 * Distance` opaca, sin origen documentado; ISR en `CHANGE` da 2 pulsos/ranura. Si la constante no se calibró con CHANGE activo, `runDistance` está sistemáticamente 2× mal.
- **Efecto:** avances imprecisos → falla recolección/posición en rescate.
- **Fix:** documentar/calibrar empíricamente (`PULSES_PER_CM` medida con 1 m real).

### Bugs medios (no ameritan issue individual — backlog agrupado)
- **B-E04** salida del cuarto: ambas ramas del if/else giran `-90` (la 2ª debería `+90`) — `main.cpp:1254-1265`.
- **B-C05** histéresis de dirección invierte `_dir` al arrancar (`_pwmVal<10`) — `drivebase.cpp:44-47`.
- **B-L06** `case 14` no ejecuta el giro si `green_state` cambió tras `serialEvent5()` — `main.cpp:1115`.
- **B-V03** verde en LAB con rango L demasiado restrictivo (pierde verde en sombra/LED) — `Main.py:70-71`.
- **B-C09** secuencia de pinza plateada sin delay entre `lower()` y `sortLeft()` (colisión servos) — `main.cpp:1163`.
- **B-V04** `cls` por `round()` en vez de `argmax` (depende de B7) — `Main.py:486`.
- **B-E06** `ball_counter` global inicializado en 2 — `main.cpp:83`.
- **B-V06** `anti_flash_preprocess` reasigna `s` sin modificar (no-op confuso) — `Main.py:235`.

---

## 🟢 OPORTUNIDADES DE MEJORA (priorizadas por puntaje)

**Impacto ALTO**
- **Calibración de color in-situ para Songdo** — rangos hoy hardcoded de Salta; luz LED de estadio ≠ Salta. Extender `calibration.py` → JSON cargable. *El mayor riesgo de rendimiento en Incheon.*
- **Barrido sistemático del cuarto de evacuación** — hoy gira a la derecha esperando que aparezcan víctimas. Patrón serpentina/espiral con TOF. Vale 40–60 pts (encontrar las 3).
- **Confirmación multi-frame de esquina viva/muerta** — hoy 1 frame decide. Hasta 75 pts (evita depósito en lado equivocado).
- **Estrategia de salida del cuarto** — hoy comentada → el robot queda atrapado tras depositar.
- **PID real (hoy kp=0, solo integrador) + rampa de aceleración** — respuesta lenta, patinaje en arranque, error de encoder.
- **Recuperación activa de línea perdida** — hoy ángulo fijo a 0 sin búsqueda; gaps/speedbumps son donde más se pierde.
- **Exposición/WB de cámara fijos** + `silver_line` con confirmación multi-frame (evita entrada prematura a rescate por reflejo).

**Impacto MEDIO**
- Speed scheduling curva/recta (hoy 40 fijo). Esquiva de obstáculo por sensor (hoy `random(1,3)`). Frenar en bajada de rampa (hoy solo sube en subida). `avance_recto()` como piloto en gaps (hoy nunca se usa en línea). Memoria de víctimas ya recogidas. Depósito con confirmación de orientación. `runAngle` con control P en vez de bang-bang. Unificar la doble FSM de pinza. NMS explícito post-inferencia. `choose_stable_target` ponderando score.

---

## Lente de coach

- **Quick-wins de oro (1 línea c/u, impacto enorme, bajo riesgo):** B2, B3, B4, B9. Una tarde, desbloquean rescate + retorno. **Máxima prioridad.** Track A/B push libre.
- **Críticos grandes:** B5, B6, B8, B10 — fix acotado pero requieren banco. B7 — verificación de 10 min que puede invalidar medio pipeline (hacer YA).
- **Grande y delicado, NO quick-win:** B1 (PID invertido). El hallazgo más profundo, pero banco intensivo obligatorio — cambiarlo a ciegas puede empeorar.
- **Régimen:** Track A (firmware/control: B1,B4,B5,B6,B8,B10) push libre ≤2026-05-26. Track B (visión: B2,B3,B7,B9) push libre ≤2026-06-11. No duplica resiliencia #108–#119; es eje de correctitud, complementario.

---

## Apéndice — trazabilidad por auditor
- **Línea/verde** (O-L*, B-L*): O-L01..08, B-L01..07. Top: B-L01 (vel 55 curva)→B5, B-L03 (cx_black)→ya #110.
- **Evacuación** (O-E*, B-E*): O-E01..07, B-E01..06. Top: B-E01 (clases YOLO)→B3, B-E03 (salida anticipada)→B6.
- **Percepción** (O-V*, B-V*): O-V01..08, B-V01..06. Top: B-V01 (silver BGR)→B2, B-V05 (rojo wrap)→B9, B-V02 (NMS)→B7.
- **Control** (O-C*, B-C*): O-C01..08, B-C01..09. Top: B-C03 (PID invertido)→B1, B-C06 (runAngle 180)→B8, B-C01/O-C04 (encoder)→B10. Convención confirmada: `rotation>0`=izquierda, `<0`=derecha (drivebase.cpp:115-154).

*Auditoría asistida por Claude Code (orquestador rcj-rescue-reviewer replicado + 4 subagentes) bajo supervisión de @gviollaz. Consolidado trazable; reportes completos en el log de la sesión.*
