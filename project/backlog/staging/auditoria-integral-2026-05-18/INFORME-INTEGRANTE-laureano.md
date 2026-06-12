# Informe de Desempeño — Laureano Monteros (@Laumonteros)

**Para:** Enzo Juarez (coach del equipo)
**De:** Coach senior / auditoría integral 2026-05-18 (corrida 2026-05-31)
**Asunto:** Desempeño de Laureano Monteros como dueño técnico del firmware de pinza/garra y co-dueño de la máquina de rescate del Teensy 4.1.
**Insumos:** datos duros de `git log`/`git blame` y `gh` (PRs/issues), + lectura completa del código que firma (`lib/claw/`, partes de `src/main.cpp`, `variables_doc.md`), + las auditorías técnicas de su subsistema (drivebase/PID, línea-FSM, rescate-FSM, sensores, serial).

> **Cómo leer este informe.** Esto es una herramienta de coaching, no un juicio. Laureano es un estudiante de secundaria aprendiendo ingeniería de competencia y tiene **talento real de arquitectura por encima del promedio del equipo**. El tono es exigente con los datos y justo con la persona. Todos los findings de código vienen de auditorías que usan el marco "riesgo-de-no-tocar / riesgo-de-tocar / tiempo" — ninguno es "un bug que Laureano metió y hay que fixear a ciegas". Varios de "sus" bugs son, en realidad, su trabajo perdido o código heredado.

> **Aviso de identidad (importante para Enzo).** Laureano commitea bajo **dos identidades git** — `laumonteros18@gmail.com` (3 commits) y `139661320+Laumonteros@users.noreply.github.com` (3 commits). Es la misma persona; todos los conteos de abajo están deduplicados por el handle **@Laumonteros**. Conviene pedirle que unifique su `git config user.email` en la máquina del banco, porque hoy su huella aparece partida y eso confunde cualquier métrica de equipo. **No existe "Lautaro"** — es un typo recurrente en docs viejas; es Laureano.

---

## 1. Resumen de actividad (datos duros)

| Métrica | Valor | Fuente |
|---|---|---|
| Commits de contenido (no-merge, dedup) | **6** | `git log --all --no-merges` (2 identidades) |
| Commits de merge | 3 | resolución de conflictos rama `Pinzas` |
| **Total commits** | **9** | coincide con `git shortlog` |
| **Ventana de actividad** | **2026-03-07 → 2026-03-14 (8 días)** | primer/último commit |
| **Actividad abril + mayo 2026** | **0 commits** | ~2,5 meses sin tocar `main`, a 30 días del mundial |
| Líneas (bruto) | +534 / −90 | `git show --numstat` |
| PRs abiertos | **2** — #37, #39 | `gh pr list --author Laumonteros` |
| PRs mergeados | 2/2 (ambos por `enzzo19`) | — |
| PRs con review formal (APPROVED) | **0/2** | sólo comentarios |
| **Issues autorados** | **0** | `gh issue list --author Laumonteros` (verificado: lista vacía) |
| Issues asignados OPEN hoy | **14** | incluye #25, #27, #105, #109, #112, #115, #120–#123, #125, #126, #46, #97 |
| Issues cerrados atribuibles a él | ~1 (#51, compartido + de visión) | no es de su dominio |
| Entradas en `testing/TEST_LOG.md` (su dominio) | **0** | viola Regla de Oro #3 |

**Detalle de los 6 commits** (todos en marzo, ninguno después):
```
2026-03-07  f2d1593  fix(teensy):serail comunication broke pinzas   (typo "serail", sin espacio)
2026-03-07  77050d0  add(docs): doc by servo fix                     ("add" no es tipo válido; inglés)
2026-03-07  d149f2e  fix(teensy): solve upload code                  (inglés, verbo vago)
2026-03-13  ec8e6ab  fix(teensy): Timeout/Watchdogs                  (su MEJOR commit — ver §5)
2026-03-14  b8fc68b  fix(teensy):  pinzas y movimiento               (doble espacio, vago)
2026-03-14  c0c620d  fix(teensy): solve conflicts merge              (describe git, no el cambio)
```

**Pull Requests:**
- **PR #39** — `fix(teensy): solve upload code`. Creado y mergeado el mismo día (2026-03-07), 0 reviews. +44/−9.
- **PR #37** — `fix(teensy): serial comunication broke pinzas`. Creado 2026-03-07, **mergeado 2026-04-29 (≈7 semanas abierto)**, 0 reviews, +397/−41. Su cuerpo declara `Closes #123`, pero **#123 no existía** al momento (se creó el 2026-05-19, dos meses después) → link inválido. El mismo cuerpo dice honestamente que resolvió el problema "con ayuda de Copilot en modo agente". Declararlo es lo correcto; el problema es que el `Closes #123` falso sugiere que **aceptó output de IA sin verificarlo** (incluido el número de issue).

**Posición relativa en el equipo** (commits de contenido, todas las ramas):

| Alumno | Commits no-merge | Dominio |
|---|---|---|
| Benjamin Villagran | **26** | firmware + hardware + banco; sostiene `main` |
| **Laureano Monteros** | **6** | pinza + parte de rescate (ráfaga de marzo) |
| Lucio Saucedo | 5 | visión RPi |

Laureano y Lucio están en el mismo orden de magnitud, pero el **dominio de Laureano (control de firmware) es más crítico para "no colgarse en pista"** que lo que sugiere el volumen. El problema no es sólo cantidad: es **continuidad** (todo en 8 días de marzo) y **persistencia** (su mejor trabajo se borró, §5).

---

## 2. Calidad del trabajo

### 2.1 Foco
Laureano **sí es dueño de un subsistema real**, no un contribuidor marginal. Por `git blame` sobre `main`:
- `lib/claw/claw.cpp` y `claw.h` → dueño casi exclusivo (5–6 de 6–7 commits del historial).
- `src/main.cpp` → ~221 líneas (2º contribuidor después de la migración inicial de gviollaz).
- `variables_doc.md` → autor original (iniciativa propia de documentar las globales del firmware; nadie más lo hizo).

El foco temático es correcto y coherente: **pinza, rescate, y resiliencia (timeouts/watchdogs)** — exactamente donde el equipo lo necesita. El problema no es *dónde* trabaja, sino *cuánto sostiene* ese trabajo en el tiempo (§4).

### 2.2 Tests documentados
**Cero.** No hay una sola entrada suya (ni de nadie) en `testing/TEST_LOG.md`, y ninguna referida a pinza/claw. La Regla de Oro #3 ("antes de mergear un fix de firmware, probar en banco y documentar") **no se cumple**. Para un subsistema que **agarra físicamente las víctimas** —lo que más necesita evidencia empírica para el TDP (rúbrica §Software/§Performance)— esto es jugar a ciegas. **Es la deficiencia de proceso más importante de su perfil.**

### 2.3 Convenciones (Reglas de Oro)

| Regla | ¿Cumple? | Evidencia |
|---|---|---|
| #1 PR con review | ⚠️ Parcial | Usó PRs (bien), pero **0 reviews formales** en ambos |
| #2 Cambio vinculado a Issue | ⚠️ Parcial | PR #37 → `Closes #123` **inexistente**; resto sin link |
| #3 Banco + TEST_LOG | ❌ **No** | 0 entradas |
| #5 Idioma fuente español | ⚠️ Parcial | 3 de 6 commits en inglés |
| #7 Conventional Commits español | ⚠️ Parcial | usa `tipo(scope):` pero con `add(...)` inválido + typos |

Cumple **la letra parcial pero no el espíritu** de varias reglas. Nada de esto es grave de forma aislada; el patrón conjunto (PRs sin review, sin link real, sin test, con typos) dibuja **disciplina de proceso floja**. Aclaración justa: parte de la responsabilidad de "0 reviews" y "PR de 7 semanas" es **compartida con quien mergeó** (el coach), no sólo de Laureano.

### 2.4 Calidad del código que firma (lectura directa)

**Lo bueno (mérito genuino, confirmado por lectura de `claw.cpp`/`claw.h`):**
- **Máquina de estados no bloqueante de la pinza** (`Claw::update()` con `CL_PICKUP_*_STEP1..4`): es el patrón **correcto** para no bloquear el loop mientras la garra se mueve, y **ataca directamente su propio issue #25** (bloqueo serial en pinzas) de la forma arquitectónicamente correcta. Esto es de lo mejor del firmware del equipo.
- **`enum ClawState` documentado** estado por estado (claw.h:53-63). Legible y mantenible.
- **`begin()` separado del constructor** con comentario explícito *"Do not attach here to avoid global initialization issues"* (claw.cpp:8): muestra que entendió un problema real y sutil de orden de inicialización de objetos globales en Arduino/Teensy. **Sofisticado para su nivel.**

**Temas a analizar — NUEVOS, no listados en auditorías previas** (cada uno con su lectura de riesgo; ninguno cambia el veredicto de "buen diseño", son detalles a pulir):

- **`_lastAction` declarado `unsigned long long`** (claw.h:51) y asignado siempre desde `millis()` (que es `unsigned long` 32-bit). El hermano `_stateStartedAt` sí es `unsigned long` (correcto). El mismatch rompe la semántica de wraparound de `millis()` (diseñada para 32-bit). *Riesgo real: casi nulo (haría falta >49 días de corrida).* Pero **delata copy/paste o IA sin entender la semántica**. Fix trivial (2 min), pero igual exige re-test en banco.
- **`Claw::available()` es código muerto** (claw.cpp:54-57). La lógica de rescate decide por `busy()`/`_state`, no por `available()`/`_lastAction`. Quedan **dos mecanismos de "estoy ocupado" en paralelo** y uno está abandonado: las 13 asignaciones de `_lastAction` alimentan una función que nadie llama. Deuda de mantenibilidad / bus-factor.
- **`Claw::pickupLeft()/pickupRight()` + estados `CL_PICKUP_*` están MUERTOS.** La auditoría de rescate confirmó que la recolección real corre por una **secuencia inline bloqueante** en `main.cpp` (la que RESILIENCIA marcó por bloquear UART), y que `actualizarRescate()` + `pickup*()` **nunca se invocan**. O sea: la pieza más linda que escribió Laureano —su FSM no bloqueante— **no se ejecuta**. El equipo puede estar tuneando código fantasma.
- **`green_state != 0` usado como proxy de "hay línea"** en la recuperación que escribió (commit `ec8e6ab`): `green_state` codifica verdes/pelotas/rojo, **no** presencia de línea negra. Es semánticamente incorrecto (el robot creería que "tiene línea" al ver un cuadrado verde). Hoy no vive en `main` (se perdió con el revert), pero importa si se **re-aplica** (issue #115). Patrón de "reuso la primera variable que suena parecida", típico de soluciones asistidas por IA sin validar el dominio.
- **`variables_doc.md` ya está desactualizado:** describe `serial5state` con valores 0–3, pero el protocolo oficial maneja 4 campos `[255,speed,254,angle,253,green,252,silver]`. **Documentación que miente es peor que no tenerla**, porque la próxima persona (o IA) confía en ella. Fix de markdown, sin riesgo de robot (30–45 min).

### 2.5 Reincidencia de bugs
Matiz importante y **a favor de Laureano**: el bug **B5 / #122 "velocidad sube a 55 en curva"** (confirmado vivo en `main.cpp:1066-1068`) **NO lo re-introdujo**. Es el código que su commit `ec8e6ab` intentó **borrar/refactorizar** en marzo; como ese PR nunca llegó a `main` (§5), el bug original sobrevivió y hoy se le re-asigna. No es reincidencia: es **su trabajo perdido**. Lo mismo aplica a los timeouts (B-family de resiliencia). El dato real no es "reincide en bugs", sino "**su mejor trabajo no tuvo impacto porque no se integró**".

---

## 3. Fortalezas concretas

1. **Mejor instinto de arquitectura de firmware del equipo (dentro de su módulo).** La FSM no bloqueante de la pinza y la separación `begin()`/constructor no son copy-paste: demuestran comprensión real de los problemas correctos (no bloquear el loop, orden de init de globales). Si sostuviera el involucramiento, **sería el firmware-lead natural**.
2. **Ataca los problemas correctos.** Su issue propio #25 (bloqueo serial) lo resolvió con el patrón arquitectónicamente bueno; su commit estrella iba por timeouts/watchdogs (la familia de resiliencia que es justo lo que más necesita el robot para "no colgarse"). El **criterio técnico de qué importa** está bien calibrado.
3. **Iniciativa de documentación.** `variables_doc.md` fue idea suya y nadie más lo hizo. Aunque quedó desactualizado, **el reflejo de documentar es valioso** y hay que reforzarlo, no penalizarlo.
4. **Transparencia sobre el uso de IA.** Declaró explícitamente que usó Copilot en modo agente. Eso es **honestidad de proceso** y hay que valorarlo (el problema no es usar IA, es no verificar su salida — ver §4).
5. **Dueño de subsistema, no contribuidor de paso.** Posee de verdad `lib/claw/` y ~221 líneas de `main.cpp`. Tiene un territorio técnico propio sobre el que construir.

---

## 4. Debilidades / áreas de mejora concretas

1. **Desconexión temporal — el riesgo #1.** **0 commits en abril y mayo.** El dueño de la pinza y de media máquina de rescate lleva ~2,5 meses sin tocar `main`, con el mundial en 30 días y **14 issues asignados OPEN** (incluidos sus propios #25 y #27 originales, y los 6 de CORRECTITUD). Esto es **bus-factor puro**: si la pinza falla en Incheon, el autor lleva meses desconectado del código. Es lo más urgente a conversar.
2. **Cero verificación empírica.** Ninguna prueba de banco documentada de la pinza. Para el subsistema que agarra víctimas, y para el TDP, es **evidencia faltante crítica**. No sabemos si su FSM siquiera corre en el robot real (de hecho, la versión que corre es la inline bloqueante, no la suya).
3. **Acepta salida de IA sin verificar.** El `Closes #123` falso en PR #37, los typos, y el `green_state` mal usado apuntan al mismo hábito: **delegar en la IA y no auditar el resultado**. A su nivel es entendible, pero es exactamente la habilidad que más hay que entrenar para que su talento escale sin meter deuda.
4. **Su trabajo no se integra / no hace seguimiento.** PR #37 marinó 7 semanas; su mejor commit (`ec8e6ab`) nunca llegó a `main` y nadie (ni él) lo reclamó. **No hace follow-up de sus propios PRs** hasta verlos mergeados y vivos en `main`. Un cambio que no llega a `main` es trabajo perdido.
5. **Higiene de proceso floja.** Commits en inglés con typos y verbos vagos, dos identidades git, PRs sin link real a issue, sin review. Individualmente menor; en conjunto **resta profesionalismo y trazabilidad** justo en el firmware que más se cuelga.
6. **No revisa PRs de compañeros** (no aparece como reviewer en GitHub). Pierde una vía de aprendizaje y de aportar al equipo de bajo costo. (Si lo hace fuera de GitHub, no es medible.)

---

## 5. El caso "ec8e6ab" — por qué merece atención de Enzo

Este es el dato más importante para entender a Laureano, y conviene que Enzo lo trabaje explícitamente con él:

- Su commit **`ec8e6ab "fix(teensy): Timeout/Watchdogs"`** (+57/−14 en `main.cpp`) implementaba timeouts en `runAngle`/`runDistance` + recuperación de línea. **Verificado:** `git merge-base --is-ancestor ec8e6ab main` → **NO es ancestro de `main`**. Su mejor trabajo **nunca se integró**.
- Ese esfuerzo fue **rehecho después por Benjamin** (`5bac4a5` "timeouts implementados") y luego **revertido en `cead75e`** ("error de libreria claw.cpp", que borró 181 líneas, probablemente arrastrando los timeouts de forma no intencional).
- **Consecuencia hoy:** el firmware en `main` **no tiene ningún timeout** en `runAngle`/`runDistance`/esquiva → cuelgue permanente sin WDT (lo confirman las auditorías de línea y resiliencia). Y el bug B5 (vel 55 en curva) sobrevive **porque es justo el código que `ec8e6ab` intentaba borrar**.

**Lectura de coaching:** Laureano hizo el trabajo correcto, en el momento correcto, sobre el problema correcto — y **el proceso del equipo lo desperdició** (PR sin review, merge tardío, revert masivo sin verificar qué se llevaba puesto). Esto es tanto un problema del equipo como de él. La oportunidad de oro: el issue **#115 le pide re-aplicar SUS timeouts** — es recuperar su propio trabajo perdido, con alta probabilidad de éxito.

---

## 6. Recomendaciones de coaching para Enzo

Ordenadas por impacto. La idea es **reconectar a Laureano a través de una victoria rápida** y construir disciplina desde ahí, sin aplastar su talento.

1. **Reactivación inmediata con una victoria garantizada — ejecutar #115 (re-aplicar SUS timeouts).** Es trabajo que ya hizo una vez (`ec8e6ab` está en git, `git show ec8e6ab`), ataca el riesgo P0 de "se cuelga", y le devuelve el orgullo de ver su código vivo en `main`. **Empezá por acá esta semana.** Es la palanca psicológica + técnica de mayor ROI.
2. **Romper el cero de TEST_LOG.** Pedile **una** entrada de banco de la pinza (categoría `[MECH]`/`[SW]`): "la garra baja, clasifica y deposita, N/N veces". Rompe el cero, le da evidencia citable para el TDP, y lo obliga a comprobar **si su FSM siquiera corre en el robot** (spoiler: hoy corre la inline bloqueante, no la suya — descubrir eso juntos es muy formativo).
3. **Triage guiado de sus issues B*.** Sentarse 30 min y que **él** clasifique cuáles de sus 6 issues de CORRECTITUD (#120/#121/#122/#123/#125/#126) son reales y cuáles son su trabajo perdido. Priorizar los que afectan agarrar víctimas y no salirse de pista (B5, B6, B10). Que **vea** que B5 es el código que él intentó borrar lo reconecta con la historia.
4. **Entrenar el "verificar la IA".** Como usa Copilot (y lo declara, bien), enseñarle un check mínimo antes de commitear: *(a)* ¿el número de issue del `Closes #N` existe?, *(b)* ¿la variable que reusé significa lo que creo (mirar `variables_doc.md`)?, *(c)* ¿compila y lo probé en banco? Convertirlo en un hábito de 3 preguntas, no en un sermón. Esto multiplica su talento sin frenarlo.
5. **Higiene de proceso, en pequeño:** unificar su `git config user.email`; commits en español; PR chico con link a issue **real**; y **regla dura del equipo: ningún merge sin 1 review** (esto es tanto pedido a Enzo como a Laureano). PRs de 7 semanas y +397 líneas no pueden repetirse.
6. **Darle un rol que exija continuidad, no ráfagas.** Su patrón es "aparezco, hago una semana brillante, desaparezco". Asignarle **ownership explícito con check-ins semanales cortos** (15 min: ¿qué tocaste de la pinza esta semana? ¿qué probaste en banco?) lo fuerza a sostener, que es justo su debilidad. Idealmente, **emparejarlo con Benjamin** (que sostiene `main`) para que su arquitectura y la continuidad de Benjamin se potencien — y para reducir el bus-factor de la pinza de cara a Incheon.

---

## 7. Veredicto honesto (una línea para Enzo)

**Talento de arquitectura de firmware por encima del promedio del equipo, lastrado por disciplina de proceso e involucramiento sostenido muy por debajo de lo que exige un mundial.** El riesgo real no es que escriba mal —escribe bien—: es **bus-factor + subsistema sin un solo test + su mejor trabajo perdido + sus propios bugs sin atender a 30 días de Incheon**. La buena noticia: la palanca de reactivación (#115, recuperar sus timeouts) es a la vez la de mayor impacto técnico y la más motivante para él. Si se reconecta, es el firmware-lead que el equipo necesita.

---

## 8. Limitaciones de esta evaluación

- **Trabajo no commiteado no es medible:** horas de banco, debugging físico o ayuda a compañeros que no dejen rastro en git. Es posible que su contribución real sea mayor que su huella en commits.
- **Atribución de #51:** cerrado y compartido entre 3 personas; no hay forma desde git/gh de aislar su parte. Contado como ~1 con la salvedad de que es de visión, no firmware.
- **Líneas en bruto:** las +534 incluyen re-adiciones tras merges; no es código nuevo neto.
- **Responsabilidad compartida:** "0 reviews" y "PR de 7 semanas" dependen también del coach que mergeó, no sólo de Laureano. Se señala como proceso del equipo a corregir, no como falta individual.
- **Los findings técnicos** provienen de las auditorías de dominio (drivebase/PID, línea, rescate, sensores, serial) en esta misma carpeta; este informe los **cruza con la actividad de la persona**, no los re-audita.

---

*Informe de desempeño individual · auditoría integral 2026-05-18 · dominio Firmware/Laureano · sólo lectura, sin modificación de código fuente ni de issues.*
