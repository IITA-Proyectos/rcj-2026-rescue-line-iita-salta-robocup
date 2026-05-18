## Roadmap a 8/10 de confiabilidad para Incheon — plan de trabajo

**Decisión del director (2026-05-18):** objetivo para Incheon = **8/10 sólido y probado en banco**. El tramo **8→10 es post-mundial** (esfuerzo alto, riesgo de regresión, validación que no hay tiempo de hacer bien antes del mundial). Hoy estamos en **2/10**. Detalle del razonamiento: `docs/es/2026-05-18-auditoria-resiliencia.md` + `journal/decisiones/2026-05-18-objetivo-confiabilidad-8-incheon.md`.

Este issue es el **plan de trabajo ordenado en sprints**. Cada sprint distingue lo que **se puede escribir YA sin el robot** de lo que **requiere banco**.

---

### Sprint 0 — Destrabar (Enzo, esta semana) — *no toca el robot*
Sin esto nada fluye. Es lo de #107.
- [ ] Mergear PR #101 (TEST_LOG, ~24 pts TDP, riesgo cero).
- [ ] Correr triage #91 (vencido) clasificando por track.
- **Resultado:** equipo con prioridades cerradas y sustrato de registro de banco.

### Sprint 1 — CÓDIGO QUE SE ESCRIBE YA (no requiere robot enfrente) → habilita el 6/10
Esto se puede empezar HOY, en cualquier checkout del repo, aunque el equipo esté disperso o el robot no esté a mano. La validación en banco viene después (Sprint 2).
- [ ] **#60 + #61** — re-aplicar los timeouts revertidos. El código YA existió en el commit `5bac4a5`; es cherry-pick/re-escritura selectiva, no diseño nuevo. (Track A, Lautaro)
- [ ] **#112** — timeout + dreno serial en `runAngle()`. Patrón idéntico a #60. (Track A, Lautaro)
- [ ] **#113** — `threading.Lock` en `camthreader.py` (~6 líneas). (Track B, Lucio/Benjamin)
- [ ] **#110** — inicializar `cx_black` + `try/except` en loop de línea (~2 líneas). (Track B, Lucio/Benjamin)
- [ ] **#108** — escribir la unit `systemd` + `try/except` global en `Main.py`. Se prueba en cualquier Pi/PC, no necesita el robot. (Track B, Lucio/Benjamin)
- **Resultado:** todo el código de las 3 palancas + quick-wins escrito y en PRs, listo para validar.

### Sprint 2 — VALIDACIÓN EN BANCO (Track A, push libre ≤2026-05-26) → cierra el 6/10 sólido
Requiere el robot. Cada fix con su "test plan (banco)" del issue + entrada en `testing/TEST_LOG.md`.
- [ ] **#53** — heartbeat serial + failsafe `speed=0`. Necesita banco para tunear el timeout real y probar el corte. **La palanca #1.** (Track A, Lautaro)
- [ ] **#27** — watchdog de hardware (`WDT_T4`) + callback que para motores. Validar reset+recuperación en banco. (Track A, Lautaro)
- [ ] Validar en banco todos los fixes del Sprint 1 (timeouts, runAngle, camthreader, systemd, cx_black).
- **Resultado: 6/10 — el robot no se autodestruye, no queda descontrolado, el proceso se reinicia.**

### Sprint 3 — CAPA DE SALUD + DEGRADACIÓN (con gate Enzo/Gustavo, fin mayo–junio) → 8/10
- [ ] Diseñar e implementar `struct SystemHealth { bno_ok, apds_ok, tof_ok, encoder_stall }` (el **diseño se puede empezar YA en papel/código**, la integración requiere banco).
- [ ] Fallbacks por sensor: sin BNO→navegar por tiempo; sin color→seguir línea sin decidir verde; sin cámara→línea con sensores Teensy.
- [ ] **#109** BNO runtime + re-init · **#72** resync post-reset Teensy · **#111** infer_thread respawn · **#67** encoders no atómicos · **#59** escape FSM rescate.
- **Resultado: 8/10 — el robot OPERA DEGRADADO ante la mayoría de fallas, no solo se detiene.**

### Post-mundial — 8→10 (NO antes de Incheon)
Recuperación funcional (reanudar misión, no solo safe-state), redundancia de sensores, watchdog jerárquico probado, validación estadística por inyección de fallas. Documentado como deuda, no como meta de Incheon.

---

### Qué se puede hacer YA (resumen para la próxima reunión)
**Sin robot, hoy mismo:** todo el **Sprint 1** (código de timeouts, runAngle, camthreader Lock, cx_black, systemd) + el **diseño** del `SystemHealth` del Sprint 3. **Con Enzo:** Sprint 0 (merge #101 + triage #91). El robot solo hace falta a partir del Sprint 2 (validación).

**Régimen:** Sprint 1-2 = Track A push libre ≤2026-05-26. Sprint 3 = gate Enzo (Track A ≥27-may / Track B ≥12-jun). **Asignar:** @gviollaz @enzzo19 (coordinación), ejecución por codeowner.
