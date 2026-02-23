# Documentación del Sistema de Encendido

Este documento proporciona una guía para entender y solucionar problemas relacionados con el sistema de encendido para la teensy.

## Inicialización del Sistema de Encendido

El sistema de encendido se activa a través de un interruptor conectado a un pin específico en la teensy. Cuando el interruptor cambia de estado, se inician distintas secuencias de encendido o apagado.

### Configuración del Interruptor

El interruptor está conectado al pin digital 32 y se configura como un pin de entrada con pull-up interno. Cuando el interruptor está en la posición de encendido, el pin lee un valor lógico alto (1), y cuando está en la posición de apagado, el pin lee un valor lógico bajo (0).

## Bucle Principal

En el bucle principal, se manejan tres estados distintos relacionados con el sistema de encendido:

- **Apagado**: Cuando el interruptor está en la posición de apagado, todos los motores se detienen y se envía un mensaje de estado a través de la comunicación serie.
- **Reinicio**: Cuando el interruptor cambia de la posición de apagado a la de reinicio, se activa una secuencia de reinicio, indicada por el parpadeo de un LED incorporado.
- **Encendido**: Cuando el interruptor está en la posición de encendido, el LED incorporado permanece encendido, indicando que el sistema está activo y listo para funcionar.

### Manejo de Estados

- **Apagado**: Si el interruptor está en la posición de apagado, se detienen todas las funciones y se espera hasta que el interruptor cambie de estado.
- **Reinicio**: Durante el reinicio, el LED incorporado parpadea brevemente para indicar que el sistema se está reiniciando. Esto puede ser útil para diagnosticar problemas con el cambio de estado del interruptor.
- **Encendido**: Cuando el interruptor está en la posición de encendido, el sistema está activo y listo para funcionar. Esto se indica mediante el LED incorporado, que permanece encendido. En el else del codigo se puede empezar a agregar codigo.

## Solución de Problemas Relacionados con el Sistema de Encendido

Si encuentras problemas con el sistema de encendido, considera lo siguiente:

- Verifica las conexiones del interruptor y asegúrate de que estén configuradas correctamente.
- Confirma que el interruptor esté funcionando correctamente y que cambie de estado según lo esperado.
- Si el LED incorporado no muestra el estado adecuado, revisa la lógica en el código que controla su estado.

Con esta guía, deberías poder entender y solucionar problemas relacionados con el sistema de encendido en el código Arduino proporcionado.
