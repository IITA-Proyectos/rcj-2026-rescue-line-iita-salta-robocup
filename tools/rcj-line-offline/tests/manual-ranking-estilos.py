# -*- coding: utf-8 -*-
"""Área manual-ranking: bloques `style.` de los pug de carga manual dentro de manual.html.

Uso:
  python tests/manual-ranking-estilos.py <clon-del-cms> [--escribir]

Sin --escribir compara (sale con 1 si difieren). Con --escribir reemplaza el contenido entre los marcadores
`/* ===== INICIO VERBATIM views/manual/<variante>/line_2026.pug style. ===== */` y `FIN` de manual.html.

El texto sale de `git show d805502:<pug>`: las líneas que siguen a `style.` hasta la línea anterior a `body(`,
sin las líneas en blanco finales y quitando la sangría común (así lo emite pug para un bloque de texto).
Los bloques no contienen url(...), rutas absolutas ni interpolaciones #{} (verificado al generarlos).
"""
import os
import re
import subprocess
import sys

COMMIT = 'd805502'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(APP, 'manual.html')
VARIANTES = ['input', 'check']


def bloque_style(cms, variante):
    ruta = 'views/manual/%s/line_2026.pug' % variante
    txt = subprocess.run(['git', '-C', cms, 'show', '%s:%s' % (COMMIT, ruta)], capture_output=True, check=True).stdout.decode('utf-8')
    lineas = txt.split('\n')
    i_style = next(i for i, l in enumerate(lineas) if l.strip() == 'style.')
    i_body = next(i for i, l in enumerate(lineas) if l.lstrip().startswith('body('))
    cuerpo = lineas[i_style + 1:i_body]
    while cuerpo and not cuerpo[-1].strip():
        cuerpo.pop()
    sangria = min(len(l) - len(l.lstrip(' ')) for l in cuerpo if l.strip())
    salida = [l[sangria:] if l.strip() else '' for l in cuerpo]
    texto = '\n'.join(salida)
    if re.search(r'url\(|#\{|!\{|/images/|/components/|</style', texto):
        raise SystemExit('el bloque style de %s tiene algo que habría que adaptar' % ruta)
    return ruta, i_style + 2, i_style + 1 + len(cuerpo), texto


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cms = sys.argv[1]
    escribir = '--escribir' in sys.argv
    with open(HTML, encoding='utf-8', newline='') as f:
        html = f.read()
    difiere = False
    for v in VARIANTES:
        ruta, desde, hasta, texto = bloque_style(cms, v)
        ini = '/* ===== INICIO VERBATIM %s style. ===== */' % ruta
        fin = '/* ===== FIN VERBATIM %s style. ===== */' % ruta
        a = html.index(ini) + len(ini)
        b = html.index(fin)
        actual = html[a:b]
        nuevo = '\n' + texto + '\n'
        if actual != nuevo:
            difiere = True
            print('%s (líneas %d-%d): DIFIERE' % (ruta, desde, hasta))
            html = html[:a] + nuevo + html[b:]
        else:
            print('%s (líneas %d-%d): igual (%d bytes)' % (ruta, desde, hasta, len(texto.encode('utf-8'))))
    if escribir and difiere:
        with open(HTML, 'w', encoding='utf-8', newline='') as f:
            f.write(html)
        print('manual.html actualizado')
        return 0
    return 1 if difiere else 0


if __name__ == '__main__':
    sys.exit(main())
