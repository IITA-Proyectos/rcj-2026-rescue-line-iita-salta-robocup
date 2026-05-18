# Checkin semanal — Semana W20 (2026-05-16)

**T–6 semanas a Incheon** (2026-06-30, 45 días).
**Régimen: gate progresivo con TRACK DUAL por subsistema** (Gustavo 2026-05-16, **+7 días el 2026-05-18** para dar tiempo de cierre al equipo):
- **Track A — firmware/control + comms:** 🟢 push libre ≤2026-05-26 · 🟡 gate Enzo 2026-05-27→06-06 · 🔴 gate Gustavo ≥2026-06-07.
- **Track B — docs + visión (RPi):** 🟢 push libre ≤2026-06-11 · 🟡 gate Enzo ≥2026-06-12.
- **Transversal (NO se movió — atado al mundial):** última semana (06-23→06-29) + mundial = logística, cero código.
- **Hoy (18-may) ambos tracks en push libre.** Track A tiene 8 días de aire (hasta 26-may); Track B hasta 11-jun. La extensión descomprime el firmware/Lautaro.

> Primer checkin del régimen (no hay W19 previo para comparar). Generado por el coach director; **sin commitear** — Gustavo revisa.

## Cerrado / en vuelo esta semana
- PR #101 (TEST_LOG.md, ~24 pts TDP) **ready**, a un merge de distancia — máximo leverage abierto.
- Commits de timeouts + fixes claw.cpp en `feature/initialize-testing-log` (pero ver Atascado).
- Auditoría integral de los 3 subsistemas completada (Teensy / RPi visión / comms).
- Skill `rcj-coach-director` + `/coach-checkin` implementadas (PR #100, smoke tests pendientes).
- Reparto por persona materializado en issues #102–#106.

## Atascado / alerta
- 🔴 **Timeouts #59/#60/#61/#62 REVERTIDOS en código** (`cead75e` borró lo de `5bac4a5`). El equipo creía que estaban resueltos. Comentado en los 3 issues + plan en #105. **Riesgo P0 — prioridad #1 real.**
- 🔴 **Triage #91 vence 2026-05-17 (mañana).** Sin cerrar, el equipo entra al freeze sin prioridades.

## Estado por persona

| Persona  | Semáforo | Nota |
|----------|----------|------|
| Lautaro (Laumonteros) | 🔴 | #105: timeouts revertidos sin arrancar — es la prioridad #1 crítica del proyecto |
| Benjamin | 🟡 | #104 (cluster RPi + #68 suyo + gate de banco) definido; depende de kickoff |
| Lucio    | 🟡 | Fixes RPi (#65/#66/#73/#64 + V-A→V-F) referenciados en #104; depende de Benjamin/banco |
| Enzo     | 🟡 | #106 con deadlines inminentes: merge #101 + cerrar triage #91 mañana |

## Decisiones tomadas esta semana
- **Régimen revisado a gate progresivo con TRACK DUAL** (Gustavo 2026-05-16, reemplaza todo lo anterior): Track A firmware/comms (F1≤05-19 · gate Enzo 05-20 · gate Gustavo 05-31) · Track B docs/visión (libre ≤06-04 · gate Enzo ≥06-05). → memoria + spec + SKILL.md + comando + issues.
- Reordena el énfasis: la deadline dura (19-5) es del frente firmware/Lautaro; visión tiene ventana hasta 4-jun.
- Reparto del trabajo por persona en issues separados (#102 agenda, #103 consolidado, #104 Benjamin, #105 Lautaro, #106 Enzo).
- Alerta de timeouts revertidos comentada en #60/#61/#62 (autorizada por Gustavo).
- Aclarado: Lautaro = Laureano Monteros = `Laumonteros` (una persona).

## Movimientos en el board
- **Entran al `must` (vía triage #91):** 10 quick-wins nuevos (5 confiabilidad: T-A,T-B,V-A,V-E,C-A · 5 performance: V-F,V-D,V-B,V-C,T-C) + re-aplicación de timeouts.
- **Re-priorizado a #1:** timeouts #59/#60/#61/#62 (estaban como "verificar", ahora confirmados revertidos).
- **A evaluar en triage:** 5 temas medio-riesgo (FSM rescate bloqueante, serialEvent5 desfase, Serial5.write(255) colisión, doble-pick green_state, runTime/runDistance sin parsear) → must-con-banco o post-mundial.

## Agenda semana próxima (detalle en cada issue)
- **Enzo (#106):** mergear #101 → cerrar triage #91 (vence 17) → distribuir #104/#105 → cuidar que Lautaro arranque por timeouts.
- **Lautaro (#105):** re-aplicar timeouts incremental (PRIORIDAD #1) → T-A get_color → T-B taskDone → #58 break.
- **Benjamin (#104):** #68 pinning → banco/co-review cluster RPi → V-B/V-C performance con medición FPS.
- **Lucio (vía #104):** fixes RPi #65/#66/#73/#64 + V-A/V-D/V-E/V-F, Benjamin valida en banco.

## Alertas / decisiones que Gustavo tiene que firmar
- ✅ **Régimen de fases — DECIDIDO** (gate progresivo 3 fases, ver arriba). Ya no es pregunta abierta.
- Pendiente operativo: el push fuerte real son **3 días** (16→19). Si el triage #91 corre tarde, parte del push F1 se come el fin de semana antes de que entre el gate Enzo el 20.
- TDP/Poster/Video (#95/#97/#98/#94/#96): NO tocan el robot → se pueden trabajar en F2/F3 sin gate de código. Confirmar encuadre con Enzo en el triage.
- Smoke tests PR #100: pendientes, no urgentes (no tocan el robot). OK dejarlos para F2/F3.
