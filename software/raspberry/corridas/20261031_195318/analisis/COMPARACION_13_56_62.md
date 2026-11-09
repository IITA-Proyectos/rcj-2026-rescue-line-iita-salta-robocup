# Comparación específica de 00:13, 00:56–57 y 01:02–03 del AVI

Esta revisión corrige una interpretación incompleta del primer informe: habilitar el verde derecho del cuadro 1143 no es la solución. La secuencia previa contiene un verde izquierdo válido que el filtro de luminosidad pierde. El derecho aparece después del cruce y corresponde conservar su rechazo.

No se modificaron fuentes, parámetros ni servicios del robot.

## Diferencia entre las tres escenas

Los tiempos aquí son del AVI de 20 FPS, no de `cuadros.csv`. La imagen `comparacion_13_56_62.jpg` muestra las tres aproximaciones.

### 00:13 — rechazo correcto que se debe preservar

Al acercarse el robot, el verde derecho está en el lado lejano de la franja transversal: la franja pasa antes que el verde. En el cuadro 277 (00:13,80) hay 2.223 píxeles verdes aceptados por color, pero no hay negro encima de ese marcador en la franja de validación. GS0 es consistente con ignorarlo.

Al reproducir con límite de luminosidad 100 en lugar de 120, el cuadro sigue enviando GS0: negro encima sigue siendo 0%. Toda la ventana de cuadros 250–290 conserva el rechazo.

### 00:56–57 — el izquierdo anterior se pierde por luminosidad

Cuadros 1125–1135: aparece un marcador izquierdo antes de la franja transversal; a la derecha se ve otro en el lado posterior. No son un doble verde válido simultáneo.

Cuadro 1135 (00:56,70):

- La zona verde izquierda entra en el área de detección (filas 80–119).
- Solo 35 píxeles pasan el LAB actual, por debajo de 600.
- Inspección del material verde con una máscara cromática amplia, usada solo para medición: 1.846 píxeles en esa zona; mediana LAB [97,100,128]. 1.811 de esos píxeles incumplen el límite de luminosidad, mayormente por quedar debajo de L=120. La mediana A/B sí cae en el rango existente.
- Con L mínimo 100 y sin cambiar A/B, área mínima ni regla del negro, pasan 804 píxeles y la ocupación negra encima es 80,1%. La reproducción devuelve GS1, izquierda.

Cuadro 1143 (00:57,10):

- El izquierdo ya pasó. El verde que destaca es el derecho posterior a la franja.
- Con los parámetros actuales pasan 1.233 píxeles pero hay 0,85% de negro encima; se rechaza.
- Con L mínimo 100 sigue rechazado (1,5%, lejos del 32%).

Conclusión: corregir la detección del izquierdo en 1135, conservar el rechazo del derecho en 1143. La geometría temporal distingue los lados antes y después de la intersección.

### 01:02–03 — desplazamiento lateral más pérdida de verde oscuro

La salida de línea comienza antes del instante de máxima visibilidad del verde:

1. Cuadros 1220–1234: el robot baja una pendiente cercana a −31°. Una rama transversal hacia la derecha entra en la máscara negra. La orden de seguimiento deriva desde casi cero hasta −48,1°, aunque la continuación longitudinal sigue visible.
2. La Teensy recibe ese comando. Las ruedas cambian sus consignas; no es una orden de verde ni una recuperación.
3. La línea longitudinal queda desplazada hacia la izquierda en imagen. Los cuadros 1246–1250 envían 0° con `bajada-sin-recup`, por lo que el robot avanza durante la pérdida de conexión, protegido por la excepción de bajada.
4. Cuadro 1254: vuelve una corrección fuerte opuesta (+62,2°); la línea sigue cerca del borde izquierdo. La secuencia alterna grandes correcciones con tramos rectos.
5. Cuadro 1266 (01:03,25): el verde izquierdo alcanza la zona baja, con desplazamiento y recorte lateral. Hay 441 píxeles en el filtro actual: no llega a 600. Con L mínimo 100 pasan 763 y la regla de negro da 82%; devuelve GS1.

Conclusión: se superponen un error de seguimiento frente a una rama lateral durante la bajada y un verde que se pierde por color/recorte. Habilitar el verde oscuro rescata la instrucción de giro en la imagen grabada; no resuelve por sí solo la desviación que empezó antes.

## Cruce con receptor y cuatro ruedas

Muestras del CSV tomadas unos 20 ms después del cuadro, con sincronización de +50,35 s. Orden FL/FR/BL/BR. Las RPM son magnitudes; el sentido se registra aparte. Los cambios de sentido durante curvas fuertes son pedidos del control, no prueba de cableado invertido.

| Cuadro / AVI | Orden Pi | Ángulo recibido equivalente | GS Pi | Consignas RPM FL/FR/BL/BR | RPM medidas FL/FR/BL/BR |
|---|---:|---:|---:|---|---|
| 277 / 00:13,80 | +24,4° | +23,9° | 0 | 11/32/11/32 | 15/31/19/30 |
| 1135 / 00:56,70 | +10,8° | +11,0° | 0 | 21/32/21/32 | 25/34/18/32 |
| 1143 / 00:57,10 | −15,1° | −14,9° | 0 | 32/18/32/18 | 30/22/29/19 |
| 1234 / 01:01,65 | −48,1° | −48,0° | 0 | 34/5/34/5 | 35/4/32/4 |
| 1246 / 01:02,25 | 0° | 0° | 0 | 32/32/32/32 | 59/35/29/40 |
| 1254 / 01:02,65 | +62,2° | +61,9° | 0 | 16/36/16/36 | 1/34/12/35 |
| 1266 / 01:03,25 | +2,3° | +2,0° | 0 | 29/32/29/32 | 20/38/24/31 |

El receptor sigue las órdenes de la Pi en estas muestras. La desviación a la derecha ya es solicitada por el seguimiento. En 1234 la respuesta de las cuatro ruedas se aproxima a las consignas. En las inversiones posteriores aparecen diferencias transitorias, especialmente la delantera izquierda: 59 RPM frente a 32, y más tarde 1 frente a 16 en sentido contrario. La pendiente, las inversiones y la inercia pueden contribuir; estas muestras no permiten separar adherencia, dinámica mecánica y regulación. No justifican retocar globalmente el PID antes de corregir las órdenes visuales.

No hay GS recibido en el CSV: GS de la tabla es el enviado por la Pi. Las consignas, dirección y recepción de ángulo sí vienen de la Teensy.

## Prueba sobre los 7.927 cuadros

Se reprodujo el detector con L=120 y con L=100, conservando A/B, área >600, regla de negro >32%, morfología y clasificación originales.

La reproducción base coincide con las 102 detecciones GS1/2/3 grabadas. Las otras 818 diferencias entre GS grabado y salida del detector base son 680 GS4 y 138 GS18: el árbitro final manda esas recuperaciones, mientras el detector de verde devuelve cero.

Como propuesta aditiva, se conservan todas las detecciones actuales y solo se consulta la alternativa oscura cuando no hay un verde ya aceptado. En la comparación estática de cuadros con GS0 añade 28 detecciones:

- Recupera GS1 en 1135 y 1266.
- Mantiene GS0 en 1143 y en todos los cuadros 250–290 (rechazo correcto de 00:13).
- Anticipa GS3 en 1692, antes del GS2 de 1693. Esto ofrece una posible ayuda al doble temprano, pero no sustituye la resolución temporal del tipo de marcador.
- Varias adiciones son cuadros inmediatamente anteriores o posteriores a marcas que el detector actual ya acepta.

El listado íntegro está en `replay_verde_oscuro.csv`. No se afirma que las 28 adiciones sean todas correctas en pista: hay que revisar sus episodios y la prioridad respecto de rampa/recuperación. Mantener decisiones originales en un replay estático no garantiza mantener trayectorias: una orden nueva cambia los cuadros futuros.

## Propuesta concreta y acotada

1. Mantener el detector actual como vía principal. Agregar una vía de verde oscuro con L mínimo 100, mismos A/B, área y validación negra, consultada únicamente cuando la vía principal no da verde. Es un punto de partida demostrado para estos cuadros, no una calibración universal.
2. Asociar componentes a un candidato temporal y al mismo cruce. Conservar el rechazo del verde posterior a la franja. Registrar posición y avance del marcador para no transformar la secuencia izquierdo válido → derecho inválido en doble o en dos instrucciones.
3. No exigir varios GS finales consecutivos: en 1135 y 1266 la oportunidad recuperada es de un cuadro con este umbral. Acumular antes evidencia cromática/geométrica y conservarla hasta resolver el evento.
4. Durante una bajada, cuando entra una rama transversal y la continuación longitudinal sigue conectada, calcular corrección desde esa continuación y su continuidad previa. La rama lateral no debe arrastrar sola el centroide. Aplicar la nueva regla solo en esa geometría; mantener la protección de cresta/bajada en los demás casos.
5. Ante pérdida de conexión durante esa maniobra, evitar la alternancia de avance ciego y correcciones fuertes. Diseñar una transición acotada que tenga en cuenta pendiente, línea visible y velocidad; no eliminar globalmente `BAJADA_SIN_RECUP`.
6. Validar primero sobre esta grabación y después con pasada física: rechazo 00:13 conservado, izquierdo 1135 reconocido, derecho 1143 rechazado, izquierdo 1266 reconocido y continuación longitudinal preservada en 1220–1254. Verificar las curvas y GAP que ya funcionan.

La primera corrección debería ser la vía aditiva de verde oscuro con memoria del marcador. La corrección de seguimiento en la bajada es otra causa y debe probarse por separado, conservando como referencia las órdenes y ruedas de esta tabla.
