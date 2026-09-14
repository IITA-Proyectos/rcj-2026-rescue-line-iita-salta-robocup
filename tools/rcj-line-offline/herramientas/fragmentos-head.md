# Fragmentos de `<head>` por página (rcj-line-offline)

Dueño: área **assets**. Los demás agentes **copian de acá** el bloque de su página. Si hace falta cambiar un
fragmento, se pide al área assets (o se reporta en `bugs_en_otros_modulos`), para que todas las páginas sigan
el mismo orden.

## 0. Reglas

1. **Rutas relativas sin barra inicial.** Todas las páginas viven en la raíz de la app (ESPEC §1), así que
   `components/...`, `stylesheets/...`, `javascripts/...` resuelven igual en todas.
2. **Mismo orden que el pug original.** El orden sale de `views/includes/common_component.pug` más las líneas
   propias de cada pug. El render real se comprobó contra el HTML vivo del editor
   (`live/service_editor_line_2026`):
   1. scripts comunes;
   2. `append scripts` de la página;
   3. css comunes;
   4. `block page_css`;
   5. las 4 hojas de `modern_layout`;
   6. `append css` de la página;
   7. `translate_config.js`, meta, íconos, manifest, `fonts.css` y script inline de `head.pug`.
3. **Lo que no se enlaza queda como comentario `<!-- OMITIDO: ... -->` en su lugar**, así se ve el orden original.
   Los motivos vienen de `analysis/06-dependencias.md` §3.1:
   - C: se carga sin uso;
   - X: no existe en el sitio vivo;
   - stub: lo reemplaza `local/io-shim.js`.

   Los archivos omitidos **sí están vendorizados** en `components/`. Si el agente de una página prefiere
   fidelidad total en la secuencia de carga, puede descomentarlos sin romper nada, salvo `themes/fa/theme.min.js`,
   que no existe.
4. **`<meta charset="utf-8">` va primero en todas las páginas.** Es un agregado necesario, no un desvío de lógica:
   - Express enviaba `Content-Type: text/html; charset=utf-8`.
   - `python -m http.server` envía `text/html` **sin charset**, y los textos en español se verían rotos.
   - `head.pug` tiene `meta(name="charset")`, que **no** declara la codificación.
5. **Scripts `local/*` (ESPEC §4).** Van en este orden:

   | Paso | Qué | Dónde y por qué |
   |---|---|---|
   | a | `local/config.js`, `local/io-shim.js`, `local/nucleo/*` | Justo **antes** del `<script>` inline de globales. No dependen de jQuery ni de Angular. En los pugs standalone (juez, firma, vista, manual, planillas) quedan antes de los scripts comunes; en los pugs con layout, después. |
   | b | `<script>` inline de globales | Lee `RCJLocal.param(...)`. Reemplaza lo que inyectaba pug. |
   | c | JS de la página y sus extras | En el orden del pug. |
   | d | `local/http-backend.js` y `<script>RCJLocal.instalarBackend('<módulo>')</script>` | **Después** del JS de la página y de sus extras: necesita el módulo Angular y jQuery. Siempre antes del `DOMContentLoaded`, que es cuando Angular hace el bootstrap. |
   | e | `javascripts/translate_config.js` | En su posición original. Hace `app.config(...)` sobre la global `app`. |

   Notas:
   - El orden de `local/nucleo/*` es el de ESPEC §3; el dueño (backend) puede fijar otro y se actualiza **solo acá**.
   - **Para backend:** el decorador de `$httpBackend` tiene que dejar pasar todo lo que **no** sea `/api/`. angular-translate pide `lang/es.json` y los modales piden `templates/*.html` (el del editor con `?gs`) por `$http`.
6. **Fuentes Outfit/Inter:** no se enlaza `stylesheets/fonts.css` (ESPEC §1). El `@import` que tenía
   `stylesheets/common/modern_layout.css` ya quedó neutralizado por el importador.
7. **Manifest:** el `/manifest.json` del CMS no se copia. Cuando el área docs publique `manifest.webmanifest`,
   se descomenta su `<link>`. Mientras no exista, dejarlo comentado (si no, da 404).

Nombres de módulo Angular (para `instalarBackend`):

| Página | Módulo |
|---|---|
| editor | `LineEditor` |
| juez, firma, vista, manual | `ddApp` |
| ranking | `LineScore` |
| planillas, admin-corridas | `RunAdmin` |
| corridas | `LineCompetition` |
| mapas | `MapAdmin` |

---

## 1. Bloques reutilizables

### 1.A Scripts comunes (`common_component.pug:1-19`)

```html
<script src="components/jquery/dist/jquery.min.js"></script>
<script src="components/popper.js/dist/umd/popper.min.js"></script>
<script src="components/bootstrap/dist/js/bootstrap.min.js"></script>
<script src="components/angular/angular.min.js"></script>
<script src="components/angular-animate/angular-animate.min.js"></script>
<!-- OMITIDO (06: C, sin uso): <script src="components/alertifyjs/dist/js/ngAlertify.js"></script> -->
<script src="components/sweetalert2/dist/sweetalert2.all.min.js"></script>
<!-- OMITIDO (stub: lo reemplaza local/io-shim.js): <script src="components/socket.io-client/dist/socket.io.min.js"></script> -->
<script src="components/angular-bootstrap/dist/ui-bootstrap-tpls.js"></script>
<script src="components/angular-translate/angular-translate.min.js"></script>
<script src="components/angular-translate-loader-static-files/angular-translate-loader-static-files.min.js"></script>
<script src="components/angular-translate-storage-local/angular-translate-storage-local.min.js"></script>
<script src="components/angular-translate-storage-cookie/angular-translate-storage-cookie.min.js"></script>
<script src="components/angular-translate-handler-log/angular-translate-handler-log.min.js"></script>
<script src="components/angular-cookies/angular-cookies.min.js"></script>
<script src="components/angular-touch/angular-touch.min.js"></script>
<script src="components/angular-sanitize/angular-sanitize.min.js"></script>
<!-- OMITIDO (06: C, ningún módulo usa ui.select): <script src="components/angular-ui-select/dist/select.min.js"></script> -->
```

### 1.B CSS comunes (`common_component.pug:21-30`)

```html
<link rel="stylesheet" href="components/bootstrap/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="stylesheets/style.css">
<link rel="stylesheet" href="stylesheets/navbar_premium.css">
<link href="components/font-awesome-5/css/all.min.css" rel="stylesheet">
<link rel="stylesheet" href="components/angular-bootstrap/dist/ui-bootstrap-csp.css">
<!-- OMITIDO (06: C, reglas solo .ui-select-*): <link rel="stylesheet" href="components/angular-ui-select/dist/select.min.css"> -->
<!-- OMITIDO (solo ENVIRONMENT == "STG"): stylesheets/stg.css -->
```

### 1.C Scripts locales, parte 1 (va antes de los globales)

```html
<script src="local/config.js"></script>
<script src="local/io-shim.js"></script>
<script src="local/nucleo/store.js"></script>
<script src="local/nucleo/pathfinder-servidor.js"></script>
<script src="local/nucleo/init-run.js"></script>
<script src="local/nucleo/score-2026.js"></script>
<script src="local/nucleo/copy-properties.js"></script>
<script src="local/nucleo/api.js"></script>
<script src="local/nucleo/ranking.js"></script>
```

### 1.D Modern layout (`modern_layout.pug:4-9`)

Va después de 1.B y del `block page_css` de la página:

```html
<link href="stylesheets/common/modern_layout.css" rel="stylesheet">
<link href="stylesheets/common/modern_components.css" rel="stylesheet">
<link href="stylesheets/common/modern_list.css" rel="stylesheet">
<link href="stylesheets/common/modern_modal.css" rel="stylesheet">
```

### 1.E Cola de `head.pug:6-44` (páginas con `layout`/`modern_layout`)

```html
<script src="javascripts/translate_config.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1.0,minimum-scale=1.0,maximum-scale=1.0,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#043C78">
<meta name="charset" content="UTF-8">
<link rel="icon" type="image/vnd.microsoft.icon" sizes="16x16" href="images/favicon-16.ico">
<link rel="icon" type="image/vnd.microsoft.icon" sizes="32x32" href="images/favicon-32.ico">
<link rel="icon" type="image/vnd.microsoft.icon" sizes="96x96" href="images/favicon-96.ico">
<link rel="apple-touch-icon" sizes="144x144" href="images/apple-touch-icon-144.png">
<link rel="apple-touch-icon" sizes="152x152" href="images/apple-touch-icon-152.png">
<link rel="apple-touch-icon" sizes="180x180" href="images/apple-touch-icon-180.png">
<link rel="icon" type="image/png" sizes="196x196" href="images/favicon-196.png">
<link rel="icon" type="image/png" sizes="32x32" href="images/favicon-32.png">
<link rel="icon" type="image/png" sizes="128x128" href="images/favicon-128.png">
<!-- PENDIENTE (docs): <link rel="manifest" href="manifest.webmanifest"> ; el CMS usaba /manifest.json -->
<!-- OMITIDO (ESPEC §1, fuentes rotas en el origen): <link href="stylesheets/fonts.css" rel="stylesheet"> -->
<script>
  currentWidth = -1;
  $(window).on('load resize', function(){
  if (currentWidth == window.innerWidth) {
  return;
  }
  currentWidth = window.innerWidth;
  var height = $('.navbar').height();
  $('body').css('padding-top',height+13);
  });

  let lastTouch = 0;
  document.addEventListener('touchend', event => {
  const now = window.performance.now();
  if (now - lastTouch <= 500) {
  event.preventDefault();
  }
  lastTouch = now;
  }, true);
</script>
```

### 1.F Selector de idioma con ES (regla 3c; `language_modal.pug`)

Se usa en el `<body>` de las páginas con layout. Es el markup de `language_modal.pug` pasado a HTML. El único
agregado es la fila con la tarjeta ES; EN y JA quedan intactas.

```html
<div class="modal fade" id="languageModal" tabindex="-1" role="dialog" aria-labelledby="languageModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered" role="document">
    <div class="modal-content premium-modal-content">
      <div class="modal-header border-0">
        <button class="close" type="button" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
      </div>
      <div class="modal-body px-5 pb-5">
        <div class="text-center mb-5">
          <i class="fas fa-language fa-4x mb-3" style="color: var(--primary-color);"></i>
          <h2 class="modal-title font-weight-bold">{{"select_lang" | translate}}</h2>
        </div>
        <div class="row no-gutters gap-3">
          <div class="col-6 pr-2">
            <div class="language-card" onclick="changeLanguage('en')">
              <div class="lang-circle bg-primary">EN</div>
              <h4>English</h4>
            </div>
          </div>
          <div class="col-6 pl-2">
            <div class="language-card" onclick="changeLanguage('ja')">
              <div class="lang-circle bg-danger">JA</div>
              <h4>日本語</h4>
            </div>
          </div>
        </div>
        <!-- [rcj-line-offline] regla 3c: español agregado al selector -->
        <div class="row no-gutters gap-3 mt-3">
          <div class="col-6 pr-2">
            <div class="language-card" onclick="changeLanguage('es')">
              <div class="lang-circle bg-success">ES</div>
              <h4>Español</h4>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
    function changeLanguage(langKey) {
        try {
            const injector = angular.element(document.body).injector();
            const $translate = injector.get('$translate');
            $translate.use(langKey).then(function() {
                window.location.reload();
            });
        } catch (e) {
            // Fallback for non-angular pages or if injection fails
            console.error("Language switch failed, reloading anyway...", e);
            window.location.reload();
        }
    }
</script>
```

Las páginas standalone (juez, firma, vista, manual, planillas) no tienen selector en el CMS: el idioma se elige en
cualquier página con layout y se guarda en `localStorage` (`NG_TRANSLATE_LANG_KEY`).

### 1.G Footer fijo (`footer.pug`; lo usan las páginas con layout y la vista)

`process.env.cms_copyright` y `cms_version` quedan fijos con los valores del sitio vivo (06 §2):

```html
<footer class="footer" style="background-color: #000000; width: 100%;">
  <div class="d-flex justify-content-between align-items-center w-100 px-3 pt-1 pb-2 m-0">
    <div class="footer-text text-truncate" style="text-align:left; font-size:max(12px, min(1vw, 25px)); white-space: nowrap; color: #aaaaaa;">
      <i class="far fa-copyright" aria-hidden="true"></i>&nbsp;2016-2026 RoboCupJunior Rescue CMS Development SubCommittee&nbsp;-&nbsp;<i class="fas fa-code-branch" aria-hidden="true"></i>&nbsp; v26.0.2
    </div>
  </div>
</footer>
```

---

## 2. Páginas portadas del CMS

### 2.1 `editor.html`: `views/admin/mapEditor/line_2026.pug` (extends `modern_layout`)

Módulo `LineEditor`. Globales de `routes/admin.js:540`: `{ competitionId, mapId, leagueId }`. `pubService` vale `false` en el
modo admin (D1).

```html
<head>
<meta charset="utf-8">
<title>RoboCupJunior CMS</title>
<!-- 1.A scripts comunes -->
<!-- 1.C scripts locales, parte 1 -->
<!-- [salidas] E8 (PNG/PDF/planilla) registra rutas en RCJLocal.api: -->
<script src="components/pdfkit/js/pdfkit.standalone.js"></script>
<script src="components/qrcode-generator/qrcode.js"></script>
<script src="local/render/mapa-png.js"></script>
<script src="local/render/mapa-pdf.js"></script>
<script src="local/render/planilla-pdf.js"></script>
<script>
  // [local] globales de line_2026.pug:11-15
  var mapId = RCJLocal.param('map');
  var competitionId = RCJLocal.param('competition');
  var pubService = false;
  var leagueId = "Line";
</script>
<script src="javascripts/lvl-uuid.js"></script>
<script src="javascripts/pathFinder.js"></script>
<!-- OMITIDO (comentados en el pug): bootstrap-fileinput/js/plugins/piexif|sortable|purify.min.js -->
<!-- OMITIDO (06: C, el import usa FileReader): <script src="components/bootstrap-fileinput/js/fileinput.min.js"></script> -->
<!-- OMITIDO (06: X, soft-404 en el sitio vivo): components/bootstrap-fileinput/themes/fa/theme.min.js -->
<!-- OMITIDO (06: C, requiere fileinput): <script src="components/bootstrap-fileinput/js/locales/ja.js"></script> -->
<!-- OMITIDO (06: C, sin uso): <script src="components/html2canvas/index.js"></script> -->
<script src="javascripts/admin/mapEditor/line_2026.js"></script>
<!-- [editor] polyfill táctil (D5, flag tactil): -->
<script src="components/mobile-drag-drop/index.min.js"></script>
<script src="components/mobile-drag-drop/scroll-behaviour.min.js"></script>
<script src="local/tactil.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('LineEditor');</script>
<!-- 1.B css comunes -->
<!-- block page_css (line_2026.pug:28-32) -->
<link href="stylesheets/fredrik.css" rel="stylesheet">
<!-- OMITIDO (06: C): <link href="components/bootstrap-fileinput/css/fileinput.min.css" rel="stylesheet"> -->
<link href="stylesheets/admin/mapEditor/maze_modern.css" rel="stylesheet">
<link href="stylesheets/admin/mapEditor/line_modern.css" rel="stylesheet">
<link href="components/mobile-drag-drop/default.css" rel="stylesheet"> <!-- [editor] polyfill táctil -->
<!-- 1.D modern layout -->
<!-- 1.E cola de head.pug (translate_config.js, meta, íconos, script inline) -->
</head>
```

Body: navbar, contenido, footer (1.G), login_modal (en modo admin local no hay login) y 1.F.

### 2.2 `juez.html`: `views/judge/line_2026.pug` (standalone)

Módulo `ddApp`. Globales de `routes/line.js:93`: `{ id }`.

```html
<head>
<meta charset="utf-8">
<title>Rescue Line Judge</title>
<!-- 1.C scripts locales, parte 1 -->
<script>
  // [local] globales de judge/line_2026.pug:4-6
  var runId = RCJLocal.param('run');
  var movie = "";
</script>
<!-- 1.A scripts comunes -->
<script src="javascripts/judge/line_2026.js"></script>
<script src="local/timer-persistente.js"></script> <!-- [juez] D5, flag persistirTimer -->
<!-- OMITIDO (06: C, huérfanos): <script src="javascripts/deflate.js"></script> -->
<!-- OMITIDO (06: C): <script src="components/jquery-qrcode/jquery.qrcode.min.js"></script> -->
<!-- OMITIDO (06: C): <script src="javascripts/makeQR.js"></script> -->
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('ddApp');</script>
<script src="javascripts/translate_config.js"></script>
<!-- OMITIDO (06: C, sin data-lightbox): <script src="components/lightbox2/dist/js/lightbox.min.js"></script> -->
<!-- 1.B css comunes -->
<!-- OMITIDO (06: C): <link rel="stylesheet" href="components/lightbox2/dist/css/lightbox.min.css"> -->
<link href="stylesheets/fredrik.css" rel="stylesheet">
<!-- OMITIDO (06: C, sin .switch-toggle): <link href="components/css-toggle-switch/dist/toggle-switch.css" rel="stylesheet"> -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
</head>
```

En el pug, `include common_component` mete **scripts y css juntos** en la línea 8. En HTML, 1.A y 1.B pueden ir
seguidos en esa posición, o 1.B donde se indica arriba. El resultado es el mismo: los `<link>` no bloquean scripts
posteriores. Para respetar el render literal del pug, poner 1.A seguido de 1.B inmediatamente después del bloque
de globales. Esto vale para todas las páginas standalone.

### 2.3 `firma.html`: `views/sign/line_2026.pug` (standalone)

Módulo `ddApp`. Globales de `routes/line.js:123`: `{ id }`, así que `iframe` rinde `""`.

```html
<head>
<meta charset="utf-8">
<title>Rescue Line Sign</title>
<!-- 1.C scripts locales, parte 1 (incluye io-shim: sign/line_2026.js:114 llama io() al cargar) -->
<script>
  // [local] globales de sign/line_2026.pug:4-7
  var runId = RCJLocal.param('run');
  var timeIncrement = false;
  var iframe = "";
</script>
<!-- 1.A scripts comunes + 1.B css comunes -->
<script src="javascripts/sign/line_2026.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('ddApp');</script>
<script src="javascripts/translate_config.js"></script>
<script src="components/jSignature/libs/jSignature.min.js"></script>
<link href="stylesheets/fredrik.css" rel="stylesheet">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
</head>
```

El body incluye `views/view/common/line_2026.pug` (desglose).

### 2.4 `vista.html`: `views/view/line_2026.pug` (standalone; mismo JS que la firma)

Módulo `ddApp`. Globales de `routes/line.js:73`: `{ id, rule }`. La variante `/line/view/:id/iframe` se mapea a
`vista.html?run=<id>&iframe=true` (ESPEC §4), por eso `iframe` sale del parámetro.

```html
<head>
<meta charset="utf-8">
<title>Rescue Line View</title>
<!-- 1.C scripts locales, parte 1 (io-shim obligatorio) -->
<script>
  // [local] globales de view/line_2026.pug:4-7
  var runId = RCJLocal.param('run');
  var timeIncrement = false;
  var iframe = RCJLocal.param('iframe');
</script>
<!-- 1.A scripts comunes + 1.B css comunes -->
<script src="javascripts/sign/line_2026.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('ddApp');</script>
<script src="javascripts/translate_config.js"></script>
<link href="stylesheets/fredrik.css" rel="stylesheet">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
</head>
```

El body incluye `view/common/line_2026.pug` y, al final, el footer (1.G; `view/line_2026.pug:121`).

### 2.5 `manual.html`: `views/manual/input/line_2026.pug` y `views/manual/check/line_2026.pug`

Módulo `ddApp`. Globales de `routes/line.js:103/113`: `{ id }`. Las dos variantes comparten JS; el `<head>`
difiere en título, CSS, meta y `<style>`. Con `?check=true` va la variante B.

Variante A, input (`input/line_2026.pug:1-16`):

```html
<head>
<meta charset="utf-8">
<title>Rescue Line Input</title>
<!-- 1.C scripts locales, parte 1 -->
<script>
  var runId = RCJLocal.param('run');
</script>
<!-- 1.A scripts comunes + 1.B css comunes -->
<script src="javascripts/manual/line_2026.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('ddApp');</script>
<script src="javascripts/translate_config.js"></script>
<!-- OMITIDO (06: C): <script src="components/lightbox2/dist/js/lightbox.min.js"></script> -->
<!-- OMITIDO (06: C): <link rel="stylesheet" href="components/lightbox2/dist/css/lightbox.min.css"> -->
<link href="stylesheets/fredrik.css" rel="stylesheet">
<style>/* copiar el bloque style. de input/line_2026.pug:16 en adelante */</style>
</head>
```

Variante B, check (`check/line_2026.pug:1-19`):

```html
<head>
<meta charset="utf-8">
<title>Rescue Line Approval - Double Check</title>
<!-- 1.C scripts locales, parte 1 -->
<script>
  var runId = RCJLocal.param('run');
</script>
<!-- 1.A scripts comunes + 1.B css comunes -->
<script src="javascripts/manual/line_2026.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('ddApp');</script>
<script src="javascripts/translate_config.js"></script>
<!-- OMITIDO (06: C): lightbox2 js y css -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<!-- OMITIDO (ESPEC §1): <link href="stylesheets/fonts.css" rel="stylesheet"> -->
<style>/* copiar el bloque style. de check/line_2026.pug:19 en adelante */</style>
</head>
```

Los `<title>` distintos se pueden resolver con `document.title` según `RCJLocal.param('check')`.

### 2.6 `ranking.html`: `views/ranking/line_2026.pug` (extends `layout`, sin `modern_layout`)

Módulo `LineScore`. Globales de `routes/line.js:48`: `{ competitionId, leagueId }`.

```html
<head>
<meta charset="utf-8">
<title>RoboCupJunior CMS</title>
<!-- 1.A scripts comunes -->
<!-- 1.C scripts locales, parte 1 -->
<script>
  // [local] globales de ranking/line_2026.pug:8-10
  var competitionId = RCJLocal.param('competition');
  var leagueId = RCJLocal.param('league') || 'Line';
</script>
<script src="javascripts/ranking/line_2026.js"></script>
<script src="components/datatables/media/js/jquery.dataTables.min.js"></script>  <!-- 06: DI, el módulo exige 'datatables' -->
<script src="components/angular-datatables/demo/src/archives/dist/angular-datatables.min.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('LineScore');</script>
<!-- 1.B css comunes (no hay page_css ni modern_layout) -->
<!-- 1.E cola de head.pug -->
</head>
```

Body: `layout.pug` (navbar, breadcrumb, contenido e `include ranking/include/line_2026.pug`), footer (1.G),
login_modal y 1.F.

### 2.7 `planillas.html`: `views/admin/gamesPrint/line_2026.pug` (standalone)

Módulo `RunAdmin`. Globales de `routes/admin.js:477`: `{ competitionId, leagueId }`.

```html
<head>
<meta charset="utf-8">
<title>Rescue Line Runs Print</title>
<!-- 1.A scripts comunes + 1.B css comunes (include de la línea 6) -->
<!-- 1.C scripts locales, parte 1 -->
<script>
  // [local] globales de gamesPrint/line_2026.pug:7-9
  var competitionId = RCJLocal.param('competition');
  var leagueId = RCJLocal.param('league') || 'Line';
</script>
<script src="javascripts/admin/gamesPrint/line_2026.js"></script>
<link rel="stylesheet" href="stylesheets/admin/live_ranking.css">
<script src="components/angular-bootstrap-datetimepicker/src/js/datetimepicker.js"></script>  <!-- 06: DI -->
<script src="components/angular-bootstrap-datetimepicker/src/js/datetimepicker.templates.js"></script>
<script src="components/ng-file-upload/ng-file-upload-all.min.js"></script>  <!-- 06: DI (inyecta Upload) -->
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('RunAdmin');</script>
<script src="javascripts/translate_config.js"></script>
<style>/* copiar el bloque style(type='text/css'). de gamesPrint/line_2026.pug:17 en adelante */</style>
</head>
```

### 2.8 `corridas.html`: `views/line_competition.pug` (extends `modern_layout`)

Módulo `LineCompetition`. Globales de `routes/line.js:31-32`: `{ id, judge: 1|0, league }`. Pug los rinde como
**strings**. Offline siempre se es juez, así que `isJudge = "1"`.

```html
<head>
<meta charset="utf-8">
<title>RoboCupJunior CMS</title>
<!-- 1.A scripts comunes -->
<!-- 1.C scripts locales, parte 1 -->
<script>
  // [local] globales de line_competition.pug:8-11
  var competitionId = RCJLocal.param('competition');
  var isJudge = "1";
  var league = RCJLocal.param('league') || 'Line';
</script>
<script src="javascripts/line_competition.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('LineCompetition');</script>
<!-- 1.B css comunes -->
<style>/* block page_css: copiar el style. de line_competition.pug:14-62 */</style>
<!-- 1.D modern layout -->
<!-- 1.E cola de head.pug -->
</head>
```

### 2.9 `admin-corridas.html`: `views/admin/games.pug` (extends `modern_layout`)

Módulo `RunAdmin`. Globales de `routes/admin.js:447`: `{ competitionId, leagueId }`.

```html
<head>
<meta charset="utf-8">
<title>RoboCupJunior CMS</title>
<!-- 1.A scripts comunes -->
<!-- 1.C scripts locales, parte 1 -->
<script>
  // [local] globales de games.pug:10-12
  var competitionId = RCJLocal.param('competition');
  var leagueId = RCJLocal.param('league') || 'Line';
</script>
<script src="components/angular-bootstrap-datetimepicker/src/js/datetimepicker.js"></script>  <!-- DI + uib-datepicker -->
<script src="components/angular-bootstrap-datetimepicker/src/js/datetimepicker.templates.js"></script>
<script src="javascripts/admin/games.js"></script>
<script src="components/ng-file-upload/ng-file-upload-all.min.js"></script>
<script src="components/exceljs/index.js"></script>  <!-- export XLSX (games.js:570); 1,1 MB: se puede omitir si no se porta el export -->
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('RunAdmin');</script>
<!-- 1.B css comunes -->
<!-- (games.pug no define page_css) -->
<!-- 1.D modern layout -->
<!-- append css de games.pug:19-20 -->
<link rel="stylesheet" href="components/angular-bootstrap-datetimepicker/src/css/datetimepicker.css">
<style>/* copiar el style(type='text/css'). de games.pug:21 en adelante */</style>
<!-- 1.E cola de head.pug -->
</head>
```

Body: `games.pug` usa `script(type="text/ng-template" id="scoreSheetModal.html")` (línea 905) y `images/loader2.gif`.

### 2.10 `mapas.html`: `views/admin/maps.pug` (extends `modern_layout`; lista admin de mapas, `routes/admin.js:495-504`)

Módulo `MapAdmin`. Globales: `{ id → competitionId, leagueId }`.

```html
<head>
<meta charset="utf-8">
<title>RoboCupJunior CMS</title>
<!-- 1.A scripts comunes -->
<!-- 1.C scripts locales, parte 1 -->
<!-- [salidas] si la impresión masiva (maps.js, printSettingsModal) usa E8, agregar pdfkit, qrcode y local/render/* como en 2.1 -->
<script>
  // [local] globales de maps.pug:8-10
  var competitionId = RCJLocal.param('competition');
  var leagueId = RCJLocal.param('league') || 'Line';
</script>
<script src="javascripts/admin/maps.js"></script>
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('MapAdmin');</script>
<!-- 1.B css comunes -->
<!-- 1.D modern layout -->
<!-- 1.E cola de head.pug -->
</head>
```

---

## 3. Páginas nuevas (`index.html`, `estadisticas.html`, `configuracion.html`)

No tienen pug. Para que se vean como el resto, usar la estructura de `modern_layout`. El JS propio crea
`var app = angular.module('<Nombre>', ['ngTouch', 'ngAnimate', 'ui.bootstrap', 'pascalprecht.translate', 'ngCookies'])`
antes de `translate_config.js`.

```html
<head>
<meta charset="utf-8">
<title>RCJ Rescue Line offline</title>
<!-- 1.A scripts comunes -->
<!-- 1.C scripts locales, parte 1 -->
<!-- [estadisticas] <script src="local/estadisticas/....js"></script> -->
<script src="local/ui/<pagina>.js"></script>              <!-- crea `app` -->
<script src="local/http-backend.js"></script>
<script>RCJLocal.instalarBackend('<Nombre>');</script>
<!-- 1.B css comunes -->
<!-- 1.D modern layout -->
<link href="local/ui/<pagina>.css" rel="stylesheet">
<!-- 1.E cola de head.pug -->
</head>
```

Las claves de traducción nuevas (español) se entregan al área assets. Se fusionan en `lang/es.json` volviendo a
correr `herramientas/importar_cms.py` con un `--es-keys` adicional. `lang/` es del área assets.

---

## 4. Verificación

Cuando existan las páginas, correr `python tests/assets-verificar.py`. Comprueba que toda referencia relativa
exista, distinguiendo mayúsculas, y que no queden rutas absolutas de estáticos. Respeta `<base href>`.
