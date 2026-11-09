# Mi prueba independiente: silver mask como referencia

Revisión terminada el 2 de noviembre de 2026. Este directorio es independiente de los cambios de Claude. No se modificó main.py, la Teensy, el servicio ni archivos de despliegue.

## Qué está implementado

`silver_mask.py` recibe el cuadro BGR original de 160×120 y produce:

1. Máscara de color calculada en **RGB**: píxeles aproximadamente neutros y de luminosidad intermedia. El intervalo es deliberadamente amplio para incluir metal oscuro y reflejos.
2. Candidato de banda limitado por dos bordes largos, con estrechamiento admitido por perspectiva. Se exige contraste relativo con el entorno superior e inferior, extensión suficiente y predominio de píxeles compatibles con el color. La segunda versión rechaza bandas dominadas por negro.
3. `silver_mask`: intersección del color con la banda geométrica seleccionada. No se toma todo el piso gris como plateado.
4. Pendiente de imagen, continuidad de la hipótesis y persistencia de tres cuadros. La continuidad utiliza solapamiento de las bandas y diferencia de pendientes.

**No genera órdenes de motor, GS, APDS ni rescate.** Devuelve `centered=None` y `motor_command=None`: no inventa centrado ni convierte la detección en movimiento. Cuando desaparece la geometría, invalida la pendiente; no conserva la última medición como pose actual.

Esta máscara sigue siendo de **posible banda**, no una identificación inequívoca de metal. Los bordes detectados pertenecen al patrón de imagen y pueden corresponder a otro objeto.

## Qué se probó de verdad

Se reprodujeron **29.395 PNG originales**, sin recurrir a capturas comprimidas del video:

- Corrida 12:49:12: 24.341 cuadros completos.
- Corrida 12:38:04: 5.054 cuadros completos, usada como comprobación adicional después de ajustar las muestras iniciales. Es el mismo mapa/cámara, no una validación independiente de condiciones de competencia.

En las ocho ventanas de aproximación del video principal aparece al menos una hipótesis persistente. También aparece en los dos reintentos de la corrida anterior. **No significa que detecte la banda en cada cuadro, ni acredita que un robot controlado por este módulo complete esas entradas.** Las ventanas incluyen cuadros sin banda utilizable, contexto y maniobras posteriores.

| Ventana principal | Cuadros revisados | Con candidato | Con persistencia |
|---|---:|---:|---:|
| P01 | 92 | 29 | 19 |
| P02 | 158 | 25 | 19 |
| P03 | 157 | 32 | 21 |
| P04 | 169 | 27 | 8 |
| P05 | 182 | 26 | 9 |
| P06 | 168 | 21 | 14 |
| P07 | 173 | 17 | 7 |
| P08 | 228 | 29 | 19 |

P01–P08 corresponden a 04:10–04:15, 07:35–07:43, 07:43–07:51, 12:42–12:50, 12:56–13:05, 13:13–13:21, 13:21–13:30 y 17:27–17:38 del video principal.

### Contraejemplos

En los 23.014 cuadros del principal que quedan fuera de esas ventanas, la segunda versión todavía produce **297 candidatos**, de los cuales **33 cuadros pasan la persistencia**, distribuidos en 16 grupos. Se revisó visualmente un representante de cada grupo: son bordes de rampa, juntas/bordes de panel y reflejos sobre otros límites del mapa. La figura `falsos_v2.jpg` los muestra. Por tanto, **no está listo como detector autónomo de plateado**.

La primera versión daba 66 cuadros persistentes fuera de ventanas; el rechazo de bandas dominadas por negro los redujo a 33, manteniendo los mismos 126 cuadros persistentes dentro de P01–P08. Eso mide una mejora en esta grabación, no una tasa universal de falsos positivos.

En la corrida adicional hay 42 candidatos fuera de las dos ventanas marcadas y **ninguno** alcanza persistencia. Las dos aproximaciones conservan respectivamente 19 y 10 cuadros persistentes. No se convierte ese cero observado en promesa de cero falsos con sol o en otro mapa.

### Pruebas de comportamiento del módulo

Pasan cuatro comprobaciones: un reflejo redondo aislado no forma banda; un codo negro sintético no identifica material; al desaparecer la imagen válida se borra la orientación; una pausa exige confirmar nuevamente. La detección persistente no produce orden de motor ni declara centrado.

## Hallazgo que cambia la integración

Con este prototipo, al exigir **GS0, estado llano y los tres segundos posteriores a una orden GS4 izquierda**, no queda ningún cuadro persistente válido en P01–P08. La banda se detecta antes y durante la aproximación; después del pivote sus dos bordes ya no están suficientemente visibles para este detector.

Esto no prueba que sea imposible seguir un borde con una cámara. Sí demuestra que no se puede instalar este detector tal cual y empezar a usarlo recién al terminar la recuperación. Haría falta adquirir la identidad de la banda antes y seguirla durante el giro, permitiendo observar un único borde cuando el otro sale de imagen, con comprobaciones de continuidad. Ese seguimiento de un borde y su calibración **todavía no están implementados ni verificados**.

No se debe resolver una pérdida de observación extrapolando indefinidamente la pendiente anterior. Una referencia antigua puede quedar desactualizada precisamente porque el robot giró.

## Cómo alinearía con el plateado, según mi criterio

### Orientación: referencia en la banda

La dirección para cruzar es la **normal a la banda** en el plano del piso. No se obtiene siguiendo el centroide de la máscara negra de recuperación.

Usaría los bordes de la banda, con corrección de perspectiva/calibración de cámara, para medir el error de orientación. Los bordes físicos paralelos convergen en la imagen; por eso la pendiente calculada aquí es una medida de imagen, **no grados de yaw**. Una cámara inclinada lateralmente también cambia la referencia. Hay que medir una postura de entrada realmente correcta o calibrar la proyección al piso antes de convertirla en consigna.

Con cámara nivelada y piso plano, una banda que cruza de forma oblicua ofrece un error visual para enderezarse. El objetivo debe ser la orientación de cruce calibrada, no que el centro de la mancha plateada coincida con el centro de la pantalla.

### Posición: falta un punto de entrada

Una banda larga que sale por los bordes de imagen **no permite conocer el centrado lateral usando solo su máscara**. Su centroide se desplaza cuando cambia el recorte y la perspectiva. Dos posiciones laterales distintas pueden producir una banda similar.

Para elegir dónde cruzar, conservaría como referencia el punto donde la cinta original llega a la banda, observado antes del retroceso, y seguiría ese punto o una referencia visual asociada. Ese punto fija el lugar de entrada; los bordes plateados fijan la orientación. No se reelige un objetivo tomando el fragmento negro más grande que aparezca después de la recuperación.

Así no nos centramos con «la línea de recuperación»: el giro se corrige respecto de la banda y el lugar de cruce se refiere a un punto identificado previamente. Si se pierde también la identidad de ese punto, no se declara centrado. El seguimiento de ese punto **es una parte pendiente**, no una capacidad que este prototipo ya tenga.

## Cómo lo incorporaría sin alterar lo que funciona

1. **Ahora: solo offline.** Esta versión ni se importa desde main.py ni se ejecuta en la Raspberry. No cambia órdenes, máscaras del seguidor ni tiempos de su lazo.
2. **Observación futura:** un observador acotado recibe una copia del cuadro y registra máscara/pendiente/confianza. No escribe sobre las máscaras existentes. Debe medirse su carga en la Raspberry: incluso un observador puede alterar el tiempo de respuesta si se añade sin límite de trabajo. El tiempo medido en esta computadora no demuestra rendimiento en la Pi.
3. **Detección anticipada y seguimiento de identidad:** adquirir la banda mientras aún se ven sus bordes; conservar su identidad durante la llegada. No limitar el inicio de la detección al fin de la recuperación, porque la reproducción muestra que sería tarde.
4. **Autoridad separada:** el APDS conserva la confirmación de material. Los candidatos RGB, incluidos los persistentes, no deben por sí solos cancelar un GAP, ordenar un giro ni iniciar rescate. Los episodios laterales izquierdos aportan contexto, pero no convierten cualquier junta en plateado.
5. **Control futuro:** una fase de entrada pendiente en la Teensy espera geometría fresca de banda y punto de cruce válidos antes del avance. Esa fase debe quedar separada de los verdes, los GAPs rectos, las subidas y las recuperaciones normales. No basta modificar solo la Raspberry si la Teensy continúa una rutina automática de entrada.
6. **Pérdida de referencia:** detener/reobservar con una terminación acotada; no interpretar `sin máscara` como `alineado`, ni agregar un giro fijo por defecto.

## Archivos para comparar las dos opiniones

- `silver_mask_ejemplo.jpg`: cámara original, RGB amplio, máscara acotada y banda superpuesta.
- `silver_mask_demo.avi`: dos fragmentos concatenados de la grabación, con máscara y estado geométrico; es una reproducción offline, no una prueba del robot controlado por el detector.
- `falsos_v2.jpg`: los 16 grupos persistentes que aún confunden al detector en el principal.
- `silver_mask.py`: prototipo actual.
- `silver_mask_v1.py`: primera versión, para conservar la comparación.
- `resumen_final.csv` y los dos CSV con sufijo `SILVER-MASK-SHADOW-2`: resultados de todos los cuadros.
- `test_silver_mask.py`: pruebas del borrado de referencias inválidas y ausencia de autoridad de movimiento.

**Mi opinión:** la máscara del plateado es una referencia razonable para orientar el cruce, y esta prueba demuestra que podemos extraerla en esas llegadas. No sirve todavía como detector sin falsos ni permite centrar lateralmente solo por su centroide. Conectarla ahora a los motores, especialmente solo después de la recuperación, sería adelantar una conclusión que los resultados no respaldan.
