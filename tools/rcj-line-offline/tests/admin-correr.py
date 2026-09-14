# -*- coding: utf-8 -*-
"""Pruebas del área admin en Edge headless (puerto 8807).

Uso:
  python tests/admin-correr.py [--sin-capturas | --solo-capturas] [--paginas index.html,mapas.html] [--tamanios 412,1024]

1) Flujo completo desde cero (tests/admin-flujo.html, --dump-dom) con un perfil de Edge nuevo.
2) Capturas en tests/capturas/admin-<pagina>-<ancho>x<alto>.png (tests/admin-captura.html, --screenshot) a
   1366x900, 1024x768 y 412x915 (celular), con el MISMO perfil: se ven los datos que dejó el flujo.
   Cada captura mide además scroll horizontal, controles inalcanzables y controles chicos para el dedo.

Servidor: http.server (ThreadingHTTPServer + SimpleHTTPRequestHandler, igual que
`python -m http.server 8807 --bind 127.0.0.1`) sobre la carpeta de la app, con dos agregados SOLO de prueba:
  GET  /__latido?ms=N    espera N ms y responde 204 (mantiene pausado el tiempo virtual; ver admin-comun.js)
  POST /__resultado?nombre=X  guarda el JSON de una captura (--screenshot no permite --dump-dom)
Se juntan también los mensajes de consola que Edge escribe por stderr (--enable-logging=stderr).
Perfiles de Edge en $RCJ_TMP (o el temporal del sistema). Apaga el servidor al terminar.
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

PUERTO = 8807
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.environ.get('RCJ_TMP') or tempfile.gettempdir()
CAPTURAS = os.path.join(APP, 'tests', 'capturas')
# (pagina, [(ancho, alto, iframes apilados)])
PLAN = [
    ('index.html', [(1366, 900, 2), (1024, 768, 2), (412, 915, 4)]),
    ('mapas.html', [(1366, 900, 1), (1024, 768, 1), (412, 915, 2)]),
    ('corridas.html', [(1366, 900, 1), (1024, 768, 1), (412, 915, 2)]),
    ('admin-corridas.html', [(1366, 900, 3), (1024, 768, 4), (412, 915, 8)]),
    ('configuracion.html', [(1366, 900, 2), (1024, 768, 2), (412, 915, 5)]),
]
RESULTADOS_POST = {}


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
        if u.path == '/__resultado':
            largo = int(self.headers.get('Content-Length') or 0)
            cuerpo = self.rfile.read(largo).decode('utf-8', 'replace')
            nombre = (urllib.parse.parse_qs(u.query).get('nombre') or [''])[0]
            RESULTADOS_POST[nombre] = cuerpo
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(405)

    def log_message(self, *args):
        pass


def levantar_servidor():
    manejador = functools.partial(Manejador, directory=APP)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PUERTO), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:%d/index.html' % PUERTO, timeout=1)
            return srv
        except Exception:
            time.sleep(0.2)
    raise SystemExit('el servidor no respondió en el puerto %d' % PUERTO)


def consola_edge(stderr):
    return [l.strip()[:600] for l in stderr.splitlines() if 'CONSOLE' in l]


def edge(args, perfil, ancho, alto, presupuesto, timeout=600):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
           '--hide-scrollbars', '--enable-logging=stderr', '--v=0',
           '--user-data-dir=' + perfil, '--window-size=%d,%d' % (ancho, alto),
           '--virtual-time-budget=%d' % presupuesto] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def correr_flujo(perfil, pagina='admin-flujo.html'):
    url = 'http://127.0.0.1:%d/tests/%s' % (PUERTO, pagina)
    t0 = time.time()
    proc = edge(['--dump-dom', url], perfil, 1366, 900, 600000)
    salida = proc.stdout.decode('utf-8', 'replace')
    stderr = proc.stderr.decode('utf-8', 'replace')
    m = re.search(r'<pre id="resultado">(.*?)</pre>', salida, re.S)
    if not m:
        return {'pagina': 'admin-flujo.html', 'ok': False, 'error': 'sin #resultado', 'dom': salida[:1500],
                'consolaEdge': consola_edge(stderr)[-30:], 'segundos': round(time.time() - t0, 1)}
    crudo = html.unescape(m.group(1))
    try:
        datos = json.loads(crudo)
    except Exception as e:
        return {'pagina': 'admin-flujo.html', 'ok': False, 'error': 'resultado no es JSON: %s' % e, 'crudo': crudo[:3000],
                'consolaEdge': consola_edge(stderr)[-30:], 'segundos': round(time.time() - t0, 1)}
    datos['consolaEdge'] = consola_edge(stderr)
    datos['segundos'] = round(time.time() - t0, 1)
    datos['pagina'] = 'admin-flujo.html'
    return datos


def capturar(pagina, ancho, alto, n, perfil):
    nombre = 'admin-%s-%dx%d' % (pagina.replace('.html', ''), ancho, alto)
    png = os.path.join(CAPTURAS, nombre + '.png')
    if os.path.exists(png):
        os.remove(png)
    url = 'http://127.0.0.1:%d/tests/admin-captura.html?pagina=%s&ancho=%d&alto=%d&n=%d&nombre=%s' % (
        PUERTO, pagina, ancho, alto, n, nombre)
    t0 = time.time()
    proc = edge(['--screenshot=' + png, url], perfil, ancho, n * (alto + 4), 120000)
    res = {'captura': nombre + '.png', 'existe': os.path.exists(png), 'segundos': round(time.time() - t0, 1)}
    crudo = RESULTADOS_POST.pop(nombre, None)
    if crudo is None:
        res['ok'] = False
        res['error'] = 'la página de captura no mandó resultado'
    else:
        try:
            res.update(json.loads(crudo))
        except Exception as e:
            res['ok'] = False
            res['error'] = 'resultado no es JSON: %s' % e
    res['consolaEdge'] = [l for l in consola_edge(proc.stderr.decode('utf-8', 'replace')) if 'Download' not in l][-10:]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sin-capturas', action='store_true')
    ap.add_argument('--solo-capturas', action='store_true')
    ap.add_argument('--paginas', default='')
    ap.add_argument('--tamanios', default='')
    ap.add_argument('--pruebas', default='', help='páginas extra a correr con --dump-dom (perfil nuevo cada una), p. ej. admin-export.html')
    args = ap.parse_args()
    perfil = os.path.join(TMP, 'edge-admin-flujo')
    srv = levantar_servidor()
    flujo = None
    extras = []
    capturas = []
    try:
        for i, pagina in enumerate(p for p in args.pruebas.split(',') if p):
            perfil_extra = os.path.join(TMP, 'edge-admin-extra-%d' % i)
            shutil.rmtree(perfil_extra, ignore_errors=True)
            r = correr_flujo(perfil_extra, pagina)
            r['pagina'] = pagina
            extras.append(r)
            print(json.dumps(r, ensure_ascii=False, indent=1))
        if not args.solo_capturas:
            shutil.rmtree(perfil, ignore_errors=True)
            flujo = correr_flujo(perfil)
            print(json.dumps(flujo, ensure_ascii=False, indent=1))
        if not args.sin_capturas:
            os.makedirs(CAPTURAS, exist_ok=True)
            paginas = [p for p in args.paginas.split(',') if p]
            anchos = [int(x) for x in args.tamanios.split(',') if x]
            for pagina, tamanios in PLAN:
                if paginas and pagina not in paginas:
                    continue
                for ancho, alto, n in tamanios:
                    if anchos and ancho not in anchos:
                        continue
                    c = capturar(pagina, ancho, alto, n, perfil)
                    capturas.append(c)
                    print(json.dumps(c, ensure_ascii=False))
    finally:
        srv.shutdown()
        srv.server_close()
    print('\n==== RESUMEN ====')
    for r in extras:
        print('%-34s %-6s total=%-4s fallas=%-3s errores=%-3s (%ss)' % (
            r.get('pagina'), 'OK' if r.get('ok') else 'FALLA', r.get('total'),
            len(r.get('fallas') or []), len(r.get('errores') or []), r.get('segundos')))
    if flujo:
        print('%-34s %-6s total=%-4s fallas=%-3s errores=%-3s (%ss)' % (
            'admin-flujo.html', 'OK' if flujo.get('ok') else 'FALLA', flujo.get('total'),
            len(flujo.get('fallas') or []), len(flujo.get('errores') or []), flujo.get('segundos')))
    for c in capturas:
        print('%-34s %-6s png=%-5s inalcanzables=%-3s chicos=%-3s scrollW=%s/%s' % (
            c['captura'], 'OK' if c.get('ok') else 'FALLA', c.get('existe'), len((c.get('extra') or {}).get('inalcanzables') or []),
            (c.get('extra') or {}).get('controlesChicos'), (c.get('extra') or {}).get('scrollWidth'), (c.get('extra') or {}).get('innerWidth')))
    ok = (flujo is None or flujo.get('ok')) and all(r.get('ok') for r in extras) and all(c.get('ok') and c.get('existe') for c in capturas)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
