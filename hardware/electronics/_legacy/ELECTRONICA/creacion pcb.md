# Introducción a Easy EDA: Creación de PCB y Diagramas Esquemáticos
## ¿Qué es Easy EDA?
Easy EDA es una herramienta de diseño electrónica basada en la nube que permite a los usuarios crear esquemas de circuitos, diseñar PCB y colaborar en proyectos de forma colaborativa, todo dentro de una interfaz intuitiva y fácil de usar.
## Objetivo de esta Documentación
El objetivo principal de esta documentación es proporcionarte una introducción clara y detallada al uso de Easy EDA para la creación de PCB y diagramas esquemáticos. Usando nuestra PCB ya fabricada como base para dar las explicaciones

##

## Conexiones de componentes usados

### Ultrasonidos
| Sensor | Trigger | Echo |
|--------|---------|------|
| Right  |    8    |   9  |
| Left   |   11    |  10  |
| Front  |   39    |  33  |

## Servos

| Servo  | Pin | 
|--------|-----|
| Left   |  14 | 
| Right  |  15 | 
| Lift   |  12 | 
| Deposit|  23 | 

## Switch ON/OFF

| Tipo  | PIN | Switch |
|-------|-----|--------|
| INPUT Pullup |  32 |      |

## Motores

| Motor | PWM | Dirección | Encoder (FL) |
|-------|-----|-----------|--------------|
| BL (Back Left)   |  29 |   28  |     27     |
| FL (Front Left)  |   7 |    6  |      5     |
| BR (Back Right)  |  36 |   37  |     38     |
| FR (Front Right) |   4 |    3  |      2     |

## ToF

| Sensor | VCC  | GND  | SDA | SCL |
|--------|------|------|-----|-----|
| Sensor 1 | 3.3V | GND  | 17  | 16  |
| Sensor 2 | 3.3V | GND  | 25  | 24  |


## Comunicacion serial entre Rpi y Teensy
| RX 5  | TX 5 |
|--------|------|

## Pinout Teensy 4.1
![teensy4.1](/Creacion_PCB/imagenes/image.png)

## Diagrama esquematico
Un diagrama esquemático es una representación gráfica de un circuito electrónico que utiliza símbolos estándar para representar componentes y conexiones. Se utiliza para planificar, diseñar y comprender la estructura y el funcionamiento de un circuito electrónico.

### Diagrama esquematico usado por nosotros para la fabricacion de la PCB
![nUESTRO](/Creacion_PCB/imagenes/Schematic_Trabajo-roboliga_2024-05-02.png)


## Pasos para hacer un diagrama esquematico

### Paso 1: Preparación
Identifica los Componentes: Antes de comenzar, asegúrate de tener una lista de todos los componentes.
Reúne la Información Relevante: Obtén las especificaciones técnicas de los componentes, incluyendo sus pines, conexiones eléctricas, y cualquier otra información importante.

### Paso 2: Abrir Easy EDA y Crear un Nuevo Proyecto
Crear un Nuevo Proyecto: Una vez que hayas iniciado sesión, crea un nuevo proyecto desde el menú.
![alt text](/Creacion_PCB/imagenes/image-8.png)
### Paso 3: Agregar Componentes
Seleccionar Componentes: Utiliza la biblioteca (los componentes que use para crear la PCB mayormente la encontre en las contribuciones de los usuarios) de Easy EDA para buscar y seleccionar los componentes que necesitas para tu diseño.
![alt text](/Creacion_PCB/imagenes/image-9.png)
Conexión de Componentes: Conecta los componentes entre sí utilizando líneas para representar las conexiones eléctricas. Asegúrate de seguir las conexiones adecuadas de acuerdo con las especificaciones de los componentes.

### Paso 4: Etiquetar y Anotar
Etiquetar Componentes: Agrega etiquetas a los componentes y conexiones para identificar claramente cada elemento en el diagrama.
Anotar el Esquema: Anota el esquema con números de referencia para cada componente y conexión. Esto ayudará a mantener un registro ordenado y facilitará futuras modificaciones.

### Paso 5: Revisión y Verificación
Revisión de Conexiones: Repasa cuidadosamente el diagrama para asegurarte de que todas las conexiones estén correctamente establecidas y no haya errores.
Verificación de Especificaciones: Verifica las especificaciones de los componentes y las conexiones para asegurarte de que todo esté en orden y cumpla con tus requisitos.

Paso 6: Guardar y Compartir
Guardar el Proyecto: Guarda tu proyecto en Easy EDA para poder acceder a él más tarde y realizar modificaciones si es necesario.


## Creacion de PCB

Una vez que hayas diseñado tu diagrama esquemático en EasyEDA, puedes proceder a crear la PCB siguiendo estos pasos:

### Paso 1: Convertir a PCB
1. Abre tu proyecto en EasyEDA.
2. Selecciona la opción "Convertir a PCB" desde la interfaz.
![alt text](/Creacion_PCB/imagenes/image-1.png)
3. EasyEDA transferirá automáticamente tus componentes al entorno de la PCB.

### Paso 2: Enrutamiento de Pistas
1. Utiliza la herramienta de "autoroute" para conectar los componentes.
![alt text](/Creacion_PCB/imagenes/image-2.png)
2. Asegúrate de seguir las reglas de diseño para evitar que se choquen las pistas en nuestro caso usamos nets o uniones de esta manera
![alt text](/Creacion_PCB/imagenes/image-4.png)

### Paso 3: Agregar Capas de Cobre
1. Si es necesario, agrega capas de cobre adicionales para pistas o planos de tierra.

### Paso 4: Revisión y Verificación
1. Realiza una revisión exhaustiva de tu diseño para garantizar la corrección de las conexiones y el enrutamiento de las pistas.
2. Verifica que el diseño cumpla con tus especificaciones y requisitos.

### Paso 5: Generar Archivos Gerber
1. Utiliza la función integrada de EasyEDA para generar los archivos Gerber necesarios para la fabricación de la PCB.
![alt text](/Creacion_PCB/imagenes/image-5.png)
### Paso 6: Envío a Fabricación
1. Envía los archivos Gerber a un fabricante de PCB para que produzcan físicamente tu placa.


## Mejoras con la version anterior
### Version Anterior
![alt text](image-6.png)

### Version Actual
![alt text](image-7.png)


Al observar detenidamente, se pueden notar varias mejoras importantes en nuestro diseño. Una de ellas es la optimización en la colocación de componentes, lo que permite que los cables utilizados sean más cortos. Esto no solo contribuye a una apariencia más ordenada, sino que también reduce la posibilidad de interferencias y pérdidas de señal.

Además, hemos mejorado la claridad del diseño mediante la implementación de serigrafía. La serigrafía consiste en agregar marcadores visuales en la PCB que indican la ubicación y función de los componentes, facilitando su identificación y comprensión para los usuarios.

Otra mejora significativa es el aumento del grosor de las pistas en la PCB. Este ajuste garantiza que las pistas puedan soportar adecuadamente la corriente que fluye a través de ellas, lo que mejora la confiabilidad y la seguridad del circuito.

Además, hemos incorporado la inclusión de orificios para facilitar el enrutamiento de cables, lo que simplifica la instalación y el mantenimiento del sistema.

Por último, hemos añadido soporte para la Raspberry Pi y la batería, lo que amplía las posibilidades de integración y uso del sistema en diferentes aplicaciones. Estas mejoras no solo optimizan el rendimiento y la fiabilidad del diseño, sino que también aumentan su versatilidad y funcionalidad.