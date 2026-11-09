# Recuperaciones: pruebas repetidas y pista completa

## Alcance

Se usa la separación indicada por el usuario: hasta aproximadamente 03:53 del AVI son pruebas repetidas; desde 03:54 es pista completa. Hay **25 episodios de recuperación que comienzan en las pruebas**, no necesariamente 25 intentos independientes: una misma prueba puede contener varias recuperaciones. El episodio 25 comienza en 03:52,40 y se completa junto al límite entre ambas etapas. En toda la grabación hay 34 episodios GS4 y 9 entradas a GS18.

Se revisaron las secuencias originales antes/durante/después de los 34 episodios y, para las fallas de las pruebas, los últimos cuadros antes de las pausas. Se cruzaron decisiones por cuadro, motivos del log, ángulo recibido, consignas, RPM, encoders, yaw y giroscopio. No se modificó el robot.

Los tiempos de este documento son del **AVI a 20 FPS**. El reloj real del crudo es distinto. Sincronización con CSV: `segundo CSV desde su primera muestra ≈ t_crudo + 31,30 s`, determinada por coincidencia de cambios del ángulo recibido. La precisión práctica es de decenas de milisegundos.

## Resultado principal

Hay cuatro problemas distintos:

1. Se decide izquierda aunque la salida derecha ya estuvo visible antes de perder la línea.
2. Se convierte un codo en búsqueda GAP, por la regla PALILLO o por el fallback de ambigüedad.
3. Se decide correctamente el lado y se completa el ángulo programado, pero se libera avance sin línea recapturada.
4. En la pista completa, cuatro GAP reales se convierten en curvas izquierdas, pese a evidencia de GAP registrada antes del retroceso.

La Teensy no decide visualmente izquierda/derecha ni GAP: recibe GS y un rumbo. El clasificador de la Raspberry decide y la Teensy ejecuta el movimiento correspondiente. La Teensy tampoco recibe una orden física de girar 54° cuando el protocolo lleva 54°: ese rumbo se convierte en un objetivo menor según su fórmula.

## Lo que ejecuta actualmente la Teensy

En el fuente guardado al recoger esta corrida:

- Retroceso: 550 ms, 25 RPM.
- Pivote: 35 RPM, `rot=1`.
- Objetivo: `28 + 0,15 × |rumbo|`, limitado a 35–58°.
- Timeout de pivote: 1600 ms.

Además del cambio 400→550 ms, el factor de giro disponible pasó de 0,22 en la revisión inicial a **0,15**. El CSV no registra directamente esas dos constantes, pero las duraciones y giros medidos son compatibles con 550 ms y con la fórmula de 0,15. No se verificó identidad binaria completa del firmware; el identificador `c92c566-s` no basta para distinguir los cambios locales.

Los retrocesos medidos duran aproximadamente 535–550 ms. Los pivotes dirigidos duran aproximadamente 635–720 ms y giran unos 34–38°. Es consistente con los objetivos actuales, no con un timeout de 1600 ms.

La Raspberry conserva un reloj de recuperación de 1,35 s desde el comienzo del episodio. Al vencer, puede enviar GS0 sin recaptura. La Teensy tiene una protección que continúa el pivote ya comprometido aunque llegue GS0: no se debe concluir que ese mensaje corta anticipadamente todos los giros.

## Pruebas anteriores a 03:53: inventario

La orientación de rama se inspeccionó en los cuadros previos a la pérdida. Como apoyo cuantitativo, `ramas_pre_perdida.csv` cuenta en los 30 cuadros anteriores cuántos muestran la componente conectada llegando al borde izquierdo/derecho en filas 60–104. Es evidencia de geometría de imagen, no un detector definitivo de ruta. En un círculo o cruce volver a encontrar negro no garantiza haber tomado la rama correcta.

| Episodio / inicio AVI | Rama/evidencia visual | Decisión ejecutada | Resultado relevante |
|---|---|---|---|
| 1 / 00:19,05 | Codo derecho, rama derecha visible en 20 cuadros previos | PALILLO convierte CURVA en RECTA/GAP | Cruza la rama y se pierde. Problema de decisión. |
| 2 / 00:31,25 | Rama izquierda | Izquierda, yaw ≈35,8° | Recaptura y continúa. Caso de comparación a conservar. |
| 3 / 00:46,45 | Codo derecho | Derecha ≈36,5° y complemento de giro | Recaptura y continúa hacia el GAP siguiente. Conservar. |
| 4 / 00:51,25 | Cinta interrumpida, sin rama lateral previa | GAP, autorizado por PALILLO | Reconecta y continúa. No desactivar PALILLO globalmente. |
| 5 / 00:55,10 | Rama izquierda | Izquierda ≈35,5° | Recaptura; después aparece otra curva. Conservar la decisión. |
| 6 / 01:01,80 | Codo derecho | Derecha ≈36,2° | Recaptura y continúa. Conservar. |
| 7 / 01:11,55 | Curva circular, rama derecha visible antes de perderla | La intención previa era derecha, pero el post-retro elige izquierda por “3 frames laterales” | Giro izquierdo ≈34,9°. Reaparece negro de la curva; existe contradicción de rama y no debe contarse automáticamente como éxito de ruta. |
| 8 / 01:20,65 | Cinta interrumpida sin rama previa | GAP por PALILLO | Reconecta y continúa. Conservar. |
| 9 / 01:24,45 | Rama izquierda | Izquierda ≈36,7° | Recaptura; el fallo llega en el codo siguiente. Conservar esta decisión. |
| 10 / 01:30,90 | Codo derecho; 16 cuadros previos con rama derecha, ninguno izquierda | Izquierda ≈34,8°, por memoria lateral | Sale al piso blanco. En 29 de los siguientes 30 cuadros analizados no hay línea conectada. |
| 11 / 01:36,70 | Codo derecho; rama derecha en 13 cuadros previos | AMBIGUA termina en GAP | Avanza a través de la rama y sale. El fallback recto no está justificado por la imagen del codo. |
| 12 / 01:48,70 | Rama derecha | Derecha ≈37,5° | Recaptura alineada. Conservar. |
| 13 / 01:56,25 | Codo derecho; rama derecha en 14 cuadros previos | Izquierda ≈33,9°, por memoria lateral | Sale sin recaptura: 31/31 cuadros posteriores sin componente conectada. |
| 14 / 02:03,90 | Codo derecho | Derecha ≈37,3° más COMPLETAR_GIRO | El complemento actúa durante 9 cuadros y recaptura. Conservar ese mecanismo. |
| 15 / 02:18,50 | Curva circular con rama derecha previa | La intención previa era derecha; el post-retro cambia a izquierda por tres laterales | Izquierda ≈37,5°. Vuelve a ver negro del círculo, pero contradice la rama anterior. Necesita revisión de elección de rama, no solo de conectividad. |
| 16 / 02:31,00 | Curva circular, rama derecha visible en 26 cuadros previos | Cambia intención derecha a izquierda por “par lateral fuerte temprano” | Izquierda ≈36°. Pasa 37/43 cuadros posteriores sin línea conectada, con avance recto; luego vuelve a encontrar negro. Recuperar negro tarde no valida la decisión inicial. |
| 17 / 02:42,95 | Codo derecho | Elige derecha y gira ≈38° | Lado correcto, salida fallida: 44/44 cuadros posteriores sin conexión. La cinta queda todavía atravesada/lejana y avanza recto. Falta cierre visual. |
| 18 / 02:57,50 | Rama izquierda | Izquierda ≈35° | Recaptura y continúa. Conservar. |
| 19 / 03:13,10 | Codo derecho | Derecha ≈37,5° más complemento | Recaptura. Conservar. |
| 20 / 03:17,75 | Cinta interrumpida, sin rama lateral previa | GAP por PALILLO | Reconecta y continúa. Conservar. |
| 21 / 03:21,60 | Rama izquierda | Izquierda ≈37,3° | Recaptura; el fallo posterior corresponde al siguiente codo. Conservar esta decisión. |
| 22 / 03:28,00 | Codo derecho; rama derecha en 17 cuadros previos | Izquierda ≈34,9°, por memoria lateral | Sale; 45/45 cuadros posteriores sin línea conectada y 44 con `recup-cooldown-recto`. |
| 23 / 03:34,10 | Codo derecho; rama derecha en 17 cuadros previos | AMBIGUA termina en GAP | Avanza sin tomar la rama; termina sin línea y se interrumpe. |
| 24 / 03:44,65 | Curva derecha | Derecha ≈38,2° | Recaptura. El fallo siguiente es otro episodio. Conservar la decisión. |
| 25 / 03:52,40 | Codo derecho, rama derecha en 13 cuadros previos | Izquierda ≈33,9°, por “fragmento pequeño compatible” | 28/28 cuadros posteriores sin conexión, hasta la pausa. Otro caso de lado equivocado más liberación de avance. |

Los porcentajes de desconexión se miden en la ventana de hasta 1,5 s después de abandonar GS4, limitada por el siguiente episodio o una interrupción larga. No describen el recorrido completo de cada prueba.

## Por qué toma el lado equivocado

### Memoria de izquierda que sobrevive a una salida derecha

En 10, 13 y 22, la decisión final es `lateral previa muy reciente + post ambiguo no la refuta`; en 25 es `lateral previa + fragmento pequeno compatible`. La salida derecha ya es visible en la imagen previa a la pérdida, pero la memoria de orientación del clasificador queda a izquierda.

El log muestra además `SIDE-CHECK BLOQUEADO por LATERAL real previo ...`. Esa barrera protege episodios buenos, pero también impide corregir estos. Aumentar el giro izquierdo agravaría la salida.

Se reprodujo la geometría CAMINO de muestras alrededor de los episodios, con calentamiento local de 35 cuadros. En 10 y 22 aparecen trazos post-retro hacia la derecha; en 13 la señal derecha aparece algo más tarde. Como la decisión ya queda congelada, no necesariamente se aprovecha. Esta reproducción local no reconstruye toda la historia interna del proceso y no se presenta como identidad exacta con todos sus estados originales.

### Cambios de derecha a izquierda en curvas circulares

En 7 y 15 la intención previa registrada era derecha; “3 frames laterales post-retro” cambia a izquierda. En 16 ocurre algo similar con el par lateral temprano. La forma local de la cinta de entrada, un fragmento y otras partes del círculo pueden confundir la lectura de rumbo.

Estos casos necesitan conservar evidencia de la rama seguida antes de perderla y contrastarla con la componente de salida. Un fragmento local no debe borrar sin comprobación una rama observada consistentemente. Tampoco se debe imponer siempre la memoria: esa es precisamente la causa de los casos anteriores.

## Qué hacen las ruedas en las fallas

| Episodio | Orden de protocolo recibida | Objetivo según fórmula actual | Yaw medido | Gyro integrado, magnitud | RPM medianas FL/FR/BL/BR |
|---:|---:|---:|---:|---:|---|
| 10 | +34,9° → izquierda | 35° | −34,8° | 35,0° | 32,5/33/31/32 |
| 13 | +31,0° → izquierda | 35° | −33,9° | 35,2° | 33/32/32/30 |
| 16 | +61,9° → izquierda | 37,3° | −36,0° | 38,4° | 34/33/32/30 |
| 17 | −65,0° → derecha | 37,7° | +38,0° | 38,3° | 31/34/31/33 |
| 22 | +43,9° → izquierda | 35° | −34,9° | 35,8° | 31/31/33/30 |
| 25 | +12,0° → izquierda | 35° | −33,9° | 34,7° | 34/32/31,5/29,5 |

Las medianas pertenecen al pivote dirigido, no a toda la recuperación. El sentido por rueda se registra aparte porque las RPM son magnitudes. No hubo aumento de `drop` en estas ventanas.

El pivote ocurre y se aproxima a lo programado. No se encontró una rueda permanentemente parada ni un timeout que explique estos seis casos. Esto no descarta patinamiento ni transitorios mecánicos puntuales, pero no justifica comenzar modificando el PID.

## Por qué no termina bien aun eligiendo el lado correcto

El caso 17 separa este problema de la clasificación:

1. La Pi elige derecha y envía un rumbo de aproximadamente −65°.
2. La Teensy retrocede unos 540 ms y pivota aproximadamente 38°, coherente con el objetivo actual de 37,7°.
3. La Pi abandona GS4 por su reloj de 1,35 s. No exige recuperar la línea.
4. Aparecen `recup-cooldown-recto` y luego máscara vacía. El robot avanza en lugar de completar la orientación o detenerse.

`COMPLETAR_GIRO` ayuda en los casos 3/14/19. Sin embargo, se activa solo con una forma de cinta transversal específica (F) y una componente conectada. Si la cinta queda separada o fuera del área que toca la fila 118, `_solo_mi_linea` entrega vacío, la forma pasa a `.` y el complemento no arranca. Es lo que muestra el caso 17: el giro correcto puede quedarse geométricamente incompleto y el mecanismo de cierre no cubrirlo.

La conectividad por sí sola tampoco acredita haber tomado la rama correcta en un círculo. Se debe comprobar conexión, orientación y coherencia con la salida elegida.

## Pista completa: los instantes señalados

En estas marcas el objeto físico era GAP, pero en cuatro intentos se ejecutó una curva izquierda. Esto es independiente del problema contrario de convertir codos en GAP.

| Marca aproximada del usuario | Inicio GS4 / cuadro | Evidencia previa registrada | Decisión final y movimiento |
|---|---|---|---|
| 04:45 | 04:43,75 / 5676 | `strong=True`, `piso=True`, 18 cuadros desde arriba, ancho máximo 1,5 cm, sin rama lateral | CURVA IZQ por fragmento compatible; recibe ≈+54°, gira −36° y se desvía |
| 04:50 | 04:49,15 / 5784 | Igual patrón; 16 cuadros, ancho 1,6 cm | CURVA IZQ; recibe ≈+59°, gira −36° y se desvía |
| 04:58, correcto | 04:56,85 / 5938 | 15 cuadros, ancho 1,5 cm; intención previa RECTA | Pasa a GAP, avanza sin pivotar y reconecta |
| También 05:22 | 05:21,45 / 6430 | 17 cuadros, ancho 1,5 cm, sin rama lateral | CURVA IZQ; gira −36,4° y se desvía |
| 05:27 | 05:26,20 / 6525 | 23 cuadros, ancho 1,6 cm, sin rama lateral | CURVA IZQ; gira −35,6° y se desvía |
| 05:30–32, correcto | 05:30,30 / 6607 | `strong=True`, regla antigua de terminal válida, pero `piso=False` | El veto existente sí aplica a su motivo de memoria; pasa a GAP y reconecta |

### Regla omitida

`would_veto_curve()` solo deja vetar dos motivos de CURVA basados en memoria. **No incluye `lateral previa + fragmento pequeno compatible`.** Ese es exactamente el motivo de los cuatro GAP fallidos.

El sistema ya tiene evidencia previa suficiente para distinguirlos de los codos: la punta baja desde arriba sin rama lateral, con ancho de cinta coherente. La evidencia se calcula pero no tiene autoridad contra ese tercer motivo.

### Efecto del retroceso de 550 ms

Puede cambiar el fragmento visible y el reloj restante de la Pi. Sin una corrida equivalente a 400 ms no se puede afirmar que sea la causa única.

En los seis episodios comparados, las dos ruedas delanteras retroceden normalmente cantidades similares. Por ejemplo: episodio 27, 118/115 pulsos; episodio 29 correcto, 116/117; episodio 30, 116/116. El episodio 31 tiene 113/137 y unos 5° de cambio de rumbo durante el retroceso, lo que puede contribuir a su pose; sin embargo, otros GAP fallidos tienen retroceso casi simétrico. El correcto 32 también registra unos 4° durante el retroceso. La diferencia mecánica no explica por sí sola la selección repetida de CURVA.

## Propuestas separadas para conservar lo que funciona

### A. GAP visto antes de la pérdida frente a fragmento pequeño

Extender de forma acotada la prioridad del GAP cuando se cumplen simultáneamente:

- motivo final `lateral previa + fragmento pequeno compatible`;
- evidencia previa `strong=True` y `strong_piso=True`;
- `side_recent=0`.

Se probó a nivel de decisiones registradas: cambia únicamente episodios 27/28/30/31 de esta corrida; conserva las otras 30 decisiones, incluidos los GAP correctos 29/32 y las decisiones de curva previas. En los 22 episodios de la grabación anterior no añade cambios. Archivo: `resultado_propuesta.txt`.

Esto NO arregla por sí solo las fallas de las pruebas antes de 03:53. Conservar decisiones tampoco significa que todas esas decisiones conservadas fueran correctas.

### B. Congelar evidencia de rama, además del rumbo de memoria

Guardar antes de la pérdida qué componente de la línea mostraba una rama persistente y hacia qué lado. Confrontarla con la lectura post-retro y con las razones de decisión. Los recuentos de borde de este informe separan claramente varios casos, pero no se deben convertir sin validación en una orden universal: una chicana, círculo o entrada muy diagonal puede necesitar más geometría.

Usar los casos 10/13/22/25 para corregir memoria equivocada y 7/15/16 para corregir el cambio de una intención previa derecha a izquierda. Conservar como regresión las curvas 2/3/5/6/9/12/14/18/19/21/24. El caso 33 de pista completa ve ambos bordes: una regla simplista de “manda el borde con más píxeles” no sería suficiente.

En la grabación anterior, los mismos recuentos detectan contradicción en 4517 y 5362, dos recuperaciones que ya habían terminado mal. Es apoyo adicional, no prueba de trayectoria futura.

### C. Evitar GAP de ambigüedad o PALILLO cuando hay un codo observado

Para PALILLO, dos fragmentos cercanos no prueban que haya una interrupción recta: también aparecen en un codo y su borde. Conservar las pasadas correctas 4/8/20, pero impedir que la regla borre una salida lateral claramente observada como en 1 y 34.

En ambigüedad, los casos 11/23 no deben convertirse automáticamente en avance recto si ya hay evidencia persistente de una rama derecha. Confirmar detenido o usar esa geometría, con límites. No eliminar toda búsqueda GAP: los casos correctos deben conservarse.

### D. Cierre visual de recuperación

Conservar el pivote inicial como base y comprobar su resultado. Si hay rama visible pero no alineación, completar lentamente dentro de límites. Si no hay línea, detener el avance y buscar de forma acotada. Mantener GAP y excepciones de cresta/rampa separados.

Cambiar el K de 0,15 a otro valor global no puede corregir un giro al lado equivocado y podría alterar las curvas que ya recapturan. La prioridad es corregir la decisión y la salida sin recaptura; después medir si determinados codos necesitan otro objetivo inicial.

## Límites de la validación

La propuesta A se contrastó contra estados y motivos registrados, no contra una simulación completa del robot. La inspección de imágenes y los cálculos de geometría B/C/D sustentan el diagnóstico, pero aún no constituyen una corrección desplegada ni validada en pista.

Cambiar una orden modifica los cuadros futuros. Un replay de la grabación puede comprobar reglas y regresiones conocidas; no puede demostrar que la nueva trayectoria completará una curva. No se cambió el código de producción.

## Archivos para revisar

- `gaps_445_450_458.jpg`, `gaps_527_530.jpg`: aproximaciones, decisiones y salidas de los GAP señalados.
- `todas_recuperaciones_1.jpg` a `todas_recuperaciones_5.jpg`: los 34 episodios, una fila por episodio.
- `fin_pruebas_1.jpg`, `fin_pruebas_2.jpg`: cuadros anteriores a interrupciones de las pruebas.
- `episodios_cruzados.csv`: motivos, comandos, duraciones, giro, ruedas y retroceso.
- `cierre_recuperaciones.csv`, `post_recuperacion_frames.csv`: conexión y forma de cinta después de soltar GS4.
- `ramas_pre_perdida.csv`, `ramas_corrida_anterior.csv`: evidencia lateral previa.
- `geometria_post_muestra.csv`: geometría CAMINO reproducida en muestras locales.
