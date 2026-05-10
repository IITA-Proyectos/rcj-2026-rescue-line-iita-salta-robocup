# Triage de issues abiertos — sesión @enzzo19 + @benjaminvillagran

> **Pedido del coach @gviollaz:** revisen los 20 issues técnicos abiertos por las auditorías y decidan, issue por issue, **cuáles tomar esta semana, cuáles este mes, y cuáles dejar para post-mundial**. No tienen que implementar todo — el triage es la tarea.
>
> **Tiempo estimado de la sesión:** 60-90 min entre los dos.
>
> **Deadline sugerido:** 1 semana desde hoy (2026-05-17).
>
> **Resultado esperado:** este doc completado con sus decisiones + comentarios en cada issue cerrando o etiquetando.

---

## 0. Cómo usar este doc

Por cada issue marcado abajo, decidan **una sola opción**:

| Decisión | Significado | Acción inmediata |
|---|---|---|
| 🟢 **Tomar** | Se hace en la ventana indicada (esta semana / este mes). | Comentar en el issue: "tomado por X, deadline Y". |
| 🟡 **Posponer** | El tema sigue válido pero entra a post-mundial. | Etiquetar con `priority/low`. |
| 🔴 **Descartar** | Falso positivo o el equipo confirma que era intencional. | Cerrar el issue con explicación de 1-2 líneas. |
| ❓ **Investigar** | Hace falta más info (git blame, ensayo en banco) antes de decidir. | Comentar quién investiga y deadline. |

**Regla de oro de la sesión:** si dudan más de 5 min en un issue, marquen 🟡 Posponer y sigan. Mejor decidir 28 issues en 90 min que perder la sesión en 3.

---

## 1. Bucket A — Esta semana (alto valor / bajo costo)

> **Criterio:** trabajo ≤ 90 min, riesgo de cambiar Bajo, riesgo de no cambiar Medio o Alto. Estos son los de mayor ROI.
>
> **Suma de tiempo si toman todos:** ~6 horas distribuidas entre el equipo.

| # | Título | R-no-cambiar | R-cambiar | Tiempo | Decisión |
|---|---|---|---|---|---|
| [#73](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/73) | `serial.Serial` sin timeout en RPi | Bajo | Bajo | **5 min** | ⬜ |
| [#70](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/70) | `serialEvent5()` lee 1 byte por loop — drain incompleto | Medio | Bajo | **30 min** | ⬜ |
| [#71](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/71) | `reset_input_buffer()` descarta comandos en estado `esperando` | Medio | Bajo | **30 min** | ⬜ |
| [#65](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/65) | `vs.read()` puede devolver `None` sin chequeo | Medio | Bajo | **30 min** | ⬜ |
| [#66](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/66) | `ser.write()` sin clamp ni flush | Medio | Bajo | **1 h** | ⬜ |
| [#62](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/62) | `while(1)` infinito ante fallo init sin LED de aviso | Medio | Bajo | **1 h** | ⬜ |
| [#57](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/57) | **[P0]** Zona rescate: ambas ramas rotan -90° | **Alto** | Medio | **1 h** | ⬜ |
| [#81](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/81) | `--mode` flag en RPi para arrancar en distintos modos | Medio | Bajo | **90 min** | ⬜ |

**Notas:**
- **#57 es el único P0** del bucket A. Antes de tocar: revisen `git blame` y confirmen con quien lo escribió que era bug, no intención.
- **#73 es el quick-win más obvio** — 5 min y mejora robustez.
- **#81 abre la puerta a probar Technical Challenges aislados sin reflashear** — lo más estratégico del bucket.

---

## 2. Bucket B — Este mes (mayor inversión, recomendado pre-mundial)

> **Criterio:** trabajo entre 1-5 horas. Riesgo medio. Importante de cara a competencia.
>
> **Suma de tiempo si toman todos:** ~30-35 horas. Distribuir entre el equipo.

| # | Título | R-no-cambiar | R-cambiar | Tiempo | Decisión |
|---|---|---|---|---|---|
| [#61](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/61) | `while (!apds.colorDataReady())` sin timeout | Medio | Bajo | 1 h | ⬜ |
| [#64](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/64) | `cv2.imshow` sin guard `HEADLESS` | Medio | Bajo | 1 h | ⬜ |
| [#72](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/72) | Sin handshake `0xFA` al boot del Teensy | Medio | Bajo | 1 h | ⬜ |
| [#58](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/58) | `case 12` cae al `case 14` por falta de `break` | Medio | Medio | 1 h | ❓ Verificar git blame primero |
| [#60](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/60) | `runDistance` sin timeout — robot infinito si encoder falla | Medio | Medio | 2 h | ⬜ |
| [#63](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/63) | `runTime/runDistance` descartan bytes serial sin parsear | Medio | Medio | 2 h | ⬜ |
| [#59](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/59) | Movimientos no actualizan `claw.update()` ni rescate FSM | Medio | Medio | 3 h | ⬜ |
| [#53](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/53) | **(viejo)** Heartbeat serial — STOP a 500ms si no hay frame | **Alto** | Medio | 2 h | ⬜ |
| [#25](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/25) | **(viejo)** Bloqueo serial en movimiento de pinzas | Medio | Medio | 3 h | ⬜ |
| [#87](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/87) | `pinout.h` central — alinear sketches con firmware | Bajo | Bajo | 3 h | ⬜ |
| [#84](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/84) | Stub Bluetooth para SuperTeam Challenge | Medio | Medio | 4 h | ⬜ |
| [#85](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/85) | **Detección víctimas falsas (regla 2026)** | **Medio-Alto** | Medio | ~5 h | ⬜ |
| [#86](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/86) | **LED en pared zona (regla 2026)** | Medio | Bajo | ~5 h | ⬜ |

**Notas:**
- **#53 (viejo) tiene riesgo no-cambiar Alto** — sin heartbeat, si la Pi se cuelga el robot se va de pista. Considerar cabeza de bucket B.
- **#85 y #86 son obligatorios si se aplican las reglas RCJ 2026** — víctimas falsas + LED de pared son requerimientos NUEVOS este año. Si no se atacan, perdemos puntaje en mundial.
- **#84 (SuperTeam stub)** vale aunque no sepamos qué pedirá el challenge — es seguro de adaptabilidad.

---

## 3. Bucket C — Post-mundial / cuando haya tiempo (deuda técnica)

> **Criterio:** P2 robustez o refactors mayores con riesgo Medio-Alto. No bloquean competencia.

| # | Título | R-no-cambiar | R-cambiar | Tiempo | Decisión |
|---|---|---|---|---|---|
| [#67](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/67) | `Moto::pulseCount` sin init en constructor | Bajo | Bajo | 30 min | ⬜ |
| [#76](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/76) | Documentar contrato de rangos del payload | Bajo | Mínimo | 1 h | ⬜ |
| [#74](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/74) | Sanity check de rangos en parser Teensy | Bajo | Bajo | 1 h | ⬜ |
| [#68](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/68) | `requirements.txt` sin pinning | Bajo | Bajo | 1 h | ⬜ |
| [#75](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/75) | Sin telemetría de frames RX/TX | Bajo | Bajo | 2 h | ⬜ |
| [#83](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/83) | Magic numbers a `parametros.h` | Bajo | Medio | ~3 h | ⬜ |
| [#27](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/27) | **(viejo)** Watchdogs faltantes (general) | Medio | Medio | 3 h | ⬜ |
| [#69](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/69) | Modelos / videos al repo — migrar a Git LFS | Bajo | Medio (coord. equipo) | 3 h | ⬜ |
| [#82](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/82) | Skill registry mínimo en Teensy (refactor switch) | Bajo-Medio | Medio | ~4 h | ⬜ |
| [#38](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/38) | **(viejo)** Clonar SD | Bajo | Bajo | — | ⬜ |

---

## 4. Issues administrativos del equipo (NO son del audit técnico)

Estos no entraron al triage de auditoría — son tareas del equipo decididas antes. Solo los listamos para que no se les escapen.

| # | Título | Asignado | Notas |
|---|---|---|---|
| [#4](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/4) | Informe de coaching repositorio (2026-02-23) | — | Old, evaluar si sigue vigente |
| [#41](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/41) | P0 Diagrama de bloques / flujo del software | — | TDP requirement |
| [#45](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/45) | Armado Poster | — | TDP / poster |
| [#46](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/46) | Armado TDP | enzo, lucio, lautaro, benjamin | TDP requirement |
| [#47](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/47) | Mejora Drive-Base | — | Mecánica |
| [#52](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/52) | Mejora y Dudas sobre Diseño | — | Discusión abierta |
| [#55](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/55) | Armado VIDEO | benjamin | TDP |

---

## 5. Plantilla de decisión final

Después de pasar por los 31 issues, completen esta tabla resumen al final de la sesión:

```
Sesión de triage 2026-MM-DD
Participantes: @enzzo19 @benjaminvillagran [+otros]

Bucket A (esta semana):
  - Tomados:    [lista de #]
  - Pospuestos: [lista de #]
  - Descartados: [lista de # + razón]

Bucket B (este mes):
  - Tomados:    [lista de #]
  - Pospuestos: [lista de #]
  - Descartados: [lista de # + razón]
  - Investigar: [lista de # + responsable]

Bucket C (post-mundial):
  - Confirmados como deuda: [lista de #]
  - Re-priorizados a A o B: [lista de #]

Total horas comprometidas para esta semana: X
Total horas comprometidas para este mes: Y

Próxima revisión: 2026-MM-DD
```

---

## 6. Sugerencia de orden para la sesión

1. **Empezar por Bucket A** (8 items, ~15 min). Son los más fáciles de decidir — riesgo bajo, ROI alto. Probable que la mayoría sean 🟢 Tomar.
2. **Después Bucket B** (13 items, ~45 min). Acá está el grueso de la conversación. Decidir cuáles van pre-mundial y cuáles post.
3. **Cerrar con Bucket C** (10 items, ~10 min). Casi todos serán 🟡 Posponer. Confirmar.
4. **Issues admin del equipo** (~10 min). Solo verificar que no se les pase ningún deadline.
5. **Completar la plantilla resumen del §5** (~5 min) y pegarla como comentario en el meta-issue [#88](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/88) y [#77](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/77).

---

## 7. Reglas de la sesión

1. **No empiecen a implementar mientras triagean.** El triage es triage, la implementación es después.
2. **Ante duda > 5 min → 🟡 Posponer.** Pueden retomarlo la próxima sesión.
3. **🔴 Descartar requiere razón en una línea** en el comentario del issue. Ejemplo: "intencional, así lo decidió Lautaro porque el robot SIEMPRE entra por la izquierda en zona de rescate".
4. **🟢 Tomar requiere asignar a alguien.** Sin dueño, no es Tomado — es Pospuesto.
5. **El coach (Gustavo) NO decide acá.** Vos dos eligen, y le mandan el resumen del §5 al final.

---

## 8. Resumen estimado de carga

Si completan todo el Bucket A (~6 h totales) en una semana, el robot ya queda significativamente más fail-safe y flexible. **Esa es la meta mínima sugerida.**

| Bucket | Items | Tiempo total si todos ✅ | % del trabajo total |
|---|---|---|---|
| A — Esta semana | 8 | ~6 h | 12 % |
| B — Este mes | 13 | ~33 h | 65 % |
| C — Post-mundial | 10 | ~12 h | 23 % |
| **Total auditoría** | **31** | **~51 h** | **100 %** |

> Nota: el tiempo "total si todos ✅" asume que se hacen todos los temas. **No es realista hacer los 31** antes del mundial. Por eso el triage. Esperar que en realidad se cierren ~10-15 (50 % del Bucket A + B).

---

## 9. Después de la sesión

Cuando terminen, manden el resumen del §5 como comentario en el meta-issue [#77](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/77) y/o [#88](https://github.com/IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup/issues/88) y notifiquen al coach @gviollaz.

A partir de ahí, el calendario sale solo: trabajo del Bucket A esta semana, del B durante el mes, post-mundial el resto.

---

*Documento preparado por Claude Code (Opus 4.7) a pedido de @gviollaz para facilitar la decisión del equipo. Filosofía: TEMAS A ANALIZAR — el equipo decide, el coach asiste, el auditor IA solo presenta el material. Fecha: 2026-05-10.*
