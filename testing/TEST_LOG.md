# TEST_LOG — Bitácora de tests IITA RCJ 2026

> **Equipo:** IITA Salta · **Competencia:** RoboCup Junior Rescue Line 2026 · **Mundial:** Incheon, Corea, 2026-06-30 a 2026-07-06.
>
> Cómo se usa esta bitácora → ver [`README.md`](README.md). En resumen: cada ensayo se anota antes de irse del lab, con ID secuencial `T-XXX` y categoría entre corchetes.

---

## 1. Índice por categoría

Cuando llegue el momento del TDP, esta tabla es la evidencia citable directa para cada criterio de la rúbrica.

### `[MECH]` — Mechanical reliability (rúbrica TDP §Mechanical, T7, 6 pts)

| ID | Fecha | Título | Resultado |
|----|-------|--------|-----------|
| _(vacío — próximos tests acá)_ | | | |

### `[ELEC]` — Electronic reliability (rúbrica TDP §Electronic, T11, 6 pts)

| ID | Fecha | Título | Resultado |
|----|-------|--------|-----------|
| _(vacío — próximos tests acá)_ | | | |

### `[SW]` — Software reliability (rúbrica TDP §Software, T14, 6 pts)

| ID | Fecha | Título | Resultado |
|----|-------|--------|-----------|
| _(vacío — próximos tests acá)_ | | | |

### `[PERF]` — Performance evaluation (rúbrica TDP §Performance, T15, 6 pts)

| ID | Fecha | Título | Resultado |
|----|-------|--------|-----------|
| _(vacío — próximos tests acá)_ | | | |

---

## 2. Convenciones

- **ID:** `T-001`, `T-002`, … secuencial sin huecos. No se reutilizan IDs aunque se borre una entrada.
- **Fecha:** formato `YYYY-MM-DD`. Es la fecha del test, no la del que escribe.
- **Categoría:** uno o dos tags entre corchetes, ej `[SW]`, `[MECH][PERF]`.
- **Resultado en la tabla índice:** ✅ pasó / ⚠️ parcial / ❌ falló. Sin grises.
- **Tester:** nombre o handle GitHub del que ejecutó.
- **Robot rev:** `rev-current` (HEAD del repo en ese momento) o un tag específico si se rebobinó.
- **Issue/PR:** linkear si el test verifica un fix o destapa un bug. Si destapa bug nuevo, abrir issue antes de cerrar el test.

---

## 3. Plantilla para nueva entrada

> Copiar este bloque, pegarlo abajo del último test, llenar y agregar la fila en el índice §1.

```markdown
## T-XXX · YYYY-MM-DD · [CAT] Título corto descriptivo

**Tester:** @handle · **Robot:** rev-current · **Pista:** sala IITA / pista oficial / …
**Issue/PR relacionado:** #NNN (si aplica)

**Objetivo.** Qué se quería verificar. Una sola oración.

**Setup.**
- Batería: X.XV al arranque.
- Iluminación: fluorescente / mixta / LED zona.
- Pista: dibujo + obstáculos + víctimas configurados como…
- Firmware commit: <sha corto>.
- Modo RPi: `--mode <X>` (si #81 ya mergeó).

**Procedimiento.**
1. Paso 1.
2. Paso 2.
3. …

**Resultado.**

| Métrica | Esperado | Obtenido | OK |
|---|---|---|---|
| … | … | … | ✅/⚠️/❌ |

**Conclusión.** Qué pasó realmente. Si falló, cuál es la hipótesis del cuello de botella.

**Acción.**
- Issue abierto / cerrado: #NNN.
- Re-test programado: T-XXX (referencia al siguiente).
- Cambio de hardware: anotado en `hardware/cambios_de_hardware.md`.
```

---

## 4. Entradas

<!--
═══════════════════════════════════════════════════════════════════════════
EJEMPLO DIDÁCTICO — no es un test real. Mostrar cómo se llena.
BORRAR ESTE BLOQUE cuando se agregue la primera entrada de verdad.
═══════════════════════════════════════════════════════════════════════════
-->

### T-000 · 2026-05-11 · `[SW][PERF]` EJEMPLO — Cómo se ve una entrada llena

> ⚠️ **Este NO es un test real.** Es solo el template lleno para que el equipo vea cómo queda. Borrar este bloque cuando se agregue T-001.

**Tester:** @ejemplo · **Robot:** rev-current · **Pista:** sala IITA
**Issue/PR relacionado:** #57

**Objetivo.** Verificar que el robot completa la zona de rescate sin chocar contra pared (issue #57 propone fix al bug de doble `-90°`).

**Setup.**
- Batería: 11.8V al arranque, 11.4V al final.
- Iluminación: fluorescente del techo + lámpara LED de zona.
- Pista: zona de rescate oficial con 2 víctimas vivas + 1 muerta.
- Firmware commit: `abc1234` (rama `feature/fix-rescate-90`).
- Modo RPi: producción headless.

**Procedimiento.**
1. Robot encendido fuera de la zona.
2. Empujarlo al rescate con `veces_deposit == 2` por consola.
3. Acercarlo a la pared lateral derecha hasta `front_distance < 12`.
4. Observar sentido del giro y si choca.
5. Repetir 10 veces alternando pared izquierda y derecha (5 c/u).

**Resultado.**

| Métrica | Esperado | Obtenido | OK |
|---|---|---|---|
| Corridas sin chocar pared (izq) | 5/5 | 5/5 | ✅ |
| Corridas sin chocar pared (der) | 5/5 | 4/5 | ⚠️ |
| Tiempo medio salida de rescate | <30 s | 22 s ±3 | ✅ |

**Conclusión.** Fix de #57 funciona en pared izquierda. En derecha falla 1/5: el sensor ultrasonido derecho devuelve 0 esporádicamente y la rama toma la decisión inversa. Hipótesis: ruido del cable del HC-SR04 derecho.

**Acción.**
- #57 NO se cierra todavía — re-test con cable apantallado.
- Abierto #XXX para apantallar cable HC-SR04 derecho.
- Re-test programado: T-001 (después del fix de cable).

<!-- ═══════════════════ FIN EJEMPLO — BORRAR HASTA ACÁ ═══════════════════ -->

---

*Bitácora inicializada el 2026-05-11 vía issue [#93](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/93). Mantenida por el equipo. Coach: @gviollaz.*
