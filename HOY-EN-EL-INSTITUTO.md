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

### 1. Medir la curva con una cinta · **5 minutos, sin robot** ⭐

**Es lo que más desbloquea de todo lo que hay pendiente.**

Medir el radio de las curvas más cerradas de la pista. Con una cinta métrica y el
centro de la curva: el radio de la **línea negra**, no del borde.

Anotar: **el más cerrado**, y cuántas curvas de ese tipo hay.

**Por qué vale más que cualquier corrida**: las tres constantes `0,710` del
firmware salen de suponer 4,9 cm. Si la curva real es de 8 cm, **el robot ya la
puede tomar y el problema es otro**. Si es de 4, hay que frenar. **Cambia el
diagnóstico entero y cuesta cinco minutos.**

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
