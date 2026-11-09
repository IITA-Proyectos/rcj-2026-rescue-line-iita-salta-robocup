# Reenganche aislado del codo — RECUP-REENGANCHE-2

Instalado en Raspberry el 31/10/2026. Respaldo: `/home/iita/Desktop/respaldo_reenganche_20261031_220939`. No se inicio el robot ni se reinicio el servicio. La version nueva se carga al iniciar una nueva ejecucion.

## Patron y alcance

En los 11 codos repetidos la rama elegida es coherente con la evidencia previa, pero despues del pivote no hay linea conectada. El fragmento visible queda al otro lado del giro inicial: izquierda en los diez derechos, derecha en el izquierdo. Continuar imponiendo el signo de la rama no equivale a apuntar hacia la cinta que ahora muestra la camara. No se afirma haber medido el giro real ni descartado deslizamiento: no hay CSV Teensy de esta corrida.

Se agrega un UNICO reintento en el punto donde la proteccion anterior iba a enviar STOP. Requiere rama previa persistente y un fragmento lateral visto hace menos de 1,5 segundos. Guarda la componente negra mas cercana a la parte baja de la imagen, con area minima 60 px y extension hasta fila 65; toma el centro de sus ultimas seis filas. El error lateral debe superar 0,35. Durante GS4 solo guarda esa informacion: no cambia el giro original.

Al fallar el cierre existente, pivota hacia la ultima posicion del fragmento (angulo de protocolo +/-85), aunque ese lado sea opuesto al giro anterior. Sin componente conectada no manda avance recto. Con componente conectada deja actuar al seguidor. El reintento termina con tres cuadros consecutivos con error cercano <=0,45 y diferencia entre bandas cercana/lejana <=0,50; o con STOP a un segundo. Estas tolerancias no certifican centrado perfecto: permiten volver al seguidor. No repite el reintento dentro del mismo episodio. Verdes y cambios de estado reinician la proteccion existente.

El segundo adicional es un limite inicial de ensayo, no un tiempo optimo medido. El movimiento nuevo necesita prueba fisica: una grabacion antigua no puede mostrar los cuadros que producira una orden distinta.

## Verificacion

- Replay de todas las curvas de la corrida de 69 episodios: cambian exactamente 4,18,39,40,41,48,50,66,67,68,69, en su primer STOP anterior. Los diez derechos buscan el fragmento a izquierda y el izquierdo a derecha.
- Ninguna recuperacion clasificada como recaptura visible cambia sus comandos en el replay. Los GAP conservan su codigo y decisiones. Los 53 casos correctos quedan preservados en las trayectorias grabadas; esto no demuestra invariancia ante cualquier imagen futura.
- Once cierres correctos de la corrida anterior tambien conservan sus comandos.
- El metodo de decision y el cierre anterior son identicos por comparacion de AST; el bloque de verdes es identico. No se modifico firmware, retroceso de 550 ms ni parametros de motores.
- Cinco pruebas verifican signo hacia fragmento, rechazo de evidencia ausente/vencida, limite temporal sin reintentos infinitos, cierre geometrico y reinicio entre episodios.
- Compilacion local/remota, prueba sintetica remota y hashes coincidentes. No se ejecuto main durante la validacion.

Los tres episodios transitorios 43/47/52, el GAP mal clasificado 13 y la salida sobre madera 12 NO se declaran resueltos por este cambio. Se mantienen separados para no ampliar el parche del codo con comportamientos de otra causa.

## Proxima prueba

Hacer diez intentos del codo repetido y algunos del codo que ya funciona, con crudo y CSV. Buscar en el log `[RECUP-REENGANCHE]`; el registro por cuadro usa `recup-guard-reenganche`. Comprobar si el fragmento baja hasta conectar, si vuelve a seguir la salida correcta y si el limite detiene cuando no alcanza. Si solo vuelve al tramo de entrada y repite la falla, no contar eso como exito: indicaria que hace falta corregir la posicion de aproximacion, no aumentar mas el tiempo de giro.

Raspberry:

```bash
sudo systemctl stop iita-robot.service
cd /home/iita/Desktop
N="reenganche_$(date +%Y%m%d_%H%M%S)"
GRABAR_CRUDO="/home/iita/crudo_$N" GRABAR="/home/iita/pista_$N.avi" LOG_FILE="/home/iita/pista_$N.log" python3 -u main.py
```

PowerShell en la computadora, antes de mover el robot (cerrar otro monitor serial que use COM6):

```powershell
Set-Location "C:\Users\villa\rcj-2026-rescue-line-iita-salta-robocup-priority-fixes\software\teensy\firmware"
python tools/registrar_diagnostico.py COM6 ("reenganche_" + (Get-Date -Format "MMdd_HHmmss") + ".csv") --nota "RECUP-REENGANCHE-2; codo repetido; retroceso 550ms; K giro 0.15"
```

## Archivos instalados

- main.py SHA256: 991df6bf36ce29d61457df8e46a9a67e6ab7b96c9f3d911a3d1dd6051f20e098
- recuperacion_guard.py SHA256: 7beb66b2a11786f20fba0ab512f9ccae0149d2bda1cddb3e77d982b4cefc0845
