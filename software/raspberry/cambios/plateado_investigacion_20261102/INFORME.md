# Plateado: investigación y calibración aislada — 2026-11-02

## Resultado

La cámara puede aportar una máscara y una orientación de la franja, pero una calibración de color sola no distingue de forma fiable metal, piso sombreado y reflejos. No se ha demostrado un detector listo para competencia. Se creó y aplicó un calibrador auxiliar a cuadros guardados; su perfil tiene `enabled_for_control: false`. No se modificaron main.py, la recuperación, los verdes, la rampa, la Teensy ni los ajustes compartidos de cámara.

## Fuentes primarias revisadas

1. [System Override, documentación de equipo 2026](https://robocup-junior.github.io/rcj-rescue-docs-site/2026/line/system-override/). Describe detección de plateado con cámara y una comprobación con sensor RGB para reducir falsos positivos. Es el enfoque más cercano a nuestra combinación cámara + sensor de piso. Su montaje OpenMV y su perspectiva son diferentes. Se leyó la documentación, no el archivo de código enlazado, cuyo acceso desde el navegador falló.
2. [FusionZero 2026, detector real](https://github.com/BlanketOmelette/FusionZero-Robocup-2026/blob/beb3ceb8f61f244304efe36ec6757f4aa338bfa8/1_robot/behaviours/silver_detector.py), [captura de muestras](https://github.com/BlanketOmelette/FusionZero-Robocup-2026/blob/beb3ceb8f61f244304efe36ec6757f4aa338bfa8/1_robot/tools/capture_silver_dataset.py) y [metadatos](https://github.com/BlanketOmelette/FusionZero-Robocup-2026/blob/beb3ceb8f61f244304efe36ec6757f4aa338bfa8/2_assets/models/silver/silver_detector_meta.json). Clasificador de imágenes silver/no_silver con TorchScript, procesamiento separado y entrada 96×96. Los metadatos declaran ShuffleNet, sin aumento de datos, y resultados propios sobre un conjunto pequeño. No se transfieren su umbral ni sus resultados a nuestra cámara. La clasificación no produce bordes ni posición para alinearse. Se inspeccionó código; no se ejecutaron modelos ajenos.
3. [FusionZero International, sensor](https://github.com/D-uality/FusionZero-Robocup-International/blob/HEAD/1_international/hardware/silver_sensor.py). Su calibración registra mínimos y máximos durante 10 segundos y normaliza un sensor analógico. No es una calibración de cámara ni del APDS; copiar sus números aquí sería incorrecto.
4. [OpenMV, documentación oficial de cámara](https://docs.openmv.io/v4.5.6/library/omv.sensor.html). Explica estabilizar los cuadros tras cambios y controlar ganancia/balance para seguimiento de color. Estos controles requieren adaptación al hardware. Cambiar globalmente la exposición o el balance de nuestra cámara podría alterar los verdes y la línea: no se hizo.
5. [Airborne 2025](https://github.com/JamesBond6873/Airborne_Rescue_Line_2025). Publica detección mediante modelos y archivos para silver strip. Se revisaron README y árbol de archivos; no se probó su precisión ni se descargaron pesos. Es una alternativa futura, no evidencia de que funcione en nuestras imágenes.

## Calibración aplicada a nuestras imágenes

`calibrar_lab.py` adapta la idea de seleccionar muestras de color, sin copiar código OpenMV ni sus rangos numéricos. Usa LAB de OpenCV de 8 bits. RGB y LAB son representaciones de la misma imagen: cambiar de espacio no recupera detalles perdidos por saturación ni identifica por sí mismo el material.

Se eligieron manualmente dos regiones pequeñas de plateado para ajustar, dos de plateado de otros cuadros para evaluar y cuatro negativas: piso blanco, cinta negra, piso de otra zona y piso junto a un borde. Las regiones y sus cuadros están en `muestras_provisionales.json`; las imágenes `prueba_calibracion/muestra_*.png` permiten revisar cada selección. No son etiquetas completas de la pista ni muestras de distintas sedes.

Perfil obtenido: LAB inferior `[59,117,123]`, superior `[137,137,140]`, a partir de 240 píxeles. En los dos recortes positivos reservados aceptó el 100% de sus píxeles con el brillo original. Esto NO es 100% de detección de entradas.

Se simuló multiplicar el brillo por 0.6, 0.8, 1.0, 1.2 y 1.4. Con 0.6, las regiones positivas conservaron sólo 55% y 34% de sus píxeles. Un recorte de piso que originalmente no entraba en la máscara pasó a entrar al 100%; otro negativo llegó al 90%. La variación sintética no reproduce el sol, sombras coloreadas ni reflejos especulares, pero ya refuta que este rango fijo sea suficiente.

Reproducción desde la carpeta software, en PowerShell:

```powershell
python raspberry/cambios/plateado_investigacion_20261102/calibrar_lab.py raspberry/cambios/plateado_investigacion_20261102/muestras_provisionales.json --out raspberry/cambios/plateado_investigacion_20261102/prueba_calibracion
```

## Propuesta para aislar la entrada

La recomendación es propia, basada en esas fuentes y en nuestros cuadros; no es un algoritmo ya validado de otro equipo.

1. Generar candidatos en una copia de la imagen. Combinar color respecto al piso cercano, contraste, bordes largos, ancho y continuidad de la franja. Medir si la imagen está demasiado saturada; en ese caso reducir confianza. El brillo absoluto no confirma plateado.
2. Identificar la franja ANTES de que el giro de recuperación la saque de cuadro. Exigir consistencia temporal y conservar la identidad de esa misma franja. El prototipo geométrico anterior todavía produce falsos con juntas y bordes; no está habilitado para conducir.
3. Estimar orientación de la franja sobre el plano del piso, con calibración de perspectiva. Para centrarse lateralmente hace falta además conservar el punto donde la línea original llega a la franja. El centro de una franja recortada por los límites de imagen no indica el centro de la entrada. No seleccionar automáticamente el mayor fragmento negro después de recuperar.
4. Habilitar una corrección especial sólo mientras esa entrada esté identificada con confianza, dentro de una región alcanzable y con límites de tiempo y desplazamiento. Estar después de una recuperación izquierda no basta para activarla. Si se pierde la referencia, indicar pose desconocida; no asumir que ya está recto ni imponer recto durante segundos.
5. Conservar el sensor de piso como confirmación final del plateado. La cámara anticipa y orienta. Esto no resuelve por sí solo una maniobra posterior de Teensy que vuelva a desalinear el robot; debe contrastarse con el firmware realmente cargado y su registro.

## Calibración en competencia y criterio de aceptación

Tomar imágenes con la misma cámara, altura y ajustes de uso: plateado de frente y oblicuo; piso blanco, negro, juntas, bordes de rampa, verdes y reflejos como negativos. Repetir bajo las luces reales, sombra y los cambios de iluminación previsibles. Separar recorridos completos para evaluación: no mezclar cuadros contiguos de un mismo paso entre ajuste y evaluación.

Elegir parámetros con positivos Y negativos y evaluar detecciones persistentes por evento, no sólo píxeles o cuadros. Revisar todas las recuperaciones y curvas laterales, incluidas las que funcionaban. Primero ejecutar como observador y medir el tiempo por cuadro en la Raspberry; un detector auxiliar también puede afectar al seguimiento si consume demasiado procesamiento.

No hay validación con las luces de la sede, calibración de perspectiva ni control de alineación implementado en este cambio. No se puede prometer cero falsos ni funcionamiento bajo cualquier iluminación. El siguiente cambio de conducción debe esperar a que la identificación aislada y el seguimiento de la entrada superen esas comprobaciones.
