#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
importar_cms.py - Importador reproducible de assets del CMS oficial (rcj-rescue-cms) para
rcj-line-offline.

Qué hace, en orden:
  1. Copia con `git show <commit>:<ruta>` (bytes del blob, sin CRLF del working tree) todo lo que
     usan las páginas de Rescue Line 2026 que se portan: JS de cada página, pathFinder.js,
     lvl-uuid.js, translate_config.js, CSS, templates, imágenes (incluidas las dinámicas:
     images/tiles/*, images/mapimage/*, víctimas, bonus, favicons...), sounds/*,
     scoresheet_generation/line/*, lang/en.json y lang/ja.json, y el LICENSE del CMS.
  2. Aplica la regla 3a de ESPEC-CONSTRUCCION: rutas absolutas de estáticos -> relativas
     (NUNCA toca "/api/..."), con reemplazos precisos que se listan uno por uno.
  3. Aplica la regla 3c sobre javascripts/translate_config.js (registra 'es' y lo deja como
     idioma preferido cuando no hay elección guardada; en y ja siguen disponibles).
  4. Neutraliza el @import de stylesheets/fonts.css en common/modern_layout.css (ESPEC §1: las
     fuentes Outfit/Inter del CMS son HTML roto y no se empaquetan).
  5. Opcional (--es-keys): genera lang/es.json = en.json fusionado (deep merge) con uno o más
     JSON de claves en español (el último pisa).
  6. Opcional (--tilesets): copia byte a byte el JSON vivo de tilesets a data/tilesets.json.
  7. Verifica cobertura: busca referencias a estáticos en los pug/JS/templates/CSS de las páginas
     y avisa si alguna no quedó cubierta por el inventario ni por una omisión documentada.
  8. Escribe el listado de reemplazos en cambios/assets.md (bloque automático entre marcadores).

Idempotencia:
  - Cada salida se recalcula siempre desde el blob de git (nunca se transforma lo que ya está en
    disco), así que correrlo N veces da el mismo resultado.
  - herramientas/importar_cms.estado.json guarda el sha256 de lo último que escribió el script.
    Si un archivo del destino fue editado a mano después (por ejemplo, el agente de una página
    aplicó la regla 3b a "su" JS), NO se pisa: se informa como "protegido". Usar --forzar para
    sobrescribir igual.

Uso (python 3.11, sin dependencias externas):
  python herramientas/importar_cms.py --cms <checkout del CMS> [--commit d805502]
         [--destino <raíz de rcj-line-offline>] [--es-keys analysis/es-line-keys.json ...]
         [--tilesets live/api_maps_line_tilesets_populate_true] [--forzar] [--simular]
"""

import argparse
import hashlib
import html
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import uuid
from collections import OrderedDict

COMMIT_POR_DEFECTO = 'd805502'

# Prefijos de estáticos que la regla 3a relativiza. "/api/" queda fuera por construcción.
PREFIJOS_3A = ('components', 'images', 'templates', 'lang', 'stylesheets', 'javascripts',
               'sounds', 'scoresheet_generation')

# ---------------------------------------------------------------------------------------------
# Inventario: ruta en el repo del CMS -> motivo (quién la usa). Las rutas "public/..." se copian
# a la raíz de la app sin el prefijo "public/".
# ---------------------------------------------------------------------------------------------
INVENTARIO_JS = OrderedDict([
    ('public/javascripts/admin/mapEditor/line_2026.js', 'editor (views/admin/mapEditor/line_2026.pug:26)'),
    ('public/javascripts/judge/line_2026.js', 'juez (views/judge/line_2026.pug:10)'),
    ('public/javascripts/sign/line_2026.js', 'firma y vista (views/sign/line_2026.pug:10, views/view/line_2026.pug:10)'),
    ('public/javascripts/manual/line_2026.js', 'carga manual input/check (views/manual/*/line_2026.pug:8)'),
    ('public/javascripts/ranking/line_2026.js', 'ranking (views/ranking/line_2026.pug:12)'),
    ('public/javascripts/admin/gamesPrint/line_2026.js', 'planillas (views/admin/gamesPrint/line_2026.pug:10)'),
    ('public/javascripts/line_competition.js', 'lista de corridas (views/line_competition.pug:12)'),
    ('public/javascripts/admin/games.js', 'admin de corridas (views/admin/games.pug:15)'),
    ('public/javascripts/admin/maps.js', 'lista admin de mapas (views/admin/maps.pug:11, routes/admin.js:495-504)'),
    ('public/javascripts/pathFinder.js', 'editor (views/admin/mapEditor/line_2026.pug:18) - PFc verbatim'),
    ('public/javascripts/lvl-uuid.js', 'editor (views/admin/mapEditor/line_2026.pug:17)'),
    ('public/javascripts/translate_config.js', 'todas (head.pug:6 y pugs standalone)'),
    ('public/javascripts/deflate.js', 'juez (views/judge/line_2026.pug:12) - cargado sin uso (06 §3.2)'),
    ('public/javascripts/makeQR.js', 'juez (views/judge/line_2026.pug:14) - cargado sin uso (06 §3.2)'),
])

INVENTARIO_CSS = OrderedDict([
    ('public/stylesheets/style.css', 'todas (common_component.pug:23)'),
    ('public/stylesheets/navbar_premium.css', 'todas (common_component.pug:25)'),
    ('public/stylesheets/fredrik.css', 'editor, juez, firma, vista, manual input'),
    ('public/stylesheets/admin/mapEditor/line_modern.css', 'editor (line_2026.pug:32)'),
    ('public/stylesheets/admin/mapEditor/maze_modern.css', 'editor (line_2026.pug:31)'),
    ('public/stylesheets/common/modern_layout.css', 'páginas modern_layout (modern_layout.pug:6)'),
    ('public/stylesheets/common/modern_components.css', 'páginas modern_layout (modern_layout.pug:7)'),
    ('public/stylesheets/common/modern_list.css', 'páginas modern_layout (modern_layout.pug:8)'),
    ('public/stylesheets/common/modern_modal.css', 'páginas modern_layout (modern_layout.pug:9)'),
    ('public/stylesheets/admin/live_ranking.css', 'planillas (gamesPrint/line_2026.pug:11)'),
])

INVENTARIO_TEMPLATES = OrderedDict([
    ('public/templates/tile.html', 'editor/juez/firma/vista (templateUrl)'),
    ('public/templates/line_editor_modal.html', 'editor (templateUrl con ?gs, line_2026.js:1121)'),
    ('public/templates/line_judge_modal.html', 'juez (templateUrl, judge/line_2026.js:673)'),
    ('public/templates/line_view_modal.html', 'firma y vista (templateUrl, sign/line_2026.js:478)'),
])

INVENTARIO_IMAGENES = OrderedDict([
    ('public/images/logo.png', 'navbar.pug:5, login_modal.pug:9; planilla PDF (scoreSheetPDFLineRules/2026.js:68)'),
    ('public/images/liveVictim.png', 'juez, vista/firma, manual, ranking/planillas (victimImgPath)'),
    ('public/images/deadVictim.png', 'juez, vista/firma, manual, ranking/planillas (victimImgPath)'),
    ('public/images/rescueKit.png', 'ranking/line_2026.js:161, gamesPrint/line_2026.js:412 (victimImgPath)'),
    ('public/images/rescuekit.png', 'misma imagen en minúsculas (mismo blob que rescueKit.png)'),
    ('public/images/evacZone/red_lv2.png', 'juez:201, view/common:186, manual'),
    ('public/images/evacZone/green_lv2.png', 'juez:210, view/common:195, manual'),
    ('public/images/evacZone/red_lv2_a.png', 'juez:185, manual input:858'),
    ('public/images/evacZone/green_lv2_a.png', 'juez:188, manual input:855'),
    ('public/images/line_bonus.png', 'juez:224, view/common:101, manual'),
    ('public/images/nl_bonus.png', 'view/common:102 (league LineNL)'),
    ('public/images/next-robot-done.png', 'line_judge_modal.html, line_view_modal.html'),
    ('public/images/next-robot-undone.png', 'line_judge_modal.html, line_view_modal.html'),
    ('public/images/loader2.gif', 'ranking/include:3, gamesPrint:192, line_competition:128, games:823'),
    ('public/images/unknownVictim.png', 'gamesPrint:231'),
    ('public/images/greenVictim.png', 'gamesPrint:234'),
    ('public/images/blackVictim.png', 'gamesPrint:237'),
    ('public/images/noLogo.png', 'logo por defecto de competencia (routes/api/competitions.js:105)'),
    ('public/images/NoImage.png', 'placeholder de foto/logo (routes/api/competitions.js:47, document.js:1558)'),
    ('public/images/favicon.ico', 'favicon raíz que pide el navegador'),
    ('public/images/favicon-16.ico', 'head.pug:13'),
    ('public/images/favicon-32.ico', 'head.pug:14'),
    ('public/images/favicon-96.ico', 'head.pug:15'),
    ('public/images/apple-touch-icon-144.png', 'head.pug:16'),
    ('public/images/apple-touch-icon-152.png', 'head.pug:17'),
    ('public/images/apple-touch-icon-180.png', 'head.pug:18'),
    ('public/images/favicon-196.png', 'head.pug:19'),
    ('public/images/favicon-32.png', 'head.pug:20'),
    ('public/images/favicon-128.png', 'head.pug:21'),
])

# Globs (prefijo de directorio en el repo -> motivo). Se expanden con git ls-tree.
INVENTARIO_GLOBS = OrderedDict([
    ('public/images/tiles/', 'baldosas dinámicas images/tiles/{{tileType.image}} + ev-entrance/ev-exit (tile.html, modales, editor, lineSSR)'),
    ('public/images/mapimage/', 'overlays del PNG del mapa (helper/lineSSR/2026.js:12)'),
    ('public/sounds/', 'getAudioBuffer de juez/firma/manual'),
    ('scoresheet_generation/line/', 'planilla PDF (helper/scoreSheetPDFLineRules/2026.js)'),
])

INVENTARIO_OTROS = OrderedDict([
    ('public/lang/en.json', 'angular-translate (translate_config.js prefix lang/)'),
    ('public/lang/ja.json', 'angular-translate (translate_config.js prefix lang/)'),
    ('LICENSE', 'licencia MIT del CMS -> LICENSE-rcj-rescue-cms.txt'),
])

# Colisiones que solo difieren en mayúsculas: nombre preferido (el que referencia el código).
PREFERIDOS_MAYUSCULAS = {
    'images/rescuekit.png': 'images/rescueKit.png',
}

# Referencias a estáticos que aparecen en los pug/JS y que se omiten a propósito.
OMISIONES_DOCUMENTADAS = OrderedDict([
    ('stylesheets/fonts.css', 'ESPEC §1: fuentes Outfit/Inter rotas en el origen; no se enlaza ni se copia'),
    ('stylesheets/stg.css', 'solo si ENVIRONMENT == "STG" (common_component.pug:29-30)'),
    ('manifest.json', 'lo genera el área docs como manifest.webmanifest'),
])

# Referencias dinámicas que no son un glob de directorio: prefijo -> archivos concretos que puede pedir.
DINAMICAS_RESUELTAS = OrderedDict([
    ('images/{{victimImgPath(victim', ['images/liveVictim.png', 'images/deadVictim.png', 'images/rescueKit.png']),
    ('lang/', ['lang/en.json', 'lang/ja.json', 'lang/es.json']),
])

# Pug/archivos del CMS donde se busca cobertura de referencias (además del inventario JS/CSS/templates).
PUGS_COBERTURA = [
    'views/includes/common_component.pug', 'views/includes/head.pug', 'views/includes/layout.pug',
    'views/includes/modern_layout.pug', 'views/includes/navbar.pug', 'views/includes/footer.pug',
    'views/includes/login_modal.pug', 'views/includes/language_modal.pug',
    'views/admin/mapEditor/line_2026.pug', 'views/judge/line_2026.pug', 'views/sign/line_2026.pug',
    'views/view/line_2026.pug', 'views/view/common/line_2026.pug',
    'views/manual/input/line_2026.pug', 'views/manual/check/line_2026.pug',
    'views/ranking/line_2026.pug', 'views/ranking/include/line_2026.pug',
    'views/admin/gamesPrint/line_2026.pug', 'views/line_competition.pug',
    'views/admin/games.pug', 'views/admin/maps.pug',
]

MARCA_INICIO = '<!-- AUTO:importar_cms INICIO (no editar a mano: lo regenera herramientas/importar_cms.py) -->'
MARCA_FIN = '<!-- AUTO:importar_cms FIN -->'

RE_3A_JS_HTML = re.compile(r'''(?P<q>['"`])/(?P<p>%s)/''' % '|'.join(PREFIJOS_3A))
RE_3A_CSS_URL = re.compile(
    r'''url\(\s*(?P<q>['"]?)/(?P<ruta>(?:%s)/[^'")\s]*)(?P=q)\s*\)''' % '|'.join(PREFIJOS_3A))
RE_IMPORT_FONTS = re.compile(r'''@import\s+url\(\s*['"]?/stylesheets/fonts\.css['"]?\s*\)\s*;''')
COMENTARIO_FONTS = ('/* [rcj-line-offline] se omite el @import de stylesheets/fonts.css: las fuentes '
                    'Outfit/Inter del CMS son HTML (ESPEC §1); el sitio vivo ya dibuja con sans-serif */')

TRANSLATE_ANTES = """        .registerAvailableLanguageKeys(['en', 'ja'], {
            'en_*': 'en',
            'ja_*': 'ja',
            '*': 'en'
        })
        .determinePreferredLanguage()
"""
TRANSLATE_DESPUES = """        .registerAvailableLanguageKeys(['en', 'ja', 'es'], {
            'en_*': 'en',
            'ja_*': 'ja',
            'es_*': 'es',
            '*': 'es'
        })
        .determinePreferredLanguage()
        // [rcj-line-offline] regla 3c: español como idioma preferido cuando no hay elección guardada.
        // Si el usuario ya eligió un idioma (localStorage NG_TRANSLATE_LANG_KEY) esa elección gana.
        .preferredLanguage('es')
"""

RE_REF_COBERTURA = re.compile(
    r'''(?P<q>['"`(=])/(?P<ruta>(?:components|images|templates|lang|stylesheets|javascripts|sounds|fonts|scoresheet_generation)/[^'"`)\s?#]*|manifest\.json)''')


# ---------------------------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------------------------
def sha256(datos):
    return hashlib.sha256(datos).hexdigest()


class Git:
    def __init__(self, cms, commit):
        self.cms = cms
        self.commit = commit
        salida = self._run(['ls-tree', '-r', '-l', '--full-tree', commit])
        self.arbol = {}
        for linea in salida.decode('utf-8').splitlines():
            meta, ruta = linea.split('\t', 1)
            _modo, tipo, sha_blob, tam = meta.split()
            if tipo == 'blob':
                self.arbol[ruta] = (sha_blob, int(tam))

    def _run(self, args):
        r = subprocess.run(['git', '-C', self.cms] + args, capture_output=True)
        if r.returncode != 0:
            raise SystemExit('ERROR git %s: %s' % (' '.join(args), r.stderr.decode('utf-8', 'replace')))
        return r.stdout

    def show(self, ruta):
        if ruta not in self.arbol:
            raise SystemExit('ERROR: %s no existe en %s' % (ruta, self.commit))
        datos = self._run(['show', '%s:%s' % (self.commit, ruta)])
        _sha_blob, tam = self.arbol[ruta]
        if len(datos) != tam:
            raise SystemExit('ERROR: %s: git show dio %d bytes y el blob mide %d' % (ruta, len(datos), tam))
        # Verificación extra: el sha1 de git del contenido tiene que coincidir con el del blob.
        sha_git = hashlib.sha1(b'blob %d\0' % len(datos) + datos).hexdigest()
        if sha_git != _sha_blob:
            raise SystemExit('ERROR: %s: el contenido no coincide con el blob %s' % (ruta, _sha_blob))
        return datos

    def listar(self, prefijo):
        return sorted(r for r in self.arbol if r.startswith(prefijo))


def destino_de(ruta_cms):
    if ruta_cms == 'LICENSE':
        return 'LICENSE-rcj-rescue-cms.txt'
    if ruta_cms.startswith('public/'):
        return ruta_cms[len('public/'):]
    return ruta_cms


def fs_distingue_mayusculas(directorio):
    base = directorio if os.path.isdir(directorio) else tempfile.gettempdir()
    nombre = '.PruebaMayus-%s.tmp' % uuid.uuid4().hex
    ruta = os.path.join(base, nombre)
    with open(ruta, 'wb'):
        pass
    try:
        return not os.path.exists(os.path.join(base, nombre.lower()))
    finally:
        os.remove(ruta)


def nombre_en_disco(ruta_abs):
    """Nombre real (con mayúsculas) del último componente, o None si no existe."""
    carpeta, nombre = os.path.split(ruta_abs)
    if not os.path.isdir(carpeta):
        return None
    for n in os.listdir(carpeta):
        if n.lower() == nombre.lower():
            return n
    return None


# ---------------------------------------------------------------------------------------------
# Transformaciones (reglas 3a y 3c + fuentes)
# ---------------------------------------------------------------------------------------------
def fragmento(linea, inicio, fin, margen=45):
    a = max(0, inicio - margen)
    b = min(len(linea), fin + margen)
    return ('…' if a > 0 else '') + linea[a:b].strip() + ('…' if b < len(linea) else '')


def regla_3a_js_html(texto):
    cambios = []
    lineas = texto.split('\n')
    for i, linea in enumerate(lineas):
        nueva = linea
        partes = []
        for m in RE_3A_JS_HTML.finditer(linea):
            partes.append((m.start(), m.end()))
        if partes:
            nueva = RE_3A_JS_HTML.sub(lambda m: m.group('q') + m.group('p') + '/', linea)
            ini, fin = partes[0][0], partes[-1][1]
            cambios.append({
                'linea': i + 1,
                'antes': fragmento(linea, ini, fin),
                'despues': fragmento(nueva, ini, fin - len(partes)),
                'regla': '3a',
                'motivo': 'ruta absoluta de estático -> relativa (%d ocurrencia/s)' % len(partes),
            })
            lineas[i] = nueva
    return '\n'.join(lineas), cambios


def regla_3a_css(texto, ruta_destino_css):
    cambios = []
    carpeta_css = posixpath.dirname(ruta_destino_css)
    lineas = texto.split('\n')
    for i, linea in enumerate(lineas):
        m_imp = RE_IMPORT_FONTS.search(linea)
        if m_imp:
            nueva = linea[:m_imp.start()] + COMENTARIO_FONTS + linea[m_imp.end():]
            cambios.append({
                'linea': i + 1, 'antes': linea.strip(), 'despues': nueva.strip(), 'regla': 'ESPEC §1',
                'motivo': 'no enlazar stylesheets/fonts.css (fuentes Outfit/Inter rotas en el origen; evita 404)',
            })
            lineas[i] = nueva
            linea = nueva
        encontrados = list(RE_3A_CSS_URL.finditer(linea))
        if encontrados:
            def reemplazo(m):
                relativa = posixpath.relpath(m.group('ruta'), carpeta_css or '.')
                return 'url(%s%s%s)' % (m.group('q'), relativa, m.group('q'))
            nueva = RE_3A_CSS_URL.sub(reemplazo, linea)
            cambios.append({
                'linea': i + 1, 'antes': linea.strip(), 'despues': nueva.strip(), 'regla': '3a',
                'motivo': 'url() absoluta -> relativa al CSS (%d ocurrencia/s)' % len(encontrados),
            })
            lineas[i] = nueva
    return '\n'.join(lineas), cambios


def regla_3c_translate(texto):
    if TRANSLATE_ANTES not in texto:
        raise SystemExit('ERROR: translate_config.js no tiene el bloque esperado; revisar la regla 3c')
    idx = texto.index(TRANSLATE_ANTES)
    linea = texto[:idx].count('\n') + 1
    nuevo = texto.replace(TRANSLATE_ANTES, TRANSLATE_DESPUES, 1)
    return nuevo, [{
        'linea': linea,
        'antes': ' '.join(l.strip() for l in TRANSLATE_ANTES.strip().split('\n')),
        'despues': ' '.join(l.strip() for l in TRANSLATE_DESPUES.strip().split('\n')),
        'regla': '3c',
        'motivo': "registrar 'es' (alias es_* y comodín), mantener en/ja y dejar 'es' como preferido sin elección guardada",
    }]


def transformar(ruta_cms, destino, datos):
    ext = posixpath.splitext(destino)[1].lower()
    cambios = []
    if ext in ('.js', '.html'):
        texto = datos.decode('utf-8')
        texto, cambios = regla_3a_js_html(texto)
        if destino == 'javascripts/translate_config.js':
            texto, c3 = regla_3c_translate(texto)
            cambios += c3
        return texto.encode('utf-8'), cambios
    if ext == '.css':
        texto = datos.decode('utf-8')
        texto, cambios = regla_3a_css(texto, destino)
        return texto.encode('utf-8'), cambios
    return datos, cambios


# ---------------------------------------------------------------------------------------------
# lang/es.json
# ---------------------------------------------------------------------------------------------
def cargar_json_ordenado(datos, origen, avisos):
    def hook(pares):
        d = OrderedDict()
        for k, v in pares:
            if k in d:
                avisos.append('%s: clave duplicada "%s" (gana el último valor, igual que JSON.parse)' % (origen, k))
            d[k] = v
        return d
    return json.loads(datos.decode('utf-8'), object_pairs_hook=hook)


def contar_hojas(obj):
    if isinstance(obj, dict):
        return sum(contar_hojas(v) for v in obj.values())
    return 1


def fusionar(base, extra, camino, stats):
    for k, v in extra.items():
        ruta = camino + [k]
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            fusionar(base[k], v, ruta, stats)
        else:
            if k in base:
                if isinstance(base[k], dict) != isinstance(v, dict):
                    stats['conflictos_tipo'].append('.'.join(ruta))
                stats['pisadas'] += contar_hojas(v)
            else:
                stats['agregadas'].append('.'.join(ruta))
            base[k] = v


# ---------------------------------------------------------------------------------------------
# Escritura idempotente con protección de ediciones locales
# ---------------------------------------------------------------------------------------------
class Escritor:
    def __init__(self, destino_app, estado_path, forzar, simular, distingue):
        self.app = destino_app
        self.estado_path = estado_path
        self.forzar = forzar
        self.simular = simular
        self.distingue = distingue
        self.estado = {}
        if os.path.exists(estado_path):
            with open(estado_path, 'r', encoding='utf-8') as f:
                self.estado = json.load(f).get('archivos', {})
        self.resultados = OrderedDict()  # destino -> estado

    def escribir(self, destino, datos):
        ruta_abs = os.path.join(self.app, *destino.split('/'))
        nuevo_sha = sha256(datos)
        real = nombre_en_disco(ruta_abs)
        nombre = os.path.basename(ruta_abs)
        existe = real is not None
        if existe and real != nombre:
            # Mismo archivo con otra grafía: renombrar para que el nombre en disco sea el pedido.
            if not self.simular:
                carpeta = os.path.dirname(ruta_abs)
                tmp = os.path.join(carpeta, '.renombrando-%s' % uuid.uuid4().hex)
                os.rename(os.path.join(carpeta, real), tmp)
                os.rename(tmp, ruta_abs)
            self.resultados.setdefault(destino + ' (renombrado desde %s)' % real, 'renombrado')
        if existe:
            with open(ruta_abs, 'rb') as f:
                actual = f.read()
            actual_sha = sha256(actual)
            if actual_sha == nuevo_sha:
                self.estado[destino] = nuevo_sha
                self.resultados[destino] = 'sin cambios'
                return
            if not self.forzar and self.estado.get(destino) != actual_sha:
                self.resultados[destino] = 'PROTEGIDO (editado localmente; no se pisa, usar --forzar)'
                return
            estado_txt = 'actualizado'
        else:
            estado_txt = 'creado'
        if not self.simular:
            os.makedirs(os.path.dirname(ruta_abs), exist_ok=True)
            tmp = ruta_abs + '.tmp-importar'
            with open(tmp, 'wb') as f:
                f.write(datos)
            os.replace(tmp, ruta_abs)
        self.estado[destino] = nuevo_sha
        self.resultados[destino] = estado_txt

    def guardar_estado(self, commit):
        if self.simular:
            return
        os.makedirs(os.path.dirname(self.estado_path), exist_ok=True)
        with open(self.estado_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'commit': commit, 'archivos': OrderedDict(sorted(self.estado.items()))},
                      f, ensure_ascii=False, indent=2)
            f.write('\n')


# ---------------------------------------------------------------------------------------------
# Cobertura de referencias
# ---------------------------------------------------------------------------------------------
def verificar_cobertura(git, destinos_inventario, globs_destino):
    archivos = list(PUGS_COBERTURA) + list(INVENTARIO_JS) + list(INVENTARIO_CSS) + list(INVENTARIO_TEMPLATES)
    cubiertas, dinamicas, vendor, omitidas, faltantes = [], [], set(), [], []
    minus = {d.lower() for d in destinos_inventario}
    for ruta in archivos:
        texto = git.show(ruta).decode('utf-8', 'replace')
        for n, linea in enumerate(texto.split('\n'), 1):
            for m in RE_REF_COBERTURA.finditer(linea):
                ref = m.group('ruta')
                donde = '%s:%d' % (ruta, n)
                if ref.startswith('components/'):
                    vendor.add(ref)
                    continue
                if '{{' in ref or '#{' in ref or '${' in ref or ref.endswith('/'):
                    if ref in DINAMICAS_RESUELTAS:
                        concretos = DINAMICAS_RESUELTAS[ref]
                        sin = [c for c in concretos if c not in destinos_inventario]
                        dinamicas.append((donde, ref, 'resuelta: ' + ', '.join(concretos) + (' | FALTAN: ' + ', '.join(sin) if sin else '')))
                        if sin:
                            faltantes.append((donde, ref + ' -> ' + ', '.join(sin)))
                        continue
                    ok = any(ref.startswith(g) for g in globs_destino)
                    dinamicas.append((donde, ref, 'glob' if ok else 'SIN GLOB'))
                    if not ok:
                        faltantes.append((donde, ref))
                    continue
                if ref in OMISIONES_DOCUMENTADAS:
                    omitidas.append((donde, ref, OMISIONES_DOCUMENTADAS[ref]))
                    continue
                if ref in destinos_inventario:
                    cubiertas.append((donde, ref))
                elif ref.lower() in minus:
                    cubiertas.append((donde, ref + ' (difiere en mayúsculas)'))
                    faltantes.append((donde, ref + ' (solo existe con otras mayúsculas)'))
                else:
                    faltantes.append((donde, ref))
    return cubiertas, dinamicas, sorted(vendor), omitidas, faltantes


# ---------------------------------------------------------------------------------------------
# cambios/assets.md
# ---------------------------------------------------------------------------------------------
def celda(texto):
    return '<code>%s</code>' % html.escape(texto).replace('|', '&#124;')


def bloque_markdown(commit, todos_cambios, resumen_es, resumen_tilesets, protegidos):
    out = [MARCA_INICIO, '',
           '### Reemplazos aplicados por `herramientas/importar_cms.py` (commit `%s`)' % commit, '',
           'Generado automáticamente. Cada fila es una línea de un archivo copiado del CMS; "antes" es el '
           'blob de git y "después" lo que queda en la app.', '',
           '| Archivo:línea | Regla | Antes | Después | Motivo |', '|---|---|---|---|---|']
    for destino, cambios in todos_cambios:
        for c in cambios:
            out.append('| `%s:%d` | %s | %s | %s | %s |' % (
                destino, c['linea'], c['regla'], celda(c['antes']), celda(c['despues']), c['motivo']))
    total = sum(len(c) for _, c in todos_cambios)
    out += ['', 'Total de líneas modificadas: **%d**.' % total, '']
    if protegidos:
        out += ['Archivos protegidos (editados por otro agente después de la copia; el importador no los pisó):', '']
        out += ['- `%s`' % p for p in protegidos]
        out.append('')
    if resumen_es:
        out += ['### lang/es.json', ''] + ['- %s' % l for l in resumen_es] + ['']
    if resumen_tilesets:
        out += ['### data/tilesets.json', ''] + ['- %s' % l for l in resumen_tilesets] + ['']
    out.append(MARCA_FIN)
    return '\n'.join(out)


def actualizar_cambios_md(ruta, bloque, simular):
    if simular:
        return
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
        if MARCA_INICIO in contenido and MARCA_FIN in contenido:
            a = contenido.index(MARCA_INICIO)
            b = contenido.index(MARCA_FIN) + len(MARCA_FIN)
            contenido = contenido[:a] + bloque + contenido[b:]
        else:
            contenido = contenido.rstrip('\n') + '\n\n' + bloque + '\n'
    else:
        contenido = '# Cambios del área assets respecto del CMS\n\n' + bloque + '\n'
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8', newline='\n') as f:
        f.write(contenido)


# ---------------------------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------------------------
def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    app_por_defecto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description='Importa assets del CMS oficial para rcj-line-offline.')
    ap.add_argument('--cms', required=True, help='checkout de robocup-junior/rcj-rescue-cms')
    ap.add_argument('--commit', default=COMMIT_POR_DEFECTO)
    ap.add_argument('--destino', default=app_por_defecto, help='raíz de rcj-line-offline')
    ap.add_argument('--es-keys', action='append', default=[],
                    help='JSON de claves en español a fusionar sobre en.json (repetible; el último pisa)')
    ap.add_argument('--tilesets', help='JSON vivo de GET /api/maps/line/tilesets?populate=true')
    ap.add_argument('--forzar', action='store_true', help='sobrescribir aunque el archivo esté editado localmente')
    ap.add_argument('--simular', action='store_true', help='no escribir nada, solo informar')
    args = ap.parse_args()

    app = os.path.abspath(args.destino)
    git = Git(args.cms, args.commit)
    distingue = fs_distingue_mayusculas(app)
    escritor = Escritor(app, os.path.join(app, 'herramientas', 'importar_cms.estado.json'),
                        args.forzar, args.simular, distingue)

    print('=' * 100)
    print('importar_cms.py - CMS %s @ %s -> %s%s' % (args.cms, args.commit, app, ' [SIMULACIÓN]' if args.simular else ''))
    print('Sistema de archivos del destino distingue mayúsculas: %s' % ('sí' if distingue else 'no'))
    print('=' * 100)

    # 1. Armar la lista completa (ruta cms -> motivo)
    fuentes = OrderedDict()
    for tabla in (INVENTARIO_JS, INVENTARIO_CSS, INVENTARIO_TEMPLATES, INVENTARIO_IMAGENES):
        fuentes.update(tabla)
    globs_destino = []
    for prefijo, motivo in INVENTARIO_GLOBS.items():
        lista = git.listar(prefijo)
        if not lista:
            raise SystemExit('ERROR: el glob %s no tiene archivos en %s' % (prefijo, args.commit))
        for r in lista:
            fuentes[r] = motivo
        globs_destino.append(destino_de(prefijo))
    fuentes.update(INVENTARIO_OTROS)

    # Colisiones por mayúsculas
    alias_no_materializables = []
    destinos = OrderedDict()
    for ruta_cms, motivo in fuentes.items():
        d = destino_de(ruta_cms)
        destinos[d] = (ruta_cms, motivo)
    if not distingue:
        for d in list(destinos):
            preferido = PREFERIDOS_MAYUSCULAS.get(d)
            if preferido and preferido in destinos:
                datos_a = git.show(destinos[d][0])
                datos_b = git.show(destinos[preferido][0])
                if sha256(datos_a) != sha256(datos_b):
                    raise SystemExit('ERROR: %s y %s difieren y el disco no distingue mayúsculas' % (d, preferido))
                alias_no_materializables.append((d, preferido))
                del destinos[d]

    # 2. Copiar + transformar
    todos_cambios = []
    tamanio_total = 0
    for d, (ruta_cms, motivo) in destinos.items():
        datos = git.show(ruta_cms)
        salida, cambios = transformar(ruta_cms, d, datos)
        tamanio_total += len(salida)
        escritor.escribir(d, salida)
        if cambios:
            todos_cambios.append((d, cambios))

    print('\n[1] Copia desde git show (%d archivos, %.1f KB)' % (len(destinos), tamanio_total / 1024))
    conteo = {}
    for d, est in escritor.resultados.items():
        clave = 'protegido' if est.startswith('PROTEGIDO') else est
        conteo[clave] = conteo.get(clave, 0) + 1
        if not d.startswith('images/tiles/') or est != 'sin cambios':
            print('    %-60s %s' % (d, est))
    print('    (baldosas images/tiles/* sin cambios no se listan una por una)')
    print('    Resumen: ' + ', '.join('%s=%d' % kv for kv in sorted(conteo.items())))
    for alias, preferido in alias_no_materializables:
        print('    AVISO mayúsculas: %s es el mismo blob que %s; en este disco solo existe %s '
              '(el código referencia %s).' % (alias, preferido, preferido, preferido))

    print('\n[2] Reglas 3a / 3c / fuentes (%d líneas modificadas)' % sum(len(c) for _, c in todos_cambios))
    for d, cambios in todos_cambios:
        for c in cambios:
            print('    %s:%d [%s]' % (d, c['linea'], c['regla']))
            print('        antes:   %s' % c['antes'])
            print('        después: %s' % c['despues'])

    # Seguridad: ningún '/api/' fue tocado (comparación de conteos antes/después).
    for d, (ruta_cms, _m) in destinos.items():
        if posixpath.splitext(d)[1] in ('.js', '.html', '.css'):
            antes = git.show(ruta_cms).count(b'/api/')
            ruta_abs = os.path.join(app, *d.split('/'))
            if os.path.exists(ruta_abs) and escritor.resultados.get(d, '').startswith(('creado', 'actualizado', 'sin cambios')):
                with open(ruta_abs, 'rb') as f:
                    despues = f.read().count(b'/api/')
                if antes != despues:
                    raise SystemExit('ERROR: cambió la cantidad de "/api/" en %s (%d -> %d)' % (d, antes, despues))
    print('    Control: la cantidad de "/api/" es idéntica antes y después en todos los JS/HTML/CSS copiados.')

    print('\n[3] Cobertura de referencias en pugs/JS/templates/CSS del CMS')
    conocidos = set(destinos) | {a for a, _ in alias_no_materializables}
    if args.es_keys:
        conocidos.add('lang/es.json')
    cubiertas, dinamicas, vendor, omitidas, faltantes = verificar_cobertura(git, conocidos, globs_destino)
    print('    Referencias estáticas cubiertas por el inventario: %d' % len(cubiertas))
    print('    Referencias dinámicas: %d' % len(dinamicas))
    for donde, ref, est in dinamicas:
        print('        %-55s %-45s %s' % (donde, ref, est))
    print('    Omisiones documentadas: %d' % len(omitidas))
    for donde, ref, motivo in omitidas:
        print('        %-55s %-30s %s' % (donde, ref, motivo))
    print('    Rutas de components/ (las cubre herramientas/vendorizar.py): %d distintas' % len(vendor))
    if faltantes:
        print('    AVISO: referencias NO cubiertas:')
        for donde, ref in faltantes:
            print('        %s -> %s' % (donde, ref))
    else:
        print('    Sin referencias faltantes.')

    # 4. es.json
    resumen_es = []
    if args.es_keys:
        avisos = []
        en = cargar_json_ordenado(git.show('public/lang/en.json'), 'en.json', avisos)
        hojas_en = contar_hojas(en)
        stats = {'pisadas': 0, 'agregadas': [], 'conflictos_tipo': []}
        hojas_es = 0
        for archivo in args.es_keys:
            with open(archivo, 'rb') as f:
                extra = cargar_json_ordenado(f.read(), os.path.basename(archivo), avisos)
            hojas_es += contar_hojas(extra)
            fusionar(en, extra, [], stats)
        datos_es = (json.dumps(en, ensure_ascii=False, indent=4) + '\n').encode('utf-8')
        json.loads(datos_es.decode('utf-8'))  # validación
        escritor.escribir('lang/es.json', datos_es)
        resumen_es = [
            'Base: `lang/en.json` del commit `%s` (%d hojas).' % (args.commit, hojas_en),
            'Fusionado con: %s (%d hojas; el español pisa).' % (', '.join('`%s`' % os.path.basename(a) for a in args.es_keys), hojas_es),
            'Hojas pisadas: %d. Claves agregadas que no existían en en.json: %s.' % (
                stats['pisadas'], ', '.join('`%s`' % a for a in stats['agregadas']) or 'ninguna'),
            'Hojas totales en es.json: %d. Tamaño: %d bytes. sha256 `%s`.' % (contar_hojas(en), len(datos_es), sha256(datos_es)),
            'Conflictos de tipo (objeto vs hoja): %s.' % (', '.join(stats['conflictos_tipo']) or 'ninguno'),
        ] + ['Aviso: %s' % a for a in avisos]
        print('\n[4] lang/es.json -> %s' % escritor.resultados.get('lang/es.json'))
        for l in resumen_es:
            print('    ' + l)

    # 5. tilesets
    resumen_tilesets = []
    if args.tilesets:
        with open(args.tilesets, 'rb') as f:
            datos_t = f.read()
        obj = json.loads(datos_t.decode('utf-8'))
        escritor.escribir('data/tilesets.json', datos_t)
        resumen_tilesets = [
            'Copia byte a byte de `live/api_maps_line_tilesets_populate_true` (sin reordenar).',
            'JSON válido: sí. Tilesets: %s.' % ', '.join('%s (`%s`, %d baldosas)' % (t.get('name'), t.get('_id'), len(t.get('tiles', []))) for t in obj),
            'Tamaño: %d bytes. sha256 `%s`.' % (len(datos_t), sha256(datos_t)),
        ]
        print('\n[5] data/tilesets.json -> %s' % escritor.resultados.get('data/tilesets.json'))
        for l in resumen_tilesets:
            print('    ' + l)

    protegidos = [d for d, e in escritor.resultados.items() if e.startswith('PROTEGIDO')]
    escritor.guardar_estado(args.commit)
    actualizar_cambios_md(os.path.join(app, 'cambios', 'assets.md'),
                          bloque_markdown(args.commit, todos_cambios, resumen_es, resumen_tilesets, protegidos),
                          args.simular)
    print('\n[6] Estado guardado en herramientas/importar_cms.estado.json; bloque automático en cambios/assets.md')
    if protegidos:
        print('    AVISO: %d archivo(s) protegidos por edición local: %s' % (len(protegidos), ', '.join(protegidos)))
    print('\nListo.')
    return 1 if faltantes else 0


if __name__ == '__main__':
    sys.exit(main())
