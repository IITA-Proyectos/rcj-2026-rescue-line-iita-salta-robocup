# Cambios respecto del CMS — área manual-ranking

Área dueña de `manual.html` (carga manual 2026, pasos input y check), `ranking.html` (ranking 2026),
`javascripts/manual/line_2026.js`, `javascripts/ranking/line_2026.js` (solo regla 3b y desvíos),
`local/ui/movil-manual-ranking.css` (excepción de propiedad para móvil) y `tests/manual-ranking-*`.

Fuente: rcj-rescue-cms `d805502`, bytes tomados con `git -C <cms> show d805502:<ruta>`.

## 1. `manual.html` — render de `views/manual/input/line_2026.pug` y `views/manual/check/line_2026.pug`

Rutas del CMS: `/line/input/:id` y `/line/check/:id` (`routes/line.js:96-114`, ambas pasan `{ id }`). En la app:
`manual.html?run=<id>` (paso 1, input) y `manual.html?run=<id>&check=true` (paso 2, check), según la tabla de
`RCJLocal.ruta` (ESPEC §4). Los dos pug usan el mismo controlador (`ddController` de `javascripts/manual/line_2026.js`),
así que se sirven desde una sola página.

| Qué | CMS | Local | Motivo |
|---|---|---|---|
| doctype | los dos pug no tienen `doctype` (modo quirks) | sin doctype (igual) | fidelidad visual |
| `<meta charset="utf-8">` | no está | primero en el head | `python http.server` no manda charset (fragmentos-head.md) |
| global `runId` | `var runId = "#{id}"` (pug:4-5) | `var runId = RCJLocal.param('run')` | no hay servidor que lo inyecte |
| `<title>` | `Rescue Line Input` / `Rescue Line Approval - Double Check` | el de input en el HTML; con `?check=true` un script inline pone el de check | una página para las dos variantes |
| `include common_component` | scripts y css comunes | idéntico según fragmentos-head.md §1.A/§1.B; `socket.io` reemplazado por `local/io-shim.js`; `ngAlertify` y `ui-select` comentados (06: clase C) | ESPEC §1 y §4 |
| scripts `local/*` | — | `local/config.js`, `local/io-shim.js`, `local/nucleo/*` antes; `local/http-backend.js` + `RCJLocal.instalarBackend('ddApp')` después del JS de página | backend local (ESPEC §4) |
| `lightbox2` js/css | enlazados (pug:11-13) | comentados (OMITIDO) | 06: clase C, no hay marcado `data-lightbox` |
| `fredrik.css` | solo input (pug:14) | solo input (lo inserta un script inline si no hay `?check=true`) | variante |
| `meta viewport` | solo check (pug:15) | **en las dos variantes** (desvío móvil, §4) | Chrome Android arma el paso input a 980 px sin ella |
| `fonts.css` | solo check (pug:17) | OMITIDO | ESPEC §1 (fuentes rotas en el origen) |
| bloque `style.` | distinto en cada pug (rosa / violeta, mismas clases) | los dos, **verbatim**, dentro de `<template id="rcj-estilo-input">` y `<template id="rcj-estilo-check">`; un script inline inserta el de la variante al final del head | las mismas clases con otros valores no pueden convivir |
| cuerpo | input pug:775-946 / check pug:452-573 | render a mano de cada uno dentro de `<template id="rcj-cuerpo-input">` / `<template id="rcj-cuerpo-check">`; un script inline inserta el de la variante antes de que arranque Angular (DOMContentLoaded) y borra las plantillas | una página para las dos variantes |
| rutas de estáticos | `/images/...` | `images/...` | regla 3a |

Los bloques `style.` se verifican contra `git show` con `python tests/manual-ranking-estilos.py <clon-del-cms>`
(sale 0 si son idénticos; con `--escribir` los regenera). No tienen `url(...)`, rutas absolutas ni interpolaciones.

## 2. `ranking.html` — render de `views/ranking/line_2026.pug` + `views/ranking/include/line_2026.pug`

Ruta CMS: `/line/:competitionid/:leagueId/ranking` (`routes/line.js:35-49`, pasa `{ competitionId, leagueId }`).
Local: `ranking.html?competition=<cid>&league=<league>`.

| Qué | CMS | Local | Motivo |
|---|---|---|---|
| layout | `extends includes/layout` (head.pug + navbar + footer + modales) | head según fragmentos-head.md §1.A-§1.E, navbar, footer §1.G | render a mano |
| globals | `competitionId`, `leagueId` (pug:8-10) | `RCJLocal.param('competition')`, `RCJLocal.param('league') \|\| 'Line'` | sin servidor |
| DataTables | `jquery.dataTables.min.js` + `angular-datatables.min.js` (el módulo `LineScore` inyecta `'datatables'`) | vendor real de `components/` (no stub) | 06: DI |
| navbar | con botón de login si no hay sesión | sin botón de login (comentado) | no hay login offline |
| `login_modal.pug` | incluido | OMITIDO | `POST /api/auth/login` no existe offline |
| `language_modal.pug` | EN / JA | EN / JA + tarjeta ES en una segunda fila | regla 3c (fragmento 1.F) |
| texto `</file>` | literal al final de `include/line_2026.pug:62` | OMITIDO (comentario) | el navegador lo descarta igual |
| selector de desempate | no existe | bloque `#rcj-desempate` antes de la tabla + interceptor `$http` | D9, ver abajo |
| estilos móviles | — | `<link href="local/ui/movil-manual-ranking.css">` | §4 |

### 2.1 D9: selector de desempate CMS / reglamento 6.1.8

El backend local (`local/nucleo/ranking.js`) expone la extensión `GET /api/ranking/<cid>/<league>?desempate=6.1.8`
(alias `reglamento`): ante igual `finalScore`, ordena primero por la **media de los puntajes normalizados por grupo
de las corridas usadas** (mayor primero) y recién después por el tiempo total como el CMS. Agrega
`result.desempate = '6.1.8'` y `ranking[i].desempate6118`.

`ranking.html` agrega (sin tocar `javascripts/ranking/line_2026.js`):
- un grupo de dos botones, "CMS (tiempo total)" y "Reglamento 6.1.8 (media de puntajes normalizados)", con una nota
  que explica el criterio activo. Al tocar uno la página recarga con o sin `&desempate=6.1.8` en la URL (así el
  criterio queda en el enlace y sobrevive al refresco);
- un interceptor `$http` registrado en el módulo `LineScore` que, solo si la URL de la página trae
  `desempate=6.1.8`, agrega `desempate=6.1.8` al `GET /api/ranking/...`. Sin el parámetro el pedido es byte a byte el
  del CMS.

El refresco en vivo (socket `runs/line/<cid>` → `getRanking()`) pasa por el mismo interceptor, así que conserva el
criterio elegido.

## 3. Cambios en los JS copiados del CMS

`javascripts/manual/line_2026.js` (diff contra `git show d805502:public/javascripts/manual/line_2026.js`):

| Línea | Antes | Después | Regla |
|---|---|---|---|
| 277 | `return "/images/tiles/tile-0.png";` | `return "images/tiles/tile-0.png";` | 3a |
| 304 | `return "/images/tiles/" + imgName;` | `return "images/tiles/" + imgName;` | 3a |
| 581 | `window.location = path` | `window.location = path ? RCJLocal.ruta(path) : path` | 3b (con `''` recarga la página como en el CMS) |
| 730 | `getAudioBuffer('/sounds/click.mp3', …` | `getAudioBuffer('sounds/click.mp3', …` | 3a |
| 733 | `'/sounds/info.mp3'` | `'sounds/info.mp3'` | 3a |
| 736 | `'/sounds/error.mp3'` | `'sounds/error.mp3'` | 3a |
| 739 | `'/sounds/timeup.mp3'` | `'sounds/timeup.mp3'` | 3a |

`javascripts/ranking/line_2026.js` (diff contra `git show d805502:public/javascripts/ranking/line_2026.js`):

| Línea | Antes | Después | Regla |
|---|---|---|---|
| 23 | `window.location = path` | `window.location = RCJLocal.ruta(path)` | 3b |
| 146 | `` `<iframe src="/line/view/${id}?iframe=true" …` `` | `` `<iframe src="${RCJLocal.ruta(`/line/view/${id}?iframe=true`)}" …` `` | 3b (detalle de corrida → `vista.html?run=<id>&iframe=true`) |

Nada más cambia: la cascada `changerAfterAll`, víctimas, LoPs, tiempo, `send()`, `approval()`, `cancel()` y todo el
cálculo del ranking quedan verbatim. Las URLs `/api/...` se dejan como están (las atiende el backend local).

## 4. Celular (Android 412x915, táctil) — desvíos

Requisito del usuario: cada dispositivo (celular, tablet, notebook) tiene que poder hacer todo por sí solo.

### 4.1 Markup (lo imprescindible)

- `manual.html`, paso input: se agrega `<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">`
  (la misma que ya trae el paso check, pug:15). Sin ella Chrome Android arma la página con un ancho de 980 px y la
  muestra achicada a 412 px: los botones del stepper de LoP quedaban de ~13 px reales. No cambia nada en notebook.
- `manual.html` y `ranking.html`: `<link rel="stylesheet" href="local/ui/movil-manual-ranking.css">` (en manual.html
  después del bloque `style.` insertado, para ganarle en la cascada).

### 4.2 `local/ui/movil-manual-ranking.css`

Todo dentro de `@media (max-width: 767.98px)` salvo la primera regla. Las reglas de la carga manual van con el
selector `body[ng-controller="ddController"]` y las del ranking con `body[ng-controller="LineScoreController"]`.

| Regla | Problema en 412 px | Arreglo |
|---|---|---|
| `#rank > .col-lg-12 { overflow-x: auto }` (todos los anchos) | la tabla del ranking crece con grupos/rondas y el nombre de equipo; su `.container-fluid` tiene `overflow:hidden` inline (pug:19): lo que no entraba quedaba **cortado e inalcanzable** | la tabla se desplaza dentro de su columna; si entra, no cambia nada |
| navbar fija → `position: sticky`, alto automático, envuelve | la navbar de 60 px no entra en una fila (equipo + STEP + ronda + cancha [+ puntaje]) y sus filas extra tapaban la primera tarjeta | queda arriba con su alto real; `body` sin `padding-top` |
| checkpoints en una sola columna | columnas de 190 px dentro de una caja de 560 px con scroll horizontal propio (scroll dentro del scroll) | lista vertical al ancho de la tarjeta, ítems de 60 px (122 px con LoP) |
| steppers de LoP 44x44 px, contador 64 px | el CMS les pone 26-32 px por `ng-style` inline (el de la meta es el más chico) | `!important` sobre el inline |
| botones de zona y papelera ≥ 48 px | papelera chica | `min-height/min-width` |
| bono de salida con `flex-wrap` | imagen + "Exit Bonus Achieved" en 1,4 rem no entran | envuelve, fuente 1,15 rem |
| cálculo final del paso 2 con `flex-wrap` | `raw × multiplicador = total` no entra | envuelve |
| barra inferior fija | "Complete Data Entry & Submit Score" (y Reject/Approve) se salían de los 412 px | botones flexibles, texto en dos renglones si hace falta, alto ≥ 52 px; `padding-bottom` del body a 96 px |
| ranking: breadcrumb, `.btn`, ícono de idioma ≥ 40-44 px; selector de desempate al ancho con texto envuelto; celdas de corrida con más padding | enlaces y botones chicos; el grupo de botones de desempate se salía | tamaños mínimos |

## 5. Pruebas y cuentas a mano

Runner: `python tests/manual-ranking-correr.py` (Edge headless, puerto 8806, `ThreadingHTTPServer` con el latido
`/__latido` de `tests/backend-correr.py`). Corre `tests/manual-ranking-manual.html`, `tests/manual-ranking-ranking.html`
y `tests/manual-ranking-movil.html`, y saca las capturas a `tests/capturas/manual-ranking-<nombre>-<ancho>x<alto>.png`
en 1366x900, 1024x768 y 412x915.

Nota del runner: con un `--user-data-dir` largo (el scratchpad de la sesión tiene > 150 caracteres) la ruta de LevelDB
supera MAX_PATH, IndexedDB tira `DOMException`, cada marco usa su store en memoria y la página no ve los datos
sembrados (la prueba se colgaba). Si `RCJ_TMP` es más largo que 100 caracteres, el runner usa el temporal del sistema.

### 5.1 Carga manual completa (`tests/manual-ranking-manual.html`)

Mapa `tests/backend-fixtures/fixture-mapa-oficial.json` (14 índices, `EvacuationAreaLoPIndex` 2, víctimas
`{live 2, dead 1}`). Baldosas puntuables: 1 speedbump, 3 intersection (count 1), 4 gap, 5 checkpoint, 6 obstacle
(count 1), 7 ramp (count 1), 8 seesaw (count 1), 10 checkpoint.

Escenario con clics reales sobre el DOM: tocar el inicio (showedUp + cascada `changerAfterAll` marca todo), tocar la
rampa (desmarca 7, 8 y 10), tocar la intersección (índice 3 < `lastModifiedIndex` 7: solo cambia ella), tocar el sube
y baja (marca 8 y la cascada vuelve a marcar 10). LoPs con los steppers `[1, 0, 1]`. Víctimas LIVE/GREEN, LIVE/GREEN,
DEAD/RED (con altas y bajas por doble clic y el tope del mapa). Bono de salida. Tiempo 04:37 con el teclado.

Cuenta a mano con `calculateLineScore` (CALC verbatim):

```
checkpoint 5 : tileCount 5-0 = 5, LoPs[0]=1 -> 5*(5-2*1) = 15
speedbump 1  : 10          gap 4 : 10          obstacle 6 : 20*1 = 20       seesaw 8 : 20*1 = 20
intersection 3 y ramp 7    : no puntuadas -> 0
checkpoint 10: tileCount 10-5 = 5, LoPs[1]=0 -> 5*5 = 25
subtotal                   = 15+10+10+20+20+25 = 100
exitBonus: max(60 - 5*(1+0+1), 0) = 50 ; tramo final 14-10-1 = 3 baldosas, LoPs[2]=1 -> 3*(5-2) = 9
showedUp                   : +5
raw_score                  = 100 + 50 + 9 + 5 = 164
multiplicador: LoPs[EvacuationAreaLoPIndex=2] = 1 -> max(1400-50*1, 1250) = 1350
  LIVE/GREEN x1350 (liveCount 1), LIVE/GREEN x1350 (liveCount 2),
  DEAD/RED: no es DEAD/GREEN y liveCount (2) == map.victims.live (2) -> x1350
  multiplier = 1350^3 / 1000^3 = 2.460375
score = Math.round(164 * 2.460375) = Math.round(403.5015) = 404
```

La prueba verifica que el `PUT` responde 200 `Saved run`, que la corrida queda con `status 4`, que `score`,
`raw_score` y `multiplier` guardados y los de la respuesta son `===` a `RCJLocal.calculateLineScore(corrida + mapa)`
y a la cuenta a mano, que vuelve a `?return=` por `RCJLocal.ruta`, y después el paso check (solo lectura,
`404` = `164 × 2.460375`, aprobación → `status 6`).

### 5.2 Ranking (`tests/manual-ranking-ranking.html`)

Mapa `tests/backend-fixtures/ejemplo-01.json`: 4 índices, checkpoint en el índice 1, `EvacuationAreaLoPIndex` 1.
Puntajes de corrida (CALC):

```
80  = checkpoint 1*(5-0) + bono 60 + tramo final (4-1-1)=2 baldosas * 5 + 5          LoPs [0,0]
71  = checkpoint 5 + bono (60-5*1)=55 + tramo final 2*(5-2*1)=6 + 5                   LoPs [0,1]
10  = checkpoint 5 + 5 (sin bono)                                                   LoPs [0,4]
5   = solo showedUp
80  con LIVE/RED o DEAD/GREEN: esas víctimas no multiplican (continue) -> 80
112 = 80 * 1400/1000 (LIVE/GREEN, LoPs[1]=0)
```

3 equipos × 3 corridas (grupo de normalización = número de ronda), `num = 2`:

| Equipo | G1 (Ronda 1) | G2 (Ronda 2) | G3 (Ronda 3) |
|---|---|---|---|
| A | 80 (04:30) | 5 (07:00) | 71 (03:50) |
| B | 71 (03:40) | 80 (04:15) | 5 (02:00) |
| C | 10 (06:10) | 112 (03:20) | 71 (04:05) |

Algoritmo (`routes/api/ranking.js`, port en `local/nucleo/ranking.js`): máximo por grupo, `normalizedScore = score / max`;
por equipo ordena con `sortRunsNormalized` (o `sortRuns` en SUM: puntaje desc, empate por tiempo asc), toma las
`num` primeras (`used`), suma tiempos de las usadas; `finalScore` = media de normalizados (MEAN) o suma (SUM); orden
final con `sortFinalScore` (puntaje desc, empate por `gameSum.time` asc).

**Fase 1 — MEAN_OF_NORMALIZED_BEST_N_GAMES.** Máximos: G1 80, G2 112, G3 71.

```
A: 80/80=1, 5/112=0.0446, 71/71=1          -> usadas 1 y 1       -> finalScore 1        tiempo 04:30+03:50 = 08:20
B: 71/80=0.8875, 80/112=0.7143, 5/71=0.0704 -> usadas 0.8875 y 0.7143 -> (0+0.8875+0.714285…)/2 = 0.80089…  tiempo 03:40+04:15 = 07:55
C: 10/80=0.125, 112/112=1, 71/71=1         -> usadas 1 y 1       -> finalScore 1        tiempo 03:20+04:05 = 07:25
orden: C y A empatan en 1 -> tiempo 07:25 < 08:20 -> 1º C, 2º A, 3º B (0.80)
```

**Fase 2 — SUM_OF_BEST_N_GAMES** (`runGroups` = nombres de ronda).

```
A: 80 + 71 = 151 (08:20)    B: 80 + 71 = 151 (04:15+03:40 = 07:55)    C: 112 + 71 = 183 (07:25)
CMS  : 1º C 183; empate A/B en 151 -> tiempo -> 2º B (07:55), 3º A (08:20)
6.1.8: medias normalizadas de las usadas: A (80/80 + 71/71)/2 = 1 ; B (71/80 + 80/112)/2 = 0.80089…
       -> 2º A, 3º B (el tiempo ya no decide)
```

**Fase 3 — refresco en vivo.** Con la competencia en MEAN y la página abierta, la prueba hace un `PUT` desde otro
contexto: B G3 pasa de 5 a 80 (checkpoint + bono, LoPs [0,0]). El io-shim emite `runs/line/<cid>`, la página vuelve a
pedir el ranking una sola vez y re-renderiza sin recargar.

```
máximo G3 = 80: A 71/80 = 0.8875, B 80/80 = 1, C 71/80 = 0.8875 (G1 y G2 no cambian)
A: 1 + 0.8875  -> 0.94375 (08:20)   B: 1 + 0.8875 -> 0.94375 (G3 02:00 + G1 03:40 = 05:40)   C: 1 + 0.8875 -> 0.94375 (07:25)
triple empate -> por tiempo: 1º B 05:40, 2º C 07:25, 3º A 08:20
```

Además: `openRunDetails` abre `vista.html?run=<id>&iframe=true` en un SweetAlert (regla 3b), celdas grises para
corridas no usadas, colores de víctima por zona y `{{ }}` sin compilar = 0.

### 5.3 Celular / tablet / notebook (`tests/manual-ranking-movil.html`)

Cada página en un iframe de 412x915, 1024x768 y 1366x900: sin scroll horizontal de la página ni elementos cortados
fuera de un contenedor desplazable; en celular, controles tocables ≥ 40x40 px; primera tarjeta debajo de la navbar;
al final de la página el contenido no queda debajo de la barra fija de envío. Cada control se "toca" llevándolo a la
vista y verificando con `elementFromPoint` que en su centro no hay otra cosa encima. En 412x915: carga manual completa
(cascada, LoPs incluido el stepper de la meta, 3 víctimas, bono, teclado del tiempo, envío → status 4 y
`score === calculateLineScore`), aprobación (status 6) y detalle de corrida desde el ranking.

### 5.4 Resultados

(se completa al final de la corrida de pruebas)
