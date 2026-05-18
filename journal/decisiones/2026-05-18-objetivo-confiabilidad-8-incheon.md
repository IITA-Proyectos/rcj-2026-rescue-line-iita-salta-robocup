# Decisión — Objetivo de confiabilidad para Incheon: 8/10 (10/10 post-mundial)

**Fecha:** 2026-05-18 · **Tipo:** corte de scope / criterio de proyecto

**Decisión:** El objetivo de auto-recuperación para el mundial Incheon es **8/10 sólido y validado en banco**, NO 10/10. El tramo **8→10 queda explícitamente como post-mundial**.

**Contexto:** La auditoría de resiliencia 2026-05-18 (4 auditores) dio el sistema en **2/10**. Las 3 palancas base lo suben a ~6/10 (~medio día); la capa de salud + degradación lo lleva a 8/10 (~1 semana de código + banco). El 8→10 son semanas de un equipo dedicado + validación estadística por inyección de fallas. Faltan 6 semanas a Incheon y el equipo no se está moviendo (0 commits / 7 días).

**Opciones consideradas:**
- A) Ir por 10/10. Contra: rendimientos decrecientes brutales; cada capa extra es código nuevo que toca sistemas validados → riesgo de regresión; el 8→10 es sobre todo *validación* (tiempo de banco que se necesita para puntuar, no para robustez marginal); contradice el régimen de fases que el director definió.
- B) **Objetivo 8/10 probado, 8→10 post-mundial.** Pro: máximo retorno real; un robot 8/10 *probado* gana más corridas que un 10/10 *teórico sin validar*; coherente con el filtro de fases (8→10 no pasa "ventaja desproporcionada").

**Recomendación / decisión tomada:** **Opción B.** Un robot 8/10 bien probado en banco es más competitivo que un 10/10 frágil a medio validar. El cuello de botella del proyecto no es el techo de diseño — es arrancar la ejecución y conseguir horas de banco.

**Riesgo si nos equivocamos:** si sobra tiempo y banco (improbable dado el ritmo actual), se podría haber empujado algún ítem del 8→10. Mitigación: el 8→10 queda documentado como deuda priorizada (no perdido), revisable si el equipo acelera y el régimen lo permite.

**Quién firma:** Gustavo (director). Bajado al equipo vía #114 (roadmap) y #107 (foco Enzo).

**Subsistema → track → fase → gate:** transversal. Sprint 1-2 (→6/10) = Track A push libre ≤2026-05-26. Sprint 3 (→8/10) = gate Enzo. 8→10 = post-mundial.

**Plan de ejecución:** issue **#114** (roadmap por sprints). Lo accionable YA sin robot = Sprint 1 completo + diseño del `SystemHealth`.
