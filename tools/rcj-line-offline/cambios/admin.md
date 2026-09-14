# Cambios del área admin respecto del CMS

Fuente: `robocup-junior/rcj-rescue-cms`, commit `d805502`. Las citas `archivo:línea` son de ese commit, salvo
las que dicen "local". Los bytes del CMS se tomaron con `git show d805502:<ruta>`. Las rutas relativas (regla 3a)
de los JS copiados ya las había aplicado el área assets.

La app es para **entrenar simulando lo oficial**, en un solo dispositivo (celular Android, tablet o notebook) y sin
sincronizar. Por eso las páginas de administración juntan en un lugar lo que en el CMS estaba repartido en varias
páginas de servidor, y omiten lo que depende de usuarios, documentos o cartelería.

## 0. Archivos del área

| Archivo | Qué es |
|---|---|
| `index.html` + `local/ui/inicio.js` | **Nuevo.** Inicio en español: competencia activa, accesos grandes, corridas pendientes y corrida rápida. |
| `corridas.html` | Port de `views/line_competition.pug` (lista de corridas de la liga). |
| `javascripts/line_competition.js` | CMS verbatim + regla 3b (1 línea). |
| `admin-corridas.html` + `local/ui/admin-corridas.js` | Port de `views/admin/games.pug` + tarjeta local de rondas, pistas, equipos, ranking y grupos. |
| `javascripts/admin/games.js` | CMS verbatim + regla 3b (3 lugares). |
| `mapas.html` + `local/ui/mapas.js` | Port de `views/admin/maps.pug` (lista admin de mapas, `routes/admin.js:495-504`) + agregados locales. |
| `javascripts/admin/maps.js` | CMS verbatim + regla 3b (3 lugares) + 1 desvío (gancho de refresco). |
| `configuracion.html` + `local/ui/configuracion.js` | **Nuevo.** Flags, idioma, respaldo, borrado, almacenamiento, versión y licencia. |
| `local/ui/comun.js` | `RCJLocalUI`: competencia activa, URLs locales, descargas, salidas binarias, alta de corridas y directiva de archivos. |
| `local/ui/estilos.css` | Estilos de las páginas nuevas y de los agregados (misma paleta y radios que `modern_*.css`). |
| `local/ui/movil-admin.css` | Ajustes para celular (412 px). Solo actúan por debajo de 576 px. |
| `tests/admin-*` | Pruebas en Edge headless (sección 6). |

## 1. Reglas comunes a las 5 páginas

- **Doctype**: `includes/layout.pug:2` tiene `doctype html`, así que las páginas llevan `<!DOCTYPE html>` (modo estándar).
- `<meta charset="utf-8">` va primero: `python -m http.server` no manda charset (hallazgo de assets).
- `<head>`: sale de `herramientas/fragmentos-head.md` (§1.A-1.E, §2.10), en el orden del pug. Las libs de clase C
  (ngAlertify, ui-select) y `socket.io-client` quedan comentadas en su lugar (las reemplaza `local/io-shim.js`).
  `stylesheets/fonts.css` y `stg.css` quedan omitidos.
- Scripts locales en el orden de ESPEC §4: `local/config.js`, `io-shim`, `nucleo/*`, `local/ui/comun.js`, globales
  inline, JS del CMS, `local/http-backend.js` y `RCJLocal.instalarBackend('<Módulo>')`.
- **Navbar** (`includes/navbar.pug`): el menú de usuario y el login (`navbar.pug:13-37`, `login_modal.pug`) se
  omiten porque offline no hay usuarios. En su lugar va un engranaje que lleva a `configuracion.html`. La marca lleva a
  `index.html`. Las páginas nuevas agregan la pastilla `offline`.
- **Selector de idioma** (`language_modal.pug`): se agrega la tarjeta ES en una segunda fila (regla 3c, fragmento §1.F).
- **Competencia**: cada página toma `?competition=`. Si falta, usa la competencia activa que se eligió en el Inicio
  (`localStorage['rcjLocalCompetenciaActiva']`). Así los accesos funcionan aunque se abran sin parámetros.
- Link a `local/ui/movil-admin.css` después de `local/ui/estilos.css` (sección 5).

## 2. corridas.html (`views/line_competition.pug`)

| Lugar | Antes (CMS) | Después (local) | Motivo |
|---|---|---|---|
| globales (`line_competition.pug:8-11`) | `competitionId = "#{id}"`, `isJudge = "#{judge}"`, `league = "#{league}"` | `competitionId = RCJLocal.param('competition') \|\| competencia activa`; `isJudge = "1"`; `league = RCJLocal.param('league') \|\| 'Line'` | Sin pug. Offline siempre se es juez. |
| `javascripts/line_competition.js:166` | `window.location = path` | `window.location = RCJLocal.ruta(path)` | Regla 3b. |
| `block page_css` | `style.` | igual, inline | Verbatim. |
| rutas `/images/loader2.gif` | absolutas | relativas | Regla 3a. |

Todo lo demás es el render del pug: la tarjeta de ranking, la de Technical Challenge (queda oculta porque el modo
de documentos está fuera de v1, D8), los filtros y la tabla con `go`/`go_judge`. Los botones Juez, Manual Input y
Ver pasan por `RCJLocal.ruta` y llevan a `juez.html`, `manual.html` y `vista.html`.

## 3. admin-corridas.html (`views/admin/games.pug`)

### 3.1 Port del pug

| Lugar | Antes | Después | Motivo |
|---|---|---|---|
| globales (`games.pug:10-12`) | `competitionId = "#{competitionId}"`, `leagueId = "#{leagueId}"` | `RCJLocal.param('competition') \|\| activa`, `RCJLocal.param('league') \|\| 'Line'` | Sin pug. |
| scripts (`games.pug:13-17`) | datetimepicker, `games.js`, ng-file-upload, exceljs | iguales, relativos | Se conserva el export XLSX. |
| `append css` (`games.pug:19-…`) | datetimepicker.css + estilos inline | iguales | Verbatim. |
| hero (`games.pug:708-709`) | botón monitor `/signage/games/...` | **omitido** (comentario en su lugar) | Cartelería de sede, sin equivalente offline. |
| formulario (`games.pug:763-767`) | botón «bulk» `/admin/.../games/bulk` | **omitido** (comentario) | `games_bulk.pug` sube un CSV al servidor; no se portó. |
| breadcrumb | `#{leagueId} Games` | `{{league.league}} Games` | Interpolación de pug → Angular. |
| `<head>` | — | `<script src="local/render/registrar.js">` | E8 de salidas: `GET /api/runs/line/scoresheet2`. |

### 3.2 `javascripts/admin/games.js`

| Línea local | Antes (CMS) | Después | Motivo |
|---|---|---|---|
| 345-346 | `window.open('/api/runs/line/scoresheet2?run=...', "_blank")` | `RCJLocalUI.abrirApi('GET', mismaUrl, undefined, {tipo:'application/pdf'})` | Regla 3b: sin servidor, la URL `/api/` se pide al backend local y el PDF se abre como Blob. La ventana se abre antes del pedido asíncrono para que no la bloquee el navegador. |
| 387-389 | `return=` + `pathname`; `window.location = path` | `return=` + `pathname + search`; `window.location = RCJLocalUI.ruta(path)` | Regla 3b. En la app local la competencia viaja en la query, así que el retorno la necesita. |
| 487-488 | `window.open('/api/runs/line/scoresheet2?competition=...', "_blank")` | `RCJLocalUI.salidaApi(..., {nombreDescarga:'scoresheets.pdf'})` | Regla 3b. Se descarga porque la ventana ya no puede abrirse después del modal. |

### 3.3 Agregado local: tarjeta «Rondas, pistas, equipos y ranking» (`#catalogosLocales`)

En el CMS esto vive en páginas separadas: `views/admin/round.pug` + `admin/round.js`, `field.pug` + `field.js`,
`team.pug` + `team.js` y el modo de ranking en `competition_settings.pug`. Offline se junta debajo de la tabla de
games.pug, con controlador propio (`CatalogosLocalController`, local/ui/admin-corridas.js) sobre el módulo `RunAdmin`.
Usa las mismas rutas `/api/*` que esas páginas:

- Rondas: `POST /api/rounds`, `DELETE /api/rounds/:id`.
- Pistas: `POST /api/fields`, `DELETE /api/fields/:id`.
- Equipos: `POST /api/teams`, `PUT /api/teams/:cid/:id` (nombre y código), `DELETE /api/teams/:id` (borra también sus
  corridas, como el CMS). Fotos del equipo y del robot para el pre-chequeo del juez: se guardan como dataURL (lado
  máximo 800 px) con `RCJLocal.api.guardarFotoEquipo`.
- Ranking de la competencia: `PUT /api/competitions/:id` con `leagues[].mode/num/disclose`. Solo ofrece los dos
  modos de D9.
- Grupos de normalización: tabla de grupos existentes y «asignar a las corridas tildadas» con
  `PUT /api/runs/line/:id {normalizationGroup}`.

Después de cada cambio refresca las listas del formulario «Add run» de games.js (mismas fuentes que
`games.js:17-27`). Si cambian corridas, emite `changed` en la sala `runs/line/<cid>` del io() local y games.js recarga
la tabla con su propio listener.

Omitido: documentos, e-mails y miembros de equipos; alta masiva por CSV; países; usuarios y permisos.

## 4. mapas.html (`views/admin/maps.pug`)

### 4.1 Port del pug y de `javascripts/admin/maps.js`

| Lugar | Antes | Después | Motivo |
|---|---|---|---|
| globales (`maps.pug:8-10`) | `competitionId = "#{id}"`, `leagueId = "#{leagueId}"` | `param('competition') \|\| activa`, `param('league') \|\| 'Line'` | Sin pug. |
| `<head>` | — | `javascripts/pathFinder.js` (CMS verbatim) y `local/render/registrar.js` | `RCJLocal.exportMap` recalcula index/next como el editor si el pathFinder cliente está cargado. E8 para la impresión masiva. |
| botón «Crear» (`maps.pug`) | `ng-href="/admin/{{competitionId}}/{{league.league}}/mapEditor"` | `ng-click="go('/admin/' + competitionId + '/' + league.league + '/mapEditor')"` | Regla 3b: pasa por `RCJLocal.ruta` → `editor.html?competition&league`. |
| breadcrumb | `#{leagueId} Maps` | `{{league.league}} Maps` | Interpolación de pug. |
| `maps.js:107` (local) | — | `$scope.updateMapList = updateMapList;` | **Desvío**: gancho para que `local/ui/mapas.js` refresque la lista después de importar o duplicar. No cambia el comportamiento del CMS. |
| `maps.js:144-154` | `<a href="/api/maps/line/image/<id>" download>` por mapa | `RCJLocalUI.exportarMapas(url, ids, settings, cid, liga)` | Regla 3b: sin servidor. Pide `GET /api/maps/line/image/:id`; si no hay generador (501), `POST map-image-png` con el cuerpo del editor. |
| `maps.js:160` | `window.open('/api/maps/line/export?...')` | `RCJLocalUI.exportarMapas(...)` | Regla 3b. Pide el export masivo; si no hay generador (501), genera un PDF por mapa con `map-image-pdf` o `scoresheet`. |
| `maps.js:168` | `window.location = path` | `window.location = RCJLocal.ruta(path)` | Regla 3b. |

### 4.2 Agregados locales (marcados `AGREGADO` en el HTML; lógica en `local/ui/mapas.js`)

- **Importar JSON** (botón en el hero, `input type=file multiple`): lee cada archivo y acepta un mapa o un array de
  mapas. Llama a `RCJLocal.ingestMap(json, {competition, league, renombrarSiExiste:true})`. Acepta el export oficial y
  la variante con `tiles` array y `tileType` id (la tolerancia está en `ingestMap`, D1). Muestra una tarjeta con el
  resultado por archivo (nombre final, terminado o error).
- Por mapa, en cada tarjeta:
  - **Terminado / sin terminar**: `PUT /api/maps/line/:id` con el mismo cuerpo que el Save del editor
    (`admin/mapEditor/line_2026.js:933-947`) y `finished` cambiado.
  - **Crear corrida** (modal): equipo, ronda y pista (automáticas si se dejan vacías) y grupo; «Crear» o «Crear y
    puntuar» (abre `juez.html`). Usa `RCJLocalUI.crearCorrida`, sección 4.3.
  - **Exportar JSON**: `RCJLocal.exportMap(id)` → `JSON.stringify` sin espacios → `<nombre>.json`, igual que
    `$scope.export` del editor (`line_2026.js:993-1019`).
  - **Duplicar**: `exportMap` + `ingestMap` con nombre «(copia)».
  - **Planilla** (PDF): `POST /api/maps/line/scoresheet` con el cuerpo de `generateOutput` del editor. Si no hay
    generador, avisa y ofrece el link a `planillas.html`.
  - **Estadísticas**: `estadisticas.html?competition=<cid>&map=<id>`.
- Debajo del nombre de cada mapa: estado, dimensiones, cantidad de índices y cantidad de corridas. La lista del CMS
  (`GET /api/competitions/:c/:l/maps`) no trae esos datos, así que se leen (solo lectura) de `RCJLocal.store`.

### 4.3 `RCJLocalUI.crearCorrida` (Inicio y Mapas)

Payload igual al de `admin/games.js:91-104` (`POST /api/runs/line`). Si falta algún dato, lo resuelve así:
- **Ronda**: la primera en la que el equipo todavía no tiene corrida (el CMS exige que round+team sea único). Si no
  hay, crea «Práctica N».
- **Pista**: la primera. Si no hay, crea «Cancha 1».
- **Grupo de normalización**: el nombre de la ronda.

## 5. Páginas nuevas

### 5.1 index.html (Inicio)

Tiene la estructura de `includes/modern_layout.pug`: navbar premium, hero con breadcrumb y tarjetas `modern-card`.
- Al cargar llama a `RCJLocal.semillas()`, que es idempotente.
- Selector de competencia activa y alta de competencia (`POST /api/competitions`).
- 8 accesos grandes pensados para tablet: Puntuar, Mapas, Corridas, Administrar corridas, Ranking, Estadísticas,
  Planillas y Configuración. Todos llevan `?competition=`.
- Lista de corridas pendientes (status < 4) con Puntuar (juez), Firmar (status 3) y Ver.
- **Corrida rápida de práctica**: mapa terminado + equipo → `RCJLocalUI.crearCorrida` → `juez.html?run=<id>&return=index`.
- Se refresca cuando otra pestaña cambia corridas (io() local, sala `runs/line`).

### 5.2 configuracion.html

- Las 6 flags de ESPEC §2 (D4, D5, D6), cada una con su explicación, default y decisión. Se aplican con
  `RCJLocal.setFlag`; «Valores por defecto» las restablece.
- Idioma (es, en, ja) con `$translate.use` + recarga.
- **Respaldo completo**:
  - Exportar: `RCJLocal.backup.exportar()` → `rcj-line-offline-respaldo_AAAA-MM-DD_HHMM.json`.
  - Importar: valida `formato`, muestra los conteos por colección y elige modo reemplazar o fusionar (con confirmación).
- **Borrar todos los datos**: dos confirmaciones (la segunda exige escribir BORRAR) y `store.clear` de cada colección.
  Al volver al Inicio se re-siembra.
- Almacenamiento: `navigator.storage.persisted()` (con botón para pedir `persist()`), `estimate()` y conteo de
  documentos por colección. Avisa si la base quedó en memoria.
- Versión (`RCJLocal.version`), créditos y licencia MIT del CMS (link a `LICENSE-rcj-rescue-cms.txt`).

## 5bis. Celular (`local/ui/movil-admin.css`)

Requisito: cada dispositivo (celular Android 412×915, tablet o notebook) tiene que poder hacer todo por sí solo. El
archivo se enlaza desde las 5 páginas del área después de `local/ui/estilos.css`. Solo actúa con `max-width: 576px`,
así que a 1024 y 1366 px las páginas quedan como el CMS. **No cambia el markup.**

Problemas medidos con `tests/admin-captura.html` a 412 px antes del CSS, y cómo se resolvieron:

| Página | Problema | Ajuste |
|---|---|---|
| mapas | La fila del CMS (selección + nombre + 7 botones) no entra: el nombre se parte letra por letra (`word-break: break-all` de modern_list.css), los botones pisan los detalles y el de borrar queda recortado por `.modern-list`. | La tarjeta pasa a dos filas (`flex-wrap`): nombre arriba y acciones abajo, alineadas a la derecha, con botones de 44 px. |
| corridas | En la tarjeta móvil de `line_competition.pug` el botón «Manual Input» queda recortado por `.btn-table-group` (`overflow:hidden`). | El grupo envuelve en varias filas (`overflow: visible`) y los botones miden 44 px de alto. |
| todas | Íconos del navbar de 37 px de alto y breadcrumb de 16 px. | 44 px y 40 px. |
| admin-corridas | Casillas de 20 px y botón «Action» de 31 px. | 36 px y 44 px; ítems del menú más altos. |
| index | Link «Ver todas» de 24 px. | 40 px. |

## 6. Pruebas

`python tests/admin-correr.py` (puerto 8807; `RCJ_TMP` = carpeta para perfiles de Edge). Ver el resultado en la
salida del agente.
- `tests/admin-flujo.html`: flujo completo desde una base vacía, dentro de un iframe con las páginas reales.
- `tests/admin-export.html` (`--pruebas admin-export.html`): `ingestMap` → `exportMap` contra el sha256 del export oficial.
- `tests/admin-captura.html`: capturas 1366×900, 1024×768 y 412×915 en `tests/capturas/admin-*.png`. En cada una mide
  scroll horizontal, controles inalcanzables o recortados y controles chicos.
- `tests/admin-comun.js`: ayudas de las pruebas (latido, iframes, SweetAlert, archivos con DataTransfer).

Último resultado (2026-09-13):

| Prueba | Resultado |
|---|---|
| `admin-flujo.html` | 70 verificaciones: 67 OK y 3 FALLA, 0 errores de consola. Las 3 fallas son el sha256 del export (`exportar`, `tiles array`, `después de restaurar`), que viene de `RCJLocal.exportMap` del área backend: cada baldosa sale con otro orden de claves (`x,y,z,tileType…` en vez de `rot,tileType,items,index,next,x,y,z`) y con campos de más (9278 bytes contra 6902). |
| `admin-export.html` | 2/2 FALLA por la misma causa. |
| Capturas (15) | Todas generadas. Sin scroll horizontal y 0 controles inalcanzables en las 5 páginas y los 3 tamaños. A 412 px quedan 2 casillas de 36 px en admin-corridas y el link inline «Ver la licencia». |

Agregados del servidor de pruebas, que no usa la app: `GET /__latido` (igual que backend) y `POST /__resultado`
(el resultado de las capturas, porque `--screenshot` no permite `--dump-dom`).
