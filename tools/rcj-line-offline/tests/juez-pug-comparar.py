# -*- coding: utf-8 -*-
"""Área juez: verificación de fidelidad de juez.html contra views/judge/line_2026.pug.

No hay node ni pug en la máquina, así que este script trae un renderizador MÍNIMO de pug que
cubre exactamente la sintaxis que usa views/judge/line_2026.pug (tags con .clase/#id, atributos
entre paréntesis con strings, texto en línea, texto con |, comentarios // e interpolación #{}).
Reproduce la salida compacta de Express + pug (sin `pretty`): sin espacios entre tags.

Uso:
  python tests/juez-pug-comparar.py --cms <clon del CMS>            compara (exit 0 = igual)
  python tests/juez-pug-comparar.py --cms <clon del CMS> --generar  imprime el <body> renderizado
                                                                     en estilo "salto dentro del tag"

La comparación se hace sobre el árbol que arma html.parser (tags, atributos como conjunto, texto
exacto con entidades resueltas y comentarios). Los únicos cambios admitidos son los documentados en
cambios/juez.md, que el script aplica al render del pug antes de comparar (CAMBIOS_DOCUMENTADOS).
"""
import argparse
import difflib
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

COMMIT = 'd805502'
PUG = 'views/judge/line_2026.pug'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VACIOS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
# Regla 3a: rutas absolutas de estáticos -> relativas
RE_ESTATICO = re.compile(r'^/(components|images|templates|lang|stylesheets|javascripts|sounds|scoresheet_generation)/')


# ------------------------------------------------------------------ renderizador mínimo de pug
class Nodo:
    def __init__(self, tipo, **kw):
        self.tipo = tipo  # 'tag' | 'texto' | 'comentario'
        self.hijos = []
        self.__dict__.update(kw)


def leer_parentesis(s, i):
    """s[i] == '(' -> (contenido, índice después del ')')."""
    assert s[i] == '('
    j = i + 1
    comilla = None
    prof = 0
    while j < len(s):
        c = s[j]
        if comilla:
            if c == '\\':
                j += 2
                continue
            if c == comilla:
                comilla = None
        elif c in '\'"`':
            comilla = c
        elif c == '(':
            prof += 1
        elif c == ')':
            if prof == 0:
                return s[i + 1:j], j + 1
            prof -= 1
        j += 1
    raise ValueError('paréntesis sin cerrar: ' + s)


def leer_atributos(txt):
    attrs = []
    i = 0
    n = len(txt)
    while i < n:
        while i < n and txt[i] in ' \t,':
            i += 1
        if i >= n:
            break
        m = re.match(r'[^\s=,]+', txt[i:])
        nombre = m.group(0)
        i += len(nombre)
        while i < n and txt[i] in ' \t':
            i += 1
        if i < n and txt[i] == '=':
            i += 1
            while i < n and txt[i] in ' \t':
                i += 1
            q = txt[i]
            if q not in '\'"':
                raise ValueError('valor de atributo no literal (no soportado): ' + txt[i:])
            j = i + 1
            val = []
            while txt[j] != q:
                if txt[j] == '\\':
                    val.append(txt[j + 1])
                    j += 2
                    continue
                val.append(txt[j])
                j += 1
            attrs.append((nombre, ''.join(val)))
            i = j + 1
        else:
            attrs.append((nombre, True))
    return attrs


def interpolar(texto):
    # #{rule} e #{id}: la ruta /line/judge/:id solo pasa `id` (routes/line.js:93) -> rule rinde ''
    return re.sub(r'#\{\s*(\w+)\s*\}', lambda m: '', texto)


def parsear_linea(contenido):
    if contenido.startswith('//-'):
        return None
    if contenido.startswith('//'):
        return Nodo('comentario', texto=contenido[2:])
    if contenido.startswith('|'):
        t = contenido[1:]
        if t.startswith(' '):
            t = t[1:]
        return Nodo('texto', texto=interpolar(t))
    m = re.match(r'([a-zA-Z][\w:-]*)?((?:[.#][\w-]+)*)', contenido)
    if not m or m.end() == 0:
        raise ValueError('línea no soportada: ' + contenido)
    tag = m.group(1) or 'div'
    attrs = []
    clases = []
    pos_clase = None
    for sel in re.findall(r'[.#][\w-]+', m.group(2)):
        if sel[0] == '.':
            if pos_clase is None:
                pos_clase = len(attrs)
                attrs.append(('class', None))
            clases.append(sel[1:])
        else:
            attrs.append(('id', sel[1:]))
    i = m.end()
    if i < len(contenido) and contenido[i] == '(':
        dentro, i = leer_parentesis(contenido, i)
        for nombre, val in leer_atributos(dentro):
            if nombre == 'class':
                if pos_clase is None:
                    pos_clase = len(attrs)
                    attrs.append(('class', None))
                clases.append(val)
            else:
                attrs.append((nombre, val))
    if pos_clase is not None:
        attrs[pos_clase] = ('class', ' '.join(clases))
    resto = contenido[i:]
    texto = None
    if resto:
        if resto == '.':
            raise ValueError('bloque de texto no soportado en el body: ' + contenido)
        if not resto.startswith(' '):
            raise ValueError('resto inesperado: ' + contenido)
        texto = interpolar(resto[1:])
    return Nodo('tag', tag=tag, attrs=attrs, texto=texto)


def parsear_body(fuente):
    lineas = fuente.split('\n')
    inicio = next(i for i, l in enumerate(lineas) if l.strip().startswith('body('))
    raiz = Nodo('raiz')
    pila = [(-1, raiz)]
    for l in lineas[inicio:]:
        if not l.strip():
            continue
        sangria = len(l) - len(l.lstrip(' '))
        nodo = parsear_linea(l.strip())
        if nodo is None:
            continue
        while pila[-1][0] >= sangria:
            pila.pop()
        pila[-1][1].hijos.append(nodo)
        pila.append((sangria, nodo))
    return raiz.hijos[0]


def aplicar_3a(attrs):
    out = []
    for k, v in attrs:
        if isinstance(v, str) and k in ('src', 'href', 'ng-src') and RE_ESTATICO.match(v):
            v = v[1:]
        out.append((k, v))
    return out


def esc_attr(v):
    return v.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def render(nodo, sangria=0, compacto=True):
    if nodo.tipo == 'texto':
        return nodo.texto
    if nodo.tipo == 'comentario':
        return '<!--' + nodo.texto + '-->'
    attrs = aplicar_3a(nodo.attrs)
    partes = []
    for k, v in attrs:
        partes.append(k if v is True else '%s="%s"' % (k, esc_attr(v)))
    if compacto:
        abre = '<' + nodo.tag + (' ' + ' '.join(partes) if partes else '') + '>'
    else:
        abre = '<' + nodo.tag + '\n' + '  ' * (sangria + 1) + ' '.join(partes) + '>'
    cuerpo = (nodo.texto or '') + ''.join(render(h, sangria + 1, compacto) for h in nodo.hijos)
    if nodo.tag in VACIOS:
        return abre
    return abre + cuerpo + '</' + nodo.tag + '>'


# ------------------------------------------------------------------ comparación por tokens
class Tokens(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.t = []
        self.dentro = False

    def _push(self, tok):
        if tok[0] == 'texto' and self.t and self.t[-1][0] == 'texto':
            self.t[-1] = ('texto', self.t[-1][1] + tok[1])
        else:
            self.t.append(tok)

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.dentro = True
        if self.dentro:
            self._push(('abre', tag, tuple(sorted((k, v if v is not None else '') for k, v in attrs))))

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if self.dentro:
            self._push(('cierra', tag))
        if tag == 'body':
            self.dentro = False

    def handle_data(self, data):
        if self.dentro:
            self._push(('texto', data))

    def handle_comment(self, data):
        if self.dentro:
            self._push(('comentario', data))


def tokens(html_txt):
    p = Tokens()
    p.feed(html_txt)
    p.close()
    return p.t


def fmt(tok):
    if tok[0] == 'abre':
        return '<%s %s>' % (tok[1], ' '.join('%s=%r' % kv for kv in tok[2]))
    if tok[0] == 'cierra':
        return '</%s>' % tok[1]
    return '%s %r' % tok


# Cambios documentados en cambios/juez.md que juez.html aplica sobre el render del pug.
def CAMBIOS_DOCUMENTADOS(toks):
    aplicados = []
    # C1 (desvío 9, flag corregirBugsVisuales): fila "Rule" -> <td><span ng-if=...>{{rcjRegla(...)}}</span></td>
    for i in range(len(toks) - 3):
        if toks[i] == ('texto', "{{'common.rule' | translate}}") and toks[i + 1] == ('cierra', 'th') \
                and toks[i + 2][0] == 'abre' and toks[i + 2][1] == 'td' and toks[i + 3] == ('cierra', 'td'):
            nuevo = [('abre', 'span', (('ng-if', 'rcjFlags.corregirBugsVisuales'),)),
                     ('texto', '{{rcjRegla(competition, league)}}'),
                     ('cierra', 'span')]
            toks = toks[:i + 3] + nuevo + toks[i + 3:]
            aplicados.append('C1 fila Rule con ng-if rcjFlags.corregirBugsVisuales')
            break
    return toks, aplicados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cms', required=True, help='clon del repo rcj-rescue-cms')
    ap.add_argument('--generar', action='store_true')
    args = ap.parse_args()
    fuente = subprocess.run(['git', '-C', args.cms, 'show', '%s:%s' % (COMMIT, PUG)], capture_output=True, check=True).stdout.decode('utf-8')
    body = parsear_body(fuente)
    if args.generar:
        sys.stdout.buffer.write(render(body, 0, compacto=False).encode('utf-8'))
        return 0
    esperado, aplicados = CAMBIOS_DOCUMENTADOS(tokens(render(body, 0, compacto=True)))
    with open(os.path.join(APP, 'juez.html'), encoding='utf-8') as f:
        obtenido = tokens(f.read())
    a = [fmt(t) for t in esperado]
    b = [fmt(t) for t in obtenido]
    print('tokens del body: pug=%d juez.html=%d; cambios documentados aplicados: %s' % (len(a), len(b), aplicados))
    if a == b and len(aplicados) == 1:
        print('IGUAL: el <body> de juez.html es el render del pug (salida compacta) + los cambios documentados')
        return 0
    for linea in difflib.unified_diff(a, b, 'pug renderizado', 'juez.html', lineterm='', n=2):
        print(linea)
    return 1


if __name__ == '__main__':
    sys.exit(main())
