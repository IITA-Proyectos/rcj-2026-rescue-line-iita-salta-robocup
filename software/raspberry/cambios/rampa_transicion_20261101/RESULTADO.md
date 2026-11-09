# RAMPA-TRANSICION-1 — instalado 01/11/2026

Instalado y comprobado por hashes, compilacion y prueba sintetica remota. Respaldo: /home/iita/Desktop/respaldo_rampa_transicion_20261101_110703. No se reinicio ni ejecuto el robot. La nueva version se carga al iniciar otra ejecucion.

Conserva recuperacion RECUP-REENGANCHE-3. No incluye candidata4 ni correccion de identidad del fragmento del codo: siguen separadas.

Implementacion: solo SUBE vigente, ROI cresta y CTRL atan2. Se arma despues de20 cuadros consecutivos rampa-recta; conserva intactas sus ordenes. Solo reemplaza rampa-linea despues de armarse. Ajusta una recta a los centros medianos entre filas94–118: al menos8 filas, extension14, ancho5–90, span<=95, residual<=3px. Compensa perspectiva como el controlador recto existente, centra con ganancia30 y limita a +/-15 de protocolo. Si falta geometria, mantiene cero hasta1,5s desde ultima geometria valida, igual al plazo de proteccion de cresta existente; despues desarma esta ayuda y devuelve el comportamiento previo. Se reinicia al dejar SUBE, pausas>0,5s o los reinicios de proteccion/estados existentes. Los modos cresta, centrado y cinta corta conservan sus ordenes. Colores se procesan despues y conservan prioridad.

La limitacion de15 no es un angulo fisico de giro y no garantiza por si sola atravesar centrado. Es un limite inicial para ensayo, pendiente de comprobacion fisica. No se cambiaron motores, velocidades, firmware ni el modulo de recuperacion.

Validacion: replay de8354 cuadros nuevos,7420 de la prueba anterior y18331 de la anterior. Se alteran497/38/69 cuadros respectivamente; todos eran rampa-linea con SUBE y ayuda armada. Ningun cuadro de rampa-recta/centra/cresta se altera. Las cuatro subidas senaladas tienen intervencion desde su primer abandono de recta; las dos subidas de control (00:29 y05:43 del video nuevo) conservan sus ordenes. Bloque de verdes identico. Ver replay_cambios.csv y verificar.py. Estos son cambios de orden sobre imagenes grabadas, no prueba de las trayectorias que produciran.

Hashes:
main.py eeb98adf876ff7fdc3545e22336fcd0576b3e7c16893a1f05d93726b8c4392cf
rampa_transicion.py ed46092fd1854b5c3c5e6251f58ad8c059e3839d4fdff581efc832a47ca580d0
recuperacion_guard.py c3333b7e51f479cea041c656402438dc6a818f5d34ec4971f93ce0d910c9f52f

En la siguiente prueba, registrar video+crudo y CSV de Teensy; comparar misma entrada y ascenso hasta bajar completamente. Buscar RAMPA-TRANSICION-1 al iniciar y rampa-transicion-cerca/sin-geometria en cuadros.csv. Detener y revisar si la cinta lateral se aleja pese a la correccion limitada; no contar como exito solo haber llegado al borde.
