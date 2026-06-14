# Auditoría integral 2026-05-18 — Módulo SERIAL del Teensy (lado C++)

> **Dominio:** `serialEvent5`, parser del protocolo `[255,speed,254,angle,253,green,252,silver]`, framing, bytes de control (0xFF/0xF9/0xF8/0xFA…), drenaje del buffer `Serial5` y *fail-safe* del enlace.
> **Archivo único auditado:** [`software/teensy/firmware/src/main.cpp`](../../../../software/teensy/firmware/src/main.cpp) (estado post-merge PR #101, branch `feature/initialize-testing-log`; contenido idéntico al de `main`).
> **Solo lectura.** No se modificó código. No se abrieron/editaron issues.
> **Auditor:** Claude Code (Opus 4.8, 1M) bajo dirección de Gustavo Viollaz. Fecha 2026-05-18.

---

## 0. Cómo leer este informe (regla del coach)

Cada finding lleva, además de la causa y el fix:

- **Riesgo de NO arreglar** (qué pasa en Incheon si lo dejamos como está).
- **Riesgo de arreglar** (qué subsistema validado podríamos romper — los chicos llevan meses tuneando esto).
- **Tiempo estimado** del cambio (no del testing en banco, que va aparte).

Esto **no** es una lista de "bugs a fixear ya". Es material para decidir, con la competencia encima, qué tocar y qué dejar quieto. Varias cosas acá **conviene NO tocarlas antes del mundial** y están marcadas como tal.

**Relación con auditorías previas:** este informe **NO repite** los issues #63, #70 y #72 ni el doc [`analisis-integral-comunicacion-2026-05-10.md`](../../../../docs/es/analisis-integral-comunicacion-2026-05-10.md). Los **cita** y agrega lo que esos no vieron al mirar el código real de hoy. Donde un finding refina o contradice algo previo, lo digo explícito.

---

## 1. Estado del arte: qué ya está dicho (y NO repito)

| Ref previa | Qué dice | Estado en el código HOY |
|---|---|---|
| **#70** ([P1]) | `serialEvent5()` consume 1 byte por llamada → necesita 8 iteraciones de `loop()` para un frame. Fix: `while` en vez de `if`. | **Sigue abierto.** Línea 385 sigue con `if (Serial5.available() > 0)`. Confirmo el bug. |
| **#63** ([P1]) | `runTime`/`runDistance` leen bytes durante maniobras y los **descartan sin parsear** (`Serial.print(lecturas)`). Fix: llamar `serialEvent5()`. | **Sigue abierto.** Líneas 418-422, 553-556, 576-579 intactas. Confirmo. |
| **#72** ([P1]) | Sin handshake al boot. Fix propuesto: Teensy manda `0xFA` ×20 en `setup()`; RPi vuelve a `esperando` al recibirlo. | **Parcialmente implementado, asimétrico.** Ver §2.1 — **es el hallazgo más grave de este informe.** |
| Doc §5.2 | Parser sin sanity-check de rangos (`speed`, `steer` sin clamp). | Confirmo: líneas 398-404 sin clamp. `DriveBase::steer` clampa silenciosamente (`drivebase.cpp:112-113`). No lo re-desarrollo. |
| Doc §5.6 | Buffer `Serial5` (1 KB) puede llenarse en maniobras largas. | Confirmo y **lo agravo** con datos nuevos: ver §2.4. |
| Doc §6.1 | Heartbeat Teensy→STOP a 500 ms (issue #53). | **No implementado.** Lo retomo con un ángulo nuevo en §2.5 (por qué el diseño del doc no alcanza con el `loop()` actual). |

Lo que sigue es **material nuevo** surgido de leer `main.cpp` completo, no de oficina.

---

## 2. Findings nuevos (lado C++ serial)

### 2.1 — `serialEvent5()` NO es un *event handler*: el `loop()` casi nunca le devuelve el control al core → la recepción serial depende de 9 llamadas manuales dispersas

**Severidad técnica: P0.** Es el hallazgo central y no está en ninguna auditoría previa.

**Causa.** En Teensyduino, `serialEventN()` es una *callback* que el runtime invoca **solo cuando `loop()` retorna** (el core la llama desde `yield()`/entre iteraciones de `loop`). El `loop()` de este firmware **prácticamente nunca retorna**: se queda atrapado en bucles infinitos por diseño —

```cpp
while (rutina == "linea"  && digitalRead(32) == 0) { ... }   // línea 884
while (rutina == "rescate"&& digitalRead(32) == 0) { ... }   // línea 1129
while (true) { ... }                                          // línea 823 (switch off)
```

Mientras el robot corre, está **dentro** de uno de estos `while`. La callback automática `serialEvent5()` **no se dispara**. Por eso el equipo terminó **llamando `serialEvent5()` a mano** en 9 puntos:

```
línea  599  (nonBlockingDelay)
línea 1048  (case 6 verde izq)
línea 1056  (case 5 verde der)
línea 1081, 1090  (case 12)
línea 1116  (case 14)
línea 1133  (tope del while rescate)
línea 1193  (post-248 depositar)
```

Y comentadas en 950 y 965 (`// serialEvent5();`).

**Consecuencia real.** La frecuencia con que el Teensy "escucha" a la RPi **no es periódica ni está acotada**: depende de por qué `case` del `switch` esté pasando. En `case 7` (line-track, el 90 % del tiempo) **no hay ninguna llamada a `serialEvent5()` dentro del case** — el parseo del frente del buffer ocurre solo en la próxima vuelta del `while(rutina=="linea")`, que primero hace `get_color()` (que **bloquea** con `while(!apds.colorDataReady()) delay(5)`, líneas 336-339), `leer_tof()` y `leer_ultrasonidos()` (cada `ping_cm()` bloquea hasta ~5,8 ms × 3 sonares). O sea: entre dos lecturas del serial pueden pasar fácilmente **20-40 ms aun en el caso bueno**, y mucho más si un sonar hace timeout.

> **Por qué esto NO es lo mismo que #70.** #70 dice "el frame tarda 8 iteraciones de `loop`". Pero el `loop()` **no itera** mientras estás en line-track; iteras el `while` interno. El problema no es "8 loops", es "la callback no existe en la práctica y el muestreo del serial está atado a sensores bloqueantes". El fix de #70 (poner `while`) es **necesario pero no suficiente**: drena rápido *cuando se lo llama*, pero no cambia *cuándo* se lo llama.

- **Riesgo de NO arreglar:** latencia visión→acción alta y **variable** (jitter). En curvas cerradas el ángulo que actúa el Teensy puede ser de hace 30-50 ms → sobrepaso de línea, sobre todo a `speed=55` (case 7, línea 1068). Es coherente con el síntoma "el robot se pasa de la línea" que ya motivó otras revisiones.
- **Riesgo de arreglar:** **Medio-alto.** Meter `serialEvent5()` dentro de `case 7` (line-track) cambia `speed`/`steer` en medio del ciclo de control que los chicos ya tunearon. Si se hace mal, se altera el comportamiento del seguidor validado. **No es un cambio cosmético.**
- **Fix recomendado (mínimo y seguro):** agregar **una sola** llamada `serialEvent5()` al **tope** del `while(rutina=="linea")` (antes de `get_color()`), de modo que cada vuelta refresque el frame ANTES de decidir `action`. Combinarlo con el `while`-drain de #70. No tocar el interior de los `case`.
- **Tiempo:** 10 min el cambio; el testing en banco es lo caro (validar que el seguidor no degrada).
- **Decisión sugerida:** **SÍ** vale para el mundial, pero medido — aplicar #70 primero, después esta llamada única, y comparar en banco con el TEST_LOG. Si el seguidor se degrada, revertir (regla de oro #4).

---

### 2.2 — La lectura "de debug" en `runTime`/`runDistance` **descarta bytes de control y desincroniza el framing** (agravante de #63 que #63 no menciona)

**Severidad técnica: P1.**

**Causa.** #63 ya señala que `runTime`/`runDistance` descartan comandos. Pero hay un daño **adicional y peor** que #63 no nombra: lo que descartan puede ser un **sync byte** (255/254/253/252), y eso **rompe el framing** del próximo parseo real.

```cpp
// runTime, líneas 418-422
if (Serial5.available() > 0) {
    int lecturas = Serial5.read();   // ← consume UN byte cualquiera y lo tira
    Serial.print(lecturas);
}
```

El parser de `serialEvent5()` es un **autómata con estado persistente** (`serial5state`, global, línea 52). Si durante un `runTime` se consume y descarta —por ejemplo— el `0xFE` (254, marcador de `angle`), el byte siguiente (el valor de `angle`, p. ej. 130) **queda en el buffer**. Cuando termina el `runTime` y se vuelve a llamar `serialEvent5()`, ese 130 se interpreta con el `serial5state` que haya quedado de antes → **se asigna al campo equivocado**. Resultado: `speed`, `steer` o `green_state` con basura durante uno o varios frames hasta que, por suerte, vuelva a alinear con el siguiente `255`.

Esto es especialmente peligroso porque los `runTime(0, …)` "quietos" abundan (p. ej. `runTime(0,FORWARD,0,3000)` en líneas 985, 1043, 1140, 1148…): 3 segundos drenando y **desalineando** el buffer byte a byte.

- **Riesgo de NO arreglar:** tras cada maniobra larga, ráfaga de 1-N frames mal interpretados. Si el frame mal leído cae en `green_state`, puede disparar una acción equivocada (p. ej. leer un `angle=130` como `green_state=…` no aplica acá porque el valor no matchea casos, pero un `speed` alto interpretado como otra cosa sí puede mover el robot). Probabilísticamente bajo por frame, pero **se repite en cada maniobra**.
- **Riesgo de arreglar:** **Bajo**, si se hace como dice #63 (reemplazar el `read()` ciego por `serialEvent5()`, que respeta el autómata). El riesgo que advierte #63 (que `serialEvent5` pise `speed/steer` durante la maniobra) es real pero acotado: `runTime` usa sus **parámetros locales** `speed/dir/steer`, no los globales, así que actualizar los globales no altera la maniobra en curso.
- **Fix:** el de #63 (llamar `serialEvent5()` en vez de `read()+print`). **Como mínimo**, si no se quiere parsear, **drenar entero** (`while(Serial5.available()) Serial5.read();`) para no dejar el buffer a mitad de frame — peor es leer 1 byte y dejar el resto desalineado.
- **Tiempo:** 15 min (es el mismo cambio de #63, aplicado a las 3 ramas).
- **Decisión sugerida:** **SÍ**, junto con #63. El agravante de framing eleva la prioridad de #63 de "perdés comandos" a "podés meter basura en variables de control".

---

### 2.3 — El parser **no auto-limpia el comando consumido**: `green_state` es "sticky" y puede **re-disparar rutinas de rescate completas**

**Severidad técnica: P1 (potencial P0 en rescate).** No está en auditorías previas.

**Causa.** El parser escribe `green_state = data` (línea 402) y nunca lo vuelve a 0. El **consumidor** tampoco lo limpia tras actuar. En el `while(rutina=="rescate")` (1129-1276):

```cpp
serialEvent5();                          // 1133: puede o no traer frame nuevo
robot.steer(speed, FORWARD, steer);
if (green_state == 6) { /* rutina negra completa, ~6 s bloqueantes */ ball_counter++; }
if (green_state == 7) { /* rutina plateada completa */ ball_counter++; }
```

La rutina de `green_state==6` tarda varios segundos (varios `nonBlockingDelay(1000…1400)` + `runDistance` + `runTime`). Cuando termina y el `while` vuelve a girar, llama `serialEvent5()` —pero si **todavía no llegó un frame nuevo** que reescriba `green_state` (muy posible: la RPi en `modo_rescate` envía a ~15-20 fps pero el Teensy estuvo 6 s ocupado y el buffer trae frames **viejos** encolados, ver §2.4), `green_state` **sigue valiendo 6** → **se ejecuta la recolección de nuevo** sobre una pelota que ya no está.

Mismo patrón con `green_state==8/9` (depósito rojo/verde, líneas 1196-1220): si no se refresca, **vuelve a depositar**.

> Nota de diseño: en `linea` (`taskDone`), `action` sí se reasigna desde `green_state` en cada vuelta y `case 14` hace `action=7` al final — ahí el riesgo es menor. El problema agudo es en **rescate**, donde no hay reset.

- **Riesgo de NO arreglar:** doble-recolección / doble-depósito → el robot repite una maniobra sobre vacío, pierde tiempo y **puede tirar la pelota que ya tenía** o golpear pared. Impacta directo el objetivo "auto-recuperación 8/10" y puntaje de rescate.
- **Riesgo de arreglar:** **Bajo.** Agregar `green_state = 0;` (o `255`/centinela neutro) **inmediatamente después** de consumir cada rutina de rescate. No afecta line-track.
- **Fix:** al final de cada bloque `if (green_state==6/7/8/9)`, resetear `green_state = 0;`. Alternativa más limpia: que la RPi mande un "comando nulo" explícito tras cada acción (pero eso toca los dos lados → más riesgo, no antes del mundial).
- **Tiempo:** 10 min (4 líneas).
- **Decisión sugerida:** **SÍ**, alto valor / bajo riesgo. De lo más rentable de este informe para rescate.

---

### 2.4 — Confirmación + agravante de §5.6 del doc: durante los segundos bloqueantes el buffer encola **frames viejos**, y al volver se procesan **stale** (no hay "quedarse con el último")

**Severidad técnica: P1.**

**Causa.** El doc §5.6 dice "el buffer (1 KB) puede llenarse" y lo trata como riesgo de *overrun*. El problema real, leyendo el código, es más sutil y **no se resuelve solo con drenar rápido**: la RPi manda ~240 B/s; una maniobra de rescate bloquea 4-6 s → llegan **~1-1,4 KB** → el buffer de 1 KB **se llena y descarta** (Teensyduino tira los bytes nuevos cuando el ring está lleno, no los viejos). Cuando el Teensy vuelve, el `while`-drain (si se aplica #70) procesa **del más viejo al más nuevo**, y el último frame que queda **no es el más reciente de la RPi** sino el último que entró antes de que el ring se llenara. El robot actúa sobre una foto **vencida**.

Hoy, **sin** el fix de #70, es aún peor: drena 1 byte por llamada, así que tras 6 s con 1 KB encolado necesitaría ~1000 llamadas a `serialEvent5()` para vaciarlo — efectivamente **nunca alcanza el frame actual** y arrastra retraso acumulado.

- **Riesgo de NO arreglar:** decisiones sobre datos viejos justo al salir de cada maniobra; sensación de "lag" y de que el robot "no reacciona" un instante. Acumulativo.
- **Riesgo de arreglar:** **Bajo.** Dos medidas independientes:
  1. **Ampliar el buffer** no resuelve el *stale* (lo difiere). **No** recomiendo `addMemoryForRead` como única medida.
  2. **Drenar y quedarse con el último frame**: al entrar/salir de maniobra, hacer `Serial5.clear()` antes de la primera lectura útil, o parsear en bucle quedándote solo con el frame más nuevo. El código **ya hace `Serial5.clear()`** en el kill-switch (líneas 427, 813) — falta hacerlo al **salir** de cada rutina de rescate.
- **Fix:** tras cada rutina de rescate larga, `Serial5.clear();` **antes** del siguiente `serialEvent5()`, para descartar el backlog vencido y leer fresco. Esto se complementa con #70 (drain) y con §2.3 (reset de `green_state`).
- **Tiempo:** 10 min.
- **Decisión sugerida:** **SÍ**, pero **coordinado** con §2.3 (si reseteás `green_state` y limpiás el buffer juntos, evitás tanto la re-ejecución como el stale). Probar en banco que no se "pierde" el frame que dispara la siguiente acción.

---

### 2.5 — El handshake de boot `0xFA` (#72) está implementado en la RPi pero **NO en el Teensy**: protocolo medio hecho → el *fail-safe* de reset **no funciona**

**Severidad técnica: P1.** Hallazgo nuevo de **integración cruzada** que solo se ve mirando los dos lados juntos.

**Causa.** La RPi (`Main.py`) **ya tiene** todo el receptor del handshake de #72:

```python
TEENSY_BOOT = b'\xfa'                       # línea 31
...
if data == TEENSY_BOOT:                      # handle_control_byte, líneas 156-159
    print("[INFO] ...: Teensy reseteado -> esperando")
    estado = 'esperando'
    return 'boot'
```

Pero el **Teensy NUNCA escribe `0xFA`**. Confirmado por búsqueda exhaustiva: los únicos `Serial5.write` del firmware son **255** (×5: 427, 453, 559, 582, 822), **249** (862) y **248** (1191). `setup()` (736-798) **no emite ningún byte de boot**. El `for(20){ Serial5.write(0xFA); }` que proponía #72 **no se aplicó del lado del firmware**.

**Consecuencia.** El gap que #72 quería cerrar **sigue completamente abierto**, pero ahora con una falsa sensación de cobertura: alguien que lea `Main.py` va a creer que "el reset del Teensy ya está manejado". No lo está. Si el Teensy se resetea (brownout por motores, watchdog, reflash) mientras la RPi está en `linea`/`rescate`:

- El Teensy arranca, ejecuta `setup()`, entra al `loop()`. Con el switch **encendido** (caso típico en pista), cae en la rama `digitalRead(32)==0 && !startUp` (línea 849), hace el bailecito de arranque y manda **`Serial5.write(249)`** (línea 862) **una sola vez**.
- La RPi, si estaba en `linea`, al recibir `0xF9` (249) cae en `handle_control_byte`: `if estado=='esperando': estado='linea'` — pero **no está en 'esperando'**, está en 'linea', así que el `249` **se ignora** (retorna `'ready'` sin efecto). La RPi sigue en `linea` mandando frames; el Teensy ya está en línea también… o no, según el timing. Queda un sistema **frágil y dependiente del azar del estado**.

Además, ese `Serial5.write(249)` es **único y sin reintentos**: si la RPi justo está bloqueada en inferencia YOLO o el byte se pierde, el arranque **no se completa** y no hay reintento (contradice el propio patrón ×20 que #72 recomendaba para `0xFA`).

- **Riesgo de NO arreglar:** ante cualquier reset del Teensy en pista (los brownouts por corriente de motores son **reales** en estos robots), el sistema queda desincronizado, robot inerte o errático, **sin diagnóstico**. Es exactamente el escenario que #72 documentó como "robot inerte". Pega de lleno en "auto-recuperación 8/10".
- **Riesgo de arreglar:** **Bajo.** El receptor ya existe en la RPi y está probado en estructura. Solo falta el emisor en Teensy. No cambia frames existentes.
- **Fix (lado Teensy, el que falta):** al final de `setup()`, emitir el boot signal que la RPi **ya espera**:
  ```cpp
  for (int i = 0; i < 20; i++) { Serial5.write(0xFA); delay(100); }  // 2 s, como #72
  ```
  Y **revisar el `startUp`**: hoy `0xFA` haría que la RPi vuelva a `esperando`, pero el Teensy necesita que la RPi le re-confirme o que su propio `startUp` se reinicie coherentemente. Lo mínimo seguro: emitir `0xFA` en `setup()` y dejar que el flujo `esperando→(249)→linea` se rehaga.
- **Tiempo:** 15 min el emisor. (La coordinación fina del re-arranque, otros 30-45 min de banco.)
- **Decisión sugerida:** **SÍ — es el de mayor relación valor/riesgo de todo el informe.** El 50 % del trabajo (RPi) ya está hecho y sin pareja. Cerrar el otro 50 % es trivial y activa un *fail-safe* que hoy es ilusorio. **Recomiendo priorizarlo sobre cualquier otro finding serial.**

---

### 2.6 — `green_state` multiplexa 3 "espacios de comando" sobre un mismo byte sin discriminador de modo → ambigüedad estructural

**Severidad técnica: P2 (deuda de diseño, no tocar antes del mundial).**

**Causa.** El mismo campo `green_state` transporta significados **disjuntos según el modo**:

| Valor | En `linea` | En `rescate`/`depositar` |
|---|---|---|
| 0-3 | verdes/giro | (no aplica) |
| 6,7 | — | recolección plateada/negra |
| 8,9 | — | depósito rojo/verde |
| 10 | línea roja | — |
| 14-17 | callejón/intersección (case 12/14) | — |

El **único** discriminador es la variable `rutina` (`"linea"`/`"rescate"`), que vive **solo en el Teensy**. El frame **no lleva** el modo. Si por la desincronización de §2.5 los dos lados discrepan de modo, el **mismo byte** se interpreta distinto en cada extremo. Es la raíz que hace que §2.3 y §2.5 sean tan dañinos: no hay forma, a nivel de protocolo, de detectar que `green_state=6` llegó "fuera de contexto".

- **Riesgo de NO arreglar:** ninguno *nuevo* mientras los modos estén sincronizados; amplifica los otros findings cuando se desincronizan.
- **Riesgo de arreglar:** **Alto.** Separar en campos/opcodes toca el parser y la RPi → es protocolo v2. El doc §7 ya lo manda explícitamente a **fase 3, post-mundial**. Coincido.
- **Decisión sugerida:** **NO** antes de Incheon. Dejar como deuda documentada. Mitigar los síntomas con §2.3 + §2.5, que son baratos.

---

### 2.7 — `serial5state` es global persistente y el parser **no tiene resync ante pérdida de cuadro**

**Severidad técnica: P2.**

**Causa.** El parser (383-406) usa `serial5state` global. No hay timeout de frame ni mecanismo de re-sincronización: si se pierde **un** sync byte (ruido, o el descarte de §2.2), el autómata queda "corrido" hasta que **casualmente** vuelva a llegar un `255`. Como `speed∈[0,100]` y `angle+90∈[90,270]`… ojo: **`angle+90` puede llegar a 270 > 255** si `angle>165`. Veamos: la RPi hace `clamp_byte(angle+90)` (Main.py línea 104) que satura a 255. Con `angle∈[0,180]`, `angle+90∈[90,270]` → **se satura a 255 para angle≥165**. Es decir, **un `angle` real ≥165° se transmite como 255 = sync byte de speed**. Colisión real, no teórica.

> El doc §5.5 afirma "angle ∈ [0,180] tras +90 → no toca [252,255] ✅". **Eso es incorrecto:** `180+90=270`, y aunque `clamp_byte` lo corta a 255, **255 ES un sync byte**. Un giro fuerte (angle cercano a 180 en el frame de visión) puede emitir un payload = 255 que el Teensy lee como "viene speed". Es un caso borde pero **alcanzable** en curvas muy cerradas o en el `angle=int(-error_norm*90)` de rescate (que da [-90,90] → +90 = [0,180] → +90 otra vez NO; en rescate el frame manda `angle` directo, ver Main.py 637/645). En line-track, `round(angle)` con `angle=(atan2…)-90 ∈ [-90,90]`, +90 ⇒ [0,180]; el extremo 180 es improbable pero no imposible.

- **Riesgo de NO arreglar:** raro, pero cuando pasa, el frame se corre y mete basura hasta el próximo `255` legítimo. Combina mal con §2.2.
- **Riesgo de arreglar:** **Bajo** del lado Teensy (sanity check), pero el fix correcto es **acotar `angle` a [0,164] del lado RPi** o reservar 255 solo como sync (clamp a 251). Eso toca la RPi → coordinación.
- **Fix mínimo (Teensy):** en el parser, si `serial5state` lleva mucho sin ver un sync esperado, o ante valores imposibles, **descartar y esperar `255`**. Documentar el contrato real: **payload ≤ 251** para no colisionar con 252-255.
- **Tiempo:** 20-30 min (parser + clamp RPi coordinado).
- **Decisión sugerida:** **Tal vez.** Bajo riesgo, bajo costo, pero baja probabilidad de gatillarse. Si hay tiempo después de §2.1/2.3/2.5, hacerlo. Si no, documentar el contrato (`payload∈[0,251]`) como comentario en el parser — eso es 5 min y evita que un futuro `green_state=254` rompa todo (§5.5 del doc).

---

### 2.8 — Variables de control **no `volatile`** y leídas/escritas sin sección crítica

**Severidad técnica: P2 (hoy benigno, frágil a futuro).**

**Causa.** `speed` (double), `steer` (double), `green_state` (int), `silver_line` (int) son globales **planas** (líneas 53-56). Hoy `serialEvent5()` se llama **siempre desde contexto `loop()`** (manualmente), **nunca desde un ISR**, así que no hay race real. **Pero**: (a) el diseño *asume* que `serialEvent5` podría ser la callback del core (que corre fuera de tu `loop`), y (b) `double` no es atómico en el M7 — si alguien algún día llama el parser desde un timer/ISR, `speed`/`steer` se corrompen a media escritura. Es una **trampa latente**, no un bug activo.

- **Riesgo de NO arreglar:** **ninguno hoy.** Riesgo si alguien mueve la recepción serial a un `IntervalTimer`/ISR (tentador para arreglar §2.1).
- **Riesgo de arreglar:** marcar `volatile` es inocuo en correctitud pero puede **frenar optimizaciones** del compilador en los `case` que leen `steer` en caliente (line-track). Bajo, pero medible.
- **Decisión sugerida:** **NO tocar ahora.** Anotar como nota: *"si se migra la recepción serial a ISR/timer, hacer `volatile` + leer `speed`/`steer` bajo `noInterrupts()`"*. Es prevención, no acción.

---

### 2.9 — El `Serial5.write(255)` del kill-switch comparte byte con un payload válido y **no resetea `silver_line`/`green_state`** al apagar

**Severidad técnica: P2.**

**Causa.** Dos cosas chicas:

1. El byte de "STOP" Teensy→RPi es **255**, el **mismo** que el sync byte `0xFF` que la RPi usa para `SYNC_SPEED` en sentido RPi→Teensy. Son direcciones opuestas del enlace, así que no colisionan físicamente, pero es **confuso** y reusar 255 para dos semánticas dificulta el debug. (La RPi lo maneja bien: `TEENSY_STOP=0xff` en `handle_control_byte`.)
2. El bloque de switch-off (808-822) resetea `esquinas_negro`, `first_rescate`, `final_rescate`, `action=7`, `startUp`, `taskDone` — pero **NO** resetea `green_state` ni `silver_line`. Si se apaga durante rescate con `silver_line=1`/`green_state=7` y se reenciende, esos globales **siguen sucios** hasta que llegue un frame nuevo, y `if(silver_line==1)→action=2` (línea 930) podría **re-disparar rescate** apenas arranca, antes de leer un frame fresco.

- **Riesgo de NO arreglar:** al reiniciar con el switch tras un rescate, posible re-entrada espuria a rescate. Probabilidad media en pruebas repetidas de banco (donde se apaga/prende mucho).
- **Riesgo de arreglar:** **Muy bajo.** Agregar `green_state=0; silver_line=0;` al bloque de apagado.
- **Tiempo:** 5 min.
- **Decisión sugerida:** **SÍ**, trivial y coherente con §2.3 (misma filosofía: limpiar estado de comando al cambiar de fase).

---

## 3. Tabla resumen de decisión

| # | Finding | Sev. | Riesgo NO fix | Riesgo fix | Tiempo | ¿Antes del mundial? |
|---|---|---|---|---|---|---|
| 2.5 | Handshake `0xFA` a medias (RPi sí, Teensy no) | P1 | Robot inerte ante reset; *fail-safe* ilusorio | Bajo (receptor ya existe) | 15 min | **SÍ — primero** |
| 2.3 | `green_state` sticky → re-dispara rescate | P1/P0 | Doble recolección/depósito | Bajo | 10 min | **SÍ** |
| 2.4 | Frames stale encolados en maniobras | P1 | Decisiones con datos viejos | Bajo (`Serial5.clear()` al salir) | 10 min | **SÍ** (con 2.3) |
| 2.2 | Debug-read desincroniza framing (agrava #63) | P1 | Basura en variables de control | Bajo | 15 min | **SÍ** (con #63) |
| 2.1 | `serialEvent5` no es callback; muestreo atado a sensores | P0 | Jitter de latencia, sobrepaso de línea | Medio-alto (toca seguidor) | 10 min + banco | **SÍ, medido** (tras #70) |
| 2.7 | Colisión `angle≥165 → 255` + sin resync | P2 | Frame corrido en curvas extremas | Bajo (clamp/doc) | 20-30 min | Tal vez / documentar contrato |
| 2.9 | Kill-switch no limpia `green_state`/`silver_line` | P2 | Re-entrada espuria a rescate al reencender | Muy bajo | 5 min | **SÍ** (trivial) |
| 2.6 | `green_state` multiplexa 3 espacios sin discriminador | P2 | Amplifica desincronizaciones | Alto (protocolo v2) | — | **NO** (post-mundial) |
| 2.8 | Variables de control no `volatile` | P2 | Ninguno hoy | Bajo pero inútil ahora | — | **NO** (solo nota) |

**Dependencias previas que siguen abiertas y son prerequisito:** **#70** (drain con `while`) y **#63** (parsear en maniobras). Sin #70, los findings 2.1/2.4 no mejoran del todo.

---

## 4. Oportunidades (no son bugs)

- **O1 — Heartbeat Teensy→STOP (issue #53, doc §6.1):** sigue sin implementar. **Pero ojo:** el diseño del doc (chequear `lastFrameMs` en `loop()`) **no se ejecutaría** mientras el robot está en los `while` internos (§2.1) — el heartbeat hay que evaluarlo **dentro** de `while(rutina=="linea")` y `while(rutina=="rescate")`, no solo en `loop()`. Es una corrección al diseño previo. Valor de seguridad alto, riesgo medio (puede frenar el robot por falsos timeouts si el muestreo serial es esporádico). **Recomiendo diseñarlo junto con 2.1**, no antes.
- **O2 — Telemetría de framing:** un contador de `frames_ok` / `frames_desync` (incrementado cuando el parser ve un payload donde esperaba sync) daría visibilidad de §2.2/2.7 en banco. Barato (2-3 contadores + un `Serial.print` cada N). Ayuda a **decidir con datos** si los findings P2 valen la pena. La RPi ya tiene telemetría TX (`frames_sent`, Main.py 110-114); falta el espejo en Teensy.
- **O3 — Documentar el contrato real de rangos en el parser** (`// payload ∈ [0,251]; 252-255 reservados como sync`). 5 min, evita regresiones futuras (un `green_state=254` rompería todo silenciosamente). Es lo único de §2.6/2.7 que sí conviene tocar ya.

---

## 5. Verificación en banco (lo que habría que medir antes de tocar nada)

Coherente con §8 del doc previo, pero específico a estos findings:

1. **§2.5:** con todo corriendo en `linea`, presionar RESET del Teensy. **Esperado HOY:** RPi sigue en `linea`, robot inerte/errático (confirma el bug). Tras el fix: la RPi imprime `[INFO] Teensy reseteado -> esperando` y vuelve a `esperando`.
2. **§2.3:** forzar `green_state=6`, dejar que ejecute la rutina negra, y **no** mandar frame nuevo durante 7 s. **Esperado HOY:** la rutina se repite. Tras el fix: se ejecuta una sola vez.
3. **§2.4/2.1:** `Serial.print(Serial5.available())` cada 100 ms durante un rescate. HOY crece hacia ~1 KB y se satura. Tras #70 + `Serial5.clear()`: vuelve a ~0 al salir.
4. **§2.7:** loguear cada vez que el parser reciba un valor 252-255 en posición de payload. Contar ocurrencias en 5 min de pista con curvas cerradas.

Registrar todo en [`testing/TEST_LOG.md`](../../../../testing/TEST_LOG.md) (regla de oro #3).

---

## 6. Cierre y recomendación al coach

El módulo serial del Teensy **funciona en la mesa pero es frágil bajo estrés de competencia** (resets por brownout, maniobras largas, ruido de motores). Las auditorías previas (#63/#70/#72) apuntaron bien pero **#72 quedó implementado a medias** (solo RPi) y **#63/#70 no vieron** que el problema de fondo es que `serialEvent5()` **no es una callback efectiva** y que el parser **nunca limpia el comando consumido**.

**Si tuviera que tocar solo 4 cosas antes de Incheon, en este orden:**

1. **§2.5** — cerrar el emisor `0xFA` en el Teensy (15 min, riesgo bajo, activa un *fail-safe* hoy ilusorio).
2. **#70 + #63 + §2.2** — drain con `while` y parseo en maniobras (los tres juntos, ~45 min).
3. **§2.3 + §2.4 + §2.9** — limpiar `green_state`/`silver_line` y `Serial5.clear()` al salir de rescate/al apagar (~25 min, evita doble-recolección).
4. **§2.1** — la llamada única a `serialEvent5()` al tope del `while(linea)`, **medida en banco** (riesgo sobre el seguidor; si degrada, revertir).

Todo lo demás (2.6, 2.7, 2.8 y protocolo v2) es **deuda documentada para después del mundial**. No tocar lo que el seguidor ya tiene tuneado salvo que el banco demuestre mejora (regla de oro #4).

---

*Auditoría asistida por Claude Code (Opus 4.8, 1M) — dominio SERIAL del Teensy (C++). Solo lectura. Complementa, no reemplaza, los issues #53/#63/#70/#72 ni [`analisis-integral-comunicacion-2026-05-10.md`](../../../../docs/es/analisis-integral-comunicacion-2026-05-10.md). 2026-05-18.*
