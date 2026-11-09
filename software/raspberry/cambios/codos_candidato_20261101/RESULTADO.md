# Preparacion local — codos pendientes, 01/11/2026

No instalado en Raspberry. La bateria esta cargando. Mantener separadas las pruebas: primero RECUP-REENGANCHE-3 (STOP con cinta recuperada), luego esta candidata para los codos izquierdos. No se reintento conexion durante la carga.

## Candidata 4: autorizar reenganche en el patron izquierdo aislado

Conserva la correccion 3. No modifica main.py, verdes, GAP, clasificador ni los umbrales de la decision principal. Cambia solo la autorizacion de un reintento en el punto donde el cierre anterior enviaria STOP:

- Si ya hay rama persistente fuerte, se conserva exactamente la autorizacion anterior.
- Si no la hay: al menos ocho observaciones unilaterales y como maximo una del lado contrario; la decision CURVA debe coincidir con ese lado; debe existir un fragmento lateral reciente y situado al lado contrario al giro inicial. El plazo maximo de edad del fragmento sigue en 1,5 s.
- Se usa el mismo reintento hacia fragmento, una sola vez, con limite de un segundo y cierre de version 3. No amplifica todos los giros ni baja el minimo general de doce observaciones.

El minimo de ocho es una tolerancia inicial de ensayo, no un umbral fisico universal estimado. Los dos casos observados tienen nueve. Debe probarse fisicamente y contrastarse con variantes cercanas.

Validacion: comparado con version 3, replay de las 29 recuperaciones cambia SOLO episodios 5 y29, exactamente en f905 y f7323: STOP -> busqueda derecha -85 hacia fragmento que quedo a derecha despues del giro izquierdo. Los otros episodios conservan sus acciones hasta la primera divergencia. Replay del video anterior de 69 episodios no cambia ninguna accion respecto de version 3 en las ventanas revisadas. GAP y verdes conservan sus bloques. Ocho pruebas verifican la busqueda, cierre, temporizador y rechazo de evidencia contradictoria, escasa o de lado incorrecto. Compilacion correcta.

La reproduccion termina de ser evidencia de trayectoria en cuanto cambia la primera orden. No se declara que el robot ya resuelva fisicamente estos codos. Falta probar repetidos izquierdos y derechos que antes funcionaban con video+crudo+CSV.

## GAP -> curva: diagnostico separado, sin cambios de movimiento

Se midio cada cuadro durante los primeros 1,65 segundos despues de los cinco GAP. Los tres problematicos salen con error cercano aproximado +0,54 / +0,68 / +0,62. Durante el acomodo aparece una curva/transversal, deja de verse cinta en la banda lejana y el centroide manda correcciones de magnitud 73–88, cambiando de signo antes de la perdida.

Se preparo una alarma de diagnostico: ya se vio cinta en banda lejana, despues falta esa banda tres cuadros, sigue habiendo componente conectada >=200 px y el seguidor pide magnitud >=60. En esta corrida marca solo los tres GAP problematicos (f802,f1226,f3003), no los dos con salida seguida (f3849,f4745). Las primeras alertas y tiempos estan en alertas_gap.csv, y todas las mediciones en diagnostico_salida_gap.csv.

Esta alarma localiza una fase candidata para intervenir; NO demuestra todavia que cierto giro, velocidad o rumbo la corrija. No se modifico el avance de GAP ni se aplico un giro fijo cuando falta banda lejana. La solucion requiere mantener la identidad del tramo saliente durante la curva y entregar al seguidor con posicion/orientacion sostenidas. Antes de tocar motores, hay que validar el detector contra los GAP de las corridas anteriores y registrar el movimiento real de Teensy. En el fuente disponible speed de la Pi no gobierna la velocidad normal de linea, asi que no se propone bajar ese campo como si frenara el robot.

## Orden de prueba

1. Instalar y probar version 3 para el caso de STOP con cinta ya conectada, sin mezclar excepciones nuevas.
2. Probar candidata 4 en codos izquierdos repetidos; comparar tambien controles derechos/izquierdos que ya salian. Registrar si realmente sigue la salida correcta o solo vuelve a la entrada.
3. Con esas pruebas, resolver el control en GAP -> curva; conservar el cruce GAP que funciona.
