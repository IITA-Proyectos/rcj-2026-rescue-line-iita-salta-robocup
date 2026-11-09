# Primer cambio: respaldo de verde oscuro

Instalado en `/home/iita/Desktop/main.py` y `/home/iita/Desktop/verde_oscuro.py`.

Base extraída inmediatamente antes de editar: SHA256 `0bb4531d36900e7a761e64bc50a26475a9733c1fbd67edb92a843f28809fee02`. La única diferencia respecto de la grabación era `min_square_size=200`, que se conservó.

El detector principal permanece intacto. Si devuelve cero, se consulta una máscara con L mínimo 100, los mismos A/B y las mismas comprobaciones de negro/posición. Este respaldo exige área >max(600,min_square_size). Si acepta un verde, el crudo registra esa máscara para poder analizar la próxima corrida.

Se ejecutó el bloque real de detección extraído de los programas sobre los 7.927 PNG:

- Las 102 detecciones originales se conservan con su tipo.
- Todas las detecciones de la versión actual con área 200 se conservan con su tipo.
- Las cuatro pasadas con derecho posterior conservan el rechazo.
- Izquierdos 1135, 1266 y 6569 reconocidos. El 1266 ya pasa con la base actual de área 200.
- Verdes de un cuadro 1444 y 6698 conservados.
- Respecto de la base actual, agrega nueve cuadros: 1135 izquierda, 2501 derecha, 2577 derecha, 6569 izquierda, 7122 izquierda, 7599 derecha, 7600 derecha, 7679 derecha y 7775 derecha. Corresponden a aproximaciones de marcadores revisados visualmente.
- Detalle reproducible: `verificar_grabacion.py`, `validacion_7927_cuadros.csv`.

Validación de sintaxis local y en Raspberry; comprobación del helper con el OpenCV de la Raspberry sin ejecutar el programa de movimiento. Copias remotas verificadas por SHA256.

Backup remoto: `/home/iita/Desktop/respaldo_verde_oscuro_20261031_203855/main.py`.

No se reinició la ejecución manual abierta. El cambio entra al volver a ejecutar `main.py`. La reproducción verifica detección sobre las imágenes existentes; la trayectoria nueva se comprueba con otra corrida física.

SHA256 desplegados:

- main.py: `06d93b4ab53d1bbdbec2738f5c5941303d7a432c92c18f6254800b7c75bc9cd3`
- verde_oscuro.py: `1ee07fc3041add7146bd9ae38fd45741bbc9dbde998dde9acc61205695fce7c8`
