# Auditoria del TDP en rama Bugs-Prioritarios

Fecha: 2026-05-22
Archivo revisado: `TDP.md`
Rama local: `Bugs-Prioritarios`
Repo: `IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup`

## Diagnostico corto

El TDP actual ya tiene bastante texto, pero todavia no esta en condicion de puntaje alto. El problema principal no es "falta escribir mas"; es que el documento:

- no usa la ubicacion/estructura pedida en los issues (`docs/tdp/TDP-IITA-2026.md`);
- no sigue de forma estricta la plantilla oficial 2026;
- promete pruebas, metricas, diagramas y fotos que no estan citadas o no existen en la rama local;
- mezcla texto generico con afirmaciones fuertes no demostradas;
- tiene errores de Markdown que rompen secciones completas;
- no cruza cada componente contra requirements derivados de reglas RCJ 2026;
- no incorpora los avances ya mergeados en `origin/main`, especialmente `testing/TEST_LOG.md`.

Estimacion honesta: si el juez acepta texto declarativo sin mucha evidencia, podria estar cerca de 20-30/102. Si el juez es estricto con plantilla, diagramas, evidencia y trazabilidad, puede caer a 10-18/102. Para llegar a 80-100 hay que convertirlo en un paquete con evidencias, no solo en un texto largo.

## Issues de GitHub relevantes

| Issue/PR | Estado detectado | Impacto sobre el TDP |
|---|---:|---|
| #46 Armado de TDP | Abierto | Issue padre del TDP. Pide estructura por rubrica, carpeta `docs/tdp/`, template oficial y PDF final. |
| #97 META Documentacion pre-mundial | Abierto | Define meta: TDP 102 pts, actual estimado bajo, potencial 80-90. |
| #98 Plan de ejecucion para 100% | Abierto | Lista tareas T1-T17 para TDP y dependencias. |
| #41 Diagramas de bloques o flujo | Abierto | Bloquea T12 Software architecture diagrams y tambien Poster. |
| #93 Inicializar `testing/TEST_LOG.md` | Cerrado | PR #101 lo mergeo en `main`, pero esta rama local todavia no lo tiene. |
| PR #101 `testing/TEST_LOG.md` | Mergeado 2026-05-19 | Crea template de test log, pero no trae tests historicos reales. Hay que mergear/rebasear o copiarlo. |
| #95 Validar fidelidad tecnica | Abierto | Antes de copiar docs/es al TDP, verificar que no digan bugs ya arreglados. |
| #96 BOM actualizado | Abierto | Bloquea electronica: BOM oficial, componentes, costos, links, funcion. |

## Hallazgos locales importantes

- `TDP.md` esta sin trackear en la rama local.
- `software/teensy/firmware/variables_doc.md` contiene el mismo contenido que `TDP.md` o parece haber sido usado como copia. Eso es un error fuerte: un TDP no debe vivir dentro de firmware ni llamarse `variables_doc.md`.
- La rama local esta 1 commit adelante y 17 commits atras de `origin/main`.
- En la rama local `testing/` tiene solo `.gitkeep`, aunque en `origin/main` ya existen `testing/README.md` y `testing/TEST_LOG.md`.
- `origin/main` tiene `docs/es/analisis-documentacion-rubricas-2026-05-10.md`, que esta rama local no tiene.

## Errores criticos del TDP actual

### 1. Ubicacion y nombre del archivo

Error: el archivo esta como `TDP.md` en la raiz y no como `docs/tdp/TDP-IITA-2026.md`, que es lo pedido por #46 y #98.

Arreglo:

1. Crear `docs/tdp/`.
2. Mover el documento a `docs/tdp/TDP-IITA-2026.md`.
3. Mantener `TDP.md` raiz solo si se usa como redirect/indice, o eliminarlo cuando haya PR.

### 2. No esta basado fielmente en la plantilla oficial 2026

Error: la rubrica oficial 2026 evalua 17 items T1-T17. El TDP usa secciones parecidas, pero no demuestra cada criterio con claridad.

Arreglo:

- Descargar/usar `TDP_Template_Line_Maze.docx`.
- Crear headings que mapeen 1:1 contra T1-T17.
- Antes de cada seccion, decidir que evidencia la sostiene.

### 3. Project Planning: faltan requirements reales

Lineas relevantes: `TDP.md:34`, `TDP.md:42`, `TDP.md:204`.

Error: hay objetivos generales, timeline y success criteria, pero no una lista de requirements derivados de reglas RCJ 2026. Ejemplos que faltan: dimensiones, peso si aplica, rampas, seesaw, victimas, zona de evacuacion, obstaculos, limites de intervencion humana, comunicacion, energia, seguridad.

Arreglo:

- Crear tabla: `Requirement`, `Regla/criterio`, `Decision de diseño`, `Modulo que lo cumple`, `Evidencia`.
- Citar reglas oficiales 2026.

### 4. Plan de proyecto demasiado declarativo

Lineas: `TDP.md:61`, `TDP.md:204`, `TDP.md:221`.

Error: las responsabilidades son por rol, pero el milestone schedule no asigna owner real ni evidencia de completion. Los gates existen como texto, no como proceso verificable.

Arreglo:

- Tabla con owner por milestone.
- Link a issue/PR/test/foto/video que demuestre cada hito.
- Incluir cambios historicos reales, no solo fechas deseadas.

### 5. Integration Plan incompleto

Lineas: `TDP.md:859`, `TDP.md:875`, `TDP.md:925`.

Error: hay diagramas parciales, pero no hay matriz `componente -> requirement -> comunicacion -> evidencia`. La rubrica pide claridad sobre conexiones y que requirements cumple cada parte.

Arreglo:

- Diagrama de sistema completo.
- Tabla por componente: RPi, Teensy, PCB, motores, encoders, camara, BNO055, APDS9960, ToF, ultrasonicos, servos, bateria.

### 6. Seccion mecanica sin imagenes reales ni CAD referenciado

Lineas: `TDP.md:330` a `TDP.md:577`.

Error: describe muy bien muchas piezas, pero no muestra fotos ortogonales, CAD, medidas, renders, materiales con parametros de impresion ni ubicacion de sensores.

Arreglo:

- Agregar fotos top/front/side/rear.
- Agregar captura CAD con labels.
- Agregar dimensiones y material de cada modulo.
- Linkear STL/CAD/revision si existen.

### 7. Bloque Markdown roto en mecanica

Lineas: `TDP.md:581` a `TDP.md:640`.

Error: se abre un bloque ```text en `Mechanical Module Interaction Diagram` y no se cierra antes de `##2.3`. Eso hace que gran parte de la seccion quede renderizada como codigo.

Arreglo:

- Cerrar el bloque antes de "Main Mechanical Interfaces".
- Convertir interfaces, quick access features y serviceability a headings/listas normales.

### 8. Headings mal formateados

Lineas: `TDP.md:640`, `TDP.md:679`, `TDP.md:791`.

Error: headings como `##2.3`, `##2.4`, `##2.5` no tienen espacio. Algunos renderizadores no los reconocen como headings.

Arreglo:

- Cambiar a `## 2.3`, `## 2.4`, `## 2.5`.

### 9. Tests mecanicos declarados sin evidencia

Lineas: `TDP.md:679` a `TDP.md:789`.

Error: afirma `More than 300 pickup cycles`, `>95%`, `100%`, etc. sin fecha, tester, setup, numero de corridas, evidencia, video, log ni metodo de medicion.

Arreglo:

- Todo numero debe apuntar a `testing/TEST_LOG.md`.
- Si no existe evidencia, cambiar a "planned validation" o reconstruir el test honestamente.

### 10. Electronica con placeholders

Lineas: `TDP.md:813`, `TDP.md:815`.

Error original: quedaban `[Insert Figure 3]` y `[Insert Figure 4]`. Esto destruia T8/T17.

Estado 2026-05-23: resuelto en el nuevo `TDP.md` con `hardware-overview-2026.png`, `pcb-main-layout-2026.png` y `electronics-schematic-2026.png` en `docs/tdp/assets/`.

Arreglo:

- Reemplazar por fotos/diagramas reales: PCB photo, wiring layout, schematic, power tree.

### 11. Power system insuficiente

Lineas: `TDP.md:831` a `TDP.md:835`.

Error: menciona bateria y regulador, pero faltan corriente maxima, protecciones, fusible/switch, reguladores por rail, consumo RPi/servos/motores, ruido, caidas de tension, conectorado.

Arreglo:

- Agregar power tree: bateria -> switch -> rail motores -> buck 5V -> RPi/logic -> servos/sensores.
- Agregar mediciones de voltaje bajo carga.

### 12. Comunicacion serial incompleta

Lineas: `TDP.md:837` a `TDP.md:846`, `TDP.md:992`.

Error: el protocolo aparece como bytes sueltos. Falta frame completo, direccion, frecuencia, checksum/delimiters si existen, timeout, comportamiento ante perdida de comunicacion.

Arreglo:

- Dibujar sequence diagram RPi -> Teensy.
- Documentar frame exacto desde el codigo actual.
- Agregar errores conocidos y fixes.

### 13. BOM no integrado

Issue: #96.

Error: el TDP lista componentes principales, pero no tiene BOM oficial ni link a archivo actualizado.

Arreglo:

- Crear `hardware/electronics/BOM-2026.xlsx` o tabla Markdown equivalente.
- Incluir modelo, cantidad, proveedor, link, precio, funcion, reemplazo.

### 14. Software architecture no alcanza para T12

Lineas: `TDP.md:889` a `TDP.md:1004`.

Error: hay ASCII diagram y state machine, pero falta:

- flowchart real del main loop Teensy;
- flowchart real de `Main.py`;
- diagrama de comunicacion serial;
- state machine de pinza/rescate;
- class/module diagram;
- pseudocodigo de algoritmos criticos.

Arreglo: ejecutar issue #41 y guardar fuente + PNG/SVG en `docs/diagrams/`.

### 15. Secciones de software demasiado genericas

Lineas: `TDP.md:1006` a `TDP.md:1057`.

Error: frases como "hybrid pipeline", "adaptive line-following", "sensor fusion", "fault-tolerant recovery" suenan bien, pero no explican algoritmo, parametros, casos borde, ni ventaja medida.

Arreglo:

- Para cada algoritmo: input, output, pseudocodigo, parametros, caso borde, evidencia.

### 16. Tests de software sin pruebas reales

Lineas: `TDP.md:1059` a `TDP.md:1133`.

Error: enumera unit/integration/stress/robustness tests, pero no hay archivos de tests, comandos, logs, videos ni resultados reales.

Arreglo:

- Vincular a `testing/TEST_LOG.md`.
- Agregar comandos reproducibles si hay tests automatizados.
- Si no hay tests unitarios, no llamarlos "unit tests"; llamarlos "manual module validation" hasta que existan.

### 17. Performance Evaluation sin metodologia

Lineas: `TDP.md:1149` a `TDP.md:1228`.

Error: muestra numeros aproximados (`10 cm/s`, `14-20 FPS`, `90 min`, etc.) sin explicar como se midieron.

Arreglo:

- Para cada metrica: fecha, setup, cantidad de corridas, promedio, desviacion/rango, resultado, link a evidencia.
- Separar "observado informalmente" de "medido".

### 18. Overclaiming: promete puntaje alto sin demostrarlo

Lineas: `TDP.md:1146`, `TDP.md:1272`.

Error: "satisfy the highest evaluation criteria" es riesgoso. Un juez espera evidencia; si ve placeholders y no ve logs, esa frase resta credibilidad.

Arreglo:

- Cambiar tono a factual: "The design addresses the criteria through..." y linkear evidencia.

### 19. Seccion Document se autoevalua en lugar de mejorar

Lineas: `TDP.md:1231` a `TDP.md:1266`.

Error: la seccion dice que el documento es claro/formateado, pero todavia contiene placeholders, headings rotos y seccion 6.3 faltante.

Arreglo:

- Usar esa seccion solo si la plantilla oficial la pide.
- Completar `6.3` o renumerar.
- Eliminar "figure placeholders" de la lista de formatting; placeholders no son virtud.

### 20. Extra content final poco profesional

Lineas: `TDP.md:1286` a `TDP.md:1296`.

Error: `## . extra content`, links sueltos y "Thank you for reading" quedan informales para entrega.

Arreglo:

- Reemplazar por `References` / `Links`.
- Incluir links con descripcion y fecha de consulta si corresponde.

## Prioridad de trabajo recomendada

### Bloque 0: sincronizar base

1. Traer a la rama los 17 commits que faltan de `origin/main` o cherry-pick de PR #101 si no quieren mezclar todo.
2. Recuperar `testing/README.md`, `testing/TEST_LOG.md` y `docs/es/analisis-documentacion-rubricas-2026-05-10.md`.
3. Revisar conflictos con `software/teensy/firmware/variables_doc.md` y decidir si debe borrarse o restaurarse a su proposito real.

### Bloque 1: ganar puntos rapidos

1. Crear `docs/tdp/TDP-IITA-2026.md`.
2. Arreglar Markdown roto y headings.
3. Eliminar placeholders.
4. Crear indice T1-T17.
5. Agregar links a evidencias ya existentes.

### Bloque 2: evidencias

1. Llenar `testing/TEST_LOG.md` con 5-10 tests reales.
2. Sacar fotos del robot y PCB.
3. Crear diagramas de #41.
4. Crear BOM de #96.
5. Validar fidelidad tecnica de #95.

### Bloque 3: convertir texto generico en puntaje

Para cada seccion:

- escribir que hicieron;
- mostrar diagrama/foto;
- explicar por que esa decision resuelve un requirement;
- demostrar con test/log/video;
- cerrar con limitacion honesta y mejora futura.

## Checklist T1-T17 contra archivo actual

| Tema | Rubrica | Estado actual | Accion |
|---|---|---|---|
| T1 | Requirements | Debil | Lista desde reglas 2026 + matriz requirement/componente. |
| T2 | Project plan | Medio | Agregar owners, issues, PRs, gates reales. |
| T3 | Integration | Debil | Diagrama formal + matriz de interfaces. |
| T4 | Mechanical diagrams | Debil | Fotos/CAD/medidas. |
| T5 | Mechanical submodules | Medio-bajo | Cerrar bloque roto + diagramas de interfaces. |
| T6 | Mechanical innovation | Medio | Foto/sketch/ventaja medible. |
| T7 | Mechanical tests | Debil | TEST_LOG con ciclos reales, setup y evidencia. |
| T8 | Electronic diagrams | Muy debil | Reemplazar placeholders por schematic/PCB/power tree. |
| T9 | Electronic submodules | Medio-bajo | Power tree + wiring + funciones por modulo. |
| T10 | Electronic innovation | Debil | Probar PCB propia con BOM/esquematico/fotos. |
| T11 | Electronic tests | Debil | Voltage/current/noise tests. |
| T12 | Software diagrams | Medio-bajo | Ejecutar #41 completo. |
| T13 | Software innovation | Medio | Pseudocodigo + ventaja medida. |
| T14 | Software tests | Debil | Tests manuales/automatizados reales, no lista declarativa. |
| T15 | Performance | Debil | Metricas con metodo, corridas y conclusion. |
| T16 | Clarity | Medio-bajo | Quitar repeticion, corregir estructura, tono factual. |
| T17 | Formatting | Muy debil | Template oficial + PDF final + placeholders fuera. |

## Regla de oro para no inventar puntaje

Cada numero del TDP debe tener una fuente:

- un test en `testing/TEST_LOG.md`;
- un video/foto;
- un commit/PR;
- una medicion reproducible;
- un documento tecnico en `docs/es` validado contra codigo actual.

Si no tiene fuente, no se borra necesariamente, pero se marca como objetivo, estimacion o observacion preliminar.

## Segunda pasada: cobertura de issues para objetivo 102/102

Estado honesto de lectura:

- Primera pasada: busqueda por TDP/rubrica/documentacion. Cubrio #41, #45, #46, #55, #93, #94, #95, #96, #97, #98 y PR #101.
- Segunda pasada: se reviso tambien el triage de #91, que enumera los 31 issues tecnicos abiertos, y los meta-issues recientes #102, #106, #114, #118, #120-#128.
- No alcanza con "issues sobre TDP" literales: para sacar 100%, el TDP tiene que demostrar un robot confiable con evidencias. Por eso entran tambien issues de bugs, testing y performance.

### Issues que son bloqueantes directos del 100% del TDP

| Issue | Por que bloquea puntaje TDP | Seccion TDP afectada |
|---|---|---|
| #46 | Issue padre. Pide archivo Markdown en docs, estructura por rubrica, template oficial y PDF. | T16, T17, todo el documento |
| #97 | Define roadmap de documentacion pre-mundial y puntaje actual/potencial. | Todas |
| #98 | Plan de ejecucion para TDP 102/102 con T1-T17. | Todas |
| #41 | Faltan flowcharts, comunicacion, FSM y pseudocodigo. | T12, tambien T3 |
| #93 / PR #101 | TEST_LOG existe en main pero esta rama no lo tiene; ademas esta vacio de tests reales. | T7, T11, T14, T15 |
| #94 | Fotos de equipo/robot. Aunque es poster/video, tambien sube T4/T8/T16 del TDP. | T4, T8, T16 |
| #95 | Evita copiar docs obsoletas al TDP. | T16, T15, credibilidad general |
| #96 | BOM actualizado. Sin BOM no se defiende electronica al maximo. | T8, T9, T10 |
| #45 | Poster comparte fotos, datos y diagramas con TDP. | Insumo visual |
| #55 | Video comparte evidencia de robot en accion. | T15, evidencia |

### Issues tecnicos que el TDP debe citar como evidencia o como riesgo resuelto

Estos no son "del TDP" por titulo, pero si el TDP quiere 100%, debe demostrar que el equipo identifico, corrigio o valido estos puntos. Si siguen abiertos, el TDP debe tratarlos como riesgos controlados con plan/test.

| Grupo | Issues | Impacto sobre el documento |
|---|---|---|
| Fail-safe / watchdog / timeouts | #27, #53, #59, #60, #61, #62, #63, #72, #73 | T14/T15: confiabilidad del software y comportamiento ante fallas. |
| Comunicacion RPi-Teensy | #70, #71, #74, #75, #76 | T3/T12/T14: protocolo, rangos, parser, telemetria, perdida de frames. |
| Vision RPi | #64, #65, #66, #68, #81, #120, #124 | T12/T13/T14/T15: pipeline, robustez de camara, dependencias, FPS, tensor/NMS. |
| Movimiento/control | #57, #58, #67, #121, #122, #125, #126, #127 | T13/T15: linea, giros, encoder, PID, performance real. |
| Rescate y scoring | #85, #86, #120, #123, #127, #128 | T1/T13/T15: requisitos RCJ 2026, victimas falsas, LED, salida de cuarto, estrategia de rescate. |
| Hardware/mecanica | #47, #52, #87, #96 | T4-T11: diseno, PCB/BOM, pinout, montaje y mantenimiento. |
| Proceso y evidencia | #91, #102, #106, #114, #117, #118 | T2/T7/T11/T14/T15: triage, asignaciones, banco, TEST_LOG. |

### Para 102/102, cada criterio debe tener este minimo

| Tema | Max | Evidencia obligatoria para aspirar a 100% |
|---|---:|---|
| T1 Requirements | 6 | Tabla desde reglas RCJ 2026: requisito, regla, decision de diseno, modulo, test/evidencia. Incluir victimas falsas, LED, rescue room, rampas, obstaculos, autonomia. |
| T2 Project Plan | 6 | Timeline con owners reales, issues/PRs, gates y fechas. No solo fases genericas. |
| T3 Integration Plan | 6 | Diagrama completo + matriz componente/requisito/interfaz. RPi-Teensy-PCB-sensores-actuadores. |
| T4 Mechanical diagrams | 6 | Fotos ortogonales + CAD/render + medidas + labels. |
| T5 Mechanical submodules | 6 | Chasis, drivebase, claw, corrales, deposito, mounts; interfaces y mantenimiento. |
| T6 Mechanical innovation | 6 | 1-3 innovaciones con foto/sketch, por que son propias, ventaja competitiva y prueba. |
| T7 Mechanical reliability | 6 | TEST_LOG con tests reales de pinza, rampas, golpes, depositos, mantenimiento. |
| T8 Electronic diagrams | 6 | Schematic, PCB, power tree, wiring photo, sensor map. Nada de placeholders. |
| T9 Electronic submodules | 6 | Power rails, reguladores, sensores, actuadores, UART, protecciones, switches. |
| T10 Electronic innovation | 6 | PCB propia: fuente, revision, fotos, BOM, conexion de controladores/sensores/actuadores. |
| T11 Electronic reliability | 6 | Tests de bateria, voltaje bajo carga, resets, ruido, conectores, banco. |
| T12 Software architecture | 6 | Flowchart Teensy, flowchart Main.py, serial sequence, rescue FSM, pseudocodigo, modulo/class diagram. |
| T13 Software innovation | 6 | YOLO/vision hibrida, FSM rescate, sensor fusion, recovery; con parametros y ventaja medida. |
| T14 Software reliability | 6 | Tests de parser, camara, serial, watchdog/timeouts, headless, systemd, fallas inyectadas. |
| T15 Performance evaluation | 6 | Metricas con metodo: corridas completas, FPS, pickup/deposit success, curvas, rescate, fallas y fixes. |
| T16 Clarity | 6 | Texto corto, factual, sin claims inflados, sin contradicciones con codigo actual. |
| T17 Formatting | 6 | Plantilla oficial 2026, PDF final limpio, figuras numeradas, tablas rotuladas, referencias. |

### Politica para llegar al 100% sin mentir

1. No se inventan tests. Se hacen, se reconstruyen con evidencia o se escriben como "planned".
2. No se prometen metricas sin metodo. Todo numero debe tener fecha/setup.
3. Si un issue critico sigue abierto, se documenta como riesgo controlado, no como problema resuelto.
4. Si una mejora no entra antes del submit, el TDP puede igual ganar puntos si muestra ingenieria madura: problema detectado, decision, tradeoff, plan y prueba parcial.
5. Para puntaje maximo, el TDP debe parecer escrito por un equipo que mide, decide y valida, no por un equipo que solo describe piezas.

### Orden duro de trabajo para transformar `TDP.md`

1. Sincronizar esta rama con `origin/main` o cherry-pick de PR #101 para traer `testing/TEST_LOG.md`.
2. Mover `TDP.md` a `docs/tdp/TDP-IITA-2026.md`.
3. Arreglar Markdown roto, headings y placeholders.
4. Crear estructura T1-T17 exacta.
5. Armar matriz Requirements (T1) y matriz Integration (T3).
6. Ejecutar #41: diagramas formales.
7. Ejecutar #96: BOM.
8. Poblar TEST_LOG con minimo 10 tests reales, distribuidos en MECH/ELEC/SW/PERF.
9. Incorporar fotos/diagramas/referencias.
10. Reescribir claims genericos como evidencia concreta.
11. Hacer self-review con la rubrica oficial 2026 y marcar puntaje estimado por cada T.

## Estado despues de la reescritura inicial

Fecha: 2026-05-22.

Archivos actualizados:

- `TDP.md`: reescrito como fuente principal T1-T17, con requisitos, plan, diagramas Mermaid, mecanica, electronica, software, IA, tests y performance.
- `docs/tdp/TDP-IITA-2026.md`: punto de entrada pedido por los issues de documentacion.
- `testing/README.md` y `testing/TEST_LOG.md`: recuperada la estructura de bitacora para evidencia T7/T11/T14/T15.
- `software/teensy/firmware/variables_doc.md`: convertido a aviso deprecado para evitar una copia vieja y contradictoria del TDP dentro del firmware.

### Estimacion honesta tras esta pasada

| Criterio | Antes | Ahora | Para 5-6 real |
|---|---:|---:|---|
| T1 Requirements | bajo | alto | Verificar reglas 2026 finales contra cada requirement. |
| T2 Project plan | bajo | medio-alto | Completar fechas reales/owners si el equipo quiere defenderlo oralmente. |
| T3 Integration | medio | alto | Renderizar diagramas en PNG/SVG para PDF. |
| T4 Mechanical diagrams | medio | medio-alto | Agregar fotos actuales del robot real, no solo CAD. |
| T5 Mechanical modules | medio | alto | Mantener links a CAD/STL. |
| T6 Mechanical innovation | medio | alto | Agregar 1 imagen/sketch de la garra y deposito. |
| T7 Mechanical reliability | bajo | medio | Cargar tests reales en `testing/TEST_LOG.md`. |
| T8 Electronic diagrams | medio | alto | Renderizar schematic/PCB y power tree en PDF. |
| T9 Electronic modules | medio | alto | Cerrar BOM oficial #96. |
| T10 Electronic innovation | medio | alto | Fotos PCB + explicacion de power rails. |
| T11 Electronic reliability | bajo | medio | Medir voltajes bajo carga y serial/sensores. |
| T12 Software architecture | medio | alto | Renderizar flowcharts/UML; asegurar que coinciden con codigo actual. |
| T13 Software innovation | medio | alto | Resolver runtime ONNX/TFLite y class-map antes de final. |
| T14 Software reliability | bajo | medio | Tests reales de camara, UART, crash, timeouts. |
| T15 Performance | bajo | medio | FPS real, pickup/deposit success, runDistance/runAngle error. |
| T16 Clarity | bajo | alto | Relectura final por coach/equipo. |
| T17 Formatting | bajo | medio | Pasar a template oficial DOCX/PDF. |

Estimacion actual si se entrega tal cual en Markdown: 55-70/102, dependiendo de cuan estricto sea el juez con evidencia y template.

Estimacion si se completan TEST_LOG + BOM + fotos + PDF oficial + fixes de consistencia: 90-102/102.

### Bloqueos restantes que no se pueden inventar

1. `testing/TEST_LOG.md` todavia no tiene tests reales. Sin esto no hay 100%.
2. Hay que decidir y documentar el runtime final de IA: docs dicen ONNX, `Main.py` actual usa TFLite.
3. Hay que validar el mapeo de clases de victimas: docs dicen `0 negro / 1 plateado`, pero el control actual debe compararse contra labels reales del modelo.
4. Hay que validar/fijar la mascara plateada: thresholds HSV no deben aplicarse sobre imagen BGR.
5. Hay que cerrar BOM oficial #96 con costo/cantidad/source final.
6. Hay que exportar a PDF usando la plantilla oficial RCJ 2026; si no se respeta formato/template, T17 puede caer fuerte.

## Evidencia visual agregada despues del benchmark Airborne

Fecha: 2026-05-23.

El TDP ahora incorpora cuatro assets visuales nuevos en `docs/tdp/assets/`:

- `robot-evolution-2023-2025.jpg`: secuencia de evolucion del robot, reconstruccion previa a competencia, robot listo y clasificacion mundial. Suma en T2, T4, T15 y narrativa de iteracion.
- `hardware-overview-2026.png`: diagrama visual de bateria, reguladores, motores, servos, sensores, Raspberry Pi y Teensy. Suma en T3, T8 y T9.
- `pcb-main-layout-2026.png`: layout de PCB custom con ruteo y forma de placa. Suma fuerte en T8 y T10.
- `electronics-schematic-2026.png`: esquematico con power, sensors, Teensy, COM, indicators y actuators. Suma fuerte en T8, T9 y T11.

Impacto estimado: estas imagenes suben el techo del TDP porque corrigen una de las diferencias mas claras con Airborne: evidencia visual embebida. Aun asi, no reemplazan los datos numericos de performance. Para acercarse a 95-100 sigue haciendo falta completar `TEST_LOG.md` con mediciones reales.
