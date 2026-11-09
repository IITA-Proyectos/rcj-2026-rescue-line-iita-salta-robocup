# Análisis de verdes y curvas — corrida 31/10/2026, 19:53:18

**Revisión posterior importante:** la comparación temporal específica de 00:13, 00:56 y 01:02 encontró verdes izquierdos válidos perdidos por luminosidad antes de los verdes derechos rechazados. Para esos casos prevalece [COMPARACION_13_56_62.md](COMPARACION_13_56_62.md). No se propone aceptar el verde derecho de 1143: se propone recuperar el izquierdo de 1135 y conservar ese rechazo.

No se modificó el programa del robot ni su configuración. Los scripts de esta carpeta trabajan sobre copias.

## Qué se cruzó y precisión

- 7.927 imágenes originales y sus 7.927 filas de decisiones (`cuadros.csv`). El grabador declara cero cuadros perdidos.
- Video de 7.927 cuadros, codificado a 20 FPS. Su tiempo de reproducción NO representa el tiempo real de la corrida: hay pausas sin imágenes y el procesamiento activo rondó 25 FPS. Para localizar evidencia usar el número de cuadro; el cuadro n corresponde aproximadamente a (n−1)/20 segundos del AVI.
- CSV USB con 80.290 filas numéricas candidatas. Una fila claramente dañada con `us=3807` fue excluida del cruce. Hay además cabeceras repetidas y pérdidas de muestras indicadas por `drop`.
- Log: 16 mensajes `cambiando estado`. El código los imprime al recibir STOP/BOOT: prueban una interrupción, por sí solos no prueban que el robot se haya salido. Se revisaron los cuadros anteriores y las interrupciones largas del registro crudo. El listado está en `paradas.csv` y la vista completa en `paradas.jpg`.
- Parámetros guardados por el grabador y código de la Raspberry con SHA256 `2a0bfd8b95b2f41f3cb1f576fa772dff551a6f492aa058fac51920323d73448e`.
- El CSV identifica firmware `c92c566-s`; la `s` y los cambios locales impiden asegurar identidad exacta con todos los fuentes actuales. Las fórmulas descritas abajo son las del fuente disponible y coinciden con las maniobras observadas; no equivalen a recuperar el binario flasheado.

Sincronización: segundo CSV ≈ segundo crudo + 50,35 s. Se buscó el desplazamiento comparando cambios de órdenes de dirección, no los nombres de los archivos. Con una consulta al receptor 20 ms después de la decisión, 97,2% de los cuadros coinciden dentro de un grado del protocolo. La precisión práctica es de decenas de milisegundos, no de una muestra de 5 ms.

El CSV registra `rxsteer` recibido pero NO `green_state` recibido. `green_state` sí está guardado cuadro por cuadro por la Raspberry. La aceptación de verdes en Teensy se infiere por la secuencia de movimiento; no hay confirmación explícita de cada GS en este CSV.

## Resultado principal

Las fallas tienen causas diferentes. No hay fundamento para aumentar o reducir todos los giros, cambiar el PID o ampliar globalmente el rango de verde.

1. Un doble verde empieza como verde simple y el movimiento se compromete antes de que llegue la clasificación correcta.
2. El filtro geométrico de negro encima elimina verdes que ya superaron ampliamente el umbral de color.
3. Recuperaciones terminan por tiempo y avanzan aunque todavía no haya línea conectada/alineada.
4. Algunos cambios del rumbo absoluto de la IMU durante la transición de pendiente no son rotaciones físicas equivalentes.

## Verdes: reproducción de las reglas reales

Parámetros: LAB [120,90,110] a [198,109,134], área >600 píxeles; solo filas 80–119 para verde. Negro: cada canal BGR entre 0 y 90, solo filas 60–119. Referencia lateral: centroide negro en filas 90–119. Validación: ocupación negra >32% en la franja fija 60–89 comprendida entre los extremos del verde.

Se reprodujeron los filtros sobre todos los cuadros candidatos con >100 píxeles verdes (250 cuadros):

| Resultado de la regla | Cuadros |
|---|---:|
| No superan 600 píxeles | 75 |
| Superan el área pero fallan negro encima | 73 |
| Aceptados por el detector y enviados como GS1/2/3 | 102 |

Estos números cuentan cuadros, no marcadores físicos. No todos los verdes visibles tienen por qué ser válidos: el lado respecto de la intersección y el sentido de marcha importan.

Ejemplos reproducidos de rechazo:

| Cuadro | Segundo crudo | Verde detectado | Ocupación negra encima | GS |
|---|---:|---:|---:|---:|
| 1577 | 78,7 | 2345 px | 0% | 0 |
| 1578 | 78,7 | 3123 px | 0,11% | 0 |
| 5717 | 286,2 | 2193 px | 0% | 0 |
| 6576 | 320,9 | 1390 px | 1,35% | 0 |
| 6836 | 332,6 | 3227 px | 0,07% | 0 |

El verde se segmenta; el filtro posterior lo rechaza. Bajar 600 no corrige estos cuadros. Debe verificarse si cada marcador está antes o después del cruce. La propuesta es comprobar asociación geométrica con la rama/intersección usando la posición de cada componente, en lugar de quitar la validación de negro y aceptar todo verde visible.

### Doble verde que se ejecutó como simple

| Cuadro | Segundo crudo | GS enviado |
|---|---:|---|
| 1693 | 83,210 | 2, derecha |
| 1694 | 83,251 | 3, doble |
| 1694–1702 | 83,251–83,559 | 3, doble |
| 1703–1706 | 83,599–83,719 | 1, izquierda |

El primer cuadro solo ve un contorno suficiente. Al siguiente aparecen dos. La maniobra Teensy empieza hacia 83,220 s y su intervalo programado registra +46,3° de rumbo: unos +2,3° durante el avance y +44° en el giro. Es consistente con ejecutar el primer GS2 y no el GS3 que llega 41 ms después.

El fuente disponible hace re-chequeo inmediato, luego avanza 800 ms y gira 45°, sin reconsiderar el doble durante ese avance. El problema en este caso es la decisión temprana y su compromiso, no que el motor no alcance 180°.

Comparación: los dobles de los cuadros 1853 y 6952 sí produjeron aproximadamente −181,5° y −182,3° durante sus secuencias programadas. La media vuelta funciona cuando esa maniobra es la que se ejecuta. En el doble de 1853, luego se pierde la línea: completar 180° desde una entrada oblicua más un avance fijo no garantiza quedar sobre la rama de regreso.

### Verde de un solo cuadro

Cuadro 6698: GS1 con 601 píxeles, apenas supera 600. Los cuadros anteriores tienen 1003 y 849 píxeles pero fallan la franja negra (0,52% y 21,14%); solo el último pasa (76,57%).

La Teensy sí reacciona a ese cuadro aislado. Por eso exigir ciegamente tres cuadros idénticos eliminaría un verde que actualmente logra ejecutar. Hay que acumular evidencia del mismo marcador durante su aproximación y resolver el tipo con geometría, sin exigir tres GS finales consecutivos.

### El supuesto exceso de giro de la bajada

La secuencia de 327,300 s acumula aproximadamente −68,6° de rumbo, pero no son −68,6° de giro programado:

- Durante los 800 ms de avance recto el rumbo cambia aproximadamente −25° (el valor depende de la frontera de lectura).
- La integración del giroscopio Z en ese avance es aproximadamente +1,9°; las medianas de RPM son FL20/FR19/BL20/BR20 y las consignas son 20/20.
- Durante el giro posterior: rumbo ≈−43° y giroscopio ≈+44,4°, con convención de signo opuesta.
- El pitch cambia aproximadamente de −16° hacia el llano.

No hay evidencia para achicar ese giro 25°. Existe una inconsistencia del rumbo absoluto durante la transición de pendiente. Posibles causas incluyen fusión/orientación o perturbación magnética; esta grabación no permite distinguirlas. Conviene usar giroscopio, inclinación y visión para validar el rumbo antes de concluir que hubo exceso físico.

## Recuperaciones: ángulo enviado frente a giro medido

El `angle` es un comando normalizado del protocolo. No es un pedido de girar esa cantidad de grados físicos. En seguimiento también controla curvatura; durante GS4 lleva el rumbo visual utilizado para elegir el pivote.

En el fuente disponible el objetivo de recuperación es 28° + 0,22 × |rumbo|, limitado a 35–58°. Por eso enviar aproximadamente 70° produce un pivote de unos 43°, no uno de 70°.

Se localizaron 22 episodios GS4. Cuatro pasan a búsqueda GAP. Se midieron 17 pivotes completos y uno final interrumpido; el último se excluye de las comparaciones de éxito porque el robot se detuvo y luego cambió el rumbo con ruedas sin movimiento.

| Cuadro dentro del pivote | Inicio crudo | Comando Pi | Giro yaw medido | Integración gyro Z |
|---|---:|---:|---:|---:|
| 449 | 27,155 s | −55° | +40,6° | −41,2° |
| 2429 | 116,750 s | +72° | −44,5° | +45,3° |
| 2808 | 131,380 s | −69,9° | +43,6° | −43,8° |
| 3040 | 141,770 s | −72° | +43,5° | −43,5° |
| 3629 | 172,775 s | −63° | +41,7° | −42,8° |
| 4076 | 194,660 s | −66° | +42,2° | −43,4° |
| 4532 | 220,225 s | +77,9° | −45,5° | +45,6° |
| 4664 | 227,885 s | −42,9° | +40,7° | −41,2° |
| 5378 | 261,115 s | −90° | +47,3° | −48,6° |
| 5892 | 293,115 s | −72° | +43,8° | −45,3° |

El signo opuesto entre yaw y gyro corresponde a sus convenciones. Las magnitudes concuerdan en estos pivotes. La tabla completa está en `pivotes_medidos.csv`.

### Falla comprobada: soltar sin recaptura visual

Episodio cuadro 2793, 130,732 s:

- GS4 primero pide retroceso y espera ACK.
- Se decide derecha y se envía −69,9°.
- El pivote gira +43,6°, coherente con el objetivo disponible en fuente.
- Cuadro 2829, 132,099 s: se suelta GS4 y se envían GS0/ángulo 0 aunque todavía no hay recaptura válida.
- Cuadros 2830–2861: `recup-cooldown-recto`. La máscara negra cae desde 480 píxeles hasta unos pocos.
- Cuadros 2862–2869: negro exactamente cero y aun así GS0/ángulo 0.
- El CSV muestra consignas 32/32 y RPM delanteras cercanas a 32–36 durante la salida. Por tanto, el robot efectivamente sigue avanzando.
- Último cuadro antes de la interrupción: 2869, 133,462 s, sin línea.

La recuperación termina con un reloj de aproximadamente 1,35 s; después el bloqueo evita otro episodio y fuerza recto cuando no hay línea conectada. Falta validar éxito al salir. La función `COMPLETAR_GIRO` solo actúa con determinada forma de cinta transversal (F), durante una ventana de 0,8 s y un máximo de 0,45 s; no resuelve todos los casos de cinta parcial/no conectada.

### Falla con elección de lado cuestionable

Episodio 5362, 260,464 s: el log registra memoria lateral izquierda, luego `SIDE_CHECK ... FLIP_APLICADO` a derecha y un rumbo próximo a +90° en la convención del clasificador; el comando de protocolo resulta −90°. Se mide pivote derecho de unos 47,3°. Tras él, los cuadros 5402–5425 muestran suelo sin recapturar línea y termina habiendo una interrupción.

Está probado que se aplicó el cambio de lado y que ese intento no recuperó. La imagen frontal no demuestra por sí sola que girar al otro lado habría funcionado: no se debe invertir todos los SIDE_CHECK. Se necesita contrastar conectividad de la rama y evolución durante el giro, especialmente cuando la decisión contradice memoria estable.

### Recuperaciones que conviene preservar

- Episodios GAP alrededor de cuadros 941 y 6383: la cinta reaparece desde arriba, se conecta y vuelve el control normal.
- Pivotes alrededor de cuadros 434 y 5877: el mismo sector de pista tiene giros de unos 41–44° y recaptura posterior visible.
- `COMPLETAR_GIRO` sí se activa en algunos codos: hay 29 cuadros con `recup-completa-giro`; no corresponde quitarlo globalmente.

## Propuesta de resolución acotada

### 1. Resolver el tipo de verde antes de comprometer la maniobra

Conservar el rango LAB y el comportamiento de los casos confirmados. Mantener un candidato asociado al mismo marcador mientras se aproxima. Al aparecer un simple potencial con otro componente entrando, reducir avance y dar una ventana breve a completar geometría. Permitir que doble confirmado tenga prioridad antes de iniciar el giro. Una vez iniciado el giro, congelar la decisión y no reinterpretar el mismo marcador como un verde nuevo. Terminar con confirmación de línea recapturada antes de aceptar otra marca.

Punto de partida a validar: ventana máxima de 80–120 ms (2–3 cuadros a la frecuencia medida), con tiempo real y límites de desplazamiento. Es propuesta, no un valor demostrado. Debe conservar el caso 6698 de un GS aislado usando evidencia previa del candidato.

Doble: verificar dos componentes suficientemente grandes y separados por la línea pertinente. Contar contornos y comparar un centroide global permite transiciones simple→doble→simple que no representan tres instrucciones distintas.

### 2. Corregir la geometría del filtro de verde, sin aceptar todos los rechazos

Analizar la posición de cada componente verde respecto de la rama negra y la intersección. La comprobación debe moverse con el marcador y la perspectiva. Reproducir primero sobre los casos rechazados y los verdes válidos de esta corrida. Mantener el rechazo de marcas que ya quedaron después del cruce o no pertenecen a la ruta.

No ampliar LAB, bajar el área o eliminar la condición del negro como arreglo general: esos cambios no atacan la causa mostrada y pueden introducir órdenes falsas.

### 3. Cambiar únicamente la salida fallida de recuperación

Conservar la clasificación, retroceso y pivote inicial en los casos que recapturan bien. Al recibir fin de pivote, decidir con la imagen:

- Línea conectada y orientación coherente durante varios cuadros: devolver seguimiento como hoy.
- Rama visible todavía transversal/diagonal baja: completar el mismo giro lentamente, con límite angular y temporal, validando que la rama se acerque a alineación.
- Sin línea: detener el avance. Hacer búsqueda corta y acotada según el último lado válido, o terminar detenido si no aparece. No convertir máscara vacía en avance recto durante el bloqueo de una recuperación lateral.

Mantener por separado la búsqueda recta de GAP y las excepciones explícitas de rampa, para no romper las dos recapturas GAP y la transición de cresta que sí se observaron funcionando.

### 4. Revisar SIDE_CHECK y rumbo sin ajustar el motor por anticipado

Cuando un cambio de lado contradice memoria reciente, exigir evidencia de rama conectada o frenar para confirmar. Verificar ambos lados sobre los cuadros del episodio 5362. No invertir globalmente ni aumentar todos los pivotes.

Validar rumbo de la IMU con giroscopio e inclinación al bajar. El exceso aparente de 25° no justifica modificar 45° a 20° ni retocar el PID.

## Validación necesaria para aceptar una futura corrección

1. Reproducir detector de verdes en estos mismos 7.927 cuadros: conservar las marcas válidas, resolver el doble 1693/1694 y preservar la detección aislada 6698.
2. Verificar en replay que las salidas fallidas 2793, 4196, 4517 y 5362 no reciban avance ciego cuando no hay recaptura; conservar GAP 941/6383 y recuperación 434/5877.
3. La imagen de un replay no cambia cuando el nuevo control decide otra maniobra: el replay permite validar reglas, no afirmar que el robot completará la pista. Hace falta una nueva pasada física.
4. En la próxima captura agregar GS recibido, acción activa, objetivo de pivote, causa de fin (ángulo/tiempo/STOP), ACK y tiempos de maniobra. Es instrumentación propuesta; aún no se implementó.

## Archivos de evidencia

- `evidencia_principal.jpg`: secuencias resumidas de los casos principales.
- `verdes_0.jpg`, `verdes_1.jpg`, `verdes_2.jpg`: todos los encuentros candidatos de verde agrupados.
- `verdes_filtros.csv`: resultado por cuadro de cada condición.
- `recup_0.jpg`, `recup_1.jpg`, `recup_2.jpg`: antes/durante/después de todos los episodios de recuperación.
- `paradas.jpg`, `paradas.csv`: cuadros previos a interrupciones largas; corroborar con el log, no equiparar automáticamente toda pausa a una salida.
- `eventos.csv`, `frames_sincronizados.csv`, `pivotes_medidos.csv`: decisiones y cruce temporal.
- `maniobras.csv`: desplazamiento neto en ventanas que incluyen maniobra y seguimiento posterior. NO usar esa columna como ángulo puro del pivote; para eso está `pivotes_medidos.csv` y los intervalos específicos de este informe.
