# Plateados visibles y entrada alineada por cámara

## Alcance comprobado

Se buscó la banda plateada visualmente a intervalos de un segundo en cuatro videos recientes: 12:38:04, 12:49:12, 13:54:38 y 14:09:05 del 1 de noviembre. La revisión general no equivale a inspeccionar cada cuadro de los cuatro videos ni garantiza descubrir una aparición que durase menos que el intervalo de búsqueda.

Se localizaron ocho aproximaciones a la banda en el video de 20:17 de las 12:49. En el de las 12:38 hay una secuencia con dos aproximaciones separadas por un reinicio. En el de las 13:54 hay una secuencia con aproximación y reintentos sobre la banda. En la prueba de las 14:09 no se identificó esa banda de entrada: se ve la rampa y sus cruces/verdes, revisados también en la auditoría anterior.

Las diez ventanas seleccionadas para detalle contienen **2.051 cuadros**. Se revisaron visualmente todos esos cuadros en 36 láminas y se cruzaron con el CSV. Algunas ventanas contienen más de un intento; no se presentan como diez detecciones físicas independientes. Las referencias exactas están en `casos.json`, `indice_revision.csv` y `acciones_todos_plateados.csv`.

La búsqueda no incluye todos los videos históricos del repositorio. Tampoco es una reconstrucción de todas las lecturas APDS. Se distingue ver material plateado de tener prueba de que la Teensy lo confirmó.

## Las ocho aproximaciones del video principal

Tiempos del AVI, calculados como `(cuadro-1)/20`. Las ventanas incluyen contexto previo, por lo que su comienzo no es el primer píxel plateado ni el instante de contacto del sensor.

| ID | Ventana revisada | Primer GS4 de esa aproximación | Decisión posterior visible en el registro |
|---|---|---|---|
| P01 | 04:10.00–04:14.55, f5001–5092 | 04:11.60, f5033 | Retroceso; ambigua; GAP/GS18 desde f5052. |
| P02 | 07:35.00–07:42.85, f9101–9258 | 07:39.25, f9186 | Curva, orden +54; después GS19 desde f9236. |
| P03 | 07:42.90–07:50.70, f9259–9415 | 07:47.35, f9348 | Retroceso; ambigua; GAP/GS18 desde f9365. |
| P04 | 12:42.00–12:50.40, f15241–15409 | 12:46.95, f15340 | Curva, orden +49,8; después GS19 desde f15390. Corresponde al caso indicado como 12:45. |
| P05 | 12:56.00–13:05.05, f15521–15702 | 13:02.45, f15650 | Retroceso; ambigua; GAP/GS18 desde f15669. Corresponde al caso de 13:04. |
| P06 | 13:13.00–13:21.35, f15861–16028 | 13:17.55, f15952 | Curva, orden +66,3; después GS19 desde f16003. Corresponde al caso de 13:18. |
| P07 | 13:21.40–13:30.00, f16029–16201 | 13:26.40, f16129 | Curva, orden +64,5; después búsqueda/reenganche con orden −85. Corresponde al caso de 13:27. |
| P08 | 17:27.00–17:38.35, f20941–21168 | 17:31.70, f21035 | Curva, orden +54; después GS19 desde f21083. |

Los signos anteriores son órdenes de cámara: positivo izquierda y negativo derecha. **No son grados de yaw ejecutados por el robot.** GS19 es parada; GS18 es búsqueda GAP. La tabla no afirma que los ocho episodios hayan ejecutado la misma maniobra física ni que se conozca el resultado final del rescate.

El momento 13:08 señalado anteriormente es un codo derecho, con pérdida y recuperación posteriores. No se contó como otra entrada al plateado: la banda de entrada aparece en otras aproximaciones cercanas, pero no corresponde confundir el codo con una detección de ese material.

## Secuencias adicionales

- **P09, video 12:38:04:** f4701–5054, 03:55.00–04:12.65. Incluye el codo previo y dos aproximaciones a la banda. Hay un salto de 57,029 s de tiempo real antes de f4913; se considera reinicio/reintento, no movimiento continuo. Primera aproximación: pérdida en f4847 y GAP desde f4864. Segunda: pérdida en f4978, curva +62 desde f4997, y posteriormente búsqueda −85 con muy poca referencia de cinta.
- **P10, video 13:54:38:** f3801–4170, 03:10.00–03:28.45. Incluye aproximación, interrupción antes de f3879 y un nuevo inicio antes de f4085. Se distinguen la aproximación f3801–3878, el episodio f3879–4084 —GS4 desde f3895, curva −70, parada desde f3943— y el reintento ya próximo a la banda f4085–4169 —GS4 desde f4097, GAP desde f4140—. No se suman estos fragmentos como tres cruces completos del plateado. F4170 pertenece al reinicio siguiente y solo cierra la ventana de contexto.

## Patrón visual que explica el problema

En las aproximaciones del video principal se repite la siguiente secuencia:

1. La cinta llega a una curva corta o termina con una dirección oblicua junto a la banda plateada.
2. Mientras la parte cercana aún está aproximadamente centrada, el centroide puede mandar un giro pequeño o incluso cero. Eso no prueba que el robot apunte en la dirección necesaria para cruzar: la punta y la dirección futura de la cinta ya están hacia un costado.
3. El extremo negro sale del campo cercano. En las ocho ventanas aparece GS4, por lo que el sistema trata ese final como pérdida de línea antes de tener una entrada visualmente validada.
4. Tras retroceder, queda un fragmento de cinta, el borde de la banda o reflejos oscuros. El resultado varía entre curva, ambigua/GAP, búsqueda complementaria o parada. La misma llegada oblicua puede producir decisiones distintas al variar los pocos píxeles restantes.
5. Una recuperación puede terminar sin que haya una cinta continua y orientada hacia delante. Terminar un pivote no certifica alineación.

No se concluye que todos los píxeles negros sobre el plateado sean reflejos: algunos son cinta real que sigue visible. La identidad temporal y la posición del fragmento son necesarias para separarlos. Tampoco basta con buscar cualquier superficie gris o brillante: el piso, juntas, cresta de rampa y objetos del recorrido producen apariencias parecidas.

## Cómo preparar una entrada recta usando la cámara

La corrección debe empezar **mientras todavía se ve la cinta**, antes de que el sensor de color y la pérdida de línea provoquen una maniobra que ya no dispone de una referencia visual clara.

### 1. Anticipar una posible banda

Formar una hipótesis temporal de «posible plateado» combinando una banda reflectante/neutra extensa con el extremo de nuestra cinta que llega a ella. Debe persistir y acercarse coherentemente durante varios cuadros. Una máscara por color o un final de línea aislados no son suficientes.

Esta hipótesis sirve para preparar el alineamiento; no declara rescate, no reemplaza la confirmación APDS y no debe convertir automáticamente un GAP o codo real en entrada al plateado. Antes de usarla para cambiar movimiento hay que medir falsos positivos en subidas, gaps, cruces y reflejos del piso.

### 2. Terminar la curva y medir dos errores distintos

- Posición de la cinta cerca del robot: desplazamiento lateral.
- Dirección de esa misma cinta entre una banda cercana y otra más lejana: orientación relativa.
- Forma temporal: distinguir un tramo recto de salida de una curva todavía pendiente. El promedio de todo el negro de la imagen puede cancelar esos errores y dar cero aun con una llegada incorrecta.

Los errores son de imagen; no se presentan como grados físicos sin calibración. Es necesario compensar la perspectiva para no interpretar como giro el estrechamiento normal de una cinta recta descentrada. Las bandas tienen que seguir siendo visibles y pertenecer a la misma cinta.

### 3. Autorizar el avance solo con geometría consistente

La entrada queda lista cuando el robot está centrado respecto del tramo de salida, la dirección es compatible y la medición se mantiene durante varios cuadros. Los umbrales concretos todavía deben elegirse con controles de entradas rectas físicamente exitosas; en estas grabaciones no hay evidencia suficiente para certificar una trayectoria de rescate completa como patrón ideal.

Si todavía está terminando la curva, debe conservar la rama correcta y completar el giro. Si ya perdió toda la cinta, no se debe inventar que está alineado porque el centroide vale cero o porque pasó cierto tiempo. Hay que detener el avance y reobservar/reencontrar una referencia con una maniobra acotada.

Una banda plateada uniforme no informa por sí sola el desplazamiento lateral absoluto del robot. Su borde puede ayudar a estimar orientación, con calibración, pero no sustituye la cinta para certificar que está centrado. Por eso no es responsable prometer «recto siempre» si ya no queda ninguna referencia visible.

### 4. Coordinar la entrada con la Teensy

La cámara debe conservar autoridad sobre el alineamiento hasta confirmar la entrada. En el código local disponible, al entrar a `case 2` se ejecuta:

- Retroceso a 30 durante 1.000 ms.
- Pausa de 1.000 ms.
- Giro izquierdo de 20° nominales.
- Avance a 30 durante 5.000 ms.

Esa secuencia no espera una confirmación visual de alineación entre el giro y el avance. Esto coincide parcialmente con lo que el usuario describe —retroceder y girar a la izquierda—, pero **no prueba que ese fuente sea exactamente el firmware que corrió**, ni permite ver el avance completo en estas grabaciones. No se atribuye el choque a cinco segundos efectivamente ejecutados sin esa comprobación.

Además existe en el fuente una corrección anterior a la entrada que depende de la recuperación reciente. Reorientar usando solo la historia del giro no equivale a medir la orientación actual. Esa función debe contrastarse con el firmware cargado antes de decidir si hay que conservarla, sustituirla o condicionarla.

La integración necesita una fase «plateado pendiente/alineando» anterior a la entrada automática. Si el APDS confirma mientras la cámara aún ve una llegada torcida, la confirmación de material debe conservarse, pero no convertirse inmediatamente en autorización para ejecutar el avance. Una vez alineado, se autoriza la entrada. Si la maniobra posterior vuelve a cambiar la orientación, también tiene que respetar esa comprobación; alinear y después imponer otro giro ciego no resuelve el problema.

No se utiliza ultrasonido para esta solución. Tampoco se promete reducir la velocidad cambiando únicamente el campo `speed` de cámara: el modo normal de seguimiento de la Teensy calcula su propia velocidad, de modo que un modo de aproximación lento necesita integración real en su control.

## Límite importante de los videos actuales

Las llamadas a `_grabar` y `_grabar_crudo` están dentro de la fase de seguimiento de línea. El log contiene avisos 241/entrada a rescate, pero los cuadros CSV de estas grabaciones son de línea. El archivo AVI completo, por tanto, **no equivale a una filmación continua de todas las maniobras de rescate**. Los saltos de `t` permiten detectar intervalos omitidos, pero no reconstruir sus movimientos.

`silver=0` en ese CSV tampoco significa que el APDS no detectó material: es el campo de cámara, sin autoridad sobre esa confirmación. La revisión visual no transforma esa columna en telemetría del sensor.

Para comprobar la entrada hasta que termine debe registrarse la cámara también durante la transición y el rescate, con marcas de inicio/fin de la maniobra de Teensy. No se pueden reconstruir retrospectivamente yaw, ruedas ni lecturas APDS que no se grabaron.

## Conclusión práctica

El cambio viable es una **aproximación y alineación visual previa al plateado**, seguida de una autorización de entrada coordinada. Debe preservar la detección de material que funciona y conservar separados los casos de codo, GAP, verde y cresta. No se propone un giro fijo extra ni desactivar globalmente las recuperaciones.

En esta revisión solo se generaron evidencia, índices y este informe. **No se modificó ni instaló código del robot.** Los giros de subida y verde siguen siendo el otro trabajo pendiente; esta propuesta de plateado todavía no se presenta como una corrección probada.

## Archivos de revisión

- `galeria.html`: todos los cuadros de las diez ventanas seleccionadas.
- `ocho_aproximaciones.jpg`: comparación de las ocho aproximaciones del video principal.
- `resumen.csv`: ventanas y decisiones posteriores.
- `acciones_todos_plateados.csv`: los 2.051 registros, con tiempo del AVI y tiempo real.
- `P01_cambios.csv` a `P10_cambios.csv`: cambios de GS/controlador de cada ventana.
- `scan_*.jpg` y `scan_*.csv`: cobertura de la búsqueda inicial en los cuatro videos.
