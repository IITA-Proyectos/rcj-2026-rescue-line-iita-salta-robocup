# Refuerzo del doble con descarte por transversal — versión 2

## Estado

Preparado para prueba física, no instalado. La Raspberry no respondió en 10.109.108.189. El candidato anterior de `doble_temprano_20261102` permanece rechazado: no usarlo.

## Cambios comprobados

Se conservaron los rangos originales del main: `[120,90,110]..[198,109,134]`, el respaldo oscuro/sombra y su geometría. No se aplicó el perfil nuevo de práctica. Esto permite aislar el refuerzo del doble sin mezclarlo con cambios de calibración.

Se reprodujeron consecutivamente dos corridas, con el estado temporal del doble y tiempos del CSV:

| Corrida | Cuadros procesados | Diferencias con el clasificador previo |
| --- | ---: | --- |
| 20261101_124912 | 24.341 | 1651: 2→3; 17706: 2→3 |
| 20261101_114747 | 17.296 | Ninguna |

**41.635 de 41.637 salidas quedaron idénticas.** Los dos cambios son los simples que precedían al doble, a 01:22,50 y 14:45,25 del AVI principal. Se revisaron visualmente esos cuadros y los vecinos; no se afirma inspección visual de los 41.637.

Se ejecutó primero el núcleo aislado y después el módulo final `doble_dato.py` que utilizaría main. Ambos produjeron exactamente los mismos dos cambios. Evidencia: `replay_*.csv/json` y `paquete_*.csv/json`.

La izquierda confirmada por el usuario se conserva: 9970, 9971 y 9972 siguen devolviendo 1. Se agregó además una prueba con verdes por encima de la transversal y sólo un verde válido debajo a la izquierda: sigue devolviendo 1, sin espera ni doble. Los descartes del clasificador anterior no cambiaron en estas reproducciones.

Hay 12 pruebas del refuerzo, integración e instalador y 17 del calibrador. No sustituyen la prueba real.

## Qué se corrigió respecto al candidato rechazado

El anterior permitía que sólo uno de los componentes tuviera negro encima. Eso admitía dos verdes ubicados a lados distintos de la transversal. Ahora **cada uno de los dos cuadrados debe satisfacer la comprobación de negro encima**, con el mismo umbral 0,32. También se exige separación negra entre los dos, dimensiones suficientes, posición a ambos lados de la referencia de línea y consistencia durante dos observaciones.

El detector principal recibe negro recortado desde fila 60. Por eso comprobar una marca más alta con esa máscara podía borrar la evidencia de la transversal. El refuerzo reconstruye una máscara negra auxiliar sobre la imagen LAB reconvertida a BGR para mirar encima de esa marca, sin alterar la máscara de seguimiento. Por debajo de 60 conserva la máscara negra recibida. Excluye de esa máscara auxiliar los píxeles reconocidos como verde, para que un verde oscuro no se use como cinta negra.

La observación usa componentes completos desde fila 50; la salida sólo se modifica después de que el detector anterior acepte una marca. No se crean episodios desde cero. La memoria del refuerzo es independiente y respeta cualquier 3 que el clasificador anterior ya sostuviera. No se cambia la maniobra de Teensy, la rampa, recuperación, plateado, área mínima ni main.

## Límites de la comprobación

Se reproduce únicamente la parte visual del main: clasificación de verdes, helpers y estado temporal del doble. No se reproduce el control global de main, bloqueos de rampa, transmisión ni Teensy. Una nueva decisión real cambia el movimiento y por tanto los cuadros futuros; el replay no demuestra que vaya a recorrer la misma trayectoria.

Mantener una salida anterior no prueba que sea semánticamente correcta. Esta extensión conserva los 3 previos; no intenta corregir cualquier doble erróneo preexistente. El caso de izquierda se comprobó exactamente en los tres cuadros confirmados, no se etiquetó automáticamente toda su secuencia posterior.

El descarte por transversal es una comprobación de imagen, no una garantía geométrica bajo cualquier perspectiva. La conversión LAB→BGR puede introducir pequeñas diferencias de color. No se cambiaron colores para compensarlo. No hay validación con luces de competencia ni medición de rendimiento en Raspberry.

## Paquete e instalación

Archivos de conducción: `doble_dato.py` conserva el clasificador anterior y lo envuelve; `doble_transversal.py` agrega la comprobación. `doble_dato_base.py` es la referencia para verificar y respaldar, no reemplaza al main.

Copiar el paquete descomprimido a una carpeta propia en la Raspberry. Con robot detenido, ejecutar desde esa carpeta:

```bash
python3 desplegar.py
```

El instalador comprueba que doble_dato.py coincida con la referencia probada y que los colores de main sean los originales verificados. Si Claude u otra persona cambió esos archivos, rechaza la instalación en vez de pisarlos. Compila antes de escribir, crea respaldo y verifica las copias. No cambia main ni inicia el servicio. Los cambios se usan en el siguiente arranque.

Para volver al comportamiento anterior se puede ejecutar la corrida con `DOBLE_TRANSVERSAL=0`, o restaurar sólo doble_dato.py desde el respaldo indicado. No copiar la referencia manualmente sin comprobar la versión de la Raspberry.

La prueba física siguiente debe incluir: el doble que enviaba primero derecha; un doble que siempre entraba bien; la izquierda correcta con otro verde por arriba; derecha simple y verde que debe descartarse; lateral/rampa. Grabar Python y, si está disponible, CSV Teensy para confirmar qué dato recibió y qué maniobra ejecutó.

## Compatibilidad del calibrador

El calibrador actualizado reconoce este envoltorio y mantiene los colores del refuerzo sincronizados con los del doble al previsualizar o aplicar un perfil. Incluye también la huella de doble_transversal.py en sus comprobaciones. No se instaló el perfil de práctica ni se falseó su validación por escenas independientes: requiere una comprobación separada con la versión y las luces reales.
