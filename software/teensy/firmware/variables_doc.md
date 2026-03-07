# Documentación de Variables y Estados - Firmware Teensy

## Variables Globales

### Variables de Estado General
- `String color_detected`: Color detectado por el sensor de color. Valores posibles: "Rojo", "Negro", "Verde", "Desconocido". No debe ser vacío.
- `unsigned long tiemporescate`: Timestamp del inicio de la rutina de rescate. Usado para timeouts.
- `static unsigned long lastTurn`: Timestamp del último giro. Persiste entre iteraciones. No debe ser modificado manualmente.
- `const unsigned long turnCooldown = 600`: Tiempo mínimo entre giros en ms. Solo lectura.
- `int counter`: Contador genérico para lógica de steering. Valores: 0-∞, reset a 0 cuando se usa.
- `int laststeer`: Valor anterior de steer. Valores: -1.0 a 1.0.
- `int serial5state`: Estado del protocolo serial con Raspberry. Valores: 0 (speed), 1 (steer), 2 (task), 3 (line_middle). No debe ser >3.
- `double speed`: Velocidad del robot. Valores: 0-100. Fuera de rango causa comportamiento impredecible.
- `double steer`: Dirección del robot. Valores: -1.0 (izquierda) a 1.0 (derecha). Fuera de rango limita automáticamente.
- `int green_state`: Estado de cuadrados verdes detectados. Valores: 0 (ninguno), 1 (izquierda), 2 (derecha), 3 (doble), 6 (pelota negra), 7 (pelota plateada), 8 (rojo), 9 (verde), 14-17 (otros). No debe ser negativo.
- `int silver_line`: Indicador de línea plateada. Valores: 0 (no), 1 (sí).
- `int servo`: Variable no usada actualmente. Reservada para futuro.
- `int action`: Acción actual a ejecutar. Valores: 1-14 (ver switch en loop). 7 por defecto (linetrack).
- `bool taskDone`: Indica si la tarea actual terminó. Valores: true/false. Reset a true después de completar.
- `int angle0`: Ángulo inicial del IMU. Valores: 0-360 grados.
- `bool startUp`: Indica si el robot inició. Valores: true/false. Solo true después de setup inicial.
- `float frontUSReading`: Lectura del ultrasonido frontal. Valores: 0-∞ cm.
- `int RanNumber`: Número aleatorio para decisiones. Valores: 1-3.
- `String rutina`: Rutina actual. Valores: "linea", "rescate". No debe ser vacío.
- `bool first_rescate`: Primera vez en rescate. Valores: true/false.
- `String wall`: Pared detectada. Valores: "right", "left".
- `bool esquinas_negro[3]`: Esquinas con negro detectado. Índices 0-2, valores true/false.
- `bool final_rescate`: Final del rescate. Valores: true/false.
- `String lado_plateado`: Lado de la pelota plateada. Valores: "izquierda", "derecha", "medio".
- `bool lectura`: Flag de lectura. Valores: true/false.
- `int cccounter`: Contador genérico. Valores: 0-∞.
- `int leftLidarReading, rightLidarReading`: Lecturas de LIDAR. Valores: 0-∞ mm.
- `int distance_left_tof, distance_right_tof`: Distancias TOF. Valores: 0-∞ mm.
- `float angulo_rescate`: Ángulo de rescate. Valores: 0-360 grados.
- `float centrar`: Ángulo para centrar. Valores: 0-360 grados.
- `String pared`: Pared actual. Valores: "left", "right".
- `bool alineado`: Si el robot está alineado. Valores: true/false.
- `bool depositando`: Si está depositando. Valores: true/false.
- `int veces_deposit`: Veces depositado. Valores: 0-2.
- `int ball_counter`: Pelotas recolectadas. Valores: 0-∞.

### Variables de la Máquina de Estados de Rescate
- `RescateState rescateState`: Estado actual de rescate. Valores: RESCATE_IDLE (0), RESCATE_NEGRA_STEP1-8, RESCATE_PLATEADA_STEP1-8. No debe ser negativo.
- `unsigned long rescateLastTime`: Timestamp del último paso. Usado para delays no-bloqueantes.
- `const unsigned long RESCATE_STEP_DELAY = 1000`: Delay entre pasos en ms. Solo lectura.

## Estados de la Máquina de Rescate

### Estados para Pelota Negra (RESCATE_NEGRA_*)
- **RESCATE_NEGRA_STEP1**: Baja la garra
- **RESCATE_NEGRA_STEP2**: Posiciona depósito al centro
- **RESCATE_NEGRA_STEP3**: Clasifica a la derecha
- **RESCATE_NEGRA_STEP4**: Avanza 8 unidades de distancia
- **RESCATE_NEGRA_STEP5**: Cierra la garra y suena buzzer
- **RESCATE_NEGRA_STEP6**: Levanta la garra
- **RESCATE_NEGRA_STEP7**: Abre la garra
- **RESCATE_NEGRA_STEP8**: Retrocede un poco y incrementa contador

### Estados para Pelota Plateada (RESCATE_PLATEADA_*)
- **RESCATE_PLATEADA_STEP1**: Baja la garra
- **RESCATE_PLATEADA_STEP2**: Clasifica a la izquierda
- **RESCATE_PLATEADA_STEP3**: Posiciona depósito al centro
- **RESCATE_PLATEADA_STEP4**: Avanza 8 unidades de distancia
- **RESCATE_PLATEADA_STEP5**: Cierra la garra y suena buzzer
- **RESCATE_PLATEADA_STEP6**: Levanta la garra
- **RESCATE_PLATEADA_STEP7**: Abre la garra
- **RESCATE_PLATEADA_STEP8**: Retrocede un poco y incrementa contador

## Notas de Seguridad
- No modificar variables marcadas como "Solo lectura" o "No debe ser...".
- Los valores fuera de rango pueden causar comportamientos impredecibles o crashes.
- Las máquinas de estados deben resetearse apropiadamente para evitar estados inválidos.