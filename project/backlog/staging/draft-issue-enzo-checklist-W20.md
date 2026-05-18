## Enzo — tu checklist de coach, semana W20

**Fase:** 🟢 Fase 1 — push exhaustivo · **T–6 semanas a Incheon** · **freeze el 2026-05-20** (3-4 días).

Enzo, esto es **lo que tenés que hacer vos** como coach/coordinador esta semana, en orden. No es el panorama (eso está en #103) ni la agenda para distribuir (#102) — es tu lista personal de acciones. Cada ítem tiene deadline y criterio de "hecho".

---

### 1. 🟥 HOY/mañana — Mergear PR #101 (TEST_LOG.md)
- **Por qué primero:** desbloquea el "criterio de hecho" de TODOS los demás temas (cada fix se valida con una línea en `testing/TEST_LOG.md`). Además son ~24 pts del TDP con riesgo cero (es doc).
- **Acción:** revisar y mergear PR #101.
- **Hecho:** PR #101 mergeado a `main`.
- **Deadline:** hoy o mañana 2026-05-17.

### 2. 🟥 Vence 2026-05-17 — Cerrar el triage del #91
- **Por qué:** el deadline del #91 vence mañana. Sin triage cerrado el equipo entra al freeze sin prioridades.
- **Acción:** correr la sesión de triage usando **#103** (consolidado) como input. Decidir baldes (must/should/post-mundial), etiquetar issues, mandar a `post-mundial` lo que no entra antes del 2026-05-20.
- **Hecho:** #91 cerrado; issues etiquetados por balde; documentado qué se congela el 2026-05-20.
- **Deadline:** 2026-05-17.

### 3. 🟧 Antes del 2026-05-20 — Distribuir y arrancar el push
- **Acción:** bajar a cada chico su frente: **#105** a Lautaro (Teensy), **#104** a Benjamin (RPi+banco; Benjamin coordina con Lucio los fixes de visión). Usar la agenda #102 como guion de la reunión de equipo.
- **Hecho:** cada chico confirmó su lista y arrancó; reunión de kickoff del push hecha.
- **Deadline:** 2026-05-18 (para que queden 2 días de ejecución antes del freeze).

### 4. 🟧 Seguimiento crítico — Prioridad #1 de Lautaro
- **Por qué:** el hallazgo más grave es que los timeouts #59/#60/#61/#62 están **revertidos en código** (ver comentarios en esos issues y plan en #105). El equipo creía que estaban resueltos.
- **Acción:** asegurarte de que Lautaro ataque la re-aplicación de timeouts **antes** que cualquier quick-win. Que no se distraiga con lo chico mientras el agujero grande sigue abierto.
- **Hecho:** Lautaro confirmó que arranca por los timeouts; #105 con progreso visible antes del 2026-05-20.
- **Deadline:** seguimiento diario hasta el freeze.

### 5. 🟨 Tu dominio (docs pre-mundial) — encuadrar qué entra antes del freeze
- **Acción:** revisar los issues de docs que son tuyos/del equipo y decidir en el triage cuáles entran antes del 05-20 y cuáles son post: **#95** (validar fidelidad docs/es vs código antes del TDP), **#97/#98** (plan TDP/Poster/Video según rúbrica), **#94** (sesión de fotos), **#96** (BOM). Ojo: el TDP/Poster/Video son puntaje grande pero NO tocan el robot — pueden trabajarse incluso durante el freeze.
- **Hecho:** cada uno con balde asignado en el triage #91.
- **Deadline:** dentro del triage (2026-05-17).

### 6. 🟦 Nice (post-freeze OK) — Smoke tests del PR #100
- **Acción:** si queda aire (NO es prioridad sobre lo de arriba), correr los smoke tests de la skill `rcj-coach-director` (PR #100) en una sesión nueva de Claude Code dentro del repo. No toca el robot — puede esperar al post-freeze sin costo.
- **Hecho:** smoke tests marcados en el PR #100, o nota de que quedan post-freeze.
- **Deadline:** sin deadline (nice-to-have).

---

### Resumen de tu semana en una línea
**Mergeá #101 → cerrá el triage #91 con #103 → distribuí #104/#105 → cuidá que Lautaro arranque por los timeouts. Lo demás es secundario hasta el freeze.**

*Generado por el coach director (Claude Code) bajo supervisión de @gviollaz. Panorama: #103 · Agenda equipo: #102 · Frentes: #104 (Benjamin) #105 (Lautaro).*
