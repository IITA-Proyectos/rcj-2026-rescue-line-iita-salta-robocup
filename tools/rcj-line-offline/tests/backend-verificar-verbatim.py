# -*- coding: utf-8 -*-
"""Verifica que las regiones marcadas "INICIO VERBATIM ... FIN VERBATIM" de local/nucleo/*.js sean
byte a byte iguales a `git show d805502:<ruta>` del CMS (con las únicas sustituciones documentadas en
cambios/backend.md).

Uso: python tests/backend-verificar-verbatim.py <ruta-al-clon-de-rcj-rescue-cms>
"""
import os
import re
import subprocess
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMIT = 'd805502'

# Sustituciones permitidas (texto del CMS -> texto local)
SUSTITUCIONES = {
    'helper/initRunData.js': [(
        "  const query = lineMap.findById(run.map);\n  query.populate('tiles.tileType', '-__v');\n\n  let map = await query.lean().exec();",
        "  // [rcj-line-offline] initRunData.js:7-10 reemplazadas: el mapa poblado (tiles.tileType sin __v, lean)\n  let map = __mapaPoblado;"
    )]
}


def show(cms, ruta):
    return subprocess.check_output(['git', '-C', cms, 'show', '%s:%s' % (COMMIT, ruta)]).decode('utf-8')


def region_cms(cms, ref):
    m = re.match(r'^(.*?)(?::(\d+)-(\d+))?$', ref)
    ruta, a, b = m.group(1), m.group(2), m.group(3)
    texto = show(cms, ruta)
    if a:
        lineas = texto.split('\n')
        texto = '\n'.join(lineas[int(a) - 1:int(b)]) + '\n'
    for viejo, nuevo in SUSTITUCIONES.get(ruta, []):
        assert texto.count(viejo) == 1, 'sustitución no encontrada en ' + ruta
        texto = texto.replace(viejo, nuevo)
    if not texto.endswith('\n'):
        texto += '\n'
    return texto


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cms = sys.argv[1]
    total, fallas = 0, 0
    for nombre in sorted(os.listdir(os.path.join(APP, 'local', 'nucleo'))):
        if not nombre.endswith('.js'):
            continue
        with open(os.path.join(APP, 'local', 'nucleo', nombre), encoding='utf-8', newline='') as f:
            local = f.read()
        for m in re.finditer(r'// ===== INICIO VERBATIM (\S+) \(rcj-rescue-cms %s\) =====\n(.*?)// ===== FIN VERBATIM \1 =====\n' % COMMIT, local, re.S):
            total += 1
            ref, cuerpo = m.group(1), m.group(2)
            esperado = region_cms(cms, ref)
            ok = cuerpo == esperado
            if not ok:
                fallas += 1
            print('%-26s %-40s %s (%d bytes)' % (nombre, ref, 'IDENTICO' if ok else 'DIFIERE', len(cuerpo.encode('utf-8'))))
    print('regiones: %d, difieren: %d' % (total, fallas))
    return 0 if total and not fallas else 1


if __name__ == '__main__':
    sys.exit(main())
