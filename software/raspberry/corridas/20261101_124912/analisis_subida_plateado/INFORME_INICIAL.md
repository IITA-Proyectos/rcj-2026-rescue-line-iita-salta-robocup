# Giros de subida señalados por el usuario

Video completo: pista_doble_dato_20261101_124912.avi, 24341 cuadros, 20 FPS, 20:17.05. Ultimo cuadro legible. Tiempos siguientes son del AVI, no del reloj real del CSV.

Respaldo diagnostico_doble_20261101.tar: SHA256 local/remoto 6b6e38982545860c90042073b101db2323dd06b215b554f0c657b6470ce8b639. Incluye dos corridas (12:49:12 y 12:38:04), crudos, CSV de camara, logs y cinco archivos del programa.

## Hallazgo confirmado

Se revisaron visualmente secuencias muestreadas de 18:27-18:38 y 18:46-18:57, cruzando cada etiqueta con cuadros.csv. No se afirma haber inspeccionado todos los cuadros de la corrida.

La linea forma un codo a la derecha al final de la subida. Antes de ejecutar el codo, el control sigue en subida y centra/rectifica; despues se pierde la conexion inferior y la proteccion de cresta manda seguir recto.

Primer intento: rampa-transicion-sin-geometria manda 0 en 18:35.85-18:36.10; rampa-cresta-recto manda 0 en 18:36.15-18:38.45; luego rampa-sin-recup sigue en 0. Previamente la transicion alcanza +15 (izquierda), aunque el futuro codo sale a la derecha: la geometria cercana aun representa el tramo de entrada, no la rama que sigue.

Segundo intento: rampa-transicion-sin-geometria manda 0 en 18:50.35-18:50.65; rampa-cresta-recto manda 0 en 18:50.70-18:53.00; luego rampa-sin-recup manda 0 hasta 18:53.35. Desde 18:53.40 rampa-linea vuelve, y posteriormente aparecen ordenes a la derecha; visualmente ya no se hizo el codo a tiempo.

La falla no se resuelve solo aumentando el limite de +/-15: hay dos anulaciones posteriores de giro (cresta y sin recuperacion), y ademas el controlador necesita distinguir una rama lateral de una cinta corta recta. Tampoco conviene quitar globalmente las protecciones de cresta que hicieron funcionar las subidas rectas.

## Resolucion a preparar y verificar

Detectar evidencia temporal de codo conectado antes de perder la linea inferior, usando la imagen sin el recorte de paisaje. Solo con evidencia suficiente de rama lateral, entregar control al giro y evitar que los modos rectos posteriores borren esa decision. Mantener el comportamiento actual cuando la cinta es recta o realmente desaparece al coronar la rampa. Verificar reproduciendo los dos casos fallidos y las subidas rectas exitosas de grabaciones anteriores antes de instalar.

## Plateado pendiente

Este CSV solo contiene estado linea y silver=0. Ese campo no acredita la lectura real del APDS de la Teensy. No se dispone de CSV Teensy de esta corrida. Se necesitan ubicar visualmente las entradas al plateado para analizar orientacion y ordenes de camara; no se atribuye todavia la causa del plateado al mismo fallo de subida. La orientacion debe resolverse con imagen, segun solicitud del usuario; no se incorpora ultrasonido.

No se modifico ni instalo programa en esta descarga.
