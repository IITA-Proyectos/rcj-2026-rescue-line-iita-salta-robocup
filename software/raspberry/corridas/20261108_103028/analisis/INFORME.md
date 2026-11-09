# Corrida del 8-nov-2026, 10:30

11.492 cuadros, 37 verdes ejecutados. Copia verificada por sha contra la Pi. Las horas de video son a 20 fps.

## El verde que había que ignorar

Giró mal 5 veces, siempre el mismo cuadrado a la izquierda con el travesaño abajo: **1:51, 2:02, 4:09, 4:13 y 4:17** (`los_5_giros_falsos.jpg`). Con el arreglo de `cambios/verde_ya_cruzado_20261108` el simulador ignora esos 5 y no cambia ningún otro verde.

## Cuando se quedó quieto

### 1. Se frena a propósito porque perdió la cinta (3 veces)

| Video | Cuadros | Quieto | Después |
|---|---|---|---|
| 2:17 | 2739–2763 | 0,8 s | lo levantaron |
| 7:10 | 8609–8690 | 2,7 s | lo levantaron |
| 7:34 | 9088–9159 | 2,6 s | lo levantaron |

**Cambiado el 8-nov:** ahora en estos casos sigue derecho como un GAP (`cambios/gap_tras_stop_20261108`).

La secuencia era: pierde la cinta, recuperación (GS 4), decide CURVA, no reengancha, `recup-guard-stop` y parada GS 19. Las de 7:10 y 7:34 son la misma esquina: decide CURVA a la derecha (−60 y −57), queda con la cinta sobre el borde izquierdo de la imagen y el reenganche busca a la derecha durante 1 s (`paradas.jpg`).

### 2. Cuelgue al apagar el switch frente a la zona verde (al final)

Es un error del programa, y deja al robot quieto hasta cortar con Ctrl+C.

1. Se apaga el switch durante el rescate: el hilo serie pone `estado = 'esperando'`.
2. En esa misma vuelta, el lazo de rescate ve la zona verde cerca y **pisa** `estado = "depositar verde"` (`main.py`, `modo_rescate`).
3. El lazo principal no tiene manejador para ese estado: gira sin leer el serie y nunca ve el aviso de "listo" de la Teensy.

En el log se ve en este orden: `serial monitor: switch apagado`, `[STOP] width_ratio=0.634`, `main_loop: stop_rescate activo`. Después siguen 435.744 repeticiones de los mensajes de inicio. **No está arreglado.**

### 3. Trabas cortas de la Pi (2 veces)

En 4:01 (4,3 s) y 6:15 (1,1 s) la Pi dejó de procesar cuadros sin que nadie tocara nada, y el robot no se movió. No es nuevo: aparece en todas las corridas revisadas (`trabas.py`), casi siempre por debajo de 2 s, y el 7-nov llegó a 4,9 s. **Causa sin determinar.**

### Lo que no es

- **Switch a mano:** los otros 22 cortes de la grabación tienen la imagen totalmente distinta antes y después: a mano movieron el robot (`huecos_antes_y_despues.jpg`). Corresponden a apagar el switch.
- **Reinicio de la Teensy:** el log no muestra ninguno.
- **Cámara:** ningún aviso de cuadro vacío.
- **Alimentación:** `vcgencmd get_throttled` da `0x0`.
- **Sistema:** ningún mensaje del kernel desde las 10:25.
