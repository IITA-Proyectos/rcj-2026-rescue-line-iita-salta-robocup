# Cambios del área editor respecto del CMS

Fuente: `robocup-junior/rcj-rescue-cms`, commit `d805502` (bytes tomados con `git show d805502:<ruta>`).
Referencia de lo común (markup, clases, estilos inline, orden): HTML vivo de `https://intl.rcj.cloud/service/editor/line/2026`
(`scratchpad/live/service_editor_line_2026`).

Archivos del área:

| Archivo | Qué es |
|---|---|
| `editor.html` | Render a mano de `views/admin/mapEditor/line_2026.pug` (extends `includes/modern_layout`) en **modo admin** (D1) |
| `javascripts/admin/mapEditor/line_2026.js` | Copia del CMS (la hace `herramientas/importar_cms.py`, que aplica la regla 3a) + los cambios de §2 |
| `local/tactil.js` | Capa táctil nueva (D5, flag `tactil`) |
| `local/ui/movil-editor.css` | CSS nuevo solo para pantallas angostas (< 768 px, celular) |
| `tests/editor-*` | Pruebas (§5) |

`templates/tile.html` y `templates/line_editor_modal.html` **no se tocaron** en esta área: solo tienen la regla 3a que aplica
el importador de assets (`images/tiles/...` relativo). El modal de propiedades se hace usable en pantallas bajas con CSS
(scroll interno), sin cambiar su contenido.

## 1. `editor.html` (render del pug)

Orden de `<head>`: el de `herramientas/fragmentos-head.md` (common_component → locales → append scripts del pug → page_css →
modern_layout → cola de head.pug), confirmado contra el HTML vivo. Diferencias con el HTML vivo (que es el modo público):

| Parte | CMS / HTML vivo | Local | Motivo |
|---|---|---|---|
| `<meta charset="utf-8">` | no está | primero en `<head>` | `python -m http.server` no manda charset (hallazgo de assets) |
| Globales `line_2026.pug:11-15` | `mapId = "#{mapId}"`, `competitionId = "#{competitionId}"`, `pubService = !{pubService \|\| false}`, `leagueId = "#{leagueId}"` (los inyecta `routes/admin.js:520` y `:540`) | `mapId = RCJLocal.param('map')`, `competitionId = RCJLocal.param('competition')`, `pubService = false`, `leagueId = "Line"` | D1: modo admin local |
| Arranque de Angular | pug resolvía `competitionId` en el servidor (siempre viene en la URL `/admin/<cid>/Line/mapEditor[/<id>]`) | si falta `?competition`, se difiere el bootstrap con `NG_DEFER_BOOTSTRAP!` (API pública de AngularJS) hasta completar `competitionId` desde la base: competencia del mapa (`GET /api/maps/line/<id>`); sin mapa, la primera competencia con liga Line (con la base vacía crea las semillas D10). Reserva de 10 s | `RCJLocal.ruta('/admin/<cid>/Line/mapEditor/<id>')` devuelve `editor.html?map=<id>` (sin competencia); el controlador lee la global en su construcción (`L26:97`) y la usa en `saveMap` (POST), en la redirección y en `tileCount` |
| Scripts de clase C/X (06) | `ngAlertify`, `socket.io`, `ui-select` js/css, `bootstrap-fileinput` (js, theme fa, locale ja, css), `html2canvas` | comentados en su lugar | sin uso en el editor; `theme.min.js` es un soft-404 en el sitio vivo (SyntaxError en su consola) |
| Backend local | — | `local/config.js`, `io-shim.js`, `nucleo/*`, `render/registrar.js` (E8 de salidas), `http-backend.js` + `RCJLocal.instalarBackend('LineEditor')` después del JS de página | ESPEC §4 |
| Capa táctil | — | `components/mobile-drag-drop/index.min.js`, `scroll-behaviour.min.js`, `default.css` y `local/tactil.js` después de `line_2026.js` | D5 |
| CSS móvil | — | `<link href="local/ui/movil-editor.css">` después de `modern_modal.css` | requisito de uso en celular 412x915 (§4) |
| Manifest | `<link rel="manifest" href="/manifest.json">` | comentado (pendiente de docs) | fragmentos-head |
| `stylesheets/fonts.css` | enlazado | omitido | ESPEC §1 (fuentes rotas en el origen) |
| Navbar `a.navbar-brand[href=/home]` | `/home` | `href` puesto con `RCJLocal.ruta('/home')` (script inline después de la navbar) → `index.html` | regla 3b |
| Menú de usuario / botón Login (`navbar.pug:13-37`) | según sesión | omitido | offline no hay sesión |
| `include login_modal` (`#loginModal`, `$.post('/api/auth/login')`) | presente | omitido (comentario en su lugar) | no hay servidor de sesión |
| Modal de idioma (`language_modal.pug`) | tarjetas EN / JA | EN / JA intactas + segunda fila con ES (`changeLanguage('es')`) | regla 3c |
| Hero (breadcrumb, subtítulo, SAVE/Save As, alerta noStart) | rama `pubService` (público) en el HTML vivo | rama `!pubService` del pug (`line_2026.pug:35-42, 53-70`): `Home › Admin › {{competition.name}} › Line Maps › Editor`, `{{competition.name}} - {{league.name}} Map Editor 2026`, botones Save y Save As (`parent` nunca se pasa) | D1 |
| Breadcrumb `go('/admin')`, `go('/admin/'+competitionId)`, `.../maps` | rutas del CMS | sin cambio en el markup: `go()` pasa por `RCJLocal.ruta` (§2) → `index.html` / `mapas.html?competition=<cid>` | regla 3b |
| `images/tiles/{{…}}` (paleta y fantasma), `images/logo.png`, favicons | absolutas `/images/...` | relativas | regla 3a |
| Resto del `main_content` y footer | — | idéntico al HTML vivo (clases, estilos inline, orden, rareza `#outputCollapse` hermano del card) | "tal cual" |

## 2. `javascripts/admin/mapEditor/line_2026.js`

Líneas del archivo local (el original tiene 1690 líneas; las de `templateUrl` son regla 3a del importador de assets).

| Archivo:línea local (original) | Antes | Después | Motivo |
|---|---|---|---|
| `:188` (`L26:188`) | `window.location = path` | `window.location = RCJLocal.ruta(path) // [rcj-line-offline] regla 3b` | `go()` del breadcrumb |
| `:810` (`L26:810`) | `window.location.replace("/admin/" + targetCompetitionId + "/" + leagueId + "/mapEditor/" + response.data.id)` | `window.location.replace(RCJLocal.ruta("/admin/" + … + response.data.id)) // [rcj-line-offline] regla 3b` | Save As → abre la copia |
| `:977` (`L26:977`) | `window.location.replace("/admin/" + competitionId + "/" + leagueId + "/mapEditor/" + response.data.id)` | `window.location.replace(RCJLocal.ruta(…)) // [rcj-line-offline] regla 3b` | Save de un mapa nuevo → `editor.html?map=<id>` |
| `:849`, `:880` (`L26:849`, `:880`) | `window.open(url, '_blank')` | **sin cambio** | `url` es un `blob:` creado con `URL.createObjectURL` (PDF generado), no una ruta del CMS. Pasarlo por `RCJLocal.ruta` lo rompería (hoy `ruta()` convierte un `blob:` del mismo origen en `index.html`; reportado a backend) |
| `:1052-1076` (nuevo, antes de `L26:1052`) | — | función `adaptarImportacionLocal(data, tileSets)` | Desvío D1 (ESPEC §2, 08 §5.2 "adaptador permitido"): import tolerante a `tiles` como array (formato de `GET /api/maps/line/:id`) y a `tileType` como id. Con el formato oficial (objeto `"x,y,z"` y `tileType` embebido) devuelve `data` sin tocarlo |
| `:1099` (`L26:1071`, dentro de `reader.onload`) | `var data = JSON.parse(reader.result);` | + `data = adaptarImportacionLocal(data, $scope.tileSets); // [rcj-line-offline] desvío D1` | idem |

No se tocó nada más: `pathFinder.js` (PFc), `updateTileIndex`, directivas DnD, `cycleTileLevel`, `export`, el resto del import,
Toasts y textos en inglés quedan verbatim. Verificación: `git show d805502:public/javascripts/admin/mapEditor/line_2026.js`
contra el archivo local da solo los 7 bloques de arriba (3 de regla 3b, 2 del desvío D1, 2 de regla 3a).

## 3. `local/tactil.js` (D5, flag `RCJLocal.flags.tactil`, default `true`)

Se activa solo si hay pantalla táctil (`'ontouchstart' in window` o `maxTouchPoints > 0`) y el flag no es `false`. En escritorio
sin touch no agrega nada (verificado: `RCJLocal.tactil.activo === false`, sin barra, sin polyfill). Todos los gestos terminan
en los MISMOS handlers del CMS:

| Gesto | Implementación | Handler del CMS que ejecuta |
|---|---|---|
| Arrastrar con el dedo (paleta → celda, celda → celda, celda → paleta) | `MobileDragDrop.polyfill` (mobile-drag-drop 2.3.0-rc.2 de `components/`) con `holdToDrag: 300` y `scrollBehaviourDragImageTranslateOverride`: traduce touch a `dragstart/dragenter/dragover/drop/dragend` con `dataTransfer.setData/getData`. Una celda vacía del mapa no inicia arrastre (así se puede desplazar desde ahí). **Además** cancela `dragenter` (listener en captura) sobre los destinos del CMS (`[x-lvl-drop-target]`): el polyfill sigue la especificación y solo toma como destino un elemento que cancela `dragenter`, pero `lvlDropTarget` solo cancela `dragover` (Chrome de escritorio lo acepta igual); sin esto el destino quedaba en `<body>` y el `drop` nunca llegaba (hallado con `tests/editor-tactil.html`: `dragstart:img, dragenter:tile, dragover:body`, sin `drop`) | directivas `lvlDraggable` / `lvlDropTarget` (`L26:1418-1673`) |
| Pulsación larga ~500 ms sobre una celda del mapa | despacha `contextmenu` sobre el `<tile>`; si el navegador ya disparó el suyo (Chrome Android) no duplica; se cancela si el dedo se mueve > 10 px, con un segundo dedo o si empieza un arrastre; el clic de ese mismo toque se descarta (si no, rotaría la baldosa o cerraría el modal) | `ng-right-click="open(c,r)"` (modal o "Oops!" en celda vacía) |
| Botón flotante **Selección** | con el modo activo, un clic en una baldosa se re-despacha con `ctrlKey: true` | `ng-click="handleTileClick(c, r, $event)"` → `toggleSelection` |
| Botones **Deshacer / Rehacer / Cortar / Borrar selección** | `scope.undo()`, `scope.redo()`, `scope.cutSelection()`, `scope.bulkDelete()` dentro de `$apply` | las mismas funciones del scope |
| Botón **Salir del sello** | `keydown` Esc (`keyCode` 27) sobre `document` | listener de teclado `L26:734-765` (el Esc no tiene función propia) |
| Paneo | scroll nativo del `#map-container` con uno o dos dedos; el marquee sigue siendo solo de mouse | — |
| Modal de propiedades | CSS: `.modal-content` en columna con `max-height: 100dvh - 3rem` y `.premium-modal-body` con `overflow-y: auto` | contenido del template sin cambios |

Los botones se habilitan con `canUndo()`, `canRedo()`, `hasSelection()` e `isPasting` (un `$watch` sobre el scope). Textos
de los botones en español. En pantallas < 768 px la barra ocupa todo el ancho (seis botones iguales, ≥ 50 px de alto) y el
`body` recibe `padding-bottom: 76px` para que la barra no tape el pie.

## 4. Uso en celular (412x915), tablet (1024x768) y notebook (1366x900)

`local/ui/movil-editor.css` (solo `@media (max-width: 767.98px)`; en 768 px o más no aplica):

- La fila mapa + paleta del pug es `flex-nowrap` con la paleta fija en 360 px: en 412 px el mapa quedaba con ~0 px. Se apilan:
  mapa al 100 % del ancho y 60vh (mín. 340 px), paleta al 100 % y 55vh (mín. 320 px). Hace falta `!important` para pisar los
  estilos inline y `.h-100` de Bootstrap.
- La barra de dimensiones/víctimas/duración/finished/calculadora envuelve en filas (sin bordes separadores).
- La alerta "No start tile" pasa de `position:absolute; top:-45px` a estática (tapaba el título).
- Hero con menos padding lateral, título a 1.4rem.
- Modal con scroll interno también sin touch (en celular siempre es alto).

No se cambió el markup del CMS para esto. En 1024x768 y 1366x900 el layout es el original.

## 5. Pruebas

`python tests/editor-correr.py` (puerto 8803) levanta un `http.server` con dos agregados SOLO de prueba:
`/__latido` (igual que backend) y la inyección de `tests/editor-captura.js` en las respuestas de `/editor.html` (el archivo en
disco no cambia). Cada página abre `editor.html` real en un iframe del mismo origen y lo maneja con eventos DOM y funciones
del scope.

`tests/editor-captura.js` (solo prueba) hace cuatro cosas antes de que cargue la app:
1. junta errores (`onerror`, recursos que no cargan, `unhandledrejection`, `console.error`) y avisos para la página de prueba;
2. intercepta `<a download>.click()` y `window.open` (export JSON, PNG, PDF) y guarda href/nombre en lugar de descargar;
3. **`requestAnimationFrame` con respaldo por `setTimeout`** y `scrollTo` sin `behavior:'smooth'`: Edge headless con
   `--virtual-time-budget` no entrega cuadros de forma confiable (dentro del iframe casi nunca), y ngAnimate / `$animateCss`
   de ui-bootstrap esperan un cuadro para terminar: los modales quedaban a mitad del fundido (`translateY(-50px)`) y nunca se
   quitaban del DOM, y `centerMap()` (scroll suave) no centraba el mapa en las capturas. Es un problema del entorno de prueba,
   no de la app (en un navegador real hay cuadros); las animaciones quedan encendidas;
   además una hoja `*{transition-duration:0s; animation-duration:0s; scroll-behavior:auto}` (todo `!important`): las
   transiciones CSS tampoco avanzan (el fundido de Bootstrap dejaba el modal en `translateY(-26px)`) y
   `#map-container` tiene `scroll-behavior: smooth` en `line_modern.css`, así que `scrollIntoView` y `centerMap` no llegaban;
4. `?__latido=N` y `?__modal=x,y` para las capturas.

Capturas de celular: Edge headless no dibuja ventanas de menos de 500 px de ancho (con `--window-size=412,915` renderiza a
~500 px y recorta la imagen, lo que hacía parecer cortada la barra y el hero). La captura de 412x915 se toma con
`tests/editor-marco.html` (editor.html en un iframe de 412x915 dentro de una ventana de 500 px) y se recorta con Pillow.
Las medidas de `tests/editor-movil.html` se toman dentro de un iframe del ancho exacto, así que no tienen ese problema.

| Página | Qué prueba |
|---|---|
| `tests/editor-importar.html` | modo admin (globales, botones, breadcrumb), T4 (import por `#select` + export → sha256 `df7986…251e`, round-trip de 3 vueltas), import tolerante (D1), T5 (casos T1-T7 de 01 §7.3 con el `pathFinder.js` real vía `updateTileIndex`) |
| `tests/editor-guardar.html` | alerta y Toast de inicio faltante, Save (POST) + redirección a `editor.html?map=` + reapertura que conserva todo, PUT, calculadora (popup 210 / 576), `tileCount` entre dos mapas del mismo tileset (scope y badge), Save As |
| `tests/editor-edicion.html` | spinners, paleta (rotar + arrastrar con DnD sintético), rotación, undo/redo (botones y Ctrl+Z/Y), mover y borrar arrastrando, modal (checkpoint, levelUp, start, Cancel, "Oops!"), Ctrl+clic, copiar/pegar con sello, rotar y borrar en grupo, Ctrl+X, Esc, pisos, salidas PNG/PDF/planilla |
| `tests/editor-tactil.html` | (con `--touch-events=enabled`) pulsación larga → modal, toque que se desplaza / dos dedos no abren nada, barra (Deshacer, Rehacer, Selección, Cortar, Salir del sello, Borrar), arrastre con el dedo desde la paleta (mobile-drag-drop), "Oops!" en celda vacía |
| `tests/editor-movil.html` | (con touch) en 412x915, 1024x768 y 1366x900: sin scroll horizontal, mapa y paleta con lugar, controles dentro del ancho, barra dentro de la pantalla con botones ≥ 44 px, modal dentro de la pantalla con Save/Cancel visibles y grilla de transiciones alcanzable |

| `tests/editor-scroll.html` | `#map-container` se desplaza con `scrollTop/scrollLeft` y `scrollTo({…})`, y `centerMap()` deja la tabla visible |

Capturas en `tests/capturas/editor-*.png` (1366x900, 1024x768, 412x915, modal en tablet y celular).

## 6. Resultado de la última corrida (2026-09-13, Edge headless, puerto 8803)

| Página | Verificaciones | Fallas | Errores de consola |
|---|---|---|---|
| `editor-importar.html` | 30 | 0 | 0 |
| `editor-guardar.html` | 29 | 0 | 0 |
| `editor-edicion.html` | 45 | 0 | 0 |
| `editor-tactil.html` | 34 | 0 | 0 |
| `editor-movil.html` | 33 | 0 | 0 |
| `editor-scroll.html` | 3 | 0 | 0 |

Valores clave: T4 export sha256 `df7986072ce370a1c5347ce76b2f4eacb8e9bf9de228cff0932652834de1251e` (idéntico, 3 vueltas);
T5 T1-T7 como 01 §7.3 (T3: `RangeError: Maximum call stack size exceeded` con el lazo 270/0/90/180); calculadora
`Line Trace Score 210 / Final Score 576`; fixture: `indexCount 14`, `EvacuationAreaLoPIndex 2`; tileCount entre dos mapas
verificado en el scope y en el badge; PNG, PDF de mapa y planilla generados como `blob:` (área salidas).

Errores de consola que tiene el original y acá no: el `SyntaxError` de `bootstrap-fileinput/themes/fa/theme.min.js` (soft-404
en el sitio vivo; el script se omite) y el warning `Translation for admin.lineMapEditor.mapName doesn't exist` (`lang/es.json`
trae la clave). En modo admin el `TypeError` de `leagues.find` del público no ocurre (`competitionId` siempre existe).

Hallazgos que corrigieron código propio durante las pruebas:
- `local/tactil.js`: faltaba cancelar `dragenter` para que el soltar con el dedo llegue al `drop` del CMS (§3).
- `local/ui/movil-editor.css`: en 412 px la fila mapa + paleta dejaba el mapa sin ancho (§4).

Limitaciones conocidas de la verificación:
- Todo es Edge headless con `--touch-events=enabled` y `Touch`/`TouchEvent` sintéticos: **no se probó en un celular o tablet
  real** (Chrome Android / iPadOS Safari), donde la pulsación larga puede disparar además el menú nativo o la selección de texto.
- En la captura de celular (iframe dentro de ventana de 500 px) no se ve la barra flotante y los botones del modal salen sin
  texto; las medidas de `editor-movil.html` a 412x915 confirman que la barra está dentro de la pantalla (botones ≥ 44 px) y
  que Guardar/Cancelar tienen texto y color legible. Se atribuye a la forma de capturar, no al layout.
- `tests/assets-verificar.py` marca dos falsos positivos en archivos de prueba del editor (`tests/editor-guardar.html`: selector
  `src^="images/tiles/"` que apunta al documento del iframe; `tests/editor-tactil.html`: el texto "local/tactil.js").
- Una corrida de una página de diagnóstico descartada terminó sin volcar el DOM y con un
  `TypeError: Cannot read properties of undefined (reading 'length') Possibly unhandled rejection` al abrir un mapa recién
  creado con `RCJLocal.ingestMap`; no se repitió en ninguna de las otras corridas (que usan el mismo flujo).
