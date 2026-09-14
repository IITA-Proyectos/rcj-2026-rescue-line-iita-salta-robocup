# Sección "En vivo": % del máximo del mapa (agregado, no es del CMS)

**Archivos:** `local/porcentaje-maximo.js` (nuevo) y un `<script>` en `juez.html`, `firma.html` y `vista.html`.
**Flag:** `mostrarPorcentaje` (default `true`, en Configuración).

**Qué muestra:** una tarjeta Bootstrap insertada arriba de la tarjeta de LoPs del panel izquierdo:
- porcentaje del puntaje final sobre el máximo posible del mapa, con barra de progreso;
- puntaje final contra máximo, puntaje de recorrido (`raw_score`) contra máximo y multiplicador contra máximo.

**De dónde sale el máximo:** `GET /api/maps/line/:id/maxScore`, lo mismo que la calculadora del editor
(`initLine` con todo logrado, sin LoPs, víctimas en orden y exit bonus, calculado con `scoreCalculatorRules/2026.js`).

**Cómo se actualiza:** cada 2 s lee la corrida directo de IndexedDB (`RCJLocal.store.get('lineRuns', runId)`).
No usa `GET /api/runs/line/:id` porque ese endpoint re-inicializa las corridas no empezadas (08 C1).

**Por qué:** el "puntaje normalizado" del CMS compara contra la mejor corrida de todos los equipos del mismo
grupo de normalización; en un entrenamiento de un solo equipo siempre da 1 o queda vacío. El % del máximo
del mapa sí sirve para comparar corridas entre mapas distintos.

**Qué no cambia:** el puntaje, el flujo del juez y la firma. Si no encuentra la tarjeta de LoPs (por ejemplo
durante el pre-chequeo) muestra una píldora flotante con el porcentaje.
