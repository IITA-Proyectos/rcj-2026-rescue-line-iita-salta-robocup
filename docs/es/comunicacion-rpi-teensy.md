# Comunicacion entre la Raspberry Pi y la Teensy

Esta documentacion esta basada en el codigo real:
- Raspberry: `rpi/final_rpi/Main.py`
- Teensy: `src/main.cpp`

## Resumen rapido

- **Medio**: serial por UART.
- **Baudios**: 115200.
- **Raspberry**: `/dev/serial0`.
- **Teensy**: `Serial5`.
- **Formato**: protocolo simple de bytes con marcadores (255, 254, 253, 252).

## Protocolo de Raspberry -> Teensy

La Raspberry envia una trama de 8 bytes, siempre en el mismo orden:

```text
[255, speed, 254, angle, 253, green_state, 252, silver_line]
```

Significado:
- `speed`: 0 a 100. En Teensy se interpreta como porcentaje (ver `serialEvent5`).
- `angle`: 0 a 180. Teensy lo convierte a `steer` en rango [-1, 1] con `(angle - 90) / 90`.
- `green_state`: comando de alto nivel (ver tabla).
- `silver_line`: 0 o 1, indica si se detecto linea plateada en modo linea.

## Comandos `green_state`

Estos valores salen de `Main.py` y se usan en `main.cpp`:

| Valor | Detecta Raspberry | Que provoca en Teensy |
|---|---|---|
| 0 | Nada especial | Sigue linea normal (`action = 7`). |
| 1 | Verde a la izquierda | Gira a la izquierda (`action = 6`). |
| 2 | Verde a la derecha | Gira a la derecha (`action = 5`). |
| 3 | Doble verde | Media vuelta (`action = 14`). |
| 6 | Pelota plateada centrada | Ejecuta rutina de recoleccion plateada. |
| 7 | Pelota negra centrada | Ejecuta rutina de recoleccion negra. |
| 8 | Zona roja centrado | Deposita en zona roja. |
| 9 | Zona verde detectada | Deposita en zona verde. |
| 10 | Linea roja (en linea) | En Raspberry se envia 10, pero Teensy no usa 10 directamente; lo detecta como evento visual y sigue su logica de linea. |

Notas:
- En rescate, `green_state` viene de la deteccion YOLO.
- En linea, `green_state` viene de la deteccion de cuadrados verdes o linea roja.

## Mensajes Teensy -> Raspberry

La Teensy tambien envia bytes para cambiar el estado del programa de la Raspberry:

| Byte | Cuando se envia | Efecto en Raspberry |
|---|---|---|
| `0xF9` (249) | Cuando termina el `startUp` | Pasa de `esperando` a `linea`. |
| `0xF8` (248) | Cuando ya recolecto suficientes pelotas | Pasa de `rescate` a `depositar`. |
| `0xFF` (255) | Cuando se apaga el switch o se cancela | Pasa a `esperando`. |

## Estados de la Raspberry

El `Main.py` opera por estados:
- `esperando`: espera `0xF9` para empezar.
- `linea`: seguidor de linea y deteccion de verdes/rojo/plateado.
- `rescate`: deteccion de pelotas y acercamiento.
- `depositar`: busca zonas de deposito.
- `depositar verde`: etapa extra al detectar zona verde.

Transiciones principales:
- `esperando` -> `linea` cuando llega `0xF9`.
- `linea` -> `rescate` cuando detecta linea plateada (`silver_line = 1`).
- `rescate` -> `depositar` cuando llega `0xF8`.
- Cualquier estado -> `esperando` cuando llega `0xFF`.

Si se modifica el protocolo o el orden de los bytes, hay que actualizar tanto `Main.py` como `main.cpp`.
