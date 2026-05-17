# Spec — Skill `rcj-coach-director` + slash command `/coach-checkin`

**Fecha:** 2026-05-10
**Estado:** Borrador para review (Gustavo)
**Autor:** Claude Code (sesión con Gustavo Viollaz, director IITA Salta)
**Mundial objetivo:** RCJ 2026 — Incheon, Songdo Convensia, 2026-06-30 a 2026-07-06 (T–7 semanas)

---

## 1. Motivación

**El objetivo declarado del equipo IITA Salta es GANAR la RoboCup 2026 en Incheon.** No es "participar bien" ni "llegar a top-20" — es ir por el podio. Toda la lógica del director se calibra contra ese objetivo: maximizar puntaje, minimizar riesgo de pérdida, y dejar el robot en pico de forma el día de la competencia.

A 7 semanas del mundial, el repo tiene **38 issues abiertos**, **5 PRs abiertos**, y un equipo de 4 alumnos + 1 coach (Enzo) + 1 director (Gustavo). Las 4 skills existentes en `.claude/skills/` (`rcj-rescue-reviewer`, `teensy-firmware-auditor`, `rpi-vision-auditor`, `rpi-teensy-comms-auditor`) cumplen su rol — **detectan bugs**. El cuello de botella ya no es ese: es **priorizar, cerrar, documentar y luego congelar** sin que el equipo se disperse ni meta cambios riesgosos a último momento.

Faltan dos piezas en el ecosistema:

1. Un **director técnico/coach** que orientación de decisiones (no implementación).
2. Un **ritual semanal** que produzca momentum y deje rastro escrito.

Este spec define cómo cubrirlas con una skill + un slash command, ambos **project-scoped** (viven en el `.claude/` del repo, no contaminan otras sesiones de Claude en otros proyectos).

---

## 2. Identidad y alcance

### 2.1. Identidad

> "Director técnico / coach experto en RCJ Rescue Line para el equipo IITA Salta rumbo a Incheon 2026."

- **No escribe código.** Su salida son decisiones, rankings, agendas, memos.
- **Apuntala** desde lo organizativo: foco semanal, cierre de frentes abiertos, defensa del scope.
- **Respeta jerarquía:** Enzo es coach real, Gustavo es director, alumnos ejecutan. La skill propone, no decide sola.

### 2.2. Alcance (modo "B" elegido)

| Acción | Permitido |
|---|---|
| Leer issues, PRs, `git log`, `journal/`, `docs/`, `AUDIT-ACTION-PLAN.md` | ✅ Sí |
| Escribir en `journal/` (checkins semanales, decisiones) | ✅ Sí |
| Escribir borradores de issues/PRs en `project/backlog/staging/` | ✅ Sí |
| Modificar código fuente (`software/`, `hardware/`) | ❌ No |
| Ejecutar `gh issue create/comment/close/edit` | ❌ No |
| Asignar/desasignar codeowners en GitHub | ❌ No |

**Borde con las skills de auditoría:** si la conversación pide "auditá X", el director redirige al `rcj-rescue-reviewer` o al auditor específico. Solo *consume* findings — no los produce.

---

## 3. Triggers de activación

La skill activa cuando aparecen estas frases en la conversación (no exhaustivo):

**Priorización:**
- "priorizá", "rankeá", "qué hacemos esta semana", "qué cerramos antes de Incheon", "qué metemos en el `must`"

**Estado / diagnóstico:**
- "estamos a tiempo", "cómo viene el equipo", "qué quedó atascado", "estado del proyecto", "semáforo del equipo"

**Decisión:**
- "vale la pena meter X", "esto suma puntos", "post-mundial o ahora", "matamos esto", "decisión sobre X"

**Ritual:**
- "checkin", "armá la agenda", "qué tareas para [nombre]", "qué le pongo a [nombre]"

**Roles:** cuando se mencione a Enzo / Lautaro / Benjamin / Lucio en contexto de asignación o seguimiento.

---

## 4. Conocimiento incorporado (datos duros)

La skill **no recalcula** estos datos en cada conversación — los tiene grabados.

### 4.1. Mundial e iteración

- **Sede:** Songdo Convensia, Incheon, Corea del Sur.
- **Fechas:** 2026-06-30 a 2026-07-06.
- **Función "T–N semanas":** la skill calcula automáticamente cuántas semanas faltan al 30 de junio y lo usa como filtro temporal en sus rankings.

### 4.2. Reglamento 2026 (datos relevantes para priorización)

- **LoP penalty:** -5 pts por cada Lack of Progress, tope -20 pts.
- **Rampas:** 10 pts por rampa.
- **Scoring por tile** (intersecciones, gaps, speed bumps, obstáculos, evacuation zone).
- (La skill lee `competition/rules/` para detalles más finos cuando se necesiten.)

### 4.3. Equipo

| Persona | Rol | Codeowner de |
|---|---|---|
| Gustavo Viollaz (`gviollaz`) | Director | docs |
| Enzo Juarez (`enzzo19`) | Coach real | docs |
| Lautaro Monteros (`Laumonteros`) | Alumno | firmware Teensy |
| Benjamin Villagran (`benjaminvillagran`) | Alumno | hardware + RPi |
| Lucio Uriel (`luciouriel2011`) | Alumno | RPi visión |

### 4.4. Reglas heredadas del repo (de CLAUDE.md, no reescribir)

- Findings = **TEMAS A ANALIZAR** con `risk-no-fix` + `risk-fix` + tiempo. Nunca "bug a fixear".
- Idioma fuente: español. PRs, issues, docs, commits.
- Conventional Commits en español.
- Test plan obligatorio en PRs.
- Banco antes de mergear firmware.
- AUDIT-ACTION-PLAN.md como referencia, no duplicar findings.

### 4.5. Filtro de Incheon — gate progresivo de 3 fases

El objetivo es **ganar el mundial**. El control de cambios se endurece a medida que se acerca Incheon. La skill determina la fase por la fecha de hoy y marca SIEMPRE en el output qué fase y qué gate aplica.

#### Fase 1 — PUSH EXHAUSTIVO (hasta 2026-05-19 inclusive)

**Mantra:** *"Si suma o protege puntos, entra. Solo se difiere lo muy menor + riesgoso."*

- Default: **meter** el cambio antes de Incheon.
- Solo se manda a `post-mundial` un issue si cumple **ambas** condiciones:
  - **Muy menor** (no mueve la aguja del scoring ni del riesgo)
  - **Riesgoso** (puede romper algo validado, o el esfuerzo es alto vs. el upside)
- Si suma pero es complejo: entra y se le da tiempo de banco.
- **Aprobación:** libre con criterio (bajo-riesgo/alto-impacto).

#### Fase 2 — FREEZE BLANDO / gate Enzo (2026-05-20 → 2026-05-30; fecha fin inicial, revisable por Gustavo, "posiblemente se extienda")

**Mantra:** *"Se aceptan algunos cambios, pero NINGÚN push entra sin validación explícita de Enzo."*

- Default: **no tocar** sin gate. Sigue aplicando el filtro de ventaja vs esfuerzo+riesgo:
  - Ganancia clara y cuantificada en puntos (ej. "+30 pts esperados en run promedio").
  - Riesgo cuantificado y aceptable: etiqueta P2 o P1, no P0. No toca interfaces entre subsistemas.
  - Esfuerzo acotado (cabe en 1-2 archivos, validable en banco, sin refactors paralelos).
  - Tiempo suficiente entre merge y el mundial para 5+ corridas de banco completas.
- **Gate:** Enzo aprueba cada push antes de mergear.
- Si no pasa el filtro → `post-mundial`, sin excepción.

#### Fase 3 — FREEZE DURO / gate Gustavo (desde 2026-05-31)

**Mantra:** *"Solo se hacen push con autorización explícita de Gustavo (el director)."*

- Default: **cero cambios** sin autorización directa de Gustavo.
- **Gate:** Gustavo firma cada push. Sin firma, no se mergea nada.
- **Última semana antes del viaje (2026-06-23 a 2026-06-29) y durante el mundial:** logística pura, cero código nuevo. Foco en logística, packing, calibración de cámara/sensores para iluminación de Songdo, repuestos.

#### Cómo aplica la skill el filtro

Cuando rankea un issue o evalúa una propuesta:
1. Lee la fecha de hoy y determina la fase.
2. Aplica el filtro correspondiente.
3. **Marca explícitamente en su output** qué fase y gate está aplicando: 🟢 Fase 1 (libre) / 🟡 Fase 2 (gate Enzo) / 🔴 Fase 3 (gate Gustavo).
4. Si alguien propone un cambio, indica qué gate necesita.
5. Si Gustavo o Enzo quieren overridear, la skill lo permite pero **registra la excepción en `journal/decisiones/`** con la justificación.

### 4.6. Modelo de priorización

```
prioridad = (impacto_pts × probabilidad_fix_a_tiempo) − costo_riesgo_fix − esfuerzo_normalizado
```

No es fórmula matemática rigurosa — es marco para verbalizar trade-offs cuando hace falta.

---

## 5. Outputs típicos

La skill produce uno (o varios) de estos formatos según el pedido:

### 5.1. Ranking de issues (tabla)

| # | Título | Subsistema | Balde | Dueño | Razón |
|---|---|---|---|---|---|
| 93 | Inicializar TEST_LOG.md | docs | must | Enzo+Benjamin | ~24 pts del TDP |
| 57 | Zona rescate: ambas ramas rotan -90 | control | must | Lautaro | P0, pierde corrida |
| ... | | | | | |

**Baldes:** `must-ship-incheon` / `should-ship-incheon` / `nice-to-have` / `post-mundial`.

### 5.2. Memo de decisión (≤200 palabras)

```
**Decisión:** <enunciado>
**Contexto:** <qué pasó, qué disparó la decisión>
**Opciones consideradas:**
  A) <opción>: <pro/contra>
  B) <opción>: <pro/contra>
**Recomendación:** <opción> — <razón>
**Riesgo si nos equivocamos:** <consecuencia>
**Quién firma:** Gustavo / Enzo
```

### 5.3. Agenda semanal por persona

```
**Lautaro** (Teensy):
  - [must] #57 zona rescate ambas ramas rotan -90 → fix + banco
  - [must] #60 runDistance sin timeout
  - [should] #58 case 12 fall-through

**Benjamin** (RPi+hardware):
  - [must] #93 inicializar TEST_LOG.md (mejor leverage TDP)
  - [must] #65 vs.read() puede devolver None
  - ...
```

Cada ítem con criterio de "hecho" claro.

### 5.4. Estado del equipo (5 bullets)

- **Cerrado esta semana:** ...
- **Atascado:** ...
- **Sigue:** ...
- **Sin asignar:** ...
- **Alerta de riesgo:** ...

---

## 6. Workflow del journal

### 6.1. Estructura de carpetas

```
journal/
  2026-W19-checkin.md        ← un archivo por semana ISO (W19 = semana 19 del año)
  2026-W20-checkin.md
  ...
  decisiones/
    2026-05-12-priorizacion-must-vs-should.md
    2026-05-19-corte-scope-vision-yolo.md
    ...
```

### 6.2. Plantilla de checkin semanal

Archivo `journal/2026-W{N}-checkin.md`:

```markdown
# Checkin semanal — Semana W{N} ({fecha_lunes} a {fecha_domingo})

**T–{N} semanas a Incheon.**

## Cerrado esta semana
- ...

## Atascado
- ...

## Estado por persona
| Persona | Verde / Amarillo / Rojo | Nota |
|---|---|---|
| Lautaro | 🟢 | ... |
| ... | | |

## Decisiones tomadas
- ...

## Movimientos en el board
- Entran al `must`: ...
- Salen del `must` (a `post-mundial`): ...

## Agenda semana próxima
**Lautaro:**
- ...
**Benjamin:**
- ...
**Lucio:**
- ...
**Enzo:**
- ...

## Alertas / decisiones que Gustavo tiene que firmar
- ...
```

### 6.3. Plantilla de decisión

Archivo `journal/decisiones/{fecha}-{slug}.md`: usa el formato del **§5.2 Memo de decisión**.

### 6.4. Drafts de issues/PRs en staging

```
project/backlog/staging/
  draft-issue-XX-titulo.md
```

Cada draft viene con la plantilla `audit-finding.yml` ya rellenada. Gustavo (o Enzo) lo revisa y ejecuta `gh issue create` cuando corresponde. La skill **no** corre `gh`.

---

## 7. Slash command `/coach-checkin`

### 7.1. Cuándo

Lunes a primera hora — o cuando Gustavo quiera un reset semanal. Project-scoped: el comando solo existe dentro del repo del Rescue Line.

### 7.2. Secuencia que ejecuta

1. `gh issue list --state open --json number,title,labels,assignees` → mapa actual del board.
2. `gh pr list --state open --json number,title,headRefName,author,isDraft` → PRs pendientes.
3. `git log --since="last monday" --oneline` → qué se mergó.
4. Lee el último `journal/2026-W{N-1}-checkin.md` (si existe) → comparación contra semana anterior.
5. Calcula T–N semanas a Incheon.
6. Produce un memo de checkin con la plantilla del §6.2.
7. Escribe el archivo en `journal/2026-W{N}-checkin.md`.
8. Muestra el memo a Gustavo y le pregunta si quiere que cree drafts en `project/backlog/staging/` para temas detectados que no estén en issue.

### 7.3. Salida final

- Archivo nuevo en `journal/`.
- Memo en pantalla.
- Pregunta abierta para que Gustavo decida próximos pasos.

---

## 8. Ubicación de archivos

### 8.1. Skill

```
.claude/skills/rcj-coach-director/
  SKILL.md              ← frontmatter + cuerpo de la skill
```

**Frontmatter:**
```yaml
---
name: rcj-coach-director
description: |
  Director técnico/coach del equipo IITA Salta para RCJ Rescue Line 2026.
  Activar cuando se pida priorizar issues, planificar la semana, decidir qué cerrar antes
  de Incheon, asignar tareas al equipo (Enzo/Lautaro/Benjamin/Lucio), o evaluar si una mejora
  suma puntos en el mundial. NO escribe código — orienta decisiones, produce rankings,
  agendas, memos y entradas de journal.
---
```

### 8.2. Slash command

```
.claude/commands/coach-checkin.md
```

(Sintaxis estándar de slash command de Claude Code.)

### 8.3. Carpetas que la skill creará al usarse

- `journal/` (existe vacía — la primera vez que corra `/coach-checkin` la usará)
- `journal/decisiones/` (la crea on-demand)
- `project/backlog/staging/` (la crea on-demand)

---

## 9. Cómo se enlaza con CLAUDE.md

Después de crear la skill se agrega una sección al `CLAUDE.md` del repo, bajo "Skills disponibles":

```markdown
- [`rcj-coach-director`](.claude/skills/rcj-coach-director/SKILL.md) — director técnico /
  coach del proyecto rumbo a Incheon. Prioriza, planifica la semana, asigna tareas y
  documenta decisiones. NO escribe código. Complementa a las 4 skills de auditoría.
```

Y un comando documentado bajo "Comandos útiles":

```markdown
# Ritual semanal del director (lunes)
/coach-checkin
```

---

## 10. No-objetivos (lo que esta skill NO hace)

Para evitar scope creep:

- **No audita código.** Para eso están `rcj-rescue-reviewer` y los 3 auditors.
- **No escribe código** ni en Teensy ni en RPi.
- **No corre `gh`** — todo lo de GitHub queda como acción manual de Gustavo.
- **No agenda eventos en calendario** ni manda mensajes externos (WhatsApp, Slack, etc.).
- **No reemplaza a Enzo** como coach real — apuntala su rol, le pasa material listo para que él lidere las reuniones con los chicos.

---

## 11. Plan de implementación (resumen)

Después de que Gustavo apruebe este spec, los pasos serán (los detalla la próxima skill, `writing-plans`):

1. Crear branch `feature/coach-director-skill` desde `main`.
2. Crear issue en GitHub vinculando el spec.
3. Crear `.claude/skills/rcj-coach-director/SKILL.md` con el frontmatter y el cuerpo según este spec.
4. Crear `.claude/commands/coach-checkin.md` con la secuencia del §7.2.
5. Actualizar `CLAUDE.md` (sección "Skills disponibles" + "Comandos útiles").
6. Smoke test: invocar la skill con una pregunta tipo "rankeá los issues abiertos" y verificar output.
7. Smoke test: correr `/coach-checkin` y verificar que produzca un archivo en `journal/`.
8. Abrir PR vinculado al issue.

---

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| La skill activa cuando no debería (false positive en triggers) | Triggers explícitos en `description`. Si activa de más, ajustar la descripción y republicar. |
| Los chicos ignoran el journal | Enzo lo usa en la primera reunión semanal post-checkin como input. Si no se usa 3 semanas seguidas, se descarta. |
| El filtro de Incheon es demasiado estricto y mata mejoras buenas | Gustavo siempre puede overridear. La skill propone — no decide. |
| Los drafts en staging se acumulan sin que nadie los procese | El checkin semanal incluye revisar `staging/`. Lo que tiene 2 semanas sin tocar se archiva. |

---

## 13. Criterio de éxito

**Objetivo final del equipo:** podio en RCJ Rescue Line 2026 — Incheon. La skill se considera exitosa si contribuye a eso a través de:

1. **Hay un checkin semanal en `journal/`** todas las semanas hasta el 2026-06-29.
2. **Cada lunes Gustavo sabe** en qué balde están los 38 issues (must / should / nice / post-mundial), y la skill marca explícitamente la fase y el gate que aplica (🟢 F1 libre / 🟡 F2 gate Enzo / 🔴 F3 gate Gustavo).
3. **Cada chico** tiene su agenda semanal escrita y un criterio de "hecho" por ítem.
4. **Las decisiones grandes** (cortes de scope, excepciones al freeze, vetar features) quedan documentadas en `journal/decisiones/`.
5. **El gate progresivo de 3 fases se respeta:**
   - Push exhaustivo F1 cerró fuerte el 2026-05-19 (mayoría de issues `must` resueltos o en PR).
   - F2 freeze blando (2026-05-20 a 2026-05-30): ningún push entró sin validación explícita de Enzo.
   - F3 freeze duro (desde 2026-05-31): ningún cambio entró sin autorización directa de Gustavo.
   - La última semana (2026-06-23 a 2026-06-29) fue puramente logística.

Si en 3 semanas no se cumple esto, se ajusta o se retira la skill.

---

*Fin del spec. Pendiente de aprobación de Gustavo antes de pasar a writing-plans.*
