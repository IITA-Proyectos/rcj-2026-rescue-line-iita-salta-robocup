# -*- coding: utf-8 -*-
"""Pruebas del área firma (firma.html, vista.html) en Edge headless.

Uso:  python tests/firma-correr.py [--sin-capturas | --solo-capturas] [--capturas=412,1024] [pagina1.html ...]
      (sin páginas corre todas las tests/firma-*.html salvo firma-captura.html)

Levanta un servidor http.server en 127.0.0.1:8805 sobre la carpeta de la app (igual que
`python -m http.server 8805 --bind 127.0.0.1`), con UN agregado solo para pruebas: GET /__latido?ms=N
espera N ms y responde 204. Las páginas de prueba (firma-comun.js) mantienen un fetch a /__latido pendiente
mientras corren: con --virtual-time-budget, Edge headless no adelanta el tiempo virtual con pedidos
pendientes, así el volcado no se dispara antes de que termine IndexedDB.

1) Corre cada página con --dump-dom, extrae <pre id="resultado">JSON</pre> y además junta los mensajes de
   consola del navegador (--enable-logging=stderr) de TODOS los marcos, para no perder errores tempranos
   de los iframes.
2) Capturas (tests/capturas/*.png) con --screenshot sobre tests/firma-captura.html.
Apaga el servidor al terminar. Perfiles de Edge en RCJ_TMP (o el temporal del sistema).
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

PUERTO = 8805
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.environ.get('RCJ_TMP') or tempfile.gettempdir()
# Ojo: con un --user-data-dir largo (p.ej. el scratchpad de la sesión, >150 caracteres) la ruta de LevelDB de
# IndexedDB supera MAX_PATH de Windows, IndexedDB falla y store.js cae a memoria POR MARCO: la página de prueba y el
# iframe de firma.html dejan de compartir datos (404 en /api/runs/line/<id>). Se usa un directorio corto.
if len(TMP) > 60:
    TMP = os.path.join(os.path.splitdrive(TMP)[0] + os.sep, 'Users', os.environ.get('USERNAME', ''), 'AppData', 'Local', 'Temp')         if os.name == 'nt' and os.environ.get('USERNAME') else tempfile.gettempdir()
CAPTURAS = os.path.join(APP, 'tests', 'capturas')


class Manejador(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/__latido':
            q = urllib.parse.parse_qs(u.query)
            ms = min(int((q.get('ms') or ['200'])[0]), 5000)
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
            urllib.request.urlopen('http://127.0.0.1:%d/firma.html' % PUERTO, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def consola(stderr):
    """Mensajes de consola del navegador (todas las frames) que parecen errores."""
    out = []
    for linea in stderr.splitlines():
        if 'CONSOLE' not in linea:
            continue
        if re.search(r'Uncaught|Error|error|TypeError|ReferenceError|Failed', linea):
            out.append(linea.strip()[:400])
    return out


def edge(args, timeout=600):
    return subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
                           '--autoplay-policy=no-user-gesture-required', '--enable-logging=stderr', '--v=0'] + args,
                          capture_output=True, timeout=timeout)


def correr_pagina(pagina, n):
    perfil = os.path.join(TMP, 'edge-firma-%d-%d' % (os.getpid(), n))
    url = 'http://127.0.0.1:%d/tests/%s' % (PUERTO, pagina)
    t0 = time.time()
    proc = edge(['--user-data-dir=' + perfil, '--window-size=1400,1000', '--virtual-time-budget=240000', '--dump-dom', url])
    salida = proc.stdout.decode('utf-8', 'replace')
    errores_consola = consola(proc.stderr.decode('utf-8', 'replace'))
    m = re.search(r'<pre id="resultado">(.*?)</pre>', salida, re.S)
    if not m:
        return {'pagina': pagina, 'ok': False, 'error': 'sin #resultado', 'dom': salida[:1500], 'consola': errores_consola,
                'segundos': round(time.time() - t0, 1)}
    try:
        datos = json.loads(html.unescape(m.group(1)))
    except Exception as e:
        return {'pagina': pagina, 'ok': False, 'error': 'resultado no es JSON: %s' % e, 'crudo': m.group(1)[:2000],
                'consola': errores_consola, 'segundos': round(time.time() - t0, 1)}
    datos['consola'] = errores_consola
    datos['segundos'] = round(time.time() - t0, 1)
    datos['pagina'] = pagina
    return datos


CAPTURAS_DEF = [
    # (archivo, query de firma-captura.html, ancho de iframe, alto de iframe, cantidad de iframes apilados)
    ('firma-arriba.png', 'pagina=firma.html', 1366, 900, 1),
    ('firma-completa.png', 'pagina=firma.html&firmar=1', 1366, 900, 5),
    ('vista-completa.png', 'pagina=vista.html', 1366, 900, 4),
    ('vista-iframe.png', 'pagina=vista.html&iframe=true&estado=2', 1366, 900, 1),
    ('vista-corregir-bugs-visuales.png', 'pagina=vista.html&scroll=rescate&flags=corregirBugsVisuales&victimas=4', 1366, 900, 1),
    ('vista-original-rescate.png', 'pagina=vista.html&scroll=rescate&victimas=4', 1366, 900, 1),
    ('firma-modal-direccion.png', 'pagina=firma.html&modal=1', 1366, 900, 1),
    # tablet horizontal
    ('firma-1024x768.png', 'pagina=firma.html&firmar=1', 1024, 768, 2),
    ('vista-1024x768.png', 'pagina=vista.html', 1024, 768, 1),
    # celular (Chrome Android 412x915)
    ('firma-412x915-arriba.png', 'pagina=firma.html', 412, 915, 1),
    ('firma-412x915-completa.png', 'pagina=firma.html&firmar=1', 412, 915, 8),
    ('vista-412x915-completa.png', 'pagina=vista.html', 412, 915, 7),
    ('vista-iframe-412x915.png', 'pagina=vista.html&iframe=true&estado=2', 412, 915, 1),
    ('firma-412x915-modal.png', 'pagina=firma.html&modal=1', 412, 915, 1),
]


def capturar(n0, solo=None):
    os.makedirs(CAPTURAS, exist_ok=True)
    res = []
    for i, (archivo, query, ancho, alto, n) in enumerate(CAPTURAS_DEF):
        if solo and not any(x in archivo for x in solo):
            continue
        perfil = os.path.join(TMP, 'edge-firma-cap-%d-%d' % (os.getpid(), n0 + i))
        destino = os.path.join(CAPTURAS, archivo)
        if os.path.exists(destino):
            os.remove(destino)
        url = 'http://127.0.0.1:%d/tests/firma-captura.html?%s&n=%d&ancho=%d&alto=%d' % (PUERTO, query, n, ancho, alto)
        proc = edge(['--user-data-dir=' + perfil, '--window-size=%d,%d' % (ancho, n * (alto + 4)), '--hide-scrollbars',
                     '--virtual-time-budget=120000', '--screenshot=' + destino, url])
        ok = os.path.exists(destino) and os.path.getsize(destino) > 5000
        res.append({'captura': archivo, 'ok': ok, 'bytes': os.path.getsize(destino) if os.path.exists(destino) else 0,
                    'consola': consola(proc.stderr.decode('utf-8', 'replace'))})
    return res


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # consola/archivo en cp1252 no puede imprimir los datos
    except Exception:
        pass
    args = sys.argv[1:]
    sin_capturas = '--sin-capturas' in args
    args = [a for a in args if a != '--sin-capturas']
    solo_capturas = '--solo-capturas' in args
    args = [a for a in args if a != '--solo-capturas']
    filtro = [a.split('=', 1)[1] for a in args if a.startswith('--capturas=')]
    filtro = filtro[0].split(',') if filtro else None
    args = [a for a in args if not a.startswith('--capturas=')]
    paginas = args or sorted(f for f in os.listdir(os.path.join(APP, 'tests'))
                             if f.startswith('firma-') and f.endswith('.html') and f != 'firma-captura.html')
    if solo_capturas:
        paginas = []
    srv = levantar_servidor()
    resultados, capturas = [], []
    try:
        if not esperar_servidor():
            print('ERROR: el servidor no respondió en el puerto', PUERTO)
            return 2
        for i, p in enumerate(paginas):
            r = correr_pagina(p, i)
            resultados.append(r)
            print(json.dumps(r, ensure_ascii=False, indent=1))
        if not sin_capturas:
            capturas = capturar(len(paginas), filtro)
            print(json.dumps(capturas, ensure_ascii=False, indent=1))
    finally:
        srv.shutdown()
        srv.server_close()
    print('\n==== RESUMEN ====')
    for r in resultados:
        print('%-30s %-6s total=%-4s fallas=%-3s errores=%-3s consola=%-3s (%ss)' % (
            r.get('pagina'), 'OK' if r.get('ok') else 'FALLA', r.get('total'), len(r.get('fallas') or []),
            len(r.get('errores') or []), len(r.get('consola') or []), r.get('segundos')))
    for c in capturas:
        print('%-36s %-6s %s bytes' % (c['captura'], 'OK' if c['ok'] else 'FALLA', c['bytes']))
    ok = all(r.get('ok') for r in resultados) and all(c['ok'] for c in capturas)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
