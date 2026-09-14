# Cambios del área backend respecto del CMS

Fuente: `robocup-junior/rcj-rescue-cms`, commit `d805502`. Todas las citas `archivo:línea` son de ese commit.
Archivos del área: `local/config.js`, `local/io-shim.js`, `local/http-backend.js`, `local/nucleo/**`, `tests/backend-*`.

## 1. Qué se copió verbatim y cómo verificarlo

| Archivo local | Origen verbatim | Único cambio |
|---|---|---|
| `local/nucleo/pathfinder-servidor.js` | `helper/pathFinder.js` completo | Envoltorio IIFE con `module`/`exports`/`require` locales; export a `RCJLocal.PFs`. Así no pisa los globales del `pathFinder.js` cliente (`traverse`, `exitDir`, ...). |
| `local/nucleo/init-run.js` | `helper/initRunData.js` completo | Líneas 7-10 (consulta Mongo del mapa) reemplazadas por `let map = __mapaPoblado;`. `RCJLocal.initLine(run, map, rule, scored)` recibe el mapa ya poblado y devuelve la misma Promise que el original. |
| `local/nucleo/score-2026.js` | `helper/scoreCalculatorRules/2026.js` completo, `helper/scoreCalculator.js:12-19`, `leagues.json` | `rules` estático `{'2026': ...}` en lugar de `fs.readdirSync` + `require` dinámico (`scoreCalculator.js:1-10`). |
| `local/nucleo/copy-properties.js` | `routes/api/lineMaps.js:214-239` | Ninguno (es idéntico a `lineRuns.js:561-586` salvo sangría; el generador lo comprueba). |
| `local/nucleo/ranking.js` | `routes/api/ranking.js:607-666` (`sortRuns`, `sortRunsNormalized`, `sortFinalScore`, `sum`) | Ninguno. El handler (`ranking.js:22-228`) está portado a mano, ver §4. |

Las regiones van entre `// ===== INICIO VERBATIM <ruta> =====` y `// ===== FIN VERBATIM <ruta> =====`.
`python tests/backend-verificar-verbatim.py <clon-del-cms>` las compara byte a byte con `git show d805502:<ruta>`
(resultado al cierre: 7 regiones, 0 diferencias).

**Sin tope de profundidad en PFs** (desvío permitido 11 no aplicado). Un recorrido con lazo lanza `RangeError`, que
`guardarMapa` captura igual que el `try/catch` de `models/lineMap.js:142-146`: el mapa se guarda con `index[]` enormes.
En el navegador tarda ~60 ms y no cuelga (probado en `tests/backend-t2t3-mapas.html`). El largo exacto de `index[]` depende
de la profundidad de pila del motor (Node y Edge difieren).

## 2. Emulación de Express y mongoose (`local/nucleo/api.js`)

### 2.1 Router
- Orden efectivo de Express por montaje: rutas `public`, luego `private`, luego `admin` (`app.js:179-198`). `next()` por
  `ObjectId.isValid` se emula con guardas `si`. `RCJLocal.esIdValido` replica bson 4.x: 24 hex **o cualquier string de 12
  bytes** (p.ej. `competitions`).
- Ruta desconocida bajo `/api` → `404 {"message":"404 Not found"}` (`app.js:287-290`). Una excepción síncrona dentro de un
  handler de Express (p.ej. `tile.items` undefined en el POST de mapa) también da ese 404.
- Rutas sin distinción de mayúsculas y con barra final opcional (Express por defecto).
- Usuario local único `superDuperAdmin`: `ensureLoginApi`/`ensureAdminApi` (`config/pass.js:75-100`) y `authViewRun`
  (`helper/authLevels.js:31-62`) siempre permiten; las ramas 0/2 no se alcanzan. `authLevel` de competencias = 15.
- Cada pedido corre en **una** transacción IndexedDB sobre todas las colecciones (`readonly` para GET, `readwrite` para el
  resto y para el GET de corrida). Las emisiones de socket y la actualización de la caché van después del commit.

### 2.2 Casteo, defaults y validación de mongoose 6.11
`models/lineRun.js:19-90`, `models/lineMap.js:27-124`, `models/competition.js:83-405` se describen como esquemas en `api.js`.
- Casteo con las reglas de `mongoose/lib/cast/{number,boolean,string,objectid}.js`: `'5'`→5, `''`→`null` en Number,
  `'true'/'1'/'yes'`→true, setters `''→0/false/-1` de lineMap. Error de casteo → `ValidationError` con el formato
  `Cast to Number failed for value "5a" (type string) at path "time.minutes"`.
- Validadores en el orden de mongoose: `required` primero, luego `min`/`max`/`enum`/`validate` en orden de declaración, y el
  entero de `mongoose-integer` al final. Un error por ruta. Mensajes:
  `Path \`time.seconds\` (60) is more than maximum allowed value (59).`, ``` `FOO` is not a valid enum value for path `victimType`. ```.
  **Aproximado**: el texto exacto del plugin `mongoose-integer` (no está en el repo): se usa `Error, expected \`x\` to be an integer.`
- Modo *strict*: las claves desconocidas de un subdocumento se descartan. Los subdocumentos reciben `_id` al final.
- **Momento del casteo**: en mongoose ocurre en cada asignación; acá el `copyProperties` verbatim trabaja sobre objetos
  planos y el casteo se aplica **inmediatamente después** (antes de `calculateScore`), restaurando el valor previo si una
  asignación falla (como el `$set` fallido de mongoose). `rescueOrder` y `nl.*` se castean en el momento de reemplazarlos
  (`lineRuns.js:541-553`). Resultado observable idéntico en los casos probados.
- **`LoPs: {type:[Number], min:0}`** (`lineRun.js:46`): en mongoose 6 `SchemaArray` no tiene método `min`, así que esa opción
  no crea validador. **No se valida `LoPs ≥ 0`**, aunque 08 §5.5 paso 10 lo liste: validarlo sería validar algo que el CMS
  acepta (08 §5.8).
- Errores que en mongoose **lanzan** en vez de invalidar (asignar un elemento no numérico dentro de `LoPs`, o un elemento
  no-objeto en un DocumentArray): en el CMS dejan el pedido sin respuesta; acá responden 400 con el error de casteo.
- `copyProperties` sobre objetos planos: la lista blanca es `hasOwnProperty`. Única diferencia conocida: en mongoose la clave
  raíz `id` (virtual) es legal; acá da `Illegal key: id`. Ninguna página la envía.
- `createdAt`/`updatedAt` (mongoose-timestamp) como strings ISO. `__v` se incrementa cuando el PUT trae `tiles`, `LoPs` o
  `rescueOrder` (el `$set` de un array incrementa la versión); solo se ve en el payload del socket.
- **Orden de claves** de las respuestas: `_id` primero y el resto en orden de esquema. No se emula el orden exacto de BSON ni
  el esqueleto de `$__buildDoc` (`time`, `sign`, `nl` primero en documentos no-lean). Ningún consumidor depende de él.
- Orden natural de Mongo (listas sin `sort`) = orden de `createdAt` y luego `_id` (los ids locales son tipo ObjectId:
  timestamp + aleatorio de sesión + contador).
- `decimal.js` (`lineRuns.js:137`, `ranking.js:73`) se reemplaza por `RCJLocal._Decimal` (BigInt, 20 dígitos
  significativos, ROUND_HALF_UP, `toString` con los umbrales de exponente de decimal.js). En E12 `score` sale como **string**
  igual que `Decimal.toJSON`.

### 2.3 Casos en que el CMS no responde nunca (excepción asíncrona o `if (dbRun)` sin else)
No se emula el cuelgue. Se responde:

| Caso (origen) | Respuesta local |
|---|---|
| GET/PUT de corrida inexistente (`lineRuns.js:319`, `:514`) | 404 `{"message":"404 Not found"}` |
| Corrida sin equipo o liga ausente en la competencia (`lineRuns.js:320`, `scoreCalculator.js:13-16`) | 500 `{msg:'Error interno del backend local', err}` |
| `calculateScore` lanza fuera de su try (regla no cargada) | 500 |
| maxScore de mapa inexistente (`lineMaps.js:189`) | 400 `{msg:'Could not get map', err:'Map not found'}` |
| PUT de mapa inexistente (`lineMaps.js:281`) | 400 `{msg:'Could not get map', err:'Map not found'}` |
| tileCount de tileset inexistente (`lineMaps.js:492`) | 400 `{msg:'Could not get tile set', ...}` |
| POST de corrida con mapa inexistente (`lineRun.js:95-98`) | 400 `{msg:'Error saving run in db', err:'No map with that id!'}` |
| POST de equipo con competencia inexistente (`teams.js:306-311`) | 400 `{msg:'Error saving team', err:'No competition with that id!'}` |
| DELETE de corrida/equipo con primer id inexistente (`lineRuns.js:786-798`, `teams.js:246-262`) | 404 |
| PUT de competencia/equipo inexistente (`competitions.js:224`, `teams.js:184`) | 404 |
| `/competitions/leagues/:league` con coincidencia parcial sin exacta (`competitions.js:63-81`) | 500 |
| PUT `/runs/line/bulk` con algún id inexistente (`lineRuns.js:392-440`) | 200 `Partial success: n/m` |
| PUT de corrida con `tiles` disperso, `started=false` y score 0 (`lineRuns.js:617-624`, quirk 10) | se saltean los huecos (08 §5.5 paso 9) |

## 3. Endpoints (E1..E16) — diferencias puntuales

- **E10 GET corrida** (`lineRuns.js:298-384`): re-inicializa con `initLine` si `!started` y persiste `tiles`, `LoPs`, `nl` y
  `rescueOrder = []` (C1). Como en el original la respuesta se arma antes de que termine `save()`
  (`lineRuns.js:336-347`): si la validación o el pre-save fallan (p.ej. mapa no `finished`) se responde 200 con la
  inicialización **sin persistirla** (se avisa por `console.warn`). `updatedAt` de la respuesta es el anterior.
  `normalized`: la búsqueda `{normalizationGroup: undefined}` se interpreta con `==` (null/undefined iguales).
- **E11 PUT corrida**: pipeline de 08 §5.5 en el orden de `lineRuns.js:482-657`, en una transacción. El mapa poblado para
  `calculateScore` lleva `tiles.tileType = {_id}` (el `select: 'indexCount, victims'` de `lineRuns.js:501` no existe en
  TileType). Payload de `runs/<id>`: la corrida con `competition` y `team` completos y `map = {_id, name, finished}` (el
  pre-save repuebla `map` con `'name finished'`, `lineRun.js:95`; inferido de mongoose, no ejecutado). Las fotos locales del
  equipo nunca salen en respuestas ni en sockets.
- **E13 POST corrida**: validaciones del pre-save (`lineRun.js:92-280`) en el orden competition, round, team, field, map
  (en el CMS corren en paralelo y gana el primer callback con error).
- **E5/E6/E7/E9 mapas**: `guardarMapa` = validación → populate de `tiles.tileType` desde los tilesets → `PFs.findPath` con
  errores solo logueados → nombre único por competencia o "used in started runs" (`models/lineMap.js:133-182`). No hay
  colección `tileTypes`: se derivan de `tileSets` (poblados con el JSON vivo). E9 síncrono sale de una caché en memoria de
  mapas (se precarga al instalar el backend y se refresca por BroadcastChannel cuando otra pestaña guarda mapas).
- **E8** (`map-image-png`, `map-image-pdf`, `scoresheet`, `image/:mapid`, `export`, `runs/line/scoresheet2`): si el área
  salidas no registró un generador con `RCJLocal.api.registrarRuta`, responden **501** `{msg:'Salida no disponible ...'}`
  (el editor muestra su Toast "Error generating output"). `map-image-*` sin `tiles` mantiene el 400 `Invalid map data`
  de `lineMaps.js:654-658`. Las rutas registradas tienen prioridad sobre las internas y corren fuera de la transacción.
- **E14 fotos** (`document.js:1511-1569`, rama "file not found" en `:1556-1569`): el CMS responde `public/images/NoImage.png` con 200 si no hay archivo; acá
  **404** (ESPEC E14). Las fotos se guardan como dataURL en el equipo (`teamPhoto`/`robotPhoto`), campo local agregado al
  esquema de equipo, con `PUT /api/teams/:competition/:team` (acepta `''` para borrar) o `RCJLocal.api.guardarFotoEquipo`.
  Nota: `<img ng-src="/api/...">` no pasa por `$http`; la página del juez tiene que resolver la imagen con
  `RCJLocal.api.fotoEquipo(teamId, nombre)` o con `api.request`.
- **E16 sockets**: se emite `LChanged` como el CMS (`lineRuns.js:646-650`); la lista escucha `StatusChanged`
  (`line_competition.js:57`) y sigue sin refrescar por socket (fiel al original, D4).
- **Competencias** `POST /api/competitions` (`competitions.js:745-753`): el CMS crea una entrada por cada liga de
  `leagues.json` con su última regla; acá solo `{league:'Line', rule:'2026'}` (ESPEC §5, D8). Nombre repetido →
  400 con el texto del índice único `E11000 ...`. `DELETE` borra en cascada rondas, equipos, canchas, mapas y corridas
  (`models/competition.js:204-218`). Los directorios de documentos/cabinet no existen offline.
- **Equipos** `POST /api/teams`: no se guardan `email`, `members` ni `document` (son `select:false` y no aplican
  offline); no se crea el registro de Technical Challenge (`teams.js:333-339`).
- **Ranking** (`ranking.js:22-228`): modos `SUM_OF_BEST_N_GAMES` y `MEAN_OF_NORMALIZED_BEST_N_GAMES`. Los modos con documento
  o Technical Challenge responden 400 (D8; en el CMS sin documentos crashean en `ranking.js:211,214`). Competencia
  inexistente → 400 (en el CMS, TypeError sin respuesta).
  **Extensión nueva** `?desempate=6.1.8` (alias `?desempate=reglamento`): ante empate de `finalScore` ordena por la media
  de field scores normalizados de las rondas usadas (reglamento 2026 §6.1.8; normaliza por `normalizationGroup` aunque el
  modo sea SUM) y recién después por tiempo (`sortFinalScore`). Agrega `result.desempate = '6.1.8'` y
  `ranking[i].desempate6118`. Sin el parámetro la respuesta es la del CMS.
- Endpoints no emulados (no los usa ninguna página de línea 2026 ni la administración local): signage
  `find/team_status`, `pre_recorded`, documentos/revisiones, registración, `adminTeams` completo con email/token,
  `tilesets` POST/PUT/DELETE, `/competitions/:c/line/runs` (en el CMS llama a una función inexistente).

## 4. APIs nuevas (no existen en el CMS)
- `RCJLocal.ingestMap(export, {competition, league, nombre?, renombrarSiExiste?})`: POST + PUT según 08 §5.3; exige que la
  competencia exista; tolera `tiles` array y `tileType` id (D1). `renombrarSiExiste` agrega ` (2)`, ` (3)`, ...
- `RCJLocal.exportMap(mapId)`: reproduce la carga del editor (`L26:134-170`) y `$scope.export` (`L26:993-1019`); si el
  `pathFinder` cliente global está cargado, recalcula `index`/`next` como `updateTileIndex` (`L26:435-461`).
- `RCJLocal.semillas({tilesets?})`: tilesets de `data/tilesets.json` (validando que no sea un HTML de error) y competencia
  "Práctica IITA 2026" + "Ronda 1" + "Cancha 1" + "IITA Salta". Idempotente. Además, el primer pedido a la API siembra
  los tilesets automáticamente si la base no tiene ninguno.
- `RCJLocal.backup.exportar()` → `{formato:'rcj-line-offline/respaldo', version:1, app, fecha, colecciones}`;
  `RCJLocal.backup.importar(obj, {modo:'reemplazar'|'fusionar'})`.
- `RCJLocal.api.request/requestSync/registrarRuta/listo/precargar/fotoEquipo/guardarFotoEquipo`, `RCJLocal.emitirSocket`,
  `RCJLocal.store` (IndexedDB con respaldo en memoria si IndexedDB no está disponible; `navigator.storage.persist()` se
  pide al abrir).

## 5. `local/http-backend.js`
- Decora `$httpBackend` (firma de AngularJS 1.8.2). Pedidos a `/api/*` del mismo origen → `RCJLocal.api.request`; el resto
  → `$delegate`. Respeta `responseType` (`arraybuffer`, `blob`, `json`, texto), `headers()`, `statusText`, `xhrStatus`,
  timeout numérico (`-1`/`timeout`) y timeout por promesa (`-1`/`abort`). No dispara `eventHandlers`/`uploadEventHandlers`
  (ninguna página de línea los usa).
- Parchea `jQuery.ajax`: `async:false` a `/api/maps/line/tileCount/...` sale de la caché síncrona con `responseJSON`; otros
  `$.ajax` a `/api` se atienden asíncronos con un Deferred de jQuery; todo lo demás va al `$.ajax` original.
- Uso: después de angular, jQuery y el JS de la página: `RCJLocal.instalarBackend('NombreModulo')` antes del arranque.

## 6. `local/io-shim.js`
- `io()`/`io.connect()` devuelven un socket con `on/once/off/emit/connect/disconnect`; `emit('subscribe'|'unsubscribe', sala)`
  como `server.js:74-83`; `connect` se dispara asíncrono. Transporte: `BroadcastChannel('rcj-line-offline')` + entrega en la
  misma ventana (sin duplicados). Alcance: pestañas y marcos del mismo navegador y origen (multi-dispositivo fuera de v1).
- Debe cargarse **después** de `components/socket.io-client` si una página lo incluye.

## 7. `local/config.js`
- `RCJLocal.base` = carpeta que contiene `local/config.js`; `ruta()` devuelve rutas absolutas desde esa base (funciona
  servida en `/` o en un subdirectorio). Rutas agregadas a la tabla de ESPEC §4, por existir en el CMS:
  `/admin/<cid>/<league>/games/print` → `planillas.html?competition&league` y `/admin/<cid>/<league>/mapEditor` sin id →
  `editor.html?competition&league`. Una ruta que ya es `*.html` o de otro origen se devuelve igual.
- Flags en `localStorage['rcjLocalFlags']` con los defaults de ESPEC §2.

## 8. Pruebas (`tests/backend-*`)
`python tests/backend-correr.py` (servidor en 8802 + Edge headless `--virtual-time-budget --dump-dom`).
El servidor de pruebas es `http.server.ThreadingHTTPServer` con un único agregado, `GET /__latido?ms=N`: las páginas
mantienen ese pedido pendiente mientras corren, porque con `--virtual-time-budget` Edge avanza el tiempo virtual durante las
operaciones de IndexedDB y volcaba el DOM antes de terminar. Con `python -m http.server` común las páginas funcionan igual
(el latido da 404 y se detiene); solo cambia el `--dump-dom` automatizado.

| Página | Cubre |
|---|---|
| `backend-t1-vectores.html` | T1 39/39 con `===` + despachador |
| `backend-t2t3-mapas.html` | T2 {80,220,2.744} {210,576,2.744} {125,343,2.744} vía E7; T3 0 diferencias (ingestMap y PFs directo); D1; export; lazo |
| `backend-t6-reglas.html` | T6: C1, started, status, tiempo, enums, KIT, disperso, LoPs, 202, firma, mapa no finished, E12, E13, E16 |
| `backend-admin.html` | config/ruta, semillas, competencias/rondas/canchas/equipos, E5/E6/E7/E9, ranking + 6.1.8, E14, E8, respaldo, cascadas |
| `backend-angular.html` | `$http` real (GET/PUT/400/arraybuffer/blob/timeout/abort/estáticos) y `$.ajax` síncrono y asíncrono |
| `backend-io.html` (+ `backend-io-hijo.html`) | dos iframes reciben `data`/`changed`/`LChanged` tras un PUT; unsubscribe |
| `backend-verificar-verbatim.py` | regiones verbatim contra `git show d805502` |
