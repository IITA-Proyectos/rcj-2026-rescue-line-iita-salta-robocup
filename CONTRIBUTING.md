# Guía de Contribución

## Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scope): descripción
fix(scope): descripción
docs(scope): descripción
test(scope): descripción
hardware(scope): descripción
```

Scopes válidos: `teensy`, `rpi`, `vision`, `control`, `comms`, `power`, `mechanics`, `docs`

## Branches

- `main`: rama protegida, solo via PR
- `feat/<nombre>`: nuevas funcionalidades
- `fix/<nombre>`: correcciones
- `docs/<nombre>`: documentación

## Pull Requests

Cada PR debe incluir:

1. Resumen técnico de los cambios
2. Evidencia de testing (fotos, videos, logs)
3. Declaración de uso de IA (si aplica)
4. Issue vinculado

## Issues

Todo trabajo debe originarse en un Issue. Usar las labels definidas en el repositorio.

## Flujo de trabajo paso a paso

A continuación se describe el proceso completo que deben seguir **Benja, Laureano y Lucio** (y cualquier otro miembro del equipo) para contribuir al repositorio de forma ordenada y pedagógica. Cada paso incluye ejemplos y explicaciones para que sea fácil de seguir.

1. **Seleccionar un Issue** 📌
   - Abrir la sección de *Issues* en GitHub.
   - Escoger uno de prioridad P0 (o la que corresponda) que normalmente está referenciado desde `AUDIT-ACTION-PLAN.md`.
   - Leer con atención el título y la descripción.
   - Si no entiendes algo, si hay dudas o necesitas más información, usa siempre **el hilo de comentarios del mismo Issue** para preguntar, debatir o compartir hallazgos. Todas las comunicaciones relacionadas deben quedar en el Issue.

2. **Entender el problema y la solución** 🔍
   - Investiga en la documentación, en otros archivos del repo o prueba en el robot si es necesario.
   - Discute esas ideas en el Issue para que quede claro el alcance: ¿qué se pide? ¿por qué es importante? ¿cuál es la forma propuesta de solucionarlo?
   - Sólo cuando tengas claro el objetivo, procede al siguiente paso.

3. **Crear una rama de trabajo** 🌿
   - Asegúrate de que tu `main` local está actualizado: `git checkout main` y `git pull origin main`.
   - Crear una rama nueva paralela a `main` con un nombre descriptivo, por ejemplo:
     ```bash
     git checkout -b feat/ISSUE-123-sensor-calibration
     ```
     o `fix/ISSUE-45-typo` según tipo de cambio. Incluye el número de Issue para facilitar el seguimiento.
   - En esa rama solo resuelve lo que pide el Issue; no mezcles tareas.

4. **Implementar el cambio** 🛠️
   - Modificar el código, la documentación, etc., siguiendo los convenciones de commits mencionadas en este archivo.
   - Haz commits pequeños y claros. Ejemplos:
     ```
     feat(vision): añadir filtro de ruido HDMI en cámara
     fix(rpi): corregir inicialización de GPIO 17
     ```
   - Puedes incluir pruebas locales, fotos, videos o logs que demuestren que tu cambio funciona.

5. **Abrir una Pull Request (PR)** 🔁
   - Cuando el código esté listo, empuja la rama al remoto: `git push origin feat/ISSUE-123-sensor-calibration`.
   - En GitHub, crea una PR apuntando a `main`.
   - Usa este formato de descripción para la PR:
     ```markdown
     ### Descripción
     - ¿Qué hace este cambio?
     - ¿Por qué es necesario?

     ### Cómo probarlo
     1. Pasos para reproducir (ej. conectar el sensor X, correr `python3 test.py`).
     2. Resultados esperados.

     ### Evidencia
     - Fotos / videos / capturas de pantalla
     - Logs o resultados de testing.

     ### Issue relacionado
     - Closes #123
     
     ### Uso de IA (si hay)
     - Herramienta: ChatGPT 4
     - Se generó el algoritmo de filtrado y luego se ajustó manualmente.
     ```
   - Vincula el Issue usando `Closes #N` o `Fixes #N` para que se cierre automáticamente al fusionar.

6. **Mover el Issue y probar en clase** 📝
   - Cambia el estado del Issue en el tablero de backlog: de "en progreso" a "revisión".
   - En la próxima clase, prueben el cambio en el robot real. Si funciona, aprueban la PR. Si aún falta, comentan en la PR y el Issue y mejoran el código.

7. **Fusionar y actualizar ramas** 🔄
   - Una vez aprobada la PR, se fusiona en `main` (usualmente con *squash and merge* o como se acuerde).
   - Actualiza tu repositorio local:
     ```bash
     git checkout main
     git pull origin main
     ```
   - Si tienes otras ramas en las que estás trabajando, integra los últimos cambios de `main` usando `merge` o `rebase`:
     ```bash
     git checkout otra-rama
     git merge main    # o git rebase main
     ```
     Resuelve cualquier conflicto que aparezca.
   - Si no tienes ninguna rama activa, estás listo para tomar un nuevo Issue.

   > 💡 **Consejo**: si mientras trabajabas en una rama aparece un cambio ajeno en `main`, actualiza antes de terminar tu trabajo para evitar conflictos grandes. Saca `git pull` en `main` y luego haz `git rebase main` en tu rama, o crea una rama nueva a partir del `main` actualizado si prefieres.

8. **Otras aportaciones** 💬
   - Cualquier idea de mejora, sugerencia, investigación o propuesta que no sea directamente un bug/tarea técnica, **debe abrirse como una _Discussion_** en GitHub.
   - Esto mantiene los Issues enfocados en trabajo concreto y da lugar a debates más abiertos.

---

Con este flujo cada uno puede contribuir de manera ordenada, transparente y pedagógica. ¡Manos a la obra y buen código! 🧑‍💻🤖

## Uso de IA

Si se usó IA (ChatGPT, Claude, Copilot, etc.) en el desarrollo, declararlo en el PR con:

- Herramienta usada
- Qué parte del código fue asistida
- Si se revisó/modificó manualmente
