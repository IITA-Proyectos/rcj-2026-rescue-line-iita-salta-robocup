# Auditoría Integral 2026-05-18 — Teensy / Navegación de Línea (FSM)

**Dominio:** `software/teensy/firmware/src/main.cpp` — seguimiento de línea, switch-case de acciones por `green_state`, intersecciones, doble-verde, obstáculo (esquiva), rampa, gap, speedbump, recuperación.
**Auditor:** módulo `teensy-03-linea-fsm`
**Fecha:** 2026-05-18 (redactado sobre checkout `feature/initialize-testing-log`, HEAD `5a868ea`; contenido de navegación idéntico a `main` post-PR #101).
**Alcance:** SOLO LECTURA. No se modificó código fuente.

---

## 0. Cómo leer este informe (marco coach IITA)

Cada finding lleva la estructura obligatoria del equipo: **causa → riesgo-si-NO-se-toca → riesgo-si-se-toca → tiempo estimado → validación en banco**. Ningún finding se presenta como "bug a fixear" sin su contracara: tocar firmware a 6 semanas del mundial (Incheon, 2026-06-30) tiene costo. La decisión final de qué entra es de Enzo (coach) + Gustavo (director), no de esta auditoría.

**Convención de prioridad** (igual que `CLAUDE.md`):
- **P0** — riesgo de no completar una corrida (se va de pista, se cuelga, no arranca).
- **P1** — pérdida significativa de puntaje o comportamiento errático intermitente.
- **P2** — robustez / mantenibilidad / deuda técnica.

**Auditorías previas que NO se repiten** (se citan y se amplían): RESILIENCIA (#53, #27, #57, #119) y CORRECTITUD (#120–#128, bugs #B1–#B10). Cuando un hallazgo ya tiene Issue, se referencia el número y se agrega únicamente lo nuevo.

---

## 1. Mapa del subsistema de navegación de línea

El robot Teensy es "tonto/reactivo": la RPi le manda `[255,speed,254,angle,253,green_state,252,silver]` y la Teensy ejecuta. La navegación de línea vive **toda dentro de `loop()`**, en el bloque `while (rutina == "linea" && digitalRead(32) == 0)` (líneas 884–1128).

### 1.1 Flujo real

```
loop()
 ├─ claw.update()                         (no-bloqueante)
 ├─ actualizarRescate()                   (FSM rescate no-bloqueante)
 ├─ if switch OFF  → STOP + reset flags + while(espera switch ON)
 ├─ else if switch ON && !startUp → secuencia de arranque (runTime bloqueante)
 └─ else
      └─ while(rutina=="linea" && switch ON)
           ├─ color_detected = get_color()      ← BLOQUEANTE (while !colorDataReady)
           ├─ leer_tof()                         ← I2C, puede timeout 500ms c/u
           ├─ leer_ultrasonidos()                ← 3× ping_cm() bloqueante (~hasta 8.7ms c/u)
           └─ if (taskDone)
                ├─ DISPATCH: cadena de if's que setean `action` según green_state/front/silver
                └─ switch(action) { case 1,2,5,6,7,12,14 }
```

### 1.2 Tabla de acciones (lo que el código intenta hacer)

| `green_state` (de RPi) | → `action` | Significado | Caso |
|---|---|---|---|
| 0 | 7 | line-track normal | case 7 |
| 1 | 6 | verde izquierda → giro -60° | case 6 |
| 2 | 5 | verde derecha → giro +60° | case 5 |
| 3 | 14 | doble verde → 180° | case 14 |
| `front_distance<12` | 1 | obstáculo → esquiva | case 1 |
| 14 | 12 | (gap/intersección compleja) | case 12 |
| silver_line==1 | 2 | entra a rescate | case 2 |

### 1.3 Contraste con lo que la RPi REALMENTE envía (verificado en `Main.py`)

Esto es **clave** y nadie lo había documentado. En el estado `'linea'`, `Main.py` (líneas 724–814) **sólo** puede emitir:

- `green_state ∈ {0, 1, 2, 3, 10}` (línea 753 lo arranca en 0; 1/2/3 por verde; 10 por línea roja de fin de pista).
- `silver_line ∈ {0,1}`.
- `speed = 40` **fijo y constante** (línea 757).

Valores `6,7,8,9` se emiten **sólo** en `modo_rescate()` (otro estado). Valores `14,15,16,17` **NO los emite NUNCA la RPi** en ninguna parte del código actual.

**Consecuencias inmediatas (ampliación nueva, no estaba en auditorías previas):**

1. **`case 12` (action=12 vía green_state==14) es código MUERTO.** La RPi nunca manda `green_state==14`, ni 15/16/17. Todo el `case 12` (líneas 1079–1113), su `while` interno y la cascada 15/16/17, son inalcanzables en la configuración actual. Esto **no elimina** el bug #58 (fall-through al case 14) como deuda, pero sí baja su probabilidad real a ~0 *mientras* la RPi no cambie. Ver F-07.

2. **`green_state==10` (línea roja = fin de recorrido / "end of course") se IGNORA por completo en línea.** El dispatch (líneas 905–933) no tiene rama para `green_state==10`. La RPi detecta el rojo y lo manda (Main.py:811–812), pero la Teensy no hace nada con él en modo línea — el `case` para 10 está comentado (línea 1269, dentro de rescate). **El robot no frena ni se detiene al final de la pista.** Ver F-03.

3. **`speed=40` de la RPi se descarta en línea.** El case 7 usa velocidades **hardcodeadas** (25 ó 55), ignorando el `speed` recibido. El contrato de protocolo existe pero la Teensy no lo honra en line-track. Ver F-02 y #B5.

---

## 2. FINDINGS

### F-01 — [P0] El guard `taskDone` está roto: nunca vuelve a `false`, y arranca en `false` (la lógica de "tarea en curso" es ficticia)

**Confirma y AMPLÍA** lo que ninguna auditoría previa había aislado.

**Causa.**
- `bool taskDone = false;` (línea 59).
- El **único** lugar donde se escribe `taskDone = true` es la rama de switch-OFF (línea 821).
- **No existe ningún `taskDone = false` en todo el archivo** (verificado con grep: sólo 3 ocurrencias — declaración, set-true, y el `if`).

Esto produce dos efectos graves y contradictorios según el momento:

1. **Antes del primer toggle de switch:** en el arranque normal (`startUp` se setea en la rama `!startUp`, línea 857), `taskDone` sigue en `false`. El bloque `if (taskDone)` (línea 900) que contiene **TODO el dispatch y el switch de acciones nunca se ejecuta**. El `while(rutina=="linea")` queda girando llamando sólo a `get_color()`, `leer_tof()`, `leer_ultrasonidos()` y **sin mover los motores** (no se llama `robot.steer()` con el line-track). El robot quedaría quieto (o repitiendo el último PWM) hasta que alguien apague y prenda el switch una vez.
   - *Matiz:* la secuencia de arranque (líneas 849–864) corre una vez con `runTime(...)`. Si el operador apaga el switch y lo vuelve a prender (gesto habitual en pista para "soltar" el robot), recién ahí `taskDone=true` (vía línea 821 en el ciclo OFF) y el line-track empieza a funcionar. Es decir: **el robot depende de un OFF→ON manual para arrancar a seguir línea.** Frágil y no documentado.

2. **Después del primer toggle:** `taskDone` queda en `true` **para siempre**. El comentario "robot is currently not performing any task" (línea 901) es entonces mentira: el `if(taskDone)` siempre es verdadero, el dispatch corre **cada iteración del while** sin ninguna noción de "estoy ocupado en una maniobra". El nombre y la intención original (una FSM con tareas atómicas) quedaron a medio implementar.

**Riesgo si NO se toca.** El comportamiento de arranque queda atado a un ritual no escrito (apagar/prender). Si un alumno suelta el robot sin el doble toggle, **no sigue la línea** y parece "colgado" — pérdida de corrida completa (P0). Además, como el guard no protege nada, no hay forma limpia de evitar que una maniobra (giro de verde, esquiva) sea re-disparada mientras se está ejecutando (ver F-08).

**Riesgo si se toca.** Medio-alto. Es lógica de control central. Si se "arregla" `taskDone` para que vuelva a `false` al completar cada acción, hay que definir **qué cuenta como completar** cada case, y varios cases (5,6,14) ya son bloqueantes (corren su `runAngle` completo antes de devolver control). Mal hecho, se puede romper el ritmo de giros. Requiere banco con pista de verdes.

**Fix propuesto (mínimo, conservador).** No re-arquitecturar. Dos opciones:
- **(a) Quirúrgico:** inicializar `taskDone = true;` (línea 59) para que el line-track funcione desde el arranque sin depender del toggle. Es 1 carácter y elimina el riesgo de "robot quieto al soltar". NO toca el resto de la lógica (que ya asume `taskDone` siempre true post-toggle).
- **(b) Correcto pero más caro:** convertir el dispatch en una verdadera FSM no-bloqueante con estados explícitos (ver F-09). Post-mundial.

**Validación en banco.** Encender el robot **sin** tocar el switch dos veces y verificar que sigue la línea. Repetir 5 arranques "en frío". Registrar en `testing/TEST_LOG.md` ("5/5 arranca y sigue línea sin doble-toggle").
**Tiempo.** (a) 5 min + banco 20 min. (b) 1–2 días.
**Prioridad: P0** (afecta arranque de corrida).

---

### F-02 — [P1] El `speed` que envía la RPi se ignora en line-track (velocidad hardcodeada) + acoplamiento con #B5

**Causa.** `serialEvent5()` decodifica y guarda `speed` global (líneas 397–398), pero el `case 7` (line-track, líneas 1062–1077) usa `ajustarVelocidadPorPendiente(25)` y un literal `55`, nunca `speed`. La RPi manda `speed=40` constante (Main.py:757) que se descarta.

**Por qué importa.** El contrato `[255,speed,...]` sugiere que la RPi modula velocidad (p.ej. frenar antes de un verde detectado, o en zona de víctimas). Hoy ese canal es decorativo en línea. Cualquier "speed scheduling" desde visión es imposible sin tocar la Teensy.

**Interacción con #B5 (Issue #122, confirmado).** Ver F-05. El `55` hardcodeado en curva es justamente el síntoma más grave de esta velocidad fija mal elegida.

**Riesgo si NO se toca.** No se puede implementar frenado anticipado por visión (oportunidad perdida, no rotura). El robot va siempre a la misma velocidad base salvo la corrección de pendiente.

**Riesgo si se toca.** Bajo-medio. Si se pasa a usar `speed` de la RPi, se introduce dependencia del canal serial para la velocidad: si la RPi manda 0 o un valor raro por un glitch, el robot podría frenar/acelerar inesperadamente. Mitigable con `constrain` + un piso mínimo.

**Fix propuesto.** No urgente. Si se decide habilitar speed scheduling: en case 7 usar `int base = constrain((int)speed, 18, 45);` y derivar de ahí, manteniendo la lógica de pendiente. Coordinar con `rpi-vision` para que la RPi efectivamente module.
**Validación.** Banco: variar speed desde RPi (script `test/prueba_send_serial.py`) y ver que el robot responde. Pista: corrida completa con velocidad fija actual de control = baseline.
**Tiempo.** 30 min código + 1h banco + coordinación RPi.
**Prioridad: P1** (oportunidad de puntaje; hoy bloquea mejoras de visión).

---

### F-03 — [P1] La línea roja de fin de pista (`green_state==10`) se ignora en modo línea: el robot no se detiene al terminar

**Hallazgo NUEVO.** No estaba en auditorías previas.

**Causa.** La RPi detecta la línea roja (banda de fin de baldosa / fin de recorrido) y emite `green_state=10` (Main.py:803–812). En el dispatch de la Teensy (líneas 905–933) **no hay rama para `green_state==10`**. El único manejo de `==10` está **comentado** dentro del bloque de rescate (líneas 1269–1274). Resultado: en line-track, el robot **pasa por encima de la línea roja sin frenar**.

**Riesgo si NO se toca.** En Rescue Line, la línea roja marca fin de recorrido / "stop". No detenerse puede significar perder el punto de fin-de-pista y, peor, que el robot siga andando fuera del circuito (penalización / corrida sucia). P1 (puede escalar a P0 si el reglamento de la sede penaliza fuerte el no-stop).

**Riesgo si se toca.** Bajo. Agregar un `case` que frene es simple. El riesgo real es **falso positivo de rojo** (la RPi confunde una baldosa o un reflejo con rojo y frena de más). Hoy el umbral de rojo es muy chico (`area>25` px en 160×120, Main.py:807) y el rango HSV (líneas 74–75) es estrecho; conviene revisar con `rpi-vision` antes de actuar sobre el rojo.

**Fix propuesto.** Agregar en el dispatch: `if (green_state == 10) { action = <nuevo case stop>; }` con la prioridad adecuada (probablemente igual o mayor que silver). El case debe frenar suave (`runTime(0,...)`) y/o señalizar (buzzer). Confirmar primero que el falso-positivo de rojo está bajo control.
**Validación.** Banco: cinta roja bajo el sensor → robot frena. Pista: 3 corridas, verificar que frena en la roja final y no en baldosas intermedias.
**Tiempo.** 30 min Teensy + dependencia de validar rojo en RPi.
**Prioridad: P1.**

---

### F-04 — [P0] Esquiva de obstáculo (case 1) usa `random()` SIN seed + lógica de re-adquisición de línea frágil

**Confirma y AMPLÍA** el ítem "esquiva random vs sensor" del encargo. Relacionado con la familia de resiliencia (while sin timeout, #57/#119).

**Causa A — random no sembrado (NUEVO).**
```cpp
RanNumber = random(3);      // línea 941 — resultado descartado inmediatamente
RanNumber = random(1, 3);   // línea 942 — 1 ó 2
```
- La primera llamada (línea 941) es inútil: su valor se pisa en la línea 942.
- **`randomSeed()` nunca se llama** en todo el firmware (verificado con grep). En Arduino/Teensy, sin `randomSeed`, `random()` produce **la misma secuencia idéntica en cada power-up**. Es decir, la "decisión aleatoria" de esquivar por izquierda o por derecha **no es aleatoria entre arranques**: el robot elegirá siempre el mismo lado en la primera esquiva de cada encendido, y la misma secuencia en esquivas sucesivas.

**Por qué es malo.** Si el primer obstáculo de la pista exige esquivar por un lado (porque del otro hay pared/abismo), y el `random` determinístico elige el lado equivocado, el robot lo hará **en todas las corridas igual**. Y como decide a ciegas (no mira ToF/ultrasonido lateral para elegir el lado libre), es una ruleta cargada hacia el peor caso reproducible.

**Causa B — esquiva ciega (no usa sensores para elegir lado).**
El `case 1` no consulta `left_distance`/`right_distance` ni los ToF para decidir hacia dónde rodear. Tira la moneda (cargada) y va. El robot **tiene** ToF laterales (`distance_left_tof`, `distance_right_tof`) y ultrasonidos laterales — y `lado_pared()` (líneas 719–729) ya implementa exactamente "¿qué lado está más cerca?", pero **no se usa en la esquiva**.

**Causa C — re-adquisición de línea por color, en `while` sin timeout.**
```cpp
runAngle(25, FORWARD, -95);
runTime(30, FORWARD, -0.35, 1000);
while (digitalRead(32) == 0) {           // ← sin timeout
    robot.steer(30, FORWARD, -0.35);
    if (get_color() == "Negro") { runAngle(30, FORWARD, -90); break; }
}
```
- El `while` sólo sale por (a) encontrar negro o (b) apagar el switch. Si el robot rodeó el obstáculo y **no reencuentra la línea** (se pasó, el arco fue muy abierto, o el sensor de color falla), **gira en círculos indefinidamente** consumiendo la corrida. Esto es la misma clase de bug de la auditoría de RESILIENCIA (timeouts revertidos en `cead75e` — ver §3) y hermano de #57.
- Además `get_color()` es **bloqueante** (`while(!apds.colorDataReady()) delay(5);`, líneas 336–339): dentro de este `while` de esquiva, cada iteración puede frenarse esperando el sensor de color, degradando el control del arco.

**Riesgo si NO se toca.** (1) Esquiva siempre al mismo lado → choca contra pared/cae si el lado fijo es el malo, de forma reproducible. (2) `while` sin timeout → cuelgue permanente si no reencuentra línea. Ambos son **P0** (pérdida de corrida y, con el WDT real ausente, cuelgue duro).

**Riesgo si se toca.** Medio. Cambiar la elección de lado a basada en sensores cambia el comportamiento que los alumnos ya "conocen". Agregar `randomSeed(analogRead(<pin libre>))` es trivial y de bajo riesgo, pero **cambia** qué lado elige (ya no será el mismo de siempre) — podría empeorar si justo el determinismo actual venía funcionando en una pista concreta. Decisión de Enzo.

**Fix propuesto (incremental, elegir según apetito de riesgo).**
1. **Mínimo (5 min):** borrar la línea 941 (random muerto) y agregar `randomSeed(analogRead(A0))` (o pin analógico libre) en `setup()`. Hace la esquiva realmente aleatoria entre arranques. *Pero* aleatorio ciego sigue siendo malo.
2. **Recomendado (1–2 h):** reemplazar el `random` por decisión por sensor: `leer_ultrasonidos(); leer_tof();` y elegir el lado con **más** espacio libre lateral. Reusar el patrón de `lado_pared()`.
3. **Resiliencia (combinar con §3):** poner timeout a los `while` de re-adquisición (p.ej. `while(switch ON && millis()-t0 < 4000)`), y si expira sin negro, ejecutar rutina de búsqueda (barrido) en vez de colgarse.

**Validación en banco.** (a) Obstáculo con pared a un lado: verificar que esquiva hacia el lado libre 5/5. (b) Obstáculo sin reencuentro de línea: verificar que **no** gira indefinidamente (sale por timeout). Registrar.
**Tiempo.** Mínimo 5 min; recomendado 1–2 h + banco 1h.
**Prioridad: P0** (cuelgue + decisión reproduciblemente mala).

---

### F-05 — [P1] #B5 CONFIRMADO: velocidad sube a 55 en curva cerrada (lógica invertida) — causa probable #1 de salidas de pista

**Confirma Issue #122 (#B5).** Reproducido leyendo el código; agrego cuantificación.

**Causa.** Case 7, líneas 1066–1074:
```cpp
int velocidadAjustada = ajustarVelocidadPorPendiente(25);
if (steer < -0.7 || steer > 0.7) {        // |steer| > 0.7  ⇒ CURVA CERRADA
    robot.steer(55, FORWARD, steer);       // ← ACELERA a 55 en la curva
} else {                                   // recta / curva suave
    robot.steer(velocidadAjustada, FORWARD, steer);  // ← 25 en recta
}
```
La condición está **invertida** respecto de lo deseable: a mayor `|steer|` (curva más cerrada) **sube** la velocidad a 55, y en recta usa 25. Debería ser al revés (rápido en recta, lento en curva).

**Cuantificación del efecto en el drivebase.** En `DriveBase::steer` (drivebase.cpp:110–155), con `rotation=0.8` y `speed=55`: la rueda externa va a 55 y la interna a `55 - 2·0.8·55 = 55 - 88 = -33` → se invierte y gira a 33 en sentido contrario (giro pivote agresivo) **a velocidad alta**. A 55 de base, el pivote en curva cerrada es brusco: el robot sobre-gira y/o se va de la línea por inercia. En recta (steer≈0) iría a 25, lento e innecesariamente conservador. Es exactamente el patrón "sale de pista en la curva" reportado.

**Riesgo si NO se toca.** Salidas de pista recurrentes en curvas cerradas = LoP (Lack of Progress) repetidos = pérdida fuerte de puntaje (P1, frecuente). Es, como dice #122, "la causa más probable de salidas".

**Riesgo si se toca.** Bajo-medio. Invertir la lógica es simple, pero los valores 25/55 fueron tuneados por los alumnos: bajar la velocidad de curva sin re-tunear el seguimiento puede hacer el robot "lento" en rectas si no se sube la base. Recomendado: **velocidad continua** en función de `|steer|` en vez de dos escalones, pero eso es más cambio. Para Incheon, el swap simple es lo seguro.

**Fix propuesto (de #122, refinado).**
```cpp
int base = ajustarVelocidadPorPendiente(40);   // base de recta más alta
int v;
if (steer < -0.5 || steer > 0.5)  v = 22;       // curva: LENTO
else if (steer < -0.2 || steer > 0.2) v = 30;   // curva suave
else v = base;                                   // recta: rápido
robot.steer(v, FORWARD, steer);
```
(Valores a re-tunear en banco; lo importante es **invertir la relación**.)

**Validación.** Banco con curva cerrada de prueba: medir salidas en 10 pasadas antes/después. Objetivo: 0 salidas en curva a velocidad de control. Pista completa: cronometrar para que no quede lento.
**Tiempo.** 15 min código + 1–2 h re-tuneo banco.
**Prioridad: P1** (ya trackeado #122; este informe lo confirma y cuantifica).

---

### F-06 — [P1] #B8 CONFIRMADO: `runAngle(..., 180)` ignora el signo del error (doble-verde gira por el camino largo o falla)

**Confirma Issue #125 (#B8).** Reproducido.

**Causa.** En `runAngle` (líneas 434–530), la rama `angle == 180`:
```cpp
if (angle == 180) {
    robot.steer(speed, dir, 1);   // ← SIEMPRE gira a la derecha, sin mirar `error`
}
```
A diferencia de las ramas 90/-90/45/-45 (que eligen sentido según el signo de `error`), la rama 180 **siempre** comanda `rotation=+1` (pivote a la derecha). El bucle sale cuando `fabs(error) <= 1.0`. Como un giro de 180° es simétrico, salir "al alcanzar el target" puede funcionar **o** recorrer el arco largo / oscilar cerca del objetivo según la `initialAngle`. El comportamiento es inconsistente y, en la práctica, el doble-verde (que llama `runAngle(30,FORWARD,180)` en case 14, línea 1119) "falla frecuente" como dice #125.

**Detalle adicional (NUEVO).** El `runAngle` completo es **bloqueante** (`while(true)` hasta alcanzar ángulo o apagar switch, sin timeout). Si el giro nunca converge a `<=1.0°` (ruido del BNO055, robot trabado, rueda patinando), **se cuelga** — mismo patrón de resiliencia que F-04/§3. La tolerancia de `1.0°` es además exigente para un giro pivote con encoders+IMU; puede oscilar sin entrar nunca a la banda. Esto agrava #B8.

**Riesgo si NO se toca.** Doble-verde (giro en U) mal ejecutado = el robot toma dirección equivocada en la bifurcación = se va por el camino incorrecto o se desorienta (P1). Si además no converge, cuelgue (P0 latente).

**Riesgo si se toca.** Bajo para el signo (fix de #125 es 1 línea). Medio para la tolerancia/timeout (cambiar `1.0` o agregar timeout puede hacer que el giro "termine antes" y quede mal alineado). Re-tunear en banco.

**Fix propuesto (de #125 + ampliación).**
```cpp
if (angle == 180) {
    robot.steer(speed, dir, (error > 0) ? 1 : -1);   // elegir sentido por error
}
```
Y, transversal a todo `runAngle`: agregar timeout (ver §3) y considerar tolerancia 2–3° con histéresis para evitar oscilación.

**Validación.** Banco: comandar 180° desde varias orientaciones iniciales (0°, 90°, 180°, 270°) y verificar que siempre gira por el lado corto y termina alineado ±3°. Pista: doble-verde 5/5 toma dirección correcta.
**Tiempo.** 10 min signo + 1h tolerancia/timeout + banco.
**Prioridad: P1** (trackeado #125; confirmado y ampliado con el riesgo de no-convergencia).

---

### F-07 — [P1] #58 CONFIRMADO: `case 12` cae al `case 14` por falta de `break` + `while` interno con `break` incondicional + `case 12` es inalcanzable hoy

**Confirma Issue #58.** Reproducido + contexto nuevo importante.

**Causa A (fall-through).** El `case 12` (líneas 1079–1113) **no termina en `break;`**. Tras su llave de cierre, el control **cae al `case 14`** (línea 1115). Si en ese instante `green_state==3`, el case 14 ejecuta `runAngle(30,FORWARD,180)` — un giro de 180° espurio. Exactamente lo descripto en #58.

**Causa B (while que corre una sola vez).** Dentro del `case 12` hay `while(digitalRead(32)==0){ ... break; }` con un **`break;` incondicional** al final del cuerpo (línea 1112). El `while` que parecía "esperar a que green_state cambie a 15/16/17" en realidad **se ejecuta como máximo una vez** y sale. La espera no existe.

**Contexto NUEVO que cambia la prioridad real.** Como se documentó en §1.3: **la RPi nunca envía `green_state==14`** (ni 15/16/17). Por lo tanto `action` nunca toma el valor 12 en la pista actual, y **el `case 12` es inalcanzable** → el fall-through al case 14 **no se dispara en la práctica** mientras el código de la RPi no cambie. Esto NO cierra #58 (sigue siendo un bug latente y trampa para el futuro), pero su probabilidad operativa hoy es ~0. Sugerencia: o se **elimina** el case 12 (código muerto) o se le agrega el `break` y se documenta que está reservado para una feature futura de la RPi.

**Riesgo si NO se toca.** Hoy: bajo (inalcanzable). Futuro: si alguien en la RPi habilita `green_state=14` para gaps/intersecciones, hereda un 180° espurio y un while roto sin saberlo. Trampa de mantenimiento (P1 latente).

**Riesgo si se toca.** Bajo. Agregar `break` es seguro. Eliminar el case 12 entero es seguro si se confirma con el equipo que no hay plan inmediato de usarlo (git blame / preguntar a Benjamin/Lucio).

**Fix propuesto.** Aplicar el fix de #58 (agregar `break;` al cierre del case 12; quitar el `break;` incondicional del while interno; agregar timeout al while). **O** borrar el case 12 si se confirma que es muerto. Decidir con el equipo.
**Validación.** Banco: forzar `green_state=14` por serial (`prueba_send_serial.py`) y verificar que NO hace 180° al salir y que el while espera. Si se elimina: compilar y correr pista normal sin regresión.
**Tiempo.** 15 min.
**Prioridad: P1** (trackeado #58; este informe agrega que es inalcanzable hoy → reclasificar como "limpieza/trap futura").

---

### F-08 — [P1] Sin anti-rebote de marcadores verdes: el giro puede re-dispararse mientras el verde sigue a la vista (variables de cooldown declaradas pero MUERTAS)

**Hallazgo NUEVO** (toca la raíz del por qué los giros de verde a veces "doblan de más").

**Causa.** El dispatch (líneas 905–933) re-deriva `action` **cada iteración** del `while(rutina=="linea")` a partir del `green_state` global, que la RPi actualiza ~30 veces/s mientras el marcador esté en el cuadro. No hay **edge-detection** ("verde nuevo") ni **cooldown** entre giros:

- Existen `static unsigned long lastTurn = 0;` y `const unsigned long turnCooldown = 600;` (líneas 48–49) con comentario "// persiste entre iteraciones" — pero **`lastTurn` no se lee ni se escribe en ningún lado** (verificado con grep: sólo aparece en su declaración). Son **variables muertas**: alguien empezó a implementar el cooldown y quedó a medias.
- Idéntico para `laststeer`/`counter`/`steertimer`/`contador`/`retroceder`: declaradas (líneas 34–36, 51) y usadas **sólo dentro de bloques comentados** (líneas 872–883). Código zombi.

**Por qué importa.** Los cases 5/6 (verde der/izq) son **bloqueantes** (`runTime(20,FORWARD,0,800)` + `runAngle(...)`). Mientras se ejecuta el giro, `serialEvent5()` se llama dentro del case para refrescar `green_state` — pero al volver al `while`, si el robot todavía ve el verde (o un resto del mismo), `green_state` puede seguir en 1/2 y **re-disparar el giro**. Esto produce "dobla de más" / giros encadenados en una sola intersección. La intención de `turnCooldown=600ms` era exactamente prevenir esto, pero nunca se cableó.

**Riesgo si NO se toca.** Giros de verde inconsistentes (a veces correcto, a veces doble giro) → mala navegación en intersecciones, que son donde se gana/pierde el recorrido (P1, intermitente). Difícil de diagnosticar en pista porque depende del timing cámara↔maniobra.

**Riesgo si se toca.** Medio. Agregar cooldown puede **suprimir** un giro legítimo si dos verdes vienen muy seguidos (intersecciones consecutivas). Hay que elegir bien el `turnCooldown` (600ms es un punto de partida razonable). Re-tunear en banco con pista de verdes encadenados.

**Fix propuesto.** Cablear el cooldown ya declarado:
```cpp
// en el dispatch, antes de setear action por verde:
if ((green_state==1 || green_state==2 || green_state==3)
        && (millis() - lastTurn) > turnCooldown) {
    action = (green_state==1)?6 : (green_state==2)?5 : 14;
    lastTurn = millis();
}
```
y borrar las variables zombi (`laststeer`, `counter`, `steertimer`, `contador`, `retroceder`) y los bloques comentados, para que no confundan.

**Validación.** Banco: pista con un solo verde → un solo giro (no doble). Pista con dos verdes seguidos → dos giros. Ajustar `turnCooldown`. Registrar.
**Tiempo.** 30–45 min + 1h banco.
**Prioridad: P1.**

---

### F-09 — [P2] El "FSM" de línea no es una FSM: es un `while` con cuerpo bloqueante; el PID de motores se detiene durante cada maniobra

**Hallazgo de arquitectura.** Coincide con la oportunidad #3 del `AUDIT-ACTION-PLAN.md` ("FSM No Bloqueante") y con la familia de resiliencia. Se documenta acá su impacto específico en navegación.

**Causa.** Los cases 1,2,5,6,12,14 usan helpers **bloqueantes**: `runTime` (while por tiempo), `runAngle` (while hasta ángulo), `runDistance` (while por encoder), y `get_color()` (while hasta sensor). Durante una maniobra de verde o esquiva, el `loop()` **no vuelve a iterar**: `claw.update()` y `actualizarRescate()` no corren, y sobre todo **la RPi sigue mandando frames que se acumulan en el buffer serial** (sólo se drena con `serialEvent5()` puntual dentro de algunos helpers). El PID de cada motor (`_motoPID.Compute()` en `setSpeed`) sólo recalcula cuando se llama `robot.steer(...)`; en los huecos del while bloqueante el control de velocidad de rueda queda congelado en el último valor.

**Relación con `serialEvent5()`.** En Teensy, `serialEvent5()` **no es un ISR**: se invoca automáticamente sólo entre iteraciones de `loop()` (yield), o manualmente. Como las maniobras bloquean `loop()`, los frames de la RPi durante una maniobra se procesan tarde/mal, salvo las llamadas manuales dispersas. Esto explica parte del "lag de dirección" mencionado en el plan maestro (línea 13).

**Riesgo si NO se toca.** Robustez/latencia, no rotura inmediata. Pero amplifica F-04/F-06/§3: cualquier maniobra que no termina cuelga todo. P2 como deuda; sus síntomas concretos ya están cubiertos como P0/P1 en otros findings.

**Riesgo si se toca.** **Alto.** Reescribir a FSM real es el cambio más invasivo posible a 6 semanas del mundial. La regla de oro #4 ("no tocar lo que funciona porque suena mejor") aplica de lleno. **Recomendación: NO hacerlo antes de Incheon.** Dejar como deuda explícita post-mundial. Los fixes quirúrgicos de timeout (§3) dan el 80% del beneficio de robustez sin la reescritura.

**Fix propuesto.** Post-Incheon: migrar a FSM con `millis()` (oportunidad #3 del plan). Antes de Incheon: **sólo** poner timeouts (§3).
**Tiempo.** Reescritura: semanas. No recomendado pre-mundial.
**Prioridad: P2** (deuda; no bloquea competencia si se aplican los timeouts).

---

### F-10 — [P2] Recuperación de línea perdida: inexistente (no hay rutina de búsqueda cuando se pierde el negro)

**Hallazgo NUEVO** (parte de la oportunidad "recuperación de línea perdida" del encargo).

**Causa.** Cuando se pierde la línea, la RPi pone `angle=0` (Main.py:791–792, `if np.sum(black_mask) < min_line_size: angle = 0`). La Teensy entonces recibe `steer≈0` y en case 7 sigue **derecho a velocidad base**. No hay ninguna rutina de "perdí la línea → barrido/giro de búsqueda". El robot simplemente **avanza recto** esperando reencontrarla; si la línea giraba, se aleja.

**Detalle Teensy.** No existe en la Teensy un contador de "frames sin línea" ni un estado de búsqueda. La decisión de qué hacer al perder línea está partida entre RPi (que manda angle=0) y Teensy (que va derecho), sin coordinación. Combinado con la ausencia de heartbeat (#53), si la RPi se cuelga, la Teensy también va derecho con el último `speed/steer` — peligroso.

**Riesgo si NO se toca.** En gaps de línea (permitidos en Rescue Line) o tras una maniobra que deja al robot fuera de la línea, el robot se va recto y no recupera → LoP / sale de pista (P1-P2 según frecuencia de gaps en la pista). Lo dejo en P2 porque el reglamento permite gaps cortos y "ir derecho" a veces alcanza, pero es claramente subóptimo.

**Riesgo si se toca.** Medio. Una rutina de búsqueda mal calibrada (barrido muy amplio) puede hacer que el robot "se pierda buscando" en una recta con sombra. Coordinar con RPi para distinguir "gap real" de "línea perdida por visión".

**Fix propuesto.** Estrategia conservadora: en RPi, en vez de `angle=0` al perder línea, mantener el **último ángulo válido** unos frames (memoria corta) antes de declarar pérdida; en Teensy, si pasan N iteraciones con línea perdida, un micro-barrido. Es trabajo conjunto RPi+Teensy → coordinar con `rpi-vision`.
**Validación.** Pista con gap de línea: el robot lo cruza. Curva con pérdida momentánea: recupera.
**Tiempo.** 1–2 h conjunto + banco.
**Prioridad: P2** (oportunidad de robustez).

---

### F-11 — [P2] Frenado en bajada / control de pendiente: `ajustarVelocidadPorPendiente` sólo detecta subida, ignora bajada; y `leer_pitch` puede no leer el eje correcto

**Hallazgo NUEVO** (oportunidad "frenado en bajada" del encargo; relacionado con oportunidad #5 del plan).

**Causa A — sólo mira subida.** `ajustarVelocidadPorPendiente` (líneas 628–641):
```cpp
leer_pitch();
if (pitch > 10) velocidadAjustada = 30;   // subida → MÁS rápido (para no quedarse)
else            velocidadAjustada = 25;    // resto → 25
return velocidadAjustada;
```
- Sólo contempla `pitch > 10` (subida). **No hay rama para bajada** (`pitch < -10` o el equivalente según signo del BNO). En una rampa hacia abajo, el robot va a 25 (igual que en plano) y **no frena**, con riesgo de embalarse / volcar / pasarse la línea por inercia. La oportunidad #5 del plan maestro ("reducir velocidad en bajadas para evitar volcamientos") **no está implementada**; sólo está el caso de subida.

**Causa B — signo/eje del pitch dudoso.** `leer_pitch()` (líneas 617–622) asigna `pitch = event.orientation.y`. En el BNO055 en modo `NDOF`, `orientation.y` es el **pitch** y `orientation.z` el **roll** (o viceversa según montaje y librería). El umbral fijo `pitch > 10` asume un signo y un eje concretos que **no están documentados ni verificados** contra el montaje físico del robot. Si el sensor está rotado 90° respecto de lo asumido, podría estar leyendo roll en vez de pitch. (Verificable sólo en banco con el robot inclinado.)

**Causa C — interacción con #B5.** En case 7, la velocidad de **curva** (55) ignora por completo la pendiente (no pasa por `ajustarVelocidadPorPendiente`). O sea: en una **curva en bajada** el robot va a 55 sin freno alguno → peor caso para volcar/salir.

**Riesgo si NO se toca.** Embalamiento en bajadas (especialmente curva-en-bajada por #B5) → salida de pista / vuelco / víctima perdida (P2, depende de si la pista de Incheon tiene rampas pronunciadas — RCJ suele tenerlas). Lo marco P2 porque depende de la pista, pero puede escalar a P1 si hay rampa+curva.

**Riesgo si se toca.** Bajo-medio. Agregar la rama de bajada es simple, pero si el eje/signo del pitch está mal asumido (Causa B), la corrección podría frenar en el momento equivocado. **Validar primero el signo del pitch en banco** antes de confiar en el umbral.

**Fix propuesto.**
1. Verificar en banco qué eje/signo da el BNO al inclinar el robot (imprimir `orientation.x/y/z` con el robot en rampa de subida y bajada).
2. Agregar rama de bajada: `else if (pitch < -8) velocidadAjustada = 18;` (frenar).
3. Hacer que la velocidad de curva (case 7, el `55`) **también** pase por el ajuste de pendiente (no embalar en curva-bajada). Esto se resuelve naturalmente al arreglar #B5/F-05 con una sola función de velocidad.

**Validación.** Banco con rampa: medir velocidad en subida/bajada/plano. Pista con rampa: 5 pasadas sin vuelco ni salida. Registrar.
**Tiempo.** 30 min código + 1h banco (incluye verificar eje del pitch).
**Prioridad: P2** (escala a P1 si la pista tiene rampa+curva).

---

## 3. Transversal — Timeouts revertidos en `cead75e` (impacto en TODA la navegación)

**Confirma y data la familia de RESILIENCIA (#27/#57/#119, timeouts).**

`git log` muestra: el commit `5bac4a5 "feat(teensy): timeouts implementados"` agregó timeouts a los `while` bloqueantes (gates `fixIssue58Enabled()`, `fixIssue60Enabled()`, `fixIssue61Enabled()`, `computeRunDistanceTimeoutMs(...)`, con guardas `millis()`). El commit siguiente `cead75e "fix(teensy): error de libreria claw.cpp"` (Benjamin, 2026-05-10) **borró 181 líneas** (`+13 −181`) y **revirtió esos timeouts**. El `main.cpp` actual **no tiene ningún timeout** en sus `while` de navegación:

- `runTime` (líneas 411–433): `while((millis()-startTime) < time)` — éste SÍ tiene cota natural por `time`, OK.
- `runAngle` (líneas 446–528): `while(true)` — **sin timeout** (F-06).
- `runDistance` (líneas 540–588): `while(true)` por encoder — **sin timeout** (cuelga si la rueda patina y nunca llega al pulso objetivo).
- `case 1` re-adquisición (líneas 947–956, 962–971): `while(digitalRead(32)==0)` — **sin timeout** (F-04).
- `case 12` while interno (líneas 1087–1112): **sin timeout** (F-07).
- Bucles de rescate (líneas 1230–1267): `while(digitalRead(32)==0)` — **sin timeout** (fuera de mi dominio, pero misma clase; ver #57).

**Por qué pasó (hipótesis).** El mensaje "error de libreria claw.cpp" sugiere que se revirtió un conjunto grande de cambios para resolver un problema de compilación/librería de la pinza, y los timeouts se fueron "de arrastre" en esa reversión masiva — probablemente **no intencional** respecto de los timeouts. **Verificar con Benjamin** si la pérdida de timeouts fue deliberada o colateral.

**Riesgo si NO se restituyen.** Cualquier maniobra que no converge (rueda patina, robot trabado, sensor de color no ve negro, IMU ruidosa) **cuelga el robot permanentemente** — sin WDT real que lo saque (ver #53/#27). Es la categoría P0 de "se cuelga / no completa corrida". Afecta F-04 y F-06 directamente.

**Riesgo si se restituyen.** Bajo-medio. Re-aplicar timeouts bien acotados es seguro; el riesgo es elegir un timeout **muy corto** que aborte una maniobra legítima (p.ej. un giro lento). Usar márgenes generosos (giro 180°: ~3–4s; runDistance: proporcional a la distancia).

**Fix propuesto.** Recuperar la lógica de `5bac4a5` (está en git, `git show 5bac4a5`) o re-implementar timeouts simples por bucle. **Es probablemente el fix de mayor ROI de robustez antes de Incheon.** Coordinar con la auditoría de RESILIENCIA para no duplicar Issues (#57/#27 ya lo cubren parcialmente).
**Validación.** Banco: trabar físicamente el robot a mitad de un `runDistance`/`runAngle` y verificar que sale por timeout (no se cuelga). Registrar.
**Tiempo.** 1–2 h (recuperar de git + re-tunear timeouts) + banco.
**Prioridad: P0** (cuelgue permanente; ya parcialmente trackeado en #57/#27).

---

## 4. Otros puntos menores (P2, deuda)

| # | Hallazgo | Ubicación | Nota |
|---|---|---|---|
| M-1 | `random(3)` muerto (resultado pisado por la línea siguiente) | main.cpp:941 | Borrar. Cubierto en F-04. |
| M-2 | Variables zombi de cooldown/steer (`lastTurn`, `turnCooldown`, `laststeer`, `counter`, `steertimer`, `contador`, `retroceder`) declaradas y nunca usadas (o sólo en bloques comentados) | main.cpp:34–36,48–49,51 | Cablear (F-08) o borrar. Confunden el código. |
| M-3 | `green_state` nunca se resetea a 0 en la Teensy; depende 100% de que la RPi mande 0 cada frame | main.cpp (global) | Si la RPi deja de mandar (cuelgue), `green_state` queda "pegado" en el último valor → maniobra fantasma. Mitigado por heartbeat (#53). |
| M-4 | `get_color()` bloqueante (`while(!colorDataReady) delay(5)`) llamado en el hot-loop de línea cada iteración | main.cpp:331–339,887 | Aunque la línea se sigue por cámara (RPi), la Teensy lee color cada vuelta y puede frenarse esperando el APDS. Considerar lectura no-bloqueante. |
| M-5 | `case 6` usa `runAngle(35,...,-60)` y `case 5` usa `runAngle(25,...,+60)`: **velocidades de giro distintas** (35 vs 25) para maniobras simétricas | main.cpp:1051,1059 | Inconsistencia: el giro a izquierda es más rápido que a derecha. Probablemente no intencional. Unificar. |
| M-6 | `serialEvent5()` se llama manualmente dentro de varios cases (5,6,12,14) pero NO en case 7 (line-track) | main.cpp | En line-track, el refresco de `speed/steer` depende del yield entre iteraciones del while; si el cuerpo del while es largo (color+tof+ultrasonidos bloqueantes), el steer puede quedar viejo. |
| M-7 | `front_distance < 12` dispara esquiva con un único ping (sin filtro/confirmación) | main.cpp:921–924 | Un ping ultrasónico espurio (eco fantasma) puede disparar una esquiva innecesaria a mitad de línea. Confirmar con 2 lecturas. |

---

## 5. Tabla resumen priorizada

| ID | Prioridad | Finding | ¿Trackeado? | Tiempo | Acción |
|---|---|---|---|---|---|
| **F-01** | **P0** | `taskDone` roto: arranque depende de doble-toggle del switch | NUEVO | 5 min (a) | Inicializar `taskDone=true` |
| **F-04** | **P0** | Esquiva `random` sin seed + ciega + while sin timeout | parcial (#57) | 5min–2h | Seed + decisión por sensor + timeout |
| **§3** | **P0** | Timeouts revertidos en `cead75e` → cuelgue permanente | parcial (#57/#27) | 1–2h | Recuperar timeouts de `5bac4a5` |
| **F-02** | **P1** | `speed` de RPi ignorado en line-track | NUEVO | 30 min | Usar `speed` o documentar |
| **F-03** | **P1** | Línea roja fin-de-pista (`green_state==10`) ignorada | NUEVO | 30 min | Agregar case stop |
| **F-05** | **P1** | #B5 vel 55 en curva (invertido) — salidas de pista | **#122** | 15min+tune | Invertir relación vel↔steer |
| **F-06** | **P1** | #B8 `runAngle(180)` ignora signo + no converge | **#125** | 10min+tune | `(error>0)?1:-1` + timeout |
| **F-07** | **P1** | #58 case 12 fall-through + while 1-shot + es inalcanzable | **#58** | 15 min | `break` o borrar case 12 |
| **F-08** | **P1** | Sin anti-rebote de verde (cooldown declarado pero muerto) | NUEVO | 45 min | Cablear `turnCooldown` |
| **F-09** | **P2** | "FSM" es while bloqueante (PID se congela en maniobras) | plan #3 | semanas | NO pre-Incheon |
| **F-10** | **P2** | Sin recuperación de línea perdida | NUEVO | 1–2h | Memoria de ángulo + barrido |
| **F-11** | **P2** | Pendiente sólo detecta subida, no bajada (sin frenado) | plan #5 | 30min+banco | Rama bajada + verificar eje |
| M-1..M-7 | P2 | Limpieza / deuda menor | varios | — | Ver tabla §4 |

---

## 6. Recomendación de secuencia para Incheon (opinión del auditor)

A 6 semanas del mundial, con la regla de oro #4 en mente, **propongo** (decisión final de Enzo/Gustavo):

**Bloque 1 — "no se cuelga ni queda quieto" (P0, ~medio día de banco):**
1. **§3** recuperar timeouts (mayor ROI de robustez; está en git).
2. **F-01** inicializar `taskDone=true` (1 carácter; elimina el "robot quieto al soltar").
3. **F-04** mínimo: `randomSeed()` + timeout en el while de esquiva.

**Bloque 2 — "no se va de pista ni dobla mal" (P1, ~1 día de banco):**
4. **F-05/#B5** invertir velocidad curva (la causa #1 de salidas).
5. **F-06/#B8** signo del giro 180°.
6. **F-08** cablear cooldown de verde.
7. **F-03** stop en línea roja (coordinar con RPi para falsos positivos).
8. **F-07/#58** `break` en case 12 (o borrarlo).

**Bloque 3 — sólo si hay tiempo / no antes:** F-02, F-10, F-11, M-*.
**NO TOCAR antes de Incheon:** F-09 (reescritura a FSM).

**Regla de validación (no negociable, `CLAUDE.md` #3):** cada fix que se mergee va con entrada en `testing/TEST_LOG.md` (robot enciende, motores responden, no hay cuelgue). Ningún cambio de los bloques 1–2 debería mergearse sin al menos 3 corridas de banco documentadas.

---

## 7. Notas de método

- Leídos completos: `main.cpp` (1279 líneas), `drivebase.cpp/.h`, `PID.cpp/.h`, `Main.py` (850 líneas, para verificar el protocolo real que recibe la Teensy).
- Verificaciones con `git log`/`git show` sobre `cead75e` y `5bac4a5` (reversión de timeouts) y `grep` para variables muertas (`lastTurn`, `randomSeed`, `taskDone`, `green_state=`, `action=`).
- Issues leídos (solo lectura): #58, #57, #53, #119, #120–#128 (en particular #122/#B5 y #125/#B8).
- **No** se modificó código ni se crearon/editaron Issues, conforme a las reglas del encargo.
- Hallazgos marcados "NUEVO" no aparecían en auditorías previas; los marcados con #NNN confirman/amplían un Issue existente.
