# Sábado 29-ago — quién hace qué

**3 h 30 de robot. Un error cuesta la semana.** Este documento es el reparto.
El razonamiento técnico está en [`SOLUCION-MOVIMIENTO-2026-08-26.md`](SOLUCION-MOVIMIENTO-2026-08-26.md).

> **La regla que manda: UN FLAG POR VEZ.** Si se encienden dos y algo cambia,
> no se sabe cuál fue y se perdió la sesión. Los cinco están en `false`.

---

## Antes de tocar el robot — 10 min, cualquiera

| # | qué | cómo se sabe que salió bien |
|---|---|---|
| 0.1 | Batería **fresca**, anotar voltaje de arranque | ≥ 12,4 V |
| 0.2 | Tirar suave de cada Dupont y del USB de la cámara | ninguno se mueve |
| 0.3 | `git log --oneline -1` y anotarlo en la planilla | coincide con lo que se va a flashear |
| 0.4 | Arrancar el registrador **antes** de prender el robot | el LED de la Teensy parpadea |

> `pio run --target upload` dice **SUCCESS aunque el Teensy no haya entrado en
> modo programación**. Hay que apretar el pulsador de la placa y después
> **verificar contra la línea de procedencia que emite la propia Teensy**, no
> contra el mensaje del cargador.

---

## BLOQUE A — la línea base. **Sin esto, nada de lo demás vale.** ~30 min

**Responsable sugerido: quien maneje el registrador.**

1. Flashear `diagnostico_fix` **con los cinco flags nuevos en `false`**.
2. Correr **3 pasadas** de la curva que hoy falla. Grabar los 3 CSV.
3. Nombrarlos `2026-08-29_base_1.csv`, `_2`, `_3`.

**Por qué 3 y no 1:** todo lo que viene se compara contra esto. Con una sola
pasada no se sabe cuánto varía el robot solo, y cualquier diferencia después
parece un efecto cuando puede ser ruido.

**Además, etiquetar a mano**: anotar en papel el **segundo aproximado en que el
robot se sale**, si se sale. Los CSV del 22-ago no tienen esa marca y por eso
«qué pasa antes de salirse» sigue sin poder contestarse.

---

## BLOQUE B — el barrido de banco. ~20 min, **no necesita pista**

**Responsable sugerido: quien tenga paciencia con las planillas.**

1. Flashear `banco_barrido`.
2. **Las 4 ruedas apoyadas** sobre la pista (no en el aire — hay un CSV del
   22-ago que se perdió justo por eso).
3. Dejar correr el barrido completo. Grabar el CSV.

**Qué contesta:** re-mide el **factor de apertura**, que hoy vale **1,15** y de
él salen las tres constantes `0,710` del firmware.

```bash
python software/raspberry/final_rpi/radio_minimo.py
```

**Falsador:** si el factor cambia de 1,15, **hay que recalcular las tres
constantes** antes de encender ningún flag de movimiento. Se recalculan así:

```
rot = b_eff / (2·(R_objetivo / factor) + b_eff)     con b_eff = 20,9 cm
```

---

## BLOQUE C — los flags, uno por vez. ~25 min cada uno

**Responsable sugerido: Benjamín** (es el que conoce el comportamiento de
movimiento y puede decir "esto empeoró" mirando).

Para **cada** flag: encender **sólo ese**, flashear, 3 pasadas, comparar contra
el bloque A.

### C.1 — `kFixGapSueltaPivote` (fix 9). **Empezar por acá.**

Es el único con fundamento reglamentario. Hoy **19 de 63 gaps (30 %) se cruzan
girando en el lugar** en vez de recto.

- ✅ **mejora si**: cruza más gaps sin perder la línea del otro lado
- ❌ **se apaga si**: baja el conteo de gaps tomados bien, **o** si el pivote se
  suelta por un `steer = 0` espurio en medio de una curva y el robot sale
  derecho donde antes giraba

### C.2 — `kFixPivoteMemoria` (fix 8)

Devuelve avance donde el pivote quedó pegado pero la visión ya pide poco ángulo.

- ✅ **mejora si**: la velocidad mediana mientras gira **sube** de 0,81 cm/s
- ❌ **se apaga si**: el robot **corta** una curva que hoy toma
- ⚠️ **control**: la fracción de muestras con `rot = 1` tiene que **bajar**. Si
  no baja, el flag no está actuando y cualquier diferencia es otra cosa

### C.3 — `kFixWatchdogTramaFresca` (fix 6)

Ortogonal al movimiento: se puede correr aunque C.1 y C.2 hayan salido mal.

- ⚠️ **control primero**: `g_serial_drenados` tiene que ser **> 0**. Si es 0, el
  fix no actuó
- ✅ **prueba fuerte**: desconectar el cable de la Pi **a propósito** durante una
  maniobra. Con el fix el robot **tiene que frenar**; sin el fix sigue con la
  orden vieja
- ❌ **se apaga si**: el robot frena en tramos donde hoy anda bien (el umbral de
  250 ms quedó corto)

### C.4 — `kFixMapeoRot` (fix 7). **Sólo si C.2 salió bien.**

El grande. Rehace la curva `steer → rot` entera.

- ❌ **se apaga si**: corta curvas. **Es el riesgo principal**: pide bastante
  menos giro que hoy

### NO tocar — `kFixPivoteAvanza` (fix 5)

Superado por el (8). Queda sólo para comparar si sobra tiempo.

---

## BLOQUE D — lado Raspberry. **No necesita el robot en pista**

**Responsable sugerido: Benjamín** (es su área) — o se delega.

### D.1 — Por qué nunca corrió la rutina de línea perdida

`Main.py:987` manda `angle = ±65` con `speed = 12` cuando pierde la línea. En
las **61.615 muestras** del 22-ago, `rxspeed` vale sólo **0 o 40: nunca 12**.
La rutina existe y no se activó. **Averiguar por qué.**

### D.2 — El barrido de `LOOKAHEAD`

Sigue sin hacerse (era la tarea B del traspaso anterior). `LOOKAHEAD = 70` px es
un parámetro que nadie barrió. **Ojo: más lookahead es más amortiguación, o sea
menos reacción en curva cerrada** — puede empeorar justo lo que se busca.

### D.3 — Medir el radio real de las curvas de la pista

**El `R = 4,9 cm` no sale del reglamento** — es una cita heredada que no se pudo
verificar, y de ella salen las tres constantes del firmware. Medir con una cinta
el radio de las curvas más cerradas de la pista del equipo y anotarlo.

---

## Qué se anota, sí o sí

Una fila por pasada en [`testing/TEST_LOG.md`](testing/TEST_LOG.md):

```
fecha | commit | flag encendido | pasada | ¿completó la curva? | ¿se salió? ¿en qué segundo? | archivo CSV
```

**Sin la columna del commit y sin el CSV, la pasada no sirve para comparar.**

---

## Lo que NO hay que hacer

- **No encender dos flags juntos.** Ni "para ahorrar tiempo".
- **No tunear constantes en la arena.** Si algo no da, se apaga y se anota.
- **No confiar en el SUCCESS del cargador** — verificar la línea de procedencia.
- **No usar `git add -A`** — ya arrastró 60 MB de `.avi` una vez.
- **No cambiar código el sábado si no está en este plan.** Lo que aparezca se
  anota y se decide con la cabeza fría, no con la laptop abierta.
