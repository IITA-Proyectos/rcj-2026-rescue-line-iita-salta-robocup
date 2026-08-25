# Falsador preregistrado — el radio mínimo que el robot puede trazar

**Escrito ANTES de medir.** Regla 1 del equipo. Fecha: 2026-08-26.
Datos: `software/teensy/firmware/corridas/*.csv` del 22-ago (baseline, 6 corridas
de pista + 2 de banco). Cero robot.

---

## 0. Por qué este experimento, y qué corrige del traspaso de la noche

El traspaso de la noche cerró que la curva cerrada no es posible porque
`v = 9,0 cm/s > ω·R = 4,7 cm/s`, y propuso **tres salidas**, entre ellas la
**salida 2: subir el giro** vía `LINE_PIVOT_SPEED`, declarada como *«la única que
no cuesta tiempo de corrida»*.

Leyendo `drivebase.cpp:205-228`, la salida 2 tiene un problema analítico:

```
_rightspeed = _speed                          (rueda externa)
_leftspeed  = _speed * (1 - 2*rotation)       (rueda interna)

  v_centro = vel * (1 - rot)
  Δv       = vel * 2 * rot
  ω        = Δv / b_eff
  R        = v_centro / ω  =  b_eff * (1 - rot) / (2 * rot)
```

**`R` no contiene `vel`.** Subir `LINE_PIVOT_SPEED` sube `ω` y `v` en la misma
proporción: el cociente no se mueve. Y eso es exactamente lo que ya se había
medido sin interpretarlo así — `ANALISIS-2026-08-23.md:50-56`: *«la constante no
se mueve: 1,15 a 1,29 gr/s por rpm en las seis configuraciones»*. Esa constante
**es** `1/R` disfrazada.

Si esto es cierto, **la salida 2 no existe como está planteada** y la variable de
control real es `rot`, no `vel`.

## 1. Hipótesis

> **H-R:** el radio de giro que el robot traza está fijado por `rot` y por un
> ancho de vía efectivo `b_eff` aproximadamente constante, y **no** por la
> velocidad. Por lo tanto `LINE_PIVOT_SPEED` no cambia el radio alcanzable, y la
> curva cerrada (R = 4,9 cm) se alcanza pidiendo `rot` suficientemente alto —
> no yendo más rápido.

## 2. El falsador, en números, ANTES de mirar

H-R queda **REFUTADA** si se cumple **cualquiera** de estas:

| # | condición que la mata | umbral |
|---|---|---|
| **F1** | `b_eff` **no** es constante: depende de la velocidad de avance | si el `b_eff` mediano del tercil de mayor `v` difiere del tercil de menor `v` en **más del 25 %** |
| **F2** | `b_eff` **no** es constante: depende de `rot` | si el `b_eff` mediano varía **más del 25 %** entre los bins de `rot` con n ≥ 200 |
| **F3** | el radio **sí** depende de la velocidad | si al regresar `R_inst` contra `v_centro` (dentro de un bin estrecho de `rot`, ±0,05) la pendiente es significativa: `|Δlog R / Δlog v| > 0,25` |
| **F4** | el modelo no predice: `R` medido contra `b_eff·(1−rot)/(2·rot)` con el `b_eff` global | si el error mediano relativo es **> 30 %** |

Si **ninguna** se cumple, H-R **sobrevive** (no "queda probada").

## 3. Preregistro en BANDA — sólo hay conclusión si hay plateau

No se elige un umbral: se barre y se exige que el veredicto **no cambie** dentro
de la banda. Un resultado que sólo aparece en un punto de la banda no cuenta.

| parámetro | banda barrida |
|---|---|
| umbral de "está girando" (`|gz|` mínimo) | **20, 30, 40, 50 °/s** |
| umbral de "avanza" (`v_centro` mínimo) | **1, 2, 3 cm/s** |
| bin de `rot` para F2/F3 | **ancho 0,10 y 0,15** |
| descarte de transitorio tras un cambio de `rot` | **0, 3, 5 muestras** |

**Conclusión sólo si el veredicto de F1–F4 es el mismo en las 4×3×2×3 = 72
combinaciones.** Si el veredicto se da vuelta dentro de la banda, el resultado es
*«no concluyente»* y se reporta así.

## 4. Controles

| control | qué tiene que dar | por qué |
|---|---|---|
| **C1 — signo** | el signo de `ω` medido coincide con el signo de `rot` comandado en **> 95 %** de las muestras que pasan el filtro | si no, el parseo o el mapeo de ruedas está mal y todo lo demás es basura |
| **C2 — ruedas en el aire** | `2026-08-22_INVALIDA_ruedas_en_el_aire.csv` tiene que dar `b_eff` **absurdo o indefinido** (ω≈0 con Δv grande) | control positivo: el método tiene que *detectar* una corrida inválida, no digerirla |
| **C3 — recta** | con `rot ≈ 0` el `Δv` medido tiene que ser ≈ 0 y `ω` ≈ 0 | verifica que los encoders y el giroscopio hablan del mismo robot |
| **C4 — banco** | `2026-08-22_banco_piso_historico.csv` (24 segmentos, consigna conocida) tiene que dar el **mismo** `b_eff` que las corridas de pista, dentro del 25 % | si el banco y la pista dan `b_eff` distintos, el slip depende de la superficie y eso es un hallazgo aparte |

## 5. Lo que NO puede concluir este experimento

- **No mide el ancho de vía geométrico.** `b_eff` absorbe el ancho real **y** el
  slip del skid steer. Un `b_eff` mayor que el ancho del CAD (≤ 17,7 cm,
  `docs/tdp/TDP-IITA-2026.md:161`) es la firma del slip, pero separar los dos
  factores necesita el número del CAD, que hoy no está confirmado.
- **No dice si el robot puede sostener un `rot` alto.** Dice qué radio traza
  *cuando* lo pide. Que el control lo pida y lo sostenga es otra pregunta.
- **No es una política.** Diagnóstico confirmado ≠ política adoptada (regla 5).
- **`ω` viene del giroscopio del BNO055** (`gz`, entero ×10, `main.cpp:789`), que
  es el sensor bueno. Las rpm del encoder son **magnitud sin signo**: el sentido
  hay que sacarlo de las columnas `*_dir`, y si eso está mal, C1 lo detecta.

## 6. Métrica primaria, decidida ahora

**`R_min_p05`**: el percentil 5 de `R_inst = v_centro / ω` sobre las muestras que
pasan el filtro de "está girando y avanzando". Es *el radio más cerrado que el
robot efectivamente trazó*.

Predicción registrada antes de mirar: **`R_min_p05` estará entre 4 y 12 cm.**
Si da < 2 cm o > 25 cm, sospechar del método antes que del robot (regla 6:
sanidad física antes de publicar un número).
