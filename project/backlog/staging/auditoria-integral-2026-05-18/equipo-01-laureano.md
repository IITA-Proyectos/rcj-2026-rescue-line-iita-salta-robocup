# Auditoría de Desempeño — Laureano Monteros (@Laumonteros)

**Dominio:** Firmware Teensy 4.1 (PlatformIO C++) — control, pinza/garra, timeouts.
**Período auditado:** repo completo hasta 2026-05-31 (checkout `feature/initialize-testing-log`, contenido equivalente a `main`).
**Auditor:** análisis de datos duros (git log/blame, `gh pr/issue`) + lectura completa del código que firma.
**Marco:** este informe NO presenta "bugs a fixear". Cada finding lleva su lectura de riesgo y se enmarca como **tema a analizar** sobre el desempeño de la persona, no sobre la calidad moral del alumno. Laureano es un estudiante de secundaria aprendiendo ingeniería de competencia; el tono es exigente con los datos y justo con la persona.

> **Aviso de identidad:** Laureano commitea bajo dos identidades git — `Laureano Monteros <laumonteros18@gmail.com>` (5 commits) y `Laureano Monteros <139661320+Laumonteros@...>` (4 commits). Ambas son la misma persona. Todos los conteos de abajo están deduplicados y cruzados con `gh` por el handle **@Laumonteros**. No existe "Lautaro" — es error de tipeo recurrente en docs preexistentes, ya corregido en commits `6ffba5d`/`5a868ea`.

---

## 1. Resumen ejecutivo

Laureano es el **dueño técnico de un subsistema real y crítico**: la pinza/garra (`lib/claw/`) y buena parte de la máquina de rescate en `main.cpp`. Su código de garra es de los más limpios del firmware: máquina de estados **no bloqueante** bien estructurada, con `enum` documentado y nombres claros. Eso es mérito genuino y poco común a su nivel.

Pero los datos de actividad y de proceso cuentan una historia preocupante de cara a Incheon:

1. **Actividad concentrada y vieja.** Sus 6 commits de contenido caen en una sola ventana de **8 días (7→14 de marzo de 2026)**. No registra un solo commit de firmware en abril ni en mayo. A 30 días del mundial, el dueño del firmware de pinza lleva ~2,5 meses sin tocar `main`.
2. **Su trabajo de resiliencia se perdió.** Su commit estrella `ec8e6ab "fix(teensy): Timeout/Watchdogs"` (timeouts en `runAngle`/`runDistance` + recuperación de línea) **nunca llegó a `main`** y fue superado/borrado por el trabajo de Benjamin (`5bac4a5` + revert `cead75e`). Hoy ese esfuerzo no protege al robot.
3. **Sus tareas asignadas siguen abiertas.** Sus issues originales **#25 (bloqueo serial en pinzas)** y **#27 (watchdogs)** siguen OPEN. El único issue cerrado que tiene asignado (#51) es una tarea **compartida de etiquetado de dataset**, ni siquiera de su dominio.
4. **Cero evidencia de banco.** `testing/TEST_LOG.md` no tiene ninguna entrada real suya (ni de nadie). La Regla de Oro #3 del repo exige probar firmware en banco y documentarlo; su subsistema de pinza es justamente el que más necesita esa evidencia para el TDP.
5. **Proceso flojo.** Sus 2 PRs se mergearon con **0 reviews formales**; PR #37 estuvo **7 semanas abierto** y declara `Closes #123` (un issue que en ese momento no existía — link inválido). Mensajes de commit con typos y verbos vagos.

**Veredicto honesto:** talento técnico por encima del promedio del equipo en diseño de su módulo, pero **disciplina de proceso e involucramiento sostenido muy por debajo de lo que exige un mundial.** El riesgo no es que escriba mal: es que su subsistema llegue a Incheon sin él, sin tests y con sus propios bugs reportados (#120-#126) todavía sin tocar.

---

## 2. Datos duros — Cantidad

| Métrica | Valor | Fuente / nota |
|---|---|---|
| Commits de contenido (no-merge, dedup) | **6** | `git log --all --no-merges --author` (2 identidades) |
| Commits de merge | 3 | resolución de conflictos en rama `Pinzas` |
| **Total commits** | **9** | coincide con `git shortlog` (5+4) |
| Período de actividad | **2026-03-07 → 2026-03-14 (8 días)** | primer y último commit |
| Actividad abril–mayo 2026 | **0 commits** | sin actividad en `main` en 2,5 meses |
| Líneas agregadas / borradas (bruto) | **+534 / −90** | `git show --numstat` agregado |
| PRs abiertos por él | **2** (#37, #39) | `gh pr list --author Laumonteros` |
| PRs mergeados | **2 / 2** | ambos por `enzzo19` |
| PRs con review formal | **0 / 2** | sólo comentarios, ningún `APPROVED` |
| Issues autorados | **0** | `gh issue list --author Laumonteros` |
| Issues asignados (total histórico) | 15 | incluye los de auditorías nuevas |
| Issues cerrados asignados a él | **1** (#51) | y es compartido + de visión, no firmware |
| Issues propios de firmware aún OPEN | #25, #27 | sus P1/P2 originales, sin cerrar |
| Entradas en TEST_LOG.md | **0** | toda la bitácora está vacía |

### Comparación con pares (commits de contenido, todas las ramas)

| Alumno | Commits no-merge | Lectura |
|---|---|---|
| Benjamin Villagran | **26** | dueño de facto del firmware + hardware + banco; el que más sostiene `main` |
| **Laureano Monteros** | **6** | dueño de pinza; ráfaga de marzo, luego silencio |
| Lucio Saucedo | 5 | visión RPi (dominio distinto) |

> Laureano y Lucio están en el mismo orden de magnitud (5-6), pero el dominio de Laureano (firmware de control) es mucho más crítico para "no colgarse en pista" que la cantidad sugiere. El problema no es sólo volumen: es **continuidad** (todo en una semana) y **persistencia del trabajo** (su mejor commit se borró).

### Archivos que realmente posee (git blame sobre `main`)

| Archivo | Su autoría | Nota |
|---|---|---|
| `lib/claw/claw.cpp` | **5 de 6 commits** del historial | dueño casi exclusivo (resto: migración inicial de gviollaz) |
| `lib/claw/claw.h` | **6 de 7 commits** | dueño casi exclusivo |
| `src/main.cpp` | **~221 líneas** (194 + 27 entre sus 2 identidades) de 1278 | 2º contribuidor después de gviollaz (migración) |
| `variables_doc.md` | autor original (72 líneas) | doc de variables, buena pero ya desactualizada (ver §4) |

**Conclusión de cantidad:** Laureano **sí es dueño de un subsistema** (no es un contribuidor marginal). Pero su huella temporal es una ráfaga de 8 días en marzo y nada más. Para un proyecto que cierra en junio, eso es un riesgo de bus-factor: si la pinza falla en Incheon, el autor lleva meses desconectado del código.

---

## 3. Datos duros — Calidad de proceso

### 3.1 Pull Requests

| PR | Título | Creado | Mergeado | Gap | Mergeado por | Reviews | Δ |
|---|---|---|---|---|---|---|---|
| #39 | fix(teensy): solve upload code | 2026-03-07 | 2026-03-07 (2 min después) | inmediato | enzzo19 | **0** | +44/−9 |
| #37 | fix(teensy): serial comunication broke pinzas | 2026-03-07 | **2026-04-29** | **~7 semanas** | enzzo19 | **0** | +397/−41 |

Observaciones críticas sobre el proceso:

- **0 reviews formales en ambos PRs.** La Regla de Oro #1 del repo dice "Toda mejora pasa por PR con al menos un review". Se cumplió la letra (hubo PR) pero no el espíritu (nadie aprobó formalmente; sólo comentarios). Esto es responsabilidad compartida con el coach que mergeó, pero el patrón debilita la calidad del firmware que más se cuelga.
- **PR #37 estuvo 7 semanas abierto** (7-mar → 29-abr). Un PR de pinza de +397 líneas marinándose casi dos meses es deuda de integración pura: durante ese tiempo `main` y `Pinzas` divergieron y hubo que resolver conflictos a mano (commits `c0c620d`, `c051439`, `327df6f`). PRs grandes y longevos son exactamente lo que el repo quiere evitar.
- **Vínculo a issue inválido.** El cuerpo de PR #37 declara `Closes #123`, pero #123 es `[CORRECTITUD] B6 — salida anticipada del cuarto`, creado el **2026-05-19**, dos meses *después* del PR. Es un link fabricado/alucinado (muy probablemente sugerido por la IA, ver abajo). La Regla de Oro #2 ("todo cambio se vincula a un Issue") se cumple de forma puramente cosmética: el número no corresponde a nada real en ese momento.
- **Uso de IA declarado honestamente.** El cuerpo de PR #37 dice textualmente que resolvió el problema "con ayuda de Copilot en modo agente" pidiéndole "que analizara todo lo relacionado con la Teensy". Declararlo es lo correcto (transparencia). Pero combinado con el `Closes #123` falso y los typos, sugiere que **aceptó output de IA sin verificarlo a fondo** — incluido el número de issue.

### 3.2 Mensajes de commit (convención del repo: Conventional Commits en español)

Lista completa de sus subjects:
```
fix(teensy):serail comunication broke pinzas   ← typo "serail", sin espacio tras ":"
add(docs): doc by servo fix                     ← "add" no es tipo válido; mezcla inglés/español
fix(teensy): solve upload code                  ← inglés, verbo vago
fix(teensy): Timeout/Watchdogs                  ← OK-ish pero sin descripción de qué se hizo
fix(teensy):  pinzas y movimiento               ← doble espacio, vago ("y movimiento")
fix(teensy): solve conflicts merge              ← inglés, describe mecánica de git no el cambio
```

Evaluación: **parcialmente adherente.** Usa el prefijo `tipo(scope):` la mayoría de las veces, lo cual está bien. Pero:
- 3 de 6 están en **inglés**, violando la Regla de Oro #5 ("idioma fuente: español" para commits).
- Usa `add(...)` que no es un tipo Conventional Commits válido (debería ser `docs(...)`).
- Typos (`serail`), dobles espacios, y mensajes que describen **la mecánica de git** ("solve conflicts merge") en vez del **cambio funcional**.
- Ninguno referencia el issue que resuelve en el cuerpo (los `Closes #N` aparecen recién en el PR, y mal).

### 3.3 Issues — ¿cierra lo suyo? ¿reincide en bugs?

| Issue | Título | Estado | Relación |
|---|---|---|---|
| #25 | P1 - Bloqueo Serial en movimiento de pinzas | **OPEN** | asignado a él, su dominio core |
| #27 | P2 - Watchdogs Faltantes | **OPEN** | asignado a él + Lucio |
| #51 | Etiquetado y entrenamiento del modelo | CLOSED | **compartido (3 asignados), es visión, no firmware** |
| #105, #109, #112, #115 | Cluster Teensy / RESI (auditoría resiliencia) | OPEN | asignados a él, sin tocar |
| #120, #121, #122, #123, #125, #126 | CORRECTITUD B1/B5/B6/B8/B10 | OPEN | asignados a él, sin tocar |

- **Su único "cierre" (#51) no es de su dominio** y es una tarea grupal de etiquetado en Roboflow. No hay evidencia de que el cierre sea atribuible a él específicamente.
- **Reincidencia en bugs (dato fuerte):** el bug **B5 / #122 "velocidad sube a 55 en curva"** está en `main.cpp:1066-1068`. Ese bloque es *exactamente* el código que su commit `ec8e6ab` intentó refactorizar y eliminar en marzo. Como su PR de timeouts nunca se mergeó a `main`, el bug volvió y hoy se le re-asigna a él. No es que lo haya *re-introducido* — es que su fix se perdió y el bug original quedó. Esto refuerza el punto: **su trabajo de resiliencia no tuvo impacto porque no se integró.**
- Tiene **6 issues de CORRECTITUD nuevos asignados (B1, B5, B6, B8, B10)** todos OPEN. Son bugs en código que en buena parte él tocó (encoder 25 pulsos/cm sin calibrar, runAngle(180), salida anticipada del cuarto). A 30 días del mundial, ninguno está en progreso.

---

## 4. Calidad del código que firma (lectura completa)

Leí íntegros `lib/claw/claw.cpp`, `lib/claw/claw.h`, `variables_doc.md` y los diffs de sus commits en `main.cpp`. Lo bueno y lo que queda como tema a analizar:

### Lo bueno (mérito real)
- **Máquina de estados no bloqueante** (`Claw::update()` con `CL_PICKUP_*_STEP1..4`): el patrón correcto para no bloquear el loop principal. Es la diferencia entre un robot que sigue leyendo serial mientras mueve la pinza y uno que se cuelga. Esto **ataca directamente su issue #25** (bloqueo serial) de la forma arquitectónicamente correcta.
- **`enum ClawState` documentado** con comentario por estado (claw.h:53-63). Legible y mantenible.
- **`begin()` separado del constructor** con comentario explícito ("Do not attach here to avoid global initialization issues", claw.cpp:8) — muestra que entendió un problema real de orden de inicialización de objetos globales en Arduino/Teensy. Es sofisticado para su nivel.
- **`variables_doc.md`**: documentar todas las variables globales del firmware es una iniciativa valiosa que nadie más tomó.

### Temas a analizar (nuevos — NO en auditorías previas #53/#27/#120-#128)

**T-L01 — Tipo `unsigned long long` para `_lastAction` (claw.h:51), mezclado con `millis()`.**
`millis()` devuelve `unsigned long` (32-bit en Teensy). `_lastAction` está declarado `unsigned long long` (64-bit). La resta `millis() - _lastAction` en `available()` (claw.cpp:56) mezcla anchos: el `millis()` de 32-bit se promociona a 64-bit, y como `_lastAction` se asigna desde `millis()` (32-bit), la aritmética de wraparound de `millis()` (que está *diseñada* para funcionar en 32-bit) deja de comportarse como se espera. En la práctica el riesgo es bajísimo (haría falta una corrida de >49 días), pero es un **mismatch de tipos que delata copy-paste/IA sin entender la semántica de wraparound**. El mismo patrón inconsistente: `_stateStartedAt` sí es `unsigned long` (correcto). 
- *Riesgo de NO tocar:* prácticamente nulo en una corrida de 8 min. Cosmético.
- *Riesgo de tocar:* trivial (cambiar `unsigned long long`→`unsigned long`), 2 min. Pero tocar la pinza sin banco viola Regla #3.
- *Tiempo:* 2 min fix + obligatorio re-test en banco.

**T-L02 — `Claw::available()` es código muerto.**
`available()` (claw.cpp:54-57, basado en `_lastAction` + ventana de 1000 ms) no se usa: la lógica de rescate en `main.cpp` decide por `busy()` y por su propia máquina `RescateState`. Quedan **dos mecanismos de "estoy ocupado" en paralelo** (`available()`/`_lastAction` vs `busy()`/`_state`), y uno está abandonado. Toda la maquinaria de `_lastAction` (13 asignaciones en claw.cpp) existe sólo para alimentar una función que nadie llama.
- *Riesgo de NO tocar:* mantenibilidad — un futuro lector (o IA) puede creer que `_lastAction` importa y construir sobre lógica muerta. Confunde el bus-factor.
- *Riesgo de tocar:* bajo, pero es refactor de su módulo → banco.
- *Tiempo:* 15-20 min limpieza + re-test.

**T-L03 — En su commit de recuperación (`ec8e6ab`), `green_state != 0` se usó como proxy de "hay línea".**
En `reencontrarLinea()` y en el case 7 que escribió, usó `if(green_state != 0) { tiempoSinLinea = millis(); }` como señal de "veo la línea". Pero `green_state` (según su propio `variables_doc.md`) codifica **marcadores verdes, pelotas y rojo (valores 1,2,3,6,7,8,9...)**, no presencia de línea negra. Usarlo como "tengo línea" es semánticamente incorrecto: el robot creería que tiene línea cuando ve un cuadrado verde, y dispararía la recuperación en momentos equivocados. **Este código ya no está en `main`** (se perdió con el revert), así que es un tema de *criterio de diseño* más que un bug vivo — pero ilustra un patrón de "reutilizar la primera variable que suena parecida" típico de soluciones asistidas por IA sin validar el dominio.
- *Riesgo de NO tocar:* nulo hoy (código no vive en main). Relevante sólo si alguien intenta **re-aplicar** sus timeouts (que es justo lo que pide el issue #115).
- *Riesgo de tocar / re-aplicar:* medio — hay que reintroducir la lógica con la señal correcta de línea, no con `green_state`.
- *Tiempo:* parte del trabajo de #105/#115 (re-aplicar timeouts), varias horas + banco.

**T-L04 — `variables_doc.md` ya está desactualizado respecto a `main.cpp`.**
El doc describe `serial5state` con "Valores: 0 (speed), 1 (steer), 2 (task), 3 (line_middle). No debe ser >3", pero el protocolo oficial del repo (CLAUDE.md) y `serialEvent5()` manejan **4 campos** `[255,speed,254,angle,253,green,252,silver]`. La doc quedó atada a una versión vieja del firmware. Documentar está muy bien; **documentación que miente es peor que no tenerla** porque la próxima persona (o IA) confía en ella.
- *Riesgo de NO tocar:* medio — induce a error a quien lea el protocolo. 
- *Riesgo de tocar:* nulo (es markdown, no es código de robot).
- *Tiempo:* 30-45 min para sincronizar el doc con el `main.cpp` actual.

> Nota: los bugs **B1 (PID invertido), B5 (vel 55), B6 (salida anticipada), B8 (runAngle 180), B10 (encoder sin calibrar)** ya están documentados en las auditorías previas (#120-#128) y asignados a Laureano. NO los re-listo. Sólo dejo constancia de que **varios caen en código que él tocó o posee**, y que ninguno está en progreso.

---

## 5. ¿Respeta las convenciones del repo? (checklist Reglas de Oro)

| Regla de Oro | ¿Cumple? | Evidencia |
|---|---|---|
| #1 No push directo a main; PR con review | ⚠️ Parcial | Usó PRs (bien), pero **0 reviews formales** en ambos |
| #2 Todo cambio vinculado a Issue | ⚠️ Parcial | PR #37 declara `Closes #123` **inexistente** al momento; el resto sin link |
| #3 Probar en banco + documentar en TEST_LOG | ❌ No | **0 entradas** suyas (ni de nadie) en TEST_LOG.md |
| #5 Idioma fuente español (commits) | ⚠️ Parcial | 3 de 6 commits en inglés |
| #7 Conventional Commits en español | ⚠️ Parcial | usa `tipo(scope):` pero con `add(...)` inválido, typos, inglés |

No aplican a su rol directamente: #4 (no romper lo que funciona — irónicamente su trabajo *se rompió* a él), #6 (hardware versionado — dominio de Benjamin).

---

## 6. Evaluación honesta y recomendaciones

**Fortaleza diferencial:** Laureano tiene el mejor instinto de **arquitectura de firmware** del equipo dentro de su módulo. La máquina de estados no bloqueante de la pinza y la separación `begin()`/constructor demuestran comprensión real, no copy-paste. Si sostuviera ese nivel de involucramiento, sería el firmware-lead natural.

**Riesgo #1 — Desconexión temporal.** El dato más duro: **0 commits en abril y mayo.** El dueño de la pinza y de media máquina de rescate lleva ~2,5 meses sin tocar `main`, con el mundial en 30 días y 6 issues de CORRECTITUD propios sin abrir. Esto es lo más urgente a conversar con él y con Enzo.

**Riesgo #2 — Su mejor trabajo no se integró.** Sus timeouts/watchdogs (`ec8e6ab`) nunca llegaron a `main` y fueron rehechos por Benjamin. Hay que entender *por qué*: ¿se perdió en un merge?, ¿se descartó?, ¿nadie lo revisó a tiempo (PR #37 marinó 7 semanas)? El issue #115 le pide re-aplicar timeouts — es exactamente recuperar su propio trabajo perdido.

**Riesgo #3 — Cero disciplina de verificación.** No hay una sola prueba de banco documentada de la pinza. Para el TDP (rúbrica §Software/§Performance) eso es evidencia faltante; para Incheon es jugar a ciegas con el subsistema que agarra las víctimas.

**Recomendaciones concretas (para el coach, no para imponerle al alumno):**
1. **Reactivación inmediata:** sentarlo a ejecutar #115 (re-aplicar SUS timeouts) — es trabajo que ya hizo una vez, alta probabilidad de éxito, y recupera resiliencia perdida.
2. **Que documente 1 test de pinza en TEST_LOG** (categoría `[MECH]`/`[SW]`) — rompe el cero y le da evidencia citable para el TDP.
3. **Triage de sus 6 issues B*:** que confirme cuáles aplican a su código y priorice B1/B5/B10 (los que afectan no-colgarse y agarrar víctimas).
4. **Higiene de proceso:** PRs chicos, en español, con link a issue *real*, y exigir 1 review antes de merge (esto es tanto del coach como de él).

---

## 7. Limitaciones de esta auditoría (qué NO pude medir)

- **Atribución de #51:** está cerrado y asignado a 3 personas; no hay forma desde git/gh de saber qué parte hizo Laureano específicamente. Lo conté como "1 cerrado" pero con la salvedad de que es compartido y de visión.
- **Trabajo no commiteado:** no puedo medir horas de banco, debugging físico, o ayuda a compañeros que no dejen rastro en git. Es posible que su contribución real al equipo sea mayor que su huella en commits.
- **Reviews de otros PRs:** no encontré evidencia de que Laureano haya *revisado* PRs de sus compañeros (no aparece como reviewer). Si lo hizo fuera de GitHub, no es medible.
- **Identidad/typos en docs:** el "Lautaro" preexistente no es culpa suya; ya fue corregido y no afecta su evaluación.
- Los números de líneas son **brutos** (`numstat`); parte de las +173 líneas de `main.cpp` en `77050d0` pueden ser re-adiciones tras merges, no código nuevo neto.

---

*Informe generado para la auditoría integral 2026-05-18 · dominio Firmware/Laureano · sólo lectura, sin modificación de código fuente.*
