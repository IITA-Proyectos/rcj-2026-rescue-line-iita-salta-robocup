# La solución de movimiento — 26-ago-2026

**Qué hacer el sábado, en qué orden, y con qué falsador se apaga cada cosa.**

Este documento reemplaza a la sección "las tres salidas" de
`TRASPASO-2026-08-25-NOCHE.md`. La salida 2 de aquel documento —subir
`LINE_PIVOT_SPEED`— **no existe**, y abajo está el porqué.

---

## 0. Lo primero, porque cambia el orden de todo

> **El robot no tiene un problema de "no puede girar". Tiene un problema de
> "gira sin avanzar".**

`drivebase.cpp:212-215` reparte `v_ext = vel` y `v_int = vel·(1−2·rot)`:

```
v_centro = vel · (1 − rot)        ω = 2·vel·rot / b_eff
R        = v_centro / ω = b_eff · (1 − rot) / (2·rot)
```

Tres consecuencias, y **las tres son álgebra, no estadística**:

1. **`R` no contiene `vel`.** Subir `LINE_PIVOT_SPEED` sube `ω` y `v` en la
   misma proporción: el radio no se mueve. **La salida 2 del traspaso de la
   noche no existe como estaba planteada.**
2. **En `rot = 1` el centro del robot no avanza.** No es un efecto secundario:
   es la definición del pivote.
3. Y esto ya estaba medido sin interpretarlo así —`ANALISIS-2026-08-23.md:54`:
   *«la constante no se mueve: 1,15 a 1,29 gr/s por rpm en las seis
   configuraciones»*. **Esa constante es `1/R` disfrazada.**

---

## 1. Lo que está sólido

Todo esto es álgebra o medición directa, y **no depende de ninguna hipótesis
estadística**.

| | qué | de dónde |
|---|---|---|
| **b_eff = 20,9 cm** | ancho de vía efectivo (geometría + slip) | `dv_encoder/gz_giro` sobre los 10 CSV. Pista: 21,35 / 21,38 / 21,28. Banco (otra superficie, otro binario): 22,41 / 22,31. Un agente independiente lo re-midió y dio 20,8–23,6 |
| **el pivote engancha en 0,60** | `LINE_PIVOTE_ENTRA`, no en el 0,92 de `LINE_PIVOT_STEER` | `main.cpp:100,3775` |
| **y es pegajoso hasta 0,15** | `LINE_PIVOTE_SALE`. En el medio, "la memoria" | `main.cpp:104` |
| **57,9 % del tiempo se pide R < 4,9 cm** | más cerrado que la curva más cerrada que existe en el reglamento | 50.962 muestras frescas, 6 corridas |
| **19 % del tiempo con rot = 1 por nivel** | y el total con `rot=1` es 17–61 % según corrida: la diferencia es la memoria | íd. |
| **dentro del `steer=0`: derecho a fondo** | `\|ls − rs\| = 0,0 rpm` en p50 **y** en p90; `rxspeed = 40`; avanza 3,4 cm (p50) | 35 episodios |
| **el pivote picotea** | 24 a 77 episodios de `rot=1` por corrida, de 155–250 ms | íd. |
| **y gira 6°** | ya estaba en el firmware: `main.cpp:3664` | 295 episodios |

---

## 2. Lo que NO está verificado — y no hay que tratarlo como si lo estuviera

Cinco hipótesis de esta sesión **no sobrevivieron su propio falsador
preregistrado**. Se dejan escritas para que nadie las reproponga como si fueran
hallazgos:

| hipótesis | por qué cayó |
|---|---|
| «el pivote enganchado precede a la pérdida de línea» | lift vs placebo **1,29** < 1,5 preregistrado |
| «los ángulos previos al `steer=0` son más grandes» | lift vs tasa base **0,73–1,24** < 1,3. Y el motivo importa: **no hay contraste porque el estado malo es el estado normal** (el `\|steer\|` p90 global ya es 0,822) |
| «el comando oscila de +fondo a −fondo» | **0,4 %** de los cambios (23 de 5660). Un agente lo reportó como firma dominante generalizando desde 13 episodios que él mismo seleccionó |
| «los flips se concentran antes del `steer=0`» | lift 4,65× pero con **n=6** y usando el test de *«al menos uno»*, que es justo el bug que ya mató una hipótesis acá |
| «el modelo ideal de skid steer describe al robot» | F4 refuta al 100 %: `b_eff` no es constante en toda la banda |

**Y lo más importante: los nueve refutadores adversariales NO corrieron.**
Murieron por límite de sesión, no por contenido. Las tres propuestas de diseño
del workflow **no tienen verificación independiente**.

---

## 3. La solución, en orden de prueba

**Regla: un flag por vez.** Los cuatro están en `false`. Cada uno tiene su
falsador escrito en `priority_fix_flags.h`.

### Paso 1 — `kFixPivoteMemoria`, fix (8). **Empezar por acá.**

Es el más quirúrgico de todos. `s_en_pivote` es pegajoso: entra con
`absSteer ≥ 0,60` y no suelta hasta bajar de `0,15`. En el medio, el comando
fresco ya pide poco ángulo pero `rot` sigue clavado en `1,0`. El fix devuelve
la rampa normal **sólo en esa región**, con piso `0,681` (= R 4,9 cm).

```
                     toca              de eso, con la visión pidiendo fondo
  fix (5) techo global   198,8 s                65,5 s     <- le saca el pivote
  fix (8) sólo memoria    44,8 s                 0,0 s     <- por construcción
```

Verificado dos veces de forma independiente. Recupera **217 cm** de avance.
Control positivo: con el piso en `1,000` es la **identidad exacta**.

> **Falsador: si el robot corta una curva que hoy toma, se apaga.**

### Paso 2 — `kFixWatchdogTramaFresca`, fix (6).

Ortogonal al movimiento. Al volver de una maniobra bloqueante, la primera trama
del buffer sella `g_last_rx_ms` con la hora actual y el watchdog ve "fresco"
algo de segundos atrás. Umbral 250 ms, elegido con el período del lazo medido
(p90 = 95 ms, p99 = 445 ms).

> **Falsador: `g_serial_drenados` tiene que ser > 0. Si es 0, el fix no actuó
> y cualquier diferencia es otra cosa.**

### Paso 3 — `kFixMapeoRot`, fix (7). **Sólo si el paso 1 mostró que la
dirección es correcta.**

Rehace la curva entera: `rot = 0,681·√|steer|`. Avance 0,320 → 0,595 (+86 %).
**Riesgo grande: es mucho menos giro que hoy** (decil 50: de pedir 3,58 cm a
pedir 13,49). Si el robot necesitaba ese giro, **corta las curvas**.

### NO usar — `kFixPivoteAvanza`, fix (5).

Superado por el (8). Toca el 69 % del tiempo de pista y le saca el giro en el
lugar durante 65,5 s en los que **la visión lo estaba pidiendo a fondo de
escala**. Queda sólo para poder comparar los dos en banco.

---

## 4. Lo que hay que medir el sábado, y no es un flag

**El `steer = 0` es ambiguo, y ahí se pierde la corrida.**

Dentro de esos episodios el robot va derecho a fondo (`ls == rs`, `rxspeed=40`)
y avanza 3,4 cm de mediana. Pero:

- El protocolo **sí** tiene código de línea perdida: `green_state = 4`
  (`main.cpp:219`), y la Pi tiene su rutina propia —`angle = ±65`,
  `speed = 12` (`Main.py:987`).
- **Esa rutina no corrió el 22-ago.** `rxspeed` vale sólo 0 o 40 en las 61.615
  muestras: **nunca 12**.

O sea que la protección **ya está escrita y no se activó**. Averiguar por qué es
probablemente el fix de mayor impacto de todos, y **no está en ningún flag**.
Es trabajo del lado de la Pi.

---

## 5. Lo que sigue abierto

- **El barrido de `LOOKAHEAD`** (tarea B del traspaso) sigue sin hacerse.
- **Las dos propuestas del workflow que no implementé**: la ley de persecución
  pura con `Ld` en cm, y el radio explícito vía `steerRadius()`. Sus autores
  reportaron honestamente sus propios fallos (el del radio explícito avisó que
  su falsador F3 falló y que la forma final es post-hoc). **Sin refutadores.**
- **Una corrida etiquetada**: marcar el instante en que el robot se sale. Sin
  eso, «qué pasa antes de salirse» no se puede contestar — hoy hay 8 episodios
  candidatos y apuntan al revés.
- **El TDP tiene dos errores**: dice "a 60 mm wheel" (`:196`) y "fixed wheels
  and omniwheels" (`:163`). Hoy son 4 fijas de silicona A10 y el efectivo de
  rodadura es ~68,8 mm.

---

## 6. Una nota de proceso

El fix (7) se escribió **dos veces**: la primera la pisó un agente del workflow
que corría en el mismo árbol y le hizo `checkout` a `main.cpp` para "dejarlo
como lo encontró". Los fixes (5) y (6) sobrevivieron por estar ya commiteados.

**No editar el árbol mientras hay agentes trabajando en él**, o commitear
inmediatamente.
