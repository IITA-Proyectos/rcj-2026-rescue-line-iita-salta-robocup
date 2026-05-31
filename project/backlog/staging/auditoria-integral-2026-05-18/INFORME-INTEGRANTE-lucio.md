# Informe de Desempeño — Lucio Saucedo (@luciouriel2011)

**Para:** Enzo Juarez (@enzzo19), coach del equipo
**De:** Coach senior / auditoría integral (rol de apoyo a coaching)
**Fecha:** 2026-05-31 (datos de la corrida de auditoría 2026-05-18)
**Rol nominal de Lucio:** Raspberry Pi 4B — Visión (OpenCV + YOLO)
**Repo / branch:** `rcj-2026-rescue-line-iita-salta-robocup` · `feature/initialize-testing-log` (= `main` post-PR #101)
**Insumos:** `equipo-02-lucio.md` (minería git/gh), `rpi-01-vision.md` (calidad del módulo percepción), `rpi-02-decision.md` (calidad de la capa FSM/decisión), `doc-01-tdp.md` (estado del TDP). Verificado contra `git log/blame --all` y `gh`.

> **Cómo leer este informe.** Esto NO es una lista de reproches. Es una lectura honesta para que vos, como coach, sepas dónde está parado Lucio y qué palancas tenés para hacerlo crecer antes de Incheon (30-jun). Sigo la convención del equipo: cada problema viene con **riesgo de NO actuar**, **riesgo de actuar** y **tiempo**, porque mover a una persona también tiene costo. El objetivo es el equipo, no la calificación de nadie.
>
> **Aclaración de identidad:** Lucio Saucedo = @luciouriel2011. NO confundir con Laureano Monteros (firmware) ni con ningún "Lautaro" (ese nombre no existe en el equipo, es un error de tipeo histórico por Laureano).

---

## 1. Resumen de actividad (los números, sin maquillaje)

Minería de `git log --all --no-merges` + `gh pr/issue list`, filtros `lucio`/`luciouriel`/`Saucedo`. Todos los números están verificados contra git, no son estimaciones.

### 1.1 Commits

**Total autorado por Lucio en todas las ramas, sin merges: 5.**

| # | Hash | Fecha | Mensaje | Qué es realmente |
|---|------|-------|---------|------------------|
| 1 | `a8241e2` | 2026-03-07 | `fix(teensy): cambio de comparacion de punteros` | **Fix real de C++** (firmware, NO visión). Mergeado vía PR #36. |
| 2 | `848f142` | 2026-03-14 | `Update README with Teensy loader download link` | 1 línea en README. Trivial, pero sobrevive en `main`. |
| 3 | `795cc8e` | 2026-03-16 | `docs/comentarios en codigos` | Pase de comentarios (PR #42, **abierto sin mergear**). Sobreescrito en visión. |
| 4 | `19f6055` | 2026-03-23 | `docs(tdp): base de tdp` | Base del TDP + `consumo.md`. **Varado en rama sin mergear.** |
| 5 | `53657fb` | 2026-04-25 | `feat(docs): agregue mas imagenes al TDP` | 3 imágenes + edición menor del TDP. Misma rama sin mergear. |

(Existe un 6º hash, `e0616e5`, pero es un **merge commit** — no es autoría original, no cuenta como trabajo.)

### 1.2 Volumen comparado con el resto del equipo

Commits no-merge, todas las ramas (`git shortlog --all --no-merges -sn`):

```
gviollaz (Gustavo)        27
benjaminvillagran          23   ┐ Benjamín ≈ 26 sumando su segundo handle
Laureano Monteros           6   │  ("Benjamin Villagran" +3)
lucio                       5   ┘
Enzo Juarez                 3
```

**Lucio es el de menor volumen entre los tres alumnos** (Laureano 6, Benjamín ~26, Lucio 5). El volumen por sí solo no condena a nadie — pero combinado con *en qué* se gastó ese volumen (sección 2), sí dibuja un patrón.

### 1.3 GitHub (PRs, issues, reviews)

- **PRs autorados: 2.**
  - #36 (`comparacion_de_punteros_res`) → **MERGED**. Bueno.
  - #42 (`documentation_and_diagrams`) → **OPEN desde 2026-03-16** (>2,5 meses). Recibió feedback tuyo el 2026-04-29 y quedó sin respuesta.
- **Issues abiertos por Lucio: 0.** No abrió ni un finding propio en todo el proyecto.
- **PRs de compañeros revisados por Lucio: 0.** No participó del code-review del equipo en ningún momento.

### 1.4 Línea de tiempo (la señal más preocupante)

```
2026-03-07  fix(teensy) punteros        <- pico técnico
2026-03-14  README link
2026-03-16  comentarios (PR #42)
2026-03-23  base TDP
2026-04-25  +imágenes TDP               <- ULTIMA actividad registrada
... silencio ...
2026-05-31  (hoy)                        <- +1 mes sin commits, PRs ni reviews
```

Toda la actividad real se concentra en una ventana de **~2 semanas en marzo**, con una sola reaparición el 25 de abril. **Desde el 2026-04-25 no hay rastro de Lucio en el repo:** ni commit, ni PR, ni review, ni comentario en issues. Estamos a **más de un mes de silencio**, justo en la recta final hacia el mundial. Para contrastar: Benjamín tiene commits de visión hasta el 20-24 de mayo. El equipo está activo; Lucio, no.

---

## 2. Calidad del trabajo

### 2.1 El hallazgo que define todo: cero líneas vivas de visión

Esto es lo más importante del informe y conviene que lo tengas presente al hablar con él. Hice `git blame` línea por línea sobre la versión **actual** de cada archivo de visión y conté autores:

| Archivo (versión viva) | Benjamín | Gustavo | **Lucio** |
|---|---:|---:|---:|
| `final_rpi/Main.py` | 537 | 312 | **0** |
| `final_rpi/camthreader.py` | 0 | 43 | **0** |
| `final_rpi/calibration.py` | 0 | 50 | **0** |
| `test/rescue_zone_test/rescatemodelonos.py` | 0 | 450 | **0** |
| `test/rescue_zone_test/tfmodelprueba.py` | 0 | 524 | **0** |
| `test/rescue_zone_test/warmup.py` | 485 | 0 | **0** |

**Lucio tiene 0 líneas sobrevivientes en TODO el código de visión**, que es su dominio asignado. El directorio de modelos de IA (`software/raspberry/AI/` — entrenamiento YOLO, export NCNN/TFLite, *literalmente* el corazón de su rol) es **100% de Benjamín y Gustavo**. Su único toque a visión fue el pase de comentarios de `795cc8e`, que agregó anotaciones sin tocar la lógica; cuando Benjamín reescribió `Main.py` completo (heartbeating, autobalanceador de blancos, latencia de inferencia), esos comentarios **murieron en el rebase de la realidad**.

> **Importante para vos como coach:** esto NO prueba que Lucio "no trabajó". El git muestra resultado, no intención. Puede haber trabajado offline sin commitear, puede haber un reparto informal donde Benjamín absorbió visión, o puede haberse desconectado. Lo que sí es un hecho objetivo y accionable es: **el dueño nominal de visión no tiene huella técnica en visión**, y eso es un riesgo de equipo que hay que mirar de frente (ver §4 y §5).

### 2.2 Foco: fuera de dominio

El patrón es nítido. Las **dos** contribuciones de Lucio que tocaron algo real fueron:
- un fix de **firmware C++** (dominio de Laureano), y
- un **TDP** (documentación).

Ninguna fue a visión. Esto es clave para el diagnóstico: **el problema no es de capacidad, es de aplicación al rol** (lo desarrollo en Fortalezas).

### 2.3 Tests documentados

**Cero.** Lucio no tiene ninguna entrada en `testing/TEST_LOG.md` ni evidencia de validación en banco de nada de lo que hizo. Esto es coherente con que su trabajo fue mayormente documentación y un fix puntual, pero también significa que **no incorporó todavía el hábito de "fix → banco → registro en TEST_LOG"** que es regla de oro del equipo (regla #3 del CLAUDE.md).

### 2.4 Convenciones

Mixto:
- **Bien:** usa Conventional Commits en español (`fix(teensy):`, `docs(tdp):`, `feat(docs):`) — respeta la regla #7. Los mensajes son claros.
- **Mal:** el TDP está **en inglés** (correcto: RoboCup pide el TDP en inglés) pero **nadie del equipo lo revisó** — por eso pasó un error de hecho grave (dice "Raspberry Pi 5" cuando el hardware es **RPi 4B**, en el Abstract y en la sección 7). Y el pase de comentarios de PR #42 tiene fuerte olor a autogenerado por IA (banners ASCII, comentario línea-a-línea sobre cada `import`, lógica intacta) — documentar está bien, pero eso **no demuestra comprensión propia del código**.

### 2.5 Reincidencia de bugs

**No aplica en sentido estricto** y esto es un dato a favor: como Lucio no tiene código vivo, **no hay bugs atribuibles a él** en las auditorías de RESILIENCIA (#53/#27/#57-#119) ni de CORRECTITUD (#120-#128). Su único fix (punteros) fue **correcto** y no introdujo regresiones. El contraste es elocuente: la enorme batería de findings de visión (V18-01 a V18-12 en `rpi-01-vision.md`; D1-D12 en `rpi-02-decision.md`) recae sobre código de **Benjamín y Gustavo**, no de Lucio — precisamente porque Lucio no escribió ese código.

Esto tiene una doble lectura honesta:
1. A favor: no rompió nada, su trabajo puntual fue limpio.
2. En contra: **no estuvo presente para prevenir, detectar ni arreglar** los bugs P0/P1 de su propio subsistema. El bug más caro de todo el módulo, **V18-01** (formato del tensor TFLite sin verificar → el rescate puede no funcionar EN ABSOLUTO si el TFLite no trae NMS), está sin confirmar y hay que medirlo en 48h — y el responsable nominal de visión no está en condiciones de liderar ese diagnóstico porque no conoce el pipeline por dentro.

---

## 3. FORTALEZAS concretas

No son de relleno; son reales y son la base sobre la que construir.

1. **Sabe programar y razona bugs de verdad.** El fix de punteros (`a8241e2`, PR #36) es técnicamente impecable. El código comparaba IDs de motor con `if (this->id == "FL" || this->id == "BL")` — eso compara **direcciones de puntero**, no contenido de string (undefined behavior, puede romper la cuenta de pulsos de encoder y la odometría). Lucio lo corrigió bien:
   ```cpp
   #include <string.h>
   if (this->id != NULL && (strcmp(this->id, "FL") == 0 || strcmp(this->id, "BL") == 0))
   ```
   Incluso agregó el guard `!= NULL`. Es exactamente la clase de bug que marca el auditor de firmware Teensy. **Esto demuestra que la capacidad técnica está**: no es un alumno que "no puede", es uno que no aplicó esa capacidad a su rol.

2. **Escribe documentación técnica de calidad.** El TDP (`TDP/TDP.md`, 411 líneas) está **bien estructurado**: cubre las 15 secciones del rubro RoboCup (Project Planning, Mechanical, Electronic, Sensors, Software Architecture, Vision and AI, Motion and Control, Rescue Strategy, Testing, Problems and Solutions, Innovation, Future Work, Conclusion, Acknowledgements). La prosa es competente y no suena a relleno: describe correctamente la arquitectura de dos computadoras, el YOLO entrenado con +2500 imágenes, la deposición selectiva. **El TDP es un entregable obligatorio y evaluado en el mundial, y hoy es el aporte de mayor valor de Lucio al equipo.** Con la rúbrica de documentación valiendo 102 puntos y el repo hoy en ~6-12% (ver `doc-01-tdp.md`), el draft de Lucio es potencialmente el mayor salto de puntaje disponible.

3. **Respeta las convenciones de proceso** (Conventional Commits en español, intención de documentar el código para el resto). El "estándar de comentarios" que propuso en PR #42 vos mismo lo valoraste ("el estándar de comentarios que propones está bueno").

4. **Trabaja sin romper.** Cuando tocó código, no introdujo regresiones. Es un perfil cuidadoso, no temerario — eso es valioso en un equipo donde la regla de oro #4 es "no rompas lo que funciona".

**Síntesis de fortalezas:** Lucio tiene el **perfil técnico-documental** del equipo. Razona código, escribe bien, es prolijo. La materia prima es buena.

---

## 4. DEBILIDADES / áreas de mejora concretas

Honesto y directo, porque es para mejorar.

1. **Desalineación rol ↔ realidad (la más grave).** Es el "dueño de visión" con **cero líneas vivas de visión**. Consecuencia operativa concreta: el **bus-factor de visión es 1** (solo Benjamín entiende `Main.py`). Si Benjamín se enferma, se satura o falla en Incheon, **no hay una segunda persona capaz de debuggear el subsistema más crítico para el puntaje** (línea, víctimas, zonas). A 6 semanas del mundial, esto es inaceptable como riesgo de equipo.

2. **Falta de continuidad / desconexión sostenida.** Más de un mes sin actividad (>4 semanas desde el 25-abr) entrando a la recta final. En pista, cada integrante necesita poder operar o debuggear *algo*; un miembro desacoplado del estado real del robot es peso muerto operativo en competencia — y, peor, un problema de moral para los otros dos que sí están full.

3. **Entregables sin cerrar (patrón de "no termina lo que empieza").** Sus dos aportes de mayor valor están **ambos varados**:
   - **PR #42** abierto desde marzo, abandonado tras tu feedback del 29-abr (le pediste rebasear por conflictos y nunca respondió).
   - **El TDP NO está en `main`** — vive solo en `origin/documentation_and_diagrams`, sin mergear, sin review, con el error "RPi 5".
   - **Y hay un agravante de gobernanza (issue #46):** el 2026-03-23 Lucio comentó *"estuve viendo lo del tdp y creé una base... lo desarrollé en la mayoría"*, refiriéndose a un draft en **Google Drive**. Vos le pediste el link el 01-abr **y de nuevo el 29-abr, sin respuesta**. O sea: el entregable más importante de documentación puede estar más avanzado de lo que muestra el repo, **pero vive fuera de control de versiones, invisible para el coach y para los jueces**. Esto no es solo "falta de cierre": es un riesgo de que se pierda trabajo real por no compartirlo.

4. **No participa del proceso de equipo.** 0 issues abiertos, 0 reviews de PRs de compañeros. No hay evidencia de que esté colaborando en el flujo de revisión cruzada que el equipo necesita. Trabaja (cuando trabaja) en aislamiento.

5. **No tiene el hábito de validación en banco.** 0 entradas en `TEST_LOG.md`. Todavía no internalizó el ciclo "fix → banco → registro" que es no-negociable en este repo.

---

## 5. Recomendaciones de coaching para Enzo

El diagnóstico clave es este: **el problema de Lucio NO es de talento, es de aplicación, continuidad y cierre.** El fix de punteros y el TDP prueban competencia. Entonces tu trabajo como coach **no es "que escriba más código"**, sino **(a) rescatar lo que ya hizo bien, (b) reconectarlo con tareas concretas y (c) darle una segunda función operativa real para Incheon.** Acá van las palancas, ordenadas por ROI.

### 5.1 ACCIÓN DE MAYOR ROI: rescatar el TDP (es puntaje casi gratis y se está por perder)

El TDP es de los pocos entregables 100% bajo control del equipo, vale 102 puntos de rúbrica, y el repo hoy está en ~6-12%. El draft de Lucio puede ser el mayor salto disponible.

- **Pedile concretamente:** el **link del Drive de #46** (ya se lo pediste dos veces — hacelo una conversación, no un comentario de GitHub) + que **cherry-pickee `TDP/` + imágenes + `consumo.md` a una rama limpia y lo mergee a `main`**.
- **Importante:** NO mergear `documentation_and_diagrams` entera (arrastra el PR #42 conflictivo). Separar el TDP del pase de comentarios.
- **Corregir el error de hecho:** "Raspberry Pi 5" → "Raspberry Pi 4B", y que Benjamín/Laureano revisen los datos técnicos (sensores, consumo).
- **Tiempo:** 1-2 h cherry-pick + merge; +1 h review técnico. **Alta prioridad — es la victoria más rápida sobre el trabajo de Lucio.**
- **Por qué funciona como coaching:** le devuelve **ownership de algo que SÍ hizo bien**, le cierra un entregable (rompe el patrón de "no termina"), y le da una victoria visible que lo reconecta.

### 5.2 Garantizar bus-factor 2 en visión (pairing dirigido, NO reasignación)

NO le pidas que reescriba visión a 6 semanas del mundial — sería onboarding tardío en el peor momento. El objetivo es **que sea la segunda persona capaz de debuggear visión en pista**, no que la reescriba.

- **Pedile:** 4-6 h de **pairing dirigido Benjamín → Lucio** sobre `Main.py`, corriendo el banco, repetido 2-3 veces antes de viajar.
- **Anclalo a un finding real y acotado:** por ejemplo, hacelo **dueño de la calibración de color en sede** (HSV de plata + verde LAB), que es justo lo que se rompe con la luz de Incheon. Esto conecta directo con los findings **V18-02** (silver_mask en BGR, el único trigger de entrada a rescate), **V18-04** (rojo sin wrap de Hue), **V18-05** (verde LAB frágil) y **V18-10** (protocolo de recalibración in-situ por JSON). Es una tarea **chica, medible, con commit y entrada en TEST_LOG al final** — perfecta para reintroducirlo al ciclo de trabajo.
- **Tiempo:** 4-6 h pairing + la tarea de calibración (~3-4 h). **Riesgo de fixear:** fricción social baja si se enmarca como "te necesitamos como segundo de visión para Corea", no como "no hiciste tu parte".

### 5.3 Cerrar PR #42 (limpieza, decisión de 10 minutos)

Rebasear un PR de 32 archivos de comentarios contra el `main` actual es trabajo no-trivial y de bajo valor a esta altura. **Recomendación: cerrarlo** ("estándar de comentarios adoptado a futuro, no se mergea así") y no reabrir antes del mundial. Opcional: portar el estándar de comentarios solo a los archivos de visión vivos (2-3 h) **si** queda aire. Que la decisión la tomen entre vos y Lucio, para que él la sienta como cierre y no como descarte.

### 5.4 La conversación 1:1 (lo más importante y lo más delicado)

Esto **no es un issue de GitHub** — requiere que vos (coach) y ojo Gustavo (director) tengan una charla franca con él. No para reprochar, sino para entender **por qué se desconectó** (¿perdió motivación? ¿se sintió desplazado cuando Benjamín tomó visión? ¿problemas personales/escolares? ¿no supo cómo reengancharse?). El git no te dice esto; solo una conversación.

- **Encuadre sugerido:** "Lucio, tenés el mejor perfil técnico-documental del equipo —el fix de punteros y el TDP lo demuestran—. Te necesito de vuelta en el equipo con tareas concretas para Corea. ¿Qué pasó y qué necesitás para reengancharte?"
- **Salí de la charla con 2-3 tareas acotadas, medibles y con fecha** (el TDP a `main`, dueño de calibración de color, segundo operador de visión en banco). Tareas chicas con commit al final, para reconstruir el hábito y la confianza.
- **Tiempo:** 30-45 min. **Es deuda de equipo, no de código** — y es la palanca que más mueve la aguja con Lucio.

### 5.5 Qué pedirle, en una línea cada cosa

1. El link del Drive del TDP (#46) — **hoy**.
2. TDP cherry-pickeado a `main`, con "RPi 5" → "RPi 4B" corregido.
3. Ser el **segundo operador de visión** (pairing con Benjamín + banco).
4. Dueño de la **calibración de color en sede** (HSV plata + verde LAB), con commit + TEST_LOG.
5. Cerrar PR #42.

---

## 6. Veredicto honesto

**Desempeño: por debajo de lo esperado para el rol asignado** — pero **no por incapacidad**. El fix de punteros (correcto, fuera de dominio) y el TDP (de buena calidad, varado sin mergear) demuestran competencia técnica y de redacción reales. La brecha es de **aplicación fuera de dominio + falta de continuidad (>1 mes de silencio) + entregables sin cerrar**.

El riesgo más concreto para Incheon no es "Lucio no programó suficiente", sino que **(a)** su mejor trabajo (el TDP) se pierda por un problema de proceso (Drive, sin merge, sin review), y **(b)** el equipo viaje con bus-factor 1 en visión y un integrante desacoplado del estado real del robot.

La buena noticia para vos como coach: **las tres acciones de mayor impacto son recuperables en pocas horas** y todas refuerzan a Lucio en vez de castigarlo — rescatar su TDP, hacerlo segundo de visión, y reconectarlo con una conversación franca y tareas chicas con cierre. La materia prima es buena; lo que falta es engancharla al rol y al equipo antes de viajar.

---

*Informe de desempeño individual — auditoría integral 2026-05-18. Números verificados contra `git log/blame --all` y `gh` sobre el checkout `feature/initialize-testing-log` al 2026-05-31. Solo lectura; no se modificó código ni se ejecutaron acciones de escritura en GitHub. Insumos cruzados: `equipo-02-lucio.md`, `rpi-01-vision.md`, `rpi-02-decision.md`, `doc-01-tdp.md`. Marco "TEMAS A ANALIZAR" (riesgo-no-actuar / riesgo-actuar / tiempo), no "bugs a fixear".*
