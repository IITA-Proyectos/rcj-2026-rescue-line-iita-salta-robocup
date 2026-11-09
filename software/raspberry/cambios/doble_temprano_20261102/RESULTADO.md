# Doble temprano — candidato aislado, no desplegado

**ACTUALIZACION: RECHAZADO PARA INSTALAR.** El usuario confirmó que en la entrada de los cuadros 9970–9972 corresponde izquierda. El candidato cambia 9971 de 1 a 0: es una regresión. La anterior interpretación visual de los 25 cambios como dobles correctos queda revocada. Dos manchas visibles no bastan para adjudicar doble. Incluso la clasificación previa con los colores nuevos produce 3 en 9972, mientras el registro original todavía indica 1. Hace falta separar la regresión por color de la extensión temporal y geométrica. Los resultados numéricos de replay se conservan como evidencia, no como aprobación ni verdad visual. No se instaló.

## Resultado comprobado

Se revisó la secuencia completa de los dos cuadros pendientes, que son parte de la misma entrada al doble: originales 1650 y 1651 de la corrida 20261101_124912. El candidato clasifica ambos como doble sin ampliar el color hacia plateado o negro.

Se procesaron consecutivamente 24.341 cuadros de esa corrida y 17.296 de 20261101_114747, reservada fuera de las muestras de ajuste. Total: 41.637 cuadros. No significa que se hayan inspeccionado visualmente todos: se inspeccionaron los 25 donde cambió la salida, más cuadros de contexto. Los 25 cambios se concentran en pares de verdes visibles. No se observó una modificación sobre un verde visualmente simple entre esos cambios.

Se ejecutaron siete pruebas específicas del candidato y las 17 del calibrador. El código está separado de main y no se instaló en la Raspberry ni se modificó el firmware.

## Causa

En el registro original:

| Cuadro | Tiempo CSV | GS registrado |
| --- | --- | --- |
| 1650 | 67,603 s | 0 |
| 1651 | 67,649 s | 2 (derecha) |
| 1652 | 67,695 s | 3 (doble) |

Hay un simple 46 ms antes del doble. El tiempo CSV es el del programa, no debe confundirse con la posición del reproductor AVI.

El principal mira verdes desde fila 80. El respaldo del doble recorta desde fila 70 y pide negro por encima de ambos componentes. Cuando el verde izquierdo todavía está alto, queda recortado y su comprobación superior puede mirar el propio verde. Esto rechaza el par aunque ambos cuadrados sean visibles en la imagen completa. Ampliar el color conseguía GS3 usando ruido en el negro: no era la solución correcta.

En el firmware local, GS2 puede seleccionar la acción 5; su caso hace un re-chequeo antes de iniciar un avance de 800 ms y un giro fijo. Si ya arrancó esa maniobra, recibir GS3 después no garantiza cambiarla a doble. Es una explicación compatible con el código, no una confirmación del movimiento de aquella corrida: falta CSV Teensy y verificación de firmware cargado. No se atribuyen ruedas, ángulo real o recepción de tramas a los datos de Python.

## Qué agrega el candidato

`EarlyDouble` envuelve al clasificador temporal previo. No cambia el detector principal, sus respaldos, motores, rampa o recuperación.

1. Observa componentes completos de verde desde fila 50, antes de recortarlos por fila 70/80.
2. Exige dos componentes de tamaño suficiente, a lados opuestos de la referencia negra, con solapamiento vertical y separación horizontal. Al menos uno debe tener la comprobación superior negra; además exige una franja negra entre ambos.
3. Confirma la identidad del par durante dos observaciones próximas. Puede observar antes de que el principal acepte la marca, pero no inicia una marca mientras el principal siga enviando cero.
4. Si aparece por primera vez un par cuando el principal ya propone un simple, difiere ese simple durante un cuadro. Si el par no se confirma, devuelve el simple. Si se confirma, devuelve doble. Un simple sin evidencia de segundo componente no espera.
5. Mantiene una memoria independiente: nunca modifica el reloj del doble anterior ni acorta sus GS3. Conserva prioridad de los estados distintos de 0/1/2/3.

Esas condiciones no demuestran infalibilidad; describen el alcance del candidato comprobado offline.

## Comparación justa

Se mantuvo el mismo rango calibrado de las muestras actuales en ambos lados: LAB `[54,95,120]..[132,112,139]`, con las ampliaciones de respaldo que ya calcula el calibrador. Se comparó clasificador anterior versus anterior más candidato, no código viejo con colores diferentes contra código nuevo.

Para evitar ejecutar main y sus motores, el replay extrae sólo su bloque de clasificación de verdes y usa los helpers locales. Mantiene el estado temporal del doble y los tiempos del CSV. No simula bloqueos de rampa, estado global, transmisión, movimiento ni el efecto de la nueva decisión sobre imágenes futuras: el robot real dejaría de seguir exactamente la trayectoria grabada.

## Cambios observados

| Corrida | Cuadros | Salida diferente | Grupos de cambio |
| --- | ---: | ---: | ---: |
| 20261101_124912 | 24.341 | 13 | 6 |
| 20261101_114747 | 17.296 | 12 | 7 |

De los 25 cambios, 21 adelantan doble sobre un simple y cuatro difieren un simple un cuadro por evidencia inicial de par. Los cuatro también muestran dobles. No hubo GS3 anterior degradado ni cambio directo de un lado simple al otro. Se comprobaron visualmente todos los cuadros modificados en `cambios_principal_*.jpg` y `cambios_validacion_*.jpg`, junto con vecinos de las esperas.

En la entrada crítica, con los colores calibrados:

| Cuadro | Clasificador previo | Candidato | Observaciones compatibles |
| --- | --- | --- | ---: |
| 1648 | 0 | 0 | 1 |
| 1649 | 2 | 3 | 2 |
| 1650 | 2 | 3 | 3 |
| 1651 | 2 | 3 | 4 |
| 1652 | 3 | 3 | 5 |

Así elimina el primer simple del replay en ese episodio. Las dos etiquetas pendientes se conservan intactas: no se borraron ni cambiaron para aprobar.

## Qué falta antes de usarlo

Este paquete no es un reemplazo directo de doble_dato.py. Recibe una instancia del clasificador previo y los rangos calibrados; la integración debe hacerse sobre el main y helpers realmente cargados en la Raspberry, conservando la misma instancia entre cuadros.

El calibrador actual evalúa escenas independientes con el detector anterior. Por eso S sigue rechazando esos dos cuadros: no se falseó ese resultado ni se habilitó una instalación automática del candidato.

Próximo paso: integrar con versión comprobada y ejecutar prueba física grabada de simples, dobles, descartes, lateral y rampa, preferiblemente con CSV Teensy. Las dos corridas offline son del taller, no prueban iluminación de competencia. El rango L máximo de estas muestras oscuras tampoco demuestra cobertura de verdes más iluminados; no debe reemplazarse globalmente una calibración de sede sin comprobarla.

Archivos: candidato `doble_temprano.py`, copia de referencia `doble_dato_base.py`, replay reproducible `replay.py`, tablas por cuadro y resúmenes JSON, pruebas y galerías. Ningún archivo de conducción fue sustituido.
