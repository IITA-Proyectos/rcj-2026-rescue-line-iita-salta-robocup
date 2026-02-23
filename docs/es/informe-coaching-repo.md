# Informe de coaching del repositorio (RCJ Rescue Line) — IITA Salta

**Fecha de creación:** 2026-02-23 (America/Argentina/Salta)  
**Creado por:** AI ChatGPT 5.2 (GPT-5.2 Pro)  
**A pedido de:** Gustavo Viollaz  
**Repositorio analizado:** `IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup` (rama `main`)  
**Estándar del repo:** ICRS v1.1 L2 (`AI-INSTRUCTIONS.md`)  
**Idioma:** Este documento vive en `docs/es/` (español = fuente). `docs/en/` es mirror auto-generado (**NO EDITAR**).

---

## Objetivo

Este informe es una revisión técnica-profesional del repositorio y del estado del proyecto, con foco en:

- **Competencia**: RoboCupJunior Rescue Line (baseline: reglas 2025; nota: existen borradores 2026).
- **Rendimiento competitivo**: robustez, repetibilidad, tiempo, y control de fallas.
- **TDP / Documentación**: evidencias y artefactos típicos exigidos por plantillas/rúbricas (TDP, BOM, video técnico, poster).
- **Buenas prácticas**: lo que tienden a hacer equipos fuertes (ingeniería + pruebas + trazabilidad).

> Importante: esta auditoría se basa en lo visible al momento de la revisión (2026-02-23). Si luego se agregaron archivos (p. ej. en `hardware/` o `testing/`), este informe debe actualizarse.

---

## Normalización aplicada (convenciones del repo)

Según el README y `AI-INSTRUCTIONS.md`, la documentación se organiza así:

- `docs/es/`: documentación fuente en español (verdad).
- `docs/en/`: espejo auto-generado en inglés (**no se edita**).
- Convención sugerida para nombres de archivos: **kebab-case** en minúsculas (ej.: `yolo-raspberry.md`).
- Proceso de cambios: **todo cambio debería nacer de un Issue** y entrar por PR (ver `CONTRIBUTING.md` y `AI-INSTRUCTIONS.md`).

**Nombre y ubicación recomendada para este informe:**
- ✅ `docs/es/informe-coaching-repo.md` (este archivo)

---

## Resumen ejecutivo (lo más importante en 2 minutos)

### Puntos fuertes (señales de equipo “serio”)
1. **Repositorio con estructura ICRS clara** (software/hardware/docs/testing/journal/research/competition/project).  
2. **Arquitectura de doble procesador** bien planteada: Teensy (tiempo real) + Raspberry Pi (visión/IA).  
3. **Documentación técnica útil** ya existente (comunicaciones RPi↔Teensy, YOLO en Raspberry, librerías del firmware).  
4. **Reglas de contribución estilo industria** (Conventional Commits, PR con evidencia, declaración de uso de IA).

### Puntos a mejorar (lo que más suele separar “andar” de “ganar”)
1. **Trazabilidad de trabajo**: el repo muestra 0 Issues → falta backlog “jugable” (tareas, responsables, fechas, riesgos).  
2. **Evidencia de testing con resultados**: se declara `testing/`, pero no hay un índice/tabla de pruebas claramente accesible.  
3. **TDP readiness**: para puntaje alto suele faltar (o no estar a 1 clic): diagrama eléctrico/power tree, esquemáticos/PCB, BOM oficial, CAD con medidas, ubicación física de sensores, y métricas de performance.

### Riesgos técnicos competitivos detectados (prioridad alta)
- Comparación de strings por puntero en `drivebase.cpp` (bug probable).
- Posible mezcla de unidades mm/cm en control por distancia.
- Lógica con `delay()` / bucles bloqueantes en firmware: latencia y pérdida de eventos.

---

## Evidencias revisadas (links internos)

Documentos clave ya existentes:
- `docs/es/comunicacion-rpi-teensy.md`
- `docs/es/yolo-raspberry.md`
- `docs/es/librerias-firmware.md`

Políticas del repo:
- `README.md` (estructura, robot, links a docs)
- `CONTRIBUTING.md` (commits/branches/PRs/IA)
- `AI-INSTRUCTIONS.md` (ICRS y reglas de proceso)

Código con señales relevantes:
- `software/teensy/firmware/src/main.cpp`
- `software/teensy/firmware/lib/drivebase/drivebase.cpp`
- `software/teensy/firmware/lib/claw/claw.h`

---

## Evaluación por área

### 1) Proceso y gestión (lo que el repo “dice” vs lo que “se ve”)

**Lo que el repo dice que se debe hacer (muy bien):**
- Todo trabajo nace de un **Issue**.
- Cambios entran por PR con **evidencia de testing**.
- Se declara uso de IA.

**Lo que hoy se observa:**
- Pestaña “Issues” en 0 → **gap entre proceso ideal y práctica real**.

**Recomendación concreta (acción):**
- Activar un flujo mínimo:
  - 1 Issue por feature (ej.: “Fix unidades ToF”, “No-blocking FSM”, “Tabla de pruebas gaps”).
  - labels: `bug`, `enhancement`, `docs`, `hardware`, `testing`, `competition`.
  - milestones: “Roboliga / Regional / Nacional / Mundial”.

> Los equipos ganadores no se diferencian por “ideas”: se diferencian por tener un sistema que hace que las ideas lleguen a pista y queden estables.

---

### 2) Documentación y TDP (qué tan listos están para la grilla)

#### 2.1 Lo que ya está fuerte
- **Comunicaciones** documentadas con tabla y bytes (bien para TDP).
- **Pipeline de visión** explicado (mejor si se agregan métricas).
- **Dependencias** y librerías listadas (reduce preguntas del juez).

#### 2.2 Lo que falta (o no está visible/a 1 clic)
Para TDP y rubricas típicas, falta consolidar en un solo lugar:

**Hardware**
- Diagrama de bloques del robot (alto nivel).
- Diagrama eléctrico + “power tree” (batería → reguladores → cargas).
- Esquemáticos/PCB (PDF + fuente).
- Layout físico de sensores (foto + dibujo + medidas).
- BOM completa usando la **plantilla oficial**.

**Software**
- Diagrama de estados (linea/rescate/depositar) en gráfico (flowchart).
- Descripción de algoritmos (línea, verdes, gaps, obstáculos, rescate) con “casos borde”.
- Configuración y calibración (qué parámetros existen y cómo se ajustan).

**Testing**
- Tabla de pruebas + resultados (éxito %, tiempo, modos de falla).
- Videos/links internos por feature.
- Logs (aunque sea CSV) por corrida para poder comparar mejoras.

---

### 3) Firmware Teensy (robustez y control)

#### 3.1 Fortalezas
- Estructura modular (`drivebase`, `claw`, PID, sensores).
- Sensor suite competitiva (IMU, ToF, color, ultrasónicos, encoders).
- Máquina de estados clara a nivel de intención.

#### 3.2 Riesgos / bugs probables (alta prioridad)

**(A) Comparación incorrecta de strings**
En `software/teensy/firmware/lib/drivebase/drivebase.cpp` se observa patrón del tipo:
- `if (this->id == "FL" || this->id == "BL") ...`

En C/C++ eso compara **punteros**, no contenido. Es un bug clásico que puede “funcionar” por casualidad y romperse luego.

✅ Recomendación:
- reemplazar por `strcmp(id, "FL")==0` o, mejor, usar `enum MotorID`.

**(B) Unidades mm vs cm**
En `src/main.cpp` se usan lecturas `readRangeContinuousMillimeters()` (mm), pero constantes comentadas en cm.
Si se mezclan unidades, el control se vuelve errático (sobre-corrección o lentitud).

✅ Recomendación:
- Definir una única unidad (mm recomendado) y normalizar todo en `config.h`.

**(C) Bloqueos / delays**
Bucles `while(rutina==...)` con `delay()` y acciones largas hacen al robot lento para reaccionar y pueden degradar la comunicación serial.

✅ Recomendación:
- FSM no bloqueante por “ticks” usando `millis()`/`elapsedMillis`.

---

### 4) Raspberry Pi (visión + IA)

#### 4.1 Fortalezas
- Uso de ONNX Runtime + ultralytics (en CPU) es un camino válido si está medido.
- Multihilo / separación de captura e inferencia (según docs).

#### 4.2 Recomendación competitiva (lo que hacen equipos fuertes)
Medir y registrar, como si fuera telemetría de Fórmula 1:
- FPS real (promedio y percentiles).
- Latencia de inferencia (ms).
- Tasa de detección correcta (por clase) en pista real.
- Robustez a iluminación (frío/cálido, sombras, reflejos, cámara sucia).

Sin números, la IA suele sentirse “mágica” hasta que el día de la competencia deja de serlo.

---

## 5) Testing y evidencia

**Estado actual:**
- La estructura del repo contempla `testing/`, pero no se encontró un `testing/README.md` que actúe como índice.
- En `CONTRIBUTING.md` se exige evidencia en PR (muy bien).

**Recomendación mínima (alta rentabilidad):**
Crear `testing/README.md` con una tabla simple:

| Feature | Setup | Métrica | Resultado | Evidencia | Fecha |
|---|---|---|---|---|---|

Y dentro de `testing/`:
- `videos/` (mp4 cortos por feature)
- `logs/` (CSV)
- `photos/` (setup)

---

## Checklist de TDP (para transformar el repo en “TDP-ready”)

> Esta lista está pensada como checklist de producción. No discute teoría: apunta a lo que el juez puede evaluar rápido.

### Sección Hardware
- [ ] Diagrama de bloques del sistema (Teensy/RPi/sensores/actuadores).
- [ ] Diagrama eléctrico / power tree.
- [ ] Esquemático (PDF + fuente).
- [ ] PCB (si existe) + revisiones (`rev-a`, `rev-b`).
- [ ] Fotos del robot (4 vistas) + dimensiones.
- [ ] Ubicación de sensores (foto + dibujo + distancias).
- [ ] BOM completa (en template oficial) + proveedores + costos.

### Sección Software
- [ ] Arquitectura (qué corre en Teensy vs RPi).
- [ ] Máquina de estados (flowchart).
- [ ] Algoritmos clave y “casos borde”.
- [ ] Parámetros / calibración (cómo, cuándo, con qué criterio).
- [ ] Gestión de fallas (timeouts, modos safe).

### Sección Validación
- [ ] Plan de pruebas (matriz de features vs condiciones).
- [ ] Resultados cuantitativos (éxito %, tiempos).
- [ ] Videos por feature.
- [ ] Registro de cambios: “cambio → mejora medida”.

---

## Plan de trabajo recomendado (sprints)

### Sprint 1 — Estabilidad (evitar perder rondas por bugs)
- Fix strings / unidades / FSM no bloqueante.
- Watchdog de comunicación RPi↔Teensy.
- Logging mínimo (build + parámetros + resultado).

### Sprint 2 — Cobertura de pista (reglas)
- Gaps, verdes, obstáculos, rampas/seesaw (según disponibilidad).
- Tabla de pruebas con métricas.

### Sprint 3 — Rescate repetible
- Pickup + deposit con tasa de éxito medible.
- Reducción de falsos positivos de visión.

### Sprint 4 — Documentación final (TDP)
- Consolidar hardware + software + testing en un TDP que “se deja leer”.

---

## Próximos pasos sugeridos (para cumplir proceso del repo)

Para subir este documento correctamente según las reglas del repo:
1. Crear un Issue: “Agregar informe de coaching del repositorio”.
2. Crear branch: `docs/informe-coaching-repo`.
3. Commit (Conventional Commits): `docs(docs): add repo coaching report`
4. PR con:
   - resumen de cambio (agrega documento),
   - declaración de IA (ChatGPT 5.2),
   - link al Issue.

---

## Fuentes externas (referencia)

- RoboCupJunior Rescue Line 2025 Rules (PDF):  
  https://junior.robocup.org/wp-content/uploads/2025/02/RCJRescueLine2025-final-1.pdf

- RoboCupJunior Rescue League — Documents (TDP Template / Rubrics / BOM):  
  https://rescue.rcj.cloud/documents

- RoboCupJunior Rescue Line (página general):  
  https://junior.robocup.org/rcj-rescue-line/

- (Contexto) Draft Rules 2026 (pueden cambiar):  
  https://junior.robocup.org/wp-content/uploads/2026/01/RCJRescueLine2026-draft.pdf
