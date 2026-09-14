# -*- coding: utf-8 -*-
"""Pruebas del área editor en Edge headless (puerto 8803).

Uso:
  python tests/editor-correr.py [--perfiles DIR] [--sin-capturas] [pagina.html ...]
  (sin páginas corre todas las de PAGINAS)

Levanta un http.server (ThreadingHTTPServer + SimpleHTTPRequestHandler, igual que
`python -m http.server 8803 --bind 127.0.0.1`) sobre la carpeta de la app con DOS agregados solo de prueba:
  - GET /__latido?ms=N espera N ms y responde 204 (ver tests/editor-comun.js): mantiene pausado el tiempo
    virtual de Edge headless mientras trabaja IndexedDB.
  - GET /editor.html se sirve con <script src="tests/editor-captura.js"></script> inyectado después de
    <meta charset="utf-8"> (captura errores de consola y descargas). El archivo en disco no cambia.
Abre cada página con Edge headless (--dump-dom), extrae <pre id="resultado">JSON</pre> y junta las líneas de
consola que Edge escribe por stderr. Después toma capturas de editor.html en tests/capturas/ con el mismo
perfil (misma IndexedDB) de la prueba que sembró el mapa. Apaga el servidor al terminar.
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

PUERTO = 8803
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# (página, argumentos extra de Edge)
PAGINAS = [
    ('editor-importar.html', []),
    ('editor-guardar.html', []),
    ('editor-edicion.html', []),
    ('editor-tactil.html', ['--touch-events=enabled']),
    ('editor-movil.html', ['--touch-events=enabled']),
    ('editor-scroll.html', []),
]
INYECCION = '<meta charset="utf-8">\n<script src="tests/editor-captura.js"></script>'


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
        if u.path == '/editor.html':
            with open(os.path.join(APP, 'editor.html'), 'rb') as fh:
                cuerpo = fh.read().decode('utf-8').replace('<meta charset="utf-8">', INYECCION, 1).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(cuerpo)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        return super().do_GET()

    def log_message(self, *args):
        pass


def levantar_servidor():
    manejador = functools.partial(Manejador, directory=APP)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PUERTO), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:%d/editor.html' % PUERTO, timeout=1)
            return srv
        except Exception:
            time.sleep(0.2)
    raise SystemExit('el servidor no respondió en el puerto %d' % PUERTO)


def consola_edge(stderr):
    return [l.strip()[:600] for l in stderr.splitlines() if 'CONSOLE' in l]


def edge(args, perfil, ancho, alto, presupuesto, extra=None):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
           '--hide-scrollbars', '--enable-logging=stderr', '--v=0',
           '--user-data-dir=' + perfil, '--window-size=%d,%d' % (ancho, alto),
           '--virtual-time-budget=%d' % presupuesto] + (extra or []) + args
    return subprocess.run(cmd, capture_output=True, timeout=900)


def correr_pagina(pagina, extra, perfil):
    url = 'http://127.0.0.1:%d/tests/%s' % (PUERTO, pagina)
    t0 = time.time()
    proc = edge(['--dump-dom', url], perfil, 1400, 1000, 300000, extra)
    salida = proc.stdout.decode('utf-8', 'replace')
    stderr = proc.stderr.decode('utf-8', 'replace')
    m = re.search(r'<pre id="resultado">(.*?)</pre>', salida, re.S)
    base = {'pagina': pagina, 'segundos': round(time.time() - t0, 1)}
    if not m:
        base.update({'ok': False, 'error': 'sin #resultado', 'dom': salida[:1500], 'consolaEdge': consola_edge(stderr)[-30:]})
        return base
    try:
        datos = json.loads(html.unescape(m.group(1)))
    except Exception as e:
        base.update({'ok': False, 'error': 'resultado no es JSON: %s' % e, 'crudo': m.group(1)[:3000]})
        return base
    datos.update(base)
    datos['consolaEdgeErrores'] = [l for l in consola_edge(stderr) if 'ERROR' in l.upper() and 'CONSOLE(' in l][:30]
    return datos


def capturar(query, nombre, perfil, ancho, alto, extra):
    carpeta = os.path.join(APP, 'tests', 'capturas')
    os.makedirs(carpeta, exist_ok=True)
    png = os.path.join(carpeta, '%s-%dx%d.png' % (nombre, ancho, alto))
    if os.path.exists(png):
        os.remove(png)
    recorte = None
    if ancho < 500:
        # Edge headless no dibuja ventanas de menos de 500 px: editor.html va en un iframe del ancho real
        # (tests/editor-marco.html) dentro de una ventana de 500 px y después se recorta la imagen.
        url = 'http://127.0.0.1:%d/tests/editor-marco.html?w=%d&h=%d&q=%s' % (PUERTO, ancho, alto, urllib.parse.quote(query))
        proc = edge(['--screenshot=' + png, url], perfil, 500, alto, 30000, extra)
        if os.path.exists(png):
            try:
                from PIL import Image
                with Image.open(png) as im:
                    recortada = im.crop((0, 0, ancho, alto))
                recortada.save(png)
                recorte = 'recortada a %dx%d' % (ancho, alto)
            except Exception as e:  # sin Pillow queda la franja de la ventana a la derecha
                recorte = 'sin recortar (%s)' % e
    else:
        url = 'http://127.0.0.1:%d/editor.html?%s&__latido=7000' % (PUERTO, query)
        proc = edge(['--screenshot=' + png, url], perfil, ancho, alto, 30000, extra)
    return {'png': os.path.relpath(png, APP).replace('\\', '/'), 'existe': os.path.exists(png), 'recorte': recorte,
            'bytes': os.path.getsize(png) if os.path.exists(png) else 0,
            'consolaEdge': [l for l in consola_edge(proc.stderr.decode('utf-8', 'replace')) if 'rcj' in l.lower() or 'error' in l.lower()][:10]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--perfiles', default=os.environ.get('RCJ_TMP') or tempfile.gettempdir())
    ap.add_argument('--sin-capturas', action='store_true')
    ap.add_argument('paginas', nargs='*')
    args = ap.parse_args()
    elegidas = [p for p in PAGINAS if not args.paginas or p[0] in args.paginas]

    srv = levantar_servidor()
    resultados = []
    capturas = []
    try:
        for i, (p, extra) in enumerate(elegidas):
            perfil = os.path.join(args.perfiles, 'edge-editor-%s' % p.replace('.html', ''))
            shutil.rmtree(perfil, ignore_errors=True)
            r = correr_pagina(p, extra, perfil)
            resultados.append(r)
            print(json.dumps(r, ensure_ascii=False, indent=1))
            ex = r.get('extra') or {}
            if args.sin_capturas or not ex.get('mapId'):
                continue
            q = 'map=%s' % ex['mapId']
            if p == 'editor-guardar.html':
                capturas.append(capturar(q, 'editor', perfil, 1366, 900, []))
                capturas.append(capturar(q, 'editor', perfil, 1024, 768, []))
            if p == 'editor-tactil.html':
                capturas.append(capturar(q, 'editor-tactil', perfil, 1024, 768, ['--touch-events=enabled']))
                capturas.append(capturar(q, 'editor-movil', perfil, 412, 915, ['--touch-events=enabled']))
                if ex.get('modal'):
                    qm = q + '&__modal=%s' % ex['modal']
                    capturas.append(capturar(qm, 'editor-modal-tactil', perfil, 1024, 768, ['--touch-events=enabled']))
                    capturas.append(capturar(qm, 'editor-modal-movil', perfil, 412, 915, ['--touch-events=enabled']))
    finally:
        srv.shutdown()
        srv.server_close()

    print('\n==== CAPTURAS ====')
    for c in capturas:
        print(json.dumps(c, ensure_ascii=False))
    print('\n==== RESUMEN ====')
    for r in resultados:
        print('%-26s %-6s total=%-4s fallas=%-3s errores=%-3s (%ss)' % (
            r.get('pagina'), 'OK' if r.get('ok') else 'FALLA', r.get('total'), len(r.get('fallas') or []),
            len(r.get('errores') or []), r.get('segundos')))
    ok = resultados and all(r.get('ok') for r in resultados) and all(c['existe'] for c in capturas)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
