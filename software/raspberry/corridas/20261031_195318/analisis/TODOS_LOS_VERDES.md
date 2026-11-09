# Todas las pasadas por verdes — análisis visual y cruce con la Teensy

Corrida `pista_20261031_195318.avi`. No se modificó el robot. Este informe completa y, donde corresponde, precisa los anteriores.

## Alcance y forma de revisión

Se inspeccionaron visualmente las aproximaciones y salidas de las pasadas por marcadores, usando las imágenes originales. Se hizo un barrido cromático amplio de los 7.927 cuadros, independiente del filtro LAB de competencia, para localizar también verdes oscuros. Produjo 61 intervalos candidatos: la inspección visual permite descartar personas, sillas, reflejos azulados del piso y marcas de otros sectores. Se revisaron además cinco láminas de barrido de toda la corrida y secuencias ampliadas antes/durante/después de los marcadores.

Se identifican **21 pasadas por conjuntos de marcadores de la línea seguida**, contando cada repetición como una pasada, no como un marcador físico nuevo:

- 14 maniobras programadas se ejecutan al detectar verde.
- 3 pasadas pierden un verde izquierdo válido por oscuridad/recorte.
- 4 pasadas muestran únicamente un derecho posterior a la franja, correctamente rechazado.

Dos de las tres pasadas con izquierdo perdido también incluyen un derecho posterior que se debe seguir rechazando. En los dobles hay dos cuadrados, pero se cuenta una sola decisión de intersección. Los verdes de baldosas adyacentes y del fondo se documentan aparte.

**Los tiempos de las tablas son del AVI**, calculados por cuadro a 20 FPS. No son el tiempo real de `cuadros.csv`. Ejemplo: cuadro 1135 es 00:56,70 del AVI y 54,594 s del reloj del grabador crudo. El cruce con Teensy usa este último más 50,35 s.

Las muestras de movimiento son del CSV: recepción de ángulo, consignas, RPM, sentido, yaw y giroscopio. El CSV no trae GS recibido; GS enviado sí está en el registro por cuadro de la Pi. La ejecución de las maniobras se verifica por sus intervalos programados y movimiento. No hubo incremento de `drop` dentro de ninguna de las 14 maniobras de verde analizadas, aunque el CSV completo tiene pérdidas en otros momentos.

## Inventario completo de pasadas

“Recaptura” significa que después de la maniobra se ve nuevamente la línea seguida; no equivale a garantizar el resto de la pista. No se atribuye una curva posterior al verde solo porque aparezca unos segundos después.

| Nº | Tiempo AVI / cuadro | Lectura visual del marcador | Decisión y movimiento | Resultado y causa |
|---:|---|---|---|---|
| 1 | 00:12,75–14,15 / 256–284 | Derecho después de la transversal | GS0; sin maniobra de verde | Rechazo correcto. Sigue longitudinal y llega a la curva siguiente. Conservar. |
| 2 | 00:56,20–57,40 / 1125–1149 | Izquierdo válido primero; derecho inválido después | No envía verde. En 1135 acepta solo 35 píxeles | Pierde la instrucción izquierda y sigue longitudinal. Luego hay interrupción/reposicionamiento. El derecho de 1143 se rechaza correctamente; la falla está antes, en luminosidad del izquierdo. |
| 3 | 01:02,75–03,30 / 1256–1267 | Izquierdo válido, oscuro y recortado en el borde | GS0; máximo local registrado de 565 píxeles | Ya llega desplazado por una rama que arrastra el seguimiento durante bajada. No detecta la izquierda y luego sigue avanzando sin línea conectada. Se necesita corregir color y seguimiento previo, por separado. |
| 4 | 01:11,80–12,25 / 1437–1446 | Izquierdo válido | GS1 solo en 1444; avance y giro izquierdo ≈44° | La maniobra se ejecuta aunque solo hubo un cuadro aceptado. Recaptura la rama y continúa. Conservar; no agregar una exigencia ciega de tres GS consecutivos. |
| 5 | 01:18,35–19,40 / 1568–1589 | Derecho posterior a la transversal | GS0 pese a >3.000 píxeles verdes | Rechazo correcto. Cruza de largo por longitudinal y continúa. El verde no es la causa de la curva posterior. |
| 6 | 01:24,55–25,35 / 1692–1708 | Doble válido, entrada oblicua | 1693 GS2; 41 ms después GS3; luego GS1. Se ejecuta giro derecho ≈44° | Falla de compromiso temprano: el simple empieza antes de completar la observación del doble. Después aparecen suelo sin línea y avance recto durante bloqueo. No faltó fuerza para un 180: nunca se ejecutó esa maniobra. |
| 7 | 01:32,00–33,60 / 1841–1873 | Doble válido, entrada oblicua | GS3; giro neto de secuencia ≈181,5° izquierdo | La media vuelta sí ocurre. Después no recaptura la línea y continúa sobre piso blanco hasta interrupción. Falta salida guiada por línea; no corregir agregando grados globalmente. |
| 8 | 01:42,25–43,80 / 2046–2077 | Izquierdo válido | GS1; giro izquierdo ≈43° | Recaptura y continúa por curvas posteriores. No hay evidencia de fallo de este verde. |
| 9 | 02:04,05–05,45 / 2482–2510 | Derecho válido | GS2; giro derecho ≈44° | Durante/saliendo del giro la línea pasa por el borde y el control necesita corrección fuerte; después continúa al siguiente verde. Hay riesgo en la salida fija, no una falta de detección. |
| 10 | 02:07,10–09,35 / 2543–2588 | Derecho válido en aproximación oblicua | GS2; giro derecho ≈44° | La orientación al llegar y al salir es oblicua. La secuencia neta parece ≈41° porque durante el avance anterior gira ≈−3°. El giro propiamente dicho no se queda en 41°. Continúa al siguiente marcador. |
| 11 | 02:12,50–14,60 / 2651–2693 | Derecho válido | GS2; giro derecho ≈44° | Recaptura longitudinal. La recuperación que falla más tarde, en 2793, corresponde a una curva posterior; no a un verde ignorado. |
| 12 | 02:24,35–26,25 / 2888–2926 | Derecho válido tras reposicionamiento | GS2; giro derecho ≈44° | Recaptura la rama, luego aborda otro codo. Separar el resultado del verde de la recuperación posterior. |
| 13 | 04:44,55–46,95 / 5692–5740 | Derecho después de la transversal; repite caso 1 | GS0 | Rechazo correcto; sigue longitudinal y llega a la curva. Es un caso de regresión que se debe conservar. |
| 14 | 05:27,45–29,10 / 6550–6583 | Izquierdo válido oscuro y luego derecho posterior | GS0 en toda la pasada | Repite la falla 2. La alternativa L≥100 reconoce izquierda en 6569; el derecho posterior se debe seguir descartando. El robot conserva la ruta longitudinal y luego intervienen sobre él. |
| 15 | 05:34,50–34,90 / 6691–6699 | Izquierdo válido en bajada | GS1 solo en 6698, con 601 píxeles. Giro izquierdo ≈43° | Reacciona y recaptura después. El rumbo total aparenta −69°, pero ≈−25° ocurren en el avance con muy poco giro de giroscopio: no son 69° físicos de giro programado. |
| 16 | 05:40,95–42,20 / 6820–6845 | Derecho posterior a la transversal; repite caso 5 | GS0 | Rechazo correcto. Sigue por longitudinal hacia el doble siguiente. |
| 17 | 05:47,05–48,50 / 6942–6971 | Doble válido en aproximación oblicua | GS3 primero; después aparece GS1 mientras gira. Se ejecuta una media vuelta ≈182,3° | La Teensy mantiene la maniobra doble. Después vuelve a quedar sin recaptura y avanza por piso blanco. Repite la falla de cierre del doble 7. |
| 18 | 05:55,05–56,60 / 7102–7133 | Izquierdo válido | GS1; cambio yaw durante el giro ≈43,5° | Recaptura la rama y continúa. Hay discrepancia de unos grados con la integración gyro y cambio previo de rumbo; no concluir exceso físico a partir del neto ≈53°. |
| 19 | 06:18,90–20,35 / 7579–7608 | Derecho válido | GS2 intermitente al principio; maniobra derecha ≈44° | Se ejecuta una sola secuencia programada y continúa al siguiente derecho. Las interrupciones breves de GS2 no impidieron el giro. |
| 20 | 06:21,95–24,40 / 7640–7689 | Derecho válido en entrada oblicua | GS2; giro derecho ≈44° | Secuencia neta ≈41°, por ≈−3° de avance previo; mismo patrón que caso 10. Continúa, pero necesita corrección fuerte de seguimiento al salir. |
| 21 | 06:26,10–29,45 / 7723–7790 | Derecho válido | GS2; giro derecho ≈44° | Recaptura. El episodio final GS4 empieza después, en una curva; la grabación se corta durante la recuperación. No hay base para atribuir esa interrupción al verde. |

## Evidencia visual completa

Cada pasada ocupa dos filas de cuatro cuadros: aproximación, detección y evolución posterior. Las láminas incluyen algo de contexto del siguiente sector, por lo que una imagen tardía puede pertenecer a la curva siguiente.

- [Pasadas 1–4](pasadas_verdes_1.jpg): rechazo 00:13, dos izquierdos perdidos y el izquierdo de un cuadro que sí gira.
- [Pasadas 5–8](pasadas_verdes_2.jpg): derecho posterior, doble ejecutado como simple, doble que gira pero no recaptura e izquierdo que funciona.
- [Pasadas 9–12](pasadas_verdes_3.jpg): las cuatro maniobras derechas de la primera vuelta.
- [Verdes ajenos y pasadas 13–15](pasadas_verdes_4.jpg): baldosas cercanas, rechazo correcto y repetición de los izquierdos de bajada.
- [Pasadas 16–18](pasadas_verdes_5.jpg): rechazo correcto, segundo doble que no recaptura e izquierdo que continúa.
- [Pasadas 19–21](pasadas_verdes_6.jpg): últimas tres derechas.

Para la verificación del barrido completo: `catalogo_verdes_1.jpg` a `catalogo_verdes_8.jpg` muestran todos los intervalos cromáticos candidatos, y `barrido_visual_1.jpg` a `barrido_visual_5.jpg` el muestreo de toda la corrida. Los 61 intervalos no son 61 verdes: incluyen reflejos del piso y objetos del fondo.

## Verdes que aparecen pero no pertenecen a la decisión actual

- Al bajar se ven verdes en la baldosa inferior antes de llegar a ellos (por ejemplo alrededor de 1033–1053 y 6474–6490). Son la aproximación lejana a pasadas posteriores, no eventos de giro independientes.
- Durante los codos se ven verdes lejanos en otras baldosas; no están junto a la rama inmediata seguida. No deben disparar un giro solo por aparecer en imagen.
- Alrededor de 4795–5021, especialmente 4935 (04:06,70), se ven marcas verdes impresas grandes en una zona lateral durante una búsqueda GAP y curvas. Visualmente no constituyen los cuadrados izquierdo/derecho de la línea inmediata. El registro mantiene GS18 o seguimiento/recuperación, sin giro de verde: no se encontró una instrucción válida omitida ahí.
- Cuando levantan o reposicionan el robot aparecen personas, objetos y otros sectores de pista; esos cambios no se cuentan como pasadas autónomas nuevas por un marcador.

## Qué aportan ruedas, receptor e IMU

### La detección y la maniobra son problemas distintos

En las pasadas 2, 3 y 14 no sale una instrucción válida de verde desde la Pi. La Teensy sigue recibiendo dirección normal y moviendo las ruedas: un PID distinto no puede recuperar una instrucción que la visión nunca emitió.

En el caso 6 sí sale GS3, pero llega después del primer GS2 y del inicio de la secuencia programada. La rotación observada corresponde a la maniobra simple. Se necesita resolución temporal del tipo de marcador, no aumentar 45° hasta 180° para todas las derechas.

En los casos 7 y 17, la rotación de media vuelta se verifica; sin embargo, las imágenes posteriores no muestran línea recapturada. El problema se repite en el mismo tipo de maniobra: falta validación de la rama al terminar.

### Ángulos medidos por fase

En verdes simples el fuente disponible primero avanza 800 ms y luego gira 45°. Por eso el cambio de rumbo total no es el ángulo del giro. Se separaron ambas fases. En dobles la secuencia es distinta y se informa el neto del intervalo programado.

| Pasada / cuadro | GS inicial | Cambio de yaw total de secuencia | Cambio durante avance inicial | Giro posterior aproximado |
|---|---:|---:|---:|---:|
| 4 / 1444 | 1 | −45,4° | −1,8° | −43,6° |
| 6 / 1693 | 2 | +46,3° | +2,3° | +44,0° |
| 7 / 1853 | 3 | −181,5° | No aplica separar 800 ms | Media vuelta |
| 8 / 2070 | 1 | −44,9° | −1,5° | −43,4° |
| 9 / 2502 | 2 | +45,6° | +1,6° | +44,0° |
| 10 / 2579 | 2 | +41,0° | −2,9° | +43,9° |
| 11 / 2676 | 2 | +44,8° | +1,2° | +43,6° |
| 12 / 2908 | 2 | +43,6° | 0,0° | +43,6° |
| 15 / 6698 | 1 | −68,6° | −25,4° | −43,2° |
| 17 / 6952 | 3 | −182,3° | No aplica separar 800 ms | Media vuelta |
| 18 / 7123 | 1 | −52,8° | −9,3° | −43,5° |
| 19 / 7602 | 2 | +44,5° | +0,5° | +44,0° |
| 20 / 7682 | 2 | +41,2° | −2,8° | +44,0° |
| 21 / 7778 | 2 | +44,7° | +0,3° | +44,4° |

La mayoría concuerda razonablemente con la integración de gyro (con signo opuesto). En 6698 el yaw previo cambia mucho al terminar la pendiente, con gyro integrado de apenas unos 2°; no contarlo como 25° de giro físico adicional. En 7123 también hay discrepancia, por lo que el yaw absoluto no debe usarse solo.

Las medianas de las cuatro ruedas durante las derechas son parecidas (aproximadamente 20–23 RPM en los intervalos completos, que mezclan avance y giro). No se encontró evidencia de una rueda permanentemente detenida que explique todas las fallas. Las muestras y estadísticas están en `verdes_movimientos.csv`. Las medianas no descartan transitorios, patinamiento o errores mecánicos puntuales.

### La salida de 01:02 empieza antes del marcador

La rama lateral influye en el seguimiento con pitch cercano a −31°. En 1234 la Pi manda −48,1°; Teensy recibe −48° y pide RPM 34/5/34/5. Se miden 35/4/32/4: las ruedas responden a esa orden de desvío. Después alterna recto (`bajada-sin-recup`) con corrección contraria fuerte. Aparecen transitorios de ruedas durante esos cambios. La pérdida del verde izquierdo llega después.

Es necesario conservar el seguimiento de la continuación longitudinal frente a una rama lateral durante bajada y mejorar el verde oscuro. Resolver solo uno de los dos no cubre toda la secuencia.

## Por qué se sale: causas apoyadas por las repeticiones

1. **Tres izquierdos perdidos por luminosidad/recorte:** pasadas 2, 3 y 14. La vía adicional L≥100, mismos A/B y misma regla de negro, recupera GS1 en 1135, 1266 y 6569. Mantiene los derechos posteriores rechazados. En las pasadas 2 y 14 el robot conserva inicialmente una línea longitudinal pero elige una ruta distinta de la instruida; no confundirlo con una salida física inmediata de la cinta.
2. **Un doble resuelto demasiado pronto como simple:** pasada 6. Hay evidencia directa de GS2→GS3 en 41 ms y ejecución de 45°, no de 180°.
3. **Dos medias vueltas sin cierre visual:** pasadas 7 y 17. Girar el ángulo nominal no garantiza volver al eje de la rama, especialmente con entrada oblicua y desplazamiento. El avance posterior y el bloqueo de recuperación prolongan el recorrido por suelo blanco.
4. **Seguimiento contaminado por ramas y posición oblicua:** la pasada 3 muestra el desvío anterior al verde. Las derechas 9/10/20 muestran correcciones fuertes y línea en el borde al salir, aunque logran continuar. Es una fragilidad de posición y orientación al retomar seguimiento, no evidencia de que todos los giros estén cortos.
5. **Recuperaciones posteriores que fallan por otro motivo:** no atribuir a los verdes 11, 12 o 21 los codos que aparecen más adelante. Se deben analizar y corregir con el criterio de recaptura de recuperación del informe anterior.

## Resolución propuesta, preservando los casos que sí funcionan

1. Agregar detección de verde oscuro como respaldo del detector actual. Mantener área, A/B, validación geométrica y prioridad de detecciones ya aceptadas. Revisar los 28 cuadros adicionales de replay antes de desplegar.
2. Seguir el mismo marcador en el tiempo para distinguir izquierdo válido → derecho posterior, y simple provisional → doble. Preservar verdes aceptados de un solo cuadro acumulando evidencia previa; no exigir varios GS finales consecutivos.
3. En doble, resolver el tipo antes del compromiso de maniobra. Una vez iniciado, congelar la decisión hasta cerrar el evento.
4. Conservar los ángulos nominales actuales como base. Agregar cierre visual de maniobra: no devolver avance normal hasta recapturar una rama conectada con dirección coherente; si no aparece, detener y buscar de manera acotada. Prioridad en dobles, donde se repite la salida.
5. Corregir por separado el cálculo de seguimiento en la bajada frente a ramas laterales. Mantener la continuación longitudinal si sigue visible y conectada; no apagar globalmente las protecciones de rampa ni retocar el PID como primer paso.
6. Prueba de regresión obligatoria: conservar pasadas 1/5/13/16 rechazadas; recuperar 2/3/14; preservar 4/8/15/18 y las derechas que continúan; resolver el doble 6 y verificar cierre de 7/17. Después comprobar los GAP y codos que ya funcionan.

Una reproducción de imágenes permite verificar la clasificación y las condiciones de cierre, pero no demuestra la trayectoria que generaría una orden nueva. El comportamiento final requiere otra pasada física. Esta revisión no cambió el programa del robot.
