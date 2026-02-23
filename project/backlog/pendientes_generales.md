# Pendientes 

## Equipo:
- Laureano
- Lucio
- Benjamin

Los tres trabajamos en el mismo objetivo. La unica diferencia es que Benjamin hace pruebas de IA por separado.

Objetivo principal: optimizar el rescate con IA para aumentar FPS en Raspberry, manteniendo precision y estabilidad.

## Resumen reglamento 2026 (zona de rescate)

Resumen del reglamento 2026:
- Zona de evacuacion de 120 cm x 90 cm con paredes de al menos 10 cm.
- Cinta plateada reflectiva en la entrada (25 mm x 250 mm).
- Cinta negra en la salida (25 mm x 250 mm).
- La linea negra termina en la entrada y vuelve a empezar en la salida.
- Dos zonas altas (triangulos): rojo (victima muerta) y verde (victimas vivas).
- Triangulos de 30 cm x 30 cm, paredes de 6 cm, centro hueco.
- Paredes de cualquier color excepto rojo, verde y negro.
- Zonas en cualquier esquina que no sea entrada/salida.
- Puede haber obstaculos o speed bumps dentro de la zona (no suman puntos).
- Puede haber luces LED blancas en la parte alta de las paredes.
- Puede haber victimas falsas que deben ignorarse.
- Victimas reales: esferas de 4-5 cm, masa descentrada, max 80 g.
  - Vivas: plateadas, reflectivas y conductoras.
  - Muerta: negra, no conductora.


## Pendientes prioritarios

- Definir decision sobre segunda camara y documentarla.
- Evaluar la incorporación de una segunda cámara, verificando que no afecte el desempeño de la cámara wide en rescate y que mejore efectivamente el seguimiento de línea en curvas cerradas.
- Prototipo rapido de segunda camara con soporte temporal (si se aprueba).
- Probar linea en curvas 135 con la camara baja.
- Evaluar el impacto mecanico de mover el servo lift.
- Implementar y testear la estrategia de re-enganche con ROIs laterales.
- Salida de la zona de rescate de manera correcta tenemos una base pero no funciona con los obstaculos 
- Definir estrategia para resolver pendientes laterales inclinadas (mecánica vs control).
- Definir cómo adaptar el modelo de IA ante:
    Cambios de color en paredes.
    Iluminación variable.
    Linterna intermitente.
## Sistema de re-enganche en curvas cerradas con camara WIDE

1. La Raspberry calcula el porcentaje de linea negra visible.
2. Si baja de un umbral minimo, la Raspberry envia un green_state especial a la Teensy.
3. La Teensy retrocede una distancia corta para recuperar contexto visual.
4. La Raspberry analiza ROIs laterales (izquierda y derecha) buscando linea negra.
5. Si hay linea en un ROI, se gira hacia ese lado.
6. Si no hay linea, la Teensy avanza recto hasta recuperar un porcentaje confiable.
7. Al recuperar el porcentaje durante varios frames seguidos, se vuelve al modo normal.

Parametros por definir:
- Umbral de poca linea negra.
- Umbral de linea confiable.
- Tiempo o distancia de retroceso.
- Tamano y ubicacion exacta de ROIs laterales.

## Tareas especificas de IA

- Probar TFLite con NMS en Raspberry Pi 5.
- Resultado actual: 16 FPS en pruebas internas.
- Comparar FPS vs precision con el modelo ONNX FP32.
- Ajustar augmentations con linternas intermitentes.
- Medir impacto de los augmentations en detecciones reales.
- Grabar nuevos videos con los nuevos cambios implementados para adaptar el modelo a ese entorno

## Bloqueos actuales

- La segunda camara requiere definicion mecanica antes de programar.

## Criterios de exito

- FPS superiores a 15 con rescate estable.
- Detecciones consistentes en diferente iluminacion.
- Mejora clara en curvas 135 sin salidas de linea.
- Salida de zona de evacuacion funcionando de forma confiable.
- No perder mucho tiempo probando las cosas
