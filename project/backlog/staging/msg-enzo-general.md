**Enzo — panorama completo y qué tenés que hacer para que el equipo arranque YA.**

> **DOCUMENTO HISTÓRICO (2026-05-18).** Estado de proyecto y régimen vigente: ver [`docs/es/ESTADO-ACTUAL-2026-05-31.md`](../../../docs/es/ESTADO-ACTUAL-2026-05-31.md). Las fechas y pendientes de abajo pueden estar superados.
>
> **Correcciones (al 2026-05-31):** **PR #101 ya está mergeado en `main`**; el triage #91 quedó superado por el régimen 31-may. El régimen "Track A push ≤26-may" SUPERADO → firmware/comms ya entra por **gate de Enzo**; docs/visión push libre ≤2026-06-11; freeze de código 2026-06-15. "6 semanas a Incheon / 7 días sin commit" es del 18-may (hoy faltan **~30 días / ~4,3 semanas**). **DUPLICADO:** se solapa con `programa-enzo-coordinacion-validacion.md` y los `msg-*` por persona.

El plan a 8/10 de confiabilidad para Incheon (#114) ya está bajado a código concreto. Hay **4 documentos de aceleración**, uno por persona, con análisis + código propuesto + cómo validar. Tu trabajo: distribuir, destrabar y aprobar — no implementar.

## El tablero (quién hace qué esta semana)

| Persona | Frente | Issue de arranque | Doc detallado (en `project/backlog/staging/`) |
|---|---|---|---|
| **Laureano** | Firmware Teensy — red de seguridad (Track A, push ≤26-may). Prioridad #1 técnica. | **#115** | `programa-laureano-teensy-resiliencia.md` (865 l) |
| **Lucio** | Visión RPi — quick-wins Sprint 1 (Track B) | **#116** | `programa-lucio-rpi-vision.md` (651 l) |
| **Benjamin** | systemd #108 + **gate de banco de todo el equipo** | **#117** | `programa-benjamin-rpi-hardware.md` (661 l) |
| **Vos (Enzo)** | Coordinar, destrabar, aprobar | este issue | `programa-enzo-coordinacion-validacion.md` (338 l) |

## Tus 2 acciones de destrabe (Sprint 0 — sin esto nada fluye)

Siguen siendo las de #107, ahora con herramienta:
1. ~~**Mergear PR #101**~~ — ✅ **YA está en `main`** (al 2026-05-31).
2. **Correr el triage #91** ~~(vencido)~~ — superado por el régimen 31-may. Tu doc trae un **guion de 60 min** para hacerlo usando #114 como orden maestro.

## Tu documento (`programa-enzo-coordinacion-validacion.md`) tiene

- Mapa del tablero por alumno con orden de issues.
- Guion paso a paso del triage #91 (60 min).
- **Checklist de aprobación de PRs reutilizable** (base + Teensy + Python + systemd) — tu activo más importante: te deja aprobar sin ser cuello de botella. Criterio central: *banco antes de mergear firmware, sin excepción*.
- Definición operativa del gate amarillo (qué dejás pasar en freeze blando).
- Ritmo diario de los 8 días + guion literal de la reunión de arranque de 15 min para romper la inercia (7 días sin un commit).

## Cómo distribuir los docs

Los 4 docs están en `project/backlog/staging/` en el working tree (NO commiteados — son propuestas a validar, no código del robot). **Vos hacés llegar a cada uno su doc** (mandáselo / pasáselo por donde trabajen). Cada issue de arranque (#115/#116/#117) ya tiene el mensaje corto con "lo primero que hace hoy", así que pueden empezar aunque el doc largo tarde en llegarles.

## El mensaje, sin vueltas

El cuello del proyecto no es diseño — el plan y el código propuesto ya están. Es **arranque**: 7 días sin un commit a 6 semanas de Incheon. La reunión de 15 min de tu doc está pensada para que cada chico salga con una rama abierta hoy. Laureano es el más urgente (Track A cierra el 26-may).

— Gustavo (vía coach director)
