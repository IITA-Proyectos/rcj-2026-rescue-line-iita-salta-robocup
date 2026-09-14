# Cambios del área assets respecto del CMS

Área **assets** de `tools/rcj-line-offline`. Fuente: `robocup-junior/rcj-rescue-cms`, commit `d805502` (rama develop-2026).
Todo lo del CMS se tomó con `git show d805502:<ruta>`: los bytes del blob, sin el CRLF que agrega `autocrlf` al
working tree.

Hay tres herramientas reproducibles (python 3.11, sin dependencias externas):

| Script | Qué hace |
|---|---|
| `herramientas/importar_cms.py` | Copia del CMS, reglas 3a/3c, `lang/es.json`, `data/tilesets.json`, licencia. Regenera el bloque automático del final de este archivo. |
| `herramientas/vendorizar.py` | Arma `components/` y `components/VERSIONES.md`. |
| `tests/assets-verificar.py` | Verificación estática de referencias y del contenido de `components/`. |

## 1. Qué se copió

183 archivos, 3 696,3 KB. El importador verifica, para cada uno, que el sha1 de git del contenido coincida
con el del blob.

| Grupo | Archivos | Detalle |
|---|---|---|
| JS | 14 | `javascripts/`: los de editor, juez, firma/vista, manual, ranking, gamesPrint, `line_competition`, `admin/games`, `admin/maps`, más `pathFinder.js`, `lvl-uuid.js`, `translate_config.js`, `deflate.js` y `makeQR.js` (los dos últimos los carga el juez sin usarlos) |
| CSS | 10 | `stylesheets/`: `style`, `navbar_premium`, `fredrik`, `admin/mapEditor/line_modern` y `maze_modern`, `common/modern_*` (4), `admin/live_ranking` |
| Templates | 4 | `tile.html`, `line_editor_modal.html`, `line_judge_modal.html`, `line_view_modal.html` |
| Imágenes explícitas | 28 | logo, víctimas, `rescueKit`, `evacZone/*_lv2*` (4), bonus (2), `next-robot` (2), `loader2.gif`, víctimas de Entry (3), `noLogo`, `NoImage`, favicons e íconos Apple (10) |
| `images/tiles/*` | 98 | Todas las del repo. El tileset usa 87; además `ev-entrance` y `ev-exit` las usan `tile.html`, los modales y `lineSSR`. |
| `images/mapimage/*` | 11 | Overlays del PNG del mapa (`helper/lineSSR/2026.js`) |
| `sounds/*` | 5 | |
| `scoresheet_generation/line/*` | 10 | Planilla PDF |
| `lang/` | 2 | `en.json`, `ja.json` |
| Licencia | 1 | `LICENSE-rcj-rescue-cms.txt`: MIT, 1 082 bytes, idéntico al blob |

Cobertura: el importador recorre los 21 pug de las páginas e includes más los JS, CSS y templates copiados, y
comprueba cada referencia a estáticos:
- 177 referencias estáticas cubiertas;
- 26 dinámicas: globs de `images/tiles`, `victimImgPath` y `lang/`;
- 5 omisiones documentadas;
- 0 faltantes.

**No se copió:**

| Qué | Motivo |
|---|---|
| Variantes E | Fuera de v1, D8 |
| `stylesheets/fonts.css` y `public/fonts/*` | ESPEC §1 |
| `manifest.json` | Es del área docs |
| `images/ranking/*` | Solo signage |
| `images/evacZone/*_lv1*` | Solo las usan las variantes E |
| `templates/tile4Image.html` | Solo EditorE |
| `stylesheets/stg.css` | Solo en entorno STG |

## 2. Cambios dentro de archivos copiados (reglas 3a, 3c y ESPEC §1)

Se modificaron 103 líneas; el detalle línea por línea está en la tabla automática del final. Los archivos que no
aparecen en esa tabla quedaron byte a byte iguales al blob. Ejemplos: `pathFinder.js`, `lvl-uuid.js`, `games.js`,
`maps.js`, `line_competition.js`, `ranking/line_2026.js`, `gamesPrint/line_2026.js`, `admin/mapEditor/line_2026.js`
(salvo sus 2 `templateUrl`) y todas las CSS menos `modern_layout.css`.

1. **Regla 3a: 101 líneas.** Rutas absolutas de estáticos pasan a relativas, sin la barra inicial:
   - `templateUrl` del editor, el juez y la firma;
   - `getAudioBuffer('/sounds/...')` del juez, la firma y la carga manual;
   - `/images/tiles/` de `manual/line_2026.js:277,304`;
   - `prefix: '/lang/'` de `translate_config.js:4`;
   - los `src` y `ng-src` de `tile.html`, `line_judge_modal.html` y `line_view_modal.html`.

   El reemplazo usa la expresión `(['"\`])/(components|images|templates|lang|stylesheets|javascripts|sounds|scoresheet_generation)/`
   y conserva la comilla. **`/api/` no se toca.** El importador cuenta las apariciones de `/api/` antes y después
   en cada JS, HTML y CSS, y aborta si difieren. Las rutas de navegación (`/line/...`, `/home`, `/admin/...`,
   regla 3b) quedan intactas: las cambia el agente dueño de cada página.
2. **Regla 3c: `javascripts/translate_config.js:8`.**
   - `registerAvailableLanguageKeys(['en', 'ja', 'es'], {'en_*':'en', 'ja_*':'ja', 'es_*':'es', '*':'es'})`.
   - Se conserva `.determinePreferredLanguage()` y a continuación se agrega `.preferredLanguage('es')` con un
     comentario.
   - Efecto, verificado en Edge: sin elección guardada el idioma es `es` aunque el navegador esté en `en-US`. Si hay
     elección guardada en `localStorage NG_TRANSLATE_LANG_KEY` (`en` o `ja`), esa elección gana. Lo hace el bloque
     `run` de angular-translate: storage primero y, si no hay, `preferredLanguage`.
   - Pendiente de las páginas con layout: agregar la tarjeta ES al selector (`language_modal.pug`). El HTML listo
     está en `herramientas/fragmentos-head.md` §1.F.
3. **ESPEC §1: `stylesheets/common/modern_layout.css:2`.**
   - Antes: `@import url('/stylesheets/fonts.css');`.
   - Después: un comentario `/* [rcj-line-offline] se omite el @import ... */`.
   - Motivo: las fuentes Outfit/Inter del CMS son HTML. Sin empaquetarlas, el `@import` daría 404 (primero de
     `fonts.css`, después de cada `.ttf`). El resultado visual es el mismo del sitio vivo: cae a `sans-serif`.
     Queda declarado en `desvios`.

## 3. `images/rescueKit.png` y `images/rescuekit.png`

- En el CMS son **dos entradas con el mismo blob** (`5ad7ed4…`, 5 271 bytes).
- El código de Línea 2026 solo referencia `rescueKit.png` (`ranking/line_2026.js:161`, `gamesPrint/line_2026.js:412`).
- NTFS no distingue mayúsculas, así que en este disco solo puede existir un nombre. El importador deja
  **`rescueKit.png`**, el que usa el código.
- En un sistema de archivos que distingue mayúsculas escribe los dos (detecta el caso creando un archivo de prueba).
- `tests/assets-verificar.py` compara nombres exactos, así que un `rescuekit.png` referenciado daría error.

## 4. `lang/es.json`

- Es `lang/en.json` del commit, fusionado en profundidad con `analysis/es-line-keys.json` (el español pisa).
  Se generó con `importar_cms.py --es-keys`.
- En `en.json` hay 1 146 hojas y en `es-line-keys.json` 190: 189 pisan una hoja existente y 1 es nueva
  (`admin.lineMapEditor.mapName` = "Nombre del mapa", que falta en en/ja, 06 §5.2).
- Total: 1 147 hojas, 63 774 bytes, sha256 `301c775a0be94126936e371e1a414acf31f860d1a706936398cac0fe6c526b5f`.
- `en.json` trae dos claves duplicadas: `m_identified` e `includeLetterVictims`, ajenas a Línea. Se respetó la
  semántica de `JSON.parse`: gana el último valor en la posición de la primera aparición.
- Formato: `json.dumps(indent=4, ensure_ascii=False)` y LF final.
- Las claves de páginas nuevas (D2) todavía no existen. Cuando las entreguen, se vuelve a correr el importador con
  otro `--es-keys` (ver pendientes).

## 5. `data/tilesets.json`

- Copia byte a byte de `live/api_maps_line_tilesets_populate_true`, comparada con `cmp`.
- JSON válido. Contiene `Default(2022)` (`5c19d2439590f2d68b15b302`, 87 baldosas) y `PTY1`
  (`6a2ea9e7388e8f7d01f36435`, 86), sin reordenar.
- 35 314 bytes, sha256 `19ebf50a31b30ef0cfa8eeca8ba25ba6a7d82249f368982f0b48bd9da4f2f961`.

## 6. `components/` (vendor)

52 archivos, 5 643,1 KB. El detalle por archivo (bytes, sha256, origen y verificación) está en
`components/VERSIONES.md`.

Todo archivo pasa por las validaciones de `vendorizar.py`: no es HTML, tamaño exacto de 06, cadena de versión y
bytes mágicos. Todos resultaron **idénticos por sha256** a la misma versión bajada de otro CDN
(cdnjs, jsDelivr o unpkg).

Correcciones a `analysis/06-dependencias.md`:

| Tema | 06 decía | Resultado |
|---|---|---|
| `alertifyjs/dist/js/ngAlertify.js` | 1.0.12 | Es **1.0.11**: el sha coincide con `alertify.js@1.0.11` y difiere del de 1.0.12, aunque miden igual. Además el archivo dice `version:"1.0.11"`. |
| `angular-ui-select` | 0.19.8 | Es 0.19.8 (sha idéntico a cdnjs 0.19.8), pero el banner interno dice "Version: 0.19.7". |
| Imágenes de lightbox2 | — | Las de cdnjs 2.12.0 están recomprimidas (237/1035/1031 bytes); se verificaron contra npm `lightbox2@2.12.0`. |

Agregados que no estaban en la tabla de 06 porque 06 no analizó `games.pug`:
- `angular-bootstrap-datetimepicker/src/css/datetimepicker.css` 1.1.4 (`games.pug:20`);
- `exceljs/index.js` = ExcelJS 4.2.1, idéntico a cdnjs (`games.pug:17`).

También se agregaron:
- `bootstrap-fileinput/img/*` y `lightbox2/dist/images/*`, que piden sus CSS;
- `socket.io-client` 4.2.0, vendorizado aunque las páginas usan `local/io-shim.js`.

Librerías nuevas:

| Librería | Versión | Nota |
|---|---|---|
| `pdfkit/js/pdfkit.standalone.js` | **0.12.3** | Existe esa versión exacta en npm, la misma de `cms/package.json:48`. No hizo falta usar otra. |
| `qrcode-generator/qrcode.js` | 1.4.4 | |
| `mobile-drag-drop/{index.min.js, scroll-behaviour.min.js, default.css}` | 2.3.0-rc.2 | |

Omitidos a propósito:

| Qué | Motivo |
|---|---|
| `bootstrap-fileinput/themes/fa/theme.min.js` | La copia de vendor-live es el HTML soft-404; no existe en 5.5.4. |
| Fuentes Outfit/Inter | Son HTML. |
| Font Awesome `woff`/`ttf`/`eot`/`svg` | Alcanza con woff2. `assets-verificar.py` los lista como omisiones documentadas. |
| Plugins comentados de fileinput y source maps | |

## 7. Notas para las demás áreas

- **`<meta charset="utf-8">` es obligatorio primero en cada página.** `python -m http.server` sirve `.html` como
  `text/html` sin charset; Express mandaba `charset=utf-8`. Está incluido en todos los fragmentos.
- **Tipos MIME en `python -m http.server` (Windows):**
  - `.js` sale como `application/javascript`;
  - `.json` sale como `application/json`;
  - `.woff2` sale como `application/octet-stream`. Font Awesome carga igual (probado);
  - `.md` sale como `application/octet-stream`.
- **Backend:** el decorador de `$httpBackend` tiene que dejar pasar `lang/*.json` y `templates/*.html` (con `?gs`).
- El orden exacto de `<script>`/`<link>` por página y la ubicación de los `local/*` están en
  `herramientas/fragmentos-head.md`.

## 8. Pruebas ejecutadas

| Prueba | Resultado |
|---|---|
| `importar_cms.py` ×3 | 1ª corrida: 183 creados + `es.json` + `tilesets.json`. 2ª y 3ª: todo "sin cambios" (idempotente). |
| `vendorizar.py` ×2 | 52 creados; después 52 "sin cambios", sin errores, 52/52 idénticos por sha a otro CDN. |
| `tests/assets-verificar.py` | OK: 47 archivos, 228 referencias, 0 errores y 0 avisos. |
| `tests/assets-vendor.html` en Edge headless (puerto 8801) | Todas las libs cargan y exponen su global o módulo. Versiones correctas: jQuery 3.7.1, Angular 1.8.2, Bootstrap 4.4.1, SweetAlert2 7.33.1, DataTables 1.10.21. `angular.bootstrap` pasa con los 9 módulos, incluidos DI. Traducción `es` ("Volver"). Font Awesome carga las 3 caras woff2. jSignature genera svgbase64. PDFKit arma un PDF de 41 484 bytes con texto e imagen PNG pasada como ArrayBuffer. qrcode-generator genera un data URL. Cargan 107/107 imágenes (tileset completo, víctimas, evacZone y mapimage), 4 templates, 3 lang y 4 sonidos. 0 errores de consola. |
| `tests/assets-idioma.html` en Edge headless con `--lang=en-US`, 3 perfiles | Sin elección: `use=es`, "Volver". Guardado `en`: `use=en`, "Back". Guardado `ja`: `use=ja`, "戻る". |
| `curl` a 34 rutas en 8801 | 32 responden 200 con su tipo. Las 2 restantes, `themes/fa/theme.min.js` y `stylesheets/fonts.css`, dan 404, como corresponde porque no se empaquetan. `images/rescuekit.png` (minúsculas) también dio 200, pero solo porque NTFS no distingue mayúsculas; en un host que las distingue, solo existe `rescueKit.png`. |

## 9. Cómo re-ejecutar

```bash
SP=<scratchpad>; cd tools/rcj-line-offline
python herramientas/importar_cms.py --cms "$SP/cms" --commit d805502 \
  --es-keys "$SP/analysis/es-line-keys.json" --tilesets "$SP/live/api_maps_line_tilesets_populate_true"
python herramientas/vendorizar.py --vendor-live "$SP/vendor-live"
python tests/assets-verificar.py
```

- `importar_cms.py` no pisa archivos editados después por otras áreas: los marca "PROTEGIDO". Con `--forzar` los sobrescribe.
- `vendorizar.py` sin `--vendor-live` baja lo que falte del sitio vivo o del CDN.

<!-- AUTO:importar_cms INICIO (no editar a mano: lo regenera herramientas/importar_cms.py) -->

### Reemplazos aplicados por `herramientas/importar_cms.py` (commit `d805502`)

Generado automáticamente. Cada fila es una línea de un archivo copiado del CMS; "antes" es el blob de git y "después" lo que queda en la app.

| Archivo:línea | Regla | Antes | Después | Motivo |
|---|---|---|---|---|
| `javascripts/admin/mapEditor/line_2026.js:1121` | 3a | <code>templateUrl: &#x27;/templates/line_editor_modal.html?gs&#x27;,</code> | <code>templateUrl: &#x27;templates/line_editor_modal.html?gs&#x27;,</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/admin/mapEditor/line_2026.js:1230` | 3a | <code>templateUrl: &#x27;/templates/tile.html&#x27;,</code> | <code>templateUrl: &#x27;templates/tile.html&#x27;,</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/judge/line_2026.js:673` | 3a | <code>templateUrl: &#x27;/templates/line_judge_modal.html&#x27;,</code> | <code>templateUrl: &#x27;templates/line_judge_modal.html&#x27;,</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/judge/line_2026.js:1072` | 3a | <code>templateUrl: &#x27;/templates/tile.html&#x27;,</code> | <code>templateUrl: &#x27;templates/tile.html&#x27;,</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/judge/line_2026.js:1268` | 3a | <code>getAudioBuffer(&#x27;/sounds/click.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/click.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/judge/line_2026.js:1271` | 3a | <code>getAudioBuffer(&#x27;/sounds/info.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/info.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/judge/line_2026.js:1274` | 3a | <code>getAudioBuffer(&#x27;/sounds/error.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/error.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/judge/line_2026.js:1277` | 3a | <code>getAudioBuffer(&#x27;/sounds/timeup.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/timeup.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/sign/line_2026.js:478` | 3a | <code>templateUrl: &#x27;/templates/line_view_modal.html&#x27;,</code> | <code>templateUrl: &#x27;templates/line_view_modal.html&#x27;,</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/sign/line_2026.js:756` | 3a | <code>templateUrl: &#x27;/templates/tile.html&#x27;,</code> | <code>templateUrl: &#x27;templates/tile.html&#x27;,</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/sign/line_2026.js:1142` | 3a | <code>getAudioBuffer(&#x27;/sounds/click.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/click.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/sign/line_2026.js:1145` | 3a | <code>getAudioBuffer(&#x27;/sounds/error.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/error.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/sign/line_2026.js:1148` | 3a | <code>getAudioBuffer(&#x27;/sounds/info.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/info.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/manual/line_2026.js:277` | 3a | <code>if(tile.start) return &quot;/images/tiles/tile-0.png&quot;;</code> | <code>if(tile.start) return &quot;images/tiles/tile-0.png&quot;;</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/manual/line_2026.js:304` | 3a | <code>if(imgName) return &quot;/images/tiles/&quot; + imgName;</code> | <code>if(imgName) return &quot;images/tiles/&quot; + imgName;</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/manual/line_2026.js:730` | 3a | <code>getAudioBuffer(&#x27;/sounds/click.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/click.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/manual/line_2026.js:733` | 3a | <code>getAudioBuffer(&#x27;/sounds/info.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/info.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/manual/line_2026.js:736` | 3a | <code>getAudioBuffer(&#x27;/sounds/error.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/error.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/manual/line_2026.js:739` | 3a | <code>getAudioBuffer(&#x27;/sounds/timeup.mp3&#x27;, function (buffer) {</code> | <code>getAudioBuffer(&#x27;sounds/timeup.mp3&#x27;, function (buffer) {</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/translate_config.js:4` | 3a | <code>prefix: &#x27;/lang/&#x27;,</code> | <code>prefix: &#x27;lang/&#x27;,</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `javascripts/translate_config.js:8` | 3c | <code>.registerAvailableLanguageKeys([&#x27;en&#x27;, &#x27;ja&#x27;], { &#x27;en_*&#x27;: &#x27;en&#x27;, &#x27;ja_*&#x27;: &#x27;ja&#x27;, &#x27;*&#x27;: &#x27;en&#x27; }) .determinePreferredLanguage()</code> | <code>.registerAvailableLanguageKeys([&#x27;en&#x27;, &#x27;ja&#x27;, &#x27;es&#x27;], { &#x27;en_*&#x27;: &#x27;en&#x27;, &#x27;ja_*&#x27;: &#x27;ja&#x27;, &#x27;es_*&#x27;: &#x27;es&#x27;, &#x27;*&#x27;: &#x27;es&#x27; }) .determinePreferredLanguage() // [rcj-line-offline] regla 3c: español como idioma preferido cuando no hay elección guardada. // Si el usuario ya eligió un idioma (localStorage NG_TRANSLATE_LANG_KEY) esa elección gana. .preferredLanguage(&#x27;es&#x27;)</code> | registrar 'es' (alias es_* y comodín), mantener en/ja y dejar 'es' como preferido sin elección guardada |
| `stylesheets/common/modern_layout.css:2` | ESPEC §1 | <code>@import url(&#x27;/stylesheets/fonts.css&#x27;);</code> | <code>/* [rcj-line-offline] se omite el @import de stylesheets/fonts.css: las fuentes Outfit/Inter del CMS son HTML (ESPEC §1); el sitio vivo ya dibuja con sans-serif */</code> | no enlazar stylesheets/fonts.css (fuentes Outfit/Inter rotas en el origen; evita 404) |
| `templates/tile.html:5` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{tile.tileType.image}}&quot;  class=&quot;rot{{t…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{tile.tileType.image}}&quot;  class=&quot;rot{{t…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/tile.html:6` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/tile.html:7` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(t…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(t…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:9` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[0].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[0].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:10` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:11` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:19` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[1].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[1].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:20` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:21` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:29` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:33` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:37` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:43` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[2].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[2].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:44` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:45` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:55` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[3].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[3].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:56` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:57` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:65` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:69` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:73` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:79` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[4].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[4].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:80` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:81` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:89` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[5].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[5].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:90` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:91` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:99` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:103` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:107` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:115` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[6].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[6].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:116` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:117` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:125` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[7].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[7].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:126` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:127` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:135` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:139` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:143` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:149` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[8].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[8].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:150` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_judge_modal.html:151` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:9` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[0].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[0].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:10` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:11` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:19` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[1].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[1].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:20` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:21` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:29` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:33` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:37` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:43` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[2].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[2].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:44` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:45` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:55` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[3].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[3].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:56` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:57` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:65` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:69` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:73` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:79` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[4].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[4].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:80` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:81` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:89` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[5].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[5].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:90` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:91` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:99` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:103` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:107` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:115` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[6].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[6].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:116` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:117` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:125` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[7].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[7].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:126` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:127` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:135` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:139` | 3a | <code>&lt;img src=&quot;/images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | <code>&lt;img src=&quot;images/next-robot-done.png&quot; style=&quot;position:absolute…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:143` | 3a | <code>&lt;img src=&quot;/images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | <code>&lt;img src=&quot;images/next-robot-undone.png&quot; style=&quot;position:absolu…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:149` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/{{nineTile[8].tileType.image}}&quot; style=&quot;…</code> | <code>&lt;img ng-src=&quot;images/tiles/{{nineTile[8].tileType.image}}&quot; style=&quot;…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:150` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-entrance.png&quot;  class=&quot;rot{{evacTapeR…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |
| `templates/line_view_modal.html:151` | 3a | <code>&lt;img ng-src=&quot;/images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | <code>&lt;img ng-src=&quot;images/tiles/ev-exit.png&quot;  class=&quot;rot{{evacTapeRot(n…</code> | ruta absoluta de estático -> relativa (1 ocurrencia/s) |

Total de líneas modificadas: **103**.

### lang/es.json

- Base: `lang/en.json` del commit `d805502` (1146 hojas).
- Fusionado con: `es-line-keys.json` (190 hojas; el español pisa).
- Hojas pisadas: 189. Claves agregadas que no existían en en.json: `admin.lineMapEditor.mapName`.
- Hojas totales en es.json: 1147. Tamaño: 63774 bytes. sha256 `301c775a0be94126936e371e1a414acf31f860d1a706936398cac0fe6c526b5f`.
- Conflictos de tipo (objeto vs hoja): ninguno.
- Aviso: en.json: clave duplicada "m_identified" (gana el último valor, igual que JSON.parse)
- Aviso: en.json: clave duplicada "includeLetterVictims" (gana el último valor, igual que JSON.parse)

### data/tilesets.json

- Copia byte a byte de `live/api_maps_line_tilesets_populate_true` (sin reordenar).
- JSON válido: sí. Tilesets: Default(2022) (`5c19d2439590f2d68b15b302`, 87 baldosas), PTY1 (`6a2ea9e7388e8f7d01f36435`, 86 baldosas).
- Tamaño: 35314 bytes. sha256 `19ebf50a31b30ef0cfa8eeca8ba25ba6a7d82249f368982f0b48bd9da4f2f961`.

<!-- AUTO:importar_cms FIN -->
