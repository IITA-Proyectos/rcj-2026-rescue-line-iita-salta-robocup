# `testing/` - Bitacora de tests del equipo

Esta carpeta contiene la evidencia documental de los tests de banco y pista rumbo a RoboCupJunior Rescue Line 2026.

Es la respuesta del equipo al criterio **Reliability Tests and quality assurance** de la rubrica oficial TDP 2026. Ese criterio aparece en Mechanical, Electronic, Software y Performance, por lo que esta carpeta afecta una parte grande del puntaje del TDP.

## Archivos

- [`TEST_LOG.md`](TEST_LOG.md): bitacora cronologica. Cada test usa un ID `T-XXX`.
- `tests/`: reservada para dividir pruebas futuras si el log crece durante junio.

## Regla de oro

Despues de cada ensayo, el responsable de la sesion escribe una entrada en `TEST_LOG.md` antes de irse del laboratorio.

Si no se anota, el test no existe para el TDP.

## Como abrir un test nuevo

1. Abrir `TEST_LOG.md`.
2. Buscar el ultimo ID (`T-001`, `T-002`, etc.) y usar el siguiente.
3. Copiar la plantilla de la seccion 3.
4. Completar setup, procedimiento, resultados y accion.
5. Agregar la fila correspondiente en el indice por categoria.
6. Commit sugerido: `docs(testing): T-XXX <titulo corto>`.

## Categorias

| Tag | Seccion rubrica | Ejemplos |
|---|---|---|
| `[MECH]` | T7 Mechanical reliability | chasis, drivebase, pinza, sensores fijos |
| `[ELEC]` | T11 Electronic reliability | power tree, ruido, voltaje bajo carga, conexiones |
| `[SW]` | T14 Software reliability | line track, FSM rescate, vision, comms |
| `[PERF]` | T15 Performance evaluation | corridas completas, fallas, arreglos y comparativas |

Un test puede tener dos tags si cruza categorias, por ejemplo `[MECH][PERF]`.

## Mantenimiento

Rotacion semanal entre Laureano, Benjamin, Lucio y Enzo. La bitacora es una regla del equipo: si no hay evidencia, no hay puntaje.

Issue padre: #93 - Inicializar `testing/TEST_LOG.md`.
