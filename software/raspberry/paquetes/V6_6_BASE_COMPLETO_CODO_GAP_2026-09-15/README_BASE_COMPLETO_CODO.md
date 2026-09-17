# BASE COMPLETO + CODO + GAP CRUZADO — 2026-09-15

> Copia de `V6_6_BASE_COMPLETO_CODO_2026-09-13` con UN agregado: **TERM_PISO** (abajo, primera sección).
> Cambian solo `RASPBERRY_V6_6_FIELD_REV/terminal_local_guard.py` y dos `print` de `main.py`.
> La Teensy es la misma. Sin `TERM_PISO=1` decide exactamente igual que el paquete del 13-sep.

## GAP con el robot cruzado (TERM_PISO) — 15-sep

**Problema.** TERM_HARD reconoce el gap solo si el robot llega derecho. Pide 7 cuadros seguidos sin tocar
el margen lateral y ancho abajo < 100 px. Después de una curva, o subiendo una loma, la cinta llega en
diagonal: roza el margen o mide más de 100 px abajo, el veto no actúa y queda la CURVA por memoria.

**Regla nueva.** GAP si la punta de la cinta **se despegó del borde de arriba** y desde ahí hasta perder
la línea (≥ 4 cuadros) **nunca hubo una rama**:
- la punta no toca el margen lateral de 8 px;
- ningún tramo pegado al borde lateral empieza arriba de la fila 105 sin llegar a la esquina de abajo
  (si llega a la esquina es la cinta entrando cruzada, no una rama);
- ninguna fila de abajo (105-119) mide más de 2,6 cm en el piso (modelo de cámara del 15-sep).

Además, igual que hoy: última punta en fila ≥ 100 y bb ≤ 0,10.

**Por qué separa.** En los 44 codos y curvas grabados, entre que la punta deja el borde de arriba y la
pérdida siempre aparece una rama por el costado o una fila de abajo de 3,4-4,5 cm (en 5 a 14 cuadros).
En los gaps la cinta mide 1,5-2,0 cm todo el tiempo.

**Replay** con las mismas máscaras que `main.py`. La clase del paquete da lo mismo que el análisis en los
178 casos:

| casos | TERM_HARD de hoy | con TERM_PISO |
|---|---|---|
| codos y curvas reales (4 videos) | 0 / 44 como gap | **0 / 44** |
| gaps reales (gap A x2, gap B, fin de negro del plateado) | 3 / 4 | **4 / 4** |
| loma blanca artificial (completo 1:21) | 0 / 1 | **1 / 1** |
| gap artificial, robot cruzado 15-25° | 32 / 44 | **37 / 44** |
| gap artificial, robot cruzado 25-40° | 37 / 85 | **51 / 85** |

**Qué hace con `TERM_PISO=1`:** el veto de `TERM_HARD_AUTH` usa (TERM_HARD **o** PISO). Sigue vetando
**solo** las CURVA decididas por memoria lateral (V6.4 y regla 4). Una CURVA con evidencia post-retroceso
no se toca. Sin la variable, solo se agrega al log `| hoy=... piso=... (motivo)` en cada `[TERM-HARD] snapshot`.

**No cubre:**
- Gap que aparece **ya en el medio** de la imagen justo después de pivotar (la punta nunca bajó desde
  arriba). La cámara ve de 1,7 a 5,4 cm adelante y no lo distingue de un codo con la otra rama escondida.
- Robot cruzado > 25° con la cinta rozando el costado (quedan 34 de 85 sin reconocer).
- **El cruce.** `GAP_ACTION` cruza derecho en la dirección que tenga el robot, sin alinearse. Cruzado 25°
  en un gap de 20 cm termina ~8 cm al costado de la línea y la cámara ve ±2 a ±5 cm. Eso es otro arreglo
  (Teensy) y no está en este paquete.

**Sábado:**
1. Banco del codo y pista completa **sin** `TERM_PISO`: en el log `piso=True` no tiene que salir nunca en
   una curva.
2. Gap derecho, y gap justo después de una curva (robot cruzado), **con** `TERM_PISO=1`:
   buscar `piso=True` y `VETO_APLICADO`.

---

# BASE COMPLETO + CODO — 2026-09-13

**Base:** lo que corrió en `completo_auth_1` (la corrida casi completa del 12-sep):
`V6_6_REV3_FREEZE_SILVER_RECOVERY_UNDO_GREEN_2026-09-12`. El log de esa corrida dice
`V6.6-FIELD-TERM-HARD-REV3`, que es la versión de ese paquete.

Regla de este paquete: **todo cambio tiene que dejar igual lo que la completa hizo bien.**

## Qué cambia respecto de la completa

### Raspberry (`RASPBERRY_V6_6_FIELD_REV/`)

1. **SIDE25 + POSTMAG + edad 0,80** (igual que `V6_6_REV3_FREEZE_SIDE25_POSTMAG`).
   Replay sobre `completo_auth_1`: **10 de 11 decisiones idénticas**. Solo cambia 0:36, el
   codo que falló: IZQ → DER con pivote de 47°. El gap de `v66_shadow_curva1` sigue en RECTA.
2. **COMPLETAR_GIRO** (nuevo, `completar_giro.py` + 6 enganches en `main.py`).
   **Apagado si no se pasa `COMPLETAR_GIRO=1`.**
   Después de soltar una CURVA, cuando la Teensy avisa que terminó el pivote (0xED):
   si la cinta está **de frente** (atravesada), manda ±85 hacia el mismo lado del pivote
   hasta que la cinta suba (alineada o diagonal). Topes: tiene 0,8 s para empezar y gira como
   máximo 0,45 s. Si la cinta no está de frente, no hace nada.

### Teensy (`TEENSY/main.cpp` = repo `software/teensy/firmware/src/main.cpp`)

3. **ACK 0xED** al terminar el pivote de recuperación. Una Pi vieja lo ignora.
4. **`RECUP_GIRO_DER_EXTRA_GRADOS = 0` y signo corregido.** El cambio del 12-sep sumaba
   los +10 con `g_recup_signo > 0`, que es el pivote **izquierdo**. Ahora es `< 0`
   (derecha). Con 0 grados el pivote es idéntico al de la completa.
5. **Evacuación:** `accionNegro()` gira 30° al lado contrario de la pared recordada.
   Todavía sin prueba de banco.
6. **Esquina de depósito en evacuación:** `front_distance <= 34` (antes 31). **Cambio intencional del
   equipo** (confirmado el 15-sep): con 31 cm la maniobra no se disparaba a tiempo. Probar en la zona de
   evacuación.

Compila: `pio run -e competencia` → SUCCESS.

## Por qué COMPLETAR_GIRO y no más grados

Forma de la cinta **justo al terminar el pivote**, medida frame por frame en los videos:

| video | recoveries | la cinta queda de frente al terminar el pivote |
|---|---|---|
| completo_auth_1 | 11 | **ninguno** |
| v66r3_auth_1 (banco del codo) | codos que se fueron | 0:15, 0:25, 1:13, 1:27, 1:40 (DER) · 2:28, 2:45 (IZQ) |
| v66r3_auth_1 | los 2 que salieron bien (0:57, 2:38) | ninguno |

Subir los grados fijos cambia también las curvas de 90 que hoy salen bien. Esta regla
solo actúa donde la cinta quedó de frente.

Validación del módulo sobre los videos (`valida_cg.py`), con el aviso 0xED llegando 0, 2 o 4
frames tarde:

- **completo_auth_1:** 0 episodios con giro forzado, en los tres casos.
- **v66r3_auth_1:** 7 / 7 / 5 episodios, siempre hacia el lado del pivote. Nunca en 0:57 ni en 2:38.

**Límite del replay:** el video es lo que pasó sin la regla, así que no muestra cuánto gira
de más. Eso se ve solo en el banco.

**No cubre** los codos de r3 donde, al terminar el pivote, queda una mancha baja o no se ve
línea: 0:02, 0:47, 1:03, 1:52, 2:01, 2:10.

## Comando (desde `RASPBERRY_V6_6_FIELD_REV`)

```
LOSS_ARB_DIAG=1 RECUP=1 RETROCEDER=1 RECUP_CAMINO=1 TERM_HARD_SHADOW=1 TERM_HARD_AUTH=1 \
SIDE_CHECK_SHADOW=1 SIDE_CHECK_AUTH=1 SAFE_NO_LINE_GUARD=1 CURVE_LATCH=1 COMPLETAR_GIRO=1 \
GRABAR=/home/iita/codo_cg_1.avi python3 -u main.py 2>&1 | tee /home/iita/codo_cg_1.log
```

Sin `COMPLETAR_GIRO=1` se comporta igual que POSTMAG. Para volver atrás no hace falta flashear.

## Qué mirar en el log y en el video

- `[CG] COMPLETAR_GIRO=1 ...` al arrancar.
- `[CG] linea: pivote terminado (0xED)` después de cada CURVA.
  **Si no aparece nunca, la Teensy no está flasheada con este firmware.**
- `[CG] cinta de frente tras el pivote -> sigue girando DER/IZQ`: la regla actuó.
  En el overlay del video aparece `recup-completa-giro`.

## Banco del sábado, en este orden

1. Flashear la Teensy. Probar que enciende, que los motores responden y que no hay reset por watchdog.
2. **Recta y curvas de 90** con `COMPLETAR_GIRO=1`. No tiene que aparecer
   `sigue girando`; en la completa la regla no actuó nunca.
3. **Codo de 135 aislado, 10 veces a cada lado, grabando.** Anotar si alinea o se va.
   - Si se pasa de giro: `CG_MAX_S=0.30`.
   - Si sigue quedando corto: `CG_MAX_S=0.60`.
4. Solo si a la derecha sigue corto: `RECUP_GIRO_DER_EXTRA_GRADOS 10.0f` (el signo ya está bien).
5. **Pista completa grabando**, para comparar con `completo_auth_1`.
6. **Plateado después de un lateral**, aislado, a los dos lados. Va después del codo porque la
   corrección del plateado usa los grados del pivote.
7. **Salida de evacuación por el negro**, con la pared a cada lado.
