# Protocolo del diagnóstico de curvas — un solo día

**Lo que se quiere contestar:** por qué el robot no toma las curvas cerradas
desde que se pasó de 2 fijas + 2 omni a 4 fijas de silicona.

**Con un solo día no se persigue la pista.** El orden de abajo está armado para
que a los 15 minutos ya haya un veredicto, y lo demás sea propina.

---

## El cable

**No hace falta uno de 3 m, y además sería contraproducente:** tironea del chasis
justo en las curvas cerradas, que es la mecánica que se está midiendo, y si se
engancha resetea la Teensy a mitad de corrida.

El barrido de banco hace que el robot **pivotee en el lugar**. El radio de giro
es `trocha·(1−r)/(2r)`:

| rotation | radio | diámetro del círculo |
|---|---|---|
| 0,40 | 124 mm | 248 mm |
| 0,60 | 55 mm | 110 mm |
| 1,00 | 0 mm | 0 mm |

**Todo el barrido entra en un círculo de 25 cm.** Con los 30 cm que ya tenés
alcanza si ponés la notebook en el piso al lado. Si querés estar cómodo, **1 m**.

---

## Los primeros 15 minutos — el barrido de banco

Es el paso 1 del traspaso original, automatizado. **No necesita pista, ni visión,
ni la Raspberry.**

```bash
cd software/teensy/firmware && pio run -e banco_barrido --target upload
```

```bash
python tools/registrar_diagnostico.py COM7 banco_piso.csv --nota "piso de la sede"
```

Prendé el switch. Dura ~90 s: barre `rotation` en 0,40 / 0,50 / 0,60 / 0,70 /
0,85 / 1,00 (los dos signos, dos pasadas) y después barre la velocidad a
`rotation = 1`. **El LED queda fijo al terminar.** Se corta apagando el switch.

Después, **lo mismo con las ruedas al aire**:

```bash
python tools/registrar_diagnostico.py COM7 banco_aire.csv --nota "ruedas levantadas"
```

```bash
python tools/analizar_barrido.py banco_piso.csv --aire banco_aire.csv
```

### Qué va a decir

Las dos hipótesis predicen **órdenes opuestos**, por eso esto decide:

| lo que muestra | veredicto |
|---|---|
| el giro **mejora** hacia `rotation = 1` | **PID ciego al signo.** En `rotation=1` la consigna de la rueda interna es la velocidad completa y el lazo no puede colapsar; el colapso vive en la banda intermedia. **Se arregla por firmware** |
| el giro **empeora** hacia `rotation = 1` | **Techo de par.** `rotation=1` es el scrub máximo. **Es mecánico**: ruedas, peso, geometría. Ningún firmware lo arregla |
| **parejo** en todo el rango, columna `colapso` siempre en "no" | la actuación está sana → el problema del seguidor está en la **visión** |
| **en el aire anda y en el piso no** | el problema **depende de la carga**: la prueba directa de toda la hipótesis |

En la fase 2, si los grados por segundo **se aplanan** al subir la velocidad, el
techo es de par.

---

## Los 15 minutos siguientes — confirmar el fix

Solo si el veredicto fue "PID ciego al signo":

```bash
pio run -e banco_barrido --target upload   # con -D FIX_LAZO_MOTOR=1 agregado al env
```

Mismo barrido, mismo análisis. Si la columna `colapso` pasa de **SI** a **no** en
la banda 0,5–0,85 y el giro real sube ahí, **el fix funciona y está medido**.

---

## Si sobra tiempo — la pista

Recién acá tiene sentido gastar pista. Tres corridas de la misma curva:

```bash
pio run -e diagnostico --target upload       # como está hoy
pio run -e diagnostico_lazo --target upload  # + fix del lazo
pio run -e diagnostico_fix --target upload   # + rotation continua
```

**Tres y no dos.** Si se cambian dos cosas a la vez, cualquier diferencia tiene
dos explicaciones. El analizador lo chequea solo:

```bash
python tools/analizar_diagnostico.py c2.csv --comparar c1.csv
```

Una corrida sirve si el registrador dice **CORRIDA VALIDA** al cortar: 5 o más
curvas de visión (`ram >= 2`), `drop` en 0, 150 Hz o más. **No guardes el robot
hasta verlo.**

---

## Chequeos de 5 minutos que vale la pena hacer igual

**Los 540 flancos por vuelta.** Es la escala de `rpm_real`, la única referencia
física del análisis. Con el robot grabando, girá una rueda **10 vueltas a mano** y
mirá el delta de `fl_raw`: tiene que dar **5400 ± 20**, en las cuatro. Si no da,
corregí `TICKS_VUELTA` en `lib/drivebase/drivebase.h` (está en un solo lugar).

**Flancos espurios.** Ruedas al aire, motores **quietos**, grabando 1 minuto.
`*_raw` no se tiene que mover ni un tick. Si se mueve, hay ruido eléctrico y eso
es una causa completa del síntoma: un flanco espurio le mete al PID un error de
−200 rpm y lo tira a coast. Se arregla con un capacitor, no reescribiendo el
lazo. El analizador lo marca como **[R]**.

**La cadena de análisis:**

```bash
python tools/probar_analizador.py
```

Once fallas conocidas, once veredictos esperados. Si alguna falla, no confíes en
el análisis del día.

---

## Los seis binarios

| entorno | qué es |
|---|---|
| `teensy_hid_device` | **competencia**. No tiene nada de esto adentro |
| `banco_barrido` | el barrido automático. **El primero a subir** |
| `diagnostico` | el robot tal cual está hoy + registro CSV a 200 Hz |
| `diagnostico_lazo` | + fix del lazo de motor |
| `diagnostico_fix` | + fix del lazo **y** rotation continua |
| `diagnostico_suelto` | como `diagnostico` pero por Serial8, sin cable USB |

---

## Las causas y dónde se arregla cada una

| | qué significa | dónde |
|---|---|---|
| **[A]** | el PID le corta la corriente a la rueda interna | firmware — `FIX_LAZO_MOTOR` |
| **[B]** | las ruedas obedecen y el robot igual no gira | **mecánica** |
| **[C]** | el pin de dirección oscilando | firmware, tres líneas |
| **[D]** | el control se congela en un movimiento bloqueante | firmware |
| **[E]** | el robot actúa sobre un comando viejo | comms |
| **[F]** | la visión nunca pidió el giro | percepción |
| **[G]** | el estimador de RPM miente | reescribir `getSpeed()` |
| **[P]** | las cuatro ruedas cortas a la vez | alimentación / driver |
| **[R]** | flancos imposibles del encoder | **hardware**: capacitor / apantallado |
| **[!]** | hubo ruido antes del colapso → **[A] no concluyente** | resolver [R] primero |
| **[i]** | [B] descartada, otra causa ya lo explica | — |
| **[-]** | la curva la pidió un `runAngle`, no la visión | no cuenta |

**[B] es residual**: solo sobrevive cuando ni [G], ni [P], ni [D] explican la
falta de giro. El analizador no sentencia "es mecánico" sin descartar el resto.

---

## Lo que esto no puede ver

1. **El sentido real de giro.** Encoder de un solo canal: `raw` dice que la rueda
   se movió, no para dónde. "La están arrastrando" es una inferencia fuerte, no
   una medición. Cerrarla necesita encoder en cuadratura.
2. **Tensión de batería y corriente.** No hay sensor. **[P] discrimina por
   simetría** —el scrub castiga a la interna, una caída de tensión castiga a las
   cuatro— pero es inferencia. Un divisor resistivo a un ADC lo convertiría en
   medición, y serviría también en competencia.
3. **Si una rueda está en el aire.** Se infiere, no se mide. Aunque el barrido con
   ruedas levantadas cubre buena parte de esto.
