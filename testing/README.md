# `testing/` — Bitácora de tests del equipo

Esta carpeta contiene la **evidencia documental de los tests que hacemos en banco y en pista** rumbo a RoboCup Junior Rescue Line 2026 (Incheon, Corea).

Es la respuesta del equipo al criterio **"Reliability Tests and quality assurance"** de la rúbrica oficial TDP 2026 — que aparece en 4 de las 5 grandes secciones (Mechanical, Electronic, Software, Performance) y suma **24 puntos directos del TDP** + otros 3 del Poster. Si esta carpeta está vacía, perdemos automáticamente ~19% del puntaje de documentación.

---

## Archivos

- **[`TEST_LOG.md`](TEST_LOG.md)** — bitácora cronológica. Cada test es una entrada con ID `T-XXX`.
- **`tests/`** — reservada para splits futuros si `TEST_LOG.md` crece mucho durante junio. Por ahora vacía.

---

## Regla de oro: 10 minutos antes de irte del laboratorio

> **Después de cada ensayo, el responsable de la sesión escribe una entrada en `TEST_LOG.md` antes de irse.**
> Toma 5-10 min. No se posterga al día siguiente — la memoria de qué falló se pierde rápido.

Si no se anota, el test no existió para el TDP. Es así de simple.

---

## Cómo abrir un test nuevo

1. Abrí `TEST_LOG.md`.
2. Buscá el último ID (`T-001`, `T-002`…) y usá el siguiente.
3. Copiá la **plantilla** del §3 del archivo y completala.
4. Agregá el link en la **tabla índice** del §1, en la fila de la categoría correspondiente.
5. Commit con mensaje: `docs(testing): T-XXX <título corto>`.

---

## Categorías

Cada entrada lleva uno o dos tags entre corchetes que mapean a las secciones de la rúbrica:

| Tag | Sección rúbrica | Ejemplos |
|---|---|---|
| `[MECH]` | T7 Mechanical reliability | chasis, drive-base, pinza, sensores fijos |
| `[ELEC]` | T11 Electronic reliability | power tree, ruido, voltaje bajo carga, conexiones |
| `[SW]` | T14 Software reliability | line-track, FSM rescate, visión, comms |
| `[PERF]` | T15 Performance evaluation | corridas completas + qué falló + cómo se arregló |

Un test puede tener dos tags si cruza categorías (ej: `[MECH][PERF]` para una corrida que falló por slip mecánico).

---

## Quién mantiene esto

Rotación semanal entre Laureano, Benjamin, Lucio y Enzo. La regla es del equipo, no del coach — si nadie anota, nadie llega al TDP.

> **Issue padre:** [#93 — Inicializar testing/TEST_LOG.md](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/93)
