# -*- coding: utf-8 -*-
"""Pruebas del área juez en Edge headless (puerto 8804).

Uso:
  python tests/juez-correr.py [--perfiles DIR] [--sin-capturas] [pagina.html ...]
  (sin páginas corre juez-escenario, juez-recarga, juez-flags y juez-modal)

Levanta un http.server (ThreadingHTTPServer + SimpleHTTPRequestHandler, igual que
`python -m http.server 8804 --bind 127.0.0.1`) sobre la carpeta de la app con UN agregado de prueba:
GET /__latido?ms=N espera N ms y responde 204 (ver tests/juez-comun.js). Abre cada página con Edge
headless (--dump-dom), extrae <pre id="resultado">JSON</pre> y junta además los mensajes de consola que
Edge escribe por stderr (--enable-logging=stderr). Después toma capturas de juez.html a 1024x768 y
1366x900 en tests/capturas/ usando el mismo perfil (misma IndexedDB) que la prueba que sembró los datos.
Apaga el servidor al terminar.
"""
import argparse
import base64
import concurrent.futures
import functools
import socket
import struct
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

PUERTO = 8804
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGINAS = ['juez-escenario.html', 'juez-recarga.html', 'juez-flags.html', 'juez-movil.html']
TAMANIOS = [(1024, 768), (1366, 900), (412, 915)]


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

    def end_headers(self):
        # Sin caché: al iterar en un navegador no headless, los .html/.js de prueba viejos quedaban en caché.
        self.send_header('Cache-Control', 'no-store')
        return super().end_headers()

    def log_message(self, *args):
        pass


def levantar_servidor():
    manejador = functools.partial(Manejador, directory=APP)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PUERTO), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:%d/juez.html' % PUERTO, timeout=1)
            return srv
        except Exception:
            time.sleep(0.2)
    raise SystemExit('el servidor no respondió en el puerto %d' % PUERTO)


def consola_edge(stderr):
    """Líneas CONSOLE que Edge headless escribe con --enable-logging=stderr (sin ruido de GPU/red del proceso)."""
    salida = []
    for linea in stderr.splitlines():
        if 'CONSOLE' in linea:
            salida.append(linea.strip()[:600])
    return salida


def edge(args, perfil, ancho, alto, presupuesto, espera=600):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
           '--hide-scrollbars', '--enable-logging=stderr', '--v=0',
           '--user-data-dir=' + perfil, '--window-size=%d,%d' % (ancho, alto),
           '--virtual-time-budget=%d' % presupuesto] + args
    return subprocess.run(cmd, capture_output=True, timeout=espera)


def decodificar(datos):
    """El volcado de Edge es UTF-8; si no lo es (consola en cp1252), se decodifica como cp1252."""
    try:
        return datos.decode('utf-8')
    except UnicodeDecodeError:
        return datos.decode('cp1252', 'replace')


def correr_pagina(pagina, perfil):
    url = 'http://127.0.0.1:%d/tests/%s' % (PUERTO, pagina)
    t0 = time.time()
    try:
        proc = edge(['--dump-dom', url], perfil, 1366, 900, 180000)
    except subprocess.TimeoutExpired:
        return {'pagina': pagina, 'ok': False, 'error': 'Edge no terminó en 600 s', 'segundos': round(time.time() - t0, 1)}
    salida = decodificar(proc.stdout)
    stderr = decodificar(proc.stderr)
    m = re.search(r'<pre id="resultado">(.*?)</pre>', salida, re.S)
    if not m:
        return {'pagina': pagina, 'ok': False, 'error': 'sin #resultado', 'dom': salida[:1500], 'consolaEdge': consola_edge(stderr), 'segundos': round(time.time() - t0, 1)}
    try:
        datos = json.loads(html.unescape(m.group(1)))
    except Exception as e:
        return {'pagina': pagina, 'ok': False, 'error': 'resultado no es JSON: %s' % e, 'crudo': m.group(1)[:3000], 'segundos': round(time.time() - t0, 1)}
    datos['consolaEdge'] = consola_edge(stderr)
    datos['segundos'] = round(time.time() - t0, 1)
    datos['pagina'] = pagina
    return datos


class WebSocketMinimo:
    """Cliente WebSocket mínimo (RFC 6455, solo texto) sobre socket: la máquina no tiene websocket-client."""

    def __init__(self, url):
        u = urllib.parse.urlparse(url)
        self.s = socket.create_connection((u.hostname, u.port), timeout=120)
        clave = base64.b64encode(os.urandom(16)).decode()
        pedido = ('GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                  'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n') % (u.path, u.hostname, u.port, clave)
        self.s.sendall(pedido.encode())
        resp = b''
        while b'\r\n\r\n' not in resp:
            trozo = self.s.recv(4096)
            if not trozo:
                raise ConnectionError('handshake WebSocket cortado')
            resp += trozo
        cabecera, self.buf = resp.split(b'\r\n\r\n', 1)
        if b' 101 ' not in cabecera.split(b'\r\n')[0] + b' ':
            raise ConnectionError('handshake WebSocket rechazado: %r' % cabecera[:200])

    def enviar(self, texto):
        datos = texto.encode('utf-8')
        n = len(datos)
        cab = bytearray([0x81])
        if n < 126:
            cab.append(0x80 | n)
        elif n < 65536:
            cab.append(0x80 | 126)
            cab += struct.pack('>H', n)
        else:
            cab.append(0x80 | 127)
            cab += struct.pack('>Q', n)
        mascara = os.urandom(4)
        cab += mascara
        self.s.sendall(bytes(cab) + bytes(b ^ mascara[i % 4] for i, b in enumerate(datos)))

    def _leer(self, n):
        while len(self.buf) < n:
            trozo = self.s.recv(1 << 20)
            if not trozo:
                raise ConnectionError('WebSocket cerrado')
            self.buf += trozo
        datos, self.buf = self.buf[:n], self.buf[n:]
        return datos

    def recibir(self):
        partes = b''
        while True:
            b1, b2 = self._leer(2)
            n = b2 & 0x7f
            if n == 126:
                n = struct.unpack('>H', self._leer(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._leer(8))[0]
            if b2 & 0x80:
                self._leer(4)
            datos = self._leer(n)
            op = b1 & 0x0f
            if op == 8:
                raise ConnectionError('WebSocket cerrado por el navegador')
            if op in (9, 10):
                continue
            partes += datos
            if b1 & 0x80:
                return partes.decode('utf-8', 'replace')

    def cerrar(self):
        try:
            self.s.close()
        except OSError:
            pass


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.n = 0

    def llamar(self, metodo, **params):
        self.n += 1
        mid = self.n
        self.ws.enviar(json.dumps({'id': mid, 'method': metodo, 'params': params}))
        while True:
            m = json.loads(self.ws.recibir())
            if m.get('id') == mid:
                if 'error' in m:
                    raise RuntimeError('%s: %s' % (metodo, m['error']))
                return m.get('result', {})


def capturar(vista, perfiles):
    """Captura juez.html en la vista dada a cada tamaño con el protocolo DevTools (Page.captureScreenshot).

    No usa --screenshot: en ese modo Edge headless no da IndexedDB (DOMException) y el juez del iframe no ve los
    datos sembrados. Acá Edge corre en tiempo real con --remote-debugging-port, un perfil nuevo por vista, y
    tests/juez-captura.html siembra sus datos y juega el tramo. El tamaño se emula exacto
    (Emulation.setDeviceMetricsOverride; mobile + táctil debajo de 768 px)."""
    carpeta = os.path.join(APP, 'tests', 'capturas')
    os.makedirs(carpeta, exist_ok=True)
    hechas = []
    nombre = 'juez-' + vista
    perfil = os.path.join(perfiles, 'edge-juez-captura-%s-%d' % (vista, int(time.time() * 1000)))
    os.makedirs(perfil, exist_ok=True)
    # Mismos argumentos que la sonda que funcionó. Con navegación inmediata tras arrancar un perfil nuevo,
    # RCJLocal.store no pudo abrir IndexedDB y cayó a memoria (el juez del iframe no veía los datos).
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
           '--user-data-dir=' + perfil, '--remote-debugging-port=0', 'about:blank']
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        archivo = os.path.join(perfil, 'DevToolsActivePort')
        fin = time.time() + 30
        while not os.path.exists(archivo) and time.time() < fin:
            time.sleep(0.2)
        puerto_cdp = int(open(archivo).read().split()[0])
        destinos = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % puerto_cdp, timeout=10).read())
        pagina = [d for d in destinos if d.get('type') == 'page'][0]
        ws = WebSocketMinimo(pagina['webSocketDebuggerUrl'])
        cdp = CDP(ws)
        cdp.llamar('Page.enable')
        # Precalentamiento SIN emulación: la primera apertura de IndexedDB de un perfil nuevo bajo
        # Emulation.setDeviceMetricsOverride (igual que en modo --screenshot) falla y RCJLocal.store cae a memoria.
        # Se carga una vez la página de captura sin emular (crea y siembra la base) y recién después se emula.
        cdp.llamar('Page.navigate', url='http://127.0.0.1:%d/tests/juez-captura.html?vista=prechequeo&calentar=1' % PUERTO)
        fin = time.time() + 90
        while time.time() < fin:
            time.sleep(0.5)
            try:
                v = cdp.llamar('Runtime.evaluate', returnByValue=True, expression=(
                    "(function(){var e=document.getElementById('resultado');return e ? e.textContent : ''})()"))
                v = (v.get('result') or {}).get('value')
            except RuntimeError:
                v = None
            if v and v != 'PENDIENTE':
                break
        for ancho, alto in TAMANIOS:
            png = os.path.join(carpeta, '%s-%dx%d.png' % (nombre, ancho, alto))
            if os.path.exists(png):
                os.remove(png)
            movil = ancho < 768
            estado = None
            error = None
            detalles = None
            try:
                cdp.llamar('Emulation.setDeviceMetricsOverride', width=ancho, height=alto, deviceScaleFactor=1, mobile=movil)
                if movil:
                    cdp.llamar('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=5)
                cdp.llamar('Page.navigate', url='http://127.0.0.1:%d/tests/juez-captura.html?vista=%s' % (PUERTO, vista))
                fin = time.time() + 120
                while time.time() < fin:
                    time.sleep(0.5)
                    try:
                        r = cdp.llamar('Runtime.evaluate', returnByValue=True, expression=(
                            "(function(){var e=document.getElementById('resultado');"
                            "return e ? e.textContent : ''})()"))
                        estado = (r.get('result') or {}).get('value')
                    except RuntimeError:
                        estado = None
                    if estado and estado != 'PENDIENTE':
                        break
                # juez-captura.html vuelca el JSON de T.terminar: extra.estado = 'LISTO' | 'ERROR ...'
                try:
                    res = json.loads(estado) if estado and estado.startswith('{') else None
                except ValueError:
                    res = None
                if res is not None:
                    extra_c = res.get('extra') or {}
                    estado = extra_c.get('estado')
                    if estado != 'LISTO':
                        detalles = {'errores': res.get('errores'), 'consola': res.get('consola'),
                                    'pedidos': extra_c.get('pedidos'), 'juez': extra_c.get('juez')}
                    elif res.get('errores'):
                        detalles = {'errores': res.get('errores')}
                if estado != 'LISTO':
                    error = 'la página de captura no quedó LISTO: %r' % estado
                datos = cdp.llamar('Page.captureScreenshot', format='png')['data']
                with open(png, 'wb') as f:
                    f.write(base64.b64decode(datos))
            except Exception as e:
                error = repr(e)
            hechas.append({'png': os.path.relpath(png, APP).replace('\\', '/'), 'existe': os.path.exists(png),
                           'bytes': os.path.getsize(png) if os.path.exists(png) else 0, 'estado': estado, 'error': error,
                           'detalles': detalles})
    finally:
        if ws:
            ws.cerrar()
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    return hechas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--perfiles', default=os.environ.get('RCJ_TMP') or tempfile.gettempdir())
    ap.add_argument('--sin-capturas', action='store_true')
    # Default 1: con varios Edge headless simultáneos ningún pedido llegaba al servidor (todas las páginas fallaban en 2,5 s)
    ap.add_argument('--paralelo', type=int, default=1, help='páginas de prueba simultáneas (cada una con su perfil)')
    ap.add_argument('paginas', nargs='*')
    args = ap.parse_args()
    paginas = args.paginas or PAGINAS
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # la consola de Windows es cp1252

    srv = levantar_servidor()
    resultados = []
    capturas = []
    try:
        perfiles = {}
        for i, p in enumerate(paginas):
            perfiles[p] = os.path.join(args.perfiles, 'edge-juez-%d' % i)
            shutil.rmtree(perfiles[p], ignore_errors=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.paralelo)) as ejecutor:
            futuros = [ejecutor.submit(correr_pagina, p, perfiles[p]) for p in paginas]
            resultados = [f.result() for f in futuros]
        for r in resultados:  # primero todos los resultados: una captura que falle no los puede tapar
            print(json.dumps(r, ensure_ascii=False, indent=1))
        sys.stdout.flush()
        if not args.sin_capturas:
            for vista in ('prechequeo', 'puntuacion', 'modal'):
                try:
                    capturas += capturar(vista, args.perfiles)
                except Exception as e:
                    capturas.append({'png': 'juez-' + vista, 'existe': False, 'error': repr(e)})
    finally:
        srv.shutdown()
        srv.server_close()

    print('\n==== CAPTURAS ====')
    for c in capturas:
        print(json.dumps(c, ensure_ascii=False))
    print('\n==== RESUMEN ====')
    for r in resultados:
        print('%-26s %-6s total=%-4s fallas=%-3s errores=%-3s consolaEdge=%-3s (%ss)' % (
            r.get('pagina'), 'OK' if r.get('ok') else 'FALLA', r.get('total'), len(r.get('fallas') or []),
            len(r.get('errores') or []), len(r.get('consolaEdge') or []), r.get('segundos')))
    ok = resultados and all(r.get('ok') for r in resultados) and all(c['existe'] for c in capturas)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
