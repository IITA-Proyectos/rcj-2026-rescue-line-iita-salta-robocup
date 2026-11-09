# Auditoría de giros en subida y después del verde

## Resultado

El último cambio permite tomar el primer codo derecho de subida en los tres recorridos derechos de la prueba de las 14:09. Después del verde, los cinco intentos siguen sin cerrar correctamente el seguimiento: tres derechos y dos izquierdos. Son dos etapas distintas y no corresponde deshacer todo el cambio de subida ni aumentar globalmente el giro de los verdes.

La detección de los cinco verdes de esta última prueba coincide con el lado visible: tres GS2 y dos GS1. No aparece GS3. La falla común está en la transición desde la maniobra del verde hacia el seguimiento: se pierde la cinta conectada al borde inferior, el centroide puede representar otra parte del cruce y las protecciones de cresta/máscara vacía ordenan seguir recto. No existe una confirmación visual de que terminó el giro sobre la rama elegida.

Esto describe las órdenes y la evolución visual. No se dispone de CSV de la Teensy para medir el giro real, su terminación exacta, RPM, deslizamiento o distancia recorrida. Por eso no se puede concluir que falten exactamente determinados grados ni atribuir toda la falla al ángulo fijo de 39°.

## Evidencia y alcance de la revisión

- `pista_cresta_verde_20261101_140905.avi`: 1.760 cuadros, 20 FPS, 88 segundos de AVI. Se revisaron visualmente **todos los cuadros**, presentados en las 28 láminas `todos_01.jpg` a `todos_28.jpg`, y se cruzaron los 1.760 registros CSV.
- Hay cinco intentos separados por pausas y reinicios: cuadros 2–324, 325–675, 676–1044, 1045–1402 y 1403–1760. El cuadro 1 corresponde a la preparación.
- `pista_giro_cresta_20261101_135438.avi`: 6.428 cuadros y 6.428 registros CSV. Se revisaron visualmente 374 posiciones —328 cuadros distintos— que incluyen los cambios de controlador/GS y el contexto de los 21 grupos de señales verdes. **No se afirma inspección visual de los 6.428 cuadros.** Los grupos no equivalen siempre a marcas físicas distintas: un verde reaparece y puede cambiar de lado aparente durante un giro.
- Se contrastaron estos resultados con las secuencias previamente revisadas de la corrida de las 12:49, incluidos 18:33, 18:50, 19:07 y 20:11.
- Los dos videos y CSV nuevos ya estaban en la computadora. En las carpetas locales nuevas no están los PNG originales; la Raspberry no respondió por SSH durante esta revisión. Las mediciones geométricas nuevas usan el panel de máscara del AVI y se identifican como tales. No se reconstruyeron falsamente imágenes crudas desde el video.
- Se verificó que el archivo de cámara enumera los cuadros en orden y que sus cantidades coinciden con los videos. El log declara cero cuadros crudos perdidos; no se pudo verificar localmente la presencia de esos PNG.

Los tiempos de la tabla son **del video**, `(n-1)/20`. Las duraciones de órdenes se calculan con `cuadros.csv.t`, excluyendo los saltos entre intentos; no se confunden con la duración del AVI.

## Los cinco intentos de la última prueba

| Intento | Lado detectado | Primer verde en AVI | Primer giro 0 protegido después del verde | Resultado visual |
|---|---|---|---|---|
| 1 | Derecha, GS2, f243–253 | 00:12.10 | f275, 00:13.70 | La cinta sale hacia el borde izquierdo; máscara vacía, cresta recto y finalmente sin recuperación. No vuelve a un seguimiento estable antes del reinicio. |
| 2 | Derecha, GS2, f569–578 | 00:28.40 | f599, 00:29.90 | Repite la salida por la izquierda y la secuencia de órdenes rectas. |
| 3 | Derecha, GS2, f949–957 | 00:47.40 | f982, 00:49.05 | Repite el patrón de los dos anteriores. |
| 4 | Izquierda, GS1, f1239–1252 | 01:01.90 | f1265, 01:03.20 | La línea permanece visible como diagonal/franja, pero deja de tocar el borde inferior. Cresta anula el giro. Después vuelve intermitentemente el centroide, con oscilaciones; termina perdiéndose otra vez. |
| 5 | Izquierda, GS1, f1617–1631 | 01:20.80 | f1643, 01:22.10 | Misma primera anulación que el intento 4, luego órdenes alternantes y nueva pérdida al terminar el video. |

**No se envía GS4 ni GS19 en ninguno de los cinco intentos.** No es una recuperación disparada que haya elegido mal el lado. El sistema está impidiendo que se dispare y, cuando manda GS0 con ángulo 0, solicita seguimiento recto. **Ángulo 0 no es una orden de detenerse.**

Cuadros con órdenes rectas impuestas por `mascara-vacia`, `cresta-recto` o `sin-recup` después del último verde:

| Intento | Cuadros | Tiempo real observado, suma de intervalos |
|---|---:|---:|
| 1 | 50 | 1,473 s |
| 2 | 66 | 1,993 s |
| 3 | 63 | 1,887 s |
| 4 | 71 | 2,291 s |
| 5 | 61 | 1,959 s |

Estas son sumas de intervalos observados. En los izquierdos hay intervalos separados por reapariciones del control normal; no se presentan como un único bloqueo continuo. No se sabe cuánto habría durado cada pérdida sin la intervención/reinicio del usuario.

## Qué cambió Claude y por qué no alcanza

Los MD5 locales coinciden con los indicados en el mensaje del despliegue:

- `main.py`: `8143f9485f0c01c490b909171fa9e05a`.
- `rampa_transicion.py`: `4f1c0198b313ff488a06f06c5f75fd5e`.

Además, el SHA256 de `main.py` coincide con el guardado en los parámetros de la corrida 14:09: `df73beb17034566873db5bf2d32655f73a8aa8ac12cc7036e662db85fe5f5097`. Esto vincula el código local revisado con el programa de esa prueba. No verifica el firmware grabado en la Teensy ni el estado actual de la Raspberry apagada.

El cambio en `main.py`, frente al programa de las 12:49, es una condición adicional en un único lugar: evita `_corte_paisaje` mientras `tras_giro()` sea verdadero. El módulo nuevo detecta una rama lateral que se aproxima durante cuatro avances y abre una ventana de cuatro segundos.

Problemas que deja abiertos:

1. La ventana comienza en el **codo anterior**, no al terminar el verde. En los tres recorridos derechos, el replay aproximado con la máscara del AVI sitúa el desarme en f166, f492 y f872. El primer verde llega unos 3,1–3,2 s después. Cuando aparece la pérdida posterior, ya pasaron unos 4,5 s: la ventana de cuatro segundos está vencida. El replay es aproximado porque no están los PNG, pero sus transiciones coinciden con la salida de `rampa-transicion` a `rampa-linea` registrada en los tres recorridos.
2. En los izquierdos no hay una ventana vigente al pasar el verde. `tras_giro` no se activa directamente por GS1/GS2, y parte de la aproximación se procesa como `rampa-centra`, no como `rampa-linea`.
3. Evitar `_corte_paisaje` **no evita** la protección posterior `rampa-cresta-recto` cuando `_solo_mi_linea` no encuentra una componente que toque abajo.
4. Tampoco evita `rampa-sin-recup`, que vuelve a imponer 0 durante la subida y su transición posterior.
5. El bloqueo de recuperación tras el verde tiene otra regla independiente: con máscara completamente vacía impone `v66-bloqueo-mascara-vacia-recto`.
6. Aunque se eliminen esas anulaciones, el centroide de todo un cruce no certifica la rama elegida por el verde. En varios cuadros posteriores al GS2 calcula izquierda; en los izquierdos aparecen órdenes hacia el otro lado antes de que el robot quede siguiendo la rama. Eso no demuestra qué motores actuaron durante la maniobra fija, pero sí muestra por qué devolver simplemente el centroide no garantiza completar el giro.

## Raspberry y Teensy: quién controla cada fase

El fuente local de la Teensy usa:

- GS2: comprobación del verde, avance a 20 durante 800 ms y `runAngle(25, FORWARD, 39)`.
- GS1: comprobación del verde, avance a 20 durante 800 ms y `runAngle(35, FORWARD, -39)`.

Durante esa rutina, los ángulos que continúa enviando la Pi no sustituyen el objetivo de `runAngle`. El CSV de cámara dice qué se envió, no el yaw ejecutado. Después, si vuelve a seguimiento normal con GS0 y ángulo 0, el robot puede avanzar sin haber recuperado la rama.

El número del protocolo de cámara no es un ángulo de giro físico: positivo pide izquierda y negativo derecha. El signo de `runAngle` es distinto: positivo corresponde al giro derecho. Mezclarlos lleva a conclusiones incorrectas sobre sobre giro o giro insuficiente.

## Qué funciona y debe conservarse

- En los tres primeros recorridos de las 14:09 se ve el primer codo derecho de subida, anterior al verde: se libera la transición, se vuelve a encontrar cinta y el robot continúa hasta la marca verde. No corresponde describir todo ese cambio como inútil. Esto acredita esa secuencia, no una pista completa sin fallas.
- Las aproximaciones rectas de los cinco recorridos permanecen controladas hasta sus cambios de geometría. La protección que permitió subir recto sigue siendo necesaria.
- En la corrida de las 13:54, los verdes del piso de f2421, f2487 y f4962 ofrecen referencias de reencuentro de cinta posterior sin la persistencia de la orden `rampa-cresta-recto`. Son referencias locales de seguimiento recuperado, no prueba de éxito de todos los verdes de esa corrida.
- Otros grupos del piso y de bajada también muestran pérdidas o dudas. No se etiquetan todos como correctos por el mero hecho de haber enviado un GS.
- En las cinco pruebas nuevas el lado detectado es consistente. Cambiar los umbrales LAB no resuelve este fallo de cierre.

## Resolución acotada que se desprende de la evidencia

Hay que separar **codo sin verde** de **salida del giro verde**.

Para el codo sin verde: conservar la liberación de transición que ya permite tomar el codo, y asegurar que la decisión de curva no vuelva a convertirse en avance recto mientras se está completando esa misma curva. El reconocimiento debe usar evidencia temporal de rama conectada, no cualquier borde oscuro del fondo. Una banda de cresta puede parecer una rama en un solo cuadro.

Para el verde en subida: agregar un cierre de maniobra específico, armado por el verde confirmado en subida y conservando el lado elegido. Debe conocer el fin de la maniobra de la Teensy —preferentemente con aviso explícito— y recuperar la rama por cámara antes de entregar el control normal. Durante ese cierre no deben anularlo las órdenes rectas genéricas de cresta, ni debe cambiar de rama porque otro brazo del cruce domine el centroide.

La salida del cierre debe exigir cinta coherente en más de una banda y durante varios cuadros, para distinguir cinta atravesada de una rama realmente orientada hacia delante. Si solo queda un fragmento lateral compatible, el seguimiento de ese fragmento debe conservar su identidad temporal. Si no hay evidencia útil, se necesita una terminación acotada que no transforme el desconocimiento en avance recto indefinido.

El alcance debe ser **verde simple iniciado durante subida**, con retorno a comportamiento actual al completar el cierre. Los verdes del piso, los dobles, las subidas rectas y las recuperaciones generales quedan como controles de regresión. La transición a LLANO puede ocurrir antes de terminar de recuperar la rama, por lo que no debe borrar automáticamente ese episodio.

No se propone aumentar de forma global 39°, 800 ms, la ventana de cuatro segundos ni el tiempo de recuperación: no hay medición suficiente para justificar esos valores y no corrigen la falta de confirmación visual. Para saber si además hay que corregir la colocación física previa al giro, se necesita contrastar el fin real del avance/giro con la imagen; no se inventan RPM ni yaw desde el CSV de cámara.

## Entregables y estado

- `galeria.html`: los 1.760 cuadros de la última corrida y las 12 láminas de comparación anterior.
- `comparacion_cinco.jpg`: cuatro momentos por intento.
- `resumen_cinco_intentos.csv`: resultados y duración de órdenes rectas.
- `acciones_cinco_intentos.csv`: todos los cambios de GS/controlador, con tiempo real.
- `metricas_1760.csv`: mediciones de la máscara mostrada en el AVI; no se confunden con la máscara interna recortada del controlador.
- `replay_aproximado_tras_giro.csv`: comprobación de la ventana temporal con máscara del video.
- `inventario.csv`: archivos, tamaños y SHA256 locales.

**En esta auditoría no se modificó ni instaló ningún programa del robot.** El análisis identifica el cambio que hay que preparar; no se presenta todavía un parche como probado en el robot. El plateado queda fuera de este cambio, según la prioridad del usuario.
