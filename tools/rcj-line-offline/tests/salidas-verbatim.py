# -*- coding: utf-8 -*-
"""Área salidas: inserta y verifica el código VERBATIM del CMS en local/render/*.js.

Uso:
  python tests/salidas-verbatim.py <clon-del-cms>            verifica (sale con 1 si hay diferencias)
  python tests/salidas-verbatim.py <clon-del-cms> --escribir  (re)inserta el código entre las marcas

Cada región está entre
  // ===== INICIO VERBATIM <ruta>:<desde>-<hasta> =====
  // ===== FIN VERBATIM <ruta>:<desde>-<hasta> =====
y su contenido es `git show d805502:<ruta>` (líneas desde..hasta) con SOLO los cambios de CAMBIOS
(cada uno comprueba la línea original antes de reemplazarla). Idempotente.
"""
import os
import re
import subprocess
import sys

COMMIT = 'd805502'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REGIONES = {
    'local/render/mapa-png.js': [
        ('helper/lineSSR/2026.js', 1, 320),
        ('helper/lineSSR/index.js', 1, 32),
    ],
    'local/render/mapa-pdf.js': [
        ('helper/lineMapPDF.js', 1, 86),
    ],
    'local/render/planilla-pdf.js': [
        ('helper/scoreSheetUtil.js', 1, 19),
        ('helper/scoreSheetPDFUtil.js', 1, 53),
        ('helper/scoreSheetPDFLineRules/2026.js', 1, 461),
        ('helper/scoreSheetPDFLine2.js', 1, 100),
    ],
    'local/render/rutas-cms.js': [
        ('routes/api/lineMaps.js', 24, 29),
        ('routes/api/lineMaps.js', 650, 804),
        ('routes/api/lineMaps.js', 818, 822),
        ('routes/api/lineRuns.js', 663, 745),
    ],
}

# (ruta, línea) -> (original exacta, reemplazo)
CAMBIOS = {
    ('helper/lineSSR/2026.js', 22): (
        "  if (fs.existsSync(imgPath)) {",
        "  if (await fs.existe(imgPath)) { // [rcj-line-offline] existsSync -> await: en el navegador el archivo se consulta con fetch",
    ),
    ('helper/lineSSR/2026.js', 308): (
        "  const buffer = canvas.toBuffer('image/png');",
        "  const buffer = await canvas.toBuffer('image/png'); // [rcj-line-offline] toBlob del navegador es asíncrono",
    ),
    ('helper/lineSSR/2026.js', 313): (
        "  return (await drawLineCanvas(map)).toBuffer('image/png');",
        "  return await (await drawLineCanvas(map)).toBuffer('image/png'); // [rcj-line-offline] toBlob del navegador es asíncrono",
    ),
}


def git_show(cms, ruta):
    salida = subprocess.run(['git', '-C', cms, 'show', '%s:%s' % (COMMIT, ruta)], capture_output=True, check=True)
    return salida.stdout.decode('utf-8').split('\n')


def esperado(cms, ruta, desde, hasta, cache):
    if ruta not in cache:
        cache[ruta] = git_show(cms, ruta)
    lineas = cache[ruta]
    out = []
    for n in range(desde, hasta + 1):
        linea = lineas[n - 1]
        if (ruta, n) in CAMBIOS:
            original, nuevo = CAMBIOS[(ruta, n)]
            if linea != original:
                raise SystemExit('ERROR: %s:%d no coincide con el original esperado:\n  %r\n  %r' % (ruta, n, linea, original))
            linea = nuevo
        out.append(linea)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cms = sys.argv[1]
    escribir = '--escribir' in sys.argv[2:]
    cache = {}
    diferencias = 0
    regiones = 0
    for archivo, lista in REGIONES.items():
        ruta_archivo = os.path.join(APP, archivo)
        with open(ruta_archivo, 'r', encoding='utf-8', newline='') as f:
            texto = f.read()
        lineas = texto.split('\n')
        for (ruta, desde, hasta) in lista:
            regiones += 1
            etiqueta = '%s:%d-%d' % (ruta, desde, hasta)
            ini = '// ===== INICIO VERBATIM %s =====' % etiqueta
            fin = '// ===== FIN VERBATIM %s =====' % etiqueta
            try:
                i = lineas.index(ini)
                j = lineas.index(fin)
            except ValueError:
                raise SystemExit('ERROR: faltan las marcas de %s en %s' % (etiqueta, archivo))
            actual = lineas[i + 1:j]
            quiero = esperado(cms, ruta, desde, hasta, cache)
            if actual != quiero:
                if escribir:
                    lineas[i + 1:j] = quiero
                else:
                    diferencias += 1
                    for k, (a, b) in enumerate(zip(actual, quiero)):
                        if a != b:
                            print('DIFERENCIA %s en %s, línea %d de la región:\n  local: %r\n  cms:   %r' % (etiqueta, archivo, desde + k, a, b))
                            break
                    else:
                        print('DIFERENCIA %s en %s: largo %d (local) vs %d (cms)' % (etiqueta, archivo, len(actual), len(quiero)))
        if escribir:
            nuevo = '\n'.join(lineas)
            if nuevo != texto:
                with open(ruta_archivo, 'w', encoding='utf-8', newline='') as f:
                    f.write(nuevo)
                print('escrito', archivo)
    cambios = len(CAMBIOS)
    if escribir:
        print('regiones: %d, cambios documentados: %d' % (regiones, cambios))
        return 0
    print('regiones: %d, diferencias: %d, cambios documentados aplicados: %d' % (regiones, diferencias, cambios))
    return 1 if diferencias else 0


if __name__ == '__main__':
    sys.exit(main())
