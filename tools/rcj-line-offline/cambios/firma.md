# Cambios del área firma respecto del CMS

Fuente: `robocup-junior/rcj-rescue-cms`, commit `d805502`. Todas las citas `archivo:línea` son de ese commit salvo que
digan "local". Los bytes del CMS se tomaron con `git show d805502:<ruta>`.

Archivos del área:
- `firma.html`: render de `views/sign/line_2026.pug`, con el include `views/view/common/line_2026.pug`.
- `vista.html`: render de `views/view/line_2026.pug` (con el include común y `includes/footer`). Con `?iframe=true` rinde
  `views/view_iframe/line_2026.pug`.
- `javascripts/sign/line_2026.js`: solo regla 3b y desvíos por flag. Las rutas relativas (3a) ya las había aplicado
  assets.
- `templates/line_view_modal.html`: ícono FA4 detrás del flag. Las rutas 3a ya las había aplicado assets.
- `local/ui/movil-firma.css`: CSS extra solo para pantallas angostas (§8), enlazado desde `firma.html` y `vista.html`.
- `tests/firma-*`, `tests/capturas/firma-*.png` y `tests/capturas/vista-*.png`.

## 1. Render de los pug

Node y pug no están instalados, así que el HTML se escribió a mano siguiendo las reglas de salida de pug 3 sin
`pretty`:
- **Sin doctype.** Los tres pug empiezan con `html(ng-app="ddApp")` sin `doctype`, y `app.js` no define la opción
  `doctype`. El CMS sirve estas páginas **en modo quirks**. Por eso funcionan estilos sin unidades como
  `padding:30 0 30 0` y `margin:100 0 100 0`, y las tablas no heredan el tamaño de letra. Las páginas locales tampoco
  llevan doctype, para verse igual (verificado: `document.compatMode === 'BackCompat'`).
- Atributos: `class` primero (comprobado contra el HTML vivo del editor). Los booleanos van como `disabled="disabled"`,
  que es la salida sin doctype. Los vacíos van como `<br/>` y `<hr/>`. `&` y `>` dentro de los atributos van escapados.
- Texto de pug:
  - `tag  texto` conserva un espacio inicial.
  - `| texto` no conserva espacio.
  - Dos líneas `|` seguidas se unen con un salto de línea, que se ve como un espacio, por ejemplo
    `{{calc_victim_type_lop_multiplier(0)}}\n - (x0.05 ×`.
  - Entre etiquetas no hay espacios en blanco: los inline se escribieron pegados para no agregar separaciones.
- El comentario `// Navbar content` sale como `<!-- Navbar content-->`.
- Globales que inyectaba pug, definidos en un `<script>` inline antes de los scripts comunes (fragmentos-head §2.3/§2.4):

| Página | Global | Valor en el CMS | Valor local |
|---|---|---|---|
| firma | `runId` | `"#{id}"` | `RCJLocal.param('run')` |
| firma | `timeIncrement` | `false` | `false` |
| firma | `iframe` | `"#{iframe}"`, que rinde `""` porque `routes/line.js:123` no lo pasa | `""` |
| vista | `runId` / `timeIncrement` | `"#{id}"` / `false` | `param('run')` / `false` |
| vista | `iframe` | `""` | `RCJLocal.param('iframe')`, que es `""` sin el parámetro |
| vista | `#{rule}` (fila Regla) | `"2026"`: `ruleDetector` solo manda a `view/line_2026` las corridas con regla 2026 | texto fijo `2026` |
| vista `?iframe=true` | `runId` / `timeIncrement` | `"#{id}"` / `true` | `param('run')` / `true` |

- `if user` (`view/line_2026.pug:93-120`) **no se rinde**: la ruta no pasa `user` (04 §0.6), así que en producción ese
  bloque de comentario y firmas nunca aparece. Queda indicado con un comentario HTML.
- El footer (`includes/footer`) usa el fragmento 1.G, con copyright y versión fijos del sitio vivo.
- `<head>`: fragmentos 2.3 y 2.4 de `herramientas/fragmentos-head.md`, con `<meta charset="utf-8">` primero,
  `local/*`, los scripts y CSS comunes con los mismos omitidos, `sign/line_2026.js`, `local/http-backend.js` +
  `RCJLocal.instalarBackend('ddApp')`, `translate_config.js` y `jSignature.min.js` (este último solo en la firma).
- **Variante iframe en `vista.html`.** Las dos variantes van en `<template>`. Un script inline al final del `<body>`
  clona la que corresponde y borra las dos plantillas antes del `DOMContentLoaded`, que es cuando arranca Angular.
  Así la variante que no se usa no pide imágenes. En `<head>`:
  - `document.title` pasa a `Rescue Line View Iframe`;
  - se agrega el script inline de `view_iframe/line_2026.pug:10-34`, con `cookie sRotate=0` y `tile_size()`
    redefinido. Va después del JS de firma, como en el pug, y se asigna como `window.tile_size`. El cuerpo de la
    función es verbatim.
- En la variante iframe el pug no declara `iframe`. Localmente vale `"true"`, y solo se usa en la redirección 401
  (`sign/line_2026.js:292`), que offline no ocurre.

## 2. Cambios en archivos del CMS (regla 3b y desvíos)

Líneas "local" = número de línea en `javascripts/sign/line_2026.js` después del cambio.

| Archivo:línea (CMS → local) | Regla | Antes | Después | Motivo |
|---|---|---|---|---|
| `sign/line_2026.js:11` → local `12-20` | apoyo | — | `function rcjFlag(nombre)`: lee `RCJLocal.flags` y devuelve `false` si falla | acceso único a los flags |
| `sign/line_2026.js:99` → local `110-111` | D4 | — | `$scope.rcjCorregirBugsVisuales = rcjFlag('corregirBugsVisuales')` | lo usa la numeración de la tabla de rescate |
| `sign/line_2026.js:145` y `:221` → local `157-159`, `235-237` | D4 | `point: 5 * $scope.showedUp` | `point: rcjFlag('corregirBugsVisuales') ? 5 * ($scope.showedUp \|\| $scope.raw_score > 0) : 5 * $scope.showedUp` | +5 implícito del servidor (`scoreCalculatorRules/2026.js:81-83`). Si `showedUp` es false, `raw_score > 0` ⇔ el servidor sumó 5. El `status` de la tarjeta sigue siendo `showedUp` |
| `sign/line_2026.js:328` → local `344-346` | D4 | `if (v.victimType == "LIVE") liveCount ++;` | `if (v.victimType == "LIVE" && !(rcjFlag('corregirBugsVisuales') && v.zoneType == "RED")) liveCount ++;` | el servidor cuenta solo las LIVE efectivas (`2026.js:61-68`). Se conserva el `i` global sin declarar del original |
| `sign/line_2026.js:400` → local `418-425` | 3b | `window.location = path;` | marca de sesión si `path` empieza con `/line/judge/`, y `window.location = RCJLocal.ruta(path);` | rutas del CMS → páginas locales; "To correct" vuelve al juez salteando el pre-chequeo (§3) |
| `sign/line_2026.js:631-639` → local `656-666` | D6 | `err_mes += "[" + txt_ref_sign + "] "` (y lo mismo para `txt_cref_sign`) | `if (!rcjFlag('soloFirmaCapitan')) err_mes += …` | con el flag solo es obligatoria la firma del capitán; las otras se envían si existen |
| `sign/line_2026.js:970` → local `998-1000` | D4 | — | `$scope.rcjCorregirBugsVisuales = rcjFlag('corregirBugsVisuales')` en `ModalInstanceCtrl` | para el ícono del modal |
| `templates/line_view_modal.html:14,24,48,60,84,94,120,130,154` | D4 | `<i class="fa fa-play-circle-o fa-fw fa-2x" ng-show=…>` | `<i class="fa-fw fa-2x" ng-class="rcjCorregirBugsVisuales ? 'far fa-play-circle' : 'fa fa-play-circle-o'" ng-show=…>` | FA4 `fa-play-circle-o` no tiene glifo en FA5. Sin el flag la clase final es la misma que en el original |
| `view/common/line_2026.pug:183` (en `firma.html` y `vista.html`) | D4 | `{{j*4 + (i+1)}}` | `{{j*(rcjCorregirBugsVisuales?3:4) + (i+1)}}` | el 2º bloque del original numera 5,6,7; con el flag, 4,5,6 (igual que el juez, `JPUG:198`) |
| `view_iframe/line_2026.pug:11` (en `vista.html`) | desvío | `document.cookie = 'sRotate=0';` | `document.cookie = 'sRotate=0; path=' + location.pathname;` | en el CMS la cookie queda con path `/line/view/<id>` y no toca al juez ni a la firma. Localmente todas las páginas comparten carpeta: sin acotar el path, la variante iframe pisaría la rotación del juez (`sRotate`, path `/`) |
| `firma.html`, `vista.html` (script inline nuevo) | D5 | — | con `RCJLocal.flags.audioResume` (default true), `context.resume()` en el primer `pointerdown`/`mousedown`/`touchend`/`keydown` | 08 §5.8 desvío 6: el `AudioContext` de `sign/line_2026.js:1113` nace suspendido por la política de autoplay |

Todo lo demás de `sign/line_2026.js` es byte a byte igual al blob, salvo las 5 líneas de la regla 3a que ya había cambiado
assets. Esto incluye `loadNewRun`, `launchSocketIo`, `send_sign`, `success_message`, `toggleSign`, la directiva `tile`,
`ModalInstanceCtrl` y `tile_size`. Para verificarlo: `git show d805502:public/javascripts/sign/line_2026.js | diff - javascripts/sign/line_2026.js`.

### Flags (valores por defecto de ESPEC §2)

| Flag | Default | Qué cambia en firma y vista |
|---|---|---|
| `corregirBugsVisuales` | `false` | Cuatro correcciones: (1) numeración `j*3`; (2) la tarjeta de inicio vale 5 si el servidor sumó el +5 implícito, así "Item points" deja de quedar inflado en 5; (3) conteo de vivas previas como el servidor, así el producto de los `x` por víctima coincide con el multiplicador; (4) ícono de inicio del modal en FA5 |
| `soloFirmaCapitan` | `false` | Solo exige la firma del capitán. Si hay firma del árbitro o del asistente, se envía igual. No oculta los bloques de firma |
| `audioResume` | `true` | reanuda el audio en el primer gesto |

Divergencias que **no** corrige ningún flag porque son fieles al CMS (D4):
- "Base points", "times", "Zone", "/victim", "points" y los `swal` "Finish Run?", "Yes, finish it!", "Recorded!" y
  "We couldn't connect…" siguen en inglés.
- "Complete" sin dibujar genera igual un SVG y cuenta como firmado.
- El socket pisa `normalizedScore` con `undefined`.
- `clearSign` conserva la firma anterior en `signData` hasta el próximo "Complete".

## 3. "To correct" → juez: contrato con el área juez

- **Quién escribe:** `$scope.go` de `sign/line_2026.js`, justo antes de navegar, cuando la ruta del CMS empieza con
  `/line/judge/`. Eso solo pasa con el botón "To correct" de `firma.html`.
- **Qué escribe:** `sessionStorage.setItem('rcjVolviDeFirma', runId)`, con el id de la corrida de la firma.
- **A dónde navega:** `RCJLocal.ruta('/line/judge/<id>?return=<return>')` → `juez.html?run=<id>&return=<return>`. El
  `return` va sin codificar, como en el CMS (probado).
- **Qué debe hacer el juez:** reemplazar la condición `document.referrer.indexOf('sign') != -1`
  (`judge/line_2026.js:202`) por "`sessionStorage.getItem('rcjVolviDeFirma') === runId`, o bien el referrer". El efecto
  es el mismo: `$scope.checked = true`, `$scope.fromSign = true` y los `tile_size` a 10/200 ms. Conviene hacer
  `removeItem` después de leerla, así una recarga posterior del juez vuelve a mostrar el pre-chequeo.
  - Localmente el referrer es `…/firma.html?run=…` y **no** contiene "sign", por eso hace falta la marca.
  - `sessionStorage` vive por pestaña: se comparte con los iframes del mismo origen y se pierde al cerrar la pestaña.

## 4. Socket (io-shim) y `setInterval(launchSocketIo, 15000)`

- `io(window.location.origin, {transports:['websocket']})` (`sign/line_2026.js:114`) usa `local/io-shim.js`. Cuando
  cualquier pestaña o marco del mismo origen hace el PUT de la corrida, el backend emite `runs/<id>` → `data` por
  `BroadcastChannel`, y la vista y la firma se actualizan: puntaje, tiempo, LoPs, desglose, víctimas y color de la
  navbar de la variante iframe. Probado con la vista en un iframe y el PUT desde la página padre.
- **El `setInterval` se conserva tal cual.** Cada 15 s vuelve a llamar `socket.on('data', …)`, así que los handlers se
  duplican igual que en el CMS. No rompe nada:
  - cada handler asigna los mismos valores y llama `$scope.$apply()` fuera de un digest (el io-shim entrega desde una
    microtarea o desde `BroadcastChannel`, nunca dentro de un digest de Angular);
  - `emit('subscribe')` repetido no duplica la sala, porque es un `Set`.

  Medido en `tests/firma-vista-vivo.html`: después de 16 s hay 2 handlers y cada PUT dispara 2 actualizaciones, con la
  vista correcta y sin errores. Costo: después de N minutos abierta, cada evento corre ≈ 4·N digests. Con una sesión de
  práctica típica (una corrida de 8 min) no se nota. Si una vista queda abierta horas en un monitor, recargarla la
  limpia.

## 5. Notas para otras áreas

- **`?iframe=true` es ambiguo.** `RCJLocal.ruta('/line/view/<id>?iframe=true')` conserva la query y da
  `vista.html?run=<id>&iframe=true`, igual que `/line/view/<id>/iframe`. En el CMS esa URL (la de
  `ranking/line_2026.js:openRunDetails`) muestra la **vista normal**: el parámetro no cambia de plantilla. Si ranking la
  pasa por `ruta()`, va a ver la variante compacta. Hay dos salidas: ranking arma `vista.html?run=<id>` directamente, o
  backend distingue las dos formas en `ruta()`. Está reportado en `bugs_en_otros_modulos`.
- **`?return=` con `&`.** `getParam` del CMS parte la query por `&` y descarta los valores con `=`. Un `return` tiene
  que ser una ruta del CMS (`/line/<cid>/<league>`) o ir codificado con `encodeURIComponent`, nunca
  `corridas.html?competition=…&league=…` crudo.
- La fila Regla es texto fijo `2026`; si en el futuro se agrega Entry 2026E, su vista tiene que rendir su propia regla.

## 6. Pruebas

`python tests/firma-correr.py` levanta el servidor en 127.0.0.1:8805, con el mismo `/__latido` que backend, y corre las
páginas con Edge headless (`--dump-dom`). Además junta la consola de todos los marcos con `--enable-logging=stderr` y saca
las capturas de `tests/capturas/` con `--screenshot` sobre `tests/firma-captura.html`. Con `--sin-capturas` omite las
capturas.

| Página | Cubre |
|---|---|
| `tests/firma-flujo.html` | Corrida puntuada en status 3 sobre el fixture oficial. El oráculo coincide con el backend. Desglose de `firma.html` (navbar, `checkTotal`, bonus, "Item points" = elementos, cierre, producto de `x` = multiplicador, tarjetas, LoPs, tabla de rescate, grilla e imágenes). Oops! sin firmas y sin PUT. Tres firmas con trazos sintéticos de jSignature (`native` con 2 trazos, SVG base64 con `<path>`), Clear y nueva firma, comentario. Submit → "Finish Run?" → PUT `{comment, sign:{captain,referee,referee_as}, status:4}` → "Recorded!" → store en status 4 → OK navega a `corridas.html?competition&league`. "To correct" → `juez.html?run&return` con `rcjVolviDeFirma`. |
| `tests/firma-flags.html` | Con `showedUp=false` y 4 víctimas (LIVE/RED, LIVE/GREEN, DEAD/RED, LIVE/GREEN), en firma y vista. Original: inicio 0, "Item points" +5, producto de `x` ≠ servidor, numeración 5,6,7, ícono FA4 sin glifo. Con `corregirBugsVisuales`: todo coincide con el servidor, 4,5,6 y ícono FA5. `soloFirmaCapitan`: sin el flag pide árbitro y asistente; con el flag envía solo `captain` y guarda status 4. |
| `tests/firma-vista-vivo.html` | `vista.html` y `vista.html?iframe=true` en iframes: quirks, globales, información básica con Regla 2026, footer, sin bloque `if user`, cookie `sRotate` acotada, navbar por `navColor`, capas apiladas, reloj local con status 2. PUT desde el padre → las dos se actualizan en vivo (navbar, desglose, rescate, `【 ×mult 】`, color con status 3). Handlers duplicados después de 16 s. Back → `corridas.html`. |
| `tests/firma-movil.html` | Layout de `vista.html` y `firma.html` en 412×915, 1024×768 y 1366×900: nada se sale por la derecha, la navbar fija no tapa el principio, LoPs no se pisa con el plano, el plano entra en el ancho y el final de la página se alcanza. Variante iframe en 412. En 412: botones tocables, las 3 firmas con `TouchEvent` sintéticos (lienzo ≥ 300 px), Submit → "Finish Run?" y "Recorded!" dentro de la pantalla, PUT y status 4; modal de dirección dentro del ancho con OK alcanzable. A 1366 el CSS de celular no aplica. |
| `tests/firma-captura.html` | Mosaico de iframes (`ancho`/`alto`/`n`) para las capturas de 1366×900, 1024×768 y 412×915 |

Opciones de `firma-correr.py`: `--sin-capturas`, `--solo-capturas`, `--capturas=412,1024` (filtra por nombre de
archivo) y páginas sueltas como argumentos.

Resultados: ver el resumen de la corrida al pie (§7).

## 7. Resultado de la última corrida de pruebas

Corrida del 2026-09-13 con `python tests/firma-correr.py` (Edge headless, 127.0.0.1:8805, perfil corto en `%TEMP%`):

| Página / captura | Resultado |
|---|---|
| `tests/firma-flags.html` | OK — 40 verificaciones, 0 fallas, 0 errores de página, 0 errores de consola |
| `tests/firma-flujo.html` | OK — 59 verificaciones, 0 fallas, 0 errores, 0 consola. Incluye la integración con `juez.html`: después de "To correct" el juez queda con `checked=true`, `fromSign=true`, la marca consumida de `sessionStorage` y guardada en `history.state` |
| `tests/firma-vista-vivo.html` | OK — 31 verificaciones, 0 fallas, 0 errores, 0 consola. Tras 16 s hay 2 handlers `data` y cada PUT dispara 2 actualizaciones (fiel al CMS, §4) |
| `tests/firma-movil.html` | OK — 48 verificaciones, 0 fallas, 0 errores, 0 consola (vuelta a correr después de la regla 9 de §8; la primera vuelta dio 3 fallas: versión del footer fuera de pantalla, `.tilearea` de la variante iframe de 419 px y botón "To correct" de 30 px). Sonda `rAFenIframeEn1s` = 1 |
| 14 capturas (`tests/capturas/firma-*.png`, `vista-*.png`) | OK — todas generadas (> 5 KB), sin errores de consola. `firma-412x915-completa.png` y `firma-412x915-modal.png` son de antes de la regla 9 (el botón "Corregir" se ve de 30 px); `firma-412x915-arriba.png`, `vista-412x915-completa.png` y `vista-iframe-412x915.png` ya la incluyen |

Oráculo del flujo (corrida sembrada en status 3 sobre el fixture oficial): elementos 70 + checkpoints 48 (inicio 5 +
25 + 15 + tramo final 3) + bonus 45 = `raw_score` 163; multiplicador 2.197 (3 víctimas efectivas × 1.3); `score` 358 =
`Math.round(163 × 2.197)`. El desglose de `firma.html` cierra exactamente con el backend. Con `showedUp=false` la
diferencia conocida del CMS aparece tal cual sin el flag (inicio 0, "Item points" +5, producto de `x` 2.744 ≠ 1.96
del servidor, numeración 5,6,7) y desaparece con `corregirBugsVisuales` (`firma-flags.html`).

## 8. Uso en celular y tablet: `local/ui/movil-firma.css`

Requisito: la app es para entrenar y cada dispositivo (celular Android ~412×915, tablet, notebook) tiene que poder
hacer todo solo. El markup de `firma.html` y `vista.html` **no se tocó** para esto: el único cambio es un
`<link href="local/ui/movil-firma.css">` después de `stylesheets/fredrik.css` (excepción de propiedad permitida para
`local/ui/movil-<area>.css`). Todas las reglas están dentro de media queries por ancho, así que a 1200 px o más la
página se ve exactamente como el CMS (la prueba `firma-movil.html` verifica que a 1366 px el `padding-top` del body
sigue siendo el de `navbar_premium.css`).

Lo que se ve mal o queda inalcanzable en el CMS original en un celular, y la regla que lo corrige:

| # | Ancho | Problema en el original | Regla |
|---|---|---|---|
| 1 | < 576 | La navbar fija ocupa dos filas (~80 px) y `navbar_premium.css` reserva 70 px: tapa el principio de la página | `body { padding-top: 95px }` |
| 2 | < 576 | `tile_size()` fija `#card_area` a `innerHeight-130` px; con las columnas apiladas la lista de LoPs puede desbordar sobre el plano y deja un hueco enorme | `#card_area { height: auto !important }` y menos margen inferior en su columna |
| 3 | < 576 | Filas de números con `col-3`/`col-1`/`col-4` (bonus de salida): un `h1` de 2.5rem ("60 puntos") no entra en ~90 px y se pisa con la columna vecina | `h1` de 1.15rem en esas filas; `h1` de las alertas a 1.9rem |
| 4 | < 576 | `calc_victim_type_lop_multiplier(0) - (x0.05 × LoPs)` usa `font-size:1vw` (≈4 px) | 12 px |
| 5 | < 576 | Fila sobre el plano `col-3` pisos / `col-6` Subtotal / `col-3` rotar: los botones de piso no entran en ~100 px y el Subtotal los tapa (el botón del piso 1 queda inalcanzable) | pisos y rotar al 50 % en la primera línea, Subtotal abajo al 100 % (`order`) |
| 6 | < 576 | Botones de piso/rotar y OK del modal chicos para el dedo | `min-height`/`min-width` 44 px |
| 7 | < 576 | Títulos de sección de 2rem hacen el desglose muy largo | `h2` 1.5rem, Subtotal del plano 1.1rem |
| 8 | < 576 | `vista.html?iframe=true`: el plano va dentro de la navbar fija y el alert de LoPs/víctimas/multiplicador queda escondido debajo; además `tile_size()` de esa variante no descuenta el padding de la navbar ni el margen de `.slot`, y `.tilearea` (ítem flex de la navbar) crece al ancho de su contenido: la última columna se corta | en celular la navbar de esa variante es `static` (con `:has(.tilearea)`), sin padding lateral, `.slot` sin margen derecho, `.tilearea` con `flex:0 0 100%; min-width:0` y `#wrapTile` con `max-width:100%` |
| 9 | < 576 | Botón "To correct" de la navbar con `margin:-5px` (~30 px de alto); footer con `text-truncate` y `white-space:nowrap` inline: la versión del CMS queda fuera de la pantalla | botones de la navbar con `min-height:40px`; texto del footer con `white-space:normal !important` |
| 10 | 576–1199 | Tarjetas de "Puntaje por checkpoints" (`col-md-3 col-lg-2`, ~95 px de contenido en 1024 px): "25 puntos" en 2.5rem se parte y el `h1` absoluto de la tarjeta Subtotal se pisa con su título | `h1` de esas tarjetas a 1.6rem |

Firma con el dedo: jSignature ya maneja `touchstart/touchmove/touchend`; el lienzo ocupa el ancho de la tarjeta
(≥ 300 px en 412). Probado con `TouchEvent` sintéticos en `tests/firma-movil.html`.

Capturas (`tests/capturas/`): `firma-412x915-arriba.png`, `firma-412x915-completa.png` (8 pantallas apiladas, con
las 3 firmas), `vista-412x915-completa.png`, `vista-iframe-412x915.png`, `firma-412x915-modal.png`,
`firma-1024x768.png`, `vista-1024x768.png`, más las de 1366×900 de §6.

## 9. Notas de las pruebas (entorno, no producto)

- **Perfil de Edge con ruta larga ⇒ IndexedDB cae a memoria.** Con `--user-data-dir` dentro del scratchpad de la
  sesión (>150 caracteres) la ruta de LevelDB supera `MAX_PATH` de Windows, `indexedDB.open` falla y
  `local/nucleo/store.js` usa su respaldo en memoria **por marco**: la página de prueba siembra la corrida y el iframe
  de `firma.html` no la ve (`GET /api/runs/line/<id>` → 404). `tests/firma-correr.py` usa un directorio corto
  (`%TEMP%`) aunque `RCJ_TMP` sea largo. En un dispositivo real no pasa, pero si IndexedDB faltara (modo privado de
  algún navegador) la firma no vería las corridas del juez: está anotado para backend.
- **Sin frames en los iframes de Edge headless.** `requestAnimationFrame`, `animationend` y `transitionend` no llegan
  (la sonda de `firma-movil.html` lo mide en `extra.rAFenIframeEn1s`): SweetAlert2 7.33 deja el contenedor con
  `.swal2-hide`, ui-bootstrap no saca el modal del DOM y ngAnimate deja a medias los `ng-show`. Las pruebas llaman
  `$animate.enabled(false)` en el iframe (`T.sinAnimaciones`) y consideran cerrado un swal con `.swal2-hide` y un modal
  cuando `$uibModalStack.getTop()` es `undefined` (mismo criterio que `tests/juez-comun.js`). La página no cambia.
- `firma-correr.py` imprime en UTF-8 (`sys.stdout.reconfigure`): con la salida redirigida a archivo en cp1252 se caía
  al imprimir `Σ`.
