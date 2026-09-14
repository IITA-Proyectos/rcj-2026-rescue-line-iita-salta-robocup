# -*- coding: utf-8 -*-
"""Pruebas del área manual-ranking en Edge headless (puerto 8806).

Uso:  python tests/manual-ranking-correr.py [pagina.html ...] [--sin-capturas]
      (sin páginas corre tests/manual-ranking-manual.html y tests/manual-ranking-ranking.html)

- Levanta http.server (ThreadingHTTPServer, igual que `python -m http.server 8806 --bind 127.0.0.1`) sobre la
  carpeta de la app con un único agregado de prueba: GET /__latido?ms=N (ver tests/backend-correr.py: mantiene un
  pedido pendiente para que --virtual-time-budget no vuelque el DOM antes de que termine IndexedDB).
- Corre cada página con --dump-dom y lee <pre id="resultado">JSON</pre>.
- Lee la consola de Edge (--enable-logging=stderr) para ver errores de TODOS los marcos, incluidos los que ocurren
  en un iframe antes de que la página de prueba pueda engancharse. Una línea "Uncaught" hace fallar la página.
- Si el resultado trae extra.capturas = [{nombre, url, listo, alto}], saca capturas PNG con el MISMO perfil
  (los datos sembrados siguen en IndexedDB) usando tests/manual-ranking-captura.html, en 1366x900, 1024x768 y 412x915.
  Van a tests/capturas/manual-ranking-<nombre>-<ancho>x<alto>.png.
- Apaga el servidor al terminar.
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

PUERTO = 8806
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.environ.get('RCJ_TMP') or tempfile.gettempdir()
# Con un --user-data-dir largo (p. ej. el scratchpad de la sesión, >150 caracteres) la ruta de LevelDB supera
# MAX_PATH en Windows: IndexedDB tira DOMException, cada marco usa su store en memoria y la página no ve los datos.
if len(TMP) > 100:
    TMP = tempfile.gettempdir()
PAGINAS = ['manual-ranking-manual.html', 'manual-ranking-ranking.html', 'manual-ranking-movil.html']


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
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def esperar_servidor():
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:%d/manual.html' % PUERTO, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def consola(stderr):
    lineas = []
    for l in stderr.splitlines():
        if 'CONSOLE' in l:
            lineas.append(re.sub(r'^\[[^\]]*\]\s*', '', l)[:600])
    return lineas


def edge(args, perfil, timeout=300):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
           '--enable-logging=stderr', '--v=0', '--autoplay-policy=no-user-gesture-required',
           '--user-data-dir=' + perfil] + args
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # Edge no terminó: se devuelve lo que alcanzó a escribir (la consola sirve para ver dónde se colgó)
        class Parcial:
            stdout = e.stdout or b''
            stderr = (e.stderr or b'') + (b'\nCONSOLE TIMEOUT: Edge no termino en %d s' % timeout)
        return Parcial()


def correr_pagina(pagina, perfil):
    url = 'http://127.0.0.1:%d/tests/%s' % (PUERTO, pagina)
    t0 = time.time()
    proc = edge(['--virtual-time-budget=120000', '--window-size=1400,1000', '--dump-dom', url], perfil)
    salida = proc.stdout.decode('utf-8', 'replace')
    lineas_consola = consola(proc.stderr.decode('utf-8', 'replace'))
    m = re.search(r'<pre id="resultado">(.*?)</pre>', salida, re.S)
    if not m:
        return {'pagina': pagina, 'ok': False, 'error': 'sin #resultado', 'dom': salida[:2000], 'consola': lineas_consola}
    crudo = html.unescape(m.group(1))
    try:
        datos = json.loads(crudo)
    except Exception as e:
        return {'pagina': pagina, 'ok': False, 'error': 'resultado no es JSON: %s' % e, 'crudo': crudo[:3000], 'consola': lineas_consola}
    datos['segundos'] = round(time.time() - t0, 1)
    datos['pagina'] = pagina
    datos['consolaEdge'] = lineas_consola
    uncaught = [l for l in lineas_consola if 'Uncaught' in l]
    if uncaught:
        datos['ok'] = False
        datos['erroresConsolaEdge'] = uncaught
    return datos


TAMANOS = [(1366, 900), (1024, 768), (412, 915)]


def capturar(c, perfil, carpeta):
    """Una captura por tamaño de ventana (notebook, tablet, celular Android). c['tamanos'] limita la lista."""
    os.makedirs(carpeta, exist_ok=True)
    salida = []
    for (ancho, alto) in [tuple(t) for t in c.get('tamanos', TAMANOS)]:
        destino = os.path.join(carpeta, 'manual-ranking-%s-%dx%d.png' % (c['nombre'], ancho, alto))
        if os.path.exists(destino):
            os.remove(destino)
        params = {'url': c['url'], 'listo': c.get('listo', 'body'), 'ms': c.get('ms', 1500)}
        for k in ('api', 'scroll'):
            if c.get(k):
                params[k] = c[k]
        url = 'http://127.0.0.1:%d/tests/manual-ranking-captura.html?%s' % (PUERTO, urllib.parse.urlencode(params))
        proc = edge(['--virtual-time-budget=60000', '--hide-scrollbars', '--window-size=%d,%d' % (ancho, alto),
                     '--screenshot=' + destino, url], perfil, timeout=180)
        lineas = consola(proc.stderr.decode('utf-8', 'replace'))
        salida.append({'nombre': c['nombre'], 'tamano': '%dx%d' % (ancho, alto), 'archivo': destino,
                       'existe': os.path.exists(destino),
                       'bytes': os.path.getsize(destino) if os.path.exists(destino) else 0,
                       'uncaught': [l for l in lineas if 'Uncaught' in l]})
        # la preparación ?api= se aplica una sola vez (los datos quedan en el perfil)
        c = dict(c, api=None)
    return salida


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    con_capturas = '--sin-capturas' not in sys.argv
    paginas = args or PAGINAS
    srv = levantar_servidor()
    resultados = []
    try:
        if not esperar_servidor():
            print('ERROR: el servidor no respondió en el puerto', PUERTO)
            return 2
        for i, p in enumerate(paginas):
            perfil = os.path.join(TMP, 'edge-manual-ranking-%d-%d' % (os.getpid(), i))
            r = correr_pagina(p, perfil)
            capturas = ((r.get('extra') or {}).get('capturas') or []) if con_capturas else []
            if capturas:
                r['capturas'] = [x for c in capturas for x in capturar(c, perfil, os.path.join(APP, 'tests', 'capturas'))]
                if not all(c['existe'] and c['bytes'] > 10000 and not c['uncaught'] for c in r['capturas']):
                    r['ok'] = False
            resultados.append(r)
            print(json.dumps(r, ensure_ascii=False, indent=1))
    finally:
        srv.shutdown()
        srv.server_close()
    print('\n==== RESUMEN ====')
    for r in resultados:
        print('%-34s %-6s total=%-4s fallas=%-3s errores=%-3s (%ss)' % (
            r.get('pagina'), 'OK' if r.get('ok') else 'FALLA', r.get('total'),
            len(r.get('fallas') or []), len(r.get('errores') or []), r.get('segundos')))
    return 0 if resultados and all(r.get('ok') for r in resultados) else 1


if __name__ == '__main__':
    sys.exit(main())
