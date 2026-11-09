# Revisión completa de las 69 recuperaciones — versión RECUP-GEOMETRIA-1

[Video original de la prueba](../pista_recuperacion_corregida_20261031_213650.avi).

Se descargaron y verificaron video, log y 18.331 imágenes originales. El hash del archivo completo coincide con el de Raspberry; el grabador declara cero imágenes perdidas. Los parámetros registran el main instalado con SHA256 62a01b4bbc9b8cc82e6fd2abc548f8826e774b58d14942ccbc16e12602c2ee53.

No se grabó CSV de Teensy en esta prueba, confirmado por el usuario. Se conocen las órdenes enviadas por Raspberry y las imágenes posteriores; no se conocen las órdenes recibidas, RPM, encoders o yaw reales de esta corrida. No se trasladan mediciones de ruedas de la corrida anterior como si fueran nuevas.

Se inspeccionaron seis momentos de cada episodio (414 imágenes en diez láminas) y se midió conectividad/forma de cinta en 3.530 cuadros posteriores. La ventana posterior se limita a dos segundos reales, al siguiente episodio o al cambio de sesión. Los tiempos del inventario son del AVI a 20 FPS; difieren del reloj real del crudo. Una recaptura en esta ventana no garantiza la ruta completa ni descarta una salida posterior.

## Resultado

- 53 episodios presentan recaptura visible dentro de la ventana revisada.
- 3 recapturan temporalmente y vuelven a perder conexión en esa ventana.
- 12 terminan en el STOP de protección sin recaptura: 11 codos (10 derechos y uno izquierdo) y un GAP físico mal clasificado como curva.
- 1 muestra búsqueda GAP sobre madera, sin reconexión en la ventana; es otro problema distinto a la repetición del codo.

La mayoría de las decisiones de rama funciona en esta grabación. No corresponde tratar los 69 episodios como fallas equivalentes ni contabilizar STOP como recuperación exitosa.

Las 13 intervenciones de RAMA_PREVIA (9/19/24/30/36/37/38/45/54/55/60/61/63) tienen recaptura visible. Las cinco de GAP_PREVIO (7/22/28/34/58) también reconectan, varias entrando rápidamente en la curva siguiente. Es evidencia física favorable a la corrección, aunque no hay una pasada idéntica de control para calcular una tasa causal de mejora.

## Inventario completo

| Episodio | Tiempo AVI | Cuadro inicial | Decisión | Intervención | Resultado observado |
|---:|---|---:|---|---|---|
| 1 | 00:22.95 | 460 | derecha | Base | Recaptura visible |
| 2 | 00:48.15 | 964 | GAP | Base | Recaptura visible |
| 3 | 01:47.60 | 2153 | izquierda | Base | Recaptura visible |
| 4 | 02:06.50 | 2531 | derecha | Base + complemento acotado | STOP sin recaptura |
| 5 | 02:22.35 | 2848 | izquierda | Base | Recaptura visible |
| 6 | 02:37.40 | 3149 | derecha | Base + completar giro | Recaptura visible |
| 7 | 02:41.75 | 3236 | GAP | GAP previo | Recaptura visible |
| 8 | 02:45.20 | 3305 | izquierda | Base | Recaptura visible |
| 9 | 02:50.90 | 3419 | derecha | Rama previa | Recaptura visible |
| 10 | 03:01.35 | 3628 | derecha | Base | Recaptura visible |
| 11 | 03:09.25 | 3786 | derecha | Base + completar giro | Recaptura visible |
| 12 | 03:17.55 | 3952 | GAP | Base | GAP sobre madera; no reconecta en la ventana |
| 13 | 03:30.05 | 4202 | derecha | Base | GAP fisico clasificado CURVA; termina STOP |
| 14 | 03:56.05 | 4722 | derecha | Base | Recaptura visible |
| 15 | 04:20.05 | 5202 | GAP | Base | Recaptura visible |
| 16 | 05:09.50 | 6191 | GAP | Base | Recaptura visible |
| 17 | 05:55.55 | 7112 | izquierda | Base | Recaptura visible |
| 18 | 06:15.00 | 7501 | derecha | Base + complemento acotado | STOP sin recaptura |
| 19 | 06:28.65 | 7774 | derecha | Rama previa | Recaptura visible |
| 20 | 06:36.35 | 7928 | izquierda | Base + complemento acotado | Recaptura visible |
| 21 | 06:52.65 | 8254 | derecha | Base + completar giro | Recaptura visible |
| 22 | 06:57.00 | 8341 | GAP | GAP previo | Recaptura visible |
| 23 | 07:00.40 | 8409 | izquierda | Base | Recaptura visible |
| 24 | 07:06.65 | 8534 | derecha | Rama previa | Recaptura visible |
| 25 | 07:17.25 | 8746 | derecha | Base | Recaptura visible |
| 26 | 07:25.05 | 8902 | derecha | Base + completar giro | Recaptura visible |
| 27 | 07:38.30 | 9167 | derecha | Base + completar giro | Recaptura visible |
| 28 | 07:42.85 | 9258 | GAP | GAP previo | Recaptura visible |
| 29 | 07:46.65 | 9334 | izquierda | Base | Recaptura visible |
| 30 | 07:53.00 | 9461 | derecha | Rama previa | Recaptura visible |
| 31 | 08:02.50 | 9651 | derecha | Base | Recaptura visible |
| 32 | 08:10.05 | 9802 | derecha | Base + completar giro | Recaptura visible |
| 33 | 08:22.10 | 10043 | derecha | Base + completar giro | Recaptura visible |
| 34 | 08:26.55 | 10132 | GAP | GAP previo | Recaptura visible |
| 35 | 08:30.20 | 10205 | izquierda | Base | Recaptura visible |
| 36 | 08:36.70 | 10335 | derecha | Rama previa | Recaptura visible |
| 37 | 08:47.00 | 10541 | derecha | Rama previa | Recaptura visible |
| 38 | 08:54.30 | 10687 | derecha | Rama previa + completar giro | Recaptura visible |
| 39 | 09:07.85 | 10958 | derecha | Base + complemento acotado | STOP sin recaptura |
| 40 | 09:31.15 | 11424 | derecha | Base + complemento acotado | STOP sin recaptura |
| 41 | 09:44.60 | 11693 | izquierda | Base + complemento acotado | STOP sin recaptura |
| 42 | 09:55.90 | 11919 | izquierda | Base | Recaptura visible |
| 43 | 10:00.70 | 12015 | derecha | Base | Recaptura transitoria; vuelve a perder conexion |
| 44 | 10:08.25 | 12166 | izquierda | Base | Recaptura visible |
| 45 | 10:13.60 | 12273 | derecha | Rama previa | Recaptura visible |
| 46 | 10:28.20 | 12565 | izquierda | Base | Recaptura visible |
| 47 | 10:33.05 | 12662 | derecha | Base | Recaptura transitoria; vuelve a perder conexion |
| 48 | 10:44.25 | 12886 | derecha | Base | STOP sin recaptura |
| 49 | 11:01.80 | 13237 | izquierda | Base | Recaptura visible |
| 50 | 11:13.50 | 13471 | derecha | Base + complemento acotado | STOP sin recaptura |
| 51 | 11:24.85 | 13698 | izquierda | Base | Recaptura visible |
| 52 | 11:29.85 | 13798 | derecha | Base | Recaptura transitoria; vuelve a perder conexion |
| 53 | 11:57.10 | 14343 | GAP | Base | Recaptura visible |
| 54 | 12:19.85 | 14798 | derecha | Rama previa + complemento acotado | Recaptura visible |
| 55 | 12:42.20 | 15245 | derecha | Rama previa | Recaptura visible |
| 56 | 12:49.95 | 15400 | izquierda | Base | Recaptura visible |
| 57 | 13:05.05 | 15702 | derecha | Base + completar giro | Recaptura visible |
| 58 | 13:09.45 | 15790 | GAP | GAP previo | Recaptura visible |
| 59 | 13:12.95 | 15860 | izquierda | Base | Recaptura visible |
| 60 | 13:19.00 | 15981 | derecha | Rama previa | Recaptura visible |
| 61 | 13:29.60 | 16193 | derecha | Rama previa | Recaptura visible |
| 62 | 13:37.50 | 16351 | derecha | Base + completar giro | Recaptura visible |
| 63 | 13:46.85 | 16538 | izquierda | Rama previa | Recaptura visible |
| 64 | 13:53.35 | 16668 | izquierda | Base | Recaptura visible |
| 65 | 13:58.65 | 16774 | derecha | Base | Recaptura visible |
| 66 | 14:11.80 | 17037 | derecha | Base | STOP sin recaptura |
| 67 | 14:35.40 | 17509 | derecha | Base | STOP sin recaptura |
| 68 | 14:50.20 | 17805 | derecha | Base | STOP sin recaptura |
| 69 | 15:11.80 | 18237 | derecha | Base + complemento acotado | STOP sin recaptura |

## La falla repetida: un codo, no una decisión general incorrecta

Los episodios **4, 18, 39, 40, 48, 50, 66, 67, 68 y 69** son repeticiones de un codo derecho de aspecto muy similar y terminan sin recaptura. El **41** presenta el patrón opuesto a izquierda.

| Episodio | Inicio en el AVI | Decisión | Cierre observado |
|---:|---|---|---|
| 4 | 02:06,50 | Derecha | Complemento acotado, luego STOP |
| 18 | 06:15,00 | Derecha | Complemento acotado, luego STOP |
| 39 | 09:07,85 | Derecha | Complemento acotado, luego STOP |
| 40 | 09:31,15 | Derecha | Complemento acotado, luego STOP |
| 41 | 09:44,60 | Izquierda | Complemento acotado, luego STOP |
| 48 | 10:44,25 | Derecha | Ya no queda cinta suficiente para complementar; STOP |
| 50 | 11:13,50 | Derecha | Complemento acotado, luego STOP |
| 66 | 14:11,80 | Derecha | Sin cinta suficiente para complementar; STOP |
| 67 | 14:35,40 | Derecha | Sin cinta suficiente para complementar; STOP |
| 68 | 14:50,20 | Derecha | Sin cinta suficiente para complementar; STOP |
| 69 | 15:11,80 | Derecha | Complemento acotado, luego STOP |

En esos once casos el signo enviado coincide con el lado de la rama que se ve antes de la pérdida. La evidencia previa guardada también coincide: en los derechos se registra side=1 con unas 19–24 observaciones derechas y muy pocas o ninguna izquierda. El último parche no está invirtiendo esos codos.

Lo que ocurre después es el problema: tras el retroceso y el pivote, la cámara no vuelve a tener una componente de línea conectada. En siete de esos codos se intenta el complemento; en cuatro la cinta ya no cumple el mínimo visible y el sistema se detiene directamente. El STOP impide seguir avanzando a ciegas, pero **no equivale a haber recuperado la línea**.

Según el último fuente disponible, el objetivo inicial para esos comandos ronda 35,5–38,1°. Eso es un objetivo calculado, NO una medición de esta corrida. Sin CSV no puede determinarse si el robot giró exactamente esa cantidad, si hubo patinamiento o si el eje quedó desplazado respecto de la rama. Las imágenes sí muestran que el problema ya está en la pose/reenganche después de decidir correctamente el lado.

**Hipótesis a distinguir:** giro todavía insuficiente, posición desplazada respecto de la salida tras el retroceso, o desplazamiento durante el giro. Si la cámara queda paralela pero corrida respecto de la rama, sumar grados no arregla por sí solo la posición. Por eso no se recomienda aumentar todos los giros ni modificar el PID a partir de este video.

## Falla aislada de clasificación: GAP de 03:30

Episodio 13, cuadro 4202, 03:30,05 del AVI: se ve una interrupción recta, pero se envía CURVA derecha. El log registra:

- strong=True, piso=True;
- solo cuatro cuadros válidos para la evidencia de punta desde arriba;
- side_recent=1;
- rama persistente congelada side=0 (left=6, right=2);
- motivo final `lateral previa + fragmento pequeno compatible`.

La excepción de GAP nueva requiere side_recent=0. Esa única observación lateral la deja fuera y permite el giro. Luego el cierre detiene el robot sin recaptura.

Este es un caso separado del codo repetido. Una revisión acotada debería distinguir una observación lateral aislada de una rama persistente, manteniendo las protecciones de curvas reales. No se cambió esa condición en el robot durante el análisis.

## Tres recapturas transitorias

Episodios 43, 47 y 52, iniciados aproximadamente en **10:00,70**, **10:33,05** y **11:29,85**. La línea vuelve a tocar el área del robot y luego se pierde otra vez dentro de la ventana revisada.

La protección actual deja de actuar después de dos cuadros A/D. En estos tres episodios esa condición aparece con la cinta muy corrida a la izquierda. Ejemplos medidos:

| Episodio | Cuadro próximo al cierre | Forma | Error lateral normalizado cercano | Orden enviada |
|---:|---:|---|---:|---:|
| 43 | 12060 | A | −0,67 | +65,1° |
| 47 | 12708 | A | −0,73 | +66,2° |
| 52 | 13842 | A | −0,72 | +66,8° |

En una imagen de 160 píxeles, esos valores corresponden a centros de cinta aproximadamente en x=21–26, muy lejos de x≈80. **A indica una forma que llega arriba, no que el robot esté centrado.** Es una limitación concreta del criterio de cierre introducido: no basta con dos A/D para certificar recuperación completa.

En los cuadros siguientes el seguimiento manda correcciones grandes y de signo alternante; finalmente vuelve a haber máscara no conectada. La protección lateral ya se había desarmado, por lo que aparecen comandos de cooldown o de máscara vacía. El registro por cuadro permite comprobarlo en `cierre_por_frame.csv`.

La siguiente revisión de cierre debería considerar posición cercana, orientación y continuidad durante la salida. Debe comprobarse contra las 53 recapturas visibles para no convertir un movimiento normal de seguimiento en un STOP innecesario. Exigir simplemente más cuadros sin evaluar posición tampoco demostraría que la ruta es correcta.

## Episodio fuera de pista

Episodio 12, alrededor de 03:17,55: la cámara pasa a mostrar madera y se mantiene búsqueda GAP sin reconexión en la ventana. El video por sí solo no distingue con certeza toda manipulación externa del desplazamiento autónomo. Se documenta separado y no se usa como ejemplo de GAP de pista válido.

## Qué conservar y qué medir después

- Conservar por ahora la corrección de lado por rama previa: las 13 intervenciones revisadas tienen recaptura visible.
- Conservar la prioridad de GAP aplicada en los cinco casos observados: reconectan.
- Conservar los codos donde el complemento existente sí termina reconectando, por ejemplo 6/11/21/26/27/32/33/38/57/62.
- Concentrar la prueba mecánica en el codo derecho repetido, comparándolo con otro derecho que funciona. Grabar crudo + CSV y, si es posible, vista externa del robot completo. Es la evidencia que falta para separar giro de desplazamiento.
- Revisar por separado la condición de cierre transitoria y el único GAP excluido por side_recent=1.

No se modificaron programas, parámetros ni firmware al efectuar esta revisión.

## Láminas de todas las recuperaciones

Cada fila corresponde a un episodio. Las seis columnas muestran aproximación, decisión, comienzo de salida y evolución posterior. El final de una fila se limita antes de mezclar otra sesión o recuperación.

- [Episodios 1–7](todas_01.jpg).
- [Episodios 8–14](todas_02.jpg).
- [Episodios 15–21](todas_03.jpg).
- [Episodios 22–28](todas_04.jpg).
- [Episodios 29–35](todas_05.jpg).
- [Episodios 36–42](todas_06.jpg).
- [Episodios 43–49](todas_07.jpg).
- [Episodios 50–56](todas_08.jpg).
- [Episodios 57–63](todas_09.jpg).
- [Episodios 64–69](todas_10.jpg).

Los datos completos están en `inventario_final.csv`, `metricas_cierre.csv` y `cierre_por_frame.csv`. La conclusión de recaptura se refiere a las imágenes y la ventana descrita; no reemplaza mediciones de movimiento que no se grabaron.
