# Auditoría integral 2026-05-18 — Análisis crítico de ESTRATEGIA del equipo (tono director)

**Dominio:** estrategia de proyecto rumbo a Incheon — ¿se trabaja en lo correcto, se cambia el **código** o solo se documenta/analiza, se documentan los **testeos**, alcanza el **ritmo**, hay **desbalance** entre subsistemas?
**Autor:** auditor de estrategia (lectura solamente; datos duros de `git log`, `gh issue/pr`, `testing/TEST_LOG.md`).
**Branch analizada:** `feature/initialize-testing-log` (contenido también en `main`, post-PR #101).
**Fecha de corte de datos:** 2026-05-31. **Mundial:** Incheon, 2026-06-30 → 07-06 → **quedan 30 días al inicio**.

> **Marco de lectura (LEER ANTES).** Este informe es de **dirección**, no de código. No repite las dos auditorías técnicas previas (RESILIENCIA #53/#27/#57–#119 y CORRECTITUD #120–#128); las **cita** y construye encima con los datos de actividad real del repo. Cada riesgo estratégico viene con **riesgo de NO corregir el rumbo**, **riesgo de corregirlo** (costo/efecto colateral) y **esfuerzo**. La decisión es del director y el coach. El tono es duro a propósito: faltan 30 días y el diagnóstico tibio no sirve.

---

## 0. TL;DR para el director (leer esto si no leés nada más)

1. **El código del robot está CONGELADO desde el 2026-05-10.** El último commit que tocó `.cpp`/`.py`/`.h` mergeado a `main` es `cead75e` (claw.cpp), del **10 de mayo**. Hace **21 días** que no entra una línea de código del robot a la rama principal. La competencia es en 30 días.
2. **Todo el trabajo real de fixes existe, pero está atrapado en un PR sin mergear: #129 "Bugs prioritarios"** (abierto **2026-05-24**, +5707/−506, 39 archivos, **0 reviews**, `reviewDecision` vacío). Ese PR es el 80% del valor técnico del último mes y lleva **7 días parado** sin que nadie lo revise. **Si #129 no se mergea, el robot que viaja a Incheon tiene los bugs B1–B10 vivos.**
3. **Los bugs de CORRECTITUD siguen en `main`.** Verificado a mano: `drivebase.cpp:50` todavía dice `analogWrite(_pwmPin, (int)(255 - _pwmVal))` con PID DIRECT (B1/#121). El fix está **solo dentro de #129**, no en la rama principal.
4. **El TEST_LOG de `main` tiene CERO tests reales.** Solo el ejemplo didáctico `T-000`. Las dos únicas entradas reales (`T-001`, `T-002`, del 23-may) viven **dentro de #129**, no mergeadas. O sea: oficialmente el equipo aún no documentó ni un ensayo en banco en la rama que cuenta.
5. **Desbalance de personas grave.** El 100% del código del último mes lo escribió **Benjamin**. **Lucio (visión) commiteó 3 veces de código en toda la vida del repo**; **Laureano (firmware) no toca código desde el 14-mar**. El proyecto depende de una sola persona.
6. **Hay sobre-inversión en documentación y meta-trabajo.** De los 35 PRs del repo, la mayoría son `docs(...)`. Hay 7+ issues "META/ARRANQUE/TAREA-de-coach" (#102–#118) que son **gestión sobre el trabajo**, no el trabajo. El TDP es importante (vale puntos), pero hoy el embudo está tapado en review/merge, no en producción de documentos.

**Veredicto:** el equipo **identificó correctamente qué arreglar** (los issues son de altísima calidad y apuntan a lo que da puntos) pero **falla en EJECUTAR el cierre**: el código no llega a `main`, los tests no se documentan donde cuentan, y la carga recae en una persona. El riesgo número uno a Incheon **no es técnico, es de proceso de merge y de bus-factor.**

---

## 1. Metodología y datos duros

Todo lo que sigue sale de comandos sobre el repo local (no de impresiones):

| Métrica | Valor | Fuente |
|---|---|---|
| Commits totales (alcanzables) | 81 | `git rev-list --count HEAD` |
| Primer commit | 2026-02-22 | `git log --reverse` |
| Último commit (cualquier tipo) | 2026-05-18 | `git log -1` |
| **Último commit de código del robot en `main`** | **2026-05-10** (`cead75e`) | `git log -1 -- '*.cpp' '*.h'` y `'*.py'` |
| Issues abiertos | **51** | `gh issue list --state open` |
| Issues abiertos priority/high | **29** | `gh issue list --label priority/high` |
| Issues abiertos priority/medium | 16 | idem |
| Issues abiertos priority/low | 6 | idem |
| Issues cerrados | 18 | `gh issue list --state closed` |
| PRs abiertos | **9** (incl. #129, #100, #89, #80, #79, #42, #119, #1) | `gh pr list` |
| **PR #129 "Bugs prioritarios"** | **OPEN, +5707/−506, 39 files, 0 reviews, abierto 24-may** | `gh pr view 129` |
| TEST_LOG en `main`: entradas reales | **0** (solo `T-000` ejemplo) | lectura directa |
| TEST_LOG dentro de #129: entradas reales | 2 (`T-001`, `T-002`) | `git show origin/Bugs-Prioritarios:testing/TEST_LOG.md` |
| Binarios pesados commiteados | **207 MB** (`AI/` 151M + `Videos/` 56M), **sin Git LFS** | `du -sh`, `ls .gitattributes`→no existe |

### 1.1 Cadencia de commits — la foto que más asusta

Distribución de commits por día (rama principal):

```
2026-02-22..02-23   31 commits   ← arranque/migración (boom inicial)
2026-02-27..03-24   ~30 commits  ← desarrollo real firmware+visión (Feb–Mar)
2026-03-25..04-27    0 commits   ← ★ HUECO DE ~5 SEMANAS ★
2026-04-28..04-29    7 commits   ← 2 merges (TFLite #50, electrónica #43)
2026-04-30..05-08    0 commits   ← otro hueco
2026-05-09..05-11   ~14 commits  ← sprint de auditoría/docs del coach
2026-05-18           2 commits   ← fix de nombre (docs)
```

Hay **dos pozos de inactividad** (fines de marzo a fin de abril, y principios de mayo). La actividad de mayo es mayormente **del coach** (tooling de auditoría, docs de rúbricas, triage, TEST_LOG vacío) — no del robot. El único pulso de código del robot post-marzo es el PR #129… que sigue sin entrar.

---

## 2. ¿Trabajan en los temas CORRECTOS para maximizar puntaje en Incheon?

**Diagnóstico: SÍ en el "qué", con dos desvíos de prioridad.**

### 2.1 Lo que está bien priorizado (felicitar al equipo)

- Los issues #120–#128 (CORRECTITUD) atacan **bugs que cuestan puntos en pista directamente**: PID invertido (#121/B1), velocidad 55 en curva (#122/B5), salida anticipada del cuarto (#123/B6), doble-verde mal (#125/B8). Esto es exactamente lo que mueve la aguja del score de Rescue Line.
- Los issues #57–#113 (RESILIENCIA) atacan lo que impide **completar la corrida** (cuelgues, deadlocks, crash de cámara, sin auto-restart). Alineado con el objetivo declarado "auto-recuperación 8/10" (#114).
- El foco en `systemd`/auto-restart de `Main.py` (#108, incluido en #129) es **la mejor relación puntos/esfuerzo del proyecto**: si la RPi crashea y no revive, el robot queda ciego el resto de la corrida. Bien visto.

### 2.2 Desvío de prioridad #1 — el TDP se comió el sprint final de código

PR #129 mezcla **dos cosas que debieron ir separadas**: los fixes de firmware/RPi (drivebase.cpp, main.cpp, Main.py, systemd) **y** un TDP completo con ~20 diagramas, BOM, assets de imágenes, `code-reliability-evidence`, `roboflow-dataset-status`, etc. El propio cuerpo del PR lo dice: cierra/refiere a **~35 issues a la vez** (Closes #46/#57/#58/#59/#60/#61/#62/#64/#65/#66/#72/#74/#75/#76/#108/#112/#113/#124/#126 + Refs a otros 15).

**Problema estratégico:** un PR de 39 archivos que mezcla código crítico de robot con documentación es **imposible de revisar rápido y peligroso de mergear con confianza**. Por eso lleva 7 días parado. El TDP (que no corre en pista) está **bloqueando la entrada de los fixes que sí corren en pista**.

- **Riesgo de NO corregir:** los fixes B1/B5/B6/B8 + timeouts + systemd no llegan a `main` → el robot compite con los bugs vivos. Riesgo **alto**, impacto directo en score.
- **Riesgo de corregir (separar PRs):** costo de 1–2 h de Benjamin partiendo el branch; algún conflicto menor. Riesgo **bajo**.
- **Esfuerzo:** S (medio día de un alumno + coach revisando).

### 2.3 Desvío de prioridad #2 — el "Technical Challenges / SuperTeams" (#88, #81, #84) es ruido para Incheon

Hay issues de flexibilidad para Technical Challenges, boot-mode `--mode` (#81), stub Bluetooth para SuperTeam (#84). Son legítimos para un equipo maduro, pero **a 30 días, con el core sin estabilizar y un solo programador, esto es alcance que distrae**. El objetivo declarado del equipo (memoria del director) es **"podio + auto-recuperación 8/10"**, no ganar Technical Challenges en su primer mundial (estrategia Soccer/Incheon dice explícitamente "Incheon = aprender"). Postergar.

---

## 3. ¿Hacen cambios reales en los PROGRAMAS o se quedan en documentación/análisis?

**Diagnóstico: en `main`, hoy NO. El robot lleva 3 semanas sin cambios de código mergeados. El cambio real existe pero está represado en #129.**

### 3.1 La evidencia

Conteo de PRs por naturaleza (de los 35 totales):

- **Docs/análisis/meta puro:** la amplísima mayoría — #2/#3/#6/#8/#10/#12/#15/#16/#18/#20/#21/#22 (lote de auditoría inicial Feb), #56 (tooling), #78 (comms análisis), #79 (traducción), #80 (re-framing), #89 (flexibilidad), #90 (triage), #92 (rúbricas), #100 (skill coach), #101 (TEST_LOG vacío), #119 (fix de nombre).
- **Código real del robot mergeado:** un puñado — #34 (encoders atómicos), #35 (latencia IA), #36 (punteros), #37 (pinzas serial), #39 (upload), #43 (pines en main.cpp), #50 (TFLite). **Todos de febrero–abril.**
- **Código real del robot SIN mergear:** **#129** (el grande) y #42 (comentarios de Lucio, abierto desde 16-mar, +2654/−1557, **abandonado hace 2.5 meses**).

Traducido: **el repo produce documentación a buen ritmo y código a cuentagotas, y el poco código nuevo no cruza la línea de merge.** Es el patrón clásico de "analizamos mucho, mergeamos poco".

### 3.2 Confirmación a nivel de archivo (lo más importante)

Leí `drivebase.cpp` en la rama actual. El bug B1 sigue ahí, textual:

```cpp
// software/teensy/firmware/lib/drivebase/drivebase.cpp:50 (rama actual / main)
analogWrite(_pwmPin, (int)(255 - _pwmVal));
```

con `_motoPID` en modo DIRECT y la histéresis `if (_pwmVal < 10) _dir = !_dir;` intacta (ver detalle técnico en el informe hermano `teensy-01-drivebase-pid.md`, T-01). **El fix está dentro de #129 y NO en `main`.** Lo mismo aplica a `priority_fix_flags.h`: ese archivo **no existe en la rama actual** (`ls` → No such file), solo en #129. Es decir, **toda la estrategia de "fixes por flag" del equipo vive fuera de la rama de competencia.**

- **Riesgo de NO corregir:** se compite con el PID que satura en vez de regular (B1), velocidad mal en curva (B5), etc. **Pérdida de score garantizada.**
- **Riesgo de corregir (mergear #129):** introducir regresión no testeada en banco. Mitigable: #129 trae flags para activar/desactivar fixes (`priority_fix_flags.h`) y los autores ya dejaron por escrito qué fixes desactivaron por comportamiento observado (#63, #110, #122, #123, #125). El riesgo es **medio** y **gestionable** si se mergea y se prueba en banco YA.
- **Esfuerzo:** review serio de #129 = 3–5 h de coach + sesión de banco. **Es la tarea #1 del proyecto.**

---

## 4. ¿Documentan los TESTEOS? (¿TEST_LOG tiene entradas reales?)

**Diagnóstico: en `main`, NO (cero tests reales). En #129, recién empezaron (2 entradas). El proceso existe en papel pero todavía no es hábito.**

### 4.1 Estado del TEST_LOG en la rama que cuenta (`main`/actual)

`testing/TEST_LOG.md` tiene **solo el ejemplo didáctico `T-000`** (marcado "Este NO es un test real"). Las cuatro tablas índice (`[MECH]`, `[ELEC]`, `[SW]`, `[PERF]`) están **vacías** ("_(vacío — próximos tests acá)_"). La regla de oro #3 del `CLAUDE.md` dice "antes de mergear un fix de firmware, probar en banco; resultado en TEST_LOG.md". **Esa regla se está incumpliendo**: se mergearon fixes (timeouts, claw) sin entrada de banco.

### 4.2 Lo bueno: dentro de #129 sí hay testeo real y honesto

Hay que reconocerlo — la rama `Bugs-Prioritarios` trae **testeo de verdad y bien hecho**:

- `T-001` (2026-05-23, `[MECH][ELEC][PERF]`): medición física inicial — batería 12.6V→10.5V en 1h, error de `runDistance()` ~1–2 cm, etc.
- `T-002` (2026-05-23, `[SW][PERF]`): **FPS real medido = 91.33 FPS** en line-following 30s desde el service real, transiciones de estado desde systemd.
- `MEDICIONES_PENDIENTES.md`: lista honesta de lo que **falta** medir con el robot (voltaje bajo carga extrema, precisión de `runAngle()`), con instrucciones. Esto es **excelente práctica de equipo**.
- `TEST_LOG_AUTO.md`: métricas auto-extraídas del código por IA (Codex), **correctamente rotuladas** como "values need field validation before TDP submission" y "does not contain measured competition performance". Honesto: no se vende constante de código como si fuera medición.

### 4.3 El problema de fondo

Todo ese testeo real **está represado en #129 sin mergear**. Mientras tanto, la rama de competencia muestra cero evidencia. Para el TDP (la rúbrica premia "Performance evaluation", "Software/Mechanical/Electronic reliability" con evidencia citable — 4×6 pts según el propio índice del TEST_LOG), tener la bitácora vacía en `main` es **dejar ~24 pts del TDP sin respaldo visible**. El issue #93 (inicializar TEST_LOG) se cerró, pero **inicializar la plantilla no es lo mismo que llenarla**: hoy está inicializada y vacía.

- **Riesgo de NO corregir:** TDP sin evidencia de tests = pierde puntos de rúbrica; y peor, **se compite a ciegas** (sin banco no se sabe si los fixes andan). Riesgo **alto**.
- **Riesgo de corregir:** ninguno real; documentar tests solo cuesta disciplina.
- **Esfuerzo:** continuo, bajo por sesión. La clave es **mergear #129 para que T-001/T-002 lleguen a `main`** y seguir agregando T-003+.

---

## 5. ¿El RITMO actual alcanza para llegar listos?

**Diagnóstico: NO al ritmo actual. El cuello de botella no es la velocidad de tipear código, es la velocidad de REVISAR y MERGEAR — y eso hoy es prácticamente cero.**

### 5.1 La cuenta cruda

- **30 días** al inicio de Incheon (menos en la práctica: hay que congelar, viajar, armar logística → realista **~3 semanas hábiles de banco**).
- **29 issues priority/high abiertos.** Aunque #129 cierra ~20 de un saque al mergear, quedan resilientes nuevos (#109 BNO055 sin re-init, #111 respawn de thread, #113 lock de camthreader pendiente parcial) + correctitud no resuelta (#122/#123/#125 que los autores **decidieron NO tocar**, lo cual es legítimo pero hay que validar en banco que la decisión es correcta).
- **Velocidad de merge de código observada en mayo: ~0 PRs de código mergeados.** El último merge de código fue #50 (TFLite) el **29-abril**. A esa tasa, no se cierra el backlog crítico.

### 5.2 El verdadero limitante: bus-factor + review

El proyecto avanza tan rápido como **una sola persona (Benjamin) pueda escribir Y como el coach pueda revisar.** Con un único productor de código y reviews que tardan 7+ días (#129), el throughput es estructuralmente insuficiente. **No es un problema de "trabajen más horas"; es un problema de que el pipeline tiene un solo carril y un peaje cerrado.**

- **Riesgo de NO corregir:** se llega a Incheon con #129 a medio revisar, mergeado a las apuradas la última semana, **sin tiempo de banco para validar regresiones** → el peor escenario (robot inestable y sin red de testeo).
- **Riesgo de corregir (forzar cadencia de merge + sumar manos):** meter presión sobre Lucio/Laureano para que retomen código puede generar fricción o commits de baja calidad si no se los acompaña. Mitigable con pairing.
- **Esfuerzo:** organizacional, M.

---

## 6. ¿Hay desbalance entre subsistemas (y entre personas)?

**Diagnóstico: SÍ, en dos ejes. El desbalance de PERSONAS es más grave que el de subsistemas.**

### 6.1 Desbalance de personas (crítico)

Commits que tocan código del robot (`.py`/`.cpp`/`.h`, excluyendo traducciones/migración), por autor:

| Autor | Commits de código | Rol asignado | Última actividad de código |
|---|---:|---|---|
| **Benjamin Villagran** | **19 (+3)** | RPi + hardware + banco | **24-may** (en #129) |
| Laureano Monteros | 9 | **Firmware Teensy (owner)** | **14-mar** (¡hace 2.5 meses!) |
| Lucio Saucedo | 3 | **RPi visión (owner)** | 14-mar (y PR #42 abandonado) |
| Enzo Juarez (coach) | 3 | Coach (merges) | abr |

**Esto es una bandera roja de dirección.** Los dos "dueños" nominales de subsistema (Laureano/firmware, Lucio/visión) **no están escribiendo el código de sus propios subsistemas**. Benjamin está cubriendo firmware, visión, hardware, banco, TDP y systemd — **es un punto único de falla total**. Si Benjamin se enferma la semana del mundial, el proyecto se detiene. Lucio, dueño de visión, tiene **3 commits de código en toda la historia del repo** y un PR (#42) abandonado desde marzo.

- **Riesgo de NO corregir:** bus-factor = 1. Además, Laureano y Lucio **llegan al mundial sin haber tocado el código que tendrán que debuggear en vivo en el pit** — no van a poder asistir bajo presión. Riesgo **muy alto** (operativo y educativo).
- **Riesgo de corregir:** repartir trabajo ahora baja la velocidad de Benjamin a corto plazo. Vale la pena.
- **Esfuerzo:** M, sostenido.

### 6.2 Desbalance de subsistemas (moderado)

- **Visión (RPi):** la más madura en features (TFLite, NCNN, AGCWD/Zero-DCE, autobalance de blancos, 91 FPS medidos). Bien.
- **Firmware (Teensy):** **estancado**. Sin cambios desde el sprint de timeouts (revertidos parcialmente, ver #105) y claw del 10-may. Los bugs P0 de control (B1 PID, B5 velocidad, rescate #57) son los de mayor impacto en score y **no están resueltos en `main`**. El subsistema que más puntos puede ganar/perder es el menos atendido las últimas semanas.
- **Comms (serial):** **deuda explícita y sin cerrar.** No hay heartbeat, no hay handshake al boot, lecturas sin timeout robusto (issues #70–#76, #72, #73, #112). Verifiqué: **no hay heartbeat/handshake/WDT en el código de producción** (única coincidencia de `grep` es un comentario en `Main.py:823`). Las auditorías RESILIENCIA #53/#27 siguen **abiertas**. Es el subsistema más frágil ante un reset del Teensy en pista.
- **Resiliencia transversal:** auto-restart (systemd) viene en #129 — bien — pero el resto (re-init de BNO055 #109, respawn de infer_thread #111, lock de camthreader #113) queda parcial.

### 6.3 Higiene del repo (deuda que ya pesa)

- **207 MB de binarios commiteados** (`AI/` 151 MB de modelos `.onnx/.pt/.tflite/.zip` + `Videos/` 56 MB) **sin Git LFS** (`.gitattributes` no existe). Issue #69 abierto desde el 10-may, sin resolver. Esto hace el repo lento de clonar y es un riesgo si alguien tiene que clonar limpio en el pit con internet de hotel coreano.
- **`AUDIT-ACTION-PLAN.md` está obsoleto:** última modificación **23-feb**. El `CLAUDE.md` lo llama "lista maestra curada de bugs" y dice "antes de abrir un finding nuevo verificá que no esté ahí" — pero lleva 3 meses sin tocarse mientras se abrían 50+ issues. La fuente de verdad declarada está muerta; la verdad real vive en los issues. **Desalinear el proceso documentado del proceso real genera confusión.**
- **9 PRs abiertos** simultáneos (varios del coach: #80, #89, #100; uno auto-traducción #79; uno abandonado #42). PRs abiertos colgando = ruido y conflictos latentes.

---

## 7. Riesgos estratégicos priorizados

| # | Riesgo | Prob. | Impacto | Severidad |
|---|---|---|---|---|
| RE-1 | **#129 no se mergea (o se mergea sin banco la última semana)** → robot compite con B1/B5/B6/B8 vivos | Alta | Alto | **P0** |
| RE-2 | **Bus-factor = 1 (Benjamin)** → si falla, el proyecto se detiene; Laureano/Lucio no pueden asistir en el pit | Media | Muy alto | **P0** |
| RE-3 | **TEST_LOG vacío en `main`** → se compite sin validación de banco y el TDP pierde evidencia (~24 pts) | Alta | Medio-Alto | **P1** |
| RE-4 | **Comms sin heartbeat/handshake** (#53/#72/#73/#112) → un reset del Teensy en pista deja el robot inerte | Media | Alto | **P1** |
| RE-5 | **Scope creep** (TDP+Technical Challenges+SuperTeam) compite por las pocas horas de la persona-cuello | Media | Medio | **P1** |
| RE-6 | **Ritmo de merge ~0 en mayo** → backlog de 29 P0/P1 no cierra a tiempo | Alta | Alto | **P1** |
| RE-7 | **207 MB sin LFS + AUDIT-ACTION-PLAN obsoleto** → fricción operativa y proceso desalineado | Media | Bajo-Medio | **P2** |

---

## 8. Correcciones de rumbo concretas (lo que pediste: 3–5 acciones)

### Corrección 1 — DESBLOQUEAR Y PARTIR #129 esta semana (lo más urgente del proyecto)
**Acción:** el coach (Enzo) y el director hacen review de #129 **en las próximas 48 h**. Para que sea revisable, pedirle a Benjamin que lo **parta en dos**: (a) PR-código (drivebase.cpp, main.cpp, Main.py, camthreader.py, systemd, priority_fix_flags.h, test/evacuation.cpp) → mergear **primero**, con sesión de banco; (b) PR-TDP (docs/tdp/*, assets) → mergear después, sin presión de pista. **Mientras #129 esté abierto, el robot de competencia NO tiene los fixes.**
- *Riesgo de no hacerlo:* se compite con los bugs vivos. *Esfuerzo:* medio día Benjamin + 3–5 h review. *Métrica de éxito:* PR-código mergeado a `main` antes del 2026-06-05, con T-003 en TEST_LOG documentando la corrida de validación.

### Corrección 2 — ROMPER EL BUS-FACTOR: reactivar a Laureano (firmware) y Lucio (visión) en CÓDIGO YA
**Acción:** asignar dueños reales y exigir **commits de código de cada uno esta semana**, no análisis. Laureano: tomar los fixes de control que #129 dejó **sin tocar** (#122 velocidad en curva, #125 doble-verde, validar en banco la decisión de "no cambiar") — su issue de arranque #115 ya existe, **que lo ejecute en código**. Lucio: tomar #110 (cx_black) y #111 (respawn infer_thread) — su #116 ya existe. Hacer **pairing** Benjamin↔Lucio/Laureano para transferir conocimiento antes del pit.
- *Riesgo de no hacerlo:* Benjamin colapsa y los otros dos no pueden asistir en vivo. *Esfuerzo:* M sostenido. *Métrica:* ≥3 commits de código de Laureano y ≥3 de Lucio mergeados antes del 2026-06-10.

### Corrección 3 — CONVERTIR EL TEST_LOG EN HÁBITO DE BANCO (no en documento muerto)
**Acción:** hacer cumplir la regla de oro #3 del `CLAUDE.md` **literalmente**: ningún fix de firmware/visión se mergea sin su entrada `T-XXX` en `testing/TEST_LOG.md` de `main`. Agendar **2 sesiones de banco/semana** fijas hasta el congelamiento, cada una produce ≥1 entrada. Cerrar primero las `MEDICIONES_PENDIENTES.md` (voltaje bajo carga extrema, `runAngle()`), porque alimentan el TDP. **Mergear #129 lleva T-001/T-002 a `main` y arranca la bitácora de verdad.**
- *Riesgo de no hacerlo:* TDP sin evidencia + competir a ciegas. *Esfuerzo:* bajo por sesión, alto en disciplina. *Métrica:* ≥6 entradas reales en TEST_LOG de `main` antes del mundial.

### Corrección 4 — RECORTAR ALCANCE: congelar todo lo que no sea "core robot + TDP base"
**Acción:** mover a "post-mundial" explícitamente los issues #88 (Technical Challenges fases), #81 (boot-mode), #84 (Bluetooth SuperTeam), #82/#83/#87 (refactors de mantenibilidad). Cerrar o etiquetar `post-incheon`. El objetivo declarado es **podio + 8/10 recuperación + aprender**, no ganar challenges en el primer mundial (coherente con la estrategia "Incheon = aprender"). Cada hora gastada en flexibilidad de challenges es una hora no gastada en estabilizar el PID.
- *Riesgo de no hacerlo:* dispersión de la única persona-cuello. *Esfuerzo:* 1 h de triage. *Métrica:* backlog priority/high baja de 29 a <12 (cerrando lo de #129 + posponiendo scope).

### Corrección 5 — FIJAR UN CONGELAMIENTO Y UNA CADENCIA DE MERGE
**Acción:** declarar **feature freeze el 2026-06-15** (15 días de margen para banco + viaje). Hasta ahí, **cadencia de merge obligatoria: revisar y mergear PRs en ≤48 h** (no 7 días como #129). Post-freeze: solo fixes P0 verificados en banco. Además, higiene: cerrar/mergear los 9 PRs colgados (consolidar #80/#89/#100 o cerrarlos), y **migrar binarios a LFS (#69)** antes de que alguien tenga que clonar limpio en Corea.
- *Riesgo de no hacerlo:* fixes entran la última semana sin tiempo de validar; repo de 207 MB intransportable. *Esfuerzo:* M. *Métrica:* 0 PRs de código con >48 h sin review a partir de hoy; freeze respetado.

---

## 9. Lo que el equipo está haciendo BIEN (para no desmoralizar)

En tono de dirección honesta, también hay que decir lo positivo, porque es real:

- **La calidad del análisis de bugs es de nivel mundial.** Los issues #57–#128 están mejor documentados (causa, repro, fix, riesgo) que los de muchos equipos seniors. El equipo **sabe exactamente qué está mal**.
- **El testeo que SÍ hicieron (T-001/T-002) es honesto y riguroso** — midieron FPS real (91.33), curva de batería real, error de odometría real, y separaron limpiamente "métrica de código" de "métrica medida". Eso es madurez de ingeniería.
- **La decisión de NO tocar ciertos bugs** (#122, #123, #125) porque "el comportamiento observado compensa" es **criterio de competencia correcto** — no rompieron lo que anda. Solo falta **documentar en banco** que esa decisión es la buena.
- **El foco en systemd/auto-restart** demuestra que entendieron que en Rescue Line "terminar la corrida" vale más que "correr rápido".

El problema **no es de talento ni de criterio técnico. Es de EJECUCIÓN del cierre: mergear, repartir y documentar en la rama que cuenta.** A 30 días, eso es 100% recuperable si se actúa esta semana sobre #129 y el bus-factor.

---

## 10. Cierre

El equipo identificó el blanco correcto y le apuntó bien, pero **la bala está atascada en la recámara (#129) y la maneja un solo tirador (Benjamin)**. Las tres palancas de dirección, en orden: **(1) mergear el código de #129 con banco esta semana**, **(2) poner a Laureano y Lucio a escribir código de sus subsistemas YA**, **(3) hacer del TEST_LOG un hábito en `main`**. Si esas tres se mueven en los próximos 7 días, el objetivo "podio + 8/10" es alcanzable. Si #129 sigue abierto el 2026-06-10, el riesgo de llegar a Incheon con un robot no validado es alto.

---

*Informes hermanos de esta auditoría (citados, no duplicados):* `teensy-01-drivebase-pid.md` (T-01 PID/B1), `teensy-04-rescate-fsm.md`, `rpi-01-vision.md`, `rpi-03-comms-threading.md`, `comms-01-protocolo-integral.md`, `doc-01-tdp.md`, `equipo-01-laureano.md`, `equipo-02-lucio.md`.
*Auditorías previas citadas:* RESILIENCIA (#53/#27/#57–#119), CORRECTITUD (#120–#128, bugs B1–B10).
