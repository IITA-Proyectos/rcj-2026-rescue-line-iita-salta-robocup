#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assets-verificar.py - Verificación estática de los assets de rcj-line-offline (área assets).

Recorre los HTML, JS, CSS y templates de la app y comprueba:
  1. Que cada referencia relativa a un estático exista en disco DISTINGUIENDO MAYÚSCULAS (aunque el
     disco de Windows no las distinga): src/href/ng-src de los HTML, literales de JS con prefijos
     de estáticos (components/, images/, templates/, lang/, stylesheets/, javascripts/, sounds/,
     scoresheet_generation/, data/, local/), url() e @import de CSS (relativos al CSS).
     Las referencias dinámicas se expanden: images/tiles/{{...tileType.image}} contra
     data/tilesets.json, images/{{victimImgPath(...)}} y el prefijo lang/.
  2. Que ningún .js/.css/.json de components/ empiece con HTML (soft-404) y que las imágenes y fuentes
     de components/ tengan los bytes mágicos correctos.
  3. Que no queden rutas absolutas de estáticos ("/components/...", "/images/...", etc.) en los
     archivos copiados del CMS ni en las páginas/JS propios ("/api/..." está permitido).
  4. Que los JSON de lang/ y data/ sean válidos.

Se puede re-ejecutar cuando existan las páginas: toma todo lo que haya en la app.
Uso: python tests/assets-verificar.py [--app <raíz>] [--json <salida.json>]
Código de salida: 0 sin errores, 1 con errores.
"""

import argparse
import json
import os
import posixpath
import re
import sys
from collections import OrderedDict

PREFIJOS = ('components', 'images', 'templates', 'lang', 'stylesheets', 'javascripts', 'sounds',
            'scoresheet_generation', 'data', 'local')
PREFIJOS_ABSOLUTOS = ('components', 'images', 'templates', 'lang', 'stylesheets', 'javascripts', 'sounds',
                      'scoresheet_generation', 'fonts', 'data', 'local')
EXT_ESTATICAS = ('.js', '.css', '.png', '.gif', '.jpg', '.jpeg', '.ico', '.svg', '.json', '.webmanifest',
                 '.html', '.mp3', '.woff', '.woff2', '.ttf')

# Omisiones documentadas en components/VERSIONES.md (referencias internas de CSS vendor que no se empaquetan).
OMISIONES = [
    (re.compile(r'^components/font-awesome-5/webfonts/fa-(solid-900|regular-400|brands-400)\.(eot|woff|ttf|svg)$'),
     'formato de respaldo de Font Awesome (solo se empaqueta woff2)'),
]

RE_BASE = re.compile(r'''<base\s+href\s*=\s*(['"])(.*?)\1''', re.I)
RE_ATRIB = re.compile(r'''\b(?:src|href|ng-src|ng-href|data-src)\s*=\s*(['"])(.*?)\1''', re.I)
RE_LITERAL = re.compile(r'''(['"`(])((?:\.\./|\./)*(?:%s)/[^'"`)\s]*)''' % '|'.join(PREFIJOS))
RE_CSS_URL = re.compile(r'''url\(\s*(['"]?)([^'")]+?)\1\s*\)''')
RE_CSS_IMPORT = re.compile(r'''@import\s+(['"])([^'"]+)\1''')
RE_ABSOLUTA = re.compile(r'''(?:['"`(=]|url\(\s*['"]?)\s*/(?:%s)/[^'"`)\s]*''' % '|'.join(PREFIJOS_ABSOLUTOS))
RE_ABS_MANIFEST = re.compile(r'''['"]/manifest\.json['"]''')
RE_COMENTARIO_CSS = re.compile(r'/\*.*?\*/', re.S)
RE_COMENTARIO_HTML = re.compile(r'<!--.*?-->', re.S)


class Verificador:
    def __init__(self, app):
        self.app = os.path.abspath(app)
        self.errores = []
        self.avisos = []
        self.omitidas = []
        self.ok = 0
        self.dinamicas = []
        self.escaneados = OrderedDict()
        self._cache = {}
        self._vistos = set()

    # ---------------- utilidades
    def listar(self, carpeta):
        if carpeta not in self._cache:
            try:
                self._cache[carpeta] = set(os.listdir(carpeta))
            except (FileNotFoundError, NotADirectoryError):
                self._cache[carpeta] = None
        return self._cache[carpeta]

    def existe_exacto(self, rel, directorio=False):
        """rel es relativa a la raíz de la app, con '/'. Compara nombres exactos componente por componente."""
        actual = self.app
        partes = [p for p in rel.split('/') if p]
        for i, p in enumerate(partes):
            nombres = self.listar(actual)
            if nombres is None or p not in nombres:
                sugerencia = None
                if nombres:
                    for n in nombres:
                        if n.lower() == p.lower():
                            sugerencia = n
                return False, sugerencia
            actual = os.path.join(actual, p)
        if directorio:
            return os.path.isdir(actual), None
        return os.path.isfile(actual), None

    def rel(self, ruta_abs):
        return os.path.relpath(ruta_abs, self.app).replace(os.sep, '/')

    @staticmethod
    def es_externa(ref):
        r = ref.strip().lower()
        return (not r or r.startswith(('http:', 'https:', 'data:', 'blob:', 'mailto:', 'javascript:', 'tel:', '#', '//', 'about:'))
                or r.startswith('/api/') or r.startswith('{{'))

    def resolver(self, base_dir_rel, ref):
        ref = ref.split('#', 1)[0].split('?', 1)[0]
        if ref.startswith('/'):
            return None
        return posixpath.normpath(posixpath.join(base_dir_rel, ref)) if base_dir_rel else posixpath.normpath(ref)

    def comprobar(self, origen, base_dir_rel, ref):
        if self.es_externa(ref):
            return
        ref_limpia = ref.split('#', 1)[0].split('?', 1)[0]
        if ref_limpia.startswith('/'):
            return  # las absolutas se informan en comprobar_absolutas
        clave = (origen, ref_limpia)
        if clave in self._vistos:
            return
        self._vistos.add(clave)
        destino = self.resolver(base_dir_rel, ref_limpia)
        if destino.startswith('..'):
            self.errores.append('%s: "%s" apunta fuera de la app' % (origen, ref))
            return
        if '{{' in ref_limpia or '${' in ref_limpia or '#{' in ref_limpia or ref_limpia.endswith('/'):
            self.dinamica(origen, destino, ref_limpia)
            return
        for patron, motivo in OMISIONES:
            if patron.match(destino):
                ok, _ = self.existe_exacto(destino)
                if not ok:
                    self.omitidas.append('%s: %s (%s)' % (origen, destino, motivo))
                    return
        ok, sugerencia = self.existe_exacto(destino)
        if ok:
            self.ok += 1
        elif sugerencia:
            self.errores.append('%s: "%s" no existe con esas mayúsculas (en disco: "%s")' % (origen, destino, sugerencia))
        else:
            self.errores.append('%s: "%s" no existe' % (origen, destino))

    def dinamica(self, origen, destino, ref):
        # Prefijo hasta la primera parte dinámica
        if ref.endswith('/'):
            carpeta = destino if destino != '.' else ''  # prefijo que se concatena: la carpeta es la ruta completa
        else:
            corte = min([i for i in (destino.find('{{'), destino.find('${'), destino.find('#{')) if i >= 0] or [len(destino)])
            prefijo = destino[:corte]
            carpeta = prefijo.rsplit('/', 1)[0] if '/' in prefijo else ''
        ok, _ = self.existe_exacto(carpeta, directorio=True) if carpeta else (True, None)
        self.dinamicas.append('%s: %s -> carpeta "%s" %s' % (origen, ref, carpeta, 'existe' if ok else 'NO EXISTE'))
        if not ok:
            self.errores.append('%s: referencia dinámica "%s" y la carpeta "%s" no existe' % (origen, ref, carpeta))

    # ---------------- escaneos
    def comprobar_absolutas(self, origen, texto, severidad):
        for n, linea in enumerate(texto.split('\n'), 1):
            for m in list(RE_ABSOLUTA.finditer(linea)) + list(RE_ABS_MANIFEST.finditer(linea)):
                msg = '%s:%d: ruta absoluta de estático "%s"' % (origen, n, m.group(0).strip())
                (self.errores if severidad == 'error' else self.avisos).append(msg)

    def escanear_html(self, ruta_abs, es_template):
        rel = self.rel(ruta_abs)
        with open(ruta_abs, 'r', encoding='utf-8', errors='replace') as f:
            texto = f.read()
        sin_coment = RE_COMENTARIO_HTML.sub('', texto)
        if es_template:
            base = ''  # los templates se insertan en páginas de la raíz
        else:
            base = posixpath.dirname(rel)
            mb = RE_BASE.search(sin_coment)
            if mb:
                base = posixpath.normpath(posixpath.join(base, mb.group(2))) if not mb.group(2).startswith(('http', '/')) else base
                if base == '.':
                    base = ''
        n_refs = 0
        for m in RE_ATRIB.finditer(sin_coment):
            valor = m.group(2)
            if self.es_externa(valor):
                continue
            limpio = valor.split('#', 1)[0].split('?', 1)[0]
            if limpio.lower().endswith(EXT_ESTATICAS) or any(limpio.startswith(p + '/') or limpio.startswith('../' + p + '/') for p in PREFIJOS):
                self.comprobar(rel, base, valor)
                n_refs += 1
        for m in RE_LITERAL.finditer(sin_coment):
            self.comprobar(rel, base, m.group(2))
            n_refs += 1
        # CSS embebido
        for m in RE_CSS_URL.finditer(sin_coment):
            self.comprobar(rel, base, m.group(2))
        self.comprobar_absolutas(rel, sin_coment, 'aviso' if rel.startswith('tests/') else 'error')
        self.escaneados[rel] = n_refs

    def escanear_js(self, ruta_abs):
        rel = self.rel(ruta_abs)
        with open(ruta_abs, 'r', encoding='utf-8', errors='replace') as f:
            texto = f.read()
        n_refs = 0
        for m in RE_LITERAL.finditer(texto):
            self.comprobar(rel, '', m.group(2))  # los JS se ejecutan en páginas de la raíz
            n_refs += 1
        self.comprobar_absolutas(rel, texto, 'aviso' if rel.startswith('tests/') else 'error')
        self.escaneados[rel] = n_refs

    def escanear_css(self, ruta_abs, vendor):
        rel = self.rel(ruta_abs)
        with open(ruta_abs, 'r', encoding='utf-8', errors='replace') as f:
            texto = RE_COMENTARIO_CSS.sub('', f.read())
        base = posixpath.dirname(rel)
        n_refs = 0
        for m in list(RE_CSS_URL.finditer(texto)) + list(RE_CSS_IMPORT.finditer(texto)):
            self.comprobar(rel, base, m.group(2))
            n_refs += 1
        if not vendor:
            self.comprobar_absolutas(rel, texto, 'error')
        self.escaneados[rel] = n_refs

    def verificar_components(self):
        base = os.path.join(self.app, 'components')
        if not os.path.isdir(base):
            self.errores.append('no existe components/')
            return
        magias = {'.png': (b'\x89PNG\r\n\x1a\n',), '.gif': (b'GIF87a', b'GIF89a'), '.woff2': (b'wOF2',), '.woff': (b'wOFF',)}
        revisados = 0
        for raiz, _d, archivos in os.walk(base):
            for n in archivos:
                ruta = os.path.join(raiz, n)
                rel = self.rel(ruta)
                ext = os.path.splitext(n)[1].lower()
                with open(ruta, 'rb') as f:
                    cabeza = f.read(4096)
                if ext in ('.js', '.css', '.json'):
                    c = cabeza.lstrip(b'\xef\xbb\xbf \t\r\n').lower()
                    if c.startswith((b'<!doctype', b'<html', b'<head', b'<body')) or b'<!doctype html' in c[:512]:
                        self.errores.append('%s: empieza con HTML (soft-404)' % rel)
                    revisados += 1
                if ext in magias and not cabeza.startswith(magias[ext]):
                    self.errores.append('%s: bytes mágicos incorrectos para %s' % (rel, ext))
        self.escaneados['(components: .js/.css/.json revisados contra HTML)'] = revisados

    def verificar_json(self):
        for carpeta in ('lang', 'data'):
            d = os.path.join(self.app, carpeta)
            if not os.path.isdir(d):
                continue
            for n in sorted(os.listdir(d)):
                if n.endswith('.json'):
                    try:
                        with open(os.path.join(d, n), 'r', encoding='utf-8') as f:
                            json.load(f)
                    except Exception as e:  # noqa
                        self.errores.append('%s/%s: JSON inválido: %s' % (carpeta, n, e))

    def verificar_expansiones(self):
        """Referencias dinámicas conocidas del CMS, expandidas a archivos concretos."""
        ts = os.path.join(self.app, 'data', 'tilesets.json')
        if os.path.exists(ts):
            with open(ts, 'r', encoding='utf-8') as f:
                tilesets = json.load(f)
            imagenes = sorted({t['tileType']['image'] for s in tilesets for t in s.get('tiles', [])
                               if isinstance(t.get('tileType'), dict) and t['tileType'].get('image')})
            faltan = [i for i in imagenes if not self.existe_exacto('images/tiles/' + i)[0]]
            for extra in ('ev-entrance.png', 'ev-exit.png', 'tile-0.png'):
                if not self.existe_exacto('images/tiles/' + extra)[0]:
                    faltan.append(extra)
            if faltan:
                self.errores.append('images/tiles: faltan imágenes del tileset o fijas: %s' % ', '.join(faltan))
            else:
                self.ok += len(imagenes) + 3
            self.escaneados['(expansión images/tiles/{{tileType.image}} desde data/tilesets.json)'] = len(imagenes) + 3
        for concreto in ('images/liveVictim.png', 'images/deadVictim.png', 'images/rescueKit.png',
                         'lang/en.json', 'lang/ja.json', 'lang/es.json'):
            ok, sug = self.existe_exacto(concreto)
            if ok:
                self.ok += 1
            else:
                self.errores.append('expansión dinámica: falta "%s"%s' % (concreto, ' (en disco: %s)' % sug if sug else ''))
        for n in ('click.mp3', 'info.mp3', 'error.mp3', 'timeup.mp3'):
            if not self.existe_exacto('sounds/' + n)[0]:
                self.errores.append('falta sounds/%s' % n)

    def correr(self):
        self.verificar_components()
        self.verificar_json()
        self.verificar_expansiones()
        for raiz, dirs, archivos in os.walk(self.app):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__'))
            rel_raiz = self.rel(raiz)
            en_components = rel_raiz == 'components' or rel_raiz.startswith('components/')
            for n in sorted(archivos):
                ruta = os.path.join(raiz, n)
                ext = os.path.splitext(n)[1].lower()
                if en_components:
                    if ext == '.css':
                        self.escanear_css(ruta, vendor=True)
                    continue
                if ext == '.html':
                    self.escanear_html(ruta, es_template=rel_raiz == 'templates' or rel_raiz.startswith('templates/'))
                elif ext == '.js':
                    self.escanear_js(ruta)
                elif ext == '.css':
                    self.escanear_css(ruta, vendor=False)
        return not self.errores


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    app_def = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument('--app', default=app_def)
    ap.add_argument('--json', help='escribir el resultado en este archivo JSON')
    ap.add_argument('--detalle', action='store_true', help='listar archivos escaneados y referencias dinámicas')
    args = ap.parse_args()
    v = Verificador(args.app)
    exito = v.correr()
    print('assets-verificar.py sobre %s' % v.app)
    print('  Archivos escaneados: %d' % len(v.escaneados))
    print('  Referencias verificadas OK: %d' % v.ok)
    print('  Referencias dinámicas: %d' % len(v.dinamicas))
    print('  Omisiones documentadas: %d' % len(v.omitidas))
    if args.detalle:
        for k, n in v.escaneados.items():
            print('    %-80s %d refs' % (k, n))
        for d in v.dinamicas:
            print('    dinámica: ' + d)
        for o in v.omitidas:
            print('    omitida: ' + o)
    for a in v.avisos:
        print('  AVISO: ' + a)
    for e in v.errores:
        print('  ERROR: ' + e)
    print('RESULTADO: %s (%d errores, %d avisos)' % ('OK' if exito else 'FALLA', len(v.errores), len(v.avisos)))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump({'ok': exito, 'errores': v.errores, 'avisos': v.avisos, 'omitidas': v.omitidas,
                       'dinamicas': v.dinamicas, 'referencias_ok': v.ok, 'escaneados': v.escaneados},
                      f, ensure_ascii=False, indent=2)
    return 0 if exito else 1


if __name__ == '__main__':
    sys.exit(main())
