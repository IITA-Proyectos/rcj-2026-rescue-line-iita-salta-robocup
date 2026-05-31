---
description: Ritual semanal del director — produce un memo de checkin en journal/2026-W{N}-checkin.md leyendo issues, PRs y git log
---

# /coach-checkin — Ritual semanal del director

Ejecutás el ritual semanal de seguimiento del proyecto IITA Salta para RoboCup Junior Rescue Line 2026 — Incheon. **Activá la skill `rcj-coach-director` antes** y aplicá su contexto (gate progresivo con track dual por subsistema, filtros, equipo).

> **El estado y régimen vigente del proyecto vive en `docs/es/ESTADO-ACTUAL-2026-05-31.md` — consultalo al inicio de cada sesión.**

## Secuencia (8 pasos)

### 1. Calcular T–N a Incheon y determinar track + fase por subsistema

- Fecha objetivo: **2026-06-30** (apertura del mundial). Calculá semanas y días restantes.
- Para cada issue/cambio, mirá su label `subsystem/*` → **Track A** (`control`, `comms`, `power`/firmware) o **Track B** (`vision`, `docs`).
- **Track A — firmware/control + comms:**
  - Ventana de push libre **VENCIDA** → 🟡 gate Enzo (todo cambio de firmware/comms entra con su validación explícita).
  - ≥ 2026-06-15 (freeze de código) → 🔴 gate Gustavo.
- **Track B — docs + visión (RPi):**
  - ≤ 2026-06-11 → 🟢 push libre con criterio
  - 2026-06-12 → 2026-06-14 → 🟡 gate Enzo
  - ≥ 2026-06-15 (freeze de código) → 🔴 gate Gustavo
- **Transversal:** última semana 2026-06-22→06-29 y mundial (2026-06-30→07-06) = ⚪ logística pura, cero código nuevo (ambos tracks).

### 2. Leer estado del board

```bash
gh issue list --state open --limit 100 \
  --json number,title,labels,assignees,createdAt,updatedAt

gh pr list --state open \
  --json number,title,headRefName,author,isDraft,createdAt,updatedAt
```

### 3. Leer actividad reciente

```bash
git log --since="last monday" --oneline --all
git log --since="last monday" --stat --no-merges
```

### 4. Leer checkin de la semana anterior (si existe)

Calculá número de semana ISO actual (`{N}`) y semana anterior (`{N-1}`).

Si existe `journal/2026-W{N-1}-checkin.md`, leerlo entero. Si no existe, anotar "primer checkin del régimen".

### 5. Comparar progreso semana a semana

Para cada item de la agenda de la semana anterior:
- ✅ Cerrado (PR mergeado, issue cerrado).
- 🟡 En progreso (PR abierto, draft, branch activa).
- 🔴 No tocado (sin actividad).

### 6. Producir memo de checkin

Usar la plantilla de la skill `rcj-coach-director` (sección "Plantilla de checkin semanal").

Campos obligatorios:
- T–N semanas a Incheon.
- Fase actual con su mantra.
- Cerrado / Atascado / Estado por persona (semáforo 🟢🟡🔴) / Decisiones / Movimientos del board.
- Agenda para la semana próxima por persona, con criterio de "hecho".
- Alertas / decisiones que Gustavo tiene que firmar.

### 7. Escribir el archivo

```bash
# {N} es el número de semana ISO actual, formato ISO 8601 (lunes inicia semana).
# Si {N} es 19, el archivo es journal/2026-W19-checkin.md
```

Escribir el memo a `journal/2026-W{N}-checkin.md` usando la herramienta `Write` (no commitear todavía — Gustavo revisa primero).

### 8. Preguntar al usuario

Después de escribir el archivo, mostrar el memo y preguntar:

> "Memo guardado en `journal/2026-W{N}-checkin.md`. ¿Querés que prepare drafts de issues nuevos en `project/backlog/staging/` para los temas detectados que no estén en issue? ¿O hay alguna decisión que querés discutir antes?"

## Restricciones

- ❌ NO ejecutar `gh issue create/comment/close/edit`. Solo lectura con `gh`.
- ❌ NO modificar código fuente.
- ❌ NO commitear el archivo del journal — Gustavo lo revisa y commitea él (regla del repo).
- ✅ Sí escribir markdown en `journal/` y proponer drafts en `project/backlog/staging/`.
