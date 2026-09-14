# Librerías vendor de rcj-line-offline (`components/`)

Generado por `herramientas/vendorizar.py` (no editar a mano; volver a correr el script). Fuente de versiones: `analysis/06-dependencias.md` §3, que las identificó comparando tamaños del sitio vivo (`https://intl.rcj.cloud/components/...`) contra cdnjs/jsDelivr.

Validaciones aplicadas a cada archivo: no es HTML (soft-404), tamaño exacto, cadena de versión cuando existe, bytes mágicos (PNG/GIF/WOFF2). La columna "Verificación" compara el sha256 contra una copia de la misma versión bajada de otro CDN.

## Por librería

| Librería | Versión | Licencia | Uso según 06 | Páginas |
|---|---|---|---|---|
| jQuery | 3.7.1 | MIT | O | todas |
| Popper.js | 1.16.1 | MIT | O | todas |
| Bootstrap | 4.4.1 | MIT | O | todas |
| AngularJS | 1.8.2 | MIT | O | todas |
| ngAnimate | 1.8.2 | MIT | O | todas |
| alertify.js (ngAlertify) | 1.0.11 (06 §3.1 decía 1.0.12 porque miden igual; el sha coincide con 1.0.11 y difiere de 1.0.12) | MIT | C | todas (sin uso) |
| SweetAlert2 | 7.33.1 | MIT | O | todas |
| socket.io-client | 4.2.0 | MIT | O/stub (se reemplaza por local/io-shim.js) | todas en el CMS; offline no se enlaza |
| UI Bootstrap (fork rrrobo/ab-for-rcj, base ui-bootstrap4 3.0.0-beta.3) | master (sin tags; fork propio, 06 §3.3) | MIT (heredada de angular-ui/bootstrap; el fork no declara LICENSE) | O | todas |
| angular-translate (+ loader static files, storage local/cookie, handler log) | 2.19.1 | MIT | O | todas |
| ngCookies | 1.8.2 | MIT | O | todas |
| ngTouch | 1.8.2 | MIT | O | todas |
| ngSanitize | 1.8.2 | MIT | O (ranking, lista); C resto | todas |
| ui-select | 0.19.8 (el banner dice "Version: 0.19.7"; identidad por tamaño y sha con cdnjs 0.19.8) | MIT | C | todas (sin uso) |
| Font Awesome Free (build de GitHub) | 5.15.4 | CSS MIT; fuentes OFL-1.1; íconos CC-BY-4.0 | O | todas |
| bootstrap-fileinput | 5.5.4 | BSD-3-Clause | C | editor (sin uso) |
| html2canvas | 1.4.1 | MIT | C | editor (sin uso) |
| jquery-qrcode (jeromeetienne) | 1.0 (master) | MIT | C | juez (sin uso) |
| Lightbox2 | 2.12.0 | MIT | C | juez, manual (sin uso) |
| css-toggle-switch | 4.1.0 | MIT | C | juez (sin uso) |
| jSignature | 2.1.3 | MIT | O | firma |
| DataTables | 1.10.21 | MIT | DI | ranking |
| angular-datatables (legacy AngularJS) | 0.5.6 | MIT | DI | ranking |
| angular-bootstrap-datetimepicker | 1.1.4 | MIT | DI | planillas, admin de corridas |
| ng-file-upload | 12.2.13 | MIT | DI | planillas, admin de corridas |
| ExcelJS | 4.2.1 (bower.json:52 apunta a cdnjs 4.2.1; identidad por sha) | MIT | O (export XLSX de admin de corridas, games.js:570) | admin de corridas |
| PDFKit (build standalone para navegador) | 0.12.3 (misma versión que cms/package.json:48) | MIT | NUEVA (salidas: PDF de mapa y planilla, D7) | editor/planillas vía local/render/* |
| qrcode-generator (Kazuhiko Arase) | 1.4.4 | MIT | NUEVA (QR de planilla, D7) | salidas |
| mobile-drag-drop (polyfill HTML5 DnD táctil) | 2.3.0-rc.2 | MIT | NUEVA (flag tactil, D5) | editor |

Uso: O = obligatoria; DI = solo la exige la inyección de módulos Angular; C = el CMS la carga sin usarla; NUEVA = agregada por la app offline.

## Por archivo

| Archivo | Bytes | sha256 | Origen | Verificación | Nota |
|---|---|---|---|---|---|
| `components/jquery/dist/jquery.min.js` | 87533 | `fc9a93dd241f6b045cbff0481cf4e1901becd0e12fb45166a8f17f95823f0b1a` | vendor-live (copia de https://intl.rcj.cloud/components/jquery/dist/jquery.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js |  |
| `components/popper.js/dist/umd/popper.min.js` | 21233 | `fe28dc38bc057f6eb11180235bbe458b3295a39b674d889075d3d9a0b5071d9f` | vendor-live (copia de https://intl.rcj.cloud/components/popper.js/dist/umd/popper.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.16.1/umd/popper.min.js |  |
| `components/bootstrap/dist/js/bootstrap.min.js` | 60010 | `5aa53525abc5c5200c70b3f6588388f86076cd699284c23cda64e92c372a1548` | vendor-live (copia de https://intl.rcj.cloud/components/bootstrap/dist/js/bootstrap.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/4.4.1/js/bootstrap.min.js |  |
| `components/bootstrap/dist/css/bootstrap.min.css` | 159515 | `2ff5b959fa9f6b4b1d04d20a37d706e90039176ab1e2a202994d9580baeebfd6` | vendor-live (copia de https://intl.rcj.cloud/components/bootstrap/dist/css/bootstrap.min.css) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/4.4.1/css/bootstrap.min.css |  |
| `components/angular/angular.min.js` | 177366 | `24103af48b9ee0409c9178cd92eba5dc3cdf0c76827b7c265c4f6f681b4dc176` | vendor-live (copia de https://intl.rcj.cloud/components/angular/angular.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular.js/1.8.2/angular.min.js |  |
| `components/angular-animate/angular-animate.min.js` | 26809 | `91dd61cff58efd54434d6bbea42fe6c0eed1af42968e9c592fb516736395c22a` | vendor-live (copia de https://intl.rcj.cloud/components/angular-animate/angular-animate.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-animate/1.8.2/angular-animate.min.js |  |
| `components/alertifyjs/dist/js/ngAlertify.js` | 11362 | `bc8aca120bd0d8aa23be5d5e089a4c2d39b709f9b9465ee914d47455ce3d0dd0` | vendor-live (copia de https://intl.rcj.cloud/components/alertifyjs/dist/js/ngAlertify.js) | idéntico a https://cdn.jsdelivr.net/npm/alertify.js@1.0.11/dist/js/ngAlertify.js |  |
| `components/sweetalert2/dist/sweetalert2.all.min.js` | 64943 | `41fc609fd8d42de18075b69e0e35de221641dd16ba3422b776f8f0006f18fb15` | vendor-live (copia de https://intl.rcj.cloud/components/sweetalert2/dist/sweetalert2.all.min.js) | idéntico a https://cdn.jsdelivr.net/npm/sweetalert2@7.33.1/dist/sweetalert2.all.min.js |  |
| `components/socket.io-client/dist/socket.io.min.js` | 66064 | `2b3ec2cdd4d4f133329f9f582315ab273306b9a68e0718ba88bb36a0fb879bde` | https://intl.rcj.cloud/components/socket.io-client/dist/socket.io.min.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.2.0/socket.io.min.js |  |
| `components/angular-bootstrap/dist/ui-bootstrap-tpls.js` | 282113 | `4145c50f7610af448ca417794d525099720fc1c7af20ade94b121389afaab745` | vendor-live (copia de https://intl.rcj.cloud/components/angular-bootstrap/dist/ui-bootstrap-tpls.js) | idéntico a https://cdn.jsdelivr.net/gh/rrrobo/ab-for-rcj@master/dist/ui-bootstrap-tpls.js |  |
| `components/angular-bootstrap/dist/ui-bootstrap-csp.css` | 4041 | `840babb7889dcdd4a72770dfdde22c5abfbbf4cae3f54c5e5d76a1e9cbaf4d78` | vendor-live (copia de https://intl.rcj.cloud/components/angular-bootstrap/dist/ui-bootstrap-csp.css) | idéntico a https://cdn.jsdelivr.net/gh/rrrobo/ab-for-rcj@master/dist/ui-bootstrap-csp.css |  |
| `components/angular-translate/angular-translate.min.js` | 24450 | `06114dc257e2b0b7eb2018a93ed37f04411058cf1ca3775e4c60a730fd09bc7d` | vendor-live (copia de https://intl.rcj.cloud/components/angular-translate/angular-translate.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-translate/2.19.1/angular-translate.min.js |  |
| `components/angular-translate-loader-static-files/angular-translate-loader-static-files.min.js` | 1373 | `1cb702a4b2ff5924c763a49a5b1dd6cff05b1af8c953d39d2f45bdd56e0ab625` | https://intl.rcj.cloud/components/angular-translate-loader-static-files/angular-translate-loader-static-files.min.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-translate-loader-static-files/2.19.1/angular-translate-loader-static-files.min.js |  |
| `components/angular-translate-storage-local/angular-translate-storage-local.min.js` | 896 | `4b6e36fd014ce67467892576bc84df5b06528d43f39d0410fb769776e64c25db` | vendor-live (copia de https://intl.rcj.cloud/components/angular-translate-storage-local/angular-translate-storage-local.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-translate-storage-local/2.19.1/angular-translate-storage-local.min.js |  |
| `components/angular-translate-storage-cookie/angular-translate-storage-cookie.min.js` | 872 | `775b8bb2f847d568e2e8f4aca597e5bfc87ed736079e7687fa801243d190a2c2` | vendor-live (copia de https://intl.rcj.cloud/components/angular-translate-storage-cookie/angular-translate-storage-cookie.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-translate-storage-cookie/2.19.1/angular-translate-storage-cookie.min.js |  |
| `components/angular-translate-handler-log/angular-translate-handler-log.min.js` | 592 | `45428a921e90c94f8b0f46f8efc4a97766c25151dd8ce8f0e03fd45d9724eca7` | vendor-live (copia de https://intl.rcj.cloud/components/angular-translate-handler-log/angular-translate-handler-log.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-translate-handler-log/2.19.1/angular-translate-handler-log.min.js |  |
| `components/angular-cookies/angular-cookies.min.js` | 1331 | `14dd592e11b348118b490883a60bdaccb4b049c9a8e9f1b79f933d61e3cafd75` | vendor-live (copia de https://intl.rcj.cloud/components/angular-cookies/angular-cookies.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-cookies/1.8.2/angular-cookies.min.js |  |
| `components/angular-touch/angular-touch.min.js` | 1740 | `e4bd11692e04ce20e8db6d96249a94dc2ccf02c49c3d8409c44396d641e52a72` | vendor-live (copia de https://intl.rcj.cloud/components/angular-touch/angular-touch.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-touch/1.8.2/angular-touch.min.js |  |
| `components/angular-sanitize/angular-sanitize.min.js` | 6526 | `3e8d479b61e09797aa910a2de2d84cb0bdd8d1e26acd061ec713082ddd57839a` | vendor-live (copia de https://intl.rcj.cloud/components/angular-sanitize/angular-sanitize.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-sanitize/1.8.2/angular-sanitize.min.js |  |
| `components/angular-ui-select/dist/select.min.js` | 45235 | `c92478334e1ce00cf85712561725984608d7325dcb5b02e4e85fe60d76f9eafd` | vendor-live (copia de https://intl.rcj.cloud/components/angular-ui-select/dist/select.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-ui-select/0.19.8/select.min.js |  |
| `components/angular-ui-select/dist/select.min.css` | 6092 | `e82d95d90c03ff1acb5ebaf72be2204fac4f6c58da5dc98526de80e2d2760e95` | vendor-live (copia de https://intl.rcj.cloud/components/angular-ui-select/dist/select.min.css) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-ui-select/0.19.8/select.min.css |  |
| `components/font-awesome-5/css/all.min.css` | 59305 | `99464ceb71bc9bbdcc72275faefe44f98eb5cbb6b5d8ee665b87b35376f1a96e` | vendor-live (copia de https://intl.rcj.cloud/components/font-awesome-5/css/all.min.css) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css |  |
| `components/font-awesome-5/webfonts/fa-solid-900.woff2` | 78260 | `1d0e6c7f6b40b62c10c929739ed76b0adbd9a08591aa95697b6f802c4dc4824f` | vendor-live (copia de https://intl.rcj.cloud/components/font-awesome-5/webfonts/fa-solid-900.woff2) | idéntico a https://cdn.jsdelivr.net/gh/FortAwesome/Font-Awesome@5.15.4/webfonts/fa-solid-900.woff2 |  |
| `components/font-awesome-5/webfonts/fa-regular-400.woff2` | 13224 | `f82c17b6cba4ae53d18f40ab8066eea83ffabe9e73ce61df4034403fbcd65265` | vendor-live (copia de https://intl.rcj.cloud/components/font-awesome-5/webfonts/fa-regular-400.woff2) | idéntico a https://cdn.jsdelivr.net/gh/FortAwesome/Font-Awesome@5.15.4/webfonts/fa-regular-400.woff2 |  |
| `components/font-awesome-5/webfonts/fa-brands-400.woff2` | 76740 | `bcc6afbc327c5fdd7e8137f7cfca1144a76a24b83d338cdb782bbf4c1bae8cbb` | vendor-live (copia de https://intl.rcj.cloud/components/font-awesome-5/webfonts/fa-brands-400.woff2) | idéntico a https://cdn.jsdelivr.net/gh/FortAwesome/Font-Awesome@5.15.4/webfonts/fa-brands-400.woff2 |  |
| `components/bootstrap-fileinput/js/fileinput.min.js` | 136598 | `7b2aa5e45c848bdf81fdf3d623cab4ad94606d8b41bb35e690ed1702a32af818` | vendor-live (copia de https://intl.rcj.cloud/components/bootstrap-fileinput/js/fileinput.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/bootstrap-fileinput/5.5.4/js/fileinput.min.js |  |
| `components/bootstrap-fileinput/js/locales/ja.js` | 8011 | `312b97691c402cee2287293d2853fc6467b944d1948aa219902e5399f2a12d90` | https://intl.rcj.cloud/components/bootstrap-fileinput/js/locales/ja.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/bootstrap-fileinput/5.5.4/js/locales/ja.js |  |
| `components/bootstrap-fileinput/css/fileinput.min.css` | 10232 | `04e9a4ed8334404d5190833f008a337d69099cf3495e8ed66724866b7c577587` | vendor-live (copia de https://intl.rcj.cloud/components/bootstrap-fileinput/css/fileinput.min.css) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/bootstrap-fileinput/5.5.4/css/fileinput.min.css |  |
| `components/bootstrap-fileinput/img/loading.gif` | 847 | `abb2c87444ef9f0ad7ff70d880ab21728e26380949753c630fa1831fe62b8026` | https://intl.rcj.cloud/components/bootstrap-fileinput/img/loading.gif | idéntico a https://cdnjs.cloudflare.com/ajax/libs/bootstrap-fileinput/5.5.4/img/loading.gif |  |
| `components/bootstrap-fileinput/img/loading-sm.gif` | 2670 | `84b11496418cc9cb300b44f9d331580dce32229b8d624f542fb1ab4a02ea9b04` | https://intl.rcj.cloud/components/bootstrap-fileinput/img/loading-sm.gif | idéntico a https://cdnjs.cloudflare.com/ajax/libs/bootstrap-fileinput/5.5.4/img/loading-sm.gif |  |
| `components/html2canvas/index.js` | 198689 | `e87e550794322e574a1fda0c1549a3c70dae5a93d9113417a429016838eab8cb` | vendor-live (copia de https://intl.rcj.cloud/components/html2canvas/index.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js |  |
| `components/jquery-qrcode/jquery.qrcode.min.js` | 13995 | `f4ccf02b69092819ac24575c717a080c3b6c6d6161f1b8d82bf0bb523075032d` | vendor-live (copia de https://intl.rcj.cloud/components/jquery-qrcode/jquery.qrcode.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/jquery.qrcode/1.0/jquery.qrcode.min.js |  |
| `components/lightbox2/dist/js/lightbox.min.js` | 14613 | `c02b1fdd46a15d65387447668bc3ad9b2b3cb47638d4c0c210273b82c7006e6b` | vendor-live (copia de https://intl.rcj.cloud/components/lightbox2/dist/js/lightbox.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/lightbox2/2.12.0/js/lightbox.min.js |  |
| `components/lightbox2/dist/css/lightbox.min.css` | 2693 | `5a84f4d3bcc035a49e7c323da27addb85edc0a00572f17f3e29a51d7704c875e` | vendor-live (copia de https://intl.rcj.cloud/components/lightbox2/dist/css/lightbox.min.css) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/lightbox2/2.12.0/css/lightbox.min.css |  |
| `components/lightbox2/dist/images/close.png` | 280 | `5d62e6c90005bfb71f6abb440f9e4753681cb23bbd5e60477ab6f442d2f0e69c` | https://intl.rcj.cloud/components/lightbox2/dist/images/close.png | idéntico a https://cdn.jsdelivr.net/npm/lightbox2@2.12.0/dist/images/close.png |  |
| `components/lightbox2/dist/images/loading.gif` | 8476 | `225aa88b6ab02c06222ec9468d62e15fa188e39cdb9431d1f55401ad380753ed` | https://intl.rcj.cloud/components/lightbox2/dist/images/loading.gif | idéntico a https://cdn.jsdelivr.net/npm/lightbox2@2.12.0/dist/images/loading.gif |  |
| `components/lightbox2/dist/images/prev.png` | 1360 | `7fd9273f20fdb1229c224341271a119020a5eee74ccf6b4605730917c864caf2` | https://intl.rcj.cloud/components/lightbox2/dist/images/prev.png | idéntico a https://cdn.jsdelivr.net/npm/lightbox2@2.12.0/dist/images/prev.png |  |
| `components/lightbox2/dist/images/next.png` | 1350 | `15b869b02c6fbaa8c6c26445a2dd2d9bad80fd27b1409f8179e5dd89dc89d90a` | https://intl.rcj.cloud/components/lightbox2/dist/images/next.png | idéntico a https://cdn.jsdelivr.net/npm/lightbox2@2.12.0/dist/images/next.png |  |
| `components/css-toggle-switch/dist/toggle-switch.css` | 15497 | `abb0c0ca34aeceafdf74a33fb9ee2088ce821c94db4a7fbcaebcaf2a6818ddd9` | vendor-live (copia de https://intl.rcj.cloud/components/css-toggle-switch/dist/toggle-switch.css) | idéntico a https://cdn.jsdelivr.net/npm/css-toggle-switch@4.1.0/dist/toggle-switch.css |  |
| `components/jSignature/libs/jSignature.min.js` | 24241 | `6f7e06f6aa97431823a4dafb29c99e95d85e9696863a06edd67ddccfc4e4aedf` | vendor-live (copia de https://intl.rcj.cloud/components/jSignature/libs/jSignature.min.js) | idéntico a https://cdnjs.cloudflare.com/ajax/libs/jSignature/2.1.3/jSignature.min.js |  |
| `components/datatables/media/js/jquery.dataTables.min.js` | 84647 | `ffbce8dbb2e5fe154a842b04fb2f26d924b96e114f11016179308bf3b1eeba60` | https://intl.rcj.cloud/components/datatables/media/js/jquery.dataTables.min.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/datatables/1.10.21/js/jquery.dataTables.min.js |  |
| `components/angular-datatables/demo/src/archives/dist/angular-datatables.min.js` | 14287 | `026ed312ef5de4bd9a5477559cf5ab7b0e096572c0d21cccf8c0515e1076e142` | https://intl.rcj.cloud/components/angular-datatables/demo/src/archives/dist/angular-datatables.min.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-datatables/0.5.6/angular-datatables.min.js |  |
| `components/angular-bootstrap-datetimepicker/src/js/datetimepicker.js` | 22071 | `64df124642e81fa7ca5310dcc1f235b8fe6b0b78d68b3c58d2d83e3cc40fac42` | https://intl.rcj.cloud/components/angular-bootstrap-datetimepicker/src/js/datetimepicker.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-bootstrap-datetimepicker/1.1.4/js/datetimepicker.js |  |
| `components/angular-bootstrap-datetimepicker/src/js/datetimepicker.templates.js` | 2957 | `2f82c5c61d98982592bd461aa5e15368396bed1c5c27045a5eae8bab7d7db553` | https://intl.rcj.cloud/components/angular-bootstrap-datetimepicker/src/js/datetimepicker.templates.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-bootstrap-datetimepicker/1.1.4/js/datetimepicker.templates.js |  |
| `components/angular-bootstrap-datetimepicker/src/css/datetimepicker.css` | 3127 | `49cd574b5ffb39823196290585f5d9e916fe115bb5b7828bb880ff65ff1b7194` | https://intl.rcj.cloud/components/angular-bootstrap-datetimepicker/src/css/datetimepicker.css | idéntico a https://cdnjs.cloudflare.com/ajax/libs/angular-bootstrap-datetimepicker/1.1.4/css/datetimepicker.css | lo enlaza views/admin/games.pug:20 (no está en la tabla de 06) |
| `components/ng-file-upload/ng-file-upload-all.min.js` | 44742 | `2eb66adde7c89055f4068a17ef1feb8d6c980ef30a7c55761c9a72e87070edc1` | https://intl.rcj.cloud/components/ng-file-upload/ng-file-upload-all.min.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/danialfarid-angular-file-upload/12.2.13/ng-file-upload-all.min.js |  |
| `components/exceljs/index.js` | 1168403 | `7c28f32fef3ea7e2b582470332bb0b357a2409cd32ded2a57c54f280f5505804` | https://intl.rcj.cloud/components/exceljs/index.js | idéntico a https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.2.1/exceljs.min.js | lo enlaza views/admin/games.pug:17 (no está en la tabla de 06) |
| `components/pdfkit/js/pdfkit.standalone.js` | 2651046 | `c134a418995507e4b1c0f0c6a755a7fbcda8c7e2a56cffaf7b961283e24358ca` | https://cdn.jsdelivr.net/npm/pdfkit@0.12.3/js/pdfkit.standalone.js | idéntico a https://unpkg.com/pdfkit@0.12.3/js/pdfkit.standalone.js |  |
| `components/qrcode-generator/qrcode.js` | 56694 | `18ae399f81182bc9de916e9c77b195df20cc58d6f2d55a62b085a299f1bf1780` | https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js | idéntico a https://unpkg.com/qrcode-generator@1.4.4/qrcode.js |  |
| `components/mobile-drag-drop/index.min.js` | 10693 | `de9f5cd8299bb2ba0384e79344bf545f74d498ff2085fe187ee4031267d9e83f` | https://cdn.jsdelivr.net/npm/mobile-drag-drop@2.3.0-rc.2/index.min.js | idéntico a https://unpkg.com/mobile-drag-drop@2.3.0-rc.2/index.min.js |  |
| `components/mobile-drag-drop/scroll-behaviour.min.js` | 2456 | `32ec4549e4cf314ebcbeae70c552ab75fc3db4244ada4b9be78c690a009a683c` | https://cdn.jsdelivr.net/npm/mobile-drag-drop@2.3.0-rc.2/scroll-behaviour.min.js | idéntico a https://unpkg.com/mobile-drag-drop@2.3.0-rc.2/scroll-behaviour.min.js |  |
| `components/mobile-drag-drop/default.css` | 260 | `78460a8d3512f692dd035f09657a924a9a44ff5053ba7107cb7fc51ce2986448` | https://cdn.jsdelivr.net/npm/mobile-drag-drop@2.3.0-rc.2/default.css | idéntico a https://unpkg.com/mobile-drag-drop@2.3.0-rc.2/default.css |  |

## Omitido a propósito

- `components/bootstrap-fileinput/themes/fa/theme.min.js`: No existe en bootstrap-fileinput 5.5.4; el sitio vivo responde soft-404 (HTML de 10 631 bytes) y la copia de vendor-live es ese HTML. El pug lo pide (editor line_2026.pug:23) pero no se empaqueta (06 §3.1 #24).
- `fonts/outfit/*.ttf, fonts/inter/*.ttf (8 archivos)`: Son páginas HTML de GitHub guardadas con extensión .ttf, en el repo y en el sitio vivo (06 §4.3). No se empaquetan (ESPEC §1).
- `components/font-awesome-5/webfonts/*.woff, *.ttf, *.eot, *.svg`: Formatos de respaldo de all.min.css que un navegador actual no pide (usa woff2). 06 §4.3 recomienda solo los 3 woff2.
- `components/bootstrap-fileinput/js/plugins/{piexif,sortable,purify}.min.js`: Comentados en el pug del editor (line_2026.pug:19-21).
- `*.map (source maps)`: Solo DevTools; los comentarios sourceMappingURL no afectan la ejecución.
- `Dependencias de bower.json que ninguna página de Línea 2026 carga`: angular-color-picker, angular-toastr, async, cheet.js, dateformat, image-compressor, driver.js, ngQuill/quill, pdfjs, socket.io (servidor), tether, jquery-ui, mutation_events (06 §3.1).

### Archivos de `vendor-live/components` que no se copiaron

- `bootstrap-fileinput/themes/fa/theme.min.js`: HTML soft-404
- `font-awesome-5/webfonts/fa-brands-400.ttf`: no requerido
- `font-awesome-5/webfonts/fa-brands-400.woff`: no requerido
- `font-awesome-5/webfonts/fa-regular-400.ttf`: no requerido
- `font-awesome-5/webfonts/fa-regular-400.woff`: no requerido
- `font-awesome-5/webfonts/fa-solid-900.ttf`: no requerido
- `font-awesome-5/webfonts/fa-solid-900.woff`: no requerido

## Notas

- **SweetAlert2 tiene que quedar en 7.x**: el código mezcla `swal(...)` y `Swal.fire(...)` (06 §3.3).
- **UI Bootstrap es un fork** (`rrrobo/ab-for-rcj`, banner "ui-bootstrap4 3.0.0-beta.3"); no reemplazar por angular-ui-bootstrap 2.5.6.
- **PDFKit**: existe exactamente la 0.12.3 (la del servidor del CMS) en npm; no hizo falta usar una versión cercana.
- **Font Awesome**: los woff2 son los del repo de GitHub 5.15.4 (difieren por pocos bytes de los de npm/cdnjs, 06 §3.3).
- socket.io-client, ngAlertify, ui-select, bootstrap-fileinput, html2canvas, jquery-qrcode, lightbox2 y css-toggle-switch se vendorizan para poder reproducir el orden de carga original, pero `herramientas/fragmentos-head.md` indica omitirlos (sin uso en Línea 2026 o reemplazados por `local/io-shim.js`).
