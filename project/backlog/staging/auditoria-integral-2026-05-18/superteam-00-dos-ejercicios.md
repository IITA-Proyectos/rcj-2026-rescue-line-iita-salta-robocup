# SUPERTEAM CHALLENGE — Dos ejercicios listos para asignar (Auditoría Integral 2026-05-18)

> **Dominio:** SuperTeam Challenge de RoboCup Junior Rescue Line 2026 (Incheon, Corea, 2026-06-30 → 07-06).
> **Pregunta del coach:** qué es el SuperTeam Challenge, cómo se forma, cómo se evalúa, qué cooperación inter-robot se espera, qué canal de comunicación se usa. Y diseñar **DOS** ejercicios/simulaciones concretos y completos para que Enzo los asigne en **dos sesiones distintas**.
> **Modo:** sólo lectura del repo + investigación web/reglamento. No se modificó código ni GitHub.
> **Checkout:** `feature/initialize-testing-log` (== `main` post-PR #101).
> **Convención de findings (memoria del coach):** todo lo accionable se presenta como **TEMA A ANALIZAR** con *riesgo de no hacerlo* + *riesgo de hacerlo* + *tiempo*. No son "tareas obligatorias"; el equipo decide, el coach asigna, el auditor IA presenta el material.

---

## 0. TL;DR para el coach (leer esto primero)

1. **El SuperTeam Challenge existe y es oficial en Rescue Line 2026** (reglamento §6.3). Es **independiente** de la competencia principal, **NO afecta el puntaje individual**, tiene **su propio premio**, y su foco es **la cooperación entre equipos** de distinto idioma nativo. Es decir: para el podio individual del equipo (objetivo #1 del proyecto) el SuperTeam **no suma ni resta**, pero es donde se juega visibilidad, networking y la cultura "RoboCup". Posicionarlo así con los chicos: **bajo riesgo deportivo, alto retorno de aprendizaje y de relaciones**.
2. **El reglamento es deliberadamente vago a propósito:** la **tarea concreta del SuperTeam se anuncia recién EN Incheon** (§6.3.2) y "requiere cambios sustanciales de software y puede requerir ajustes menores de hardware" (§6.3.3). Nadie puede entrenar la tarea exacta de antemano. **Por eso estos dos ejercicios entrenan la *capacidad genérica*** (acordar un protocolo mínimo en minutos, ponerlo a andar entre dos robots desconocidos, degradar con elegancia) **y no una tarea específica** que probablemente no salga.
3. **El reglamento "recomienda fuertemente" traer hardware de comunicación o pensar un mecanismo de comunicación** (§6.3, nota final). El canal está acotado por la regla general §1.3.1: **2.4 GHz y ≤ 100 mW EIRP**. Esto valida exactamente el trabajo del módulo ESP32 / canal inter-robot del issue #84 y del doc de hardware (ver auditoría hermana `comms-02-esp32.md`).
4. **Hoy el robot está en ~0 % de canal inter-robot** (no hay ESP32 montada, no existe `superteam.py`, `Serial8` nunca se inicializa, hay dos arquitecturas incompatibles sin decidir — todo documentado en `comms-02-esp32.md`). **Estos dos ejercicios NO presuponen que eso esté resuelto:** el Ejercicio 1 se hace **sin radio** (cooperación por percepción/comportamiento, "0 % comms") y el Ejercicio 2 introduce el canal **del lado más barato y reversible** (Ruta B del issue #84: Bluetooth nativo de la RPi, sin abrir el robot). Así el equipo gana capacidad SuperTeam **aunque la decisión ESP32 vs BT-RPi siga abierta**.
5. **Las dos sesiones son secuenciales y acumulativas:** Ejercicio 1 (sin comms, "lenguaje común y coreografía") → Ejercicio 2 (con comms mínima real, "handshake y handoff"). Cada uno cabe en una sesión de taller. Ambos terminan con una entrada en `testing/TEST_LOG.md` (Regla de oro #3 del repo).

---

## 1. ¿Qué es el SuperTeam Challenge? (evidencia del reglamento)

### 1.1 Texto oficial — Reglamento RCJ Rescue Line 2026, §6.3 (cita textual, traducida)

Fuente: *RoboCupJunior Rescue Line Rules 2026* (final, last updated 2026-03-29), página 27, sección **6.3. SuperTeam Challenge**. Texto original en inglés:

> *"The SuperTeam Challenge takes place independantly of the main competition and won't influence the team's individual score. It has its own award and is focussed on the cooperation between the teams.*
> *1. Each SuperTeam will consist of at least two teams. Teams coming from regions that share a native language will not be part of the same SuperTeam.*
> *2. The rules of the SuperTeam Challenge will be announced at the competition and require the teams of each SuperTeam to work together.*
> *3. The SuperTeam Challenge will require substantial software changes and may require minor hardware adjustments.*
> *It is highly recommended that teams bring some kind of communication hardware or think about a communication mechanism for this challenge."*

**Traducción / lectura para el equipo:**

| Aspecto | Qué dice el reglamento 2026 | Implicancia para IITA Salta |
|---|---|---|
| **Peso en el puntaje** | Independiente; **no influye** en el score individual; **premio propio**. | No arriesga el objetivo de podio. Es "upside" puro. |
| **Foco** | **Cooperación entre equipos.** | Se evalúa que dos equipos **trabajen juntos**, no que un robot sea el más rápido. |
| **Formación** | Cada SuperTeam = **al menos dos equipos**. Equipos que comparten **idioma nativo NO** van juntos. | IITA Salta (español) será emparejado con un equipo **no hispanohablante** (japonés, coreano, alemán, etc.). **El idioma de trabajo será inglés / señas / diagramas.** Esto es central para el Ejercicio 1. |
| **Cuándo se conocen las reglas** | **En la competencia** (§6.3.2). | No se puede entrenar la tarea exacta. Se entrena la **capacidad de acordar rápido**. |
| **Esfuerzo** | **Cambios sustanciales de software**; **ajustes menores de hardware** posibles (§6.3.3). | Hay que llegar con un robot **fácil de reprogramar** y con un canal de comms **ya probado**, no improvisado el día D. |
| **Comunicación** | **"Altamente recomendado"** traer hardware de comunicación **o** pensar un mecanismo de comunicación. | No es obligatorio, pero los equipos que llegan con canal andando **dominan** el challenge. Conecta directo con issue #84 / ESP32. |

### 1.2 Canal de comunicación permitido — Reglamento §1.3.1 (cita textual, traducida)

Fuente: mismo PDF, página 8, sección **1.3.1. Robot Communication**:

> *"Permitted Communication: Communication between robots during gameplay is allowed as long as it uses the 2.4GHz spectrum and its power output does not exceed 100 mW EIRP (Effective Isotropic Radiated Power) under any circumstances.*
> *Responsibility: Teams are responsible for managing their robot communication. Spectrum availability is not guaranteed.*
> *Component Communication: Communication between components of the same robot is permitted.*
> *League Adaptability: Each league may modify the robot communication rules..."*

**Lo que esto fija (duro):**
- El canal inter-robot **debe ser 2.4 GHz** y **≤ 100 mW EIRP**. → **BLE, ESP-NOW y WiFi 2.4 GHz están todos dentro de la regla** (todos son 2.4 GHz; con la potencia de un módulo estándar, < 100 mW EIRP). El Bluetooth class 2 nativo de la Raspberry Pi 4B (≈ 2.5 mW / 4 dBm) **cumple con muchísimo margen**.
- **"Spectrum availability is not guaranteed":** la sala de Incheon va a estar **saturada** de 2.4 GHz (decenas de equipos, WiFi del venue, cámaras, público). **El diseño tiene que tolerar interferencia y pérdida de paquetes.** Esto no es opcional: es la condición real de operación. → Lo entrena el Ejercicio 2 (degradación).
- **"Communication between components of the same robot is permitted":** el enlace Teensy↔RPi (UART) y un eventual Teensy↔ESP32 (Serial8) son legales sin restricción de banda (son cable interno). La restricción 2.4 GHz aplica sólo al **salto por aire** entre los dos robots.

### 1.3 Cómo se forma y cómo corre (síntesis reglamento + formato histórico)

El reglamento 2026 de **Line** deja la mecánica concreta para el venue. Para diseñar ejercicios realistas conviene apoyarse en cómo viene siendo el SuperTeam en RoboCup Junior Rescue (formato histórico estable, p. ej. Rescue Simulation y ediciones previas):

- **Composición:** ≥ 2 equipos de **distinto idioma nativo**, fusionados en un "SuperTeam" por los organizers en el venue. Generalmente **2 equipos → 2 robots** (en la nomenclatura clásica, `ROBOT_RED` y `ROBOT_BLUE`, uno por equipo).
- **Ventana de colaboración:** se da un **tiempo corto en el venue** para que el SuperTeam se conozca, acuerde estrategia y **reprograme** sus robots para la tarea anunciada. Acá es donde "substantial software changes" muerde: hay que cambiar comportamiento **rápido y bajo presión**, con un compañero que no habla tu idioma.
- **Corrida:** típicamente los **dos robots comparten el mismo campo / la misma misión** (no corren aislados); el SuperTeam suma puntos **en conjunto**. El tiempo de juego suele ser del orden de los **8 minutos** (igual que la corrida individual de Line). La tarea premia que los robots **se repartan trabajo o se coordinen** (ej.: cada robot cubre una mitad del recorrido; o uno hace línea y otro rescate; o se pasan información de víctimas / de zona de evacuación).
- **Evaluación:** **rúbrica propia** centrada en cooperación + resultado de la tarea conjunta, con **premio separado** del ranking individual. No se normaliza contra el field score individual (es un evento aparte, §6.3).

> ⚠️ **Honestidad metodológica:** la *tarea exacta* y la *rúbrica exacta* del SuperTeam Line 2026 **NO están publicadas** (por diseño, salen en Incheon). Todo lo de "cómo corre" del párrafo anterior es **el patrón histórico del SuperTeam de RoboCup Junior Rescue**, no una cita del reglamento 2026. Los dos ejercicios están construidos para entrenar **la capacidad transferible** a *cualquier* tarea que salga, no una tarea concreta. Si los organizers publican la mecánica antes del torneo (a veces sale un anexo), **reajustar los roles de los ejercicios** a esa mecánica.

### 1.4 Cooperación inter-robot esperada (qué tipo de "trabajar juntos")

De §6.3 ("focussed on the cooperation between the teams") + el patrón histórico, las formas de cooperación que típicamente se piden son alguna combinación de:

1. **Reparto de territorio:** cada robot cubre una zona/mitad del campo y no se pisan. (No requiere radio si hay percepción mutua o coreografía temporal; sí la facilita.)
2. **Relevo / handoff:** el robot A hace una parte (ej. seguir línea hasta un punto) y "le pasa la posta" al robot B (ej. el rescate). Requiere **una señal de "ya terminé / tu turno"**.
3. **Compartir información:** A detecta algo (una víctima, el color de una víctima, la zona de evacuación) y **se lo comunica** a B para que B no tenga que re-detectarlo. Requiere **mensajes con contenido**, no sólo una señal.
4. **Sincronización temporal:** ambos arrancan/paran/esperan coordinados (ej. "no entres a la zona de evacuación hasta que yo salga"). Requiere **handshake / barrera**.

Los Ejercicios 1 y 2 cubren progresivamente estas cuatro: **Ej. 1** entrena (1) y (2) **sin radio** (por percepción y coreografía); **Ej. 2** entrena (2), (3) y (4) **con radio mínima** (señal + contenido + barrera).

---

## 2. Estado del robot relevante para estos ejercicios (qué hay y qué falta)

Resumen de la auditoría hermana `comms-02-esp32.md` (no se repite, se cita) y de lo verificado en el checkout:

| Pieza | Estado real hoy | Consecuencia para los ejercicios |
|---|---|---|
| **Canal inter-robot (cualquiera)** | **No existe** funcional. | El Ejercicio 1 se diseña **sin** canal. El Ejercicio 2 **lo crea** por la ruta más barata. |
| **ESP32 Super Mini (Ruta A, doc HW de Benjamin)** | Sólo propuesta escrita. No montada, sin firmware, sin footprint PCB, sin BOM. Pines 34/35 liberados (`Serial8`) pero **`Serial8.begin()` nunca se llama**. | El Ejercicio 2 **no depende** de la ESP32 (no exige abrir el robot a < 5 semanas de Incheon). La ESP32 queda como **ruta de migración** posterior, no como bloqueante. |
| **`superteam.py` / BT nativo RPi (Ruta B, issue #84)** | Archivo **inexistente**. Stub conceptual con `pass`/TODO. `bleak`/`pybluez` sin pinear en `requirements.txt`. | El Ejercicio 2 **es la primera implementación real** de este archivo. ~4 h de stub ping-pong según el propio #84. |
| **Decisión de arquitectura (ESP32 vs BT-RPi)** | **Pendiente** (dos planes incompatibles, asignados a @enzzo19 + @benjaminvillagran en #84). | El Ejercicio 2 **no obliga a decidir**: usa BT-RPi por ser reversible y aislado, y deja la migración a ESP32 documentada como opción. **Hacer el Ejercicio 2 da datos para decidir** mejor. |
| **Enlace Teensy↔RPi (UART 115200)** | Funciona, pero **frágil**: sin heartbeat (#53), overflow de buffer en bloqueos (#63/#70/F-3 de `comms-01`), handshake de boot medio-implementado (F-1). | **Regla dura para el Ejercicio 2:** el canal SuperTeam **NO debe tocar el hot-path serial Teensy↔RPi.** Por eso va en la RPi como **proceso/flag aislado**, sin sumar tráfico al UART ya saturado. |
| **Máquina de estados de alto nivel (RPi)** | `Main.py` maneja `estado ∈ {esperando, linea, rescate, depositar}` con control bytes `0xFA/0xF9/0xF8/0xFF`. | El Ejercicio 2 **reutiliza este vocabulario**: el canal SuperTeam puede anunciar el `estado` propio y reaccionar al `estado` del par, **sin inventar conceptos nuevos**. |

**Conclusión operativa:** los ejercicios están ordenados para que el equipo **gane capacidad SuperTeam sin bloquearse en la decisión ESP32-vs-BT y sin arriesgar el robot validado**. El Ejercicio 2 produce, además, el primer entregable concreto del issue #84.

---

## 3. Mapa de las dos sesiones (para que Enzo las ubique)

| | **EJERCICIO 1** | **EJERCICIO 2** |
|---|---|---|
| **Título** | "Lenguaje común y coreografía sin radio" | "Handshake, handoff y degradación con canal real" |
| **Sesión** | Sesión A (primera) | Sesión B (segunda, después de la A) |
| **Comms** | **Cero radio.** Cooperación por percepción + tiempo + señales físicas (LED/buzzer/cartel). | **Radio mínima real:** Bluetooth nativo RPi (Ruta B / issue #84). Sin abrir el robot. |
| **Aprendizaje central** | Acordar un protocolo de cooperación **en minutos, sin idioma común**, y ejecutarlo. Simula la "ventana de colaboración" de Incheon. | Diseñar, implementar y **estresar** un canal inter-robot mínimo: handshake, mensaje con contenido, barrera, y **degradación** ante pérdida de señal. |
| **Hardware nuevo** | Ninguno. | Ninguno físico en el robot (usa BT que ya tiene la Pi). Opcional: 2ª Pi o un celular como "par". |
| **Relación con #84 / ESP32** | Define **qué** se comunica (el protocolo de aplicación, hoy inexistente en cualquier forma). | Crea `software/raspberry/final_rpi/superteam.py` (hoy no existe) e implementa el stub real de #84. Deja la migración a ESP32 (Ruta A) documentada. |
| **Entregable tangible** | Una **"tarjeta de protocolo SuperTeam"** (1 hoja) + video de la coreografía + entrada en `TEST_LOG.md`. | `superteam.py` funcional (ping-pong + 1 mensaje con contenido + barrera) + log de prueba de degradación + entrada en `TEST_LOG.md`. |
| **Duración** | ~2 h 30 (una tarde de taller). | ~3 h (una tarde de taller). |

---

---

# EJERCICIO 1 — "Lenguaje común y coreografía sin radio"

> **Simula la ventana de colaboración de Incheon: dos equipos que NO hablan el mismo idioma deben acordar y ejecutar una tarea cooperativa en minutos, con cero comunicación por radio. Entrena lo que el reglamento §6.3 evalúa de verdad: cooperación.**

## 1.1 Objetivo de aprendizaje

Al terminar, los chicos deben ser capaces de:
1. **Diseñar un protocolo de cooperación mínimo bajo presión de tiempo** (15 min de "ventana de colaboración" cronometrada), acordándolo **sin idioma común** (sólo dibujos, gestos y demostración) — exactamente la restricción de §6.3.1 (idiomas nativos distintos).
2. **Repartir una misión Rescue Line entre dos robots** sin que se estorben, usando únicamente **percepción mutua + sincronización temporal + señales físicas** (LED rojo, buzzer, un cartel de cartón) — **sin radio**. Esto fuerza a entender qué cooperación es posible **aunque el canal de comms falle** (degradación máxima = sin canal).
3. **Definir el "qué se comunica"** (el protocolo de aplicación SuperTeam), que hoy **no existe en ninguna forma** en el repo (hallazgo central de `comms-02-esp32.md` §5). Este ejercicio produce ese diseño en papel, que el Ejercicio 2 después implementa en radio.
4. Vivir la diferencia entre **"nuestro robot anda solo"** y **"nuestro robot coopera"**: practicar empatía técnica con un par desconocido.

## 1.2 Materiales y setup

- **Dos robots Rescue Line.** Idealmente el robot del equipo + un segundo robot. Si el equipo tiene **un solo** robot funcional:
  - **Opción A (preferida):** pedir prestado/usar el robot del equipo Roboliga/next-gen, o un segundo armado de banco, aunque sea más simple. No necesita ser idéntico.
  - **Opción B (fallback):** **un robot real + un "robot humano"**: un alumno hace de segundo robot moviendo una caja con un LED y un cartel, siguiendo *exactamente* las mismas reglas que tendría el robot (sin hablar, sólo reaccionando a lo que ve). Suena tonto pero entrena perfecto el protocolo de cooperación y la coreografía.
- **Pista Rescue Line** armada con baldosas: al menos **un recorrido con una intersección/checkpoint y una zona de evacuación** (o un cuadrado marcado que la simule). No hace falta la pista completa del mundial; alcanza con un tramo que tenga **un punto de "handoff"** claro.
- **Señales físicas disponibles en el robot** (ya existen en el firmware): **LED_ROJO** y **BUZZER** (ojo: pines remapeados a 30/31 — ver `comms-02-esp32.md` §3; **verificar en banco que encienden** antes de la sesión, porque eso está sin confirmar). Más un **cartel de cartón** que un alumno levanta como "señal de estado" (rojo = ocupado, verde = libre).
- **Cronómetro** (el del celular) para la ventana de colaboración y para la corrida.
- **Papel y fibrón** para la "tarjeta de protocolo" (entregable). **Prohibido escribir palabras en español/inglés**: sólo **dibujos, flechas, íconos**. Esto fuerza el modo "sin idioma común".
- **Cámara/celular** para grabar la corrida (evidencia + revisión).
- **Banco de pruebas de Benjamin** para el chequeo previo de LED/buzzer.

**Setup de roles humanos:** dividir a los 3 alumnos en **dos "equipos" artificiales** para simular el cruce de idiomas:
- **"Equipo Rojo" (1 alumno):** opera el robot del equipo. Rol fuerte: el que sabe cómo anda su robot.
- **"Equipo Azul" (2 alumnos):** opera el segundo robot (o el robot humano). **Regla del juego:** Rojo y Azul **no pueden hablarse en español** durante la ventana de colaboración ni durante la corrida. Sólo dibujos/gestos. (Para que sea realista, Enzo puede pedir que Azul "hable" sólo en inglés básico o sólo con señas.)

> Nota de encuadre (memoria del coach, frame de ingeniería senior): presentar esto **no** como "jueguito" sino como *ensayo de la situación real de Incheon*. El valor está en que descubran por sí mismos qué tan difícil es coordinar sin idioma, y qué información es **imprescindible** comunicar.

## 1.3 Roles de cada robot durante la tarea

La tarea cooperativa de este ejercicio es un **handoff con reparto de zona** (cubre las formas de cooperación (1) y (2) de §1.4), elegida porque **no requiere radio**:

- **ROBOT_ROJO — "el de la línea":**
  - Sigue la línea desde la salida hasta el **checkpoint de handoff** (una intersección marcada, o un parche plateado/silver que ya detecta el firmware vía `silver_line`).
  - Al llegar, **se detiene completamente**, enciende **LED_ROJO** y hace **un beep largo** con el BUZZER: esa es su señal física de *"llegué, terminé mi parte, te toca"*.
  - **No avanza** a la zona de evacuación. Su trabajo termina en el checkpoint.
- **ROBOT_AZUL — "el del rescate":**
  - Arranca **detenido** más allá del checkpoint (o esperando fuera de la zona).
  - **Detecta la señal de Rojo** por percepción: ve el LED encendido / "oye" el beep (en la Opción B humana, el alumno-robot simplemente ve el cartel rojo→verde). Recién entonces **avanza** a hacer el "rescate" (recoger una pelota / llegar a la zona de evacuación).
  - **Restricción de no-colisión:** Azul **no puede entrar** al checkpoint mientras Rojo siga ahí con el LED encendido (simula "no se pisen"). Si Rojo no se fue, Azul espera.

**Variante de dificultad creciente (si sobra tiempo):** invertir roles a mitad de sesión, o agregar una **segunda señal** (ej. Rojo comunica *con cuántos beeps* el "color de la víctima" que vio: 1 beep = víctima viva, 2 beeps = muerta), forzando un protocolo con **contenido** y no sólo una señal binaria. Esto es el puente conceptual al Ejercicio 2.

## 1.4 Pasos detallados (con tiempos)

**Bloque 0 — Preparación previa a la sesión (Benjamin, antes / 20 min):**
- Verificar en banco que **LED_ROJO y BUZZER encienden** en los pines actuales (30/31). Si no, el ejercicio usa la Opción B (cartel humano) y se anota como hallazgo. (Esto está sin confirmar — `comms-02-esp32.md` §3.)
- Tener la pista armada con el checkpoint de handoff y la zona de evacuación marcados.

**Bloque 1 — Encuadre (Enzo, 10 min):**
- Explicar qué es el SuperTeam Challenge (usar §1 de este doc): no afecta el puntaje, premia cooperación, el par es de otro idioma, la tarea se sabe recién en Incheon.
- Anunciar la **regla de oro de la sesión**: *desde ahora, Rojo y Azul no se hablan en español*.

**Bloque 2 — Ventana de colaboración cronometrada (15 min, en silencio idiomático):**
- Rojo y Azul tienen **15 minutos** (cronometrados, visible) para **acordar el protocolo de cooperación usando SÓLO dibujos y gestos**, y para **dibujar la "tarjeta de protocolo"** (la hoja con íconos).
- Deben dejar acordado, **sin palabras**: quién hace qué, cuál es la señal de handoff, qué hace cada uno si el otro no responde.
- Enzo cronometra y **no ayuda** (los jueces en Incheon tampoco). Si a los 15 min no terminaron, **igual se corre** con lo que tengan (así se siente la presión real).

**Bloque 3 — Primera corrida (8 min de "juego", como en Incheon):**
- Se ejecuta la coreografía acordada. Enzo graba.
- Criterio: ¿hubo handoff limpio? ¿se pisaron? ¿Azul arrancó por la señal correcta o adivinó?

**Bloque 4 — Retro sin idioma → con idioma (20 min):**
- Primero Rojo y Azul intentan corregir **sin hablar** (5 min): ajustan la tarjeta de protocolo.
- Segunda corrida (8 min).
- Recién al final, **se levanta la restricción de idioma** y todo el equipo discute en español: ¿qué información fue imprescindible comunicar? ¿qué se resolvió por percepción y qué hubiera necesitado radio? **Esa lista de "lo que hubiéramos querido decir por radio" es el insumo directo del Ejercicio 2.**

**Bloque 5 — Cierre y entregable (15 min):**
- Pasar la "tarjeta de protocolo" a limpio (puede seguir siendo en íconos).
- Escribir la entrada en `testing/TEST_LOG.md`: fecha, qué se probó, resultado, qué falló (ej. "el beep no se escuchó con ruido de motores → en Incheon la señal acústica no sirve, hay que radio o LED").

## 1.5 Qué preparar del robot / comms antes (relación con ESP32 / #84)

- **No requiere canal de radio** (ese es el punto: entrena el "peor caso degradado"). Pero **sí requiere** que las **señales físicas de salida del robot funcionen**: LED_ROJO y BUZZER en pines 30/31. **Verificar en banco** (enlaza con el hallazgo de `comms-02-esp32.md` §3: el remapeo de pines está aplicado en firmware pero **no confirmado en hardware**). **Si LED/buzzer no andan, este ejercicio lo detecta** — bonus de diagnóstico.
- **Define el protocolo de aplicación SuperTeam** que hoy **no existe** (el gran agujero señalado en `comms-02-esp32.md` §5: "Diseño de protocolo de aplicación SuperTeam — hoy no existe en ningún lado, ni siquiera en prosa"). La "tarjeta de protocolo" de este ejercicio **es** ese diseño en su forma más cruda. **Sin este paso, el canal de radio del Ejercicio 2 no tendría qué transportar.**
- **Insumo para #84:** la lista del Bloque 4 ("lo que hubiéramos querido decir por radio") es la **especificación de mensajes** que el Ejercicio 2 implementa. Llevarla al issue #84 como comentario de diseño (cuando el equipo decida; el auditor no toca GitHub).

## 1.6 Criterio de éxito medible

Marcar **logrado** si se cumplen **todos**:
1. **Handoff sin colisión en ≥ 2 de 2 corridas finales:** Azul arranca su parte **sólo después** de la señal de Rojo, y **nunca** invade el checkpoint con Rojo presente. (Métrica binaria por corrida; objetivo 2/2.)
2. **Protocolo acordado sin idioma:** la tarjeta de protocolo está hecha **sólo con íconos/dibujos** (cero palabras) y **ambos sub-equipos la interpretan igual** cuando Enzo les pregunta por separado (test de consistencia: señalan lo mismo).
3. **Tiempo de acuerdo ≤ 15 min:** el protocolo quedó cerrado dentro de la ventana cronometrada (o se documenta cuánto faltó, como dato de mejora).
4. **Lista de "qué necesitábamos por radio" producida:** al menos **3 mensajes** identificados que NO se pudieron transmitir por percepción (ej. "el color de la víctima", "cuántas pelotas me quedan", "abortá, hay problema"). Esta lista alimenta el Ejercicio 2.

> Métrica de coach (opcional, para ver progreso entre sesiones): cronometrar el **tiempo desde la señal de Rojo hasta que Azul empieza a moverse**. En la primera corrida suele ser errático (Azul "adivina"); al final debería ser **reactivo y consistente** (< 2 s tras la señal). Bajar esa latencia es el mismo skill que después se mide en el handshake del Ejercicio 2.

## 1.7 Duración total

**~2 h 30 min:** Bloque 0 (previo, 20) + Bloque 1 (10) + Bloque 2 (15) + Bloque 3 (~12 con setup) + Bloque 4 (20) + Bloque 5 (15) + colchón/transiciones (~40). Cabe en una tarde de taller.

---

---

# EJERCICIO 2 — "Handshake, handoff y degradación con canal real"

> **Construye, por primera vez, un canal inter-robot funcional mínimo (Ruta B del issue #84: Bluetooth nativo de la RPi, sin abrir el robot) y lo estresa con la condición real de Incheon: espectro saturado y pérdida de paquetes. Entrena las formas de cooperación (2) handoff, (3) compartir contenido y (4) barrera/sincronización del §1.4.**

## 2.1 Objetivo de aprendizaje

Al terminar, los chicos deben ser capaces de:
1. **Implementar un canal inter-robot mínimo y aislado** que **NO toque el hot-path serial Teensy↔RPi** (regla dura: el UART ya está frágil — #53/#63 / `comms-01`). Concretamente: crear `software/raspberry/final_rpi/superteam.py` (hoy **inexistente**) y poner a andar un **ping-pong** entre dos Pi (o Pi + celular).
2. **Diseñar un mini-protocolo de aplicación con framing y semántica explícitos:** un **handshake** ("hola, soy ROJO, ¿estás?"), un **mensaje con contenido** (ej. "víctima viva detectada" / "mi estado = rescate"), y una **barrera** ("no entres a la zona hasta que yo salga"). Esto materializa en radio la "tarjeta de protocolo" del Ejercicio 1.
3. **Probar la degradación:** apagar la radio a mitad de corrida y verificar que **ambos robots siguen su pista individual sin colgarse** (enlaza con los watchdogs/heartbeat de #27/#53). "Spectrum availability is not guaranteed" (§1.3.1) → el robot **debe** tolerar pérdida total de canal.
4. Entender, con datos reales, **por qué la Ruta B (BT-RPi) es de bajo riesgo** y qué haría falta para migrar a la **Ruta A (ESP32, doc HW)** si en el futuro se quisiera. Producir el primer entregable concreto del issue #84.

## 2.2 Materiales y setup

- **Dos Raspberry Pi 4B** (idealmente las de los dos robots). Si hay una sola Pi:
  - **Fallback A:** la Pi del robot + **un celular Android** con una app BLE/Bluetooth genérica (ej. "Serial Bluetooth Terminal" o "nRF Connect") haciendo de "robot par". Permite probar handshake y mensajes con contenido reales sin segunda Pi.
  - **Fallback B:** la Pi del robot + **la laptop** con `bleak`/`pybluez` corriendo un script espejo de `superteam.py`. Misma cobertura.
- **Bluetooth de la Pi 4B activado** (viene de fábrica, class 2 ≈ 2.5 mW → cumple §1.3.1 con enorme margen). Confirmar que `bluetoothctl` lista el adaptador.
- **Librería de comms en la RPi:** elegir y **pinear** en `requirements.txt` (hoy sin pinning — issue #68): **`bleak`** (BLE, asyncio — recomendado por #84) **o** `pybluez` (RFCOMM clásico, más simple para un ping-pong de texto). Para este ejercicio, **RFCOMM/`pybluez` es más rápido de poner a andar** (socket tipo serie); `bleak` es más cercano a lo que haría una ESP32. Enzo elige según con qué se sienta el equipo.
- **Los dos robots con su pista** del Ejercicio 1 (mismo checkpoint de handoff y zona de evacuación). Se reutiliza la coreografía, ahora **comandada por radio** en vez de por LED.
- **Cámara/celular** para grabar.
- **Cronómetro.**
- **NO se requiere** montar la ESP32, ni soldar, ni tocar el firmware del Teensy, ni `Serial8`. **El robot no se abre.** (Ese es justamente el bajo riesgo de la Ruta B.)

**Setup de software (clave): aislamiento total del hot-path.**
- `superteam.py` corre como **módulo/proceso separado** que NO comparte el `serial.Serial('/dev/serial0')` de `Main.py`. La comunicación SuperTeam y la comunicación con el Teensy son **canales físicos distintos** (BT vs UART) y deben permanecer **desacoplados en el código**.
- Activación por **flag de entorno** (ej. `SUPERTEAM_ROLE=rojo` / `=azul` / ausente). **Sin el flag, `Main.py` se comporta idéntico a hoy** (test explícito obligatorio — ver criterio de éxito). Esto respeta la Regla de oro #4 del repo (no romper lo validado).

## 2.3 Roles de cada robot durante la tarea

Se reutiliza el **handoff con reparto de zona** del Ejercicio 1, pero ahora cada "señal física" se reemplaza por un **mensaje por radio con contenido**, y se agrega una **barrera** y un **mensaje de información compartida**:

- **ROBOT_ROJO (rol "líder de línea + emisor"):**
  1. Al arrancar, hace **handshake**: emite `HELLO|ROJO` y espera `HELLO|AZUL` (con timeout). Si no hay respuesta en N segundos → marca "sin par" y **corre su pista individual igual** (degradación).
  2. Sigue la línea hasta el checkpoint.
  3. Al detectar el checkpoint, **comparte contenido**: emite `VICTIMA|VIVA` (o `VICTIMA|MUERTA`) — el dato que en el Ejercicio 1 no se podía transmitir por beeps de forma confiable.
  4. Emite `HANDOFF|TU_TURNO` y entra en barrera: **no libera** el checkpoint hasta recibir `ACK|AZUL`.
  5. Tras el `ACK`, se retira y emite `LIBRE|CHECKPOINT`.
- **ROBOT_AZUL (rol "rescate + receptor"):**
  1. Responde el handshake (`HELLO|AZUL`).
  2. Espera en barrera: **no avanza** hasta recibir `HANDOFF|TU_TURNO`.
  3. Al recibir `VICTIMA|VIVA/MUERTA`, **ajusta su comportamiento** (ej. prepara la pinza distinto, o elige a qué triángulo de evacuación ir) — demuestra que el contenido **cambia la acción**, no es decorativo.
  4. Envía `ACK|AZUL`, espera `LIBRE|CHECKPOINT`, y recién entonces avanza a hacer el rescate.

**Mini-protocolo (framing explícito, lo que el Ejercicio 1 no tenía):**
- Formato de mensaje sugerido (texto, legible para debug): `TIPO|ARG\n` (ej. `HELLO|ROJO\n`, `VICTIMA|VIVA\n`, `HANDOFF|TU_TURNO\n`, `ACK|AZUL\n`).
- **Tipos mínimos:** `HELLO`, `VICTIMA`, `HANDOFF`, `ACK`, `LIBRE`, y un `PING`/`PONG` de fondo (heartbeat del canal, 1/seg) para detectar caída de enlace.
- **Reglas de robustez (entran como diseño, se prueban en el Bloque de degradación):** todo `wait_for_*` tiene **timeout**; si vence, el robot **no se cuelga** sino que sigue su plan individual y registra "par perdido". Nada de `while` infinito esperando al par (mismo error que el firmware ya tiene con lecturas bloqueantes — no repetirlo en `superteam.py`).

> Reutilización del vocabulario existente: el `estado` interno de `Main.py` (`esperando/linea/rescate/depositar`) **puede mapearse** a mensajes `ESTADO|<x>` para que el par sepa en qué anda el robot, sin inventar conceptos. Esto deja el canal listo para *cualquier* tarea que salga en Incheon (no sólo este handoff).

## 2.4 Pasos detallados (con tiempos)

**Bloque 0 — Preparación previa (Lucio + Benjamin, antes / 30 min):**
- Confirmar Bluetooth en ambas Pi (`bluetoothctl list`, emparejar las dos Pi una vez).
- Elegir librería (`pybluez` RFCOMM recomendado para arrancar) y **pinear versión** en una rama de trabajo de `requirements.txt`. (Recordar: no se commitea nada en esta sesión salvo que el equipo decida; el ejercicio se puede hacer en working tree.)
- Tener listo un **esqueleto de `superteam.py`** con la clase `SuperTeamChannel(role, peer)` y los métodos del stub de #84 (`announce_state`, `wait_for_signal`) **vacíos** — los chicos los llenan en la sesión.

**Bloque 1 — Encuadre técnico (Enzo, 15 min):**
- Recordar el reglamento: §6.3 (cooperación, premio propio) y §1.3.1 (**2.4 GHz, ≤ 100 mW EIRP, spectrum NOT guaranteed**). Subrayar que **el canal puede caerse** y el robot **no debe colgarse**.
- Mostrar la "tarjeta de protocolo" del Ejercicio 1 y anunciar: *"hoy esto lo hacemos por radio, con framing de verdad"*.
- Recordar la regla dura: **no tocar el UART del Teensy**; SuperTeam vive aislado en la RPi.

**Bloque 2 — Ping-pong (handshake) — 40 min:**
- Implementar `HELLO/PONG` entre las dos Pi (o Pi + celular). Objetivo mínimo: **una Pi dice `HELLO|ROJO`, la otra responde `HELLO|AZUL`, y ambas lo imprimen.**
- Probar `PING/PONG` 1/seg de fondo y **detección de caída**: apagar el BT de una y ver que la otra detecta "par perdido" por timeout (no se cuelga).
- *Este es exactamente el "stub funcional ping-pong" que el issue #84 estima en ~4 h; acá se hace guiado en ~40 min porque el esqueleto ya está.*

**Bloque 3 — Mensaje con contenido + barrera — 45 min:**
- Agregar `VICTIMA|VIVA/MUERTA`, `HANDOFF|TU_TURNO`, `ACK`, `LIBRE`.
- Probar la **barrera**: Azul **no avanza** hasta `HANDOFF`; Rojo **no libera** hasta `ACK`. Verificar en seco (sin robot, sólo imprimiendo) que la secuencia ocurre en orden.
- Demostrar que `VICTIMA|VIVA` vs `VICTIMA|MUERTA` **cambia** lo que Azul imprime/haría (el contenido es accionable).

**Bloque 4 — Integración en pista — 30 min:**
- Conectar el canal a la coreografía real del Ejercicio 1: Rojo sigue línea → en checkpoint manda `VICTIMA|...` + `HANDOFF` → Azul reacciona. Una o dos corridas grabadas.
- **No** se exige que toda la lógica de visión dispare los mensajes; alcanza con que un disparo manual o un evento simple (detección de silver) emita el mensaje. El foco es el **canal y la coordinación**, no re-escribir la visión.

**Bloque 5 — Prueba de degradación (la más importante) — 20 min:**
- A mitad de una corrida, **apagar la radio** (desconectar BT de una Pi).
- **Criterio:** ambos robots deben **seguir su pista individual sin colgarse** y registrar "par perdido". Si alguno se queda esperando para siempre → **bug encontrado**, se anota y se arregla el timeout. Esto **es** el entrenamiento del peor caso de Incheon.

**Bloque 6 — Cierre y entregable (20 min):**
- Dejar `superteam.py` funcional (handshake + 1 mensaje con contenido + barrera + degradación).
- Entrada en `testing/TEST_LOG.md`: qué se probó, latencia del handshake, comportamiento al cortar la radio.
- **Anotar para la decisión ESP32 vs BT-RPi (#84):** ¿el BT-RPi alcanzó? ¿hubo interferencia en el taller? ¿valdría la pena la ESP32 (Ruta A) o BT-RPi es suficiente? — **datos reales** para que @enzzo19 + @benjaminvillagran decidan el issue #84 con evidencia, no a priori.

## 2.5 Qué preparar del robot / comms antes (relación con ESP32 / #84 / issue de comms)

- **Decisión de arquitectura que este ejercicio asume (y por qué):** usa **Ruta B (Bluetooth nativo RPi, issue #84)**, NO la **Ruta A (ESP32 por `Serial8`, doc HW de Benjamin)**. Razón (de `comms-02-esp32.md` §5): a < 5 semanas de Incheon, la Ruta B es **reversible, aislada y no abre el robot validado**; la Ruta A implica desoldar/montar/escribir firmware en dos lados sobre un robot que ya anda. **Hacer el ejercicio NO cierra la decisión** — la informa con datos.
- **Lo que NO hay que tocar (regla dura):** el firmware del Teensy, `Serial8`, los pines 34/35, y **sobre todo** el hot-path UART Teensy↔RPi. El canal SuperTeam **no debe sumar tráfico ni latencia** al enlace serial ya frágil (#53/#63 / `comms-01` F-2/F-3). Por eso vive en BT, en un proceso/flag aparte.
- **Lo que sí hay que preparar (entregable de #84):**
  - Crear `software/raspberry/final_rpi/superteam.py` (hoy **no existe** — confirmado en `comms-02-esp32.md` §2.2).
  - Implementar de verdad los métodos que el stub de #84 dejó en `pass`/`# TODO: implementar BLE` (`announce_state`, `wait_for_signal`, + los de este ejercicio).
  - Pinear `bleak` **o** `pybluez` en `requirements.txt` (cierra de paso un pedazo de #68).
  - Garantizar el **flag opcional** (`SUPERTEAM_ROLE`) y el **test de que sin el flag el robot corre idéntico**.
- **Insumo que viene del Ejercicio 1:** el mini-protocolo (`HELLO/VICTIMA/HANDOFF/ACK/LIBRE`) **es** la "tarjeta de protocolo" del Ejercicio 1 traducida a framing. Sin el Ejercicio 1, este protocolo se diseñaría a ciegas.
- **Camino de migración a Ruta A (documentar, no hacer):** si en el futuro se decide la ESP32, el **protocolo de aplicación es el mismo** — sólo cambia el transporte (BT-RPi → ESP32 por `Serial8`). Diseñar `superteam.py` con el transporte **detrás de una interfaz** (`enviar(msg)` / `recibir()`), así migrar a ESP32 es cambiar la implementación del transporte, no el protocolo. Esto vuelve el trabajo de hoy **no desechable** pase lo que pase con #84.

## 2.6 Criterio de éxito medible

Marcar **logrado** si se cumplen **todos**:
1. **Handshake confiable:** en **≥ 8 de 10** intentos, Rojo y Azul completan `HELLO`↔`HELLO` en **< 3 s**. (Métrica: 8/10. Esto es la versión radio del "objetivo auto-recuperación 8/10" del proyecto, aplicada al canal.)
2. **Mensaje con contenido accionable:** Azul **cambia de comportamiento** observablemente según reciba `VICTIMA|VIVA` vs `VICTIMA|MUERTA` (no sólo lo imprime: dispara una acción distinta, aunque sea un LED o un mensaje de "iría al triángulo X").
3. **Barrera correcta:** en 2 de 2 corridas, Azul **nunca** avanza antes de `HANDOFF`, y Rojo **nunca** libera antes de `ACK`. (Orden estricto verificable en el log de mensajes.)
4. **Degradación sin cuelgue (criterio P0):** al cortar la radio a mitad de corrida, **ambos** robots siguen su pista individual y **ninguno se queda colgado** esperando al par. (Binario; si alguno se cuelga, el ejercicio cumplió su función de *encontrar* el bug, pero no se marca "logrado" hasta arreglar el timeout.)
5. **No-regresión del robot solo:** con `SUPERTEAM_ROLE` **ausente**, `Main.py` corre **idéntico** a antes del ejercicio (una corrida individual normal, sin diferencias). Test explícito.

> Métrica de coach (puente con el Ejercicio 1): comparar el **tiempo señal→reacción** del handoff. En el Ej. 1 (LED/percepción) era errático y lento; con radio debería ser **más rápido y consistente**. Que los chicos vean ese delta **justifica el canal** y conecta las dos sesiones.

## 2.7 Duración total

**~3 h:** Bloque 0 (previo, 30) + Bloque 1 (15) + Bloque 2 (40) + Bloque 3 (45) + Bloque 4 (30) + Bloque 5 (20) + Bloque 6 (20). Es la sesión más densa; si el grupo es nuevo en `bleak`/`pybluez`, partir el Bloque 2 en dos y correr el resto en una tercera sesión.

---

## 4. Cómo encadenar las dos sesiones (nota para Enzo)

- **Orden obligatorio:** Ejercicio 1 **antes** que el 2. El 1 produce el **protocolo de aplicación** (qué se comunica), sin el cual el 2 no tiene contenido que transportar. Es el mismo agujero que `comms-02-esp32.md` §5 marca como bloqueante ("no existe en ningún lado, ni siquiera en prosa").
- **Hilo conductor entre sesiones:** la **"tarjeta de protocolo"** del Ej. 1 → se convierte en el **mini-protocolo con framing** del Ej. 2. Y la métrica **señal→reacción** se mide en ambas para mostrar el progreso.
- **Qué queda para después de las dos sesiones (no es parte de estos ejercicios, se enumera para que el coach lo tenga en el radar):**
  - **Decisión #84** (ESP32 vs BT-RPi) — ahora **con datos** del Ejercicio 2.
  - Si se elige Ruta A: el trabajo de hardware/firmware de `comms-02-esp32.md` §5 (desarmar, soldar, `Serial8.begin`, firmware ESP32). **Riesgo alto pre-mundial**; los ejercicios permiten **no** depender de eso para tener capacidad SuperTeam.
  - **Acordar formato mínimo común con el equipo-par en Incheon** antes de la corrida (el reglamento da una ventana de colaboración; llegar con un protocolo flexible y un canal probado es la ventaja).
  - **Plan de degradación** ya entrenado (Ej. 2 Bloque 5) — enlaza con watchdogs/heartbeat #27/#53.

---

## 5. Cruce con auditorías previas (no se repiten, se citan)

- **`comms-02-esp32.md` (auditoría hermana, ESP32/SuperTeam):** este documento **toma de ahí** el estado real (ESP32 no existe, `superteam.py` no existe, dos rutas incompatibles, pines 34/35 liberados sin uso, protocolo de aplicación inexistente) y **agrega lo que faltaba**: los **dos ejercicios concretos** que el coach pidió y que esa auditoría no incluía. La recomendación de **Ruta B** sale de su §5 y se respeta.
- **Issue #84 ([TEMA] Stub Bluetooth para SuperTeam):** el **Ejercicio 2 es la primera implementación real** de ese stub (`superteam.py`, `SuperTeamChannel`, `announce_state`/`wait_for_signal`). Sigue 100 % válido y sin implementar; estos ejercicios lo aterrizan en una sesión.
- **Cadena RESILIENCIA #27/#53 (heartbeat/watchdog):** el **Bloque 5 del Ejercicio 2 (degradación)** entrena exactamente el principio de esos issues — el robot **no debe colgarse** si un canal cae. El `PING/PONG` con timeout del canal SuperTeam es un heartbeat aplicado al enlace inter-robot.
- **`comms-01` F-1/F-2/F-3 (protocolo serial Teensy↔RPi):** **regla dura heredada** — el canal SuperTeam **no toca** ese UART frágil. Por eso vive en BT, aislado, por flag. No se suma tráfico al enlace ya saturado (overflow de 0,27 s, sin heartbeat).
- **CORRECTITUD #B1–#B10:** sin solapamiento (ninguno toca comms inter-robot). El protocolo `[255,speed,254,angle,253,green,252,silver]` es exclusivamente RPi→Teensy y no contempla un tercer interlocutor — por eso SuperTeam necesita un canal **nuevo**, no extender ese frame.
- **Issue #68 (requirements sin pinning):** el Ejercicio 2 lo toca tangencialmente al **pinear `bleak`/`pybluez`**.

---

## 6. Fuentes (reglamento + formato)

- **RoboCupJunior Rescue Line Rules 2026** (final, last updated 2026-03-29): §6.3 *SuperTeam Challenge* (p. 27), §1.3.1 *Robot Communication* (p. 8, 2.4 GHz / ≤ 100 mW EIRP), §6 *Competition* (p. 25, "the inclusion of … the SuperTeam Challenge may vary…"). PDF oficial: `https://junior.robocup.org/wp-content/uploads/2026/02/RCJRescueLine2026-final.pdf`
- **RoboCupJunior — General Rules** (marco general de comunicación y SuperTeam): `https://junior.robocup.org/robocupjunior-general-rules/`
- **Formato histórico del SuperTeam** (composición ≥ 2 equipos de distinto idioma, robots `ROBOT_RED`/`ROBOT_BLUE`, ventana de colaboración, juego conjunto ~8 min, premio propio): patrón estable de RoboCup Junior Rescue (incl. Rescue Simulation), usado aquí sólo para dar realismo a los ejercicios; **la tarea y rúbrica exactas de Line 2026 se anuncian en Incheon** (§6.3.2). Referencias: `https://junior.robocup.org/rcj-rescue-line/`, `https://rescue.rcj.cloud/`
- **Auditoría hermana del repo:** `project/backlog/staging/auditoria-integral-2026-05-18/comms-02-esp32.md` (estado ESP32/#84) y `comms-01-protocolo-integral.md` (UART Teensy↔RPi).

---

*SUPERTEAM-00 (Dos ejercicios) — Auditoría Integral 2026-05-18. Sólo lectura; sin commits ni cambios en GitHub. Filosofía TEMAS A ANALIZAR: cada acción lleva riesgo-de-no-hacerla + riesgo-de-hacerla + tiempo. El equipo decide; el coach (Enzo) asigna; el auditor IA presenta el material. La tarea exacta del SuperTeam Line 2026 se conoce recién en Incheon — estos ejercicios entrenan la capacidad transferible, no una tarea concreta.*
