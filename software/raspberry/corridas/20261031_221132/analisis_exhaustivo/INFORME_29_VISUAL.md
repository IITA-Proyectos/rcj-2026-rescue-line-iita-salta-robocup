# Revision visual y cruce de las 29 recuperaciones

Esta revision reemplaza la interpretacion rapida anterior: recapturar cinta no significa terminar estable una recuperacion ni superar la curva siguiente. No se atribuyen todas las fallas a una misma causa.

## Archivos y versiones corroboradas

- Video revisado: pista_reenganche_20261031_221132.avi, 31/10 a las 22:11, 7420 cuadros, con crudo y registro de ordenes. main SHA256 991df6bf36ce29d61457df8e46a9a67e6ab7b96c9f3d911a3d1dd6051f20e098; helper SHA256 7beb66b2a11786f20fba0ab512f9ccae0149d2bda1cddb3e77d982b4cefc0845. Corresponde a RECUP-REENGANCHE-2.
- La corrida posterior iniciada por servicio a las 22:19 tambien declara RECUP-REENGANCHE-2. Su log dice Video y Crudo vacios: no hay imagenes de esa corrida para contrastar su movimiento visualmente. El nombre de version coincide; ese log por si solo no acredita todos los archivos o el firmware compilado.
- El video anterior de las 21:36 con 69 episodios corresponde a RECUP-GEOMETRIA-1, main SHA256 62a01b4bbc9b8cc82e6fd2abc548f8826e774b58d14942ccbc16e12602c2ee53: entre esos dos videos SI cambio el programa.
- RECUP-REENGANCHE-3 esta preparado localmente; el intento de transferencia fallo y no se lo cuenta como instalado.
- No hay CSV de ruedas/encoders/yaw de esta prueba. La tabla de ordenes acredita lo que registro el envio de Raspberry; no acredita recepcion de cada trama ni giro real de las ruedas. La Raspberry actualmente no responde en la IP conocida, por lo que no se verificaron archivos nuevos posteriores a los descargados.

## Alcance real de la revision

Se revisaron visualmente 50 laminas temporales, con 2287 posiciones de imagen (puede haber repetidas entre ventanas), muestreando un cuadro de cada dos y agregando cambios de accion. Se midieron todos los cuadros de esas ventanas: 4282 registros, 4162 cuadros distintos. Las ventanas incluyen aproximacion, todo GS4 y hasta cinco segundos reales despues, limitadas por el siguiente episodio o cambio de sesion. En las laminas se ven las ordenes GS/angulo/quien y el numero de cuadro.

Esto es una revision de las 29 secuencias con todas sus transiciones de accion, no una afirmacion de haber inspeccionado visualmente los 7420 cuadros uno por uno. Tampoco una recaptura en cinco segundos certifica toda la pista. Los tiempos de esta tabla son del AVI, a 20 FPS. Las duraciones fisicas aproximadas se calculan por t de cuadros.csv; no hay que usar la escala temporal del AVI como reloj del robot.

## Hallazgos principales

### 1. El reenganche nuevo actua solo en tres episodios; no explica por si solo todas las salidas

En esta grabacion aparece recup-guard-reenganche en 1,12,25. El 1 gira hacia el fragmento izquierdo durante 11 cuadros, unos 0,33 s entre primer y ultimo envio, y vuelve al seguidor. El 25 primero agota el complemento derecho y luego invierte hacia el fragmento izquierdo durante 23 cuadros, unos 0,70 s, y vuelve al seguidor. En ambos hay oscilacion visible al devolver el control. El 12 tambien devuelve cinta, pero se detiene por el cierre temporal explicado abajo.

Las otras 26 recuperaciones no reciben la orden SEARCH nueva. Sus diferencias de resultado no pueden atribuirse directamente a un giro SEARCH que no se envio. Eso no demuestra ausencia de cualquier efecto indirecto o diferencia fisica: las entradas, posiciones y luminosidad no son identicas y no hay medicion de ruedas.

### 2. Mismo codo izquierdo: episodios 5 y 29, 00:42,10 y 06:03,05

Ambos llegan despues de cruzar GAP y perder la curva inmediata. Eligen izquierda (+36,8 y +41,4 de protocolo), retroceden y pivotan. Al soltar GS4 no hay componente conectada; la cinta queda al borde derecho y se aleja durante el complemento izquierdo +85. Se termina en STOP f905 y f7323.

En los dos la historia congelada es exactamente side=0,left=9,right=0. El minimo de rama persistente es 12 observaciones. Por eso el reintento hacia el fragmento NO se habilita, aunque el lado elegido por el clasificador sea izquierda. Es un bloqueo logico verificable; no es evidencia de que el robot hubiera girado una cantidad concreta de grados.

El episodio 17 es un control util: tambien sale del mismo tipo de GAP y elige izquierda. Su historia tiene left=13,right=0 y al soltar GS4 ya vuelve a haber cinta conectada, por lo que el seguidor puede continuar. Segun el ultimo fuente Teensy disponible, los objetivos iniciales de 5,17,29 quedan todos en aproximadamente 35 grados por el minimo impuesto. Un objetivo teorico igual no da una pose final igual; esto no justifica aumentar globalmente el giro.

### 3. STOP con cinta recuperada: episodio 12, 01:48,55

La busqueda izquierda empieza en f2144 y vuelve al seguidor en f2157. Desde ahi hay linea conectada, pero el reloj de un segundo sigue corriendo. En f2172 vence y envia GS19.

| Cuadro | Cinta conectada px | Error cercano | Diferencia lejana-cercana | Orden registrada |
|---:|---:|---:|---:|---:|
| 2170 | 3065 | +0,506 | -0,600 | -48,4 |
| 2171 | 3312 | +0,331 | -0,550 | -30,3 |
| 2172 | 3258 | +0,175 | -0,519 | 0, GS19 |

El error cercano mejora, pero la condicion de orientacion <=0,50 no se cumple y no se acumulan tres cuadros centrados. Se esta confundiendo cinta todavia en acomodo con cinta perdida. La revision 3 preparada modifica este caso: al vencer el plazo permite entregar al seguidor si hay tres cuadros seguidos observables con tolerancia de seguimiento. Su replay cambia solo f2172 del episodio 12 en las ventanas de esta prueba. Eso demuestra seleccion del caso, no prueba la trayectoria fisica futura.

### 4. GAP correcto con mala transicion a la curva

Los cinco GAP de esta grabacion cruzan y vuelven al seguimiento: episodios 4,7,16,21,23. En tres, la curva inmediatamente posterior vuelve a perderse:

| GAP | Recupera en cuadro | Nueva perdida | Tiempo real hasta nueva perdida |
|---:|---:|---:|---:|
| 4 | 803 | 843, episodio 5 | 1,520 s |
| 7 | 1227 | 1261, episodio 8 | 1,269 s |
| 16 | 3003 | 3039, episodio 17 | 1,379 s |

No son tres decisiones GAP incorrectas. Se vuelve al control por centroide y se llega a la curva con desplazamiento y ordenes grandes. Se observan magnitudes de 80-88 antes de perder la conexion. Otros encadenamientos tambien obligan a distinguir recaptura de salida estable: 8 ->9, 13 ->14 y 17 ->18. En 28 se recupera el codo, se atraviesa la zona de GAP por seguimiento y se termina perdiendo la curva que dispara 29; alli no se envia GS18 entre los dos episodios.

### 5. Los complementos y el seguidor explican parte de la oscilacion

Hay tres fuentes diferentes que pueden terminar imponiendo un giro: el pivote de GS4 en Teensy; COMPLETAR_GIRO ante cinta transversal conectada; y RecoveryGuard ante falta de recaptura. No deben confundirse en el inventario.

COMPLETAR_GIRO actua en 3,6,11,15,20,28 con orden -85. El complemento de RecoveryGuard actua en 5,24,25,26,29; en 24 y26 dura solo dos cuadros. La busqueda nueva actua solo en 1,12,25 y manda +85 en los tres.

El programa conserva el seguidor por centroide (CTRL por defecto atan2), no un PID nuevo. Tras recaptura aparecen inversiones rapidas, por ejemplo en 12: +48 al volver la cinta, luego -67, -30 y STOP. En 1 y25 tambien aparece el cambio de + a - durante el acomodo. El criterio de dos formas A/D del cierre anterior no mide centrado: una A puede quedar muy lateral. El seguidor normal usa informacion distinta a la geometria de dos bandas que la proteccion usa para aprobar el cierre.

En el ultimo fuente Teensy disponible, un GS0 con +/-85 normaliza steer a aproximadamente +/-0,944 y alcanza el umbral de pivote 0,92. Ademas entra en la rama de curvas cerradas LINE_FRENO_STEER=0,70, con LINE_FRENO_VEL=55; el pivote inicial GS4 usa RECUP_GIRO_VEL=35. Son objetivos del fuente disponible, no RPM medidas de esta corrida ni prueba del binario cargado. Una orden de Raspberry de 85 NO significa 85 grados de yaw. Reducir solamente speed en la trama Pi tampoco regula la velocidad normal de linea: esa rama calcula su propia velocidad en Teensy.

### 6. El episodio 27 no es el mismo fallo de un codo bien visible

A 05:40,75 queda muy poca cinta util; tras retroceder la imagen muestra principalmente piso. La historia izquierda hace que al agotarse la ambiguedad se mande izquierda +35. No aparece fragmento reciente suficiente para el reenganche y la proteccion detiene. Hay que revisar la salida anterior y la validez temporal de la memoria, no habilitar un giro indefinido sobre piso sin linea. El video no permite excluir toda manipulacion externa en la entrada; no se afirma que la causa mecanica este demostrada.

## Inventario de las 29 recuperaciones

En todos los casos se revisaron aproximacion, espera del retroceso, decision y salida. Las observaciones detallan lo que se ve dentro de la ventana y el encadenamiento inmediato. Los angulos son de protocolo, con negativo derecha y positivo izquierda; no son yaw medido.

| Episodio | Inicio AVI | Decision | Angulo | Resultado observado | Detalle |
|---:|---|---|---:|---|---|
| 1 | 00:08.45 | Derecha | -61.0 | Reenganche con oscilacion | El pivote derecho pierde conexion; 0,33 s de busqueda izquierda recuperan cinta. Alterna +54/-65 antes de estabilizar y continuar. |
| 2 | 00:17.50 | Izquierda | +58.1 | Recupera y continua | Izquierda; vuelve a cinta y sigue la curva con correcciones alternantes. No interviene la busqueda nueva. |
| 3 | 00:33.40 | Derecha | -66.6 | Recupera; encadena GAP | Derecha; cinta transversal al salir. COMPLETAR_GIRO manda -85 y vuelve al seguidor; despues llega al GAP 4. |
| 4 | 00:38.05 | GAP | +0.0 | GAP cruzado; salida fragil | GS18 recto cruza y declara recuperado en f803. La curva inmediata se pierde y dispara 5 en f843. |
| 5 | 00:42.10 | Izquierda | +36.8 | STOP sin reenganche | Izquierda +36,8. Cinta queda hacia el borde derecho; complemento +85 la pierde. Evidencia izquierda 9 no alcanza 12: no hay busqueda hacia fragmento. |
| 6 | 00:54.70 | Derecha | -59.3 | Recupera; encadena GAP | Derecha -59,3; COMPLETAR_GIRO breve -85. Cinta vuelve y sigue al GAP 7. |
| 7 | 00:59.35 | GAP | +0.0 | GAP cruzado; salida fragil | GS18 recto recupera en f1227; la curva inmediata se pierde y dispara 8 en f1261. |
| 8 | 01:03.00 | Izquierda | +64.3 | Recaptura; otra perdida despues | Izquierda +64,3; entrega al centroide con -64,2. Vuelve a seguir, pero pierde el siguiente codo y dispara 9. |
| 9 | 01:09.45 | Derecha | -35.0 | Decision tardia; recupera | AMBIGUA unos 0,95 s; rama previa fuerza derecha -35. Luego aparece cooldown recto con linea transversal; finalmente recaptura. |
| 10 | 01:20.40 | Derecha | -57.9 | Recupera y continua | Rama previa confirma derecha -57,9 tras ambiguedad; recaptura con cambios de signo y continua el zigzag. |
| 11 | 01:27.65 | Derecha | -70.4 | Recupera con complemento | Derecha -70,4; COMPLETAR_GIRO -85 sostenido y oscilacion al volver al seguidor; sigue con linea visible. |
| 12 | 01:44.70 | Derecha | -47.0 | Reengancha pero STOP indebido | Derecha -47; busqueda +85 recupera cinta en f2157. El limite de un segundo termina en GS19 f2172 con 3258 px conectados. |
| 13 | 02:00.25 | Derecha | -12.0 | Recaptura; otra perdida despues | Rama previa cambia el lado y manda derecha -12; tras cooldown vuelve a cinta. Mas tarde pierde siguiente codo izquierdo y dispara 14. |
| 14 | 02:08.35 | Izquierda | +64.7 | Recupera y continua | Izquierda +64,7; tras tramo recto de cooldown vuelve al seguidor y continua curva. |
| 15 | 02:23.55 | Derecha | -59.8 | Recupera; encadena GAP | Derecha -59,8; COMPLETAR_GIRO -85 y varias inversiones de signo antes del GAP 16. |
| 16 | 02:28.15 | GAP | +0.0 | GAP cruzado; salida fragil | GS18 recto recupera en f3003; se pierde la curva inmediata y dispara 17 en f3039. |
| 17 | 02:31.90 | Izquierda | +46.5 | Recaptura; otra perdida despues | Izquierda +46,5; entrega al centroide -65,1, oscila, sigue la cinta y pierde siguiente codo derecho en 18. |
| 18 | 02:38.30 | Derecha | -58.4 | Recupera y continua | Derecha -58,4; pasa por cooldown recto con cinta transversal. Luego recaptura y continua el zigzag. |
| 19 | 02:48.20 | Derecha | -73.0 | Recupera y continua | Derecha -73; vuelve al centroide con +57 y cambios de signo; mantiene cinta en la salida revisada. |
| 20 | 02:56.10 | Derecha | -43.2 | Recupera con complemento | Rama previa derecha -43,2; COMPLETAR_GIRO -85. Vuelve al seguidor y continua. |
| 21 | 03:10.55 | GAP | +0.0 | GAP cruzado y salida seguida | GAP recto del puente; recupera en f3849 y mantiene cinta. Hay confirmaciones de perdida breves sin nuevo GS4. |
| 22 | 03:26.80 | Derecha | -59.6 | Recupera y entra a rampa | Derecha -59,6; devuelve al seguidor, corrige fuerte y mantiene linea al entrar en rampa. |
| 23 | 03:53.90 | GAP | +0.0 | GAP cruzado y salida seguida | GAP recto despues de rampa; recupera en f4745 y sigue linea hacia descenso. |
| 24 | 04:58.00 | Izquierda | +66.7 | Recupera; verde posterior | Izquierda +66,7; complemento guard +85 de dos cuadros. Sigue hasta verde derecho GS2; tras verde hay mascara vacia temporal, separado del cierre de recuperacion. |
| 25 | 05:18.20 | Derecha | -65.5 | Reenganche con oscilacion | Derecha -65,5; complemento -85 no recaptura, busqueda +85 de 0,70 s lo logra. Vuelve a oscilar y continua hasta otro codo. |
| 26 | 05:28.65 | Izquierda | +67.7 | Recupera con complemento breve | Izquierda +67,7; complemento guard +85 dos cuadros. Sigue la curva; mas adelante aparece otra perdida (27), fuera de la ventana principal de cinco segundos. |
| 27 | 05:40.75 | Izquierda | +35.0 | Sin cinta util; STOP | Entrada con orden +65 y cinta baja ya casi fuera. Tras retroceso se ve mayormente piso. Rama previa manda izquierda +35 tarde; no hay fragmento fresco y termina STOP. |
| 28 | 05:55.50 | Derecha | -71.3 | Recupera; encadena GAP | Derecha -71,3; COMPLETAR_GIRO -85. Vuelve a cinta, atraviesa hacia GAP y se pierde la siguiente curva en 29. |
| 29 | 06:03.05 | Izquierda | +41.4 | STOP sin reenganche | Repite 5: izquierda +41,4, complemento +85, cinta se aleja al borde derecho. Solo 9 observaciones izquierdas: no se habilita busqueda hacia fragmento. |

## Resolucion que se desprende de esta evidencia

1. Corregir el STOP con seguimiento ya recuperado (caso 12). La version 3 preparada tiene ese alcance; NO se la presenta como solucion de los otros tres STOP o de todas las oscilaciones.
2. Tratar 5 y29 como un patron separado de 1/12/25: rama izquierda coherente pero historia de nueve cuadros y fragmento posterior al lado contrario. Evaluar una autorizacion acotada con evidencia post-retroceso y fragmento reciente. Bajar globalmente 12 a9 cambiaria tambien otras decisiones y requiere validacion; no esta justificado hacerlo a ciegas.
3. En GAP -> curva y entrega del pivote al seguidor, validar posicion cercana, orientacion y continuidad, no solo negro conectado o dos A/D. :codex-annotation{index="1"} La observacion previa del usuario sobre plateado que puede aparecer negro sigue siendo relevante: ese criterio debe limitarse al cierre de linea y respetar la prioridad del sensor de plateado de Teensy; estas pruebas no validan una entrada a rescate ni un cambio del detector de plateado.
4. Coordinar los complementos dentro de una misma fase de cierre, con el ACK de fin de pivote como evidencia fisica disponible y objetivos de seguimiento explicitos. No aumentar todos los angulos ni retocar todo el seguidor para resolver estos casos aislados.
5. Para atribuir sobre/subgiro a motores, registrar CSV de Teensy sincronizado en la siguiente prueba y comparar el mismo codo con entrada similar. La oscilacion visual y la alternancia de ordenes si estan demostradas; patinamiento, bateria y yaw real no estan medidos aqui.

No se cambio ni se subio codigo al hacer esta revision. Los resultados favorables del replay anterior eran preservacion de comandos sobre imagenes grabadas; no demostraban que la nueva maniobra fisica terminaria bien. Esta distincion corrige el alcance de lo afirmado antes.

## Evidencias para revisar juntos

- [Galeria temporal de los 29 episodios](galeria.html): las 50 laminas, con GS/angulo/accion por imagen.
- [Comparacion de los dos patrones repetidos](comparacion_patrones.jpg).
- [Todas las transiciones de accion](todas_acciones.csv).
- [Mediciones por cuadro](metricas_todos_cuadros.csv).
- [Dictamen por episodio](dictamen_29.csv).
- [Video original](../pista_reenganche_20261031_221132.avi).
