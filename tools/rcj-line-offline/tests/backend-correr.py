# -*- coding: utf-8 -*-
"""Pruebas del área backend en Edge headless.

Uso:  python tests/backend-correr.py [pagina1.html pagina2.html ...]
      (sin argumentos corre todas las tests/backend-*.html, salvo las páginas hijas)

Levanta un servidor http.server (ThreadingHTTPServer + SimpleHTTPRequestHandler, igual que
`python -m http.server 8802 --bind 127.0.0.1`) sobre la carpeta de la app, con UN agregado solo para
pruebas: GET /__latido?ms=N espera N ms y responde 204. Las páginas de prueba (backend-comun.js)
mantienen un fetch a /__latido pendiente mientras corren: con --virtual-time-budget, Edge headless
pausa el tiempo virtual mientras haya pedidos de red pendientes, y así el --dump-dom no se dispara
antes de que terminen las operaciones de IndexedDB (que corren en otro hilo y no frenan el tiempo
virtual). Con el `python -m http.server` común el latido da 404 y la página deja de latir.

Abre cada página con Edge headless (--dump-dom), extrae <pre id="resultado">JSON</pre>, imprime un
resumen y apaga el servidor al terminar. Cada página se corre con un --user-data-dir nuevo.
"""
import functools
import html
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

PUERTO = 8802
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.environ.get('RCJ_TMP') or tempfile.gettempdir()


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

    def log_message(self, *args):
        pass


def levantar_servidor():
    manejador = functools.partial(Manejador, directory=APP)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PUERTO), manejador)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    return srv


def esperar_servidor():
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:%d/tests/backend-fixtures/ejemplo-01.json' % PUERTO, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def correr_pagina(pagina, n):
    perfil = os.path.join(TMP, 'edge-backend-%d-%d' % (os.getpid(), n))
    url = 'http://127.0.0.1:%d/tests/%s' % (PUERTO, pagina)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
           '--user-data-dir=' + perfil, '--virtual-time-budget=60000', '--dump-dom', url]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    salida = proc.stdout.decode('utf-8', 'replace')
    m = re.search(r'<pre id="resultado">(.*?)</pre>', salida, re.S)
    if not m:
        return {'pagina': pagina, 'ok': False, 'error': 'sin #resultado', 'dom': salida[:2000], 'segundos': round(time.time() - t0, 1)}
    crudo = html.unescape(m.group(1))
    try:
        datos = json.loads(crudo)
    except Exception as e:
        return {'pagina': pagina, 'ok': False, 'error': 'resultado no es JSON: %s' % e, 'crudo': crudo[:3000], 'segundos': round(time.time() - t0, 1)}
    datos['segundos'] = round(time.time() - t0, 1)
    datos['pagina'] = pagina
    return datos


def main():
    paginas = sys.argv[1:] or sorted(f for f in os.listdir(os.path.join(APP, 'tests'))
                                     if f.startswith('backend-') and f.endswith('.html') and 'hijo' not in f)
    srv = levantar_servidor()
    resultados = []
    try:
        if not esperar_servidor():
            print('ERROR: el servidor no respondió en el puerto', PUERTO)
            return 2
        for i, p in enumerate(paginas):
            r = correr_pagina(p, i)
            resultados.append(r)
            print(json.dumps(r, ensure_ascii=False, indent=1))
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
