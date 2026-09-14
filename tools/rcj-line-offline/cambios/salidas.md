# Cambios respecto del CMS — área salidas

CMS de referencia: robocup-junior/rcj-rescue-cms, commit `d805502`. Todos los bytes del CMS se tomaron con
`git show d805502:<ruta>`.

Archivos del área:

| Archivo | Qué es |
|---|---|
| `local/render/registrar.js` | Registra las rutas de salida en `RCJLocal.api.registrarRuta`. Carga el resto bajo demanda |
| `local/render/comun.js` | Entorno "Node" mínimo para correr los generadores del CMS en el navegador |
| `local/render/mapa-png.js` | `helper/lineSSR/2026.js` y `helper/lineSSR/index.js` (verbatim) sobre `<canvas>` |
| `local/render/mapa-pdf.js` | `helper/lineMapPDF.js` (verbatim) sobre pdfkit 0.12.3 standalone |
| `local/render/planilla-pdf.js` | `helper/scoreSheetUtil.js`, `scoreSheetPDFUtil.js`, `scoreSheetPDFLineRules/2026.js` y `scoreSheetPDFLine2.js` (verbatim) |
| `local/render/rutas-cms.js` | Handlers de Express de `routes/api/lineMaps.js` y `routes/api/lineRuns.js` (verbatim) y emulación de las consultas de mongoose |
| `planillas.html` | Render a mano de `views/admin/gamesPrint/line_2026.pug` |
| `javascripts/admin/gamesPrint/line_2026.js` | Copia de assets; salidas solo aplica la regla 3b |
| `local/ui/movil-salidas.css` | Ajustes táctiles de `planillas.html` (excepción de propiedad permitida) |
| `tests/salidas-*` | Pruebas (ver §6) |

---

## 1. Código verbatim y los únicos 3 cambios de línea

El código del CMS está entre marcas `// ===== INICIO VERBATIM <ruta>:<desde>-<hasta> =====` y
`// ===== FIN VERBATIM ... =====`. `tests/salidas-verbatim.py <clon-del-cms>` compara cada región contra
`git show d805502:<ruta>` y sale con 1 si hay diferencias. Con `--escribir` las vuelve a insertar. Cada
cambio verifica la línea original antes de reemplazarla.

Resultado al 2026-09-13: `regiones: 11, diferencias: 0, cambios documentados aplicados: 3`.

| Región | Destino |
|---|---|
| `helper/lineSSR/2026.js:1-320` | `local/render/mapa-png.js` |
| `helper/lineSSR/index.js:1-32` | `local/render/mapa-png.js` |
| `helper/lineMapPDF.js:1-86` | `local/render/mapa-pdf.js` |
| `helper/scoreSheetUtil.js:1-19` | `local/render/planilla-pdf.js` |
| `helper/scoreSheetPDFUtil.js:1-53` | `local/render/planilla-pdf.js` |
| `helper/scoreSheetPDFLineRules/2026.js:1-461` | `local/render/planilla-pdf.js` |
| `helper/scoreSheetPDFLine2.js:1-100` | `local/render/planilla-pdf.js` |
| `routes/api/lineMaps.js:24-29` | `local/render/rutas-cms.js` (registro en los routers) |
| `routes/api/lineMaps.js:650-804` | `local/render/rutas-cms.js` (map-image-pdf/png, export, image/:mapid) |
| `routes/api/lineMaps.js:818-822` | `local/render/rutas-cms.js` (handleScoresheet) |
| `routes/api/lineRuns.js:663-745` | `local/render/rutas-cms.js` (GET /scoresheet2) |

Cambios de línea. Cada uno lleva el comentario `[rcj-line-offline]` en la misma línea:

| Archivo:línea | Antes | Después | Motivo |
|---|---|---|---|
| `helper/lineSSR/2026.js:22` | `if (fs.existsSync(imgPath)) {` | `if (await fs.existe(imgPath)) {` | En el navegador la imagen se consulta con `fetch`, que es asíncrono. La función ya era `async` |
| `helper/lineSSR/2026.js:308` | `const buffer = canvas.toBuffer('image/png');` | `const buffer = await canvas.toBuffer('image/png');` | `canvas.toBlob` del navegador es asíncrono |
| `helper/lineSSR/2026.js:313` | `return (await drawLineCanvas(map)).toBuffer('image/png');` | `return await (await drawLineCanvas(map)).toBuffer('image/png');` | Mismo motivo |

Cada módulo va envuelto en `(function (module, exports, require, __dirname, __filename) { ... })` con un
`require` por tabla. Es la misma semántica de CommonJS, y la lógica no se toca.

## 2. Entorno emulado (`local/render/comun.js`, `local/render/rutas-cms.js`)

Código nuevo, escrito a mano, con lo que en el servidor daba Node, Express o mongoose:

- **`@napi-rs/canvas`** → `<canvas>` del navegador (misma API 2D). `loadImage` usa `createImageBitmap`, y `toBuffer` devuelve `Promise<ArrayBuffer>`.
- **`fs`**
  - Los estáticos `public/...` y `scoresheet_generation/...` se bajan con `fetch` desde la raíz de la app y quedan en caché. Un 404 o un HTML "blando" cuenta como archivo inexistente.
  - `tmp/course/*`, donde escribe el generador, vive en memoria.
  - `existsSync`, `statSync`, `readFileSync` y `writeFileSync` son sincrónicos sobre esa caché, y lanzan `ENOENT` como Node. La planilla precarga sus 11 imágenes antes de correr.
  - `readdirSync('helper/scoreSheetPDFLineRules')` devuelve `['2026.js']`, porque solo está portada la regla 2026 (D8).
- **`path`**: `join` y `normalize` estilo POSIX.
- **`pdfkit`** → `components/pdfkit/js/pdfkit.standalone.js` 0.12.3, la misma versión que el CMS. Se usa una subclase cuyo único cambio es `openImage('ruta')`, que lee los bytes del `fs` emulado (el standalone no tiene disco). La clave del registro de imágenes es la misma que en Node. Fuentes: Helvetica estándar de pdfkit, porque la carpeta `fonts/` del CMS está vacía (así lo resuelven `glob` y `guesslanguage` en el servidor).
- **`qr-image`** → `components/qrcode-generator` 1.4.4 + un codificador PNG gris de 8 bits. Respeta `ec_level`, `size` y `margin` tal como los pasa el CMS. El contenido del QR es el mismo (`L;<runId>`), pero el patrón de módulos puede diferir si la librería elige otra máscara (ver desvíos).
- **`archiver('zip')`** → ZIP sin compresión (método STORE).
- **`glob`** → `sync()` devuelve `[]`, y **`guesslanguage`** → `'unknown'`. Da el mismo resultado que el CMS con `fonts/` vacía.
- **`process.env`** que lee `scoreSheetPDFLineRules/2026.js:161`: `cms_copyright` y `cms_version` salen de `package.json` d805502 (`26.0.2`), como hace `server.js`.
- **`res` de Express**: `status`, `setHeader`, `attachment`, `send`, `json`, `write`, `end`, eventos y `pipe` de pdfkit. `next()` sin error responde 404 `{message:'404 Not found'}` (`app.js:280-282`).
- **mongoose**: `lineMap` y `lineRun` con `find`, `findById`, `sort`, `select`, `populate` (incluido `tiles.tileType` desde los tilesets locales), `lean` y `exec` sobre `RCJLocal.store`. El orden de tipos es el de MongoDB.
- **`ObjectId`, `ObjectId.isValid`, `auth.authCompetition` y `ACCESSLEVELS`**: el usuario local es admin, con el mismo criterio que `local/nucleo/api.js`.

## 3. `local/render/registrar.js`: rutas registradas

| Método y ruta | Handler del CMS | Carga |
|---|---|---|
| `POST /api/maps/line/map-image-png` | `lineMaps.js` handlePublicMapImagePNG | comun + mapa-png (sin pdfkit) |
| `POST /api/maps/line/map-image-pdf` | handlePublicMapImagePDF → lineMapPDF | + pdfkit, qrcode-generator |
| `POST /api/maps/line/scoresheet` | handleScoresheet → scoreSheetPDFLine2 | + pdfkit, qrcode-generator |
| `GET /api/maps/line/image/:mapid` | getMapImage | sin pdfkit |
| `GET /api/maps/line/export` | handleExport (maps PDF/PNG-zip, scoresheets) | + pdfkit |
| `GET /api/runs/line/scoresheet2` | `lineRuns.js:663-745` | + pdfkit |

- Las expresiones regulares no distinguen mayúsculas y aceptan barra final, como Express.
- La respuesta es `{status, data: ArrayBuffer | string | objeto, headers}` con los headers del CMS (`Content-Type`, `Content-Disposition`).
- Las librerías pesadas (pdfkit, 2,6 MB) se cargan con `<script>` recién en el primer pedido que las necesita. El PNG nunca carga pdfkit.
- Hay ayudas opcionales para páginas que abren estas URL sin `$http`: `RCJLocal.salidas.abrir(url)`, `descargar(url, nombre)` e `interceptarWindowOpen()`.

Se incluye con `<script src="local/render/registrar.js"></script>` después de `local/nucleo/api.js`, y no hace
falta nada más. Lo incluyen `editor.html` (área editor) y `planillas.html`.

## 4. `planillas.html` (render de `views/admin/gamesPrint/line_2026.pug`)

Ruta del CMS: `/admin/:competitionid/:leagueId/games/print` (`routes/admin.js:467-480`). `RCJLocal.ruta` la mapea a
`planillas.html?competition=<cid>&league=<league>`.

| Línea de planillas.html | Cambio | Regla |
|---|---|---|
| 1 | Sin `<!doctype>`, como el pug: se conserva el modo quirks del original | fidelidad |
| 3 | `<meta charset="utf-8">` agregado, porque `http.server` no manda charset | fragmentos-head (assets) |
| 13-37 | `include ../../includes/common_component` expandido con rutas relativas (`/components/…` → `components/…`, `/stylesheets/…` → `stylesheets/…`) | 3a |
| 18, 20, 30, 36, 37 | Omitidos y comentados en su lugar: ngAlertify (06: C, sin uso), socket.io-client (lo reemplaza `local/io-shim.js`), angular-ui-select js/css (ningún módulo lo usa) y `stg.css` (solo con `ENVIRONMENT=="STG"`) | fragmentos-head |
| 39-50 | Scripts `local/*`: `config.js`, `io-shim.js`, `nucleo/*` y `render/registrar.js` | ESPEC §4 |
| 52-56 | Globales del pug (`gamesPrint/line_2026.pug:7-9`): `competitionId = RCJLocal.param('competition')`, `leagueId = RCJLocal.param('league') \|\| 'Line'` | ESPEC §4 |
| 57, 58, 62-64, 68 | `/javascripts/…`, `/stylesheets/…` y `/components/…` → relativas. Datetimepicker y ng-file-upload son el vendor real de `components/`, sin stub | 3a |
| 59-60 | `<link rel="stylesheet" href="local/ui/movil-salidas.css">` agregado (§5) | requisito móvil |
| 65-67 | `local/http-backend.js` + `RCJLocal.instalarBackend('RunAdmin')`, antes del arranque de Angular | ESPEC §4 |
| 214 | `img(src="/images/loader2.gif")` → `images/loader2.gif` | 3a |
| 251 | `ng-src='/images/{{victimImgPath(victim)}}'` → `images/{{…}}` | 3a |
| 254-256 | `/images/unknownVictim.png`, `/images/greenVictim.png`, `/images/blackVictim.png` → relativas | 3a |

El resto del markup es el del pug: mismas clases, atributos `ng-*`, textos en inglés y estilos inline.

### `javascripts/admin/gamesPrint/line_2026.js`

| Línea | Antes | Después | Regla |
|---|---|---|---|
| 372 | `window.location = path` | `window.location = RCJLocal.ruta(path) // [rcj-line-offline] regla 3b: …` | 3b |

Es la única diferencia con `git show d805502:public/javascripts/admin/gamesPrint/line_2026.js`: un `diff` contra el blob
da solo la línea 372. El archivo no tiene rutas absolutas de estáticos, así que no hubo cambios 3a.

### Comportamientos del CMS que se conservan a propósito (D4, original por defecto)

1. **Checkboxes "Display items" y filtro "Nombre del equipo" sin efecto.** Usan `ng-model` primitivo (`showVictim`, `teamName`, …) adentro de un `ng-if`, que crea un scope hijo. El controlador nunca ve el cambio. Por defecto solo se muestra la columna Team (`gamesPrint/line_2026.js:5`). Los filtros de Ronda y Pista sí funcionan, porque son objetos (`Rrounds[key]`). Lo verifica `tests/salidas-planillas.html`. Queda como pendiente proponer la corrección detrás de `corregirBugsVisuales`.
2. **Botón "Export XLSX" (modo Ranking) sin efecto.** `exportRankingXlsx` no está definido en el JS de la página, y el pug no carga ExcelJS.
3. **"Please use Google Chrome to print this page."** Texto original.
4. **Bloque `#ranking-export` visible en modo lista** (competencia + comentario del ranking): markup original.

## 5. `local/ui/movil-salidas.css`

Solo afecta `@media screen`, así que la impresión es idéntica al CMS. No cambia el markup.

- `≤ 1024 px` o `pointer: coarse`: botones de la cabecera de Config, `.form-control` e `.input-group-text` con `min-height: 44px`. Con el CSS original medían 30-38 px.
- `≤ 768 px`: `table.custom { display:block; overflow-x:auto }`. Con todas las columnas encendidas, la tabla se desplaza sola a lo ancho y la página no.

## 6. Pruebas

`python tests/salidas-correr.py [--pasos png,pdf,angular,editor,planillas,capturas,analisis]` levanta el puerto 8808
y usa Edge headless. El servidor de prueba es `http.server` con 3 agregados solo para tests:

- `GET /__latido`
- `POST /__archivo` (guarda en `tests/capturas/salidas-*`)
- `POST /__resultado`

| Página | Qué prueba |
|---|---|
| `tests/salidas-png.html` | PNG del fixture oficial: dimensiones calculadas aparte, píxeles no blancos/naranja/celeste/negro, headers, errores 400/404, `image/:mapid` con los mismos bytes |
| `tests/salidas-pdf.html` | PDF de mapa A4/Letter, planilla del editor, `scoresheet2` con 2 corridas puntuadas (2 páginas, filtros run/startTime/offset), export (maps PDF, ZIP de PNG, scoresheets) y errores |
| `tests/salidas-angular.html` | `$scope.generateOutput` extraído del JS real del editor, con `$http` real y el decorador |
| `tests/salidas-editor.html` | `editor.html?map=<id>` real en iframe: clics en las opciones y en el botón Generate PDF/PNG |
| `tests/salidas-sembrar.html` + `tests/salidas-planillas.html` | `planillas.html` con 2 corridas, modo Ranking, comportamiento de filtros, `@media print` |
| `tests/salidas-captura.html` | Capturas de `planillas.html` a 1366x900, 1024x768 y 412x915, con medición de scroll horizontal, controles inalcanzables, controles < 40 px y peor caso con todas las columnas |
| Paso `analisis` (Python) | pypdf (cabecera y páginas, texto "Competition  Rescue Line" en la planilla del editor), PyMuPDF (rasteriza cada PDF a `tests/capturas/salidas-*-pN.png`) y OpenCV (decodifica el QR `L;<runId>` de cada planilla) |
| `tests/salidas-verbatim.py` | Regiones verbatim contra `git show d805502` |

El visor de PDF integrado de Edge no dibuja el documento en `--headless=new` (la captura sale gris liso). Por eso la
captura de referencia de los PDF es el rasterizado de PyMuPDF.

## 7. Desvíos

1. **QR.** qrcode-generator en lugar de qr-image. El texto codificado es idéntico, y OpenCV decodifica `L;<runId>`. Los bytes del PNG del QR y, posiblemente, la máscara del patrón difieren.
2. **Bytes del PNG y del PDF.** No son iguales a los del servidor: el antialias y el codificador PNG de Chromium difieren de @napi-rs/canvas, y los PDF llevan otra fecha de creación e id. Dimensiones, coordenadas en pt, MediaBox, cantidad de páginas y contenido sí son los mismos.
3. **ZIP del export de PNG** sin compresión (STORE). El CMS usa deflate nivel 9.
4. **Errores asíncronos.** Cuando en el CMS el pedido quedaba colgado o daba 500 (excepción dentro de un callback de `exec` o una promesa rechazada), acá responde 500 `{msg:'Error interno del backend local', err}`.
5. **Solo la regla de planilla 2026.** `readdirSync` devuelve `['2026.js']` (D8: Entry 2026E queda fuera de v1).
6. **Planilla del editor titulada "Competition  Rescue Line"**, igual que el original (C6): `scoreSheetPDFLine2.js:72` lee `map.competition.name` y el editor no lo manda.
7. **Estilos móviles** en `local/ui/movil-salidas.css`, solo para pantalla (§5).
