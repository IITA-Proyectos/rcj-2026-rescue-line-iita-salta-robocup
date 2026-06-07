<!--
Plantilla estándar IITA RCJ 2026. Borrá esta línea y rellená cada sección.
Si es un fix de auditoría, usá la sección "Audit fix"; si es feature/refactor, borrala.
-->

## ¿Qué cambia?

<!-- 1-3 oraciones describiendo el cambio. NO copies el diff. Enfocate en intención. -->

## Issue relacionado

Closes #NNN

<!-- Todo PR debe cerrar al menos un Issue. Si no hay issue, abrí uno antes (audit-finding.yml). -->

---

## ✅ Checklist obligatorio

- [ ] Vinculado a un Issue (línea `Closes #` arriba).
- [ ] Conventional Commit en el título (`fix(teensy): ...`, `feat(rpi): ...`, `refactor(comms): ...`).
- [ ] Cambios documentados en `docs/es/` si afectan comportamiento del robot.
- [ ] No commiteo binarios pesados (modelos, videos) — van a Git LFS o bucket.
- [ ] No hay secretos/tokens/credenciales en el diff.
- [ ] El idioma del diff es español (comentarios, mensajes, docs).

## 🧪 Test plan ejecutado

<!--
Tachá lo que corresponda. Si no probaste en hardware real, decí EXPLÍCITAMENTE
"NO PROBADO EN BANCO — pendiente antes de merge". El revisor puede pedir test
antes de aprobar.
-->

- [ ] **Compila** (`pio run` para Teensy / `python -m py_compile` para RPi).
- [ ] **Probado en banco** — robot enciende, motores responden, no hay watchdog reset.
- [ ] **Probado en pista** — corrida completa simulada o segmento crítico.
- [ ] **Métricas** registradas en `testing/TEST_LOG.md` con fecha y resultado.

### Resultado del test

<!-- Pegá acá la entrada que vas a agregar a TEST_LOG.md o un screenshot/video corto. -->

```
Ej: 2026-05-09 — fix encoder volatile
  - 3/3 corridas runDistance(1000) → 99-103 cm
  - 0 watchdog resets en 5 min de operación continua
  - Sin regresión en pinza ni visión
```

---

## 🤖 Uso de IA (declaración ICRS)

<!-- Política IITA: declarar uso de IA en todo PR. -->

- [ ] Este PR fue **escrito por IA** (especificá modelo/herramienta): ___
- [ ] Este PR fue **asistido por IA** (sugerencias revisadas por humano).
- [ ] Este PR fue **escrito 100% por humano**, sin asistencia de IA.

---

## 📋 Riesgo y rollback

**Riesgo:** Bajo / Medio / Alto

**Plan de rollback si rompe:** <!-- "revertir commit", o pasos específicos -->

---

## 📸 Screenshots / videos (si aplica)

<!-- Especialmente útil para visión, pinza y mecánica. -->
