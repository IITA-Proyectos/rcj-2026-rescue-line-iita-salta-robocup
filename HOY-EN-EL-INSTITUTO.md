# Hoy en el instituto — qué medir, en orden de valor

_26-ago-2026 · sesión no planificada, aprovechar el robot_

**Regla que vale igual que el sábado: la línea base primero, y un cambio por vez.**

---

## Qué va a pasar cuando llegue a la curva

Predicción, del tramo de la corrida `pista_rampa_continua_pivote20` — la que tiene
escrito en su nota **"curva que falla"**. Tramo de 3 s de mayor giro:

```
giro real (BNO)      120°
avance real          15,4 cm
RADIO QUE TRAZÓ      7,3 cm

rot mediano pedido   0,703
RADIO QUE PIDIÓ      4,4 cm       →  se abrió un factor 1,7 en ese tramo
```

**Va a girar, y bastante.** El pivote casi no aparece ahí (4 % del tiempo): no se
queda clavado. Lo que pasa es que **pide 4,4 cm y traza 7,3**.

Entonces, cuando entre a la curva:

1. `steer` sube, `rot` sube a ~0,70
2. el robot **empieza a girar y avanza** — no se planta
3. **traza ~7 cm de radio, no los 4,4 que pidió**
4. **si la curva es más cerrada que ~7 cm, se va por afuera.** Si es más abierta,
   la toma

> **Lo que NO sabemos, y es lo que hay que medir hoy: cuánto mide de verdad la
> curva de nuestra pista.** Todo el análisis se ancló en "4,9 cm, la curva más
> cerrada del reglamento", y ese número **no está en el reglamento**.

---

## Orden de hoy — de mayor a menor valor por minuto

### 1. Medir el CODO · **5 minutos, sin robot** ⭐

**Corrección al plan anterior:** te había dicho "medí el radio de la curva". Con
el dibujo que mandaste queda claro que **no son curvas, son CODOS**, y un codo
vivo **no tiene radio** — son dos rectas que se cruzan. Ver `COMO_MEDIR_CODO.png`.

En un codo se miden **dos cosas**:

| qué | cómo | para qué |
|---|---|---|
| **el ángulo α** | con transportador o foto desde arriba | dice cuánto tiene que girar el robot |
| **el radio de acuerdo r** | el redondeo de la esquina, si lo tiene | **es el radio más chico que el robot tiene que poder trazar** |

Si la esquina es viva (r ≈ 0), **ningún radio alcanza: hay que frenar y rotar.**
Si tiene acuerdo, **r es el número que reemplaza a la cita de 4,9 cm.**

**Anotá los 3 o 4 codos donde más se sale**, con α y r de cada uno.

### 1bis. Y el dato NUEVO que sale de tu observación · **10 min, con robot**

Dijiste: *"no gira en el lugar sino que avanza, y llega un punto donde le queda
casi nada de línea"*. Eso es medible y **puede dar vuelta el diagnóstico**:

> **¿Cuánto AVANZA el robot desde que empieza a girar hasta que completa el codo?**

Con cinta en el piso: marcá dónde está el robot cuando **empieza** a girar y dónde
está cuando **terminó** de girar. La distancia entre las dos marcas es el número.

- si avanza **poco** (≈ el largo del robot): está girando bien, el problema es otro
- si avanza **mucho** (más de 15-20 cm): **se pasa el codo**, y ahí está la falla

**Por qué importa tanto**: si se pasa, el arreglo va en dirección **contraria** a
tres de los cinco fixes. Ver la advertencia abajo.

### 2. Línea base · ~20 min

Flashear `diagnostico_fix` **con todo como está** (los cinco flags en `false`).

```bash
cd software/teensy/firmware
pio run -e diagnostico_fix --target upload
python tools/registrar_diagnostico.py COM7 2026-08-26_base_1.csv --nota "base, curva que falla, pasada 1"
```

**3 pasadas.** Y en papel, por cada una:

```
¿completó la curva?   ¿se salió?   ¿en qué segundo?   ¿de qué lado se fue?
```

> El `--target upload` dice **SUCCESS aunque el Teensy no haya entrado en modo
> programación**. Apretar el pulsador de la placa y verificar contra la línea de
> procedencia que emite la Teensy, no contra el mensaje del cargador.

**Ese "en qué segundo" es el dato que falta hace tres sesiones.** Sin él, "qué
pasa justo antes de salirse" no se puede contestar.

### 3. Barrido de banco extendido · ~15 min, **sin pista**

```bash
pio run -e banco_barrido --target upload
python tools/registrar_diagnostico.py COM7 2026-08-26_banco.csv --nota "barrido hasta 110 rpm"
```

**Las 4 ruedas apoyadas** (hay un CSV del 22-ago que se perdió por correrlo en el
aire). Dejarlo terminar solo.

**Qué contesta**: hasta 70 rpm el giro **no satura** — 1,77 °/s por rpm, plano, con
el PWM en 157 de 255. Hoy el barrido llega a **110** y va a decir si eso sigue o si
ahí aparece el scrub de las 4 fijas.

```bash
python software/raspberry/final_rpi/radio_minimo.py     # re-mide el factor 1,15
```

**Seguridad**: el switch corta en cualquier punto. Si chilla, huele raro o la
batería se hunde, apagar y **anotar hasta dónde llegó — ese es el dato**.

### 4. Si sobra tiempo: el fix (9) · ~20 min

**Sólo si 1, 2 y 3 están hechos.** Es el más chico y el único con fundamento
reglamentario.

En `software/teensy/firmware/src/priority_fix_flags.h`:

```cpp
inline constexpr bool kFixGapSueltaPivote = true;   // estaba en false
```

3 pasadas, mismo registro.

- ✅ **mejora si**: cruza más gaps sin perder la línea del otro lado
- ❌ **se apaga si**: baja el conteo de gaps tomados bien, **o** si el pivote se
  suelta por un `steer = 0` espurio en medio de una curva y sale derecho donde
  antes giraba

**Y volver a `false` antes de guardar el robot.**

---

## Lo que NO conviene hacer hoy

- **No encender dos flags juntos.** Ni para ahorrar tiempo.
- **No tocar `kFixMapeoRot` ni `kFixPivoteAvanza`** — son los más invasivos y no
  están probados.
- **No tunear constantes en el momento.** Si algo no da, se apaga y se anota.
- **No cambiar código que no esté en esta lista.**

---

## Si sólo alcanza para una cosa

**Medir la curva con la cinta.** Cinco minutos, sin robot, y puede dar vuelta el
diagnóstico de dos semanas.

Segundo: **las 3 pasadas de línea base con el segundo de salida anotado.**

Los flags pueden esperar al sábado. Los datos no: **sin línea base y sin el radio
real, el sábado se va en discutir en vez de medir.**


---

## ⚠️ Una tensión que abrió tu observación, y hay que resolverla ANTES de encender fixes

Lo que describiste —*el robot avanza mientras gira y se pasa el codo*— apunta en
**dirección opuesta** a tres de los cinco fixes.

Los fixes **(5)**, **(7)** y **(8)** le dan **MÁS avance** al robot mientras gira
(el (7) lo sube de 0,320 a 0,595). Eso está bien si el problema es que *gira sin
avanzar*. **Pero si el problema en el codo es que avanza DE MÁS, esos tres lo
empeoran justo ahí.**

Los dos diagnósticos pueden convivir —el robot puede pasar 19 % del tiempo sin
avanzar *en otros momentos* y aun así pasarse en el codo— pero **no se puede
decidir sin el número de 1bis**.

**Por eso hoy no conviene encender (7) ni (8).** El (9) sí: en un gap ir recto es
lo correcto, y no toca el codo.

Y si el número de 1bis dice que se pasa, **resucita una salida que había quedado
descartada: frenar antes del codo**. Que es lo contrario de darle más avance.
