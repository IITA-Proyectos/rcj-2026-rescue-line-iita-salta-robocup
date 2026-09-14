#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vendorizar.py - Arma components/ de rcj-line-offline con las librerías vendor exactas del sitio vivo
(https://intl.rcj.cloud/components/...) y las librerías nuevas que necesita la app offline.

Fuentes, en orden de preferencia:
  1. Copia local del sitio vivo ya bajada (--vendor-live, carpeta con components/...).
  2. El archivo ya presente en components/ si pasa todas las validaciones (no hace falta red).
  3. Descarga desde la URL primaria (sitio vivo o jsDelivr para las libs nuevas).

Validaciones obligatorias por archivo (si alguna falla NO se escribe y el script termina con error):
  - no es HTML (el sitio vivo responde "soft-404": HTTP 200 text/html para rutas inexistentes);
  - si se descargó, el Content-Type no es text/html;
  - tamaño exacto = el que midió analysis/06-dependencias.md (o el HEAD de jsDelivr para libs nuevas);
  - cadena de versión esperada dentro del archivo, cuando la hay;
  - bytes mágicos para imágenes y fuentes (PNG, GIF, WOFF2).
Verificación de identidad (informativa, se hace una vez por sha y queda guardada): se baja la misma
versión desde cdnjs/jsDelivr/unpkg y se compara el sha256.

Salidas: components/**, components/VERSIONES.md, herramientas/vendorizar.estado.json.
Idempotente: si el archivo ya está y coincide, no se reescribe ni se vuelve a verificar.

Uso: python herramientas/vendorizar.py [--vendor-live <carpeta>] [--destino <app>]
                                       [--reverificar] [--redescargar]
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import OrderedDict

VIVO = 'https://intl.rcj.cloud/components/'
CDNJS = 'https://cdnjs.cloudflare.com/ajax/libs/'
JSD = 'https://cdn.jsdelivr.net/'
UNPKG = 'https://unpkg.com/'
UA = 'rcj-line-offline-vendorizar/1.0 (+python urllib)'


def F(dest, tam, contiene=None, cdn=None, url=None, nota=None):
    return dict(dest=dest, tam=tam, contiene=contiene, cdn=cdn, url=url or (VIVO + dest), nota=nota)


LIBS = [
    dict(nombre='jQuery', version='3.7.1', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('jquery/dist/jquery.min.js', 87533, 'jQuery v3.7.1', CDNJS + 'jquery/3.7.1/jquery.min.js')]),
    dict(nombre='Popper.js', version='1.16.1', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('popper.js/dist/umd/popper.min.js', 21233, 'Federico Zivolo', CDNJS + 'popper.js/1.16.1/umd/popper.min.js')]),
    dict(nombre='Bootstrap', version='4.4.1', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('bootstrap/dist/js/bootstrap.min.js', 60010, 'Bootstrap v4.4.1', CDNJS + 'twitter-bootstrap/4.4.1/js/bootstrap.min.js'),
        F('bootstrap/dist/css/bootstrap.min.css', 159515, 'Bootstrap v4.4.1', CDNJS + 'twitter-bootstrap/4.4.1/css/bootstrap.min.css')]),
    dict(nombre='AngularJS', version='1.8.2', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('angular/angular.min.js', 177366, 'AngularJS v1.8.2', CDNJS + 'angular.js/1.8.2/angular.min.js')]),
    dict(nombre='ngAnimate', version='1.8.2', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('angular-animate/angular-animate.min.js', 26809, 'AngularJS v1.8.2', CDNJS + 'angular-animate/1.8.2/angular-animate.min.js')]),
    dict(nombre='alertify.js (ngAlertify)', version='1.0.11 (06 §3.1 decía 1.0.12 porque miden igual; el sha coincide con 1.0.11 y difiere de 1.0.12)',
         licencia='MIT', uso='C', paginas='todas (sin uso)', archivos=[
        F('alertifyjs/dist/js/ngAlertify.js', 11362, 'version:"1.0.11"', JSD + 'npm/alertify.js@1.0.11/dist/js/ngAlertify.js')]),
    dict(nombre='SweetAlert2', version='7.33.1', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('sweetalert2/dist/sweetalert2.all.min.js', 64943, 'version="7.33.1', JSD + 'npm/sweetalert2@7.33.1/dist/sweetalert2.all.min.js')]),
    dict(nombre='socket.io-client', version='4.2.0', licencia='MIT', uso='O/stub (se reemplaza por local/io-shim.js)',
         paginas='todas en el CMS; offline no se enlaza', archivos=[
        F('socket.io-client/dist/socket.io.min.js', 66064, 'Socket.IO v4.2.0', CDNJS + 'socket.io/4.2.0/socket.io.min.js')]),
    dict(nombre='UI Bootstrap (fork rrrobo/ab-for-rcj, base ui-bootstrap4 3.0.0-beta.3)', version='master (sin tags; fork propio, 06 §3.3)',
         licencia='MIT (heredada de angular-ui/bootstrap; el fork no declara LICENSE)', uso='O', paginas='todas', archivos=[
        F('angular-bootstrap/dist/ui-bootstrap-tpls.js', 282113, 'ui-bootstrap4', JSD + 'gh/rrrobo/ab-for-rcj@master/dist/ui-bootstrap-tpls.js'),
        F('angular-bootstrap/dist/ui-bootstrap-csp.css', 4041, 'CSP mode', JSD + 'gh/rrrobo/ab-for-rcj@master/dist/ui-bootstrap-csp.css')]),
    dict(nombre='angular-translate (+ loader static files, storage local/cookie, handler log)', version='2.19.1', licencia='MIT',
         uso='O', paginas='todas', archivos=[
        F('angular-translate/angular-translate.min.js', 24450, 'v2.19.1', CDNJS + 'angular-translate/2.19.1/angular-translate.min.js'),
        F('angular-translate-loader-static-files/angular-translate-loader-static-files.min.js', 1373, 'v2.19.1',
          CDNJS + 'angular-translate-loader-static-files/2.19.1/angular-translate-loader-static-files.min.js'),
        F('angular-translate-storage-local/angular-translate-storage-local.min.js', 896, 'v2.19.1',
          CDNJS + 'angular-translate-storage-local/2.19.1/angular-translate-storage-local.min.js'),
        F('angular-translate-storage-cookie/angular-translate-storage-cookie.min.js', 872, 'v2.19.1',
          CDNJS + 'angular-translate-storage-cookie/2.19.1/angular-translate-storage-cookie.min.js'),
        F('angular-translate-handler-log/angular-translate-handler-log.min.js', 592, 'v2.19.1',
          CDNJS + 'angular-translate-handler-log/2.19.1/angular-translate-handler-log.min.js')]),
    dict(nombre='ngCookies', version='1.8.2', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('angular-cookies/angular-cookies.min.js', 1331, 'AngularJS v1.8.2', CDNJS + 'angular-cookies/1.8.2/angular-cookies.min.js')]),
    dict(nombre='ngTouch', version='1.8.2', licencia='MIT', uso='O', paginas='todas', archivos=[
        F('angular-touch/angular-touch.min.js', 1740, 'AngularJS v1.8.2', CDNJS + 'angular-touch/1.8.2/angular-touch.min.js')]),
    dict(nombre='ngSanitize', version='1.8.2', licencia='MIT', uso='O (ranking, lista); C resto', paginas='todas', archivos=[
        F('angular-sanitize/angular-sanitize.min.js', 6526, 'AngularJS v1.8.2', CDNJS + 'angular-sanitize/1.8.2/angular-sanitize.min.js')]),
    dict(nombre='ui-select', version='0.19.8 (el banner dice "Version: 0.19.7"; identidad por tamaño y sha con cdnjs 0.19.8)',
         licencia='MIT', uso='C', paginas='todas (sin uso)', archivos=[
        F('angular-ui-select/dist/select.min.js', 45235, 'ui-select', CDNJS + 'angular-ui-select/0.19.8/select.min.js'),
        F('angular-ui-select/dist/select.min.css', 6092, 'ui-select', CDNJS + 'angular-ui-select/0.19.8/select.min.css')]),
    dict(nombre='Font Awesome Free (build de GitHub)', version='5.15.4', licencia='CSS MIT; fuentes OFL-1.1; íconos CC-BY-4.0',
         uso='O', paginas='todas', archivos=[
        F('font-awesome-5/css/all.min.css', 59305, 'Font Awesome Free 5.15.4', CDNJS + 'font-awesome/5.15.4/css/all.min.css'),
        F('font-awesome-5/webfonts/fa-solid-900.woff2', 78260, None, JSD + 'gh/FortAwesome/Font-Awesome@5.15.4/webfonts/fa-solid-900.woff2'),
        F('font-awesome-5/webfonts/fa-regular-400.woff2', 13224, None, JSD + 'gh/FortAwesome/Font-Awesome@5.15.4/webfonts/fa-regular-400.woff2'),
        F('font-awesome-5/webfonts/fa-brands-400.woff2', 76740, None, JSD + 'gh/FortAwesome/Font-Awesome@5.15.4/webfonts/fa-brands-400.woff2')]),
    dict(nombre='bootstrap-fileinput', version='5.5.4', licencia='BSD-3-Clause', uso='C', paginas='editor (sin uso)', archivos=[
        F('bootstrap-fileinput/js/fileinput.min.js', 136598, 'bootstrap-fileinput v5.5.4', CDNJS + 'bootstrap-fileinput/5.5.4/js/fileinput.min.js'),
        F('bootstrap-fileinput/js/locales/ja.js', 8011, None, CDNJS + 'bootstrap-fileinput/5.5.4/js/locales/ja.js'),
        F('bootstrap-fileinput/css/fileinput.min.css', 10232, 'bootstrap-fileinput v5.5.4', CDNJS + 'bootstrap-fileinput/5.5.4/css/fileinput.min.css'),
        F('bootstrap-fileinput/img/loading.gif', 847, None, CDNJS + 'bootstrap-fileinput/5.5.4/img/loading.gif'),
        F('bootstrap-fileinput/img/loading-sm.gif', 2670, None, CDNJS + 'bootstrap-fileinput/5.5.4/img/loading-sm.gif')]),
    dict(nombre='html2canvas', version='1.4.1', licencia='MIT', uso='C', paginas='editor (sin uso)', archivos=[
        F('html2canvas/index.js', 198689, 'html2canvas 1.4.1', CDNJS + 'html2canvas/1.4.1/html2canvas.min.js')]),
    dict(nombre='jquery-qrcode (jeromeetienne)', version='1.0 (master)', licencia='MIT', uso='C', paginas='juez (sin uso)', archivos=[
        F('jquery-qrcode/jquery.qrcode.min.js', 13995, 'fn.qrcode', CDNJS + 'jquery.qrcode/1.0/jquery.qrcode.min.js')]),
    dict(nombre='Lightbox2', version='2.12.0', licencia='MIT', uso='C', paginas='juez, manual (sin uso)', archivos=[
        F('lightbox2/dist/js/lightbox.min.js', 14613, 'Lightbox', CDNJS + 'lightbox2/2.12.0/js/lightbox.min.js'),
        F('lightbox2/dist/css/lightbox.min.css', 2693, 'lb-', CDNJS + 'lightbox2/2.12.0/css/lightbox.min.css'),
        # cdnjs recomprime las imágenes (237/1035/1031 bytes); se verifica contra el paquete npm.
        F('lightbox2/dist/images/close.png', 280, None, JSD + 'npm/lightbox2@2.12.0/dist/images/close.png'),
        F('lightbox2/dist/images/loading.gif', 8476, None, JSD + 'npm/lightbox2@2.12.0/dist/images/loading.gif'),
        F('lightbox2/dist/images/prev.png', 1360, None, JSD + 'npm/lightbox2@2.12.0/dist/images/prev.png'),
        F('lightbox2/dist/images/next.png', 1350, None, JSD + 'npm/lightbox2@2.12.0/dist/images/next.png')]),
    dict(nombre='css-toggle-switch', version='4.1.0', licencia='MIT', uso='C', paginas='juez (sin uso)', archivos=[
        F('css-toggle-switch/dist/toggle-switch.css', 15497, 'CSS TOGGLE SWITCH', JSD + 'npm/css-toggle-switch@4.1.0/dist/toggle-switch.css')]),
    dict(nombre='jSignature', version='2.1.3', licencia='MIT', uso='O', paginas='firma', archivos=[
        F('jSignature/libs/jSignature.min.js', 24241, 'jSignature v2', CDNJS + 'jSignature/2.1.3/jSignature.min.js')]),
    dict(nombre='DataTables', version='1.10.21', licencia='MIT', uso='DI', paginas='ranking', archivos=[
        F('datatables/media/js/jquery.dataTables.min.js', 84647, None, CDNJS + 'datatables/1.10.21/js/jquery.dataTables.min.js')]),
    dict(nombre='angular-datatables (legacy AngularJS)', version='0.5.6', licencia='MIT', uso='DI', paginas='ranking', archivos=[
        F('angular-datatables/demo/src/archives/dist/angular-datatables.min.js', 14287, None, CDNJS + 'angular-datatables/0.5.6/angular-datatables.min.js')]),
    dict(nombre='angular-bootstrap-datetimepicker', version='1.1.4', licencia='MIT', uso='DI', paginas='planillas, admin de corridas', archivos=[
        F('angular-bootstrap-datetimepicker/src/js/datetimepicker.js', 22071, None, CDNJS + 'angular-bootstrap-datetimepicker/1.1.4/js/datetimepicker.js'),
        F('angular-bootstrap-datetimepicker/src/js/datetimepicker.templates.js', 2957, None, CDNJS + 'angular-bootstrap-datetimepicker/1.1.4/js/datetimepicker.templates.js'),
        F('angular-bootstrap-datetimepicker/src/css/datetimepicker.css', 3127, None, CDNJS + 'angular-bootstrap-datetimepicker/1.1.4/css/datetimepicker.css',
          nota='lo enlaza views/admin/games.pug:20 (no está en la tabla de 06)')]),
    dict(nombre='ng-file-upload', version='12.2.13', licencia='MIT', uso='DI', paginas='planillas, admin de corridas', archivos=[
        F('ng-file-upload/ng-file-upload-all.min.js', 44742, None, CDNJS + 'danialfarid-angular-file-upload/12.2.13/ng-file-upload-all.min.js')]),
    dict(nombre='ExcelJS', version='4.2.1 (bower.json:52 apunta a cdnjs 4.2.1; identidad por sha)', licencia='MIT', uso='O (export XLSX de admin de corridas, games.js:570)',
         paginas='admin de corridas', archivos=[
        F('exceljs/index.js', 1168403, None, CDNJS + 'exceljs/4.2.1/exceljs.min.js', nota='lo enlaza views/admin/games.pug:17 (no está en la tabla de 06)')]),
    # --- Librerías nuevas de la app offline (no existen en el CMS) ---
    dict(nombre='PDFKit (build standalone para navegador)', version='0.12.3 (misma versión que cms/package.json:48)', licencia='MIT',
         uso='NUEVA (salidas: PDF de mapa y planilla, D7)', paginas='editor/planillas vía local/render/*', archivos=[
        F('pdfkit/js/pdfkit.standalone.js', 2651046, 'PDFDocument', UNPKG + 'pdfkit@0.12.3/js/pdfkit.standalone.js',
          url=JSD + 'npm/pdfkit@0.12.3/js/pdfkit.standalone.js')]),
    dict(nombre='qrcode-generator (Kazuhiko Arase)', version='1.4.4', licencia='MIT', uso='NUEVA (QR de planilla, D7)', paginas='salidas', archivos=[
        F('qrcode-generator/qrcode.js', 56694, 'qrcode', UNPKG + 'qrcode-generator@1.4.4/qrcode.js',
          url=JSD + 'npm/qrcode-generator@1.4.4/qrcode.js')]),
    dict(nombre='mobile-drag-drop (polyfill HTML5 DnD táctil)', version='2.3.0-rc.2', licencia='MIT', uso='NUEVA (flag tactil, D5)', paginas='editor', archivos=[
        F('mobile-drag-drop/index.min.js', 10693, 'MobileDragDrop', UNPKG + 'mobile-drag-drop@2.3.0-rc.2/index.min.js',
          url=JSD + 'npm/mobile-drag-drop@2.3.0-rc.2/index.min.js'),
        F('mobile-drag-drop/scroll-behaviour.min.js', 2456, None, UNPKG + 'mobile-drag-drop@2.3.0-rc.2/scroll-behaviour.min.js',
          url=JSD + 'npm/mobile-drag-drop@2.3.0-rc.2/scroll-behaviour.min.js'),
        F('mobile-drag-drop/default.css', 260, None, UNPKG + 'mobile-drag-drop@2.3.0-rc.2/default.css',
          url=JSD + 'npm/mobile-drag-drop@2.3.0-rc.2/default.css')]),
]

OMISIONES = [
    ('components/bootstrap-fileinput/themes/fa/theme.min.js', 'No existe en bootstrap-fileinput 5.5.4; el sitio vivo responde soft-404 (HTML de 10 631 bytes) y la copia de vendor-live es ese HTML. El pug lo pide (editor line_2026.pug:23) pero no se empaqueta (06 §3.1 #24).'),
    ('fonts/outfit/*.ttf, fonts/inter/*.ttf (8 archivos)', 'Son páginas HTML de GitHub guardadas con extensión .ttf, en el repo y en el sitio vivo (06 §4.3). No se empaquetan (ESPEC §1).'),
    ('components/font-awesome-5/webfonts/*.woff, *.ttf, *.eot, *.svg', 'Formatos de respaldo de all.min.css que un navegador actual no pide (usa woff2). 06 §4.3 recomienda solo los 3 woff2.'),
    ('components/bootstrap-fileinput/js/plugins/{piexif,sortable,purify}.min.js', 'Comentados en el pug del editor (line_2026.pug:19-21).'),
    ('*.map (source maps)', 'Solo DevTools; los comentarios sourceMappingURL no afectan la ejecución.'),
    ('Dependencias de bower.json que ninguna página de Línea 2026 carga', 'angular-color-picker, angular-toastr, async, cheet.js, dateformat, image-compressor, driver.js, ngQuill/quill, pdfjs, socket.io (servidor), tether, jquery-ui, mutation_events (06 §3.1).'),
]


# ---------------------------------------------------------------------------------------------
def sha256(b):
    return hashlib.sha256(b).hexdigest()


def parece_html(datos):
    cabeza = datos[:2048].lstrip(b'\xef\xbb\xbf \t\r\n').lower()
    return cabeza.startswith((b'<!doctype', b'<html', b'<head', b'<body')) or b'<!doctype html' in cabeza[:512]


def magic_ok(dest, datos):
    ext = os.path.splitext(dest)[1].lower()
    if ext == '.png':
        return datos.startswith(b'\x89PNG\r\n\x1a\n')
    if ext == '.gif':
        return datos.startswith((b'GIF87a', b'GIF89a'))
    if ext == '.woff2':
        return datos.startswith(b'wOF2')
    if ext == '.woff':
        return datos.startswith(b'wOFF')
    return True


def descargar(url, reintentos=3):
    ultimo = None
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers.get('Content-Type', ''), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get('Content-Type', '') if e.headers else '', b''
        except Exception as e:  # red intermitente
            ultimo = e
            time.sleep(1 + intento)
    raise RuntimeError('no se pudo descargar %s: %s' % (url, ultimo))


def validar(archivo, datos, content_type=None):
    errores = []
    if parece_html(datos):
        errores.append('el contenido es HTML (soft-404)')
    if content_type and 'text/html' in content_type.lower():
        errores.append('Content-Type text/html')
    if archivo['tam'] is not None and len(datos) != archivo['tam']:
        errores.append('tamaño %d != esperado %d' % (len(datos), archivo['tam']))
    if archivo['contiene'] and archivo['contiene'].encode('utf-8') not in datos:
        errores.append('no contiene la cadena de versión "%s"' % archivo['contiene'])
    if not magic_ok(archivo['dest'], datos):
        errores.append('bytes mágicos incorrectos para %s' % os.path.splitext(archivo['dest'])[1])
    return errores


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    app_por_defecto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description='Vendoriza components/ para rcj-line-offline.')
    ap.add_argument('--vendor-live', help='carpeta con components/ bajada del sitio vivo')
    ap.add_argument('--destino', default=app_por_defecto)
    ap.add_argument('--reverificar', action='store_true', help='volver a comparar contra el CDN aunque ya esté verificado')
    ap.add_argument('--redescargar', action='store_true', help='ignorar lo que ya está en components/')
    args = ap.parse_args()

    app = os.path.abspath(args.destino)
    comp = os.path.join(app, 'components')
    estado_path = os.path.join(app, 'herramientas', 'vendorizar.estado.json')
    estado = {}
    if os.path.exists(estado_path):
        with open(estado_path, 'r', encoding='utf-8') as f:
            estado = json.load(f).get('archivos', {})

    print('=' * 100)
    print('vendorizar.py -> %s' % comp)
    print('=' * 100)
    errores_totales = []
    avisos = []
    conteo = OrderedDict()
    inventario = set()
    for lib in LIBS:
        print('\n## %s %s [%s]' % (lib['nombre'], lib['version'], lib['uso']))
        for a in lib['archivos']:
            inventario.add(a['dest'])
            destino = os.path.join(comp, *a['dest'].split('/'))
            origen = None
            content_type = None
            datos = None
            local = os.path.join(args.vendor_live, 'components', *a['dest'].split('/')) if args.vendor_live else None
            if local and os.path.isfile(local):
                with open(local, 'rb') as f:
                    datos = f.read()
                origen = 'vendor-live (copia de %s)' % a['url']
            elif os.path.isfile(destino) and not args.redescargar:
                with open(destino, 'rb') as f:
                    datos = f.read()
                if validar(a, datos):
                    datos = None
                else:
                    origen = estado.get(a['dest'], {}).get('origen') or ('existente (originalmente %s)' % a['url'])
            if datos is None:
                status, content_type, datos = descargar(a['url'])
                origen = a['url']
                if status != 200:
                    errores_totales.append('%s: HTTP %s en %s' % (a['dest'], status, a['url']))
                    print('    ERROR %-70s HTTP %s' % (a['dest'], status))
                    continue
            errs = validar(a, datos, content_type)
            if errs:
                errores_totales.append('%s: %s (origen %s)' % (a['dest'], '; '.join(errs), origen))
                print('    ERROR %-70s %s' % (a['dest'], '; '.join(errs)))
                continue
            sha = sha256(datos)
            previo = estado.get(a['dest'], {})
            # Escritura idempotente
            accion = 'sin cambios'
            actual = None
            if os.path.isfile(destino):
                with open(destino, 'rb') as f:
                    actual = f.read()
            if actual != datos:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                tmp = destino + '.tmp-vendorizar'
                with open(tmp, 'wb') as f:
                    f.write(datos)
                os.replace(tmp, destino)
                accion = 'creado' if actual is None else 'actualizado'
            conteo[accion] = conteo.get(accion, 0) + 1
            # Verificación contra CDN
            verif = previo.get('verificacion') if previo.get('sha256') == sha else None
            if a['cdn'] and (verif is None or args.reverificar or verif.startswith('sin verificar') or a['cdn'] not in verif):
                try:
                    st, _ct, cdn_datos = descargar(a['cdn'])
                    if st != 200:
                        verif = 'sin verificar (HTTP %s en %s)' % (st, a['cdn'])
                    elif sha256(cdn_datos) == sha:
                        verif = 'idéntico a %s' % a['cdn']
                    else:
                        verif = 'DISTINTO de %s (%d bytes, sha256 %s)' % (a['cdn'], len(cdn_datos), sha256(cdn_datos)[:16])
                        avisos.append('%s: %s' % (a['dest'], verif))
                except RuntimeError as e:
                    verif = 'sin verificar (%s)' % e
            elif not a['cdn']:
                verif = verif or 'sin URL alternativa'
            estado[a['dest']] = OrderedDict([
                ('biblioteca', lib['nombre']), ('version', lib['version']), ('licencia', lib['licencia']),
                ('bytes', len(datos)), ('sha256', sha), ('origen', origen), ('verificacion', verif),
                ('nota', a['nota']),
            ])
            print('    %-12s %-70s %8d  %s' % (accion, a['dest'], len(datos), verif))

    # Archivos presentes en components/ que no están en el inventario
    ajenos = []
    for raiz, _dirs, archivos in os.walk(comp):
        for n in archivos:
            rel = os.path.relpath(os.path.join(raiz, n), comp).replace(os.sep, '/')
            if rel != 'VERSIONES.md' and rel not in inventario:
                ajenos.append(rel)
    ignorados_vl = []
    if args.vendor_live:
        base_vl = os.path.join(args.vendor_live, 'components')
        for raiz, _dirs, archivos in os.walk(base_vl):
            for n in archivos:
                rel = os.path.relpath(os.path.join(raiz, n), base_vl).replace(os.sep, '/')
                if rel not in inventario:
                    with open(os.path.join(raiz, n), 'rb') as f:
                        es_html = parece_html(f.read(4096))
                    ignorados_vl.append((rel, 'HTML soft-404' if es_html else 'no requerido'))

    # Guardar estado
    os.makedirs(os.path.dirname(estado_path), exist_ok=True)
    with open(estado_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'generado': datetime.date.today().isoformat(), 'archivos': OrderedDict(sorted(estado.items()))},
                  f, ensure_ascii=False, indent=2)
        f.write('\n')

    escribir_versiones(os.path.join(comp, 'VERSIONES.md'), estado, ignorados_vl)

    print('\nResumen: ' + ', '.join('%s=%d' % kv for kv in conteo.items()))
    total = sum(v['bytes'] for k, v in estado.items() if k in inventario)
    print('Tamaño total de components/ (inventario): %.1f KB' % (total / 1024))
    if ignorados_vl:
        print('Archivos de vendor-live NO copiados:')
        for rel, motivo in ignorados_vl:
            print('    %-70s %s' % (rel, motivo))
    if ajenos:
        print('AVISO: archivos en components/ fuera del inventario: %s' % ', '.join(ajenos))
    for av in avisos:
        print('AVISO: ' + av)
    if errores_totales:
        print('\nERRORES:')
        for e in errores_totales:
            print('    ' + e)
        return 1
    print('Sin errores.')
    return 0


def escribir_versiones(ruta, estado, ignorados_vl):
    lineas = [
        '# Librerías vendor de rcj-line-offline (`components/`)', '',
        'Generado por `herramientas/vendorizar.py` (no editar a mano; volver a correr el script). '
        'Fuente de versiones: `analysis/06-dependencias.md` §3, que las identificó comparando tamaños del sitio vivo '
        '(`https://intl.rcj.cloud/components/...`) contra cdnjs/jsDelivr.', '',
        'Validaciones aplicadas a cada archivo: no es HTML (soft-404), tamaño exacto, cadena de versión cuando existe, '
        'bytes mágicos (PNG/GIF/WOFF2). La columna "Verificación" compara el sha256 contra una copia de la misma '
        'versión bajada de otro CDN.', '',
        '## Por librería', '',
        '| Librería | Versión | Licencia | Uso según 06 | Páginas |', '|---|---|---|---|---|',
    ]
    for lib in LIBS:
        lineas.append('| %s | %s | %s | %s | %s |' % (lib['nombre'], lib['version'], lib['licencia'], lib['uso'], lib['paginas']))
    lineas += ['', 'Uso: O = obligatoria; DI = solo la exige la inyección de módulos Angular; C = el CMS la carga sin usarla; '
               'NUEVA = agregada por la app offline.', '',
               '## Por archivo', '',
               '| Archivo | Bytes | sha256 | Origen | Verificación | Nota |', '|---|---|---|---|---|---|']
    for lib in LIBS:
        for a in lib['archivos']:
            e = estado.get(a['dest'])
            if not e:
                lineas.append('| `components/%s` | — | — | FALTA | — | — |' % a['dest'])
                continue
            lineas.append('| `components/%s` | %d | `%s` | %s | %s | %s |' % (
                a['dest'], e['bytes'], e['sha256'], e['origen'], e['verificacion'], e.get('nota') or ''))
    lineas += ['', '## Omitido a propósito', '']
    for que, por in OMISIONES:
        lineas.append('- `%s`: %s' % (que, por))
    if ignorados_vl:
        lineas += ['', '### Archivos de `vendor-live/components` que no se copiaron', '']
        for rel, motivo in ignorados_vl:
            lineas.append('- `%s`: %s' % (rel, motivo))
    lineas += ['', '## Notas', '',
               '- **SweetAlert2 tiene que quedar en 7.x**: el código mezcla `swal(...)` y `Swal.fire(...)` (06 §3.3).',
               '- **UI Bootstrap es un fork** (`rrrobo/ab-for-rcj`, banner "ui-bootstrap4 3.0.0-beta.3"); no reemplazar por angular-ui-bootstrap 2.5.6.',
               '- **PDFKit**: existe exactamente la 0.12.3 (la del servidor del CMS) en npm; no hizo falta usar una versión cercana.',
               '- **Font Awesome**: los woff2 son los del repo de GitHub 5.15.4 (difieren por pocos bytes de los de npm/cdnjs, 06 §3.3).',
               '- socket.io-client, ngAlertify, ui-select, bootstrap-fileinput, html2canvas, jquery-qrcode, lightbox2 y css-toggle-switch '
               'se vendorizan para poder reproducir el orden de carga original, pero `herramientas/fragmentos-head.md` indica omitirlos '
               '(sin uso en Línea 2026 o reemplazados por `local/io-shim.js`).', '']
    with open(ruta, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lineas))


if __name__ == '__main__':
    sys.exit(main())
