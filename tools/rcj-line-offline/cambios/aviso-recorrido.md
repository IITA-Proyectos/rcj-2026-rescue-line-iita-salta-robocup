# Recorrido tolerante y avisos del recorrido (desvíos declarados)

## 1. Aviso de recorrido cortado

**Archivos:** `local/aviso-recorrido.js` (nuevo) y un `<script>` en `juez.html`.

Cuando el juez carga la corrida busca baldosas con elementos que puntúan (gap, intersección, obstáculo,
lomo, rampa, seesaw) cuyo `index` quedó vacío y muestra un aviso amarillo cerrable con sus coordenadas
del editor.

**Por qué:** en el CMS oficial esas baldosas se ignoran en silencio (`judge/line_2026.js:620`,
`if (!mtile || mtile.index.length == 0) return;`) y el editor 2026 no muestra la numeración (la línea
de `tileNumber` está comentada en `templates/tile.html:3`).

## 2. Recorrido tolerante (flag `recorridoTolerante`, activo por defecto)

**Archivos:** `local/nucleo/pathfinder-servidor.js` (función nueva `RCJLocal.PFtolerante`, agregada DESPUÉS
del bloque verbatim, que no se modifica), `local/nucleo/api.js` (guardado de mapa), `local/config.js`
(flag) y `local/aviso-recorrido.js` (aviso azul).

**Qué hace:** al guardar o importar un mapa se corre primero el pathFinder oficial. Solo si dejó baldosas
de línea sin numerar (sin contar la zona de evacuación), se recalcula con `PFtolerante`: es el mismo
`traverse()` salvo que, cuando la línea apunta a una celda VACÍA, antes de tratarlo como entrada a la
evacuación busca una baldosa vecina todavía no recorrida que tenga entrada desde ese lado
(`top, right, bottom, left`) y sigue por ahí.

**Garantías:**
- Un mapa que el pathFinder oficial recorre completo queda idéntico (no se llama a `PFtolerante`).
- Solo salta a baldosas sin recorrer, así que no crea lazos nuevos.
- El puntaje (`scoreCalculatorRules/2026.js`) no cambia; cambia qué baldosas forman parte del recorrido.

**Diferencia con la competencia real:** en el CMS oficial ese mapa quedaría cortado. Es una ayuda para
entrenar con mapas armados rápido. Se desactiva en Configuración.

**Ejemplo:** "Awesome Testbana" con la recta con gap de `(0,3)` vertical apuntando a `(0,4)` vacía: el
oficial numera 8 pasos; el tolerante une `(0,3) → (1,3)` y recorre el mapa completo.
