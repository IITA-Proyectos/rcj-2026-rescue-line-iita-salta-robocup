---
name: seguimiento-de-trayectoria
description: Diseña y diagnostica el lazo que convierte "dónde está la línea" en "cuánto giro" — pure pursuit y su ganancia 2/ℓd², el lookahead como distancia del SUELO y no de imagen, el límite duro ℓd ≤ 2·R, la búsqueda monótona hacia adelante que evita elegir el tramo ya recorrido, separar error de posición de error de rumbo (Stanley), la factibilidad v_max = ω_max·R, el presupuesto de retardo del lazo y qué puede y qué no puede probar un replay open-loop. Usar cuando el robot oscile o corte las curvas, cuando el target apunte hacia atrás, cuando se quiera tocar LOOKAHEAD o la ley de steer, cuando se discuta si un problema es de percepción o de control, o antes de creerle a un A/B corrido sobre video grabado.
---

# seguimiento-de-trayectoria

Sos experto en **path tracking** para un robot de RoboCupJunior Rescue Line con
tracción skid steer y cámara fija. Tu trabajo es distinguir **problemas de
percepción** de **problemas de control**, que se ven parecidos y se arreglan en
lugares opuestos.

## Por qué existe esta skill

En agosto de 2026 el equipo IITA gastó semanas y refutó siete hipótesis seguidas
—H5, H6, H6b, H8, H9, H9-GATE, H10— todas sobre **qué punto elegir**. Ninguna
preguntó **qué se hace con el punto después**. El robot seguía sin doblar.

Cuando cae un árbol entero de hipótesis, lo que suele estar mal es el marco.

---

## 1. El lookahead es una distancia del SUELO. Siempre.

En pure pursuit la curvatura comandada es

```
κ = 2·sin(α) / ℓd        y en términos de error lateral:   κ = (2/ℓd²)·e
```

Snider (CMU-RI-TR-09-08) lo dice explícito: pure pursuit **es un controlador
proporcional con ganancia 2/ℓd²**.

> **La consecuencia que casi nadie ve: si ℓd no es una distancia física, la
> ganancia del lazo es una variable desconocida que cambia frame a frame.**
> Y como entra al cuadrado, un lookahead que varía 2,3× da una ganancia que
> varía 5,3×. Ningún tuning sobrevive eso.

### El error concreto que cometió este equipo

`LOOKAHEAD = 70` eran **70 píxeles geodésicos sobre el esqueleto**, con la cámara
casi horizontal. Medido sobre 13.036 frames, el **arco de suelo real** hasta el
target varió de **0,230 a 1,370 entre p05 y p95: 5,9×**. Con la ganancia al
cuadrado, **la ganancia del lazo varía 35×**.

> **Ojo con qué se mide.** La primera versión de esta medición dio 2,3× porque
> comparaba la **profundidad** del target (`Z` de su fila). Lo que fija la
> ganancia es el **arco a lo largo del camino**, que hay que integrar con la
> métrica del suelo arista por arista. Medido bien es 2,5 veces peor.

### Cómo se detecta

Buscá cualquier constante de lookahead y preguntá **en qué unidades está**. Si la
respuesta es "píxeles", ya encontraste un defecto. Convertí con el modelo de
suelo (ver `geometria-camara-suelo`) y medí la dispersión de la distancia real.

### Cómo se arregla sin tocar hardware

Proyectá el candidato al suelo **antes** de aplicar el criterio de lookahead, y
elegí el punto cuya distancia en el suelo esté más cerca de ℓd_objetivo. El
grafo, el esqueleto y Dijkstra pueden quedarse: lo que cambia es el criterio de
selección sobre la shell.

---

## 2. El límite duro: ℓd ≤ 2·R

Coulter (CMU-RI-TR-92-01, el paper original de 1992) demuestra que para un
círculo de radio `r`, los lookahead admisibles están **acotados en [0, 2r]**.

> "If the path between the vehicle and the goal point is sufficiently 'curvy'
> then **there is no single arc that joins the two points; any driven arc will
> induce error**."

Por encima de 2·R el controlador está resolviendo un problema **sin solución**.
No es que elija mal: no existe respuesta correcta.

Para RoboCupJunior:

| radio | ℓd máximo admisible |
|---|---|
| 4,9 cm (curva más cerrada, RCJA 2.2.2 fija radio interno ≥ 40 mm) | **~10 cm** |
| 15 cm (cuarto de círculo en tile de 30 cm) | ~30 cm |

**Regla:** `ℓd = k·v`, saturado entre `ℓd_min` y `ℓd_max`, con
`ℓd_max ≤ 2·R_min` y `ℓd_min ≥ v · T_lazo_total` (si el target está más cerca de
lo que el robot recorre en un ciclo de control, el lazo es inestable por retardo
puro).

Coulter buscó una fórmula cerrada para ℓd dado un radio y **demostró que no
existe**. No la busques: se sintoniza, con esas dos cotas.

---

## 3. La búsqueda tiene que ser MONÓTONA HACIA ADELANTE

Este es el bug más caro y tiene solución publicada en 1992. Coulter especifica
el orden de operaciones:

> "The path point closest to the vehicle will first be found, and **the search
> for a point 1 lookahead distance away from the vehicle will start at this
> point and commence up the path**."

Primero el punto más cercano. Después se avanza **monótonamente hacia adelante**
sobre el camino. **Nunca una búsqueda global por distancia.**

### El síntoma

El robot apunta a un pedazo de línea **que ya recorrió**. Con un grafo de
esqueleto y Dijkstra, un nodo a ℓd de distancia geodésica puede estar
perfectamente hacia atrás: la rama de entrada, o el otro brazo de una curva.
Nada en la distancia geodésica distingue adelante de atrás.

Y si además el score tiene un término de continuidad angular con el rumbo
anterior, **el error se auto-sostiene**: volver a la rama correcta cuesta mucho
más que seguir equivocado. El equipo IITA midió un caso donde volver costaba
38,51 puntos contra 2,75 de seguir mal, y el enganche duró 20 frames.

### El arreglo correcto

Mantener un **índice de progreso monótono** sobre el camino: el target del frame
`n+1` no puede estar antes que el del frame `n` en la parametrización del
camino. No es un guard heurístico sobre el punto: es una restricción del
algoritmo de búsqueda.

> **Advertencia sobre arreglos que NO funcionan:** el equipo IITA probó una
> política que elegía la rama de mayor alcance, con exclusión de cruces, y
> corrió el A/B en toda una banda de umbrales preregistrados. Las inversiones
> **subieron en los cinco umbrales**. Reemplazar "elegir mal" por "elegir otra
> cosa" sin la restricción de monotonía no arregla nada.

---

## 4. Posición y rumbo son errores distintos y necesitan ganancias distintas

Un target se corre de la columna central por **dos causas físicamente
diferentes**:

| error | qué significa | cómo se corrige |
|---|---|---|
| `e` — cross-track | el robot está corrido de la línea | ganancia que **depende de la velocidad** |
| `ψ` — heading | la línea dobla adelante | ganancia ~1, sin depender de v |

Stanley los separa explícitamente:

```
δ = ψ + arctan( k·e / v )
```

El término de posición **se divide por la velocidad**. Si no lo hacés, a más
velocidad el lazo oscila; a menos velocidad, no converge.

### Cómo detectar que están mezclados

Regresá el comando contra los dos errores por separado:

```
steer ≈ a·e_lat + b·ψ
```

y mirá el reparto de varianza. En el sistema de IITA dio **47,8 % posición /
52,2 % rumbo, con R² = 0,82** — mitad y mitad, por el mismo número y con **una
sola ganancia**, y la ley de steer nunca veía la velocidad, que se mandaba por
separado a la Teensy.

Diagnóstico rápido: contá los frames con el robot **centrado** (|e_lat| pequeño)
y comando fuerte. Si son muchos, el comando lo está generando la curvatura y no
hay forma de sintonizar las dos cosas por separado.

---

## 5. Factibilidad cinemática: v_max = ω_max · R

Es trivial y es devastador. Antes de tocar una línea de percepción, calculá si
la curva **es físicamente posible a la velocidad a la que vas**.

| ω_max | R = 5 cm | R = 10 cm | R = 15 cm |
|---|---|---|---|
| 39 °/s | 3,3 cm/s | 6,8 cm/s | 10,2 cm/s |
| 58 °/s | 5,1 cm/s | 10,1 cm/s | 15,2 cm/s |

Si el robot va más rápido que eso, **se va de la pista y ningún arreglo de
visión lo cambia**.

### Tres advertencias que cuestan sesiones físicas

1. **Verificá que ω_max sea un techo real y no una configuración.** En IITA los
   "39 °/s" resultaron ser `LINE_PIVOT_SPEED = 20 × ganancia 0,55`, no un límite
   del motor. La ganancia de giro medida era **lineal y sin saturar entre 40 y
   96 rpm de diferencial**. Antes de declarar un techo, barré el parámetro y
   confirmá que la respuesta se aplana.
2. **ω_max depende del piso.** Mandow et al. (IROS 2007) muestran que un skid
   steer se comporta como un diferencial de ancho `α·B`, con **α = 1,5 en vinilo
   y α > 2 en hormigón**. Medilo en la superficie de la sede, no en el taller.
3. **Las salidas son tres y hay que elegir una:** frenar en curva hasta
   `v ≤ ω_max·R`; subir ω_max; o **girar en el lugar** (determinista pero caro:
   ~2,3 s por cada 90° a 39 °/s).

---

## 6. Presupuesto de retardo, y el que se esconde

El retardo total sensor→actuador tiene más términos de los que la gente cuenta:

```
edad del frame  +  procesamiento  +  serie  +  periodo del lazo de control  +  respuesta del motor
```

**El término que siempre falta es el período del lazo del microcontrolador**, y
suele estar clavado a algo que nadie eligió.

En IITA, el `while` de seguimiento de línea llamaba a `leer_tof()` en cada
vuelta, y el VL53L0X en modo continuo hace **espera activa hasta tener muestra
nueva** (~33 ms de presupuesto por defecto). Resultado medido sobre 7.673
períodos: p50 = 30 ms, con un segundo modo en 65 ms (el doble). La Pi mandaba a
66–86 Hz y **el comando cambiaba a 8,6–20,6 Hz: tres de cada cuatro tramas de
visión se descartaban**, y la correlación comando↔giroscopio daba su máximo en
**lag 65–70 ms**, exactamente dos períodos de lazo.

### Cómo se detecta

Histograma del período del lazo. Una distribución **angosta** con un segundo
modo en 2× no es "suma de trabajo variable": es una **espera enganchada a un
reloj de hardware**. Buscá lecturas bloqueantes de sensores dentro del lazo de
control.

### Por qué importa acá

Un retardo puro convierte una ley de signo en un **ciclo límite**. No crea las
inversiones, pero les pone el precio: mientras el comando llega tarde, el robot
sigue girando en el sentido viejo.

---

## 7. Qué puede y qué no puede probar un replay open-loop

Un video grabado contiene **el futuro que generó el controlador que realmente
manejó el robot**.

| El replay SÍ prueba | El replay NO prueba |
|---|---|
| qué ve la percepción en cada frame | qué trayectoria haría otro controlador |
| consistencia entre frames | si el robot completa la curva |
| regresiones contra un baseline | nada causal sobre closed-loop |
| contradicciones internas | que una política sea mejor |

**Cualquier cambio en la ley de control cambia la trayectoria, así que el replay
sólo puede juzgarlo por métricas de percepción y por controles positivos.** Si
un A/B sobre replay dice que una política de control mejora, ese resultado no
significa lo que parece.

Corolario práctico: **priorizá conseguir un runner de lazo cerrado, aunque sea
log-only, sobre seguir refinando el A/B offline.** Un banco de replay perfecto
no reemplaza una corrida.

---

## Checklist de diagnóstico

Ante "el robot no dobla" o "el robot oscila", en este orden:

1. ¿La curva es **físicamente posible** a esa velocidad? `v ≤ ω_max·R`.
2. ¿`ω_max` es un techo real o una constante de configuración?
3. ¿El **lookahead está en unidades del suelo**? ¿Cuánto varía?
4. ¿`ℓd ≤ 2·R_min`?
5. ¿La búsqueda del target es **monótona hacia adelante**?
6. ¿Posición y rumbo tienen **ganancias separadas**? ¿La de posición depende de v?
7. ¿Cuál es el **período real del lazo** del micro? ¿Hay lecturas bloqueantes adentro?
8. ¿A qué frecuencia **cambia el comando**, contra a qué frecuencia se manda?
9. ¿El target final está **sobre el camino planificado**? Si un guard lo mueve
   fuera, el planificador y el controlador no se hablan.

Los puntos 1, 2, 7 y 8 se contestan **sin tocar percepción**, y suelen cerrar el
caso.

---

## Referencias

- Coulter (1992), *Implementation of the Pure Pursuit Path Tracking Algorithm*,
  CMU-RI-TR-92-01 — búsqueda monótona hacia adelante, ℓd ≤ 2r, ℓd como factor de
  amortiguación.
- Snider (2009), *Automatic Steering Methods for Autonomous Automobile Path
  Tracking*, CMU-RI-TR-09-08 — ganancia 2/ℓd², escalado con velocidad, Stanley.
- Mandow et al. (2007), *Experimental kinematics for wheeled skid-steer mobile
  robots*, IROS — el factor α dependiente del terreno.

Ver también: [`geometria-camara-suelo`](../geometria-camara-suelo/SKILL.md) para
convertir píxeles a distancias, y
[`experimento-falsable`](../experimento-falsable/SKILL.md) para no autoengañarse
midiendo.
