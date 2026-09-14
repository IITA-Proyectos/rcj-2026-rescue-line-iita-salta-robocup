# -*- coding: utf-8 -*-
"""Pruebas del área salidas en Edge headless (puerto 8808).

Uso:
  python tests/salidas-correr.py [--pasos png,pdf,angular,editor,planillas,capturas,analisis]

Pasos:
  png        tests/salidas-png.html       PNG del mapa (map-image-png, image/:mapid)
  pdf        tests/salidas-pdf.html       PDF de mapa, planilla del editor, scoresheet2 de 2 corridas, export
  angular    tests/salidas-angular.html   $scope.generateOutput del editor con $http real
  editor     tests/salidas-editor.html    botón Generate de editor.html (página real, en iframe)
  planillas  tests/salidas-sembrar.html + tests/salidas-planillas.html  (mismo perfil: 2 corridas)
  capturas   tests/salidas-captura.html   planillas.html a 1366x900, 1024x768 y 412x915 (mismo perfil)
  analisis   Python sobre los archivos generados: pypdf (páginas, texto), PyMuPDF (rasterizado),
             OpenCV (decodifica el QR "L;<runId>") y captura del PDF abierto en Edge.

Servidor: ThreadingHTTPServer + SimpleHTTPRequestHandler (como `python -m http.server 8808 --bind 127.0.0.1`)
con agregados SOLO de prueba:
  GET  /__latido?ms=N           espera N ms y responde 204 (pausa el tiempo virtual de Edge mientras corre IndexedDB)
  POST /__archivo?nombre=X      guarda un archivo generado en tests/capturas/salidas-X
  POST /__resultado?nombre=X    guarda el JSON de una captura (--screenshot no permite --dump-dom)
Apaga el servidor al terminar.
"""
import argparse
import functools
import html
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

PUERTO = 8808
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.environ.get('RCJ_TMP') or tempfile.gettempdir()
CAPTURAS = os.path.join(APP, 'tests', 'capturas')
RESULTADOS_POST = {}
TAMANIOS = [(1366, 900, 1), (1024, 768, 2), (412, 915, 4)]


class Manejador(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/__latido':
            q = urllib.parse.parse_qs(u.query)
            ms = min(int((q.get('ms') or ['250'])[0]), 5000)
            time.sleep(ms / 1000.0)
            self.send_response(204)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        return super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        nombre = (urllib.parse.parse_qs(u.query).get('nombre') or [''])[0]
        largo = int(self.headers.get('Content-Length') or 0)
        cuerpo = self.rfile.read(largo)
        if u.path == '/__archivo' and re.match(r'^[\w.-]+$', nombre):
            os.makedirs(CAPTURAS, exist_ok=True)
            with open(os.path.join(CAPTURAS, 'salidas-' + nombre), 'wb') as f:
                f.write(cuerpo)
        elif u.path == '/__resultado':
            RESULTADOS_POST[nombre] = cuerpo.decode('utf-8', 'replace')
        else:
            self.send_error(405)
            return
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def levantar_servidor():
    manejador = functools.partial(Manejador, directory=APP)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PUERTO), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:%d/planillas.html' % PUERTO, timeout=1)
            return srv
        except Exception:
            time.sleep(0.2)
    raise SystemExit('el servidor no respondió en el puerto %d' % PUERTO)


def consola_edge(stderr):
    return [l.strip()[:400] for l in stderr.splitlines() if 'CONSOLE' in l]


def edge(args, perfil, ancho, alto, presupuesto, timeout=600):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
           '--hide-scrollbars', '--enable-logging=stderr', '--v=0',
           '--user-data-dir=' + perfil, '--window-size=%d,%d' % (ancho, alto),
           '--virtual-time-budget=%d' % presupuesto] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def dump(pagina, perfil, query=''):
    url = 'http://127.0.0.1:%d/tests/%s%s' % (PUERTO, pagina, ('?' + query) if query else '')
    t0 = time.time()
    proc = edge(['--dump-dom', url], perfil, 1366, 900, 600000)
    salida = proc.stdout.decode('utf-8', 'replace')
    stderr = proc.stderr.decode('utf-8', 'replace')
    base = {'pagina': pagina, 'segundos': round(time.time() - t0, 1)}
    m = re.search(r'<pre id="resultado">(.*?)</pre>', salida, re.S)
    if not m:
        base.update(ok=False, error='sin #resultado', dom=salida[:1500], consolaEdge=consola_edge(stderr)[-20:])
        return base
    try:
        datos = json.loads(html.unescape(m.group(1)))
    except Exception as e:
        base.update(ok=False, error='resultado no es JSON: %s' % e, crudo=html.unescape(m.group(1))[:2000],
                    consolaEdge=consola_edge(stderr)[-20:])
        return base
    datos.update(base)
    return datos


def perfil_nuevo(nombre):
    p = os.path.join(TMP, 'edge-salidas-' + nombre)
    shutil.rmtree(p, ignore_errors=True)
    return p


def capturar(cid, ancho, alto, n, perfil):
    nombre = 'salidas-planillas-%dx%d' % (ancho, alto)
    png = os.path.join(CAPTURAS, nombre + '.png')
    if os.path.exists(png):
        os.remove(png)
    url = 'http://127.0.0.1:%d/tests/salidas-captura.html?competition=%s&ancho=%d&alto=%d&n=%d&nombre=%s' % (
        PUERTO, cid, ancho, alto, n, nombre)
    t0 = time.time()
    proc = edge(['--screenshot=' + png, url], perfil, ancho, n * (alto + 4), 120000)
    res = {'pagina': nombre + '.png', 'existe': os.path.exists(png), 'segundos': round(time.time() - t0, 1)}
    crudo = RESULTADOS_POST.pop(nombre, None)
    if crudo is None:
        res.update(ok=False, error='la página de captura no mandó resultado',
                   consolaEdge=consola_edge(proc.stderr.decode('utf-8', 'replace'))[-10:])
    else:
        res.update(json.loads(crudo))
    return res


# ------------------------------------------------------------------------------------------ análisis
def analizar(runs):
    """Verifica los PDF/PNG generados con librerías independientes del generador."""
    checks = []

    def check(nombre, cond, detalle=None):
        c = {'nombre': nombre, 'ok': bool(cond)}
        if not cond and detalle is not None:
            c['detalle'] = detalle
        checks.append(c)

    extra = {}
    try:
        import fitz
        import numpy as np
        import cv2
        from pypdf import PdfReader
    except Exception as e:
        return {'pagina': 'analisis', 'ok': False, 'error': 'faltan librerías de análisis: %s' % e}

    def ruta(n):
        return os.path.join(CAPTURAS, 'salidas-' + n)

    def rasterizar(nombre, zoom=2.0):
        doc = fitz.open(ruta(nombre))
        salidas = []
        for i, pagina in enumerate(doc):
            pix = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            destino = ruta(nombre.replace('.pdf', '') + '-p%d.png' % (i + 1))
            pix.save(destino)
            salidas.append(destino)
        return salidas

    def qr_de(png):
        img = cv2.imread(png)
        det = cv2.QRCodeDetector()
        ok, textos, _, _ = det.detectAndDecodeMulti(img)
        textos = [t for t in (textos or []) if t] if ok else []
        if not textos:
            t, _, _ = det.detectAndDecode(img)
            textos = [t] if t else []
        return textos

    def no_blanco(png):
        img = cv2.imread(png, cv2.IMREAD_GRAYSCALE)
        return float((img < 245).mean()) if img is not None else 0.0

    # PNG del mapa
    if os.path.exists(ruta('mapa-editor.png')):
        img = cv2.imread(ruta('mapa-editor.png'))
        extra['mapaPng'] = {'alto': img.shape[0], 'ancho': img.shape[1], 'fraccionNoBlanca': round(no_blanco(ruta('mapa-editor.png')), 3)}
        check('PNG del mapa: OpenCV lo abre y no está en blanco', img is not None and extra['mapaPng']['fraccionNoBlanca'] > 0.2, extra['mapaPng'])
    else:
        check('PNG del mapa generado', False, 'falta salidas-mapa-editor.png')

    # PDFs
    esperados = {
        'mapa-A4.pdf': 1, 'mapa-Letter.pdf': 1, 'planilla-editor.pdf': 1, 'planillas-corridas.pdf': 2,
        'planilla-corrida-1.pdf': 1, 'export-planillas.pdf': 1, 'export-mapas.pdf': 1,
    }
    for nombre, paginas in esperados.items():
        if not os.path.exists(ruta(nombre)):
            check('%s generado' % nombre, False, 'no existe')
            continue
        with open(ruta(nombre), 'rb') as f:
            cabecera = f.read(8)
        lector = PdfReader(ruta(nombre))
        check('%s: cabecera %%PDF y %d página(s) según pypdf' % (nombre, paginas),
              cabecera.startswith(b'%PDF') and len(lector.pages) == paginas, {'cabecera': str(cabecera), 'paginas': len(lector.pages)})
        pngs = rasterizar(nombre)
        fr = [round(no_blanco(p), 3) for p in pngs]
        check('%s: PyMuPDF lo rasteriza y no está en blanco' % nombre, len(pngs) == paginas and all(x > 0.03 for x in fr), fr)
        extra.setdefault('rasterizados', {})[nombre] = [os.path.basename(p) for p in pngs]

    # Texto y QR de las planillas
    if os.path.exists(ruta('planilla-editor.pdf')):
        texto = PdfReader(ruta('planilla-editor.pdf')).pages[0].extract_text() or ''
        extra['textoPlanillaEditor'] = texto[:300]
        check('planilla del editor titulada "Competition  Rescue Line" (C6)', 'Competition' in texto and 'Rescue Line' in texto, texto[:300])
        q = qr_de(ruta('planilla-editor-p1.png'))
        check('planilla del editor sin QR (el mapa no tiene _id)', not any(t.startswith('L;') for t in q), q)
    if os.path.exists(ruta('planillas-corridas.pdf')):
        lector = PdfReader(ruta('planillas-corridas.pdf'))
        textos = [(p.extract_text() or '') for p in lector.pages]
        extra['textoPlanillas'] = [t[:200] for t in textos]
        check('planillas de corridas con el nombre de la competencia', all('IITA 2026' in t for t in textos), [t[:200] for t in textos])
        qrs = []
        for i in range(len(lector.pages)):
            png = ruta('planillas-corridas-p%d.png' % (i + 1))
            q = qr_de(png)
            if not q:  # más resolución si no decodifica
                doc = fitz.open(ruta('planillas-corridas.pdf'))
                doc[i].get_pixmap(matrix=fitz.Matrix(4, 4)).save(png + '.x4.png')
                q = qr_de(png + '.x4.png')
                os.remove(png + '.x4.png')
            qrs.append(q)
        extra['qrs'] = qrs
        esperado = sorted(['L;' + r for r in (runs or [])])
        obtenido = sorted(t for q in qrs for t in q if t.startswith('L;'))
        check('QR de cada planilla decodifica "L;<runId>" (OpenCV)', runs and obtenido == esperado, {'obtenido': qrs, 'esperado': esperado})

    # El visor de PDF de Edge headless no dibuja el documento (la captura sale gris liso, probado el
    # 2026-09-13): no se usa como verificación; el rasterizado de referencia es el de PyMuPDF.
    extra['edgeVisorPdf'] = 'no se usa: Edge --headless=new no renderiza su visor de PDF (captura gris #333)'
    fallas = [c for c in checks if not c['ok']]
    return {'pagina': 'analisis', 'ok': not fallas, 'total': len(checks), 'fallas': fallas, 'errores': [],
            'verificaciones': [('OK    ' if c['ok'] else 'FALLA ') + c['nombre'] for c in checks], 'extra': extra}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pasos', default='png,pdf,angular,editor,planillas,capturas,analisis')
    args = ap.parse_args()
    try:  # la consola de Windows (cp1252) no imprime Σ, ×, etc.
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    pasos = set(p for p in args.pasos.split(',') if p)
    os.makedirs(CAPTURAS, exist_ok=True)
    srv = levantar_servidor()
    resultados = []
    runs = None

    def mostrar(r):
        resultados.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:12000])
        sys.stdout.flush()

    try:
        if 'png' in pasos:
            mostrar(dump('salidas-png.html', perfil_nuevo('png')))
        if 'pdf' in pasos:
            r = dump('salidas-pdf.html', perfil_nuevo('pdf'))
            runs = ((r.get('extra') or {}).get('runs'))
            if runs:  # el paso analisis los usa aunque se corra solo
                with open(os.path.join(CAPTURAS, 'salidas-runs.json'), 'w', encoding='utf-8') as f:
                    json.dump(runs, f)
            mostrar(r)
        if 'angular' in pasos:
            mostrar(dump('salidas-angular.html', perfil_nuevo('angular')))
        if 'editor' in pasos:
            mostrar(dump('salidas-editor.html', perfil_nuevo('editor')))
        perfil = os.path.join(TMP, 'edge-salidas-planillas')
        cid = None
        if 'planillas' in pasos or 'capturas' in pasos:
            perfil = perfil_nuevo('planillas')
            s = dump('salidas-sembrar.html', perfil)
            mostrar(s)
            cid = (s.get('extra') or {}).get('cid')
        if 'planillas' in pasos and cid:
            mostrar(dump('salidas-planillas.html', perfil, 'competition=' + cid))
        if 'capturas' in pasos and cid:
            for ancho, alto, n in TAMANIOS:
                mostrar(capturar(cid, ancho, alto, n, perfil))
        if 'analisis' in pasos:
            if runs is None:
                try:
                    with open(os.path.join(CAPTURAS, 'salidas-runs.json'), encoding='utf-8') as f:
                        runs = json.load(f)
                except Exception:
                    runs = None
            mostrar(analizar(runs))
    finally:
        srv.shutdown()
        srv.server_close()

    print('\n==== RESUMEN ====')
    for r in resultados:
        print('%-36s %-6s total=%-4s fallas=%-3s errores=%-3s (%ss)' % (
            r.get('pagina'), 'OK' if r.get('ok') else 'FALLA', r.get('total'),
            len(r.get('fallas') or []), len(r.get('errores') or []), r.get('segundos')))
    return 0 if resultados and all(r.get('ok') for r in resultados) else 1


if __name__ == '__main__':
    sys.exit(main())
