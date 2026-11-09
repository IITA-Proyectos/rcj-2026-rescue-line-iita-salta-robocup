# VERDE-SOMBRA-1 — refuerzo instalado 01/11/2026

Instalado y verificado por hash, compilacion y prueba sintetica remota. Respaldo: /home/iita/Desktop/respaldo_verde_sombra_20261101_114452. No se reinicio el servicio ni se ejecuto el robot. La siguiente ejecucion carga el cambio.

## Archivos de la nueva prueba

Se copiaron video pista_rampa_transicion_20261101_111110.avi, log,12194 PNG originales, cuadros.csv,parametros y programas. Grabador declara cero cuadros perdidos. El archivo completo corrida_111110.tar tiene SHA256 c49c1557c6ee44f1767fdc89ed43e4b6dd03aeda40c2adc272078f15f6a79298, verificado contra Raspberry. El usuario confirma que ahora subio la rampa; no se declara resuelto por eso todo tipo de subida. Las recuperaciones siguen siendo una tarea separada.

## Causa y cambio

La captura propuesta muestra LAB [80,90,111]–[162,111,137]. La prueba aun tenia el principal [120,90,110]–[198,109,134], con respaldo oscuro L>=100. En el verde izquierdo de f130, los percentiles10/50/90 de L medidos sobre una seleccion verde HSV dan65/74/78: tanto el principal como el respaldo y gran parte del rango sugerido80 lo descartan. Es un ejemplo de esta iluminacion, no una calibracion universal de toda superficie verde.

Se mantienen completos e identicos el principal y el respaldo anterior. SOLO si ambos devuelven0 se ensaya un respaldo nuevo: Lmin60, maximoL198 conservado; A90–111; B110–137. Area estrictamente mayor a max(600,min_square_size). ROI desde fila80, referencia negra en90:120 y ocupacion de negro encima en60:90 >0,32, igual a los filtros geometricos existentes. No se convierte cualquier mancha de color en orden de giro.

Para las detecciones NUEVAS, doble exige componentes de area morfologica>=60 en lados opuestos del centro negro, con margen3px. Dos componentes situadas a derecha no valen doble; tampoco una mancha izquierda fragmentada que simplemente extiende su caja a traves del centro. Esto evita los falsos GS3 de f7702 y de la secuencia12152–12165 que aparecian al ampliar el color sin mejorar ese criterio.

Version en log: [VERDE] VERDE-SOMBRA-1. Cada deteccion adicional imprime [VERDE-SOMBRA] gs=... px=... y guarda la mascara usada en el conteo verde del registro.

## Validacion

Replay completo de63133 cuadros de seis grabaciones. Se conservan las834 detecciones positivas del detector anterior evaluado; se agregan316 cuadros. Son cuadros, NO316 marcas diferentes ni316 exitos fisicos.

|             run |   cuadros |   positivos |   nuevos |
|----------------:|----------:|------------:|---------:|
| 20261031_195318 |      7927 |         138 |       31 |
| 20261031_210305 |      8907 |         137 |       32 |
| 20261031_213650 |     18331 |         276 |       77 |
| 20261031_221132 |      7420 |          79 |       25 |
| 20261101_103155 |      8354 |          99 |       76 |
| 20261101_111110 |     12194 |         105 |       75 |

Se inspeccionaron las laminas de101 grupos de cuadros agregados, con principio/medio/final. Los grupos pueden pertenecer a la misma marca durante una maniobra. Los seis intervalos de control del primer video que rechazaban verdes posteriores al cruce siguen en cero. En la prueba nueva se verifica deteccion izquierda en130–135,1336–1339,1469–1473,11289–11295,11418–11421; y derecha coherente en7702–7710 sin falso doble. Se mantienen los105 cuadros positivos anteriores de esta prueba y se agregan75.

Cinco pruebas adicionales: izquierda/derecha/doble sinteticos, fragmentos de un mismo lado, necesidad de negro arriba y de referencia abajo, area insuficiente, identidad del respaldo anterior por AST. Compilacion y prueba en Raspberry. Bloque previo de verdes identico. Hashes de rampa y recuperacion siguen identicos a los instalados antes del cambio.

## Limites y prueba fisica

La conservacion por cuadro no demuestra que la nueva trayectoria completa conserve todos sus resultados: la primera deteccion agregada cambia el movimiento y los cuadros futuros reales. Confirmar en robot que toma los verdes oscuros y sigue ignorando los posteriores al cruce.

La modificacion conserva las decisiones previas incluso si alguna de ellas requiere otra correccion: no se la presenta como prueba de que todos los verdes ya funcionan. En particular no se cambio el orden de prioridad de un simple previamente detectado frente a un doble que aparece despues, ni el re-chequeo/maniobra de Teensy. El reconocimiento de color y la ejecucion completa del giro deben verificarse por separado. Los nuevos disparos durante una maniobra tambien necesitan validacion fisica; el video viejo no prueba la recepcion de la trama ni que no haya un segundo giro. No hay CSV nuevo de Teensy.

No se modificaron recuperacion, rampas, motores o deteccion de plateado. La candidata de codos no se instalo.

Hashes instalados:
main.py ecdeaa4d6b2c5f8da832b19b9d5f8c5b7357e3333541db13e280c656fb825186
verde_oscuro.py 5bdded29693df6ef2f9eda3765edfd6f1f6382c032a7bc2f98c3c4a55f611da7
rampa_transicion.py ed46092fd1854b5c3c5e6251f58ad8c059e3839d4fdff581efc832a47ca580d0
recuperacion_guard.py c3333b7e51f479cea041c656402438dc6a818f5d34ec4971f93ce0d910c9f52f
