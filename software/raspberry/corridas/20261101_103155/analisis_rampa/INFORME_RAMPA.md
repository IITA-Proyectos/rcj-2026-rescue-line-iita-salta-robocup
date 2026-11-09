# Subidas: aislamiento de recta -> cresta

Se compararon las cuatro pasadas senaladas por el usuario (00:40,00:57,01:11,01:34), sus entradas y salidas, y las otras cinco ventanas de SUBE del mismo video. No se modifico software. Las mediciones proceden del video/crudo y de las ordenes de Raspberry; no hay yaw/RPM de Teensy para separar cualquier asimetria mecanica residual.

## Hallazgo comprobado

La entrada recta funciona en las cuatro: rampa-recta permanece 48,47,46 y45 cuadros, con correcciones pequenas, aproximadamente dentro de +/-8,4. El problema comun aparece al acercarse a la cresta: deja de cumplirse el criterio de forma de recta y el programa vuelve a rampa-linea, que usa el centroide atan2. Esa transicion no tiene histeresis: un solo cuadro que falla pone el contador de recta en cero.

La causa inicial NO es que la cinta se vuelva demasiado corta en esos cuatro cuadros: su alto medido aun es58 filas. Falla el desvio maximo permitido de1 pixel, mientras la pendiente y el desplazamiento cercano siguen pequenos. La distorsion de la imagen al aparecer el plano superior/reflejos altera la forma de la componente conectada. El recorte de paisaje todavia devuelve60, por lo que no aparta esa informacion del control. Es una falla de seleccion de modo comprobada; el video no prueba por si solo la contribucion de traccion o carga de ruedas.

| Pasada indicada | Ultimo cuadro recta | Primer fallback | Desvio medido al abandonar recta | Rango posterior de rampa-linea |
|---|---:|---:|---:|---|
| 00:40 | 837 | 838,00:41,85 | 1,574 px | -60,8 a +74,7 |
| 00:57 | 1121 | 1122,00:56,05 | 1,576 px | -62,4 a +88,0 |
| 01:11 | 1424 | 1425,01:11,20 | 1,687 px | -53,0 a +87,4 |
| 01:34 | 1832 | 1833,01:31,60 | 1,055 px | -84,4 a +67,5 |

Los rangos cubren la ventana SUBE de cada pasada y no son un angulo fisico de yaw. El umbral excedido dispara la vuelta al centroide; los giros grandes aparecen en los cuadros posteriores, no necesariamente en ese primer cuadro exacto.

En la segunda pasada hay120 cuadros rampa-linea con magnitud>=30; en la primera20 y en la tercera35 considerando todo SUBE. Se ve la camara oscilar mientras el registro alterna ordenes fuertes. La cuarta termina atravesando la cresta, como indica el usuario, pero no es un control perfectamente recto: tambien tiene41 cuadros rampa-linea con magnitud>=30. La proteccion de cresta/centrado aparece antes respecto de la perdida de modo recta: 23 cuadros despues en la cuarta, frente a38/107/37 en las primeras tres. Una vez que entra ese modo, reduce o anula la correccion; eso explica una diferencia de control visible, sin probar una causa mecanica unica de su exito.

## Contraste con las que suben mejor

Se encontraron nueve ventanas con rampa=1. Las subidas iniciadas en00:29,30 y05:43,55 mantienen recta durante solo7 y8 cuadros, y pasan pronto al modo de cresta. Son controles utiles para no ampliar innecesariamente la modificacion. Las otras ventanas, incluidas01:20,05:53,85 y06:10,55, repiten una fase larga de recta (45–50 cuadros) seguida de oscilacion en rampa-linea.

No se debe interpretar el numero de cuadros de recta como geometria universal: depende de la frecuencia y de la aproximacion. El aislamiento debe combinar historia de recta confirmada, estado SUBE vigente y la geometria cercana, no un tiempo fijo aplicado a todas las rampas.

## Correccion acotada propuesta

- Conservar la entrada rampa-recta y los modos rampa-centra/rampa-cresta-recto que ya actuan; no alterar plano normal, bajada, GAP, verdes o recuperacion.
- Solo despues de una recta estable durante SUBE, crear una transicion explicita hacia la cresta. No volver de inmediato al centroide de toda la componente por un desvio de forma aislado de1–2 px.
- Mientras la cinta cercana siga siendo observable, usar posicion y orientacion de la banda cercana con correccion limitada, en lugar de los angulos de60–88 del centroide cuando el plano superior/reflejos empieza a contaminar la forma. Evaluar continuidad e histeresis para entrar/salir; no aumentar globalmente el umbral de recta.
- Si desaparece la cinta en la cresta, conservar la proteccion recta ya existente dentro de sus limites. No mandar cero durante toda la subida: con una entrada desplazada eso impediria corregir.
- Antes de instalar, reproducir las nueve subidas y las grabaciones anteriores: comprobar que los modos recta/cresta ya correctos conservan sus ordenes y que solo cambia el fallback de transicion. El exito fisico debe verificarse despues: el video antiguo no contiene la trayectoria que producira una orden nueva.

## Evidencias

- comparacion_4_subidas.jpg: cuatro filas, ultimo recta, perdida del modo y ordenes posteriores.
- intento1_1.jpg ... intento4_2.jpg: secuencias de las cuatro pasadas.
- otros5.jpg,otros6.jpg,otros7.jpg: otras tres repeticiones del patron.
- umbral_salida_recta.csv: forma medida de los cuadros que abandonan recta.
- todas_las_9_subidas.csv: inventario completo de SUBE del video.

La propuesta queda separada del cierre de recuperaciones: no corresponde intentar arreglar la cresta con otro parche del codo.
