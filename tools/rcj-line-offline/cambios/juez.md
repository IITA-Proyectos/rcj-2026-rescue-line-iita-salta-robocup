# Cambios del área juez respecto del CMS (`rcj-rescue-cms` d805502)

Página: `juez.html` (puerto de pruebas 8804). Origen: `views/judge/line_2026.pug` +
`public/javascripts/judge/line_2026.js` + `public/templates/line_judge_modal.html` + `routes/line.js:93`
(`/line/judge/:id` → `res.render('judge/line_2026', {id})`).

Abreviaturas: **JPUG** = `views/judge/line_2026.pug`, **J26** = `public/javascripts/judge/line_2026.js` (números del blob
original salvo que diga "local").

## 1. Archivos del área

| Archivo | Tipo | Qué es |
|---|---|---|
| `juez.html` | nuevo (render) | Render a mano de JPUG. El `<body>` es la salida compacta de pug (sin espacios entre tags). Verificable con `python tests/juez-pug-comparar.py --cms <clon del CMS>` → "IGUAL" (501 tokens, único cambio aplicado: C1). |
| `javascripts/judge/line_2026.js` | copia del CMS | Copia de assets (regla 3a) + los cambios de la §2. Todo lo demás byte a byte igual: `git show d805502:public/javascripts/judge/line_2026.js \| diff - javascripts/judge/line_2026.js`. |
| `templates/line_judge_modal.html` | copia del CMS | Sin cambios del área juez (solo la regla 3a que aplicó assets). |
| `local/timer-persistente.js` | nuevo | Desvío D5 `persistirTimer` (§5.1). |
| `local/ui/movil-juez.css` | nuevo | CSS para celular < 768 px (§4). |
| `tests/juez-*` | nuevo | Pruebas (§7). |

## 2. Cambios en `javascripts/judge/line_2026.js`

Cada línea nueva lleva el comentario `// [rcj-line-offline]`.

| J26 (original) → local | Regla | Antes | Después | Motivo |
|---|---|---|---|---|
| `:177` → local `178-183` (`upload_run`) | D4 | `if(response.statusCode == 202){ setTimeout($scope.upload_run, 100, data); return; }` (queda igual) | se agrega debajo: `if (RCJLocal.flags.corregirBugsVisuales && response.status == 202) { $scope.sync--; $timeout(function () { upload_run(data); }, 100); return; }` | `$http` expone `.status`, no `.statusCode`, y `$scope.upload_run` no existe (02 §3.1): con 202 el CMS toma la respuesta como éxito y deja `score` en `undefined` (la navbar muestra " points"). Con el flag reintenta. |
| `:202` → local `208` | 3b | `if (document.referrer.indexOf('sign') != -1) {` | `if (document.referrer.indexOf('sign') != -1 \|\| rcjVolviDeFirma(runId)) {` | la firma local es `firma.html` (no contiene "sign"). Ver §3 A1 y §6. La condición original se conserva. |
| `:423` → local `429` (`calc_victim_multipliers`) | D4 | `if (v.victimType == "LIVE") liveCount ++;` | `if (v.victimType == "LIVE" && (!RCJLocal.flags.corregirBugsVisuales \|\| v.zoneType == "GREEN")) liveCount ++;` | con el flag la etiqueta x del cliente cuenta solo las vivas efectivas, igual que el servidor (`scoreCalculatorRules/2026.js:59-69`). Sin flag: original. |
| `:771` → local `778-783` (`saveEverything`) | D4 | `if(response.statusCode == 202){ setTimeout($scope.saveEverything, 100); return; }` (queda igual) | se agrega: `if (flag && response.status == 202) { $scope.sync--; $timeout($scope.saveEverything, 100); return; }` | mismo bug del 202. |
| `:809` → local `822-827` (`confirm`) | D4 | `if(response.statusCode == 202){ ... }` (queda igual) | se agrega: `if (flag && response.status == 202) { $scope.sync--; $timeout($scope.confirm, 100); return; }` | mismo bug del 202 en Go NEXT. |
| `:838` → local `856` (`$scope.go`) | 3b | `window.location = path` | `window.location = RCJLocal.ruta(path)` | todas las navegaciones del juez pasan por aquí: `go('/line/sign/<id>?return=…')` → `firma.html?run=<id>&return=…`; `go('/home/access_denied')` (401 en `:182`, `:323`) → `index.html`; Back (`go(getParam('return'))` o `go('/line/<cid>/<league>')`) → `corridas.html?competition=…&league=Line`. |
| `:673`, `:1072`, `:1268-1277` | 3a | `/templates/…`, `/sounds/…` | relativas | las aplicó el área assets (cambios/assets.md). |

## 3. `juez.html`: diferencias con el render del pug

- **Sin `<!doctype>`**, igual que JPUG (`html(ng-app="ddApp")`): la página corre en modo quirks como en el CMS (verificado: `document.compatMode === 'BackCompat'`).
- **`<head>`**: `<meta charset="utf-8">` primero (python http.server no manda charset); `local/config.js`, `io-shim.js` y `local/nucleo/*` antes que todo; globales de JPUG:4-6 en un `<script>` inline (`runId = RCJLocal.param('run')`, `movie = ""`); después `includes/common_component` según `herramientas/fragmentos-head.md`. `local/http-backend.js` + `RCJLocal.instalarBackend('ddApp')` van después de `judge/line_2026.js` y antes de `translate_config.js`.
- **Omitidos (comentados en su lugar, clase C de 06)**: `ngAlertify`, `angular-ui-select` (js/css), `socket.io-client` (lo reemplaza `io-shim.js`), `stg.css` (solo `ENVIRONMENT == "STG"`), `deflate.js`, `jquery.qrcode`, `makeQR.js`, `lightbox2` (js/css), `css-toggle-switch`. El juez no usa ninguno.
- **Sonidos**: `sounds/click.mp3`, `info.mp3`, `error.mp3`, `timeup.mp3` (regla 3a en J26). No hay selector de idioma: JPUG no incluye el layout. El idioma sale de `translate_config.js` (ES por defecto, D2).
- **C1 fila "Rule"** (desvío permitido 9, flag `corregirBugsVisuales`): JPUG:83 `td #{rule}` se renderiza vacío porque `routes/line.js` solo pasa `id`. Render local: `<td><span ng-if="rcjFlags.corregirBugsVisuales">{{rcjRegla(competition, league)}}</span></td>`. Sin flag queda vacía (como el CMS); con flag muestra la regla de la liga (`2026`).
- **Script inline de adaptaciones** (después de `local/timer-persistente.js`):
  - **A1** `window.rcjVolviDeFirma(runId)`: contrato con firma (§6).
  - **A2** `$rootScope.rcjFlags` y `$rootScope.rcjRegla(competition, league)` para C1.
  - **A3 fotos del pre-chequeo** (E14): `<img ng-src="/api/document/inspection/files/{{team._id}}/teamPhoto">` no pasa por `$http`. Un decorador de `ngSrc` (solo para `ng-src` que empiezan con `/api/`) resuelve la foto con `RCJLocal.api.fotoEquipo`. Sin foto muestra `images/NoImage.png`, que es lo que responde el CMS (`routes/api/document.js:1556-1569`). No se hace ningún pedido de red a `/api/document`.
  - **A4** `audioResume` (§5.2). **A5** estilo FA4 (§5.4).
- **`<link href="local/ui/movil-juez.css">`** después de `fredrik.css` (§4).

## 4. Celular (Android 412x915, táctil)

`local/ui/movil-juez.css`, solo `@media (max-width: 767.98px)`; en tablet y notebook no aplica nada. No se tocó el markup.

| Problema medido a 412x915 | Ajuste |
|---|---|
| La navbar fija pasa a 2 filas (~83 px) y `navbar_premium.css` da `body{padding-top:70px}`: el título del pre-chequeo y los botones Start/Reset quedaban tapados | `body{padding-top:96px}` |
| `tile_size()` pone a `#card_area` `height` inline = alto de ventana con `overflow:scroll`: en una columna es un scroll anidado dentro del scroll de la página | `#card_area{height:auto!important;overflow:visible!important}` |
| Botones de piso (" 0", " 1") y de rotación de unos 30 px de ancho | `.tilearea .btn-group > .btn{min-width:44px;min-height:38px}` |

A 1024x768 la navbar mide 50 px (debajo del padding de 70 px): no hacía falta nada. La grilla del mapa oficial (7x4) entra a 412 px con baldosas de ~52 px. Go NEXT y los inputs de tiempo quedan alcanzables al final de la página.

## 5. Desvíos por flag (ESPEC D4/D5)

Flags en `localStorage['rcjLocalFlags']`, leídos con `RCJLocal.flags` al cargar la página.

| Flag | Default | Qué hace en el juez |
|---|---|---|
| `persistirTimer` | `true` | §5.1 |
| `audioResume` | `true` | §5.2 |
| `fotosOpcionales` | `true` | §5.3 |
| `corregirBugsVisuales` | `false` | x1.4 del cliente, 202 (`upload_run`, `saveEverything`, `confirm`), ícono FA4 del modal, fila Rule (§2, §3 C1, §5.4) |

### 5.1 `persistirTimer` (`local/timer-persistente.js`)

- En el CMS el cronómetro vive en memoria: recargar con el reloj corriendo lo detiene y el tiempo vuelve al último guardado.
- Con el flag, mientras el reloj corre se guarda `localStorage['rcjJuezTimer:<runId>'] = {runId, startedTime:true, startUnixTime, prev, time, guardadoEn}`. `prev` es el `prevTime` del controlador, tomado al arrancar.
- Al recargar, cuando `loadNewRun` ya definió `$scope.duration`, reanuda con el mismo handler del botón (`toggleTime()`, que arranca `tick` y manda `{status:2}` como siempre). Después corre `startUnixTime` hacia atrás lo necesario para que `tick` dé el tiempo que llevaba.
- Con el reloj detenido se borra la clave: Stop, Reset, exit bonus y fin de tiempo ya guardaron el tiempo en el backend, así que la recarga se comporta igual que el original.
- No se reanuda un estado de más de 15 min (una corrida dura como mucho 8 min): evita un "Time Up!" que pise una corrida terminada.
- No toca J26. Al recargar, el pre-chequeo vuelve a aparecer (como en el CMS) mientras el reloj sigue corriendo.

### 5.2 `audioResume`

- El `AudioContext` de J26:1239 (local 1257) se crea antes de cualquier gesto y en Chrome/Android queda `suspended`.
- Con el flag, un listener en captura (`touchstart`, `touchend`, `pointerdown`, `mousedown`, `click`, `keydown`) llama `context.resume()` mientras siga suspendido, y se quita cuando queda `running`.

### 5.3 `fotosOpcionales`

- Sin foto del equipo o del robot (lo normal offline), la tarjeta de esa foto nace confirmada (verde). Se puede destildar tocándola.
- Con `false` se comporta como el CMS: las 4 tarjetas en rojo, y hay que tocarlas todas para habilitar "I confirmed!!".
- Con foto cargada (dataURL en el equipo) se muestra la foto y la tarjeta arranca en rojo, como el CMS.

### 5.4 `corregirBugsVisuales` (default original)

- **x1.4**: §2 `:423`. Ejemplo probado: LIVE/GREEN, LIVE/RED, DEAD/RED con 2 vivas en el mapa.
  - Cliente original: `[1.4, 1, 1.4]`.
  - Con flag: `[1.4, 1, 1]`, cuyo producto es 1.4 = multiplicador del backend.
- **202**: §2 `:177`, `:771`, `:809`.
- **FA4**: el modal usa `fa fa-play-circle-o` (FA4, invisible en FA5; 02 §2.4). Con el flag se inyecta `<style data-rcj-line-offline="fa4">` que le da el glifo FA5 `\f144` (regular).
- **Rule**: §3 C1.
- `j*4` no existe en el juez (JPUG ya usa `j*3`; el `j*4` es de `view/common`, área firma).

## 6. Vuelta desde la firma: marca `rcjVolviDeFirma` (contrato con el área firma)

- En el CMS el pre-chequeo se saltea si `document.referrer` contiene `sign` (`/line/sign/<id>`). Localmente el referrer es `firma.html?...` y no lo contiene.
- **Escribe** la firma: el botón "To correct" (`$scope.go` de `sign/line_2026.js` con ruta `/line/judge/…`) hace `sessionStorage.setItem('rcjVolviDeFirma', runId)` antes de navegar (cambios/firma.md §3).
- **Lee** el juez: `rcjVolviDeFirma(runId)`, en `juez.html` A1.
  1. Si hay marca, la **consume** (`removeItem`).
  2. Si coincide con la corrida, la copia a `history.state` de esa entrada y devuelve `true`. Si es de otra corrida, se descarta.
  3. Sin marca, devuelve `history.state.rcjVolviDeFirma === runId`.
- La condición original (`referrer` con `sign`) se conserva y sigue funcionando (probado con `tests/juez-desde-sign.html`).
- **Diferencia con la sugerencia de cambios/firma.md §3**: allá se propone que una recarga posterior vuelva a mostrar el pre-chequeo. Acá se replica el CMS, donde el referrer se conserva al recargar. Por eso la marca pasa a `history.state`:
  - una recarga sigue salteando el pre-chequeo;
  - una navegación nueva a `juez.html?run=…` lo muestra.
  - El contrato de escritura no cambia.

## 7. Pruebas

```
python tests/juez-correr.py [--perfiles DIR] [--sin-capturas] [pagina.html ...]
python tests/juez-pug-comparar.py --cms <clon del CMS>
```

- `juez-correr.py` levanta el servidor en 8804 (http.server + `GET /__latido` + `Cache-Control: no-store`), corre cada página con Edge headless `--dump-dom` y lee `<pre id="resultado">`. Después toma capturas de `juez.html` a 1024x768, 1366x900 y 412x915 en `tests/capturas/` (pre-chequeo, puntuación y modal).
- `juez-escenario.html`: corrida completa con clics reales sobre el mapa oficial. Pasos: pre-chequeo, `time==0` bloquea, Start, inicio, todas las baldosas con puntaje de los 2 pisos, LoPs (con aviso ≥ 3), víctimas LIVE x2 GREEN + DEAD RED, exit bonus, aviso "Oops!" y Go NEXT → `firma.html?run=<id>&return=`. En cada paso verifica navbar == respuesta del backend == esperado a mano. Al final, navbar == backend == corrida guardada == `RCJLocal.calculateLineScore` == 535.
- `juez-recarga.html`: re-inicialización al recargar antes de `started` (E10), cronómetro persistente, flag apagado (original), estado viejo descartado, marca de firma, referrer con `sign`.
- `juez-flags.html`: D4/D5 con defaults y cambiados, 202 simulado con `RCJLocal.api.registrarRuta`, modal "Direction scored" (cerrar manda `tiles[]` de 14).
- `juez-movil.html`: el juez en un iframe de 412x915. Mide que nada quede bajo la navbar, que no haya desborde horizontal, botones ≥ 36x30 px, `#card_area` sin scroll anidado, Go NEXT alcanzable y una corrida corta.

Notas de las pruebas:
- `juez-flags.html` puntúa una baldosa antes de cargar víctimas. Regla del CMS (08 §5.5 paso 9): `started` pasa a `true` solo con `score > 0` o una baldosa puntuada. Con víctimas solas (score 0), recargar re-inicializa la corrida (E10) y las borra. Es comportamiento original, no un bug.
- Las pruebas están pensadas para Edge headless, que renderiza frames. En una pestaña oculta de un navegador normal no corren `requestAnimationFrame` ni `animationend`. Por eso SweetAlert2 deja el popup con `.swal2-hide` (las pruebas lo toleran), y el `closed` del modal de ui-bootstrap no se resuelve y no llega el PUT del modal. Es un artefacto de la pestaña oculta, no del juez.
- **Arnés sin animaciones**: con `--virtual-time-budget`, Edge headless no termina las animaciones de ngAnimate. Los elementos quedan con `ng-hide-animate ng-hide-remove`, la vista de puntuación queda oculta y el `closed` del modal no se resuelve. Por eso `juez-comun.js` hace `$animate.enabled(false)` en el juez del iframe. El cambio es solo del arnés: los cambios de clase quedan inmediatos, como en un navegador real un frame después, y `juez.html` sigue con animaciones.
- `juez-correr.py` corre las páginas **de a una** (`--paralelo 1`). Con varios Edge headless simultáneos ningún pedido llegaba al servidor y todas las páginas fallaban en 2,5 s. Las capturas no usan `--screenshot`: en ese modo Edge headless no da IndexedDB (DOMException) y el juez aparecía sin datos. Se toman con el protocolo DevTools (`--remote-debugging-port`, cliente WebSocket mínimo en Python) en tiempo real, con un perfil nuevo por vista y el tamaño emulado exacto (`mobile` + táctil debajo de 768 px). Antes de la primera captura se hace un precalentamiento: una página del mismo origen y 2 s de espera. Sin él, al navegar apenas arranca un perfil nuevo, `RCJLocal.store` no abría IndexedDB, caía a memoria y el juez del iframe no veía los datos sembrados. `juez-captura.html` siembra sus propios datos, porque reutilizar o copiar el perfil de la prueba colgaba el lanzamiento o dejaba la IndexedDB inaccesible. En la vista de puntuación juega con clics: Start, inicio, lomo, intersección, 1 LoP y 2 vivas en verde.
- `juez-comun.js` reconoce la página vieja del iframe con la marca `__rcjViejo`: `iframe.contentWindow` es el mismo WindowProxy antes y después de navegar. El cuerpo de los pedidos llega serializado desde `$http` y se parsea para las verificaciones.

**Capturas de pantalla: PENDIENTES (fallan)**. Estado al 2026-09-13:

- El `<pre id="resultado">` de `juez-captura.html` volcó `[RCJLocal.store] IndexedDB no disponible, se usa memoria` en la página y en el iframe. El juez pidió `GET /api/runs/line/<id>` → 404 y se dibujó sin datos. Así terminaron todas las capturas intentadas: `--screenshot` de Edge headless, y DevTools con emulación, con precalentamiento y con una carga previa sin emular.
- Una sonda por DevTools en el mismo tipo de navegador abrió `rcj-line-offline` v1 con las 8 colecciones sin error. Además, esa misma página de captura, cargada en una sonda aparte, quedó `LISTO` (con y sin emulación). No se aisló qué diferencia hay con `capturar()`.
- Las PNG generadas mostraban el juez sin datos y se borraron para no dejar evidencia engañosa.
- El layout en celular queda verificado con medidas en `juez-movil.html` (16/16 en headless, iframe de 412x915). En el panel del navegador se vieron pre-chequeo y puntuación a 412x915 con datos (§4).

**Mapa sin baldosa recorrida dos veces**: ni el mapa oficial ni `ejemplo-01`/`sintetico-03` tienen baldosas con `index.length > 1`. El modal se prueba abriéndolo con `open(1,0,0)` (lo que hace `doScoring` cuando `total > 1`).

### Cuenta a mano del escenario (`scoreCalculatorRules/2026.js`)

Mapa oficial: `indexCount` 14, checkpoints en los índices 5 y 10, `EvacuationAreaLoPIndex` 2. LoPs finales `[1,0,0]`.

| Concepto | Cálculo | Puntos |
|---|---|---|
| Elementos | lomo idx1 10 + intersección idx3 10 + gap idx4 10 + obstáculo idx6 20 + rampa idx7 10 + balancín idx8 20 | 80 |
| Checkpoint idx5 | 5 baldosas × (5 − 2·LoPs[0]=1 → 3) | 15 |
| Checkpoint idx10 | 5 baldosas × (5 − 2·0) | 25 |
| Exit bonus | 60 − 5·(LoPs totales = 1) | 55 |
| Último tramo | (14 − 10 − 1) = 3 baldosas × 5 | 15 |
| Inicio (showedUp) | | 5 |
| **raw_score** | | **195** |
| Multiplicador | LIVE/GREEN × 2 y DEAD/RED con LoPs[2] = 0: 1.4³ | 2.744 |
| **score** | round(195 × 2.744 = 535.08) | **535** |
