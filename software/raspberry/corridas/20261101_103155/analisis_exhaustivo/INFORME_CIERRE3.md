# Prueba RECUP-REENGANCHE-3 del 01/11, 10:31

## Que se verifico

Video completo descargado: pista_cierre3_20261101_103155.avi, 8354 cuadros. Se descargaron tambien PNG originales, cuadros.csv, parametros, log y programas. SHA256 del archivo completo corrida_103155.tar: bd8a408196fd20623d94cc91b3e0cbb2226d231098eb589bdd130e4b0a0e24d5, igual al calculado en Raspberry. El log confirma RECUP-REENGANCHE-3. Helper SHA256 c3333b7e51f479cea041c656402438dc6a818f5d34ec4971f93ce0d910c9f52f. No se grabo CSV de Teensy; no se atribuyen RPM, patinamiento o yaw reales.

Se revisaron visualmente las 18 ventanas de recuperacion, en 31 laminas, con 1356 posiciones de imagen (un cuadro de cada dos mas cambios de accion). Se midieron 2453 cuadros distintos. Las ventanas cubren aproximacion, GS4 y hasta cinco segundos reales posteriores, cortadas por siguiente recuperacion o pausa de captura. Los tiempos del informe son del AVI a 20 FPS; las duraciones se calculan por t del crudo. No se afirma haber visto los 8354 cuadros uno por uno.

## Falla principal: codo derecho, episodio 6, 03:21,70–03:26,25

### Se cambia la identidad del fragmento

El programa elige derecha -67,4 y despues del pivote la cinta queda a izquierda. Esto se observa tambien en la mascara: f4072 tiene el fragmento con x cercano5,5; f4078 x5; f4082 x4; f4086 x3. Mientras tanto el complemento sigue imponiendo derecha -85.

Al desaparecer ese fragmento, remember_fragment no mantiene una identidad temporal: elige en cada imagen la componente negra mas baja que cumpla area >=60 y llegue a fila65. En f4094 acepta un trazo oscuro del borde/reflejo del piso a derecha, de 100 pixeles, con x149; en f4096 x139. Asi la memoria salta de izquierda a derecha. Al empezar SEARCH f4096, manda derecha -85 en vez de apuntar a la cinta izquierda original.

Esto se comprobo con la imagen y la mascara seleccionada, no solo por el signo del comando. Ver fragmento_elegido_E06.jpg: componente elegida en rojo. El cuadro demuestra que el nuevo trazo esta en el otro borde y no se siguio la misma componente. No se afirma que toda diferencia de apariencia sea un fallo global del umbral negro ni que el valor de yaw real este medido.

### El cierre sigue teniendo una carrera contra el reloj

La busqueda comienza f4096. No hay componente conectada hasta f4124 inclusive. En f4125 vuelve cinta conectada; solo 44 ms despues, f4126 manda GS19 porque ya pasaron 1,018 segundos desde el inicio de la busqueda.

| Cuadro | Conexion px | Error cercano | Diferencia lejana-cercana | Orden final |
|---:|---:|---:|---:|---|
| 4124 | 0 | — | — | -85, SEARCH |
| 4125 | 2774 | +0,881 | -0,588 | -47,4, centroide |
| 4126 | 3125 | +0,781 | -0,675 | 0, GS19 STOP |
| 4127 | 3611 | +0,606 | -0,700 | GS19 persistente |
| 4128 | 3953 | +0,356 | -0,588 | GS19 persistente |

Version3 requiere tres cuadros consecutivos aptos al vencer el segundo. El primero recapturado queda fuera de la tolerancia cercana de0,80; el segundo, fuera de orientacion0,65. Ademas ni siquiera existen tres cuadros recapturados antes del plazo. Por eso la excepcion que reparaba f2172 de la prueba anterior NO cubre este caso. El movimiento que sigue apareciendo despues del STOP puede incluir inercia/latencia; sin telemetria no se asigna una causa mecanica exacta.

Conclusion: no alcanza ampliar un umbral una vez mas. Hay que separar el tiempo maximo de busqueda sin cinta de una confirmacion breve cuando la cinta reaparece, conservando un limite total. Tambien hay que impedir que un parche oscuro de otro lado reemplace al fragmento seguido.

## Las otras fallas o limites de esta prueba

- GAP10, inicio04:16,30: cruza y vuelve al seguidor en f5166. Se pierde la curva inmediata y dispara11 en f5196, 1,157 segundos reales despues. Persiste el problema GAP -> curva, separado del STOP del codo6.
- Episodio15, inicio04:52,10: ya se observa madera/franja brillante y una esquina de cinta antes de GS4. Gira izquierda y sigue mostrando madera; luego busca derecha. Hay pausa/reinicio antes de un desenlace. No se lo cuenta como exito ni como un fallo corriente de un codo sobre pista blanca. El registro Pi permanece en linea; no hay lecturas del APDS para determinar lo que detecto el sensor de color.
- Episodio2: la captura se interrumpe en AMBIGUA/GS4, y reaparece otra sesion. El clasificador rapido antiguo lo etiquetaba GAP por ausencia de CURVE-LATCH; eso no acredita que se haya enviado GS18 en esa ventana. Queda corregido como interrumpido.
- Episodio18: el video termina con cinta no conectada tras girar. No hay salida grabada y no se clasifica como recuperacion exitosa.

Hay 14 episodios con recaptura visible en sus ventanas, uno que termina STOP, y tres con desenlace incompleto o fuera de pista/interrumpido (2,15,18). La recaptura no certifica la ruta completa: varios enlazan otra perdida mas adelante.

## Inventario de todas las recuperaciones

| Episodio | Inicio AVI | Angulo protocolo | Resultado | Observacion |
|---:|---|---:|---|---|
| 1 | 00:23.55 | -58.4 | Recaptura | Derecha -58,4; cooldown recto breve y centroide. Oscila al acomodarse, sigue hacia rampa. |
| 2 | 00:48.45 | +0.0 | Interrumpida | Termina la ventana en f987, aun AMBIGUA/GS4. Hay pausa de captura y reinicio de estado: no clasificar como GAP exitoso. |
| 3 | 01:40.25 | +0.0 | Recaptura recta | GS18 cruza interrupcion recta de rampa y recupera f2070; sigue hacia bajada. |
| 4 | 02:20.15 | +0.0 | Recaptura recta | Tras proteccion de bajada, la linea queda desplazada/no conectada. Espera AMBIGUA, usa GS18 y vuelve a linea f2872; continua hasta verde. |
| 5 | 03:02.60 | +63.3 | Recaptura | Izquierda +63,3; vuelve a cinta y llega a verde derecho. La mascara vacia despues del verde es otra fase. |
| 6 | 03:21.70 | -67.4 | STOP con cinta recien conectada | Codo derecho -67,4; complemento -85 y busqueda -85. La memoria cambia de cinta izquierda a trazo de piso derecho. Conecta f4125; en f4126 vence el segundo y manda STOP. |
| 7 | 03:48.95 | -12.0 | Recaptura; otro codo despues | Rama previa corrige a derecha -12; vuelve a cinta. Despues requiere izquierda en episodio8. |
| 8 | 03:56.95 | +62.5 | Recaptura | Izquierda +62,5; sigue la curva con oscilacion visible y conserva linea en la ventana. |
| 9 | 04:11.80 | -60.4 | Recaptura; GAP siguiente | Derecha -60,4; COMPLETAR_GIRO -85 seis cuadros; vuelve a cinta y pasa al GAP10. |
| 10 | 04:16.30 | +0.0 | Cruza GAP; pierde salida | GS18 recto vuelve a linea f5166; la curva siguiente se pierde 1,157 s reales despues y dispara11. |
| 11 | 04:19.75 | +60.8 | Recaptura; otro codo despues | Izquierda +60,8; vuelve al centroide y sigue hasta el codo derecho12. |
| 12 | 04:26.10 | -35.0 | Recaptura tras decision tardia | AMBIGUA cercana a un segundo post-retroceso; rama previa confirma derecha -35. Cooldown recto con transversal, luego centroide y sigue zigzag. |
| 13 | 04:36.90 | -70.0 | Recaptura; otro codo despues | Derecha -70; vuelve al centroide y sigue el zigzag hasta derecha14. |
| 14 | 04:44.15 | -12.3 | Recaptura | Rama previa derecha -12,3; COMPLETAR_GIRO -85 diez cuadros; vuelve a linea con oscilacion y llega a otra zona. |
| 15 | 04:52.10 | +53.2 | Fuera de pista; resultado interrumpido | Empieza ya sobre madera/franja brillante, gira izquierda +53,2 y sigue mostrando madera. Busca derecha -85, pero termina la sesion sin ver recaptura ni STOP. No usar como codo normal de pista blanca. |
| 16 | 05:38.00 | -58.2 | Recaptura | Repite entrada derecha hacia rampa -58,2; vuelve a linea y continua subida. |
| 17 | 06:25.30 | +0.0 | Recaptura recta | GS18 cruza GAP recto de rampa, recupera f7772 y sigue hacia bajada. |
| 18 | 06:55.55 | -73.1 | Video termina sin cierre | Derecha -73,1 tras marca verde; al soltar se pierde cinta. El archivo termina f8354 en mascara vacia. No hay desenlace grabado. |

## Siguiente correccion propuesta

1. Dar continuidad al fragmento del cierre: asociarlo con la cinta observada durante el giro y rechazar saltos a componentes del otro lado sin transicion visible. Cuando se pierde su identidad, conservar la ultima referencia por un plazo corto o detener; no sustituirla automaticamente por cualquier componente negra baja.
2. Separar BUSCAR de CONFIRMAR: el segundo limita la busqueda sin conexion; si reaparece cinta justo al vencer, permitir una ventana breve y acotada de confirmacion, sin prolongar giro ciego. Si vuelve a perderse o no se sostiene, detener. Los limites y el comportamiento de seguimiento deben probarse contra los casos de exito y las salidas transitorias anteriores.
3. Mantener separado GAP -> curva. La candidata4 de autorizacion de los codos izquierdos no corrige el cambio de identidad visto aqui y no corresponde subirla como solucion a esta prueba sin revisarla.

No se cambio ni se subio codigo durante este analisis. La siguiente implementacion debe verificar este caso nuevo y las grabaciones previas; un replay solo acredita la seleccion de ordenes hasta la primera divergencia, no el movimiento fisico que ocurriria despues.

## Evidencias

- [Video completo](../pista_cierre3_20261101_103155.avi).
- [Galeria de las 18 secuencias](galeria.html).
- [Fragmento seleccionado, original y mascara](fragmento_elegido_E06.jpg).
- [Resumen del fallo en cuadros](falla_codo_0326.jpg).
- [Todas las transiciones registradas](todas_acciones.csv).
- [Metricas de cada cuadro revisado](metricas_todos_cuadros.csv).
