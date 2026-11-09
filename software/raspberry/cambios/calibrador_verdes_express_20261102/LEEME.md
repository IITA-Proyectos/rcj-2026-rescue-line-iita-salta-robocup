# Calibrador express de verdes

## Versión 2: guardar no equivale a instalar

**Comprobar (T)** muestra por separado COLOR y DECISIONES. **Guardar perfil (S)** siempre conserva un `borrador_verdes.json` y los informes; sólo crea `perfil_verdes.json` si pasan todas las comprobaciones. Un borrador nunca se puede aplicar con --apply. `validacion.txt` explica los pendientes. El mensaje anterior de "no guardado" podía confundir que no existiera nada: las muestras siempre se conservaban, y ahora también se guarda el borrador explícitamente.

El ajuste comienza con los rangos anteriores y busca la ampliación mínima necesaria. Evalúa la cobertura con principal/oscuro/sombra: un verde oscuro no tiene que entrar forzosamente en la máscara principal. Puede ajustar de forma independiente el límite de luminosidad del respaldo de sombra, conservando la prioridad de los detectores. Usa negativos para evitar ampliaciones que los confundan. Si no puede separar los materiales sin perder los colores previos, rechaza el perfil: no borra ni cambia etiquetas. Conservar colores NO garantiza conservar decisiones, por eso las prueba también.

El perfil incluye `shadow_l_min`. Al aplicar un perfil aprobado, puede modificar únicamente ese número en verde_oscuro.py y el rango correspondiente del doble, sin cambiar la lógica geométrica, área mínima o tiempos. Si los rangos del principal no cambian, main.py queda sin escribir. Todo archivo que se modifica se respalda, y se conservan los finales de línea.

Las escenas de `protecciones/muestras.json` conservan las izquierdas confirmadas por el usuario. No pertenecen a las etiquetas que se pueden borrar desde la ventana. Un perfil que las cambie queda bloqueado, aunque el color de sus recortes parezca correcto. Estas protecciones del taller no sustituyen pruebas con la cámara y luces de la sede.

Las pruebas 0/1/2/3 deben incluir imágenes que no se hayan usado para ajustar el verde. Se compara el contenido de la imagen, no sólo el nombre de archivo. Esta comprobación evita reutilización exacta, pero no garantiza independencia entre cuadros vecinos: lo más sólido sigue siendo reservar otra corrida completa.

El botón **Prueba: foto/entrada (F)**, arriba de la imagen, elige qué significa pulsar 0/1/2/3. **Foto** exige el resultado en ese cuadro exacto. **Entrada** usa contexto real anterior y hasta diez cuadros posteriores y comprueba el **primer dato de marca**, no el último: si primero sale derecha y luego doble, una prueba de entrada doble falla. Una foto anterior al disparo puede tener 0 sin que toda la entrada esté mal. Entrada requiere una fuente con secuencia disponible; no repite artificialmente una imagen aislada.

Para cambiar una prueba ya guardada de foto a entrada, elegir el modo F y volver a pulsar la misma etiqueta sobre esa misma imagen. Se conserva respaldo y se reemplaza sólo el tipo de esa prueba, sin cambiar su clase. No cambiar el tipo para ocultar un error: usar entrada cuando la etiqueta describe la maniobra de toda la llegada y foto cuando se exige un estado en un instante concreto. Elegir una entrada con contexto suficiente, sin otra marca distinta dentro de la ventana anterior.

Cuando una escena proviene de --recording o de un video limpio, el calibrador busca hasta 25 cuadros anteriores y usa sus tiempos para reproducir el estado del doble. No inventa confirmación repitiendo una foto. Si sólo hay una imagen aislada, lo informa y no da por aprobada una confirmación que requiere secuencia. Si existe cuadros.csv, usa sus tiempos; sin él usa 20 FPS para PNG, una aproximación que debe contrastarse con la grabación original.

**Exportar muestras (X)** crea un ZIP con PNG, etiquetas y contexto disponible, con rutas relativas para abrirlo en otra computadora o Raspberry. No incluye una instalación de programas. Descomprimir y usar esa carpeta como --out, eligiendo el main real con --main. El contexto de video exportado se guarda como PNG, sin copiar el video entero.

No se duplican etiquetas idénticas al mantener una tecla. Al recuperar una sesión antigua, se retiran únicamente duplicados exactos con respaldo; se conservan etiquetas contradictorias para revisarlas. Exportar reutiliza imágenes de contexto idénticas sin borrar observaciones ni sus tiempos reales.

Para comprobar sin ventanas:

```bash
python3 calibrador_verdes_express.py --main /home/iita/Desktop/main.py --out /home/iita/calibracion_verdes_express --assess
```

Las instrucciones de captura siguientes también sirven en esta versión; donde se indique que S rechaza el perfil, conserva igualmente el borrador para revisión.

Calibra el color del detector principal, los respaldos oscuro/sombra y la comprobación del doble. Conserva áreas, geometría, tiempos, recuperación, rampa y protocolo. No importa ni ejecuta main.py, no abre serial ni envía movimientos.

## Antes de abrir

Copiar `calibrador_verdes_express.py` a `/home/iita/Desktop/` junto al main real y sus módulos `verde_oscuro.py` y `doble_dato.py`. Se necesitan Python 3.9 o superior, numpy y OpenCV con ventanas, normalmente ya presentes en el robot. El calibrador anterior tenía constantes diferentes: este lee main y extrae su bloque de decisiones de verde. Si no reconoce su estructura se detiene.

Usar una terminal del escritorio de la Raspberry (monitor o VNC). SSH sin escritorio gráfico no muestra estas ventanas. Mantener el robot inmóvil y la alimentación de motores desconectada durante la calibración. Detener el servicio libera la cámara, pero no se presupone que sea una orden de freno de la Teensy.

```bash
sudo systemctl stop iita-robot.service
cd /home/iita/Desktop
python3 calibrador_verdes_express.py --main /home/iita/Desktop/main.py --out /home/iita/calibracion_verdes_express
```

Si la corrida usa `CAMARA_WB`, `CAMARA_EXPO` o `DOBLE_SIN_FACTOR` desde el servicio/terminal, usar esos mismos valores al calibrar y aplicar. El calibrador no lee automáticamente EnvironmentFile de systemd. Sólo aplica controles de cámara si esas variables están presentes; no inventa nuevos ajustes. Una apertura nueva con exposición automática puede tardar en asentarse: observar unos segundos antes de muestrear. No se garantiza que la cámara mantenga los mismos colores al reabrir; comprobar la máscara al iniciar la prueba real.

## Recorrido rápido (aproximadamente 3–5 minutos)

**El modo inicial ahora es 4 puntos**, como el calibrador por esquinas. Marcar con cuatro clics las esquinas de un cuadrilátero dentro del material, dejando margen respecto a negro y blanco. Puede ser un trapecio por perspectiva: no tiene que ser un cuadrado geométrico. Los puntos se ordenan automáticamente aunque se marquen cruzados. Se colorea sólo el interior real del polígono para ajustar y validar; no su rectángulo envolvente. Si el cuarto punto queda dentro del triángulo de los otros tres o alineado, no se agrega: elegir otra esquina. **B**, clic derecho o Quitar punto elimina el último punto de la selección sin borrar muestras guardadas. **R** limpia la selección sin tocar etiquetas. **V** o el botón Modo alterna entre cuatro puntos y arrastrar rectángulo. Después de completar la figura, guardar con **G** o **N**. Para calibrar dos verdes, completar y guardar cada uno por separado.

Para borrar una figura YA guardada, pulsar **Eliminar figura (E)** y tocar su contorno verde/azul. Si hay figuras superpuestas, se elige el borde más cercano al clic; tocar una parte del borde que distinga la figura deseada. Se elimina sólo esa muestra, conservando las demás y las pruebas posteriores. Se guarda una copia `muestras_antes_borrar_FECHA.json` y se recalcula el rango. E nuevamente cancela el modo de borrado. R sólo limpia la selección en curso; Z quita la última etiqueta de toda la sesión.

La interfaz incluye botones para todas las acciones de calibración y prueba. **A** va a la imagen anterior y **D** a la siguiente. También se puede hacer clic en Anterior/Siguiente. **P** o espacio congela/reanuda la cámara. Los botones de navegación se desactivan en cámara; Pausa/vivo se desactiva al revisar archivos.

El rectángulo rojo sigue el mouse mientras se arrastra y se ajusta a los límites de la imagen. Con cámara, empezar a dibujar congela automáticamente el cuadro que se estaba viendo. Al soltar, pulsar G o Guardar verde; la selección guardada queda en verde con G OK. Un negativo queda en azul con N OK. Las marcas se conservan al volver a esa misma imagen; Z/Deshacer elimina la última etiqueta. Al reabrir se recuperan las muestras y, si ya hay tres verdes, se recalcula el mismo rango de práctica. No instala el perfil automáticamente.

1. Presentar un verde como lo ve el robot. Pulsar **espacio** para congelar o empezar a marcar para congelar automáticamente. Marcar cuatro esquinas interiores (o usar rectángulo con V), evitando bordes y negro, y pulsar **g**. Espacio vuelve a vivo. Repetir al menos tres veces: iluminado, sombra, vista lateral/rampa. Incluir los cuadrados de ambos lados del doble; no seleccionar el espacio entre ellos. Cuantas más condiciones reales se incluyan, mejor se comprueba el rango.
2. Guardar al menos tres negativos con selección + **n**: blanco con brillo, negro, plateado u otro piso. No mezclar materiales diferentes en una selección grande, porque diluye los falsos positivos. Se evalúan todos los rangos, incluso los respaldos y doble.
3. Pulsar **c**. Se propone LAB con las muestras verdes acumuladas, conservando el soporte previo y comprobando los negativos disponibles. Mirar las cuatro máscaras: principal, oscuro, sombra y color del doble. Línea amarilla: desde allí empieza la máscara principal. También hay que comprobar las decisiones del paso siguiente; píxeles aceptados no demuestran un giro correcto.
4. Con **otras posiciones**, congelar y pulsar **1** para guardar una escena que debería decidir izquierda, **2** derecha, **3** doble, **0** una escena que debe descartar (sin verde o verde que correctamente no debe provocar un giro). Incluir negro y geometría real del cruce: tener píxeles verdes no basta. Repetir las escenas difíciles: rampa, lateral y doble bajo sombra. No etiquetar izquierda/derecha según el giro que deseamos si la marca realmente está en el otro lado.
5. Pulsar **s**. Si un negativo acepta más del 2% de sus píxeles, una muestra verde queda por debajo del 90% de cobertura principal o alguna escena da un GS distinto del indicado, rechaza el perfil y escribe `validacion.json` con el motivo. Estos límites son controles conservadores del calibrador, no garantías estadísticas. **z** elimina la última etiqueta; sirve para corregir un rectángulo equivocado. No borrar una escena difícil sólo para lograr que pase.

El panel muestra GS visual del cuadro: 0 descartar, 1 izquierda, 2 derecha, 3 doble. Usa las funciones locales de oscuro/sombra y la geometría real del doble. No simula confirmación temporal entre cuadros, bloqueos de rampa, estado de recuperación ni el dato finalmente recibido por Teensy. El área `min_square_size` se muestra y no se altera: bajarla automáticamente puede disparar verdes antes de tiempo.

Las muestras y sus PNG quedan guardadas. Al reabrir con el mismo `--out`, se recuperan las etiquetas; pulsar c para recalcular. Para condiciones nuevas de iluminación conviene usar otra carpeta o incluir explícitamente todas las condiciones que se quieran conservar. Un sol que sature el color no se arregla ampliando LAB indefinidamente.

## Comprobar y aplicar el perfil

Con el servicio todavía detenido:

```bash
python3 calibrador_verdes_express.py --main /home/iita/Desktop/main.py --check /home/iita/calibracion_verdes_express/perfil_verdes.json
python3 calibrador_verdes_express.py --main /home/iita/Desktop/main.py --apply /home/iita/calibracion_verdes_express/perfil_verdes.json
```

`--apply` vuelve a comprobar las muestras, el entorno y las huellas de los tres archivos. Si Claude u otra persona cambió esos programas, rechaza el perfil para evitar pisar cambios. Guarda los archivos anteriores en `Desktop/respaldo_verdes_FECHA/` y cambia únicamente los dos límites de color en main.py y los límites de la comprobación del doble en doble_dato.py. Los respaldos oscuro/sombra derivan sus límites de los del principal, como ya hacían. Compila antes de escribir y restaura si falla una escritura. No inicia el robot.

Después hay que hacer una corrida real corta con motores, grabación y registro: simple izquierdo, simple derecho, doble, verde que debe descartar y verde lateral/rampa. Si antes un verde era correcto y ahora falla, no usar ese perfil en competencia. Las escenas independientes del calibrador comprueban color/geometría por cuadro; no sustituyen esta prueba.

Para volver, copiar sólo los dos archivos de la carpeta de respaldo indicada por el instalador, con el robot detenido:

```bash
cp /home/iita/Desktop/respaldo_verdes_FECHA/main.py /home/iita/Desktop/main.py
cp /home/iita/Desktop/respaldo_verdes_FECHA/doble_dato.py /home/iita/Desktop/doble_dato.py
```

## Fuera de la Raspberry

Para revisar un PNG crudo de las grabaciones (160×120, ya orientado):

```bash
python calibrador_verdes_express.py --main RUTA/main.py --image RUTA/f_000001.png --out calibracion_prueba
```

La cámara en vivo se rota 180° igual que main. Los PNG de las grabaciones ya están orientados y no se vuelven a rotar. No usar una captura del overlay ni un panel con máscaras como muestra de cámara.

Para recorrer una carpeta completa de PNG con **A / D** o los botones:

```bash
python calibrador_verdes_express.py --main RUTA/main.py --images RUTA/imagenes_crudas --out calibracion_prueba
```

El paquete incluye `ejemplos_locales/VER_IMAGENES.html`, una galería sin conexión con 12 imágenes completas y comparaciones de las cuatro máscaras. Los GS del registro son evidencia de lo enviado, no etiquetas de que la decisión fuera correcta. La galería sirve para practicar; no sustituye muestras de competencia.

## Corridas y videos anteriores

Preferir los PNG crudos que se guardaron junto al video: evitan compresión y textos dibujados. Se puede abrir una carpeta `crudo_*` con subcarpetas sin copiar sus miles de imágenes:

```bash
python calibrador_verdes_express.py --main RUTA/main.py --recording RUTA/crudo_corrida --out calibracion_prueba
```

A/D y los botones recorren los cuadros. Se conserva el origen de cada nueva muestra. Abrir únicamente una corrida por carpeta `--recording`, para no mezclar secuencias distintas en el orden de navegación.

Para un video limpio 4:3, sin textos ni panel de máscaras:

```bash
python calibrador_verdes_express.py --main RUTA/main.py --video RUTA/video_crudo.avi --video-start 60 --video-step 1 --out calibracion_prueba
```

P reproduce/pausa; dibujar congela el cuadro; A/D retrocede/avanza la cantidad de cuadros indicada en `--video-step`. `--video-start` es el segundo inicial. El video se considera ya orientado como lo ve main; sólo agregar `--video-rotate` si realmente está invertido. El calibrador rechaza dimensiones de paneles como 640×240; no puede identificar automáticamente todos los textos que pudieran estar incrustados en un video 4:3. No usar un video con overlay aunque sus dimensiones sean aceptadas. La compresión puede alterar los colores; preferir PNG originales cuando existan.

Para comprobar con independencia, usar recortes G para ajustar de una corrida y escenas 0/1/2/3 de otra. Las escenas no entran en el ajuste del color. No usar G sobre las imágenes reservadas para evaluación: si se aprovechan para reajustar, dejan de ser una prueba independiente y hace falta otra corrida reservada. No se puede demostrar robustez en la sede con grabaciones que sólo muestran la iluminación del taller.

Archivos locales comprobados disponibles al preparar este cambio:

- `20261101_124912/crudo_doble_dato_20261101_124912`: 24.341 cuadros; origen de las imágenes de esta práctica.
- `20261101_114747/crudo_verde_sombra_20261101_114747`: 17.296 cuadros de otra corrida, disponibles para reservar como evaluación.
- `20261031_210305/crudo_pista_completa_20261031_210305`: 8.907 cuadros, otra fuente posible.

Esos conteos indican archivos disponibles, no cuadros que ya hayan sido todos revisados o etiquetados.
