# Auditoría integral 2026-05-18 — Teensy 04: Zona de Evacuación / Máquina de Estados de Rescate

> **Dominio:** lógica de la zona de rescate del Teensy 4.1 — `actualizarRescate()`, `while (rutina == "rescate")`, `avance_recto()`, `lado_pared()`, secuencias de pinza (`claw`), conteo de pelotas (`ball_counter`), depósito y salida del cuarto.
> **Archivos leídos completos:** `software/teensy/firmware/src/main.cpp` (1279 líneas), `lib/claw/claw.cpp`, `lib/claw/claw.h`, `lib/drivebase/drivebase.cpp`, `lib/drivebase/drivebase.h`, `firmware/variables_doc.md`.
> **Checkout:** rama `feature/initialize-testing-log` (contenido idéntico a `main` post-PR #101). Números de línea referidos a este checkout.
> **Autor:** auditoría Claude Code, 2026-05-18 (corrida 2026-05-31).
> **Regla de framing:** cada hallazgo se presenta como **TEMA A ANALIZAR** con *riesgo de NO tocar*, *riesgo de tocar* y *tiempo estimado*. No son "bugs a fixear a ciegas": el equipo lleva meses tuneando esto y varias rutinas "funcionan como sea". Toda decisión se valida en banco antes de mergear (regla de oro #3).

---

## 0. Resumen ejecutivo

La zona de evacuación es **el subsistema con más deuda estructural de todo el firmware**. No por falta de trabajo —hay muchísimo código— sino porque conviven **dos implementaciones completas y contradictorias** de la recolección de pelotas, una de las cuales (la "linda", no bloqueante) **está 100% muerta** y la otra (la que realmente corre) es la vieja secuencia bloqueante con `delay()` que las auditorías previas de RESILIENCIA marcaron. Encima, la lógica de conteo y de salida del cuarto descansa sobre dos variables (`ball_counter`, `veces_deposit`) cuyos valores iniciales globales (`=2`) contradicen su reseteo de runtime (`=0`), dejando el comportamiento dependiente de *qué camino* tomó el robot para entrar a rescate.

**El riesgo de competencia es máximo**: en el peor caso realista (entrada a rescate sin pasar por el reset de contadores, o una falsa esquina) el robot **sale del cuarto con 0 víctimas depositadas**, perdiendo *todo* el puntaje de evacuación (~la mitad del puntaje útil de una corrida de Rescue Line). En el caso medio, la pinza plateada falla la captura por falta de delay entre dos servos.

Hallazgos nuevos de este dominio (no cubiertos por auditorías previas):

| ID | Tema | Severidad | Estado previo |
| :-- | :-- | :-- | :-- |
| **R-FSM-01** | Doble FSM de pinza: `actualizarRescate()` es código muerto; corre la versión bloqueante | **P0** | NUEVO |
| **R-FSM-02** | `ball_counter` init global = 2 contradice reset = 0 → conteo dependiente del camino | **P0** | NUEVO (complementa #123) |
| **R-FSM-03** | Pinza plateada: `lower()` + `sortLeft()` sin delay entre servos | **P1** | NUEVO |
| **R-FSM-04** | `veces_deposit` doble inicialización (global=2 / reset=0) + salida a `veces_deposit==2` ciega | **P0** | complementa #123 (B6) |
| **R-FSM-05** | Confirmación cita de #57: ambas ramas `-90` en alineación a pared | **P0** | **ya en #57** — se confirma + se amplía |
| **R-FSM-06** | `lado_pared()` definida pero nunca usada; decisión de pared duplicada e incoherente | **P2** | NUEVO |
| **R-FSM-07** | `avance_recto()` definida pero nunca llamada en rescate (navegación a lazo abierto) | **P1** | NUEVO (toca #B4/#120) |
| **R-FSM-08** | Estrategia de salida codificada rígida (`runAngle 180`) — depósito contra pared vacía | **P1 / oportunidad** | amplía doc estratégico 2026-02-23 |
| **R-FSM-09** | Sin barrido sistemático ni memoria de víctimas — cobertura del cuarto = suerte | **Oportunidad** | NUEVO |
| **R-FSM-10** | `pelotita()` vacía + bloque `green_state==10` (salida) comentado → no hay salida final | **P1** | NUEVO |

Las dependencias con bugs ya abiertos (no se re-auditan, se citan): **#57** (ramas -90), **#123/B6** (salida anticipada), **#125/B8** (`runAngle(180)` ignora signo — afecta el giro de depósito), **#120/B4** (`leer_yaw()` no asigna la global — rompe `avance_recto`), **#112/R-T01** (`runAngle` sin timeout — congela en pared), **#60** (`runDistance` sin timeout). Toda secuencia de rescate que llama `runAngle`/`runDistance`/`runTime` hereda esos deadlocks.

---

## 1. Mapa del flujo de rescate (cómo corre HOY)

Para que el coach pueda seguir las críticas, este es el camino real de ejecución, no el que sugiere la estructura del código:

1. **Entrada** (`while (rutina=="linea")`, `case 2`, líneas 975-1045): la RPi manda `silver_line==1` → `action=2`. Se setea `rutina="rescate"`, `ball_counter=0`, `veces_deposit=0`, `alineado=false`, `depositando=false`. Se hace un baile de aproximación con `runTime`/`runAngle(±45)` según `left_distance`/`right_distance`, se fija `pared` y `lado_plateado`, y `angulo_rescate = yaw actual`.
2. **Bucle de rescate** (`while (rutina=="rescate" && digitalRead(32)==0)`, líneas 1129-1276):
   - Cada vuelta: `serialEvent5()` + `robot.steer(speed, FORWARD, steer)` (sigue lo que diga la RPi).
   - `green_state==6` → secuencia **bloqueante** de recolección negra (1137-1162).
   - `green_state==7` → secuencia **bloqueante** de recolección plateada (1163-1186).
   - `ball_counter>=3 && !depositando` → avisa a RPi (`Serial5.write(248)`), `depositando=true` (1188-1195).
   - `green_state==9` (verde/vivo) → giro 180, deposita derecha, `veces_deposit++` (1196-1207).
   - `green_state==8` (rojo/muerto) → giro 180, deposita izquierda, `veces_deposit++` (1208-1220).
   - `veces_deposit==2` → rutina de salida: cierra pinza, gira a `angulo_rescate`, busca pared, alinea (1222-1268).
3. **Lo que NO corre:** `actualizarRescate()` (líneas 126-254) se llama en `loop()` (línea 807) pero su estado nunca sale de `RESCATE_IDLE` porque **nadie llama** `iniciarRecoleccionNegra()` ni `iniciarRecoleccionPlateada()` (ver R-FSM-01). `avance_recto()`, `lado_pared()`, `pelotita()` tampoco se llaman dentro de rescate.

**Conclusión de mapa:** el robot recolecta con la versión vieja bloqueante. La FSM no bloqueante "moderna" es decorado. Esto es el núcleo de R-FSM-01.

---

## 2. Hallazgos detallados

### R-FSM-01 — [P0] Doble máquina de estados de pinza: la "buena" está muerta, corre la bloqueante

**Evidencia (código actual):**
- FSM no bloqueante completa: `enum RescateState` (86-104), `iniciarRecoleccionNegra()` (110-115), `iniciarRecoleccionPlateada()` (118-123), `actualizarRescate()` (126-254). Se invoca `actualizarRescate()` en `loop()` línea 807.
- **`grep` exhaustivo:** `iniciarRecoleccionNegra` / `iniciarRecoleccionPlateada` aparecen **solo en su definición**. No hay ni una sola llamada en todo `main.cpp`. Por lo tanto `rescateState` queda en `RESCATE_IDLE` toda la corrida y los ~130 estados de esa FSM **jamás se ejecutan**.
- La recolección real es la secuencia bloqueante inline en el `while(rutina=="rescate")` (1137-1186), construida con `nonBlockingDelay()` + `runTime`/`runDistance` + algún `delay(100)` para el buzzer.
- Paralelo idéntico en la librería: `Claw::pickupLeft()` / `pickupRight()` y los estados `CL_PICKUP_*` (claw.cpp 122-220) **tampoco se llaman desde main.cpp** — otra FSM muerta, esta vez dentro de la clase `Claw`.

**Por qué importa:** hay tres niveles de implementación de "recolectar pelota" (FSM en main, FSM en Claw, secuencia inline) y solo uno corre. El que corre es justamente el que las auditorías de RESILIENCIA (#63, doc estratégico §4 líneas 66) marcaron por bloquear el UART. Cualquier alumno que lea el código asumirá que la FSM no bloqueante es la activa y tuneará delays/ángulos ahí **sin ningún efecto**, perdiendo horas y metiendo regresiones por confusión. Es una bomba de mantenimiento a tres semanas del mundial.

- **Riesgo de NO tocar:** alto a mediano plazo. El robot *funciona* hoy (corre la inline), pero el equipo está tuneando a ciegas: cualquier ajuste en `actualizarRescate()` o `claw.pickup*()` no hace nada y genera falsa sensación de cambio. Riesgo concreto de que en Incheon alguien "arregle" la pinza editando el código muerto y el robot siga igual de roto.
- **Riesgo de tocar:** bajo-medio. Hay dos caminos: (a) **borrar el código muerto** (FSM de main + `pickup*` de Claw) y dejar solo la inline documentada — riesgo casi nulo, es eliminar lo que no se ejecuta; (b) **migrar a la FSM no bloqueante** y borrar la inline — riesgo medio-alto porque cambia el comportamiento validado y la inline tiene timings ya tuneados en banco. Recomendación: opción (a) ahora (limpieza segura), opción (b) sólo post-mundial.
- **Tiempo estimado:** (a) 30-45 min + 1 corrida de banco de verificación de que la recolección sigue igual. (b) 4-6 h + batería de banco completa — **no hacer antes de Incheon**.
- **Validación:** tras borrar el código muerto, compilar (`pio run`) y correr 3 recolecciones negra + 3 plateada en banco; deben comportarse idénticas a antes. Entrada en `TEST_LOG.md`.

> **Nota de framing para el coach:** esto NO es "la FSM está mal". Es "hay dos FSM y una es fantasma". La decisión es de *higiene de código*, no de cambiar lo que anda. La opción segura es borrar la fantasma.

---

### R-FSM-02 — [P0] `ball_counter` inicializado en 2 globalmente, reset a 0 solo por un camino → conteo dependiente del camino de entrada

**Evidencia:**
- Declaración global: `int ball_counter=2;` (línea 83). También `int veces_deposit=2;` (línea 82).
- Único reset a 0: dentro de `case 2` (entrada normal a rescate), línea 981 `ball_counter=0;` y 982 `veces_deposit = 0;`.
- Incrementos de `ball_counter`: en la inline negra (1161), inline plateada (1185), y **también** en los estados muertos `RESCATE_*_STEP8` (188, 249) — estos últimos nunca corren (ver R-FSM-01).
- Trigger de depósito: `if (ball_counter>= 3 && depositando==false)` (1188).

**El problema:** el valor global `=2` solo se neutraliza si el robot entra a rescate por `case 2` (la transición `silver_line==1`). Pero el firmware tiene **otras formas** de quedar en `rutina=="rescate"` sin pasar por ese reset:
- Tras el `while(true)` de switch-off (líneas 823-847), al volver a encender, las variables globales conservan su último valor en RAM (no hay reinicio de hardware). Si se apaga el switch *durante* rescate y se reenciende, `ball_counter`/`veces_deposit` pueden estar en cualquier valor.
- El reset de switch-off (808-848) **no** resetea `ball_counter` ni `veces_deposit` (sí resetea `esquinas_negro`, `first_rescate`, `final_rescate`, `action`, `startUp`, `taskDone`). Asimetría peligrosa.

**Consecuencia:** con `ball_counter` arrancando en 2, **una sola** recolección exitosa lo lleva a 3 y dispara depósito anticipado. Y como el global es 2, si por cualquier path el reset no corre, el robot cree que ya casi terminó sin haber juntado nada.

- **Riesgo de NO tocar:** alto. Es un *latent bug*: hoy "anda" porque en la corrida típica se entra por `case 2` y el reset corre. Pero en un re-arranque por switch (común en competencia cuando el robot se traba y el operador lo resetea) el conteo queda corrupto y se va a depositar con 1 pelota o con 0. Pérdida total de puntos de evacuación.
- **Riesgo de tocar:** muy bajo. Cambiar `int ball_counter=2;`→`=0` y `int veces_deposit=2;`→`=0` es semánticamente lo correcto (la doc `variables_doc.md` dice "Valores: 0-∞" y "0-2"). El único motivo por el que alguien pondría `=2` es para forzar un atajo de testing; hay que confirmarlo con Laureano. Además, sumar el reset de ambos en el bloque de switch-off para simetría.
- **Tiempo estimado:** 10 min el cambio + confirmación con el equipo de por qué estaba en 2 + 2 corridas de banco (entrada normal y re-arranque por switch).
- **Validación:** banco: entrar a rescate, juntar 3 pelotas, verificar que deposita exactamente al llegar a 3 (no a 1). Re-encender el switch en medio de rescate y verificar que el conteo se reinicia coherente.

> **Importante:** R-FSM-02 y R-FSM-04 son dos caras del mismo problema de inicialización. El issue #123 (B6) ya cubre la *salida anticipada por `veces_deposit`*; lo nuevo acá es que **el valor inicial global `=2` es la causa raíz compartida** y que el reset es asimétrico respecto a switch-off.

---

### R-FSM-03 — [P1] Recolección plateada: dos servos consecutivos sin delay → la pinza no llega a posición

**Evidencia (comparación de las dos secuencias inline):**

Recolección negra (1137-1162), con delays entre servos:
```cpp
claw.lower();
nonBlockingDelay(1000);      // espera a que baje
claw.depositCenter();
nonBlockingDelay(1400);      // espera a que centre
claw.sortRight();
nonBlockingDelay(1000);      // espera a que clasifique
runDistance(30,FORWARD,5);
```

Recolección plateada (1163-1186), **sin delay entre `lower` y `sortLeft`**:
```cpp
claw.lower();
claw.sortLeft();             // ← se manda inmediatamente, sin esperar
nonBlockingDelay(1400);      // el delay viene DESPUÉS de los dos
claw.depositCenter();
nonBlockingDelay(1000);
runDistance(20,FORWARD,5);
```

**Por qué importa:** `claw.lower()` y `claw.sortLeft()` mueven servos distintos (`_liftDFServo` y `_sortDFServo`), así que físicamente *pueden* moverse en paralelo. Pero `DFServo::setAngle()` es un `writeMicroseconds` instantáneo; los dos comandos se emiten en el mismo milisegundo y el servo de lift recién empieza a bajar mientras el de sort ya gira. Si el diseño asume que la garra baja *antes* de clasificar (como en la negra, que sí espera), la plateada arranca la clasificación con la garra a media altura. Sumado a que la versión negra avanza `runDistance(...,5)` y la plateada también 5 pero con velocidad 20 vs 30 — los timings están desbalanceados entre ambas ramas, señal de que se editó una y no la otra.

- **Riesgo de NO tocar:** medio. La recolección plateada (víctima viva, vale más puntos: cada víctima viva = más que muerta en RCJ) puede fallar la captura intermitentemente porque la geometría de la garra no está asentada. Pérdida de la víctima de mayor valor.
- **Riesgo de tocar:** bajo. Agregar un `nonBlockingDelay(1000)` entre `claw.lower()` y `claw.sortLeft()` replica el patrón ya validado de la rama negra. Es aditivo (solo agrega una espera), no cambia ángulos ni distancias.
- **Tiempo estimado:** 5 min + 3 capturas plateadas en banco comparando con/sin el delay.
- **Validación:** banco con pelota plateada real: medir tasa de captura exitosa antes/después. Documentar en `TEST_LOG.md`.

> **Sospecha adicional a confirmar en banco:** el *orden* también difiere — negra hace `lower → depositCenter → sortRight`, plateada hace `lower → sortLeft → depositCenter`. Conviene que el equipo confirme si el orden plateado es intencional o copy-paste a medio editar.

---

### R-FSM-04 — [P0] Salida del cuarto gobernada por `veces_deposit==2` sin verificar víctimas reales (raíz de inicialización compartida con R-FSM-02)

**Evidencia:**
- Declaración global `int veces_deposit=2;` (línea 82) → la doc dice "Valores: 0-2".
- Reset a 0 solo en `case 2` (línea 982).
- Incremento solo en depósito verde (`green_state==9`, línea 1206) y rojo (`green_state==8`, línea 1218).
- Trigger de salida: `if (veces_deposit == 2)` (línea 1222) → ejecuta cierre de pinza, giro a `angulo_rescate` y búsqueda de pared para salir.

**El problema (complementa #123/B6, agrega causa raíz):**
1. Como en R-FSM-02, el global `=2` significa que **si el reset de `case 2` no corre, el robot cree que ya depositó 2 veces y dispara la salida inmediatamente, sin haber rescatado nada.** Esto es exactamente lo que reporta #123 ("salida anticipada... una falsa esquina dispara salida con 0 víctimas") pero la auditoría #123 lo atribuye a "no chequea `ball_counter`"; acá se documenta que **además** el valor inicial global es parte del problema.
2. `veces_deposit==2` asume rígidamente que siempre hay exactamente 2 depósitos (1 vivo + 1 muerto). El reglamento RCJ 2026 permite combinaciones variables de víctimas vivas/muertas; el robot puede tener que depositar 2 vivas (ambas en la zona verde) o ninguna muerta. Con la lógica actual, dos depósitos del *mismo* color igual suman 2 y disparan salida, pero si solo hay víctimas de un tipo el conteo nunca llega a 2 y **el robot nunca sale** (deadlock de evacuación).
3. Usar `==2` exacto (en vez de `>=2`) es frágil: si por un glitch `veces_deposit` saltara de 1 a 3 (no debería, pero), nunca dispararía.

- **Riesgo de NO tocar:** alto. Dos modos de fallo opuestos: salida prematura con 0 víctimas (pérdida total) o nunca salir (pierde los puntos de "salir de la zona"). Ambos cuestan mucho.
- **Riesgo de tocar:** medio. La corrección correcta combina: (a) `veces_deposit=0` global (R-FSM-02); (b) condicionar salida a "ya deposité todas las que junté", p.ej. `if (depositando && veces_deposit >= victimas_a_depositar)` donde `victimas_a_depositar` se deriva de `ball_counter`; (c) usar `>=` no `==`. Esto cambia comportamiento validado → banco obligatorio. **Coordinar con #123 para no duplicar el fix.**
- **Tiempo estimado:** 30-45 min de diseño de la condición correcta + 4-5 corridas de banco con distintas combinaciones de víctimas.
- **Validación:** banco con escenarios: (i) 1 viva + 1 muerta, (ii) 2 vivas, (iii) 1 sola víctima. El robot debe depositar todas y *recién entonces* salir.

---

### R-FSM-05 — [P0] Confirmación + ampliación de #57: ambas ramas de alineación giran -90

**Estado: ya está abierto como #57.** Aquí se **confirma sobre el checkout actual** y se agrega contexto nuevo, no se duplica.

**Confirmación textual (líneas 1254-1264):**
```cpp
if(left_distance < right_distance) {
    runAngle(25,FORWARD,-90);          // 1258
}
else if(right_distance<left_distance) {
    runAngle(25,FORWARD,-90);          // 1263  ← idéntico, ambas -90
}
```
Confirmado: ambas ramas ejecutan `runAngle(25, FORWARD, -90)`. La decisión `left<right` vs `right<left` no tiene efecto.

**Ampliación nueva (no está en #57):**
- Hay un **segundo** bloque de alineación más arriba en el mismo `if(veces_deposit==2)` (1237-1244) que **sí** discrimina correctamente: `pared=="left"`→`runAngle(25,FORWARD,90)`, `pared=="right"`→`runAngle(25,FORWARD,-90)`. O sea, el robot tiene la lógica correcta a 17 líneas de distancia del bug. Esto refuerza la hipótesis de #57 de que fue un copy-paste con signo sin editar: **el patrón correcto ya existe en `pared==` y debería replicarse en el `left_distance<right_distance`.**
- Además, el segundo bloque usa `front_distance<12` como gatillo *dentro* de `if(alineado)` (1251), pero los giros se hacen con `runAngle` que **no tiene timeout** (#112/R-T01). Si el robot ya está pegado a la pared y no puede girar físicamente, se cuelga ahí para siempre. El bug de #57 y el de #112 se componen en este bloque.

- **Riesgo de NO tocar:** alto (ya evaluado en #57): el robot puede chocar la pared al salir. Se mantiene la prioridad P0 de #57.
- **Riesgo de tocar:** medio. #57 ya propone el fix tentativo (`left<right → +90`). Lo nuevo: **usar como referencia el bloque `pared==` de las líneas 1237-1244 que ya está bien**, en vez de inventar el signo. Confirmar contra videos viejos.
- **Tiempo estimado:** incluido en #57 (10-15 min + banco). Esta auditoría solo aporta la referencia interna y el cruce con #112.
- **Validación:** la de #57 (bloquear cada ToF y verificar giros opuestos).

---

### R-FSM-06 — [P2] `lado_pared()` definida pero nunca usada; decisión de pared duplicada e incoherente

**Evidencia:**
- `void lado_pared()` (719-729) calcula `wall = "right"` o `"left"` según `left_distance`/`right_distance`. **`grep` confirma: nunca se llama.** La variable `wall` se setea solo aquí y en el reset de switch-off no se usa para nada en rescate.
- La decisión real de pared en rescate usa **otra** variable, `pared` (String), seteada en `case 2` (1006, 1023) con lógica distinta y luego consultada en 1237/1241.
- O sea: hay dos variables (`wall`, `pared`) y dos lógicas para "de qué lado está la pared", una de ellas muerta.

- **Riesgo de NO tocar:** bajo (P2). No rompe nada hoy porque `lado_pared()`/`wall` están muertas. Pero es deuda: el próximo que toque alineación puede usar `wall` creyendo que está viva y obtener basura (se setea una sola vez, nunca se actualiza en rescate).
- **Riesgo de tocar:** bajo. Borrar `lado_pared()` y la variable `wall` (o unificar todo en `pared`). Limpieza segura.
- **Tiempo estimado:** 20 min + compilación.
- **Validación:** `pio run` compila; comportamiento de rescate idéntico (no se tocó nada vivo).

---

### R-FSM-07 — [P1] `avance_recto()` definida pero nunca llamada en rescate → navegación dentro del cuarto a lazo abierto

**Evidencia:**
- `void avance_recto(String pared)` (672-717) implementa un controlador decente: corrige ángulo con IMU (`leer_yaw`) si el error angular supera el umbral, si no mantiene distancia a pared con ToF. Es **exactamente** lo que querés para barrer el cuarto pegado a una pared.
- **`grep` confirma: `avance_recto` nunca se llama.** El movimiento dentro de rescate es solo `robot.steer(speed, FORWARD, steer)` (1134) con `speed`/`steer` que vienen crudos de la RPi.
- Encima `avance_recto()` depende de `leer_yaw()` que **no asigna la global `yaw`** (#120/B4): la función tiene una variable local `float yaw` que sombrea la global (línea 614), así que aunque se llamara, `avance_recto` leería la `yaw` global que nadie actualiza → navegaría con IMU fantasma. Los dos bugs se componen.

- **Riesgo de NO tocar:** medio-alto. El robot dentro del cuarto depende 100% de que la RPi le mande `steer` correcto. Si la visión pierde la pelota (encandilamiento, pelota fuera de cuadro), el Teensy no tiene navegación propia: se queda con el último `steer` y deambula. No hay barrido sistemático (ver R-FSM-09).
- **Riesgo de tocar:** medio. Integrar `avance_recto()` como modo de búsqueda cuando la RPi no ve pelota cambia el comportamiento del cuarto. Requiere primero arreglar #120/B4 (la global `yaw`) para que el controlador angular sirva. No es un quick-win; es un mini-proyecto.
- **Tiempo estimado:** depende de #120 (B4). Solo integrar `avance_recto` + tunear KP: 2-3 h + banco. **Post quick-wins.**
- **Validación:** banco: poner al robot en el cuarto sin pelota visible y verificar que barre pegado a la pared en vez de quedarse quieto.

---

### R-FSM-08 — [P1 / Oportunidad] Estrategia de salida y depósito codificada rígida (`runAngle 180`)

**Evidencia:**
- Depósito: tanto verde (1199) como rojo (1211) hacen `runAngle(20,FORWARD,180)` asumiendo que la zona de depósito está **siempre exactamente a 180° de donde está el robot**.
- Salida: tras `veces_deposit==2`, gira a `angulo_rescate` (el yaw que tenía al entrar, capturado en 998/1015) y busca pared.
- `runAngle(180)` arrastra el bug #125/B8 (ignora el signo del error → puede tomar el camino largo o terminar mal orientado).

**Crítica (amplía el doc estratégico 2026-02-23 §2.D):** el reglamento RCJ permite zonas de evacuación con la entrada y el triángulo de depósito en lados arbitrarios. Girar 180° fijo deposita contra una pared vacía si la geometría no es simétrica Sur-Norte. La salida por `angulo_rescate` asume que la salida está donde entró — válido (la entrada es la salida en Rescue Line), pero depende de que `angulo_rescate` se haya capturado bien y de que `runAngle` no se cuelgue (#112).

- **Riesgo de NO tocar:** medio-alto. En una zona asimétrica (probable que los jueces la armen así), el robot deposita al aire → pierde puntos de evacuación aunque haya capturado las víctimas. Es el escenario §2.D del doc estratégico, aún sin resolver.
- **Riesgo de tocar:** alto. La solución correcta (RPi busca visualmente el triángulo de depósito y guía dinámicamente) es trabajo de visión + protocolo, no solo Teensy. En el Teensy, mitigación parcial: arreglar #125/B8 para que el 180 sea confiable. Rediseño completo = post-mundial.
- **Tiempo estimado:** mitigación (#125): 15 min. Rediseño dinámico: días, multi-subsistema. **No antes de Incheon.**
- **Validación:** la de #125 para el giro; el rediseño dinámico necesita pista completa.

---

### R-FSM-09 — [Oportunidad] Sin barrido sistemático del cuarto ni memoria de víctimas

**Evidencia:** no existe ninguna estructura que registre qué zonas del cuarto ya se exploraron ni qué víctimas ya se recogieron. `esquinas_negro[3]` (global, línea 67) sugiere que *hubo* una intención de marcar esquinas, pero **`grep` confirma que solo se resetea en switch-off (814-816) y nunca se lee ni escribe en rescate.** Es otra variable muerta.

**Crítica:** la cobertura del cuarto depende enteramente de que la RPi vaya viendo pelotas y el Teensy reaccione. No hay patrón de búsqueda (espiral, perímetro, zig-zag). Si una pelota está en una esquina que la cámara no barre, nunca se recoge. Para el objetivo declarado del equipo (auto-recuperación 8/10, podio), un barrido determinista del perímetro usando `avance_recto()` (R-FSM-07) + conteo de paredes elevaría mucho la tasa de captura.

- **Riesgo de NO tocar:** medio (oportunidad de puntaje, no fallo). Se dejan víctimas sin recoger por cobertura incompleta → menos puntos, pero el robot no se rompe.
- **Riesgo de tocar:** alto (es feature nueva). Diseñar una FSM de barrido (idealmente reusando la FSM no bloqueante hoy muerta de R-FSM-01, dándole por fin un uso) + integrar `avance_recto`. Mini-proyecto.
- **Tiempo estimado:** 1-2 días de diseño + banco. **Post quick-wins, candidato fuerte para subir puntaje en Incheon si hay tiempo.**
- **Validación:** pista de rescate con pelotas en esquinas; medir tasa de recolección con/sin barrido.

> **Sinergia:** R-FSM-01 (FSM muerta) + R-FSM-07 (`avance_recto` muerta) + R-FSM-09 (sin barrido) se resuelven juntos elegantemente: **darle a la FSM no bloqueante existente el trabajo de orquestar un barrido perimetral con `avance_recto`.** El esqueleto ya está escrito; falta cablearlo y darle propósito.

---

### R-FSM-10 — [P1] No hay salida final del cuarto implementada: `green_state==10` comentado y `pelotita()` vacía

**Evidencia:**
- Bloque de salida final comentado (1269-1274):
```cpp
/*if(green_state == 10)
    {
        estado == "salida"   // ← además: '==' en vez de '=', y 'estado' no existe
        runTime(0,BACKWARD,0,3000);
    }*/
```
- `void pelotita()` (730-733) está **completamente vacía**.
- En `case 2` de la línea, hay comentado todo un sub-bloque de manejo de zona con pared lejana (`right_distance && left_distance>=50`, líneas 1026-1042) que incluía la lógica de salida por el medio (`lado_plateado="medio"`).

**Crítica:** tras alinear contra la pared en `veces_deposit==2` (1222-1268), el `while` interno (1230) corre hasta que se apaga el switch — **no hay transición de vuelta a `rutina="linea"` ni una salida limpia del cuarto.** El robot queda alineándose contra paredes indefinidamente. La única forma de "salir" es el switch-off manual. El bloque que haría la salida real (`green_state==10`) está comentado y encima tiene errores que impedirían compilarlo si se descomenta tal cual (`estado == "salida"` usa `==` y una variable `estado` inexistente).

- **Riesgo de NO tocar:** alto. El robot **no completa la evacuación**: aunque deposite bien, no sale del cuarto por sí solo → pierde los puntos de "salir de la zona de evacuación por la baldosa de salida" y queda atascado contra la pared hasta fin de tiempo. Es el cierre faltante de toda la rutina.
- **Riesgo de tocar:** medio-alto. Implementar la salida real (detectar baldosa de salida / línea negra de salida y volver a `rutina="linea"`) es lógica nueva coordinada con la RPi. El bloque comentado da pistas de la intención (`green_state==10` desde RPi → retroceder y salir).
- **Tiempo estimado:** 2-4 h (Teensy) + coordinación con visión para el trigger `green_state==10`. **Prioritario para "completar corrida".**
- **Validación:** banco/pista: tras depositar, el robot debe encontrar la salida y reanudar seguimiento de línea (`rutina="linea"`), no quedarse contra la pared.

---

## 3. Cruces con auditorías previas (no se re-auditan, se citan)

| Issue previo | Cómo impacta este dominio |
| :-- | :-- |
| **#57** (P0) | Confirmado en R-FSM-05 sobre checkout actual; se aporta la referencia interna correcta (líneas 1237-1244) y el cruce con #112. |
| **#123 / B6** (Correctitud) | Núcleo de R-FSM-04. Esta auditoría agrega la **causa raíz de inicialización** (`veces_deposit=2` global) y la asimetría con switch-off, que #123 no menciona. Coordinar el fix. |
| **#125 / B8** (Correctitud) | `runAngle(180)` ignora el signo → afecta directamente el giro de depósito (1199, 1211) y la salida. R-FSM-08 depende de este fix. |
| **#120 / B4** (Correctitud) | `leer_yaw()` no asigna la global `yaw` → rompe `avance_recto()` (R-FSM-07) y la corrección angular dentro del cuarto. Prerrequisito de R-FSM-07. |
| **#112 / R-T01** (Resiliencia) | `runAngle()` sin timeout → todos los `runAngle` de rescate (aproximación, depósito 180, alineación a pared) pueden colgar el robot contra la pared. Se compone con R-FSM-05. |
| **#60** (Resiliencia) | `runDistance` sin timeout → los `runDistance` de recolección (1147, 1171) y de avance post-depósito (1205, 1217) cuelgan si una rueda patina sobre debris (doc estratégico §2.B). |
| **#63** (Resiliencia) | `runTime`/`runDistance` descartan bytes serial → durante toda la secuencia bloqueante de recolección (segundos) se pierden comandos de la RPi. Confirma por qué la versión inline (R-FSM-01) es la peor de las dos FSM. |

---

## 4. Priorización sugerida para el dominio (input para triage #91)

**Quick-wins seguros (una tarde, bajo riesgo, alto impacto) — hacer antes del freeze:**
1. **R-FSM-02 / R-FSM-04** — `ball_counter=0` y `veces_deposit=0` globales + reset en switch-off. *(coordinar con #123)*. ~30 min + banco.
2. **R-FSM-03** — `nonBlockingDelay(1000)` entre `lower()` y `sortLeft()` en plateada. ~5 min + banco.
3. **R-FSM-05 / #57** — corregir el signo de la rama `left<right` usando el patrón de las líneas 1237-1244. ~15 min + banco.
4. **R-FSM-01 (opción a)** — borrar el código muerto (FSM de main + `pickup*` de Claw) para que el equipo deje de tunear fantasmas. ~45 min + 1 banco de no-regresión.

**Prioritario para "completar corrida" (no quick-win, pero alto valor):**
5. **R-FSM-10** — implementar la salida final del cuarto (`green_state==10`). 2-4 h + coordinación RPi.

**Post quick-wins / depende de otros fixes:**
6. **R-FSM-07** — integrar `avance_recto()` (requiere #120/B4 primero).
7. **R-FSM-08** — depósito/salida dinámicos (requiere #125/B8 + visión).

**Oportunidad de puntaje si hay tiempo antes de Incheon:**
8. **R-FSM-09** — barrido sistemático + memoria de víctimas (reusar la FSM hoy muerta).

**Higiene (P2, sin urgencia):**
9. **R-FSM-06** — borrar `lado_pared()`/`wall` muertas.

---

## 5. Nota metodológica

- Todos los hallazgos se confirmaron por **lectura directa** del checkout actual (no se asumió nada de auditorías previas). Los `grep` de "definida pero nunca llamada" se corrieron sobre `main.cpp` completo.
- **No se modificó código** (regla del encargo: solo lectura de `software/**`).
- Cada hallazgo lleva *riesgo de no tocar*, *riesgo de tocar* y *tiempo* (regla de framing de feedback del coach). Ninguno se presenta como "bug a fixear a ciegas".
- Antes de aplicar cualquier cambio: confirmar intención con Laureano (firmware) / Enzo (coach), abrir Issue con plantilla `audit-finding.yml`, y validar en banco con entrada en `testing/TEST_LOG.md` (reglas de oro #2 y #3).

*Fin del informe — Teensy 04: Zona de Evacuación / FSM de Rescate.*
