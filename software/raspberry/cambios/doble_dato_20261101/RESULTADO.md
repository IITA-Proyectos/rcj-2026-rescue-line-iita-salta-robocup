# Dobles verdes: dato de Raspberry, separado del movimiento

Prioridad indicada por el usuario: clasificar correctamente y enviar el dato correcto; no modificar el giro ni el plateado en esta etapa.

Se descargaron y verificaron video,log,17296 PNG originales,cuadros.csv,parametros y programas de la prueba114747. Archivo completo SHA256 93f0b6f8aeb7ab203e40256f076da03bdcfc1d0c5d7e0d51445c05438cab4aee. Es VERDE-SOMBRA-1, main ecdeaa4d6b2c5f8da832b19b9d5f8c5b7357e3333541db13e280c656fb825186. El usuario reporta funcionamiento favorable de simples,rampa y recuperaciones; los dobles requieren correccion de dato. El plateado se pospone por indicacion posterior.

Se revisaron las siete pasadas de doble en secuencias temporales,aproximacion,salida y estados GS. En cuatro sale GS2 antes de GS3:41,93,86 y43ms de diferencia. En tres empieza directamente con GS3. Se ven cambios posteriores de3 a1 y oscilaciones; eso no debe convertirse en otra clasificacion de marca dentro del mismo encuentro. No se usa el angulo de Raspberry como si fuera yaw real. No hay CSV de Teensy de esta prueba para acreditar que accion fue aceptada ni cuanto giro.

| Evento | Inicio AVI | Primer dato anterior | Primer GS3 | Demora anterior | Clip |
|---:|---|---:|---:|---:|---|
| 7 | 02:50.35 | 3 | f3408 | 0 ms | [Ver clip](clips/doble_07_02m50s.avi) |
| 14 | 06:21.65 | 2 | f7635 | 41 ms | [Ver clip](clips/doble_14_06m21s.avi) |
| 17 | 06:53.15 | 3 | f8264 | 0 ms | [Ver clip](clips/doble_17_06m53s.avi) |
| 21 | 08:02.65 | 2 | f9656 | 93 ms | [Ver clip](clips/doble_21_08m02s.avi) |
| 24 | 08:33.35 | 3 | f10268 | 0 ms | [Ver clip](clips/doble_24_08m33s.avi) |
| 31 | 11:50.65 | 2 | f14216 | 86 ms | [Ver clip](clips/doble_31_11m50s.avi) |
| 34 | 12:29.35 | 2 | f14989 | 43 ms | [Ver clip](clips/doble_34_12m29s.avi) |

## Correccion local DOBLE-DATO-1

El filtro de verdes existente sigue determinando si hay una marca aceptable. Solo entonces se comprueba el par desde fila70,para ver el segundo cuadrado antes de que entre completamente a la ROI80 del detector simple. No se aceptan dos manchas arbitrarias: area>=120 cada una,ancho>=6,alto>=5,centros en lados opuestos del centro negro con margen5px,negro inmediatamente encima de cada componente >0,32 y solapamiento vertical>=5 filas. Se usa el rango de sombra ya validado. Si existen ambos,GS3 tiene prioridad en ese mismo primer aviso; no se espera a enviar un simple antes.

Una vez confirmado el par,se conserva la identidad de doble durante esa marca aunque uno de los cuadrados salga primero. Hay un maximo de1s sin renovar la confirmacion del par y se tolera un hueco de ausencia de hasta0,18s; pausas>0,5s y estados prioritarios borran memoria. Un nuevo positivo sin par no se convierte en doble si no habia confirmacion previa. No se modifica la maniobra de motores.

Replay de la prueba: siete dobles con GS3 desde el primer positivo y sin degradarse a1/2 durante el encuentro;31 eventos simples conservados. Se revisan tambien los63133 cuadros de seis grabaciones anteriores,con el detector VERDE-SOMBRA-1 como entrada: los intervalos de control de verdes posteriores al cruce siguen rechazados. Se inspeccionaron visualmente las siete agrupaciones anteriores donde un dato simple pasa a doble; corresponden a pares visibles o a la salida de un par ya confirmado. Hay seis pruebas sinteticas de par temprano,simple,marca rechazada,ocultamiento,huecos,prioridades y negro superior. Compilacion correcta.

Se valida la CLASIFICACION y el dato que el candidato produciria, no la recepcion fisica ni el resultado de la media vuelta. Algunos eventos ya arrancaban enGS3 antes del cambio y el usuario reporto falla: esa parte de ejecucion queda separada y no se presenta como resuelta por este filtro. Una trayectoria nueva requiere otra grabacion.

Estado: INSTALADO y verificado el 01/11/2026. Respaldo /home/iita/Desktop/respaldo_doble_dato_20261101_123606. Compilacion y prueba sintetica remota correctas; hashes local/remoto coinciden. Main SHA256 66170c4620d1d30108ef71ec6cd2e1905f74dfc72673397bf8f3af63bc7d9397; helper SHA256 436e90359ad0f00ba8c4108914a292e66215831a91c5d55ad527f748c0d2b80f. No se reinicio el proceso del robot: requiere nueva ejecucion para cargar DOBLE-DATO-1. Se mantienen los detectores de sombra y de rampa y la recuperacion actuales.

Los clips conservan20FPS del AVI original y estan limitados antes de una pausa de sesion para no mostrar una recolocacion como si fuera salida autonoma. Los tiempos visibles son del AVI; no del reloj real de captura. El video completo permite revisar el contexto.

- [Video completo nuevo](../pista_verde_sombra_20261101_114747.avi).
- [Comparacion de datos por cuadro](doble_color_prioridad.csv).
- [Resumen de las siete pasadas](resumen_dobles.csv).
