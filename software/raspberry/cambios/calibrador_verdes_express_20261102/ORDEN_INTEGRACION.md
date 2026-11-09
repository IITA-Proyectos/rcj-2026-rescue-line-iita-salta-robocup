# Orden para combinar los cambios sin pisarse

1. Claude termina su paquete y se conserva esa versión final identificada por sus archivos y huellas. Se instala y verifica ese paquete primero, con su respaldo. No se usa un main antiguo de este chat para reemplazarlo.
2. Se consulta el main y los helpers que realmente quedaron en Desktop, junto con el entorno del servicio. El instalador del refuerzo del doble comprueba el helper anterior y los colores: si difieren, se adapta el refuerzo a esa base, no se fuerza la copia.
3. Nuestro paquete `doble_transversal_20261102` agrega doble_transversal.py y reemplaza únicamente doble_dato.py, conservando el clasificador anterior por dentro. No modifica main.py ni los helpers de rampa, plateado o cresta de Claude. Conserva su propio respaldo. Se prueba con los colores originales para aislar el cambio del doble.
4. Después se abre el calibrador usando ese main REAL: `--main /home/iita/Desktop/main.py`. Se comprueban cámara y entorno del servicio. No se aplica automáticamente el perfil de práctica de Windows.
5. Sólo se aplica un perfil de color si pasa sus negativos, las decisiones, las protecciones y pruebas con imágenes nuevas. Si colores y decisiones tienen resultados diferentes, se guarda borrador y se mantiene la configuración del robot.
6. Una corrida corta grabada confirma simple izquierdo/derecho, doble, descarte, lateral y rampa; de ser posible se registra Teensy. La comparación visual offline no demuestra el comportamiento combinado del movimiento.

## Comprobación local realizada

La instantánea local de `cresta_bajada_20261101/main.py` con SHA256 `e91869114a80507fc92aea627b96e624c22715a3ca9d3c5425fdf11346d2ee81` tiene el mismo bloque visual de verdes y las mismas constantes de color/área que nuestra referencia de las pruebas. Evidencia: compatibilidad_claude.json. Esto no confirma que sea la versión final ni la instalada en la Raspberry, y no valida los cambios de rampa/plateado de Claude.

`base_visual_claude_y_verdes/` es una copia local para el calibrador con ese main y los helpers visuales necesarios. No se ejecutó main ni se instala esa carpeta: no es un paquete completo de conducción. Si Claude actualiza el main, debe renovarse la instantánea y repetir la comprobación.

## Estado actual del calibrador

La versión 2 añade Comprobar (T), Exportar muestras (X), borrador no instalable, separación de color/decisiones, escenas de protección y verificación de reutilización de imágenes. Conserva cuatro puntos, rectángulos, borrado de muestras, cámara, PNG y video limpio.

Tus muestras de práctica siguen guardadas. El borrador tiene color comprobado en esos recortes, pero aún hay decisiones y pruebas nuevas pendientes; no es un perfil aprobado. Los colores originales con el refuerzo del doble fueron los comprobados en 41.637 cuadros. No confundir ese resultado con aprobación de los colores nuevos de práctica.
