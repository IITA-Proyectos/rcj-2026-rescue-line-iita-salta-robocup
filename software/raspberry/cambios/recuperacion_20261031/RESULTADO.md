# Corrección de recuperación preparada — 31/10/2026

**Instalada en la Raspberry.** Respaldo remoto: `/home/iita/Desktop/respaldo_recuperacion_20261031_213617`. Se verificó la base antes de reemplazar, se comprobó sintaxis y se probaron cálculos del módulo con el OpenCV de la Raspberry sin ejecutar movimientos. Hashes locales y remotos coinciden. El servicio anterior quedó sin reiniciar; la nueva versión se carga al volver a ejecutar el programa.

SHA256 main instalado: `62a01b4bbc9b8cc82e6fd2abc548f8826e774b58d14942ccbc16e12602c2ee53`.

SHA256 módulo instalado: `36fbb3cb755fe64c23a9447dc099a8d9fb087ad46ca4974413f4e3844fcf547f`.

Base: `/home/iita/Desktop/main.py`, SHA256 `06d93b4ab53d1bbdbec2738f5c5941303d7a432c92c18f6254800b7c75bc9cd3`, capturada de la corrida 21:03. Conserva área verde 200 y respaldo de verde oscuro.

Archivos de producción: `main.py`, `recuperacion_guard.py`, `verde_oscuro.py` (este último sin cambios).

## Qué cambia

- Conserva evidencia de rama lateral en los 30 cuadros anteriores. Solo fija un lado si aparece al menos en 12 cuadros y el contrario en no más de dos. La evidencia queda congelada al comenzar el episodio, antes de retroceder.
- Da prioridad al GAP previamente confirmado frente al fallback de fragmento pequeño, con las condiciones específicas verificadas.
- Contrasta el lado final con esa rama persistente. Impide convertirla en avance recto por PALILLO o por vencimiento de ambigüedad.
- Mantiene el pivote inicial de Teensy. Al devolver seguimiento conserva el comportamiento durante desconexiones breves. Si sigue sin línea durante 350 ms, permite un complemento en el mismo sentido de hasta 450 ms cuando todavía hay cinta visible. Si no recaptura, envía GS19, que sí detiene el control de línea. No usa `speed=0` como sustituto: la Teensy no usa esa velocidad para detener su seguimiento normal.
- Dos cuadros A/D de componente conectada cierran la protección. Verdes, nuevas recuperaciones y el cambio de estado reinician el mecanismo. Las ramas de GAP no usan este cierre lateral.

No se modificaron PID, firmware, retroceso de 550 ms, factor de giro de Teensy 0,15 ni los bloques de verde.

## Verificación ejecutada

`python verificar_recuperaciones.py` usa imágenes originales, funciones de conectividad extraídas del programa real, evidencias del registro y decisiones guardadas.

- 34 episodios de la corrida 21:03: 15 decisiones problemáticas cambian; 19 se conservan, incluidos los GAP correctos y los lados correctos de comparación.
- Cambios: episodios 1/7/10/11/13/15/16/22/23/25/27/28/30/31/34. Archivo `decisiones_34.csv`.
- 11 cierres observados como correctos conservan todos sus comandos en el replay de salida: 2/3/5/6/9/12/14/18/19/21/24.
- Seis cierres sin recaptura 10/13/16/17/22/25 abandonan avance ciego y llegan a STOP al no observar recuperación en las imágenes grabadas. Archivo `cierres_verificados.csv`.
- Corrida 19:53, 22 episodios: las contradicciones de lado detectadas son solo 12 y 17, que ya habían fallado. No se invierte el lado de los casos observados como correctos.
- Bloque de detección de verdes y módulo de respaldo idénticos a la base ya probada. La validación previa de verdes abarcó 7.927 cuadros.
- Compilación sintáctica de los archivos de producción correcta.

## Límite de esta verificación

Los 15 cambios se verifican sobre decisiones y geometría registradas; no se reproduce íntegramente el proceso conectado a la cámara, ni una trayectoria física nueva. El replay de salida comprueba que la protección conserva los 11 casos indicados sobre sus imágenes existentes. Una orden distinta cambia los cuadros siguientes: hace falta una nueva corrida para comprobar recaptura, adherencia y elección de rama, especialmente en círculos y cruces.

El siguiente paso es subir después de comprobar que la base remota sigue coincidiendo, guardar respaldo y probar con crudo + CSV. No debe arrancarse otra instancia mientras una ejecución manual esté abierta.
