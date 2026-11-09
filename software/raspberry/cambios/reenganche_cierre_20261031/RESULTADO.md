# Cierre de reenganche â€” RECUP-REENGANCHE-3

Estado: INSTALADO y verificado el 01/11/2026. Hashes local/remoto coinciden; compilacion y prueba sintetica remota correctas. Respaldo: /home/iita/Desktop/respaldo_reenganche_20261101_103103. No se reinicio el servicio: el proceso que ya estaba activo conserva la version 2 hasta la proxima ejecucion. Helper SHA256 c3333b7e51f479cea041c656402438dc6a818f5d34ec4971f93ce0d910c9f52f. La candidata 4 no se instalo.

La nueva corrida 20261031_221132 esta descargada completa: video, log, 7420 PNG (cero perdidos declarados), cuadros.csv, parametros y fuentes. Archivo corrida_221132.tar SHA256 5ea7a7bae3c2f7998d80fa7b85df16fa2283c5589b1d30087397f3ac5ba19896, coincidente con Raspberry.

Se revisaron seis cuadros de cada uno de los 29 episodios en cinco laminas. No se encontro CSV nuevo de Teensy en la carpeta habitual. Esta revision rapida no asigna causalidad mecanica a todas las salidas ni reemplaza un analisis temporal exhaustivo.

Falla aislada y comprobada: episodio 12, AVI 01:44,70 al inicio, STOP en cuadro 2172 (01:48,55 AVI). El reenganche recupera cinta conectada desde alrededor de f2157; el reloj de un segundo vence mientras el seguidor la acomoda. En f2172 la componente conectada tiene 3258 pixeles, error cercano +0,175 y diferencia entre bandas -0,51875. El limite anterior de orientacion 0,50 y tres cuadros centrados no se cumple y se manda GS19, pese a que ya existe seguimiento.

Cambio unico respecto de version 2: al vencer un segundo, si durante tres cuadros consecutivos hay componente conectada con ambas bandas observables, error cercano <=0,80 y diferencia entre bandas <=0,65, devuelve el control normal al seguidor en lugar de STOP. La condicion temprana de tres cuadros centrados queda igual; sin cinta recuperada permanece STOP, sin ampliar el tiempo de giro ni repetir intentos.

Verificacion: seis pruebas de signo, evidencia, limite, reinicio y cierre; compilacion. Replay de todas las curvas de los 29 episodios: cambia SOLO el episodio 12, primer cambio exacto en f2172: STOP -> conservar comando normal. Los otros episodios, incluidos los reenganches 1 y 25, conservan las acciones en la ventana revisada. Los GAP, verdes y main.py no cambian. Una grabacion antigua no demuestra el recorrido fisico despues de suprimir el STOP: eso requiere nueva prueba.

No se declaran corregidos por este cambio los otros STOP de episodios 5,27,29 ni las oscilaciones visibles en varios codos. En particular 27 muestra casi solo piso sin cinta util y no corresponde ampliar su busqueda a ciegas. Quedan para analisis separado.
