# Revisión de las etiquetas de práctica

Se revisaron las 36 etiquetas guardadas: 14 recortes verdes, 11 negativos y 11 escenas con estado esperado. Se inspeccionaron visualmente todos los recortes verdes, las escenas y los tres negativos rechazados. No se borraron ni alteraron las etiquetas y no se instaló ningún perfil.

## Problema encontrado

El ajuste automático toma percentiles de cada recorte y les agrega margen. Algunos rectángulos tocan bordes oscuros; unos pocos píxeles con poco color llevan el rango a LAB `[39,95,113]..[126,123,138]`. El límite A=123 se aproxima a colores neutros y termina aceptando zonas de plateado/piso, además de partes de cinta negra.

En los tres negativos rechazados acepta aproximadamente 23,6%, 31,8% y 3,25% de los píxeles del recorte. Los negativos están correctamente etiquetados. Que las escenas completas devuelvan GS=0 no demuestra que el color esté separado: geometría y recorte de la imagen también intervienen. Los negativos se prueban como material, incluso cuando están fuera de la zona activa del detector en ese cuadro.

## El falso éxito de dos pruebas de doble

Las escenas `muestra_20261102_085529_642029.png` y `muestra_20261102_085536_942123.png` corresponden a los cuadros originales 1650 y 1651. El cuadrado izquierdo está principalmente por encima del corte de fila 80.

Con el rango automático, aparecen manchas en la cinta negra. Tras la morfología del principal, el cuadro 1650 contiene el componente derecho y un componente adicional pequeño de área 32,5; el 1651 contiene el derecho y otros dos pequeños de áreas 24,5 y 71,5. El principal usa cantidad de contornos, sin un mínimo de área por contorno: esos fragmentos ayudan a producir GS=3. No es evidencia de que ambos cuadrados se estén segmentando correctamente.

Con colores más separados desaparecen esos fragmentos y ambos cuadros dan GS=2. La comprobación independiente del doble tampoco confirma: exige ocupación negra superior mayor que 0,32; para el componente izquierdo esos cuadros dan aproximadamente 0,234 y 0,223 porque la región de referencia está recortada sobre el propio verde. Por tanto no alcanza con ampliar color para obtener un doble temprano fiable. No se propone cambiar ese criterio dentro de esta revisión.

En el cuadro siguiente, 1652, ya hay un componente izquierdo real dentro de la zona principal y la clasificación da doble sin necesitar ruido en el negro. Ver `dobles_tempranos.jpg`.

## Candidato para comparar, NO instalar

Se evaluó `[39,90,110]..[198,115,138]`. Este rango contiene los colores originales del principal y los respaldos anteriores; conserva además el techo L=198 en lugar de reducirlo al máximo observado en las muestras oscuras de esta práctica. Contener el rango anterior no garantiza conservar decisiones: más píxeles también pueden cambiar contornos.

- Acepta como mínimo 96,9% de cada uno de los 14 recortes verdes.
- Acepta 0 píxeles en los 11 recortes negativos seleccionados. Es un resultado de estos recortes, no de todo el mapa ni de otras luces.
- Coincide con 9 de las 11 etiquetas de escena. Las dos discrepancias son los dobles tempranos descritos arriba. Se conservan como fallos pendientes: no se cambiaron a derecha ni se eliminaron para aprobar el perfil.
- No se considera validación independiente: muchas escenas reutilizan la imagen de las muestras de ajuste. Para validar de verdad hacen falta cuadros o recorridos nuevos.

El archivo `candidato_NO_INSTALAR.json` tiene `enabled_for_control: false`, conserva la validación fallida y no es un perfil de instalación del calibrador.

## Comprobación ampliada

Se compararon 1.903 cuadros reales del recorrido 20261101_124912: muestreo general, alrededores de las marcas registradas y muestras de entradas al plateado. No son todos los cuadros ni todas las corridas. La comparación es visual por cuadro, reiniciando el estado temporal del doble; no reproduce la secuencia completa de main, rampa, recuperación o Teensy. El GS del registro no se usó como verdad visual.

En los cuadros comparados, el detector anterior produjo estado distinto de cero en 488 y el candidato en 605. Hubo 117 cuadros adicionales con marca, cero cuadros donde una marca anterior pasase a cero y seis cambios entre estados de marca. Esto no prueba ausencia de regresiones: 1/2/3 también tienen que ser correctos y el momento de envío importa.

Se inspeccionó un representante de cada uno de los 49 grupos de cambios, más los seis cambios entre estados de marca, en `cambios_0.jpg` a `cambios_3.jpg`. Muchos corresponden a verdes visibles que entran antes o se conservan más tiempo, pero no se adjudicó automáticamente corrección a todos los cuadros nuevos. Para una prueba de conducción todavía hace falta revisar secuencias continuas y el dato recibido por Teensy.

## Qué hacer ahora

Conservar estas muestras y los negativos. No forzar Guardar ni aplicar este perfil. El cálculo inicial del calibrador necesita usar negativos al elegir el rango, además de preservar la cobertura anterior; ahora los usa para rechazar, no para ajustar. Separadamente, la detección del doble temprano requiere estudiar su geometría y momento de confirmación. No se deben cambiar recuperación o rampa para compensar este problema de visión.

Artefactos: `comparacion.json`, `replay_muestreado.csv`, `replay_resumen.json`, galerías y candidato bloqueado. Los programas del robot permanecen intactos.
