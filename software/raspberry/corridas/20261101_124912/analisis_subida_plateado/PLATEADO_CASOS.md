# Casos de plateado y lateral indicados por el usuario

Se revisaron cinco secuencias visuales, 24 posiciones temporales por secuencia, cruzadas con el CSV completo en esas ventanas. No se afirma inspeccion visual de cada cuadro. Las galerias plateado_765/784/788/798/807.jpg conservan referencia de cuadro, controlador y angulo.

| Momento indicado | Evidencia en la grabacion |
|---|---|
| 12:45 | La cinta llega oblicua a la banda plateada. La mascara pasa del extremo de cinta a fragmentos. GS4 desde 12:46.95; orden curva +49.8; posteriormente GS19 desde 12:49.45. No hay validacion de alineacion antes de declarar terminada la maniobra. |
| 13:04 | Ya esta en recuperacion desde 13:02.45; tras retroceder pasa de ambigua a GAP GS18 desde 13:03.40 hasta 13:05.05. En imagen hay banda plateada y restos de cinta, no evidencia suficiente para tratarlo como un gap normal. |
| 13:08 | Caso lateral diferente: codo a la derecha, angulo -30 a -42 inicialmente, despues llega -87.6 cuando la linea ya sale por el borde. GS4 desde 13:09.30 y orden curva -74.9. No equivale a una entrada recta al plateado. |
| 13:18 | Final de cinta oblicuo a la banda, GS4 desde 13:17.55; orden curva +66.3; luego GS19 desde 13:20.10. |
| 13:27 | Final de cinta oblicuo a la banda, GS4 desde 13:26.40; orden curva +64.5; despues aparecen ordenes de reenganche -85 con poca/ninguna cinta util visible. |

Los angulos son datos del protocolo de la Raspberry, positivos izquierda, negativos derecha. No son grados fisicos de giro ni prueba de ejecucion/recepcion de la Teensy.

El usuario confirma que la maniobra real de la Teensy consiste en retroceder, girar a la izquierda y terminar. Esta observacion tiene prioridad sobre inferencias a partir del fuente local. No hay CSV Teensy de esta corrida que permita reconstruir yaw o ruedas. El fuente local contiene tambien una correccion al confirmar plateado (deshacer parte de una recuperacion o giro derecho sin recuperacion), pero no se afirma que esa parte se ejecute en el firmware usado.

Hallazgo comun: terminar la maniobra no equivale a estar orientado y centrado. La camara no certifica ese estado antes de la entrada. Ademas, en la banda plateada el umbral de negro produce fragmentos; perseguirlos como si fueran la linea puede introducir nuevas decisiones de recuperacion/GAP. No se propone cambiar el reconocimiento APDS que ya reconoce el material.

Resolucion propuesta: conservar la maniobra existente y agregar una fase de confirmacion por camara, coordinada con la Teensy antes de avanzar a rescate. Medir linea cercana para desplazamiento y dos bandas para direccion, con consistencia temporal; corregir mientras la linea siga siendo visible. Si ya no hay geometria valida, no declarar alineacion por tiempo cumplido ni perseguir un reflejo. Es necesario un intercambio de estados que impida que la Teensy inicie su avance antes de esa confirmacion; un cambio visual solo en la Raspberry no basta si el firmware continua automaticamente. La toma al plateado no debe confundirse con un gap ni con un codo normal sin evidencia de contexto. Sin ultrasonido.

Limitacion de grabacion: main.py llama a _grabar y _grabar_crudo dentro del lazo de linea; no graba de la misma forma la fase de rescate. Por eso todos los cuadros CSV figuran linea, mientras el log si contiene mensajes 241/entrada a rescate. silver=0 de camara no demuestra ausencia de lectura APDS. Hay saltos de tiempo real entre cuadros, especialmente al salir a rescate o al reiniciar, y no deben interpretarse como filmacion continua de los movimientos posteriores.

No se cambio ni instalo programa. Pendiente: preparar y verificar un cambio acotado con subidas rectas y recuperaciones exitosas como controles, y confirmar firmware actualmente cargado antes de modificar su protocolo.
