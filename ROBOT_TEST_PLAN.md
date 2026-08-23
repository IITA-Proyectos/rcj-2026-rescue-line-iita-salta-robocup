# Plan de pruebas con el robot — sábado

_Escrito la noche del 2026-08-23, cuando se agotó todo lo que se podía saber sin mover el
robot. Cada prueba dice qué flashear, dónde poner el robot, qué correr, qué grabar, y el
número que decide. **El objetivo es que mañana no se investigue improvisando.**_

**La ventana es de 3 h 30 y después el robot no se ve por una semana.**

---

## LO QUE HAY QUE ENTENDER ANTES DE EMPEZAR

**La causa medida:** el pivote dura **0,190 s** y entrega **4,9 grados**. Una curva pide
~90. De 369 tramos de pivote con signo constante, **ninguno llegó a 90** y entre el 32 % y
el 87 % de los consecutivos **cambian de signo**. Al mismo tiempo el robot gira **1.184 a
2.174 grados por minuto** en bruto y entrega neto ±20.

**Autoridad sobra. Lo que falta es persistencia de dirección.** Es un ciclo límite.

**El fix:** con el pivote enganchado, el signo no se puede dar vuelta antes de `T_min` ms.
Nada más. `LINE_PIVOTE_DWELL_MS = 0` deja el comportamiento de siempre.

---

## REGLA DE ORO DEL DÍA

**Una variable por corrida, y todas las corridas desde el mismo punto de la misma curva.**

El 22-ago se perdieron dos corridas midiendo dos cambios juntos, y las cinco corridas de
control resultaron incomparables entre sí: `como_esta.avi` comparte entre **0,3 % y 1,4 %**
de sus vistas con las demás, contra 44-66 % entre ellas. **Comparar dos corridas grabadas en
pedazos distintos del salón no es un A/B.**

Y **cada corrida graba video Y CSV con el mismo nombre.** De 60 pares posibles del 22-ago,
enganchó **uno**.

---

## PRUEBA 0 — El ritual (20 min, no se saltea)

| | |
|---|---|
| **Firmware** | `git checkout roboliga` y `pio run -e diagnostico_fix -t upload` |
| **Dónde** | Se marca con cinta **una** curva cerrada y un punto de arranque. Todo el día se corre desde ahí |
| **Qué correr** | `sudo systemctl stop iita-robot`, aplicar el parche, y una corrida cualquiera |
| **Qué grabar** | `LOG=~/Desktop/p0.csv GRABAR=~/Desktop/p0.avi python3 main.py`, y el CSV de la Teensy con el registrador |

> **El entorno se nombra siempre.** Todo el día se usa `diagnostico_fix`, que es el único
> que graba CSV. `pio run -t upload` **pelado** ahora flashea `competencia_fix`, que **no
> emite procedencia ni graba nada** — `diagProcedencia()` vive entera dentro del
> `#if MODO_DIAGNOSTICO`. Y para volver al binario histórico:
> `pio run -e teensy_hid_device -t upload`.

**PASS:** el log de la Pi y el CSV de la Teensy enganchan por número de frame, y el log
reporta el fps real al cerrar. Hoy el enganche funciona en **1 de cada 10 corridas**.

**FAIL:** si no enganchan, se para y se arregla. **Sin esto, todo lo que se mida después se
vuelve a analizar a ciegas, que es lo que costó dos noches enteras.**

**Verificación extra, gratis:** mirar la línea `#` de procedencia del CSV. Ahora dice
`gain=`, `rot_exp=`, `piv_entra=`, `piv_sale=`, `piv_vel=`, `piv_max_ms=`,
`piv_confirma_ms=` y `piv_dwell_ms=`. **Si esos campos no están, el binario que se flasheó
no es el de esta rama.** Y `piv_confirma_ms` tiene que decir **0**: con 300 el pivote gira
en el lugar 2,5 s (medido: las rachas de alineación duran 50-75 ms y sólo el 1,2-7,7 % llega
a 300).

**Dónde se guardan los CSV: FUERA de `software/teensy/firmware/`.** Un archivo nuevo ahí
adentro hace que `git_commit.py` marque todos los binarios posteriores con sufijo `-s`
(árbol sucio), y ahí se pierde la trazabilidad de qué binario grabó qué. Guardarlos en el
Escritorio y moverlos al repo al final del día.

---

## PRUEBA 1 — El barrido de `T_min` (55 min) — **LA PRUEBA DEL DÍA**

| | |
|---|---|
| **Valores** | `X` = **0**, luego **250**, luego **400**, y **de nuevo 0** al final |
| **Dónde** | La curva marcada, desde el punto marcado |
| **Cuántas** | 3 intentos por valor. 12 corridas en total |
| **Qué grabar** | CSV de la Teensy **y** log de la Pi, mismo nombre, uno por corrida |

**Cómo se flashea cada valor.** En **PowerShell**, que es lo que se usa en esta máquina —
la sintaxis de bash `VAR=x pio run` es un error de parseo acá:

```powershell
$env:PLATFORMIO_BUILD_FLAGS = "-D LINE_PIVOTE_DWELL_MS=400UL"
pio run -e diagnostico_fix -t upload
Remove-Item Env:PLATFORMIO_BUILD_FLAGS
```

**La última línea no se olvida.** En PowerShell la variable **queda pegada a esa consola** y
contamina todo build posterior. Lo más seguro es **una consola nueva por cada valor**. Y
después de flashear, **mirar `piv_dwell_ms=` en la línea de procedencia del CSV**: es la
única forma de saber qué se flasheó de verdad, y `pio` ya mintió una vez sobre eso.

### El número que decide, calculable del CSV en 30 segundos

Tramos contiguos de linetrack con `|rot| ≥ 0,95` y **signo constante**.

> **LEER ESTO ANTES DE COMPARAR CONTRA NADA.** Los **0,190 s** que circulan salen de las
> seis corridas del 22-ago, y **ninguna de ellas tenía el latch de pivote encendido**
> (verificado: `s_en_pivote` no existe en los commits que las produjeron). Sin latch, `rot`
> sigue a `absSteer` y el tramo se corta apenas baja el ángulo: **el 79,9 % de los tramos
> termina por salir de la banda y sólo el 20,1 % por cambio de signo.**
>
> **Encender el latch solo, sin ningún dwell, ya lleva el p50 a ~245 ms** (simulado sobre el
> `rxsteer` real). Así que **la línea de base NO es 0,190 s: es el bloque de `T_min = 0` del
> propio sábado.** Por eso el 0 se corre dos veces.

| | base = el bloque `T_min=0` de hoy | qué esperar con `T_min = 400 ms` |
|---|---|---|
| duración p50 | ~245 ms (simulado; **se mide el sábado**) | **~305 ms** |
| tramos ≥ 300 ms | ~39 % | **~51 %** |
| tramos que terminan por cambio de signo | ~38 % | **~31 %** |

**PASS:** el p50 sube y la fracción de tramos ≥ 300 ms sube, **contra el bloque de 0 del
mismo día**, y la diferencia aparece en los DOS bloques de 0 (el del principio y el del
final).

**El efecto esperado es moderado, no espectacular.** Si alguien esperaba pasar de 190 a 300
ms, ese salto ya lo da el latch solo. Lo que el dwell agrega arriba es del orden de
245 → 305 ms.

**FAIL, y es el resultado más informativo del día:** si el `T_min` no mueve **ninguna** de
las tres filas fuera del ruido entre repeticiones, el dwell no es la palanca. Ahí lo que
sigue es mirar por qué el tramo termina por **salir de la banda** —que es la otra mitad del
mecanismo y que el dwell no toca— o directamente la actuación.

**Y el otro FAIL, más grave:** si un tramo sostenido de 0,30 s entrega **menos de 8 grados**,
la hipótesis del transitorio se cae entera y el problema es el tren motriz, no el control.

**ABORTO:** si el robot se sale **más** que con `T_min = 0`, se vuelve a 0 en el acto. Es
una constante, no un `git revert`.

**Por qué el 0 se corre dos veces (al principio y al final):** para saber si la diferencia
es del cambio o de la pista, que se ensucia, se calienta y cambia de luz a lo largo del día.
Si los dos bloques de 0 no se parecen entre sí, **ninguna comparación del día vale**.

---

## PRUEBA 2 — La pérdida de línea, sólo medir (25 min)

| | |
|---|---|
| **Firmware** | el mismo de la prueba 1 con el mejor `T_min` |
| **Qué correr** | `LOG=~/Desktop/p2.csv GRABAR=~/Desktop/p2.avi python3 main.py` |
| **Qué cambia** | **nada del comportamiento.** El detector nuevo se loguea y no actúa |

**Qué se mide:** la columna `perdida_nueva` del log de la Pi contra lo que hacía el robot.

| | medido en video | qué esperamos en pista |
|---|---|---|
| recall del detector viejo | 13,5-40,1 % | — |
| recall del detector nuevo | 98,4-100 % | que se sostenga |
| falsos positivos | 0,9-1,8 % | **si supera 5 %, no se enciende la maniobra** |

**PASS:** los episodios de pérdida se sostienen (no son parpadeos de un frame) y los falsos
positivos quedan bajo 5 %.

**Qué se concluye:** si los episodios se sostienen, la próxima semana se decide **qué
maniobra** hacer. **No se enciende `green_state=4` este sábado**: el `case 4` nunca corrió
—0 muestras en 61.615 con su firma— y encenderlo junto con el dwell sería cambiar dos cosas
a la vez.

**Dato que va en contra de retroceder, y por eso no se hace a ciegas:** durante la pérdida
el robot avanza **0,19 cm netos**. No hay ningún "pasarse de largo" que deshacer. Y el signo
del ángulo durante la pérdida predice de qué lado reaparece la cinta el **66,7 %** de las
veces (azar 51 %). Seguir girando hacia donde estaba puede ser mejor que retroceder derecho.

---

## PRUEBA 3 — La velocidad de pivote (20 min, sólo si sobra tiempo)

| | |
|---|---|
| **Firmware** | `-D LINE_PIVOT_SPEED=35` contra el 50 de hoy, con el mejor `T_min` |

**La razón:** medido sobre tramos **sostenidos**, la tasa de giro **satura**: `ls` 0-22 da
19,6 °/s, `ls` 32-42 da **39,3**, y `ls` 42-60 da **39,2**. De 20 a 35 duplica; de 35 a 50
no compra nada. Si 35 anda igual que 50, el robot avanza menos mientras gira y la curva
sale más apretada.

**PASS:** la tasa de giro en tramos de más de 150 ms se mantiene en ~39 °/s con 35 rpm.

---

## LO QUE **NO** VA ESTE SÁBADO, y por qué

| | el número que lo saca |
|---|---|
| `green_state = 4` / la maniobra de retroceso | el `case 4` nunca corrió: **0 muestras en 61.615**. Y el robot avanza 0,19 cm durante la pérdida: no hay nada que deshacer |
| `LINE_PIVOTE_CONFIRMA_MS = 300` | simulado sobre el `rxsteer` grabado, el **71-100 %** de los episodios terminaría por el tope de 2500 ms |
| el objetivo extensible en grados | **100 %** de los episodios cierra en el tope y **0 %** por tiempo. Degenera |
| el planner | 11 ms/frame y recorre el **borde** de la mancha |
| **una novena ley de control** | ocho probadas, todas en la misma banda. Ninguna cambia la duración del pedido, que es lo que decide |

---

## SEGURIDAD

- **El robot no se deja moviéndose sin alguien al lado.** Ninguna prueba de este plan es
  autónoma ni desatendida.
- El tope `LINE_PIVOTE_MAX_MS = 2500` sigue puesto: el pivote no puede quedarse girando
  para siempre. **Pero ojo**: con 39 °/s medidos en tramos sostenidos, 90° cuestan 2,3 s, así
  que ese tope está **sobre el filo**, no con margen. Si un pivote legítimo llega al tope,
  hay que subirlo, no bajar el dwell.
- El dwell queda **inhibido en rampa** (`pitch > PITCH_RAMPA`), porque ahí las traseras se
  pisan en configuración de marcha recta después del `steer`.

---

## SI EL DÍA SE CORTA A LA MITAD

**Orden de valor: 0 → 1 → 2.**

La prueba 0 no es opcional: sin el enganche video↔CSV, las pruebas 1 y 2 producen datos que
no se pueden analizar. Ya pasó una vez y costó dos noches.

---

## LO QUE SIGUE SIN SABERSE Y ESTE PLAN NO CONTESTA

1. **Si sostener el signo completa la curva.** El banco de replay es de visión y en lazo
   abierto: las imágenes están grabadas con la trayectoria que el robot realmente hizo.
2. **Si el `T_min` correcto son 250 o 400 ms.** Los 369 tramos de hoy no los sostuvo nadie;
   la relación grados↔dwell se extrapola de los 36 que duraron más de 0,4 s.
3. **Si los 39 °/s se sostienen en el piso de la pista de competencia.** El scrub de las
   cuatro fijas de silicona depende de la superficie.
4. **Cuántos grados pide realmente la curva que falla.** No hay mapa de pista; el "~90°"
   viene de un informe, no de una medición.
5. **Si un giro sostenido tapa un verde, un doble verde o un plateado.** Y acá hay un P0
   aparte: **el detector de verde no disparó ni una vez en 417 s de video** — `green_mask`
   nunca pasó de 6 píxeles contra un umbral de 510. **Eso hay que mirarlo, y no es parte de
   este plan.**
