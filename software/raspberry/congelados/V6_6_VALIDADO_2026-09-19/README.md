# Base Raspberry validada en pista

Estos son los nueve archivos que el usuario identifico como funcionando en la prueba del 19 de septiembre de 2026. Se conservan byte por byte, incluidos sus saltos de linea, desde:

`C:\Users\villa\Downloads\V6_6_BASE_COMPLETO_CODO_GAP_2026-09-15\V6_6_BASE_COMPLETO_CODO_GAP_2026-09-15\RASPBERRY_V6_6_FIELD_REV`

No modificar esta copia de referencia. Los experimentos posteriores deben hacerse en otra copia. `SHA256SUMS` permite verificar la integridad de cada archivo; `.gitattributes` evita que Git convierta los saltos de linea.

Es una referencia de los nueve archivos seleccionados, no una distribucion completa: requiere el resto de dependencias, modelos y configuracion del paquete original. Guardarla no instala ni cambia el programa que esta ejecutando la Raspberry.

La logica coincide con `software/raspberry/paquetes/V6_6_BASE_COMPLETO_CODO_GAP_2026-09-15/RASPBERRY_V6_6_FIELD_REV` en el commit `1a4878f`; la copia de trabajo de ese paquete tiene diferentes saltos de linea.

Esta base aun tiene `ROI_ARRIBA=60` por defecto y no interpreta los avisos de rampa `0xF2/0xF3/0xF4`. El ajuste anterior de ROI de subida se hizo en otra variante, `EN_EL_ROBOT/main.py`, y no esta incorporado aqui. La subida sigue pendiente de una prueba y un cambio acotado sobre una copia de esta base.

El usuario confirmo en pista el rele HIGH durante rescate y el giro doble verde de 180 grados. Durante esta captura, el archivo local de Teensy contenia otros ajustes en curso (170 grados y verdes +/-45); esta instantanea de Raspberry no los altera.
